"""Tests fuer R13bw-5 (2026-10-05): `/autonom yolo` - Dauerbetrieb ohne Peak-Warten.

**Auftrag (Nutzer, 2026-10-05):** „den /autonom Befehl um einen zusätzlichen '/autonom
yolo' erweitern, dass wenn man diesen Befehl [nutzt] nicht drauf geachtet wird, ob gerade
bei DeepSeek Peak oder Offpeak Zeiten sind."

**Regel:**
* `/autonom yolo` setzt zwei Felder: `autonomous` **und** `autonom_trotz_peak` (neu in
  `state.DEFAULTS`).
* Wirksam nur MIT Dauerbetrieb (`Orchestrator.autonom_yolo()`): sonst waere ein vergessener
  Schalter ein stiller Kostentreiber - jeder Start im Peak kostet den doppelten Tarif.
* Beide Peak-Pruefstellen werden uebergangen: die vor dem Review (`_loop`, `gate is None`)
  und die unmittelbar vor dem Start (`warte_auf_offpeak`). Das Gate selbst bleibt bestehen
  (`[peak] block_new_batches`) - yolo **wartet** es nur nicht ab.
* Der teure Start bleibt erkennbar: Log `Peak ignoriert (Dauerbetrieb yolo)` bzw.
  `trotz Peak gestartet (Dauerbetrieb yolo)`, im Zustand und in `result.json` das Feld
  `peak_hinweis` (der Worker reicht es durch, `worker.py`).
* `/autonom on` schaltet yolo **ab**, `/autonom off` beides, ein unbekannter Zusatz aendert
  nichts und nennt den Zustand.

Wegwerf-Verzeichnisse unter `tests/_tmp_r13bw5`.
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

from hx import protocol, state as statemod, telegram             # noqa: E402
from hx.config import load_config                                 # noqa: E402
from hx.orchestrator import Orchestrator                         # noqa: E402
from hx.util import Log, ensure_dir, read_text, write_text_atomic  # noqa: E402

DOKU = ROOT.parent / "docs" / "bedienung.md"
ANKER = """# Workstream R1B

**Stand:** BATCH 180 (2026-10-05) - Beispielstand fuer den Test.
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
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13bw5"
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
        cfg.data["peak"]["block_new_batches"] = True
        cfg.data["peak"]["extra_offpeak_dates"] = []
        cfg.data["peak"]["peak_vorlauf_min"] = 90
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)
        self.orch = Orchestrator(cfg, self.log, mock=True,
                                 state_file=self.root / "state" / "run.json")
        self.gesagt: list[str] = []
        self.orch.say = lambda t="", *a, **k: self.gesagt.append(str(t))
        st = self.orch.state
        st.data["batch"] = 180
        st.data["last_batch_number"] = 180
        st.data["paused"] = False
        st.data["delivered"] = []
        st.clear_gate()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ------------------------------------------------------------------ Helfer
    def text(self) -> str:
        return " ".join(self.gesagt)

    def log_zeilen(self) -> list[str]:
        p = self.tmp / "log.jsonl"
        if not p.is_file():
            return []
        return [str(json.loads(z).get("msg") or "") for z in
                p.read_text(encoding="utf-8").splitlines() if z.strip()]

    def notbremse(self, max_poll: int = 50) -> None:
        zaehler = {"n": 0}

        def poll(*a, **k):
            zaehler["n"] += 1
            if zaehler["n"] > max_poll:
                self.orch.quit = True

        self.orch.poll = poll

    def schleife(self, yolo: bool) -> dict:
        """Einen Schleifendurchlauf im DAUERHAFTEN Peak fahren (Attrappen, kein Netz)."""
        gesehen: dict = {"reviews": 0, "worker": None}
        self.orch.state.data["autonomous"] = True
        self.orch.state.data["autonom_trotz_peak"] = bool(yolo)
        self.orch.review_ok = lambda res: True

        def review(*a, **k):
            gesehen["reviews"] += 1
            return _ReviewStub(batch=self.orch.expected_batch())

        def worker_run(instruction, *a, **k):
            gesehen["worker"] = instruction
            # Der Vermerk steht WAEHREND des Laufs im Zustand - der Worker kopiert ihn in
            # sein Ergebnis (`worker.py`, `peak_hinweis` in `result.json`). Danach wird er
            # verbraucht ("gilt nur fuer diesen einen Start").
            gesehen["hinweis_waehrend_lauf"] = self.orch.state.data.get("peak_hinweis")
            self.orch.quit = True
            return None

        self.orch.do_review = review
        self.orch.run_worker = worker_run
        self.orch.peak_gate = lambda *a, **k: (False, "Peak-Tarif aktiv (Test)")
        self.orch.git_preflight = lambda: (True, "")
        self.orch.git.checkpoint = lambda n: f"harness/b{int(n)}-start"
        self.orch.git_push = lambda: (True, "ok")
        self.orch.mark_harness_head = lambda n: None
        self.notbremse()
        try:
            with mock.patch("hx.orchestrator.time.sleep", lambda *_: None):
                self.orch._loop()
        finally:
            self.orch.quit = False
        return gesehen


