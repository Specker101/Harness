"""Tests fuer R13bt (2026-10-04): Mischungs-Zeile ohne gemischte Groessen + Stillstandszähler.

**Auftrag (Nutzer, Harness-Wartung).** Die Aussensicht zu B264 hat in `hx/stand.py` eine
Mischrechnung gefunden, die sich selbst widerspricht (`0 C von 2 Batches im Fenster
(31 %)`, Befund M264-5): Zähler und Nenner kamen aus dem BILANZ-**Fenster**, die
Prozentzahl aus der **Preflight-Reihe**.

Der zweite Teil ist der **Stillstandszähler** der B-Phase. Regel wortgetreu
(`analysis/hybrid-plan.md:257-274`, Nutzerklarstellung 2026-10-03):

> Als Sicherung gilt die Stillstandserkennung mit der Schwelle **4 B-Batches ohne
> Station**; der Zaehler wird **ab jeder Station neu** gestartet.

C-Batches zählen **nicht mit** und setzen den Zähler **nicht** zurück. Datenlage der
Vorgabe: B258 ohne Station, **B259 Station**, B260 ohne, **B261 Station**, B262–B264 ohne
(Beginn des Zählers jeweils neu) -> nach B264 steht der Zähler auf **3 von 4**.

Der Harness **rät** die Station nicht: er liest die Pflichtzeile `STATION: ja|nein` aus
dem Review, das den Batch bewertet hat (`runs/b<N+1>/review.md`, R13w). Fehlt sie, ist
der Zähler eine **Untergrenze** und der Batch eine Lücke.

Alles ohne API-Kosten; Zustand und Lauf-Ordner liegen in Wegwerf-Verzeichnissen
(`tests/_tmp_r13bt*`). Das laufende Harness-Verzeichnis wird NICHT angefasst.
"""

from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import aussensicht, stand                                 # noqa: E402
from hx.config import load_config                                 # noqa: E402
from hx.util import (Log, ensure_dir, open_shared_read,           # noqa: E402
                     read_text, write_text_atomic)


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / f"_tmp_r13bt_{type(self).__name__}"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "root")
        ensure_dir(self.root / "runs")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["harness_home"] = str(self.tmp)
        # `paths.decomp` zeigt auf ein leeres Wegwerf-Verzeichnis: sonst lesen die
        # Ausloeser (Hybrid-Lauf, C-Kernzahl) den ECHTEN Decomp-Bestand mit.
        cfg.data["paths"]["decomp"] = str(ensure_dir(self.tmp / "decomp"))
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["paths"]["inbox"] = str(self.root / "inbox")
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---------------------------------------------------------------- Vorrichtungen
    def batch(self, n: int, strang: str = "B", station: bool | None = None) -> None:
        """Ein Batch mit Strang-Zeile; `station` schreibt die Pflichtzeile ins Review.

        Das Review zu Batch N liegt in `runs/b<N+1>/review.md` (R13w) - genau dort liest
        `stand.station_von_batch` sie.
        """
        write_text_atomic(self.root / "runs" / f"b{n:03d}" / "auftrag.md",
                          f"Batch {n}\n\nSTRANG: {strang}\n")
        if station is not None:
            write_text_atomic(self.root / "runs" / f"b{n + 1:03d}" / "review.md",
                              f"STATION: {'ja' if station else 'nein'}\n"
                              "B-SCHRITT: 4/5 Boot bis Hauptschleife\n")

    def lage_258_bis_264(self) -> None:
        """Die Vorgabedaten: Station B259 und B261, sonst keine (B258, B260, B262..B264)."""
        for n in range(258, 265):
            self.batch(n, station=n in (259, 261))


