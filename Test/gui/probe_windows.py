"""What native windows does the game open, and where does the loading time go?

Two measurements, both about the same complaint: something flashes up when a
battle starts, and the game feels slow.

**Windows.** A real playthrough runs as a *subprocess* with Qt offscreen, so
the interface creates no windows at all. This process then watches every
top-level window on the desktop that belongs to the child or to anything the
child spawned. Whatever that finds came from something other than the
interface -- an SDL video window, a console flash from `os.system`, a stray
Tk root. Watching from outside is the point: a console window belongs to
`conhost.exe`, a *different process*, so the child could never have seen it.

**Loading.** Every import the engine pulls in on its way to the first frame,
timed, each module charged only its own time and not its children's.

Prints measurements; it does not pass or fail.

    python Test/gui/probe_windows.py <root> <out>
"""
import os
import subprocess
import sys
import time

ROOT, OUT = sys.argv[1], sys.argv[2]

#: how often to look for new windows. A console flash is short; this is well
#: inside the time one stays up.
POLL_SECONDS = 0.05
#: give the playthrough this long before giving up on it
BUDGET_SECONDS = 300


# -- the process tree, and the windows on it -------------------------------
if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32
    _CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    TH32CS_SNAPPROCESS = 0x00000002

    class PROCESSENTRY32(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD),
                    ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                    ("th32ModuleID", wintypes.DWORD),
                    ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD),
                    ("pcPriClassBase", ctypes.c_long),
                    ("dwFlags", wintypes.DWORD),
                    ("szExeFile", ctypes.c_char * 260)]

    def process_table():
        """{pid: (parent_pid, exe_name)} for everything running."""
        table = {}
        snapshot = _kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snapshot == -1:
            return table
        try:
            entry = PROCESSENTRY32()
            entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
            ok = _kernel32.Process32First(snapshot, ctypes.byref(entry))
            while ok:
                table[int(entry.th32ProcessID)] = (
                    int(entry.th32ParentProcessID),
                    entry.szExeFile.decode("mbcs", "replace"))
                ok = _kernel32.Process32Next(snapshot, ctypes.byref(entry))
        finally:
            _kernel32.CloseHandle(snapshot)
        return table

    def family(root_pid):
        """`root_pid` and every descendant of it that is running now."""
        table = process_table()
        kin = {root_pid: table.get(root_pid, (0, "?"))[1]}
        # repeat until nothing new: a grandchild can appear in any table order
        growing = True
        while growing:
            growing = False
            for pid, (parent, name) in table.items():
                if parent in kin and pid not in kin:
                    kin[pid] = name
                    growing = True
        return kin

    def windows_of(pids):
        """Every top-level window owned by any of `pids`."""
        found = []

        @_CB
        def visit(hwnd, _):
            pid = wintypes.DWORD()
            _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value not in pids:
                return True
            name = ctypes.create_unicode_buffer(256)
            _user32.GetClassNameW(hwnd, name, 256)
            length = _user32.GetWindowTextLengthW(hwnd)
            title = ctypes.create_unicode_buffer(length + 1)
            _user32.GetWindowTextW(hwnd, title, length + 1)
            found.append((int(hwnd), int(pid.value), name.value, title.value,
                          bool(_user32.IsWindowVisible(hwnd))))
            return True

        _user32.EnumWindows(visit, 0)
        return found
else:
    def family(root_pid):
        return {root_pid: "?"}

    def windows_of(pids):
        return []


def watch_playthrough(report):
    """Drive a real game in a child process and log what it puts on screen."""
    environment = dict(os.environ)
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment["PYTHONUNBUFFERED"] = "1"
    child = subprocess.Popen(
        [sys.executable, os.path.join("Test", "gui", "playthrough.py"),
         ROOT, OUT, "Probe"],
        cwd=ROOT, env=environment,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    seen_windows, seen_pids, sightings = set(), set(), []
    started = time.perf_counter()
    while child.poll() is None:
        if time.perf_counter() - started > BUDGET_SECONDS:
            child.kill()
            sightings.append(("TIMEOUT", "", "", False, 0.0))
            break
        kin = family(child.pid)
        for pid, name in kin.items():
            if pid not in seen_pids:
                seen_pids.add(pid)
                sightings.append(("process", name, "", True,
                                  time.perf_counter() - started))
        for hwnd, pid, cls, title, visible in windows_of(set(kin)):
            if hwnd in seen_windows:
                continue
            seen_windows.add(hwnd)
            sightings.append(("window", "%s (%s)" % (cls, kin.get(pid, "?")),
                              title, visible, time.perf_counter() - started))
        time.sleep(POLL_SECONDS)

    report("playthrough exited with %s after %.1fs"
           % (child.returncode, time.perf_counter() - started))
    report("")
    report("Everything the game put on the desktop or started as a process")
    report("(Qt ran offscreen, so no entry here belongs to the interface):")
    kinds = [s for s in sightings if s[0] == "window"]
    if not kinds:
        report("    no windows -- nothing pops up")
    for kind, what, title, visible, when in sightings:
        report("    %7s  +%6.1fs  %-40s %-24r visible=%s"
               % (kind, when, what, title, visible))


def time_imports(report):
    """What the engine costs to load, module by module."""
    # __ROOT__ rather than %r: the script below is full of %-formats of its
    # own, and interpolating it with % would try to read them as fields.
    script = r"""
import builtins, os, sys, time
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, __ROOT__)
os.chdir(__ROOT__)
real, spent, stack = builtins.__import__, {}, []
def timed(name, *a, **k):
    if name in sys.modules:
        return real(name, *a, **k)
    stack.append(name)
    began = time.perf_counter()
    try:
        return real(name, *a, **k)
    finally:
        took = (time.perf_counter() - began) * 1000.0
        stack.pop()
        for parent in stack:
            spent[parent] = spent.get(parent, 0.0) - took
        spent[name] = spent.get(name, 0.0) + took
builtins.__import__ = timed
began = time.perf_counter()
import main
whole = (time.perf_counter() - began) * 1000.0
builtins.__import__ = real
print("TOTAL %.0f" % whole)
for name, ms in sorted(spent.items(), key=lambda kv: -kv[1])[:18]:
    if ms >= 5:
        print("%.0f\t%s" % (ms, name))
""".replace("__ROOT__", repr(ROOT))
    done = subprocess.run([sys.executable, "-c", script], cwd=ROOT,
                          capture_output=True, text=True, timeout=180)
    report("")
    report("Loading the engine, module by module (own time, not children's):")
    for line in done.stdout.splitlines():
        if line.startswith("TOTAL"):
            report("    %s ms for `import main` altogether"
                   % line.split()[1])
            continue
        if "\t" in line:
            ms, name = line.split("\t", 1)
            report("    %8s ms  %s" % (ms, name))
    if done.stderr.strip():
        report("    (stderr: %s)" % done.stderr.strip()[:400])


def main():
    lines = []

    def report(line=""):
        lines.append(line)
        print(line)

    time_imports(report)
    report("")
    watch_playthrough(report)
    with open(os.path.join(OUT, "windows.txt"), "w", encoding="utf-8") as out:
        out.write("\n".join(lines) + "\n")


main()
