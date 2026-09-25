"""Worker-Runner (E1, E3, E4, E6, E7).

Ablauf eines Batches:
  1. Ghidra erreichbar?  (nur wenn das Profil MCP braucht)
  2. Programm stellen und VORHERN pruefen (Harness, nicht der Worker)
  3. Projekt-Sicherung, wenn das Profil in die Ghidra-DB schreiben kann
  4. Umgebung bauen + Vorher-Pruefung (keine fremden Token)
  5. Prozess starten, stream-json (UTF-8) mitschneiden, Ereignisse deduplizieren,
     Grenzen ueberwachen (ALARM per Telegram, HART = Prozess beenden)
  6. Nachher-Pruefung: Modell aus der Ausgabe; Snapshot schreiben
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from . import envs, pricing, secrets, streamjson
from .ghidra import Ghidra
from .proc import run_stream
from .profiles import builtin_args, load_profile
from .util import ensure_dir, now_iso, write_json_atomic, write_text_atomic


class WorkerResult:
    def __init__(self):
        self.rc: int | None = None
        self.duration_s = 0.0
        self.killed_reason: str | None = None
        self.alarms: list[str] = []
        self.limits: dict = {}
        self.model_seen: str | None = None
        self.model_ok: bool | None = None
        self.stats: dict = {}
        self.cost_usd = 0.0
        self.cost_naive_usd = 0.0
        self.final_text = ""
        self.snapshot_path: str | None = None
        self.stream_path: str | None = None
        self.run_dir: str | None = None
        self.profile: str | None = None
        self.program: str | None = None

    def describe(self) -> str:
        return (f"rc={self.rc} dauer={self.duration_s:.0f}s grenze={self.killed_reason or '-'} "
                f"anfragen={self.stats.get('requests')} kosten=${self.cost_usd:.4f} "
                f"modell={self.model_seen} (ok={self.model_ok})")


def run_dir(cfg, batch: int) -> Path:
    p = ensure_dir(Path(cfg.root) / "runs" / f"b{batch:03d}")
    return p


def write_mcp_config(cfg, run_path: Path, profile) -> str | None:
    """Schreibt die MCP-Konfiguration fuer genau diesen Lauf (Profil-abhaengig)."""
    if not profile.mcp:
        return None
    groups = profile.groups or str(cfg.get("ghidra", "bridge_groups", "listing,function,program"))
    data = {
        "mcpServers": {
            "ghidra": {
                "type": "stdio",
                "command": str(cfg.get("ghidra", "bridge_exe")),
                "args": ["--transport", "stdio", *list(cfg.get("ghidra", "bridge_args", ["--lazy"])),
                         "--default-groups", groups],
                "env": {},
            }
        }
    }
    p = write_json_atomic(run_path / "mcp.json", data)
    return str(p)


def build_command(cfg, profile, run_path: Path, session_id: str,
                  system_prompt_file: str | None = None) -> tuple[list[str], str | None]:
    """Kommandozeile OHNE Prompt - der Prompt geht über stdin (UTF-8).

    Beleg (offizielle Doku, Seite "Run Claude Code programmatically"):
      "Non-interactive mode reads stdin, so you can pipe data in" und
      "Piped stdin is capped at 10MB".
    Grund: die Windows-Kommandozeile ist bei ~32.000 Zeichen zu Ende; unsere
    Prompts (Vorspann + Auftrag + Queue) können deutlich größer werden.
    """
    exe = str(cfg.get("claude", "exe"))
    tools_value, allowed = builtin_args("worker")
    mcp_cfg = write_mcp_config(cfg, run_path, profile)
    cmd = [exe, "-p",
           "--output-format", "stream-json", "--verbose",
           "--strict-mcp-config",
           "--permission-prompts", "none",
           "--model", str(cfg.get("claude", "model_worker")),
           "--max-turns", str(int(cfg.get("claude", "max_turns_safety", 800))),
           "--tools", tools_value,
           "--session-id", session_id]
    if mcp_cfg:
        cmd += ["--mcp-config", mcp_cfg]
        allowed = allowed + profile.mcp_names()
    cmd += ["--allowedTools", *allowed]
    denied = profile.mcp_denied_names() if profile.mcp else ["mcp__ghidra"]
    cmd += ["--disallowedTools", *denied]
    if system_prompt_file:
        cmd += ["--append-system-prompt-file", system_prompt_file]
    return cmd, mcp_cfg


def run_batch(cfg, log, state, instruction: str, profile_name: str, program: str | None,
              queue_block: str = "", notify=None, tick=None, cancel=None, mock=False) -> WorkerResult:
    res = WorkerResult()
    res.profile = profile_name
    profile = load_profile(cfg.root, profile_name)
    res.program = program
    batch = state.batch
    rd = run_dir(cfg, batch)
    res.run_dir = str(rd)

    # --- 1./2. Ghidra -----------------------------------------------------------------
    if profile.mcp and not mock:
        gh = Ghidra(cfg, log)
        if not gh.ensure_server(log):
            raise RuntimeError("Ghidra-Server nicht erreichbar - Batch startet NICHT")
        wanted = str(program or cfg.get("ghidra", "program_default"))
        chk = gh.ensure_program(wanted, log)
        for step in chk.get("steps", []):
            log.info("Ghidra: " + str(step))
        if not chk.get("ok"):
            raise RuntimeError(f"Programmwechsel fehlgeschlagen (gewuenscht {wanted})")
        res.program = "/" + str(chk.get("current"))
        # --- 3. Sicherung, wenn das Profil schreiben darf -----------------------------
        if profile.writes_ghidra:
            bk = gh.backup_project(log, reason=f"vor Batch {batch} (Profil {profile_name})")
            if not bk.get("ok"):
                raise RuntimeError("Ghidra-Sicherung fehlgeschlagen - Batch mit Schreibprofil startet NICHT")
            res.limits["ghidra_backup"] = bk.get("path")

    # --- Auftrag schreiben -------------------------------------------------------------
    prompt = build_prompt(cfg, instruction, queue_block, res.program, profile_name)
    write_text_atomic(rd / "auftrag.md", prompt)

    # --- 4. Umgebung -------------------------------------------------------------------
    token = secrets.load(cfg.secrets_dir, secrets.DEEPSEEK)
    env = envs.worker_env(cfg, os.environ, token)
    bad = envs.precheck(env, "worker")
    if bad:
        raise RuntimeError(f"Umgebungs-Vorher-Pruefung fehlgeschlagen: {bad}")
    log.info("Worker-Umgebung geprueft", env=envs.describe(env))

    # --- 5. Lauf -----------------------------------------------------------------------
    if mock:
        from .mock import mock_worker_stream
        mode = str(cfg.get("mock", "worker_mode", "ok"))
        stream_path = mock_worker_stream(cfg, rd, instruction, log, mode=mode)
        res.stream_path = str(stream_path)
        stats = streamjson.StreamStats()
        for line in Path(stream_path).read_text(encoding="utf-8").splitlines():
            stats.feed(line)
        rc_file = Path(rd) / "mock_rc.txt"
        res.rc = int(rc_file.read_text(encoding="utf-8").strip()) if rc_file.is_file() else 0
        res.duration_s = 1.0
        if res.rc != 0:
            res.killed_reason = "mock_crash"
    else:
        session_id = str(uuid.uuid4())   # --session-id verlangt eine echte UUID (mit Bindestrichen)
        cmd, _mcp = build_command(cfg, profile, rd, session_id)
        if len(prompt.encode("utf-8")) > MAX_STDIN_BYTES:
            raise RuntimeError(f"Prompt zu groß für stdin ({len(prompt)} Zeichen)")
        stream_path = rd / "stream.jsonl"
        stats = streamjson.StreamStats()
        lim = {
            "alarm_wall": float(cfg.get("limits", "alarm_wall_s", 5400)),
            "alarm_requests": int(cfg.get("limits", "alarm_requests", 250)),
            "alarm_cost": float(cfg.get("limits", "alarm_cost_usd", 1.0)),
            "hard_wall": float(cfg.get("limits", "hard_wall_s", 10800)),
            "hard_requests": int(cfg.get("limits", "hard_requests", 400)),
            "hard_cost": float(cfg.get("limits", "hard_cost_usd", 2.0)),
        }
        fired: set[str] = set()
        extra_dates = list(cfg.get("peak", "extra_offpeak_dates", []) or [])

        def on_event(line: str):
            if tick is not None:
                try:
                    tick()
                except Exception:
                    pass
            stats.feed(line)
            t = stats.totals()
            cost = stats.cost_usd(extra_dates)
            for key, cond, text in (
                ("alarm_requests", t["requests"] >= lim["alarm_requests"],
                 f"ALARM: {t['requests']} Anfragen erreicht (Alarmgrenze {lim['alarm_requests']})"),
                ("alarm_cost", cost >= lim["alarm_cost"],
                 f"ALARM: Kosten ${cost:.3f} erreicht (Alarmgrenze ${lim['alarm_cost']:.2f})"),
            ):
                if cond and key not in fired:
                    fired.add(key)
                    res.alarms.append(text)
                    if notify:
                        notify(text)
            if t["requests"] >= lim["hard_requests"]:
                res.killed_reason = "hard_requests"
                return "kill"
            if cost >= lim["hard_cost"]:
                res.killed_reason = "hard_cost"
                return "kill"
            return None

        run = run_stream(cmd, env, cwd=str(cfg.decomp), out_path=stream_path,
                         on_event=on_event, hard_wall_s=lim["hard_wall"], log=log,
                         cancel=cancel, stdin_text=prompt, stderr_path=rd / "stream.err.txt")
        res.rc = run.rc
        res.duration_s = run.duration_s
        res.killed_reason = res.killed_reason or run.killed_reason
        res.stream_path = str(stream_path)
        if res.duration_s >= lim["alarm_wall"]:
            res.alarms.append(f"ALARM: Laufzeit {res.duration_s:.0f}s (Alarmgrenze {lim['alarm_wall']:.0f}s)")

    # --- 6. Nachher-Pruefung + Snapshot ------------------------------------------------
    res.stats = stats.totals()
    extra_dates = list(cfg.get("peak", "extra_offpeak_dates", []) or [])
    res.cost_usd = stats.cost_usd(extra_dates)
    res.cost_naive_usd = stats.cost_naive_usd(extra_dates)
    res.final_text = stats.final_text()
    res.model_seen = stats.model
    expected = str(cfg.get("claude", "model_worker"))
    res.model_ok = bool(res.model_seen) and res.model_seen.lower().replace(" ", "") == expected.lower()
    if res.model_ok is False:
        log.error("MODELL-ABWEICHUNG im Worker", erwartet=expected, gesehen=res.model_seen)
    res.stats["tool_counts"] = dict(stats.tool_counts)
    res.stats["denials"] = list(stats.denials)[:5]
    res.stats["api_errors"] = list(stats.api_errors)[:5]
    res.stats["num_turns"] = stats.num_turns()
    res.stats["total_cost_usd_field"] = stats.total_cost_usd_field()
    res.stats["tariff_now"] = pricing.tariff(None, extra_dates)

    payload = {
        "batch": batch, "profile": profile_name, "program": res.program,
        "rc": res.rc, "duration_s": res.duration_s, "killed_reason": res.killed_reason,
        "alarms": res.alarms, "stats": res.stats, "cost_usd": res.cost_usd,
        "cost_naive_usd": res.cost_naive_usd, "model_seen": res.model_seen,
        "model_ok": res.model_ok, "finished_at": now_iso(),
    }
    write_json_atomic(rd / "result.json", payload)
    write_text_atomic(rd / "antwort.md", res.final_text)
    res.snapshot_path = write_snapshot(cfg, state, res, stats, log)
    return res


WORKER_PREAMBLE = """Du bist der Worker (DeepSeek über Claude Code) im Projekt Silent Scope Decomp.

