"""R13bi: dieselben zwei Aufrufe wie in `_r13bi_ram.py`, aber MIT Ausgabe.

Nur zum Nachsehen, warum die Laeufe so kurz waren: stdout/stderr werden in
`%TEMP%` gelegt (nicht ins Repo) und mitgedruckt.
"""
from __future__ import annotations

import pathlib
import subprocess
import tempfile
import time

DEC = pathlib.Path("g:/Silent Scope Decomp")
TMP = pathlib.Path(tempfile.gettempdir()) / "r13bi"
TMP.mkdir(exist_ok=True)
ROM = DEC / "rom" / "build" / "830d01.27p.be.bin"
C_KOPF = DEC / "port" / "build" / "c_kopf.exe"
HYBRID = DEC / "port" / "build" / "hybrid_lauf.exe"
PROFILE = DEC / "analysis" / "_m197" / "_ck_09DE0.case"

AUFRUFE = [
    ("c_kopf.exe (1 Kopf)", [str(C_KOPF), str(ROM), str(PROFILE)]),
    ("hybrid 2M", [str(HYBRID), "--schritte", "2000000"]),
    ("hybrid 20M", [str(HYBRID), "--schritte", "20000000"]),
]

for name, argv in AUFRUFE:
    t0 = time.time()
    r = subprocess.run(argv, cwd=str(DEC), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=900)
    dauer = time.time() - t0
    z = [f"### {name}  rc={r.returncode}  {dauer:.1f} s  argv={' '.join(argv[1:])}",
         "--- stdout ---", (r.stdout or "").strip(), "--- stderr ---",
         (r.stderr or "").strip(), ""]
    text = "\n".join(z)
    print(text)
    (TMP / (name.replace(" ", "_").replace("(", "").replace(")", "") + ".txt")
     ).write_text(text, encoding="utf-8", newline="\n")
print(f"Ausgaben liegen in {TMP}")
