"""Protokoll-Parser (Abschnitt F des Plans) - mit Fehlerfaellen.

Erwartete Bloecke des Reviewers:
    <TELEGRAM_SUMMARY>...</TELEGRAM_SUMMARY>
    <DS_TOOLS>profile: ghidra-read / program: /830d01.27p.main.bin</DS_TOOLS>
    <DS_INSTRUCTION>...</DS_INSTRUCTION>
Watchdog:
    <DECISION>CONTINUE|OBSERVE|INTERVENE</DECISION>
    <PROBLEM>...</PROBLEM>      (nur bei OBSERVE/INTERVENE)
Worker-Marker (Rueckkanal):
    <TOOL_REQUEST>...</TOOL_REQUEST>  <PROGRAM_REQUEST>...</PROGRAM_REQUEST>

Grundsatz: NIE raten. Was fehlt, wird gemeldet und der Batch startet nicht.
"""

from __future__ import annotations

import re

TAG_RE = re.compile(r"<([A-Z_]{3,})>(.*?)</\1>", re.DOTALL | re.IGNORECASE)

LIMIT_PATTERNS = [
    r"usage limit", r"limit reached", r"you'?ve hit your", r"rate limit",
    r"out of extra usage", r"resets at", r"quota",
]

PROFILE_ALIASES = {
    "none": "none",
    "ghidra-read": "ghidra-read", "read": "ghidra-read",
    "ghidra-standard": "ghidra-standard", "standard": "ghidra-standard",
    "ghidra-full": "ghidra-full", "full": "ghidra-full",
}

PROGRAM_ALIASES = {
    "main": "/830d01.27p.main.bin",
    "main.bin": "/830d01.27p.main.bin",
    "830d01.27p.main.bin": "/830d01.27p.main.bin",
    "be": "/830d01.27p.be.bin",
    "be.bin": "/830d01.27p.be.bin",
    "830d01.27p.be.bin": "/830d01.27p.be.bin",
}


class Review:
    def __init__(self):
        self.blocks: dict[str, list[str]] = {}
        self.summary: str = ""
        self.instruction: str = ""
        self.decision: str | None = None
        self.problem: str = ""
        self.profile: str | None = None
        self.program: str | None = None
        self.batch: int | None = None
        self.issues: list[str] = []

    @property
    def status(self) -> str:
        if self.issues:
            return "incomplete" if not self.is_usable() else "warning"
        return "ok"

    def is_usable(self) -> bool:
        """Kann daraus ein Batch gestartet werden?"""
        if self.decision in ("OBSERVE", "CONTINUE"):
            return True
        return bool(self.instruction.strip()) and bool(self.profile or self.decision is None)

    def describe(self) -> str:
        parts = [f"status={self.status}"]
        if self.profile:
            parts.append(f"profil={self.profile}")
        if self.program:
            parts.append(f"programm={self.program}")
        if self.decision:
            parts.append(f"entscheidung={self.decision}")
        if self.issues:
            parts.append("probleme=" + "; ".join(self.issues))
        return " ".join(parts)


