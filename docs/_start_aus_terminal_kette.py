#!/usr/bin/env python
"""Namen zu den PIDs der Job-Kette (Ergaenzung zum Punkt-3-Beleg)."""

from __future__ import annotations

import subprocess
from pathlib import Path

PIDS = [9688, 2968, 20272, 640, 21336, 12744, 1236, 19652]
OUT = Path(__file__).with_name("_start_aus_terminal_beleg.txt")


def name(pid: int) -> str:
    out = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId={pid}' -ErrorAction SilentlyContinue; "
         "if ($p) { \"$($p.Name) | $($p.CommandLine)\" } else { '(weg)' }"],
        capture_output=True, text=True)
    return (out.stdout or "").strip()[:160]


def main() -> int:
    zeilen = ["", "## 4. Wer sind die Prozesse dieser Kette?",
              "   (Job-Mitglied True bis PID 640, danach False - dort endet der Job.)"]
    for pid in PIDS:
        zeilen.append(f"- PID {pid}: {name(pid)}")
    with OUT.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(zeilen) + "\n")
    print("\n".join(zeilen))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
