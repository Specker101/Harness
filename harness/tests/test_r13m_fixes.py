"""Tests fuer R13m: Ein Git-Halt darf den bezahlten Auftrag nicht verwerfen.

FALL AUS DER PRAXIS (2026-09-27): Batch 180s Worker war fertig, der Harness haengte
danach (R13k) und wurde neu gestartet. Er holte den Batch nach, der Review lief,
der Auftrag fuer Batch 181 stand - und dann brach die **Git-Vorpruefung** ab, weil
`origin/main` hinter dem lokalen Stand lag (der Push aus `_finish_run` war nie
gelaufen). Der Code verwarf den Auftrag VOR der Vorpruefung: nach dem `/resume`
musste ein zweiter (kostenpflichtiger) Opus-Review laufen, obwohl die Instruktion
unveraendert gueltig war. Der Nutzer sah nur "er pausiert immer wieder".

Geprueft wird:
* Ein fehlgeschlagener Git-Vorlauf laesst den Auftrag STEHEN und pausiert nur,
* beim Fortsetzen startet der Batch mit DERSELBEN Instruktion - ohne neuen Review,
* erst der wirklich startende Batch verbraucht den Auftrag (Gate ist dann weg).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import state as hxstate                                   # noqa: E402
from hx.config import load_config                                 # noqa: E402
from hx.orchestrator import Orchestrator                          # noqa: E402
from hx.util import Log, ensure_dir                               # noqa: E402

ANKER = """# Workstream R1B
**Stand:** BATCH 180 (2026-09-26) - Scheibe 6a Terminsteuerung.
**Naechster Schritt:** (a) **B181:** Fortsetzung.
"""

INSTRUKTION = "Batch 181 - Terminsteuerung fortsetzen."


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = ensure_dir(Path(__file__).resolve().parent / "_tmp_r13m")
        shutil.rmtree(self.tmp, ignore_errors=True)
        ensure_dir(self.tmp)
        self.repo = ensure_dir(self.tmp / "decomp")
        subprocess.run(["git", "init", "-q"], cwd=self.repo, capture_output=True)
        ensure_dir(self.repo / "analysis")
        (self.repo / "analysis" / "r1b-workstream.md").write_text(ANKER, encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=self.repo, capture_output=True)
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@example.invalid",
                        "commit", "-q", "-m", "start"], cwd=self.repo, capture_output=True)
        self.root = ensure_dir(self.tmp / "root")
        prof = ensure_dir(self.root / "profiles")
        for f in (ROOT / "profiles").glob("*.json"):
            shutil.copy2(f, prof / f.name)
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.repo)
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)
        self.orch = Orchestrator(cfg, self.log, mock=True,
                                 state_file=self.root / "state" / "run.json")
        self.gesagt: list[str] = []
        self.orch.say = lambda t: self.gesagt.append(str(t))
        st = self.orch.state
        st.data["batch"] = 180
        st.data["last_batch_number"] = 180
        st.save()
        # R13m: Auftrag steht, Nutzer hat freigegeben (oder Dauerbetrieb).
        st.set_gate("g-b181", "Summary", INSTRUKTION,
                    {"batch": 181, "profile": "none", "program": None}, "roh")
        st.data["paused"] = False
        st.data["autonomous"] = True
        st.save()
        self.orch.approved_gate = "g-b181"
        self.orch.git_preflight = lambda: (True, "")
        self.orch.git.checkpoint = lambda n: f"harness/b{int(n)}-start"
        self.orch.git_push = lambda: (True, "ok")
        self.orch.mark_harness_head = lambda n: None
        self.orch.save_ghidra_if_pending = lambda reason: True

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _loop(self, preflight=(True, "")) -> dict:
        """Einen Durchlauf fahren - mit Notbremse statt Endlosschleife."""
        self.gesagt = []
        gesehen: dict = {"reviews": 0, "worker": None}
        self.orch.git_preflight = lambda: preflight
        self.orch.do_review = lambda *a, **k: gesehen.__setitem__("reviews",
                                                                  gesehen["reviews"] + 1)

        def worker(instruction, profile, program, queue_block):
            gesehen["worker"] = instruction
            self.orch.quit = True
            return None

        self.orch.run_worker = worker
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


class TestGitHaltBehaeltDenAuftrag(Base):
    def test_git_halt_verwirft_den_auftrag_nicht(self):
        gesehen = self._loop(preflight=(False, "origin/main weicht ab (ahead 4)"))
        self.assertIsNotNone(self.orch.state.gate,
                             "R13m: der Auftrag darf beim Git-Halt NICHT verworfen werden")
        self.assertEqual(gesehen["reviews"], 0, "kein neuer Review wegen eines Git-Halts")
        self.assertIsNone(gesehen["worker"], "es darf kein Batch starten")
        self.assertEqual(self.orch.state.state, hxstate.PAUSED)
        self.assertTrue(self.orch.state.data.get("paused"))
        self.assertTrue(any("weicht ab" in t for t in self.gesagt), self.gesagt)
        self.assertTrue(any("bleibt stehen" in t for t in self.gesagt), self.gesagt)

    def test_fortsetzen_startet_ohne_neuen_review(self):
        self._loop(preflight=(False, "origin/main weicht ab (ahead 4)"))
        self.assertIsNotNone(self.orch.state.gate)
        # Der Nutzer setzt fort (/resume) - danach ist der Git-Stand in Ordnung.
        st = self.orch.state
        st.data["paused"] = False
        st.save()
        gesehen = self._loop(preflight=(True, ""))
        self.assertEqual(gesehen["reviews"], 0, "der Review darf NICHT ein zweites Mal laufen")
        self.assertEqual(gesehen["worker"], INSTRUKTION,
                         "der Batch startet mit der unveraenderten Instruktion")
        self.assertIsNone(self.orch.state.gate, "erst der Start verbraucht den Auftrag")

    def test_ohne_git_halt_wird_der_auftrag_verbraucht(self):
        gesehen = self._loop(preflight=(True, ""))
        self.assertEqual(gesehen["worker"], INSTRUKTION)
        self.assertIsNone(self.orch.state.gate)


if __name__ == "__main__":
    unittest.main()
