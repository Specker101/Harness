"""Tests fuer D (R13d): atomares Schreiben darf an einem LESER nicht sterben.

Hintergrund (gemessen 2026-09-26): der Harness brach zweimal mit

    PermissionError: [WinError 5] Zugriff verweigert: '...run.json.tmp' -> '...run.json'

ab - einmal in `phase("review", ...)`, einmal in `do_review` ->
`state.set(CLAUDE_REVIEWING)`. Beide Male war `hx.cli watch` (liest `run.json`
alle 1,5 s, oeffnet und schliesst sie) der zweite Prozess.

GEMESSEN am 2026-09-26 (C:\\Temp und G:, gleiches Ergebnis): solange ein anderer
Prozess die Zieldatei offen haelt, scheitert `os.replace` mit WinError 5 - auch
dann, wenn der Leser FILE_SHARE_DELETE vergibt (dann geht `DeleteFile`, aber kein
Rename-Ersetzen). Die Abhilfe ist deshalb die Nachsicht beim Schreiben
(`replace_with_retry`), nicht der Leser. `open_shared_read` hilft beim *Loeschen*
(Kontrollkanal, Rotation) - der Test unten haelt das ausdruecklich fest.

Alles im Attrappenbetrieb: keine Kosten, kein Netz, kein Ghidra.
"""

from __future__ import annotations

import os
import shutil
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import state as hxstate                                   # noqa: E402
from hx import util                                               # noqa: E402
from hx.util import (ensure_dir, open_shared_read, read_json,     # noqa: E402
                     read_text, replace_with_retry, write_text_atomic)


def _teilungsfehler(quelle) -> PermissionError:
    """Genau die Ausnahme aus dem Absturzbericht: WinError 5."""
    return PermissionError(13, "Zugriff verweigert", str(quelle), 5)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__file__).resolve().parent / "_tmp_r13d"
        shutil.rmtree(self.tmp, ignore_errors=True)
        ensure_dir(self.tmp)

    # ------------------------------------------------------------- Testhelfer
    def kurzlebiger_leser(self, p: Path, dauer_s: float = 0.2) -> threading.Thread:
        """Ein Leser wie `hx.cli watch`: normale Freigaben, haelt kurz, schliesst.

        Absichtlich `open()` und nicht `open_shared_read` - der Absturz kam von
        genau dieser Sorte Leser (kein FILE_SHARE_DELETE).
        """
        offen = threading.Event()

        def lesen():
            with open(p, "r", encoding="utf-8") as fh:
                fh.read()
                offen.set()
                time.sleep(dauer_s)

        t = threading.Thread(target=lesen, daemon=True)
        t.start()
        self.assertTrue(offen.wait(3.0), "der Leser wurde nicht geoeffnet")
        return t


