"""Tests fuer R13ao (2026-09-29, Auftrag Teil B): Hinweis bei zu fruehem Preflight.

**Auftrag.** Enthaelt ein Bash-Aufruf des Workers `preflight.py`, liegt die Batch-Uhr vor
der Umschaltschwelle UND traegt `auftrag.md` eine `NACHRUECKLISTE`
(`hx.worker.hat_nachrueckliste`), bekommt der Worker unmittelbar eine Hook-Nachricht mit
dem Wortlaut unten. **Nicht blockieren, nur hinweisen.** In `runs/b<N>/result.json`
stehen danach `preflight_laeufe` (Anzahl) und `preflight_frueh` (Anzahl vor der Schwelle
mit offener Nachrueckliste). Nur berichten: `preflight_laeufe` fuer B206-B215
(`docs/_r13ao_messung.txt`).

Warum: der Preflight liest den Stand, den der Batch gerade erst herstellt - laeuft er
vorher, muss er spaeter wiederholt werden und kostet dann doppelt (~10 min).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import streamjson, uhr, worker                          # noqa: E402
from hx.config import load_config                               # noqa: E402
from hx.util import Log, ensure_dir, write_text_atomic          # noqa: E402

# Der Wortlaut STEHT HIER ausgeschrieben (nicht aus `hx.uhr` geholt): nur so schlaegt
# dieser Test an, wenn jemand den Text aendert. X = Minuten seit Batch-Start,
# Y = Umschaltschwelle. (R13ap, 2026-09-30: "Umschwellschwelle" aus dem Auftrag wurde
# zu "Umschaltschwelle" korrigiert - so heisst das Ding auch sonst.)
HINWEIS = ("Preflight vor der Umschaltschwelle (42.0 von 80 min). Er ist nur zulässig, "
           "wenn alle Posten der NACHRUECKLISTE erledigt sind. Sonst erst die "
           "Nachrückliste abarbeiten; ein früher Preflight muss später wiederholt werden "
           "und kostet ~10 min.")

AUFTRAG_MIT_LISTE = """# Batch 999 - Test

## NACHRUECKLISTE (offen):
- (1) erster Posten
- (2) zweiter Posten

Sonst nichts.
"""

AUFTRAG_OHNE_LISTE = """# Batch 999 - Test

