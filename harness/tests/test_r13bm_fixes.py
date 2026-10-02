"""Tests fuer R13bm (02.10.2026): die vier Vorschlaege aus R13bl-4.

Je Punkt ein Abschnitt, je Punkt ein Commit:

  1. **`api_errors` befuellen** - API-/Gateway-Fehler im Mitschnitt erkennen und mit
     Zeitpunkt, gekuerztem Text und **Mitschnittzeile** nach `result.json` tragen.
     Fixture: `tests/fixtures/b235_api_fehler.jsonl` = wortgetreuer Ausschnitt der Zeilen
     28439-28442 aus `runs/b235/stream.jsonl` (die Fehlerzeile ist die vom Nutzer
     genannte `:28441`).
  2. **Infrastrukturabbruch als eigene Klasse** (`killed_reason = "infra"`): `rc != 0` UND
     die letzte Modellantwort ist ein API-/Gateway-Fehler. Folge: **kein** Review,
     derselbe Batch startet nach 15 min als Fortsetzung neu (Gate-Quelle `infra`, ohne
     `/approve`); nach zwei Neustarts Pause plus Telegram. Budgets gelten weiter.
  3. **Session-Limit ist ein Wartezustand**, kein verworfener Review: der Rohtext liegt
     als `review-limit-<stempel>-v<versuch>.md` (nicht `review-verworfen-…`), und die
     Wiedereinstiegszeit ist die gelesene Reset-Zeit **plus 5 min Puffer**; auch der
     zweite Review-Versuch laeuft nicht in `review_failed`.
  4. Aussensicht an dieselbe Limit-Uhr.

Alles laeuft in Wegwerf-Verzeichnissen; das Decomp-Repo und der laufende Batch bleiben
unberuehrt.
"""

from __future__ import annotations

import json
import shutil
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "b235_api_fehler.jsonl"

from hx import protocol, state as st, streamjson, worker             # noqa: E402
from hx import reviewer as rvmod                                     # noqa: E402
from hx.config import load_config                                    # noqa: E402
from hx.orchestrator import INFRA_MAX_NEUSTARTS, Orchestrator        # noqa: E402
from hx.util import Log, ensure_dir, write_text_atomic               # noqa: E402


def _zeilen() -> list[str]:
    return FIXTURE.read_text(encoding="utf-8").splitlines()


