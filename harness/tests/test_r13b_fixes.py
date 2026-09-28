"""Attrappen-Tests fuer R13b: erzwungene Rotation, Uebergabe, gescheiterter Review.

Fall (gemessen am echten Fehler vom 2026-09-25):
  * `force_rotate` + Uebergabe der alten Session,
  * der Review startet in der NEUEN Session (nicht in der alten - sonst bricht
    Claude Code mit "Session ID <id> is already in use" ab),
  * ein Review ohne gueltigen Protokollblock oeffnet NIE ein Gate: ein
    Wiederholungsversuch mit Format-Erinnerung, danach pausieren + Rohtext,
  * /claude-Nachrichten gelten erst nach einem gueltigen Review als zugestellt,
  * Nummern: Review-Verzeichnis und Gate nach dem Anker (naechster Batch),
  * Laufzeit = Wanduhr des Worker-Prozesses.

Alles im Attrappenbetrieb: keine Kosten, kein Netz, kein Ghidra.
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

from hx import queue, reviewer as rvmod, worker                         # noqa: E402
from hx.config import load_config                                        # noqa: E402
from hx.orchestrator import Orchestrator                                 # noqa: E402
from hx.util import Log, ensure_dir                                       # noqa: E402

ANKER = """# Workstream R1B
**Stand:** BATCH 159 (2026-09-25) - Doku-Batch abgeschlossen.
**Naechster Schritt:** (a) **B160:** cc54-Szene-Ketten-Nachweis.
"""


class Base(unittest.TestCase):
    """Wie der echte Fall: Anker steht auf 159, der naechste Batch ist 160."""

    def setUp(self):
        self.tmp = ensure_dir(Path(__file__).resolve().parent / "_tmp_r13b")
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
        st = self.orch.state
        st.data["batch"] = 159
        st.data["last_batch_number"] = 159
        # Belege des bewerteten Laufs (werden vom Review gelesen - aus runs/b159).
        rd = ensure_dir(self.root / "runs" / "b159")
        (rd / "antwort.md").write_text("## 1) Uebernommener Stand\n(mock) B159 fertig.\n",
                                       encoding="utf-8")
        (rd / "result.json").write_text(json.dumps(
            {"batch": 159, "profile": "none", "program": None, "rc": 0, "duration_s": 377.257,
             "killed_reason": None, "alarms": [], "stats": {"requests": 72},
             "cost_usd": 0.068, "cost_naive_usd": 0.068,
             "model_seen": "deepseek-flash[1m]", "model_ok": True,
             "duration_quelle": "cli", "duration_cli_s": 377.257}, indent=1),
            encoding="utf-8")
        st.save()
        self.gesagte: list[str] = []

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -------------------------------------------------------------- Helfer
    def _mit_gesagten(self):
        self.gesagte = []
        self.orch.say = lambda t: self.gesagte.append(str(t))

    def _ein_durchlauf(self, mode: str = "ok"):
        """Genau EIN Schleifendurchlauf (Review + evtl. Wiederholung + Gate)."""
        self._mit_gesagten()
        self.orch.mock_reviewer_mode = mode
        st = self.orch.state
        st.data["paused"] = False
        st.clear_gate()
        st.save()
        echt = self.orch.do_review

        def einmal(*a, **k):
            res = echt(*a, **k)
            self.orch.quit = True          # nach diesem Durchlauf die Schleife verlassen
            return res

        self.orch.do_review = einmal
        with mock.patch.object(self.orch, "peak_gate", lambda: (True, "")):
            with mock.patch("hx.orchestrator.time.sleep", lambda *_: None):
                self.orch._loop()
        self.orch.quit = False
        return self.gesagte

    def _queue_leeren(self):
        done = self.root / "inbox" / "done"
        if done.is_dir():
            for p in done.glob("*.md"):
                p.unlink()

    def _queue_nachricht(self, text: str = "Bitte die Audio-Frage klaeren.") -> Path:
        self._queue_leeren()
        p = queue.enqueue(self.root, "claude", text, "telegram", "47190682")
        return p


# ------------------------------------------------------- 1) Kennung der Session
class TestSessionKennung(Base):
    def test_neue_session_ohne_vorgabe_bekommt_frische_kennung(self):
        cmd = rvmod.build_command(self.cfg, None, new_session=True)
        neue = rvmod.session_id_of_command(cmd)
        self.assertTrue(neue and len(neue) >= 32, f"frische Kennung erwartet, war {neue!r}")
        self.assertIn("--session-id", cmd)
        self.assertNotIn("--resume", cmd)

    def test_der_aufrufer_uebergibt_die_frische_kennung(self):
        cmd = rvmod.build_command(self.cfg, "frische-abc", new_session=True)
        self.assertEqual(rvmod.session_id_of_command(cmd), "frische-abc")

    def test_fortsetzen_nutzt_resume(self):
        cmd = rvmod.build_command(self.cfg, "laufende-456", new_session=False)
        self.assertEqual(rvmod.session_id_of_command(cmd), "laufende-456")
        self.assertIn("--resume", cmd)
        self.assertNotIn("--session-id", cmd)

    def test_attrappenlauf_meldet_dieselbe_kennung_wie_das_kommando(self):
        res = rvmod.run_review(self.cfg, self.log, "prompt", session_id="frische-789",
                               new_session=True, mock=True)
        self.assertEqual(res.session_id, "frische-789",
                         "Attrappe und echter Lauf muessen dieselbe Kennung melden")


# --------------------------------------------- 2) Rotation + Uebergabe + Review
class TestRotationUndUebergabe(Base):
    def _rotation_mit_uebergabe(self, handover_im_zustand: bool):
        rev = {"session_id": "alte-session-123", "reviews": 2, "force_rotate": True}
        if handover_im_zustand:
            rev["pending_handover"] = {"from_session": "alte-session-123",
                                       "text": "UEBERGABE AUS DEM ZUSTAND: B159 fertig.",
                                       "at": "2026-09-25T22:04:53+00:00"}
        self.orch.state.data["reviewer"] = rev
        self.orch.state.save()

    def test_rotation_holt_die_uebergabe_und_reviewt_in_neuer_session(self):
        self._rotation_mit_uebergabe(handover_im_zustand=False)
        auf = {}
        echt = rvmod.run_review

        def fake(cfg, log, prompt, **kw):
            auf.update(kw)
            auf["prompt"] = prompt
            return echt(cfg, log, prompt, **kw)

        with mock.patch.object(rvmod, "run_handover",
                               lambda *a, **k: "UEBERGABE-MARKE aus der alten Session"):
            with mock.patch.object(rvmod, "run_review", fake):
                self._ein_durchlauf("ok")
        self.assertTrue(auf.get("new_session"), "es muss eine neue Session starten")
        self.assertNotEqual(auf.get("session_id"), "alte-session-123")
        self.assertIn("UEBERGABE-MARKE", auf.get("prompt", ""))
        rev = self.orch.state.data["reviewer"]
        self.assertEqual(rev["session_id"], auf["session_id"],
                         "die Kennung im Zustand ist die Kennung des Laufs")
        self.assertFalse(rev.get("force_rotate"), "die Rotation ist verbraucht")
        self.assertTrue(rev.get("pending_handover", {}).get("text"),
                        "die Uebergabe wird aufbewahrt")
        self.assertTrue((Path(self.cfg.sub("sessions")) /
                         f"claude-{rev['session_id']}.md").is_file())

    def test_vorhandene_uebergabe_wird_wiederverwendet(self):
        self._rotation_mit_uebergabe(handover_im_zustand=True)
        auf = {}
        echt = rvmod.run_review

        def fake(cfg, log, prompt, **kw):
            auf.update(kw)
            auf["prompt"] = prompt
            return echt(cfg, log, prompt, **kw)

        def darf_nicht(*a, **k):
            raise AssertionError("die Uebergabe lag schon vor - kein zweiter Aufruf")

        with mock.patch.object(rvmod, "run_handover", darf_nicht):
            with mock.patch.object(rvmod, "run_review", fake):
                self._ein_durchlauf("ok")
        self.assertIn("UEBERGABE AUS DEM ZUSTAND", auf.get("prompt", ""))
        self.assertIn("Uebergabe wiederverwendet", (self.tmp / "log.jsonl").read_text(
            encoding="utf-8"))


# ------------------------------------- 3) Review ohne Protokollblock -> kein Gate
class TestReviewOhneProtokollblock(Base):
    def _startzustand(self):
        self.orch.state.data["reviewer"] = {"session_id": "laufende-999", "reviews": 4}
        self.orch.state.save()

    def test_zwei_versuche_dann_pause_ohne_gate(self):
        self._startzustand()
        self._queue_nachricht()
        gesagt = self._ein_durchlauf("parser_error")
        st = self.orch.state
        self.assertIsNone(st.gate, "ein Review ohne Protokollblock darf NIE ein Gate oeffnen")
        self.assertEqual(st.state, "PAUSED")
        self.assertTrue(st.data["paused"])
        self.assertIn("Review ohne Protokollblock", str(st.data.get("note")))
        text = "\n".join(gesagt)
        self.assertIn("REVIEW OHNE PROTOKOLLBLOCK", text)
        self.assertIn("REVIEW ZWEIMAL OHNE PROTOKOLLBLOCK", text)
        self.assertIn("NICHTS frei", text)
        ziel = self.root / "runs" / "b160"
        self.assertEqual(len(list(ziel.glob("review-verworfen-*-v1.md"))), 1,
                         "Rohantwort 1 als Beleg")
        self.assertEqual(len(list(ziel.glob("review-verworfen-*-v2.md"))), 1,
                         "Rohantwort 2 als Beleg")
        self.assertFalse((ziel / "review.md").is_file())
        self.assertEqual(len(list((self.root / "logs").glob("review-verworfen-*.json"))), 1,
                         "ein Protokolleintrag in logs/")
        self.assertEqual(int((st.data["reviewer"] or {}).get("reviews", 0)), 4,
                         "ein ungueltiger Review zaehlt nicht")

    def test_queue_bleibt_liegen_wenn_der_review_scheitert(self):
        self._startzustand()
        p = self._queue_nachricht()
        kennung = queue.pending(self.root, "claude")[0].id
        self._ein_durchlauf("parser_error")
        self.assertTrue(p.is_file(), "die Nachricht bleibt in inbox/claude")
        self.assertEqual(str(p.parent.name), "claude")
        self.assertEqual([i.id for i in queue.pending(self.root, "claude")], [kennung])
        self.assertNotIn(kennung, self.orch.state.data.get("delivered") or [],
                         "nichts als zugestellt verbucht")
        self.assertFalse((self.root / "inbox" / "done" / p.name).is_file())

    def test_modellabweichung_gibt_ebenfalls_nichts_frei(self):
        self._startzustand()
        self._ein_durchlauf("modell_falsch")
        st = self.orch.state
        self.assertIsNone(st.gate)
        self.assertEqual(st.state, "PAUSED")
        self.assertIn("Modell", str(st.data.get("note")))

    def test_zweiter_versuch_gelingt_und_oeffnet_das_gate(self):
        self._startzustand()
        p = self._queue_nachricht()
        self._ein_durchlauf("ok_zweiter_versuch")
        st = self.orch.state
        self.assertIsNotNone(st.gate, "der zweite Versuch liefert einen Auftrag")
        self.assertEqual((st.gate.get("tools") or {}).get("batch"), 160,
                         "die Freigabe gilt fuer den Anker-Nachfolger (160)")
        ziel = self.root / "runs" / "b160"
        self.assertTrue((ziel / "review.md").is_file())
        self.assertEqual(len(list(ziel.glob("review-verworfen-*-v1.md"))), 1,
                         "der erste Versuch bleibt als Beleg")
        self.assertEqual(int((st.data["reviewer"] or {}).get("reviews", 0)), 5,
                         "genau ein gueltiger Review")
        # R13u (2026-09-28): die Nachricht ist mit dem gueltigen Review noch NICHT
        # zugestellt - sie reist im Gate und wird erst bei dessen Freigabe archiviert
        # (bis R13t wurde sie hier schon nach `done/` gelegt und war bei einem
        # verworfenen Gate verloren). Beleg: tests/test_r13u_fixes.py.
        self.assertTrue(p.is_file(), "R13u: Nachricht bleibt bis zur Freigabe liegen")
        self.assertEqual((st.gate or {}).get("claude_queue_ids"), [p.stem])
        self.assertFalse((self.root / "inbox" / "done" / p.name).is_file())
        self.assertNotIn(p.stem, st.data.get("delivered") or [])

    def test_gate_und_verzeichnis_tragen_die_anker_nummer(self):
        self._startzustand()
        self._ein_durchlauf("ok")
        st = self.orch.state
        self.assertEqual((st.gate.get("tools") or {}).get("batch"), 160)
        self.assertEqual(self.orch._review_target, 160)
        self.assertEqual(Path(self.orch._review_dir).name, "b160")
        self.assertTrue((self.root / "runs" / "b160" / "review.md").is_file())
        self.assertFalse((self.root / "runs" / "b160" / "antwort.md").is_file(),
                         "die Belege des bewerteten Laufs bleiben in runs/b159")
        facts = (self.root / "runs" / "b160" / "harness-facts.md").read_text(encoding="utf-8")
        self.assertIn("bewertet wird Batch 159", facts)
        self.assertIn("gilt fuer Batch 160", facts)
        self.assertIn("Wanduhr des Worker-Prozesses", facts)
        self.assertTrue((self.root / "runs" / "b159" / "antwort.md").is_file())


# ------------------------------------------------------------- 4) Queue-Regeln
class TestQueueZustellung(Base):
    def test_ohne_markierung_wird_nichts_verbucht(self):
        p = self._queue_nachricht()
        block, ids = self.orch.read_queue_block("claude", mark=False)
        self.assertIn("Audio-Frage", block)
        self.assertTrue(ids)
        self.assertTrue(p.is_file(), "mark=False laesst die Datei liegen")
        self.assertFalse(self.orch.state.data.get("delivered"))

    def test_commit_verbucht_und_archiviert(self):
        p = self._queue_nachricht()
        block, ids = self.orch.read_queue_block("claude", mark=False)
        self.assertEqual(self.orch.commit_queue("claude", ids), len(ids))
        self.assertFalse(p.is_file())
        self.assertTrue((self.root / "inbox" / "done" / p.name).is_file())
        self.assertTrue(self.orch.state.data.get("delivered"))


# ----------------------------------------------------- 5) Laufzeit = Prozesszeit
class TestLaufzeit(Base):
    def _mitschnitt(self, run_dir: Path, duration_ms: int, api_ms: int) -> Path:
        ensure_dir(run_dir)
        lines = [
            json.dumps({"type": "result", "subtype": "success", "is_error": False,
                        "num_turns": 82, "duration_ms": duration_ms,
                        "duration_api_ms": api_ms, "total_cost_usd": 2.9,
                        "usage": {"input_tokens": 100, "cache_read_input_tokens": 0,
                                  "cache_creation_input_tokens": 0, "output_tokens": 50},
                        "result": "(mock) fertig"}),
        ]
        (run_dir / "auftrag.md").write_text("Ghidra-Profil dieses Laufs: none\n",
                                            encoding="utf-8")
        p = run_dir / "stream.jsonl"
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return p

    def test_rebuild_nimmt_die_wanduhr_nicht_die_api_zeit(self):
        rd = ensure_dir(self.root / "runs" / "b159")
        self._mitschnitt(rd, duration_ms=377257, api_ms=288568)
        res = worker.rebuild_from_stream(self.cfg, self.log, self.orch.state, 159)
        self.assertAlmostEqual(res.duration_s, 377.257, places=3)
        self.assertEqual(res.duration_quelle, "cli")
        self.assertAlmostEqual(res.duration_api_s, 288.568, places=3)
        daten = json.loads((rd / "result.json").read_text(encoding="utf-8"))
        self.assertAlmostEqual(daten["duration_s"], 377.257, places=3)
        self.assertEqual(daten["duration_quelle"], "cli")
        self.assertAlmostEqual(daten["duration_cli_s"], 377.257, places=3)
        self.assertEqual(daten["stats"]["dauer"]["quelle"], "cli")

    def test_dauer_text_nennt_die_quelle_und_den_rueckstau(self):
        res = worker.WorkerResult()
        res.duration_s, res.duration_harness_s = 377.0, 1237.0
        res.duration_quelle = "cli"
        txt = res.dauer_text()
        self.assertIn("Wanduhr des Worker-Prozesses", txt)
        self.assertIn("6m17s", txt)
        self.assertIn("Rueckstau", txt)
        self.assertIn("Wanduhr des Worker-Prozesses",
                      self.orch.dauer_line({"duration_s": 377.257, "duration_quelle": "cli"}))
        ohne = self.orch.dauer_line({})
        self.assertIn("Herkunft unbekannt", ohne)

    def test_attrappe_meldet_die_prozesszeit(self):
        res = worker.run_batch(self.cfg, self.log, self.orch.state, "Batch 160 - Test",
                               "none", None, mock=True)
        self.assertEqual(res.duration_quelle, "cli")
        self.assertAlmostEqual(res.duration_s, 195.0, places=3)   # duration_ms der Attrappe
        self.assertEqual(res.duration_harness_s, 1.0)
        self.assertIn("Wanduhr des Worker-Prozesses", res.dauer_text())


# --------------------------------------------------------- 6) Gueltigkeit/Attrappe
class TestReviewGueltigkeit(Base):
    def test_ok_nur_mit_bloecken_und_modell(self):
        gut = rvmod.run_review(self.cfg, self.log, "p", mock=True, mock_mode="ok", mock_batch=160)
        kaputt = rvmod.run_review(self.cfg, self.log, "p", mock=True,
                                  mock_mode="parser_error", mock_batch=160)
        falsch = rvmod.run_review(self.cfg, self.log, "p", mock=True,
                                  mock_mode="modell_falsch", mock_batch=160)
        self.assertTrue(self.orch.review_ok(gut))
        self.assertFalse(self.orch.review_ok(kaputt))
        self.assertFalse(self.orch.review_ok(falsch))
        self.assertIn("Modell", self.orch.review_fehler_grund(falsch))
        self.assertIn("Protokollblock", self.orch.review_fehler_grund(kaputt))

    def test_wiederholungsversuch_bekommt_die_formaterinnerung(self):
        prompt1 = rvmod.build_prompt(self.cfg, "batch_end", {"batch": 159, "next_batch": 160})
        prompt2 = rvmod.build_prompt(self.cfg, "batch_end",
                                     {"batch": 159, "next_batch": 160, "retry_hint": True,
                                      "previous_raw": "nur Prosa ohne Bloecke"})
        self.assertNotIn("FORMAT-ERINNERUNG", prompt1)
        self.assertIn("FORMAT-ERINNERUNG", prompt2)
        self.assertIn("<DS_TOOLS>", prompt2)
        self.assertIn("nur Prosa ohne Bloecke", prompt2)


if __name__ == "__main__":
    unittest.main()
