"""Zustand: eine atomar geschriebene JSON-Datei + Recovery-Hilfen."""

from __future__ import annotations

import os
from pathlib import Path

from .util import now_iso, read_json, write_json_atomic, new_id

# Zustaende laut Plan (Abschnitt C1)
IDLE = "IDLE"
GATE_APPROVAL = "GATE_APPROVAL"
DS_WORKING = "DS_WORKING"
REVIEW_DUE = "REVIEW_DUE"
CLAUDE_REVIEWING = "CLAUDE_REVIEWING"
LIMIT_WAIT = "LIMIT_WAIT"
PAUSED = "PAUSED"
STOPPED = "STOPPED"
RECOVERING = "RECOVERING"
ERROR = "ERROR"

DEFAULTS = {
    "gen": 0,
    "state": IDLE,
    "batch": 0,
    "autonomous": False,
    "paused": False,
    "stopped": False,
    "worker": None,
    "gate": None,
    "reviewer": {"session_id": None, "reviews": 0, "started_at": None, "last_decision": None},
    "delivered": [],
    "telegram_offset": 0,
    "spent": {},
    "note": None,
    "last_error": None,
    "phase": None,
}


class State:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.data = dict(DEFAULTS)
        loaded = read_json(self.path, None)
        if isinstance(loaded, dict):
            merged = dict(DEFAULTS)
            merged.update(loaded)
            self.data = merged

    # ------------------------------------------------------------ Speichern
    def save(self) -> None:
        self.data["gen"] = int(self.data.get("gen", 0)) + 1
        self.data["updated_at"] = now_iso()
        write_json_atomic(self.path, self.data)

    def set(self, state: str, note: str | None = None) -> None:
        self.data["state"] = state
        self.data["note"] = note
        self.save()

    # ------------------------------------------------------------- Abfragen
    @property
    def state(self) -> str:
        return self.data.get("state", IDLE)

    @property
    def batch(self) -> int:
        return int(self.data.get("batch", 0))

    def next_batch(self) -> int:
        self.data["batch"] = self.batch + 1
        self.save()
        return self.batch

    # -------------------------------------------------------------- Worker
    def worker_started(self, pid: int, log_path: str, session_id: str) -> None:
        self.data["worker"] = {
            "pid": pid,
            "started_at": now_iso(),
            "log": log_path,
            "session_id": session_id,
        }
        self.save()

    def worker_finished(self) -> None:
        self.data["worker"] = None
        self.save()

    def live_worker_pid(self) -> int | None:
        w = self.data.get("worker") or {}
        pid = w.get("pid")
        if not pid:
            return None
        if pid_alive(int(pid)):
            return int(pid)
        return None

    # ---------------------------------------------------------------- Gate
    def set_gate(self, review_id: str, summary: str, instruction: str, tools: dict, raw_path: str) -> None:
        self.data["gate"] = {
            "id": review_id,
            "created_at": now_iso(),
            "summary": summary,
            "instruction": instruction,
            "tools": tools,
            "raw": raw_path,
        }
        self.save()

    def clear_gate(self) -> None:
        self.data["gate"] = None
        self.save()

    @property
    def gate(self) -> dict | None:
        return self.data.get("gate")

    # ------------------------------------------------------------ Reviewer
    def reviewer_note_review(self, decision: str | None) -> int:
        rev = dict(self.data.get("reviewer") or {})
        rev["reviews"] = int(rev.get("reviews", 0)) + 1
        rev["last_decision"] = decision
        rev["last_at"] = now_iso()
        self.data["reviewer"] = rev
        self.save()
        return int(rev["reviews"])

    def reviewer_new_session(self, session_id: str, handover: str = "",
                             from_session: str = "") -> None:
        """Neue Reviewer-Session verbuchen (R13b).

        Die Uebergabe der alten Session wird MITGESPEICHERT. Scheitert der Review oder
        bricht der Harness ab, ist sie nicht verloren: `do_review` verwendet sie wieder,
        statt die alte Session ein zweites Mal zu fragen.
        """
        self.data["reviewer"] = {
            "session_id": session_id,
            "reviews": 0,
            "started_at": now_iso(),
            "last_decision": None,
            "force_rotate": False,
            "pending_handover": ({"from_session": from_session, "text": handover,
                                  "at": now_iso()} if handover else {}),
        }
        self.save()

    @property
    def reviewer_session(self) -> str | None:
        return (self.data.get("reviewer") or {}).get("session_id")

    # ------------------------------------------------------------- Queue
    def mark_delivered(self, msg_id: str) -> None:
        lst = list(self.data.get("delivered") or [])
        if msg_id not in lst:
            lst.append(msg_id)
        self.data["delivered"] = lst[-200:]
        self.save()

    # ----------------------------------------------------------- Telegram
    def set_offset(self, offset: int) -> None:
        self.data["telegram_offset"] = int(offset)
        self.save()

    # -------------------------------------------------------------- Geld
    def spent_today(self, day: str) -> float:
        return float((self.data.get("spent") or {}).get(day, 0.0))

    def add_spend(self, day: str, usd: float) -> float:
        spent = dict(self.data.get("spent") or {})
        spent[day] = round(float(spent.get(day, 0.0)) + float(usd), 6)
        # nur die letzten 14 Tage behalten
        for k in sorted(spent)[:-14]:
            spent.pop(k, None)
        self.data["spent"] = spent
        self.save()
        return spent[day]


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
        k32.CloseHandle(h)
        return bool(ok) and code.value == STILL_ACTIVE
    except Exception:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def new_review_id() -> str:
    return new_id()
