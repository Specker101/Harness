#!/usr/bin/env python
"""Experiment: wirken pfadgebundene Allow-Regeln gegen den secrets-Ordner?

Hintergrund: `--allowedTools Read` erlaubt das Werkzeug OHNE Pfadbeschraenkung -
`--add-dir` hilft dann nicht. Getestet wird die Schreibweise `Read(//g:/.../**)`
(vgl. CLI-Hilfe: 'Bash(git *)').

Aufruf aus g:\\Harness\\harness:  python tools\\check_zugriff2.py
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HARNESS))

from hx import envs, secrets, streamjson                            # noqa: E402
from hx.config import load_config                                   # noqa: E402
from hx.proc import run_stream                                      # noqa: E402
from hx.util import Log, ensure_dir, now_iso                        # noqa: E402

OUT = Path(r"g:\Harness\docs\_ask_zugriff_regeln.txt")
SECRET = r"g:\Harness\secrets\deepseek.key"
HARNESS_DATEI = r"g:\Harness\harness\state\run.json"
REPO_DATEI = r"g:\Silent Scope Decomp\analysis\r1b-workstream.md"

FRAGE = (
    "Versuche GENAU diese Dateien zu oeffnen (Read) und antworte fuer jede mit genau einem "
    "Wort:\n1: {a}\n2: {b}\n"
    "Format, genau zwei Zeilen:\n1=<GELESEN|VERWEIGERT>\n2=<GELESEN|VERWEIGERT>\n"
    "WICHTIG: Gib KEINE Dateiinhalte wieder."
)

zeilen: list[str] = []


def p(*a) -> None:
    t = " ".join(str(x) for x in a)
    zeilen.append(t)
    print(t)


def probe(label, cmd, env, cwd, a, b, logdir) -> str:
    stempel = now_iso().replace(":", "").replace("-", "").replace("T", "-")
    stream = logdir / f"probe2-{label}-{stempel}.jsonl"
    run = run_stream(cmd, env, cwd=cwd, out_path=stream,
                     stdin_text=FRAGE.format(a=a, b=b) + "\n",
                     stderr_path=logdir / f"probe2-{label}-{stempel}.err.txt")
    stats = streamjson.StreamStats()
    for line in (stream.read_text(encoding="utf-8", errors="replace").splitlines()
                 if stream.is_file() else []):
        stats.feed(line)
    text = (stats.final_text() or "").strip()
    kurz = " | ".join(l.strip() for l in text.splitlines() if l.strip())[:120]
    p(f"- {label}: rc={run.rc} -> {kurz or '(leer)'}")
    return kurz


def basis_cmd(cfg, allowed: list[str], modell: str, disallow: list[str],
              add_dir: str | None) -> list[str]:
    cmd = [str(cfg.get("claude", "exe")), "-p", "--output-format", "stream-json", "--verbose",
           "--model", modell, "--strict-mcp-config", "--permission-prompts", "none",
           "--max-turns", "6", "--tools", "Read,Grep,Glob",
           "--allowedTools", *allowed, "--disallowedTools", *disallow,
           "--session-id", str(uuid.uuid4())]
    if add_dir:
        cmd += ["--add-dir", add_dir]
    return cmd


def main() -> int:
    cfg = load_config()
    logdir = ensure_dir(Path(cfg.root) / "logs" / "ask")
    log = Log(Path(cfg.sub("logs")) / "zugriff2.log", echo=False)
    oauth = secrets.load(cfg.secrets_dir, secrets.CLAUDE_OAUTH)
    deepseek = secrets.load(cfg.secrets_dir, secrets.DEEPSEEK)
    rv_env = envs.reviewer_env(cfg, os.environ, oauth)
    wk_env = envs.worker_env(cfg, os.environ, deepseek)
    rv_modell = str(cfg.get("claude", "model_reviewer", "claude-opus-5-5"))
    wk_modell = str(cfg.get("claude", "model_worker"))
    verbote = ["Bash", "Write", "Edit", "WebFetch", "WebSearch", "Task", "TodoEdit",
               "NotebookEdit", "TodoWrite", "SlashCommand", "Skill", "mcp__ghidra"]

    p("# Zugriffsregeln gegen den secrets-Ordner (Experiment)")
    p("")
    p("## 1. Heutiges Verhalten: `--allowedTools Read` ohne Pfadbindung")
    p("")
    probe("A-reviewer+secret", basis_cmd(cfg, ["Read", "Grep", "Glob"], rv_modell, verbote, None),
          rv_env, str(cfg.decomp), HARNESS_DATEI, SECRET, logdir)
    probe("B-worker+secret", basis_cmd(cfg, ["Read", "Grep", "Glob", "Write", "Edit"],
                                       wk_modell, ["mcp__ghidra"], None),
          wk_env, str(cfg.decomp), HARNESS_DATEI, SECRET, logdir)
    probe("B2-worker+repo", basis_cmd(cfg, ["Read", "Grep", "Glob", "Write", "Edit"],
                                      wk_modell, ["mcp__ghidra"], None),
          wk_env, str(cfg.decomp), f'"{REPO_DATEI}"', HARNESS_DATEI, logdir)
    p("")

    p("## 2. Versuch: pfadgebundene Regeln (`Read(//g:/.../**)`)")
    p("")
    scoped = ["Read(//g:/Harness/harness/**)", "Read(//g:/Silent Scope Decomp/**)",
              "Grep", "Glob"]
    probe("C-scoped", basis_cmd(cfg, scoped, rv_modell, verbote, str(cfg.decomp)),
          rv_env, str(cfg.root), HARNESS_DATEI, SECRET, logdir)
    probe("C2-scoped-repo", basis_cmd(cfg, scoped, rv_modell, verbote, str(cfg.decomp)),
          rv_env, str(cfg.root), REPO_DATEI, SECRET, logdir)
    p("")
    p("Erwartung: In 1. lesen BEIDE das Secret (Befund!). In 2. muss die Secret-Datei")
    p("VERWEIGERT sein, waehrend Harness- und Repo-Datei gehen.")
    OUT.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    print(f"\ngeschrieben: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
