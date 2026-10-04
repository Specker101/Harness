"""Tests R13bv (2026-10-04): `/watch` zeigt Fortsetzungs-Mitschnitte.

**Auftrag (Nutzer).** Nach einer Fortsetzung im selben Chat schreibt der Worker nach
`runs/b<N>/stream-forts<k>.jsonl` (`hx/worker.py:1067`, k ab 1). `hx/watch.py` las in
`_follow_live` nur `stream.jsonl` - `/watch` blieb nach dem Ende des ersten Teils stumm,
obwohl der Worker weiterarbeitete (gemessen: B266, `stream-forts1.jsonl`).

Abnahme:
  * alle Teile in **numerischer** Reihenfolge (`forts10` nach `forts9`),
  * keine Zeile doppelt, Trennzeile `--- Fortsetzung <k> ---` EINMAL beim Wechsel,
  * eine Fortsetzung, die erst nach dem Start des Zuschauers auftaucht, wird live
    mitgelesen (ohne Neustart),
  * Herzschlag: nach 60 s ohne neue Zeile eine Statuszeile, solange der Batch laeuft;
    die Zahlenzeile bei Aenderung (`_print_stats`, R11-4) bleibt unberuehrt.
"""

from __future__ import annotations

import json
import shutil
import sys
import time
import unittest
import zipfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import watch                                              # noqa: E402
from hx.config import load_config                                 # noqa: E402
from hx.util import Log, ensure_dir, write_text_atomic            # noqa: E402


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13bv"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "root")
        ensure_dir(self.root / "runs")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["harness_home"] = str(self.tmp)
        cfg.data["paths"]["decomp"] = str(ensure_dir(self.tmp / "decomp"))
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ------------------------------------------------------------------ Helfer
    def run_dir(self, batch: int = 266) -> Path:
        return ensure_dir(self.root / "runs" / f"b{batch:03d}")

    def mitschnitt(self, pfad: Path, *marker: str, anhaengen: bool = False) -> Path:
        """Mitschnittzeilen schreiben - je Marker eine Assistenten-Zeile mit diesem Text."""
        text = "".join(json.dumps({
            "type": "assistant",
            "message": {"id": m, "model": "deepseek-flash[1m]",
                        "usage": {"input_tokens": 10, "output_tokens": 2},
                        "content": [{"type": "text", "text": m}]}}) + "\n" for m in marker)
        with pfad.open("a" if anhaengen else "w", encoding="utf-8") as fh:
            fh.write(text)
        return pfad

    def zustand(self, batch: int = 266, state: str = "DS_WORKING") -> None:
        write_text_atomic(self.root / "state" / "run.json", json.dumps({
            "state": state, "batch": batch, "last_batch_number": batch, "paused": False,
            "updated_at": "2026-10-04T18:00:00+00:00"}))

    def watcher(self) -> watch.Watcher:
        return watch.Watcher(self.cfg, self.log, color=False)


