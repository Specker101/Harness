"""Tests fuer R13al (2026-09-29): Peak-Sperre vervollstaendigen.

Auftrag: (1) **zweite Pruefung direkt vor dem Batch-Start** — der Review kann selbst in
den Peak laufen, das `/approve` kann im Peak kommen, und nach einer Git-Pause kann der
Start beliebig spaet liegen. Der Auftrag bleibt dabei **stehen** (wie bei der Git-Pause)
und startet von selbst, sobald Off-Peak. (2) **Vorlauf** `[peak] peak_vorlauf_min`
(Nutzerentscheid 2026-09-29: **10**): kein Start, wenn das naechste Peak-Fenster innerhalb
dieser Minuten beginnt —
an beiden Pruefstellen. (3) **`/approve jetzt`** startet trotz Peak/Vorlauf, mit dem
Vermerk „trotz Peak gestartet (Nutzer)" im Log und in `result.json`. (4) Feiertagsliste.
(5) Bericht ueber bisherige Peak-Starts (`docs/_r13al_messung.txt`).

Peak: 01:00-04:00 und 06:00-10:00 UTC, Mo-Fr, ausser chinesischen Feiertagen
(`hx/pricing.py::PEAK_WINDOWS_UTC`).
"""

from __future__ import annotations

import json
import shutil
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import pricing, protocol, queue, worker                    # noqa: E402
from hx.config import load_config                                  # noqa: E402
from hx.orchestrator import Orchestrator                           # noqa: E402
from hx.util import Log, ensure_dir, read_json, write_text_atomic  # noqa: E402

# Montag, 2026-09-21: 02:00 UTC = Peak, 00:30 UTC = off-peak (naechster Peak 01:00)
MONTAG_PEAK = datetime(2026, 9, 21, 2, 0, tzinfo=timezone.utc)
MONTAG_VOR_30 = datetime(2026, 9, 21, 0, 30, tzinfo=timezone.utc)
MONTAG_VOR_120 = datetime(2026, 9, 20, 23, 0, tzinfo=timezone.utc)
MONTAG_OFFPEAK = datetime(2026, 9, 21, 16, 0, tzinfo=timezone.utc)
FEIERTAG = datetime(2026, 10, 1, 2, 0, tzinfo=timezone.utc)        # Nationalfeiertag (Do)

ANKER = """# Workstream R1B

**Stand:** BATCH 180 (2026-09-29) - Beispielstand fuer den Test.
**Fertig:** nichts.
**Naechster Schritt:** **(a)** warten.
**Offene Entscheidung:** **(1) GESCHLOSSEN:** nichts.
"""


