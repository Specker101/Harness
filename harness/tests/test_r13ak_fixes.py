"""Tests fuer R13ak (2026-09-29): zwei Fixes aus der Postfach-Pruefung.

**Fix 1 - Antwortmuster zu streng (`hx/aussensicht.py`).** Das Muster verlangte das
Verdikt DIREKT hinter dem Doppelpunkt. Gemessen waren zwei Befunde deshalb weiter
„offen", obwohl der Reviewer geantwortet hatte:

* `runs/b211/review.md:15` — „M209-3b: **zurückgestellt** (Nutzer), spätestens B216"
* `runs/b213/review.md:11` — „M212-1: **für B213 abgelehnt** (Werkzeug vor Serie),
  **für B216 übernommen** (SOLL-KOEPFE > 0, Liste aus B213)"

Jetzt zählt der Text hinter der Kennung, und **das letzte Verdikt darin** entscheidet;
`zurueckgestellt` ist eine Antwort (Klasse `uebernommen`, das Wort bleibt im Register).
Beide echten Zeilen werden nachgetragen (`docs/_r13ak_nachtrag.py`).

**Fix 2 - Doppelzustellung nach verworfenem Gate (`hx/queue.py`, `hx/orchestrator.py`).**
Ein verworfenes Gate laesst seine `/claude`-Nachrichten liegen (R13u) — richtig, aber die
Antwort steht schon im Register (`antworten_uebernehmen` laeuft VOR der Gate-Entscheidung).
Beim erneuten Zustellen tragen solche Aussensicht-Nachrichten jetzt den Vermerk
`(bereits beantwortet im verworfenen Review: <Verdikt>)` in der ersten Zeile, statt als neu
zu gelten. Gemessen: M209-1/2/3b/4 und M210-1…5 wurden am 28.09. um 20:38 und noch einmal
um 20:51 zugestellt (`logs/review-prompt-*`), nachdem um 20:50:59 ein Auftrag verworfen
wurde.
"""

from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import aussensicht, queue                               # noqa: E402
from hx.config import load_config                               # noqa: E402
from hx.orchestrator import Orchestrator                        # noqa: E402
from hx.util import Log, ensure_dir, read_text, write_text_atomic   # noqa: E402

# Die beiden echten Zeilen aus den Reviews (wortgleich, nur fuer den Test kopiert).
ZEILE_B211 = "M209-3b: zurückgestellt (Nutzer), spätestens B216"
ZEILE_B213 = ("M212-1: für B213 abgelehnt (Werkzeug vor Serie), für B216 übernommen "
              "(SOLL-KOEPFE > 0, Liste aus B213)")


class Basis(unittest.TestCase):
    """Wegwerf-Harness mit Wegwerf-Decomp-Repo (wie test_r13z/test_r13ah)."""

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13ak"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "root")
        self.decomp = ensure_dir(self.tmp / "decomp")
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

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def ledger(self, *eintraege: dict) -> None:
        aussensicht.ledger_schreiben(self.cfg, list(eintraege))

    @staticmethod
    def befund(bid: str, status: str = "offen") -> dict:
        return {"id": bid, "batch": int(bid[1:4]), "gewicht": "mittel",
                "empfaenger": "Reviewer", "beleg": "hx/x.py:1", "aussage": "a",
                "empfehlung": "b", "status": status, "antwort": "",
                "antwort_batch": None}

    def nachricht(self, mid: str, text: str, source: str = "aussensicht") -> Path:
        d = ensure_dir(self.root / "inbox" / "claude")
        p = d / f"{mid}.md"
        write_text_atomic(p, f"---\nid: {mid}\nts: 2026-09-29T16:43:36+00:00\n"
                             f"target: claude\nsource: {source}\nuser_id: \n---\n{text}\n")
        return p

    def orch(self) -> Orchestrator:
        o = Orchestrator(self.cfg, self.log, mock=True,
                         state_file=self.root / "state" / "run.json")
        o.qroot = self.root
        return o

    @staticmethod
    def aussensicht_text(bid: str) -> str:
        return "\n".join([
            f"Aussensicht Batch {int(bid[1:4])} - Befund {bid} (Gewicht mittel):",
            "Beleg: `hybrid-plan.md:230-232`",
            "Aussage: x", "Empfehlung: y", "",
            f"Bitte im naechsten Review beantworten: \"{bid}: uebernommen (…)\" oder "
            f"\"{bid}: abgelehnt, Grund …\"."])


