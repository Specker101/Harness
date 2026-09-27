"""Tests fuer R13o: Frage-Chat mit Gedaechtnis, Warteschlange, Zugriff, Token-Hinweis.

Nutzerwunsch (2026-09-27):
  * Rueckfragen sollen im SELBEN Chat landen (vorher: jede Frage ein neuer Chat),
    Rotation nach 30 min Ruhe, mehr als 10 Fragen oder aelter als 2 h,
  * `/ask-neu` fuer einen sofortigen neuen Chat,
  * Fragen strikt nacheinander (nie zwei Aufrufe auf derselben Session),
  * Leserecht auf den ganzen Harness-Ordner (`docs/`), aber gesperrt bleiben
    `secrets`, `backups/` und jede `.credentials.json`,
  * Hinweiszeile mit TOKEN-Zahlen und "Abo" statt eines Dollar-Betrags.

Alles im Attrappenbetrieb: kein Netz, keine API-Kosten, kein Ghidra.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import time
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import ask, reviewer, streamjson                              # noqa: E402
from hx.config import load_config                                     # noqa: E402
from hx.orchestrator import Orchestrator                              # noqa: E402
from hx.util import Log, ensure_dir                                   # noqa: E402


def _opt(cmd: list[str], name: str) -> list[str]:
    i = cmd.index(name)
    out: list[str] = []
    for a in cmd[i + 1:]:
        if a.startswith("--"):
            break
        out.append(a)
    return out


def _ereignis(mid: str, inp: int, cache: int, neu: int, out: int) -> str:
    """Ein assistant-Ereignis im Mitschnittformat (Nutzung je message.id)."""
    return json.dumps({
        "type": "assistant",
        "message": {"id": mid, "model": "claude-opus-5-5",
                    "usage": {"input_tokens": inp, "cache_read_input_tokens": cache,
                              "cache_creation_input_tokens": neu, "output_tokens": out},
                    "content": [{"type": "text", "text": "Antwort"}]}})


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__file__).resolve().parent / "_tmp_r13o"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "harness")
        self.decomp = ensure_dir(self.tmp / "decomp")
        ensure_dir(self.tmp / "secrets")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.decomp)
        cfg.data["paths"]["secrets"] = str(self.tmp / "secrets")
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["telegram"]["allowlist_user_ids"] = []
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)
        self.orch = Orchestrator(cfg, self.log, mock=True,
                                 state_file=self.root / "state" / "run.json")
        self.orch.say = lambda *a, **k: None

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _chat_schreiben(self, **felder) -> None:
        ziel = ensure_dir(self.root / "logs" / "ask")
        daten = {"id": str(uuid.uuid4()), "seit": datetime.now(timezone.utc).isoformat(),
                 "letzte": datetime.now(timezone.utc).isoformat(), "fragen": 0}
        daten.update(felder)
        (ziel / "session.json").write_text(json.dumps(daten) + "\n", encoding="utf-8")


class TestRotation(Base):
    def test_erste_frage_oeffnet_einen_chat(self):
        sess = ask.session_waehlen(self.cfg)
        self.assertTrue(sess["neu"])
        self.assertIn("kein Chat", sess["grund"])

    def test_folgefrage_bleibt_im_chat(self):
        self._chat_schreiben(fragen=2)
        sess = ask.session_waehlen(self.cfg)
        self.assertFalse(sess["neu"], "die Rueckfrage muss im selben Chat laufen")
        self.assertEqual(sess["grund"], "weiter")

    def test_zu_viele_fragen_rotieren(self):
        self._chat_schreiben(fragen=int(self.cfg.get("ask", "max_fragen", 10)))
        sess = ask.session_waehlen(self.cfg)
        self.assertTrue(sess["neu"])
        self.assertIn("Fragen im Chat", sess["grund"])

    def test_lange_ruhe_rotiert(self):
        alt = datetime.now(timezone.utc) - timedelta(minutes=31)
        self._chat_schreiben(letzte=alt.isoformat(), fragen=2)
        sess = ask.session_waehlen(self.cfg)
        self.assertTrue(sess["neu"])
        self.assertIn("still", sess["grund"])

    def test_zu_alter_chat_rotiert(self):
        alt = datetime.now(timezone.utc) - timedelta(minutes=121)
        self._chat_schreiben(seit=alt.isoformat(), letzte=datetime.now(timezone.utc).isoformat())
        sess = ask.session_waehlen(self.cfg)
        self.assertTrue(sess["neu"])
        self.assertIn("alt", sess["grund"])

    def test_neu_erzwingt_einen_chat(self):
        self._chat_schreiben(fragen=1)
        sess = ask.session_waehlen(self.cfg, neu=True)
        self.assertTrue(sess["neu"])
        self.assertIn("/ask-neu", sess["grund"])

    def test_frage_wird_gezaehlt(self):
        sess = ask.session_waehlen(self.cfg, neu=True)
        stand = ask.session_merken(self.cfg, sess)
        self.assertEqual(stand["fragen"], 1)
        sess2 = ask.session_waehlen(self.cfg, neu=False)
        self.assertEqual(sess2["id"], sess["id"])
        self.assertEqual(sess2["fragen"], 1)
        stand2 = ask.session_merken(self.cfg, sess2)
        self.assertEqual(stand2["fragen"], 2)

    def test_grenzen_sind_einstellbar(self):
        self.cfg.data.setdefault("ask", {})["max_fragen"] = 3
        self._chat_schreiben(fragen=3)
        self.assertTrue(ask.session_waehlen(self.cfg)["neu"])
        self.assertEqual(ask.grenzen(self.cfg)["max_fragen"], 3.0)


class TestSperre(Base):
    def test_nacheinander_und_freigabe(self):
        self.assertTrue(ask.lock_holen(self.cfg, warten_s=0.1))
        try:
            self.assertFalse(ask.lock_holen(self.cfg, warten_s=0.3),
                             "die zweite Frage darf nicht gleichzeitig starten")
            self.assertIn(str(os.getpid()), ask.lock_pfad(self.cfg).read_text(encoding="utf-8"))
        finally:
            ask.lock_freigeben(self.cfg)
        self.assertTrue(ask.lock_holen(self.cfg, warten_s=0.1))
        ask.lock_freigeben(self.cfg)

    def test_verwaiste_sperre_wird_uebernommen(self):
        self.assertTrue(ask.lock_holen(self.cfg, warten_s=0.1))
        p = ask.lock_pfad(self.cfg)
        alt = time.time() - (ask.LOCK_VERFALL_S + 60)
        os.utime(p, (alt, alt))
        self.assertTrue(ask.lock_holen(self.cfg, warten_s=1.0),
                        "eine uralte Sperre darf den Fragekanal nicht sperren")
        ask.lock_freigeben(self.cfg)


class TestKommando(Base):
    def test_neue_frage_mit_kennung(self):
        kennung = str(uuid.uuid4())
        cmd = ask.build_command(self.cfg, kennung, neu=True)
        self.assertEqual(_opt(cmd, "--session-id"), [kennung])
        self.assertNotIn("--resume", cmd)

    def test_folgefrage_setzt_fort(self):
        kennung = str(uuid.uuid4())
        cmd = ask.build_command(self.cfg, kennung, neu=False)
        self.assertEqual(_opt(cmd, "--resume"), [kennung])
        self.assertNotIn("--session-id", cmd)

    def test_ohne_kennung_kein_flag(self):
        cmd = ask.build_command(self.cfg)
        self.assertNotIn("--resume", cmd)
        self.assertNotIn("--session-id", cmd)

    def test_max_turns_ist_einstellbar(self):
        self.assertEqual(_opt(ask.build_command(self.cfg), "--max-turns"),
                         [str(int(ask.STANDARD["max_turns"]))])
        self.cfg.data.setdefault("ask", {})["max_turns"] = 40
        self.assertEqual(_opt(ask.build_command(self.cfg), "--max-turns"), ["40"])

    def test_lesen_umfasst_den_harness_ordner(self):
        cmd = ask.build_command(self.cfg)
        erlaubt = _opt(cmd, "--allowedTools")
        heim = str(self.cfg.harness_home).replace("\\", "/").rstrip("/")
        self.assertIn(f"Read(//{heim}/**)", erlaubt)
        self.assertEqual(_opt(cmd, "--tools"), ["Read,Grep,Glob"])
        cfgd = [cmd[i + 1] for i, a in enumerate(cmd) if a == "--add-dir"]
        self.assertIn(str(self.cfg.harness_home), cfgd)
        self.assertIn(str(self.cfg.decomp), cfgd)

    def test_backups_und_credentials_sind_verboten(self):
        cmd = ask.build_command(self.cfg)
        verboten = _opt(cmd, "--disallowedTools")
        self.assertTrue([v for v in verboten if "backups" in v], "backups fehlt im Verbot")
        cred = [v for v in verboten if ".credentials.json" in v]
        self.assertTrue(cred, "kein Verbot fuer .credentials.json")
        self.assertTrue(any("cc-reviewer" in v for v in cred))
        # Und der Reviewer darf die Datei in SEINER Wurzel auch nicht lesen.
        rv = reviewer.build_command(self.cfg, None, True)
        self.assertTrue([v for v in _opt(rv, "--disallowedTools")
                         if ".credentials.json" in v])

    def test_kein_dollar_im_hinweis(self):
        stats = streamjson.StreamStats()
        stats.feed(_ereignis("m1", 1000, 8000, 500, 120))
        stats.feed(_ereignis("m2", 200, 9000, 0, 80))
        zeile = ask.token_zeile(stats)
        self.assertIn("ein", zeile)
        self.assertIn("aus Cache", zeile)
        self.assertIn("18700", zeile)          # 1000+8000+500 + 200+9000+0
        self.assertNotIn("$", zeile)

    def test_chat_zeile_kennt_beide_faelle(self):
        weiter = {"id": "x", "neu": False, "grund": "weiter"}
        neu = {"id": "y", "neu": True, "grund": "kein Chat vorhanden"}
        stand = {"seit": datetime.now(timezone.utc).isoformat(), "fragen": 2}
        self.assertIn("Chat seit", ask.chat_zeile(self.cfg, weiter, stand))
        self.assertIn("Neuer Chat", ask.chat_zeile(self.cfg, neu, stand))
        self.assertIn("/10", ask.chat_zeile(self.cfg, weiter, stand))

    def test_aufraeumen_nach_der_antwort(self):
        """`ask()` gibt die Sperre frei - auch wenn der Lauf schiefgeht."""
        frei = threading.Event()

        def lauf(cmd, env, cwd=None, **k):
            frei.set()

            class R:
                rc = 1
            return R()

        with mock.patch.object(ask, "run_stream", lauf):
            with mock.patch.object(ask.envs, "reviewer_env", lambda *a, **k: {}):
                with mock.patch.object(ask.secrets, "load",
                                       lambda *a, **k: "abo-token"):
                    res = ask.ask(self.cfg, self.log, "Testfrage")
        self.assertTrue(frei.is_set(), "der Unterprozess wurde nicht gestartet")
        self.assertFalse(ask.lock_pfad(self.cfg).exists(), "Sperre blieb liegen")
        self.assertIn("chat", res)
        self.assertEqual(res["chat"]["fragen"], 1)


class TestBefehl(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__file__).resolve().parent / "_tmp_r13o"
        self.root = ensure_dir(self.tmp / "harness")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(ensure_dir(self.tmp / "decomp"))
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["telegram"]["allowlist_user_ids"] = []
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg
        self.orch = Orchestrator(cfg, Log(self.tmp / "log2.jsonl", echo=False), mock=True,
                                 state_file=self.root / "state" / "run.json")
        self.orch.say = lambda *a, **k: None

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_ask_neu_wird_geleitet(self):
        gerufen: list = []

        def fake(frage="", neu=False):
            gerufen.append((frage, neu))

        self.orch._do_ask = fake
        self.orch.handle_command("/ask-neu Warum Batch 181?")
        self.assertEqual(gerufen, [("Warum Batch 181?", True)], gerufen)

    def test_ask_wird_geleitet(self):
        gerufen: list = []
        self.orch._do_ask = lambda frage="", neu=False: gerufen.append((frage, neu))
        self.orch.handle_command("/ask Wie viele Tests?")
        self.assertEqual(gerufen, [("Wie viele Tests?", False)])

    def test_hilfe_nennt_ask_neu(self):
        import hx.telegram as tg
        self.assertIn("/ask-neu", tg.HELP)


if __name__ == "__main__":
    unittest.main()
