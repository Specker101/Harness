"""Zugangsdaten: lesen, niemals ausgeben. Nur Fingerabdruecke duerfen in Logs."""

from __future__ import annotations

import hashlib
from pathlib import Path

# Dateiname -> Verwendungszweck
DEEPSEEK = "deepseek.key"          # Worker: ANTHROPIC_AUTH_TOKEN
TELEGRAM = "telegram.key"          # Bot-Token
CLAUDE_OAUTH = "claude-oauth.token"  # Reviewer: CLAUDE_CODE_OAUTH_TOKEN


class SecretError(RuntimeError):
    pass


def load(secrets_dir: str | Path, name: str) -> str:
    p = Path(secrets_dir) / name
    if not p.is_file():
        raise SecretError(f"Secret fehlt: {name}")
    value = p.read_text(encoding="utf-8-sig").strip()
    if not value:
        raise SecretError(f"Secret ist leer: {name}")
    return value


def fingerprint(value: str) -> str:
    """Nur der Fingerabdruck darf je in Logs/Telegram auftauchen."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]


def looks_like_secret(text: str, secrets: list[str]) -> bool:
    """Prueft einen Text auf enthaltene Secret-Werte (fuer den Leck-Test)."""
    for s in secrets:
        if s and len(s) >= 8 and s in text:
            return True
    return False


def secret_names_in(text: str, secrets: dict[str, str]) -> list[str]:
    """Welche Secrets tauchen im Text auf? (Rueckgabe: Namen, nie Werte)"""
    hits = []
    for name, value in secrets.items():
        if value and len(value) >= 8 and value in text:
            hits.append(name)
    return hits


def redact(text: str, secrets: dict[str, str]) -> str:
    out = text
    for value in secrets.values():
        if value and len(value) >= 8:
            out = out.replace(value, "<REDACTED>")
    return out
