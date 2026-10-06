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
**R13bw-9 (2026-10-06):** dieselbe Rechnung zusätzlich auf der fortgeschriebenen
Datenlage **B258 bis B277** (`Basis.lage_258_bis_277`, Station B259/B261/B269) sowie der
**letzte C-Batch** aus der lückenlosen Strangreihe (`stand.strang_lauf`).

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
    def batch(self, n: int, strang: str = "B", station: bool | None = None,
              bewegung: bool | None = None) -> None:
        """Ein Batch mit Strang-Zeile; `station`/`bewegung` schreiben die Pflichtzeilen.

        Das Review zu Batch N liegt in `runs/b<N+1>/review.md` (R13w) - genau dort liest
        `stand.station_von_batch` sie. `bewegung` schreibt seit R13bw-10 zusaetzlich die
        Pflichtzeile `BEWEGUNG: ja|nein` (fehlt sie, greift der Anker-Rueckfall).
        """
        write_text_atomic(self.root / "runs" / f"b{n:03d}" / "auftrag.md",
                          f"Batch {n}\n\nSTRANG: {strang}\n")
        if station is not None or bewegung is not None:
            zeilen = []
            if station is not None:
                zeilen.append(f"STATION: {'ja' if station else 'nein'}")
            if bewegung is not None:
                zeilen.append(f"BEWEGUNG: {'ja' if bewegung else 'nein'}")
            zeilen.append("B-SCHRITT: 4/5 Boot bis Hauptschleife")
            write_text_atomic(self.root / "runs" / f"b{n + 1:03d}" / "review.md",
                              "\n".join(zeilen) + "\n")

    def lage_258_bis_264(self) -> None:
        """Die Vorgabedaten: Station B259 und B261, sonst keine (B258, B260, B262..B264)."""
        for n in range(258, 265):
            self.batch(n, station=n in (259, 261))

    def lage_258_bis_277(self) -> None:
        """Die DATENLAGE ab B258, bis zum laufenden Batch B277 fortgeschrieben (R13bw-9).

        Station nur bei B259, B261 und **B269**; danach B270..B277 ohne Station. Der
        Aufbau spiegelt den Ankerkopf (`analysis/r1b-workstream.md:5-6`): dort steht
        `Stillstand (Station) 7` bei letzter Station B269 (B270..B276) - mit den zwei
        zusaetzlichen Batches bis B277 sind es hier **8**.
        """
        for n in range(258, 278):
            self.batch(n, station=n in (259, 261, 269))


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
        """R13bw-10: der Stationszaehler ist reine Information - er loest NICHTS aus."""
        self.lage_258_bis_264()
        self.batch(265, station=False)                     # vier ohne Station in Folge
        z = stand.stillstand_zaehler(self.cfg)
        self.assertEqual(z["zaehler"], 4)
        self.assertTrue(z["schwelle_erreicht"])           # bleibt eine Zahl ...
        text = "\n".join(stand.b_phase_zeile(self.cfg, z))
        self.assertIn("4 B-Batches in Folge ohne Station", text)
        self.assertIn("reine Information (R277-1", text)
        self.assertNotIn("loest eine Aussensicht aus", text)     # ... aber kein Ausloeser
        self.assertNotIn("OFFENE FRAGE", text)
        self.assertNotIn("SCHWELLE 4 ERREICHT", text)

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
        self.assertIn("Stationszaehler 4 loest nichts mehr aus", text)

    def test_datenlage_bis_b277(self):
        """R13bw-9: dieselbe Rechnung auf der fortgeschriebenen Datenlage (B258..B277)."""
        self.lage_258_bis_277()
        z = stand.stillstand_zaehler(self.cfg)
        self.assertEqual(z["zaehler"], 8, "B270..B277 ohne Station")
        self.assertEqual((z["von"], z["bis"]), (270, 277))
        self.assertEqual(z["station_bei"], 269)
        self.assertIsNone(z["luecke_ab"], "alle Batches sind belegt")


