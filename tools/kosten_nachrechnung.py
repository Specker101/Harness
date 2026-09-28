"""Kosten und Token eines Batch-Mitschnitts nachrechnen (R13v, 2026-09-28).

Auftrag (Nutzer): "Zaehlt der Kostenzaehler inzwischen die Output-Tokens? Bitte gegen die
Werte im b207-Mitschnitt nachrechnen und, falls noch offen, beheben (Output aus
message_delta bzw. result-Event)."

Das Werkzeug liest NUR `runs/b<N>/stream.jsonl` und stellt drei Dinge gegenueber:
  1. die **Summe der Nutzung je Nachricht** (`assistant.message.usage`, Maximum je
     message.id - so rechnet `hx/streamjson.py`),
  2. die Nutzung aus dem **`result`-Ereignis** (Gesamtlauf),
  3. die Nutzung aus **`message_delta`**-Ereignissen (falls die CLI sie traegt).
Danach rechnet es die Kosten mit `hx/pricing.py` nach - einmal MIT und einmal OHNE
Ausgabe-Token, damit der Unterschied sichtbar ist.

Aufruf:  python tools/kosten_nachrechnung.py --batch 207
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1] / "harness"
sys.path.insert(0, str(HARNESS))

from hx import pricing  # noqa: E402

RUNS = HARNESS / "runs"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--batch", type=int, default=207)
    args = p.parse_args(argv)
    pfad = RUNS / f"b{args.batch:03d}" / "stream.jsonl"
    if not pfad.is_file():
        print(f"kein Mitschnitt: {pfad}")
        return 2

    je_msg: dict[str, dict] = {}
    result_usage: dict = {}
    delta_usage: dict = {}
    delta_arten: dict[str, int] = {}
    zeilen = 0
    with pfad.open(encoding="utf-8", errors="replace") as fp:
        for zeile in fp:
            zeilen += 1
            if "usage" not in zeile:
                continue
            try:
                ev = json.loads(zeile)
            except ValueError:
                continue
            et = ev.get("type")
            if et == "assistant":
                msg = ev.get("message") or {}
                u = msg.get("usage") or {}
                mid = msg.get("id")
                if mid and u:
                    e = je_msg.setdefault(mid, {"miss": 0, "hit": 0, "creation": 0, "output": 0})
                    for key, uk in (("miss", "input_tokens"), ("hit", "cache_read_input_tokens"),
                                    ("creation", "cache_creation_input_tokens"),
                                    ("output", "output_tokens")):
                        e[key] = max(e[key], int(u.get(uk) or 0))
            elif et == "result":
                u = (ev.get("usage") or {})
                if u:
                    result_usage = {"miss": int(u.get("input_tokens") or 0),
                                    "hit": int(u.get("cache_read_input_tokens") or 0),
                                    "creation": int(u.get("cache_creation_input_tokens") or 0),
                                    "output": int(u.get("output_tokens") or 0)}
            elif et == "message_delta":
                u = (ev.get("usage") or {})
                if u:
                    delta_arten["message_delta mit usage"] = delta_arten.get(
                        "message_delta mit usage", 0) + 1
                    for key, uk in (("miss", "input_tokens"), ("hit", "cache_read_input_tokens"),
                                    ("creation", "cache_creation_input_tokens"),
                                    ("output", "output_tokens")):
                        delta_usage[key] = max(delta_usage.get(key, 0), int(u.get(uk) or 0))

    def summe(feld: str) -> int:
        return sum(e[feld] for e in je_msg.values())

    print(f"# Mitschnitt {pfad} - {zeilen} Zeilen, {len(je_msg)} Nachrichten mit Nutzung")
    print(f"# je Nachricht (Maximum je id): miss={summe('miss')} hit={summe('hit')} "
          f"creation={summe('creation')} output={summe('output')}")
    print(f"# result-Ereignis            : {result_usage or '(keins)'}")
    print(f"# message_delta              : {delta_usage or '(keins)'} {delta_arten or ''}")
    print()
    out_je_msg = summe("output")
    out_result = int(result_usage.get("output") or 0)
    genutzt = max(out_je_msg, out_result)
    print(f"# Ausgabe-Token: aus Ereignissen {out_je_msg} | aus result {out_result} "
          f"-> genommen {genutzt} ({'result' if out_result > out_je_msg else 'Ereignisse'})")
    print()
    for name, out in (("MIT Ausgabe", genutzt), ("OHNE Ausgabe", 0)):
        c = pricing.cost_usd(summe("miss"), summe("hit"), summe("creation"), out)
        print(f"# {name:14s}: ${c:.6f}  "
              f"(miss {summe('miss')} x {pricing.RATES['offpeak']['cache_miss']} + "
              f"hit {summe('hit')} x {pricing.RATES['offpeak']['cache_hit']} + "
              f"out {out} x {pricing.RATES['offpeak']['output']} je 1M)")
    if genutzt:
        ohne = pricing.cost_usd(summe("miss"), summe("hit"), summe("creation"), 0)
        mit = pricing.cost_usd(summe("miss"), summe("hit"), summe("creation"), genutzt)
        print(f"# Ohne Ausgabe waeren es {100 * (mit - ohne) / mit:.1f} % weniger.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