# ------------------------------------------------- 1) Stillstandszähler (Vorgabedaten)
class TestStillstand(Basis):
    def test_daten_aus_der_vorgabe(self):
        self.lage_258_bis_264()
        z = stand.stillstand_zaehler(self.cfg)
        self.assertEqual(z["zaehler"], 3, "B262, B263, B264 ohne Station")
        self.assertEqual((z["von"], z["bis"]), (262, 264))
        self.assertEqual(z["station_bei"], 261, "B261 ist die letzte Station")
        self.assertEqual(z["schwelle"], 4)
        self.assertFalse(z["schwelle_erreicht"], "3 von 4 - die Schwelle ist nicht erreicht")
        self.assertIsNone(z["luecke_ab"], "alle vier Batches sind belegt")
        self.assertEqual(z["reihe"], [(264, "nein"), (263, "nein"), (262, "nein"), (261, "ja")])

    def test_station_setzt_den_zaehler_zurueck(self):
        self.lage_258_bis_264()
        self.batch(265, station=True)
        z = stand.stillstand_zaehler(self.cfg)
        self.assertEqual(z["zaehler"], 0)
        self.assertEqual(z["station_bei"], 265)

    def test_c_batch_zaehlt_nicht_und_setzt_nicht_zurueck(self):
        """Beleg im Plan: "B225 und B227 (B224/B226/B228 sind C-Batches)"."""
        self.lage_258_bis_264()
        self.batch(263, strang="C", station=None)          # C-Batch mitten in der Reihe
        z = stand.stillstand_zaehler(self.cfg)
        self.assertEqual(z["zaehler"], 2, "B264 und B262 zaehlen, B263 nicht")
        self.assertEqual((z["von"], z["bis"]), (262, 264))
        self.assertEqual(z["station_bei"], 261, "der C-Batch setzt NICHT zurueck")

    def test_schwelle_erreicht(self):
        self.lage_258_bis_264()
        self.batch(265, station=False)                     # vier ohne Station in Folge
        z = stand.stillstand_zaehler(self.cfg)
        self.assertEqual(z["zaehler"], 4)
        self.assertTrue(z["schwelle_erreicht"])
        self.assertIn("SCHWELLE 4 ERREICHT", "\n".join(stand.b_phase_zeile(self.cfg, z)))

    def test_ohne_vermerk_wird_nicht_geraten(self):
        """Fehlt die Pflichtzeile, endet der Lauf dort - der Zähler ist eine Untergrenze."""
        self.lage_258_bis_264()
        (self.root / "runs" / "b263" / "review.md").unlink()   # Review zu B262 fehlt
        z = stand.stillstand_zaehler(self.cfg)
        self.assertEqual(z["zaehler"], 2, "B264 und B263 sind belegt - B262 nicht mehr")
        self.assertEqual(z["luecke_ab"], 262)
        text = "\n".join(stand.b_phase_zeile(self.cfg, z))
        self.assertIn("UNTERGRENZE", text)
        self.assertIn("ab B262 ohne STATION:-Vermerk", text)

    def test_ohne_jede_zeile_keine_zahl(self):
        for n in range(262, 265):
            self.batch(n, station=None)
        z = stand.stillstand_zaehler(self.cfg)
        self.assertEqual(z["zaehler"], 0)
        text = "\n".join(stand.b_phase_zeile(self.cfg, z))
        self.assertIn("nicht belegt", text)
        self.assertNotIn("in Folge ohne Station", text)

    def test_zeile_nennt_die_regel(self):
        self.lage_258_bis_264()
        text = "\n".join(stand.b_phase_zeile(self.cfg))
        self.assertIn("3 B-Batches in Folge ohne Station", text)
        self.assertIn("(B262..B264)", text)
        self.assertIn("Schwelle 4", text)


# --------------------------------------- 2) Die Mischungs-Zeile (Befund M264-5)
class TestMischung(Basis):
    def _d(self, **kw) -> dict:
        d = {"n": 2, "fenster": [{"batch": 262}, {"batch": 260}], "c_fenster": [],
             "anteil_c": 0.5, "anteil_quelle": 'Regel hybrid-plan.md:510 "1 B : 1 C"',
             "anteil_gemessen": 4 / 13,
             "anteil_gemessen_basis": "13 Batches mit belegtem Strang",
             "lauf_b": 9, "letzter_c_batch": 254}
        d.update(kw)
        return d

    def test_keine_prozentzahl_aus_einer_fremden_grundmenge(self):
        """Der Befund (\"0 von 2 = 31 %\") darf nicht wiederkehren."""
        zeilen = stand._mischung_zeile(self.cfg, self._d())
        self.assertIn("0 C von 2 Batches im Fenster = 0 %", zeilen[0])
        self.assertNotIn("31 %", zeilen[0], "die Reihen-Quote gehoert nicht neben c/n")
        self.assertIn("gemessen an der Preflight-Reihe", zeilen[1])
        self.assertIn("C-Anteil 31 %", zeilen[1])
        self.assertIn("13 Batches mit belegtem Strang", zeilen[1])

    def test_reine_b_reihe_ruht_die_c_hochrechnung(self):
        """Kein Plan-Anteil als Rechengroesse, wenn seit Batches kein C-Batch lief."""
        zeilen = "\n".join(stand._mischung_zeile(self.cfg, self._d(anteil_c=None)))
        self.assertIn("Strang B laeuft seit B255 ohne C-Batch", zeilen)
        self.assertIn("die C-Hochrechnung ruht", zeilen)
        self.assertNotIn("Anteil fuer die Rechnung", zeilen)

    def test_prozentzahl_kommt_aus_den_eigenen_zahlen(self):
        d = self._d(n=5, c_fenster=[{"batch": b} for b in (207, 206, 205, 204)])
        self.assertIn("4 C von 5 Batches im Fenster = 80 %",
                      stand._mischung_zeile(self.cfg, d)[0])


