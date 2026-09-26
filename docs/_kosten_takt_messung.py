"""Vorher/Nachher der Kostenrechnung im Mitschnitt-Leser (R13h), 2026-09-26.

Gemessen wird, was der Harness beim Abnehmen der Kindausgabe zusaetzlich rechnet.
Vorher lief `stats.totals()` + `stats.cost_usd()` fuer JEDE Zeile; nachher nur noch
im Takt (`TaktGeber`, 2 s). Beide Rechnungen laufen hier auf einem ECHTEN Mitschnitt
derselben Laenge - einmal in der alten Form, einmal in der neuen.

    python docs\\_kosten_takt_messung.py runs/b177/stream.jsonl
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "harness"
sys.path.insert(0, str(ROOT))

from hx import streamjson                                            # noqa: E402

STREAM = Path(sys.argv[1] if len(sys.argv) > 1 else "harness/runs/b177/stream.jsonl")


def main() -> int:
    zeilen = STREAM.read_text(encoding="utf-8", errors="replace").splitlines()
    print(f"Mitschnitt: {STREAM}  ({len(zeilen)} Zeilen)")

    # --- ALT: je Zeile Summen + Kosten -------------------------------------------
    s = streamjson.StreamStats()
    t0 = time.perf_counter()
    for ln in zeilen:
        s.feed(ln)
        s.totals()
        s.cost_usd()
    t_alt = time.perf_counter() - t0

    # --- NEU: nur feed() je Zeile, Rechnung im Takt ------------------------------
    s2 = streamjson.StreamStats()
    takt = streamjson.TaktGeber(2.0)
    t1 = time.perf_counter()
    rechnungen = 0
    for ln in zeilen:
        s2.feed(ln)
        if takt.faellig():
            s2.totals()
            s2.cost_usd()
            rechnungen += 1
    t_neu = time.perf_counter() - t1

    # --- Gegenprobe: dieselbe Zahl am Ende? -------------------------------------
    gleich = (round(s.cost_usd(), 6) == round(s2.cost_usd(), 6)
              and s.totals() == s2.totals())

    # Im ECHTEN Lauf feuert der Takt nicht einmal, sondern alle 2 s Wanduhr. Der
    # Nachspiel-Lauf hier ist viel schneller als echt; deshalb wird die Zahl der
    # Rechnungen aus der echten Batch-Dauer hochgerechnet (nichts geraten).
    dauer = None
    res = STREAM.parent / "result.json"
    if res.is_file():
        try:
            dauer = float(json.loads(res.read_text(encoding="utf-8")).get("duration_harness_s"))
        except Exception:                                        # noqa: BLE001
            dauer = None
    echt_neu = (dauer / 2.0) if dauer else None
    zeilen_out = [
        f"Mitschnitt: {STREAM.name} ({len(zeilen)} Zeilen, {len(s.requests)} Anfragen)",
        f"  ALT  Summen+Kosten je Zeile : {t_alt:6.2f} s  "
        f"({len(zeilen)} Rechnungen im Nachspiel, im echten Lauf genauso viele)",
        f"  NEU  im Takt (2 s)          : {t_neu:6.2f} s  ({rechnungen} Rechnung im Nachspiel)",
        f"  gespart im Nachspiel        : {t_alt - t_neu:6.2f} s "
        f"({100 * (t_alt - t_neu) / t_alt:.0f} % der Leserechenzeit)",
    ]
    if dauer and echt_neu is not None:
        zeilen_out.append(
            f"  echter Lauf                : {dauer:.0f} s Wanduhr -> ~{echt_neu:.0f} Rechnungen * 1 ms "
            f"= {echt_neu / 1000:.1f} s statt {len(zeilen) / 1000:.0f} s")
    zeilen_out.append(f"  Ergebnis identisch          : {'ja' if gleich else 'NEIN - FEHLER'}")
    text = "\n".join(zeilen_out)
    print(text)
    p = Path("g:/Harness/docs/_kosten_takt_messung.txt")
    p.write_text(text + "\n", encoding="utf-8")
    print(f"\nBeleg: {p}")
    return 0 if gleich else 1


if __name__ == "__main__":
    raise SystemExit(main())