# ================================================== 1) API-Fehler erkennen
class TestApiFehler(unittest.TestCase):
    """Punkt 1: der Fehler aus B235 wird erkannt (echter Mitschnitt-Ausschnitt)."""

    def setUp(self):
        self.stats = streamjson.StreamStats()
        for zeile in _zeilen():
            self.stats.feed(zeile)

    def test_fixture_ist_der_echte_ausschnitt(self):
        self.assertEqual(len(_zeilen()), 4, "vier Zeilen (28439-28442)")
        self.assertIn('"<synthetic>"', _zeilen()[2], "die Fehlerzeile liegt in Zeile 3")

    def test_fehler_wird_erkannt_mit_zeit_text_und_zeile(self):
        self.assertEqual(len(self.stats.api_errors), 1)
        e = self.stats.api_errors[0]
        self.assertEqual(e["zeile"], 3, "dritte Fixture-Zeile = stream.jsonl:28441")
        self.assertTrue(e["ts"].startswith("2026-10-01T"), e["ts"])
        self.assertTrue(e["text"].startswith("API Error:"), e["text"][:60])
        self.assertLessEqual(len(e["text"]), streamjson.API_FEHLER_TEXT)
        self.assertNotIn("\n", e["text"], "der Text wird auf eine Zeile gezogen")

    def test_letzter_text_ist_der_fehler(self):
        """Genau das ist die Bedingung der Klasse „Infrastrukturabbruch" (Punkt 2)."""
        self.assertTrue(self.stats.letzter_text_api_fehler)

    def test_normaler_bericht_ist_kein_fehler(self):
        s = streamjson.StreamStats()
        s.feed(json.dumps({"type": "assistant", "message": {
            "id": "m1", "model": "deepseek-flash[1m]",
            "content": [{"type": "text",
                         "text": "Ergebnis: fertig.\nAPI Error: war ein Gateway-Problem."}]}}))
        self.assertEqual(s.api_errors, [])
        self.assertFalse(s.letzter_text_api_fehler)

    def test_letzter_text_zaehlt_nicht_der_fruehere(self):
        """Ein Fehler in der MITTE (danach lief es weiter) ist kein Infrastrukturabbruch."""
        s = streamjson.StreamStats()
        s.feed(json.dumps({"type": "assistant", "message": {
            "id": "m1", "model": "<synthetic>",
            "content": [{"type": "text", "text": "API Error: Gateway - neuer Versuch"}]}}))
        s.feed(json.dumps({"type": "assistant", "message": {
            "id": "m2", "model": "deepseek-flash[1m]",
            "content": [{"type": "text", "text": "Ergebnis: alles gebaut."}]}}))
        self.assertEqual(len(s.api_errors), 1, "der Fehler bleibt belegt")
        self.assertFalse(s.letzter_text_api_fehler, "aber der LETZTE Text ist normal")

    def test_synthetische_nachricht_zaehlt_auch_ohne_api_error(self):
        """Die CLI erzeugt auch andere Synthetik-Texte (`<synthetic>` ist das Kennzeichen)."""
        s = streamjson.StreamStats()
        s.feed(json.dumps({"type": "assistant", "message": {
            "id": "m1", "model": "<synthetic>",
            "content": [{"type": "text", "text": "Prompt ist zu lang."}]}}))
        self.assertEqual(len(s.api_errors), 1)
        self.assertTrue(s.letzter_text_api_fehler)

    def test_leerer_text_zaehlt_nicht(self):
        s = streamjson.StreamStats()
        s.feed(json.dumps({"type": "assistant", "message": {
            "id": "m1", "model": "<synthetic>",
            "content": [{"type": "text", "text": "   "}]}}))
        self.assertEqual(s.api_errors, [])

    def test_faktenzeile_nennt_den_fehler(self):
        """Der Reviewer sieht die Fehler in `harness-facts.md` (R13bm)."""
        leer = Orchestrator.api_fehler_zeile({})
        self.assertEqual(leer, "keine")
        res = {"stats": {"api_errors": list(self.stats.api_errors)}}
        zeile = Orchestrator.api_fehler_zeile(res)
        self.assertIn("1x", zeile)
        self.assertIn("Mitschnittzeile 3", zeile)
        self.assertIn("API Error:", zeile)


# ============================ 2) Infrastrukturabbruch: Neustart statt Review
class _WorkerStub:
    """Minimaler Ersatz fuer `worker.WorkerResult` (nur, was die Schleife liest)."""

    def __init__(self, rc: int = 0, killed_reason: str | None = None, kosten: float = 0.1):
        self.rc = rc
        self.killed_reason = killed_reason
        self.cost_usd = kosten


class _ReviewStub:
    """Minimaler Ersatz fuer `reviewer.ReviewResult` (gueltig, ohne API)."""

    def __init__(self, batch: int = 237):
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


