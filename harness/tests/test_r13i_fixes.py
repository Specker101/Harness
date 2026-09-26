"""Tests fuer R13i: harter Tod durch Muster-Prozessabbau (2026-09-26).

Anlass: der Harness starb zweimal still. Der zweite Fall ist belegt - der Worker hat
in Batch 178

    Get-Process python | Where-Object { $_.CPU -gt 50 } | Stop-Process

abgesetzt und damit **jeden** python.exe mit ueber 50 s CPU-Zeit getoetet, darunter
den Harness selbst (`python.exe -m hx.cli run`, ~370 s CPU). Ein `TerminateProcess`
hinterlaesst keinen Crash-Bericht, keine stderr-Zeile und keinen Ereigniseintrag.

Geprueft wird:
* `streamjson.abbau_gefahr` erkennt die gefaehrlichen Muster (CPU/Name/pauschale Liste)
  und laesst die harmlosen durch (feste `-Id`, `CommandLine -like`).
* Der Harness nennt den Befund beim naechsten Start (`orchestrator.abbau_ursache`).
* Der Waechter greift, wenn ein Werkzeugaufruf die Gefahr traegt.
"""

from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import reviewer, streamjson                                   # noqa: E402
from hx.config import load_config                                     # noqa: E402
from hx.orchestrator import Orchestrator                              # noqa: E402
from hx.util import Log, ensure_dir                                   # noqa: E402

TOETER = ("Get-Process python -ErrorAction SilentlyContinue | "
          "Where-Object { $_.CPU -gt 50 } | ForEach-Object { Stop-Process -Id $_.Id -Force }")


def zeile_tool(cmd: str, tid: str = "t1") -> str:
    return json.dumps({"type": "assistant", "timestamp": "2026-09-26T19:37:57Z",
                       "message": {"id": "m1", "model": "m", "usage": {}, "content": [
                           {"type": "tool_use", "id": tid, "name": "PowerShell",
                            "input": {"command": cmd}}]}}, ensure_ascii=False)


HAARMLOS = [
    "Stop-Process -Id 13744 -Force -ErrorAction SilentlyContinue",
    "Get-Process python | Where-Object { $_.Id -eq 7856 } | Stop-Process -Force",
    "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object "
    "{ $_.CommandLine -like \"*port4c2*\" } | ForEach-Object { Stop-Process -Id $_.ProcessId }",
    "git status --porcelain",
    "",
]

GEFAEHRLICH = [
    TOETER,
    "Stop-Process -Name python -Force",
    "taskkill /IM python.exe /F",
    "Get-Process python | Stop-Process -Force",
]


class TestErkennung(unittest.TestCase):
    def test_gefaehrliche_muster(self):
        for cmd in GEFAEHRLICH:
            self.assertIsNotNone(streamjson.abbau_gefahr(cmd), f"nicht erkannt: {cmd}")

    def test_harmlose_befehle_bleiben_still(self):
        for cmd in HAARMLOS:
            self.assertIsNone(streamjson.abbau_gefahr(cmd), f"Fehlalarm: {cmd}")

    def test_cpu_befund_nennt_den_grund(self):
        grund = streamjson.abbau_gefahr(TOETER) or ""
        self.assertIn("CPU", grund)
        self.assertIn("Harness", grund)

    def test_stream_haelt_den_befund_fest(self):
        s = streamjson.StreamStats()
        s.feed(zeile_tool(TOETER))
        self.assertEqual(len(s.abbau), 1)
        self.assertEqual(s.abbau[0]["werkzeug"], "PowerShell")
        self.assertIn("CPU", s.abbau[0]["grund"])

    def test_harmloser_abbau_landet_nicht_im_stream(self):
        s = streamjson.StreamStats()
        s.feed(zeile_tool("Stop-Process -Id 13744 -Force"))
        self.assertEqual(s.abbau, [])


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__file__).resolve().parent / "_tmp_r13i"
        shutil.rmtree(self.tmp, ignore_errors=True)
        cfg = load_config()
        cfg.data["paths"]["root"] = str(ensure_dir(self.tmp / "harness"))
        cfg.data["paths"]["decomp"] = str(ensure_dir(self.tmp / "decomp"))
        cfg.data["paths"]["secrets"] = str(ensure_dir(self.tmp / "secrets"))
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["telegram"]["allowlist_user_ids"] = []
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def orch(self, gesagt: list | None = None) -> Orchestrator:
        o = Orchestrator(self.cfg, self.log, mock=True,
                         state_file=self.tmp / "harness" / "state" / "run.json")
        o.say = (lambda *a, **k: None) if gesagt is None else (lambda t, *a, **k: gesagt.append(str(t)))
        return o

    def stream(self, batch: int, zeilen: list[str]) -> None:
        rd = ensure_dir(Path(self.cfg.sub("runs")) / f"b{batch:03d}")
        (rd / "stream.jsonl").write_text("\n".join(zeilen) + "\n", encoding="utf-8")


