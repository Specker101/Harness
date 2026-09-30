"""R13bb: vier Harness-Punkte aus Aussensicht B224 / Review B225 - Beleg (nur lesend).

Punkt 2 (Befund M224-4): der Preflight-Zaehler des Harness verfehlte in B218, B223 und B224
je einen Lauf - genau die Fehllaeufe, die die Regel "ein gueltiger Preflight je Batch"
ueberwacht. Geprueft wird der Zaehler jetzt gegen die archivierten Dateien
`analysis/_m<N>/_preflight_<N>_fehllauf*.txt` und `*_ueberholt*.txt`; die Differenz steht in
`result.json` und in den Review-Fakten. Der Rueckblick fuer die drei Batches steht unten.

Aufruf: python -u docs/_r13bb_belege.py            (gibt aus)
        python -u docs/_r13bb_belege.py schreiben  (schreibt docs/_r13bb_belege.txt)
"""

from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
HARNESS = HIER.parent / "harness"
sys.path.insert(0, str(HARNESS))

from hx import stand                                           # noqa: E402
from hx.config import load_config                              # noqa: E402

ZIEL = HIER / "_r13bb_belege.txt"
RUECKBLICK = (218, 223, 224)


def bericht() -> None:
    cfg = load_config()
    print("R13bb: vier Harness-Punkte (Aussensicht B224 / Review B225) - Beleg")
    print(f"Decomp-Repo: {cfg.decomp}")
    print()
    print("2) PREFLIGHT-ZAEHLER gegen die archivierten Laeufe (Befund M224-4)")
    print("   Batch | Aufrufe im Mitschnitt | Fehllaeufe im Archiv | Laeufe gesamt | "
          "ueberholt")
    for b in RUECKBLICK:
        aufrufe, frueh = stand.zaehle_preflight_aufrufe(cfg, b)
        a = stand.preflight_archiv(cfg, b)
        print(f"   {b:>5} | {aufrufe:>20} | {a['ungezaehlt']:>20} | "
              f"{aufrufe + a['ungezaehlt']:>13} | {len(a['ueberholt'])}")
    print()
    print("   Die Fehllauf-Dateien:")
    for b in RUECKBLICK:
        for rel in stand.preflight_archiv(cfg, b)["fehllauf"]:
            print(f"     {rel}")
    print()
    print("   Die Review-Fakten-Zeilen dieses Rueckblicks (Wortlaut):")
    for b in RUECKBLICK:
        print(f"     B{b}: " + stand.preflight_zaehler_zeile(cfg, b)[0])
    print()
    print("   Gegenprobe (Batches ohne Fund):")
    for b in (215, 220):
        print(f"     B{b}: " + stand.preflight_zaehler_zeile(cfg, b)[0])
    print()
    print("3) MISCHREGEL DER PROGNOSE (Befund M224-5)")
    p = stand.plan_mischung(cfg)
    print(f"   geltende Regel : {p['regel']!r}  Anteil {p['anteil']:.3f}  "
          f"({p['datei']}:{p['zeile_nr']}, Zustand {p['zustand']})")
    print(f"   Stand          : {p['stand']}")
    print(f"   Zeile          : {p['zeile']}")
    print(f"   Kandidaten     : {p['kandidaten']}  Paare {p['paare']}")
    # Wie in `stand.durchsatz_zeilen`: die Rate des Medians einsetzen (R13ba).
    raten = stand.c_rate(cfg)
    d = dict(stand.durchsatz(cfg), rate_c_koepfe=raten["rate"],
             rate_c_quelle=raten["quelle"])
    print(f"   Quelle in der Prognosezeile: {d.get('anteil_quelle')}")
    alt = dict(d, anteil_c=1 / 3,
               anteil_quelle='Regel hybrid-plan.md "2 B : 1 C" (ueberholt)')
    offen = d.get("offen_koepfe") or 0
    for name, dd in (("VORHER 2:1 (Anteil 33 %)", alt), ("NACHHER geltend", d)):
        zeilen = stand.kalender_zeilen(cfg, offen, dd)
        print(f"   {name:26}: " + (zeilen[0].strip() if zeilen else "(keine)"))
        for z in zeilen[1:]:
            print(f"   {'':26}  " + z.strip())
    print(f"   offener Paket-E-Vorrat: {offen} Koepfe; Rate {d.get('rate_c_koepfe')} "
          f"(Median der Kopf-Batches)")


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
