"""R13bd: EIN Einzelfall der Leerlaufprobe mit voller Ausgabe (Werkzeug fuer die Handpruefung).

Die Uebersicht (`_r13bd_leerlauf.py`) fasst jeden Modus zu einer Zeile zusammen. Wenn dort
"rot (errors=1)" steht, ist nicht zu sehen, WER geworfen hat. Dieses Skript faehrt genau einen
Test in genau einem Modus und zeigt die ganze Ausgabe.

Aufruf: python -u docs/_r13bd_einzelfall.py <modus> <modul> <Klasse> <test>
Beispiel: python -u docs/_r13bd_einzelfall.py E-format-geaendert test_r13ac_fixes \\
              TestTrendMitEchtenDateien test_die_kopie_stimmt_mit_dem_lebenden_repo
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
HARNESS = HIER.parent / "harness"
TESTS = HARNESS / "tests"
sys.path.insert(0, str(HIER))

from _r13bd_leerlauf import VORSPANN                                  # noqa: E402


def main() -> int:
    if len(sys.argv) != 5:
        print(__doc__)
        return 2
    modus, modul, klasse, test = sys.argv[1:5]
    kratz = HARNESS / "tests" / "_tmp_r13bd"
    kratz.mkdir(parents=True, exist_ok=True)
    leer = kratz / "leer.txt"
    leer.write_text("", encoding="utf-8", newline="\n")
    vor = VORSPANN.replace("__MODUS__", modus).replace("__LEERDATEI__", str(leer))
    code = (
        "import sys, unittest\n"
        f"sys.path.insert(0, r'{HARNESS}')\n"
        f"sys.path.insert(0, r'{TESTS}')\n"
        + vor
        + f"\nimport {modul} as m\n"
        f"s = unittest.TestLoader().loadTestsFromName('{klasse}.{test}', m)\n"
        "unittest.TextTestRunner(verbosity=2).run(s)\n"
    )
    p = subprocess.run([sys.executable, "-u", "-c", code], cwd=str(HARNESS),
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=420)
    print(p.stdout or "")
    if p.stderr:
        print("=== stderr ===")
        print(p.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
