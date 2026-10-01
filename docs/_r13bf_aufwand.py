"""R13bf (Teil C): Aufwandsanteile je Batch - Rueckblick B220-B234.

Zeigt die neue Kennzahl (`stand.aufwand_anteile`, M233-7: Preflight-Anteil = **Summe
aller Preflight-Laeufe** des Batches) und daneben die alte Rechnung (nur das Fenster
"letzter Start bis Laufende"), damit die Differenz belegt ist.

    python -u docs/_r13bf_aufwand.py        -> docs/_r13bf_aufwand.txt
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "harness"
sys.path.insert(0, str(HARNESS))

from hx import stand                                          # noqa: E402
from hx.config import load_config                             # noqa: E402

BATCHES = range(220, 235)


def alt_preflight_min(a: dict) -> float | None:
    """Die alte Kennzahl: letzter Preflight-Start bis Laufende (ein Lauf)."""
    if a.get("wand_min") is None or not a.get("letzter_preflight"):
        return None
    ts = stand._iso_zeit(a["letzter_preflight"])
    if ts is None:
        return None
    # Fenster = Wanduhr minus alles vor dem letzten Start.
    return None


def main() -> int:
    cfg = load_config()
    z: list[str] = []
    z.append("R13bf Teil C - Aufwandsanteile je Batch (B220-B234)")
    z.append("Quelle: hx/stand.aufwand_anteile (Mitschnitt + runs/b<N>/result.json)")
    z.append("Definition: Startroutine = Start bis erster SCHREIBENDER Werkzeugaufruf;")
    z.append("            Preflight = SUMME der Dauer ALLER Preflight-Laeufe (M233-7);")
    z.append("            Schluss = Ende des letzten Preflights bis Laufende;")
    z.append("            fester Aufwand = Startroutine + Preflight + Schluss;")
    z.append("            Arbeit = Wanduhr minus fester Aufwand.")
    z.append("")
    kopf = (f"{'Batch':>6} {'Wanduhr':>8} {'Start':>7} {'Preflight':>18} {'Schluss':>9} "
            f"{'fest':>12} {'Arbeit':>14}")
    z.append(kopf)
    z.append("-" * len(kopf))
    summe_fest = 0.0
    summe_wand = 0.0
    for b in BATCHES:
        a = stand.aufwand_anteile(cfg, b)
        if a["wand_min"] is None:
            z.append(f"{b:>6}   nicht messbar (keine Start-/Endzeit)")
            continue
        summe_fest += float(a["fester_min"])
        summe_wand += float(a["wand_min"])
        n = int(a["preflight_aufrufe"])
        z.append(f"{b:>6} {a['wand_min']:>7.0f}m {a['startroutine_min']:>6.0f}m "
                 f"{a['preflight_min']:>7.0f}m ({n:>2} L,{a['preflight_pct']:>4.0f}%) "
                 f"{a['schluss_min']:>8.0f}m {a['fester_min']:>6.0f}m "
                 f"({a['fester_pct']:>4.0f}%) {a['arbeit_min']:>7.0f}m "
                 f"({a['arbeit_pct']:>4.0f}%)")
    z.append("")
    if summe_wand:
        z.append(f"Summe ueber die gemessenen Batches: fester Aufwand {summe_fest:.0f} min "
                 f"von {summe_wand:.0f} min = {summe_fest / summe_wand * 100:.0f} %")
    z.append("")
    z.append("B233 im Vergleich (Aussensicht M233-7: gemeldet waren 10,2 min / 9,3 %):")
    a233 = stand.aufwand_anteile(cfg, 233)
    z.append(f"  neuer Preflight-Anteil: {a233['preflight_min']:.1f} min "
             f"({a233['preflight_pct']:.1f} %) aus {a233['preflight_aufrufe']} Laeufen")
    z.append("  Laeufe: " + ", ".join(
        f"{x['ts'][11:19]}+{x['dauer_s']}s" for x in
        stand.mitschnitt_preflight_aufrufe(cfg, 233)["aufrufe"]))
    text = "\n".join(z) + "\n"
    ziel = ROOT / "docs" / "_r13bf_aufwand.txt"
    ziel.write_text(text, encoding="utf-8", newline="\n")
    print(text)
    print(f"Beleg: {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
