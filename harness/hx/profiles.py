"""Werkzeugprofile (E4/R7b): Built-ins fest, Ghidra-Profil steuert nur MCP.

Die Profildateien liegen in <root>/profiles/*.json und werden von
tools/make_profiles.py aus dem Werkzeugkatalog (_ghidra_schema.json) erzeugt
und danach von Hand geprueft.
"""

from __future__ import annotations

import json
from pathlib import Path

# Built-ins: der Worker darf IMMER Dateien bearbeiten, Git und PowerShell nutzen,
# unabhaengig vom Ghidra-Profil (Entscheidung R7b). Ohne sie kein Port-Batch.
BUILTIN_WORKER = ["Read", "Write", "Edit", "Glob", "Grep", "PowerShell"]
BUILTIN_REVIEWER = ["Read", "Grep", "Glob"]

# Immer gesperrt - auch in "full" (run_ghidra_script/run_script_inline = beliebige
# Codeausfuehrung in Ghidra, Debugger sprechen einen fremden Prozess).
NEVER_ALLOW = [
    "run_ghidra_script",
    "run_script_inline",
]

PROFILES = ("none", "ghidra-read", "ghidra-standard", "ghidra-full")


class ProfileError(RuntimeError):
    pass


class Profile:
    def __init__(self, data: dict, path: Path):
        self.data = data
        self.path = path

    # ------------------------------------------------------------- Zugriff
    @property
    def name(self) -> str:
        return self.data.get("name", "?")

    @property
    def mcp(self) -> bool:
        return bool(self.data.get("mcp", False))

    @property
    def groups(self) -> str:
        return self.data.get("groups", "")

    @property
    def allowed(self) -> list[str]:
        return list(self.data.get("allowed") or [])

    @property
    def denied(self) -> list[str]:
        return list(self.data.get("denied") or [])

    @property
    def writes_ghidra(self) -> bool:
        """True, wenn dieses Profil in die Ghidra-DB schreiben kann (Backup-Pflicht)."""
        return bool(self.data.get("writes_ghidra", False))

    def mcp_names(self, server: str = "ghidra") -> list[str]:
        return [f"mcp__{server}__{n}" for n in self.allowed]

    def mcp_denied_names(self, server: str = "ghidra") -> list[str]:
        return [f"mcp__{server}__{n}" for n in self.denied]

    def summary(self) -> str:
        if not self.mcp:
            return "kein MCP-Server"
        return f"{len(self.allowed)} MCP-Werkzeuge erlaubt, {len(self.denied)} gesperrt, Gruppen={self.groups}"


def load_profile(root: str | Path, name: str) -> Profile:
    if name not in PROFILES:
        raise ProfileError(f"unbekanntes Profil: {name}")
    p = Path(root) / "profiles" / f"{name}.json"
    if not p.is_file():
        raise ProfileError(f"Profildatei fehlt: {p} (tools/make_profiles.py fahren)")
    return Profile(json.loads(p.read_text(encoding="utf-8")), p)


def builtin_args(role: str) -> tuple[str, list[str]]:
    """( --tools-Wert, --allowedTools-Grundliste ) fuer Worker oder Reviewer."""
    names = BUILTIN_WORKER if role == "worker" else BUILTIN_REVIEWER
    return ",".join(names), list(names)


# --------------------------------------------------- pfadgebundene Leseregeln
# GEMESSEN 2026-09-26 (docs/_ask_zugriff_regeln.txt): ein blosses
# `--allowedTools Read` erlaubt das Werkzeug OHNE Pfadbeschraenkung - damit war
# `g:\Harness\secrets\deepseek.key` fuer Reviewer UND Worker lesbar. Wirksam ist
# nur die gebundene Form `Read(//<pfad>/**)` (CLI-Hilfe: 'Bash(git *)').
LESE_ROLLEN = ("Read", "Grep", "Glob")


def pfad_regeln(wurzeln, rollen: tuple[str, ...] = LESE_ROLLEN) -> list[str]:
    """`Read(//g:/Harness/harness/**)` usw. fuer jede Wurzel und jede Rolle."""
    regeln: list[str] = []
    for w in wurzeln:
        p = str(w).replace("\\", "/").rstrip("/")
        regeln += [f"{rolle}(//{p}/**)" for rolle in rollen]
    return regeln


def secrets_verbote(secrets_dir, rollen: tuple[str, ...] = LESE_ROLLEN) -> list[str]:
    """Ausdrueckliches Verbot fuer den secrets-Ordner (Guertel und Hosentraeger).

    Das Verbot greift auch dann, wenn irgendwo versehentlich ein ungebundenes
    `Read` in der Erlaubnisliste steht.
    """
    s = str(secrets_dir).replace("\\", "/").rstrip("/")
    regeln = [f"{rolle}(//{s}/**)" for rolle in rollen]
    regeln += [f"{rolle}({s}/**)" for rolle in rollen]
    return regeln
