"""Batch-Uhr als Claude-Code-Hook (R13ac, Befund M210-1).

Wird vom Harness als `PostToolUse`-Hook in die Worker-Sitzung gehaengt (Einstellungsdatei
`runs/b<N>/worker-hooks.json`, erzeugt in `hx/worker.py`). Der Hook laeuft nach JEDEM
Werkzeugaufruf und gibt eine Zeile `additionalContext` aus - die Claude-CLI haengt sie
als System-Reminder neben das Werkzeugergebnis, das Modell liest sie beim naechsten
Aufruf (Doku "Hooks reference", Abschnitt "Add context for Claude").

    python tools/batch_uhr.py --state <state/run.json> --weich 90 --hart 180 \
        --umschalt 80 --preflight-min 10.0 --preflight-batch 214 \
        --kontext-limit 1000000 --run <runs/b<N>>

Quelle der Zahl ist dieselbe wie in der watch-Anzeige: `hx.uhr` liest
`state/run.json -> worker.started_at` (Prozessstart des Workers). Gegenprobe fuer einen
beendeten Lauf ist `runs/b<N>/result.json:duration_s`.

**R13ao (2026-09-29, Auftrag Teil B) - Hinweis bei zu fruehem Preflight.** Enthaelt ein
Shell-Aufruf `preflight.py`, liegt die Batch-Uhr VOR der Umschaltschwelle und traegt
`auftrag.md` eine `NACHRUECKLISTE` (`hx.worker.hat_nachrueckliste`), haengt der Hook den
Hinweis aus `hx.uhr.PREFLIGHT_HINWEIS` an. **Kein Blockieren** - der Worker entscheidet
selbst. Je erkanntem Preflight-Aufruf wird eine Zeile an
`runs/b<N>/preflight-aufrufe.jsonl` geschrieben (`{"ts", "min", "frueh"}`);
`hx.worker._finish_run` zaehlt sie nach `result.json` (`preflight_laeufe`,
`preflight_frueh`). Ohne `--run` (Einstellungsdatei eines schon laufenden Batches aus
aelterer Fassung) wird **nichts** geschrieben und **nichts** behauptet.

**Kein Fehler darf den Batch stoeren**: bei jedem Problem wird nichts ausgegeben (bzw.
nur die Uhr-Zeile) und mit 0 beendet (der Hook ist dann wirkungslos, der Lauf geht
weiter).
"""

from __future__ import annotations

import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ZAHL_DATEI = "preflight-aufrufe.jsonl"
# R13be-2: der einmalige Stopp je Batch. Die Datei ist die Marke - sie entsteht beim
# ersten Block UND ist der Beleg (Zeile je Stopp mit Zeit und Minute).
BLOCK_DATEI = "preflight-blockiert.jsonl"
# Wortlaut aus dem Nutzerauftrag (01.10.2026): der Worker soll den Stopp nicht als
# Verbot lesen, sondern als Nachfrage, die er begruendet beantworten kann.
BLOCK_ZUSATZ = ("Falls alle Posten erledigt sind oder ein Posten belegt blockiert ist: "
                "das im Batch-Dokument festhalten und den Preflight erneut starten.")


def _stdin_json() -> dict:
    """Die Hook-Eingabe lesen (PostToolUse). Leer/kaputt -> `{}`."""
    try:
        roh = sys.stdin.read()
    except Exception:                                                     # noqa: BLE001
        return {}
    if not roh or not roh.strip():
        return {}
    try:
        daten = json.loads(roh)
    except ValueError:
        return {}
    return daten if isinstance(daten, dict) else {}


def _nachrueckliste_offen(lauf: Path | None) -> bool:
    """Traegt `auftrag.md` dieses Laufs eine NACHRUECKLISTE? (R13ao)

    Der Import von `hx.worker`/`hx.util` steht ABSICHTLICH hier drin: er kostet ~0,1 s
    und wird nur gebraucht, wenn wirklich ein Preflight-Aufruf vorliegt - die Uhr-Zeile
    selbst darf billig bleiben. Die Regel ist dieselbe wie im Harness
    (`hat_nachrueckliste`), sie wird nicht nachgebaut.
    """
    if lauf is None:
        return False
    p = Path(lauf) / "auftrag.md"
    if not p.is_file():
        return False
    from hx.util import read_text
    from hx.worker import hat_nachrueckliste
    return bool(hat_nachrueckliste(read_text(p)))


