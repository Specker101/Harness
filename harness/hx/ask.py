"""Freie Frage an Claude (Opus 5.5) - eigener, kurzer Lauf, NUR LESEND (R13f).

Nicht zu verwechseln mit dem Reviewer:
  * eigener Prozess und **eigene Session** (kein `--session-id`/`--resume`),
  * eigener Werkzeugsatz: nur `Read`, `Grep`, `Glob` - kein Schreiben, kein Bash,
    kein MCP,
  * eigener Systemprompt (`prompts/ask.md`), mit dem Abo-Token des Reviewers.

Lesezugriff: das Decomp-Repo (`--add-dir`) und `g:\\Harness\\harness` (Arbeits-
verzeichnis). `g:\\Harness\\secrets` liegt AUSSERHALB beider Wurzeln und ist damit
gesperrt; der Beleg steht in `docs/_ask_zugriff_beleg.txt` (Probe, die genau das
abfragt).

Der Lauf wird vom Aufrufer **in einem eigenen Thread** gestartet: laeuft gerade
ein Batch, darf /ask ihn nicht beeinflussen - der Worker-Takt ruft `poll()` aus
dem Mitschnitt-Thread auf, ein blockierender Unterprozess dort wuerde den
Mitschnitt und damit den Batch anhalten.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from . import envs, protocol, secrets, streamjson
from .profiles import pfad_regeln, secrets_verbote
from .proc import run_stream
from .util import ensure_dir, now_iso, write_text_atomic

# Alles, was schreiben oder nach draussen reden koennte - doppelt gesperrt.
VERBOTEN = ["Bash", "Write", "Edit", "MultiEdit", "NotebookEdit", "WebFetch", "WebSearch",
            "Task", "TodoWrite", "SlashCommand", "Skill", "mcp__ghidra"]


def build_command(cfg) -> list[str]:
    r"""Kommandozeile des Frage-Laufs (Prompt kommt ueber stdin).

    Lesen ist NUR in zwei Wurzeln erlaubt, und die Regeln sind pfadgebunden -
    ein blosses `Read` haette (gemessen 2026-09-26) auch `g:\Harness\secrets`
    geoeffnet. `secrets` steht zusaetzlich ausdruecklich im Verbot.
    """
    exe = str(cfg.get("claude", "exe"))
    cmd = [exe, "-p",
           "--output-format", "stream-json",
           "--verbose",
           "--model", str(cfg.get("claude", "model_reviewer", "claude-opus-5-5")),
           "--strict-mcp-config",
           "--permission-prompts", "none",
           "--max-turns", "25",
           "--tools", "Read,Grep,Glob",
           "--allowedTools", *pfad_regeln((cfg.root, cfg.decomp)),
           "--disallowedTools", *(VERBOTEN + secrets_verbote(cfg.secrets_dir)),
           "--add-dir", str(cfg.root),
           "--add-dir", str(cfg.decomp)]
    sp = Path(cfg.prompts_dir) / "ask.md"
    if sp.is_file():
        cmd += ["--append-system-prompt-file", str(sp)]
    return cmd


def prompt_bauen(frage: str, zusatz: str = "") -> str:
    teile = ["FRAGE DES NUTZERS (beantworte sie direkt und knapp):", frage.strip()]
    if zusatz:
        teile += ["", zusatz.strip()]
    return "\n".join(teile) + "\n"


def ask(cfg, log, frage: str, mock: bool = False, zusatz: str = "") -> dict:
    """Eine Frage stellen und die Antwort zurueckgeben.

    Rueckgabe: {"ok", "text", "hinweis", "modell", "anfragen", "kosten_usd", "limit",
                "dauer_s", "stream", "datei"}
    """
    ziel = ensure_dir(Path(cfg.root) / "logs" / "ask")
    stempel = now_iso().replace(":", "").replace("-", "").replace("T", "-")
    stream = ziel / f"ask-{stempel}.jsonl"
    datei = ziel / f"ask-{stempel}.md"
    prompt = prompt_bauen(frage, zusatz)

    if mock:
        text = "(Attrappe) Keine echte Frage gestellt."
        write_text_atomic(datei, f"# Frage\n\n{frage}\n\n# Antwort (Attrappe)\n\n{text}\n")
        return {"ok": True, "text": text, "hinweis": "(Attrappe - keine Kosten)",
                "modell": "mock", "anfragen": 0, "kosten_usd": 0.0, "limit": False,
                "dauer_s": 0.0, "stream": str(stream), "datei": str(datei)}

    oauth = secrets.load(cfg.secrets_dir, secrets.CLAUDE_OAUTH)
    if not oauth:
        return {"ok": False, "text": "", "limit": False,
                "hinweis": "Kein Abo-Token gefunden - /ask kann nicht laufen.",
                "modell": None, "anfragen": 0, "kosten_usd": 0.0, "dauer_s": 0.0,
                "stream": "", "datei": ""}
    env = envs.reviewer_env(cfg, os.environ, oauth)
    cmd = build_command(cfg)
    if log:
        log.info("Frage gestartet", modell=str(cfg.get("claude", "model_reviewer")),
                 zeichen=len(prompt))
    t0 = time.time()
    run = run_stream(cmd, env, cwd=str(cfg.root), out_path=stream, log=log,
                     stdin_text=prompt, stderr_path=ziel / f"ask-{stempel}.err.txt")
    dauer = time.time() - t0

    stats = streamjson.StreamStats()
    text = stream.read_text(encoding="utf-8", errors="replace") if stream.is_file() else ""
    for line in text.splitlines():
        stats.feed(line)
    antwort = (stats.final_text() or "").strip()
    if not antwort:
        roh = (stream.read_text(encoding="utf-8", errors="replace")
               if stream.is_file() else "")[-4000:]
        antwort = f"(keine Antwort erhalten; rc={run.rc})\n{roh}".strip()
    kosten = stats.cost_usd(list(cfg.get("peak", "extra_offpeak_dates", []) or []))
    anfragen = len(stats.requests)
    limit = protocol.looks_like_limit(antwort) or protocol.looks_like_limit(text[-2000:])
    hinweis = (f"({stats.model or '?'} | {anfragen} Anfragen | ${kosten:.4f} | "
               f"{dauer:.0f}s" + (" | LIMIT ERREICHT - spaeter erneut fragen" if limit else "")
               + ")")
    write_text_atomic(datei, f"# Frage\n\n{frage.strip()}\n\n# Antwort\n\n{antwort}\n\n"
                             f"{hinweis}\n")
    if log:
        log.info("Frage beantwortet", rc=run.rc, anfragen=anfragen, kosten=kosten,
                 dauer_s=round(dauer, 1), limit=limit)
    return {"ok": bool(antwort) and not limit, "text": antwort, "hinweis": hinweis,
            "modell": stats.model, "anfragen": anfragen, "kosten_usd": kosten,
            "limit": bool(limit), "dauer_s": dauer, "stream": str(stream), "datei": str(datei)}
