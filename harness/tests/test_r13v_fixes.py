"""Tests fuer R13v (2026-09-28): Warteschleifen technisch verhindern.

Auftrag (Nutzer): "In B207 gingen 1390 s in Abfrageschleifen verloren, obwohl Vorspann und
Instruktion das verbieten ... Dann einen Mechanismus vorschlagen UND bauen, der das
technisch verhindert statt es nur zu verbieten ... Wichtig: der Worker braucht dann einen
erlaubten Weg fuer lange Laeufe (synchron mit hoher Zeitgrenze oder Wait-Process -Timeout)
- den im Vorspann klar benennen."

Gemessen (Belege `docs/_r13v_beleg_b207.txt`):
  * `runs/b207/stream.jsonl:76873` - `for ($i=0; $i -lt 40; …) { … Start-Sleep -Seconds 20 }`
    auf PID 4996 → **601,9 s**
  * `runs/b207/stream.jsonl:77152` - dieselbe Schleife, 28 Schritte → **481,8 s**
  * `runs/b207/stream.jsonl:76897` - Werkzeug: "Command did not complete within its 600s
    timeout and was moved to the background" (deshalb wurde ueberhaupt gepollt)
  * `runs/b207/stream.jsonl:66903` - `Start-Process … c_kopf.py mutalle` (PID 4996)

Alles im Attrappenbetrieb: kein Netz, keine API-Kosten, kein Ghidra.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import envs, streamjson, worker                       # noqa: E402
from hx.config import load_config                             # noqa: E402

POLL40 = ("cd \"g:\\Silent Scope Decomp\"; for ($i=0; $i -lt 40; $i++) "
          "{ if (-not (Get-Process -Id 4996 -ErrorAction SilentlyContinue)) { break }; "
          "Start-Sleep -Seconds 20 }; \"fertig\"")
POLL28 = ("for ($i=0; $i -lt 28; $i++) { if (-not (Get-Process -Id 4996 "
          "-ErrorAction SilentlyContinue)) { break }; Start-Sleep -Seconds 20 }")
ERLAUBT = ("$t=Get-Date; python -u scripts/c_kopf.py vergl alle *> "
           "analysis\\_m207\\_vergl_alle.txt; \"exit=$LASTEXITCODE dauer \" + "
           "((Get-Date)-$t).TotalSeconds")
WAITPROC = ("$p = Start-Process -FilePath python -ArgumentList '-u','scripts/c_kopf.py','mutalle' "
            "-PassThru; Wait-Process -Id $p.Id -Timeout 480; Get-Content "
            "analysis\\_m207\\_c_kopf_mutation.txt -Tail 5")


class TestMuster(unittest.TestCase):
    def test_pollschleifen_werden_erkannt(self):
        for befehl in (POLL40, POLL28):
            grund = streamjson.warte_muster(befehl)
            self.assertIsNotNone(grund, befehl[:60])
            self.assertIn("Abfrageschleife", grund)

    def test_fester_schlaf_ab_30s(self):
        self.assertIsNotNone(streamjson.warte_muster("Start-Sleep -Seconds 30"))
        self.assertIsNotNone(streamjson.warte_muster("Start-Sleep -Seconds 300"))
        self.assertIsNone(streamjson.warte_muster("Start-Sleep -Seconds 5"))

    def test_erlaubter_weg_ist_erlaubt(self):
        for befehl in (ERLAUBT, WAITPROC,
                       "python -u scripts/preflight.py before *> analysis\\_preflight_207.txt",
                       "Start-Process -FilePath python -ArgumentList 'x' -Wait"):
            self.assertIsNone(streamjson.warte_muster(befehl), befehl[:60])

    def test_schleife_mit_prozessabfrage_ohne_schlaf(self):
        grund = streamjson.warte_muster("for ($i=0; $i -lt 10; $i++) { Get-Process -Id 4996 }")
        self.assertIsNotNone(grund)

    def test_wartezeit_wird_mit_der_schleife_multipliziert(self):
        # 40 Schritte x 20 s = 800 s (Obergrenze) - so rechnet auch R13h.
        self.assertAlmostEqual(streamjson.warte_sekunden(POLL40), 800.0, places=1)

    def test_alias_und_fremdschlaf_werden_gemessen(self):
        """R13v2: Formen, die die Sperre NICHT faengt, muessen messbar bleiben.

        Nachgemessen am 2026-09-28 mit echtem claude-Lauf
        (`tools/r13v_sperrprobe.py`, `docs/_r13v_sperrprobe.txt`):
          * `PowerShell(Start-Sleep*)` sperrt `Start-Sleep` an JEDER Stelle und loest
            den Alias `sleep` auf - die Schleife ist also schon gesperrt,
          * `[Threading.Thread]::Sleep(2000)` ist NICHT gesperrt.
        Damit der Waechter auch dort abbricht statt nur zu melden, muss die Wartezeit
        geschaetzt werden - vorher stand hier 0,0 s und der Fund blieb ein Alarm.
        """
        alias = ("for ($i=0; $i -lt 40; $i++) { Get-Process -Id 4996; "
                 "sleep -Seconds 20 }")
        self.assertAlmostEqual(streamjson.warte_sekunden(alias), 800.0, places=1)
        thread = ("for ($i=0; $i -lt 40; $i++) { Get-Process -Id 4996; "
                  "[Threading.Thread]::Sleep(20000) }")
        self.assertIsNotNone(streamjson.warte_muster(thread))
        self.assertAlmostEqual(streamjson.warte_sekunden(thread), 800.0, places=1)
        self.assertEqual(streamjson.warte_entscheidung(
            1, streamjson.warte_sekunden(thread),
            streamjson.warte_sekunden(thread))[0], "kill")
        # Millisekunden-Schreibweisen ohne Schleife
        self.assertAlmostEqual(
            streamjson.warte_sekunden("[Threading.Thread]::Sleep(2500)"), 2.5, places=1)

    def test_blosse_erwaehnung_ist_keine_warteschleife(self):
        # Der Befehl nennt `Start-Sleep` nur in einem Text - kein Schlaf, keine Schleife.
        self.assertIsNone(streamjson.warte_muster('Write-Output "Start-Sleep -Seconds 3"'))
        self.assertIsNone(streamjson.warte_muster("Select-String -Pattern 'Start-Sleep' -Path x"))


class TestEntscheidung(unittest.TestCase):
    def test_erster_fund_nur_alarm(self):
        art, text = streamjson.warte_entscheidung(1, 20.0, 20.0)
        self.assertEqual(art, "alarm")
        self.assertIn("Warteschleife", text)

    def test_summe_ueber_grenze_bricht_ab(self):
        art, text = streamjson.warte_entscheidung(2, 800.0, 400.0)
        self.assertEqual(art, "kill")
        self.assertIn("300", text)

    def test_einzelner_langer_aufruf_bricht_ab(self):
        art, _ = streamjson.warte_entscheidung(1, 400.0, 400.0)
        self.assertEqual(art, "kill")


class TestStatsUndFakten(unittest.TestCase):
    def _feed(self, *befehle: str) -> streamjson.StreamStats:
        st = streamjson.StreamStats()
        for i, b in enumerate(befehle):
            ev = {"type": "assistant", "message": {
                "id": f"m{i}", "model": "deepseek-flash[1m]",
                "content": [{"type": "tool_use", "id": f"t{i}", "name": "PowerShell",
                             "input": {"command": b}}]}}
            st.feed(json.dumps(ev))
        return st

    def test_mitschnitt_zaehlt_die_warteschleifen(self):
        st = self._feed(POLL40, ERLAUBT, WAITPROC, POLL28)
        self.assertEqual(len(st.warteschleifen), 2)
        self.assertEqual(st.warteschleifen[0]["werkzeug"], "PowerShell")
        self.assertIn("Abfrageschleife", st.warteschleifen[0]["grund"])
        p = st.laufzeit_profil()
        self.assertEqual(p["warteschleifen"], 2)
        self.assertGreater(p["warteschleifen_s"], 1000.0)

    def test_nur_erlaubte_befehle_ergeben_null(self):
        st = self._feed(ERLAUBT, WAITPROC, WAITPROC)
        self.assertEqual(len(st.warteschleifen), 0)
        self.assertEqual(st.laufzeit_profil()["warteschleifen_s"], 0.0)


class TestSperrenUndVorspann(unittest.TestCase):
    def test_kommando_sperrt_das_warteprimitiv(self):
        cfg = load_config()
        from hx.profiles import load_profile
        p = load_profile(cfg.root, "none")
        cmd, _ = worker.build_command(cfg, p, Path(cfg.sub("runs")) / "b900", "sid")
        txt = " ".join(cmd)
        self.assertIn("PowerShell(Start-Sleep*)", txt)
        self.assertIn("Bash(sleep *)", txt)

    def test_worker_umgebung_hebt_die_zeitgrenze(self):
        import os
        env = envs.worker_env(load_config(), dict(os.environ), "token")
        self.assertEqual(env["BASH_DEFAULT_TIMEOUT_MS"], "600000")
        self.assertEqual(env["BASH_MAX_TIMEOUT_MS"], "600000")

    def test_vorspann_nennt_den_erlaubten_weg(self):
        v = worker.WORKER_PREAMBLE
        self.assertIn("Wait-Process -Id $p.Id -Timeout", v)
        self.assertIn("timeout", v)
        self.assertIn("Start-Sleep", v)
        self.assertIn("GESPERRT", v)
        # Der alte, irrefuehrende Rat darf NICHT mehr dastehen.
        self.assertNotIn("kurzem Schritt (10-20 s)", v)


class TestFaktenzeile(unittest.TestCase):
    """Die Warteschleifen muessen im Review sichtbar sein (R13v)."""

    def _zeile(self, p: dict) -> str:
        from hx.orchestrator import Orchestrator
        from hx.util import Log
        cfg = load_config()
        orch = Orchestrator.__new__(Orchestrator)          # nur die reine Formatierung
        orch.log = Log(Path(cfg.root) / "logs" / "_r13v_test.jsonl", echo=False)
        return Orchestrator.laufzeit_zeile(orch, {"stats": {"laufzeit": p}})

    def test_zeile_nennt_die_warteschleifen(self):
        zeile = self._zeile({"spanne_s": 2845.0, "werkzeug_s": 2057.0, "modell_s": 789.0,
                             "warte_s": 1390.0, "warteschleifen": 2,
                             "warteschleifen_s": 1282.0,
                             "langsamste": [{"name": "PowerShell", "kurz": "for ($i=0; ...)",
                                             "dauer_s": 601.9}]})
        self.assertIn("WARTESCHLEIFEN 2 Aufrufe / ~1282 s", zeile)
        self.assertIn("vermeidbar", zeile)

    def test_zeile_ohne_warteschleifen_bleibt_schlank(self):
        zeile = self._zeile({"spanne_s": 100.0, "werkzeug_s": 80.0, "modell_s": 20.0,
                             "warte_s": 0.0, "warteschleifen": 0, "warteschleifen_s": 0.0,
                             "langsamste": []})
        self.assertNotIn("WARTESCHLEIFEN", zeile)


if __name__ == "__main__":
    unittest.main()
