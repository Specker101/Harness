"""Tests fuer R13bf (2026-10-01): vier Harness-Fixes aus den Batches B230-B234.

**Teil B - Bilanz ohne Preflight (Aussensicht B234, Befund M234-1).** B234 brach ab,
bevor ein Preflight lief (`runs/b234/result.json`: `preflight_laeufe: 0`). Die Bilanz
fuehrte trotzdem „115 referenzgleich" - das war die **Soll-Spalte** des Batch-Dokuments
(`port-batch234-…md:49`). Zwei Aenderungen:

* `stand.ist_wert` liest keine Zelle mehr aus einer Spalte, die **Soll** heisst
  (Kopfzeile der Tabelle, `stand.tabellen_kopf`).
* `stand.kernzahlen` faellt fuer einen Batch **in der Preflight-Aera** ohne eigene
  `_preflight_<N>.txt` nicht mehr auf das Dokument zurueck: die Zeile traegt **keine**
  C-Zahl (`c_nicht_gemessen`), die Anzeige bleibt beim letzten gemessenen Stand, und
  `bilanz.gesamt_block` sagt „B<N> nicht gemessen".

Gefrorene Fixture: `tests/fixtures/stand_b234_luecke/` (echter Dokumentstand 10:51 +
`_preflight_233.txt`, **ohne** `_preflight_234.txt`).
"""

from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import bilanz, stand                                          # noqa: E402
from hx.config import load_config                                     # noqa: E402
from hx.util import ensure_dir, write_text_atomic                     # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "stand_b234_luecke"
DOK = "port-batch234-c-ausgefuehrte-koepfe-2026-10-01.md"
# Der echte Dokumentausschnitt: Ist-Spalte 110, Soll-Spalte 115.
TABELLE = ("| Bilanzzeile | Ist (B233) | Soll (B234) | Begruendung |\n"
           "|---|---|---|---|\n"
           "| `C Koepfe` | 110 / 6187 / 0 | **115 / 6271 / 0** | +5 Koepfe |\n")


class Basis(unittest.TestCase):
    """Wegwerf-Repo mit der eingefrorenen Fixture; `cfg` zeigt darauf."""

    MIT_PREFLIGHT_234 = False

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13bf"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.dec = ensure_dir(self.tmp / "decomp")
        shutil.copytree(FIXTURE / "decomp" / "analysis", self.dec / "analysis")
        if self.MIT_PREFLIGHT_234:
            quelle = self.dec / "analysis" / "_preflight_233.txt"
            ziel = self.dec / "analysis" / "_preflight_234.txt"
            roh = quelle.read_bytes()
            ziel.write_bytes(roh.replace(b"110 / 6187 / 0", b"115 / 6271 / 0"))
        self.root = ensure_dir(self.tmp / "harness")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.dec)
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        self.cfg = cfg

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def reihe(self) -> dict:
        return {e["batch"]: e for e in stand.kernzahlen(self.cfg, 8)}


# ------------------------------------------------- 1) Soll-Spalte ist kein Wert
class TestSollSpalte(Basis):
    def test_ist_spalte_gewinnt_gegen_die_soll_spalte(self):
        """Der echte B234-Ausschnitt: 110 (Ist), nicht 115 (Soll)."""
        _nr, wert = stand.ist_wert(self.text(), stand._ETIKETT_CKOPF,
                                   stand._RE_ZAHL_CKOPF)
        self.assertEqual(wert, (110, 6187, 0))

    def test_nur_soll_spalte_ergibt_keinen_wert(self):
        """Rotprobe: steht der Wert NUR unter `Soll`, gibt es keinen Messwert."""
        text = ("| Bilanzzeile | Zaehlerdefinition | Soll (B234) |\n|---|---|---|\n"
                "| `C Koepfe` | registrierte Koepfe (`c_kopf.py`) | **115 / 6271 / 0** |\n")
        _nr, wert = stand.ist_wert(text, stand._ETIKETT_CKOPF, stand._RE_ZAHL_CKOPF)
        self.assertIsNone(wert)

    def test_ohne_kopfzeile_bleibt_die_alte_regel(self):
        """Eine Tabelle ohne Kopf/Trenner wird wie vorher gelesen (letzte Zahlzelle)."""
        text = ("| **`C Koepfe`** | 110 / 6187 / 0 | 115 / 6271 / 0 |\n")
        _nr, wert = stand.ist_wert(text, stand._ETIKETT_CKOPF, stand._RE_ZAHL_CKOPF)
        self.assertEqual(wert, (115, 6271, 0))

    def test_paket_e_soll_spalte_zaehlt_nicht(self):
        text = ("| Bilanzzeile | Ist (B233) | Soll (B234) |\n|---|---|---|\n"
                "| Paket E offen | 25 / 2011, Blaetter 20 / 1657 | "
                "**20 / 1655, Blaetter 17 / 1200** |\n")
        _nr, wert = stand.ist_wert(text, stand._ETIKETT_PAKET_E, stand._RE_ZAHL_PAKET_E)
        self.assertEqual(wert, (25, 2011, 20, 1657))

    def text(self) -> str:
        return (self.dec / "analysis" / DOK).read_text(encoding="utf-8")


