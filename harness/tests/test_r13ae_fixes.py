"""Tests fuer R13ae (2026-09-29): Preflight-Zeilen tolerant lesen und laut melden,
Umschaltschwelle auf 75 min.

**Anlass (gemessen, `analysis/_preflight_212.txt` / `_213.txt`).** Das Decomp-Werkzeug
schreibt die C-Kopfzeile seit B212 als

    C Koepfe referenzgleich 78 / 4006 / 0

Das Muster in `hx/stand.py` verlangte die Zahlen **direkt** hinter dem Etikett
(`^C Koepfe\\s+(\\d+)`) und erkannte die Zeile nicht mehr. Der Parser lieferte still
`None`: `c_trend` endete bei B211 und zeigte weiter **2795** statt der gemessenen **4006**.

Feste Regeln, die diese Datei prueft:

  1. Zwischen Etikett und Zahlen darf Prosa stehen ("referenzgleich"), hinter den Zahlen
     ein Zusatz ("| ausgeduennt 12") - fuer **alle** Preflight-Zeilen-Parser.
  2. Fehlt eine erwartete Zeile in einer VORHANDENEN Preflight-Datei, gibt es eine
     WARN-Zeile im Log UND eine Zeile `PARSER: Zeile <Name> in _preflight_<N>.txt nicht
     erkannt` in den Review-Fakten - kein stilles `None`.
  3. `limits.umschalt_vor_alarm_s` = 900 s -> Umschaltschwelle **75 min** (der Preflight
     dauert selbst ~10 min, B213: 602 s; bei 80 min lief jeder volle Batch ueber den
     90-min-Alarm, B213 mit 104 min).

Die Tests mit den echten Dateien laufen gegen `g:\\Silent Scope Decomp` (Muster wie R13ac:
**eingefroren kopieren**, nicht das lebende Fenster lesen - waehrend der Testreihe laeuft
der Harness und schreibt neue Preflight-Dateien).
"""

from __future__ import annotations

import json
import shutil
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import stand, uhr, worker                                  # noqa: E402
from hx.config import load_config                                  # noqa: E402
from hx.orchestrator import Orchestrator                           # noqa: E402
from hx.util import Log, ensure_dir, write_text_atomic             # noqa: E402

# Zwei echte Kopfzeilenformen: B211 (alt) und B213 (neu, "referenzgleich").
KOPF_ALT = "C Koepfe           78 / 2795 / 0                                   OK"
KOPF_NEU = "C Koepfe referenzgleich 78 / 4006 / 0                             OK"
BAHN = "Bahnabdeckung      57/78 | Bloecke 335/434 | verifiziert 60 | teilgeprueft 18 OK"
HYBRID = "Hybrid-Lauf        215 | 800138F0 | MMIO | 28/407 | 0                OK"


def preflight_text(*zeilen: str) -> str:
    return ("=== PREFLIGHT (before) 2026-09-29 14:58 ===\n"
            "Lauf 2026-09-29 14:58:50 | HEAD b672641\n"
            + "\n".join(zeilen) + "\n=> BEFORE SAUBER\n")


class Basis(unittest.TestCase):
    """Wegwerf-Workspace mit eigenem 'decomp'-Repo (nur `analysis/`)."""

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13ae"
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

    def preflight(self, batch: int, *zeilen: str) -> Path:
        p = self.ana / f"_preflight_{batch}.txt"
        write_text_atomic(p, preflight_text(*zeilen))
        return p

    def warnungen(self) -> list[dict]:
        """Nur die Parser-Warnungen (das Log traegt auch Telegram-/Queue-Meldungen)."""
        if not self.log.path.is_file():
            return []
        raus: list[dict] = []
        for z in self.log.path.read_text(encoding="utf-8").splitlines():
            if not z.strip():
                continue
            satz = json.loads(z)
            if satz.get("msg") == "Preflight-Zeile nicht erkannt":
                raus.append(satz)
        return raus


