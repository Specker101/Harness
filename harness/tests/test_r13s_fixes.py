"""Tests fuer R13s: lesbare Bilanz (Delta oben, Prozent, Durchsatz) + `/fragen`.

Auftrag (Nutzer, 2026-09-28):
  * `/bilanz` oben das, was sich geaendert hat - in Prozent, gegen den Batch davor,
  * dazu eine **DURCHSATZ**-Zeile (verifizierte Koepfe/Insn je Batch, Mittel der letzten 5,
    offen, Hochrechnung als HYPOTHESIS),
  * Aeste-Tabelle nur noch fuer Zeilen MIT Prozentzahl (volle Tabelle: `/bilanz voll`),
  * ein eigener `/fragen`-Befehl: jede offene Frage als EINE entscheidbare Zeile
    (Frage | Empfehlung | bei ja / bei nein); was sich so nicht formulieren laesst,
    wird als "UNKLAR FORMULIERT" markiert,
  * Review-Prompt: PLAN/IST-Tafel der letzten 5 Batches + Median-Regel,
  * Reviewer-Regeln: Pflichtbloecke `FERTIG WENN` und `STREICHREIHENFOLGE`.

Alles im Attrappenbetrieb: kein Netz, keine API-Kosten, kein Ghidra.
"""

from __future__ import annotations

import io
import json
import re
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import bilanz, retention, reviewer, stand, telegram               # noqa: E402
from hx.config import load_config                                        # noqa: E402
from hx.orchestrator import Orchestrator                                 # noqa: E402
from hx.util import Log, ensure_dir, write_json_atomic, write_text_atomic  # noqa: E402

ANKER = """# Workstream R1B

**Stand:** BATCH 101 (2026-09-28) - **ZWEI KOEPFE GEBAUT** und gemessen.
**Fertig:** **(1) TEIL 1:** `m114_matrix.py` gebaut, 3 Sonden. **(2)** Belege.
**Naechster Schritt:** **(a) R535 (NEU, GEMESSEN, OFFEN): `addc` addiert das CA nicht** - eine Probe machte 12 von 74 Koepfen rot. **(b)** Paket E weiter.
**Offene Entscheidung:** **(1) GESCHLOSSEN (Reviewer B101):** Interpreter streng. **(2) GESCHLOSSEN (Reviewer B101):** Kopf korrigieren. **(5) NEU:** soll `prof` je Kopf MEHRERE MEM-Varianten fahren (Vorschlag: **ja**, eigener kleiner Werkzeugschritt)? **(6)** offen bleiben: R330, `M60_NO_EVID`, `NEG_IMM_LO`, `setup_mesa.ps1` bei EINER DLL, die Pins (R381), der "Later"-Abschnitt
"""

REVIEW = """<TELEGRAM_SUMMARY>
Ergebnis: solide.
ENTSCHIEDEN: Zuerst wird der Interpreter streng gemacht.
ENTSCHIEDEN: Wird ein Kopf rot, wird der Kopf korrigiert.
WARTET AUF LIVE-AUFNAHME: 0x40B/0x40E/0x40F
</TELEGRAM_SUMMARY>
<DS_TOOLS>
profile: ghidra-read
</DS_TOOLS>
<DS_INSTRUCTION>
Batch 102 - Beispiel
TEIL 3 - Bauen: `8005BF74` (51), `80055DA8` (71), `80017A8C` (76).
FERTIG WENN: mindestens 3 Koepfe verifiziert.
STREICHREIHENFOLGE: 1. Doku, 2. Koepfe ueber dem Minimum.
</DS_INSTRUCTION>
"""