def pre_tooluse(eingabe: dict, lauf: "Path | None", state_datei, umschalt) -> int:
    """PreToolUse: den Preflight-Aufruf EINMAL stoppen, wenn er zu frueh kaeme (R13be-2).

    **Was PreToolUse darf** (Beleg: das Hooks-Handbuch im CLI-Binary,
    `docs/_r13be_belege.md`): Ereignis-Tabelle „PreToolUse - Run before tool, **can
    block**“; Ausgabefelder `hookSpecificOutput.permissionDecision` = „allow“, „deny“
    oder „ask“ und `permissionDecisionReason` (beide **PreToolUse only**). Ein Hinweis
    **ohne** Blockieren ginge ueber `additionalContext`; hier wird bewusst `deny`
    benutzt, damit der Worker vor dem Aufruf anhaelt statt danach.

    Geblockt wird nur, wenn ALLE Bedingungen gelten:
      * es ist ein Preflight-**Start** (`streamjson.ist_preflight_aufruf`),
      * die Batch-Uhr steht **vor** der Umschaltschwelle (`uhr.preflight_zu_frueh`),
      * `auftrag.md` traegt eine offene `NACHRUECKLISTE` (`_nachrueckliste_offen`).

    **Je Batch nur einmal:** nach dem ersten Stopp entsteht `preflight-blockiert.jsonl`;
    jeder weitere Aufruf im selben Batch laeuft durch (der Worker hat den Hinweis dann
    gelesen und entschieden). Ohne Laufverzeichnis oder ohne Startzeit im Zustand
    passiert nichts - der Lauf bleibt unberuehrt.
    """
    from hx import streamjson, uhr
    if not streamjson.ist_preflight_aufruf(eingabe.get("tool_name"),
                                           eingabe.get("tool_input")):
        return 0
    if umschalt is None:
        return 0
    state = uhr.lies_state(state_datei)
    d = uhr.start_zeit(state)
    if d["zeit"] is None:
        return 0
    minuten = max(0.0, (d["alter_s"] or 0) / 60.0)
    if not uhr.preflight_zu_frueh(minuten, umschalt):
        return 0
    if not _nachrueckliste_offen(lauf):
        return 0
    marke = (Path(lauf) / BLOCK_DATEI) if lauf is not None else None
    if marke is not None and marke.is_file():
        return 0                       # schon einmal gestoppt - jetzt durchlaufen lassen
    if marke is not None:
        from hx.util import append_jsonl
        append_jsonl(marke, {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                             "min": round(minuten, 1), "umschalt": float(umschalt),
                             "werkzeug": str(eingabe.get("tool_name") or "")})
    # Derselbe Wortlaut wie beim Hinweis NACH dem Aufruf ("PREFLIGHT-HINWEIS: …") plus
    # der Zusatz aus dem Auftrag, damit der Worker den Stopp begruendet beantworten kann.
    grund = ("PREFLIGHT-HINWEIS: " + uhr.preflight_hinweis(minuten, umschalt)
             + " " + BLOCK_ZUSATZ)
    io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8").write(json.dumps(
        {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                "permissionDecision": "deny",
                                "permissionDecisionReason": grund}},
        ensure_ascii=False))
    return 0


def main(argv: list[str]) -> int:
    if "--state" not in argv:
        return 0
    eingabe = _stdin_json()
    try:
        i = argv.index("--state")
        state_datei = Path(argv[i + 1])
        weich = float(argv[argv.index("--weich") + 1]) if "--weich" in argv else 90.0
        hart = float(argv[argv.index("--hart") + 1]) if "--hart" in argv else 180.0
        # R13ad: die Umschaltschwelle (Alarmgrenze minus `umschalt_vor_alarm_s`, seit
        # R13ae 900 s = 15 min) und die Kontextgrenze kommen aus `harness.toml` und
        # werden vom Harness mitgegeben.
        # R13ah: dazu die gemessene Dauer des letzten Preflight-Aufrufs (`--preflight-min`).
        # R13aj: und der Batch, aus dem sie stammt (`--preflight-batch`) - er kann
        # aelter sein, wenn der neueste Aufruf nur parallel lief.
        # R13ao: `--run` ist das Laufverzeichnis (`runs/b<N>`) - daraus kommen
        # `auftrag.md` (NACHRUECKLISTE) und die Zaehldatei.
        umschalt = (float(argv[argv.index("--umschalt") + 1])
                    if "--umschalt" in argv else None)
        preflight_min = (float(argv[argv.index("--preflight-min") + 1])
                         if "--preflight-min" in argv else None)
        preflight_batch = (int(argv[argv.index("--preflight-batch") + 1])
                           if "--preflight-batch" in argv else None)
        kontext_limit = (int(argv[argv.index("--kontext-limit") + 1])
                         if "--kontext-limit" in argv else None)
        lauf = (Path(argv[argv.index("--run") + 1]) if "--run" in argv else None)
        if "--pre" in argv:
            # R13be-2: VOR dem Werkzeugaufruf pruefen (billigster Fall zuerst: kein
            # Preflight-Aufruf -> sofort raus, ohne den Zustand zu lesen).
            return pre_tooluse(eingabe, lauf, state_datei, umschalt)
        from hx import streamjson, uhr
        state = uhr.lies_state(state_datei)
        d = uhr.start_zeit(state)
        if d["zeit"] is None:
            # Nichts gemessen (kein laufender Batch im Zustand) -> KEINE Zeile. Sonst
            # stuende nach jedem Werkzeugaufruf ein Hinweis ohne Messwert im Kontext.
            return 0
        text = uhr.uhr_text(state, weich, hart, umschalt_min=umschalt,
                            kontext_limit=kontext_limit,
                            preflight_min=preflight_min,
                            preflight_batch=preflight_batch)
        # --- R13ao: Preflight-Aufruf erkennen, zaehlen, ggf. hinweisen ----------------
        if streamjson.ist_preflight_aufruf(eingabe.get("tool_name"),
                                           eingabe.get("tool_input")):
            minuten = max(0.0, (d["alter_s"] or 0) / 60.0)
            frueh = (uhr.preflight_zu_frueh(minuten, umschalt)
                     and _nachrueckliste_offen(lauf))
            if lauf is not None:
                from hx.util import append_jsonl
                append_jsonl(Path(lauf) / ZAHL_DATEI,
                             {"ts": datetime.now(timezone.utc).isoformat(
                                 timespec="seconds"),
                              "min": round(minuten, 1), "frueh": bool(frueh),
                              "werkzeug": str(eingabe.get("tool_name") or "")})
            if frueh:
                text += "\nPREFLIGHT-HINWEIS: " + uhr.preflight_hinweis(minuten, umschalt)
        io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8").write(json.dumps(
            {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                    "additionalContext": text}},
            ensure_ascii=False))
    except Exception:                                                     # noqa: BLE001
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