# ------------------------------------------------- 1) Reihe, Reihenfolge, Dopplung
class TestReihe(Basis):
    def test_alle_teile_in_reihenfolge_ohne_dopplung(self):
        rd = self.run_dir()
        self.mitschnitt(rd / "stream.jsonl", "TEIL1")
        self.mitschnitt(rd / "stream-forts1.jsonl", "FORTS1")
        self.mitschnitt(rd / "stream-forts2.jsonl", "FORTS2")
        w = self.watcher()
        aus = StringIO()
        with redirect_stdout(aus):
            self.assertTrue(w._tail_reihe(rd, "WORKER", "seen_forts"), "neue Zeilen")
        text = aus.getvalue()
        self.assertEqual(text.count("TEIL1"), 1, text)
        self.assertEqual(text.count("FORTS1"), 1, text)
        self.assertEqual(text.count("FORTS2"), 1, text)
        self.assertIn("--- Fortsetzung 1 ---", text)
        self.assertIn("--- Fortsetzung 2 ---", text)
        self.assertLess(text.index("TEIL1"), text.index("FORTS1"))
        self.assertLess(text.index("FORTS1"), text.index("FORTS2"))
        aus2 = StringIO()
        with redirect_stdout(aus2):
            self.assertFalse(w._tail_reihe(rd, "WORKER", "seen_forts"), "nichts Neues")
        self.assertEqual(aus2.getvalue(), "", "kein zweiter Durchlauf, keine zweite Trennzeile")

    def test_neue_zeile_in_der_fortsetzung(self):
        rd = self.run_dir()
        self.mitschnitt(rd / "stream.jsonl", "TEIL1")
        self.mitschnitt(rd / "stream-forts1.jsonl", "FORTS1")
        w = self.watcher()
        with redirect_stdout(StringIO()):
            w._tail_reihe(rd, "WORKER", "seen_forts")
        self.mitschnitt(rd / "stream-forts1.jsonl", "FORTS1B", anhaengen=True)
        aus = StringIO()
        with redirect_stdout(aus):
            self.assertTrue(w._tail_reihe(rd, "WORKER", "seen_forts"))
        text = aus.getvalue()
        self.assertIn("FORTS1B", text)
        zeilen = [z.strip() for z in text.splitlines()]
        self.assertEqual(zeilen.count("FORTS1"), 0,
                         "die schon gezeigte Zeile kommt nicht wieder")
        self.assertEqual(zeilen.count("FORTS1B"), 1)
        self.assertNotIn("--- Fortsetzung 1 ---", text)

    def test_forts10_kommt_nach_forts9(self):
        """Numerisch, nicht alphabetisch (`stream-forts10` < `stream-forts9` als Text)."""
        rd = self.run_dir()
        self.mitschnitt(rd / "stream.jsonl", "TEIL1")
        self.mitschnitt(rd / "stream-forts9.jsonl", "NEUN")
        self.mitschnitt(rd / "stream-forts10.jsonl", "ZEHN")
        namen = [p.name for _n, p in self.watcher()._mitschnitt_reihe(rd)]
        self.assertEqual(namen, ["stream.jsonl", "stream-forts9.jsonl",
                                 "stream-forts10.jsonl"])

    def test_fortsetzung_taucht_spaeter_auf(self):
        """Der Zuschauer laeuft schon - die Fortsetzung wird ohne Neustart mitgelesen."""
        rd = self.run_dir()
        self.mitschnitt(rd / "stream.jsonl", "TEIL1")
        w = self.watcher()
        with redirect_stdout(StringIO()):
            self.assertTrue(w._tail_reihe(rd, "WORKER", "seen_forts"))
        self.mitschnitt(rd / "stream-forts1.jsonl", "FORTS1")     # jetzt entsteht sie
        aus = StringIO()
        with redirect_stdout(aus):
            self.assertTrue(w._tail_reihe(rd, "WORKER", "seen_forts"))
        text = aus.getvalue()
        self.assertIn("--- Fortsetzung 1 ---", text)
        self.assertIn("FORTS1", text)
        self.assertNotIn("TEIL1", text, "der erste Teil wird nicht wiederholt")

    def test_gepackte_fortsetzung_wird_gelesen(self):
        """`stream-forts1.jsonl.zip` (R13p) - die entpackte Datei fehlt."""
        rd = self.run_dir()
        self.mitschnitt(rd / "stream.jsonl", "TEIL1")
        roh = self.mitschnitt(rd / "_tmp_forts1.jsonl", "FORTS1")
        with zipfile.ZipFile(rd / "stream-forts1.jsonl.zip", "w") as zf:
            zf.write(roh, "stream-forts1.jsonl")
        roh.unlink()
        w = self.watcher()
        aus = StringIO()
        with redirect_stdout(aus):
            self.assertTrue(w._tail_reihe(rd, "WORKER", "seen_forts"))
        self.assertIn("FORTS1", aus.getvalue())

    def test_kleinere_datei_gilt_als_neuer_lauf(self):
        """Wird derselbe Ordner neu benutzt, faengt der Mitschnitt von vorn an."""
        rd = self.run_dir()
        self.mitschnitt(rd / "stream.jsonl", "ALT1", "ALT2", "ALT3")
        w = self.watcher()
        with redirect_stdout(StringIO()):
            w._tail_reihe(rd, "WORKER", "seen_forts")
        self.mitschnitt(rd / "stream.jsonl", "NEU1")              # neuer Lauf, kuerzer
        aus = StringIO()
        with redirect_stdout(aus):
            self.assertTrue(w._tail_reihe(rd, "WORKER", "seen_forts"))
        self.assertIn("NEU1", aus.getvalue())


