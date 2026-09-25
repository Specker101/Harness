"""Kommandozeile des Harness.

  python -m hx.cli run            [--mock] [--config PFAD]
  python -m hx.cli status
  python -m hx.cli budget
  python -m hx.cli profiles
  python -m hx.cli probe-telegram
  python -m hx.cli allowlist-add <USER_ID>
  python -m hx.cli demo           [--scenario ok|parser_error|crash]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from .config import load_config
from .util import Log, ensure_dir, now_iso, read_text, write_text_atomic


def _log(cfg, name: str = "harness") -> Log:
    ensure_dir(cfg.sub("logs"))
    return Log(Path(cfg.sub("logs")) / f"{name}-{now_iso().replace(':', '')}.log")


# --------------------------------------------------------------------- run
def cmd_run(args) -> int:
    from .orchestrator import Orchestrator
    cfg = load_config(args.config)
    if args.mock:
        cfg.data.setdefault("mock", {})["enabled"] = True
    log = _log(cfg)
    log.info("Harness startet", config=str(cfg.path), mock=bool(args.mock))
    orch = Orchestrator(cfg, log, mock=bool(args.mock))
    try:
        orch.run(paused=bool(getattr(args, "paused", False)))
    except KeyboardInterrupt:
        log.info("Abbruch per Strg+C")
        orch.state.set("PAUSED", "Strg+C")
    return 0


# ------------------------------------------------------------------ status
def cmd_status(args) -> int:
    from .orchestrator import Orchestrator
    cfg = load_config(args.config)
    log = Log(Path(cfg.sub("logs")) / "status.log", echo=False)
    orch = Orchestrator(cfg, log)
    print(orch.status_text())
    return 0


def cmd_budget(args) -> int:
    from .orchestrator import Orchestrator
    cfg = load_config(args.config)
    log = Log(Path(cfg.sub("logs")) / "status.log", echo=False)
    print(Orchestrator(cfg, log).budget_text())
    return 0


# ---------------------------------------------------------------- profiles
def cmd_profiles(args) -> int:
    from .profiles import PROFILES, ProfileError, load_profile
    cfg = load_config(args.config)
    for name in PROFILES:
        try:
            p = load_profile(cfg.root, name)
            print(f"{name:<18} {p.summary()}")
        except ProfileError as exc:
            print(f"{name:<18} FEHLER: {exc}")
    return 0


# ---------------------------------------------------------- probe-telegram
def cmd_probe(args) -> int:
    """Zeigt die Absender der letzten Nachrichten (nur IDs/Namen, keine Inhalte)."""
    from .telegram import Telegram
    from . import secrets
    cfg = load_config(args.config)
    token = secrets.load(cfg.secrets_dir, secrets.TELEGRAM)
    allow = [str(x) for x in (cfg.get("telegram", "allowlist_user_ids", []) or [])]
    tg = Telegram(token, allow, 0)
    me = tg.get_me()
    print(f"Bot: @{me.get('username')} (id {me.get('id')})")
    print(f"Allowlist: {allow if allow else '(leer - der Bot ignoriert alles)'}")
    senders = tg.probe_senders()
    if not senders:
        print("Keine offenen Nachrichten. Bitte dem Bot /start schreiben und erneut ausfuehren.")
        return 1
    print("Absender der letzten Nachrichten:")
    for s in senders:
        print(f"  user_id={s['user_id']}  username=@{s['username'] or '-'}  "
              f"name={s['first_name'] or '-'}  chat_id={s['chat_id']}  text={s['text']!r}")
    return 0


# ----------------------------------------------------------- allowlist-add
def cmd_allowlist(args) -> int:
    cfg = load_config(args.config)
    path = Path(cfg.path)
    text = path.read_text(encoding="utf-8")
    ids = sorted({str(x) for x in (cfg.get("telegram", "allowlist_user_ids", []) or [])} | {str(args.user_id)})
    new_line = "allowlist_user_ids = [" + ", ".join(f'"{i}"' for i in ids) + "]"
    lines = []
    replaced = False
    for ln in text.splitlines():
        if ln.strip().startswith("allowlist_user_ids"):
            lines.append(new_line)
            replaced = True
        else:
            lines.append(ln)
    if not replaced:
        print("Konnte die Zeile allowlist_user_ids nicht finden - nichts geaendert.", file=sys.stderr)
        return 2
    write_text_atomic(path, "\n".join(lines) + "\n")
    print(f"Allowlist jetzt: {ids}")
    print("Hinweis: laufender Harness liest die Konfiguration beim Start - neu starten.")
    return 0


# -------------------------------------------------------------------- demo
def cmd_demo(args) -> int:
    """Attrappen-Zyklus ohne API-Kosten (Testmodus, Abschnitt 'Tests')."""
    from . import protocol, queue
    from .orchestrator import Orchestrator
    cfg = load_config(args.config)
    cfg.data.setdefault("mock", {})["enabled"] = True
    cfg.data["mock"]["worker_mode"] = "crash" if args.scenario == "crash" else "ok"

    # Die Demo laeuft in einem EIGENEN Wurzelverzeichnis. Sonst schriebe sie in den
    # echten Zustand, den echten Eingang (inbox/) und die echten Laeufe - eine
    # Attrappen-Nachricht im echten Eingang wuerde beim naechsten Batch als echter
    # Auftrag zugestellt. Nur die Profile werden hineinkopiert (sie gehoeren zum
    # Werkzeug, nicht zu den Daten).
    real_root = cfg.root
    demo_root = real_root / "state" / f"_demo_{args.scenario}"
    if demo_root.exists():
        shutil.rmtree(demo_root, ignore_errors=True)
    (demo_root / "profiles").mkdir(parents=True, exist_ok=True)
    for f in sorted((real_root / "profiles").glob("*.json")):
        shutil.copy2(f, demo_root / "profiles" / f.name)
    cfg.data["paths"]["root"] = str(demo_root)

    log = _log(cfg, "demo")
    demo_state = Path(cfg.sub("state")) / f"run.demo-{args.scenario}.json"
    if demo_state.exists():
        demo_state.unlink()
    orch = Orchestrator(cfg, log, mock=True, state_file=demo_state)
    fails: list[str] = []

    def check(name: str, cond: bool, info: str = ""):
        print(f"  [{'OK ' if cond else 'FEHL'}] {name}" + (f" - {info}" if info else ""))
        if not cond:
            fails.append(name)

    print("== 0: Prompt-Übergabe über stdin (keine Kommandozeile) ==")
    from . import worker as wkmod
    from .profiles import load_profile
    langer = "X" * 45000
    cmd_demo_w, _mcpc = wkmod.build_command(cfg, load_profile(cfg.root, "none"),
                                           Path(cfg.root) / "runs" / "b999", "demo-session")
    maxarg = max(len(a) for a in cmd_demo_w)
    voll = wkmod.build_prompt(cfg, langer, "", None, "none")
    check("argv bleibt kurz", maxarg < 500, f"laengstes Argument {maxarg} Zeichen")
    check("kein Argument traegt den Prompt", not any(len(a) > 500 for a in cmd_demo_w))
    check("Auftrag ueber 40.000 Zeichen baubar", len(voll) > 40000, f"{len(voll)} Zeichen fuer stdin")
    check("Vorspann mit echten Umlauten", "Übernommener Stand" in wkmod.WORKER_PREAMBLE)

    print("== P0: Vorbedingungen ==")
    check("Ankerdatei lesbar", Path(cfg.anchor_file).is_file())
    check("Secrets (3)", all((Path(cfg.secrets_dir) / n).is_file()
                             for n in ("deepseek.key", "telegram.key", "claude-oauth.token")))
    check("Werkzeugprofile vorhanden", all((cfg.root / "profiles" / f"{p}.json").is_file()
                                           for p in ("none", "ghidra-read", "ghidra-standard", "ghidra-full")))

    print("== 1: Bootstrap-Review (Attrappe) ==")
    r1 = orch.do_review("bootstrap", orch.build_snapshot_text())
    p1 = r1.parsed
    check("Review geparst", bool(p1 and p1.blocks), p1.describe() if p1 else "kein Ergebnis")
    check("DS_TOOLS erkannt", bool(p1 and p1.profile), f"profil={p1.profile if p1 else '-'} "
                                                       f"programm={p1.program if p1 else '-'}")
    check("DS_INSTRUCTION vorhanden", bool(p1 and len(p1.instruction) > 40))

    print("== 2: Parser-Fehlerfall (Attrappe ohne DS_TOOLS) ==")
    broken = protocol.parse_review(__import__("hx.mock", fromlist=["x"]).mock_reviewer_text("parser_error"))
    check("Fehler wird erkannt", any("DS_TOOLS" in i for i in broken.issues), str(broken.issues))
    check("keine automatische Freigabe moeglich", broken.profile is None)

    print("== 3: Gate + Freigabe per Befehl ==")
    orch.state.set_gate("demo-gate", p1.summary, p1.instruction,
                        {"profile": p1.profile, "program": p1.program}, str(r1.raw_path))
    orch.say = lambda *a, **k: None  # keine Telegram-Ausgabe im Demo
    orch.handle_command("/status")
    orch.handle_command("/ds Zusatzauftrag aus dem Test")
    check("Queue-Datei angelegt", len(queue.pending(cfg.root, "ds")) >= 1)
    orch.handle_command("/approve")
    check("Gate freigegeben", orch.approved_gate == "demo-gate")

    print("== 4: Worker-Batch (Attrappe) ==")
    gate = orch.state.gate
    tools = gate["tools"]
    orch.state.next_batch()
    wres = orch.run_worker(gate["instruction"], tools["profile"], tools["program"], "")
    check("Worker-Ergebnis", wres.rc == 0 or args.scenario == "crash",
          f"rc={wres.rc}, {wres.describe()}")
    check("Snapshot geschrieben", bool(wres.snapshot_path and Path(wres.snapshot_path).is_file()))
    check("Antwortdatei geschrieben",
          (Path(wres.run_dir) / "antwort.md").is_file())
    check("Kosten gerechnet", wres.cost_usd > 0, f"${wres.cost_usd:.4f} (Gegenprobe ${wres.cost_naive_usd:.4f})")
    if args.scenario == "crash":
        check("Absturz erkannt", wres.killed_reason == "mock_crash", str(wres.killed_reason))
    else:
        check("Abschlussbericht enthaelt Marker", "<TOOL_REQUEST>" in wres.final_text)
    orch.state.clear_gate()

    print("== 5: Batch-Ende-Review (Attrappe) ==")
    r2 = orch.do_review("batch_end", orch.build_snapshot_text())
    check("Review 2 geparst", bool(r2.parsed and r2.parsed.blocks))
    check("Review-Zaehler", (orch.state.data.get("reviewer") or {}).get("reviews", 0) >= 1,
          str((orch.state.data.get("reviewer") or {}).get("reviews")))

    print("== 6: Absturz + Wiederaufnahme ==")
    orch.state.worker_started(999999, "(test)", "test")
    orch.recover()
    check("Recovery ohne lebenden Prozess", (orch.state.data.get("worker") is None))
    check("Zustand nach Recovery", orch.state.state in ("IDLE", "GATE_APPROVAL"), orch.state.state)

    print("== 7: Weitere Befehle ==")
    for cmd in ("/budget", "/queue", "/why", "/last", "/pause", "/resume", "/autonom on",
                "/autonom off", "/review", "/help"):
        ok = orch.handle_command(cmd)
        check(f"Befehl {cmd}", ok)
    check("Freitext ist kein Befehl", orch.handle_command("mach weiter") is False)
    check("Tagesbudget-Abfrage", orch.daily_budget_left() > 0,
          f"${orch.daily_budget_left():.2f} frei")
    orch.state.data["paused"] = False
    orch.state.save()

    print()
    if fails:
        print(f"DEMO: {len(fails)} FEHLER: " + ", ".join(fails))
        return 1
    print("DEMO: alle Pruefungen OK")
    return 0


ENV_PROOF_PROMPT = """ENV-NACHWEIS. Nur eine einzige Aktion, danach Antwort.