def _blocks(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for m in TAG_RE.finditer(text or ""):
        tag = m.group(1).upper()
        out.setdefault(tag, []).append(m.group(2).strip())
    return out


def parse_review(text: str) -> Review:
    r = Review()
    r.blocks = _blocks(text)

    def one(tag: str) -> str:
        vals = r.blocks.get(tag) or []
        if len(vals) > 1:
            r.issues.append(f"{tag} mehrfach ({len(vals)}x) - erster Block gilt")
        return vals[0] if vals else ""

    r.summary = one("TELEGRAM_SUMMARY")
    r.instruction = one("DS_INSTRUCTION")
    r.problem = one("PROBLEM")
    r.batch = parse_batch_number(r.instruction)
    if r.instruction and r.batch is None:
        r.issues.append("keine Batch-Nummer in DS_INSTRUCTION gefunden")
    decision = one("DECISION").strip().upper()
    if decision:
        if decision in ("CONTINUE", "OBSERVE", "INTERVENE"):
            r.decision = decision
        else:
            r.issues.append(f"DECISION unbekannt: {decision!r} - wird wie OBSERVE behandelt")
            r.decision = "OBSERVE"

    tools_raw = one("DS_TOOLS")
    if tools_raw:
        profile, program = parse_tools(tools_raw)
        r.profile = profile
        r.program = program
        if profile is None:
            r.issues.append("DS_TOOLS ohne erkennbares Profil")
    elif r.decision is None:
        r.issues.append("DS_TOOLS fehlt")

    if not r.summary and r.decision is None:
        r.issues.append("TELEGRAM_SUMMARY fehlt")
    if not r.instruction and r.decision in (None, "INTERVENE"):
        r.issues.append("DS_INSTRUCTION fehlt")
    if r.decision == "INTERVENE" and not r.instruction:
        r.issues.append("INTERVENE ohne DS_INSTRUCTION")
    if text and not r.blocks:
        r.issues.append("kein einziger Protokollblock gefunden")
    return r


def parse_tools(raw: str) -> tuple[str | None, str | None]:
    """Akzeptiert Key/Value-Zeilen UND die Kurzform 'ghidra-read main'."""
    profile = None
    program = None
    lines = [ln.strip() for ln in (raw or "").splitlines() if ln.strip()]
    kv_seen = False
    for ln in lines:
        if ":" in ln:
            key, _, val = ln.partition(":")
            key = key.strip().lower()
            val = val.strip().strip("`\"'")
            if key in ("profile", "profil"):
                profile = PROFILE_ALIASES.get(val.lower(), val.lower())
                kv_seen = True
            elif key in ("program", "programm"):
                program = PROGRAM_ALIASES.get(val.lower(), val)
                kv_seen = True
    if not kv_seen:
        tokens = re.split(r"[\s,]+", raw.strip())
        tokens = [t for t in tokens if t]
        if tokens:
            profile = PROFILE_ALIASES.get(tokens[0].lower(), tokens[0].lower())
        if len(tokens) > 1:
            program = PROGRAM_ALIASES.get(tokens[1].lower(), tokens[1])
    if profile and profile not in PROFILE_ALIASES.values():
        profile = None
    if program:
        program = "/" + program.lstrip("/").split("/")[-1]
    return profile, program


BATCH_RE = re.compile(r"\bBatch\s*(?:Nr\.?\s*)?(\d{1,4})\b", re.IGNORECASE)
ANCHOR_BATCH_RE = re.compile(r"\bBATCH\s+(\d{1,4})\b")
# Querverweis aus der Zeile "**Naechster Schritt:** ... **B159:** ..." des Ankers.
ANCHOR_NEXT_RE = re.compile(r"\bB\s?(\d{3,4})\b")


def parse_batch_number(text: str) -> int | None:
    """Liest die Batch-Nummer aus einer DS_INSTRUCTION ("Batch 159 - ...")."""
    m = BATCH_RE.search(text or "")
    return int(m.group(1)) if m else None


def parse_anchor_batch(text: str) -> int | None:
    """Liest die Batch-Nummer des Anker-Kopfes ("**Stand:** BATCH 158 ...")."""
    m = ANCHOR_BATCH_RE.search(text or "")
    return int(m.group(1)) if m else None


def parse_anchor_next_hint(text: str) -> int | None:
    """Liest die im Anker genannte NAECHSTE Nummer ("**Naechster Schritt:** (a) **B159:**").

    Nur ein Querverweis zum Anker-Kopf: der Kopf sagt, welcher Batch abgeschlossen
    ist, diese Zeile sagt, welcher als naechster gemeint ist. Gelesen wird die
    ERSTE solche Zeile (der aktuelle Kopf; die ARCHIV-Abschnitte folgen spaeter).
    """
    for line in (text or "").splitlines():
        if "Naechster Schritt" in line:
            h = ANCHOR_NEXT_RE.search(line)
            return int(h.group(1)) if h else None
    return None


def looks_like_limit(text: str) -> bool:
    low = (text or "").lower()
    return any(re.search(p, low) for p in LIMIT_PATTERNS)


def parse_worker_markers(text: str) -> dict:
    b = _blocks(text)
    return {
        "tool_request": [x.strip() for x in (b.get("TOOL_REQUEST") or [])],
        "program_request": [x.strip() for x in (b.get("PROGRAM_REQUEST") or [])],
    }


def summary_for_telegram(text: str, max_len: int = 3500) -> str:
    r = parse_review(text)
    if r.summary:
        out = r.summary
    else:
        out = (text or "").strip()
    if len(out) > max_len:
        out = out[:max_len] + "\n[... gekuerzt, vollstaendig im Archiv]"
    return out
