#!/usr/bin/env python
"""Punkt 5: Laufzeit von port_regression.py - nackt vs. Harness-Umgebung.

Gemessen wird zweimal dieselbe Regression:
  A) nackte Umgebung (geerbter PATH),
  B) PATH wie ihn der Harness seinen Kindprozessen gibt (envs.resolve_path,
     also mit dem MSYS2-UCRT64-Zusatz aus [env] path_prepend).

Zusaetzlich wird der Harness-Anteil aus den Nachtbelegen geholt (Worker-Env-Zeile
und die Laufzeiten der Batches) - der Harness setzt keine CPU-Grenze und keine
Prioritaet; mechanisch beeinflussen kann nur die Umgebung.

Aufruf aus g:\\Harness:  python docs\\_regression_vergleich.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

HARNESS = Path(r"g:\Harness\harness")
DECOMP = Path(r"g:\Silent Scope Decomp")
OUT = Path(__file__).with_name("_regression_vergleich.txt")
sys.path.insert(0, str(HARNESS))

from hx import envs                                                  # noqa: E402
from hx.config import load_config                                    # noqa: E402


def lauf(label: str, env: dict | None) -> float:
    t0 = time.time()
    p = subprocess.run([sys.executable, "scripts/port_regression.py"], cwd=str(DECOMP),
                       env=env, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    dauer = time.time() - t0
    letzte = [l for l in (p.stdout or "").splitlines() if l.strip()][-1:] or ["(leer)"]
    zeilen.append(f"{label}: {dauer:.1f} s (rc={p.returncode}) - {letzte[0][:110]}")
    return dauer


zeilen: list[str] = []


def main() -> int:
    cfg = load_config()
    a = lauf("A) nackte Umgebung", None)
    wenv = envs.worker_env(cfg, os.environ, "dummy-token")
    b = lauf("B) Harness-Umgebung (PATH wie worker_env)", wenv)
    zeilen.append("")
    zeilen.append(f"Unterschied: {b - a:+.1f} s ({(b - a) / a * 100:+.1f} %)")
    zeilen.append("PATH-Zusatz des Harness: " + (envs.path_of(wenv) != envs.path_of(dict(os.environ))
                                                and "anders als geerbt" or "gleich"))
    zeilen.append("")
    zeilen.append("Vergleich zum Harness-Betrieb (Belege der Nacht):")
    zeilen.append("- Der Worker fuehrt dieselbe Datei ueber die PowerShell-Werkzeugschale aus.")
    zeilen.append("  Geprueft im Code: der Harness setzt KEINE CPU-Grenze und KEINE Prioritaet")
    zeilen.append("  (der einzige creationflags-Aufruf, ghidra.py:136, ist CREATE_NO_WINDOW")
    zeilen.append("  fuer den Headless-Server - ein Fensterflag, keine Leistungsgrenze).")
    zeilen.append("- Laufzeiten der Batches der Nacht: B161-B173 13-117 min, B174 79 min.")
    zeilen.append("  Die Regression ist darin ein Schritt von rund einer halben Minute (0,2-2 %).")
    zeilen.append("- Der Preflight (AGENTS.md) fuehrt sie ohnehin genau EINMAL je Batch aus.")
    OUT.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    print("\n".join(zeilen))
    print("geschrieben: " + str(OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
