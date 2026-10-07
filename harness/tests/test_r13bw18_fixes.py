"""Tests R13bw-18 (08.10.2026): Waechter vor dem Gate-Lauf + Startzustand im Beleg.

**Auftrag (Nutzer, Harness-Wartung).** Die drei Vorschlaege aus meiner Antwort zu R13bw-17:

1. `docs/_r13av_lauf.py` lehnt den Start ab, wenn `state/run.json` einen laufenden Worker
   oder Review zeigt (`worker` gesetzt bzw. `state` in `DS_WORKING`/`CLAUDE_REVIEWING`) -
   klare Meldung, `--trotzdem` als bewusstes Uebersteuern.
2. Der Beleg-Kopf nennt den Zustand **beim Start** und **am Ende**.
3. Die Regel steht in `docs/bedienung.md` bei der Gate-Anleitung (Einleitung + §12z).

Anlass: In R13bw-17 habe ich die volle Reihe gestartet, waehrend Batch 292 seit 2 h 10 min
lief (Zeitachse in `docs/bedienung.md` §12z). Die Einzeltests der betroffenen Dateien waren
richtig, die volle Reihe war es nicht. Der Beleg spiegelte damals nur den ENDzustand
(`state=DS_WORKING`) - der Lauf sah damit wie ein Verstoss aus, obwohl er am Gate begann.

Geprueft wird die ENTSCHEIDUNG (`hx.state.laufender_lauf`), der Waechter des Werkzeugs
(`wache()`) und der Kopfaufbau (`kopf()`) - `lauf()` selbst wird NIE aufgerufen (das waere
die volle Reihe, genau das, was diese Tests verhindern helfen).
"""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import state as st                                          # noqa: E402
from hx.config import load_config                                   # noqa: E402
from hx.util import ensure_dir, write_text_atomic                    # noqa: E402

LAUFER = ROOT.parent / "docs" / "_r13av_lauf.py"
DOCS = ROOT.parent / "docs" / "bedienung.md"


