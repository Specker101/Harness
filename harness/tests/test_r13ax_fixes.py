"""Tests fuer R13ax (2026-09-30): kein Fortsetzungsanstoss nach einem Preflight.

**Auftrag (Aussensicht B219, Befund 5, Gewicht mittel).** Beleg: `port-batch219-…md:203-206`
(Preflight bei 60 von 75 min, obwohl NACHRUECKLISTE 1 offen war), B217 mit zweitem Preflight
in der Fortsetzung (`981a8bd`), B218 mit drei Preflights. Aussage: „nach dem Preflight kein
`port/`", „Preflight erst nach der Nachrueckliste" und die automatische Fortsetzung stossen
zusammen; die Fortsetzung laeuft in den schon gemessenen Stand hinein.

Regel: hat der Worker in diesem Batch schon einen Preflight **gestartet**
(`streamjson.ist_preflight_aufruf`), gibt es keinen Anstoss mehr - die offene Nachrueckliste
wird **uebertragen**. Log und Review-Fakten nennen den Grund im Klartext:
`Kein Fortsetzungsanstoss: Preflight bereits gelaufen, offene Nachrueckliste -> UEBERTRAG`.

Die Archivierung „Preflight vor Fortsetzung" (R13ah) bleibt als Code stehen - dieser Zweig
wird praktisch nur noch erreicht, wenn die Regel einmal gelockert wird.
"""

from __future__ import annotations

import inspect
import json
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import streamjson, worker                                  # noqa: E402
from hx.config import load_config                                  # noqa: E402
from hx.orchestrator import Orchestrator                           # noqa: E402
from hx.util import Log, ensure_dir, write_json_atomic             # noqa: E402

AUFTRAG = "TEIL 1: irgendwas.\n\n## NACHRUECKLISTE\n1. Kopf 80054AE4 verifizieren\n"
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


def preflight_aufruf(befehl: str = "python -u scripts/preflight.py before") -> dict:
    """Ein `tool_use`-Eintrag, wie ihn `StreamStats.tools` fuehrt."""
    return {"zeile": 1, "ts": "2026-09-30T00:00:00Z", "id": "tu-pf", "name": "PowerShell",
            "input": {"command": befehl, "description": "Preflight"}}


class TestPreflightGestartet(unittest.TestCase):
    """Nur ein START zaehlt - dieselbe Definition wie beim Preflight-Zaehler (R13ao)."""

    def stats(self, *tools: dict) -> streamjson.StreamStats:
        s = streamjson.StreamStats()
        s.tools = list(tools)
        return s

    def test_echter_start_zaehlt(self):
        for befehl in ("python -u scripts/preflight.py before",
                       "cd g:\\Silent Scope Decomp; python scripts/preflight.py before"):
            self.assertTrue(worker.preflight_gestartet(self.stats(preflight_aufruf(befehl))),
                            befehl)

    def test_blosse_nennung_zaehlt_nicht(self):
        """`description` nennt den Preflight oft, ohne ihn zu starten (R13ao)."""
        eintrag = {"zeile": 1, "ts": "x", "id": "t", "name": "PowerShell",
                   "input": {"command": "Get-ChildItem", "description": "Preflight-Umfeld"}}
        self.assertFalse(worker.preflight_gestartet(self.stats(eintrag)))

    def test_filter_zaehlt_nicht(self):
        eintrag = preflight_aufruf("Select-String -Path runs\\b1\\stream.jsonl "
                                   "-Pattern 'preflight.py'")
        self.assertFalse(worker.preflight_gestartet(self.stats(eintrag)))

    def test_lesen_zaehlt_nicht(self):
        eintrag = {"zeile": 1, "ts": "x", "id": "t", "name": "Read",
                   "input": {"file_path": "analysis/_preflight_219.txt"}}
        self.assertFalse(worker.preflight_gestartet(self.stats(eintrag)))

    def test_ohne_aufrufe_kein_preflight(self):
        self.assertFalse(worker.preflight_gestartet(self.stats()))
        self.assertFalse(worker.preflight_gestartet(None))


