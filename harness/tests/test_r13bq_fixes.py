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
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import cli, util                                          # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
