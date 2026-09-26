"""Tests fuer R13k: kein Netz im Mitschnitt-Leser (2026-09-27).

FALL AUS DER PRAXIS: Der Worker war seit 17 Minuten fertig (letztes Ereignis `result`),
sein Prozess weg - aber der Harness kam nicht weiter. Ein **Stack-Dump** (py-spy) zeigte
den Hauptthread in:

    run_stream -> on_event -> takt_jetzt -> poll -> get_updates -> urlopen -> ssl.read

Der Mitschnitt-Leser machte also eine **blockierende Telegram-Abfrage**. Solange die
haengt, kann der Leser weder das Ausgabe-Ende noch die Gnade aus R13j pruefen - der
Batch kommt nie zum Ende, und selbst `/stop` wirkt nicht (der Abbruch wird im Leser
geprueft).

Geprueft wird deshalb:
* `on_event` ruft **keinen** Netz-Takt mehr auf (AST-Pruefung, nicht Textsuche),
* die Takt-/Auswertungslogik im Leser ist weiterhin da (Summen/Kosten im Takt),
* Telegram-Abfragen sind knapp begrenzt (kurze Abfrage <= 8 s, Langpoll bounded).
"""

from __future__ import annotations

import ast
import inspect
import sys
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import telegram, worker                                       # noqa: E402


def _on_event_knoten() -> ast.FunctionDef:
    """Der AST-Knoten der Funktion `on_event` innerhalb von `worker.run_batch`."""
    baum = ast.parse(inspect.getsource(worker.run_batch).strip())
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.FunctionDef) and knoten.name == "on_event":
            return knoten
    raise AssertionError("on_event in run_batch nicht gefunden")


def _aufgerufene_namen(knoten: ast.AST) -> set[str]:
    """Alle FUNKTIONSNamen, die in diesem Knoten aufgerufen werden (ohne Kommentare)."""
    namen: set[str] = set()
    for k in ast.walk(knoten):
        if not isinstance(k, ast.Call):
            continue
        f = k.func
        if isinstance(f, ast.Name):
            namen.add(f.id)
        elif isinstance(f, ast.Attribute):
            namen.add(f.attr)
    return namen


class TestKeinNetzImLeser(unittest.TestCase):
    def test_on_event_ruft_keinen_netz_takt(self):
        namen = _aufgerufene_namen(_on_event_knoten())
        self.assertNotIn("takt_jetzt", namen,
                         "on_event darf den Telegram-Takt NICHT aufrufen (R13k)")
        self.assertNotIn("poll", namen)
        self.assertNotIn("say", namen)

    def test_takt_logik_bleibt_erhalten(self):
        namen = _aufgerufene_namen(_on_event_knoten())
        self.assertIn("faellig", namen, "Kostenzaehlung im Takt muss bleiben")
        self.assertIn("cost_usd", namen)

    def test_taktgeber_ist_noch_da(self):
        """Der Takt-Thread (R13h) ist jetzt der EINZIGE, der tickt."""
        quelle = inspect.getsource(worker.run_batch)
        self.assertIn("TaktThread", quelle)
        self.assertIn("takt_jetzt", quelle)


class TestTelegramZeitlimits(unittest.TestCase):
    def _tg(self) -> telegram.Telegram:
        return telegram.Telegram("token", ["1"], poll_timeout=25)

    def test_kurze_abfrage_ist_knapp_begrenzt(self):
        tg = self._tg()
        gesehen: dict = {}

        def fake_call(method, params=None, timeout=40.0, grenze=None):
            gesehen["timeout"] = timeout
            gesehen["grenze"] = grenze
            gesehen["poll"] = (params or {}).get("timeout")
            return {"result": []}

        tg.call = fake_call                     # type: ignore[assignment]
        tg.get_updates(offset=0, timeout=0)
        self.assertEqual(gesehen["poll"], 0)
        self.assertLessEqual(gesehen["timeout"], 8.0)
        self.assertLessEqual(gesehen["grenze"], 8.0, "kurze Abfrage: harte Grenze knapp")

    def test_langpoll_bleibt_bounded(self):
        tg = self._tg()
        gesehen: dict = {}

        def fake_call(method, params=None, timeout=40.0, grenze=None):
            gesehen["timeout"] = timeout
            gesehen["grenze"] = grenze
            return {"result": []}

        tg.call = fake_call                     # type: ignore[assignment]
        tg.get_updates(offset=1)
        self.assertLessEqual(gesehen["timeout"], 45.0)
        self.assertGreaterEqual(gesehen["timeout"], 25.0)
        self.assertLessEqual(gesehen["grenze"], 50.0, "auch der Langpoll ist endlich")

    def test_senden_ist_knapp_begrenzt(self):
        tg = self._tg()
        gesehen: dict = {}

        def fake_call(method, params=None, timeout=40.0, grenze=None):
            gesehen["timeout"] = timeout
            gesehen["grenze"] = grenze
            return {"ok": True, "result": {"message_id": 1}}

        tg.call = fake_call                     # type: ignore[assignment]
        tg.send("hallo")
        self.assertEqual(gesehen["timeout"], 15)
        self.assertLessEqual(gesehen["grenze"], 20.0)

    def test_haengender_aufruf_wirft_telegramerror(self):
        """Ein Zeitlimit muss als TelegramError ankommen (urllib-Timeouts ebenso)."""
        tg = self._tg()
        with mock.patch.object(urllib.request, "urlopen",
                               side_effect=TimeoutError("Zeitlimit")):
            with self.assertRaises(telegram.TelegramError):
                tg.call("getMe")
            with self.assertRaises(telegram.TelegramError):
                tg.get_updates(offset=0, timeout=0)


if __name__ == "__main__":
    unittest.main()