Es ist NIEMAND anwesend: Rückfragen sind nicht möglich. Warte nie auf eine Antwort,
entscheide selbst und dokumentiere die Entscheidung. Fehlt dir etwas (Werkzeug, Programm,
Information), meldest du es am Ende im Abschlussbericht.

ARBEITSUMFELD
- Arbeitsverzeichnis: das echte Decomp-Repo; hier gelten die Projektregeln.
- Projektregeln: AGENTS.md im Repo-Wurzelverzeichnis — lies sie und halte sie ein
  (Batch-Reihenfolge: git status, Memory-Sync, Mesa-Check, genau EIN preflight-Lauf,
  Bilanz, Memory-Export, Commit; Ankerblock am Ende aktualisieren).
- Immer verfügbar: Dateien lesen, schreiben, bearbeiten, Suchen (Glob/Grep), PowerShell.
- Ghidra liegt am MCP-Server `ghidra` (Profil und Programm unten). Adressbasierte Aufrufe
  immer mit `program="<name>"` versehen.
- Ein Programmwechsel ist NICHT erlaubt; Ghidra-Skripte und der Debugger sind gesperrt.

ABLAUF
1. Auftrag lesen, dann Anker/Regeln lesen, dann arbeiten.
2. Den Auftrag vollständig abarbeiten — mehrere Teile in einem Zug, kein Mini-Schritt.
3. Stopp-Bedingungen des Auftrags beachten: ist etwas nicht belegbar, dokumentieren und
   mit dem nächsten Teil weitermachen statt abzubrechen.
