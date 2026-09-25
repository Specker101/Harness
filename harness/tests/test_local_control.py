"""Attrappen-Tests für den lokalen Steuerkanal (ohne Telegram, ohne API-Kosten).

Getestet wird der echte Code-Pfad: Orchestrator.check_local_control() mit eigenen
Steuerdateien, dazu die Pausen-Erkennung (HEAD bewegt / Arbeitsbaum unsauber) in
einem eigenen Wegwerf-Git-Repo (das Decomp-Repo wird NICHT angefasst).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import control, queue                                 # noqa: E402
from hx.config import load_config                              # noqa: E402
from hx.orchestrator import Orchestrator                       # noqa: E402
from hx.util import Log, ensure_dir                            # noqa: E402


def _git(repo: Path, *args: str) -> int:
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    return p.returncode


class TestLocalControl(unittest.TestCase):
    def setUp(self):
        self.tmp = ensure_dir(Path(__file__).resolve().parent / "_tmp_control")
        shutil.rmtree(self.tmp, ignore_errors=True)
        ensure_dir(self.tmp)
        self.repo = ensure_dir(self.tmp / "repo")

        _git(self.repo, "init", "-q")
        (self.repo / "a.txt").write_text("eins\n", encoding="utf-8")
        _git(self.repo, "add", "a.txt")
        _git(self.repo, "-c", "user.name=T", "-c", "user.email=t@example.invalid",
             "commit", "-q", "-m", "start")
        self.base = _git(self.repo, "rev-parse", "--short", "HEAD")

        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.tmp / "root")
        cfg.data["paths"]["decomp"] = str(self.repo)
        cfg.data["paths"]["secrets"] = str(ensure_dir(self.tmp / "secrets"))  # kein Token
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["telegram"]["allowlist_user_ids"] = []
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)
        self.orch = Orchestrator(cfg, self.log, mock=True,
                                 state_file=self.tmp / "root" / "state" / "run.json")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ------------------------------------------------------------ Steuerdateien
    def test_ctl_roundtrip(self):
        for name in ("pause", "resume", "stop", "approve"):
            control.put(self.cfg, name, "text")
            self.assertIn(name, control.pending(self.cfg))
            self.assertEqual(control.take(self.cfg, name), "text")
            self.assertIsNone(control.take(self.cfg, name))

    def test_unbekannter_befehl(self):
        with self.assertRaises(ValueError):
            control.put(self.cfg, "selbstzerstoerung")

    def test_instruction_roundtrip(self):
        control.put_instruction(self.cfg, "Batch 159 - Text", "ghidra-read",
                                "/830d01.27p.main.bin", "ziel.md")
        obj = control.take_instruction(self.cfg)
        self.assertEqual(obj["profile"], "ghidra-read")
        self.assertEqual(obj["source"], "user")
        self.assertIsNone(control.take_instruction(self.cfg))

    # -------------------------------------------------- Befehle erreichen die Schleife
    def test_pause_resume_ueber_steuerdatei(self):
        control.put(self.cfg, "pause")
        self.orch.check_local_control()
        self.assertTrue(self.orch.state.data["paused"])
        self.assertIn("pause_since", self.orch.state.data)

        control.put(self.cfg, "resume")
        self.orch.check_local_control()
        self.assertFalse(self.orch.state.data["paused"])
        # nichts geaendert -> kein Hinweis
        self.assertFalse(self.orch.state.data.get("pause_work"))

    def test_stop_ueber_steuerdatei(self):
        control.put(self.cfg, "stop")
        self.orch.check_local_control()
        self.assertTrue(self.orch.state.data["stopped"])
        self.assertTrue(self.orch.stop_requested)

    def test_eigene_instruktion_am_reviewer_vorbei(self):
        control.put_instruction(self.cfg, "Batch 159 - eigener Auftrag", "none", None, "x.md")
        self.orch.check_local_control()
        gate = self.orch.state.gate
        self.assertIsNotNone(gate)
        self.assertEqual(gate["tools"]["source"], "user")
        self.assertEqual(gate["tools"]["batch"], 159)
        self.assertEqual(gate["tools"]["profile"], "none")
        self.assertIn("VOM NUTZER", self.orch.status_text())

    # ------------------------------------------------------- Pause + Handarbeit
    def test_resume_erkennt_bewegten_head(self):
        self.orch._do_pause("test")
        (self.repo / "a.txt").write_text("zwei\n", encoding="utf-8")
        _git(self.repo, "add", "a.txt")
        _git(self.repo, "-c", "user.name=T", "-c", "user.email=t@example.invalid",
             "commit", "-q", "-m", "pause-arbeit")
        self.orch._do_resume()
        info = self.orch.state.data.get("pause_work") or {}
        self.assertTrue(info.get("moved"))
        self.assertNotEqual(info.get("head_before"), info.get("head_now"))
        self.assertFalse(self.orch.state.data["paused"])
        note = self.orch.pause_work_note()
        self.assertIn("in der Pause", note)

    def test_resume_wartet_bei_unsauberem_baum(self):
        self.orch._do_pause("test")
        (self.repo / "uncommitted.txt").write_text("offen\n", encoding="utf-8")
        self.orch._do_resume(accept_dirty=False)
        self.assertTrue(self.orch.state.data["paused"], "unsauber -> bleibt pausiert")
        self.assertTrue(self.orch.state.data.get("pause_work"))

    def test_resume_mit_bestaetigung(self):
        self.orch._do_pause("test")
        (self.repo / "uncommitted.txt").write_text("offen\n", encoding="utf-8")
        self.orch._do_resume(accept_dirty=True)
        self.assertFalse(self.orch.state.data["paused"])
        self.assertTrue(self.orch.state.data.get("pause_work"))


class TestLocalQueueAndWatch(unittest.TestCase):
    def setUp(self):
        self.tmp = ensure_dir(Path(__file__).resolve().parent / "_tmp_watch")
        shutil.rmtree(self.tmp, ignore_errors=True)
        ensure_dir(self.tmp)
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.tmp)
        cfg.data["paths"]["secrets"] = str(ensure_dir(self.tmp / "secrets"))
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_send_legt_queue_datei_an(self):
        p = queue.enqueue(self.cfg.root, "claude", "Projektziele ...", "lokal")
        self.assertTrue(p.is_file())
        items = queue.pending(self.cfg.root, "claude")
        self.assertEqual(len(items), 1)
        self.assertIn("Projektziele", items[0].text)

    def test_watch_spielt_abgeschlossenen_batch_nach(self):
        from hx import mock, watch
        rd = ensure_dir(self.tmp / "runs" / "b001")
        mock.mock_worker_stream(self.cfg, rd, "Auftrag", None, mode="ok")
        (rd / "result.json").write_text(
            '{"batch": 1, "rc": 0, "duration_s": 1.0, "stats": {"requests": 5},'
            ' "cost_usd": 0.0042, "model_seen": "deepseek-flash[1m]", "model_ok": true}\n',
            encoding="utf-8")
        (rd / "review.md").write_text(
            "<TELEGRAM_SUMMARY>Alles gut.</TELEGRAM_SUMMARY>\n"
            "<DS_TOOLS>profile: none</DS_TOOLS>\n"
            "<DS_INSTRUCTION>Batch 2 - weiter</DS_INSTRUCTION>\n", encoding="utf-8")
        log = Log(self.tmp / "w.jsonl", echo=False)
        rc = watch.Watcher(self.cfg, log, batch=1).run()
        self.assertEqual(rc, 0)

    def test_watch_spielt_benannten_lauf_nach(self):
        from hx import watch
        rd = ensure_dir(self.tmp / "runs" / "env-proof")
        (rd / "stream.jsonl").write_text('{"type":"assistant","message":{"content":['
                                         '{"type":"text","text":"hallo"}]}}\n',
                                         encoding="utf-8")
        log = Log(self.tmp / "w2.jsonl", echo=False)
        self.assertEqual(watch.Watcher(self.cfg, log, run="env-proof").run(), 0)

    def test_watch_meldet_fehlenden_lauf(self):
        from hx import watch
        log = Log(self.tmp / "w3.jsonl", echo=False)
        self.assertEqual(watch.Watcher(self.cfg, log, run="gibtsnicht").run(), 1)

    def test_control_pid(self):
        self.assertIsNone(control.read_pid(self.cfg))
        pid = control.write_pid(self.cfg)
        self.assertEqual(control.read_pid(self.cfg), pid)
        self.assertTrue(control.runner_alive(self.cfg))     # eigener Prozess lebt
        control.clear_pid(self.cfg)
        self.assertFalse(control.runner_alive(self.cfg))


if __name__ == "__main__":
    unittest.main()
