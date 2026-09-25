"""Attrappen-Tests fuer die vier Korrekturen aus R10.

  1. Batch-Nummer kommt ausschliesslich aus dem Anker; bei Abweichung wird
     angehalten statt "mit 1 weiterzuarbeiten". Run-Verzeichnis und
     Checkpoint-Tag tragen die echte Nummer.
  2. Telegram: die vollstaendige Instruktion, /last liefert sie ganz.
  3. watch: Farben abschaltbar, ohne Argument dem Geschehen folgen, Reviewer
     als Mitschnitt.
  4. Profil none: kein Ghidra-Programmwechsel, keine Sicherung.

Alles laeuft in Wegwerf-Verzeichnissen; der echte Eingang und das Decomp-Repo
bleiben unberuehrt.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import control, mock as hxmock, protocol, queue, watch, worker   # noqa: E402
from hx.config import load_config                                        # noqa: E402
from hx.orchestrator import Orchestrator                                 # noqa: E402
from hx.util import Log, ensure_dir                                      # noqa: E402

ANKER = """# Workstream R1B
**Stand:** BATCH 158 (2026-09-25) - irgendwas Messbares.
**Fertig:** (1) dies, (2) das.
**Naechster Schritt:** (a) **B159:** `80054AE4` verdrahten; danach (b) Scheibe B.
**Offene Entscheidung:** (1) offen.
**Fallstricke/Regeln:** R386 gilt.

## ARCHIV - Stand Batch 157
**Naechster Schritt:** (a) **B158:** etwas Altes.
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = ensure_dir(Path(__file__).resolve().parent / "_tmp_r10")
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

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _subprocess_git(self, *args: str) -> int:
        return subprocess.run(["git", "-C", str(self.repo), *args],
                              capture_output=True).returncode


