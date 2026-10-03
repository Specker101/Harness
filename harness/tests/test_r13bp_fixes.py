"""R13bp Punkt 1 (2026-10-03, Nutzerauftrag): Strangerkennung.

Die Klassifikation eines Batches (B- oder C-Strang) las die Pflichtzeile `B-SCHRITT:`
des **Folge**-Reviews: das Review von Batch N liegt im Ordner `runs/b<N+1>` (R13x) und
traegt dort die Zusammenfassung des Batches, der N bewertet - gemessen beschrieb sie in
`runs/b255/review.md` den NAECHSTEN B-Batch ("B-SCHRITT: 4/5 Boot bis Hauptschleife,
B-Batch 26"), waehrend B254 ein C-Batch war. B254 galt dadurch als B-Batch.

Jetzt ist die **Pflichtzeile `STRANG: B|C` im Auftrag des Batches selbst**
(`runs/b<N>/auftrag.md`) die erste Quelle, danach der uebrige Auftragstext; die
`B-SCHRITT`-Zeile ist nur noch **Rueckfall** (`stand.strang_von_batch`).

Der Test mit den echten Werten laeuft gegen den **eingefrorenen Stand**
`tests/fixtures/stand_b255` (Kopien der Dateien, die am 2026-10-03 im Harness lagen) -
nicht gegen die lebenden `runs/`, die der laufende Harness fortschreibt.

Alles im Attrappenbetrieb: kein Netz, keine API-Kosten, kein Ghidra.
"""

from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import stand                                             # noqa: E402
from hx.config import load_config                                # noqa: E402
from hx.util import ensure_dir, write_text_atomic                # noqa: E402

# R13bp: der feste Stand (03.10.2026, B249..B256) - eingefroren, nicht nachziehen.
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "stand_b255"
# Die erwartete Reihe dieses Stands (Fenster der Fixture: B249..B255): B251-B254 waren
# C-Batches (der Auftrag von B256 sagt es ausdruecklich), B249/B250 und B255 sind
# B-Batches. Die `quelle` steht in den Einzeltests dabei, damit ein Test nicht nur den
# Wert, sondern auch den BELEG prueft.
REIHE_B255 = {249: "B", 250: "B", 251: "C", 252: "C", 253: "C", 254: "C",
              255: "B"}


class Basis(unittest.TestCase):
    """Wegwerf-Harness mit Wegwerf-Decomp-Repo (wie test_r13ba)."""

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13bp"
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

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --------------------------------------------------------------- Attrappen
    def auftrag(self, batch: int, text: str) -> None:
        write_text_atomic(ensure_dir(self.root / "runs" / f"b{batch:03d}") / "auftrag.md",
                          text)

    def review(self, batch: int, text: str) -> None:
        """`text` ist die Zusammenfassung des Reviews, das `batch` BEWERTET hat.

        Die Ordner-Konvention (R13x): dieses Review liegt in `runs/b<batch+1>`.
        """
        write_text_atomic(ensure_dir(self.root / "runs" / f"b{batch + 1:03d}") / "review.md",
                          text)


class StandFixtureMixin:
    """Den eingefrorenen Stand in das Wegwerf-Verzeichnis der Basis kopieren."""

    def stand_laden(self) -> None:
        shutil.copytree(FIXTURE / "root", self.root, dirs_exist_ok=True)
        shutil.copytree(FIXTURE / "decomp", self.decomp, dirs_exist_ok=True)
        self.ana = self.decomp / "analysis"


