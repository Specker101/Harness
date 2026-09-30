"""Tests fuer R13au (2026-09-30): Rechnerlast mitschreiben (Auftrag Teil C).

**Auftrag.** Während eines Batches jede Minute CPU gesamt in %, freien RAM in MB und die
Zahl der `python`-/`java`-Prozesse erfassen, die **nicht** zum Worker gehören; die Zahlen
als `cpu_mittel`, `cpu_max`, `ram_frei_min`, `fremdlast_minuten` in `result.json` und als
Zeile in die Review-Fakten. Dazu die Arbeitsregel, während eines Batches nur die
betroffenen Testdateien zu fahren.

**Definition der drei Gruppen** (`hx/last.py`): *eigene* = Harness-Baum (der Worker ist
ein Kind des Harness), *ghidra* = der Ghidra-Server des Projekts (Java, erkannt an der
Kommandozeile), *fremd* = alles andere an `python`/`java`. Nur **fremd** erzeugt
`fremdlast_minuten`.
"""

from __future__ import annotations

import json
import inspect
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import last, streamjson, worker                              # noqa: E402
from hx.config import load_config                                    # noqa: E402
from hx.orchestrator import Orchestrator                             # noqa: E402
from hx.util import Log, ensure_dir, read_text, write_text_atomic    # noqa: E402


# ------------------------------------------------------- gefälschtes psutil
class _Proc:
    def __init__(self, pid: int, name: str, cmdline: list[str] | None = None):
        self.info = {"pid": pid, "ppid": 0, "name": name, "cmdline": cmdline or []}


class _VM:
    total = 6 * 1024 ** 3
    available = 3 * 1024 ** 3


class FakePsutil:
    """So viel psutil, wie `hx/last.py` braucht - mit vorgegebenen Prozessen."""

    def __init__(self, procs=(), cpu: float = 25.0, ram_frei_mb: float = 2048.0,
                 fehler: bool = False):
        self._procs = list(procs)
        self._cpu = cpu
        self._ram = ram_frei_mb
        self._fehler = fehler

    def cpu_percent(self, interval=None):
        if self._fehler:
            raise OSError("kein Zaehler")
        return self._cpu

    def virtual_memory(self):
        if self._fehler:
            raise OSError("kein Zaehler")
        vm = _VM()
        vm.available = int(self._ram * 1024 * 1024)
        return vm

    def process_iter(self, felder=None):
        return list(self._procs)

    def cpu_count(self, logical=True):
        return 8 if logical else 4


class TestProzessgruppen(unittest.TestCase):
    """Wer zaehlt als eigen, wer als Ghidra, wer als fremd?"""

    def recorder(self, procs):
        with mock.patch.object(last, "_psutil", return_value=FakePsutil(procs)):
            return last.Recorder()

    def test_drei_gruppen(self):
        procs = [
            _Proc(1, "python.exe"),                                  # Harness (eigene pid)
            _Proc(2, "java.exe", ["C:/jdk/bin/java", "-Dghidra.home=g:/gh",
                                  "ghidra.GhidraMCP"]),
            _Proc(3, "python.exe", ["python", "tests/test_x.py"]),   # fremd
            _Proc(4, "java.exe", ["java", "irgendeinEmulator"]),     # fremd
            _Proc(5, "claude.exe"),                                  # kein python/java
        ]
        with mock.patch.object(last.os, "getpid", return_value=1):
            eintrag = self.recorder(procs).probe()
        self.assertEqual(eintrag["eigene"], 1)
        self.assertEqual(eintrag["ghidra"], 1)
        self.assertEqual(eintrag["fremd"], 2)
        self.assertEqual(eintrag["fremde_namen"], ["java.exe", "python.exe"])

    def test_ram_und_cpu_kommen_aus_der_quelle(self):
        r = self.recorder([_Proc(1, "python.exe")])
        with mock.patch.object(last.os, "getpid", return_value=1):
            eintrag = r.probe()
        self.assertEqual(eintrag["cpu"], 25.0)
        self.assertEqual(eintrag["ram_frei_mb"], 2048.0)

    def test_fehler_der_quelle_ergibt_keine_zahl(self):
        with mock.patch.object(last, "_psutil",
                               return_value=FakePsutil([], fehler=True)):
            r = last.Recorder()
            with mock.patch.object(last.os, "getpid", return_value=1):
                eintrag = r.probe()
            self.assertIsNone(eintrag["cpu"])
            self.assertIn("Aufnahme fehlgeschlagen", r.fehler)
            self.assertIn("nicht gemessen", last.fakten_zeile(last.in_result(r.werte())))


