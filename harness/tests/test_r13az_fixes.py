"""Tests fuer R13az (2026-09-30): zwei feste Pruefpunkte in beiden Rollenprompts.

**Auftrag (Nutzer).** Zwei Pruefpunkte gehoeren fest in `prompts/aussensicht.md` **und**
`prompts/reviewer.md`:

1. **Messziel gegen Messgroesse.** Fuer jeden Strang wird geprueft, ob die gefuehrte
   Fortschrittszahl das festgelegte Ziel misst (Strang B: Anteil nativer Koepfe an den
   ausgefuehrten Schritten, Nutzerentscheid A4; Strang C: referenzgleiche Koepfe). Wird das
   Ziel nicht gemessen oder steht die Zahl seit mehreren Batches bei 0: Befund melden.
2. **Vorhandene Arbeit.** Jede Aussage "fehlt", "Blockade", "Quelle nicht vorhanden",
   "unbekannte Hardware" wird geprueft, indem `analysis/` und `port/` nach der **Adresse bzw.
   dem Symbol** durchsucht werden (Grep auf den Bezeichner, nicht auf einen geratenen
   Dateinamen); Fundstellen mit `Datei:Zeile`. Anlass: `0x40000000` war seit dem 16.09. in
   `analysis/bucket-d-fun80013d80.md` geklaert und wurde in B220-B222 uebersehen.
3. **Fuer den Reviewer zusaetzlich:** ein Befund gilt erst als erledigt, wenn die
   beabsichtigte **Wirkung** belegt ist (nicht nur "uebernommen" - Beispiel M214-4, dort
   wurde nur die Beschriftung geaendert).

Die Prompt-Texte sind der Pruefgegenstand; die Belegformen, die sie vorschreiben, werden
zusaetzlich **ausgefuehrt** (`aussensicht.beleg_gueltig`, `aussensicht.antworten_uebernehmen`),
damit Prompt und Harness-Verhalten nicht auseinanderlaufen. Die Zitate des Anlasses werden
gegen die echten Dateien geprueft (nur lesend, mit `skipTest`, wenn sie fehlen).
"""

from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import aussensicht                                          # noqa: E402
from hx.config import load_config                                   # noqa: E402
from hx.util import Log, ensure_dir                                 # noqa: E402

AUSSEN = ROOT / "prompts" / "aussensicht.md"
REVIEWER = ROOT / "prompts" / "reviewer.md"

# Die zwei Antwortzeilen der Wirkung-Regel, wortgleich aus `prompts/reviewer.md`.
ZEILE_WIRKUNG_BELEGT = ("M214-4: übernommen als <Ziel> - Wirkung belegt: "
                        "<Datei:Zeile> (Messung/Vergleich)")
ZEILE_WIRKUNG_OFFEN = ("M214-4: übernommen als <Ziel> - Wirkung noch nicht belegt "
                       "-> bleibt offen")

# Die Belegform, die beide Prompts fuer eine gepruefte Fehlstelle vorschreiben.
FEHLSTELLE = ('Fehlstelle: gesucht in analysis/ und port/, nicht gefunden '
              '(Grep "0x40000000")')

ECHTER_CFG = load_config()
DEC = Path(ECHTER_CFG.decomp)


def prompt(p: Path) -> str:
    return p.read_text(encoding="utf-8")


