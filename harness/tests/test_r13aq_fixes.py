"""Tests fuer R13aq (2026-09-30): gescheiterte Aussensicht, Zuglimit, „zur Kenntnis".

**Auftrag.** (1) Bericht: warum rc=1 (meta-217), wie hoch das Zuglimit, wie viele Zuege
die erfolgreichen Laeufe brauchten. (2) Bericht: welche Marken der Harness setzt und ob
rc=1 als gelaufene Aussensicht zaehlt. (3) Fix: ein Lauf mit `rc != 0` oder **ohne**
AUSSENSICHT-Block zaehlt NICHT als gelaufen (keine Marke, Telegram-Meldung, genau eine
Wiederholung beim naechsten Batch-Ende); Zuglimit konfigurierbar (`meta_max_turns`) mit
Reserve; Frist im Prompt (`<max-5>` Zuege); kein Ersatz-Eintrag im Register.
(4) `_RE_VERDIKT` kennt „zur Kenntnis" (zaehlt wie „erledigt"), M213-4a nachgetragen.

**Gemessen** (`docs/_r13aq_belege.md`, `docs/_r13aq_messung.txt`): `runs/meta-217.jsonl`
endet mit `subtype=error_max_turns`, `is_error=true`, `num_turns=31`,
`Reached maximum number of turns (30)`; die gelungenen Laeufe meta-208..meta-214
brauchten 17, 26, 25, 24, 29, **35** Zuege.
"""

from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import aussensicht                                         # noqa: E402
from hx.config import load_config                                  # noqa: E402
from hx.orchestrator import Orchestrator                           # noqa: E402
from hx.util import Log, ensure_dir, read_text, write_text_atomic  # noqa: E402

# Die Review-Zeile, die den Nachtrag ausloest (Bewertung von Batch 216, Ordner b217).
REVIEW_B217 = ROOT / "runs" / "b217" / "review.md"
ZEILE_M213_4A = "M213-4a: zur Kenntnis - die Batch-Uhr bleibt das Maß"


def _ergebnis(rc=0, summary="", befunde=None, subtype="", zuege=None, text=""):
    res = aussensicht.Ergebnis()
    res.rc = rc
    res.summary = summary
    res.befunde = list(befunde or [])
    res.subtype = subtype
    res.zuege = zuege
    res.text = text
    res.dauer_s = 202.0
    return res


class Basis(unittest.TestCase):
    """Wegwerf-Workspace: eigenes root/decomp, eigenes Register, eigene runs/."""

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13aq"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "root")
        self.decomp = ensure_dir(self.tmp / "decomp")
        ensure_dir(self.decomp / "analysis")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.decomp)
        cfg.data["paths"]["harness_home"] = str(self.tmp)
        cfg.data["paths"]["secrets"] = str(ensure_dir(self.tmp / "secrets"))
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)
        self.gesagt: list[str] = []

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def orch(self, batch: int = 217) -> Orchestrator:
        o = Orchestrator(self.cfg, self.log, mock=True,
                         state_file=self.root / "state" / "run.json")
        o.state.data["batch"] = batch
        o.state.data["meta"] = {"letzter_lauf_batch": 214, "geprueft_batch": 214}
        o.state.save()
        o.say = lambda *a, **k: self.gesagt.append(str(a[0] if a else ""))
        self.gesagt.clear()
        return o

    def log_zeilen(self) -> list[dict]:
        if not self.log.path.is_file():
            return []
        return [json.loads(z) for z in
                self.log.path.read_text(encoding="utf-8").splitlines() if z.strip()]


