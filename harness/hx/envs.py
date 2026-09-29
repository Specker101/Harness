"""Prozessumgebungen: Whitelist statt Vererbung, Vorher-Pruefung, Nachher-Pruefung.

Regel (E3): Der Harness baut die Umgebung des Kindprozesses NEU auf - er erbt
nichts. Nur so kann kein Abo-Token in den Worker und kein DeepSeek-Token in den
Reviewer lecken. Vorher wird geprueft, dass die verbotenen Namen NICHT gesetzt
sind; nachher wird das tatsaechlich verwendete Modell aus der Ausgabe gelesen.
"""

from __future__ import annotations

import os
from pathlib import Path

# Basisvariablen, die Windows und die Werkzeugkette brauchen (keine Zugangsdaten).
BASE_KEYS = [
    "PATH", "PATHEXT", "SystemRoot", "SystemDrive", "windir", "ComSpec",
    "TEMP", "TMP", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA",
    "PROGRAMFILES", "PROGRAMFILES(X86)", "PROCESSOR_ARCHITECTURE", "NUMBER_OF_PROCESSORS",
    "OS", "HOME", "USERNAME", "COMPUTERNAME", "LANG",
]


def find_msys_ucrt64(environ: dict) -> str | None:
    """`ucrt64\\bin` finden - dieselbe Reihenfolge wie `scripts/port_build.ps1` (R310).

    Damit baut der Worker mit denselben Werkzeugen wie der Nutzer (R11-3):
    `g++ --version` soll 16.2.0 zeigen, nicht MinGW.org 6.3.0.
    """
    cands: list[str] = []
    if environ.get("MSYS_ROOT"):
        cands.append(str(environ["MSYS_ROOT"]))
    if environ.get("USERNAME"):
        cands.append(f"C:\\Users\\{environ['USERNAME']}\\msys64")
    cands += ["C:\\msys64", "C:\\tools\\msys64"]
    try:
        cands += [str(p) for p in Path("C:/Users").glob("*/msys64")]
    except OSError:
        pass
    for c in cands:
        bin_dir = Path(c) / "ucrt64" / "bin"
        if (bin_dir / "g++.exe").is_file():
            return str(bin_dir)
    return None


def resolve_path(cfg, environ: dict) -> tuple[str, list[str]]:
    """PATH fuer Kindprozesse: der geerbte PATH plus konfigurierte Zusaetze.

    Rueckgabe: (PATH, Hinweise). `$MSYS_UCRT64` steht fuer das gesuchte
    Verzeichnis; unbekannte oder fehlende Zusaetze werden GEMELDET, nicht
    verschwiegen.
    """
    base = environ.get("PATH", "")
    hinweise: list[str] = []
    prepend: list[str] = []
    append: list[str] = []
    for raw in list(cfg.get("env", "path_prepend", []) or []):
        raw = str(raw)
        if raw == "$MSYS_UCRT64":
            found = find_msys_ucrt64(environ)
            if found:
                prepend.append(found)
            else:
                hinweise.append("msys2 UCRT64 nicht gefunden - g++ im PATH bleibt der geerbte")
        elif Path(raw).is_dir():
            prepend.append(str(Path(raw)))
        else:
            hinweise.append(f"PATH-Zusatz fehlt: {raw}")
    for raw in list(cfg.get("env", "path_append", []) or []):
        if Path(str(raw)).is_dir():
            append.append(str(Path(raw)))
        else:
            hinweise.append(f"PATH-Zusatz fehlt: {raw}")
    teile = prepend + [p for p in base.split(";") if p] + append
    return ";".join(dict.fromkeys(teile)), hinweise


def toolchain(env: dict) -> list[tuple[str, str]]:
    """Versionen der Werkzeuge messen, die ein Kindprozess mit DIESER Umgebung sieht.

    Wichtig: gestartet wird ueber `cmd /c`. Windows sucht das Programm mit dem PATH
    des ELTERNPROZESSES, wenn man `subprocess` mit `env=` aufruft - die Messung
    haette dann die Kette der Harness-Sitzung gezeigt statt die des Kindes
    (gemessen am Umgebungs-Nachweis: g++ 6.3.0 statt 16.2.0).
    """
    from .proc import run_capture
    out: list[tuple[str, str]] = []
    for name, aufruf in (("g++", "g++ --version"), ("python", "python --version"),
                         ("git", "git --version"), ("mingw32-make", "mingw32-make --version")):
        rc, so, se = run_capture(["cmd", "/c", aufruf], cwd=os.getcwd(), env=env, timeout=60)
        text = (so or se).strip().splitlines()
        first = text[0].strip() if text else "(keine Ausgabe)"
        out.append((name, first if rc == 0 else f"rc={rc}: {first[:80]}"))
    return out


def path_of(env: dict) -> str:
    return str(env.get("PATH", ""))

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
    env["PATH"], _hinweise = resolve_path(cfg, environ)
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
        # R13v (2026-09-28): Zeitgrenzen des Werkzeugs anheben. Gemessen in B207:
        # das Werkzeug kappte bei 600 s und schob den Befehl in den HINTERGRUND
        # ("Command did not complete within its 600s timeout and was moved to the
        # background", runs/b207/stream.jsonl:76897). Der Worker wartete danach in
        # zwei Abfrageschleifen 1083,7 s auf PID 4996. Mit 600 s als STANDARD-Zeit
        # laeuft ein 7- bis 10-Minuten-Lauf synchron in EINEM Aufruf - es gibt keinen
        # Grund mehr, im Hintergrund zu starten und zu pollen.
        # R13ah (Aussensicht B214, Befund 3): die HARTE Obergrenze ist jetzt eine eigene
        # Zahl (`claude.bash_max_timeout_s`, Vorgabe 1800 s). Mit 600 s wurde jeder
        # laengere Aufruf gekappt und in den Hintergrund geschoben (gemessen: preflight
        # 602 s in B213/B214, `mutalle` 601 s in B214) - danach folgten Warteschleifen von
        # 542 s. Die VORGABE fuer Aufrufe ohne eigenes `timeout` bleibt `tool_timeout_ms`.
        "BASH_DEFAULT_TIMEOUT_MS": str(cfg.get("claude", "tool_timeout_ms", 600000)),
        "BASH_MAX_TIMEOUT_MS": str(int(float(cfg.get("claude", "bash_max_timeout_s",
                                                      1800)) * 1000)),
    })
    return env


def reviewer_env(cfg, environ: dict, oauth_token: str) -> dict:
    env = base_env(environ)
    env["PATH"], _hinweise = resolve_path(cfg, environ)
    env.update({
        "CLAUDE_CONFIG_DIR": str(cfg.get("claude", "config_dir_reviewer")),
        "CLAUDE_CODE_OAUTH_TOKEN": oauth_token,
        "CLAUDE_CODE_EFFORT_LEVEL": str(cfg.get("claude", "reviewer_effort", "high")),
        "CLAUDE_CODE_ALWAYS_ENABLE_EFFORT": "1",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "CLAUDE_CODE_SUBPROCESS_ENV_SCRUB": "1",
        "DISABLE_AUTOUPDATER": "1",
        "DISABLE_UPDATES": "1",
        # R13p: Der Reviewer bekommt das PowerShell-Werkzeug - aber NUR fuer die vier
        # Nur-Lese-Git-Befehle (Erlaubnisliste in reviewer.build_command). Ohne diese
        # Variable hiessen die Regeln `Bash(...)` und es braeuchte Git Bash.
        "CLAUDE_CODE_USE_POWERSHELL_TOOL": "1",
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
                   "CLAUDE_CODE_ALWAYS_ENABLE_EFFORT",
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