class TestStartforensik(Base):
    def test_befund_wird_gefunden(self):
        self.stream(178, [zeile_tool("git status"), zeile_tool(TOETER, "t2")])
        treffer = self.orch().abbau_ursache(178)
        self.assertIn("CPU", treffer)
        self.assertIn("Stop-Process", treffer)

    def test_ohne_befund_leer(self):
        self.stream(177, [zeile_tool("Stop-Process -Id 18172 -Force")])
        self.assertEqual(self.orch().abbau_ursache(177), "")

    def test_ohne_mitschnitt_leer(self):
        self.assertEqual(self.orch().abbau_ursache(199), "")

    def test_recover_nennt_den_harten_tod(self):
        """Zustand steht auf 'Worker laeuft' und kein Prozess lebt -> Harttod melden."""
        self.stream(178, [zeile_tool(TOETER)])
        gesagt: list[str] = []
        o = self.orch(gesagt)
        o.state.data["batch"] = 178
        o.state.data["worker"] = {"pid": 999999, "started_at": "2026-09-26T18:55:21+00:00",
                                  "log": "", "session_id": "x"}
        o.state.save()
        o.recover()
        text = "\n".join(gesagt)
        self.assertIn("HART", text)
        self.assertIn("verbotener Prozessabbau", text)
        self.assertFalse(o.state.data.get("worker"), "Worker-Eintrag muss geraeumt sein")


class TestModulnamen(unittest.TestCase):
    """Statische Pruefung: keine undefinierten Namen (R13i).

    Auslöser: in `reviewer.py` fehlte nach dem Einbau der Secret-Pruefung der Import
    von `streamjson`. Der Fehler stand in einem `try/except` und tauchte nur als
    WARN-Zeile im Log auf (`name 'streamjson' is not defined`).
    """

    def test_keine_undefinierten_namen(self):
        try:
            from pyflakes.api import checkPath                 # noqa: PLC0415
            from pyflakes.reporter import Reporter             # noqa: PLC0415
        except ImportError:                                    # pragma: no cover
            self.skipTest("pyflakes nicht installiert")
        import io
        meldungen: list[str] = []

        class _Sammler(Reporter):
            def unexpectedError(self, filename, msg):          # noqa: N802
                meldungen.append(f"{filename}: {msg}")

            def syntaxError(self, filename, msg, lineno, offset, text):   # noqa: N802
                meldungen.append(f"{filename}:{lineno}: Syntaxfehler: {msg}")

            def report(self, messageClass, filename, lineno, text):       # noqa: N802
                meldungen.append(f"{filename}:{lineno}: {text}")

        for p in sorted((ROOT / "hx").glob("*.py")):
            checkPath(str(p), _Sammler(io.StringIO(), io.StringIO()))
        undefined = [m for m in meldungen if "undefined name" in m]
        self.assertEqual(undefined, [], "undefinierte Namen: " + "; ".join(undefined))

    def test_reviewer_hat_den_streamjson_import(self):
        self.assertTrue(reviewer.streamjson is streamjson)


if __name__ == "__main__":
    unittest.main()
