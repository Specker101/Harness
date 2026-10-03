"""Tests fuer R13bq (2026-10-03, Nutzerauftrag "Konsolenfenster zeigt nichts").

Beobachtung: das Harness-Fenster blieb zeitweise stehen und lief spaeter weiter; in B257
war `runs/b257/stream-forts1.jsonl` nach dem Start der Fortsetzung 20:21 rund 45 min lang
0 Bytes.

Befund (gemessen, s. `docs/_r13bq_belege.md`):
  * Der Harness druckt jede Log-Zeile mit `print(..., flush=True)` (`hx/util.py` `Log._emit`).
    Steht das Konsolenfenster im Markiermodus (QuickEdit), BLOCKIERT der Schreibvorgang den
    druckenden Thread - waehrend eines Batches ist das der Takt-Thread (Telegram-Warnungen)
    oder der Haupt-Thread. Der Worker schreibt dagegen in eine DATEI (`hx/proc.py`) und
    laeuft weiter: das Fenster steht, der Batch laeuft.
  * Punkt 1 dieses Auftrags: QuickEdit beim Start abschalten (`util.konsole_quickedit_aus`,
    aufgerufen in `cli.cmd_run`).
  * Punkt 2: Warnung, wenn laenger als `[limits] stille_warn_min` (Vorgabe 20) keine Zeile
    im Mitschnitt ankommt (`proc.run_stream` -> `util.stille_warnung`).

Alles im Attrappenbetrieb: kein Netz, keine API-Kosten, kein Ghidra.
"""

from __future__ import annotations

import ctypes
import inspect
import json
import os
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import cli, proc, streamjson, util, worker               # noqa: E402
from hx.config import load_config                                # noqa: E402
from hx.util import Log, ensure_dir                              # noqa: E402


class TestQuickEdit(unittest.TestCase):
    """Punkt 1 - QuickEdit abschalten (Bit-Rechnung, Aufruf, echtes Fenster)."""

    def test_das_bit_ist_danach_weg(self):
        self.assertEqual(util.ENABLE_QUICK_EDIT, 0x0040)
        ohne = util.ohne_quickedit_modus(0x0007 | util.ENABLE_QUICK_EDIT)
        self.assertEqual(ohne & util.ENABLE_QUICK_EDIT, 0)
        # ENABLE_EXTENDED_FLAGS muss mitgesetzt werden (Windows verlangt das, sonst
        # wird der Rest des Modus ignoriert).
        self.assertTrue(ohne & util.ENABLE_EXTENDED_FLAGS)

    def test_alle_anderen_bits_bleiben(self):
        voll = 0x0007                                     # typischer Eingabemodus (ohne 0x80)
        ohne = util.ohne_quickedit_modus(voll)
        self.assertEqual(ohne, 0x0087)
        # Alles ausser QuickEdit und dem zugesetzten ENABLE_EXTENDED_FLAGS bleibt stehen.
        self.assertEqual(ohne & ~util.ENABLE_EXTENDED_FLAGS, voll & ~util.ENABLE_QUICK_EDIT)
        # idempotent - zweimal abschalten aendert nichts mehr
        self.assertEqual(util.ohne_quickedit_modus(ohne), ohne)
        self.assertEqual(util.ohne_quickedit_modus(0x0003), 0x0083)

    def test_abschalten_wirft_nie_und_antwortet_bool(self):
        self.assertIsInstance(util.konsole_quickedit_aus(), bool)

    def test_der_start_schaltet_ab(self):
        """Der Dauerbetrieb (`hx.cli run`) muss die Abschaltung aufrufen."""
        quelle = inspect.getsource(cli.cmd_run)
        self.assertIn("konsole_quickedit_aus", quelle)

    def test_im_echten_fenster_ist_das_bit_danach_weg(self):
        """Am echten Konsolenhandle nachgemessen (im VS-Code-Terminal ggf. uebersprungen)."""
        if os.name != "nt":
            self.skipTest("nur Windows")
        k = ctypes.windll.kernel32
        handle = k.GetStdHandle(util.STD_INPUT_HANDLE)
        vorher = ctypes.c_uint32()
        if not k.GetConsoleMode(handle, ctypes.byref(vorher)):
            self.skipTest("kein Konsolenhandle (umgeleitete Ausgabe)")
        util.konsole_quickedit_aus()
        nachher = ctypes.c_uint32()
        self.assertTrue(k.GetConsoleMode(handle, ctypes.byref(nachher)))
        self.assertEqual(nachher.value & util.ENABLE_QUICK_EDIT, 0)
        # und der Aufruf meldet Erfolg, wenn es ein Handle gibt
        self.assertTrue(util.konsole_quickedit_aus())


