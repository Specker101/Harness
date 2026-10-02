"""Tests fuer R13bm (02.10.2026): die vier Vorschlaege aus R13bl-4.

Je Punkt ein Abschnitt, je Punkt ein Commit:

  1. **`api_errors` befuellen** - API-/Gateway-Fehler im Mitschnitt erkennen und mit
     Zeitpunkt, gekuerztem Text und **Mitschnittzeile** nach `result.json` tragen.
     Fixture: `tests/fixtures/b235_api_fehler.jsonl` = wortgetreuer Ausschnitt der Zeilen
     28439-28442 aus `runs/b235/stream.jsonl` (die Fehlerzeile ist die vom Nutzer
     genannte `:28441`).
  2. Infrastrukturabbruch als eigene Klasse (`killed_reason = "infra"`), Neustart statt
     Review.
  3. Session-Limit nicht als „verworfen" ablegen; Wiederaufnahme mit 5 min Puffer.
  4. Aussensicht an dieselbe Limit-Uhr.

Alles laeuft in Wegwerf-Verzeichnissen; das Decomp-Repo und der laufende Batch bleiben
unberuehrt.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "b235_api_fehler.jsonl"

from hx import streamjson                                        # noqa: E402
from hx.orchestrator import Orchestrator                          # noqa: E402


def _zeilen() -> list[str]:
    return FIXTURE.read_text(encoding="utf-8").splitlines()


# ================================================== 1) API-Fehler erkennen
class TestApiFehler(unittest.TestCase):
    """Punkt 1: der Fehler aus B235 wird erkannt (echter Mitschnitt-Ausschnitt)."""

    def setUp(self):
        self.stats = streamjson.StreamStats()
        for zeile in _zeilen():
            self.stats.feed(zeile)

    def test_fixture_ist_der_echte_ausschnitt(self):
        self.assertEqual(len(_zeilen()), 4, "vier Zeilen (28439-28442)")
        self.assertIn('"<synthetic>"', _zeilen()[2], "die Fehlerzeile liegt in Zeile 3")

    def test_fehler_wird_erkannt_mit_zeit_text_und_zeile(self):
        self.assertEqual(len(self.stats.api_errors), 1)
        e = self.stats.api_errors[0]
        self.assertEqual(e["zeile"], 3, "dritte Fixture-Zeile = stream.jsonl:28441")
        self.assertTrue(e["ts"].startswith("2026-10-01T"), e["ts"])
        self.assertTrue(e["text"].startswith("API Error:"), e["text"][:60])
        self.assertLessEqual(len(e["text"]), streamjson.API_FEHLER_TEXT)
        self.assertNotIn("\n", e["text"], "der Text wird auf eine Zeile gezogen")

    def test_letzter_text_ist_der_fehler(self):
        """Genau das ist die Bedingung der Klasse „Infrastrukturabbruch" (Punkt 2)."""
        self.assertTrue(self.stats.letzter_text_api_fehler)

    def test_normaler_bericht_ist_kein_fehler(self):
        s = streamjson.StreamStats()
        s.feed(json.dumps({"type": "assistant", "message": {
            "id": "m1", "model": "deepseek-flash[1m]",
            "content": [{"type": "text",
                         "text": "Ergebnis: fertig.\nAPI Error: war ein Gateway-Problem."}]}}))
        self.assertEqual(s.api_errors, [])
        self.assertFalse(s.letzter_text_api_fehler)

    def test_letzter_text_zaehlt_nicht_der_fruehere(self):
        """Ein Fehler in der MITTE (danach lief es weiter) ist kein Infrastrukturabbruch."""
        s = streamjson.StreamStats()
        s.feed(json.dumps({"type": "assistant", "message": {
            "id": "m1", "model": "<synthetic>",
            "content": [{"type": "text", "text": "API Error: Gateway - neuer Versuch"}]}}))
        s.feed(json.dumps({"type": "assistant", "message": {
            "id": "m2", "model": "deepseek-flash[1m]",
            "content": [{"type": "text", "text": "Ergebnis: alles gebaut."}]}}))
        self.assertEqual(len(s.api_errors), 1, "der Fehler bleibt belegt")
        self.assertFalse(s.letzter_text_api_fehler, "aber der LETZTE Text ist normal")

    def test_synthetische_nachricht_zaehlt_auch_ohne_api_error(self):
        """Die CLI erzeugt auch andere Synthetik-Texte (`<synthetic>` ist das Kennzeichen)."""
        s = streamjson.StreamStats()
        s.feed(json.dumps({"type": "assistant", "message": {
            "id": "m1", "model": "<synthetic>",
            "content": [{"type": "text", "text": "Prompt ist zu lang."}]}}))
        self.assertEqual(len(s.api_errors), 1)
        self.assertTrue(s.letzter_text_api_fehler)

    def test_leerer_text_zaehlt_nicht(self):
        s = streamjson.StreamStats()
        s.feed(json.dumps({"type": "assistant", "message": {
            "id": "m1", "model": "<synthetic>",
            "content": [{"type": "text", "text": "   "}]}}))
        self.assertEqual(s.api_errors, [])

    def test_faktenzeile_nennt_den_fehler(self):
        """Der Reviewer sieht die Fehler in `harness-facts.md` (R13bm)."""
        leer = Orchestrator.api_fehler_zeile({})
        self.assertEqual(leer, "keine")
        res = {"stats": {"api_errors": list(self.stats.api_errors)}}
        zeile = Orchestrator.api_fehler_zeile(res)
        self.assertIn("1x", zeile)
        self.assertIn("Mitschnittzeile 3", zeile)
        self.assertIn("API Error:", zeile)


if __name__ == "__main__":
    unittest.main()
