"""Tests fuer R13u (2026-09-28): /claude-Nachrichten gelten erst mit freigegebenem Gate.

Auftrag (Nutzer): "Falls Nachrichten bei einem verworfenen Gate verloren gehen: als R13u
vorschlagen und bauen: /claude-Nachrichten gelten erst als zugestellt, wenn das Gate
ihres Reviews freigegeben wird; beim Verwerfen zurueck in inbox/claude (Reihenfolge
erhalten, keine Doppelten). Tests dazu, wirksam nach Neustart."

Vorher (R13b, gemessen): `commit_queue("claude", …)` lief DIREKT nach dem gueltigen
Review - also vor der Gate-Entscheidung. Ein `/review` verwarf dann den Auftrag
(`discard_gate`), die Nachricht lag aber schon in `inbox/done/` und wurde nie wieder
gelesen. Jetzt reisen die Nachrichten-IDs im Gate (`claude_queue_ids`) und werden erst
beim Worker-Start zugestellt.

Alles im Attrappenbetrieb: kein Netz, keine API-Kosten, kein Ghidra.
"""

from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import protocol, queue                                   # noqa: E402
from hx.config import load_config                              # noqa: E402
from hx.orchestrator import Orchestrator                       # noqa: E402
from hx.util import Log, ensure_dir, write_text_atomic          # noqa: E402

ANKER = """# Workstream R1B

**Stand:** BATCH 180 (2026-09-28) - Beispielstand fuer den Test.
**Fertig:** nichts.
**Naechster Schritt:** **(a)** warten.
**Offene Entscheidung:** **(1) GESCHLOSSEN:** nichts.
"""


class _ReviewStub:
    """Minimaler Ersatz fuer `reviewer.ReviewResult` (gueltig, ohne API)."""

    def __init__(self, batch: int = 181):
        self.parsed = protocol.Review()
        self.parsed.blocks = ["TELEGRAM_SUMMARY", "DS_TOOLS", "DS_INSTRUCTION"]
        self.parsed.summary = "Zusammenfassung"
        self.parsed.instruction = f"Batch {batch} - Testauftrag"
        self.parsed.batch = batch
        self.parsed.profile = "none"
        self.parsed.program = None
        self.text = "x"
        self.review_dir = ""
        self.review_file = ""
        self.raw_path = ""
        self.limit_reached = False
        self.session_id = "s1"
        self.model_seen = "claude-opus-5-5"
        self.model_ok = True
        self.rc = 0
        self.duration_s = 1.0
        self.error = ""


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__file__).resolve().parent / "_tmp_r13u"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "root")
        self.decomp = ensure_dir(self.tmp / "decomp")
        write_text_atomic(self.decomp / "analysis" / "r1b-workstream.md", ANKER)
        prof = ensure_dir(self.root / "profiles")
        for f in (ROOT / "profiles").glob("*.json"):
            shutil.copy2(f, prof / f.name)
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.decomp)
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["paths"]["secrets"] = str(ensure_dir(self.tmp / "secrets"))
        cfg.data["telegram"]["allowlist_user_ids"] = []
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)
        self.orch = Orchestrator(cfg, self.log, mock=True,
                                 state_file=self.root / "state" / "run.json")
        self.orch.say = lambda *a, **k: None
        st = self.orch.state
        st.data["batch"] = 180
        st.data["last_batch_number"] = 180
        st.data["paused"] = False
        st.data["autonomous"] = False
        st.data["delivered"] = []
        st.clear_gate()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ------------------------------------------------------------------ Helfer
    def nachricht(self, text: str = "Testnachricht an den Reviewer.") -> Path:
        return queue.enqueue(self.root, "claude", text, "lokal")

    def durchlauf(self, gueltig: bool = True, bis_worker: bool = True) -> dict:
        """Einen Schleifendurchlauf fahren - mit Notbremse statt Endlosschleife."""
        gesehen: dict = {"reviews": 0, "worker": None}
        self.orch.review_ok = lambda res: gueltig

        def review(*a, **k):
            gesehen["reviews"] += 1
            return _ReviewStub(batch=self.orch.expected_batch())

        def worker(instruction, profile, program, queue_block):
            gesehen["worker"] = instruction
            gesehen["ds_block"] = queue_block
            if bis_worker:
                self.orch.quit = True
            return None

        self.orch.do_review = review
        self.orch.run_worker = worker
        self.orch.git_preflight = lambda: (True, "")
        self.orch.git.checkpoint = lambda n: f"harness/b{int(n)}-start"
        self.orch.git_push = lambda: (True, "ok")
        self.orch.mark_harness_head = lambda n: None
        zaehler = {"poll": 0}

        def poll(*a, **k):
            zaehler["poll"] += 1
            if zaehler["poll"] > 3:
                self.orch.quit = True

        self.orch.poll = poll
        try:
            with mock.patch.object(self.orch, "peak_gate", lambda: (True, "")):
                with mock.patch("hx.orchestrator.time.sleep", lambda *_: None):
                    self.orch._loop()
        finally:
            self.orch.quit = False
        return gesehen

    def inbox(self, name: str) -> Path:
        return self.root / "inbox" / "claude" / name

    def done(self, name: str) -> Path:
        return self.root / "inbox" / "done" / name


