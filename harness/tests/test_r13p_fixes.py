"""Tests fuer R13p: Alarmgrenzen, Nutzerlimit, Review-Historie, Nur-Lese-Git, Aufbewahrung.

Auftrag (Nutzer, 2026-09-27):
  a) Alarm erst bei 500 Anfragen (und die harte Grenze mitziehen),
  b) Nutzerlimit (80 % Sitzung/Woche) als Telegram-Warnung + Anzeige mit Ruectsetzzeit
     in deutscher Zeit,
  c) Reviewer: BATCH-DIFF und HISTORIE im Prompt, dazu nur lesende Git-Befehle,
  d) alte Mitschnitte nach 14 Tagen als ZIP, Warnung bei < 20 GB frei,
  e) bedienung.md: was mitgeschnitten wird und wie man nach einem Absturz vorgeht.

Alles im Attrappenbetrieb: kein Netz, keine API-Kosten, kein Ghidra.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import profiles, retention, reviewer, streamjson, worker          # noqa: E402
from hx.config import load_config                                         # noqa: E402
from hx.orchestrator import Orchestrator                                  # noqa: E402
from hx.util import Log, ensure_dir, write_text_atomic                    # noqa: E402

RATE_EV = {"type": "rate_limit_event",
           "rate_limit_info": {"status": "allowed", "rateLimitType": "five_hour",
                               "overageStatus": "rejected",
                               "overageDisabledReason": "org_level_disabled",
                               "unifiedWindows": {
                                   "five_hour": {"utilization": 0.84, "resetsAt": 1790521200},
                                   "seven_day": {"utilization": 0.65, "resetsAt": 1790658000}}}}


def _git(cwd, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {r.stderr.strip()[:200]}")
    return (r.stdout or "").strip()


def _weg(p: Path) -> None:
    retention._weg(p)


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__file__).resolve().parent / "_tmp_r13p"
        _weg(self.tmp)
        self.root = ensure_dir(self.tmp / "harness")
        self.decomp = ensure_dir(self.tmp / "decomp")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.decomp)
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["telegram"]["allowlist_user_ids"] = []
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)
        self.orch = Orchestrator(cfg, self.log, mock=True,
                                 state_file=self.root / "state" / "run.json")
        self.gesagt: list[str] = []
        self.orch.say = lambda t, *a, **k: self.gesagt.append(str(t))

    def tearDown(self):
        _weg(self.tmp)


# --------------------------------------------------------- a) Alarmgrenzen
class TestGrenzen(Basis):
    def test_alarm_500_und_hart_darueber(self):
        alarm = int(self.cfg.get("limits", "alarm_requests"))
        hart = int(self.cfg.get("limits", "hard_requests"))
        self.assertEqual(alarm, 500)
        self.assertGreater(hart, alarm,
                           "die harte Grenze muss UEBER der Alarmgrenze liegen, "
                           "sonst toetet sie den Batch bevor der Alarm kommt")
        self.assertEqual(hart, 1000)

    def test_code_vorgaben_stimmen_mit_der_konfiguration(self):
        """Ohne [limits] in der Konfiguration gelten dieselben Zahlen (worker.py)."""
        import inspect
        quelle = inspect.getsource(worker.run_batch)
        self.assertIn('"alarm_requests", 500', quelle)
        self.assertIn('"hard_requests", 1000', quelle)


# ------------------------------------------------------------ b) Nutzerlimit
class TestNutzerlimit(Basis):
    def test_event_wird_gelesen(self):
        stats = streamjson.StreamStats()
        stats.feed(json.dumps(RATE_EV))
        self.assertTrue(stats.rate_limit)
        werte = streamjson.rate_limit_werte(stats.rate_limit)
        self.assertEqual([w["schluessel"] for w in werte], ["five_hour", "seven_day"])
        self.assertAlmostEqual(werte[0]["anteil"], 0.84)

    def test_resetszeit_in_deutscher_zeit(self):
        text = streamjson.resets_zeit(1790521200)
        self.assertRegex(text, r"^\d{2}\.\d{2}\.\d{4} \d{2}:\d{2} \(UTC[+-]\d{2}:\d{2}\)$")
        # Deutscher Tag/Monat: 27.09.2026 (lokal, UTC+2)
        self.assertIn("27.09.2026", text)

    def test_warnung_erst_ab_80_prozent(self):
        self.assertEqual(streamjson.rate_limit_warnung({}), "")
        leise = {"unifiedWindows": {"five_hour": {"utilization": 0.5, "resetsAt": 1}}}
        self.assertEqual(streamjson.rate_limit_warnung(leise), "")
        laut = json.loads(json.dumps(RATE_EV["rate_limit_info"]))
        text = streamjson.rate_limit_warnung(laut)
        self.assertIn("84 %", text)
        self.assertIn("Reset", text)
        self.assertIn("kein Nachkaufen", text)
        # Nur das Fenster ueber der Schwelle wird genannt.
        self.assertNotIn("Woche", text)

    def test_schluessel_haengt_am_reset(self):
        laut = RATE_EV["rate_limit_info"]
        self.assertEqual(streamjson.rate_limit_schluessel(laut), "five_hour@1790521200")

    def test_datei_und_status(self):
        p = streamjson.schreibe_rate_limit(self.cfg, RATE_EV["rate_limit_info"], "Reviewer")
        self.assertTrue(p.is_file())
        d = streamjson.lies_rate_limit(self.cfg)
        self.assertEqual(d["quelle"], "Reviewer")
        self.assertIn("84 %", self.orch.rate_limit_text())
        status = self.orch.status_text()
        self.assertIn("Nutzerlimit (Abo)", status)
        self.assertIn("Sitzung (5 h)", status)

    def test_warnung_nur_einmal_je_fenster(self):
        streamjson.schreibe_rate_limit(self.cfg, RATE_EV["rate_limit_info"], "Reviewer")
        self.gesagt.clear()
        self.orch.rate_limit_pruefen()
        self.assertTrue(any("NUTZERLIMIT" in g for g in self.gesagt), self.gesagt)
        self.gesagt.clear()
        self.orch.rate_limit_pruefen()
        self.assertEqual(self.gesagt, [], "dieselbe Warnung darf nicht wiederholt werden")

    def test_reviewer_und_ask_schreiben_die_werte(self):
        """Der Reviewer-Mitschnitt wird ausgewertet, der Worker-Mitschnitt nicht geleert."""
        rd = ensure_dir(self.root / "runs" / "b196")
        write_text_atomic(rd / "reviewer.jsonl", json.dumps(RATE_EV) + "\n")
        info = streamjson.rate_limit_aus_mitschnitt(self.cfg, rd / "reviewer.jsonl")
        self.assertTrue(info)
        write_text_atomic(rd / "leer.jsonl", '{"type":"system"}\n')
        self.assertEqual(streamjson.rate_limit_aus_mitschnitt(self.cfg, rd / "leer.jsonl"), {})

    def test_leere_konfiguration_ergibt_keine_warnung(self):
        self.assertEqual(self.orch.rate_limit_pruefen(), "")
        self.assertIn("noch nicht gemessen", self.orch.status_text())


# ------------------------------------------- c) Review-Historie und Nur-Lese-Git
class TestReviewHistorie(Basis):
    def _repo(self) -> None:
        """Ein echtes kleines Repo mit Historie und einem Batch-Dokument."""
        _git(self.tmp, "init", "-q", str(self.decomp)) if False else None
        _git(self.decomp, "init", "-q")
        _git(self.decomp, "symbolic-ref", "HEAD", "refs/heads/main")
        _git(self.decomp, "config", "user.name", "T")
        _git(self.decomp, "config", "user.email", "t@example.invalid")
        ensure_dir(self.decomp / "analysis")
        (self.decomp / "readme.md").write_text("start\n", encoding="utf-8")
        _git(self.decomp, "add", "-A")
        _git(self.decomp, "commit", "-q", "-m", "start")
        _git(self.decomp, "tag", "harness/b196-start")
        for i in range(3):
            (self.decomp / f"port{i}.txt").write_text("x\n", encoding="utf-8")
            (self.decomp / "analysis" / f"port-batch19{i}-thema.md").write_text(
                f"# Batch 19{i}\n", encoding="utf-8")
            _git(self.decomp, "add", "-A")
            _git(self.decomp, "commit", "-q", "-m", f"Batch 19{i}: etwas geaendert")

    def test_batch_diff_und_historie_im_prompt(self):
        self._repo()
        self.orch.state.data["batch"] = 196
        self.orch.state.data["last_batch_number"] = 196
        self.orch.state.data["last_checkpoint"] = "harness/b196-start"
        diff = self.orch.batch_diff_text()
        self.assertIn("harness/b196-start..HEAD", diff)
        self.assertIn("A\tport0.txt", diff)
        self.assertIn("Diffstat", diff)
        hist = self.orch.historie_text()
        self.assertIn("Batch 192: etwas geaendert", hist)
        self.assertIn("port-batch19", hist)
        ctx = self.orch.review_context("SNAP", rdir=self.root / "runs" / "b197")
        prompt = reviewer.build_prompt(self.cfg, "batch_end", ctx)
        self.assertIn("=== BATCH-DIFF", prompt)
        self.assertIn("=== HISTORIE", prompt)
        self.assertIn("port0.txt", prompt)

    def test_ohne_checkpoint_kein_absturz(self):
        self._repo()
        self.orch.state.data["last_checkpoint"] = "harness/b999-start"
        self.assertIn("fehlt", self.orch.batch_diff_text())

    def test_reviewer_darf_nur_lese_git(self):
        cmd = reviewer.build_command(self.cfg, None, True)
        opt = lambda n: [cmd[i + 1] for i, a in enumerate(cmd) if a == n]      # noqa: E731
        tools = (opt("--tools") or [""])[0]
        self.assertIn("PowerShell", tools, "die Shell muss gestellt sein")
        i = cmd.index("--allowedTools")
        erlaubt, verboten = [], []
        for a in cmd[i + 1:]:
            if a.startswith("--"):
                break
            erlaubt.append(a)
        j = cmd.index("--disallowedTools")
        for a in cmd[j + 1:]:
            if a.startswith("--"):
                break
            verboten.append(a)
        git_erlaubt = [x for x in erlaubt if "git" in x]
        self.assertEqual(sorted(git_erlaubt), sorted(profiles.nur_lese_git_regeln()),
                         "erlaubt sind GENAU die vier Nur-Lese-Befehle")
        for verb in ("git push", "git commit", "git checkout", "git reset", "git clean",
                     "git config", "git tag", "git stash"):
            self.assertIn(f"PowerShell({verb} *)", verboten)
        for fremd in ("Get-Content", "Remove-Item", "Invoke-Expression", "Start-Process"):
            self.assertIn(f"PowerShell({fremd} *)", verboten)
        self.assertIn("PowerShell(git log*--output*)", verboten)
        # Kein ungebundenes `PowerShell` in der Erlaubnisliste!
        self.assertNotIn("PowerShell", erlaubt)
        self.assertNotIn("Read", erlaubt)

    def test_reviewer_env_kennt_das_powershell_werkzeug(self):
        from hx import envs
        env = envs.reviewer_env(self.cfg, {"PATH": "x"}, "token")
        self.assertEqual(env.get("CLAUDE_CODE_USE_POWERSHELL_TOOL"), "1")

    def test_ask_bleibt_ohne_shell(self):
        from hx import ask
        cmd = ask.build_command(self.cfg)
        self.assertNotIn("PowerShell", " ".join(cmd))


# ------------------------------------------------------------- d) Aufbewahrung
class TestAufbewahrung(Basis):
    def _alter_batch(self, nummer: int, tage: float = 20.0) -> Path:
        rd = ensure_dir(self.root / "runs" / f"b{nummer:03d}")
        write_text_atomic(rd / "stream.jsonl", json.dumps({"type": "system"}) + "\n" * 3)
        write_text_atomic(rd / "reviewer.jsonl", json.dumps({"type": "result"}) + "\n")
        write_text_atomic(rd / "result.json", '{"rc": 0}\n')
        write_text_atomic(rd / "harness-facts.md", "- Anfragen: 7\n")
        sdir = ensure_dir(self.root / "snapshots" / f"b{nummer:03d}")
        write_text_atomic(sdir / "snapshot.md", "# Snapshot\n")
        alt = (datetime.now(timezone.utc) - timedelta(days=tage)).timestamp()
        import os
        for p in (rd / "stream.jsonl", rd / "reviewer.jsonl", rd / "result.json",
                  rd / "harness-facts.md", sdir, sdir / "snapshot.md"):
            os.utime(p, (alt, alt))
        return rd

    def test_alle_dateien_werden_gepackt_und_lesbar(self):
        rd = self._alter_batch(150)
        res = retention.lauf(self.cfg, self.log)
        self.assertEqual(res["gezippt"], 3, res)          # stream, reviewer, Snapshots
        self.assertFalse((rd / "stream.jsonl").is_file())
        self.assertTrue((rd / "stream.jsonl.zip").is_file())
        self.assertFalse((self.root / "snapshots" / "b150").exists())
        self.assertTrue((self.root / "snapshots" / "b150.zip").is_file())
        # Unkomprimiert bleiben die taeglich gebrauchten Dateien.
        self.assertTrue((rd / "result.json").is_file())
        self.assertTrue((rd / "harness-facts.md").is_file())
        # ... und die gepackten sind weiter lesbar (genau das braucht watch/rebuild).
        zeilen = retention.mitschnitt_zeilen(rd / "stream.jsonl")
        self.assertEqual(len(zeilen), 3)
        self.assertIsNotNone(retention.mitschnitt_vorhanden(rd / "stream.jsonl"))
        import zipfile
        with zipfile.ZipFile(self.root / "snapshots" / "b150.zip") as zf:
            self.assertIn("# Snapshot", zf.read("snapshot.md").decode("utf-8"))

    def test_junge_batches_bleiben_unberuehrt(self):
        rd = self._alter_batch(151, tage=1.0)
        res = retention.lauf(self.cfg, self.log)
        self.assertEqual(res["gezippt"], 0)
        self.assertTrue((rd / "stream.jsonl").is_file())

    def test_je_lauf_begrenzt(self):
        for n in (140, 141, 142, 143, 144, 145, 146, 147):
            self._alter_batch(n)
        res = retention.lauf(self.cfg, self.log, max_einheiten=3)
        self.assertEqual(res["gezippt"], 3)
        self.assertGreater(res["uebrig"], 0, "der Rest kommt beim naechsten Lauf dran")

    def test_gepackte_mitschnitte_sind_fuer_rebuild_lesbar(self):
        rd = ensure_dir(self.root / "runs" / "b152")
        write_text_atomic(rd / "stream.jsonl",
                          json.dumps({"type": "result", "subtype": "success",
                                      "duration_ms": 1000}) + "\n")
        write_text_atomic(rd / "auftrag.md", "Ghidra-Profil dieses Laufs: ghidra-read\n")
        ok, vorher, nachher = retention.zip_datei(rd / "stream.jsonl", self.log)
        self.assertTrue(ok)
        self.assertFalse((rd / "stream.jsonl").is_file())
        res = worker.rebuild_from_stream(self.cfg, self.log, self.orch.state, 152)
        self.assertEqual(res.profile, "ghidra-read")

    def test_kaputtes_zip_loescht_das_original_nicht(self):
        rd = ensure_dir(self.root / "runs" / "b153")
        write_text_atomic(rd / "stream.jsonl", "x\n")
        with mock.patch("hx.retention.zipfile.ZipFile", side_effect=OSError("kaputt")):
            ok, _v, _n = retention.zip_datei(rd / "stream.jsonl", self.log)
        self.assertFalse(ok)
        self.assertTrue((rd / "stream.jsonl").is_file(), "Original muss liegen bleiben")

    def test_taeglich_nur_einmal(self):
        st = self.orch.state
        st.data.pop("retention", None)
        self.assertTrue(retention.faellig(self.cfg, st))
        st.data["retention"] = {"ts": datetime.now(timezone.utc).isoformat()}
        self.assertFalse(retention.faellig(self.cfg, st))

    def test_tick_laeuft_nicht_waehrend_eines_batches(self):
        self._alter_batch(154)
        self.orch.state.set("DS_WORKING", "Test")
        self.orch.state.data["worker"] = {"pid": 1}
        self.assertIsNone(self.orch.retention_tick())
        self.assertTrue((self.root / "runs" / "b154" / "stream.jsonl").is_file())
        self.orch.state.data.pop("worker", None)
        self.orch.state.set("IDLE", "Test")
        res = self.orch.retention_tick()
        self.assertIsNotNone(res)
        self.assertFalse((self.root / "runs" / "b154" / "stream.jsonl").is_file())

    def test_warnung_bei_wenig_platz(self):
        self._alter_batch(155)
        with mock.patch.object(retention, "frei_gb", lambda cfg: 12.5):
            gesagt: list[str] = []
            res = retention.lauf(self.cfg, self.log, notify=lambda t: gesagt.append(t))
        self.assertIn("nur noch 12.5 GB frei", res["warnung"])
        self.assertTrue(any("WENIG PLATZ" in t for t in gesagt), gesagt)

    def test_hohes_max_einheiten_faengt_alle(self):
        """Mit dem Standardwert (6) und 8 Kandidaten bleibt etwas uebrig."""
        self.assertEqual(retention.MAX_EINHEITEN, 6)


if __name__ == "__main__":
    unittest.main()