# ------------------------------------------- 2) Luecke in der Preflight-Aera
class TestLuecke(Basis):
    def test_ohne_preflight_keine_c_zahl(self):
        r = self.reihe()
        self.assertNotIn("c_koepfe", r[234])
        self.assertNotIn("c_faelle", r[234])
        self.assertTrue(r[234]["c_nicht_gemessen"])
        self.assertEqual(r[234]["c_erwartet"], "_preflight_234.txt")

    def test_letzter_gemessener_stand_bleibt(self):
        r = self.reihe()
        self.assertEqual(r[233]["c_koepfe"], 110)
        self.assertEqual(r[233]["c_quelle"], "_preflight_233.txt")
        self.assertEqual(r[234].get("c_quelle"), None)

    def test_bilanz_nennt_die_luecke_und_bleibt_bei_110(self):
        zeilen = bilanz.gesamt_block(self.cfg)
        c_zeile = [z for z in zeilen if z.strip().startswith("C Koepfe referenzgleich")]
        self.assertEqual(len(c_zeile), 1)
        self.assertIn("110 Koepfe", c_zeile[0])
        self.assertIn("B233", c_zeile[0])
        self.assertNotIn("115", c_zeile[0])
        self.assertTrue(any("B234 nicht gemessen" in z for z in zeilen), zeilen)
        self.assertTrue(any("_preflight_234.txt" in z for z in zeilen), zeilen)
        self.assertTrue(any("Stand von B233" in z for z in zeilen), zeilen)

    def test_mit_preflight_ist_die_luecke_weg(self):
        """Rotprobe: liegt die Datei vor, wird gemessen - und zwar die Messung."""
        self._mit_datei()
        r = self.reihe()
        self.assertNotIn("c_nicht_gemessen", r[234])
        self.assertEqual(r[234]["c_koepfe"], 115)
        self.assertEqual(r[234]["c_quelle"], "_preflight_234.txt")
        zeilen = bilanz.gesamt_block(self.cfg)
        self.assertFalse(any("B234 nicht gemessen" in z for z in zeilen), zeilen)

    def test_alter_batch_ohne_aera_nutzt_die_ist_spalte(self):
        """Vor der Preflight-Aera bleibt der Dokumentweg (R13x) erhalten."""
        for p in (self.dec / "analysis").glob("_preflight_*.txt"):
            p.unlink()
        r = self.reihe()
        self.assertEqual(r[234]["c_koepfe"], 110)
        self.assertEqual(r[234]["c_quelle"], DOK)
        self.assertNotIn("c_nicht_gemessen", r[234])

    def _mit_datei(self) -> None:
        quelle = (self.dec / "analysis" / "_preflight_233.txt").read_bytes()
        (self.dec / "analysis" / "_preflight_234.txt").write_bytes(
            quelle.replace(b"110 / 6187 / 0", b"115 / 6271 / 0"))


class TestMitPreflight234(Basis):
    """Dieselbe Fixture MIT `_preflight_234.txt` - die Kennzahl kommt aus der Datei."""

    MIT_PREFLIGHT_234 = True

    def test_datei_schlaegt_das_dokument(self):
        r = self.reihe()
        self.assertEqual(r[234]["c_koepfe"], 115)
        self.assertEqual(r[234]["c_quelle"], "_preflight_234.txt")


if __name__ == "__main__":
    unittest.main()
