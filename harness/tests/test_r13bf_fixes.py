"""Tests fuer R13bf (2026-10-01): vier Harness-Fixes aus den Batches B230-B234.

**Teil B - Bilanz ohne Preflight (Aussensicht B234, Befund M234-1).** B234 brach ab,
bevor ein Preflight lief (`runs/b234/result.json`: `preflight_laeufe: 0`). Die Bilanz
fuehrte trotzdem „115 referenzgleich" - das war die **Soll-Spalte** des Batch-Dokuments
(`port-batch234-…md:49`). Zwei Aenderungen:

* `stand.ist_wert` liest keine Zelle mehr aus einer Spalte, die **Soll** heisst
  (Kopfzeile der Tabelle, `stand.tabellen_kopf`).
* `stand.kernzahlen` faellt fuer einen Batch **in der Preflight-Aera** ohne eigene
  `_preflight_<N>.txt` nicht mehr auf das Dokument zurueck: die Zeile traegt **keine**
  C-Zahl (`c_nicht_gemessen`), die Anzeige bleibt beim letzten gemessenen Stand, und
  `bilanz.gesamt_block` sagt „B<N> nicht gemessen".

Gefrorene Fixture: `tests/fixtures/stand_b234_luecke/` (echter Dokumentstand 10:51 +
`_preflight_233.txt`, **ohne** `_preflight_234.txt`).
"""

from __future__ import annotations

import inspect
import json
import os
import shutil
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import bilanz, stand, worker                                   # noqa: E402
from hx.config import load_config                                      # noqa: E402
from hx.util import Log, ensure_dir, write_text_atomic                 # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "stand_b234_luecke"
DOK = "port-batch234-c-ausgefuehrte-koepfe-2026-10-01.md"
# Der echte Dokumentausschnitt: Ist-Spalte 110, Soll-Spalte 115.
TABELLE = ("| Bilanzzeile | Ist (B233) | Soll (B234) | Begruendung |\n"
           "|---|---|---|---|\n"
           "| `C Koepfe` | 110 / 6187 / 0 | **115 / 6271 / 0** | +5 Koepfe |\n")


class Basis(unittest.TestCase):
    """Wegwerf-Repo mit der eingefrorenen Fixture; `cfg` zeigt darauf."""

    MIT_PREFLIGHT_234 = False

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13bf"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.dec = ensure_dir(self.tmp / "decomp")
        shutil.copytree(FIXTURE / "decomp" / "analysis", self.dec / "analysis")
        if self.MIT_PREFLIGHT_234:
            quelle = self.dec / "analysis" / "_preflight_233.txt"
            ziel = self.dec / "analysis" / "_preflight_234.txt"
            roh = quelle.read_bytes()
            ziel.write_bytes(roh.replace(b"110 / 6187 / 0", b"115 / 6271 / 0"))
        self.root = ensure_dir(self.tmp / "harness")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.dec)
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        self.cfg = cfg

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def reihe(self) -> dict:
        return {e["batch"]: e for e in stand.kernzahlen(self.cfg, 8)}


