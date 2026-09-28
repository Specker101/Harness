"""Tests fuer R13e: Sammelauftrag nach der ersten Nacht (Punkte 1, 2, 4, 6-10).

Alles im Attrappenbetrieb: kein Netz, keine API-Kosten, kein Ghidra, und das
Decomp-Repo wird nie angefasst (Git-Tests laufen in einem Wegwerf-Repo).
"""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import protocol, reviewer as rvmod, state as st, streamjson, worker  # noqa: E402
from hx.config import load_config                                   # noqa: E402
from hx.orchestrator import Orchestrator                            # noqa: E402
from hx.profiles import load_profile                                # noqa: E402
from hx.util import Log, ensure_dir                                 # noqa: E402
from hx.watch import Watcher                                        # noqa: E402


def _git(repo: Path, *args: str) -> int:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True).returncode


def _assistant(usage: dict, mid: str = "m1", text: str = "hallo") -> str:
    return json.dumps({"type": "assistant",
                       "message": {"id": mid, "model": "deepseek-flash[1m]", "usage": usage,
                                   "content": [{"type": "text", "text": text}]}})


class _ReviewStub:
    """Minimaler Ersatz fuer reviewer.ReviewResult (kein Mock - Logs brauchen Werte)."""

    def __init__(self):
        self.text = "x"
        self.parsed = protocol.Review()
        self.review_dir = ""
        self.review_file = ""
        self.raw_path = ""
        self.limit_reached = False
        self.session_id = None
        self.model_seen = "claude-opus-5-5"
        self.model_ok = True
        self.rc = 0
        self.duration_s = 1.0
        self.error = ""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__file__).resolve().parent / "_tmp_r13e"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.repo = ensure_dir(self.tmp / "repo")
        _git(self.repo, "init", "-q")
        (self.repo / "a.txt").write_text("eins\n", encoding="utf-8")
        _git(self.repo, "add", "a.txt")
        _git(self.repo, "-c", "user.name=T", "-c", "user.email=t@example.invalid",
             "commit", "-q", "-m", "start")

        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.tmp / "root")
        cfg.data["paths"]["decomp"] = str(self.repo)
        cfg.data["paths"]["secrets"] = str(ensure_dir(self.tmp / "secrets"))
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["telegram"]["allowlist_user_ids"] = []
        cfg.data["mock"]["enabled"] = True
        # Die echten Profile in das Wegwerf-Root kopieren (load_profile liest dort).
        prof = ensure_dir(self.tmp / "root" / "profiles")
        for f in (ROOT / "profiles").glob("*.json"):
            shutil.copy2(f, prof / f.name)
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)
        self.orch = Orchestrator(cfg, self.log, mock=True,
                                 state_file=self.tmp / "root" / "state" / "run.json")
        self.orch.say = lambda *a, **k: None

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def watcher(self, **kw) -> Watcher:
        return Watcher(self.cfg, self.log, color=False, once=True, **kw)

    def commit(self, text: str) -> None:
        """Echten Commit erzeugen - Inhalt aendert sich mit der Nachricht.

        Gleicher Inhalt => git legt keinen Commit an, HEAD bliebe stehen.
        """
        (self.repo / "a.txt").write_text(text + "\n", encoding="utf-8")
        _git(self.repo, "add", "a.txt")
        _git(self.repo, "-c", "user.name=T", "-c", "user.email=t@example.invalid",
             "commit", "-q", "-m", text)


