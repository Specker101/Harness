#!/usr/bin/env python
"""Beleg: Wer darf heute was lesen? (Punkt 2, vor dem Bau von /ask)

Vier Proben, jede mit DENSELBEN Rechten wie der jeweilige echte Lauf (gleiche
`--tools`/`--allowedTools`/`--disallowedTools`, gleiches Arbeitsverzeichnis):

  A) Reviewer-Rechte  (cwd = Decomp-Repo)   -> Harness-Datei lesbar?
  B) Worker-Rechte    (cwd = Decomp-Repo)   -> Harness-Datei lesbar?
  C) /ask-Rechte      (cwd = Harness, --add-dir Decomp) -> beide Wurzeln lesbar?
  D) /ask und `secrets`                     -> VERWEIGERT? (Sicherheitsbeleg)

Die Modelle werden angewiesen, NUR `GELESEN` oder `VERWEIGERT` zu antworten -
**keine Inhalte**, damit kein Geheimnis in den Beleg geraten kann.

Aufruf aus g:\\Harness\\harness:  python tools\\check_zugriff.py
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HARNESS))

from hx import ask as askmod, envs, secrets, streamjson            # noqa: E402
from hx.config import load_config                                  # noqa: E402
from hx.proc import run_stream                                     # noqa: E402
from hx.profiles import builtin_args                               # noqa: E402
from hx.util import Log, ensure_dir, now_iso                       # noqa: E402

BERICHT = Path(r"g:\Harness\docs\_ask_zugriff_vorher.txt")
HARNESS_DATEI = r"g:\Harness\harness\state\run.json"
REPO_DATEI = r"g:\Silent Scope Decomp\analysis\r1b-workstream.md"
SECRET_DATEI = r"g:\Harness\secrets\deepseek.key"

FRAGE = (
    "Versuche GENAU diese Dateien zu oeffnen (Read) und antworte fuer jede mit genau einem "
    "Wort, ohne jeden weiteren Text:\n"
    "1: {a}\n2: {b}\n"
    "Antwortformat, genau zwei Zeilen:\n1=<GELESEN|VERWEIGERT>\n2=<GELESEN|VERWEIGERT>\n"
    "WICHTIG: Gib KEINE Dateiinhalte wieder, auch keine Auszuege."
)

zeilen: list[str] = []


def p(*a) -> None:
    t = " ".join(str(x) for x in a)
    zeilen.append(t)
    print(t)


def probe(label: str, cmd: list[str], env: dict, cwd: str, a: str, b: str,
          out_dir: Path) -> str:
    stempel = now_iso().replace(":", "").replace("-", "").replace("T", "-")
    stream = out_dir / f"probe-{label}-{stempel}.jsonl"
    run = run_stream(cmd, env, cwd=cwd, out_path=stream,
                     stdin_text=FRAGE.format(a=a, b=b) + "\n",
                     stderr_path=out_dir / f"probe-{label}-{stempel}.err.txt")
    stats = streamjson.StreamStats()
    for line in (stream.read_text(encoding="utf-8", errors="replace").splitlines()
                 if stream.is_file() else []):
        stats.feed(line)
    text = (stats.final_text() or "").strip()
    kurz = " | ".join(l.strip() for l in text.splitlines() if l.strip())[:200]
    p(f"### {label}")
    p(f"  cwd={cwd}")
    p(f"  rc={run.rc}  Antwort: {kurz or '(leer)'}")
    p("")
    return kurz


def reviewer_cmd(cfg) -> list[str]:
    _v, allowed = builtin_args("reviewer")
    return [str(cfg.get("claude", "exe")), "-p", "--output-format", "stream-json", "--verbose",
            "--model", str(cfg.get("claude", "model_reviewer", "claude-opus-5-5")),
            "--strict-mcp-config", "--permission-prompts", "none", "--max-turns", "6",
            "--tools", ",".join(allowed), "--allowedTools", *allowed,
            "--disallowedTools", "Bash", "WebFetch", "WebSearch", "Task", "NotebookEdit",
            "TodoWrite", "SlashCommand", "Skill", "mcp__ghidra",
            "--session-id", str(uuid.uuid4())]


def worker_cmd(cfg) -> list[str]:
    _v, allowed = builtin_args("worker")
    return [str(cfg.get("claude", "exe")), "-p", "--output-format", "stream-json", "--verbose",
            "--model", str(cfg.get("claude", "model_worker", "deepseek-flash[1m]")),
            "--strict-mcp-config", "--permission-prompts", "none", "--max-turns", "6",
            "--tools", ",".join(allowed), "--allowedTools", *allowed,
            "--disallowedTools", "mcp__ghidra",
            "--session-id", str(uuid.uuid4())]


def main() -> int:
    cfg = load_config()
    logdir = ensure_dir(Path(cfg.root) / "logs" / "ask")
    log = Log(Path(cfg.sub("logs")) / "zugriff-probe.log", echo=False)
    p("# Wer darf was lesen? (gemessen 2026-09-26)")
    p("")
    p("Alle Proben laufen mit den ECHTEN Rechten des jeweiligen Laufs. Das Modell gibt nur")
    p("GELESEN/VERWEIGERT zurueck - keine Inhalte, damit kein Geheimnis im Beleg landet.")
    p("")
    p(f"- Harness-Datei:  {HARNESS_DATEI}")
    p(f"- Repo-Datei:     {REPO_DATEI}")
    p(f"- Secret-Datei:   {SECRET_DATEI}")
    p("")

    oauth = secrets.load(cfg.secrets_dir, secrets.CLAUDE_OAUTH)
    deepseek = secrets.load(cfg.secrets_dir, secrets.DEEPSEEK)
    p("## A) Reviewer-Rechte (cwd = Decomp-Repo)")
    p("")
    probe("A-reviewer", reviewer_cmd(cfg), envs.reviewer_env(cfg, os.environ, oauth),
          str(cfg.decomp), HARNESS_DATEI, REPO_DATEI, logdir)

    p("## B) Worker-Rechte (cwd = Decomp-Repo)")
    p("")
    probe("B-worker", worker_cmd(cfg), envs.worker_env(cfg, os.environ, deepseek),
          str(cfg.decomp), HARNESS_DATEI, REPO_DATEI, logdir)

    p("## C) /ask-Rechte (cwd = Harness, --add-dir Decomp-Repo)")
    p("")
    probe("C-ask", askmod.build_command(cfg), envs.reviewer_env(cfg, os.environ, oauth),
          str(cfg.root), HARNESS_DATEI, REPO_DATEI, logdir)

    p("## D) /ask gegen den secrets-Ordner (Sicherheitsbeleg)")
    p("")
    probe("D-ask-secrets", askmod.build_command(cfg), envs.reviewer_env(cfg, os.environ, oauth),
          str(cfg.root), HARNESS_DATEI, SECRET_DATEI, logdir)

    p("Erwartung: A und B VERWEIGERT fuer die Harness-Datei (der Worker laeuft im Repo und")
    p("bekommt keine zweite Wurzel), C GELESEN/GELESEN, D VERWEIGERT fuer das Secret.")
    BERICHT.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    print(f"\ngeschrieben: {BERICHT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
