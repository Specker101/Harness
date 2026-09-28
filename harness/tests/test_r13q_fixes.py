"""Tests fuer R13q: Live-Zahlen in /status und der Bilanz-Bericht (/bilanz).

Auftrag (Nutzer, 2026-09-27):
  a) `/status` zeigt Dauer UND Kosten des LAUFENDEN Batches - ohne den bis zu 32 MB
     grossen Mitschnitt zu lesen,
  b) `/bilanz [N]` zeigt die Aeste im Vergleich zu N Batches vorher (Vorgabe 1),
  c) oben eine Gesamtzeile zum Projektstand (Teil C: Koepfe und Insn gebaut/gesamt in
     Prozent, Programm-Inventar in Prozent),
  d) ein Kostenblock: DeepSeek-Kosten der letzten 24 Stunden, Anzahl Batches, dazu die
     Abo-Auslastung (Sitzung/Woche mit Reset-Zeit) aus `logs/rate-limit.json`,
  e) festes Format, Telegram-tauglich (Monospace-Block).

Alles im Attrappenbetrieb: kein Netz, keine API-Kosten, kein Ghidra.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import bilanz, retention, telegram                             # noqa: E402
from hx.config import load_config                                        # noqa: E402
from hx.orchestrator import Orchestrator                                 # noqa: E402
from hx.util import Log, ensure_dir, now_iso, write_json_atomic, write_text_atomic  # noqa: E402

# Ein echter Mitschnitt-Ausschnitt (wie in R13p) - daraus kommt die Abo-Auslastung.
RATE_INFO = {"status": "allowed",
             "overageStatus": "rejected",
             "unifiedWindows": {
                 "five_hour": {"utilization": 0.84, "resetsAt": 1790521200},
                 "seven_day": {"utilization": 0.65, "resetsAt": 1790658000}}}

# Zwei Bilanz-Schnappschuesse: R207 bewegt sich (+3), die Nachzuegler wandern.
ROWS_100 = {
    "2a-Kern": {"_text": "2a-Kern (1/0)", "gebaut": 1, "offen": 0},
    "327er-Pool": {"_text": "327er-Pool", "pct": 32.1, "s1": 105, "total": 327},
    "Audio 68K-Treiber": {"_text": "Audio", "insn_gebaut": 4627, "insn_gesamt": 7959,
                          "insn_offen": 1808, "koepfe_gebaut": 58, "koepfe_gesamt": 97},
    "Programm-Inventar": {"_text": "Programm-Inventar", "pct": 80.3, "s1": 1664,
                          "total": 2072},
    "R207 rueckwaerts": {"_text": "R207", "gebaut": 607, "named": 10926, "unnamed": 0,
                         "nz": 66, "nz_ziel": 30, "nz_a": 15, "nz_b": 6},
}
ROWS_101 = {
    "2a-Kern": dict(ROWS_100["2a-Kern"]),
    "327er-Pool": dict(ROWS_100["327er-Pool"]),
    "Audio 68K-Treiber": dict(ROWS_100["Audio 68K-Treiber"]),
    "Programm-Inventar": dict(ROWS_100["Programm-Inventar"]),
    "R207 rueckwaerts": {"_text": "R207", "gebaut": 610, "named": 10926, "unnamed": 0,
                         "nz": 66, "nz_ziel": 30, "nz_a": 6, "nz_b": 3},
}

# Die C-Zahlen stehen als Prosa in der Batch-Datei - mit Fettmarken und Umbruch.
BATCH_DOC = """# Batch 101