class TestFortsetzungPruefen(unittest.TestCase):
    AUFTRAG = AUFTRAG

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
    def _run(rc: int = 0, killed=None):
        from hx.proc import StreamRun
        r = StreamRun()
        r.rc = rc
        r.killed_reason = killed
        return r

    def entsch(self, **kwargs):
        return worker.fortsetzung_pruefen(self.cfg, self._run(), self._stats(**kwargs),
                                          self.AUFTRAG, 30.0, [])

    def test_ohne_preflight_wird_angestossen(self):
        e = self.entsch()
        self.assertTrue(e["ja"], e)
        self.assertFalse(e.get("uebertrag"))

    def test_nach_preflight_kein_anstoss(self):
        e = self.entsch(preflight=True)
        self.assertFalse(e["ja"])
        self.assertEqual(e["grund"], worker.UEBERTRAG_GRUND)
        self.assertTrue(e["uebertrag"])

    def test_wortlaut_ist_festgeschrieben(self):
        self.assertEqual(worker.UEBERTRAG_TEXT, TEXT)
        self.assertEqual(worker.UEBERTRAG_GRUND,
                         "Preflight bereits gelaufen, offene Nachrueckliste -> UEBERTRAG")

    def test_andere_gruende_haben_kein_uebertrag_merkmal(self):
        """Nur der Preflight-Fall ist ein UEBERTRAG - sonst bleibt der Grund wie vorher."""
        e = worker.fortsetzung_pruefen(self.cfg, self._run(), self._stats(preflight=True),
                                      "TEIL 1 ohne Liste.", 30.0, [])
        self.assertFalse(e["ja"])
        self.assertIn("NACHRUECKLISTE", e["grund"])
        self.assertFalse(e.get("uebertrag"))

    def test_abbruch_bleibt_abbruch(self):
        """Ein Abbruch ist kein UEBERTRAG, auch wenn ein Preflight gelaufen war."""
        e = worker.fortsetzung_pruefen(self.cfg, self._run(killed="cancel"),
                                      self._stats(preflight=True), self.AUFTRAG, 30.0, [])
        self.assertIn("cancel", e["grund"])
        self.assertFalse(e.get("uebertrag"))

    def test_im_lauf_wird_der_text_geloggt(self):
        quelle = inspect.getsource(worker.run_batch)
        self.assertIn("log.info(UEBERTRAG_TEXT)", quelle)
        self.assertIn("res.fortsetzung_uebertrag = bool(entsch.get(\"uebertrag\"))", quelle)


class TestErgebnisUndFakten(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13ax"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "root")
        self.decomp = ensure_dir(self.tmp / "decomp")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.decomp)
        cfg.data["paths"]["harness_home"] = str(self.tmp)
        cfg.data["paths"]["secrets"] = str(ensure_dir(self.tmp / "secrets"))
        cfg.data["mock"]["enabled"] = True
        cfg.data["telegram"]["allowlist_user_ids"] = []
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_result_json_traegt_den_grund(self):
        stats = streamjson.StreamStats()
        stats.feed(_result(1000))
        stats.tools.append(preflight_aufruf())
        res = worker.WorkerResult()
        res.fortsetzung_grund = worker.UEBERTRAG_GRUND
        res.fortsetzung_uebertrag = True
        state = mock.Mock()
        state.data = {}
        with mock.patch("hx.worker.write_json_atomic") as schreiben, \
                mock.patch("hx.worker.write_snapshot", return_value=""), \
                mock.patch.object(worker.reihenfolge, "git_zeilen", return_value=[]):
            worker._finish_run(self.cfg, state, res, stats, 999, "none", self.log,
                               ghidra_save=False)
        nutzlast = schreiben.call_args[0][1]
        self.assertEqual(nutzlast.get("fortsetzung_grund"), worker.UEBERTRAG_GRUND)
        self.assertTrue(nutzlast.get("fortsetzung_uebertrag"))

    def test_review_fakten_nennen_den_satz(self):
        rd = ensure_dir(self.root / "runs" / "b219")
        write_json_atomic(rd / "result.json", {
            "batch": 219, "rc": 0, "profile": "none", "program": "main.bin",
            # So schreibt `_finish_run` sie: oben UND in `stats` (die Anzeige liest stats).
            "fortsetzung_grund": worker.UEBERTRAG_GRUND, "fortsetzung_uebertrag": True,
            "stats": {"fortsetzung_grund": worker.UEBERTRAG_GRUND,
                      "fortsetzung_uebertrag": True},
        })
        o = Orchestrator(self.cfg, self.log, mock=True,
                         state_file=self.root / "state" / "run.json")
        o.say = lambda *a, **k: None
        o.state.data["last_batch_number"] = 219
        text = o.harness_facts(219, ziel=self.root / "out")
        self.assertIn("- Fortsetzungen (R13ad): keine | " + TEXT, text)

    def test_review_fakten_ohne_uebertrag_wie_vorher(self):
        rd = ensure_dir(self.root / "runs" / "b220")
        write_json_atomic(rd / "result.json", {
            "batch": 220, "rc": 0, "fortsetzung_grund": "max_fortsetzungen (2) erreicht",
            "stats": {"fortsetzung_grund": "max_fortsetzungen (2) erreicht"},
        })
        o = Orchestrator(self.cfg, self.log, mock=True,
                         state_file=self.root / "state" / "run.json")
        o.say = lambda *a, **k: None
        o.state.data["last_batch_number"] = 220
        text = o.harness_facts(220, ziel=self.root / "out")
        self.assertIn("kein weiterer Anstoss: max_fortsetzungen (2) erreicht", text)
        self.assertNotIn("UEBERTRAG", text)

    def test_fortsetzungen_zeile_haengt_den_grund_an(self):
        o = Orchestrator(self.cfg, self.log, mock=True,
                         state_file=self.root / "state" / "run.json")
        st = {"fortsetzungen": [{"minute": 42.0, "kontext": 300000,
                                 "antwort_kurz": "NACHRUECKLISTE ERLEDIGT"}],
              "fortsetzung_grund": worker.UEBERTRAG_GRUND, "fortsetzung_uebertrag": True}
        zeile = o.fortsetzungen_zeile(st)
        self.assertIn("#1 bei 42 min", zeile)
        self.assertIn(TEXT, zeile)


if __name__ == "__main__":
    unittest.main()
