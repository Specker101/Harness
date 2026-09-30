"""R13bc: der eingefrorene Stand `tests/fixtures/stand_b224` - Messwerte (nur lesend).

Zweck: die Zahlen, die die Tests der Runden R13ay/R13ba/R13bb gegen diesen Stand behaupten,
aus der Fixture selbst ausgeben. Vorher lasen diese Tests die **lebenden** Dateien im
Decomp-Repo (`analysis/_m<N>/…`, `analysis/_preflight_<N>.txt`, `analysis/hybrid-plan.md`)
und im Harness-`runs/`; sobald der laufende Batch etwas schrieb, wurden sie rot und
schalteten sich per `skipTest` ab. Jetzt ist der Stand fest, und jede Erwartung im Test ist
eine Aussage ueber genau diese Dateien.

Aufruf: python -u docs/_r13bc_fixture.py            (gibt aus)
        python -u docs/_r13bc_fixture.py schreiben  (schreibt docs/_r13bc_fixture.txt)
"""

from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
HARNESS = HIER.parent / "harness"
sys.path.insert(0, str(HARNESS))

from hx import bilanz, stand                                   # noqa: E402
from hx.config import load_config                              # noqa: E402
from hx.util import read_text_erkannt                          # noqa: E402

FIXTURE = HARNESS / "tests" / "fixtures" / "stand_b224"
ZIEL = HIER / "_r13bc_fixture.txt"


def cfg_aus_fixture():
    """Konfiguration, die direkt auf die Fixture zeigt (nur lesende Zugriffe)."""
    cfg = load_config()
    cfg.data["paths"]["root"] = str(FIXTURE / "root")
    cfg.data["paths"]["decomp"] = str(FIXTURE / "decomp")
    cfg.data["paths"]["harness_home"] = str(FIXTURE)
    return cfg


def bericht() -> None:
    cfg = cfg_aus_fixture()
    print("R13bc: eingefrorener Stand tests/fixtures/stand_b224 - Messwerte")
    print(f"Fixture: {FIXTURE.as_posix()}")
    dateien = sorted(p for p in FIXTURE.rglob("*") if p.is_file())
    print(f"Dateien: {len(dateien)} ({sum(p.stat().st_size for p in dateien) / 1024:.0f} KB)")
    print()
    print("1) Paket-E-Messung (stand.paket_e_messung)")
    m = stand.paket_e_messung(cfg)
    print(f"   gewaehlt: {m['datei']}  B{m['batch']}  {m['koepfe']} Koepfe / {m['insn']} Insn"
          f"  stand={m['stand']!r}  kodierung={m['kodierung']}")
    print(f"   Datum: {m['datum']!r} (Quelle {m['datum_quelle']})")
    vor = m.get("vorher") or {}
    print(f"   vorher (anderer Wert): {vor.get('datei')}  B{vor.get('batch')}  "
          f"{vor.get('koepfe')} Koepfe -> Delta {vor.get('koepfe', 0) - m['koepfe']:+d} Koepfe / "
          f"{vor.get('insn', 0) - m['insn']:+d} Insn")
    print(f"   gleicher Wert im selben Batch: {(m.get('vorher_gleich') or {}).get('datei')}")
    print(f"   PARSER-Meldung: {stand.paket_e_datum_hinweis(cfg) or 'keine'}")
    for zeile in bilanz.gesamt_block(cfg):
        if "Paket E offen" in zeile:
            print("   " + zeile.strip()[:190])
    print()
    print("2) Rate je C-Batch (stand.c_rate, Fenster 5)")
    r = stand.c_rate(cfg)
    print(f"   Median {r['median']}  Mittel {r['mittel']}  gerechnet {r['rate']}")
    print(f"   Kopf-Batches: {r['kopf_batches']}")
    print(f"   Zeile: {r['text']}")
    print(f"   Quelle: {r['quelle']}")
    print("   PLAN/IST-Tafel (n=12, groesseres Fenster - daher Median 5):")
    for zeile in stand.plan_ist_text(cfg, 12).splitlines()[-2:]:
        print("     " + zeile.strip()[:170])
    print("   Durchsatzzeilen (Auszug):")
    for zeile in stand.durchsatz_zeilen(cfg):
        if "C-Rate" in zeile or "bei +" in zeile or "offen (Paket E" in zeile:
            print("     " + zeile.strip()[:170])
    print()
    print("3) Mischregel (stand.plan_mischung)")
    p = stand.plan_mischung(cfg)
    print(f"   Regel {p['regel']!r}  Anteil {p['anteil']}  Zustand {p['zustand']}  "
          f"({p['datei']}:{p['zeile_nr']})")
    print(f"   Stand: {p['stand']}   Paare: {p['paare']}   Kandidaten: {p['kandidaten']}")
    print(f"   Zeile: {p['zeile'][:130]}")
    print(f"   Prognosequelle: {stand.durchsatz(cfg)['anteil_quelle']}")
    print()
    print("4) Preflight-Zaehler gegen das Archiv (M224-4)")
    for b in (218, 223, 224):
        print("   B" + str(b) + ": " + stand.preflight_zaehler_zeile(cfg, b)[0])
    print()
    print("5) Kodierungen der Messdateien (Byte-Kopien, deshalb erhalten)")
    for p2 in sorted((FIXTURE / "decomp" / "analysis").glob("_m*/_c_paket_e*.txt")):
        text, kod = read_text_erkannt(p2)
        datum = "Datum erkannt" if any(mu.search(text) for mu in stand.RE_PAKET_E_DATUM) \
            else "kein Datum im Kopf"
        print(f"   {p2.relative_to(FIXTURE).as_posix():48} {kod:12} {datum}")


def main() -> int:
    if "schreiben" in sys.argv:
        puffer = io.StringIO()
        with contextlib.redirect_stdout(puffer):
            bericht()
        text = puffer.getvalue()
        ZIEL.write_text(text, encoding="utf-8", newline="\n")
        print(f"geschrieben: {ZIEL.name} ({len(text)} Zeichen, UTF-8)")
        return 0
    bericht()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
