"""Tests fuer R13ay (2026-09-30): die zwei Kennzahlen aus Aussensicht-Befund M219-3.

**Auftrag (Gewicht mittel, Empfaenger Reviewer).** Beleg: die BILANZ rechnete mit
„offen (Paket E) 38 Koepfe / 2674 Insn → 13 C-Batches" aus `port-batch208-hybrid-kern-…md:214`,
waehrend gemessen **26 / 2114** waren (`analysis/_m219/_c_paket_e_nachher.txt:127`;
38 − 7 (B216) − 5 (B219) = 26). Dazu war der „MEDIAN … 88 Koepfe" ein Median von SUMMEN,
nicht von Zuwaechsen - der Reviewer hatte ihn in `b219/review.md` von Hand korrigiert.

Zwei Aenderungen:

* **Paket E offen** kommt aus der juengsten **Messung** `analysis/_m<N>/_c_paket_e*.txt`
  (mit Datum aus dem Dateikopf, `stand.paket_e_messung`); fehlt sie, steht ausdruecklich
  „nicht gemessen seit B<k>".
* Der **SOLL-KOEPFE-Median** wird ueber die **Zuwaechse** der C Koepfe je C-Batch gebildet
  (`c_delta`), nicht ueber die Gesamtzahl.

Der Test mit den **echten Werten** laeuft gegen das Decomp-Repo (nur lesend) und wird
uebersprungen, wenn die Dateien fehlen.
"""

from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import bilanz, stand                                        # noqa: E402
from hx.config import load_config                                   # noqa: E402
from hx.util import ensure_dir, write_text_atomic                   # noqa: E402

ECHTER_CFG = load_config()
DEC = Path(ECHTER_CFG.decomp)
# Die echten Messdateien (B219 = heute, B210 = der letzte andere Stand).
ECHT_219 = DEC / "analysis" / "_m219" / "_c_paket_e_nachher.txt"
ECHT_210 = DEC / "analysis" / "_m210" / "_c_paket_e.txt"


def messdatei(ana: Path, batch: int, koepfe: int, insn: int, stand: str = "nachher",
              datum: str = "2026-09-30 03:33") -> Path:
    """Eine Paket-E-Messung schreiben, wie `c_kopf.py paket_e` sie ablegt."""
    d = ensure_dir(ana / f"_m{batch}")
    zusatz = f"_{stand}" if stand else ""
    p = d / f"_c_paket_e{zusatz}.txt"
    write_text_atomic(p, f"# Batch {batch} TEIL 2 - PAKET E, Stand {stand or 'gemessen'}\n"
                         f"# Messung: {datum}, HEAD 5b7eaf6, python scripts/c_kopf.py "
                         "paket_e\n"
                         "# Batch 198 (C) TEIL 1 - PAKET E GEMESSEN (offline, R398)\n"
                         "== ERGEBNIS ==\n"
                         f"  Paket E, offen GESAMT   :   {koepfe} Koepfe /   {insn} Insn\n")
    return p


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13ay"
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


class TestPaketEMessung(Basis):
    def test_liest_koepfe_insn_datum_und_batch(self):
        messdatei(self.ana, 219, 26, 2114)
        m = stand.paket_e_messung(self.cfg)
        self.assertEqual(m["koepfe"], 26)
        self.assertEqual(m["insn"], 2114)
        self.assertEqual(m["batch"], 219)
        self.assertEqual(m["datum"], "2026-09-30 03:33")
        self.assertEqual(m["datei"], "_m219/_c_paket_e_nachher.txt")
        self.assertEqual(m["zeile"], 5)
        self.assertTrue(m["kopf"])

    def test_juengste_messung_gewinnt(self):
        messdatei(self.ana, 210, 38, 2674, stand="", datum="")
        messdatei(self.ana, 219, 26, 2114)
        m = stand.paket_e_messung(self.cfg)
        self.assertEqual((m["koepfe"], m["batch"]), (26, 219))

    def test_nachher_gewinnt_bei_gleichem_datum(self):
        """GEMESSEN B219: `_vorher` und `_nachher` tragen dasselbe Datum und denselben
        HEAD (Befund M219-4) - dann entscheidet der Dateiname."""
        messdatei(self.ana, 219, 30, 2200, stand="vorher")
        messdatei(self.ana, 219, 26, 2114, stand="nachher")
        m = stand.paket_e_messung(self.cfg)
        self.assertEqual(m["stand"], "nachher")
        self.assertEqual(m["koepfe"], 26)

    def test_vorgaenger_ist_die_naechstaeltere_andere_messung(self):
        messdatei(self.ana, 210, 38, 2674, stand="", datum="")
        messdatei(self.ana, 219, 26, 2114)
        m = stand.paket_e_messung(self.cfg)
        self.assertEqual((m["vorher"]["koepfe"], m["vorher"]["batch"]), (38, 210))

    def test_ohne_messung_leer(self):
        self.assertEqual(stand.paket_e_messung(self.cfg), {})

    def test_dateiname_ohne_m_ordner_zaehlt_nicht(self):
        """Nur `_m<N>/_c_paket_e*.txt` ist eine Messung - `_archiv/` ist es nicht."""
        d = ensure_dir(self.ana / "_archiv")
        write_text_atomic(d / "_c_paket_e.007.19cc46a8.txt",
                          "== ERGEBNIS ==\n  Paket E, offen GESAMT   :   26 Koepfe / "
                          "2114 Insn\n")
        self.assertEqual(stand.paket_e_messung(self.cfg), {})

    def test_text_mit_und_ohne_messung(self):
        messdatei(self.ana, 219, 26, 2114)
        text = stand.paket_e_offen_text(stand.paket_e_messung(self.cfg))
        self.assertIn("26 Koepfe / 2114 Insn", text)
        self.assertIn("gemessen B219, 2026-09-30 03:33", text)
        self.assertIn("_m219/_c_paket_e_nachher.txt", text)
        ohne = stand.paket_e_offen_text(None, 208)
        self.assertIn("nicht gemessen seit B208", ohne)
        self.assertIn("keine Datei analysis/_m*/_c_paket_e*.txt", ohne)


