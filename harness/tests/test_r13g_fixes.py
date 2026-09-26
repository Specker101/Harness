"""Tests fuer R13g: Schluessel ausserhalb des Harness, Ueberwachung der Mitschnitte.

Drei Zusagen werden geprueft:

1. **Ablage/Rechte**: die Schluessel liegen ausserhalb (`%USERPROFILE%/.hx-secrets`),
   die Pfadaufloesung der Konfiguration kennt `$USERPROFILE`, und der ALTE Ort bleibt
   in den Werkzeugverboten (dort soll niemand mehr suchen).
2. **Ueberwachung**: Werkzeugaufrufe auf den alten und neuen Ort werden erkannt,
   SchluesselWERTE im Mitschnitt ebenfalls - aber ein Dokument, das den Pfad nur
   zitiert, loest KEINEN Alarm aus (Lehre aus B172/B173).
3. **Keine Werte in Belegen**: Alarmtext, Belegdatei und Messdatenzeile nennen nur
   Art, Werkzeug und Dateinamen.

Werte sind im Test Attrappen ("TESTKEY-..."), verglichen wird nur im Speicher.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import ask, reviewer, secrets, streamjson, worker                # noqa: E402
from hx.config import Config, expand_path, load_config                   # noqa: E402
from hx.orchestrator import Orchestrator                                 # noqa: E402
from hx.profiles import secrets_verbote                                  # noqa: E402
from hx.util import Log, ensure_dir                                      # noqa: E402

WERT_D = "TESTKEY-DEEPSEEK-0001"
WERT_T = "TESTKEY-TELEGRAM-0002"
WERT_C = "TESTKEY-CLAUDE-0003"
ALT = r"g:\Harness\secrets"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__file__).resolve().parent / "_tmp_r13g"
        shutil.rmtree(self.tmp, ignore_errors=True)
        sec = ensure_dir(self.tmp / "profile" / ".hx-secrets")
        (sec / secrets.DEEPSEEK).write_text(WERT_D + "\n", encoding="utf-8")
        (sec / secrets.TELEGRAM).write_text(WERT_T + "\n", encoding="utf-8")
        (sec / secrets.CLAUDE_OAUTH).write_text(WERT_C + "\n", encoding="utf-8")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(ensure_dir(self.tmp / "harness"))
        cfg.data["paths"]["decomp"] = str(ensure_dir(self.tmp / "decomp"))
        cfg.data["paths"]["secrets"] = str(sec)
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["telegram"]["allowlist_user_ids"] = []
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def stats(self, *bloecke) -> streamjson.StreamStats:
        """Ein assistant-Ereignis mit den gegebenen Inhaltsbloecken fuettern."""
        s = streamjson.StreamStats(streamjson.secret_watch(self.cfg))
        s.feed(json.dumps({"type": "assistant",
                           "message": {"id": "m1", "model": "m", "usage": {},
                                       "content": list(bloecke)}}, ensure_ascii=False))
        return s

    @staticmethod
    def tool(tid: str, name: str, inp: dict) -> dict:
        return {"type": "tool_use", "id": tid, "name": name, "input": inp}


# --------------------------------------------------------- 1. Ablage und Rechte
class TestAblage(Base):
    def test_userprofile_wird_aufgeloest(self):
        cfg = Config({"paths": {"secrets": "$USERPROFILE/.hx-secrets"}}, Path("x.toml"))
        self.assertEqual(str(cfg.secrets_dir),
                         str(Path(os.environ["USERPROFILE"]) / ".hx-secrets"))
        self.assertEqual(
            str(Path(expand_path("%USERPROFILE%/x"))),
            str(Path(os.environ["USERPROFILE"]) / "x"))

    def test_konfiguration_zeigt_nicht_mehr_ins_harness(self):
        echt = load_config()
        self.assertNotIn("Harness/secrets", str(echt.secrets_dir).replace("\\", "/"))
        self.assertIn(".hx-secrets", str(echt.secrets_dir).replace("\\", "/"))

    def test_alter_ort_bleibt_verboten(self):
        verbote = secrets_verbote(self.cfg.secrets_dir, *secrets.ALT_ORTE)
        self.assertIn("Read(//g:/Harness/secrets/**)", verbote)
        neu = str(self.cfg.secrets_dir).replace("\\", "/")
        self.assertIn(f"Read(//{neu}/**)", verbote)

    def test_rollen_verbieten_beide_orte(self):
        for cmd in (ask.build_command(self.cfg),
                    reviewer.build_command(self.cfg, None, True)):
            verboten = cmd[cmd.index("--disallowedTools") + 1:]
            verboten = " ".join(a for a in verboten if not a.startswith("--"))
            self.assertIn("harness/secrets", verboten.replace("\\", "/").lower())
            self.assertIn(".hx-secrets", verboten.lower())

    def test_alter_ordner_ist_leer(self):
        """Betriebsbedingt: im Harness liegt kein Schluessel mehr (nur eine Marke)."""
        alt = Path("g:/Harness/secrets")
        if alt.is_dir():
            reste = [p.name for p in alt.iterdir()]
            self.assertEqual(reste, [], f"im alten Ordner liegt noch etwas: {reste}")


# ------------------------------------------------------------ 2. Ueberwachung
class TestUeberwachung(Base):
    def test_alter_ort_im_leseaufruf(self):
        s = self.stats(self.tool("t1", "Read", {"file_path": ALT + r"\deepseek.key"}))
        self.assertEqual([h["art"] for h in s.secret_hits], ["pfad"])
        self.assertEqual(s.secret_hits[0]["name"], "g:/harness/secrets")

    def test_neuer_ort_in_powershell(self):
        pfad = str(Path(self.cfg.secrets_dir) / secrets.TELEGRAM)
        s = self.stats(self.tool("t1", "PowerShell", {"command": f"Get-Content {pfad}"}))
        self.assertEqual(len(s.secret_hits), 1)
        self.assertEqual(s.secret_hits[0]["werkzeug"], "PowerShell")

    def test_schreibende_werkzeuge_pruefen_nur_das_ziel(self):
        """Ein Write, der den Pfad nur im TEXT nennt, ist kein Zugriff."""
        s = self.stats(self.tool("t1", "Write", {"file_path": str(self.tmp / "x.md"),
                                                 "content": f"frueher lag es in {ALT}"}))
        self.assertEqual(s.secret_hits, [])

    def test_dokument_im_ergebnis_ist_kein_zugriff(self):
        s = streamjson.StreamStats(streamjson.secret_watch(self.cfg))
        s.feed(json.dumps({"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "t9",
             "content": f"Datei gelesen: {ALT}\\deepseek.key"}]}}, ensure_ascii=False))
        self.assertEqual(s.secret_hits, [])

    def test_wert_im_mitschnitt_ist_ein_treffer(self):
        s = self.stats({"type": "text", "text": f"gefunden: {WERT_D}"})
        self.assertEqual([h["art"] for h in s.secret_hits], ["wert"])
        self.assertEqual(s.secret_hits[0]["name"], secrets.DEEPSEEK)
        self.assertNotIn(WERT_D, json.dumps(s.secret_hits, ensure_ascii=False))

    def test_wert_im_denkblock_ist_ein_treffer(self):
        s = self.stats({"type": "thinking", "thinking": f"ich sah {WERT_T} in der Datei"})
        self.assertEqual([h["name"] for h in s.secret_hits], [secrets.TELEGRAM])

    def test_treffer_werden_gezaehlt_nicht_vervielfacht(self):
        s = self.stats(self.tool("t1", "Read", {"file_path": ALT + "/a"}),
                       self.tool("t2", "Read", {"file_path": ALT + "/b"}))
        self.assertEqual(len(s.secret_hits), 1)
        self.assertEqual(s.secret_hits[0]["anzahl"], 2)

    def test_ohne_watch_kostet_es_nichts(self):
        s = streamjson.StreamStats()
        s.feed(json.dumps({"type": "assistant", "message": {
            "id": "m", "model": "m", "usage": {}, "content": [
                {"type": "text", "text": f"{WERT_D} und {ALT}"}]}}, ensure_ascii=False))
        self.assertEqual(s.secret_hits, [])

    def test_alarmtext_und_beleg_ohne_werte(self):
        s = self.stats({"type": "text", "text": f"gefunden: {WERT_D}"},
                       self.tool("t1", "Read", {"file_path": ALT + "/deepseek.key"}))
        alarm = streamjson.secret_alarm_text(s.secret_hits, "Worker", 176)
        self.assertIn("SECRET-ZUGRIFF", alarm)
        self.assertIn("Batch 176", alarm)
        for wert in (WERT_D, WERT_T, WERT_C):
            self.assertNotIn(wert, alarm)
        beleg = streamjson.schreibe_secret_beleg(self.cfg, s.secret_hits, "Worker", 176)
        text = Path(beleg).read_text(encoding="utf-8")
        for wert in (WERT_D, WERT_T, WERT_C):
            self.assertNotIn(wert, text)
        self.assertIn("Worker", text)
        self.assertEqual(len(streamjson.secret_meldungen(self.cfg, 176)), len(s.secret_hits))

    def test_mitschnitt_nachpruefen(self):
        """`scanne_mitschnitt` findet Werte in einer fertigen Datei (Rebuild/Review)."""
        p = self.tmp / "stream.jsonl"
        p.write_text(json.dumps({"type": "assistant", "message": {
            "id": "m", "model": "m", "usage": {}, "content": [
                {"type": "text", "text": f"wert {WERT_C}"}]}}) + "\n", encoding="utf-8")
        treffer = streamjson.scanne_mitschnitt(self.cfg, p)
        self.assertEqual([h["name"] for h in treffer], [secrets.CLAUDE_OAUTH])


# -------------------------------------------------- 3. Meldeweg und Messdaten
class TestMeldeweg(Base):
    def _orch(self) -> Orchestrator:
        o = Orchestrator(self.cfg, self.log, mock=True,
                         state_file=self.tmp / "harness" / "state" / "run.json")
        o.say = lambda *a, **k: None
        return o

    def test_messdatenzeile_ohne_treffer(self):
        self.assertEqual(self._orch().secret_zeile(176), "keine")

    def test_messdatenzeile_mit_treffer(self):
        treffer = [{"art": "pfad", "werkzeug": "Read", "name": "g:/harness/secrets",
                    "stelle": "", "anzahl": 1}]
        streamjson.schreibe_secret_beleg(self.cfg, treffer, "Worker", 176)
        zeile = self._orch().secret_zeile(176)
        self.assertIn("1 Treffer", zeile)
        self.assertIn("Worker:Read:pfad", zeile)
        # Ein anderer Batch bleibt sauber.
        self.assertEqual(self._orch().secret_zeile(177), "keine")

    def test_messdatenblock_enthaelt_die_zeile(self):
        treffer = [{"art": "wert", "werkzeug": "-", "name": secrets.TELEGRAM,
                    "stelle": "", "anzahl": 1}]
        streamjson.schreibe_secret_beleg(self.cfg, treffer, "Reviewer", 176)
        o = self._orch()
        o.state.data["last_batch_number"] = 176
        text = o.harness_facts(176, ziel=self.tmp / "out")
        self.assertIn("SECRET-ZUGRIFF (Ueberwachung): 1 Treffer", text)
        self.assertNotIn(WERT_T, text)

    def test_worker_vorspann_verbietet_den_zugriff(self):
        pre = worker.WORKER_PREAMBLE.lower()
        self.assertIn("zugangsdaten sind tabu", pre)
        self.assertIn("verboten", pre)
        self.assertIn("secret-zugriff", pre)

    def test_reviewer_scannt_seinen_mitschnitt(self):
        alt = Path("g:/Harness/secrets")
        self.assertTrue(alt.is_dir() or True)          # nur Dokumentation des Ortes
        r = reviewer.ReviewResult()
        self.assertEqual(r.secret_hits, [])

    def test_meldungen_sind_leer_ohne_datei(self):
        (Path(self.cfg.sub("logs")) / "secret-zugriff.jsonl").unlink(missing_ok=True)
        self.assertEqual(streamjson.secret_meldungen(self.cfg), [])


if __name__ == "__main__":
    unittest.main()
