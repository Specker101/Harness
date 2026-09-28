"""Kommandozeile des Harness.

  python -m hx.cli run            [--mock] [--config PFAD]
  python -m hx.cli status
  python -m hx.cli budget
  python -m hx.cli bilanz         [--n <Abstand in Batches>]
  python -m hx.cli thinking       [--n N] [--batch B] [--voll]
  python -m hx.cli fragen
  python -m hx.cli profiles
  python -m hx.cli probe-telegram
  python -m hx.cli allowlist-add <USER_ID>
  python -m hx.cli demo           [--scenario ok|parser_error|crash]
  python -m hx.cli watch          [--batch N | --run <name>] [--no-color] [--once]
  python -m hx.cli pause|resume|stop|approve|number <N>
  python -m hx.cli send ds|claude "<Text>" [--file <pfad>]
  python -m hx.cli ask "<Frage>" [--file <pfad>]
  python -m hx.cli run-instruction --file <pfad> [--profile none]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from .config import load_config
from .util import Log, ensure_dir, now_iso, read_json, read_text, write_text_atomic


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
    except Exception as exc:
        # Der Traceback steht bereits im Log und in logs/crash-*.txt (Orchestrator.run).
        # Hier nur eine kurze Meldung auf stderr + Exit-Code, damit start.ps1 es merkt.
        bericht = orch.letzter_crash_bericht()
        print(f"ABSTURZ: {type(exc).__name__}: {exc}", file=sys.stderr)
        if bericht:
            print(f"Bericht: {bericht}", file=sys.stderr)
        return 3
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


def _druck(text: str) -> None:
    """Ausgabe, die auch in einer Konsolen-Codepage nicht abbricht (R13r/R13s).

    R13r: Denkbloecke enthalten Pfeile/Umlaute (`→`); `print` starb daran mit
    `UnicodeEncodeError`. Telegram ist davon nicht betroffen (UTF-8), die Konsole schon:
    nicht darstellbare Zeichen werden dort durch `?` ersetzt.
    """
    try:
        print(text)
    except UnicodeEncodeError:
        kod = sys.stdout.encoding or "utf-8"
        print(text.encode(kod, "replace").decode(kod, "replace"))


def cmd_bilanz(args) -> int:
    """Bilanz auf der Konsole (R13q) - dieselbe Ausgabe wie Telegram `/bilanz [N]`.

    Rein lesend: kleiner Schnappschuss, Belegdateien, `runs/b*/result.json`,
    `logs/rate-limit.json`. Kein Ghidra, kein Netz, kein Mitschnitt.
    """
    from . import bilanz as bilanzmod
    cfg = load_config(args.config)
    _druck(bilanzmod.bericht(cfg, n=max(1, int(getattr(args, "n", 1) or 1))))
    return 0


def cmd_fragen(args) -> int:
    """Offene Fragen an den Nutzer auf der Konsole (R13s/R13y) - wie Telegram `/fragen`.

    Jede Frage traegt eine Kennung (`A5`, `R209-1`, `M208-1`); geantwortet wird per
    `/claude <Kennung> <Text>` beziehungsweise `send claude "<Kennung> <Text>"`.
    """
    from . import stand as standmod
    cfg = load_config(args.config)
    gate = (read_json(Path(cfg.sub("state")) / "run.json", {}) or {}).get("gate")
    _druck(standmod.fragen_text(cfg, gate=gate))
    return 0


def cmd_meta(args) -> int:
    """Aussensicht (Meta-Review) starten - wie Telegram `/meta` (R13w).

    Laeuft der Harness, wird NUR der Steuerbefehl `state/ctl/meta` abgelegt: nur der
    Harness darf den Zustand schreiben (und nur er weiss, ob gerade ein Worker laeuft -
    dann wird die Aussensicht vorgemerkt und nach dem Batch-Ende vor dem Review gefahren).
    Ohne laufenden Harness faehrt die CLI den Lauf direkt.
    """
    from . import control, state as st_mod
    from .orchestrator import Orchestrator
    from .util import Log as _Log
    cfg = load_config(args.config)
    pid = control.read_pid(cfg)
    if pid:
        control.put(cfg, "meta", "cli")
        print(f"Aussensicht vorgemerkt (Harness laeuft, PID {pid})."
              "\nLaeuft ein Batch, startet sie direkt danach - noch vor dem Review.")
        return 0
    log = _Log(Path(cfg.sub("logs")) / "meta.log", echo=False)
    state = st_mod.State(Path(cfg.sub("state")) / "run.json")
    orch = Orchestrator.__new__(Orchestrator)          # nur fuer den Zustand gebraucht
    orch.cfg, orch.state, orch.log = cfg, state, log
    orch.qroot = Path(cfg.root)
    gesagt: list[str] = []
    orch.say = lambda *t, **k: (gesagt.append(" ".join(str(x) for x in t)),
                                _druck(" ".join(str(x) for x in t)))
    orch.phase = lambda *a, **k: None
    orch.mock = bool(getattr(args, "mock", False))
    grund = str(getattr(args, "grund", "") or "Befehl 'hx.cli meta'")
    orch._do_aussensicht(grund)
    return 0


def cmd_thinking(args) -> int:
    """Denkbloecke des Workers auf der Konsole (R13r) - wie Telegram `/thinking [N] [voll]`.

    Ohne `--batch` wird der neueste Batch genommen (`denken.neuester_mitschnitt`, nur
    echte `b<N>`-Ordner - `runs/` enthaelt auch `env-proof` und `ghidra-smoke`).
    """
    from . import denken as denkenmod
    cfg = load_config(args.config)
    pfad = (denkenmod.mitschnitt_fuer_batch(cfg, args.batch) if args.batch
            else denkenmod.neuester_mitschnitt(cfg))
    if pfad is None:
        print("Kein Mitschnitt gefunden (kein passender runs/b<N>/stream.jsonl).",
              file=sys.stderr)
        return 2
    erg = denkenmod.denkbloecke(pfad, n=max(1, int(args.n or denkenmod.STANDARD_N)),
                                grenze_zeichen=None if args.voll
                                else denkenmod.GRENZE_ZEICHEN)
    _druck(denkenmod.beschreibe(erg))
    return 0 if not erg.get("fehler") else 1


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

    print("== 1b: Batch-Nummer kommt aus dem Anker ==")
    aus_anker = orch.expected_batch()
    check("Anker-Nummer gefunden", aus_anker > 0, orch.batch_number_line())
    prompt = __import__("hx.reviewer", fromlist=["x"]).build_prompt(
        cfg, "bootstrap", orch.review_context(orch.build_snapshot_text()))
    check("Review-Prompt nennt die Anker-Nummer",
          f"Naechster Batch laut Anker: {aus_anker}" in prompt)
    check("kein interner Zaehler im Prompt", "der naechste Batch ist" not in prompt)
    rdir = Path(cfg.sub("runs")) / f"b{aus_anker:03d}"
    check("Review liegt nach echter Nummer", (rdir / "review-pre.md").is_file(), str(rdir.name))
    check("Reviewer-Mitschnitt liegt daneben", (rdir / "reviewer.jsonl").is_file())
    falsch = protocol.parse_review("<TELEGRAM_SUMMARY>x</TELEGRAM_SUMMARY>\n"
                                   "<DS_TOOLS>profile: none</DS_TOOLS>\n"
                                   "<DS_INSTRUCTION>Batch 1 - falsche Nummer</DS_INSTRUCTION>")
    check("Parser liest die Nummer aus der Instruktion", falsch.batch == 1)
    st_num = orch.gate_from_review(falsch, "(demo)")
    check("Abweichung haelt an (kein Start)", st_num == "number_mismatch", st_num)
    check("Harness ist dabei pausiert", bool(orch.state.data.get("paused")))
    orch._do_number(str(aus_anker))
    check("Nummer per /number korrigiert",
          ((orch.state.gate or {}).get("tools") or {}).get("batch") == aus_anker)
    orch.discard_gate("Demo: Nummernpruefung beendet")
    orch.state.data["paused"] = False
    orch.state.save()

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
    # Nummer aus dem Anker uebernehmen (kein interner Zaehler) - wie in der Schleife.
    orch.state.data["batch"] = orch.expected_batch()
    orch.state.data["last_batch_number"] = orch.state.data["batch"]
    orch.state.save()
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

    print("== 8: Profil none ohne Ghidra ==")
    from .profiles import load_profile as _lp
    none_p = _lp(cfg.root, "none")
    check("Profil none ohne MCP", none_p.mcp is False)
    check("Profil none schreibt Ghidra nicht", none_p.writes_ghidra is False)
    p_none = protocol.parse_review(
        "<TELEGRAM_SUMMARY>nur Doku</TELEGRAM_SUMMARY>\n"
        "<DS_TOOLS>profile: none\nprogram: /830d01.27p.main.bin</DS_TOOLS>\n"
        f"<DS_INSTRUCTION>Batch {orch.expected_batch()} - nur Doku</DS_INSTRUCTION>")
    orch.gate_from_review(p_none, "(demo)")
    check("Programm bei Profil none verworfen",
          ((orch.state.gate or {}).get("tools") or {}).get("program") is None)
    orch.discard_gate("Demo beendet")

    print("== 9: Rotation mit Uebergabe (Attrappe) ==")
    orch.state.data["reviewer"] = {"session_id": "alte-demo-session", "reviews": 10}
    orch.state.save()
    r3 = orch.do_review("batch_end", orch.build_snapshot_text())
    check("Review nach Rotation", bool(r3.parsed and r3.parsed.blocks))
    check("Rotation startet eine neue Session",
          (orch.state.data["reviewer"] or {}).get("session_id") != "alte-demo-session",
          str((orch.state.data["reviewer"] or {}).get("session_id")))
    check("Uebergabedatei geschrieben",
          (Path(cfg.sub("sessions")) / "vorherige-session.md").is_file())
    p_rot = (Path(cfg.sub("sessions")) / "vorherige-session.md")
    check("Uebergabe steht in der Datei", "UEBERGABE" in p_rot.read_text(encoding="utf-8").upper()
          or "Attrappe" in p_rot.read_text(encoding="utf-8"))

    print("== 10: Ghidra nach dem Batch speichern (Attrappe) ==")
    r_none = wkmod.save_ghidra_after_batch(cfg, orch.log, orch.state, "none", mock=True)
    check("Profil none: kein Speichern noetig", not r_none["needed"], r_none["hinweis"])
    r_schreib = wkmod.save_ghidra_after_batch(cfg, orch.log, orch.state, "ghidra-standard",
                                              mock=True)
    check("Schreibprofil: Speichern ausgefuehrt", r_schreib["needed"] and r_schreib["ok"],
          r_schreib["hinweis"])
    check("Messdatenzeile ja",
          orch.ghidra_save_line({"ghidra_save": r_schreib}).startswith("ja"))
    check("Messdatenzeile NEIN",
          orch.ghidra_save_line({"ghidra_save": {"needed": True, "ok": False,
                                                  "hinweis": "Fehler"}}).startswith("NEIN"))
    orch.state.data["ghidra_pending"] = True
    orch.state.data["last_profile"] = "ghidra-standard"
    check("Merker wird bei Stopp/Ende abgearbeitet",
          orch.save_ghidra_if_pending("Demo-Stopp") and not orch.state.data.get("ghidra_pending"))

    print("== 11: Rotation + Uebergabe + gescheiterter Review (echter Schleifendurchlauf) ==")
    # Genau der Fall vom 2026-09-25: alte Session, Wechsel erzwungen, Uebergabe liegt
    # vor, der erste Review liefert keinen gueltigen Protokollblock.
    orch.state.data["batch"] = 159
    orch.state.data["last_batch_number"] = 159
    orch.state.data["reviewer"] = {"session_id": "alte-demo-session", "reviews": 2,
                                   "force_rotate": True,
                                   "pending_handover": {"from_session": "alte-demo-session",
                                                        "text": "UEBERGABE-MARKE (Demo)",
                                                        "at": now_iso()}}
    orch.state.data["paused"] = True
    orch.state.clear_gate()
    orch.state.save()
    rd159 = ensure_dir(Path(cfg.sub("runs")) / "b159")
    write_text_atomic(rd159 / "antwort.md", "## 1) Uebernommener Stand\n(Demo) B159 fertig.\n")
    write_text_atomic(rd159 / "result.json", '{\n "batch": 159, "profile": "none",\n'
                                             ' "duration_s": 377.257, "duration_quelle": "cli",\n'
                                             ' "duration_cli_s": 377.257,\n'
                                             ' "stats": {"requests": 72}, "cost_usd": 0.068\n}\n')

    def ein_durchlauf(mode: str, bis_workerstart: bool = False) -> tuple[list[str], Path, bool]:
        """Einen Schleifendurchlauf fahren und danach anhalten (Demo-Hilfe).

        `bis_workerstart=True` laeuft ueber die Freigabe hinaus: der Worker wird nur
        GEMERKT, nicht gestartet (Attrappe, keine Kosten). Telegram wird fuer die Dauer
        der Attrappe abgeschaltet, damit der laufende Harness seine Nachrichten behaelt.
        """
        gesagt: list[str] = []
        gestartet = {"worker": False}
        orch.say = lambda t: gesagt.append(str(t))
        orch.mock_reviewer_mode = mode
        orch.state.data["paused"] = False
        orch.state.save()
        echt_review = orch.do_review
        echt_peak = orch.peak_gate
        echt_worker = orch.run_worker
        echt_tg = orch.tg
        echt_poll = orch.poll
        echt_pre = orch.git_preflight
        echt_chk = orch.git.checkpoint
        echt_push = orch.git_push
        zaehler = {"poll": 0}

        def einmal(*a, **k):
            res = echt_review(*a, **k)
            if not bis_workerstart:
                orch.quit = True
            return res

        def worker_merker(*a, **k):
            gestartet["worker"] = True
            orch.quit = True
            return None

        def poll_ende(*a, **k):
            zaehler["poll"] += 1
            if zaehler["poll"] > 3:
                orch.quit = True

        def push_merker(*a, **k):
            return True, "Attrappe: kein Push"

        orch.do_review = einmal
        orch.peak_gate = lambda: (True, "")
        orch.tg = None
        orch.poll = poll_ende
        if bis_workerstart:
            orch.run_worker = worker_merker
            orch.git_preflight = lambda: (True, "")
            orch.git.checkpoint = lambda n: f"harness/b{int(n)}-start"
            orch.git_push = push_merker
        try:
            orch._loop()
        finally:
            orch.do_review = echt_review
            orch.peak_gate = echt_peak
            orch.run_worker = echt_worker
            orch.tg = echt_tg
            orch.poll = echt_poll
            orch.git_preflight = echt_pre
            orch.git.checkpoint = echt_chk
            orch.git_push = echt_push
            orch.quit = False
        return gesagt, Path(cfg.sub("runs")) / f"b{orch.expected_batch():03d}", gestartet["worker"]

    p_a = queue.enqueue(cfg.root, "claude", "Demo-Nachricht A: Audio-Frage klaeren.", "demo")
    gesagt, ziel, _ = ein_durchlauf("ok_zweiter_versuch")
    check("Review landete im Anker-Verzeichnis (nicht b159)",
          ziel.name == f"b{orch.expected_batch():03d}", ziel.name)
    check("1. Versuch als Beleg verworfen",
          len(list(ziel.glob("review-verworfen-*-v1.md"))) == 1)
    check("2. Versuch ist das Review", (ziel / "review.md").is_file())
    check("Gate traegt den Anker-Nachfolger",
          (orch.state.gate or {}).get("tools", {}).get("batch") == orch.expected_batch(),
          str((orch.state.gate or {}).get("tools")))
    check("Belege bleiben in runs/b159", (rd159 / "antwort.md").is_file())
    check("Nachricht A bleibt nach dem Review liegen (R13u)",
          p_a.is_file() and (Path(cfg.root) / "inbox" / "claude" / p_a.name).is_file())
    check("Nachricht A (noch) nicht als zugestellt verbucht",
          queue.pending(cfg.root, "claude")[0].id not in (orch.state.data.get("delivered") or []))
    check("Nachricht A reist im Gate mit",
          (orch.state.gate or {}).get("claude_queue_ids") == [p_a.stem])
    check("Wiederholung wurde angekuendigt",
          any("EINMAL" in s.upper() or "WIEDERHOL" in s.upper() for s in gesagt))
    neuer_stand = orch.state.data["reviewer"]
    check("Review laeuft in NEUER Session", neuer_stand["session_id"] != "alte-demo-session",
          neuer_stand["session_id"])
    check("Uebergabe wurde wiederverwendet (kein zweiter Aufruf)",
          "Uebergabe wiederverwendet" in read_text(str(orch.log.path)))

    # Zweiter Durchlauf: Review scheitert zweimal -> Pause, kein Gate, Queue bleibt liegen.
    orch.discard_gate("Demo: Gate verwerfen")
    check("verworfenes Gate frisst die Nachricht NICHT (R13u)", p_a.is_file())
    queue.archive(cfg.root, [p_a.stem], "claude")     # A wegraeumen, sonst ist B nicht [0]
    p_b = queue.enqueue(cfg.root, "claude", "Demo-Nachricht B: bleibt liegen.", "demo")
    gesagt2, _, _ = ein_durchlauf("parser_error")
    check("kein Gate nach zwei Fehlversuchen", orch.state.gate is None)
    check("Zustand PAUSED", orch.state.state == "PAUSED", orch.state.state)
    check("Nachricht B bleibt in inbox/claude", p_b.is_file())
    check("Nachricht B nicht als zugestellt verbucht",
          queue.pending(cfg.root, "claude")[0].id not in (orch.state.data.get("delivered") or []))
    check("Rohtexte als Belege (v1 und v2)",
          len(list(ziel.glob("review-verworfen-*-v1.md"))) >= 1
          and len(list(ziel.glob("review-verworfen-*-v2.md"))) >= 1)
    check("Protokoll in logs/",
          bool(list((Path(cfg.sub("logs"))).glob("review-verworfen-*.json"))))
    check("Meldung nennt den Grund", any("PROTOKOLLBLOCK" in s.upper() for s in gesagt2))
    queue.archive(cfg.root, [queue.pending(cfg.root, "claude")[0].id], "claude")

    print("== 12: Entscheidungs-Bremse im Dauerbetrieb (A) ==")
    orch.discard_gate("Demo: Gate verwerfen")
    orch.state.data["autonomous"] = True
    orch.state.save()
    gesagt3, _, start3 = ein_durchlauf("entscheidung", bis_workerstart=True)
    check("autonom + ENTSCHEIDUNG: kein Workerstart", start3 is False)
    check("Gate bleibt offen",
          orch.state.gate is not None and orch.state.state == "GATE_APPROVAL",
          f"{orch.state.state} / {orch.state.data.get('note')}")
    check("Meldung 'Wartet auf deine Entscheidung'",
          any("Wartet auf deine Entscheidung" in s for s in gesagt3))
    check("Kopfzeile 'WARTET AUF DEINE ENTSCHEIDUNG'",
          any("WARTET AUF DEINE ENTSCHEIDUNG" in s for s in gesagt3))
    check("Status zeigt die offene Entscheidung",
          "Offene Entscheidung:" in orch.status_text())
    orch.discard_gate("Demo: Gate verwerfen")
    gesagt4, _, start4 = ein_durchlauf("offene_frage", bis_workerstart=True)
    check("autonom + OFFENE FRAGE: Worker startet", start4 is True)
    check("offene Frage bremst nicht (Gate wird verbraucht)", orch.state.gate is None)
    check("Status nennt die offene Frage nicht als Bremse",
          "Offene Frage:" not in orch.status_text()
          or "braucht eine ENTSCHEIDUNG" not in orch.status_text())
    orch.discard_gate("Demo: Gate verwerfen")
    orch.state.data["autonomous"] = False
    orch.state.save()

    print()
    if fails:
        print(f"DEMO: {len(fails)} FEHLER: " + ", ".join(fails))
        return 1
    print("DEMO: alle Pruefungen OK")
    return 0


ENV_PROOF_PROMPT = """ENV-NACHWEIS. Drei Schritte, dann die Antwort.