class TestInfraRegel(unittest.TestCase):
    """Die Regel im Worker (`worker.infra_abbruch_regel`) auf dem echten Mitschnitt."""

    def setUp(self):
        self.stats = streamjson.StreamStats()
        for z in _zeilen():
            self.stats.feed(z)

    def test_rc_api_fehler_und_kein_anderer_grund(self):
        regel = worker.infra_abbruch_regel
        self.assertTrue(self.stats.letzter_text_api_fehler, "Vorbedingung: Fehler am Ende")
        self.assertTrue(regel(1, None, self.stats.letzter_text_api_fehler))
        self.assertFalse(regel(0, None, self.stats.letzter_text_api_fehler),
                         "rc=0 ist kein Abbruch")
        self.assertFalse(regel(1, "wall", self.stats.letzter_text_api_fehler),
                         "eine Zeitgrenze bleibt eine Zeitgrenze")
        self.assertFalse(regel(1, None, False), "ohne API-Fehler keine Infrastruktur")
        self.assertFalse(regel(None, None, True), "ohne rc keine Aussage")

    def test_frueherer_fehler_ist_kein_infrastrukturabbruch(self):
        """Ein Fehler in der MITTE (danach lief es weiter) bleibt ein inhaltlicher Fall."""
        s = streamjson.StreamStats()
        for z in _zeilen():
            s.feed(z)
        s.feed(json.dumps({"type": "assistant", "message": {
            "id": "m9", "model": "deepseek-flash[1m]",
            "content": [{"type": "text", "text": "Bericht: alles gebaut."}]}}))
        self.assertEqual(len(s.api_errors), 1, "der Fehler bleibt belegt")
        self.assertFalse(s.letzter_text_api_fehler)
        self.assertFalse(worker.infra_abbruch_regel(1, None, s.letzter_text_api_fehler))


class BasisOrch(unittest.TestCase):
    """Wegwerf-Wurzel nach dem Muster von `test_r13al_fixes` (kein Netz, kein Decomp)."""

    ANKER = "# Workstream R1B\n\n**Stand:** BATCH 236 (2026-10-02) - Teststand.\n"

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13bm_orch"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "root")
        self.decomp = ensure_dir(self.tmp / "decomp")
        write_text_atomic(self.decomp / "analysis" / "r1b-workstream.md", self.ANKER)
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
        cfg.data["limits"]["hard_cost_usd"] = 2.0
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)
        self.orch = Orchestrator(cfg, self.log, mock=True,
                                 state_file=self.root / "state" / "run.json")
        self.gesagt: list[str] = []
        self.orch.say = self.gesagt.append
        s = self.orch.state
        s.data["batch"] = 236
        s.data["last_batch_number"] = 236
        s.data["paused"] = False
        s.data["autonomous"] = True
        s.data["delivered"] = []
        s.clear_gate()
        self.batch = self.orch.expected_batch()               # 237
        self.assertEqual(self.batch, 237, "Vorbedingung der Tests")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---------------------------------------------------------------- Helfer
    def log_zeilen(self) -> list[dict]:
        p = self.tmp / "log.jsonl"
        if not p.is_file():
            return []
        return [json.loads(z) for z in p.read_text(encoding="utf-8").splitlines() if z.strip()]

    def start_bar(self, worker_fn, max_poll: int = 40) -> dict:
        """Die Schleife mit Attrappen fahren; `worker_fn(n, instruction)` liefert den Lauf.

        `peak_gate` ist fest auf Off-Peak gestellt: die zweite Peak-Pruefung sitzt im
        Startpfad, und dieser Test soll nicht am Kalender haengen.
        """
        gesehen: dict = {"reviews": 0, "starts": []}
        spur: list[str] = []
        echt_set = self.orch.state.set

        def set_merken(name, grund="", **kw):
            spur.append(str(name).split(".")[-1])
            return echt_set(name, grund, **kw)

        self.orch.state.set = set_merken

        def review(*a, **k):
            gesehen["reviews"] += 1
            spur.append(f"review{gesehen['reviews']}")
            return _ReviewStub(batch=self.orch.expected_batch())

        def worker_run(instruction, profile, program, block):
            gesehen["starts"].append(instruction)
            spur.append(f"start{len(gesehen['starts'])}")
            return worker_fn(len(gesehen["starts"]), instruction)

        self.orch.do_review = review
        self.orch.review_ok = lambda res: True
        self.orch.peak_gate = lambda *a, **k: (True, "")
        self.orch.run_worker = worker_run
        self.orch.git_preflight = lambda: (True, "")
        self.orch.git.checkpoint = lambda n: f"harness/b{int(n)}-start"
        self.orch.git_push = lambda: (True, "ok")
        self.orch.mark_harness_head = lambda n: None
        zaehler = {"n": 0}

        def poll(*a, **k):
            zaehler["n"] += 1
            if zaehler["n"] > max_poll:
                self.orch.quit = True

        self.orch.poll = poll
        try:
            with mock.patch("hx.orchestrator.time.sleep", lambda *_: None):
                self.orch._loop()
        finally:
            self.orch.quit = False
        gesehen["trace"] = spur
        return gesehen


