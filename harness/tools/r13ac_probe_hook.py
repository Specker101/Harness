"""R13ac-Sonde: kommt ein `PostToolUse`-Hook-Text beim Worker-Modell an?

Frage des Nutzers (2026-09-28, Befund M210-1): erlaubt Claude Code fuer den Worker einen
PostToolUse-Hook, der nach JEDEM Werkzeugaufruf eine Zeile "BATCH-UHR: <m> min von
<budget> min seit Batch-Start (Harness-Messung)" einblendet - und **belegt**, dass die
Zeile beim Modell ankommt?

Die Sonde macht genau das mit EINEM echten Worker-Aufruf (DeepSeek ueber den
Anthropic-Endpunkt, Umgebung `envs.worker_env` wie im Batch):

1. Zustandsdatei mit `worker.started_at = jetzt - 42 min` schreiben.
2. Einstellungsdatei mit dem PostToolUse-Hook auf `tools/batch_uhr.py` schreiben
   (Weichgrenze 77 min / harte Grenze 123 min - **auffaellige Zahlen**, damit die
   Antwort nicht von einer Modellschaetzung stammen kann).
3. `claude -p … --settings <datei>` mit der Frage: ein PowerShell-Aufruf, danach
   woertlich die BATCH-UHR-Zeile nennen.

Antwortet das Modell mit der Zeile (42,x min, Grenzen 77/123), laeuft der Hook und der
Text kommt an. Antwortet es KEINE-ZEILE, liefert der Hook nichts aus - dann greift der
Rueckfallweg (absolute Startzeit im Vorspann).

Es wird NICHTS am Harness-Zustand geaendert; der Beleg landet in `docs/_r13ac_hook.txt`.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import envs, secrets, uhr                                # noqa: E402
from hx.config import load_config                                # noqa: E402
from hx.util import ensure_dir, write_text_atomic                # noqa: E402

BELEG = Path(ROOT).parent / "docs" / "_r13ac_hook.txt"
_puffer = io.StringIO()
_echt = sys.stdout


class _Tee:
    def write(self, text):
        _puffer.write(text)
        return len(text)

    def flush(self):
        pass


sys.stdout = _Tee()

WEICH = 77.0
HART = 123.0
ALTER_MIN = 42

FRAGE = ("Rufe genau EINMAL das Werkzeug PowerShell mit dem Befehl `Get-Date` auf. "
         "Antworte danach mit NUR der Zeile aus deinem Kontext, die mit `BATCH-UHR` "
         "beginnt - woertlich - oder mit dem Wort KEINE-ZEILE, wenn es keine gibt. "
         "Keine weitere Ausgabe.")


def lauf(cmd: list[str], env: dict, cwd: str, timeout: int = 300) -> tuple[str, str]:
    p = subprocess.run(cmd, input=FRAGE.encode("utf-8"), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, env=env, cwd=cwd, timeout=timeout)
    roh = p.stdout.decode("utf-8", "replace").strip()
    for zeile in reversed(roh.splitlines()):
        zeile = zeile.strip()
        if not zeile.startswith("{"):
            continue
        try:
            obj = json.loads(zeile)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("result"):
            return str(obj["result"]).strip(), ""
    return "", (f"rc={p.returncode} stderr={p.stderr.decode('utf-8', 'replace')[:300]} "
                f"stdout={roh[:300]}")


def main() -> int:
    cfg = load_config()
    print("R13ac-Sonde: kommt ein PostToolUse-Hook-Text beim Worker an?")
    print(f"Zeitpunkt: {datetime.now().astimezone().isoformat(timespec='seconds')}")
    print("Umgebung und Modell: wie ein echter Worker-Lauf (worker_env, cc-worker).")
    print()
    tmp = ensure_dir(Path(cfg.harness_home) / "sandbox" / "sperrprobe" / "_r13ac")
    start = datetime.now(timezone.utc) - timedelta(minutes=ALTER_MIN)
    state = tmp / "run.json"
    write_text_atomic(state, json.dumps(
        {"batch": 999, "state": "DS_WORKING",
         "worker": {"pid": 0, "started_at": start.isoformat(timespec="seconds")},
         "live": {"batch": 999}}, indent=1))
    settings = tmp / "worker-hooks.json"
    hooks = {"hooks": {"PostToolUse": [{"hooks": [
        {"type": "command", "timeout": 10,
         "command": sys.executable,
         "args": [str(ROOT / "tools" / "batch_uhr.py"), "--state", str(state),
                  "--weich", str(int(WEICH)), "--hart", str(int(HART))]}]}]}}
    write_text_atomic(settings, json.dumps(hooks, indent=1))

    print(f"### Aufbau")
    print(f"   Zustand : {state} (worker.started_at = jetzt - {ALTER_MIN} min "
          f"= {uhr.ortszeit(start)} Ortszeit)")
    print(f"   Hook    : PostToolUse (ohne Matcher) -> {ROOT / 'tools' / 'batch_uhr.py'}")
    print(f"   Grenzen : Weich {WEICH:.0f} min / Hart {HART:.0f} min (auffaellig gewaehlt)")
    print(f"   Erwartete Zeile: {uhr.uhr_text(uhr.lies_state(state), WEICH, HART)[:150]}…")
    print()

    token = secrets.load(cfg.secrets_dir, secrets.DEEPSEEK)
    if not token:
        print("KEIN DeepSeek-Token gefunden - Sonde nicht moeglich.")
        return 2
    env = envs.worker_env(cfg, os.environ, token)
    exe = str(cfg.get("claude", "exe"))
    modell = str(cfg.get("claude", "model_worker"))
    sid = str(uuid.uuid4())
    cmd = [exe, "-p", "--output-format", "json", "--model", modell, "--max-turns", "4",
           "--strict-mcp-config", "--permission-prompts", "none",
           "--tools", "PowerShell", "--allowedTools", "PowerShell",
           "--session-id", sid, "--settings", str(settings)]
    print("### Aufruf")
    print("   " + " ".join(cmd[:3]) + f" … --session-id {sid} --settings {settings.name}")
    antwort, fehler = lauf(cmd, env, str(cfg.decomp))
    print(f"   Antwort: {antwort[:600]!r}")
    if fehler:
        print(f"   FEHLER: {fehler}")
    print()
    print("### Verdikt")
    ok = ("BATCH-UHR" in antwort) and ("77" in antwort) and ("123" in antwort)
    if ok:
        print("   Der Hook-Text KOMMT BEIM MODELL AN (BATCH-UHR-Zeile mit 77/123 genannt).")
        print("   -> Der PostToolUse-Weg ist belegt; die Batch-Uhr wird so eingebaut.")
    elif "KEINE-ZEILE" in antwort:
        print("   KEINE Zeile angekommen -> der Hook liefert nichts aus (Einstellungsdatei")
        print("   oder Format pruefen). Rueckfall: absolute Startzeit im Vorspann.")
    else:
        print(f"   Unklar - Antwort war {antwort[:200]!r} (Fehler: {fehler[:200]})")
    write_text_atomic(BELEG, _puffer.getvalue())
    sys.stdout = _echt
    print(f"Beleg geschrieben: {BELEG} ({len(_puffer.getvalue())} Zeichen)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