1. Führe GENAU EINEN PowerShell-Befehl aus:  (Get-ChildItem Env:).Name
   Schreibe in deiner Antwort NUR die Namen, die mit einem dieser Präfixe beginnen:
   ANTHROPIC, CLAUDE, DEEPSEEK, TELEGRAM, GHIDRA_MCP, OPENAI, AZURE.
   Beginnt keiner damit, schreibe genau: KEINE
   Von diesen Variablen gibst du KEINEN Wert aus.

2. Führe GENAU EINEN weiteren PowerShell-Befehl aus und schreibe die Ausgabe WÖRTLICH:
   g++ --version; python --version; git --version
   Diese drei Zeilen sind ERWÜNSCHT und ausdrücklich erlaubt: es sind
   Werkzeug-Versionen und keine Zugangsdaten.

3. Keine weiteren Werkzeugaufrufe, keine Erklärungen, keine Dateien anlegen.
   Letzte Zeile: ENV-PROOF-FERTIG
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
    # --- Werkzeugkette (R11-3): lokal mit DERSELBEN Umgebung messen und mit der
    # --- Antwort des Workers vergleichen.
    lokal = dict(envs.toolchain(env))
    import re as _re2

    def _versions(text: str) -> dict:
        out: dict[str, str] = {}
        for line in text.splitlines():
            l = line.strip()
            for key, pref in (("g++", "g++"), ("python", "python "), ("git", "git version")):
                if l.lower().startswith(pref) and key not in out:
                    out[key] = l[:120]
        return out

    def _zahl(text: str) -> str:
        m = _re2.search(r"(\d+\.\d+\.\d+|\d+\.\d+)", text or "")
        return m.group(1) if m else "?"

    gesehen = _versions(text_teile)
    kette_zeilen = []
    kette_ok = True
    for name in ("g++", "python", "git"):
        lok = lokal.get(name, "(nicht messbar)")
        sieh = gesehen.get(name, "(nicht in der Antwort)")
        gleich = name != "g++" or (_zahl(lok) == _zahl(sieh) != "?")
        if name == "g++":
            kette_ok = bool(gleich)
        kette_zeilen.append(f"  - {name}: Harness={lok} | Worker={sieh} | "
                            f"{'gleich' if gleich else 'ABWEICHUNG'}")
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
        "",
        "## Werkzeugkette (R11-3)",
        f"- PATH-Anfang: {'; '.join(envs.path_of(env).split(';')[:4])}",
        *kette_zeilen,
        f"- Urteil Werkzeugkette: {'STIMMT mit der Umgebung des Harness' if kette_ok else 'WEICHT AB'}",
        "",
        f"- Antworttext des Workers: {stats.final_text()[:600].strip() or '(leer)'}",
        "",
        f"**Urteil R16: {'BESTANDEN' if erfolg else 'FEHLGESCHLAGEN'}** "
        f"(kein Zugangstoken und kein Secret-Wert erreichbar)",
        f"**Urteil Werkzeugkette: {'BESTANDEN' if kette_ok else 'FEHLGESCHLAGEN'}**",
        "",
        "Hinweis: Werte der Zugangsdaten werden nie ausgegeben, nur Namen und Treffer-Zaehlung.",
    ]
    p = write_text_atomic(run_dir / "report.md", "\n".join(report) + "\n")
    print("\n".join(report))
    print(f"\nBericht: {p}")
    return 0 if erfolg else 1