# Soll/Ist-Tafel eines Batch-Dokuments (so schreibt der Worker sie wirklich).
# R13x: Ein echtes Dokument fuehrt ZWEI Tafeln - Paragraph 5 die VORHERSAGE (Soll) und
# Paragraph 6 die Soll/Ist-Tafel (Messung). Der Harness muss die Ist-Spalte lesen; die
# Attrappe hat deshalb beide, und die Vorhersagewerte duerfen abweichen
# (`ck_soll`/`pek_soll`), damit die Verwechslung auffaellt.
DOKU = """# Batch {n}

**1. Inventar (GEMESSEN).** {inv_k} Koepfe / {inv_i} Insn im Programm-Inventar,
davon **{baut_k} Koepfe / {baut_i} Insn** in der
Bau-Liste. **OFFEN: {off_k} Koepfe /
{off_i} Insn.** Davon haben **{bl_k} Koepfe / {bl_i} Insn** keinen offenen Ruf.

## 5. TEIL 3a - VORHERSAGE (Soll je Bilanzzeile)

| Bilanzzeile | Zaehlerdefinition | Soll B{n} |
|---|---|---|
| C Koepfe | registrierte Koepfe / Faelle / Abweichungen (`c_kopf_check.py`) | **{ck_soll} / {cf_soll} / 0** |
| Paket E offen | `c_kopf.py paket_e` (keine Preflight-Zeile) | **{pek_soll} / {pei_soll} (Blaetter {pbl} / {pbi})** |

## 6. Abweichungen Soll/Ist

| Zeile | Soll | Ist | Abweichung |
|---|---|---|---|
| **C Koepfe** | {ck_v} / {cf_v} / 0 | **{ck} / {cf} / 0** | keine |
| Paket E offen | {pek_v} / {pei_v} (Bl {pbl_v} / {pbi_v}) | **{pek} / {pei} (Bl {pbl} / {pbi})** | keine |
"""

BILANZDATEI = """## PFLICHT-BILANZ ALLER GETRACKTEN AESTE (Stand: **Batch {n}**)

| Ast / Kern | Vorbatch (B{vm}) | **heute (mit {n})** | Quelle |
|---|---|---|---|
| **R207 rueckwaerts** | **{v}** (a 30 / b 0 / c 0), `check` **{v}** gebaut / **10990** benannt | **{h}** (a 30 / b 0 / c 0), `check` **{h}** gebaut / **11026** benannt | `preflight.py` |
| **Modi** | **85** | **85** | `port_selftest.cpp` |
"""


def _weg(p: Path) -> None:
    retention._weg(p)


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__file__).resolve().parent / "_tmp_r13s"
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
    def anker(self, text: str = ANKER) -> None:
        write_text_atomic(self.ana / "r1b-workstream.md", text)

    def dokument(self, n: int, ck: int, cf: int, pek: int, pei: int,
                 vm: int | None = None, ck_soll: int | None = None,
                 cf_soll: int | None = None, pek_soll: int | None = None,
                 pei_soll: int | None = None) -> None:
        write_text_atomic(self.ana / f"port-batch{n}-beispiel-2026-09-28.md", DOKU.format(
            n=n, vm=vm if vm is not None else n - 1, inv_k=2072, inv_i=123771,
            baut_k=600 + n, baut_i=29000 + n, off_k=1400, off_i=94000,
            bl_k=664, bl_i=31690, ck=ck, cf=cf, ck_v=ck - 5, cf_v=cf - 120,
            ck_soll=ck if ck_soll is None else ck_soll,
            cf_soll=cf if cf_soll is None else cf_soll,
            pek=pek, pei=pei, pek_v=pek + 5, pei_v=pei + 351,
            pek_soll=pek if pek_soll is None else pek_soll,
            pei_soll=pei if pei_soll is None else pei_soll,
            pbl=15, pbi=1083, pbl_v=20, pbi_v=1434))

    def bilanzdatei(self, n: int, v: int, h: int) -> None:
        d = ensure_dir(self.ana / f"_m{n}")
        write_text_atomic(d / f"_bilanz{n}.txt", BILANZDATEI.format(n=n, vm=n - 1, v=v, h=h))

    def preflight(self, n: int, ck: int, cf: int) -> None:
        """Die maschinengeschriebene Messzeile des Batches (`analysis/_preflight_<N>.txt`)."""
        write_text_atomic(self.ana / f"_preflight_{n}.txt",
                          "=== PREFLIGHT (before) ===\n"
                          "Pruefung           Ergebnis                          Urteil\n"
                          f"C Koepfe           {ck} / {cf} / 0                    OK\n"
                          "=> BEFORE SAUBER\n")

    def lauf(self, n: int, auftrag: str = "", dauer: str = "30m07s",
             abbruch: str = "kein Abbruch", ohne_result: bool = False,
             fakten_nach: int | None = None) -> None:
        """Ein Lauf: `result.json` in `runs/b<N>` und die Fakten-Datei in `runs/b<N+1>`.

        R13x: genau die Ablage des Harness - `orchestrator.review` schreibt die
        `harness-facts.md` in den Ordner des NAECHSTEN Batches (`ziel=rdir`), ihr Kopf
        nennt den bewerteten Batch.
        """
        d = ensure_dir(self.root / "runs" / f"b{n}")
        write_text_atomic(d / "auftrag.md", auftrag or "# Prompt\n")
        m = re.fullmatch(r"(?:(\d+)h)?(\d+)m(\d+)s", dauer or "")
        sekunden = (int(m.group(1) or 0) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
                    if m else 0)
        if not ohne_result:
            write_json_atomic(d / "result.json",
                              {"batch": n, "rc": 0, "duration_s": float(sekunden),
                               "killed_reason": None if abbruch == "kein Abbruch" else abbruch,
                               "cost_usd": 0.1, "stats": {"requests": 10, "output": 5000},
                               "finished_at": "2026-09-28T17:21:31+00:00"})
        ziel = ensure_dir(self.root / "runs" / f"b{(fakten_nach or n + 1):03d}")
        write_text_atomic(ziel / "harness-facts.md",
                          f"- Review: bewertet wird Batch {n}; die Instruktion gilt fuer "
                          f"Batch {n + 1}\n"
                          f"- Exit-Code: 0 | Laufzeit: {dauer} (Wanduhr) | "
                          f"Abbruchgrund: {abbruch}\n")

    def snapshot(self, batches=(100, 101)) -> None:
        rows100 = {"2a-Kern": {"gebaut": 1, "offen": 0},
                   "327er-Pool": {"pct": 32.1, "gelesen": 105, "total": 327},
                   "R207 rueckwaerts": {"gebaut": 681, "named": 10990, "nz": 64,
                                        "nz_ziel": 30, "nz_a": 6, "nz_b": 3},
                   "Modi": {"modi": 85},
                   "Programm-Inventar": {"pct": 81.6, "s1": 1690, "total": 2072}}
        rows101 = json.loads(json.dumps(rows100))
        rows101["R207 rueckwaerts"]["gebaut"] = 686
        rows101["R207 rueckwaerts"]["named"] = 11026
        d = {"batches": {}}
        for b in batches:
            d["batches"][str(b)] = {"rows": rows100 if b == 100 else rows101,
                                    "zusatz": {"faelle": 180, "r216a": 259, "r216b": 82,
                                               "r216c": 79, "r216d": 689, "reg_a": 271,
                                               "reg_f": 32}}
        write_json_atomic(self.ana / "_bilanz_snapshot.json", d)


