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
import re
import shutil
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import aufraeumen, envs, pricing, retention, secrets, stand, streamjson, uhr
from .gitsafe import Git

# R13v3: Wie oft werden die Nachfahren des Workers aufgenommen? Der Nachweis "dieser
# Prozess gehoerte zu diesem Lauf" ist nur zu fuehren, SOLANGE die Kette lebt - ein per
# `Start-Process` gestarteter Hintergrundlauf verliert seinen Elternprozess mit dem
# naechsten Werkzeugaufruf (B207: PID 4996). Deshalb alle 60 s eine kurze Aufnahme in
# einem Daemon-Thread (der Leser des Mitschnitts darf dafuer nie warten).
PID_AUFNAHME_S = 60.0
from .ghidra import Ghidra
from .proc import run_stream
from .profiles import builtin_args, load_profile
from .util import ensure_dir, now_iso, read_text, secs_human, write_json_atomic, write_text_atomic


class WorkerResult:
    def __init__(self):
        self.rc: int | None = None
        self.duration_s = 0.0               # Wanduhr des Worker-Prozesses (R13c)
        self.duration_harness_s: float | None = None   # vom Harness gemessen
        self.duration_cli_s: float | None = None       # vom claude-Prozess gemeldet
        self.duration_api_s: float | None = None       # nur API-Zeit
        self.duration_quelle: str = ""     # woraus duration_s stammt
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
        self.ghidra_save: dict = {}          # R13-1: nach dem Batch gespeichert?
        self.secret_hits: list[dict] = []    # R13g: Schluessel-Zugriffe/Werte im Mitschnitt
        self.abbau: list[dict] = []          # R13i: Muster-Prozessabbau (Harness-Gefahr)
        self.warteschleifen: list[dict] = []  # R13v: Warteschleifen (vermeidbare Zeit)
        self.aufraeumen: dict | None = None   # R13v3: Job-Objekt + Nachsuche nach Resten
        self.vorgaenger: list[str] = []       # R13v3: gesicherte Belege der Vor-Fassung
        # R13ad: Fortsetzungen im SELBEN Chat ({minute, kontext, antwort_kurz, …}).
        self.fortsetzungen: list[dict] = []
        # R13ah: Archiv des Preflights VOR der Fortsetzung (Pfad, "" = keiner noetig).
        self.preflight_archiv: str = ""

    def describe(self) -> str:
        return (f"rc={self.rc} dauer={self.duration_s:.0f}s grenze={self.killed_reason or '-'} "
                f"anfragen={self.stats.get('requests')} kosten=${self.cost_usd:.4f} "
                f"modell={self.model_seen} (ok={self.model_ok})")

    def dauer_text(self) -> str:
        """Laufzeit mit Herkunft - nie eine Zahl ohne Bezug (R13c)."""
        basis = {
            "cli": "Wanduhr des Worker-Prozesses laut claude-Prozess",
            "wanduhr": "vom Harness gemessene Wanduhr (Prozess nennt keine Dauer)",
            "api": "NUR API-Zeit - der Prozess nennt keine Wanduhr",
        }.get(self.duration_quelle or "", self.duration_quelle or "Herkunft unbekannt")
        txt = f"{secs_human(self.duration_s)} ({basis}"
        if self.duration_quelle == "cli" and self.duration_harness_s:
            rest = self.duration_harness_s - self.duration_s
            if rest >= 120:
                txt += f"; zusaetzlich {secs_human(rest)} Harness-Nachlauf/Rueckstau"
        txt += ")"
        return txt


def save_ghidra_after_batch(cfg, log, state, profile_name: str, mock: bool = False,
                            http_state: list | None = None) -> dict:
    """Nach JEDEM Batch mit Ghidra-Zugriff speichern (R13-1, erweitert R13e).

    Ohne das bleiben Aenderungen nur im Speicher des Servers: bei Absturz oder
    Neustart sind sie weg, und der Git-Commit waere weiter als die Ghidra-DB.

    R13e: Das gilt jetzt fuer JEDES Profil mit Ghidra-Zugriff - auch `ghidra-read`.
    Grund (Punkt 2 des Sammelauftrags): der HTTP-Weg auf 127.0.0.1:8089 ist
    ausdruecklich erlaubt, auch schreibend; ein Leseprofil kann den gemeinsamen
    Zustand also sehr wohl veraendern. Speichern kostet Sekunden.

    Rueckgabe: {"needed":bool, "ok":bool|None, "blocking":bool, "hinweis":str, "steps":[...]}
    `blocking` = ein Fehlschlag muss Push/Review anhalten (bei schreibendem Profil
    oder bemerkter HTTP-Beruehrung des gemeinsamen Zustands).
    """
    try:
        profile = load_profile(cfg.root, profile_name)
    except Exception as exc:
        return {"needed": False, "ok": None, "blocking": False,
                "hinweis": f"Profil unbekannt: {str(exc)[:80]}"}
    if not profile.mcp:
        return {"needed": False, "ok": None, "blocking": False,
                "hinweis": f"nicht noetig (Profil {profile_name} ohne Ghidra-Zugriff)"}
    # Ein Fehlschlag ist ein Haltegrund, wenn das Profil schreiben darf ODER der
    # Mitschnitt eine schreibende HTTP-Beruehrung zeigt.
    blocking = bool(profile.writes_ghidra or (http_state or []))
    grund = ("Profil schreibt" if profile.writes_ghidra
             else "HTTP-Beruehrung im Mitschnitt" if http_state
             else f"Profil {profile_name} liest nur")
    if mock:
        return {"needed": True, "ok": True, "blocking": blocking, "grund": grund,
                "hinweis": "Attrappe: Speichern nur simuliert",
                "steps": ["mock: save_all_programs simuliert"]}
    try:
        res = Ghidra(cfg, log).save_all_programs()
    except Exception as exc:
        if log:
            log.error("Ghidra-Speichern nach dem Batch fehlgeschlagen", fehler=str(exc)[:200])
        return {"needed": True, "ok": False, "blocking": blocking,
                "hinweis": f"Fehler: {str(exc)[:200]}", "steps": []}
    ok = bool(res.get("success", True)) if isinstance(res, dict) else True
    hinweis = (f"save_all_programs ok ({res.get('saved_count')} Programme)"
               if ok else f"save_all_programs meldet Fehler: {json.dumps(res)[:200]}")
    if log:
        (log.info if ok else log.error)("Ghidra nach dem Batch gespeichert" if ok
                                        else "Ghidra NICHT gespeichert", hinweis=hinweis)
    return {"needed": True, "ok": ok, "blocking": blocking, "grund": grund,
            "hinweis": hinweis,
            "steps": [f"save_all_programs -> {json.dumps(res, ensure_ascii=False)[:300]}"]}


def run_dir(cfg, batch: int) -> Path:
    p = ensure_dir(Path(cfg.root) / "runs" / f"b{batch:03d}")
    return p


# R13v3: Belege, die eine VORIGE Fassung desselben Batches hinterlassen hat.
# Reihenfolge = Umbenennung in `<name>-v1.<endung>`.
VORGAENGER_BELEGE = ("stream.jsonl", "stream.err.txt", "auftrag.md", "result.json",
                     "antwort.md", "harness-facts.md")


def sichere_vorgaenger(rd: Path, log=None) -> list[str]:
    """Belege der vorigen Fassung desselben Batches wegsichern (R13v3).

    Anlass: die Nummer des naechsten Laufs kommt aus dem ANKERKOPF. Schreibt ein
    abgebrochener Worker den Anker nicht fort, laeuft der naechste Batch mit DERSELBEN
    Nummer und damit in DENSELBEN Ordner - ohne diese Sicherung ueberschreibt er den
    Mitschnitt des abgebrochenen Laufs. `retention.MIT_ZIP` kennt `stream-v1.jsonl`
    ohnehin schon; hier entsteht die Datei.
    """
    if not (Path(rd) / "stream.jsonl").is_file():
        return []
    umbenannt: list[str] = []
    for name in VORGAENGER_BELEGE:
        quelle = Path(rd) / name
        if not quelle.is_file():
            continue
        ziel = quelle.with_name(quelle.stem + "-v1" + quelle.suffix)
        try:
            quelle.replace(ziel)
            umbenannt.append(ziel.name)
        except OSError as exc:                                       # noqa: BLE001
            if log:
                log.warn("Beleg der vorigen Fassung nicht gesichert", datei=name,
                         fehler=str(exc)[:120])
    if umbenannt and log:
        log.warn("Belege der vorigen Fassung gesichert (gleiche Batch-Nummer)",
                 ordner=str(rd), dateien=umbenannt)
    return umbenannt


def write_mcp_config(cfg, run_path: Path, profile) -> str | None:
    """Schreibt die MCP-Konfiguration fuer genau diesen Lauf (Profil-abhaengig)."""
    if not profile.mcp:
        return None
    lazy = "--lazy" in [str(a) for a in (cfg.get("ghidra", "bridge_args", []) or [])]
    args = ["--transport", "stdio", *list(cfg.get("ghidra", "bridge_args", []) or [])]
    if lazy:
        # R13e: im Lazy-Modus ist die sichtbare Werkzeugmenge kleiner als die
        # erlaubte - gemessen 97/215 (Befund 2026-09-26). Nur dann ist
        # --default-groups ueberhaupt wirksam; im Normalbetrieb (eager) laedt die
        # Bridge alle Gruppen und allowed/denied entscheiden allein.
        groups = profile.groups or str(cfg.get("ghidra", "bridge_groups", "listing,function,program"))
        args += ["--default-groups", groups]
        if run_path is not None:
            (run_path / "mcp-lazy-warnung.txt").write_text(
                "ACHTUNG: --lazy ist aktiv. Die Bridge zeigt dann nur die Gruppen "
                f"'{groups}' - Werkzeuge ausserhalb sind unsichtbar, auch wenn das Profil "
                "sie erlaubt. Nachladen ginge nur ueber search_tools/load_tool_group "
                "(absichtlich gesperrt). Empfehlung: --lazy entfernen.",
                encoding="utf-8")
    data = {
        "mcpServers": {
            "ghidra": {
                "type": "stdio",
                "command": str(cfg.get("ghidra", "bridge_exe")),
                "args": args,
                "env": {},
            }
        }
    }
    p = write_json_atomic(run_path / "mcp.json", data)
    return str(p)


