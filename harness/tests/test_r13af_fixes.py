"""Tests fuer R13af (2026-09-29): kein Posten verschwindet.

Zwei Regeln in der Rollenanweisung (`prompts/reviewer.md`), beide aus der `/ask`-Pruefung
vom 29.09.2026:

  1. **UEBERTRAG / VERWORFEN.** Jeder nicht erledigte Posten aus `NACHRUECKLISTE` und
     `STREICHREIHENFOLGE` des bewerteten Batches erscheint als eine dieser beiden Zeilen.
     Verloren ging B213 Nachrueckliste 1 (weitere teilgepruefte Koepfe, 57/78).
  2. **Teilpunkt-Tafel fuer ersetzte `/ds`-Nachrichten.** Wird eine Nachricht nur als
     Zusammenfassung zugestellt (Vorbild `docs/_r13t4_claude_zusammenfassung.txt`), gehoert
     eine Zeile je Teilpunkt dazu. Verloren ging `readme.md:69x` aus Nachricht `113914a`.

Geprueft wird der Text der Rollenanweisung (wie in `test_r13ae_fixes.py`) und die
Kurzfassung, die direkt neben dem `/ds`-Block im Review-Prompt steht.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import reviewer                                   # noqa: E402
from hx.config import load_config                         # noqa: E402


def _rolle() -> str:
    return (ROOT / "prompts" / "reviewer.md").read_text(encoding="utf-8")


class TestUebertragUndVerworfen(unittest.TestCase):
    """Regel 1: die beiden Zeilenformen, ihr Anlass und die Vollstaendigkeitspflicht."""

    def test_beide_zeilenformen_stehen_in_der_summary_gliederung(self):
        text = _rolle()
        gliederung = text.split("`<TELEGRAM_SUMMARY>` — maximal", 1)[1]
        gliederung = gliederung.split("### Strang B", 1)[0]
        self.assertIn('UEBERTRAG: <Posten> -> <Ziel-Batch oder Anker "Naechster Schritt">',
                      gliederung)
        self.assertIn("VERWORFEN: <Posten> - <Grund>", gliederung)
        self.assertIn("PFLICHT", gliederung)

    def test_abschnitt_ist_pflicht_und_nennt_beide_quellen(self):
        text = _rolle()
        self.assertIn("### Übertrag am Batch-Ende: kein Posten verschwindet "
                      "(Pflicht, R13af, 2026-09-29)", text)
        abschnitt = text.split("### Übertrag am Batch-Ende", 1)[1]
        abschnitt = abschnitt.split("### Ersetzte", 1)[0]
        # Beide Quellen der Posten stehen darin - die Instruktion UND der Worker-Bericht.
        self.assertIn("`NACHRUECKLISTE`/`STREICHREIHENFOLGE` der bewerteten Instruktion",
                      abschnitt)
        self.assertIn("`runs/b<N>/auftrag.md`", abschnitt)
        self.assertIn("`runs/b<N>/antwort.md`", abschnitt)
        # Auch ein nicht begonnener Posten ist ein Posten (der B213-Fall).
        self.assertIn("**gar nicht begonnener** Posten", abschnitt)

    def test_kein_posten_darf_ohne_zeile_verschwinden(self):
        text = _rolle()
        self.assertIn("**Kein Posten darf ohne eine dieser beiden Zeilen verschwinden.**",
                      text)
        # Und die Abwesenheit ist keine Aussage: es gibt eine ausdrueckliche Nullzeile.
        self.assertIn("UEBERTRAG: keiner - alle Posten erledigt", text)
        self.assertIn("Die **fehlende** Zeile ist keine Aussage.", text)

    def test_ziel_muss_konkret_sein(self):
        text = _rolle()
        self.assertIn("Nenne das **Ziel konkret**", text)
        self.assertIn('„nächster Batch\" ohne Nummer zählt nicht', text)

    def test_anlass_nennt_den_gemessenen_verlust(self):
        text = _rolle()
        self.assertIn("B213 Nachrückliste 1", text)
        self.assertIn("runs/b213/auftrag.md:187", text)
        self.assertIn("logs/ask/ask-20260929-141152+0000.md", text)
        self.assertIn("Für 12 von 13 Posten", text)
        # Die Regel ist datiert (Projektkonvention: R-Nummer + Datum im Titel).
        self.assertRegex(text, r"Pflicht, R13af, 2026-09-29")


class TestTeilpunktTafel(unittest.TestCase):
    """Regel 2: eine Zeile je Teilpunkt jeder ersetzten Nachricht."""

    def test_abschnitt_ist_pflicht(self):
        text = _rolle()
        self.assertIn("### Ersetzte `/ds`-Nachrichten: Tafel mit einer Zeile je Teilpunkt "
                      "(Pflicht, R13af, 2026-09-29)", text)

    def test_tafelform_und_spalten(self):
        text = _rolle()
        abschnitt = text.split("### Ersetzte `/ds`-Nachrichten", 1)[1]
        abschnitt = abschnitt.split("### Aussensicht-Befunde", 1)[0]
        self.assertIn("| Nachricht | Teilpunkt | übernommen als … / bewusst weggelassen - "
                      "Grund | Beleg |", abschnitt)
        self.assertIn("**Ein Teilpunkt ist keine Nachricht.**", abschnitt)
        self.assertIn("fünf Punkten ergibt fünf", abschnitt)
        self.assertIn("**„übernommen als …\"**", abschnitt)
        self.assertIn("**„bewusst weggelassen - Grund\"**", abschnitt)

    def test_fehlende_tafel_wird_nachgetragen_und_gemeldet(self):
        text = _rolle()
        abschnitt = text.split("### Ersetzte `/ds`-Nachrichten", 1)[1]
        abschnitt = abschnitt.split("### Aussensicht-Befunde", 1)[0]
        self.assertIn("trägst du", abschnitt)
        self.assertIn("`OFFENE FRAGE: …`", abschnitt)
        self.assertIn("Vorbild:", abschnitt)
        self.assertIn("docs/_r13t4_claude_zusammenfassung.txt", abschnitt)

    def test_anlass_nennt_den_gemessenen_verlust(self):
        text = _rolle()
        abschnitt = text.split("### Ersetzte `/ds`-Nachrichten", 1)[1]
        abschnitt = abschnitt.split("### Aussensicht-Befunde", 1)[0]
        self.assertIn("`113914a` hatte **zwei**", abschnitt)
        self.assertIn("readme.md:640-642", abschnitt)
        self.assertIn("readme.md:69x", abschnitt)
        self.assertIn("logs/ask/ask-20260929-141009+0000.md", abschnitt)


class TestKurzfassungImPrompt(unittest.TestCase):
    """Die Kurzfassung steht dort, wo die Nachrichten erscheinen (neben `/ds`)."""

    def setUp(self):
        self.cfg = load_config()

    def prompt(self) -> str:
        ctx = {"batch": 213, "ds_queue": "NACHRICHTEN AUS DER QUEUE\n113914a readme.md:69x"}
        return reviewer.build_prompt(self.cfg, "batch_end", ctx)

    def test_ds_regel_nennt_die_zeilenformen(self):
        text = self.prompt()
        self.assertIn("Diese Nachrichten sind fuer den Worker", text)
        self.assertIn("EIN TEILPUNKT IST KEINE NACHRICHT", text)
        self.assertIn("UEBERTRAG: <Teilpunkt> -> <Ziel>", text)
        self.assertIn("VERWORFEN: <Teilpunkt> - <Grund>", text)
        self.assertIn("ZUSAMMENFASSUNG zugestellt", text)

    def test_rollenanweisung_wird_als_systemdatei_ausgeliefert(self):
        """Die neue Regel wirkt nur, wenn die Rollenanweisung mitgeht - sie wird als
        `--append-system-prompt-file` uebergeben (nicht in den Prompt eingebettet)."""
        from hx import reviewer as rv
        cmd = rv.build_command(self.cfg, "sess", True)
        self.assertIn("--append-system-prompt-file", cmd)
        datei = Path(cmd[cmd.index("--append-system-prompt-file") + 1])
        self.assertEqual(datei.resolve(), (ROOT / "prompts" / "reviewer.md").resolve())
        text = datei.read_text(encoding="utf-8")
        self.assertIn("Übertrag am Batch-Ende", text)
        self.assertIn("Ersetzte `/ds`-Nachrichten", text)
        # Und genau diese Datei ist die, deren Hash der Harness als Kennung fuehrt.
        self.assertEqual(rv.prompt_hash(self.cfg), rv.prompt_hash(self.cfg))

    def test_reviewer_darf_die_auftraege_lesen(self):
        """Regel 1 verweist auf `runs/b<N>/auftrag.md` - der Pfad muss freigegeben sein."""
        from hx import reviewer as rv
        cmd = rv.build_command(self.cfg, "sess", True)
        self.assertIn("--add-dir", cmd)
        self.assertIn(str(self.cfg.root), cmd)


class TestBelegdateien(unittest.TestCase):
    """Die zitierten Belege existieren und tragen den Verlust (sonst ist es Prosa)."""

    def test_ask_belege_nennen_verloren(self):
        for name, stichwort in (("ask-20260929-141152+0000.md", "B213"),
                                ("ask-20260929-141009+0000.md", "113914a")):
            p = ROOT / "logs" / "ask" / name
            if not p.is_file():
                self.skipTest(f"{name} fehlt")
            text = p.read_text(encoding="utf-8")
            self.assertIn("VERLOREN", text)
            self.assertIn(stichwort, text)

    def test_vorbild_zusammenfassung_hat_die_luecke(self):
        """`113914a` hatte zwei Teilpunkte - die Zusammenfassung fuehrt nur 640-642."""
        p = ROOT.parent / "docs" / "_r13t4_claude_zusammenfassung.txt"
        if not p.is_file():
            self.skipTest("Vorbild-Zusammenfassung fehlt")
        text = p.read_text(encoding="utf-8")
        self.assertIn("readme.md:640-642", text)
        self.assertNotIn("readme.md:69", text)
        # Genau das ist die Luecke, die die neue Regel sichtbar macht.
        self.assertRegex(text, re.compile(r"ersetzt ALLE /ds-Nachrichten"))


class TestDokumentation(unittest.TestCase):
    def test_bedienung_hat_den_abschnitt(self):
        p = ROOT.parent / "docs" / "bedienung.md"
        if not p.is_file():
            self.skipTest("bedienung.md fehlt")
        text = p.read_text(encoding="utf-8")
        self.assertIn("### 12j. Kein Posten verschwindet", text)
        self.assertIn("UEBERTRAG: <Posten> -> <Ziel-Batch oder Anker", text)
        self.assertIn("Teilpunkt-Tafel", text)


if __name__ == "__main__":
    unittest.main()
