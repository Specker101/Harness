"""Einmal-Diagnose: Was stand im Ergebnis des langen Bau-Aufrufs? (2026-09-26)

Fragt nicht "wie lange", sondern "was wurde da gebaut" - der Mitschnitt traegt die
vollstaendige make-Ausgabe. Damit laesst sich entscheiden, ob die 420 s ein echter
Neubau waren (Quellen geaendert) oder vermeidbar (Makefile/Objektzeiten).

    python docs\\_bauzeit_ursache.py runs\\b177\\stream.jsonl port_build
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

STREAM = Path(sys.argv[1] if len(sys.argv) > 1 else "runs/b177/stream.jsonl")
MUSTER = (sys.argv[2] if len(sys.argv) > 2 else "port_build").lower()


def main() -> int:
    offen: dict[str, tuple[str, str]] = {}
    for line in (STREAM.read_text(encoding="utf-8", errors="replace").splitlines()):
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(ev, dict):
            continue
        typ = ev.get("type")
        msg = ev.get("message") or {}
        if typ == "assistant":
            for b in (msg.get("content") or []):
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    cmd = ""
                    if isinstance(b.get("input"), dict):
                        cmd = str(b["input"].get("command") or "")
                    if MUSTER in cmd.lower():
                        offen[str(b.get("id"))] = (ev.get("timestamp") or "", cmd)
        elif typ == "user":
            for b in (msg.get("content") or []):
                if not (isinstance(b, dict) and b.get("type") == "tool_result"):
                    continue
                e = offen.pop(str(b.get("tool_use_id")), None)
                if not e:
                    continue
                body = b.get("content")
                text = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
                print("=" * 78)
                print(f"AUFRUF   {e[0]}")
                print("BEFEHL   " + " ".join(e[1].split())[:300])
                print("-" * 78)
                print(text[:2500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
