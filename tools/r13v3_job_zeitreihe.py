"""Zeitreihe: stirbt ein Prozess genau beim Schliessen des Job-Objekts?

Kleine, gezielte Messung zur R13v3-Sonde: der Herzschlag wird jede Sekunde
abgefragt (absolute Schreibzeit + Alter), damit "vor 0.4 s" nicht mehrdeutig ist.

Aufruf: python -u tools/r13v3_job_zeitreihe.py <direkt|startprocess> [sekunden]
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

HIER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HIER / "harness"))

from hx import aufraeumen                      # noqa: E402

HB = HIER / "tools" / "r13v_herzschlag.py"
PY = sys.executable
ARBEIT = HIER / "sandbox" / "sperrprobe"


def uhr(t: float) -> str:
    return time.strftime("%H:%M:%S", time.localtime(t)) + f".{int((t % 1) * 1000):03d}"


def main() -> int:
    art = sys.argv[1] if len(sys.argv) > 1 else "direkt"
    dauer = float(sys.argv[2]) if len(sys.argv) > 2 else 12.0
    datei = ARBEIT / f"hb_zeitreihe_{art}.txt"
    datei.unlink(missing_ok=True)
    ARBEIT.mkdir(parents=True, exist_ok=True)

    job = aufraeumen.Job(name=f"r13v3-zeitreihe-{art}")
    if not job.create():
        print(f"Job nicht eingerichtet: {job.grund}")
        return 1
    if art == "direkt":
        start = f"& '{PY}' '{HB}' '{datei}' 60"
    else:
        start = (f"Start-Process -FilePath '{PY}' -ArgumentList '{HB}','{datei}','60' "
                 "-WindowStyle Hidden")
    # WICHTIG: Die Zuweisung muss VOR dem Start des Kindes passieren (so macht es der
    # Harness in `proc.run_stream`: Popen, dann sofort `job.assign`). Deshalb wartet die
    # Shell erst 3 s, bevor sie den Hintergrundlauf startet - sonst entsteht das Kind
    # vor der Zuweisung und erbt den Job nicht (erster Messanlauf war genau deswegen
    # wertlos: das Kind lief weiter, obwohl die Shell im Job war).
    ps = subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                           f"Start-Sleep -Seconds 3; {start}; Start-Sleep -Seconds 60"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    zugewiesen = job.assign(ps.pid)           # sofort, wie im Harness
    print(f"Art: {art} | Worker-Shell PID {ps.pid} | Zuweisung: {zugewiesen}")
    time.sleep(9)                             # Shell startet das Kind bei t+3 s
    t0 = time.time()
    print(f"{uhr(t0)}  Job wird geschlossen (KILL_ON_JOB_CLOSE)")
    job.close()
    for i in range(int(dauer) + 1):
        jetzt = time.time()
        if datei.is_file():
            m = datei.stat().st_mtime
            print(f"{uhr(jetzt)}  t+{jetzt - t0:4.1f}s  letzte Schreibung {uhr(m)} "
                  f"({jetzt - m:4.1f}s alt)  Shell lebt: {ps.poll() is None}")
        else:
            print(f"{uhr(jetzt)}  t+{jetzt - t0:4.1f}s  keine Datei")
        if i < int(dauer):
            time.sleep(1.0)
    if ps.poll() is None:
        ps.kill()
    # Aufraeumen: den Herzschlag beenden, falls er ueberlebt hat
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                    f"Where-Object {{ $_.CommandLine -like '*{datei.name}*' }} | "
                    "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
                   capture_output=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
