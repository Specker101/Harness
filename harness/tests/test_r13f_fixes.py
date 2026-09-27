"""Tests fuer R13f: Entscheidungsregel des Reviewers und der /ask-Kanal.

Punkt 1 (Entscheidungsregel): `ENTSCHIEDEN:` ist eine Meldung, kein Halt.
Punkt 2 (/ask): eigener Lauf, eigener Thread, und Lesen ist NUR in den beiden
Wurzeln erlaubt - `g:\\Harness\\secrets` ist verboten (gemessen: mit einem
ungebundenen `Read` war der Schluessel lesbar, docs/_ask_zugriff_regeln.txt).

Alles im Attrappenbetrieb: kein Netz, keine API-Kosten, kein Ghidra.
"""

from __future__ import annotations

import shutil
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import ask, protocol, reviewer                              # noqa: E402
from hx import orchestrator as orch_mod                             # noqa: E402
from hx.config import load_config                                   # noqa: E402
from hx.orchestrator import Orchestrator                            # noqa: E402
from hx.profiles import pfad_regeln, secrets_verbote                # noqa: E402
from hx.util import Log, ensure_dir                                 # noqa: E402

SECRET_ZEILE = r"g:\Harness\secrets\deepseek.key"


def _opt(cmd: list[str], name: str) -> list[str]:
    """Werte eines Schalters mit Werteliste (bis zum naechsten `--...`)."""
    i = cmd.index(name)
    out: list[str] = []
    for a in cmd[i + 1:]:
        if a.startswith("--"):
            break
        out.append(a)
    return out


def _mehrfach(cmd: list[str], name: str) -> list[str]:
    """Werte eines mehrfach angegebenen Schalters (z. B. `--add-dir A --add-dir B`)."""
    return [cmd[i + 1] for i, a in enumerate(cmd) if a == name and i + 1 < len(cmd)]


def _posix(p) -> str:
    return str(p).replace("\\", "/").rstrip("/")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__file__).resolve().parent / "_tmp_r13f"
        shutil.rmtree(self.tmp, ignore_errors=True)
        cfg = load_config()
        cfg.data["paths"]["root"] = str(ensure_dir(self.tmp / "harness"))
        cfg.data["paths"]["decomp"] = str(ensure_dir(self.tmp / "decomp"))
        cfg.data["paths"]["secrets"] = str(ensure_dir(self.tmp / "harness" / ".." / "secrets"))
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["telegram"]["allowlist_user_ids"] = []
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)
        self.orch = Orchestrator(cfg, self.log, mock=True,
                                 state_file=self.tmp / "harness" / "state" / "run.json")
        self.orch.say = lambda *a, **k: None

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


