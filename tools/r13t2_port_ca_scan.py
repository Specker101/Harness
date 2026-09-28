"""R13t2 (1a): CA-Muster in den PORT-QUELLEN der CA-Koepfe - NUR LESEND.

Auftrag (Nutzer 2026-09-28): "alle Port-Quellen der 34 CA-Koepfe auf dasselbe Muster
pruefen (CA wird addiert, obwohl im ROM `addc`/`subfc` statt `adde`/`subfe` steht).
Zensus-Werkzeug um die Port-Seite erweitern, Ergebnis mit Datei:Zeile."

Vorgehen (drei Schritte, alles offline):
  1. `scripts/c_kopf.py::KOPF_DEF` = die registrierten Koepfe; die Rohworte aus
     `rom/build/830d01.27p.main.bin` (Base 0x80000000) ergeben je Kopf die CA-Formen
     (`addc` 10 / `adde` 138 / `addme` 234 / `addze` 202 / `subfc` 8 / `subfe` 136 /
     `subfme` 232 / `subfze` 200 - XO-Formen, Hauptopcode 31).
  2. `Kopf -> Portfunktion`: die Tabelle `const Head kHeads[]` in
     `port/src/ckopf_leaves.cpp` fuehrt je Kopf `{adresse, Insn, Beschreibung, LXXXXX}`.
  3. Die Portfunktion wird aus den Quellen geschnitten (Brace-Matching ab der
     Definition) und auf **CA-verbrauchende Muster** geprueft:
       `+ 1u`, `+ 1`, `+ ca`, `ca =`, `carry` …
     Jeder Treffer wird eingeordnet:
       * `ok (adde)`,      wenn das ROM des Kopfes eine CA-LESENDE Form hat,
       * `harmlos (addic)`, wenn die Zeile selbst einen Nicht-CA-Befehl kommentiert
                            (`addic`/`addi`/`subfic`/`lwzu` … = Zaehler/Adresse),
       * `VERDAECHTIG`,    sonst (CA wird addiert, obwohl das ROM nur `addc`/`subfc` hat).

Aufruf:  python tools/r13t2_port_ca_scan.py [--json <datei>] [--kopf 0x8005BF74]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
import r13s_ca_zensus as zensus  # noqa: E402  (KOPF_DEF-Parser, ROM, BASE, CA)

WS = zensus.WS
PORT = WS / "port"
HEADS_C = PORT / "src" / "ckopf_leaves.cpp"
# Die XO-Formen, die CA LESEN (alles andere schreibt CA nur).
CA_LESEND = {138: "adde", 234: "addme", 202: "addze",
             136: "subfe", 232: "subfme", 200: "subfze"}
# Zeilen, die CA offensichtlich NICHT wegen eines CA-Befehls addieren.
NICHT_CA = re.compile(r"addic|addi\b|addis|subfic|lwzu|lbzu|stbu|stwu|addq", re.IGNORECASE)
# Ein Inkrement (auch `+= 1u`) ist erst dann CA-VERDACHT, wenn es aus einem VERGLEICH
# kommt (Carry-Fortpflanzung) - `r0 += 1u` im Schleifenrumpf ist harmlos.
_RE_INKREMENT = re.compile(r"\+=\s*1u?\b|\+\s*1u?\b")
_RE_VERGLEICH = re.compile(r">=|<=|(?<![<>!=])\s[<>]\s|\?\s*1u?\s*:|\bca\b")
_RE_CA_WORT = re.compile(r"\bca\b|\bCA\b|carry|Uebertrag")
_RE_KOMMENTAR = re.compile(r"//\s*(.+)$")
_RE_HEAD_EINTRAG = re.compile(r"\{\s*0x(?P<addr>[0-9A-Fa-f]{8})u\s*,\s*(?P<insn>\d+)u\s*,"
                              r"\s*\"[^\"]*\"\s*,\s*(?P<fn>[A-Za-z_][A-Za-z0-9_]*)\s*\}")


def kopf_zu_funktion() -> dict[int, str]:
    """`Kopf -> Portfunktion` aus der `kHeads`-Tabelle."""
    text = HEADS_C.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"^const Head kHeads\[\]\s*=\s*\{(.*?)^\};", text,
                  re.DOTALL | re.MULTILINE)
    if not m:
        raise SystemExit("kHeads-Tabelle nicht gefunden")
    return {int(e.group("addr"), 16): e.group("fn")
            for e in _RE_HEAD_EINTRAG.finditer(m.group(1))}


def quellen() -> list[Path]:
    return sorted(list((PORT / "src").glob("*.cpp")) + list((PORT / "include").rglob("*.h")))


def funktionstext(name: str) -> tuple[Path, int, str] | None:
    """Die Definition `name` inkl. Rumpf (Brace-Matching) plus Datei und Startzeile."""
    muster = re.compile(r"^[A-Za-z_][A-Za-z0-9_:<>,\s\*&]*\b" + re.escape(name) + r"\s*\(",
                        re.MULTILINE)
    for p in quellen():
        text = p.read_text(encoding="utf-8", errors="replace")
        m = muster.search(text)
        if not m:
            continue
        i = text.find("{", m.end())
        if i < 0:
            continue
        tiefe, j = 0, i
        while j < len(text):
            if text[j] == "{":
                tiefe += 1
            elif text[j] == "}":
                tiefe -= 1
                if tiefe == 0:
                    break
            j += 1
        return p, text[:m.start()].count("\n") + 1, text[m.start():j + 1]
    return None


def inventar_ca(abbild: bytes) -> dict:
    """CA-Zensus ueber ALLE Inventarfunktionen (`analysis/_m60_inventar.csv`).

    Gegenprobe zur Kopf-Pruefung: CA-LESENDE Formen sind im Programm erlaubt und
    noetig (`addze` nach `addc`, `subfe` nach `addic`) - sie duerfen nur nicht in den
    Koepfen stehen, deren ROM sie nicht hat. Gezaehlt wird innerhalb der
    Inventargroesse `size`.
    """
    import csv

    pfad = WS / "analysis" / "_m60_inventar.csv"
    lesend: dict[str, int] = {}
    schreibend: dict[str, int] = {}
    funktionen = 0
    with pfad.open(encoding="utf-8") as fp:
        for row in csv.DictReader(fp):
            try:
                adresse, groesse = int(row["addr"]), int(row["size"])
            except (KeyError, ValueError):
                continue
            funktionen += 1
            for w in zensus.woerter(abbild, adresse, adresse + max(4, groesse)):
                if (w >> 26) != 31:
                    continue
                xo = (w >> 1) & 0x3FF
                if xo in CA_LESEND:
                    lesend[CA_LESEND[xo]] = lesend.get(CA_LESEND[xo], 0) + 1
                elif xo in zensus.CA:
                    n = zensus.CA[xo]
                    schreibend[n] = schreibend.get(n, 0) + 1
    return {"funktionen": funktionen, "lesend": lesend, "schreibend": schreibend}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", default="")
    p.add_argument("--kopf", default="", help="nur einen Kopf pruefen")
    args = p.parse_args(argv)

    abbild = zensus.ROM.read_bytes()
    koepfe = zensus.kopf_def(zensus.SCRIPT.read_text(encoding="utf-8", errors="replace"))
    tabelle = kopf_zu_funktion()
    nur = int(args.kopf, 0) if args.kopf else None

    zeilen: list[str] = []
    ergebnis: list[dict] = []
    ca_koepfe = 0
    for tag, start, ende in koepfe:
        if nur is not None and start != nur:
            continue
        formen = zensus.zaehle(zensus.woerter(abbild, start, ende))
        if not formen:
            continue
        ca_koepfe += 1
        lesend = {n: c for n, c in formen.items() if n in CA_LESEND.values()}
        fn = tabelle.get(start)
        treffer: list[dict] = []
        quelle = "(keine Portfunktion in kHeads)"
        if fn:
            gefunden = funktionstext(fn)
            if not gefunden:
                quelle = f"{fn}: Definition nicht gefunden"
            else:
                pfad, startzeile, rumpf = gefunden
                quelle = f"{pfad.name} {fn}() ab Zeile {startzeile}"
                rumpfzeilen = rumpf.splitlines()
                for i, zeile in enumerate(rumpfzeilen):
                    inkrement = _RE_INKREMENT.search(zeile)
                    ca_wort = _RE_CA_WORT.search(zeile)
                    if not (inkrement or ca_wort):
                        continue
                    kommentar = _RE_KOMMENTAR.search(zeile)
                    # BLINDSTELLE 1: der Vergleich kann in den ZWEI ZEILEN DAVOR stehen
                    # (mehrzeiliges `if (…)` / `ca = (…)`). Deshalb das Fenster pruefen.
                    fenster = "\n".join(rumpfzeilen[max(0, i - 2):i + 1])
                    if lesend:
                        art = "ok (adde)"
                    elif kommentar and NICHT_CA.search(kommentar.group(1)):
                        art = "harmlos (addic)"
                    elif inkrement and _RE_VERGLEICH.search(fenster):
                        art = "VERDAECHTIG"
                    elif ca_wort and not inkrement:
                        art = "CA erwaehnt"
                    else:
                        art = "harmlos (Zaehler)"
                    treffer.append({"datei": pfad.name,
                                    "zeile": startzeile + i,
                                    "art": art,
                                    "text": zeile.strip()[:120]})
        ergebnis.append({"kopf": tag, "adresse": f"0x{start:08X}", "funktion": fn or "",
                         "formen": formen, "ca_lesend": lesend, "quelle": quelle,
                         "treffer": treffer})
        verdacht = [t for t in treffer if t["art"] == "VERDAECHTIG"]
        nennungen = [t for t in treffer if t["art"] == "CA erwaehnt"]
        marke = "  <== VERDACHT" if verdacht else ("  (CA genannt)" if nennungen else "")
        zeilen.append(f"{tag}  {format_formen(formen)}  {quelle}{marke}")
        for t in verdacht + nennungen + [x for x in treffer if x["art"].startswith("ok ")][:1]:
            zeilen.append(f"     {t['art']:18s} {t['datei']}:{t['zeile']}  {t['text']}")

    print(f"# CA-Zensus mit PORT-Seite ({ca_koepfe} Koepfe mit CA-Formen von "
          f"{len(koepfe)} registrierten)")
    inventar = inventar_ca(abbild)
    print(f"# CA-Formen im GANZEN Inventar ({inventar['funktionen']} Funktionen):")
    print("#   LESEND  : " + (", ".join(f"{n}x{c}" for n, c in
                                     sorted(inventar["lesend"].items(), key=lambda kv: -kv[1]))
                                or "keine"))
    print("#   schreibend: " + (", ".join(f"{n}x{c}" for n, c in
                                       sorted(inventar["schreibend"].items(), key=lambda kv: -kv[1]))
                                   or "keine"))
    print("#   in den 78 registrierten Koepfen: LESEND 0 (s. Kopf-Liste unten)")
    verdaechtige = [(e, t) for e in ergebnis for t in e["treffer"]
                    if t["art"] == "VERDAECHTIG"]
    print(f"# VERDAECHTIGE Stellen: {len(verdaechtige)}")
    for e, t in verdaechtige:
        print(f"  {e['kopf']} {e['adresse']}  {t['datei']}:{t['zeile']}  {t['text']}")
    print()
    for z in zeilen:
        print(z)
    if args.json:
        Path(args.json).write_text(json.dumps(
            {"koepfe_mit_ca": ca_koepfe, "registrierte": len(koepfe),
             "inventar_ca": inventar,
             "verdaechtig": [{"kopf": e["kopf"], **t} for e, t in verdaechtige],
             "koepfe": ergebnis}, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"\n# JSON: {args.json}")
    return 0 if not verdaechtige else 1


def format_formen(formen: dict[str, int]) -> str:
    return ", ".join(f"{n}x{c}" for n, c in sorted(formen.items(),
                                                   key=lambda kv: -kv[1]))


if __name__ == "__main__":
    raise SystemExit(main())