4. Keine Rücknahme von Belegen: Analyse- und Belegdateien werden nicht gelöscht.

ABSCHLUSSBERICHT (letzte Nachricht, Pflicht in dieser Gliederung)
## 1) Übernommener Stand (5 Sätze)
## 2) Was ich untersucht habe (Dateien/Belege)
## 3) Befunde mit Einstufung (CONFIRMED / STRONG INFERENCE / HYPOTHESIS), je mit Datei:Zeile
## 4) Was ich geändert habe (Dateien + Commit-Hash)
## 5) Nächster Schritt (Vorschlag an den Reviewer)
## 6) Marker (nur falls nötig)

MARKER (genau so schreiben, einer pro Zeile, am Ende des Berichts)
<TOOL_REQUEST>mcp__ghidra__read_memory</TOOL_REQUEST>
<PROGRAM_REQUEST>/830d01.27p.be.bin</PROGRAM_REQUEST>
"""

# Harte Grenze der stdin-Übergabe (Doku: "Piped stdin is capped at 10MB").
MAX_STDIN_BYTES = 9_000_000


def build_prompt(cfg, instruction: str, queue_block: str, program: str | None, profile: str) -> str:
    """Vorspann + Auftrag + Queue. Der Worker bekommt KEINE Rückfragemöglichkeit."""
    parts = [WORKER_PREAMBLE]
    umfeld = [f"Ghidra-Profil dieses Laufs: {profile}"]
    if program:
        umfeld.append(f"Aktuelles Ghidra-Programm (vom Harness gestellt): {program}")
    else:
        umfeld.append("Kein Ghidra-Programm gestellt (Profil ohne Ghidra-Zugriff).")
    parts += ["", "UMFELD DIESES LAUFS", *umfeld, "", "=== AUFTRAG (vom Reviewer) ===",
              instruction.strip()]
    if queue_block:
        parts += ["", queue_block.strip()]
    return "\n".join(parts) + "\n"


def write_snapshot(cfg, state, res: WorkerResult, stats: streamjson.StreamStats, log) -> str:
    """Kompakter Review-Kontext (Abschnitt G): Kennzahlen, Werkzeuge, Texte."""
    snap_dir = ensure_dir(Path(cfg.root) / "snapshots" / f"b{state.batch:03d}")
    anchor = ""
    try:
        lines = Path(cfg.anchor_file).read_text(encoding="utf-8", errors="replace").splitlines()
        anchor = "\n".join(lines[:6])
    except OSError:
        anchor = "(Ankerdatei nicht lesbar)"

    tools_tsv = "\n".join(f"{n}\t{c}" for n, c in stats.tool_table())
    write_text_atomic(snap_dir / "tools.tsv", tools_tsv + "\n")

    reasoning = []
    if res.stream_path:
        for line in Path(res.stream_path).read_text(encoding="utf-8", errors="replace").splitlines():
            if '"thinking"' in line or '"redacted_thinking"' in line:
                reasoning.append(line)
    if reasoning:
        write_text_atomic(snap_dir / "reasoning.jsonl", "\n".join(reasoning) + "\n")

    t = res.stats
    body = f"""# Snapshot Batch {state.batch} (Worker)

