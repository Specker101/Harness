"""Konfiguration (harness.toml) + Projektgewohnheiten (AGENTS.md-Anker)."""

from __future__ import annotations

import tomllib
from pathlib import Path

CONFIG_DEFAULT = Path("g:/Harness/harness/harness.toml")


class Config:
    def __init__(self, data: dict, path: Path):
        self.data = data
        self.path = path

    # ------------------------------------------------------------ Zugriff
    def section(self, name: str) -> dict:
        return self.data.get(name, {}) or {}

    def get(self, section: str, key: str, default=None):
        return self.section(section).get(key, default)

    # ------------------------------------------------------------- Pfade
    @property
    def root(self) -> Path:
        return Path(self.get("paths", "root", "g:/Harness/harness"))

    @property
    def decomp(self) -> Path:
        return Path(self.get("paths", "decomp", "g:/Silent Scope Decomp"))

    @property
    def secrets_dir(self) -> Path:
        return Path(self.get("paths", "secrets", "g:/Harness/secrets"))

    @property
    def prompts_dir(self) -> Path:
        return Path(self.get("paths", "prompts", str(self.root / "prompts")))

    @property
    def backups_dir(self) -> Path:
        return Path(self.get("paths", "backups", "g:/Harness/backups"))

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
