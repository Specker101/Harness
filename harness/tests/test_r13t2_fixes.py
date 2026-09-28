"""Tests fuer R13t2 (2026-09-28): drei Arbeitsvorrat-Klassen + Aufnahme-Zeile in /bilanz.

Auftrag (Nutzer):
  4. "/bilanz: C-Arbeitsvorrat in drei Klassen getrennt zaehlen, je mit Hochrechnung:
      (1) in den Aufnahmen ausgefuehrt, noch nicht gebaut/nicht verifiziert,
      (2) nicht ausgefuehrt, aber Paket E,
      (3) nicht ausgefuehrt, Rest. Klasse 3 heisst 'in vorhandenen Aufnahmen nicht
      ausgefuehrt' (nicht 'unnoetig') ... Zusaetzlich eine Zeile: welche Aufnahmen die
      Coverage abdeckt (Szenen/Laenge)."

Die Zahlen selbst kommen aus dem Cache `docs/_port_relevanz.json`
(`tools/r13t_cov_relevanz.py`); hier wird die ANZEIGE geprueft - inklusive der Faelle
"kein Cache" und "Cache ohne Klassen" (dann bleibt die abgeleitete Zeile stehen).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import stand                                        # noqa: E402
from hx.config import load_config                           # noqa: E402
from hx.util import ensure_dir, write_json_atomic, write_text_atomic  # noqa: E402

BILANZ = """# Bilanz B206

| Bilanzzeile | Vorbatch (B205) | Heute (B206) | Werkzeug |
|---|---|---|---|
| **R207 rueckwaerts** | **681** (a 30/b 0/c 0) | **686** (a 30/b 0/c 0) | `preflight.py` |
"""

DOKU = """# Batch 206

| Bilanzzeile | Vorbatch (B205) | **Soll B206** | Zaehlerdefinition |
|---|---|---|---|
| Paket E offen | 43 Koepfe / 3025 Insn (Bl 20 / 1434) | **38 / 2674 (Bl 15 / 1083)** | `c_kopf.py paket_e` |
"""

KLASSEN = {
    "1_ausgefuehrt_nicht_gebaut": {"koepfe": 677, "insn": 28976},
    "2_nicht_ausgefuehrt_paket_e": {"koepfe": 1, "insn": 38},
    "3_nicht_ausgefuehrt_rest": {"koepfe": 725, "insn": 24521},
}


def _weg(p: Path) -> None:
    if not p.exists():
        return
    for k in sorted(p.rglob("*"), reverse=True):
        k.unlink() if k.is_file() else k.rmdir()
    p.rmdir()


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__file__).resolve().parent / "_tmp_r13t2"
        _weg(self.tmp)
        self.root = ensure_dir(self.tmp / "harness")
        self.decomp = ensure_dir(self.tmp / "decomp")
        self.ana = ensure_dir(self.decomp / "analysis")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.decomp)
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["paths"].pop("harness_home", None)
        self.cfg = cfg
        d = ensure_dir(self.ana / "_m206")
        write_text_atomic(d / "_bilanz206.txt", BILANZ)
        write_text_atomic(self.ana / "port-batch206-x-2026-09-28.md", DOKU)

    def tearDown(self):
        _weg(self.tmp)

    def cache(self, klassen=True, **werte) -> None:
        daten = {"erzeuger": "tools/r13t_cov_relevanz.py", "ts": "2026-09-28 03:00",
                 "fenster": "Rumpf", "inventar": 2072, "ausgefuehrt": 1086,
                 "gebaut": 686, "gebaut_ausgefuehrt": 416, "verifiziert": 78,
                 "verifiziert_ausgefuehrt": 56, "paket_e_wurzeln": 86,
                 "paket_e_wurzeln_ausgefuehrt": 66, "paket_e_blaetter": 17,
                 "paket_e_blaetter_ausgefuehrt": 12}
        if klassen:
            daten.update({"klassen": KLASSEN, "paket_e_huelle": 265,
                          "paket_e_huelle_offen": 28,
                          "aufnahmen": {"beschreibung": "Gameplay + Boot+Attract",
                                        "quelle": "analysis/f5-descr-batch42.md:87-88"}})
        daten.update(werte)
        write_json_atomic(ensure_dir(self.tmp / "docs") / "_port_relevanz.json", daten)


class TestKlassen(Basis):
    def test_drei_klassen_mit_hochrechnung(self):
        self.cache()
        text = "\n".join(stand.durchsatz_zeilen(self.cfg))
        self.assertIn("C-Arbeitsvorrat: 1403 Koepfe nicht gebaut", text)
        self.assertIn("(1) ausgefuehrt, noch nicht gebaut", text)
        self.assertIn("677 Koepfe /  28976 Insn", text)
        self.assertIn("(2) nicht ausgefuehrt, Paket E", text)
        self.assertIn("(3) nicht ausgefuehrt, sonstiger Rest", text)
        # Hochrechnung mit dem Mittel aus der Bilanzdatei (hier +5 -> 677/5 = 135)
        self.assertIn("-> ca. 135 Batches", text)

    def test_klasse_3_wird_als_aufnahme_luecke_ausgewiesen(self):
        self.cache()
        text = "\n".join(stand.durchsatz_zeilen(self.cfg))
        self.assertIn('NICHT "unnoetig"', text)
        self.assertIn("Boot + einen Teil von Level 1", text)
        self.assertIn("eigene Nachrechnung: 265 Koepfe, davon offen 28", text)

    def test_aufnahme_zeile(self):
        self.cache()
        text = "\n".join(stand.durchsatz_zeilen(self.cfg))
        self.assertIn("Aufnahmen    : Gameplay + Boot+Attract", text)
        self.assertIn("analysis/f5-descr-batch42.md:87-88", text)

    def test_c_gesamt_nimmt_die_gemessene_summe(self):
        self.cache()
        text = "\n".join(stand.durchsatz_zeilen(self.cfg))
        self.assertIn("HYPOTHESIS (C gesamt, GEMESSEN): offen 1403 Koepfe / 53535 Insn", text)
        self.assertNotIn("ABGELEITET", text)

    def test_ohne_klassen_bleibt_die_abgeleitete_zeile(self):
        self.cache(klassen=False)
        text = "\n".join(stand.durchsatz_zeilen(self.cfg))
        self.assertNotIn("Koepfe nicht gebaut", text)
        # kein Cache und kein Dokument mit "OFFEN: <K> Koepfe / <I> Insn" -> ehrliche Meldung
        self.assertIn("HYPOTHESIS (C gesamt): nicht ermittelbar", text)

    def test_ohne_cache_kein_raten(self):
        text = "\n".join(stand.durchsatz_zeilen(self.cfg))
        self.assertIn("Port-Relevanz: nicht gemessen", text)
        self.assertNotIn("Koepfe nicht gebaut", text)
        self.assertNotIn("Aufnahmen    :", text)


if __name__ == "__main__":
    unittest.main()