# --------------------------------------------------------------- 1) Der Befehl
class TestBefehl(Basis):
    def test_yolo_setzt_beide_schalter(self):
        self.assertTrue(self.orch.handle_command("/autonom yolo"))
        d = self.orch.state.data
        self.assertTrue(d["autonomous"])
        self.assertTrue(d["autonom_trotz_peak"])
        self.assertTrue(self.orch.autonom_yolo())
        self.assertIn("yolo", self.text().lower())
        self.assertIn("PEAK WIRD IGNORIERT", self.text())

    def test_on_schaltet_yolo_ab(self):
        self.orch.handle_command("/autonom yolo")
        self.orch.handle_command("/autonom on")
        self.assertTrue(self.orch.state.data["autonomous"])
        self.assertFalse(self.orch.state.data["autonom_trotz_peak"])
        self.assertFalse(self.orch.autonom_yolo())

    def test_off_schaltet_beides_ab(self):
        self.orch.handle_command("/autonom yolo")
        self.orch.handle_command("/autonom off")
        self.assertFalse(self.orch.state.data["autonomous"])
        self.assertFalse(self.orch.state.data["autonom_trotz_peak"])
        self.assertIn("AUS", self.text())

    def test_unbekannter_zusatz_aendert_nichts(self):
        self.orch.handle_command("/autonom on")
        self.gesagt.clear()
        self.assertTrue(self.orch.handle_command("/autonom quatsch"))
        self.assertTrue(self.orch.state.data["autonomous"], "der Zustand bleibt")
        self.assertFalse(self.orch.state.data["autonom_trotz_peak"])
        self.assertIn("Unbekannter Zusatz", self.text())
        self.assertIn("/autonom [on|off|yolo]", self.text())

    def test_yolo_ohne_dauerbetrieb_wirkt_nicht(self):
        """Ein vergessener Schalter darf nicht still jeden Start verteuern."""
        self.orch.state.data["autonom_trotz_peak"] = True
        self.orch.state.data["autonomous"] = False
        self.assertFalse(self.orch.autonom_yolo())

    def test_dauerbetrieb_text_nennt_yolo(self):
        d = self.orch.state.data
        self.assertEqual(self.orch.dauerbetrieb_text(), "AUS")
        d["autonomous"] = True
        self.assertEqual(self.orch.dauerbetrieb_text(), "AN")
        d["autonom_trotz_peak"] = True
        self.assertEqual(self.orch.dauerbetrieb_text(), "AN (yolo: Peak wird ignoriert)")
        self.assertIn("yolo", self.orch.status_text())


