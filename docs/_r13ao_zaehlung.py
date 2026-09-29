"""R13ao: `preflight_laeufe` fuer B206-B215 aus den Mitschnitten (nur Bericht).

Der Auftrag (Teil B) verlangt **nur einen Bericht**: wie oft lief der Preflight in den
abgeschlossenen Batches? Der Zaehler, den der Harness ab jetzt selbst schreibt
(`result.json: preflight_laeufe`), existiert fuer diese Batches noch nicht - der Hook
bekommt das Laufverzeichnis (`--run`) erst mit dieser Fassung. Deshalb wird hier
**nachgezaehlt**, mit derselben Regel wie der Hook
(`hx.streamjson.ist_preflight_aufruf`: Shell-Werkzeug, Interpreter + `preflight.py` als
Argument, und der Befehlsteil ist kein Filter).

Weil die blosse Textsuche nach `preflight.py` viel haeufiger ist als ein echter Start,
steht **beides** nebeneinander: `Starts` (gezaehlt wie der Hook) und `nur genannt`
(Treffer der reinen Textsuche, die KEIN Aufruf sind - gemessen: `Select-String -Path
scripts/preflight.py`, `git add … scripts/preflight.py`, `Get-CimInstance … -like
'*preflight.py*before*'`).

Zusaetzlich - ausdruecklich als **Rekonstruktion** markiert - der Abstand des ersten
echten Starts vom Batch-Anfang und die Umschaltschwelle. Ob die Nachrueckliste in
diesem Moment offen war, laesst sich nachtraeglich NICHT feststellen (das war eine
Laufzeit-Eigenschaft; der Auftrag ist statisch, der Stand der Liste nicht) - die Spalte
nennt nur, ob der Auftrag ueberhaupt eine NACHRUECKLISTE traegt.

Aufruf:  python -u docs/_r13ao_zaehlung.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HIER = Path(__file__).resolve().parent
ROOT = HIER.parent                     # g:\Harness
sys.path.insert(0, str(ROOT / "harness"))

from hx import streamjson, worker                       # noqa: E402
from hx.config import load_config                        # noqa: E402
from hx.util import read_json, read_text                 # noqa: E402

RUNS = ROOT / "harness" / "runs"
BEREICH = range(206, 216)


def _zeit(wert) -> datetime | None:
    if not wert:
        return None
    try:
        t = datetime.fromisoformat(str(wert).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _mitschnitt(n: int):
    """Zeilen des Mitschnitts (auch als `.zip` gepackt) - oder None."""
    p = RUNS / f"b{n:03d}" / "stream.jsonl"
    if p.is_file():
        return p.read_text(encoding="utf-8", errors="replace").splitlines()
    z = RUNS / f"b{n:03d}" / "stream.zip"
    if z.is_file():
        import zipfile
        with zipfile.ZipFile(z) as fh:
            return fh.read("stream.jsonl").decode("utf-8", "replace").splitlines()
    return None


def zeile_fuer(n: int, umschalt_min: float) -> dict:
    aus = {"batch": n, "laeufe": None, "nur_genannt": None, "erste_min": None,
           "frueh": "", "nachrueckliste": "", "hinweis": ""}
    auftrag = read_text(RUNS / f"b{n:03d}" / "auftrag.md")
    aus["nachrueckliste"] = "ja" if (auftrag and worker.hat_nachrueckliste(auftrag)) else "-"
    zeilen = _mitschnitt(n)
    if not zeilen:
        aus["hinweis"] = "kein Mitschnitt"
        return aus
    stats = streamjson.StreamStats()
    for z in zeilen:
        stats.feed(z)
    aufrufe = [t for t in stats.tools
               if streamjson.ist_preflight_aufruf(t.get("name"), t.get("input"))]
    nennt = sum(1 for t in stats.tools
                if streamjson.nennt_preflight_nur(t.get("name"), t.get("input")))
    aus["laeufe"] = len(aufrufe)
    aus["nur_genannt"] = max(0, nennt - len(aufrufe))
    if not aufrufe:
        return aus
    # Bezugspunkt ist der ERSTE Ereignis-Zeitstempel im Mitschnitt (die erste Zeile ist
    # die `system`/`init`-Zeile OHNE Zeitstempel). Er liegt Sekunden nach dem
    # Harness-Start - die Spalte ist deshalb eine Naeherung auf ~1 min und als solche
    # gekennzeichnet.
    erst = None
    for z in zeilen[:200]:
        try:
            erst = _zeit(json.loads(z).get("timestamp"))
        except ValueError:
            erst = None
        if erst:
            break
    ts = _zeit(aufrufe[0].get("ts"))
    if erst and ts:
        minuten = round((ts - erst).total_seconds() / 60.0, 1)
        aus["erste_min"] = minuten
        aus["frueh"] = "ja" if minuten < umschalt_min else "nein"
    else:
        aus["hinweis"] = "kein Zeitstempel im Mitschnitt"
    return aus


def main() -> int:
    cfg = load_config()
    u = worker.umschalt_minuten(cfg, None)
    umschalt = float(u["umschalt_min"])
    print("R13ao: Preflight-Aufrufe je Batch (Nachzaehlung aus den Mitschnitten)")
    print("Start-Regel: hx.streamjson.ist_preflight_aufruf (Shell-Werkzeug, Interpreter "
          "+ 'preflight.py' als Argument, Befehlsteil kein Filter)")
    print("Quelle: harness/runs/b<N>/stream.jsonl")
    print(f"Umschaltschwelle heute: {umschalt:.0f} min "
          f"(Alarm {u['alarm_min']:.0f} min minus Vorlauf {u['vorlauf_min']:.1f} min; "
          f"Preflight zuletzt ~{u['preflight_min']:.1f} min aus B{u['preflight_batch']})")
    print()
    kopf = (f"{'Batch':>5}  {'Starts':>6}  {'nur genannt':>11}  "
            f"{'1. Start ab Batch-Anfang':>25}  {'frueh?':>6}  {'NACHRUECKLISTE':>14}  "
            "Hinweis")
    print(kopf)
    print("-" * len(kopf))
    summe = 0
    genannt = 0
    anzahl_batches = 0
    frueh = 0
    for n in BEREICH:
        z = zeile_fuer(n, umschalt)
        if z["laeufe"] is None:
            print(f"{z['batch']:>5}  {'-':>6}  {'-':>11}  {'-':>25}  {'-':>6}  "
                  f"{z['nachrueckliste']:>14}  {z['hinweis']}")
            continue
        anzahl_batches += 1
        summe += z["laeufe"]
        genannt += z["nur_genannt"]
        if z["frueh"] == "ja":
            frueh += 1
        erste = "-" if z["erste_min"] is None else f"{z['erste_min']:.1f} min"
        print(f"{z['batch']:>5}  {z['laeufe']:>6}  {z['nur_genannt']:>11}  "
              f"{erste:>25}  {z['frueh'] or '-':>6}  {z['nachrueckliste']:>14}  "
              f"{z['hinweis']}")
    print()
    print(f"Summe ueber {anzahl_batches} Batches mit Mitschnitt: {summe} echte "
          f"Preflight-Starts")
    print(f"daneben {genannt} Treffer, die 'preflight.py' nur GENANNT haben (keine "
          f"Starts, nicht gezaehlt)")
    print(f"davon Batches mit dem ersten Start VOR der Schwelle (rekonstruiert): {frueh}")
    print()
    print("Lesehilfe: 'Starts' ist die Zahl der WERKZEUGAUFRUFE, die den Preflight "
          "starten - derselbe Befehl zweimal zaehlt zweimal. Das ist die Definition von "
          "'preflight_laeufe' im Hook; 'preflight_frueh' (vor der Schwelle MIT offener "
          "Nachrueckliste) laesst sich fuer diese Batches NICHT nachzaehlen und steht "
          "deshalb hier nicht. '1. Start ab Batch-Anfang' bezieht sich auf den ersten "
          "Zeitstempel im Mitschnitt (Naeherung auf ~1 min, der Harness-Start liegt "
          "Sekunden davor).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