class TestInfraNeustart(BasisOrch):
    """Der Auftrag: kein Review, derselbe Batch als Fortsetzung, nach 2 Neustarts Pause."""

    def test_nur_infra_ist_ein_infrastrukturabbruch(self):
        self.assertTrue(self.orch.infra_abbruch(_WorkerStub(rc=1, killed_reason="infra")))
        self.assertFalse(self.orch.infra_abbruch(_WorkerStub(rc=1)))
        self.assertFalse(self.orch.infra_abbruch(_WorkerStub(rc=1, killed_reason="wall")))
        self.assertFalse(self.orch.infra_abbruch(None))

    def test_ohne_infra_kein_neustart(self):
        """Ein inhaltlicher Abbruch laeuft unveraendert in den Review."""
        self.assertFalse(self.orch.infra_wait_planen(_WorkerStub(rc=1), self.batch,
                                                     "Auftrag", "none", None))
        self.assertIsNone(self.orch.state.gate, "kein neuer Auftrag")
        self.assertNotIn("infra_wait_until", self.orch.state.data)

    def test_kein_review_und_neustart_desselben_batches(self):
        """Der Kern: derselbe Batch wird fortgesetzt, ohne dass ein Review laeuft."""
        def worker_fn(n, instruction):
            if n >= 2:
                self.orch.quit = True
                return _WorkerStub(rc=0)        # der Neustart laeuft durch
            # Die Klasse setzt der Worker (`worker.infra_abbruch_regel`, oben geprueft) -
            # hier wird sie vorausgesetzt, denn geprueft wird die Folge im Harness.
            return _WorkerStub(rc=1, killed_reason="infra")

        with mock.patch("hx.orchestrator.INFRA_WARTE_MIN", 0.0):
            gesehen = self.start_bar(worker_fn)
        self.assertEqual(len(gesehen["starts"]), 2, "erst der Lauf, dann der Neustart")
        self.assertEqual(gesehen["reviews"], 1,
                         "der Infrastrukturabbruch wird NICHT bewertet: "
                         + " -> ".join(gesehen["trace"]))
        self.assertIn("FORTSETZUNG NACH INFRASTRUKTURFEHLER", gesehen["starts"][1])
        self.assertIn("Zwischenstand-Commits", gesehen["starts"][1])
        s = self.orch.state
        self.assertEqual(int(s.data["infra_neustarts"][str(self.batch)]), 1)
        self.assertFalse(s.data.get("paused"), "die Wartezeit hebt sich selbst auf")
        self.assertNotIn("infra_wait_until", s.data)
        self.assertTrue(any("INFRASTRUKTUR-ABBRUCH" in t for t in self.gesagt), self.gesagt)
        self.assertTrue(any("Neustart geplant" in str(z.get("msg") or "")
                            for z in self.log_zeilen()), self.log_zeilen())

    def test_gate_ist_ohne_approve_freigegeben(self):
        """`source = "infra"` - der Neustart laeuft ohne `/approve` an."""
        self.orch.state.data["autonomous"] = False
        self.assertTrue(self.orch.infra_wait_planen(
            _WorkerStub(rc=1, killed_reason="infra"), self.batch,
            "Batch 237 - Testauftrag", "ghidra-standard", "Prog"))
        s = self.orch.state
        gate = s.gate
        self.assertIsNotNone(gate)
        self.assertEqual(gate["tools"]["source"], "infra")
        self.assertTrue(gate["tools"]["fortsetzung"], "der vorige Lauf wird gesichert")
        self.assertEqual(int(gate["tools"]["batch"]), self.batch, "DERSELBE Batch")
        self.assertIn("Fortsetzung nach Infrastrukturfehler", gate["summary"])
        self.assertIn("Neustart 1 von 2", gate["summary"])
        self.assertIn("Batch 237 - Testauftrag", gate["instruction"],
                      "der alte Auftrag bleibt erhalten")
        self.assertTrue(self.orch.gate_approved(gate), "Quelle `infra` braucht kein /approve")
        self.assertTrue(s.data["paused"])
        self.assertEqual(s.state, st.PAUSED)
        ziel = datetime.fromisoformat(s.data["infra_wait_until"])
        rest = (ziel - datetime.now(timezone.utc)).total_seconds()
        self.assertGreater(rest, 14 * 60, "15 Minuten Wartezeit")
        self.assertEqual(s.data["letzter_abbruch"]["grund"], "infra")

    def test_dritter_abbruch_pausiert_und_meldet(self):
        """Nach zwei Neustarts ist Schluss - Pause, Meldung, kein neuer Auftrag."""
        self.orch.state.data["infra_neustarts"] = {str(self.batch): INFRA_MAX_NEUSTARTS}
        self.assertTrue(self.orch.infra_wait_planen(
            _WorkerStub(rc=1, killed_reason="infra"), self.batch,
            "Auftrag", "none", None))
        s = self.orch.state
        self.assertTrue(s.data["paused"])
        self.assertEqual(s.state, st.PAUSED)
        self.assertIsNone(s.gate, "kein neuer Auftrag")
        self.assertNotIn("infra_wait_until", s.data)
        self.assertEqual(int(s.data["infra_neustarts"][str(self.batch)]), INFRA_MAX_NEUSTARTS)
        self.assertTrue(any("verbraucht" in t for t in self.gesagt), self.gesagt)

    def test_batch_budget_verhindert_den_neustart(self):
        """Das Batch-Budget gilt auch fuer den Neustart (Kosten aller Laeufe zusammen)."""
        rd = ensure_dir(self.root / "runs" / f"b{self.batch:03d}")
        write_text_atomic(rd / "result.json", json.dumps({"cost_usd": 1.5}))
        vor = ensure_dir(rd / "lauf1")
        write_text_atomic(vor / "result.json", json.dumps({"cost_usd": 0.7}))
        self.assertAlmostEqual(self.orch.infra_batch_kosten(self.batch), 2.2, places=6)
        self.assertTrue(self.orch.infra_wait_planen(
            _WorkerStub(rc=1, killed_reason="infra"), self.batch, "Auftrag", "none", None))
        s = self.orch.state
        self.assertTrue(s.data["paused"])
        self.assertIsNone(s.gate)
        self.assertNotIn("infra_wait_until", s.data, "kein Neustart geplant")
        self.assertTrue(any("Batch-Budget" in t for t in self.gesagt), self.gesagt)

    def test_tagesbudget_verhindert_den_neustart(self):
        self.orch.daily_budget_left = lambda: 0.0
        self.assertTrue(self.orch.infra_wait_planen(
            _WorkerStub(rc=1, killed_reason="infra"), self.batch, "Auftrag", "none", None))
        self.assertTrue(self.orch.state.data["paused"])
        self.assertIsNone(self.orch.state.gate)
        self.assertTrue(any("Tagesbudget" in t for t in self.gesagt), self.gesagt)

    def test_inhaltlicher_abbruch_bleibt_unveraendert(self):
        """`rc != 0` OHNE API-Fehler: alles wie bisher - bewerten, kein Neustart."""
        def worker_fn(n, instruction):
            return _WorkerStub(rc=1)

        gesehen = self.start_bar(worker_fn, max_poll=4)
        self.assertGreaterEqual(gesehen["reviews"], 2, "es wird weiter bewertet")
        self.assertNotIn("infra_neustarts", self.orch.state.data)
        self.assertNotIn("infra_wait_until", self.orch.state.data)
        self.assertFalse(self.orch.state.data.get("paused"))


