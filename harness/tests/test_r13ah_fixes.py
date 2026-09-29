"""Tests fuer R13ah (2026-09-29): drei Harness-Fixes nach der Aussensicht B214.

**Befund 2 - Fortsetzung nach Preflight.** Die Fortsetzung laeuft im SELBEN Batch weiter.
Der Preflight-Stand von VOR der Fortsetzung wird deshalb unveraendert nach
`analysis/_m<N>/_preflight_<N>_vor_fortsetzung<k>.txt` kopiert und committet
(`B<N>: Preflight vor Fortsetzung archiviert`); der Fortsetzungstext beginnt mit der
Batch-Nummer, die aus dem Harness-Tag `harness/b<N>-start` kommt.

**Befund 3 - Zeitkappung.** `BASH_MAX_TIMEOUT_MS` stand auf `tool_timeout_ms` (600 s):
gemessen wurden preflight 602 s (B213), `mutalle` 601 s und preflight 602 s (B214), danach
Warteschleifen von 542 s. Jetzt `[claude] bash_max_timeout_s = 1800`, und die Batch-Uhr
nennt „Preflight zuletzt ~X min" - die Umschaltschwelle ist um diesen Vorlauf vorgezogen
(`Alarm − max(15 min, Preflight + 5 min)`).

**Befund 4 - B-Schritt-Ausloeser.** Das Feld `B-SCHRITT:` mass nichts (B212 2/5, B213 2/5,
waehrend der Hybrid-Lauf in B214 von 28/407 auf 448/42599 lief). Stillstand heisst jetzt:
in 3 B-Batches in Folge ist der Halt-PC (Feld 2 der Preflight-Zeile `Hybrid-Lauf`) gleich
**und** das Wegmass (Feld 4, Zaehler) steigt nicht.

Der laufende Batch wird nicht angefasst: alle Fixtures liegen in Wegwerfordnern unter
`tests/_tmp_r13ah*`, die echten Dateien werden nur GELESEN.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import aussensicht, envs, stand, uhr, worker               # noqa: E402
from hx.config import load_config                                  # noqa: E402
from hx.orchestrator import Orchestrator                           # noqa: E402
from hx.util import Log, ensure_dir, write_text_atomic             # noqa: E402

HYBRID = "Hybrid-Lauf        215 | 800138F0 | MMIO | 28/407 | 0                OK"


def hybrid(halt: str, weg: int, gesamt: int = 407, nr: str = "215",
           art: str = "MMIO", rest: str = "0") -> str:
    return (f"Hybrid-Lauf        {nr} | {halt} | {art} | {weg}/{gesamt} | {rest}"
            "                       OK")


class Basis(unittest.TestCase):
    """Wegwerf-Harness (`root`) + Wegwerf-Decomp-Repo (`decomp`, echtes Git-Repo)."""

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13ah"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "harness")
        self.decomp = ensure_dir(self.tmp / "decomp")
        self.ana = ensure_dir(self.decomp / "analysis")
        # Eigenes Repo MIT lokaler Identitaet: `archiviere_preflight_…` committet selbst.
        subprocess.run(["git", "init", "-q"], cwd=self.decomp, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"],
                       cwd=self.decomp, capture_output=True)
        subprocess.run(["git", "config", "user.email", "t@example.invalid"],
                       cwd=self.decomp, capture_output=True)
        write_text_atomic(self.decomp / "anfang.txt", "start\n")
        self._git("add", "anfang.txt")
        self._git("commit", "-q", "-m", "start")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.decomp)
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["paths"]["harness_home"] = str(self.tmp)
        cfg.data["paths"]["inbox"] = str(self.root / "inbox")
        cfg.data["telegram"]["allowlist_user_ids"] = []
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ------------------------------------------------------------------ Helfer
    def _git(self, *args: str) -> str:
        p = subprocess.run(["git", *args], cwd=self.decomp, capture_output=True, text=True)
        return (p.stdout or "") + (p.stderr or "")

    def git_subjects(self) -> list[str]:
        return [z for z in self._git("log", "--pretty=%s").splitlines() if z.strip()]

    def preflight(self, batch: int, *zeilen: str) -> Path:
        p = self.ana / f"_preflight_{batch}.txt"
        write_text_atomic(p, "=== PREFLIGHT (before) ===\n"
                             "C Koepfe           78 / 4006 / 0                     OK\n"
                             + "\n".join(zeilen) + "\n=> BEFORE SAUBER\n")
        return p

    def auftrag(self, batch: int, text: str) -> None:
        write_text_atomic(ensure_dir(self.root / "runs" / f"b{batch:03d}") / "auftrag.md",
                          text)

    def strang(self, batch: int, art: str) -> None:
        """Auftrag dieses Batches mit Pflichtzeile `STRANG: <art>` (Quelle 0)."""
        self.auftrag(batch, f"TEIL 1: bauen.\n\nSTRANG: {art}\n")

    def result_json(self, batch: int, preflight_s: float, andere: float = 100.0) -> None:
        d = ensure_dir(self.root / "runs" / f"b{batch:03d}")
        write_text_atomic(d / "result.json", json.dumps({
            "rc": 0, "duration_s": 600.0,
            "stats": {"laufzeit": {"langsamste": [
                {"name": "PowerShell", "dauer_s": andere, "kurz": "Get-Date; git status"},
                {"name": "PowerShell", "dauer_s": preflight_s,
                 "kurz": "python -u scripts/preflight.py before *> analysis\\_preflight.txt"},
            ]}}}, indent=1))

    def state(self, tag: str = "harness/b214-start", batch: int = 214):
        from hx import state as st
        s = st.State(self.root / "state" / "run.json")
        s.data["batch"] = int(batch)
        s.data["last_checkpoint"] = tag
        s.data["worker"] = {"pid": 1}
        s.save()
        return s


# ====================================== 1) Fortsetzung nach Preflight (Befund 2)
class TestPreflightArchiv(Basis):
    def test_archiviert_und_committet(self):
        quelle = self.preflight(214, HYBRID)
        s = self.state()
        ziel = worker.archiviere_preflight_vor_fortsetzung(self.cfg, s, 1, log=self.log)
        self.assertEqual(Path(ziel).name, "_preflight_214_vor_fortsetzung1.txt")
        self.assertEqual(Path(ziel).parent, self.ana / "_m214")
        self.assertEqual(Path(ziel).read_bytes(), quelle.read_bytes(),
                         "die Kopie ist UNVERAENDERT")
        self.assertEqual(Path(ziel).read_text(encoding="utf-8"),
                         quelle.read_text(encoding="utf-8"))
        self.assertIn("B214: Preflight vor Fortsetzung archiviert", self.git_subjects())
        # Der Kopf des Commits ist der einzige neue Eintrag (`git log -1` = neuester).
        self.assertEqual(self._git("log", "-1", "--pretty=%s").strip(),
                         "B214: Preflight vor Fortsetzung archiviert")

    def test_ohne_preflight_kein_archiv_und_kein_commit(self):
        s = self.state()
        vorher = self.git_subjects()
        self.assertEqual(worker.archiviere_preflight_vor_fortsetzung(self.cfg, s, 1,
                                                                     log=self.log), "")
        self.assertEqual(self.git_subjects(), vorher)
        self.assertFalse((self.ana / "_m214").exists())

    def test_batchnummer_kommt_aus_dem_tag_nicht_aus_state_batch(self):
        """`state.batch` sagt 99, der Harness-Tag sagt 214 - es gilt der Tag."""
        quelle = self.preflight(214, HYBRID)
        s = self.state(tag="harness/b214-start", batch=99)
        ziel = worker.archiviere_preflight_vor_fortsetzung(self.cfg, s, 2, log=self.log)
        self.assertEqual(Path(ziel).name, "_preflight_214_vor_fortsetzung2.txt")
        self.assertEqual(Path(ziel).read_bytes(), quelle.read_bytes())
        self.assertIn("B214: Preflight vor Fortsetzung archiviert", self.git_subjects())

    def test_zweite_fortsetzung_eigene_datei(self):
        self.preflight(214, HYBRID)
        s = self.state()
        e1 = worker.archiviere_preflight_vor_fortsetzung(self.cfg, s, 1, log=self.log)
        e2 = worker.archiviere_preflight_vor_fortsetzung(self.cfg, s, 2, log=self.log)
        self.assertNotEqual(e1, e2)
        self.assertTrue(Path(e1).is_file() and Path(e2).is_file())
        self.assertEqual(self.git_subjects().count(
            "B214: Preflight vor Fortsetzung archiviert"), 2)

    def test_ohne_tag_rueckfall_und_warnung(self):
        self.preflight(207, HYBRID)
        s = self.state(tag="", batch=207)
        ziel = worker.archiviere_preflight_vor_fortsetzung(self.cfg, s, 1, log=self.log)
        self.assertEqual(Path(ziel).name, "_preflight_207_vor_fortsetzung1.txt")

    def test_ohne_batchnummer_kein_archiv(self):
        s = self.state(tag="(kein Tag)", batch=0)
        self.assertEqual(worker.archiviere_preflight_vor_fortsetzung(self.cfg, s, 1,
                                                                     log=self.log), "")

    def test_lesefehler_ist_kein_absturz(self):
        """Fehlt das Repo, darf der Anstoss nicht scheitern (Rueckgabe "")."""
        cfg = load_config()
        cfg.data["paths"]["decomp"] = str(self.tmp / "gibtsnicht")
        s = self.state()
        self.assertEqual(worker.archiviere_preflight_vor_fortsetzung(cfg, s, 1,
                                                                     log=self.log), "")

    # ------------------------------------------------------- Fortsetzungstext
    def test_text_beginnt_mit_der_batchnummer(self):
        text = worker.fortsetzungs_text(34.0, 310000, 90.0, 75.0, batch=214)
        self.assertTrue(text.startswith("Du bist weiterhin in Batch 214. Alle Commits "
                                        "tragen B214:, nicht B215:."), text[:120])
        self.assertIn("Batch-Uhr: 34 von 90 min", text)
        self.assertIn("Umschaltschwelle 75 min nicht erreicht", text)

    def test_text_ohne_batch_hat_keinen_kopf(self):
        text = worker.fortsetzungs_text(34.0, 310000, 90.0, 75.0)
        self.assertFalse(text.startswith("Du bist weiterhin"))
        self.assertTrue(text.startswith("Batch-Uhr:"))

    def test_batch_aus_checkpoint(self):
        s = self.state(tag="harness/b213-start", batch=213)
        self.assertEqual(worker.batch_aus_checkpoint(s), 213)
        s.data["last_checkpoint"] = "irgendwas"
        s.data["batch"] = 212
        self.assertEqual(worker.batch_aus_checkpoint(s), 212)


# ========================================== 2) Zeitkappung (Befund 3)
class TestZeitkappung(unittest.TestCase):
    def test_max_ist_1800_default_bleibt_600(self):
        import os
        env = envs.worker_env(load_config(), dict(os.environ), "token")
        self.assertEqual(env["BASH_DEFAULT_TIMEOUT_MS"], "600000",
                         "ohne eigenes timeout gilt weiter die Vorgabe")
        self.assertEqual(env["BASH_MAX_TIMEOUT_MS"], "1800000",
                         "harte Obergrenze: 1800 s laut harness.toml")

    def test_config_wert_wird_benutzt(self):
        import os
        cfg = load_config()
        cfg.data.setdefault("claude", {})["bash_max_timeout_s"] = 900
        env = envs.worker_env(cfg, dict(os.environ), "token")
        self.assertEqual(env["BASH_MAX_TIMEOUT_MS"], "900000")

    def test_config_hat_den_schluessel_und_die_quelle_steht_in_envs(self):
        cfg = load_config()
        self.assertEqual(float(cfg.get("claude", "bash_max_timeout_s")), 1800.0)
        quelle = (ROOT / "hx" / "envs.py").read_text(encoding="utf-8").splitlines()
        treffer = [i for i, z in enumerate(quelle, 1)
                   if "BASH_MAX_TIMEOUT_MS" in z and "bash_max_timeout_s" in z]
        self.assertTrue(treffer, "BASH_MAX_TIMEOUT_MS haengt nicht an bash_max_timeout_s")
        self.assertIn("BASH_DEFAULT_TIMEOUT_MS", quelle[treffer[0] - 2],
                      "die Vorgabe steht direkt darueber (Zeile beider Zahlen)")


class TestPreflightDauer(Basis):
    def test_dauer_aus_dem_neuesten_batch(self):
        self.result_json(213, 602.0)
        d = stand.preflight_dauer(self.cfg)
        self.assertEqual(d["batch"], 213)
        self.assertAlmostEqual(d["minuten"], 10.03, places=2)
        self.assertIn("preflight.py", d["befehl"])

    def test_ohne_treffer_keine_messung(self):
        self.result_json(213, 10.0, andere=700.0)
        write_text_atomic(ensure_dir(self.root / "runs" / "b213") / "result.json",
                          json.dumps({"stats": {"laufzeit": {"langsamste": [
                              {"name": "PowerShell", "dauer_s": 700.0,
                               "kurz": "Get-Date; git status"}]}}}))
        self.assertIsNone(stand.preflight_dauer(self.cfg))

    def test_groesserer_batch_ohne_preflight_faellt_zurueck(self):
        """Der neueste Batch hat keinen Preflight-Aufruf -> der vorige zaehlt."""
        self.result_json(212, 540.0)
        write_text_atomic(ensure_dir(self.root / "runs" / "b213") / "result.json",
                          json.dumps({"stats": {"laufzeit": {"langsamste": []}}}))
        self.assertEqual(stand.preflight_dauer(self.cfg)["batch"], 212)

    # --------------------------------------------------------- Schwelle
    def test_schwelle_zieht_den_preflight_vor(self):
        self.result_json(214, 600.0)              # 10 min
        u = worker.umschalt_minuten(self.cfg)
        self.assertAlmostEqual(u["preflight_min"], 10.0, places=2)
        self.assertAlmostEqual(u["vorlauf_min"], 15.0, places=2)
        self.assertAlmostEqual(u["umschalt_min"], 75.0, places=2)
        self.assertEqual(u["preflight_batch"], 214)

    def test_langer_preflight_schiebt_die_schwelle_weiter_vor(self):
        self.result_json(214, 1200.0)             # 20 min
        u = worker.umschalt_minuten(self.cfg)
        self.assertAlmostEqual(u["vorlauf_min"], 25.0, places=2)
        self.assertAlmostEqual(u["umschalt_min"], 65.0, places=2)

    def test_ohne_messung_gilt_die_feste_zahl(self):
        u = worker.umschalt_minuten(self.cfg)
        self.assertEqual(u["preflight_min"], 0.0)
        self.assertEqual(u["preflight_batch"], 0)
        self.assertAlmostEqual(u["vorlauf_min"], 15.0, places=2)
        self.assertAlmostEqual(u["umschalt_min"], 75.0, places=2)

    def test_anstoss_grenze_folgt_der_schwelle(self):
        from hx import streamjson
        from hx.proc import StreamRun
        self.result_json(214, 1200.0)             # Schwelle 65 min
        s = streamjson.StreamStats()
        s.feed(json.dumps({"type": "assistant", "message": {
            "id": "m1", "model": "m", "usage": {"input_tokens": 1000},
            "content": [{"type": "text", "text": "x"}]}}))
        run = StreamRun()
        run.rc = 0
        entsch = worker.fortsetzung_pruefen(self.cfg, run, s,
                                            "## NACHRUECKLISTE\n1. Posten\n", 66.0, [])
        self.assertFalse(entsch["ja"])
        self.assertIn("Umschaltschwelle 65 min", entsch["grund"])

    # ------------------------------------------------------------ Uhr + Hook
    def test_uhr_zeigt_den_preflight(self):
        from datetime import datetime, timedelta, timezone
        start = datetime.now(timezone.utc) - timedelta(minutes=34)
        st = {"worker": {"pid": 1, "started_at": start.isoformat(timespec="seconds")},
              "live": {"batch": 214, "kontext": 310000}}
        text = uhr.uhr_text(st, 90, 180, umschalt_min=75, kontext_limit=1000000,
                            preflight_min=10.0)
        self.assertIn("Preflight zuletzt ~10 min", text)
        self.assertIn("Der Vorlauf enthaelt den Preflight (gemessen ~10 min) plus 5 min",
                      text)
        ohne = uhr.uhr_text(st, 90, 180, umschalt_min=75, kontext_limit=1000000)
        self.assertNotIn("Preflight zuletzt", ohne)

    def test_hook_datei_traegt_die_neue_schwelle(self):
        self.result_json(213, 1200.0)             # 20 min -> Schwelle 65 min
        state_datei = self.state().path
        ziel = worker.write_worker_hooks(self.cfg, self.root / "runs" / "b214",
                                         state_datei, self.log)
        args = json.loads(Path(ziel).read_text(encoding="utf-8"))[
            "hooks"]["PostToolUse"][0]["hooks"][0]["args"]
        self.assertEqual(args[args.index("--umschalt") + 1], "65")
        self.assertEqual(args[args.index("--preflight-min") + 1], "20.0")

    def test_hook_skript_zeigt_beides_im_text(self):
        from datetime import datetime, timedelta, timezone
        start = datetime.now(timezone.utc) - timedelta(minutes=34)
        state_datei = self.root / "state" / "run.json"
        write_text_atomic(state_datei, json.dumps(
            {"worker": {"pid": 1, "started_at": start.isoformat(timespec="seconds")},
             "live": {"batch": 214, "kontext": 310000}}))
        p = subprocess.run([sys.executable, str(ROOT / "tools" / "batch_uhr.py"),
                            "--state", str(state_datei), "--weich", "90", "--hart", "180",
                            "--umschalt", "65", "--preflight-min", "20.0",
                            "--kontext-limit", "1000000"],
                           input=b"{}", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=120)
        self.assertEqual(p.returncode, 0, p.stderr.decode("utf-8", "replace")[:200])
        txt = json.loads(p.stdout.decode("utf-8"))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Umschalten ab 65", txt)
        self.assertIn("Preflight zuletzt ~20 min", txt)

    def test_vorspann_nennt_den_vorlauf(self):
        pre = worker.WORKER_PREAMBLE
        self.assertIn("Preflight zuletzt ~<p> min", pre)
        self.assertIn("Alarmgrenze minus Vorlauf", pre)
        self.assertIn("Du bist weiterhin in Batch <N>", pre)


# ============================== 3) B-Schritt-Ausloeser ersetzt (Befund 4)
class TestHybridVerlauf(Basis):
    def test_zeile_wird_gelesen(self):
        self.preflight(214, HYBRID)
        e = stand.hybrid_verlauf(self.cfg, 4)
        self.assertEqual(len(e), 1)
        self.assertEqual((e[0]["batch"], e[0]["halt_pc"], e[0]["art"]), (214, "800138F0",
                                                                         "MMIO"))
        self.assertEqual((e[0]["weg"], e[0]["weg_gesamt"]), (28, 407))
        self.assertEqual(e[0]["rest"].split(), ["0", "OK"],
                         "Feld 5 samt Urteil - Leerraum wird nicht verglichen")

    def test_ohne_zeile_fehlt_der_eintrag(self):
        self.preflight(214, "Bahnabdeckung      57/78 | Bloecke 335/434 | verifiziert 60")
        self.assertEqual(stand.hybrid_verlauf(self.cfg, 4), [])

    def test_schranke_und_grosse_werte(self):
        self.preflight(214, hybrid("8000CB98", 448, 42599, nr="2000000", art="Schranke",
                                   rest="nein"))
        e = stand.hybrid_verlauf(self.cfg, 4)[0]
        self.assertEqual((e["halt_pc"], e["art"], e["weg"], e["weg_gesamt"], e["rest"]),
                         ("8000CB98", "Schranke", 448, 42599, "nein                      "
                                                              " OK"))
        self.assertEqual(e["nr"], "2000000")

    def test_alle_drei_felder_der_echten_dateien(self):
        cfg = load_config()
        e = {x["batch"]: x for x in stand.hybrid_verlauf(cfg, 8)}
        if 212 not in e or 214 not in e:
            self.skipTest("echte Preflight-Dateien fehlen")
        self.assertEqual((e[212]["halt_pc"], e[212]["weg"]), ("800138F0", 28))
        self.assertEqual((e[213]["halt_pc"], e[213]["weg"]), ("800138F0", 28))
        self.assertEqual((e[214]["halt_pc"], e[214]["weg"]), ("8000CB98", 448))


class TestHybridStillstand(Basis):
    def reihe(self, *werte: tuple[int, str, int]) -> None:
        """`(batch, halt_pc, weg)` je B-Batch - schreibt Preflight + Auftrag."""
        for batch, halt, weg in werte:
            self.strang(batch, "B")
            self.preflight(batch, hybrid(halt, weg))

    def gruende(self, batch: int) -> list[str]:
        s = self.state(tag=f"harness/b{batch}-start", batch=batch)
        return aussensicht.faellig(self.cfg, s, log=self.log)

    def hybrid_grund(self, gruende: list[str]) -> list[str]:
        return [g for g in gruende if g.startswith(aussensicht.HYBRID_GRUND)]

    def test_drei_gleiche_b_batches_ergeben_den_grund(self):
        self.reihe((212, "800138F0", 28), (213, "800138F0", 28), (214, "800138F0", 28))
        text = aussensicht.hybrid_stillstand(self.cfg)
        self.assertIn("Hybrid-Lauf haengt: Halt-PC 800138F0", text)
        self.assertIn("Wegmass 28/407 -> 28/407 steigt nicht", text)
        self.assertIn("(B212, B213, B214", text)
        self.assertIn("kein Fortschritt ueber 3 B-Batches (B212 bis B214)", text)
        self.assertEqual(len(self.hybrid_grund(self.gruende(214))), 1)

    def test_zwei_gleiche_sind_noch_kein_stillstand(self):
        self.reihe((213, "800138F0", 28), (214, "800138F0", 28))
        self.assertEqual(aussensicht.hybrid_stillstand(self.cfg), "")
        self.assertEqual(self.hybrid_grund(self.gruende(214)), [])

    def test_steigendes_wegmass_ist_fortschritt(self):
        self.reihe((212, "800138F0", 28), (213, "800138F0", 28), (214, "800138F0", 41))
        self.assertEqual(aussensicht.hybrid_stillstand(self.cfg), "")

    def test_anderer_halt_pc_ist_kein_stillstand(self):
        self.reihe((212, "800138F0", 28), (213, "800138F0", 28), (214, "8000CB98", 28))
        self.assertEqual(aussensicht.hybrid_stillstand(self.cfg), "")

    def test_gefallenes_wegmass_zaehlt_als_stillstand(self):
        """\"steigt nicht\" schliesst Rueckschritte ein - sie sind kein Fortschritt."""
        self.reihe((212, "800138F0", 28), (213, "800138F0", 28), (214, "800138F0", 27))
        self.assertIn("Wegmass 28/407 -> 27/407 steigt nicht",
                      aussensicht.hybrid_stillstand(self.cfg))

    def test_c_batch_zaehlt_nicht_mit(self):
        """B212, B213 ist ein C-Batch, B214 - die Reihe hat nur ZWEI B-Batches."""
        self.reihe((212, "800138F0", 28), (214, "800138F0", 28))
        self.strang(213, "C")
        self.preflight(213, hybrid("800138F0", 28))
        verlauf = [e["batch"] for e in stand.hybrid_verlauf(self.cfg, 6)]
        self.assertEqual(verlauf, [212, 213, 214], "die Zeile ist da ...")
        self.assertEqual(aussensicht.hybrid_stillstand(self.cfg), "",
                         "... aber der C-Batch zaehlt fuer den Stillstand nicht")

    def test_b_batch_ohne_zeile_zaehlt_nicht_mit(self):
        self.strang(211, "B")
        self.reihe((212, "800138F0", 28), (214, "800138F0", 28))
        self.assertEqual(aussensicht.hybrid_stillstand(self.cfg), "")

    def test_schwelle_ist_konfigurierbar(self):
        self.cfg.data.setdefault("meta", {})["bschritt_stillstand_batches"] = 2
        self.reihe((213, "800138F0", 28), (214, "800138F0", 28))
        self.assertIn("ueber 2 B-Batches", aussensicht.hybrid_stillstand(self.cfg))

    def test_neuester_b_batch_ist_der_letzte_mit_zeile(self):
        self.reihe((212, "800138F0", 28), (214, "8000CB98", 448))
        self.assertEqual(aussensicht.hybrid_neuester_b(self.cfg), 214)

    def test_echte_dateien_loesen_keinen_falschen_alarm_aus(self):
        """B212/B213 sind gleich, B214 nicht - und B213 ist ein C-Batch."""
        cfg = load_config()
        if not (Path(cfg.decomp) / "analysis" / "_preflight_214.txt").is_file():
            self.skipTest("echte Preflight-Dateien fehlen")
        self.assertEqual(aussensicht.hybrid_stillstand(cfg), "")

    # ------------------------------------------------------------- Entprellung
    def test_marke_wird_nur_einmal_gemeldet(self):
        self.reihe((212, "800138F0", 28), (213, "800138F0", 28), (214, "800138F0", 28))
        s = self.state(tag="harness/b214-start", batch=214)
        gruende = aussensicht.faellig(self.cfg, s, log=self.log)
        self.assertEqual(len(self.hybrid_grund(gruende)), 1)
        self.assertEqual(aussensicht.hybrid_marke_setzen(self.cfg, s), 214)
        s.save()
        self.assertEqual(s.data["meta"]["hybrid_gemeldet_bis"], 214)
        self.assertEqual(self.hybrid_grund(aussensicht.faellig(self.cfg, s)), [],
                         "derselbe Stillstand darf nicht zweimal feuern")
        # Ein neuer B-Batch mit gleichen Werten verlaengert die Reihe -> wieder ein Grund.
        self.reihe((215, "800138F0", 28))
        s.data["batch"] = 215
        self.assertTrue(self.hybrid_grund(aussensicht.faellig(self.cfg, s)))

    def test_migration_startet_bei_null(self):
        self.reihe((212, "800138F0", 28), (213, "800138F0", 28), (214, "800138F0", 28))
        s = self.state(tag="harness/b214-start", batch=214)
        self.assertNotIn("hybrid_gemeldet_bis", s.data.get("meta") or {})
        self.assertTrue(self.hybrid_grund(aussensicht.faellig(self.cfg, s, log=self.log)))
        self.assertEqual(s.data["meta"]["hybrid_gemeldet_bis"], 0,
                         "die Migration setzt 0 (nichts gemeldet)")

    def test_fehlgeschlagener_lauf_setzt_die_marke_nicht(self):
        self.reihe((212, "800138F0", 28), (213, "800138F0", 28), (214, "800138F0", 28))
        grund = aussensicht.hybrid_stillstand(self.cfg)
        self.assertTrue(grund)
        orig = aussensicht.run
        aussensicht.run = self._fake_run(7)
        try:
            o = self.orch(214)
            o._do_aussensicht(grund, gruende=[grund])
            self.assertNotIn("hybrid_gemeldet_bis", o.state.data["meta"],
                             "rc != 0 darf die Marke nicht setzen")
        finally:
            aussensicht.run = orig

    def test_erfolgreicher_lauf_setzt_die_marke(self):
        self.reihe((212, "800138F0", 28), (213, "800138F0", 28), (214, "800138F0", 28))
        grund = aussensicht.hybrid_stillstand(self.cfg)
        orig = aussensicht.run
        aussensicht.run = self._fake_run(0)
        try:
            o = self.orch(214)
            o._do_aussensicht(grund, gruende=[grund])
            self.assertEqual(o.state.data["meta"]["hybrid_gemeldet_bis"], 214)
        finally:
            aussensicht.run = orig

    def orch(self, batch: int) -> Orchestrator:
        o = Orchestrator(self.cfg, self.log, mock=True,
                         state_file=self.root / "state" / "run.json")
        o.qroot = self.root
        o.said = []
        o.say = lambda t="", *a, **k: o.said.append(str(t))
        o.state.data["batch"] = int(batch)
        o.state.save()
        return o

    @staticmethod
    def _fake_run(rc: int):
        def lauf(cfg, log, state, grund, mock=False, zufall=None):
            res = aussensicht.Ergebnis()
            res.rc, res.dauer_s, res.text, res.summary, res.tiefe = rc, 1.0, "", "", {}
            return res
        return lauf

    # ------------------------------------------------------- alter Grund ist weg
    def test_alter_grund_ist_entfernt(self):
        for name in ("b_schritt", "b_schritt_stillstand", "bschritt_neuester_b",
                     "bschritt_gemeldet_bis", "bschritt_marke_setzen",
                     "bschritt_beteiligt", "BSCHRITT_GRUND", "MARKE_BSCHRITT_SCHLUESSEL"):
            self.assertFalse(hasattr(aussensicht, name), f"{name} existiert noch")
        # Und keine Ausloeser-Zeile nennt mehr den B-Schritt.
        self.reihe((212, "800138F0", 28), (213, "800138F0", 28), (214, "800138F0", 28))
        s = self.state(tag="harness/b214-start", batch=214)
        self.assertFalse(any("B-Schritt" in g for g in aussensicht.faellig(self.cfg, s)))

    def test_konfiguration_hat_die_drei(self):
        self.assertEqual(
            int(aussensicht.grenzen(load_config())["bschritt_stillstand_batches"]), 3)

    def test_b_schritt_pflichtzeile_bleibt_fuer_den_strang(self):
        """Die Review-Zeile selbst bleibt: `strang_von_batch` nutzt sie als Beleg.

        Konvention: das Review, das Batch N bewertet, liegt in `runs/b<N+1>`.
        """
        self.strang(214, "B")
        self.assertEqual(stand.strang_von_batch(self.cfg, 214)["strang"], "B")
        write_text_atomic(ensure_dir(self.root / "runs" / "b216") / "review.md",
                          "<TELEGRAM_SUMMARY>\nErgebnis: x\n"
                          "B-SCHRITT: 2/5 Kontrollfluss, B-Batch 4 von max 20\n"
                          "</TELEGRAM_SUMMARY>\n")
        s = stand.strang_von_batch(self.cfg, 215)
        self.assertEqual(s["strang"], "B")
        self.assertIn("Pflichtzeile B-SCHRITT", s["quelle"])
        self.assertTrue(hasattr(stand, "_RE_B_SCHRITT"))


