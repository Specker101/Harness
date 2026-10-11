"""Tests fuer R13bx-5: der REVIEW faehrt wahlweise auf dem Abo oder auf DeepSeek.

**Auftrag (Nutzer, 2026-10-10):** "wir sollten es wirklich so bauen jetzt, dass ich mit
einem Befehl wie /reviewer_swap auf DeepSeek wechseln kann und umgekehrt wieder auf Sonnet
bzw. Opus (das was er genommen hatte bisher fuer die Reviews)."

**Anlass (GEMESSEN):** das Claude-Wochenkontingent war am 10.10. erschoepft. Der
gescheiterte Review-Lauf hinterliess `runs/b332/review-limit-20261010-210706-v1.md` mit

    You've hit your weekly limit - resets Oct 13, 7am (Europe/Berlin)

Der Bruchpunkt war damit der **Reviewer** - der Worker faehrt laengst auf DeepSeek, und die
Aussensicht kann seit R13bx-1 umschalten. Der Review ist aber die STEUERUNG des Harness:
welchem Modell die naechste Instruktion anvertraut wird, entscheidet der Nutzer. Deshalb ist
die Umschaltung hier ein ausdruecklicher Befehl und KEINE Automatik.

Regeln, die diese Datei festhaelt:

* Der Anbieter gehoert zur **Sitzung**: ein Wechsel legt eine frische Reviewer-Session an
  (eigener Konfigordner je Anbieter, dort ist die fremde Kennung unbekannt).
* Die Uebergabe wird beim **alten** Anbieter erfragt - dort liegt die Sitzung.
* Auf DeepSeek heisst die Rolle fuer die Vorher-Pruefung `reviewer_ds`, nicht `reviewer`.
  Ein falscher Rollenname faellt LAUT auf, statt still durchzulaufen.
* Ohne Umschaltung bleibt alles wie bisher (B-Batch/Erkundung -> Opus, C-Batch -> Sonnet).
* `/reviewer_swap abo` setzt den Merker NICHT auf "abo", sondern ENTFERNT ihn - das Abo ist
  die Vorgabe, und ein stehengebliebener Merker wuerde eine spaetere Konfigurationsaenderung
  wirkungslos machen.

Alles im Attrappenbetrieb: kein Netz, keine API-Kosten, keine echten Sitzungen.
"""

from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import envs, reviewer                                          # noqa: E402
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


class _ReviewStub:
    """Minimaler ReviewResult-Ersatz fuer die Rotation (kein Lauf, kein Netz)."""

    def __init__(self, anbieter: str = reviewer.ANBIETER_ABO):
        self.rc = 0
        self.duration_s = 1.0
        self.text = ""
        self.session_id = "neu-stub"
        self.model_seen = ""
        self.model_expected = ""
        self.model_ok = True
        self.modell = ""
        self.modell_art = ""
        self.anbieter = anbieter
        self.limit_reached = False
        self.raw_path = ""
        self.parsed = None
        self.error = ""
        self.secret_hits = []
        self.rate_limit = {}

    def describe(self) -> str:
        return "stub"


class TestAnbieterWort(unittest.TestCase):
    def test_schreibweisen(self):
        for wort in ("abo", "ABO", "claude", "Opus", "sonnet", "pro", " abo "):
            self.assertEqual(reviewer.anbieter_wort(wort), reviewer.ANBIETER_ABO, msg=wort)
        for wort in ("deepseek", "DeepSeek", "ds", "flash"):
            self.assertEqual(reviewer.anbieter_wort(wort), reviewer.ANBIETER_DEEPSEEK, msg=wort)

    def test_leer_und_unbekannt_sind_kein_abo(self):
        """Der Aufrufer entscheidet, was ein fehlendes Wort bedeutet."""
        self.assertIsNone(reviewer.anbieter_wort(""))
        self.assertIsNone(reviewer.anbieter_wort("   "))
        self.assertIsNone(reviewer.anbieter_wort("quatsch"))


