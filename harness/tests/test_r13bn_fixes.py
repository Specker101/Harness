"""Tests fuer R13bn (02.10.2026): Harness-Wartung am Gate.

Je Punkt ein Abschnitt, je Punkt ein Commit:

  1. **Abbruch-Marke nur einmal** (M241-4/M242-5/M243-2): die Marker-Ausloeser
     (`MEILENSTEIN ERREICHT:` / `ABBRUCHKRITERIUM ERREICHT:`) bekommen dieselbe
     `gemeldet_bis`-Sperre wie Kernzahl, `c_soll_null` und Hybrid-Lauf - je Review-Datei
     hoechstens eine Ausloesung. Anlass: EINE Marke aus der B241-Review hat vier
     Außensicht-Laeufe ausgeloest (meta-240 bis meta-243).
  2. Nur messen: Verbrauch je Aufruftyp (Beleg `docs/_r13bn_verbrauch.txt`).
  3. **Prognose** (M242-3/M243-3): der Median der Koepfe je C-Batch kommt aus der
     **lueckenlosen Preflight-Reihe** statt aus den Bilanzdateien (die fuer einzelne
     Batches fehlen - B241), die Kalender-Hochrechnung nimmt den **gemessenen C-Anteil**
     (Strang B ruht -> 100 %), und der Trend fuehrt **zusaetzlich** `C verifiziert`.
     Stand: `tests/fixtures/stand_b243` (Reihe B236-B243).

Alles laeuft in Wegwerf-Verzeichnissen; das Decomp-Repo wird nur gelesen.
"""

from __future__ import annotations

import inspect
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import aussensicht, bilanz, stand                            # noqa: E402
from hx.config import load_config                                   # noqa: E402
from hx.orchestrator import Orchestrator                            # noqa: E402
from hx.util import Log, ensure_dir, write_text_atomic              # noqa: E402


class _State:
    """Minimaler Zustands-Ersatz: `faellig` liest `data`/`batch` und ruft `save()`."""

    def __init__(self, data: dict):
        self.data = data
        self.saves = 0

    @property
    def batch(self):
        return self.data.get("batch")

    def save(self) -> None:
        self.saves += 1


class Basis(unittest.TestCase):
    """Wegwerf-Harness mit Wegwerf-Decomp-Repo (Muster aus `test_r13ah_fixes`)."""

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13bn"
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

    # ------------------------------------------------------------------ Helfer
    def review(self, ordner: int, text: str) -> None:
        """Ein Review im Ordner `runs/b<ordner>` (Konvention: Review N-1 liegt in bN)."""
        write_text_atomic(ensure_dir(self.root / "runs" / f"b{ordner:03d}") / "review.md",
                          "<TELEGRAM_SUMMARY>\n" + text + "\n</TELEGRAM_SUMMARY>\n")

    def state(self, batch: int, meta: dict | None = None) -> _State:
        d = {"batch": batch, "last_batch_number": batch - 1,
             "meta": dict(meta if meta is not None else {})}
        return _State(d)

    def marker(self, batch: int, art: str = "ABBRUCHKRITERIUM") -> str:
        return f"{art} ERREICHT: M242-1 (Attrappe in runs/b{batch})"

    def ausloesungen(self, batche=(241, 242, 243), verbuchen: bool = True,
                     meta: dict | None = None) -> tuple[list[bool], _State]:
        """Pruefungen ueber mehrere Batches mit EINEM Zustand (wie im Betrieb).

        Zwischen den Pruefungen laeuft jeweils eine Aussensicht; `verbuchen=True`
        stellt das nach (`marker_marke_setzen`).
        """
        s = self.state(batche[0], meta=meta)
        aus: list[bool] = []
        for batch in batche:
            s.data["batch"] = batch
            gruende = aussensicht.faellig(self.cfg, s, self.log)
            hier = [g for g in gruende if "Abbruchkriterium" in g]
            aus.append(bool(hier))
            if hier and verbuchen:         # gelaufener Lauf: der Orchestrator verbucht
                aussensicht.marker_marke_setzen(self.cfg, s, gruende)
        return aus, s