class TestAuswertung(unittest.TestCase):
    def test_mittel_spitze_minimum_und_fremdminuten(self):
        r = last.Recorder()
        r.proben = [
            {"cpu": 10.0, "ram_frei_mb": 3000.0, "fremd": 0, "ghidra": 1, "eigene": 2,
             "fremde_namen": []},
            {"cpu": 80.0, "ram_frei_mb": 1200.0, "fremd": 2, "ghidra": 1, "eigene": 2,
             "fremde_namen": ["python.exe"]},
            {"cpu": 30.0, "ram_frei_mb": 900.0, "fremd": 1, "ghidra": 0, "eigene": 3,
             "fremde_namen": ["python.exe", "java.exe"]},
        ]
        w = r.werte()
        self.assertEqual(w["cpu_mittel"], 40.0)
        self.assertEqual(w["cpu_max"], 80.0)
        self.assertEqual(w["ram_frei_min"], 900.0)
        self.assertEqual(w["fremdlast_minuten"], 2)
        self.assertEqual(w["fremd_max"], 2)
        self.assertEqual(w["proben"], 3)
        self.assertEqual(w["ghidra_prozesse_max"], 1)
        self.assertEqual(w["eigene_prozesse_max"], 3)
        self.assertEqual(w["fremde_namen"], ["python.exe", "java.exe"])

    def test_ohne_proben_keine_geratenen_zahlen(self):
        w = last.Recorder().werte()
        self.assertIsNone(w["cpu_mittel"])
        self.assertIsNone(w["cpu_max"])
        self.assertIsNone(w["ram_frei_min"])
        self.assertEqual(w["fremdlast_minuten"], 0)
        self.assertEqual(w["proben"], 0)

    def test_luecken_verfaelschen_das_mittel_nicht(self):
        """Fehlt eine CPU-Zahl (Quelle gestolpert), zaehlt sie nicht als 0."""
        r = last.Recorder()
        r.proben = [{"cpu": 20.0, "ram_frei_mb": 100.0, "fremd": 0},
                    {"cpu": None, "ram_frei_mb": None, "fremd": 0},
                    {"cpu": 40.0, "ram_frei_mb": 50.0, "fremd": 0}]
        w = r.werte()
        self.assertEqual(w["cpu_mittel"], 30.0)
        self.assertEqual(w["ram_frei_min"], 50.0)


class TestFaktenzeile(unittest.TestCase):
    def test_mit_werten(self):
        res = {"cpu_mittel": 31.2, "cpu_max": 68.0, "ram_frei_min": 4210.0,
               "fremdlast_minuten": 3, "last_proben": 47, "last_fremd_max": 9,
               "last_fremde_namen": ["python.exe"], "last_ghidra_max": 1,
               "last_quelle": "psutil"}
        text = last.fakten_zeile(res)
        self.assertTrue(text.startswith("RECHNERLAST: CPU 31.2 % (Spitze 68.0 %), "
                                        "RAM frei min 4210 MB"), text)
        self.assertIn("FREMDLAST in 3 von 47 Minuten (bis 9 Prozesse: python.exe)", text)
        self.assertIn("Ghidra lief mit (1 Java-Prozess)", text)

    def test_ohne_fremdlast_steht_das_da(self):
        res = {"cpu_mittel": 12.0, "cpu_max": 20.0, "ram_frei_min": 500.0,
               "fremdlast_minuten": 0, "last_proben": 4, "last_quelle": "psutil"}
        self.assertIn("keine Fremdlast in 0 von 4 Minuten", last.fakten_zeile(res))

    def test_nicht_gemessen_wird_genannt(self):
        self.assertIn("nicht gemessen", last.fakten_zeile({}))
        self.assertIn("nachgerechnet", last.fakten_zeile({"last_fehler": "nachgerechnet"}))
        self.assertIn("Quelle windows", last.fakten_zeile(
            {"cpu_mittel": 1.0, "cpu_max": 2.0, "ram_frei_min": 3.0,
             "fremdlast_minuten": 0, "last_proben": 1, "last_quelle": "windows"}))

    def test_feldnamen_wie_im_auftrag(self):
        w = {"cpu_mittel": 1.0, "cpu_max": 2.0, "ram_frei_min": 3.0,
             "fremdlast_minuten": 4, "fremd_max": 5, "proben": 6, "intervall_s": 60.0,
             "ghidra_prozesse_max": 1, "eigene_prozesse_max": 2, "fremde_namen": [],
             "quelle": "psutil", "fehler": ""}
        res = last.in_result(w)
        for feld in ("cpu_mittel", "cpu_max", "ram_frei_min", "fremdlast_minuten"):
            self.assertIn(feld, res)
        self.assertEqual(res["fremdlast_minuten"], 4)
        self.assertEqual(res["last_fremd_max"], 5)
        self.assertEqual(res["last_proben"], 6)
        self.assertEqual(last.in_result(None)["cpu_mittel"], None)


