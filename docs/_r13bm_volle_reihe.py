"""Die VOLLE Testreihe des Harness fahren - mit Kopfzeile als Beleg (R13bm, am Gate).

Waehrend ein Batch laeuft, wird nur gefahren, was die Aenderungen beruehrt (R13bm:
`docs/_r13bm_testreihe.py`). Die volle Reihe gehoert an das GATE - dieses Skript ist
dafuer gedacht und laeuft nur, wenn kein Worker arbeitet.

    python -u docs/_r13bm_volle_reihe.py

Der Beleg `docs/_r13bm_volle_reihe.txt` traegt Zeitpunkt, Verzeichnis, HEAD,
Harness-Zustand und das vollstaendige Ergebnis - dieselbe Form wie die Belege der
vorigen Runden (`docs/_r13bl_volle_reihe.txt`).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1] / "harness"
REPO = HARNESS.parent
ZIEL = Path(__file__).resolve().parent / "_r13bm_volle_reihe.txt"

RE_LAUF = re.compile(r"^Ran (\d+) tests? in ([\d.]+)s", re.MULTILINE)
RE_ERGEB = re.compile(r"^(OK|FAILED)\b(.*)$", re.MULTILINE)
RE_SKIP = re.compile(r"skipped=(\d+)")


def git(*args: str) -> str:
    try:
        p = subprocess.run(["git", *args], cwd=str(REPO), capture_output=True, text=True)
        return (p.stdout or "").strip()
    except OSError:
        return ""


def zustand() -> str:
    """Eine Zeile ueber den Harness-Zustand - die Reihe laeuft NEBEN dem Betrieb."""
    try:
        s = json.loads((HARNESS / "state" / "run.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "nicht lesbar"
    return (f"state={s.get('state')} batch={s.get('batch')} "
            f"worker={bool(s.get('worker'))} paused={bool(s.get('paused'))}")


def main() -> int:
    kopf = [
        f"Volle Testreihe {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Verzeichnis: {HARNESS}",
        f"HEAD: {git('log', '--oneline', '-1')}",
        f"Harness-Zustand: {zustand()}",
        "",
    ]
    # ACHTUNG (gemessen 02.10.2026): `harness/tests/` hat KEIN `__init__.py`. Mit
    # `-t .` bricht `unittest discover` deshalb mit "Start directory is not importable:
    # 'tests'" ab (0 Tests, 0,0 s). Ohne `-t` laeuft es: 1406 Tests.
    p = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                       cwd=str(HARNESS), capture_output=True, text=True)
    roh = (p.stdout or "") + (p.stderr or "")
    lauf = RE_LAUF.search(roh)
    ergebnis = RE_ERGEB.search(roh)
    anzahl = int(lauf.group(1)) if lauf else 0
    dauer = float(lauf.group(2)) if lauf else 0.0
    wort = ergebnis.group(1) if ergebnis else "KEINE ZUSAMMENFASSUNG"
    rest = (ergebnis.group(2) if ergebnis else "").strip()
    skip = RE_SKIP.search(wort + " " + rest)
    fehler = 0
    fehlschlaege = 0
    m = re.search(r"failures=(\d+)", wort + " " + rest)
    if m:
        fehlschlaege = int(m.group(1))
    m = re.search(r"errors=(\d+)", wort + " " + rest)
    if m:
        fehler = int(m.group(1))

    fuss = [
        f"Dauer: {dauer:.1f} s",
        f"Tests: {anzahl} | Fehler: {fehler} | Fehlschlaege: {fehlschlaege} | "
        f"uebersprungen: {int(skip.group(1)) if skip else 0}",
        f"ERGEBNIS: {'OK' if wort == 'OK' else wort}",
        "",
        "Uebersprungen: " + ("keine" if not skip or skip.group(1) == "0" else
                             f"{skip.group(1)} (s. Lauf oben)"),
    ]
    ZIEL.write_text("\n".join(kopf) + roh.rstrip() + "\n\n" + "\n".join(fuss) + "\n",
                    encoding="utf-8")
    print("\n".join(fuss))
    print(f"Beleg: {ZIEL}")
    return 0 if wort == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
