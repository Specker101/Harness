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
        self.model_expected: str | None = None
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

    R13b: Bei `new_session` wird IMMER eine frische Kennung erzeugt - auch wenn
    `session_id` gesetzt ist. Sonst liefe der "neue" Review in der alten Session
    und Claude Code bricht ab ("Session ID <id> is already in use"), wie im
    fehlerhaften Lauf vom 2026-09-25 (runs/b159/reviewer.jsonl.err).
    """
    exe = str(cfg.get("claude", "exe"))
    _tools_value, allowed = builtin_args("reviewer")
    cmd = [exe, "-p",
           "--output-format", "stream-json",
           "--verbose",
           "--model", str(cfg.get("claude", "model_reviewer", "claude-opus-5-5")),
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
        # Bei `new_session` MUSS der Aufrufer eine frische Kennung uebergeben
        # (`orchestrator.do_review`); fehlt sie, wird hier eine erzeugt. Die alte Kennung
        # darf hier nie landen - genau das liess Claude Code mit "Session ID <id> is
        # already in use" abbrechen (R13b).
        cmd += ["--session-id", session_id or str(uuid.uuid4())]
    return cmd


def session_id_of_command(cmd: list[str]) -> str | None:
    """Die Kennung, mit der dieses Kommando laeuft (--session-id oder --resume)."""
    for flag in ("--session-id", "--resume"):
        if flag in cmd:
            i = cmd.index(flag)
            if i + 1 < len(cmd):
                return cmd[i + 1]
    return None


def _stream_result(body: str) -> tuple[str, str | None, str | None]:
    """Ergebnis, Session und Modell aus der Ausgabe lesen.

    Unterstuetzt stream-json (viele Ereigniszeilen, Ergebnis am Ende) UND die
    alte Form (eine JSON-Zeile). Grundsatz: lieber beide Formate lesen als eines
    annehmen - ein Formatwechsel darf den Review nicht kosten.
    """
    text, session, model = "", None, None
    for ln in (body or "").splitlines():
        if not ln.strip():
            continue
        try:
            obj = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        typ = obj.get("type")
        if typ == "assistant":
            m = (obj.get("message") or {}).get("model") or obj.get("model")
            if m and not model:
                model = str(m)
            continue
        if typ == "result" or (typ is None and obj.get("result")):
            text = str(obj.get("result") or text or "")
            session = str(obj.get("session_id") or session or "") or session
            mu = obj.get("modelUsage") or {}
            if isinstance(mu, dict) and mu:
                model = ",".join(list(mu.keys())[:3])
    return text, session, model


def run_review(cfg, log, prompt: str, session_id: str | None = None, new_session: bool = False,
               mock: bool = False, mock_mode: str = "ok", stream_path=None,
               mock_batch: int | None = None, attempt: int = 1) -> ReviewResult:
    res = ReviewResult()
    rd = ensure_dir(Path(cfg.root) / "logs")

    if mock:
        from .mock import mock_reviewer_stream, mock_reviewer_text
        res.text = mock_reviewer_text(mock_mode, batch=mock_batch, attempt=attempt)
        res.rc = 0
        res.duration_s = 0.5
        # Wie im echten Lauf: die Kennung kommt aus der Kommandozeile. Bei `new_session`
        # ist das die frische Kennung, die der Aufrufer uebergeben hat.
        res.session_id = session_id_of_command(build_command(cfg, session_id, new_session))
        # Im Attrappenbetrieb muss die Modell-Nachpruefung (R11-5c) ebenfalls greifen -
        # deshalb traegt die Attrappe das Konfigurationsmodell.
        res.model_seen = str(cfg.get("claude", "model_reviewer", "claude-opus-5-5")) + " (mock)"
        if mock_mode == "modell_falsch":
            res.model_seen = "claude-sonnet-5 (mock)"
        if mock_mode == "reviewer_crash":
            res.rc = 1
            res.text = ""
        if stream_path:
            res.raw_path = str(mock_reviewer_stream(Path(stream_path).parent, mock_batch,
                                                    mode=mock_mode, attempt=attempt))
        else:
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
        # R13b: die Kennung, mit der dieser Versuch laeuft - auch wenn er scheitert.
        res.session_id = session_id_of_command(cmd)
        raw = Path(stream_path) if stream_path else rd / f"reviewer-{now_iso().replace(':', '')}.json"
        # Prompt mitschneiden: belegt, was der Reviewer wirklich bekommen hat.
        write_text_atomic(rd / f"review-prompt-{now_iso().replace(':', '')}.md", prompt)
        run = run_stream(cmd, env, cwd=str(cfg.decomp), out_path=raw, log=log,
                         stdin_text=prompt)
        res.rc = run.rc
        res.duration_s = run.duration_s
        res.raw_path = str(raw)
        body = read_text(raw)
        err = read_text(str(raw) + ".err")
        res.text, sid, model = _stream_result(body)
        res.session_id = sid or res.session_id or session_id
        if model:
            res.model_seen = model
        if not res.text:
            res.text = body.strip()[:4000]
        if protocol.looks_like_limit(body + "\n" + err) or protocol.looks_like_limit(res.text):
            res.limit_reached = True
        if not res.text and res.rc not in (0, None):
            res.error = f"Reviewer ohne Ergebnis (rc={res.rc}): {err.strip()[:300]}"

    res.parsed = protocol.parse_review(res.text)
    # --- Nachher-Pruefung (E3, R11-5c): Modell muss das konfigurierte sein ------------
    res.model_expected = str(cfg.get("claude", "model_reviewer", "claude-opus-5-5"))
    res.model_ok = bool(res.model_seen) and res.model_expected.lower() in str(res.model_seen).lower()
    if not res.model_ok:
        res.error = (f"Reviewer-Modell weicht ab: laut Ausgabe {res.model_seen!r}, "
                     f"erwartet {res.model_expected!r}")
        if log:
            log.error("REVIEWER-MODELL-ABWEICHUNG", erwartet=res.model_expected,
                      gesehen=str(res.model_seen))
    write_text_atomic(rd / f"review-{now_iso().replace(':', '')}.md",
                      res.text or "(leer)")
    if log:
        log.info("Review fertig", info=res.describe())
    return res


REVIEW_RETRY_HINT = """Deine vorige Antwort enthielt KEINEN gueltigen Protokollblock. Ohne die
Bloecke kann der Harness nichts freigeben - es wird NICHTS gestartet, bis das Format stimmt.

