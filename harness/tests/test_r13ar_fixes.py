"""Tests fuer R13ar (2026-09-30): Zuglimit der Aussensicht mechanisch absichern.

**Auftrag.** (1) Ein Hook wie die Batch-Uhr des Workers: nach jedem Werkzeugaufruf die
Zeile `Zug X von <meta_max_turns>`, ab Zug (Limit - 5) zusaetzlich „JETZT die Antwort im
Blockformat schreiben, Unvollständiges als nicht geprüft kennzeichnen." (2) Fruehwarnung,
wenn ein erfolgreicher Lauf mehr als 80 % des Limits braucht (Telegram + Zeile im
Bericht). (3) Bericht: wie passt `num_turns=35` bei meta-214 mit Limit 30 zusammen?

**Gemessen** (`docs/_r13ar_zuege.txt`, `docs/_r13ar_limit_probe_reviewer.txt`): die CLI
zaehlt als Zug eine **Werkzeugrunde** (Modellantwort MIT Werkzeugaufruf): `--max-turns 2`
bricht nach 2 Runden ab. `num_turns` im Ergebnis-Ereignis ist eine andere Zahl
(Werkzeugergebnisse + 1): meta-214 hatte `num_turns=35`, aber nur **23** Runden; meta-217
brach bei **30** Runden ab (Limit 30).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import aussensicht, streamjson                            # noqa: E402
from hx.config import load_config                                 # noqa: E402
from hx.orchestrator import Orchestrator                          # noqa: E402
from hx.util import Log, ensure_dir, read_text, write_text_atomic  # noqa: E402

HOOK = ROOT / "tools" / "aussensicht_uhr.py"
DRINGEND = ("JETZT die Antwort im Blockformat schreiben, Unvollständiges als nicht "
            "geprüft kennzeichnen.")
# Sitzungskennung des gescheiterten meta-217 (aus seinem `init`-Ereignis).
SITZUNG_217 = "d19c9eda-fe57-4fae-8cbc-8c154e7745db"


def zeile(mid: str, tools: int = 0, text: str = "") -> str:
    """Eine stream-json-Zeile: eine Modellantwort mit `tools` Werkzeugaufrufen."""
    bloecke: list[dict] = []
    if text:
        bloecke.append({"type": "text", "text": text})
    for i in range(tools):
        bloecke.append({"type": "tool_use", "id": f"tu-{mid}-{i}", "name": "Read",
                        "input": {"file_path": "x"}})
    return json.dumps({"type": "assistant", "timestamp": "2026-09-30T00:00:00Z",
                       "message": {"id": mid, "model": "m", "usage": {},
                                   "content": bloecke}})


class TestRunden(unittest.TestCase):
    """Werkzeugrunden - die Zahl, gegen die die CLI ihr `--max-turns` prueft."""

    def test_zwei_aufrufe_in_einer_antwort_sind_eine_runde(self):
        self.assertEqual(streamjson.runden_aus_zeilen([zeile("m1", tools=2)]), 1)

    def test_zwei_antworten_sind_zwei_runden(self):
        self.assertEqual(streamjson.runden_aus_zeilen(
            [zeile("m1", tools=1), zeile("m2", tools=1)]), 2)

    def test_mehrere_ereignisse_je_nachricht_zaehlen_einmal(self):
        """Die CLI schreibt je Inhaltsblock ein eigenes `assistant`-Ereignis."""
        self.assertEqual(streamjson.runden_aus_zeilen(
            [zeile("m1", tools=0, text="denke"), zeile("m1", tools=1),
             zeile("m1", tools=1)]), 1)

    def test_antwort_ohne_werkzeug_ist_keine_runde(self):
        self.assertEqual(streamjson.runden_aus_zeilen(
            [zeile("m1", tools=2), zeile("m2", tools=0, text="fertig")]), 1)

    def test_kaputte_und_fremde_zeilen_stoeren_nicht(self):
        self.assertEqual(streamjson.runden_aus_zeilen(
            ["", "   ", "{kaputt", '{"type":"system","subtype":"init"}',
             zeile("m1", tools=1)]), 1)

    def test_echte_laeufe_und_num_turns_sind_verschieden(self):
        """meta-214: 35 laut `num_turns`, aber nur 23 Runden - deshalb lief er durch."""
        p14 = ROOT / "runs" / "meta-214.jsonl"
        p17 = ROOT / "runs" / "meta-217.jsonl"
        if not (p14.is_file() and p17.is_file()):
            self.skipTest("runs/meta-214.jsonl oder meta-217.jsonl fehlt")
        for pfad, runden, turns, subtype in ((p14, 23, 35, "success"),
                                             (p17, 30, 31, "error_max_turns")):
            st = streamjson.StreamStats()
            for z in pfad.read_text(encoding="utf-8", errors="replace").splitlines():
                st.feed(z)
            self.assertEqual(st.runden(), runden, pfad.name)
            self.assertEqual(st.num_turns(), turns, pfad.name)
            self.assertEqual(str((st.result or {}).get("subtype")), subtype, pfad.name)

    def test_transcript_zaehlt_dasselbe(self):
        """Das Transcript der Sitzung meta-217 ergibt dieselben 30 Runden."""
        p = (ROOT / "cc-reviewer" / "projects" / "g--Silent-Scope-Decomp" /
             f"{SITZUNG_217}.jsonl")
        if not p.is_file():
            self.skipTest("Transcript der Sitzung meta-217 fehlt")
        self.assertEqual(streamjson.runden_aus_zeilen(
            p.read_text(encoding="utf-8", errors="replace").splitlines()), 30)


class TestHook(unittest.TestCase):
    """Der Hook als Unterprozess - so, wie die CLI ihn ruft."""

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13ar"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.transcript = self.tmp / "sitzung.jsonl"
        ensure_dir(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def schreibe(self, *zeilen: str) -> Path:
        write_text_atomic(self.transcript, "\n".join(zeilen) + "\n")
        return self.transcript

    def hook(self, *, limit: str | None = "50", transcript: Path | None = None,
             eingabe: dict | None = None, zeilen: tuple[str, ...] = (),
             frist: str | None = "8"):
        if zeilen:
            self.schreibe(*zeilen)
        daten = eingabe if eingabe is not None else {
            "hook_event_name": "PostToolUse", "tool_name": "Read",
            "transcript_path": str(transcript or self.transcript)}
        args = [sys.executable, str(HOOK)]
        if limit is not None:
            args += ["--limit", str(limit)]
        if frist is not None:
            args += ["--frist", str(frist)]
        p = subprocess.run(args, input=json.dumps(daten).encode("utf-8"),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        self.assertEqual(p.returncode, 0, p.stderr.decode("utf-8", "replace")[:300])
        roh = p.stdout.decode("utf-8").strip()
        if not roh:
            return ""
        return json.loads(roh)["hookSpecificOutput"]["additionalContext"]

    def test_zugzeile_mit_dem_stand(self):
        text = self.hook(zeilen=(zeile("m1", tools=1), zeile("m2", tools=2)))
        self.assertEqual(text, "AUSSENSICHT-UHR: Zug 2 von 50 (Werkzeugrunden).")

    def test_ab_limit_minus_acht_kommt_die_frist(self):
        """R13at: der Abstand ist 8 (vorher 5) - bei Limit 70 also ab Zug 62."""
        zeilen = tuple(zeile(f"m{i}", tools=1) for i in range(1, 8))   # 7 Runden
        text = self.hook(limit="10", zeilen=zeilen)
        self.assertIn("Zug 7 von 10", text)
        self.assertIn("Noch 3 Zuege bis zum Abbruch.", text)
        self.assertIn(DRINGEND, text)

    def test_frist_abstand_kommt_aus_dem_harness(self):
        """Ein GROESSERER Abstand feuert FRUEHER: 4 Runden bei Limit 10 feuern mit
        `--frist 8` (ab Zug 2), mit `--frist 3` (ab Zug 7) nicht."""
        vier = tuple(zeile(f"m{i}", tools=1) for i in range(1, 5))
        self.assertIn(DRINGEND, self.hook(limit="10", zeilen=vier))
        self.assertNotIn(DRINGEND, self.hook(limit="10", zeilen=vier, frist="3"))

    def test_ohne_frist_gilt_acht(self):
        """Rueckfall, wenn der Harness `--frist` nicht mitgibt: 8."""
        drei = tuple(zeile(f"m{i}", tools=1) for i in range(1, 4))     # 3 < 12 - 8
        text = self.hook(limit="12", zeilen=drei, frist=None)
        self.assertIn("Zug 3 von 12", text)
        self.assertNotIn("JETZT", text)
        vier = tuple(zeile(f"m{i}", tools=1) for i in range(1, 5))     # 4 = 12 - 8
        self.assertIn(DRINGEND, self.hook(limit="12", zeilen=vier, frist=None))

    def test_vor_der_frist_kommt_sie_nicht(self):
        zeilen = tuple(zeile(f"m{i}", tools=1) for i in range(1, 2))   # 1 < 10 - 8
        text = self.hook(limit="10", zeilen=zeilen)
        self.assertIn("Zug 1 von 10", text)
        self.assertNotIn("JETZT", text)

    def test_genau_an_der_grenze(self):
        zeilen = tuple(zeile(f"m{i}", tools=1) for i in range(1, 3))   # 2 = 10 - 8
        text = self.hook(limit="10", zeilen=zeilen)
        self.assertIn(DRINGEND, text)
        eine = tuple(zeile(f"m{i}", tools=1) for i in range(1, 2))     # 1 < 10 - 8
        self.assertNotIn(DRINGEND, self.hook(limit="10", zeilen=eine))

    def test_echtes_limit_70(self):
        """Der laufende Fall (R13at): Limit 70 -> Frist ab Zug 62."""
        sechzig = tuple(zeile(f"m{i}", tools=1) for i in range(1, 62))  # 61 Runden
        self.assertNotIn("JETZT", self.hook(limit="70", zeilen=sechzig))
        einundsechzig = tuple(zeile(f"m{i}", tools=1) for i in range(1, 63))
        text = self.hook(limit="70", zeilen=einundsechzig)
        self.assertIn("Zug 62 von 70", text)
        self.assertIn(DRINGEND, text)

    def test_parallele_aufrufe_geben_keine_extrazeile(self):
        text = self.hook(zeilen=(zeile("m1", tools=3),))
        self.assertIn("Zug 1 von 50", text)

    def test_ohne_transcript_keine_zeile(self):
        self.assertEqual(self.hook(transcript=self.tmp / "gibtsnicht.jsonl"), "")
        self.assertEqual(self.hook(zeilen=()), "")

    def test_ohne_limit_keine_zeile(self):
        self.assertEqual(self.hook(limit=None, zeilen=(zeile("m1", tools=1),)), "")

    def test_kaputte_eingabe_ist_still(self):
        self.assertEqual(self.hook(limit="50",
                                   eingabe={"hook_event_name": "PostToolUse"}), "")
        self.assertEqual(self.hook(limit="viel", zeilen=(zeile("m1", tools=1),)), "")


class TestEinstellungen(unittest.TestCase):
    """Die Einstellungsdatei mit dem Hook (R13ar)."""

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13ar_cfg"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "root")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(ensure_dir(self.tmp / "decomp"))
        self.cfg = cfg

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_datei_traegt_das_limit(self):
        self.cfg.data["meta"]["meta_max_turns"] = 44
        pfad = aussensicht.write_hook_settings(self.cfg, 217)
        self.assertTrue(pfad)
        daten = json.loads(read_text(pfad))
        args = daten["hooks"]["PostToolUse"][0]["hooks"][0]["args"]
        self.assertIn("aussensicht_uhr.py", " ".join(args))
        self.assertEqual(args[args.index("--limit") + 1], "44")
        # R13at: die Frist kommt ebenfalls aus dem Harness (EINE Quelle).
        self.assertEqual(args[args.index("--frist") + 1], str(aussensicht.FRIST_ABSTAND))
        # R13br: die Einstellungsdatei liegt im Ordner des bewerteten Batches.
        self.assertTrue(str(pfad).endswith("meta-hooks.json"))
        self.assertEqual(Path(pfad).parent.name, "b217")

    def test_kommando_haengt_die_einstellungen_an(self):
        pfad = aussensicht.write_hook_settings(self.cfg, 217)
        cmd = aussensicht.build_command(self.cfg, hooks_settings=pfad)
        self.assertIn("--settings", cmd)
        self.assertEqual(cmd[cmd.index("--settings") + 1], str(pfad))

    def test_ohne_einstellungen_kein_schalter(self):
        self.assertNotIn("--settings", aussensicht.build_command(self.cfg))


class TestFruehwarnung(unittest.TestCase):
    def test_ueber_80_prozent_warnt(self):
        self.assertEqual(aussensicht.limit_hinweis(217, 25, 30),
                         "Aussensicht B217: 25 von 30 Zuegen genutzt - Limit pruefen")

    def test_genau_80_prozent_warnt_nicht(self):
        self.assertEqual(aussensicht.limit_hinweis(217, 24, 30), "")

    def test_ohne_runden_keine_warnung(self):
        self.assertEqual(aussensicht.limit_hinweis(217, 0, 30), "")
        self.assertEqual(aussensicht.limit_hinweis(217, 25, 0), "")

    def test_echte_laeufe_haetten_gewarnt_oder_nicht(self):
        """Gegenprobe an den echten Runden: 23/30 warnt nicht, 30/30 haette gewarnt."""
        self.assertEqual(aussensicht.limit_hinweis(214, 23, 30), "")
        self.assertNotEqual(aussensicht.limit_hinweis(217, 30, 30), "")


class TestBerichtUndOrchestrator(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13ar_bericht"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "root")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(ensure_dir(self.tmp / "decomp"))
        cfg.data["paths"]["harness_home"] = str(self.tmp)
        cfg.data["paths"]["secrets"] = str(ensure_dir(self.tmp / "secrets"))
        cfg.data["mock"]["enabled"] = True
        cfg.data["meta"]["meta_max_turns"] = 30
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)
        self.gesagt: list[str] = []

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _res(self, runden: int, rc: int = 0, summary: str = "Geprueft: ok."):
        res = aussensicht.Ergebnis()
        res.rc, res.dauer_s, res.modell = rc, 200.0, "claude-opus-5-5"
        res.summary, res.zug_runden = summary, runden
        res.zuege = runden + 1
        return res

    def test_bericht_zeigt_zuege_und_warnung(self):
        text = aussensicht.bericht(self.cfg, 217, "Test", self._res(29),
                                   {"ids": [], "verdikte": [], "offen_alt": 0}, ["Test"])
        self.assertIn("- Zuege (Werkzeugrunden): 29 von 30", text)
        self.assertIn("num_turns laut CLI: 30", text)
        self.assertIn("- LIMIT PRUEFEN: Aussensicht B217: 29 von 30 Zuegen genutzt - "
                      "Limit pruefen", text)

    def test_bericht_ohne_warnung_bei_wenig_zuegen(self):
        text = aussensicht.bericht(self.cfg, 217, "Test", self._res(12),
                                   {"ids": [], "verdikte": [], "offen_alt": 0}, ["Test"])
        self.assertIn("- Zuege (Werkzeugrunden): 12 von 30", text)
        self.assertNotIn("LIMIT PRUEFEN", text)

    def test_json_traegt_die_runden(self):
        aussensicht.bericht_schreiben(self.cfg, 217, "Test", self._res(26), {},
                                      ["Test"])
        # R13br: die Maschinenfassung liegt im Batchordner (`runs/b217/meta.json`).
        daten = json.loads(read_text(aussensicht.json_pfad(self.cfg, 217)))
        self.assertEqual(daten.get("zug_runden"), 26)
        self.assertEqual(daten.get("zuege"), 27)

    def orch(self, batch: int = 217) -> Orchestrator:
        o = Orchestrator(self.cfg, self.log, mock=True,
                         state_file=self.root / "state" / "run.json")
        o.state.data["batch"] = batch
        o.state.data["meta"] = {"letzter_lauf_batch": 214, "geprueft_batch": 214}
        o.state.save()
        o.say = lambda *a, **k: self.gesagt.append(str(a[0] if a else ""))
        self.gesagt.clear()
        return o

    def test_orchestrator_meldet_die_warnung(self):
        o = self.orch()
        with mock.patch.object(aussensicht, "run", return_value=self._res(27)), \
                mock.patch.object(aussensicht, "verteile",
                                  return_value={"ids": [], "verdikte": [], "offen_alt": 0}):
            o._do_aussensicht("alle 3 Batches", gruende=["alle 3 Batches"])
        self.assertTrue(any(z.startswith("Aussensicht B217: 27 von 30 Zuegen genutzt - "
                                         "Limit pruefen") for z in self.gesagt),
                        self.gesagt)
        self.assertTrue(any(z.get("msg") == "Zuglimit fast erreicht"
                            for z in self.log_zeilen()))

    def test_orchestrator_schweigt_bei_wenig_zuegen(self):
        o = self.orch()
        with mock.patch.object(aussensicht, "run", return_value=self._res(5)), \
                mock.patch.object(aussensicht, "verteile",
                                  return_value={"ids": [], "verdikte": [], "offen_alt": 0}):
            o._do_aussensicht("alle 3 Batches", gruende=["alle 3 Batches"])
        self.assertFalse([z for z in self.gesagt if "Zuegen genutzt" in z], self.gesagt)
        self.assertFalse([z for z in self.log_zeilen()
                          if z.get("msg") == "Zuglimit fast erreicht"])

    def log_zeilen(self) -> list[dict]:
        if not self.log.path.is_file():
            return []
        return [json.loads(z) for z in
                self.log.path.read_text(encoding="utf-8").splitlines() if z.strip()]


if __name__ == "__main__":
    unittest.main()