class TestTolerantesAntwortmuster(Basis):
    """Fix 1: zurueckgestellt + letztes Verdikt der Zeile."""

    def test_echte_zeile_b211_zurueckgestellt(self):
        self.ledger(self.befund("M209-3b"))
        geaendert = aussensicht.antworten_uebernehmen(self.cfg, ZEILE_B211, 210)
        self.assertEqual(geaendert, ["M209-3b"])
        e = {b["id"]: b for b in aussensicht.ledger(self.cfg)}["M209-3b"]
        self.assertEqual(e["status"], "zurueckgestellt")
        self.assertEqual(e["antwort_batch"], 210)
        self.assertIn("spätestens B216", e["antwort"])
        self.assertEqual(aussensicht.offene(self.cfg), [])

    def test_echte_zeile_b213_letztes_verdikt_gewinnt(self):
        self.ledger(self.befund("M212-1"))
        self.assertEqual(aussensicht.antworten_uebernehmen(self.cfg, ZEILE_B213, 212),
                         ["M212-1"])
        e = {b["id"]: b for b in aussensicht.ledger(self.cfg)}["M212-1"]
        self.assertEqual(e["status"], "uebernommen",
                         "das SPAETERE Verdikt der Zeile entscheidet")
        self.assertEqual(aussensicht.offene(self.cfg), [])

    def test_echte_zeilen_stehen_wirklich_so_im_repo(self):
        """Die Vorlage im Test ist wortgleich mit den Review-Dateien."""
        p211 = ROOT / "runs" / "b211" / "review.md"
        p213 = ROOT / "runs" / "b213" / "review.md"
        if not (p211.is_file() and p213.is_file()):
            self.skipTest("runs/b211 bzw. b213 fehlen")
        z211 = read_text(p211).splitlines()[14].strip()
        z213 = read_text(p213).splitlines()[10].strip()
        self.assertIn("M209-3b: zur", z211)
        self.assertEqual(z211, ZEILE_B211)
        self.assertIn("M212-1: ", z213)
        self.assertIn("f\u00fcr B216 \u00fcbernommen", z213)
        self.assertEqual(z213, ZEILE_B213)

    def test_zurueckgestellt_zaehlt_nicht_als_offen(self):
        for wort in ("zurueckgestellt", "zurückgestellt"):
            self.assertEqual(aussensicht.klasse({"status": wort}), "uebernommen", wort)
        # Die Quote bleibt dreiteilig (R13z) - „zurueckgestellt" ist kein eigener Topf.
        self.ledger(self.befund("M209-3b", "zurueckgestellt"), self.befund("M212-1"))
        self.assertEqual(aussensicht.quote(self.cfg),
                         {"gesamt": 2, "uebernommen": 1, "abgelehnt": 0, "offen": 1})

    def test_ohne_verdikt_keine_antwort(self):
        """Prosa, die eine Kennung nur erwaehnt, darf den Befund nicht zuklappen."""
        self.ledger(self.befund("M212-1"))
        for text in ("M212-1: siehe oben", "M212-1 wurde nicht beantwortet",
                     "siehe M212-1"):
            self.assertEqual(aussensicht.antworten_uebernehmen(self.cfg, text, 213), [],
                             text)
        self.assertEqual([b["id"] for b in aussensicht.offene(self.cfg)], ["M212-1"])

    def test_abgelehnt_bleibt_abgelehnt(self):
        self.ledger(self.befund("M212-1"))
        aussensicht.antworten_uebernehmen(
            self.cfg, "M212-1: abgelehnt, die Werkzeugliste kommt vor der Serie", 212)
        self.assertEqual(aussensicht.klasse(aussensicht.ledger(self.cfg)[0]), "abgelehnt")

    def test_offen_als_verdikt_haelt_den_befund_offen(self):
        self.ledger(self.befund("M213-4a", "offen"))
        aussensicht.antworten_uebernehmen(
            self.cfg, "M213-4a: offen, der Nutzer muss entscheiden", 213)
        self.assertEqual(aussensicht.klasse(aussensicht.ledger(self.cfg)[0]), "offen")

    def test_kennung_aus_dem_nachrichtentext(self):
        self.assertEqual(aussensicht.kennung_aus_text(self.aussensicht_text("M214-5b")),
                         "M214-5b")
        self.assertEqual(aussensicht.kennung_aus_text("kein Befund hier"), "")

    def test_geteilter_befund_kurzform_gilt_weiter(self):
        self.ledger(self.befund("M208-5a"), self.befund("M208-5b"))
        self.assertEqual(sorted(aussensicht.antworten_uebernehmen(
            self.cfg, "M208-5: übernommen (beide Teile)", 209)), ["M208-5a", "M208-5b"])


