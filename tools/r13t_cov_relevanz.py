"""R13t (Punkt 2): Port-Relevanz vollstaendig - NUR LESEND, kein MAME-Lauf.

Auftrag (Nutzer 2026-09-28): "Punkt 4b vollstaendig machen (die ~30 min): ausgefuehrt vs.
gebaut (built_map) vs. verifiziert, mit Rumpf-Fenstern. Zusaetzlich: wie viele
Paket-E-Koepfe liegen in der ausgefuehrten Menge? Ergebnis als feste Zeile in /bilanz."

Quellen (alle vorhanden, offline):
  analysis/_m60_funcs.json        Funktionsinventar, je Zeile `NAME at <HEX>` (2072)
  capture/ppc_coverage.bin        SSCOV1-Byte-Map (4 MiB, Gameplay/DRC-Lauf)
  capture/ppc_cov_boot.bin        dieselbe Form, Boot-Lauf
  port/src/ckopf_leaves.cpp       `const Head kHeads[] = {...}` = die GEBAUTEN Koepfe
  scripts/c_kopf.py               `KOPF_DEF` = die registrierten/verifizierten Koepfe
  analysis/_m<N>/_c_paket_e.txt   Paket-E-Wurzeln und -Blaetter (neueste Datei)

Fenster: "Rumpf" = ab dem Eintritt bis zum ERSTEN `blr` (wie `c_kopf.rumpf_end`), hart
auf 0x400 B gedeckelt. "ausgefuehrt" = mindestens ein Coverage-Byte im Fenster; die
strenge Fassung (nur das Eintrittsbyte) wird zusaetzlich ausgegeben.

Aufruf:  python tools/r13t_cov_relevanz.py
"""

from __future__ import annotations

import re
import struct
from pathlib import Path

WS = Path("g:/Silent Scope Decomp")
BASE = 0x80000000
MAX_RUMPF = 0x400
BLR = 0x4E800020
FUNCS = WS / "analysis" / "_m60_funcs.json"
COVS = (WS / "capture" / "ppc_coverage.bin", WS / "capture" / "ppc_cov_boot.bin")
KOPF_C = WS / "scripts" / "c_kopf.py"
PORT_HEADS = WS / "port" / "src" / "ckopf_leaves.cpp"
ROM = WS / "rom" / "build" / "830d01.27p.main.bin"

_RE_KOPF = re.compile(r'\(\s*"[0-9A-Fa-f]+"\s*,\s*0x([0-9A-Fa-f]{8})\s*,')
_RE_HEAD = re.compile(r"\{\s*0x([0-9A-Fa-f]{8})u\s*,")
_RE_HEX8 = re.compile(r"\b([0-9A-F]{8})\b")

# Was die beiden Karten abdecken. QUELLE ist der Satz in
# `analysis/f5-descr-batch42-2026-09-17.md:87-88`: "die Coverage-Bins (…, 74 528
# markierte PCs aus Boot+Attract+Gameplay-Replay)". 74528 = beide Karten SUMMIERT
# (31929 + 42599), daher wird hier zusaetzlich die Vereinigungsmenge gemessen.
AUFNAHMEN = ("ppc_coverage.bin = Gameplay-Replay, ppc_cov_boot.bin = Boot+Attract "
             "(neueste Aufnahme 2026-09-17; deckt NICHT das ganze Spiel ab - "
             "Menuepfade/Service fehlen, s. analysis/bucket-d-2026-09-16.md:312)")
AUFNAHMEN_JSON = {
    "gameplay": "capture/ppc_coverage.bin",
    "boot_attract": "capture/ppc_cov_boot.bin",
    "beschreibung": AUFNAHMEN,
    "quelle": "analysis/f5-descr-batch42-2026-09-17.md:87-88",
}


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