# --------------------------------------------------------------- 1. Nummer
class TestBatchNummer(Base):
    def test_anker_nummer_und_querverweis(self):
        text = (self.repo / "analysis" / "r1b-workstream.md").read_text(encoding="utf-8")
        self.assertEqual(protocol.parse_anchor_batch(text), 158)
        self.assertEqual(protocol.parse_anchor_next_hint(text), 159)   # erster Treffer = Kopf
        self.assertEqual(self.orch.expected_batch(), 159)
        self.assertIn("159", self.orch.batch_number_line())

    def test_ohne_anker_keine_nummer(self):
        (self.repo / "analysis" / "r1b-workstream.md").write_text("# leer\n", encoding="utf-8")
        self.assertEqual(self.orch.expected_batch(), 0)
        self.assertIn("UNBEKANNT", self.orch.batch_number_line())

    def test_review_prompt_nennt_die_anker_nummer(self):
        from hx import reviewer as rv
        ctx = self.orch.review_context("(snapshot)")
        prompt = rv.build_prompt(self.cfg, "bootstrap", ctx)
        self.assertIn("Naechster Batch laut Anker: 159", prompt)
        self.assertIn("Anker-Kopf nennt BATCH 158", prompt)
        self.assertIn("Querverweis im Anker: B159", prompt)
        self.assertNotIn("der naechste Batch ist", prompt)       # kein interner Zaehler
        self.assertNotIn("Batch-Nummer: 0", prompt)
        self.assertIn('MUSS mit "Batch 159 - ..." beginnen', prompt)

    def test_instruktion_mit_falscher_nummer_haelt_an(self):
        p = protocol.parse_review(
            "<TELEGRAM_SUMMARY>ok</TELEGRAM_SUMMARY>\n"
            "<DS_TOOLS>profile: none</DS_TOOLS>\n"
            "<DS_INSTRUCTION>Batch 1 - falsch</DS_INSTRUCTION>")
        gesagt: list[str] = []
        self.orch.say = lambda t: gesagt.append(t)
        status = self.orch.gate_from_review(p, "(test)")
        self.assertEqual(status, "number_mismatch")
        self.assertTrue(self.orch.state.data["paused"])
        self.assertIn("PAUSED", self.orch.state.state)
        gate = self.orch.state.gate
        self.assertIsNotNone(gate, "der Auftrag bleibt erhalten")
        self.assertEqual(gate["tools"]["batch"], 1)
        self.assertEqual(gate["tools"]["expected"], 159)
        text = "\n".join(gesagt)
        self.assertIn("nennt Batch 1", text)
        self.assertIn("Batch 159", text)
        self.assertIn("Ich starte diesen Auftrag NICHT", text)
        self.assertIn("/number 159", text)

    def test_number_befehl_korrigiert_die_nummer(self):
        p = protocol.parse_review(
            "<TELEGRAM_SUMMARY>ok</TELEGRAM_SUMMARY>\n"
            "<DS_TOOLS>profile: none</DS_TOOLS>\n"
            "<DS_INSTRUCTION>Batch 1 - falsch</DS_INSTRUCTION>")
        self.orch.say = lambda *a, **k: None
        self.orch.gate_from_review(p, "(test)")
        self.orch._do_number("159")
        gate = self.orch.state.gate
        self.assertEqual(gate["tools"]["batch"], 159)
        self.assertTrue(gate["tools"]["number_set_by_user"])
        self.orch._do_approve()
        self.assertEqual(self.orch.approved_gate, gate["id"])

    def test_number_befehl_ohne_gate(self):
        gesagt: list[str] = []
        self.orch.say = lambda t: gesagt.append(t)
        self.orch._do_number("159")
        self.assertIn("Kein offener Auftrag", gesagt[0])

    def test_passen_de_zahl_startet_normal(self):
        p = protocol.parse_review(
            "<TELEGRAM_SUMMARY>ok</TELEGRAM_SUMMARY>\n"
            "<DS_TOOLS>profile: ghidra-read\nprogram: main</DS_TOOLS>\n"
            "<DS_INSTRUCTION>Batch 159 - Auftrag</DS_INSTRUCTION>")
        self.assertEqual(self.orch.gate_from_review(p, "(test)"), "ok")
        self.assertFalse(self.orch.state.data["paused"])
        self.assertEqual(self.orch.state.gate["tools"]["batch"], 159)

    def test_review_verzeichnis_und_mitschnitt(self):
        self.orch.say = lambda *a, **k: None
        res = self.orch.do_review("bootstrap", self.orch.build_snapshot_text())
        rd = self.root / "runs" / "b159"
        self.assertTrue((rd / "review-pre.md").is_file(), "Review nach echter Nummer")
        self.assertTrue((rd / "reviewer.jsonl").is_file(), "Reviewer-Mitschnitt daneben")
        self.assertIn("Batch 159", res.text)
        self.assertFalse((self.root / "runs" / "b000").exists())

    def test_batch_ende_review_heisst_review_md(self):
        self.orch.state.data["batch"] = 159
        self.orch.state.data["last_batch_number"] = 159
        self.orch.state.save()
        self.orch.say = lambda *a, **k: None
        self.orch.do_review("batch_end", "(snapshot)")
        self.assertTrue((self.root / "runs" / "b159" / "review.md").is_file())

    def test_checkpoint_tag_traegt_die_echte_nummer(self):
        from hx.gitsafe import Git
        for p in ("init", "-q"):
            self._subprocess_git(p)
        (self.repo / "a.txt").write_text("eins\n", encoding="utf-8")
        self._subprocess_git("add", "a.txt")
        self._subprocess_git("-c", "user.name=T", "-c", "user.email=t@example.invalid",
                             "commit", "-q", "-m", "start")
        tag = Git(self.cfg, self.log).checkpoint(159)
        self.assertEqual(tag, "harness/b159-start")


