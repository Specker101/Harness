"""Tests fuer R13bo (2026-10-02): Modellwahl je Review-Anlass + Takt 4.

Nutzerauftrag (Harness-Wartung, 2026-10-02):

  * `reviewer_modell`      = Sonnet 5.5 - Review eines C-Batches (Dekompilierung),
  * `reviewer_modell_b`    = Opus 5.5  - Review eines B-Strang-/Erkundungs-Batches,
  * unklare Batchart       -> Opus (vorsichtige Seite); Batchart aus `stand.strang_von_batch`,
  * `aussensicht_modell`   = Opus 5.5  - Aussensicht (Meta-Review),
  * `aussensicht_takt`     = 4         - reiner Batch-Takt (Ereignis-Ausloeser unveraendert),
  * das GEWAEHLTE Modell steht in `runs/b<N>/result.json` (Feld `review`) UND in der
    Telegram-Zusammenfassung des Reviews.

Alles ohne API-Kosten: Reviews nur im Attrappenmodus, Zustand/Arbeitsordner in
Wegwerf-Verzeichnissen (`tests/_tmp_r13bo*`). Die Batchart wird gestubbt (kein Zugriff
auf das lebende Decomp-Repo).
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

from hx import ask, aussensicht, reviewer as rv, stand       # noqa: E402
from hx.config import load_config                            # noqa: E402
from hx.orchestrator import Orchestrator                     # noqa: E402
from hx.util import Log, ensure_dir                           # noqa: E402

ANKER = """# Workstream R1B
**Stand:** BATCH 249 (2026-10-02) - irgendwas.
**Naechster Schritt:** (a) **B250:** weiter.
"""


def _stub_strang(strang: str):
    """`stand.strang_von_batch` durch eine feste Batchart ersetzen."""
    return mock.patch.object(stand, "strang_von_batch",
                             lambda cfg, b: {"strang": strang, "quelle": "Stub"})


# ------------------------------------------------------- 1) Modellwahl je Batchart
class TestModellwahl(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config()

    def test_konfigwerte_sind_da(self):
        self.assertEqual(str(self.cfg.get("claude", "reviewer_modell")),
                         "claude-sonnet-5-5")
        self.assertEqual(str(self.cfg.get("claude", "reviewer_modell_b")),
                         "claude-opus-5-5")
        self.assertEqual(str(self.cfg.get("claude", "aussensicht_modell")),
                         "claude-opus-5-5")
        self.assertEqual(str(self.cfg.get("claude", "reviewer_effort")), "high")

    def test_c_batch_bekommt_sonnet(self):
        with _stub_strang("C"):
            modell, art = rv.review_modell(self.cfg, 250)
        self.assertEqual(modell, "claude-sonnet-5-5")
        self.assertEqual(art, "C")

    def test_b_batch_bekommt_opus(self):
        with _stub_strang("B"):
            modell, art = rv.review_modell(self.cfg, 250)
        self.assertEqual(modell, "claude-opus-5-5")
        self.assertEqual(art, "B")

    def test_unklare_art_bekommt_opus(self):
        # Unbekannte/fehlende Art -> vorsichtige Seite: das B-Modell (Opus).
        for strang in ("", "X"):
            with _stub_strang(strang):
                modell, art = rv.review_modell(self.cfg, 250)
            self.assertEqual(modell, "claude-opus-5-5", f"strang={strang!r}")
            self.assertEqual(art, "unklar")

    def test_dateifehler_faellt_auf_opus_zurueck(self):
        with mock.patch.object(stand, "strang_von_batch", side_effect=RuntimeError("kaputt")):
            modell, art = rv.review_modell(self.cfg, 250)
        self.assertEqual(modell, "claude-opus-5-5")
        self.assertEqual(art, "unklar")

    def test_code_vorgaben_spiegeln_die_config(self):
        # Fehlt der Schluessel, greifen die Code-Vorgaben - sie muessen zu harness.toml passen.
        leer = load_config()
        leer.data["claude"].pop("reviewer_modell", None)
        leer.data["claude"].pop("reviewer_modell_b", None)
        with _stub_strang("C"):
            self.assertEqual(rv.review_modell(leer, 1)[0], rv.MODELL_C)
        with _stub_strang("B"):
            self.assertEqual(rv.review_modell(leer, 1)[0], rv.MODELL_B)


# ------------------------------------------------------------- 2) Kommandozeile
class TestKommando(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config()

    def _modell(self, cmd) -> str:
        return cmd[cmd.index("--model") + 1]

    def test_reviewer_default_ist_sonnet(self):
        cmd = rv.build_command(self.cfg, None, True)
        self.assertEqual(self._modell(cmd), "claude-sonnet-5-5")

    def test_reviewer_nimmt_das_uebergebene_modell(self):
        cmd = rv.build_command(self.cfg, None, True, modell="claude-opus-5-5")
        self.assertEqual(self._modell(cmd), "claude-opus-5-5")

    def test_aussensicht_hat_eigenes_modell(self):
        cmd = aussensicht.build_command(self.cfg)
        self.assertEqual(self._modell(cmd), "claude-opus-5-5")

    def test_ask_bleibt_opus(self):
        cmd = ask.build_command(self.cfg)
        self.assertEqual(self._modell(cmd), "claude-opus-5-5")


# ------------------------------------------- 3) Attrappenlauf (Wegwerf-Root)
class Basis(unittest.TestCase):
    """Wegwerf-Root/-Decomp wie in `test_r11_fixes.Base` - kein echter Pfad wird angefasst."""

    def setUp(self):
        self.tmp = ensure_dir(Path(__file__).resolve().parent / "_tmp_r13bo")
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

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestAttrappenlauf(Basis):
    def _lauf(self, strang: str, batch: int = 250):
        with _stub_strang(strang):
            return rv.run_review(self.cfg, self.log, "prompt", mock=True, batch=batch)

    def test_b_batch_traegt_opus(self):
        res = self._lauf("B")
        self.assertEqual(res.model_expected, "claude-opus-5-5")
        self.assertEqual(res.modell_art, "B")
        self.assertTrue(res.model_ok, f"gesehen={res.model_seen}")

    def test_c_batch_traegt_sonnet(self):
        res = self._lauf("C")
        self.assertEqual(res.model_expected, "claude-sonnet-5-5")
        self.assertEqual(res.modell_art, "C")
        self.assertTrue(res.model_ok, f"gesehen={res.model_seen}")


# ------------------------------------------- 4) Beleg in result.json + Telegram-Zeile
class TestBeleg(Basis):
    def setUp(self):
        super().setUp()
        self.orch = Orchestrator(self.cfg, self.log, mock=True,
                                 state_file=self.root / "state" / "run.json")
        # Bewerteter Batch 250 mit einem result.json-Beleg des Worker-Laufs.
        self.rd = ensure_dir(self.root / "runs" / "b250")
        (self.rd / "result.json").write_text(
            json.dumps({"batch": 250, "rc": 0, "stats": {"requests": 7}}), encoding="utf-8")
        self.orch.state.data["batch"] = 250
        self.orch.state.data["last_batch_number"] = 250
        self.orch.state.save()

    def _review(self, strang: str):
        with _stub_strang(strang):
            res = self.orch.do_review("batch_end", "(snapshot)")
        return res

    def test_b_review_steht_als_opus_in_result_json(self):
        res = self._review("B")
        self.assertTrue(self.orch.review_ok(res))
        beleg = json.loads((self.rd / "result.json").read_text(encoding="utf-8"))
        self.assertIn("review", beleg)
        self.assertEqual(beleg["review"]["art"], "B")
        self.assertEqual(beleg["review"]["modell_soll"], "claude-opus-5-5")
        self.assertEqual(beleg["review"]["batch"], 250)
        self.assertEqual(beleg["review"]["effort"], "high")
        # Die Worker-Felder bleiben unberuehrt.
        self.assertEqual(beleg["rc"], 0)
        self.assertEqual(beleg["stats"]["requests"], 7)

    def test_c_review_steht_als_sonnet_in_result_json(self):
        res = self._review("C")
        self.assertTrue(self.orch.review_ok(res))
        beleg = json.loads((self.rd / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(beleg["review"]["art"], "C")
        self.assertEqual(beleg["review"]["modell_soll"], "claude-sonnet-5-5")

    def test_telegram_zeile_nennt_das_modell(self):
        res = self._review("B")
        zeile = self.orch.review_modell_zeile(res)
        self.assertIn("claude-opus-5-5", zeile)
        self.assertIn("B-Batch", zeile)
        self.assertIn("Effort high", zeile)

    def test_review_modell_soll_je_batch(self):
        with _stub_strang("C"):
            self.assertIn("claude-sonnet-5-5 (C)", self.orch.review_modell_soll(250))
        with _stub_strang("B"):
            self.assertIn("claude-opus-5-5 (B)", self.orch.review_modell_soll(250))

    def test_ohne_result_json_wird_nichts_angelegt(self):
        # Ein fehlender Beleg wird NICHT erfunden.
        self.orch.review_in_result(999, rv.ReviewResult(), "batch_end")
        self.assertFalse((self.root / "runs" / "b999" / "result.json").exists())


# ------------------------------------------------------------------ 5) Takt 4
class TestTakt(unittest.TestCase):
    def test_takt_ist_vier(self):
        cfg = load_config()
        self.assertEqual(int(cfg.get("meta", "aussensicht_takt")), 4)
        self.assertEqual(int(aussensicht.STANDARD["every_batches"]), 4)
        self.assertEqual(int(aussensicht.grenzen(cfg)["every_batches"]), 4)

    def test_alter_schluessel_bleibt_gueltig(self):
        cfg = load_config()
        cfg.data["meta"].pop("aussensicht_takt", None)
        cfg.data["meta"]["every_batches"] = 7
        self.assertEqual(aussensicht.takt(cfg), 7)

    def test_vorgabe_ohne_schluessel(self):
        cfg = load_config()
        cfg.data["meta"].pop("aussensicht_takt", None)
        cfg.data["meta"].pop("every_batches", None)
        self.assertEqual(aussensicht.takt(cfg), 4)


if __name__ == "__main__":
    unittest.main()