class _ReviewStub:
    """Minimaler Ersatz fuer `reviewer.ReviewResult` (gueltig, ohne API)."""

    def __init__(self, batch: int = 181):
        self.parsed = protocol.Review()
        self.parsed.blocks = ["TELEGRAM_SUMMARY", "DS_TOOLS", "DS_INSTRUCTION"]
        self.parsed.summary = "Zusammenfassung"
        self.parsed.instruction = f"Batch {batch} - Testauftrag"
        self.parsed.batch = batch
        self.parsed.profile = "none"
        self.parsed.program = None
        self.text = "x"
        self.review_dir = ""
        self.review_file = ""
        self.raw_path = ""
        self.limit_reached = False
        self.session_id = "s1"
        self.model_seen = "claude-opus-5-5"
        self.model_ok = True
        self.rc = 0
        self.duration_s = 1.0
        self.error = ""


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13al"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "root")
        self.decomp = ensure_dir(self.tmp / "decomp")
        write_text_atomic(self.decomp / "analysis" / "r1b-workstream.md", ANKER)
        prof = ensure_dir(self.root / "profiles")
        for f in (ROOT / "profiles").glob("*.json"):
            shutil.copy2(f, prof / f.name)
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.decomp)
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["paths"]["secrets"] = str(ensure_dir(self.tmp / "secrets"))
        cfg.data["telegram"]["allowlist_user_ids"] = []
        cfg.data["mock"]["enabled"] = True
        cfg.data["peak"]["block_new_batches"] = True
        # Der Vorlauf wird HIER ausdruecklich gesetzt: die Tests haengen damit nicht an
        # `harness.toml` (dort steht seit dem Nutzerentscheid 2026-09-29 der Wert 10).
        cfg.data["peak"]["peak_vorlauf_min"] = 90
        cfg.data["peak"]["extra_offpeak_dates"] = []
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)
        self.orch = Orchestrator(cfg, self.log, mock=True,
                                 state_file=self.root / "state" / "run.json")
        self.orch.say = lambda *a, **k: None
        st = self.orch.state
        st.data["batch"] = 180
        st.data["last_batch_number"] = 180
        st.data["paused"] = False
        # Dauerbetrieb: das Gate wird von selbst freigegeben (so laeuft der Harness im
        # Betrieb) - sonst wartet die Schleife auf /approve und der Start ist nicht zu
        # pruefen. `/approve`-Faelle setzen das Flag in ihrem Test selbst.
        st.data["autonomous"] = True
        st.data["delivered"] = []
        st.clear_gate()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ------------------------------------------------------------------ Helfer
    def log_zeilen(self) -> list[dict]:
        p = self.tmp / "log.jsonl"
        if not p.is_file():
            return []
        return [json.loads(z) for z in p.read_text(encoding="utf-8").splitlines() if z.strip()]

    def notbremse(self, max_poll: int = 50) -> None:
        """Sicherheitsnetz fuer die Schleifentests: nach N Durchgaengen Schluss.

        Ohne das kann ein Test, dessen Attrappen nie "starten" sagen, in der while-Schleife
        des Harness haengen bleiben (die `time.sleep`-Aufrufe sind ja abgeschaltet).
        """
        zaehler = {"n": 0}

        def poll(*a, **k):
            zaehler["n"] += 1
            if zaehler["n"] > max_poll:
                self.orch.quit = True

        self.orch.poll = poll

    def lage(self, jetzt: datetime) -> tuple[bool, str]:
        return self.orch.peak_gate(jetzt=jetzt)

    def durchlauf(self, peak_antworten: list[bool] | None = None,
                  trotz_peak: bool = False, bis_worker: bool = True) -> dict:
        """Einen Schleifendurchlauf fahren (wie test_r13u): Attrappen, kein Netz.

        `peak_antworten` ist eine Liste von Antworten der Attrappen-`peak_gate`: so lassen
        sich mehrere Takte im Peak und danach der Off-Peak nachstellen (Reste = True).
        """
        gesehen: dict = {"reviews": 0, "worker": None, "peak_fragen": 0}
        self.orch.review_ok = lambda res: True

        def review(*a, **k):
            gesehen["reviews"] += 1
            return _ReviewStub(batch=self.orch.expected_batch())

        def worker_run(instruction, profile, program, queue_block):
            gesehen["worker"] = instruction
            if bis_worker:
                self.orch.quit = True
            return None

        if peak_antworten is not None:
            antworten = list(peak_antworten)

            def peak_gate(*a, **k):
                gesehen["peak_fragen"] += 1
                return (False, "Peak-Tarif aktiv (Test)") if antworten.pop(0) is False \
                    else (True, "")

            self.orch.peak_gate = peak_gate
        self.orch.do_review = review
        self.orch.run_worker = worker_run
        self.orch.git_preflight = lambda: (True, "")
        self.orch.git.checkpoint = lambda n: f"harness/b{int(n)}-start"
        self.orch.git_push = lambda: (True, "ok")
        self.orch.mark_harness_head = lambda n: None
        zaehler = {"poll": 0}

        def poll(*a, **k):
            zaehler["poll"] += 1
            if zaehler["poll"] > 50:
                self.orch.quit = True

        self.orch.poll = poll
        if trotz_peak and self.orch.state.gate:
            self.orch.approved_peak = (self.orch.state.gate or {}).get("id")
        try:
            with mock.patch("hx.orchestrator.time.sleep", lambda *_: None):
                self.orch._loop()
        finally:
            self.orch.quit = False
        return gesehen