def cmd_rebuild(args) -> int:
    """Einen Lauf aus dem vorhandenen Mitschnitt nachrechnen (R11-2).

    Fuer den Fall, dass der Harness nach dem Worker-Ende stehen bleibt: die Zahlen
    kommen aus `runs/b<N>/stream.jsonl`, nichts wird geschaetzt.
    """
    from datetime import datetime, timezone
    from . import state as st, worker as wk
    cfg = load_config(args.config)
    log = _log(cfg, "rebuild")
    state = st.State(Path(cfg.sub("state")) / "run.json")
    n = int(args.batch or state.data.get("last_batch_number") or state.batch or 0)
    if n <= 0:
        print("Keine Batch-Nummer bekannt - 'rebuild <N>' angeben.", file=sys.stderr)
        return 2
    res = wk.rebuild_from_stream(cfg, log, state, n)
    heute = datetime.now(timezone.utc).date().isoformat()
    marker = Path(res.run_dir) / "spend-recorded.txt"
    if marker.is_file():
        gesamt = state.spent_today(heute)
        print("Kosten waren bereits verbucht - nichts doppelt gezaehlt.")
    else:
        gesamt = state.add_spend(heute, res.cost_usd)
        write_text_atomic(marker, f"{res.cost_usd:.6f}\n{heute}\n")
    t = res.stats or {}
    print(f"Batch {n}: Profil {res.profile}, rc={res.rc} ({res.killed_reason})")
    print(f"  Anfragen            : {t.get('requests')}")
    print(f"  Eingabe ohne Cache  : {t.get('input_miss')}")
    print(f"  Cache-Treffer       : {t.get('cache_read')}")
    print(f"  Ausgabe             : {t.get('output')}")
    print(f"  Kosten              : ${res.cost_usd:.4f} | heute jetzt ${gesamt:.4f}")
    print(f"  Gegenprobe (result) : {t.get('usage_check')}")
    print(f"  Modell laut Ausgabe : {res.model_seen} (ok={res.model_ok})")
    print(f"  Antwort             : {Path(res.run_dir) / 'antwort.md'}")
    print(f"  Snapshot            : {res.snapshot_path}")
    return 0


