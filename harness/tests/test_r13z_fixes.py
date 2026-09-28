"""Tests fuer R13z (2026-09-28): Aussensicht-Takt + Quote, zwei Pflichtabschnitte im Review.

Auftrag (Nutzer, nach der Abnahme von R13y):

  5. **Aussensicht-Takt**: `harness.toml` `[meta] every_batches` von 10 auf **3**
     (vorlaeufig; Begruendung in `docs/bedienung.md` 12e, Auswertung nach einer Woche
     anhand der Quote "uebernommen" im Register `state/meta_befunde.json`). `/bilanz`
     zeigt die Quote: "Aussensicht: n Befunde, davon u uebernommen, a abgelehnt, o offen".
  6. **`prompts/reviewer.md`**, Pflichtabschnitt `## VERALLGEMEINERUNG` vor der
     `DS_INSTRUCTION` (steht im `review.md`, NICHT in der `TELEGRAM_SUMMARY`): je Befund
     (a) Fehlerklasse, (b) verwandte Faelle + wie die Instruktion sie mitprueft,
     (c) was sie ausdruecklich NICHT prueft.
  7. **`prompts/reviewer.md`**: jede "Offene Entscheidung" im Ankerkopf MUSS entscheidbar
     formuliert sein (Frage ja/nein ODER A/B, Empfehlung, Folgen) - sonst zeigt `/fragen`
     `UNKLAR FORMULIERT`. Der naechste Review formuliert A1-A3 neu oder schliesst sie.

Alles ohne Netz und API-Kosten: Wegwerf-Verzeichnisse unter `tests/_tmp_r13z*`.
Das laufende Harness-Verzeichnis wird NICHT angefasst (Ausnahme: `load_config()` liest
die echte `harness.toml` - das ist der Pruefgegenstand).
"""

from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import aussensicht, bilanz, fragen, stand                # noqa: E402
from hx.config import load_config                                # noqa: E402
from hx.orchestrator import Orchestrator                         # noqa: E402
from hx.util import Log, ensure_dir, write_text_atomic           # noqa: E402

PROMPT = ROOT / "prompts" / "reviewer.md"

ANKER_AB = """# Workstream R1B

**Stand:** BATCH 101 (2026-09-28) - Beispielstand.
**Naechster Schritt:** **(a)** Kern weiter bauen.
**Offene Entscheidung:** **(4) NEU:** soll der Kern gegen den PPC-Kern unter `mame/` (A) oder gegen eine Befehlstabelle (B) geprueft werden (Vorschlag: A. bei A: Vergleich je Form. bei B: Stichproben.)?
"""


def _befund(i: int, status: str) -> dict:
    return {"id": f"M208-{i}", "batch": 208, "gewicht": "mittel",
            "empfaenger": "Reviewer", "beleg": "hx/x.py:1", "aussage": "a",
            "empfehlung": "b", "status": status}


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13z"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "root")
        self.decomp = ensure_dir(self.decomp_pfad())
        self.ana = ensure_dir(self.decomp / "analysis")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.decomp)
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["paths"]["harness_home"] = str(self.tmp)
        cfg.data["telegram"]["allowlist_user_ids"] = []
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)

    def decomp_pfad(self) -> Path:
        return Path(ROOT) / "tests" / "_tmp_r13z" / "decomp"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def anker(self, text: str = ANKER_AB) -> None:
        write_text_atomic(self.ana / "r1b-workstream.md", text)

    def ledger(self, *status: str) -> None:
        aussensicht.ledger_schreiben(self.cfg, [_befund(i, s)
                                                for i, s in enumerate(status, 1)])

    def meta_lauf(self, batch: int = 208, befunde: int = 0) -> None:
        """Einen Aussensicht-Bericht (Maschinenfassung) ablegen."""
        write_text_atomic(self.root / "runs" / f"meta-{batch:03d}.json",
                          json.dumps({"batch": batch,
                                      "befunde": [{}] * befunde}))

    def schnappschuss(self, batch: int = 208) -> None:
        """Einen leeren Bilanz-Schnappschuss im Wegwerf-Decomp-Repo."""
        write_text_atomic(self.ana / "_bilanz_snapshot.json",
                          json.dumps({"batches": {str(batch): {"rows": {}}}}))


