"""R13ar: was zaehlt `num_turns` - und warum lief meta-214 mit 35 Zuegen durch?

GEMESSEN: `[meta] max_turns = 30` stand seit R13w (1eee551) bis R13aq unveraendert; meta-214
(29.09. 18:43) lief damit erfolgreich und meldete `num_turns=35`, meta-217 brach mit
`error_max_turns` bei `num_turns=31` ab. Das Werkzeug zaehlt also nicht dasselbe wie die
Zahl `--max-turns`.

Dieses Skript stellt die Zaehlweisen nebeneinander (nur lesend):
  * `num_turns` aus dem `result`-Ereignis,
  * Anzahl `assistant`-Ereignisse / eindeutige Message-IDs,
  * Anzahl Werkzeugaufrufe (`tool_use`),
  * Anzahl `user`-Ereignisse (Werkzeugergebnisse).

Aufruf: python -u docs/_r13ar_zuege.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
HARNESS = HIER.parent / "harness"
sys.path.insert(0, str(HARNESS))

from hx import streamjson                                     # noqa: E402


def zeile(n: int) -> dict:
    p = HARNESS / "runs" / f"meta-{n}.jsonl"
    aus = {"n": n, "da": p.is_file(), "num_turns": None, "subtype": "",
           "assistant": 0, "ids": 0, "tools": 0, "runden": 0, "runden_ids": 0,
           "max_bloecke": 0, "user": 0, "system": 0}
    if not p.is_file():
        return aus
    st = streamjson.StreamStats()
    ids: set = set()
    mit_tools: dict[str, int] = {}
    ohne_id = 0
    for z in p.read_text(encoding="utf-8", errors="replace").splitlines():
        st.feed(z)
        try:
            e = json.loads(z)
        except ValueError:
            continue
        typ = e.get("type")
        if typ == "assistant":
            aus["assistant"] += 1
            msg = e.get("message") or {}
            mid = msg.get("id")
            if mid:
                ids.add(mid)
            bloecke = msg.get("content")
            anzahl = (len([b for b in bloecke
                           if isinstance(b, dict) and b.get("type") == "tool_use"])
                      if isinstance(bloecke, list) else 0)
            if anzahl:
                aus["runden"] += 1
                if mid:
                    mit_tools[mid] = max(mit_tools.get(mid, 0), anzahl)
                else:
                    ohne_id += 1
        elif typ in ("user", "system"):
            aus[typ] += 1
        elif typ == "result":
            aus["num_turns"] = e.get("num_turns")
            aus["subtype"] = str(e.get("subtype") or "")
    aus["ids"] = len(ids)
    aus["tools"] = len(st.tools)
    aus["runden_ids"] = len(mit_tools) + ohne_id
    aus["max_bloecke"] = max(list(mit_tools.values()) + [0])
    return aus


def transcript_runden(n: int) -> tuple[int, str]:
    """Zweite Quelle: das Sitzungs-Transcript der CLI (R13ar, Zuguhr-Argument).

    Der Hook zaehlt die Runden im Transcript - also muss dieselbe Zahl dort stehen,
    die der Harness am Ende aus `runs/meta-<n>.jsonl` liest.
    """
    p = HARNESS / "runs" / f"meta-{n}.jsonl"
    if not p.is_file():
        return 0, ""
    sid = ""
    for z in p.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            e = json.loads(z)
        except ValueError:
            continue
        if e.get("type") == "system" and e.get("subtype") == "init":
            sid = str(e.get("session_id") or "")
            break
    if not sid:
        return 0, ""
    treffer = sorted((HARNESS / "cc-reviewer" / "projects").glob(f"*/{sid}.jsonl"))
    if not treffer:
        return 0, ""
    q = treffer[0]
    return streamjson.runden_aus_zeilen(
        q.read_text(encoding="utf-8", errors="replace").splitlines()), str(q)


def main() -> int:
    print("R13ar: Zaehlweisen der Aussensicht-Laeufe (Limit war 30 bis R13aq)")
    print()
    kopf = (f"{'Lauf':<10}{'num_turns':>10}{'subtype':>18}{'Runden-IDs':>12}"
            f"{'tool_use':>10}{'max/Block':>11}{'user':>7}{'Message-IDs':>13}")
    print(kopf)
    print("-" * len(kopf))
    for n in (208, 209, 210, 211, 212, 213, 214, 215, 216, 217):
        z = zeile(n)
        if not z["da"]:
            continue
        print(f"{'meta-' + str(n):<10}{str(z['num_turns']):>10}{z['subtype']:>18}"
              f"{z['runden_ids']:>12}{z['tools']:>10}{z['max_bloecke']:>11}"
              f"{z['user']:>7}{z['ids']:>13}")
    print()
    print("Lesehilfe: `num_turns` ist die Zahl aus dem Ergebnis-Ereignis der CLI.")
    print("`Runden-IDs` = Modellantworten MIT Werkzeugaufruf, nach Message-ID gezaehlt")
    print("(mehrere Aufrufe in derselben Antwort = EINE Runde); `max/Block` ist die")
    print("groesste Zahl paralleler Aufrufe in einer Antwort.")
    print()
    print("Transcript-Gegenprobe (zweite Quelle, zaehlt wie die Zuguhr):")
    for n in (214, 217):
        r, q = transcript_runden(n)
        if q:
            print(f"  meta-{n}: {r} Runden  <- {Path(q).relative_to(HARNESS).as_posix()}")
        else:
            print(f"  meta-{n}: Transcript nicht gefunden")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