class TestTeilungsfehler(Base):
    def test_kurzlebiger_leser_blockiert_nicht(self):
        """Der Absturzfall: Leser offen, Harness schreibt - es muss durchgehen."""
        p = self.tmp / "run.json"
        write_text_atomic(p, '{"gen": 1}\n')
        t = self.kurzlebiger_leser(p)
        write_text_atomic(p, '{"gen": 2}\n')          # starb hier zweimal
        t.join(3.0)
        self.assertEqual(read_json(p)["gen"], 2)
        self.assertFalse((self.tmp / "run.json.tmp").exists())

    def test_state_set_bei_kurzlebigem_leser(self):
        """Dieselbe Stelle wie im Bericht: `state.set` -> `save` -> `os.replace`."""
        sp = self.tmp / "state" / "run.json"
        zustand = hxstate.State(sp)
        zustand.data["batch"] = 170
        zustand.save()
        t = self.kurzlebiger_leser(sp)
        zustand.set(hxstate.CLAUDE_REVIEWING, "Review laeuft")
        t.join(3.0)
        self.assertEqual(hxstate.State(sp).state, hxstate.CLAUDE_REVIEWING)
        self.assertEqual(hxstate.State(sp).batch, 170)

    def test_ersetzung_wartet_auf_den_leser(self):
        """Steht die Sperre nur kurz, wird nachgesetzt statt abgebrochen."""
        p = self.tmp / "z.json"
        echt = os.replace
        zaehler = {"n": 0}

        def kaputt(quelle, ziel):
            zaehler["n"] += 1
            if zaehler["n"] <= 2:
                raise _teilungsfehler(quelle)
            return echt(quelle, ziel)

        with mock.patch.object(util.os, "replace", kaputt):
            write_text_atomic(p, "inhalt\n")
        self.assertEqual(zaehler["n"], 3)
        self.assertEqual(read_text(p), "inhalt\n")
        self.assertFalse((self.tmp / "z.json.tmp").exists())

    def test_echter_fehler_wird_nicht_wiederholt(self):
        """Kein Teilungsproblem -> sofort weitergeben (keine Nachsicht)."""
        p = self.tmp / "y.json"
        zaehler = {"n": 0}

        def kaputt(quelle, ziel):
            zaehler["n"] += 1
            raise FileNotFoundError(2, "nicht da", str(quelle))

        with mock.patch.object(util.os, "replace", kaputt):
            with self.assertRaises(FileNotFoundError):
                write_text_atomic(p, "x\n")
        self.assertEqual(zaehler["n"], 1)

    def test_nach_erschoepfter_nachsicht_bleibt_der_fehler_sichtbar(self):
        """Kein stilles Schreiben in die Zieldatei: der Fehler kommt weiterhin."""
        p = self.tmp / "w.json"
        zaehler = {"n": 0}

        def kaputt(quelle, ziel):
            zaehler["n"] += 1
            raise _teilungsfehler(quelle)

        with mock.patch.object(util.os, "replace", kaputt):
            with self.assertRaises(PermissionError):
                replace_with_retry(p, p, versuche=4, pause_s=0.001)
        self.assertEqual(zaehler["n"], 4)

    @unittest.skipUnless(os.name == "nt", "Windows-Teilesemantik")
    def test_dauerhafter_leser_bleibt_ein_klarer_fehler(self):
        """Ehrlich gemessen: ein *dauerhaft* offener Leser ist nicht ueberwindbar."""
        p = self.tmp / "v.json"
        write_text_atomic(p, '{"gen": 1}\n')
        tmp = self.tmp / "v.json.tmp"
        tmp.write_text('{"gen": 2}\n', encoding="utf-8")
        offen, freigabe = threading.Event(), threading.Event()

        def lesen():
            with open(p, "r", encoding="utf-8") as fh:
                fh.read()
                offen.set()
                freigabe.wait(5.0)

        t = threading.Thread(target=lesen, daemon=True)
        t.start()
        self.assertTrue(offen.wait(3.0))
        try:
            with self.assertRaises(PermissionError) as ctx:
                replace_with_retry(tmp, p, versuche=3, pause_s=0.001)
            self.assertIn(int(getattr(ctx.exception, "winerror", 0)), (5, 32))
        finally:
            freigabe.set()
            t.join(3.0)
        self.assertEqual(read_json(p)["gen"], 1)          # nie halb geschrieben


class TestLesen(Base):
    @unittest.skipUnless(os.name == "nt", "FILE_SHARE_DELETE ist Windows-Sache")
    def test_leser_gibt_delete_frei(self):
        """Kontrollkanal/Rotation: Loeschen muss gehen, waehrend wir lesen."""
        p = self.tmp / "log.txt"
        p.write_text("zeile\n", encoding="utf-8")
        with open_shared_read(p) as fh:
            self.assertEqual(fh.read(), "zeile\n")
            os.remove(p)
        self.assertFalse(p.exists())

    def test_leser_liest_wie_bisher(self):
        p = self.tmp / "daten.json"
        p.write_text('{"batch": 170}\n', encoding="utf-8")
        with open_shared_read(p) as fh:
            self.assertEqual(fh.read(), '{"batch": 170}\n')
        self.assertEqual(read_json(p), {"batch": 170})

    def test_read_json_default_bei_fehlender_datei(self):
        self.assertEqual(read_json(self.tmp / "gibtsnicht.json", {"a": 1}), {"a": 1})

    def test_read_json_tolerant_bei_halber_datei(self):
        p = self.tmp / "halb.json"
        p.write_text('{"a": 1', encoding="utf-8")
        self.assertEqual(read_json(p, "ersatz"), "ersatz")

    def test_read_text_ersetzt_ungueltige_bytes(self):
        p = self.tmp / "roh.txt"
        p.write_bytes(b"gut\xffschlecht")
        self.assertEqual(read_text(p), "gut\ufffdschlecht")

    def test_read_text_umlaut_und_fehltoleranz(self):
        p = self.tmp / "text.txt"
        p.write_text("Laeuft: äöü\n", encoding="utf-8")
        self.assertEqual(read_text(p), "Laeuft: äöü\n")
        self.assertEqual(read_text(self.tmp / "nix.txt", "leer"), "leer")


if __name__ == "__main__":
    unittest.main()
