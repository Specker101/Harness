"""Tests fuer R13t (2026-09-28): /ds-Nachrichten im Review + Port-Relevanz + C-Hochrechnung.

Auftrag (Nutzer):
  2. Punkt 4b vollstaendig: "ausgefuehrt vs. gebaut vs. verifiziert" mit Rumpf-Fenstern,
     dazu die Anzahl Paket-E-Koepfe in der ausgefuehrten Menge - als **feste Zeile** in
     `/bilanz`: "Port-Relevanz: ausgefuehrt X | davon gebaut Y | davon verifiziert Z".
  3. `/bilanz`: die HYPOTHESIS-Hochrechnung GETRENNT ausweisen - "Paket E: ca. N Batches"
     UND "C gesamt: offen K Koepfe / I Insn -> ca. M Batches".
  5. R13t: die `/ds`-Nachrichten dieses Batches in den Review-Prompt.

Alles im Attrappenbetrieb: kein Netz, keine API-Kosten, kein Ghidra.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import reviewer, stand                                        # noqa: E402
from hx.config import load_config                                     # noqa: E402
from hx.util import ensure_dir, write_json_atomic, write_text_atomic  # noqa: E402

AUFTRAG = """# Prompt

=== AUFTRAG (vom Reviewer) ===
Batch 206 - Silent Scope Decomp
TEIL 3 - Bauen: `8005BF74` (51).

NACHRICHTEN AUS DER QUEUE (vom Nutzer, nicht verhandelbar):
- [2026-09-28T00:28:42+00:00 | lokal] R535 IST WIDERLEGT (FEHLALARM) - nicht bauen.
"""

DOKU = """# Batch {n}

**1. Inventar (GEMESSEN).** 2072 Koepfe / 123771 Insn im Programm-Inventar,
davon **{bau} Koepfe / 28858 Insn**
in der
Bau-Liste. **OFFEN: {off} Koepfe /
{offi} Insn.** Davon haben **664 Koepfe / 31690 Insn** keinen offenen Ruf.

| Bilanzzeile | Vorbatch (B{n1}) | **Soll B{n}** | Zaehlerdefinition |
|---|---|---|---|
| **C Koepfe** | 73 / 1752 / 0 | **78 / 1872 / 0** | `c_kopf.py vergl alle` |
| Paket E offen | 43 Koepfe / 3025 Insn (Bl 20 / 1434) | **38 / 2674 (Bl 15 / 1083)** | `c_kopf.py paket_e` |
"""

BILANZ = """# Bilanz B{n}

