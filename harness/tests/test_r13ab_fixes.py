"""Tests fuer R13ab (2026-09-28): Systemprompt-Ankunft, Rotation, `/fragen`-Abschnitte.

Anlass (Nutzerpruefung vor dem naechsten Review): die Pflichtzeile `B-SCHRITT:` fehlte in
den Reviews B209/B210, obwohl die Regel seit R13w in `prompts/reviewer.md` steht.

**Gemessen** (`tools/r13ab_probe_systemprompt.py`, Beleg `docs/_r13ab_probe.txt`): die
Claude-CLI liest `--append-system-prompt-file` bei **`--resume` nicht neu** - der zweite
Aufruf antwortete weiter `PROBE-A`, obwohl die Datei auf `PROBE-B` geaendert war. Der
Harness haengt die Datei zwar bei jedem Aufruf an (`reviewer.build_command`), bei
`--resume` kommt sie aber nicht an. Die laufende Reviewer-Session
(`bdc3a357…`, angelegt 2026-09-27T22:02:56Z) war aelter als die Regel (R13w,
2026-09-28 16:32:52Z = `1eee551`) - sie hat sie nie gesehen.

Folge (Punkt 3): der Hash von `prompts/reviewer.md` steht im Zustand, und bei Abweichung
rotieren (neue Session + Uebergabe). Dazu `state/ctl/rotate` / `hx.cli rotate` fuer den
Fall, dass ohne Prompt-Aenderung gewechselt werden soll.

Punkt 4: `ENTSCHIEDEN`-Zeilen des Reviewers stehen unter
"ZUR KENNTNIS (Veto per /claude <Kennung> moeglich)", nicht unter "OFFENE FRAGEN AN DICH".

Alles im Attrappenbetrieb (`mock=True`), Wegwerf-Verzeichnisse unter `tests/_tmp_r13ab`.
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

from hx import control, fragen, reviewer as rvmod                # noqa: E402
from hx.config import load_config                                # noqa: E402
from hx.orchestrator import Orchestrator                         # noqa: E402
from hx.util import Log, ensure_dir, write_text_atomic           # noqa: E402

ANKER = """# Workstream R1B - Beispiele

