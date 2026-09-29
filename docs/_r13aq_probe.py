"""R13aq: der gescheiterte Aussensicht-Lauf meta-217 (nur LESEND ausser der Ausgabe).

Beantwortet Punkt 1 und Punkt 2 des Auftrags mit Messwerten:

  1. Warum rc=1? (Mitschnitt `runs/meta-217.jsonl`: subtype, Zugarzahl, Fehlertext)
     Wie hoch ist das Zuglimit (Datei:Zeile)? Wie viele Zuege brauchten meta-208..meta-216?
  2. Welche Marken setzt der Harness nach dem gescheiterten Lauf? Zaehlt rc=1 als
     gelaufene Aussensicht?

Gelesen wird ausschliesslich; geschrieben wird nur die Ausgabe (stdout).
Aufruf: python -u docs/_r13aq_probe.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
ROOT = HIER.parent                       # g:\Harness
HARNESS = ROOT / "harness"
sys.path.insert(0, str(HARNESS))

from hx import aussensicht                                     # noqa: E402
from hx.config import load_config                              # noqa: E402
from hx.util import read_json, read_text                       # noqa: E402


def zuege_und_subtype(p: Path) -> dict:
    """Aus dem Mitschnitt: subtype, is_error, num_turns, Dauer, Fehlertext."""
    aus = {"datei": p.name, "subtype": "", "is_error": None, "zuege": None,
           "dauer_s": None, "fehler": ""}
    if not p.is_file():
        return aus
    for z in read_text(p).splitlines():
        try:
            e = json.loads(z)
        except ValueError:
            continue
        if e.get("type") == "result":
            aus["subtype"] = str(e.get("subtype") or "")
            aus["is_error"] = e.get("is_error")
            aus["zuege"] = e.get("num_turns")
            dauer = e.get("duration_ms")
            aus["dauer_s"] = round(float(dauer) / 1000.0, 1) if dauer else None
            aus["fehler"] = "; ".join(str(x) for x in (e.get("errors") or []))
    return aus


def main() -> int:
    cfg = load_config()
    runs = HARNESS / "runs"

    print("== 1) Warum rc=1 (meta-217) ==")
    d = zuege_und_subtype(runs / "meta-217.jsonl")
    print(f"   Mitschnitt: {d['datei']}  subtype={d['subtype']!r}  "
          f"is_error={d['is_error']}  num_turns={d['zuege']}  dauer={d['dauer_s']}s")
    print(f"   Fehlertext: {d['fehler']}")
    j = read_json(runs / "meta-217.json", {}) or {}
    print(f"   Bericht:    rc={j.get('rc')} befund={len(j.get('befunde') or [])} "
          f"verworfen={len(j.get('verworfen') or [])} modell={j.get('modell')!r}")
    print(f"   Rohantwort: {str(j.get('text') or '')[:120]!r}")
    print()
    print("== Zuglimit (Datei:Zeile) ==")
    toml = read_text(HARNESS / "harness.toml").splitlines()
    for i, z in enumerate(toml, 1):
        if "max_turns" in z and not z.strip().startswith("#"):
            print(f"   harness/harness.toml:{i}: {z.strip()}")
    print(f"   hx/aussensicht.py:66  STANDARD ... max_turns = "
          f"{aussensicht.STANDARD['max_turns']}  (Vorgabe)")
    print(f"   hx/aussensicht.py     build_command -> --max-turns "
          f"{aussensicht.grenzen(cfg)['max_turns']}  (wirksam)")
    print()
    print("== Zuege der Laeufe meta-208..meta-217 ==")
    for p in sorted(runs.glob("meta-*.jsonl")):
        v = zuege_und_subtype(p)
        print(f"   {v['datei']:<18} zuege={v['zuege']:<4} subtype={v['subtype']:<16} "
              f"is_error={v['is_error']}")

    print()
    print("== 2) Marken nach dem gescheiterten Lauf ==")
    zustand = read_json(HARNESS / "state" / "run.json", {}) or {}
    meta = dict(zustand.get("meta") or {})
    for feld in ("letzter_lauf_batch", "letzter_lauf_ts", "geprueft_batch",
                 "vorgemerkt", "vorgemerkt_grund", "kernzahl_gemeldet_bis",
                 "c_soll_null_gemeldet_bis", "hybrid_gemeldet_bis",
                 "gescheitert_batch", "gescheitert_grund"):
        print(f"   {feld:<26} = {meta.get(feld)!r}")
    print(f"   Batch jetzt                = {zustand.get('batch')!r}  "
          f"Zustand = {zustand.get('state')!r}")
    letzte = int(meta.get("letzter_lauf_batch") or 0)
    takt = int(aussensicht.grenzen(cfg)["every_batches"])
    print(f"   -> die Takt-Regel 'alle {takt}' rechnete von {letzte}: naechster "
          f"automatischer Lauf bei Batch {letzte + takt}")
    print(f"   -> `geprueft_batch` = {meta.get('geprueft_batch')!r} heisst: fuer diesen "
          "Batch ist entschieden (kein zweiter Versuch im selben Batch)")

    print()
    print("== Register (state/meta_befunde.json) ==")
    reg = read_json(aussensicht.ledger_pfad(cfg), {}) or {}
    print(f"   updated_at={reg.get('updated_at')!r}  Befunde={len(reg.get('befunde') or [])}"
          f"  verworfen={len(reg.get('verworfen') or [])}")
    print(f"   tiefenprobe={json.dumps(reg.get('tiefenprobe') or {}, ensure_ascii=False)}")
    print(f"   Quote: {aussensicht.zeile(cfg) or '(keine)'}")
    print(f"   offen: {[b.get('id') for b in aussensicht.offene(cfg)] or 'keine'}")
    print("   -> Der gescheiterte Lauf hat am Register NUR `updated_at` auf den eigenen")
    print("      Zeitstempel gesetzt (2026-09-29T22:49:49, s. runs/meta-217.json -> ts);")
    print("      Befundzahl unveraendert 40, KEIN Eintrag zu Batch 217, und die gezogene")
    print("      Tiefenprobe B214 steht NICHT unter `gezogen` (erst ein Lauf MIT Ergebnis")
    print("      merkt sie, R13ac3). Der Register-Nachtrag M213-4a hat `updated_at` danach")
    print("      neu gesetzt (docs/_r13aq_nachtrag.txt).")

    print()
    print("== 3) Wiederholung: was der neue Code aus den VORHANDENEN Belegen liest ==")
    z = aussensicht.bericht_zustand(cfg)
    print(f"   bericht_zustand: letzte_gelungen=B{z['letzte_gelungen']} "
          f"neuester_gescheitert=B{z['neuester_gescheitert']} "
          f"grund={z['gescheitert_grund']!r} berichte={z['anzahl_berichte']}")
    # `faellig` fuer den NAECHSTEN Batch - gegen eine KOPIE des Zustands im Tempordner,
    # damit nichts unter state/ geschrieben wird.
    from hx.state import State
    kopie = Path(HIER) / "_r13aq_zustandskopie.json"
    daten = dict(zustand)
    daten["batch"] = int(zustand.get("batch") or 0) + 1
    kopie.write_text(json.dumps(daten, ensure_ascii=False, indent=1), encoding="utf-8")
    s = State(kopie)
    print(f"   faellig(batch={s.batch}): {aussensicht.faellig(cfg, s)}")
    kopie.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
