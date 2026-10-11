"""Tests fuer R13bx-6: auch `/ask` kann ohne Abo laufen (`/ask_swap`).

**Auftrag (Nutzer, 2026-10-11):** "am besten wir machen auch ein /ask_swap damit /ask auch
ohne abo laufen kann".

Bauart wie R13bx-5 (`/reviewer_swap`), mit zwei Besonderheiten von /ask:

* /ask hat ein **eigenes Chat-Gedaechtnis** (`logs/ask/session.json`). Der Anbieter gehoert
  zum CHAT: die Kennung lebt im Konfigordner des Anbieters, ein Wechsel kann den alten Chat
  nicht fortsetzen und legt deshalb einen neuen an.
* /ask zeigt auf dem Abo **Token statt Dollar** (R13o: ein Dollarbetrag waere dort mit der
  DeepSeek-Tabelle gerechnet). Auf DeepSeek ist der Dollarbetrag RICHTIG - dort steht er.

Weiter festgehalten: die **Anbieter-Namen und ihre Schreibweisen** stehen jetzt in `envs`
(EINE Quelle fuer Review UND /ask), und die Regel "nur das Abo kann ins Abo-Limit laufen"
steht ebenfalls dort (`envs.abo_limit_moeglich`) - sie wird von Reviewer, Aussensicht und
/ask gerufen.

Alles im Attrappenbetrieb: kein Netz, keine API-Kosten, keine echten Chats.
"""

from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import ask, aussensicht, envs, reviewer                        # noqa: E402
from hx.config import load_config                                      # noqa: E402
from hx.orchestrator import Orchestrator                               # noqa: E402
from hx.util import Log, ensure_dir, write_text_atomic                 # noqa: E402

ANKER = "# Workstream R1B\n\n**Stand:** BATCH 180\n"


def _cfg(**claude) -> object:
    """Frische Konfiguration - je Aufruf neu, damit sich Tests nicht beeinflussen."""
    cfg = load_config()
    for k, v in claude.items():
        cfg.data.setdefault("claude", {})[k] = v
    return cfg


class TestAskWahl(unittest.TestCase):
    def test_abo_ist_die_vorgabe(self):
        cfg = _cfg()
        w = ask.ask_wahl(cfg)
        self.assertEqual(w["anbieter"], envs.ANBIETER_ABO)
        # Das Modell kommt aus der Konfiguration (`ask_modell`) - NICHT hart nennen.
        self.assertEqual(w["modell"], cfg.get("claude", "ask_modell"))
        self.assertEqual(w["grund"], "Abo (Vorgabe)")

    def test_deepseek_ohne_eigenes_modell_nimmt_den_worker(self):
        cfg = _cfg()
        w = ask.ask_wahl(cfg, "deepseek")
        self.assertEqual(w["anbieter"], envs.ANBIETER_DEEPSEEK)
        self.assertEqual(w["modell"], cfg.get("claude", "model_worker"))
        self.assertEqual(w["effort"], cfg.get("claude", "ask_effort_deepseek", "high"))
        self.assertIn("/ask_swap", w["grund"])

    def test_eigenes_deepseek_modell_hat_vorrang(self):
        w = ask.ask_wahl(_cfg(ask_modell_deepseek="deepseek-flash[1m]"), "ds")
        self.assertEqual(w["modell"], "deepseek-flash[1m]")

    def test_unbekannter_anbieter_faellt_aufs_abo(self):
        self.assertEqual(ask.ask_wahl(_cfg(), "quatsch")["anbieter"], envs.ANBIETER_ABO)


class TestAnbieterGemeinsam(unittest.TestCase):
    """Die gemeinsame Basis in `envs` - Review und /ask duerfen nicht auseinanderlaufen."""

    def test_reviewer_zeigt_auf_envs(self):
        self.assertEqual(reviewer.ANBIETER_ABO, envs.ANBIETER_ABO)
        self.assertEqual(reviewer.ANBIETER_DEEPSEEK, envs.ANBIETER_DEEPSEEK)
        self.assertIs(reviewer.anbieter_wort, envs.anbieter_wort)

    def test_abo_limit_regel(self):
        self.assertTrue(envs.abo_limit_moeglich(""))
        self.assertTrue(envs.abo_limit_moeglich("abo"))
        self.assertTrue(envs.abo_limit_moeglich("quatsch"))
        self.assertFalse(envs.abo_limit_moeglich("deepseek"))
        self.assertFalse(envs.abo_limit_moeglich("ds"))

    def test_alle_drei_rollen_benutzen_dieselbe_regel(self):
        """Reviewer, Aussensicht und /ask - eine Regel, nicht drei Formulierungen."""
        self.assertFalse(reviewer.limit_erreicht(_Res("deepseek"), "quota", ""))
        self.assertTrue(reviewer.limit_erreicht(_Res("abo"), "usage limit", ""))
        self.assertFalse(aussensicht.limit_erreicht("deepseek", "quota", ""))
        self.assertTrue(aussensicht.limit_erreicht("abo", "usage limit", ""))

    def test_ask_ds_ist_eine_deepseek_rolle(self):
        self.assertIn("ask_ds", envs.ROLLEN_DEEPSEEK)


