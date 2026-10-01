"""R13bf: Umfeld aus B234 lesen (Mitschnitt-Zeilen, Befunde der Aussensicht).

Aufruf:
    python -u docs/_r13bf_probe.py b234 [<suchwort> ...]   # Zeilen mit dem Suchwort
    python -u docs/_r13bf_probe.py zeilen 39715            # genau diese Zeilennummern
    python -u docs/_r13bf_probe.py meta                    # meta-233/234.md
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent / "harness"


def _bloecke(d: dict):
    for b in (d.get("message") or {}).get("content") or []:
        if isinstance(b, dict):
            yield b


def zeige(nummer: int, b: dict) -> None:
    if b.get("type") == "tool_use":
        print(f"--- Zeile {nummer} | {b.get('name')}")
        print(json.dumps(b.get("input"), ensure_ascii=False)[:3000])
    elif b.get("type") == "text":
        print(f"--- Zeile {nummer} TEXT: {str(b.get('text'))[:400]}")
    elif b.get("type") == "tool_result":
        c = b.get("content")
        print(f"--- Zeile {nummer} RESULT: {str(c)[:300]}")


def zeilen(pfad: pathlib.Path, nummern=None, suchworte=()) -> None:
    if not pfad.is_file():
        print(f"FEHLT: {pfad}")
        return
    treffer = 0
    with pfad.open(encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f, 1):
            if nummern is not None and i not in nummern:
                continue
            if suchworte and not any(s.lower() in line.lower() for s in suchworte):
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if not isinstance(d, dict):
                continue
            gedruckt = False
            for b in _bloecke(d):
                zeige(i, b)
                gedruckt = True
            if gedruckt:
                treffer += 1
            if nummern is None and treffer >= 12:
                break
    print(f"[{pfad.name}: {treffer} Treffer]")


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] == "b234":
        for name in ("stream.jsonl", "stream-v1.jsonl", "stream-forts1.jsonl"):
            p = ROOT / "runs" / "b234" / name
            print(f"##### {name} #####")
            zeilen(p, None, args[1:] or ["@(704", "foreach ($id"])
    elif args[0] == "zeilen":
        for name in ("stream.jsonl", "stream-v1.jsonl"):
            p = ROOT / "runs" / "b234" / name
            print(f"##### {name} #####")
            zeilen(p, {int(x) for x in args[1:]})
    elif args[0] == "meta":
        for n in (233, 234):
            p = ROOT / "runs" / f"meta-{n}.md"
            if p.is_file():
                t = p.read_text(encoding="utf-8", errors="replace")
                print(f"===== meta-{n}.md ({len(t)} Zeichen) =====")
                print(t[:7000])
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
