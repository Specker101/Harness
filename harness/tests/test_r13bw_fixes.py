"""Tests fuer R13bw (2026-10-05): Fortsetzung nach dem Preflight bis zur Umschaltschwelle.

**Aussensicht M268-3.** Die Rest-Bremse aus R13bb (Nachfolgerin der R13aw-Regel) liess
Batches zu frueh enden: gemessen tragen B255 (132,5 min), B259 (127,9), B260 (130,6),
B264 (130,9) und B268 (119,2) `fortsetzung_uebertrag: true`, obwohl die Batch-Uhr die
Umschaltschwelle noch nicht erreicht hatte. Die Schwelle ist **dynamisch**
(`worker.umschalt_minuten`: Grundwert 135 min, vorgezogen um die gemessene Preflight-Dauer -
fuer B268 sind das 22,4 min, also 122,6 min) und wird deshalb in den Tests nicht
festgeschrieben, sondern ueber `umschalt_minuten` geholt. B268 hatte 3,4 min Rest bei 20 min
Merkgrenze und setzte gar nicht fort (kein `stream-forts*.jsonl`).

**Neue Regel.** Liegt die Batch-Uhr unter der Umschaltschwelle und ist die Nachrueckliste
offen, wird auch nach einem gelaufenen Preflight angestossen; der Rest ist nur noch eine
Merkgrenze (`rest_min`, `rest_knapp`). **Unveraendert:** ueber der Schwelle gibt es keinen
Anstoss, und eine *erledigte* Nachrueckliste beendet den Batch schon vorher
(`NACHRUECKLISTE ERLEDIGT`).

**Zaehlung.** Mehrere Preflight-Laeufe je Batch sind kein Verstoss: gezaehlt wird jeder
Start (Mitschnitt, nicht der Hook - der sieht nur Exit 0), und es gilt der **letzte** Lauf
(`prompts/reviewer.md`).

Wegwerf-Verzeichnisse unter `tests/_tmp_r13bw`.
"""

from __future__ import annotations

import inspect
import json
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import stand, streamjson, worker                          # noqa: E402
from hx.config import load_config                                 # noqa: E402
from hx.util import Log, ensure_dir, read_text, write_text_atomic  # noqa: E402

AUFTRAG = ("TEIL 1: etwas bauen.\n\n## NACHRUECKLISTE\n1. Posten eins\n2. Posten zwei\n")
OHNE_LISTE = "TEIL 1: etwas bauen - Liste ist fertig.\n"
START = "2026-09-30T21:42:34+00:00"
REVIEWER = ROOT / "prompts" / "reviewer.md"


def _assistant(mid: str, kontext: int) -> str:
    return json.dumps({"type": "assistant", "timestamp": "2026-09-30T00:00:00Z",
                       "message": {"id": mid, "model": "m", "content": [],
                                   "usage": {"input_tokens": kontext}}})


def _result(kontext: int) -> str:
    return json.dumps({"type": "result", "subtype": "success", "num_turns": 5,
                       "result": "fertig", "is_error": False,
                       "usage": {"input_tokens": kontext}})


def preflight_aufruf(kennung: str = "tu-pf") -> dict:
    """Ein ECHTER Preflight-Start (`streamjson.ist_preflight_aufruf`)."""
    return {"zeile": 1, "ts": "2026-09-30T00:00:00Z", "id": kennung, "name": "PowerShell",
            "input": {"command": "python -u scripts/preflight.py before *> out.txt",
                      "description": "Preflight"}}


def mitschnitt_aufruf(kennung: str, ts: str) -> str:
    """Eine Mitschnitt-Zeile mit einem Preflight-Start (fuer den Zaehler)."""
    return json.dumps({"type": "assistant", "timestamp": ts,
                       "message": {"role": "assistant", "content": [
                           {"type": "tool_use", "id": kennung, "name": "PowerShell",
                            "input": {"command": "python -u scripts/preflight.py before",
                                      "description": "Preflight"}}]}})


