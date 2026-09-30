"""Tests fuer R13aw (2026-09-30): `antwort.md` wird nicht mehr ueberschrieben.

**Auftrag (Aussensicht B219, Befund 1, Gewicht hoch).** Beleg: `runs/b214/antwort.md:1` bis
`runs/b218/antwort.md:1` enthalten nur „NACHRUECKLISTE ERLEDIGT"; der Pflichtbericht mit den
Abschnitten 1-6 stand nur im Mitschnitt (`runs/b217/stream.jsonl:74417`, erstes
`result`-Ereignis). Ursache: bei jeder Fortsetzung schrieb `worker._finish_run`
`stats.final_text()` - und das ist der LETZTE `result`-Text.

Jetzt gilt: der **erste** Antworttext bleibt in `antwort.md`, jede Fortsetzung bekommt
`antwort-forts<k>.md`, und Reviewer/Aussensicht bekommen beides mit Ueberschrift
(`worker.antwort_text`). Fuer B214-B218 traegt `docs/_r13aw_nachtrag.py` den ersten Bericht
als `antwort-bericht.md` nach (Ergebnis: fuenf Dateien, `docs/_r13aw_nachtrag.txt`).
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

from hx import streamjson, worker                                  # noqa: E402
from hx.config import load_config                                  # noqa: E402
from hx.orchestrator import Orchestrator                           # noqa: E402
from hx.util import Log, ensure_dir, read_text, write_json_atomic, write_text_atomic  # noqa: E402

BERICHT = "## 1) Uebernommener Stand\n\nAlle Commits liegen, Baum sauber.\n"
FORTS = "NACHRUECKLISTE ERLEDIGT\n- 1a) 0abc123\n"


def antwort_zeile(text: str, num_turns: int = 5) -> str:
    """Ein `result`-Ereignis der CLI (so steht die Antwort im Mitschnitt)."""
    return json.dumps({"type": "result", "subtype": "success", "result": text,
                       "num_turns": num_turns, "is_error": False})


def stats_aus(*texte: str) -> streamjson.StreamStats:
    st = streamjson.StreamStats()
    for t in texte:
        st.feed(antwort_zeile(t))
    return st


class TestAntwortTeile(unittest.TestCase):
    def test_ein_lauf_hat_einen_text(self):
        self.assertEqual(worker.antwort_teile(stats_aus(BERICHT)), [BERICHT])

    def test_zwei_laeufe_haben_zwei_texte(self):
        """Der Kern des Befunds: der erste Text darf nicht verloren gehen."""
        self.assertEqual(worker.antwort_teile(stats_aus(BERICHT, FORTS)), [BERICHT, FORTS])

    def test_final_text_ist_der_letzte(self):
        """Warum es passiert ist - `final_text()` nimmt den LETZTEN Text."""
        st = stats_aus(BERICHT, FORTS)
        self.assertEqual(st.final_text().strip(), FORTS.strip())
        self.assertEqual(worker.antwort_teile(st)[0].strip(), BERICHT.strip())

    def test_leere_ereignisse_zaehlen_nicht(self):
        self.assertEqual(worker.antwort_teile(stats_aus(BERICHT, "   ")), [BERICHT])

    def test_ohne_result_greift_der_antworttext(self):
        st = streamjson.StreamStats()
        st.texts = ["nur Text, kein result-Ereignis"]
        self.assertEqual(worker.antwort_teile(st), ["nur Text, kein result-Ereignis"])

    def test_ohne_alles_leer(self):
        self.assertEqual(worker.antwort_teile(streamjson.StreamStats()), [])
        self.assertEqual(worker.antwort_teile(None), [])


class TestAntwortText(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13aw"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.rd = ensure_dir(self.tmp / "runs" / "b220")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_bericht_allein(self):
        write_text_atomic(self.rd / "antwort.md", BERICHT)
        text = worker.antwort_text(self.rd)
        self.assertIn("## Bericht des Workers (antwort.md)", text)
        self.assertIn("Alle Commits liegen", text)

    def test_bericht_und_fortsetzungen_mit_ueberschrift(self):
        write_text_atomic(self.rd / "antwort.md", BERICHT)
        write_text_atomic(self.rd / "antwort-forts1.md", FORTS)
        write_text_atomic(self.rd / "antwort-forts2.md", "noch ein Posten\n")
        text = worker.antwort_text(self.rd)
        self.assertIn("## Bericht des Workers (antwort.md)", text)
        self.assertIn("## Fortsetzung 1 (antwort-forts1.md)", text)
        self.assertIn("## Fortsetzung 2 (antwort-forts2.md)", text)
        # Reihenfolge: Bericht steht VOR den Fortsetzungen.
        self.assertLess(text.index("Bericht des Workers"), text.index("Fortsetzung 1"))
        self.assertLess(text.index("Fortsetzung 1"), text.index("Fortsetzung 2"))

    def test_fortsetzungen_numerisch_sortiert(self):
        write_text_atomic(self.rd / "antwort.md", BERICHT)
        for k in (1, 2, 10):
            write_text_atomic(self.rd / f"antwort-forts{k}.md", f"Antwort Nummer {k}\n")
        text = worker.antwort_text(self.rd)
        self.assertLess(text.index("Antwort Nummer 1"), text.index("Antwort Nummer 2"))
        self.assertLess(text.index("Antwort Nummer 2"), text.index("Antwort Nummer 10"))

    def test_nachgetragener_bericht_steht_vorn(self):
        """B214-B218: der Bericht liegt als `antwort-bericht.md` daneben."""
        write_text_atomic(self.rd / "antwort-bericht.md", BERICHT)
        write_text_atomic(self.rd / "antwort.md", FORTS)
        text = worker.antwort_text(self.rd)
        self.assertIn("## Bericht (antwort-bericht.md, nachgetragen)", text)
        self.assertIn("## Kurzantwort (antwort.md, vor der Umstellung ueberschrieben)", text)
        self.assertLess(text.index("Bericht (antwort-bericht.md"), text.index("Kurzantwort"))

    def test_leerer_ordner_ergibt_leer(self):
        self.assertEqual(worker.antwort_text(self.rd), "")


class TestFinishRunSchreibtGetrennt(unittest.TestCase):
    """`_finish_run` mit einem Mitschnitt aus zwei Teillaeufen - echte Dateien."""

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13aw_finish"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "root")
        self.decomp = ensure_dir(self.tmp / "decomp")
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

    def lauf(self, *texte: str, batch: int = 220):
        rd = ensure_dir(self.root / "runs" / f"b{batch:03d}")
        stats = stats_aus(*texte)
        res = worker.WorkerResult()
        state = mock.Mock()
        state.data = {}
        with mock.patch("hx.worker.write_snapshot", return_value=""), \
                mock.patch.object(worker.reihenfolge, "git_zeilen", return_value=[]):
            worker._finish_run(self.cfg, state, res, stats, batch, "none", self.log,
                               ghidra_save=False)
        return rd, res

    def test_ein_lauf_schreibt_nur_antwort(self):
        rd, res = self.lauf(BERICHT)
        self.assertEqual(read_text(rd / "antwort.md").strip(), BERICHT.strip())
        self.assertFalse((rd / "antwort-forts1.md").is_file())
        self.assertEqual(res.antwort_dateien, ["antwort.md"])

    def test_fortsetzung_bekommt_eigene_datei(self):
        rd, res = self.lauf(BERICHT, FORTS)
        self.assertEqual(read_text(rd / "antwort.md").strip(), BERICHT.strip(),
                         "der erste Bericht bleibt stehen")
        self.assertEqual(read_text(rd / "antwort-forts1.md").strip(), FORTS.strip())
        self.assertEqual(res.antwort_dateien, ["antwort.md", "antwort-forts1.md"])

    def test_drei_teillaeufe_drei_dateien(self):
        rd, _res = self.lauf(BERICHT, FORTS, "zweite Fortsetzung\n")
        self.assertEqual(read_text(rd / "antwort.md").strip(), BERICHT.strip())
        self.assertEqual(read_text(rd / "antwort-forts1.md").strip(), FORTS.strip())
        self.assertEqual(read_text(rd / "antwort-forts2.md").strip(),
                         "zweite Fortsetzung")
        self.assertEqual(len(list(rd.glob("antwort*.md"))), 3)

    def test_result_json_nennt_die_dateien(self):
        with mock.patch("hx.worker.write_json_atomic") as schreiben, \
                mock.patch("hx.worker.write_snapshot", return_value=""), \
                mock.patch.object(worker.reihenfolge, "git_zeilen", return_value=[]):
            res = worker.WorkerResult()
            state = mock.Mock()
            state.data = {}
            worker._finish_run(self.cfg, state, res, stats_aus(BERICHT, FORTS), 220,
                               "none", self.log, ghidra_save=False)
        nutzlast = schreiben.call_args[0][1]
        self.assertEqual(nutzlast.get("antwort_dateien"),
                         ["antwort.md", "antwort-forts1.md"])

    def test_snapshot_text_enthaelt_beides(self):
        """`res.final_text` ist der GANZE Lauf - sonst zeigte der Snapshot die Kurzantwort."""
        _rd, res = self.lauf(BERICHT, FORTS)
        self.assertIn("Alle Commits liegen", res.final_text)
        self.assertIn("NACHRUECKLISTE ERLEDIGT", res.final_text)


class TestReviewerBekommtBeides(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13aw_review"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "root")
        self.decomp = ensure_dir(self.tmp / "decomp")
        (self.decomp / "analysis").mkdir(parents=True, exist_ok=True)
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

    def test_worker_report_enthaelt_bericht_und_fortsetzung(self):
        rd = ensure_dir(self.root / "runs" / "b220")
        write_text_atomic(rd / "antwort.md", BERICHT)
        write_text_atomic(rd / "antwort-forts1.md", FORTS)
        o = Orchestrator(self.cfg, self.log, mock=True,
                         state_file=self.root / "state" / "run.json")
        o.say = lambda *a, **k: None
        o.state.data["batch"] = 220
        ctx = o.review_context("(snapshot)")
        report = ctx["worker_report"]
        self.assertIn("Alle Commits liegen", report)
        self.assertIn("## Fortsetzung 1 (antwort-forts1.md)", report)
        self.assertIn("NACHRUECKLISTE ERLEDIGT", report)

    def test_marker_aus_dem_bericht_werden_gefunden(self):
        """Die Marker stehen im ERSTEN Bericht - vorher waren sie mit ihm verschwunden."""
        rd = ensure_dir(self.root / "runs" / "b220")
        write_text_atomic(rd / "antwort.md",
                          "## 1) Stand\n\n<TOOL_REQUEST>mcp__ghidra__read_memory"
                          "</TOOL_REQUEST>\n")
        write_text_atomic(rd / "antwort-forts1.md", FORTS)
        o = Orchestrator(self.cfg, self.log, mock=True,
                         state_file=self.root / "state" / "run.json")
        o.say = lambda *a, **k: None
        o.state.data["batch"] = 220
        ctx = o.review_context("(snapshot)")
        self.assertIn("mcp__ghidra__read_memory", ctx["worker_report"])


if __name__ == "__main__":
    unittest.main()