# ------------------------------------------------------------------- stand
class TestStand(Basis):
    def test_ankerkopf_wird_zerlegt(self):
        self.anker()
        kopf = stand.anchor_bloecke(self.cfg)
        self.assertIn("BATCH 101", kopf["Stand"])
        self.assertIn("TEIL 1", kopf["Fertig"])
        self.assertIn("R535", kopf["Naechster Schritt"])
        self.assertIn("Offene Entscheidung", " ".join(kopf.keys()))

    def test_offene_und_geschlossene_posten(self):
        self.anker()
        text = stand.anchor_bloecke(self.cfg)["Offene Entscheidung"]
        offen, geschlossen = stand.offene_entscheidungen(text)
        self.assertEqual(geschlossen, 2)
        self.assertEqual([nr for nr, _t in offen], ["(5)", "(6)"])

    def test_entscheidbare_zeile(self):
        e = stand.entscheidbar("NEU: die Fallfabrik erreicht zwei Bahnen nicht - soll "
                               "`prof` je Kopf MEHRERE MEM-Varianten fahren (Vorschlag: "
                               "**ja**, eigener kleiner Werkzeugschritt)?")
        self.assertIsNotNone(e)
        self.assertEqual(e["frage"], "soll `prof` je Kopf MEHRERE MEM-Varianten fahren?")
        self.assertEqual(e["empfehlung"], "ja")
        self.assertEqual((e["bei_ja"], e["bei_nein"]), ("", ""))

    def test_unklar_formuliert_bleibt_unklar(self):
        self.assertIsNone(stand.entscheidbar(
            "offen bleiben: R330, `M60_NO_EVID`, `NEG_IMM_LO`, die Pins (R381)"))
        # Frage ohne Empfehlung ist ebenfalls nicht entscheidbar.
        self.assertIsNone(stand.entscheidbar("soll der Vorrat wachsen?"))

    def test_folgen_werden_gelesen_wenn_sie_dastehen(self):
        e = stand.entscheidbar("soll die Sonde erweitert werden (Vorschlag: ja)? "
                               "Bei ja: eigener Werkzeugschritt. Bei nein: bleibt offen.")
        self.assertEqual(e["empfehlung"], "ja")
        self.assertIn("eigener Werkzeugschritt", e["bei_ja"])
        self.assertIn("bleibt offen", e["bei_nein"])

    def test_durchsatz_aus_den_bilanzdateien(self):
        self.anker()
        for n, v, h in ((100, 670, 675), (101, 675, 681)):
            self.bilanzdatei(n, v, h)
            self.dokument(n, ck=73 + (n - 100), cf=1752 + (n - 100) * 24,
                          pek=43 - (n - 100), pei=3025 - (n - 100) * 351)
        d = stand.durchsatz(self.cfg, n=5)
        self.assertEqual([e["batch"] for e in d["fenster"]], [101, 100])
        self.assertEqual(d["fenster"][0]["koepfe"], 6)
        self.assertEqual(d["fenster"][1]["koepfe"], 5)
        self.assertAlmostEqual(d["mittel_koepfe"], 5.5)
        self.assertEqual(d["letzter"]["insn"], 351)
        self.assertEqual(d["paket_e"]["paket_e_koepfe"], 42)

    def test_durchsatz_zeilen_nennen_die_quelle_und_hypothesis(self):
        self.anker()
        for n, v, h in ((100, 670, 675), (101, 675, 681)):
            self.bilanzdatei(n, v, h)
            self.dokument(n, ck=73 + (n - 100), cf=1752, pek=43 - (n - 100),
                          pei=3025 - (n - 100) * 351)
        text = "\n".join(stand.durchsatz_zeilen(self.cfg))
        self.assertIn("Mittel der letzten 2", text)
        self.assertIn("offen (Paket E, C-Arbeitsvorrat)", text)
        self.assertIn("HYPOTHESIS", text)
        self.assertIn("_bilanz101.txt", text)
        self.assertIn("Batches fuer die", text)

    def test_median(self):
        self.assertEqual(stand.median([5, 9, 5, 0, 5]), 5)
        self.assertEqual(stand.median([4, 9]), 6.5)
        self.assertIsNone(stand.median([]))

    def test_geplante_koepfe_aus_der_instruktion(self):
        k, i, quelle = stand.geplante_koepfe(REVIEW.split("<DS_INSTRUCTION>")[1])
        self.assertEqual(k, 3)
        self.assertEqual(i, 51 + 71 + 76)
        self.assertIn("TEIL 3", quelle)

    def test_plan_ist_text_mit_median(self):
        self.anker()
        for n, v, h in ((100, 670, 675), (101, 675, 681)):
            self.bilanzdatei(n, v, h)
            self.dokument(n, ck=73, cf=1752, pek=43, pei=3025)
            self.lauf(n, REVIEW.split("<DS_INSTRUCTION>")[1])
        text = stand.plan_ist_text(self.cfg, 5)
        self.assertIn("B101", text)
        self.assertIn("3 Koepfe", text)
        self.assertIn("+6 Koepfe", text)
        self.assertIn("30m07s", text)
        self.assertIn("MEDIAN", text)
        self.assertIn("Ziel des naechsten Batches: hoechstens ca. 7", text)

    def test_fragen_text_entscheidbar_und_unklar(self):
        self.anker()
        d = ensure_dir(self.root / "runs" / "b101")
        write_text_atomic(d / "review.md", REVIEW)
        text = stand.fragen_text(self.cfg, gate={"instruction": "Auftrag: R535",
                                                 "tools": {"source": "user"}})
        self.assertIn("FRAGEN AN DICH (Anker: BATCH 101)", text)
        self.assertIn("NAECHSTER SCHRITT", text)
        # R13y: jede Frage traegt eine Kennung (`A5` fuer den Ankerposten `(5)`).
        self.assertIn("A5", text)
        self.assertIn("ANKERPOSTEN (5): soll `prof` je Kopf MEHRERE MEM-Varianten fahren?",
                      text)
        self.assertIn("Empfehlung: ja", text)
        self.assertIn("A6", text)
        self.assertIn("UNKLAR FORMULIERT", text)
        self.assertIn("2 Posten hat der Reviewer selbst geschlossen", text)
        self.assertIn("WARTET AUF LIVE-AUFNAHME: 0x40B/0x40E/0x40F", text)
        self.assertIn("OFFENER AUFTRAG (VOM NUTZER)", text)
        self.assertIn("ANTWORTEN: /claude <Kennung>", text)
        self.assertIn('/claude A5 ja', text)

    def test_fragen_ohne_anker(self):
        text = stand.fragen_text(self.cfg)
        self.assertIn("FRAGEN AN DICH", text)
        self.assertIn("keine - der Reviewer entscheidet den Regelfall selbst", text)