Der Auftrag nennt keine Nachrueckliste.
"""

PREFLIGHT_CMD = "python -u scripts/preflight.py before *> analysis/_preflight_999.txt"
BILANZ_CMD = "python -u scripts/m149_bilanz.py --batch 999"


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13ao"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "root")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(ensure_dir(self.tmp / "decomp"))
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- Hilfen ---------------------------------------------------------------------
    def hook(self, *, minuten: float = 42.0, umschalt: float = 80.0,
             auftrag: str | None = AUFTRAG_MIT_LISTE,
             eingabe: dict | None = None, mit_run: bool = True,
             batch: int = 999) -> tuple[Path, str]:
        """Den Hook so aufrufen, wie die Claude-CLI es tut (stdin-JSON, Rueckgabe-JSON)."""
        lauf = ensure_dir(self.root / "runs" / f"b{batch:03d}")
        if auftrag is not None:
            write_text_atomic(lauf / "auftrag.md", auftrag)
        state = self.root / "state" / "run.json"
        start = datetime.now(timezone.utc) - timedelta(minutes=minuten)
        write_text_atomic(state, json.dumps(
            {"worker": {"pid": 1, "started_at": start.isoformat(timespec="seconds")},
             "live": {"batch": batch}}))
        args = [sys.executable, str(ROOT / "tools" / "batch_uhr.py"),
                "--state", str(state), "--weich", "90", "--hart", "180",
                "--umschalt", f"{umschalt:.0f}", "--preflight-min", "10.0",
                "--preflight-batch", "214", "--kontext-limit", "1000000"]
        if mit_run:
            args += ["--run", str(lauf)]
        daten = eingabe if eingabe is not None else {
            "hook_event_name": "PostToolUse", "tool_name": "PowerShell",
            "tool_input": {"command": PREFLIGHT_CMD}}
        p = subprocess.run(args, input=json.dumps(daten).encode("utf-8"),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        self.assertEqual(p.returncode, 0, p.stderr.decode("utf-8", "replace")[:300])
        aus = json.loads(p.stdout.decode("utf-8"))
        return lauf, aus["hookSpecificOutput"]["additionalContext"]

    @staticmethod
    def zeilen(lauf: Path) -> list[dict]:
        p = Path(lauf) / "preflight-aufrufe.jsonl"
        if not p.is_file():
            return []
        return [json.loads(z) for z in p.read_text(encoding="utf-8").splitlines()
                if z.strip()]


# --------------------------------------------------------------- 1) Aufruf erkennen
class TestErkennung(unittest.TestCase):
    """Ein Preflight-Aufruf ist ein START (Interpreter + Skript), keine Erwaehnung.

    GEMESSEN in B206-B215 (`docs/_r13ao_messung.txt`): von 23 Treffern der reinen
    Textsuche waren nur 8 echte Starts - der Rest war `Select-String -Path
    scripts/preflight.py`, `git add … scripts/preflight.py` und die Ueberwachung des
    eigenen Laufs (`Get-CimInstance … -like '*preflight.py*before*'`).
    """

    def test_shell_mit_preflight_ist_ein_aufruf(self):
        for name in ("PowerShell", "Bash", "Shell", "Terminal"):
            self.assertTrue(streamjson.ist_preflight_aufruf(
                name, {"command": PREFLIGHT_CMD}), name)

    def test_uebliche_schreibweisen_zaehlen(self):
        for cmd in (
            "python -u scripts/preflight.py before *> analysis/_preflight_999.txt",
            r"cd 'g:\Silent Scope Decomp'; py -3 scripts/preflight.py before",
            r'$p = Start-Process -FilePath python -ArgumentList "-u",'
            r'"scripts/preflight.py","before" -RedirectStandardOutput out.txt',
            r"cd g:\Silent Scope Decomp; Get-Date; python -u scripts/preflight.py before; "
            r"Get-Content analysis/_preflight_999.txt | Select-Object -Last 30",
        ):
            self.assertTrue(streamjson.ist_preflight_aufruf("PowerShell", {"command": cmd}),
                            cmd[:60])

    def test_erwaehnung_ist_kein_start(self):
        """Die reine Textsuche nach dem Skript startet es nicht."""
        for cmd in (
            r"cd 'g:\Silent Scope Decomp'; Select-String -Path scripts/preflight.py "
            r"-Pattern 'selftest' -Context 1,4 | Select-Object -First 25",
            r"git add scripts/m114_matrix.py scripts/preflight.py scripts/m210_zensus.py",
            r"Get-Content scripts/preflight.py | Select-Object -First 20",
        ):
            self.assertFalse(streamjson.ist_preflight_aufruf("PowerShell", {"command": cmd}),
                             cmd[:60])
            self.assertTrue(streamjson.nennt_preflight_nur("PowerShell", {"command": cmd}))

    def test_ueberwachung_des_laufs_ist_kein_start(self):
        """`-like '*preflight.py*before*'` ueberwacht nur (B214)."""
        cmd = (r'$p = Get-CimInstance Win32_Process -Filter "Name='
               r"'" + r"'python.exe'" + r'" | Where-Object { $_.CommandLine -like '
               r"'*preflight.py*before*' }")
        self.assertFalse(streamjson.ist_preflight_aufruf("PowerShell", {"command": cmd}))
        self.assertTrue(streamjson.nennt_preflight_nur("PowerShell", {"command": cmd}))

    def test_read_und_grep_sind_keine_aufrufe(self):
        """Ein Ergebnis, das den Text zitiert, ist kein Aufruf."""
        self.assertFalse(streamjson.ist_preflight_aufruf(
            "Read", {"file_path": "C:/x/scripts/preflight.py"}))
        self.assertFalse(streamjson.ist_preflight_aufruf(
            "Grep", {"pattern": "preflight.py"}))
        self.assertFalse(streamjson.ist_preflight_aufruf(
            "Read", {"file_path": "a.md", "content": "… preflight.py …"}))

    def test_nur_description_zaehlt_nicht(self):
        """`description` nennt den Preflight oft, ohne ihn zu starten."""
        self.assertFalse(streamjson.ist_preflight_aufruf(
            "PowerShell", {"command": BILANZ_CMD,
                           "description": "danach preflight.py laufen lassen"}))

    def test_anderer_shell_befehl_ist_keiner(self):
        self.assertFalse(streamjson.ist_preflight_aufruf(
            "PowerShell", {"command": BILANZ_CMD}))

    def test_fehlende_eingabe_ist_kein_aufruf(self):
        for eingabe in (None, {}, "text", []):
            self.assertFalse(streamjson.ist_preflight_aufruf("PowerShell", eingabe))
        self.assertFalse(streamjson.ist_preflight_aufruf(None, {"command": PREFLIGHT_CMD}))


# ------------------------------------------------------------------- 2) Wortlaut
class TestWortlaut(unittest.TestCase):
    def test_wortlaut_ist_der_des_auftrags(self):
        self.assertEqual(uhr.preflight_hinweis(42.0, 80.0), HINWEIS)

    def test_zu_frueh_ist_nur_vor_der_schwelle(self):
        self.assertTrue(uhr.preflight_zu_frueh(42.0, 80.0))
        self.assertFalse(uhr.preflight_zu_frueh(80.0, 80.0))       # genau auf der Schwelle
        self.assertFalse(uhr.preflight_zu_frueh(85.0, 80.0))
        self.assertFalse(uhr.preflight_zu_frueh(42.0, None))       # ohne Schwelle: nichts
        self.assertFalse(uhr.preflight_zu_frueh(None, 80.0))       # ohne Messwert: nichts


# --------------------------------------------------------------- 3) Der Hook selbst
class TestHook(Basis):
    def test_frueher_preflight_mit_liste_bekommt_den_hinweis(self):
        lauf, text = self.hook()
        self.assertIn("BATCH-UHR", text, "die Uhr-Zeile bleibt")
        self.assertIn("PREFLIGHT-HINWEIS: ", text)
        self.assertIn(HINWEIS, text, "Wortlaut aus dem Auftrag")
        z = self.zeilen(lauf)
        self.assertEqual(len(z), 1)
        self.assertTrue(z[0]["frueh"])
        self.assertAlmostEqual(z[0]["min"], 42.0, delta=0.2)

    def test_nach_der_schwelle_kein_hinweis_aber_gezaehlt(self):
        """Später Preflight: erlaubt, kein Hinweis - gezaehlt wird er trotzdem."""
        lauf, text = self.hook(minuten=85.0)
        self.assertNotIn("PREFLIGHT-HINWEIS", text)
        z = self.zeilen(lauf)
        self.assertEqual(len(z), 1)
        self.assertFalse(z[0]["frueh"])

    def test_ohne_nachrueckliste_kein_hinweis(self):
        """Der Hinweis haengt an der offenen Nachrueckliste (Bedingung aus dem Auftrag)."""
        lauf, text = self.hook(auftrag=AUFTRAG_OHNE_LISTE)
        self.assertNotIn("PREFLIGHT-HINWEIS", text)
        z = self.zeilen(lauf)
        self.assertEqual(len(z), 1)
        self.assertFalse(z[0]["frueh"])

    def test_anderer_befehl_wird_nicht_gezaehlt(self):
        lauf, text = self.hook(eingabe={"hook_event_name": "PostToolUse",
                                        "tool_name": "PowerShell",
                                        "tool_input": {"command": BILANZ_CMD}})
        self.assertIn("BATCH-UHR", text)
        self.assertNotIn("PREFLIGHT-HINWEIS", text)
        self.assertEqual(self.zeilen(lauf), [], "kein Eintrag, kein Hinweis")

    def test_read_des_skripts_wird_nicht_gezaehlt(self):
        lauf, _ = self.hook(eingabe={"tool_name": "Read",
                                     "tool_input": {"file_path": "scripts/preflight.py"}})
        self.assertEqual(self.zeilen(lauf), [])

    def test_ohne_run_schalter_wird_nichts_behauptet(self):
        """Ein Lauf mit aelterer Einstellungsdatei (z. B. der laufende B216): still."""
        lauf, text = self.hook(mit_run=False)
        self.assertIn("BATCH-UHR", text)
        self.assertNotIn("PREFLIGHT-HINWEIS", text)
        self.assertFalse((Path(lauf) / "preflight-aufrufe.jsonl").exists())
        self.assertEqual(list(Path(self.root).rglob("preflight-aufrufe.jsonl")), [])

    def test_ohne_auftrag_kein_hinweis(self):
        """Fehlt `auftrag.md`, ist keine Nachrueckliste nachweisbar - nur zaehlen."""
        lauf, text = self.hook(auftrag=None)
        self.assertNotIn("PREFLIGHT-HINWEIS", text)
        self.assertEqual(len(self.zeilen(lauf)), 1)
        self.assertFalse(self.zeilen(lauf)[0]["frueh"])

    def test_zwei_aufrufe_ergeben_zwei_zeilen(self):
        """Die Zahl zaehlt AUFRUFE, nicht Laeufe."""
        self.hook()
        self.hook()
        self.assertEqual(len(self.zeilen(self.root / "runs" / "b999")), 2)


# ------------------------------------------------------------- 4) Zaehler + result.json
class TestZaehler(Basis):
    def test_ohne_datei_null(self):
        self.assertEqual(worker.zaehle_preflight_aufrufe(self.root / "runs" / "b001"),
                         (0, 0))

    def test_zaehlt_aufrufe_und_fruehe(self):
        rd = ensure_dir(self.root / "runs" / "b999")
        write_text_atomic(rd / "preflight-aufrufe.jsonl", "\n".join([
            json.dumps({"ts": "2026-09-29T21:00:00+00:00", "min": 20.0, "frueh": True}),
            json.dumps({"ts": "2026-09-29T21:30:00+00:00", "min": 50.0, "frueh": False}),
            json.dumps({"ts": "2026-09-29T22:00:00+00:00", "min": 80.0, "frueh": True}),
            "",                                  # Leerzeile
            '{"ts": "kaputt"',                   # halb geschriebene Zeile
        ]) + "\n")
        self.assertEqual(worker.zaehle_preflight_aufrufe(rd), (3, 2))

    def test_result_json_traegt_die_zahlen(self):
        """Ein frueher und ein spaeter Aufruf -> `preflight_laeufe=2, preflight_frueh=1`."""
        rd = ensure_dir(self.root / "runs" / "b999")
        write_text_atomic(rd / "preflight-aufrufe.jsonl", "\n".join([
            json.dumps({"ts": "2026-09-29T21:00:00+00:00", "min": 20.0, "frueh": True}),
            json.dumps({"ts": "2026-09-29T22:00:00+00:00", "min": 95.0, "frueh": False}),
        ]) + "\n")
        res = worker.WorkerResult()
        stats = streamjson.StreamStats()
        state = mock.Mock()
        state.data = {}
        with mock.patch("hx.worker.write_json_atomic") as schreiben, \
                mock.patch("hx.worker.write_snapshot", return_value=""):
            worker._finish_run(self.cfg, state, res, stats, 999, "none", self.log,
                               ghidra_save=False)
        nutzlast = schreiben.call_args[0][1]
        self.assertEqual(nutzlast.get("preflight_laeufe"), 2)
        self.assertEqual(nutzlast.get("preflight_frueh"), 1)

    def test_ohne_aufrufe_null_in_result_json(self):
        res = worker.WorkerResult()
        stats = streamjson.StreamStats()
        state = mock.Mock()
        state.data = {}
        with mock.patch("hx.worker.write_json_atomic") as schreiben, \
                mock.patch("hx.worker.write_snapshot", return_value=""):
            worker._finish_run(self.cfg, state, res, stats, 999, "none", self.log,
                               ghidra_save=False)
        nutzlast = schreiben.call_args[0][1]
        self.assertEqual(nutzlast.get("preflight_laeufe"), 0)
        self.assertEqual(nutzlast.get("preflight_frueh"), 0)


# ------------------------------------------------------------ 5) Verdrahtung im Harness
class TestVerdrahtung(unittest.TestCase):
    """Die Hook-Einstellungsdatei muss das Laufverzeichnis mitgeben (R13ao)."""

    def test_hook_einstellung_gibt_run_mit(self):
        ziel = Path(ROOT) / "tests" / "_tmp_r13ao_draht"
        shutil.rmtree(ziel, ignore_errors=True)
        rd = ensure_dir(ziel / "runs" / "b999")
        try:
            cfg = load_config()
            cfg.data["paths"]["root"] = str(ziel)
            pfad = worker.write_worker_hooks(cfg, rd, ziel / "state" / "run.json")
            self.assertTrue(pfad, "ohne Einstellungsdatei gibt es keinen Hook")
            daten = json.loads(Path(pfad).read_text(encoding="utf-8"))
            args = daten["hooks"]["PostToolUse"][0]["hooks"][0]["args"]
            self.assertIn("--run", args)
            self.assertEqual(args[args.index("--run") + 1], str(rd))
        finally:
            shutil.rmtree(ziel, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