class TestPeakFenster(Basis):
    """Die Rechenregeln: Peak, Vorlauf, frei_ab, Feiertag."""

    def test_peak_ist_peak(self):
        self.assertFalse(self.lage(MONTAG_PEAK)[0])
        self.assertIn("Peak-Tarif aktiv", self.lage(MONTAG_PEAK)[1])

    def test_30_min_vor_dem_peak_ist_gesperrt(self):
        """Start 30 min vor Peak -> wartet (Vorlauf 90 min)."""
        ok, why = self.lage(MONTAG_VOR_30)
        self.assertFalse(ok)
        self.assertIn("Peak beginnt in 30 min", why)
        self.assertIn("Vorlauf 90 min", why)

    def test_120_min_vor_dem_peak_startet(self):
        """Start 120 min vor Peak -> startet (Vorlauf 90 min)."""
        self.assertTrue(self.lage(MONTAG_VOR_120)[0])

    def test_offpeak_startet(self):
        self.assertTrue(self.lage(MONTAG_OFFPEAK)[0])

    # Nutzerentscheid 2026-09-29: der Vorlauf steht auf 10 min. Beide Faelle setzen ihn
    # ausdruecklich, sie haengen also nicht an `harness.toml`.
    def test_5_min_vor_peak_wartet_bei_vorlauf_10(self):
        self.cfg.data["peak"]["peak_vorlauf_min"] = 10
        fuenf_vor = datetime(2026, 9, 21, 0, 55, tzinfo=timezone.utc)   # Peak ab 01:00
        ok, why = self.lage(fuenf_vor)
        self.assertFalse(ok)
        self.assertIn("Peak beginnt in 5 min", why)
        self.assertIn("Vorlauf 10 min", why)
        self.assertTrue(self.lage(datetime(2026, 9, 21, 0, 45, tzinfo=timezone.utc))[0],
                        "45 min vor dem Peak ist der Start erlaubt")

    def test_15_min_vor_peak_startet_bei_vorlauf_10(self):
        self.cfg.data["peak"]["peak_vorlauf_min"] = 10
        fuenfzehn_vor = datetime(2026, 9, 21, 0, 45, tzinfo=timezone.utc)
        self.assertTrue(self.lage(fuenfzehn_vor)[0])

    def test_vorlauf_null_sperrt_nur_das_fenster_selbst(self):
        self.cfg.data["peak"]["peak_vorlauf_min"] = 0
        self.assertTrue(self.lage(MONTAG_VOR_30)[0])
        self.assertFalse(self.lage(MONTAG_PEAK)[0])

    def test_abschaltbar(self):
        self.cfg.data["peak"]["block_new_batches"] = False
        self.assertTrue(self.lage(MONTAG_PEAK)[0])

    def test_frei_ab_ist_wirklich_frei(self):
        for jetzt in (MONTAG_PEAK, MONTAG_VOR_30, MONTAG_VOR_120, MONTAG_OFFPEAK):
            frei = self.orch.peak_frei_ab(jetzt)
            self.assertTrue(self.lage(frei)[0], f"frei_ab({jetzt}) ist nicht frei")
            self.assertGreaterEqual(frei, jetzt)

    def test_feiertag_ist_kein_peak(self):
        """Feiertag -> kein Peak (auch 02:00 UTC an einem Werktag)."""
        self.cfg.data["peak"]["extra_offpeak_dates"] = ["2026-10-01"]
        self.assertTrue(self.lage(FEIERTAG)[0])
        # Ohne den Eintrag waere es Peak (Do 02:00 UTC).
        self.cfg.data["peak"]["extra_offpeak_dates"] = []
        self.assertFalse(self.lage(FEIERTAG)[0])

    def test_feiertage_stehen_in_der_konfiguration(self):
        echt = load_config()
        tage = list(echt.get("peak", "extra_offpeak_dates", []) or [])
        for tag in ("2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06", "2026-10-07"):
            self.assertIn(tag, tage)
        # Nutzerentscheid 2026-09-29: 90 -> 10 (Durchsatz vor dem Peak-Aufschlag).
        self.assertEqual(float(echt.get("peak", "peak_vorlauf_min", 0)), 10.0)

    def test_vorlauf_regeln_in_pricing(self):
        self.assertEqual(pricing.next_peak_start(MONTAG_VOR_120),
                         datetime(2026, 9, 21, 1, 0, tzinfo=timezone.utc))
        self.assertTrue(pricing.im_vorlauf(MONTAG_VOR_30, 90))
        self.assertFalse(pricing.im_vorlauf(MONTAG_VOR_120, 90))
        self.assertTrue(pricing.start_blockiert(MONTAG_PEAK, 90))
        self.assertFalse(pricing.start_blockiert(MONTAG_OFFPEAK, 90))
        # Wochenende: kein kommendes Peak-Fenster an diesem Tag
        sonntag = datetime(2026, 9, 20, 23, 0, tzinfo=timezone.utc)
        self.assertFalse(pricing.start_blockiert(sonntag, 90))


