"""R13s (4b): Port-Relevanz aus der vorhandenen Coverage - NUR LESEND, kein MAME-Lauf.

Auftrag (Nutzer 2026-09-28): "Eine gemessene Port-Relevanz-Zahl: Anteil der in der
vorhandenen Level-1-Aufnahme tatsaechlich ausgefuehrten Funktionen, die portiert UND
verifiziert sind. Pruefe, ob die vorhandenen Logs/Zaehllaeufe das ohne neuen MAME-Lauf
hergeben, und nenne den Aufwand."

Quellen (alle vorhanden, offline):
  analysis/_m60_funcs.json      Funktionsinventar, je Zeile `NAME at <HEX>` (2072)
  capture/ppc_coverage.bin      SSCOV1-Byte-Map (4 MiB, Gameplay/DRC-Lauf)
  capture/ppc_cov_boot.bin      dieselbe Form, Boot-Lauf
  scripts/c_kopf.py             `KOPF_DEF` = die registrierten C-Koepfe (78, verifiziert)

Methode:
  * "ausgefuehrt" = im Fenster [Eintritt, Eintritt + FENSTER) ist mindestens ein
    Coverage-Byte gesetzt. FENSTER = 0x100 (64 Befehle) deckt den Eintrittsblock ab;
    zusaetzlich wird die strenge Fassung (nur das Eintrittsbyte) ausgegeben.
  * "verifiziert" = der Kopf steht in `KOPF_DEF` (je Kopf 24 Vergleichsfaelle, `vergl alle`).
  * "portiert" unterscheidet dieses Werkzeug NICHT - dafuer muesste die Bau-Liste aus
    `m104_built.built_map()` mitgelesen werden (offener Aufwand, s. Bericht).

Aufruf:  python tools/r13s_cov_probe.py
"""

from __future__ import annotations

import re
import struct
from pathlib import Path

WS = Path("g:/Silent Scope Decomp")
BASE = 0x80000000
FENSTER = 0x100
FUNCS = WS / "analysis" / "_m60_funcs.json"
COVS = (WS / "capture" / "ppc_coverage.bin", WS / "capture" / "ppc_cov_boot.bin")
SCRIPT = WS / "scripts" / "c_kopf.py"
_EINTRAG = re.compile(r'\(\s*"(?P<tag>[0-9A-Fa-f]+)"\s*,\s*0x(?P<start>[0-9A-Fa-f]{8})\s*,')


def coverage() -> bytearray:
    merged = bytearray(0x400000)
    for p in COVS:
        if not p.is_file():
            continue
        data = p.read_bytes()
        if data[:6] != b"SSCOV1":
            continue
        for i, b in enumerate(data[16:]):
            if b and i < len(merged):
                merged[i] = 1
    return merged


def funktionen() -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for zeile in FUNCS.read_text(encoding="utf-8", errors="replace").splitlines():
        if " at " not in zeile:
            continue
        name, addr = zeile.rsplit(" at ", 1)
        try:
            out.append((name.strip(), int(addr.strip(), 16)))
        except ValueError:
            continue
    return out


def verifizierte() -> set[int]:
    text = SCRIPT.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"^KOPF_DEF\s*=\s*\[(.*?)^\]", text, re.DOTALL | re.MULTILINE)
    return {int(e.group("start"), 16) for e in _EINTRAG.finditer(m.group(1))} if m else set()


def main() -> int:
    cov = coverage()
    gesetzt = sum(1 for b in cov if b)
    funcs = funktionen()
    ver = verifizierte()

    def beruehrt(addr: int, fenster: int) -> bool:
        i = addr - BASE
        return 0 <= i < len(cov) and any(cov[i:i + fenster])

    ausgefuehrt = [(n, a) for n, a in funcs if beruehrt(a, FENSTER)]
    streng = [(n, a) for n, a in funcs if beruehrt(a, 1)]
    schnitt = [(n, a) for n, a in ausgefuehrt if a in ver]
    ver_ausgefuehrt = [a for a in ver if beruehrt(a, FENSTER)]

    print("# Port-Relevanz aus der vorhandenen Coverage (kein MAME-Lauf)")
    print(f"# Coverage-Bytes gesetzt: {gesetzt} von {len(cov)} "
          f"({100.0 * gesetzt / len(cov):.2f} % des Abbilds)")
    print(f"# Funktionsinventar (_m60_funcs.json): {len(funcs)} Funktionen")
    print(f"# davon ausgefuehrt (Fenster {FENSTER} B): {len(ausgefuehrt)}")
    print(f"# davon ausgefuehrt (nur Eintrittsbyte):  {len(streng)}")
    print(f"# registrierte/verifizierte C-Koepfe (KOPF_DEF): {len(ver)}")
    print(f"# davon ausgefuehrt: {len(ver_ausgefuehrt)}")
    print(f"# SCHNITT ausgefuehrt UND verifiziert: {len(schnitt)}")
    if ausgefuehrt:
        print(f"# ANTEIL der ausgefuehrten Funktionen, die verifiziert sind: "
              f"{100.0 * len(schnitt) / len(ausgefuehrt):.1f} %")
    print()
    print("Die verifizierten Koepfe, die die Aufnahme NICHT ausfuehrt:")
    leer = sorted(a for a in ver if not beruehrt(a, FENSTER))
    print("  " + (", ".join(f"0x{a:08X}" for a in leer) if leer else "(keiner)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
