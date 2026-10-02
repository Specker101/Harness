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

Der Test mit den **echten Werten** laeuft gegen den **eingefrorenen Stand**
`tests/fixtures/stand_b224` (R13bc) - frueher gegen die lebenden Dateien des Decomp-Repos,
mit `skipTest`, sobald der naechste Batch etwas schrieb.
"""

from __future__ import annotations

import inspect
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import bilanz, stand                                       # noqa: E402
from hx.config import load_config                                  # noqa: E402
from hx.util import ensure_dir, write_text_atomic                  # noqa: E402

# R13bc: der feste Stand (30.09.2026, B224) - eingefroren, nicht nachziehen (s. README).
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "stand_b224"
# Die Werte dieses Stands (gemessen mit `docs/_r13bc_fixture.py`).
# R13bn (M242-3): die BASIS des Medians hat gewechselt - er kommt jetzt wie das Mittel aus
# der lueckenlosen PREFLIGHT-Reihe (`c_trend`, TREND_FENSTER) statt aus den Zeilen der
# PLAN/IST-Tafel (die haengt an den kanonischen Bilanzdateien). Dieselben Fixture-DATEIEN
# ergeben damit fuenf statt drei Zuwaechse: +3 (B224), +3 (B222), +1 (B220), +5 (B219),
# +7 (B216) -> Median 3 (vorher 4 aus nur zwei Werten). Die Fixture selbst ist unveraendert.
STAND_TEXT = ("Median Zuwachs (Kopf-Batches): 3 | "
              "Mittel ueber alle C-Batches: 2,4")
STAND_QUELLE = ("Median der Zuwaechse der Kopf-Batches "
                "(+3 (B224), +3 (B222), +1 (B220), +5 (B219), +7 (B216))")
TEXT_219 = ("Median Zuwachs (Kopf-Batches): 6 | "
            "Mittel ueber alle C-Batches: 3,0")


class TestRateText(unittest.TestCase):
    """Die Zeile selbst - beide Werte mit ihrer Grundmenge im Namen (M221-5)."""

    def test_echte_werte(self):
        self.assertEqual(stand.rate_text(6.0, 3.0), TEXT_219)

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
        self.assertEqual(r["text"], TEXT_219)
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
        self.assertIn("C-Rate je C-Batch: " + TEXT_219, text)
        self.assertIn("-> 4 C-Batches bei +6.0 Koepfe je C-Batch", text)
        self.assertIn("Median der Zuwaechse der Kopf-Batches", text)
        self.assertNotIn("-> 9 C-Batches", text)

    def test_bilanz_block_nutzt_den_median(self):
        self.echter_fall()
        self.messdatei(219, 26, 2114)
        text = "\n".join(bilanz.gesamt_block(self.cfg))
        self.assertIn("C-Rate je C-Batch: " + TEXT_219, text)
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


class StandFixtureMixin:
    """Den eingefrorenen Stand in das Wegwerf-Verzeichnis der Basis kopieren (R13bc)."""

    def stand_laden(self) -> None:
        shutil.copytree(FIXTURE / "root", self.root, dirs_exist_ok=True)
        shutil.copytree(FIXTURE / "decomp", self.decomp, dirs_exist_ok=True)
        self.ana = self.decomp / "analysis"


class TestFesterStandB224(Basis, StandFixtureMixin):
    """Der feste Stand: neueste Messung, Datum, Vorher-Paar (R13ba-Nachtrag/R13bb Punkt 4)."""

    def setUp(self):
        super().setUp()
        self.stand_laden()
        self.m = stand.paket_e_messung(self.cfg)

    def test_neueste_messung_ist_b224_offen_20(self):
        self.assertEqual(self.m["datei"], "_m224/_c_paket_e_nachher.txt")
        self.assertEqual(self.m["batch"], 224)
        self.assertEqual((self.m["koepfe"], self.m["insn"]), (20, 1657))
        self.assertEqual(self.m["stand"], "nachher", "nachher schlaegt die blosse Messung")
        self.assertEqual(self.m["datum"], "2026-09-30 16:55")
        self.assertEqual(self.m["datum_quelle"], "kopf")
        self.assertEqual(self.m["kodierung"], "utf-8-bom")
        self.assertEqual(stand.paket_e_datum_hinweis(self.cfg), [])

    def test_vorher_paar_ist_nicht_verdreht(self):
        vor = self.m.get("vorher") or {}
        self.assertEqual((vor.get("batch"), vor.get("koepfe"), vor.get("insn")),
                         (222, 22, 1849))
        self.assertLess(vor["batch"], self.m["batch"], "das Paar ist nicht verdreht")
        self.assertEqual((self.m.get("vorher_gleich") or {}).get("datei"),
                         "_m224/_c_paket_e.txt")
        text = "\n".join(bilanz.gesamt_block(self.cfg))
        self.assertIn("(B222 -> B224: 2 Koepfe / 192 Insn gebaut)", text)
        self.assertNotIn("(B224 -> B222", text)

    def test_die_parser_meldung_haengt_an_dieser_funktion(self):
        """Die Review-Fakten rufen genau den Hinweis auf, der hier geprueft wird."""
        from hx.orchestrator import Orchestrator
        quelle = inspect.getsource(Orchestrator.harness_facts)
        self.assertIn("paket_e_datum_hinweis", quelle)
        self.assertEqual([z for z in stand.paket_e_datum_hinweis(self.cfg)
                          if "Messdatum" in z], [])


class TestFesterStandRate(Basis, StandFixtureMixin):
    """Die Rate des festen Stands - Median der Kopf-Batches, Mittel daneben."""

    def setUp(self):
        super().setUp()
        self.stand_laden()
        self.raten = stand.c_rate(self.cfg)

    def test_kopf_batches_und_median(self):
        # R13bn: fuenf Kopf-Batches statt zwei - die Grundmenge ist die Preflight-Reihe
        # des Trendfensters, nicht mehr die (lueckenhafte) PLAN/IST-Reihe.
        self.assertEqual(self.raten["kopf_batches"],
                         [(224, 3), (222, 3), (220, 1), (219, 5), (216, 7)])
        self.assertEqual(self.raten["median"], 3.0)
        self.assertEqual(self.raten["mittel"], 2.375)
        self.assertEqual(self.raten["rate"], self.raten["median"])
        self.assertEqual(self.raten["text"], STAND_TEXT)
        self.assertEqual(self.raten["quelle"], STAND_QUELLE)
        self.assertIn("Median", self.raten["quelle"])

    def test_durchsatzzeile_nennt_beide_grundmengen(self):
        text = "\n".join(stand.durchsatz_zeilen(self.cfg))
        self.assertIn("C-Rate je C-Batch: " + STAND_TEXT, text)
        self.assertIn("(Grundlage: " + STAND_QUELLE + ")", text)
        self.assertIn("offen (Paket E, C-Arbeitsvorrat): 20 Koepfe / 1657 Insn", text)
        self.assertIn("gemessen B224, 2026-09-30 16:55", text)

    def test_hochrechnung_rechnet_mit_dem_median(self):
        """Der Durchsatz-Block rechnet mit dem Median (nicht mit dem Mittel)."""
        text = "\n".join(stand.durchsatz_zeilen(self.cfg))
        # R13bn: 20 Koepfe offen bei Median 3 -> 7 C-Batches (vorher 5 bei Median 4).
        self.assertIn("-> 7 C-Batches bei +3.0 Koepfe je C-Batch", text)
        self.assertIn("(Grundlage: " + STAND_QUELLE + ")", text)
        self.assertNotIn("-> 9 C-Batches", text)         # der alte Mittel-Wert (2,4)

    def test_tafel_zeigt_beide_zahlen(self):
        """Die PLAN/IST-Tafel zeigt dieselbe Rate wie der Durchsatz-Block (R13bn)."""
        text = stand.plan_ist_text(self.cfg, 12)
        self.assertIn("MEDIAN der 5 Zuwaechse", text)
        self.assertIn("(Median Zuwachs (Kopf-Batches): 3 | "
                      "Mittel ueber alle C-Batches: 2,4)", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
