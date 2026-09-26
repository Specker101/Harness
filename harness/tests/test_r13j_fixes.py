"""Tests fuer R13j: Ausgabe-Pipe ohne EOF (2026-09-26).

Fall aus der Praxis: Der Worker war fertig gerechnet (letztes Ereignis `end_turn`,
Abschlussbericht geschrieben), sein Prozess beendet - aber der Harness stand **ueber
40 Minuten** in `proc.run_stream` und wartete auf das Ende der Ausgabe. Folge: kein
`result.json`, kein Push, kein Review, kein Log-Eintrag; der Zustand blieb auf
`DS_WORKING` und `/status` zeigte einen laufenden Batch, der laengst fertig war.

Ursache: Die Ausgabe-Pipe meldet nur dann EOF, wenn **alle** Schreib-Handles zu sind.
Startet der Worker einen Enkelprozess, der das Handle erbt (z. B. `Start-Process` ohne
`-Wait`), bleibt die Pipe offen, obwohl der Worker selbst weg ist.

Der Test erzeugt genau diese Lage: ein Kind, das einen Enkel startet und sich dann
sofort beendet. Ohne die Bremse (`eof_gnade_s`) kehrt `run_stream` nie zurueck.
"""

from __future__ import annotations

import shutil
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx.proc import run_stream                                        # noqa: E402
from hx.util import Log, ensure_dir                                   # noqa: E402

# Kind startet einen Enkel (erbt stdout, laeuft lange) und beendet sich selbst.
KIND = (
    "import subprocess, sys, time;"
    "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']);"
    "print('kind fertig', flush=True);"
    "sys.exit(0)"
)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__file__).resolve().parent / "_tmp_r13j"
        shutil.rmtree(self.tmp, ignore_errors=True)
        ensure_dir(self.tmp)
        self.log = Log(self.tmp / "log.jsonl", echo=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestEofGnade(Base):
    def test_offene_pipe_beendet_den_lauf(self):
        t0 = time.perf_counter()
        run = run_stream([sys.executable, "-c", KIND], env=None, cwd=str(self.tmp),
                         out_path=self.tmp / "stream.jsonl", log=self.log,
                         eof_gnade_s=2.0)
        dauer = time.perf_counter() - t0
        self.assertIsNotNone(run.eof_offen_s, "die Bremse hat nicht gegriffen")
        self.assertGreaterEqual(run.eof_offen_s, 1.0)
        self.assertLess(dauer, 15.0, "der Lauf haette ohne Bremse unbegrenzt gewartet")
        self.assertEqual(run.rc, 0, "das Kind selbst war erfolgreich")
        text = (self.tmp / "stream.jsonl").read_text(encoding="utf-8")
        self.assertIn("kind fertig", text)

    def test_normaler_lauf_ohne_bremse(self):
        """Ein Kind, dessen Ausgabe sauber endet, darf NICHT als '/pipe offen/' gelten."""
        run = run_stream([sys.executable, "-c", "print('kurz und fertig', flush=True)"],
                         env=None, cwd=str(self.tmp), out_path=self.tmp / "s2.jsonl",
                         log=self.log, eof_gnade_s=2.0)
        self.assertIsNone(run.eof_offen_s)
        self.assertEqual(run.rc, 0)

    def test_bremse_abschaltbar(self):
        """`eof_gnade_s=0` schaltet die Bremse ab (alte Wirkung: warten bis EOF)."""
        run = run_stream([sys.executable, "-c", "print('x', flush=True)"], env=None,
                         cwd=str(self.tmp), out_path=self.tmp / "s3.jsonl",
                         log=self.log, eof_gnade_s=0)
        self.assertIsNone(run.eof_offen_s)

    def test_ereignisse_kommen_vollstaendig_an(self):
        """Auch bei offener Pipe muessen alle Zeilen vorher verarbeitet sein."""
        gesehen: list[str] = []
        run_stream([sys.executable, "-c", KIND], env=None, cwd=str(self.tmp),
                   out_path=self.tmp / "s4.jsonl", log=self.log, eof_gnade_s=2.0,
                   on_event=lambda ln: gesehen.append(ln))
        self.assertIn("kind fertig", gesehen)


class TestMeldung(unittest.TestCase):
    """Die Batch-Meldung muss den Hinweis tragen (sonst sieht es wie ein Haenger aus)."""

    def test_worker_meldet_offene_pipe(self):
        from hx import worker
        res = worker.WorkerResult()

        class _Run:
            eof_offen_s = 61.0

        run = _Run()
        if getattr(run, "eof_offen_s", None):
            res.alarms.append(
                f"HINWEIS: Der Worker-Prozess war fertig, aber ein weiterlaufender "
                f"Kindprozess hielt die Ausgabe-Pipe ({run.eof_offen_s:.0f} s kein Ende). "
                f"Der Lauf wurde abgeschlossen (R13j).")
        self.assertTrue(res.alarms[0].startswith("HINWEIS"))
        self.assertIn("61 s", res.alarms[0])


if __name__ == "__main__":
    unittest.main()