class TestVermerkImPostfach(Basis):
    """Fix 2: Vermerk fuer schon beantwortete Aussensicht-Nachrichten."""

    def test_beantworteter_befund_bekommt_den_vermerk(self):
        self.nachricht("20260929_164336_0000_AAAA", self.aussensicht_text("M214-1"))
        self.ledger(self.befund("M214-1", "uebernommen"))
        block, ids = self.orch().read_queue_block("claude", mark=False)
        self.assertEqual(ids, ["20260929_164336_0000_AAAA"])
        self.assertIn("(bereits beantwortet im verworfenen Review: uebernommen)", block)
        # Der Vermerk steht in der ERSTEN Zeile des Eintrags, nicht am Ende.
        erste = [z for z in block.splitlines()
                 if z.startswith("- [2026-09-29T16:43:36+00:00 | aussensicht]")][0]
        self.assertIn("M214-1", erste)
        self.assertIn("bereits beantwortet", erste)
        self.assertNotIn("Bitte im naechsten Review beantworten", erste)

    def test_zurueckgestellt_bekommt_den_vermerk_mit_seinem_wort(self):
        self.nachricht("20260929_164336_0000_BBBB", self.aussensicht_text("M209-3b"))
        self.ledger(self.befund("M209-3b", "zurueckgestellt"))
        block, _ids = self.orch().read_queue_block("claude", mark=False)
        self.assertIn("(bereits beantwortet im verworfenen Review: zurueckgestellt)", block)

    def test_offener_befund_bleibt_ohne_vermerk(self):
        self.nachricht("20260929_164336_0000_CCCC", self.aussensicht_text("M214-2"))
        self.ledger(self.befund("M214-2", "offen"))
        block, _ids = self.orch().read_queue_block("claude", mark=False)
        self.assertNotIn("bereits beantwortet", block)
        self.assertNotIn("schon entschieden", block)
        self.assertIn("Bitte im naechsten Review beantworten", block)

    def test_unbekannter_befund_bleibt_ohne_vermerk(self):
        self.nachricht("20260929_164336_0000_DDDD", self.aussensicht_text("M214-9"))
        self.ledger(self.befund("M214-1", "uebernommen"))
        block, _ids = self.orch().read_queue_block("claude", mark=False)
        self.assertNotIn("bereits beantwortet", block)

    def test_nutzer_nachricht_mit_befundkennung_bekommt_keinen_vermerk(self):
        """Nur `source: aussensicht` wird vermerkt - ein Zitat in einer Telegram-Nachricht
        darf nicht als Befund gedeutet werden."""
        self.nachricht("20260929_164336_0000_EEEE",
                       "Bitte pruefen: Aussensicht Batch 214 - Befund M214-1 "
                       "(Gewicht hoch):", source="telegram")
        self.ledger(self.befund("M214-1", "uebernommen"))
        block, _ids = self.orch().read_queue_block("claude", mark=False)
        self.assertNotIn("bereits beantwortet", block)

    def test_hinweiszeile_nur_wenn_vermerkt(self):
        self.nachricht("20260929_164336_0000_FFFF", self.aussensicht_text("M214-1"))
        self.ledger(self.befund("M214-1", "uebernommen"))
        block, _ids = self.orch().read_queue_block("claude", mark=False)
        self.assertIn("sie werden NICHT erneut beantwortet", block)

    def test_leere_queue_bleibt_leer(self):
        self.assertEqual(queue.deliver_block(self.root, "claude", []), ("", []))

    def test_vermerk_wird_auch_bei_gemischter_queue_gesetzt(self):
        self.nachricht("20260929_164336_0000_GGGG", self.aussensicht_text("M214-1"))
        self.nachricht("20260929_165742_0000_HHHH",
                       "Bitte vor dem Commit noch die Bilanz zeigen.", source="telegram")
        self.ledger(self.befund("M214-1", "uebernommen"))
        block, ids = self.orch().read_queue_block("claude", mark=False)
        self.assertEqual(len(ids), 2)
        self.assertIn("bereits beantwortet", block)
        self.assertIn("Bitte vor dem Commit noch die Bilanz zeigen.", block)
        self.assertEqual(block.count("sie werden NICHT erneut beantwortet"), 1)


class TestZustellungAmEchtenFall(Basis):
    """Der 28.09.-Fall als Regressionspflock: dieselben ids wurden zweimal zugestellt."""

    def test_die_zehn_nachrichten_des_verworfenen_auftrags(self):
        """Nach dem verworfenen Auftrag (batch 211) trugen M209-*/M210-* kein Vermerk -
        sie wurden als NEU vorgelegt. Genau das ist jetzt markiert."""
        self.ledger(*[self.befund(b, "uebernommen") for b in
                      ("M209-1", "M209-3b", "M209-2", "M209-4",
                       "M210-1", "M210-2", "M210-3", "M210-4", "M210-5")])
        for i, bid in enumerate(("M209-1", "M209-3b", "M209-2", "M209-4",
                                 "M210-1", "M210-2", "M210-3", "M210-4", "M210-5"), 1):
            self.nachricht(f"20260928_203834_0000_{i:04d}", self.aussensicht_text(bid))
        block, ids = self.orch().read_queue_block("claude", mark=False)
        self.assertEqual(len(ids), 9)
        self.assertEqual(block.count("(bereits beantwortet im verworfenen Review: "
                                     "uebernommen)"), 9)

    def test_register_zustand_ist_lesbar(self):
        """Der Testfall steht auch als Datei im Wegwerfordner (Nachvollziehbarkeit)."""
        self.ledger(self.befund("M214-1", "uebernommen"))
        p = aussensicht.ledger_pfad(self.cfg)
        daten = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(daten["befunde"][0]["id"], "M214-1")


if __name__ == "__main__":
    unittest.main()
