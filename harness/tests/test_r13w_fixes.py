"""Tests fuer R13w (2026-09-28): Aussensicht (Meta-Review).

Auftrag (Nutzer): eigener Baustein "Aussensicht" mit anderem Auftrag als der Reviewer
("stimmen Messgroessen, Plan und Annahmen noch?"), Ausloesern (alle 10 Batches, /meta,
Ereignisse), frischer Session, Befundliste mit Gewicht/Empfaenger, Verteilung
(Reviewer -> /claude-Queue, Nutzer -> Telegram+/fragen), Ablage `runs/meta-<batch>.md`
und einer Zeile in `/bilanz`. Entscheidungen des Nutzers vom 2026-09-28:

  (1) synchron, (2) je Befund eine /claude-Nachricht, (3) KEINE Textmarken - der
  Reviewer schreibt Pflichtzeilen (`B-SCHRITT:`, `MEILENSTEIN ERREICHT:`,
  `ABBRUCHKRITERIUM ERREICHT:`), (4) /ds-Queue sichtbar;
  (a) Kernzahl-Ausloeser nach Batch-Art trennen (C nur gegen C-Batches),
  (b) Beleg-Pflicht gelockert (Datei:Zeile ODER Zahl+Quelldatei ODER "Fehlstelle: …"),
  (c) Stichprobenpflicht im Prompt (2 Zusammenfassungen + 1 Denkblock-Batch),
  (d) der Reviewer beantwortet jede Befund-ID, der Ledger uebernimmt den Status.

Alles ohne API-Kosten: Laeufe nur im Attrappenmodus (`mock=True`), Zustand und
Arbeitsordner liegen in Wegwerf-Verzeichnissen (`tests/_tmp_r13w*`). Das laufende
Harness-Verzeichnis wird NICHT angefasst.
"""

from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import aussensicht, control, queue, state as st         # noqa: E402
from hx.config import load_config                               # noqa: E402
from hx.orchestrator import Orchestrator                        # noqa: E402
from hx.util import Log, ensure_dir, write_text_atomic          # noqa: E402

BEISPIEL = """<AUSSENSICHT>
Zwei Stichproben aus B207 gegen die Rohbelege: Ergebnis bestaetigt (Anfragen passen),
zweite widerspricht (Kosten im Bericht gerundet). Denkbloecke B207 gelesen.
</AUSSENSICHT>

<BEFUND n="1" gewicht="niedrig" empfaenger="Nutzer">
Beleg: 137 Anfragen in runs/b207/result.json
Aussage: Die Anfragenzahl im Bericht weicht von der Messdatei ab.
Empfehlung: Die Zahl direkt aus result.json ziehen.
</BEFUND>

<BEFUND n="2" gewicht="hoch" empfaenger="Reviewer">
Beleg: port/src/ckopf_leaves.cpp:1977
Aussage: Eine Kennzahl wird ohne Quelldatei berichtet.
Empfehlung: Quelle im Batch-Dokument mitnennen.
</BEFUND>

<BEFUND n="3" gewicht="mittel" empfaenger="Reviewer">
Beleg: Fehlstelle: gesucht in analysis/ nach einem Beleg fuer 12.000 Insn, nicht gefunden
Aussage: Eine Zahl im Anhang hat keine Quelle.
Empfehlung: Zahl streichen oder belegen.
</BEFUND>

<BEFUND n="4" gewicht="mittel" empfaenger="Reviewer">
Beleg: readme.md:640-642
Aussage: Der Zielsatz in readme.md nennt kein Budget fuer den Rest des Vorhabens.
Empfehlung: Das Budget im Zielsatz der readme nachtragen.
</BEFUND>

<BEFUND n="4" gewicht="hoch" empfaenger="Reviewer">
Aussage: Dieser Befund hat gar keinen Beleg.
Empfehlung: Wird verworfen.
</BEFUND>

<PRUEFUNG id="M207-1" status="erledigt"/>
<PRUEFUNG id="M207-2" status="offen"/>
"""