class _Res:
    """Minimaler Ergebnis-Ersatz fuer `reviewer.limit_erreicht`."""

    def __init__(self, anbieter: str, text: str = ""):
        self.anbieter = anbieter
        self.text = text


class TestAskUmgebung(unittest.TestCase):
    def setUp(self):
        self.cfg = _cfg(config_dir_reviewer="C:/tmp/cc-reviewer",
                        config_dir_reviewer_ds="C:/tmp/cc-reviewer-ds",
                        config_dir_ask_ds="C:/tmp/cc-ask-ds")

    def test_deepseek_umgebung_hat_kein_abo_token(self):
        env = envs.ask_deepseek_env(self.cfg, {}, "ds-token", "high")
        self.assertEqual(env["CLAUDE_CONFIG_DIR"], "C:/tmp/cc-ask-ds")
        self.assertEqual(env["ANTHROPIC_AUTH_TOKEN"], "ds-token")
        self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN", env)
        self.assertEqual(env["CLAUDE_CODE_EFFORT_LEVEL"], "high")

    def test_eigener_ordner_auch_gegen_den_reviewer_ds(self):
        a = envs.ask_deepseek_env(self.cfg, {}, "t", "high")
        r = envs.reviewer_deepseek_env(self.cfg, {}, "t", "high")
        self.assertNotEqual(a["CLAUDE_CONFIG_DIR"], r["CLAUDE_CONFIG_DIR"])
        self.assertNotEqual(a["CLAUDE_CONFIG_DIR"], self.cfg.get("claude", "config_dir_reviewer"))

    def test_precheck_je_rolle(self):
        ds = envs.ask_deepseek_env(self.cfg, {}, "t", "high")
        abo = envs.reviewer_env(self.cfg, {}, "oauth")
        self.assertEqual(envs.precheck(ds, "ask_ds"), [])
        self.assertEqual(envs.precheck(abo, "reviewer"), [])

    def test_falscher_rollenname_faellt_laut_auf(self):
        ds = envs.ask_deepseek_env(self.cfg, {}, "t", "high")
        abo = envs.reviewer_env(self.cfg, {}, "oauth")
        self.assertTrue(envs.precheck(ds, "reviewer"))
        self.assertTrue(envs.precheck(abo, "ask_ds"))


class TestKommando(unittest.TestCase):
    """`build_command` und die Preiszeile - hier wird nichts gestartet."""

    def test_strict_mcp_config_bleibt_im_kommando(self):
        """Der Frage-Lauf darf keine MCP-Werkzeuge erben (R13o)."""
        cmd = ask.build_command(_cfg())
        self.assertIn("--strict-mcp-config", cmd)
        self.assertIn("Read,Grep,Glob", cmd)

    def test_modell_ist_waehlbar(self):
        cfg = _cfg()
        cmd = ask.build_command(cfg, modell="deepseek-flash[1m]")
        self.assertEqual(cmd[cmd.index("--model") + 1], "deepseek-flash[1m]")
        # Ohne Angabe bleibt es beim Abo-Modell (Altaufrufer).
        cmd2 = ask.build_command(cfg)
        self.assertEqual(cmd2[cmd2.index("--model") + 1], cfg.get("claude", "ask_modell"))


class Basis(unittest.TestCase):
    """Ein echter Orchestrator im Attrappenbetrieb (kein Netz, keine Chats)."""

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13bx6"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "root")
        self.decomp = ensure_dir(self.tmp / "decomp")
        write_text_atomic(self.decomp / "analysis" / "r1b-workstream.md", ANKER)
        prof = ensure_dir(self.root / "profiles")
        for f in (ROOT / "profiles").glob("*.json"):
            shutil.copy2(f, prof / f.name)
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.decomp)
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["paths"]["secrets"] = str(ensure_dir(self.tmp / "secrets"))
        cfg.data["telegram"]["allowlist_user_ids"] = []
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)
        self.orch = Orchestrator(cfg, self.log, mock=True,
                                 state_file=self.root / "state" / "run.json")
        self.gesagt: list[str] = []
        self.orch.say = lambda t="", *a, **k: self.gesagt.append(str(t))
        st = self.orch.state
        st.data["batch"] = 180
        st.data["last_batch_number"] = 180
        st.data["paused"] = False

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def text(self) -> str:
        return " ".join(self.gesagt)

    def befehl(self, text: str) -> None:
        self.gesagt.clear()
        self.orch.handle_command(text)

    def session(self) -> dict:
        p = Path(self.cfg.root) / "logs" / "ask" / "session.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


