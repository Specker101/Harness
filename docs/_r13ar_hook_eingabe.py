"""R13ar: Was bekommt ein PostToolUse-Hook der Aussensicht auf stdin? (MESSUNG)

Der Zugzaehler (Punkt 1 des Auftrags) soll "Zug X von <meta_max_turns>" zeigen. Die CLI
zaehlt als Zug eine **Modellantwort mit Werkzeugaufruf** (gemessen: `--max-turns 2` bricht
nach 2 solchen Antworten ab). Ein Hook wird je WERKZEUGAUFRUF gerufen - sind mehrere
Aufrufe in EINER Antwort (parallel, R13aj), zaehlt er mehr als die CLI.

Diese Sonde schreibt die Hook-Eingabe mit und prueft, ob ein Feld wie `transcript_path`
drinsteht, mit dem der Hook die Runden exakt zaehlen koennte.

Aufruf: python -u docs/_r13ar_hook_eingabe.py
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

from hx import envs, secrets                                      # noqa: E402
from hx.config import load_config                                 # noqa: E402

TMP = HIER / "_r13ar_hook"
MITSCHRIFT = TMP / "stdin.jsonl"

# Ein winziger Mitschnitt-Hook: haengt jede Eingabe an und beendet sich still.
HOOK = '''"""Sonde: stdin mitschreiben, sonst nichts tun."""
import sys
from pathlib import Path
p = Path(r"{ziel}")
roh = sys.stdin.read()
with open(p, "a", encoding="utf-8", newline="\\n") as fh:
    fh.write(roh.replace("\\n", " ") + "\\n")
'''


def main() -> int:
    shutil.rmtree(TMP, ignore_errors=True)
    TMP.mkdir(parents=True, exist_ok=True)
    for name in ("a.txt", "b.txt"):
        (TMP / name).write_text(f"Inhalt {name}\n", encoding="utf-8")
    skript = TMP / "mitschreiben.py"
    skript.write_text(HOOK.format(ziel=str(MITSCHRIFT).replace("\\", "\\\\")),
                      encoding="utf-8")
    einstellungen = TMP / "hooks.json"
    einstellungen.write_text(json.dumps({"hooks": {"PostToolUse": [{"hooks": [
        {"type": "command", "timeout": 10, "command": sys.executable,
         "args": [str(skript)]}]}]}}), encoding="utf-8")

    cfg = load_config()
    env = envs.worker_env(cfg, os.environ, secrets.load(cfg.secrets_dir, secrets.DEEPSEEK))
    cmd = [str(cfg.get("claude", "exe")), "-p", "--output-format", "stream-json",
           "--verbose", "--model", str(cfg.get("claude", "model_worker")),
           "--permission-prompts", "none", "--allowedTools", "Read",
           "--add-dir", str(TMP), "--settings", str(einstellungen)]
    prompt = ("Lies nacheinander a.txt und b.txt (je ein Read-Aufruf) "
              "und antworte dann nur mit OK.")
    from hx.proc import run_stream
    run = run_stream(cmd, env, cwd=str(TMP), out_path=TMP / "stream.jsonl",
                     on_event=None, hard_wall_s=180.0, log=None, stdin_text=prompt,
                     stderr_path=TMP / "stream.err.txt")
    print(f"Probelauf: rc={run.rc} dauer={run.duration_s:.1f}s")
    print(f"Hook-Eingaben: {MITSCHRIFT}")
    if not MITSCHRIFT.is_file():
        print("KEINE Hook-Eingabe geschrieben - der Hook wurde nicht gerufen.")
        return 0
    zeilen = [z for z in MITSCHRIFT.read_text(encoding="utf-8").splitlines() if z.strip()]
    print(f"Anzahl Hook-Aufrufe: {len(zeilen)}")
    for z in zeilen[:2]:
        try:
            d = json.loads(z)
        except ValueError:
            print(f"  (nicht lesbar): {z[:200]}")
            continue
        print(f"  Felder: {sorted(d.keys())}")
        for feld in ("hook_event_name", "tool_name", "session_id", "transcript_path",
                     "cwd", "permission_mode"):
            if feld in d:
                print(f"    {feld} = {str(d[feld])[:120]}")
        ti = d.get("tool_input") or {}
        print(f"    tool_input-Schluessel = {sorted(ti.keys())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