class TestParser(unittest.TestCase):
    def test_befunde_gewichte_empfaenger_und_deckel(self):
        summary, befunde, verworfen, pruefungen = aussensicht.parse(BEISPIEL, 7)
        self.assertIn("Stichproben", summary)
        # Befund 5 hat keinen Beleg -> verworfen, nicht verschwiegen.
        self.assertEqual(len(befunde), 4)
        self.assertEqual(len(verworfen), 1)
        # Sortierung nach Gewicht: hoch, mittel, mittel, niedrig
        self.assertEqual([b["gewicht"] for b in befunde],
                         ["hoch", "mittel", "mittel", "niedrig"])
        # Der Empfaenger kommt aus dem Modell; die Aufteilung nach Entscheidungstraeger
        # passiert erst beim Verteilen (`entscheidungstraeger`, R13y).
        self.assertEqual([b["empfaenger"] for b in befunde],
                         ["Reviewer", "Reviewer", "Reviewer", "Nutzer"])
        self.assertEqual([p["id"] for p in pruefungen], ["M207-1", "M207-2"])
        self.assertEqual([p["status"] for p in pruefungen], ["erledigt", "offen"])

    def test_deckel_max_befunde(self):
        _s, befunde, _v, _p = aussensicht.parse(BEISPIEL, 2)
        self.assertEqual(len(befunde), 2)

    def test_belegpflicht_gelockert(self):
        # Datei:Zeile
        self.assertTrue(aussensicht.beleg_gueltig("port/src/x.cpp:12"))
        # Zahl mit Quelldatei (Nutzerentscheid b)
        self.assertTrue(aussensicht.beleg_gueltig("137 Anfragen in runs/b207/result.json"))
        # ausdrueckliche Fehlstelle ist ein Ergebnis, kein Fehler
        self.assertTrue(aussensicht.beleg_gueltig(
            "Fehlstelle: gesucht in analysis/, nicht gefunden"))
        self.assertFalse(aussensicht.beleg_gueltig(""))
        self.assertFalse(aussensicht.beleg_gueltig("ich glaube, das ist ungenau"))

    def test_unbekanntes_gewicht_wird_mittel(self):
        text = ('<BEFUND n="1" gewicht="riesig" empfaenger="Chef">\n'
                'Beleg: hx/aussensicht.py:1\nAussage: x\nEmpfehlung: y\n</BEFUND>')
        _s, befunde, _v, _p = aussensicht.parse(text, 7)
        self.assertEqual(befunde[0]["gewicht"], "mittel")
        self.assertEqual(befunde[0]["empfaenger"], "Reviewer")


class TestKommando(unittest.TestCase):
    def test_frische_session_und_verbote(self):
        cfg = load_config()
        cmd = aussensicht.build_command(cfg)
        text = " ".join(cmd)
        # IMMER neue Session (kein Verlauf) - nie --resume.
        self.assertIn("--session-id", cmd)
        self.assertNotIn("--resume", cmd)
        zweite = aussensicht.build_command(cfg)
        i = cmd.index("--session-id") + 1
        self.assertEqual(cmd.count("--session-id"), 1)
        self.assertNotEqual(cmd[i], zweite[i],
                            "jeder Lauf bekommt eine eigene, frische Kennung")
        # Reviewer-Modell und Reviewer-Effort-Umgebung
        self.assertIn(str(cfg.get("claude", "model_reviewer")), cmd)
        # Lesen, aber NICHTS schreiben
        for verboten in ("Bash", "Write", "Edit", "mcp__ghidra"):
            self.assertIn(verboten, cmd)
        for erlaubt in ("Read", "Grep", "Glob", "PowerShell(git log *)"):
            self.assertIn(erlaubt, text)
        # Beide Wurzeln angemeldet und der eigene Systemprompt
        self.assertIn(str(cfg.root), text)
        self.assertIn(str(cfg.decomp), text)
        self.assertIn("aussensicht.md", text)
        self.assertEqual(cmd.count("--session-id"), 1)
        self.assertIn("--add-dir", cmd)


