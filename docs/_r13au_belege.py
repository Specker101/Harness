"""R13au: Rechnerlast - Maschine, Ghidra/Java, Worker (MESSUNG, nur lesend).

Der Auftrag verlangt (Teil C, Punkt 4) den Bericht "Kerne und RAM des Rechners; typischer
RAM-Bedarf von Ghidra/Java und des Workers". Gemessen wird hier live (der Ghidra-Server
des Projekts und der laufende Worker sind echte Prozesse), dazu die Heap-Grenze aus dem
Startskript.

Aufruf: python -u docs/_r13au_belege.py            (gibt aus)
        python -u docs/_r13au_belege.py schreiben  (schreibt docs/_r13au_belege.txt)
"""

from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
HARNESS = HIER.parent / "harness"
sys.path.insert(0, str(HARNESS))

from hx import last                                            # noqa: E402
from hx.config import load_config                               # noqa: E402

ZIEL = HIER / "_r13au_belege.txt"
DECOMP = Path("g:/Silent Scope Decomp")
GHIDRA_START = DECOMP / "scripts" / "start-ghidra-headless.ps1"


def mb(wert) -> str:
    return f"{float(wert) / (1024.0 * 1024.0):.0f} MB"


def prozesse() -> None:
    ps = last._psutil()
    if ps is None:
        print("  psutil fehlt - Prozessaufstellung nicht moeglich")
        return
    rec = last.Recorder()
    eigene = rec.eigene_pids()
    print(f"  eigene PIDs (Harness-Baum): {len(eigene)} -> {sorted(eigene)[:12]}")
    zeilen = []
    for p in ps.process_iter(["pid", "name", "cmdline", "memory_info"]):
        try:
            name = str(p.info.get("name") or "")
            stamm = name[:-4].lower() if name.lower().endswith(".exe") else name.lower()
            if stamm not in ("java", "javaw", "python", "pythonw", "node", "claude"):
                continue
            rss = getattr(p.info.get("memory_info"), "rss", 0)
            befehl = " ".join(p.info.get("cmdline") or [])
            marke = "EIGEN" if p.info["pid"] in eigene else "fremd"
            if stamm.startswith("java") and any(m in befehl.lower()
                                                for m in last.GHIDRA_MERKMALE):
                marke = "GHIDRA"
            zeilen.append((rss, f"  {marke:<6} {stamm:<8} pid={p.info['pid']:<7} "
                                f"RSS={mb(rss):>9}  {befehl[:90]}"))
        except Exception:                                          # noqa: BLE001
            continue
    for _rss, zeile in sorted(zeilen, reverse=True):
        print(zeile)


def summen() -> None:
    """Summen je Gruppe und die groessten Prozesse - fuer den Bericht."""
    ps = last._psutil()
    if ps is None:
        return
    gruppen: dict[str, list[float]] = {"java": [], "node/claude": [], "python": [],
                                       "andere": []}
    top: list[tuple[float, str]] = []
    for p in ps.process_iter(["pid", "name", "memory_info"]):
        try:
            name = str(p.info.get("name") or "?")
            stamm = name[:-4].lower() if name.lower().endswith(".exe") else name.lower()
            rss = getattr(p.info.get("memory_info"), "rss", 0) / (1024.0 * 1024.0)
            if stamm.startswith("java"):
                gruppen["java"].append(rss)
            elif stamm in ("node", "claude"):
                gruppen["node/claude"].append(rss)
            elif stamm in ("python", "pythonw"):
                gruppen["python"].append(rss)
            else:
                gruppen["andere"].append(rss)
            top.append((rss, f"{name} (pid {p.info['pid']})"))
        except Exception:                                          # noqa: BLE001
            continue
    print("  Summe RSS je Gruppe:")
    for k, werte in gruppen.items():
        print(f"    {k:<12} {len(werte):>3} Prozess(e), zusammen {sum(werte):>7.0f} MB")
    vm = ps.virtual_memory()
    print(f"    RAM gesamt {vm.total / 1048576.0:.0f} MB, belegt {vm.percent:.0f} %, "
          f"frei {vm.available / 1048576.0:.0f} MB")
    print("  groesste acht Prozesse:")
    for rss, text in sorted(top, reverse=True)[:8]:
        print(f"    {rss:>7.0f} MB  {text}")


def bericht() -> None:
    cfg = load_config()
    m = last.maschine()
    print("R13au: Rechnerlast - Maschine, Ghidra/Java, Worker (Messung 2026-09-30)")
    print()
    print("1) Rechner")
    print(f"  Kerne: {m.get('kerne')} physisch / {m.get('threads')} Threads "
          f"(Quelle: {m.get('quelle')})")
    print(f"  RAM gesamt: {m.get('ram_gesamt_mb')} MB")
    print(f"  Ghidra-Heap laut Startskript: "
          + (", ".join(z.strip() for z in GHIDRA_START.read_text(encoding='utf-8',
                                                                 errors='replace')
                       .splitlines() if "-Xmx" in z)
             if GHIDRA_START.is_file() else "(Skript nicht gefunden)"))
    print()
    print("2) Laufende Prozesse (RSS, gruppiert wie im Waechter)")
    prozesse()
    print()
    print("2b) Summen und die groessten Prozesse")
    summen()
    print()
    print("3) Eine Aufnahme des Recorders (das ist die Zeile je Minute)")
    r = last.Recorder(log=None)
    if r.quelle == "keine":
        print(f"  nicht messbar: {r.fehler}")
    else:
        p = r.probe()
        print(f"  Quelle {r.quelle}: CPU {p['cpu']:.1f} %, RAM frei "
              f"{p['ram_frei_mb']:.0f} MB, eigene {p['eigene']}, "
              f"Ghidra {p['ghidra']}, fremd {p['fremd']} "
              f"({', '.join(p['fremde_namen']) or 'keine'})")
    print()
    print("4) Wie die Zahlen im Bericht aussehen (Beispielwerte des laufenden Batches)")
    probe = {"cpu_mittel": 31.2, "cpu_max": 68.0, "ram_frei_min": 4210.0,
             "fremdlast_minuten": 3, "last_proben": 47, "last_quelle": "psutil",
             "last_fremde_namen": ["python.exe"], "last_ghidra_max": 1}
    print("  " + last.fakten_zeile(probe))
    print()
    print("5) Was der Harness daraus in result.json schreibt")
    print("  " + ", ".join(sorted(last.in_result(
        {"cpu_mittel": 1.0, "cpu_max": 2.0, "ram_frei_min": 3.0, "fremdlast_minuten": 4,
         "proben": 5, "intervall_s": 60.0, "ghidra_prozesse_max": 1,
         "eigene_prozesse_max": 2, "fremde_namen": [], "quelle": "psutil",
         "fehler": ""}).keys())))
    print(f"  (der Wächter misst alle {last.INTERVALL_S:.0f} s; Einstellung im Modul)")


def main() -> int:
    if "schreiben" in sys.argv:
        puffer = io.StringIO()
        with contextlib.redirect_stdout(puffer):
            bericht()
        text = puffer.getvalue()
        ZIEL.write_text(text, encoding="utf-8", newline="\n")
        print(f"geschrieben: {ZIEL.name} ({len(text)} Zeichen, UTF-8)")
        return 0
    bericht()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
