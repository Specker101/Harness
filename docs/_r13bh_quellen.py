"""R13bh (nur lesend): Schreibziele und Unterprozesse der Preflight-MODULE.

Zweiter Anlauf: der erste Versuch suchte nur `EV.target/_out` - die Module schreiben
aber unterschiedlich (`_schreib(name, ...)`, `EV.target(...)`, `io.open(os.path.join(
WS, "analysis", EV, name), "w")`). Dieses Werkzeug sammelt je Modul:

  * jede Zeile mit einem Schreibzugriff (`_schreib(`/`"w"`/`EV.target(`/`EV.write(`),
  * jede Zeile, die einen Unterprozess startet (`subprocess.run/Popen`, `LAUF_EXE`,
    `port_selftest`, `port_gl`, `port_build`, `mingw32-make`, `c_kopf.py`),
  * jede Zeile, die einen Beleg eines ANDEREN Moduls liest (`analysis/_m...`).

    python -u docs/_r13bh_quellen.py [modul ...]   -> docs/_r13bh_quellen.txt
"""
from __future__ import annotations

import pathlib
import re
import sys

HARNESS = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = pathlib.Path("g:/Silent Scope Decomp/scripts")
MODULE = ["m104_built", "m115_pass", "m116_pass", "m114_pass", "m130_ast",
          "m5_kopf_check", "c_kopf_check", "m200_einbindung", "m210_bahnabdeckung",
          "m210_r391", "m227_profile_live", "m212_zeilen", "m214_archiv",
          "m233_binary", "port_regression"]
SCHREIB = re.compile(r'_schreib\(|EV\.target\(|EV\.write\(|_out\(|"w"\)|,\s*"w"|'
                     r'"wt"|open\([^)]*"w"')
START = re.compile(r"subprocess\.(?:run|Popen|check_output)|LAUF_EXE|hybrid_lauf|"
                   r"port_selftest|port_gl|port_build|mingw32-make|make\b|c_kopf\.py|"
                   r"ppc_poc|m193|m227_profile_live")
LIEST = re.compile(r'analysis[\\/]_m\d+[\\/][A-Za-z0-9_.]+|_m\d+[\\/]_[a-z0-9_]+\.txt')
NAMEN = re.compile(r'["\']([A-Za-z0-9_./-]*\.(?:txt|csv|json|ppm|py|exe|md))["\']')


def main() -> int:
    module = sys.argv[1:] or MODULE
    z: list[str] = []
    for mod in module:
        p = SCRIPTS / f"{mod}.py"
        if not p.is_file():
            z.append(f"### {mod}: Datei fehlt")
            continue
        zeilen = p.read_text(encoding="utf-8", errors="replace").splitlines()
        z.append(f"### {mod}.py  ({len(zeilen)} Zeilen)")
        z.append("  -- Schreibzugriffe --")
        for i, zeile in enumerate(zeilen, 1):
            if SCHREIB.search(zeile):
                z.append(f"    {i:>5}: {zeile.strip()[:150]}")
        z.append("  -- Unterprozesse / Starter --")
        for i, zeile in enumerate(zeilen, 1):
            if START.search(zeile):
                z.append(f"    {i:>5}: {zeile.strip()[:150]}")
        z.append("  -- liest Belege anderer Module --")
        for i, zeile in enumerate(zeilen, 1):
            if LIEST.search(zeile) and not SCHREIB.search(zeile):
                treffer = ", ".join(sorted(set(LIEST.findall(zeile))))
                z.append(f"    {i:>5}: {treffer}")
        z.append("")
    text = "\n".join(z) + "\n"
    ziel = HARNESS / "docs" / "_r13bh_quellen.txt"
    ziel.write_text(text, encoding="utf-8", newline="\n")
    print(text[:20000])
    print(f"Beleg: {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