# ============================================ 1) Eine Abbruch-Marke loest EINMAL aus
class TestAbbruchMarkeEinmal(Basis):
    """Punkt 1: dieselbe Marke ueber drei Batches -> genau eine Ausloesung."""

    def test_dieselbe_marke_loest_nur_einmal_aus(self):
        # Die Marke steht in runs/b245 (Review-Konvention) - juenger als die Migration.
        self.review(245, self.marker(244))
        aus, _s = self.ausloesungen(batche=(244, 245, 246))
        self.assertEqual(aus, [True, False, False],
                         "die Marke darf nur den ersten Lauf ausloesen")

    def test_ohne_sperre_waere_es_dreimal(self):
        """Gegenprobe zum Befund: ohne das Verbuchen feuert sie bei JEDER Pruefung."""
        self.review(245, self.marker(244))
        aus, _s = self.ausloesungen(batche=(244, 245, 246), verbuchen=False)
        self.assertEqual(aus, [True, True, True], "so war es vor R13bn (vier Laeufe)")

    def test_eine_neue_marke_loest_wieder_aus(self):
        """Eine NEUE Review mit derselben Marke ist eine neue Nachricht - sie feuert."""
        self.review(245, self.marker(244))
        aus, s = self.ausloesungen(batche=(244, 245, 246))
        self.assertEqual(aus, [True, False, False])
        self.review(247, self.marker(246))          # neue Marke aus B246
        s.data["batch"] = 246
        gruende = aussensicht.faellig(self.cfg, s, self.log)
        self.assertTrue([g for g in gruende if "Abbruchkriterium" in g], gruende)

    def test_marke_im_fenster_loest_aus_ohne_eintrag(self):
        """Frischer Zustand (kein Schluessel): eine Marke im Fenster loest ganz normal aus.

        Gemessen am 02.10.2026 braucht es dafuer KEINE Migration: die Marke aus
        `runs/b241/review.md` liegt nicht mehr unter den letzten drei
        Zusammenfassungen (`runs/b242..b244`, `aussensicht.summaries(cfg, 3)`) - die
        vier Laeufe meta-240..243 sind damit von selbst vorbei. Eine feste
        Migrationsnummer haette dagegen jede kuenftige Marke bis dahin verschluckt.
        """
        self.review(241, self.marker(240))
        s = self.state(240)
        gruende = aussensicht.faellig(self.cfg, s, self.log)
        self.assertTrue([g for g in gruende if "Abbruchkriterium" in g], gruende)
        self.assertIn("runs/b241", [g for g in gruende if "Abbruchkriterium" in g][0])
        self.assertIn("marker_gemeldet_bis", s.data["meta"],
                      "die Sperrtafel wird einmal angelegt")
        self.assertTrue(s.saves, "der Zustand wird gesichert")

    def test_beide_markenarten_zaehlen_getrennt(self):
        """`MEILENSTEIN ERREICHT` ist eine eigene Marke - die Sperre gilt je Art."""
        self.review(245, self.marker(244) + "\nMEILENSTEIN ERREICHT: B244 fertig")
        s = self.state(244)
        gruende = aussensicht.faellig(self.cfg, s, self.log)
        self.assertTrue([g for g in gruende if "Meilenstein" in g], gruende)
        bet = aussensicht.marker_marke_setzen(self.cfg, s, gruende)
        self.assertEqual(bet, {"Meilenstein erreicht": 245, "Abbruchkriterium erreicht": 245})
        # Jetzt sind BEIDE Marken dieser Review gesperrt.
        s.data["batch"] = 245
        gruende2 = aussensicht.faellig(self.cfg, s, self.log)
        self.assertFalse([g for g in gruende2 if "erreicht - laut Review" in g], gruende2)

    def test_beteiligt_liest_die_review_datei_aus_dem_grund(self):
        self.assertEqual(aussensicht.marker_beteiligt(
            ["Abbruchkriterium erreicht - laut Review in runs/b241: irgendwas"]),
            {"Abbruchkriterium erreicht": 241})
        self.assertEqual(aussensicht.marker_beteiligt(
            ["Meilenstein erreicht - laut Review in runs/b242: x",
             "Abbruchkriterium erreicht - laut Review in runs/b241: y"]),
            {"Meilenstein erreicht": 242, "Abbruchkriterium erreicht": 241})
        self.assertEqual(aussensicht.marker_beteiligt(["Worker-Abbruch in Batch 240 (wall)"]), {})

    def test_gemeldet_bis_ohne_tafel_ist_null(self):
        """Ohne Tafel gilt 0 = nichts gemeldet (keine Migration, s. `aussensicht.py`)."""
        self.assertEqual(aussensicht.marker_gemeldet_bis({}, "Abbruchkriterium erreicht"), 0)
        self.assertEqual(aussensicht.marker_gemeldet_bis({}, "Meilenstein erreicht"), 0)
        self.assertEqual(aussensicht.marker_gemeldet_bis(
            {"marker_gemeldet_bis": {"Abbruchkriterium erreicht": 250}},
            "Abbruchkriterium erreicht"), 250)
        self.assertEqual(aussensicht.marker_gemeldet_bis(
            {"marker_gemeldet_bis": {"andere": 7}}, "Meilenstein erreicht"), 0)

    def test_orchestrator_verbucht_die_marke(self):
        """Ohne das Verbuchen im Orchestrator bliebe die Sperre wirkungslos."""
        quelle = inspect.getsource(Orchestrator._do_aussensicht)
        self.assertIn("marker_marke_setzen", quelle)