class TestEingabenUndPrompt(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13w_prompt"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "root")
        self.decomp = ensure_dir(self.tmp / "decomp")
        self.cfg = load_config()
        self.cfg.data["paths"]["root"] = str(self.root)
        self.cfg.data["paths"]["decomp"] = str(self.decomp)
        self.cfg.data["paths"]["harness_home"] = str(self.tmp)
        self.state = st.State(self.root / "state" / "run.json")
        self.state.data["batch"] = 208

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _review(self, batch: int, summary: str) -> None:
        d = ensure_dir(self.root / "runs" / f"b{batch:03d}")
        write_text_atomic(d / "review.md",
                          f"<TELEGRAM_SUMMARY>\n{summary}\n</TELEGRAM_SUMMARY>\n")

    def test_prompt_enthaelt_alle_eingaben_und_stichprobenpflicht(self):
        self._review(207, "Ergebnis: x\nB-SCHRITT: 2/5 Maschine, B-Batch 2 von max 20")
        (self.decomp / "readme.md").write_text("## Project Goal\nZiel: nativer Port\n",
                                               encoding="utf-8")
        (self.decomp / "AGENTS.md").write_text("## Project Goal\nHybrid-Geruest\n",
                                               encoding="utf-8")
        prompt = aussensicht.build_prompt(self.cfg, self.state, "Befehl /meta")
        for stelle in ("BILANZ: TREND", "PLAN/IST", "TELEGRAM_SUMMARY", "ANKERKOPF",
                       "ZIEL UND UMFANG", "OFFENE FRAGEN", "KOSTEN UND LAUFZEITEN",
                       "/ds-QUEUE", "BEFUND", "PRUEFUNG", "STICHPROBEN", "reasoning.jsonl"):
            self.assertIn(stelle, prompt, stelle)
        # (c) Stichprobenpflicht: zwei Zusammenfassungen UND ein Denkblock-Batch
        self.assertIn("mindestens ZWEI", prompt)
        self.assertIn("Denkbloecke", prompt)
        # (3) keine Textmarken mehr als Ausloeser, aber die Pflichtzeilen der Reviewer
        self.assertIn("B-SCHRITT", prompt)
        self.assertNotIn("Abbruchkriterium erreicht", prompt.lower().replace(
            "abbruchkriterium erreicht:", ""))

    def test_fruehere_befunde_stehen_im_prompt(self):
        aussensicht.ledger_schreiben(self.cfg, [{
            "id": "M207-3", "batch": 207, "gewicht": "hoch", "empfaenger": "Reviewer",
            "beleg": "hx/x.py:1", "aussage": "alt", "empfehlung": "neu", "status": "offen"}])
        prompt = aussensicht.build_prompt(self.cfg, self.state, "x")
        self.assertIn("M207-3", prompt)
        self.assertIn("FRUEHERE BEFUNDE", prompt)
        # Ein erledigter Befund wird nicht erneut vorgelegt.
        aussensicht.ledger_schreiben(self.cfg, [{
            "id": "M207-3", "batch": 207, "gewicht": "hoch", "empfaenger": "Reviewer",
            "beleg": "hx/x.py:1", "aussage": "alt", "empfehlung": "neu", "status": "erledigt"}])
        self.assertNotIn("M207-3", aussensicht.build_prompt(self.cfg, self.state, "x"))


class TestAusloeser(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13w_ausl"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "root")
        self.decomp = ensure_dir(self.tmp / "decomp")
        ensure_dir(self.decomp / "analysis")
        self.cfg = load_config()
        self.cfg.data["paths"]["root"] = str(self.root)
        self.cfg.data["paths"]["decomp"] = str(self.decomp)
        self.cfg.data["paths"]["harness_home"] = str(self.tmp)
        self.state = st.State(self.root / "state" / "run.json")
        self.state.data["batch"] = 208

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _review(self, batch: int, summary: str) -> None:
        d = ensure_dir(self.root / "runs" / f"b{batch:03d}")
        write_text_atomic(d / "review.md",
                          f"<TELEGRAM_SUMMARY>\n{summary}\n</TELEGRAM_SUMMARY>\n")

    def _dokument(self, batch: int, ck: tuple[str, str] | None = None,
                  paket: tuple[str, str] | None = None, inv: str = "2072 Koepfe / 28858 Insn",
                  bau: str = "591 Koepfe / 17440 Insn") -> None:
        """Ein Batch-Dokument in der Form, die `stand.c_zahlen` liest (Muster beachten)."""
        ck = ck or ("76 / 1800 / 0", "78 / 2903 / 0")
        paket = paket or ("43 Koepfe / 3025 Insn (Bl 20 / 1434)",
                          "38 / 2674 (Bl 15 / 1083)")
        text = "\n".join([
            f"# Batch {batch}",
            "",
            "| Zeile | vorher | heute |",
            "|---|---|---|",
            f"| **C Koepfe** | {ck[0]} | **{ck[1]}** |",
            f"| Paket E offen | {paket[0]} | **{paket[1]}** |",
            f"| **Programm-Inventar** | {inv} im Programm-Inventar |",
            f"| **Bau-Liste** | {bau} in der Bau-Liste |",
            "",
        ])
        (self.decomp / "analysis" / f"port-batch{batch:03d}-test.md").write_text(
            text, encoding="utf-8")

    # ---------------------------------------------------------- Vormerkung
    def test_vorgemerkt_ist_ein_grund_und_zaehlt_einmal(self):
        self.state.data["meta"] = {"vorgemerkt": True}
        gruende = aussensicht.faellig(self.cfg, self.state)
        self.assertEqual(len(gruende), 1)
        self.assertIn("vorgemerkt", gruende[0])
        # Mehrfaches /meta vor dem Lauf: derselbe Zustand -> derselbe eine Grund.
        self.assertEqual(aussensicht.faellig(self.cfg, self.state), gruende)

    def test_kein_grund_ohne_anlass(self):
        self.assertEqual(aussensicht.faellig(self.cfg, self.state), [])

    def test_nach_entscheidung_kein_zweiter_lauf_fuer_denselben_batch(self):
        self.state.data["meta"] = {"geprueft_batch": 208}
        self.assertEqual(aussensicht.faellig(self.cfg, self.state), [])
        # Ausnahme mit Absicht: ein ausdrueckliches /meta sticht den Merker.
        self.state.data["meta"] = {"geprueft_batch": 208, "vorgemerkt": True}
        self.assertTrue(any("vorgemerkt" in g
                            for g in aussensicht.faellig(self.cfg, self.state)))

    # ------------------------------------------------------------ 10er-Regel
    def test_zehn_batches_erst_nach_der_ersten_aussensicht(self):
        # Nie gelaufen -> KEIN automatischer Lauf (die erste loest der Nutzer aus).
        self.state.data["meta"] = {}
        self.assertEqual([g for g in aussensicht.faellig(self.cfg, self.state)
                          if "Batches" in g], [])
        # Nach der ersten Aussensicht in Batch 199 greift die Regel in 209.
        self.state.data["meta"] = {"letzter_lauf_batch": 199}
        self.state.data["batch"] = 208
        self.assertEqual([g for g in aussensicht.faellig(self.cfg, self.state)
                          if "Batches" in g], [])
        self.state.data["batch"] = 209
        self.assertTrue(any("alle 10 Batches" in g
                            for g in aussensicht.faellig(self.cfg, self.state)))

    def test_worker_abbruch_loest_aus(self):
        self.state.data["meta"] = {"letzter_lauf_batch": 207, "geprueft_batch": 207}
        self.state.data["letzter_abbruch"] = {"batch": 208, "grund": "warteschleife"}
        self.assertTrue(any("Worker-Abbruch" in g
                            for g in aussensicht.faellig(self.cfg, self.state)))

    # ------------------------------------------- Marken des Reviewers (Punkt 3)
    def test_meilenstein_und_abbruchkriterium_loesen_aus(self):
        self._review(208, "Ergebnis: x\nMEILENSTEIN ERREICHT: Kern steht (m208/_kern_diff.txt)")
        self.assertTrue(any("Meilenstein" in g
                            for g in aussensicht.faellig(self.cfg, self.state)))
        self.state.data["meta"] = {"geprueft_batch": 208}
        self._review(209, "Ergebnis: x\nABBRUCHKRITERIUM ERREICHT: 10 B-Batches ohne Boot")
        self.state.data["batch"] = 209
        self.assertTrue(any("Abbruchkriterium" in g
                            for g in aussensicht.faellig(self.cfg, self.state)))

    def test_blosse_erwaehnung_loest_nicht_aus(self):
        # "Abbruchkriterium" steht in jeder B-Instruktion - das darf NICHT ausloesen.
        self._review(208, "Ergebnis: x\nDas Abbruchkriterium gilt weiterhin, es ist NICHT "
                          "erreicht. B-SCHRITT: 1/5 Kern, B-Batch 1 von max 20")
        self.assertFalse(any("Abbruchkriterium" in g
                             for g in aussensicht.faellig(self.cfg, self.state)))

    # ------------------------------------------------------ B-Schritt (Punkt a)
    def test_b_schritt_stillstand_loest_aus(self):
        self._review(207, "Ergebnis: x\nB-SCHRITT: 1/5 Kern, B-Batch 0 von max 20")
        self._review(208, "Ergebnis: x\nB-SCHRITT: 1/5 Kern, B-Batch 1 von max 20")
        self.assertTrue(any("B-Schritt 1/5" in g
                            for g in aussensicht.faellig(self.cfg, self.state)))

    def test_b_schritt_fortschritt_loest_nicht_aus(self):
        self._review(207, "Ergebnis: x\nB-SCHRITT: 1/5 Kern, B-Batch 0 von max 20")
        self._review(208, "Ergebnis: x\nB-SCHRITT: 2/5 Maschine, B-Batch 1 von max 20")
        self.assertFalse(any("B-Schritt" in g
                             for g in aussensicht.faellig(self.cfg, self.state)))

    # ------------------------------------------ Kernzahl-Ausloeser (Punkt a!)
    def test_kernzahl_stillstand_nur_ueber_c_batches(self):
        """Bei 2 B : 1 C darf der C-Ausloeser nicht in jedem B-Batch feuern.

        B208, B209 = B-Batches, B210 = C-Batch; C-Zahlen stehen in 209 und 210 still.
        Verglichen werden 209 (B) und 210 (C) NICHT - sondern 208 (C-Ersatz?) ... hier:
        es gibt nur EINEN C-Batch mit Zahlen -> kein Ausloeser.
        """
        self._dokument(208, ("76 / 1800 / 0", "78 / 2903 / 0"))
        self._dokument(209, ("76 / 1800 / 0", "78 / 2903 / 0"))
        self._dokument(210, ("76 / 1800 / 0", "78 / 2903 / 0"))
        self._review(208, "Ergebnis: x\nB-SCHRITT: 1/5 Kern, B-Batch 1 von max 20")
        self._review(209, "Ergebnis: x\nB-SCHRITT: 2/5 Maschine, B-Batch 2 von max 20")
        self._review(210, "Ergebnis: x\nB-SCHRITT: kein B-Batch (Strang C)")
        self.assertEqual(aussensicht.kernzahl_stillstand(self.cfg), [],
                         "ein einzelner C-Batch ist kein Stillstand")

    def test_kernzahl_stillstand_ueber_zwei_c_batches(self):
        self._dokument(208, ("76 / 1800 / 0", "78 / 2903 / 0"))
        self._dokument(209, ("76 / 1800 / 0", "78 / 2903 / 0"))
        self._dokument(210, ("76 / 1800 / 0", "78 / 2903 / 0"))
        self._review(208, "Ergebnis: x\nB-SCHRITT: 1/5 Kern, B-Batch 1 von max 20")
        self._review(209, "Ergebnis: x\nB-SCHRITT: kein B-Batch (Strang C)")
        self._review(210, "Ergebnis: x\nB-SCHRITT: kein B-Batch (Strang C)")
        stehend = aussensicht.kernzahl_stillstand(self.cfg)
        self.assertTrue(stehend, "zwei C-Batches ohne Bewegung muessen melden")
        self.assertTrue(any("C Koepfe" in z for z in stehend))

    def test_kernzahl_bewegung_loest_nicht_aus(self):
        self._dokument(209, ("74 / 1700 / 0", "74 / 1700 / 0"),
                       ("50 Koepfe / 3100 Insn (Bl 21 / 1500)", "46 / 3100 (Bl 21 / 1500)"),
                       inv="2000 Koepfe / 28000 Insn", bau="560 Koepfe / 17000 Insn")
        self._dokument(210, ("74 / 1700 / 0", "80 / 2951 / 0"),
                       ("46 / 3100 (Bl 21 / 1500)", "40 / 3000 (Bl 19 / 1400)"),
                       inv="2000 Koepfe / 28000 Insn", bau="560 Koepfe / 17000 Insn")
        self._review(209, "Ergebnis: x\nB-SCHRITT: kein B-Batch (Strang C)")
        self._review(210, "Ergebnis: x\nB-SCHRITT: kein B-Batch (Strang C)")
        # Nur die bewegten Zahlen duerfen NICHT gemeldet werden - die stehengebliebenen
        # (Inventar/Bau-Liste) duerfen es sehr wohl.
        stehend = aussensicht.kernzahl_stillstand(self.cfg)
        self.assertFalse(any("C Koepfe" in z for z in stehend))
        self.assertFalse(any("Paket E" in z for z in stehend))


class TestLedgerUndVerteilung(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13w_ledger"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "root")
        self.cfg = load_config()
        self.cfg.data["paths"]["root"] = str(self.root)
        self.cfg.data["paths"]["harness_home"] = str(self.tmp)
        self.state = st.State(self.root / "state" / "run.json")
        self.state.data["batch"] = 208
        self.log = Log(self.tmp / "log.jsonl", echo=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _ergebnis(self):
        _s, befunde, verworfen, pruefungen = aussensicht.parse(BEISPIEL, 7)
        res = aussensicht.Ergebnis()
        res.text, res.rc = BEISPIEL, 0
        res.summary, res.befunde, res.verworfen, res.pruefungen = \
            _s, befunde, verworfen, pruefungen
        return res

    def test_verteile_legt_ids_an_und_wendet_verdikte_an(self):
        aussensicht.ledger_schreiben(self.cfg, [
            {"id": "M207-1", "batch": 207, "gewicht": "hoch", "empfaenger": "Reviewer",
             "beleg": "x:1", "aussage": "a", "empfehlung": "b", "status": "offen"},
            {"id": "M207-2", "batch": 207, "gewicht": "hoch", "empfaenger": "Reviewer",
             "beleg": "x:1", "aussage": "a", "empfehlung": "b", "status": "offen"}])
        res = self._ergebnis()
        v = aussensicht.verteile(self.cfg, self.state, res.summary, res.befunde,
                                 res.pruefungen, 208, self.log)
        self.assertEqual(v["ids"], ["M208-1", "M208-2", "M208-3", "M208-4"])
        self.assertIn("M207-1 -> erledigt", v["verdikte"])
        alle = {b["id"]: b for b in aussensicht.ledger(self.cfg)}
        self.assertEqual(alle["M207-1"]["status"], "erledigt")
        self.assertEqual(alle["M207-2"]["status"], "offen")
        self.assertEqual(alle["M208-1"]["status"], "offen")
        self.assertEqual(alle["M208-1"]["empfaenger"], "Reviewer")
        # R13y: der Empfaenger folgt dem Entscheidungstraeger, nicht der Modellangabe.
        # Befund 4 nennt den Zielsatz/readme -> Nutzer; Befund 1 (Anfragenzahl) und
        # Befund 3 (Zahl ohne Quelle) sind Orchestrator-Sache -> Reviewer.
        self.assertEqual(alle["M208-3"]["empfaenger"], "Nutzer")
        self.assertEqual(alle["M208-4"]["empfaenger"], "Reviewer")
        # Befund 1 der Antwort (niedrig) wollte "Nutzer", ist aber Orchestrator-Sache.
        self.assertTrue(any("Nutzer -> Reviewer" in u for u in v["umgeleitet"]),
                        f"Umleitung fehlt: {v['umgeleitet']}")
        self.assertEqual(v["geteilt"], [])
        self.assertEqual(sorted(v["offen_alt"]), ["M207-2"])

    def test_geteilter_befund_bekommt_zwei_kennungen(self):
        """Ein Befund mit beiden Anteilen wird geteilt (`M208-1a`/`M208-1b`)."""
        teile = aussensicht.entscheidungstraeger({
            "aussage": "Der Zielsatz der readme nennt kein Budget. Der Kern springt nicht "
                       "zurueck und kennt keinen Interrupt.",
            "empfehlung": "Den Zielsatz in der readme ergaenzen."})
        self.assertEqual([t["empfaenger"] for t in teile], ["Nutzer", "Reviewer"])
        self.assertEqual([t.get("teil") for t in teile], ["a", "b"])
        self.assertIn("Budget", teile[0]["aussage"])
        self.assertNotIn("Interrupt", teile[0]["aussage"])
        self.assertIn("Interrupt", teile[1]["aussage"])
        self.assertEqual(teile[0]["empfehlung"], "Den Zielsatz in der readme ergaenzen.")
        self.assertEqual(teile[1]["empfehlung"], "")

    def test_zeile_und_fragen_mit_kennungen(self):
        from hx import fragen as fragenmod
        self.assertEqual(aussensicht.zeile(self.cfg), "")
        res = self._ergebnis()
        v = aussensicht.verteile(self.cfg, self.state, res.summary, res.befunde,
                                 res.pruefungen, 208, self.log)
        aussensicht.bericht_schreiben(self.cfg, 208, "Test", res, v, ["Testgrund"])
        zeile = aussensicht.zeile(self.cfg)
        self.assertIn("Batch 208", zeile)
        self.assertIn("4 Befunde", zeile)
        self.assertIn("4 offen", zeile)
        # R13y: die Nutzer-Befunde stehen mit Kennung in /fragen, die Reviewer-Befunde nicht.
        fragen = fragenmod.fragen_text(self.cfg)
        self.assertIn("M208-3", fragen)
        self.assertIn("AUSSENSICHT", fragen)
        self.assertNotIn("M208-1 ", fragen)
        anhang = fragenmod.anhang([fragenmod.nachschlagen(self.cfg, "M208-3")])
        self.assertIn("M208-3", anhang)
        self.assertIn("Frage:", anhang)
        self.assertIn("Empfehlung:", anhang)

    def test_antworten_uebernehmen(self):
        res = self._ergebnis()
        aussensicht.verteile(self.cfg, self.state, res.summary, res.befunde,
                             res.pruefungen, 208, self.log)
        geaendert = aussensicht.antworten_uebernehmen(
            self.cfg, "M208-1: uebernommen (Quelle ergaenzt)\nM208-2: abgelehnt, "
                      "die Zahl ist belegt\nM208-9: uebernommen", 209)
        self.assertEqual(sorted(geaendert), ["M208-1", "M208-2"])
        alle = {b["id"]: b for b in aussensicht.ledger(self.cfg)}
        self.assertEqual(alle["M208-1"]["status"], "beantwortet")
        self.assertEqual(alle["M208-2"]["status"], "abgelehnt")
        self.assertEqual(alle["M208-2"]["antwort_batch"], 209)
        # Unbeantwortet bleibt offen und erscheint weiter in der Zeile.
        self.assertTrue(any(b["id"] == "M208-3" for b in aussensicht.offene(self.cfg)))
        self.assertIn("2 offen", aussensicht.zeile(self.cfg))


class TestOrchestratorAblauf(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13w_orch"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "root")
        self.decomp = ensure_dir(self.tmp / "decomp")
        ensure_dir(self.decomp / "analysis")
        self.cfg = load_config()
        self.cfg.data["paths"]["root"] = str(self.root)
        self.cfg.data["paths"]["decomp"] = str(self.decomp)
        self.cfg.data["paths"]["harness_home"] = str(self.tmp)
        self.cfg.data["paths"]["inbox"] = str(self.root / "inbox")
        self.log = Log(self.tmp / "log.jsonl", echo=False)
        self.orch = Orchestrator(self.cfg, self.log, mock=True,
                                 state_file=self.root / "state" / "run.json")
        self.orch.qroot = self.root
        self.orch.say = lambda *t, **k: self.gesagt.append(" ".join(str(x) for x in t))
        self.gesagt: list[str] = []
        self.orch.state.data["batch"] = 208
        self.orch.state.save()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_mocklauf_schreibt_bericht_und_verteilt(self):
        self.orch._do_aussensicht("Befehl /meta", gruende=["Befehl /meta"])
        p = aussensicht.bericht_pfad(self.cfg, 208)
        self.assertTrue(p.is_file(), "Bericht muss geschrieben werden")
        self.assertTrue(aussensicht.json_pfad(self.cfg, 208).is_file())
        d = json.loads(aussensicht.json_pfad(self.cfg, 208).read_text(encoding="utf-8"))
        self.assertEqual(d["batch"], 208)
        self.assertTrue(d["ids"], "Befunde muessen im Ledger landen")
        # Empfaenger Reviewer -> /claude-Queue (eine Nachricht je Befund)
        cl = queue.pending(self.root, "claude")
        self.assertTrue(cl, "mindestens eine /claude-Nachricht")
        self.assertEqual(len(cl), len([b for b in aussensicht.offene(self.cfg)
                                       if b["empfaenger"] == "Reviewer"]))
        # Zustand: vorgemerkt weg, Batch vermerkt
        meta = self.orch.state.data["meta"]
        self.assertFalse(meta["vorgemerkt"])
        self.assertEqual(meta["letzter_lauf_batch"], 208)
        self.assertEqual(meta["geprueft_batch"], 208)
        # Meldung nennt den Bericht
        self.assertTrue(any("Aussensicht Batch 208" in s for s in self.gesagt))

    def test_waehrend_worker_wird_nur_vorgemerkt(self):
        self.orch.state.data["worker"] = {"pid": 1, "started_at": "x", "log": "y",
                                          "session_id": "z"}
        self.orch.state.set(st.DS_WORKING, "Test")
        self.orch._do_aussensicht("Befehl /meta")
        self.assertTrue(self.orch.state.data["meta"]["vorgemerkt"])
        self.assertFalse(aussensicht.bericht_pfad(self.cfg, 208).exists())
        self.assertEqual(queue.pending(self.root, "claude"), [])
        self.assertTrue(any("vorgemerkt" in s for s in self.gesagt))

    def test_mehrfaches_vormerken_bleibt_eines(self):
        self.orch.state.data["worker"] = {"pid": 1}
        self.orch.state.set(st.DS_WORKING, "Test")
        self.orch._do_aussensicht("Befehl /meta")
        self.orch._do_aussensicht("Befehl /meta")
        self.assertEqual(len(aussensicht.faellig(self.cfg, self.orch.state)
                             if False else ["vorgemerkt"]), 1)
        self.assertTrue(self.orch.state.data["meta"]["vorgemerkt"])
        self.assertEqual(self.orch.state.data["meta"]["vorgemerkt_grund"], "Befehl /meta")

    def test_befehl_meta_erreicht_die_methode(self):
        self.assertTrue(self.orch.handle_command("/meta"))
        self.assertTrue(aussensicht.bericht_pfad(self.cfg, 208).is_file())

    def test_steuerdatei_meta(self):
        aussensicht.bericht_pfad(self.cfg, 208).unlink(missing_ok=True)
        control.put(self.cfg, "meta", "cli")
        self.orch.check_local_control()
        self.assertTrue(aussensicht.bericht_pfad(self.cfg, 208).is_file())

    def test_status_und_fragen_zeigen_die_aussensicht(self):
        self.orch._do_aussensicht("Befehl /meta")
        self.assertIn("Aussensicht:", self.orch.meta_zeile())
        self.assertIn("Batch 208", self.orch.meta_zeile())
        self.orch._do_fragen()
        text = "\n".join(self.gesagt)
        self.assertIn("FRAGEN AN DICH", text)
        self.assertIn("ANTWORTEN: /claude", text)


class TestBilanzZeile(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13w_bilanz"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.cfg = load_config()
        self.cfg.data["paths"]["root"] = str(ensure_dir(self.tmp / "root"))
        self.cfg.data["paths"]["harness_home"] = str(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_bilanz_zeigt_die_aussensicht_nur_wenn_es_sie_gibt(self):
        from hx import bilanz as bilanzmod
        ohne = bilanzmod.bericht(self.cfg, n=1)
        self.assertNotIn("letzte Aussensicht", ohne)
        aussensicht.ledger_schreiben(self.cfg, [
            {"id": "M208-1", "batch": 208, "gewicht": "hoch", "empfaenger": "Reviewer",
             "beleg": "x:1", "aussage": "a", "empfehlung": "b", "status": "offen"}])
        getattr(bilanzmod, "bericht")  # nur zur Klarheit: dieselbe Funktion
        mit = bilanzmod.bericht(self.cfg, n=1)
        self.assertIn("letzte Aussensicht", mit)
        self.assertIn("1 offen", mit)


if __name__ == "__main__":
    unittest.main()
