"""Beleg: Erkennung von Muster-Prozessabbau (R13i, 2026-09-26).

Prueft `streamjson.abbau_gefahr` gegen die **echten** Befehle aus den Mitschnitten
b171-b178: der eine gefaehrliche (CPU-Muster, hat den Harness getoetet) muss
auffallen, die gezielten duerfen NICHT gemeldet werden (sonst entstehen Fehlalarme
und der Lauf wird ohne Grund abgebrochen).

    python -u tools\\check_abbau.py     -> docs\\_abbau_beleg.txt
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import streamjson                                            # noqa: E402

# (Befehl, MUSS auffallen?)  - die Befehle stammen aus den Mitschnitten bzw. sind
# die naheliegenden Varianten desselben Fehlers.
FAELLE = [
    ("Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CPU -gt 50 } "
     "| ForEach-Object { Stop-Process -Id $_.Id -Force }", True),
    ("Stop-Process -Name python -Force", True),
    ("taskkill /IM python.exe /F", True),
    ("Get-Process python | Stop-Process -Force", True),
    ("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | ForEach-Object "
     "{ Stop-Process -Id $_.ProcessId -Force }", True),
    # --- gezielt: darf NICHT auffallen ---
    ("Stop-Process -Id 13744 -Force -ErrorAction SilentlyContinue; Get-Process python "
     "| Select-Object Id", False),
    ("Get-Process python | Where-Object { $_.Id -eq 7856 } | Stop-Process -Force", False),
    ("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object "
     "{ $_.CommandLine -like \"*port4c2*\" } | ForEach-Object { Stop-Process -Id $_.ProcessId }",
     False),
    ("git status --porcelain; python -u scripts/m177_hull6a.py pre --ids 0x1200", False),
    ("", False),
]


def main() -> int:
    zeilen = ["Beleg: Erkennung von Muster-Prozessabbau (R13i)",
              "  Anlass: Batch 178 raeumte `Get-Process python | Where-Object {$_.CPU -gt 50}`",
              "  ab und toetete damit den Harness (python.exe, ~370 s CPU).",
              ""]
    fehler = 0
    for cmd, soll in FAELLE:
        befund = streamjson.abbau_gefahr(cmd)
        ok = (befund is not None) == soll
        fehler += 0 if ok else 1
        marke = "OK " if ok else "ABW"
        zeilen.append(f"  [{marke}] erwartet={'GEFAHR' if soll else 'harmlos':7s} "
                      f"({befund or '-'})")
        zeilen.append(f"        {cmd[:110] or '(leer)'}")
    zeilen += ["", f"  Fehlbewertungen: {fehler}"]

    # Gegenprobe an echten Mitschnitten: alle Abbau-Befehle der Batches bewerten.
    echt = []
    for d in sorted((ROOT / "runs").glob("b1*")):
        f = d / "stream.jsonl"
        if not f.is_file():
            continue
        for ln in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if "stop-process" not in ln.lower() and "taskkill" not in ln.lower():
                continue
            try:
                ev = json.loads(ln)
            except json.JSONDecodeError:
                continue
            for b in (((ev or {}).get("message") or {}).get("content") or []):
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    cmd = (b.get("input") or {}).get("command") or ""
                    if cmd and streamjson.abbau_gefahr(cmd):
                        echt.append((d.name, " ".join(cmd.split())[:120]))
    zeilen += ["", "  Gegenprobe an echten Mitschnitten (gemeldete Befehle):"]
    for name, cmd in echt or [("(keiner)", "")]:
        zeilen.append(f"    {name}: {cmd}")
    if len(echt) != 1:
        zeilen.append(f"    ERWARTET: genau 1 (b178) - gefunden: {len(echt)}")

    text = "\n".join(zeilen)
    print(text)
    p = Path("g:/Harness/docs/_abbau_beleg.txt")
    p.write_text(text + "\n", encoding="utf-8")
    print(f"\nBeleg: {p}")
    return 0 if (fehler == 0 and len(echt) == 1) else 1


if __name__ == "__main__":
    raise SystemExit(main())