def inventar() -> dict[int, tuple[int, int]]:
    """`analysis/_m60_inventar.csv`: Adresse -> (Groesse in B, Insn).

    Das CSV ist die Inventarquelle des Projekts (2072 Funktionen, Spalten
    `addr,name,size,span,...,insn,...`). `size` ist NICHT immer die Funktionsgrenze
    (R170/R177) - fuer die Huelle wird deshalb zusaetzlich am ersten `blr` gestoppt.
    """
    import csv

    p = WS / "analysis" / "_m60_inventar.csv"
    out: dict[int, tuple[int, int]] = {}
    if not p.is_file():
        return out
    with p.open(encoding="utf-8") as fp:
        for row in csv.DictReader(fp):
            try:
                addr = int(row["addr"])
                groesse = max(4, int(row["size"]))
                insn = int(row["insn"] or 0)
            except (KeyError, ValueError):
                continue
            out[addr] = (groesse, insn)
    return out


def _rufziele(abbild: bytes, adresse: int, groesse: int, bekannt: set[int]) -> set[int]:
    """Die Ziele der Rufbefehle in einem Rumpf (`bl` = Op 18 mit LK, Tail-`b`).

    Gescannt wird bis zum ersten `blr` ODER bis `groesse` (was zuerst kommt), hoechstens
    0x800 B - das ist dieselbe Rumpf-Idee wie in der Relevanzmessung.
    """
    off = adresse - BASE
    ziele: set[int] = set()
    for i in range(min(groesse, 0x800) // 4):
        if off + 4 * i + 4 > len(abbild):
            break
        w = struct.unpack_from(">I", abbild, off + 4 * i)[0]
        if w == BLR:
            break
        if (w >> 26) != 18:
            continue
        li = w & 0x03FFFFFC
        if li & 0x02000000:
            li -= 0x04000000
        pc = adresse + 4 * i
        ziel = (li if (w & 2) else (pc + li)) & 0xFFFFFFFF
        if (w & 1) or ziel in bekannt:          # `bl` oder Tail-`b` auf einen Kopf
            if ziel in bekannt:
                ziele.add(ziel)
    return ziele


def paket_e_huelle(abbild: bytes, wurzeln: set[int],
                   bekannt: set[int], groessen: dict[int, tuple[int, int]]) -> set[int]:
    """Der Ruf-Abschluss der Paket-E-Wurzeln (Definition aus `_c_paket_e.txt`)."""
    gesehen: set[int] = set()
    rand = [w for w in sorted(wurzeln) if w in bekannt]
    while rand:
        a = rand.pop()
        if a in gesehen:
            continue
        gesehen.add(a)
        groesse = groessen.get(a, (0x400, 0))[0]
        for z in _rufziele(abbild, a, groesse, bekannt):
            if z not in gesehen:
                rand.append(z)
    return gesehen


def verifizierte() -> set[int]:
    text = KOPF_C.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"^KOPF_DEF\s*=\s*\[(.*?)^\]", text, re.DOTALL | re.MULTILINE)
    return {int(a, 16) for a in _RE_KOPF.findall(m.group(1))} if m else set()


def kopf_leaves() -> set[int]:
    """Die Kopf-Leaves des C-Ports (`kHeads` in `ckopf_leaves.cpp`)."""
    text = PORT_HEADS.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"^const Head kHeads\[\]\s*=\s*\{(.*?)^\};", text,
                  re.DOTALL | re.MULTILINE)
    return {int(a, 16) for a in _RE_HEAD.findall(m.group(1))} if m else set()


def gebaute() -> set[int]:
    """`built_map()` aus `scripts/m104_built.py` - der Projektbegriff "gebaut".

    Der Import ist NUR LESEND (das Modul definiert Listen/Konstanten); ein
    `git status --porcelain` im Decomp-Repo beweist das nach dem Lauf.
    """
    import sys

    if str(WS / "scripts") not in sys.path:
        sys.path.insert(0, str(WS / "scripts"))
    import m104_built  # type: ignore

    return set(m104_built.built_all())


def paket_e() -> tuple[set[int], set[int]]:
    """(Wurzeln, Blaetter) aus der neuesten `_c_paket_e.txt`."""
    kandidaten = sorted(WS.glob("analysis/_m*/_c_paket_e.txt"),
                        key=lambda p: p.stat().st_mtime, reverse=True)
    if not kandidaten:
        return set(), set()
    text = kandidaten[0].read_text(encoding="utf-8", errors="replace")
    abschnitte = re.split(r"^== ", text, flags=re.MULTILINE)
    wurzeln: set[int] = set()
    blaetter: set[int] = set()
    for a in abschnitte:
        kopf = a.split("\n", 1)[0].upper()
        adressen = {int(x, 16) for x in _RE_HEX8.findall(a)}
        if kopf.startswith("PAKET-E-MODULE"):
            wurzeln |= adressen
        elif kopf.startswith("DIE BLAETTER"):
            blaetter |= adressen
    return wurzeln, blaetter


