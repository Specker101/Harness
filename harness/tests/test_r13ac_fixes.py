"""Tests fuer R13ac (2026-09-28): Batch-Uhr, Trend aus der Preflight-Reihe, Zaehler-Trennung.

Anlass sind vier Befunde der Aussensicht zu B210 (`runs/meta-210.md`), die der Reviewer
ausdruecklich als Harness-Sache markiert hat:

* **M210-1 / Punkt 1:** der Worker schaetzte seine Laufzeit an der Zahl der
  Werkzeugaufrufe ("~180 min", gemessen **46 min**) und strich deshalb Pflichtteile.
* **Punkt 2 (M210-2):** Trend- und Durchsatzzeile standen auf dem R207-Zaehler
  ("verifiziert: +0 Koepfe (78 -> 78)"), im Fenster fehlte B209, und die C-Koepfe wurden
  mit R207 gemischt. Gemessen sind es **+61** Koepfe von B198 (17) bis B210 (78).
* **M210-3:** "C verifiziert" zeigte die **Kopfzahl** (78), waehrend derselbe Preflight
  23 davon als teilgeprueft und nur 55 als verifiziert auswies.
* **M210-4:** die PLAN-Spalte las einen Wert, der nicht im Auftrag stand ("B210 | 6
  Koepfe" gegen "keine neuen Koepfe"), und die Median-Regel zaehlte B-Batches als
  Null-Batches mit.
* **Punkt 5:** die watch-Anzeige zaehlte die Minuten ab dem Start des ZUSCHAUERS
  ("Batch 210 laufend: … 200.6 min" um 22:11 bei 46 min Laufzeit).

Die Tests mit den **echten** Dateien laufen gegen `g:\\Silent Scope Decomp` (wie R13aa);
fehlen sie, werden sie uebersprungen. Alles andere im Attrappenbetrieb.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import bilanz, fragen, stand, uhr, worker                  # noqa: E402
from hx.config import load_config                                 # noqa: E402
from hx.util import Log, ensure_dir, write_text_atomic            # noqa: E402
from hx.watch import Watcher                                      # noqa: E402

PREFLIGHT = """=== PREFLIGHT (before) 2026-09-28 22:33 ===
Lauf 2026-09-28 22:33:19 | HEAD 0cdff730
Pruefung           Ergebnis                                                 Urteil
C Koepfe           {koepfe} / {faelle} / 0                                   OK
Bahnabdeckung      {v}/{g} | Bloecke 326/434 | verifiziert {v} | teilgeprueft {t} OK
=> BEFORE SAUBER
"""


class Basis(unittest.TestCase):
    """Wegwerf-Workspace: eigener root (state/runs) und ein eigenes 'decomp'-Repo."""

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13ac"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "root")
        self.repo = ensure_dir(self.tmp / "decomp")
        self.ana = ensure_dir(self.repo / "analysis")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.repo)
        cfg.data["paths"]["secrets"] = str(ensure_dir(self.tmp / "secrets"))
        cfg.data["paths"]["harness_home"] = str(self.tmp)
        prof = ensure_dir(self.root / "profiles")
        for f in (ROOT / "profiles").glob("*.json"):
            shutil.copy2(f, prof / f.name)
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---------------------------------------------------------------- Helfer
    def preflight(self, batch: int, koepfe: int, verifiziert: int | None = None,
                  gesamt: int | None = None, teil: int = 23, extra: str = "") -> None:
        text = (PREFLIGHT.format(koepfe=koepfe, faelle=koepfe * 36, v=verifiziert or 0,
                                 g=gesamt or koepfe, t=teil) + extra)
        write_text_atomic(self.ana / f"_preflight_{batch}.txt", text)

    def bilanz_datei(self, batch: int, vorher: int, heute: int) -> None:
        """Kanonische Bilanzdatei-Attrappe (`analysis/_m<N>/_bilanz<N>.txt`).

        Der Durchsatz liest die Zeile `R207 rueckwaerts` mit Vorbatch- und Heute-Spalte;
        ohne so eine Datei ist das Fenster leer und die PLAN/IST-Tafel gibt es nicht.
        """
        d = ensure_dir(self.ana / f"_m{batch}")
        write_text_atomic(d / f"_bilanz{batch}.txt",
                          "| Ast | Vorbatch | heute |\n"
                          f"| **R207 rueckwaerts** | **{vorher}** (a 30) | "
                          f"**{heute}** (a 30) |\n")

    def state(self, **felder) -> dict:
        daten = {"batch": 210, "state": "DS_WORKING", "live": {"batch": 210}}
        daten.update(felder)
        write_text_atomic(self.root / "state" / "run.json", json.dumps(daten, indent=1))
        return daten

    def run_ordner(self, batch: int, **felder) -> Path:
        rd = ensure_dir(self.root / "runs" / f"b{batch:03d}")
        daten = {"batch": batch, "rc": 0, "duration_s": 2771.0, "stats": {"requests": 10},
                 "cost_usd": 0.2, "model_seen": "deepseek-flash[1m]", "model_ok": True}
        daten.update(felder)
        write_text_atomic(rd / "result.json", json.dumps(daten, indent=1))
        return rd

    def watcher(self) -> Watcher:
        w = Watcher(self.cfg, self.log, color=False, once=True)
        w.batch_nr = 210
        return w


# ---------------------------------------------------------------- 1) Batch-Uhr
class TestBatchUhr(Basis):
    def test_hook_datei_wird_geschrieben(self):
        """Der Hook landet als Einstellungsdatei im Lauf-Ordner, mit Zustand und Grenzen."""
        rd = self.run_ordner(210)
        state = self.root / "state" / "run.json"
        self.state()
        ziel = worker.write_worker_hooks(self.cfg, rd, state, self.log)
        self.assertTrue(ziel and Path(ziel).is_file())
        daten = json.loads(Path(ziel).read_text(encoding="utf-8"))
        gruppe = daten["hooks"]["PostToolUse"][0]["hooks"][0]
        self.assertEqual(gruppe["type"], "command")
        self.assertIn("batch_uhr.py", " ".join(gruppe["args"]))
        self.assertIn(str(state), gruppe["args"])
        # Die Grenzen kommen aus [limits] (Weich 90 min / Hart 180 min in harness.toml).
        i = gruppe["args"].index("--weich")
        self.assertEqual(gruppe["args"][i + 1],
                         f"{float(self.cfg.get('limits', 'alarm_wall_s', 5400)) / 60:.0f}")

    def test_hook_abschaltbar(self):
        self.cfg.data["claude"]["worker_hooks"] = False
        self.assertIsNone(worker.write_worker_hooks(self.cfg, self.run_ordner(210),
                                                    self.root / "state" / "run.json",
                                                    self.log))

    def test_settings_kommt_in_die_kommandozeile(self):
        from hx.profiles import load_profile
        p = load_profile(self.cfg.root, "none")
        rd = self.run_ordner(210)
        cmd, _ = worker.build_command(self.cfg, p, rd, "sid-1")
        self.assertNotIn("--settings", cmd)
        cmd, _ = worker.build_command(self.cfg, p, rd, "sid-1", hooks_settings="X.json")
        self.assertIn("--settings", cmd)
        self.assertEqual(cmd[cmd.index("--settings") + 1], "X.json")

    def test_startzeit_steht_im_vorspann(self):
        p = worker.build_prompt(self.cfg, "Auftrag", "", None, "none",
                                start_zeit=datetime.now(timezone.utc))
        self.assertIn("Batch-Start (Harness-Zeitstempel):", p)
        self.assertIn("Die ZAHL DER WERKZEUGAUFRUFE sagt nichts", p)
        self.assertIn("Get-Date", p)

    def test_uhr_text_nennt_die_gemessenen_minuten(self):
        start = datetime.now(timezone.utc) - timedelta(minutes=42)
        st = {"worker": {"pid": 1, "started_at": start.isoformat(timespec="seconds")},
              "live": {"batch": 210}}
        text = uhr.uhr_text(st, 77, 123)
        self.assertIn("BATCH-UHR (Harness-Messung)", text)
        self.assertRegex(text, r"4[12]\.\d min von 77 min")
        self.assertIn("harte Grenze 123 min", text)

    def test_uhr_ohne_laufenden_batch(self):
        text = uhr.uhr_text({}, 90, 180)
        self.assertIn("kein laufender Batch", text)

    def test_uhr_erkennt_unplausible_startzeit(self):
        alt = datetime.now(timezone.utc) - timedelta(hours=9)
        d = uhr.start_zeit({"worker": {"started_at": alt.isoformat(timespec="seconds")}})
        self.assertTrue(d["unplausibel"])
        self.assertIn("unplausibel", uhr.uhr_text({"worker": {
            "started_at": alt.isoformat(timespec="seconds")}}, 90, 180))

    def test_hook_skript_im_unterprozess(self):
        """Das Skript selbst: Eingabe auf stdin, Ausgabe = JSON mit additionalContext."""
        state = self.root / "state" / "run.json"
        start = datetime.now(timezone.utc) - timedelta(minutes=42)
        write_text_atomic(state, json.dumps(
            {"worker": {"pid": 1, "started_at": start.isoformat(timespec="seconds")},
             "live": {"batch": 210}}))
        p = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "batch_uhr.py"),
             "--state", str(state), "--weich", "77", "--hart", "123"],
            input=b'{"hook_event_name": "PostToolUse", "tool_name": "Read"}',
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        self.assertEqual(p.returncode, 0, p.stderr.decode("utf-8", "replace")[:200])
        daten = json.loads(p.stdout.decode("utf-8"))
        hso = daten["hookSpecificOutput"]
        self.assertEqual(hso["hookEventName"], "PostToolUse")
        self.assertIn("BATCH-UHR", hso["additionalContext"])
        self.assertIn("77 min", hso["additionalContext"])

    def test_hook_skript_ohne_zustand_ist_still(self):
        p = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "batch_uhr.py"),
             "--state", str(self.tmp / "gibtsnicht.json")],
            input=b"{}", stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout.strip(), b"")

    def test_hook_skript_ohne_worker_schweigt(self):
        """Zustand ohne `worker` (Lauf beendet) -> keine Zeile im Kontext."""
        state = self.root / "state" / "run.json"
        write_text_atomic(state, json.dumps({"batch": 210, "worker": None}))
        p = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "batch_uhr.py"), "--state", str(state)],
            input=b"{}", stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout.strip(), b"")

    def test_beleg_der_sonde_ist_da(self):
        """Der Hook-Weg ist GEMESSEN (tools/r13ac_probe_hook.py), nicht behauptet."""
        beleg = Path(ROOT).parent / "docs" / "_r13ac_hook.txt"
        self.assertTrue(beleg.is_file(), "Sonden-Beleg fehlt")
        text = beleg.read_text(encoding="utf-8")
        self.assertIn("KOMMT BEIM MODELL AN", text)
        self.assertIn("BATCH-UHR", text)


# ------------------------------------------------- 2) Trend/Durchsatz (M210-2)
class TestTrendMitEchtenDateien(unittest.TestCase):
    """Die C-Koepfe-Reihe aus den ECHTEN Preflight-Dateien - EINGEFROREN kopiert.

    **FALLSTRICK (erst so gebaut, dann rot):** der erste Anlauf las direkt aus
    `g:\\Silent Scope Decomp` und nahm "das neueste Fenster". Waehrend der vollen
    Testreihe beendete sich B211 und schrieb `analysis/_preflight_211.txt` - damit
    rutschte das Fenster auf B199..B211 und drei Tests wurden rot ("211 != 210",
    "Trend B199 45 -> B211 78"). Genau dieser Fallstrick steht seit R13x in den
    Projektnotizen ("der neueste Batch ist kein stabiler Bezug, solange der Harness
    laeuft"). Deshalb wird die Spanne B198..B210 EINMAL in ein Wegwerf-Verzeichnis
    kopiert und dort geprueft; daneben steht je ein Test, der die Kopie gegen das
    lebende Repo prueft (uebersprungen, wenn die Datei fehlt).
    """

    @classmethod
    def setUpClass(cls):
        cls.cfg = load_config()
        cls.echt = Path(cls.cfg.decomp) / "analysis"
        cls.tmp = Path(ROOT) / "tests" / "_tmp_r13ac_real"
        shutil.rmtree(cls.tmp, ignore_errors=True)
        ana = ensure_dir(cls.tmp / "decomp" / "analysis")
        cls.kopiert: list[str] = []
        for b in range(198, 211):
            p = cls.echt / f"_preflight_{b}.txt"
            if p.is_file():
                shutil.copy2(p, ana / p.name)
                cls.kopiert.append(p.name)
        # Die kanonischen Bilanzdateien mitkopieren (R207-Zaehler, B209 fehlt bewusst).
        for ordner in sorted(cls.echt.glob("_m*")):
            if not ordner.is_dir() or not (ordner.name[2:].isdigit()):
                continue
            if not 203 <= int(ordner.name[2:]) <= 210:
                continue
            ziel = ensure_dir(ana / ordner.name)
            for f in ordner.glob("_bilanz*.txt"):
                shutil.copy2(f, ziel / f.name)
        cls.cfg.data["paths"]["decomp"] = str(cls.tmp / "decomp")
        cls.t = stand.c_trend(cls.cfg, stand.TREND_FENSTER)
        cls.zeilen = "\n".join(stand.durchsatz_zeilen(cls.cfg, 5))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_kopie_ist_vollstaendig(self):
        self.assertEqual(len(self.kopiert), 13, "B198..B210 nicht vollstaendig kopiert")

    def test_plus_61_ueber_das_fenster(self):
        self.assertTrue(self.t["gemessen"], "keine Preflight-Reihe gefunden")
        self.assertEqual((self.t["erst"]["batch"], self.t["erst"]["koepfe"]), (198, 17))
        self.assertEqual((self.t["letzt"]["batch"], self.t["letzt"]["koepfe"]), (210, 78))
        self.assertEqual(self.t["delta"], 61)
        self.assertEqual(self.t["anzahl_batches"], 12)
        self.assertEqual(self.t["luecken"], [])

    def test_durchsatzzeilen_trennen_die_zaehler(self):
        self.assertIn("C Koepfe (Preflight-Messung", self.zeilen)
        self.assertIn("Trend B198 17 -> B210 78 = +61 Koepfe", self.zeilen)
        self.assertIn("lueckenlos, 13 Dateien", self.zeilen)
        self.assertIn("Zaehler R207 (gebaut, ALLE Straenge", self.zeilen)
        self.assertIn("nicht mit den C Koepfen mischen", self.zeilen)
        # Die kanonischen Bilanzdateien fuer B209 gibt es nicht -> das Fenster ist
        # lueckenhaft, und genau das muss dastehen.
        self.assertIn("LUECKENHAFT", self.zeilen)
        self.assertNotIn("Durchsatz    : Koepfe (R207 gebaut)", self.zeilen)

    def test_keine_verwechslung_der_zaehler(self):
        """Die R207-Zeile heisst R207 - und die C-Zeile nennt ihre Quelle."""
        i_c = self.zeilen.index("C Koepfe (Preflight-Messung")
        i_r = self.zeilen.index("Zaehler R207")
        self.assertLess(i_c, i_r)
        self.assertIn("Quelle dieser Zeilen: analysis/_preflight_198.txt", self.zeilen)

    def test_bahnabdeckung_210_aus_der_kopie(self):
        e = [x for x in stand.preflight_bahnabdeckung(self.cfg, 20) if x["batch"] == 210]
        self.assertEqual(len(e), 1)
        self.assertEqual((e[0]["verifiziert"], e[0]["gesamt"], e[0]["teilgeprueft"]),
                         (55, 78, 23))
        self.assertEqual(e[0]["bloecke"], 326)
        self.assertEqual(e[0]["quelle"], "Bahnabdeckung")

    def test_die_kopie_stimmt_mit_dem_lebenden_repo(self):
        """Gegenprobe: die eingefrorenen Werte sind die des echten Repos.

        R13bd: beide Seiten werden aus den Zeilen mit `C Koepfe` gebildet. Fehlt diese Zeile
        im lebenden Preflight (Format geaendert), sind BEIDE Listen leer, `assertEqual` haelt
        und der Test prueft nichts mehr - gemessen in `docs/_r13bd_leerlauf.txt`. Deshalb die
        zusätzliche Zusicherung, dass die Zeile ueberhaupt gefunden wurde.
        """
        for name in ("_preflight_198.txt", "_preflight_210.txt"):
            p = self.echt / name
            if not p.is_file():
                self.skipTest(f"{name} fehlt im echten Repo")
            moeglich = [z for z in p.read_text(encoding="utf-8").splitlines()
                        if z.startswith("C Koepfe")]
            kopie = [z for z in (self.tmp / "decomp" / "analysis" / name)
                     .read_text(encoding="utf-8").splitlines() if z.startswith("C Koepfe")]
            self.assertTrue(moeglich, f"{name}: keine Zeile 'C Koepfe' im lebenden Repo - "
                                       "ohne sie vergleicht dieser Test nur zwei leere Listen")
            self.assertEqual(kopie, moeglich)


class TestTrendLogik(Basis):
    def test_r207_fenster_mit_luecke_wird_benannt(self):
        """Der R207-Zaehler hat fuer B209 keine Bilanzdatei - das steht dann auch da."""
        for n, v, h in ((205, 670, 675), (206, 675, 681), (207, 681, 686),
                        (208, 686, 686), (210, 686, 686)):      # B209 fehlt
            self.bilanz_datei(n, v, h)
        self.preflight(209, 78)
        zeilen = "\n".join(stand.durchsatz_zeilen(self.cfg, 5))
        self.assertIn("LUECKENHAFT", zeilen)
        self.assertIn("B209", zeilen)

    def test_luecke_wird_benannt_nicht_als_null_gezaehlt(self):
        self.bilanz_datei(202, 620, 679)
        self.preflight(198, 17)
        self.preflight(199, 45)
        self.preflight(201, 45)          # B200 fehlt
        self.preflight(202, 59)
        t = stand.c_trend(self.cfg, 4)
        self.assertEqual(t["luecken"], [200])
        self.assertEqual(t["delta"], 42)
        # Gezaehlt werden nur BENACHBARTE C-Schritte (198->199: +28 und 201->202: +14);
        # der Schritt ueber die Luecke (199->201) zaehlt nicht mit -> 42/2 = 21.
        self.assertEqual([(s["von"], s["bis"], s["delta"]) for s in t["c_schritte"]],
                         [(198, 199, 28), (201, 202, 14)])
        self.assertEqual(t["mittel_je_c_batch"], 21.0)
        zeilen = "\n".join(stand.durchsatz_zeilen(self.cfg, 3))
        self.assertIn("Luecken: B200", zeilen)

    def test_ohne_quelle_nicht_gemessen(self):
        self.bilanz_datei(210, 681, 686)          # Fenster existiert, C-Quelle fehlt
        t = stand.c_trend(self.cfg, 12)
        self.assertFalse(t["gemessen"])
        self.assertIn("Preflight", t["grund"])
        zeilen = "\n".join(stand.durchsatz_zeilen(self.cfg, 5))
        self.assertIn("C Koepfe (Preflight-Messung", zeilen)
        self.assertIn("NICHT GEMESSEN", zeilen)

    def test_eine_datei_reicht_nicht(self):
        self.preflight(210, 78, verifiziert=55, gesamt=78)
        t = stand.c_trend(self.cfg, 12)
        self.assertFalse(t["gemessen"])
        self.assertIn("nur 1 Preflight", t["grund"])


# --------------------------------------------------- 3) "C verifiziert" (M210-3)
class TestVerifiziertGetrennt(Basis):
    def test_bahnabdeckung_wird_gelesen(self):
        self.preflight(210, 78, verifiziert=55, gesamt=78, teil=23)
        reihe = stand.preflight_bahnabdeckung(self.cfg, 4)
        self.assertEqual(len(reihe), 1)
        e = reihe[-1]
        self.assertEqual((e["verifiziert"], e["gesamt"], e["teilgeprueft"]), (55, 78, 23))
        self.assertEqual(e["bloecke"], 326)
        self.assertEqual(e["quelle"], "Bahnabdeckung")

    def test_nachrueckliste_hat_vorrang(self):
        """Ab B211 liefert der Preflight eine Nachrueckliste - dann gilt DEREN Zahl."""
        self.preflight(211, 80, verifiziert=55, gesamt=78, teil=23,
                       extra="Nachrueckliste 1   62/80 | verifiziert 62\n")
        e = stand.preflight_bahnabdeckung(self.cfg, 4)[-1]
        self.assertEqual(e["quelle"], "Nachrueckliste 1")
        self.assertEqual(e["verifiziert"], 62)
        zeilen = "\n".join(bilanz._verifiziert_zeile(self.cfg))
        self.assertIn("62 von 80 Koepfen", zeilen)
        self.assertIn("Nachrueckliste 1", zeilen)

    def test_kopfzeile_heisst_referenzgleich(self):
        self.preflight(206, 78, verifiziert=55, gesamt=78)
        self.preflight(210, 78, verifiziert=55, gesamt=78)
        zeilen = "\n".join(bilanz.gesamt_block(self.cfg)[:4])
        self.assertIn("C Koepfe referenzgleich: 78 Koepfe", zeilen)
        self.assertIn("C verifiziert: 55 von 78 Koepfen", zeilen)
        self.assertNotIn("C verifiziert: 78", zeilen)

    def test_ohne_bahnabdeckung_nicht_gemessen(self):
        zeilen = "\n".join(bilanz._verifiziert_zeile(self.cfg))
        self.assertIn("C verifiziert: nicht gemessen", zeilen)


# ------------------------------------------------------ 4) PLAN/Median (M210-4)
class TestPlanUndMedian(Basis):
    def test_soll_zeile_wird_gelesen(self):
        self.assertEqual(stand.soll_koepfe("... SOLL-KOEPFE: 7 Koepfe ..."), 7)
        self.assertEqual(stand.soll_koepfe("SOLL-KOEPFE 12"), 12)
        self.assertIsNone(stand.soll_koepfe("keine Soll-Angabe"))

    def test_plan_zeigt_strich_ohne_soll_zeile(self):
        """Ein Auftrag mit Adressen, aber ohne SOLL-KOEPFE-Zeile -> PLAN '-'.

        Genau der Befund M210-4: die alte Heuristik las "6 Koepfe", waehrend der Auftrag
        "keine neuen Koepfe" sagte.
        """
        self.bilanz_datei(210, 681, 686)
        rd = self.run_ordner(210)
        write_text_atomic(rd / "auftrag.md",
                          "=== AUFTRAG ===\nTEIL 3\nkeine neuen Koepfe\n"
                          "0x8005BF74 (51)\n0x8005BF80 (51)\n")
        self.preflight(210, 78)
        text = stand.plan_ist_text(self.cfg, 5)
        zeile = [z for z in text.splitlines() if z.startswith("B210")][0]
        self.assertIn("| - |", zeile)

    def test_soll_zeile_erscheint_im_plan(self):
        self.bilanz_datei(210, 681, 686)
        rd = self.run_ordner(210)
        write_text_atomic(rd / "auftrag.md", "TEIL 3\nSOLL-KOEPFE: 7\n")
        self.preflight(210, 78)
        text = stand.plan_ist_text(self.cfg, 5)
        self.assertIn("| 7 Koepfe |", text)

    def test_median_nur_c_batches_mit_soll(self):
        self.bilanz_datei(210, 681, 686)
        self.run_ordner(210)
        write_text_atomic(self.root / "runs" / "b210" / "auftrag.md",
                          "TEIL 3\nSOLL-KOEPFE: 6\n")
        # R13aw (M219-3): gebildet wird der Median der ZUWaeCHSE - dafuer braucht es
        # den Vorgaengerwert (73 -> 78 = +5), nicht nur den heutigen Stand.
        self.preflight(209, 73)
        self.preflight(210, 78)
        text = stand.plan_ist_text(self.cfg, 5)
        self.assertRegex(text,
                         r"MEDIAN der 1 Zuwaechse der C Koepfe je C-Batch mit SOLL-KOEPFE > 0")
        self.assertIn("+5 (B210)", text)
        # R13ba (M221-5): die zweite Grundmenge steht mit Definition daneben.
        self.assertIn("Mittel ueber alle C-Batches", text)

    def test_median_ohne_soll_ist_nicht_gemessen(self):
        self.bilanz_datei(210, 681, 686)
        self.run_ordner(210)
        write_text_atomic(self.root / "runs" / "b210" / "auftrag.md", "TEIL 3\nirgendwas\n")
        self.preflight(210, 78)
        text = stand.plan_ist_text(self.cfg, 5)
        self.assertIn("MEDIAN: nicht gemessen", text)

    def test_tafel_trennt_die_zaehler_spalten(self):
        self.bilanz_datei(210, 681, 686)
        self.run_ordner(210)
        write_text_atomic(self.root / "runs" / "b210" / "auftrag.md", "TEIL 3\nx\n")
        self.preflight(210, 78)
        kopf = stand.plan_ist_text(self.cfg, 5).splitlines()[0]
        self.assertIn("IST (R207 gebaut, alle Straenge)", kopf)
        self.assertIn("C Koepfe (Preflight)", kopf)


# ------------------------------------------------- 5) watch (Punkt 5)
class TestGegenprobeEchteDaten(unittest.TestCase):
    """Die eine Startzeit gegen die echten Belege: `finished_at - duration_s`."""

    def test_startzeit_aus_result_json_stimmt_mit_dem_bericht(self):
        """B210: `finished_at 2026-09-28T20:34:55Z - 2771,05 s` = 21:48 Ortszeit.

        Genau diese Startzeit nennt der Reviewer-Bericht ("B210 lief 46 min, Start
        21:48") - und genau sie war die Grundlage der falschen watch-Zahl ("200.6 min"
        ab watch-Start). Fehlt die Datei (anderer Rechner), wird uebersprungen.
        """
        p = Path(load_config().sub("runs")) / "b210" / "result.json"
        if not p.is_file():
            self.skipTest("runs/b210/result.json fehlt")
        d = json.loads(p.read_text(encoding="utf-8"))
        ende = datetime.fromisoformat(str(d["finished_at"]).replace("Z", "+00:00"))
        start = ende - timedelta(seconds=float(d["duration_s"]))
        self.assertEqual(start.astimezone().strftime("%H:%M"), "21:48")
        self.assertEqual(uhr.hms(d["duration_s"]), "46m11s")
        # Die Uhr rechnet dasselbe: Startzeit im Zustand = Ende - Laufzeit.
        d2 = uhr.start_zeit({"worker": {"started_at": start.isoformat(timespec="seconds")},
                             "live": {"batch": 210}}, jetzt=ende)
        self.assertAlmostEqual(d2["alter_s"] / 60.0, float(d["duration_s"]) / 60.0,
                               delta=0.05)


class TestWatchUhr(Basis):
    def test_minuten_zaehlen_ab_batch_start_nicht_ab_watch_start(self):
        """Der gemessene Fehler: 200.6 min ab watch-Start bei 46 min Laufzeit."""
        start = datetime.now(timezone.utc) - timedelta(minutes=46.18)
        self.state(worker={"pid": 1, "started_at": start.isoformat(timespec="seconds")})
        w = self.watcher()
        w.started = time.time() - 200.6 * 60        # Zuschauer laeuft seit 200 min
        teil = w._uhr_teil()
        self.assertIn("min seit Batch-Start", teil)
        self.assertNotIn("200", teil)
        self.assertRegex(teil, r"4[56]\.\d min")

    def test_gegenprobe_gegen_result_json(self):
        """Dieselbe Startzeit wie `runs/b<N>/result.json` -> gleiche Minuten."""
        rd = self.run_ordner(210)                      # duration_s = 2771,0 = 46m11s
        res = json.loads((rd / "result.json").read_text(encoding="utf-8"))
        start = datetime.now(timezone.utc) - timedelta(seconds=float(res["duration_s"]))
        self.state(worker={"pid": 1, "started_at": start.isoformat(timespec="seconds")})
        teil = self.watcher()._uhr_teil()
        minuten = float(teil.split(" min ")[0])
        self.assertAlmostEqual(minuten, float(res["duration_s"]) / 60.0, delta=0.2)

    def test_beendeter_batch_zeigt_die_laufzeit_aus_result_json(self):
        rd = self.run_ordner(210)
        self.state(worker=None, live=None, batch=210, state="GATE_APPROVAL")
        w = self.watcher()
        teil = w._uhr_teil()
        self.assertIn("runs/b210/result.json", teil)
        self.assertIn("46m11s", teil)

    def test_watch_ueber_mehrere_batches(self):
        """Batch 210 beendet (46 min), 211 laeuft seit 3 min -> die Uhr folgt dem Batch."""
        rd210 = self.run_ordner(210)
        self.state(worker=None, live=None, batch=210, state="GATE_APPROVAL")
        w = self.watcher()
        w.batch_nr = 210
        self.assertIn("46m11s", w._uhr_teil())
        # Batch 211 startet: Zustand traegt die neue Startzeit, die Anzeige folgt ihr.
        start = datetime.now(timezone.utc) - timedelta(minutes=3)
        self.state(batch=211, state="DS_WORKING", live={"batch": 211},
                   worker={"pid": 2, "started_at": start.isoformat(timespec="seconds")})
        w.batch_nr = 211
        teil = w._uhr_teil()
        self.assertRegex(teil, r"[23]\.\d min seit Batch-Start")
        self.assertNotIn("46m11s", teil)

    def test_statuszeile_nennt_beide_zeiten_getrennt(self):
        start = datetime.now(timezone.utc) - timedelta(minutes=10)
        self.state(worker={"pid": 1, "started_at": start.isoformat(timespec="seconds")})
        w = self.watcher()
        # Eine echte Anfrage im Mitschnitt (die Statuszeile kommt erst mit Zahlen).
        w.stats.feed(json.dumps({"type": "assistant", "message": {
            "id": "m1", "model": "deepseek-flash",
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "content": [{"type": "text", "text": "hallo"}]}}))
        w.ges_batches = 2
        w.ges_requests = 5
        w.ges_cost = 0.1
        w.started = time.time() - 200.6 * 60        # genau der gemeldete Fall
        aus: list[str] = []
        w._p = lambda text="", style="": aus.append(str(text))
        w._print_stats(force=True)
        zeile = "\n".join(aus)
        vor, _, nach = zeile.partition("seit watch-Start")
        self.assertRegex(vor, r"1[01]\.\d min seit Batch-Start")
        self.assertNotIn("200", vor)                # der Fehler von damals
        self.assertIn("200", nach)                  # die watch-Zeit steht nur dort
        self.assertIn("min", nach)


# ------------------------- 6) Batch-Art aus den Pflichtzeilen (R13ac2, Nutzer 2026-09-29)
ANKER_SAMMEL = """# Workstream R1B - Beispiele

**Stand:** BATCH 211 (2026-09-28) - Beispielstand.
**Fertig:** **(1)** etwas fertig.
**Naechster Schritt:** **(a)** weiter.
**Offene Entscheidung:** Alle Posten GESCHLOSSEN. **(1)** R391: GESCHLOSSEN, erledigt. **(2)** A2-Altposten: GESCHLOSSEN. **(3)** be.bin: GESCHLOSSEN. **(4)** A1 MEM-Varianten, **(5)** `42704`, **(6)** Schrittdatei/`mutalle`: GESCHLOSSEN als Entscheidungsposten - Arbeitsposten. **(7)** `nachzuegler`-Sonde: GESCHLOSSEN, ENTSCHIEDEN (Reviewer). **Keine offene Nutzerfrage.**
**Fallstricke/Regeln:** keine.
"""

ANKER_EINZELN = """# Workstream R1B - Beispiele

**Stand:** BATCH 211 (2026-09-28) - Beispielstand.
**Fertig:** **(1)** etwas fertig.
**Naechster Schritt:** **(a)** weiter.
**Offene Entscheidung:** **(1)** R391: GESCHLOSSEN. **(4)** A1 MEM-Varianten - soll das so bleiben (Vorschlag: ja)? Bei ja: bleibt. Bei nein: anders.
**Fallstricke/Regeln:** keine.
"""


class TestBatchArtPflichtzeilen(Basis):
    """R13ac2 (1): `STRANG: B|C` und `SOLL-KOEPFE: n (Strang B, …)` entscheiden die Art.

    Anlass: B211 trug nur `SOLL-KOEPFE: 0 (Strang B, …)`; keine Quelle griff, der Batch
    galt als C-Batch und loeste eine Aussensicht aus (`runs/meta-211.md`).
    """

    def test_soll_koepfe_zeile_mit_strang(self):
        rd = ensure_dir(self.root / "runs" / "b211")
        write_text_atomic(rd / "auftrag.md",
                          "Vorspann\n=== AUFTRAG (vom Reviewer) ===\nTEIL 3\n"
                          "SOLL-KOEPFE: 0 (Strang B, B-Batch 3 von hoechstens 20).\n")
        d = stand.strang_von_batch(self.cfg, 211)
        self.assertEqual(d["strang"], "B")
        self.assertIn("auftrag.md", d["quelle"])

    def test_strang_zeile_im_review_der_ihn_bestellt(self):
        """Am Gate liegt die Instruktion noch in `runs/b<N>/review.md` (B212)."""
        rd = ensure_dir(self.root / "runs" / "b212")
        write_text_atomic(rd / "review.md",
                          "BATCH-ENDE-REVIEW\n\n<DS_INSTRUCTION>\n"
                          "STRANG: B (B-Batch 4 von hoechstens 20). SOLL-KOEPFE: 0.\n")
        d = stand.strang_von_batch(self.cfg, 212)
        self.assertEqual(d["strang"], "B")
        self.assertIn("review.md", d["quelle"])

    def test_strang_zeile_hat_vorrang_vor_fliesstext(self):
        rd = ensure_dir(self.root / "runs" / "b213")
        write_text_atomic(rd / "auftrag.md",
                          "=== AUFTRAG ===\nB212 war ein B-Batch, B213 ist ein C-Batch.\n"
                          "STRANG: C\nSOLL-KOEPFE: 9\n")
        self.assertEqual(stand.strang_von_batch(self.cfg, 213)["strang"], "C")

    def test_ohne_pflichtzeile_bleibt_es_leer(self):
        rd = ensure_dir(self.root / "runs" / "b214")
        write_text_atomic(rd / "auftrag.md", "=== AUFTRAG ===\nkeine Pflichtzeile\n")
        self.assertEqual(stand.strang_von_batch(self.cfg, 214)["strang"], "")

    def test_echte_batches_211_und_212_sind_b(self):
        """Am echten Repo: B211 (Auftrag) und B212 (Review) sind B-Batches."""
        cfg = load_config()
        for batch, datei in ((211, "auftrag.md"), (212, "review.md")):
            if not (Path(cfg.sub("runs")) / f"b{batch:03d}" / datei).is_file():
                self.skipTest(f"runs/b{batch:03d}/{datei} fehlt")
        for batch in (211, 212):
            d = stand.strang_von_batch(cfg, batch)
            self.assertEqual(d["strang"], "B", f"B{batch}: {d}")


class TestAnkerSammelschluss(Basis):
    """R13ac2 (2): Posten unter einem gemeinsamen GESCHLOSSEN sind keine offenen Fragen."""

    def anker(self, text: str) -> None:
        write_text_atomic(ensure_dir(self.repo / "analysis") / "r1b-workstream.md", text)

    def test_mitgezogene_posten_zaehlen_nicht_als_offen(self):
        self.anker(ANKER_SAMMEL)
        t = stand.anchor_bloecke(self.cfg).get("Offene Entscheidung", "")
        offen, geschlossen, ohne = stand.posten_status(t)
        self.assertEqual([n for n, _ in offen], [])
        self.assertEqual(geschlossen, 5)
        self.assertEqual([n for n, _ in ohne], ["(4)", "(5)"])
        self.assertEqual(stand.offene_entscheidungen(t)[0], [])

    def test_ohne_sammelschluss_bleiben_sie_offen(self):
        """Die Regel darf nicht zu weit greifen: ohne Sammel-Schluss ist (4) offen."""
        self.anker(ANKER_EINZELN)
        t = stand.anchor_bloecke(self.cfg).get("Offene Entscheidung", "")
        offen, geschlossen, ohne = stand.posten_status(t)
        self.assertEqual([n for n, _ in offen], ["(4)"])
        self.assertEqual(geschlossen, 1)
        self.assertEqual(ohne, [])

    def test_fragen_zeigt_sie_unter_zur_kenntnis(self):
        self.anker(ANKER_SAMMEL)
        text = fragen.fragen_text(self.cfg, gate=None)
        i_off = text.index("OFFENE FRAGEN AN DICH")
        i_ken = text.index("ZUR KENNTNIS")
        offen_teil, kenntnis_teil = text[i_off:i_ken], text[i_ken:]
        self.assertIn("keine - der Reviewer entscheidet den Regelfall selbst", offen_teil)
        for kennung in ("A4", "A5"):
            self.assertNotIn(kennung, offen_teil)
            self.assertIn(kennung, kenntnis_teil)
        self.assertIn("Sammel-Schluss", kenntnis_teil)

    def test_ohne_sammelschluss_steht_die_frage_offen(self):
        self.anker(ANKER_EINZELN)
        text = fragen.fragen_text(self.cfg, gate=None)
        i_off = text.index("OFFENE FRAGEN AN DICH")
        self.assertIn("A4", text[i_off:text.index("ZUR KENNTNIS")
                                 if "ZUR KENNTNIS" in text else len(text)])


if __name__ == "__main__":
    unittest.main()