# ------------------------------------------------- 1) Zeilen tolerant lesen
class TestZeilenTolerant(Basis):
    """Zwischen Etikett und Zahlen darf Prosa stehen, hinter den Zahlen ein Zusatz."""

    def test_b211_form_wird_gelesen(self):
        self.preflight(211, KOPF_ALT)
        e = stand.preflight_c_koepfe(self.cfg, 4)[-1]
        self.assertEqual((e["batch"], e["koepfe"], e["faelle"], e["abweichungen"]),
                         (211, 78, 2795, 0))

    def test_b212_b213_form_mit_referenzgleich_wird_gelesen(self):
        """Der Anlass: `C Koepfe referenzgleich 78 / 4006 / 0` (vorher stilles None)."""
        self.preflight(212, "C Koepfe referenzgleich 78 / 2795 / 0   OK")
        self.preflight(213, KOPF_NEU)
        reihe = stand.preflight_c_koepfe(self.cfg, 4)
        self.assertEqual([(e["batch"], e["faelle"]) for e in reihe], [(212, 2795), (213, 4006)])

    def test_zusatz_hinter_den_zahlen(self):
        self.preflight(213, "C Koepfe 78 / 4006 / 0 | ausgeduennt 12")
        self.preflight(214, "C Koepfe referenzgleich 78 / 4006 / 0 referenzgleich")
        self.assertEqual([(e["batch"], e["faelle"]) for e in stand.preflight_c_koepfe(self.cfg, 4)],
                         [(213, 4006), (214, 4006)])

    def test_die_luecke_enthielt_keine_ziffern_sonst_keine_zeile(self):
        """Die Luecke zwischen Etikett und Zahlen ist auf Zeichen OHNE Ziffern begrenzt -
        eine unvollstaendige Zeile darf sich ihre Zahlen nicht aus der naechsten holen."""
        self.preflight(213, "C Koepfe           78",
                       "C Einbindung       8 / 20 / 51                        Meldung")
        self.assertEqual(stand.preflight_c_koepfe(self.cfg, 4), [])

    def test_c_trend_ueber_die_neue_form(self):
        self.preflight(211, KOPF_ALT)
        self.preflight(212, "C Koepfe referenzgleich 78 / 2795 / 0   OK")
        self.preflight(213, KOPF_NEU)
        t = stand.c_trend(self.cfg, 2)
        self.assertTrue(t["gemessen"])
        self.assertEqual((t["erst"]["batch"], t["erst"]["faelle"]), (211, 2795))
        self.assertEqual((t["letzt"]["batch"], t["letzt"]["faelle"]), (213, 4006))
        self.assertEqual(t["luecken"], [])

    def test_bahnabdeckung_tolerant(self):
        """Dieselbe Toleranz fuer die Bahnabdeckungszeile."""
        self.preflight(213, "Bahnabdeckung referenzgleich 57/78 | Bloecke 335/434 | "
                            "verifiziert 60 | teilgeprueft 18 OK", HYBRID)
        e = stand.preflight_bahnabdeckung(self.cfg, 4)[-1]
        self.assertEqual((e["koepfe"], e["gesamt"], e["verifiziert"], e["teilgeprueft"]),
                         (57, 78, 60, 18))
        self.assertEqual((e["bloecke"], e["bloecke_gesamt"]), (335, 434))
        self.assertEqual(e["quelle"], "Bahnabdeckung")

    def test_nachrueckliste_bleibt_tolerant_und_hat_vorrang(self):
        self.preflight(213, BAHN, "Nachrueckliste 1   62/80 | verifiziert 62", HYBRID)
        e = stand.preflight_bahnabdeckung(self.cfg, 4)[-1]
        self.assertEqual(e["quelle"], "Nachrueckliste 1")
        self.assertEqual(e["verifiziert"], 62)