# ------------------------------------------------------------- 2. Telegram
class TestTelegramVollstaendig(Base):
    def test_split_message_haelt_die_grenze_auch_bei_langen_zeilen(self):
        from hx.telegram import split_message
        text = "A" * 9000 + "\n" + "B" * 100
        teile = split_message(text, 4000)
        self.assertTrue(all(len(t) <= 4000 for t in teile))
        self.assertEqual("".join(teile), text)

    def test_gate_meldung_ist_vollstaendig(self):
        from hx import mock as mk
        lang = mk.REVIEWER_OK.replace("(Erster Arbeitsschritt.)", "X" * 9000)
        p = protocol.parse_review(lang)
        gesagt: list[str] = []
        self.orch.say = lambda t: gesagt.append(t)
        self.orch.gate_from_review(p, "(test)")
        self.orch.say("Instruktion (vollstaendig):\n" + p.instruction)
        voll = [t for t in gesagt if "Instruktion (vollstaendig)" in t]
        self.assertTrue(voll, "die Instruktion wird gemeldet")
        self.assertIn("X" * 9000, voll[0], "auch der lange Teil ist dabei")
        # und die Telegram-Schicht teilt sie in 4000er Stuecke
        from hx.telegram import split_message
        self.assertTrue(all(len(t) <= 4000 for t in split_message(voll[0])))

    def test_last_liefert_die_ganze_instruktion(self):
        p = protocol.parse_review(
            "<TELEGRAM_SUMMARY>kurz</TELEGRAM_SUMMARY>\n"
            "<DS_TOOLS>profile: none</DS_TOOLS>\n"
            "<DS_INSTRUCTION>Batch 159 - " + "Y" * 6000 + "</DS_INSTRUCTION>")
        self.orch.say = lambda *a, **k: None
        self.orch.state.set_gate("g1", p.summary, p.instruction, {"profile": "none"}, "(test)")
        gesagt: list[str] = []
        self.orch.say = lambda t: gesagt.append(t)
        self.orch.handle_command("/last claude")
        self.assertIn("Y" * 6000, gesagt[0])
        self.assertIn("vollstaendig", gesagt[0])


# ---------------------------------------------------------------- 3. watch
class TestWatch(Base):
    def _capture(self, fn) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn()
        return buf.getvalue()

    def test_farben_abschaltbar_und_ohne_konsole_aus(self):
        w = watch.Watcher(self.cfg, self.log, color=False)
        self.assertFalse(w.color)
        self.assertNotIn("\x1b", self._capture(lambda: w._p("hallo", "bold")))
        w.color = True                      # erzwungen: Codes muessen kommen
        self.assertIn("\x1b[1m", self._capture(lambda: w._p("hallo", "bold")))

    def test_ohne_argument_zeigt_die_wartende_freigabe(self):
        p = protocol.parse_review(
            "<TELEGRAM_SUMMARY>Zusammenfassung</TELEGRAM_SUMMARY>\n"
            "<DS_TOOLS>profile: none</DS_TOOLS>\n"
            "<DS_INSTRUCTION>Batch 159 - Doku</DS_INSTRUCTION>")
        self.orch.say = lambda *a, **k: None
        self.orch.gate_from_review(p, "(test)")
        out = self._capture(lambda: watch.Watcher(self.cfg, self.log, once=True).run())
        self.assertIn("FREIGABE WARTET", out)
        self.assertIn("Batch 159", out)
        self.assertIn("Batch 159 - Doku", out)
        self.assertIn("/approve", out)

    def test_ohne_argument_zeigt_laufenden_review(self):
        self.orch.state.data["state"] = "CLAUDE_REVIEWING"
        self.orch.state.data["note"] = "bootstrap"
        self.orch.state.save()
        ensure_dir(self.root / "runs" / "b159")
        (self.root / "logs").mkdir(parents=True, exist_ok=True)
        (self.root / "logs" / "review-prompt-x.md").write_text(
            "BOOTSTRAP-REVIEW.\nNaechster Batch laut Anker: 159\n", encoding="utf-8")
        out = self._capture(lambda: watch.Watcher(self.cfg, self.log, once=True).run())
        self.assertIn("REVIEW LAEUFT seit", out)
        self.assertIn("Naechster Batch laut Anker: 159", out)

    def test_zeigt_den_reviewer_mitschnitt(self):
        self.orch.say = lambda *a, **k: None
        self.orch.do_review("bootstrap", "(snapshot)")
        out = self._capture(lambda: watch.Watcher(self.cfg, self.log, batch=159).run())
        self.assertIn("REVIEWER:", out)                                  # Mitschnitt des Laufs
        self.assertIn("Read(file_path=analysis/r1b-workstream.md)", out)
        self.assertIn("REVIEWER (b159/review-pre.md)", out)              # und die Antwort
        self.assertIn("Instruktion (DS_INSTRUCTION)", out)

    def test_replay_ohne_mitschnitt_meldet_sauber(self):
        self.assertEqual(watch.Watcher(self.cfg, self.log, batch=999).run(), 1)

    def test_watch_ziel_aus_dem_anker(self):
        w = watch.Watcher(self.cfg, self.log)
        self.assertEqual(w._target_batch(self.orch.state.data), 159)
        self.assertEqual(w._run_dir(), self.root / "runs" / "b159")