Antworte jetzt GENAU so, ohne Einleitung und ohne Text davor/danach:

<TELEGRAM_SUMMARY>
(kurze Zusammenfassung fuer den Nutzer, max. ca. 1500 Zeichen)
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: none|ghidra-read|ghidra-standard|ghidra-full
program: /830d01.27p.main.bin
</DS_TOOLS>

<DS_INSTRUCTION>
Batch <Nummer aus dem Messdatenblock> - ...
(vollstaendige Instruktion fuer genau diesen Batch)
</DS_INSTRUCTION>

Die drei Bloecke sind Pflicht. `profile: none` heisst: kein Ghidra-Programm angeben.
"""


HANDOVER_PROMPT = """UEBERGABE. Diese Session wird jetzt beendet, eine neue uebernimmt den Dienst.

Fasse in hoechstens 1500 Zeichen zusammen, was die neue Session wissen muss:
- was zuletzt passiert ist (Batch, Stand laut Anker),
- getroffene Entscheidungen und ihre Gruende,
- offene Punkte, Fallstricke und Regeln, die du in dieser Session gelernt hast,
- was die neue Session zuerst lesen soll.

Keine Werkzeuge, keine Dateien, keine Einleitung, keine Entschuldigung - nur dieser Text.
"""


def run_handover(cfg, log, session_id: str, mock: bool = False, stream_path=None,
                 max_turns: int = 4) -> str:
    """Die alte Session um eine Uebergabe bitten, BEVOR die neue startet (R13-2)."""
    if mock:
        return ("(Attrappe) Uebergabe der vorigen Session: Stand laut Anker, Entscheidungen "
                "und offene Punkte stehen im Messdatenblock.")
    oauth = secrets.load(cfg.secrets_dir, secrets.CLAUDE_OAUTH)
    env = envs.reviewer_env(cfg, os.environ, oauth)
    cmd = build_command(cfg, session_id, new_session=False)
    if "--max-turns" in cmd:
        cmd[cmd.index("--max-turns") + 1] = str(max_turns)
    if stream_path:
        raw = ensure_dir(Path(stream_path).parent) / Path(stream_path).name
    else:
        raw = Path(cfg.sub("logs")) / f"handover-{now_iso().replace(':', '')}.json"
    run = run_stream(cmd, env, cwd=str(cfg.decomp), out_path=raw, log=log,
                     stdin_text=HANDOVER_PROMPT, hard_wall_s=600)
    body = read_text(raw)
    text, _sid, model = _stream_result(body)
    if not text:
        text = body.strip()[:2000]
    if log:
        log.info("Uebergabe angefordert", rc=run.rc, zeichen=len(text), modell=model or "-",
                 datei=str(raw))
    return text.strip()


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
    nxt = ctx.get("next_batch") or 0
    anker = ctx.get("anchor_batch")
    hint = ctx.get("anchor_hint")
    if nxt:
        nummer = ("Naechster Batch laut Anker: " + str(nxt)
                  + (f" (Anker-Kopf nennt BATCH {anker})" if anker else "")
                  + (f"; Querverweis im Anker: B{hint}" if hint else ""))
        regel = (f"Verbindlich: die DS_INSTRUCTION MUSS mit \"Batch {nxt} - ...\" beginnen. "
                 "Nenne KEINE andere Nummer. Es gibt keinen internen Zaehler: die Nummer kommt "
                 "ausschliesslich aus dem Anker. Nennt die Instruktion eine andere Nummer, startet "
                 "der Harness den Batch NICHT und haelt mit Meldung an.")
    else:
        nummer = ("Naechster Batch laut Anker: UNBEKANNT (der Anker nennt keine Nummer)")
        regel = ("Verbindlich: die DS_INSTRUCTION muss eine Nummer im Format \"Batch <N> - ...\" "
                 "nennen (naechste freie Nummer nach dem Anker).")
    parts = [
        kind_text,
        nummer,
        regel,
        (f"Zuletzt gelaufener Batch: {batch}" if batch else "Bisher gelaufene Batches: keine"),
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
        "=== UEBERGABE AUS DER VORIGEN SESSION ===",
        (ctx.get("handover") or "(keine Uebergabe - du liest den Stand selbst aus Anker "
                                "und Messdaten)").strip(),
        "",
        "=== SNAPSHOT / LAGE ===",
        (ctx.get("snapshot") or "(kein Snapshot)").strip(),
        "",
        "Antworte jetzt ausschliesslich im vereinbarten Blockformat (TELEGRAM_SUMMARY, "
        "DS_TOOLS, DS_INSTRUCTION; SUMMARY max. ca. 1500 Zeichen).",
    ]
    if ctx.get("note"):
        parts += ["", "=== NACHRICHT DES NUTZERS AN DICH ===", str(ctx["note"]).strip()]
    if ctx.get("retry_hint"):
        # R13b: zweiter Versuch - ausdrueckliche Format-Erinnerung + Rohtext.
        parts += ["", "=== FORMAT-ERINNERUNG (ZWEITER VERSUCH) ===",
                  REVIEW_RETRY_HINT.strip()]
        if ctx.get("previous_raw"):
            parts += ["", "=== DEINE VORIGE ANTWORT (ohne gueltigen Protokollblock) ===",
                      str(ctx["previous_raw"]).strip()[:4000]]
    if ctx.get("extra"):
        parts += ["", str(ctx["extra"]).strip()]
    return "\n".join(parts)