class TestZweitePruefungVorDemStart(Basis):
    """Der Kern: der laufende Batch wird nicht unterbrochen, der neue wartet."""

    def test_start_im_peak_wartet_und_startet_bei_offpeak(self):
        # Review faellig (erste Pruefung: off-peak), dann 2 Takte Peak, dann off-peak.
        gesehen = self.durchlauf(peak_antworten=[True, False, False, True])
        self.assertEqual(gesehen["worker"], "Batch 181 - Testauftrag",
                         "nach dem Off-Peak muss gestartet werden")
        self.assertGreaterEqual(gesehen["peak_fragen"], 4)
        self.assertTrue(any("PEAK: Auftrag wartet" in str(z.get("msg") or "")
                            for z in self.log_zeilen()), "Warten muss im Log stehen")
        # Der Auftrag bleibt waehrend des Wartens stehen (kein neuer Review).
        self.assertEqual(gesehen["reviews"], 1, "ein wartender Auftrag wird nicht neu bewertet")

    def test_wartezustand_steht_im_zustand(self):
        folge = [True, False, False, True]          # Review, Peak, Peak, dann Off-Peak

        def peak_gate(*a, **k):
            return ((True, "") if folge.pop(0) else (False, "Peak-Tarif aktiv (Test)")) \
                if folge else (True, "")

        zustand: dict = {}

        def worker_run(*a, **k):
            zustand["gestartet"] = str(a[0] if a else k.get("instruction") or "")
            self.orch.quit = True

        self.orch.peak_gate = peak_gate
        self.orch.do_review = lambda *a, **k: _ReviewStub(batch=181)
        self.orch.review_ok = lambda res: True
        self.orch.run_worker = worker_run
        self.orch.git_preflight = lambda: (True, "")
        self.orch.git.checkpoint = lambda n: f"harness/b{int(n)}-start"
        self.orch.git_push = lambda: (True, "ok")
        self.orch.mark_harness_head = lambda n: None
        self.notbremse()
        gesetzt: list[str] = []
        echt_set = self.orch.state.set

        def merken(name, grund="", **kw):
            gesetzt.append(f"{name}: {grund}")
            return echt_set(name, grund, **kw)

        self.orch.state.set = merken
        with mock.patch("hx.orchestrator.time.sleep", lambda *_: None):
            self.orch._loop()
        self.assertTrue(gesetzt, f"der Wartezustand muss gesetzt werden; log={self.log_zeilen()}")
        self.assertTrue(any("PEAK" in z for z in gesetzt), f"{gesetzt} | log={self.log_zeilen()}")
        self.assertTrue(any(z.startswith("GATE_APPROVAL") for z in gesetzt), gesetzt)
        self.assertEqual(zustand.get("gestartet"), "Batch 181 - Testauftrag",
                         "nach dem Off-Peak muss der wartende Auftrag starten")

    def test_verworfener_auftrag_beendet_das_warten(self):
        """`/review` waehrend des Wartens: kein Start mit einem verworfenen Auftrag.

        Der zweite Takt der Attrappen-`peak_gate` verwirft den Auftrag (so wie es der
        Befehl `/review` tut). Danach darf NICHTS mehr starten - das Warten endet, und der
        naechste Durchgang beginnt mit einem neuen Review.
        """
        gesehen: dict = {"worker": None, "takten": 0}
        self.orch.review_ok = lambda res: True
        self.orch.do_review = lambda *a, **k: _ReviewStub(batch=181)
        self.orch.run_worker = lambda *a, **k: gesehen.update(worker="gestartet")
        self.orch.git_preflight = lambda: (True, "")
        self.orch.git_checkpoint = lambda n: f"harness/b{int(n)}-start"
        self.orch.git.checkpoint = lambda n: f"harness/b{int(n)}-start"
        self.orch.git_push = lambda: (True, "ok")
        self.orch.mark_harness_head = lambda n: None
        self.notbremse()

        def peak_gate(*a, **k):
            """Takt 1: Review zulassen. Ab Takt 2: Peak; in Takt 3 verwirft "/review"."""
            gesehen["takten"] += 1
            takt = gesehen["takten"]
            if takt == 1:
                return True, ""
            if takt == 3:
                self.orch.state.clear_gate()
                self.orch.approved_gate = None
            if takt > 40:
                self.orch.quit = True
            return False, "Peak-Tarif aktiv (Test)"

        self.orch.peak_gate = peak_gate
        with mock.patch("hx.orchestrator.time.sleep", lambda *_: None):
            self.orch._loop()
        self.assertIsNone(gesehen["worker"], "verworfener Auftrag darf nicht starten")
        self.assertTrue(any(str(z.get("msg") or "").startswith("PEAK-Warten beendet")
                            for z in self.log_zeilen()),
                        f"log={self.log_zeilen()}")

    def test_keine_peak_pruefung_im_laufenden_batch(self):
        """Die Sperre gilt nur VOR dem Start - im laufenden Batch gibt es keine Pruefung."""
        import inspect
        quelle = inspect.getsource(Orchestrator._loop)
        nach_worker = quelle[quelle.index("self.run_worker("):]
        self.assertNotIn("peak_gate", nach_worker,
                         "ein laufender Batch wird nie unterbrochen")

    def test_offpeak_startet_sofort_ohne_zu_warten(self):
        gesehen = self.durchlauf(peak_antworten=[True, True])
        self.assertEqual(gesehen["worker"], "Batch 181 - Testauftrag")
        self.assertFalse(any("PEAK: Auftrag wartet" in str(z.get("msg") or "")
                             for z in self.log_zeilen()))

    def test_laufender_batch_wird_nicht_unterbrochen(self):
        """Die Sperre greift nur VOR dem Start - der Worker laeuft durch."""
        gesehen = self.durchlauf(peak_antworten=[True, True])
        self.assertEqual(gesehen["worker"], "Batch 181 - Testauftrag")
        self.assertEqual(gesehen["reviews"], 1)