# --------------------------------------- 2) Fehlende Zeile: Log + Review-Fakten
class TestZeilenWarnung(Basis):
    def test_fehlende_kopfzeile_ergibt_die_warnung(self):
        self.preflight(213, BAHN, HYBRID)                    # C Koepfe fehlt
        meldungen = stand.preflight_zeilen_pruefen(self.cfg, log=self.log)
        self.assertEqual(meldungen,
                         ["PARSER: Zeile C Koepfe in _preflight_213.txt nicht erkannt"])
        warn = self.warnungen()
        self.assertEqual(len(warn), 1)
        self.assertEqual(warn[0]["level"], "WARN")
        self.assertEqual(warn[0]["zeile"], "C Koepfe")
        self.assertEqual(warn[0]["datei"], "_preflight_213.txt")
        self.assertEqual(warn[0]["parsen"], "preflight_c_koepfe")

    def test_fehlende_bahnabdeckung_und_hybrid_zeile(self):
        self.preflight(213, KOPF_NEU)                        # Bahn + Hybrid fehlen
        self.assertEqual(stand.preflight_zeilen_pruefen(self.cfg, log=self.log), [
            "PARSER: Zeile Bahnabdeckung in _preflight_213.txt nicht erkannt",
            "PARSER: Zeile Hybrid-Lauf in _preflight_213.txt nicht erkannt",
        ])
        self.assertEqual(len(self.warnungen()), 2)

    def test_vollstaendige_datei_wirft_keine_warnung(self):
        self.preflight(213, KOPF_NEU, BAHN, HYBRID)
        self.assertEqual(stand.preflight_zeilen_pruefen(self.cfg, log=self.log), [])
        self.assertEqual(self.warnungen(), [])

    def test_ohne_preflight_datei_eigene_meldung(self):
        self.assertEqual(stand.preflight_zeilen_pruefen(self.cfg, log=self.log),
                         ["PARSER: keine Preflight-Datei (analysis/_preflight_<N>.txt) "
                          "gefunden"])

    def test_alte_batches_werden_nicht_geprueft(self):
        """Nur die neuesten `anzahl` Dateien: B155..B197 fuehren die Zeile gar nicht."""
        self.preflight(198, "R207 tails         686 rueckwaerts (a 30 / b 0 / c 0)  OK")
        self.preflight(213, KOPF_NEU, BAHN, HYBRID)
        self.assertEqual(stand.preflight_zeilen_pruefen(self.cfg, log=self.log), [])
        alt = stand.preflight_zeilen_pruefen(self.cfg, log=self.log, anzahl=2)
        self.assertEqual(alt, ["PARSER: Zeile C Koepfe in _preflight_198.txt nicht erkannt",
                               "PARSER: Zeile Bahnabdeckung in _preflight_198.txt nicht "
                               "erkannt",
                               "PARSER: Zeile Hybrid-Lauf in _preflight_198.txt nicht "
                               "erkannt"])

    def test_erwartete_zeilen_sind_dieselben_muster_wie_die_parser(self):
        """Was geprueft wird, ist genau das, womit geparst wird (sonst Luege)."""
        namen = [e["name"] for e in stand.PREFLIGHT_ERWARTET]
        self.assertEqual(namen, ["C Koepfe", "Bahnabdeckung", "Hybrid-Lauf"])
        self.assertIs(stand.PREFLIGHT_ERWARTET[0]["muster"], stand._RE_PREFLIGHT_CKOPF)
        self.assertIs(stand.PREFLIGHT_ERWARTET[1]["muster"], stand._RE_BAHN_ZEILE)
        # Die Nachrueckliste ist OPTIONAL - sie steht nicht in der Pflichtliste.
        self.assertNotIn("Nachrueckliste", namen)


# ------------------------------------------- 3) Die Zeile in den Review-Fakten
class TestFaktenZeile(Basis):
    def orch(self) -> Orchestrator:
        o = Orchestrator(self.cfg, self.log, mock=True,
                         state_file=self.root / "harness" / "state" / "run.json")
        o.say = lambda *a, **k: None
        o.state.data["last_batch_number"] = 213
        return o

    def fakten(self) -> str:
        return self.orch().harness_facts(213, ziel=self.tmp / "out")

    def test_luecke_steht_in_den_fakten_und_im_log(self):
        self.preflight(213, KOPF_NEU, HYBRID)                # Bahnabdeckung fehlt
        text = self.fakten()
        self.assertIn("- PARSER: Zeile Bahnabdeckung in _preflight_213.txt nicht erkannt",
                      text)
        self.assertEqual([w["level"] for w in self.warnungen()], ["WARN"])        # Die Datei im Zielordner traegt dieselbe Zeile.
        self.assertIn("PARSER: Zeile Bahnabdeckung",
                      (self.tmp / "out" / "harness-facts.md").read_text(encoding="utf-8"))

    def test_ohne_luecke_steht_die_positive_zeile(self):
        self.preflight(213, KOPF_NEU, BAHN, HYBRID)
        text = self.fakten()
        self.assertIn("- Parser (R13ae): erwartete Zeilen gelesen, keine Luecke "
                      "(_preflight_213.txt: C Koepfe, Bahnabdeckung, Hybrid-Lauf)", text)
        self.assertNotIn("nicht erkannt", text)
        self.assertEqual(self.warnungen(), [])


