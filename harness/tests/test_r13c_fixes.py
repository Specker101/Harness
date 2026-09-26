"""Attrappen-Tests fuer R13c: Entscheidungs-Bremse (A), Denkbloecke in watch (B),
Absturzschutz (C).

Alles im Attrappenbetrieb: keine Kosten, kein Netz, kein Ghidra.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import cli, mock as hxmock, protocol, worker               # noqa: E402
from hx.config import load_config                                  # noqa: E402
from hx.orchestrator import Orchestrator                           # noqa: E402
from hx.util import Log, ensure_dir, read_text, write_text_atomic  # noqa: E402
from hx.watch import Watcher                                       # noqa: E402

ANKER = """# Workstream R1B
**Stand:** BATCH 159 (2026-09-25) - Doku-Batch abgeschlossen.
**Naechster Schritt:** (a) **B160:** cc54-Szene-Ketten-Nachweis.
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = ensure_dir(Path(__file__).resolve().parent / "_tmp_r13c")
        shutil.rmtree(self.tmp, ignore_errors=True)
        ensure_dir(self.tmp)
        self.repo = ensure_dir(self.tmp / "decomp")
        # R13i: ein ECHTES (Wegwerf-)Repo. Der Tempordner liegt im Harness-Repo, und
        # `git` sucht seine Wurzel selbst - ohne eigenes Repo arbeitet es still am
        # aeusseren Repo (Unfall vom 2026-09-26: `wip_rescue` stashte den Harness).
        # `gitsafe.Git` verweigert solche Aufrufe jetzt zusaetzlich.
        subprocess.run(["git", "init", "-q"], cwd=self.repo, capture_output=True)
        ensure_dir(self.repo / "analysis")
        (self.repo / "analysis" / "r1b-workstream.md").write_text(ANKER, encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=self.repo, capture_output=True)
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@example.invalid",
                        "commit", "-q", "-m", "start"], cwd=self.repo, capture_output=True)
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
        st.save()
        self.gesagt: list[str] = []

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -------------------------------------------------------------- Helfer
    def _loop_sicher(self) -> None:
        """Einen Schleifendurchlauf fahren - ohne echtes Git und ohne Endlosschleife.

        Ohne die Bremsen liefe die Schleife endlos weiter, wenn der Auftrag vor dem
        Worker abgelehnt wird (z. B. Git-Vorpruefung im Temp-Verzeichnis).
        """
        zaehler = {"poll": 0}
        echt_poll = self.orch.poll
        echt_pre = self.orch.git_preflight
        echt_chk = self.orch.git.checkpoint

        def poll_ende(*a, **k):
            zaehler["poll"] += 1
            if zaehler["poll"] > 3:
                self.orch.quit = True

        self.orch.poll = poll_ende
        self.orch.git_preflight = lambda: (True, "")
        self.orch.git.checkpoint = lambda n: f"harness/b{int(n)}-start"
        try:
            with mock.patch.object(self.orch, "peak_gate", lambda: (True, "")):
                with mock.patch("hx.orchestrator.time.sleep", lambda *_: None):
                    self.orch._loop()
        finally:
            self.orch.poll = echt_poll
            self.orch.git_preflight = echt_pre
            self.orch.git.checkpoint = echt_chk
            self.orch.quit = False

    def _ein_durchlauf(self, mode: str, stopp_nach_review: bool = True,
                       autonom: bool = False) -> dict:
        """Einen Schleifendurchlauf fahren; merkt sich, ob der Worker gestartet wurde."""
        self.gesagt = []
        self.orch.say = lambda t: self.gesagt.append(str(t))
        self.orch.mock_reviewer_mode = mode
        st = self.orch.state
        st.data["paused"] = False
        st.data["autonomous"] = bool(autonom)
        st.clear_gate()
        st.save()
        auf: dict = {"worker": False}
        echt_review = self.orch.do_review
        echt_worker = self.orch.run_worker

        def einmal(*a, **k):
            res = echt_review(*a, **k)
            if stopp_nach_review:
                self.orch.quit = True
            return res

        def worker_merker(*a, **k):
            auf["worker"] = True
            auf["worker_args"] = a
            self.orch.quit = True
            # NICHT werfen: der Fehlerzweig der Schleife wuerde weiterlaufen.
            return None

        self.orch.do_review = einmal
        self.orch.run_worker = worker_merker
        try:
            self._loop_sicher()
        finally:
            self.orch.do_review = echt_review
            self.orch.run_worker = echt_worker
            self.orch.quit = False
        auf["gesagt"] = list(self.gesagt)
        auf["gate"] = self.orch.state.gate
        auf["state"] = self.orch.state.state
        auf["note"] = self.orch.state.data.get("note")
        return auf