class TestAussensichtPrompt(unittest.TestCase):
    """`prompts/aussensicht.md`: die zwei festen Pruefpunkte."""

    @classmethod
    def setUpClass(cls):
        cls.t = prompt(AUSSEN)

    def test_beide_pruefpunkte_stehen_drin(self):
        self.assertIn("## Zwei feste Prüfpunkte (in JEDEM Lauf", self.t)
        self.assertIn("### 1. Messziel gegen Messgröße", self.t)
        self.assertIn("### 2. Vorhandene Arbeit", self.t)
        self.assertIn("R13az", self.t)

    def test_pruefpunkt_7_verweist_auf_die_liste(self):
        """Der Pruefauftrag nennt die zwei Punkte, damit sie nicht uebersehen werden."""
        self.assertIn("7. **Die zwei festen Prüfpunkte**", self.t)
        self.assertIn("`Messziel: …`", self.t)
        self.assertIn("`Arbeit vorhanden: …`", self.t)

    def test_strang_b_ziel_und_quelle(self):
        self.assertIn("Anteil der nativen Köpfe an den ausgeführten Schritten", self.t)
        self.assertIn("Entscheidung A4", self.t)
        self.assertIn("analysis/hybrid-plan.md:9-10", self.t)
        self.assertIn("readme.md:21", self.t)

    def test_strang_c_ziel(self):
        self.assertIn("**referenzgleiche Köpfe**", self.t)
        self.assertIn("Rotprobe", self.t)
        self.assertIn("nicht die gebauten, abgelegten oder", self.t)

    def test_nullregel_ist_ein_befund(self):
        self.assertIn("seit mehreren Batches bei 0", self.t)
        self.assertIn("mit den Batches, in denen sie sich nicht bewegt hat", self.t)
        self.assertIn("Nenne die Ersatzzahl **und** das Ziel, das sie nicht misst.", self.t)

    def test_grep_auf_den_bezeichner_nicht_auf_den_dateinamen(self):
        self.assertIn("**Grep auf den Bezeichner**", self.t)
        self.assertIn("Nicht** auf einen geratenen Dateinamen", self.t)
        self.assertIn("`0x40000000`", self.t)
        self.assertIn("`FUN_80013d80`", self.t)
        self.assertIn("**`Datei:Zeile`**", self.t)

    def test_fehlstelle_form_wird_vorgeschrieben(self):
        self.assertIn("Fehlstelle: gesucht in analysis/ und port/, nicht gefunden", self.t)

    def test_anlass_ist_im_prompt_belegt(self):
        self.assertIn("analysis/bucket-d-fun80013d80.md:121", self.t)
        self.assertIn("ppccom.cpp:322", self.t)
        self.assertIn("B220–B222", self.t)
        self.assertIn("runs/b222/review.md:3", self.t)

    def test_erledigt_nur_mit_wirkung(self):
        """Punkt 3 fuer die Aussensicht: nur die Beschriftung geaendert => `offen`."""
        self.assertIn("**`erledigt`\n   nur mit belegter Wirkung (R13az):**", self.t)
        self.assertIn("lautet das Verdikt `offen`", self.t)

    def test_beleg_tabelle_nennt_die_neue_fehlstelle(self):
        i = self.t.index("| ausdrückliche Fehlstelle |")
        self.assertIn("Grep \"0x40000000\"", self.t[i:i + 200])


class TestReviewerPrompt(unittest.TestCase):
    """`prompts/reviewer.md`: dieselben zwei Punkte + die Wirkung-Regel."""

    @classmethod
    def setUpClass(cls):
        cls.t = prompt(REVIEWER)

    def test_beide_pruefpunkte_stehen_drin(self):
        self.assertIn("### Zwei feste Prüfpunkte (in JEDEM Review, R13az", self.t)
        self.assertIn("**a) Messziel gegen Messgröße — je Strang.**", self.t)
        self.assertIn("**b) „fehlt\" wird geprüft, nicht geglaubt.**", self.t)
        self.assertIn("6. **Die zwei festen Prüfpunkte** prüfen", self.t)

    def test_dieselben_ziele_wie_in_der_aussensicht(self):
        a = prompt(AUSSEN)
        for satz in ("Anteil der nativen Köpfe an den ausgeführten Schritten",
                     "analysis/hybrid-plan.md:9-10", "readme.md:21",
                     "**referenzgleiche Köpfe**", "seit **mehreren Batches bei 0**"):
            roh = satz.replace("**", "")
            self.assertIn(roh, a.replace("**", ""), satz)
            self.assertIn(roh, self.t.replace("**", ""), satz)

    def test_ersatzzahl_wird_gekennzeichnet(self):
        self.assertIn("Ersatzzahl", self.t)
        self.assertIn("als Ersatzzahl", self.t)

    def test_instruktion_muss_die_zielzahl_erheben(self):
        self.assertIn("Deine **Instruktion** muss die Zahl erheben, die das Ziel misst", self.t)

    def test_fehlt_nur_nach_eigener_suche_auch_gegen_die_eigene_entscheidung(self):
        self.assertIn("aus **deiner eigenen** früheren Entscheidung", self.t)
        self.assertIn("Blockade-Begründung ist keine Tatsache", self.t)
        self.assertIn("analysis/bucket-d-fun80013d80.md:121", self.t)
        self.assertIn("`runs/b222/review.md:3`", self.t)

    def test_wirkung_regel_und_zeilen(self):
        self.assertIn("„Übernommen\" ist erst erledigt, wenn die Wirkung belegt ist", self.t)
        self.assertIn(ZEILE_WIRKUNG_BELEGT, self.t)
        self.assertIn(ZEILE_WIRKUNG_OFFEN, self.t)
        self.assertIn("ist **keine** Wirkung", self.t)
        self.assertIn("hx/aussensicht.py:1338", self.t)

    def test_m214_4_als_beispiel(self):
        self.assertIn("Befund M214-4", self.t)
        self.assertIn("state/meta_befunde.json", self.t)
        self.assertIn("die verlangte Wirkung", self.t)


