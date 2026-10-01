"""R13bj (01.10.2026): Batchnummer, Lauf-Ordner, vorlaeufige Zeitgrenzen.

Auftrag des Nutzers (zwei Teile), Anlass B235:

  A) Die Nummer zaehlt der **Harness selbst** (letzter Start + 1), der Ankerkopf ist
     nur Gegenprobe - eine Abweichung steht in den Review-Fakten. Nennt die Instruktion
     die Nummer des **bewerteten** Laufs, ist das eine **Fortsetzung** (erlaubt); ein
     fertiger Lauf im Zielordner wird **nicht** ueberschrieben. Die Belege des vorigen
     Laufs wandern nach `runs/b<N>/lauf<k>/`.
  B) Zeitgrenzen vorlaeufig hoeher: `bash_max_timeout_s` 1800 -> 3600 (der Preflight von
     B235 lief mit 1799 s genau dagegen), `hard_wall_s` 10800 -> 14400 (B235 lief 2h53m),
     `timeout=3600000` in Worker-Vorspann und `prompts/reviewer.md`, Rueckbau-Vermerk im
     Handbuch.

Alles laeuft in Wegwerf-Verzeichnissen; der echte Zustand und das Decomp-Repo bleiben
unberuehrt. Belege: `docs/_r13bj_belege.md`.
"""

from __future__ import annotations

import os
import shutil
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import envs, protocol, retention, uhr, worker              # noqa: E402
from hx.config import load_config                                  # noqa: E402
from hx.orchestrator import Orchestrator                           # noqa: E402
from hx.util import Log, ensure_dir                                # noqa: E402