# ------------------------------------------------- Ghidra-Rauchtest (R12, nicht als Batch)
GHIDRA_MAIN = "/830d01.27p.main.bin"
GHIDRA_BE = "/830d01.27p.be.bin"
GHIDRA_ADDR = 0x80054AE4          # Rohwort-Sollwert 48008171 (bl 0x8005CC54)
GHIDRA_FUN = 0x8005CC54

GHIDRA_READ_PROMPT = """GHIDRA-RAUCHTEST (nur LESEN). Das Arbeitsverzeichnis ist ein Sandkasten.

REGELN: Lege KEINE Dateien an, aendere NICHTS in Ghidra, committe nichts, keine Erklaerungen.

1. get_current_program_info -> melde Name und Basisadresse.
2. read_memory an 0x80054AE4, Laenge 4 -> melde das Rohwort als Hex.
   Sollwert aus den Batch-Dokumenten: 48008171 (das ist `bl 0x8005CC54`).
3. decompile_function an 0x8005CC54 -> gib die ersten 12 Zeilen wieder.

Antworte am Ende GENAU in diesen fuenf Zeilen:
PROGRAMM: <name>
ROHWORT: <hex>
SOLL-ERFUELLT: ja|nein
DEKOMPILAT: <erste Zeile des Dekompilats>
ZIEL-FUNKTION: 0x8005CC54
"""

