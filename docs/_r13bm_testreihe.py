"""R13bm - die BETROFFENEN Testdateien einzeln fahren (Beleg).

Waehrend ein Batch laeuft, wird nur gefahren, was die Aenderungen beruehren; die
volle Reihe gehoert an das naechste Gate. Dieses Skript startet JEDE Datei als
eigenen Prozess (ein Fehlschlag in einer Datei kann so keine andere verdecken) und
schreibt je Datei eine Zeile nach `docs/_r13bm_testreihe.txt`.

    python docs/_r13bm_testreihe.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1] / "harness"
BELEG = Path(__file__).resolve().parent / "_r13bm_testreihe.txt"

# Die Dateien, die die fuenf Punkte beruehren (Schleife/Worker: 1+2, Limit: 3,
# Aussensicht: 4, Uhr/Limits: 5) - je Datei der Grund.
DATEIEN = [
    ("test_r13bm_fixes", "neu: alle fuenf Punkte"),
    ("test_r10_fixes", "Uhr/Kopfzeilen (P5)"),
    ("test_r11_fixes", "result.json + review-verworfen (P1/P3)"),
    ("test_r13_fixes", "Worker-Lauf im Mock (P2)"),
    ("test_r13ab_fixes", "result.json-Felder (P1)"),
    ("test_r13ac_fixes", "Batch-Uhr MAX_START_ALTER_S (P5)"),
    ("test_r13ac3_fixes", "Aussensicht-Lauf (P4)"),
    ("test_r13ad_fixes", "killed_reason/result.json (P1/P2)"),
    ("test_r13ae_fixes", "Preflight-Zeit/Bilanz (P1)"),
    ("test_r13ah_fixes", "Aussensicht-Marken (P4)"),
    ("test_r13aj_fixes", "Werkzeugdauer (P1)"),
    ("test_r13al_fixes", "Schleife/Peak-Warten (P2)"),
    ("test_r13ao_fixes", "Preflight-Zaehler (P1)"),
    ("test_r13aq_fixes", "Aussensicht gelaufen/gescheitert (P4)"),
    ("test_r13ar_fixes", "Zuglimit-Fruehwarnung (P4)"),
    ("test_r13as_fixes", "Faktenzeile (P1)"),
    ("test_r13au_fixes", "Status/Anzeige (P1)"),
    ("test_r13aw_fixes", "Antwortfassungen (P1)"),
    ("test_r13ax_fixes", "Abbruchgruende (P1/P2)"),
    ("test_r13b_fixes", "Review-Gueltigkeit/review-verworfen (P3)"),
    ("test_r13bb_fixes", "Abbruch ohne Review (P1/P2)"),
    ("test_r13bj_fixes", "Lauf-Ordner + Zeitgrenzen (P2/P5)"),
    ("test_r13bl_fixes", "Zeitgrenzen-Rueckbau (P3/P5)"),
    ("test_r13c_fixes", "Schleife/Freigabe (P2)"),
    ("test_r13e_fixes", "Limit-Wartezustand (P3)"),
    ("test_r13g_fixes", "Secret-Alarm (P3)"),
    ("test_r13h_fixes", "Laufzeit-Profil (P1)"),
    ("test_r13i_fixes", "Telegram-Meldungen (P2/P3)"),
    ("test_r13m_fixes", "Git-Halt der Schleife (P2)"),
    ("test_r13o_fixes", "Pfade/Ask (P1)"),
    ("test_r13p_fixes", "Grenzen/Alarme (P5)"),
    ("test_r13s_fixes", "Abbruchgruende (P1)"),
    ("test_r13u_fixes", "Schleife/Gate (P2)"),
    ("test_r13v_fixes", "WIP-Sicherung (P2)"),
    ("test_r13v3_fixes", "lauf<k>/ (P2/P3)"),
    ("test_r13w_fixes", "Aussensicht-Verdikte (P4)"),
    ("test_r13x_fixes", "Bilanz/result.json (P1)"),
]
# ACHTUNG: `unittest` schreibt die Zusammenfassung in die MITTE des Ausgabestroms -
# ohne `re.MULTILINE` trifft `^` nur den Stringanfang und die Zeile bleibt leer.
RE_LAUF = re.compile(r"^Ran (\d+) tests? in ([\d.]+)s", re.MULTILINE)
RE_OK = re.compile(r"^(OK|FAILED.*)", re.MULTILINE)


def head() -> str:
    """Kurz-Hash des Harness-HEAD - der Beleg nennt damit seinen Stand selbst."""
    try:
        p = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                           cwd=str(HARNESS.parent), capture_output=True, text=True)
        return (p.stdout or "").strip() or "UNBEKANNT"
    except OSError:
        return "UNBEKANNT"


def main() -> int:
    zeilen = []
    fehler = 0
    gesamt = 0
    for name, zweck in DATEIEN:
        p = subprocess.run([sys.executable, "-m", "unittest", f"tests.{name}"],
                           cwd=str(HARNESS), capture_output=True, text=True)
        roh = (p.stdout or "") + (p.stderr or "")
        lauf = RE_LAUF.search(roh)
        ok = RE_OK.search(roh)
        anzahl = int(lauf.group(1)) if lauf else 0
        dauer = float(lauf.group(2)) if lauf else 0.0
        ergebnis = (ok.group(1) if ok else "KEINE ZUSAMMENFASSUNG")
        gesamt += anzahl
        if not ergebnis.startswith("OK"):
            fehler += 1
        zeilen.append(f"{name:<22} {anzahl:>4} Tests {dauer:>7.1f}s  {ergebnis:<12} "
                      f"({zweck})")
        print(zeilen[-1], flush=True)
    kopf = [f"R13bm - betroffene Testdateien EINZELN ({len(DATEIEN)} Dateien)",
            f"HEAD beim Lauf: {head()} (Harness-Repo)",
            f"Ergebnis: {gesamt} Tests, {fehler} Datei(en) ohne OK", ""]
    BELEG.write_text("\n".join(kopf + zeilen) + "\n", encoding="utf-8")
    print("\n" + "\n".join(kopf) + f"\nBeleg: {BELEG}")
    return 1 if fehler else 0


if __name__ == "__main__":
    raise SystemExit(main())
