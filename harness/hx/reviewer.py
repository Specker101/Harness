"""Reviewer-Runner (E2, E3): Claude Code ueber das Pro-Abo, nur Read/Grep/Glob.

Isolation (E3): nur CLAUDE_CODE_OAUTH_TOKEN im Prozess, KEINE DeepSeek-Variablen.
Rollenanweisung: prompts/reviewer.md (stabiler Systemprompt-Praefix, cache-freundlich).
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from . import envs, protocol, secrets, streamjson
from .proc import run_stream
from .profiles import (builtin_args, credential_verbote, git_schreib_verbote,
                       nur_lese_git_regeln, pfad_regeln, secrets_verbote)
from .util import ensure_dir, now_iso, read_text, write_json_atomic, write_text_atomic

# R13p: Name des Shell-Werkzeugs fuer die Nur-Lese-Git-Befehle. Unter Windows laeuft
# die CLI mit CLAUDE_CODE_USE_POWERSHELL_TOOL=1 (envs.reviewer_env), damit die Regeln
# `PowerShell(...)` heissen und die CLI den AST parst (Aliase werden normalisiert).
GIT_TOOL = "PowerShell"


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
        self.secret_hits: list[dict] = []    # R13g: Schluessel-Zugriffe/Werte im Mitschnitt
        self.rate_limit: dict = {}           # R13p: Abo-Auslastung aus diesem Lauf

    def describe(self) -> str:
        base = f"rc={self.rc} dauer={self.duration_s:.0f}s modell={self.model_seen} limit={self.limit_reached}"
        if self.parsed:
            base += " " + self.parsed.describe()
        return base


def prompt_hash(cfg) -> str:
    """Hash des Systemprompts `prompts/reviewer.md` (12 Hexzeichen; '' wenn unlesbar).

    R13ab (gemessen, Beleg `docs/_r13ab_probe.txt`): die Claude-CLI liest
    `--append-system-prompt-file` bei **`--resume` NICHT neu** - eine Aenderung an
    `prompts/reviewer.md` erreicht eine LAUFENDE Session also nicht. Der Harness haengt die
    Datei zwar bei jedem Aufruf an (`build_command`), aber das genuegt nicht.

    Deshalb merkt sich der Zustand den Hash der Fassung, mit der die Session angelegt
    wurde (`state.reviewer_new_session(prompt_hash=…)`); `orchestrator.do_review`
    vergleicht ihn vor jedem Review und rotiert, wenn er sich geaendert hat.
    """
    import hashlib
    try:
        roh = (Path(cfg.prompts_dir) / "reviewer.md").read_bytes()
    except OSError:
        return ""
    return hashlib.sha256(roh).hexdigest()[:12]


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
    # R13p: Die Shell ist NUR fuer vier Nur-Lese-Git-Befehle da (Doku:
    # code.claude.com/docs/en/permissions). Das Werkzeug wird gestellt, aber seine
    # Erlaubnisliste enthaelt ausschliesslich `git log/show/diff/status *` - im
    # `-p`-Lauf wird jeder andere Aufruf abgelehnt (keine Rueckfrage moeglich).
    tools_value = ",".join([*allowed, GIT_TOOL])
    cmd = [exe, "-p",
           "--output-format", "stream-json",
           "--verbose",
           "--model", str(cfg.get("claude", "model_reviewer", "claude-opus-5-5")),
           "--strict-mcp-config",
           "--permission-prompts", "none",
           "--max-turns", "40",
           "--tools", tools_value,
           # R13f: Lesen ist pfadgebunden. Gemessen 2026-09-26 konnte der Reviewer mit
           # einem ungebundenen `Read` auch `g:\Harness\secrets` oeffnen.
           "--allowedTools", *pfad_regeln((cfg.root, cfg.decomp)), *nur_lese_git_regeln(GIT_TOOL),
           "--disallowedTools", "Bash", "WebFetch", "WebSearch", "Task", "NotebookEdit",
           "TodoWrite", "SlashCommand", "Skill", "mcp__ghidra",
           # R13p: schreibende Git-Befehle und jede fremde Shell-Arbeit ausdruecklich
           # verbieten (Deny schlaegt Allow).
           *git_schreib_verbote(GIT_TOOL),
           *secrets_verbote(cfg.secrets_dir, *secrets.ALT_ORTE),
           # R13o: auch der Reviewer hat eine `.credentials.json` in seinem
           # CLAUDE_CONFIG_DIR (cc-reviewer) - und dieses Verzeichnis liegt IN seiner
           # erlaubten Wurzel. Ohne diese Regeln koennte er den Abo-Token des eigenen
           # Kontos oeffnen und zitieren.
           *credential_verbote((cfg.root, cfg.decomp)),
           # R13f: Wurzel fuer den Pfadbereich anmelden. Sonst gilt ein absoluter
           # Pfad ausserhalb des Arbeitsverzeichnisses als "draussen" und wird
           # abgelehnt, obwohl die Regel ihn erlaubt (gemessen: harness.toml war
           # ohne --add-dir VERWEIGERT). `secrets` ist ein Geschwisterordner von
           # `harness` und damit weiterhin ausserhalb.
           "--add-dir", str(cfg.root),
           "--add-dir", str(cfg.decomp)]
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

    # R13g: Schluessel-Zugriffe im Reviewer-Mitschnitt. Nach dem Lauf geprueft (der
    # Reviewer liest nur; ein Zugriff waere ein Befund, kein Notfall) - der Harness
    # alarmiert daraufhin.
    try:
        res.secret_hits = streamjson.scanne_mitschnitt(cfg, res.raw_path) if not mock else []
    except Exception as exc:                                     # noqa: BLE001
        if log:
            log.warn("Secret-Pruefung des Review-Mitschnitts fehlgeschlagen", err=str(exc)[:150])
    if res.secret_hits:
        streamjson.schreibe_secret_beleg(cfg, res.secret_hits, "Reviewer", None)
        if log:
            log.error("SECRET-ZUGRIFF", rolle="Reviewer",
                      treffer=[f"{h['werkzeug']}:{h['art']}:{h['name']}" for h in res.secret_hits])

    # R13p: Abo-Auslastung aus dem Review-Mitschnitt ablegen (fuer /status und die
    # 80-%-Warnung). Nur die Zeilen mit `rate_limit_event` werden gelesen.
    if not mock and res.raw_path:
        try:
            info = streamjson.rate_limit_aus_mitschnitt(cfg, res.raw_path)
            if info:
                streamjson.schreibe_rate_limit(cfg, info, "Reviewer")
                res.rate_limit = info
        except Exception as exc:                                 # noqa: BLE001
            if log:
                log.warn("Nutzerlimit nicht auswertbar", err=str(exc)[:150])

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
    # R13bj: Nummernzeile und Nummernregel kommen FERTIG aus dem Orchestrator
    # (`batch_number_line` / `batch_nummer_regel`) - EINE Quelle, damit Prompt und
    # Pruefung (`gate_from_review`) nicht auseinanderlaufen. Die alte Fassung baut nur
    # noch, wer den Kontext von Hand stellt (Tests).
    nummer = ctx.get("batch_nummer_zeile") or ""
    regel = ctx.get("batch_nummer_regel") or ""
    if not nummer:
        if nxt:
            nummer = ("Naechster Batch laut Anker: " + str(nxt)
                      + (f" (Anker-Kopf nennt BATCH {anker})" if anker else "")
                      + (f"; Querverweis im Anker: B{hint}" if hint else ""))
        else:
            nummer = "Naechster Batch laut Anker: UNBEKANNT (der Anker nennt keine Nummer)"
    if not regel:
        if nxt:
            regel = (f"Verbindlich: die DS_INSTRUCTION MUSS mit \"Batch {nxt} - ...\" beginnen. "
                     "Nenne KEINE andere Nummer. Nennt die Instruktion eine andere Nummer als "
                     "der Harness erwartet, startet er den Batch NICHT und haelt mit Meldung an.")
        else:
            regel = ("Verbindlich: die DS_INSTRUCTION muss eine Nummer im Format "
                     "\"Batch <N> - ...\" nennen (naechste freie Nummer).")
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
        # R13p: der Diff des bewerteten Batches - ohne ihn urteilt der Reviewer blind.
        "=== BATCH-DIFF (was der bewertete Batch geaendert hat) ===",
        (ctx.get("diff") or "(kein Diff ermittelbar)").strip(),
        "",
        "=== HISTORIE (aeltere Batches: Commits und Belegdateien) ===",
        (ctx.get("historie") or "(keine Historie ermittelbar)").strip(),
        "",
        # R13s: PLAN/IST der letzten Batches + verbindliche Zuschnitt-Regel.
        "=== PLAN/IST DER LETZTEN BATCHES (gemessen aus den Belegdateien, rein lesend) ===",
        (ctx.get("plan_ist") or "(keine PLAN/IST-Daten)").strip(),
        "REGEL (Nutzerauftrag 2026-09-28, R13ac): Der Bau-Umfang des naechsten Batches "
        "orientiert sich am MEDIAN der gemessenen C Koepfe der **C-Batches mit "
        "SOLL-KOEPFE > 0** aus der PLAN/IST-Tafel; das Ziel darf hoechstens ca. das "
        "1,3-fache des Median sein. Steht in der Tafel kein solcher Batch (heute: keine "
        "SOLL-KOEPFE-Zeile), ist der Median nicht gemessen - dann gilt die Regel nicht "
        "und die Sollzahl MUSS als eigene Zeile `SOLL-KOEPFE: <n>` in der "
        "DS_INSTRUCTION stehen. Weicht die DS_INSTRUCTION vom Median ab, begruende das "
        "in EINEM Satz in der TELEGRAM_SUMMARY.",
        "",
        # R13ag: die Pflichtbloecke des BEWERTETEN Auftrags stehen wortgleich hier - aus
        # ihnen werden die `UEBERTRAG:`/`VERWORFEN:`-Zeilen. Vorher las der Reviewer sie
        # selbst aus `runs/b<N>/auftrag.md`; dabei verschwand B213 Nachrueckliste 1.
        "=== PFLICHTBLOECKE DER BEWERTETEN INSTRUKTION "
        "(NACHRUECKLISTE + STREICHREIHENFOLGE, wortgleich) ===",
        (ctx.get("pflichtbloecke") or "(nicht ermittelbar)").strip(),
        "REGEL (R13ag): Jeder Posten braucht im Review eine Zeile UEBERTRAG oder "
        "VERWORFEN oder erscheint als erledigt mit Beleg.",
        "",
        "=== NACHRICHTEN AUS DER /claude-QUEUE ===",
        (ctx.get("queue_block") or "(keine)").strip(),
        "",
        # R13t (Nutzerauftrag 2026-09-28): die /ds-Nachrichten des BEWERTETEN Batches
        # gehoeren in den Review - der Reviewer soll pruefen, ob der Worker sie
        # umgesetzt hat, und offene Punkte in die naechste Instruktion tragen.
        "=== NUTZER-NACHRICHTEN AN DEN WORKER DIESES BATCHES (/ds) ===",
        (ctx.get("ds_queue") or "(keine)").strip(),
        "REGEL (Nutzerauftrag 2026-09-28): Diese Nachrichten sind fuer den Worker "
        "bindend. Pruefe im Review, ob sie umgesetzt sind; was offen blieb, nennst "
        "du in der TELEGRAM_SUMMARY und traegst es in die naechste DS_INSTRUCTION "
        "(oder als Marker), damit es nicht untergeht. R13af (2026-09-29): EIN "
        "TEILPUNKT IST KEINE NACHRICHT - jeder offene Teilpunkt bekommt eine Zeile "
        "`UEBERTRAG: <Teilpunkt> -> <Ziel>` bzw. `VERWORFEN: <Teilpunkt> - <Grund>`; "
        "wird eine Nachricht nur als ZUSAMMENFASSUNG zugestellt, gehoert eine Tafel "
        "mit einer Zeile je Teilpunkt dazu (Rollenanweisung, Abschnitt \"Ersetzte "
        "/ds-Nachrichten\").",
        "",
        # R13v3 (Nutzerauftrag 2026-09-28): ein abgebrochener Lauf ist kein normaler Lauf.
        "=== ABBRUCH DES BEWERTETEN LAUFS (nur wenn zutreffend) ===",
        (ctx.get("abbruch") or "kein Abbruch - der Lauf ist regulaer zu Ende gegangen").strip(),
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
        # R13aa (Punkt 1, Aussensicht-Nachbesserung aus runs/meta-209.md): die
        # Pflichtzeilen des Reviews werden geprueft. Fehlt `B-SCHRITT:`, kann der Harness
        # den B-Fortschritt nicht messen UND der Ausloeser "Kernzahl ohne Bewegung" haelt
        # einen B-Batch fuer einen C-Batch (gemessen B208/B209). Deshalb steht hier, was
        # dieser Review ueber den Strang des bewerteten Batches schreiben MUSS.
        "=== PROTOKOLL-WARNUNG (Pflichtzeilen im Review) ===",
        (ctx.get("protokoll_warnung")
         or "(nichts offen - die Pflichtzeilen sind vollstaendig)").strip(),
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