# --------------------------------------------------------------- 2) Das Warten
class TestWarten(Basis):
    def test_yolo_wartet_nicht_und_setzt_den_vermerk(self):
        self.orch.peak_gate = lambda *a, **k: (False, "Peak-Tarif aktiv (Test)")
        s = self.orch.state
        self.assertTrue(self.orch.warte_auf_offpeak(s, 181, trotz_peak=True,
                                                   quelle="Dauerbetrieb yolo"))
        self.assertEqual(s.data.get("peak_hinweis"),
                         "trotz Peak gestartet (Dauerbetrieb yolo)")
        self.assertIn("trotz Peak gestartet (Dauerbetrieb yolo)", self.log_zeilen())
        self.assertIn("Dauerbetrieb yolo", self.text())

    def test_ohne_ausweg_wird_gewartet(self):
        """Kontrolle: ohne yolo bleibt das Verhalten wie in R13al."""
        folge = [False, False, True]          # Takt 1+2 Peak, dann Off-Peak

        def peak_gate(*a, **k):
            if folge:
                return (True, "") if folge.pop(0) else (False, "Peak-Tarif aktiv (Test)")
            return True, ""

        self.orch.peak_gate = peak_gate
        # Im Betrieb liegt hier ein freigegebener Auftrag; die Warteschleife bricht sonst
        # sofort ab (`gate_approved`). Der Gate selbst ist R13al-Territorium.
        self.orch.gate_approved = lambda *a, **k: True
        s = self.orch.state
        with mock.patch("hx.orchestrator.time.sleep", lambda *_: None):
            self.assertTrue(self.orch.warte_auf_offpeak(s, 181))
        self.assertIsNone(s.data.get("peak_hinweis"), "ohne yolo kein 'trotz Peak'-Vermerk")
        self.assertIn("PEAK: Auftrag B181 wartet bis", self.text())
        self.assertIn("PEAK vorbei", self.text())

    def test_offpeak_ist_kein_sonderfall(self):
        self.orch.peak_gate = lambda *a, **k: (True, "")
        s = self.orch.state
        self.assertTrue(self.orch.warte_auf_offpeak(s, 181, trotz_peak=True,
                                                   quelle="Dauerbetrieb yolo"))
        self.assertIsNone(s.data.get("peak_hinweis"), "off-peak braucht keinen Vermerk")


# --------------------------------------------------------------- 3) Die Schleife
class TestSchleife(Basis):
    def test_yolo_startet_im_peak(self):
        gesehen = self.schleife(yolo=True)
        self.assertIsNotNone(gesehen["worker"], f"yolo muss starten; log={self.log_zeilen()}")
        self.assertGreaterEqual(gesehen["reviews"], 1)
        self.assertEqual(gesehen["hinweis_waehrend_lauf"],
                         "trotz Peak gestartet (Dauerbetrieb yolo)")
        self.assertIn("Peak ignoriert (Dauerbetrieb yolo)", self.log_zeilen())
        self.assertIn("trotz Peak gestartet (Dauerbetrieb yolo)", self.log_zeilen())
        self.assertIn("[TROTZ PEAK, Dauerbetrieb yolo]", self.text())
        self.assertFalse(any("PEAK: Auftrag wartet" in z for z in self.log_zeilen()),
                         "yolo wartet nicht")

    def test_ohne_yolo_wartet_der_dauerbetrieb(self):
        """Gleicher Aufbau, yolo aus: im dauerhaften Peak wird NICHT gestartet."""
        gesehen = self.schleife(yolo=False)
        self.assertIsNone(gesehen["worker"], f"ohne yolo darf nichts starten;"
                                             f" log={self.log_zeilen()}")
        self.assertIsNone(self.orch.state.data.get("peak_hinweis"))


# --------------------------------------------------------------- 4) Vorgaben/Doku
class TestVorgabeUndDoku(unittest.TestCase):
    def test_vorgabe_im_zustand(self):
        self.assertIs(statemod.DEFAULTS["autonom_trotz_peak"], False)

    def test_hilfetext_nennt_yolo(self):
        self.assertIn("/autonom [on|off|yolo]", telegram.HELP)
        self.assertIn("wartet den Peak NICHT ab", telegram.HELP)

    def test_bedienung_dokumentiert_den_befehl(self):
        text = read_text(DOKU)
        self.assertIn("/autonom [on|off|yolo]", text)
        self.assertIn("Dauerbetrieb ohne Peak-Warten (R13bw-5)", text)
        self.assertIn("trotz Peak gestartet (Dauerbetrieb yolo)", text)


if __name__ == "__main__":                       # pragma: no cover
    unittest.main()