def write_worker_hooks(cfg, rd: Path, state_datei, log=None) -> str | None:
    """PostToolUse-Hook "Batch-Uhr" als Einstellungsdatei fuer DIESEN Lauf (R13ac).

    Anlass (Befund M210-1): der Worker schaetzte seine Laufzeit an der Zahl der
    Werkzeugaufrufe (B210: "~180 min" geschaetzt, **46 min** gemessen) und strich mit
    dieser falschen Zeitnot Pflichtteile. Die Zeile, die der Hook nach JEDEM
    Werkzeugaufruf in den Kontext legt, ist die gemessene Wanduhr.

    **Gemessen** (`tools/r13ac_probe_hook.py`, Beleg `docs/_r13ac_hook.txt`): mit einer
    Einstellungsdatei nach diesem Muster nannte das Worker-Modell die BATCH-UHR-Zeile
    woertlich - der Text kommt also beim Modell an (Claude-Doku "Hooks reference",
    PostToolUse -> `hookSpecificOutput.additionalContext`).

    Die Startzeit kommt aus `state/run.json` (`worker.started_at`) - derselben Quelle
    wie die watch-Anzeige (R13ac, Punkt 5). Fehlt die Datei oder das Skript, wird kein
    Hook gehaengt (der Lauf bleibt unberuehrt).
    """
    if not bool(cfg.get("claude", "worker_hooks", True)):
        return None
    skript = Path(__file__).resolve().parents[1] / "tools" / "batch_uhr.py"
    if not skript.is_file():
        if log:
            log.warn("Batch-Uhr-Hook fehlt", pfad=str(skript))
        return None
    weich = float(cfg.get("limits", "alarm_wall_s", 5400)) / 60.0
    hart = float(cfg.get("limits", "hard_wall_s", 10800)) / 60.0
    # R13ad: EINE Zeitquelle - die Umschaltschwelle und die Kontextgrenze kommen aus
    # `harness.toml` und gehen mit in den Hook.
    # R13ah (Aussensicht B214, Befund 3): die Schwelle ist jetzt
    # `Alarm - max(15 min, Preflightdauer + 5 min)` (`umschalt_minuten`) und die
    # gemessene Preflightdauer steht als eigene Zahl in der Uhr-Zeile.
    # R13ao (Teil B): `--run` nennt dem Hook das Laufverzeichnis. Daraus liest er
    # `auftrag.md` (NACHRUECKLISTE) und schreibt `preflight-aufrufe.jsonl`, das
    # `_finish_run` nach `result.json` zaehlt. Fehlt der Schalter (Einstellungsdatei
    # aus einer aelteren Fassung, z.B. bei einem schon laufenden Batch), behauptet der
    # Hook nichts und zaehlt nichts - der Lauf bleibt unberuehrt.
    u = umschalt_minuten(cfg, log)
    umschalt = u["umschalt_min"]
    kontext_limit = int(cfg.get("limits", "kontext_limit", 1000000))
    daten = {"hooks": {"PostToolUse": [{"hooks": [{
        "type": "command",
        "timeout": 10,
        "command": sys.executable,
        "args": [str(skript), "--state", str(state_datei),
                 "--weich", f"{weich:.0f}", "--hart", f"{hart:.0f}",
                 "--umschalt", f"{umschalt:.0f}",
                 "--preflight-min", f"{u['preflight_min']:.1f}",
                 "--preflight-batch", str(u["preflight_batch"]),
                 "--kontext-limit", str(kontext_limit),
                 "--run", str(rd)],
    }]}]}}
    ziel = Path(rd) / "worker-hooks.json"
    write_text_atomic(ziel, json.dumps(daten, indent=1) + "\n")
    if log:
        log.info("Batch-Uhr als PostToolUse-Hook gehaengt", datei=ziel.name,
                 weich_min=f"{weich:.0f}", hart_min=f"{hart:.0f}",
                 umschalt_min=f"{umschalt:.0f}",
                 vorlauf_min=f"{u['vorlauf_min']:.1f}",
                 preflight_min=f"{u['preflight_min']:.1f}",
                 preflight_batch=u["preflight_batch"], kontext_limit=kontext_limit)
    return str(ziel)