# ------------------------------------------------------------------- bilanz
class TestBilanzNeu(Basis):
    def test_fortschritt_regeln(self):
        self.assertEqual(bilanz.fortschritt({"pct": 32.1, "gelesen": 105, "total": 327}),
                         (32.1, "105/327"))
        p, basis = bilanz.fortschritt({"insn_gebaut": 4627, "insn_gesamt": 7959})
        self.assertAlmostEqual(p, 58.1, places=1)
        self.assertEqual(basis, "4627/7959 Insn")
        p, basis = bilanz.fortschritt({"gebaut": 100, "offen": 6})
        self.assertAlmostEqual(p, 94.3, places=1)
        p, basis = bilanz.fortschritt({"gebaut": 681, "named": 10990})
        self.assertLess(p, 7.0)
        self.assertIn("benannt", basis)
        self.assertIsNone(bilanz.fortschritt({"modi": 85})[0])
        self.assertIsNone(bilanz.fortschritt(None)[0])

    def test_aenderungen_nur_bewegtes_und_sortiert(self):
        alt = {"R207 rueckwaerts": {"gebaut": 681, "named": 10990},
               "Modi": {"modi": 85},
               "Huelle (A)": {"gebaut": 100, "offen": 6}}
        neu = {"R207 rueckwaerts": {"gebaut": 686, "named": 11026},
               "Modi": {"modi": 85},
               "Huelle (A)": {"gebaut": 100, "offen": 6}}
        bewegt = bilanz.aenderungen(alt, neu)
        self.assertEqual([e["name"] for e in bewegt], ["R207 rueckwaerts"])
        self.assertEqual(bewegt[0]["absolut"], 5)
        self.assertAlmostEqual(bewegt[0]["p_neu"] - bewegt[0]["p_alt"], bewegt[0]["pp"])

    def test_aenderungen_melden_neue_und_entfallene_zeilen(self):
        alt = {"Alt": {"gebaut": 1, "offen": 0}}
        neu = {"Neu": {"gebaut": 1, "offen": 1}}
        namen = [e["name"] for e in bilanz.aenderungen(alt, neu)]
        self.assertIn("Neu", namen)
        self.assertIn("Alt", namen)

    def test_offener_rest_wird_als_offen_gezeigt(self):
        alt = {"Unterbau (B)": {"knoten": 21, "insn": 569, "b": 2276}}
        neu = {"Unterbau (B)": {"knoten": 17, "insn": 465, "b": 1860}}
        bewegt = bilanz.aenderungen(alt, neu)
        self.assertEqual(bewegt[0]["name"], "Unterbau (B)")
        self.assertTrue(bewegt[0]["offen"])
        self.assertIn("offen 569 -> 465 Insn", bilanz._bewegt_zeile(bewegt[0]))

    def test_bericht_reihenfolge_und_gefilterte_tabelle(self):
        self.anker()
        self.snapshot()
        for n, v, h in ((100, 670, 675), (101, 675, 681)):
            self.bilanzdatei(n, v, h)
            self.dokument(n, ck=73 if n == 100 else 78, cf=1752 if n == 100 else 1872,
                          pek=43 if n == 100 else 38, pei=3025 if n == 100 else 2674)
        text = bilanz.bericht(self.cfg, n=1)
        i_kopf = text.index("ZULETZT:")
        i_delta = text.index("WAS SICH GEAENDERT HAT")
        i_gesamt = text.index("GESAMT")
        i_tabelle = text.index("Ast ")
        self.assertLess(i_kopf, i_delta)
        self.assertLess(i_delta, i_gesamt)
        self.assertLess(i_gesamt, i_tabelle)
        self.assertIn("verifiziert  : +5 Koepfe", text)
        self.assertIn("Paket E      : 5 Koepfe / 351 Insn gebaut", text)
        self.assertIn("C verifiziert: 78 Koepfe / 1872 Faelle", text)
        self.assertIn("Durchsatz", text)
        self.assertIn("HYPOTHESIS", text)
        self.assertIn("R207 rueckwaerts", text)          # hat eine Prozentzahl
        self.assertNotIn("Modi          ", text)         # keine Prozentzahl -> weg
        voll = bilanz.bericht(self.cfg, n=1, voll=True)
        self.assertIn("Modi", voll)
        self.assertIn("volle Tabelle: /bilanz voll", text)

    def test_bericht_ohne_schnappschuss(self):
        self.anker()
        text = bilanz.bericht(self.cfg, n=1)
        self.assertIn("kein Bilanz-Schnappschuss gefunden", text)
        self.assertIn("GESAMT", text)

    def test_kurz_satz_kuerzt_an_worthgrenze(self):
        lang = "wort " * 100
        kurz = bilanz._kurz_satz(lang, 40)
        self.assertLessEqual(len(kurz), 45)
        self.assertTrue(kurz.endswith("..."))
        self.assertFalse(kurz.rstrip(".").endswith("wor"))