class Pruefbasis(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config()

    @staticmethod
    def _run():
        from hx.proc import StreamRun
        r = StreamRun()
        r.rc = 0
        r.killed_reason = None
        return r

    def _stats(self, kontext: int = 300000, preflight: bool = False):
        s = streamjson.StreamStats()
        s.feed(_assistant("m1", 1000))
        s.feed(_assistant("m2", kontext))
        s.feed(_result(kontext))
        if preflight:
            s.tools.append(preflight_aufruf())
        return s

    def umschalt(self) -> float:
        return float(worker.umschalt_minuten(self.cfg)["umschalt_min"])

    def entsch(self, minuten: float, preflight: bool = True, auftrag: str = AUFTRAG,
               fortsetzungen: list | None = None) -> dict:
        return worker.fortsetzung_pruefen(self.cfg, self._run(), self._stats(preflight=preflight),
                                          auftrag, minuten, [] if fortsetzungen is None
                                          else fortsetzungen)


# -------------------------------------------- 1) Uhr unter der Schwelle: Anstoss
class TestUnterDerSchwelleWirdAngestossen(Pruefbasis):
    def test_preflight_und_uhr_unter_der_schwelle_gibt_fortsetzung(self):
        """Der Kernfall: der Rest ist keine Bremse mehr."""
        u = self.umschalt()
        for rest in (60.0, 25.0, 20.0, 19.9, 10.0, 15.8, 1.0):
            with self.subTest(rest=rest):
                e = self.entsch(u - rest)
                self.assertTrue(e["ja"], e)
                self.assertTrue(e["preflight_erneut"], e)
                self.assertAlmostEqual(e["rest_min"], rest, places=1)
                self.assertFalse(e.get("uebertrag"))

    def test_b268_ist_jetzt_ein_anstoss(self):
        """Der gemessene Fall: 119,2 min - die Uhr war unter der Schwelle, der Rest so klein,
        dass die 20-min-Bremse griff."""
        u = self.umschalt()
        self.assertLess(119.2, u, "B268 muss unter der Schwelle liegen")
        e = self.entsch(119.2)
        self.assertTrue(e["ja"], e)
        self.assertTrue(e["rest_knapp"])
        self.assertTrue(e["preflight_erneut"])
        self.assertAlmostEqual(e["rest_min"], u - 119.2, places=1)
        self.assertLess(e["rest_min"], 20.0)

    def test_rest_knapp_markiert_nur_die_merkgrenze(self):
        u = self.umschalt()
        knapp = self.entsch(u - 19.9)
        genug = self.entsch(u - 20.0)
        self.assertTrue(knapp["rest_knapp"])
        self.assertFalse(genug["rest_knapp"])
        self.assertEqual(float(self.cfg.get("limits", "fortsetzung_min_rest_min", 0)), 20.0)

    def test_ohne_preflight_bleibt_der_anstoss_ohne_merkmal(self):
        u = self.umschalt()
        e = self.entsch(u - 10, preflight=False)
        self.assertTrue(e["ja"])
        self.assertNotIn("preflight_erneut", e)
        self.assertNotIn("rest_knapp", e)

    def test_zwei_anstosse_nach_preflight_sind_erlaubt(self):
        """„zwei Preflights im Batch" ist kein Verstoss - der zweite Anstoss laeuft."""
        u = self.umschalt()
        einer = self.entsch(u - 10, fortsetzungen=[{"minute": 40.0, "preflight_erneut": True}])
        self.assertTrue(einer["ja"], einer)
        zwei = self.entsch(u - 5, fortsetzungen=[{"minute": 40.0}, {"minute": 80.0}])
        self.assertFalse(zwei["ja"])
        self.assertIn("max_fortsetzungen", zwei["grund"])


# -------------------------------------------- 2) Uhr ueber der Schwelle: kein Anstoss
class TestUeberDerSchwelleKeinAnstoss(Pruefbasis):
    def test_uhr_auf_oder_ueber_der_schwelle_gibt_keine_fortsetzung(self):
        u = self.umschalt()
        for minuten in (u, u + 0.1, u + 20.0):
            with self.subTest(minuten=minuten):
                e = self.entsch(minuten)
                self.assertFalse(e["ja"], e)
                self.assertIn(">= Umschaltschwelle", e["grund"])
                self.assertNotIn("rest_knapp", e)
                self.assertNotIn("preflight_erneut", e)

    def test_auch_ohne_preflight_keine_fortsetzung(self):
        u = self.umschalt()
        e = self.entsch(u + 5, preflight=False)
        self.assertFalse(e["ja"])
        self.assertIn("Umschaltschwelle", e["grund"])

    def test_b257_bleibt_abgelehnt(self):
        """Gegenprobe aus der Messung: B257 endete bei 154,8 min -> Absage durch die Uhr
        (`Batch-Uhr 155 min >= Umschaltschwelle 135 min`), nicht durch den Preflight."""
        u = self.umschalt()
        e = self.entsch(154.8)
        self.assertFalse(e["ja"])
        self.assertIn(">= Umschaltschwelle", e["grund"])
        self.assertIn("Batch-Uhr", e["grund"])
        self.assertNotIn("UEBERTRAG", e["grund"])
        self.assertGreater(154.8, u)


# -------------------------------------------- 3) Nachrueckliste erledigt: kein Anstoss
class TestNachruecklisteErledigt(Pruefbasis):
    def test_erledigt_wird_erkannt(self):
        self.assertTrue(worker.nachrueckliste_erledigt(
            "TEIL 1 fertig.\n\nNACHRUECKLISTE ERLEDIGT\n1. abc1234\n"))
        self.assertFalse(worker.nachrueckliste_erledigt("TEIL 1 fertig, Liste noch offen.\n"))

    def test_der_lauf_bricht_vor_dem_anstoss_ab(self):
        """Der Erledigt-Zweig steht VOR `fortsetzung_pruefen` - die Reihenfolge ist die Regel."""
        quelle = inspect.getsource(worker.run_batch)
        self.assertIn('letzte_f["antwort_kurz"] = "NACHRUECKLISTE ERLEDIGT"', quelle)
        self.assertIn("Nachrueckliste erledigt - kein weiterer Anstoss", quelle)
        self.assertLess(quelle.index("nachrueckliste_erledigt(antwort)"),
                        quelle.index("entsch = fortsetzung_pruefen("))

    def test_ohne_liste_im_auftrag_kein_anstoss(self):
        """Und das gilt auch unter der Schwelle und nach einem Preflight."""
        u = self.umschalt()
        e = self.entsch(u - 10, auftrag=OHNE_LISTE)
        self.assertFalse(e["ja"])
        self.assertEqual(e["grund"], "kein Abschnitt NACHRUECKLISTE im Auftrag")
        self.assertNotIn("rest_knapp", e)


# -------------------------------------------- 4) Mehrere Preflights: gezahlt, kein Verstoss
class TestMehrerePreflightsKeinVerstoss(unittest.TestCase):
    """Zwei Preflights im Batch (plus einer in der Fortsetzung) - kein Regelverstoss."""

    BATCH = 999

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13bw"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "harness")
        self.rd = ensure_dir(self.root / "runs" / f"b{self.BATCH:03d}")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(ensure_dir(self.tmp / "decomp"))
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["telegram"]["allowlist_user_ids"] = []
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _drei_starts(self) -> None:
        write_text_atomic(self.rd / "stream.jsonl",
                          "\n".join([mitschnitt_aufruf("tu1", "2026-09-30T22:00:00+00:00"),
                                     mitschnitt_aufruf("tu2", "2026-09-30T22:40:00+00:00")]) + "\n")
        write_text_atomic(self.rd / "stream-forts1.jsonl",
                          mitschnitt_aufruf("tu3", "2026-09-30T23:10:00+00:00") + "\n")

    def test_alle_starts_im_batch_werden_gezaehlt(self):
        self._drei_starts()
        d = stand.mitschnitt_preflight_aufrufe(self.cfg, self.BATCH,
                                               start_zeit=stand._iso_zeit(START))
        self.assertEqual(d["laeufe"], 3)
        self.assertEqual(d["dateien"], ["stream.jsonl", "stream-forts1.jsonl"])
        self.assertEqual([a["min"] for a in d["aufrufe"]], [17.4, 57.4, 87.4])

    def test_frueh_zaehlt_die_laeufe_vor_der_schwelle(self):
        """„zu frueh" ist die Zahl der Starts vor der Umschaltschwelle - hier zwei."""
        self._drei_starts()
        d = stand.mitschnitt_preflight_aufrufe(self.cfg, self.BATCH,
                                               start_zeit=stand._iso_zeit(START),
                                               umschalt_min=60.0, nachrueckliste=True)
        self.assertEqual(d["frueh"], 2)

    def test_die_zeile_nennt_die_zahl_ohne_verstoss(self):
        self._drei_starts()
        zeile = stand.preflight_zaehler_zeile(self.cfg, self.BATCH, laeufe=3, frueh=2,
                                             hook=3, mitschnitt=3)[0]
        self.assertTrue(zeile.startswith("PREFLIGHT-AUFRUFE: 3 (Quelle Stream)"), zeile)
        self.assertIn("3 Aufruf(e) im Mitschnitt (davon 2 zu frueh)", zeile)
        for wort in ("Verstoss", "Verstoß", "Regelverstoss"):
            self.assertNotIn(wort, zeile)

    def test_ueberholte_und_fehllaeufe_kommen_aus_dem_archiv(self):
        """Die Archivdateien desselben Batches erhoehen die Zahl - kein Fehlerfall."""
        ana = ensure_dir(Path(self.cfg.decomp) / "analysis" / f"_m{self.BATCH}")
        write_text_atomic(ana / f"_preflight_{self.BATCH}.txt", "gueltig\n")
        write_text_atomic(ana / f"_preflight_{self.BATCH}_fehllauf1.txt", "fehllauf\n")
        write_text_atomic(ana / f"_preflight_{self.BATCH}_ueberholt.txt", "ueberholt\n")
        write_text_atomic(ana / f"_preflight_{self.BATCH}_vor_fortsetzung1.txt", "kopie\n")
        a = stand.preflight_archiv(self.cfg, self.BATCH)
        self.assertEqual(a["ungezaehlt"], 1)
        self.assertEqual(len(a["ueberholt"]), 1)
        zeile = stand.preflight_zaehler_zeile(self.cfg, self.BATCH, laeufe=1, frueh=1,
                                             hook=1, mitschnitt=1)[0]
        self.assertIn("1 ueberholt abgelegt", zeile)

    def test_der_letzte_preflight_gilt_steht_im_reviewer_prompt(self):
        """Die Pruefung „genau ein gueltiger Preflight" ist eine Textregel - sie muss den
        letzten Lauf gelten lassen, nicht den einzigen."""
        text = read_text(REVIEWER)
        self.assertIn("der letzte; fruehere sind ueberholt", text)
        self.assertIn("Mehrere Preflights je Batch sind der Regelfall", text)
        self.assertIn("aufgehoben", text)
        self.assertIn("Ein `UEBERTRAG` nach Preflight", text)


if __name__ == "__main__":                       # pragma: no cover
    unittest.main()