class TestApproveJetzt(Basis):
    """`/approve jetzt` ist der bewusste Ausweg."""

    def test_approve_im_peak_wartet(self):
        """Normales /approve respektiert die Sperre (kein Vermerk)."""
        self.orch.state.set_gate("g1", "s", "Batch 181 - x",
                                 {"profile": "none", "batch": 181}, "")
        self.orch.handle_command("/approve")
        self.assertEqual(self.orch.approved_gate, "g1")
        self.assertIsNone(self.orch.approved_peak)
        self.assertTrue(self.orch.gate_approved())

    def test_approve_jetzt_setzt_den_ausweg(self):
        self.orch.state.set_gate("g1", "s", "Batch 181 - x",
                                 {"profile": "none", "batch": 181}, "")
        self.orch.handle_command("/approve jetzt")
        self.assertEqual(self.orch.approved_gate, "g1")
        self.assertEqual(self.orch.approved_peak, "g1")
        self.assertTrue(any("Freigabe trotz Peak (Nutzer)" == str(z.get("msg") or "")
                            for z in self.log_zeilen()), f"log={self.log_zeilen()}")

    def test_approve_mit_text_bleibt_ds_nachricht(self):
        self.orch.state.set_gate("g1", "s", "Batch 181 - x",
                                 {"profile": "none", "batch": 181}, "")
        self.orch.handle_command("/approve bitte die Bilanz vorziehen")
        self.assertIsNone(self.orch.approved_peak)
        nachrichten = queue.pending(self.root, "ds")
        self.assertEqual(len(nachrichten), 1)
        self.assertIn("Bilanz", nachrichten[0].text)

    def test_jetzt_startet_im_peak_mit_vermerk(self):
        """Der Vermerk muss im Log UND in `result.json` landen."""
        self.orch.review_ok = lambda res: True
        self.orch.do_review = lambda *a, **k: _ReviewStub(batch=181)
        self.orch.git_preflight = lambda: (True, "")
        self.orch.git.checkpoint = lambda n: f"harness/b{int(n)}-start"
        self.orch.git_push = lambda: (True, "ok")
        self.orch.mark_harness_head = lambda n: None
        self.notbremse()
        gesehen: dict = {}

        def worker_run(instruction, profile, program, queue_block):
            gesehen["hinweis_waehrend_lauf"] = self.orch.state.data.get("peak_hinweis")
            # so, wie `_finish_run` es liest (der Harness hat den Vermerk vorher gesetzt)
            gesehen["result"] = {"peak_hinweis": self.orch.state.data.get("peak_hinweis")}
            self.orch.quit = True

        self.orch.run_worker = worker_run
        self.orch.peak_gate = lambda *a, **k: (False, "Peak-Tarif aktiv (Test)")
        self.orch.approved_gate = None
        self.orch.state.set_gate("g1", "s", "Batch 181 - x",
                                 {"profile": "none", "batch": 181}, "")
        self.orch.approved_gate = "g1"
        self.orch.approved_peak = "g1"
        with mock.patch("hx.orchestrator.time.sleep", lambda *_: None):
            self.orch._loop()
        self.assertEqual(gesehen["hinweis_waehrend_lauf"], "trotz Peak gestartet (Nutzer)")
        self.assertEqual(gesehen["result"]["peak_hinweis"], "trotz Peak gestartet (Nutzer)")
        self.assertTrue(any("trotz Peak gestartet (Nutzer)" == str(z.get("msg") or "")
                            for z in self.log_zeilen()))
        # Nach dem Lauf ist der Vermerk weg (er gilt nur fuer diesen einen Start).
        self.assertIsNone(self.orch.state.data.get("peak_hinweis"))

    def test_worker_schreibt_den_vermerk_in_result_json(self):
        """`worker._finish_run` nimmt den Vermerk aus dem Zustand in `result.json`."""
        from hx import streamjson
        res = worker.WorkerResult()
        stats = streamjson.StreamStats()
        state = mock.Mock()
        state.data = {"peak_hinweis": "trotz Peak gestartet (Nutzer)"}
        with mock.patch("hx.worker.write_json_atomic") as schreiben, \
                mock.patch("hx.worker.write_snapshot", return_value=""):
            worker._finish_run(self.cfg, state, res, stats, 181, "none", self.log,
                               ghidra_save=False)
        self.assertTrue(schreiben.called)
        pfad, nutzlast = schreiben.call_args[0][0], schreiben.call_args[0][1]
        self.assertIn("result.json", str(pfad))
        self.assertEqual(nutzlast.get("peak_hinweis"),
                         "trotz Peak gestartet (Nutzer)")

    def test_ohne_vermerk_kein_feld_in_result_json(self):
        """Ein normaler Lauf traegt das Feld NICHT (kein Rauschen in den Messdaten)."""
        from hx import streamjson
        res = worker.WorkerResult()
        stats = streamjson.StreamStats()
        state = mock.Mock()
        state.data = {}
        with mock.patch("hx.worker.write_json_atomic") as schreiben, \
                mock.patch("hx.worker.write_snapshot", return_value=""):
            worker._finish_run(self.cfg, state, res, stats, 181, "none", self.log,
                               ghidra_save=False)
        self.assertNotIn("peak_hinweis", schreiben.call_args[0][1])