class TestInfraWartezeit(BasisOrch):
    """`infra_wait_tick` - die Wartezeit endet von selbst (Muster `limit_wait_tick`)."""

    def test_zukunft_wartet(self):
        s = self.orch.state
        s.data["paused"] = True
        s.data["infra_wait_until"] = (datetime.now(timezone.utc)
                                      + timedelta(minutes=10)).isoformat(timespec="seconds")
        s.set(st.PAUSED, "Infrastruktur-Abbruch - Neustart")
        self.assertFalse(self.orch.infra_wait_tick())
        self.assertTrue(s.data["paused"])
        self.assertIn("infra_wait_until", s.data)
        self.assertEqual(s.state, st.PAUSED)

    def test_vergangenheit_setzt_fort(self):
        s = self.orch.state
        s.data["paused"] = True
        s.data["infra_wait_until"] = (datetime.now(timezone.utc)
                                      - timedelta(minutes=1)).isoformat(timespec="seconds")
        s.set(st.PAUSED, "Infrastruktur-Abbruch - Neustart")
        self.assertTrue(self.orch.infra_wait_tick())
        self.assertFalse(s.data["paused"])
        self.assertNotIn("infra_wait_until", s.data)
        self.assertEqual(s.state, st.GATE_APPROVAL)
        self.assertTrue(any("ist vorbei" in t for t in self.gesagt), self.gesagt)

    def test_nur_im_pausenzustand(self):
        """Ohne Pause kein Takten - sonst wuerde ein Warteziel den Betrieb umstellen."""
        s = self.orch.state
        s.data["infra_wait_until"] = (datetime.now(timezone.utc)
                                      - timedelta(minutes=1)).isoformat(timespec="seconds")
        s.set(st.IDLE, "idle")
        self.assertFalse(self.orch.infra_wait_tick())
        self.assertIn("infra_wait_until", s.data)
        self.assertEqual(s.state, st.IDLE)

    def test_kaputte_zeitangabe_wird_verworfen(self):
        s = self.orch.state
        s.data["paused"] = True
        s.data["infra_wait_until"] = "kein Zeitstempel"
        s.set(st.PAUSED, "Infrastruktur-Abbruch - Neustart")
        self.assertFalse(self.orch.infra_wait_tick())
        self.assertNotIn("infra_wait_until", s.data, "der Wert wird nicht mitgeschleppt")
        self.assertTrue(s.data["paused"], "aber die Pause bleibt stehen")

    def test_pause_des_nutzers_loescht_die_wartezeit(self):
        """`/pause` schlaegt den Selbst-Neustart (wie beim Limit-Warten, R13e)."""
        s = self.orch.state
        s.data["infra_wait_until"] = (datetime.now(timezone.utc)
                                      + timedelta(minutes=10)).isoformat(timespec="seconds")
        self.orch._do_pause("Handarbeit")
        self.assertNotIn("infra_wait_until", s.data)
        self.assertTrue(s.data["paused"])


