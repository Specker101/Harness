"""Tests fuer R13h: Laufzeit messen und den Leser-Thread entlasten (2026-09-26).

Ausgangsfrage des Nutzers: Warum dauern manche Batches Stunden bei wenigen Tokens?
Die Antwort steht in den Mitschnitten (Werkzeuge statt Modell) - diese Tests sichern
die Werkzeuge, die das messen, und die eine Optimierung, die dabei herauskam:

* `TaktGeber`: Summen und Kosten NICHT je Zeile rechnen. Gemessen kostete
  `cost_usd()` ~1 ms; bei 156.493 Zeilen waren das ~156 s Rechenzeit im Leser-Thread
  (Beleg `docs/_kosten_takt_messung.txt`, 85 s -> 1,2 s im Nachspiel).
* `warte_sekunden`: erkennt reine Wartebefehle (`Start-Sleep`, Poll-Schleifen). In
  einem echten Batch steckten so 1993 s (42 % der Laufzeit).
* `laufzeit_profil`: Werkzeugzeit/Modellzeit/Wartezeit aus den Zeitstempeln.
"""

from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import streamjson                                            # noqa: E402
from hx.config import load_config                                    # noqa: E402
from hx.orchestrator import Orchestrator                             # noqa: E402
from hx.util import Log, ensure_dir                                  # noqa: E402


def ereignis(ts: str, bloecke: list) -> str:
    return json.dumps({"type": "assistant", "timestamp": ts,
                       "message": {"id": "m" + ts, "model": "m", "usage": {},
                                   "content": bloecke}}, ensure_ascii=False)


def ergebnis(ts: str, tid: str) -> str:
    return json.dumps({"type": "user", "timestamp": ts, "message": {"content": [
        {"type": "tool_result", "tool_use_id": tid, "content": "ok"}]}},
        ensure_ascii=False)


# ------------------------------------------------------------- Takt der Auswertung
class TestTaktGeber(unittest.TestCase):
    def test_erste_zeile_rechnet_immer(self):
        t = streamjson.TaktGeber(2.0)
        self.assertTrue(t.faellig(100.0))

    def test_innen_kein_zweites_mal(self):
        t = streamjson.TaktGeber(2.0)
        self.assertTrue(t.faellig(100.0))
        self.assertFalse(t.faellig(100.5))
        self.assertFalse(t.faellig(101.9))

    def test_nach_dem_intervall_wieder(self):
        t = streamjson.TaktGeber(2.0)
        t.faellig(100.0)
        self.assertTrue(t.faellig(102.0))

    def test_intervall_null_rechnet_immer(self):
        t = streamjson.TaktGeber(0)
        self.assertTrue(t.faellig(1.0))
        self.assertTrue(t.faellig(1.0))

    def test_kostet_ohne_rechnung(self):
        """Die Kernaussage: 1000 Zeilen in kurzer Zeit => EINE Rechnung."""
        t = streamjson.TaktGeber(2.0)
        self.assertEqual(sum(1 for i in range(1000) if t.faellig(50.0 + i * 0.001)), 1)


# -------------------------------------------------------------- Wartezeit erkennen
class TestWartezeit(unittest.TestCase):
    def test_formen(self):
        self.assertEqual(streamjson.warte_sekunden("Start-Sleep -Seconds 300"), 300)
        self.assertEqual(streamjson.warte_sekunden("Start-Sleep 45"), 45)
        self.assertEqual(streamjson.warte_sekunden("sleep 60"), 60)
        self.assertEqual(streamjson.warte_sekunden("Start-Sleep -Milliseconds 500"), 0.5)

    def test_poll_schleife_zaehlt_die_schritte(self):
        cmd = ("for ($i=0; $i -lt 20; $i++) { if (Test-Path x.txt) { break }; "
               "Start-Sleep -Seconds 30 }")
        self.assertEqual(streamjson.warte_sekunden(cmd), 600)

    def test_ohne_sleep_keine_wartezeit(self):
        self.assertEqual(streamjson.warte_sekunden("Get-ChildItem analysis"), 0)
        self.assertEqual(streamjson.warte_sekunden(""), 0)
        self.assertEqual(streamjson.warte_sekunden(None), 0)

    def test_hintergrundlauf_ist_keine_wartezeit(self):
        cmd = "Start-Process -NoNewWindow -FilePath python -ArgumentList '-u','x.py'"
        self.assertEqual(streamjson.warte_sekunden(cmd), 0)


