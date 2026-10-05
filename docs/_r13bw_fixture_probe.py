"""R13bw-4: die Fixture gegen die lebende Bilanz pruefen (nur lesend).

Zeigt beide Texte und die Zeilen, in denen sie sich unterscheiden. Zweck des Belegs:
`tests/fixtures/stand_b268` liefert **dieselben** Eingaben wie das lebende Decomp-Repo am
05.10.2026 - und der Test laeuft danach ohne das Repo (nur noch auf der Fixture).

Der Bericht wird vom Skript selbst als UTF-8/LF geschrieben (nie ueber `*>` - das schreibt
in PowerShell UTF-16):

    python -u docs/_r13bw_fixture_probe.py
"""

from __future__ import annotations

import io
import shutil
import sys
import time
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1] / "harness"
HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HARNESS))

from hx import stand                                        # noqa: E402
from hx.config import load_config                           # noqa: E402

FIXTURE = HARNESS / "tests" / "fixtures" / "stand_b268"
TMP = HARNESS / "tests" / "_tmp_r13bw_probe"
ZIEL = HIER / "_r13bw_fixture_beleg.txt"


def fixture_cfg():
    """`cfg` auf eine Wegwerf-Kopie der Fixture - der Test macht es genauso."""
    shutil.rmtree(TMP, ignore_errors=True)
    dec = TMP / "decomp"
    root = TMP / "harness"
    shutil.copytree(FIXTURE / "decomp", dec)
    shutil.copytree(FIXTURE / "root", root)
    cfg = load_config()
    cfg.data["paths"]["root"] = str(root)
    cfg.data["paths"]["decomp"] = str(dec)
    cfg.data["paths"]["prompts"] = str(HARNESS / "prompts")
    return cfg


def main() -> int:
    live = stand.durchsatz_zeilen(load_config())
    fix = stand.durchsatz_zeilen(fixture_cfg())
    nur_live = [z for z in live if z not in fix]
    nur_fix = [z for z in fix if z not in live]
    puffer = io.StringIO()
    puffer.write(f"R13bw-4 Fixture-Probe {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    puffer.write(f"Fixture: {FIXTURE}\n")
    puffer.write(f"Zeilen: lebend {len(live)}, Fixture {len(fix)}\n")
    for name, zeilen in (("LEBEND (g:\\Silent Scope Decomp)", live), ("FIXTURE", fix)):
        puffer.write("\n" + "=" * 78 + f"\n{name}\n" + "=" * 78 + "\n")
        for z in zeilen:
            puffer.write(z + "\n")
    puffer.write("\n" + "#" * 78 + "\n"
                 f"nur lebend ({len(nur_live)}):\n")
    for z in nur_live:
        puffer.write("  - " + z + "\n")
    puffer.write(f"nur Fixture ({len(nur_fix)}):\n")
    for z in nur_fix:
        puffer.write("  + " + z + "\n")
    text = puffer.getvalue()
    ZIEL.write_text(text, encoding="utf-8", newline="\n")
    shutil.rmtree(TMP, ignore_errors=True)
    print(f"geschrieben: {ZIEL.name} ({len(text)} Zeichen, UTF-8)")
    print(f"Zeilen: lebend {len(live)}, Fixture {len(fix)} | "
          f"nur lebend {len(nur_live)}, nur Fixture {len(nur_fix)}")
    for z in nur_live + nur_fix:
        print("  diff:", z[:150])
    return 0 if not nur_fix else 1


if __name__ == "__main__":
    sys.exit(main())
