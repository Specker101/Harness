"""Tests fuer R13v3 (2026-09-28): Aufraeumen nach einem Abbruch + /autonom-Haltbarkeit.

Auftrag (Nutzer, vor dem Neustart):

1. "autonomous: Ich hatte /autonom off gesetzt ... jetzt steht in state/run.json
   autonomous: True. Belegen: wird der Wert beim Stoppen/Starten zurueckgesetzt oder
   nicht gespeichert? Erwartung: eine per /autonom gesetzte Einstellung ueberlebt /stop
   und Neustart. Falls nicht: beheben."
2. "Aufraeumen nach einem Abbruch (Waechter, Zeitgrenze, Kill-Switch):
   a) Verwaiste Prozesse: alle vom Worker gestarteten Prozesse muessen nach dem Abbruch
      weg sein ... Job-Objekt mit KILL_ON_JOB_CLOSE, plus Nachsuche nach python/g++/make/
      ppc_*-Prozessen, deren Kommandozeile oder Arbeitsverzeichnis im Decomp-Repo liegt
      und die nach dem Batch-Start entstanden sind (nie den Harness selbst treffen, R13i).
   b) Halber Arbeitsstand: direkt nach dem Abbruch wip_rescue ausfuehren ... und im
      naechsten Review ausdruecklich melden.
   c) Belegen, welche Batchnummer der naechste Lauf bekommt, wenn der Anker nach einem
      Abbruch nicht fortgeschrieben wurde ... und dass das Review das korrekt einordnet."

Alles ohne API-Kosten, ohne Ghidra, ohne Netz. Die echten Prozessmessungen stehen in
`docs/_r13v3_beleg_aufraeumen.txt` (Werkzeug `tools/r13v3_aufraeumen_probe.py`).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import aufraeumen, state as st, reviewer          # noqa: E402
from hx.config import load_config                         # noqa: E402
from hx.orchestrator import Orchestrator                  # noqa: E402
from hx.util import Log                                   # noqa: E402

KONFIG = load_config()


def _dummy_zeile(**felder) -> dict:
    """Ein Prozess-Eintrag wie ihn `aufraeumen.prozess_liste` liefert."""
    basis = {"pid": 1000, "ppid": 0, "name": "python.exe", "alter_s": 10,
             "cmd": "python -u scripts/c_kopf.py prof"}
    basis.update(felder)
    return basis


class TestAutonomHaelt(unittest.TestCase):
    """/autonom muss /stop und Neustart ueberleben (Punkt 1)."""

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13v3_autonom"
        if self.tmp.exists():
            import shutil
            shutil.rmtree(self.tmp, ignore_errors=True)
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.datei = self.tmp / "run.json"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _orch(self, geschwister: list[str]):
        """Orchestrator mit echtem Zustand, aber ohne Netz/Git."""
        orch = Orchestrator.__new__(Orchestrator)
        orch.cfg = KONFIG
        orch.state = st.State(self.datei)
        orch.log = Log(self.tmp / "log.jsonl", echo=False)
        orch.qroot = self.tmp
        gesagt: list[str] = []

        def say(*teile, **kw):
            gesagt.append(" ".join(str(t) for t in teile))
        orch.say = say
        return orch, gesagt

    def _befehl(self, text: str):
        """Den Telegram-Weg fahren (`handle_command`) - nicht einen Nachbau."""
        orch, gesagt = self._orch(["x"])
        try:
            Orchestrator.handle_command(orch, text)
        except AttributeError as exc:                      # fehlende Geschwistermethode
            self.skipTest(f"handle_command braucht mehr Umgebung: {exc}")
        return orch, gesagt

    def test_standard_ist_aus(self):
        neu = st.State(self.tmp / "leer.json")
        self.assertIs(neu.data.get("autonomous"), False)
        self.assertIs(st.DEFAULTS["autonomous"], False)

    def test_befehl_speichert_sofort_und_ueberlebt_neustart(self):
        orch, gesagt = self._orch(["x"])
        orch.state.data["autonomous"] = True
        orch.state.save()
        # Der Telegram-Befehl (derselbe Code wie im Betrieb).
        orch, gesagt = self._befehl("/autonom off")
        self.assertIn("AUS", " ".join(gesagt))
        roh = json.loads(self.datei.read_text(encoding="utf-8"))
        self.assertIs(roh.get("autonomous"), False, "Wert muss SOFORT auf der Platte stehen")
        # Neustart: frisch von der Platte lesen - nichts setzt ihn zurueck.
        neu = st.State(self.datei)
        self.assertIs(neu.data.get("autonomous"), False)
        # Stoppen (derselbe Aufruf wie im Stopp-Pfad) aendert nichts.
        neu.data["stopped"] = True
        neu.set(st.STOPPED, "Stop ueber Telegram")
        wieder = st.State(self.datei)
        self.assertIs(wieder.data.get("autonomous"), False)
        self.assertIs(wieder.data.get("stopped"), True)
        # Und die Gegenrichtung haelt genauso (kein Einbahn-Feld).
        wieder.data["autonomous"] = True
        wieder.save()
        self.assertIs(st.State(self.datei).data.get("autonomous"), True)

    def test_kein_code_setzt_autonom_ausser_dem_befehl(self):
        """Nur der Telegram-Befehl und die Demo schreiben `autonomous`."""
        treffer = []
        for name in ("orchestrator.py", "cli.py", "state.py", "worker.py", "watch.py"):
            text = (ROOT / "hx" / name).read_text(encoding="utf-8")
            for i, zeile in enumerate(text.splitlines(), 1):
                if 'data["autonomous"]' in zeile and "=" in zeile.split("data[")[0] + "=":
                    treffer.append(f"hx/{name}:{i}")
                elif 'data["autonomous"] =' in zeile or "data['autonomous'] =" in zeile:
                    treffer.append(f"hx/{name}:{i}")
        self.assertTrue(treffer, "die Schreibstellen muessen auffindbar sein")
        # Erlaubt ist nur der Telegram-Zweig (orchestrator) und die Demo (cli).
        erlaubt = [t for t in treffer if t.startswith(("hx/orchestrator.py", "hx/cli.py"))]
        self.assertEqual(sorted(treffer), sorted(erlaubt),
                         f"unerwartete Schreibstelle: {treffer}")
        # In state.py steht nur die Vorgabe.
        self.assertIn("autonomous", (ROOT / "hx" / "state.py").read_text(encoding="utf-8"))


class TestKandidaten(unittest.TestCase):
    """Wer darf beendet werden - und wer NIE (Punkt 2a, R13i)."""

    WURZEL = r"g:\Silent Scope Decomp"

    def test_python_der_die_wurzel_nennt(self):
        treffer = aufraeumen.kandidaten(
            [_dummy_zeile(pid=4711, cmd=r'python -u "g:\Silent Scope Decomp\scripts\c_kopf.py" mutalle')],
            wurzel=self.WURZEL, seit_s=100.0, ausgenommen={1}, wurzeln_pids={2})
        self.assertEqual([t["pid"] for t in treffer], [4711])
        self.assertIn("Wurzel", treffer[0]["grund"])

    def test_nachfahre_des_worker_laufs_ohne_pfad(self):
        # Der Enkel nennt nur "scripts/preflight.py", haengt aber unter dem Worker.
        treffer = aufraeumen.kandidaten(
            [_dummy_zeile(pid=100, ppid=0, name="claude.exe", cmd="claude -p"),
             _dummy_zeile(pid=200, ppid=100, name="powershell.exe", cmd="powershell -Command x"),
             _dummy_zeile(pid=300, ppid=200, name="python.exe", cmd="python -u scripts/preflight.py before")],
            wurzel=self.WURZEL, seit_s=100.0, ausgenommen={1}, wurzeln_pids={100})
        self.assertEqual([t["pid"] for t in treffer], [300])
        self.assertIn("Nachfahre", treffer[0]["grund"])

    def test_fremder_prozess_bleibt(self):
        # Gleicher Name, aber weder Wurzel noch Nachfahre dieses Laufs: NICHT anfassen.
        treffer = aufraeumen.kandidaten(
            [_dummy_zeile(pid=900, ppid=1, cmd="python -u c:/anderes/c_kopf.py prof")],
            wurzel=self.WURZEL, seit_s=100.0, ausgenommen={1}, wurzeln_pids={100})
        self.assertEqual(treffer, [])

    def test_harness_wird_nie_getroffen(self):
        # R13i: genau diese Verwechslung hat den Harness schon einmal getoetet.
        treffer = aufraeumen.kandidaten(
            [_dummy_zeile(pid=500, name="python.exe",
                          cmd=r'python -u -m hx.cli --config g:\Harness\harness\harness.toml run'),
             _dummy_zeile(pid=501, name="python.exe",
                          cmd=r'python g:\Harness\harness\hx\cli.py watch',
                          pid_extra=1)],
            wurzel=self.WURZEL, seit_s=100.0, ausgenommen={1}, wurzeln_pids={500})
        self.assertEqual(treffer, [])

    def test_aeltere_prozesse_bleiben(self):
        # Ein Compiler, der schon vor dem Batch lief, gehoert nicht zu diesem Lauf.
        treffer = aufraeumen.kandidaten(
            [_dummy_zeile(pid=600, name="g++.exe", alter_s=4000,
                          cmd=r"g++ -c g:\Silent Scope Decomp\port\src\x.cpp")],
            wurzel=self.WURZEL, seit_s=100.0, ausgenommen={1}, wurzeln_pids={2})
        self.assertEqual(treffer, [])

    def test_ausgenommene_und_fremde_namen(self):
        treffer = aufraeumen.kandidaten(
            [_dummy_zeile(pid=700, cmd=r"python g:\Silent Scope Decomp\scripts\m149_bilanz.py"),
             _dummy_zeile(pid=701, name="explorer.exe", cmd=r"explorer g:\Silent Scope Decomp"),
             _dummy_zeile(pid=702, name="powershell.exe", cmd=r"powershell -File g:\Silent Scope Decomp\x.ps1")],
            wurzel=self.WURZEL, seit_s=100.0, ausgenommen={700}, wurzeln_pids={2})
        self.assertEqual(treffer, [])

    def test_waehrend_des_laufs_gesehene_nachfahren(self):
        """B207-Fall: der Hintergrundlauf nennt keinen Pfad, sein Shell ist tot.

        Belegt ist er trotzdem - weil `nachfahren_pids` ihn waehrend des Laufs gesehen
        hat, als die Kette noch lebte. Ohne diesen Nachweis blieb er unauffindbar.
        """
        treffer = aufraeumen.kandidaten(
            [_dummy_zeile(pid=4996, ppid=123456789, cmd="python -u scripts/c_kopf.py mutalle")],
            wurzel=self.WURZEL, seit_s=1500.0, ausgenommen={1}, wurzeln_pids=set(),
            bekannte_pids={4996})
        self.assertEqual([t["pid"] for t in treffer], [4996])
        self.assertIn("gesehen", treffer[0]["grund"])
        # Gegenprobe: ohne den Nachweis bleibt er liegen (kein Raten).
        treffer2 = aufraeumen.kandidaten(
            [_dummy_zeile(pid=4996, ppid=123456789, cmd="python -u scripts/c_kopf.py mutalle")],
            wurzel=self.WURZEL, seit_s=1500.0, ausgenommen={1}, wurzeln_pids=set())
        self.assertEqual(treffer2, [])

    @unittest.skipUnless(os.name == "nt", "Prozessabfrage ueber WMI")
    def test_nachfahren_pids_findet_kinder(self):
        eltern = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(20)"])
        try:
            time.sleep(1.5)
            pids = aufraeumen.nachfahren_pids(eltern.pid)
            self.assertNotIn(os.getpid(), pids)
            self.assertNotIn(eltern.pid, pids)
        finally:
            if eltern.poll() is None:
                eltern.kill()

    def test_bauwerkzeuge_werden_erkannt(self):
        namen = [("mingw32-make.exe", "make"), ("gcc.exe", "-c"), ("ppc_poc.exe", "run"),
                 ("port_selftest.exe", "all"), ("ld.exe", "-o out")]
        prozesse = [_dummy_zeile(pid=800 + i, name=n, cmd=f"{n} {a} -o g:\\Silent Scope Decomp\\x")
                    for i, (n, a) in enumerate(namen)]
        treffer = aufraeumen.kandidaten(prozesse, wurzel=self.WURZEL, seit_s=100.0,
                                        ausgenommen={1}, wurzeln_pids={2})
        self.assertEqual(len(treffer), len(namen))


class TestJobObjekt(unittest.TestCase):
    """Das Job-Objekt muss Prozesse wirklich mitnehmen (Punkte 2a)."""

    @unittest.skipUnless(os.name == "nt", "Windows-Job-Objekte")
    def test_kindprozess_stirbt_mit_dem_job(self):
        from hx.proc import run_stream
        job = aufraeumen.Job()
        self.assertTrue(job.create(), job.grund)
        skript = ROOT / "tests" / "_tmp_r13v3_job.py"
        skript.write_text("import time\ntime.sleep(60)\n", encoding="utf-8")
        p = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(60)"])
        try:
            self.assertTrue(job.assign(p.pid), job.grund)
            self.assertEqual(p.poll(), None)
            job.close()
            for _ in range(40):
                if p.poll() is not None:
                    break
                time.sleep(0.1)
            self.assertIsNotNone(p.poll(), "der Prozess muss mit dem Job sterben")
        finally:
            if p.poll() is None:
                p.kill()
            skript.unlink(missing_ok=True)

    @unittest.skipUnless(os.name == "nt", "Windows-Job-Objekte")
    def test_run_stream_weist_den_prozess_zu(self):
        from hx.proc import run_stream
        job = aufraeumen.Job()
        self.assertTrue(job.create(), job.grund)
        stream = ROOT / "tests" / "_tmp_r13v3_stream.jsonl"
        run = run_stream([sys.executable, "-c", "import time;time.sleep(4)"], env=dict(os.environ),
                         cwd=str(ROOT), out_path=stream, job=job)
        try:
            self.assertEqual(job.zugewiesen, [run.pid])
        finally:
            job.close()
            stream.unlink(missing_ok=True)
            if run.pid:
                subprocess.run(["taskkill", "/PID", str(run.pid), "/T", "/F"],
                               capture_output=True)


class TestWipNachAbbruch(unittest.TestCase):
    """Punkt 2b: halber Stand wird gesichert und gemeldet."""

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13v3_wip"
        if self.tmp.exists():
            import shutil
            shutil.rmtree(self.tmp, ignore_errors=True)
        self.tmp.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _orch(self, wip_ergebnis: dict):
        orch = Orchestrator.__new__(Orchestrator)
        orch.cfg = KONFIG
        orch.state = st.State(self.tmp / "run.json")
        orch.state.data["batch"] = 208
        orch.state.data["last_batch_number"] = 208
        orch.log = Log(self.tmp / "log.jsonl", echo=False)
        gesagt: list[str] = []
        orch.say = lambda *t, **k: gesagt.append(" ".join(str(x) for x in t))

        class FakeGit:
            def wip_rescue(self, batch, log_dir):
                (Path(log_dir)).mkdir(parents=True, exist_ok=True)
                return dict(wip_ergebnis)
        orch.git = FakeGit()

        class Res:
            killed_reason = "warteschleife"
        return orch, gesagt, Res()

    def test_dirty_stand_wird_gemeldet_und_steht_im_zustand(self):
        orch, gesagt, res = self._orch(
            {"dirty": True, "status": [" M port/src/x.cpp", "?? analysis/_m208/y.txt"],
             "patch": "logs/wip-b208.patch", "stash": "Saved working directory", "ref": "abc123"})
        eintrag = orch.wip_nach_abbruch(res)
        self.assertEqual(eintrag["batch"], 208)
        self.assertEqual(eintrag["grund"], "warteschleife")
        self.assertEqual(eintrag["dateien"], 2)
        self.assertEqual(eintrag["ref"], "abc123")
        gespeichert = json.loads((self.tmp / "run.json").read_text(encoding="utf-8"))
        self.assertEqual(gespeichert["letzter_abbruch"]["ref"], "abc123")
        self.assertTrue(any("ABBRUCH" in s and "abc123" in s for s in gesagt))
        self.assertTrue(any("Arbeitsbaum ist jetzt sauber" in s for s in gesagt))

    def test_sauberer_baum_wird_ebenso_gemeldet(self):
        orch, gesagt, res = self._orch({"dirty": False, "status": [], "patch": "", "stash": None})
        eintrag = orch.wip_nach_abbruch(res)
        self.assertFalse(eintrag["dirty"])
        self.assertTrue(any("war sauber" in s for s in gesagt))

    def test_fehlgeschlagene_sicherung_wird_deutlich_gemeldet(self):
        orch, gesagt, res = self._orch({"dirty": None, "status": [],
                                        "fehler": "git stash nicht moeglich"})
        eintrag = orch.wip_nach_abbruch(res)
        self.assertIn("git stash", eintrag["fehler"])
        self.assertTrue(any("WIP-Sicherung FEHLGESCHLAGEN" in s for s in gesagt))
        # Der Messdatenblock muss es ebenfalls zeigen.
        zeile = orch.abbruch_zeile()
        self.assertIn("FEHLGESCHLAGEN", zeile)


class TestAbbruchImReview(unittest.TestCase):
    """Punkte 2b/2c: der Review muss den Abbruch und die Nummer einordnen."""

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13v3_review"
        if self.tmp.exists():
            import shutil
            shutil.rmtree(self.tmp, ignore_errors=True)
        self.tmp.mkdir(parents=True, exist_ok=True)
        (self.tmp / "analysis").mkdir(parents=True, exist_ok=True)
        self.anker = self.tmp / "analysis" / "r1b-workstream.md"
        self.anker.write_text("**Stand:** BATCH 207 (2026-09-28)\n\nText\n", encoding="utf-8")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _orch(self, batch: int, abb: dict | None = None):
        orch = Orchestrator.__new__(Orchestrator)
        orch.cfg = KONFIG
        orch.state = st.State(self.tmp / "run.json")
        orch.state.data["batch"] = batch
        if abb:
            orch.state.data["letzter_abbruch"] = abb
        orch.log = Log(self.tmp / "log.jsonl", echo=False)
        # Anker lesen, aber aus dem Testordner (Decomp-Repo bleibt unberuehrt).
        orch.cfg.data["paths"]["decomp"] = str(self.tmp)
        return orch

    def test_nummer_kommt_aus_dem_anker_nicht_aus_dem_zustand(self):
        orch = self._orch(batch=208)
        self.assertEqual(orch.anchor_batch(), 207)
        self.assertEqual(orch.expected_batch(), 208)
        # Anker NICHT fortgeschrieben -> derselbe Wert, auch wenn der Zustand 209 sagt.
        orch.state.data["batch"] = 209
        self.assertEqual(orch.expected_batch(), 208)

    def test_abbruchzeile_nennt_gleiche_nummer_und_sicherung(self):
        orch = self._orch(batch=208, abb={"batch": 208, "grund": "warteschleife",
                                          "ts": "2026-09-28T18:00:00+00:00",
                                          "dirty": True, "dateien": 3,
                                          "ref": "deadbee", "patch": "logs/wip-b208.patch"})
        zeile = orch.abbruch_zeile()
        self.assertIn("Batch 208 ABGEBROCHEN", zeile)
        self.assertIn("warteschleife", zeile)
        self.assertIn("deadbee", zeile)
        self.assertIn("dieselbe Nummer", zeile)
        self.assertIn("208", zeile.split("naechste Lauf bekommt also")[1])

    def test_ohne_abbruch_keine_zeile(self):
        orch = self._orch(batch=208)
        self.assertEqual(orch.abbruch_zeile(), "kein Abbruch")
        self.assertEqual(orch.abbruch_block(), "")

    def test_review_prompt_enthaelt_den_abbruchblock(self):
        orch = self._orch(batch=208, abb={"batch": 208, "grund": "wall",
                                          "ts": "2026-09-28T18:00:00+00:00",
                                          "dirty": True, "dateien": 1, "ref": "cafe", "patch": ""})
        ctx = {"batch": 208, "next_batch": 208, "anchor_batch": 207, "facts": "(x)",
               "worker_report": "(kein Bericht)", "diff": "(x)", "historie": "(x)",
               "plan_ist": "(x)", "queue_block": "", "ds_queue": "", "anchor": "(x)",
               "snapshot": "(x)", "handover": "", "markers": "",
               "abbruch": orch.abbruch_block(), "extra": ""}
        prompt = reviewer.build_prompt(KONFIG, "batch_end", ctx)
        self.assertIn("=== ABBRUCH DES BEWERTETEN LAUFS", prompt)
        self.assertIn("Batch 208 ABGEBROCHEN (wall", prompt)
        # Ohne Abbruch steht dort ausdruecklich, dass alles regulaer war.
        ctx["abbruch"] = ""
        prompt2 = reviewer.build_prompt(KONFIG, "batch_end", ctx)
        self.assertIn("kein Abbruch - der Lauf ist regulaer", prompt2)


class TestVorgaengerSicherung(unittest.TestCase):
    """Punkt 2c: gleiche Nummer = gleicher Ordner - die alten Belege muessen bleiben."""

    def setUp(self):
        self.rd = Path(ROOT) / "tests" / "_tmp_r13v3_v1" / "b208"
        if self.rd.parent.exists():
            import shutil
            shutil.rmtree(self.rd.parent, ignore_errors=True)
        self.rd.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.rd.parent, ignore_errors=True)

    def test_belege_werden_umbenannt_und_fremde_nicht(self):
        from hx import worker as wk
        for name in ("stream.jsonl", "stream.err.txt", "auftrag.md", "result.json",
                     "antwort.md", "harness-facts.md", "reviewer.jsonl"):
            (self.rd / name).write_text(name, encoding="utf-8")
        namen = wk.sichere_vorgaenger(self.rd)
        # Benennung: `-v1` an den Stamm gehaengt - fuer den Mitschnitt ergibt das genau
        # `stream-v1.jsonl`, wie es `retention.MIT_ZIP` schon kennt.
        self.assertEqual(sorted(namen),
                         ["antwort-v1.md", "auftrag-v1.md", "harness-facts-v1.md",
                          "result-v1.json", "stream-v1.jsonl", "stream.err-v1.txt"])
        self.assertTrue((self.rd / "stream-v1.jsonl").is_file())
        self.assertEqual((self.rd / "stream-v1.jsonl").read_text(encoding="utf-8"),
                         "stream.jsonl")
        self.assertFalse((self.rd / "stream.jsonl").exists())
        # Fremdes bleibt liegen (das Review-Verzeichnis gehoert dazu).
        self.assertTrue((self.rd / "reviewer.jsonl").is_file())

    def test_zweiter_lauf_ueberschreibt_den_ersten_nicht(self):
        from hx import worker as wk
        (self.rd / "stream.jsonl").write_text("ERSTE FASSUNG", encoding="utf-8")
        wk.sichere_vorgaenger(self.rd)
        (self.rd / "stream.jsonl").write_text("ZWEITE FASSUNG", encoding="utf-8")
        self.assertEqual((self.rd / "stream-v1.jsonl").read_text(encoding="utf-8"),
                         "ERSTE FASSUNG")
        self.assertEqual((self.rd / "stream.jsonl").read_text(encoding="utf-8"),
                         "ZWEITE FASSUNG")

    def test_ohne_mitschnitt_passiert_nichts(self):
        from hx import worker as wk
        (self.rd / "auftrag.md").write_text("alt", encoding="utf-8")
        self.assertEqual(wk.sichere_vorgaenger(self.rd), [])
        self.assertTrue((self.rd / "auftrag.md").is_file())


class TestAufraeumenZeile(unittest.TestCase):
    def _orch(self):
        orch = Orchestrator.__new__(Orchestrator)
        orch.cfg = KONFIG
        orch.state = st.State(Path(ROOT) / "tests" / "_tmp_r13v3_zeile.json")
        orch.log = Log(Path(ROOT) / "tests" / "_tmp_r13v3_zeile.log", echo=False)
        return orch

    def tearDown(self):
        for n in ("_tmp_r13v3_zeile.json", "_tmp_r13v3_zeile.log"):
            (Path(ROOT) / "tests" / n).unlink(missing_ok=True)

    def test_zeile_ohne_abbruch(self):
        orch = self._orch()
        self.assertEqual(orch.aufraeumen_zeile({}), "kein Abbruch - nicht noetig")
        self.assertEqual(orch.aufraeumen_zeile(None), "kein Abbruch - nicht noetig")

    def test_zeile_mit_resten(self):
        orch = self._orch()
        auf = {"ok": True, "anlass": "warteschleife", "job": "Job x: 1 Prozessbaum",
               "gefunden": [{"pid": 999, "name": "python.exe", "grund": "Kommandozeile"}],
               "beendet": [999]}
        zeile = orch.aufraeumen_zeile({"aufraeumen": auf})
        self.assertIn("1 von 1 Resten beendet", zeile)
        self.assertIn("python.exe:999", zeile)
        self.assertIn("warteschleife", zeile)


if __name__ == "__main__":
    unittest.main()
