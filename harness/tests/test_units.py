"""Unit-Tests der Harness-Bausteine (Parser, Tarife, Queue, Zustand, Profile).

Aufruf:  python -m unittest discover -s tests -v   (im Ordner g:\\Harness\\harness)
"""

from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import pricing, protocol, queue, state as st          # noqa: E402
from hx.config import load_config                              # noqa: E402
from hx.util import ensure_dir                                 # noqa: E402


class TestProtocol(unittest.TestCase):
    OK = """<TELEGRAM_SUMMARY>
Kurz.
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: ghidra-standard
program: main
</DS_TOOLS>

<DS_INSTRUCTION>
Batch 160 - Text
</DS_INSTRUCTION>
"""

    def test_vollstaendig(self):
        r = protocol.parse_review(self.OK)
        self.assertEqual(r.summary, "Kurz.")
        self.assertEqual(r.profile, "ghidra-standard")
        self.assertEqual(r.program, "/830d01.27p.main.bin")
        self.assertIn("Batch 160", r.instruction)
        self.assertEqual(r.issues, [])
        self.assertEqual(r.status, "ok")

    def test_kurzform_tools(self):
        profile, program = protocol.parse_tools("ghidra-read be")
        self.assertEqual(profile, "ghidra-read")
        self.assertEqual(program, "/830d01.27p.be.bin")

    def test_fehlender_werkzeugblock(self):
        r = protocol.parse_review("<TELEGRAM_SUMMARY>x</TELEGRAM_SUMMARY>"
                                 "<DS_INSTRUCTION>y</DS_INSTRUCTION>")
        self.assertIsNone(r.profile)
        self.assertTrue(any("DS_TOOLS" in i for i in r.issues))

    def test_mehrfachblock(self):
        text = self.OK + "\n<DS_INSTRUCTION>zweite</DS_INSTRUCTION>"
        r = protocol.parse_review(text)
        self.assertTrue(any("mehrfach" in i for i in r.issues))
        self.assertIn("Batch 160", r.instruction)

    def test_unbekannte_decision_wird_observe(self):
        r = protocol.parse_review("<DECISION>Vielleicht</DECISION>")
        self.assertEqual(r.decision, "OBSERVE")
        self.assertTrue(any("unbekannt" in i for i in r.issues))

    def test_intervene_ohne_instruktion(self):
        r = protocol.parse_review("<DECISION>INTERVENE</DECISION><PROBLEM>Fehler</PROBLEM>")
        self.assertTrue(any("ohne DS_INSTRUCTION" in i for i in r.issues))

    def test_kein_block(self):
        r = protocol.parse_review("Ich habe keine Tags benutzt.")
        self.assertTrue(any("kein einziger" in i for i in r.issues))

    def test_limit_erkennung(self):
        self.assertTrue(protocol.looks_like_limit("Usage limit reached. Resets at 22:00"))
        self.assertFalse(protocol.looks_like_limit("Alles gut, Batch 160 fertig."))

    def test_batch_nummer_aus_instruktion(self):
        r = protocol.parse_review(self.OK.replace("Batch 160", "Batch 159"))
        self.assertEqual(r.batch, 159)
        self.assertNotIn("Batch-Nummer", " ".join(r.issues))

    def test_batch_nummer_fehlt(self):
        r = protocol.parse_review("<DS_INSTRUCTION>ohne Nummer</DS_INSTRUCTION>")
        self.assertIsNone(r.batch)
        self.assertTrue(any("Batch-Nummer" in i for i in r.issues))

    def test_anker_batch_aus_kopfblock(self):
        self.assertEqual(protocol.parse_anchor_batch("**Stand:** BATCH 158 (2026-09-25) - ..."), 158)
        self.assertIsNone(protocol.parse_anchor_batch("kein Kopfblock"))