# ---------------------------------------------------- Punkt 1: laufender Review
class TestWatchReviewDir(Base):
    def test_review_ordner_kommt_aus_dem_zustand(self):
        """Das Review von Batch N liegt in runs/b<N+1> - nicht in runs/b<N>."""
        w = self.watcher()
        zustand = {"batch": 161, "last_batch_number": 161,
                   "review": {"dir": str(self.tmp / "root" / "runs" / "b162")}}
        self.assertEqual(w._review_dir(zustand).name, "b162")

    def test_ohne_zustandsangabe_naechster_ordner(self):
        """Alter Zustand (Feld fehlt): Nummer nach dem Anker rechnen."""
        w = self.watcher()
        self.assertEqual(w._review_dir({"batch": 173, "last_batch_number": 173}).name, "b174")

    def test_bewerteter_batch_wird_benannt(self):
        rd = ensure_dir(self.tmp / "run")
        (rd / "harness-facts.md").write_text(
            "- Review: bewertet wird Batch 173; die Instruktion gilt fuer Batch 174\n",
            encoding="utf-8")
        self.assertEqual(self.watcher()._bewerteter_batch(rd), "173")

    def test_do_review_schreibt_den_ordner_in_den_zustand(self):
        self.orch.state.data["batch"] = 161
        self.orch.state.data["last_batch_number"] = 161
        # Kennung setzen, damit keine Rotation/Uebergabe ausgeloest wird.
        # R13ab: dazu gehoert der Hash des Systemprompts - fehlt er, rotiert der Harness
        # einmal (Session aus einer aelteren Fassung).
        self.orch.state.data["reviewer"] = {
            "session_id": "s-test", "reviews": 1, "force_rotate": False,
            "prompt_hash": rvmod.prompt_hash(self.cfg)}
        rv = _ReviewStub()
        with mock.patch("hx.orchestrator.rv.run_review", return_value=rv), \
             mock.patch.object(self.orch, "expected_batch", return_value=162):
            self.orch.do_review("batch_end", "snap")
        self.assertEqual(Path(self.orch.state.data["review"]["dir"]).name, "b162")
        self.assertEqual(self.orch.state.data["review"]["evidence"], 161)


# --------------------------------------------- Punkt 8/9: watch-Werte und -Grenzen
class TestWatchWerte(Base):
    def test_grenzen_kommen_aus_der_konfiguration(self):
        text = self.watcher()._limits_text()
        # R13p: Alarm 500 / Hart 1000 (vorher 250/400 - die harte Grenze lag zu knapp
        # ueber dem Normalbetrieb und haette den Alarm unerreichbar gemacht).
        self.assertIn("500", text)
        self.assertIn("1000", text)
        self.assertIn("90 min", text)
        self.assertIn("180 min", text)

    def test_werte_werden_pro_batch_gerechnet(self):
        """`_print_stats` zeigt den laufenden Batch; erst der Wechsel summiert."""
        w = self.watcher()
        w.stats.feed(_assistant({"input_tokens": 100, "cache_read_input_tokens": 0,
                                 "cache_creation_input_tokens": 0, "output_tokens": 7}))
        w.stats.feed(_assistant({"input_tokens": 50, "cache_read_input_tokens": 0,
                                 "cache_creation_input_tokens": 0, "output_tokens": 3},
                                mid="m2"))
        self.assertEqual(len(w.stats.requests), 2)
        w.batch_nr = 174
        puffer = io.StringIO()
        with redirect_stdout(puffer):
            w._print_stats(force=True)
        self.assertIn("Batch 174 laufend: 2 Anfragen", puffer.getvalue())
        self.assertNotIn("seit watch-Start", puffer.getvalue())   # noch kein Vorlauf
        w._stats_umlegen()
        self.assertEqual(w.ges_requests, 2)
        self.assertEqual(w.ges_batches, 1)
        w.stats = streamjson.StreamStats()                        # neuer Batch
        w.stats.feed(_assistant({"input_tokens": 1, "cache_read_input_tokens": 0,
                                 "cache_creation_input_tokens": 0, "output_tokens": 1},
                                mid="m3"))
        puffer = io.StringIO()
        with redirect_stdout(puffer):
            w._print_stats(force=True)
        self.assertIn("Batch 174 laufend: 1 Anfragen", puffer.getvalue())
        self.assertIn("seit watch-Start: 1 Batch(es), 3 Anfragen", puffer.getvalue())

    def test_batch_ende_im_pausenzustand_wird_gemeldet(self):
        """Punkt 9: Ende und Zustand danach auch pausiert sichtbar."""
        w = self.watcher()
        rd = ensure_dir(self.tmp / "runs" / "b174")
        (rd / "result.json").write_text(json.dumps(
            {"batch": 174, "rc": 0, "duration_s": 60, "cost_usd": 0.1, "model_seen": "x",
             "model_ok": True, "stats": {"requests": 5}}), encoding="utf-8")
        puffer = io.StringIO()
        with redirect_stdout(puffer):
            w._batch_ende_melden({"paused": True}, rd, 174)
        text = puffer.getvalue()
        self.assertIn("Batch 174", text)
        self.assertIn("PAUSIERT", text)
        self.assertIn("Review zu Batch 174 steht aus", text)
        self.assertTrue(w.review_shown)

    def test_batch_ende_ohne_pause(self):
        w = self.watcher()
        rd = ensure_dir(self.tmp / "runs" / "b175")
        (rd / "result.json").write_text(json.dumps(
            {"batch": 175, "rc": 0, "duration_s": 60, "cost_usd": 0.1, "model_seen": "x",
             "model_ok": True, "stats": {"requests": 5}}), encoding="utf-8")
        puffer = io.StringIO()
        with redirect_stdout(puffer):
            w._batch_ende_melden({"paused": False}, rd, 175)
        self.assertIn("Review folgt", puffer.getvalue())
        self.assertNotIn("PAUSIERT", puffer.getvalue())


