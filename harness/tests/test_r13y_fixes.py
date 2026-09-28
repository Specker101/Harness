"""Tests fuer R13y: Kennungen fuer die Fragen an den Nutzer + Aufteilung nach Traeger.

Auftrag (Nutzer, 2026-09-28, kein neuer Befehl):

  1. `/fragen`: jede offene Frage an den Nutzer bekommt eine eindeutige Kennung
     (Ankerposten `A5`, Reviewer-Fragen `R209-1`, Aussensicht-Befunde `M208-1`),
     sofern sie nicht schon eine hat.
  2. Beginnt eine `/claude`-Nachricht mit einer solchen Kennung ("M208-1: ja",
     "A5 nein, erst spaeter"), haengt der Harness Wortlaut der Frage und Empfehlung an
     und markiert die Frage als "beantwortet, wartet auf Review"; nach dem Review, das
     sie aufnimmt, verschwindet sie aus `/fragen`. Mehrere Kennungen sind erlaubt,
     eine unbekannte Kennung am Anfang wird mit den gueltigen gemeldet.
  3. Aussensicht: Befunde nach Entscheidungstraeger aufteilen - Orchestrator-Sache an
     den Reviewer, Ziel/Scope/Budget/fruehere Nutzerentscheidungen an den Nutzer;
     Befunde mit beiden Anteilen werden geteilt.

Alles im Attrappenbetrieb: kein Netz, keine API-Kosten, Wegwerf-Verzeichnisse unter
`tests/_tmp_r13y*`. Das laufende Harness-Verzeichnis wird NICHT angefasst.
"""

from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import aussensicht, fragen, queue                       # noqa: E402
from hx.config import load_config                                  # noqa: E402
from hx.orchestrator import Orchestrator                           # noqa: E402
from hx.util import Log, ensure_dir, write_text_atomic             # noqa: E402

ANKER = """# Workstream R1B

**Stand:** BATCH 101 (2026-09-28) - Beispielstand.
**Fertig:** **(1)** etwas fertig.
**Naechster Schritt:** **(a)** Paket E weiter.
**Offene Entscheidung:** **(5) NEU:** soll `prof` je Kopf MEHRERE MEM-Varianten fahren (Vorschlag: **ja**, eigener kleiner Werkzeugschritt)? **(6)** offen bleiben: R330, `M60_NO_EVID`, die Pins (R381)
"""

REVIEW = """<TELEGRAM_SUMMARY>
Ergebnis: solide.
ENTSCHEIDUNG NOETIG: Soll der Hybrid-Kern gegen Unicorn geprueft werden?
OFFENE FRAGE: Du nennst 21 Referenzstroeme, gezaehlt sind 20. Welcher fehlt?
WARTET AUF LIVE-AUFNAHME: 0x40B/0x40E/0x40F
ENTSCHIEDEN: Zuerst wird der Interpreter streng gemacht.
</TELEGRAM_SUMMARY>
<DS_INSTRUCTION>
Batch 210 - Beispiel
</DS_INSTRUCTION>
"""

BEFUND = {"id": "M208-1", "batch": 208, "gewicht": "mittel", "empfaenger": "Nutzer",
          "beleg": "readme.md:640-642", "status": "offen",
          "aussage": "Der Zielsatz in readme.md nennt kein Budget fuer den Rest.",
          "empfehlung": "Das Budget im Zielsatz der readme nachtragen."}


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13y"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "root")
        self.decomp = ensure_dir(self.tmp / "decomp")
        self.ana = ensure_dir(self.decomp / "analysis")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.decomp)
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["telegram"]["allowlist_user_ids"] = []
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ------------------------------------------------------------- Fixture
    def anker(self, text: str = ANKER) -> None:
        write_text_atomic(self.ana / "r1b-workstream.md", text)

    def review(self, text: str = REVIEW, ordner: str = "b211",
               fakten: str | None = "bewertet wird Batch 210") -> None:
        d = ensure_dir(self.root / "runs" / ordner)
        write_text_atomic(d / "review.md", text)
        if fakten:
            write_text_atomic(d / "harness-facts.md",
                              f"- Review: {fakten}; die Instruktion gilt fuer Batch 211\n")

    def ledger(self, eintraege: list[dict] | None = None) -> None:
        aussensicht.ledger_schreiben(self.cfg, eintraege if eintraege is not None
                                     else [dict(BEFUND)])

    def orch(self) -> Orchestrator:
        o = Orchestrator(self.cfg, self.log, mock=True,
                         state_file=self.root / "state" / "run.json")
        o.qroot = self.root
        o.said = []
        o.say = lambda t="", *a, **k: o.said.append(str(t))
        o.state.data["batch"] = 210
        o.state.save()
        return o


