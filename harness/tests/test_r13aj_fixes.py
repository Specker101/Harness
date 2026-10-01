"""Tests fuer R13aj (2026-09-29): Werkzeugdauer bei UEBERLAPPUNG kennzeichnen.

**Befund (gemessen in B212-B214, `tests/_tmp_r13aj/probe*.py`).** Ein `tool_use` steht
immer **allein** in seiner Assistant-Nachricht (B212 234/234, B213 211/211, B214 293/293
Nachrichten mit genau EINEM Aufruf). Zwei Aufrufe koennen sich aber trotzdem ueberlappen:
in B212 steht `stream.jsonl:14790` (Grep) **eine Zeile hinter** `:14789` (PowerShell,
`Get-ChildItem capture\\ppc_cov_boot.bin`), beide mit demselben Zeitstempel - der
gekappte PowerShell-Aufruf lief im Hintergrund weiter. Die Ereignisdistanz misst dann
nicht die Arbeit des Aufrufs, sondern das Warten mit: derselbe Grep steht mit **602,3 s**
und (zweites Paar `:37986/:37987`) mit **511,0 s** in der Liste, obwohl er normale
Treffer lieferte. Genau diese Zahl wanderte ueber `stand.preflight_dauer` in die
Umschaltschwelle.

**Regel.** `stats.laufzeit.langsamste` traegt je Aufruf ein Feld `parallel`
(1 = allein gemessen = 1 + die Zahl der Aufrufe, mit denen sich das Zeitintervall um mehr
als `PARALLEL_TOLERANZ_S` = 1,0 s schneidet). `stand.preflight_dauer` nimmt nur
`parallel == 1`; hat der neueste Batch keinen solchen Aufruf, kommt der Wert aus dem
naechstaelteren Batch und das Log bekommt `Preflight-Dauer aus B<k>, B<N> nur parallel
gemessen`. Die BATCH-UHR nennt die Quelle als `(B<k>)`.

Altdateien ohne das Feld gelten als `parallel = 1` (damals wurde nicht unterschieden).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import stand, streamjson, uhr, worker                     # noqa: E402
from hx.config import load_config                                 # noqa: E402
from hx.util import Log, ensure_dir, write_text_atomic            # noqa: E402

T0 = datetime(2026, 9, 29, 10, 0, 0, tzinfo=timezone.utc)


def _zeile(art: str, t: float, *, name: str | None = None, tid: str | None = None,
           inp: dict | None = None, text: str = "x") -> str:
    """Eine Mitschnittzeile um `t` Sekunden nach `T0`."""
    ts = (T0 + timedelta(seconds=t)).isoformat().replace("+00:00", "Z")
    if art == "use":
        inhalt = [{"type": "text", "text": text},
                  {"type": "tool_use", "id": tid, "name": name, "input": inp or {}}]
        return json.dumps({"type": "assistant", "timestamp": ts,
                           "message": {"id": f"m{tid}", "model": "m",
                                       "usage": {"input_tokens": 100},
                                       "content": inhalt}}, ensure_ascii=False)
    return json.dumps({"type": "user", "timestamp": ts,
                       "message": {"content": [{"type": "tool_result",
                                                "tool_use_id": tid,
                                                "content": text}]}},
                      ensure_ascii=False)


def _stats(zeilen: list[str]) -> streamjson.StreamStats:
    s = streamjson.StreamStats()
    for z in zeilen:
        s.feed(z)
    return s


class TestParallelFeld(unittest.TestCase):
    """`parallel` in `stats.laufzeit.langsamste` (R13aj)."""

    def test_einzelaufruf_ist_parallel_eins(self):
        s = _stats([_zeile("use", 1.0, name="Grep", tid="a", inp={"pattern": "x"}),
                    _zeile("ergebnis", 3.0, tid="a")])
        eintrag = s.laufzeit_profil()["langsamste"][0]
        self.assertEqual(eintrag["parallel"], 1)
        self.assertAlmostEqual(eintrag["dauer_s"], 2.0, places=1)

    def test_zwei_ueberlappende_aufrufe_tragen_parallel_zwei(self):
        """Die B212-Lage: der zweite startet, der erste ist noch offen."""
        s = _stats([_zeile("use", 1.0, name="PowerShell", tid="a",
                           inp={"command": "Get-ChildItem capture\\ppc_cov_boot.bin"}),
                    _zeile("use", 1.1, name="Grep", tid="b", inp={"pattern": "scopes"}),
                    _zeile("ergebnis", 11.0, tid="a"),
                    _zeile("ergebnis", 11.2, tid="b")])
        lang = {e["name"]: e for e in s.laufzeit_profil()["langsamste"]}
        self.assertEqual(lang["PowerShell"]["parallel"], 2)
        self.assertEqual(lang["Grep"]["parallel"], 2,
                         "der Grep lief neben dem offenen PowerShell-Aufruf")

    def test_winzige_ueberlappung_zaehlt_nicht(self):
        """0,2 s sind Rundung der Zeitstempel, kein Nebenlauf (B212-B214: viele davon)."""
        s = _stats([_zeile("use", 1.0, name="PowerShell", tid="a"),
                    _zeile("ergebnis", 3.0, tid="a"),
                    _zeile("use", 2.9, name="Read", tid="b"),
                    _zeile("ergebnis", 4.0, tid="b")])
        for e in s.laufzeit_profil()["langsamste"]:
            self.assertEqual(e["parallel"], 1, e)

    def test_drei_gleichzeitig_ergeben_drei(self):
        s = _stats([_zeile("use", 1.0, name="PowerShell", tid="a"),
                    _zeile("use", 1.5, name="Grep", tid="b"),
                    _zeile("use", 2.0, name="Read", tid="c"),
                    _zeile("ergebnis", 9.0, tid="c"),
                    _zeile("ergebnis", 9.5, tid="b"),
                    _zeile("ergebnis", 10.0, tid="a")])
        self.assertEqual(s.laufzeit_profil()["langsamste"][0]["parallel"], 3)

    def test_toleranz_ist_eine_sekunde(self):
        self.assertEqual(streamjson.PARALLEL_TOLERANZ_S, 1.0)


class TestPreflightDauerAllein(unittest.TestCase):
    """`preflight_dauer` nimmt nur Einzelaufrufe und faellt sonst zurueck (R13aj)."""

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13aj"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "harness")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ------------------------------------------------------------------ Helfer
    def result(self, batch: int, *eintraege: dict) -> None:
        d = ensure_dir(self.root / "runs" / f"b{batch:03d}")
        write_text_atomic(d / "result.json", json.dumps(
            {"rc": 0, "stats": {"laufzeit": {"langsamste": list(eintraege)}}}, indent=1))

    @staticmethod
    def preflight(dauer: float, parallel: int | None = 1) -> dict:
        e = {"name": "PowerShell", "dauer_s": dauer,
             "kurz": "python -u scripts/preflight.py before *> analysis\\_preflight.txt"}
        if parallel is not None:
            e["parallel"] = parallel
        return e

    def log_text(self) -> str:
        p = self.tmp / "log.jsonl"
        return p.read_text(encoding="utf-8") if p.is_file() else ""

    # ------------------------------------------------------------------ Faelle
    def test_einzelaufruf_wird_genommen(self):
        self.result(214, {"name": "PowerShell", "dauer_s": 5.0, "kurz": "Get-Date"},
                    self.preflight(600.0))
        d = stand.preflight_dauer(self.cfg, log=self.log)
        self.assertEqual(d["batch"], 214)
        self.assertAlmostEqual(d["minuten"], 10.0, places=2)
        self.assertEqual(d["parallel"], 1)
        self.assertEqual(d["uebersprungen"], [])

    def test_nur_parallel_gemessen_faellt_zurueck(self):
        """B212-Lage: der Preflight-Aufruf lief neben einem anderen -> nicht nehmen."""
        self.result(213, self.preflight(540.0))
        self.result(214, self.preflight(602.3, parallel=2))
        d = stand.preflight_dauer(self.cfg, log=self.log)
        self.assertEqual(d["batch"], 213, "der neueste saubere Batch zaehlt")
        self.assertAlmostEqual(d["minuten"], 9.0, places=2)
        self.assertEqual(d["uebersprungen"], [214])
        text = self.log_text()
        self.assertIn("B214 nur parallel gemessen", text)
        self.assertIn("uebersprungen", text)

    def test_paralleler_aufruf_im_selben_batch_zaehlt_nicht_mit(self):
        """Im selben Batch liegen ein paralleler UND ein einzelner Aufruf."""
        self.result(214, self.preflight(602.3, parallel=2),
                    self.preflight(540.0))
        d = stand.preflight_dauer(self.cfg, log=self.log)
        self.assertEqual(d["batch"], 214)
        self.assertAlmostEqual(d["minuten"], 9.0, places=2)
        self.assertEqual(d["uebersprungen"], [])

    def test_ohne_jede_gueltige_messung_kein_wert(self):
        self.result(214, self.preflight(602.3, parallel=3))
        self.assertIsNone(stand.preflight_dauer(self.cfg, log=self.log))
        self.assertIn("B214 nur parallel gemessen", self.log_text())

    def test_alteintrag_ohne_parallel_bleibt_gueltig(self):
        self.result(214, self.preflight(600.0, parallel=None))
        d = stand.preflight_dauer(self.cfg)
        self.assertEqual(d["batch"], 214)
        self.assertEqual(d["parallel"], 1)


class TestSchwelleUhrUndHook(unittest.TestCase):
    """Quelle der Messung bis in die BATCH-UHR (R13aj)."""

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13aj"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "harness")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["harness_home"] = str(self.tmp)
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def result(self, batch: int, dauer: float, parallel: int = 1) -> None:
        d = ensure_dir(self.root / "runs" / f"b{batch:03d}")
        write_text_atomic(d / "result.json", json.dumps({"stats": {"laufzeit": {
            "langsamste": [{"name": "PowerShell", "dauer_s": dauer, "parallel": parallel,
                            "kurz": "python -u scripts/preflight.py before"}]}}}, indent=1))

    def state(self):
        from hx import state as st
        s = st.State(self.root / "state" / "run.json")
        s.data["batch"] = 214
        s.data["worker"] = {"pid": 1,
                            "started_at": (datetime.now(timezone.utc)
                                           - timedelta(minutes=34)).isoformat(
                                               timespec="seconds")}
        s.data["live"] = {"batch": 214, "kontext": 310000}
        s.save()
        return s

    def test_schwelle_nennt_den_quellbatch(self):
        self.result(213, 600.0)
        self.result(214, 602.0, parallel=2)
        u = worker.umschalt_minuten(self.cfg, self.log)
        # R13be-3: die Schwelle haengt an der Alarmgrenze aus der Config (150 min -> 135),
        # hier mit gemessenem Vorlauf 15 min - keine zweite feste Zahl im Test.
        weich = float(self.cfg.get("limits", "alarm_wall_s")) / 60.0
        self.assertEqual(u["preflight_batch"], 213)
        self.assertAlmostEqual(u["preflight_min"], 10.0, places=2)
        self.assertAlmostEqual(u["umschalt_min"], weich - 15.0, places=2)

    def test_uhr_zeigt_die_quelle(self):
        text = uhr.uhr_text(self.state().data, 90, 180, umschalt_min=75,
                            kontext_limit=1000000, preflight_min=10.0,
                            preflight_batch=213)
        self.assertIn("Preflight zuletzt ~10 min (B213)", text)
        ohne = uhr.uhr_text(self.state().data, 90, 180, umschalt_min=75,
                            kontext_limit=1000000, preflight_min=10.0)
        self.assertIn("Preflight zuletzt ~10 min", ohne)
        self.assertNotIn("(B213)", ohne)

    def test_hook_uebergibt_den_batch(self):
        self.result(213, 600.0)
        ziel = worker.write_worker_hooks(self.cfg, self.root / "runs" / "b214",
                                         self.state().path, self.log)
        args = json.loads(Path(ziel).read_text(encoding="utf-8"))[
            "hooks"]["PostToolUse"][0]["hooks"][0]["args"]
        self.assertEqual(args[args.index("--preflight-batch") + 1], "213")

    def test_hookskript_schreibt_die_quelle_in_die_zeile(self):
        state_datei = self.state().path
        p = subprocess.run([sys.executable, str(ROOT / "tools" / "batch_uhr.py"),
                            "--state", str(state_datei), "--weich", "90", "--hart", "180",
                            "--umschalt", "75", "--preflight-min", "10.0",
                            "--preflight-batch", "213", "--kontext-limit", "1000000"],
                           input=b"{}", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=120)
        self.assertEqual(p.returncode, 0, p.stderr.decode("utf-8", "replace")[:200])
        txt = json.loads(p.stdout.decode("utf-8"))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Preflight zuletzt ~10 min (B213)", txt)

    def test_vorspann_erklaert_die_klammer(self):
        pre = worker.WORKER_PREAMBLE
        self.assertIn("Preflight zuletzt ~<p> min (B<k>)", pre)
        self.assertIn("die Zahl ist dann die letzte saubere Messung", pre)


class TestReviewerRegelLangeBefehle(unittest.TestCase):
    """Der Reviewer verlangt die langen Aufrufe blockierend (R13aj, Nachtrag).

    Nur ein blockierender Aufruf ist messbar - seine Dauer ist die Zahl, um die die
    Umschaltschwelle vorgezogen wird. Im Hintergrund gemessen enthaelt sie die Wartezeit
    des Nachbaraufrufs und wird verworfen (`parallel > 1`, s. o.).
    """

    def setUp(self):
        self.p = ROOT / "prompts" / "reviewer.md"
        if not self.p.is_file():
            self.skipTest("prompts/reviewer.md fehlt")
        self.text = self.p.read_text(encoding="utf-8")

    def test_abschnitt_existiert(self):
        self.assertIn("## Lange Befehle (R13aj, 2026-09-29)", self.text)

    def test_die_drei_aufrufe_und_der_parameter(self):
        abschnitt = self.text.split("## Lange Befehle")[1].split("\n## ")[0]
        self.assertIn("timeout=3600000", abschnitt)
        for name in ("Preflight", "c_kopf.py mutalle", "port_build"):
            self.assertIn(name, abschnitt)
        self.assertIn("Nicht** per `Start-Process`", abschnitt)

    def test_begruendung_ist_die_messbarkeit(self):
        abschnitt = self.text.split("## Lange Befehle")[1].split("\n## ")[0]
        self.assertIn("messbar", abschnitt)
        self.assertIn("Umschaltschwelle", abschnitt)
        self.assertIn("Warteschleifen", abschnitt)

    def test_vorspann_sagt_dasselbe(self):
        """Die Regel steht auch im Worker-Vorspann - beide Seiten nennen 3600000."""
        self.assertIn("timeout=3600000` setzen; sonst wird nach 600 s gekappt",
                      worker.WORKER_PREAMBLE)


class TestEchterMitschnitt(unittest.TestCase):
    """Regressionspflock am echten B212-Mitschnitt (nur lesend, R13aj).

    Belegt die Ursache: `stream.jsonl:14789` (PowerShell) und `:14790` (Grep) starten mit
    demselben Zeitstempel; erst bei `:14814/14815` kommen die Ergebnisse. Der Grep wird
    deshalb mit `parallel = 2` gekennzeichnet und darf nicht als Preflight-Dauer dienen.
    Der Ausschnitt reicht von ein paar Zeilen davor bis hinter die beiden Ergebnisse - die
    ganze 22-MB-Datei muss dafuer nicht gelesen werden.
    """

    def setUp(self):
        self.cfg = load_config()
        self.p = Path(self.cfg.root) / "runs" / "b212" / "stream.jsonl"

    def test_b212_grep_paar_traegt_parallel_zwei(self):
        if not self.p.is_file():
            self.skipTest("runs/b212/stream.jsonl fehlt")
        zeilen: list[str] = []
        with open(self.p, encoding="utf-8", errors="replace") as fh:
            for i, z in enumerate(fh, 1):
                if i < 14786:
                    continue
                if i > 14816:
                    break
                zeilen.append(z)
        s = _stats(zeilen)
        lang = {str(e["kurz"]): e for e in s.laufzeit_profil()["langsamste"]}
        treffer = [e for e in lang.values() if e["name"] == "Grep"]
        self.assertTrue(treffer, "der Grep-Aufruf fehlt im Ausschnitt")
        self.assertEqual(treffer[0]["parallel"], 2)
        self.assertGreater(treffer[0]["dauer_s"], 500.0,
                           "die Ereignisdistanz misst hier die Wartezeit mit")
        pws = [e for e in lang.values() if e["name"] == "PowerShell"]
        self.assertTrue(pws, "der PowerShell-Aufruf fehlt im Ausschnitt")
        self.assertGreaterEqual(pws[0]["parallel"], 2,
                                "der gekappte Aufruf lief neben dem Grep")


if __name__ == "__main__":
    unittest.main()
