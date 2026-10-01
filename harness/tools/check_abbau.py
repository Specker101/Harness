"""Beleg: Erkennung von Muster-Prozessabbau (R13i, 2026-09-26; erweitert R13bf).

Prueft `streamjson.abbau_gefahr` gegen die **echten** Befehle aus den Mitschnitten:
Der gefaehrliche CPU-Befehl aus b178 (hat den Harness getoetet) muss auffallen, die
gezielten duerfen NICHT gemeldet werden (sonst entstehen Fehlalarme und der Lauf wird
ohne Grund abgebrochen).

R13bf (Aussensicht B234, Befund M234-2): Der Detektor brach B234 ab, weil er eine
**woertliche PID-Liste** in einer Schleife nicht als gezielt erkannte
(`foreach ($id in @(704,13960,18296)) { Stop-Process -Id $id -Force }`,
`runs/b234/stream-v1.jsonl:40020`). Seitdem gilt sie als gezielt; die Gegenprobe laeuft
ueber **alle** Batches (nicht mehr nur `b1*`) und liest die Mitschnitte ZIP-fest
(`retention.mitschnitt_zeilen`, R13p).

    python -u tools\\check_abbau.py     -> docs\\_abbau_beleg.txt
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import retention, streamjson                                 # noqa: E402

# Der echte Befehl aus B234 (dort als Alarm ausgeloest) - gehoert zu den harmlosen.
B234_LISTE = ("foreach ($id in @(704,13960,18296)) { try { Stop-Process -Id $id -Force } "
              "catch {} }; \"killed\"; Get-CimInstance Win32_Process -Filter "
              "\"Name='hybrid_lauf.exe'\" | Measure-Object | Select-Object -ExpandProperty Count")
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
    # R13bf: Nummernquelle ohne woertliche Zahlen - bleibt verdaechtig.
    ("foreach ($id in $liste) { Stop-Process -Id $id -Force }", True),
    ("foreach ($p in (Get-Process python)) { Stop-Process -Id $p.Id -Force }", True),
    # --- gezielt: darf NICHT auffallen ---
    ("Stop-Process -Id 13744 -Force -ErrorAction SilentlyContinue; Get-Process python "
     "| Select-Object Id", False),
    ("Get-Process python | Where-Object { $_.Id -eq 7856 } | Stop-Process -Force", False),
    ("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object "
     "{ $_.CommandLine -like \"*port4c2*\" } | ForEach-Object { Stop-Process -Id $_.ProcessId }",
     False),
    ("git status --porcelain; python -u scripts/m177_hull6a.py pre --ids 0x1200", False),
    # R13bf: der echte B234-Befehl (Fehlalarm) und seine kuerzeste Form.
    (B234_LISTE, False),
    ("foreach ($id in @(704,13960,18296)) { Stop-Process -Id $id -Force }", False),
    ("$p = Start-Process -FilePath hybrid_lauf.exe -PassThru; Wait-Process -Id $p.Id "
     "-Timeout 480; Stop-Process -Id $p.Id -Force", False),
    ("", False),
]

# Erwartung der Gegenprobe an echten Mitschnitten: Nach R13bf darf KEIN echter Befehl
# mehr gemeldet werden (b234 war der einzige, und er war ein Fehlalarm). Wer eine neue
# Regel baut, traegt hier ein, was er bewusst als gefaehrlich ansieht - mit Grund.
ERWARTET_GEMELDET: list[str] = []


def echte_befehle() -> list[tuple[str, str, str]]:
    """`[(batch, quelle, befehl)]` - jeder Shell-Aufruf mit einem Abbau-Wort."""
    out: list[tuple[str, str, str]] = []
    for d in sorted((ROOT / "runs").glob("b*")):
        if not d.is_dir():
            continue
        for name in list(retention.MIT_ZIP) + ["stream-forts1.jsonl",
                                               "stream-forts2.jsonl"]:
            zeilen = retention.mitschnitt_zeilen(d / name)
            if not zeilen:
                continue
            for ln in zeilen:
                niedrig = ln.lower()
                if not any(w in niedrig for w in ("stop-process", "taskkill")):
                    continue
                try:
                    ev = json.loads(ln)
                except ValueError:
                    continue
                if not isinstance(ev, dict):
                    continue
                nachricht = ev.get("message")
                if not isinstance(nachricht, dict):
                    continue
                for b in nachricht.get("content") or []:
                    if not isinstance(b, dict) or b.get("type") != "tool_use":
                        continue
                    cmd = (b.get("input") or {}).get("command") or ""
                    if cmd:
                        out.append((d.name, name, " ".join(str(cmd).split())))
    return out


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

    # Gegenprobe an echten Mitschnitten (alle Batches, ZIP-fest).
    echt = [(b, q, c) for (b, q, c) in echte_befehle() if streamjson.abbau_gefahr(c)]
    zeilen += ["", "  Gegenprobe an echten Mitschnitten (gemeldete Befehle):"]
    for name, quelle, cmd in echt or [("(keiner)", "", "")]:
        zeilen.append(f"    {name}/{quelle}: {cmd[:130]}")
    if sorted(c for _b, _q, c in echt) != sorted(ERWARTET_GEMELDET):
        zeilen.append(f"    ERWARTET: {len(ERWARTET_GEMELDET)} gemeldete(r) Befehl(e) "
                      f"- gefunden: {len(echt)}")
        fehler += 1

    text = "\n".join(zeilen)
    print(text)
    p = Path("g:/Harness/docs/_abbau_beleg.txt")
    p.write_text(text + "\n", encoding="utf-8")
    print(f"\nBeleg: {p}")
    return 0 if fehler == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
