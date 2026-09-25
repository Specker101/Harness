"""Tarife und Peak-/Off-Peak-Fenster (offiziell belegt, in UTC gerechnet).

Quelle: https://api-docs.deepseek.com/quick_start/pricing, Fussnote (2)
  "Peak hours are 01:00 - 04:00 and 06:00 - 10:00 UTC, Monday through Friday,
   excluding Chinese public holidays. All other hours are off-peak, including
   weekends and Chinese public holidays in full."
Umrechnung nach Europe/Berlin (nur Anzeige; gerechnet wird immer in UTC):
  Sommerzeit (CEST, UTC+2): 03:00-06:00 und 08:00-12:00
  Winterzeit (CET,  UTC+1): 02:00-05:00 und 07:00-11:00
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

# Preise deepseek-flash, USD je 1M Token
RATES = {
    "offpeak": {"cache_hit": 0.003, "cache_miss": 0.15, "output": 0.60},
    "peak": {"cache_hit": 0.006, "cache_miss": 0.30, "output": 1.20},
}

# Peak-Fenster in UTC (Stunden, halboffen [start, end))
PEAK_WINDOWS_UTC = ((1, 4), (6, 10))


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_peak(dt: datetime | None = None, extra_offpeak_dates: list[str] | None = None) -> bool:
    """True, wenn der Zeitpunkt im Peak-Tarif liegt."""
    dt = _as_utc(dt or datetime.now(timezone.utc))
    if dt.weekday() >= 5:  # Samstag/Sonntag: immer off-peak
        return False
    day = dt.date().isoformat()
    if extra_offpeak_dates and day in set(extra_offpeak_dates):
        return False  # chinesischer Feiertag
    for start, end in PEAK_WINDOWS_UTC:
        if start <= dt.hour < end:
            return True
    return False


def next_offpeak(dt: datetime | None = None, extra_offpeak_dates: list[str] | None = None) -> datetime:
    """Naechster Zeitpunkt (UTC), ab dem ein neuer Batch starten darf."""
    dt = _as_utc(dt or datetime.now(timezone.utc))
    probe = dt.replace(minute=0, second=0, microsecond=0)
    for _ in range(0, 8 * 24):
        if not is_peak(probe, extra_offpeak_dates):
            return max(probe, dt)
        probe = probe + timedelta(hours=1)
    return dt + timedelta(days=1)


def tariff(dt: datetime | None = None, extra_offpeak_dates: list[str] | None = None) -> str:
    return "peak" if is_peak(dt, extra_offpeak_dates) else "offpeak"


def rates_for(dt: datetime | None = None, extra_offpeak_dates: list[str] | None = None) -> dict:
    return RATES[tariff(dt, extra_offpeak_dates)]


def cost_usd(input_miss: int, cache_read: int, cache_creation: int, output: int,
             dt: datetime | None = None, extra_offpeak_dates: list[str] | None = None) -> float:
    """Kosten eines Aufrufs nach dem Tarif SEINES Zeitpunkts."""
    r = rates_for(dt, extra_offpeak_dates)
    miss = (input_miss or 0) + (cache_creation or 0)
    return (miss * r["cache_miss"] + (cache_read or 0) * r["cache_hit"] + (output or 0) * r["output"]) / 1_000_000.0


# --------------------------------------------------------------- Anzeige

def berlin_offset_hours(dt_utc: datetime) -> int:
    """EU-Regel: letzter Sonntag im Maerz 01:00 UTC -> +2, letzter Sonntag im Oktober 01:00 UTC -> +1."""
    dt_utc = _as_utc(dt_utc)
    y = dt_utc.year

    def last_sunday(year: int, month: int) -> datetime:
        day = 31
        while True:
            try:
                d = datetime(year, month, day, 1, 0, tzinfo=timezone.utc)
                break
            except ValueError:
                day -= 1
        while d.weekday() != 6:
            d = d - timedelta(days=1)
        return d

    start = last_sunday(y, 3)
    end = last_sunday(y, 10)
    return 2 if start <= dt_utc < end else 1


def local_window_text(dt: datetime | None = None) -> str:
    """Anzeigetext der Peak-Fenster in Ortszeit (Europe/Berlin)."""
    dt = _as_utc(dt or datetime.now(timezone.utc))
    off = berlin_offset_hours(dt)
    parts = []
    for start, end in PEAK_WINDOWS_UTC:
        parts.append("%02d:00-%02d:00" % ((start + off) % 24, (end + off) % 24))
    zone = "CEST" if off == 2 else "CET"
    return f"{parts[0]} und {parts[1]} Ortszeit ({zone})"


def status_line(cfg, dt: datetime | None = None) -> str:
    dt = _as_utc(dt or datetime.now(timezone.utc))
    extra = list(cfg.get("peak", "extra_offpeak_dates", []) or [])
    now_t = tariff(dt, extra)
    nxt = next_offpeak(dt, extra) if now_t == "peak" else None
    txt = f"Tarif jetzt: {now_t.upper()} (UTC {dt.strftime('%a %H:%M')})"
    if nxt:
        txt += f"; naechster Off-Peak: {nxt.strftime('%Y-%m-%d %H:%M')} UTC"
    return txt
