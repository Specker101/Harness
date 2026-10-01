"""R13bf (Aufgabe A): `streamjson.abbau_gefahr` gegen ALLE echten Mitschnitte pruefen.

Das Werkzeug `tools/check_abbau.py` sieht nur `runs/b1*` (bis Batch 178, Anlass R13i).
Seit dem Fehlalarm in B234 (Aussensicht M234-2) muessen auch die neueren Batches
mitgeprueft werden - und zwar **vorher und nachher** mit derselben Regel, damit "keine
neuen Fehlalarme" belegt und nicht behauptet ist.

Aufruf (aus `g:\\Harness\\harness`):

    python -u docs/_r13bf_abbau.py             # Liste + Kennzahlen, nur lesend
    python -u docs/_r13bf_abbau.py schreiben   # zusaetzlich JSON nach docs/
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "harness"
sys.path.insert(0, str(HARNESS))

from hx import streamjson                                          # noqa: E402

ZIEL = ROOT / "docs" / "_r13bf_abbau.json"
WORTE = ("stop-process", "taskkill")


def befehle() -> list[dict]:
    """Jeder Werkzeugaufruf mit einem Abbau-Wort aus JEDEM Mitschnitt."""
    out: list[dict] = []
    for d in sorted((HARNESS / "runs").glob("b*")):
        if not d.is_dir():
            continue
        for f in sorted(d.glob("stream*.jsonl")):
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for i, ln in enumerate(text.splitlines(), 1):
                niedrig = ln.lower()
                if not any(w in niedrig for w in WORTE):
                    continue
                try:
                    ev = json.loads(ln)
                except ValueError:
                    continue
                if not isinstance(ev, dict):
                    continue
                nachricht = ev.get("message")
                if not isinstance(nachricht, dict):
                    continue
                inhalt = nachricht.get("content")
                if not isinstance(inhalt, list):
                    continue
                for b in inhalt:
                    if not isinstance(b, dict) or b.get("type") != "tool_use":
                        continue
                    cmd = (b.get("input") or {}).get("command") or ""
                    if not cmd:
                        continue
                    out.append({"batch": d.name, "datei": f.name, "zeile": i,
                                "werkzeug": b.get("name") or "",
                                "befehl": " ".join(str(cmd).split())[:300],
                                "befund": streamjson.abbau_gefahr(cmd)})
    return out


def main() -> int:
    args = sys.argv[1:]
    alle = befehle()
    gemeldet = [e for e in alle if e["befund"]]
    print(f"Abbau-Wort in Werkzeugaufrufen: {len(alle)}")
    print(f"davon von abbau_gefahr gemeldet: {len(gemeldet)}")
    print()
    for e in gemeldet:
        print(f"  {e['batch']}/{e['datei']}:{e['zeile']}  {e['befund']}")
        print(f"      {e['befehl'][:150]}")
    nach_batch: dict[str, int] = {}
    for e in gemeldet:
        nach_batch[e["batch"]] = nach_batch.get(e["batch"], 0) + 1
    print()
    print("je Batch:", ", ".join(f"{k}={v}" for k, v in sorted(nach_batch.items())) or "-")
    if "schreiben" in args:
        daten = {"alle": len(alle), "gemeldet": len(gemeldet),
                 "je_batch": nach_batch,
                 "faelle": [{"batch": e["batch"], "datei": e["datei"],
                             "zeile": e["zeile"], "befehl": e["befehl"],
                             "befund": e["befund"]} for e in gemeldet]}
        ZIEL.write_text(json.dumps(daten, ensure_ascii=False, indent=1),
                        encoding="utf-8", newline="\n")
        print(f"\ngeschrieben: {ZIEL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