# ------------------------------------------------- 1) Soll-Spalte ist kein Wert
class TestSollSpalte(Basis):
    def test_ist_spalte_gewinnt_gegen_die_soll_spalte(self):
        """Der echte B234-Ausschnitt: 110 (Ist), nicht 115 (Soll)."""
        _nr, wert = stand.ist_wert(self.text(), stand._ETIKETT_CKOPF,
                                   stand._RE_ZAHL_CKOPF)
        self.assertEqual(wert, (110, 6187, 0))

    def test_nur_soll_spalte_ergibt_keinen_wert(self):
        """Rotprobe: steht der Wert NUR unter `Soll`, gibt es keinen Messwert."""
        text = ("| Bilanzzeile | Zaehlerdefinition | Soll (B234) |\n|---|---|---|\n"
                "| `C Koepfe` | registrierte Koepfe (`c_kopf.py`) | **115 / 6271 / 0** |\n")
        _nr, wert = stand.ist_wert(text, stand._ETIKETT_CKOPF, stand._RE_ZAHL_CKOPF)
        self.assertIsNone(wert)

    def test_ohne_kopfzeile_bleibt_die_alte_regel(self):
        """Eine Tabelle ohne Kopf/Trenner wird wie vorher gelesen (letzte Zahlzelle)."""
        text = ("| **`C Koepfe`** | 110 / 6187 / 0 | 115 / 6271 / 0 |\n")
        _nr, wert = stand.ist_wert(text, stand._ETIKETT_CKOPF, stand._RE_ZAHL_CKOPF)
        self.assertEqual(wert, (115, 6271, 0))

    def test_paket_e_soll_spalte_zaehlt_nicht(self):
        text = ("| Bilanzzeile | Ist (B233) | Soll (B234) |\n|---|---|---|\n"
                "| Paket E offen | 25 / 2011, Blaetter 20 / 1657 | "
                "**20 / 1655, Blaetter 17 / 1200** |\n")
        _nr, wert = stand.ist_wert(text, stand._ETIKETT_PAKET_E, stand._RE_ZAHL_PAKET_E)
        self.assertEqual(wert, (25, 2011, 20, 1657))

    def text(self) -> str:
        return (self.dec / "analysis" / DOK).read_text(encoding="utf-8")


# ------------------------------------------- 2) Luecke in der Preflight-Aera
class TestLuecke(Basis):
    def test_ohne_preflight_keine_c_zahl(self):
        r = self.reihe()
        self.assertNotIn("c_koepfe", r[234])
        self.assertNotIn("c_faelle", r[234])
        self.assertTrue(r[234]["c_nicht_gemessen"])
        self.assertEqual(r[234]["c_erwartet"], "_preflight_234.txt")

    def test_letzter_gemessener_stand_bleibt(self):
        r = self.reihe()
        self.assertEqual(r[233]["c_koepfe"], 110)
        self.assertEqual(r[233]["c_quelle"], "_preflight_233.txt")
        self.assertEqual(r[234].get("c_quelle"), None)

    def test_bilanz_nennt_die_luecke_und_bleibt_bei_110(self):
        zeilen = bilanz.gesamt_block(self.cfg)
        c_zeile = [z for z in zeilen if z.strip().startswith("C Koepfe referenzgleich")]
        self.assertEqual(len(c_zeile), 1)
        self.assertIn("110 Koepfe", c_zeile[0])
        self.assertIn("B233", c_zeile[0])
        self.assertNotIn("115", c_zeile[0])
        self.assertTrue(any("B234 nicht gemessen" in z for z in zeilen), zeilen)
        self.assertTrue(any("_preflight_234.txt" in z for z in zeilen), zeilen)
        self.assertTrue(any("Stand von B233" in z for z in zeilen), zeilen)

    def test_mit_preflight_ist_die_luecke_weg(self):
        """Rotprobe: liegt die Datei vor, wird gemessen - und zwar die Messung."""
        self._mit_datei()
        r = self.reihe()
        self.assertNotIn("c_nicht_gemessen", r[234])
        self.assertEqual(r[234]["c_koepfe"], 115)
        self.assertEqual(r[234]["c_quelle"], "_preflight_234.txt")
        zeilen = bilanz.gesamt_block(self.cfg)
        self.assertFalse(any("B234 nicht gemessen" in z for z in zeilen), zeilen)

    def test_alter_batch_ohne_aera_nutzt_die_ist_spalte(self):
        """Vor der Preflight-Aera bleibt der Dokumentweg (R13x) erhalten."""
        for p in (self.dec / "analysis").glob("_preflight_*.txt"):
            p.unlink()
        r = self.reihe()
        self.assertEqual(r[234]["c_koepfe"], 110)
        self.assertEqual(r[234]["c_quelle"], DOK)
        self.assertNotIn("c_nicht_gemessen", r[234])

    def _mit_datei(self) -> None:
        quelle = (self.dec / "analysis" / "_preflight_233.txt").read_bytes()
        (self.dec / "analysis" / "_preflight_234.txt").write_bytes(
            quelle.replace(b"110 / 6187 / 0", b"115 / 6271 / 0"))


