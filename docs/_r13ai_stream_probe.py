"""Dauer je Werkzeugaufruf aus den Zeitstempeln eines Mitschnitts (R13ai, 2026-09-29).

Rechnet wie `hx/streamjson.py` (`_offen` / `_tool_ende`): Start = `timestamp` des
`tool_use`-Ereignisses, Ende = `timestamp` des zugehoerigen `tool_result`-Ereignisses.
Damit sind die Zahlen mit der Bilanzzeile "Laufzeit-Profil -> langsamste" vergleichbar.

Beantwortet die Fragen zu den gekappten Aufrufen:
  * Welcher Aufruf genau war es (Name, voller Befehl, `timeout`-Parameter)?
  * Was stand im Ergebnis (Kappungsmeldung oder normale Ausgabe)?

Aufruf (aus `harness/`):

    python -u ../docs/_r13ai_stream_probe.py 212 213 214

Schreibt zusaetzlich `docs/_r13ai_messung.txt` (UTF-8, LF) - das ist der Beleg.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

HIER = Path(__file__).resolve().parent                # docs/
HARNESS = HIER.parent / "harness"
sys.path.insert(0, str(HARNESS))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                            # noqa: BLE001
    pass

from hx.config import load_config                       # noqa: E402

cfg = load_config()
BATCHES = [int(a) for a in sys.argv[1:]] or [212, 213, 214]
zeilen: list[str] = []


def sag(text: str = "") -> None:
    zeilen.append(text)
    print(text)


def ts(wert: str | None) -> float | None:
    if not wert:
        return None
    try:
        return datetime.fromisoformat(str(wert).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def kurz(inp: dict) -> str:
    for k in ("command", "path", "pattern", "file_path"):
        if inp.get(k):
            return str(inp[k])[:100].replace("\n", " ")
    return json.dumps(inp, ensure_ascii=False)[:100]


def scan(batch: int) -> list[dict]:
    """Je Aufruf: Dauer, Name, Eingabe, Ergebnis (aus den Ereignis-Zeitstempeln)."""
    p = Path(cfg.root) / "runs" / f"b{batch:03d}" / "stream.jsonl"
    offen: dict[str, tuple[float, str, dict]] = {}
    raus: list[dict] = []
    if not p.is_file():
        return raus
    with open(p, encoding="utf-8", errors="replace") as fh:
        for zeile in fh:
            if '"tool_use"' not in zeile and '"tool_result"' not in zeile:
                continue
            try:
                satz = json.loads(zeile)
            except ValueError:
                continue
            t = ts(satz.get("timestamp"))
            for block in ((satz.get("message") or {}).get("content") or []):
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use" and t is not None:
                    offen[str(block.get("id"))] = (t, str(block.get("name")),
                                                   block.get("input") or {})
                elif block.get("type") == "tool_result" and t is not None:
                    e = offen.pop(str(block.get("tool_use_id")), None)
                    if not e:
                        continue
                    txt = block.get("content")
                    if isinstance(txt, list):
                        txt = " ".join(str(x.get("text") or "") for x in txt
                                       if isinstance(x, dict))
                    raus.append({"id": block.get("tool_use_id"), "name": e[1],
                                 "input": e[2], "dauer_s": round(t - e[0], 1),
                                 "text": str(txt or "")})
    return raus


sag(f"R13ai Werkzeug-Zeiten aus den Mitschnitten - {datetime.now():%Y-%m-%d %H:%M}")
for batch in BATCHES:
    aufrufe = scan(batch)
    aufrufe.sort(key=lambda a: -a["dauer_s"])
    mit_timeout = [a for a in aufrufe if "timeout" in a["input"]]
    sag("")
    sag(f"=== B{batch}: {len(aufrufe)} Aufrufe mit gemessener Dauer, davon "
        f"{len(mit_timeout)} mit eigenem `timeout` ===")
    for a in aufrufe[:6]:
        inp = a["input"]
        sag(f"  {a['dauer_s']:8.1f} s  timeout={str(inp.get('timeout', '(kein)')):10} "
            f"{a['name']:11} {kurz(inp)}")
    for a in aufrufe:
        if a["dauer_s"] < 500:
            continue
        inp = a["input"]
        sag("")
        sag(f"  --- Aufruf {a['id']} ({a['dauer_s']:.1f} s) ---")
        sag(f"      timeout : {inp.get('timeout', '(NICHT gesetzt)')}")
        if inp.get("command"):
            sag("      Befehl  : " + str(inp["command"]).replace("\n", " | ")[:700])
        else:
            for k, v in inp.items():
                if k != "timeout":
                    sag(f"      {k}: {str(v)[:200]}")
        sag("      Ergebnis: " + a["text"].replace("\n", " | ")[:700])

ziel = HIER / "_r13ai_messung.txt"
ziel.write_text("\n".join(zeilen) + "\n", encoding="utf-8", newline="\n")
print(f"\n-> {ziel} ({ziel.stat().st_size} B)")
