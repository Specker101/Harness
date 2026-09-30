"""Tests fuer R13bb (2026-09-30): vier Harness-Punkte aus Aussensicht B224 / Review B225.

Punkt 1 (dieser Teil): FORTSETZUNG NACH EINEM FRUEHEN PREFLIGHT WIEDER ERLAUBEN (R13ax
anpassen). Bleibt bis zur Umschaltschwelle mindestens `limits.fortsetzung_min_rest_min`
(Default 20) Minuten, wird trotz gelaufenem Preflight fortgesetzt: der vorhandene Stand
wird vorher archiviert (R13ah), der Anstoss verlangt am Ende einen NEUEN Preflight
("der letzte gilt"). Darunter bleibt es beim UEBERTRAG.
Grund (gemessen): der Preflight dauert jetzt ~5 min, B224 endete bei 45 min mit 3/5 Koepfen.

Wegwerf-Verzeichnisse unter `tests/_tmp_r13bb`; die Konfiguration wird gelesen (der neue
Schluessel steht in `harness.toml`).
"""

from __future__ import annotations

import inspect
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import streamjson, worker                                   # noqa: E402
from hx.config import load_config                                   # noqa: E402

TOML = ROOT / "harness.toml"
AUFTRAG = ("TEIL 1: etwas bauen.\n\n## NACHRUECKLISTE\n1. Posten eins\n2. Posten zwei\n")
TEXT = ("Kein Fortsetzungsanstoss: Preflight bereits gelaufen, offene Nachrueckliste "
        "-> UEBERTRAG")


def _assistant(mid: str, kontext: int, werkzeug: str | None = None) -> str:
    bloecke: list[dict] = []
    if werkzeug:
        bloecke.append({"type": "tool_use", "id": f"tu-{mid}", "name": werkzeug,
                        "input": {"file_path": "x"}})
    return json.dumps({"type": "assistant", "timestamp": "2026-09-30T00:00:00Z",
                       "message": {"id": mid, "model": "m", "content": bloecke,
                                   "usage": {"input_tokens": kontext}}})


def _result(kontext: int) -> str:
    return json.dumps({"type": "result", "subtype": "success", "num_turns": 5,
                       "result": "fertig", "is_error": False,
                       "usage": {"input_tokens": kontext}})


def preflight_aufruf() -> dict:
    """Ein ECHTER Preflight-Start (PowerShell-Aufruf mit `preflight.py`)."""
    return {"zeile": 1, "ts": "2026-09-30T00:00:00Z", "id": "tu-pf",
            "name": "PowerShell",
            "input": {"command": "python -u scripts/preflight.py before *> out.txt",
                      "description": "Preflight"}}


