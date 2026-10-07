"""Die Batch-Uhr (R13ac): EINE Quelle fuer "seit wann laeuft dieser Batch".

Anlass (Befund M210-1 und Punkt 5 der Nutzerpruefung 2026-09-28):

* Der **Worker** schaetzte seine Laufzeit an der Zahl der Werkzeugaufrufe und hielt
  sich in B210 fuer "~180 min", waehrend real **46 min** vergangen waren
  (`snapshots/b210/reasoning.jsonl:122,174` gegen `runs/b210/result.json`,
  `duration_s = 2771`). Mit dieser falschen Zeitnot strich er Pflichtteile.
* Die **watch-Anzeige** zaehlte dagegen ab dem Start des ZUSCHAUERS
  (`watch.Watcher.started`): "Batch 210 laufend: … 200.6 min" um 22:11, obwohl der
  Batch um 21:48 begonnen hatte und 46 min lief.

Beide Zahlen kommen deshalb jetzt aus **derselben** Quelle: `state/run.json` ->
`worker.started_at`, der Zeitstempel des Prozessstarts, den `worker.run_batch` ueber
`state.worker_started(pid, …)` setzt. Gegenprobe fuer einen **beendeten** Lauf ist
`runs/b<N>/result.json` (`duration_s`, Wanduhr des Kindprozesses).

Das Modul haelt absichtlich nur `json`/`datetime`/`pathlib` - es wird auch aus einem
Claude-Code-**Hook** importiert (`tools/batch_uhr.py`), der nach JEDEM Werkzeugaufruf
des Workers laeuft und deshalb billig bleiben muss.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

# Ein Batch laeuft nie laenger als die harte Grenze (`harness.toml: hard_wall_s`, heute
# **10800 s = 3 h**) - plus eine Stunde Luft: 4 h. Die Zahl steuert NICHTS, sie sagt nur,
# ob ein Zeitstempel GEGLAUBT wird (`start_zeit() -> unplausibel`, gezeigt in `uhr_text`
# und `watch`). Ein "Start" von vor 4 Stunden oder aus der Zukunft ist kein Messwert,
# sondern ein Rest aus einem abgebrochenen Lauf.
# R13bj hatte die Zahl auf 5 h gehoben, weil sie die harte Grenze damals von 3 h auf 4 h
# hob ("uhr.MAX_START_ALTER_S mitgezogen"). R13bl hat `hard_wall_s` auf 3 h
# zurueckgebaut, diese Zahl aber stehen lassen - damit galten Zeitstempel von 4 bis 5
# Stunden als plausibel, obwohl kein Batch so alt werden kann. R13bm (Punkt 5): zurueck
# auf die alte Regel (harte Grenze + 1 h); die Kopplung pruefen die Tests
# (`test_r13bm_fixes.TestUhrGrenze`).
MAX_START_ALTER_S = 4 * 3600.0
ZUKUNFT_TOLERANZ_S = 120.0


def lies_state(state_datei: str | Path) -> dict:
    """`state/run.json` lesen - fehlende/kaputte Datei ergibt `{}` (nie ein Fehler)."""
    try:
        with open(state_datei, "r", encoding="utf-8") as f:
            daten = json.load(f)
    except (OSError, ValueError):
        return {}
    return daten if isinstance(daten, dict) else {}


def _zeit(wert) -> datetime | None:
    """ISO-Zeitstempel (auch `…Z`) als bewusste Zeit; None, wenn unbrauchbar."""
    if not wert:
        return None
    try:
        t = datetime.fromisoformat(str(wert).replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t


def start_zeit(state: dict, jetzt: datetime | None = None) -> dict:
    """Startzeit des **laufenden** Batches aus dem Harness-Zustand.

    Rueckgabe:

    * `zeit`          - bewusste `datetime` oder None (nichts gemessen)
    * `quelle`        - woher sie kommt (`state/run.json:worker.started_at`) oder ""
    * `batch`         - Batch-Nummer des laufenden Laufs (oder None)
    * `alter_s`       - Sekunden seit dem Start (None ohne Startzeit)
    * `unplausibel`   - True, wenn der Zeitstempel aelter als `MAX_START_ALTER_S` ist
                        (Reste eines abgebrochenen Laufs) oder in der Zukunft liegt

    Die Startzeit verschwindet mit dem Ende des Laufs (`state.worker_finished` loescht
    `worker`) - dann ist hier bewusst NICHTS zu holen. Die Laufzeit eines fertigen
    Laufs steht in `runs/b<N>/result.json` (`duration_s`), nicht hier.
    """
    jetzt = jetzt or datetime.now(timezone.utc)
    w = state.get("worker") or {}
    zeit = _zeit(w.get("started_at"))
    if zeit is None:
        return {"zeit": None, "quelle": "", "batch": None, "alter_s": None,
                "unplausibel": False}
    alter = (jetzt - zeit).total_seconds()
    return {
        "zeit": zeit,
        "quelle": "state/run.json:worker.started_at",
        "batch": _batch_aus_state(state),
        "alter_s": alter,
        "unplausibel": alter > MAX_START_ALTER_S or alter < -ZUKUNFT_TOLERANZ_S,
    }


def _batch_aus_state(state: dict) -> int | None:
    """Nummer des Laufs: der Live-Eintrag ist der laufende, sonst der Zustandsbatch."""
    live = state.get("live") or {}
    b = live.get("batch") if isinstance(live, dict) else None
    if b:
        return int(b)
    b = state.get("batch")
    return int(b) if b else None


def ortszeit(zeit: datetime | None) -> str:
    """`21:48:07` in der Zeitzone des Rechners (fuer Anzeigen wie die Batch-Uhr)."""
    if zeit is None:
        return "?"
    return zeit.astimezone().strftime("%H:%M:%S")


def hms(sekunden) -> str:
    """`46m11s` bzw. `1h20m03s` - abgeschnitten, nicht gerundet (wie `stand`)."""
    try:
        gesamt = int(float(sekunden))
    except (TypeError, ValueError):
        return ""
    if gesamt < 0:
        return ""
    h, rest = divmod(gesamt, 3600)
    m, s = divmod(rest, 60)
    return (f"{h}h{m:02d}m{s:02d}s" if h else f"{m}m{s:02d}s")


def kontext_kurz(tokens) -> str:
    """`310k` / `1M` - kompakte Kontextangabe fuer die Batch-Uhr (R13ad)."""
    try:
        n = int(tokens)
    except (TypeError, ValueError):
        return "?"
    if n >= 1_000_000:
        m = n / 1_000_000.0
        return (f"{m:.0f}M" if abs(m - round(m)) < 0.05 else f"{m:.1f}M")
    if n >= 1000:
        return f"{n / 1000.0:.0f}k"
    return str(n)


# ---------------------------------------------------------------------------
# R13ao (2026-09-29, Auftrag Teil B): HINWEIS BEI ZU FRUEHEM PREFLIGHT.
# Der Preflight (`scripts/preflight.py`) gehoert ans Batch-Ende: er dauert ~10 min und
# liest den Stand, den der Batch gerade erst herstellt. Laeuft er VOR der
# Umschaltschwelle und liegt noch eine offene Nachrueckliste im Auftrag, ist er
# wertlos und muss spaeter wiederholt werden - er kostet dann doppelt. Der Hook
# (`tools/batch_uhr.py`) sagt das dem Worker, sobald der Aufruf vorbei ist:
# **Hinweis, keine Sperre** (der Worker entscheidet selbst).
#
# Der Wortlaut ist der des Auftrags vom 2026-09-29. Die Schreibweise "Umschwellschwelle"
# des Auftrags wurde am 2026-09-30 auf Nutzerwunsch zu "Umschaltschwelle" korrigiert
# (R13ap) - so heisst das Ding auch in der uebrigen Ausgabe.
#
# R13bw-17 (08.10.2026, Befund aus Batch 292): Der Text sagt jetzt, WIE die Liste
# "erledigt" gemeldet wird. Gemessen (Watch-Log 00:30, Batch-Uhr 118 min): der Worker
# hatte alle Posten fertig, hielt es "im Batch-Dokument" fest und wartete die Schranke ab -
# der Marker `NACHRUECKLISTE ERLEDIGT` stand nie als Antwortzeile, also griff die Sperre
# (S1, `worker.nachrueckliste_marker`) nicht. Der Marker zaehlt nur als eigener TEXT des
# Workers (Antwort oder `text`-Block des Mitschnitts), nicht in einem Dokument und nicht
# in einem Werkzeugaufruf.
PREFLIGHT_HINWEIS = (
    "Preflight vor der Umschaltschwelle ({minuten:.1f} von {umschalt:.0f} min). "
    "Er ist nur zulässig, wenn alle Posten der NACHRUECKLISTE erledigt sind. Ist sie "
    "erledigt, schreibe als ANTWORTTEXT eine eigene Zeile `NACHRUECKLISTE ERLEDIGT` "
    "(nicht in ein Dokument, nicht in einen Werkzeugaufruf) - danach ist der Preflight "
    "sofort erlaubt. Sonst erst die Nachrückliste abarbeiten; ein früher Preflight muss "
    "später wiederholt werden und kostet ~10 min."
)


def preflight_zu_frueh(minuten, umschalt_min) -> bool:
    """Liegt die Batch-Uhr VOR der Umschaltschwelle? (R13ao)

    Ohne Schwelle (`umschalt_min is None`) gibt es keine Aussage - dann `False`, damit
    ein unvollstaendiger Hook-Aufruf nichts behauptet.
    """
    if umschalt_min is None:
        return False
    try:
        return float(minuten) < float(umschalt_min)
    except (TypeError, ValueError):
        return False


def preflight_hinweis(minuten, umschalt_min) -> str:
    """Der Hinweistext bei zu fruehem Preflight (R13ao, Wortlaut aus dem Auftrag)."""
    return PREFLIGHT_HINWEIS.format(minuten=float(minuten or 0.0),
                                    umschalt=float(umschalt_min or 0.0))


def uhr_text(state: dict, weich_min: float, hart_min: float,
             umschalt_min: float | None = None, kontext_limit: int | None = None,
             preflight_min: float | None = None, preflight_batch: int | None = None,
             jetzt: datetime | None = None) -> str:
    """Die Zeile, die dem Worker nach jedem Werkzeugaufruf erscheint (R13ac, M210-1).

    Faktisch formuliert (die Claude-Doku raet ausdruecklich davon ab, Hooks als
    Systemanweisung zu kleiden - das loest die Prompt-Injection-Abwehr des Modells aus).

    R13ad (Auftrag 2026-09-29): die Zeile nennt jetzt auch die **Umschaltschwelle**
    (`umschalt_min`, Vorgabe: Alarmgrenze minus 15 min = `limits.umschalt_vor_alarm_s`
    900 s, R13ae) und die **Kontextgroesse** der letzten Anfrage aus dem Harness-Zustand
    (`state/run.json -> live.kontext`). Damit gibt es genau EINE Zeitquelle; der Reviewer
    schreibt keine eigene Minutenzahl mehr.

    R13ah (Aussensicht B214, Befund 3): dazu kommt **`preflight_min`** - die gemessene
    Dauer des Preflight-Aufrufs aus dem letzten Batch ("Preflight zuletzt ~10 min"). Der
    Worker sieht damit, wieviel Zeit am Batch-Ende schon verplant ist; die Schwelle ist
    um genau diese Dauer vorgezogen (`worker.umschalt_minuten`).

    R13aj: die Zahl kommt moeglicherweise aus einem **frueheren** Batch, weil der
    neueste den Aufruf nur parallel gemessen hat (dann misst sie die Wartezeit mit).
    `preflight_batch` nennt die Quelle und steht als `(B<k>)` hinter der Zahl, damit
    niemand eine alte Messung fuer die des laufenden Batches haelt.
    """
    d = start_zeit(state, jetzt=jetzt)
    if d["zeit"] is None:
        return ("BATCH-UHR (Harness-Messung): kein laufender Batch im Harness-Zustand "
                "(state/run.json hat keinen worker.started_at).")
    minuten = max(0.0, (d["alter_s"] or 0) / 60.0)
    if umschalt_min is None:
        umschalt_min = max(0.0, float(weich_min) - 15.0)
    kopf = (f"BATCH-UHR (Harness-Messung): {minuten:.1f} min von {weich_min:.0f} min "
            f"(Umschalten ab {umschalt_min:.0f}) seit Batch-Start {ortszeit(d['zeit'])} "
            "(Ortszeit).")
    live = state.get("live") if isinstance(state.get("live"), dict) else None
    k = (live or {}).get("kontext")
    if kontext_limit and k:
        kopf += f" | Kontext {kontext_kurz(k)} von {kontext_kurz(kontext_limit)}"
    if preflight_min:
        quelle = f" (B{int(preflight_batch)})" if preflight_batch else ""
        kopf += f" | Preflight zuletzt ~{float(preflight_min):.0f} min{quelle}"
    rest = (f"Weichgrenze {weich_min:.0f} min, harte Grenze {hart_min:.0f} min, "
            f"Umschaltschwelle {umschalt_min:.0f} min (Alarmgrenze minus Vorlauf) - diese "
            "Zahl ist die Wanduhr des "
            "Worker-Prozesses "
            "(state/run.json:worker.started_at) - die Zahl der Werkzeugaufrufe sagt "
            "nichts ueber die Zeit (B210: '180 min' geschaetzt, 46 min gemessen).")
    if preflight_min:
        rest += (" Der Vorlauf enthaelt den Preflight (gemessen "
                 f"~{float(preflight_min):.0f} min) plus 5 min fuer Bilanz/Export.")
    if d["unplausibel"]:
        rest += (" HINWEIS: der Zeitstempel ist unplausibel alt - er kann aus einem "
                 "abgebrochenen Lauf stammen; bitte mit Get-Date gegenpruefen.")
    return kopf + " " + rest