class TestReviewWahl(unittest.TestCase):
    def test_ohne_umschaltung_bleibt_es_beim_abo(self):
        w = reviewer.review_wahl(_cfg(), {}, 180)
        self.assertEqual(w["anbieter"], reviewer.ANBIETER_ABO)
        # B-Batch/Erkundung -> Opus (R13bo), Effort aus `reviewer_effort`.
        self.assertIn("opus", w["modell"].lower())
        self.assertEqual(w["effort"], "high")
        self.assertIn(w["art"], ("B", "C", "unklar"))

    def test_umschaltung_schlaegt_die_konfiguration(self):
        cfg = _cfg(reviewer_modell_b="claude-opus-5-5")
        w = reviewer.review_wahl(cfg, {"reviewer_anbieter": "deepseek"}, 180)
        self.assertEqual(w["anbieter"], reviewer.ANBIETER_DEEPSEEK)
        # Ohne eigenes DeepSeek-Modell gilt `model_worker` - EINE Quelle, kein zweiter Name.
        self.assertEqual(w["modell"], cfg.get("claude", "model_worker"))
        self.assertEqual(w["effort"], cfg.get("claude", "reviewer_effort_deepseek", "high"))
        # Die Abo-Arten (B/C) gibt es dort nicht.
        self.assertEqual(w["art"], "")

    def test_eigenes_deepseek_modell_hat_vorrang(self):
        cfg = _cfg(reviewer_modell_deepseek="deepseek-flash[1m]")
        w = reviewer.review_wahl(cfg, {"reviewer_anbieter": "ds"}, 180)
        self.assertEqual(w["modell"], "deepseek-flash[1m]")

    def test_unbekannter_merker_faellt_aufs_abo_zurueck(self):
        w = reviewer.review_wahl(_cfg(), {"reviewer_anbieter": "quatsch"}, 180)
        self.assertEqual(w["anbieter"], reviewer.ANBIETER_ABO)

    def test_grund_nennt_den_befehl(self):
        self.assertIn("/reviewer_swap",
                      reviewer.review_wahl(_cfg(), {"reviewer_anbieter": "deepseek"}, 1)["grund"])
        self.assertIn("/reviewer_swap",
                      reviewer.review_wahl(_cfg(), {"reviewer_anbieter": "abo"}, 1)["grund"])


class TestUmgebung(unittest.TestCase):
    """Die zwei Umgebungen duerfen sich nicht vermischen (E3)."""

    def setUp(self):
        self.cfg = _cfg(config_dir_reviewer="C:/tmp/cc-reviewer",
                        config_dir_reviewer_ds="C:/tmp/cc-reviewer-ds")

    def test_deepseek_umgebung_hat_kein_abo_token(self):
        env = envs.reviewer_deepseek_env(self.cfg, {}, "ds-token", "high")
        self.assertEqual(env["CLAUDE_CONFIG_DIR"], "C:/tmp/cc-reviewer-ds")
        self.assertEqual(env["ANTHROPIC_AUTH_TOKEN"], "ds-token")
        self.assertTrue(env.get("ANTHROPIC_BASE_URL"))
        self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN", env)
        self.assertEqual(env["CLAUDE_CODE_EFFORT_LEVEL"], "high")

    def test_eigener_konfigordner_nicht_der_des_abos(self):
        ds = envs.reviewer_deepseek_env(self.cfg, {}, "t", "high")
        abo = envs.reviewer_env(self.cfg, {}, "oauth")
        self.assertNotEqual(ds["CLAUDE_CONFIG_DIR"], abo["CLAUDE_CONFIG_DIR"])

    def test_precheck_je_rolle(self):
        ds = envs.reviewer_deepseek_env(self.cfg, {}, "t", "high")
        abo = envs.reviewer_env(self.cfg, {}, "oauth")
        self.assertEqual(envs.precheck(ds, "reviewer_ds"), [])
        self.assertEqual(envs.precheck(abo, "reviewer"), [])

    def test_falscher_rollenname_faellt_laut_auf(self):
        """Deshalb heisst die DeepSeek-Rolle `reviewer_ds` und nicht `reviewer`."""
        ds = envs.reviewer_deepseek_env(self.cfg, {}, "t", "high")
        self.assertTrue(envs.precheck(ds, "reviewer"))
        abo = envs.reviewer_env(self.cfg, {}, "oauth")
        self.assertTrue(envs.precheck(abo, "reviewer_ds"))

    def test_reviewer_ds_zaehlt_zu_den_deepseek_rollen(self):
        self.assertIn("reviewer_ds", envs.ROLLEN_DEEPSEEK)


class TestRunReviewAttrappe(unittest.TestCase):
    """Beide Wege durch `run_review` - inklusive der Modell-Nachpruefung."""

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13bx5"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "root")
        ensure_dir(self.root / "logs")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["paths"]["secrets"] = str(ensure_dir(self.tmp / "secrets"))
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)
        self._p = mock.patch.object(reviewer, "ensure_dir", self._ensure)
        self._p.start()

    def tearDown(self):
        self._p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _ensure(self, p):
        """Alle Schreibpfade des Reviewers in den Temp-Ordner umlenken."""
        q = self.tmp / Path(p).name
        q.mkdir(parents=True, exist_ok=True)
        return q

    def _review(self, **kw):
        return reviewer.run_review(self.cfg, self.log, "Auftrag", mock=True,
                                   stream_path=self.tmp / "reviewer.jsonl", batch=180, **kw)

    def test_abo_ist_die_vorgabe(self):
        res = self._review()
        self.assertEqual(res.anbieter, reviewer.ANBIETER_ABO)
        self.assertTrue(res.model_ok, res.error)
        self.assertIn("opus", str(res.model_expected).lower())

    def test_deepseek_lauf_nennt_das_gewaehlte_modell(self):
        res = self._review(anbieter="deepseek")
        self.assertEqual(res.anbieter, reviewer.ANBIETER_DEEPSEEK)
        self.assertEqual(res.model_expected, self.cfg.get("claude", "model_worker"))
        # Die Modell-Nachpruefung (R11-5c) muss auch hier greifen.
        self.assertIsNotNone(res.model_seen)
        self.assertTrue(res.model_ok, res.error)
        self.assertEqual(res.modell_art, "")

    def test_unbekannter_anbieter_wird_zum_abo(self):
        res = self._review(anbieter="quatsch")
        self.assertEqual(res.anbieter, reviewer.ANBIETER_ABO)