def build_command(cfg, profile, run_path: Path, session_id: str,
                  system_prompt_file: str | None = None,
                  hooks_settings: str | None = None,
                  resume: bool = False) -> tuple[list[str], str | None]:
    """Kommandozeile OHNE Prompt - der Prompt geht über stdin (UTF-8).

    Beleg (offizielle Doku, Seite "Run Claude Code programmatically"):
      "Non-interactive mode reads stdin, so you can pipe data in" und
      "Piped stdin is capped at 10MB".
    Grund: die Windows-Kommandozeile ist bei ~32.000 Zeichen zu Ende; unsere
    Prompts (Vorspann + Auftrag + Queue) können deutlich größer werden.

    `hooks_settings` (R13ac) ist die Einstellungsdatei mit dem Batch-Uhr-Hook
    (`--settings <datei>`, s. `write_worker_hooks`).

    `resume` (R13ad): `True` setzt denselben Chat mit `--resume <session_id>` fort.
    Gemessen im Reviewer und bei `/ask`: die CLI legt mit `--session-id <uuid>` an und
    setzt mit `--resume <uuid>` fort (Doku: "-r, --resume [value]  Resume a conversation
    by session ID"). Der Systemprompt wird bei `--resume` NICHT neu gelesen - hier ohne
    Belang, der Worker bekommt seinen Auftrag ueber stdin.
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
           "--tools", tools_value]
    cmd += ["--resume", session_id] if resume else ["--session-id", session_id]
    if mcp_cfg:
        cmd += ["--mcp-config", mcp_cfg]
        allowed = allowed + profile.mcp_names()
    cmd += ["--allowedTools", *allowed]
    denied = profile.mcp_denied_names() if profile.mcp else ["mcp__ghidra"]
    # R13v (2026-09-28): das WARTE-PRIMITIV sperren. Gemessen in B207: zwei
    # Abfrageschleifen kosteten 1083,7 s (`stream.jsonl:76873/77152`). Der erlaubte
    # Weg fuer lange Laeufe steht im Vorspann (`Wait-Process -Timeout`, oder synchron
    # mit `timeout` bis 600000 ms).
    # NACHGEMESSEN am 2026-09-28 mit echtem claude-Lauf (tools/r13v_sperrprobe.py,
    # Beleg docs/_r13v_sperrprobe.txt): die Sperre wirkt NICHT als Praefix-Regel.
    # `PowerShell(Start-Sleep*)` lehnt `Start-Sleep` an JEDER Stelle des Befehls ab -
    # nackt, hinter `;`, in `if (…) { … }` und in der `for`-Schleife (wortgleich) -
    # und loest den Alias `sleep` dabei auf. Nur eine blosse ERWAEHNUNG im Text
    # (`Write-Output "Start-Sleep -Seconds 3"`) laeuft durch.
    # Nicht gesperrt: `[Threading.Thread]::Sleep(2000)`. Dafuer ist der Waechter da
    # (`streamjson.warte_muster` im on_event, R13v2 schaetzt auch diese Form).
    denied = denied + ["PowerShell(Start-Sleep*)", "Bash(sleep *)"]
    cmd += ["--disallowedTools", *denied]
    if system_prompt_file:
        cmd += ["--append-system-prompt-file", system_prompt_file]
    if hooks_settings:
        cmd += ["--settings", hooks_settings]
    return cmd, mcp_cfg


def _kurz(text: str, grenze: int = 200) -> str:
    """Antwort des Workers in EINER Zeile (fuer `result.json`)."""
    return " ".join(str(text or "").split())[:grenze]


# ------------------------------------------------- Fortsetzung (R13ad, Auftrag 2026-09-29)
# Der Worker hoerte zwischen B202 und B212 wiederholt FRUEH auf (18-52 min von 90), oft mit
# offener Nachrueckliste - kein Batch wurde hart abgebrochen. Statt den Batch zu verlieren,
# wird derselbe Chat fortgesetzt (`--resume <session-id>`), solange alle Bedingungen unten
# erfuellt sind. Die Grenzen (Zeit, Anfragen, Kosten) gelten ueber ALLE Teillaeufe.
_RE_NACHRUECK = re.compile(r"^\s*(?:[#*]+\s*)*NACHR(?:Ü|UE)CKLISTE\b",
                           re.IGNORECASE | re.MULTILINE)
_RE_ERLEDIGT = re.compile(r"NACHR(?:Ü|UE)CKLISTE\s+ERLEDIGT", re.IGNORECASE)


def hat_nachrueckliste(text: str) -> bool:
    """Traegt der Auftrag einen `NACHRUECKLISTE`-Abschnitt? (Bedingung (d), R13ad)

    Erkannt wird das Wort am **Zeilenanfang** (mit optionaler Markdown-Auszeichnung
    `#`/`*` - auch kombiniert - und Einrueckung), Gross/Klein egal, in **beiden**
    Schreibweisen (`NACHRUECKLISTE` und `Nachrückliste`) und mit beliebigem Anhang. Damit
    gelten alle geforderten Formen:

        ## NACHRUECKLISTE
        NACHRUECKLISTE:
        NACHRUECKLISTE (…):
        Nachrückliste

    Das ist genau das ALTE Format der Auftraege (gemessen mit
    `Select-String -Path runs\b2*\auftrag.md -Pattern 'NACHR(UE|Ü)CKLISTE'`):
    `runs/b211/auftrag.md:170`, `runs/b212/auftrag.md:169` und
    `runs/b213/review.md:126` (DS_INSTRUCTION) schreiben je
    `NACHRUECKLISTE (…):` am Zeilenanfang. **Erkennung heisst nicht Pflicht:** der
    Reviewer soll seit R13ad `## NACHRUECKLISTE` schreiben (`prompts/reviewer.md`),
    angenommen wird auch die alte Form.

    Nicht erkannt werden blosse ERWAEHNUNGEN mitten in der Zeile (z. B.
    `  (4) NACHRUECKLISTE;` oder `- Offen: Nachrueckliste B211 (…)`) - die beschreiben
    fremde Posten, keinen Abschnitt dieses Auftrags.
    """
    return bool(_RE_NACHRUECK.search(text or ""))


def rest_wanduhr_s(hard_wall_s: float, batch_start: float, jetzt: float) -> float:
    """Rest der HARTEN Wanduhr fuer den GANZEN Batch (mindestens 60 s, R13ad)."""
    return max(60.0, float(hard_wall_s) - (float(jetzt) - float(batch_start)))


# Zuschlag hinter der gemessenen Preflight-Dauer (R13ah): nach dem Preflight kommen noch
# Bilanz, Memory-Export und Commit.
PREFLIGHT_ZUSCHLAG_MIN = 5.0


def umschalt_minuten(cfg, log=None) -> dict:
    """Die wirksame Umschaltschwelle in Minuten (R13ah, Aussensicht B214 Befund 3).

        Vorlauf   = max(`limits.umschalt_vor_alarm_s`, Preflightdauer + 5 min)
        Schwelle  = `limits.alarm_wall_s` - Vorlauf

    Grund: der Vorlauf muss den **Preflight-Lauf selbst** abdecken - er dauert ~10 min
    (gemessen B213 602 s, B214 601,8 s), danach folgen Bilanz und Memory-Export. Mit
    festen 15 min lief B213 mit 104 min ueber die 90-min-Alarmgrenze.

    R13aj: Es zaehlt nur eine Messung, bei der der Preflight-Aufruf **allein** lief
    (`parallel == 1`); sonst misst die Zahl die Wartezeit mit. Ist der neueste Batch
    nur parallel gemessen, kommt der Wert aus dem naechstaelteren Batch und `log`
    bekommt den Vermerk (siehe `stand.preflight_dauer`).

    Rueckgabe: `{alarm_min, fest_min, preflight_min, preflight_batch, vorlauf_min,
    umschalt_min}`. Ohne Messung (kein `result.json` mit Preflight-Aufruf) gilt die feste
    Zahl - `preflight_min` ist dann 0,0 und `preflight_batch` 0.
    """
    alarm_min = float(cfg.get("limits", "alarm_wall_s", 5400)) / 60.0
    fest_min = float(cfg.get("limits", "umschalt_vor_alarm_s", 900)) / 60.0
    dauer = stand.preflight_dauer(cfg, log=log)
    preflight_min = float(dauer["minuten"]) if dauer else 0.0
    vorlauf = max(fest_min, preflight_min + PREFLIGHT_ZUSCHLAG_MIN)
    return {"alarm_min": alarm_min, "fest_min": fest_min,
            "preflight_min": preflight_min,
            "preflight_batch": int(dauer["batch"]) if dauer else 0,
            "vorlauf_min": vorlauf,
            "umschalt_min": max(0.0, alarm_min - vorlauf)}


def batch_aus_checkpoint(state) -> int:
    """Die Batchnummer aus dem Harness-Tag `harness/b<N>-start` (R13ah).

    **Nicht** aus dem Text und nicht aus `state.batch`: der Tag ist der Anker des Batches
    und steht in `state.data["last_checkpoint"]` (`orchestrator` setzt ihn unmittelbar vor
    dem Start, `hx/gitsafe.py::checkpoint`). Fehlt der Tag, gilt `state.batch` als
    Rueckfall - die Zahl ist dann dieselbe, nur die Quelle ist schwaecher (wird geloggt).
    """
    tag = str((getattr(state, "data", {}) or {}).get("last_checkpoint") or "")
    m = re.search(r"harness/b(\d+)-start", tag)
    if m:
        return int(m.group(1))
    return int(getattr(state, "batch", 0) or 0)


def archiviere_preflight_vor_fortsetzung(cfg, state, fortsetzung: int, log=None) -> str:
    """Preflight VOR einem Fortsetzungs-Anstoss wegschreiben und committen (R13ah).

    Liegt `analysis/_preflight_<N>.txt` schon vor, wird sie **unveraendert** (byteweise,
    `shutil.copy2`) nach `analysis/_m<N>/_preflight_<N>_vor_fortsetzung<k>.txt` kopiert
    und mit dem Betreff `B<N>: Preflight vor Fortsetzung archiviert` committet. Grund
    (Aussensicht B214, Befund 2): die Fortsetzung laeuft im SELBEN Batch weiter und
    ueberschreibt die Datei beim naechsten Preflight-Lauf - der Beleg des Standes VOR der
    Fortsetzung waere weg.

    Rueckgabe: Pfad der Archivdatei ("" = nichts zu tun).
    """
    nr = batch_aus_checkpoint(state)
    if nr <= 0:
        if log:
            log.warn("Preflight-Archiv: keine Batchnummer", checkpunkt=
                     str((getattr(state, "data", {}) or {}).get("last_checkpoint")))
        return ""
    quelle = Path(cfg.decomp) / "analysis" / f"_preflight_{nr}.txt"
    if not quelle.is_file():
        if log:
            log.info("Kein Preflight vor der Fortsetzung", batch=nr, fortsetzung=fortsetzung)
        return ""
    ziel = ensure_dir(quelle.parent / f"_m{nr}") / (
        f"_preflight_{nr}_vor_fortsetzung{int(fortsetzung)}.txt")
    shutil.copy2(quelle, ziel)                    # unveraendert, byteweise
    rel = ziel.relative_to(Path(cfg.decomp)).as_posix()
    git = Git(cfg, log)
    git.run("add", "--", rel)
    rc, _so, se = git.run("commit", "-m",
                          f"B{nr}: Preflight vor Fortsetzung archiviert")
    if log:
        log.info("Preflight vor Fortsetzung archiviert", batch=nr, fortsetzung=fortsetzung,
                 datei=rel, rc=rc, fehler=(se.strip()[:200] if rc != 0 else ""))
    return str(ziel)


def fortsetzung_pruefen(cfg, run, stats, auftrag_text: str, minuten: float,
                        fortsetzungen: list[dict], killed_reason: str | None = None,
                        log=None) -> dict:
    """Darf der Worker in DEMSELBEN Chat fortgesetzt werden? -> `{"ja": bool, "grund": str}`.

    Alle Bedingungen (Auftrag 2026-09-29, Punkt 3) muessen erfuellt sein:
      a) regulaeres Ende - letzte Antwort ohne Werkzeugaufruf, kein Abbruchgrund, rc 0,
      b) die Batch-Uhr liegt VOR der Umschaltschwelle,
      c) `kontext_letzte_anfrage` < `kontext_schwelle`,
      d) der Auftrag enthaelt einen Abschnitt `NACHRUECKLISTE`,
      e) es gab weniger als `max_fortsetzungen` Anstoesse.
    """
    max_f = int(cfg.get("limits", "max_fortsetzungen", 2))
    if len(fortsetzungen) >= max_f:
        return {"ja": False, "grund": f"max_fortsetzungen ({max_f}) erreicht"}
    grund = killed_reason or getattr(run, "killed_reason", None)
    if grund:
        return {"ja": False, "grund": f"Abbruchgrund {grund}"}
    if getattr(run, "rc", None) != 0:
        return {"ja": False, "grund": f"rc={getattr(run, 'rc', None)}"}
    if stats.is_error():
        return {"ja": False, "grund": "Antwort ist als Fehler markiert"}
    if stats.letzte_antwort_ohne_werkzeug() is not True:
        return {"ja": False,
                "grund": "kein regulaeres Ende (letzte Antwort mit Werkzeugaufruf)"}
    umschalt_min = umschalt_minuten(cfg, log)["umschalt_min"]
    if minuten >= umschalt_min:
        return {"ja": False, "grund": f"Batch-Uhr {minuten:.0f} min >= "
                                      f"Umschaltschwelle {umschalt_min:.0f} min"}
    kontext = stats.kontext_stats()["kontext_letzte_anfrage"]
    schwelle = int(cfg.get("limits", "kontext_schwelle", 550000))
    if kontext >= schwelle:
        return {"ja": False, "grund": f"Kontext {kontext} >= Schwelle {schwelle}"}
    if not hat_nachrueckliste(auftrag_text):
        return {"ja": False, "grund": "kein Abschnitt NACHRUECKLISTE im Auftrag"}
    return {"ja": True, "grund": ""}


def fortsetzungs_text(minuten: float, kontext: int, alarm_min: float, umschalt_min: float,
                      batch: int = 0, preflight_erneut: bool = False) -> str:
    """Die Fortsetzungsnachricht im SELBEN Chat (Wortlaut laut Auftrag 2026-09-29).

    R13ah (Aussensicht B214, Befund 2): der Text BEGINNT mit der Batchnummer. Grund: die
    Fortsetzung laeuft im selben Batch weiter, ein Commit mit `B<N+1>:` war bisher
    naheliegend - gemessen in B213/B214 wurde die Nummer aus dem Text abgeleitet statt aus
    dem Harness-Tag (`harness/b<N>-start`).
    """
    text = ""
    if batch > 0:
        text = (f"Du bist weiterhin in Batch {int(batch)}. Alle Commits tragen "
                f"B{int(batch)}:, nicht B{int(batch) + 1}:. ")
    text += (f"Batch-Uhr: {minuten:.0f} von {alarm_min:.0f} min, Umschaltschwelle "
             f"{umschalt_min:.0f} min nicht erreicht, Kontext {uhr.kontext_kurz(kontext)}. "
             "Arbeite die offenen Posten der NACHRUECKLISTE ab, je Posten ein Commit mit "
             "Soll-Delta. Ist ein Posten blockiert, nenne mit Beleg, welches Material oder "
             "welche Entscheidung fehlt; Aufwand ist kein Grund. Ist die Nachrückliste "
             "vollständig erledigt, antworte nur mit NACHRUECKLISTE ERLEDIGT und je Posten "
             "dem Commit-Hash.")
    if preflight_erneut:
        text += (" Nach der Nacharbeit: Preflight erneut laufen lassen, Bilanz "
                 "aktualisieren, committen. Der letzte Preflight gilt, der frühere ist "
                 "überholt.")
    return text


def nachrueckliste_erledigt(text: str) -> bool:
    """Hat der Worker mit `NACHRUECKLISTE ERLEDIGT` geantwortet?"""
    return bool(_RE_ERLEDIGT.search(text or ""))


def run_batch(cfg, log, state, instruction: str, profile_name: str, program: str | None,
              queue_block: str = "", notify=None, tick=None, cancel=None, mock: bool = False,
              remote_hinweis: str = "") -> WorkerResult:
    res = WorkerResult()
    res.profile = profile_name
    profile = load_profile(cfg.root, profile_name)
    res.program = program
    batch = state.batch
    rd = run_dir(cfg, batch)
    res.run_dir = str(rd)
    # R13v3: Belege einer vorigen Fassung DIESES Batchordners wegsichern, bevor der neue
    # Lauf etwas schreibt (gleiche Nummer = gleicher Ordner, siehe `sichere_vorgaenger`).
    res.vorgaenger = sichere_vorgaenger(rd, log)
    if profile.mcp:
        # R13-1/R13e: ab jetzt koennen Aenderungen im Server-Speicher stehen, die noch
        # nicht in der Projektdatei sind - auch bei Nur-Lese-Profilen, weil der
        # HTTP-Weg schreibend erlaubt ist. Der Merker wird erst nach dem Speichern
        # wieder geloescht (auch bei Stopp und Harness-Ende geprueft).
        state.data["ghidra_pending"] = True
        state.save()

    # --- 1./2. Ghidra -----------------------------------------------------------------
    if not profile.mcp:
        # Profil ohne Ghidra-Zugriff (z. B. none): KEIN Programmwechsel, KEINE Sicherung
        # und KEIN Programm in den Messdaten - sonst stuende im Bericht ein Programm,
        # das nie gestellt wurde.
        if res.program:
            log.info("Profil ohne Ghidra-Zugriff - Programm wird nicht gestellt",
                     profil=profile_name, programm=str(res.program))
        res.program = None
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
        # --- 3. Sicherung - jetzt fuer JEDES Profil mit Ghidra-Zugriff (R13e) ---------
        # Punkt 2b: Auch ein "Leseprofil" kann den gemeinsamen Zustand veraendern,
        # weil der HTTP-Weg auf 8089 schreibend erlaubt ist. Gemessen 2026-09-26:
        # eine Sicherung kostet 12,1 MB und rund 2 s (Aufbewahrung 5 Staende = ~60 MB),
        # das ist neben Batches von 20-120 min vernachlaessigbar - also immer sichern,
        # statt die Ausnahme zu erraten.
        bk = gh.backup_project(log, reason=f"vor Batch {batch} (Profil {profile_name})")
        if not bk.get("ok"):
            raise RuntimeError("Ghidra-Sicherung fehlgeschlagen - Batch mit Ghidra-Profil "
                               "startet NICHT")
        res.limits["ghidra_backup"] = bk.get("path")

    # --- Auftrag schreiben -------------------------------------------------------------
    # R13ac: die Startzeit steht als ABSOLUTE Ortszeit im Vorspann (Punkt 5 der
    # Nutzerpruefung: "die Batch-Uhr muss dieselbe, korrigierte Startzeit verwenden").
    # Sie ist der Harness-Zeitstempel dieses Moments; die wenigen Sekunden bis zum
    # Prozessstart sind in der Zeile benannt, und die BATCH-UHR-Zeile im Verlauf
    # (worker.started_at) ist die exakte Messung.
    start_zeit = datetime.now(timezone.utc)
    prompt = build_prompt(cfg, instruction, queue_block, res.program, profile_name,
                          remote_hinweis=remote_hinweis, start_zeit=start_zeit)
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
        # Auch die Attrappe traegt die Herkunft der Laufzeit (R13c) - mit derselben
        # Vorrangregel wie der echte Lauf: Prozess-Wanduhr vor Harness-Messung.
        res.duration_harness_s = res.duration_s
        d_cli, d_feld = stats.duration_field()
        res.duration_cli_s = d_cli
        if d_cli:
            res.duration_s = d_cli
            res.duration_quelle = "cli" if d_feld == "duration_ms" else "api"
        else:
            res.duration_quelle = "wanduhr"
        if res.rc != 0:
            res.killed_reason = "mock_crash"
    else:
        session_id = str(uuid.uuid4())   # --session-id verlangt eine echte UUID (mit Bindestrichen)
        hooks = write_worker_hooks(cfg, rd, state.path, log)
        cmd, _mcp = build_command(cfg, profile, rd, session_id, hooks_settings=hooks)
        if len(prompt.encode("utf-8")) > MAX_STDIN_BYTES:
            raise RuntimeError(f"Prompt zu groß für stdin ({len(prompt)} Zeichen)")
        stream_path = rd / "stream.jsonl"
        stats = streamjson.StreamStats(streamjson.secret_watch(cfg))
        lim = {
            "alarm_wall": float(cfg.get("limits", "alarm_wall_s", 5400)),
            # R13p: Vorgaben wie in harness.toml (Alarm 500 / Hart 1000).
            "alarm_requests": int(cfg.get("limits", "alarm_requests", 500)),
            "alarm_cost": float(cfg.get("limits", "alarm_cost_usd", 1.0)),
            "hard_wall": float(cfg.get("limits", "hard_wall_s", 10800)),
            "hard_requests": int(cfg.get("limits", "hard_requests", 1000)),
            "hard_cost": float(cfg.get("limits", "hard_cost_usd", 2.0)),
        }
        # R13ah: die wirksame Umschaltschwelle (Alarmgrenze minus Vorlauf; der Vorlauf
        # enthaelt die gemessene Preflight-Dauer) - EINE Quelle fuer Hook, Fortsetzungs-
        # text und Anstoss-Entscheidung.
        uhr_schwelle = umschalt_minuten(cfg, log)
        fired: set[str] = set()
        gemeldet = [0]                      # R13g: bis hierher schon alarmierte Secret-Treffer
        gemeldet_abbau = [0]                # R13i: bis hierher gemeldeter Prozessabbau
        gemeldet_warte = [0]                # R13v: bis hierher gemeldete Warteschleifen
        extra_dates = list(cfg.get("peak", "extra_offpeak_dates", []) or [])
        takt = streamjson.TaktGeber(TICK_MIN_INTERVAL_S)
        takt_lock = threading.Lock()        # R13h: Takt-Thread und Leser duerfen nicht doppelt takten
        live_stand = [0.0]                  # R13q: Zeitpunkt der letzten Live-Schreibung
        bekannte_pids: list[int] = []       # R13v3: waehrend des Laufs gesehene Nachfahren
        letzte_aufnahme = [0.0]

        def pid_aufnahme(pid: int) -> None:
            """Nachfahren des Workers aufnehmen (laeuft in einem eigenen Thread)."""
            try:
                for p in aufraeumen.nachfahren_pids(pid):
                    if p not in bekannte_pids:
                        bekannte_pids.append(p)
            except Exception as exc:                                 # noqa: BLE001
                log.warn("PID-Aufnahme fehlgeschlagen", fehler=str(exc)[:150])

        def live_schreiben(t: dict, cost: float) -> None:
            """Live-Zahlen des laufenden Batches ablegen (R13q), hoechstens alle 15 s.

            Rein lokal und billig: der Zustand ist eine kleine JSON-Datei. Der
            Mitschnitt wird NICHT dafuer gelesen. Fehler hier duerfen den Lauf nicht
            stoeren - die Anzeige ist kein Messwert.
            """
            jetzt = time.monotonic()
            if jetzt - live_stand[0] < LIVE_SEKUNDEN:
                return
            live_stand[0] = jetzt
            state.data["live"] = {
                "batch": int(batch),
                "ts": now_iso(),
                "requests": int(t.get("requests") or 0),
                "cost_usd": round(float(cost), 6),
                "input_miss": int(t.get("input_miss") or 0),
                "cache_read": int(t.get("cache_read") or 0),
                "output": int(t.get("output") or 0),
                # Auftrag 2026-09-29: die Kontextgroesse der letzten Anfrage - die
                # Batch-Uhr (Hook) zeigt sie, ohne den Mitschnitt zu lesen.
                "kontext": (stats.kontext_werte()[-1] if stats.requests else 0),
            }
            try:
                state.save()
            except OSError as exc:
                log.warn("Live-Zahlen nicht gespeichert", fehler=str(exc)[:120])

        def takt_jetzt():
            """Einen Taktschlag ausfuehren - hoechstens einer gleichzeitig."""
            if tick is None:
                return
            with takt_lock:
                try:
                    tick()
                except Exception:
                    pass

        def on_event(line: str):
            stats.feed(line)
            # R13i: Muster-Prozessabbau SOFORT abbrechen. Der Worker hat in Batch 178 mit
            # `Get-Process python | Where-Object {$_.CPU -gt 50} | Stop-Process` den
            # Harness selbst getoetet (python.exe, ~370 s CPU) - still, ohne
            # Crash-Bericht, ohne stderr. Der Abbruch hier ist eine Notbremse; die Regel
            # im Vorspann soll es verhindern (der Befehl laeuft sonst schon los).
            neu_abbau = stats.abbau[gemeldet_abbau[0]:]
            if neu_abbau:
                gemeldet_abbau[0] = len(stats.abbau)
                res.abbau = list(stats.abbau)
                text = ("ABBRUCH - GEFAHR FUER DEN HARNESS: " + neu_abbau[0]["grund"]
                        + f" (Aufruf: {neu_abbau[0].get('kurz')})")
                log.error("Prozessabbau nach Muster", werkzeug=neu_abbau[0]["werkzeug"],
                          grund=neu_abbau[0]["grund"], befehl=neu_abbau[0].get("kurz"))
                res.alarms.append(text)
                if notify:
                    notify(text)
                res.killed_reason = "prozess_abbau"
                return "kill"
            # R13v: Warteschleifen SOFORT melden und bei Zeitverlust abbrechen.
            # Gemessen in B207: 601,9 s + 481,8 s in zwei Abfrageschleifen auf PID 4996
            # (`runs/b207/stream.jsonl:76873/77152`), in B174 waren es 1993 s - der
            # Vorspann verbot das nur in Prosa. Die Notbremse ist dieselbe wie beim
            # Prozessabbau (R13i): der Lauf endet mit klarem Grund statt in Wartezeit.
            neu_warte = stats.warteschleifen[gemeldet_warte[0]:]
            if neu_warte:
                gemeldet_warte[0] = len(stats.warteschleifen)
                res.warteschleifen = list(stats.warteschleifen)
                summe = sum(float(w.get("warte_s") or 0) for w in stats.warteschleifen)
                letzte = float(neu_warte[0].get("warte_s") or 0)
                art, grund = streamjson.warte_entscheidung(len(stats.warteschleifen),
                                                           summe, letzte)
                text = ("WARTESCHLEIFE (" + str(neu_warte[0].get("grund")) + "): "
                        + str(neu_warte[0].get("kurz")) + f" - {grund}")
                log.warn("Warteschleife erkannt", art=art, grund=neu_warte[0].get("grund"),
                         warte_s=letzte, summe_s=summe, befehl=neu_warte[0].get("kurz"))
                if art == "kill":
                    res.alarms.append(text + "\nABBruch: erlaubt sind `Wait-Process -Timeout`"
                                             " oder ein synchroner Aufruf mit `timeout`.")
                    if notify:
                        notify("ABBRUCH - " + text)
                    res.killed_reason = "warteschleife"
                    return "kill"
                if art == "alarm":
                    res.alarms.append(text)
                    if notify:
                        notify("Hinweis - " + text)
            # R13g: Schluessel-Zugriff sofort melden (Werkzeug nennen, nie den Wert).
            neu = stats.secret_hits[gemeldet[0]:]
            if neu:
                gemeldet[0] = len(stats.secret_hits)
                res.secret_hits = list(stats.secret_hits)
                text = streamjson.secret_alarm_text(neu, "Worker", batch)
                streamjson.schreibe_secret_beleg(cfg, neu, "Worker", batch)
                log.error("SECRET-ZUGRIFF", rolle="Worker", batch=batch,
                          treffer=[f"{h['werkzeug']}:{h['art']}:{h['name']}" for h in neu])
                res.alarms.append(text)
                if notify:
                    notify(text)
            # R13h: Takt, Summen und Kosten NUR im Takt rechnen, nicht je Zeile.
            # Gemessen am 2026-09-26: `cost_usd()` kostet ~1 ms (272 Anfragen) und lief
            # fuer JEDE Zeile - in b177 (156.493 Zeilen) sind das ~179 s Rechenzeit im
            # Leser-Thread, der eigentlich die Ausgabe des Kindprozesses abnehmen soll.
            # `feed()` selbst kostet nur 0,01 ms/Zeile.
            # R13k: HIER KEIN NETZ. Der Telegram-Takt lief bis 2026-09-27 auch in diesem
            # Leser (`takt_jetzt()`), und ein haengender HTTPS-Aufruf hat damit den ganzen
            # Lauf festgehalten: Stack-Dump zeigte den Hauptthread in
            # `on_event -> poll -> get_updates -> urlopen`. Der Leser konnte weder das
            # Ausgabe-Ende noch die Gnade aus R13j pruefen - der Batch kam nie zum Ende.
            # Das Ticken macht jetzt AUSSCHLIESSLICH der Takt-Thread (R13h), der dafuer da
            # ist. Hier bleiben nur lokale, billige Pruefungen (Alarme, harte Grenzen).
            # R13v3: Die PID-Aufnahme der Nachfahren sitzt VOR dem Takt-Riegel: sie
            # braucht keinen Takt und darf nicht davon abhaengen, ob gerade getickt wird.
            jetzt = time.monotonic()
            if jetzt - letzte_aufnahme[0] > PID_AUFNAHME_S:
                letzte_aufnahme[0] = jetzt
                pid = int(((state.data.get("worker") or {}).get("pid") or 0))
                if pid:
                    threading.Thread(target=pid_aufnahme, args=(pid,), daemon=True).start()
            if not takt.faellig():
                return None
            t = stats.totals()
            cost = stats.cost_usd(extra_dates)
            live_schreiben(t, cost)
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

        # R13h: waehrend eines langen Werkzeugaufrufs (68K-Emulation 400-600 s, Port-Bau
        # 420 s) kommt KEINE Zeile im Mitschnitt an - dann wird `on_event` nicht gerufen,
        # der Harness beantwortet also weder /stop noch /pause (Befund 2026-09-26).
        # Der Takt-Thread schliesst diese Luecke und endet mit dem Lauf.
        ticker = (streamjson.TaktThread(takt_jetzt, TICK_MIN_INTERVAL_S, log=log).start()
                  if tick is not None else None)
        # R13v3: Der Worker-Prozess kommt in ein Job-Objekt. Beim Schliessen des Jobs
        # beendet Windows alles, was dann noch darin laeuft - auch Enkel, die der
        # Worker per `Start-Process` entkoppelt hat. Gemessen (docs/_r13v_waise.txt):
        # `taskkill /T /F` trifft nur den Baum, ein entkoppelter Hintergrundlauf
        # ueberlebt ihn. Der Job schliesst diese Luecke, `nachsuche` den Rest (WMI).
        job = aufraeumen.Job(log=log, name=f"harness-worker-b{batch}-{int(time.time())}")
        if not job.create():
            log.warn("Job-Objekt nicht eingerichtet - nur Nachsuche moeglich",
                     grund=job.grund)
            res.alarms.append(f"HINWEIS: Job-Objekt nicht verfuegbar ({job.grund}); "
                              "Prozessreste werden nur nachgesucht.")
        batch_start = time.time()

        def on_start_erster(pid: int) -> None:
            """Erster Teillauf: Startzeit UND PID in den Zustand (das ist die Batch-Uhr)."""
            state.worker_started(pid, str(stream_path), session_id)

        def pid_merken(pid: int) -> None:
            """Fortsetzung: NUR die PID nachziehen.

            `worker.started_at` bleibt der Start des GANZEN Batches - die Batch-Uhr darf
            durch eine Fortsetzung NICHT neu beginnen (Auftrag 2026-09-29, Punkt 3).
            """
            w = dict(state.data.get("worker") or {})
            w["pid"] = int(pid)
            state.data["worker"] = w
            state.save()

        # R13ad: der Batch darf aus MEHREREN Teillaeufen bestehen (Fortsetzung im SELBEN
        # Chat). Alle Ereignisse laufen in DENSELBEN `stats` - damit gelten Anfragen- und
        # Kostenlimit ueber den GANZEN Batch. Die harte Wanduhr wird je Teillauf um die
        # bereits verbrauchte Zeit gekuerzt.
        laeufe: list[dict] = []
        fortsetzungen: list[dict] = []
        fortsetz_text = prompt
        resume = False
        try:
            while True:
                nummer = len(fortsetzungen)
                ziel = stream_path if not resume else rd / f"stream-forts{nummer}.jsonl"
                fehler = (rd / "stream.err.txt" if not resume
                          else rd / f"stream-forts{nummer}.err.txt")
                if resume:
                    log.info("Fortsetzung im selben Chat", anstoss=nummer,
                             session=session_id,
                             rest_s=round(rest_wanduhr_s(lim["hard_wall"], batch_start,
                                                         time.time()), 1))
                    cmd, _mcp = build_command(cfg, profile, rd, session_id,
                                              hooks_settings=hooks, resume=True)
                run = run_stream(cmd, env, cwd=str(cfg.decomp), out_path=ziel,
                                 on_event=on_event,
                                 hard_wall_s=rest_wanduhr_s(lim["hard_wall"], batch_start,
                                                            time.time()),
                                 log=log, cancel=cancel, stdin_text=fortsetz_text,
                                 stderr_path=fehler, job=job,
                                 on_start=(pid_merken if resume else on_start_erster))
                laeufe.append({"run": run, "ziel": ziel, "resume": resume})
                if resume and ziel.is_file():
                    # EIN Mitschnitt: die Fortsetzung wird an `stream.jsonl` angehaengt,
                    # damit watch/rebuild/reasoning-Snapshot unveraendert funktionieren.
                    with open(stream_path, "a", encoding="utf-8") as fh:
                        fh.write(ziel.read_text(encoding="utf-8", errors="replace"))
                if run.killed_reason:
                    res.killed_reason = run.killed_reason
                if resume:
                    letzte_f = fortsetzungen[-1]
                    antwort = stats.final_text() or ""
                    letzte_f["antwort_kurz"] = _kurz(antwort)
                    letzte_f["dauer_s"] = round(float(run.duration_s or 0.0), 1)
                    letzte_f["rc"] = run.rc
                    if nachrueckliste_erledigt(antwort):
                        letzte_f["antwort_kurz"] = "NACHRUECKLISTE ERLEDIGT"
                        log.info("Nachrueckliste erledigt - kein weiterer Anstoss",
                                 anstoss=nummer)
                        break
                minuten = max(0.0, (time.time() - batch_start) / 60.0)
                entsch = fortsetzung_pruefen(cfg, run, stats, prompt, minuten, fortsetzungen,
                                             killed_reason=res.killed_reason, log=log)
                if not entsch["ja"]:
                    log.info("Kein Fortsetzungsanstoss", grund=entsch["grund"],
                             teillaeufe=len(laeufe))
                    break
                kontext = stats.kontext_stats()["kontext_letzte_anfrage"]
                fortsetzungen.append({"minute": round(minuten, 1), "kontext": kontext,
                                      "antwort_kurz": "", "dauer_s": None, "rc": None,
                                      "stream": f"stream-forts{nummer + 1}.jsonl"})
                # R13ah: den Preflight-Stand VOR der Fortsetzung wegsichern (unveraendert
                # plus eigener Commit) - sonst ueberschreibt der naechste Preflight-Lauf
                # im selben Batch den Beleg. Die Batchnummer kommt aus dem Checkpoint-Tag
                # (`harness/b<N>-start`), NICHT aus `state.batch` oder dem Text.
                res.preflight_archiv = archiviere_preflight_vor_fortsetzung(
                    cfg, state, len(fortsetzungen), log=log)
                fortsetz_text = fortsetzungs_text(
                    minuten, kontext, lim["alarm_wall"] / 60.0,
                    uhr_schwelle["umschalt_min"],
                    batch=batch_aus_checkpoint(state),
                    preflight_erneut=(stats.werkzeug_enthaelt("preflight")
                                      and stats.werkzeug_enthaelt("bilanz")))
                resume = True
        finally:
            if ticker is not None:
                ticker.stop()
                log.info("Takt-Thread beendet", aufrufe=ticker.aufrufe)
            # Job schliessen = alle Reste darin beenden (KILL_ON_JOB_CLOSE). Das gilt
            # fuer JEDEN Ausgang: ein nach dem Worker-Ende weiterlaufender Hintergrund-
            # prozess wuerde sonst in den naechsten Batch hineinschreiben.
            if job.zugewiesen:
                log.info("Job-Objekt geschlossen", zugewiesen=job.zugewiesen)
            job.close()
        res.fortsetzungen = list(fortsetzungen)
        # R13p: Abo-Auslastung mitschreiben, WENN dieser Lauf sie geliefert hat. Der
        # DeepSeek-Worker hat kein Claude-Kontingent - dann passiert hier nichts.
        streamjson.schreibe_rate_limit(cfg, stats.rate_limit, f"Worker b{batch}")
        # R13j: Das Kind war fertig, die Pipe blieb offen (Enkelprozess). Das ist kein
        # Abbruch, aber es gehoert in die Batch-Meldung - sonst sieht es aus, als haette
        # der Worker gehaengt.
        letzter = laeufe[-1]["run"]
        if getattr(letzter, "eof_offen_s", None):
            res.alarms.append(
                f"HINWEIS: Der Worker-Prozess war fertig, aber ein weiterlaufender "
                f"Kindprozess hielt die Ausgabe-Pipe ({letzter.eof_offen_s:.0f} s kein Ende). "
                f"Der Lauf wurde abgeschlossen (R13j).")
        res.rc = letzter.rc
        gesamt_wanduhr = round(time.time() - batch_start, 3)
        # R13ad: bei Fortsetzungen ist die Batch-Wanduhr die Summe der Teillaeufe; der
        # Normalfall (EIN Lauf) bleibt unveraendert.
        res.duration_harness_s = (letzter.duration_s if len(laeufe) == 1 else gesamt_wanduhr)
        d_cli, d_feld = stats.duration_field()
        res.duration_cli_s = d_cli
        _api_ms = stats.summe_feld("duration_api_ms")
        res.duration_api_s = round(_api_ms / 1000.0, 3) if _api_ms else None
        # R13c: die Laufzeit ist die Wanduhr des Worker-Prozesses. Vorrang hat die
        # Selbstauskunft des claude-Prozesses (`duration_ms`); sie zaehlt bis zu seinem
        # Ende. Unsere eigene Messung laeuft weiter, bis die Ausgabe abgearbeitet ist -
        # ein Rueckstau im Harness wuerde die Zahl sonst aufblaehen (B159: 20 min statt 6).
        if res.duration_cli_s:
            res.duration_s = res.duration_cli_s
            res.duration_quelle = "cli" if d_feld == "duration_ms" else "api"
        else:
            res.duration_s = res.duration_harness_s
            res.duration_quelle = "wanduhr"
        res.stream_path = str(stream_path)
        if (len(laeufe) == 1 and res.duration_cli_s
                and (res.duration_harness_s - res.duration_cli_s) >= 120):
            # R13c: eine grosse Luecke heisst, der Harness hing hinterher (Rueckstau der
            # Ausgabe) - das gehoert sichtbar in die Bilanz, nicht in eine stille Zahl.
            res.alarms.append(
                f"ALARM: Harness-Nachlauf {res.duration_harness_s - res.duration_cli_s:.0f}s "
                f"(Prozess {res.duration_cli_s:.0f}s laut {d_feld or 'claude'}, "
                f"{res.duration_harness_s:.0f}s aus Harness-Sicht) - Ausgabe-Rueckstau pruefen")
        if res.duration_s >= lim["alarm_wall"]:
            res.alarms.append(f"ALARM: Laufzeit {res.duration_s:.0f}s (Alarmgrenze {lim['alarm_wall']:.0f}s)")

        # R13v3: Prozessreste nachsuchen. Der Job hat den Baum schon beendet; die
        # Nachsuche findet, was NICHT im Baum haengt (per WMI gestartete Hintergrund-
        # laeufe, Muster B207-PID 4996). Sie laeuft nach JEDEM Abbruch und immer dann,
        # wenn das Job-Objekt nicht greifen konnte.
        grund = res.killed_reason or ("" if job.ok or job.zugewiesen else "job-objekt-nicht-verfuegbar")
        if grund:
            auf = aufraeumen.nachsuche(cfg.decomp, seit=batch_start,
                                       wurzeln_pids={l["run"].pid for l in laeufe
                                                     if l["run"].pid},
                                       bekannte_pids=bekannte_pids, log=log)
            auf["anlass"] = grund
            auf["job"] = job.beschreibung()
            res.aufraeumen = auf
            zeile = aufraeumen.zeile(auf)
            if auf.get("gefunden"):
                res.alarms.append(f"PROZESSRESTE des Laufs ({grund}): {zeile}")
                if notify:
                    notify(f"Nachsuche: {zeile}")
            log.info("Nachsuche nach Prozessresten", anlass=grund, ergebnis=zeile,
                     dauer_s=auf.get("dauer_s"))

    # --- 6. Nachher-Pruefung + Snapshot ------------------------------------------------
    return _finish_run(cfg, state, res, stats, batch, profile_name, log, mock=mock)


PREFLIGHT_ZAHL_DATEI = "preflight-aufrufe.jsonl"


def zaehle_preflight_aufrufe(rd) -> tuple[int, int]:
    """`(Aufrufe, davon zu frueh)` aus `runs/b<N>/preflight-aufrufe.jsonl` (R13ao).

    **Definition der Zaehler** (R387: ein Zaehler ohne Definition zaehlt nichts):

    * `preflight_laeufe` - Preflight-Aufrufe des Workers, die der PostToolUse-Hook
      (`tools/batch_uhr.py`) als Shell-Aufruf mit `preflight.py` erkannt hat, **waehrend
      die Batch-Uhr lief** (ohne Startzeit im Zustand schreibt der Hook nichts). Es ist
      die Zahl der *Aufrufe*, nicht der *Laeufe*: derselbe Befehl zweimal = zwei.
    * `preflight_frueh` - davon die Aufrufe **vor der Umschaltschwelle**, als
      `auftrag.md` eine offene `NACHRUECKLISTE` trug (genau die Faelle, in denen der
      Worker den Hinweis gesehen hat).

    Ohne Datei (aeltere Batches, Attrappen, laufende Batches ohne `--run` im Hook):
    `(0, 0)`. Eine halb geschriebene letzte Zeile wird verworfen.
    """
    p = Path(rd) / PREFLIGHT_ZAHL_DATEI
    if not p.is_file():
        return 0, 0
    laeufe = 0
    frueh = 0
    for zeile in read_text(p).splitlines():
        if not zeile.strip():
            continue
        try:
            daten = json.loads(zeile)
        except ValueError:
            continue
        if not isinstance(daten, dict):
            continue
        laeufe += 1
        if daten.get("frueh"):
            frueh += 1
    return laeufe, frueh


def _fehler_kurz(fehler: list[dict], grenze: int = 5) -> list[dict]:
    """Werkzeugfehler je Werkzeug zusammenfassen (Name, Anzahl, Arten).

    R13e: Grundlage der Bilanzzeile "Werkzeugfehler". Die alte Zeile
    "Abgelehnte Werkzeugaufrufe" zaehlte auch Dateiinhalte mit, die den Fehlersatz
    nur zitieren (gemessen an B173: vier gemeldet, eine echt).
    """
    zaehler: dict[str, dict] = {}
    for f in (fehler or []):
        name = str(f.get("name") or "?")
        e = zaehler.setdefault(name, {"name": name, "n": 0, "arten": []})
        e["n"] += 1
        art = str(f.get("art") or "fehler")
        if art not in e["arten"]:
            e["arten"].append(art)
    return sorted(zaehler.values(), key=lambda x: -x["n"])[:grenze]


def fehler_text(kurz: list[dict]) -> str:
    """Kurzform fuer Snapshot und Bilanz: 'mcp__ghidra__load_program×4 (gesperrt)'."""
    return "; ".join(f"{e['name']}×{e['n']} ({'/'.join(e['arten'])})"
                     for e in (kurz or [])) or "keine"


def _finish_run(cfg, state, res, stats, batch: int, profile_name: str, log, rebuilt: bool = False,
                mock: bool = False, ghidra_save: bool = True):
    """Messdaten, result.json, antwort.md und Snapshot schreiben (R11-2).

    Gemeinsam fuer den normalen Lauf und fuer das Nachrechnen aus einem
    Mitschnitt (`rebuild_from_stream`). Bei schreibenden Profilen wird hier auch
    die Ghidra-DB gespeichert (R13-1) - vor Push und Review.
    """
    rd = run_dir(cfg, batch)
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
    res.stats["tool_errors"] = _fehler_kurz(stats.tool_errors)
    # Punkt 2c: HTTP-Beruehrungen des gemeinsamen Ghidra-Zustands - nur Vermerk.
    res.stats["http_state"] = list(stats.http_state)[:5]
    res.stats["api_errors"] = list(stats.api_errors)[:5]
    res.stats["secret_hits"] = list(stats.secret_hits)[:10]
    res.stats["abbau"] = list(stats.abbau)[:5]
    res.stats["warteschleifen"] = list(stats.warteschleifen)[:5]
    res.stats["aufraeumen"] = res.aufraeumen or {}
    res.stats["vorgaenger"] = list(res.vorgaenger or [])
    # R13h: Laufzeit-Profil (Werkzeuge / Modell / Warten) - damit der Reviewer und der
    # Nutzer sehen, WOHIN die Zeit ging, statt nur wie lange es dauerte.
    res.stats["laufzeit"] = stats.laufzeit_profil()
    res.stats["num_turns"] = stats.num_turns()
    res.stats["total_cost_usd_field"] = stats.total_cost_usd_field()
    res.stats["tariff_now"] = pricing.tariff(None, extra_dates)
    res.stats["result_usage"] = stats.result_usage()
    # Auftrag 2026-09-29: die Kontextgroesse je Anfrage mitmessen (input + cache_read +
    # cache_creation) - als Zahl am Laufende, als Verlauf und als Kompaktierungshinweis.
    res.stats.update(stats.kontext_stats())
    # R13ad: Fortsetzungen im selben Chat (Minute, Kontext, Antwort des Workers).
    res.stats["fortsetzungen"] = list(res.fortsetzungen or [])
    # R13ah: der Preflight-Stand VOR der Fortsetzung (Beleg, s. `archiviere_preflight_…`).
    res.stats["preflight_archiv"] = res.preflight_archiv or ""
    res.stats["usage_check"] = stats.usage_check()
    res.stats["rebuilt"] = bool(rebuilt)
    res.stats["dauer"] = {"wanduhr_s": res.duration_s, "quelle": res.duration_quelle,
                          "harness_s": res.duration_harness_s, "claude_s": res.duration_cli_s,
                          "api_s": res.duration_api_s}
    if ghidra_save:
        res.ghidra_save = save_ghidra_after_batch(cfg, log, state, profile_name, mock=mock,
                                                  http_state=list(stats.http_state))
        if res.ghidra_save.get("needed") and res.ghidra_save.get("ok"):
            state.data["ghidra_pending"] = False
            state.save()
        res.stats["ghidra_save"] = res.ghidra_save

    # R13ao (Auftrag Teil B): wie oft lief der Preflight, und wie oft zu frueh?
    # Die Zahlen kommen aus `runs/b<N>/preflight-aufrufe.jsonl`, das der
    # PostToolUse-Hook je erkanntem Aufruf eine Zeile schreibt - nicht aus dem
    # Mitschnitt: ob die Nachrueckliste in DIESEM Moment offen war, steht nur dort.
    preflight_laeufe, preflight_frueh = zaehle_preflight_aufrufe(rd)

    payload = {
        "batch": batch, "profile": profile_name, "program": res.program,
        "rc": res.rc, "duration_s": res.duration_s, "killed_reason": res.killed_reason,
        "alarms": res.alarms, "stats": res.stats, "cost_usd": res.cost_usd,
        "secret_hits": list(stats.secret_hits)[:10],
        "warteschleifen": list(stats.warteschleifen)[:5],
        "aufraeumen": res.aufraeumen or {},
        "laufzeit": res.stats.get("laufzeit") or {},
        "cost_naive_usd": res.cost_naive_usd, "model_seen": res.model_seen,
        "model_ok": res.model_ok, "finished_at": now_iso(),
        "rebuilt": bool(rebuilt), "ghidra_save": res.ghidra_save,
        "duration_quelle": res.duration_quelle, "duration_cli_s": res.duration_cli_s,
        "duration_harness_s": res.duration_harness_s, "duration_api_s": res.duration_api_s,
        "preflight_laeufe": preflight_laeufe, "preflight_frueh": preflight_frueh,
    }
    # R13al: der bewusste Start trotz Peak (`/approve jetzt`) gehoert in die Messdaten -
    # sonst sieht spaeter niemand, warum dieser Lauf zum doppelten Tarif lief. Der Harness
    # setzt den Vermerk vor dem Start und nimmt ihn nach dem Lauf wieder heraus.
    peak_hinweis = str((getattr(state, "data", {}) or {}).get("peak_hinweis") or "")
    if peak_hinweis:
        payload["peak_hinweis"] = peak_hinweis
    write_json_atomic(rd / "result.json", payload)
    write_text_atomic(rd / "antwort.md", res.final_text)
    res.snapshot_path = write_snapshot(cfg, state, res, stats, log)
    return res


def rebuild_from_stream(cfg, log, state, batch: int):
    """Einen Lauf aus dem vorhandenen Mitschnitt nachrechnen (R11-2).

    Gedacht fuer den Fall, dass der Harness nach dem Worker-Ende stehen bleibt:
    Die Zahlen kommen dann aus `runs/b<N>/stream.jsonl` und `auftrag.md` selbst -
    nichts wird geschaetzt. Das Ergebnis wird als `rebuilt` gekennzeichnet.
    """
    rd = run_dir(cfg, batch)
    stream = rd / "stream.jsonl"
    zeilen = retention.mitschnitt_zeilen(stream)
    if zeilen is None:
        raise RuntimeError(f"kein Mitschnitt vorhanden: {stream} (auch nicht als .zip)")
    stats = streamjson.StreamStats()
    for line in zeilen:
        stats.feed(line)
    res = WorkerResult()
    res.run_dir = str(rd)
    res.stream_path = str(stream)
    res.profile = "unbekannt"
    auftrag = rd / "auftrag.md"
    if auftrag.is_file():
        for line in read_text(auftrag).splitlines()[:60]:
            if "ghidra-profil dieses laufs" in line.lower():
                res.profile = line.split(":", 1)[1].strip() or "unbekannt"
    res.rc = 0 if (stats.result or {}).get("subtype") == "success" else None
    res.killed_reason = "nachgerechnet (Harness stand nach dem Worker-Ende still)"
    # R13c: Laufzeit = Wanduhr des Worker-Prozesses. Der Mitschnitt traegt sie selbst
    # (`duration_ms`); `duration_api_ms` ist nur die API-Zeit und war zu klein.
    d_cli, d_feld = stats.duration_field()
    res.duration_cli_s = d_cli
    res.duration_quelle = "cli" if d_feld == "duration_ms" else ("api" if d_feld else "")
    res.duration_s = d_cli or 0.0
    v_api = (stats.result or {}).get("duration_api_ms")
    res.duration_api_s = round(float(v_api) / 1000.0, 3) if isinstance(v_api, (int, float)) else None
    if log:
        log.warn("Lauf aus dem Mitschnitt nachgerechnet", batch=batch, profil=res.profile,
                 laufzeit_s=res.duration_s, quelle=res.duration_quelle or "unbekannt")
    return _finish_run(cfg, state, res, stats, batch, res.profile, log, rebuilt=True,
                       ghidra_save=False)


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
- **Nie Prozesse nach Muster abräumen (R13i).** `Get-Process python | Where-Object { $_.CPU -gt 50 }
  | Stop-Process`, `Stop-Process -Name python`, `taskkill /IM python.exe` sind **verboten** — der
  Harness ist selbst ein `python.exe` und stirbt daran (in Batch 178 passiert, ohne jede Spur).
  Erlaubt ist nur ein **gezielter** Abbau: `Stop-Process -Id 1234` mit einer Nummer, die du selbst
  gestartet hast (`Start-Process … -PassThru` liefert sie), oder die Auswahl über die Kommandozeile
  (`Where-Object { $_.CommandLine -like "*deinmarker*" }`). Ein verbotener Befehl bricht den Batch ab.
- **Zugangsdaten sind tabu (R13g).** Die Schlüsseldateien des Aufbaus liegen AUSSERHALB
  dieses Repos. Sie zu lesen, aufzulisten, zu durchsuchen, zu kopieren, zu verändern oder
  in eine Ausgabe/Datei zu schreiben ist VERBOTEN — auch „nur zum Prüfen". Alles, was du
  brauchst, bekommst du als Umgebungsvariable. Ein Zugriffsversuch wird im Mitschnitt
  erkannt und als `SECRET-ZUGRIFF` alarmiert; er ist ein Befund im nächsten Review.
- Ghidra liegt am MCP-Server `ghidra` (Profil und Programm unten). Adressbasierte Aufrufe
  immer mit `program="<name>"` versehen.
  * Das aktuelle Programm stellt das HARNESS. Es ist normalerweise `main.bin` -
    das ist das PPC-Hauptprogramm (Base 0x80000000) und das Arbeitsprogramm.
  * `be.bin` ist das Boot-/Loader-Image; es ist NUR richtig, wenn der Auftrag
    ausdruecklich den Boot-/Ladepfad betrifft.
  * Brauchst du ein anderes Programm: NICHT selbst wechseln (kein
    `switch_program`, kein `load_program`, kein HTTP-Aufruf dafuer), sondern am
    Ende `<PROGRAM_REQUEST>/830d01.27p.<name>.bin</PROGRAM_REQUEST>` melden.
    Der naechste Batch bekommt es dann gestellt.
- Ein Programmwechsel, Ghidra-Skripte und der Debugger sind gesperrt (Sperrliste).
- Der HTTP-Weg auf 127.0.0.1:8089 ist ERLAUBT - auch schreibend. Er ist der
  dokumentierte Ausweichweg, wenn ein MCP-Werkzeug fehlt. Beachte: schreibende
  HTTP-Aufrufe auf den gemeinsamen Zustand (Programm oeffnen/wechseln/schliessen,
  restore_project, Skripte) werden im Review VERMERKT. Erlaubt ist er trotzdem.
  Fehlt dir ein MCP-Werkzeug, melde es zusaetzlich als
  `<TOOL_REQUEST>mcp__ghidra__<name></TOOL_REQUEST>` - statt zu raten.

ABLAUF
1. Auftrag lesen, dann Anker/Regeln lesen, dann arbeiten.
2. Den Auftrag vollständig abarbeiten — mehrere Teile in einem Zug, kein Mini-Schritt.
3. Stopp-Bedingungen des Auftrags beachten: ist etwas nicht belegbar, dokumentieren und
   mit dem nächsten Teil weitermachen statt abzubrechen.
4. Keine Rücknahme von Belegen: Analyse- und Belegdateien werden nicht gelöscht.

RECHENZEIT (R13v/R13ah, gemessen 2026-09-28 - bitte einhalten)
- **Lange Laeufe laufen SYNCHRON, nicht im Hintergrund.** Ohne eigenen `timeout`-Parameter
  kappt das Werkzeug bei **600 s** und schiebt den Befehl in den Hintergrund ("Command did
  not complete within its 600s timeout and was moved to the background"). Genau das fuehrte
  in B207 zu zwei Abfrageschleifen und **1084 s verlorener Wartezeit**, in B174 zu 1993 s,
  in B213/B214 zu Kappungen von Preflight und `mutalle`.
- **Der erlaubte Weg fuer alles, was laenger als ein paar Minuten dauert:**
  1. **Synchron mit ausdruecklicher Zeitgrenze:** beim Werkzeugaufruf `timeout`
     mitgeben (Millisekunden, **bis 1800000 = 30 min**). Das ist der Normalfall fuer
     `c_kopf.py prof`, `vergl alle`, `preflight.py`, `port_build.ps1`, Mutationslaeufe.
     Gemessen (R13ah): `timeout=600000` ist KEINE Erhoehung - das war schon die alte
     Obergrenze; wer mehr braucht, muss mehr setzen.
  2. **Nur wenn es laenger als 30 min dauern kann:** `Start-Process … -PassThru` und
     dann **EIN** `Wait-Process -Id $p.Id -Timeout 480` - und danach die Ausgabe
     lesen. Kein zweiter Wartebefehl, keine Schleife.
- **`Start-Sleep` ist GESPERRT** - nachgemessen am 2026-09-28 mit echtem Lauf: das
  Werkzeug lehnt `Start-Sleep` an JEDER Stelle ab (nackt, hinter `;`, in `if (…) { … }`,
  in der Schleife) und loest auch den Alias `sleep` auf (`docs/_r13v_sperrprobe.txt`).
  **Keine Abfrageschleife** (`for`/`while` mit `Start-Sleep` oder `Get-Process`): der
  Harness erkennt sie im Mitschnitt, meldet sie und **bricht den Lauf ab**, sobald 300 s
  Wartezeit zusammenkommen (`streamjson.warte_muster`). Das gilt auch fuer Formen, die
  die Sperre nicht faengt (`[Threading.Thread]::Sleep(2000)`).
- **Unabhaengige Rechenlaeufe parallel starten, nicht nacheinander.** Die Maschine hat
  4 Kerne; ein Lauf ueber alle IDs in EINEM Prozess ist fast immer schneller als viele
  Einzelaufrufe hintereinander (jeder zahlt das Laden erneut).
- Fortschritt pruefen statt warten: Dateigroesse/mtime oder Prozess-CPU-Delta
  (`(Get-Process -Id N).CPU`) in EINEM kurzen Aufruf, ohne Schleife.

ZEIT (R13ac/R13ad/R13ah - gemessen, nicht geschaetzt, EINE Quelle)
- Der Harness MISST die Batch-Zeit mit der Wanduhr des Worker-Prozesses. Nach jedem
  Werkzeugaufruf steht in deinem Kontext eine Zeile
  `BATCH-UHR (Harness-Messung): <m> min von <weich> min (Umschalten ab <u>) | Kontext <x>k von 1M | Preflight zuletzt ~<p> min (B<k>) …`.
  Sie ist die gueltige Grundlage fuer "wie lange laeuft dieser Batch schon".
- Die Zeile nennt auch die **Umschaltschwelle** und den **Kontext**. Die Schwelle ist
  `Alarmgrenze minus Vorlauf`, und der Vorlauf enthaelt die gemessene Dauer des letzten
  Preflight-Aufrufs (R13ah) - er laeuft am Batch-Ende und seine Zeit ist damit schon
  verplant. Nennt der Auftrag eine andere Minutenzahl ("Budget 80 min", "ab 70 min"),
  gilt die BATCH-UHR - der Reviewer schreibt seit R13ad keine eigene Zahl mehr.
- Die Zahl hinter `Preflight` traegt in Klammern den Batch, aus dem sie stammt
  (`(B213)`). Fehlt die Klammer, ist es der laufende Batch; steht dort ein **aelterer**
  Batch, hat der neueste den Preflight-Aufruf nicht allein gemessen (er lief neben
  einem anderen Aufruf, R13aj) - die Zahl ist dann die letzte saubere Messung.
- Die ZAHL DER WERKZEUGAUFRUFE sagt nichts ueber die Zeit. In B210 hielt sich der Worker
  nach Aufrufzaehlung fuer "~180 min" und strich deshalb Pflichtteile - gemessen waren
  es **46 min**. Die Startzeit dieses Laufs steht unten unter "UMFELD DIESES LAUFS".
- Restzeit also NUR so rechnen: `Get-Date` minus dieser Startzeit (oder die letzte
  BATCH-UHR-Zeile lesen). Eine Streichung von Pflichtteilen "aus Zeitgruenden" gilt nur
  mit einer unmittelbar davor gemessenen `Get-Date`-Zeile im Batch-Dokument.
- **Für `preflight.py`, `c_kopf.py mutalle` und `port_build` den Bash-Parameter
  `timeout=1800000` setzen; sonst wird nach 600 s gekappt.** (Die Obergrenze des
  Werkzeugs ist seit R13ah 1800 s, die Vorgabe ohne Parameter bleibt 600 s - Schutz
  gegen haengende Befehle.)
- Hoerst du vor der Umschaltschwelle auf, wird derselbe Chat **fortgesetzt**: die
  Fortsetzungsnachricht beginnt mit "Du bist weiterhin in Batch <N>. Alle Commits tragen
  B<N>:, nicht B<N+1>:." - die Batch-Nummer kommt aus dem Harness, nicht aus dem Text.
  Danach arbeitest du die offenen Posten der `NACHRUECKLISTE` des Auftrags ab (je Posten
  ein Commit mit Soll-Delta). Die STREICHREIHENFOLGE faellt erst ab der Umschaltschwelle
  und nur mit Uhrnachweis.

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

# R11-1: der Takt (Telegram-Abfrage + lokale Befehle) darf NICHT bei jeder Zeile
# laufen. B159 hatte 20.486 Zeilen - mit einem Langpoll je Zeile stand der Harness
# nach dem Worker-Ende minutenlang still. Ein Takt alle 2 s genuegt.
TICK_MIN_INTERVAL_S = 2.0

# R13q: wie oft die Live-Zahlen des laufenden Batches in den Zustand wandern.
# Anlass: `/status` soll Dauer und Kosten eines LAUFENDEN Batches zeigen, ohne den
# Mitschnitt zu lesen (`runs/b*/stream.jsonl` ist in b180 32 MB gross - und der
# Leser-Thread ist derselbe, der entscheiden soll, ob das Kind fertig ist).
LIVE_SEKUNDEN = 15.0


def build_prompt(cfg, instruction: str, queue_block: str, program: str | None, profile: str,
                 remote_hinweis: str = "",
                 start_zeit: datetime | None = None) -> str:
    """Vorspann + Auftrag + Queue. Der Worker bekommt KEINE Rückfragemöglichkeit.

    `start_zeit` (R13ac) ist der Harness-Zeitstempel unmittelbar vor dem Start des
    Laufs; er erscheint als **absolute Ortszeit** im Umfeld-Block, damit "Restzeit" ohne
    Zaehlung von Werkzeugaufrufen ausgerechnet werden kann. Ist er None (aeltere Aufrufer,
    Tests), fehlt die Zeile - es wird nichts erfunden.
    """
    parts = [WORKER_PREAMBLE]
    umfeld = [f"Ghidra-Profil dieses Laufs: {profile}"]
    if start_zeit is not None:
        umfeld.append(f"Batch-Start (Harness-Zeitstempel): "
                      f"{uhr.ortszeit(start_zeit)} Ortszeit am "
                      f"{start_zeit.astimezone().strftime('%Y-%m-%d')}")
        umfeld.append("  - Die exakte Messung ist die BATCH-UHR-Zeile im Verlauf "
                      "(Prozessstart des Workers); dieser Zeitstempel liegt wenige "
                      "Sekunden davor.")
    if program:
        umfeld.append(f"Aktuelles Ghidra-Programm (vom Harness gestellt): {program}")
        # Punkt 10d: der Worker hat mehrfach be.bin angefordert, obwohl PPC-Arbeit
        # auf main.bin laeuft. Die Bedeutung steht deshalb direkt daneben.
        umfeld.append("  - main.bin = PPC-Hauptprogramm (Base 0x80000000) - das Arbeitsprogramm.")
        umfeld.append("  - be.bin = Boot-/Loader-Image - nur bei Aufträgen zum Ladepfad.")
        umfeld.append("  - Ein anderes Programm NICHT selbst stellen: PROGRAM_REQUEST melden.")
    else:
        umfeld.append("Kein Ghidra-Programm gestellt (Profil ohne Ghidra-Zugriff).")
    parts += ["", "UMFELD DIESES LAUFS", *umfeld]
    # R13n: ist waehrend des Pulls Code von aussen dazugekommen, MUSS der Worker das
    # wissen - sonst arbeitet er auf einem Stand, der den Neubau noch nicht gesehen hat.
    if remote_hinweis:
        parts += ["", remote_hinweis.strip()]
    parts += ["", "=== AUFTRAG (vom Reviewer) ===", instruction.strip()]
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
        # R13p: der Mitschnitt kann gepackt sein (.zip) - retention liest beide Formen.
        for line in (retention.mitschnitt_zeilen(res.stream_path) or []):
            if '"thinking"' in line or '"redacted_thinking"' in line:
                reasoning.append(line)
    if reasoning:
        write_text_atomic(snap_dir / "reasoning.jsonl", "\n".join(reasoning) + "\n")

    t = res.stats
    body = f"""# Snapshot Batch {state.batch} (Worker)

## Harness-Kennzahlen
- Profil: {res.profile} | Programm: {res.program or '-'}
- Exit-Code: {res.rc} | Dauer: {res.dauer_text()} | Grenze ausgeloest: {res.killed_reason or 'nein'}
- Alarmmeldungen: {'; '.join(res.alarms) if res.alarms else 'keine'}
- Anfragen: {t.get('requests')} | Eingabe Miss: {t.get('input_miss')} | Cache-Hit: {t.get('cache_read')} \
| Cache-Neu: {t.get('cache_creation')} | Ausgabe: {t.get('output')}
- Kosten (gerechnet, Tarif je Aufruf): ${res.cost_usd:.4f} (Gegenprobe alles zum Jetzt-Tarif: ${res.cost_naive_usd:.4f})
- Tarif beim Abschluss: {t.get('tariff_now')}
- Modell laut Ausgabe: {res.model_seen} (Soll erfuellt: {res.model_ok})
- num_turns: {t.get('num_turns')} | total_cost_usd-Feld (nicht massgeblich): {t.get('total_cost_usd_field')}
- Abgelehnte Werkzeugaufrufe: {t.get('denials') or 'keine'}
- Werkzeugfehler: {fehler_text(t.get('tool_errors'))}

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
