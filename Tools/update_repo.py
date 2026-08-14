"""Put the current state of the game into your git repository.

    python Tools/update_repo.py                        what would change
    python Tools/update_repo.py -m "added save slots"  commit it
    python Tools/update_repo.py -m "..." --push        commit and push
    python Tools/update_repo.py --remote <url>         connect the repository
    python Tools/update_repo.py --status               branch, remote, ahead/behind

Run it from anywhere; it always works on the project folder.

With no -m it only ever *reports*. Nothing is committed and nothing is pushed
unless you say so on the command line, so the first run is always safe.

The one thing this refuses to do
--------------------------------
Commit a save file. Your career lives in Save/savefile1..4.json, with
savefile.json kept as a pre-slots backup, and Test/gui/_out/ holds copies of
it that the test runner parks there. None of that is source, and a repository
carrying it publishes your progress and conflicts on every machine that plays.
.gitignore excludes all of it -- but a file that was committed *before* being
added to .gitignore stays tracked, which is exactly the case that would slip
through. So the staged set is checked every time, and a save in it stops the
commit rather than being explained afterwards.
"""
import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: anything matching these must never be committed -- see the module docstring
SECRETS = ("savefile.json", "savefile.dat", "Save/", "Test/gui/_out/")


def git(*args, **kw):
    """Run git in the project folder. Returns (code, output)."""
    done = subprocess.run(("git",) + args, cwd=ROOT, capture_output=True,
                          text=True, errors="replace", **kw)
    return done.returncode, ((done.stdout or "") + (done.stderr or "")).strip()


def is_repo():
    code, _ = git("rev-parse", "--git-dir")
    return code == 0


def looks_like_a_save(path):
    tidy = path.replace("\\", "/").lstrip("./")
    return any(tidy == mark or tidy.startswith(mark) for mark in SECRETS)


def staged():
    _, out = git("diff", "--cached", "--name-only")
    return [line for line in out.splitlines() if line.strip()]


def staged_additions():
    """Staged paths that would put content *into* the repository.

    Deletions have to be excluded, and not as a nicety: `git rm --cached` is
    the fix this script recommends for a save that was committed before it was
    ignored, and a staged removal still lists the path. Treating that as "a
    save is about to be committed" made the advice impossible to follow -- the
    script undid the untracking every time and sent you round again.
    """
    _, out = git("diff", "--cached", "--name-status")
    paths = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 2 or parts[0].startswith("D"):
            continue
        paths.append(parts[-1])           # renames list the destination last
    return paths


def tracked_saves():
    """Save files git is already tracking -- the case .gitignore cannot fix."""
    _, out = git("ls-files")
    return [line for line in out.splitlines() if looks_like_a_save(line)]


def show_status():
    code, branch = git("rev-parse", "--abbrev-ref", "HEAD")
    print("branch:  %s" % (branch if code == 0 else "(no commits yet)"))
    code, remote = git("remote", "get-url", "origin")
    print("remote:  %s" % (remote if code == 0 else "(none set)"))
    if code == 0:
        ahead = git("rev-list", "--count", "@{upstream}..HEAD")
        behind = git("rev-list", "--count", "HEAD..@{upstream}")
        if ahead[0] == 0 and behind[0] == 0:
            print("ahead:   %s commit(s) not pushed" % ahead[1])
            print("behind:  %s commit(s) not pulled" % behind[1])
        else:
            print("tracking: not set up yet for this branch")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Update your git repository with the current game.")
    parser.add_argument("-m", "--message",
                        help="commit message. Without it, nothing is "
                             "committed -- you just see what would change.")
    parser.add_argument("--push", action="store_true",
                        help="push after committing (needs a remote)")
    parser.add_argument("--remote",
                        help="the repository to push to. Sets 'origin', or "
                             "changes it if it is already set.")
    parser.add_argument("--branch", default="main",
                        help="branch to use when starting from scratch "
                             "(default: main)")
    parser.add_argument("--status", action="store_true",
                        help="just show branch, remote and ahead/behind")
    args = parser.parse_args(argv)

    print("project: %s" % ROOT)

    # -- a repository to work in -------------------------------------------
    if not is_repo():
        if not args.remote and not args.message:
            print()
            print("This folder is not a git repository yet.")
            print("To connect it to the one you already have:")
            print()
            print("    python Tools/update_repo.py --remote <your repo url>")
            print()
            print("That runs git init, points 'origin' at it and fetches, "
                  "without committing anything.")
            return 0
        print("starting a repository here (git init)")
        code, out = git("init", "-b", args.branch)
        if code != 0:                       # older git without -b
            git("init")
            git("checkout", "-b", args.branch)
        print("  %s" % out.splitlines()[0] if out else "  done")

    if args.remote:
        code, _ = git("remote", "get-url", "origin")
        verb = "set-url" if code == 0 else "add"
        code, out = git("remote", verb, "origin", args.remote)
        if code != 0:
            print("could not set the remote: %s" % out)
            return 1
        print("remote:  origin -> %s" % args.remote)
        code, out = git("fetch", "origin")
        print("fetch:   %s" % ("ok" if code == 0 else out.splitlines()[-1]
                               if out else "failed"))

    if args.status:
        show_status()
        return 0

    # -- what has changed --------------------------------------------------
    already = tracked_saves()
    if already:
        print()
        print("STOP -- git is already tracking save files:")
        for path in already:
            print("    %s" % path)
        print()
        print("Adding them to .gitignore does not untrack them. Remove them")
        print("from the repository but keep them on disk with:")
        print()
        for path in already:
            print('    git rm --cached "%s"' % path)
        print()
        print("then run this again. Nothing has been committed.")
        return 1

    code, out = git("add", "-A")
    if code != 0:
        print("could not stage: %s" % out)
        return 1

    files = staged()
    risky = [path for path in staged_additions() if looks_like_a_save(path)]
    if risky:
        # .gitignore should have caught these; if one is here, something is
        # forcing it in and it must not be committed by accident
        print()
        print("STOP -- these would commit your save data:")
        for path in risky:
            print("    %s" % path)
        print()
        print("Check .gitignore. Unstaging everything; nothing was committed.")
        git("reset")
        return 1

    if not files:
        print()
        print("nothing to update -- the repository already matches the folder")
        show_status()
        return 0

    print()
    print("%d file(s) to update:" % len(files))
    _, summary = git("diff", "--cached", "--stat")
    for line in summary.splitlines()[-24:]:
        print("    %s" % line)

    if not args.message:
        print()
        print("Nothing committed -- this was a dry run. To commit:")
        print()
        print('    python Tools/update_repo.py -m "what you changed"')
        print()
        print("Add --push to send it to your repository as well.")
        git("reset")
        return 0

    # -- commit ------------------------------------------------------------
    code, out = git("commit", "-m", args.message)
    if code != 0:
        print()
        print("commit failed:")
        print(out)
        return 1
    print()
    print("committed: %s" % args.message)

    if not args.push:
        print("not pushed -- add --push when you want it sent.")
        show_status()
        return 0

    code, _ = git("remote", "get-url", "origin")
    if code != 0:
        print("no remote set, so nothing to push to. Set one with:")
        print()
        print("    python Tools/update_repo.py --remote <your repo url>")
        return 1
    _, branch = git("rev-parse", "--abbrev-ref", "HEAD")
    code, out = git("push", "-u", "origin", branch)
    print("push:    %s" % ("ok" if code == 0 else "failed"))
    if code != 0:
        print(out)
        return 1
    show_status()
    return 0


if __name__ == "__main__":
    sys.exit(main())
