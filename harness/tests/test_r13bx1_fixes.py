"""Tests fuer R13bx-1: die Aussensicht faehrt auf DeepSeek, wenn das Abo knapp wird.

Auftrag (Nutzer, 2026-10-09): "Das Harness muss in der Lage sein, die Aussensicht ueber
DeepSeek zu machen statt ueber Opus. Das sollte dann immer umswitchen, wenn das
Wochenkontingent 80 % erreicht hat oder mehr." Denkstufe wie die Reviews (`high`);
Anbieter-Entscheidungen des Nutzers: ohne Messwert bleibt es beim Abo, nach einem
gescheiterten DeepSeek-Lauf wird wieder DeepSeek versucht (KEIN Rueckfall auf Opus),
Kosten des DeepSeek-Laufs werden NICHT gebucht.

GEMESSEN vor dem Einbau (Belege `docs/_effort_probe.txt`, `docs/_beleg_probe.txt`):
  * die Denkstufe kommt auf dem DeepSeek-Endpunkt an (`high` wie `max`);
  * `result.modelUsage` nennt `deepseek-flash[1m]` - kein stilles Mapping;
  * `max` findet nicht mehr Befunde als `high` und braucht ~47 % mehr Zeit -> `high`.
  * Der Mitschnitt traegt die Denkstufe NICHT (kein `effort`/`perTurnEffort` in
    `runs/b313/meta.jsonl`) - deshalb steht sie in `meta.md`/`meta.json`.

Alles im Attrappenbetrieb: kein Netz, keine API-Kosten.
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import aussensicht, envs                                       # noqa: E402
from hx.config import load_config                                      # noqa: E402
from hx.retention import _weg                                          # noqa: E402
from hx.state import State                                             # noqa: E402
from hx.util import Log, ensure_dir                                    # noqa: E402


def _cfg(**claude) -> object:
    """Frische Konfiguration - je Aufruf neu, damit sich Tests nicht beeinflussen."""
    cfg = load_config()
    for k, v in claude.items():
        cfg.data.setdefault("claude", {})[k] = v
    return cfg


def stand(fh: float | None = None, sd: float | None = None) -> dict:
    """Ein `lies_rate_limit`-Stand mit den zwei Fenstern (None = Fenster fehlt)."""
    fenster = {}
    if fh is not None:
        fenster["five_hour"] = {"utilization": fh, "resetsAt": 1}
    if sd is not None:
        fenster["seven_day"] = {"utilization": sd, "resetsAt": 2}
    return {"info": {"unifiedWindows": fenster}}


# --------------------------------------------------------------- die Entscheidung
class TestModellWahl(unittest.TestCase):
    def test_ohne_messwert_bleibt_es_beim_abo(self):
        w = aussensicht.modell_wahl(_cfg(), stand=stand())
        self.assertEqual(w["anbieter"], "abo")
        self.assertIn("kein Messwert", w["grund"])
        self.assertIsNone(w["woche"])

    def test_woche_ueber_der_schwelle_schaltet_um(self):
        w = aussensicht.modell_wahl(_cfg(), stand=stand(0.02, 0.87))
        self.assertEqual(w["anbieter"], "deepseek")
        self.assertEqual(w["grund"], "Wochenkontingent 87 % >= 80 %")
        self.assertAlmostEqual(w["woche"], 0.87)

    def test_woche_unter_der_schwelle_bleibt_abo(self):
        w = aussensicht.modell_wahl(_cfg(), stand=stand(0.4, 0.62))
        self.assertEqual(w["anbieter"], "abo")
        self.assertEqual(w["grund"], "Wochenkontingent 62 % < 80 %")

    def test_die_sitzung_schaltet_nicht_um(self):
        """Nur die WOCHE zaehlt - die 5-h-Sitzung erholt sich von selbst."""
        w = aussensicht.modell_wahl(_cfg(), stand=stand(0.95, 0.2))
        self.assertEqual(w["anbieter"], "abo")
        self.assertAlmostEqual(w["woche"], 0.2)

    def test_genau_auf_der_schwelle_schaltet_um(self):
        self.assertEqual(aussensicht.modell_wahl(_cfg(), stand=stand(0.0, 0.8))["anbieter"],
                         "deepseek")

    def test_nie_schaltet_auch_bei_voller_woche_nicht_um(self):
        cfg = _cfg()
        cfg.data["meta"]["aussensicht_deepseek"] = "nie"
        w = aussensicht.modell_wahl(cfg, stand=stand(1.0, 0.99))
        self.assertEqual(w["anbieter"], "abo")
        self.assertIn("nie", w["grund"])

    def test_immer_schaltet_ohne_jeden_messwert(self):
        cfg = _cfg()
        cfg.data["meta"]["aussensicht_deepseek"] = "immer"
        w = aussensicht.modell_wahl(cfg, stand=stand())
        self.assertEqual(w["anbieter"], "deepseek")
        self.assertIn("immer", w["grund"])

    def test_unbekannter_schalter_gilt_als_auto(self):
        cfg = _cfg()
        cfg.data["meta"]["aussensicht_deepseek"] = "vielleicht"
        self.assertEqual(aussensicht.deepseek_schalter(cfg), "auto")
        self.assertEqual(aussensicht.modell_wahl(cfg, stand=stand(0.0, 0.9))["anbieter"],
                         "deepseek")

    def test_schwelle_kommt_aus_der_konfiguration(self):
        cfg = _cfg()
        cfg.data["meta"]["aussensicht_deepseek_ab"] = 0.5
        self.assertEqual(aussensicht.modell_wahl(cfg, stand=stand(0.0, 0.6))["anbieter"],
                         "deepseek")
        self.assertEqual(aussensicht.modell_wahl(cfg, stand=stand(0.0, 0.4))["anbieter"],
                         "abo")

    def test_unbrauchbare_schwelle_faellt_auf_die_vorgabe(self):
        for wert in ("viel", 0, -1, 2, None):
            cfg = _cfg()
            cfg.data["meta"]["aussensicht_deepseek_ab"] = wert
            self.assertAlmostEqual(aussensicht.umschalt_schwelle(cfg), 0.8, msg=str(wert))

    def test_modellnamen_kommen_aus_der_konfiguration(self):
        """Ohne eigenen Schluessel gilt der Modellname des WORKERS - eine Quelle."""
        cfg = _cfg()
        cfg.data["claude"].pop("aussensicht_modell_deepseek", None)
        cfg.data["claude"]["model_worker"] = "deepseek-flash[1m]"
        self.assertEqual(aussensicht.modell_wahl(cfg, stand=stand(0.0, 0.9))["modell"],
                         "deepseek-flash[1m]")
        cfg.data["claude"]["aussensicht_modell_deepseek"] = "deepseek-v4-pro"
        self.assertEqual(aussensicht.modell_wahl(cfg, stand=stand(0.0, 0.9))["modell"],
                         "deepseek-v4-pro")

    def test_abo_modell_bleibt_aussensicht_modell(self):
        cfg = _cfg(aussensicht_modell="claude-opus-5-5")
        w = aussensicht.modell_wahl(cfg, stand=stand(0.0, 0.1))
        self.assertEqual(w["modell"], "claude-opus-5-5")
        self.assertEqual(w["effort"], "")          # Abo-Stufe kommt aus reviewer_env

    def test_denkstufe_kommt_aus_eigenem_schluessel(self):
        """`aussensicht_effort` ist bewusst NICHT `reviewer_effort`."""
        cfg = _cfg()
        cfg.data["claude"]["reviewer_effort"] = "low"
        cfg.data["claude"]["aussensicht_effort"] = "xhigh"
        self.assertEqual(aussensicht.modell_wahl(cfg, stand=stand(0.0, 0.9))["effort"],
                         "xhigh")
        cfg.data["claude"].pop("aussensicht_effort")
        self.assertEqual(aussensicht.modell_wahl(cfg, stand=stand(0.0, 0.9))["effort"],
                         "high")


# --------------------------------------------------------------- Umgebung und Befehl
class TestUmgebung(unittest.TestCase):
    def test_deepseek_umgebung_hat_eigenen_ordner_und_stufe(self):
        env = envs.aussensicht_deepseek_env(_cfg(), os.environ, "dummy", "max")
        self.assertEqual(env["CLAUDE_CODE_EFFORT_LEVEL"], "max")
        self.assertEqual(env["ANTHROPIC_AUTH_TOKEN"], "dummy")
        self.assertNotEqual(env["CLAUDE_CONFIG_DIR"],
                            str(load_config().get("claude", "config_dir_worker")))
        self.assertIn("cc-aussensicht", env["CLAUDE_CONFIG_DIR"])
        self.assertEqual(envs.precheck(env, "aussensicht"), [])

    def test_precheck_aussensicht_meldet_ein_abo_token(self):
        env = envs.aussensicht_deepseek_env(_cfg(), os.environ, "dummy", "high")
        env["CLAUDE_CODE_OAUTH_TOKEN"] = "abo"
        self.assertIn("CLAUDE_CODE_OAUTH_TOKEN", envs.precheck(env, "aussensicht"))

    def test_worker_umgebung_ist_unveraendert(self):
        cfg = load_config()
        env = envs.worker_env(cfg, os.environ, "dummy")
        self.assertEqual(env["CLAUDE_CONFIG_DIR"], str(cfg.get("claude", "config_dir_worker")))
        self.assertEqual(env["CLAUDE_CODE_EFFORT_LEVEL"], "high")
        self.assertEqual(envs.precheck(env, "worker"), [])

    def test_reviewer_precheck_verbietet_weiter_deepseek(self):
        env = envs.reviewer_env(_cfg(), os.environ, "abo")
        env["ANTHROPIC_AUTH_TOKEN"] = "ds"
        self.assertIn("ANTHROPIC_AUTH_TOKEN", envs.precheck(env, "reviewer"))

    def test_build_command_nimmt_das_gewaehlte_modell(self):
        cmd = aussensicht.build_command(_cfg(), modell="deepseek-flash[1m]")
        self.assertEqual(cmd[cmd.index("--model") + 1], "deepseek-flash[1m]")

    def test_build_command_ohne_modell_nimmt_die_konfiguration(self):
        """Altaufrufer (und `tools/schatten_aussensicht.py`) bleiben gueltig."""
        cfg = _cfg(aussensicht_modell="claude-opus-5-5")
        cmd = aussensicht.build_command(cfg)
        self.assertEqual(cmd[cmd.index("--model") + 1], "claude-opus-5-5")


# --------------------------------------------------------------- Beleg
class TestBeleg(unittest.TestCase):
    def _ergebnis(self, **felder):
        res = aussensicht.Ergebnis()
        res.rc, res.modell = 0, "deepseek-flash[1m]"
        res.anbieter, res.modell_soll = "deepseek", "deepseek-flash[1m]"
        res.effort, res.umschalt_grund = "high", "Wochenkontingent 87 % >= 80 %"
        res.woche_anteil = 0.87
        for k, v in felder.items():
            setattr(res, k, v)
        return res

    def test_zeile_nennt_modell_anbieter_stufe_und_woche(self):
        zeile = aussensicht.modell_zeile(self._ergebnis())
        self.assertTrue(zeile.startswith("- Modell: deepseek-flash[1m] (DeepSeek, "
                                         "Denkstufe high, Woche 87 %)"), zeile)
        self.assertIn("Wochenkontingent 87 % >= 80 %", zeile)
        self.assertNotIn("laut Sitzung", zeile)

    def test_abweichendes_modell_wird_genannt_nicht_verschwiegen(self):
        zeile = aussensicht.modell_zeile(self._ergebnis(modell="deepseek-v4-pro"))
        self.assertIn("laut Sitzung: deepseek-v4-pro", zeile)

    def test_zeile_beim_abo_ohne_stufe_und_ohne_woche(self):
        res = self._ergebnis(anbieter="abo", modell_soll="claude-opus-5-5", effort="",
                             woche_anteil=None, umschalt_grund="kein Messwert im "
                             "Wochenfenster - ohne Messung keine Umschaltung "
                             "(der naechste Abo-Lauf fuellt logs/rate-limit.json)")
        zeile = aussensicht.modell_zeile(res)
        self.assertIn("(Claude-Abo)", zeile)
        self.assertNotIn("Denkstufe", zeile)

    def test_describe_nennt_den_anbieter(self):
        self.assertIn("(deepseek)", self._ergebnis().describe())


class TestBericht(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__file__).resolve().parent / "_tmp_r13bx1"
        _weg(self.tmp)
        self.root = ensure_dir(self.tmp / "harness")
        self.decomp = ensure_dir(self.tmp / "decomp")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.decomp)
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)

    def tearDown(self):
        _weg(self.tmp)

    def _res(self) -> aussensicht.Ergebnis:
        res = aussensicht.Ergebnis()
        res.rc, res.dauer_s, res.modell = 0, 210.0, "deepseek-flash[1m]"
        res.summary = "(Attrappe) geprueft."
        res.anbieter, res.modell_soll = "deepseek", "deepseek-flash[1m]"
        res.effort, res.umschalt_grund = "high", "Wochenkontingent 87 % >= 80 %"
        res.woche_anteil = 0.87
        return res

    def test_bericht_traegt_die_modellzeile_hinter_dem_nutzerlimit(self):
        text = aussensicht.bericht(self.cfg, 321, "Test", self._res(), {}, [])
        kopf = text.splitlines()[:8]
        index = next(i for i, z in enumerate(kopf) if z.startswith("- Lauf:"))
        # R13bw-15 verlangt die Nutzerlimit-Zeile DIREKT hinter `- Lauf:` - die
        # Modellzeile kommt danach, damit diese Zusage unverletzt bleibt.
        self.assertTrue(kopf[index + 1].startswith("- Nutzerlimit:"), kopf[index + 1])
        self.assertTrue(kopf[index + 2].startswith("- Modell: deepseek-flash[1m]"),
                        kopf[index + 2])

    def test_meta_json_traegt_die_wahl_maschinenlesbar(self):
        with mock.patch.object(aussensicht, "ablage_pruefen"):
            pfad = aussensicht.bericht_schreiben(self.cfg, 321, "Test", self._res(), {}, [])
        assert pfad                          # Bericht geschrieben (Pfad unbenutzt)
        d = json.loads((aussensicht.json_pfad(self.cfg, 321)).read_text(encoding="utf-8"))
        self.assertEqual(d["anbieter"], "deepseek")
        self.assertEqual(d["modell_soll"], "deepseek-flash[1m]")
        self.assertEqual(d["effort"], "high")
        self.assertAlmostEqual(d["woche_anteil"], 0.87)
        self.assertIn(">= 80 %", d["umschalt_grund"])


# --------------------------------------------------------------- Takt je Anbieter
class TestTaktNachAnbieter(unittest.TestCase):
    """R13bx (Nutzerentscheid 2026-10-10): auf DeepSeek alle 2 Batches, auf dem Abo alle 4."""

    def _cfg(self, **meta):
        cfg = load_config()
        cfg.data.setdefault("meta", {})
        cfg.data["meta"]["aussensicht_takt"] = 4
        cfg.data["meta"]["aussensicht_takt_deepseek"] = 2
        for k, v in meta.items():
            cfg.data["meta"][k] = v
        return cfg

    def test_abo_bleibt_bei_vier(self):
        self.assertEqual(aussensicht.takt(self._cfg()), 4)
        self.assertEqual(aussensicht.takt(self._cfg(), "abo"), 4)

    def test_deepseek_faehrt_alle_zwei(self):
        self.assertEqual(aussensicht.takt(self._cfg(), "deepseek"), 2)

    def test_grenzen_kennt_beide_takte(self):
        cfg = self._cfg()
        self.assertEqual(int(aussensicht.grenzen(cfg)["every_batches"]), 4)
        self.assertEqual(int(aussensicht.grenzen(cfg, "deepseek")["every_batches"]), 2)
        # der Anbieter darf NUR den Takt beeinflussen
        self.assertEqual(aussensicht.grenzen(cfg, "deepseek")["max_befunde"],
                         aussensicht.grenzen(cfg)["max_befunde"])

    def test_fehlender_deepseek_schluessel_faellt_auf_den_abo_takt(self):
        cfg = load_config()
        cfg.data["meta"].pop("aussensicht_takt_deepseek", None)
        cfg.data["meta"]["aussensicht_takt"] = 4
        self.assertEqual(aussensicht.takt(cfg, "deepseek"), 4)

    def test_ohne_jeden_schluessel_gilt_die_vorgabe_zwei(self):
        cfg = load_config()
        for k in ("aussensicht_takt_deepseek", "aussensicht_takt", "every_batches"):
            cfg.data["meta"].pop(k, None)
        self.assertEqual(aussensicht.takt(cfg, "deepseek"),
                         aussensicht.TAKT_DEEPSEEK_VORGABE)
        self.assertEqual(aussensicht.takt(cfg), int(aussensicht.STANDARD["every_batches"]))

    def test_bilanzzeile_nennt_beide_takte(self):
        """Sonst zeigte die Bilanz "alle 4", waehrend die Aussensicht alle 2 laeuft."""
        self.assertIn("Takt: alle 4 Batches (DeepSeek: alle 2)",
                      aussensicht.zeile(self._cfg()))

    def test_bilanzzeile_bleibt_einfach_bei_gleichem_takt(self):
        self.assertIn("Takt: alle 4 Batches)",
                      aussensicht.zeile(self._cfg(aussensicht_takt_deepseek=4)))


class TestFaelligMitTakt(unittest.TestCase):
    """Der Takt muss durch `faellig` durchschlagen - dort wird er benutzt."""

    def setUp(self):
        self.tmp = Path(__file__).resolve().parent / "_tmp_r13bx1_takt"
        _weg(self.tmp)
        self.root = ensure_dir(self.tmp / "harness")
        self.decomp = ensure_dir(self.tmp / "decomp")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.decomp)
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["meta"]["aussensicht_takt"] = 4
        cfg.data["meta"]["aussensicht_takt_deepseek"] = 2
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)

    def tearDown(self):
        _weg(self.tmp)

    def _state(self, batch: int, letzte: int):
        s = State(self.root / "state" / "run.json")
        s.data["batch"] = batch
        s.data["meta"] = {"letzter_lauf_batch": letzte, "geprueft_batch": 0}
        return s

    def _takt_grund(self, batch: int, anbieter=None) -> list[str]:
        kwargs = {} if anbieter is None else {"anbieter": anbieter}
        gruende = aussensicht.faellig(self.cfg, self._state(batch, 300), log=self.log, **kwargs)
        return [g for g in gruende if "Batches" in g]

    def test_abo_feuert_erst_nach_vier_batches(self):
        self.assertEqual(self._takt_grund(303, "abo"), [])
        self.assertTrue(self._takt_grund(304, "abo"))

    def test_deepseek_feuert_schon_nach_zwei_batches(self):
        self.assertEqual(self._takt_grund(301, "deepseek"), [])
        gruende = self._takt_grund(302, "deepseek")
        self.assertTrue(gruende)
        self.assertIn("alle 2 Batches", gruende[0])
        self.assertIn("[DeepSeek-Takt]", gruende[0])

    def test_ohne_anbieter_gilt_der_abo_takt(self):
        self.assertEqual(self._takt_grund(302), [])
        self.assertTrue(self._takt_grund(304))


if __name__ == "__main__":
    unittest.main()
