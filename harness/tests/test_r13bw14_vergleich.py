"""Tests fuer R13bw-14: das Schatten-Vergleichswerkzeug (`tools/schatten_vergleich.py`).

**Auftrag (Nutzer, Harness-Wartung 07.10.2026):** „Danach ein Diff-Skript: pro Batch
Befunde (gefunden, verpasst, zusaetzlich nach Kennung und Gewicht) und Verdikte
(PRUEFUNG-Status je Kennung, gleich/anders) gegen `runs/b285/meta.md` und
`runs/b289/meta.md`; dazu die Zahl der Werkzeugrunden, die Laufzeit und die
rate_limit-Differenz. Tests fuer das Diff-Skript (Kennungs-Parser auf den beiden
vorhandenen meta.md).“

Geprueft wird hier nur das **Lesen und Vergleichen** - kein Modellaufruf, keine
API-Kosten. Die beiden echten `meta.md` sind die Vorlage; fehlen sie, wird uebersprungen
(wie in den uebrigen Anlass-Tests).

**Befund-Format (gemessen an den echten Dateien):** `<BEFUND n="1" gewicht="hoch"
empfaenger="Nutzer">` - Befunde haben **keine** Kennung, Kennungen gibt es nur fuer die
**Verdikte** (`<PRUEFUNG id="M242-3" status="offen"/>`). Der Schluessel eines Befunds ist
deshalb seine **erste Beleg-Referenz**.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from hx import aussensicht                                    # noqa: E402
from hx.config import load_config                             # noqa: E402
from hx.util import read_text                                 # noqa: E402
import schatten_vergleich as SV                               # noqa: E402

# GEMESSEN an den echten Dateien (07.10.2026): B285 6 Befunde (hoch 2 / mittel 3 /
# niedrig 1), B289 5 Befunde, je 10 Verdikte.
ECHT = {
    285: {"befunde": 6, "hoch": 2, "mittel": 3, "niedrig": 1, "runden": "37",
          "dauer": "379s", "modell": "claude-opus-5-5", "verdikte": 10,
          "erste_id": "M242-3"},
    289: {"befunde": 5, "runden": "51", "dauer": "393s", "modell": "claude-opus-5-5",
          "verdikte": 10, "erste_id": "M242-3"},
}


def meta_text(batch: int) -> str:
    cfg = load_config()
    return read_text(aussensicht.pfad_neu(cfg, batch, "md")) or ""


class TestParser(unittest.TestCase):
    """Der Parser auf den BEIDEN vorhandenen meta.md (Auftrag)."""

    def test_befunde_und_gewichte(self):
        for batch, erwartet in ECHT.items():
            text = meta_text(batch)
            if not text:
                self.skipTest(f"runs/b{batch:03d}/meta.md fehlt")
            kopf, befunde = SV.befunde(text)
            self.assertEqual(len(befunde), erwartet["befunde"], f"B{batch}")
            for gew, zahl in (("hoch", erwartet.get("hoch")), ("mittel", erwartet.get("mittel")),
                              ("niedrig", erwartet.get("niedrig"))):
                if zahl is None:
                    continue
                self.assertEqual(sum(1 for b in befunde if b["gewicht"] == gew), zahl,
                                 f"B{batch} Gewicht {gew}")
            for b in befunde:
                self.assertTrue(b["schluessel"], f"B{batch}: Befund ohne Schluessel")

    def test_kopf_traegt_laufzeit_runden_und_modell(self):
        for batch, erwartet in ECHT.items():
            text = meta_text(batch)
            if not text:
                self.skipTest(f"runs/b{batch:03d}/meta.md fehlt")
            kopf, _ = SV.befunde(text)
            lf = kopf["lauf_felder"]
            self.assertEqual(lf.get("dauer"), erwartet["dauer"], f"B{batch}")
            self.assertEqual(lf.get("runden"), erwartet["runden"], f"B{batch}")
            self.assertEqual(lf.get("modell"), erwartet["modell"], f"B{batch}")

    def test_verdikte_je_kennung(self):
        for batch, erwartet in ECHT.items():
            text = meta_text(batch)
            if not text:
                self.skipTest(f"runs/b{batch:03d}/meta.md fehlt")
            liste = SV._verdikt_liste(text)
            self.assertEqual(len(liste), erwartet["verdikte"], f"B{batch}")
            self.assertEqual(liste[0][0], erwartet["erste_id"], f"B{batch}")
            for kid, status in liste:
                self.assertRegex(kid, r"^M\d+-\d+[a-z]?$")
                self.assertIn(status, ("offen", "erledigt", "verworfen", "zur kenntnis"))

    def test_schluessel_normalisiert_den_belegordner(self):
        b = {"beleg": "`analysis/_m283/_x.txt:12` gegen `runs/b282/review.md:61`"}
        self.assertEqual(SV.schluessel(b), "_m283/_x.txt:12")
        self.assertEqual(SV.schluessel({"beleg": "runs/b209/result.json: 3 Zeilen"}),
                         "runs/b209/result.json:3")
        self.assertEqual(SV.schluessel({"beleg": "Eingabe Kosten und Laufzeiten je Batch"}),
                         "ohne-referenz: Eingabe Kosten und Laufzeiten je Batch")
        self.assertEqual(SV.schluessel({}), "ohne-beleg")


class TestVergleich(unittest.TestCase):
    """Der Vergleich selbst - mit den echten Dateien gegen sich selbst."""

    def test_selbstvergleich_ist_vollstaendig_gleich(self):
        for batch in ECHT:
            text = meta_text(batch)
            if not text:
                self.skipTest(f"runs/b{batch:03d}/meta.md fehlt")
            v = SV.vergleiche(text, text)
            self.assertEqual(len(v["gefunden"]), len(v["befunde_echt"]), f"B{batch}")
            self.assertEqual(v["verpasst"], [], f"B{batch}")
            self.assertEqual(v["zusaetzlich"], [], f"B{batch}")
            self.assertEqual(v["verdikte_anders"], [], f"B{batch}")
            self.assertEqual(len(v["verdikte_gleich"]), ECHT[batch]["verdikte"], f"B{batch}")

    def test_verpasst_zusaetzlich_und_anders_werden_erkannt(self):
        """Ein veraenderter Schattenbericht muss alle drei Klassen ausloesen."""
        text = meta_text(285)
        if not text:
            self.skipTest("runs/b285/meta.md fehlt")
        # (a) einen Befund-Block entfernen, (b) einen neuen anhaengen,
        # (c) einen Verdikt-Status kippen.
        anfang = text.find("<BEFUND")
        ende = text.find("</BEFUND>", anfang) + len("</BEFUND>")
        ohne = text[:anfang] + text[ende:]
        neu = ('<BEFUND n="99" gewicht="niedrig" empfaenger="Reviewer">\n'
               "Beleg: `docs/_sonnet_vergleich_b285.md:1`\n"
               "Aussage: reine Probe fuer den Vergleich.\n"
               "Empfehlung: keine.\n</BEFUND>\n")
        gekippt = text.replace('id="M254-1" status="offen"', 'id="M254-1" status="erledigt"')
        # echt = der volle Bericht mit gekipptem Verdikt, Schatten = ohne den einen
        # Befund, aber mit dem neuen: so ist der entfernte "verpasst", der neue
        # "zusaetzlich" und ein Verdikt "anders".
        v = SV.vergleiche(gekippt, ohne + neu)
        self.assertEqual(len(v["verpasst"]), 1, "der entfernte Befund fehlt im Schatten")
        self.assertEqual(len(v["zusaetzlich"]), 1, "der neue Befund steht nur im Schatten")
        self.assertEqual(len(v["verdikte_gleich"]), ECHT[285]["verdikte"] - 1)
        self.assertEqual(v["verdikte_anders"], [("M254-1", "erledigt", "offen")])

    def test_tafel_zeigt_die_auftragszeilen(self):
        text = meta_text(289)
        if not text:
            self.skipTest("runs/b289/meta.md fehlt")
        aus = SV.tafel(SV.vergleiche(text, text), 289)
        self.assertIn("B289", aus)
        self.assertIn("gegen claude-opus-5-5", aus)
        self.assertIn("runden=51", aus)
        self.assertIn("dauer=393s", aus)
        self.assertIn("Verdikte: 10 gleich, 0 anders", aus)


if __name__ == "__main__":
    unittest.main()
