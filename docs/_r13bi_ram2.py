"""R13bi (nur lesend): der ECHTE FRONT-Lauf neben `c_kopf.exe` - RAM und Dauer.

`m212_zeilen._lauf(200000000)` (scripts/m212_zeilen.py:250-268) ist der teure Teil
der Gruppe: `hybrid_lauf.exe --schritte 200000000 --nativ-weiter`. Gemessen wird
seine **RSS-Spitze** und seine **Dauer**, waehrend gleichzeitig `c_kopf.exe`
(genau der Aufruf aus `c_kopf._port_lauf`, c_kopf.py:2412) Kopf fuer Kopf ueber
die vorhandenen `analysis/_m197/_ck_*.case` laeuft.

Nichts wird geschrieben: `hybrid_lauf.exe` schreibt nur mit `--s-log` (hybrid_lauf.cpp:605),
`c_kopf.exe` gibt auf stdout aus. Ausgabe nach docs/_r13bi_ram2.txt.
"""
from __future__ import annotations

import glob
import os
import pathlib
import subprocess
import time

DEC = pathlib.Path("g:/Silent Scope Decomp")
HARNESS = pathlib.Path(__file__).resolve().parents[1]
ROM = DEC / "rom" / "build" / "830d01.27p.be.bin"
C_KOPF = DEC / "port" / "build" / "c_kopf.exe"
HYBRID = DEC / "port" / "build" / "hybrid_lauf.exe"
FRONT = [str(HYBRID), "--schritte", "200000000", "--nativ-weiter"]
CASES = sorted(glob.glob(str(DEC / "analysis" / "_m197" / "_ck_*.case")))
GRENZE = 900.0


def frei_mb() -> float:
    import psutil
    return psutil.virtual_memory().available / 1048576.0


def rss_mb(pid: int) -> float:
    import psutil
    try:
        return psutil.Process(pid).memory_info().rss / 1048576.0
    except Exception:                                              # noqa: BLE001
        return 0.0


def main() -> int:
    import psutil                                                 # noqa: F401
    z: list[str] = []
    z.append("R13bi - FRONT-Lauf (`--schritte 200000000 --nativ-weiter`) neben c_kopf.exe")
    z.append(f"FRONT  : {' '.join(FRONT[1:])}")
    z.append(f"Kopf   : {C_KOPF.name} {ROM.name} <_ck_*.case>  ({len(CASES)} Profile da)")
    z.append("")
    frei0 = frei_mb()
    z.append(f"freier Speicher vorher: {frei0:.0f} MB")

    t0 = time.time()
    p = subprocess.Popen(FRONT, cwd=str(DEC), stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                         errors="replace")
    front_spitze = 0.0
    kopf_spitze = 0.0
    kopf_max_gleich = 0
    frei_min = frei0
    laufend: list[subprocess.Popen] = []
    i = 0
    letzter_start = 0.0
    while p.poll() is None and time.time() - t0 < GRENZE:
        front_spitze = max(front_spitze, rss_mb(p.pid))
        laufend = [q for q in laufend if q.poll() is None]
        for q in laufend:
            kopf_spitze = max(kopf_spitze, rss_mb(q.pid))
        kopf_max_gleich = max(kopf_max_gleich, len(laufend))
        if not laufend and i < len(CASES) and time.time() - letzter_start > 1.0:
            laufend.append(subprocess.Popen(
                [str(C_KOPF), str(ROM), CASES[i]], cwd=str(DEC),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
            letzter_start = time.time()
            i += 1
        frei_min = min(frei_min, frei_mb())
        time.sleep(0.25)
    aus = p.stdout.read() if p.stdout else ""
    front_dauer = time.time() - t0
    for q in laufend:
        if q.poll() is None:
            q.kill()
    z.append(f"FRONT  : Dauer {front_dauer:.1f} s   RSS-Spitze {front_spitze:.1f} MB   "
             f"rc={p.returncode}")
    z.append(f"c_kopf : {i} Koepfe gestartet (hoechstens {kopf_max_gleich} gleichzeitig), "
             f"RSS-Spitze {kopf_spitze:.1f} MB")
    z.append(f"Zusammen: RSS-Spitze {front_spitze + kopf_spitze:.1f} MB   "
             f"freier Speicher {frei0:.0f} -> {frei_min:.0f} MB "
             f"(Abnahme {frei0 - frei_min:.0f} MB)")
    z.append("")
    z.append("--- ERGEBNIS-Zeilen des FRONT-Laufs ---")
    for linie in aus.splitlines():
        if linie.startswith(("Schritte", "Halt-", "Hauptschleife", "Wegmass",
                             "Anteil nativ", "Hybrid-Anteil", "Hybrid-Kopf",
                             "Hybrid-Funktionen", "Kopf-Weiterlauf", "Zugriffe",
                             "SPU", "Attrappe-4-Lesen", "ausgefuehrte PCs",
                             "Boot-Coverage", "Eintritte", "#")):
            z.append("  " + linie.strip())
    text = "\n".join(z) + "\n"
    (HARNESS / "docs" / "_r13bi_ram2.txt").write_text(text, encoding="utf-8", newline="\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