# ------------------------------------------------ Punkt 4: Reviewer-Limit
class TestLimit(Base):
    def test_zeitpunkt_aus_der_meldung(self):
        wann = protocol.parse_limit_reset(
            "Usage limit reached. Your limit will reset at 2026-09-25 22:00 UTC.")
        self.assertEqual(wann, datetime(2026, 9, 25, 22, 0, tzinfo=timezone.utc))

    def test_zeitpunkt_ohne_datum_ist_lokal(self):
        jetzt = datetime(2026, 9, 26, 10, 0, tzinfo=timezone.utc)
        wann = protocol.parse_limit_reset("Your limit will reset at 3pm.", now=jetzt)
        self.assertIsNotNone(wann)
        self.assertGreater(wann, jetzt)

    def test_ohne_zeitpunkt_stuendlich(self):
        wann, quelle = self.orch.limit_wait_ziel("Limit erreicht, kein Datum")
        rest = (wann - datetime.now(timezone.utc)).total_seconds()
        self.assertGreater(rest, 55 * 60)
        self.assertIn("stuendliche", quelle)

    def test_wartezustand_setzt_von_selbst_fort(self):
        self.orch.state.set(st.LIMIT_WAIT, "Pro-Limit erreicht")
        self.orch.state.data["paused"] = True
        self.orch.state.data["limit_wait_until"] = (
            datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(timespec="seconds")
        self.assertFalse(self.orch.limit_wait_tick(), "noch nicht faellig")
        self.assertTrue(self.orch.state.data["paused"])

        self.orch.state.data["limit_wait_until"] = (
            datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(timespec="seconds")
        self.assertTrue(self.orch.limit_wait_tick(), "faellig -> fortsetzen")
        self.assertFalse(self.orch.state.data["paused"])
        self.assertEqual(self.orch.state.state, st.IDLE)
        self.assertNotIn("limit_wait_until", self.orch.state.data)

    def test_nutzerpause_schlaegt_den_wartezustand(self):
        self.orch.state.set(st.LIMIT_WAIT, "Pro-Limit erreicht")
        self.orch.state.data["limit_wait_until"] = (
            datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(timespec="seconds")
        self.orch._do_pause("per Telegram pausiert")
        self.assertNotIn("limit_wait_until", self.orch.state.data)
        self.assertFalse(self.orch.limit_wait_tick(), "ausdrueckliche Pause bleibt")


# ---------------------------------------------- Punkt 7: Pause vs. Harness-Commits
class TestPause(Base):
    def test_harness_commit_ist_keine_handarbeit(self):
        self.orch.state.data["batch"] = 173
        self.orch._do_pause("test")
        self.assertEqual(self.orch.state.data["pause_since"]["batch"], 173)
        self.commit("B173: Vorhersage")
        self.orch.mark_harness_head(173)
        self.commit("Batch 173: Scheibe 4 gemessen")
        self.orch._do_resume()
        self.assertFalse(self.orch.state.data.get("pause_work"),
                         "nur Harness-Batches -> kein Handarbeits-Hinweis")
        self.assertFalse(self.orch.state.data["paused"])

    def test_handarbeit_neben_harness_commit_wird_getrennt(self):
        self.orch._do_pause("test")
        self.commit("B173: Vorhersage")
        self.orch.mark_harness_head(173)
        self.commit("Handarbeit des Nutzers")
        self.orch._do_resume()
        info = self.orch.state.data.get("pause_work") or {}
        self.assertEqual(len(info.get("commits_hand") or []), 1)
        self.assertEqual(len(info.get("commits_harness") or []), 0)
        note = self.orch.pause_work_note()
        self.assertIn("in der Pause", note)
        self.assertIn("1 Handarbeit", note)

    def test_note_trennt_harness_und_handarbeit(self):
        self.orch._do_pause("test")
        self.commit("B173: Vorhersage")
        self.orch.mark_harness_head(173)
        self.commit("Handarbeit des Nutzers")
        self.orch._do_resume()
        note = self.orch.pause_work_note()
        self.assertIn("Harness-Batch (keine Handarbeit)", note)


# --------------------------- Punkt 2/10: Stream-Auswertung (Fehler, HTTP-Beruehrung)
class TestStreamAuswertung(unittest.TestCase):
    def stats(self, *lines: str) -> streamjson.StreamStats:
        s = streamjson.StreamStats()
        for l in lines:
            s.feed(l)
        return s

    @staticmethod
    def tool_result(text: str, tid: str = "t1", is_error: bool = True) -> str:
        return json.dumps({"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": tid, "content": text,
             "is_error": is_error}]}})

    @staticmethod
    def tool_use(name: str, inp: dict, tid: str = "t1") -> str:
        return json.dumps({"type": "assistant", "message": {
            "id": "m1", "content": [{"type": "tool_use", "id": tid, "name": name,
                                     "input": inp}]}})

    def test_gesperrtes_werkzeug_wird_erkannt(self):
        s = self.stats(self.tool_use("mcp__ghidra__load_program", {}))
        s.feed(self.tool_result("<tool_use_error>Error: No such tool available: "
                                "mcp__ghidra__load_program</tool_use_error>"))
        self.assertEqual(len(s.tool_errors), 1)
        self.assertEqual(s.tool_errors[0]["art"], "gesperrt")
        self.assertEqual(s.tool_errors[0]["name"], "mcp__ghidra__load_program")

    def test_fehlende_freigabe_zaehlt_als_gesperrt(self):
        """Genau die Meldung der Nacht zu search_tools/check_tools/load_tool_group."""
        s = self.stats(self.tool_use("mcp__ghidra__search_tools", {"query": "x"}))
        s.feed(self.tool_result("Permission for this tool use was denied. It requires "
                                "approval, and this session has no approval surface."))
        self.assertEqual(s.tool_errors[0]["art"], "gesperrt")

    def test_zitat_im_leseergebnis_ist_keine_ablehnung(self):
        """Ein Dokument, das den Fehlersatz zitiert, ist kein abgelehnter Aufruf."""
        s = self.stats(self.tool_use("Read", {"file_path": "notes.md"}))
        s.feed(self.tool_result("1\tNo such tool available: mcp__ghidra__load_program\n"
                                "2\tDas steht in ghidra-mcp-notes.md", is_error=False))
        self.assertEqual(s.tool_errors, [])
        self.assertEqual(s.denials, [])

    def test_echter_werkzeugfehler(self):
        s = self.stats(self.tool_use("PowerShell", {"command": "kaputt"}))
        s.feed(self.tool_result("<tool_use_error>Exit code 1</tool_use_error>"))
        self.assertEqual(s.tool_errors[0]["art"], "fehler")
        self.assertEqual(s.denials, [])

    def test_http_beruehrung_des_zustands_wird_vermerkt(self):
        s = self.stats(self.tool_use("PowerShell", {"command": (
            "curl -X POST http://127.0.0.1:8089/switch_program -d '{}'")}))
        self.assertEqual(len(s.http_state), 1)
        self.assertEqual(s.http_state[0]["endpoint"], "/switch_program")

    def test_http_lesezugriff_ist_kein_vermerk(self):
        s = self.stats(self.tool_use("PowerShell", {"command": (
            "curl http://127.0.0.1:8089/get_metadata")}))
        self.assertEqual(s.http_state, [])

    def test_zitat_im_leseergebnis_ist_kein_http_vermerk(self):
        s = self.stats(self.tool_use("Read", {"file_path": "ghidra-mcp-notes.md"}))
        s.feed(self.tool_result("curl http://127.0.0.1:8089/load_program_from_project",
                                is_error=False))
        self.assertEqual(s.http_state, [])


