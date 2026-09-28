"""Lokale Steuerung ohne Telegram.

Warum Dateien und nicht direkt der Zustand: der laufende Harness hält
`state/run.json` im Speicher und schreibt sie bei jeder Änderung. Würde ein
zweiter Prozess dieselbe Datei ändern, überschriebe der Harness die Änderung
beim nächsten Speichern. Deshalb legt die lokale Steuerung **Auftragsdateien**
unter `state/ctl/` ab; der Harness liest sie in seiner Schleife und löscht sie
dabei ("take"). Nur der Harness schreibt den Zustand.

Befehle: pause · resume · stop · approve · instruction
"""

from __future__ import annotations

import json
from pathlib import Path

from .util import ensure_dir, now_iso, read_text, write_text_atomic

NAMES = ("pause", "resume", "stop", "approve", "number", "meta")


def ctl_dir(root: str | Path) -> Path:
    d = Path(root) / "ctl"
    return ensure_dir(d)


def put(cfg, name: str, content: str = "") -> Path:
    """Legt einen Steuerbefehl ab (atomar)."""
    if name not in NAMES:
        raise ValueError(f"unbekannter Steuerbefehl: {name}")
    p = write_text_atomic(ctl_dir(cfg.sub("state")) / f"{name}.ctl", content or "")
    return p


def take(cfg, name: str) -> str | None:
    """Liest und löscht einen Steuerbefehl. None = nicht vorhanden."""
    p = ctl_dir(cfg.sub("state")) / f"{name}.ctl"
    if not p.is_file():
        return None
    try:
        text = read_text(p)
    except OSError:
        text = ""
    try:
        p.unlink()
    except OSError:
        pass
    return text


def pending(cfg) -> list[str]:
    d = ctl_dir(cfg.sub("state"))
    return sorted(p.stem for p in d.glob("*.ctl"))


# --------------------------------------------------------- eigene Instruktion

def put_instruction(cfg, instruction: str, profile: str, program: str | None,
                    source_file: str = "") -> Path:
    obj = {
        "ts": now_iso(),
        "instruction": instruction,
        "profile": profile,
        "program": program,
        "source_file": source_file,
        "source": "user",
    }
    p = write_text_atomic(ctl_dir(cfg.sub("state")) / "instruction.json",
                          json.dumps(obj, ensure_ascii=False, indent=1) + "\n")
    return p


def take_instruction(cfg) -> dict | None:
    p = ctl_dir(cfg.sub("state")) / "instruction.json"
    if not p.is_file():
        return None
    try:
        obj = json.loads(read_text(p))
    except (OSError, json.JSONDecodeError):
        obj = None
    try:
        p.unlink()
    except OSError:
        pass
    return obj if isinstance(obj, dict) else None


# ------------------------------------------------------------------ PID-Datei

def pid_path(cfg) -> Path:
    return Path(cfg.sub("state")) / "harness.pid"


def write_pid(cfg) -> int:
    import os
    pid = os.getpid()
    write_text_atomic(pid_path(cfg), f"{pid}\n{now_iso()}\n")
    return pid


def read_pid(cfg) -> int | None:
    p = pid_path(cfg)
    if not p.is_file():
        return None
    try:
        return int(read_text(p).splitlines()[0].strip())
    except (OSError, ValueError, IndexError):
        return None


def clear_pid(cfg) -> None:
    try:
        pid_path(cfg).unlink()
    except OSError:
        pass


def runner_alive(cfg) -> bool:
    from .state import pid_alive
    pid = read_pid(cfg)
    return bool(pid and pid_alive(pid))
