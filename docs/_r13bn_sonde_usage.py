"""Kurzsonde: wie sehen die `usage`-Felder in den Mitschnitten aus? (R13bn Punkt 2)"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1] / "harness"

for name in ("runs/b243/reviewer.jsonl", "runs/meta-243.jsonl"):
    p = HARNESS / name
    arten = Counter()
    beispiele: list[str] = []
    with open(p, "r", encoding="utf-8", errors="replace") as fh:
        for zeile in fh:
            if "usage" not in zeile:
                continue
            try:
                d = json.loads(zeile)
            except ValueError:
                continue
            arten[d.get("type")] += 1
            m = d.get("message") if isinstance(d.get("message"), dict) else {}
            u = m.get("usage") or d.get("usage")
            if u and len(beispiele) < 3:
                beispiele.append(f"{d.get('type')}: {json.dumps(u, ensure_ascii=False)[:180]}")
    print("==", name, dict(arten))
    for b in beispiele:
        print("   ", b)
