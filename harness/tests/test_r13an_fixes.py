"""Tests fuer R13an (2026-09-29): `plan_mischung` robust + entkoppelte Fixtures.

**Anlass (gemessen).** `test_r13aa_fixes.py::test_mischverhaeltnis_aus_dem_plan` las
`analysis/hybrid-plan.md` **lebend** aus `g:\\Silent Scope Decomp`. Der laufende Batch B216
hat die Datei um 23:04 um eine neue Zeile ergaenzt:

```
hybrid-plan.md:299  Mischverhaeltnis 2:1 ab B217 voraussichtlich **B221** (B217 B, B218 B, B219 C,
hybrid-plan.md:301  - **Mischverhaeltnis 2 B : 1 C (ENTSCHEIDUNG Reviewer):** B208 B, B209 B, B210 C
```

Die alte Regel "erste Trefferzeile" nahm damit Zeile 299, fand darin kein `n B : m C` und
lieferte still `anteil=None` → `TypeError` im Test. Jetzt gilt:

* gewaehlt wird die Zeile mit einem Verhaeltnis `n B : m C` (auch `n B:m C`),
* gibt es mehrere, die mit dem Wort `ENTSCHEIDUNG`, sonst die **letzte**,
* traegt KEINE Zeile ein Verhaeltnis, ist `erkannt=False` + `grund` gesetzt und
  `plan_mischung_pruefen` meldet es ins Log **und** in die Review-Fakten
  (`PARSER: Mischverhaeltnis in hybrid-plan.md nicht erkannt`) — kein stilles `None` (R13ae).
  Ist die Datei selbst nicht lesbar, lautet die Zeile `PARSER: hybrid-plan.md nicht lesbar`
  (eigener Fall: in einem Echtlauf eine Anomalie, in Tests mit umgebogenem Wurzelverzeichnis
  normal) — ebenfalls kein Schweigen.

**Fixtures** (`tests/fixtures/`, eingefroren aus dem Decomp-Repo, ohne Vorspann — die
Zeilennummern stimmen mit der Originaldatei ueberein):

| Datei | Decomp-Revision | Zustand |
|---|---|---|
| `hybrid-plan_vor_b216.md` | `bd92910` | vor dem B216-Nachtrag: nur die Zeile `2 B : 1 C (ENTSCHEIDUNG Reviewer)` |
| `hybrid-plan_mit_b216.md` | `4f60f45` | mit beiden Zeilen (`:299` ohne Verhaeltnis, `:301` mit) |
"""

from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import stand                                              # noqa: E402
from hx.config import load_config                                 # noqa: E402
from hx.util import Log, ensure_dir, write_text_atomic            # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
VOR_B216 = FIXTURES / "hybrid-plan_vor_b216.md"
MIT_B216 = FIXTURES / "hybrid-plan_mit_b216.md"


class Basis(unittest.TestCase):
    """Wegwerf-Decomp-Repo; der Plan wird aus einer Fixture bzw. einer Zeile gebaut."""

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13an"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "harness")
        self.decomp = ensure_dir(self.tmp / "decomp")
        self.ana = ensure_dir(self.decomp / "analysis")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.decomp)
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["paths"]["harness_home"] = str(self.tmp)
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def fixture(self, quelle: Path) -> None:
        """Die eingefrorene Datei unveraendert in das Wegwerf-Repo legen."""
        if not quelle.is_file():
            self.skipTest(f"Fixture fehlt: {quelle.name}")
        shutil.copy2(quelle, self.ana / "hybrid-plan.md")

    def plan(self, *zeilen: str) -> None:
        write_text_atomic(self.ana / "hybrid-plan.md",
                          "# Plan\n\n" + "\n".join(zeilen) + "\n")

    def log_zeilen(self) -> list[dict]:
        p = self.tmp / "log.jsonl"
        if not p.is_file():
            return []
        return [json.loads(z) for z in p.read_text(encoding="utf-8").splitlines() if z.strip()]


AUFTRAG_ZEILE = ("Mischverhaeltnis 2:1 ab B217 voraussichtlich **B221**"
                 " (B217 B, B218 B, B219 C,")
