"""Tests fuer R13ba (2026-09-30): eine Rate "Koepfe je C-Batch" fuer alle Hochrechnungen.

**Auftrag (Nutzer, nach Aussensicht-Befund M221-5 und der Frage aus dem Review B222).**
Die Rate "Koepfe je C-Batch" wurde an zwei Stellen mit zwei Grundmengen gebildet:
die PLAN/IST-Tafel nahm den **Median der Zuwaechse der C-Batches mit SOLL-KOEPFE > 0**
(real +7 (B216), +5 (B219) -> **6**), die Durchsatzzeile der BILANZ das **Mittel ueber
alle C-Batches** (+0, +0, +7, +5 -> **3.0**). Derselbe Restvorrat (26 Koepfe) ergab damit
"9 C-Batches" gegen "etwa 5 C-Batches".

Jetzt:

* `stand.c_rate` bildet **beide** Zahlen mit ihrer Grundmenge und liefert sie
  nebeneinander: `Median Zuwachs (Kopf-Batches): 6 | Mittel ueber alle C-Batches: 3,0`.
* **Gerechnet wird mit dem Median** - in der Paket-E-Hochrechnung, in der
  C-gesamt-Hochrechnung und in der Klasse "nicht gebaut" (`kalender_zeilen`,
  `_relevanz_zeilen`).
* Faellt der Median aus (kein Kopf-Batch im Fenster), tritt das Mittel an seine Stelle;
  `quelle` sagt, welche der beiden Zahlen gerechnet wurde.

Der Test mit den **echten Werten** laeuft gegen das Decomp-Repo (nur lesend) und
ueberspringt sich, wenn die echten Kopf-Batches weitergezogen sind.
"""

from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import bilanz, stand                                       # noqa: E402
from hx.config import load_config                                  # noqa: E402
from hx.util import ensure_dir, write_text_atomic                  # noqa: E402

ECHTER_CFG = load_config()
DEC = Path(ECHTER_CFG.decomp)
ECHTER_STAND = stand.c_rate(ECHTER_CFG)
ECHTER_MESSUNG = stand.paket_e_messung(ECHTER_CFG)
# Die echten Kopf-Batches vom 30.09.2026: B216 (+7), B219 (+5).
ECHTER_MEDIAN = 6
ECHTER_TEXT = ("Median Zuwachs (Kopf-Batches): 6 | "
               "Mittel ueber alle C-Batches: 3,0")


class TestRateText(unittest.TestCase):
    """Die Zeile selbst - beide Werte mit ihrer Grundmenge im Namen (M221-5)."""

    def test_echte_werte(self):
        self.assertEqual(stand.rate_text(6.0, 3.0), ECHTER_TEXT)

    def test_beide_grundmengen_werden_genannt(self):
        t = stand.rate_text(6.0, 3.0)
        self.assertIn("Median Zuwachs (Kopf-Batches)", t)
        self.assertIn("Mittel ueber alle C-Batches", t)
        self.assertIn(" | ", t)

    def test_krummes_mittel_mit_komma(self):
        self.assertIn("Mittel ueber alle C-Batches: 3,5", stand.rate_text(6.0, 3.5))
        self.assertIn("Mittel ueber alle C-Batches: 3,2", stand.rate_text(6.0, 3.25))

    def test_ohne_messung_ausdruecklich(self):
        t = stand.rate_text(None, None)
        self.assertEqual(t.count("nicht gemessen"), 2)

    def test_nur_mittel_ist_lesbar(self):
        self.assertIn("Median Zuwachs (Kopf-Batches): nicht gemessen",
                      stand.rate_text(None, 3.0))


