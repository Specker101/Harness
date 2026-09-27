"""Tests fuer R13n: Remote-Stand automatisch uebernehmen und als Nutzerarbeit fuehren.

Auftrag (2026-09-27): ist der Arbeitsbaum sauber und `origin/main` **nur voraus**
(lokaler HEAD ist Vorfahre), soll der Harness `git pull --ff-only` fahren, per Telegram
"Stand vom Remote uebernommen: <Commits>" melden und die Commits im naechsten Review als
**Nutzerarbeit** kennzeichnen. Bei echter Abweichung oder unsauberem Baum bleibt es beim
Anhalten.

Gemessen wird an echten Repos: ein Bare-Repo als "origin", ein zweiter Klon als "anderer
Rechner". Keine API, keine Kosten, kein Ghidra.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import worker                                              # noqa: E402
from hx.config import load_config                                  # noqa: E402
from hx.orchestrator import Orchestrator                           # noqa: E402
from hx.util import Log, ensure_dir                                # noqa: E402


def _weg(pfad: Path) -> None:
    """Ordner loeschen - auch wenn git schreibgeschuetzte Objekte hinterlassen hat.

    `git` legt seine Objektdateien NUR-LESEND an; `shutil.rmtree` scheitert dann mit
    WinError 5 und laesst den Ordner stehen. Steht er noch, scheitert der naechste
    Testlauf (beim `git clone` in denselben Pfad) - genau das ist hier passiert.
    """
    def zwingend(func, path):
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except OSError:
            pass

    if sys.version_info >= (3, 12):
        shutil.rmtree(pfad, onexc=lambda f, p, _e: zwingend(f, p))
    else:                                                          # pragma: no cover
        shutil.rmtree(pfad, onerror=lambda f, p, _e: zwingend(f, p))


def _git(cwd, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} -> rc={r.returncode}: {r.stderr.strip()[:300]}")
    return (r.stdout or "").strip()


def _neu_repo(pfad: Path) -> Path:
    """`git init` mit Zweig `main` - unabhaengig von der git-Version (kein `-b`)."""
    p = ensure_dir(pfad)
    _git(p, "init", "-q")
    _git(p, "symbolic-ref", "HEAD", "refs/heads/main")
    return p


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__file__).resolve().parent / "_tmp_r13n"
        _weg(self.tmp)
        ensure_dir(self.tmp)

        # "origin" als Bare-Repo.
        self.remote = ensure_dir(self.tmp / "remote.git")
        _git(self.tmp, "init", "--bare", "-q", str(self.remote))
        _git(self.remote, "symbolic-ref", "HEAD", "refs/heads/main")

        # Das Decomp-Repo, auf dem der Harness arbeitet.
        self.repo = _neu_repo(self.tmp / "decomp")
        _git(self.repo, "config", "user.name", "T")
        _git(self.repo, "config", "user.email", "t@example.invalid")
        (self.repo / "readme.md").write_text("start\n", encoding="utf-8")
        (self.repo / "analysis").mkdir()
        (self.repo / "analysis" / "r1b-workstream.md").write_text(
            "# Workstream R1B\n**Stand:** BATCH 180\n**Naechster Schritt:** B181\n",
            encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "start")
        _git(self.repo, "remote", "add", "origin", str(self.remote))
        _git(self.repo, "push", "-q", "-u", "origin", "main")

        # Der "andere Rechner": eigener Klon desselben Remote.
        self.anderer = self.tmp / "anderer"
        _git(self.tmp, "clone", "-q", str(self.remote), str(self.anderer))
        _git(self.anderer, "config", "user.name", "T2")
        _git(self.anderer, "config", "user.email", "t2@example.invalid")

        cfg = load_config()
        cfg.data["paths"]["root"] = str(ensure_dir(self.tmp / "harness"))
        cfg.data["paths"]["decomp"] = str(self.repo)
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["telegram"]["allowlist_user_ids"] = []
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)
        self.orch = Orchestrator(cfg, self.log, mock=True,
                                 state_file=self.tmp / "harness" / "state" / "run.json")
        self.orch.state.data["batch"] = 180
        self.orch.state.data["last_batch_number"] = 180
        self.orch.state.save()
        self.gesagt: list[str] = []
        self.orch.say = lambda t, *a, **k: self.gesagt.append(str(t))

    def tearDown(self):
        _weg(self.tmp)

    # -------------------------------------------------------------- Helfer
    def _auf_dem_anderen_rechner(self, datei: str, inhalt: str, titel: str) -> str:
        """Commit + Push im zweiten Klon; gibt den kurzen Hash zurueck."""
        (self.anderer / datei).write_text(inhalt, encoding="utf-8")
        _git(self.anderer, "add", "-A")
        _git(self.anderer, "commit", "-q", "-m", titel)
        _git(self.anderer, "push", "-q", "origin", "main")
        return _git(self.anderer, "rev-parse", "--short", "HEAD")

    def _lokal_committen(self, datei: str, inhalt: str, titel: str) -> str:
        (self.repo / datei).write_text(inhalt, encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", titel)
        return _git(self.repo, "rev-parse", "--short", "HEAD")

    def _text(self) -> str:
        return "\n".join(self.gesagt)

    def _sync(self, anlass: str = "Test") -> tuple[bool, str]:
        """`git_sync` liefert (ok, Meldung, Art) - hier auf zwei Werte verkuerzt."""
        ok, meldung, art = self.orch.git_sync(anlass)
        self.art = art
        return ok, meldung


class TestNurRemoteVoraus(Base):
    def test_stand_wird_uebernommen(self):
        self._auf_dem_anderen_rechner("neu.txt", "vom anderen Rechner\n", "B172: Vorhersage")
        ok, meldung = self._sync()

        self.assertTrue(ok, f"Pull haette laufen muessen: {meldung}")
        self.assertEqual(self.art, "geholt")
        self.assertTrue((self.repo / "neu.txt").is_file(), "Datei fehlt nach dem Vorlauf")
        self.assertIn("Stand vom Remote uebernommen: 1 Commit(s)", self._text())
        self.assertIn("B172: Vorhersage", self._text())
        rw = self.orch.state.data.get("remote_work") or {}
        self.assertEqual(len(rw.get("hashes") or []), 1)
        self.assertEqual(rw.get("anlass"), "Test")

    def test_zweiter_lauf_ist_ruhig(self):
        """Ohne neue Remote-Commits passiert nichts und es wird nichts gemeldet."""
        self._auf_dem_anderen_rechner("neu.txt", "x\n", "B172: etwas")
        self.orch.git_sync("Test")
        self.gesagt.clear()
        ok, meldung = self._sync()
        self.assertTrue(ok)
        self.assertEqual(meldung, "")
        self.assertNotIn("uebernommen", self._text())

    def test_uebernommener_commit_mit_harness_titel_ist_nutzerarbeit(self):
        """Die Herkunft entscheidet, nicht der Betreff (R13n)."""
        kurz = self._auf_dem_anderen_rechner("neu.txt", "x\n", "B172: Vorhersage")
        self.orch.git_sync("Test")
        rw = self.orch.state.data["remote_work"]
        # Format von `git log --pretty=%h %ad %s` (so liest es die Pausen-Erkennung).
        zeile = f"{kurz} 2026-09-27 B172: Vorhersage"
        self.assertIn(kurz, rw["hashes"])
        self.assertFalse(self.orch._ist_harness_commit(zeile),
                         "ein per Pull gekommener Commit ist Nutzerarbeit")
        # Gegenprobe: ein echter Worker-Commit desselben Titelmusters bleibt Harness.
        self.assertTrue(self.orch._ist_harness_commit("abc1234 2026-09-26 B172: Vorhersage"))

    def test_review_hinweis_nennt_die_nutzerarbeit(self):
        kurz = self._auf_dem_anderen_rechner("neu.txt", "x\n", "B172: Vorhersage")
        self.orch.git_sync("Test")
        note = self.orch.pause_work_note()
        self.assertIn("VOM REMOTE UEBERNOMMEN", note)
        self.assertIn("NUTZERARBEIT", note)
        self.assertIn(kurz, note)
        self.assertIn("Diffstat", note)

    def test_worker_vorspann_kennt_r367(self):
        self._auf_dem_anderen_rechner("neu.txt", "x\n", "B172: Vorhersage")
        self.orch.git_sync("Test")
        hinweis = self.orch.remote_work_hinweis()
        self.assertIn("REMOTE-STAND UEBERNOMMEN", hinweis)
        self.assertIn("R367", hinweis)
        self.assertIn("port_build.ps1", hinweis)
        self.assertIn("port_regression.py", hinweis)
        self.assertIn("NEUBAU", hinweis)
        # Und der Vorspann des Workers traegt ihn wirklich.
        prompt = worker.build_prompt(self.cfg, "Batch 181 - Test", "", None, "none",
                                     remote_hinweis=hinweis)
        self.assertIn("REMOTE-STAND UEBERNOMMEN", prompt)
        self.assertLess(prompt.index("REMOTE-STAND UEBERNOMMEN"),
                        prompt.index("=== AUFTRAG (vom Reviewer) ==="),
                        "der Hinweis gehoert VOR den Auftrag")

    def test_ohne_pull_kein_hinweis(self):
        self.assertEqual(self.orch.remote_work_hinweis(), "")
        self.assertEqual(self.orch.pause_work_note(), "")
        self.assertIn("nichts uebernommen", self.orch.remote_work_zeile())

    def test_messdatenblock_hat_die_zeile(self):
        self._auf_dem_anderen_rechner("neu.txt", "x\n", "B172: Vorhersage")
        self.orch.git_sync("Test")
        facts = self.orch.harness_facts(180)
        self.assertIn("Remote-Stand (R13n)", facts)
        self.assertIn("NUTZERARBEIT", facts)
        self.assertIn("R367", facts)


class TestAnhalten(Base):
    def test_eigener_stand_voraus_haelt_an(self):
        self._lokal_committen("lokal.txt", "x\n", "eigene Arbeit")
        ok, meldung = self._sync()
        self.assertFalse(ok)
        self.assertIn("weicht ab", meldung)
        self.assertEqual(self.art, "abweichung")
        self.assertNotIn("remote_work", self.orch.state.data)

    def test_divergenz_haelt_an(self):
        self._auf_dem_anderen_rechner("fremd.txt", "x\n", "B172: fremd")
        self._lokal_committen("lokal.txt", "x\n", "eigene Arbeit")
        ok, meldung = self._sync()
        self.assertFalse(ok)
        self.assertIn("DIVERGIERT", meldung)
        self.assertEqual(self.art, "abweichung")
        self.assertFalse((self.repo / "fremd.txt").exists(),
                         "bei Divergenz darf nichts uebernommen werden")
        self.assertNotIn("remote_work", self.orch.state.data)

    def test_unsauberer_baum_haelt_an(self):
        self._auf_dem_anderen_rechner("fremd.txt", "x\n", "B172: fremd")
        (self.repo / "readme.md").write_text("angefangen\n", encoding="utf-8")
        ok, meldung = self._sync()
        self.assertFalse(ok)
        self.assertIn("nicht sauber", meldung)
        self.assertEqual(self.art, "unsauber")
        self.assertFalse((self.repo / "fremd.txt").exists())
        self.assertNotIn("remote_work", self.orch.state.data)

    def test_fortsetzen_haelt_bei_abweichung_an(self):
        """/resume darf bei echter Abweichung NICHT einfach weiterlaufen (R13n)."""
        self._lokal_committen("lokal.txt", "x\n", "eigene Arbeit")
        self.orch.state.set("PAUSED", "Test")
        self.orch.state.data["paused"] = True
        self.orch._do_resume()
        self.assertTrue(self.orch.state.data.get("paused"))
        self.assertIn("PAUSE:", self._text())
        self.assertNotEqual(self.orch.state.state, "IDLE")
    def test_fortsetzen_holt_den_stand(self):
        self._auf_dem_anderen_rechner("neu.txt", "x\n", "B172: fremd")
        self.orch.state.set("PAUSED", "Test")
        self.orch.state.data["paused"] = True
        self.orch._do_resume()
        self.assertTrue((self.repo / "neu.txt").is_file())
        self.assertFalse(self.orch.state.data.get("paused"))
        self.assertEqual(self.orch.state.state, "IDLE")

    def test_fortsetzen_bei_unpruefbarem_git(self):
        """Kein Repo/kein Netz ist KEIN Haltegrund fuer /resume - nur echte Abweichung.

        Sonst waere ein `resume` in einer Umgebung ohne erreichbares git unmoeglich;
        die Vorpruefung vor dem naechsten Batch entscheidet spaeter endgueltig.
        """
        self.cfg.data["paths"]["decomp"] = str(ensure_dir(self.tmp / "keinrepo"))
        orch = Orchestrator(self.cfg, self.log, mock=True,
                            state_file=self.tmp / "harness" / "state" / "run.json")
        gesagt: list[str] = []
        orch.say = lambda t, *a, **k: gesagt.append(str(t))
        orch.state.set("PAUSED", "Test")
        orch.state.data["paused"] = True
        orch._do_resume()
        self.assertFalse(orch.state.data.get("paused"), "resume wurde unnoetig gesperrt")
        self.assertEqual(orch.state.state, "IDLE")
        self.assertTrue(any("nicht pruefbar" in g for g in gesagt), gesagt)


if __name__ == "__main__":
    unittest.main()