ENTSCHEIDUNG_ZEILE = ("- **Mischverhaeltnis 2 B : 1 C (ENTSCHEIDUNG Reviewer):** "
                      "B208 B, B209 B, B210 C")
OHNE_VERHAELTNIS = "- **Mischverhaeltnis** offen (noch nicht entschieden)"


class TestFixtures(unittest.TestCase):
    """Die eingefrorenen Staende - Zeilennummern wie in `analysis/hybrid-plan.md`."""

    def test_vor_b216_traegt_genau_die_entscheidungszeile(self):
        if not VOR_B216.is_file():
            self.skipTest("Fixture fehlt")
        text = VOR_B216.read_text(encoding="utf-8")
        self.assertIn(ENTSCHEIDUNG_ZEILE, text)
        self.assertNotIn("2:1 ab B217", text, "der Stand ist VOR dem B216-Nachtrag")
        zeilen = [z for z in text.splitlines() if "Mischverh" in z]
        self.assertEqual(len(zeilen), 1)
        self.assertEqual(text.splitlines()[285].strip(), ENTSCHEIDUNG_ZEILE,
                         "die Zeile liegt wie in der Originaldatei (:286)")

    def test_mit_b216_traegt_beide_zeilen_und_die_originalnummern(self):
        if not MIT_B216.is_file():
            self.skipTest("Fixture fehlt")
        text = MIT_B216.read_text(encoding="utf-8")
        self.assertIn(AUFTRAG_ZEILE, text)
        self.assertIn(ENTSCHEIDUNG_ZEILE, text)
        zeilen = text.splitlines()
        self.assertEqual(zeilen[298].strip().split()[0], "Mischverhaeltnis",
                         ":299 = die neue Zeile (ohne `n B : m C`)")
        self.assertEqual(zeilen[300].strip(), ENTSCHEIDUNG_ZEILE, ":301 = die Entscheidung")
        # Und genau diese erste Zeile war der Grund fuer den Fehler: sie traegt kein
        # Verhaeltnis, die alte Regel nahm aber die erste Trefferzeile.
        self.assertIsNone(stand._RE_MISCH_ZAHL.search(zeilen[298]))


