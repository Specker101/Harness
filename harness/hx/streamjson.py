"""stream-json auswerten: deduplizieren, Tokens zaehlen, Kosten rechnen.

Befund aus dem Sandkasten (results-probe.md 2.7): eine API-Antwort erzeugt
MEHRERE assistant-Ereignisse (eines je Inhaltsblock). Ungefiltert summieren sich
die Token dadurch ~2,9-fach. Deshalb: Anfragen werden nach message.id
dedupliziert, Werkzeugaufrufe nach tool_use.id.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from . import pricing

# Punkt 2c (R13e): Der HTTP-Weg auf 127.0.0.1:8089 ist ausdruecklich erlaubt. Er
# kann aber den GEMEINSAMEN Ghidra-Zustand beruehren (Programm wechseln/oeffnen/
# schliessen, Projekt zuruecksetzen, Skript ausfuehren). Das wird nur VERMERKT -
# kein Alarm, keine Sperre.
HTTP_RE = re.compile(r"(?:127\.0\.0\.1|localhost):8089")
HTTP_STATE_ENDPOINTS = (
    "/load_program_from_project", "/load_program", "/switch_program", "/open_program",
    "/close_program", "/open_project", "/close_project", "/create_project",
    "/restore_project", "/archive_project", "/checkin_program",
    "/save_all_programs", "/save_program", "/create_program",
    "/run_script", "/run_ghidra_script", "/script",
    "/import_program", "/import_file", "/export_program",
)
# Nur diese Werkzeuge KOENNEN einen HTTP-Aufruf ausloesen. Ein Read-Ergebnis mit
# einem Dokument, das die Endpunkte zitiert, ist kein Aufruf (gleiche Falle wie
# bei den Ablehnungen - B172/B173).
HTTP_TOOLS = {"PowerShell", "Bash", "Shell", "Write", "Edit", "MultiEdit",
              "NotebookEdit", "Terminal"}


class StreamStats:
    def __init__(self):
        self.session_id: str | None = None
        self.model: str | None = None
        self.models: dict[str, int] = {}
        self.mcp_servers: dict = {}
        self.permission_mode: str | None = None
        self.tools_available: int | None = None

        self._msg_ids: set[str] = set()
        self._by_msg: dict[str, dict] = {}       # message.id -> Eintrag (in place aktualisiert)
        self.requests: list[dict] = []          # je Anfrage: {ts, id, miss, hit, creation, output}
        self._tool_ids: set[str] = set()
        self._tool_names: dict[str, str] = {}   # tool_use.id -> Werkzeugname
        self.tools: list[dict] = []             # je Aufruf: {ts, id, name, input}
        self.tool_counts: dict[str, int] = {}

        self.texts: list[str] = []
        self.tool_results: list[str] = []
        self.reasoning_blocks: int = 0
        self.thinking_tokens: int = 0
        self.denials: list[str] = []
        self.tool_errors: list[dict] = []       # echte Werkzeugfehler: {id, name, text}
        self.http_state: list[dict] = []        # HTTP-Beruehrungen des Ghidra-Zustands
        self.api_errors: list[str] = []
        self.result: dict | None = None
        self.raw_events: int = 0

    # ------------------------------------------------------------------ Feed
    def feed(self, line: str) -> dict | None:
        line = line.strip()
        if not line:
            return None
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(ev, dict):
            return None
        self.raw_events += 1
        etype = ev.get("type")

        if etype == "system" and ev.get("subtype") == "init":
            self.session_id = ev.get("session_id") or self.session_id
            self.model = ev.get("model") or self.model
            if self.model:
                self.models[self.model] = self.models.get(self.model, 0) + 1
            servers = ev.get("mcp_servers")
            if isinstance(servers, list):
                self.mcp_servers = {s.get("name"): s.get("status") for s in servers if isinstance(s, dict)}
            elif isinstance(servers, dict):
                self.mcp_servers = servers
            self.permission_mode = ev.get("permissionMode") or self.permission_mode
            tools = ev.get("tools")
            if isinstance(tools, list):
                self.tools_available = len(tools)

        elif etype == "assistant":
            msg = ev.get("message") or {}
            mid = msg.get("id")
            usage = msg.get("usage") or {}
            if mid:
                eintrag = self._by_msg.get(mid)
                if eintrag is None:
                    eintrag = {"ts": ev.get("timestamp") or "", "id": mid,
                               "model": msg.get("model"), "miss": 0, "hit": 0,
                               "creation": 0, "output": 0, "thinking": 0, "events": 0}
                    self._by_msg[mid] = eintrag
                    self.requests.append(eintrag)
                    if msg.get("model"):
                        self.models[msg["model"]] = self.models.get(msg["model"], 0) + 1
                eintrag["events"] = int(eintrag.get("events") or 0) + 1
                # R11-2: NICHT den ersten Wert nehmen. Eine Antwort erzeugt mehrere
                # assistant-Ereignisse, und die Nutzung waechst darin mit; es gilt
                # das MAXIMUM je message.id (Gegenprobe: usage im result-Ereignis).
                for key, ukey in (("miss", "input_tokens"),
                                  ("hit", "cache_read_input_tokens"),
                                  ("creation", "cache_creation_input_tokens"),
                                  ("output", "output_tokens")):
                    wert = int(usage.get(ukey) or 0)
                    if wert > int(eintrag.get(key) or 0):
                        eintrag[key] = wert
                details = usage.get("output_tokens_details") or {}
                think = int(details.get("thinking_tokens") or 0)
                if think > int(eintrag.get("thinking") or 0):
                    eintrag["thinking"] = think
                if msg.get("model"):
                    eintrag["model"] = msg["model"]
                self.thinking_tokens = sum(int(e.get("thinking") or 0) for e in self.requests)
            for block in (msg.get("content") or []):
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "text":
                    txt = block.get("text") or ""
                    if txt.strip():
                        self.texts.append(txt)
                elif btype in ("thinking", "redacted_thinking"):
                    self.reasoning_blocks += 1
                elif btype == "tool_use":
                    tid = block.get("id")
                    if tid and tid in self._tool_ids:
                        continue
                    if tid:
                        self._tool_ids.add(tid)
                    name = block.get("name") or "?"
                    if tid:
                        self._tool_names[tid] = name
                    self.tools.append({"ts": ev.get("timestamp") or "", "id": tid,
                                       "name": name, "input": block.get("input") or {}})
                    self.tool_counts[name] = self.tool_counts.get(name, 0) + 1
                    if name in HTTP_TOOLS:
                        self._scan_http(json.dumps(block.get("input") or {},
                                                   ensure_ascii=False))

        elif etype == "user":
            # Kann Werkzeugergebnisse oder Verweigerungen tragen.
            content = ((ev.get("message") or {}).get("content")) or []
            for block in (content if isinstance(content, list) else []):
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    body = block.get("content")
                    text = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
                    if text:
                        self.tool_results.append(text[:20000])
                    art = self._fehlerart(block, text)
                    if art:
                        tid = block.get("tool_use_id")
                        self.tool_errors.append({"id": tid,
                                                 "name": self._tool_name(tid),
                                                 "art": art, "text": text[:300]})
                        if art == "gesperrt":
                            self.denials.append(text[:300])

        elif etype == "result":
            self.result = ev
            for d in (ev.get("permission_denials") or []):
                self.denials.append(str(d)[:300])

        return ev

    # ------------------------------------------------------- Fehler erkennen
    def _scan_http(self, text: str) -> None:
        """Vorbeigehende HTTP-Aufrufe auf den Ghidra-Port bemerken (Punkt 2c).

        Kein Alarm und keine Wertung: das ist der dokumentierte Ausweichweg.
        Vermerkt werden nur die Endpunkte, die den gemeinsamen Zustand beruehren.
        """
        if not text or "8089" not in text or not HTTP_RE.search(text):
            return
        for ep in HTTP_STATE_ENDPOINTS:
            if ep in text:
                self.http_state.append({"endpoint": ep, "text": text[:200]})
                return

    def _tool_name(self, tool_use_id) -> str:
        return self._tool_names.get(str(tool_use_id), "?")

    @staticmethod
    def _fehlerart(block: dict, text: str) -> str | None:
        """Art des Werkzeugergebnisses: None = Erfolg, sonst 'gesperrt' oder 'fehler'.

        R13e (gemessen an B172/B173): Die alte Regel suchte den Satz
        "no such tool available" IRGENDWO im Ergebnis. Liest der Worker ein
        Dokument, das diesen Satz zitiert (Batch-Dokument, ghidra-mcp-notes.md),
        landete der DATEIINHALT als "abgelehnter Werkzeugaufruf" in der Bilanz -
        B173 meldete so vier Ablehnungen, von denen genau eine echt war. Ein
        echtes Fehlerergebnis traegt den Wrapper <tool_use_error> oder is_error.
        """
        if not text and not block.get("is_error"):
            return None
        low = text.lower()
        # R13e: drei Formulierungen bedeuten "gesperrt": das Werkzeug ist gar nicht
        # vorhanden, im Client abgeschaltet, oder es braucht eine Freigabe, die es
        # hier nicht gibt (headless ohne Rueckfrage). Die dritte Form war die
        # haeufigste der Nacht (search_tools/check_tools/load_tool_group).
        gesperrt = ("no such tool available" in low
                    or "disabled for this session" in low
                    or "requires approval" in low
                    or "permission for this tool use was denied" in low)
        if text.lstrip().startswith("<tool_use_error>"):
            return "gesperrt" if gesperrt else "fehler"
        if block.get("is_error"):
            return "gesperrt" if gesperrt else "fehler"
        return None

    # --------------------------------------------------------------- Auswertung
    def output_total(self) -> int:
        """Ausgabe-Tokens: Summe je Nachricht, sonst aus dem result-Ereignis.

        Gemessen an B159 (DeepSeek ueber den Anthropic-Endpunkt): die Nutzung der
        assistant-Ereignisse traegt Eingabe und Cache EXAKT, aber KEINE Ausgabe
        (alle 0). Die richtige Gesamtzahl steht im result-Ereignis; sie wird
        genommen, sobald sie groesser ist als die Summe - und die Abweichung
        wird gemeldet, nicht verschwiegen.
        """
        summe = sum(int(r.get("output") or 0) for r in self.requests)
        return max(summe, self.result_usage()["output"])

    def totals(self) -> dict:
        miss = sum(r["miss"] for r in self.requests)
        hit = sum(r["hit"] for r in self.requests)
        creation = sum(r["creation"] for r in self.requests)
        return {"requests": len(self.requests), "input_miss": miss, "cache_read": hit,
                "cache_creation": creation, "output": self.output_total()}

    def cost_usd(self, extra_offpeak_dates: list[str] | None = None) -> float:
        """Kosten nach dem Tarif JEDES Aufrufs (Fenster darf mitten im Batch wechseln).

        Fehlt die Ausgabe in den Ereignissen, wird die Gesamtausgabe gleichmaessig
        auf die Aufrufe verteilt - so bleibt der Tarif je Aufruf wirksam.
        """
        summe_out = sum(int(r.get("output") or 0) for r in self.requests)
        gesamt_out = self.output_total()
        anteil = 0.0
        if gesamt_out > summe_out and self.requests:
            anteil = gesamt_out / len(self.requests)
        total = 0.0
        for r in self.requests:
            dt = None
            ts = r.get("ts") or ""
            if ts:
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
                except ValueError:
                    dt = None
            out = int(r["output"]) if gesamt_out <= summe_out else anteil
            total += pricing.cost_usd(r["miss"], r["hit"], r["creation"], out,
                                      dt, extra_offpeak_dates)
        return round(total, 6)

    def cost_naive_usd(self, extra_offpeak_dates: list[str] | None = None) -> float:
        """Gegenprobe: alles zum JETZIGEN Tarif (fuer die Messdifferenz)."""
        t = self.totals()
        return round(pricing.cost_usd(t["input_miss"], t["cache_read"], t["cache_creation"],
                                      t["output"], None, extra_offpeak_dates), 6)

    # ------------------------------------------------- Nutzung: Gegenprobe
    def result_usage(self) -> dict:
        """Nutzung aus dem result-Ereignis (Gesamtlauf laut Claude Code)."""
        u = (self.result or {}).get("usage") or {}
        return {"input_miss": int(u.get("input_tokens") or 0),
                "cache_read": int(u.get("cache_read_input_tokens") or 0),
                "cache_creation": int(u.get("cache_creation_input_tokens") or 0),
                "output": int(u.get("output_tokens") or 0)}

    def usage_check(self, tolerance: float = 0.01) -> dict:
        """Summe je Nachricht gegen das result-Ereignis stellen (R11-2).

        Stimmt beides ueberein, ist die Zaehlung belegt. Weicht es ab, wird das
        GEMELDET - nicht stillschweigend eine der beiden Zahlen benutzt.
        """
        summe = self.totals()
        res = self.result_usage()
        if not any(res.values()):
            return {"ok": None, "hinweis": "kein result-Ereignis mit usage"}
        diff = {k: int(summe[k]) - int(res[k]) for k in res}
        summe_ereignisse = sum(int(r.get("output") or 0) for r in self.requests)
        ok = all(abs(d) <= max(2, int(tolerance * max(1, abs(res[k])))) for k, d in diff.items())
        return {"ok": bool(ok),
                "summe": {k: int(summe[k]) for k in res},
                "result": res, "diff": diff,
                "quelle_output": "ereignisse" if summe_ereignisse >= res["output"] else "result"}

    def final_text(self) -> str:
        if self.result and isinstance(self.result.get("result"), str) and self.result["result"].strip():
            return self.result["result"]
        return "\n\n".join(self.texts).strip()

    def is_error(self) -> bool:
        return bool(self.result and self.result.get("is_error"))

    def terminal_reason(self) -> str | None:
        return (self.result or {}).get("terminal_reason")

    def num_turns(self) -> int | None:
        v = (self.result or {}).get("num_turns")
        return int(v) if isinstance(v, int) else None

    def total_cost_usd_field(self) -> float | None:
        v = (self.result or {}).get("total_cost_usd")
        return float(v) if isinstance(v, (int, float)) else None

    def duration_field(self) -> tuple[float | None, str]:
        """Die vom Worker-Prozess SELBST gemeldete Laufzeit + ihre Herkunft (R13c).

        `duration_ms` ist die Wanduhr-Zeit des `claude`-Prozesses, `duration_api_ms`
        nur die darin verbrachte API-Zeit. Fuer die Bilanz ist die Wanduhr massgeblich:
        B159 stand mit `duration_api_ms` (288 s) in der Bilanz, waehrend der Prozess
        377 s lief - der Unterschied ist Ausfuehrungszeit im Kind (Werkzeuge, Rueckstau).
        """
        r = self.result or {}
        for key in ("duration_ms", "duration_api_ms"):
            v = r.get(key)
            if isinstance(v, (int, float)) and v > 0:
                return round(float(v) / 1000.0, 3), key
        return None, ""

    def tool_table(self) -> list[tuple[str, int]]:
        return sorted(self.tool_counts.items(), key=lambda kv: (-kv[1], kv[0]))

    def repeated_calls(self) -> list[tuple[str, int]]:
        """Identische Aufrufe (Name + Argumente) - Signal fuer den Watchdog (Spaeter)."""
        seen: dict[str, int] = {}
        for t in self.tools:
            key = t["name"] + "|" + json.dumps(t["input"], sort_keys=True, ensure_ascii=False)
            seen[key] = seen.get(key, 0) + 1
        return sorted(((k, v) for k, v in seen.items() if v > 1), key=lambda kv: -kv[1])