class Basis(unittest.TestCase):
    """Wegwerf-Harness mit Wegwerf-Decomp-Repo (wie test_r13ay)."""

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13ba"
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

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def bilanzdatei(self, n: int, vorher: int, heute: int) -> None:
        """Kanonische Bilanzdatei (`_m<N>/_bilanz<N>.txt`, Zeile `R207 rueckwaerts`)."""
        d = ensure_dir(self.ana / f"_m{n}")
        write_text_atomic(d / f"_bilanz{n}.txt",
                          "| Ast | Vorbatch | heute |\n"
                          f"| **R207 rueckwaerts** | **{vorher}** (a 30) | "
                          f"**{heute}** (a 30) |\n")

    def preflight(self, n: int, ck: int) -> None:
        write_text_atomic(self.ana / f"_preflight_{n}.txt",
                          "Pruefung           Ergebnis              Urteil\n"
                          f"C Koepfe           {ck} / 4833 / 0        OK\n")

    def auftrag(self, n: int, soll: int | None) -> None:
        """Die Instruktion des Batches - `SOLL-KOEPFE: <k>` macht ihn zum Kopf-Batch."""
        d = ensure_dir(self.root / "runs" / f"b{n}")
        write_text_atomic(d / "auftrag.md",
                          "TEIL 3\n" + (f"SOLL-KOEPFE: {soll}\n"
                                        if soll is not None else "irgendwas\n"))

    def dokument(self, n: int) -> None:
        write_text_atomic(self.ana / f"port-batch{n}-attrappe.md",
                          "# Batch\n\n| Zeile | Zaehlerdefinition | Soll | Ist | "
                          "Abweichung |\n|---|---|---|---|---|\n"
                          "| **C Koepfe** | `c_kopf.py` | 78 / 2903 / 0 | "
                          "**78 / 2903 / 0** | 0 |\n")

    def messdatei(self, n: int, koepfe: int, insn: int, stand: str = "nachher",
                  datum: str | None = "2026-09-30 03:33", form: str = "messung") -> None:
        """Eine Paket-E-Messung, wie sie im Repo liegt.

        `form="messung"` -> `# Messung: <datum>` (so schreibt B219), `form="vorher-kopf"`
        -> `# PAKET-E-STAND VORHER - Batch <n>, Datum <datum>` (so liegt B222);
        `datum=None` -> **kein** Datum im Kopf (die blosse B222-Datei).
        """
        d = ensure_dir(self.ana / f"_m{n}")
        name = f"_c_paket_e_{stand}.txt" if stand else "_c_paket_e.txt"
        if datum and form == "messung":
            kopf = f"# Messung: {datum}, HEAD 5b7eaf6\n"
        elif datum:
            kopf = f"# PAKET-E-STAND VORHER - Batch {n}, Datum {datum}, HEAD babf57c\n"
        else:
            kopf = "# Batch 198 (C) TEIL 1 - PAKET E GEMESSEN (offline, R398)\n"
        write_text_atomic(d / name, kopf + "# Erzeuger: python scripts/c_kopf.py paket_e\n"
                          "== ERGEBNIS ==\n"
                          f"  Paket E, offen GESAMT   :   {koepfe} Koepfe / "
                          f"  {insn} Insn\n")

    def echter_fall(self) -> None:
        """Der gemessene Fall vom 30.09.2026: 4 C-Batch-Schritte 0/0/+7/+5, zwei Kopf-Batches."""
        for n, ck in ((215, 78), (216, 85), (217, 85), (218, 85), (219, 90)):
            self.preflight(n, ck)
            self.bilanzdatei(n, 600 + n, 686 + n)
            self.dokument(n)
        self.auftrag(216, 7)
        self.auftrag(219, 5)