# ------------------------------ Punkt 10c: Bridge-Gruppen und Profil-Werkzeuglisten
class TestBridgeConfig(Base):
    def test_kein_lazy_bedeutet_keine_default_groups(self):
        prof = load_profile(self.cfg.root, "ghidra-standard")
        p = worker.write_mcp_config(self.cfg, ensure_dir(self.tmp / "run1"), prof)
        daten = json.loads(Path(p).read_text(encoding="utf-8"))
        args = daten["mcpServers"]["ghidra"]["args"]
        self.assertNotIn("--lazy", args)
        self.assertNotIn("--default-groups", args,
                         "im Normalbetrieb laedt die Bridge alle Gruppen; "
                         "allowed/denied entscheiden allein")
        self.assertFalse((self.tmp / "run1" / "mcp-lazy-warnung.txt").exists())

    def test_lazy_wird_sichtbar_gewarnt(self):
        self.cfg.data["ghidra"]["bridge_args"] = ["--lazy"]
        prof = load_profile(self.cfg.root, "ghidra-standard")
        p = worker.write_mcp_config(self.cfg, ensure_dir(self.tmp / "run2"), prof)
        args = json.loads(Path(p).read_text(encoding="utf-8"))["mcpServers"]["ghidra"]["args"]
        self.assertIn("--lazy", args)
        self.assertIn("--default-groups", args)
        self.assertTrue((self.tmp / "run2" / "mcp-lazy-warnung.txt").is_file())

    def test_ausgelieferte_konfiguration_ist_nicht_lazy(self):
        self.assertNotIn("--lazy", list(self.cfg.get("ghidra", "bridge_args") or []))

    def test_alle_erlaubten_werkzeuge_sind_im_normalbetrieb_sichtbar(self):
        """Regression zu Punkt 10c - prueft gegen den Katalog-Schnappschuss.

        GEMESSEN 2026-09-26: mit --lazy zeigt die Bridge nur die Gruppen
        listing/function/program/comment = 97 der 215 Werkzeuge; von den 148
        erlaubten Werkzeugen des Profils ghidra-standard waren damit 76 unsichtbar
        (u. a. get_xrefs_to, search_instructions, get_function_pcode). Nachladen
        ginge nur ueber die gesperrten Hilfswerkzeuge -> der Worker fiel auf HTTP
        aus. Deshalb ist der Normalbetrieb eager (alle Gruppen).
        """
        snap = Path("g:/Harness/sandbox/_ghidra_schema.json")
        if not snap.is_file():
            self.skipTest("kein Ghidra-Katalog-Schnappschuss vorhanden")
        daten = json.loads(snap.read_text(encoding="utf-8"))
        eintraege = daten if isinstance(daten, list) else daten.get("tools", [])
        gruppen: dict[str, set[str]] = {}
        for e in eintraege:
            gruppen.setdefault(str(e.get("category") or "?"), set()).add(
                str(e.get("path", "")).lstrip("/"))
        lazy = set().union(*(gruppen.get(g, set())
                             for g in ("listing", "function", "program", "comment")))
        alle = set().union(*gruppen.values())

        prof = load_profile(self.cfg.root, "ghidra-standard")
        erlaubt = set(prof.data.get("allowed") or [])
        self.assertGreater(len(erlaubt - lazy), 0,
                           "die Lazy-Luecke muss belegt sein (Messgrundlage)")
        self.assertEqual(erlaubt - alle, set(),
                         "jedes erlaubte Werkzeug muss im Katalog stehen")
        self.assertNotIn("--lazy", list(self.cfg.get("ghidra", "bridge_args") or []),
                         "im Normalbetrieb darf --lazy die erlaubten Werkzeuge nicht verstecken")


