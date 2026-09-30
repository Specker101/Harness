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
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import stand, streamjson, worker                            # noqa: E402
from hx.config import load_config                                   # noqa: E402
from hx.util import ensure_dir                                      # noqa: E402

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


class TestPreflightZaehlerArchiv(unittest.TestCase):
    """Punkt 2 (Befund M224-4): der Preflight-Zaehler gegen die archivierten Laeufe."""

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13bb"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "root")
        self.decomp = ensure_dir(self.tmp / "decomp")
        self.ana = ensure_dir(self.decomp / "analysis")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.decomp)
        cfg.data["paths"]["harness_home"] = str(self.tmp)
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def archiv(self, batch: int, name: str) -> Path:
        d = ensure_dir(self.ana / f"_m{batch}")
        p = d / name
        p.write_text(f"# Preflight {batch}\n", encoding="utf-8")
        return p

    def aufruf(self, batch: int, n: int, frueh: bool = True) -> None:
        d = ensure_dir(Path(self.root) / "runs" / f"b{batch:03d}")
        zeilen = [json.dumps({"ts": f"2026-09-30T0{i}:00:00+00:00", "min": 40.0 + i,
                              "frueh": frueh, "werkzeug": "PowerShell"})
                  for i in range(n)]
        (d / "preflight-aufrufe.jsonl").write_text("\n".join(zeilen) + "\n", encoding="utf-8")

    def test_fehllauf_ist_die_differenz(self):
        self.aufruf(224, 1)
        self.archiv(224, "_preflight_224_fehllauf1.txt")
        self.archiv(224, "_preflight_224.txt")
        a = stand.preflight_archiv(self.cfg, 224)
        self.assertEqual(a["fehllauf"], ["analysis/_m224/_preflight_224_fehllauf1.txt"])
        self.assertEqual(a["ungezaehlt"], 1)
        zeile = stand.preflight_zaehler_zeile(self.cfg, 224)[0]
        self.assertIn("1 Aufruf(e) im Mitschnitt", zeile)
        self.assertIn("_preflight_224_fehllauf1.txt", zeile)
        self.assertIn("-> 2 Laeufe", zeile)

    def test_vor_fortsetzung_zaehlt_nicht(self):
        """R13ah-Kopien sind byteweise Kopien eines gezaehlten Laufs."""
        self.aufruf(218, 2)
        self.archiv(218, "_preflight_218_vor_fortsetzung1.txt")
        self.archiv(218, "_preflight_218.txt")
        a = stand.preflight_archiv(self.cfg, 218)
        self.assertEqual(a["ungezaehlt"], 0)
        self.assertNotIn("vor_fortsetzung", " ".join(a["dateien"]))
        self.assertIn("keine archivierten Fehllaeufe", stand.preflight_zaehler_zeile(self.cfg, 218)[0])

    def test_nicht_lauf_dateien_zaehlen_nicht(self):
        self.aufruf(224, 1)
        for name in ("_preflight_224_zeiten.txt", "_preflight_224_vergleich.txt",
                     "_preflight_224_stderr.txt"):
            self.archiv(224, name)
        self.assertEqual(stand.preflight_archiv(self.cfg, 224)["ungezaehlt"], 0)

    def test_ueberholt_wird_benannt_aber_nicht_addiert(self):
        """Ein ueberholter Lauf kann im Mitschnitt schon gezaehlt sein - darum getrennt."""
        self.aufruf(220, 2)
        self.archiv(220, "_preflight_220_ueberholt1.txt")
        self.archiv(220, "_preflight_220_lauf2_ueberholt.txt")
        a = stand.preflight_archiv(self.cfg, 220)
        self.assertEqual(a["ungezaehlt"], 0)
        self.assertEqual(len(a["ueberholt"]), 2)
        zeile = stand.preflight_zaehler_zeile(self.cfg, 220)[0]
        self.assertIn("2 Aufruf(e) im Mitschnitt", zeile)
        self.assertIn("ueberholt abgelegt", zeile)
        self.assertNotIn("-> 4 Laeufe", zeile)

    def test_ohne_archiv_keine_differenz(self):
        self.aufruf(226, 1, frueh=False)
        zeile = stand.preflight_zaehler_zeile(self.cfg, 226)[0]
        self.assertIn("1 Aufruf(e) im Mitschnitt (davon 0 zu frueh)", zeile)
        self.assertIn("keine archivierten Fehllaeufe (_m226)", zeile)

    def test_ungueltige_zeilen_zaehlen_nicht(self):
        d = ensure_dir(Path(self.root) / "runs" / "b227")
        (d / "preflight-aufrufe.jsonl").write_text('{"ts": "x"}\nkaputt\n\n', encoding="utf-8")
        self.assertEqual(stand.zaehle_preflight_aufrufe(self.cfg, 227), (1, 0))

    def test_result_json_traegt_die_differenz(self):
        quelle = inspect.getsource(worker._finish_run)
        self.assertIn('pf_archiv = stand.preflight_archiv(cfg, batch)', quelle)
        self.assertIn('"preflight_ungezaehlt": pf_archiv["ungezaehlt"]', quelle)
        self.assertIn('"preflight_laeufe_gesamt": int(preflight_laeufe)', quelle)
        self.assertIn('"preflight_archiv_fehllauf"', quelle)
        self.assertIn("archivierte Fehllaeufe nicht gezaehlt", quelle)

    def test_review_fakten_nennen_den_abgleich(self):
        from hx.orchestrator import Orchestrator
        quelle = inspect.getsource(Orchestrator.harness_facts)
        self.assertIn("standmod.preflight_zaehler_zeile(", quelle)
        self.assertIn('res.get("preflight_laeufe")', quelle)


class TestRueckblickEchteBatches(unittest.TestCase):
    """Die drei Batches aus M224-4 - gegen die echten Dateien (skip, wenn sie fehlen)."""

    BATCHES = {218: (2, 1), 223: (1, 1), 224: (1, 1)}   # (Aufrufe im Mitschnitt, Fehllaeufe)

    def setUp(self):
        self.cfg = load_config()
        self.dec = Path(self.cfg.decomp)

    def test_rueckblick_stimmt(self):
        for batch, (aufrufe, fehllauf) in self.BATCHES.items():
            p = (self.dec / "analysis" / f"_m{batch}"
                 / f"_preflight_{batch}_fehllauf1.txt")
            if not p.is_file():
                self.skipTest(f"{p} fehlt")
            a = stand.preflight_archiv(self.cfg, batch)
            self.assertEqual(a["ungezaehlt"], fehllauf, batch)
            gelesen = stand.zaehle_preflight_aufrufe(self.cfg, batch)
            if gelesen[0] != aufrufe:
                self.skipTest(f"b{batch}: Mitschnitt hat jetzt {gelesen}, nicht {aufrufe}")
            zeile = stand.preflight_zaehler_zeile(self.cfg, batch)[0]
            self.assertIn(f"-> {aufrufe + fehllauf} Laeufe", zeile)


if __name__ == "__main__":
    unittest.main(verbosity=2)
