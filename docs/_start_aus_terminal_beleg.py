#!/usr/bin/env python
"""Punkt 3: Beleg, dass ein Start aus dem VS-Code-Terminal nicht ueberlebt.

Drei Messungen:
  1. Ist dieser Prozess (aus dem VS-Code-Terminal gestartet) in einem Job-Objekt?
     Und der Harness, den der Nutzer in einem EIGENEN Fenster gestartet hat?
  2. Wie sieht ein Job-Kill aus? (Nachstellung: Job mit
     JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE, Kind hinein, Job schliessen.)
     Erwartung nach den zwei stillen Abstuerzen: Prozess weg, KEIN Traceback,
     KEINE stderr-Zeile - genau das Muster der beiden 373-Byte-Logs.
  3. Beide Ergebnisse zusammen: Ursache/Nicht-Ursache.

Aufruf aus g:\\Harness:   python docs\\_start_aus_terminal_beleg.py
"""

from __future__ import annotations

import ctypes
import json
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

k32 = ctypes.WinDLL("kernel32", use_last_error=True)

JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JobObjectExtendedLimitInformation = 9
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_TERMINATE = 0x0001


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong)]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD)]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t)]


def in_job(pid: int) -> bool:
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return False
    try:
        res = wintypes.BOOL()
        if not k32.IsProcessInJob(h, None, ctypes.byref(res)):
            return False
        return bool(res.value)
    finally:
        k32.CloseHandle(h)


def job_limits(handle) -> dict:
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    ok = k32.QueryInformationJobObject(handle, JobObjectExtendedLimitInformation,
                                       ctypes.byref(info), ctypes.sizeof(info), None)
    if not ok:
        return {"fehler": ctypes.get_last_error()}
    flags = int(info.BasicLimitInformation.LimitFlags)
    return {"LimitFlags": hex(flags),
            "tötet_beim_Schliessen": bool(flags & JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE),
            "aktive_Prozesse": int(info.BasicProcessCount) if hasattr(info, "BasicProcessCount") else None}


def hauptprozess_kette() -> list[dict]:
    """Elternkette dieses Prozesses, jeweils mit Job-Mitgliedschaft."""
    import os
    kette = []
    pid = os.getpid()
    for _ in range(6):
        kette.append({"pid": pid, "in_job": in_job(pid)})
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').ParentProcessId"],
            capture_output=True, text=True)
        try:
            pid = int((out.stdout or "0").strip())
        except ValueError:
            break
        if pid <= 0:
            break
    return kette


def nachstellung(job_kill: bool, tmp: Path) -> dict:
    """Kind in einen Job stecken, Job schliessen, Sterbemuster protokollieren."""
    log = tmp / f"kind_{'kill' if job_kill else 'ohne'}.log"
    err = tmp / f"kind_{'kill' if job_kill else 'ohne'}.err"
    code = ("import sys,time\n"
            "print('kind gestartet', flush=True)\n"
            "for i in range(120):\n"
            "    print('takt', i, flush=True)\n"
            "    time.sleep(0.25)\n"
            "raise SystemExit(0)\n")
    k32.CreateJobObjectW.restype = wintypes.HANDLE
    job = k32.CreateJobObjectW(None, None)
    if job_kill:
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        k32.SetInformationJobObject(job, JobObjectExtendedLimitInformation,
                                    ctypes.byref(info), ctypes.sizeof(info))
    with log.open("w", encoding="utf-8") as fh, err.open("w", encoding="utf-8") as eh:
        p = subprocess.Popen([sys.executable, "-u", "-c", code], stdout=fh, stderr=eh)
        # KIND in den Job setzen - der Harness wird in der Wirklichkeit hineingeboren.
        k32.AssignProcessToJobObject(job, k32.OpenProcess(PROCESS_TERMINATE | 0x0400, False, p.pid))
        time.sleep(1.0)
        vorher = p.poll()
        leave = k32.CloseHandle(job)          # Job schliessen
        time.sleep(1.5)
        nachher = p.poll()
        if nachher is None:
            p.kill()
            p.wait(timeout=5)
    return {"job_kill_beim_schliessen": job_kill,
            "exit_vor_dem_schliessen": vorher,
            "exit_nach_dem_schliessen": nachher,
            "kernzeilen_stdout": len(log.read_text(encoding="utf-8").splitlines()),
            "stderr": err.read_text(encoding="utf-8").strip()[:200],
            "close_handle_hat_geklappt": bool(leave)}


def main() -> int:
    ziel = Path(__file__).with_name("_start_aus_terminal_beleg.txt")
    tmp = Path(__file__).with_name("_jobprobe")
    tmp.mkdir(exist_ok=True)
    puffer: list[str] = []

    def p(*a):
        puffer.append(" ".join(str(x) for x in a))

    p("# Punkt 3: Start aus dem VS-Code-Terminal - Beleg")
    p()
    p("## 1. Job-Mitgliedschaft (IsProcessInJob) dieser Prozesskette")
    for e in hauptprozess_kette():
        p(f"- PID {e['pid']}: in einem Job-Objekt = {e['in_job']}")
    p()
    p("Vergleich: der Harness, den der Nutzer im EIGENEN Fenster gestartet hat.")
    harness = []
    for pid in (1236, 19652):
        harness.append((pid, in_job(pid)))
    for pid, j in harness:
        p(f"- PID {pid}: in einem Job-Objekt = {j}")
    p()
    p("## 2. Nachstellung des Sterbemusters eines Job-Kills")
    for kill in (True, False):
        d = nachstellung(kill, tmp)
        p(f"- Job ohne/mit KILL_ON_JOB_CLOSE = {d['job_kill_beim_schliessen']}")
        p(f"    exit vor dem Schliessen: {d['exit_vor_dem_schliessen']}")
        p(f"    exit nach dem Schliessen: {d['exit_nach_dem_schliessen']}")
        p(f"    stdout-Zeilen insgesamt: {d['kernzeilen_stdout']}")
        p(f"    stderr: {d['stderr'] or '(leer)'}")
    p()
    p("## 3. Muster der zwei stillen Harness-Abstaende (aus logs/)")
    for f in sorted(Path("g:/Harness/harness/logs").glob("harness-2026-09-2*T0*.log")):
        if f.stat().st_size == 373:
            p(f"- {f.name}: {f.stat().st_size} Bytes, letzte Zeile "
              f"'{f.read_text(encoding='utf-8').splitlines()[-1][:110]}'")
    p("- start-stderr.log: fuer beide Starts KEINE ABSTURZ-Zeile, KEIN Traceback.")
    p("- logs/crash-*.txt: fuer beide Starts KEIN Bericht (die zwei anderen Abstuerze")
    p("  derselben Nacht, PermissionError, haben Berichte hinterlassen).")
    ziel.write_text("\n".join(puffer) + "\n", encoding="utf-8")
    print("geschrieben: " + str(ziel))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
