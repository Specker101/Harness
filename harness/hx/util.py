"""Kleinere Helfer: Pfade, atomares Schreiben, JSONL, Logging (UTF-8)."""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------- Zeit / IDs

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().isoformat(timespec="seconds")


def stamp(compact: bool = False) -> str:
    fmt = "%Y%m%d-%H%M%S" if compact else "%Y-%m-%d %H:%M:%S"
    return datetime.now().strftime(fmt)


def new_id() -> str:
    return uuid.uuid4().hex[:12].upper()


# ------------------------------------------------------------- Dateisystem

def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_text_atomic(path: str | Path, text: str) -> Path:
    """Schreibt ueber eine .tmp-Datei und os.replace -> nie halbe Zustandsdateien."""
    p = Path(path)
    ensure_dir(p.parent)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, p)
    return p


def write_json_atomic(path: str | Path, obj) -> Path:
    return write_text_atomic(path, json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def read_json(path: str | Path, default=None):
    p = Path(path)
    if not p.is_file():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def read_text(path: str | Path, default: str = "") -> str:
    p = Path(path)
    if not p.is_file():
        return default
    return p.read_text(encoding="utf-8", errors="replace")


def append_text(path: str | Path, text: str) -> Path:
    p = Path(path)
    ensure_dir(p.parent)
    with open(p, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return p


def append_jsonl(path: str | Path, obj) -> Path:
    return append_text(path, json.dumps(obj, ensure_ascii=False) + "\n")


def read_jsonl_tolerant(path: str | Path) -> list:
    """Liest JSONL; eine halb geschriebene letzte Zeile wird verworfen."""
    p = Path(path)
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def tail_lines(path: str | Path, n: int) -> list:
    p = Path(path)
    if not p.is_file():
        return []
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-n:]


# ------------------------------------------------------------------- Logging

class Log:
    """JSONL-Logdatei + knappe Konsolenausgabe (UTF-8-tolerant)."""

    def __init__(self, path: str | Path, echo: bool = True, tag: str = "harness"):
        self.path = Path(path)
        self.echo = echo
        self.tag = tag
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    def _emit(self, level: str, msg: str, **extra):
        rec = {"ts": now_iso(), "level": level, "msg": msg}
        if extra:
            rec.update(extra)
        try:
            append_jsonl(self.path, rec)
        except OSError:
            pass
        if self.echo:
            line = f"[{datetime.now().strftime('%H:%M:%S')}] {level:<5} {msg}"
            if extra:
                line += "  " + " ".join(f"{k}={v}" for k, v in extra.items())
            print(line, flush=True)

    def info(self, msg: str, **extra):
        self._emit("INFO", msg, **extra)

    def warn(self, msg: str, **extra):
        self._emit("WARN", msg, **extra)

    def error(self, msg: str, **extra):
        self._emit("ERROR", msg, **extra)

    def event(self, name: str, **extra):
        self._emit("EVENT", name, **extra)


def secs_human(seconds: float) -> str:
    seconds = int(max(0, seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def sleep_until(ts: float, max_chunk: float = 30.0, interrupt=None) -> None:
    """Schlaeft bis Zeitstempel, in Stuecken; interrupt() darf frueher abbrechen."""
    while True:
        left = ts - time.time()
        if left <= 0:
            return
        if interrupt is not None and interrupt():
            return
        time.sleep(min(max_chunk, left))
