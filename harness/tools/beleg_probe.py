"""Belegpruefung der Schatten-Aussensichten: sind die Belege aufloesbar? (R13bx)

Zweck.  Zwei Arme liefern eine verschiedene Zahl von Befunden - das allein sagt nichts,
denn mehr Befunde koennen auch mehr Geschwaetz sein.  Gezaehlt wird deshalb die
**Belegquote**: zeigt jeder Befund auf eine Stelle, die es wirklich gibt?

Geprueft wird je Befund
  * gibt es die genannte Datei in einem der bekannten Wuurzeln (Decomp-Repo,
    Harness-Wurzel, harness/)?
  * liegt die genannte Zeile im Bereich der Datei (Zeilenzahl)?
  * wurde ueberhaupt eine Stelle genannt?

WEGGELASSEN
    Ob ein aufloesbarer Beleg INHALTLICH stimmt.  "analysis/foo.md:12 existiert und hat
    400 Zeilen" heisst NICHT, dass Zeile 12 die behauptete Zahl traegt.  Ebenso bleibt
    die Gewichtung (hoch/mittel/niedrig) ungeprueft.
NICHT ZULAESSIG
    Ein Urteil "besser" allein aus diesen Zahlen.  Eine Belegquote von 100 % heisst nur,
    dass jede Aussage auf eine existierende Stelle zeigt.  Ueber Nutzen und Wahrheit
    entscheidet das nicht - dafuer muesste ein Reviewer die Befunde bewerten (Abo).

Zuordnung der Arme.  Der Vergleichsschluessel ist - wie in `bedienung.md` Paragraph 19a
beschrieben - die **erste genannte Stelle** (`Datei:Zeile`), normalisiert: Schraegstriche
vereinheitlicht, fuehrende `./` weg, Zeilenbereich auf die Startzeile reduziert.  Zwei
Befunde zum selben Ort zaehlen damit als EINE Stelle.  Das ist beabsichtigt und steht
auch so in der Ausgabe.

Aufruf:

    python tools/beleg_probe.py --batch 309 --batch 313 --batch 317
    python tools/beleg_probe.py --batch 309 --stufe high --stufe max --stdout
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hx import aussensicht                                    # noqa: E402
from hx.config import load_config                             # noqa: E402
from hx.util import read_json, read_text, write_text_atomic   # noqa: E402

# Eine genannte Stelle.  Der Doppelpunkt steckt auch im Laufwerksbuchstaben (`g:\...`),
# deshalb laesst die Klasse ihn zu - das Zuruecksetzen findet die Endung trotzdem.
_RE_STELLE = re.compile(
    r"(?P<datei>[A-Za-z0-9_:./\\-]+\.(?:cpp|hpp|hh|h|c|py|md|json|jsonl|txt|inc|ps1"
    r"|toml|cfg|tsv|csv|log))"
    r"(?:\s*:\s*(?P<zeile>\d+)(?:\s*[-–]\s*(?P<bis>\d+))?)?", re.IGNORECASE)

VORGABE_STUFEN = ("high", "max")


def stelle(text: str) -> tuple[str, int | None] | None:
    """`('analysis/foo.md', 12)` aus einem Belegtext - oder None, wenn nichts dasteht."""
    roh = (text or "").replace("`", " ")
    m = _RE_STELLE.search(roh)
    if not m:
        return None
    datei = m.group("datei").lstrip("./").replace("\\", "/")
    zeile = int(m.group("zeile")) if m.group("zeile") else None
    return (datei, zeile)


class Wuurzeln:
    """Bekannte Wuurzeln + Zeilenzahl-Cache (jede Datei wird einmal gezaehlt).

    `zusatz` faengt ABGESCHNITTENE Pfade ab (gemessen 2026-10-09: die Antwort nannte
    `_m242/_c_paket_e.txt`, gemeint war `analysis/_m242/_c_paket_e.txt`).  Der Fund wird
    als Hinweis ausgewiesen - verschwiegen wird er nicht.
    """

    def __init__(self, cfg):
        self.wurzeln = [Path(cfg.decomp), Path(cfg.root), Path(cfg.root).parent]
        self.zusatz = [(Path(cfg.decomp) / "analysis", "analysis/")]
        self._zeilen: dict[Path, int] = {}

    def zeilen(self, p: Path) -> int | None:
        if p not in self._zeilen:
            try:
                with open(p, "r", encoding="utf-8", errors="replace") as fh:
                    self._zeilen[p] = sum(1 for _ in fh)
            except OSError:
                self._zeilen[p] = -1
        n = self._zeilen[p]
        return None if n < 0 else n

    def kandidaten(self, datei: str):
        """`(pfad, hinweis)` - erst die Wuurzeln, dann die abgeschnittenen Pfade."""
        p = Path(datei)
        if p.is_absolute():
            yield p, ""
            return
        for w in self.wurzeln:
            yield w / datei, ""
        for z, label in self.zusatz:
            yield z / datei, f"Vorsatz '{label}' ergaenzt"

    def pruefen(self, datei: str, zeile: int | None) -> tuple[str, str]:
        """`(urteil, hinweis)` - urteil ist 'ok', 'zeile', 'datei' oder 'leer'."""
        if not datei:
            return "leer", "keine Stelle genannt"
        for k, hinweis in self.kandidaten(datei):
            if not k.is_file():
                continue
            zusatz = f" ({hinweis})" if hinweis else ""
            if zeile is None:
                return "ok", f"{k} (ohne Zeile){zusatz}"
            n = self.zeilen(k)
            if n is None or zeile > n:
                return "zeile", (f"{k} hat {n if n is not None else '?'} Zeilen, "
                                 f"Zeile {zeile} fehlt{zusatz}")
            return "ok", f"{k}{zusatz}"
        return "datei", f"{datei} nicht gefunden"


def belege_aus_bericht(p: Path) -> list[dict]:
    """Die `<BEFUND>`-Bloecke aus einem Schattenbericht (`tools/schatten_aussensicht.py`)."""
    text = read_text(p)
    if not text:
        raise SystemExit(f"kein Bericht: {p}")
    roh = text.split("## Antwort (roh)", 1)[-1]
    grenze = 7
    _s, befunde, verworfen, _pr = aussensicht.parse(roh, grenze)
    return list(befunde) + list(verworfen)


def belege_aus_meta(cfg, batch: int) -> list[dict]:
    """Die Befunde der ECHTEN Aussensicht - aus `runs/b<N>/meta.json` (maschinenlesbar)."""
    d = read_json(aussensicht.json_pfad(cfg, batch)) or {}
    return list(d.get("befunde") or []) + list(d.get("verworfen") or [])


def zaehlen(befunde: list[dict], w: Wuurzeln) -> dict:
    """Belegquote eines Arms zaehlen."""
    stellen: list[tuple[str, int | None]] = []
    ok = zeile = datei = leer = 0
    fehler: list[str] = []
    for b in befunde:
        s = stelle(str(b.get("beleg") or ""))
        if s is None:
            leer += 1
            fehler.append("ohne Stelle: " + str(b.get("beleg") or "")[:120])
            continue
        stellen.append(s)
        urteil, hinweis = w.pruefen(*s)
        if urteil == "ok":
            ok += 1
        elif urteil == "zeile":
            zeile += 1
            fehler.append(f"Zeile: {s[0]}:{s[1]} - {hinweis}")
        else:
            datei += 1
            fehler.append(f"Datei: {s[0]}:{s[1]} - {hinweis}")
    return {"n": len(befunde), "ok": ok, "zeile": zeile, "datei": datei, "leer": leer,
            "stellen": stellen, "eindeutig": len(set(stellen)), "fehler": fehler}


def zeile(name: str, z: dict, opus: set, arm: set) -> str:
    quote = f"{z['ok'] / z['n'] * 100:.0f} %" if z["n"] else "-"
    gemeinsam = len(arm & opus)
    return (f"| {name} | {z['n']} | {z['ok']} ({quote}) | {z['zeile']} | {z['datei']} "
            f"| {z['leer']} | {z['eindeutig']} | {gemeinsam} | {len(arm - opus)} "
            f"| {len(opus - arm)} |")


KOPF = ["| Arm | Befunde | Beleg ok | Zeile fehlt | Datei fehlt | ohne Stelle "
        "| versch. Stellen | mit Opus gemeinsam | nur hier | nur Opus |",
        "|---|---|---|---|---|---|---|---|---|---|"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--batch", type=int, action="append", required=True)
    ap.add_argument("--stufe", action="append", default=None,
                    help=f"mehrfach moeglich; Vorgabe {list(VORGABE_STUFEN)}")
    ap.add_argument("--stdout", action="store_true", help="nicht als Beleg schreiben")
    ap.add_argument("--zeigen", action="store_true",
                    help="die gebildeten Schluessel ausgeben (Rohzeilenprobe)")
    ap.add_argument("--config", default=None)
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    stufen = list(args.stufe or VORGABE_STUFEN)
    w = Wuurzeln(cfg)
    docs = Path(cfg.root).parent / "docs"
    zeilen = ["# Belegpruefung der Schatten-Aussensichten (tools/beleg_probe.py)", "",
              "- Geprueft wird NUR die Aufloesbarkeit der genannten Stelle (Datei da? "
              "Zeile im Bereich?), NICHT ob die Aussage stimmt.",
              "- Sauberer Vergleich ist **high gegen max** (gleicher Prompt); der "
              "Vergleich gegen Opus misst ueberwiegend den Eingabe-Unterschied "
              "(Schattenlauf baut die Eingaben aus dem Stand von heute, Paragraph 19a).",
              "", "## Stellen gegen high/max", "",
              "| Vergleich | gleiche Stelle | gleiche Datei | nur links | nur rechts |",
              "|---|---|---|---|---|", ""]
    gesamt: dict[tuple[str, str], dict] = {}
    arme: dict[str, dict] = {}
    for batch in args.batch:
        opus_z = zaehlen(belege_aus_meta(cfg, batch), w)
        opus_set = set(opus_z["stellen"])
        zeilen += [f"## Batch {batch}", "", *KOPF]
        print(f"\n=== Batch {batch} ===")
        for z in [opus_z]:
            print(zeile("Opus 5.5 (echt)", z, opus_set, opus_set))
        zeilen.append(zeile("Opus 5.5 (echt)", opus_z, opus_set, opus_set))
        if args.zeigen:
            for s in sorted(opus_set, key=str):
                print(f"    Opus      {s}")
        for stufe in stufen:
            p = docs / f"_ds_vergleich_b{batch}_{stufe}.md"
            if not p.is_file():
                print(f"  fehlt: {p.name}")
                continue
            arm_z = zaehlen(belege_aus_bericht(p), w)
            arm_set = set(arm_z["stellen"])
            arme[stufe] = arm_z
            text = zeile(f"DeepSeek {stufe}", arm_z, opus_set, arm_set)
            print(text)
            if args.zeigen:
                for s in sorted(arm_set, key=str):
                    print(f"    DS-{stufe:<5}{s}")
                for f in arm_z["fehler"]:
                    print(f"    !! DS-{stufe:<5}{f}")
            zeilen.append(text)
            gesamt[(stufe, str(batch))] = arm_z
        # R13bx: der SAUBERE Vergleich - high gegen max.  Beide Arme hatten denselben
        # Prompt (nur die Tiefenprobe angeheftet), nur die Denkstufe war anders.  Der
        # Vergleich gegen Opus misst dagegen ueberwiegend den EINGABE-Unterschied:
        # der Schattenlauf baut seine Eingaben aus dem Stand von HEUTE (Paragraph 19a,
        # "Grenze der Nachstellung"), nicht aus dem des nachgestellten Batches.
        if len(arme) > 1:
            namen = sorted(arme)
            for i in range(len(namen)):
                for j in range(i + 1, len(namen)):
                    a, b2 = namen[i], namen[j]
                    ka = {s[0] for s in arme[a]["stellen"]}
                    kb = {s[0] for s in arme[b2]["stellen"]}
                    ga = set(arme[a]["stellen"])
                    gb = set(arme[b2]["stellen"])
                    t = (f"| {a} gegen {b2} | {len(ga & gb)} | {len(ka & kb)} "
                         f"| {len(ga - gb)} | {len(gb - ga)} |")
                    print(t)
                    zeilen.append(t)
        arme.clear()
        zeilen.append("")
    # Summe ueber alle Batches je Stufe
    zeilen += ["## Summe je Stufe", "", *KOPF]
    print("\n=== Summe je Stufe ===")
    for stufe in stufen:
        teile = [gesamt[(stufe, str(b))] for b in args.batch
                 if (stufe, str(b)) in gesamt]
        if not teile:
            continue
        summe = {k: sum(t[k] for t in teile) for k in ("n", "ok", "zeile", "datei", "leer")}
        stellen: list = []
        for t in teile:
            stellen += t["stellen"]
        summe["eindeutig"] = len(set(stellen))
        text = zeile(f"DeepSeek {stufe} (Summe)", summe, set(), set())
        print(text)
        zeilen.append(text)
    if not args.stdout:
        ziel = docs / "_beleg_probe.txt"
        write_text_atomic(ziel, "\n".join(zeilen) + "\n")
        print(f"\nBeleg: {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