# --------------------------------------------------- 1) Markerzeilen lesen (A)
class TestMarker(Base):
    def test_formen_werden_erkannt(self):
        text = ("Ergebnis:\n"
                "- ENTSCHEIDUNG NOETIG: Audio A oder B?\n"
                "* ENTSCHEIDUNG NÖTIG: Zweite Weiche\n"
                "OFFENE FRAGE: Texturnamen offen.\n"
                "  - WARTET AUF LIVE-AUFNAHME: ein Lauf mit Name-BP fehlt.\n"
                "Normale Zeile ohne Marker\n"
                "ENTSCHEIDUNG NOETIG:\n")           # ohne Text -> zaehlt nicht
        p = protocol.parse_offene_punkte(text)
        self.assertEqual(p["entscheidung"], ["Audio A oder B?", "Zweite Weiche"])
        self.assertEqual(p["frage"], ["Texturnamen offen."])
        self.assertEqual(p["live"], ["ein Lauf mit Name-BP fehlt."])

    def test_parse_review_haengt_die_punkte_an(self):
        r = protocol.parse_review(
            "<TELEGRAM_SUMMARY>\nErgebnis ok.\nENTSCHEIDUNG NOETIG: Audio?\n"
            "</TELEGRAM_SUMMARY>\n<DS_TOOLS>\nprofile: none\n</DS_TOOLS>\n"
            "<DS_INSTRUCTION>\nBatch 160 - Test\n</DS_INSTRUCTION>")
        self.assertEqual(r.offene["entscheidung"], ["Audio?"])
        self.assertEqual(protocol.offene_punkte_kurz(r.offene),
                         ["Offene Entscheidung: Audio?"])


# ------------------------------------------- 2) Entscheidung als Bremse (A)
class TestEntscheidungsBremse(Base):
    def test_autonom_plus_entscheidung_wartet(self):
        auf = self._ein_durchlauf("entscheidung", stopp_nach_review=False, autonom=True)
        self.assertFalse(auf["worker"], "im Dauerbetrieb darf hier NICHT gestartet werden")
        self.assertIsNotNone(auf["gate"], "der Auftrag bleibt liegen")
        self.assertEqual(auf["state"], "GATE_APPROVAL")
        self.assertIn("Entscheidung", str(auf["note"]))
        text = "\n".join(auf["gesagt"])
        self.assertIn("WARTET AUF DEINE ENTSCHEIDUNG", text)
        self.assertIn("Wartet auf deine Entscheidung", text)
        self.assertIn("Audio-Verfahren waehlen", text)

    def test_umlautschreibweise_bremst_ebenfalls(self):
        auf = self._ein_durchlauf("entscheidung_umlaut", stopp_nach_review=False, autonom=True)
        self.assertFalse(auf["worker"])
        self.assertTrue(self.orch.gate_wait_decision(auf["gate"]))

    def test_autonom_plus_offene_frage_laeuft_weiter(self):
        auf = self._ein_durchlauf("offene_frage", stopp_nach_review=False, autonom=True)
        self.assertTrue(auf["worker"], "eine offene Frage bremst nicht")
        self.assertTrue(auf["gesagt"] is not None)

    def test_autonom_plus_live_aufnahme_wartet_nicht(self):
        auf = self._ein_durchlauf("live_aufnahme", stopp_nach_review=False, autonom=True)
        self.assertTrue(auf["worker"], "WARTET AUF LIVE-AUFNAHME bremst nicht")

    def test_autonom_ohne_marker_laeuft_weiter(self):
        auf = self._ein_durchlauf("ok", stopp_nach_review=False, autonom=True)
        self.assertTrue(auf["worker"], "ohne Marker bleibt der Dauerbetrieb wie bisher")

    def test_ohne_dauerbetrieb_wartet_das_gate_ohnehin(self):
        auf = self._ein_durchlauf("entscheidung", stopp_nach_review=False, autonom=False)
        self.assertFalse(auf["worker"])
        self.assertIn("Entscheidung", str(auf["note"]))

    def test_manuelle_freigabe_ist_erlaubt(self):
        "Der Mensch darf auch ein Entscheidungs-Gate freigeben - nur der Automat nicht."
        auf = self._ein_durchlauf("entscheidung", stopp_nach_review=False, autonom=True)
        gate = auf["gate"]
        self.orch.approved_gate = gate["id"]          # wie /approve
        self.orch.state.data["autonomous"] = True
        self.orch.state.save()
        auf2: dict = {"worker": False}

        def worker_merker(*a, **k):
            auf2["worker"] = True
            self.orch.quit = True
            return None

        echt = self.orch.run_worker
        self.orch.run_worker = worker_merker
        try:
            self._loop_sicher()
        finally:
            self.orch.run_worker = echt
            self.orch.quit = False
        self.assertTrue(auf2["worker"], "nach /approve muss gestartet werden")
        self.assertIsNone(self.orch.state.gate)

    def test_altbestand_ohne_feld_wird_abgeleitet(self):
        "Ein Gate ohne offene_punkte-Feld (wie B161 vor dieser Aenderung) zaehlt trotzdem."
        gate = {"id": "ALT1", "created_at": "2026-09-25T23:17:00+00:00",
                "summary": "Ergebnis ok.\nENTSCHEIDUNG NOETIG: Audio A oder B?",
                "instruction": "Batch 161 - Test", "tools": {"batch": 161}, "raw": "-"}
        self.orch.state.data["gate"] = gate
        self.orch.state.save()
        self.assertTrue(self.orch.gate_wait_decision())
        self.assertEqual(self.orch.gate_offene_punkte()["entscheidung"], ["Audio A oder B?"])

    def test_status_zeigt_die_offenen_punkte(self):
        self.orch.state.data["gate"] = {
            "id": "ALT2", "created_at": "-",
            "summary": ("Ergebnis.\nENTSCHEIDUNG NOETIG: Audio A oder B?\n"
                        "OFFENE FRAGE: Texturnamen offen."),
            "instruction": "Batch 161 - Test", "tools": {"batch": 161}, "raw": "-"}
        self.orch.state.save()
        text = self.orch.status_text()
        self.assertIn("Offene Entscheidung: Audio A oder B?", text)
        self.assertIn("Offene Frage: Texturnamen offen.", text)
        self.assertIn("ENTSCHEIDUNG", text)

    def test_offene_punkte_ohne_gate_kommen_aus_dem_letzten_review(self):
        rd = ensure_dir(self.root / "runs" / "b161")
        (rd / "review.md").write_text(
            "<TELEGRAM_SUMMARY>\nErgebnis.\nENTSCHEIDUNG NOETIG: Audio?\n"
            "</TELEGRAM_SUMMARY>\n", encoding="utf-8")
        self.assertIsNone(self.orch.state.gate)
        self.assertIn("Offene Entscheidung: Audio?", "\n".join(self.orch.offene_punkte_zeilen()))