# --------------------------------------------------- 1) Was zaehlt als gelaufen?
class TestGelaufen(unittest.TestCase):
    def test_rc_ungleich_null_zaehlt_nicht(self):
        ok, warum = aussensicht.gelaufen(_ergebnis(rc=1, subtype="error_max_turns",
                                                   zuege=31))
        self.assertFalse(ok)
        self.assertIn("rc=1", warum)
        self.assertIn("error_max_turns", warum)
        self.assertIn("31 Zuege", warum)

    def test_ohne_antwortblock_zaehlt_nicht(self):
        ok, warum = aussensicht.gelaufen(_ergebnis(rc=0, text="Zwischenstand: … Jetzt die "
                                                             "Tiefenprobe B214"))
        self.assertFalse(ok)
        self.assertIn("AUSSENSICHT-Block", warum)

    def test_gelaufener_lauf_zaehlt(self):
        self.assertEqual(aussensicht.gelaufen(_ergebnis(rc=0, summary="Geprueft: …")),
                         (True, ""))

    def test_befunde_ohne_summary_genuegen(self):
        ok, _ = aussensicht.gelaufen(_ergebnis(rc=0, befunde=[{"beleg": "a.md:1"}]))
        self.assertTrue(ok)

    def test_der_echte_meta_217_ist_das_beispiel(self):
        """Der gescheiterte Lauf, wie er auf der Platte steht (Mitschnitt, kein Mock)."""
        p = ROOT / "runs" / "meta-217.jsonl"
        if not p.is_file():
            self.skipTest("runs/meta-217.jsonl fehlt")
        letzte = None
        for z in p.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                e = json.loads(z)
            except ValueError:
                continue
            if e.get("type") == "result":
                letzte = e
        self.assertIsNotNone(letzte, "kein result-Ereignis im Mitschnitt")
        self.assertEqual(letzte.get("subtype"), "error_max_turns")
        self.assertTrue(letzte.get("is_error"))
        self.assertEqual(int(letzte.get("num_turns") or 0), 31)
        # Und der Bericht des Laufs: 0 Befunde, Rohantwort nur ein Zwischenstand.
        md = read_text(ROOT / "runs" / "meta-217.md")
        self.assertIn("befunde=0", md)
        self.assertIn("Zwischenstand", md)


# ------------------------------------------------------------- 2) Das Zuglimit
class TestZuglimit(Basis):
    def test_meta_max_turns_hat_vorrang(self):
        self.cfg.data["meta"]["max_turns"] = 30
        self.cfg.data["meta"]["meta_max_turns"] = 55
        self.assertEqual(aussensicht.max_turns(self.cfg), 55)
        self.assertEqual(aussensicht.grenzen(self.cfg)["max_turns"], 55)

    def test_max_turns_gilt_ohne_alias(self):
        self.cfg.data["meta"].pop("meta_max_turns", None)
        self.cfg.data["meta"]["max_turns"] = 42
        self.assertEqual(aussensicht.max_turns(self.cfg), 42)

    def test_kaputter_wert_faellt_auf_die_vorgabe(self):
        self.cfg.data["meta"]["meta_max_turns"] = "viel"
        self.cfg.data["meta"].pop("max_turns", None)
        self.assertEqual(aussensicht.max_turns(self.cfg), int(aussensicht.STANDARD["max_turns"]))

    def test_vorgabe_hat_reserve_gegen_den_groessten_lauf(self):
        """Groesster gemessener Lauf: 35 Zuege (meta-214) - die Vorgabe liegt darueber."""
        self.assertGreaterEqual(int(aussensicht.STANDARD["max_turns"]), 45)
        self.assertGreaterEqual(aussensicht.max_turns(load_config()), 45)

    def test_kommando_traegt_das_limit(self):
        self.cfg.data["meta"]["meta_max_turns"] = 44
        cmd = aussensicht.build_command(self.cfg)
        self.assertIn("--max-turns", cmd)
        self.assertEqual(cmd[cmd.index("--max-turns") + 1], "44")

    def test_toml_ist_angehoben(self):
        toml = read_text(ROOT / "harness.toml")
        self.assertIn("max_turns        = 50", toml)

    def test_prompt_nennt_die_frist(self):
        self.cfg.data["meta"]["meta_max_turns"] = 50
        text = aussensicht.build_prompt(self.cfg, self._state(), "Test")
        self.assertIn("spaetestens nach 45 Zuegen", text)
        self.assertIn("Unvollstaendiges als nicht geprueft kennzeichnen", text)

    def test_frist_wandert_mit_dem_limit(self):
        self.cfg.data["meta"]["meta_max_turns"] = 40
        text = aussensicht.build_prompt(self.cfg, self._state(), "Test")
        self.assertIn("spaetestens nach 35 Zuegen", text)

    def _state(self):
        from hx.state import State
        s = State(self.root / "state" / "run.json")
        s.data["batch"] = 217
        return s


