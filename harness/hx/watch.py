"""Live-Ansicht: `hx.cli watch` — rein lesend.

Zeigt den laufenden Batch mit: Texte des Workers, Werkzeugaufrufe in Kurzform,
Ablehnungen, laufende Kosten/Anfragen/Laufzeit; am Ende die Reviewer-Antwort.

Grundsatz: **nur lesen**. Es werden ausschließlich Dateien geöffnet, die der
Harness ohnehin schreibt; es gibt keine Sperren, keine Schreibvorgänge, und das
Schließen des Fensters beendet nur diesen Zuschauer (KeyboardInterrupt).
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from . import protocol, retention, streamjson, uhr
from .util import read_json, read_text

STYLES = {
    "reset": "\x1b[0m", "bold": "\x1b[1m", "dim": "\x1b[2m",
    "cyan": "\x1b[36m", "yellow": "\x1b[33m", "red": "\x1b[31m", "green": "\x1b[32m",
}

# B (R13c): Denkbloecke live, abgesetzt und gekuerzt. Reine Anzeige - fasst weder
# Harness noch Kosten an (gelesen wird nur der Mitschnitt).
THINK_PREFIX = "  ~ "
THINK_MAX = 400


def enable_vt() -> bool:
    """ANSI-Ausgabe in der klassischen Windows-Konsole einschalten.

    Ohne das erscheinen die Farbcodes als "←[1m" (gemessen in der klassischen
    PowerShell). Schlaegt es fehl (alte Konsole, umgeleitete Ausgabe), bleibt die
    Ansicht lieber farblos als unlesbar.
    """
    if os.name != "nt":
        return True
    try:
        import ctypes
        k = ctypes.windll.kernel32
        handle = k.GetStdHandle(-11)                     # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if not k.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(k.SetConsoleMode(handle, mode.value | 0x0004))   # VT_PROCESSING
    except Exception:
        return False


def _clip(value, n: int = 110) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 3] + "..."


def _fmt_tool(name: str, inp: dict) -> str:
    if not isinstance(inp, dict):
        return name
    kurz = ", ".join(f"{k}={_clip(v, 60)}" for k, v in list(inp.items())[:4])
    return f"{name}({kurz})"


class Watcher:
    def __init__(self, cfg, log, batch: int | None = None, run: str | None = None,
                 color: bool = True, once: bool = False, thinking: bool = True):
        self.cfg = cfg
        self.log = log
        self.batch = batch
        self.run_name = run          # NICHT self.run: das ist die Methode run()
        self.once = once
        self.thinking = bool(thinking)
        self.color = bool(color) and not os.environ.get("NO_COLOR") and sys.stdout.isatty()
        if self.color and not enable_vt():
            self.color = False
        self.stats = streamjson.StreamStats()      # nur der LAUFENDE Batch
        self.rstats = streamjson.StreamStats()     # nur der laufende Review
        self.ges_requests = 0                      # Summe ueber alle gezeigten Batches
        self.ges_cost = 0.0
        self.ges_batches = 0
        self.batch_nr = 0
        self.seen = 0                # beim Nachspielen
        self.seen_worker = 0         # live
        self.seen_reviewer = 0       # live
        self.review_shown = False
        self.started = time.time()
        self._last_stats = 0.0
        self._stats_key = None

    # ------------------------------------------------------------------ Helfer
    def _state(self) -> dict:
        return read_json(Path(self.cfg.sub("state")) / "run.json", {}) or {}

    def _target_batch(self, state: dict) -> int:
        """Nummer des Laufs, um den es geht: zuletzt gelaufen, sonst Anker + 1."""
        b = int(state.get("last_batch_number") or state.get("batch") or 0)
        if b:
            return b
        try:
            n = protocol.parse_anchor_batch(read_text(self.cfg.anchor_file))
        except OSError:
            return 0
        return (n + 1) if n is not None else 0

    def _run_dir(self) -> Path:
        if self.run_name:
            p = Path(self.run_name)
            return p if p.is_absolute() or "/" in self.run_name or "\\" in self.run_name \
                else Path(self.cfg.sub("runs")) / self.run_name
        if self.batch:
            return Path(self.cfg.sub("runs")) / f"b{int(self.batch):03d}"
        return Path(self.cfg.sub("runs")) / f"b{self._target_batch(self._state()):03d}"

    def _review_dir(self, state: dict) -> Path:
        """Ordner des LAUFENDEN Reviews.

        R13e: Das Review von Batch N liegt in `runs/b<N+1>` (Nummer nach dem
        Anker) - dort steht, was den naechsten Batch betrifft. Vorher las watch
        `runs/b<N>/reviewer.jsonl`; das ist der Mitschnitt des VORIGEN Reviews,
        deshalb zeigte watch nach B161 die B160-Bewertung samt B161-Instruktion
        unter der Ueberschrift "REVIEW LAEUFT". Der Harness schreibt den
        Zielordner jetzt in den Zustand (`review.dir`); fehlt er (alter Zustand),
        wird gerechnet.
        """
        eintrag = state.get("review") or {}
        d = eintrag.get("dir")
        if d:
            return Path(d)
        b = int(state.get("last_batch_number") or state.get("batch") or 0)
        return Path(self.cfg.sub("runs")) / f"b{b + 1:03d}"

    def _bewerteter_batch(self, rd: Path) -> str:
        """Welcher Batch im Ordner `rd` bewertet wurde (aus harness-facts.md)."""
        text = read_text(rd / "harness-facts.md")
        for l in text.splitlines():
            if l.startswith("- Review: bewertet wird Batch "):
                return l[len("- Review: bewertet wird Batch "):].split(";")[0].strip()
        return "?"

    # ---------------------------------------------------------------- Ausgabe
    def _p(self, text: str = "", style: str = ""):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
        if style and self.color:
            print(STYLES.get(style, "") + text + STYLES["reset"], flush=True)
        else:
            print(text, flush=True)

    def _tail(self, path: Path, who: str, counter: str) -> int:
        """Neue Zeilen einer Mitschnittdatei anzeigen; gibt die Gesamtzahl zurueck.

        R13p: gepackte Batches (`.zip`) werden mitgelesen - `retention.mitschnitt_zeilen`
        oeffnet beide Formen.
        """
        alle = retention.mitschnitt_zeilen(path)
        if alle is None:
            return getattr(self, counter, 0)
        start = getattr(self, counter, 0)
        if len(alle) > start:
            for line in alle[start:]:
                self._render_line(line, who=who)
            setattr(self, counter, len(alle))
        return len(alle)

    def _render_thinking(self, text: str):
        """Denkblock abgesetzt/gedimmt; leere Bloecke (display: omitted) ueberspringen."""
        if not self.thinking:
            return
        roh = text or ""
        kurz = " ".join(roh.split())
        if not kurz:
            return
        if len(kurz) > THINK_MAX:
            self._p(f"{THINK_PREFIX}{kurz[:THINK_MAX]} ... "
                    f"[gekuerzt - Denkblock hat {len(roh)} Zeichen]", "dim")
        else:
            self._p(THINK_PREFIX + kurz, "dim")

    def _render_line(self, line: str, who: str = "WORKER"):
        # R13e: Worker- und Reviewer-Mitschnitt haben eigene Zaehler. Vorher lief
        # alles in einen Topf - die "laufend"-Zeile zeigte dadurch Werte seit
        # Harness-Start statt die des laufenden Batches.
        obj = (self.rstats if who == "REVIEWER" else self.stats).feed(line)
        if not obj:
            return
        t = obj.get("type")
        if t == "assistant":
            for block in ((obj.get("message") or {}).get("content") or []):
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and (block.get("text") or "").strip():
                    self._p("")
                    self._p(who + ":", "bold")
                    self._p(block["text"].strip())
                elif block.get("type") == "thinking":
                    self._render_thinking(str(block.get("thinking") or ""))
                elif block.get("type") == "tool_use":
                    self._p("  > " + _fmt_tool(str(block.get("name")), block.get("input") or {}), "cyan")
        elif t == "user":
            for block in ((obj.get("message") or {}).get("content") or []):
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    body = block.get("content")
                    text = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
                    low = text.lower()
                    # R13e: nur ECHTE Fehlerergebnisse markieren. Die alte Regel
                    # suchte den Satz irgendwo im Ergebnis; ein Read eines
                    # Dokuments, das ihn zitiert, wurde als "ABGELEHNT" gezeigt.
                    if text.lstrip().startswith("<tool_use_error>"):
                        if "no such tool available" in low or "disabled for this session" in low:
                            self._p("  x ABGELEHNT: " + _clip(text, 160), "red")
                        else:
                            self._p("  x Werkzeugfehler: " + _clip(text, 160), "red")
                    elif block.get("is_error"):
                        self._p("  ! Fehler: " + _clip(text, 160), "yellow")
        elif t == "result":
            self._p("")
            self._p(f"--- {who} beendet ---", "dim")

    def _limits_text(self) -> str:
        """Die Grenzen aus [limits] - sie gelten JE BATCH (worker.run_batch)."""
        g = lambda k, d: self.cfg.get("limits", k, d)              # noqa: E731
        return (f"  Grenzen je Batch (aus [limits]): ALARM {int(g('alarm_requests', 500))} "
                f"Anfragen / ${float(g('alarm_cost_usd', 1.0)):.2f} / "
                f"{float(g('alarm_wall_s', 9000)) / 60:.0f} min - HART "
                f"{int(g('hard_requests', 1000))} / ${float(g('hard_cost_usd', 2.0)):.2f} / "
                f"{float(g('hard_wall_s', 10800)) / 60:.0f} min")

    def _stats_umlegen(self):
        """Den abgeschlossenen Batch in die Gesamtsumme uebernehmen (R13e)."""
        if self.stats.requests:
            self.ges_requests += len(self.stats.requests)
            self.ges_cost += self.stats.cost_usd(
                list(self.cfg.get("peak", "extra_offpeak_dates", []) or []))
            self.ges_batches += 1

    def _uhr_teil(self) -> str:
        """Der Laufzeit-Teil der Statuszeile - aus der Startzeit des LAUFENDEN Batches.

        R13ac (Punkt 5 der Nutzerpruefung 2026-09-28): hier stand vorher
        `time.time() - self.started`, also die Zeit **seit dem Start des Zuschauers**.
        Gemessen wurde die Folge: um 22:11 zeigte watch "Batch 210 laufend: … 200.6 min",
        waehrend B210 laut `runs/b210/result.json` 46 min lief (2771 s, Start 21:48);
        watch war um ~18:50 gestartet. Die Zahl passte exakt zu "seit watch-Start".

        Jetzt gilt genau EINE Quelle (`hx.uhr` -> `state/run.json:worker.started_at`,
        Prozessstart des Workers) - dieselbe, die auch die BATCH-Uhr im Worker zeigt
        (R13ac, Befund M210-1). Ist der Lauf beendet, steht die Laufzeit in
        `runs/b<N>/result.json`; fehlt beides, wird das gesagt statt geraten.
        """
        stt = self._state()
        d = uhr.start_zeit(stt)
        if d["zeit"] is not None and not d["unplausibel"]:
            return (f"{max(0.0, d['alter_s'] or 0) / 60:.1f} min seit Batch-Start "
                    f"{uhr.ortszeit(d['zeit'])} (Harness-Messung)")
        if d["zeit"] is not None:
            return (f"Laufzeit nicht gemessen (Startzeit im Zustand unplausibel: "
                    f"{uhr.ortszeit(d['zeit'])}, {uhr.hms(d['alter_s'])} alt)")
        b = self.batch_nr or self._target_batch(stt)
        res = read_json(Path(self.cfg.sub("runs")) / f"b{int(b):03d}" / "result.json", {}) or {}
        if res.get("duration_s"):
            return (f"Laufzeit {uhr.hms(res.get('duration_s'))} "
                    f"(runs/b{int(b):03d}/result.json, Lauf beendet)")
        return "Laufzeit nicht gemessen (kein worker.started_at im Harness-Zustand)"

    def _print_stats(self, force: bool = False):
        t = self.stats.totals()
        if not t["requests"]:
            return
        cost = self.stats.cost_usd(list(self.cfg.get("peak", "extra_offpeak_dates", []) or []))
        # R11-4: nur bei AENDERUNG ausgeben - vorher stand alle 10 s dieselbe Zeile.
        key = (t["requests"], t["input_miss"], t["cache_read"], t["output"], round(cost, 5))
        if not force and key == self._stats_key:
            return
        self._stats_key = key
        gesamt = ""
        if self.ges_batches:
            # R13ac: der watch-Minutenwert steht NUR noch hier - und heisst so, wie er
            # gemessen ist ("seit watch-Start"), nicht "Laufzeit des Batches".
            up = time.time() - self.started
            gesamt = (f"  |  seit watch-Start: {self.ges_batches} Batch(es), "
                      f"{self.ges_requests + t['requests']} Anfragen, "
                      f"${self.ges_cost + cost:.4f}, {up / 60:.1f} min")
        self._p(f"[{time.strftime('%H:%M:%S')}] Batch {self.batch_nr} laufend: "
                f"{t['requests']} Anfragen · "
                f"{t['input_miss']} ein / {t['cache_read']} cache / {t['output']} aus · "
                f"${cost:.4f} · {self._uhr_teil()}" + gesamt, "dim")

    def _prompt_info(self):
        files = sorted(Path(self.cfg.sub("logs")).glob("review-prompt-*.md"))
        if not files:
            return
        p = files[-1]
        text = read_text(p)
        self._p(f"  Prompt: {len(text)} Zeichen ({p.name}) - Kopf:", "dim")
        for line in text.splitlines()[:4]:
            if line.strip():
                self._p("    " + line.strip()[:170], "dim")

    def _show_gate(self, gate: dict):
        tools = gate.get("tools") or {}
        self._p("")
        self._p("=" * 70, "dim")
        self._p(f"FREIGABE WARTET - Batch {tools.get('batch')} · Profil {tools.get('profile')} · "
                f"Programm {tools.get('program') or '-'}", "bold")
        if (tools.get("source") or "") == "user":
            self._p("(eigene Instruktion des Nutzers - startet ohne Review)", "yellow")
        self._p("=" * 70, "dim")
        punkte = protocol.parse_offene_punkte(gate.get("summary") or "")
        for zeile in protocol.offene_punkte_kurz(punkte):
            self._p(zeile, "yellow")
        if punkte.get("entscheidung"):
            self._p("Achtung: dieses Gate wird im Dauerbetrieb NICHT automatisch freigegeben.",
                    "yellow")
        if gate.get("summary"):
            self._p("Zusammenfassung (TELEGRAM_SUMMARY):", "bold")
            self._p(gate["summary"])
        if gate.get("instruction"):
            self._p("")
            self._p("Instruktion (DS_INSTRUCTION, vollstaendig):", "bold")
            self._p(gate["instruction"])
        self._p("")
        self._p("Weiter mit /approve · Nummer korrigieren mit /number <N> · neu bewerten mit /review",
                "dim")

    def _print_review(self):
        rd = self._run_dir()
        review = rd / "review.md"
        if not review.is_file():
            review = rd / "review-pre.md"
        if not review.is_file():
            files = sorted(Path(self.cfg.sub("logs")).glob("review-*.md"))
            if not files:
                return
            review = files[-1]
        text = read_text(review)
        parsed = protocol.parse_review(text)
        self._p("")
        self._p("=" * 70, "dim")
        self._p(f"REVIEWER ({review.parent.name}/{review.name})", "bold")
        self._p("=" * 70, "dim")
        if parsed.summary:
            self._p("Zusammenfassung (TELEGRAM_SUMMARY):", "bold")
            self._p(parsed.summary)
        if parsed.decision:
            self._p(f"Entscheidung: {parsed.decision}",
                    "green" if parsed.decision == "CONTINUE" else "yellow")
        if parsed.profile or parsed.program:
            self._p(f"Werkzeuge: Profil {parsed.profile or '-'}, Programm {parsed.program or '-'}")
        if parsed.instruction:
            self._p("")
            self._p("Instruktion (DS_INSTRUCTION):", "bold")
            self._p(parsed.instruction)
        if parsed.issues:
            self._p("Hinweise: " + "; ".join(parsed.issues), "yellow")
        for zeile in protocol.offene_punkte_kurz(parsed.offene):
            self._p(zeile, "yellow")
        self.review_shown = True

    # ------------------------------------------------------------------- Lauf
    def run(self) -> int:
        """Ohne Argumente dem laufenden Geschehen folgen, sonst nachspielen."""
        if self.batch or self.run_name:
            return self._replay()
        if self.once:
            return self._snapshot()
        return self._follow_live()

    # ------------------------------------------------------------- Nachspielen
    def _replay(self) -> int:
        rd = self._run_dir()
        stream = rd / "stream.jsonl"
        rev_stream = rd / "reviewer.jsonl"
        res = read_json(rd / "result.json", {}) or {}
        hat_review = (rd / "review.md").is_file() or (rd / "review-pre.md").is_file()
        self._p(f"watch: {rd.name}  (nachspielen)", "bold")
        if not any((stream.is_file(), rev_stream.is_file(), res, hat_review)):
            self._p(f"(noch kein Mitschnitt unter {rd})", "yellow")
            return 1
        if stream.is_file():
            self._tail(stream, "WORKER", "seen")
        if rev_stream.is_file():
            # R13e: der Reviewer-Mitschnitt in diesem Ordner gehoert zum VORIGEN
            # Batch (das Review von N liegt in b<N+1>). Deshalb hier benennen,
            # statt es unter dem Ordnernamen laufen zu lassen.
            self._p(f"(Reviewer-Mitschnitt = Review von Batch "
                    f"{self._bewerteter_batch(rd)})", "dim")
            self._tail(rev_stream, "REVIEWER", "seen_reviewer")
        self._print_stats(force=True)
        self._summary(res)
        if not res and stream.is_file():
            self._p("(fuer diesen Lauf gibt es keine Kennzahlen-Datei - "
                    "gezeigt wurde der Mitschnitt selbst)", "yellow")
        self._print_review()
        return 0

    # ------------------------------------------------------------ Einmalbild
    def _snapshot(self) -> int:
        """Ein Bild der jetzigen Lage (fuer Tests und kurze Kontrolle)."""
        stt = self._state()
        zust = str(stt.get("state") or "?")
        b = self._target_batch(stt)
        rd = Path(self.cfg.sub("runs")) / f"b{b:03d}"
        self._p(f"watch: {zust} · Batch {b} · seit {stt.get('updated_at') or '-'}", "bold")
        ph = stt.get("phase") or {}
        if ph.get("name"):
            self._p(f"Harness: {ph.get('name')}" + (f" ({ph.get('extra')})" if ph.get("extra") else ""),
                    "bold")
        gate = stt.get("gate")
        if zust == "CLAUDE_REVIEWING":
            rdir = self._review_dir(stt)
            self._p(f"REVIEW LAEUFT seit {stt.get('updated_at')} ({stt.get('note') or '-'}) "
                    f"- gezeigt wird {rdir.name}/reviewer.jsonl", "bold")
            self._prompt_info()
            self._tail(rdir / "reviewer.jsonl", "REVIEWER", "seen_reviewer")
            return 0
        if gate:
            self._show_gate(gate)
            return 0
        if zust == "DS_WORKING" and retention.mitschnitt_vorhanden(rd / "stream.jsonl"):
            self._tail(rd / "stream.jsonl", "WORKER", "seen_worker")
            self._print_stats(force=True)
        elif (rd / "result.json").is_file():
            # Fertiger Lauf: nur die Kennzahlen, nicht den ganzen Mitschnitt.
            self._summary(read_json(rd / "result.json", {}) or {})
            self._p(f"(Mitschnitt nachspielen: watch --batch {b})", "dim")
        else:
            self._p(f"(nichts zu zeigen: kein offener Auftrag, kein laufender Batch unter {rd})",
                    "yellow")
        return 0

    # ------------------------------------------------------------------- Live
    def _follow_live(self) -> int:
        self._p("watch: laufender Betrieb - rein lesend (Strg+C beendet nur den Zuschauer)", "bold")
        last: tuple | None = None
        last_phase: str | None = None
        last_worker_dir: Path | None = None
        last_review_dir: Path | None = None
        gate_id = None
        review_marker = None
        while True:
            try:
                time.sleep(1.5)
                stt = self._state()
                zust = str(stt.get("state") or "?")
                b = self._target_batch(stt)
                rd = Path(self.cfg.sub("runs")) / f"b{b:03d}"
                if (zust, b) != last:
                    last = (zust, b)
                    self._p(f"[{time.strftime('%H:%M:%S')}] {zust} · Batch {b} · seit "
                            f"{stt.get('updated_at') or '-'}"
                            + (f" · {stt.get('note')}" if stt.get("note") else ""), "dim")
                ph = stt.get("phase") or {}
                pname = ph.get("name")
                if pname != last_phase:
                    last_phase = pname
                    if pname:
                        self._p(f"[{time.strftime('%H:%M:%S')}] Harness: {pname}"
                                + (f" ({ph.get('extra')})" if ph.get("extra") else ""), "bold")
                gate = stt.get("gate")
                if zust == "CLAUDE_REVIEWING":
                    gate_id = None
                    # R13e: den Ordner des LAUFENDEN Reviews nehmen und beim Wechsel
                    # den Zaehler zuruecksetzen - sonst haengt watch am Mitschnitt
                    # des vorigen Reviews (B160 unter "REVIEW LAEUFT").
                    rdir = self._review_dir(stt)
                    if rdir != last_review_dir:
                        last_review_dir = rdir
                        self.seen_reviewer = 0
                    if review_marker != stt.get("updated_at"):
                        review_marker = stt.get("updated_at")
                        self._p("")
                        self._p(f"REVIEW LAEUFT seit {stt.get('updated_at')} "
                                f"({stt.get('note') or '-'})", "bold")
                        self._p(f"  Mitschnitt: {rdir.name}/reviewer.jsonl", "dim")
                        self._prompt_info()
                    self._tail(rdir / "reviewer.jsonl", "REVIEWER", "seen_reviewer")
                elif gate:
                    review_marker = None
                    last_review_dir = None
                    if gate_id != gate.get("id"):
                        gate_id = gate.get("id")
                        self._show_gate(gate)
                else:
                    review_marker = None
                    gate_id = None
                    # R13e: ein laufender Worker wird AUCH im Pausenzustand gezeigt.
                    # /pause setzt den Zustand auf PAUSED, der Worker laeuft aber bis
                    # zum Ende weiter - vorher verschwand er damit aus watch.
                    if zust == "DS_WORKING" or pname == "worker":
                        # Nur der LAUFENDE Lauf wird gezeigt. Betritt der Zustand den
                        # Batch neu, faengt der Mitschnitt von vorn an (die Datei kann
                        # von einem frueheren Lauf derselben Nummer stammen).
                        if last_worker_dir != rd:
                            last_worker_dir = rd
                            self._stats_umlegen()
                            self.stats = streamjson.StreamStats()
                            self._stats_key = None
                            self.seen_worker = 0
                            # R13e: neuer Batch -> Batch-Ende wieder anzeigen. Vorher
                            # blieb `review_shown` gesetzt, deshalb erschien das Ende
                            # jedes weiteren Batches nie mehr im Fenster.
                            self.review_shown = False
                            self.batch_nr = b
                            self._p("")
                            self._p(f"Worker laeuft: {rd.name}"
                                    + (" (pausiert - laeuft zu Ende)" if stt.get("paused") else ""),
                                    "bold")
                            self._p(self._limits_text(), "dim")
                        if self._tail(rd / "stream.jsonl", "WORKER", "seen_worker"):
                            self._print_stats()
                    else:
                        last_worker_dir = None
                    if (rd / "result.json").is_file() and not self.review_shown:
                        self._batch_ende_melden(stt, rd, b)
            except KeyboardInterrupt:
                self._p("(watch beendet - der Harness laeuft unberuehrt weiter)", "dim")
                return 0

    def _batch_ende_melden(self, stt: dict, rd: Path, b: int) -> None:
        """Batch-Ende zeigen - auch im Pausenzustand (R13e).

        Vorher erschien nach /pause nur noch die Telegram-Meldung; im watch-Fenster
        fehlte das Ende des laufenden Batches. Ausserdem blieb `review_shown` ueber
        Batches hinweg gesetzt, sodass ab dem zweiten Batch gar kein Ende mehr kam.
        """
        self._print_stats(force=True)
        self._summary(read_json(rd / "result.json", {}) or {})
        if stt.get("paused"):
            self._p(f"PAUSIERT - Batch {b} ist beendet, der Review zu Batch {b} "
                    "steht aus (startet erst nach /resume).", "yellow")
        else:
            self._p("(Review folgt - er laeuft als eigener Zustand)", "dim")
        self.review_shown = True

    def _summary(self, res: dict):
        if not res:
            return
        t = res.get("stats") or {}
        self._p("")
        self._p("-" * 70, "dim")
        self._p(f"Batch {res.get('batch')}: rc={res.get('rc')} · "
                f"{float(res.get('duration_s') or 0):.0f}s · "
                f"{t.get('requests')} Anfragen · ${float(res.get('cost_usd') or 0):.4f} · "
                f"Modell {res.get('model_seen')} (ok={res.get('model_ok')})", "bold")
        if res.get("alarms"):
            self._p("ALARM: " + "; ".join(res["alarms"]), "yellow")
        if res.get("killed_reason"):
            grund = str(res["killed_reason"])
            if grund.startswith("nachgerechnet"):
                self._p("Hinweis: " + grund, "yellow")
            else:
                self._p("Grenze ausgeloest: " + grund, "red")
        if t.get("denials"):
            self._p("Ablehnungen: " + str(t["denials"])[:300], "yellow")
        self._p("-" * 70, "dim")