class TestDurchsatzUndBilanz(Basis):
    def bilanzdatei(self, n: int, vorher: int, heute: int) -> None:
        """Kanonische Bilanzdatei (`_m<N>/_bilanz<N>.txt`, Zeile `R207 rueckwaerts`)."""
        d = ensure_dir(self.ana / f"_m{n}")
        write_text_atomic(d / f"_bilanz{n}.txt",
                          "| Ast | Vorbatch | heute |\n"
                          f"| **R207 rueckwaerts** | **{vorher}** (a 30) | "
                          f"**{heute}** (a 30) |\n")

    def dokument(self, n: int, pek: int = 38, pei: int = 2674) -> None:
        """Ein Batch-Dokument mit der (veralteten) Soll/Ist-Zeile `Paket E offen`."""
        write_text_atomic(self.ana / f"port-batch{n}-attrappe.md",
                          "# Batch\n\n| Zeile | Zaehlerdefinition | Soll | Ist | Abweichung |\n"
                          "|---|---|---|---|---|\n"
                          "| Paket E offen | `c_kopf.py paket_e` | 43 / 3025 "
                          f"(Bl 20 / 1434) | **{pek} / {pei} (Bl 17 / 1202)** | 5 |\n")

    def test_offener_vorrat_kommt_aus_der_messung(self):
        self.dokument(208)
        self.bilanzdatei(208, 681, 686)
        messdatei(self.ana, 219, 26, 2114)
        d = stand.durchsatz(self.cfg)
        self.assertEqual(d["offen_koepfe"], 26)
        self.assertEqual(d["offen_insn"], 2114)
        self.assertEqual(d["paket_e_messung"]["batch"], 219)
        text = "\n".join(stand.durchsatz_zeilen(self.cfg))
        self.assertIn("offen (Paket E, C-Arbeitsvorrat): 26 Koepfe / 2114 Insn", text)
        self.assertNotIn("38 Koepfe / 2674", text)

    def test_ohne_messung_keine_alte_zahl(self):
        self.dokument(208)
        self.bilanzdatei(208, 681, 686)
        text = "\n".join(stand.durchsatz_zeilen(self.cfg))
        self.assertIn("offen (Paket E, C-Arbeitsvorrat): nicht gemessen seit B208", text)
        self.assertNotIn("38 Koepfe", text)

    def test_bilanz_zeigt_messung_und_delta(self):
        self.dokument(208)
        self.bilanzdatei(208, 681, 686)
        write_text_atomic(self.ana / "_preflight_219.txt",
                          "Pruefung           Ergebnis              Urteil\n"
                          "C Koepfe           90 / 4833 / 0        OK\n")
        messdatei(self.ana, 210, 38, 2674, stand="", datum="")
        messdatei(self.ana, 219, 26, 2114)
        text = "\n".join(bilanz.gesamt_block(self.cfg))
        self.assertIn("Paket E offen: 26 Koepfe / 2114 Insn", text)
        self.assertIn("gemessen B219, 2026-09-30 03:33", text)
        self.assertIn("(B210 -> B219: 12 Koepfe / 560 Insn gebaut)", text)

    def test_identische_vorher_messung_wird_benannt(self):
        """B219: beide Dateien desselben Laufs zeigen 26 - das ist keine Vorher-Messung."""
        self.dokument(208)
        self.bilanzdatei(208, 681, 686)
        messdatei(self.ana, 219, 26, 2114, stand="vorher")
        messdatei(self.ana, 219, 26, 2114, stand="nachher")
        text = "\n".join(bilanz.gesamt_block(self.cfg))
        self.assertIn("Vorher-Messung B219 identisch", text)