# ------------------------------------------------- 4) Die BILANZ zeigt beides
class TestBilanzblock(Basis):
    def test_b_phase_steht_auch_ohne_bilanzdatei(self):
        """Der Stand des Zaehlers haengt an den Reviews, nicht an den Bilanzdateien.

        In diesem Wegwerf-Repo gibt es keine `_m<N>/_bilanz*.txt`, der Durchsatz-Block ist
        damit "nicht ermittelbar" - die B-Phase-Zeile muss trotzdem stehen.
        """
        self.lage_258_bis_264()
        text = "\n".join(stand.durchsatz_zeilen(self.cfg))
        self.assertIn("nicht ermittelbar", text)
        self.assertIn("B-Phase", text)
        self.assertIn("3 B-Batches in Folge ohne Station", text)


# --------------------------- 5) Teilen Lesen auf Nicht-ASCII-Pfaden (R13bt-3)
class TestNichtAsciiPfade(Basis):
    """GEMESSEN (2026-10-04): `_winapi.CreateFile` scheitert an Umlauten im Pfad.

    Probe (vier Faelle, je Datei vorhanden, `Path.is_file()` True, `open()` ok):

    =========================  =============  ==================
    Pfad                       `open()`       `read_text` davor
    =========================  =============  ==================
    ascii/ascii                ok             ok
    ascii/umlaut-name          ok             WinError 2
    umlaut-dir/ascii           ok             WinError 3
    umlaut-dir/umlaut-name     ok             WinError 3
    =========================  =============  ==================
    """

    def test_datei_mit_umlaut_im_namen(self):
        p = self.root / "grüße.md"
        write_text_atomic(p, "STATION: ja\n")
        self.assertTrue(p.is_file())
        self.assertEqual(read_text(p), "STATION: ja\n")
        with open_shared_read(p) as fh:
            self.assertEqual(fh.read(), "STATION: ja\n")

    def test_ordner_mit_umlaut(self):
        p = ensure_dir(self.root / "Läufe" / "b264") / "review.md"
        write_text_atomic(p, "STATION: nein\n")
        self.assertEqual(read_text(p), "STATION: nein\n")

    def test_review_zu_batch_liest_umlaut_pfad(self):
        """Der Stillstandszähler darf an einem Umlaut-Pfad nicht scheitern."""
        p = ensure_dir(self.root / "runs") / "b264"
        write_text_atomic(p / "auftrag.md", "STRANG: B\n")
        write_text_atomic(p / "review.md", "STATION: ja\n")
        self.assertIn("STATION: ja", stand.review_zu_batch(self.cfg, 263))


