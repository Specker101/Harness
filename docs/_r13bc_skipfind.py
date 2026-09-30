"""R13bc-Nebenpruefung: welcher Test hat sich in der vollen Reihe abgeschaltet?

Die Reihe meldet `OK (skipped=1)`; bei `verbosity=1` nennt unittest den Namen nicht.
Dieses Skript faehrt nur die Testdateien, die ueberhaupt eine `skipTest`/`skipIf`-Stelle
haben, einzeln mit `verbosity=2` und sammelt die Zeilen mit `skipped`.

Aufruf: python -u docs/_r13bc_skipfind.py
Schreibt: docs/_r13bc_skipfind.txt
"""

from __future__ import annotations

import io
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HIER = Path(__file__).resolve().parent
HARNESS = HIER.parent / "harness"
ZIEL = HIER / "_r13bc_skipfind.txt"

KANDIDATEN = [
    "test_r11_fixes.py", "test_r13aa_fixes.py", "test_r13ac_fixes.py",
    "test_r13ad_fixes.py", "test_r13ae_fixes.py", "test_r13af_fixes.py",
    "test_r13ah_fixes.py", "test_r13aj_fixes.py", "test_r13ak_fixes.py",
    "test_r13an_fixes.py", "test_r13ap_fixes.py", "test_r13aq_fixes.py",
    "test_r13ar_fixes.py", "test_r13az_fixes.py", "test_r13d_fixes.py",
    "test_r13e_fixes.py", "test_r13i_fixes.py", "test_r13v3_fixes.py",
    "test_r13x_fixes.py",
]

SKIP_RE = re.compile(r"\.\.\. skipped\s+(.*)$")


def main() -> int:
    zeilen = [f"Nebenpruefung zum Lauf docs/_r13bc_volle_reihe.txt "
              f"({time.strftime('%Y-%m-%d %H:%M:%S')})",
              f"Kandidaten: {len(KANDIDATEN)} Testdateien mit skip-Stelle", ""]
    treffer = 0
    for name in KANDIDATEN:
        puffer = io.StringIO()
        r = subprocess.run([sys.executable, "-u", "-m", "unittest", "discover",
                            "-s", "tests", "-p", name, "-v"],
                           cwd=str(HARNESS), capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        text = (r.stdout or "") + (r.stderr or "")
        for z in text.splitlines():
            m = SKIP_RE.search(z)
            if m:
                treffer += 1
                zeilen.append(f"{name}: {z.strip()}")
        letzte = [z for z in text.splitlines() if z.startswith(("OK", "FAILED"))]
        zeilen.append(f"  {name:26} rc={r.returncode}  {letzte[-1] if letzte else '(kein Ergebnis)'}")
    zeilen += ["", f"Gefundene Skips: {treffer}"]
    text_out = "\n".join(zeilen) + "\n"
    ZIEL.write_text(text_out, encoding="utf-8", newline="\n")
    for z in zeilen:
        print(z)
    return 0


if __name__ == "__main__":
    os.chdir(HARNESS)
    raise SystemExit(main())