class TestRateAusDenDaten(Basis):
    """`c_rate`: Median ueber die Kopf-Batches, Mittel ueber ALLE C-Batches."""

    def test_beide_zahlen_aus_demselben_fall(self):
        self.echter_fall()
        r = stand.c_rate(self.cfg, 5)
        self.assertEqual(r["median"], 6, "Zuwaechse +7 (B216) und +5 (B219)")
        self.assertEqual(r["mittel"], 3.0, "0, 0, +7, +5 ueber alle C-Batch-Schritte")
        self.assertEqual(r["rate"], 6, "gerechnet wird mit dem Median")
        self.assertEqual(r["text"], ECHTER_TEXT)
        self.assertIn("+5 (B219)", r["quelle"])
        self.assertIn("+7 (B216)", r["quelle"])

    def test_median_nutzt_nur_kopf_batches(self):
        self.echter_fall()
        r = stand.c_rate(self.cfg, 5)
        self.assertEqual(sorted(b for b, _d in r["kopf_batches"]), [216, 219])
        self.assertEqual(dict(r["kopf_batches"]), {216: 7, 219: 5})

    def test_batch_ohne_soll_zaehlt_nicht_mit(self):
        """Ein C-Batch mit `SOLL-KOEPFE: 0` hat einen Zuwachs, ist aber kein Kopf-Batch."""
        self.echter_fall()
        self.auftrag(218, 0)
        r = stand.c_rate(self.cfg, 5)
        self.assertEqual([b for b, _d in r["kopf_batches"]], [219, 216])
        self.assertEqual(r["median"], 6)

    def test_ohne_kopf_batch_kein_median_aber_mittel(self):
        self.echter_fall()
        self.auftrag(216, None)
        self.auftrag(219, None)
        r = stand.c_rate(self.cfg, 5)
        self.assertIsNone(r["median"])
        self.assertEqual(r["mittel"], 3.0)
        self.assertEqual(r["rate"], 3.0, "Rueckfall auf das Mittel")
        self.assertIn("Mittel ueber alle C-Batches", r["quelle"])
        self.assertIn("nicht gemessen", r["text"])

    def test_ohne_vorgaengerwert_kein_median(self):
        self.preflight(219, 90)
        self.bilanzdatei(219, 681, 686)
        self.dokument(219)
        self.auftrag(219, 5)
        r = stand.c_rate(self.cfg, 5)
        self.assertIsNone(r["median"])
        self.assertEqual(r["text"], "Median Zuwachs (Kopf-Batches): nicht gemessen | "
                                    "Mittel ueber alle C-Batches: nicht gemessen")


class TestHochrechnungNutztDenMedian(Basis):
    """Die Paket-E-Hochrechnung rechnet mit dem Median, nicht mit dem Mittel."""

    def test_median_ergeben_vier_c_batches(self):
        d = {"rate_c_koepfe": 6.0,
             "rate_c_quelle": "Median der Zuwaechse der Kopf-Batches (+5 (B219), +7 (B216))",
             "c_fenster": [{"batch": 219}, {"batch": 216}],
             "anteil_c": 1 / 3, "anteil_quelle": "Regel hybrid-plan.md: \"2 B : 1 C\""}
        zeilen = stand.kalender_zeilen(self.cfg, 26, d)
        self.assertIn("-> 4 C-Batches bei +6.0 Koepfe je C-Batch", zeilen[0])
        self.assertIn("Median der Zuwaechse der Kopf-Batches", zeilen[0])
        self.assertNotIn("9 C-Batches", zeilen[0])

    def test_das_mittel_ist_nur_rueckfall_und_wird_benannt(self):
        """Ohne `rate_c_koepfe` (kein Median) gilt das Mittel - der Anlassfall von M221-5."""
        d = {"mittel_c_koepfe": 3.0, "mittel_c_quelle": "Preflight-Messung: C Koepfe "
                                                       "je C-Batch B209..B221",
             "c_fenster": [], "anteil_c": 1 / 3, "anteil_quelle": "Regel hybrid-plan.md"}
        zeilen = stand.kalender_zeilen(self.cfg, 26, d)
        self.assertIn("-> 9 C-Batches bei +3.0 Koepfe je C-Batch", zeilen[0])
        self.assertIn("Preflight-Messung", zeilen[0])

    def test_ohne_rate_keine_hochrechnung(self):
        self.assertEqual(stand.kalender_zeilen(self.cfg, 26, {}), [])

    def test_durchsatzzeile_zeigt_beide_grundmengen(self):
        """`durchsatz_zeilen` holt die Rate selbst (`c_rate`) - der Aufrufer muss nichts setzen."""
        self.echter_fall()
        self.messdatei(219, 26, 2114)
        text = "\n".join(stand.durchsatz_zeilen(self.cfg, 5))
        self.assertIn("C-Rate je C-Batch: " + ECHTER_TEXT, text)
        self.assertIn("-> 4 C-Batches bei +6.0 Koepfe je C-Batch", text)
        self.assertIn("Median der Zuwaechse der Kopf-Batches", text)
        self.assertNotIn("-> 9 C-Batches", text)

    def test_bilanz_block_nutzt_den_median(self):
        self.echter_fall()
        self.messdatei(219, 26, 2114)
        text = "\n".join(bilanz.gesamt_block(self.cfg))
        self.assertIn("C-Rate je C-Batch: " + ECHTER_TEXT, text)
        self.assertIn("bei +6.0 Koepfe je C-Batch", text)
        self.assertNotIn("bei +3.0 Koepfe je C-Batch", text)


