"""Tests fuer R13bw-7 (2026-10-05): Review-Zuordnung - `runs/b<N>/review.md` bewertet B<N-1>.

**Auftrag (Nutzer, 05.10.2026, Punkt 2):** "Review-Zuordnung: runs/b<N>/review.md bewertet
Batch N-1. Eingabezeile 'LETZTE REVIEW-ZUSAMMENFASSUNGEN' und Stichprobenregel (aussensicht)
entsprechend umstellen; Fundstellen nennen."

**Fundstellen (vor der Aenderung):**

* `hx/aussensicht.py summaries()` - lieferte `(reviewordner, summary)`; die Zahl wurde von
  den Meldern als **Batch** gelesen (einmal um eins zu hoch).
* `hx/aussensicht.py _marker()` - keyte Treffer mit dem Ordnernamen.
* `hx/aussensicht.py faellig()` - Grund lautete `"… - laut Review in runs/b<N>: …"`, also
  mit dem Ordnernamen als Batch.
* `hx/aussensicht.py eingaben()` - Eingabezeile lautete
  `"--- Zusammenfassung aus runs/b<N>/review.md ---"` (ohne den bewerteten Batch).
* `hx/aussensicht.py marker_beteiligt()` - las den Ordnernamen per Regex aus dem Grund.

**Die Quelle der Zuordnung** ist `orchestrator.do_review`: `evidence = state.batch` (der
bewertete Lauf), `target = expected_batch()` (die Freigabe), `rdir = runs/b<target>` - der
Review liegt also im Ordner des **danach** freigegebenen Batches.

Wegwerf-Verzeichnisse unter `tests/_tmp_r13bw7`.
"""

from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import aussensicht                                        # noqa: E402
from hx.config import load_config                                 # noqa: E402
from hx.util import Log, ensure_dir, read_text, write_text_atomic  # noqa: E402

PROMPT = ROOT / "prompts" / "aussensicht.md"
MARKER = "ABBRUCHKRITERIUM ERREICHT: M242-1 (Attrappe zu B240)"


class _State:
    """Minimaler Zustands-Ersatz: `faellig`/`eingaben` lesen `data`, `batch`, `gate`."""

    def __init__(self, data: dict):
        self.data = dict(data)
        self.gate = None
        self.saves = 0

    @property
    def batch(self):
        return self.data.get("batch")

    def save(self) -> None:
        self.saves += 1


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13bw7"
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

    def review(self, ordner: int, text: str) -> None:
        """Review im Ordner `runs/b<ordner>` - er bewertet Batch `ordner - 1`."""
        write_text_atomic(ensure_dir(self.root / "runs" / f"b{ordner:03d}") / "review.md",
                          "<TELEGRAM_SUMMARY>\n" + text + "\n</TELEGRAM_SUMMARY>\n")

    def state(self, batch: int) -> _State:
        return _State({"batch": batch, "last_batch_number": batch - 1, "meta": {}})


# ------------------------------------------------------------ 1) Die Zuordnung selbst
class TestZuordnung(Basis):
    def test_bewerteter_batch_ist_eins_niedriger(self):
        self.assertEqual(aussensicht.bewerteter_batch(241), 240)
        self.assertEqual(aussensicht.bewerteter_batch(1), 0)
        self.assertEqual(aussensicht.bewerteter_batch(0), 0, "nie negativ")

    def test_summaries_traegt_bewerteten_batch_und_ordner(self):
        self.review(241, MARKER)
        out = aussensicht.summaries(self.cfg, 1)
        self.assertEqual(len(out), 1)
        bewertet, ordner, summary = out[0]
        self.assertEqual((bewertet, ordner), (240, 241))
        self.assertIn("M242-1", summary)

    def test_stichprobe_bleibt_dieselbe_reihe(self):
        """Die AUSWAHL aendert sich nicht - nur die Nummer, die sie traegt."""
        for b in (239, 240, 241, 242):
            self.review(b, f"Marke {b}")
        ordner = [o for _b, o, _s in aussensicht.summaries(self.cfg, 2)]
        self.assertEqual(ordner, [241, 242], "die letzten zwei Review-Dateien")


# ------------------------------------------------------------ 2) Grund und Eingabezeile
class TestTexte(Basis):
    def test_grund_nennt_batch_und_datei(self):
        self.review(241, MARKER)
        gruende = aussensicht.faellig(self.cfg, self.state(240), self.log)
        treffer = [g for g in gruende if "Abbruchkriterium" in g]
        self.assertTrue(treffer, gruende)
        self.assertIn("laut Review zu B240", treffer[0])
        self.assertIn("Datei runs/b241", treffer[0])
        self.assertNotIn("laut Review in runs/b241", treffer[0],
                         "der alte Wortlaut las den Ordner als Batch")

    def test_marke_zaehlt_den_bewerteten_batch(self):
        self.review(241, MARKER)
        s = self.state(240)
        gruende = aussensicht.faellig(self.cfg, s, self.log)
        aussensicht.marker_marke_setzen(self.cfg, s, gruende)
        self.assertEqual(s.data["meta"]["marker_gemeldet_bis"],
                         {"Abbruchkriterium erreicht": 240})

    def test_eingabezeile_nennt_batch_und_datei(self):
        self.review(241, "Zusammenfassung zu B240 mit Marker")
        text = aussensicht.eingaben(self.cfg, self.state(240))
        self.assertIn("=== LETZTE REVIEW-ZUSAMMENFASSUNGEN (TELEGRAM_SUMMARY) ===", text)
        self.assertIn("--- Review zu B240 (Datei runs/b241/review.md) ---", text)
        self.assertNotIn("Zusammenfassung aus runs/b241/review.md", text)

    def test_kopfzeile_erklaert_die_zuordnung(self):
        self.review(241, "Zusammenfassung zu B240")
        text = aussensicht.eingaben(self.cfg, self.state(240))
        self.assertIn("Jede Zusammenfassung bewertet den GENANNTEN Batch", text)


# ------------------------------------------------------------ 3) Doku
class TestDokuUndPrompt(unittest.TestCase):
    def test_aussensicht_prompt_erklaert_die_zuordnung(self):
        text = read_text(PROMPT)
        self.assertIn("runs/b<N>/review.md` **bewertet Batch", text)
        self.assertIn("--- Review zu B<N-1> (Datei runs/b<N>/review.md) ---", text)


if __name__ == "__main__":                       # pragma: no cover
    unittest.main()