# --------------------------------------- Punkt 2a/b: Speichern nach jedem Ghidra-Batch
class TestGhidraSpeichernJedesProfil(Base):
    def test_leseprofil_speichert_trotzdem(self):
        res = worker.save_ghidra_after_batch(self.cfg, self.log, self.orch.state,
                                             "ghidra-read", mock=True)
        self.assertTrue(res["needed"], "auch ein Leseprofil kann per HTTP geschrieben haben")
        self.assertFalse(res["blocking"], "ohne HTTP-Beruehrung kein Haltegrund")
        self.assertIn("liest nur", res.get("grund") or "")

    def test_schreibprofil_ist_haltegrund(self):
        res = worker.save_ghidra_after_batch(self.cfg, self.log, self.orch.state,
                                             "ghidra-standard", mock=True)
        self.assertTrue(res["needed"])
        self.assertTrue(res["blocking"])

    def test_http_beruehrung_macht_auch_das_leseprofil_zum_haltegrund(self):
        res = worker.save_ghidra_after_batch(self.cfg, self.log, self.orch.state,
                                             "ghidra-read", mock=True,
                                             http_state=[{"endpoint": "/switch_program"}])
        self.assertTrue(res["blocking"])
        self.assertIn("HTTP", res.get("grund") or "")

    def test_profil_none_speichert_nicht(self):
        res = worker.save_ghidra_after_batch(self.cfg, self.log, self.orch.state,
                                             "none", mock=True)
        self.assertFalse(res["needed"])