GHIDRA_WRITE_PROMPT = """GHIDRA-RAUCHTEST (SCHREIBEN, Aktion {aktion}). Das Arbeitsverzeichnis ist ein Sandkasten.

REGELN: Fasse NUR die Adresse {addr} an. Keine anderen Adressen, keine Dateien, kein Git.
SPEICHERN IST NICHT DEINE AUFGABE: `save_program` ist absichtlich gesperrt - das Speichern
macht der Harness. Versuche es nicht.

1. get_current_program_info -> melde Name und Basisadresse.
2. get_comment an {addr} -> melde has_comment und den Text.
3. {schritt}

Antworte am Ende GENAU in diesen vier Zeilen:
PROGRAMM: <name>
VORHER: <has_comment vor Schritt 3>
NACHHER: <has_comment nach Schritt 3>
TEXT: <Kommentartext nach Schritt 3, oder LEER>
"""


def _smoke_worker(cfg, log, profile_name: str, prompt: str, run_dir: Path, cwd: Path) -> dict:
    """Ein echter Kleinlauf des Workers (Profil, Umgebung, Mitschnitt) in `cwd`."""
    import os
    import uuid
    from . import envs, secrets, streamjson, worker as wk
    from .proc import run_stream
    from .profiles import load_profile
    profile = load_profile(cfg.root, profile_name)
    run_dir = ensure_dir(run_dir)
    session = str(uuid.uuid4())
    cmd, mcp = wk.build_command(cfg, profile, run_dir, session)
    token = secrets.load(cfg.secrets_dir, secrets.DEEPSEEK)
    env = envs.worker_env(cfg, os.environ, token)
    bad = envs.precheck(env, "worker")
    if bad:
        raise RuntimeError(f"Umgebungs-Pruefung fehlgeschlagen: {bad}")
    stats = streamjson.StreamStats()
    out = run_dir / "stream.jsonl"
    log.info("Rauchtest-Lauf startet", profil=profile_name, cwd=str(cwd),
             werkzeuge=len(profile.allowed))
    run = run_stream(cmd, env, cwd=str(cwd), out_path=out, on_event=stats.feed, log=log,
                     hard_wall_s=900, stdin_text=prompt, stderr_path=run_dir / "stream.err.txt")
    write_text_atomic(run_dir / "auftrag.md", prompt)
    return {"rc": run.rc, "dauer": run.duration_s, "text": stats.final_text(),
            "stats": stats.totals(), "cost": stats.cost_usd(), "run_dir": str(run_dir),
            "mcp": mcp, "cmd": cmd, "profile": profile_name, "model": stats.model}


def _hex_kompakt(text: str) -> str:
    return "".join(ch for ch in str(text or "") if ch.isalnum()).lower()


def _pick_comment_address(g, program: str) -> tuple[int, dict, str]:
    """Harmlose Adresse: am Bildende, ohne Kommentar, Bytes sind Fuellmuster."""
    info = g.current_program()
    hi = int(str(info.get("max_address")), 16)
    for off in (4, 8, 16, 32, 64, 128, 256, 512, 1024):
        a = hi - off + 1 if off == 4 else hi - off
        a = hi - off
        try:
            c = g.get_comment(hex(a), program)
            roh = g.call("/read_memory", {"address": hex(a), "length": 4, "program": program})
        except Exception:
            continue
        if c.get("has_comment"):
            continue
        h = _hex_kompakt(roh.get("hex") or roh.get("bytes") or roh.get("data") or "")
        fuell = h in ("ffffffff", "00000000", "")
        if fuell:
            return a, c, h or "(leer)"
    return None, {}, ""