# ------------------------------------------------------------------ Kennungen
class TestKennungen(unittest.TestCase):
    def test_leading_ids(self):
        self.assertEqual(fragen.ids_am_anfang("M208-1: ja"), ["M208-1"])
        self.assertEqual(fragen.ids_am_anfang("A5 nein, erst spaeter"), ["A5"])
        self.assertEqual(fragen.ids_am_anfang("A5, M208-1: ja"), ["A5", "M208-1"])
        self.assertEqual(fragen.ids_am_anfang("R209-1 ja"), ["R209-1"])
        self.assertEqual(fragen.ids_am_anfang("M208-5a: abgelehnt"), ["M208-5a"])
        self.assertEqual(fragen.ids_am_anfang("a5 ja"), ["A5"])       # tolerant
        self.assertEqual(fragen.ids_am_anfang("A5 A5 ja"), ["A5"])    # ohne Dubletten

    def test_ids_mitten_im_text_zaehlen_nicht(self):
        self.assertEqual(fragen.ids_am_anfang("bitte A5 beachten"), [])
        self.assertEqual(fragen.ids_am_anfang(""), [])
        self.assertEqual(fragen.ids_am_anfang("nur Text ohne Kennung"), [])


# ------------------------------------------------------------------ Register
class TestFragenregister(Basis):
    def test_kennungen_fuer_alle_quellen(self):
        self.anker()
        self.review()
        self.ledger()
        posten = {p["id"]: p for p in fragen.fragen_posten(self.cfg)}
        self.assertIn("A5", posten)                 # Ankerposten (5)
        self.assertIn("A6", posten)                 # Ankerposten (6), unklar
        self.assertFalse(posten["A6"]["frage"])
        self.assertIn("R210-1", posten)             # erster Marker = ENTSCHEIDUNG NOETIG
        self.assertIn("R210-2", posten)             # OFFENE FRAGE
        self.assertIn("R210-3", posten)             # LIVE-AUFNAHME
        self.assertIn("R210-4", posten)             # ENTSCHIEDEN (Veto moeglich)
        self.assertIn("M208-1", posten)             # Aussensicht-Befund
        self.assertTrue(posten["R210-1"]["bremst"])
        self.assertFalse(posten["R210-2"]["bremst"])
        self.assertEqual(posten["M208-1"]["beleg"], "readme.md:640-642")

    def test_text_zeigt_kennungen_und_antwortweg(self):
        self.anker()
        self.review()
        self.ledger()
        text = fragen.fragen_text(self.cfg, gate={"instruction": "Auftrag X",
                                                  "tools": {"source": "user"}})
        self.assertIn("FRAGEN AN DICH (Anker: BATCH 101)", text)
        self.assertIn("A5", text)
        self.assertIn("ANKERPOSTEN (5): soll `prof`", text)
        self.assertIn("R210-1", text)
        self.assertIn("ENTSCHEIDUNG NOETIG (bremst)", text)
        self.assertIn("M208-1", text)
        self.assertIn("Beleg: readme.md:640-642", text)
        self.assertIn("ANTWORTEN: /claude <Kennung>", text)
        self.assertIn("OFFENER AUFTRAG (VOM NUTZER)", text)

    def test_review_kennung_nennt_den_bewerteten_batch(self):
        self.anker()
        self.review(fakten=None)                    # ohne Fakten-Datei: Ordner-1
        posten = [p for p in fragen.fragen_posten(self.cfg) if p["id"].startswith("R")]
        self.assertTrue(posten)
        self.assertEqual(posten[0]["id"], "R210-1")

    def test_status_offen_beantwortet_aufgenommen(self):
        self.anker()
        posten = {p["id"]: p for p in fragen.fragen_posten(self.cfg)}
        self.assertEqual(posten["A5"]["status"], "offen")
        # Nachricht liegt in der Queue -> beantwortet
        p = queue.enqueue(self.root, "claude", "A5 ja, bitte fahren", "telegram")
        posten = {x["id"]: x for x in fragen.fragen_posten(self.cfg)}
        self.assertEqual(posten["A5"]["status"], "beantwortet")
        zeilen = fragen.fragen_text(self.cfg)
        self.assertIn("BEANTWORTET, WARTET AUF REVIEW", zeilen)
        self.assertIn("A5", zeilen)
        # Review hat sie gelesen (claude_queue_ids des Gates) -> aufgenommen
        gate = {"claude_queue_ids": [p.stem]}
        posten = {x["id"]: x for x in fragen.fragen_posten(self.cfg, gate=gate)}
        self.assertEqual(posten["A5"]["status"], "aufgenommen")
        zeilen = fragen.fragen_text(self.cfg, gate=gate)
        self.assertIn("aufgenommen (nicht mehr offen): A5", zeilen)
        # Archiviert (done/) zaehlt ebenfalls als aufgenommen
        queue.archive(self.root, [p.stem], "claude")
        posten = {x["id"]: x for x in fragen.fragen_posten(self.cfg)}
        self.assertEqual(posten["A5"]["status"], "aufgenommen")

    def test_status_ohne_anker_und_review(self):
        self.assertEqual(fragen.fragen_posten(self.cfg), [])
        text = fragen.fragen_text(self.cfg)
        self.assertIn("keine - der Reviewer entscheidet den Regelfall selbst", text)


