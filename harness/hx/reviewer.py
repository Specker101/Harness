"""Reviewer-Runner (E2, E3): Claude Code ueber das Pro-Abo, nur Read/Grep/Glob.

Isolation (E3): nur CLAUDE_CODE_OAUTH_TOKEN im Prozess, KEINE DeepSeek-Variablen.
Rollenanweisung: prompts/reviewer.md (stabiler Systemprompt-Praefix, cache-freundlich).
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from . import envs, protocol, secrets
from .proc import run_stream
from .profiles import builtin_args
from .util import ensure_dir, now_iso, read_text, write_json_atomic, write_text_atomic


class ReviewResult:
    def __init__(self):
        self.rc: int | None = None
        self.duration_s = 0.0
        self.text = ""
        self.session_id: str | None = None
        self.model_seen: str | None = None
        self.model_ok: bool | None = None
        self.limit_reached = False
        self.raw_path: str | None = None
        self.parsed: protocol.Review | None = None
        self.error: str | None = None

    def describe(self) -> str:
        base = f"rc={self.rc} dauer={self.duration_s:.0f}s modell={self.model_seen} limit={self.limit_reached}"
        if self.parsed:
            base += " " + self.parsed.describe()
        return base


def build_command(cfg, session_id: str | None, new_session: bool) -> list[str]:
    """Kommandozeile OHNE Prompt - der Prompt geht über stdin (UTF-8).

    Beleg: offizielle Doku, "Non-interactive mode reads stdin" / "Piped stdin is
    capped at 10MB". Der Review-Prompt (Snapshot + Messdaten + Bericht) ist groß.
    """
    exe = str(cfg.get("claude", "exe"))
    _tools_value, allowed = builtin_args("reviewer")
    cmd = [exe, "-p",
           "--output-format", "json",
           "--strict-mcp-config",
           "--permission-prompts", "none",
           "--max-turns", "40",
           "--tools", ",".join(allowed),
           "--allowedTools", *allowed,
           "--disallowedTools", "Bash", "WebFetch", "WebSearch", "Task", "NotebookEdit",
           "TodoWrite", "SlashCommand", "Skill", "mcp__ghidra"]
    sp = Path(cfg.prompts_dir) / "reviewer.md"
    if sp.is_file():
        cmd += ["--append-system-prompt-file", str(sp)]
    if session_id and not new_session:
        cmd += ["--resume", session_id]
    else:
        cmd += ["--session-id", session_id or str(uuid.uuid4())]
    return cmd


def run_review(cfg, log, prompt: str, session_id: str | None = None, new_session: bool = False,
               mock: bool = False, mock_mode: str = "ok") -> ReviewResult:
    res = ReviewResult()
    rd = ensure_dir(Path(cfg.root) / "logs")

    if mock:
        from .mock import mock_reviewer_text
        res.text = mock_reviewer_text(mock_mode)
        res.rc = 0
        res.duration_s = 0.5
        res.session_id = session_id or "mock-session"
        res.model_seen = "claude-sonnet-5 (mock)"
        res.raw_path = str(write_text_atomic(rd / "reviewer-mock.json",
                                             json.dumps({"result": res.text}, indent=1)))
    else:
        oauth = secrets.load(cfg.secrets_dir, secrets.CLAUDE_OAUTH)
        env = envs.reviewer_env(cfg, os.environ, oauth)
        bad = envs.precheck(env, "reviewer")
        if bad:
            res.error = f"Umgebungs-Vorher-Pruefung fehlgeschlagen: {bad}"
            log.error(res.error)
            return res
        log.info("Reviewer-Umgebung geprueft", env=envs.describe(env))
        cmd = build_command(cfg, session_id, new_session)
        raw = rd / f"reviewer-{now_iso().replace(':', '')}.json"
        # Prompt mitschneiden: belegt, was der Reviewer wirklich bekommen hat.
        write_text_atomic(rd / f"review-prompt-{now_iso().replace(':', '')}.md", prompt)
        run = run_stream(cmd, env, cwd=str(cfg.decomp), out_path=raw, log=log,
                         stdin_text=prompt)
        res.rc = run.rc
        res.duration_s = run.duration_s
        res.raw_path = str(raw)
        body = read_text(raw)
        err = read_text(str(raw) + ".err")
        try:
            data = json.loads(body.strip().splitlines()[-1]) if body.strip() else {}
        except (json.JSONDecodeError, IndexError):
            data = {}
        res.text = str(data.get("result") or "")
        res.session_id = data.get("session_id") or session_id
        usage_models = data.get("modelUsage") or {}
        if isinstance(usage_models, dict) and usage_models:
            res.model_seen = ",".join(list(usage_models.keys())[:3])
        if not res.text:
            res.text = body.strip()[:4000]
        if protocol.looks_like_limit(body + "\n" + err) or protocol.looks_like_limit(res.text):
            res.limit_reached = True
        if not res.text and res.rc not in (0, None):
            res.error = f"Reviewer ohne Ergebnis (rc={res.rc}): {err.strip()[:300]}"

    res.parsed = protocol.parse_review(res.text)
    write_text_atomic(rd / f"review-{now_iso().replace(':', '')}.md",
                      res.text or "(leer)")
    if log:
        log.info("Review fertig", info=res.describe())
    return res


def build_prompt(cfg, kind: str, ctx: dict) -> str:
    """Baut den Review-Auftrag (Abschnitt F/G des Plans).

    ctx-Schluessel: batch, facts, worker_report, markers, queue_block, anchor,
    snapshot, note, extra.
    """
    kind_text = {
        "bootstrap": ("BOOTSTRAP-REVIEW. Es gibt noch keinen Worker-Lauf. Uebernimm den Stand aus "
                      "der Ankerdatei und erzeuge die Instruktion fuer den ersten Batch."),
        "batch_end": ("BATCH-ENDE-REVIEW. Bewerte den Batch anhand der Messdaten und der Belege "
                      "und erzeuge TELEGRAM_SUMMARY + DS_TOOLS + DS_INSTRUCTION."),
        "watchdog": ("WATCHDOG-CHECK. Bewerte nur den Zwischenstand und antworte mit "
                     "<DECISION>CONTINUE|OBSERVE|INTERVENE</DECISION>."),
    }[kind]

    batch = ctx.get("batch") or 0
    parts = [
        kind_text,
        f"Batch-Nummer: {batch} (der naechste Batch ist {batch + 1})",
        "Arbeitsverzeichnis: das Decomp-Repo; Projektwissen holst du dir bei Bedarf gezielt "
        "per Read/Grep (AGENTS.md, Anker, Statusdokumente) - nicht alles auf einmal.",
        "",
        "=== HARNESS-MESSDATEN (gemessen, nicht vom Worker behauptet) ===",
        (ctx.get("facts") or "(keine Messdaten - Bootstrap)").strip(),
        "",
        "=== WORKER-ABSCHLUSSBERICHT (finale Antwort, wortgleich) ===",
        (ctx.get("worker_report") or "(kein Worker-Bericht - Bootstrap)").strip(),
        "",
        "=== MARKER DES WORKERS (fehlende Werkzeuge / Programmwunsch) ===",
        (ctx.get("markers") or "(keine)").strip(),
        "",
        "=== NACHRICHTEN AUS DER /claude-QUEUE ===",
        (ctx.get("queue_block") or "(keine)").strip(),
        "",
        "=== ANKERDATEI analysis/r1b-workstream.md (Kopf) ===",
        (ctx.get("anchor") or "(nicht lesbar)").strip(),
        "",
        "=== SNAPSHOT / LAGE ===",
        (ctx.get("snapshot") or "(kein Snapshot)").strip(),
        "",
        "Antworte jetzt ausschliesslich im vereinbarten Blockformat (TELEGRAM_SUMMARY, "
        "DS_TOOLS, DS_INSTRUCTION; SUMMARY max. ca. 1500 Zeichen).",
    ]
    if ctx.get("note"):
        parts += ["", "=== NACHRICHT DES NUTZERS AN DICH ===", str(ctx["note"]).strip()]
    if ctx.get("extra"):
        parts += ["", str(ctx["extra"]).strip()]
    return "\n".join(parts)
