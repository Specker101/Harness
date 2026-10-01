"""R13bf: Blob-Bytes im Git-Index pruefen (nicht ueber die Konsole - die schreibt UTF-16).

Aufruf:  python -u docs/_r13bf_blob.py <pfad-im-index> [...]
"""
from __future__ import annotations

import subprocess
import sys

REPO = "g:/Harness"


def main() -> int:
    pfade = sys.argv[1:] or [
        "harness/tests/fixtures/stand_b234_luecke/decomp/analysis/_preflight_233.txt"]
    for p in pfade:
        roh = subprocess.run(["git", "-C", REPO, "show", f":{p}"],
                             capture_output=True).stdout
        print(f"{p}\n  Groesse={len(roh)} erste4={list(roh[:4])} "
              f"CR={roh.count(13)} LF={roh.count(10)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
