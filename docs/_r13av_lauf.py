"""Volle Testreihe fahren und den Beleg selbst schreiben (R13av).

Warum ein eigenes Skript und keine Konsole-Pipe: `python -u -m unittest discover` schreibt
nach **stderr**, und `| Out-File -Encoding utf8` laeuft ueber die Konsole und verstuemmelt
Umlaute (dieselbe Falle wie bei `docs/_r13as_belege.py`). Hier schreibt Python den Bericht
selbst als UTF-8 mit LF.

Aufruf: python -u docs/_r13av_lauf.py            (gibt eine Kurzfassung aus)
        python -u docs/_r13av_lauf.py schreiben  (schreibt docs/_r13av_volle_reihe.txt)
"""

from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

HIER = Path(__file__).resolve().parent
HARNESS = HIER.parent / "harness"
ROOT = HARNESS
sys.path.insert(0, str(ROOT))

ZIEL = HIER / "_r13av_volle_reihe.txt"


def kopf() -> list[str]:
    """Was zu diesem Lauf gehoert: Zeitpunkt, HEAD, Harness-Zustand (R13au-Regel)."""
    zeilen = [f"Volle Testreihe {time.strftime('%Y-%m-%d %H:%M:%S')}",
              f"Verzeichnis: {HARNESS}"]
    try:
        r = subprocess.run(["git", "log", "-1", "--pretty=%h %s"], cwd=str(HIER.parent),
                           capture_output=True, text=True, timeout=30)
        zeilen.append("HEAD: " + (r.stdout or "").strip())
    except Exception:                                                  # noqa: BLE001
        zeilen.append("HEAD: nicht lesbar")
    try:
        from hx.config import load_config
        from hx.util import read_json
        cfg = load_config()
        d = read_json(Path(cfg.root) / "state" / "run.json", {}) or {}
        zeilen.append(f"Harness-Zustand: state={d.get('state')} batch={d.get('batch')} "
                      f"worker={bool(d.get('worker'))}")
    except Exception as exc:                                           # noqa: BLE001
        zeilen.append(f"Harness-Zustand: nicht lesbar ({str(exc)[:80]})")
    return zeilen


def lauf() -> tuple[str, int]:
    puffer = io.StringIO()
    # GENAU wie auf der Kommandozeile: `cd harness` + `unittest discover -s tests
    # -p "test_*.py"`. Ohne das gibt `discover` auf, weil `tests/` kein Paket ist
    # (kein `__init__.py`).
    os.chdir(ROOT)
    loader = unittest.TestLoader()
    suite = loader.discover("tests", pattern="test_*.py")
    runner = unittest.TextTestRunner(stream=puffer, verbosity=1)
    t0 = time.time()
    ergebnis = runner.run(suite)
    dauer = time.time() - t0
    kopfzeilen = kopf()
    bilanz = [
        "",
        f"Dauer: {dauer:.1f} s",
        f"Tests: {ergebnis.testsRun} | Fehler: {len(ergebnis.errors)} "
        f"| Fehlschläge: {len(ergebnis.failures)} "
        f"| übersprungen: {len(ergebnis.skipped)}",
        "ERGEBNIS: " + ("OK" if ergebnis.wasSuccessful() else "FEHLGESCHLAGEN"),
    ]
    text = "\n".join(kopfzeilen + bilanz[:1] + puffer.getvalue().splitlines() + bilanz[1:])
    return text, (0 if ergebnis.wasSuccessful() else 1)


def main() -> int:
    text, rc = lauf()
    if "schreiben" in sys.argv:
        ZIEL.write_text(text + "\n", encoding="utf-8", newline="\n")
        print(f"geschrieben: {ZIEL.name} ({len(text)} Zeichen, UTF-8)")
    else:
        print(text)
    # Kurzfassung (unabhaengig davon, ob geschrieben wurde)
    for z in text.splitlines():
        if z.startswith(("Tests:", "Dauer:", "ERGEBNIS:", "Harness-Zustand:", "HEAD:")):
            print(z)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
