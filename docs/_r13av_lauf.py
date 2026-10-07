"""Volle Testreihe fahren und den Beleg selbst schreiben (R13av).

Warum ein eigenes Skript und keine Konsole-Pipe: `python -u -m unittest discover` schreibt
nach **stderr**, und `| Out-File -Encoding utf8` laeuft ueber die Konsole und verstuemmelt
Umlaute (dieselbe Falle wie bei `docs/_r13as_belege.py`). Hier schreibt Python den Bericht
selbst als UTF-8 mit LF.

Aufruf: python -u docs/_r13av_lauf.py            (gibt eine Kurzfassung aus)
        python -u docs/_r13av_lauf.py schreiben  (schreibt docs/_r13av_volle_reihe.txt)

R13bd (2026-09-30): Der Bericht nennt jetzt JEDEN uebersprungenen Test mit Grund.
`verbosity=1` schreibt nur "OK (skipped=1)" - der Name fehlte, und in R13bc musste der
eine Skip mit einem eigenen Werkzeug (`docs/_r13bc_skipfind.py`) gesucht werden. Wer die
volle Reihe faehrt, hat damit in derselben Datei Anzahl UND Namen.

R13bw-18 (2026-10-08): Die Reihe gehoert ANS GATE. Deshalb prueft `wache()` VOR dem Start
`state/run.json` (`hx.state.laufender_lauf`): laeuft ein Worker oder ein Review
(`worker` gesetzt bzw. `DS_WORKING`/`CLAUDE_REVIEWING`), bricht der Lauf mit rc=2 und
klarer Meldung ab - die Maschine des laufenden Batches soll die Last nicht mittragen.
`--trotzdem` uebersteuert das bewusst (die Warnung steht dann im Bericht). Im Kopf stehen
jetzt BEIDE Zustaende: beim Start und am Ende.
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


class Skippergebnis(unittest.TextTestResult):
    """Sammelt jeden uebersprungenen Test mit seinem Grund (R13bd).

    `verbosity=1` fasst Skips nur als Zahl zusammen ("OK (skipped=1)"). Ein Test, der
    sich abschaltet, ist aber genau der Verdachtsfall: er meldet keinen Fehler mehr.
    """

    def __init__(self, *args, **kwargs) -> None:                       # noqa: ANN002,ANN003
        super().__init__(*args, **kwargs)
        self.skips: list[tuple[str, str]] = []

    def addSkip(self, test, reason) -> None:                           # noqa: ANN001
        modul = test.__class__.__module__.split(".")[-1]
        self.skips.append((f"{modul}.{test.__class__.__name__}.{test._testMethodName}",
                           reason))
        super().addSkip(test, reason)


def zustand_text() -> str:
    """`state=… batch=… worker=…` aus `state/run.json` (R13au-Regel)."""
    try:
        from hx.config import load_config
        from hx.util import read_json
        cfg = load_config()
        d = read_json(Path(cfg.root) / "state" / "run.json", {}) or {}
        return (f"state={d.get('state')} batch={d.get('batch')} "
                f"worker={bool(d.get('worker'))}")
    except Exception as exc:                                           # noqa: BLE001
        return f"nicht lesbar ({str(exc)[:80]})"


def laufender_lauf_text() -> str:
    """Begruendung, wenn gerade ein Worker oder Review laeuft, sonst "" (R13bw-18)."""
    try:
        from hx.config import load_config
        from hx.state import laufender_lauf
        cfg = load_config()
        return laufender_lauf(Path(cfg.root) / "state" / "run.json")
    except Exception:                                                  # noqa: BLE001
        return ""


def wache() -> tuple[int, str]:
    """VOR dem Lauf: laeuft ein Batch? -> `(rc, Meldung)`; 0 = weiter, 2 = abgelehnt.

    Anlass (R13bw-17): die Reihe wurde gestartet, waehrend Batch 292 seit 2 h 10 min lief -
    die Maschine des Workers trug die Last mit. Die Regel steht in `docs/bedienung.md`
    (Einleitung, §12u, §12z); hier wird sie erzwungen. `--trotzdem` uebersteuert sie
    bewusst - dann steht die Warnung im Bericht.
    """
    grund = laufender_lauf_text()
    if not grund:
        return 0, ""
    if "--trotzdem" in sys.argv[1:]:
        return 0, f"WARNUNG: es laeuft ein Batch ({grund}) - mit --trotzdem gefahren."
    return 2, ("ABGELEHNT: es laeuft ein Batch - " + grund + ".\n"
               "Die volle Reihe gehoert ANS GATE (state=GATE_APPROVAL, worker leer) oder an "
               "einen gestoppten Harness; sonst nur die betroffenen Testdateien fahren "
               "(docs/bedienung.md Einleitung, §12u).\n"
               "Bewusst uebersteuern: --trotzdem")


def kopf(zustand_start: str = "") -> list[str]:
    """Zeitpunkt, HEAD und der Harness-Zustand BEIM START und AM ENDE (R13au, R13bw-18).

    `kopf()` laeuft am ENDE (nach `os.chdir`), deshalb kommt der Startzustand von `main`
    herein. Anlass: in R13bw-17 stand nur der Endstand im Beleg ("state=DS_WORKING"),
    obwohl der Lauf am Gate begonnen hatte - der Bericht sah damit selbst wie ein
    Regelverstoss aus.
    """
    zeilen = [f"Volle Testreihe {time.strftime('%Y-%m-%d %H:%M:%S')}",
              f"Verzeichnis: {HARNESS}"]
    try:
        r = subprocess.run(["git", "log", "-1", "--pretty=%h %s"], cwd=str(HIER.parent),
                           capture_output=True, text=True, timeout=30)
        zeilen.append("HEAD: " + (r.stdout or "").strip())
    except Exception:                                                  # noqa: BLE001
        zeilen.append("HEAD: nicht lesbar")
    zeilen.append(f"Harness-Zustand beim Start: {zustand_start or 'nicht gelesen'}")
    zeilen.append(f"Harness-Zustand am Ende:  {zustand_text()}")
    return zeilen


def lauf(zustand_start: str = "") -> tuple[str, int]:
    puffer = io.StringIO()
    # GENAU wie auf der Kommandozeile: `cd harness` + `unittest discover -s tests
    # -p "test_*.py"`. Ohne das gibt `discover` auf, weil `tests/` kein Paket ist
    # (kein `__init__.py`).
    os.chdir(ROOT)
    loader = unittest.TestLoader()
    suite = loader.discover("tests", pattern="test_*.py")
    runner = unittest.TextTestRunner(stream=puffer, verbosity=1,
                                     resultclass=Skippergebnis)
    t0 = time.time()
    ergebnis = runner.run(suite)
    dauer = time.time() - t0
    kopfzeilen = kopf(zustand_start)
    bilanz = [
        "",
        f"Dauer: {dauer:.1f} s",
        f"Tests: {ergebnis.testsRun} | Fehler: {len(ergebnis.errors)} "
        f"| Fehlschläge: {len(ergebnis.failures)} "
        f"| übersprungen: {len(ergebnis.skipped)}",
        "ERGEBNIS: " + ("OK" if ergebnis.wasSuccessful() else "FEHLGESCHLAGEN"),
    ]
    skips = getattr(ergebnis, "skips", [])
    skipblock = ([f"Übersprungen ({len(skips)}) - Name und Grund:"]
                 + [f"  - {name}  [{grund}]" for name, grund in skips]) if skips else \
                ["Übersprungen: keine"]
    text = "\n".join(kopfzeilen + bilanz[:1] + puffer.getvalue().splitlines()
                      + bilanz[1:] + [""] + skipblock)
    return text, (0 if ergebnis.wasSuccessful() else 1)


def main() -> int:
    rc_wache, meldung = wache()
    if meldung:
        print(meldung)
    if rc_wache:
        return rc_wache                       # R13bw-18: kein Lauf waehrend eines Batches
    text, rc = lauf(zustand_text())
    ziel = ZIEL
    for a in sys.argv[1:]:
        if a.startswith("--ziel="):
            # WICHTIG: relativ angegebene Ziele werden gegen HIER aufgeloest - `lauf()`
            # hat vorher `os.chdir(ROOT)` gemacht, sonst landet die Datei im Harness.
            p = Path(a.split("=", 1)[1])
            ziel = p if p.is_absolute() else (HIER / p.name)
    if "schreiben" in sys.argv:
        ziel.write_text(text + "\n", encoding="utf-8", newline="\n")
        print(f"geschrieben: {ziel.name} ({len(text)} Zeichen, UTF-8)")
    else:
        print(text)
    # Kurzfassung (unabhaengig davon, ob geschrieben wurde)
    for z in text.splitlines():
        if z.startswith(("Tests:", "Dauer:", "ERGEBNIS:", "Harness-Zustand", "HEAD:",
                         "Übersprungen")) or z.startswith("  - "):
            print(z)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
