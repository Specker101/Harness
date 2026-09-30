"""Nebenpruefung R13bc: Kodierungen und C-Koepfe-Zeilen der eingefrorenen Preflight-Dateien.

Nur lesend, schreibt `docs/_r13bc_kodierung.txt`. Hilft zu sehen, dass die Fixture die
Eigenheiten der Originale behalten hat (UTF-16-Dateien, BOM, CRLF).
"""

from __future__ import annotations

import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER.parent / "harness"))

from hx.util import erkenne_kodierung, read_bytes_shared, read_text_erkannt   # noqa: E402

FIX = HIER.parent / "harness" / "tests" / "fixtures" / "stand_b224" / "decomp" / "analysis"
ZIEL = HIER / "_r13bc_kodierung.txt"


def main() -> int:
    zeilen = []
    for p in sorted(FIX.glob("_preflight_*.txt")):
        b = read_bytes_shared(p)
        text, kod = read_text_erkannt(p)
        ck = [z.strip() for z in text.splitlines() if z.startswith("C Koepfe")]
        zeilen.append(f"{p.name:34} {kod:16} {len(b):>6} B  "
                      f"erste Bytes {b[:4].hex(' ')}  {ck[0][:44] if ck else '(keine C-Koepfe-Zeile)'}")
    for p in sorted((FIX / "_m224").glob("_c_paket_e*.txt")) + sorted(
            (FIX / "_m222").glob("_c_paket_e*.txt")):
        b = read_bytes_shared(p)
        text, kod = read_text_erkannt(p)
        ges = [z.strip() for z in text.splitlines() if "offen GESAMT" in z]
        zeilen.append(f"{p.parent.name}/{p.name:28} {kod:16} {len(b):>6} B  "
                      f"erste Bytes {b[:4].hex(' ')}  {ges[0][:40] if ges else '(keine Zeile)'}")
    ZIEL.write_text("\n".join(zeilen) + "\n", encoding="utf-8", newline="\n")
    print(f"geschrieben: {ZIEL.name} ({len(zeilen)} Zeilen)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
