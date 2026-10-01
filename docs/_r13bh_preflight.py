"""R13bh (nur lesend): Preflight-Gruppen - Zeiten, Schreibziele, Startkommandos.

Auftragsvorbereitung (Nutzerauftrag 2026-10-01): welche Pruefgruppen des Preflights
(`scripts/preflight.py`, Registry `CHECK_MODULES`) sind voneinander unabhaengig, welche
koennen parallel laufen, was waere die erwartete Gesamtzeit?

Quellen:
  * `analysis/_m<N>/_preflight_zeiten.txt` (je Teilschritt Sekunden, B216),
  * die Modulquellen unter `scripts/` (Schreibziele ueber `evidence.target/guard/write`),
  * `scripts/preflight.py` (Registry-Reihenfolge, Aufruf der Module).

    python -u docs/_r13bh_preflight.py        -> docs/_r13bh_preflight.txt
"""
from __future__ import annotations

import pathlib
import re
import sys

HARNESS = pathlib.Path(__file__).resolve().parents[1]
DEC = pathlib.Path("g:/Silent Scope Decomp")
SCRIPTS = DEC / "scripts"
ANALYSIS = DEC / "analysis"

# Registry-Reihenfolge aus scripts/preflight.py (CHECK_MODULES)
MODULE = ["m104_built", "m115_pass", "m116_pass", "m114_pass", "m130_ast",
          "m5_kopf_check", "c_kopf_check", "m200_einbindung", "m210_bahnabdeckung",
          "m210_r391", "m227_profile_live", "m212_zeilen", "m214_archiv",
          "m233_binary", "port_regression"]
BATCHES = [230, 231, 232, 233, 234]
# Startkommandos, die eine Gruppe als Unterprozess fahren kann.
STARTER = ("hybrid_lauf", "port_selftest", "port_gl", "ppc_poc", "c_kopf", "m193",
           "port_build", "mingw32-make")


# Zeilen der Datei, die KEIN Teilschritt sind (sonst doppelt gezaehlt: die Summe
# enthaelt sie ebenfalls - im ersten Anlauf ergab das 4736 statt 1578 Sekunden).
KEIN_TEILSCHRITT = ("Summe Teilschritte", "Gesamtwanduhr", "Abweichung",
                    "Gegenprobe", "Teilschritt")


def zeiten(batch: int) -> dict[str, float]:
    """{Teilschritt: Sekunden} aus `analysis/_m<N>/_preflight_zeiten.txt`."""
    p = ANALYSIS / f"_m{batch}" / "_preflight_zeiten.txt"
    out: dict[str, float] = {}
    if not p.is_file():
        return out
    for zeile in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if "|" not in zeile or zeile.startswith("#"):
            continue
        links, _, rechts = zeile.partition("|")
        if links.strip().startswith(KEIN_TEILSCHRITT):
            continue
        try:
            out[links.strip()] = float(rechts.strip().split()[0])
        except (IndexError, ValueError):
            continue
    return out


def gruppe(teilschritt: str) -> str:
    return teilschritt.split("/")[0].strip()


def quelle(modul: str) -> tuple[list[str], list[str], list[str]]:
    """(schreibt, startet, liest) aus dem Modulquelltext."""
    p = SCRIPTS / f"{modul}.py"
    if not p.is_file():
        return [], [], []
    text = p.read_text(encoding="utf-8", errors="replace")
    schreibt = sorted(set(re.findall(r'(?:EV\.(?:target|guard|write)\(|_out\()\s*["\']'
                                     r'([^"\']+)["\']', text)))
    schreibt += sorted(set(re.findall(r'EV\.write\(\s*["\']([^"\']+)["\']', text)))
    startet = sorted({s for s in STARTER if s in text})
    liest = sorted(set(re.findall(r'(?:EV\.target|read_text\(|open\()\(\s*["\']'
                                  r'(analysis/[^"\']+|_[a-z0-9_]+\.txt)["\']', text)))
    liest += sorted(set(re.findall(r'["\'](analysis/[A-Za-z0-9_./<>-]+)["\']', text)))
    return schreibt, startet, sorted(set(liest))


def main() -> int:
    z: list[str] = []
    z.append("R13bh - Preflight-Gruppen: Zeiten, Schreibziele, Starter")
    z.append("Registry: scripts/preflight.py CHECK_MODULES (seriell in dieser Reihenfolge)")
    z.append("")
    z.append("Sekunden je Gruppe (aus analysis/_m<N>/_preflight_zeiten.txt):")
    pro_batch = {b: zeiten(b) for b in BATCHES}
    kopf = f"{'Gruppe':<20}" + "".join(f"{b:>9}" for b in BATCHES) + f"{'Mittel':>9}"
    z.append(kopf)
    z.append("-" * len(kopf))
    for mod in MODULE:
        werte = []
        for b in BATCHES:
            s = sum(v for k, v in pro_batch[b].items() if gruppe(k) == mod)
            werte.append(s)
        mittel = sum(werte) / len(werte) if werte else 0.0
        z.append(f"{mod:<20}" + "".join(f"{w:>9.1f}" for w in werte)
                 + f"{mittel:>9.1f}")
    gesamt = [sum(pro_batch[b].values()) for b in BATCHES]
    z.append(f"{'SUMME':<20}" + "".join(f"{w:>9.1f}" for w in gesamt)
             + f"{sum(gesamt) / len(gesamt):>9.1f}")
    teilschritte = sorted({k for b in BATCHES for k in pro_batch[b]})
    z.append("")
    z.append("Teilschritte (alle Gruppen, Mittel ueber die Batches):")
    for k in teilschritte:
        ws = [pro_batch[b].get(k) for b in BATCHES]
        g = [w for w in ws if w is not None]
        z.append(f"  {k:<50} {sum(g) / len(g):>9.1f} s   (n={len(g)})")
    z.append("")
    z.append("Schreibziele und Starter je Modul (aus dem Quelltext):")
    for mod in MODULE:
        schreibt, startet, liest = quelle(mod)
        z.append(f"  {mod}:")
        z.append(f"    schreibt: {', '.join(schreibt) or '(kein EV.target gefunden)'}")
        z.append(f"    startet : {', '.join(startet) or '-'}")
        if liest:
            z.append(f"    liest   : {', '.join(liest[:6])}")
    text = "\n".join(z) + "\n"
    ziel = HARNESS / "docs" / "_r13bh_preflight.txt"
    ziel.write_text(text, encoding="utf-8", newline="\n")
    print(text)
    print(f"Beleg: {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