# --------------------------------------------------------------- 3) Ausloeser
class TestWiederholung(Basis):
    def test_im_selben_batch_wird_nicht_wiederholt(self):
        o = self.orch(217)
        meta = dict(o.state.data["meta"])
        meta.update({"gescheitert_batch": 217, "gescheitert_grund": "rc=1",
                     "geprueft_batch": 217})
        o.state.data["meta"] = meta
        o.state.save()
        self.assertEqual(aussensicht.faellig(self.cfg, o.state, log=self.log), [])

    def test_beim_naechsten_batch_ende_kommt_die_wiederholung(self):
        o = self.orch(218)
        meta = dict(o.state.data["meta"])
        meta.update({"gescheitert_batch": 217, "gescheitert_grund": "rc=1",
                     "geprueft_batch": 217})
        o.state.data["meta"] = meta
        o.state.save()
        gruende = aussensicht.faellig(self.cfg, o.state, log=self.log)
        self.assertTrue(any(g.startswith("Wiederholung nach gescheiterter Aussensicht B217")
                            for g in gruende), gruende)
        self.assertTrue(any("rc=1" in g for g in gruende), gruende)

    def test_ohne_vermerk_keine_wiederholung(self):
        o = self.orch(218)
        gruende = aussensicht.faellig(self.cfg, o.state, log=self.log)
        self.assertFalse([g for g in gruende if "Wiederholung" in g], gruende)

    def test_der_bericht_allein_traegt_die_wiederholung(self):
        """`runs/meta-217.json` (rc=1) entstand VOR dem Fix - auch er loest aus."""
        write_text_atomic(self.root / "runs" / "meta-214.json",
                          json.dumps({"batch": 214, "rc": 0, "befunde": [{"n": 1}]}))
        write_text_atomic(self.root / "runs" / "meta-217.json",
                          json.dumps({"batch": 217, "rc": 1, "befunde": [],
                                      "subtype": "error_max_turns"}))
        o = self.orch(218)                       # Zustand OHNE `gescheitert_batch`
        gruende = aussensicht.faellig(self.cfg, o.state, log=self.log)
        self.assertTrue(any(g.startswith("Wiederholung nach gescheiterter Aussensicht B217")
                            for g in gruende), gruende)
        self.assertTrue(any("rc=1" in g for g in gruende), gruende)

    def test_ueberholter_bericht_loest_nicht_aus(self):
        """Ein gelungener Lauf NACH dem gescheiterten ueberholt ihn."""
        write_text_atomic(self.root / "runs" / "meta-217.json",
                          json.dumps({"batch": 217, "rc": 1, "befunde": []}))
        write_text_atomic(self.root / "runs" / "meta-218.json",
                          json.dumps({"batch": 218, "rc": 0, "befunde": [{"n": 1}]}))
        z = aussensicht.bericht_zustand(self.cfg)
        self.assertEqual(z["neuester_gescheitert"], 0)
        self.assertEqual(z["letzte_gelungen"], 218)


