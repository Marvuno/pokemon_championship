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
#: the .gitignore lines that keep them out. Leading "/" anchors each one to the
#: folder holding the .gitignore, so these work whether this folder is the
#: repository root or a directory inside a larger one.
IGNORE_RULES = ("/savefile.json", "/savefile.dat", "/Save/",
                "/Test/gui/_out/")


def missing_rules():
    """Which of IGNORE_RULES this folder's .gitignore does not have."""
    path = os.path.join(ROOT, ".gitignore")
    try:
        with open(path, encoding="utf-8") as handle:
            present = {line.strip() for line in handle}
    except OSError:
        present = set()
    return [rule for rule in IGNORE_RULES if rule not in present]


def add_missing_rules():
    """Append whatever is missing. Returns the lines it added."""
    missing = missing_rules()
    if not missing:
        return []
    path = os.path.join(ROOT, ".gitignore")
    existing = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            existing = handle.read().rstrip("\n")
    block = ["", "# Save files and harness output -- never commit these #",
             "#######################################################",
             "# A career is personal progress, not source, and Test/gui/_out/",
             "# holds copies of it that the test runner parks there."]
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(existing + "\n".join(block) + "\n"
                     + "\n".join(missing) + "\n")
    return missing


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
    parser.add_argument("--fix-ignore", action="store_true",
                        help="add the save-file rules to .gitignore and stop")
    args = parser.parse_args(argv)

    print("project: %s" % ROOT)

    if args.fix_ignore:
        added = add_missing_rules()
        if added:
            print("added to .gitignore:")
            for line in added:
                print("    %s" % line)
        else:
            print(".gitignore already has all of them -- nothing to add.")
        already = tracked_saves() if is_repo() else []
        if already:
            print()
            print("Note: git is still *tracking* these, which .gitignore")
            print("cannot undo. Run this to stop tracking them (the files")
            print("stay on your disk):")
            for path in already:
                print('    git rm --cached "%s"' % path)
        return 0

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
        # .gitignore should have caught these. If one is here the rules are
        # missing or are anchored somewhere else -- which is the usual case
        # when the repository root is not this folder, or when the repo has a
        # .gitignore of its own that predates the save slots. Saying "check
        # .gitignore" and stopping was useless: it named no rule and left no
        # way forward. Print the exact lines, and offer to write them.
        git("reset")
        print()
        print("STOP -- these would commit your save data, so nothing was")
        print("staged or committed:")
        for path in risky:
            print("    %s" % path)
        print()
        print("Your .gitignore is not excluding them. It needs these lines:")
        print()
        for line in IGNORE_RULES:
            print("    %s" % line)
        print()
        missing = missing_rules()
        if missing:
            print("%d of those %s missing from %s"
                  % (len(missing), "is" if len(missing) == 1 else "are",
                     os.path.join(ROOT, ".gitignore")))
        print("Add them for me and try again with:")
        print()
        print("    python Tools/update_repo.py --fix-ignore")
        print()
        print("Nothing on disk is touched by that except .gitignore itself.")
        return 1

    committed = False
    if not files:
        print()
        print("nothing to update -- the repository already matches the folder")
        # Deliberately falls through to the --push handling below rather than
        # returning here. A commit made in an earlier run (with no --push, or
        # with a --push that failed) leaves nothing staged on the next run --
        # working tree already matches the index -- so stopping at "nothing to
        # update" silently ate the --push flag and never even tried. That is
        # probably the single most common way this tool "does nothing":
        # --remote in one run, -m in a second, --push in a third, and the
        # third finds no staged changes.
    else:
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
            if args.push:
                # --push was on the command line and is about to be silently
                # ignored, because there is nothing yet to push -- say so
                # explicitly rather than letting the dry-run message imply
                # --push wasn't tried yet, which is not true: it can't do
                # anything without a commit to send.
                print("--push was given but there is nothing committed yet "
                     "to send -- add -m as well.")
            else:
                print("Add --push to send it to your repository as well.")
            git("reset")
            return 0

        # -- commit ----------------------------------------------------
        code, out = git("commit", "-m", args.message)
        if code != 0:
            print()
            print("commit failed:")
            print(out)
            return 1
        print()
        print("committed: %s" % args.message)
        committed = True

    if not args.push:
        if committed:
            print("not pushed -- add --push when you want it sent.")
        show_status()
        return 0

    # -- push, whether or not this run made a new commit --------------
    code, _ = git("remote", "get-url", "origin")
    if code != 0:
        print("no remote set, so nothing to push to. Set one with:")
        print()
        print("    python Tools/update_repo.py --remote <your repo url>")
        return 1
    code, branch = git("rev-parse", "--abbrev-ref", "HEAD")
    if code != 0 or branch == "HEAD":
        print("no commit on this branch yet, so there is nothing to push.")
        print('Run with -m "message" first.')
        return 1
    ahead_code, ahead = git("rev-list", "--count",
                            "origin/%s..%s" % (branch, branch))
    if ahead_code == 0 and ahead == "0" and not committed:
        print("already up to date with origin/%s -- nothing to push."
              % branch)
        show_status()
        return 0
    code, out = git("push", "-u", "origin", branch)
    print("push:    %s" % ("ok" if code == 0 else "failed"))
    if code != 0:
        # Printed in full rather than summarised: the two most likely causes
        # here -- no credentials configured for this remote on this machine,
        # or the remote branch has commits this one doesn't -- both explain
        # themselves in git's own message, and guessing which one happened
        # instead of showing it would send someone chasing the wrong fix.
        print()
        print(out)
        return 1
    show_status()
    return 0


if __name__ == "__main__":
    sys.exit(main())