class Basis(unittest.TestCase):
    """Wegwerf-Harness mit Wegwerf-Decomp-Repo fuer das Register (wie test_r13ak)."""

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13az"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "root")
        self.decomp = ensure_dir(self.tmp / "decomp")
        ensure_dir(self.decomp / "analysis")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.decomp)
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["paths"]["harness_home"] = str(self.tmp)
        cfg.data["telegram"]["allowlist_user_ids"] = []
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)
        aussensicht.ledger_schreiben(self.cfg, [self.befund("M214-4")])

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    @staticmethod
    def befund(bid: str, status: str = "offen") -> dict:
        return {"id": bid, "batch": int(bid[1:4]), "gewicht": "mittel",
                "empfaenger": "Reviewer", "beleg": "hx/x.py:1", "aussage": "a",
                "empfehlung": "b", "status": status, "antwort": "",
                "antwort_batch": None}

    def status(self) -> str:
        return str(aussensicht.ledger(self.cfg)[0].get("status"))


class TestWirkungZeilenVerhalten(Basis):
    """Die zwei Antwortzeilen aus dem Prompt tun im Register das Zugesagte (R13az)."""

    def test_belegte_wirkung_schliesst_den_befund(self):
        self.assertEqual(aussensicht.antworten_uebernehmen(
            self.cfg, ZEILE_WIRKUNG_BELEGT, 223), ["M214-4"])
        self.assertEqual(self.status(), "uebernommen")
        self.assertEqual(aussensicht.offene(self.cfg), [])

    def test_fehlende_wirkung_haelt_den_befund_offen(self):
        self.assertEqual(aussensicht.antworten_uebernehmen(
            self.cfg, ZEILE_WIRKUNG_OFFEN, 223), ["M214-4"])
        self.assertEqual(self.status(), "offen")
        self.assertEqual([b["id"] for b in aussensicht.offene(self.cfg)], ["M214-4"])

    def test_wirkung_mit_beleg_in_der_zeile(self):
        """So sieht die Zeile im Normalfall aus: Ziel UND Beleg in einer Zeile."""
        zeile = ("M214-4: übernommen als B-SCHRITT-Feld - Wirkung belegt: "
                 "runs/b223/review.md:11")
        aussensicht.antworten_uebernehmen(self.cfg, zeile, 223)
        self.assertEqual(self.status(), "uebernommen")
        self.assertEqual(aussensicht.klasse(aussensicht.ledger(self.cfg)[0]),
                         "uebernommen")

    def test_fehlstelle_ist_ein_gueltiger_beleg(self):
        self.assertTrue(aussensicht.beleg_gueltig(FEHLSTELLE))

    def test_behauptung_ohne_fundstelle_ist_kein_beleg(self):
        """Genau der Anlass: 'fehlt' ohne Suche darf kein Befund werden."""
        for text in ("0x40000000 fehlt in der Hardware",
                     "das Symbol ist nirgends vorhanden",
                     "Blockade: Quelle nicht vorhanden"):
            self.assertFalse(aussensicht.beleg_gueltig(text), text)


class TestAnlassImRepo(unittest.TestCase):
    """Die im Prompt zitierten Fundstellen stimmen (nur lesend; skip, wenn nicht da)."""

    def test_bucket_d_klart_0x40000000(self):
        p = DEC / "analysis" / "bucket-d-fun80013d80.md"
        if not p.is_file():
            self.skipTest(f"{p} fehlt")
        zeilen = p.read_text(encoding="utf-8").splitlines()
        self.assertIn("0x40000000", zeilen[120])
        self.assertIn("aufgeloest", zeilen[120])
        self.assertIn("SPU", zeilen[121])

    def test_hybrid_plan_nennt_das_ziel(self):
        p = DEC / "analysis" / "hybrid-plan.md"
        if not p.is_file():
            self.skipTest(f"{p} fehlt")
        text = "\n".join(p.read_text(encoding="utf-8").splitlines()[8:10])
        self.assertIn("schrumpfenden Anteil", text)
        self.assertIn("interpretierten Codes", text)

    def test_bericht_b221_zaehlt_null_prozent(self):
        p = DEC / "analysis" / "bericht-b221-berichtspunkt-hybrid.md"
        if not p.is_file():
            self.skipTest(f"{p} fehlt")
        zeile = p.read_text(encoding="utf-8").splitlines()[127]
        self.assertIn("Anteil native Koepfe an den Hybrid-Schritten: 0 von", zeile)
        self.assertIn("= 0 %", zeile)

    def test_reviewer_gesteht_den_fehler_ein(self):
        p = ROOT / "runs" / "b222" / "review.md"
        if not p.is_file():
            self.skipTest(f"{p} fehlt")
        zeile = p.read_text(encoding="utf-8").splitlines()[2]
        self.assertIn("nicht nach der Adresse durchsucht", zeile)


if __name__ == "__main__":
    unittest.main(verbosity=2)
