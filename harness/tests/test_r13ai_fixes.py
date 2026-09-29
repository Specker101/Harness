"""Tests fuer R13ai (2026-09-29): die Regel "Fragen an den Nutzer".

Gefragt wird nur bei grundsaetzlichen Weichenstellungen (Projektziel, Strategie,
Strangwechsel, Aufnahmen, Budget/Umfang). Technische Einzelposten entscheidet der Reviewer
selbst und fuehrt sie als `ENTSCHIEDEN (Reviewer): …` mit Begruendung. Muss doch gefragt
werden: Alltagssprache, je Frage ein Satz, was sich im Ergebnis aendert, und eine
Empfehlung - keine Regel- oder Postennummern ohne Erklaerung.

Der Nachtrag zu R13ah (`BASH_DEFAULT_TIMEOUT_MS` bleibt 600 s, Vorspann-Zeile) wird in
`tests/test_r13ah_fixes.py::TestTimeoutVorgabe` geprueft.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import reviewer                                      # noqa: E402
from hx.config import load_config                            # noqa: E402


def _rolle() -> str:
    return (ROOT / "prompts" / "reviewer.md").read_text(encoding="utf-8")


def _abschnitt(text: str, kopf: str, ende: str) -> str:
    return text.split(kopf, 1)[1].split(ende, 1)[0]


# ==================================== 1) Fragen an den Nutzer
class TestFragenAnDenNutzer(unittest.TestCase):
    def test_abschnitt_ist_da_und_datiert(self):
        text = _rolle()
        self.assertIn("## Fragen an den Nutzer (R13ai, 2026-09-29)", text)

    def test_nur_grundsaetzliche_weichenstellungen(self):
        a = _abschnitt(_rolle(), "## Fragen an den Nutzer", "## Ideen, die auf den Nutzer")
        self.assertIn("Gefragt wird nur bei grundsätzlichen Weichenstellungen", a)
        for begriff in ("Projektziel", "Strategie", "Strangwechsel", "Aufnahmen",
                        "Budget"):
            self.assertIn(begriff, a)
        self.assertIn("die fünf Fälle aus „Wer entscheidet was\"", a)

    def test_technische_einzelposten_entscheidet_der_reviewer(self):
        a = _abschnitt(_rolle(), "## Fragen an den Nutzer", "## Ideen, die auf den Nutzer")
        self.assertIn("Technische Einzelposten entscheidest du selbst", a)
        self.assertIn("`ENTSCHIEDEN (Reviewer): …`", a)
        self.assertIn("mit einer Begründung im Batch-Dokument", a)
        for beispiel in ("Zähler- und\n  Anzeigefehler", "Werkzeug-Altposten",
                         "`R330`", "`R535`"):
            self.assertIn(beispiel, a)
        # Die Kernaussage: eine Regelnummer ist kein Entscheidungsgrund.
        self.assertIn("ist **kein** Entscheidungsgrund", a)

    def test_wenn_doch_gefragt_wird(self):
        a = _abschnitt(_rolle(), "## Fragen an den Nutzer", "## Ideen, die auf den Nutzer")
        self.assertIn("in **Alltagssprache**", a)
        self.assertIn("**ein Satz**", a)
        self.assertIn("**was sich im Ergebnis ändert**", a)
        self.assertIn("**Empfehlung**", a)
        self.assertIn("**Keine Regel- oder Postennummern ohne Erklärung**", a)

    def test_beispiele_gut_und_schlecht(self):
        a = _abschnitt(_rolle(), "## Fragen an den Nutzer", "## Ideen, die auf den Nutzer")
        self.assertIn("Gute Frage (Weichenstellung, ein Satz, Wirkung, Empfehlung)", a)
        self.assertIn("Schlechte Frage (technischer Einzelposten", a)
        gut = _abschnitt(a, "Gute Frage", "Schlechte Frage")
        self.assertIn("ENTSCHEIDUNG NOETIG:", gut)
        self.assertIn("Ergebnis:", gut)
        self.assertIn("Vorschlag:", gut)
        schlecht = a.split("Schlechte Frage", 1)[1]
        self.assertIn("Soll R330 jetzt gemessen werden", schlecht)
        # Die schlechte Frage hat KEINE Wirkung und KEINE Empfehlung.
        self.assertNotIn("Vorschlag:", schlecht.split("```")[0])

    def test_rolle_wird_als_systemdatei_ausgeliefert(self):
        cfg = load_config()
        cmd = reviewer.build_command(cfg, "sess", True)
        datei = Path(cmd[cmd.index("--append-system-prompt-file") + 1])
        self.assertIn("Fragen an den Nutzer",
                      datei.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