# ------------------------------------------------------------------ Nachricht
class TestNachricht(Basis):
    def test_bekannte_kennung_bekommt_wortlaut_und_empfehlung(self):
        self.anker()
        self.ledger()
        vor = fragen.nachricht_vorbereiten(self.cfg, "M208-1: ja, aber spaeter")
        self.assertTrue(vor["ok"])
        self.assertEqual(vor["bekannt"], ["M208-1"])
        self.assertIn("[Antwort auf Frage(n)", vor["text"])
        self.assertIn("M208-1", vor["text"])
        self.assertIn("Der Zielsatz in readme.md nennt kein Budget", vor["text"])
        self.assertIn("Empfehlung: Das Budget im Zielsatz der readme nachtragen.",
                      vor["text"])
        self.assertIn("beantwortet, wartet auf Review", vor["meldung"])

    def test_mehrere_kennungen_in_einer_nachricht(self):
        self.anker()
        vor = fragen.nachricht_vorbereiten(self.cfg, "A5, A6: ja bzw. nein")
        self.assertTrue(vor["ok"])
        self.assertEqual(vor["bekannt"], ["A5", "A6"])
        self.assertIn("Empfehlung: ja", vor["text"])
        self.assertIn("A6", vor["text"])

    def test_unbekannte_kennung_wird_gemeldet_und_nicht_eingereiht(self):
        self.anker()
        vor = fragen.nachricht_vorbereiten(self.cfg, "A9 ja")
        self.assertFalse(vor["ok"])
        self.assertEqual(vor["unbekannt"], ["A9"])
        self.assertIn("NICHT in die Queue gelegt", vor["meldung"])
        self.assertIn("Gueltige Kennungen: A5, A6", vor["meldung"])

    def test_ohne_kennung_bleibt_die_nachricht_unveraendert(self):
        self.anker()
        vor = fragen.nachricht_vorbereiten(self.cfg, "Bitte den Kern haerten")
        self.assertTrue(vor["ok"])
        self.assertEqual(vor["text"], "Bitte den Kern haerten")
        self.assertEqual(vor["bekannt"], [])

    def test_nachschlagen_kennt_die_kurzform_geteilter_befunde(self):
        self.ledger([dict(BEFUND, id="M208-5a", aussage="Budget im Zielsatz fehlt."),
                     dict(BEFUND, id="M208-5b", empfaenger="Reviewer")])
        self.assertIsNotNone(fragen.nachschlagen(self.cfg, "M208-5"))
        self.assertEqual(fragen.nachschlagen(self.cfg, "M208-5a")["id"], "M208-5a")


