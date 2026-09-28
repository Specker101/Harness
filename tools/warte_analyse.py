"""Warteschleifen in einem Batch-Mitschnitt messen (R13v, 2026-09-28).

Auftrag (Nutzer): "In B207 gingen 1390 s in Abfrageschleifen verloren ... belege aus dem
B207-Mitschnitt: welche Befehle genau, worauf wurde gewartet, und warum der Worker nicht
synchron mit Tool-Zeitgrenze lief."

Das Werkzeug liest NUR (`runs/b<N>/stream.jsonl`) und rechnet die **gemessene** Dauer je
Werkzeugaufruf aus der Zeitspanne zwischen `tool_use` und dem zugehoerigen `tool_result`.
Es klassifiziert:
  * `poll`      - Schleife mit `Start-Sleep`/`Get-Process`/`while`/`for` (Abfrageschleife)
  * `sleep`     - einzelnes `Start-Sleep`
  * `warten`    - `Wait-Process`/`Start-Process -Wait`
  * `hintergrund` - `Start-Process`/`Start-Job` (Befehl wird abgegeben, nicht gewartet)
  * `arbeit`    - alles andere

Aufruf:  python tools/warte_analyse.py [--batch 207] [--top 12]
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1] / "harness"
RUNS = HARNESS / "runs"

_RE_POLL = re.compile(r"for\s*\(\s*\$|while\s*\(|do\s*\{", re.IGNORECASE)
_RE_SLEEP = re.compile(r"start-sleep|\bsleep\s+\d", re.IGNORECASE)
_RE_GEPROC = re.compile(r"get-process|get-ciminstance", re.IGNORECASE)
_RE_WAIT = re.compile(r"wait-process|start-process[^\n]*-wait\b", re.IGNORECASE)
_RE_BG = re.compile(r"start-process|start-job", re.IGNORECASE)
_RE_TIMEOUT_ARG = re.compile(r'"timeout"\s*:', re.IGNORECASE)


def _zeit(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def klasse(befehl: str) -> str:
    t = befehl or ""
    if _RE_POLL.search(t) and (_RE_SLEEP.search(t) or _RE_GEPROC.search(t)):
        return "poll"
    if _RE_SLEEP.search(t):
        return "sleep"
    if _RE_WAIT.search(t):
        return "warten"
    if _RE_BG.search(t):
        return "hintergrund"
    return "arbeit"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--batch", type=int, default=207)
    p.add_argument("--top", type=int, default=12)
    args = p.parse_args(argv)

    pfad = RUNS / f"b{args.batch:03d}" / "stream.jsonl"
    if not pfad.is_file():
        print(f"kein Mitschnitt: {pfad}")
        return 2

    offen: dict[str, dict] = {}            # tool_use_id -> {klasse, befehl, start, zeile}
    gruppen: dict[str, float] = {}
    treffer: list[dict] = []
    hintergrund_starts: list[dict] = []    # Start-Process/-Job (der Prozess, auf den gewartet wird)
    timeout_funde: list[dict] = []         # tool_result mit Timeout-Wort
    timeout_args = 0
    zeilen = 0
    with pfad.open(encoding="utf-8", errors="replace") as fp:
        for nr, zeile in enumerate(fp, start=1):
            zeilen += 1
            if '"tool_use"' not in zeile and '"tool_result"' not in zeile:
                continue
            try:
                ev = json.loads(zeile)
            except ValueError:
                continue
            msg = ev.get("message") or {}
            for block in (msg.get("content") or []):
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    eingabe = block.get("input") or {}
                    befehl = str(eingabe.get("command") or "")
                    if _RE_TIMEOUT_ARG.search(json.dumps(eingabe)):
                        timeout_args += 1
                    if _RE_BG.search(befehl):
                        hintergrund_starts.append({"zeile": nr, "befehl": befehl})
                    k = klasse(befehl)
                    offen[block.get("id")] = {"klasse": k, "befehl": befehl,
                                              "start": _zeit(ev.get("timestamp")), "zeile": nr}
                elif block.get("type") == "tool_result":
                    e = offen.pop(block.get("tool_use_id"), None)
                    if e is None:
                        continue
                    inhalt = json.dumps(block.get("content"), ensure_ascii=False)
                    m = re.search(r".{0,90}(timed out|timeout|Zeitgrenze).{0,90}", inhalt,
                                  re.IGNORECASE)
                    if m:
                        timeout_funde.append({"zeile": nr,
                                              "text": " ".join(m.group(0).split()),
                                              "befehl": " ".join(e["befehl"].split())[:130]})
                    ende = _zeit(ev.get("timestamp"))
                    dauer = ((ende - e["start"]).total_seconds()
                             if ende and e["start"] else 0.0)
                    gruppen[e["klasse"]] = gruppen.get(e["klasse"], 0.0) + dauer
                    treffer.append({**e, "dauer_s": round(dauer, 1)})

    print(f"# Mitschnitt {pfad} - {zeilen} Zeilen")
    print(f"# Tool-Aufrufe mit Ergebnis: {len(treffer)}")
    for k in ("poll", "sleep", "warten", "hintergrund", "arbeit"):
        if k in gruppen:
            print(f"#   {k:12s} {gruppen[k]:8.1f} s")
    print(f"# Aufrufe MIT 'timeout'-Argument: {timeout_args} | "
          f"tool_result mit Timeout-Wort: {len(timeout_funde)}")
    print()
    print(f"# Die {args.top} laengsten Aufrufe:")
    for t in sorted(treffer, key=lambda x: -x["dauer_s"])[:args.top]:
        kurz = " ".join(t["befehl"].split())[:150]
        print(f"  {t['dauer_s']:7.1f} s  [{t['klasse']:11s}]  stream.jsonl:{t['zeile']}")
        print(f"           {kurz}")
    print()
    print("# Nur die Abfrageschleifen (poll):")
    for t in sorted((x for x in treffer if x["klasse"] == "poll"),
                    key=lambda x: -x["dauer_s"]):
        kurz = " ".join(t["befehl"].split())[:160]
        print(f"  {t['dauer_s']:7.1f} s  stream.jsonl:{t['zeile']}  {kurz}")
    print()
    print("# Wartebefehle und ihre Prozessnummern (WORAUF wurde gewartet):")
    for t in sorted((x for x in treffer if x["klasse"] in ("poll", "warten", "sleep")),
                    key=lambda x: -x["dauer_s"]):
        pids = sorted(set(re.findall(r"-Id\s+(\d+)", t["befehl"])))
        print(f"  {t['dauer_s']:7.1f} s  PIDs {pids or '-'}  stream.jsonl:{t['zeile']}")
    print()
    print("# Hintergrundstarts (Start-Process/-Job):")
    for h in hintergrund_starts:
        print(f"  stream.jsonl:{h['zeile']}  {' '.join(h['befehl'].split())[:170]}")
    if timeout_funde:
        print()
        print("# Tool-Timeout-Meldungen im Mitschnitt:")
        for f in timeout_funde:
            print(f"  stream.jsonl:{f['zeile']}  {f['text'][:150]}")
            print(f"           Aufruf: {f['befehl']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
