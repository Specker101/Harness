"""Attrappen-Tests fuer R13: Ghidra nach dem Batch speichern, frische Reviewer-Session.

Alles im Attrappenbetrieb: keine Kosten, kein echter Ghidra-Server, kein Netz.
"""

from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import queue, reviewer as rvmod, worker                  # noqa: E402
from hx.config import load_config                                # noqa: E402
from hx.orchestrator import Orchestrator                         # noqa: E402
from hx.util import Log, ensure_dir                               # noqa: E402

ANKER = """# Workstream R1B
**Stand:** BATCH 158 (2026-09-25) - irgendwas.
**Naechster Schritt:** (a) **B159:** cc54 verdrahten.
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = ensure_dir(Path(__file__).resolve().parent / "_tmp_r13")
        shutil.rmtree(self.tmp, ignore_errors=True)
        ensure_dir(self.tmp)
        self.repo = ensure_dir(self.tmp / "decomp")
        ensure_dir(self.repo / "analysis")
        (self.repo / "analysis" / "r1b-workstream.md").write_text(ANKER, encoding="utf-8")
        self.root = ensure_dir(self.tmp / "root")
        sec = ensure_dir(self.root / "secrets")
        (sec / "deepseek.key").write_text("sk-test-000\n", encoding="utf-8")
        prof = ensure_dir(self.root / "profiles")
        for f in (ROOT / "profiles").glob("*.json"):
            shutil.copy2(f, prof / f.name)
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.repo)
        cfg.data["paths"]["secrets"] = str(sec)
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)
        self.orch = Orchestrator(cfg, self.log, mock=True,
                                 state_file=self.root / "state" / "run.json")
        self.orch.say = lambda *a, **k: None
        self.orch.state.data["batch"] = 159
        self.orch.state.data["last_batch_number"] = 159
        self.orch.state.save()


    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


# ------------------------------------------------- 1) Ghidra nach dem Batch
class TestGhidraSpeichern(Base):
    def test_profil_none_braucht_kein_speichern(self):
        r = worker.save_ghidra_after_batch(self.cfg, self.log, self.orch.state, "none",
                                           mock=True)
        self.assertFalse(r["needed"])
        self.assertIn("nicht noetig", r["hinweis"])

    def test_schreibendes_profil_speichert(self):
        r = worker.save_ghidra_after_batch(self.cfg, self.log, self.orch.state,
                                           "ghidra-standard", mock=True)
        self.assertTrue(r["needed"])
        self.assertTrue(r["ok"])
        self.assertIn("Attrappe", r["hinweis"])

    def test_unbekanntes_profil_ist_kein_fehler(self):
        r = worker.save_ghidra_after_batch(self.cfg, self.log, self.orch.state, "gibtsnicht",
                                           mock=True)
        self.assertFalse(r["needed"])
        self.assertIsNone(r["ok"])

    def test_run_batch_haelt_den_merker_und_speichert(self):
        self.orch.state.data["ghidra_pending"] = True     # so setzt es run_batch
        res = worker.run_batch(self.cfg, self.log, self.orch.state, "Batch 159 - Test",
                               "ghidra-standard", None, mock=True)
        self.assertTrue(res.ghidra_save.get("needed"))
        self.assertTrue(res.ghidra_save.get("ok"))
        self.assertFalse(self.orch.state.data.get("ghidra_pending"),
                         "nach dem Speichern ist der Merker weg")
        daten = json.loads((Path(res.run_dir) / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(daten["ghidra_save"]["ok"], True)
        self.assertEqual(daten["stats"]["ghidra_save"]["needed"], True)

    def test_run_batch_bei_profil_none_ohne_speichern(self):
        res = worker.run_batch(self.cfg, self.log, self.orch.state, "Batch 159 - Test",
                               "none", None, mock=True)
        self.assertFalse(res.ghidra_save.get("needed"))

    def test_fehler_pausiert_und_haelt_push_und_review_zurueck(self):
        def kaputt(cfg, log, state, profile_name, mock=False, http_state=None):
            return {"needed": True, "ok": False, "blocking": True,
                    "hinweis": "Fehler: Server weg"}
        with mock.patch.object(worker, "save_ghidra_after_batch", kaputt):
            self.orch.run_worker("Batch 159 - Test", "ghidra-standard", None, "")
        self.assertTrue(self.orch.ghidra_failed, "die Schleife muss Push/Review ueberspringen")
        self.assertTrue(self.orch.state.data["paused"])
        self.assertIn("Ghidra-Speichern", str(self.orch.state.data.get("note")))

    def test_merker_zaehlt_auch_bei_stopp_und_ende(self):
        self.orch.state.data["ghidra_pending"] = True
        self.orch.state.data["last_profile"] = "ghidra-standard"
        self.assertTrue(self.orch.save_ghidra_if_pending("Stopp"))
        self.assertFalse(self.orch.state.data.get("ghidra_pending"))
        # ohne Merker passiert nichts
        self.assertTrue(self.orch.save_ghidra_if_pending("Ende"))

    def test_messdatenzeile(self):
        self.assertEqual(self.orch.ghidra_save_line({}).startswith("nicht noetig"), True)
        self.assertTrue(self.orch.ghidra_save_line(
            {"ghidra_save": {"needed": False, "ok": None, "hinweis": "kein schreibendes Profil"}}
        ).startswith("nicht noetig"))
        self.assertTrue(self.orch.ghidra_save_line(
            {"ghidra_save": {"needed": True, "ok": True, "hinweis": "save_all_programs ok (2 Programme)"}}
        ).startswith("ja"))
        self.assertTrue(self.orch.ghidra_save_line(
            {"ghidra_save": {"needed": True, "ok": False, "hinweis": "Fehler: weg"}}
        ).startswith("NEIN"))
        # und im Messdatenblock des Reviews
        rd = ensure_dir(self.root / "runs" / "b159")
        (rd / "result.json").write_text(json.dumps(
            {"batch": 159, "profile": "ghidra-standard", "program": None, "rc": 0,
             "duration_s": 10, "stats": {"requests": 3, "usage_check": {"ok": True}},
             "cost_usd": 0.01, "ghidra_save": {"needed": True, "ok": True,
                                               "hinweis": "save_all_programs ok (2 Programme)"}}),
            encoding="utf-8")
        fakten = self.orch.harness_facts(159)
        self.assertIn("Ghidra gespeichert: ja", fakten)


# ---------------------------------------- 2) Frische Reviewer-Session mit Uebergabe
class TestFrischeReviewerSession(Base):
    def _review_mit_aufzeichnung(self):
        """Fuehrt do_review aus und zeichnet auf, wie der Reviewer gestartet wurde."""
        aufzeichnung: dict = {}
        handover: dict = {}
        echt = rvmod.run_review

        def fake(cfg, log, prompt, **kw):
            aufzeichnung.update(kw)
            aufzeichnung["prompt"] = prompt
            return echt(cfg, log, prompt, **kw)

        def fake_handover(cfg, log, session_id, **kw):
            handover["session_id"] = session_id
            return "UEBERGABE-MARKE: Stand B159, cc54 offen"

        with mock.patch.object(rvmod, "run_handover", fake_handover):
            with mock.patch.object(rvmod, "run_review", fake):
                self.orch.do_review("batch_end", "(snapshot)")
        aufzeichnung["handover_session"] = handover.get("session_id")
        return aufzeichnung

    def test_force_rotate_startet_neue_session_mit_uebergabe(self):
        self.orch.state.data["reviewer"] = {"session_id": "alte-session-123", "reviews": 2}
        self.orch.state.data["reviewer"]["force_rotate"] = True
        self.orch.state.save()
        auf = self._review_mit_aufzeichnung()
        self.assertTrue(auf["new_session"], "es muss eine NEUE Session starten")
        self.assertNotEqual(auf["session_id"], "alte-session-123",
                            "der Review laeuft in der NEUEN Session, nie in der alten")
        self.assertEqual(auf["handover_session"], "alte-session-123",
                         "die Uebergabe kommt aus der ALTEN Session")
        self.assertIn("UEBERGABE AUS DER VORIGEN SESSION", auf["prompt"])
        self.assertIn("UEBERGABE-MARKE", auf["prompt"])
        rev = self.orch.state.data["reviewer"]
        self.assertNotEqual(rev["session_id"], "alte-session-123")
        self.assertEqual(auf["session_id"], rev["session_id"],
                         "die Kennung im Zustand ist die des Laufs")
        self.assertFalse(rev.get("force_rotate"), "das Flag wird nach der Rotation geloescht")
        self.assertEqual(rev["reviews"], 1, "die neue Session zaehlt wieder bei 1")
        datei = Path(self.cfg.sub("sessions")) / "vorherige-session.md"
        self.assertTrue(datei.is_file())
        self.assertIn("UEBERGABE-MARKE", datei.read_text(encoding="utf-8"))
        self.assertTrue((Path(self.cfg.sub("sessions")) /
                         f"claude-{rev['session_id']}.md").is_file(),
                        "die Uebergabe liegt schon VOR dem Review auf der Platte")

    def test_ohne_rotation_wird_die_session_fortgesetzt(self):
        self.orch.state.data["reviewer"] = {"session_id": "laufende-session-999", "reviews": 2}
        self.orch.state.save()
        auf = self._review_mit_aufzeichnung()
        self.assertFalse(auf["new_session"], "ohne Rotation wird fortgesetzt")
        self.assertEqual(auf["session_id"], "laufende-session-999")
        self.assertNotIn("UEBERGABE-MARKE", auf["prompt"])
        self.assertEqual(self.orch.state.data["reviewer"]["session_id"], "laufende-session-999")

    def test_rotation_nach_zehn_reviews(self):
        self.orch.state.data["reviewer"] = {"session_id": "volle-session", "reviews": 10}
        self.orch.state.save()
        auf = self._review_mit_aufzeichnung()
        self.assertTrue(auf["new_session"])
        self.assertIn("UEBERGABE-MARKE", auf["prompt"])


if __name__ == "__main__":
    unittest.main()
