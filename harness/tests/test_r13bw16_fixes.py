"""Tests R13bw-16 (2026-10-07): die Regel "Rohzeilenprobe" im Worker-Vorspann.

**Auftrag (Nutzer, Harness-Wartung).** Die Regel aus dem Decomp-Repo
(`AGENTS.md`, Abschnitt `## Rohzeilenprobe`, Zeilen 96-121, Commit `edf12a0`) kommt in
`hx/worker.py::WORKER_PREAMBLE` - neben die Regel "ROM-Adressen suchen", **gekuerzt** auf
4-5 Zeilen:

  * drei zufaellige Ausgabeeintraege gegen die Rohzeilen legen, **Saat nennen**,
    `Datei:Zeile` ins Batch-Dokument,
  * `WEGGELASSEN:` / `NICHT ZULAESSIG:` im Werkzeugkopf.

Warum der Vorspann: die Schwesterregel "ROM-ADDRESSEN SUCHEN" steht dort ebenfalls
(`hx/worker.py`, Block direkt darueber) - nur so erreicht die Projektregel den Worker im
laufenden Batch. Beide Repos koennen still auseinanderlaufen; der letzte Test prueft
deshalb die Substanz gegen die echte `AGENTS.md` (mit `skipTest`, wenn das Decomp-Repo
fehlt).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import worker                                             # noqa: E402
from hx.config import load_config                                 # noqa: E402

ULEITZEILE = "ROHZEILENPROBE (B291, 2026-10-07)"


def _block() -> list[str]:
    """Die Zeilen des neuen Blocks im Vorspann (Ueberschrift bis zur Leerzeile)."""
    zs = worker.WORKER_PREAMBLE.splitlines()
    start = next(i for i, z in enumerate(zs) if z.startswith("ROHZEILENPROBE"))
    ende = start + 1
    while ende < len(zs) and zs[ende].strip():
        ende += 1
    return zs[start:ende]


class TestVorspannRegel(unittest.TestCase):
    def test_block_steht_neben_der_rom_regel(self):
        pre = worker.WORKER_PREAMBLE
        self.assertIn(ULEITZEILE, pre)
        self.assertLess(pre.index("ROM-ADRESSEN SUCHEN"), pre.index(ULEITZEILE))
        # und noch VOR dem Ablauf-Teil (die Regeln stehen beieinander)
        self.assertLess(pre.index(ULEITZEILE), pre.index("\nABLAUF\n"))

    def test_drei_eintraege_gegen_rohzeilen_mit_saat_und_beleg(self):
        pre = worker.WORKER_PREAMBLE
        self.assertIn("drei **zufaellige Ausgabeeintraege**", pre)
        self.assertIn("Zufallssaat", pre)
        self.assertIn("`Datei:Zeile`", pre)
        self.assertIn("Batch-Dokument", pre)
        self.assertIn("Zeilennummer", pre)
        self.assertIn("Schritt und pc", pre)

    def test_marken_im_werkzeugkopf(self):
        pre = worker.WORKER_PREAMBLE
        self.assertIn("`WEGGELASSEN:`", pre)
        self.assertIn("`NICHT ZULAESSIG:`", pre)
        self.assertIn("Dateikopf", pre)

    def test_betroffene_werkzeuge_sind_genannt(self):
        pre = worker.WORKER_PREAMBLE
        self.assertIn("`scripts/`", pre)
        self.assertIn("hybrid_lauf.cpp", pre)

    def test_gekuerzt_und_nicht_kopiert(self):
        """Der Auftrag verlangt 4-5 Zeilen - kein zweiter Volltext im Vorspann."""
        block = _block()
        self.assertLessEqual(len(block), 14,
                             f"Block zu lang ({len(block)} Zeilen): {block}")
        self.assertLessEqual(sum(1 for z in block if z.startswith("- ")), 4,
                             "hoechstens vier Aufzaehlungspunkte")

    def test_regel_steht_auch_in_agents_md(self):
        """Dieselbe Regel im Decomp-Repo - sonst laufen die beiden Staende auseinander."""
        agents = Path(load_config().decomp) / "AGENTS.md"
        if not agents.is_file():
            self.skipTest(f"Decomp-Repo nicht vorhanden ({agents})")
        text = agents.read_text(encoding="utf-8", errors="replace")
        self.assertIn("## Rohzeilenprobe", text)
        for wort in ("WEGGELASSEN:", "NICHT ZULAESSIG:", "Zufallssaat",
                     "Datei:Zeile", "Schritt und pc", "zufaellig"):
            self.assertIn(wort, text)


if __name__ == "__main__":
    unittest.main()
