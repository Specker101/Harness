"""Attrappen fuer den Testmodus: keine API-Kosten, aber echter Ablauf.

  * mock_worker_stream()  schreibt einen stream-json-Mitschnitt (inkl. Fehlerfaelle)
  * mock_reviewer_text()  liefert eine Antwort im Blockformat (inkl. Fehlerfaelle)
"""

from __future__ import annotations

import json
from pathlib import Path

from .util import write_text_atomic


def _ev(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _usage(miss, hit, out):
    return {"input_tokens": miss, "cache_read_input_tokens": hit,
            "cache_creation_input_tokens": 0, "output_tokens": out,
            "output_tokens_details": {"thinking_tokens": 0}}


def mock_worker_stream(cfg, run_dir: Path, instruction: str, log=None, mode: str = "ok") -> Path:
    """Schreibt einen Mitschnitt wie ihn `claude -p --output-format stream-json` liefert."""
    run_dir = Path(run_dir)
    lines: list[str] = []
    lines.append(_ev({"type": "system", "subtype": "init", "session_id": "mock-session-0001",
                      "model": str(cfg.get("claude", "model_worker")),
                      "permissionMode": "default",
                      "tools": [{"name": "Read"}, {"name": "Grep"},
                                {"name": "mcp__ghidra__decompile_function"}],
                      "mcp_servers": [{"name": "ghidra", "status": "connected", "source": "dynamic"}]}))

    plan = [
        ("Read", {"file_path": "analysis/r1b-workstream.md"}, 21000, 0, 120),
        ("Grep", {"pattern": "80054AE4", "path": "port/src"}, 300, 21000, 90),
        ("mcp__ghidra__decompile_function", {"address": "0x80054AE4"}, 400, 21300, 150),
        ("PowerShell", {"command": "python -u scripts/preflight.py before"}, 800, 21700, 210),
    ]
    for idx, (name, args, miss, hit, out) in enumerate(plan):
        mid = f"msg_mock_{idx:03d}"
        lines.append(_ev({"type": "assistant", "timestamp": "2026-09-25T20:00:00.000Z",
                          "message": {"id": mid, "model": str(cfg.get("claude", "model_worker")),
                                      "usage": _usage(miss, hit, out),
                                      "content": [{"type": "thinking", "thinking": "(mock)"}]}}))
        lines.append(_ev({"type": "assistant", "timestamp": "2026-09-25T20:00:01.000Z",
                          "message": {"id": mid, "model": str(cfg.get("claude", "model_worker")),
                                      "usage": _usage(0, 0, 0),
                                      "content": [{"type": "tool_use", "id": f"tu_mock_{idx:03d}",
                                                   "name": name, "input": args}]}}))
        lines.append(_ev({"type": "user", "timestamp": "2026-09-25T20:00:02.000Z",
                          "message": {"content": [{"type": "tool_result",
                                                   "tool_use_id": f"tu_mock_{idx:03d}",
                                                   "content": "(mock-Ergebnis)"}]}}))

    if mode == "crash":
        lines.append(_ev({"type": "assistant", "timestamp": "2026-09-25T20:00:03.000Z",
                          "message": {"id": "msg_mock_crash", "model": str(cfg.get("claude", "model_worker")),
                                      "usage": _usage(120, 22000, 60),
                                      "content": [{"type": "text", "text": "ABBRUCH: (mock)"}]}}))
        write_text_atomic(run_dir / "mock_rc.txt", "1")
        p = write_text_atomic(run_dir / "stream.jsonl", "\n".join(lines) + "\n")
        if log:
            log.warn("Mock-Worker: Absturzvariante geschrieben", datei=str(p))
        return p

    final = (
        "## 1) Uebernommener Stand\n"
        "(mock) Der Anker wurde gelesen; keine echten Messungen in diesem Testlauf.\n\n"
        "## 2) Befunde\n"
        "- (F1) MOCK-Befund mit Datei:Zeile-Beleg: `port/src/mission_script.cpp:1402` [CONFIRMED]\n"
        "- (F2) MOCK-Vermutung ohne Beleg [HYPOTHESIS]\n\n"
        "## 3) Naechster Schritt\n"
        "(mock) Verdrahtung im Sandkasten vorbereiten.\n\n"
        "<TOOL_REQUEST>mcp__ghidra__read_memory</TOOL_REQUEST>"
    )
    lines.append(_ev({"type": "assistant", "timestamp": "2026-09-25T20:00:04.000Z",
                      "message": {"id": "msg_mock_final", "model": str(cfg.get("claude", "model_worker")),
                                  "usage": _usage(150, 22500, 400),
                                  "content": [{"type": "text", "text": final}]}}))
    lines.append(_ev({"type": "result", "subtype": "success", "is_error": False,
                      "num_turns": 12, "duration_ms": 195000, "terminal_reason": "completed",
                      "total_cost_usd": 1.4289416000000004,
                      "usage": {"input_tokens": 22870, "cache_read_input_tokens": 86500,
                                "cache_creation_input_tokens": 0, "output_tokens": 1030},
                      "result": final}))
    write_text_atomic(run_dir / "mock_rc.txt", "0")
    p = write_text_atomic(run_dir / "stream.jsonl", "\n".join(lines) + "\n")
    if log:
        log.info("Mock-Worker: Mitschnitt geschrieben", datei=str(p))
    return p


REVIEWER_OK = """<TELEGRAM_SUMMARY>
Der Mock-Batch ist durchgelaufen. Zwei Befunde, einer ohne Beleg. Naechster Schritt: Verdrahtung im Sandkasten.
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: ghidra-read
program: /830d01.27p.main.bin
</DS_TOOLS>

<DS_INSTRUCTION>
Batch 160 - Silent Scope Decomp (MOCK)

STAND UEBERNEHMEN:
Den Ankerkopf lesen; der Mock-Batch hat nichts geaendert.

ARBEITSWEISE:
Projektregeln wie gehabt; ein Batch, ein Chat.

TEIL 1:
(Erster Arbeitsschritt.)

TEIL 2:
(Zweiter Arbeitsschritt.)

BATCH-ENDE:
Genau ein preflight-Lauf, Bilanz, Anker aktualisieren, Memory-Export, Commit.
</DS_INSTRUCTION>
"""

REVIEWER_BROKEN = """<TELEGRAM_SUMMARY>
Uebersicht, aber der Werkzeugblock fehlt in dieser Attrappe.
</TELEGRAM_SUMMARY>

<DS_INSTRUCTION>
Batch 160 - Silent Scope Decomp (MOCK, absichtlich fehlerhaft)
</DS_INSTRUCTION>
"""

REVIEWER_LIMIT = """Usage limit reached. Your limit will reset at 2026-09-25 22:00 UTC.
"""


def _mit_marker(text: str, zeile: str) -> str:
    """Zusaetzliche Markerzeile in die TELEGRAM_SUMMARY der Attrappe setzen (A, R13c)."""
    ende = "</TELEGRAM_SUMMARY>"
    return text.replace(ende, zeile.strip() + "\n" + ende, 1)


def mock_reviewer_text(mode: str = "ok", batch: int | None = None, attempt: int = 1) -> str:
    if mode == "parser_error":
        return REVIEWER_BROKEN
    if mode == "limit":
        return REVIEWER_LIMIT
    if mode == "reviewer_crash":
        return ""
    if mode == "modell_falsch":
        return mock_reviewer_text("ok", batch)
    if mode == "ok_zweiter_versuch":
        # R13b: erster Versuch absichtlich ohne Protokollblock, Wiederholung sauber.
        return REVIEWER_BROKEN if attempt <= 1 else mock_reviewer_text("ok", batch)
    if mode == "entscheidung":
        # A (R13c): echte Weichenstellung -> darf im Dauerbetrieb NICHT durchlaufen.
        return _mit_marker(mock_reviewer_text("ok", batch),
                           "ENTSCHEIDUNG NOETIG: Audio-Verfahren waehlen (A PCM oder B Chip)?")
    if mode == "entscheidung_umlaut":
        return _mit_marker(mock_reviewer_text("ok", batch),
                           "ENTSCHEIDUNG NÖTIG: Audio-Verfahren waehlen (A oder B).")
    if mode == "offene_frage":
        # Nur Information -> die Arbeit geht an anderer Stelle weiter.
        return _mit_marker(mock_reviewer_text("ok", batch),
                           "OFFENE FRAGE: Texturnamen noch nicht zugeordnet.")
    if mode == "live_aufnahme":
        return _mit_marker(mock_reviewer_text("ok", batch),
                           "WARTET AUF LIVE-AUFNAHME: ein Lauf mit Name-Breakpoint fehlt.")
    if batch:
        # Die Nummer muss stimmen: der Harness haelt bei Abweichung an (R10-1).
        return REVIEWER_OK.replace("Batch 160", f"Batch {batch}")
    return REVIEWER_OK


def mock_reviewer_stream(run_dir: Path, batch: int | None = None, mode: str = "ok",
                         attempt: int = 1) -> Path:
    """Schreibt einen Reviewer-Mitschnitt wie `claude -p --output-format stream-json`.

    Damit ist auch der Review in `watch` lesbar (statt nur der Worker-Lauf).
    Der Mitschnitt traegt denselben Text wie `mock_reviewer_text` (R13b).
    """
    run_dir = Path(run_dir)
    text = mock_reviewer_text(mode, batch, attempt)
    lines = [
        _ev({"type": "system", "subtype": "init", "session_id": "mock-reviewer-0001",
             "model": "claude-sonnet-5 (mock)",
             "tools": [{"name": "Read"}, {"name": "Grep"}, {"name": "Glob"}]}),
        _ev({"type": "assistant", "timestamp": "2026-09-25T20:10:00.000Z",
             "message": {"id": "msg_r_mock_0", "model": "claude-sonnet-5 (mock)",
                         "usage": _usage(1200, 0, 80),
                         "content": [{"type": "tool_use", "id": "tu_r_mock_0", "name": "Read",
                                      "input": {"file_path": "analysis/r1b-workstream.md"}}]}}),
        _ev({"type": "assistant", "timestamp": "2026-09-25T20:10:02.000Z",
             "message": {"id": "msg_r_mock_1", "model": "claude-sonnet-5 (mock)",
                         "usage": _usage(200, 1400, 120),
                         "content": [{"type": "tool_use", "id": "tu_r_mock_1", "name": "Grep",
                                      "input": {"pattern": "BATCH", "path": "analysis"}}]}}),
        _ev({"type": "assistant", "timestamp": "2026-09-25T20:10:04.000Z",
             "message": {"id": "msg_r_mock_2", "model": "claude-sonnet-5 (mock)",
                         "usage": _usage(0, 1600, 300),
                         "content": [{"type": "text", "text": text}]}}),
        _ev({"type": "result", "subtype": "success", "is_error": False, "num_turns": 3,
             "duration_ms": 4200, "result": text, "session_id": "mock-reviewer-0001"}),
    ]
    return write_text_atomic(run_dir / "reviewer.jsonl", "\n".join(lines) + "\n")