class TestBefehl(Basis):
    def test_nackter_befehl_schaltet_um_und_zurueck(self):
        self.befehl("/ask_swap")
        self.assertEqual(self.orch.state.data.get("ask_anbieter"), envs.ANBIETER_DEEPSEEK)
        self.assertIn("DEEPSEEK", self.text().upper())
        self.assertIn("Kein Abo-Kontingent", self.text())
        self.befehl("/ask_swap")
        self.assertNotIn("ask_anbieter", self.orch.state.data)
        self.assertIn("ABO", self.text().upper())
        self.assertIn("Wochenkontingent", self.text())

    def test_ausdrueckliche_angabe_und_kurzform(self):
        self.befehl("/ask_swap deepseek")
        self.assertEqual(self.orch.state.data.get("ask_anbieter"), "deepseek")
        self.befehl("/ask_swap abo")
        self.assertNotIn("ask_anbieter", self.orch.state.data)
        self.befehl("/ask_swap ds")
        self.assertEqual(self.orch.state.data.get("ask_anbieter"), "deepseek")

    def test_unbekannter_zusatz_aendert_nichts(self):
        self.befehl("/ask_swap quatsch")
        self.assertNotIn("ask_anbieter", self.orch.state.data)
        self.assertIn("Nutzung", self.text())

    def test_anbieter_und_statuszeile(self):
        self.assertEqual(self.orch.ask_anbieter(), envs.ANBIETER_ABO)
        self.befehl("/ask_swap deepseek")
        self.assertEqual(self.orch.ask_anbieter(), envs.ANBIETER_DEEPSEEK)
        st = self.orch.status_text()
        self.assertIn("Frage-Anbieter: DEEPSEEK", st)
        self.assertIn("/ask_swap", st)

    def test_getrennt_vom_reviewer(self):
        """/ask_swap darf den Review nicht umstellen - und umgekehrt."""
        self.befehl("/ask_swap deepseek")
        self.assertEqual(self.orch.reviewer_anbieter(), envs.ANBIETER_ABO)
        self.befehl("/reviewer_swap deepseek")
        self.assertEqual(self.orch.reviewer_anbieter(), envs.ANBIETER_DEEPSEEK)
        self.befehl("/ask_swap abo")
        self.assertEqual(self.orch.reviewer_anbieter(), envs.ANBIETER_DEEPSEEK)


class TestChatWechsel(Basis):
    """Der Anbieter gehoert zum Chat (Attrappen: kein Netz, keine Kosten)."""

    def _frage(self, anbieter: str) -> dict:
        return ask.ask(self.cfg, self.log, "Was steht im Anker?", mock=True,
                       anbieter=anbieter)

    def test_mock_merkt_den_anbieter(self):
        self._frage("deepseek")
        self.assertEqual(self.session().get("anbieter"), envs.ANBIETER_DEEPSEEK)

    def test_wechsel_erzwingt_einen_neuen_chat(self):
        r1 = self._frage("deepseek")
        chat1 = r1["chat"]["id"]
        # Derselbe Anbieter: der Chat laeuft weiter.
        r2 = self._frage("deepseek")
        self.assertFalse(r2["chat"]["neu"])
        self.assertEqual(r2["chat"]["id"], chat1)
        # Anbieter gewechselt -> neuer Chat, und der Grund nennt den Wechsel.
        r3 = self._frage("abo")
        self.assertTrue(r3["chat"]["neu"])
        self.assertNotEqual(r3["chat"]["id"], chat1)
        self.assertIn("Anbieter gewechselt", r3["chat"]["grund"])
        self.assertIn("deepseek -> abo", r3["chat"]["grund"])

    def test_aus_zustand_liest_den_befehl(self):
        self.assertEqual(ask.anbieter_aus_zustand(self.cfg), envs.ANBIETER_ABO)
        self.befehl("/ask_swap deepseek")
        self.assertEqual(ask.anbieter_aus_zustand(self.cfg), envs.ANBIETER_DEEPSEEK)
        self.befehl("/ask_swap abo")
        self.assertEqual(ask.anbieter_aus_zustand(self.cfg), envs.ANBIETER_ABO)

    def test_anbieter_aus_zustand_ohne_datei(self):
        """Eine fehlende Zustandsdatei darf die Frage nicht kosten."""
        p = Path(self.cfg.sub("state")) / "run.json"
        if p.is_file():
            p.unlink()
        self.assertEqual(ask.anbieter_aus_zustand(self.cfg), envs.ANBIETER_ABO)


if __name__ == "__main__":
    unittest.main()
