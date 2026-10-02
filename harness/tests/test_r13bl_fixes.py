"""R13bl (02.10.2026): Harness-Wartung - Punkt 1 von vier, je Punkt ein Commit.

  1. **Pflichtzeile `B-SCHRITT:`** - die B-Batch-Nummer ist eine **Zaehlung**; die Grenze
     von 20 B-Batches ist seit dem 30.09.2026 aufgehoben (Nutzerentscheid). Die alte
     Formulierung "von max 20" ist aus `prompts/reviewer.md` und aus dem Hinweis, den der
     Harness in den Review-Prompt schreibt, verschwunden.

Die weiteren Punkte dieser Runde kommen in den folgenden Commits in dieselbe Datei.

Alles laeuft in Wegwerf-Verzeichnissen; der echte Zustand, das Decomp-Repo und der
laufende Harness bleiben unberuehrt (kein Neustart).
"""

from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import reviewer, stand                                  # noqa: E402
from hx.config import load_config                               # noqa: E402
from hx.orchestrator import Orchestrator                        # noqa: E402
from hx.util import Log, ensure_dir, write_text_atomic          # noqa: E402


class Basis(unittest.TestCase):
    """Wegwerf-Repo: `cfg` zeigt auf ein Temp-Verzeichnis, nie auf den echten Stand."""

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13bl"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "harness")
        self.decomp = ensure_dir(self.tmp / "decomp")
        self.ana = ensure_dir(self.decomp / "analysis")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.decomp)
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["paths"]["harness_home"] = str(self.tmp)
        cfg.data["telegram"]["allowlist_user_ids"] = []
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def auftrag(self, batch: int, text: str) -> None:
        d = ensure_dir(self.root / "runs" / f"b{batch:03d}")
        write_text_atomic(d / "auftrag.md", text)

    def orch(self, batch: int = 209) -> Orchestrator:
        o = Orchestrator(self.cfg, self.log, mock=True,
                         state_file=self.root / "state" / "run.json")
        o.qroot = self.root
        o.said = []
        o.say = lambda t="", *a, **k: o.said.append(str(t))
        o.state.data["batch"] = int(batch)
        o.state.save()
        return o


# ============================================ 1) Pflichtzeile als Zaehlung
class TestPflichtzeileZaehlung(Basis):
    """Punkt 1: "B-Batch <k> von max 20" -> "B-Batch <k> (Zaehlung, keine Grenze ...)"."""

    ALT = "von max 20"

    def test_vorlage_hat_die_alte_formulierung_nicht_mehr(self):
        text = (ROOT / "prompts" / "reviewer.md").read_text(encoding="utf-8")
        self.assertNotIn(self.ALT, text)
        self.assertIn("Zählung, keine Grenze", text)

    def test_hinweis_nennt_die_zaehlung(self):
        self.auftrag(208, "B208 ist der ERSTE Batch von Strang B.")
        h = stand.pflichtzeile_hinweis(self.cfg, 208)
        self.assertIn("B208 ist ein B-Batch", h)
        self.assertNotIn(self.ALT, h)
        self.assertIn("keine Grenze", h)

    def test_erzeugter_reviewer_prompt_hat_die_alte_formulierung_nicht(self):
        """Der Prompt wird wirklich gebaut (nicht nur die Vorlage gelesen)."""
        self.auftrag(208, "B208 ist der ERSTE Batch von Strang B.")
        ctx = self.orch(208).review_context("(Snapshot)")
        self.assertIn("keine Grenze", ctx["protokoll_warnung"])
        prompt = reviewer.build_prompt(self.cfg, "batch_end", ctx)
        self.assertIn("=== PROTOKOLL-WARNUNG (Pflichtzeilen im Review) ===", prompt)
        self.assertNotIn(self.ALT, prompt)
        self.assertIn("keine Grenze", prompt)

    def test_der_parser_haengt_nicht_am_wortlaut(self):
        """`_RE_B_SCHRITT` liest nur `n/5` - die alte wie die neue Schreibweise zaehlen."""
        self.assertTrue(stand._RE_B_SCHRITT.search("B-SCHRITT: 2/5 Maschine, B-Batch 2 von max 20"))
        self.assertTrue(stand._RE_B_SCHRITT.search(
            "B-SCHRITT: 2/5 Maschine, B-Batch 2 (Zählung, keine Grenze – Nutzerentscheid 30.09.)"))


if __name__ == "__main__":
    unittest.main()