# ------------------------------------------------- Befehl / CLI / Review-Prompt
class TestBefehl(Basis):
    def test_fragen_befehl_ist_monospace(self):
        self.anker()
        self.assertTrue(self.orch.handle_command("/fragen"))
        text, mono = self.gesagt[-1]
        self.assertTrue(mono)
        self.assertIn("FRAGEN AN DICH", text)
        self.assertIn("ANKERPOSTEN (5): soll `prof`", text)   # R13y: mit Kennung A5
        self.assertIn("A5", text)

    def test_fragen_alias(self):
        self.anker()
        self.assertTrue(self.orch.handle_command("/frage"))
        self.assertIn("FRAGEN AN DICH", self.gesagt[-1][0])

    def test_hilfe_kennt_fragen(self):
        self.assertIn("/fragen", telegram.HELP)

    def test_cli_parser_kennt_fragen(self):
        from hx.cli import build_parser
        with mock.patch.object(sys, "argv", ["hx"]):
            args = build_parser().parse_args(["fragen"])
        self.assertEqual(args.cmd, "fragen")

    def test_cli_ausgabe(self):
        from hx.cli import cmd_fragen
        self.anker()
        args = type("A", (), {"config": None})()
        puffer = io.StringIO()
        with mock.patch("hx.cli.load_config", return_value=self.cfg):
            with redirect_stdout(puffer):
                rc = cmd_fragen(args)
        self.assertEqual(rc, 0)
        self.assertIn("FRAGEN AN DICH", puffer.getvalue())

    def test_review_prompt_hat_plan_ist_tafel_und_median_regel(self):
        prompt = reviewer.build_prompt(self.cfg, "batch_end",
                                       {"batch": 101, "next_batch": 102,
                                        "plan_ist": "Batch | PLAN | IST\nB101 | 3 Koepfe | +5 Koepfe"})
        self.assertIn("PLAN/IST DER LETZTEN BATCHES", prompt)
        self.assertIn("B101 | 3 Koepfe | +5 Koepfe", prompt)
        self.assertIn("MEDIAN", prompt)
        self.assertIn("1,3-fache", prompt.replace("1.3", "1,3"))

    def test_review_context_liefert_plan_ist(self):
        self.anker()
        for n, v, h in ((100, 670, 675), (101, 675, 681)):
            self.bilanzdatei(n, v, h)
            self.dokument(n, ck=73, cf=1752, pek=43, pei=3025)
            self.lauf(n, REVIEW.split("<DS_INSTRUCTION>")[1])
        ctx = self.orch.review_context("(snapshot)")
        self.assertIn("plan_ist", ctx)
        self.assertIn("B101", ctx["plan_ist"])

    def test_reviewer_regeln_enthalten_die_pflichtbloecke(self):
        text = (ROOT / "prompts" / "reviewer.md").read_text(encoding="utf-8")
        self.assertIn("FERTIG WENN:", text)
        self.assertIn("STREICHREIHENFOLGE:", text)
        self.assertIn("Median der verifizierten Menge", text)
        self.assertIn("Werkzeugbau und Serienbau", text)
        self.assertIn("FERTIG WENN", text)
        self.assertIn("Nenne das Ergebnis", text)


if __name__ == "__main__":
    unittest.main()
