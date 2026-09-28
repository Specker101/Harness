"""Tests fuer R13ac3 (2026-09-29): Tiefenprobe der Aussensicht.

Nutzerauftrag: die Aussensicht prueft je Lauf **zusaetzlich** zur Stichprobe des neuesten
Batches EINEN **zufaellig** gewaehlten Batch aus den letzten zehn in der Tiefe
(Denkbloecke, Belege, Behauptungen des Abschlussberichts gegen die Rohdaten). Dieselbe
Nummer kommt erst wieder, wenn alle anderen des Fensters dran waren. Jeder Fund aus einem
aelteren Batch wird gegen den aktuellen Stand (HEAD, Anker, heutige Belege) geprueft;
behobene Sachen sind kein Befund, sondern eine Zeile
`geprueft: <Fund>, behoben in B<N> (Beleg)`.

Alles im Attrappenbetrieb (`mock=True`) unter `tests/_tmp_r13ac3`.
"""

from __future__ import annotations

import json
import random
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import aussensicht, state as st                            # noqa: E402
from hx.config import load_config                                  # noqa: E402
from hx.util import Log, ensure_dir, read_json, write_text_atomic   # noqa: E402


class Waehler:
    """Ein `zufall`-Ersatz, der immer DIESEN Batch waehlt (fuer deterministische Tests)."""

    def __init__(self, ziel: int):
        self.ziel = int(ziel)

    def choice(self, liste):
        assert self.ziel in liste, f"{self.ziel} nicht in {liste}"
        return self.ziel


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13ac3"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "harness")
        self.decomp = ensure_dir(self.tmp / "decomp")
        self.ana = ensure_dir(self.decomp / "analysis")
        write_text_atomic(self.ana / "r1b-workstream.md",
                          "# Workstream\n\n**Stand:** BATCH 200 (Beispiel).\n"
                          "**Fertig:** **(1)** etwas.\n**Naechster Schritt:** **(a)** weiter.\n"
                          "**Offene Entscheidung:** **(1)** nichts.\n")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.decomp)
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["paths"]["harness_home"] = str(self.tmp)
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)
        self.state = st.State(self.root / "state" / "run.json")
        self.state.data["batch"] = 200
        self.state.save()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def batch(self, n: int, mit_ergebnis: bool = True) -> Path:
        rd = ensure_dir(self.root / "runs" / f"b{n:03d}")
        if mit_ergebnis:
            write_text_atomic(rd / "result.json", json.dumps(
                {"batch": n, "rc": 0, "duration_s": 600.0, "stats": {"requests": 10}}))
        write_text_atomic(rd / "auftrag.md", f"=== AUFTRAG ===\nBatch {n}\n")
        write_text_atomic(rd / "antwort.md", f"## 1) Bericht zu Batch {n}\n")
        return rd

    def zieh(self, seed: int = 1) -> dict:
        return aussensicht.tiefenprobe_waehlen(self.cfg, zufall=random.Random(seed))


