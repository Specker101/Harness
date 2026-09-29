"""Sonde (nur lesend, R13al Punkt 5): wie oft startete ein Batch im PEAK-Tarif?

Der Auftrag nennt als Quelle "die Zeitstempel 'Starte Batch' in logs/". **Diese Zeile
existiert nicht**: `Orchestrator.say()` schickt nur per Telegram und schreibt nichts ins
Log (gemessen: die `logs/harness-*.log` enthalten Git-Checkpoint, Batch beendet,
Queue zugestellt … aber kein "Starte Batch"). Geprueft werden deshalb die zwei belastbaren
Spuren je Batch:

  1. `runs/b<N>/auftrag.md` -> "Batch-Start (Harness-Zeitstempel): HH:MM:SS Ortszeit am
     YYYY-MM-DD" (Ortszeit Europe/Berlin, unmittelbar vor dem Prozessstart),
  2. `runs/b<N>/result.json` -> `finished_at` minus `duration_s` (Wanduhr des Workers).

Peak laut DeepSeek-Preisseite: 01:00-04:00 und 06:00-10:00 UTC, Mo-Fr, ohne chinesische
Feiertage (Liste `[peak] extra_offpeak_dates`).
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

HIER = Path(__file__).resolve().parent                # docs/
HARNESS = HIER.parent / "harness"
sys.path.insert(0, str(HARNESS))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                            # noqa: BLE001
    pass

from hx import pricing                                       # noqa: E402
from hx.config import load_config                            # noqa: E402

RE_START = re.compile(r"Batch-Start \(Harness-Zeitstempel\):\s*(\d{2}):(\d{2}):(\d{2}) "
                      r"Ortszeit am (\d{4})-(\d{2})-(\d{2})")


def aus_auftrag(pfad: Path) -> datetime | None:
    """Startzeit aus dem Vorspann (Ortszeit) -> UTC."""
    if not pfad.is_file():
        return None
    m = RE_START.search(pfad.read_text(encoding="utf-8", errors="replace"))
    if not m:
        return None
    hh, mm, ss, y, mo, d = (int(g) for g in m.groups())
    return datetime(y, mo, d, hh, mm, ss).astimezone().astimezone(timezone.utc)


def aus_result(pfad: Path) -> tuple[datetime, datetime] | None:
    """(Start, Ende) aus `finished_at` minus `duration_s`."""
    if not pfad.is_file():
        return None
    try:
        d = json.loads(pfad.read_text(encoding="utf-8", errors="replace"))
        ende = datetime.fromisoformat(str(d["finished_at"]).replace("Z", "+00:00"))
        dauer = float(d.get("duration_s") or 0.0)
    except (OSError, ValueError, KeyError):
        return None
    return (ende.astimezone(timezone.utc) - timedelta(seconds=dauer),
            ende.astimezone(timezone.utc))


def startzeit(p: Path) -> datetime | None:
    a = aus_auftrag(p.parent / "auftrag.md")
    if a is not None:
        return a
    r = aus_result(p)
    return r[0] if r else None


def main() -> int:
    cfg = load_config()
    extra = list(cfg.get("peak", "extra_offpeak_dates", []) or [])
    print(f"### Feiertagsliste (off-peak): {extra or '(leer)'}")
    print(f"### Peak-Fenster UTC: {', '.join('%02d-%02d' % f for f in pricing.PEAK_WINDOWS_UTC)}"
          " (Mo-Fr)\n")
    print(f"{'Batch':7} {'Start (UTC)':21} {'Tarif':8} {'Ende (UTC)':21} {'Dauer':9} Tag")
    im_peak: list[str] = []
    knapp: list[str] = []
    n = 0
    for p in sorted((HARNESS / "runs").glob("b*/result.json")):
        start = startzeit(p)
        if start is None:
            continue
        r = aus_result(p)
        tarif = pricing.tariff(start, extra)
        dauer = (r[1] - r[0]).total_seconds() if r else 0.0
        n += 1
        print(f"{p.parent.name:7} {start.strftime('%Y-%m-%d %H:%M:%S'):21} {tarif:8} "
              f"{(r[1].strftime('%Y-%m-%d %H:%M:%S') if r else '-'):21} "
              f"{(f'{dauer / 60:.0f} min' if dauer else '-'):9} {start.strftime('%a')}"
              + ("   <- PEAK" if tarif == "peak" else ""))
        if tarif == "peak":
            im_peak.append(p.parent.name)
        else:
            nxt = pricing.next_peak_start(start, extra)
            if nxt is not None and (nxt - start) <= timedelta(minutes=90):
                knapp.append(f"{p.parent.name} ({int((nxt - start).total_seconds() // 60)}"
                             " min vor Peak)")
    print(f"\nGeprueft: {n} Batches mit Ergebnisdatei")
    print(f"Im PEAK gestartet: {len(im_peak)}"
          + (f" -> {', '.join(im_peak)}" if im_peak else ""))
    print(f"Off-peak, aber < 90 min vor einem Peak-Fenster: {len(knapp)}"
          + (f" -> {', '.join(knapp)}" if knapp else ""))
    stunden: Counter = Counter()
    peak_stunden: Counter = Counter()
    for p in sorted((HARNESS / "runs").glob("b*/result.json")):
        s = startzeit(p)
        if s:
            stunden[(s.strftime("%a"), s.hour)] += 1
            if pricing.tariff(s, extra) == "peak":
                peak_stunden[(s.strftime("%a"), s.hour)] += 1
    print("\nStartstunden (UTC) - die Marke gilt nur, wenn Wochentag UND Stunde Peak sind:")
    for (tag, std), k in sorted(stunden.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        marke = " <- PEAK" if peak_stunden.get((tag, std)) else ""
        print(f"  {tag} {std:02d}:00  {k:3}{marke}")
    print("  (Sa/So sind immer off-peak - deshalb tragen die Nachtstunden oben keine Marke.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