# ------------------------------------------------- 4) Der Orchestrator-Weg
class TestOrchestratorWeg(Basis):
    def test_gescheiterter_lauf_setzt_keine_takt_marke(self):
        o = self.orch(217)
        res = _ergebnis(rc=1, subtype="error_max_turns", zuege=31,
                        text="Zwischenstand: … Jetzt die Tiefenprobe B214")
        with mock.patch.object(aussensicht, "run", return_value=res), \
                mock.patch.object(aussensicht, "verteile") as verteile:
            o._do_aussensicht("alle 3 Batches", gruende=["alle 3 Batches"])
        meta = dict(o.state.data["meta"])
        # Die Takt-Marke steht weiter auf der letzten GELUNGENEN Aussensicht.
        self.assertEqual(meta.get("letzter_lauf_batch"), 214)
        self.assertEqual(meta.get("geprueft_batch"), 217)      # Entprellung dieses Batches
        self.assertEqual(meta.get("gescheitert_batch"), 217)
        self.assertIn("error_max_turns", str(meta.get("gescheitert_grund")))
        self.assertFalse(verteile.called, "keine Verdikte aus einem gescheiterten Lauf")
        self.assertTrue(any(z.startswith("Aussensicht B217 gescheitert (rc=1, "
                                         "error_max_turns, 31 Zuege), wird beim nächsten "
                                         "Batch-Ende wiederholt") for z in self.gesagt),
                        self.gesagt)
        inbox = Path(o.qroot) / "inbox"
        self.assertEqual(sorted(p.name for p in inbox.rglob("*.md")) if inbox.is_dir()
                         else [], [], "nichts an die Queue gegeben")
        self.assertTrue(any(z.get("msg") == "Aussensicht zaehlt nicht als gelaufen"
                            for z in self.log_zeilen()))
        # Der Bericht bleibt als Beleg da - und ist maschinenlesbar als gescheitert markiert.
        daten = json.loads(read_text(self.root / "runs" / "meta-217.json"))
        self.assertFalse(daten.get("gelaufen"))
        self.assertEqual(daten.get("subtype"), "error_max_turns")
        self.assertEqual(daten.get("zuege"), 31)
        self.assertEqual(daten.get("befunde"), [])

    def test_leerer_lauf_ohne_block_zaehlt_auch_nicht(self):
        o = self.orch(217)
        res = _ergebnis(rc=0, text="Zwischenstand")
        with mock.patch.object(aussensicht, "run", return_value=res), \
                mock.patch.object(aussensicht, "verteile") as verteile:
            o._do_aussensicht("alle 3 Batches", gruende=["alle 3 Batches"])
        meta = dict(o.state.data["meta"])
        self.assertEqual(meta.get("letzter_lauf_batch"), 214)
        self.assertEqual(meta.get("gescheitert_batch"), 217)
        self.assertIn("AUSSENSICHT-Block", str(meta.get("gescheitert_grund")))
        self.assertFalse(verteile.called)

    def test_gelungener_lauf_setzt_die_marke_und_loescht_den_vermerk(self):
        o = self.orch(217)
        meta = dict(o.state.data["meta"])
        meta.update({"gescheitert_batch": 217, "gescheitert_grund": "rc=1"})
        o.state.data["meta"] = meta
        o.state.save()
        res = _ergebnis(rc=0, summary="Geprueft: zwei Zahlen bestaetigt.")
        with mock.patch.object(aussensicht, "run", return_value=res), \
                mock.patch.object(aussensicht, "verteile",
                                  return_value={"ids": [], "verdikte": [], "offen_alt": 0}):
            o._do_aussensicht("alle 3 Batches", gruende=["alle 3 Batches"])
        meta = dict(o.state.data["meta"])
        self.assertEqual(meta.get("letzter_lauf_batch"), 217)
        self.assertEqual(meta.get("geprueft_batch"), 217)
        for feld in ("gescheitert_batch", "gescheitert_grund", "gescheitert_ts"):
            self.assertNotIn(feld, meta)
        self.assertFalse(any("gescheitert" in z for z in self.gesagt), self.gesagt)

    def test_ausnahme_zaehlt_ebenfalls_nicht(self):
        o = self.orch(217)
        with mock.patch.object(aussensicht, "run", side_effect=RuntimeError("kein Token")):
            o._do_aussensicht("alle 3 Batches", gruende=["alle 3 Batches"])
        meta = dict(o.state.data["meta"])
        self.assertEqual(meta.get("letzter_lauf_batch"), 214)
        self.assertEqual(meta.get("gescheitert_batch"), 217)
        self.assertIn("Ausnahme", str(meta.get("gescheitert_grund")))