# ------------------------------------------------------------------ Auswahl
class TestZiehung(Basis):
    def test_fenster_ist_die_letzten_zehn_gelaufenen_batches(self):
        for n in range(191, 205):                      # B191..B204
            self.batch(n)
        self.assertEqual(aussensicht.gelaufene_batches(self.cfg), list(range(191, 205)))
        wahl = self.zieh()
        self.assertEqual(wahl["fenster"], list(range(195, 205)))
        self.assertIn(wahl["batch"], wahl["fenster"])
        self.assertFalse(wahl["neu_zyklus"])

    def test_gezogener_batch_kommt_erst_wieder_wenn_alle_dran_waren(self):
        for n in range(195, 205):
            self.batch(n)
        gesehen: list[int] = []
        for i in range(10):
            wahl = self.zieh(seed=i)
            self.assertNotIn(wahl["batch"], gesehen,
                             "derselbe Batch wurde zweimal gezogen")
            gesehen.append(wahl["batch"])
            self.assertFalse(wahl["neu_zyklus"])
            aussensicht.tiefenprobe_merken(self.cfg, wahl)
        self.assertEqual(sorted(gesehen), list(range(195, 205)))
        # Alle zehn waren dran -> der naechste Zug beginnt einen neuen Zyklus.
        wahl = self.zieh(seed=99)
        self.assertTrue(wahl["neu_zyklus"])
        self.assertEqual(wahl["gezogen"], [])
        self.assertIn(wahl["batch"], list(range(195, 205)))

    def test_kandidaten_schrumpfen_mit_jeder_ziehung(self):
        for n in range(195, 205):
            self.batch(n)
        wahl = self.zieh(seed=3)
        aussensicht.tiefenprobe_merken(self.cfg, wahl)
        danach = self.zieh(seed=4)
        self.assertEqual(len(danach["kandidaten"]), 9)
        self.assertNotIn(wahl["batch"], danach["kandidaten"])
        self.assertEqual(danach["gezogen"], [wahl["batch"]])

    def test_batch_ohne_ergebnis_zaehlt_nicht(self):
        self.batch(199, mit_ergebnis=False)
        for n in (198, 200):
            self.batch(n)
        self.assertEqual(aussensicht.gelaufene_batches(self.cfg), [198, 200])

    def test_ohne_lauf_keine_tiefenprobe(self):
        wahl = self.zieh()
        self.assertIsNone(wahl["batch"])
        self.assertIn("kein abgeschlossener Lauf", wahl["grund"])

    def test_batch_ausserhalb_des_fensters_wird_vergessen(self):
        for n in range(195, 205):
            self.batch(n)
        wahl = aussensicht.tiefenprobe_waehlen(self.cfg, zufall=Waehler(195))
        self.assertEqual(wahl["batch"], 195)
        aussensicht.tiefenprobe_merken(self.cfg, wahl)
        for n in range(205, 216):                      # Fenster rutscht auf B205..B214
            self.batch(n)
        stand = aussensicht.tiefenprobe_stand(self.cfg)
        self.assertNotIn(195, stand["gezogen"],
                         "ein Batch ausserhalb des Fensters gehoert nicht mehr zur Rotation")
        self.assertEqual(stand["gezogen"], [])

    def test_rotation_steht_im_register_und_ueberlebt_andere_schreibvorgaenge(self):
        for n in (199, 200):
            self.batch(n)
        wahl = self.zieh(seed=6)
        aussensicht.tiefenprobe_merken(self.cfg, wahl)
        # Ein Befund-Schreibvorgang darf die Rotation nicht loeschen.
        aussensicht.ledger_schreiben(self.cfg, [{"id": "M200-1", "status": "offen"}])
        daten = read_json(aussensicht.ledger_pfad(self.cfg), {})
        self.assertEqual(daten["tiefenprobe"]["gezogen"], [wahl["batch"]])
        self.assertEqual(daten["tiefenprobe"]["letzte"], wahl["batch"])
        self.assertEqual(len(daten["befunde"]), 1)


# -------------------------------------------------------------------- Prompt
class TestPrompt(Basis):
    def test_der_block_nennt_die_nummer_und_die_rohbelege(self):
        for n in range(195, 205):
            self.batch(n)
        wahl = self.zieh(seed=7)
        prompt = aussensicht.build_prompt(self.cfg, self.state, "Befehl /meta", tiefe=wahl)
        self.assertIn(f"=== TIEFENPROBE (Pflicht): BATCH {wahl['batch']} ===", prompt)
        for pfad in (f"runs/b{wahl['batch']:03d}/auftrag.md",
                     f"runs/b{wahl['batch']:03d}/antwort.md",
                     f"runs/b{wahl['batch']:03d}/result.json",
                     f"snapshots/b{wahl['batch']:03d}/reasoning.jsonl"):
            self.assertIn(pfad, prompt)
        self.assertIn(f"`TIEFENPROBE B{wahl['batch']}`", prompt)

    def test_die_pflichtregel_fuer_alte_funde_steht_im_prompt(self):
        self.batch(200)
        prompt = aussensicht.build_prompt(self.cfg, self.state, "Befehl /meta",
                                          tiefe=self.zieh(seed=8))
        self.assertIn("=== PFLICHT BEI FUNDEN AUS AELTEREN BATCHES (R13ac3) ===", prompt)
        self.assertIn("geprueft: <Fund in einem Satz>, behoben in B<N>", prompt)
        self.assertIn("Ist er bereits behoben?  -> KEIN Befund", prompt)

    def test_ohne_batch_sagt_der_block_das(self):
        prompt = aussensicht.build_prompt(self.cfg, self.state, "Befehl /meta",
                                          tiefe=self.zieh())
        self.assertIn("KEINE Tiefenprobe moeglich", prompt)

    def test_die_rollenanweisung_traegt_die_tiefenprobe(self):
        text = (Path(ROOT) / "prompts" / "aussensicht.md").read_text(encoding="utf-8")
        self.assertIn("Tiefenprobe", text)
        self.assertIn("behoben in B<N>", text)


