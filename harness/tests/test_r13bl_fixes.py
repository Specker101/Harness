"""R13bl (02.10.2026): Harness-Wartung - Punkt 1 von vier, je Punkt ein Commit.

  1. **Pflichtzeile `B-SCHRITT:`** - die B-Batch-Nummer ist eine **Zaehlung**; die Grenze
     von 20 B-Batches ist seit dem 30.09.2026 aufgehoben (Nutzerentscheid). Die alte
     Formulierung "von max 20" ist aus `prompts/reviewer.md` und aus dem Hinweis, den der
     Harness in den Review-Prompt schreibt, verschwunden.
  2. **Rueckbau der vorlaeufigen Zeitgrenzen** aus R13bj: `bash_max_timeout_s` 3600 -> 1800,
     `hard_wall_s` 14400 -> 10800, `timeout=3600000` -> `timeout=1800000` in Worker-Vorspann
     und `prompts/reviewer.md`, Handbuch §13 nachgezogen. Bedingung war "Preflight wieder
     unter 900 s" - der Preflight von B236 brauchte **456 s**.
  3. **R391-Sperre im PreToolUse-Hook** (`tools/batch_uhr.py`): solange im laufenden Batch
     kein Commit mit dem Betreff `B<N>: Vorhersage …` existiert, blockiert der Hook
     `Edit`/`Write`/`MultiEdit` auf `port/` und `scripts/`; `analysis/` bleibt frei.

Die weiteren Punkte dieser Runde kommen in den folgenden Commits in dieselbe Datei.

Alles laeuft in Wegwerf-Verzeichnissen; der echte Zustand, das Decomp-Repo und der
laufende Harness bleiben unberuehrt (kein Neustart).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DOCS = ROOT.parent / "docs"
TOOLS = ROOT / "tools"

from hx import envs, reviewer, stand, worker                        # noqa: E402
from hx.config import load_config                               # noqa: E402
from hx.orchestrator import Orchestrator                        # noqa: E402
from hx.util import Log, ensure_dir, write_text_atomic          # noqa: E402


class Basis(unittest.TestCase):
    """Wegwerf-Repo: `cfg` zeigt auf ein Temp-Verzeichnis, nie auf den echten Stand."""

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13bl"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "harness")
        self.decomp = ensure_dir(self.tmp / "decomp")
        self.ana = ensure_dir(self.decomp / "analysis")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.decomp)
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["paths"]["harness_home"] = str(self.tmp)
        cfg.data["telegram"]["allowlist_user_ids"] = []
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def auftrag(self, batch: int, text: str) -> None:
        d = ensure_dir(self.root / "runs" / f"b{batch:03d}")
        write_text_atomic(d / "auftrag.md", text)

    def orch(self, batch: int = 209) -> Orchestrator:
        o = Orchestrator(self.cfg, self.log, mock=True,
                         state_file=self.root / "state" / "run.json")
        o.qroot = self.root
        o.said = []
        o.say = lambda t="", *a, **k: o.said.append(str(t))
        o.state.data["batch"] = int(batch)
        o.state.save()
        return o


# ============================================ 1) Pflichtzeile als Zaehlung
class TestPflichtzeileZaehlung(Basis):
    """Punkt 1: "B-Batch <k> von max 20" -> "B-Batch <k> (Zaehlung, keine Grenze ...)"."""

    ALT = "von max 20"

    def test_vorlage_hat_die_alte_formulierung_nicht_mehr(self):
        text = (ROOT / "prompts" / "reviewer.md").read_text(encoding="utf-8")
        self.assertNotIn(self.ALT, text)
        self.assertIn("Zählung, keine Grenze", text)

    def test_hinweis_nennt_die_zaehlung(self):
        self.auftrag(208, "B208 ist der ERSTE Batch von Strang B.")
        h = stand.pflichtzeile_hinweis(self.cfg, 208)
        self.assertIn("B208 ist ein B-Batch", h)
        self.assertNotIn(self.ALT, h)
        self.assertIn("keine Grenze", h)

    def test_erzeugter_reviewer_prompt_hat_die_alte_formulierung_nicht(self):
        """Der Prompt wird wirklich gebaut (nicht nur die Vorlage gelesen)."""
        self.auftrag(208, "B208 ist der ERSTE Batch von Strang B.")
        ctx = self.orch(208).review_context("(Snapshot)")
        self.assertIn("keine Grenze", ctx["protokoll_warnung"])
        prompt = reviewer.build_prompt(self.cfg, "batch_end", ctx)
        self.assertIn("=== PROTOKOLL-WARNUNG (Pflichtzeilen im Review) ===", prompt)
        self.assertNotIn(self.ALT, prompt)
        self.assertIn("keine Grenze", prompt)

    def test_der_parser_haengt_nicht_am_wortlaut(self):
        """`_RE_B_SCHRITT` liest nur `n/5` - die alte wie die neue Schreibweise zaehlen."""
        self.assertTrue(stand._RE_B_SCHRITT.search("B-SCHRITT: 2/5 Maschine, B-Batch 2 von max 20"))
        self.assertTrue(stand._RE_B_SCHRITT.search(
            "B-SCHRITT: 2/5 Maschine, B-Batch 2 (Zählung, keine Grenze – Nutzerentscheid 30.09.)"))


# ==================================== 2) Rueckbau der vorlaeufigen Zeitgrenzen
class TestZeitgrenzenRueckbau(unittest.TestCase):
    """Punkt 2: R13bj hatte vorlaeufig erhoeht - R13bl baut auf den alten Stand zurueck."""

    def test_config_ist_zurueckgebaut(self):
        cfg = load_config()
        self.assertEqual(float(cfg.get("claude", "bash_max_timeout_s")), 1800.0)
        self.assertEqual(float(cfg.get("limits", "hard_wall_s")), 10800.0)
        # Alarm und Umschaltschwelle waren nie Teil der Erhoehung.
        self.assertEqual(float(cfg.get("limits", "alarm_wall_s")), 9000.0)
        self.assertEqual(float(cfg.get("limits", "umschalt_vor_alarm_s")), 900.0)

    def test_env_obergrenze_ist_wieder_eine_halbe_stunde(self):
        env = envs.worker_env(load_config(), dict(os.environ), "token")
        self.assertEqual(env["BASH_MAX_TIMEOUT_MS"], "1800000")
        self.assertEqual(env["BASH_DEFAULT_TIMEOUT_MS"], "600000",
                         "die Vorgabe ohne eigenes timeout bleibt der Schutz bei 600 s")

    def test_die_drei_quellen_nennen_dieselbe_zahl(self):
        """EINE Zahl an drei Stellen (Config, Worker-Vorspann, Vorlage) - R13ah-Lehre."""
        pre = worker.WORKER_PREAMBLE
        self.assertIn("timeout=1800000", pre)
        self.assertIn("bis 1800000 = 30 min", pre)
        self.assertNotIn("3600000", pre)
        text = (ROOT / "prompts" / "reviewer.md").read_text(encoding="utf-8")
        self.assertIn("timeout=1800000", text)
        # Die VORSCHRIFT-Form muss weg; die historische Nennung in der R13bl-Notiz
        # ("R13bj hatte vorlaeufig auf 3600000 erhoeht") bleibt ausdruecklich stehen -
        # sonst waere die Aenderung nach einem halben Jahr nicht mehr nachvollziehbar.
        self.assertNotIn("timeout=3600000", text)
        self.assertIn("vorläufig** auf 3600000", text)
        cfg = load_config()
        self.assertEqual(int(float(cfg.get("claude", "bash_max_timeout_s"))) * 1000, 1800000)

    def test_handbuch_haelt_den_rueckbau_fest(self):
        """§13 nennt die neuen Werte und die erfuellte Bedingung - und nicht mehr die alte Tafel."""
        text = (DOCS / "bedienung.md").read_text(encoding="utf-8")
        self.assertNotIn("Vorlaeufige Zeitgrenzen", text)
        i = text.index("**5. Zeitgrenzen (R13bl")
        abschnitt = text[i:i + 1200]
        for wert in ("1800 s", "10800 s", "timeout=1800000", "456 s"):
            self.assertIn(wert, abschnitt, f"{wert} fehlt in Paragraph 13")
        # Die alte Rueckbau-Tafel aus R13bj ist ersetzt (Spalte "Rueckbau").
        self.assertNotIn("| Rueckbau |", abschnitt)


# ============================================ 3) R391-Sperre im Hook
class TestR391Sperre(Basis):
    """Punkt 3: der PreToolUse-Hook blockiert Schreibzugriffe auf port//scripts/.

    Gefahren wird der ECHTE Hook als Unterprozess (so ruft die CLI ihn auf), gegen ein
    Wegwerf-Git-Repo - nicht gegen das Decomp-Repo.
    """

    def _git(self, repo: Path, *args: str) -> None:
        p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                           stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                           errors="replace", timeout=120)
        self.assertEqual(p.returncode, 0, f"git {args} -> {p.stderr[:200]}")

    def repo(self, vorhersage: str | None = None) -> Path:
        """Wegwerf-Repo; `vorhersage` legt einen Commit mit diesem Betreff an."""
        r = ensure_dir(self.tmp / "repo")
        self._git(r, "init", "-q")
        self._git(r, "config", "user.email", "t@example.invalid")
        self._git(r, "config", "user.name", "Test")
        self._git(r, "commit", "-q", "--allow-empty", "-m", "Start")
        if vorhersage:
            self._git(r, "commit", "-q", "--allow-empty", "-m", vorhersage)
        return r

    def hook(self, repo: Path, werkzeug: str, pfad: Path, batch: int = 237) -> tuple[str, str]:
        """Hook aufrufen -> (permissionDecision, Begruendung); '' = nicht blockiert."""
        lauf = ensure_dir(self.tmp / "runs" / f"b{batch}")
        state = lauf / "state.json"
        write_text_atomic(state, json.dumps({"batch": batch}))
        eingabe = {"tool_name": werkzeug, "tool_input": {"file_path": str(pfad)}}
        p = subprocess.run([sys.executable, str(TOOLS / "batch_uhr.py"),
                            "--state", str(state), "--pre", "--run", str(lauf),
                            "--decomp", str(repo)],
                           input=json.dumps(eingabe).encode("utf-8"),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        self.assertEqual(p.returncode, 0, p.stderr.decode("utf-8", "replace")[:300])
        roh = p.stdout.decode("utf-8").strip()
        if not roh:
            return "", ""
        d = json.loads(roh).get("hookSpecificOutput") or {}
        if d.get("permissionDecision") == "allow":
            return "", ""
        return str(d.get("permissionDecision") or ""), str(
            d.get("permissionDecisionReason") or "")

    def test_edit_auf_port_vor_dem_vorhersage_commit_wird_blockiert(self):
        repo = self.repo()
        d, grund = self.hook(repo, "Edit", repo / "port" / "src" / "x.cpp")
        self.assertEqual(d, "deny")
        self.assertIn("Vorhersage", grund)
        self.assertIn("B237", grund)

    def test_nach_dem_vorhersage_commit_ist_es_erlaubt(self):
        repo = self.repo("B237: Vorhersage - Soll je Bilanzzeile")
        d, _ = self.hook(repo, "Edit", repo / "port" / "src" / "x.cpp")
        self.assertEqual(d, "", "nach dem Vorhersage-Commit laeuft der Aufruf durch")

    def test_edit_auf_analysis_ist_vorher_erlaubt(self):
        repo = self.repo()
        d, _ = self.hook(repo, "Edit", repo / "analysis" / "port-batch.md")
        self.assertEqual(d, "", "analysis/ bleibt frei - dort wird die Vorhersage begruendet")

    def test_nachtrag_betreff_zaehlt_als_vorhanden(self):
        repo = self.repo("B237: Vorhersage-Nachtrag (Wiederholung)")
        d, _ = self.hook(repo, "Edit", repo / "port" / "x.cpp")
        self.assertEqual(d, "")

    def test_fortsetzung_betreff_zaehlt_als_vorhanden(self):
        repo = self.repo("B237: Vorhersage Fortsetzung")
        d, _ = self.hook(repo, "Edit", repo / "port" / "x.cpp")
        self.assertEqual(d, "")

    def test_fremde_batchnummer_zaehlt_nicht(self):
        repo = self.repo("B236: Vorhersage")
        d, _ = self.hook(repo, "Edit", repo / "port" / "x.cpp")
        self.assertEqual(d, "deny", "der Vorhersage-Commit muss zur LAUFENDEN Nummer gehoeren")

    def test_scripts_wird_ebenfalls_gesperrt(self):
        repo = self.repo()
        d, grund = self.hook(repo, "Write", repo / "scripts" / "m149_bilanz.py")
        self.assertEqual(d, "deny")
        self.assertIn("scripts", grund)

    def test_multi_edit_wird_auch_geprueft(self):
        repo = self.repo()
        d, _ = self.hook(repo, "MultiEdit", repo / "port" / "x.cpp")
        self.assertEqual(d, "deny")

    def test_bash_schreibt_nicht_durch_die_sperre(self):
        """Bekannte Grenze: Bash-Schreibzugriffe faengt die Sperre NICHT (Waechter)."""
        repo = self.repo()
        d, _ = self.hook(repo, "PowerShell", repo / "port" / "x.cpp")
        self.assertEqual(d, "", "PowerShell hat kein file_path - hier greift der Waechter")

    def test_der_block_wird_belegt(self):
        repo = self.repo()
        self.hook(repo, "Edit", repo / "port" / "x.cpp")
        beleg = self.tmp / "runs" / "b237" / "vorhersage-blockiert.jsonl"
        self.assertTrue(beleg.is_file(), "jeder Block bekommt eine Zeile im Laufverzeichnis")
        zeilen = [json.loads(z) for z in beleg.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(zeilen[0]["batch"], 237)
        self.assertEqual(zeilen[0]["werkzeug"], "Edit")

    def test_ohne_batchnummer_wird_nichts_behauptet(self):
        repo = self.repo()
        d, _ = self.hook(repo, "Edit", repo / "port" / "x.cpp", batch=0)
        self.assertEqual(d, "", "ohne Nummer im Zustand kein Block (kein Raten)")


if __name__ == "__main__":
    unittest.main()