class TestFortsetzungNachFruehemPreflight(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config()

    def _stats(self, kontext: int = 300000, preflight: bool = False):
        s = streamjson.StreamStats()
        s.feed(_assistant("m1", 1000))
        s.feed(_assistant("m2", kontext))
        s.feed(_result(kontext))
        if preflight:
            s.tools.append(preflight_aufruf())
        return s
    @staticmethod
    def _run():
        from hx.proc import StreamRun
        r = StreamRun()
        r.rc = 0
        r.killed_reason = None
        return r

    def umschalt(self) -> float:
        return float(worker.umschalt_minuten(self.cfg)["umschalt_min"])

    def entsch(self, minuten: float, preflight: bool = True, auftrag: str = AUFTRAG):
        return worker.fortsetzung_pruefen(self.cfg, self._run(), self._stats(preflight=preflight),
                                          auftrag, minuten, [])

    def test_schwelle_steht_in_der_konfiguration(self):
        self.assertEqual(float(self.cfg.get("limits", "fortsetzung_min_rest_min", 0)), 20.0)
        self.assertIn("fortsetzung_min_rest_min = 20", TOML.read_text(encoding="utf-8"))

    def test_genug_zeit_wird_angestossen(self):
        u = self.umschalt()
        e = self.entsch(u - 25)
        self.assertTrue(e["ja"], e)
        self.assertTrue(e["preflight_erneut"])
        self.assertFalse(e.get("uebertrag"))
        self.assertGreaterEqual(e["rest_min"], 20)

    def test_unter_20_min_bleibt_uebertrag(self):
        u = self.umschalt()
        e = self.entsch(u - 10)
        self.assertFalse(e["ja"])
        self.assertEqual(e["grund"], TEXT.replace("Kein Fortsetzungsanstoss: ", ""))
        self.assertTrue(e["uebertrag"])
        self.assertLess(e["rest_min"], 20)
        self.assertFalse(e.get("preflight_erneut"))

    def test_genau_20_min_zaehlt_als_genug(self):
        """Die Grenze ist einschliesslich: 20 min Rest = Anstoss."""
        u = self.umschalt()
        e = self.entsch(u - 20)
        self.assertTrue(e["ja"], e)

    def test_schwelle_ist_einstellbar(self):
        """`fortsetzung_min_rest_min` wird gelesen - nicht fest verdrahtet."""
        self.cfg.data["limits"]["fortsetzung_min_rest_min"] = 60
        u = self.umschalt()
        e = self.entsch(u - 25)
        self.assertFalse(e["ja"])
        self.assertTrue(e["uebertrag"])

    def test_ohne_preflight_aendert_sich_nichts(self):
        u = self.umschalt()
        e = self.entsch(u - 25, preflight=False)
        self.assertTrue(e["ja"])
        self.assertFalse(e.get("preflight_erneut"))

    def test_frueher_abbruch_bleibt_abbruch(self):
        """Die Lockerung gilt nur fuer den Preflight-Fall, nicht fuer Abbrueche."""
        u = self.umschalt()
        r = self._run()
        r.killed_reason = "cancel"
        e = worker.fortsetzung_pruefen(self.cfg, r, self._stats(preflight=True),
                                       AUFTRAG, u - 25, [])
        self.assertFalse(e["ja"])
        self.assertIn("cancel", e["grund"])
        self.assertFalse(e.get("uebertrag"))
        self.assertFalse(e.get("preflight_erneut"))

    def test_ohne_nachrueckliste_kein_anstoss(self):
        u = self.umschalt()
        e = self.entsch(u - 25, auftrag="TEIL 1 ohne Liste.")
        self.assertFalse(e["ja"])
        self.assertIn("NACHRUECKLISTE", e["grund"])


class TestAnstossTextUndAblauf(unittest.TestCase):
    """Der Anstoss sagt den neuen Preflight an, und der alte Stand wird vorher archiviert."""

    def test_text_nennt_den_neuen_preflight(self):
        text = worker.fortsetzungs_text(50.0, 300000, 90.0, self._u(), batch=224,
                                        preflight_erneut=True)
        self.assertIn("Nach der Nacharbeit neuer Preflight, der letzte gilt", text)
        self.assertIn("überholt", text)
        self.assertIn("Batch 224", text)

    @staticmethod
    def _u() -> float:
        return float(load_config().get("limits", "alarm_wall_s", 5400)) / 60.0 - 15.0

    def test_ohne_preflight_kein_zusatz(self):
        text = worker.fortsetzungs_text(50.0, 300000, 90.0, self._u(), batch=224)
        self.assertNotIn("neuer Preflight", text)
        self.assertNotIn("überholt", text)

    def test_archiv_laeuft_vor_dem_anstoss(self):
        """R13ah-Code bleibt die Stelle, die den Stand vor der Fortsetzung sichert."""
        quelle = inspect.getsource(worker.run_batch)
        self.assertIn("archiviere_preflight_vor_fortsetzung(", quelle)
        self.assertLess(quelle.index("archiviere_preflight_vor_fortsetzung("),
                        quelle.index("fortsetz_text = fortsetzungs_text("))

    def test_der_anstoss_wird_als_preflight_erneut_vermerkt(self):
        quelle = inspect.getsource(worker.run_batch)
        self.assertIn('"preflight_erneut": bool(entsch.get("preflight_erneut"))', quelle)
        self.assertIn('log.info("Fortsetzung trotz Preflight"', quelle)
        self.assertIn('preflight_erneut=(bool(entsch.get("preflight_erneut"))',
                      quelle)


if __name__ == "__main__":
    unittest.main(verbosity=2)
