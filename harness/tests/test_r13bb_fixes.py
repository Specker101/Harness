"""Tests fuer R13bb (2026-09-30): vier Harness-Punkte aus Aussensicht B224 / Review B225.

Punkt 1 (dieser Teil): FORTSETZUNG NACH EINEM FRUEHEN PREFLIGHT WIEDER ERLAUBEN (R13ax
anpassen). R13bb erlaubte sie, solange bis zur Umschaltschwelle mindestens
`limits.fortsetzung_min_rest_min` (Default 20) Minuten blieben - darunter blieb es beim
UEBERTRAG. **R13bw (05.10.2026, Aussensicht M268-3) hat diesen Rest-Vorbehalt aufgehoben:**
die Uhr entscheidet allein, der Rest steht nur noch als `rest_min`/`rest_knapp` im Beleg.
Gemessen endeten mit der Bremse B255 (132,5 min), B259 (127,9), B260 (130,6), B264 (130,9)
und B268 (119,2) vor der Umschaltschwelle von 135 min.
Grund der Lockerung (R13bb, gemessen): der Preflight dauert jetzt ~5 min, B224 endete bei
45 min mit 3/5 Koepfen.

Wegwerf-Verzeichnisse unter `tests/_tmp_r13bb`; die Konfiguration wird gelesen (der neue
Schluessel steht in `harness.toml`).
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

from hx import stand, streamjson, worker                            # noqa: E402
from hx.config import load_config                                   # noqa: E402
from hx.orchestrator import Orchestrator                           # noqa: E402
from hx.util import ensure_dir, read_text_erkannt                   # noqa: E402

TOML = ROOT / "harness.toml"
# R13bc: der eingefrorene Stand (30.09.2026, B224) - nicht nachziehen, s. README dort.
FIXTURE = ROOT / "tests" / "fixtures" / "stand_b224"
AUFTRAG = ("TEIL 1: etwas bauen.\n\n## NACHRUECKLISTE\n1. Posten eins\n2. Posten zwei\n")
TEXT = ("Kein Fortsetzungsanstoss: Preflight bereits gelaufen, offene Nachrueckliste "
        "-> UEBERTRAG")


def _assistant(mid: str, kontext: int, werkzeug: str | None = None) -> str:
    bloecke: list[dict] = []
    if werkzeug:
        bloecke.append({"type": "tool_use", "id": f"tu-{mid}", "name": werkzeug,
                        "input": {"file_path": "x"}})
    return json.dumps({"type": "assistant", "timestamp": "2026-09-30T00:00:00Z",
                       "message": {"id": mid, "model": "m", "content": bloecke,
                                   "usage": {"input_tokens": kontext}}})


def _result(kontext: int) -> str:
    return json.dumps({"type": "result", "subtype": "success", "num_turns": 5,
                       "result": "fertig", "is_error": False,
                       "usage": {"input_tokens": kontext}})


def preflight_aufruf() -> dict:
    """Ein ECHTER Preflight-Start (PowerShell-Aufruf mit `preflight.py`)."""
    return {"zeile": 1, "ts": "2026-09-30T00:00:00Z", "id": "tu-pf",
            "name": "PowerShell",
            "input": {"command": "python -u scripts/preflight.py before *> out.txt",
                      "description": "Preflight"}}


class TestFortsetzungNachFruehemPreflight(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config()

    def _stats(self, kontext: int = 300000, preflight: bool = False):
        s = streamjson.StreamStats()
        s.feed(_assistant("m1", 1000))
        s.feed(_assistant("m2", kontext))
        s.feed(_result(kontext))
        if preflight:
            s.tools.append(preflight_aufruf())
        return s
    @staticmethod
    def _run():
        from hx.proc import StreamRun
        r = StreamRun()
        r.rc = 0
        r.killed_reason = None
        return r

    def umschalt(self) -> float:
        return float(worker.umschalt_minuten(self.cfg)["umschalt_min"])

    def entsch(self, minuten: float, preflight: bool = True, auftrag: str = AUFTRAG):
        return worker.fortsetzung_pruefen(self.cfg, self._run(), self._stats(preflight=preflight),
                                          auftrag, minuten, [])

    def test_schwelle_steht_in_der_konfiguration(self):
        self.assertEqual(float(self.cfg.get("limits", "fortsetzung_min_rest_min", 0)), 20.0)
        self.assertIn("fortsetzung_min_rest_min = 20", TOML.read_text(encoding="utf-8"))

    def test_genug_zeit_wird_angestossen(self):
        u = self.umschalt()
        e = self.entsch(u - 25)
        self.assertTrue(e["ja"], e)
        self.assertTrue(e["preflight_erneut"])
        self.assertFalse(e.get("uebertrag"))
        self.assertGreaterEqual(e["rest_min"], 20)

    def test_unter_20_min_wird_jetzt_angestossen(self):
        """R13bw: der Rest ist keine Bremse mehr - nur noch eine Merkgrenze."""
        u = self.umschalt()
        e = self.entsch(u - 10)
        self.assertTrue(e["ja"], e)
        self.assertTrue(e["preflight_erneut"])
        self.assertLess(e["rest_min"], 20)
        self.assertTrue(e["rest_knapp"])
        self.assertFalse(e.get("uebertrag"))
        self.assertFalse(e.get("grund"))

    def test_genau_20_min_zaehlt_als_genug(self):
        """Die Merkgrenze ist einschliesslich: bei genau 20 min Rest ist nichts knapp."""
        u = self.umschalt()
        e = self.entsch(u - 20)
        self.assertTrue(e["ja"], e)
        self.assertFalse(e.get("rest_knapp"))

    def test_merkgrenze_ist_einstellbar(self):
        """`fortsetzung_min_rest_min` wird gelesen - als Merkgrenze, nicht als Bremse."""
        self.cfg.data["limits"]["fortsetzung_min_rest_min"] = 60
        u = self.umschalt()
        e = self.entsch(u - 25)
        self.assertTrue(e["ja"], e)
        self.assertTrue(e["rest_knapp"])
        self.assertFalse(e.get("uebertrag"))

    def test_ohne_preflight_aendert_sich_nichts(self):
        u = self.umschalt()
        e = self.entsch(u - 25, preflight=False)
        self.assertTrue(e["ja"])
        self.assertFalse(e.get("preflight_erneut"))

    def test_frueher_abbruch_bleibt_abbruch(self):
        """Die Lockerung gilt nur fuer den Preflight-Fall, nicht fuer Abbrueche."""
        u = self.umschalt()
        r = self._run()
        r.killed_reason = "cancel"
        e = worker.fortsetzung_pruefen(self.cfg, r, self._stats(preflight=True),
                                       AUFTRAG, u - 25, [])
        self.assertFalse(e["ja"])
        self.assertIn("cancel", e["grund"])
        self.assertFalse(e.get("uebertrag"))
        self.assertFalse(e.get("preflight_erneut"))

    def test_ohne_nachrueckliste_kein_anstoss(self):
        u = self.umschalt()
        e = self.entsch(u - 25, auftrag="TEIL 1 ohne Liste.")
        self.assertFalse(e["ja"])
        self.assertIn("NACHRUECKLISTE", e["grund"])


class TestAnstossTextUndAblauf(unittest.TestCase):
    """Der Anstoss sagt den neuen Preflight an, und der alte Stand wird vorher archiviert."""

    def test_text_nennt_den_neuen_preflight(self):
        text = worker.fortsetzungs_text(50.0, 300000, 90.0, self._u(), batch=224,
                                        preflight_erneut=True)
        self.assertIn("Nach der Nacharbeit neuer Preflight, der letzte gilt", text)
        self.assertIn("überholt", text)
        self.assertIn("Batch 224", text)

    @staticmethod
    def _u() -> float:
        return float(load_config().get("limits", "alarm_wall_s", 5400)) / 60.0 - 15.0

    def test_ohne_preflight_kein_zusatz(self):
        text = worker.fortsetzungs_text(50.0, 300000, 90.0, self._u(), batch=224)
        self.assertNotIn("neuer Preflight", text)
        self.assertNotIn("überholt", text)

    def test_archiv_laeuft_vor_dem_anstoss(self):
        """R13ah-Code bleibt die Stelle, die den Stand vor der Fortsetzung sichert."""
        quelle = inspect.getsource(worker.run_batch)
        self.assertIn("archiviere_preflight_vor_fortsetzung(", quelle)
        self.assertLess(quelle.index("archiviere_preflight_vor_fortsetzung("),
                        quelle.index("fortsetz_text = fortsetzungs_text("))

    def test_der_anstoss_wird_als_preflight_erneut_vermerkt(self):
        quelle = inspect.getsource(worker.run_batch)
        self.assertIn('"preflight_erneut": bool(entsch.get("preflight_erneut"))', quelle)
        self.assertIn('log.info("Fortsetzung trotz Preflight"', quelle)
        # R13bf (Teil D): der Text verlangt den neuen Preflight nur noch, wenn seit dem
        # letzten Preflight unter port/ oder scripts/ etwas geaendert wurde.
        self.assertIn('preflight_erneut=bool(pf_neu)', quelle)
        self.assertIn('preflight_geprueft=bool(hatte_preflight and not pf_neu)', quelle)
        self.assertIn('"preflight_neu": bool(pf_neu)', quelle)


class Basis(unittest.TestCase):
    """Wegwerf-Harness mit Wegwerf-Decomp-Repo (fuer die Punkte 2-4)."""

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13bb"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "root")
        self.decomp = ensure_dir(self.tmp / "decomp")
        self.ana = ensure_dir(self.decomp / "analysis")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.decomp)
        cfg.data["paths"]["harness_home"] = str(self.tmp)
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestPreflightZaehlerArchiv(Basis):
    """Punkt 2 (Befund M224-4): der Preflight-Zaehler gegen die archivierten Laeufe."""

    def archiv(self, batch: int, name: str) -> Path:
        d = ensure_dir(self.ana / f"_m{batch}")
        p = d / name
        p.write_text(f"# Preflight {batch}\n", encoding="utf-8")
        return p

    def aufruf(self, batch: int, n: int, frueh: bool = True) -> None:
        d = ensure_dir(Path(self.root) / "runs" / f"b{batch:03d}")
        zeilen = [json.dumps({"ts": f"2026-09-30T0{i}:00:00+00:00", "min": 40.0 + i,
                              "frueh": frueh, "werkzeug": "PowerShell"})
                  for i in range(n)]
        (d / "preflight-aufrufe.jsonl").write_text("\n".join(zeilen) + "\n", encoding="utf-8")

    def test_fehllauf_ist_die_differenz(self):
        self.aufruf(224, 1)
        self.archiv(224, "_preflight_224_fehllauf1.txt")
        self.archiv(224, "_preflight_224.txt")
        a = stand.preflight_archiv(self.cfg, 224)
        self.assertEqual(a["fehllauf"], ["analysis/_m224/_preflight_224_fehllauf1.txt"])
        self.assertEqual(a["ungezaehlt"], 1)
        zeile = stand.preflight_zaehler_zeile(self.cfg, 224)[0]
        self.assertIn("1 Aufruf(e) im Mitschnitt", zeile)
        self.assertIn("_preflight_224_fehllauf1.txt", zeile)
        self.assertIn("-> 2 Laeufe", zeile)

    def test_vor_fortsetzung_zaehlt_nicht(self):
        """R13ah-Kopien sind byteweise Kopien eines gezaehlten Laufs."""
        self.aufruf(218, 2)
        self.archiv(218, "_preflight_218_vor_fortsetzung1.txt")
        self.archiv(218, "_preflight_218.txt")
        a = stand.preflight_archiv(self.cfg, 218)
        self.assertEqual(a["ungezaehlt"], 0)
        self.assertNotIn("vor_fortsetzung", " ".join(a["dateien"]))
        self.assertIn("keine archivierten Fehllaeufe",
                      stand.preflight_zaehler_zeile(self.cfg, 218)[0])

    def test_nicht_lauf_dateien_zaehlen_nicht(self):
        self.aufruf(224, 1)
        for name in ("_preflight_224_zeiten.txt", "_preflight_224_vergleich.txt",
                     "_preflight_224_stderr.txt"):
            self.archiv(224, name)
        self.assertEqual(stand.preflight_archiv(self.cfg, 224)["ungezaehlt"], 0)

    def test_ueberholt_wird_benannt_aber_nicht_addiert(self):
        """Ein ueberholter Lauf kann im Mitschnitt schon gezaehlt sein - darum getrennt."""
        self.aufruf(220, 2)
        self.archiv(220, "_preflight_220_ueberholt1.txt")
        self.archiv(220, "_preflight_220_lauf2_ueberholt.txt")
        a = stand.preflight_archiv(self.cfg, 220)
        self.assertEqual(a["ungezaehlt"], 0)
        self.assertEqual(len(a["ueberholt"]), 2)
        zeile = stand.preflight_zaehler_zeile(self.cfg, 220)[0]
        self.assertIn("2 Aufruf(e) im Mitschnitt", zeile)
        self.assertIn("ueberholt abgelegt", zeile)
        self.assertNotIn("-> 4 Laeufe", zeile)

    def test_ohne_archiv_keine_differenz(self):
        self.aufruf(226, 1, frueh=False)
        zeile = stand.preflight_zaehler_zeile(self.cfg, 226)[0]
        self.assertIn("1 Aufruf(e) im Mitschnitt (davon 0 zu frueh)", zeile)
        self.assertIn("keine archivierten Fehllaeufe (_m226)", zeile)

    def test_ungueltige_zeilen_zaehlen_nicht(self):
        d = ensure_dir(Path(self.root) / "runs" / "b227")
        (d / "preflight-aufrufe.jsonl").write_text('{"ts": "x"}\nkaputt\n\n',
                                                   encoding="utf-8")
        self.assertEqual(stand.zaehle_preflight_aufrufe(self.cfg, 227), (1, 0))

    def test_result_json_traegt_die_differenz(self):
        quelle = inspect.getsource(worker._finish_run)
        self.assertIn('pf_archiv = stand.preflight_archiv(cfg, batch)', quelle)
        self.assertIn('"preflight_ungezaehlt": pf_archiv["ungezaehlt"]', quelle)
        # R13be-1: die Gesamtzahl ist das Maximum aus Mitschnitt und (Hook + Fehllaeufe).
        self.assertIn('"preflight_laeufe_gesamt": max(int(preflight_laeufe)', quelle)
        self.assertIn('int(hook_laeufe) + int(pf_archiv["ungezaehlt"])', quelle)
        self.assertIn('"preflight_archiv_fehllauf"', quelle)
        self.assertIn("archivierte Fehllaeufe nicht gezaehlt", quelle)

    def test_review_fakten_nennen_den_abgleich(self):
        from hx.orchestrator import Orchestrator
        quelle = inspect.getsource(Orchestrator.harness_facts)
        self.assertIn("standmod.preflight_zaehler_zeile(", quelle)
        self.assertIn('res.get("preflight_laeufe")', quelle)


class TestRueckblickFesterStand(Basis):
    """Die drei Batches aus M224-4, gegen den **eingefrorenen Stand** `stand_b224`.

    Frueher las der Rueckblick die lebenden Dateien und schaltete sich ab, sobald der
    naechste Batch eigene Messdateien anlegte - ein Test, der sich abschaltet, prueft nichts.
    """

    BATCHES = {218: (2, 1), 223: (1, 1), 224: (1, 1)}   # (Aufrufe im Mitschnitt, Fehllaeufe)

    def setUp(self):
        super().setUp()
        shutil.copytree(FIXTURE / "root", self.root, dirs_exist_ok=True)
        shutil.copytree(FIXTURE / "decomp", self.decomp, dirs_exist_ok=True)
        self.ana = self.decomp / "analysis"

    def test_rueckblick_stimmt(self):
        for batch, (aufrufe, fehllauf) in self.BATCHES.items():
            a = stand.preflight_archiv(self.cfg, batch)
            self.assertEqual(a["ungezaehlt"], fehllauf, batch)
            self.assertEqual(a["fehllauf"],
                             [f"analysis/_m{batch}/_preflight_{batch}_fehllauf1.txt"], batch)
            self.assertEqual(stand.zaehle_preflight_aufrufe(self.cfg, batch)[0], aufrufe, batch)
            zeile = stand.preflight_zaehler_zeile(self.cfg, batch)[0]
            self.assertIn(f"-> {aufrufe + fehllauf} Laeufe", zeile)

    def test_ueberholt_zaehlt_nicht_mit(self):
        """Der feste Stand fuehrt keine ueberholten Dateien dieser Batches."""
        for batch in self.BATCHES:
            self.assertEqual(stand.preflight_archiv(self.cfg, batch)["ueberholt"], [], batch)


class TestMischregelDerPrognose(Basis):
    """Punkt 3 (Befund M224-5): die Prognose nimmt die **geltende** Regel des Plans."""

    ALT = ("- **Mischverhaeltnis 2 B : 1 C (ENTSCHEIDUNG Reviewer):** B208 B, B209 B, B210 C\n"
           "  (A1 MEM-Varianten), danach wieder 2:1.\n")
    NEU = ("  **AB B222 GILT 1 B : 1 C (NUTZERENTSCHEIDUNG R221-1, 2026-09-30, wortgetreu):**\n"
           '  "1 B : 1 C". Praezisierung (1): vor dem Anbinden wird GEMESSEN.\n')

    def plan_schreiben(self, *teile: str) -> None:
        (self.ana / "hybrid-plan.md").write_text(
            "# Plan fuer Strang B - Hybrid-Laeufer (Entscheidung A4)\n\n" + "".join(teile),
            encoding="utf-8", newline="\n")

    def test_geltende_zeile_gewinnt_gegen_entscheidung(self):
        self.plan_schreiben(self.ALT, self.NEU)
        p = stand.plan_mischung(self.cfg)
        self.assertEqual(p["regel"], "1 B : 1 C")
        self.assertEqual(p["anteil"], 0.5)
        self.assertEqual(p["zustand"], "gilt")
        self.assertEqual(p["ab_batch"], 222)
        self.assertIn("R221-1", p["stand"])
        self.assertIn("2026-09-30", p["stand"])
        self.assertTrue(p["erkannt"])

    def test_alte_zeile_bleibt_gueltig_wenn_keine_gilt_zeile_da_ist(self):
        self.plan_schreiben(self.ALT)
        p = stand.plan_mischung(self.cfg)
        self.assertEqual(p["regel"], "2 B : 1 C")
        self.assertEqual(round(p["anteil"], 4), 0.3333)
        self.assertEqual(p["zustand"], "entschieden")
        self.assertIsNone(p["ab_batch"])

    def test_paarliste_bleibt_lesbar(self):
        """Die Paarliste kommt NUR aus der gewaehlten Zeile (R13an) - die alte Aufzaehlung
        darf keinen Batch umdeuten. Die geltende Zeile nennt keine Einzelbatches."""
        self.plan_schreiben(self.ALT, self.NEU)
        p = stand.plan_mischung(self.cfg)
        self.assertEqual(p["regel"], "1 B : 1 C")
        self.assertEqual(p["paare"], {}, "die ueberholte Zeile liefert keine Paare mehr")

    def test_ohne_verhaeltnis_bleibt_erkannt_falsch(self):
        self.plan_schreiben("- **Mischverhaeltnis 2:1 ab B217 voraussichtlich B221**\n")
        p = stand.plan_mischung(self.cfg)
        self.assertFalse(p["erkannt"])
        self.assertIsNone(p["anteil"])
        self.assertIn("kein Verhaeltnis", p["grund"])

    def test_prognosezeile_nennt_quelle_und_stand(self):
        self.plan_schreiben(self.ALT, self.NEU)
        d = stand.durchsatz(self.cfg)
        self.assertEqual(d["anteil_c"], 0.5)
        self.assertIn("Regel hybrid-plan.md:", d["anteil_quelle"])
        self.assertIn('"1 B : 1 C"', d["anteil_quelle"])
        self.assertIn("ab B222", d["anteil_quelle"])
        self.assertNotIn("2 B : 1 C", d["anteil_quelle"])
        # Die Kalender-Zeile uebernimmt Quelle und Stand der Regel.
        zeilen = stand.kalender_zeilen(self.cfg, 30, dict(d, rate_c_koepfe=6.0,
                                                          rate_c_quelle="Median (Test)"))
        self.assertTrue(zeilen, zeilen)
        self.assertIn("ab B222", "\n".join(zeilen))
        self.assertIn("Anteil 50 %", "\n".join(zeilen))


class TestPlanMischregelFesterStand(Basis):
    """Der Plan des festen Stands: die Gilt-Zeile gewinnt (Punkt 3, M224-5)."""

    def setUp(self):
        super().setUp()
        shutil.copytree(FIXTURE / "root", self.root, dirs_exist_ok=True)
        shutil.copytree(FIXTURE / "decomp", self.decomp, dirs_exist_ok=True)
        self.ana = self.decomp / "analysis"
        self.pfad = self.ana / "hybrid-plan.md"

    def test_geltende_regel_ist_1_zu_1(self):
        p = stand.plan_mischung(self.cfg)
        self.assertEqual(p["zustand"], "gilt")
        self.assertEqual(p["regel"], "1 B : 1 C")
        self.assertEqual(p["anteil"], 0.5)
        self.assertEqual(p["ab_batch"], 222)
        self.assertEqual(p["zeile_nr"], 368)
        self.assertEqual(p["stand"], "ab B222, NUTZERENTSCHEIDUNG R221-1, 2026-09-30")
        self.assertEqual(p["paare"], {}, "die Gilt-Zeile nennt keine Einzelbatches")
        # Die genannte Zeile traegt wirklich das, was der Harness ihr zuschreibt.
        zeilen = self.pfad.read_text(encoding="utf-8", errors="replace").splitlines()
        self.assertIn("GILT 1 B : 1 C", zeilen[p["zeile_nr"] - 1])

    def test_prognose_nennt_quelle_und_stand(self):
        d = stand.durchsatz(self.cfg)
        self.assertEqual(d["anteil_c"], 0.5)
        self.assertIn("Regel hybrid-plan.md:368", d["anteil_quelle"])
        self.assertIn('"1 B : 1 C"', d["anteil_quelle"])
        self.assertIn("ab B222", d["anteil_quelle"])
        self.assertNotIn("2 B : 1 C", d["anteil_quelle"])
        text = "\n".join(stand.durchsatz_zeilen(self.cfg))
        self.assertIn("jeder 2. Batch ist ein C-Batch (50 %)", text)
        self.assertNotIn("jeder 3. Batch", text)          # die ueberholte 2:1-Regel

    def test_kalenderzeile_nennt_die_grundlage(self):
        d = stand.durchsatz(self.cfg)
        raten = stand.c_rate(self.cfg)
        d = dict(d, rate_c_koepfe=raten["rate"], rate_c_quelle=raten["quelle"])
        zeilen = stand.kalender_zeilen(self.cfg, d["offen_koepfe"], d)
        self.assertIn("Anteil 50 %", zeilen[1])
        self.assertIn("ab B222", zeilen[1])


class TestPaketEKopfzeile(Basis):
    """Punkt 4 (M224-4): die Paket-E-Messdatei wird kodierungstolerant gelesen.

    `_m224/_c_paket_e_nachher.txt` ist **UTF-8-BOM**: mit `read_text` (UTF-8) stand das BOM
    vor dem `#`, das Messdatum passte nicht auf das Muster, und die Datei galt als
    datumslos (PARSER-Meldung + "Datum aus Dateizeit").
    """

    KOPF = "# Messung: 2026-09-30 16:55, HEAD 217cce8\r\n"

    def messdatei(self, batch: int, name: str, kopf: str, kodierung: str = "utf-8",
                  stand: str = "nachher", koepfe: int = 20, insn: int = 1657) -> Path:
        d = ensure_dir(self.ana / f"_m{batch}")
        p = d / name
        text = (kopf + "== ERGEBNIS ==\r\n"
                f"  Paket E, offen GESAMT   :   {koepfe} Koepfe /   {insn} Insn\r\n")
        if kodierung == "utf-16-le":
            p.write_bytes(b"\xff\xfe" + text.encode("utf-16-le"))
        else:
            p.write_text(text, encoding=kodierung, newline="")
        return p

    def test_bom_datei_datum_wird_erkannt(self):
        """Genau der B224-Fall: BOM statt UTF-8."""
        self.messdatei(224, "_c_paket_e_nachher.txt", self.KOPF, kodierung="utf-8-sig")
        m = stand.paket_e_messung(self.cfg)
        self.assertEqual(m["batch"], 224)
        self.assertEqual(m["datum"], "2026-09-30 16:55")
        self.assertEqual(m["datum_quelle"], "kopf")
        self.assertEqual(m["kodierung"], "utf-8-bom")
        self.assertEqual(stand.paket_e_datum_hinweis(self.cfg), [],
                         "kein PARSER-Hinweis bei erkanntem Datum")

    def test_utf16_datei_datum_wird_erkannt(self):
        self.messdatei(224, "_c_paket_e_nachher.txt", self.KOPF, kodierung="utf-16-le")
        m = stand.paket_e_messung(self.cfg)
        self.assertEqual(m["datum"], "2026-09-30 16:55")
        self.assertEqual(m["kodierung"], "utf-16-le")
        hinweis = stand.paket_e_datum_hinweis(self.cfg)
        self.assertEqual(len(hinweis), 1)
        self.assertIn("in utf-16-le gelesen", hinweis[0])
        self.assertIn("Datum erkannt", hinweis[0])

    def test_ohne_datum_bleibt_der_parser_hinweis(self):
        """Gegenprobe: fehlt die Datumszeile wirklich, wird weiter gemeldet."""
        self.messdatei(222, "_c_paket_e.txt", "# Erzeuger: c_kopf.py paket_e\r\n",
                       kodierung="utf-8")
        hinweis = stand.paket_e_datum_hinweis(self.cfg)
        self.assertEqual(len(hinweis), 1)
        self.assertIn("PARSER: Messdatum in _m222/_c_paket_e.txt nicht erkannt", hinweis[0])

    def test_bom_ohne_erkennung_waere_der_fehler(self):
        """Der Beweis: mit reinem UTF-8-Lesen passt das Muster nicht (BOM vor dem #)."""
        p = self.messdatei(224, "_c_paket_e_nachher.txt", self.KOPF, kodierung="utf-8-sig")
        roh_utf8 = p.read_bytes().decode("utf-8")
        self.assertFalse(stand.RE_PAKET_E_DATUM[0].search(roh_utf8),
                         "mit BOM vor dem # findet der alte Weg kein Datum")
        text, kodierung = read_text_erkannt(p)
        self.assertTrue(stand.RE_PAKET_E_DATUM[0].search(text))
        self.assertEqual(kodierung, "utf-8-bom")


class TestPaketEDateiFesterStand(Basis):
    """Die B224-Datei des festen Stands: UTF-8-BOM, Datum erkannt, keine PARSER-Meldung."""

    def setUp(self):
        super().setUp()
        shutil.copytree(FIXTURE / "root", self.root, dirs_exist_ok=True)
        shutil.copytree(FIXTURE / "decomp", self.decomp, dirs_exist_ok=True)
        self.ana = self.decomp / "analysis"
        self.m = stand.paket_e_messung(self.cfg)

    def test_b224_nachher_datum_erkannt_ohne_parser_meldung(self):
        self.assertEqual(self.m["datei"], "_m224/_c_paket_e_nachher.txt")
        self.assertEqual(self.m["kodierung"], "utf-8-bom")
        self.assertEqual(self.m["datum"], "2026-09-30 16:55")
        self.assertEqual(self.m["datum_quelle"], "kopf")
        self.assertEqual(stand.paket_e_datum_hinweis(self.cfg), [],
                         "die BOM-Datei gilt nicht mehr als datumslos")
        # Gegenprobe im selben Stand: die blosse B224-Datei (UTF-8 ohne BOM) traegt
        # denselben Wert; nur `nachher` gewinnt die Auswahl.
        roh = self.ana / "_m224" / "_c_paket_e.txt"
        text, kod = read_text_erkannt(roh)
        self.assertEqual(kod, "utf-8")
        self.assertTrue(stand.RE_PAKET_E_DATUM[0].search(text))
        self.assertIn("20 Koepfe", text)

    def test_die_parser_meldung_haengt_an_dieser_funktion(self):
        """Die Review-Fakten rufen genau den Hinweis auf, der hier geprueft wird."""
        quelle = inspect.getsource(Orchestrator.harness_facts)
        self.assertIn("paket_e_datum_hinweis", quelle)
        self.assertEqual([z for z in stand.paket_e_datum_hinweis(self.cfg)
                          if "Messdatum" in z], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
