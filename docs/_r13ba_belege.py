"""R13ba: eine Rate "Koepfe je C-Batch" - beide Grundmengen, Median ist die Rechengrundlage.

Anlass (Aussensicht **M221-5**, Frage aus dem Review B222): dieselbe Eingabe nannte fuer
denselben Restvorrat (26 Koepfe) zwei Raten mit verschiedener Grundmenge - die PLAN/IST-Tafel
den **Median** ueber die C-Batches mit `SOLL-KOEPFE > 0` (6), die Durchsatzzeile der BILANZ
das **Mittel** ueber alle C-Batches (3.0). Das ergab "9 C-Batches" gegen "etwa 5".

Gemessen wird hier (nur lesend, das Decomp-Repo):
  1. beide Raten mit ihren Grundmengen (`stand.c_rate`),
  2. die Hochrechnung VORHER (Mittel, so rechnete der Harness) und NACHHER (Median),
  3. die echten Zeilen des Durchsatz-Blocks und der PLAN/IST-Tafel.

Aufruf: python -u docs/_r13ba_belege.py            (gibt aus)
        python -u docs/_r13ba_belege.py schreiben  (schreibt docs/_r13ba_belege.txt)
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

ZIEL = HIER / "_r13ba_belege.txt"


def bericht() -> None:
    cfg = load_config()
    r = stand.c_rate(cfg)
    d = stand.durchsatz(cfg)
    print("R13ba: die Rate 'Koepfe je C-Batch' - zwei Grundmengen, Median gerechnet")
    print(f"Decomp-Repo: {cfg.decomp}")
    print()
    print("1) Die Rate (stand.c_rate)")
    print(f"  Median (Kopf-Batches)      : {r['median']}")
    print(f"  Mittel (alle C-Batches)    : {r['mittel']}")
    print(f"  gerechnet wird mit         : {r['rate']}  ({r['quelle']})")
    print(f"  Zeile                      : {r['text']}")
    print(f"  Kopf-Batches (Batch, Zuwachs): {r['kopf_batches']}")
    print("  C-Batch-Schritte der Preflight-Reihe (Delta je Schritt): "
          + ", ".join(f"{s['delta']:+d}" for s in r["c_schritte"]))
    print()
    print("2) Die Hochrechnung fuer Paket E: vorher (Mittel) und jetzt (Median)")
    offen = d.get("offen_koepfe")
    basis = {"c_fenster": d.get("c_fenster") or [], "anteil_c": d.get("anteil_c"),
             "anteil_quelle": d.get("anteil_quelle") or ""}
    vorher = dict(basis, mittel_c_koepfe=r["mittel"],
                  mittel_c_quelle="Mittel ueber alle C-Batches (die alte Rechengrundlage)")
    nachher = dict(basis, rate_c_koepfe=r["rate"], rate_c_quelle=r["quelle"])
    print(f"  offener Paket-E-Vorrat: {offen} Koepfe (aus der Messung, s. Durchsatzzeile)")
    for name, dd in (("VORHER (Mittel)", vorher), ("NACHHER (Median)", nachher)):
        zeilen = stand.kalender_zeilen(cfg, offen or 0, dd)
        print(f"  {name}: " + (zeilen[0].strip() if zeilen else "(keine Hochrechnung)"))
    print()
    print("3) Der echte Durchsatz-Block (stand.durchsatz_zeilen) - die neuen Zeilen")
    for zeile in stand.durchsatz_zeilen(cfg):
        if ("C-Rate" in zeile or "HYPOTHESIS (Paket E" in zeile
                or "Grundlage: Median" in zeile or "offen (Paket E" in zeile
                or "C-Batches im R207-Fenster" in zeile or "nicht gebaut" in zeile):
            print(zeile)
    print()
    print("4) Die PLAN/IST-Tafel (stand.plan_ist_text) - die letzten Zeilen")
    for zeile in stand.plan_ist_text(cfg).splitlines()[-2:]:
        print("  " + zeile)
    print()
    print("5) Wo die Rate ueberall gerechnet wird (Verbraucher des Medians)")
    for name, wo in (("Paket-E-Hochrechnung", "stand.kalender_zeilen (durchsatz_zeilen)"),
                     ("C-gesamt-Hochrechnung", "stand._c_gesamt_zeilen"),
                     ("Klasse 'nicht ausgefuehrt'", "stand._relevanz_zeilen"),
                     ("PLAN/IST-Tafel", "stand.plan_ist_text (MEDIAN-Zeile)"),
                     ("BILANZ (GESAMT)", "bilanz.gesamt_block -> stand.durchsatz_zeilen")):
        print(f"  {name:<26} {wo}")
    print()
    print("6) Die BILANZ-Zeilen mit der Rate (bilanz.gesamt_block)")
    for zeile in bilanz.gesamt_block(cfg):
        if "C-Rate" in zeile or "bei +" in zeile:
            print("  " + zeile.strip())
    print()
    print("7) NACHTRAG - Auswahl der Messdatei (Befund aus R13ba, behoben)")
    m = stand.paket_e_messung(cfg)
    vor = m.get("vorher") or {}
    print(f"  gewaehlt            : {m['datei']}  (B{m['batch']}, {m['koepfe']} Koepfe / "
          f"{m['insn']} Insn, Dateiname-Rang stand={m['stand'] or 'bloss'!r})")
    print(f"  Datum               : {m['datum']!r}  Quelle {m['datum_quelle']}"
          + ("  -> Anzeige '(Datum aus Dateizeit)'" if m["datum_quelle"] == "dateizeit" else ""))
    print(f"  Vorher (anderer Wert): {vor.get('datei')}  (B{vor.get('batch')}, "
          f"{vor.get('koepfe')} Koepfe)  -> Paar B{vor.get('batch')} -> B{m['batch']}")
    print(f"  gleicher Wert im selben Batch: {(m.get('vorher_gleich') or {}).get('datei')}")
    for zeile in bilanz.gesamt_block(cfg):
        if "Paket E offen" in zeile:
            print("  " + zeile.strip())
    hinweis = stand.paket_e_datum_hinweis(cfg)
    print("  Review-Fakten       : " + (hinweis[0] if hinweis else "(kein PARSER-Hinweis)"))
    print("  Auswahlsregel       : Batchnummer aus dem Ordnernamen zuerst, dann 'nachher'")
    print("                        vor der blossen Messung vor 'vorher'; das Datum ist")
    print("                        Anzeige und Gleichstand-Entscheider, nie Hauptkriterium.")


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
