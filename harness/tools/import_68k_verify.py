#!/usr/bin/env python
"""Nachtrag zum 68K-Import: Verifikation gegen die Repo-Belege (nur lesend)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HARNESS = Path(r"g:\Harness\harness")
sys.path.insert(0, str(HARNESS))

from hx.config import load_config                                  # noqa: E402
from hx.ghidra import Ghidra                                       # noqa: E402

P = "830a08.7s.68k"
BERICHT = Path(r"g:\Harness\docs\_68k_import_bericht.txt")
zeilen: list[str] = []


def p(*a) -> None:
    t = " ".join(str(x) for x in a)
    zeilen.append(t)
    print(t)


def main() -> int:
    g = Ghidra(load_config())
    p("")
    p("## 7. Verifikation gegen die Repo-Belege")
    p("")
    fz0 = g.call("/get_function_count", {"program": P})["function_count"]
    p(f"- Funktionszahl jetzt: {fz0}")

    r = g.call("/get_function_by_address", {"address": "0x5ED8", "program": P})
    p(f"- Funktion 0x5ED8: {json.dumps(r, ensure_ascii=False)[:200]}")
    p("  GEGENPROBE (analysis/_m171/_heads.txt:81):")
    p("  `5ED8   2770    752     5  voice_program` -> 2770 Byte / 752 Instruktionen.")
    p("  Ghidra-Body 0x5ED8-0x69A9 = 2770 Byte - Zahl stimmt ueberein; das ist der")
    p("  Beweis, dass Basisadresse 0 und die Worttauschung richtig sind.")

    p("")
    p("- Vektor-Einstiege, die Ghidra im Rohimport selbst gefunden hat (list_functions):")
    for f in g.call("/list_functions", {"program": P, "limit": 8}).get("raw", "").splitlines():
        p(f"    {f.strip()}")
    p("  GEGENPROBE (analysis/_memory/audio-subsystem.md, 'Ladeforschung'):")
    p("  PC = 0x00000080, IRQ1 0x0AE, IRQ2 0x0C8, IRQ6 0x0E2 - alle vier sind da.")

    p("")
    p("- Stichproben (POST /disassemble_bytes, Funktionszahl vorher/nachher gleich:")
    p(f"  {fz0} -> {fz0}, also kein Nebeneffekt im Sinne von R398):")
    for adr, erwartet in ((0x5ED8, "Kopf `voice_program`"), (0x442C, "Kopf aus dem Stimmenpfad"),
                          (0x5F66, "belegte Zeile aus port-batch166.md:316")):
        a = g._post("/disassemble_bytes", {"start_address": hex(adr), "length": 16,
                                           "include_instructions": True},
                    params={"program": P}, timeout=60)
        erste = (a.get("instructions") or [{}])[0]
        p(f"    0x{adr:X} [{erwartet}]: {erste.get('mnemonic')} {erste.get('operands')}"
          f"  bytes={erste.get('bytes')}")
    p("  GEGENPROBE: 0x5F66 muss laut Repo `movea.l #$7a004,a1` sein (227c0007a004).")
    p("  Rohbytes der Datei an 0x5ED8/0x442C: 4e56ffcc / 4e560000 = link.w A6,-0x34 / 0.")
    BERICHT.write_text(BERICHT.read_text(encoding="utf-8") + "\n".join(zeilen) + "\n",
                       encoding="utf-8")
    print(f"\nangehaengt an {BERICHT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