# ------------------------------------------------------------------- Bericht
class TestBericht(Basis):
    def test_die_nummer_steht_im_bericht_auch_ohne_modell_nennung(self):
        for n in range(195, 205):
            self.batch(n)
        res = aussensicht.Ergebnis()
        res.rc, res.text, res.summary = 0, "<AUSSENSICHT>ohne Nummer</AUSSENSICHT>", "kurz"
        res.tiefe = self.zieh(seed=9)
        text = aussensicht.bericht(self.cfg, 200, "Befehl /meta", res, {}, [])
        self.assertIn(f"- Tiefenprobe: Batch {res.tiefe['batch']} aus dem Fenster B195..B204",
                      text)
        self.assertIn("## Zusammenfassung", text)

    def test_json_traegt_die_tiefenprobe(self):
        self.batch(200)
        res = aussensicht.Ergebnis()
        res.rc, res.text, res.summary = 0, "(leer)", "kurz"
        res.tiefe = self.zieh(seed=10)
        aussensicht.bericht_schreiben(self.cfg, 200, "Befehl /meta", res, {}, [])
        daten = read_json(aussensicht.json_pfad(self.cfg, 200), {})
        self.assertEqual(daten["tiefenprobe"]["batch"], res.tiefe["batch"])
        self.assertEqual(daten["tiefenprobe"]["fenster"], res.tiefe["fenster"])

    def test_ein_neuer_zyklus_wird_im_bericht_genannt(self):
        for n in range(195, 205):
            self.batch(n)
        for i in range(10):                              # alle zehn durchziehen
            aussensicht.tiefenprobe_merken(self.cfg, self.zieh(seed=i))
        res = aussensicht.Ergebnis()
        res.rc, res.text, res.summary = 0, "(leer)", "kurz"
        res.tiefe = self.zieh(seed=11)
        text = aussensicht.bericht(self.cfg, 200, "Befehl /meta", res, {}, [])
        self.assertIn("neuer Zyklus", text)


# ---------------------------------------------------------------- im Lauf
class TestImLauf(Basis):
    def test_mock_lauf_zieht_und_merkt(self):
        for n in range(195, 205):
            self.batch(n)
        res = aussensicht.run(self.cfg, self.log, self.state, "Befehl /meta",
                              mock=True, zufall=random.Random(12))
        self.assertIn(res.tiefe["batch"], res.tiefe["fenster"])
        stand = aussensicht.tiefenprobe_stand(self.cfg)
        self.assertEqual(stand["gezogen"], [res.tiefe["batch"]])
        self.assertIn(f"tiefenprobe=B{res.tiefe['batch']}", res.describe())

    def test_zweiter_lauf_zieht_einen_anderen(self):
        for n in range(195, 205):
            self.batch(n)
        erste = aussensicht.run(self.cfg, self.log, self.state, "Befehl /meta",
                                mock=True, zufall=random.Random(13))
        zweite = aussensicht.run(self.cfg, self.log, self.state, "Befehl /meta",
                                 mock=True, zufall=random.Random(14))
        self.assertNotEqual(erste.tiefe["batch"], zweite.tiefe["batch"])
        stand = aussensicht.tiefenprobe_stand(self.cfg)
        self.assertEqual(sorted(stand["gezogen"]),
                         sorted([erste.tiefe["batch"], zweite.tiefe["batch"]]))


if __name__ == "__main__":
    unittest.main()