# ------------------------------------------------------------ 5) Takt + Quote
class TestTakt(unittest.TestCase):
    def test_takt_ist_drei(self):
        """R13z: 10 -> 3, vorlaeufig. Wer die Zahl aendert, aendert diese Zeile mit."""
        cfg = load_config()
        self.assertEqual(int(cfg.get("meta", "every_batches")), 3)
        # Die Vorgabe im Code muss dazupassen - sonst greift bei fehlendem Schluessel
        # still ein anderer Takt (genau die Klasse Fehler, die M208-3 beschreibt).
        self.assertEqual(int(aussensicht.STANDARD["every_batches"]), 3)
        self.assertEqual(int(aussensicht.grenzen(cfg)["every_batches"]), 3)


class TestQuote(Basis):
    def test_klassen_der_statusworte(self):
        self.assertEqual(aussensicht.klasse({"status": "uebernommen"}), "uebernommen")
        # "beantwortet" ist das Wort aus R13w (alte Registereintraege) - es zaehlt mit.
        self.assertEqual(aussensicht.klasse({"status": "beantwortet"}), "uebernommen")
        self.assertEqual(aussensicht.klasse({"status": "erledigt"}), "uebernommen")
        self.assertEqual(aussensicht.klasse({"status": "abgelehnt"}), "abgelehnt")
        self.assertEqual(aussensicht.klasse({"status": "verworfen"}), "abgelehnt")
        self.assertEqual(aussensicht.klasse({"status": "offen"}), "offen")
        self.assertEqual(aussensicht.klasse({"status": ""}), "offen")
        self.assertEqual(aussensicht.klasse({}), "offen")
        # Ein falsch geschriebener Status darf einen Befund NICHT aus der offenen
        # Liste werfen (sonst verschwindet eine unbeantwortete Frage still).
        self.assertEqual(aussensicht.klasse({"status": "Quatsch"}), "offen")

    def test_quote_und_zeile(self):
        self.ledger("uebernommen", "beantwortet", "abgelehnt", "offen")
        self.meta_lauf(208, befunde=4)
        q = aussensicht.quote(self.cfg)
        self.assertEqual(q, {"gesamt": 4, "uebernommen": 2, "abgelehnt": 1, "offen": 1})
        z = aussensicht.zeile(self.cfg)
        self.assertIn("Aussensicht: 4 Befunde, davon 2 uebernommen, 1 abgelehnt, "
                      "1 offen", z)
        self.assertIn("letzte Aussensicht: Batch 208", z)
        self.assertIn("Takt: alle 3 Batches", z)
        # Telegram/`/bilanz` zeigen die Zeile als EINE Zeile
        self.assertEqual(len(z.splitlines()), 1)

    def test_takt_kommt_aus_der_konfiguration(self):
        self.ledger("offen")
        self.cfg.data.setdefault("meta", {})["every_batches"] = 7
        self.assertIn("Takt: alle 7 Batches", aussensicht.zeile(self.cfg))

    def test_ohne_aussensicht_keine_zeile(self):
        self.assertEqual(aussensicht.zeile(self.cfg), "")

    def test_unbekannter_status_bleibt_in_der_offenen_liste(self):
        self.ledger("Quatsch", "abgelehnt")
        self.assertEqual([b["id"] for b in aussensicht.offene(self.cfg)], ["M208-1"])

    def test_verdikt_wort_wird_so_gespeichert_wie_es_kommt(self):
        self.ledger("offen", "offen")
        geaendert = aussensicht.antworten_uebernehmen(
            self.cfg, "M208-1: \u00fcbernommen (Quelle ergaenzt)\nM208-2: abgelehnt, "
                      "die Zahl ist belegt", 209)
        self.assertEqual(sorted(geaendert), ["M208-1", "M208-2"])
        alle = {b["id"]: b for b in aussensicht.ledger(self.cfg)}
        # Umlautschreibweise wird vereinheitlicht, das Wort bleibt sonst stehen.
        self.assertEqual(alle["M208-1"]["status"], "uebernommen")
        self.assertEqual(alle["M208-2"]["status"], "abgelehnt")
        self.assertEqual(aussensicht.quote(self.cfg),
                         {"gesamt": 2, "uebernommen": 1, "abgelehnt": 1, "offen": 0})

    def test_bilanz_zeigt_die_quote(self):
        self.schnappschuss()
        self.ledger("uebernommen", "abgelehnt", "offen")
        text = bilanz.bericht(self.cfg, n=1)
        self.assertIn("Aussensicht: 3 Befunde, davon 1 uebernommen, 1 abgelehnt, "
                      "1 offen", text)

    def test_status_zeigt_die_zeile_genau_einmal(self):
        self.ledger("offen")
        o = Orchestrator(self.cfg, self.log, mock=True,
                         state_file=self.root / "state" / "run.json")
        o.qroot = self.root
        zeile = o.meta_zeile()
        self.assertIn("Aussensicht: 1 Befunde", zeile)
        self.assertNotIn("Aussensicht: Aussensicht", zeile)
        o.state.data["meta"] = {"vorgemerkt": True}
        self.assertIn("Aussensicht: 1 Befunde", o.meta_zeile())
        self.assertIn("vorgemerkt", o.meta_zeile())