## Harness-Kennzahlen
- Profil: {res.profile} | Programm: {res.program or '-'}
- Exit-Code: {res.rc} | Dauer: {res.duration_s:.0f}s | Grenze ausgeloest: {res.killed_reason or 'nein'}
- Alarmmeldungen: {'; '.join(res.alarms) if res.alarms else 'keine'}
- Anfragen: {t.get('requests')} | Eingabe Miss: {t.get('input_miss')} | Cache-Hit: {t.get('cache_read')} \
| Cache-Neu: {t.get('cache_creation')} | Ausgabe: {t.get('output')}
- Kosten (gerechnet, Tarif je Aufruf): ${res.cost_usd:.4f} (Gegenprobe alles zum Jetzt-Tarif: ${res.cost_naive_usd:.4f})
- Tarif beim Abschluss: {t.get('tariff_now')}
- Modell laut Ausgabe: {res.model_seen} (Soll erfuellt: {res.model_ok})
- num_turns: {t.get('num_turns')} | total_cost_usd-Feld (nicht massgeblich): {t.get('total_cost_usd_field')}
- Abgelehnte Werkzeugaufrufe: {t.get('denials') or 'keine'}

## Ankerkopf (Projektkonvention)
```
{anchor}
```

## Werkzeugnutzung
```
{tools_tsv or '(keine)'}
```

## Abschlussbericht des Workers
{res.final_text or '(leer)'}

## Dateiaenderungen (Decomp-Repo, Stand jetzt)
```json
{json.dumps(_git_status(cfg), ensure_ascii=False, indent=1)}
```
"""
    p = write_text_atomic(snap_dir / "snapshot.md", body)
    if log:
        log.info("Snapshot geschrieben", datei=str(p), zeichen=len(body))
    return str(p)


def _git_status(cfg) -> dict:
    from .gitsafe import Git
    g = Git(cfg)
    try:
        st = g.status_porcelain()
        return {"head": g.head_short(), "subject": g.head_subject(), "dirty": st[:40],
                "dirty_count": len(st)}
    except Exception as exc:
        return {"error": str(exc)[:200]}