# ------------------------- 6) Die Schwelle loest eine Aussensicht aus (R13bt-5, Nutzerentscheid)
class TestAussensichtAusloeser(Basis):
    """Nutzerentscheid 2026-10-04: `SCHWELLE 4 ERREICHT` loest zusaetzlich eine Aussensicht aus.

    Feuert EINMAL je gezaehltem Lauf: die Marke steht auf dem ERSTEN Batch des Laufs
    (`von`), weil der Zaehler innerhalb des Laufs weiterwaechst und sonst bei jedem Batch
    eine neue (bezahlte) Aussensicht starten wuerde.
    """

    def zustand(self, batch: int):
        from hx import state as st
        s = st.State(self.root / "state" / "run.json")
        s.data["batch"] = int(batch)
        s.save()
        return s

    def gruende(self, batch: int, s=None) -> list[str]:
        return aussensicht.faellig(self.cfg, s or self.zustand(batch), log=self.log)

    def still_gruende(self, gruende: list[str]) -> list[str]:
        return [g for g in gruende if g.startswith(aussensicht.STATION_GRUND)]

    def vier_ohne_station(self) -> None:
        """Station bei B265 (Review `runs/b266/review.md`), dann B266..B269 ohne Station."""
        self.batch(265, station=True)
        for n in (266, 267, 268, 269):
            self.batch(n, station=False)

    # ------------------------------------------------------------------ Fälle
    def test_vier_ohne_station_loesen_aus(self):
        self.vier_ohne_station()
        text = aussensicht.station_stillstand(self.cfg)
        self.assertIn("Stillstand der B-Phase: 4 B-Batches in Folge ohne Station", text)
        self.assertIn("(B266..B269, Schwelle 4)", text)
        self.assertIn("analysis/hybrid-plan.md:257-274", text)
        self.assertEqual(len(self.still_gruende(self.gruende(269))), 1)
        self.assertTrue(aussensicht.station_beteiligt([text]))
        self.assertFalse(aussensicht.station_beteiligt(["Hybrid-Lauf haengt: halt"]))
        self.assertFalse(aussensicht.station_beteiligt([]))

    def test_drei_loesen_noch_nicht_aus(self):
        for n in (267, 268, 269):
            self.batch(n, station=False)
        self.assertEqual(aussensicht.station_stillstand(self.cfg), "")
        self.assertEqual(self.still_gruende(self.gruende(269)), [])

    def test_die_marke_verhindert_das_zweite_feuer(self):
        self.vier_ohne_station()
        s = self.zustand(269)
        self.assertEqual(len(self.still_gruende(self.gruende(269, s))), 1)
        self.assertEqual(aussensicht.station_marke_setzen(self.cfg, s), 266,
                         "die Marke steht auf dem ERSTEN Batch des Laufs")
        s.data["meta"]["geprueft_batch"] = 269        # so setzt es der echte Lauf am Ende
        s.save()
        self.batch(270, station=False)                # Zaehler steht jetzt auf 5
        self.assertEqual(stand.stillstand_zaehler(self.cfg)["zaehler"], 5)
        self.assertEqual(self.still_gruende(self.gruende(270, s)), [],
                         "derselbe Stillstand meldet nur einmal")

    def test_station_macht_die_schwelle_wieder_scharf(self):
        self.vier_ohne_station()
        s = self.zustand(269)
        aussensicht.station_marke_setzen(self.cfg, s)
        s.data["meta"]["geprueft_batch"] = 269
        s.save()
        self.batch(270, station=True)                 # Station: Zaehler neu
        self.assertEqual(self.still_gruende(self.gruende(270, s)), [])
        for n in (271, 272, 273, 274):
            self.batch(n, station=False)
        s.data["batch"] = 274
        s.save()
        self.assertEqual(aussensicht.station_neuester_b(self.cfg), 271)
        self.assertEqual(len(self.still_gruende(self.gruende(274, s))), 1,
                         "nach der Station ist die Schwelle wieder scharf")

    def test_c_batch_verlaengert_nicht_und_setzt_nicht_zurueck(self):
        """Nutzerentscheid 3: C-Batches setzen den Zaehler nicht zurueck (R13bt-2)."""
        self.vier_ohne_station()
        self.batch(270, strang="C", station=None)     # ersetzt nur den Auftrag von B270
        z = stand.stillstand_zaehler(self.cfg)
        self.assertEqual(z["zaehler"], 4)
        self.assertEqual(z["station_bei"], 265, "der C-Batch ist keine Station")
        self.assertTrue(z["schwelle_erreicht"])

    def test_luecke_hinten_meldet_und_nennt_die_untergrenze(self):
        self.vier_ohne_station()
        (self.root / "runs" / "b266" / "review.md").unlink()   # Review zu B265 fehlt
        z = stand.stillstand_zaehler(self.cfg)
        self.assertEqual((z["zaehler"], z["luecke_ab"]), (4, 265))
        text = aussensicht.station_stillstand(self.cfg)
        self.assertIn("Stillstand der B-Phase: 4 B-Batches", text)
        self.assertIn("ab B265 ist der Stand nicht belegt", text)
        self.assertIn("Untergrenze", text)

    def test_b_phase_zeile_nennt_den_ausloeser(self):
        self.vier_ohne_station()
        text = "\n".join(stand.b_phase_zeile(self.cfg))
        self.assertIn("SCHWELLE 4 ERREICHT", text)
        self.assertIn("loest eine Aussensicht aus", text)
        self.assertIn("OFFENE FRAGE an den Nutzer", text)


if __name__ == "__main__":
    unittest.main()
