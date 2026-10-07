"""Tests fuer R13bw-15: Nutzerlimit vor/nach dem Lauf in der Kopfzeile der meta.md.

Auftrag (Nutzer, 2026-10-07, Harness-Wartung): "Bei jeder echten Aussensicht
(hx/aussensicht.py) das Nutzerlimit aus logs/rate-limit.json VOR dem Lauf lesen und NACH
dem Lauf erneut (schreibe_rate_limit), und im Kopf der meta.md eine Zeile ergaenzen:
'Nutzerlimit: Sitzung x % -> y %, Woche a % -> b %'. Gleiche Zeile fuer den Reviewer in
runs/b<N>/review-Kopf nur, wenn das ohne Eingriff in die Antwortdatei geht (sonst
weglassen)."

Der zweite Teil ist BEWUSST nicht umgesetzt: `runs/b<N>/review.md` ist die Antwortdatei
selbst (`orchestrator.py` schreibt `res.text` unveraendert hinein, ebenso die Kopie
`logs/review-<stempel>.md` in `reviewer.py`) - eine Kopfzeile waere ein Eingriff und ist
damit nach dem Auftrag zu unterlassen. Der Test unten haelt diesen Befund fest, damit
die Entscheidung nicht still verschwindet.

Alles im Attrappenbetrieb: kein Netz, keine API-Kosten, kein Ghidra.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import aussensicht, streamjson                                  # noqa: E402
from hx.config import load_config                                       # noqa: E402
from hx.retention import _weg                                           # noqa: E402
from hx.state import State                                              # noqa: E402
from hx.util import Log, ensure_dir                                     # noqa: E402

INFO_VOR = {"unifiedWindows": {"five_hour": {"utilization": 0.25, "resetsAt": 1790521200},
                               "seven_day": {"utilization": 0.27, "resetsAt": 1790658000}}}
INFO_NACH = {"unifiedWindows": {"five_hour": {"utilization": 0.46, "resetsAt": 1790521200},
                                "seven_day": {"utilization": 0.30, "resetsAt": 1790658000}}}
ZEILE = "Nutzerlimit: Sitzung 25 % -> 46 %, Woche 27 % -> 30 %"

ANTWORT = ("<AUSSENSICHT>\n(Attrappe) geprueft.\n</AUSSENSICHT>\n")


def _rate_ev(info: dict) -> dict:
    return {"type": "rate_limit_event", "rate_limit_info": info}


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__file__).resolve().parent / "_tmp_r13bw15"
        _weg(self.tmp)
        self.root = ensure_dir(self.tmp / "harness")
        self.decomp = ensure_dir(self.tmp / "decomp")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.decomp)
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["telegram"]["allowlist_user_ids"] = []
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)
        self.state = State(self.root / "state" / "run.json")
        self.state.data["batch"] = 289

    def tearDown(self):
        _weg(self.tmp)


# --------------------------------------------------------------- die Zeile selbst
class TestDeltaZeile(unittest.TestCase):
    def test_beide_seiten_ergeben_die_auftragszeile(self):
        self.assertEqual(streamjson.rate_limit_delta_zeile({"info": INFO_VOR},
                                                           {"info": INFO_NACH}),
                         ZEILE)

    def test_info_objekte_werden_auch_direkt_genommen(self):
        self.assertEqual(streamjson.rate_limit_delta_zeile(INFO_VOR, INFO_NACH), ZEILE)

    def test_fehlende_seite_steht_als_fragezeichen(self):
        self.assertEqual(streamjson.rate_limit_delta_zeile({}, {"info": INFO_NACH}),
                         "Nutzerlimit: Sitzung ? -> 46 %, Woche ? -> 30 %")

    def test_ohne_jede_messung_wird_nichts_erfunden(self):
        self.assertEqual(streamjson.rate_limit_delta_zeile({}, {}),
                         "Nutzerlimit: nicht gemessen")
        self.assertEqual(streamjson.rate_limit_delta_zeile(None, None),
                         "Nutzerlimit: nicht gemessen")

    def test_nur_ein_fenster_verschwindet_nicht(self):
        halb = {"unifiedWindows": {"five_hour": {"utilization": 0.5, "resetsAt": 1}}}
        self.assertEqual(streamjson.rate_limit_delta_zeile({"info": halb}, {"info": halb}),
                         "Nutzerlimit: Sitzung 50 % -> 50 %")

    def test_rate_limit_info_kennt_beide_formen(self):
        self.assertEqual(streamjson.rate_limit_info({"info": INFO_VOR}), INFO_VOR)
        self.assertEqual(streamjson.rate_limit_info(INFO_VOR), INFO_VOR)
        self.assertEqual(streamjson.rate_limit_info({}), {})
        self.assertEqual(streamjson.rate_limit_info(None), {})


# --------------------------------------------------------------- die Kopfzeile
class TestKopfzeile(Basis):
    def _bericht(self, vor: dict, nach: dict) -> str:
        res = aussensicht.Ergebnis()
        res.rc, res.modell = 0, "claude-opus-5-5"
        res.rate_limit_vor, res.rate_limit_nach = vor, nach
        return aussensicht.bericht(self.cfg, 289, "Test", res, {}, [])

    def test_zeile_steht_im_kopf_direkt_hinter_dem_lauf(self):
        text = self._bericht({"info": INFO_VOR}, {"info": INFO_NACH})
        kopf = text.splitlines()[:8]
        index = next(i for i, z in enumerate(kopf) if z.startswith("- Lauf:"))
        self.assertEqual(kopf[index + 1], "- " + ZEILE)

    def test_ohne_messung_steht_nicht_gemessen_im_kopf(self):
        self.assertIn("- Nutzerlimit: nicht gemessen", self._bericht({}, {}))

    def test_der_kopf_traegt_die_zahlen_aus_der_datei(self):
        streamjson.schreibe_rate_limit(self.cfg, INFO_VOR)
        self.assertIn("- " + ZEILE,
                      self._bericht(streamjson.lies_rate_limit(self.cfg),
                                    {"info": INFO_NACH}))


# --------------------------------------------------------------- der Lauf
class TestLauf(Basis):
    def test_attrappe_liest_den_stand_zweimal(self):
        streamjson.schreibe_rate_limit(self.cfg, INFO_VOR, "Reviewer")
        res = aussensicht.run(self.cfg, self.log, self.state, "Test", mock=True)
        self.assertEqual(streamjson.rate_limit_info(res.rate_limit_vor), INFO_VOR)
        self.assertEqual(streamjson.rate_limit_info(res.rate_limit_nach), INFO_VOR)
        self.assertIn("- Nutzerlimit: Sitzung 25 % -> 25 %, Woche 27 % -> 27 %",
                      aussensicht.bericht(self.cfg, 289, "Test", res, {}, []))

    def test_echter_lauf_schreibt_den_nachher_stand(self):
        """Der ganze Weg: Stand vorher -> Mitschnitt mit `rate_limit_event` -> Kopfzeile."""
        streamjson.schreibe_rate_limit(self.cfg, INFO_VOR, "Reviewer")

        def fake_run_stream(cmd, env, **kw):
            ziel = Path(kw["out_path"])
            ziel.write_text("\n".join([
                json.dumps({"type": "result", "subtype": "success", "result": ANTWORT,
                            "num_turns": 12}),
                json.dumps(_rate_ev(INFO_NACH)),
            ]) + "\n", encoding="utf-8")
            return SimpleNamespace(rc=0, duration_s=1.0)

        with mock.patch("hx.secrets.load", return_value="x"), \
                mock.patch("hx.envs.reviewer_env", return_value={}), \
                mock.patch.object(aussensicht, "run_stream", fake_run_stream), \
                mock.patch.object(aussensicht, "tiefenprobe_waehlen", return_value={}):
            res = aussensicht.run(self.cfg, self.log, self.state, "Test", mock=False)
        self.assertEqual(streamjson.rate_limit_info(res.rate_limit_vor), INFO_VOR)
        self.assertEqual(streamjson.rate_limit_info(res.rate_limit_nach), INFO_NACH)
        self.assertEqual(streamjson.rate_limit_delta_zeile(res.rate_limit_vor,
                                                           res.rate_limit_nach), ZEILE)
        # Der Nachher-Stand liegt auch in der Datei - der Takt liest ihn von dort.
        self.assertEqual(streamjson.lies_rate_limit(self.cfg)["quelle"], "Aussensicht b289")

    def test_meta_json_traegt_die_rohwerte(self):
        res = aussensicht.Ergebnis()
        res.rc, res.text = 0, ANTWORT
        res.rate_limit_vor, res.rate_limit_nach = {"info": INFO_VOR}, {"info": INFO_NACH}
        p = aussensicht.bericht_schreiben(self.cfg, 289, "Test", res, {}, [])
        d = json.loads(aussensicht.json_pfad(self.cfg, 289).read_text(encoding="utf-8"))
        self.assertEqual(d["nutzerlimit"]["zeile"], ZEILE)
        self.assertTrue(d["nutzerlimit"]["vor"] and d["nutzerlimit"]["nach"])
        self.assertTrue(p.is_file())


# --------------------------------------------------------------- der Verzicht
class TestReviewerBleibtOhneZeile(unittest.TestCase):
    """Der Reviewer-Kopf ist die Antwortdatei selbst - deshalb KEINE Zeile (Auftrag)."""

    def test_review_md_ist_die_rohe_antwort(self):
        root = ROOT.parent / "harness"
        quelle = (root / "hx" / "orchestrator.py").read_text(encoding="utf-8")
        self.assertIn('write_text_atomic(rdir / name, (res.text or "") + "\\n")', quelle)
        quelle = (root / "hx" / "reviewer.py").read_text(encoding="utf-8")
        self.assertIn('write_text_atomic(rd / f"review-{now_iso().replace(\':\', \'\')}.md",',
                      quelle)
        # und die neue Kopfzeile steht nirgends im Reviewer-Pfad
        for datei in ("reviewer.py", "orchestrator.py"):
            text = (root / "hx" / datei).read_text(encoding="utf-8")
            self.assertNotIn("rate_limit_delta_zeile", text)


if __name__ == "__main__":
    unittest.main()
