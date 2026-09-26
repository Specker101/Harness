"""Laufzeit zerlegen: Wie viel Zeit steckt in Werkzeugen, wie viel im Modell?

Frage (Nutzer, 2026-09-26): manche Batches dauern lange und verbrauchen dabei wenig
Tokens - Verdacht: lange Python-Aufrufe. Dieses Werkzeug beantwortet das aus den
vorhandenen Mitschnitten, es wird NICHTS geschaetzt:

  * `duration_s`    = Selbstauskunft des claude-Prozesses (`duration_ms`)
  * `duration_harness_s` = Wanduhr, die der Harness selbst gemessen hat
  * Werkzeugzeit    = Zeitspanne vom `tool_use` bis zum zugehoerigen `tool_result`
  * Modellzeit      = Zeitspanne zwischen zwei Ereignissen, in der KEIN Werkzeug lief
  * Rest            = Wanduhr minus (Werkzeugzeit + Modellzeit): Harness-Anteil
                      (Mitschnitt schreiben, Takt, Zustandswechsel)

Aufruf:
    python -u tools\\analyse_laufzeit.py                 # alle Batches
    python -u tools\\analyse_laufzeit.py --batch 175     # einer, mit Top-Werkzeugen
    python -u tools\\analyse_laufzeit.py --write         # Beleg nach docs/
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx.config import load_config                                    # noqa: E402
from hx.util import read_text                                        # noqa: E402


def ts(wert: str) -> float | None:
    """ISO-Zeitstempel in Sekunden (None, wenn unbrauchbar)."""
    if not wert:
        return None
    try:
        return datetime.fromisoformat(str(wert).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def kurz(eingabe, grenze: int = 110) -> str:
    if isinstance(eingabe, str):
        text = eingabe
    elif isinstance(eingabe, dict):
        for feld in ("command", "file_path", "path", "pattern", "prompt", "query"):
            if eingabe.get(feld):
                text = str(eingabe[feld])
                break
        else:
            text = json.dumps(eingabe, ensure_ascii=False)
    else:
        text = str(eingabe)
    return " ".join(text.split())[:grenze]


def zerlege(stream: Path) -> dict:
    """Mitschnitt in Werkzeugzeit / Modellzeit / Luecken zerlegen."""
    offen: dict[str, dict] = {}          # tool_use.id -> {t0, name, kurz}
    werkzeuge: list[dict] = []
    ereignisse: list[float] = []
    t_start = t_ende = None

    for line in read_text(stream).splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(ev, dict):
            continue
        t = ts(ev.get("timestamp"))
        if t:
            ereignisse.append(t)
            t_start = t if t_start is None else min(t_start, t)
            t_ende = t if t_ende is None else max(t_ende, t)
        typ = ev.get("type")
        if typ == "assistant":
            for b in ((ev.get("message") or {}).get("content") or []):
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    offen[str(b.get("id"))] = {"t0": t, "name": b.get("name") or "?",
                                               "kurz": kurz(b.get("input"))}
        elif typ == "user":
            for b in ((ev.get("message") or {}).get("content") or []):
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    e = offen.pop(str(b.get("tool_use_id")), None)
                    if e and e.get("t0") and t:
                        werkzeuge.append({"name": e["name"], "kurz": e["kurz"],
                                          "dauer": max(0.0, t - e["t0"])})
    # Zeit, in der kein Werkzeug lief = Modellzeit (Denken + API).
    werkzeug_summe = sum(w["dauer"] for w in werkzeuge)
    spanne = (t_ende - t_start) if (t_start and t_ende) else 0.0
    return {"werkzeuge": sorted(werkzeuge, key=lambda w: -w["dauer"]),
            "werkzeug_summe": werkzeug_summe, "spanne": spanne,
            "modellzeit": max(0.0, spanne - werkzeug_summe), "start": t_start,
            "ende": t_ende, "ereignisse": len(ereignisse)}


def _regex_sleeps():
    import re
    # Start-Sleep -Seconds N  |  Start-Sleep N  |  sleep N  |  -Milliseconds N
    return re.compile(r"start-sleep\s+(?:-seconds\s+)?(\d+(?:\.\d+)?)"
                      r"|start-sleep\s+-milliseconds\s+(\d+)"
                      r"|\bsleep\s+(\d+)\b", re.IGNORECASE)


def wartezeiten(stream: Path, zeigen: int = 0) -> tuple[int, float, int]:
    """Reine Wartebefehle zaehlen: (Anzahl, Summe Sekunden, Poll-Schleifen).

    `Start-Sleep` in grossen Schritten ist die teuerste Form von Wartezeit: sie
    kostet keine Tokens, aber garantiert Wanduhr - auch wenn die Arbeit schon
    fertig ist (Nutzerbefund 2026-09-26).
    """
    muster = _regex_sleeps()
    n = 0
    summe = 0.0
    schleifen = 0
    for line in read_text(stream).splitlines():
        if "tool_use" not in line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(ev, dict):
            continue
        msg = ev.get("message")
        if not isinstance(msg, dict):
            continue
        for b in (msg.get("content") or []):
            if not (isinstance(b, dict) and b.get("type") == "tool_use"):
                continue
            cmd = ""
            if isinstance(b.get("input"), dict):
                cmd = str(b["input"].get("command") or "")
            if not cmd:
                continue
            treffer = muster.findall(cmd)
            if treffer and zeigen:
                print(f"    WARTE: {kurz(cmd, 240)}")
                if zeigen > 1:
                    zeigen -= 1
            for t in treffer:
                n += 1
                sek = float(t[0]) if t[0] else (float(t[1]) / 1000.0 if t[1] else float(t[2]))
                summe += sek * (24 if "for ($i" in cmd else 1)
            m = _regex_schleife().search(cmd)
            if m and treffer:
                schleifen += 1
    return n, summe, schleifen


def _regex_schleife():
    import re
    return re.compile(r"for\s*\(\s*\$[a-z]+\s*=\s*0;", re.IGNORECASE)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=0, help="nur dieser Batch, mit Top-Liste")
    ap.add_argument("--top", type=int, default=10, help="wie viele Werkzeuge auflisten")
    ap.add_argument("--write", action="store_true", help="Beleg nach docs/ schreiben")
    a = ap.parse_args()
    cfg = load_config()

    zeilen = ["Laufzeit-Analyse (aus den Mitschnitten, nichts geschaetzt)",
              "  Werkz = Summe der Werkzeuglaufzeiten (tool_use -> tool_result)",
              "  Modell = Spanne minus Werkz (Denken/API)", ""]
    kopf = (f"  {'Batch':>5} {'claude_s':>9} {'harness_s':>10} {'Werkz_s':>8} {'Modell_s':>9} "
            f"{'Rest_s':>7} {'Anfr':>5} {'out_tok':>8} {'Kosten':>9} {'Warte_n':>8} {'Warte_s':>8}")
    zeilen.append(kopf)

    batches = sorted(p for p in Path(cfg.sub("runs")).glob("b1*") if (p / "result.json").is_file())
    if a.batch:
        batches = [p for p in batches if p.name == f"b{a.batch:03d}"] or batches
    for d in batches:
        res = json.loads((d / "result.json").read_text(encoding="utf-8"))
        z = zerlege(d / "stream.jsonl") if (d / "stream.jsonl").is_file() else None
        dh = float(res.get("duration_harness_s") or 0)
        rest = dh - (z["spanne"] if z else 0.0)
        wn, ws, wl = wartezeiten(d / "stream.jsonl") if (d / "stream.jsonl").is_file() else (0, 0.0, 0)
        zeilen.append(
            f"  {res.get('batch'):>5} {float(res.get('duration_s') or 0):>9.0f} {dh:>10.0f} "
            f"{(z['werkzeug_summe'] if z else 0):>8.0f} {(z['modellzeit'] if z else 0):>9.0f} "
            f"{rest:>7.0f} {(res.get('stats') or {}).get('requests'):>5} "
            f"{(res.get('stats') or {}).get('output'):>8} "
            f"${float(res.get('cost_usd') or 0):>8.4f} {wn:>8} {ws:>8.0f}")
        if a.batch and z:
            zeilen += ["", f"  Top-Werkzeuge in {d.name}:"]
            for w in z["werkzeuge"][:a.top]:
                zeilen.append(f"    {w['dauer']:>8.1f}s  {w['name']:<12s} {w['kurz']}")
            werk = [w for w in z["werkzeuge"] if w["dauer"] >= 60]
            zeilen.append(f"    ({len(werk)} Aufrufe >= 60 s, Gesamtzeit darin "
                          f"{sum(w['dauer'] for w in werk):.0f} s)")

    text = "\n".join(zeilen)
    print(text)
    if a.write:
        p = Path("g:/Harness/docs/_laufzeit_analyse.txt")
        p.write_text(text + "\n", encoding="utf-8")
        print(f"\nBeleg: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
