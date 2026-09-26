"""Tests fuer R13l: harte Zeitgrenze fuer Telegram-Aufrufe (2026-09-27).

FALL AUS DER PRAXIS (gemessen): Der Harness stand ueber 17 Minuten, der Hauptthread
im Stack `urlopen -> ssl.read`. Das gesetzte Socket-Zeitlimit (15 s) hat den Aufruf
NICHT befreit - der Prozess blieb bei eingefrorener CPU stehen, `/stop` wirkte nicht
mehr, weil auch der Takt-Thread im Netz hing.

Deshalb gilt jetzt: Jeder Telegram-Aufruf laeuft in einem eigenen Faedchen und der
Aufrufer wartet hoechstens `grenze` Sekunden. Geprueft wird:

* ein nie antwortender `urlopen` kostet den Aufrufer nur die Grenze (nicht mehr),
* der Fehler kommt als `TelegramError` (Aufrufer behandelt ihn wie bisher),
* ein zweiter haengender Aufruf staut sich nicht auf, sondern wird sofort abgelehnt,
* ein Fehler im Faedchen kommt als `TelegramError` beim Aufrufer an,
* eine erfolgreiche Antwort kommt unveraendert zurueck,
* die Grenzen bleiben in einem sinnvollen Verhaeltnis zum Socket-Zeitlimit.
"""

from __future__ import annotations

import json
import sys
import threading
import time
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import telegram                                             # noqa: E402


class _Antwort:
    """Minimaler Ersatz fuer die urlopen-Rueckgabe (Kontextmanager + `read`)."""

    def __init__(self, nutzlast: bytes):
        self._nutzlast = nutzlast

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return self._nutzlast


class _Basis(unittest.TestCase):
    def setUp(self):
        # Offene Haenger aus einem vorigen Test wuerden das Kontingent sperren.
        with telegram._HAENGER_LOCK:
            telegram._HAENGER.clear()

    def tearDown(self):
        with telegram._HAENGER_LOCK:
            telegram._HAENGER.clear()


class TestHarteGrenze(_Basis):
    def test_haengender_aufruf_gibt_nach_der_grenze_auf(self):
        """`urlopen` antwortet nie: der Aufrufer kommt trotzdem nach ~`grenze` zurueck."""
        frei = threading.Event()

        def haengt(*a, **k):
            frei.wait(30)
            raise AssertionError("sollte nie zurueckkommen")

        tg = telegram.Telegram("t", ["1"])
        with mock.patch.object(urllib.request, "urlopen", haengt):
            t0 = time.monotonic()
            with self.assertRaises(telegram.TelegramError) as ctx:
                tg.call("getMe", {}, timeout=5, grenze=0.4)
            gedauert = time.monotonic() - t0
        frei.set()
        self.assertLess(gedauert, 5, "die harte Grenze hat nicht gegriffen")
        self.assertIn("Zeitgrenze", str(ctx.exception))
        self.assertEqual(telegram.haengende_aufrufe(), 1)

    def test_zweiter_haengender_aufruf_wird_abgelehnt(self):
        """Kein Aufstau: ab `MAX_HAENGER` offenen Aufrufen wird sofort abgelehnt."""
        frei = threading.Event()

        def haengt(*a, **k):
            frei.wait(30)
            raise AssertionError("sollte nie zurueckkommen")

        tg = telegram.Telegram("t", ["1"])
        with mock.patch.object(urllib.request, "urlopen", haengt):
            for _ in range(telegram.MAX_HAENGER):
                with self.assertRaises(telegram.TelegramError):
                    tg.call("getMe", {}, timeout=5, grenze=0.2)
            t0 = time.monotonic()
            with self.assertRaises(telegram.TelegramError) as ctx:
                tg.call("getMe", {}, timeout=5, grenze=0.2)
            gedauert = time.monotonic() - t0
        frei.set()
        self.assertLess(gedauert, 0.2, "die Ablehnung hat selbst gewartet")
        self.assertIn("Netz haengt", str(ctx.exception))

    def test_fehler_im_faden_wird_telegramerror(self):
        def kaputt(*a, **k):
            raise OSError("kein Netz")

        tg = telegram.Telegram("t", ["1"])
        with mock.patch.object(urllib.request, "urlopen", kaputt):
            with self.assertRaises(telegram.TelegramError) as ctx:
                tg.call("getMe", {}, timeout=5, grenze=2)
        self.assertIn("kein Netz", str(ctx.exception))
        self.assertEqual(telegram.haengende_aufrufe(), 0)

    def test_erfolgreiche_antwort_kommt_unveraendert(self):
        nutzlast = json.dumps({"ok": True, "result": {"id": 7}}).encode()
        tg = telegram.Telegram("t", ["1"])
        with mock.patch.object(urllib.request, "urlopen", lambda *a, **k: _Antwort(nutzlast)):
            res = tg.call("getMe", {}, timeout=5, grenze=2)
        self.assertEqual(res, {"ok": True, "result": {"id": 7}})

    def test_socket_zeitlimit_wird_durchgereicht(self):
        """Das Socket-Zeitlimit bleibt gesetzt (Best-Effort), die Grenze liegt darueber."""
        gesehen: list[float] = []

        def merkt(url, data=None, timeout=None):
            gesehen.append(timeout)
            return _Antwort(b'{"ok": true, "result": []}')

        tg = telegram.Telegram("t", ["1"])
        with mock.patch.object(urllib.request, "urlopen", merkt):
            tg.get_updates(0, timeout=0)
            tg.get_updates(0, timeout=None)
        self.assertEqual(gesehen, [8.0, tg.poll_timeout + 15])

    def test_haengende_aufrufe_zaehlen_sich_selbst_ab(self):
        """Ein HAENGENDER Faden bleibt gezaehlt, ein beendeter faellt heraus."""
        laeuft = threading.Event()

        def mal_so_mal_so(*a, **k):
            laeuft.wait(30)
            return _Antwort(b'{"ok": true, "result": {}}')

        tg = telegram.Telegram("t", ["1"])
        with mock.patch.object(urllib.request, "urlopen", mal_so_mal_so):
            with self.assertRaises(telegram.TelegramError):
                tg.call("getMe", {}, timeout=5, grenze=0.2)
            self.assertEqual(telegram.haengende_aufrufe(), 1)
            laeuft.set()
            for _ in range(100):                     # Faden darf noch kurz laufen
                if telegram.haengende_aufrufe() == 0:
                    break
                time.sleep(0.01)
            self.assertEqual(telegram.haengende_aufrufe(), 0)


if __name__ == "__main__":
    unittest.main()
