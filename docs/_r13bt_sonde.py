"""Read-only-Sonde: die Mischungs-Zeile der BILANZ mit den ECHTEN Daten nachrechnen.

Zeigt, welche Zahlen in `stand._mischung_zeile` eingehen (Fenster gegen Preflight-Reihe),
was heute herauskommt und was bei sauberer Trennung herauskaeme. Aendert nichts.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "harness"
sys.path.insert(0, str(ROOT))

from hx import stand                                              # noqa: E402
from hx.config import load_config                                 # noqa: E402

cfg = load_config()


def main() -> int:
    print(f"STANDARD_FENSTER={stand.STANDARD_FENSTER}  "
          f"TREND_FENSTER={stand.TREND_FENSTER}  "
          f"C_LAUF_MINDESTENS={stand.C_LAUF_MINDESTENS}")

    print("\n== Strang je Batch (strang_von_batch, Quelle):")
    for b in range(254, 266):
        s = stand.strang_von_batch(cfg, b)
        print(f"  B{b}: {s.get('strang') or '?':2s}  {str(s.get('quelle'))[:70]}")

    d = stand.durchsatz(cfg, stand.STANDARD_FENSTER)
    print("\n== durchsatz(cfg, STANDARD_FENSTER):")
    fen = [int(e["batch"]) for e in (d.get("fenster") or [])]
    cfen = [int(e["batch"]) for e in (d.get("c_fenster") or [])]
    print(f"  n                 = {d.get('n')}   fenster = {fen}")
    print(f"  c_fenster         = {cfen}  (len={len(cfen)})")
    print(f"  anteil_gemessen   = {d.get('anteil_gemessen')}")
    print(f"  anteil_gemessen_basis = {d.get('anteil_gemessen_basis')}")
    print(f"  anteil_c (Regel)  = {d.get('anteil_c')}")
    print(f"  anteil_quelle     = {str(d.get('anteil_quelle'))[:120]}")
    print(f"  c_lauf={d.get('c_lauf')} c_lauf_von={d.get('c_lauf_von')}")

    tr = stand.c_trend(cfg, stand.TREND_FENSTER)
    print("\n== c_trend(cfg, TREND_FENSTER) - die zweite Quelle:")
    print(f"  gemessen={tr.get('gemessen')} grund={tr.get('grund')}")
    reihe = [(t["batch"], t.get("strang") or "?") for t in (tr.get("reihe") or [])]
    print(f"  reihe ({len(reihe)}): {reihe}")
    bekannt = [a for _b, a in reihe if a in ("B", "C")]
    print(f"  bekannt (B/C)     = {len(bekannt)} von {len(reihe)}"
          f"  -> C-Anteil = {sum(1 for a in bekannt if a == 'C') / len(bekannt) if bekannt else None}")

    print("\n== was die BILANZ heute ausgibt:")
    for z in stand._mischung_zeile(cfg, d):
        print(f"  {z}")

    print("\n== sauber getrennt (Vorschlag):")
    if d.get("n"):
        c, n = len(cfen), int(d["n"])
        print(f"  Mischung     : {c} C von {n} Batches im Fenster "
              f"= {100 * c / n:.0f} %   (Fenster B{min(fen)}..B{max(fen)})")
    if bekannt:
        print(f"  Anteil C     : {sum(1 for a in bekannt if a == 'C')} von {len(bekannt)} "
              f"Batches mit belegtem Strang = "
              f"{100 * sum(1 for a in bekannt if a == 'C') / len(bekannt):.0f} %"
              f"   (Preflight-Reihe, {d.get('anteil_gemessen_basis')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