def _runner():
    """`docs/_r13av_lauf.py` als Modul laden (ohne `main()` - `__name__` bleibt anders)."""
    spec = importlib.util.spec_from_file_location("r13av_lauf", LAUFER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_json(pfad: Path, **felder) -> Path:
    daten = {"state": "IDLE", "batch": 292, "worker": None}
    daten.update(felder)
    write_text_atomic(pfad, json.dumps(daten) + "\n")
    return pfad


class TestLaufenderLauf(unittest.TestCase):
    """Die eine Entscheidung: laeuft gerade ein Worker oder ein Review?"""

    def setUp(self):
        self.tmp = Path(__file__).resolve().parent / "_tmp_r13bw18"
        ensure_dir(self.tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_gate_approval_ohne_worker_ist_frei(self):
        p = _run_json(self.tmp / "run.json", state="GATE_APPROVAL", worker=None)
        self.assertEqual(st.laufender_lauf(p), "")

    def test_worker_vermerk_sperrt_auch_in_anderen_zustaenden(self):
        """Der Worker laeuft weiter, auch wenn das Zustandswort etwas anderes sagt."""
        p = _run_json(self.tmp / "run.json", state="REVIEW_DUE",
                      worker={"pid": 1, "started_at": "2026-10-07T20:32:18+00:00"})
        text = st.laufender_lauf(p)
        self.assertIn("Worker laeuft seit 2026-10-07T20:32:18+00:00", text)

    def test_ds_working_und_claude_reviewing_sperren(self):
        for wort in (st.DS_WORKING, st.CLAUDE_REVIEWING):
            with self.subTest(state=wort):
                p = _run_json(self.tmp / "run.json", state=wort, worker=None)
                self.assertIn(f"Zustand {wort}", st.laufender_lauf(p))

    def test_pause_und_idle_ohne_worker_sind_frei(self):
        for wort in (st.IDLE, st.PAUSED, st.STOPPED, st.GATE_APPROVAL):
            with self.subTest(state=wort):
                p = _run_json(self.tmp / "run.json", state=wort, worker=None)
                self.assertEqual(st.laufender_lauf(p), "", wort)

    def test_beide_gruende_werden_genannt(self):
        p = _run_json(self.tmp / "run.json", state="DS_WORKING",
                      worker={"started_at": "2026-10-07T20:32:18+00:00"})
        text = st.laufender_lauf(p)
        self.assertIn("Worker laeuft seit", text)
        self.assertIn("Zustand DS_WORKING (Batch 292)", text)

    def test_fehlende_oder_kaputte_datei_behauptet_nichts(self):
        self.assertEqual(st.laufender_lauf(None), "")
        self.assertEqual(st.laufender_lauf(self.tmp / "gibtsnicht.json"), "")
        write_text_atomic(self.tmp / "kaputt.json", "{kein json")
        self.assertEqual(st.laufender_lauf(self.tmp / "kaputt.json"), "")

    def test_laufende_zustaende_sind_die_zwei_workenden(self):
        self.assertEqual(st.LAUFENDE_ZUSTAENDE, (st.DS_WORKING, st.CLAUDE_REVIEWING))


class TestWaechter(unittest.TestCase):
    """Der Waechter des Gate-Werkzeugs - er darf `lauf()` nie erreichen."""

    def setUp(self):
        self.runner = _runner()
        self.tmp = Path(__file__).resolve().parent / "_tmp_r13bw18_wache"
        ensure_dir(self.tmp / "state")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.tmp)
        self.cfg = cfg

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _mit_zustand(self, **felder):
        _run_json(self.tmp / "state" / "run.json", **felder)
        return mock.patch("hx.config.load_config", return_value=self.cfg)

    def test_freies_gate_laesst_durch(self):
        with self._mit_zustand(state="GATE_APPROVAL", worker=None):
            self.assertEqual(self.runner.wache(), (0, ""))
            self.assertEqual(self.runner.zustand_text(),
                             "state=GATE_APPROVAL batch=292 worker=False")

    def test_laufender_batch_wird_abgelehnt(self):
        with self._mit_zustand(state="CLAUDE_REVIEWING", worker=None):
            rc, meldung = self.runner.wache()
        self.assertEqual(rc, 2)
        self.assertIn("ABGELEHNT", meldung)
        self.assertIn("Zustand CLAUDE_REVIEWING", meldung)
        self.assertIn("--trotzdem", meldung)
        self.assertIn("betroffenen Testdateien", meldung)

    def test_trotzdem_uebersteuert_mit_warnung(self):
        with self._mit_zustand(state="DS_WORKING",
                               worker={"started_at": "2026-10-07T20:32:18+00:00"}), \
                mock.patch.object(sys, "argv", ["_r13av_lauf.py", "schreiben", "--trotzdem"]):
            rc, meldung = self.runner.wache()
        self.assertEqual(rc, 0)
        self.assertIn("WARNUNG", meldung)
        self.assertIn("DS_WORKING", meldung)

    def test_kopf_nennt_start_und_ende(self):
        with self._mit_zustand(state="GATE_APPROVAL", worker=None):
            zeilen = self.runner.kopf("state=GATE_APPROVAL batch=292 worker=False")
        text = "\n".join(zeilen)
        self.assertIn("Harness-Zustand beim Start: state=GATE_APPROVAL batch=292 worker=False",
                      text)
        self.assertIn("Harness-Zustand am Ende:  state=GATE_APPROVAL batch=292 worker=False",
                      text)

    def test_kopf_ohne_startwert_sagt_das(self):
        with self._mit_zustand(state="IDLE"):
            text = "\n".join(self.runner.kopf())
        self.assertIn("Harness-Zustand beim Start: nicht gelesen", text)

    def test_aufrufhinweis_steht_in_der_dokumentation(self):
        """`--trotzdem` ist ein bewusster Schalter - er muss dokumentiert sein."""
        quelle = LAUFER.read_text(encoding="utf-8")
        self.assertIn("--trotzdem", quelle)
        self.assertIn("laufender_lauf", quelle)


class TestDoku(unittest.TestCase):
    def test_regel_steht_bei_der_gate_anleitung(self):
        if not DOCS.is_file():
            self.skipTest(f"Bedienung nicht vorhanden ({DOCS})")
        text = DOCS.read_text(encoding="utf-8")
        self.assertIn("### 12z. Volle Reihe fahren", text)
        self.assertIn("§12z", text)
        for wort in ("ABGELEHNT", "--trotzdem", "Harness-Zustand beim Start",
                     "Harness-Zustand am Ende"):
            self.assertIn(wort, text)


if __name__ == "__main__":
    unittest.main()
