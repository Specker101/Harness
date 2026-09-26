"""Einmal-Diagnose: Welche Prozesse hat der Worker abgeraeumt? (2026-09-26)

Anlass: der Harness starb zweimal still. Ein `Stop-Process`, das Prozesse nach einem
MUSTER auswaehlt (Name, CPU-Zeit, `Get-Process | Where-Object`), trifft auch den
Harness selbst - der ist ein `python.exe` mit wachsender CPU-Zeit. `Stop-Process -Id 1234`
mit einer festen Nummer ist dagegen harmlos.

Ausgabe: je Batch die Abbau-Befehle, als WILDCARD oder gezielt gekennzeichnet.

    python docs\\_abbau_scan.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "harness"
sys.path.insert(0, str(ROOT))

ABBau = re.compile(r"stop-process|taskkill", re.IGNORECASE)
# GEFAEHRLICH: die Auswahl trifft den Harness selbst mit - der ist ein python.exe
# mit wachsender CPU-Zeit und heisst im Prozessbaum genau wie die Emulationslaeufe.
GEFAEHRLICH = re.compile(r"\$_\.cpu|-name\s|taskkill\s+/im", re.IGNORECASE)
# GEZIELT: feste Prozessnummer (auch als `$_.Id -eq 7856` in einer Pipeline).
GEZIELT = re.compile(r"stop-process\s+-id\s+\d+|\$_\.id\s+-eq\s+\d+", re.IGNORECASE)
# MUSTERGEBUNDEN: Auswahl ueber die Kommandozeile (z. B. `-like \"*port4c2*\"`).
MUSTER = re.compile(r"commandline\s+-like", re.IGNORECASE)


def befehle(stream: Path) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for ln in stream.read_text(encoding="utf-8", errors="replace").splitlines():
        if not ABBau.search(ln):
            continue
        try:
            ev = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if not isinstance(ev, dict):
            continue
        for b in ((ev.get("message") or {}).get("content") or []):
            if not (isinstance(b, dict) and b.get("type") == "tool_use"):
                continue
            cmd = " ".join(str((b.get("input") or {}).get("command") or "").split())
            if not ABBau.search(cmd):
                continue
            if GEFAEHRLICH.search(cmd):
                art = "GEFAEHRLICH"
            elif MUSTER.search(cmd):
                art = "mustergebunden"
            elif GEZIELT.search(cmd):
                art = "gezielt"
            else:
                art = "unklar"
            out.append((ev.get("timestamp") or "?", art, cmd))
    return out


def main() -> int:
    zeilen: list[str] = []
    wild = 0
    for d in sorted((ROOT / "runs").glob("b1*")):
        f = d / "stream.jsonl"
        if not f.is_file():
            continue
        treffer = befehle(f)
        if not treffer:
            continue
        n_wild = sum(1 for t in treffer if t[1] == "GEFAEHRLICH")
        wild += n_wild
        zeilen.append(f"== {d.name}: {len(treffer)} Abbau-Befehle, davon {n_wild} GEFAEHRLICH")
        for t, art, cmd in treffer:
            zeilen.append(f"   {art:8s} {t} {cmd[:180]}")
    zeilen.append("")
    zeilen.append(f"Summe GEFAEHRLICH-Befehle in allen Batches: {wild}")
    text = "\n".join(zeilen)
    print(text)
    p = Path("g:/Harness/docs/_abbau_scan.txt")
    p.write_text(text + "\n", encoding="utf-8")
    print(f"\nBeleg: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
