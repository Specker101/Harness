"""R13bm - Gegenprobe am echten B235-Mitschnitt (nur lesend).

Prueft, dass die neue Erkennung in `hx/streamjson.py` den API-/Gateway-Fehler der
B235-Fortsetzung findet und dabei GENAU die Zeile nennt, die der Nutzer genannt hat
(`runs/b235/stream.jsonl:28441`). Schreibt seinen Beleg selbst als UTF-8/LF.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(r"g:/Harness/harness")
sys.path.insert(0, str(ROOT))

from hx import streamjson                                       # noqa: E402

QUELLE = ROOT / "runs" / "b235" / "stream.jsonl"
BELEG = ROOT.parent / "docs" / "_r13bm_pruefung_b235.txt"
ERWARTET = 28441


def main() -> int:
    z: list[str] = []
    z.append("R13bm P1 - Gegenprobe am echten Mitschnitt (nur lesend)")
    z.append(f"Quelle: {QUELLE}")
    if not QUELLE.is_file():
        z.append("  FEHLT")
        return 1
    stats = streamjson.StreamStats()
    n = 0
    with io.open(QUELLE, encoding="utf-8", errors="replace") as f:
        for zeile in f:
            stats.feed(zeile)
            n += 1
    z.append(f"  gelesene Zeilen: {n}")
    z.append(f"  erkannte API-Fehler: {len(stats.api_errors)}")
    for e in stats.api_errors:
        z.append(f"    Zeile {e['zeile']}  {e['ts']}  {len(e['text'])} Zeichen  "
                 f"{e['text'][:80]}")
    z.append(f"  letzter Text ist ein API-Fehler: {stats.letzter_text_api_fehler}")
    z.append(f"  result-Ereignis is_error: {stats.is_error()}")
    z.append("")
    treffer = [e for e in stats.api_errors if int(e["zeile"]) == ERWARTET]
    ok = bool(treffer) and stats.letzter_text_api_fehler
    z.append(f"ERWARTET: Fehler in Zeile {ERWARTET} -> "
             f"{'GEFUNDEN' if treffer else 'NICHT GEFUNDEN'}")
    z.append(f"ERGEBNIS: {'OK' if ok else 'FEHLGESCHLAGEN'}")
    text = "\n".join(z) + "\n"
    BELEG.write_text(text, encoding="utf-8", newline="\n")
    print(text)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