class TestEchterStandB255(Basis, StandFixtureMixin):
    """Der feste Stand: B254 (C) und B255 (B) - die zwei gemeldeten Faelle."""

    def setUp(self):
        super().setUp()
        self.stand_laden()

    def test_b254_ist_c_und_der_auftrag_belegt_es(self):
        d = stand.strang_von_batch(self.cfg, 254)
        self.assertEqual(d["strang"], "C", d)
        self.assertIn("runs/b254/auftrag.md", d["quelle"])
        self.assertFalse(stand.ist_b_batch(self.cfg, 254))

    def test_b255_ist_b_und_der_auftrag_belegt_es(self):
        d = stand.strang_von_batch(self.cfg, 255)
        self.assertEqual(d["strang"], "B", d)
        self.assertIn("runs/b255/auftrag.md", d["quelle"])
        self.assertTrue(stand.ist_b_batch(self.cfg, 255))

    def test_die_reihe_stimmt(self):
        """B251-B254 C, B249/B250 und B255 B (so nennt es der Auftrag von B256 selbst)."""
        for batch, erwartet in REIHE_B255.items():
            d = stand.strang_von_batch(self.cfg, batch)
            self.assertEqual(d["strang"], erwartet, f"B{batch}: {d}")

    def test_der_auftrag_von_b256_traegt_die_pflichtzeile(self):
        """Quelle 0 - die neue Pflichtzeile `STRANG: B|C` im Auftrag des Batches selbst."""
        d = stand.strang_von_batch(self.cfg, 256)
        self.assertEqual(d["strang"], "B", d)
        self.assertIn("STRANG/SOLL-KOEPFE", d["quelle"])

    def test_die_alte_quelle_haette_b254_zu_b_gemacht(self):
        """Der Beweis, dass die Reihenfolge die Ursache war (nicht ein Zufallstreffer).

        Das Review von B254 liegt in `runs/b255/review.md` und traegt dort die
        `B-SCHRITT`-Zeile des NAECHSTEN B-Batches. Genau diese Zeile steht weiter im Code -
        als Rueckfall, nicht als Primaerquelle.
        """
        review = stand.review_zu_batch(self.cfg, 254)
        self.assertIn("B-SCHRITT: 4/5", review, "die irrefuehrende Zeile steht im Review")
        self.assertTrue(stand._RE_B_SCHRITT.search(review))
        self.assertEqual(stand.strang_von_batch(self.cfg, 254)["strang"], "C")
        self.assertNotIn("B-SCHRITT", stand.strang_von_batch(self.cfg, 254)["quelle"])

    def test_die_b_schritt_zeile_bleibt_erreichbar(self):
        """Rueckfall heisst nicht weg: ohne Auftrag und ohne Pflichtzeile entscheidet sie."""
        # B257 hat weder Auftrag noch Review - die Quelle ist leer (nichts wird geraten).
        self.assertEqual(stand.strang_von_batch(self.cfg, 257)["strang"], "")

    def test_der_reviewer_prompt_verlangt_die_pflichtzeile(self):
        """Die Primaerquelle entsteht nur, wenn der Reviewer sie schreiben MUSS (R13bp)."""
        text = (ROOT / "prompts" / "reviewer.md").read_text(encoding="utf-8")
        self.assertIn("`STRANG: B` bzw. `STRANG: C`", text)
        self.assertIn("<DS_INSTRUCTION>", text)


class TestReihenfolge(Basis):
    """Die Reihenfolge der Quellen - je Fall eine Attrappe, ohne Fixture."""

    def test_auftrag_schlaegt_die_b_schritt_zeile(self):
        self.auftrag(254, "=== AUFTRAG ===\nStrang C (Handport). Messziel: Insn.\n")
        self.review(254, "<TELEGRAM_SUMMARY>\nB-SCHRITT: 4/5 Kern, B-Batch 26\n"
                         "</TELEGRAM_SUMMARY>\n")
        d = stand.strang_von_batch(self.cfg, 254)
        self.assertEqual(d["strang"], "C", d)
        self.assertIn("Auftrag des Batches", d["quelle"])

    def test_pflichtzeile_bleibt_erste_quelle(self):
        self.auftrag(255, "=== AUFTRAG ===\nStrang C. Messziel: x.\nSTRANG: B\n")
        self.review(255, "<TELEGRAM_SUMMARY>\nB-SCHRITT: kein B-Batch (Strang C)\n"
                         "</TELEGRAM_SUMMARY>\n")
        d = stand.strang_von_batch(self.cfg, 255)
        self.assertEqual(d["strang"], "B", d)
        self.assertIn("STRANG/SOLL-KOEPFE", d["quelle"])

    def test_ohne_auftrag_entscheidet_die_b_schritt_zeile(self):
        self.review(254, "<TELEGRAM_SUMMARY>\nB-SCHRITT: kein B-Batch (Strang C)\n"
                         "</TELEGRAM_SUMMARY>\n")
        self.assertEqual(stand.strang_von_batch(self.cfg, 254)["strang"], "C")
        self.review(255, "<TELEGRAM_SUMMARY>\nB-SCHRITT: 4/5 Kern, B-Batch 26\n"
                         "</TELEGRAM_SUMMARY>\n")
        d = stand.strang_von_batch(self.cfg, 255)
        self.assertEqual(d["strang"], "B", d)
        self.assertIn("B-SCHRITT", d["quelle"])

    def test_der_plan_bleibt_die_letzte_quelle(self):
        write_text_atomic(self.ana / "hybrid-plan.md",
                          "# Plan\n\n**Mischverhaeltnis 2 B : 1 C (ENTSCHEIDUNG "
                          "Reviewer):** B210 B, B211 B, B212 C\n")
        d = stand.strang_von_batch(self.cfg, 212)
        self.assertEqual(d["strang"], "C", d)
        self.assertIn("hybrid-plan", d["quelle"])

    def test_fremder_batch_macht_weiter_keinen_b_batch(self):
        """Der eigene Auftrag darf FREMDE Batches nennen, ohne selbst B zu werden."""
        self.auftrag(209, "Der naechste Batch B210 ist ein C-Batch; B211 wird wieder B.\n")
        self.assertEqual(stand.strang_von_batch(self.cfg, 209)["strang"], "")


if __name__ == "__main__":
    unittest.main()