**1. Inventar (GEMESSEN).** 2072 Koepfe / 123771 Insn im Programm-Inventar,
davon **591 Koepfe / 28858 Insn** in der
Bau-Liste. **OFFEN: 1481 Koepfe /
94913 Insn.** Davon haben **664 Koepfe / 31690 Insn** keinen offenen Ruf.
"""


def _weg(p: Path) -> None:
    retention._weg(p)


def _git(cwd, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {r.stderr.strip()[:200]}")
    return (r.stdout or "").strip()


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__file__).resolve().parent / "_tmp_r13q"
        _weg(self.tmp)
        self.root = ensure_dir(self.tmp / "harness")
        self.decomp = ensure_dir(self.tmp / "decomp")
        self.ana = ensure_dir(self.decomp / "analysis")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.decomp)
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["telegram"]["allowlist_user_ids"] = []
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)
        self.orch = Orchestrator(cfg, self.log, mock=True,
                                 state_file=self.root / "state" / "run.json")
        self.gesagt: list[tuple[str, bool]] = []
        self.orch.say = lambda t, *a, **k: self.gesagt.append(
            (str(t), bool(k.get("mono") or (a[0] if a else False))))

    def tearDown(self):
        _weg(self.tmp)

    # ---------------------------------------------------------------- Fixture
    def fixture(self, batches=(100, 101), rows=None):
        """Schnappschuss, Batch-Dokument, Anker, Kostenlauf und Abo-Messung anlegen."""
        write_json_atomic(self.ana / "_bilanz_snapshot.json", {
            "batches": {str(b): {"rows": dict((rows or {}).get(b) or
                                              (ROWS_101 if b == 101 else ROWS_100)),
                                 "zusatz": {"faelle": 180, "r216a": 259, "r216b": 84,
                                            "r216c": 86, "r216d": 687, "reg_a": 271,
                                            "reg_f": 32}}
                         for b in batches}})
        write_text_atomic(self.ana / "port-batch101-rest24-2026-09-27.md", BATCH_DOC)
        write_text_atomic(self.ana / "r1b-workstream.md",
                          "# R1B\n\n**Stand:** BATCH 101 (2026-09-27) - Beispielstand\n"
                          "**Naechster Schritt:** C beginnen\n")
        rd = ensure_dir(self.root / "runs" / "b101")
        write_json_atomic(rd / "result.json", {"cost_usd": 0.25})
        write_text_atomic(rd / "reviewer.jsonl",
                          json.dumps({"type": "rate_limit_event",
                                      "rate_limit_info": RATE_INFO}) + "\n")
        write_json_atomic(self.root / "logs" / "rate-limit.json",
                          {"ts": now_iso(), "quelle": "Reviewer", "info": RATE_INFO,
                           "zeile": "Sitzung (5 h): 84 % | Woche (7 Tage): 65 %"})
        write_json_atomic(self.root / "state" / "run.json",
                          {"spent": {datetime.now(timezone.utc).date().isoformat(): 0.5},
                           "gate": {"instruction": "Auftrag: C beginnen"}})


# ------------------------------------------------------- a) Live-Zahlen in /status
class TestLiveZeile(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__file__).resolve().parent / "_tmp_r13q_live"
        _weg(self.tmp)
        self.root = ensure_dir(self.tmp / "harness")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.tmp / "decomp")
        cfg.data["telegram"]["allowlist_user_ids"] = []
        self.cfg = cfg
        self.orch = Orchestrator(cfg, Log(self.tmp / "log.jsonl", echo=False), mock=True,
                                 state_file=self.root / "state" / "run.json")

    def tearDown(self):
        _weg(self.tmp)

    def test_laufender_batch_zeigt_dauer_und_kosten(self):
        self.orch.state.data["worker"] = {"pid": 4711, "started_at": now_iso(),
                                          "log": "x", "session_id": "s"}
        self.orch.state.data["live"] = {"batch": 102, "ts": now_iso(), "requests": 184,
                                        "cost_usd": 0.2747, "input_miss": 245889,
                                        "cache_read": 45222144, "output": 170190}
        self.orch.state.save()
        zeile = self.orch.live_batch_zeile()
        self.assertIn("Laufender Batch 102", zeile)
        self.assertIn("seit", zeile)
        self.assertIn("184 Anfragen", zeile)
        self.assertIn("$0.2747", zeile)
        self.assertIn("245889 ein / 45222144 cache / 170190 aus", zeile)
        self.assertIn("Stand", zeile)
        self.assertIn("Laufender Batch 102", self.orch.status_text())

    def test_nach_dem_lauf_bleibt_der_letzte_stand(self):
        self.orch.state.data["live_letzte"] = {"batch": 101, "ts": now_iso(), "requests": 20,
                                              "cost_usd": 0.05}
        self.assertIn("Laufender Batch: keiner (letzter Batch 101: 20 Anfragen, $0.0500",
                      self.orch.live_batch_zeile())

    def test_ohne_zahlen_klare_meldung(self):
        self.assertIn("noch keine Live-Zahlen", self.orch.live_batch_zeile())

    def test_worker_finished_hebt_live_auf(self):
        self.orch.state.data["live"] = {"batch": 101, "ts": now_iso(), "requests": 20,
                                        "cost_usd": 0.05}
        self.orch.state.data["worker"] = {"pid": 1, "started_at": now_iso()}
        self.orch.state.worker_finished()
        self.assertIsNone(self.orch.state.data["live"])
        self.assertIsNone(self.orch.state.data["worker"])
        self.assertEqual(self.orch.state.data["live_letzte"]["requests"], 20)
        self.assertEqual(self.orch.state.data["live_letzte"]["batch"], 101)

    def test_live_schreiben_ist_gedrosselt(self):
        """Der Zustand darf nicht bei jeder Zeile geschrieben werden (R13h/R13q)."""
        quelle = (ROOT / "hx" / "worker.py")
        text = quelle.read_text(encoding="utf-8")
        self.assertIn("LIVE_SEKUNDEN = 15.0", text)
        self.assertIn("if jetzt - live_stand[0] < LIVE_SEKUNDEN:", text)
        # Nur im Takt-Block schreiben, nicht vor der Faelligkeitspruefung:
        self.assertLess(text.index("if not takt.faellig():"),
                        text.index("live_schreiben(t, cost)"))


# ------------------------------------------------------------ Monospace-Versand
class FakeTG(telegram.Telegram):
    def __init__(self):
        super().__init__("token", ["1"])
        self.calls: list[tuple[str, dict]] = []

    def call(self, method, params=None, timeout=40.0, grenze=None):
        self.calls.append((method, dict(params or {})))
        return {"ok": True}


class TestMonospace(unittest.TestCase):
    def test_jeder_teil_bekommt_eigene_zaeune(self):
        tg = FakeTG()
        lang = "\n".join(f"Zeile {i:04d} mit etwas Text darin" for i in range(400))
        self.assertTrue(tg.send(lang, mono=True))
        self.assertGreater(len(tg.calls), 1)
        for _methode, p in tg.calls:
            self.assertEqual(p["parse_mode"], "Markdown")
            self.assertTrue(p["text"].startswith("```\n"))
            self.assertTrue(p["text"].rstrip().endswith("```"))
            # Der umfasste Block bleibt unter der Telegram-Grenze von 4096 Zeichen.
            self.assertLessEqual(len(p["text"]), 4096)
        zusammen = "".join(p["text"].strip("`\n") for _m, p in tg.calls)
        for i in range(400):
            self.assertIn(f"Zeile {i:04d}", zusammen)

    def test_backticks_werden_entschaerft(self):
        tg = FakeTG()
        tg.send("Ast `FUN_8005471C` ist gebaut", mono=True)
        text = tg.calls[0][1]["text"]
        self.assertNotIn("`FUN_8005471C`", text)
        self.assertEqual(text.count("`"), 6)          # genau die zwei Zaeune
        self.assertIn("FUN_8005471C", text)

    def test_ohne_mono_unveraendert(self):
        tg = FakeTG()
        tg.send("einfacher Text")
        _m, p = tg.calls[0]
        self.assertNotIn("parse_mode", p)
        self.assertEqual(p["text"], "einfacher Text")

    def test_leerer_mono_text_sendet_nichts(self):
        tg = FakeTG()
        self.assertFalse(tg.send("   ", mono=True))
        self.assertEqual(tg.calls, [])


# ------------------------------------------------------------- Bilanz-Bericht
class TestBilanz(Basis):
    def test_vollstaendiger_bericht(self):
        self.fixture()
        text = bilanz.bericht(self.cfg, n=1)
        self.assertIn("BILANZ Batch 101", text)
        self.assertIn("BILANZ Batch 101 gegen 100", text)
        self.assertIn("(Abstand 1)", text)
        # Ast-Tabelle mit Vorher/Jetzt und Delta
        self.assertIn("Ast", text)
        self.assertIn("R207 rueckwaerts", text)
        self.assertIn("607 gebaut", text)
        self.assertIn("610 gebaut", text)
        self.assertIn("+3", text)
        self.assertIn("check 610/10926/0, NZ 66/30 (6/3)", text)
        self.assertIn("vorher: check 607/10926/0, NZ 66/30 (15/6)", text)
        self.assertIn("Geaendert: 1 von 5 Aesten", text)
        # Projektstand (Teil C) aus dem Batch-Dokument
        self.assertIn("2072 Koepfe / 123771 Insn", text)
        self.assertIn("591 Koepfe /  28858 Insn", text)
        self.assertIn("1481 Koepfe /  94913 Insn", text)
        self.assertIn("664 Koepfe / 31690 Insn", text)
        self.assertIn("1664 von 2072 = 80.3 %", text)
        # Kostenblock
        self.assertIn("$0.2500 aus 1 Batch(es)", text)
        self.assertIn("$0.5000 von $10.00", text)
        self.assertIn("Sitzung (5 h): 84 %", text)
        # Aufgaben
        self.assertIn("BATCH 101 (2026-09-27) - Beispielstand", text)
        self.assertNotIn("`", text)          # nichts, was den Monospace-Block sprengt

    def test_vergleich_ohne_vorgaenger(self):
        """Der aelteste Batch hat keinen Vorgaenger - das muss dastehen, nicht raten."""
        self.fixture()
        text = bilanz.bericht(self.cfg, n=1, batch=100)
        self.assertIn("kein frueherer Batch vorhanden", text)
        self.assertIn("BILANZ Batch 100", text)

    def test_fehlender_batch_wird_uebersprungen(self):
        nummern = [148, 150, 153, 155]                   # 154 fehlt (echter Fall)
        self.assertEqual(bilanz.vergleichs_batch(nummern, 155, 1), 153)
        self.assertEqual(bilanz.vergleichs_batch(nummern, 155, 5), 150)
        self.assertEqual(bilanz.vergleichs_batch(nummern, 155, 7), 148)
        self.assertIsNone(bilanz.vergleichs_batch(nummern, 148, 1))
        # Es wird NIE unter den aeltesten vorhandenen zurueckgegriffen - lieber
        # "kein frueherer Batch" als ein stiller Vergleich mit dem falschen.
        self.assertIsNone(bilanz.vergleichs_batch(nummern, 155, 20))
        self.assertIsNone(bilanz.vergleichs_batch([], 155, 1))

    def test_ohne_schnappschuss_keine_ausnahme(self):
        text = bilanz.bericht(self.cfg, n=1)
        self.assertIn("kein Bilanz-Schnappschuss gefunden", text)
        self.assertIn("GESAMT", text)
        self.assertIn("KOSTEN", text)

    def test_prozentzeile_kommt_aus_dem_schnappschuss(self):
        self.fixture()
        self.assertIn("1664 von 2072 = 80.3 %", bilanz.inventar_prozent(self.cfg))

    def test_werte_sind_kurz_und_details_extra(self):
        kurz, zahl = bilanz.wert(ROWS_100["Audio 68K-Treiber"])
        self.assertEqual(kurz, "Insn 4627/7959")
        self.assertEqual(zahl, 4627.0)
        det = bilanz.detail(ROWS_100["Audio 68K-Treiber"])
        self.assertIn("Koepfe 58/97", det)
        self.assertIn("offen 1808 Insn", det)
        # Nichts wird mitten im Wort abgeschnitten (Fehler im ersten Anlauf).
        self.assertNotIn("..", kurz)
        self.assertNotIn("..", det)
        self.assertEqual(bilanz.detail(ROWS_100["327er-Pool"]), "")

    def test_bilanz_bericht_ist_monospace_sicher(self):
        """Der Bericht enthaelt keine Backticks - sonst zerreisst der Block."""
        self.fixture()
        write_text_atomic(self.ana / "port-batch101-x.md",
                          BATCH_DOC + "\nEin Pfad `a/b/c` im Text.\n")
        self.assertNotIn("`", bilanz.bericht(self.cfg, n=1))

    def test_git_betreffe_werden_gelesen(self):
        self.fixture()
        _git(self.decomp, "init", "-q")
        _git(self.decomp, "config", "user.email", "t@example.invalid")
        _git(self.decomp, "config", "user.name", "Test")
        write_text_atomic(self.decomp / "a.txt", "1\n")
        _git(self.decomp, "add", "a.txt")
        _git(self.decomp, "commit", "-q", "-m", "B101: Beispielauftrag")
        write_text_atomic(self.decomp / "b.txt", "2\n")
        _git(self.decomp, "add", "b.txt")
        _git(self.decomp, "commit", "-q", "-m", "B102: naechster Schritt")
        text = bilanz.bericht(self.cfg, n=1)
        self.assertIn("Letzte Batches (git):", text)
        self.assertIn("B101: Beispielauftrag", text)
        self.assertIn("B102: naechster Schritt", text)


# ------------------------------------------------------------ Telegram-Befehl
class TestBefehl(Basis):
    def test_bilanz_befehl_ist_monospace(self):
        self.fixture()
        self.assertTrue(self.orch.handle_command("/bilanz"))
        text, mono = self.gesagt[-1]
        self.assertTrue(mono)
        self.assertIn("BILANZ Batch 101", text)

    def test_bilanz_mit_abstand(self):
        """`/bilanz 5` gibt den Abstand wirklich weiter (und sendet Monospace)."""
        from unittest import mock
        self.fixture()
        gesehen: dict = {}

        def falsch(cfg, n=1, **kw):
            gesehen["n"] = n
            return "BILANZ (Testbericht)"

        with mock.patch.object(bilanz, "bericht", falsch):
            self.assertTrue(self.orch.handle_command("/bilanz 5"))
        self.assertEqual(gesehen["n"], 5)
        self.assertIn("BILANZ (Testbericht)", self.gesagt[-1][0])
        self.assertTrue(self.gesagt[-1][1])          # mono=True

    def test_bilanz_mit_unsinn_zeigt_nutzung(self):
        self.assertTrue(self.orch.handle_command("/bilanz abc"))
        self.assertIn("Nutzung: /bilanz", self.gesagt[-1][0])
        self.assertFalse(self.gesagt[-1][1])

    def test_hilfe_kennt_bilanz(self):
        self.assertIn("/bilanz", telegram.HELP)

    def test_cli_parser_kennt_bilanz_mit_n(self):
        from hx.cli import build_parser
        args = build_parser().parse_args(["bilanz"])
        self.assertEqual(args.n, 1)
        self.assertEqual(build_parser().parse_args(["bilanz", "--n", "5"]).n, 5)

    def test_cli_bilanz_gibt_bericht_aus(self):
        import io
        from contextlib import redirect_stdout
        from unittest import mock
        from hx.cli import cmd_bilanz
        self.fixture()
        args = type("A", (), {"config": None, "n": 2})()
        puffer = io.StringIO()
        # Die Konfiguration wird gepatcht - der Befehl soll den FIXTURE-Stand lesen,
        # nicht das echte Repo (sonst haengt der Test an echten Batch-Nummern).
        with mock.patch("hx.cli.load_config", return_value=self.cfg):
            with redirect_stdout(puffer):
                rc = cmd_bilanz(args)
        self.assertEqual(rc, 0)
        self.assertIn("BILANZ Batch 101", puffer.getvalue())


if __name__ == "__main__":
    unittest.main()
