"""Zuguhr der Aussensicht als Claude-Code-Hook (R13ar, 30.09.2026).

Wird vom Harness als `PostToolUse`-Hook in den Lauf der Aussensicht gehaengt
(Einstellungsdatei `runs/meta-<N>-hooks.json`, erzeugt in `hx/aussensicht.py`). Der Hook
laeuft nach JEDEM Werkzeugaufruf und gibt eine Zeile `additionalContext` aus; die CLI
haengt sie als System-Reminder neben das Werkzeugergebnis.

    python tools/aussensicht_uhr.py --limit 50

**Was gezaehlt wird - gemessen, nicht geraten.** Die CLI prueft `--max-turns` gegen die
Zahl der **Werkzeugrunden** (Modellantworten MIT Werkzeugaufruf). Belege:

* `docs/_r13ar_limit_probe_reviewer.txt`: `--max-turns 2` bricht nach **2** solchen
  Antworten ab (`error_max_turns`, "Reached maximum number of turns (2)"), waehrend das
  Ergebnis `num_turns=3` meldet.
* `docs/_r13ar_zuege.txt`: `runs/meta-217` brach bei **30** Runden ab (Limit war 30),
  `runs/meta-214` lief mit nur **23** Runden durch - obwohl dort `num_turns=35` stand.
  `num_turns` ist eine ANDERE Zahl (Werkzeugergebnisse + 1: 8 von 8 erfolgreichen Laeufen).

Gezaehlt wird deshalb **nicht** die Zahl der Hook-Aufrufe (parallele Aufrufe in einer
Antwort waeren mehr als eine Runde), sondern direkt im **Transcript** der Sitzung - das
Feld `transcript_path` kommt in der Hook-Eingabe mit (gemessen,
`docs/_r13ar_hook_eingabe.txt`). Die Zaehlweise ist dieselbe wie im Harness
(`hx.streamjson.runden_aus_zeilen`).

**Kein Fehler darf den Lauf stoeren**: bei jedem Problem wird nichts ausgegeben und mit 0
beendet.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Der Satz ab (Limit - 5) Zuegen - Wortlaut aus dem Auftrag vom 30.09.2026.
DRINGEND = ("JETZT die Antwort im Blockformat schreiben, Unvollständiges als nicht "
            "geprüft kennzeichnen.")
# Sicherheitsdeckel: groesser wird kein Transcript gelesen (Arbeitsspeicher/Schutz).
MAX_TRANSCRIPT_BYTES = 16 * 1024 * 1024


def _stdin_json() -> dict:
    """Die Hook-Eingabe lesen (PostToolUse). Leer/kaputt -> `{}`."""
    try:
        roh = sys.stdin.read()
    except Exception:                                                    # noqa: BLE001
        return {}
    if not roh or not roh.strip():
        return {}
    try:
        daten = json.loads(roh)
    except ValueError:
        return {}
    return daten if isinstance(daten, dict) else {}


def zuege(transcript: str | Path) -> int:
    """Werkzeugrunden im Transcript der Sitzung (0, wenn nicht lesbar)."""
    p = Path(transcript)
    if not p.is_file():
        return 0
    try:
        if p.stat().st_size > MAX_TRANSCRIPT_BYTES:
            return 0
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    from hx import streamjson
    return streamjson.runden_aus_zeilen(text.splitlines())


def zeile(runden: int, grenze: int) -> str:
    """Die Kontextzeile: immer die Uhr, ab (Grenze - 5) zusaetzlich die Aufforderung."""
    text = f"AUSSENSICHT-UHR: Zug {int(runden)} von {int(grenze)} (Werkzeugrunden)."
    if grenze > 0 and runden >= grenze - 5:
        rest = max(0, int(grenze) - int(runden))
        text += f" Noch {rest} Zuege bis zum Abbruch. {DRINGEND}"
    return text


def main(argv: list[str]) -> int:
    if "--limit" not in argv:
        return 0
    try:
        grenze = int(float(argv[argv.index("--limit") + 1]))
    except (ValueError, IndexError):
        return 0
    eingabe = _stdin_json()
    transcript = str(eingabe.get("transcript_path") or "")
    try:
        runden = zuege(transcript)
        if runden <= 0:
            return 0
        io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8").write(json.dumps(
            {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                    "additionalContext": zeile(runden, grenze)}},
            ensure_ascii=False))
    except Exception:                                                    # noqa: BLE001
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
