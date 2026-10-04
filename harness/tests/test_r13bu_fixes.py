"""Tests R13bu (2026-10-04): die ROM-Adressen-Regel in der Worker-Vorlage.

**Auftrag (Nutzer).** Der Worker findet vorhandene native Port-Funktionen nicht, obwohl die
Grep-Pflicht R13az gilt. Gemessen (Belege in `docs/_r13bu_belege.md`): B264 suchte

    Grep {pattern: "…|800261C4|…", head_limit: 20}          # OHNE `path`

und bekam 19 Altbelege aus `analysis/` plus EINEN Port-Treffer - die Port-Dateien mit dem
Dispatcher fielen aus dem Trefferfenster. B265 rief denselben Fall mit `path: "port\\src"`
und `head_limit: 80` und **fand** ihn. B260 suchte `800237B4` (Instruktion IN
`FUN_8002379C`) und damit die falsche Adresse; ohne `-i` fehlt ausserdem die Haelfte
(`FUN_800261C4` und `FUN_800261c4` stehen beide im Port).

Dieser Test haelt die fuenf Regeln im Vorspann fest und prueft, dass das Werkzeug, auf das
die Regel zeigt, im Decomp-Repo wirklich liegt (beide Repos koennen sonst still auseinander
laufen).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import worker                                             # noqa: E402
from hx.config import load_config                                 # noqa: E402


class TestVorspannRegel(unittest.TestCase):
    def test_werkzeug_steht_vorn(self):
        pre = worker.WORKER_PREAMBLE
        self.assertIn("python scripts/port_suche.py", pre)
        self.assertIn("Ausgabe gehoert ins Batch-Dokument", pre)

    def test_fehlstelle_wortlaut(self):
        pre = worker.WORKER_PREAMBLE
        self.assertIn("Fehlstelle: gesucht in port/ und analysis/, nicht gefunden", pre)
        self.assertIn("port_suche.py <adresse>", pre)

    def test_fuenf_grep_regeln(self):
        pre = worker.WORKER_PREAMBLE
        self.assertIn("`path` IMMER setzen (`port` ZUERST, dann `analysis`)", pre)
        self.assertIn("`-i` benutzen", pre)
        self.assertIn("nackt ohne `0x`", pre)
        self.assertIn("`head_limit` mindestens **80**", pre)
        self.assertIn("Funktionseintrag", pre)

    def test_instruktionsadresse_wird_erklaert(self):
        pre = worker.WORKER_PREAMBLE
        self.assertIn("800237B4` -> `FUN_8002379C", pre)

    def test_regel_steht_auch_in_agents_md(self):
        """Die Projektregeln des Decomp-Repos tragen dieselbe Regel (sonst Luecke)."""
        decomp = Path(load_config().decomp)
        agents = decomp / "AGENTS.md"
        if not agents.is_file():
            self.skipTest(f"Decomp-Repo nicht vorhanden ({agents})")
        text = agents.read_text(encoding="utf-8", errors="replace")
        for wort in ("python scripts/port_suche.py",
                     "Fehlstelle: gesucht in port/ und analysis/, nicht gefunden",
                     "head_limit` mindestens **80**", "port` ZUERST, dann `analysis`"):
            self.assertIn(wort, text)

    def test_werkzeug_und_selbsttest_im_decomp_repo(self):
        """Das Werkzeug, auf das die Regel zeigt, existiert und bringt seinen Selbsttest mit."""
        decomp = Path(load_config().decomp)
        werkzeug = decomp / "scripts" / "port_suche.py"
        if not werkzeug.is_file():
            self.skipTest(f"Decomp-Repo nicht vorhanden ({werkzeug})")
        text = werkzeug.read_text(encoding="utf-8", errors="replace")
        self.assertIn("--selftest", text)
        for fall in ("8002379C", "800237B4", "800261C4", "0x40000000"):
            self.assertIn(fall, text, f"Fall {fall} fehlt im Selbsttest")
        self.assertIn("datenwort/maske", text, "die Maske muss klassifiziert werden")
        self.assertIn("_ppc_inventory.json", text, "Aufrufer/Aufgerufene kommen aus der Tafel")


if __name__ == "__main__":
    unittest.main()
