"""Hauptschleife (MVP P3): Batch-Ende -> Reviewer -> (Freigabe) -> neuer Worker.

Kein Watchdog in diesem Schritt (Entscheidung R4). Zustandsmaschine siehe
Abschnitt C des Plans; Zustellungen an den Worker/Reviewer nur an
Batch-Uebergaengen (E9).
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from . import control, envs, pricing, protocol, queue, reviewer as rv, secrets, state as st, worker as wk
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
        self._notified: dict[str, float] = {}
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

    def say(self, text: str):
        if self.tg:
            self.tg.send(text)

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
        """Eine Zeile fuer den Review: wurde die Ghidra-DB gespeichert? (R13-1)"""
        gs = (res or {}).get("ghidra_save") or {}
        if not gs:
            return "nicht noetig (keine Angabe im Lauf - altes Ergebnis)"
        if gs.get("needed") and gs.get("ok"):
            return "ja - " + str(gs.get("hinweis") or "")
        if gs.get("needed"):
            return "NEIN - " + str(gs.get("hinweis") or "")
        return "nicht noetig - " + str(gs.get("hinweis") or "")

    def notify_once(self, key: str, text: str, cooldown_s: float = 900.0):
        last = self._notified.get(key, 0.0)
        if time.time() - last < cooldown_s:
            return
        self._notified[key] = time.time()
        self.say(text)

    # ------------------------------------------------------------------ Queue
    def read_queue_block(self, target: str) -> tuple[str, list[str]]:
        delivered = list(self.state.data.get("delivered") or [])
        block, ids = queue.deliver_block(self.qroot, target, delivered)
        for i in ids:
            self.state.mark_delivered(i)
        if ids:
            queue.archive(self.qroot, ids, target)
        return block, ids

    # --------------------------------------------------- gemeinsame Aktionen
    # Von Telegram UND von der lokalen Steuerung (state/ctl/) benutzt.
    def _do_pause(self, note: str = "pausiert"):
        self.state.data["paused"] = True
        try:
            pause = {"ts": now_iso(), "head": self.git.head(),
                     "head_short": self.git.head_short(),
                     "dirty": self.git.status_porcelain()[:50]}
        except Exception as exc:
            pause = {"ts": now_iso(), "error": str(exc)[:200]}
        self.state.data["pause_since"] = pause
        self.state.set(st.PAUSED, note)
        self.log.info("PAUSIERT", grund=note)
        self.say("PAUSIERT (" + note + "). Ein laufender Batch laeuft zu Ende; nichts Neues startet.")

    def _do_resume(self, accept_dirty: bool = False, note: str = "fortgesetzt"):
        pause = self.state.data.get("pause_since") or {}
        try:
            head_now = self.git.head_short()
            dirty_now = self.git.status_porcelain()
        except Exception as exc:
            head_now, dirty_now = "?", []
            self.say("Git nicht lesbar: " + str(exc)[:200])
        moved = bool(pause.get("head_short")) and head_now != pause.get("head_short")
        if moved or dirty_now:
            self.state.data["pause_work"] = {
                "since": pause.get("ts"), "head_before": pause.get("head_short"),
                "head_now": head_now, "moved": moved, "dirty": dirty_now[:50],
            }
            self.state.save()
            if dirty_now and not accept_dirty:
                self.state.set(st.PAUSED, "Arbeitsbaum nicht sauber")
                self.say("In der Pause wurde gearbeitet UND der Arbeitsbaum ist nicht sauber:\n  "
                         + "\n  ".join(dirty_now[:10])
                         + "\n\nIch starte nichts. Bitte committen - oder ausdruecklich bestaetigen "
                           "(`hx.cli resume --accept-dirty`, Telegram `/resume ok`).")
                return
            self.say(f"In der Pause wurde gearbeitet (HEAD {pause.get('head_short')} -> {head_now}, "
                     f"{len(dirty_now)} Aenderungen). Der naechste Review bekommt einen Hinweis samt "
                     "git log/Diffstat.")
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
            f"Reviewer-Session: {rev.get('session_id')} ({rev.get('reviews')}/{self.cfg.get('reviewer','rotation_after',10)} Reviews)",
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
        else:
            lines.append("Gate: keins")
        if s.data.get("pause_since"):
            lines.append(f"Pause seit: {s.data['pause_since'].get('ts')} "
                         f"(HEAD {s.data['pause_since'].get('head_short')})")
        if s.data.get("pause_work"):
            lines.append("In der Pause wurde gearbeitet - der naechste Review bekommt den Hinweis.")
        lokal = control.pending(self.cfg)
        if lokal:
            lines.append("Lokale Befehle warten: " + ", ".join(lokal))
        pid = control.read_pid(self.cfg)
        lines.append(f"Harness-Prozess: {pid if pid else 'keiner'} "
                     f"({'laeuft' if control.runner_alive(self.cfg) else 'nicht erreichbar'})")
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
    def git_preflight(self) -> tuple[bool, str]:
        ok, err = self.git.fetch()
        if not ok:
            return False, f"git fetch fehlgeschlagen: {err}"
        d = self.git.divergence()
        if not d.get("ok"):
            return False, f"Git-Divergenz nicht pruefbar: {d.get('error')}"
        if not d.get("same"):
            return False, (f"origin/{self.git.branch} weicht ab (lokal {d['local'][:8]}, "
                           f"origin {str(d['remote'])[:8]}, ahead {d.get('ahead')}, behind {d.get('behind')}) "
                           "- kein Merge durch das Harness")
        return True, ""

    def git_push(self) -> tuple[bool, str]:
        if not self.cfg.get("git", "push_after_batch", True):
            return True, "Push laut Konfiguration aus"
        return self.git.push()

    # ---------------------------------------------------------------- Grenzen
    def daily_budget_left(self) -> float:
        today = datetime.now(timezone.utc).date().isoformat()
        return float(self.cfg.get("limits", "daily_budget_usd", 10)) - self.state.spent_today(today)

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
        self.say(f"GHIDRA NICHT GESPEICHERT ({reason}): {res.get('hinweis')}")
        return False

    def run_worker(self, instruction: str, profile: str, program: str | None, queue_block: str) -> wk.WorkerResult:
        self.state.set(st.DS_WORKING, f"Profil {profile}")
        self.phase("worker", f"Batch {self.state.batch}, Profil {profile}")
        res = wk.run_batch(self.cfg, self.log, self.state, instruction, profile, program,
                           queue_block=queue_block, notify=self.say,
                           tick=lambda: self.poll(fast=True), cancel=self.cancel_check,
                           mock=self.mock)
        self.state.worker_finished()
        self.state.data["last_profile"] = profile
        gs = res.ghidra_save or {}
        if gs.get("needed") and not gs.get("ok"):
            # R13-1: ohne Speichern waere der Git-Commit weiter als die Ghidra-DB.
            self.ghidra_failed = True
            self.state.data["paused"] = True
            self.state.set(st.PAUSED, "Ghidra-Speichern fehlgeschlagen")
        today = datetime.now(timezone.utc).date().isoformat()
        total = self.state.add_spend(today, res.cost_usd)
        head = (f"Batch {self.state.batch} fertig: rc={res.rc}, {secs_human(res.duration_s)}, "
                f"Kosten ${res.cost_usd:.4f} (heute ${total:.4f}), Modell-ok={res.model_ok}")
        if res.alarms:
            head += "\n" + "\n".join(res.alarms)
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

    def do_review(self, kind: str, snapshot_text: str, reviewer_note: str = "") -> rv.ReviewResult:
        rev_state = self.state.data.get("reviewer") or {}
        session_id = rev_state.get("session_id")
        count = int(rev_state.get("reviews", 0))
        rot = int(self.cfg.get("reviewer", "rotation_after", 10))
        force = bool(rev_state.get("force_rotate"))
        rotate = force or (not session_id) or (count >= rot)
        # Verzeichnis nach der ECHTEN Batch-Nummer, nicht nach einem internen Zaehler:
        # ohne gelaufenen Batch ist das die Nummer, die der Anker als naechste nennt.
        target = self.state.batch or self.expected_batch() or 0
        rdir = ensure_dir(Path(self.cfg.sub("runs")) / f"b{target:03d}")
        handover = ""
        if rotate and session_id:
            grund = "auf Wunsch (frische Session)" if force else f"Rotation nach {count} Reviews"
            self.say(f"Reviewer-Session wird gewechselt - {grund}. Die alte Session uebergibt.")
            self.log.info("Reviewer-Session-Wechsel", grund=grund, alte_session=session_id)
            handover = self.ask_handover(session_id, rdir)
        prompt = rv.build_prompt(self.cfg, kind,
                                 self.review_context(snapshot_text, reviewer_note,
                                                     handover=handover))
        if self.state.data.get("pause_work"):
            self.state.data.pop("pause_work", None)   # einmal zugestellt
            self.state.save()
        self.state.set(st.CLAUDE_REVIEWING, kind)
        res = rv.run_review(self.cfg, self.log, prompt, session_id=session_id, new_session=rotate,
                            mock=self.mock, stream_path=rdir / "reviewer.jsonl",
                            mock_batch=target)
        try:
            name = "review.md" if kind == "batch_end" else "review-pre.md"
            write_text_atomic(rdir / name, (res.text or "") + "\n")
        except OSError:
            name = "review-pre.md"
        if res.model_ok is False:
            # R11-5c: falsches Modell (z. B. automatischer Rueckfall) -> Review
            # verwerfen, melden, nichts starten. Der Mitschnitt bleibt als Beleg.
            try:
                (rdir / name).replace(rdir / "review-verworfen.md")
            except OSError:
                pass
            self.state.reviewer_note_review(None)
            self.state.data["paused"] = True
            self.state.set(st.PAUSED, "Reviewer-Modell abweichend")
            self.phase(None)
            self.say("REVIEW VERWORFEN: " + (res.error or "Modellabweichung") +
                     f"\nErwartet: {res.model_expected}; laut Ausgabe: {res.model_seen}" +
                     f"\nRohmitschnitt: {res.raw_path}\nIch starte nichts. Bitte pruefen.")
            self.log.error("Review verworfen - Modellabweichung", erwartet=res.model_expected,
                           gesehen=res.model_seen)
            return res
        if rotate:
            new_id = res.session_id or "unbekannt"
            self.state.reviewer_new_session(new_id)
            self.state.data["reviewer"]["force_rotate"] = False
            uebergabe = handover or ((res.parsed.blocks.get("HANDOVER") or [""])[0]
                                     if res.parsed else "")
            if uebergabe:
                p = write_text_atomic(Path(self.cfg.sub("sessions")) / f"claude-{new_id}.md",
                                      uebergabe)
                self.log.info("Uebergabedatei geschrieben", datei=str(p), zeichen=len(uebergabe))
            prev = Path(self.cfg.sub("sessions")) / "vorherige-session.md"
            write_text_atomic(prev, f"# Vorherige Reviewer-Session\n\nID: {session_id}\n"
                                    + (uebergabe or "(keine Uebergabe erhalten)") + "\n")
            self.log.info("Neue Reviewer-Session", alt=session_id, neu=new_id,
                          uebergabe_zeichen=len(uebergabe))
        self.state.reviewer_note_review(res.parsed.decision if res.parsed else None)
        rev = self.state.data.setdefault("reviewer", {})
        rev["model_seen"] = res.model_seen
        rev["model_ok"] = res.model_ok
        rev["effort"] = self.reviewer_effort()
        self.state.save()
        if res.limit_reached:
            self.state.set(st.LIMIT_WAIT, "Pro-Limit erreicht")
            self.state.data["paused"] = True
            self.state.save()
            self.say("Claude-Limit erreicht - das ist ein regulärer Wartezustand. "
                     "Ich pausiere; mit /resume geht es weiter.")
            return res
        return res

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
                            raw_path)
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
    def harness_facts(self, batch: int) -> str:
        """Gemessene Zahlen, die der Reviewer braucht (Abschnitt G3 des Plans)."""
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
            "- " + self.batch_number_line(),
            (f"- Reviewer: Modell {self.reviewer_model_seen() or '-'} "
             f"(Soll {self.model_reviewer()}), Effort {self.cfg.get('claude', 'reviewer_effort', 'high')}"),
            f"- Ghidra gespeichert: {self.ghidra_save_line(res)}",
            f"- Profil: {res.get('profile')} | Programm: {res.get('program')}",
            f"- Exit-Code: {res.get('rc')} | Laufzeit: {secs_human(float(res.get('duration_s') or 0))} "
            f"| Abbruchgrund: {res.get('killed_reason') or 'kein Abbruch'}",
            f"- Alarmmeldungen: {'; '.join(res.get('alarms') or []) or 'keine'}",
            f"- Kosten (gerechnet, Tarif je Aufruf): ${float(res.get('cost_usd') or 0):.4f} "
            f"| Gegenprobe alles zum Jetzt-Tarif: ${float(res.get('cost_naive_usd') or 0):.4f}",
            f"- Anfragen: {st.get('requests')} | Eingabe ohne Cache: {st.get('input_miss')} "
            f"| Cache-Treffer: {st.get('cache_read')} | Cache-Neu: {st.get('cache_creation')} "
            f"| Ausgabe: {st.get('output')}",
            f"- num_turns: {st.get('num_turns')} (nur die Harness-Grenzen sind maßgeblich)",
            f"- Modell laut Ausgabe: {res.get('model_seen')} (Soll erfüllt: {res.get('model_ok')})",
            f"- Abgelehnte Werkzeugaufrufe: {st.get('denials') or 'keine'}",
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
        p = Path(self.cfg.sub("runs")) / f"b{batch:03d}"
        try:
            write_text_atomic(p / "harness-facts.md", text + "\n")
        except OSError:
            pass
        return text

    def review_context(self, snapshot_text: str, reviewer_note: str = "",
                       handover: str = "") -> dict:
        """Alles, was der Reviewer je Review bekommt (Abschnitt F/G)."""
        batch = self.state.batch
        rd = Path(self.cfg.sub("runs")) / f"b{batch:03d}"
        report = read_text(rd / "antwort.md") if batch > 0 else ""
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
            "facts": self.harness_facts(batch),
            "worker_report": report,
            "markers": "\n".join(marker_lines),
            "queue_block": reviewer_note,
            "anchor": anchor,
            "snapshot": snapshot_text,
            "handover": handover,
            "extra": self.pause_work_note(),
        }

    def pause_work_note(self) -> str:
        """Hinweis fuer den Review, wenn der Nutzer in der Pause gearbeitet hat."""
        pause = self.state.data.get("pause_work") or {}
        if not pause:
            return ""
        zeilen = ["HINWEIS: Der Nutzer hat in der Pause selbst gearbeitet.",
                  f"- Pause seit {pause.get('since')}, HEAD {pause.get('head_before')} -> {pause.get('head_now')}"]
        if pause.get("dirty"):
            zeilen.append(f"- Arbeitsbaum: {len(pause['dirty'])} Aenderungen: "
                          + "; ".join(str(x) for x in pause["dirty"][:10]))
        ref = pause.get("head_before")
        if ref:
            try:
                zeilen.append("- git log seit Pausenbeginn: "
                              + (" | ".join(self.git.log_since(ref, 10)) or "(keine Commits)"))
                zeilen.append("- Diffstat seit Pausenbeginn:\n```\n"
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
                note_block, _ids = self.read_queue_block("claude")
                self.phase("review", kind)
                res = self.do_review(kind, snap, reviewer_note=note_block)
                if res.limit_reached:
                    continue
                if res.parsed is None or not res.parsed.blocks:
                    s.set(st.GATE_APPROVAL, "Review ohne Protokollblock")
                    self.say("Review-Antwort hatte KEINEN Protokollblock. Rohtext: " + str(res.raw_path))
                    self.approved_gate = None
                    continue
                p = res.parsed
                if p.issues:
                    self.say("Review unvollstaendig: " + "; ".join(p.issues) +
                             "\nBitte pruefen; ich starte NICHT automatisch.")
                status = self.gate_from_review(p, str(res.raw_path))
                tools = (self.state.gate or {}).get("tools") or {}
                profile = tools.get("profile") or "none"
                kopf = "FREIGABE NOETIG" if status == "ok" else "AUFTRAG ANGEHALTEN"
                self.phase("gate" if status == "ok" else None, f"Batch {tools.get('batch')}")
                self.say(f"{kopf} - Batch {tools.get('batch')}, Profil {profile}, Programm "
                         f"{tools.get('program') or '-'}")
                self.say("Zusammenfassung:\n" + (p.summary or "(keine)"))
                if p.instruction:
                    self.say("Instruktion (vollstaendig):\n" + p.instruction)
                continue

            approved = ((self.approved_gate == gate.get("id"))
                        or bool(s.data.get("autonomous"))
                        or (gate.get("tools") or {}).get("source") == "user")
            if not approved:
                s.set(st.GATE_APPROVAL, "wartet auf /approve")
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
            self.approved_gate = None
            s.clear_gate()
            instruction = gate.get("instruction") or ""

            ok, why = self.git_preflight()
            if not ok:
                s.data["paused"] = True
                s.set(st.PAUSED, why)
                self.phase(None)
                self.say("PAUSE: " + why)
                continue
            try:
                tag = self.git.checkpoint(batch_no)
                s.data["last_checkpoint"] = tag
                self.log.info("Git-Checkpoint", tag=tag, head=self.git.head_short())
            except Exception as exc:
                self.log.warn("Checkpoint fehlgeschlagen", fehler=str(exc)[:150])

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
            self.state.worker_finished()
        gate = self.state.gate
        self.state.set(st.GATE_APPROVAL if gate else st.IDLE,
                       "Recovery: Gate uebernommen" if gate else "Recovery: bereit")
        write_text_atomic(Path(self.cfg.sub("state")) / "recovery.json",
                          json.dumps({"at": now_iso(), "state": self.state.state,
                                      "batch": self.state.batch}, indent=1))