class TestPeakBericht(Basis):
    """Punkt 5 des Auftrags: die Sonde muss laufen und darf nichts erfinden."""

    def test_sonde_und_beleg_liegen_im_repo(self):
        p = ROOT.parent / "docs" / "_r13al_peakstart_probe.py"
        beleg = ROOT.parent / "docs" / "_r13al_messung.txt"
        self.assertTrue(p.is_file())
        self.assertTrue(beleg.is_file())
        text = beleg.read_text(encoding="utf-8")
        self.assertIn("Im PEAK gestartet:", text)
        # Kein Batch bisher im Peak (gemessen 2026-09-29) - die Nachtlaeufe lagen am
        # Wochenende, und Sa/So sind immer off-peak.
        self.assertIn("Im PEAK gestartet: 0", text)

    def test_starte_batch_steht_nicht_im_log(self):
        """Der Auftrag nennt `logs/` als Quelle - die Zeile gibt es dort nicht."""
        import re as _re
        treffer = []
        for p in (ROOT / "logs").glob("harness-*.log"):
            if _re.search(r'"Starte Batch', p.read_text(encoding="utf-8", errors="replace")):
                treffer.append(p.name)
        self.assertEqual(treffer, [], "wenn die Zeile doch im Log steht, Beleg anpassen")


if __name__ == "__main__":
    unittest.main()