class Basis(unittest.TestCase):
    """Ein echter Orchestrator im Attrappenbetrieb (kein Netz, keine Sitzungen)."""

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13bx5_orc"
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


class TestBefehl(Basis):
    def test_nackter_befehl_schaltet_um_und_zurueck(self):
        self.befehl("/reviewer_swap")
        self.assertEqual(self.orch.state.data.get("reviewer_anbieter"),
                         reviewer.ANBIETER_DEEPSEEK)
        self.assertIn("DEEPSEEK", self.text().upper())
        self.assertIn("Kein Abo-Kontingent", self.text())
        self.befehl("/reviewer_swap")
        self.assertNotIn("reviewer_anbieter", self.orch.state.data)
        self.assertIn("ABO", self.text().upper())
        self.assertIn("Wochenkontingent", self.text())

    def test_ausdrueckliche_angabe(self):
        self.befehl("/reviewer_swap deepseek")
        self.assertEqual(self.orch.state.data.get("reviewer_anbieter"), "deepseek")
        self.befehl("/reviewer_swap abo")
        self.assertNotIn("reviewer_anbieter", self.orch.state.data)

    def test_kurzform_ds(self):
        self.befehl("/reviewer_swap ds")
        self.assertEqual(self.orch.state.data.get("reviewer_anbieter"), "deepseek")

    def test_unbekannter_zusatz_aendert_nichts(self):
        self.befehl("/reviewer_swap quatsch")
        self.assertNotIn("reviewer_anbieter", self.orch.state.data)
        self.assertIn("Nutzung", self.text())

    def test_abo_wird_entfernt_nicht_gesetzt(self):
        """Das Abo ist die Vorgabe - ein stehengebliebener Merker waere eine Falle."""
        self.befehl("/reviewer_swap deepseek")
        self.befehl("/reviewer_swap abo")
        self.assertFalse(self.orch.state.data.get("reviewer_anbieter"))

    def test_anbieter_und_statuszeile(self):
        self.assertEqual(self.orch.reviewer_anbieter(), reviewer.ANBIETER_ABO)
        self.befehl("/reviewer_swap deepseek")
        self.assertEqual(self.orch.reviewer_anbieter(), reviewer.ANBIETER_DEEPSEEK)
        self.assertEqual(self.orch.reviewer_effort_gewaehlt(),
                         self.cfg.get("claude", "reviewer_effort_deepseek", "high"))
        st = self.orch.status_text()
        self.assertIn("Review-Anbieter: DEEPSEEK", st)
        self.assertIn("/reviewer_swap", st)

    def test_modellzeile_je_anbieter(self):
        res = _ReviewStub(reviewer.ANBIETER_DEEPSEEK)
        res.model_seen = "deepseek-flash[1m]"
        zeile = self.orch.review_modell_zeile(res)
        self.assertIn("DeepSeek", zeile)
        self.assertIn("kein Abo-Kontingent", zeile)
        res2 = _ReviewStub(reviewer.ANBIETER_ABO)
        res2.model_seen = "claude-opus-5-5"
        res2.model_expected = "claude-opus-5-5"
        res2.modell_art = "B"
        self.assertIn("B-Batch/Erkundung", self.orch.review_modell_zeile(res2))


