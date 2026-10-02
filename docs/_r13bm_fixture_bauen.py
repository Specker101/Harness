"""R13bm - Fixture fuer den API-Fehler bauen (nur lesend, schreibt EINE Datei).

Quelle: `runs/b235/stream.jsonl` — der Mitschnitt der B235-**Fortsetzung**. Die
Fehlerzeile ist die vom Nutzer genannte `stream.jsonl:28441`:

    {"type":"assistant","message":{"model":"<synthetic>", …
     "text":"API Error: API returned an empty or malformed response (HTTP 200) …"}}

Die Fixture ist ein **wortgetreuer Zeilenausschnitt** (kein Nachbau, keine Umschrift),
damit der Test am echten Material haengt. Zusaetzlich kommen zwei Zeilen DAVOR mit, damit
der Test „letzter Text ist der Fehler" pruefen kann.

Geschrieben wird nach `harness/tests/fixtures/b235_api_fehler.jsonl`; `.gitattributes`
fuehrt `harness/tests/fixtures/**  -text`, die Bytes bleiben also wie sie sind.
"""
from __future__ import annotations

import io
from pathlib import Path

ROOT = Path(r"g:/Harness/harness")
QUELLE = ROOT / "runs" / "b235" / "stream.jsonl"
ZIEL = ROOT / "tests" / "fixtures" / "b235_api_fehler.jsonl"
# Die Fehlerzeile und zwei Zeilen davor (Kontext fuer „normaler Text, dann Fehler").
VON, BIS = 28439, 28442


def main() -> int:
    if not QUELLE.is_file():
        print(f"Quelle fehlt: {QUELLE}")
        return 1
    zeilen: list[str] = []
    with io.open(QUELLE, encoding="utf-8", errors="replace") as f:
        for nr, zeile in enumerate(f, 1):
            if nr < VON:
                continue
            if nr > BIS:
                break
            zeilen.append(zeile.rstrip("\n"))
    if len(zeilen) != (BIS - VON + 1):
        print(f"ABBRUCH: nur {len(zeilen)} Zeilen gelesen ({VON}..{BIS})")
        return 1
    if '"<synthetic>"' not in zeilen[28441 - VON]:
        print("ABBRUCH: die Fehlerzeile ist nicht an der erwarteten Stelle")
        return 1
    ZIEL.parent.mkdir(parents=True, exist_ok=True)
    with io.open(ZIEL, "w", encoding="utf-8", newline="\n") as f:
        for z in zeilen:
            f.write(z + "\n")
    print(f"geschrieben: {ZIEL} ({ZIEL.stat().st_size} Bytes, {len(zeilen)} Zeilen)")
    for z in zeilen:
        print(f"   {len(z):7d} Zeichen  {z[:90]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