def rumpf_ende(abbild: bytes, adresse: int) -> int:
    """Erstes `blr` ab dem Eintritt (gedeckelt) - das gemessene Rumpfende."""
    off = adresse - BASE
    for i in range(MAX_RUMPF // 4):
        if off + 4 * i + 4 > len(abbild):
            break
        if struct.unpack_from(">I", abbild, off + 4 * i)[0] == BLR:
            return adresse + 4 * (i + 1)
    return adresse + MAX_RUMPF


def main() -> int:
    import json
    from datetime import datetime

    cov = coverage()
    abbild = ROM.read_bytes() if ROM.is_file() else b""
    funcs = funktionen()
    ver = verifizierte()
    gebaut = gebaute()
    leaves = kopf_leaves()
    wurzeln, blaetter = paket_e()
    gesetzt = sum(1 for b in cov if b)

    def fenster(addr: int) -> int:
        if not abbild:
            return MAX_RUMPF
        return max(4, rumpf_ende(abbild, addr) - addr)

    def laeuft(addr: int, fenster_b: int | None = None) -> bool:
        i = addr - BASE
        if i < 0 or i >= len(cov):
            return False
        n = fenster_b if fenster_b is not None else fenster(addr)
        return any(cov[i:i + n])

    ausgefuehrt = [(n, a) for n, a in funcs if laeuft(a)]
    streng = [a for _n, a in funcs if laeuft(a, 1)]
    gebaut_laeuft = [a for a in gebaut if laeuft(a)]
    leaves_laeuft = [a for a in leaves if laeuft(a)]
    ver_laeuft = [a for a in ver if laeuft(a)]
    w_laeuft = [a for a in wurzeln if laeuft(a)]
    b_laeuft = [a for a in blaetter if laeuft(a)]

    # ---- die drei Klassen des C-Arbeitsvorrats (R13t2, Punkt 4) --------------
    inv = inventar()
    bekannt = set(inv) or {a for _n, a in funcs}

    def insn_von(adressen) -> int:
        return sum(inv.get(a, (0, 0))[1] for a in adressen)

    huelle = paket_e_huelle(abbild, wurzeln, bekannt, inv) if abbild else set()
    nicht_gebaut = bekannt - gebaut
    k1 = sorted(a for a in nicht_gebaut if laeuft(a))
    k2 = sorted(a for a in nicht_gebaut if not laeuft(a) and a in huelle)
    k3 = sorted(a for a in nicht_gebaut if not laeuft(a) and a not in huelle)
    klassen = {
        "1_ausgefuehrt_nicht_gebaut": {"koepfe": len(k1), "insn": insn_von(k1)},
        "2_nicht_ausgefuehrt_paket_e": {"koepfe": len(k2), "insn": insn_von(k2)},
        "3_nicht_ausgefuehrt_rest": {"koepfe": len(k3), "insn": insn_von(k3)},
    }

    def pct(x: int, y: int) -> str:
        return f"{100.0 * x / y:.1f} %" if y else "-"

    print("# Port-Relevanz (Rumpf-Fenster = Eintritt bis erstes blr, max 0x400 B)")
    print(f"# Coverage: {gesetzt} von {len(cov)} Bytes gesetzt ({pct(gesetzt, len(cov))})")
    print(f"# Inventar (_m60_funcs.json):                 {len(funcs)} Funktionen")
    print(f"# davon ausgefuehrt (Rumpf-Fenster):          {len(ausgefuehrt)}"
          f"  ({pct(len(ausgefuehrt), len(funcs))})")
    print(f"# davon ausgefuehrt (nur Eintrittsbyte):      {len(streng)}")
    print(f"# gebaut (scripts/m104_built.py built_map):   {len(gebaut)}"
          f"  davon ausgefuehrt: {len(gebaut_laeuft)} ({pct(len(gebaut_laeuft), len(gebaut))})")
    print(f"#   darunter C-Kopf-Leaves (kHeads):          {len(leaves)}"
          f"  davon ausgefuehrt: {len(leaves_laeuft)}")
    print(f"# verifiziert (scripts/c_kopf.py KOPF_DEF):   {len(ver)}"
          f"  davon ausgefuehrt: {len(ver_laeuft)} ({pct(len(ver_laeuft), len(ver))})")
    print(f"# Paket-E-Wurzeln:                            {len(wurzeln)}"
          f"  davon ausgefuehrt: {len(w_laeuft)} ({pct(len(w_laeuft), len(wurzeln))})")
    print(f"# Paket-E-Blaetter (offen):                   {len(blaetter)}"
          f"  davon ausgefuehrt: {len(b_laeuft)} ({pct(len(b_laeuft), len(blaetter))})")
    print()
    print("# PORT-RELEVANZ (Zeile fuer /bilanz):")
    print(f"#   ausgefuehrt {len(ausgefuehrt)} | davon gebaut {len(gebaut_laeuft)}"
          f" | davon verifiziert {len(ver_laeuft)} von {len(ausgefuehrt)}"
          f"  ({pct(len(ver_laeuft), len(ausgefuehrt))})")
    print()
    print(f"# C-ARBEITSVORRAT (nicht gebaut: {len(nicht_gebaut)} Koepfe):")
    for name, werte in klassen.items():
        print(f"#   ({name}) {werte['koepfe']} Koepfe / {werte['insn']} Insn")
    print(f"# Paket-E-Huelle (eigene Nachrechnung ab den {len(wurzeln)} Wurzeln): "
          f"{len(huelle)} Koepfe"
          + (f"  (Projektzahl in _c_paket_e.txt: 274)" if huelle else ""))
    offen_huelle = sorted(nicht_gebaut & huelle)
    print(f"# davon NICHT gebaut (= offener Paket-E-Vorrat): {len(offen_huelle)} Koepfe"
          f" / {insn_von(offen_huelle)} Insn"
          f"  (Projektzahl der Bilanz: 38 Koepfe / 2674 Insn)"
          f" - davon ausgefuehrt: "
          f"{len([a for a in offen_huelle if laeuft(a)])}")
    print(f"# Aufnahmen: {AUFNAHMEN}")
    ziel = Path(__file__).resolve().parents[1] / "docs" / "_port_relevanz.json"
    ziel.write_text(json.dumps({
        "erzeuger": "tools/r13t_cov_relevanz.py",
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "fenster": "Rumpf (Eintritt bis erstes blr, max 0x400 B)",
        "inventar": len(funcs),
        "ausgefuehrt": len(ausgefuehrt),
        "ausgefuehrt_eintritt": len(streng),
        "gebaut": len(gebaut),
        "gebaut_ausgefuehrt": len(gebaut_laeuft),
        "verifiziert": len(ver),
        "verifiziert_ausgefuehrt": len(ver_laeuft),
        "kopf_leaves": len(leaves),
        "kopf_leaves_ausgefuehrt": len(leaves_laeuft),
        "paket_e_wurzeln": len(wurzeln),
        "paket_e_wurzeln_ausgefuehrt": len(w_laeuft),
        "paket_e_blaetter": len(blaetter),
        "paket_e_blaetter_ausgefuehrt": len(b_laeuft),
        "paket_e_huelle": len(huelle),
        "paket_e_huelle_offen": len(offen_huelle),
        "paket_e_huelle_offen_ausgefuehrt": len([a for a in offen_huelle if laeuft(a)]),
        "klassen": klassen,
        "aufnahmen": AUFNAHMEN_JSON,
    }, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"# Cache fuer /bilanz: {ziel}")
    print()
    print("# Gebaut, aber NICHT in der Aufnahme ausgefuehrt"
          f" ({len(gebaut) - len(gebaut_laeuft)}):")
    leer = sorted(a for a in gebaut if not laeuft(a))
    for i in range(0, len(leer), 8):
        print("  " + " ".join(f"0x{a:08X}" for a in leer[i:i + 8]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