# ------------------------------------------------------------ 4. Profil none
class TestProfilNone(Base):
    def test_profil_none_hat_kein_ghidra(self):
        from hx.profiles import load_profile
        p = load_profile(self.root, "none")
        self.assertFalse(p.mcp)
        self.assertFalse(p.writes_ghidra)
        from hx.worker import write_mcp_config
        self.assertIsNone(write_mcp_config(self.cfg, self.root / "runs" / "b159", p))

    def test_gate_verwirft_das_programm_bei_none(self):
        p = protocol.parse_review(
            "<TELEGRAM_SUMMARY>ok</TELEGRAM_SUMMARY>\n"
            "<DS_TOOLS>profile: none\nprogram: /830d01.27p.main.bin</DS_TOOLS>\n"
            "<DS_INSTRUCTION>Batch 159 - nur Doku</DS_INSTRUCTION>")
        self.orch.gate_from_review(p, "(test)")
        tools = self.orch.state.gate["tools"]
        self.assertIsNone(tools["program"], "Profil none bekommt kein Programm")

    def test_worker_ruft_ghidra_bei_none_nicht_an(self):
        class Boom:
            def __init__(self, *a, **k):
                raise AssertionError("Ghidra darf bei Profil none nicht angefasst werden")

        self.orch.state.data["batch"] = 159
        self.orch.state.save()
        with mock.patch.object(worker, "Ghidra", Boom):
            res = worker.run_batch(self.cfg, self.log, self.orch.state,
                                   "Batch 159 - nur Doku", "none", "/830d01.27p.main.bin",
                                   mock=True)
        self.assertIsNone(res.program)
        self.assertIsNone(res.limits.get("ghidra_backup"))
        self.assertTrue((self.root / "runs" / "b159" / "auftrag.md").is_file())


# ------------------------------------------------------------ 5. Archiv/Queue
class TestArchivWiederEinreihen(Base):
    def test_archivierte_nachricht_erneut_einreihen(self):
        p = queue.enqueue(self.root, "claude", "Die Projektziele ...", "telegram")
        items = queue.pending(self.root, "claude")
        ids = [it.id for it in items]
        self.orch.state.mark_delivered(ids[0])
        queue.archive(self.root, ids, "claude")
        self.assertEqual(queue.pending(self.root, "claude"), [])
        alt = (self.root / "inbox" / "done" / p.name).read_text(encoding="utf-8")
        body = alt.split("---", 2)[2].strip()
        neu = queue.enqueue(self.root, "claude", body, "archiv")
        wieder = queue.pending(self.root, "claude")
        self.assertEqual(len(wieder), 1)
        self.assertEqual(wieder[0].text, "Die Projektziele ...")
        self.assertNotEqual(neu.name, p.name, "neue Datei, neue id")
        block, b_ids = queue.deliver_block(self.root, "claude",
                                           [it.id for it in items])
        self.assertIn("Die Projektziele", block)


if __name__ == "__main__":
    unittest.main()