# ---------------------------------------------------------------- Laufzeit-Profil
class TestLaufzeitProfil(unittest.TestCase):
    def _profil(self) -> dict:
        s = streamjson.StreamStats()
        s.feed(ereignis("2026-09-26T10:00:00Z",
                        [{"type": "tool_use", "id": "t1", "name": "PowerShell",
                          "input": {"command": "python -u lang.py"}}]))
        # 100 s spaeter fertig
        s.feed(ergebnis("2026-09-26T10:01:40Z", "t1"))
        s.feed(ereignis("2026-09-26T10:02:00Z", [{"type": "text", "text": "weiter"}]))
        return s.laufzeit_profil()

    def test_werkzeugzeit_und_spanne(self):
        p = self._profil()
        self.assertEqual(p["spanne_s"], 120.0)
        self.assertEqual(p["werkzeug_s"], 100.0)
        self.assertEqual(p["modell_s"], 20.0)

    def test_langsamster_aufruf_mit_kurzbeschreibung(self):
        p = self._profil()
        self.assertEqual(p["langsamste"][0]["dauer_s"], 100.0)
        self.assertIn("lang.py", p["langsamste"][0]["kurz"])

    def test_hoechstens_fuenf_langsamste(self):
        s = streamjson.StreamStats()
        for i in range(7):
            s.feed(ereignis(f"2026-09-26T10:0{i}:00Z",
                            [{"type": "tool_use", "id": f"t{i}", "name": "Read",
                              "input": {"file_path": f"a{i}.txt"}}]))
            s.feed(ergebnis(f"2026-09-26T10:0{i}:30Z", f"t{i}"))
        p = s.laufzeit_profil()
        self.assertEqual(len(p["langsamste"]), 5)

    def test_wartezeit_im_profil(self):
        s = streamjson.StreamStats()
        s.feed(ereignis("2026-09-26T10:00:00Z",
                        [{"type": "tool_use", "id": "t1", "name": "PowerShell",
                          "input": {"command": "Start-Sleep -Seconds 300; Get-ChildItem x"}}]))
        s.feed(ergebnis("2026-09-26T10:05:00Z", "t1"))
        self.assertEqual(s.laufzeit_profil()["warte_s"], 300)

    def test_ohne_zeitstempel_kein_profil(self):
        s = streamjson.StreamStats()
        s.feed(json.dumps({"type": "assistant", "message": {
            "id": "m", "model": "m", "usage": {},
            "content": [{"type": "tool_use", "id": "t", "name": "Read",
                         "input": {"file_path": "a"}}]}}))
        self.assertEqual(s.laufzeit_profil()["spanne_s"], 0.0)


# --------------------------------------------------- Anzeige im Messdatenblock
class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__file__).resolve().parent / "_tmp_r13h"
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

    def orch(self) -> Orchestrator:
        o = Orchestrator(self.cfg, self.log, mock=True,
                         state_file=self.tmp / "harness" / "state" / "run.json")
        o.say = lambda *a, **k: None
        return o


class TestAnzeige(Base):
    def test_zeile_ohne_messung(self):
        self.assertIn("nicht gemessen", self.orch().laufzeit_zeile({"stats": {}}))

    def test_zeile_mit_profil(self):
        zeile = self.orch().laufzeit_zeile({"stats": {"laufzeit": {
            "spanne_s": 4764.0, "werkzeug_s": 3315.0, "modell_s": 1449.0,
            "warte_s": 1993.0,
            "langsamste": [{"name": "PowerShell", "kurz": "python -u lang.py",
                            "dauer_s": 602.0}]}}})
        self.assertIn("Werkzeuge 3315 s (70 %)", zeile)
        self.assertIn("Modell 1449 s", zeile)
        self.assertIn("reines Warten 1993 s", zeile)
        self.assertIn("lang.py 602 s", zeile)

    def test_zeile_im_messdatenblock(self):
        rd = ensure_dir(Path(self.cfg.sub("runs")) / "b176")
        (rd / "result.json").write_text(json.dumps({
            "batch": 176, "rc": 0, "profile": "ghidra-read", "program": "/x.bin",
            "cost_usd": 0.5, "cost_naive_usd": 0.5,
            "stats": {"requests": 10, "input_miss": 1, "cache_read": 2,
                      "cache_creation": 3, "output": 4, "tool_errors": [],
                      "laufzeit": {"spanne_s": 100.0, "werkzeug_s": 80.0,
                                   "modell_s": 20.0, "warte_s": 30.0,
                                   "langsamste": []}},
            "laufzeit": {"spanne_s": 100.0, "werkzeug_s": 80.0, "modell_s": 20.0,
                         "warte_s": 30.0, "langsamste": []},
        }), encoding="utf-8")
        o = self.orch()
        o.state.data["last_batch_number"] = 176
        text = o.harness_facts(176, ziel=self.tmp / "out")
        self.assertIn("- Laufzeit-Profil: Werkzeuge 80 s (80 %)", text)
        self.assertIn("reines Warten 30 s", text)

    def test_worker_vorspann_warn_vor_grossen_schlafschritten(self):
        from hx import worker
        pre = worker.WORKER_PREAMBLE
        self.assertIn("RECHENZEIT", pre)
        self.assertIn("parallel", pre)
        self.assertIn("Start-Sleep -Seconds 300", pre)


class TestTaktThread(unittest.TestCase):
    """Der Takt-Thread: der Harness muss auch bei stillem Mitschnitt lebendig bleiben."""

    def test_taktet_auch_ohne_zeile(self):
        import time
        rufe = []
        t = streamjson.TaktThread(lambda: rufe.append(time.monotonic()), 0.15).start()
        try:
            time.sleep(0.55)
        finally:
            t.stop()
        self.assertGreaterEqual(len(rufe), 2, "der Takt kam nicht durch")
        nach = len(rufe)
        time.sleep(0.25)
        self.assertEqual(len(rufe), nach, "der Thread laeuft nach stop() weiter")
        self.assertFalse(t._faden.is_alive())

    def test_fehler_im_takt_beendet_den_thread_nicht(self):
        import time
        zaehler = []

        def takt():
            zaehler.append(1)
            if len(zaehler) == 1:
                raise RuntimeError("erster Schlag scheitert")

        t = streamjson.TaktThread(takt, 0.15).start()
        try:
            time.sleep(0.55)
        finally:
            t.stop()
        self.assertGreaterEqual(len(zaehler), 2)

    def test_aufrufe_werden_gezaehlt(self):
        import time
        t = streamjson.TaktThread(lambda: None, 0.15).start()
        try:
            time.sleep(0.4)
        finally:
            t.stop()
        self.assertGreaterEqual(t.aufrufe, 2)


if __name__ == "__main__":
    unittest.main()