# ============================== 3) Prognose: Median, C-Anteil, "C verifiziert"
FIXTURE_B243 = Path(__file__).resolve().parent / "fixtures" / "stand_b243"


class BasisStand(Basis):
    """Der eingefrorene Stand `stand_b243` (Reihe B236..B243) im Wegwerf-Verzeichnis."""

    def setUp(self):
        super().setUp()
        shutil.copytree(FIXTURE_B243 / "root", self.root, dirs_exist_ok=True)
        shutil.copytree(FIXTURE_B243 / "decomp", self.decomp, dirs_exist_ok=True)
        self.ana = self.decomp / "analysis"


class TestPrognoseStandB243(BasisStand):
    """Punkt 3 mit der echten Reihe B237-B243 (M242-3/M243-3)."""

    def test_median_kommt_aus_der_preflight_reihe(self):
        r = stand.c_rate(self.cfg)
        self.assertEqual(r["kopf_batches"], [(241, 2), (239, 2), (237, 4)])
        self.assertEqual(r["median"], 2.0, "+4 (B237), +2 (B239), +2 (B241)")
        self.assertEqual(r["mittel"], 1.6, "alle C-Batch-Schritte des Fensters")
        self.assertIn("+2 (B241)", r["quelle"], "der Batch steht in der Grundmenge")

    def test_der_batch_ohne_bilanzdatei_zaehlt_mit(self):
        """B241 hat keine kanonische Bilanzdatei - genau der Anlass von M242-3."""
        self.assertFalse((self.ana / "_m241").exists())
        self.assertIn(241, [b for b, _d in stand.c_rate(self.cfg)["kopf_batches"]])

    def test_ohne_die_preflight_datei_steht_die_alte_zahl(self):
        """Gegenprobe: faellt B241 aus der Reihe, kommt wieder 3 heraus (so war es)."""
        (self.ana / "_preflight_241.txt").unlink()
        r = stand.c_rate(self.cfg)
        self.assertEqual([b for b, _d in r["kopf_batches"]], [239, 237])
        self.assertEqual(r["median"], 3.0)

    def test_ohne_benachbarte_datei_kein_schritt(self):
        """Die Reihe muss LUECKENLOS sein - ein fehlender Nachbar ergibt keinen Schritt."""
        (self.ana / "_preflight_239.txt").unlink()
        r = stand.c_rate(self.cfg)
        self.assertNotIn(239, [b for b, _d in r["kopf_batches"]])

    def test_c_anteil_ist_der_gemessene_abschnitt(self):
        d = stand.durchsatz(self.cfg)
        self.assertEqual(d["c_lauf"], 3, "B241, B242, B243 sind C-Batches")
        self.assertEqual(d["anteil_c"], 1.0, "Strang B ruht - kein 50-%-Abschlag")
        self.assertIn("B241..B243", d["anteil_quelle"])
        self.assertIn("Plan-Regel nennt 50 %", d["anteil_quelle"])

    def test_mischungszeile_nennt_den_abschnitt(self):
        zeile = "\n".join(stand._mischung_zeile(self.cfg, stand.durchsatz(self.cfg)))
        self.assertIn("die letzten 3 Batches sind C (ab B241)", zeile)
        self.assertIn("Anteil fuer die Rechnung: 100 %", zeile)

    def test_kalenderzeile_ohne_50_prozent_abschlag(self):
        d = dict(stand.durchsatz(self.cfg), rate_c_koepfe=6.0, rate_c_quelle="Median (Test)")
        zeilen = "\n".join(stand.kalender_zeilen(self.cfg, 30, d))
        self.assertIn("-> 5 C-Batches bei +6.0 Koepfe je C-Batch", zeilen)
        self.assertIn("ca. 5 KALENDER-Batches", zeilen)      # 5 / 1.0, nicht 5 / 0,5
        self.assertNotIn("ca. 10 KALENDER-Batches", zeilen)

    def test_verifizierter_trend_steht_daneben(self):
        v = stand.verifiziert_trend(self.cfg)
        self.assertTrue(v["gemessen"], v.get("grund"))
        self.assertEqual((v["erst"]["batch"], v["erst"]["verifiziert"]), (236, 87))
        self.assertEqual((v["letzt"]["batch"], v["letzt"]["verifiziert"]), (243, 92))
        self.assertEqual(v["delta"], 5)
        reihe = {e["batch"]: e["verifiziert"] for e in v["reihe"]}
        self.assertEqual(reihe[237], 90)
        # Die Reihe B237..B243 darin: +2 - der Kopfzaehler meldet im selben Fenster +4
        # (der Kopf 800660D4 ist nur deshalb "referenzgleich", weil der Pruefstand am
        # `bctr` aufhoert; M243-3).
        self.assertEqual(reihe[243] - reihe[237], 2)

    def test_durchsatzzeile_und_bilanz_nennen_ihn(self):
        text = "\n".join(stand.durchsatz_zeilen(self.cfg))
        self.assertIn("Trend C verifiziert (Bahnabdeckung", text)
        self.assertIn("B236 87 -> B243 92 = +5", text)
        self.assertIn("Rate C verifiziert: Median +1 je C-Batch", text)
        btext = "\n".join(bilanz._c_trend_zeile(self.cfg))
        self.assertIn("C verifiziert: B236 87 -> B243 92 = +5", btext)
        self.assertIn("Median +1 je C-Batch", btext)

    def test_hochrechnung_mit_verifiziertem_zuwachs(self):
        d = dict(stand.durchsatz(self.cfg), rate_c_koepfe=6.0, rate_c_quelle="Median (Test)")
        zeilen = "\n".join(stand.kalender_zeilen(self.cfg, 30, d))
        self.assertIn("VERIFIZIERTEN Zuwachs (+1.0 Koepfe je C-Batch", zeilen)
        self.assertIn("ca. 30 C-Batches (HYPOTHESIS", zeilen)


if __name__ == "__main__":
    unittest.main()