def cmd_ghidra_smoke(args) -> int:
    """Ghidra-Rauchtest ueber das Harness (R12): Wechseln, Lesen, Sichern, Schreiben."""
    import json as _json
    from .ghidra import Ghidra
    cfg = load_config(args.config)
    log = _log(cfg, "ghidra-smoke")
    g = Ghidra(cfg, log)
    sandbox = ensure_dir(Path(str(cfg.get("paths", "sandbox", "g:/Harness/sandbox/workspace"))))
    run_dir = ensure_dir(Path(cfg.root) / "runs" / "ghidra-smoke")
    R: list[str] = []
    fails: list[str] = []

    def zeile(s: str = ""):
        R.append(s)
        print(s)

    def pruef(name: str, bedingung, info: str = "") -> bool:
        ok = bool(bedingung)
        zeile(f"  [{'OK ' if ok else 'FEHL'}] {name}" + (f" - {info}" if info else ""))
        if not ok:
            fails.append(name)
        return ok

    def name_von(p: str) -> str:
        return Path(p).name

    zeile("# Ghidra-Rauchtest ueber das Harness (R12)")
    zeile(f"- Zeit: {now_iso()}")
    zeile(f"- Arbeitsverzeichnis der Test-Worker: {sandbox}")
    zeile(f"- Kein Commit im Decomp-Repo; Ghidra-Aenderungen nur der Kommentar in d).")
    ok, _meta = g.reachable()
    zeile("")
    if not pruef("Ghidra-Server erreichbar", ok):
        write_text_atomic(run_dir / "report.md", "\n".join(R) + "\n")
        return 1
    start_info = g.current_program()
    zeile(f"  Startprogramm: {start_info.get('name')} (Basis {start_info.get('image_base')}, "
          f"{start_info.get('memory_size')} B, {start_info.get('function_count')} Funktionen)")

    # ------------------------------------------------------------------ a)
    zeile("")
    zeile("## a) Programmwechsel (load_program_from_project + switch_program)")
    for ziel in (GHIDRA_MAIN, GHIDRA_BE, GHIDRA_MAIN):
        res = g.ensure_program(ziel, log)
        info = g.current_program()
        ist = str(info.get("name") or "")
        zeile(f"- Ziel {ziel}: {'OK' if res.get('ok') else 'FEHLGESCHLAGEN'} | ist {ist} "
              f"(Basis {info.get('image_base')}, {info.get('memory_size')} B, "
              f"{info.get('function_count')} Funktionen)")
        for s in res.get("steps", []):
            zeile(f"    Schritt: {s}")
        pruef(f"Programm {name_von(ziel)} gestellt", res.get("ok") and ist.lower() == name_von(ziel).lower(),
              f"ist={ist}")

    # ------------------------------------------------------------------ f)
    zeile("")
    zeile("## f) Liegen 0x80054AE4 und FUN_8005CC54 in main.bin oder be.bin?")
    zugehoerig: dict[str, bool] = {}
    for ziel in (GHIDRA_MAIN, GHIDRA_BE):
        g.ensure_program(ziel, log)
        info = g.current_program()
        lo = int(str(info.get("min_address")), 16)
        hi = int(str(info.get("max_address")), 16)
        drin = lo <= GHIDRA_ADDR <= hi and lo <= GHIDRA_FUN <= hi
        raw = ""
        try:
            r = g.call("/read_memory", {"address": hex(GHIDRA_ADDR), "length": 4,
                                        "program": info.get("name")})
            raw = _hex_kompakt(r.get("hex") or r.get("bytes") or r.get("data") or "") or \
                _json.dumps(r, ensure_ascii=False)[:160]
        except Exception as exc:
            raw = f"Fehler: {str(exc)[:120]}"
        deko = ""
        try:
            d = g.call("/decompile_function", {"address": hex(GHIDRA_FUN),
                                               "program": info.get("name")})
            deko = str(d.get("decompiled") or d.get("code") or d.get("pseudocode")
                       or _json.dumps(d, ensure_ascii=False))[:120]
        except Exception as exc:
            deko = f"Fehler: {str(exc)[:120]}"
        zugehoerig[str(info.get("name"))] = bool(drin)
        zeile(f"- {info.get('name')}: Bereich 0x{lo:08x}..0x{hi:08x} -> Adresse darin: {drin}")
        zeile(f"    read_memory(0x{GHIDRA_ADDR:08x})   -> {raw[:160]}")
        zeile(f"    decompile(0x{GHIDRA_FUN:08x})      -> {deko}")
    zeile("- Doku-Beleg (Zeilen mit Programmnamen und Basis/Adresse):")
    treffer = 0
    for p in sorted((Path(cfg.decomp) / "analysis").glob("*.md")):
        try:
            text = read_text(p)
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if ("main.bin" in line or "be.bin" in line) and \
                    ("0x80000000" in line or "80054AE4" in line or "ffe00000" in line):
                zeile(f"    {p.name}:{i}: {line.strip()[:200]}")
                treffer += 1
                if treffer >= 6:
                    break
        if treffer >= 6:
            break

    # ------------------------------------------------------------------ c)
    zeile("")
    zeile("## c) Projektsicherung (archive_project, wie bei schreibenden Profilen)")
    bk = g.backup_project(log, reason="Ghidra-Rauchtest (R12)")
    pfad = Path(bk["path"]) if bk.get("path") else None
    existiert = bool(pfad and pfad.is_file())
    groesse = pfad.stat().st_size if existiert else 0
    proj = Path(cfg.decomp) / "ghidra"
    proj_groesse = sum(f.stat().st_size for f in proj.rglob("*") if f.is_file()) if proj.is_dir() else 0
    zeile(f"- archive_project: ok={bk.get('ok')} | Datei {bk.get('path') or '-'} | {groesse} B")
    for s in bk.get("steps", []):
        zeile(f"    Schritt: {s}")
    zeile(f"    Vergleich Projektordner: {proj_groesse} B")
    pruef("Sicherungsdatei existiert", existiert)
    pruef("Sicherung plausibel gross", groesse > max(200_000, int(0.1 * proj_groesse)),
          f"{groesse} B")

    # ------------------------------------------------------------------ b)
    zeile("")
    zeile("## b) Lesen (Profil ghidra-read, Programm main.bin)")
    g.ensure_program(GHIDRA_MAIN, log)
    rb = _smoke_worker(cfg, log, "ghidra-read", GHIDRA_READ_PROMPT, run_dir / "read", sandbox)
    zeile(f"- Lauf: rc={rb['rc']} | {rb['dauer']:.0f}s | {rb['stats']['requests']} Anfragen | "
          f"${rb['cost']:.4f} | Modell {rb['model']}")
    zeile("- Antwort des Test-Workers:")
    for ln in (rb["text"] or "(leer)").strip().splitlines()[:20]:
        zeile("    " + ln)
    roh = g.call("/read_memory", {"address": hex(GHIDRA_ADDR), "length": 4,
                                  "program": name_von(GHIDRA_MAIN)})
    h_roh = _hex_kompakt(roh.get("hex") or roh.get("bytes") or roh.get("data") or "")
    zeile(f"- Harness-Gegenprobe read_memory: {_json.dumps(roh, ensure_ascii=False)[:200]}")
    pruef("Worker meldet Rohwort 48008171", "48008171" in _hex_kompakt(rb["text"]))
    pruef("Server liefert Rohwort 48008171", h_roh.startswith("48008171"), h_roh)
    pruef("Worker meldet eine Ziel-Funktion", "8005cc54" in _hex_kompakt(rb["text"]))

    # ------------------------------------------------------------------ d)
    zeile("")
    zeile("## d) Schreiben (Profil ghidra-standard)")
    if args.skip_write:
        zeile("- uebersprungen (--skip-write).")
    else:
        g.ensure_program(GHIDRA_BE, log)
        adresse, vorher_c, fuell = _pick_comment_address(g, name_von(GHIDRA_BE))
        if adresse is None:
            zeile("- keine harmlose Adresse gefunden - d) uebersprungen.")
            fails.append("d) Adresse finden")
        else:
            a_hex = hex(adresse)
            zeile(f"- Zieladresse {a_hex} in {name_von(GHIDRA_BE)} (Bytes vorher: {fuell}, "
                  f"has_comment: {vorher_c.get('has_comment')})")
            p_set = GHIDRA_WRITE_PROMPT.format(
                aktion="SETZEN", addr=a_hex,
                schritt=f'set_comment an {a_hex} mit dem Text "HARNESS-TEST" (Art "eol"). '
                        f'Sonst nichts.')
            r1 = _smoke_worker(cfg, log, "ghidra-standard", p_set, run_dir / "write-set", sandbox)
            zeile(f"- Lauf SETZEN: rc={r1['rc']} | {r1['dauer']:.0f}s | "
                  f"${r1['cost']:.4f} | {r1['stats']['requests']} Anfragen")
            for ln in (r1["text"] or "(leer)").strip().splitlines()[:12]:
                zeile("    " + ln)
            c1 = g.get_comment(a_hex, name_von(GHIDRA_BE))
            zeile(f"- Harness liest nach dem Setzen: {_json.dumps(c1, ensure_ascii=False)[:220]}")
            s1 = g.save_program(name_von(GHIDRA_BE))
            zeile(f"- save_program: {_json.dumps(s1, ensure_ascii=False)[:160]}")
            c2 = g.get_comment(a_hex, name_von(GHIDRA_BE))
            zeile(f"- Harness liest nach dem Speichern: {_json.dumps(c2, ensure_ascii=False)[:220]}")
            pruef("Kommentar gesetzt (Worker)", "HARNESS-TEST" in _json.dumps(c1, ensure_ascii=False))
            pruef("Kommentar nach dem Speichern noch da",
                  "HARNESS-TEST" in _json.dumps(c2, ensure_ascii=False))

            p_weg = GHIDRA_WRITE_PROMPT.format(
                aktion="ENTFERNEN", addr=a_hex,
                schritt=f'set_comment an {a_hex} mit LEEREM Text "" (Art "eol") - damit wird '
                        f'der Kommentar entfernt. HARNESS-TEST ist der Text, der weg soll.')
            r2 = _smoke_worker(cfg, log, "ghidra-standard", p_weg, run_dir / "write-remove", sandbox)
            zeile(f"- Lauf ENTFERNEN: rc={r2['rc']} | {r2['dauer']:.0f}s | "
                  f"${r2['cost']:.4f} | {r2['stats']['requests']} Anfragen")
            for ln in (r2["text"] or "(leer)").strip().splitlines()[:12]:
                zeile("    " + ln)
            c3 = g.get_comment(a_hex, name_von(GHIDRA_BE))
            weg_durch_worker = "HARNESS-TEST" not in _json.dumps(c3, ensure_ascii=False)
            zeile(f"- Harness liest nach dem Entfernen: {_json.dumps(c3, ensure_ascii=False)[:220]}")
            if not weg_durch_worker:
                zeile("- Der Worker hat den Kommentar NICHT entfernt - der Harness raeumt selbst.")
                g.set_comment(a_hex, "", name_von(GHIDRA_BE), kind="eol")
                c3 = g.get_comment(a_hex, name_von(GHIDRA_BE))
                weg_durch_worker = "HARNESS-TEST" not in _json.dumps(c3, ensure_ascii=False)
                zeile(f"- nach dem Raeumen: {_json.dumps(c3, ensure_ascii=False)[:220]}")
            s2 = g.save_program(name_von(GHIDRA_BE))
            zeile(f"- save_program: {_json.dumps(s2, ensure_ascii=False)[:160]}")
            c4 = g.get_comment(a_hex, name_von(GHIDRA_BE))
            sauber = "HARNESS-TEST" not in _json.dumps(c4, ensure_ascii=False)
            zeile(f"- Harness liest nach dem zweiten Speichern: "
                  f"{_json.dumps(c4, ensure_ascii=False)[:220]}")
            pruef("Kommentar ist weg (vor dem Speichern)", weg_durch_worker)
            pruef("Kommentar ist weg (nach dem Speichern)", sauber)
            zeile(f"    Kosten der Schreib-Laeufe: ${r1['cost'] + r2['cost']:.4f}")

    # ------------------------------------------------------------------ e)
    zeile("")
    zeile("## e) Endzustand")
    main_drin = zugehoerig.get(name_von(GHIDRA_MAIN), False)
    ziel_e = GHIDRA_MAIN if main_drin else GHIDRA_BE
    grund = ("0x80054AE4 liegt in main.bin - die naechste Instruktion (cc54_setup) braucht main.bin"
             if main_drin else
             "0x80054AE4 liegt NICHT in main.bin - be.bin bleibt gestellt")
    g.ensure_program(ziel_e, log)
    end_info = g.current_program()
    zeile(f"- gestellt: {end_info.get('name')} (Basis {end_info.get('image_base')}) - {grund}")
    zeile(f"- Hinweis: nach einem Serverneustart laedt das Startskript wieder "
          f"{name_von(GHIDRA_BE)} (dokumentiert).")
    pruef("Endprogramm gestellt", str(end_info.get("name")).lower() == name_von(ziel_e).lower())

    zeile("")
    zeile(f"## Ergebnis: {'ALLES OK' if not fails else str(len(fails)) + ' FEHLER: ' + ', '.join(fails)}")
    write_text_atomic(run_dir / "report.md", "\n".join(R) + "\n")
    print(f"\nBericht: {run_dir / 'report.md'}")
    return 0 if not fails else 1


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