class TestAuswahlDerMessdatei(Basis):
    """R13ba-Nachtrag: Batchnummer zuerst, `nachher` vor der blossen Messung vor `vorher`;
    das Datum ist Anzeige und Gleichstand-Entscheider - nie Hauptkriterium."""

    def test_batchnummer_schlaegt_das_datum(self):
        """B222 ohne Datum gegen B219 mit Datum - B222 gewinnt (der alte Fehler)."""
        self.messdatei(219, 26, 2114, stand="nachher")
        self.messdatei(222, 25, 2011, stand="", datum=None)
        m = stand.paket_e_messung(self.cfg)
        self.assertEqual((m["batch"], m["koepfe"]), (222, 25))
        self.assertEqual(m["datei"], "_m222/_c_paket_e.txt")
        self.assertEqual(m["datum_quelle"], "dateizeit")

    def test_datum_der_b222_form_wird_gelesen(self):
        """`# PAKET-E-STAND VORHER - Batch 222, Datum 2026-09-30, HEAD …`."""
        self.messdatei(222, 25, 2011, stand="vorher", datum="2026-09-30",
                       form="vorher-kopf")
        m = stand.paket_e_messung(self.cfg)
        self.assertEqual(m["datum"], "2026-09-30")
        self.assertEqual(m["datum_quelle"], "kopf")
        self.assertTrue(m["kopf"])

    def test_datum_der_b219_form_wird_gelesen(self):
        """`# Messung: 2026-09-30 03:33, HEAD …`."""
        self.messdatei(219, 26, 2114, stand="nachher")
        m = stand.paket_e_messung(self.cfg)
        self.assertEqual(m["datum"], "2026-09-30 03:33")
        self.assertEqual(m["datum_quelle"], "kopf")

    def test_nachher_vor_bloss_und_bloss_vor_vorher(self):
        """Innerhalb eines Batches entscheidet der Name - auch gegen ein spaeteres Datum."""
        self.messdatei(219, 26, 2114, stand="nachher", datum="2026-09-30 03:33")
        self.messdatei(219, 30, 2200, stand="", datum="2026-09-30 09:00")
        self.messdatei(219, 31, 2210, stand="vorher", datum="2026-09-30 10:00")
        self.assertEqual((stand.paket_e_messung(self.cfg)["stand"],
                          stand.paket_e_messung(self.cfg)["koepfe"]), ("nachher", 26))
        # Ohne die `nachher`-Datei gewinnt die blosse Messung gegen `vorher`.
        (self.ana / "_m219" / "_c_paket_e_nachher.txt").unlink()
        m = stand.paket_e_messung(self.cfg)
        self.assertEqual((m["stand"], m["koepfe"]), ("", 30))

    def test_datum_entscheidet_bei_gleichem_rang(self):
        """Gleichstand: zwei Messungen desselben Batches ohne `nachher`/`vorher` - das
        spaetere Datum gewinnt."""
        self.messdatei(219, 26, 2114, stand="", datum="2026-09-30 03:33")
        write_text_atomic(self.ana / "_m219" / "_c_paket_e_zweit.txt",
                          "# Messung: 2026-09-30 07:10, HEAD 5b7eaf6\n"
                          "  Paket E, offen GESAMT   :   24 Koepfe /   1990 Insn\n")
        m = stand.paket_e_messung(self.cfg)
        self.assertEqual((m["koepfe"], m["datum"]), (24, "2026-09-30 07:10"))

    def test_kein_verdrehtes_vorher_paar(self):
        """Die Fixture des echten Falls: B219/_nachher 26, B222/_vorher 25."""
        self.messdatei(219, 26, 2114, stand="nachher")
        self.messdatei(222, 25, 2011, stand="vorher", datum="2026-09-30",
                       form="vorher-kopf")
        m = stand.paket_e_messung(self.cfg)
        self.assertEqual((m["batch"], m["koepfe"]), (222, 25))
        vor = m["vorher"]
        self.assertEqual((vor["batch"], vor["koepfe"]), (219, 26))
        self.assertLess(vor["batch"], m["batch"], "das Paar ist nicht verdreht")
        text = "\n".join(bilanz.gesamt_block(self.cfg))
        self.assertIn("(B219 -> B222: 1 Koepfe / 103 Insn gebaut)", text)
        self.assertNotIn("(B222 -> B219", text)

    def test_parser_hinweis_bei_fehlendem_datum(self):
        self.messdatei(222, 25, 2011, stand="", datum=None)
        hinweis = stand.paket_e_datum_hinweis(self.cfg)
        self.assertEqual(len(hinweis), 1, hinweis)
        self.assertTrue(hinweis[0].startswith(
            "PARSER: Messdatum in _m222/_c_paket_e.txt nicht erkannt"), hinweis[0])
        text = "\n".join(bilanz.gesamt_block(self.cfg))
        self.assertIn("(Datum aus Dateizeit)", text)
        self.assertIn("gemessen B222, ", text)

    def test_kein_hinweis_wenn_das_datum_im_kopf_steht(self):
        self.messdatei(222, 25, 2011, stand="vorher", datum="2026-09-30",
                       form="vorher-kopf")
        self.assertEqual(stand.paket_e_datum_hinweis(self.cfg), [])
        self.assertNotIn("Dateizeit", "\n".join(bilanz.gesamt_block(self.cfg)))

    def test_paket_e_datum_formen(self):
        self.assertEqual(stand.paket_e_datum("# Messung: 2026-09-30 03:33, HEAD x"),
                         ("2026-09-30 03:33", "kopf"))
        self.assertEqual(stand.paket_e_datum("# PAKET-E-STAND VORHER - Batch 222, "
                                             "Datum 2026-09-30, HEAD x"),
                         ("2026-09-30", "kopf"))
        self.assertEqual(stand.paket_e_datum("# nichts hier", 0.0), ("", ""))
        # Ein Datum WEIT unten in der Datei zaehlt nicht - es wird nur der Kopf gelesen.
        tief = "\n".join(["# ohne Datum"] + ["x"] * 20
                          + ["# Messung: 2026-09-30 03:33"])
        self.assertEqual(stand.paket_e_datum(tief, 0.0)[1], "")