# ------------------------------------------------------- Median der Zuwaechse
class TestMedianDerZuwaechse(Basis):
    def bilanzdatei(self, n: int, vorher: int, heute: int) -> None:
        d = ensure_dir(self.ana / f"_m{n}")
        write_text_atomic(d / f"_bilanz{n}.txt",
                          "| Ast | Vorbatch | heute |\n"
                          f"| **R207 rueckwaerts** | **{vorher}** (a 30) | "
                          f"**{heute}** (a 30) |\n")

    def auftrag(self, n: int, soll: int) -> None:
        d = ensure_dir(self.root / "runs" / f"b{n}")
        write_text_atomic(d / "auftrag.md", f"TEIL 3\nSOLL-KOEPFE: {soll}\n")

    def preflight(self, n: int, ck: int) -> None:
        write_text_atomic(self.ana / f"_preflight_{n}.txt",
                          "Pruefung           Ergebnis              Urteil\n"
                          f"C Koepfe           {ck} / 4833 / 0        OK\n")

    def test_median_ueber_die_zuwaechse(self):
        """Die echten Zuwaechse: B216 +7 (78 -> 85), B219 +5 (85 -> 90). Median 6."""
        for n, ck in ((215, 78), (216, 85), (218, 85), (219, 90)):
            self.preflight(n, ck)
            self.bilanzdatei(n, 600 + n, 686 + n)
        for n, soll in ((216, 7), (219, 5)):
            self.auftrag(n, soll)
            write_text_atomic(self.ana / f"port-batch{n}-attrappe.md",
                              "| Zeile | Soll | Ist |\n|---|---|---|\n"
                              "| **C Koepfe** | 78 / 2903 / 0 | **78 / 2903 / 0** |\n")
        text = stand.plan_ist_text(self.cfg, 12)
        self.assertIn("MEDIAN der 2 Zuwaechse der C Koepfe je C-Batch mit SOLL-KOEPFE > 0",
                      text)
        self.assertIn("+7 (B216)", text)
        self.assertIn("+5 (B219)", text)
        self.assertIn("6 Koepfe je C-Batch", text)
        self.assertIn("Ziel des naechsten Batches: hoechstens ca. 8", text)
        # Die Summen stehen nur noch als Einordnung daneben.
        self.assertIn("Summen-Mittel derselben Batches", text)

    def test_ohne_vorgaengerwert_kein_median(self):
        self.preflight(219, 90)
        self.bilanzdatei(219, 681, 686)
        self.auftrag(219, 5)
        write_text_atomic(self.ana / "port-batch219-attrappe.md",
                          "| Zeile | Soll | Ist |\n|---|---|---|\n"
                          "| **C Koepfe** | 78 / 2903 / 0 | **78 / 2903 / 0** |\n")
        text = stand.plan_ist_text(self.cfg, 12)
        self.assertIn("MEDIAN: nicht gemessen", text)


@unittest.skipIf(not (ECHT_219.is_file() and ECHT_210.is_file()),
                 "echte Paket-E-Messungen fehlen")
class TestEchteWerte(unittest.TestCase):
    """Die echten Zahlen von B219 (26 offen) - der Befund als Regressionsschutz."""

    def setUp(self):
        self.cfg = load_config()

    def test_offener_vorrat_ist_26_nicht_38(self):
        m = stand.paket_e_messung(self.cfg)
        self.assertEqual((m["koepfe"], m["insn"]), (26, 2114))
        self.assertEqual(m["batch"], 219)
        self.assertTrue(m["datum"].startswith("2026-09-30"))
        self.assertEqual(m["vorher"]["koepfe"], 38)

    def test_bilanz_zeigt_die_gemessene_zahl(self):
        text = "\n".join(bilanz.gesamt_block(self.cfg))
        self.assertIn("Paket E offen: 26 Koepfe / 2114 Insn", text)
        self.assertIn("gemessen B219", text)
        self.assertNotIn("Paket E offen: 38", text)

    def test_median_der_echten_zuwaechse_ist_sechs(self):
        text = stand.plan_ist_text(self.cfg, 12)
        self.assertIn("+7 (B216)", text)
        self.assertIn("+5 (B219)", text)
        self.assertIn("6 Koepfe je C-Batch", text)
        # Die alte Definition (Median der Summen) haette 88 ergeben.
        self.assertNotIn("88 Koepfe", text)


if __name__ == "__main__":
    unittest.main()
