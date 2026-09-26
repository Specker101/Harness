"""A/B-Beleg zu R13d: alte Schreibweise vs. Nachsicht, jeweils mit offenem Leser.

Nachstellen des Absturzes vom 2026-09-26:

    PermissionError: [WinError 5] Zugriff verweigert: '...run.json.tmp' -> '...run.json'

Ein Leser (wie `hx.cli watch`, alle 1,5 s) haelt die Zieldatei kurz offen.
Aufruf:  python -u docs\\_teilungsfehler_probe.py   (aus g:\\Harness)
"""

from __future__ import annotations

import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "harness"))

from hx.util import read_text, write_text_atomic          # noqa: E402

BASE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "_teilungsfehler_tmp"))
P = os.path.join(BASE, "run.json")
DAUER = 0.25


def leser_halten(dauer: float) -> threading.Thread:
    """Kurzlebiger Leser mit normalen Freigaben (wie ein zweiter Prozess)."""
    offen = threading.Event()

    def lauf():
        with open(P, "r", encoding="utf-8") as fh:
            fh.read()
            offen.set()
            time.sleep(dauer)

    t = threading.Thread(target=lauf, daemon=True)
    t.start()
    offen.wait(3.0)
    return t


def alte_fassung(text: str) -> None:
    """`write_text_atomic` VOR R13d: ein `os.replace`, keine Nachsicht."""
    tmp = P + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, P)


def main() -> int:
    os.makedirs(BASE, exist_ok=True)
    with open(P, "w", encoding="utf-8", newline="\n") as fh:
        fh.write('{"gen": 1}\n')

    t = leser_halten(DAUER)
    try:
        alte_fassung('{"gen": 2}\n')
        print("VORHER  (ein os.replace, keine Nachsicht): OK")
    except OSError as exc:
        print(f"VORHER  (ein os.replace, keine Nachsicht): ABSTURZ "
              f"{type(exc).__name__}: {exc}")
    t.join()

    t = leser_halten(DAUER)
    try:
        write_text_atomic(P, '{"gen": 3}\n')
        print(f"NACHHER (replace_with_retry):              OK - Inhalt "
              f"{read_text(P).strip()}")
    except OSError as exc:
        print(f"NACHHER (replace_with_retry):              ABSTURZ "
              f"{type(exc).__name__}: {exc}")
    t.join()

    print(f"keine .tmp-Leiche: {not os.path.exists(P + '.tmp')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