**Stand:** BATCH 209 (2026-09-28) - Beispielstand.
**Fertig:** **(1)** etwas fertig.
**Naechster Schritt:** **(a)** weiter.
**Offene Entscheidung:** **(1) ENTSCHIEDEN (Nutzer):** so bleibt es.
"""


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13ab"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.repo = ensure_dir(self.tmp / "decomp")
        self.ana = ensure_dir(self.repo / "analysis")
        write_text_atomic(self.ana / "r1b-workstream.md", ANKER)
        self.root = ensure_dir(self.tmp / "root")
        self.prompts = ensure_dir(self.tmp / "prompts")
        write_text_atomic(self.prompts / "reviewer.md", "# Rollenanweisung\nStand A\n")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.repo)
        cfg.data["paths"]["prompts"] = str(self.prompts)
        cfg.data["paths"]["secrets"] = str(ensure_dir(self.tmp / "secrets"))
        cfg.data["paths"]["harness_home"] = str(self.tmp)
        prof = ensure_dir(self.root / "profiles")
        for f in (ROOT / "profiles").glob("*.json"):
            shutil.copy2(f, prof / f.name)
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)
        self.orch = Orchestrator(cfg, self.log, mock=True,
                                 state_file=self.root / "state" / "run.json")
        self.orch.qroot = self.root
        self.gesagt: list[str] = []
        self.orch.say = lambda t="", *a, **k: self.gesagt.append(str(t))
        st = self.orch.state
        st.data["batch"] = 209
        st.data["last_batch_number"] = 209
        rd = ensure_dir(self.root / "runs" / "b209")
        write_text_atomic(rd / "antwort.md", "## 1) Uebernommener Stand\n(mock)\n")
        write_text_atomic(rd / "result.json", json.dumps(
            {"batch": 209, "profile": "none", "program": None, "rc": 0, "duration_s": 300.0,
             "killed_reason": None, "alarms": [], "stats": {"requests": 40},
             "cost_usd": 0.05, "model_seen": "deepseek-flash[1m]", "model_ok": True},
            indent=1))
        st.save()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def session_setzen(self, session_id: str = "alte-session-123", **weiter) -> None:
        rev = {"session_id": session_id, "reviews": 2, "force_rotate": False}
        rev.update(weiter)
        self.orch.state.data["reviewer"] = rev
        self.orch.state.save()

    def ein_durchlauf(self) -> dict:
        """Einen Review (Attrappe) fahren und zurueckgeben, was `run_review` bekam."""
        auf: dict = {}
        echt = rvmod.run_review

        def fake(cfg, log, prompt, **kw):
            auf.update(kw)
            return echt(cfg, log, prompt, **kw)

        with mock.patch.object(rvmod, "run_review", fake):
            with mock.patch.object(rvmod, "run_handover", lambda *a, **k: "UEBERGABE"):
                self.orch.do_review("batch_end", "(Snapshot)")
        return auf


# --------------------------------------------------- 1) Wie kommt der Prompt an?
class TestPromptAnkunft(Basis):
    def test_datei_wird_bei_jedem_aufruf_angehaengt(self):
        """Der Harness haengt sie IMMER an - auch beim Fortsetzen (gemessen reicht das
        allein aber nicht, s. Probe)."""
        for neu in (True, False):
            cmd = rvmod.build_command(self.cfg, "kennung-1", new_session=neu)
            self.assertIn("--append-system-prompt-file", cmd)
            self.assertTrue(cmd[cmd.index("--append-system-prompt-file") + 1]
                            .endswith("reviewer.md"))
            self.assertIn("--session-id" if neu else "--resume", cmd)

    def test_probe_belegt_dass_resume_die_datei_nicht_neu_liest(self):
        """Der Beleg der Messung liegt im Repo (docs/_r13ab_probe.txt)."""
        p = Path(ROOT).parent / "docs" / "_r13ab_probe.txt"
        self.assertTrue(p.is_file(), f"Probe-Beleg fehlt: {p}")
        text = p.read_text(encoding="utf-8")
        self.assertIn("PROBE-A", text)
        self.assertIn("PROBE-B", text)
        self.assertIn("NICHT an", text)


class TestPromptHash(Basis):
    def test_hash_folgt_dem_inhalt(self):
        h1 = rvmod.prompt_hash(self.cfg)
        self.assertEqual(len(h1), 12)
        write_text_atomic(self.prompts / "reviewer.md", "# Rollenanweisung\nStand B\n")
        h2 = rvmod.prompt_hash(self.cfg)
        self.assertNotEqual(h1, h2)
        self.assertEqual(rvmod.prompt_hash(self.cfg), h2, "gleicher Inhalt -> gleicher Hash")

    def test_ohne_datei_kein_hash(self):
        (self.prompts / "reviewer.md").unlink()
        self.assertEqual(rvmod.prompt_hash(self.cfg), "")

    def test_neue_session_speichert_den_hash(self):
        self.orch.state.reviewer_new_session("neu-1", prompt_hash="abc123abc123")
        self.assertEqual(self.orch.state.data["reviewer"]["prompt_hash"], "abc123abc123")


# ------------------------------------------------------------- 2) Rotation
class TestRotation(Basis):
    def test_geaenderter_prompt_erzwingt_eine_neue_session(self):
        self.session_setzen(prompt_hash="ffffffffffff")        # Hash einer alten Fassung
        auf = self.ein_durchlauf()
        self.assertTrue(auf.get("new_session"), "bei geaendertem Prompt muss rotiert werden")
        rev = self.orch.state.data["reviewer"]
        self.assertEqual(rev["prompt_hash"], rvmod.prompt_hash(self.cfg))
        self.assertTrue(any("Systemprompt geaendert" in s for s in self.gesagt),
                        f"Grund nicht gemeldet: {self.gesagt}")

    def test_gleicher_prompt_rotiert_nicht(self):
        self.session_setzen(prompt_hash=rvmod.prompt_hash(self.cfg))
        auf = self.ein_durchlauf()
        self.assertFalse(auf.get("new_session"), "ohne Aenderung wird fortgesetzt")
        self.assertIn("--resume", rvmod.build_command(self.cfg, auf.get("session_id"), False))

    def test_altbestand_ohne_hash_rotiert_einmal(self):
        """Eine Session aus einer aelteren Fassung hat keinen Hash - einmal wechseln,
        danach ist der Zustand vollstaendig (und es bleibt ruhig)."""
        self.session_setzen()
        auf = self.ein_durchlauf()
        self.assertTrue(auf.get("new_session"))
        self.assertTrue(any("Hash fehlt" in s for s in self.gesagt), self.gesagt)
        rev = self.orch.state.data["reviewer"]
        self.assertEqual(rev["prompt_hash"], rvmod.prompt_hash(self.cfg))
        auf2 = self.ein_durchlauf()
        self.assertFalse(auf2.get("new_session"), "der zweite Lauf bleibt in der Session")

    def test_rotation_nach_anzahl_bleibt_erhalten(self):
        self.session_setzen(reviews=int(self.cfg.get("reviewer", "rotation_after", 10)),
                            prompt_hash=rvmod.prompt_hash(self.cfg))
        auf = self.ein_durchlauf()
        self.assertTrue(auf.get("new_session"))


class TestRotateBefehl(Basis):
    def test_rotate_setzt_force_rotate(self):
        self.session_setzen(prompt_hash=rvmod.prompt_hash(self.cfg))
        control.put(self.cfg, "rotate", "cli")
        self.orch.check_local_control()
        self.assertTrue(self.orch.state.data["reviewer"]["force_rotate"])
        self.assertTrue(any("wechselt beim naechsten Review" in s for s in self.gesagt),
                        self.gesagt)
        self.assertFalse(control.pending(self.cfg), "die Steuerdatei ist verbraucht")

    def test_force_rotate_wird_beim_review_verbraucht(self):
        self.session_setzen(force_rotate=True, prompt_hash=rvmod.prompt_hash(self.cfg))
        auf = self.ein_durchlauf()
        self.assertTrue(auf.get("new_session"))
        self.assertFalse(self.orch.state.data["reviewer"].get("force_rotate"))
        self.assertTrue(any("auf Wunsch" in s for s in self.gesagt), self.gesagt)

    def test_ohne_session_kein_wechsel(self):
        self.orch.state.data.pop("reviewer", None)
        self.orch._do_rotate("cli")
        self.assertNotIn("force_rotate", self.orch.state.data.get("reviewer") or {})
        self.assertTrue(any("noch keine Reviewer-Session" in s for s in self.gesagt),
                        self.gesagt)


# --------------------------------------------------- 3) /fragen-Abschnitte
REVIEW = """<TELEGRAM_SUMMARY>
Ergebnis: solide.
ENTSCHEIDUNG NOETIG: Soll der Hybrid-Kern gegen Unicorn geprueft werden?
OFFENE FRAGE: Du nennst 21 Referenzstroeme, gezaehlt sind 20. Welcher fehlt?
WARTET AUF LIVE-AUFNAHME: 0x40B/0x40E/0x40F
ENTSCHIEDEN: Zuerst wird der Interpreter streng gemacht.
ENTSCHIEDEN: Die A2-Altposten verschieben sich auf den naechsten C-Batch.
</TELEGRAM_SUMMARY>
<DS_INSTRUCTION>
Batch 210 - Beispiel
</DS_INSTRUCTION>
"""


class TestFragenAbschnitte(Basis):
    def setUp(self):
        super().setUp()
        d = ensure_dir(self.root / "runs" / "b211")
        write_text_atomic(d / "review.md", REVIEW)
        write_text_atomic(d / "harness-facts.md",
                          "- Review: bewertet wird Batch 210; die Instruktion gilt fuer 211\n")

    def test_entschieden_steht_zur_kenntnis(self):
        text = fragen.fragen_text(self.cfg)
        self.assertIn("ZUR KENNTNIS (Veto per /claude <Kennung> moeglich)", text)
        offene = text.split("ZUR KENNTNIS")[0].split("OFFENE FRAGEN AN DICH")[1]
        kenntnis = text.split("ZUR KENNTNIS")[1].split("ANTWORTEN")[0]
        # Die beiden ENTSCHIEDEN-Zeilen stehen NUR unten.
        self.assertNotIn("Zuerst wird der Interpreter streng", offene)
        self.assertNotIn("A2-Altposten", offene)
        self.assertIn("Zuerst wird der Interpreter streng", kenntnis)
        self.assertIn("A2-Altposten", kenntnis)

    def test_echte_fragen_bleiben_oben(self):
        text = fragen.fragen_text(self.cfg)
        offene = text.split("ZUR KENNTNIS")[0].split("OFFENE FRAGEN AN DICH")[1]
        self.assertIn("ENTSCHEIDUNG NOETIG", offene)
        self.assertIn("OFFENE FRAGE", offene)
        self.assertIn("WARTET AUF LIVE-AUFNAHME", offene)

    def test_kennungen_bleiben_antwortbar(self):
        text = fragen.fragen_text(self.cfg)
        for kennung in ("R210-1", "R210-2", "R210-3", "R210-4", "R210-5"):
            self.assertIn(kennung, text)
        p = fragen.nachschlagen(self.cfg, "R210-5")
        self.assertIsNotNone(p)
        self.assertTrue(p.get("zur_kenntnis"))
        vor = fragen.nachricht_vorbereiten(self.cfg, "R210-5 Widerspruch: bitte anders")
        self.assertTrue(vor["ok"])
        self.assertIn("R210-5", vor["text"])

    def test_status_zaehlt_getrennt(self):
        zeile = fragen.status_zeilen(self.cfg)[0]
        # A1 (Ankerposten) + Entscheidung + Frage + Live-Aufnahme = 4 echte Fragen
        self.assertIn("4 offen", zeile)
        self.assertIn("2 zur Kenntnis", zeile)
        self.assertIn("(zur Kenntnis: R210-4, R210-5)", zeile)
        self.assertNotIn("6 offen", zeile)
        self.assertNotIn("R210-4", zeile.split("(zur Kenntnis")[0],
                         "die ENTSCHIEDEN-Eintraege zaehlen nicht als offene Frage")

    def test_antwortbeispiel_ist_eine_echte_frage(self):
        text = fragen.fragen_text(self.cfg)
        beispiel = [z for z in text.splitlines() if "z. B." in z][0]
        self.assertNotIn("R210-4", beispiel)
        self.assertNotIn("R210-5", beispiel)
        offene = text.split("ZUR KENNTNIS")[0]
        self.assertTrue(any(k in beispiel for k in ("A1", "R210-1")), beispiel)
        self.assertIn("A1", offene)


if __name__ == "__main__":
    unittest.main()