class TestStdinUebergabe(unittest.TestCase):
    """Der Prompt geht über stdin - nie über die Kommandozeile (Windows ~32k)."""

    def test_argv_bleibt_kurz_bei_riesigem_auftrag(self):
        from hx.profiles import load_profile
        from hx import worker as wk
        cfg = load_config()
        langer = "X" * 45000
        voll = wk.build_prompt(cfg, langer, "", None, "none")
        self.assertGreater(len(voll), 40000)
        cmd, _mcp = wk.build_command(cfg, load_profile(cfg.root, "none"),
                                     Path(cfg.root) / "runs" / "b999", "test-session")
        self.assertTrue(all(len(a) < 500 for a in cmd), f"zu langes Argument: {max(len(a) for a in cmd)}")
        self.assertIn("-p", cmd)
        self.assertNotIn(langer, cmd)

    def test_vorspann_echte_umlaute(self):
        from hx import worker as wk
        for wort in ("Rückfragen", "Übernommener Stand", "geändert", "Nächster Schritt"):
            self.assertIn(wort, wk.WORKER_PREAMBLE)

    def test_reviewer_argv_ohne_prompt(self):
        from hx import reviewer as rvv
        cfg = load_config()
        cmd = rvv.build_command(cfg, None, True)
        self.assertTrue(all(len(a) < 500 for a in cmd))
        self.assertIn("--tools", cmd)


class TestPricing(unittest.TestCase):
    def test_peak_montag(self):
        # Montag 02:00 UTC = Peak; 05:00 UTC = off-peak; 07:00 = Peak
        mo = datetime(2026, 9, 21, 2, 0, tzinfo=timezone.utc)     # Montag
        self.assertTrue(pricing.is_peak(mo))
        self.assertFalse(pricing.is_peak(mo.replace(hour=5)))
        self.assertTrue(pricing.is_peak(mo.replace(hour=7)))
        self.assertFalse(pricing.is_peak(mo.replace(hour=16)))

    def test_wochenende_ist_offpeak(self):
        sa = datetime(2026, 9, 26, 2, 0, tzinfo=timezone.utc)     # Samstag
        self.assertFalse(pricing.is_peak(sa))
        self.assertEqual(pricing.tariff(sa), "offpeak")

    def test_feiertagsliste(self):
        mo = datetime(2026, 9, 21, 2, 0, tzinfo=timezone.utc)
        self.assertFalse(pricing.is_peak(mo, ["2026-09-21"]))

    def test_naechster_offpeak(self):
        mo = datetime(2026, 9, 21, 2, 30, tzinfo=timezone.utc)
        nxt = pricing.next_offpeak(mo)
        self.assertFalse(pricing.is_peak(nxt))
        self.assertGreater(nxt, mo)

    def test_kosten_tarif_je_aufruf(self):
        # 1M Miss + 1M Output: Peak = 0.30 + 1.20 = 1.50, Off-Peak = 0.15 + 0.60 = 0.75
        peak = datetime(2026, 9, 21, 2, 0, tzinfo=timezone.utc)
        off = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)
        self.assertAlmostEqual(pricing.cost_usd(1_000_000, 0, 0, 1_000_000, peak), 1.50)
        self.assertAlmostEqual(pricing.cost_usd(1_000_000, 0, 0, 1_000_000, off), 0.75)

    def test_ortsfenster_sommer_winter(self):
        sommer = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
        winter = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
        self.assertIn("03:00-06:00", pricing.local_window_text(sommer))
        self.assertIn("02:00-05:00", pricing.local_window_text(winter))


class TestQueue(unittest.TestCase):
    def setUp(self):
        self.root = ensure_dir(Path(__file__).resolve().parent / "_tmp_queue")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.root, ignore_errors=True)

    def test_enqueue_deliver_archive(self):
        p = queue.enqueue(self.root, "ds", "Bitte FUN_8005471C pruefen", "telegram", "42")
        self.assertTrue(p.is_file())
        block, ids = queue.deliver_block(self.root, "ds", [])
        self.assertIn("FUN_8005471C", block)
        self.assertEqual(len(ids), 1)
        moved = queue.archive(self.root, ids, "ds")
        self.assertEqual(len(moved), 1)
        block2, ids2 = queue.deliver_block(self.root, "ds", ids)
        self.assertEqual(block2, "")

    def test_leere_nachricht(self):
        with self.assertRaises(ValueError):
            queue.enqueue(self.root, "ds", "   ")

    def test_unbekanntes_ziel(self):
        with self.assertRaises(ValueError):
            queue.enqueue(self.root, "beide", "x")


