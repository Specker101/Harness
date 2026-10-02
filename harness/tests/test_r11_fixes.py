"""Attrappen-Tests fuer die Korrekturen aus R11.

  1. git laeuft nicht interaktiv und bricht bei Zeitueberschreitung ab.
  2. Token-Zaehlung: Maximum je message.id, Ausgabe aus dem result-Ereignis,
     Gegenprobe; Kosten daraus.
  3. Werkzeugkette: PATH-Zusaetze werden gesucht und VOR den geerbten PATH gelegt.
  4. watch: Statuszeile nur bei Aenderung, Phase des Harness sichtbar.
  5. Reviewer-Modell: Abweichung => Review verworfen, Meldung, keine Freigabe.
  6. rebuild: Lauf aus dem Mitschnitt nachrechnen (ohne doppelte Kosten).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import envs, reviewer as rvmod, streamjson, watch, worker   # noqa: E402
from hx.config import load_config                                    # noqa: E402
from hx.gitsafe import GIT_ENV, Git                                  # noqa: E402
from hx.orchestrator import Orchestrator                             # noqa: E402
from hx.proc import run_capture                                      # noqa: E402
from hx.util import Log, ensure_dir                                  # noqa: E402

ANKER = """# Workstream R1B
**Stand:** BATCH 158 (2026-09-25) - irgendwas.
**Naechster Schritt:** (a) **B159:** cc54 verdrahten.
"""


def _git(repo: Path, *args: str) -> int:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True).returncode


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = ensure_dir(Path(__file__).resolve().parent / "_tmp_r11")
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

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


# --------------------------------------------------------------- 1. Git/Zeitlimit
class TestGitNichtInteraktiv(Base):
    def test_zeitlimit_bricht_ab_und_meldet(self):
        rc, _so, se = run_capture([sys.executable, "-c", "import time; time.sleep(30)"],
                                  cwd=str(self.tmp), timeout=2)
        self.assertEqual(rc, -9)
        self.assertIn("ZEITLIMIT", se)

    def test_start_fehler_wird_gemeldet(self):
        rc, _so, se = run_capture(["gibt-es-nicht-xyz"], cwd=str(self.tmp), timeout=5)
        self.assertEqual(rc, -1)
        self.assertIn("Start fehlgeschlagen", se)

    def test_git_env_ist_nicht_interaktiv(self):
        self.assertEqual(GIT_ENV["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(GIT_ENV["GCM_INTERACTIVE"], "never")
        self.assertIn("BatchMode", GIT_ENV["GIT_SSH_COMMAND"])

    def test_push_mit_kaputtem_remote_meldet_statt_zu_haengen(self):
        _git(self.repo, "init", "-q")
        (self.repo / "a.txt").write_text("eins\n", encoding="utf-8")
        _git(self.repo, "add", "a.txt")
        _git(self.repo, "-c", "user.name=T", "-c", "user.email=t@example.invalid",
             "commit", "-q", "-m", "start")
        _git(self.repo, "remote", "add", "kaputt", "file:///gibt/es/nicht")
        self.cfg.data["git"]["remote"] = "kaputt"
        git = Git(self.cfg, self.log)
        ok, text = git.push()
        self.assertFalse(ok)
        self.assertTrue(text.strip(), "es muss eine Meldung geben")
        self.assertLessEqual(git.push_timeout, 300)

    def test_fetch_meldet_fehler(self):
        _git(self.repo, "init", "-q")
        self.cfg.data["git"]["remote"] = "kaputt"
        ok, err = Git(self.cfg, self.log).fetch()
        self.assertFalse(ok)
        self.assertTrue(err.strip())


# --------------------------------------------------------- 2. Token-Zaehlung
class TestTokenZaehlung(Base):
    def _stream(self, pfad: Path, out_summe: int, result_out: int | None):
        zeilen = [
            json.dumps({"type": "system", "subtype": "init", "model": "deepseek-flash[1m]"}),
            # dieselbe Nachricht dreimal, die Nutzung WAEchst (so liefert es Claude Code)
            json.dumps({"type": "assistant", "timestamp": "2026-09-25T20:00:00Z",
                        "message": {"id": "m1", "model": "deepseek-flash",
                                    "usage": {"input_tokens": 100, "cache_read_input_tokens": 0,
                                              "output_tokens": 1},
                                    "content": [{"type": "text", "text": "a"}]}}),
            json.dumps({"type": "assistant", "timestamp": "2026-09-25T20:00:01Z",
                        "message": {"id": "m1", "model": "deepseek-flash",
                                    "usage": {"input_tokens": 100, "cache_read_input_tokens": 0,
                                              "output_tokens": 40},
                                    "content": [{"type": "text", "text": "b"}]}}),
            json.dumps({"type": "assistant", "timestamp": "2026-09-25T20:00:02Z",
                        "message": {"id": "m2", "model": "deepseek-flash",
                                    "usage": {"input_tokens": 5, "cache_read_input_tokens": 900,
                                              "output_tokens": 7},
                                    "content": [{"type": "text", "text": "c"}]}}),
        ]
        if result_out is not None:
            zeilen.append(json.dumps({"type": "result", "subtype": "success", "result": "fertig",
                                      "usage": {"input_tokens": 105, "cache_read_input_tokens": 900,
                                                "cache_creation_input_tokens": 0,
                                                "output_tokens": result_out}}))
        pfad.write_text("\n".join(zeilen) + "\n", encoding="utf-8")

    def _stats(self, pfad: Path) -> streamjson.StreamStats:
        s = streamjson.StreamStats()
        for ln in pfad.read_text(encoding="utf-8").splitlines():
            s.feed(ln)
        return s

    def test_maximum_je_nachricht(self):
        p = self.tmp / "s1.jsonl"
        self._stream(p, 0, 47)
        s = self._stats(p)
        t = s.totals()
        self.assertEqual(t["requests"], 2, "eine Anfrage je message.id")
        self.assertEqual(t["input_miss"], 105)
        self.assertEqual(t["cache_read"], 900)
        # 40 (Maximum aus m1) + 7 (m2) = 47 - nicht 1+5=6 wie beim ersten Ereignis
        self.assertEqual(t["output"], 47)

    def test_ausgabe_kommt_aus_dem_result_ereignis(self):
        p = self.tmp / "s2.jsonl"
        self._stream(p, 0, 5000)          # Ereignisse tragen keine Ausgabe
        s = self._stats(p)
        self.assertEqual(s.totals()["output"], 5000)
        pruef = s.usage_check()
        self.assertTrue(pruef["ok"])
        self.assertEqual(pruef["quelle_output"], "result")

    def test_gegenprobe_meldet_abweichung(self):
        # Ereignisse zaehlen MEHR als das result-Ereignis (Doppelzaehlung): das muss auffallen.
        p = self.tmp / "s3.jsonl"
        self._stream(p, 0, 10)
        s = self._stats(p)
        pruef = s.usage_check()
        self.assertFalse(pruef["ok"])
        self.assertEqual(pruef["diff"]["output"], 47 - 10)
        self.assertEqual(pruef["quelle_output"], "ereignisse")

    def test_kosten_enthalten_die_ausgabe(self):
        p = self.tmp / "s4.jsonl"
        self._stream(p, 0, 5000)
        s = self._stats(p)
        ohne = 0.0
        mit = s.cost_usd()
        from hx import pricing
        ohne = pricing.cost_usd(105, 900, 0, 0, None)
        self.assertGreater(mit, ohne, "Ausgabe muss in die Kosten eingehen")

    def test_ganze_datei_b159(self):
        """Regression: der echte Mitschnitt muss die Gegenprobe bestehen."""
        echt = ROOT / "runs" / "b159" / "stream.jsonl"
        if not echt.is_file():
            self.skipTest("B159-Mitschnitt nicht vorhanden")
        s = streamjson.StreamStats()
        with open(echt, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                s.feed(line)
        pruef = s.usage_check()
        self.assertTrue(pruef["ok"], str(pruef))
        self.assertEqual(s.totals()["output"], s.result_usage()["output"])
        self.assertGreater(s.totals()["output"], 40000)


# ------------------------------------------------------------ 3. Werkzeugkette
class TestWerkzeugkette(Base):
    def test_ucrt64_wird_vor_den_geerbten_path_gelegt(self):
        fake = ensure_dir(self.tmp / "msys64" / "ucrt64" / "bin")
        (fake / "g++.exe").write_text("x", encoding="utf-8")
        with mock.patch.object(envs, "find_msys_ucrt64", return_value=str(fake)):
            pfad, hinweise = envs.resolve_path(self.cfg, {"PATH": "C:\\MinGW\\bin;C:\\Windows"})
        self.assertEqual(pfad.split(";")[0], str(fake))
        self.assertIn("C:\\MinGW\\bin", pfad)
        self.assertEqual(hinweise, [])

    def test_fehlendes_ucrt64_wird_gemeldet(self):
        with mock.patch.object(envs, "find_msys_ucrt64", return_value=None):
            pfad, hinweise = envs.resolve_path(self.cfg, {"PATH": "C:\\Windows"})
        self.assertEqual(pfad, "C:\\Windows")
        self.assertTrue(any("UCRT64" in h for h in hinweise))

    def test_worker_env_hat_die_aufgeloeste_kette(self):
        import os
        env = envs.worker_env(self.cfg, os.environ, "token")
        self.assertIn("PATH", env)
        self.assertTrue(envs.path_of(env))
        # Werkzeuge muessen mit dieser Umgebung messbar sein
        namen = dict(envs.toolchain(env))
        self.assertIn("git", namen)
        self.assertIn("python", namen)
        self.assertNotIn("nicht messbar", namen.get("python", ""))


# ------------------------------------------------------------------ 4. watch
class TestWatchStatus(Base):
    def test_statuszeile_nur_bei_aenderung(self):
        w = watch.Watcher(self.cfg, self.log, color=False)
        p = self.tmp / "stream.jsonl"
        p.write_text(json.dumps({"type": "assistant", "message": {
            "id": "m1", "usage": {"input_tokens": 10, "output_tokens": 3},
            "content": [{"type": "text", "text": "hallo"}]}}) + "\n", encoding="utf-8")
        w._tail(p, "WORKER", "seen_worker")
        aus = StringIO()
        with redirect_stdout(aus):
            w._print_stats()          # erste Zeile: Zahlen sind neu
            w._print_stats()          # unveraendert -> keine zweite Zeile
            w._print_stats()
        self.assertEqual(aus.getvalue().count("laufend:"), 1, aus.getvalue())
        p.write_text(p.read_text(encoding="utf-8") + json.dumps({"type": "assistant", "message": {
            "id": "m2", "usage": {"input_tokens": 5, "output_tokens": 7},
            "content": [{"type": "text", "text": "weiter"}]}}) + "\n", encoding="utf-8")
        w._tail(p, "WORKER", "seen_worker")
        aus2 = StringIO()
        with redirect_stdout(aus2):
            w._print_stats()          # neue Zahlen -> wieder eine Zeile
        self.assertEqual(aus2.getvalue().count("laufend:"), 1)

    def test_phase_wird_angezeigt(self):
        self.orch.say = lambda *a, **k: None
        self.orch.phase("push", "Batch 159")
        self.assertIn("push", self.orch.phase_text())
        aus = StringIO()
        with redirect_stdout(aus):
            watch.Watcher(self.cfg, self.log, once=True).run()
        self.assertIn("Harness: push", aus.getvalue())

    def test_once_zeigt_keinen_fertigen_mitschnitt(self):
        """Ein fertiger Lauf darf die Live-Ansicht nicht fluten - nur Kennzahlen."""
        rd = ensure_dir(self.root / "runs" / "b159")
        (rd / "stream.jsonl").write_text("\n".join(
            json.dumps({"type": "assistant", "message": {
                "id": f"m{i}", "usage": {"output_tokens": 1},
                "content": [{"type": "text", "text": "ALTER LAUF"}]}}) for i in range(5)) + "\n",
            encoding="utf-8")
        (rd / "result.json").write_text(json.dumps(
            {"batch": 159, "rc": 0, "duration_s": 10, "cost_usd": 0.01, "stats": {"requests": 5}}),
            encoding="utf-8")
        self.orch.state.data["last_batch_number"] = 159
        self.orch.state.save()
        aus = StringIO()
        with redirect_stdout(aus):
            watch.Watcher(self.cfg, self.log, once=True).run()
        text = aus.getvalue()
        self.assertNotIn("ALTER LAUF", text, "der alte Mitschnitt wird nicht ausgebreitet")
        self.assertIn("Batch 159", text)
        self.assertIn("watch --batch 159", text)


# --------------------------------------------------------- 5. Reviewer-Modell
class TestReviewerModell(Base):
    def test_mock_traegt_das_modell_der_unklaren_art(self):
        # R13bo: Modellwahl je Batchart. Ohne (bekanntes) Batch ist die Art "unklar" -
        # dann gilt die vorsichtige Seite = `reviewer_modell_b` (Opus). Die B-/C-Wahl
        # deckt `tests/test_r13bo_fixes.py` ab.
        res = rvmod.run_review(self.cfg, self.log, "prompt", mock=True)
        self.assertEqual(res.model_expected, str(self.cfg.get("claude", "reviewer_modell_b")))
        self.assertTrue(res.model_ok, f"gesehen={res.model_seen}")

    def test_command_hat_das_modell_und_der_env_den_effort(self):
        # Ohne `modell` traegt die Kommandozeile die C-Vorgabe (`reviewer_modell`);
        # `run_review` reicht dagegen IMMER das je Batch gewaehlte Modell durch.
        cmd = rvmod.build_command(self.cfg, None, True)
        self.assertEqual(cmd[cmd.index("--model") + 1],
                         str(self.cfg.get("claude", "reviewer_modell")))
        import os
        env = envs.reviewer_env(self.cfg, os.environ, "token")
        self.assertEqual(env["CLAUDE_CODE_EFFORT_LEVEL"], "high")
        self.assertNotEqual(env["CLAUDE_CODE_EFFORT_LEVEL"], "max")

    def test_abweichendes_modell_verwirft_den_review(self):
        echt = rvmod.run_review

        def fake(cfg, log, prompt, **kw):
            res = echt(cfg, log, prompt, **kw)
            res.model_seen = "claude-sonnet-5"
            res.model_ok = False
            res.model_expected = "claude-opus-5-5"
            res.error = "Reviewer-Modell weicht ab: 'claude-sonnet-5' statt 'claude-opus-5-5'"
            return res

        with mock.patch.object(rvmod, "run_review", fake):
            res = self.orch.do_review("bootstrap", "(snapshot)")
        # R13b: do_review verwirft nur (Rohantwort ablegen, nichts zaehlen, kein Gate);
        # ueber Wiederholung/Pause entscheidet die Schleife (tests/test_r13b_fixes.py).
        self.assertFalse(self.orch.review_ok(res), "falsches Modell ist kein gueltiger Review")
        self.assertIn("claude-opus-5-5", self.orch.review_fehler_grund(res))
        self.assertIsNone(self.orch.state.gate, "kein Auftrag aus einem verworfenen Review")
        ziel = Path(self.orch._review_dir)
        self.assertEqual(len(list(ziel.glob("review-verworfen-*-v1.md"))), 1,
                         "die Rohantwort wird als Beleg abgelegt")
        self.assertFalse((ziel / "review-pre.md").is_file())
        self.assertFalse((ziel / "review.md").is_file())
        self.assertEqual(int((self.orch.state.data["reviewer"] or {}).get("reviews", 0)), 0,
                         "ein ungueltiger Review zaehlt nicht")

    def test_modell_und_effort_im_status_und_den_messdaten(self):
        self.orch.say = lambda *a, **k: None
        self.orch.do_review("bootstrap", "(snapshot)")
        self.assertIn("claude-opus-5-5", self.orch.status_text())
        self.assertIn("Effort high", self.orch.status_text())


# --------------------------------------------------------------- 6. rebuild
class TestRebuild(Base):
    def test_rebuild_schreibt_ergebnis_und_verbucht_kosten(self):
        from hx import mock as hxmock
        rd = ensure_dir(self.root / "runs" / "b159")
        hxmock.mock_worker_stream(self.cfg, rd, "Auftrag", None, mode="ok")
        (rd / "auftrag.md").write_text("Ghidra-Profil dieses Laufs: none\n", encoding="utf-8")
        self.orch.state.data["batch"] = 159
        self.orch.state.save()
        res = worker.rebuild_from_stream(self.cfg, self.log, self.orch.state, 159)
        self.assertEqual(res.profile, "none")
        self.assertTrue((rd / "result.json").is_file())
        self.assertTrue((rd / "antwort.md").is_file())
        daten = json.loads((rd / "result.json").read_text(encoding="utf-8"))
        self.assertTrue(daten["rebuilt"])
        self.assertEqual(daten["stats"]["usage_check"]["ok"], True)
        self.assertGreater(res.cost_usd, 0)


if __name__ == "__main__":
    unittest.main()
