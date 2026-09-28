"""R13s (4a): CA-Zensus ueber die registrierten C-Koepfe - NUR LESEND.

Auftrag (Nutzer 2026-09-28): "R535 als NEUPRUEFUNG formulieren: alle bisher gruenen
Koepfe listen, die addc/adde/addme/addze/subfc/subfe/subfme/subfze oder andere
CA-abhaengige Befehle enthalten, und nach dem Fix neu vergleichen. Wie viele der 78
gruenen Koepfe sind betroffen? (Zaehlung mit erzeugendem Befehl.)"

Das Werkzeug liest
  * die Kopf-Liste `KOPF_DEF` (Start- und Endadresse je Kopf) aus `scripts/c_kopf.py`
    (`c_kopf.PROFILES = [(lambda d=d: _profil_def(d)) for d in KOPF_DEF]`, Zeile 2637) und
  * die Rohworte des PPC-Abbilds `rom/build/830d01.27p.main.bin` (Base 0x80000000).
Es aendert NICHTS im Decomp-Repo und braucht weder Ghidra noch Netz.

CA-abhaengige Befehle auf der PowerPC 403 (XO-Formen, Hauptopcode 31):
  addc 10, adde 138, addme 234, addze 202,
  subfc 8, subfe 136, subfme 232, subfze 200.
`add`/`subf`/`neg`/`mullw`/`divw*` beruehren CA NICHT (sie stehen im Rc-Zensus, nicht
hier).

Aufruf:
    python tools/r13s_ca_zensus.py [--json <datei>]
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from pathlib import Path

WS = Path("g:/Silent Scope Decomp")
SCRIPT = WS / "scripts" / "c_kopf.py"
ROM = WS / "rom" / "build" / "830d01.27p.main.bin"
BASE = 0x80000000

CA = {10: "addc", 138: "adde", 234: "addme", 202: "addze",
      8: "subfc", 136: "subfe", 232: "subfme", 200: "subfze"}
# Weitere XO-Formen, die hier nur zur ANZEIGE gebraucht werden (R535-Pruefung).
XO_NAME = {**CA, **{266: "add", 40: "subf", 0: "cmp", 32: "cmpl", 104: "neg",
                    235: "mullw", 459: "divwu"}}
OP_NAME = {14: "addi", 15: "addis", 12: "addic", 13: "addic.", 8: "subfic",
           34: "lwz", 36: "stw", 32: "lwz", 37: "lwzu", 16: "bc", 18: "b",
           19: "bclr/blr", 31: "(op31: siehe XO)"}

_EINTRAG = re.compile(r'\(\s*"(?P<tag>[0-9A-Fa-f]+)"\s*,\s*0x(?P<start>[0-9A-Fa-f]{8})\s*,'
                      r'\s*0x(?P<ende>[0-9A-Fa-f]{8})')


def kopf_def(text: str) -> list[tuple[str, int, int]]:
    """Die Eintraege von `KOPF_DEF` aus dem Quelltext (ohne das Modul zu importieren)."""
    m = re.search(r"^KOPF_DEF\s*=\s*\[(.*?)^\]", text, re.DOTALL | re.MULTILINE)
    if not m:
        raise SystemExit("KOPF_DEF nicht gefunden in " + str(SCRIPT))
    out: list[tuple[str, int, int]] = []
    for e in _EINTRAG.finditer(m.group(1)):
        out.append((e.group("tag"), int(e.group("start"), 16), int(e.group("ende"), 16)))
    return out


def woerter(abbild: bytes, start: int, ende: int) -> list[int]:
    off = start - BASE
    n = max(1, (ende - start) // 4)
    return [struct.unpack_from(">I", abbild, off + 4 * i)[0] for i in range(n)]


def zaehle(words: list[int]) -> dict[str, int]:
    treffer: dict[str, int] = {}
    for w in words:
        if (w >> 26) != 31:
            continue
        name = CA.get((w >> 1) & 0x3FF)
        if name:
            treffer[name] = treffer.get(name, 0) + 1
    return treffer


def _name(w: int) -> str:
    """Grober Name eines Wortes (nur fuer die Anzeige einer Kopf-Dekodierung)."""
    op = w >> 26
    if op == 31:
        return XO_NAME.get((w >> 1) & 0x3FF, f"op31/xo{(w >> 1) & 0x3FF}")
    return OP_NAME.get(op, f"op{op}")


def kopf_zeigen(abbild: bytes, adresse: int) -> int:
    """Einzelkopf dekodieren: Wort, Name, Rc/OE-Bit (R535-Pruefung)."""
    treffer = [k for k in kopf_def(SCRIPT.read_text(encoding="utf-8", errors="replace"))
               if k[1] == adresse]
    if not treffer:
        print(f"0x{adresse:08X} steht nicht in KOPF_DEF")
        return 2
    tag, start, ende = treffer[0]
    print(f"# Kopf {tag} 0x{start:08X}..0x{ende:08X} ({(ende - start) // 4} Woerter)")
    for i, w in enumerate(woerter(abbild, start, ende)):
        op = w >> 26
        rc = (w & 1) and op == 31
        oe = ((w >> 10) & 1) and op == 31
        extra = ""
        if op == 31 and ((w >> 1) & 0x3FF) in CA:
            extra = "   <== CA-Form"
        print(f"  +{4 * i:02X}  0x{w:08X}  {_name(w)}{'.' if rc else ''}"
              f"{'  OE=1' if oe else ''}{extra}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", default="", help="Ergebnis zusaetzlich als JSON ablegen")
    p.add_argument("--kopf", default="", help="einen Kopf dekodieren, z. B. 0x8005BF74")
    args = p.parse_args(argv)

    if args.kopf:
        return kopf_zeigen(ROM.read_bytes(), int(args.kopf, 0))

    koepfe = kopf_def(SCRIPT.read_text(encoding="utf-8", errors="replace"))
    abbild = ROM.read_bytes()
    betroffen: list[dict] = []
    gesamt_insn = 0
    for tag, start, ende in koepfe:
        words = woerter(abbild, start, ende)
        gesamt_insn += len(words)
        treffer = zaehle(words)
        if treffer:
            betroffen.append({"tag": tag, "head": f"0x{start:08X}", "insn": len(words),
                              "treffer": treffer,
                              "summe": sum(treffer.values())})
    print(f"# CA-Zensus ueber die registrierten C-Koepfe (KOPF_DEF)")
    print(f"# Koepfe: {len(koepfe)} | Insn (Rumpf laut KOPF_DEF): {gesamt_insn}")
    print(f"# CA-abhaengige Befehle: {', '.join(sorted(CA.values()))}")
    print(f"# BETROFFEN: {len(betroffen)} von {len(koepfe)} Koepfen")
    print()
    print("Kopf        Insn  erzeugender Befehl (Anzahl)")
    for e in betroffen:
        liste = ", ".join(f"{k} x{v}" for k, v in sorted(e["treffer"].items()))
        print(f"{e['head']}  {e['insn']:>4}  {liste}   (Tag {e['tag']})")
    if not betroffen:
        print("(keiner - kein registrierter Kopf enthaelt einen CA-abhaengigen Befehl)")
    if args.json:
        Path(args.json).write_text(json.dumps({"koepfe": len(koepfe),
                                               "insn": gesamt_insn,
                                               "betroffen": betroffen},
                                              indent=1, ensure_ascii=False) + "\n",
                                   encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
