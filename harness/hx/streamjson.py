"""stream-json auswerten: deduplizieren, Tokens zaehlen, Kosten rechnen.

Befund aus dem Sandkasten (results-probe.md 2.7): eine API-Antwort erzeugt
MEHRERE assistant-Ereignisse (eines je Inhaltsblock). Ungefiltert summieren sich
die Token dadurch ~2,9-fach. Deshalb: Anfragen werden nach message.id
dedupliziert, Werkzeugaufrufe nach tool_use.id.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from . import pricing


class StreamStats:
    def __init__(self):
        self.session_id: str | None = None
        self.model: str | None = None
        self.models: dict[str, int] = {}
        self.mcp_servers: dict = {}
        self.permission_mode: str | None = None
        self.tools_available: int | None = None

        self._msg_ids: set[str] = set()
        self.requests: list[dict] = []          # je Anfrage: {ts, id, miss, hit, creation, output}
        self._tool_ids: set[str] = set()
        self.tools: list[dict] = []             # je Aufruf: {ts, id, name, input}
        self.tool_counts: dict[str, int] = {}

        self.texts: list[str] = []
        self.tool_results: list[str] = []
        self.reasoning_blocks: int = 0
        self.thinking_tokens: int = 0
        self.denials: list[str] = []
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
            if mid and mid not in self._msg_ids:
                self._msg_ids.add(mid)
                usage = msg.get("usage") or {}
                details = usage.get("output_tokens_details") or {}
                self.thinking_tokens += int(details.get("thinking_tokens") or 0)
                self.requests.append({
                    "ts": ev.get("timestamp") or "",
                    "id": mid,
                    "model": msg.get("model"),
                    "miss": int(usage.get("input_tokens") or 0),
                    "hit": int(usage.get("cache_read_input_tokens") or 0),
                    "creation": int(usage.get("cache_creation_input_tokens") or 0),
                    "output": int(usage.get("output_tokens") or 0),
                })
                if msg.get("model"):
                    self.models[msg["model"]] = self.models.get(msg["model"], 0) + 1
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
                    self.tools.append({"ts": ev.get("timestamp") or "", "id": tid,
                                       "name": name, "input": block.get("input") or {}})
                    self.tool_counts[name] = self.tool_counts.get(name, 0) + 1

        elif etype == "user":
            # Kann Werkzeugergebnisse oder Verweigerungen tragen.
            content = ((ev.get("message") or {}).get("content")) or []
            for block in (content if isinstance(content, list) else []):
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    body = block.get("content")
                    text = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
                    if text:
                        self.tool_results.append(text[:20000])
                    if "no such tool available" in text.lower() or "disabled for this session" in text.lower():
                        self.denials.append(text[:300])

        elif etype == "result":
            self.result = ev
            for d in (ev.get("permission_denials") or []):
                self.denials.append(str(d)[:300])

        return ev

    # --------------------------------------------------------------- Auswertung
    def totals(self) -> dict:
        miss = sum(r["miss"] for r in self.requests)
        hit = sum(r["hit"] for r in self.requests)
        creation = sum(r["creation"] for r in self.requests)
        output = sum(r["output"] for r in self.requests)
        return {"requests": len(self.requests), "input_miss": miss, "cache_read": hit,
                "cache_creation": creation, "output": output}

    def cost_usd(self, extra_offpeak_dates: list[str] | None = None) -> float:
        """Kosten nach dem Tarif JEDES Aufrufs (Fenster darf mitten im Batch wechseln)."""
        total = 0.0
        for r in self.requests:
            dt = None
            ts = r.get("ts") or ""
            if ts:
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
                except ValueError:
                    dt = None
            total += pricing.cost_usd(r["miss"], r["hit"], r["creation"], r["output"],
                                      dt, extra_offpeak_dates)
        return round(total, 6)

    def cost_naive_usd(self, extra_offpeak_dates: list[str] | None = None) -> float:
        """Gegenprobe: alles zum JETZIGEN Tarif (fuer die Messdifferenz)."""
        t = self.totals()
        return round(pricing.cost_usd(t["input_miss"], t["cache_read"], t["cache_creation"],
                                      t["output"], None, extra_offpeak_dates), 6)

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

    def tool_table(self) -> list[tuple[str, int]]:
        return sorted(self.tool_counts.items(), key=lambda kv: (-kv[1], kv[0]))

    def repeated_calls(self) -> list[tuple[str, int]]:
        """Identische Aufrufe (Name + Argumente) - Signal fuer den Watchdog (Spaeter)."""
        seen: dict[str, int] = {}
        for t in self.tools:
            key = t["name"] + "|" + json.dumps(t["input"], sort_keys=True, ensure_ascii=False)
            seen[key] = seen.get(key, 0) + 1
        return sorted(((k, v) for k, v in seen.items() if v > 1), key=lambda kv: -kv[1])