class TestEchteDateienB222(unittest.TestCase):
    """Die echten Dateien aus dem Auftrag (nur lesend; skip, wenn das Repo weiterzieht)."""

    def test_m222_gewinnt_offen_25_ohne_verdrehtes_paar(self):
        m = ECHTER_MESSUNG
        if int(m.get("batch") or 0) < 222:
            self.skipTest(f"keine Messung ab B222: {m.get('datei')}")
        self.assertEqual(m["batch"], 222)
        self.assertIn("_m222/", m["datei"], "die neueste Messung liegt in _m222")
        self.assertEqual(m["koepfe"], 25)
        self.assertEqual(m["insn"], 2011)
        vor = m.get("vorher") or {}
        self.assertLess(vor.get("batch") or 0, 222, "das Paar ist nicht verdreht")
        self.assertGreaterEqual(vor.get("koepfe", 0) - m["koepfe"], 0,
                                "der offene Vorrat kann nicht negativ 'gebaut' werden")
        text = "\n".join(bilanz.gesamt_block(ECHTER_CFG))
        self.assertNotIn("(B222 -> B219", text)
        self.assertIn(f"(B{vor['batch']} -> B222: {vor['koepfe'] - m['koepfe']} Koepfe /",
                      text)

    def test_echte_datei_ohne_datum_wird_gekennzeichnet(self):
        m = ECHTER_MESSUNG
        if int(m.get("batch") or 0) < 222:
            self.skipTest(f"keine Messung ab B222: {m.get('datei')}")
        hinweis = stand.paket_e_datum_hinweis(ECHTER_CFG)
        if m["datum_quelle"] != "dateizeit":
            self.assertEqual(hinweis, [])
            return
        self.assertTrue(hinweis and "PARSER: Messdatum in" in hinweis[0], hinweis)
        self.assertIn("(Datum aus Dateizeit)", "\n".join(bilanz.gesamt_block(ECHTER_CFG)))