# ------------------------------------------------- Punkt 1: Entscheidungsregel
class TestEntscheidungsregel(Base):
    def test_entschieden_wird_gelesen(self):
        p = protocol.parse_offene_punkte(
            "TELEGRAM_SUMMARY:\n"
            "ENTSCHIEDEN: Naechster Batch nimmt D2Common statt D2Client\n"
            "HINWEIS: Anker steht bei 175\n")
        self.assertEqual(p["entschieden"],
                         ["Naechster Batch nimmt D2Common statt D2Client"])
        self.assertEqual(p["entscheidung"], [])

    def test_entschieden_steht_vor_der_entscheidung(self):
        kurz = protocol.offene_punkte_kurz({"entschieden": ["A gewaehlt"],
                                            "entscheidung": ["B ist deine Sache"]})
        self.assertTrue(kurz[0].startswith("Entschieden (Reviewer"),
                        f"erste Zeile war {kurz[0]!r}")
        self.assertIn("A gewaehlt", kurz[0])
        self.assertTrue(any("deine Sache" in z for z in kurz[1:]))

    def test_entschieden_haelt_das_gate_nicht_an(self):
        gate = {"summary": "TELEGRAM_SUMMARY:\nENTSCHIEDEN: ich nehme Weg A\n"}
        self.assertFalse(self.orch.gate_wait_decision(gate))
        self.assertEqual(self.orch.gate_offene_punkte(gate)["entschieden"],
                         ["ich nehme Weg A"])

    def test_entscheidung_noetig_haelt_an(self):
        gate = {"summary": "TELEGRAM_SUMMARY:\nENTSCHEIDUNG NOETIG: Ziel aendern?\n"}
        self.assertTrue(self.orch.gate_wait_decision(gate))

    def test_live_aufnahme_haelt_nicht_an(self):
        gate = {"summary": "WARTET AUF LIVE-AUFNAHME: Hoerprobe der Hupe\n"}
        self.assertFalse(self.orch.gate_wait_decision(gate))

    def test_gate_feld_traegt_entschieden(self):
        """Neue Gates tragen die Punkte als Feld - auch `entschieden`."""
        gate = {"summary": "egal",
                "offene_punkte": {"entschieden": ["Weg A"], "entscheidung": [],
                                  "frage": [], "live": []}}
        self.assertEqual(self.orch.gate_offene_punkte(gate)["entschieden"], ["Weg A"])
        self.assertFalse(self.orch.gate_wait_decision(gate))

    def test_status_zeigt_entschieden(self):
        zeilen = self.orch.offene_punkte_zeilen({"entschieden": ["Weg A"],
                                                 "entscheidung": [], "frage": [], "live": []})
        self.assertTrue(any("Entschieden" in z for z in zeilen))

    def test_reviewer_prompt_traegt_die_regel(self):
        text = (ROOT / "prompts" / "reviewer.md").read_text(encoding="utf-8")
        self.assertIn("ENTSCHIEDEN:", text)
        self.assertIn("Wer entscheidet was", text)
        for fall in ("Projektziel", "Verbotsliste", "Nutzerentscheidung"):
            self.assertIn(fall, text)
        self.assertIn("Veto", text)

    def test_review_parser_reicht_entschieden_durch(self):
        text = ("<TELEGRAM_SUMMARY>\n"
                "Ergebnis: gemessen\n"
                "ENTSCHIEDEN: nur eine Meldung\n"
                "ENTSCHEIDUNG NOETIG: Projektziel aendern?\n"
                "</TELEGRAM_SUMMARY>\n"
                "<DECISION>\nCONTINUE\n</DECISION>\n")
        r = protocol.parse_review(text)
        self.assertEqual(r.offene["entschieden"], ["nur eine Meldung"])
        self.assertEqual(r.offene["entscheidung"], ["Projektziel aendern?"])
        self.assertEqual(r.decision, "CONTINUE")
        # Aus der Zusammenfassung heraus muss die Bremse weiter greifen.
        self.assertTrue(self.orch.gate_wait_decision({"summary": r.summary}))


# --------------------------------------------------------------- Punkt 2: /ask
class TestAskRechte(Base):
    def test_lesen_ist_pfadgebunden(self):
        cmd = ask.build_command(self.cfg)
        erlaubt = _opt(cmd, "--allowedTools")
        for nackt in ("Read", "Grep", "Glob"):
            self.assertNotIn(nackt, erlaubt,
                             f"{nackt} ohne Pfadbindung erlaubt jedes Verzeichnis")
        # R13o: die Harness-Wurzel ist der Ordner UEBER `harness` (g:\Harness) -
        # er enthaelt die Belege in docs/ und deckt `harness/` mit ab.
        for wurzel in (self.cfg.harness_home, self.cfg.decomp):
            for rolle in ("Read", "Grep", "Glob"):
                self.assertIn(f"{rolle}(//{_posix(wurzel)}/**)", erlaubt)

    def test_secrets_ist_verboten(self):
        cmd = ask.build_command(self.cfg)
        erlaubt = _opt(cmd, "--allowedTools")
        verboten = _opt(cmd, "--disallowedTools")
        self.assertFalse([a for a in erlaubt if "secrets" in a], "secrets ist erlaubt!")
        self.assertTrue([a for a in verboten if "secrets" in a], "secrets fehlt im Verbot")
        self.assertIn(f"Read(//{_posix(self.cfg.secrets_dir)}/**)", verboten)

    def test_kein_schreibwerkzeug(self):
        verboten = _opt(ask.build_command(self.cfg), "--disallowedTools")
        for t in ask.VERBOTEN:
            self.assertIn(t, verboten)

    def test_beide_wurzeln_sind_angemeldet(self):
        cmd = ask.build_command(self.cfg)
        cfgd = _mehrfach(cmd, "--add-dir")
        self.assertIn(str(self.cfg.harness_home), cfgd)
        self.assertIn(str(self.cfg.decomp), cfgd)
        self.assertEqual(_opt(cmd, "--tools"), ["Read,Grep,Glob"])
        self.assertNotIn(str(self.cfg.secrets_dir), " ".join(cfgd))

    def test_reviewer_hat_dieselbe_bindung(self):
        cmd = reviewer.build_command(self.cfg, None, True)
        erlaubt = _opt(cmd, "--allowedTools")
        verboten = _opt(cmd, "--disallowedTools")
        for nackt in ("Read", "Grep", "Glob"):
            self.assertNotIn(nackt, erlaubt)
        self.assertFalse([a for a in erlaubt if "secrets" in a])
        self.assertTrue([a for a in verboten if "secrets" in a])
        self.assertIn(str(self.cfg.decomp), _mehrfach(cmd, "--add-dir"))

    def test_regelwerke(self):
        regeln = pfad_regeln((r"g:\Harness\harness", "g:/Silent Scope Decomp/"))
        self.assertIn("Read(//g:/Harness/harness/**)", regeln)
        self.assertIn("Grep(//g:/Silent Scope Decomp/**)", regeln)
        verbote = secrets_verbote(r"g:\Harness\secrets")
        self.assertIn("Read(//g:/Harness/secrets/**)", verbote)
        self.assertIn("Read(g:/Harness/secrets/**)", verbote)