# ------------------- 1b) Die lueckenlose Strangreihe: letzter C-Batch (R13bw-9 Punkt 2)
class TestStrangLauf(Basis):
    """Die Mischungs-Zeile nennt "letzter C-Batch B0" - gemessen war B254.

    Ursache (06.10.2026): der B-Lauf und der letzte C-Batch wurden aus der ZEILENREIHE der
    Preflight-Dateien gezaehlt (`c_trend`, nur `TREND_FENSTER`+1 = 14 Zeilen). Der B-Lauf
    war laenger als das Fenster, die Reihe lief aus - beide Zahlen fielen auf 0. Gemessen
    wird jetzt rueckwaerts ueber die **Batch-Ordner** (`stand.strang_lauf`).
    """

    def _b_reihe(self, c_batch: int = 254, von: int = 255, bis: int = 277) -> None:
        self.batch(c_batch, strang="C", station=None)
        for n in range(von, bis + 1):
            self.batch(n, station=None)

    def test_letzter_c_batch_kommt_aus_der_reihe(self):
        self._b_reihe()
        sl = stand.strang_lauf(self.cfg)
        self.assertEqual(sl["letzter_c"], 254, "nicht 0 und nicht der Fensterrand")
        self.assertEqual((sl["von"], sl["bis"]), (255, 277))
        self.assertEqual(sl["lauf_b"], 23)
        self.assertIsNone(sl["grenze_ab"])

    def test_durchsatz_und_mischungszeile_ziehen_mit(self):
        """Die Zahl der BILANZ-Zeile ist die der Reihe - kein zweiter Weg, kein B0."""
        self._b_reihe()
        d = stand.durchsatz(self.cfg)
        # Im Wegwerf-Verzeichnis gibt es keine Preflight-Reihe: Fenster von Hand setzen,
        # damit die Zeile ihre zwei Zahlen druckt (die Strang-Zahlen stehen schon drin).
        d["n"], d["fenster"] = 2, [{"batch": 276}, {"batch": 277}]
        self.assertEqual(d["letzter_c_batch"], 254)
        self.assertEqual(d["lauf_b"], 23)
        text = "\n".join(stand._mischung_zeile(self.cfg, d))
        self.assertIn("Strang B laeuft seit B255 ohne C-Batch", text)
        self.assertIn("letzter C-Batch B254", text)
        self.assertIn("B255..B277", text)
        self.assertNotIn("letzter C-Batch B0", text)

    def test_reisst_die_reihe_ist_der_wert_eine_untergrenze(self):
        """Ein Batch ohne belegten Strang beendet den Lauf - und wird als Grenze gemeldet.

        Geraten wird nichts: der zuletzt gefundene C-Batch bleibt stehen (Untergrenze),
        und die Zeile sagt, wo die Reihe reisst.
        """
        self._b_reihe()
        # B260: kein Strang im Auftrag und kein Review (der Rueckfall haette sonst
        # gegriffen) -> die Reihe reisst dort, der C-Batch B254 wird nicht mehr erreicht.
        write_text_atomic(self.root / "runs" / "b260" / "auftrag.md", "Batch 260\n")
        sl = stand.strang_lauf(self.cfg)
        self.assertEqual(sl["grenze_ab"], 260)
        self.assertIsNone(sl["letzter_c"], "die Reihe reisst VOR dem C-Batch - nicht belegt")
        self.assertEqual(sl["lauf_b"], 17, "B261..B277 (Untergrenze)")
        self.assertEqual((sl["von"], sl["bis"]), (261, 277))
        d = stand.durchsatz(self.cfg)
        d["n"], d["fenster"] = 2, [{"batch": 276}, {"batch": 277}]
        self.assertIsNone(d["letzter_c_batch"])
        text = "\n".join(stand._mischung_zeile(self.cfg, d))
        self.assertIn("UNTERGRENZE", text)
        self.assertIn("letzter C-Batch nicht belegt", text)
        self.assertNotIn("B0", text, "kein erfundener Batch: 0 wurde frueher als B0 gedruckt")

    def test_neuester_batch_ist_c_dann_ist_er_selbst_der_letzte(self):
        self.batch(254, strang="C", station=None)
        self.batch(255, strang="C", station=None)
        sl = stand.strang_lauf(self.cfg)
        self.assertEqual(sl["letzter_c"], 255)
        self.assertEqual(sl["lauf_b"], 0, "kein B-Lauf - die C-Zeile gilt")
        d = stand.durchsatz(self.cfg)
        self.assertNotIn("Strang B laeuft", "\n".join(stand._mischung_zeile(self.cfg, d)))