# ======================== 3) Session-Limit ist ein Wartezustand, kein Fehlschlag
LIMIT_MELDUNG = ("Usage limit reached. Your limit will reset at 2099-01-01 12:00 UTC.")
LIMIT_ZIEL = datetime(2099, 1, 1, 12, 0, tzinfo=timezone.utc)


class TestLimitWartezustand(BasisOrch):
    """Punkt 3: `review-limit-…` statt `review-verworfen-…`, Wiedereinstieg mit Puffer."""

    def _reviewer_state_setzen(self):
        self.orch.state.data["reviewer"] = {
            "session_id": "s-test", "reviews": 1, "force_rotate": False,
            "prompt_hash": rvmod.prompt_hash(self.cfg)}

    def test_puffer_auf_die_gelesene_reset_zeit(self):
        wann, quelle = self.orch.limit_wait_ziel(LIMIT_MELDUNG)
        self.assertEqual(wann, LIMIT_ZIEL + timedelta(minutes=5))
        self.assertIn("Puffer", quelle)
        self.assertIn("12:00", quelle)

    def test_ohne_lesbaren_zeitpunkt_stuendlich_ohne_puffer(self):
        """Ohne Zeitpunkt in der Meldung bleibt es bei der stuendlichen Pruefung."""
        wann, quelle = self.orch.limit_wait_ziel("Limit erreicht, kein Datum")
        rest = (wann - datetime.now(timezone.utc)).total_seconds()
        self.assertGreater(rest, 55 * 60)
        self.assertLessEqual(rest, 61 * 60)
        self.assertIn("stuendliche", quelle)

    def test_limit_review_heisst_nicht_verworfen(self):
        """Der Rohtext wird abgelegt - aber unter `review-limit-…`, nicht `verworfen`."""
        self._reviewer_state_setzen()
        stub = _ReviewStub(batch=self.batch)
        stub.limit_reached = True
        stub.text = LIMIT_MELDUNG
        with mock.patch("hx.orchestrator.rv.run_review", return_value=stub), \
             mock.patch.object(self.orch, "expected_batch", return_value=self.batch):
            res = self.orch.do_review("batch_end", "snap")
        self.assertTrue(res.limit_reached)
        rd = self.root / "runs" / f"b{self.batch:03d}"
        self.assertEqual(len(list(rd.glob("review-limit-*-v1.md"))), 1,
                         sorted(p.name for p in rd.glob("*.md")))
        self.assertEqual(list(rd.glob("review-verworfen-*.md")), [],
                         "ein Limit ist kein verworfener Review")
        self.assertNotIn("review.md", [p.name for p in rd.glob("*.md")])
        s = self.orch.state
        self.assertEqual(s.state, st.LIMIT_WAIT)
        self.assertTrue(s.data["paused"], "das Limit ist ein Wartezustand")
        self.assertEqual(datetime.fromisoformat(s.data["limit_wait_until"]),
                         LIMIT_ZIEL + timedelta(minutes=5))
        self.assertIn("Puffer", s.data["limit_wait_quelle"])

    def test_limit_im_zweiten_versuch_ist_kein_fehlschlag(self):
        """Der zweite Versuch darf NICHT in `review_failed` laufen (Punkt 3)."""
        kaputt = _ReviewStub(batch=self.batch)          # kein Protokollblock
        limit = _ReviewStub(batch=self.batch)
        limit.limit_reached = True
        limit.text = LIMIT_MELDUNG
        folge = [kaputt, limit]
        gerufen: list[dict] = []

        def review_mock(*a, **k):
            gerufen.append(k)
            return folge.pop(0) if folge else limit

        self.orch.do_review = review_mock
        # Beide Antworten sind formal ungueltig - der Punkt ist, dass das LIMIT vor jeder
        # Bewertung greift (`if res.limit_reached: continue`) und nicht `review_failed`.
        self.orch.review_ok = lambda res: False
        self.orch.peak_gate = lambda *a, **k: (True, "")
        zaehler = {"n": 0}

        def poll(*a, **k):
            zaehler["n"] += 1
            if zaehler["n"] > 5:
                self.orch.quit = True

        self.orch.poll = poll
        try:
            with mock.patch("hx.orchestrator.time.sleep", lambda *_: None):
                self.orch._loop()
        finally:
            self.orch.quit = False
        self.assertEqual([k.get("attempt") for k in gerufen[:2]], [None, 2],
                         "erst der normale Review, dann der Wiederholungsversuch")
        self.assertGreaterEqual(len(gerufen), 2)
        self.assertEqual(list((self.root / "logs").glob("review-verworfen-*.json")), [],
                         "kein Fehlschlag-Protokoll fuer ein Limit")
        self.assertNotEqual(self.orch.state.state, st.PAUSED, "kein Haltegrund")
        self.assertFalse(any("ZWEIMAL OHNE PROTOKOLLBLOCK" in t for t in self.gesagt),
                         self.gesagt)


if __name__ == "__main__":
    unittest.main()
