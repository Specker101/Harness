#!/usr/bin/env python
"""Punkt 10b: alle fehlgeschlagenen/abgelehnten mcp__ghidra__-Aufrufe der Nacht.

Liest die Rohmitschnitte runs/b161..b174/stream.jsonl und listet je Aufruf:
Batch, Werkzeug, Art (gesperrt/fehler) und die Meldung. Zusaetzlich: welche
Ausweichwege (HTTP auf 127.0.0.1:8089, Skripte) im Mitschnitt vorkamen.

Aufruf aus g:\\Harness:  python docs\\_ghidra_worker_fehler.py
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

HARNESS = Path(r"g:\Harness\harness")
RUNS = HARNESS / "runs"
sys.path.insert(0, str(HARNESS))

from hx import streamjson                                        # noqa: E402

HTTP_RE = re.compile(r"127\.0\.0\.1:8089|localhost:8089|/mcp/schema", re.IGNORECASE)


def main() -> int:
    ziel = Path(__file__).with_name("_ghidra_worker_fehler.txt")
    fh = ziel.open("w", encoding="utf-8", newline="\n")

    def p(*a):
        print(*a, file=fh)

    gesamt: Counter = Counter()
    p("# Fehlgeschlagene/abgelehnte mcp__ghidra__-Aufrufe B161-B174")
    p()
    for n in range(161, 175):
        f = RUNS / f"b{n:03d}" / "stream.jsonl"
        if not f.is_file():
            continue
        st = streamjson.StreamStats()
        http_hits = 0
        for line in f.open("r", encoding="utf-8", errors="replace"):
            st.feed(line)
            if HTTP_RE.search(line):
                http_hits += 1
        fehler = [e for e in st.tool_errors if str(e.get("name") or "").startswith("mcp__ghidra__")]
        for e in fehler:
            gesamt[(e["name"], e.get("art"))] += 1
        if fehler or http_hits:
            p(f"## Batch {n}")
            for e in fehler:
                p(f"- {e['name']} [{e.get('art')}]: {str(e.get('text'))[:220]}")
            if http_hits:
                p(f"- Ausweichweg: {http_hits} Zeile(n) mit HTTP-Verweis auf 127.0.0.1:8089")
            p()
    p("## Summe je Werkzeug")
    for (name, art), k in sorted(gesamt.items(), key=lambda x: -x[1]):
        p(f"- {name} [{art}]: {k}")
    fh.close()
    print(f"geschrieben: {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