# ------------------------------------------------------------------ Befehle
class TestBefehle(Basis):
    def test_claude_befehl_haengt_den_wortlaut_an(self):
        self.anker()
        o = self.orch()
        self.assertTrue(o.handle_command("/claude A5 ja"))
        self.assertIn("Beantwortet: A5", " ".join(o.said))
        posten = queue.pending(self.root, "claude")
        self.assertEqual(len(posten), 1)
        self.assertIn("Frage: soll `prof` je Kopf MEHRERE MEM-Varianten fahren?",
                      posten[0].text)
        self.assertIn("Empfehlung: ja", posten[0].text)

    def test_claude_befehl_weist_unbekannte_kennung_ab(self):
        self.anker()
        o = self.orch()
        self.assertTrue(o.handle_command("/claude A9 ja"))
        self.assertIn("A9", " ".join(o.said))
        self.assertEqual(queue.pending(self.root, "claude"), [])

    def test_claude_ohne_kennung_wie_bisher(self):
        o = self.orch()
        self.assertTrue(o.handle_command("/claude bitte den Kern haerten"))
        posten = queue.pending(self.root, "claude")
        self.assertEqual(posten[0].text, "bitte den Kern haerten")

    def test_fragen_befehl_zeigt_kennungen(self):
        self.anker()
        self.review()
        self.ledger()
        o = self.orch()
        self.assertTrue(o.handle_command("/fragen"))
        text = o.said[-1]
        self.assertIn("A5", text)
        self.assertIn("R210-1", text)
        self.assertIn("M208-1", text)

    def test_status_zeigt_die_offenen_kennungen(self):
        self.anker()
        o = self.orch()
        text = o.status_text()
        self.assertIn("Fragen an dich:", text)
        self.assertIn("A5", text)

    def test_cli_send_claude_mit_kennung(self):
        from hx import cli
        self.anker()
        args = mock.Mock(config=None, target="claude", text="A5 ja", file=None)
        with mock.patch.object(cli, "load_config", lambda *a, **k: self.cfg):
            self.assertEqual(cli.cmd_send(args), 0)
        posten = queue.pending(self.root, "claude")
        self.assertEqual(len(posten), 1)
        self.assertIn("Frage: soll `prof`", posten[0].text)

    def test_cli_send_claude_unbekannt_bricht_ab(self):
        from hx import cli
        self.anker()
        args = mock.Mock(config=None, target="claude", text="A9 ja", file=None)
        with mock.patch.object(cli, "load_config", lambda *a, **k: self.cfg):
            self.assertEqual(cli.cmd_send(args), 2)
        self.assertEqual(queue.pending(self.root, "claude"), [])

    def test_cli_fragen_gibt_kennungen_aus(self):
        from hx import cli
        self.anker()
        with mock.patch.object(cli, "load_config", lambda *a, **k: self.cfg):
            self.assertEqual(cli.cmd_fragen(mock.Mock(config=None)), 0)


# ------------------------------------------------------------------ Traeger
class TestEntscheidungstraeger(unittest.TestCase):
    def test_nur_orchestrator_sache_geht_an_den_reviewer(self):
        teile = aussensicht.entscheidungstraeger({
            "aussage": "Der Kern springt nicht zurueck.", "empfaenger": "Nutzer",
            "empfehlung": "blr auf den LR legen."})
        self.assertEqual([t["empfaenger"] for t in teile], ["Reviewer"])
        self.assertFalse(teile[0]["geteilt"])

    def test_nur_nutzer_sache_bleibt_beim_nutzer(self):
        teile = aussensicht.entscheidungstraeger({
            "aussage": "Der Zielsatz der readme nennt kein Budget.",
            "empfaenger": "Reviewer", "empfehlung": "Budget nachtragen."})
        self.assertEqual([t["empfaenger"] for t in teile], ["Nutzer"])
        self.assertFalse(teile[0]["geteilt"])

    def test_beide_anteile_werden_geteilt(self):
        teile = aussensicht.entscheidungstraeger({
            "beleg": "readme.md:640-642 und analysis/hybrid-plan.md:100",
            "aussage": "Das readme-Ziel ist mit dem Mischverhaeltnis nicht erreichbar. "
                       "Die Projektion im Plan ignoriert das 2:1-Verhaeltnis.",
            "empfaenger": "Nutzer",
            "empfehlung": "Das Ziel in der readme mit einer Priorisierung abgleichen."})
        self.assertEqual([t["empfaenger"] for t in teile], ["Nutzer", "Reviewer"])
        self.assertTrue(all(t["geteilt"] for t in teile))
        self.assertIn("readme-Ziel", teile[0]["aussage"])
        self.assertNotIn("2:1", teile[0]["aussage"])
        self.assertIn("2:1", teile[1]["aussage"])
        self.assertEqual(teile[0]["empfehlung"], "Das Ziel in der readme mit einer "
                                                 "Priorisierung abgleichen.")
        self.assertEqual(teile[1]["empfehlung"], "")
        # Gleicher Beleg in beiden Teilen.
        self.assertEqual(teile[0]["beleg"], teile[1]["beleg"])

    def test_zuschnitt_des_batches_ist_kein_nutzerthema(self):
        teile = aussensicht.entscheidungstraeger({
            "aussage": "Das Ziel des naechsten Batches ist zu gross.",
            "empfaenger": "Nutzer", "empfehlung": "Kleiner schneiden."})
        self.assertEqual([t["empfaenger"] for t in teile], ["Reviewer"])