# ------------------------------------------------------- 4) Umschaltschwelle 75
class TestZeitschwelle(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config()

    def test_config_ist_900_s_und_75_min(self):
        self.assertEqual(float(self.cfg.get("limits", "alarm_wall_s")), 5400.0)
        self.assertEqual(float(self.cfg.get("limits", "umschalt_vor_alarm_s")), 900.0)
        self.assertEqual((5400.0 - 900.0) / 60.0, 75.0)

    def test_anstoss_bei_74_minuten_keiner_bei_76(self):
        """Der Fortsetzungsanstoss haengt an derselben Zahl (EINE Zeitquelle)."""
        from hx import streamjson

        def stats() -> streamjson.StreamStats:
            s = streamjson.StreamStats()
            s.feed(json.dumps({"type": "assistant", "message": {
                "id": "m1", "model": "m", "usage": {"input_tokens": 1000},
                "content": [{"type": "text", "text": "x"}]}}))
            s.feed(json.dumps({"type": "result", "subtype": "success", "usage": {}, 
                               "num_turns": 1}))
            return s

        auftrag = "## NACHRUECKLISTE\n1. Kopf verifizieren\n"
        from hx.proc import StreamRun
        lauf = StreamRun()
        lauf.rc = 0
        frueh = worker.fortsetzung_pruefen(self.cfg, lauf, stats(), auftrag, 74.0, [])
        self.assertTrue(frueh["ja"], frueh)
        spaet = worker.fortsetzung_pruefen(self.cfg, lauf, stats(), auftrag, 76.0, [])
        self.assertFalse(spaet["ja"])
        self.assertIn("Umschaltschwelle 75 min", spaet["grund"])

    def test_uhr_vorgabe_ist_15_minuten_vor_der_alarmgrenze(self):
        start = datetime.now(timezone.utc) - timedelta(minutes=34)
        st = {"worker": {"pid": 1, "started_at": start.isoformat(timespec="seconds")},
              "live": {"batch": 213, "kontext": 310000}}
        text = uhr.uhr_text(st, 90, 180, kontext_limit=1000000)
        self.assertIn("Umschalten ab 75", text)
        self.assertIn("Umschaltschwelle 75 min", text)

    def test_hook_bekommt_die_75(self):
        tmp = Path(ROOT) / "tests" / "_tmp_r13ae_hook"
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            d = ensure_dir(tmp)
            start = datetime.now(timezone.utc) - timedelta(minutes=34)
            state_json = d / "run.json"
            write_text_atomic(state_json, json.dumps(
                {"worker": {"pid": 1, "started_at": start.isoformat(timespec="seconds")},
                 "live": {"batch": 213, "kontext": 310000}}))
            log = Log(d / "log.jsonl", echo=False)
            ziel = worker.write_worker_hooks(self.cfg, d, state_json, log)
            daten = json.loads(Path(ziel).read_text(encoding="utf-8"))
            args = daten["hooks"]["PostToolUse"][0]["hooks"][0]["args"]
            self.assertEqual(args[args.index("--umschalt") + 1], "75")
            self.assertEqual(args[args.index("--weich") + 1], "90")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_vorspann_und_reviewer_nennen_die_schwelle(self):
        pre = worker.WORKER_PREAMBLE
        # R13ah: die Schwelle ist `Alarmgrenze minus Vorlauf`, und der Vorlauf enthaelt die
        # gemessene Preflight-Dauer - die feste Zahl "900 s = 15 min" steht dort nicht mehr.
        self.assertIn("Alarmgrenze minus Vorlauf", pre)
        self.assertIn("Preflight zuletzt ~<p> min", pre)
        self.assertNotIn("Alarmgrenze minus 10 min", pre)
        rev = (Path(ROOT) / "prompts" / "reviewer.md").read_text(encoding="utf-8")
        self.assertIn("(Umschalten ab 75)", rev)
        self.assertIn("Alarm − max(15 min,", rev)
        self.assertNotIn("(Umschalten ab 80)", rev)


# ------------------------------------------------- 5) Gegenprobe: echte Dateien
class TestEchteDateien(unittest.TestCase):
    """Die echten B212/B213-Dateien - EINGEFROREN kopiert (FALLSTRICK aus R13ac: das
    lebende Fenster wandert, solange der Harness laeuft)."""

    @classmethod
    def setUpClass(cls):
        cls.cfg = load_config()
        cls.echt = Path(cls.cfg.decomp) / "analysis"
        cls.tmp = Path(ROOT) / "tests" / "_tmp_r13ae_real"
        shutil.rmtree(cls.tmp, ignore_errors=True)
        cls.ana = ensure_dir(cls.tmp / "decomp" / "analysis")
        cls.kopiert: list[str] = []
        for b in (211, 212, 213):
            p = cls.echt / f"_preflight_{b}.txt"
            if p.is_file():
                shutil.copy2(p, cls.ana / p.name)
                cls.kopiert.append(p.name)
        cls.cfg.data["paths"]["decomp"] = str(cls.tmp / "decomp")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_die_drei_dateien_sind_da(self):
        self.assertEqual(self.kopiert,
                         ["_preflight_211.txt", "_preflight_212.txt", "_preflight_213.txt"])

    def test_b212_und_b213_werden_mit_4006_erkannt(self):
        reihe = {e["batch"]: e for e in stand.preflight_c_koepfe(self.cfg, 4)}
        self.assertEqual((reihe[211]["koepfe"], reihe[211]["faelle"]), (78, 2795))
        self.assertEqual((reihe[212]["koepfe"], reihe[212]["faelle"]), (78, 2795))
        self.assertEqual((reihe[213]["koepfe"], reihe[213]["faelle"]), (78, 4006))

    def test_c_trend_endet_nicht_mehr_bei_b211(self):
        t = stand.c_trend(self.cfg, 2)
        self.assertTrue(t["gemessen"])
        self.assertEqual(t["letzt"]["batch"], 213)
        self.assertEqual(t["luecken"], [])
        self.assertEqual(t["n_gemessen"], 3)
        # Die Kopfzahl selbst steht still (78) - der Anlass war die FALL-Zahl 4006.
        self.assertTrue(t["c_schritte"])
        self.assertEqual({s["delta"] for s in t["c_schritte"]}, {0})

    def test_die_einzige_echte_luecke_ist_hybrid_in_b211(self):
        """Gegenprobe am echten Bestand: `_preflight_211.txt` kennt die Zeile
        `Hybrid-Lauf` noch nicht (sie kam mit B212) - genau EINE Meldung, nichts sonst."""
        self.assertEqual(stand.preflight_zeilen_pruefen(self.cfg, log=None, anzahl=3),
                         ["PARSER: Zeile Hybrid-Lauf in _preflight_211.txt nicht erkannt"])
        # Und die neueste Datei (B213) ist vollstaendig.
        self.assertEqual(stand.preflight_zeilen_pruefen(self.cfg, log=None, anzahl=1), [])

    def test_die_kopie_stimmt_mit_dem_laufenden_repo(self):
        for name in self.kopiert:
            p = self.echt / name
            if not p.is_file():
                self.skipTest(f"{name} fehlt im echten Repo")
            moeglich = [z for z in p.read_text(encoding="utf-8").splitlines()
                        if z.startswith("C Koepfe")]
            kopie = [z for z in (self.ana / name).read_text(encoding="utf-8").splitlines()
                     if z.startswith("C Koepfe")]
            self.assertEqual(kopie, moeglich)


if __name__ == "__main__":
    unittest.main()