# --------------------------------------- 2) Die Mischungs-Zeile (Befund M264-5)
class TestMischung(Basis):
    def _d(self, **kw) -> dict:
        d = {"n": 2, "fenster": [{"batch": 262}, {"batch": 260}], "c_fenster": [],
             "anteil_c": 0.5, "anteil_quelle": 'Regel hybrid-plan.md:510 "1 B : 1 C"',
             "anteil_gemessen": 4 / 13,
             "anteil_gemessen_basis": "13 Batches mit belegtem Strang",
             "lauf_b": 9, "letzter_c_batch": 254,
             # R13bw-9: die Bereichsangabe der Zeile kommt aus der lueckenlosen Reihe
             "strang_lauf": {"letzter_c": 254, "lauf_b": 9, "von": 255, "bis": 263,
                             "grenze_ab": None, "luecke_ab": None, "reihe": []}}
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


# ------------------------- 6) R277-1: Hinweis statt Ausloeser (R13bw-10, Nutzerentscheid)
class TestFortschrittsHinweis(Basis):
    """R277-1: der Stations-Stillstand loest KEINE Aussensicht und keine Frage mehr aus.

    Wortlaut (`analysis/hybrid-plan.md:303-317`): "ebenso der Stillstandszaehler 4 als
    Ausloeser fuer Rueckfrage und Aussensicht [entfaellt]. Der Zaehler bleibt als reine
    Information im Ankerkopf. Nur wenn 6 B-Batches in Folge weder Station noch Bewegung
    zeigen, kommt ein Hinweis an mich (keine Frage, kein Strangwechsel, B laeuft weiter bis
    ich anders entscheide)."

    Nutzerentscheid R13bw-10 (06.10.2026): "Bewegung wie die Station aus einer Pflichtzeile
    im Review lesen: neue Zeile `BEWEGUNG: ja|nein` ... Fehlt die Zeile, wird der Zaehler als
    Untergrenze ausgewiesen (wie beim Stationszaehler). Alte Batches ohne BEWEGUNG-Zeile aus
    dem Ankerkopf (Bewegung: JA/NEIN) nachlesen, falls dort vorhanden, sonst als unbekannt
    fuehren."
    """

    def zustand(self, batch: int):
        from hx import state as st
        s = st.State(self.root / "state" / "run.json")
        s.data["batch"] = int(batch)
        s.save()
        return s

    def gruende(self, batch: int) -> list[str]:
        return aussensicht.faellig(self.cfg, self.zustand(batch), log=self.log)

    def sechs_ohne_alles(self, von: int = 270) -> None:
        """Station+Bewegung in B<von>-1, danach sechs B-Batches ohne beides."""
        self.batch(von - 1, station=True, bewegung=True)
        for n in range(von, von + 6):
            self.batch(n, station=False, bewegung=False)

    def anker_schreiben(self, text: str) -> None:
        """Der Ankerkopf im Wegwerf-Decomp-Verzeichnis (`cfg.anchor_file`)."""
        write_text_atomic(self.cfg.anchor_file, text)

    # ------------------------------------------------------------------ Fälle
    def test_sechs_ohne_alles_ergeben_den_hinweis(self):
        self.sechs_ohne_alles()
        f = stand.fortschritt_zaehler(self.cfg)
        self.assertEqual(f["zaehler"], 6)
        self.assertEqual((f["von"], f["bis"]), (270, 275))
        self.assertTrue(f["schwelle_erreicht"])
        self.assertEqual(f["schwelle"], 6, "R277-1 nennt 6 - nicht die alte 4")
        self.assertIsNone(f["luecke_ab"])
        text = stand.fortschritt_hinweis_text(self.cfg, f)
        self.assertIn("R277-1: 6 B-Batches in Folge weder Station noch Bewegung", text)
        self.assertIn("(B270..B275, Hinweisgrenze 6)", text)
        self.assertIn("Keine Frage, kein Strangwechsel", text)

    def test_vier_ohne_station_ergeben_keinen_hinweis_mehr(self):
        """Der Kern von R277-1: die alte Schwelle 4 zieht nicht mehr."""
        self.batch(265, station=True, bewegung=True)
        for n in (266, 267, 268, 269):
            self.batch(n, station=False, bewegung=False)
        f = stand.fortschritt_zaehler(self.cfg)
        self.assertEqual(f["zaehler"], 4)
        self.assertFalse(f["schwelle_erreicht"], "4 von 6")
        self.assertEqual(stand.fortschritt_hinweis_text(self.cfg, f), "", "kein Hinweis")

    def test_station_oder_bewegung_beginnt_neu(self):
        self.sechs_ohne_alles()
        self.batch(276, station=True, bewegung=False)         # Station: Zaehler neu
        f = stand.fortschritt_zaehler(self.cfg)
        self.assertEqual(f["zaehler"], 0)
        self.assertEqual((f["stop_grund"], f["stop_bei"]), ("station", 276))
        self.batch(277, station=False, bewegung=True)         # Bewegung: Zaehler neu
        f = stand.fortschritt_zaehler(self.cfg)
        self.assertEqual(f["zaehler"], 0)
        self.assertEqual((f["stop_grund"], f["stop_bei"]), ("bewegung", 277))

    def test_der_hinweis_ist_keine_aussensicht(self):
        """Wortlaut R277-1: "keine Frage" - also kein Grund in `faellig`, kein Ausloeser."""
        self.sechs_ohne_alles()
        gruende = self.gruende(275)
        self.assertEqual([g for g in gruende if "Stillstand der B-Phase" in g], [])
        self.assertFalse(hasattr(aussensicht, "station_stillstand"),
                         "der Ausloeser aus R13bt-5 muss entfallen (R277-1)")
        self.assertFalse(hasattr(aussensicht, "station_beteiligt"))

    def test_c_batch_zaehlt_nicht_und_setzt_nicht_zurueck(self):
        """Nutzerentscheid 3: C-Batches setzen den Zaehler nicht zurueck (R13bt-2)."""
        self.sechs_ohne_alles()
        self.batch(271, strang="C", station=None)     # ersetzt nur den Auftrag von B271
        f = stand.fortschritt_zaehler(self.cfg)
        self.assertEqual(f["zaehler"], 5, "sechs gezaehlt, einer davon ist jetzt C")
        self.assertEqual(f["von"], 270, "der C-Batch setzt NICHT zurueck")
        self.assertEqual(f["bis"], 275)
        self.assertEqual(stand.stillstand_zaehler(self.cfg)["zaehler"], 5)

    def test_fehlende_bewegungszeile_ist_eine_untergrenze(self):
        """Reviews ohne `BEWEGUNG:`-Zeile (alte Batches): die Zahl wird nicht erfunden.

        Wie beim Stationszaehler: der Lauf endet an dem Batch ohne Beleg - die gezaehlten
        Batches bleiben stehen, die Zahl ist eine **Untergrenze**.
        """
        self.batch(268, station=True, bewegung=True)
        for n in (269, 270, 271):
            self.batch(n, station=False, bewegung=False)
        # Der Review zu B269 (Datei runs/b270/review.md): STATION da, BEWEGUNG nicht
        write_text_atomic(self.root / "runs" / "b270" / "review.md",
                          "STATION: nein\nB-SCHRITT: 4/5 Boot bis Hauptschleife\n")
        f = stand.fortschritt_zaehler(self.cfg)
        self.assertEqual(f["zaehler"], 2, "B271 und B270 sind belegt")
        self.assertEqual(f["luecke_ab"], 269)
        self.assertEqual(f["fehlt_batch"], 269)
        self.assertEqual(f["fehlt_zeile"], stand.BEWEGUNG_ZEILE)
        text = "\n".join(stand.b_phase_zeile(self.cfg))
        self.assertIn("ab B269 fehlt BEWEGUNG: ja|nein", text)
        self.assertIn("der Fortschritts-Zaehler ist eine UNTERGRENZE", text)

    def test_alter_batch_wird_aus_dem_anker_gelesen(self):
        """Alte Batches (vor R13bw-10) haben keine BEWEGUNG-Zeile - der Anker hilft aus."""
        self.anker_schreiben(
            "# Workstream R1B\n\n"
            "**Stand:** BATCH 272 (**B-Batch**).\n"
            "**Station (B271):** Regel (a) Halt-PC - **NEIN**. **Bewegung: JA** (Zeiger).\n\n"
            "**Stand (Vorgaenger, B271):** BATCH 271.\n"
            "**Station (B270):** Regel (a) - **NEIN**. **Bewegung: NEIN**.\n")
        self.assertEqual(stand._anker_bewegung(self.cfg), {271: True, 270: False})
        self.assertIs(stand.bewegung_von_batch(self.cfg, 271)["bewegung"], True)
        self.assertIs(stand.bewegung_von_batch(self.cfg, 270)["bewegung"], False)
        self.assertEqual(stand.bewegung_von_batch(self.cfg, 271)["quelle"],
                         stand.BEWEGUNG_ANKER_QUELLE)
        self.assertIsNone(stand.bewegung_von_batch(self.cfg, 269)["bewegung"],
                          "ohne Vermerk: unbekannt, nicht geraten")
        # Und der Zaehler zieht den Anker-Vermerk wie eine Pflichtzeile: B271 zeigt dort
        # Bewegung -> der Lauf endet an B271 (nichts gezaehlt).
        for n in (270, 271):
            self.batch(n, station=False, bewegung=None)       # nur STATION: nein
        f = stand.fortschritt_zaehler(self.cfg)
        self.assertEqual((f["zaehler"], f["stop_grund"], f["stop_bei"]),
                         (0, "bewegung", 271))
        # Sagt der Anker fuer BEIDE "NEIN", werden beide gezaehlt:
        self.anker_schreiben(
            "# Workstream R1B\n\n"
            "**Stand:** BATCH 272 (**B-Batch**).\n"
            "**Station (B271):** Regel (a) - **NEIN**. **Bewegung: NEIN**.\n\n"
            "**Stand (Vorgaenger, B271):** BATCH 271.\n"
            "**Station (B270):** Regel (a) - **NEIN**. **Bewegung: NEIN**.\n")
        f = stand.fortschritt_zaehler(self.cfg)
        self.assertEqual(f["zaehler"], 2, "Bewegung kommt aus dem Anker, STATION aus dem Review")
        self.assertEqual((f["von"], f["bis"]), (270, 271))

    def test_zeile_nennt_reine_information_und_hinweisgrenze(self):
        self.sechs_ohne_alles()
        text = "\n".join(stand.b_phase_zeile(self.cfg))
        self.assertIn("6 B-Batches in Folge ohne Station", text)
        self.assertIn("reine Information (R277-1", text)
        self.assertIn("Fortschritt  : 6 B-Batches in Folge weder Station noch Bewegung", text)
        self.assertIn("HINWEISGRENZE 6 ERREICHT (Telegram-Hinweis, keine Frage", text)
        self.assertNotIn("OFFENE FRAGE", text)

    def test_nach_station_oder_bewegung_steht_die_null_mit_grund(self):
        """Beendet eine belegte Station/Bewegung den Lauf, steht die 0 samt Grund da."""
        self.sechs_ohne_alles()
        self.batch(276, station=False, bewegung=True)         # Bewegung in B276
        text = "\n".join(stand.b_phase_zeile(self.cfg))
        self.assertIn("Fortschritt  : 0 B-Batches in Folge weder Station noch Bewegung "
                      "(zuletzt B276: Bewegung)", text)
        self.assertNotIn("HINWEISGRENZE", text)


if __name__ == "__main__":
    unittest.main()