# --------------------------------------------- Punkt 2d/10d: Vorspann des Workers
class TestVorspann(Base):
    def test_programmbedeutung_steht_daneben(self):
        text = worker.build_prompt(self.cfg, "Auftrag", "", "/830d01.27p.main.bin",
                                   "ghidra-standard")
        self.assertIn("main.bin = PPC-Hauptprogramm", text)
        self.assertIn("be.bin = Boot-/Loader-Image", text)
        self.assertIn("PROGRAM_REQUEST", text)

    def test_programmwechsel_bleibt_verboten(self):
        text = worker.build_prompt(self.cfg, "Auftrag", "", "/830d01.27p.main.bin", "none")
        self.assertIn("NICHT selbst", text)
        self.assertIn("gesperrt", text)

    def test_http_weg_ist_erlaubt_und_wird_vermerkt(self):
        text = worker.build_prompt(self.cfg, "Auftrag", "", None, "ghidra-read")
        self.assertIn("127.0.0.1:8089 ist ERLAUBT", text)
        self.assertIn("VERMERKT", text)


# ------------------------------------ Punkt 4/5: 68K-Programm am Batch-Rand
class TestProgramm68k(Base):
    def test_alias_68k_loest_auf(self):
        """Der neue Programmname ist ein gueltiger DS_TOOLS-Wert."""
        for alias in ("68k", "sound", "830a08.7s", "830a08.7s.68k", "SOUND.68K"):
            self.assertEqual(protocol.PROGRAM_ALIASES.get(alias.lower()), "/830a08.7s.68k",
                             f"Alias {alias!r} fehlt")
        profil, programm = protocol.parse_tools("profile: ghidra-read\nprogram: 68k")
        self.assertEqual(profil, "ghidra-read")
        self.assertEqual(programm, "/830a08.7s.68k")

    def test_main_und_be_bleiben_unveraendert(self):
        self.assertEqual(protocol.PROGRAM_ALIASES["main"], "/830d01.27p.main.bin")
        self.assertEqual(protocol.PROGRAM_ALIASES["be"], "/830d01.27p.be.bin")

    def test_load_program_bleibt_fuer_den_worker_gesperrt(self):
        """Punkt 5: der Worker bekommt den Import NIE selbst in die Hand."""
        for name in ("ghidra-read", "ghidra-standard", "ghidra-full"):
            d = json.loads((ROOT / "profiles" / f"{name}.json").read_text(encoding="utf-8"))
            hart = set(d.get("hard_denied") or [])
            erlaubt = set(d.get("allowed") or [])
            for gesperrt in ("load_program", "load_program_from_project", "switch_program",
                             "open_program", "close_program", "restore_project",
                             "run_ghidra_script", "save_all_programs"):
                self.assertIn(gesperrt, hart, f"{name}: {gesperrt} muss gesperrt bleiben")
                self.assertNotIn(gesperrt, erlaubt, f"{name}: {gesperrt} darf nicht erlaubt sein")

    def test_reviewer_kennt_das_68k_programm(self):
        text = (ROOT / "prompts" / "reviewer.md").read_text(encoding="utf-8")
        self.assertIn("/830a08.7s.68k", text)
        self.assertIn("68K-Soundprogramm", text)


if __name__ == "__main__":
    unittest.main()