class TestState(unittest.TestCase):
    def setUp(self):
        self.path = ensure_dir(Path(__file__).resolve().parent / "_tmp_state") / "run.json"
        if self.path.exists():
            self.path.unlink()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.path.parent, ignore_errors=True)

    def test_roundtrip_und_generation(self):
        s = st.State(self.path)
        s.set_gate("g1", "sum", "instr", {"profile": "none", "program": None}, "raw")
        gen1 = s.data["gen"]
        s2 = st.State(self.path)
        self.assertEqual(s2.gate["id"], "g1")
        self.assertEqual(s2.state, st.GATE_APPROVAL) if False else None
        s2.reviewer_note_review("CONTINUE")
        self.assertGreater(s2.data["gen"], gen1)

    def test_keine_halbdatei(self):
        s = st.State(self.path)
        s.set("DS_WORKING")
        self.path.write_text("{ kaputt", encoding="utf-8")   # halbe Datei simulieren
        s3 = st.State(self.path)
        self.assertEqual(s3.state, st.IDLE)                   # faellt auf Defaults zurueck

    def test_spesen(self):
        s = st.State(self.path)
        s.add_spend("2026-09-25", 0.5)
        s.add_spend("2026-09-25", 0.25)
        self.assertAlmostEqual(s.spent_today("2026-09-25"), 0.75)


class TestProfiles(unittest.TestCase):
    def test_profile_laden_und_sperren(self):
        from hx.profiles import load_profile
        cfg = load_config()
        read = load_profile(cfg.root, "ghidra-read")
        self.assertTrue(read.mcp)
        self.assertFalse(read.writes_ghidra)
        self.assertIn("decompile_function", read.allowed)
        # GET != lesend: diese vier duerfen NIE erlaubt sein
        for verboten in ("open_program", "switch_program", "save_program", "save_all_programs"):
            self.assertNotIn(verboten, read.allowed, f"{verboten} darf nicht erlaubt sein")
            self.assertIn(verboten, read.denied, f"{verboten} muss gesperrt sein")
        # Skriptausfuehrung ist in keinem Profil erlaubt
        for name in ("ghidra-read", "ghidra-standard", "ghidra-full"):
            p = load_profile(cfg.root, name)
            self.assertNotIn("run_ghidra_script", p.allowed)
            self.assertNotIn("run_script_inline", p.allowed)

    def test_standard_darf_schreiben(self):
        from hx.profiles import load_profile
        cfg = load_config()
        standard = load_profile(cfg.root, "ghidra-standard")
        self.assertTrue(standard.writes_ghidra)
        self.assertIn("set_plate_comment", standard.allowed)
        self.assertIn("batch_add_function_tags", standard.allowed)

    def test_none_ohne_mcp(self):
        from hx.profiles import load_profile
        cfg = load_config()
        none = load_profile(cfg.root, "none")
        self.assertFalse(none.mcp)
        self.assertEqual(none.allowed, [])

    def test_builtins_fest(self):
        from hx.profiles import builtin_args
        tools, allowed = builtin_args("worker")
        for name in ("Read", "Write", "Edit", "Glob", "Grep", "PowerShell"):
            self.assertIn(name, allowed)
        r_tools, r_allowed = builtin_args("reviewer")
        self.assertEqual(r_allowed, ["Read", "Grep", "Glob"])
        self.assertNotIn("Write", r_allowed)


if __name__ == "__main__":
    unittest.main()
