"""Freie Frage an Claude - eigener, kurzer Lauf, NUR LESEND (R13f/R13o).

Das Modell steht in `claude.ask_modell` (seit R13bo-4 **Sonnet 5.5**) - hier wird bewusst
kein Modellname genannt, damit Doku und Konfiguration nicht auseinanderlaufen.

Nicht zu verwechseln mit dem Reviewer:
  * eigener Prozess und **eigene Session**, eigener Systemprompt (`prompts/ask.md`),
    mit dem Abo-Token des Reviewers,
  * eigener Werkzeugsatz: nur `Read`, `Grep`, `Glob` - kein Schreiben, kein Bash,
    kein MCP.

R13o (2026-09-27, Nutzerwunsch): Der **Frage-Chat hat ein Gedaechtnis**. Die erste
Frage oeffnet eine Session (`--session-id <uuid>`), Folgefragen laufen darin weiter
(`--resume <uuid>`) - vorher war jede Frage ein neuer Chat, und eine Rueckfrage
("und warum?") konnte nicht auf die vorige Antwort zeigen. Rotiert wird nach
`[ask]` in `harness.toml`: 30 min ohne Frage, mehr als 10 Fragen oder aelter als 2 h.
`/ask-neu` erzwingt sofort einen neuen Chat.

Strikt nacheinander: `ask()` nimmt eine Datei-Sperre (`logs/ask/ask.lock`). Damit
koennen sich Telegram-/ask, `hx.cli ask` und ein zweiter Aufruf NIE dieselbe Session
gleichzeitig greifen. Die Sperre wartet begrenzt und altert (siehe `lock_holen`).
R13bx-6 (11.10.2026, Nutzerwunsch): **/ask kann ohne Abo laufen.** `/ask_swap
[abo|deepseek]` legt den Frage-Lauf auf den anderen Anbieter; auf DeepSeek laeuft er ohne
Abo-Kontingent. Der Anbieter gehoert zum CHAT: die Kennung lebt im Konfigordner des
Anbieters, ein Wechsel legt deshalb einen neuen Chat an (wie beim Reviewer, nur hier fuer
den Frage-Chat). Auf DeepSeek steht in der Hinweiszeile der DOLLARBETRAG - dort ist die
Preistabelle richtig, "kein Einzelpreis" waere schlicht falsch.
Lesezugriff (R13o): `g:\\Harness` (Belege in `docs/`, Sitzungsprotokolle, Sandbox) und
das Decomp-Repo. Gesperrt bleiben die Schluesselordner (neu und alt), `backups/` und
jede `.credentials.json` - Beleg: `tools/check_zugriff3.py` -> `docs/_ask_zugriff_beleg.txt`.

Der Lauf wird vom Aufrufer **in einem eigenen Thread** gestartet: laeuft gerade
ein Batch, darf /ask ihn nicht beeinflussen - der Worker-Takt ruft `poll()` aus
dem Mitschnitt-Thread auf, ein blockierender Unterprozess dort wuerde den
Mitschnitt und damit den Batch anhalten.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import envs, protocol, secrets, streamjson
from .profiles import credential_verbote, pfad_regeln, secrets_verbote
from .proc import run_stream
from .util import ensure_dir, now_iso, read_text, write_text_atomic

# Alles, was schreiben oder nach draussen reden koennte - doppelt gesperrt.
VERBOTEN = ["Bash", "Write", "Edit", "MultiEdit", "NotebookEdit", "WebFetch", "WebSearch",
            "Task", "TodoWrite", "SlashCommand", "Skill", "mcp__ghidra"]

# Vorgaben des Frage-Chats; jede davon ist in `[ask]` der harness.toml einstellbar.
STANDARD = {"fenster_min": 30, "max_fragen": 10, "max_alter_min": 120, "max_turns": 25}

# Sperre: so lange wird auf eine laufende Frage gewartet bzw. ab wann eine Sperre
# als verwaist gilt (ein Lauf kann bei vielen Dateien Minuten dauern).
LOCK_WARTEN_S = 900.0
LOCK_VERFALL_S = 1800.0

_SESSION_FEHLER = ("already in use", "no conversation found", "session not found",
                   "no such session", "could not find session", "invalid session")


class AskBelegt(RuntimeError):
    """Es laeuft schon eine Frage (Sperre gehalten) - nicht gleichzeitig starten."""


# ------------------------------------------------------------------ Chat-Session
def session_pfad(cfg) -> Path:
    return Path(cfg.root) / "logs" / "ask" / "session.json"


def lock_pfad(cfg) -> Path:
    return Path(cfg.root) / "logs" / "ask" / "ask.lock"


def grenzen(cfg) -> dict:
    """Die Grenzen des Frage-Chats aus `[ask]` (mit den Vorgaben als Rueckfall)."""
    return {k: float(cfg.get("ask", k, v)) for k, v in STANDARD.items()}


def _zeitpunkt(text, rueckfall: datetime) -> datetime:
    try:
        return datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return rueckfall


def session_stand(cfg) -> dict:
    """Gelesener Chat-Stand (`{}`, wenn keiner existiert oder er unlesbar ist)."""
    p = session_pfad(cfg)
    if not p.is_file():
        return {}
    try:
        d = json.loads(read_text(p))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def session_waehlen(cfg, jetzt: datetime | None = None, neu: bool = False) -> dict:
    """Welcher Chat gilt fuer diese Frage? (R13o, drei Bremsen)

    Wiederverwendet wird nur, wenn KEINE Grenze reisst: nicht mehr als
    `fenster_min` Minuten seit der letzten Frage, hoechstens `max_fragen` Fragen im
    Chat und der Chat nicht aelter als `max_alter_min` Minuten.
    """
    jetzt = jetzt or datetime.now(timezone.utc)
    g = grenzen(cfg)
    stand = session_stand(cfg)
    grund = "weiter"
    alt = stand.get("id")
    if neu:
        grund = "neu angefordert (/ask-neu)"
    elif not alt:
        grund = "kein Chat vorhanden"
    else:
        letzte = _zeitpunkt(stand.get("letzte"), jetzt - timedelta(days=3650))
        seit = _zeitpunkt(stand.get("seit"), jetzt)
        fragen = int(stand.get("fragen") or 0)
        if jetzt - letzte > timedelta(minutes=g["fenster_min"]):
            grund = (f"Chat war {int((jetzt - letzte).total_seconds() // 60)} min still "
                     f"(Grenze {int(g['fenster_min'])} min)")
        elif fragen >= int(g["max_fragen"]):
            grund = f"{fragen} Fragen im Chat (Grenze {int(g['max_fragen'])})"
        elif jetzt - seit > timedelta(minutes=g["max_alter_min"]):
            grund = (f"Chat ist {int((jetzt - seit).total_seconds() // 60)} min alt "
                     f"(Grenze {int(g['max_alter_min'])} min)")
    neu_chat = grund != "weiter"
    return {"id": str(uuid.uuid4()) if neu_chat else str(alt),
            "seit": jetzt.isoformat() if neu_chat else str(stand.get("seit") or jetzt.isoformat()),
            "fragen": 0 if neu_chat else int(stand.get("fragen") or 0),
            "neu": neu_chat, "grund": grund}


def session_merken(cfg, sess: dict, jetzt: datetime | None = None,
                   anbieter: str = "") -> dict:
    """Nach der Antwort Frage und Zeitpunkt fortschreiben.

    R13bx-6: `anbieter` wird MITGESCHRIEBEN. Nur so laesst sich beim naechsten Aufruf
    erkennen, dass die Sitzung einem anderen Anbieter gehoert - und damit im anderen
    Konfigordner liegt.
    """
    jetzt = jetzt or datetime.now(timezone.utc)
    neu = {"id": sess["id"], "seit": sess["seit"], "letzte": jetzt.isoformat(),
           "fragen": int(sess.get("fragen") or 0) + 1,
           "anbieter": str(anbieter or "")}
    ziel = ensure_dir(session_pfad(cfg).parent)
    write_text_atomic(ziel / "session.json",
                      json.dumps(neu, ensure_ascii=False, indent=1) + "\n")
    return neu


# ----------------------------------------------------------------------- Sperre
def lock_holen(cfg, warten_s: float | None = None, log=None) -> bool:
    """Datei-Sperre holen - /ask laeuft strikt nacheinander (R13o).

    Die Sperre gilt ueber PROZESSE hinweg: ohne sie koennten ein Telegram-/ask und
    ein `hx.cli ask` dieselbe Session gleichzeitig oeffnen (Claude Code bricht dann
    mit "Session ID ... is already in use" ab). Geprueft wird das ALTER, nicht ob
    der Prozess noch lebt - `os.kill(pid, 0)` beendet unter Windows den Prozess,
    das ist als Lebendpruefung unbrauchbar.
    """
    p = lock_pfad(cfg)
    ensure_dir(p.parent)
    grenze = LOCK_WARTEN_S if warten_s is None else warten_s
    t0 = time.time()
    while True:
        try:
            fd = os.open(str(p), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(f"{os.getpid()}\n{now_iso()}\n")
            return True
        except FileExistsError:
            alt = _alter_s(p)
            if alt is not None and alt > LOCK_VERFALL_S:
                if log:
                    log.warn("Frage-Sperre verwaist - wird uebernommen", alter_s=int(alt))
                try:
                    p.unlink()
                except OSError:
                    pass
                continue
            if time.time() - t0 > grenze:
                if log:
                    log.warn("Frage-Sperre blieb belegt", warten_s=int(grenze),
                             halter=_halter_pid(p))
                return False
            time.sleep(2.0)


def lock_freigeben(cfg) -> None:
    try:
        lock_pfad(cfg).unlink()
    except OSError:
        pass


def _alter_s(p: Path) -> float | None:
    try:
        return max(0.0, time.time() - p.stat().st_mtime)
    except OSError:
        return None


def _halter_pid(p: Path) -> str:
    try:
        return read_text(p).splitlines()[0].strip()
    except (OSError, IndexError):
        return "?"


# ---------------------------------------------------------------------- Kommando
# ---------------------------------------------------------------------- Anbieter (R13bx-6)
def ask_wahl(cfg, anbieter: str | None = None) -> dict:
    """(Anbieter, Modell, Denkstufe, Grund) fuer diesen Frage-Lauf.

    Umschalten mit `/ask_swap`. Ohne Umschaltung bleibt es beim Abo (`ask_modell`) - ACHTUNG:
    das ist laut `harness.toml` seit R13bo-4 **Sonnet 5.5**, nicht Opus; das Modell kommt
    deshalb IMMER aus der Konfiguration und wird hier nirgends hart genannt. Auf DeepSeek
    gilt `ask_modell_deepseek` - leer heisst `model_worker`, dieselbe 4.1-Flash-Kennung,
    EINE Quelle, kein zweiter Name im Baum.
    Die Anbieter-Namen und ihre Schreibweisen stehen in `envs` (gemeinsam mit dem Review).
    """
    a = envs.anbieter_wort(anbieter or "") or envs.ANBIETER_ABO
    if a == envs.ANBIETER_DEEPSEEK:
        return {"anbieter": a,
                "modell": str(cfg.get("claude", "ask_modell_deepseek", "")
                              or cfg.get("claude", "model_worker", "deepseek-flash[1m]")),
                "effort": str(cfg.get("claude", "ask_effort_deepseek", "high")),
                "grund": "per /ask_swap auf DeepSeek"}
    return {"anbieter": a,
            "modell": str(cfg.get("claude", "ask_modell", "claude-sonnet-5-5")),
            "effort": str(cfg.get("claude", "reviewer_effort", "high")),
            "grund": "Abo (Vorgabe)" if not (anbieter or "").strip()
                     else "per /ask_swap auf das Abo"}


def anbieter_aus_zustand(cfg) -> str:
    """Der per `/ask_swap` gewaehlte Anbieter, aus dem Harness-Zustand (R13bx-6).

    Fuer Aufrufer, die KEINEN Orchestrator haben (`hx.cli ask`): ohne Zustandsdatei gilt
    das Abo. Es wird nur gelesen - eine fehlende oder kaputte Datei darf die Frage nicht
    kosten, also faellt alles auf das Abo zurueck.
    """
    try:
        p = Path(cfg.sub("state")) / "run.json"
        d = json.loads(read_text(p)) if p.is_file() else {}
        return (envs.anbieter_wort(str((d or {}).get("ask_anbieter") or ""))
                or envs.ANBIETER_ABO)
    except Exception:                                            # noqa: BLE001
        return envs.ANBIETER_ABO


def build_command(cfg, session_id: str | None = None, neu: bool = True,
                  modell: str | None = None) -> list[str]:
    r"""Kommandozeile des Frage-Laufs (Prompt kommt ueber stdin).

    Lesen ist NUR in zwei Wurzeln erlaubt, und die Regeln sind pfadgebunden - ein
    blosses `Read` haette (gemessen 2026-09-26) auch `g:\Harness\secrets` geoeffnet.
    R13o: erlaubt ist jetzt der ganze Harness-Ordner `g:\Harness` (Belege in `docs/`),
    verboten bleiben die Schluesselordner, `backups/` und jede `.credentials.json`.

    `neu=True` mit Kennung = neue Session mit DIESER Kennung; `neu=False` = fortsetzen
    (`--resume`). Ohne Kennung laeuft der Aufruf wie frueher als Einzelfrage.

    R13bx-6: `modell` waehlt das Modell dieses Aufrufs (`ask_wahl`). Fehlt es, gilt
    `ask_modell` - so bleiben Altaufrufer und Tests gueltig.
    """
    exe = str(cfg.get("claude", "exe"))
    wurzeln = (cfg.harness_home, cfg.decomp)
    cmd = [exe, "-p",
           "--output-format", "stream-json",
           "--verbose",
           "--model", str(modell or cfg.get("claude", "ask_modell", "claude-opus-5-5")),
           "--strict-mcp-config",
           "--permission-prompts", "none",
           "--max-turns", str(int(cfg.get("ask", "max_turns", STANDARD["max_turns"]))),
           "--tools", "Read,Grep,Glob",
           "--allowedTools", *pfad_regeln(wurzeln),
           "--disallowedTools", *(VERBOTEN
                                  + secrets_verbote(cfg.secrets_dir, *secrets.ALT_ORTE,
                                                    cfg.backups_dir)
                                  + credential_verbote(wurzeln)),
           "--add-dir", str(cfg.harness_home),
           "--add-dir", str(cfg.decomp)]
    if session_id and not neu:
        cmd += ["--resume", session_id]
    elif session_id:
        cmd += ["--session-id", session_id]
    sp = Path(cfg.prompts_dir) / "ask.md"
    if sp.is_file():
        cmd += ["--append-system-prompt-file", str(sp)]
    return cmd


def prompt_bauen(frage: str, zusatz: str = "") -> str:
    teile = ["FRAGE DES NUTZERS (beantworte sie direkt und knapp):", frage.strip()]
    if zusatz:
        teile += ["", zusatz.strip()]
    return "\n".join(teile) + "\n"


def token_zeile(stats) -> str:
    """Token-Zahlen statt Dollar (R13o).

    Grund: /ask laeuft ueber das Abo. Ein Dollarbetrag waere dort mit der
    DeepSeek-Tabelle gerechnet (`pricing.RATES`) und damit schlicht falsch.
    """
    t = stats.totals()
    ein = int(t["input_miss"]) + int(t["cache_read"]) + int(t["cache_creation"])
    return (f"Token: {ein} ein ({t['cache_read']} aus Cache, {t['cache_creation']} neu), "
            f"{t['output']} aus")


def chat_zeile(cfg, sess: dict, neu: dict) -> str:
    """`Chat seit 12 min, Frage 3/10` - oder der Grund fuer einen neuen Chat."""
    fragen = int(neu.get("fragen") or 0)
    seit = _zeitpunkt(neu.get("seit"), datetime.now(timezone.utc))
    minuten = int((datetime.now(timezone.utc) - seit).total_seconds() // 60)
    grenze = int(grenzen(cfg).get("max_fragen", STANDARD["max_fragen"]))
    kopf = (f"Neuer Chat ({sess.get('grund')})" if sess.get("neu")
            else f"Chat seit {minuten} min")
    return f"{kopf}, Frage {fragen}/{grenze}"


def _session_gerissen(text: str) -> bool:
    t = (text or "").lower()
    return any(m in t for m in _SESSION_FEHLER)


def ask(cfg, log, frage: str, mock: bool = False, zusatz: str = "", neu: bool = False,
        anbieter: str | None = None) -> dict:
    """Eine Frage stellen und die Antwort zurueckgeben.

    Rueckgabe: {"ok", "text", "hinweis", "modell", "anfragen", "token", "kosten_usd",
                "limit", "dauer_s", "stream", "datei", "chat", "secret_hits"}

    `chat` = {"id", "neu", "grund", "fragen"} - welcher Frage-Chat benutzt wurde.
    """
    ziel = ensure_dir(Path(cfg.root) / "logs" / "ask")
    stempel = now_iso().replace(":", "").replace("-", "").replace("T", "-")
    stream = ziel / f"ask-{stempel}.jsonl"
    datei = ziel / f"ask-{stempel}.md"
    prompt = prompt_bauen(frage, zusatz)

    # R13bx-6: Anbieter, Modell und Denkstufe dieses Aufrufs. Der Anbieter gehoert zum
    # CHAT: die Kennung lebt im Konfigordner des Anbieters, ein Wechsel kann den alten
    # Chat nicht fortsetzen und legt deshalb einen neuen an (wie beim Reviewer, nur hier
    # fuer den Frage-Chat).
    wahl = ask_wahl(cfg, anbieter)
    a, modell = wahl["anbieter"], wahl["modell"]
    alt_a = (envs.anbieter_wort(str(session_stand(cfg).get("anbieter") or ""))
             or envs.ANBIETER_ABO)
    wechsel = alt_a != a
    sess = session_waehlen(cfg, neu=bool(neu) or wechsel)
    if wechsel and sess.get("neu"):
        sess["grund"] = f"Anbieter gewechselt ({alt_a} -> {a})"

    if mock:
        text = "(Attrappe) Keine echte Frage gestellt."
        neu_stand = session_merken(cfg, sess, anbieter=a)
        write_text_atomic(datei, f"# Frage\n\n{frage}\n\n# Antwort (Attrappe)\n\n{text}\n")
        return {"ok": True, "text": text, "hinweis": "(Attrappe - keine Kosten)",
            "modell": "mock", "anfragen": 0, "token": "", "kosten_usd": 0.0, "limit": False,
                "dauer_s": 0.0, "stream": str(stream), "datei": str(datei),
                "chat": {"id": sess["id"], "neu": sess["neu"], "grund": sess["grund"],
                         "fragen": neu_stand["fragen"]}}

    # R13bx-6: je Anbieter ein anderes Geheimnis. Fehlt es, sagt der Hinweis auch, wie es
    # anders ginge - ein stummes "kann nicht laufen" waere hier besonders aergerlich.
    if envs.abo_limit_moeglich(a):
        token = secrets.load(cfg.secrets_dir, secrets.CLAUDE_OAUTH)
        fehlt = ("Kein Abo-Token gefunden - /ask kann auf dem Abo nicht laufen. "
                 "Mit `/ask_swap deepseek` laeuft die Frage ohne Abo-Kontingent.")
    else:
        token = secrets.load(cfg.secrets_dir, secrets.DEEPSEEK)
        fehlt = "Kein DeepSeek-Schluessel gefunden - /ask kann auf DeepSeek nicht laufen."
    if not token:
        return {"ok": False, "text": "", "limit": False, "hinweis": fehlt,
                "modell": None, "anfragen": 0, "token": "", "kosten_usd": 0.0, "dauer_s": 0.0,
                "stream": "", "datei": "", "chat": {"id": sess["id"], "neu": sess["neu"],
                                                    "grund": sess["grund"], "fragen": 0}}
    if not lock_holen(cfg, log=log):
        return {"ok": False, "text": "", "limit": False,
                "hinweis": "Es laeuft schon eine Frage (Sperre belegt) - bitte nacheinander.",
                "modell": None, "anfragen": 0, "token": "", "kosten_usd": 0.0, "dauer_s": 0.0,
                "stream": "", "datei": "", "chat": {"id": sess["id"], "neu": sess["neu"],
                                                    "grund": sess["grund"], "fragen": 0}}
    try:
        # R13bx-6: Umgebung je Anbieter. Die Vorher-Pruefung stellt sicher, dass kein
        # Abo-Token in einen DeepSeek-Lauf leckt; die Rollennamen sind verschieden
        # (`reviewer`/`ask_ds`), damit ein falscher Name LAUT auffaellt.
        if envs.abo_limit_moeglich(a):
            env = envs.reviewer_env(cfg, os.environ, token)
            schlecht = envs.precheck(env, "reviewer")
        else:
            env = envs.ask_deepseek_env(cfg, os.environ, token, wahl["effort"])
            schlecht = envs.precheck(env, "ask_ds")
        if schlecht:
            return {"ok": False, "text": "", "limit": False,
                    "hinweis": f"Umgebungs-Vorher-Pruefung fehlgeschlagen: {schlecht}",
                    "modell": None, "anfragen": 0, "token": "", "kosten_usd": 0.0,
                    "dauer_s": 0.0, "stream": "", "datei": "",
                    "chat": {"id": sess["id"], "neu": sess["neu"],
                             "grund": sess["grund"], "fragen": 0}}
        if log:
            log.info("Frage gestartet", anbieter=a, modell=modell,
                     zeichen=len(prompt), chat=sess["id"][:8],
                     chat_neu=sess["neu"], chat_grund=sess["grund"])
        t0 = time.time()
        stats, run, versuch = _lauf(cfg, log, env, prompt, stream, ziel, stempel, sess,
                                    modell=modell)
        dauer = time.time() - t0
    finally:
        lock_freigeben(cfg)

    antwort = (stats.final_text() or "").strip()
    if not antwort:
        roh = (stream.read_text(encoding="utf-8", errors="replace")
               if stream.is_file() else "")[-4000:]
        antwort = f"(keine Antwort erhalten; rc={run.rc})\n{roh}".strip()
    anfragen = len(stats.requests)
    rohtext = (stream.read_text(encoding="utf-8", errors="replace")
               if stream.is_file() else "")
    # R13bx-6: dieselbe Regel wie bei Reviewer und Aussensicht - ein DeepSeek-Lauf kann das
    # Abo-Limit nicht erreichen, und `protocol.LIMIT_PATTERNS` traefe hier sonst das blanke
    # Wort `quota` im englischen Denktext (`envs.abo_limit_moeglich`).
    limit = bool(envs.abo_limit_moeglich(a)
                 and (protocol.looks_like_limit(antwort)
                      or protocol.looks_like_limit(rohtext[-2000:])))
    stand = session_merken(cfg, sess, anbieter=a)
    tok = token_zeile(stats)
    kosten = stats.cost_usd(list(cfg.get("peak", "extra_offpeak_dates", []) or []))
    # R13p: die Abo-Auslastung steht in jedem Frage-Mitschnitt - hier ablegen, damit
    # /status und der Takt sie kennen (der Worker hat kein Claude-Kontingent).
    streamjson.schreibe_rate_limit(cfg, stats.rate_limit, "/ask")
    # R13o: auf dem Abo KEIN Dollar - die Zahl waere mit der DeepSeek-Tabelle gerechnet.
    # R13bx-6: auf DeepSeek ist sie RICHTIG - dort steht der Dollarbetrag.
    preis = (f"Abo - kein Einzelpreis | {tok}" if envs.abo_limit_moeglich(a)
             else f"DeepSeek ${kosten:.4f} | {tok}")
    hinweis = (f"({preis} | {stats.model or '?'} | {anfragen} Anfragen | "
               f"{chat_zeile(cfg, sess, stand)} | {dauer:.0f}s"
               + (" | Versuch 2 (Kennung war nicht nutzbar)" if versuch > 1 else "")
               + (" | LIMIT ERREICHT - spaeter erneut fragen" if limit else "") + ")")
    write_text_atomic(datei, f"# Frage\n\n{frage.strip()}\n\n# Antwort\n\n{antwort}\n\n"
                             f"# Chat\n\n{sess['id']} (neu: {sess['neu']} - {sess['grund']}, "
                             f"Frage {stand['fragen']})\n\n{hinweis}\n")
    if log:
        log.info("Frage beantwortet", rc=run.rc, anfragen=anfragen, token=tok,
                 anbieter=a, dauer_s=round(dauer, 1), limit=limit, chat=sess["id"][:8],
                 chat_fragen=stand["fragen"], versuch=versuch)
    # R13g: auch der Frage-Lauf wird geprueft (er ist rein lesend, aber nicht blind).
    if stats.secret_hits:
        hinweis += " | " + streamjson.secret_alarm_text(stats.secret_hits, "/ask", None)
        streamjson.schreibe_secret_beleg(cfg, stats.secret_hits, "/ask", None)
        if log:
            log.error("SECRET-ZUGRIFF", rolle="/ask",
                      treffer=[f"{h['werkzeug']}:{h['art']}:{h['name']}" for h in stats.secret_hits])
    return {"ok": bool(antwort) and not limit, "text": antwort, "hinweis": hinweis,
            "modell": stats.model, "anfragen": anfragen, "token": tok,
            "kosten_usd": kosten,
            "limit": bool(limit), "dauer_s": dauer, "stream": str(stream), "datei": str(datei),
            "chat": {"id": sess["id"], "neu": sess["neu"], "grund": sess["grund"],
                     "fragen": stand["fragen"]},
            "secret_hits": list(stats.secret_hits)}


def _lauf(cfg, log, env, prompt: str, stream: Path, ziel: Path, stempel: str,
          sess: dict, modell: str | None = None) -> tuple:
    """Einen Frage-Lauf fahren; bei gerissener Session EIN neuer Versuch (R13o).

    Die Kennung kann unbrauchbar sein (Chat weg, oder parallel belegt). Dann laeuft
    die Frage mit einer FRISCHEN Kennung noch einmal - lieber eine neue Session als
    eine verlorene Frage.
    """
    for versuch in (1, 2):
        cmd = build_command(cfg, sess["id"], neu=sess["neu"], modell=modell)
        quelldatei = stream if versuch == 1 else ziel / f"ask-{stempel}-v2.jsonl"
        run = run_stream(cmd, env, cwd=str(cfg.root), out_path=quelldatei, log=log,
                         stdin_text=prompt,
                         stderr_path=ziel / f"ask-{stempel}.err.txt")
        stats = streamjson.StreamStats(streamjson.secret_watch(cfg))
        text = (quelldatei.read_text(encoding="utf-8", errors="replace")
                if quelldatei.is_file() else "")
        for line in text.splitlines():
            stats.feed(line)
        fehler_text = ""
        err = ziel / f"ask-{stempel}.err.txt"
        if err.is_file():
            fehler_text = err.read_text(encoding="utf-8", errors="replace")
        if versuch == 1 and run.rc != 0 and (
                _session_gerissen(fehler_text) or _session_gerissen(stats.final_text() or "")):
            if log:
                log.warn("Frage-Chat nicht nutzbar - neuer Versuch mit frischer Kennung",
                         rc=run.rc, chat=str(sess["id"])[:8])
            sess["id"] = str(uuid.uuid4())
            sess["neu"] = True
            sess["grund"] = "vorige Kennung war nicht nutzbar"
            continue
        return stats, run, versuch
    return stats, run, 2
