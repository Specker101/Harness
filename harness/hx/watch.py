"""Live-Ansicht: `hx.cli watch` — rein lesend.

Zeigt den laufenden Batch mit: Texte des Workers, Werkzeugaufrufe in Kurzform,
Ablehnungen, laufende Kosten/Anfragen/Laufzeit; am Ende die Reviewer-Antwort.

Grundsatz: **nur lesen**. Es werden ausschließlich Dateien geöffnet, die der
Harness ohnehin schreibt; es gibt keine Sperren, keine Schreibvorgänge, und das
Schließen des Fensters beendet nur diesen Zuschauer (KeyboardInterrupt).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from . import protocol, streamjson
from .util import read_json, read_text

RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
CYAN = "\x1b[36m"
YELLOW = "\x1b[33m"
RED = "\x1b[31m"
GREEN = "\x1b[32m"


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
                 follow: bool | None = None):
        self.cfg = cfg
        self.log = log
        self.batch = batch
        self.run_name = run          # NICHT self.run: das ist die Methode run()
        self.stats = streamjson.StreamStats()
        self.seen = 0
        self.review_shown = False
        self.started = time.time()

    # ------------------------------------------------------------------ Helfer
    def _run_dir(self) -> Path:
        if self.run_name:
            p = Path(self.run_name)
            return p if p.is_absolute() or "/" in self.run_name or "\\" in self.run_name \
                else Path(self.cfg.sub("runs")) / self.run_name
        b = self.batch
        if b in (None, 0):
            state = read_json(Path(self.cfg.sub("state")) / "run.json", {}) or {}
            b = int(state.get("last_batch_number") or state.get("batch") or 0)
        return Path(self.cfg.sub("runs")) / f"b{int(b or 0):03d}"

    def _follow(self) -> bool:
        if self.batch or self.run_name:
            return False          # ein abgeschlossener Lauf wird nachgespielt
        return True

    # ---------------------------------------------------------------- Ausgabe
    @staticmethod
    def _p(text: str = "", color: str = ""):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
        print((color + text + RESET) if color else text, flush=True)

    def _render_line(self, line: str):
        obj = self.stats.feed(line)
        if not obj:
            return
        t = obj.get("type")
        if t == "assistant":
            for block in ((obj.get("message") or {}).get("content") or []):
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and (block.get("text") or "").strip():
                    self._p("")
                    self._p("WORKER:", BOLD)
                    self._p(block["text"].strip())
                elif block.get("type") == "tool_use":
                    self._p("  > " + _fmt_tool(str(block.get("name")), block.get("input") or {}), CYAN)
        elif t == "user":
            for block in ((obj.get("message") or {}).get("content") or []):
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    body = block.get("content")
                    text = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
                    low = text.lower()
                    if "no such tool available" in low or "disabled for this session" in low:
                        self._p("  x ABGELEHNT: " + _clip(text, 160), RED)
                    elif block.get("is_error"):
                        self._p("  ! Fehler: " + _clip(text, 160), YELLOW)
        elif t == "result":
            self._p("")
            self._p("--- Worker beendet ---", DIM)

    def _print_stats(self):
        t = self.stats.totals()
        if not t["requests"]:
            return
        cost = self.stats.cost_usd(list(self.cfg.get("peak", "extra_offpeak_dates", []) or []))
        up = time.time() - self.started
        self._p(f"[{time.strftime('%H:%M:%S')}] laufend: {t['requests']} Anfragen · "
                f"{t['input_miss']} ein / {t['cache_read']} cache / {t['output']} aus · "
                f"${cost:.4f} · {up / 60:.1f} min", DIM)

    def _print_review(self):
        rd = self._run_dir()
        review = rd / "review.md"
        if not review.is_file():
            files = sorted(Path(self.cfg.sub("logs")).glob("review-*.md"))
            if not files:
                return
            review = files[-1]
        text = read_text(review)
        parsed = protocol.parse_review(text)
        self._p("")
        self._p("=" * 70, DIM)
        self._p("REVIEWER", BOLD)
        self._p("=" * 70, DIM)
        if parsed.summary:
            self._p("Zusammenfassung (TELEGRAM_SUMMARY):", BOLD)
            self._p(parsed.summary)
        if parsed.decision:
            self._p(f"Entscheidung: {parsed.decision}", GREEN if parsed.decision == "CONTINUE" else YELLOW)
        if parsed.profile or parsed.program:
            self._p(f"Werkzeuge: Profil {parsed.profile or '-'}, Programm {parsed.program or '-'}")
        if parsed.instruction:
            self._p("")
            self._p("Instruktion (DS_INSTRUCTION):", BOLD)
            self._p(parsed.instruction)
        if parsed.issues:
            self._p("Hinweise: " + "; ".join(parsed.issues), YELLOW)
        self.review_shown = True

    # ------------------------------------------------------------------- Lauf
    def run(self) -> int:
        rd = self._run_dir()
        stream = rd / "stream.jsonl"
        self._p(f"watch: {rd.name}  ({'nachspielen' if not self._follow() else 'live'})", BOLD)
        if not stream.is_file() and not (rd / "result.json").is_file():
            self._p(f"(noch kein Mitschnitt unter {stream})", YELLOW)
            return 1

        if stream.is_file():
            with open(stream, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.read().splitlines()
            for line in lines:
                self._render_line(line)
            self.seen = len(lines)

        if not self._follow():
            res = read_json(rd / "result.json", {}) or {}
            self._print_stats()
            self._summary(res)
            self._print_review()
            if not res:
                self._p("(fuer diesen Lauf gibt es keine Kennzahlen-Datei - "
                        "gezeigt wurde der Mitschnitt selbst)", YELLOW)
            return 0

        # Live: neuen Zeilen folgen, bis der Batch fertig ist.
        last_growth = time.time()
        idle_printed = False
        while True:
            try:
                time.sleep(1.5)
                if stream.is_file():
                    with open(stream, "r", encoding="utf-8", errors="replace") as fh:
                        alle = fh.read().splitlines()
                    if len(alle) > self.seen:
                        for line in alle[self.seen:]:
                            self._render_line(line)
                        self.seen = len(alle)
                        last_growth = time.time()
                        if int(self.stats.totals()["requests"]) % 5 == 0:
                            self._print_stats()
                fertig = (rd / "result.json").is_file()
                if fertig and self.stats.result and not self.review_shown:
                    self._p("")
                    self._summary(read_json(rd / "result.json", {}) or {})
                    # Kurz auf das Review warten (es entsteht nach dem Batch).
                    for _ in range(40):
                        time.sleep(1.5)
                        if (rd / "review.md").is_file():
                            break
                    self._print_review()
                    return 0
                if not fertig and (time.time() - last_growth) > 900:
                    self._p("(15 min keine neuen Ereignisse - Zuschauer beendet sich)", YELLOW)
                    return 0
                if not fertig and not idle_printed and (time.time() - self.started) > 20:
                    self._p("(warte auf neue Ereignisse ...)", DIM)
                    idle_printed = True
            except KeyboardInterrupt:
                self._p("(watch beendet - der Harness laeuft unberuehrt weiter)", DIM)
                return 0

    def _summary(self, res: dict):
        if not res:
            return
        t = res.get("stats") or {}
        self._p("")
        self._p("-" * 70, DIM)
        self._p(f"Batch {res.get('batch')}: rc={res.get('rc')} · "
                f"{float(res.get('duration_s') or 0):.0f}s · "
                f"{t.get('requests')} Anfragen · ${float(res.get('cost_usd') or 0):.4f} · "
                f"Modell {res.get('model_seen')} (ok={res.get('model_ok')})", BOLD)
        if res.get("alarms"):
            self._p("ALARM: " + "; ".join(res["alarms"]), YELLOW)
        if res.get("killed_reason"):
            self._p("Grenze ausgeloest: " + str(res["killed_reason"]), RED)
        if t.get("denials"):
            self._p("Ablehnungen: " + str(t["denials"])[:300], YELLOW)
        self._p("-" * 70, DIM)