class TestVerteilung(Basis):
    def _ergebnis(self, aussage: str, empfehlung: str, empfaenger: str = "Nutzer"):
        b = {"n": 1, "gewicht": "mittel", "empfaenger": empfaenger,
             "beleg": "readme.md:640-642", "aussage": aussage, "empfehlung": empfehlung}
        res = aussensicht.Ergebnis()
        res.text, res.rc = "<AUSSENSICHT>x</AUSSENSICHT>", 0
        res.summary, res.befunde = "ok", [b]
        res.verworfen, res.pruefungen = [], []
        return res

    def test_geteilter_befund_bekommt_zwei_kennungen(self):
        res = self._ergebnis(
            "Der Zielsatz der readme nennt kein Budget. Der Kern kennt keinen Interrupt.",
            "Das Budget im Zielsatz nachtragen.")
        state = aussensicht_run(self.cfg, self.log, res, 208)
        self.assertIn("M208-1a", state["ids"])
        self.assertIn("M208-1b", state["ids"])
        self.assertEqual(state["geteilt"], ["M208-1"])
        alle = {b["id"]: b for b in aussensicht.ledger(self.cfg)}
        self.assertEqual(alle["M208-1a"]["empfaenger"], "Nutzer")
        self.assertEqual(alle["M208-1b"]["empfaenger"], "Reviewer")
        self.assertIn("Budget", alle["M208-1a"]["aussage"])
        self.assertIn("Interrupt", alle["M208-1b"]["aussage"])

    def test_kurzform_beantwortet_beide_teile(self):
        res = self._ergebnis(
            "Der Zielsatz der readme nennt kein Budget. Der Kern kennt keinen Interrupt.",
            "Das Budget nachtragen.")
        aussensicht_run(self.cfg, self.log, res, 208)
        geaendert = aussensicht.antworten_uebernehmen(
            self.cfg, "M208-1: uebernommen (Zielsatz angepasst)", 209)
        self.assertEqual(sorted(geaendert), ["M208-1a", "M208-1b"])
        alle = {b["id"]: b for b in aussensicht.ledger(self.cfg)}
        self.assertEqual(alle["M208-1a"]["status"], "beantwortet")
        self.assertEqual(alle["M208-1b"]["status"], "beantwortet")

    def test_teilform_beantwortet_nur_einen_teil(self):
        res = self._ergebnis(
            "Der Zielsatz der readme nennt kein Budget. Der Kern kennt keinen Interrupt.",
            "Das Budget nachtragen.")
        aussensicht_run(self.cfg, self.log, res, 208)
        geaendert = aussensicht.antworten_uebernehmen(self.cfg, "M208-1b: abgelehnt, "
                                                               "kein Kontrollfluss", 209)
        self.assertEqual(geaendert, ["M208-1b"])
        alle = {b["id"]: b for b in aussensicht.ledger(self.cfg)}
        self.assertEqual(alle["M208-1b"]["status"], "abgelehnt")
        self.assertEqual(alle["M208-1a"]["status"], "offen")


def aussensicht_run(cfg, log, res, batch: int) -> dict:
    """`verteile` wie im Betrieb aufrufen (ohne Modell-Lauf)."""
    from hx import state as st_mod
    state = st_mod.State(Path(cfg.sub("state")) / "run.json")
    state.data["batch"] = batch
    return aussensicht.verteile(cfg, state, res.summary, res.befunde, res.pruefungen,
                                batch, log)


if __name__ == "__main__":
    unittest.main()