class TestAskLauf(Base):
    def _fake(self, block: threading.Event | None = None):
        gesehen: dict = {}
        frei = threading.Event()

        def fake(cfg, log, frage, mock=False, zusatz="", neu=False):
            gesehen["frage"] = frage
            gesehen["mock"] = mock
            gesehen.setdefault("fragen", []).append(frage)
            gesehen.setdefault("neu", []).append(neu)
            frei.set()
            if block is not None:
                block.wait(10)
            return {"text": "Antwort auf die Frage", "hinweis": "(modell | 1 Anfragen | 1s)"}

        return fake, gesehen, frei

    def test_frage_laeuft_im_eigenen_thread(self):
        """`_do_ask` darf NICHT blockieren - sonst steht der Batch-Mitschnitt."""
        block = threading.Event()
        fake, gesehen, frei = self._fake(block)
        with mock.patch.object(orch_mod.askmod, "ask", fake):
            t0 = time.monotonic()
            self.orch._do_ask("Was ist die naechste Batch-Nummer?")
            dauer = time.monotonic() - t0
            self.assertLess(dauer, 1.0, "Rueckkehr hat blockiert")
            self.assertTrue(frei.wait(10), "Frage-Thread ist nicht gestartet")
            self.assertTrue(self.orch._ask_running)
            block.set()
            for _ in range(100):
                if not self.orch._ask_running:
                    break
                time.sleep(0.02)
        self.assertFalse(self.orch._ask_running)
        self.assertEqual(gesehen["frage"], "Was ist die naechste Batch-Nummer?")

    def test_zweite_frage_wird_eingereiht(self):
        """R13o: statt Ablehnung wird die zweite Frage eingereiht und danach gestellt."""
        block = threading.Event()
        fake, gesehen, _frei = self._fake(block)
        gesagt: list[str] = []
        self.orch.say = lambda t, *a, **k: gesagt.append(str(t))
        with mock.patch.object(orch_mod.askmod, "ask", fake):
            self.orch._do_ask("erste Frage")
            self.assertTrue(any("Frage laeuft" in g for g in gesagt), gesagt)
            self.orch._do_ask("zweite Frage")
            self.assertTrue(any("Frage eingereiht" in g for g in gesagt), gesagt)
            block.set()
            for _ in range(200):
                if not self.orch._ask_running:
                    break
                time.sleep(0.02)
        self.assertEqual(gesehen["fragen"], ["erste Frage", "zweite Frage"],
                         "Fragen muessen nacheinander und in Reihenfolge laufen")

    def test_leere_frage_erklaert_die_nutzung(self):
        gesagt: list[str] = []
        self.orch.say = lambda t, *a, **k: gesagt.append(str(t))
        self.orch._do_ask("   ")
        self.assertTrue(any("/ask <Frage>" in g for g in gesagt))
        self.assertFalse(self.orch._ask_running)
    def test_befehl_leitet_um(self):
        fake, gesehen, _frei = self._fake()
        with mock.patch.object(orch_mod.askmod, "ask", fake):
            self.orch.handle_command("/ask Warum Batch 175?")
            for _ in range(100):
                if gesehen.get("frage"):
                    break
                time.sleep(0.02)
        self.assertEqual(gesehen["frage"], "Warum Batch 175?")

    def test_fehler_wird_gemeldet_und_gibt_frei(self):
        gesagt: list[str] = []

        def kaputt(cfg, log, frage, mock=False, zusatz="", neu=False):
            raise RuntimeError("kein Token")

        self.orch.say = lambda t, *a, **k: gesagt.append(str(t))
        with mock.patch.object(orch_mod.askmod, "ask", kaputt):
            self.orch._do_ask("frage")
            for _ in range(100):
                if not self.orch._ask_running:
                    break
                time.sleep(0.02)
        self.assertFalse(self.orch._ask_running)
        self.assertTrue(any("FEHLGESCHLAGEN" in g for g in gesagt), gesagt)


if __name__ == "__main__":
    unittest.main()
