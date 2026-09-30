"""Nebenpruefung R13bc: kommt die Fixture nach einem frischen Checkout byte-true an?

Vergleicht Blobs aus `git checkout-index` (frischer Auscheck-Vorgang, wendet die
Attribute an) mit der Arbeitskopie. Belegt, dass `harness/tests/fixtures/** -text`
das BOM und die UTF-16-Dateien unveraendert laesst.
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import subprocess
import sys

REPO = pathlib.Path(r"g:\Harness")
WURZEL = "harness/tests/fixtures/stand_b224"
DATEIEN = [
    "decomp/analysis/_m224/_c_paket_e_nachher.txt",   # UTF-8-BOM
    "decomp/analysis/_m224/_c_paket_e.txt",           # UTF-8 ohne BOM
    "decomp/analysis/_preflight_216.txt",             # UTF-16 LE mit BOM
    "decomp/analysis/_preflight_224.txt",             # UTF-8-BOM
    "decomp/analysis/hybrid-plan.md",                 # CRLF
    "root/runs/b224/preflight-aufrufe.jsonl",
]


def main() -> int:
    co = pathlib.Path(os.environ["TEMP"]) / "_r13bc_co"
    if co.exists():
        for p in sorted(co.rglob("*"), reverse=True):
            p.rmdir() if p.is_dir() else p.unlink()
    co.mkdir(parents=True, exist_ok=True)
    args = ["git", "checkout-index", "-f", "--prefix=" + str(co) + os.sep, "--"]
    args += [f"{WURZEL}/{d}" for d in DATEIEN]
    r = subprocess.run(args, cwd=REPO, capture_output=True)
    if r.returncode:
        print("checkout-index fehlgeschlagen:", r.stderr.decode("utf-8", "replace"))
        return 1
    zeilen, gleich = [], 0
    for d in DATEIEN:
        a = (co / WURZEL / d).read_bytes()
        b = (REPO / WURZEL / d).read_bytes()
        ok = a == b
        gleich += ok
        zeilen.append(f"{d:44} {len(a):>6} B  erste Bytes {a[:4].hex(' ')}  "
                      f"sha {hashlib.sha256(a).hexdigest()[:12]}  identisch={ok}")
    for z in zeilen:
        print(z)
    print(f"\n{gleich} von {len(DATEIEN)} Dateien byte-true nach frischem Checkout")
    (pathlib.Path(__file__).resolve().parent / "_r13bc_checkout.txt").write_text(
        "\n".join(zeilen) + f"\n\n{gleich} von {len(DATEIEN)} Dateien byte-true nach frischem Checkout\n",
        encoding="utf-8", newline="\n")
    return 0 if gleich == len(DATEIEN) else 1


if __name__ == "__main__":
    sys.exit(main())