# ------------------------------------------------------------ 2) Live-Schleife
class TestLiveFortsetzung(Basis):
    def _loop(self, runden: int = 4, vorbereiten=None) -> str:
        """`_follow_live` mit gepatchtem `time.sleep` fahren (kein echtes Warten)."""
        w = self.watcher()
        zaehler = {"n": 0}

        def schlaf(_sekunden):
            zaehler["n"] += 1
            if vorbereiten:
                vorbereiten(zaehler["n"])
            if zaehler["n"] > runden:
                raise KeyboardInterrupt

        aus = StringIO()
        with redirect_stdout(aus), mock.patch("time.sleep", side_effect=schlaf):
            w._follow_live()
        return aus.getvalue()

    def test_live_schaltet_ohne_neustart_um(self):
        """Zuschauer laeuft zwei Runden OHNE Fortsetzung, dann kommt `stream-forts1`."""
        self.zustand(266)
        rd = self.run_dir()
        self.mitschnitt(rd / "stream.jsonl", "TEIL1")

        def bei_runde(n):
            if n == 3:
                self.mitschnitt(rd / "stream-forts1.jsonl", "FORTS1")

        text = self._loop(4, bei_runde)
        self.assertIn("Worker laeuft: b266", text)
        self.assertIn("TEIL1", text)
        self.assertIn("--- Fortsetzung 1 ---", text)
        self.assertIn("FORTS1", text)
        self.assertEqual(text.count("TEIL1"), 1, "keine Dopplung in der Schleife")

    def test_live_zeigt_den_herzschlag_nach_der_stille(self):
        self.zustand(266)
        rd = self.run_dir()
        self.mitschnitt(rd / "stream.jsonl", "TEIL1")
        w = self.watcher()
        aus = StringIO()
        with redirect_stdout(aus):
            w._herzschlag(266, rd)                        # gerade erst gelesen -> nichts
            self.assertEqual(aus.getvalue(), "")
            w._letzte_zeile = time.time() - 61            # 61 s Stille
            w._herzschlag(266, rd)                        # -> Statuszeile
            w._herzschlag(266, rd)                        # gedrosselt -> keine zweite
        text = aus.getvalue()
        self.assertEqual(text.count("laufend, letzte Aktivität vor"), 1, text)
        self.assertIn("Batch 266 laufend, letzte Aktivität vor 1.0 min", text)
        self.assertIn("(Mitschnitt: stream.jsonl)", text)

    def test_live_herzschlag_nennt_die_neueste_fortsetzung(self):
        rd = self.run_dir()
        self.mitschnitt(rd / "stream.jsonl", "TEIL1")
        self.mitschnitt(rd / "stream-forts3.jsonl", "FORTS3")
        w = self.watcher()
        w._letzte_zeile = time.time() - 300
        aus = StringIO()
        with redirect_stdout(aus):
            w._herzschlag(266, rd)
        self.assertIn("vor 5.0 min", aus.getvalue())
        self.assertIn("(Mitschnitt: stream-forts3.jsonl)", aus.getvalue())

    def test_im_pausenzustand_keine_worker_zeilen(self):
        """Ohne laufenden Worker (PAUSED, keine Worker-Phase) wird nichts gelesen."""
        self.zustand(266, state="PAUSED")
        rd = self.run_dir()
        self.mitschnitt(rd / "stream.jsonl", "TEIL1")
        self.mitschnitt(rd / "stream-forts1.jsonl", "FORTS1")
        text = self._loop(3)
        self.assertNotIn("TEIL1", text)
        self.assertNotIn("FORTS1", text)
        self.assertNotIn("laufend, letzte Aktivität vor", text)


# -------------------------------------------- 3) Zahlenzeile bleibt (R11-4)
class TestZahlenzeile(Basis):
    def test_zahlen_kommen_auch_aus_der_fortsetzung(self):
        rd = self.run_dir()
        self.mitschnitt(rd / "stream.jsonl", "TEIL1")
        self.mitschnitt(rd / "stream-forts1.jsonl", "FORTS1", "FORTS1B")
        w = self.watcher()
        with redirect_stdout(StringIO()):
            w._tail_reihe(rd, "WORKER", "seen_forts")
        self.assertEqual(w.stats.totals()["requests"], 3,
                         "alle Teile zaehlen in dieselben Kennzahlen")
        aus = StringIO()
        with redirect_stdout(aus):
            w._print_stats()                       # Zahlen neu -> eine Zeile
            w._print_stats()                       # unveraendert -> keine zweite
        self.assertEqual(aus.getvalue().count("laufend:"), 1, aus.getvalue())


if __name__ == "__main__":
    unittest.main()
