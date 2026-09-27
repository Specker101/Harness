"""Hauptschleife (MVP P3): Batch-Ende -> Reviewer -> (Freigabe) -> neuer Worker.

Kein Watchdog in diesem Schritt (Entscheidung R4). Zustandsmaschine siehe
Abschnitt C des Plans; Zustellungen an den Worker/Reviewer nur an
Batch-Uebergaengen (E9).
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
import traceback
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import control, envs, pricing, protocol, queue, retention, reviewer as rv, secrets, state as st, streamjson, worker as wk
from . import ask as askmod
from . import bilanz as bilanzmod
from . import denken as denkenmod
from .gitsafe import Git
from .telegram import HELP, Telegram, TelegramError
from .util import ensure_dir, now_iso, read_json, read_text, secs_human, write_text_atomic

IDLE_SLEEP = 3.0


class Orchestrator:
    def __init__(self, cfg, log, mock: bool = False, state_file=None):
        self.cfg = cfg
        self.log = log
        self.mock = mock or bool(cfg.get("mock", "enabled", False))
        self.state = st.State(state_file or (Path(cfg.sub("state")) / "run.json"))
        self.git = Git(cfg, log)
        # Queue-Ordner ist <root>/inbox/... - deshalb die WURZEL uebergeben, nicht <root>/inbox.
        self.qroot = Path(cfg.root)
        self.tg: Telegram | None = None
        self.approved_gate: str | None = None
        self.stop_requested = False
        self.review_now = False
        self.ghidra_failed = False
        self.quit = False
        self._wip_done = False
        # R13o: Fragen laufen in EINER Warteschlange nacheinander. Ohne das koennten
        # zwei Aufrufe dieselbe Chat-Session gleichzeitig greifen.
        self._ask_running = False
        self._ask_queue: list[tuple[str, bool]] = []
        self._ask_lock = threading.Lock()
        self._notified: dict[str, float] = {}
        # Attrappen-Modus des Reviewers (Tests/Demo): "ok", "parser_error",
        # "ok_zweiter_versuch", "reviewer_crash", "modell_falsch", "limit".
        self.mock_reviewer_mode = str(cfg.get("mock", "reviewer_mode", "ok") or "ok")
        self._review_target: int | None = None
        self._review_dir: Path | None = None
        self._review_rotation = False
        self._review_handover = ""
        self._review_previous_raw = ""
        self._init_telegram()

    # --------------------------------------------------------------- Telegram
    def _init_telegram(self):
        try:
            token = secrets.load(self.cfg.secrets_dir, secrets.TELEGRAM)
        except secrets.SecretError:
            self.log.warn("Kein Telegram-Token gefunden - Bot ist aus")
            return
        allow = [str(x) for x in (self.cfg.get("telegram", "allowlist_user_ids", []) or [])]
        self.tg = Telegram(token, allow, int(self.cfg.get("telegram", "poll_timeout_s", 25)), log=self.log)
        try:
            me = self.tg.get_me()
            self.log.info("Telegram-Bot bereit", bot=me.get("username"), allowlist=len(allow))
        except TelegramError as exc:
            self.log.warn("Telegram getMe fehlgeschlagen", fehler=str(exc)[:120])

    def say(self, text: str, mono: bool = False):
        """Abschicken. `mono=True` (R13q) laesst Telegram den Text in Festbreitenschrift
        zeigen - die Bilanz braucht das, damit die Spalten untereinander stehen."""
        if self.tg:
            self.tg.send(text, mono=mono)

    # ------------------------------------------------------------------ Phase
    def phase(self, name: str | None, extra: str = "") -> None:
        """Was der Harness JETZT tut - sichtbar in /status und in watch (R11-4)."""
        self.state.data["phase"] = ({"name": name, "extra": extra, "since": now_iso()}
                                    if name else None)
        self.state.save()

    def phase_text(self) -> str:
        p = self.state.data.get("phase") or {}
        if not p:
            return "-"
        return str(p.get("name") or "-") + (f" ({p.get('extra')})" if p.get("extra") else "") \
            + f" seit {p.get('since')}"

    # ----------------------------------------------------- Reviewer-Modell (R11-5)
    def model_reviewer(self) -> str:
        return str(self.cfg.get("claude", "model_reviewer", "claude-opus-5-5"))

    def reviewer_effort(self) -> str:
        return str(self.cfg.get("claude", "reviewer_effort", "high"))

    def reviewer_model_seen(self) -> str | None:
        return (self.state.data.get("reviewer") or {}).get("model_seen")

    def ghidra_save_line(self, res: dict) -> str:
        """Eine Zeile fuer den Review: wurde die Ghidra-DB gespeichert? (R13-1/R13e)"""
        gs = (res or {}).get("ghidra_save") or {}
        if not gs:
            return "nicht noetig (keine Angabe im Lauf - altes Ergebnis)"
        grund = gs.get("grund") or ""
        if gs.get("needed") and gs.get("ok"):
            return "ja - " + str(gs.get("hinweis") or "") + (f" [{grund}]" if grund else "")
        if gs.get("needed"):
            art = "HALTEGRUND" if gs.get("blocking", True) else "nur Vermerk (nicht blockierend)"
            return "NEIN - " + str(gs.get("hinweis") or "") + f" [{art}]"
        return "nicht noetig - " + str(gs.get("hinweis") or "")

    def http_state_line(self, res: dict) -> str:
        """Punkt 2c: hat der Worker per HTTP den gemeinsamen Ghidra-Zustand beruehrt?

        Nur ein Vermerk - der HTTP-Weg ist erlaubt, und ein Leseprofil heisst nicht,
        dass nichts geschrieben wurde.
        """
        treffer = ((res or {}).get("stats") or {}).get("http_state") or []
        if not treffer:
            return "keine (kein HTTP-Aufruf mit Zustandswirkung im Mitschnitt)"
        return "; ".join(f"{t.get('endpoint')}" for t in treffer)

    def dauer_line(self, res: dict) -> str:
        """Laufzeit mit Herkunft (R13c): Wanduhr des Worker-Prozesses, nie eine nackte Zahl."""
        d = float((res or {}).get("duration_s") or 0)
        quelle = str((res or {}).get("duration_quelle") or "")
        basis = {
            "cli": "Wanduhr des Worker-Prozesses laut claude-Prozess",
            "wanduhr": "vom Harness gemessene Wanduhr (Prozess nennt keine Dauer)",
            "api": "NUR API-Zeit - keine Prozess-Wanduhr vorhanden",
        }.get(quelle, "Herkunft unbekannt (alter Lauf)")
        txt = f"{secs_human(d)} ({basis}"
        harness = (res or {}).get("duration_harness_s")
        if quelle == "cli" and isinstance(harness, (int, float)) and harness:
            rest = float(harness) - d
            if rest >= 120:
                txt += f"; zusaetzlich {secs_human(rest)} Harness-Nachlauf/Rueckstau"
        return txt + ")"

    def notify_once(self, key: str, text: str, cooldown_s: float = 900.0):
        last = self._notified.get(key, 0.0)
        if time.time() - last < cooldown_s:
            return
        self._notified[key] = time.time()
        self.say(text)

    # ------------------------------------------------------------------ Queue
    def read_queue_block(self, target: str, mark: bool = True) -> tuple[str, list[str]]:
        """Nachrichten fuer den naechsten Auftrag sammeln.

        R13b: `mark=False` liefert den Block, OHNE ihn als zugestellt zu verbuchen.
        Das tut erst `commit_queue` - und zwar erst, wenn der Review wirklich einen
        gueltigen Protokollblock geliefert hat. Sonst waere eine Nachricht weg, obwohl
        niemand sie je gesehen hat (B159: Review gescheitert, Nachricht in inbox/done).
        """
        delivered = list(self.state.data.get("delivered") or [])
        block, ids = queue.deliver_block(self.qroot, target, delivered)
        if mark and ids:
            self.commit_queue(target, ids)
        return block, ids

    def commit_queue(self, target: str, ids: list[str]) -> int:
        """Zugestellt = verbuchen UND archivieren (erst nach gueltigem Review)."""
        ids = [i for i in (ids or []) if i]
        if not ids:
            return 0
        for i in ids:
            self.state.mark_delivered(i)
        moved = queue.archive(self.qroot, ids, target)
        self.log.info("Queue zugestellt", ziel=target, anzahl=len(ids), archiviert=len(moved))
        return len(ids)

    # --------------------------------------------------- gemeinsame Aktionen
    # Von Telegram UND von der lokalen Steuerung (state/ctl/) benutzt.
    def _do_pause(self, note: str = "pausiert"):
        self.state.data["paused"] = True
        # R13e: eine ausdrueckliche Pause des Nutzers schlaegt den Limit-Wartezustand -
        # sonst wuerde der Harness eigenmaechtig weiterlaufen.
        self.state.data.pop("limit_wait_until", None)
        self.state.data.pop("limit_wait_quelle", None)
        try:
            pause = {"ts": now_iso(), "head": self.git.head(),
                     "head_short": self.git.head_short(),
                     "batch": int(self.state.batch or 0),
                     "dirty": self.git.status_porcelain()[:50]}
        except Exception as exc:
            pause = {"ts": now_iso(), "error": str(exc)[:200]}
        self.state.data["pause_since"] = pause
        self.state.set(st.PAUSED, note)
        self.log.info("PAUSIERT", grund=note)
        self.say("PAUSIERT (" + note + "). Ein laufender Batch laeuft zu Ende; nichts Neues startet.")

    def mark_harness_head(self, batch: int) -> None:
        """Merken, bis wohin der HARNESS selbst gearbeitet hat (R13e).

        Die Pausen-Erkennung vergleicht HEAD vor und nach der Pause. Laeuft beim
        Pausieren noch ein Batch, committet der WORKER waehrend der Pause - und
        der Review meldete das als "Arbeit in der Pause" des Nutzers (gemeldet
        fuer B161: die eigenen Batches 160/161). Nach jedem Batch-Ende wird der
        Stand hier festgehalten; `_do_resume` setzt den Ausgangspunkt darauf neu.
        """
        try:
            self.state.data["harness_head"] = {"head": self.git.head(),
                                               "head_short": self.git.head_short(),
                                               "batch": int(batch or 0),
                                               "ts": now_iso()}
        except Exception as exc:
            self.log.warn("harness_head nicht ermittelbar", fehler=str(exc)[:150])

    # Commit-Betreff der Projektkonvention: "B173: Vorhersage", "Batch 172: ..."
    _BATCH_COMMIT = re.compile(r"^(?:B\d+\b|Batch\s+\d+\b)", re.IGNORECASE)

    def _ist_harness_commit(self, zeile: str) -> bool:
        """'12d1198 2026-09-26 Batch 172: ...' gehoert zu einem Harness-Batch.

        R13n: Ein Commit, der per Pull vom Remote kam, ist IMMER Nutzerarbeit - auch
        wenn er nach Projektkonvention 'B172: ...' heisst. Entschieden wird das ueber
        den Hash, nicht ueber den Betreff.
        """
        kurz = str(zeile).split(" ", 1)[0]
        if kurz and kurz in self._remote_hashes():
            return False
        teile = str(zeile).split(" ", 2)
        subj = (teile[2] if len(teile) > 2 else str(zeile)).strip()
        return bool(self._BATCH_COMMIT.match(subj))

    def _do_resume(self, accept_dirty: bool = False, note: str = "fortgesetzt"):
        # R13j: NICHT fortsetzen, wenn schon ein Lauf in Arbeit ist. Am 2026-09-26 hat
        # ein `/resume` waehrend eines laufenden Batches den Zustand auf IDLE gesetzt -
        # der Batch lief weiter, aber `/status` zeigte "idle". Das ist keine Kleinigkeit:
        # der Zustand ist die einzige Auskunft, die der Nutzer hat.
        if self.state.data.get("worker") or self.state.state in (st.DS_WORKING, st.CLAUDE_REVIEWING):
            laeuft = "ein Worker" if self.state.state == st.DS_WORKING else "ein Review"
            self.say(f"Es laeuft bereits {laeuft} - /resume ist unnoetig und wuerde den Zustand "
                     "verfaelschen.\nWenn du danach anhalten willst: /pause (der Batch laeuft zu "
                     "Ende). Sofort abbrechen: /stop.")
            self.log.info("Resume ignoriert - ein Lauf ist bereits in Arbeit",
                          zustand=self.state.state)
            return
        pause = self.state.data.get("pause_since") or {}
        # R13n: beim Fortsetzen zuerst den Git-Stand klaeren. Ist NUR der Remote voraus
        # und der Baum sauber, wird er uebernommen. Eine ECHTE Abweichung (eigener Stand
        # voraus, divergiert, unsauberer Baum, gescheiterter Pull) haelt weiter an -
        # ein nicht pruefbarer git-Stand dagegen nicht: den faengt die Vorpruefung vor
        # dem naechsten Batch ohnehin ab, und `resume` soll daran nicht scheitern.
        gok, gwarum, gart = self.git_sync("Fortsetzen")
        if not gok and gart != "unpruefbar":
            self.state.data["paused"] = True
            self.state.set(st.PAUSED, gwarum)
            self.say("PAUSE: " + gwarum)
            self.log.info("Fortsetzen verweigert - Git-Stand nicht in Ordnung", grund=gwarum)
            return
        if not gok:
            self.log.warn("Git-Stand beim Fortsetzen nicht pruefbar", grund=gwarum)
            self.say("Hinweis: Git-Stand nicht pruefbar (" + gwarum + ")\n"
                     "Ich setze fort; die Vorpruefung vor dem naechsten Batch prueft erneut.")
        try:
            head_now = self.git.head_short()
            dirty_now = self.git.status_porcelain()
        except Exception as exc:
            head_now, dirty_now = "?", []
            self.say("Git nicht lesbar: " + str(exc)[:200])
        # R13e: hat der HARNESS waehrend der Pause noch einen Batch zu Ende
        # gebracht, ist dessen Commit keine Handarbeit - der Ausgangspunkt wird
        # dann auf den Harness-Stand neu gesetzt. Gefragt wird GIT (ist der
        # Pausen-HEAD ein Vorfahr des Harness-Stands?), nicht die Uhr: zwei
        # Zeitstempel in Sekundengenauigkeit sind dafuer zu grob.
        base = pause.get("head_short")
        hh = self.state.data.get("harness_head") or {}
        neu_gesetzt = ""
        hh_head = hh.get("head_short")
        if hh_head and ((base and self.git.is_ancestor(base, hh_head)) or not base):
            if hh_head != base:
                neu_gesetzt = (f" Ausgangspunkt neu gesetzt auf {hh_head} "
                               f"(Harness-Batch {hh.get('batch')} endete in der Pause).")
            base = hh_head
        moved = bool(base) and head_now != base
        if moved or dirty_now:
            commits: list[str] = []
            try:
                commits = self.git.log_since(base, 50) if base else []
            except Exception:
                commits = []
            hand = [c for c in commits if not self._ist_harness_commit(c)]
            har = [c for c in commits if self._ist_harness_commit(c)]
            if not hand and not dirty_now and har:
                # Nur Harness-Batches in der Pause: kein Hinweis an den Review.
                self.say(f"HEAD hat sich in der Pause bewegt ({base} -> {head_now}), aber nur "
                         f"durch Harness-Batches ({len(har)}) - das ist keine Handarbeit."
                         + neu_gesetzt)
            else:
                self.state.data["pause_work"] = {
                    "since": pause.get("ts"), "head_before": base,
                    "head_now": head_now, "moved": moved, "dirty": dirty_now[:50],
                    "commits_hand": hand, "commits_harness": har,
                }
                self.state.save()
                if dirty_now and not accept_dirty:
                    self.state.set(st.PAUSED, "Arbeitsbaum nicht sauber")
                    self.say("In der Pause wurde gearbeitet UND der Arbeitsbaum ist nicht sauber:\n  "
                             + "\n  ".join(dirty_now[:10])
                             + "\n\nIch starte nichts. Bitte committen - oder ausdruecklich bestaetigen "
                               "(`hx.cli resume --accept-dirty`, Telegram `/resume ok`).")
                    return
                self.say(f"In der Pause wurde gearbeitet (HEAD {base} -> {head_now}, "
                         f"{len(hand)} Handarbeit-Commit(s), {len(har)} Harness-Batch-Commit(s), "
                         f"{len(dirty_now)} Aenderungen). Der naechste Review bekommt einen "
                         "Hinweis samt git log/Diffstat." + neu_gesetzt)
        self.state.data["paused"] = False
        self.state.data["stopped"] = False
        self.stop_requested = False
        self.state.set(st.IDLE, note)
        self.log.info("FORTSETZUNG", grund=note)
        self.say("Weiter.")

    def _do_stop(self, note: str = "gestoppt"):
        self.state.data["stopped"] = True
        self.stop_requested = True
        self.state.set(st.STOPPED, note)
        self.say("Stop angefordert: WIP wird gesichert, dann wird der Prozess beendet.")

    def _do_number(self, rest: str) -> None:
        """Batch-Nummer fuer den offenen Auftrag festlegen (Anker-Abweichung korrigieren)."""
        gate = self.state.gate
        if not gate:
            self.say("Kein offener Auftrag - /number hat nichts zu aendern.")
            return
        wort = (rest or "").strip().split()[0] if (rest or "").strip() else ""
        if not wort.isdigit() or not (1 <= int(wort) <= 9999):
            self.say("Nutzung: /number <N>  (z. B. /number 159)")
            return
        n = int(wort)
        tools = dict(gate.get("tools") or {})
        alt = tools.get("batch")
        tools["batch"] = n
        tools["number_set_by_user"] = True
        gate["tools"] = tools
        self.state.save()
        self.log.info("Batch-Nummer gesetzt", alt=alt, neu=n)
        self.say(f"Batch-Nummer des offenen Auftrags: {alt} -> {n} (vom Nutzer). Mit /approve startet "
                 f"er; Run-Verzeichnis und Checkpoint-Tag tragen die Nummer {n}.")

    def _do_approve(self, text: str = ""):
        gate = self.state.gate
        if not gate:
            self.say("Kein Batch wartet auf Freigabe.")
            return
        if (text or "").strip():
            queue.enqueue(self.qroot, "ds", text.strip(), "freigabe")
        self.approved_gate = gate.get("id")
        self.state.set(st.IDLE, "freigegeben")
        self.say("Freigegeben. Der Batch startet.")

    def _take_user_instruction(self, obj: dict):
        """Eigene Instruktion des Nutzers als naechster Batch (am Reviewer vorbei)."""
        instr = str(obj.get("instruction") or "").strip()
        if not instr:
            self.say("Eigene Instruktion war leer - verworfen.")
            return
        profile = str(obj.get("profile") or "ghidra-read")
        program = obj.get("program") or self.cfg.get("ghidra", "program_default")
        if profile == "none":
            program = None
        batch_no = protocol.parse_batch_number(instr) or self.expected_batch()
        self.state.set_gate(st.new_review_id(), "(eigene Instruktion des Nutzers - ohne Review)",
                            instr, {"profile": profile, "program": program,
                                    "batch": batch_no, "source": "user"},
                            str(obj.get("source_file") or ""))
        self.log.info("Eigene Instruktion uebernommen", batch=batch_no, profil=profile,
                      quelle=obj.get("source_file") or "direkt")
        self.say(f"Eigene Instruktion uebernommen: Batch {batch_no}, Profil {profile}, "
                 f"Programm {program or '-'} (vom Nutzer). Sie startet ohne Review.")

    def check_local_control(self):
        """Liest die lokalen Steuerbefehle (state/ctl/) - funktioniert ohne Telegram."""
        try:
            txt = control.take(self.cfg, "pause")
            if txt is not None:
                self._do_pause("lokal pausiert")
            txt = control.take(self.cfg, "resume")
            if txt is not None:
                accept = (txt or "").strip().lower() in ("ok", "ja", "accept", "accept-dirty", "bestaetigt")
                self._do_resume(accept_dirty=accept, note="lokal fortgesetzt")
            txt = control.take(self.cfg, "stop")
            if txt is not None:
                self._do_stop("lokal gestoppt")
            txt = control.take(self.cfg, "approve")
            if txt is not None:
                self._do_approve(txt)
            txt = control.take(self.cfg, "number")
            if txt is not None:
                self._do_number(txt)
            obj = control.take_instruction(self.cfg)
            if obj:
                self._take_user_instruction(obj)
        except Exception as exc:
            self.log.warn("lokaler Steuerbefehl fehlgeschlagen", fehler=str(exc)[:200])

    # ------------------------------------------------------------------ /ask
    def _do_ask(self, frage: str = "", neu: bool = False) -> None:
        """Freie Frage an Claude - eigener Lauf im EIGENEN THREAD (R13f/R13o).

        Der Thread ist Pflicht, nicht Bequemlichkeit: laeuft ein Batch, wird
        `poll(fast=True)` aus dem Mitschnitt-Thread des Workers aufgerufen
        (`proc.run_stream` -> `on_event`). Ein blockierender Unterprozess dort
        wuerde den Mitschnitt anhalten und damit den Batch beeinflussen.

        R13o: Fragen laufen **strikt nacheinander** (`_ask_arbeiter`). Laeuft schon
        eine, wird die neue eingereiht statt abgelehnt - so kann nie ein zweiter
        Aufruf dieselbe Chat-Session gleichzeitig greifen.
        """
        frage = (frage or "").strip()
        if not frage:
            self.say("Nutzung: /ask <Frage>   (nacheinander, mit Chat-Gedaechtnis; "
                     "neuer Chat: /ask-neu <Frage>)")
            return
        with self._ask_lock:
            self._ask_queue.append((frage, bool(neu)))
            platz = len(self._ask_queue)
            laeuft = self._ask_running
            if not self._ask_running:
                self._ask_running = True
                threading.Thread(target=self._ask_arbeiter, daemon=True,
                                 name="hx-ask").start()
        if laeuft:
            self.say(f"Frage eingereiht (Platz {platz}). Ich melde sie der Reihe nach.")
        else:
            self.say("Frage laeuft (eigener Lauf, nur lesend: g:\\Harness + Decomp-Repo). "
                     "Der Betrieb hier laeuft weiter.")

    def _do_bilanz(self, rest: str = "") -> None:
        """`/bilanz [N]` - Aeste im Vergleich, Projektstand, Kosten (R13q).

        Rein lesend und schnell (kleine JSON-Dateien, kein Ghidra, kein Netz, kein
        Mitschnitt): die Antwort kann direkt aus dem Takt-Thread kommen. `N` ist der
        Vergleichsabstand in Batches (Vorgabe 1 = direkter Vorgaenger).
        """
        n = 1
        if rest.strip():
            wert = rest.strip().split()[0]
            if wert.isdigit():
                n = max(1, int(wert))
            else:
                self.say("Nutzung: /bilanz [N] - N = Vergleichsabstand in Batches "
                         "(Vorgabe 1).")
                return
        try:
            text = bilanzmod.bericht(self.cfg, n=n)
        except Exception as exc:                                # noqa: BLE001
            self.log.error("Bilanz fehlgeschlagen", fehler=str(exc)[:250])
            self.say("BILANZ FEHLGESCHLAGEN: " + str(exc)[:300])
            return
        # Monospace: die Spalten sollen untereinander stehen (Telegram-Tauglichkeit).
        self.say(text, mono=True)

    def thinking_pfad(self) -> tuple[Path | None, bool]:
        """Mitschnitt fuer /thinking: der LAUFENDE Batch, sonst der neueste (R13r).

        Rueckgabe (Pfad, laeuft). Der laufende Batch kennt seinen Pfad selbst - er steht
        als `log` im Worker-Eintrag (`worker.run_batch` -> `state.worker_started(pid,
        str(stream_path), session_id)`). Genau das will der Nutzer: LIVE mitlesen.
        Nur wenn kein Worker laeuft, wird der neueste `runs/b<N>` genommen.
        """
        w = self.state.data.get("worker") or {}
        log = str(w.get("log") or "")
        if log:
            p = retention.mitschnitt_vorhanden(log)
            if p:
                return p, True
        return denkenmod.neuester_mitschnitt(self.cfg), False

    def _do_thinking(self, rest: str = "") -> None:
        """`/thinking [N] [voll]` - die letzten Denkbloecke des DeepSeek-Workers (R13r).

        Rein lesend und ohne neuen Konfigurationsschluessel: der Tail-Leser in
        `denken` liest hoechstens 16 MB vom Dateiende, damit der TaktThread (hier laeuft
        der Befehl) nicht auf einen 32-MB-Lesvorgang wartet. Netz ist hier nicht im
        Spiel - R13k verbietet Netz im Mitschnitt-Leser, nicht lokale Lesevorgaenge.
        """
        n, voll, fehler = denkenmod.argumente(rest)
        if fehler:
            self.say("Nutzung: /thinking [N] [voll] - " + fehler + "\n"
                     "N = Anzahl der Denkbloecke (Vorgabe 10, hoechstens 50), "
                     "'voll' zeigt den ganzen Text (sonst je 200 Zeichen).")
            return
        pfad, laeuft = self.thinking_pfad()
        if pfad is None:
            self.say("Kein Mitschnitt gefunden - kein Batch gelaufen und kein "
                     "laufender Batch.")
            return
        try:
            erg = denkenmod.denkbloecke(
                pfad, n=n,
                grenze_zeichen=None if voll else denkenmod.GRENZE_ZEICHEN)
        except Exception as exc:                                # noqa: BLE001
            self.log.error("Denkbloecke fehlgeschlagen", fehler=str(exc)[:250])
            self.say("DENKEN FEHLGESCHLAGEN: " + str(exc)[:300])
            return
        self.say(denkenmod.beschreibe(erg, zusatz=self.thinking_zusatz(laeuft)),
                 mono=True)

    def thinking_zusatz(self, laeuft: bool) -> str:
        """Kopfzeilen-Zusatz: laeuft der Batch noch, mit Laufzeit und Anfragen (R13q)."""
        live = self.state.data.get("live") or {}
        teile: list[str] = []
        if laeuft:
            w = self.state.data.get("worker") or {}
            try:
                start = datetime.fromisoformat(str(w.get("started_at")).replace("Z", "+00:00"))
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                teile.append("laeuft seit " + secs_human(
                    (datetime.now(timezone.utc) - start).total_seconds()))
            except (TypeError, ValueError):
                teile.append("laeuft")
        else:
            teile.append("Batch beendet")
        if live:
            teile.append(f"{live.get('requests')} Anfragen, "
                         f"${float(live.get('cost_usd') or 0):.4f}")
        return " | ".join(teile)

    def _ask_arbeiter(self) -> None:
        """Die Warteschlange der Fragen abarbeiten - eine nach der anderen (R13o)."""
        while True:
            with self._ask_lock:
                if not self._ask_queue:
                    self._ask_running = False
                    return
                frage, neu = self._ask_queue.pop(0)
                rest = len(self._ask_queue)
            try:
                res = askmod.ask(self.cfg, self.log, frage, mock=self.mock, neu=neu)
                self.say(res.get("text") or "(keine Antwort)")
                if res.get("hinweis"):
                    self.say(res["hinweis"])
            except Exception as exc:                            # noqa: BLE001
                self.log.error("Frage fehlgeschlagen", fehler=str(exc)[:250])
                self.say("FRAGE FEHLGESCHLAGEN: " + str(exc)[:300])
            if rest:
                self.say(f"Naechste Frage laeuft ({rest} in der Warteschlange).")

    # ------------------------------------------------- Nutzerlimit des Abos (R13p)
    def rate_limit_text(self) -> str:
        """Was zuletzt gemessen wurde - mit Quelle und Zeitpunkt (leer, wenn nichts)."""
        d = streamjson.lies_rate_limit(self.cfg)
        if not d:
            return ""
        return (f"{streamjson.rate_limit_zeile(d.get('info') or {})} "
                f"[{(d.get('quelle') or '?')}, {d.get('ts') or '?'}]")

    def rate_limit_pruefen(self) -> str:
        """Bei >= 80 % Auslastung EINMAL je Fenster und Reset-Zeitpunkt warnen.

        Der Schluessel enthaelt den Reset-Zeitpunkt: nach dem Reset darf dieselbe
        Warnung wieder kommen, im selben Fenster aber nur einmal.
        """
        d = streamjson.lies_rate_limit(self.cfg)
        info = d.get("info") or {}
        text = streamjson.rate_limit_warnung(info)
        if not text:
            return ""
        key = "rate:" + (streamjson.rate_limit_schluessel(info) or "?")
        self.notify_once(key, text + f"\n(Quelle: {d.get('quelle') or '?'}, {d.get('ts')})",
                         6 * 3600)
        return text

    # --------------------------------------------- Aufbewahrung (R13p, einmal taeglich)
    def retention_tick(self) -> dict | None:
        """Alte Mitschnitte packen - NUR wenn kein Lauf arbeitet.

        Auftrag 2026-09-27: `stream.jsonl`/`reviewer.jsonl`/Snapshots aelter als 14 Tage
        als ZIP ablegen, einmal taeglich. Der Merker steht im Zustand und ueberlebt damit
        einen Neustart.
        """
        if self.state.data.get("worker") or self.state.state in (st.DS_WORKING,
                                                                 st.CLAUDE_REVIEWING):
            return None
        if not retention.faellig(self.cfg, self.state):
            return None
        res = retention.lauf(self.cfg, self.log, notify=self.say)
        retention.schreibe_bericht(self.cfg, res)
        self.state.data["retention"] = {"ts": res["ts"], "gezippt": res["gezippt"],
                                        "uebrig": res["uebrig"], "frei_gb": res["frei_gb"]}
        self.state.save()
        if res.get("warnung"):
            self.notify_once("platz", res["warnung"], 24 * 3600)
        return res

    # ------------------------------------------------------------------ Pollen
    def poll(self, fast: bool = False):
        """Lokale Befehle + Telegram abfragen.

        `fast=True` nimmt den KURZEN Telegram-Aufruf (kein Langpoll) - waehrend
        eines Worker-Batches wird der Takt oft aufgerufen, und ein 25-s-Langpoll
        je Zeile hat B159 zum Stehen gebracht (R11-1).
        """
        self.check_local_control()
        # Stop-Marker (stop.ps1) hat Vorrang vor allem - auch waehrend eines Batches.
        marker = Path(self.cfg.sub("state")) / "STOP"
        if marker.exists():
            try:
                marker.unlink()
            except OSError:
                pass
            self.log.info("STOP-Marker gefunden - breche ab")
            self.state.data["stopped"] = True
            self.stop_requested = True
            self.state.set(st.STOPPED, "Stop-Marker")
            self.say("Stop-Marker: WIP wird gesichert, dann beende ich den Batch.")
        # R13p: Abo-Auslastung pruefen - auch ohne Telegram (Log) und in jedem Takt.
        self.rate_limit_pruefen()
        if not self.tg:
            return
        offset = int(self.state.data.get("telegram_offset", 0))
        try:
            updates = self.tg.get_updates(offset, timeout=0 if fast else None)
        except TelegramError:
            return
        for u in updates:
            self.state.set_offset(int(u.get("update_id", 0)) + 1)
            msg = u.get("message") or {}
            frm = (msg.get("from") or {}).get("id")
            chat = (msg.get("chat") or {}).get("id")
            text = (msg.get("text") or "").strip()
            if not text:
                continue
            if not self.tg.is_allowed(frm):
                self.log.warn("Telegram: Nachricht von nicht freigegebener User-ID verworfen",
                              user_id=str(frm))
                continue
            self.tg.last_chat_id = str(chat or frm)
            self.handle_command(text)

    # --------------------------------------------------------------- Befehle
    def handle_command(self, text: str) -> bool:
        if not text.startswith("/"):
            self.say("Nur Befehle (/help). Deine Nachricht wurde NICHT als Befehl ausgefuehrt.\n" + HELP)
            return False
        head, _, rest = text.partition(" ")
        cmd = head.lower().lstrip("/").split("@")[0]
        rest = rest.strip()

        if cmd in ("help", "hilfe"):
            self.say(HELP)
        elif cmd == "start":
            self.say("Bot ist verbunden.\n\n" + self.status_text())
        elif cmd == "status":
            self.say(self.status_text())
        elif cmd == "budget":
            self.say(self.budget_text())
        elif cmd == "pause":
            self._do_pause("per Telegram pausiert")
        elif cmd == "resume":
            accept = rest.strip().lower() in ("ok", "ja", "accept", "accept-dirty", "bestaetigt")
            self._do_resume(accept_dirty=accept, note="per Telegram fortgesetzt")
        elif cmd == "stop":
            self._do_stop("per Telegram gestoppt")
        elif cmd == "ds":
            if not rest:
                self.say("Nutzung: /ds <Text>")
            else:
                p = queue.enqueue(self.qroot, "ds", rest, "telegram")
                self.say(f"In die Queue gelegt ({p.name}). Wird am naechsten Batch-Uebergang zugestellt.")
        elif cmd == "claude":
            if not rest:
                self.say("Nutzung: /claude <Text>")
            else:
                p = queue.enqueue(self.qroot, "claude", rest, "telegram")
                self.say(f"In die Queue gelegt ({p.name}). Wird beim naechsten Review zugestellt.")
        elif cmd == "ask":
            self._do_ask(rest)
        elif cmd in ("ask-neu", "ask_neu", "askneu"):
            self._do_ask(rest, neu=True)
        elif cmd == "bilanz":
            self._do_bilanz(rest)
        elif cmd in ("thinking", "denken"):
            self._do_thinking(rest)
        elif cmd == "approve":
            self._do_approve(rest)
        elif cmd == "autonom":
            val = rest.lower()
            new = not bool(self.state.data.get("autonomous"))
            if val in ("on", "an", "1", "true"):
                new = True
            elif val in ("off", "aus", "0", "false"):
                new = False
            self.state.data["autonomous"] = new
            self.state.save()
            self.say("Dauerbetrieb: " + ("AN" if new else "AUS"))
        elif cmd == "review":
            self.review_now = True
            self.state.data["paused"] = False
            self.state.save()
            self.say("Review angefordert" + ("; ein offener Auftrag wird dabei verworfen."
                                             if self.state.gate else ".") +
                     " Die Pause ist dafuer aufgehoben.")
        elif cmd == "number":
            self._do_number(rest)
        elif cmd == "last":
            self.send_last(rest)
        elif cmd == "queue":
            ds = queue.pending(self.qroot, "ds")
            cl = queue.pending(self.qroot, "claude")
            lines = [f"Queue ds: {len(ds)}, claude: {len(cl)}"]
            for it in (ds + cl)[-10:]:
                lines.append("- " + it.render()[:200])
            self.say("\n".join(lines))
        elif cmd == "why":
            rev = self.state.data.get("reviewer") or {}
            gate = self.state.gate
            txt = [f"Letzte Entscheidung: {rev.get('last_decision') or '-'}",
                   f"Reviews in dieser Session: {rev.get('reviews')}",
                   f"Session: {rev.get('session_id')}"]
            if gate:
                txt += ["", "Letzte Zusammenfassung:", gate.get("summary", "")[:1200]]
            self.say("\n".join(txt))
        else:
            self.say(f"Unbekannter Befehl: /{cmd}\n\n" + HELP)
            return False
        return True

    def send_last(self, rest: str):
        parts = rest.split()
        which = "claude"
        n = 40
        for p in parts:
            if p in ("ds", "claude"):
                which = p
            elif p.isdigit():
                n = int(p)
        if which == "ds":
            dirs = sorted((Path(self.cfg.sub("runs"))).glob("b*"))
            if not dirs:
                self.say("Noch kein Worker-Lauf.")
                return
            ans = read_text(dirs[-1] / "antwort.md")
            self.say(ans[-n * 120:] if ans else "(leer)")
        else:
            gate = self.state.gate
            if gate and gate.get("instruction"):
                self.say(f"Letzte Instruktion (vollstaendig, Batch "
                         f"{(gate.get('tools') or {}).get('batch')}) - offener Auftrag:\n"
                         + str(gate["instruction"]))
                return
            cands = sorted(Path(self.cfg.sub("runs")).glob("b*/review*.md"),
                           key=lambda p: p.stat().st_mtime, reverse=True)
            for path in cands:
                r = protocol.parse_review(read_text(path))
                if r.instruction:
                    self.say(f"Letzte Instruktion (vollstaendig, aus {path.parent.name}/"
                             f"{path.name}):\n" + r.instruction)
                    return
            self.say("Noch keine Instruktion vorhanden.")

    # ------------------------------------------------------------------ Texte
    @staticmethod
    def _lokale_zeit(iso: str | None) -> str:
        """`15:11` aus einem ISO-Zeitstempel (nichts, wenn er fehlt/kaputt ist)."""
        try:
            dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone().strftime("%H:%M")
        except (TypeError, ValueError):
            return ""

    def live_batch_zeile(self) -> str:
        """Dauer und Kosten des laufenden Batches - ohne den Mitschnitt zu lesen (R13q).

        Quelle sind die LIVE-Zahlen, die `worker.run_batch` gedrosselt (alle 15 s) in
        den Zustand schreibt (`state.data["live"]`). `runs/b*/stream.jsonl` wird
        ausdruecklich NICHT angefasst: der Mitschnitt ist bis zu 32 MB gross (b180),
        und /status muss sofort antworten. Nach dem Lauf bleibt der letzte Stand als
        `state.data["live_letzte"]` stehen.
        """
        live = self.state.data.get("live") or {}
        if live:
            w = self.state.data.get("worker") or {}
            dauer = ""
            try:
                start = datetime.fromisoformat(str(w.get("started_at")).replace("Z", "+00:00"))
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                dauer = "seit " + secs_human(
                    (datetime.now(timezone.utc) - start).total_seconds()) + " "
            except (TypeError, ValueError):
                pass
            stand = self._lokale_zeit(live.get("ts"))
            return (f"Laufender Batch {live.get('batch')}: {dauer}| "
                    f"{live.get('requests')} Anfragen | "
                    f"${float(live.get('cost_usd') or 0):.4f} | "
                    f"({live.get('input_miss')} ein / {live.get('cache_read')} cache / "
                    f"{live.get('output')} aus)"
                    + (f" | Stand {stand}" if stand else ""))
        letzte = self.state.data.get("live_letzte") or {}
        if letzte:
            stand = self._lokale_zeit(letzte.get("ts"))
            return (f"Laufender Batch: keiner (letzter Batch {letzte.get('batch')}: "
                    f"{letzte.get('requests')} Anfragen, "
                    f"${float(letzte.get('cost_usd') or 0):.4f}"
                    + (f", Stand {stand}" if stand else "") + ")")
        return "Laufender Batch: keiner (noch keine Live-Zahlen)"

    def status_text(self) -> str:
        s = self.state
        rev = s.data.get("reviewer") or {}
        today = datetime.now(timezone.utc).date().isoformat()
        lines = [
            f"Zustand: {s.state}",
            f"Batch: {self.expected_batch() or '?'} faellig | zuletzt gelaufen: "
            f"{s.data.get('last_batch_number') or 'keiner'} | {self.batch_number_line()}",
            f"Dauerbetrieb: {'AN' if s.data.get('autonomous') else 'AUS'}",
            f"Worker: {'PID ' + str(s.live_worker_pid()) if s.live_worker_pid() else 'laeuft nicht'}",
            self.live_batch_zeile(),
            f"Reviewer-Session: {rev.get('session_id')} ({rev.get('reviews')}/{self.cfg.get('reviewer','rotation_after',10)} Reviews)"
            + (" - Wechsel beim naechsten Review erzwungen" if rev.get("force_rotate") else ""),
            (f"Reviewer-Modell: {self.reviewer_model_seen() or '-'} (Soll {self.model_reviewer()}, "
             f"Effort {self.reviewer_effort()})"),
            f"Phase: {self.phase_text()}",
            f"Letzte Entscheidung: {rev.get('last_decision') or '-'}",
        ]
        gate = s.gate
        if gate:
            quelle = (gate.get("tools") or {}).get("source") or "reviewer"
            lines.append(f"Gate offen seit {gate.get('created_at')} - Instruktion: "
                         f"{'VOM NUTZER' if quelle == 'user' else 'vom Reviewer'}")
            if self.gate_wait_decision(gate):
                lines.append("Dieses Gate braucht eine ENTSCHEIDUNG - im Dauerbetrieb wird "
                             "es NICHT automatisch freigegeben.")
        else:
            lines.append("Gate: keins")
        for zeile in self.offene_punkte_zeilen():
            lines.append(zeile)
        if s.data.get("pause_since"):
            lines.append(f"Pause seit: {s.data['pause_since'].get('ts')} "
                         f"(HEAD {s.data['pause_since'].get('head_short')})")
        if s.data.get("limit_wait_until"):
            # R13e: der Limit-Wartezustand endet von selbst - das muss sichtbar sein.
            lines.append(f"Limit-Wartezustand bis: {s.data['limit_wait_until']} "
                         f"({s.data.get('limit_wait_quelle') or '-'}) - setzt von selbst fort")
        if s.data.get("pause_work"):
            lines.append("In der Pause wurde gearbeitet - der naechste Review bekommt den Hinweis.")
        if s.data.get("remote_work"):
            rw = s.data["remote_work"]
            lines.append(f"Vom Remote uebernommen: {len(rw.get('commits') or [])} Commit(s) "
                         f"({rw.get('ts')}, gilt als Nutzerarbeit) - Review und Worker sind "
                         "informiert (R367: Neubau + volle Regression).")
        rl = self.rate_limit_text()
        if rl:
            lines.append("Nutzerlimit (Abo): " + rl)
        else:
            lines.append("Nutzerlimit (Abo): noch nicht gemessen "
                         "(kommt aus Review, Uebergabe und /ask)")
        rt = retention.bericht(self.cfg)
        if rt:
            lines.append("Aufbewahrung (14 Tage -> ZIP): " + rt)
        lokal = control.pending(self.cfg)
        if lokal:
            lines.append("Lokale Befehle warten: " + ", ".join(lokal))
        pid = control.read_pid(self.cfg)
        laeuft = control.runner_alive(self.cfg)
        if laeuft:
            lines.append(f"Harness-Prozess: {pid} (laeuft)")
        else:
            lines.append(f"Harness-Prozess: {pid or 'keiner'} - HARNESS LAEUFT NICHT")
        crash = self.letzter_crash_bericht()
        if crash:
            try:
                ts = datetime.fromtimestamp(crash.stat().st_mtime, timezone.utc).isoformat()
            except OSError:
                ts = "?"
            lines.append(f"Letzter Crash-Bericht: {crash.name} ({ts})")
        lines.append(f"Kosten heute: ${s.spent_today(today):.4f} von "
                     f"${float(self.cfg.get('limits', 'daily_budget_usd', 10)):.2f}")
        lines.append(pricing.status_line(self.cfg))
        ds = queue.pending(self.qroot, "ds")
        cl = queue.pending(self.qroot, "claude")
        lines.append(f"Queue: ds {len(ds)}, claude {len(cl)}")
        try:
            d = self.git.divergence()
            lines.append(f"Git: {self.git.head_short()} (origin {'gleich' if d.get('same') else 'ABWEICHEND'})")
            st_lines = self.git.status_porcelain()
            lines.append(f"Arbeitsbaum: {'sauber' if not st_lines else str(len(st_lines)) + ' Aenderungen'}")
        except Exception as exc:
            lines.append(f"Git: Fehler {str(exc)[:80]}")
        if s.data.get("note"):
            lines.append(f"Hinweis: {s.data['note']}")
        return "\n".join(lines)

    def budget_text(self) -> str:
        s = self.state
        today = datetime.now(timezone.utc).date().isoformat()
        lim = self.cfg.section("limits")
        return "\n".join([
            f"Kosten heute: ${s.spent_today(today):.4f} / ${float(lim.get('daily_budget_usd', 10)):.2f}",
            f"Batch-Alarm: {lim.get('alarm_wall_s')}s / {lim.get('alarm_requests')} Anfragen / ${lim.get('alarm_cost_usd')}",
            f"Batch-Hart:  {lim.get('hard_wall_s')}s / {lim.get('hard_requests')} Anfragen / ${lim.get('hard_cost_usd')}",
            pricing.status_line(self.cfg),
            "Hinweis: --max-budget-usd wird NICHT verwendet (falsche Rechenbasis).",
        ])

    # ------------------------------------------------------------------ Git
    def git_sync(self, anlass: str) -> tuple[bool, str, str]:
        """Git-Vorpruefung + schneller Vorlauf, wenn NUR der Remote voraus ist (R13N).

        Nutzerwunsch 2026-09-27: liegt `origin/<branch>` vorne und ist der lokale HEAD
        ein Vorfahre davon (also nichts Eigenes ungepusht), wird der Stand automatisch
        uebernommen - dann arbeitet der Harness auf derselben Basis wie der andere
        Rechner. Alles andere haelt weiter an:
          * eigener Stand voraus (ahead > 0): "weicht ab", kein Merge,
          * BEIDE Seiten (ahead + behind): "DIVERGIERT", kein Merge,
          * unsauberer Arbeitsbaum: kein Pull.
        Die uebernommenen Commits werden als NUTZERARBEIT gefuehrt (R13n) - nicht ueber
        den Commit-Titel, sondern ueber ihren Hash.

        Rueckgabe: (ok, Meldung, Art). Die Art trennt "echte Abweichung" von
        "nicht pruefbar": beim Fortsetzen haelt nur eine echte Abweichung an, ein
        kaputter/ferner git-Stand wird dort nur gemeldet (die Vorpruefung vor dem
        Batch entscheidet spaeter endgueltig).
        """
        ok, err = self.git.fetch()
        if not ok:
            return False, f"git fetch fehlgeschlagen: {err}", "unpruefbar"
        d = self.git.divergence()
        if not d.get("ok"):
            return False, f"Git-Divergenz nicht pruefbar: {d.get('error')}", "unpruefbar"
        if d.get("same"):
            return True, "", "ok"
        lokal = str(d.get("local"))[:8]
        remote = str(d.get("remote"))[:8]
        ahead = int(d.get("ahead") or 0)
        behind = int(d.get("behind") or 0)
        if ahead and behind:
            return (False, f"origin/{self.git.branch} DIVERGIERT (lokal {lokal}, origin "
                           f"{remote}, ahead {ahead}, behind {behind}) "
                           "- kein Merge durch das Harness", "abweichung")
        if ahead:
            return (False, f"origin/{self.git.branch} weicht ab (lokal {lokal}, origin "
                           f"{remote}, ahead {ahead}, behind {behind}) "
                           "- kein Merge durch das Harness", "abweichung")
        # Ab hier: nur der Remote ist voraus. Voraussetzungen fuer den Vorlauf pruefen.
        dirty = self.git.status_porcelain()
        if dirty:
            return (False, f"origin/{self.git.branch} ist {behind} Commit(s) voraus, aber der "
                           f"Arbeitsbaum ist nicht sauber ({len(dirty)} Aenderungen) "
                           "- kein Pull, kein Merge durch das Harness", "unsauber")
        if not self.git.is_ancestor(str(d.get("local")), f"{self.git.remote}/{self.git.branch}"):
            return (False, f"origin/{self.git.branch} ist {behind} Commit(s) voraus, aber kein "
                           "Vorfahre von HEAD - kein Pull durch das Harness", "abweichung")
        ok, text = self.git.pull_ff_only()
        if not ok:
            return False, f"git pull --ff-only fehlgeschlagen: {text}", "pull-fehler"
        commits = self.git.commits_between(str(d.get("local")), "HEAD", 20)
        self._merke_remote_work(anlass, str(d.get("local")), commits)
        nach = self.git.head_short()
        self.log.info("Remote-Stand uebernommen", anlass=anlass, commits=len(commits),
                      von=lokal, nach=nach)
        self.say(f"Stand vom Remote uebernommen: {len(commits)} Commit(s) "
                 f"({lokal} -> {nach})\n  "
                 + ("\n  ".join(commits[:10]) or "(keine Einzelcommits gemeldet)")
                 + "\nSie gelten als Nutzerarbeit (Hinweis geht an den naechsten Review).\n"
                   "R367: der naechste Batch baut neu und faehrt EINE volle Regression.")
        return True, "", "geholt"

    def git_preflight(self) -> tuple[bool, str]:
        """Vor jedem Batch: fetch + (falls nur der Remote voraus ist) schneller Vorlauf."""
        ok, meldung, _art = self.git_sync("Batch-Vorpruefung")
        return ok, meldung

    # ------------------------------------------------- Nutzerarbeit vom Remote
    def _merke_remote_work(self, anlass: str, von: str, commits: list[str]) -> None:
        """Uebernommene Commits als Nutzerarbeit festhalten (R13n)."""
        hashes = [str(c).split(" ", 1)[0] for c in commits if str(c).strip()]
        self.state.data["remote_work"] = {
            "ts": now_iso(), "anlass": anlass, "von": str(von),
            "nach": self.git.head_short(), "commits": list(commits), "hashes": hashes}
        self.state.save()

    def _remote_work(self) -> dict:
        return self.state.data.get("remote_work") or {}

    def _remote_hashes(self) -> set[str]:
        return {str(h) for h in (self._remote_work().get("hashes") or [])}

    def remote_work_zeile(self, batch: int | None = None) -> str:
        """Eine Zeile fuer den Messdatenblock des Reviews (R13n)."""
        rw = self._remote_work()
        if not rw:
            return "nichts uebernommen (origin unveraendert)"
        n = len(rw.get("commits") or [])
        return (f"{n} Commit(s) am {rw.get('ts')} uebernommen "
                f"({str(rw.get('von') or '?')[:8]} -> {rw.get('nach')}, {rw.get('anlass')}) "
                "- gilt als NUTZERARBEIT; R367: Neubau + EINMALIGE volle Regression "
                "zu Batch-Beginn wurde dem Worker aufgetragen")

    def remote_work_hinweis(self) -> str:
        """Auftrag an den naechsten Worker, wenn Code von aussen dazukam (R13n)."""
        rw = self._remote_work()
        if not rw:
            return ""
        commits = list(rw.get("commits") or [])
        zeilen = [
            "=== REMOTE-STAND UEBERNOMMEN (R367 GILT) ===",
            f"Vor diesem Batch wurden {len(commits)} Commit(s) von "
            f"{self.git.remote}/{self.git.branch} uebernommen "
            f"({str(rw.get('von') or '?')[:8]} -> {rw.get('nach')}). Diese Arbeit stammt vom "
            "anderen Rechner und gilt als NUTZERARBEIT - nicht als deine und nicht als die "
            "des Reviewers.",
            "Deshalb gilt R367: NEUBAU inkl. einmaliger voller Regression zu Batch-Beginn - "
            "baue ZUERST neu und fahre EINE vollstaendige Regression, BEVOR du etwas aenderst:",
            r"  1) & .\scripts\port_build.ps1          (PoC + Port)",
            r"  2) & .\scripts\port_build.ps1 -Gl      (GL-Senke; die baut der Standardlauf nicht)",
            "  3) python scripts/port_regression.py   (volle Regression, EINMAL zu Batch-Beginn)",
            "Melde die drei Ergebnisse im Bericht. Wiederhole die volle Regression NICHT bei "
            "jedem Zwischenschritt.",
        ]
        for c in commits[:10]:
            zeilen.append("  * " + c)
        return "\n".join(zeilen)

    def git_push(self) -> tuple[bool, str]:
        if not self.cfg.get("git", "push_after_batch", True):
            return True, "Push laut Konfiguration aus"
        return self.git.push()

    # ---------------------------------------------------------------- Grenzen
    def daily_budget_left(self) -> float:
        today = datetime.now(timezone.utc).date().isoformat()
        return float(self.cfg.get("limits", "daily_budget_usd", 10)) - self.state.spent_today(today)

    # ------------------------------------------------------- Limit-Wartezustand
    def limit_wait_ziel(self, meldung: str) -> tuple[datetime, str]:
        """Bis wann im Limit-Wartezustand gewartet wird (R13e).

        Zeitpunkt aus der Meldung (protocol.parse_limit_reset), sonst eine Stunde
        - und dann stuendlich neu pruefen. Das Ziel steht im Zustand, damit es
        einen Harness-Neustart ueberlebt.
        """
        wann = protocol.parse_limit_reset(meldung or "")
        jetzt = datetime.now(timezone.utc)
        if wann is not None and wann > jetzt:
            return wann, "Zeitpunkt aus der Meldung"
        return jetzt + timedelta(hours=1), "kein Zeitpunkt in der Meldung - stuendliche Pruefung"

    def limit_wait_tick(self) -> bool:
        """Limit-Wartezustand abgelaufen? Dann von selbst fortsetzen (R13e).

        Vorher wartete der Harness nach "Pro-Limit erreicht" auf /resume; im
        Dauerbetrieb stand er damit bis zum Morgen. Jetzt setzt er sich selbst
        fort und sagt es per Telegram. Greift nur im Zustand LIMIT_WAIT - eine
        Pause des Nutzers wird nicht eigenmaechtig aufgehoben.
        """
        if self.state.state != st.LIMIT_WAIT:
            return False
        ziel = self.state.data.get("limit_wait_until")
        if not ziel:
            return False
        try:
            faellig = datetime.fromisoformat(str(ziel))
        except ValueError:
            return False
        if faellig.tzinfo is None:
            faellig = faellig.replace(tzinfo=timezone.utc)
        jetzt = datetime.now(timezone.utc)
        if jetzt < faellig:
            rest = int((faellig - jetzt).total_seconds() // 60) + 1
            self.notify_once("limit_wait",
                             f"Pro-Limit: ich warte noch etwa {rest} min "
                             f"(bis {faellig.isoformat(timespec='minutes')}, "
                             f"{self.state.data.get('limit_wait_quelle') or '-'}).", 1800)
            return False
        self.state.data.pop("limit_wait_until", None)
        self.state.data.pop("limit_wait_quelle", None)
        self.state.data["paused"] = False
        self.state.set(st.IDLE, "Limit abgelaufen - setzt von selbst fort")
        self.log.info("Limit-Wartezustand abgelaufen - Fortsetzung")
        self.say("Das Reviewer-Limit ist abgelaufen - ich setze von selbst fort.")
        return True

    def peak_gate(self) -> tuple[bool, str]:
        if not self.cfg.get("peak", "block_new_batches", True):
            return True, ""
        extra = list(self.cfg.get("peak", "extra_offpeak_dates", []) or [])
        if not pricing.is_peak(None, extra):
            return True, ""
        nxt = pricing.next_offpeak(None, extra)
        return False, (f"Peak-Tarif aktiv ({pricing.local_window_text()}). Kein NEUER Batch; "
                       f"naechster Off-Peak: {nxt.strftime('%Y-%m-%d %H:%M')} UTC "
                       f"({secs_human((nxt - datetime.now(timezone.utc)).total_seconds())})")

    # --------------------------------------------------------------- Ausfuehren
    def cancel_check(self) -> bool:
        if not (self.stop_requested or self.state.data.get("stopped")):
            return False
        if not self._wip_done:
            self._wip_done = True
            self.save_ghidra_if_pending("Stopp")
            info = self.git.wip_rescue(self.state.batch, Path(self.cfg.sub("logs")))
            if info.get("dirty"):
                self.say(f"STOP: WIP gesichert ({len(info['status'])} Aenderungen"
                         + (f", Patch {Path(info['patch']).name}" if info.get('patch') else "")
                         + (f", {info['stash']}" if info.get('stash') else "") + ")")
            else:
                self.say("STOP: Arbeitsbaum war sauber.")
        return True

    # ------------------------------------------------------- Ghidra-Speichern (R13-1)
    def save_ghidra_if_pending(self, reason: str) -> bool:
        """Nur speichern, wenn ein schreibender Batch lief und noch nicht gespeichert ist."""
        if not self.state.data.get("ghidra_pending"):
            self.log.info("Ghidra-Speichern nicht noetig", grund=reason)
            return True
        prof = str(self.state.data.get("last_profile") or "")
        res = wk.save_ghidra_after_batch(self.cfg, self.log, self.state, prof, mock=self.mock)
        if res.get("ok"):
            self.state.data["ghidra_pending"] = False
            self.state.save()
            self.log.info("Ghidra gespeichert", grund=reason, hinweis=res.get("hinweis"))
            return True
        self.log.error("Ghidra NICHT gespeichert", grund=reason, hinweis=res.get("hinweis"))
        if not res.get("blocking", True):
            self.say(f"Hinweis: Ghidra-Speichern fehlgeschlagen ({reason}): "
                     f"{res.get('hinweis')}\n"
                     "Kein Haltegrund - das Profil liest nur und es wurde nichts per HTTP "
                     "mit Zustandswirkung bemerkt.")
            return True
        self.say(f"GHIDRA NICHT GESPEICHERT ({reason}): {res.get('hinweis')}")
        return False

    def run_worker(self, instruction: str, profile: str, program: str | None, queue_block: str) -> wk.WorkerResult:
        self.state.set(st.DS_WORKING, f"Profil {profile}")
        self.phase("worker", f"Batch {self.state.batch}, Profil {profile}")
        # R13n: wurde vor diesem Batch Remote-Code uebernommen, MUSS der Worker das
        # wissen - samt R367 (Neubau + EINE volle Regression zu Batch-Beginn).
        res = wk.run_batch(self.cfg, self.log, self.state, instruction, profile, program,
                           queue_block=queue_block, notify=self.say,
                           tick=lambda: self.poll(fast=True), cancel=self.cancel_check,
                           mock=self.mock, remote_hinweis=self.remote_work_hinweis())
        self.state.worker_finished()
        self.state.data["last_profile"] = profile
        gs = res.ghidra_save or {}
        if gs.get("needed") and not gs.get("ok") and gs.get("blocking", True):
            # R13-1: ohne Speichern waere der Git-Commit weiter als die Ghidra-DB.
            self.ghidra_failed = True
            self.state.data["paused"] = True
            self.state.set(st.PAUSED, "Ghidra-Speichern fehlgeschlagen")
        elif gs.get("needed") and not gs.get("ok"):
            # R13e: Leseprofil ohne bemerkte HTTP-Schreibzugriffe - melden, nicht anhalten.
            self.log.warn("Ghidra-Speichern fehlgeschlagen (nicht blockierend)",
                          hinweis=str(gs.get("hinweis"))[:200])
            self.say("Hinweis: Ghidra-Speichern nach dem Batch fehlgeschlagen ("
                     f"{gs.get('grund') or '-'}): {str(gs.get('hinweis'))[:200]}\n"
                     "Der Lauf geht weiter - es ist belegt nichts geschrieben worden.")
        today = datetime.now(timezone.utc).date().isoformat()
        total = self.state.add_spend(today, res.cost_usd)
        head = (f"Batch {self.state.batch} fertig: rc={res.rc}, {secs_human(res.duration_s)}, "
                f"Kosten ${res.cost_usd:.4f} (heute ${total:.4f}), Modell-ok={res.model_ok}")
        if res.alarms:
            head += "\n" + "\n".join(res.alarms)
        # R13h: die Laufzeit-Aufteilung gehoert an die Batch-Meldung - die Frage
        # "warum hat das so lange gedauert?" soll man nicht aus dem Log beantworten.
        profil = (res.stats or {}).get("laufzeit") or {}
        if profil.get("spanne_s"):
            head += "\nZeit: " + self.laufzeit_zeile({"stats": {"laufzeit": profil}})
        if res.killed_reason:
            head += f"\nGRENZE AUSGELOEST: {res.killed_reason}"
        if res.model_ok is False:
            head += f"\nMODELL-ABWEICHUNG: gesehen {res.model_seen}, erwartet {self.cfg.get('claude','model_worker')}"
        self.say(head)
        if gs.get("needed"):
            self.say(("Ghidra gespeichert: " + str(gs.get("hinweis"))) if gs.get("ok") else
                     ("GHIDRA NICHT GESPEICHERT: " + str(gs.get("hinweis")) +
                      "\nIch pausiere - Push und Review unterbleiben."))
        self.log.info("Batch beendet", info=res.describe())
        return res

    def ask_handover(self, session_id: str, rdir: Path) -> str:
        """Die alte Reviewer-Session um eine Uebergabe bitten (R13-2).

        Faellt der Aufruf aus (Limit, Netz, alter Prozess), geht es OHNE Uebergabe
        weiter - der neue Review bekommt Anker, Messdaten und Snapshot ohnehin.
        """
        self.phase("uebergabe", "alte Reviewer-Session")
        try:
            text = rv.run_handover(self.cfg, self.log, session_id, mock=self.mock,
                                   stream_path=rdir / "handover.jsonl")
        except Exception as exc:
            self.log.warn("Uebergabe fehlgeschlagen - neue Session startet ohne",
                          fehler=str(exc)[:200])
            self.say("Uebergabe der alten Session fehlgeschlagen - die neue startet ohne.")
            return ""
        text = (text or "").strip()
        if text:
            self.log.info("Uebergabe erhalten", zeichen=len(text))
        else:
            self.say("Die alte Session hat keine Uebergabe geliefert.")
        return text

    def do_review(self, kind: str, snapshot_text: str, reviewer_note: str = "",
                  attempt: int = 1, handover: str = "") -> rv.ReviewResult:
        """Einen Review fahren (R13b: Nummern nach dem Anker, Rotation genau einmal).

        Nummern:
          * `evidence` = der Batch, dessen Belege bewertet werden (`state.batch`),
          * `target`   = der Batch, fuer den freigegeben wird (`expected_batch()`, Anker+1).
        Das Review liegt in `runs/b<target>` (dort steht, was den naechsten Batch betrifft);
        die Worker-Belege des bewerteten Laufs bleiben in `runs/b<evidence>`.

        Bei `attempt == 1` wird - falls faellig - rotiert (mit Uebergabe). Der Wechsel wird
        SOFORT verbucht: neue Kennung im Zustand, Uebergabe in `sessions/`. So bleibt beides
        erhalten, auch wenn der Review scheitert oder der Harness abstuerzt. `attempt >= 2`
        wiederholt nur den Review - ohne zweite Rotation und ohne zweite Uebergabe.
        """
        rev_state = self.state.data.get("reviewer") or {}
        session_id = rev_state.get("session_id")
        count = int(rev_state.get("reviews", 0))
        rot = int(self.cfg.get("reviewer", "rotation_after", 10))
        force = bool(rev_state.get("force_rotate"))
        evidence = int(self.state.batch or 0)
        target = self.expected_batch() or evidence or 0
        rdir = ensure_dir(Path(self.cfg.sub("runs")) / f"b{target:03d}")
        self._review_target = target
        self._review_dir = rdir
        self._review_rotation = False
        self._review_handover = handover
        if target != evidence:
            self.log.info("Review-Verzeichnis", verzeichnis=str(rdir), bewerteter_batch=evidence,
                          freigabe_fuer=target)

        if attempt > 1:
            handover = handover or str((rev_state.get("pending_handover") or {}).get("text") or "")
        elif force or (not session_id) or (count >= rot):
            grund = "auf Wunsch (frische Session)" if force else f"Rotation nach {count} Reviews"
            alt = session_id
            merker = rev_state.get("pending_handover") or {}
            if alt and merker.get("from_session") == alt and merker.get("text"):
                # Die vorhandene Uebergabe ist gueltig und bezahlt: nicht noch einmal fragen.
                handover = str(merker["text"])
                self.log.info("Uebergabe wiederverwendet", alte_session=alt, zeichen=len(handover))
                self.say("Frische Reviewer-Session - die vorhandene Uebergabe wird wiederverwendet.")
            elif alt:
                self.say(f"Reviewer-Session wird gewechselt - {grund}. Die alte Session uebergibt.")
                self.log.info("Reviewer-Session-Wechsel", grund=grund, alte_session=alt)
                handover = self.ask_handover(alt, rdir)
            neu = str(uuid.uuid4())
            if neu == alt:                       # Sicherheitsnetz: nie die alte Kennung erben
                neu = str(uuid.uuid4())
            self.state.reviewer_new_session(neu, handover=handover, from_session=alt or "")
            self.state.save()
            sp = Path(self.cfg.sub("sessions"))
            write_text_atomic(sp / f"claude-{neu}.md", handover or "(keine Uebergabe erhalten)")
            write_text_atomic(sp / "vorherige-session.md",
                              f"# Vorherige Reviewer-Session\n\nID: {alt}\n"
                              + (handover or "(keine Uebergabe erhalten)") + "\n")
            self.log.info("Neue Reviewer-Session", alt=alt, neu=neu,
                          uebergabe_zeichen=len(handover))
            session_id = neu
            self._review_rotation = True

        if attempt > 1:
            # Mitschnitt des ersten Versuchs behalten (watch zeigt `reviewer.jsonl`).
            alt = rdir / "reviewer.jsonl"
            v1 = rdir / "reviewer-v1.jsonl"
            if alt.is_file() and not v1.is_file():
                try:
                    alt.replace(v1)
                except OSError:
                    pass
        prompt = rv.build_prompt(
            self.cfg, kind,
            self.review_context(snapshot_text, reviewer_note, handover=handover,
                                attempt=attempt, rdir=rdir,
                                previous_raw=self._review_previous_raw))
        if self.state.data.get("pause_work"):
            self.state.data.pop("pause_work", None)   # einmal zugestellt
            self.state.save()
        if self.state.data.get("remote_work"):
            # R13n: ebenfalls EINMAL zugestellt - der naechste Review soll nicht
            # denselben Pull erneut gemeldet bekommen.
            self.state.data.pop("remote_work", None)
            self.state.save()
        # R13e: der Ordner des laufenden Reviews gehoert in den Zustand. `watch`
        # liest nur und wusste sonst nicht, wo der Reviewer gerade schreibt - es
        # las `runs/b<batch>/reviewer.jsonl` und zeigte damit den VORIGEN Review
        # (nach B161 stand dort die B160-Bewertung samt B161-Instruktion).
        self.state.data["review"] = {"dir": str(rdir), "kind": kind,
                                     "evidence": evidence, "target": target,
                                     "started_at": now_iso()}
        self.state.set(st.CLAUDE_REVIEWING, kind)
        res = rv.run_review(self.cfg, self.log, prompt, session_id=session_id,
                            new_session=bool(self._review_rotation), mock=self.mock,
                            mock_mode=self.mock_reviewer_mode,
                            stream_path=rdir / "reviewer.jsonl", mock_batch=target,
                            attempt=attempt)
        res.review_dir = str(rdir)
        # R13g: Schluessel-Zugriff im Reviewer-Mitschnitt sofort melden.
        if getattr(res, "secret_hits", None):
            self.say(streamjson.secret_alarm_text(res.secret_hits, "Reviewer", target))
        self._review_previous_raw = (res.text or "")[:4000]
        stempel = now_iso().replace(":", "").replace("-", "").replace("T", "-")[:15]
        name = "review.md" if kind == "batch_end" else "review-pre.md"
        if not self.review_ok(res):
            # R13b: Nichts freigeben - Rohantwort eindeutig als Beleg ablegen (nie
            # ueberschreiben), nichts verbuchen.
            name = f"review-verworfen-{stempel}-v{attempt}.md"
        res.review_file = str(rdir / name)
        try:
            write_text_atomic(rdir / name, (res.text or "") + "\n")
        except OSError:
            pass
        if self._review_rotation and res.session_id and res.session_id != session_id:
            # Der Prozess meldet eine andere Kennung - die gilt.
            self.log.warn("Reviewer-Kennung abweichend - uebernommen", erwartet=session_id,
                          gemeldet=res.session_id)
            rev = self.state.data.setdefault("reviewer", {})
            rev["session_id"] = res.session_id
            session_id = res.session_id
            self.state.save()
        if res.limit_reached:
            # R13e: Zeitpunkt aus der Meldung uebernehmen und von selbst fortsetzen.
            wann, quelle = self.limit_wait_ziel(res.text or res.error or "")
            self.state.data["limit_wait_until"] = wann.isoformat(timespec="seconds")
            self.state.data["limit_wait_quelle"] = quelle
            self.state.set(st.LIMIT_WAIT, "Pro-Limit erreicht")
            self.state.data["paused"] = True
            self.state.save()
            self.say("Claude-Limit erreicht - das ist ein regulärer Wartezustand. "
                     f"Ich warte bis {wann.isoformat(timespec='minutes')} "
                     f"({quelle}) und mache dann VON SELBST weiter - kein /resume noetig.")
            return res
        if not self.review_ok(res):
            # Modellabweichung oder leerer/kaputter Lauf: der Aufrufer entscheidet ueber
            # Wiederholung/Pause (R13b). Hier wird NICHTS gezaehlt und nichts freigegeben.
            self.log.error("Review ohne gueltigen Protokollblock", versuch=attempt,
                           grund=self.review_fehler_grund(res), rohtext=res.raw_path,
                           modell=res.model_seen)
            return res
        self.state.reviewer_note_review(res.parsed.decision)
        rev = self.state.data.setdefault("reviewer", {})
        rev["model_seen"] = res.model_seen
        rev["model_ok"] = res.model_ok
        rev["effort"] = self.reviewer_effort()
        self.state.save()
        return res

    # ------------------------------------------------- Review-Gueltigkeit (R13b)
    def review_ok(self, res) -> bool:
        """Darf dieser Review eine Freigabe erzeugen?

        Nur mit Protokollblock UND richtigem Modell - und nur, wenn er vollstaendig ist:
        Zusammenfassung, Instruktion mit Batch-Nummer und ein erkennbares Werkzeugprofil.
        Eine Watchdog-Antwort braucht nur die Entscheidung. Was hier durchfaellt, wird
        verworfen (Rohantwort als Beleg) und NIE freigegeben; die Schleife wiederholt
        einmal mit Format-Erinnerung.
        """
        if res is None or res.parsed is None or res.model_ok is False or res.error:
            return False
        p = res.parsed
        if not p.blocks:
            return False
        if p.decision is not None:          # Watchdog-Review: nur die Entscheidung
            return True
        return bool(p.summary and p.instruction and p.batch is not None and p.profile)

    def review_fehler_grund(self, res) -> str:
        """Kurz und konkret, was gefehlt hat - das geht so per Telegram raus."""
        if res is None:
            return "kein Ergebnis"
        if res.model_ok is False:
            return f"Modell {res.model_seen or '?'} statt {res.model_expected or '?'}"
        if res.error:
            return str(res.error)[:200]
        p = res.parsed
        if p is None or not p.blocks:
            issues = "; ".join((p.issues if p else [])[:3])
            return "kein Protokollblock" + (f" ({issues})" if issues else "")
        fehlt = []
        if not p.summary:
            fehlt.append("TELEGRAM_SUMMARY")
        if not p.instruction:
            fehlt.append("DS_INSTRUCTION")
        if p.batch is None:
            fehlt.append("Batch-Nummer")
        if p.decision is None and not p.profile:
            fehlt.append("DS_TOOLS mit Profil")
        if fehlt:
            return "Protokollblock unvollstaendig: " + ", ".join(fehlt)
        return "unbekannt"

    def review_failed(self, versuche: list, kind: str, queue_ids: list[str]) -> None:
        """Review zweimal ohne Ergebnis: KEIN Gate, Queue bleibt liegen, pausieren (R13b)."""
        gruende = [self.review_fehler_grund(r) for r in versuche]
        self.phase(None)
        self.state.data["paused"] = True
        self.state.set(st.PAUSED, f"Review ohne Protokollblock ({gruende[-1]})")
        self.state.save()
        rec = {"ts": now_iso(), "kind": kind, "batch_ziel": int(self._review_target or 0),
               "batch_bewertet": int(self.state.batch or 0), "gruende": gruende,
               "rohtext": [r.raw_path for r in versuche],
               "verworfen": [getattr(r, "review_file", "") for r in versuche],
               "modelle": [r.model_seen for r in versuche],
               "queue_ids": list(queue_ids or []),
               "entwurf": [(r.text or "")[:2000] for r in versuche]}
        p = Path(self.cfg.sub("logs")) / f"review-verworfen-{now_iso().replace(':', '')}.json"
        try:
            write_text_atomic(p, json.dumps(rec, ensure_ascii=False, indent=1) + "\n")
        except OSError:
            p = None
        self.log.error("Review zweimal gescheitert - nichts freigegeben", gruende=gruende,
                       protokoll=str(p) if p else "-")
        self.say("REVIEW ZWEIMAL OHNE PROTOKOLLBLOCK - ich gebe NICHTS frei und pausiere."
                 + "\nGrund 1: " + (gruende[0] or "?")
                 + "\nGrund 2: " + (gruende[-1] or "?")
                 + "\nRohtext 1: " + str(getattr(versuche[0], "raw_path", "-"))
                 + "\nRohtext 2: " + str(getattr(versuche[-1], "raw_path", "-"))
                 + (("\nProtokoll: " + str(p)) if p else "")
                 + f"\nDie /claude-Nachricht bleibt in der Queue ({len(queue_ids or [])})."
                 + "\nBitte pruefen, dann /resume (neuer Versuch) oder /review.")

    # ------------------------------------------------------- Batch-Nummer (Anker)
    def anchor_batch(self) -> int | None:
        """Batch-Nummer aus dem Ankerkopf ("**Stand:** BATCH 158 ...")."""
        try:
            text = read_text(self.cfg.anchor_file)
        except OSError:
            return None
        return protocol.parse_anchor_batch(text)

    def expected_batch(self) -> int:
        """Erwartete Nummer = Anker-Kopf + 1. 0, wenn der Anker keine Nummer nennt.

        Es gibt bewusst KEINEN zweiten Zaehler im Harness: die Nummer kommt
        ausschliesslich aus dem Anker.
        """
        n = self.anchor_batch()
        return (n + 1) if n is not None else 0

    def anchor_next_hint(self) -> int | None:
        """Querverweis aus der Zeile 'Naechster Schritt' des Ankers (B159)."""
        try:
            text = read_text(self.cfg.anchor_file)
        except OSError:
            return None
        return protocol.parse_anchor_next_hint(text)

    def batch_number_line(self) -> str:
        """Eine Zeile fuer Prompt/Status: welche Nummer gilt und woher sie kommt."""
        nxt = self.expected_batch()
        anker = self.anchor_batch()
        hint = self.anchor_next_hint()
        if not nxt:
            return "Naechster Batch laut Anker: UNBEKANNT (Anker nennt keine Nummer)"
        txt = f"Naechster Batch laut Anker: {nxt}"
        if anker:
            txt += f" (Anker-Kopf: BATCH {anker})"
        if hint and hint != nxt:
            txt += f" - ACHTUNG: der Anker nennt im 'Naechster Schritt' B{hint}; ich rechne mit {nxt}"
        return txt

    def gate_from_review(self, p, raw_path: str) -> str:
        """Uebernimmt die Reviewer-Antwort als offenen Auftrag (Gate).

        Rueckgabe: "ok" | "number_missing" | "number_mismatch".
        Bei unklarer oder abweichender Nummer wird NICHTS gestartet: der Auftrag
        bleibt als Gate liegen, der Harness pausiert und meldet die Nummern.
        """
        expected = self.expected_batch()
        instr = p.instruction or ""
        batch_no = p.batch
        hinweise: list[str] = []
        status = "ok"
        if batch_no is None:
            if expected:
                batch_no = expected
                hinweise.append(f"Die Instruktion nennt keine Batch-Nummer - ich rechne mit "
                                f"{batch_no} ({self.batch_number_line()}).")
            else:
                batch_no = 0
                status = "number_missing"
                hinweise.append("Weder die Instruktion noch der Anker nennen eine Batch-Nummer.")
        elif expected and batch_no != expected:
            status = "number_mismatch"
            hinweise.append(f"ACHTUNG: Die Instruktion nennt Batch {batch_no}, laut Anker ist "
                            f"Batch {expected} dran ({self.batch_number_line()}).")
        profile = p.profile or "none"
        program = p.program
        if profile == "none" and program:
            self.log.info("Profil none - Programm aus dem Review verworfen", program=program)
            program = None
        self.state.set_gate(st.new_review_id(), p.summary, instr,
                            {"profile": profile, "program": program, "batch": batch_no,
                             "expected": expected, "source": "reviewer"},
                            raw_path, extra={"offene_punkte": dict(getattr(p, "offene", {}) or {})})
        if status == "ok":
            return "ok"
        self.say("\n".join(hinweise) + "\n\nIch starte diesen Auftrag NICHT.")
        if status == "number_mismatch":
            self.say(f"Wege:\n  /number {expected}  -> Nummer des offenen Auftrags auf {expected} "
                     f"setzen, danach /approve\n  /review  -> neuen Review anfordern (verwirft "
                     f"diesen Auftrag)")
        else:
            self.say("Wege:\n  /number <N>  -> Nummer festlegen, danach /approve\n"
                     "  /review  -> neuen Review anfordern (verwirft diesen Auftrag)")
        self.state.data["paused"] = True
        self.state.set(st.PAUSED, "Batch-Nummer passt nicht zum Anker")
        return status

    # --------------------------------------------- Offene Punkte (A, R13c)
    def gate_offene_punkte(self, gate: dict | None = None) -> dict[str, list[str]]:
        """Offene Entscheidungen/Fragen/Live-Wuensche eines Gates.

        Neue Gates tragen sie als Feld; bei Altbestand (Gate ohne dieses Feld) werden
        sie aus der gespeicherten Zusammenfassung abgeleitet - der Zustand bleibt
        dabei unangetastet.
        """
        gate = gate if gate is not None else self.state.gate
        if not gate:
            return {"entschieden": [], "entscheidung": [], "frage": [], "live": []}
        p = gate.get("offene_punkte")
        if isinstance(p, dict) and any(p.get(k) for k in ("entschieden", "entscheidung",
                                                          "frage", "live")):
            return {"entschieden": list(p.get("entschieden") or []),
                    "entscheidung": list(p.get("entscheidung") or []),
                    "frage": list(p.get("frage") or []),
                    "live": list(p.get("live") or [])}
        return protocol.parse_offene_punkte(gate.get("summary") or "")

    def gate_wait_decision(self, gate: dict | None = None) -> bool:
        """Braucht dieses Gate eine Nutzerentscheidung? Dann NIE automatisch freigeben."""
        return bool(self.gate_offene_punkte(gate).get("entscheidung"))

    def letzte_review_datei(self) -> Path | None:
        """Die jüngste Review-Datei (falls kein Gate mehr offen ist)."""
        try:
            files = sorted(Path(self.cfg.sub("runs")).glob("b*/review*.md"),
                           key=lambda p: p.stat().st_mtime)
        except OSError:
            return None
        return files[-1] if files else None

    def offene_punkte_zeilen(self, punkte: dict | None = None) -> list[str]:
        """Zeilen fuer /status und watch: aus dem Gate, sonst aus dem letzten Review."""
        if punkte is None:
            punkte = self.gate_offene_punkte()
            if not any(punkte.values()):
                datei = self.letzte_review_datei()
                if datei is not None:
                    try:
                        punkte = protocol.parse_offene_punkte(
                            protocol.parse_review(read_text(datei)).summary)
                    except OSError:
                        punkte = None
        return protocol.offene_punkte_kurz(punkte or {})

    def discard_gate(self, reason: str) -> None:
        """Offenen Auftrag verwerfen - aber nachvollziehbar ablegen."""
        gate = self.state.gate
        if not gate:
            return
        try:
            write_text_atomic(Path(self.cfg.sub("logs")) / f"verworfen-{gate.get('id')}.json",
                              json.dumps({"reason": reason, "gate": gate}, ensure_ascii=False,
                                         indent=1) + "\n")
        except OSError:
            pass
        self.state.clear_gate()
        self.approved_gate = None
        self.log.info("Auftrag verworfen", grund=reason, id=gate.get("id"),
                      batch=(gate.get("tools") or {}).get("batch"))

    # ------------------------------------------- Harness-Messdaten fuer den Review
    def laufzeit_zeile(self, res: dict, st: dict | None = None) -> str:
        """Wo ging die Zeit hin? (R13h) Werkzeuge / Modell / Warten + langsamste Aufrufe.

        Grund (Nutzerbefund 2026-09-26): manche Batches dauerten Stunden bei wenigen
        Tokens. Gemessen war der Harness nicht die Ursache (2-21 s Rest), sondern lange
        Werkzeuglaeufe - und reine Wartezeit in `Start-Sleep`-Befehlen (in einem Batch
        1993 s = 42 %). Diese Zeile macht das im Review sichtbar, damit der Reviewer
        den naechsten Auftrag darauf zuschneiden kann.
        """
        p = ((st or res.get("stats") or {}).get("laufzeit") or res.get("laufzeit") or {})
        if not p or not p.get("spanne_s"):
            return "nicht gemessen (alter Lauf)"
        W = float(p.get("werkzeug_s") or 0)
        M = float(p.get("modell_s") or 0)
        S = float(p.get("spanne_s") or 0)
        warte = float(p.get("warte_s") or 0)
        teile = [f"Werkzeuge {W:.0f} s ({100 * W / S:.0f} %)", f"Modell {M:.0f} s"]
        if warte:
            teile.append(f"davon reines Warten {warte:.0f} s")
        lang = p.get("langsamste") or []
        if lang:
            top = "; ".join(f"{w.get('kurz') or w.get('name')} {float(w.get('dauer_s') or 0):.0f} s"
                            for w in lang[:3])
            teile.append("langsamste: " + top)
        return " | ".join(teile)

    def secret_zeile(self, batch: int) -> str:
        """Vermerk fuer den Messdatenblock: gab es Schluessel-Zugriffe in diesem Batch?

        Gelesen wird der Beleg `logs/secret-zugriff.jsonl` (R13g). Ohne Treffer steht
        dort ausdruecklich "keine" - ein fehlender Vermerk waere von "nicht geprueft"
        nicht zu unterscheiden.
        """
        try:
            treffer = streamjson.secret_meldungen(self.cfg, batch)
        except Exception:                                        # noqa: BLE001
            return "nicht pruefbar (Belegdatei unlesbar)"
        if not treffer:
            return "keine"
        teile = [f"{t.get('rolle')}:{t.get('werkzeug')}:{t.get('art')}:{t.get('name')}"
                 for t in treffer[:5]]
        mehr = "" if len(treffer) <= 5 else f" (+{len(treffer) - 5} weitere)"
        return f"{len(treffer)} Treffer - " + "; ".join(teile) + mehr

    def harness_facts(self, batch: int, ziel: Path | None = None) -> str:
        """Gemessene Zahlen, die der Reviewer braucht (Abschnitt G3 des Plans).

        `ziel` ist der Ordner, in dem die Belegdatei landet (das Review-Verzeichnis);
        gelesen wird der bewertete Lauf `runs/b<batch>`.
        """
        batch = int(self.state.data.get("last_batch_number") or batch or 0)
        ref = str(self.state.data.get("last_checkpoint") or f"harness/b{batch}-start")
        today = datetime.now(timezone.utc).date().isoformat()
        spent = self.state.spent_today(today)
        budget = float(self.cfg.get("limits", "daily_budget_usd", 10))
        if batch <= 0:
            return "\n".join([
                "- Bootstrap: es ist noch KEIN Worker-Batch gelaufen.",
                "- " + self.batch_number_line(),
                "- Ghidra gespeichert: nicht noetig (kein Batch gelaufen)",
                f"- Kosten heute: ${spent:.4f} von ${budget:.2f}",
                f"- {pricing.status_line(self.cfg)}",
            ])
        rd = Path(self.cfg.sub("runs")) / f"b{batch:03d}"
        res = read_json(rd / "result.json", {}) or {}
        st = res.get("stats") or {}
        lines = [
            f"- Review: bewertet wird Batch {batch}; die Instruktion gilt fuer Batch "
            f"{self.expected_batch() or '?'}",
            "- " + self.batch_number_line(),
            (f"- Reviewer: Modell {self.reviewer_model_seen() or '-'} "
             f"(Soll {self.model_reviewer()}), Effort {self.cfg.get('claude', 'reviewer_effort', 'high')}"),
            f"- Ghidra gespeichert: {self.ghidra_save_line(res)}",
            f"- Ghidra-Zustand per HTTP beruehrt: {self.http_state_line(res)} (nur Vermerk)",
            f"- Profil: {res.get('profile')} | Programm: {res.get('program')}",
            f"- Exit-Code: {res.get('rc')} | Laufzeit: {self.dauer_line(res)} "
            f"| Abbruchgrund: {res.get('killed_reason') or 'kein Abbruch'}",
            f"- Alarmmeldungen: {'; '.join(res.get('alarms') or []) or 'keine'}",
            f"- SECRET-ZUGRIFF (Ueberwachung): {self.secret_zeile(batch)}",
            f"- Remote-Stand (R13n): {self.remote_work_zeile(batch)}",
            f"- Laufzeit-Profil: {self.laufzeit_zeile(res, st)}",
            f"- Kosten (gerechnet, Tarif je Aufruf): ${float(res.get('cost_usd') or 0):.4f} "
            f"| Gegenprobe alles zum Jetzt-Tarif: ${float(res.get('cost_naive_usd') or 0):.4f}",
            f"- Anfragen: {st.get('requests')} | Eingabe ohne Cache: {st.get('input_miss')} "
            f"| Cache-Treffer: {st.get('cache_read')} | Cache-Neu: {st.get('cache_creation')} "
            f"| Ausgabe: {st.get('output')}",
            f"- num_turns: {st.get('num_turns')} (nur die Harness-Grenzen sind maßgeblich)",
            f"- Modell laut Ausgabe: {res.get('model_seen')} (Soll erfüllt: {res.get('model_ok')})",
            f"- Abgelehnte Werkzeugaufrufe: {st.get('denials') or 'keine'}",
            f"- Werkzeugfehler: {wk.fehler_text(st.get('tool_errors'))}",
            f"- Kosten heute: ${spent:.4f} von ${budget:.2f} | {pricing.status_line(self.cfg)}",
        ]
        tools = st.get("tool_counts") or {}
        if tools:
            top = sorted(tools.items(), key=lambda kv: -kv[1])[:10]
            lines.append("- Werkzeugnutzung (Top 10): " + ", ".join(f"{k}×{v}" for k, v in top))
        try:
            lines += [
                "",
                f"- Git-Checkpoint vor dem Batch: {ref}",
                f"- Commits seit Checkpoint: {self.git.commits_since(ref)}",
                "- git log seit Checkpoint:",
                "```",
                *(self.git.log_since(ref) or ["(keine Commits)"]),
                "```",
                "- Diffstat seit Checkpoint:",
                "```",
                (self.git.diffstat_since(ref) or "(keine Änderungen)"),
                "```",
                "- Geänderte/neue Dateien:",
                "```",
                *(self.git.name_status_since(ref) or ["(keine)"]),
                "```",
                f"- Arbeitsbaum jetzt: {', '.join(self.git.status_porcelain()[:15]) or 'sauber'}",
                f"- HEAD jetzt: {self.git.head_short()} ({self.git.head_subject()})",
            ]
        except Exception as exc:
            lines.append(f"- Git-Messwerte nicht ermittelbar: {str(exc)[:150]}")
        text = "\n".join(lines)
        p = Path(ziel) if ziel else Path(self.cfg.sub("runs")) / f"b{batch:03d}"
        try:
            write_text_atomic(p / "harness-facts.md", text + "\n")
        except OSError:
            pass
        return text

    def batch_diff_text(self) -> str:
        """Was der bewertete Batch geaendert hat (R13p).

        Der Reviewer hat nur Read/Grep/Glob (+ seit R13p vier Nur-Lese-Git-Befehle) -
        ohne diesen Block beurteilte er einen Batch, dessen Diff er nie sah.
        """
        batch = int(self.state.data.get("last_batch_number") or self.state.batch or 0)
        ref = str(self.state.data.get("last_checkpoint") or f"harness/b{batch}-start")
        if not self.git.has_ref(ref):
            return (f"(Checkpoint {ref} fehlt - dieser Batch lief ohne Checkpoint, "
                    "ein Diff ist nicht ermittelbar)")
        try:
            dateien = self.git.name_status_since(ref, 60)
            stat = self.git.diffstat_since(ref)
            anzahl = self.git.commits_since(ref)
        except Exception as exc:                                     # noqa: BLE001
            return f"(Diff nicht ermittelbar: {str(exc)[:150]})"
        return "\n".join([f"Vergleich {ref}..HEAD: Batch {batch}, {anzahl} Commit(s) "
                          "seit dem Checkpoint",
                          "Geaenderte Dateien (name-status, max. 60):",
                          *(dateien or ["(keine Aenderungen)"]),
                          "", "Diffstat:", "```", stat, "```"])

    def historie_text(self, commits: int = 15, docs: int = 8) -> str:
        """Aeltere Batches greifbar machen, ohne den Prompt zu sprengen (R13p).

        Anlass (Nutzerfrage 2026-09-27): Der Reviewer bekam nur die letzten VIER
        Commit-Betreffe aus `lage()` und kann `git log` nicht selbst fahren (lange
        kein Bash; seit R13p nur `git log/show/diff/status`). Aeltere Batches waren
        damit praktisch unsichtbar. Hier stehen die letzten Commits als Einzeiler und
        die Namen der neuesten Batch-Dokumente - dort liegt das Wissen der alten
        Batches, und lesen kann er sie mit `Read`.
        """
        zeilen: list[str] = []
        try:
            zeilen.append(f"Letzte {commits} Commits (Hash Datum Betreff):")
            zeilen += (self.git.out("log", f"--max-count={commits}", "--pretty=%h %ad %s",
                                    "--date=short").splitlines() or ["(keine Commits)"])
        except Exception as exc:                                     # noqa: BLE001
            zeilen.append(f"(git log nicht ermittelbar: {str(exc)[:150]})")
        try:
            adir = Path(self.cfg.decomp) / "analysis"
            if adir.is_dir():
                kandidaten = sorted(adir.glob("port-batch*.md"),
                                    key=lambda p: p.stat().st_mtime, reverse=True)[:docs]
                if kandidaten:
                    zeilen += ["", f"Neuere Batch-Dokumente (im Decomp-Repo, {len(kandidaten)}):"]
                    zeilen += [f"  * analysis/{p.name}" for p in kandidaten]
                    zeilen.append("Dort steht, was die einzelnen Batches gemacht haben. Lies die "
                                  "fuer den Auftrag relevanten - ein Urteil aus dem Gedaechtnis "
                                  "ist keine Tatsache.")
        except OSError:
            pass
        return "\n".join(zeilen)

    def review_context(self, snapshot_text: str, reviewer_note: str = "",
                       handover: str = "", attempt: int = 1, rdir: Path | None = None,
                       previous_raw: str = "") -> dict:
        """Alles, was der Reviewer je Review bekommt (Abschnitt F/G).

        Die Belege kommen aus dem BEWERTETEN Lauf (`runs/b<state.batch>`), die Review-Ablage
        aus dem Zielordner (`runs/b<expected_batch>`) - beides wird hier getrennt gehalten.
        """
        batch = int(self.state.batch or 0)
        edir = Path(self.cfg.sub("runs")) / f"b{batch:03d}"
        report = read_text(edir / "antwort.md") if batch > 0 else ""
        markers = protocol.parse_worker_markers(report) if report else {}
        marker_lines = []
        for name in ("tool_request", "program_request"):
            for v in (markers.get(name) or []):
                marker_lines.append(f"{name}: {v}")
        try:
            anchor = "\n".join(read_text(self.cfg.anchor_file).splitlines()[:8])
        except OSError:
            anchor = "(nicht lesbar)"
        return {
            "batch": batch,
            "next_batch": self.expected_batch(),
            "anchor_batch": self.anchor_batch(),
            "anchor_hint": self.anchor_next_hint(),
            "facts": self.harness_facts(batch, ziel=rdir),
            "worker_report": report,
            "diff": self.batch_diff_text(),
            "historie": self.historie_text(),
            "markers": "\n".join(marker_lines),
            "queue_block": reviewer_note,
            "anchor": anchor,
            "snapshot": snapshot_text,
            "handover": handover,
            "retry_hint": bool(attempt > 1),
            "previous_raw": previous_raw,
            "extra": self.pause_work_note(),
        }

    def pause_work_note(self) -> str:
        """Hinweis fuer den Review, wenn in der Pause gearbeitet wurde (oder ein Pull kam).

        R13e: Harness-Batch-Commits werden ausdruecklich getrennt ausgewiesen.
        Sie sind keine Handarbeit - ohne diese Trennung meldete der Review die
        eigenen Batches als "Arbeit in der Pause".
        R13n: Vom Remote uebernommene Commits sind NUTZERARBEIT und stehen in einem
        eigenen Block; in der Pausenliste erscheinen sie nicht noch einmal.
        """
        pause = self.state.data.get("pause_work") or {}
        remote = self._remote_work()
        if not pause and not remote:
            return ""
        remote_hashes = self._remote_hashes()
        zeilen: list[str] = []
        if pause:
            zeilen += ["HINWEIS: Der Nutzer hat in der Pause selbst gearbeitet.",
                       f"- Pause seit {pause.get('since')}, "
                       f"HEAD {pause.get('head_before')} -> {pause.get('head_now')}"]
            if pause.get("dirty"):
                zeilen.append(f"- Arbeitsbaum: {len(pause['dirty'])} Aenderungen: "
                              + "; ".join(str(x) for x in pause["dirty"][:10]))
            hand = [c for c in (pause.get("commits_hand") or [])
                    if str(c).split(" ", 1)[0] not in remote_hashes]
            har = list(pause.get("commits_harness") or [])
            if hand or har:
                zeilen.append(f"- Commits in der Pause: {len(hand)} Handarbeit, "
                              f"{len(har)} Harness-Batch (keine Handarbeit)")
            for c in hand[:10]:
                zeilen.append(f"  * Handarbeit: {c}")
            for c in har[:10]:
                zeilen.append(f"  * Harness-Batch: {c}")
        if remote:
            commits = list(remote.get("commits") or [])
            zeilen += ["",
                       "VOM REMOTE UEBERNOMMEN - DAS IST NUTZERARBEIT (nicht die des Workers):",
                       f"- {len(commits)} Commit(s), {str(remote.get('von') or '?')[:8]} -> "
                       f"{remote.get('nach')} am {remote.get('ts')} "
                       f"(Anlass: {remote.get('anlass')})",
                       "- Diese Arbeit wurde auf dem anderen Rechner committet und gepusht; "
                       "der Harness hat sie nur uebernommen. Sie ist NICHT zu bewerten wie "
                       "ein Worker-Batch, aber ihr Stand ist die Grundlage des neuen Auftrags.",
                       "- R367: wegen des uebernommenen Codes wurde Neubau + EINE volle "
                       "Regression zu Batch-Beginn verlangt (siehe Worker-Bericht)."]
            for c in commits[:10]:
                zeilen.append(f"  * Nutzerarbeit (Remote): {c}")
        ref = pause.get("head_before") if pause else remote.get("von")
        if ref:
            try:
                zeilen.append("- git log seit " + str(ref)[:8] + " (Rohform): "
                              + (" | ".join(self.git.log_since(ref, 10)) or "(keine Commits)"))
                zeilen.append("- Diffstat seit " + str(ref)[:8] + ":\n```\n"
                              + self.git.diffstat_since(ref) + "\n```")
            except Exception as exc:
                zeilen.append(f"- git-Angaben nicht ermittelbar: {str(exc)[:150]}")
        return "\n".join(zeilen)

    def lage(self, note: str = "") -> str:
        st_lines = []
        try:
            d = self.git.divergence()
            st_lines.append(f"Git: {self.git.head_short()} ({self.git.head_subject()}) "
                            f"origin={'gleich' if d.get('same') else 'ABWEICHEND'}")
            st_lines.append("Arbeitsbaum: " + (", ".join(self.git.status_porcelain()[:10]) or "sauber"))
            st_lines.append("Letzte Commits:\n  " + "\n  ".join(self.git.recent_commits(4)))
        except Exception as exc:
            st_lines.append(f"Git: Fehler {str(exc)[:120]}")
        ds = queue.pending(self.qroot, "ds")
        cl = queue.pending(self.qroot, "claude")
        today = datetime.now(timezone.utc).date().isoformat()
        head = [f"Harness-Lage am {now_iso()}",
                f"- Zustand: {self.state.state}, Batch {self.state.batch} "
                f"(naechster {self.state.batch + 1})",
                f"- Dauerbetrieb: {'AN' if self.state.data.get('autonomous') else 'AUS'}",
                f"- Kosten heute: ${self.state.spent_today(today):.4f}",
                f"- {pricing.status_line(self.cfg)}",
                f"- Queue: ds {len(ds)}, claude {len(cl)}",
                ""] + st_lines
        if note:
            head += ["", note]
        return "\n".join(head)

    def letzter_crash_bericht(self) -> Path | None:
        """Der jüngste Absturzbericht in logs/crash-*.txt (oder None)."""
        try:
            files = sorted(Path(self.cfg.sub("logs")).glob("crash-*.txt"),
                           key=lambda p: p.stat().st_mtime)
        except OSError:
            return None
        return files[-1] if files else None

    def report_crash(self, exc: BaseException) -> Path | None:
        """Unbehandelte Ausnahme: Traceback ins Log, in eine Datei und per Telegram.

        Ohne das starb der Harness am 2026-09-26 um 00:30 still und ohne jede Spur
        (kein Logeintrag, kein Ereignis in der Ereignisanzeige).
        """
        tb = traceback.format_exc()
        p = Path(self.cfg.sub("logs")) / f"crash-{now_iso().replace(':', '')}.txt"
        text = "\n".join([
            f"Harness-Absturz {now_iso()}",
            f"Ausnahme: {type(exc).__name__}: {exc}",
            f"Zustand: {self.state.state} | Batch {self.state.batch} | "
            f"Phase {self.phase_text()} | Gate {bool(self.state.gate)}",
            f"Arbeitsverzeichnis: {os.getcwd()}",
            f"Aufruf: {' '.join(sys.argv)}",
            "",
            tb,
        ])
        try:
            write_text_atomic(p, text + "\n")
        except OSError:
            p = None
        self.log.error("ABSTURZ - unbehandelte Ausnahme",
                       fehler=f"{type(exc).__name__}: {exc}"[:400],
                       bericht=str(p) if p else "-")
        self.log.error("TRACEBACK\n" + tb)
        try:
            self.say("HARNESS ABGESTÜRZT\n"
                     + f"{type(exc).__name__}: {str(exc)[:200]}\n"
                     + f"Crash-Bericht: {p if p else '(nicht schreibbar)'}\n"
                     + f"Zustand: {self.state.state}, Batch {self.state.batch}")
        except Exception as exc2:
            self.log.warn("Absturzmeldung per Telegram fehlgeschlagen", fehler=str(exc2)[:150])
        return p

    # ---------------------------------------------------------------- Schleife
    def run(self, paused: bool = False):
        control.write_pid(self.cfg)
        self.recover()
        if self.state.data.get("stopped"):
            # Ein Stopp gilt fuer den Prozess, nicht fuer die Ewigkeit: nach einem
            # Neustart wird er aufgehoben - aber nur bis PAUSIERT, damit nichts
            # von selbst loslaeuft.
            self.log.info("Voriger Stopp wird beim Start aufgehoben")
            self.state.data["stopped"] = False
            self.state.data["paused"] = True
            self.state.save()
        try:
            self._loop(paused)
        except Exception as exc:
            # C (R13c): Jede unbehandelte Ausnahme hinterlaesst eine Spur.
            self.report_crash(exc)
            raise
        finally:
            self.save_ghidra_if_pending("Harness-Ende")
            control.clear_pid(self.cfg)

    def _loop(self, paused: bool = False):
        if paused:
            self.state.data["paused"] = True
            self.state.set(st.PAUSED, "Start im Freigabemodus (pausiert)")
        self.say("Harness gestartet. " + ("MOCK-MODUS (keine echten Laeufe). " if self.mock else "") +
                 ("Zustand PAUSIERT - /resume startet den Bootstrap-Review." if paused else ""))
        if paused:
            self.say(self.status_text())
        while not self.quit:
            self.poll()
            self.retention_tick()
            s = self.state
            if self.review_now:
                # /review: offenen Auftrag verwerfen und sofort neu bewerten lassen.
                self.review_now = False
                if s.gate:
                    self.discard_gate("Review angefordert")
                s.data["paused"] = False
                s.data["stopped"] = False
                self.stop_requested = False
                s.set(st.IDLE, "Review angefordert")
            if s.data.get("stopped"):
                # Sauberer Stopp: WIP sichern (falls noch nicht geschehen) und den
                # Prozess wirklich beenden - das ist genau, was angesagt wurde.
                if not self._wip_done:
                    self._wip_done = True
                    try:
                        info = self.git.wip_rescue(self.state.batch, Path(self.cfg.sub("logs")))
                        if info.get("dirty"):
                            self.say(f"STOP: WIP gesichert ({len(info['status'])} Aenderungen"
                                     + (f", Patch {Path(info['patch']).name}" if info.get("patch") else "")
                                     + (f", {info['stash']}" if info.get("stash") else "") + ")")
                        else:
                            self.say("STOP: Arbeitsbaum war sauber.")
                    except Exception as exc:
                        self.log.warn("WIP-Sicherung fehlgeschlagen", fehler=str(exc)[:150])
                self.say("Harness beendet sich (Stopp). Neustart: start.ps1 -Paused")
                self.log.info("Harness beendet sich nach Stopp")
                self.quit = True
                continue
            if s.data.get("paused"):
                # R13e: der Limit-Wartezustand endet von selbst.
                if self.limit_wait_tick():
                    continue
                self.phase(None)
                time.sleep(IDLE_SLEEP)
                continue

            gate = s.gate
            if gate is None:
                ok, why = self.peak_gate()
                if not ok:
                    self.notify_once("peak", "PEAK: " + why, 1800)
                    time.sleep(20)
                    continue
                if self.daily_budget_left() <= 0:
                    s.data["paused"] = True
                    s.set(st.PAUSED, "Tagesbudget aufgebraucht")
                    self.say("Tagesbudget aufgebraucht - pausiert.")
                    continue
                kind = "batch_end" if s.batch > 0 else "bootstrap"
                snap = self.build_snapshot_text()
                # R13b: Nachrichten erst NACH einem gueltigen Review als zugestellt buchen.
                note_block, note_ids = self.read_queue_block("claude", mark=False)
                self.phase("review", kind)
                res = self.do_review(kind, snap, reviewer_note=note_block)
                if res.limit_reached:
                    continue
                if not self.review_ok(res):
                    # Ein Wiederholungsversuch mit ausdruecklicher Format-Erinnerung.
                    grund1 = self.review_fehler_grund(res)
                    self.log.warn("Review ohne gueltigen Protokollblock - Wiederholung",
                                  grund=grund1, ziel=self._review_target)
                    self.say("REVIEW OHNE PROTOKOLLBLOCK (" + grund1 + ")."
                             "\nIch wiederhole EINMAL mit ausdruecklicher Format-Erinnerung. "
                             "Freigegeben wird nichts.")
                    self.phase("review", f"{kind} (2. Versuch)")
                    res2 = self.do_review(kind, snap, reviewer_note=note_block, attempt=2,
                                          handover=self._review_handover)
                    if not self.review_ok(res2):
                        # Nach zwei Versuchen: pausieren, Queue behalten, KEIN Gate.
                        self.review_failed([res, res2], kind, note_ids)
                        continue
                    res = res2
                # Ab hier ist der Review gueltig: jetzt ist die Queue zugestellt.
                self.commit_queue("claude", note_ids)
                p = res.parsed
                if p.issues:
                    self.say("Review unvollstaendig: " + "; ".join(p.issues) +
                             "\nBitte pruefen; ich starte NICHT automatisch.")
                status = self.gate_from_review(p, str(res.raw_path))
                tools = (self.state.gate or {}).get("tools") or {}
                profile = tools.get("profile") or "none"
                warten = self.gate_wait_decision()
                # R13e: Der Kopf sagt, was WIRKLICH passiert. Im Dauerbetrieb wird
                # ohne Nutzer automatisch freigegeben - dann stand hier trotzdem
                # "FREIGABE NOETIG" und der Nutzer wartete auf etwas, das schon lief.
                autonom = bool(s.data.get("autonomous")) and not warten
                if status != "ok":
                    kopf = "AUFTRAG ANGEHALTEN"
                elif warten:
                    kopf = "WARTET AUF DEINE ENTSCHEIDUNG"
                elif autonom or (tools.get("source") == "user"):
                    kopf = "AUTOMATISCH FREIGEGEBEN (Dauerbetrieb)"
                else:
                    kopf = "FREIGABE NOETIG"
                self.phase("gate" if status == "ok" else None, f"Batch {tools.get('batch')}")
                self.say(f"{kopf} - Batch {tools.get('batch')}, Profil {profile}, Programm "
                         f"{tools.get('program') or '-'}"
                         + (f"\n(kein /approve noetig - Batch {tools.get('batch')} startet von selbst.)"
                            if kopf.startswith("AUTOMATISCH") else ""))
                self.say("Zusammenfassung:\n" + (p.summary or "(keine)"))
                if p.instruction:
                    self.say("Instruktion (vollstaendig):\n" + p.instruction)
                if warten:
                    # A (R13c): echte Bremse - auch im Dauerbetrieb wird hier nicht gestartet.
                    self.log.info("Gate braucht eine Entscheidung",
                                  batch=tools.get("batch"),
                                  entscheidung=self.gate_offene_punkte().get("entscheidung"))
                    self.say("Wartet auf deine Entscheidung:\n"
                             + "\n".join("- " + v for v in
                                         self.gate_offene_punkte().get("entscheidung") or [])
                             + "\nAntworte per /claude (kommt beim naechsten Review an) "
                               "oder /review; freigeben mit /approve.")
                    s.set(st.GATE_APPROVAL, "wartet auf deine Entscheidung")
                continue

            warten_gate = self.gate_wait_decision(gate)
            approved = ((self.approved_gate == gate.get("id"))
                        or (bool(s.data.get("autonomous")) and not warten_gate)
                        or (gate.get("tools") or {}).get("source") == "user")
            if not approved:
                s.set(st.GATE_APPROVAL,
                      "wartet auf deine Entscheidung" if warten_gate else "wartet auf /approve")
                self.phase("gate", f"Batch {(gate.get('tools') or {}).get('batch')}")
                time.sleep(IDLE_SLEEP)
                continue

            tools = gate.get("tools") or {}
            profile = tools.get("profile") or "none"
            program = tools.get("program")
            if profile == "none" and program:
                # Profil none = kein Ghidra-Zugriff: kein Programmwechsel, keine Sicherung.
                self.log.info("Profil none - Programm wird nicht gestellt", program=program)
                self.say(f"Profil none: Ghidra-Programm {program} wird NICHT gestellt "
                         "(kein Wechsel, keine Sicherung).")
                program = None
            batch_no = int(tools.get("batch") or self.expected_batch() or 0)
            instruction = gate.get("instruction") or ""

            ok, why = self.git_preflight()
            if not ok:
                # R13m: Der Auftrag BLEIBT stehen (Vorgabe 2026-09-27). Wird er hier
                # verworfen, laesst der naechste Versuch einen neuen Review laufen -
                # gemessen am 2026-09-27: nach dem Git-Halt (origin/main lag hinter
                # dem lokalen Stand) war der bezahlte Auftrag weg und der Review lief
                # ein zweites Mal, obwohl die Instruktion unveraendert galt.
                s.data["paused"] = True
                s.set(st.PAUSED, why)
                self.phase(None)
                self.say("PAUSE: " + why +
                         f"\nDer Auftrag fuer Batch {batch_no} bleibt stehen - "
                         "nach dem Fortsetzen startet er ohne neuen Review.")
                continue
            try:
                tag = self.git.checkpoint(batch_no)
                s.data["last_checkpoint"] = tag
                self.log.info("Git-Checkpoint", tag=tag, head=self.git.head_short())
            except Exception as exc:
                self.log.warn("Checkpoint fehlgeschlagen", fehler=str(exc)[:150])

            # R13m: erst JETZT wird der Auftrag verbraucht - alles davor (Git-Vorpruefung,
            # Checkpoint) kann den Start verhindern, ohne die Instruktion zu entwerten.
            self.approved_gate = None
            s.clear_gate()

            note_block, _ = self.read_queue_block("ds")
            s.data["last_batch_number"] = batch_no
            s.data["batch"] = batch_no
            s.save()
            self.say(f"Starte Batch {batch_no}: Profil {profile}, Programm {program or '-'}")
            self._wip_done = False
            try:
                self.run_worker(instruction, profile, program, note_block)
            except Exception as exc:
                self.log.error("Worker-Start/Ablauf fehlgeschlagen", fehler=str(exc)[:250])
                self.say("FEHLER beim Worker: " + str(exc)[:400])
                s.set(st.ERROR, str(exc)[:200])
                s.data["paused"] = True
                s.save()
                continue
            if self.ghidra_failed:
                # Nicht pushen und nicht bewerten: erst muss die Ghidra-DB stimmen.
                self.ghidra_failed = False
                self.phase(None)
                continue
            self.state.set(st.REVIEW_DUE, "Batch beendet")
            self.phase("push", f"Batch {batch_no}")
            push_ok, push_text = self.git_push()
            # R13e: Stand merken, bis zu dem der HARNESS selbst gearbeitet hat.
            # Die Pausen-Erkennung setzt ihren Ausgangspunkt darauf neu, damit
            # eigene Batch-Commits nie als Handarbeit gelten.
            self.mark_harness_head(batch_no)
            self.state.save()
            if push_ok:
                self.say("Push ok: " + (push_text or "up-to-date"))
            else:
                # R11-1: ein Push-Fehler ist ein Haltegrund - nicht stillschweigend
                # weiterarbeiten, waehrend der Remote zurueckliegt.
                s.data["paused"] = True
                s.set(st.PAUSED, "Push fehlgeschlagen")
                self.phase(None)
                self.say("PUSH FEHLGESCHLAGEN: " + str(push_text)[:400] +
                         "\nIch pausiere; der Remote ist nicht auf dem Stand von HEAD "
                         f"({self.git.head_short()}).")

    def build_snapshot_text(self) -> str:
        """Wie der Reviewer die Lage sieht (Abschnitt G3)."""
        parts = [self.lage()]
        snap_dir = Path(self.cfg.sub("snapshots")) / f"b{self.state.batch:03d}"
        snap = snap_dir / "snapshot.md"
        if snap.is_file():
            parts += ["", read_text(snap)[:12000]]
        else:
            parts += ["", "(kein Snapshot: dies ist der Bootstrap-Review, es gibt noch keinen Worker-Lauf)"]
        return "\n".join(parts)

    # --------------------------------------------------------------- Recovery
    def abbau_ursache(self, batch: int) -> str:
        """Steht im Mitschnitt des Batches ein verbotener Prozessabbau? (R13i)

        Der Harness kann seinen eigenen harten Tod nicht melden - er ist dann weg. Diese
        Suche laeuft beim NAECHSTEN Start und nennt den Befund: am 2026-09-26 hatte der
        Worker mit `Get-Process python | Where-Object {$_.CPU -gt 50} | Stop-Process`
        jeden python.exe mit ueber 50 s CPU-Zeit abgeraeumt, darunter den Harness.
        """
        p = Path(self.cfg.sub("runs")) / f"b{int(batch or 0):03d}" / "stream.jsonl"
        zeilen = retention.mitschnitt_zeilen(p)      # R13p: auch aus dem ZIP
        if not zeilen:
            return ""
        try:
            for zeile in zeilen:
                if "stop-process" not in zeile.lower() and "taskkill" not in zeile.lower():
                    continue
                try:
                    ev = json.loads(zeile)
                except json.JSONDecodeError:
                    continue
                for b in (((ev or {}).get("message") or {}).get("content") or []):
                    if not (isinstance(b, dict) and b.get("type") == "tool_use"):
                        continue
                    eingabe = b.get("input") or {}
                    cmd = eingabe.get("command") if isinstance(eingabe, dict) else ""
                    grund = streamjson.abbau_gefahr(cmd)
                    if grund:
                        return f"{grund} -> {' '.join(str(cmd).split())[:160]}"
        except OSError:
            return ""
        return ""

    def recover(self):
        self.state.set(st.RECOVERING, "Start/Neustart")
        pid = self.state.live_worker_pid()
        if pid:
            self.log.warn("Ein Worker laeuft noch - Harness wartet nicht, markiert als abgebrochen", pid=pid)
            self.say(f"Neustart erkannt: Worker-PID {pid} laeuft noch. Ich fasse sie nicht an.")
        elif self.state.data.get("worker"):
            self.log.warn("Abbruch erkannt: Worker-Eintrag ohne lebenden Prozess")
            info = self.git.wip_rescue(self.state.batch, Path(self.cfg.sub("logs")))
            self.say("Nach einem Absturz: WIP gesichert" if info.get("dirty") else "Nach einem Absturz: Arbeitsbaum war sauber.")
            # R13i: Einen HARTEN Tod benennen, nicht nur "Absturz". Ein TerminateProcess
            # hinterlaesst keinen Crash-Bericht - ohne diese Zeile bleibt nur die Frage,
            # warum der Lauf weg ist.
            ursache = self.abbau_ursache(self.state.batch)
            if ursache:
                self.log.error("HARTTOD: verbotener Prozessabbau im Mitschnitt", befehl=ursache)
                self.say("Der vorige Lauf wurde HART abgeraeumt (kein Crash-Bericht). "
                         f"Im Mitschnitt steht ein verbotener Prozessabbau: {ursache}\n"
                         "Regel dazu steht jetzt im Worker-Vorspann (R13i).")
            else:
                self.log.warn("HARTTOD ohne erkennbare Ursache im Mitschnitt")
            self.state.worker_finished()
        gate = self.state.gate
        self.state.set(st.GATE_APPROVAL if gate else st.IDLE,
                       "Recovery: Gate uebernommen" if gate else "Recovery: bereit")
        write_text_atomic(Path(self.cfg.sub("state")) / "recovery.json",
                          json.dumps({"at": now_iso(), "state": self.state.state,
                                      "batch": self.state.batch}, indent=1))