ANKER = """# Workstream R1B
**Stand:** BATCH 158 (2026-10-01) - irgendwas Messbares.
**Fertig:** (1) dies, (2) das.
**Naechster Schritt:** (a) **B159:** `80054AE4` verdrahten.
**Offene Entscheidung:** (1) offen.
**Fallstricke/Regeln:** R386 gilt.
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = ensure_dir(Path(__file__).resolve().parent / "_tmp_r13bj")
        shutil.rmtree(self.tmp, ignore_errors=True)
        ensure_dir(self.tmp)
        self.repo = ensure_dir(self.tmp / "decomp")
        ensure_dir(self.repo / "analysis")
        self.anker_setzen(158)
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

    def anker_setzen(self, nummer: int):
        text = ANKER.replace("BATCH 158", f"BATCH {nummer}")
        (self.repo / "analysis" / "r1b-workstream.md").write_text(text, encoding="utf-8")

    def review(self, instruktion: str):
        return protocol.parse_review(
            "<TELEGRAM_SUMMARY>ok</TELEGRAM_SUMMARY>\n"
            "<DS_TOOLS>profile: none</DS_TOOLS>\n"
            f"<DS_INSTRUCTION>{instruktion}</DS_INSTRUCTION>")


# ------------------------------------------------------------------ A) Nummer
class TestNummer(Base):
    def test_ohne_zaehler_fuehrt_der_anker(self):
        self.assertEqual(self.orch.own_batch(), 0)
        self.assertEqual(self.orch.expected_batch(), 159)
        zeile = self.orch.batch_number_line()
        self.assertIn("Naechster Batch: 159", zeile)
        self.assertIn("noch kein Batch gelaufen", zeile)
        self.assertIn("Anker-Kopf nennt BATCH 158", zeile)
        self.assertIn("noch kein Batch gestartet", self.orch.batch_nummer_fakten_zeile())

    def test_zaehler_fuehrt_anker_ist_gegenprobe_mit_warnung(self):
        self.orch.state.data["last_batch_number"] = 235
        self.assertEqual(self.orch.own_batch(), 236)
        self.assertEqual(self.orch.expected_batch(), 236)
        zeile = self.orch.batch_number_line()
        self.assertIn("Naechster Batch: 236", zeile)
        self.assertIn("Harness-Zaehler", zeile)
        self.assertIn("ABWEICHUNG", zeile)
        fakten = self.orch.batch_nummer_fakten_zeile()
        self.assertIn("Harness-Zaehler 236", fakten)
        self.assertIn("Anker 159", fakten)
        self.assertIn("ABWEICHUNG", fakten)
        self.assertIn("nicht fortgeschrieben", fakten)

    def test_stimmige_nummer_ohne_warnung(self):
        self.anker_setzen(235)
        self.orch.state.data["last_batch_number"] = 235
        self.assertEqual(self.orch.expected_batch(), 236)
        self.assertIn("stimmt", self.orch.batch_number_line())
        self.assertIn("stimmig", self.orch.batch_nummer_fakten_zeile())
        self.assertNotIn("ABWEICHUNG", self.orch.batch_nummer_fakten_zeile())

    def test_state_batch_zaehlt_nicht(self):
        self.orch.state.data["batch"] = 999
        self.assertEqual(self.orch.expected_batch(), 159)

    def test_regel_nennt_naechste_nummer_und_fortsetzung(self):
        self.orch.state.data["last_batch_number"] = 235
        self.orch.state.data["batch"] = 235
        regel = self.orch.batch_nummer_regel()
        self.assertIn("MUSS mit \"Batch <N> - ...\" beginnen", regel)
        self.assertIn("236 ist der NAECHSTE Batch", regel)
        self.assertIn("235 ist die FORTSETZUNG", regel)
        self.assertIn("startet NICHT", regel)


# --------------------------------------------------- A) Fortsetzung und Ordner
class TestFortsetzungUndOrdner(Base):
    def _bewertet(self, nummer: int):
        self.orch.state.data["last_batch_number"] = nummer
        self.orch.state.data["batch"] = nummer
        self.orch.say = lambda t: None

    def test_fortsetzung_wird_erkannt(self):
        self._bewertet(235)
        status = self.orch.gate_from_review(self.review("Batch 235 - Fortsetzung, TEIL 2"),
                                            "(test)")
        self.assertEqual(status, "ok")
        gate = self.orch.state.gate
        self.assertEqual(gate["tools"]["batch"], 235)
        self.assertTrue(gate["tools"]["fortsetzung"], "Fortsetzung muss im Gate stehen")
        self.assertFalse(self.orch.state.data["paused"])

    def test_naechste_nummer_ist_keine_fortsetzung(self):
        self._bewertet(235)
        status = self.orch.gate_from_review(self.review("Batch 236 - neuer Batch"), "(test)")
        self.assertEqual(status, "ok")
        self.assertFalse(self.orch.state.gate["tools"]["fortsetzung"])

    def test_fremde_nummer_haelt_an(self):
        self._bewertet(235)
        gesagt: list[str] = []
        self.orch.say = lambda t: gesagt.append(t)
        status = self.orch.gate_from_review(self.review("Batch 1 - falsch"), "(test)")
        self.assertEqual(status, "number_mismatch")
        self.assertTrue(self.orch.state.data["paused"])
        self.assertIn("Batch 236", "\n".join(gesagt))

    def test_fertiger_lauf_im_ordner_blockiert(self):
        rd = ensure_dir(Path(self.cfg.sub("runs")) / "b236")
        (rd / "result.json").write_text("{}", encoding="utf-8")
        meldung = self.orch.lauf_ordner_blockiert(236)
        self.assertIn("result.json", meldung)
        self.assertIn("ueberschreibe ihn nicht", meldung)
        self.assertIn("lauf<k>", meldung)
        # Als Fortsetzung derselben Nummer ist der belegte Ordner erlaubt.
        self.assertEqual(self.orch.lauf_ordner_blockiert(236, fortsetzung=True), "")

    def test_altbestand_gate_zaehlt_als_fortsetzung(self):
        # Gates, die VOR R13bj entstanden sind, tragen `tools["fortsetzung"]` nicht.
        rd = ensure_dir(Path(self.cfg.sub("runs")) / "b235")
        (rd / "result.json").write_text("{}", encoding="utf-8")
        self.orch.state.data["batch"] = 235
        self.assertEqual(self.orch.lauf_ordner_blockiert(235), "",
                         "die Nummer des zuletzt gestarteten Batches ist eine Fortsetzung")
        self.assertEqual(self.orch.lauf_ordner_blockiert(234), "",
                         "Gegenprobe: ein leeres Zielverzeichnis ist frei")

    def test_freier_ordner_ist_nicht_blockiert(self):
        self.assertEqual(self.orch.lauf_ordner_blockiert(236), "")
        self.assertEqual(self.orch.lauf_ordner_blockiert(0), "")

    def test_lauf_ordner_zeile_zaehlt_die_laeufe(self):
        rd = ensure_dir(Path(self.cfg.sub("runs")) / "b235")
        self.assertIn("1. Lauf", self.orch.lauf_ordner_zeile(235))
        ensure_dir(rd / "lauf1")
        zeile = self.orch.lauf_ordner_zeile(235)
        self.assertIn("2. Lauf", zeile)
        self.assertIn("runs/b235/lauf1", zeile)


# ------------------------------------------------------- A) Belege je Lauf
class TestLaufOrdner(Base):
    def test_nummer_und_verschieben(self):
        rd = ensure_dir(Path(self.cfg.sub("runs")) / "b235")
        (rd / "stream.jsonl").write_text("eins", encoding="utf-8")
        (rd / "mcp.json").write_text("{}", encoding="utf-8")
        (rd / "review.md").write_text("Review", encoding="utf-8")
        self.assertEqual(worker.lauf_ordner_nummer(rd), 1)
        namen = worker.sichere_vorgaenger(rd, self.log)
        self.assertIn("lauf1/stream.jsonl", namen)
        self.assertIn("lauf1/mcp.json", namen)
        self.assertEqual(worker.lauf_ordner_nummer(rd), 2)
        # Das Review bleibt oben stehen (Auftragskette des neuen Laufs).
        self.assertTrue((rd / "review.md").is_file())
        self.assertFalse((rd / "lauf1" / "review.md").exists())

    def test_aufbewahrung_packt_die_lauf_ordner_mit(self):
        rd = ensure_dir(Path(self.cfg.sub("runs")) / "b235" / "lauf1")
        alt = rd / "stream.jsonl"
        alt.write_text("x", encoding="utf-8")
        alt_neu = ensure_dir(Path(self.cfg.sub("runs")) / "b4711")
        (alt_neu / "stream.jsonl").write_text("y", encoding="utf-8")
        vor_30 = time.time() - 30 * 86400
        os.utime(alt, (vor_30, vor_30))
        os.utime(alt_neu / "stream.jsonl", (vor_30, vor_30))
        namen = [str(p) for p in retention.kandidaten(self.cfg, tage=14)]
        self.assertTrue(any("lauf1" in n for n in namen),
                        f"lauf<k>-Mitschnitt fehlt in {namen}")


# ------------------------------------------------------------ B) Zeitgrenzen
class TestZeitgrenzen(unittest.TestCase):
    def test_config_werte(self):
        cfg = load_config()
        self.assertEqual(float(cfg.get("claude", "bash_max_timeout_s")), 3600.0)
        self.assertEqual(float(cfg.get("limits", "hard_wall_s")), 14400.0)
        # Alarm und Umschaltschwelle bleiben unveraendert (nur die harte Grenze stieg).
        self.assertEqual(float(cfg.get("limits", "alarm_wall_s")), 9000.0)
        self.assertEqual(float(cfg.get("limits", "umschalt_vor_alarm_s")), 900.0)

    def test_env_obergrenze_ist_eine_stunde(self):
        cfg = load_config()
        env = envs.worker_env(cfg, dict(os.environ), "token")
        self.assertEqual(env["BASH_MAX_TIMEOUT_MS"], "3600000")
        self.assertEqual(env["BASH_DEFAULT_TIMEOUT_MS"], "600000")

    def test_vorspann_und_reviewer_nennen_dieselbe_zahl(self):
        self.assertIn("timeout=3600000", worker.WORKER_PREAMBLE)
        self.assertIn("bis 3600000 = 60 min", worker.WORKER_PREAMBLE)
        self.assertNotIn("1800000", worker.WORKER_PREAMBLE)
        text = (ROOT / "prompts" / "reviewer.md").read_text(encoding="utf-8")
        self.assertIn("timeout=3600000", text)
        self.assertNotIn("timeout=1800000", text)

    def test_uhr_grenze_passt_zur_hartgrenze(self):
        cfg = load_config()
        hart = float(cfg.get("limits", "hard_wall_s"))
        self.assertGreaterEqual(uhr.MAX_START_ALTER_S, hart,
                                "die Unplausibilitaetsgrenze der Uhr darf unter der "
                                "harten Grenze liegen")

    def test_handbuch_traegt_den_rueckbau_vermerk(self):
        text = (ROOT.parent / "docs" / "bedienung.md").read_text(encoding="utf-8")
        self.assertIn("zurueck auf **1800 s, sobald der Preflight wieder unter 900 s liegt**",
                      text)
        self.assertIn("zurueck auf **10800 s**", text)
        self.assertIn("bash_max_timeout_s", text)
        self.assertIn("hard_wall_s", text)

    def test_handbuch_nennt_die_neue_nummernregel(self):
        text = (ROOT.parent / "docs" / "bedienung.md").read_text(encoding="utf-8")
        self.assertIn("## 8. Batch-Nummern (der Harness zaehlt, der Anker ist Gegenprobe)",
                      text)
        self.assertIn("lauf<k>", text)


if __name__ == "__main__":
    unittest.main()