# ------------------------------------------------- 6/7) Pflichtabschnitte im Prompt
class TestReviewerPrompt(unittest.TestCase):
    def setUp(self):
        self.text = PROMPT.read_text(encoding="utf-8")

    def test_verallgemeinerung_steht_vor_der_instruktion(self):
        i = self.text.index("## VERALLGEMEINERUNG")
        # im Antwortgeruest: nach </DS_TOOLS>, vor <DS_INSTRUCTION>
        self.assertLess(self.text.index("</DS_TOOLS>"), i)
        self.assertLess(i, self.text.index("<DS_INSTRUCTION>"))

    def test_verallgemeinerung_nicht_in_der_telegram_summary(self):
        # Das Geruest (Tag am Zeilenanfang) - nicht die Prosa-Erwaehnungen im Text.
        block = self.text.split("<TELEGRAM_SUMMARY>\n", 1)[1].split("</TELEGRAM_SUMMARY>",
                                                                   1)[0]
        self.assertNotIn("VERALLGEMEINERUNG", block)
        self.assertIn("Er geh\u00f6rt ins **review.md**", self.text)
        self.assertIn("**nicht** in `<TELEGRAM_SUMMARY>`", self.text)

    def test_drei_fragen_a_b_c_mit_beispiel(self):
        for stelle in ("Fehlerklasse", "verwandten F", "NICHT"):
            self.assertIn(stelle, self.text)
        # (a)/(b)/(c) stehen als eigene Zeilen
        for marke in ("| (a) |", "| (b) |", "| (c) |"):
            self.assertIn(marke, self.text)
        # Beispiel zu (b) aus dem Auftrag: slw -> alle Formen mit rS/rA-Feldlage
        self.assertIn("`rS` in Feld 6\u201310 und `rA` in Feld 11\u201315", self.text)
        self.assertIn("slw", self.text)
        # ohne den Abschnitt ist das Review unvollstaendig
        self.assertIn("unvollst\u00e4ndig", self.text)

    def test_ankerposten_muessen_entscheidbar_sein(self):
        self.assertIn("UNKLAR FORMULIERT", self.text)
        self.assertIn("Vorschlag: A", self.text)
        self.assertIn("bei A:", self.text)
        self.assertIn("bei B:", self.text)
        self.assertIn("GESCHLOSSEN", self.text)
        # Der Uebergang: A1-A3 im naechsten Review neu formulieren oder schliessen.
        self.assertIn("A1", self.text)
        self.assertIn("A3", self.text)
        self.assertIn("\u00dcbergang (einmalig, R13z)", self.text)