class TestStilleWarnung(unittest.TestCase):
    """Punkt 2 - Warnung, wenn laenger keine Zeile im Mitschnitt ankommt."""

    def test_unter_der_schwelle_keine_meldung(self):
        self.assertEqual(util.stille_warnung(0, 1200, 0), (0, ""))
        self.assertEqual(util.stille_warnung(1199.9, 1200, 0), (0, ""))

    def test_erste_meldung_bei_voller_schwelle(self):
        stufe, text = util.stille_warnung(1200, 1200, 0)
        self.assertEqual(stufe, 1)
        self.assertIn("kein Mitschnitt-Zeichen seit 20 min", text)
        self.assertIn("1. Meldung", text)

    def test_jede_volle_schwelle_eine_meldung(self):
        # 30 min bei 20-min-Schwelle: Stufe 1 ist schon gemeldet -> nichts.
        self.assertEqual(util.stille_warnung(1800, 1200, 1), (1, ""))
        stufe, text = util.stille_warnung(3600, 1200, 1)
        self.assertEqual(stufe, 3)
        self.assertIn("seit 60 min", text)
        self.assertIn("3. Meldung", text)

    def test_abgeschaltet_und_kaputte_werte(self):
        self.assertEqual(util.stille_warnung(9999, 0, 0), (0, ""))
        self.assertEqual(util.stille_warnung(9999, None, 2), (0, ""))
        self.assertEqual(util.stille_warnung(-5, 1200, 0), (0, ""))

    def test_der_worker_reicht_die_schwelle_durch(self):
        quelle = inspect.getsource(worker.run_batch)
        self.assertIn("stille_warn_s=stille_warn_s", quelle)
        self.assertIn("stille_info=stats.letzter_aufruf", quelle)

    def test_schwelle_steht_in_der_konfiguration(self):
        cfg = load_config()
        self.assertEqual(float(cfg.get("limits", "stille_warn_min", 20)), 20)

    def test_letzter_aufruf_nennt_das_werkzeug(self):
        st = streamjson.StreamStats()
        self.assertEqual(st.letzter_aufruf(), "")
        st.feed(json.dumps({"type": "assistant", "message": {
            "id": "m1", "model": "deepseek-flash[1m]",
            "content": [{"type": "tool_use", "id": "t1", "name": "PowerShell",
                         "input": {"command": "python -u scripts/preflight.py before"}}]}}))
        self.assertIn("PowerShell", st.letzter_aufruf())
        self.assertIn("preflight.py", st.letzter_aufruf())

    def test_der_echte_lauf_meldet_die_stille(self):
        """Echter Kindprozess, der schweigt - mit kleiner Schwelle, kein langes Warten.

        Gemessen wird der ganze Weg: `proc.run_stream` zaehlt die Stille, schreibt die
        WARN-Zeile ins Protokoll (Konsole) und ruft `stille_info` fuer den Zusatz.
        """
        tmp = ensure_dir(Path(ROOT) / "tests" / "_tmp_r13bq")
        try:
            log = Log(tmp / "log.jsonl", echo=False)
            kind = [sys.executable, "-u", "-c",
                    "import time; time.sleep(1.0); print('fertig', flush=True)"]
            res = proc.run_stream(kind, os.environ, str(ROOT), tmp / "s.jsonl",
                                  log=log, stille_warn_s=0.3,
                                  stille_info=lambda: "PowerShell: test.py")
            self.assertGreaterEqual(res.stille_warnungen, 2)
            self.assertGreaterEqual(res.stille_max_s, 0.5)
            zeilen = (tmp / "log.jsonl").read_text(encoding="utf-8")
            self.assertIn("Mitschnitt still", zeilen)
            self.assertIn("PowerShell: test.py", zeilen)
            # Die Ausgabe des Kindes kommt trotzdem vollstaendig an.
            self.assertIn("fertig", (tmp / "s.jsonl").read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_ohne_schwelle_keine_meldung(self):
        tmp = ensure_dir(Path(ROOT) / "tests" / "_tmp_r13bq")
        try:
            log = Log(tmp / "log.jsonl", echo=False)
            kind = [sys.executable, "-u", "-c",
                    "import time; time.sleep(0.8); print('x', flush=True)"]
            res = proc.run_stream(kind, os.environ, str(ROOT), tmp / "s2.jsonl",
                                  log=log, stille_warn_s=None)
            self.assertEqual(res.stille_warnungen, 0)
            self.assertEqual(res.stille_max_s, 0.0)
            # Ohne Schwelle gibt es NICHTS zu melden - das Protokoll bleibt (leer).
            p = tmp / "log.jsonl"
            self.assertFalse(p.is_file() and "Mitschnitt still" in p.read_text("utf-8"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
