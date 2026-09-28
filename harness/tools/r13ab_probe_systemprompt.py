"""R13ab-Sonde: wirkt `--append-system-prompt-file` auch bei `--resume`? (nur lesend)

Frage des Nutzers (2026-09-28): die Pflichtzeile `B-SCHRITT:` fehlte in den Reviews, die
nach dem Neustart liefen - kam die Regel aus `prompts/reviewer.md` ueberhaupt beim Modell an?
Der Harness haengt die Datei bei JEDEM Aufruf an (`reviewer.build_command:96-98`), auch bei
`--resume`. Ob die Claude-CLI eine GEAENDERTE Datei in einer laufenden Session beachtet, ist
damit nicht bewiesen - diese Sonde misst es mit ZWEI minimalen Aufrufen:

  1. neue Session, Systemprompt-Datei mit `MARKER: PROBE-A`
  2. dieselbe Session per `--resume`, Datei auf `MARKER: PROBE-B` geaendert

Antwortet der zweite Lauf mit PROBE-A, liest die CLI die Datei bei `--resume` NICHT neu
(dann hilft nur Rotation). Antwortet er PROBE-B, kommt die Datei jedes Mal an.

Kosten: zwei kurze Aufrufe mit dem Reviewer-Modell ueber das Abo. Es wird NICHTS am
Harness-Zustand geaendert; die Sitzung landet in `cc-reviewer/` (wie ein echter Review).
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import envs, secrets                     # noqa: E402
from hx.config import load_config                # noqa: E402
from hx.util import ensure_dir, write_text_atomic  # noqa: E402

# Beleg mitschreiben und SELBST als UTF-8 ablegen (Konsolenumleitung wandelt Umlaute um).
_puffer = io.StringIO()
_echt = sys.stdout
BELEG = Path(ROOT).parent / "docs" / "_r13ab_probe.txt"


class _Tee:
    def write(self, text):
        _puffer.write(text)
        return len(text)

    def flush(self):
        pass


sys.stdout = _Tee()

FRAGE = ("Antworte NUR mit dem Wert, der in deinem Systemprompt hinter 'MARKER:' steht. "
         "Wenn dort kein MARKER steht, antworte mit KEIN-MARKER. Keine weitere Ausgabe.")


def lauf(cmd: list[str], env: dict, cwd: str, timeout: int = 240) -> str:
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
            return str(obj["result"]).strip()
    return f"(kein Ergebnis; rc={p.returncode}; stderr={p.stderr.decode('utf-8','replace')[:200]})"


def main() -> int:
    cfg = load_config()
    print("R13ab-Sonde: wirkt --append-system-prompt-file bei --resume?")
    print(f"Zeitpunkt: {__import__('datetime').datetime.now().astimezone().isoformat(timespec='seconds')}")
    print("Modell und Umgebung: wie ein echter Review (reviewer_env, cc-reviewer).")
    print()
    tmp = ensure_dir(Path(cfg.harness_home) / "sandbox" / "sperrprobe" / "_r13ab")
    datei = tmp / "probe_systemprompt.md"
    write_text_atomic(datei, "MARKER: PROBE-A\n" + FRAGE + "\n")
    oauth = secrets.load(cfg.secrets_dir, secrets.CLAUDE_OAUTH)
    if not oauth:
        print("KEIN Abo-Token gefunden - Sonde nicht moeglich.")
        return 2
    env = envs.reviewer_env(cfg, os.environ, oauth)
    exe = str(cfg.get("claude", "exe"))
    modell = str(cfg.get("claude", "model_reviewer", "claude-opus-5-5"))
    sid = str(uuid.uuid4())
    basis = [exe, "-p", "--output-format", "json", "--model", modell, "--max-turns", "1",
             "--strict-mcp-config", "--permission-prompts", "none"]

    print("### 1) neue Session mit MARKER: PROBE-A")
    cmd1 = [*basis, "--session-id", sid, "--append-system-prompt-file", str(datei)]
    print("   " + " ".join(cmd1[:3]) + f" … --session-id {sid} "
          f"--append-system-prompt-file {datei.name}")
    a1 = lauf(cmd1, env, str(cfg.decomp))
    print(f"   Antwort: {a1!r}")
    print(f"   Dateiinhalt jetzt: {datei.read_text('utf-8').splitlines()[0]!r}")

    print()
    print("### 2) dieselbe Session per --resume, Datei auf MARKER: PROBE-B geaendert")
    write_text_atomic(datei, "MARKER: PROBE-B\n" + FRAGE + "\n")
    cmd2 = [*basis, "--resume", sid, "--append-system-prompt-file", str(datei)]
    print("   " + " ".join(cmd2[:3]) + f" … --resume {sid} "
          f"--append-system-prompt-file {datei.name}")
    a2 = lauf(cmd2, env, str(cfg.decomp))
    print(f"   Antwort: {a2!r}")

    print()
    print("### Verdikt")
    if "PROBE-B" in a2:
        print("   Die geaenderte Datei KOMMT BEI --resume AN (Antwort PROBE-B).")
        print("   -> Ein geaenderter Systemprompt wirkt in einer laufenden Session; die")
        print("      Rotation ist NICHT noetig, damit prompts/reviewer.md ankommt.")
    elif "PROBE-A" in a2:
        print("   Die geaenderte Datei kommt bei --resume NICHT an (Antwort PROBE-A bleibt).")
        print("   -> Aenderungen an prompts/reviewer.md erreichen eine LAUFENDE Session")
        print("      nicht; sie brauchen eine neue Session (Rotation).")
    else:
        print(f"   Unklar: Antwort 1 = {a1!r}, Antwort 2 = {a2!r}")
    write_text_atomic(BELEG, _puffer.getvalue())
    sys.stdout = _echt
    print(f"Beleg geschrieben: {BELEG} ({len(_puffer.getvalue())} Zeichen)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
