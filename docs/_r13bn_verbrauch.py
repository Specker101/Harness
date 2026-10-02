"""R13bn Punkt 2 - NUR MESSEN: Verbrauch je Aufruftyp der letzten 7 Tage.

Es wird NICHTS geaendert. Gelesen werden die Mitschnitte, die die claude-CLI selbst
schreibt; die Zahlen (Tokens, `total_cost_usd`, `num_turns`) stehen im `result`-Ereignis
am Ende jedes Laufs. Laeufe ohne `result`-Ereignis (Abbruch) werden aus den
`assistant`-Ereignissen summiert und als solche gezaehlt.

    python -u docs/_r13bn_verbrauch.py            # Beleg schreiben
    python -u docs/_r13bn_verbrauch.py --stdout   # nur zeigen

Aufruftypen (Auftrag R13bn Punkt 2): Review, Aussensicht, sonstige. Der WORKER laeuft
ueber eine eigene API (`[claude] base_url`, Modell `deepseek-flash[1m]`) - er zaehlt
deshalb NICHT auf das Abo, wird aber mitgemessen und getrennt ausgewiesen.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1] / "harness"
BELEG = Path(__file__).resolve().parent / "_r13bn_verbrauch.txt"
TAGE = 7

# Typ -> (Muster, Beschreibung). Reihenfolge = Anzeige-Reihenfolge.
TYPEN = (
    ("Review", ("runs/b*/reviewer.jsonl", "runs/b*/lauf*/reviewer.jsonl",
                "runs/b*/reviewer-*.jsonl", "runs/b*/lauf*/reviewer-*.jsonl"),
     "Reviewer (Opus) - zaehlt auf das Abo"),
    ("Aussensicht", ("runs/meta-*.jsonl", "runs/meta-*.jsonl.bak"),
     "Aussensicht/Meta-Review (Opus) - zaehlt auf das Abo"),
    ("/ask", ("logs/ask/*.jsonl",), "Freie Frage per /ask (Opus) - zaehlt auf das Abo"),
    ("Worker", ("runs/b*/stream.jsonl", "runs/b*/stream-forts*.jsonl",
                "runs/b*/lauf*/stream.jsonl", "runs/b*/lauf*/stream-forts*.jsonl"),
     "Worker (deepseek-flash[1m]) - eigene API, zaehlt NICHT auf das Abo"),
)


def _zahl(x) -> int:
    try:
        return int(x or 0)
    except (TypeError, ValueError):
        return 0


def lies(pfad: Path) -> dict:
    """Tokens eines Mitschnitts - aus dem `result`-Ereignis der CLI.

    NUR das `result`-Ereignis traegt die Summe des Laufs. Die `assistant`-Ereignisse
    wiederholen die `usage` IHRER Nachricht mehrfach (Streaming-Stuecke) - eine Summe
    darueber zaehlt dieselben Tokens vielfach (gemessen: 5 assistant-Ereignisse mit
    identischer usage in `runs/b243/reviewer.jsonl`). Laeufe ohne `result`-Ereignis
    (Abbruch) werden gezaehlt, ihr Verbrauch aber NICHT geschaetzt.
    """
    roh = {"datei": pfad.name, "pfad": str(pfad), "requests": 0, "input": 0,
           "cache_read": 0, "cache_creation": 0, "output": 0, "cost_usd": None,
           "turns": None, "modell": "", "result_event": False, "fehler": ""}
    letzter_rate = None
    try:
        with open(pfad, "r", encoding="utf-8", errors="replace") as fh:
            for zeile in fh:
                if '"usage"' not in zeile and "rate_limit" not in zeile:
                    continue
                try:
                    d = json.loads(zeile)
                except ValueError:
                    continue
                if d.get("type") == "rate_limit_event":
                    letzter_rate = d.get("rate_limit_info") or letzter_rate
                    continue
                if d.get("type") != "result":
                    continue
                u = d.get("usage") or {}
                roh["result_event"] = True
                roh["input"] = _zahl(u.get("input_tokens"))
                roh["cache_read"] = _zahl(u.get("cache_read_input_tokens"))
                roh["cache_creation"] = _zahl(u.get("cache_creation_input_tokens"))
                roh["output"] = _zahl(u.get("output_tokens"))
                roh["requests"] = _zahl(d.get("num_turns"))
                roh["modell"] = ",".join((d.get("modelUsage") or {}).keys())
                kost = d.get("total_cost_usd")
                roh["cost_usd"] = float(kost) if isinstance(kost, (int, float)) else None
                break
    except OSError as exc:
        roh["fehler"] = str(exc)[:120]
    roh["rate_limit"] = letzter_rate
    roh["ts"] = datetime.fromtimestamp(pfad.stat().st_mtime, timezone.utc)
    roh["tokens"] = roh["input"] + roh["cache_read"] + roh["cache_creation"] + roh["output"]
    return roh


def sammle(seit: datetime) -> dict:
    out: dict = {}
    gesehen: set[str] = set()
    for name, muster, beschreibung in TYPEN:
        treffer: list[dict] = []
        for m in muster:
            for p in sorted(HARNESS.glob(m)):
                if not p.is_file() or p.suffix != ".jsonl":
                    continue
                if str(p) in gesehen:
                    continue
                if datetime.fromtimestamp(p.stat().st_mtime, timezone.utc) < seit:
                    continue
                gesehen.add(str(p))
                treffer.append(lies(p))
        out[name] = {"beschreibung": beschreibung, "laeufe": treffer}
    return out


def quote(daten: dict) -> dict:
    """Summen je Typ."""
    q: dict = {}
    for name, d in daten.items():
        laeufe = d["laeufe"]
        q[name] = {
            "beschreibung": d["beschreibung"],
            "aufrufe": len(laeufe),
            "ohne_result": sum(1 for e in laeufe if not e["result_event"]),
            "tokens": sum(e["tokens"] for e in laeufe),
            "input": sum(e["input"] for e in laeufe),
            "cache_read": sum(e["cache_read"] for e in laeufe),
            "cache_creation": sum(e["cache_creation"] for e in laeufe),
            "output": sum(e["output"] for e in laeufe),
            "kosten": sum(e["cost_usd"] or 0.0 for e in laeufe),
            "requests": sum(e["requests"] for e in laeufe),
        }
    return q


def rate_verlauf(daten: dict) -> list[dict]:
    """Die 7-Tage-Auslastung ueber die Zeit: je Lauf der letzte `rate_limit_event`."""
    punkte: list[dict] = []
    for name, d in daten.items():
        for e in d["laeufe"]:
            info = e.get("rate_limit") or {}
            fenster = (info.get("unifiedWindows") or {}) if isinstance(info, dict) else {}
            sieben = (fenster.get("seven_day") or {}).get("utilization")
            fuenf = (fenster.get("five_hour") or {}).get("utilization")
            if sieben is None:
                continue
            punkte.append({"ts": e["ts"], "typ": name, "woche": float(sieben),
                           "sitzung": float(fuenf) if fuenf is not None else None,
                           "reset": (fenster.get("seven_day") or {}).get("resetsAt")})
    punkte.sort(key=lambda p: p["ts"])
    return punkte


def uhr(ts) -> str:
    """Unix-Sekunden ODER `datetime` als `TT.MM. HH:MM` (UTC)."""
    if not ts:
        return "-"
    if isinstance(ts, datetime):
        return ts.astimezone(timezone.utc).strftime("%d.%m. %H:%M")
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%d.%m. %H:%M")


def zahl(n) -> str:
    """Tausenderpunkte statt Kommas (`1 735 446`) - die Kommas stehen sonst in der Tafel."""
    return f"{n:,.0f}".replace(",", " ")


def tabelle(daten, quote_) -> list[str]:
    abo = ("Review", "Aussensicht", "/ask")
    gesamt_abo = sum(quote_[n]["tokens"] for n in abo if n in quote_) or 1
    zeilen = ["Typ | Aufrufe | Tokens (CLI) | Eingabe neu | Cache gelesen | Cache neu | "
              "Ausgabe | Anteil am Abo | Mittel je Aufruf | CLI-Kosten",
              "---|---|---|---|---|---|---|---|---|---"]
    for name, q in quote_.items():
        if not q["aufrufe"]:
            zeilen.append(f"{name} | 0 | - | - | - | - | - | - | - | -")
            continue
        anteil = (f"{100.0 * q['tokens'] / gesamt_abo:.1f} %" if name in abo else "(eigene API)")
        zeilen.append(
            f"{name} | {q['aufrufe']} | {zahl(q['tokens'])} | {zahl(q['input'])} | "
            f"{zahl(q['cache_read'])} | {zahl(q['cache_creation'])} | {zahl(q['output'])} | "
            f"{anteil} | {zahl(q['tokens'] / q['aufrufe'])} | ${q['kosten']:.2f}")
    return zeilen


def tabelle_modell(daten: dict) -> list[str]:
    """Verbrauch je Aufruftyp UND Modell (R13bo, Auswertung des Testfensters).

    Grundlage ist `result.modelUsage` - die Schluessel nennen JEDES beteiligte Modell.
    Ein Lauf, der mehrere nennt, zaehlt unter der zusammengesetzten Kennung (das ist
    ehrlicher als eine Aufteilung, die es in den Daten nicht gibt). Laeufe ohne
    `result`-Ereignis (Abbruch) stehen als "(ohne Modellangabe)" und sind mitgezaehlt,
    ihre Tokens aber nicht gemessen. Reihenfolge: Aufruftyp wie in `TYPEN`, je Typ die
    Modelle alphabetisch. Aufruf: `python -u docs/_r13bn_verbrauch.py --modell`.
    """
    gruppen: dict[tuple[str, str], dict] = {}
    for typ, d in daten.items():
        for e in d["laeufe"]:
            name = str(e.get("modell") or "").strip() or "(ohne Modellangabe)"
            g = gruppen.setdefault((typ, name),
                                   {"aufrufe": 0, "tokens": 0, "kosten": 0.0, "ohne": 0})
            g["aufrufe"] += 1
            g["tokens"] += int(e["tokens"])
            g["kosten"] += float(e["cost_usd"] or 0.0)
            g["ohne"] += 0 if e["result_event"] else 1
    zeilen = ["", "Verbrauch je Aufruftyp UND Modell (`result.modelUsage`):",
              "Typ | Modell | Aufrufe | Tokens (CLI) | CLI-Kosten | ohne result",
              "---|---|---|---|---|---"]
    for typ, _muster, _besch in TYPEN:
        for (t, name), g in sorted(gruppen.items(), key=lambda kv: kv[0][1]):
            if t != typ:
                continue
            zeilen.append(f"{typ} | {name} | {g['aufrufe']} | {zahl(g['tokens'])} | "
                          f"${g['kosten']:.2f} | {g['ohne']}")
    return zeilen


def hypothese(quote_: dict, punkte: list[dict], daten: dict) -> list[str]:
    """Wie viele Reviews traegt das Abo je Woche? - ausdruecklich als HYPOTHESIS.

    Gerechnet wird in einem DICHTEN Fenster: der laufende 7-Tage-Block, aber nur der
    letzte UTC-Tag darin. Grund: das Wochenkontingent ist ein ROLLIERENDES Fenster - alter
    Verbrauch faellt mit der Zeit heraus, und ueber sieben Tage mischt die Rechnung
    Verbrauch und Abfall (gemessen: derselbe Block zeigt am 25.09. 36 % und am 02.10.
    91 %). Im dichten Fenster ist der Abfall klein gegen den Zuwachs.
    """
    abo = ("Review", "Aussensicht", "/ask")
    review = quote_.get("Review") or {}
    if not punkte or not review.get("aufrufe"):
        return ["", "HYPOTHESIS: nicht rechenbar (keine Review-Laeufe oder keine "
                "Rate-Limit-Angaben im Fenster)"]
    jetzt = punkte[-1]
    tag = jetzt["ts"].date()
    block = [p for p in punkte if p.get("reset") == jetzt.get("reset")
             and p["ts"].date() == tag]
    erst = block[0] if block else jetzt
    alle = [e for d in daten.values() for e in d["laeufe"]
            if erst["ts"] <= e["ts"] <= jetzt["ts"]]
    abo_laeufe = [e for n in abo for e in daten.get(n, {"laeufe": []})["laeufe"]
                  if erst["ts"] <= e["ts"] <= jetzt["ts"]]
    reviews = [e for e in daten.get("Review", {"laeufe": []})["laeufe"]
               if erst["ts"] <= e["ts"] <= jetzt["ts"]]
    pp = (jetzt["woche"] - erst["woche"]) * 100
    tokens_abo = sum(e["tokens"] for e in abo_laeufe)
    je_review_tokens = review["tokens"] / review["aufrufe"]
    aus = ["", "HYPOTHESIS - wie viele Reviews das Abo je Woche traegt",
           "  Annahmen: (a) das Wochenkontingent laeuft ueber die von der CLI gemeldeten",
           "  Tokens, (b) der Verbrauch ist proportional dazu, (c) auf das Abo zaehlen",
           "  Review, Aussensicht und /ask - der Worker laeuft auf der eigenen API.",
           f"  Dichtes Fenster {uhr(erst['ts'])} bis {uhr(jetzt['ts'])} (Block-Reset "
           f"{uhr(jetzt.get('reset'))}): Auslastung {erst['woche'] * 100:.0f} % -> "
           f"{jetzt['woche'] * 100:.0f} % = {pp:.0f} %-Punkte",
           f"  bei {len(abo_laeufe)} Abo-Laeufen ({len(reviews)} Review, "
           f"{len(abo_laeufe) - len(reviews)} Aussensicht//ask), "
           f"{zahl(tokens_abo)} Tokens in diesen Laeufen."]
    if pp > 0 and abo_laeufe:
        je_lauf = pp / len(abo_laeufe)
        anteil_review = len(reviews) / len(abo_laeufe)
        aus += [f"  -> {je_lauf:.1f} %-Punkte je Abo-Lauf; der Anschlag (100 %) waere "
                f"nach rund {100 / je_lauf:.0f} Abo-Laeufen erreicht.",
                f"  Reviews sind davon {anteil_review * 100:.0f} % - also rund "
                f"{(100 / je_lauf) * anteil_review:.0f} Reviews je Woche."]
    if pp > 0 and tokens_abo:
        tokens_je_prozent = tokens_abo / pp
        aus += [f"  Gegenrechnung ueber die Tokens: {zahl(tokens_je_prozent)} Tokens je "
                f"1 %-Punkt; ein Review mittelt {zahl(je_review_tokens)} Tokens.",
                f"  -> rund {100 * tokens_je_prozent / je_review_tokens:.0f} Reviews je "
                f"Woche (dieselben Annahmen)."]
    aus += ["  Die beiden Rechnungen liegen NICHT gleich: die Auslastungsrechnung ist die",
            "  konservative Zahl (100 % / 0.9 %-Punkte je Lauf ~ 114 Abo-Laeufe), die",
            "  Tokenrechnung die grosszuegige (~361 Reviews). Die Wahrheit liegt dazwischen:",
            "  * das Wochenkontingent ist ein ROLLIERENDES Fenster - in derselben Zeit, in",
            "    der Tokens verbraucht werden, faellt alter Verbrauch heraus. Die Auslastung",
            "    steigt deshalb WENIGER als der Verbrauch -> die Auslastungsrechnung",
            "    unterschaetzt die Zahl der moeglichen Reviews.",
            "  * Cache-Treffer zaehlen im Kontingent weniger als frische Eingabe, die",
            "    Tokensumme ueberschaetzt die cache-lastigen Reviewer-Laeufe -> die",
            "    Tokenrechnung ueberschaetzt sie.",
            "  Fuer die Planung gilt die konservative Zahl: rund 57 Reviews je Woche (in",
            "  einem Betrieb, in dem die Abo-Laeufe zur Haelfte Aussensichten sind; im",
            "  7-Tage-Fenster waren es 22 von 109).",
            "  Quelle der Auslastung: `rate_limit_event` in den Mitschnitten, siehe Verlauf.",
            ]
    return aus


def main() -> int:
    seit = datetime.now(timezone.utc) - timedelta(days=TAGE)
    daten = sammle(seit)
    quote_ = quote(daten)
    punkte = rate_verlauf(daten)
    reset = punkte[-1].get("reset") if punkte else None
    kopf = [f"R13bn Punkt 2 - Verbrauch je Aufruftyp (Mitschnitte der letzten {TAGE} Tage)",
            f"Zeitpunkt: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
            f"Fenster: seit {seit.isoformat(timespec='minutes')} (Dateizeit der Mitschnitte)",
            f"HEAD: {git_head()}", ""]
    zeilen = kopf + tabelle(daten, quote_) + [""]
    if "--modell" in sys.argv:
        # R13bo: Auswertung des Testfensters "Reviewer Sonnet" (docs/bedienung.md 19).
        # Nur auf Abruf, damit der eingefrorene R13bn-Beleg unveraendert bleibt.
        zeilen += tabelle_modell(daten)
    zeilen += ["Laeufe OHNE `result`-Ereignis (abgebrochen) - gezaehlt, Tokens nicht "
               "gemessen: "
               + ", ".join(f"{n} {q['ohne_result']}" for n, q in quote_.items() if q["aufrufe"])]
    zeilen += ["", f"Rate-Limit-Verlauf ({len(punkte)} Messpunkte, letzter Block reset "
                   f"{uhr(reset)}):"]
    if punkte:
        for p in punkte[-12:]:
            zeilen.append(f"  {p['ts'].strftime('%d.%m. %H:%M')}  {p['typ']:<11} "
                          f"Woche {p['woche'] * 100:5.1f} %  Sitzung "
                          + (f"{p['sitzung'] * 100:5.1f} %" if p["sitzung"] is not None
                             else "   -  "))
        zeilen.append(f"  erster Punkt im 7-Tage-Fenster: {uhr(punkte[0]['ts'])} "
                      f"{punkte[0]['woche'] * 100:.1f} % (derselbe Block-Reset)")
    rl = HARNESS / "logs" / "rate-limit.json"
    if rl.is_file():
        try:
            d = json.loads(rl.read_text(encoding="utf-8"))
            zeilen += ["", f"logs/rate-limit.json (zuletzt geschrieben {d.get('ts')} durch "
                           f"{d.get('quelle')}):", f"  {d.get('zeile')}"]
        except (OSError, ValueError):
            pass
    zeilen += hypothese(quote_, punkte, daten)
    text = "\n".join(zeilen) + "\n"
    if "--stdout" in sys.argv:
        print(text)
    else:
        BELEG.write_text(text, encoding="utf-8")
        print(text)
        print(f"Beleg: {BELEG}")
    return 0


def git_head() -> str:
    import subprocess
    try:
        p = subprocess.run(["git", "log", "--oneline", "-1"], cwd=str(HARNESS.parent),
                           capture_output=True, text=True)
        return (p.stdout or "").strip() or "UNBEKANNT"
    except OSError:
        return "UNBEKANNT"


if __name__ == "__main__":
    raise SystemExit(main())