class TestGemesseneKappungen(unittest.TestCase):
    """Nachtrag R13ai: die Kappungen aus B212-B214 als Regressionspflock (nur lesend)."""

    def setUp(self):
        self.cfg = load_config()

    def test_default_bleibt_600_max_ist_1800(self):
        """`timeout` ohne Angabe wird weiter bei 600 s gekappt - der Max-Wert greift nur
        mit ausdruecklichem `timeout`."""
        import os
        env = envs.worker_env(self.cfg, dict(os.environ), "token")
        self.assertEqual(env["BASH_DEFAULT_TIMEOUT_MS"], "600000",
                         "Schutz gegen haengende Befehle bleibt")
        self.assertEqual(env["BASH_MAX_TIMEOUT_MS"], "1800000")

    def test_vorspann_hat_die_zeile(self):
        pre = worker.WORKER_PREAMBLE
        self.assertIn("Für `preflight.py`, `c_kopf.py mutalle` und `port_build` den "
                      "Bash-Parameter\n  `timeout=1800000` setzen; sonst wird nach 600 s "
                      "gekappt.", pre)
        self.assertIn("bis 1800000 = 30 min", pre)
        self.assertIn("Die Obergrenze des\n  Werkzeugs ist seit R13ah 1800 s, die Vorgabe "
                      "ohne Parameter bleibt 600 s", pre)
        # `timeout=600000` ist KEINE Erhoehung - genau das war der Messbefund in B213/B214.
        self.assertIn("`timeout=600000` ist KEINE Erhoehung", pre)
        self.assertNotIn("Millisekunden, bis 600000 = 10 min", pre)

    def test_die_drei_namen_stehen_beisammen(self):
        pre = worker.WORKER_PREAMBLE
        for name in ("preflight.py", "c_kopf.py mutalle", "port_build"):
            self.assertIn(name, pre)

    def test_b212_hat_gekappte_aufrufe_ohne_eigenes_timeout(self):
        """Belegt, warum die Vorspann-Zeile noetig ist: die Mehrheit laeuft ohne `timeout`."""
        p = Path(self.cfg.root) / "runs" / "b212" / "stream.jsonl"
        if not p.is_file():
            self.skipTest("runs/b212/stream.jsonl fehlt")
        mit_timeout = 0
        gesamt = 0
        with open(p, encoding="utf-8", errors="replace") as fh:
            for zeile in fh:
                if '"tool_use"' not in zeile:
                    continue
                try:
                    satz = json.loads(zeile)
                except ValueError:
                    continue
                for block in ((satz.get("message") or {}).get("content") or []):
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        gesamt += 1
                        if "timeout" in (block.get("input") or {}):
                            mit_timeout += 1
        self.assertGreater(gesamt, 100)
        self.assertLess(mit_timeout, gesamt / 2,
                        "die Mehrheit der Aufrufe laeuft ohne eigene Zeitgrenze")


if __name__ == "__main__":
    unittest.main()