# --------------------------------------------- 3) Denkbloecke in watch (B)
class TestWatchThinking(Base):
    def _watch(self, thinking: bool = True) -> tuple[Watcher, list[str]]:
        out: list[str] = []
        w = Watcher(self.cfg, self.log, batch=160, color=False, thinking=thinking)
        w._p = lambda text="", style="": out.append(str(text))
        return w, out

    def _zeile(self, text: str, art: str = "thinking") -> str:
        block = {"type": art}
        block["thinking" if art == "thinking" else "text"] = text
        return json.dumps({"type": "assistant", "message": {"content": [block]}})

    def test_denkblock_wird_abgesetzt_angezeigt(self):
        w, out = self._watch()
        w._render_line(self._zeile("Erst den Anker lesen, dann cc54 pruefen."))
        self.assertTrue(out)
        self.assertTrue(out[0].startswith("  ~ "), out)
        self.assertIn("cc54", out[0])

    def test_leerer_block_und_abschalter_zeigen_nichts(self):
        w, out = self._watch()
        w._render_line(self._zeile(""))                      # display: omitted
        self.assertEqual(out, [])
        w._render_line(self._zeile("   \n  "))                # nur Leerraum
        self.assertEqual(out, [])
        w2, out2 = self._watch(thinking=False)               # --no-thinking
        w2._render_line(self._zeile("Das steht nicht in der Anzeige."))
        self.assertEqual(out2, [])

    def test_langer_block_wird_gekuerzt_mit_laengenangabe(self):
        w, out = self._watch()
        lang = "Wort " * 400                                 # 2000 Zeichen
        w._render_line(self._zeile(lang))
        self.assertEqual(len(out), 1)
        self.assertIn("[gekuerzt", out[0])
        self.assertIn(f"{len(lang)} Zeichen", out[0])
        self.assertLess(len(out[0]), len(lang))

    def test_normaler_text_bleibt_unveraendert(self):
        w, out = self._watch()
        w._render_line(self._zeile("Bericht steht.", art="text"))
        self.assertIn("Bericht steht.", "\n".join(out))

    def test_schalter_ist_in_der_cli(self):
        args = cli.build_parser().parse_args(["watch", "--batch", "160", "--no-thinking"])
        self.assertTrue(args.no_thinking)
        args2 = cli.build_parser().parse_args(["watch", "--batch", "160"])
        self.assertFalse(args2.no_thinking)

    def test_nachspielen_eines_mitschnitts_zeigt_denkbloecke(self):
        rd = ensure_dir(self.root / "runs" / "b160")
        write_text_atomic(rd / "stream.jsonl",
                          self._zeile("Ich pruefe zuerst die Belege.") + "\n"
                          + json.dumps({"type": "result", "subtype": "success",
                                        "result": "(mock)"}) + "\n")
        write_text_atomic(rd / "result.json", json.dumps({"batch": 160, "duration_s": 1,
                                                          "stats": {"requests": 1}}))
        w, out = self._watch()
        w.run()
        text = "\n".join(out)
        self.assertIn("  ~ Ich pruefe zuerst die Belege.", text)

    def test_gate_zeigt_die_offenen_punkte(self):
        w, out = self._watch()
        w._show_gate({"tools": {"batch": 161, "profile": "ghidra-read"},
                      "summary": "Ergebnis.\nENTSCHEIDUNG NOETIG: Audio A oder B?"})
        text = "\n".join(out)
        self.assertIn("Offene Entscheidung: Audio A oder B?", text)
        self.assertIn("NICHT automatisch freigegeben", text)