| Bilanzzeile | Vorbatch (B{vm}) | Heute (B{n}) | Werkzeug |
|---|---|---|---|
| **R207 rueckwaerts** | **{v}** (a 30/b 0/c 0) | **{h}** (a 30/b 0/c 0) | `preflight.py` |
"""


def _weg(p: Path) -> None:
    if not p.exists():
        return
    for k in sorted(p.rglob("*"), reverse=True):
        k.unlink() if k.is_file() else k.rmdir()
    p.rmdir()


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__file__).resolve().parent / "_tmp_r13t"
        _weg(self.tmp)
        self.root = ensure_dir(self.tmp / "harness")
        self.decomp = ensure_dir(self.tmp / "decomp")
        self.ana = ensure_dir(self.decomp / "analysis")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.decomp)
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["paths"].pop("harness_home", None)   # Elternordner von root = self.tmp
        self.cfg = cfg

    def tearDown(self):
        _weg(self.tmp)

    def lauf(self, n: int, auftrag: str = "# Prompt\n") -> None:
        d = ensure_dir(self.root / "runs" / f"b{n}")
        write_text_atomic(d / "auftrag.md", auftrag)

    def bilanzdatei(self, n: int, v: int, h: int) -> None:
        d = ensure_dir(self.ana / f"_m{n}")
        write_text_atomic(d / f"_bilanz{n}.txt", BILANZ.format(n=n, vm=n - 1, v=v, h=h))

    def dokument(self, n: int, bau: int = 591, off: int = 1481, offi: int = 94913) -> None:
        write_text_atomic(self.ana / f"port-batch{n}-beispiel-2026-09-28.md",
                          DOKU.format(n=n, n1=n - 1, bau=bau, off=off, offi=offi))

    def preflight(self, n: int, ck: int, cf: int = 1872) -> None:
        """Die gemessene Zeile `C Koepfe` der Preflight-Datei (R13ac: C-Quelle)."""
        write_text_atomic(self.ana / f"_preflight_{n}.txt",
                          "=== PREFLIGHT (before) ===\n"
                          "Pruefung           Ergebnis                Urteil\n"
                          f"C Koepfe           {ck} / {cf} / 0          OK\n"
                          "=> BEFORE SAUBER\n")

    def relevanz(self, **werte) -> None:
        d = {"erzeuger": "tools/r13t_cov_relevanz.py", "fenster": "Rumpf",
             "ausgefuehrt": 1086, "gebaut": 686, "gebaut_ausgefuehrt": 416,
             "verifiziert": 78, "verifiziert_ausgefuehrt": 56,
             "paket_e_wurzeln": 86, "paket_e_wurzeln_ausgefuehrt": 66,
             "paket_e_blaetter": 17, "paket_e_blaetter_ausgefuehrt": 12}
        d.update(werte)
        write_json_atomic(ensure_dir(self.tmp / "docs") / "_port_relevanz.json", d)


# ------------------------------------------------------- /ds im Review (R13t)
class TestDsImReview(Basis):
    def test_liest_ds_block_aus_dem_auftrag(self):
        self.lauf(206, AUFTRAG)
        text = stand.ds_nachrichten(self.cfg, 206)
        self.assertTrue(text.startswith("NACHRICHTEN AUS DER QUEUE"))
        self.assertIn("R535 IST WIDERLEGT", text)
        self.assertNotIn("=== AUFTRAG", text)

    def test_auftrag_ohne_block_ist_leer(self):
        self.lauf(206, "# Prompt\n\n=== AUFTRAG (vom Reviewer) ===\nBatch 206\n")
        self.assertEqual(stand.ds_nachrichten(self.cfg, 206), "")

    def test_fehlender_auftrag_ist_leer(self):
        self.assertEqual(stand.ds_nachrichten(self.cfg, 999), "")
        self.assertEqual(stand.ds_nachrichten(self.cfg, 0), "")

    def test_prompt_hat_den_block(self):
        ctx = {"batch": 206, "ds_queue": stand.ds_nachrichten(self.cfg, 0)}
        prompt = reviewer.build_prompt(self.cfg, "batch_end", ctx)
        self.assertIn("=== NUTZER-NACHRICHTEN AN DEN WORKER DIESES BATCHES (/ds) ===",
                      prompt)
        self.assertIn("(keine)", prompt)

    def test_prompt_zeigt_die_nachricht(self):
        self.lauf(206, AUFTRAG)
        ctx = {"batch": 206, "ds_queue": stand.ds_nachrichten(self.cfg, 206)}
        prompt = reviewer.build_prompt(self.cfg, "batch_end", ctx)
        self.assertIn("NACHRICHTEN AUS DER QUEUE", prompt)
        self.assertIn("R535 IST WIDERLEGT", prompt)
        self.assertIn("Diese Nachrichten sind fuer den Worker", prompt)


# ------------------------------------------------------- Port-Relevanz (R13t)
class TestPortRelevanz(Basis):
    def test_ohne_messung_kein_raten(self):
        self.assertIsNone(stand.port_relevanz(self.cfg))
        self.bilanzdatei(206, 681, 686)
        self.dokument(206)
        zeilen = "\n".join(stand.durchsatz_zeilen(self.cfg))
        self.assertIn("Port-Relevanz: nicht gemessen", zeilen)
        self.assertIn("r13t_cov_relevanz.py", zeilen)

    def test_feste_zeile(self):
        self.relevanz()
        self.bilanzdatei(206, 681, 686)
        self.dokument(206)
        zeilen = "\n".join(stand.durchsatz_zeilen(self.cfg))
        self.assertIn("ausgefuehrt 1086 | davon gebaut 416 | davon verifiziert 56 "
                      "von 1086", zeilen)
        self.assertIn("Paket-E-Wurzeln 66/86 ausgefuehrt, offene Blaetter 12/17", zeilen)


# --------------------------------------------- getrennte HYPOTHESIS (R13t, 3)
class TestHochrechnungGetrennt(Basis):
    def setUp(self):
        super().setUp()
        self.bilanzdatei(206, 681, 686)
        self.dokument(206)
        # R13ac: die C-Hochrechnung steht auf der gemessenen Preflight-Reihe.
        self.preflight(205, 73)
        self.preflight(206, 78)

    def test_zwei_getrennte_zeilen(self):
        zeilen = "\n".join(stand.durchsatz_zeilen(self.cfg))
        self.assertIn("HYPOTHESIS (Paket E, Arbeitsvorrat)", zeilen)
        self.assertIn("HYPOTHESIS (C gesamt, ABGELEITET)", zeilen)
        # die alte, zusammengefasste Zeile darf es nicht mehr geben
        self.assertNotIn("HYPOTHESIS: noch", zeilen)

    def test_c_gesamt_wird_abgeleitet_und_belegt(self):
        d = stand.durchsatz(self.cfg)
        self.assertEqual(d["letzter"]["r207"], 686)
        g = stand.c_offen_gesamt(self.cfg)
        self.assertEqual((g["koepfe"], g["insn"], g["bau"]), (1481, 94913, 591))
        # 1481 - (686 - 591) = 1386 offene Koepfe
        zeilen = "\n".join(stand.durchsatz_zeilen(self.cfg))
        self.assertIn("offen 1386 Koepfe", zeilen)
        self.assertIn("minus R207-Delta 686 - 591 = 95 Koepfe", zeilen)
        self.assertIn("kein Insn-Beleg je Batch", zeilen)

    def test_ohne_offen_dokument_keine_zweite_zeile(self):
        (self.ana / "port-batch206-beispiel-2026-09-28.md").unlink()
        self.assertFalse(stand.c_offen_gesamt(self.cfg))
        zeilen = "\n".join(stand.durchsatz_zeilen(self.cfg))
        # R13t2: statt einer weggelassenen Zeile steht jetzt die ehrliche Meldung
        self.assertIn("HYPOTHESIS (C gesamt): nicht ermittelbar", zeilen)
        self.assertNotIn("ABGELEITET", zeilen)


if __name__ == "__main__":
    unittest.main()