class TestEchteWerte(unittest.TestCase):
    """Gegen das Decomp-Repo (nur lesend) - echte Zahlen vom 30.09.2026."""

    def test_rate_ist_der_median_der_kopf_batches(self):
        if not ECHTER_STAND.get("median"):
            self.skipTest("kein Kopf-Batch im echten Fenster")
        self.assertEqual(ECHTER_STAND["rate"], ECHTER_STAND["median"])
        self.assertIn("Median", ECHTER_STAND["quelle"])

    def test_echte_kopf_batches(self):
        """B216 (+7) und B219 (+5) - der Median ist 6, das Mittel ueber alle 3.0."""
        if dict(ECHTER_STAND["kopf_batches"]) != {216: 7, 219: 5}:
            self.skipTest("die echten Kopf-Batches sind weitergezogen: "
                          f"{ECHTER_STAND['kopf_batches']}")
        self.assertEqual(ECHTER_STAND["median"], ECHTER_MEDIAN)
        self.assertEqual(ECHTER_STAND["mittel"], 3.0)
        self.assertEqual(ECHTER_STAND["text"], ECHTER_TEXT)

    def test_echte_durchsatzzeile(self):
        text = "\n".join(stand.durchsatz_zeilen(ECHTER_CFG))
        self.assertIn("C-Rate je C-Batch: " + ECHTER_STAND["text"], text)
        # Die Hochrechnung nennt dieselbe Grundmenge wie die Rate.
        self.assertIn("(Grundlage: " + ECHTER_STAND["quelle"] + ")", text)

    def test_echte_hochrechnung_ist_der_median(self):
        d = stand.durchsatz(ECHTER_CFG)
        raten = stand.c_rate(ECHTER_CFG)
        if not d.get("offen_koepfe") or not raten.get("rate"):
            self.skipTest("kein offener Vorrat oder keine Rate gemessen")
        erwartet = d["offen_koepfe"] / raten["rate"]
        zeilen = stand.kalender_zeilen(ECHTER_CFG, d["offen_koepfe"],
                                       {"rate_c_koepfe": raten["rate"],
                                        "rate_c_quelle": raten["quelle"]})
        self.assertIn(f"-> {erwartet:.0f} C-Batches bei +{raten['rate']:.1f} Koepfe "
                      "je C-Batch", zeilen[0])

    def test_echte_tafel_zeigt_beide_zahlen(self):
        text = stand.plan_ist_text(ECHTER_CFG)
        if "MEDIAN: nicht gemessen" in text:
            self.skipTest("kein Kopf-Batch im echten Fenster")
        self.assertIn(ECHTER_STAND["text"], text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
