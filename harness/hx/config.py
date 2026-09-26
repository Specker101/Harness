"""Konfiguration (harness.toml) + Projektgewohnheiten (AGENTS.md-Anker)."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

CONFIG_DEFAULT = Path("g:/Harness/harness/harness.toml")

# Umgebungsvariablen, die in Pfaden erlaubt sind. `$USERPROFILE` wird gebraucht,
# seit die Schluesseldateien AUSSERHALB des Harness-Ordners liegen (Option 3,
# 2026-09-26). Ohne Aufloesung waere der Pfad an einen Benutzernamen gebunden und
# der Workspace nicht mehr kopierbar (vgl. die Rechnerwechsel-Regeln in AGENTS.md).
_ENV_NAMEN = ("USERPROFILE", "APPDATA", "LOCALAPPDATA", "USERNAME")


def expand_path(value: str) -> str:
    """`$USERPROFILE`, `${USERPROFILE}` und `%USERPROFILE%` aus der Umgebung ersetzen."""
    out = str(value)
    for name in _ENV_NAMEN:
        wert = os.environ.get(name, "")
        if not wert:
            continue
        out = (out.replace(f"${{{name}}}", wert).replace(f"${name}", wert)
                  .replace(f"%{name}%", wert))
    return out


class Config:
    def __init__(self, data: dict, path: Path):
        self.data = data
        self.path = path

    # ------------------------------------------------------------ Zugriff
    def section(self, name: str) -> dict:
        return self.data.get(name, {}) or {}

    def get(self, section: str, key: str, default=None):
        return self.section(section).get(key, default)

    def pfad(self, key: str, default: str) -> Path:
        """Pfad aus [paths] mit Umgebungsvariablen-Aufloesung."""
        return Path(expand_path(str(self.get("paths", key, default))))

    # ------------------------------------------------------------- Pfade
    @property
    def root(self) -> Path:
        return self.pfad("root", "g:/Harness/harness")

    @property
    def decomp(self) -> Path:
        return self.pfad("decomp", "g:/Silent Scope Decomp")

    @property
    def secrets_dir(self) -> Path:
        return self.pfad("secrets", "$USERPROFILE/.hx-secrets")

    @property
    def prompts_dir(self) -> Path:
        return self.pfad("prompts", str(self.root / "prompts"))

    @property
    def backups_dir(self) -> Path:
        return self.pfad("backups", "g:/Harness/backups")

    def sub(self, name: str) -> Path:
        """Unterordner des Harness (state, logs, inbox, ...)."""
        return self.root / name

    # ------------------------------------------------------------ Anker
    @property
    def anchor_file(self) -> Path:
        """Ankerdatei des aktiven Workstreams (Projektkonvention)."""
        return self.decomp / "analysis" / "r1b-workstream.md"

    @property
    def notes_file(self) -> Path:
        return self.decomp / "analysis" / "ghidra-mcp-notes.md"

    @property
    def agents_file(self) -> Path:
        return self.decomp / "AGENTS.md"


def load_config(path: str | Path | None = None) -> Config:
    p = Path(path) if path else CONFIG_DEFAULT
    with open(p, "rb") as fh:
        data = tomllib.load(fh)
    return Config(data, p)
