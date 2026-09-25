"""Prozessumgebungen: Whitelist statt Vererbung, Vorher-Pruefung, Nachher-Pruefung.

Regel (E3): Der Harness baut die Umgebung des Kindprozesses NEU auf - er erbt
nichts. Nur so kann kein Abo-Token in den Worker und kein DeepSeek-Token in den
Reviewer lecken. Vorher wird geprueft, dass die verbotenen Namen NICHT gesetzt
sind; nachher wird das tatsaechlich verwendete Modell aus der Ausgabe gelesen.
"""

from __future__ import annotations

# Basisvariablen, die Windows und die Werkzeugkette brauchen (keine Zugangsdaten).
BASE_KEYS = [
    "PATH", "PATHEXT", "SystemRoot", "SystemDrive", "windir", "ComSpec",
    "TEMP", "TMP", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA",
    "PROGRAMFILES", "PROGRAMFILES(X86)", "PROCESSOR_ARCHITECTURE", "NUMBER_OF_PROCESSORS",
    "OS", "HOME", "USERNAME", "COMPUTERNAME", "LANG",
]

# Verbote: Worker darf kein Claude-Abo-Token und keinen Anthropic-API-Key sehen.
FORBIDDEN_WORKER = ["CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY", "ANTHROPIC_DEFAULT_MODEL",
                    "ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL",
                    "ANTHROPIC_DEFAULT_HAIKU_MODEL"]
# Reviewer darf nicht versehentlich auf DeepSeek umgelenkt werden.
FORBIDDEN_REVIEWER = ["ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY",
                      "ANTHROPIC_MODEL", "ANTHROPIC_DEFAULT_MODEL", "CLAUDE_CODE_SIMPLE"]


def base_env(environ: dict) -> dict:
    return {k: environ[k] for k in BASE_KEYS if k in environ}


def worker_env(cfg, environ: dict, token: str) -> dict:
    env = base_env(environ)
    env.update({
        "CLAUDE_CONFIG_DIR": str(cfg.get("claude", "config_dir_worker")),
        "ANTHROPIC_BASE_URL": str(cfg.get("claude", "base_url")),
        "ANTHROPIC_AUTH_TOKEN": token,
        # ANTHROPIC_MODEL wird ABSICHTLICH nicht gesetzt: das Modell kommt ueber
        # `--model` (R16-Befund: die Variable waere sonst in Unterskripten sichtbar).
        "CLAUDE_CODE_EFFORT_LEVEL": "high",
        "CLAUDE_CODE_ALWAYS_ENABLE_EFFORT": "1",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "CLAUDE_CODE_USE_POWERSHELL_TOOL": "1",
        # R16: Zugangsdaten aus Unterskripten (PowerShell-Werkzeug, Hooks, MCP-stdio) entfernen.
        "CLAUDE_CODE_SUBPROCESS_ENV_SCRUB": "1",
        # R15/E6: Auto-Update aus, damit die Version stabil bleibt.
        "DISABLE_AUTOUPDATER": "1",
        "DISABLE_UPDATES": "1",
    })
    return env


def reviewer_env(cfg, environ: dict, oauth_token: str) -> dict:
    env = base_env(environ)
    env.update({
        "CLAUDE_CONFIG_DIR": str(cfg.get("claude", "config_dir_reviewer")),
        "CLAUDE_CODE_OAUTH_TOKEN": oauth_token,
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "CLAUDE_CODE_SUBPROCESS_ENV_SCRUB": "1",
        "DISABLE_AUTOUPDATER": "1",
        "DISABLE_UPDATES": "1",
        # Kein PowerShell-Werkzeug fuer den Reviewer (er hat nur Read/Grep/Glob).
    })
    return env


def missing_critical(env: dict, required: list[str]) -> list[str]:
    return [k for k in required if not env.get(k)]


def precheck(env: dict, role: str) -> list[str]:
    """Gibt die Namen verbotener Variablen zurueck, die gesetzt sind (soll: leer)."""
    forbidden = FORBIDDEN_WORKER if role == "worker" else FORBIDDEN_REVIEWER
    hits = [k for k in forbidden if env.get(k)]
    # Zusaetzlich: kein fremdes Modell/Token ueber Umweg
    if role == "worker" and env.get("CLAUDE_CODE_OAUTH_TOKEN"):
        hits.append("CLAUDE_CODE_OAUTH_TOKEN")
    if role == "reviewer" and env.get("ANTHROPIC_AUTH_TOKEN"):
        hits.append("ANTHROPIC_AUTH_TOKEN")
    return sorted(set(hits))


def describe(env: dict) -> str:
    """Logbare Kurzbeschreibung: Namen + ob gesetzt, NIE Werte."""
    interesting = ["CLAUDE_CONFIG_DIR", "ANTHROPIC_BASE_URL", "ANTHROPIC_MODEL",
                   "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY",
                   "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_EFFORT_LEVEL",
                   "CLAUDE_CODE_SUBPROCESS_ENV_SCRUB", "CLAUDE_CODE_USE_POWERSHELL_TOOL"]
    parts = []
    for k in dict.fromkeys(interesting):
        v = env.get(k)
        if v is None:
            parts.append(f"{k}=<nicht gesetzt>")
        elif "TOKEN" in k or "KEY" in k:
            parts.append(f"{k}=<gesetzt,len={len(v)}>")
        else:
            parts.append(f"{k}={v}")
    return "; ".join(parts)
