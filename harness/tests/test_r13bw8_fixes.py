"""Tests fuer R13bw-8 (2026-10-05, Punkt 3): "Probe-Artefakt (Schranke)" ist kein Stillstand.

**Auftrag (Nutzer):** "Alarm 'Hybrid-Lauf haengt': Wenn die Preflight-Probe (A4_SCHRITTE) an
der Schranke endet, den Alarm als 'Probe-Artefakt (Schranke)' kennzeichnen und nicht als
Stillstand zaehlen."

**Befund (nur gelesen, `docs/_r13bw8_hybrid_beleg.txt`).** Die Zeile `Hybrid-A4` traegt
`Halt-Art`: `Schranke` heisst, die Probe lief in ihre Schrittgrenze (gemessen B260-B267 und
B269-B273: `Schritte ... 900000000`, `Halt-Art Schranke`); nur B268 hatte einen echten Halt
(`Halt-Art Form`, 422421553 Schritte). Der Melder verglich trotzdem Halt-PC und Schritte -
und feuerte am 05.10.2026 mit drei Schranken-Eintraegen:

    Hybrid-Lauf haengt: Halt-PC 80008AB0 unveraendert und Schritte 900000000 -> 900000000
    steigt nicht (B271, B272, B273, ...)

Wegwerf-Verzeichnisse unter `tests/_tmp_r13bw8`.
"""

from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import aussensicht, stand                                 # noqa: E402
from hx.config import load_config                                 # noqa: E402
from hx.util import Log, ensure_dir, read_text, write_text_atomic  # noqa: E402

SCHRANKE = 900000000
# Der Wortlaut der echten Zeile (analysis/_preflight_268.txt), auf das Noetige gekuerzt.
A4 = ("Hybrid-A4          Schritte bis erster Eintritt echter Halt {weg} | "
      "Halt-PC {pc} | Selbstsprung-PC - | Halt-Art {art} | "
      "Hauptschleife 80008AA0 erreicht ja (erster Schritt 257116667) OK")


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13bw8"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "root")
        self.decomp = ensure_dir(self.tmp / "decomp")
        self.ana = ensure_dir(self.decomp / "analysis")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.decomp)
        cfg.data["paths"]["harness_home"] = str(self.tmp)
        cfg.data["paths"]["secrets"] = str(ensure_dir(self.tmp / "secrets"))
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---------------------------------------------------------------- Hilfen
    def preflight(self, batch: int, art: str, weg: int = SCHRANKE,
                  pc: str = "80008AB0") -> None:
        """Eine Preflight-Datei mit A4-Zeile; dazu den Batch als B-Batch belegen."""
        write_text_atomic(self.ana / f"_preflight_{batch}.txt",
                          "C Koepfe           151 / 8039 / 0     OK\n"
                          + A4.format(weg=weg, pc=pc, art=art) + "\n")
        write_text_atomic(ensure_dir(self.root / "runs" / f"b{batch:03d}") / "auftrag.md",
                          f"=== AUFTRAG ===\nStrang B (Hybrid-Laeufer), B-Batch {batch}.\n")


class TestSchrankenHalt(Basis):
    def test_ist_schranken_halt_liest_die_halt_art(self):
        self.assertTrue(aussensicht.ist_schranken_halt({"art": "Schranke"}))
        self.assertTrue(aussensicht.ist_schranken_halt({"art": "schranke"}),
                        "Schreibweise egal")
        self.assertFalse(aussensicht.ist_schranken_halt({"art": "Form"}))
        self.assertFalse(aussensicht.ist_schranken_halt({"art": ""}))
        self.assertFalse(aussensicht.ist_schranken_halt({}))

    def test_verlauf_traegt_die_halt_art(self):
        self.preflight(271, "Schranke")
        self.preflight(272, "Schranke")
        verlauf = stand.hybrid_a4_verlauf(self.cfg, 4)
        self.assertEqual([e["art"] for e in verlauf], ["Schranke", "Schranke"])
        self.assertEqual([e["weg"] for e in verlauf], [SCHRANKE, SCHRANKE])

    def test_drei_schranken_kein_alarm(self):
        """**Der Kern:** drei Laeufe, die an der Schranke enden -> kein Stillstand."""
        for b in (271, 272, 273):
            self.preflight(b, "Schranke")
        self.assertEqual(aussensicht.hybrid_stillstand(self.cfg), "",
                         "die Schranke ist kein Halt")

    def test_drei_echte_halte_ergeben_den_alarm(self):
        """Kontrolle: derselbe Aufbau mit echten Halten meldet weiter."""
        for b in (271, 272, 273):
            self.preflight(b, "Form", weg=422421553, pc="8005D534")
        text = aussensicht.hybrid_stillstand(self.cfg)
        self.assertIn("Hybrid-Lauf haengt", text)
        self.assertIn("Halt-PC 8005D534", text)
        self.assertIn("B271, B272, B273", text)

    def test_schranken_werden_als_probe_artefakt_genannt(self):
        """Eine Meldung aus echten Halten nennt die ausgelassenen Schranken."""
        self.preflight(270, "Form", weg=300, pc="8005D534")
        self.preflight(271, "Form", weg=300, pc="8005D534")
        self.preflight(272, "Form", weg=300, pc="8005D534")
        self.preflight(273, "Schranke")               # juenger, faellt raus
        text = aussensicht.hybrid_stillstand(self.cfg)
        self.assertIn("Hybrid-Lauf haengt", text)
        self.assertIn("B270, B271, B272", text)
        self.assertIn("Probe-Artefakt Schranke", text)
        self.assertIn("B273", text)

    def test_steigende_schritte_bleiben_fortschritt(self):
        """Auch aus echten Halten: steigende Schritte = Fortschritt, kein Alarm."""
        self.preflight(271, "Form", weg=100, pc="8005D534")
        self.preflight(272, "Form", weg=200, pc="8005D534")
        self.preflight(273, "Form", weg=300, pc="8005D534")
        self.assertEqual(aussensicht.hybrid_stillstand(self.cfg), "")


class TestDoku(unittest.TestCase):
    def test_docstring_nennt_das_probe_artefakt(self):
        text = read_text(ROOT / "hx" / "aussensicht.py")
        self.assertIn("Probe-Artefakt Schranke", text)
        self.assertIn("ist_schranken_halt", text)


if __name__ == "__main__":                       # pragma: no cover
    unittest.main()
