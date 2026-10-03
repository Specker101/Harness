"""R13bo-5 Punkt 5 - NUR MESSEN: Verbrauch seit dem Neustart (Verfahren R13bn-2).

Wiederverwendet `docs/_r13bn_verbrauch.py` unveraendert (Tokens/Kosten aus dem
`result`-Ereignis der Mitschnitte) und beschraenkt das Fenster auf die Zeit SEIT DEM
NEUSTART. Der Neustart steht in `g:\Harness\harness\logs\start-stderr.log`:
  "=== Start 2026-10-02 21:44:00 : -u -m hx.cli --config … run ==="
Das ist LOKALE Zeit (UTC+2) -> 2026-10-02 19:44:00 UTC.

Aufruf:  python -u docs/_r13bo5_verbrauch.py            (Beleg schreiben)
         python -u docs/_r13bo5_verbrauch.py --stdout   (nur zeigen)

Der Beleg wird als UTF-8 mit LF geschrieben (R382/`_r13av_lauf.py`-Muster) - eine
Konsolen-Pipe verstuemmelt Umlaute. `docs/_r13bn_verbrauch.txt` bleibt UNBERUEHRT
(eingefrorener R13bn-Beleg).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HIER = Path(__file__).resolve().parent
HARNESS = HIER.parent / "harness"
BELEG = HIER / "_r13bo5_verbrauch.txt"
NEUSTART = datetime(2026, 10, 2, 19, 44, tzinfo=timezone.utc)

_spec = importlib.util.spec_from_file_location("r13bn_verbrauch",
                                               HIER / "_r13bn_verbrauch.py")
b = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(b)                                   # nur Definitionen


def kopf(daten: dict) -> list[str]:
    import subprocess
    try:
        head = subprocess.run(["git", "log", "-1", "--pretty=%h %s"], cwd=str(HIER.parent),
                              capture_output=True, text=True, timeout=30).stdout.strip()
    except OSError:
        head = "UNBEKANNT"
    return ["R13bo-5 Punkt 5 - Verbrauch seit dem Neustart (Verfahren R13bn-2)",
            f"Zeitpunkt: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
            "Neustart: 2026-10-02 21:44:00 lokal (UTC+2) = 2026-10-02T19:44:00Z "
            "(logs/start-stderr.log)",
            f"Fenster: Mitschnitte mit Dateizeit >= {NEUSTART.isoformat(timespec='minutes')}",
            f"HEAD: {head}",
            "Quelle der Zahlen: `result`-Ereignis der CLI (Tokens, total_cost_usd, "
            "num_turns); Modell aus `result.modelUsage`.",
            ""]


def main() -> int:
    daten = b.sammle(NEUSTART)
    quote_ = b.quote(daten)
    punkte = b.rate_verlauf(daten)
    zeilen = kopf(daten)
    zeilen += b.tabelle(daten, quote_) + [""]
    zeilen += b.tabelle_modell(daten) + [""]
    zeilen += ["Rate-Limit-Verlauf seit dem Neustart "
               f"({len(punkte)} Messpunkte):",
               "  Zeit (UTC) | Aufruftyp | Woche | Sitzung"]
    for p in punkte:
        sitzung = (f"{p['sitzung'] * 100:5.1f} %" if p["sitzung"] is not None else "  -  ")
        zeilen.append(f"  {p['ts'].strftime('%d.%m. %H:%M')} | {p['typ']:<11} "
                      f"| {p['woche'] * 100:5.1f} % | {sitzung}")
    rl = HARNESS / "logs" / "rate-limit.json"
    if rl.is_file():
        try:
            d = json.loads(rl.read_text(encoding="utf-8"))
            zeilen += ["", f"logs/rate-limit.json (zuletzt {d.get('ts')} durch "
                           f"{d.get('quelle')}):", f"  {d.get('zeile')}"]
        except (OSError, ValueError):
            pass
    text = "\n".join(zeilen) + "\n"
    if "--stdout" in sys.argv:
        print(text)
    else:
        BELEG.write_text(text, encoding="utf-8", newline="\n")
        print(text)
        print(f"Beleg: {BELEG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
