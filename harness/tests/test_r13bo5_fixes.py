"""Tests fuer R13bo-5-2 (2026-10-03): Zielgroesse und Prognose fuer C auf Insn.

Auftrag (Harness-Wartung 2026-10-03, Punkt 2; Aussensicht M249-4):

  * Quelle ist die Preflight-Zeile `Ausgefuehrte Menge` - die **referenzgleiche Insn**
    je Batch, dazu `referenzgleich aber teilgeprueft` ("davon in teilgeprueften Koepfen").
  * Zielgroesse je C-Batch = **Median der eigenen Insn der letzten 4 C-Batches**
    (`stand.c_insn_rate`), nicht mehr "hoechstens ca. N Koepfe".
  * Prognose = **offene Rumpf-Insn** / dieser Median, mit der Spanne min/max der letzten
    4, als HYPOTHESIS.

Messreihe (gemessen am lebenden Repo, B251-B254): 510 / 191 / 461 / 176 -> Median 326.
Alles im Wegwerf-Verzeichnis `tests/_tmp_r13bo5*`; das lebende Repo wird nicht angefasst.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import stand                                             # noqa: E402
from hx.config import load_config                                # noqa: E402
from hx.util import Log, ensure_dir, write_text_atomic           # noqa: E402


def ausg(ref_insn, offen: int, spannen: int = 69355, teil: int = 24,
         zweit: int | None = None) -> str:
    """Eine Zeile `Ausgefuehrte Menge`. `ref_insn=None` laesst das Feld weg (dann wird
    die referenzgleiche Insn aus `Spannen-Insn - davon nicht referenzgleich` abgeleitet)."""
    teile = [f"Ausgefuehrte Menge 1081/2076 | 50636 Insn | Spannen-Insn {spannen}",
             f"davon nicht referenzgleich {offen}"]
    if ref_insn is not None:
        teile.append(f"referenzgleich Insn {ref_insn}")
    teile += ["referenzgleich 99", "nicht referenzgleich 982", "Rumpf offen 0",
              f"referenzgleich aber teilgeprueft {teil}"]
    if zweit is not None:
        teile.append(f"Zweitkopien {zweit}")
    teile.append("Quelle capture/ppc_coverage.bin Meldung")
    return " | ".join(teile)


# Die echte Reihe B250..B254 (ref_insn: B250 ohne Feld -> 69355-65052 = 4303).
REIHE_250_254 = (
    (250, None, 65052, "B"),          # Basis: ref = 4303
    (251, 4813, 64542, "C"),          # +510
    (252, 5004, 64351, "C"),          # +191
    (253, 5465, 63890, "C"),          # +461
    (254, 5641, 63714, "C"),          # +176
)


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = ensure_dir(Path(__file__).resolve().parent / "_tmp_r13bo5")
        shutil.rmtree(self.tmp, ignore_errors=True)
        ensure_dir(self.tmp)
        self.root = ensure_dir(self.tmp / "harness")
        self.decomp = ensure_dir(self.tmp / "decomp")
        self.ana = ensure_dir(self.decomp / "analysis")
        subprocess.run(["git", "init", "-q"], cwd=self.decomp, capture_output=True)
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.decomp)
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["paths"]["harness_home"] = str(self.tmp)
        cfg.data["paths"]["inbox"] = str(self.root / "inbox")
        cfg.data["telegram"]["allowlist_user_ids"] = []
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def preflight(self, batch: int, *zeilen: str) -> None:
        write_text_atomic(self.ana / f"_preflight_{batch}.txt",
                          "=== PREFLIGHT (before) ===\n" + "\n".join(zeilen) + "\n")

    def strang(self, batch: int, art: str) -> None:
        write_text_atomic(ensure_dir(self.root / "runs" / f"b{batch:03d}") / "auftrag.md",
                          f"TEIL 1: bauen.\nSTRANG: {art}\n")

    def reihe_aufbauen(self, reihe=REIHE_250_254, teil_254: int = 29,
                       zweit_254: int | None = None) -> None:
        for batch, ref, offen, art in reihe:
            self.strang(batch, art)
            teil = teil_254 if batch == 254 else 24
            zweit = zweit_254 if batch == 254 else None
            self.preflight(batch, ausg(ref, offen, teil=teil, zweit=zweit))


class TestReihe(Basis):
    def test_eigene_insn_der_reihe_251_bis_254(self):
        self.reihe_aufbauen()
        d = stand.c_insn_rate(self.cfg, 4)
        self.assertTrue(d["gemessen"], d["grund"])
        self.assertEqual([(e["batch"], e["insn"]) for e in d["c_reihe"]],
                         [(251, 510), (252, 191), (253, 461), (254, 176)])
        self.assertEqual(d["median"], 326.0)
        self.assertEqual((d["min"], d["max"]), (176, 510))

    def test_basis_ohne_feld_wird_abgeleitet(self):
        # B250 traegt das Feld `referenzgleich Insn` nicht (69355-65052 = 4303) - genau
        # daraus entsteht B251s eigene Zahl 510.
        self.reihe_aufbauen()
        reihe = stand.ausgefuehrte_menge(self.cfg, 8)
        b250 = [e for e in reihe if e["batch"] == 250][0]
        self.assertEqual(b250["ref_insn"], 4303)
        self.assertIn("abgeleitet", b250["ref_insn_quelle"])

    def test_prognose_ist_hypothesis_mit_spanne(self):
        self.reihe_aufbauen()
        d = stand.c_insn_rate(self.cfg, 4)
        self.assertEqual(d["offen_insn"], 63714)
        self.assertEqual(d["teilgeprueft"], 29)
        t = d["text"]
        self.assertIn("ZIEL des naechsten C-Batches: 326 Insn", t)
        self.assertIn("HYPOTHESIS:", t)
        self.assertIn("63714 offene Rumpf-Insn", t)
        self.assertIn("= ca. 195 C-Batches", t)          # 63714 / 326
        self.assertIn("Spanne ca. 125..362", t)          # 63714/510 .. 63714/176
        self.assertIn("davon in teilgeprueften Koepfen 29", t)

    def test_b_batch_zaehlt_nicht_zur_zielgroesse(self):
        reihe = tuple((b, r, o, "B" if b == 251 else a)
                      for b, r, o, a in REIHE_250_254)
        self.reihe_aufbauen(reihe)
        d = stand.c_insn_rate(self.cfg, 4)
        self.assertEqual([e["batch"] for e in d["c_reihe"]], [252, 253, 254])
        self.assertEqual(d["median"], 191.0)             # Median(191, 461, 176)

    def test_zweitkopien_werden_abgezogen(self):
        self.reihe_aufbauen(zweit_254=60)
        d = stand.c_insn_rate(self.cfg, 4)
        neu = [e for e in d["c_reihe"] if e["batch"] == 254][0]
        self.assertEqual(neu["insn"], 176 - 60)

    def test_ohne_zeile_nicht_gemessen(self):
        self.strang(254, "C")
        self.preflight(254, "C Koepfe           149 / 8456 / 0        OK")
        d = stand.c_insn_rate(self.cfg, 4)
        self.assertFalse(d["gemessen"])
        self.assertIn("nicht gemessen", d["text"])


if __name__ == "__main__":
    unittest.main()