# ---------------------------------------------------- 7) A/B-Fragen im Ankerkopf
class TestAlternativen(unittest.TestCase):
    def test_ja_nein_unveraendert(self):
        e = stand.entscheidbar(
            "Die Fallfabrik erreicht die Kante NICHT - **soll** `prof` je Kopf MEHRERE "
            "MEM-Varianten fahren (Vorschlag: **ja**, eigener kleiner Werkzeugschritt)?")
        self.assertIsNotNone(e)
        self.assertEqual(e["empfehlung"], "ja")
        self.assertTrue(e["frage"].endswith("?"))
        self.assertEqual(e["bei_a"], "")
        self.assertEqual(e["bei_b"], "")

    def test_ab_frage_mit_fragewort(self):
        e = stand.entscheidbar(
            "Der Kern soll gegen eine zweite Instanz geprueft werden - der PPC-Kern "
            "unter `mame/` (A) oder eine Befehlstabelle gegen die ISA (B)? "
            "(Vorschlag: A. bei A: gemessener Vergleich je Form. bei B: nur Stichproben.)")
        self.assertIsNotNone(e)
        self.assertEqual(e["empfehlung"], "A")
        self.assertIn("(A)", e["frage"])
        self.assertIn("?", e["frage"])
        self.assertEqual(e["bei_a"], "gemessener Vergleich je Form")
        self.assertEqual(e["bei_b"], "nur Stichproben")
        self.assertEqual(e["bei_ja"], "")

    def test_ab_frage_ohne_fragewort(self):
        e = stand.entscheidbar(
            "Zwei Wege stehen offen: (A) Waehler zuerst oder (B) Nahtliste zuerst? "
            "(Empfehlung: B. bei B: Nahtliste abgleichen. bei A: Waehler messen.)")
        self.assertIsNotNone(e)
        self.assertEqual(e["empfehlung"], "B")
        self.assertIn("(A)", e["frage"])
        self.assertEqual(e["bei_b"], "Nahtliste abgleichen")
        self.assertEqual(e["bei_a"], "Waehler messen")

    def test_wort_weg_a_gilt_als_alternative(self):
        e = stand.entscheidbar("Geht der Batch Weg A oder Weg B weiter? "
                               "(Vorschlag: B. bei A: Audio. bei B: Kontrollfluss.)")
        self.assertIsNotNone(e)
        self.assertEqual(e["empfehlung"], "B")

    def test_ab_ohne_empfehlung_bleibt_unklar(self):
        self.assertIsNone(stand.entscheidbar(
            "Soll der Kern gegen `mame/` (A) oder gegen die ISA (B) geprueft werden?"))

    def test_ohne_fragezeichen_bleibt_unklar(self):
        self.assertIsNone(stand.entscheidbar(
            "Der Kern (A) oder die ISA (B) - beides denkbar. Vorschlag: A."))
        self.assertIsNone(stand.entscheidbar("Empfehlung: ja"))
        self.assertIsNone(stand.entscheidbar(""))

    def test_ab_wort_wird_nicht_aus_kleingeschriebenen_woertern_geraten(self):
        """`Vorschlag: Abstand` ist keine A/B-Empfehlung (Wortgrenze muss halten)."""
        self.assertIsNone(stand.entscheidbar(
            "Soll das gemessen werden? Vorschlag: Abstand vergroessern."))


class TestAnzeigeAlternativen(Basis):
    def test_fragen_zeigt_folgen_von_a_und_b(self):
        self.anker()
        text = fragen.fragen_text(self.cfg)
        self.assertIn("A4", text)
        self.assertIn("Empfehlung: A", text)
        self.assertIn("bei A:", text)
        self.assertIn("bei B:", text)
        self.assertNotIn("UNKLAR FORMULIERT", text)

    def test_anhang_traegt_die_alternativen_mit(self):
        self.anker()
        p = fragen.nachschlagen(self.cfg, "A4")
        self.assertIsNotNone(p)
        self.assertEqual(p["bei_a"], "Vergleich je Form")
        self.assertEqual(p["bei_b"], "Stichproben")
        anhang = fragen.anhang([p])
        self.assertIn("Empfehlung: A", anhang)
        self.assertIn("bei A: Vergleich je Form", anhang)
        self.assertIn("bei B: Stichproben", anhang)

    def test_ab_frage_ohne_empfehlung_bleibt_unklar_formuliert(self):
        self.anker("""# Workstream R1B

**Stand:** BATCH 101 (2026-09-28) - Beispielstand.
**Offene Entscheidung:** **(4)** soll der Kern gegen `mame/` (A) oder gegen die ISA (B) geprueft werden?
""")
        text = fragen.fragen_text(self.cfg)
        self.assertIn("UNKLAR FORMULIERT", text)
        # beantwortbar bleibt sie trotzdem (Kennung)
        self.assertIn("A4", text)

    def test_antwort_mit_buchstabe_erreicht_den_anhang(self):
        self.anker()
        vor = fragen.nachricht_vorbereiten(self.cfg, "A4 B")
        self.assertTrue(vor["ok"])
        self.assertEqual(vor["bekannt"], ["A4"])
        self.assertIn("bei B:", vor["text"])


if __name__ == "__main__":
    unittest.main()