class TestMitPreflight234(Basis):
    """Dieselbe Fixture MIT `_preflight_234.txt` - die Kennzahl kommt aus der Datei."""

    MIT_PREFLIGHT_234 = True

    def test_datei_schlaegt_das_dokument(self):
        r = self.reihe()
        self.assertEqual(r[234]["c_koepfe"], 115)
        self.assertEqual(r[234]["c_quelle"], "_preflight_234.txt")


# ------------------------------------- 3) Zweiter Preflight nach der Fortsetzung
class TestZweiterPreflight(unittest.TestCase):
    """R13bf Teil D (offene Frage aus dem Review von b233).

    Der Fortsetzungstext verlangt einen neuen Preflight nur, wenn seit dem letzten
    Preflight unter `port/` oder `scripts/` etwas geaendert wurde. Ohne Aenderung gilt der
    vorhandene Stand. Ist die Nachrueckliste schon erledigt, ist die Antwort
    `NACHRUECKLISTE ERLEDIGT` - und sonst nichts (der Satz steht deshalb ZULETZT).
    """

    def text(self, **kwargs) -> str:
        return worker.fortsetzungs_text(50.0, 300000, 150.0, 135.0, batch=234, **kwargs)

    def test_mit_aenderung_wird_der_neue_preflight_verlangt(self):
        t = self.text(preflight_erneut=True)
        self.assertIn("Nach der Nacharbeit neuer Preflight, der letzte gilt", t)
        self.assertNotIn("Kein neuer Preflight nötig", t)

    def test_ohne_aenderung_gilt_der_vorhandene(self):
        t = self.text(preflight_geprueft=True)
        self.assertIn("Kein neuer Preflight nötig, der vorhandene gilt", t)
        self.assertIn("port/ oder scripts/", t)
        self.assertNotIn("Nach der Nacharbeit neuer Preflight", t)

    def test_gilt_satz_erlaubt_weitere_arbeit_und_verlangt_danach_einen_preflight(self):
        """R13bp Punkt 2: der Gilt-Satz liess offen, ob unter port/scripts gearbeitet
        werden darf. Er sagt jetzt beides - die Arbeit ist ERLAUBT, und danach gilt ein
        neuer Preflight (der letzte)."""
        t = self.text(preflight_geprueft=True)
        self.assertIn("Weitere Arbeit unter port/ und scripts/ ist erlaubt; danach ein "
                      "neuer Preflight, der letzte gilt (R13bf).", t)
        # Der Erledigt-Satz steht weiterhin ZULETZT (er uebersteuert beide Preflight-Saetze).
        self.assertTrue(t.rstrip().endswith("kein Preflight und keine Bilanz."), t[-120:])

    def test_die_neuen_saetze_schliessen_sich_aus(self):
        neu = self.text(preflight_erneut=True)
        gilt = self.text(preflight_geprueft=True)
        self.assertIn("Nach der Nacharbeit neuer Preflight", neu)
        self.assertNotIn("Weitere Arbeit unter port/", neu)
        self.assertIn("Weitere Arbeit unter port/", gilt)
        self.assertNotIn("Nach der Nacharbeit neuer Preflight", gilt)

    def test_ohne_preflight_kein_preflight_satz(self):
        t = self.text()
        self.assertNotIn("neuer Preflight", t)
        self.assertNotIn("Kein neuer Preflight nötig", t)

    def test_erledigt_satz_steht_immer_zuletzt(self):
        """Auch nach dem Preflight-Satz - sonst haette er zwei Antworten zur Wahl."""
        for kwargs in ({}, {"preflight_erneut": True}, {"preflight_geprueft": True}):
            t = self.text(**kwargs)
            self.assertTrue(t.rstrip().endswith("kein Preflight und keine Bilanz."), t[-120:])
            self.assertIn("antworte nur mit NACHRUECKLISTE ERLEDIGT", t)
            self.assertNotIn("dem Commit-Hash. Nach der Nacharbeit", t)

    def test_mit_aenderung_aus_dem_echten_repo(self):
        """`aenderung_seit_preflight` liest Commits und nicht committete Dateien.

        Die Grenze ist der **Preflight-Start**: alles DANACH zaehlt. Geprueft wird
        deshalb mit drei Zeitpunkten (davor, dazwischen, danach).
        """
        b = RepoBasis()
        b.setUp()
        try:
            start = "2026-10-01T11:00:00+00:00"
            self.assertFalse(worker.aenderung_seit_preflight(b.cfg, start)["geaendert"])
            b.commit("analysis/doku.md", "nur Doku", zeit="2026-10-01T12:00:00+00:00")
            self.assertFalse(worker.aenderung_seit_preflight(b.cfg, start)["geaendert"],
                             "nur analysis/ zaehlt nicht")
            b.commit("port/src/x.cpp", "Kopf gebaut", zeit="2026-10-01T13:00:00+00:00")
            a = worker.aenderung_seit_preflight(b.cfg, start)
            self.assertTrue(a["geaendert"])
            self.assertIn("port/src/x.cpp", a["dateien"])
            self.assertTrue(a["commits"], a)
            # Nach allen Commits ist nichts mehr passiert.
            self.assertFalse(worker.aenderung_seit_preflight(
                b.cfg, "2026-10-01T14:00:00+00:00")["geaendert"])
        finally:
            b.tearDown()

    def test_nicht_committete_aenderung_zaehlt_nach_der_zeit(self):
        b = RepoBasis()
        b.setUp()
        try:
            p = ensure_dir(b.repo / "scripts") / "c_kopf.py"
            p.write_text("# neu\n", encoding="utf-8")
            # R13bl (02.10.2026): hier stand ein FESTER Zeitpunkt
            # (`2026-10-01T23:59:59+00:00`). Die Uhr hat ihn in der Nacht zum 02.10.
            # eingeholt - danach lag die Dateizeit JUENGER als der "Preflight" und der
            # Test war rot, ohne dass sich am Code etwas geaendert haette. Der Start
            # muss WIRKLICH in der Zukunft liegen, also relativ zu jetzt.
            spaeter = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(
                timespec="seconds")
            alt = worker.aenderung_seit_preflight(b.cfg, spaeter)
            self.assertFalse(alt["geaendert"], "Dateizeit liegt VOR dem Preflight")
            neu = worker.aenderung_seit_preflight(b.cfg, "2020-01-01T00:00:00+00:00")
            self.assertTrue(neu["geaendert"])
            self.assertTrue(any("nicht committet" in d for d in neu["dateien"]), neu)
        finally:
            b.tearDown()

    def test_ohne_zeitpunkt_im_zweifel_neu(self):
        roh = worker.aenderung_seit_preflight(None, "")
        self.assertTrue(roh["geaendert"])
        self.assertTrue(roh["unbekannt"])
        self.assertIn("kein Preflight-Zeitpunkt", roh["grund"])

    def test_letzter_preflight_start_kommt_aus_dem_mitschnitt(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13bf_d"
        shutil.rmtree(self.tmp, ignore_errors=True)
        root = ensure_dir(self.tmp / "harness")
        rd = ensure_dir(root / "runs" / "b234")
        write_text_atomic(rd / "stream.jsonl", "\n".join([
            json.dumps({"type": "assistant", "timestamp": "2026-10-01T10:00:00+00:00",
                        "message": {"content": [
                            {"type": "tool_use", "id": "p1", "name": "PowerShell",
                             "input": {"command": "python -u scripts/preflight.py before"}}]}}),
            json.dumps({"type": "assistant", "timestamp": "2026-10-01T11:00:00+00:00",
                        "message": {"content": [
                            {"type": "tool_use", "id": "p2", "name": "PowerShell",
                             "input": {"command": "python -u scripts/preflight.py before"}}]}}),
        ]) + "\n")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(root)
        try:
            self.assertEqual(worker.letzter_preflight_start(cfg, 234),
                             "2026-10-01T11:00:00+00:00")
            self.assertEqual(worker.letzter_preflight_start(cfg, 235), "")
        finally:
            shutil.rmtree(self.tmp, ignore_errors=True)

    def test_verdrahtung_im_lauf(self):
        quelle = inspect.getsource(worker.run_batch)
        self.assertIn("aenderung_seit_preflight(cfg, pf_start, log=log)", quelle)
        self.assertIn("letzter_preflight_start(cfg, batch, log)", quelle)
        self.assertIn("preflight_erneut=bool(pf_neu)", quelle)
        self.assertIn("preflight_geprueft=bool(hatte_preflight and not pf_neu)", quelle)
        self.assertIn('"preflight_neu": bool(pf_neu)', quelle)


# ------------------------------------ 4) Alte Aufwandsform wird nachgerechnet
class TestAlteAufwandsform(unittest.TestCase):
    """R13bf: `result.json` aus R13be-3 traegt die DREI-Teile-Form (ohne `fester_min`).

    Sie darf nicht als Zeile erscheinen (das waere `0 min fester Aufwand`) - der
    Rueckblick rechnet sie mit der neuen Definition nach.
    """

    def test_alte_form_wird_nachgerechnet(self):
        tmp = Path(ROOT) / "tests" / "_tmp_r13bf_alt"
        shutil.rmtree(tmp, ignore_errors=True)
        root = ensure_dir(tmp / "harness")
        rd = ensure_dir(root / "runs" / "b999")
        write_text_atomic(rd / "result.json", json.dumps(
            {"batch": 999, "duration_s": 1800.0,
             "finished_at": "2026-10-01T12:00:00+00:00",
             "aufwand": {"wand_min": 31.0, "startroutine_min": 1.0,
                         "preflight_min": 10.2, "arbeit_min": 19.8,
                         "preflight_pct": 32.9, "arbeit_pct": 63.9,
                         "erste_arbeit": "x", "letzter_preflight": "y",
                         "aufrufe": 5, "quelle": "zustand"}}))
        write_text_atomic(rd / "stream.jsonl", json.dumps(
            {"type": "assistant", "timestamp": "2026-10-01T11:31:00+00:00",
             "message": {"content": [
                 {"type": "tool_use", "id": "p1", "name": "PowerShell",
                  "input": {"command": "python -u scripts/preflight.py before"}}]}}) + "\n")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(root)
        cfg.data["paths"]["decomp"] = str(ensure_dir(tmp / "decomp"))
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        try:
            zeile = stand.aufwand_zeile(cfg, 999)[0]
            self.assertNotIn("fester Aufwand 0 min", zeile)
            self.assertIn("(Start aus result.json nachgerechnet)", zeile)
            self.assertIn("Preflight (1 Lauf/Laeufe", zeile)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class RepoBasis:
    """Ein echtes, kleines Git-Repo als `cfg.decomp` (Repo-Wache von `gitsafe.Git`).

    Warum ein eigenes Repo: `git` sucht seine Wurzel selbst - ein Tempordner INNERHALB
    des Harness-Repos wuerde sonst still am aeusseren Repo arbeiten (R13i-Fallstrick).
    Die Commit-Zeit kommt aus `GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE` in der Umgebung -
    `-c user.date` setzt nur den Autor, und `git log --since` nimmt den Committer.
    """

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13bf_repo"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.repo = ensure_dir(self.tmp / "decomp")
        self.git("init", "-q")
        self.commit("a.txt", "start", inhalt="eins\n", zeit="2026-10-01T09:00:00+00:00")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(ensure_dir(self.tmp / "harness"))
        cfg.data["paths"]["decomp"] = str(self.repo)
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def git(self, *args: str, zeit: str = "") -> str:
        env = dict(os.environ)
        if zeit:
            env["GIT_AUTHOR_DATE"] = zeit
            env["GIT_COMMITTER_DATE"] = zeit
        p = subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@example.invalid",
                            *args], cwd=self.repo, capture_output=True, text=True, env=env)
        return (p.stdout or "") + (p.stderr or "")

    def commit(self, pfad: str, betreff: str, inhalt: str | None = None,
               zeit: str = "") -> None:
        p = self.repo / pfad
        ensure_dir(p.parent)
        p.write_text(inhalt if inhalt is not None else f"# {betreff}\n", encoding="utf-8")
        self.git("add", "--", pfad)
        self.git("commit", "-q", "-m", betreff, zeit=zeit)


if __name__ == "__main__":
    unittest.main()