class TestMaschineUndRecorder(unittest.TestCase):
    def test_maschine_liefert_kerne_und_ram(self):
        m = last.maschine()
        self.assertGreaterEqual(m["threads"] or 0, 1)
        self.assertGreaterEqual(m["ram_gesamt_mb"] or 0, 512)
        self.assertIn(m["quelle"], ("psutil", "wmic", ""))

    def test_probe_echt_ist_plausibel(self):
        r = last.Recorder()
        eintrag = r.probe()
        self.assertIsNotNone(eintrag["cpu"], "eine echte CPU-Zahl, keine 0.0 aus Nullintervall")
        self.assertGreaterEqual(eintrag["cpu"] or 0, 0.0)
        self.assertLessEqual(eintrag["cpu"] or 0, 100.0)
        self.assertGreater(eintrag["ram_frei_mb"] or 0, 0)
        self.assertGreaterEqual(eintrag["eigene"], 1, "der Testprozess selbst")

    def test_start_ist_idempotent_und_stop_still(self):
        r = last.Recorder(intervall_s=0.05)
        r.start()
        faden = r._faden
        r.start()
        self.assertIs(r._faden, faden, "kein zweiter Faden")
        self.assertGreaterEqual(len(r.proben), 1, "die erste Probe kommt sofort")
        r.stop()
        r.stop()
        self.assertIsNone(r._faden)


class TestVerdrahtung(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13au"
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

    def test_result_json_traegt_die_vier_zahlen(self):
        res = worker.WorkerResult()
        res.last = {"cpu_mittel": 31.2, "cpu_max": 68.0, "ram_frei_min": 4210.0,
                    "fremdlast_minuten": 3, "fremd_max": 9, "proben": 47,
                    "intervall_s": 60.0, "ghidra_prozesse_max": 1,
                    "eigene_prozesse_max": 4, "fremde_namen": ["python.exe"],
                    "quelle": "psutil", "fehler": ""}
        stats = streamjson.StreamStats()
        state = mock.Mock()
        state.data = {}
        with mock.patch("hx.worker.write_json_atomic") as schreiben, \
                mock.patch("hx.worker.write_snapshot", return_value=""), \
                mock.patch.object(worker.reihenfolge, "git_zeilen", return_value=[]):
            worker._finish_run(self.cfg, state, res, stats, 999, "none", self.log,
                               ghidra_save=False)
        nutzlast = schreiben.call_args[0][1]
        self.assertEqual(nutzlast.get("cpu_mittel"), 31.2)
        self.assertEqual(nutzlast.get("cpu_max"), 68.0)
        self.assertEqual(nutzlast.get("ram_frei_min"), 4210.0)
        self.assertEqual(nutzlast.get("fremdlast_minuten"), 3)

    def test_recorder_haengt_im_worker_lauf(self):
        """`worker.run_batch` startet den Recorder und beendet ihn im `finally`."""
        quelle = inspect.getsource(worker.run_batch)
        self.assertIn("last.Recorder(log=log).start()", quelle)
        self.assertIn("last_recorder.stop()", quelle)
        self.assertIn("res.last = last_recorder.werte()", quelle)

    def test_review_fakten_zeigen_die_zeile(self):
        rd = ensure_dir(self.root / "runs" / "b220")
        write_text_atomic(rd / "result.json", json.dumps({
            "batch": 220, "rc": 0, "profile": "none", "program": "main.bin",
            "cpu_mittel": 31.2, "cpu_max": 68.0, "ram_frei_min": 4210.0,
            "fremdlast_minuten": 3, "last_proben": 47, "last_quelle": "psutil",
            "last_fremd_max": 9, "last_fremde_namen": ["python.exe"],
            "last_ghidra_max": 1,
        }))
        o = Orchestrator(self.cfg, self.log, mock=True,
                         state_file=self.root / "state" / "run.json")
        o.say = lambda *a, **k: None
        o.state.data["last_batch_number"] = 220
        text = o.harness_facts(220, ziel=self.root / "out")
        self.assertIn("- RECHNERLAST: CPU 31.2 % (Spitze 68.0 %), RAM frei min 4210 MB",
                      text)
        self.assertIn("FREMDLAST in 3 von 47 Minuten (bis 9 Prozesse: python.exe)", text)

    def test_review_fakten_ohne_messung_sagen_es(self):
        rd = ensure_dir(self.root / "runs" / "b221")
        write_text_atomic(rd / "result.json", json.dumps({
            "batch": 221, "rc": 0, "last_fehler": "nachgerechnet"}))
        o = Orchestrator(self.cfg, self.log, mock=True,
                         state_file=self.root / "state" / "run.json")
        o.say = lambda *a, **k: None
        o.state.data["last_batch_number"] = 221
        text = o.harness_facts(221, ziel=self.root / "out")
        self.assertIn("- RECHNERLAST: nicht gemessen (nachgerechnet)", text)


if __name__ == "__main__":
    unittest.main()
