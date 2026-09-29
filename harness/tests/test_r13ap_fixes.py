"""Tests fuer R13ap (2026-09-30): Preflight-Dateien kodierungstolerant lesen + Tippfehler.

**Auftrag.** (2) „Umschwellschwelle" -> „Umschaltschwelle" (Hook, Tests, Doku).
(3) `analysis/_preflight_*.txt` kodierungstolerant lesen: BOM erkennen (UTF-16 LE/BE,
UTF-8-BOM), sonst UTF-8; NUL-Bytes ohne BOM als UTF-16 LE versuchen. **Eine zentrale
Lesefunktion**, alle Leser darauf umstellen. Wird eine Datei als UTF-16 gelesen, steht
in den Review-Fakten `Preflight B<N> in UTF-16, gelesen`. Fixture: UTF-16-Kopie von
`_preflight_216.txt`, alle Pflichtzeilen müssen erkannt werden.

**Anlass (gemessen, `docs/_r13ap_belege.md`):** `_preflight_216.txt` ist **UTF-16 LE mit
BOM** (FF FE) - B211-B215 sind UTF-8-BOM. Der Review von B216 trug deshalb drei Zeilen
`PARSER: Zeile ... nicht erkannt` (`harness/runs/b217/harness-facts.md:23-25`), obwohl die
Datei die Zeilen hat. Dieselbe Form hatten schon B155-B158.
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

from hx import stand, uhr                                          # noqa: E402
from hx.config import load_config                                  # noqa: E402
from hx.orchestrator import Orchestrator                           # noqa: E402
from hx.util import (Log, ensure_dir, erkenne_kodierung,           # noqa: E402
                     ist_utf16, read_text_erkannt, write_text_atomic)

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURE_216 = FIXTURES / "preflight_216_utf16.txt"
BATCH_216 = 216
# Die Zeilen der echten Datei (gemessen 2026-09-30, `_preflight_216.txt`).
C_KOPF_216 = (85, 4446, 0)
BAHN_216 = {"koepfe": 62, "gesamt": 85, "bloecke": 382, "bloecke_gesamt": 486,
            "verifiziert": 65, "teilgeprueft": 20}
HYBRID_216 = {"halt_pc": "8000C9E8", "art": "MMIO", "weg": 460, "weg_gesamt": 42599}


def _fixture_text() -> str:
    """Der Klartext der Fixture (UTF-16 entschluesselt)."""
    if not FIXTURE_216.is_file():
        raise unittest.SkipTest("Fixture fehlt")
    return FIXTURE_216.read_bytes().decode("utf-16-le").lstrip("\ufeff")


class TestErkennung(unittest.TestCase):
    """`util.erkenne_kodierung` / `util.read_text_erkannt` - die eine Lesestelle."""

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13ap_util"
        shutil.rmtree(self.tmp, ignore_errors=True)
        ensure_dir(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _datei(self, name: str, b: bytes) -> Path:
        p = self.tmp / name
        p.write_bytes(b)
        return p

    def test_utf8_ohne_bom(self):
        p = self._datei("a.txt", "C Koepfe 85 / 4446 / 0\n".encode("utf-8"))
        self.assertEqual(erkenne_kodierung(p.read_bytes()), "utf-8")
        text, kod = read_text_erkannt(p)
        self.assertEqual(kod, "utf-8")
        self.assertEqual(text, "C Koepfe 85 / 4446 / 0\n")

    def test_utf8_mit_bom_und_umlaut(self):
        p = self._datei("b.txt", "\ufeffBahnabdeckung: 62/85\nGr\u00fc\u00dfe\n"
                        .encode("utf-8"))
        text, kod = read_text_erkannt(p)
        self.assertEqual(kod, "utf-8-bom")
        self.assertFalse(text.startswith("\ufeff"), "BOM ist entfernt")
        self.assertIn("Grüße", text)

    def test_utf16_le_mit_bom(self):
        p = self._datei("c.txt", "\ufeffC Koepfe 85 / 4446 / 0\n".encode("utf-16-le"))
        text, kod = read_text_erkannt(p)
        self.assertEqual(kod, "utf-16-le")
        self.assertTrue(ist_utf16(kod))
        self.assertEqual(text, "C Koepfe 85 / 4446 / 0\n")
        self.assertNotIn("\x00", text)

    def test_utf16_be_mit_bom(self):
        p = self._datei("d.txt", "\ufeffHybrid-Lauf 6400919\n".encode("utf-16-be"))
        text, kod = read_text_erkannt(p)
        self.assertEqual(kod, "utf-16-be")
        self.assertTrue(ist_utf16(kod))
        self.assertEqual(text, "Hybrid-Lauf 6400919\n")

    def test_utf16_le_ohne_bom_ueber_nullbytes(self):
        p = self._datei("e.txt", "C Koepfe 85 / 4446 / 0\n".encode("utf-16-le"))
        self.assertEqual(erkenne_kodierung(p.read_bytes()), "utf-16-le-ohne-bom")
        text, kod = read_text_erkannt(p)
        self.assertEqual(kod, "utf-16-le-ohne-bom")
        self.assertTrue(ist_utf16(kod))
        self.assertEqual(text, "C Koepfe 85 / 4446 / 0\n")

    def test_fehlende_datei_ist_leer_ohne_kodierung(self):
        self.assertEqual(read_text_erkannt(self.tmp / "gibtsnicht.txt"), ("", ""))
        self.assertFalse(ist_utf16(""))
        self.assertFalse(ist_utf16(None))

    def test_leere_datei_ist_utf8(self):
        p = self._datei("f.txt", b"")
        self.assertEqual(read_text_erkannt(p), ("", "utf-8"))

    def test_fixture_ist_echtes_utf16_le(self):
        """Die Fixture ist eine BYTE-Kopie von `_preflight_216.txt` (FF FE)."""
        b = FIXTURE_216.read_bytes()
        self.assertEqual(b[:2], b"\xff\xfe", "UTF-16 LE mit BOM")
        self.assertEqual(erkenne_kodierung(b), "utf-16-le")
        self.assertIn("C Koepfe", _fixture_text())


class Basis(unittest.TestCase):
    """Wegwerf-Workspace mit eigenem 'decomp'-Repo (nur `analysis/`)."""

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13ap"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "root")
        self.decomp = ensure_dir(self.tmp / "decomp")
        self.ana = ensure_dir(self.decomp / "analysis")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.decomp)
        cfg.data["paths"]["harness_home"] = str(self.tmp)
        cfg.data["paths"]["secrets"] = str(ensure_dir(self.tmp / "secrets"))
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def utf16(self, batch: int = BATCH_216) -> Path:
        """Die UTF-16-Fixture als Preflight-Datei des Batches ablegen (Byte-Kopie)."""
        p = self.ana / f"_preflight_{batch}.txt"
        shutil.copy2(FIXTURE_216, p)
        return p

    def utf8(self, batch: int = BATCH_216) -> Path:
        """Derselbe Inhalt als UTF-8-BOM (wie B211-B215)."""
        p = self.ana / f"_preflight_{batch}.txt"
        write_text_atomic(p, "\ufeff" + _fixture_text())
        return p

    def log_zeilen(self) -> list[dict]:
        if not self.log.path.is_file():
            return []
        return [json.loads(z) for z in
                self.log.path.read_text(encoding="utf-8").splitlines() if z.strip()]


# ------------------------------------------------- 1) Alle Leser sehen denselben Text
class TestLeser(Basis):
    def test_pflichtzeilen_werden_erkannt(self):
        """Die drei Pflichtzeilen - in UTF-16 keine `nicht erkannt`-Meldung mehr."""
        self.utf16()
        self.assertEqual(stand.preflight_zeilen_pruefen(self.cfg, self.log, anzahl=1), [])
        self.assertEqual([z for z in self.log_zeilen()
                          if z.get("msg") == "Preflight-Zeile nicht erkannt"], [])

    def test_c_koepfe_aus_utf16(self):
        self.utf16()
        reihe = stand.preflight_c_koepfe(self.cfg, 1)
        self.assertEqual(len(reihe), 1)
        self.assertEqual((reihe[0]["koepfe"], reihe[0]["faelle"],
                          reihe[0]["abweichungen"]), C_KOPF_216)

    def test_bahnabdeckung_aus_utf16(self):
        self.utf16()
        reihe = stand.preflight_bahnabdeckung(self.cfg, 1)
        self.assertEqual(len(reihe), 1)
        self.assertEqual(reihe[0]["quelle"], "Bahnabdeckung")
        for feld, wert in BAHN_216.items():
            self.assertEqual(reihe[0][feld], wert, feld)

    def test_hybrid_lauf_aus_utf16(self):
        self.utf16()
        reihe = stand.hybrid_verlauf(self.cfg, 1)
        self.assertEqual(len(reihe), 1)
        for feld, wert in HYBRID_216.items():
            self.assertEqual(reihe[0][feld], wert, feld)

    def test_utf8_und_utf16_lesen_dasselbe(self):
        """Die Kodierung darf das Ergebnis NICHT veraendern (Kern der Umstellung)."""
        self.utf16()
        a = (stand.preflight_zeilen_pruefen(self.cfg, anzahl=1),
             stand.preflight_c_koepfe(self.cfg, 1),
             stand.preflight_bahnabdeckung(self.cfg, 1),
             stand.hybrid_verlauf(self.cfg, 1))
        self.utf8()
        b = (stand.preflight_zeilen_pruefen(self.cfg, anzahl=1),
             stand.preflight_c_koepfe(self.cfg, 1),
             stand.preflight_bahnabdeckung(self.cfg, 1),
             stand.hybrid_verlauf(self.cfg, 1))
        self.assertEqual(a[1:], b[1:])
        self.assertEqual(a[0], b[0])

    def test_utf8_ohne_bom_liest_weiter(self):
        """Der Normalfall bleibt der Normalfall (auch ohne BOM)."""
        write_text_atomic(self.ana / "_preflight_216.txt", _fixture_text())
        self.assertEqual(stand.preflight_zeilen_pruefen(self.cfg, anzahl=1), [])
        self.assertEqual(stand.preflight_c_koepfe(self.cfg, 1)[0]["koepfe"], 85)

    def test_eine_lesestelle_fuer_alle_vier(self):
        """Alle vier Leser gehen ueber `stand.preflight_text` (Auftrag: EINE Stelle)."""
        for fn in (stand.preflight_zeilen_pruefen, stand.preflight_c_koepfe,
                   stand.preflight_bahnabdeckung, stand.hybrid_verlauf):
            quelle = inspect.getsource(fn)
            self.assertIn("preflight_text(", quelle, fn.__name__)
            self.assertNotIn("read_text(", quelle, fn.__name__)


# ------------------------------------------------- 2) Der Hinweis in den Review-Fakten
class TestHinweis(Basis):
    def test_utf16_ergibt_eine_hinweiszeile(self):
        self.utf16()
        zeilen = stand.preflight_kodierung_hinweis(self.cfg, 1, self.log)
        self.assertEqual(len(zeilen), 1)
        self.assertTrue(zeilen[0].startswith("Preflight B216 in UTF-16, gelesen"),
                        zeilen[0])
        self.assertIn("_preflight_216.txt", zeilen[0])
        self.assertIn("utf-16-le", zeilen[0])
        self.assertTrue(any(z.get("msg") == "Preflight-Datei ist UTF-16"
                            for z in self.log_zeilen()))

    def test_utf8_ergibt_keinen_hinweis(self):
        self.utf8()
        self.assertEqual(stand.preflight_kodierung_hinweis(self.cfg, 1, self.log), [])
        self.assertEqual(self.log_zeilen(), [], "kein Warnrauschen im Normalfall")

    def test_keine_datei_ergibt_keinen_hinweis(self):
        self.assertEqual(stand.preflight_kodierung_hinweis(self.cfg, 1), [])


class TestFakten(Basis):
    """Der Hinweis steht im Messdatenblock - und die positive Zeile bleibt stehen."""

    def fakten(self, batch: int = BATCH_216) -> str:
        o = Orchestrator(self.cfg, self.log, mock=True,
                         state_file=self.root / "harness" / "state" / "run.json")
        o.say = lambda *a, **k: None
        o.state.data["last_batch_number"] = batch
        return o.harness_facts(batch, ziel=self.tmp / "out")

    def test_hinweis_und_positive_zeile_stehen_beide(self):
        self.utf16()
        text = self.fakten()
        self.assertIn("- Preflight B216 in UTF-16, gelesen", text)
        self.assertIn("- Parser (R13ae): erwartete Zeilen gelesen, keine Luecke", text)
        self.assertNotIn("nicht erkannt", text)

    def test_normalfall_hat_keinen_hinweis(self):
        self.utf8()
        text = self.fakten()
        self.assertNotIn("UTF-16", text)
        self.assertIn("- Parser (R13ae): erwartete Zeilen gelesen, keine Luecke", text)


# ------------------------------------------------- 3) Der korrigierte Hinweistext
class TestTippfehler(unittest.TestCase):
    def test_hinweistext_schreibt_umschaltschwelle(self):
        text = uhr.preflight_hinweis(42.0, 80.0)
        self.assertIn("Preflight vor der Umschaltschwelle (42.0 von 80 min)", text)
        self.assertNotIn("Umschwellschwelle", text)
        self.assertNotIn("Umschwellschwelle", uhr.PREFLIGHT_HINWEIS)

    def test_auch_die_uebrige_ausgabe_schreibt_umschaltschwelle(self):
        """„Umschalten ab …" aus der BATCH-UHR - dieselbe Schreibweise."""
        self.assertIn("Umschalten ab", uhr.uhr_text(
            {"worker": {"started_at": "2026-09-30T10:00:00+00:00"}}, 90, 180,
            umschalt_min=80))


if __name__ == "__main__":
    unittest.main()