class TestR13u(Basis):
    def test_nachricht_bleibt_bis_zur_freigabe_liegen(self):
        p = self.nachricht()
        self.durchlauf()
        self.assertTrue(p.is_file(), "R13u: die Nachricht darf den Review NICHT verlassen")
        self.assertNotIn(p.stem, self.orch.state.data.get("delivered") or [])
        gate = self.orch.state.gate or {}
        self.assertEqual(gate.get("claude_queue_ids"), [p.stem],
                         "die Nachrichten-ID muss im Gate mitreisen")

    def test_freigabe_stellt_die_nachricht_zu(self):
        p = self.nachricht()
        self.durchlauf()                                  # Review -> Gate, kein Start
        ohne_freigabe = self.durchlauf()                   # Gate haelt: kein Worker
        self.assertIsNone(ohne_freigabe["worker"], "ohne Freigabe startet nichts")
        self.assertTrue(p.is_file())
        self.orch.approved_gate = (self.orch.state.gate or {}).get("id")
        gesehen = self.durchlauf()                         # jetzt startet der Worker
        self.assertIsNotNone(gesehen["worker"], "nach der Freigabe muss der Batch starten")
        self.assertFalse(p.is_file(), "bei der Freigabe wird die Nachricht zugestellt")
        self.assertTrue(self.done(p.name).is_file(), "sie liegt dann in inbox/done/")
        self.assertIn(p.stem, self.orch.state.data.get("delivered") or [])

    def test_verworfenes_gate_frisst_die_nachricht_nicht(self):
        p = self.nachricht()
        self.durchlauf()
        alt = (self.orch.state.gate or {}).get("id")
        self.orch.review_now = True                        # wie /review
        self.durchlauf()
        self.assertNotEqual((self.orch.state.gate or {}).get("id"), alt,
                            "der zweite Review muss ein neues Gate erzeugen")
        self.assertTrue(p.is_file(), "verworfenes Gate: Nachricht bleibt in inbox/claude")
        self.assertNotIn(p.stem, self.orch.state.data.get("delivered") or [])
        # und sie wird GENAU EINMAL gelesen (keine Doppelten)
        block, ids = self.orch.read_queue_block("claude", mark=False)
        self.assertEqual(ids, [p.stem])
        self.assertEqual(block.count("Testnachricht an den Reviewer."), 1)

    def test_zustellung_ohne_gate_nachricht_bleibt_leer(self):
        """Kein Regelbruch bei Altbestand: ein Gate ohne `claude_queue_ids` stellt nichts zu."""
        st = self.orch.state
        st.set_gate("g-alt", "Summary", "Batch 181 - alt",
                    {"batch": 181, "profile": "none", "program": None, "source": "user"},
                    "roh")
        p = self.nachricht()
        self.orch.approved_gate = "g-alt"
        self.durchlauf()
        self.assertTrue(p.is_file(), "ohne IDs im Gate bleibt die Nachricht liegen")
        self.assertNotIn(p.stem, self.orch.state.data.get("delivered") or [])


if __name__ == "__main__":
    unittest.main()
