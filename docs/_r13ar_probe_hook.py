"""R13ar: Kommt die Zuguhr beim Modell an? (MESSUNG mit echtem CLI-Lauf)

Der Hook-Weg ist derselbe wie bei der Batch-Uhr des Workers (R13ac): `--settings <datei>`
mit einem `PostToolUse`-Hook, der `hookSpecificOutput.additionalContext` ausgibt. Beweis
ist auch hier der **Wortlaut in der Antwort des Modells** (R13ac: "das Modell nannte die
Zeile woertlich").

Gefahren wird mit dem **Worker-Modell** (DeepSeek, Bruchteile eines Cents). Das Limit wird
klein gesetzt (5), damit die Frist schon nach dem ersten Werkzeugaufruf erscheint.

Aufruf: python -u docs/_r13ar_probe_hook.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
HARNESS = HIER.parent / "harness"
sys.path.insert(0, str(HARNESS))

from hx import envs, secrets, streamjson                         # noqa: E402
from hx.config import load_config                                # noqa: E402
from hx.proc import run_stream                                   # noqa: E402

TMP = HIER / "_r13ar_probe_hook"
LIMIT = 5
AUFTRAG = ("Lies die Datei a.txt mit einem Read-Aufruf. Schreibe danach in EINER Zeile "
           "woertlich den Text, der in deinem Kontext als 'AUSSENSICHT-UHR' steht.")


def main() -> int:
    shutil.rmtree(TMP, ignore_errors=True)
    TMP.mkdir(parents=True, exist_ok=True)
    (TMP / "a.txt").write_text("Inhalt A\n", encoding="utf-8")
    skript = HARNESS / "tools" / "aussensicht_uhr.py"
    einstellungen = TMP / "hooks.json"
    einstellungen.write_text(json.dumps({"hooks": {"PostToolUse": [{"hooks": [
        {"type": "command", "timeout": 10, "command": sys.executable,
         "args": [str(skript), "--limit", str(LIMIT)]}]}]}}), encoding="utf-8")

    cfg = load_config()
    env = envs.worker_env(cfg, os.environ, secrets.load(cfg.secrets_dir, secrets.DEEPSEEK))
    cmd = [str(cfg.get("claude", "exe")), "-p", "--output-format", "stream-json",
           "--verbose", "--model", str(cfg.get("claude", "model_worker")),
           "--permission-prompts", "none", "--allowedTools", "Read",
           "--add-dir", str(TMP), "--settings", str(einstellungen)]
    ziel = TMP / "stream.jsonl"
    run = run_stream(cmd, env, cwd=str(TMP), out_path=ziel, on_event=None,
                     hard_wall_s=300.0, log=None, stdin_text=AUFTRAG,
                     stderr_path=TMP / "stream.err.txt")
    stats = streamjson.StreamStats()
    for z in ziel.read_text(encoding="utf-8", errors="replace").splitlines():
        stats.feed(z)
    antwort = (stats.final_text() or "").strip()
    print(f"Probelauf (Limit {LIMIT}): rc={run.rc} dauer={run.duration_s:.1f}s "
          f"runden={stats.runden()} num_turns={stats.num_turns()}")
    print("Auftrag:", AUFTRAG)
    print()
    print("Antwort des Modells:")
    print("  " + antwort.replace("\n", "\n  ")[:800])
    print()
    treffer = [w for w in ("AUSSENSICHT-UHR", f"Zug 1 von {LIMIT}",
                           "JETZT die Antwort im Blockformat schreiben")
               if w.lower() in antwort.lower()]
    print("Woertlich genannt:", treffer or "NICHTS")
    print("=> " + ("Der Hook-Text kommt beim Modell an." if treffer
                   else "NICHT belegt - die Antwort nennt die Zeile nicht."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