# --------------------------------------------------- 5) „zur Kenntnis" im Verdikt
class TestZurKenntnis(Basis):
    def _register(self, status: str = "offen") -> None:
        aussensicht.ledger_schreiben(self.cfg, [{
            "id": "M213-4a", "batch": 213, "gewicht": "niedrig", "empfaenger": "Reviewer",
            "beleg": "runs/b213/result.json", "aussage": "Die Batch-Uhr misst anders.",
            "empfehlung": "Nachmessen.", "status": status, "quelle": "aussensicht",
        }])

    def test_zur_kenntnis_wird_erkannt(self):
        self._register()
        geaendert = aussensicht.antworten_uebernehmen(self.cfg, ZEILE_M213_4A, 216)
        self.assertEqual(geaendert, ["M213-4a"])
        e = aussensicht.ledger(self.cfg)[0]
        self.assertEqual(e["status"], "zur kenntnis")
        self.assertEqual(int(e["antwort_batch"]), 216)
        self.assertIn("Batch-Uhr", e["antwort"])

    def test_zur_kenntnis_zaehlt_wie_erledigt(self):
        self._register("zur kenntnis")
        self.assertEqual(aussensicht.klasse(aussensicht.ledger(self.cfg)[0]), "uebernommen")
        self.assertEqual(aussensicht.offene(self.cfg), [])
        q = aussensicht.quote(self.cfg)
        self.assertEqual(q.get("uebernommen"), 1)
        self.assertEqual(q.get("offen"), 0)

    def test_ohne_verdikt_keine_antwort(self):
        """Prosa, die eine Kennung nur erwaehnt, schliesst nichts."""
        self._register()
        self.assertEqual(aussensicht.antworten_uebernehmen(
            self.cfg, "M213-4a steht noch im Raum.", 216), [])
        self.assertEqual(aussensicht.ledger(self.cfg)[0]["status"], "offen")

    def test_die_echte_zeile_aus_b217(self):
        if not REVIEW_B217.is_file():
            self.skipTest("runs/b217/review.md fehlt")
        text = read_text(REVIEW_B217)
        self.assertIn(ZEILE_M213_4A, text, "die Zeile steht so im Review")
        self.assertTrue(aussensicht._RE_VERDIKT.search("zur Kenntnis - die Batch-Uhr"))


# --------------------------------------------- 6) „letzte Aussensicht" im Status
class TestStatuszeile(Basis):
    def _bericht(self, batch: int, rc: int = 0, befund: bool = True,
                 gelaufen: bool | None = None) -> None:
        d = {"batch": batch, "rc": rc, "befunde": ([{"n": 1}] if befund else []),
             "summary": "x", "ts": "2026-09-30T00:00:00+00:00"}
        if gelaufen is not None:
            d["gelaufen"] = gelaufen
        write_text_atomic(self.root / "runs" / f"meta-{batch:03d}.json",
                          json.dumps(d))

    def test_gescheiterter_lauf_ist_nicht_die_letzte(self):
        self._bericht(214)
        self._bericht(217, rc=1, befund=False)          # wie runs/meta-217.json
        z = aussensicht.zeile(self.cfg)
        self.assertIn("letzte Aussensicht: Batch 214", z)
        self.assertIn("zuletzt gescheitert: Batch 217", z)

    def test_gelaufen_false_wird_ebenfalls_uebersprungen(self):
        self._bericht(214)
        self._bericht(217, rc=0, befund=False, gelaufen=False)
        z = aussensicht.zeile(self.cfg)
        self.assertIn("letzte Aussensicht: Batch 214", z)
        self.assertIn("zuletzt gescheitert: Batch 217", z)

    def test_gelungener_lauf_bleibt_die_letzte(self):
        self._bericht(214)
        self._bericht(217, rc=0, befund=True, gelaufen=True)
        z = aussensicht.zeile(self.cfg)
        self.assertIn("letzte Aussensicht: Batch 217", z)
        self.assertNotIn("gescheitert", z)

    def test_alter_bericht_ohne_felder_zaehlt_als_gelaufen(self):
        self._bericht(213)
        z = aussensicht.zeile(self.cfg)
        self.assertIn("letzte Aussensicht: Batch 213", z)
        self.assertNotIn("gescheitert", z)


if __name__ == "__main__":
    unittest.main()
