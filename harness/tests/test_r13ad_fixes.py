"""Tests fuer R13ad (2026-09-29): Batch-Zeitbudget, Kontextmessung, Fortsetzungsanstoss.

Auftrag (Nutzer, drei Punkte): (1) den Kontext je Anfrage messen (input + cache_read +
cache_creation) und in `result.json`/den Review-Fakten zeigen, (2) EINE Zeitquelle
(Alarmgrenze bleibt, neue Umschaltschwelle, der Reviewer nennt keine eigene Minutenzahl
mehr), (3) frueh aufhoerende Worker im SELBEN Chat fortsetzen.

Alle Tests laufen ohne API-Kosten (Attrappe bzw. synthetische Mitschnitte).
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

from hx import streamjson, worker, uhr                            # noqa: E402
from hx.config import load_config                                # noqa: E402
from hx.orchestrator import Orchestrator                         # noqa: E402
from hx.util import Log, ensure_dir                              # noqa: E402

ANKER = """# Workstream R1B
**Stand:** BATCH 158 (2026-09-25) - irgendwas.
**Naechster Schritt:** (a) **B159:** cc54 verdrahten.
"""


def _assistant(mid: str, miss: int, hit: int = 0, creation: int = 0, out: int = 1,
               text: str = "x", werkzeug: str | None = None,
               befehl: str | None = None) -> str:
    content: list[dict] = [{"type": "text", "text": text}]
    if werkzeug:
        eingabe = {"command": befehl} if befehl else {"file_path": "x"}
        content.append({"type": "tool_use", "id": f"tu_{mid}", "name": werkzeug,
                        "input": eingabe})
    return json.dumps({"type": "assistant", "message": {
        "id": mid, "model": "deepseek-flash",
        "usage": {"input_tokens": miss, "cache_read_input_tokens": hit,
                  "cache_creation_input_tokens": creation, "output_tokens": out},
        "content": content}})


def _result(miss: int, hit: int = 0, creation: int = 0, out: int = 1,
            duration_ms: int = 1000, num_turns: int = 3, text: str = "ok") -> str:
    return json.dumps({"type": "result", "subtype": "success", "is_error": False,
                       "num_turns": num_turns, "duration_ms": duration_ms,
                       "total_cost_usd": 0.01, "result": text,
                       "usage": {"input_tokens": miss, "cache_read_input_tokens": hit,
                                 "cache_creation_input_tokens": creation,
                                 "output_tokens": out}})


def _stats(*zeilen: str) -> streamjson.StreamStats:
    s = streamjson.StreamStats()
    for z in zeilen:
        s.feed(z)
    return s


# =========================================== 1) Kontext messen
class TestKontextmessung(unittest.TestCase):
    def test_kontextsumme_ist_input_cache_und_creation(self):
        s = _stats(_assistant("m1", 1000, 2000, 500, 10))
        self.assertEqual(s.kontext_summe(s.requests[0]), 3500)
        st = s.kontext_stats()
        self.assertEqual(st["kontext_letzte_anfrage"], 3500)
        self.assertEqual(st["kontext_max"], 3500)

    def test_max_nimmt_das_groesste_und_verlauf_jede_25(self):
        s = streamjson.StreamStats()
        for i in range(60):
            s.feed(_assistant(f"m{i}", 1000 + i, 0, 0, 1))
        st = s.kontext_stats()
        werte = s.kontext_werte()
        self.assertEqual(st["kontext_max"], 1059)
        self.assertEqual(st["kontext_letzte_anfrage"], 1059)
        self.assertEqual(st["kontext_verlauf"], [werte[0], werte[25], werte[50], werte[59]])

    def test_kompaktierung_bei_sprunghaftem_rueckgang(self):
        s = _stats(_assistant("m1", 200000), _assistant("m2", 400000),
                   _assistant("m3", 40000))
        self.assertEqual(s.kompaktierungen(), [[2, 400000, 40000]])

    def test_kleiner_rueckgang_ist_keine_kompaktierung(self):
        s = _stats(_assistant("m1", 100000), _assistant("m2", 95000))
        self.assertEqual(s.kompaktierungen(), [])

    def test_compact_boundary_ereignis_wird_verankert(self):
        s = _stats(_assistant("m1", 100000),
                   json.dumps({"type": "system", "subtype": "compact_boundary"}),
                   _assistant("m2", 30000))
        self.assertEqual(s.kompaktierungen(), [[1, 100000, 30000]])


class TestResultSummenUeberFortsetzungen(unittest.TestCase):
    def test_usage_dauer_und_turns_werden_summiert(self):
        s = _stats(_assistant("m1", 100, 0, 0, 5),
                   _result(100, 0, 0, 5, duration_ms=60000, num_turns=4),
                   _assistant("m2", 200, 0, 0, 7),
                   _result(200, 0, 0, 7, duration_ms=30000, num_turns=6))
        u = s.result_usage()
        self.assertEqual(u["input_miss"], 300)
        self.assertEqual(u["output"], 12)
        self.assertEqual(s.num_turns(), 10)
        self.assertEqual(s.duration_field(), (90.0, "duration_ms"))
        self.assertEqual(s.totals()["requests"], 2)

    def test_letzte_antwort_ohne_werkzeug(self):
        s = _stats(_assistant("m1", 1, werkzeug="Read"))
        self.assertFalse(s.letzte_antwort_ohne_werkzeug())
        s.feed(_assistant("m2", 1))
        self.assertTrue(s.letzte_antwort_ohne_werkzeug())
        self.assertIsNone(streamjson.StreamStats().letzte_antwort_ohne_werkzeug())

    def test_werkzeug_enthaelt_prueft_die_aufrufe(self):
        s = streamjson.StreamStats()
        self.assertFalse(s.werkzeug_enthaelt("preflight"))
        s.feed(_assistant("m1", 1, werkzeug="PowerShell",
                          befehl="python scripts/preflight.py before"))
        self.assertTrue(s.werkzeug_enthaelt("preflight"))
        self.assertFalse(s.werkzeug_enthaelt("preflight", "bilanz"))


class TestResultJsonMitKontext(unittest.TestCase):
    """Der echte Attrappen-Lauf schreibt die Kontextzahlen in `result.json`."""

    def setUp(self):
        self.tmp = ensure_dir(Path(__file__).resolve().parent / "_tmp_r13ad")
        shutil.rmtree(self.tmp, ignore_errors=True)
        ensure_dir(self.tmp)
        self.repo = ensure_dir(self.tmp / "decomp")
        ensure_dir(self.repo / "analysis")
        (self.repo / "analysis" / "r1b-workstream.md").write_text(ANKER, encoding="utf-8")
        self.root = ensure_dir(self.tmp / "root")
        sec = ensure_dir(self.root / "secrets")
        (sec / "deepseek.key").write_text("sk-test-000\n", encoding="utf-8")
        prof = ensure_dir(self.root / "profiles")
        for f in (ROOT / "profiles").glob("*.json"):
            shutil.copy2(f, prof / f.name)
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.repo)
        cfg.data["paths"]["secrets"] = str(sec)
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)
        self.orch = Orchestrator(cfg, self.log, mock=True,
                                 state_file=self.root / "state" / "run.json")
        self.orch.say = lambda *a, **k: None
        self.orch.state.data["batch"] = 159
        self.orch.state.save()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_mocklauf_schreibt_kontextzahlen(self):
        res = worker.run_batch(self.cfg, self.log, self.orch.state, "Batch 159 - Test",
                               "none", None, mock=True)
        daten = json.loads((Path(res.run_dir) / "result.json").read_text(encoding="utf-8"))
        st = daten["stats"]
        # Die Attrappe hat 5 Anfragen: 4 Plan-Schritte + Abschluss (150 + 22500).
        self.assertEqual(st["kontext_letzte_anfrage"], 22650)
        self.assertEqual(st["kontext_max"], 22650)
        self.assertEqual(st["kontext_verlauf"], [21000, 22650])
        self.assertEqual(st["kompaktierungen"], [])
        self.assertIn("kontext_letzte_anfrage", st)


# =========================================== 2) Eine Zeitquelle
class TestZeitquelle(unittest.TestCase):
    def test_umschalt_und_kontext_stehen_in_der_uhr(self):
        start = datetime.now(timezone.utc) - timedelta(minutes=34)
        st = {"worker": {"pid": 1, "started_at": start.isoformat(timespec="seconds")},
              "live": {"batch": 210, "kontext": 310000}}
        text = uhr.uhr_text(st, 90, 180, umschalt_min=80, kontext_limit=1000000)
        self.assertIn("34", text)
        self.assertIn("min von 90 min", text)
        self.assertIn("Umschalten ab 80", text)
        self.assertIn("Kontext 310k von 1M", text)

    def test_kontext_zeile_fehlt_ohne_messwert(self):
        start = datetime.now(timezone.utc) - timedelta(minutes=5)
        st = {"worker": {"pid": 1, "started_at": start.isoformat(timespec="seconds")}}
        text = uhr.uhr_text(st, 90, 180, umschalt_min=80, kontext_limit=1000000)
        self.assertNotIn("Kontext", text)

    def test_konfiguration_hat_die_eine_zeitquelle(self):
        cfg = load_config()
        self.assertEqual(float(cfg.get("limits", "alarm_wall_s")), 5400.0)
        self.assertEqual(float(cfg.get("limits", "umschalt_vor_alarm_s")), 900.0)
        self.assertEqual(int(cfg.get("limits", "kontext_limit")), 1000000)

    def test_hook_skript_zeigt_die_umschaltschwelle(self):
        import subprocess
        tmp = Path(__file__).resolve().parent / "_tmp_r13ad_uhr"
        shutil.rmtree(tmp, ignore_errors=True)
        d = ensure_dir(tmp)
        state = d / "run.json"
        start = datetime.now(timezone.utc) - timedelta(minutes=34)
        state.write_text(json.dumps(
            {"worker": {"pid": 1, "started_at": start.isoformat(timespec="seconds")},
             "live": {"batch": 210, "kontext": 310000}}), encoding="utf-8")
        p = subprocess.run([sys.executable, str(ROOT / "tools" / "batch_uhr.py"),
                            "--state", str(state), "--weich", "90", "--hart", "180",
                            "--umschalt", "80", "--kontext-limit", "1000000"],
                           input=b"{}", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=120)
        self.assertEqual(p.returncode, 0, p.stderr.decode("utf-8", "replace")[:200])
        txt = json.loads(p.stdout.decode("utf-8"))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Umschalten ab 80", txt)
        self.assertIn("Kontext 310k von 1M", txt)
        shutil.rmtree(tmp, ignore_errors=True)


# =========================================== 3) Fortsetzungsanstoss
class TestFortsetzung(unittest.TestCase):
    """Die Entscheidung "fortsetzen?" - jede Bedingung (a)-(e) einzeln (R13ad)."""

    AUFTRAG = "TEIL 1: irgendwas.\n\n## NACHRUECKLISTE\n1. Kopf 80054AE4 verifizieren\n"

    def setUp(self):
        self.cfg = load_config()

    def _stats(self, kontext: int, letzte_mit_werkzeug: bool = False):
        s = streamjson.StreamStats()
        s.feed(_assistant("m1", 1000))
        s.feed(_assistant("m2", kontext, werkzeug="Read" if letzte_mit_werkzeug else None))
        s.feed(_result(kontext, 0, 0, 1))
        return s

    @staticmethod
    def _run(rc: int = 0, killed=None):
        from hx.proc import StreamRun
        r = StreamRun()
        r.rc = rc
        r.killed_reason = killed
        return r

    def test_30_min_kontext_300k_mit_liste_ergibt_anstoss(self):
        entsch = worker.fortsetzung_pruefen(self.cfg, self._run(), self._stats(300000),
                                            self.AUFTRAG, 30.0, [])
        self.assertTrue(entsch["ja"], entsch)

    def test_85_min_kein_anstoss(self):
        entsch = worker.fortsetzung_pruefen(self.cfg, self._run(), self._stats(300000),
                                            self.AUFTRAG, 85.0, [])
        self.assertFalse(entsch["ja"])
        self.assertIn("Umschaltschwelle", entsch["grund"])

    def test_kontext_600k_kein_anstoss(self):
        entsch = worker.fortsetzung_pruefen(self.cfg, self._run(), self._stats(600000),
                                            self.AUFTRAG, 30.0, [])
        self.assertFalse(entsch["ja"])
        self.assertIn("Kontext", entsch["grund"])

    def test_ohne_nachrueckliste_kein_anstoss(self):
        entsch = worker.fortsetzung_pruefen(self.cfg, self._run(), self._stats(300000),
                                            "TEIL 1 ohne Liste.", 30.0, [])
        self.assertFalse(entsch["ja"])
        self.assertIn("NACHRUECKLISTE", entsch["grund"])

    def test_nach_zwei_anstossen_schluss(self):
        zwei = [{"minute": 20.0}, {"minute": 40.0}]
        entsch = worker.fortsetzung_pruefen(self.cfg, self._run(), self._stats(300000),
                                            self.AUFTRAG, 45.0, zwei)
        self.assertFalse(entsch["ja"])
        self.assertIn("max_fortsetzungen", entsch["grund"])

    def test_abbruchgrund_kein_anstoss(self):
        entsch = worker.fortsetzung_pruefen(self.cfg, self._run(killed="wall"),
                                            self._stats(300000), self.AUFTRAG, 30.0, [])
        self.assertFalse(entsch["ja"])
        self.assertIn("wall", entsch["grund"])

    def test_rc_ungleich_null_kein_anstoss(self):
        entsch = worker.fortsetzung_pruefen(self.cfg, self._run(rc=1), self._stats(300000),
                                            self.AUFTRAG, 30.0, [])
        self.assertFalse(entsch["ja"])

    def test_letzte_antwort_mit_werkzeug_kein_anstoss(self):
        entsch = worker.fortsetzung_pruefen(self.cfg, self._run(),
                                            self._stats(300000, letzte_mit_werkzeug=True),
                                            self.AUFTRAG, 30.0, [])
        self.assertFalse(entsch["ja"])
        self.assertIn("regulaeres Ende", entsch["grund"])

    def test_erledigt_marker_beendet_die_kette(self):
        self.assertTrue(worker.nachrueckliste_erledigt("NACHRUECKLISTE ERLEDIGT"))
        self.assertTrue(worker.nachrueckliste_erledigt("… NACHRÜCKLISTE erledigt …"))
        self.assertFalse(worker.nachrueckliste_erledigt("## NACHRUECKLISTE\n1. offen"))

    def test_fortsetzungstext_nennt_uhr_schwelle_kontext(self):
        text = worker.fortsetzungs_text(34.0, 310000, 90.0, 80.0)
        self.assertIn("Batch-Uhr: 34 von 90 min", text)
        self.assertIn("Umschaltschwelle 80 min nicht erreicht", text)
        self.assertIn("Kontext 310k", text)
        self.assertIn("NACHRUECKLISTE ERLEDIGT", text)
        self.assertIn("Aufwand ist kein Grund", text)
        mit = worker.fortsetzungs_text(34.0, 310000, 90.0, 80.0, preflight_erneut=True)
        self.assertIn("Nach der Nacharbeit: Preflight erneut laufen lassen", mit)
        self.assertIn("Der letzte Preflight gilt, der frühere ist überholt.", mit)

    def test_limits_werden_ueber_fortsetzungen_kumuliert(self):
        # Zeit: die harte Wanduhr wird je Teillauf um die verbrauchte Zeit gekuerzt.
        self.assertEqual(worker.rest_wanduhr_s(10800.0, 0.0, 0.0), 10800.0)
        self.assertEqual(worker.rest_wanduhr_s(10800.0, 0.0, 1800.0), 9000.0)
        self.assertEqual(worker.rest_wanduhr_s(10800.0, 0.0, 20000.0), 60.0)
        # Anfragen und Kosten: EIN `stats` fuer alle Teillaeufe (Auftrag Punkt 3).
        s = streamjson.StreamStats()
        s.feed(_assistant("s1", 100, 0, 0, 5))
        s.feed(_result(100, 0, 0, 5))
        s.feed(_assistant("s2", 200, 0, 0, 7))
        s.feed(_result(200, 0, 0, 7))
        self.assertEqual(s.totals()["requests"], 2)
        self.assertEqual(s.totals()["input_miss"], 300)
        self.assertGreater(s.cost_usd(), 0.0)

    def test_build_command_nutzt_resume(self):
        from hx.profiles import load_profile
        cfg = load_config()
        prof = load_profile(cfg.root, "none")
        rd = Path(cfg.root) / "runs" / "b999"
        neu, _ = worker.build_command(cfg, prof, rd, "abc", resume=False)
        self.assertIn("--session-id", neu)
        self.assertNotIn("--resume", neu)
        fort, _ = worker.build_command(cfg, prof, rd, "abc", resume=True)
        self.assertIn("--resume", fort)
        self.assertNotIn("--session-id", fort)

    def test_faktenzeile_nennt_die_fortsetzungen(self):
        from hx.orchestrator import Orchestrator
        self.assertEqual(Orchestrator.fortsetzungen_zeile(None, {}), "keine")
        zeile = Orchestrator.fortsetzungen_zeile(None, {"fortsetzungen": [
            {"minute": 30, "kontext": 300000, "antwort_kurz": "NACHRUECKLISTE ERLEDIGT"}]})
        self.assertIn("#1 bei 30 min", zeile)
        self.assertIn("Kontext 300000", zeile)
        self.assertIn("NACHRUECKLISTE ERLEDIGT", zeile)


class TestNachruecklisteErkennung(unittest.TestCase):
    """Bedingung (d): welche Formen gelten als NACHRUECKLISTE-Abschnitt? (R13ad)

    Geprueft wird gegen die ECHTEN Auftraege B211-B213. Die Belege wurden mit PowerShell
    `Select-String` erhoben - die VS-Code-Suche blendet `runs/` aus (search.exclude /
    .gitignore) und meldete deshalb faelschlich "kein Treffer".
    """

    def test_die_geforderten_formen_am_zeilenanfang(self):
        for form in ("## NACHRUECKLISTE",
                     "NACHRUECKLISTE:",
                     "NACHRUECKLISTE (vor dem Preflight, je Posten ein Commit mit Soll-Delta):",
                     "Nachrückliste",
                     "Nachrueckliste",
                     "  ## **NACHRUECKLISTE**  "):
            self.assertTrue(worker.hat_nachrueckliste(form), form)
            # Auch mitten im Auftrag, nicht nur in Zeile 1.
            self.assertTrue(worker.hat_nachrueckliste("TEIL 1\nirgendwas\n\n" + form
                                                      + "\n1. offener Posten"), form)

    def test_erwaehnungen_mitten_in_der_zeile_gelten_nicht(self):
        for gegen in ("  (4) NACHRUECKLISTE;",
                      "- Offen: Nachrueckliste B211 (1/2/4/5/6);",
                      "Die NACHRUECKLISTE ist zuerst dran.",
                      "NACHRUECKLISTEN"):
            self.assertFalse(worker.hat_nachrueckliste(gegen), gegen)

    def test_gegen_den_echten_b213_auftrag(self):
        """Der gemessene Beleg `runs/b213/review.md:126` (DS_INSTRUCTION) muss zaehlen."""
        from hx.proc import StreamRun
        cfg = load_config()
        p = Path(cfg.root) / "runs" / "b213" / "review.md"
        if not p.is_file():
            self.skipTest("runs/b213/review.md fehlt")
        text = p.read_text(encoding="utf-8")
        i = text.find("<DS_INSTRUCTION>")
        j = text.find("</DS_INSTRUCTION>")
        self.assertGreaterEqual(i, 0, "kein DS_INSTRUCTION-Block")
        instr = text[i:j if j > i else len(text)]
        self.assertIn("NACHRUECKLISTE (vor dem Preflight", instr)
        self.assertTrue(worker.hat_nachrueckliste(instr))
        # Bedingung (d) ist damit fuer einen solchen Auftrag erfuellt.
        s = streamjson.StreamStats()
        s.feed(_assistant("m1", 1000))
        s.feed(_assistant("m2", 300000))
        s.feed(_result(300000, 0, 0, 1))
        run = StreamRun()
        run.rc = 0
        entsch = worker.fortsetzung_pruefen(cfg, run, s, instr, 30.0, [])
        self.assertTrue(entsch["ja"], entsch)

    def test_gegen_die_echten_b211_b212_auftraege(self):
        cfg = load_config()
        geprueft = 0
        for n in (211, 212):
            p = Path(cfg.root) / "runs" / f"b{n:03d}" / "auftrag.md"
            if not p.is_file():
                continue
            text = p.read_text(encoding="utf-8")
            self.assertIn("NACHRUECKLISTE (", text)
            self.assertTrue(worker.hat_nachrueckliste(text), f"B{n}")
            geprueft += 1
        if not geprueft:
            self.skipTest("keine echten Auftraege B211/B212")


if __name__ == "__main__":
    unittest.main()
