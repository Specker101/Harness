"""Sonde R13aj (2026-09-29): Werkzeugdauer - parallele Aufrufe? (NUR LESEND)

Anlass: `hx/streamjson.py` misst die Dauer eines Werkzeugaufrufs als Abstand
`tool_use` -> `tool_result`. In B212 standen zwei Aufrufe mit **511,0 s** (ein
`port_build` UND ein Grep mit normalen Treffern) und ein Grep mit **602,3 s** - die
Frage war, ob mehrere Aufrufe **gleichzeitig** laufen und die Messung daher die
Wartezeit mitzaehlt (und die Umschaltschwelle ueber `stand.preflight_dauer` verfaelscht).

Drei Teile, alle ohne Schreiber:

  1. Assistant-Nachrichten mit mehr als einem `tool_use` (echter Parallelstart im
     selben Zug) - Verteilung "Aufrufe je Nachricht";
  2. Ueberlappung: laeuft ein Aufruf noch, waehrend der naechste startet? (Zahl der
     offenen Aufrufe im Moment des Ergebnisses, Start-/Endzeiten der langsamsten);
  3. Ueberlappungsdauer je Aufruf (Intervall-Schnitt mit jedem anderen Aufruf) - daraus
     kommt die Toleranz fuer das Feld `parallel` (Rundung der Zeitstempel vs. Nebenlauf).

Aufruf aus dem Repo-Wurzelverzeichnis:   python -u docs/_r13aj_probe.py
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

BATCHES = (212, 213, 214)


def ts(wert) -> float | None:
    if not wert:
        return None
    try:
        return datetime.fromisoformat(str(wert).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def kurz(inp: dict) -> str:
    for k in ("command", "path", "pattern", "file_path"):
        if inp.get(k):
            return str(inp[k])[:64].replace("\n", " ")
    return json.dumps(inp, ensure_ascii=False)[:64]


def zeilen(pfad: Path):
    """(Zeilennr, Zeitstempel, Bloecke) - nur Ereignisse mit Werkzeugbezug."""
    with open(pfad, encoding="utf-8", errors="replace") as fh:
        for nr, zeile in enumerate(fh, 1):
            if '"tool_use"' not in zeile and '"tool_result"' not in zeile:
                continue
            try:
                satz = json.loads(zeile)
            except ValueError:
                continue
            inhalt = ((satz.get("message") or {}).get("content") or [])
            if not isinstance(inhalt, list):
                continue
            bloecke = [b for b in inhalt if isinstance(b, dict)]
            yield nr, ts(satz.get("timestamp")), satz, bloecke


def teil1(pfad: Path) -> None:
    verteilung: dict[int, int] = {}
    beispiele: list[str] = []
    for nr, _t, _s, bloecke in zeilen(pfad):
        aufrufe = [b for b in bloecke if b.get("type") == "tool_use"]
        if not aufrufe:
            continue
        verteilung[len(aufrufe)] = verteilung.get(len(aufrufe), 0) + 1
        if len(aufrufe) > 1 and len(beispiele) < 6:
            beispiele.append(f"    Zeile {nr}: "
                             + " | ".join(f"{b.get('name')} {kurz(b.get('input') or {})}"
                                          for b in aufrufe))
    print(f"  Verteilung (Aufrufe je Assistant-Nachricht): {dict(sorted(verteilung.items()))}")
    if beispiele:
        for b in beispiele:
            print(b)
    else:
        print("    keine Nachricht mit mehr als einem Werkzeugaufruf")


def teil2(pfad: Path) -> None:
    offen: dict[str, dict] = {}
    fertig: list[dict] = []
    for nr, t, _s, bloecke in zeilen(pfad):
        for b in bloecke:
            if b.get("type") == "tool_use":
                offen[str(b.get("id"))] = {"t0": t, "nr": nr, "name": str(b.get("name")),
                                           "input": b.get("input") or {}}
            elif b.get("type") == "tool_result":
                e = offen.pop(str(b.get("tool_use_id")), None)
                if not e or t is None or e["t0"] is None:
                    continue
                fertig.append({**e, "t1": t, "dauer_s": round(t - e["t0"], 1),
                               "offen_bei_ende": len(offen)})
    parallel = [a for a in fertig if a["offen_bei_ende"] > 0]
    print(f"  {len(fertig)} Aufrufe, davon {len(parallel)} mit Ueberlappung "
          "(ein anderer Aufruf lief noch)")
    for a in sorted(parallel, key=lambda x: -x["dauer_s"])[:4]:
        print(f"    {a['dauer_s']:8.1f} s  offen_bei_ende={a['offen_bei_ende']}  "
              f"{a['name']:11} Zeile {a['nr']:6}  {kurz(a['input'])}")


def teil3(pfad: Path) -> None:
    offen: dict[str, dict] = {}
    fertig: list[dict] = []
    for nr, t, _s, bloecke in zeilen(pfad):
        for b in bloecke:
            if b.get("type") == "tool_use":
                offen[str(b.get("id"))] = {"t0": t, "nr": nr, "name": str(b.get("name")),
                                           "input": b.get("input") or {}}
            elif b.get("type") == "tool_result":
                e = offen.pop(str(b.get("tool_use_id")), None)
                if not e or t is None or e["t0"] is None:
                    continue
                fertig.append({**e, "t1": t, "dauer_s": round(t - e["t0"], 1)})
    for i, a in enumerate(fertig):
        max_ueb, partner = 0.0, ""
        for j, b in enumerate(fertig):
            if i == j:
                continue
            ueb = min(a["t1"], b["t1"]) - max(a["t0"], b["t0"])
            if ueb > max_ueb:
                max_ueb, partner = ueb, f"{b['name']} ({b['dauer_s']:.1f}s)"
        a["ueb"], a["partner"] = round(max_ueb, 1), partner
    gross = [a for a in fertig if a["ueb"] > 1.0]
    klein = [a for a in fertig if 0 < a["ueb"] <= 1.0]
    print(f"  Ueberlappung > 1,0 s (echter Nebenlauf): {len(gross)}")
    for a in sorted(gross, key=lambda x: -x["ueb"])[:4]:
        print(f"    {a['dauer_s']:8.1f} s  Ueberlappung {a['ueb']:7.1f} s  mit "
              f"{a['partner']:22} {a['name']:11} Zeile {a['nr']:6}  {kurz(a['input'])}")
    print(f"  Ueberlappung <= 1,0 s (Rundung der Zeitstempel): {len(klein)}")


def main() -> int:
    cfg = load_config()
    for batch in BATCHES:
        p = Path(cfg.root) / "runs" / f"b{batch:03d}" / "stream.jsonl"
        if not p.is_file():
            print(f"=== B{batch}: kein stream.jsonl ===")
            continue
        print(f"=== B{batch} ({p}) ===")
        print(" 1) mehrere tool_use in EINER Assistant-Nachricht?")
        teil1(p)
        print(" 2) laeuft ein Aufruf noch, waehrend der naechste startet?")
        teil2(p)
        print(" 3) wie gross ist die Ueberlappung?")
        teil3(p)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