def cmd_number(args) -> int:
    """Batch-Nummer des offenen Auftrags setzen (Anker-Abweichung korrigieren)."""
    n = str(args.nummer).strip()
    if not n.isdigit():
        print("Nutzung: hx.cli number <N>   (z. B. number 159)", file=sys.stderr)
        return 2
    return _ctl_put(load_config(args.config), "number", n)


def cmd_ask(args) -> int:
    """Freie Frage an Claude - eigener, nur lesender Lauf (R13f).

    Laeuft im EIGENEN Prozess: der Harness (und ein laufender Batch) bleibt
    unberuehrt. Antwort kommt auf die Konsole, der Hinweis (Abo, Modell, Anfragen,
    Token, Chat, Limit) darunter.

    R13o: Fragen laufen nacheinander und in EINEM Chat weiter (Gedaechtnis); mit
    `--neu` beginnt ein neuer Chat. Eine Datei-Sperre verhindert, dass zwei
    Aufrufe gleichzeitig dieselbe Session greifen.
    """
    from . import ask as askmod
    cfg = load_config(args.config)
    frage = args.frage or ""
    if args.file:
        p = Path(args.file)
        if not p.is_file():
            print(f"Datei nicht gefunden: {p}", file=sys.stderr)
            return 2
        frage = read_text(p)
    if not frage.strip():
        print('Nutzung: hx.cli ask "<Frage>"   oder   hx.cli ask --file <pfad.md>',
              file=sys.stderr)
        return 2
    log = _log(cfg, "ask")
    res = askmod.ask(cfg, log, frage, neu=bool(getattr(args, "neu", False)))
    print(res.get("text") or "(keine Antwort)")
    print()
    print(res.get("hinweis") or "")
    if res.get("chat"):
        print(f"Chat: {res['chat'].get('id')} (neu: {res['chat'].get('neu')} - "
              f"{res['chat'].get('grund')}, Frage {res['chat'].get('fragen')})")
    if res.get("datei"):
        print(f"Beleg: {res['datei']}")
    return 0 if res.get("ok") else 1


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
    zusatz = ""
    if target == "claude":
        # R13y: beginnt die Nachricht mit einer Kennung aus /fragen, gilt sie als Antwort -
        # Wortlaut und Empfehlung werden angehaengt, eine unbekannte Kennung wird gemeldet.
        from . import fragen as fragenmod
        gate = (read_json(Path(cfg.sub("state")) / "run.json", {}) or {}).get("gate")
        vor = fragenmod.nachricht_vorbereiten(cfg, text, gate=gate)
        if not vor.get("ok"):
            print(vor.get("meldung") or "Unbekannte Kennung.", file=sys.stderr)
            return 2
        text = vor["text"]
        zusatz = "  " + vor["meldung"] if vor.get("bekannt") else ""
    item = queue.enqueue(cfg.root, target, text, "lokal", None)
    print(f"{target}: {item.name} ({len(text)} Zeichen){zusatz}")
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
    return Watcher(cfg, log, batch=args.batch, run=(args.run or None),
                   color=not args.no_color, once=args.once,
                   thinking=not getattr(args, "no_thinking", False)).run()


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
    bi = sub.add_parser("bilanz", help="Bilanz: Aeste im Vergleich, Projektstand, Kosten")
    bi.add_argument("--n", type=int, default=1,
                    help="Vergleichsabstand in Batches (Vorgabe 1 = direkter Vorgaenger)")
    th = sub.add_parser("thinking", help="letzte Denkbloecke des Workers (DeepSeek)")
    th.add_argument("--n", type=int, default=10, help="Anzahl (Vorgabe 10, hoechstens 50)")
    th.add_argument("--batch", type=int, default=0,
                    help="bestimmter Batch (sonst der neueste bzw. der laufende)")
    th.add_argument("--voll", action="store_true",
                    help="Denkbloecke ungekuerzt (sonst je 200 Zeichen)")
    sub.add_parser("fragen", help="offene Fragen an den Nutzer (Anker + letztes Review)")
    mt = sub.add_parser("meta", help="Aussensicht (Meta-Review) starten bzw. vormerken")
    mt.add_argument("--grund", default="", help="Anlass im Bericht (Vorgabe: Befehl)")
    mt.add_argument("--mock", action="store_true", help="Attrappe ohne API-Kosten")
    sub.add_parser("profiles")
    sub.add_parser("probe-telegram")

    a = sub.add_parser("allowlist-add")
    a.add_argument("user_id")

    d = sub.add_parser("demo", help="Attrappen-Zyklus (ohne API-Kosten)")
    d.add_argument("--scenario", default="ok", choices=["ok", "parser_error", "crash"])
    sub.add_parser("show-prompts", help="Review-Prompt und Worker-Vorspann als Dateien schreiben")
    sub.add_parser("env-proof", help="R16: Umgebungs-Nachweis mit einem echten Kleinlauf")
    rb = sub.add_parser("rebuild", help="Lauf aus dem Mitschnitt nachrechnen")
    rb.add_argument("batch", nargs="?", type=int, default=0, help="Batch-Nummer (sonst die letzte)")
    gs = sub.add_parser("ghidra-smoke", help="Ghidra-Rauchtest: wechseln, lesen, sichern, schreiben")
    gs.add_argument("--skip-write", action="store_true", help="Teil d) ueberspringen")

    # --- lokale Steuerung (gleichwertig zu den Telegram-Befehlen) ----------------
    sub.add_parser("pause", help="pausieren (laeuft ein Batch, laeuft er zu Ende)")
    rr = sub.add_parser("resume", help="fortsetzen")
    rr.add_argument("--accept-dirty", action="store_true",
                    help="unsauberen Arbeitsbaum ausdruecklich akzeptieren")
    sub.add_parser("stop", help="laufenden Batch abbrechen (WIP wird gesichert)")
    ap = sub.add_parser("approve", help="wartenden Batch freigeben")
    ap.add_argument("--text", default="", help="optionaler Text, geht als ds-Nachricht mit")
    nu = sub.add_parser("number", help="Batch-Nummer des offenen Auftrags setzen")
    nu.add_argument("nummer", help="Nummer, z. B. 159")
    sd = sub.add_parser("send", help="Nachricht an ds (Worker) oder claude (Reviewer)")
    sd.add_argument("target", choices=["ds", "claude"])
    sd.add_argument("text", nargs="?", default="")
    sd.add_argument("--file", help="langer Text aus einer Datei")
    ak = sub.add_parser("ask", help="freie Frage an Claude (eigener Lauf, nur lesend)")
    ak.add_argument("frage", nargs="?", default="", help="die Frage")
    ak.add_argument("--file", help="Frage aus einer Datei")
    ak.add_argument("--neu", action="store_true",
                    help="neuen Frage-Chat beginnen (sonst laeuft die Frage im selben "
                         "Chat weiter)")
    ri = sub.add_parser("run-instruction", help="eigene Instruktion als naechsten Batch")
    ri.add_argument("--file", help="Datei mit der Instruktion")
    ri.add_argument("--text", default="", help="Instruktion direkt")
    ri.add_argument("--profile", default="", help="none | ghidra-read | ghidra-standard | ghidra-full")
    ri.add_argument("--program", default="", help="Ghidra-Projektpfad")
    wv = sub.add_parser("watch", help="Live-Ansicht des laufenden Betriebs (rein lesend)")
    wv.add_argument("--batch", type=int, default=0, help="abgeschlossenen Batch nachspielen")
    wv.add_argument("--run", default="", help="benannten Lauf nachspielen (z. B. env-proof)")
    wv.add_argument("--no-color", action="store_true", help="ohne Farben (fuer klassisches Konsolenfenster)")
    wv.add_argument("--no-thinking", action="store_true",
                    help="Denkbloecke nicht anzeigen (nur Anzeige, kein Einfluss auf den Lauf)")
    wv.add_argument("--once", action="store_true", help="nur ein Bild der jetzigen Lage, dann Ende")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return {
        "run": cmd_run, "status": cmd_status, "budget": cmd_budget, "profiles": cmd_profiles,
        "bilanz": cmd_bilanz,
        "thinking": cmd_thinking,
        "fragen": cmd_fragen,
        "meta": cmd_meta,
        "probe-telegram": cmd_probe, "allowlist-add": cmd_allowlist, "demo": cmd_demo,
        "show-prompts": cmd_show_prompts,
        "env-proof": cmd_env_proof, "rebuild": cmd_rebuild, "ghidra-smoke": cmd_ghidra_smoke,
        "pause": cmd_pause, "resume": cmd_resume, "stop": cmd_stop,
        "approve": cmd_approve, "send": cmd_send, "number": cmd_number,
        "ask": cmd_ask,
        "run-instruction": cmd_run_instruction, "watch": cmd_watch,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
