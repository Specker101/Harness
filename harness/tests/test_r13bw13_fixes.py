"""Tests fuer R13bw-13 (07.10.2026): S1 (Sperre nur bei OFFENER Nachrueckliste) und S2
(keine neuen Hybrid-Langlaeufe ab Marker oder Schwelle minus 30 min).

**Auftrag (Nutzer, Harness-Wartung).** „S1: Die Preflight-Sperre
(`tools/batch_uhr.py:_nachrueckliste_offen`) soll nicht mehr pruefen, ob der Auftrag eine
NACHRUECKLISTE hat, sondern ob sie noch OFFEN ist (Marker `NACHRUECKLISTE ERLEDIGT` in der
Worker-Antwort, vorhandene Logik `hx/worker.py:745`). Ist sie erledigt, faellt die
Preflight-Sperre; der Preflight ist dann sofort erlaubt. Gleichzeitig gilt: nach dem Marker
keine neuen Hybrid-Langlaeufe (S2 nur fuer `hybrid_lauf`, `port_regression`,
`m2*_lang*.py` ab Marker oder ab Schwelle minus 30 min, kurze Formen per `--schritte < N`
frei)." Beleg: `runs/b282/stream.jsonl:55860/55861`.

Der Marker zaehlt **nur als Aeusserung des Workers** (Antwortdatei oder `text`-Block des
laufenden Mitschnitts) - `thinking` ist Erwaegung, `user` ist die Anweisung selbst
(`ERLEDIGT_TEXT`). GEMESSEN: `b282/stream.jsonl:55860` = `thinking`,
`b289/stream.jsonl:93228` = `thinking`, `b218/stream.jsonl:104073` = `text`.

Alles ohne API-Kosten in Wegwerf-Verzeichnissen (`tests/_tmp_r13bw13*`); das laufende
Harness-Verzeichnis wird NICHT angefasst.
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

from hx import streamjson, worker                                 # noqa: E402
from hx.config import load_config                                 # noqa: E402
from hx.util import ensure_dir, write_text_atomic                 # noqa: E402

MARKER = "NACHRUECKLISTE ERLEDIGT"
# Der Aufruf, wie ihn B284 fuhr (zweistufig: Name in der Zuweisung, Start ueber `& $exe`).
ZWEI_STUFEN = ('$kal="G:\\Silent Scope Decomp\\analysis\\_m231\\_tb_kalibrierung.txt"\n'
               '$exe="G:\\Silent Scope Decomp\\port\\build\\hybrid_lauf.exe"\n'
               '& $exe --schritte 900000000 --nativ-weiter --sharc-antwort')


def shell(command: str) -> dict:
    return {"tool_input": {"command": command}, "tool_name": "PowerShell"}


# ------------------------------------------------- 1) Erkennung der Langlaeufe
class TestErkennung(unittest.TestCase):
    def lang(self, command: str, name: str = "PowerShell") -> str:
        return streamjson.langlauf_aufruf(name, {"command": command})

    def test_lange_formen_zaehlen(self):
        for c in ("& .\\port\\build\\hybrid_lauf.exe --schritte 900000000 --nativ-weiter",
                  '$exe="G:\\Silent Scope Decomp\\port\\build\\hybrid_lauf.exe"; & $exe '
                  "--schritte 900000000 --nativ-weiter",
                  "python -u scripts/m289_lang.py 0 900000000",
                  ".\\port\\build\\port_regression.exe",
                  "& port\\build\\hybrid_lauf.exe --nativ-weiter"):
            with self.subTest(command=c):
                self.assertTrue(self.lang(c), c)

    def test_zweistufiger_aufruf_aus_b284(self):
        self.assertEqual(self.lang(ZWEI_STUFEN), "hybrid_lauf.exe")

    def test_kurze_formen_bleiben_frei(self):
        for c in ("& .\\port\\build\\hybrid_lauf.exe --schritte 2000000 --nativ-weiter",
                  '& $exe --schritte 20000000 --kalibrierung x.txt',
                  "python scripts/m289_lang.py --schritte 100000000"):
            with self.subTest(command=c):
                self.assertEqual(self.lang(c), "", c)

    def test_erwaehnung_ist_kein_start(self):
        for c in ("Get-Item port\\build\\hybrid_lauf.exe | Select-Object Name, Length",
                  "Get-CimInstance Win32_Process -Filter \"Name='hybrid_lauf.exe'\"",
                  "Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR "
                  "Name='hybrid_lauf.exe'\" | Select-Object ProcessId",
                  "Select-String -Path Makefile -Pattern 'hybrid_lauf|hybrid'",
                  "git add port/hybrid/hybrid_lauf.cpp scripts/m289_lang.py",
                  "python -c \"import sys; sys.path.insert(0,'scripts'); import m282_lang\"",
                  "Get-Content port\\hybrid\\hybrid_lauf.cpp | Measure-Object -Line"):
            with self.subTest(command=c):
                self.assertEqual(self.lang(c), "", c)

    def test_anderer_befehl_ist_keiner(self):
        self.assertEqual(self.lang("python -u scripts/preflight.py before"), "")
        self.assertEqual(self.lang("& .\\port\\build\\port_selftest.exe"), "")
        self.assertEqual(self.lang("python scripts/m289_pegel.py aus.txt"), "")

    def test_nur_das_shell_werkzeug_zaehlt(self):
        self.assertTrue(streamjson.langlauf_aufruf(
            "PowerShell", {"command": "& .\\port\\build\\hybrid_lauf.exe --schritte 900000000"}))
        self.assertEqual(streamjson.langlauf_aufruf(
            "Read", {"command": "& .\\port\\build\\hybrid_lauf.exe --schritte 900000000"}), "")
        self.assertEqual(streamjson.langlauf_aufruf("PowerShell"), "")


# ------------------------------------------------- 2) Der Marker (nur Worker-Aeusserungen)
class TestMarker(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13bw13_marker"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.lauf = ensure_dir(self.tmp / "runs" / "b999")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    @staticmethod
    def _zeile(typ: str, block_typ: str, text: str) -> str:
        if typ == "user":
            return json.dumps({"type": "user", "message": {"content": [{"type": "text",
                                                                      "text": text}]}})
        return json.dumps({"type": typ, "message": {"content": [{"type": block_typ,
                                                                "text": text}]}})

    def test_antwortdatei_traegt_den_marker(self):
        write_text_atomic(self.lauf / "antwort.md",
                          "NACHRUECKLISTE ERLEDIGT - je Posten der Commit-Hash:\n"
                          "  (1) 1234567\n")
        self.assertEqual(worker.nachrueckliste_marker(self.lauf), "antwort.md")

    def test_fortsetzungsantwort_traegt_den_marker(self):
        write_text_atomic(self.lauf / "antwort-forts1.md", f"…\n{MARKER}\n")
        self.assertEqual(worker.nachrueckliste_marker(self.lauf), "antwort-forts1.md")

    def test_textblock_im_laufenden_mitschnitt_zaehlt(self):
        write_text_atomic(self.lauf / "stream.jsonl",
                          self._zeile("assistant", "text", f"Alles fertig.\n{MARKER}\n") + "\n")
        self.assertEqual(worker.nachrueckliste_marker(self.lauf), "stream.jsonl (text)")

    def test_denkblock_zaehlt_nicht(self):
        """Gemessen: B282:55860 und B289:93228 sind `thinking` - Erwaegung, kein Ergebnis."""
        write_text_atomic(self.lauf / "stream.jsonl",
                          self._zeile("assistant", "thinking",
                                      f"Ich soll mit {MARKER} antworten?") + "\n")
        self.assertEqual(worker.nachrueckliste_marker(self.lauf), "")

    def test_anweisung_im_mitschnitt_zaehlt_nicht(self):
        """Die ANWEISUNG enthaelt den Wortlaut selbst (`worker.ERLEDIGT_TEXT`)."""
        from hx.worker import ERLEDIGT_TEXT
        write_text_atomic(self.lauf / "stream.jsonl",
                          self._zeile("user", "text", "…" + ERLEDIGT_TEXT) + "\n")
        self.assertEqual(worker.nachrueckliste_marker(self.lauf), "")

    def test_werkzeugaufruf_zaehlt_nicht(self):
        write_text_atomic(self.lauf / "stream.jsonl", json.dumps(
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "PowerShell",
                 "input": {"command": f'git commit -m "{MARKER}"'}}]}}) + "\n")
        self.assertEqual(worker.nachrueckliste_marker(self.lauf), "")

    def test_kleinschreibung_zaehlt_auch(self):
        write_text_atomic(self.lauf / "antwort.md", "nachrueckliste erledigt\n")
        self.assertEqual(worker.nachrueckliste_marker(self.lauf), "antwort.md")

    def test_ohne_lauf_kein_marker(self):
        self.assertEqual(worker.nachrueckliste_marker(None), "")
        self.assertEqual(worker.nachrueckliste_marker(self.tmp / "gibtsnicht"), "")


# ------------------------------------------------------------ 3) Der Hook selbst
AUFTRAG = "# Auftrag\n\n## NACHRUECKLISTE\n\n1. Posten eins\n2. Posten zwei\n"


class TestHook(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13bw13_hook"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "root")
        self.lauf = ensure_dir(self.root / "runs" / "b999")
        self.state = self.root / "state" / "run.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def hook(self, command: str, minuten: float = 40.0, umschalt: float = 135.0,
             marker: bool = False, auftrag: str | None = AUFTRAG) -> dict:
        if auftrag is not None:
            write_text_atomic(self.lauf / "auftrag.md", auftrag)
        if marker:
            write_text_atomic(self.lauf / "antwort.md", f"{MARKER}\n")
        start = datetime.now(timezone.utc) - timedelta(minutes=minuten)
        write_text_atomic(self.state, json.dumps(
            {"worker": {"pid": 1, "started_at": start.isoformat(timespec="seconds")},
             "live": {"batch": 999}}))
        args = [sys.executable, str(ROOT / "tools" / "batch_uhr.py"),
                "--state", str(self.state), "--umschalt", f"{umschalt:.0f}", "--pre",
                "--run", str(self.lauf)]
        daten = {"hook_event_name": "PreToolUse", "tool_name": "PowerShell",
                 "tool_input": {"command": command}}
        p = subprocess.run(args, input=json.dumps(daten).encode("utf-8"),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        self.assertEqual(p.returncode, 0, p.stderr.decode("utf-8", "replace")[:300])
        aus = p.stdout.decode("utf-8").strip()
        return json.loads(aus)["hookSpecificOutput"] if aus else {}

    def belege(self, name: str) -> list[dict]:
        p = self.lauf / name
        if not p.is_file():
            return []
        return [json.loads(z) for z in p.read_text(encoding="utf-8").splitlines()
                if z.strip()]

    PREFLIGHT = "python -u scripts/preflight.py before *> analysis/_preflight_999.txt"

    # --------------------------------------------------------------- S1
    def test_offene_liste_sperrt_den_fruehen_preflight(self):
        hoe = self.hook(self.PREFLIGHT, minuten=40.0)
        self.assertEqual(hoe.get("permissionDecision"), "deny")
        self.assertIn("PREFLIGHT-HINWEIS", hoe.get("permissionDecisionReason") or "")

    def test_marker_gibt_den_preflight_frei(self):
        """S1: erledigt = der Preflight ist SOFORT erlaubt (nicht erst an der Schwelle)."""
        hoe = self.hook(self.PREFLIGHT, minuten=40.0, marker=True)
        self.assertEqual(hoe, {}, "kein deny mehr")

    def test_ohne_nachrueckliste_bleibt_alles_wie_es_war(self):
        hoe = self.hook(self.PREFLIGHT, minuten=40.0, auftrag="# Auftrag\n\nKein Abschnitt\n")
        self.assertEqual(hoe, {})

    def test_marker_aus_dem_mitschnitt_gibt_frei(self):
        write_text_atomic(self.lauf / "stream.jsonl", json.dumps(
            {"type": "assistant", "message": {"content": [
                {"type": "text", "text": f"Erledigt.\n{MARKER}\n"}]}}) + "\n")
        self.assertEqual(self.hook(self.PREFLIGHT, minuten=40.0), {})

    # --------------------------------------------------------------- S2
    def test_langlauf_nach_dem_marker_wird_abgelehnt(self):
        hoe = self.hook("& .\\port\\build\\hybrid_lauf.exe --schritte 900000000",
                        minuten=40.0, marker=True)
        self.assertEqual(hoe.get("permissionDecision"), "deny")
        grund = hoe.get("permissionDecisionReason") or ""
        self.assertIn("LANGLAUF-HINWEIS", grund)
        self.assertIn("Nachrueckliste ist erledigt", grund)
        belege = self.belege("langlauf-blockiert.jsonl")
        self.assertEqual(len(belege), 1)
        self.assertEqual(belege[0]["skript"], "hybrid_lauf.exe")
        self.assertEqual(belege[0]["marker"], "antwort.md")

    def test_kurzer_langlauf_nach_dem_marker_bleibt_frei(self):
        self.assertEqual(self.hook("& .\\port\\build\\hybrid_lauf.exe --schritte 20000000",
                                   minuten=40.0, marker=True), {})

    def test_fenster_vor_der_schwelle_sperrt_auch_ohne_marker(self):
        hoe = self.hook("& .\\port\\build\\hybrid_lauf.exe --schritte 700000000",
                        minuten=110.0)
        self.assertEqual(hoe.get("permissionDecision"), "deny")
        self.assertIn("weniger als 30 min vor der Umschaltschwelle",
                      hoe.get("permissionDecisionReason") or "")

    def test_weit_vor_der_schwelle_bleibt_der_langlauflauf_frei(self):
        self.assertEqual(self.hook("& .\\port\\build\\hybrid_lauf.exe --schritte 700000000",
                                   minuten=40.0), {})

    def test_port_regression_hat_keine_schritte_und_gilt_als_lang(self):
        hoe = self.hook("python -u scripts/port_regression.py", minuten=110.0)
        self.assertEqual(hoe.get("permissionDecision"), "deny")
        self.assertIn("port_regression", hoe.get("permissionDecisionReason") or "")

    def test_andere_aufrufe_bleiben_unberuehrt(self):
        for c in ("Get-CimInstance Win32_Process -Filter \"Name='hybrid_lauf.exe'\"",
                  "& .\\port\\build\\port_selftest.exe",
                  "python -u scripts/preflight.py before"):
            with self.subTest(command=c):
                self.assertEqual(self.hook(c, minuten=110.0, marker=True), {}, c)


# ---------------------------------------------------------------- 4) Verdrahtung
class TestVerdrahtung(unittest.TestCase):
    def test_belegdatei_zaehlt_zu_den_laufbelegen(self):
        self.assertIn("langlauf-blockiert.jsonl", worker.LAUF_BELEGE)

    def test_grenzen_sind_benannt(self):
        from hx import streamjson as sj
        self.assertEqual(sj.LANGLAUF_FREI_SCHRITTE, 200_000_000,
                         "200M = ~2 min gemessen (900M ~ 533..543 s)")
        import importlib
        mod = importlib.import_module("batch_uhr") if False else None   # noqa: F841
        quelle = (ROOT / "tools" / "batch_uhr.py").read_text(encoding="utf-8")
        self.assertIn("LANGLAUF_VORLAUF_MIN = 30.0", quelle)


if __name__ == "__main__":
    unittest.main()