class TestAuswahlregel(Basis):
    """Die Zeile mit `n B : m C` gewinnt; bei mehreren die ENTSCHEIDUNG, sonst die letzte."""

    def test_stand_vor_b216(self):
        self.fixture(VOR_B216)
        p = stand.plan_mischung(self.cfg)
        self.assertTrue(p["erkannt"])
        self.assertAlmostEqual(p["anteil"], 1 / 3, places=3)
        self.assertEqual(p["paare"].get(208), "B")
        self.assertEqual(p["paare"].get(210), "C")
        self.assertEqual(p["kandidaten"], 1)

    def test_heutiger_stand_mit_beiden_zeilen(self):
        """Die neue Zeile :299 wird uebersprungen, die Entscheidung :301 gewinnt."""
        self.fixture(MIT_B216)
        p = stand.plan_mischung(self.cfg)
        self.assertTrue(p["erkannt"])
        self.assertAlmostEqual(p["anteil"], 1 / 3, places=3)
        self.assertEqual(p["regel"], "2 B : 1 C")
        self.assertEqual([p["paare"].get(b) for b in (208, 209, 210)], ["B", "B", "C"])
        self.assertNotIn(217, p["paare"], "die Zeile ohne Verhaeltnis darf nicht gewinnen")
        self.assertEqual(p["kandidaten"], 2)
        self.assertIn("ENTSCHEIDUNG", p["zeile"])

    def test_letzte_zeile_gewinnt_ohne_entscheidungswort(self):
        self.plan("- **Mischverhaeltnis 1 B : 1 C:** B201 B, B202 C",
                  "Mischverhaeltnis 3 B : 1 C ab B210 (ohne Entscheidungswort)")
        p = stand.plan_mischung(self.cfg)
        self.assertEqual(p["regel"], "3 B : 1 C")
        self.assertAlmostEqual(p["anteil"], 0.25, places=3)
        self.assertNotIn(201, p["paare"])

    def test_entscheidungswort_schlaegt_die_spaetere_zeile(self):
        self.plan("- **Mischverhaeltnis 2 B : 1 C (ENTSCHEIDUNG):** B208 B, B209 B, B210 C",
                  "Mischverhaeltnis 1 B : 1 C ab B211 (nur eine Ankuendigung)")
        p = stand.plan_mischung(self.cfg)
        self.assertEqual(p["regel"], "2 B : 1 C")
        self.assertEqual(p["paare"].get(210), "C")

    def test_form_ohne_leerzeichen_wird_erkannt(self):
        self.plan("Mischverhaeltnis 2B:1C ab B217 (B217 B, B218 B, B219 C)")
        p = stand.plan_mischung(self.cfg)
        self.assertTrue(p["erkannt"])
        self.assertAlmostEqual(p["anteil"], 1 / 3, places=3)

    def test_ohne_verhaeltnis_kein_stilles_none(self):
        """Kein Verhaeltnis: `erkannt=False` + Grund + Meldung in Log und Fakten."""
        self.plan(OHNE_VERHAELTNIS)
        p = stand.plan_mischung(self.cfg)
        self.assertFalse(p["erkannt"])
        self.assertIsNone(p["anteil"])
        self.assertIn("kein Verhaeltnis", p["grund"])
        meldungen = stand.plan_mischung_pruefen(self.cfg, log=self.log)
        self.assertEqual(len(meldungen), 1)
        self.assertTrue(meldungen[0].startswith(
            "PARSER: Mischverhaeltnis in hybrid-plan.md nicht erkannt"), meldungen)
        self.assertTrue(any("Mischverhaeltnis" in str(z.get("msg") or "")
                            for z in self.log_zeilen()))

    def test_fehlende_datei_wird_gemeldet(self):
        """Fehlende Datei: eigener Wortlaut ("nicht lesbar"), aber ebenfalls gemeldet."""
        (self.ana / "hybrid-plan.md").unlink(missing_ok=True)
        p = stand.plan_mischung(self.cfg)
        self.assertFalse(p["erkannt"])
        self.assertEqual(p["grund"], "Datei nicht lesbar")
        meldungen = stand.plan_mischung_pruefen(self.cfg, log=self.log)
        self.assertEqual(len(meldungen), 1)
        self.assertTrue(meldungen[0].startswith("PARSER: hybrid-plan.md nicht lesbar"),
                        meldungen)

    def test_erkannte_datei_meldet_nichts(self):
        self.fixture(MIT_B216)
        self.assertEqual(stand.plan_mischung_pruefen(self.cfg, log=self.log), [])
        self.assertEqual(self.log_zeilen(), [], "kein Warnrauschen im Normalfall")

    def test_kehrwertform_bleibt_kompatibel(self):
        """Die Aufrufer lesen `paare`/`anteil`/`regel`/`zeile`/`datei` wie bisher."""
        self.fixture(VOR_B216)
        p = stand.plan_mischung(self.cfg)
        for feld in ("paare", "anteil", "regel", "zeile", "datei"):
            self.assertIn(feld, p)
        self.assertEqual(p["datei"], "hybrid-plan.md")


class TestStrangQuelle(Basis):
    """Der C-Strang von B210 kommt weiter aus der Plan-Zeile (dritte Quelle)."""

    def test_b210_aus_dem_plan(self):
        self.fixture(MIT_B216)
        s = stand.strang_von_batch(self.cfg, 210)
        self.assertEqual(s["strang"], "C")
        self.assertIn("hybrid-plan", s["quelle"])

    def test_ohne_verhaeltnis_bleibt_der_strang_aus_der_zeile(self):
        """Auch ohne Verhaeltnis zaehlen die Paare der letzten Zeile (Rueckfall)."""
        self.plan("Mischverhaeltnis offen (noch nicht entschieden): B210 C, B211 B")
        self.assertEqual(stand.strang_von_batch(self.cfg, 210)["strang"], "C")


if __name__ == "__main__":
    unittest.main()