# ------------------------------------------------------- 4) Absturzschutz (C)
class TestAbsturzschutz(Base):
    def test_report_crash_schreibt_bericht_und_meldet(self):
        gesagt: list[str] = []
        self.orch.say = lambda t: gesagt.append(str(t))
        try:
            raise KeyError("kaputt")
        except KeyError as exc:
            p = self.orch.report_crash(exc)
        self.assertIsNotNone(p)
        self.assertTrue(Path(p).is_file())
        text = Path(p).read_text(encoding="utf-8")
        self.assertIn("KeyError", text)
        self.assertIn("Traceback", text)
        self.assertIn("Zustand:", text)
        self.assertIn("ABSTURZ", read_text(str(self.log.path)))
        self.assertIn("HARNESS ABGESTÜRZT", "\n".join(gesagt))
        self.assertIn(str(p), "\n".join(gesagt))

    def test_run_haelt_den_absturz_fest_und_reicht_ihn_weiter(self):
        def kaputt(paused=False):
            raise RuntimeError("Loop kaputt")
        with mock.patch.object(Orchestrator, "_loop", staticmethod(kaputt)):
            with self.assertRaises(RuntimeError):
                self.orch.run()
        reports = list((self.root / "logs").glob("crash-*.txt"))
        self.assertEqual(len(reports), 1, "genau ein Absturzbericht")
        self.assertIn("Loop kaputt", reports[0].read_text(encoding="utf-8"))

    def test_status_meldet_toten_prozess_und_bericht(self):
        write_text_atomic(self.root / "logs" / "crash-20260926T010101.txt", "x\n")
        text = self.orch.status_text()
        self.assertIn("HARNESS LAEUFT NICHT", text)
        self.assertIn("Letzter Crash-Bericht: crash-20260926T010101.txt", text)

    def test_cmd_run_gibt_bei_absturz_code_3(self):
        with mock.patch.object(Orchestrator, "run", side_effect=RuntimeError("platt")):
            with mock.patch.object(cli, "load_config", lambda *a, **k: self.cfg):
                code = cli.cmd_run(mock.Mock(config=None, mock=False, paused=False))
        self.assertEqual(code, 3)

    def test_startskript_schreibt_stderr_und_haelt_das_fenster(self):
        text = read_text(str(ROOT / "start.ps1"))
        self.assertIn("start-stderr.log", text)
        self.assertIn("2>> $errLog", text)
        self.assertIn("HARNESS ABGESTUERZT", text)
        self.assertIn("Read-Host", text)


# -------------------------------------------------- 5) Reviewer-Anweisung (A)
class TestReviewerPrompt(Base):
    def test_zwei_formen_und_verbotsregel_stehen_drin(self):
        text = read_text(str(ROOT / "prompts" / "reviewer.md"))
        self.assertIn("OFFENE FRAGE:", text)
        self.assertIn("ENTSCHEIDUNG NOETIG:", text)
        # Verbotene Anweisungen duerfen nicht zusammen mit der Frage kommen.
        for wort in ("Force-Push", "Historie", "analysis/", "restore_project", "AGENTS.md"):
            self.assertIn(wort, text, f"{wort} fehlt im Prompt")


if __name__ == "__main__":
    unittest.main()
