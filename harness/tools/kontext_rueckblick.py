"""Rueckblick: Kontextgroesse je Batch (R13ad, Auftrag 2026-09-29).

Liest die ECHTEN Mitschnitte `runs/b<N>/stream.jsonl` (roh, ohne API-Kosten) und zeigt je
Batch Dauer, Anfragen, `kontext_max` und `kontext_letzte_anfrage`. Die Kontextzahlen kommen
aus `streamjson.StreamStats.kontext_stats()` - derselben Funktion, die `result.json` fuellt.

    python tools/kontext_rueckblick.py [von] [bis]

Ohne Argumente: B205 bis zum hoechsten vorhandenen Batch. Es wird NICHTS geschrieben.
Dauer und Anfragen kommen aus `runs/b<N>/result.json`, wenn es da ist - sonst aus dem
Mitschnitt (Anfragen) bzw. "-" (Dauer).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import streamjson                                            # noqa: E402


def _batches(root: Path, von: int | None, bis: int | None) -> list[int]:
    nummern = sorted(int(m.group(1)) for p in (root / "runs").glob("b*")
                     if (m := re.fullmatch(r"b(\d+)", p.name)))
    if not nummern:
        return []
    lo = int(von) if von else 205
    hi = int(bis) if bis else nummern[-1]
    return [b for b in nummern if lo <= b <= hi]


def _zeile(root: Path, batch: int) -> dict:
    rd = root / "runs" / f"b{batch:03d}"
    stats = streamjson.StreamStats()
    p = rd / "stream.jsonl"
    if p.is_file():
        with open(p, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                stats.feed(line)
    res = {}
    try:
        res = json.loads((rd / "result.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        res = {}
    kontext = stats.kontext_stats()
    dauer = res.get("duration_s")
    return {"batch": batch, "dauer_s": dauer,
            "anfragen": len(stats.requests) or res.get("stats", {}).get("requests"),
            "kontext_max": kontext["kontext_max"],
            "kontext_letzte": kontext["kontext_letzte_anfrage"],
            "kompaktierungen": kontext["kompaktierungen"]}


def _minuten(sekunden) -> str:
    try:
        return f"{float(sekunden) / 60.0:.1f} min"
    except (TypeError, ValueError):
        return "-"


def main(argv: list[str]) -> int:
    root = ROOT
    von = int(argv[0]) if len(argv) > 0 else None
    bis = int(argv[1]) if len(argv) > 1 else None
    zeilen = [_zeile(root, b) for b in _batches(root, von, bis)]
    if not zeilen:
        print("(keine Mitschnitte gefunden)")
        return 1
    print("| Batch | Dauer | Anfragen | kontext_max | kontext_letzte_anfrage | "
          "Kompaktierungen |")
    print("|---|---|---|---|---|---|")
    for z in zeilen:
        print(f"| B{z['batch']} | {_minuten(z['dauer_s'])} | {z['anfragen']} "
              f"| {z['kontext_max']} | {z['kontext_letzte']} "
              f"| {z['kompaktierungen'] or 'keine'} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