class TestSitzungswechsel(Basis):
    """Ein Anbieterwechsel legt eine frische Sitzung an - sonst zeigt --resume ins Leere."""

    def _prompt_hash(self) -> str:
        return reviewer.prompt_hash(self.cfg)

    def _review_mit_wechsel(self):
        stub = _ReviewStub()
        with mock.patch.object(self.orch, "review_context", lambda *a, **k: "Auftrag"), \
             mock.patch("hx.orchestrator.rv.build_prompt", lambda *a, **k: "Auftrag"), \
             mock.patch("hx.orchestrator.rv.run_review", lambda *a, **k: stub):
            return self.orch.do_review("batch_end", "snapshot")

    def test_gleicher_anbieter_rotiert_nicht(self):
        self.orch.state.reviewer_new_session("alt-id", prompt_hash=self._prompt_hash(),
                                             anbieter=reviewer.ANBIETER_ABO)
        self._review_mit_wechsel()
        self.assertFalse(self.orch._review_rotation)
        self.assertEqual(self.orch.state.data["reviewer"]["session_id"], "alt-id")

    def test_anbieterwechsel_rotiert_und_wird_verbucht(self):
        self.orch.state.reviewer_new_session("alt-id", prompt_hash=self._prompt_hash(),
                                             anbieter=reviewer.ANBIETER_ABO)
        self.befehl("/reviewer_swap deepseek")
        self._review_mit_wechsel()
        self.assertTrue(self.orch._review_rotation)
        rev = self.orch.state.data["reviewer"]
        self.assertNotEqual(rev["session_id"], "alt-id")
        self.assertEqual(rev["anbieter"], reviewer.ANBIETER_DEEPSEEK)

    def test_session_funktion_traegt_den_anbieter(self):
        """`reviewer_new_session` schreibt den Eintrag NEU - ein Feld daneben waere weg."""
        self.orch.state.reviewer_new_session("x", anbieter="deepseek")
        self.assertEqual(self.orch.state.data["reviewer"]["anbieter"], "deepseek")
        self.orch.state.reviewer_new_session("y")
        self.assertEqual(self.orch.state.data["reviewer"]["anbieter"], "")


class TestBeleg(Basis):
    def test_result_json_traegt_anbieter_und_effort(self):
        wd = ensure_dir(Path(self.cfg.sub("runs")) / "b180")
        write_text_atomic(wd / "result.json", json.dumps({"batch": 180}))
        res = _ReviewStub(reviewer.ANBIETER_DEEPSEEK)
        res.model_expected = "deepseek-flash[1m]"
        res.model_seen = "deepseek-flash[1m]"
        self.orch.review_in_result(180, res, "batch_end")
        daten = json.loads((wd / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(daten["review"]["anbieter"], "deepseek")
        self.assertEqual(daten["review"]["effort"],
                         self.cfg.get("claude", "reviewer_effort_deepseek", "high"))

    def test_abo_beleg_traegt_abo(self):
        wd = ensure_dir(Path(self.cfg.sub("runs")) / "b180")
        write_text_atomic(wd / "result.json", json.dumps({"batch": 180}))
        self.orch.review_in_result(180, _ReviewStub(reviewer.ANBIETER_ABO), "batch_end")
        daten = json.loads((wd / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(daten["review"]["anbieter"], "abo")


class TestLimitNurBeimAbo(unittest.TestCase):
    """Dieselbe Regel wie R13bx-4 - sonst holt die Umschaltung den Fehlalarm zurueck.

    Der Fall ist GEMESSEN: in B321 galt ein fehlerfreier DeepSeek-Lauf wegen des Wortes
    `quota` im englischen Denktext als Session-Limit; der Harness pausierte eine Stunde.
    Ein Reviewer, der als Limit-Fall gilt, gibt nichts frei (reiner Wartezustand).
    """

    DENKEN = ('{"type":"assistant","message":{"content":[{"type":"thinking",'
             '"thinking":"the reason for lowering was to save weekly quota"}]}}')
    # Der ECHTE Wortlaut aus `runs/b332/review-limit-20261010-210706-v1.md`.
    ECHTES_LIMIT = "You've hit your weekly limit - resets Oct 13, 7am (Europe/Berlin)"

    class _Res:
        def __init__(self, anbieter: str):
            self.anbieter = anbieter
            self.text = ""

    def test_deepseek_denktext_ist_kein_limit(self):
        r = self._Res(reviewer.ANBIETER_DEEPSEEK)
        self.assertFalse(reviewer.limit_erreicht(r, self.DENKEN, ""))
        r.text = self.DENKEN
        self.assertFalse(reviewer.limit_erreicht(r, "", ""))

    def test_abo_erkennt_das_echte_limit(self):
        r = self._Res(reviewer.ANBIETER_ABO)
        r.text = self.ECHTES_LIMIT
        self.assertTrue(reviewer.limit_erreicht(r, "", ""))

    def test_deepseek_auch_bei_echtem_limittext_nicht(self):
        r = self._Res(reviewer.ANBIETER_DEEPSEEK)
        for t in ("usage limit", "rate limit", "quota exceeded", self.ECHTES_LIMIT):
            self.assertFalse(reviewer.limit_erreicht(r, t, ""), msg=t)

    def test_ohne_anbieter_bleibt_die_pruefung_scharf(self):
        """Altaufrufer ohne `anbieter` gelten als Abo - und damit wie bisher."""
        r = self._Res("")
        self.assertTrue(reviewer.limit_erreicht(r, self.ECHTES_LIMIT, ""))


if __name__ == "__main__":
    unittest.main()
