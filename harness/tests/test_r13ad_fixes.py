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


if __name__ == "__main__":
    unittest.main()
