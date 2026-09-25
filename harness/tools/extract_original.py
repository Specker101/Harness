"""Einmalwerkzeug: spiegelt den Originalauftrag wortgleich aus dem Chat-Transcript.

Begruendung (R17): der Auftragstext kam als Chat-Paste und lag nur im
Sitzungskontext. Abtippen waere eine Fehlerquelle - hier wird der laengste
String extrahiert, der die Ueberschrift von Abschnitt 20 enthaelt.

Aufruf:
  python tools/extract_original.py <transcript.jsonl> <ziel.md>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

NEEDLE = "Abschnitt 23"
MIN_LEN = 40000
HEADER = "# Originalauftrag (wortgleich gespiegelt)\n\n"


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    needle = sys.argv[3] if len(sys.argv) > 3 else NEEDLE
    min_len = int(sys.argv[4]) if len(sys.argv) > 4 else MIN_LEN
    best = ""
    hits = 0
    for line in src.read_text(encoding="utf-8", errors="replace").splitlines():
        if NEEDLE not in line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        hits += 1
        stack = [obj]
        while stack:
            node = stack.pop()
            if isinstance(node, str):
                if needle in node and len(node) > len(best) and len(node) >= min_len:
                    best = node
                    hits += 1
            elif isinstance(node, dict):
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
    if not best:
        print(f"Nichts gefunden (Anker {needle!r}, Mindestlaenge {min_len}).")
        return 1
    text = best.replace("\r\n", "\n")
    note = (HEADER
            + f"_Quelle: Chat-Paste im Sitzungs-Transcript ({src.name}), "
              f"Trefferzeilen: {hits}, Zeichen: {len(text)}._\n\n---\n\n")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(note + text.rstrip() + "\n", encoding="utf-8", newline="\n")
    print(f"geschrieben: {out} ({len(text)} Zeichen aus dem Paste, {hits} Trefferzeilen)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
