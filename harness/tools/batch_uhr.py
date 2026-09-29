"""Batch-Uhr als Claude-Code-Hook (R13ac, Befund M210-1).

Wird vom Harness als `PostToolUse`-Hook in die Worker-Sitzung gehaengt (Einstellungsdatei
`runs/b<N>/worker-hooks.json`, erzeugt in `hx/worker.py`). Der Hook laeuft nach JEDEM
Werkzeugaufruf und gibt eine Zeile `additionalContext` aus - die Claude-CLI haengt sie
als System-Reminder neben das Werkzeugergebnis, das Modell liest sie beim naechsten
Aufruf (Doku "Hooks reference", Abschnitt "Add context for Claude").

    python tools/batch_uhr.py --state <state/run.json> --weich 90 --hart 180 \
        --umschalt 80 --kontext-limit 1000000

Quelle der Zahl ist dieselbe wie in der watch-Anzeige: `hx.uhr` liest
`state/run.json -> worker.started_at` (Prozessstart des Workers). Gegenprobe fuer einen
beendeten Lauf ist `runs/b<N>/result.json:duration_s`.

**Kein Fehler darf den Batch stoeren**: bei jedem Problem wird nichts ausgegeben und mit
0 beendet (der Hook ist dann wirkungslos, der Lauf geht weiter).
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main(argv: list[str]) -> int:
    if "--state" not in argv:
        return 0
    try:
        try:
            sys.stdin.read()          # Hook-Eingabe abnehmen (klein), nie auswerten
        except Exception:             # noqa: BLE001
            pass
        i = argv.index("--state")
        state_datei = Path(argv[i + 1])
        weich = float(argv[argv.index("--weich") + 1]) if "--weich" in argv else 90.0
        hart = float(argv[argv.index("--hart") + 1]) if "--hart" in argv else 180.0
        # R13ad: die Umschaltschwelle (Alarmgrenze minus `umschalt_vor_alarm_s`, seit
        # R13ae 900 s = 15 min) und die Kontextgrenze kommen aus `harness.toml` und
        # werden vom Harness mitgegeben.
        # R13ah: dazu die gemessene Dauer des letzten Preflight-Aufrufs (`--preflight-min`).
        umschalt = (float(argv[argv.index("--umschalt") + 1])
                    if "--umschalt" in argv else None)
        preflight_min = (float(argv[argv.index("--preflight-min") + 1])
                         if "--preflight-min" in argv else None)
        kontext_limit = (int(argv[argv.index("--kontext-limit") + 1])
                         if "--kontext-limit" in argv else None)
        from hx import uhr
        state = uhr.lies_state(state_datei)
        if uhr.start_zeit(state)["zeit"] is None:
            # Nichts gemessen (kein laufender Batch im Zustand) -> KEINE Zeile. Sonst
            # stuende nach jedem Werkzeugaufruf ein Hinweis ohne Messwert im Kontext.
            return 0
        text = uhr.uhr_text(state, weich, hart, umschalt_min=umschalt,
                            kontext_limit=kontext_limit,
                            preflight_min=preflight_min)
        io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8").write(json.dumps(
            {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                    "additionalContext": text}},
            ensure_ascii=False))
    except Exception:                                                     # noqa: BLE001
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
