"""Tests fuer R13bw-11 (07.10.2026): `port_suche` wird nicht mehr gekuerzt.

**Auftrag (Nutzer, Harness-Wartung, 07.10.2026 Teil A).** Aussensicht B289, Befund 4
(`runs/b289/stream.jsonl:56505-56509`): der Worker rief

    cd "G:\\Silent Scope Decomp"; python scripts/port_suche.py 80008828 2>&1 | Select-Object -First 25

auf. Die Ausgabe brach genau an der Ueberschrift der **Port-Treffer** ab
(`port/src/vbi_handler.cpp`), weil die Port-Fundstellen am **Ende** stehen. Die Textregel
`AGENTS.md` R13az hat das nicht verhindert - jetzt lehnt der PreToolUse-Hook den Aufruf ab.

Abgelehnt: `port_suche` **per Pipe gekuerzt** (`Select-Object -First|-Last`,
`Select -First|-Last`, `head`, `| more`).
Erlaubt: ohne Pipe, mit `--schreiben`, und jede blosse ERWAEHNUNG des Skripts
(Suche/Lesen des Quelltextes) - das ist kein Aufruf.

Das laufende Harness-Verzeichnis wird NICHT angefasst; alle Faelle laufen in
Wegwerf-Verzeichnissen (`tests/_tmp_r13bw11*`).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import streamjson, worker                                 # noqa: E402
from hx.config import load_config                                 # noqa: E402
from hx.util import ensure_dir, write_text_atomic                 # noqa: E402

# Der Original-Aufruf, wortgetreu aus dem Mitschnitt (`runs/b289/stream.jsonl:56505`).
ORIGINAL = ('cd "G:\\Silent Scope Decomp"; python scripts/port_suche.py 80008828 2>&1 '
            '| Select-Object -First 25')


def shell(command: str) -> dict:
    """So sieht der Werkzeugaufruf im Mitschnitt aus (Name `PowerShell`, R13i)."""
    return {"tool_input": {"command": command}, "tool_name": "PowerShell"}


# ------------------------------------------------- 1) Erkennung (ohne Hook)
class TestErkennung(unittest.TestCase):
    def kuerzt(self, command: str, name: str = "PowerShell") -> bool:
        return streamjson.port_suche_kuerzung(name, {"command": command})

    # ------------------------------------------------------------------ abgelehnt
    def test_original_aus_dem_mitschnitt(self):
        self.assertTrue(self.kuerzt(ORIGINAL), "genau der Aufruf aus B289")

    def test_die_fuenf_muster_des_auftrags(self):
        for c in ('python scripts/port_suche.py 80008828 | Select-Object -First 25',
                  'python scripts/port_suche.py 80008828 | Select -First 25',
                  'python scripts/port_suche.py 80008828 | head -25',
                  'python scripts/port_suche.py 80008828 | more',
                  'python scripts/port_suche.py 80008828 | Select-Object -Last 5'):
            with self.subTest(command=c):
                self.assertTrue(self.kuerzt(c), c)

    def test_schreibweisen_des_aufrufs(self):
        for c in ('python -u scripts/port_suche.py 80008828 2>&1 | Select-Object -First 25',
                  'py scripts/port_suche.py 0x80008828 | Select-Object -First 10',
                  '& .\\scripts\\port_suche.py 80008828 | Select-Object -First 5',
                  '.\\scripts\\port_suche.py 80008828 | head -3'):
            with self.subTest(command=c):
                self.assertTrue(self.kuerzt(c), c)

    def test_kuerzung_spaeter_in_der_kette_zaehlt_auch(self):
        self.assertTrue(self.kuerzt("python scripts/port_suche.py 80008828 "
                                    "| Select-String 'Treffer' | Select-Object -First 3"))

    # ------------------------------------------------------------------- erlaubt
    def test_ohne_pipe_erlaubt(self):
        self.assertFalse(self.kuerzt("python scripts/port_suche.py 80008828"))
        self.assertFalse(self.kuerzt('cd "G:\\Silent Scope Decomp"; '
                                     "python scripts/port_suche.py 80008828"))

    def test_mit_schreiben_erlaubt(self):
        self.assertFalse(self.kuerzt("python scripts/port_suche.py 80008828 --schreiben"))
        self.assertFalse(self.kuerzt("python scripts/port_suche.py 80008828 --schreiben "
                                     "| Select-Object -First 5"),
                         "--schreiben schreibt die Datei; gekuerzt wird nur die Zusammenfassung")
        self.assertFalse(self.kuerzt("python scripts/port_suche.py 80008828 --schreiben; "
                                     "Get-Content docs/_x.txt | Select-Object -First 5"))

    def test_erwaehnung_ist_kein_aufruf(self):
        for c in ("Select-String -Path scripts/port_suche.py -Pattern 'PORT-TREFFER'",
                  "Get-Content scripts/port_suche.py | Select-Object -First 5",
                  "git add scripts/port_suche.py"):
            with self.subTest(command=c):
                self.assertFalse(self.kuerzt(c), c)

    def test_anderer_befehl_ist_keiner(self):
        self.assertFalse(self.kuerzt("python scripts/port_andere.py 80008828 "
                                     "| Select-Object -First 5"))
        self.assertFalse(self.kuerzt("python scripts/preflight.py before "
                                     "| Select-Object -First 5"))

    def test_nur_das_shell_werkzeug_zaehlt(self):
        for name in ("PowerShell", "Bash", "Shell", "Terminal"):
            self.assertTrue(streamjson.port_suche_kuerzung(name, {"command": ORIGINAL}))
        self.assertFalse(streamjson.port_suche_kuerzung("Read", {"command": ORIGINAL}))
        self.assertFalse(streamjson.port_suche_kuerzung("Grep", {"command": ORIGINAL}))

    def test_fehlende_eingabe_ist_kein_aufruf(self):
        self.assertFalse(streamjson.port_suche_kuerzung("PowerShell"))
        self.assertFalse(streamjson.port_suche_kuerzung("PowerShell", {}))
        self.assertFalse(streamjson.port_suche_kuerzung("PowerShell", {"command": None}))


# ------------------------------------------------------------ 2) Der Hook selbst
class TestHook(unittest.TestCase):
    """Der PreToolUse-Zweig entscheidet - wie die Claude-CLI ihn aufruft (stdin-JSON)."""

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13bw11_hook"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "root")
        self.lauf = ensure_dir(self.root / "runs" / "b289")
        self.state = self.root / "state" / "run.json"
        write_text_atomic(self.state, json.dumps({"live": {"batch": 289}}))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def hook(self, command: str, name: str = "PowerShell") -> tuple[str, str]:
        args = [sys.executable, str(ROOT / "tools" / "batch_uhr.py"),
                "--state", str(self.state), "--umschalt", "80", "--pre",
                "--run", str(self.lauf)]
        daten = {"hook_event_name": "PreToolUse", "tool_name": name,
                 "tool_input": {"command": command}}
        p = subprocess.run(args, input=json.dumps(daten).encode("utf-8"),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        self.assertEqual(p.returncode, 0, p.stderr.decode("utf-8", "replace")[:300])
        return p.stdout.decode("utf-8"), p.stderr.decode("utf-8", "replace")

    def belege(self) -> list[dict]:
        p = self.lauf / "port_suche-blockiert.jsonl"
        if not p.is_file():
            return []
        return [json.loads(z) for z in p.read_text(encoding="utf-8").splitlines()
                if z.strip()]

    def test_original_aufruf_wird_abgelehnt(self):
        aus, _ = self.hook(ORIGINAL)
        antwort = json.loads(aus)
        hoe = antwort["hookSpecificOutput"]
        self.assertEqual(hoe["hookEventName"], "PreToolUse")
        self.assertEqual(hoe["permissionDecision"], "deny")
        self.assertIn("port_suche ungekuerzt mit --schreiben ausfuehren und die Datei "
                      "lesen (R13az, Aussensicht B289 Befund 4)",
                      hoe["permissionDecisionReason"])

    def test_jede_wiederholung_wird_wieder_abgelehnt(self):
        """Anders als die alte Preflight-Marke: die Sperre ist KEIN Einmal-Schalter."""
        for i in range(3):
            aus, _ = self.hook(ORIGINAL)
            self.assertEqual(json.loads(aus)["hookSpecificOutput"]["permissionDecision"],
                             "deny", f"Versuch {i + 1}")
        self.assertEqual(len(self.belege()), 3, "je Stopp eine Zeile")
        self.assertEqual([b["grund"] for b in self.belege()],
                         ["pipe-gekuerzt"] * 3)

    def test_ungekuerzter_aufruf_geht_durch(self):
        for c in ("python scripts/port_suche.py 80008828",
                  "python scripts/port_suche.py 80008828 --schreiben",
                  "Select-String -Path scripts/port_suche.py -Pattern 'PORT-TREFFER'"):
            with self.subTest(command=c):
                aus, _ = self.hook(c)
                self.assertEqual(aus.strip(), "", "kein deny, keine Behauptung")
        self.assertEqual(self.belege(), [], "nichts geblockt, nichts belegt")

    def test_ohne_run_verzeichnis_keine_behauptung(self):
        args = [sys.executable, str(ROOT / "tools" / "batch_uhr.py"),
                "--state", str(self.state), "--umschalt", "80", "--pre"]
        daten = {"hook_event_name": "PreToolUse", "tool_name": "PowerShell",
                 "tool_input": {"command": ORIGINAL}}
        p = subprocess.run(args, input=json.dumps(daten).encode("utf-8"),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        self.assertEqual(p.returncode, 0)
        hoe = json.loads(p.stdout.decode("utf-8"))["hookSpecificOutput"]
        self.assertEqual(hoe["permissionDecision"], "deny")
        self.assertFalse((self.lauf / "port_suche-blockiert.jsonl").is_file())


# ---------------------------------------------------------------- 3) Verdrahtung
class TestVerdrahtung(unittest.TestCase):
    def test_belegdatei_zaehlt_zu_den_laufbelegen(self):
        self.assertIn("port_suche-blockiert.jsonl", worker.LAUF_BELEGE)

    def test_hook_einstellung_haengt_den_pretooluse_zweig(self):
        ziel = Path(ROOT) / "tests" / "_tmp_r13bw11_draht"
        shutil.rmtree(ziel, ignore_errors=True)
        rd = ensure_dir(ziel / "runs" / "b999")
        try:
            cfg = load_config()
            cfg.data["paths"]["root"] = str(ziel)
            pfad = worker.write_worker_hooks(cfg, rd, ziel / "state" / "run.json")
            self.assertTrue(pfad, "ohne Einstellungsdatei gibt es keinen Hook")
            daten = json.loads(Path(pfad).read_text(encoding="utf-8"))
            args = daten["hooks"]["PreToolUse"][0]["hooks"][0]["args"]
            self.assertIn("--pre", args)
        finally:
            shutil.rmtree(ziel, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