1. Führe GENAU EINEN PowerShell-Befehl aus:  (Get-ChildItem Env:).Name
2. Schreibe in deiner Antwort NUR die Namen, die mit einem dieser Präfixe beginnen:
   ANTHROPIC, CLAUDE, DEEPSEEK, TELEGRAM, GHIDRA_MCP, OPENAI, AZURE.
   Beginnt keiner damit, schreibe genau: KEINE
3. Gib KEINE Werte aus. Keine weiteren Werkzeugaufrufe, keine Erklärungen.
4. Letzte Zeile: ENV-PROOF-FERTIG
"""

ENV_NAMES_PATTERN = (r"\b(ANTHROPIC[A-Z0-9_]*|CLAUDE[A-Z0-9_]*|DEEPSEEK[A-Z0-9_]*|"
                     r"TELEGRAM[A-Z0-9_]*|GHIDRA_MCP[A-Z0-9_]*|OPENAI[A-Z0-9_]*|AZURE[A-Z0-9_]*)\b")

# Variablen, die Claude Code selbst für Unterskripte setzt - keine Zugangsdaten.
ENV_HARMLESS = {"CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_CHILD_SESSION",
                "CLAUDE_PID", "CLAUDE_EFFORT", "CLAUDE_JOB_DIR", "CLAUDE_ENV_FILE"}
VERBOTEN_PREFIX = ("ANTHROPIC", "DEEPSEEK", "TELEGRAM", "OPENAI", "AZURE")
VERBOTEN_EXACT = {"CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CONFIG_DIR"}
# Sichtbar, aber kein Geheimnis: Endpunkt und Modellname.
NICHT_GEHEIM = {"ANTHROPIC_BASE_URL", "ANTHROPIC_MODEL"}


def cmd_env_proof(args) -> int:
    """R16-Nachweis: sieht ein Unterskript des Workers Zugangsdaten? (echter Kleinlauf)"""
    import re as _re
    import uuid as _uuid
    from . import envs, secrets, streamjson
    from .proc import run_stream
    cfg = load_config(args.config)
    log = _log(cfg, "env-proof")
    sandbox = Path(str(cfg.get("paths", "sandbox", "g:/Harness/sandbox/workspace")))
    ensure_dir(sandbox)
    run_dir = ensure_dir(Path(cfg.root) / "runs" / "env-proof")

    alle = {}
    for name in (secrets.DEEPSEEK, secrets.TELEGRAM, secrets.CLAUDE_OAUTH):
        try:
            alle[name] = secrets.load(cfg.secrets_dir, name)
        except secrets.SecretError:
            pass
    token = alle.get(secrets.DEEPSEEK) or ""
    env = envs.worker_env(cfg, __import__("os").environ, token)
    bad = envs.precheck(env, "worker")

    cmd = [str(cfg.get("claude", "exe")), "-p",
           "--output-format", "stream-json", "--verbose",
           "--strict-mcp-config", "--permission-prompts", "none",
           "--model", str(cfg.get("claude", "model_worker")),
           "--max-turns", "8",
           "--tools", "PowerShell", "--allowedTools", "PowerShell",
           "--disallowedTools", "Bash", "Read", "Write", "Edit", "Glob", "Grep",
           "WebFetch", "WebSearch", "Task", "TodoWrite", "mcp__ghidra",
           "--session-id", str(_uuid.uuid4())]
    stream = run_dir / "stream.jsonl"
    stats = streamjson.StreamStats()
    log.info("R16: Testlauf startet", arbeitsverzeichnis=str(sandbox), argv_max=max(len(a) for a in cmd))
    run = run_stream(cmd, env, cwd=str(sandbox), out_path=stream, on_event=stats.feed, log=log,
                     hard_wall_s=300, stdin_text=ENV_PROOF_PROMPT,
                     stderr_path=run_dir / "stream.err.txt")

    raw = read_text(stream)
    text_teile = "\n".join(stats.tool_results + stats.texts)
    namen = sorted(set(_re.findall(ENV_NAMES_PATTERN, text_teile)))
    # Zugangsdaten = alles ANTHROPIC_*/DEEPSEEK*/TELEGRAM* + die zwei Token-Namen.
    # NICHT geheim: die zwei Routing-Angaben (Endpunkt + Modellname).
    verdaechtig = [n for n in namen
                   if (n.startswith(VERBOTEN_PREFIX) or n in VERBOTEN_EXACT)
                   and n not in NICHT_GEHEIM]
    nicht_geheim = [n for n in namen if n in NICHT_GEHEIM]
    harmlos = [n for n in namen if n not in verdaechtig and n not in nicht_geheim]
    wert_treffer = secrets.secret_names_in(raw, alle)

    t = stats.totals()
    erfolg = (not verdaechtig) and (not wert_treffer) and run.rc == 0
    report = [
        "# R16 — Umgebungs-Nachweis (Unterskript des Workers)",
        "",
        f"- Lauf: rc={run.rc}, Dauer={run.duration_s:.1f}s, Arbeitsverzeichnis={sandbox}",
        f"- Kommandozeile: max. Arglaenge {max(len(a) for a in cmd)} Zeichen "
        f"(Prompt {len(ENV_PROOF_PROMPT)} Zeichen ging ueber stdin)",
        f"- Modell laut Ausgabe: {stats.model}",
        f"- Anfragen: {t['requests']}, Kosten: ${stats.cost_usd():.4f}",
        f"- Umgebungs-Vorher-Pruefung des Worker-Prozesses: {'OK (keine verbotenen Namen)' if not bad else 'FEHLER: ' + str(bad)}",
        f"- Variablennamen im Unterskript: {', '.join(namen) if namen else 'KEINE'}",
        f"- davon harmlos (Claude-Code-eigene Marker): {', '.join(harmlos) if harmlos else 'keine'}",
        f"- davon NICHT geheim, aber sichtbar (Routing): {', '.join(nicht_geheim) if nicht_geheim else 'keine'}",
        f"- davon VERBOTEN (Zugangsdaten): {', '.join(verdaechtig) if verdaechtig else 'keine'}",
        f"- Secret-Werte im Rohmitschnitt gefunden: {', '.join(wert_treffer) if wert_treffer else 'keine'}",
        f"- Antworttext des Workers: {stats.final_text()[:400].strip() or '(leer)'}",
        "",
        f"**Urteil: {'BESTANDEN' if erfolg else 'FEHLGESCHLAGEN'}** "
        f"(kein Zugangstoken und kein Secret-Wert erreichbar)",
        "",
        "Hinweis: Werte werden nie ausgegeben, nur Namen und Treffer-Zaehlung.",
    ]
    p = write_text_atomic(run_dir / "report.md", "\n".join(report) + "\n")
    print("\n".join(report))
    print(f"\nBericht: {p}")
    return 0 if erfolg else 1


# --------------------------------------------------- lokale Steuerung (ohne Telegram)

def _runner_note(cfg) -> str:
    from . import control
    pid = control.read_pid(cfg)
    if control.runner_alive(cfg):
        return (f"Harness laeuft (PID {pid}) - Befehl wird im naechsten Schleifendurchlauf "
                f"ausgefuehrt (wenige Sekunden; im Pausenzustand bis ~30 s, weil dazwischen "
                f"die Telegram-Abfrage laeuft).")
    return ("KEIN Harness-Prozess erreichbar. Der Befehl bleibt als Datei liegen und wird "
            "beim naechsten Start ausgefuehrt.")


def _ctl_put(cfg, name: str, text: str = "") -> int:
    from . import control
    p = control.put(cfg, name, text)
    print(f"{name}: abgelegt ({p.name})")
    print(_runner_note(cfg))
    return 0


def cmd_pause(args) -> int:
    return _ctl_put(load_config(args.config), "pause")


def cmd_resume(args) -> int:
    return _ctl_put(load_config(args.config), "resume", "ok" if args.accept_dirty else "")


def cmd_stop(args) -> int:
    return _ctl_put(load_config(args.config), "stop")


def cmd_approve(args) -> int:
    return _ctl_put(load_config(args.config), "approve", args.text or "")


def cmd_send(args) -> int:
    """Nachricht an Worker (ds) oder Reviewer (claude) in die Queue legen."""
    from . import queue
    cfg = load_config(args.config)
    target = args.target
    if target not in ("ds", "claude"):
        print("Ziel muss 'ds' oder 'claude' sein.", file=sys.stderr)
        return 2
    text = args.text or ""
    if args.file:
        p = Path(args.file)
        if not p.is_file():
            print(f"Datei nicht gefunden: {p}", file=sys.stderr)
            return 2
        text = read_text(p)
        if not text.strip():
            print(f"Datei ist leer: {p}", file=sys.stderr)
            return 2
    if not text.strip():
        print("Kein Text: 'send ds \"...\"' oder 'send ds --file <pfad.md>'", file=sys.stderr)
        return 2
    item = queue.enqueue(cfg.root, target, text, "lokal", None)
    print(f"{target}: {item.name} ({len(text)} Zeichen)")
    print("Zustellung: ds beim naechsten Batch-Uebergang, claude beim naechsten Review.")
    print(_runner_note(cfg))
    return 0


def cmd_run_instruction(args) -> int:
    """Eigene Instruktion als naechsten Batch (am Reviewer vorbei)."""
    from . import control
    cfg = load_config(args.config)
    text = args.text or ""
    if args.file:
        p = Path(args.file)
        if not p.is_file():
            print(f"Datei nicht gefunden: {p}", file=sys.stderr)
            return 2
        text = read_text(p)
    if not text.strip():
        print("Kein Text: --file <pfad.md> oder --text \"...\"", file=sys.stderr)
        return 2
    profile = args.profile or "ghidra-read"
    program = args.program
    if profile == "none" and not args.program:
        program = None
    elif not program:
        program = str(cfg.get("ghidra", "program_default"))
    p = control.put_instruction(cfg, text, profile, program, str(args.file or "direkt"))
    print(f"Instruktion abgelegt ({p.name}, {len(text)} Zeichen).")
    print(f"Profil {profile}, Programm {program or '-'} - Quelle: vom Nutzer (ohne Review).")
    print(_runner_note(cfg))
    return 0


def cmd_watch(args) -> int:
    # rein lesend: keine Sperren, keine Schreibvorgaenge
    """Live-Ansicht (rein lesend)."""
    from .watch import Watcher
    cfg = load_config(args.config)
    log = Log(Path(cfg.sub("logs")) / "watch.log", echo=False)
    return Watcher(cfg, log, batch=args.batch, run=(args.run or None)).run()


def cmd_show_prompts(args) -> int:
    """Schreibt die beiden Vorlagen (Review-Prompt, Worker-Vorspann) als Dateien."""
    from . import reviewer as rv, worker as wk
    from .orchestrator import Orchestrator
    cfg = load_config(args.config)
    log = Log(Path(cfg.sub("logs")) / "status.log", echo=False)
    orch = Orchestrator(cfg, log)
    orch.state.data["batch"] = int(getattr(args, "batch", 1) or 0)   # nur fuer die Vorschau
    out = ensure_dir(Path(cfg.root) / "preview")
    ctx = orch.review_context(
        orch.build_snapshot_text(),
        reviewer_note="NACHRICHTEN AUS DER QUEUE (vom Nutzer, nicht verhandelbar):\n- [Beispiel] Bitte auf X achten")
    review_prompt = rv.build_prompt(cfg, "batch_end", ctx)
    worker_prompt = wk.build_prompt(
        cfg, "<DS_INSTRUCTION aus dem Review - hier wortgleich eingesetzt>",
        "\nNACHRICHTEN AUS DER QUEUE (vom Nutzer, nicht verhandelbar):\n- [Beispiel] Zusatzauftrag",
        "/830d01.27p.main.bin", "ghidra-read")
    p1 = write_text_atomic(out / "reviewer-batch-end.md", review_prompt + "\n")
    p2 = write_text_atomic(out / "worker-batch.md", worker_prompt)
    print(f"{p1}  ({len(review_prompt)} Zeichen)")
    print(f"{p2}  ({len(worker_prompt)} Zeichen)")
    print(f"Systemprompt des Reviewers: {Path(cfg.prompts_dir) / 'reviewer.md'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="hx", description="Silent-Scope-Harness (MVP)")
    p.add_argument("--config", default=None, help="Pfad zur harness.toml")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="Hauptschleife starten")
    r.add_argument("--mock", action="store_true", help="Attrappen statt echter API-Aufrufe")
    r.add_argument("--paused", action="store_true", help="im Zustand PAUSIERT starten (Bot laeuft)")

    sub.add_parser("status")
    sub.add_parser("budget")
    sub.add_parser("profiles")
    sub.add_parser("probe-telegram")

    a = sub.add_parser("allowlist-add")
    a.add_argument("user_id")

    d = sub.add_parser("demo", help="Attrappen-Zyklus (ohne API-Kosten)")
    d.add_argument("--scenario", default="ok", choices=["ok", "parser_error", "crash"])
    sub.add_parser("show-prompts", help="Review-Prompt und Worker-Vorspann als Dateien schreiben")
    sub.add_parser("env-proof", help="R16: Umgebungs-Nachweis mit einem echten Kleinlauf")

    # --- lokale Steuerung (gleichwertig zu den Telegram-Befehlen) ----------------
    sub.add_parser("pause", help="pausieren (laeuft ein Batch, laeuft er zu Ende)")
    rr = sub.add_parser("resume", help="fortsetzen")
    rr.add_argument("--accept-dirty", action="store_true",
                    help="unsauberen Arbeitsbaum ausdruecklich akzeptieren")
    sub.add_parser("stop", help="laufenden Batch abbrechen (WIP wird gesichert)")
    ap = sub.add_parser("approve", help="wartenden Batch freigeben")
    ap.add_argument("--text", default="", help="optionaler Text, geht als ds-Nachricht mit")
    sd = sub.add_parser("send", help="Nachricht an ds (Worker) oder claude (Reviewer)")
    sd.add_argument("target", choices=["ds", "claude"])
    sd.add_argument("text", nargs="?", default="")
    sd.add_argument("--file", help="langer Text aus einer Datei")
    ri = sub.add_parser("run-instruction", help="eigene Instruktion als naechsten Batch")
    ri.add_argument("--file", help="Datei mit der Instruktion")
    ri.add_argument("--text", default="", help="Instruktion direkt")
    ri.add_argument("--profile", default="", help="none | ghidra-read | ghidra-standard | ghidra-full")
    ri.add_argument("--program", default="", help="Ghidra-Projektpfad")
    wv = sub.add_parser("watch", help="Live-Ansicht des laufenden Batches (rein lesend)")
    wv.add_argument("--batch", type=int, default=0, help="abgeschlossenen Batch nachspielen")
    wv.add_argument("--run", default="", help="benannten Lauf nachspielen (z. B. env-proof)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return {
        "run": cmd_run, "status": cmd_status, "budget": cmd_budget, "profiles": cmd_profiles,
        "probe-telegram": cmd_probe, "allowlist-add": cmd_allowlist, "demo": cmd_demo,
        "show-prompts": cmd_show_prompts,
        "env-proof": cmd_env_proof,
        "pause": cmd_pause, "resume": cmd_resume, "stop": cmd_stop,
        "approve": cmd_approve, "send": cmd_send,
        "run-instruction": cmd_run_instruction, "watch": cmd_watch,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
