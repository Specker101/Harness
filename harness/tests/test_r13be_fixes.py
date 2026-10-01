"""Tests fuer R13be-1 (01.10.2026): Preflight-Zaehler aus dem Mitschnitt.

**Der Befund.** `preflight_laeufe` kam aus `runs/b<N>/preflight-aufrufe.jsonl`, das der
PostToolUse-Hook `tools/batch_uhr.py` schreibt. Der Hook laeuft aber **nur nach
erfolgreichen** Werkzeugaufrufen. Ein Preflight, der Befunde findet, endet mit Exit 2 -
das ist `is_error=true`, der Hook laeuft nicht, die Zeile fehlt.

Gemessen ueber B220-B228 (`docs/_r13be_belege.md`): Zaehldatei-Zeilen = Starts minus
Aufrufe mit `is_error` (17 - 6 = 11). **B228** hatte zwei echte Starts
(`22:44:54`, `23:00:58`, beide `is_error=true`) und `preflight_laeufe=0` - die Zaehldatei
fehlt vollstaendig, obwohl `analysis/_preflight_228.txt` vorliegt.

**Die Aenderung.** Die Zahl kommt jetzt aus dem **Mitschnitt** (`stream.jsonl` und
`stream-forts*.jsonl`, Regel `streamjson.ist_preflight_aufruf` - dieselbe wie beim Hook).
Der Hook-Zaehler bleibt als **Kontrolle** daneben und wird in den Review-Fakten als
`PREFLIGHT-AUFRUFE: n (Quelle Stream), Hook-Zaehler: m` genannt; bei Abweichung mit
HINWEIS.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import stand, streamjson, worker                             # noqa: E402
from hx.config import load_config                                    # noqa: E402
from hx.util import Log, ensure_dir, write_text_atomic                # noqa: E402

# 2026-10-01 00:44 UTC = 62,9 min nach dem Start 2026-09-30T21:42:34+00:00
START = "2026-09-30T21:42:34+00:00"
BEFEHL = "python -u scripts/preflight.py before *> analysis/_preflight_228.txt"


def aufruf(kennung: str, ts: str, befehl: str = BEFEHL) -> str:
    """Eine Mitschnitt-Zeile mit einem Werkzeugaufruf."""
    return json.dumps({"type": "assistant", "timestamp": ts,
                       "message": {"role": "assistant", "content": [
                           {"type": "tool_use", "id": kennung, "name": "PowerShell",
                            "input": {"command": befehl, "description": "Preflight"}}]}})


def ergebnis(kennung: str, ts: str, fehler: bool) -> str:
    """Eine Mitschnitt-Zeile mit dem Ergebnis dazu (`is_error` = Exit != 0)."""
    return json.dumps({"type": "user", "timestamp": ts,
                       "message": {"role": "user", "content": [
                           {"type": "tool_result", "tool_use_id": kennung,
                            "is_error": bool(fehler),
                            "content": "Exit code 2" if fehler else "exit=0"}]}})


class Basis(unittest.TestCase):
    """Wegwerf-Root mit `runs/b999`; `cfg` zeigt darauf."""

    BATCH = 999

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13be"
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "harness")
        self.rd = ensure_dir(self.root / "runs" / f"b{self.BATCH:03d}")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(ensure_dir(self.tmp / "decomp"))
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["telegram"]["allowlist_user_ids"] = []
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def mitschnitt(self, *zeilen: str, datei: str = "stream.jsonl") -> None:
        write_text_atomic(self.rd / datei, "\n".join(zeilen) + "\n")

    def hook_datei(self, *zeilen: dict) -> None:
        write_text_atomic(self.rd / "preflight-aufrufe.jsonl",
                          "\n".join(json.dumps(z) for z in zeilen) + "\n")

    def result_json(self, wand_s: float = 5071.0) -> None:
        write_text_atomic(self.rd / "result.json", json.dumps(
            {"batch": self.BATCH, "duration_s": wand_s,
             "finished_at": "2026-09-30T23:07:05+00:00"}))


# ------------------------------------------------------------------ 1) Zaehlen
class TestMitschnittZaehler(Basis):
    def test_fehlgeschlagener_aufruf_zaehlt_mit(self):
        """Der Kern: Exit 2 (`is_error`) ist ein Start und wird gezaehlt."""
        self.mitschnitt(aufruf("tu1", "2026-09-30T22:44:54+00:00"),
                        ergebnis("tu1", "2026-09-30T22:45:00+00:00", True),
                        aufruf("tu2", "2026-09-30T23:00:58+00:00"),
                        ergebnis("tu2", "2026-09-30T23:07:00+00:00", True))
        d = stand.mitschnitt_preflight_aufrufe(self.cfg, self.BATCH,
                                               start_zeit=stand._iso_zeit(START))
        self.assertEqual(d["laeufe"], 2)
        self.assertEqual([a["is_error"] for a in d["aufrufe"]], [True, True])
        self.assertEqual([a["min"] for a in d["aufrufe"]], [62.3, 78.4])

    def test_erwaehnung_zaehlt_nicht(self):
        """`Select-String -Path scripts/preflight.py` startet nichts (Regel R13ao)."""
        self.mitschnitt(aufruf("tu1", "2026-09-30T21:44:24+00:00",
                               'Select-String -Path "scripts\\preflight.py" -Pattern x'))
        d = stand.mitschnitt_preflight_aufrufe(self.cfg, self.BATCH,
                                               start_zeit=stand._iso_zeit(START))
        self.assertEqual(d["laeufe"], 0)

    def test_start_kommt_aus_result_json(self):
        """Ohne `start_zeit` wird sie aus `finished_at - duration_s` abgeleitet."""
        self.result_json(wand_s=5071.0)          # 23:07:05 - 84,5 min = 21:42:34
        self.mitschnitt(aufruf("tu1", "2026-09-30T23:00:58+00:00"))
        d = stand.mitschnitt_preflight_aufrufe(self.cfg, self.BATCH)
        self.assertEqual(d["start"][:19], START[:19])
        self.assertEqual(d["aufrufe"][0]["min"], 78.4)

    def test_fortsetzung_zaehlt_mit(self):
        """Ein Start in `stream-forts1.jsonl` gehoert zum selben Batch."""
        self.mitschnitt(aufruf("tu1", "2026-09-30T21:50:00+00:00"))
        self.mitschnitt(aufruf("tu2", "2026-09-30T22:30:00+00:00"),
                        datei="stream-forts1.jsonl")
        d = stand.mitschnitt_preflight_aufrufe(self.cfg, self.BATCH,
                                               start_zeit=stand._iso_zeit(START))
        self.assertEqual(d["laeufe"], 2)
        self.assertEqual(d["dateien"], ["stream.jsonl", "stream-forts1.jsonl"])

    def test_frueh_braucht_schwelle_und_nachrueckliste(self):
        self.mitschnitt(aufruf("tu1", "2026-09-30T22:20:00+00:00"),   # 37,4 min
                        aufruf("tu2", "2026-09-30T23:00:00+00:00"))   # 77,4 min
        ohne = stand.mitschnitt_preflight_aufrufe(self.cfg, self.BATCH,
                                                  start_zeit=stand._iso_zeit(START),
                                                  umschalt_min=75.0)
        self.assertEqual((ohne["laeufe"], ohne["frueh"]), (2, 0))
        mit = stand.mitschnitt_preflight_aufrufe(self.cfg, self.BATCH,
                                                 start_zeit=stand._iso_zeit(START),
                                                 umschalt_min=75.0, nachrueckliste=True)
        self.assertEqual((mit["laeufe"], mit["frueh"]), (2, 1))


# --------------------------------------------------- 2) Kontrolle gegen den Hook
class TestKontrollzeile(Basis):
    def test_abweichung_wird_markiert(self):
        """Der B228-Fall: Mitschnitt 2, Hook 0 -> HINWEIS in der Zeile."""
        self.mitschnitt(aufruf("tu1", "2026-09-30T22:44:54+00:00"),
                        ergebnis("tu1", "2026-09-30T22:45:00+00:00", True),
                        aufruf("tu2", "2026-09-30T23:00:58+00:00"))
        self.result_json()
        zeile = stand.preflight_zaehler_zeile(self.cfg, self.BATCH)[0]
        self.assertIn("PREFLIGHT-AUFRUFE: 2 (Quelle Stream), Hook-Zaehler: 0", zeile)
        self.assertIn("HINWEIS", zeile)
        self.assertIn("der Hook zaehlt nur erfolgreiche Aufrufe", zeile)

    def test_gleiche_zahlen_ohne_hinweis(self):
        self.mitschnitt(aufruf("tu1", "2026-09-30T22:44:54+00:00"))
        self.hook_datei({"ts": "2026-09-30T22:44:54+00:00", "min": 62.3, "frueh": True})
        self.result_json()
        zeile = stand.preflight_zaehler_zeile(self.cfg, self.BATCH)[0]
        self.assertIn("PREFLIGHT-AUFRUFE: 1 (Quelle Stream), Hook-Zaehler: 1", zeile)
        self.assertNotIn("HINWEIS", zeile)

    def test_ohne_mitschnitt_gilt_der_hook(self):
        """Aeltere Batches ohne `stream.jsonl` bleiben bei der Hook-Zahl."""
        self.hook_datei({"ts": "2026-09-30T21:00:00+00:00", "min": 20.0, "frueh": True},
                        {"ts": "2026-09-30T22:00:00+00:00", "min": 95.0, "frueh": False})
        zeile = stand.preflight_zaehler_zeile(self.cfg, self.BATCH)[0]
        self.assertIn("PREFLIGHT-AUFRUFE: 2 (Quelle Hook), Hook-Zaehler: 2", zeile)
        self.assertIn("2 Aufruf(e) im Mitschnitt (davon 1 zu frueh)", zeile)


# ------------------------------------------------------------ 3) Rotprobe (B228)
class TestRotprobe(Basis):
    """**Rotprobe**: der Fall, der den alten Zaehler widerlegt.

    Nachgebaut ist B228: zwei echte Starts, beide mit `is_error=true` (Exit 2 =
    „BEFORE MIT BEFUNDEN"), **keine** Hook-Zaehldatei. Der alte Weg (Hook) meldet 0 -
    rot; der neue Weg (Mitschnitt) meldet 2 - gruen.
    """

    def aufbau(self) -> None:
        self.mitschnitt(aufruf("tu1", "2026-09-30T22:44:54+00:00"),
                        ergebnis("tu1", "2026-09-30T22:45:00+00:00", True),
                        aufruf("tu2", "2026-09-30T23:00:58+00:00"),
                        ergebnis("tu2", "2026-09-30T23:07:00+00:00", True))
        self.result_json()

    def test_alte_quelle_ist_null(self):
        """Der Hook hat nichts gesehen - genau das war der Befund."""
        self.aufbau()
        self.assertFalse((self.rd / "preflight-aufrufe.jsonl").exists())
        self.assertEqual(worker.zaehle_preflight_aufrufe(self.rd), (0, 0))

    def test_neue_quelle_ist_zwei(self):
        self.aufbau()
        d = stand.mitschnitt_preflight_aufrufe(self.cfg, self.BATCH)
        self.assertEqual(d["laeufe"], 2)
        self.assertEqual(stand.preflight_zaehler_zeile(self.cfg, self.BATCH)[0].count("2 "),
                         2, "2 als Aufrufzahl und 2 im Mitschnitt-Satz")

    def test_result_json_nennt_beide_quellen(self):
        """Die Nutzlast traegt Mitschnitt, Hook und die Gesamtzahl."""
        self.aufbau()
        import inspect
        quelle = inspect.getsource(worker._finish_run)
        self.assertIn('hook_laeufe, hook_frueh = zaehle_preflight_aufrufe(rd)', quelle)
        self.assertIn('stand.mitschnitt_preflight_aufrufe(', quelle)
        self.assertIn('"preflight_laeufe_hook": int(hook_laeufe)', quelle)
        self.assertIn('"preflight_aufrufe": list(mitschnitt["aufrufe"])', quelle)
        self.assertIn('preflight_laeufe = max(int(mitschnitt["laeufe"]), '
                      'int(hook_laeufe))', quelle)
        self.assertIn('preflight_frueh = max(int(mitschnitt["frueh"]), '
                      'int(hook_frueh))', quelle)
        self.assertIn('"Preflight-Zaehler: Hook und Mitschnitt weichen ab"', quelle)

    def test_gesamt_ist_das_maximum(self):
        """Die Gesamtzahl wird nie kleiner als eine der Quellen."""
        self.aufbau()
        # Mitschnitt 2, Hook 0, ein archivierter Fehllauf -> 2 (nicht 3!)
        archiv = ensure_dir(Path(self.cfg.decomp) / "analysis" / f"_m{self.BATCH}")
        write_text_atomic(archiv / f"_preflight_{self.BATCH}_fehllauf1.txt", "# x\n")
        zeile = stand.preflight_zaehler_zeile(self.cfg, self.BATCH)[0]
        self.assertIn("1 Fehllauf/Fehllaeufe archiviert", zeile)
        self.assertIn("im Mitschnitt enthalten", zeile)
        self.assertNotIn("-> 3 Laeufe", zeile)


# --------------------------------------------------------------- 4) Verdrahtung
class TestVerdrahtung(unittest.TestCase):
    def test_review_fakten_geben_hook_und_mitschnitt_mit(self):
        import inspect
        from hx.orchestrator import Orchestrator
        quelle = inspect.getsource(Orchestrator.harness_facts)
        self.assertIn("standmod.preflight_zaehler_zeile(", quelle)
        self.assertIn("hook=res.get(\"preflight_laeufe_hook\")", quelle)
        self.assertIn("mitschnitt=res.get(\"preflight_laeufe\")", quelle)

    def test_regel_bleibt_am_mitschnitt(self):
        """Die Fortsetzungsregel las schon immer `stats.tools` - nicht die Zaehldatei."""
        import inspect
        quelle = inspect.getsource(worker.preflight_gestartet)
        self.assertIn("streamjson.ist_preflight_aufruf", quelle)


if __name__ == "__main__":
    unittest.main()
