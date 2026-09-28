"""Tests fuer R13x: die vier Punkte des Aussensicht-Befunds M208-3.

Der Befund (Beleg `runs/meta-208.md`, Gewicht mittel, Empfaenger Nutzer):

  (a) Die Bilanz zeigte `C verifiziert: 78 Koepfe / 1872 Faelle` statt der Preflight-Zahl
      `78 / 2903` aus B207/B208 - der Parser nahm den ERSTEN Treffer im Dokument, und das
      ist die Vorhersagetafel; weil B207/B208 die Zeile anders schreiben (Backticks,
      fette erste Spalte), fiel er still auf das Dokument von B206 zurueck.
  (b) `Paket E offen ... (Bl 15 / 1083)` kam aus der **Vorhersagespalte** von B206 statt
      aus dem gemessenen Wert `Bl 17 / 1202` (dortige Soll/Ist-Tafel).
  (c) Die Laufzeitspalte der PLAN/IST-Tafel war um einen Batch verschoben (B208 zeigte
      47m26s = b207); gelesen wurde `runs/b<N>/harness-facts.md`, und diese Datei legt
      der Harness in den Ordner des NAECHSTEN Batches.
  (d) `/status` zeigte `letzter Batch 207: $0.0903` - die Live-Zahlen enthalten die
      Ausgabe-Tokens nicht (richtig: `$0.1727` aus `runs/b207/result.json`).

Zwei Sorten Tests:
  * **echte Belege** - die Dateien von B206/B207/B208 im Decomp-Repo, nur lesend; fehlen
    sie (anderer Rechner, aelterer Stand), werden diese Tests uebersprungen.
  * **Attrappen** - eigener Temp-Baum, damit die Regel auch ohne das Decomp-Repo geprueft
    wird (Vorhersage vs. Ist, Preflight vs. Dokument, Luecke in der Reihe).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import bilanz, stand                                        # noqa: E402
from hx.config import load_config                                   # noqa: E402
from hx.orchestrator import Orchestrator, letzter_batch_zeile        # noqa: E402
from hx.util import Log, ensure_dir, write_json_atomic, write_text_atomic  # noqa: E402

ECHTER_CFG = load_config()
DEC = Path(ECHTER_CFG.decomp)
ECHTER_ROOT = Path(ECHTER_CFG.root)


def _echte(nummer: int) -> Path | None:
    """Das Batch-Dokument `port-batch<nummer>-*.md` im echten Decomp-Repo (oder None)."""
    treffer = sorted((DEC / "analysis").glob(f"port-batch{nummer}-*.md"))
    return treffer[-1] if treffer else None


def _belege_fehlen() -> list[int]:
    fehlend: list[int] = []
    for n in (206, 207, 208):
        if _echte(n) is None:
            fehlend.append(n)
        if not (DEC / "analysis" / f"_preflight_{n}.txt").is_file():
            fehlend.append(n)
        if not (ECHTER_ROOT / "runs" / f"b{n:03d}" / "result.json").is_file():
            fehlend.append(n)
    return sorted(set(fehlend))


@unittest.skipIf(_belege_fehlen(), f"echte Belege fehlen: {_belege_fehlen()}")
class TestEchteBelege(unittest.TestCase):
    """M208-3 an den echten Dateien von B206-B208 - der Befund selbst als Regressionsschutz.

    Gelesen wird eine **eingefrorene Kopie** der Belege (`tests/_tmp_r13x_echt`): die
    laufende Harness-Instanz schreibt staendig neue Batch-Dokumente und Preflight-Zeilen,
    und ein Test, der "das Neueste" prueft, waere nach dem naechsten Batch rot, ohne dass
    sich am Code etwas geaendert haette (genau so ist der erste Anlauf gescheitert:
    B209 schrieb waehrend der Testreihe sein Dokument). Kopiert werden nur kleine
    Textdateien; das echte Repo wird ausschliesslich gelesen.
    """

    def setUp(self):
        import shutil
        self.tmp = Path(__file__).resolve().parent / "_tmp_r13x_echt"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "harness")
        self.decomp = ensure_dir(self.tmp / "decomp")
        self.ana = ensure_dir(self.decomp / "analysis")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.decomp)
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        self.cfg = cfg
        q = DEC / "analysis"
        for n in (202, 203, 206, 207, 208):
            if _echte(n) is None:
                continue
            shutil.copy2(_echte(n), self.ana / _echte(n).name)
            if (q / f"_preflight_{n}.txt").is_file():
                shutil.copy2(q / f"_preflight_{n}.txt", self.ana / f"_preflight_{n}.txt")
            for p in (q / f"_m{n}").glob("_bilanz*.txt"):
                shutil.copy2(p, ensure_dir(self.ana / f"_m{n}") / p.name)
        for name in ("_bilanz_snapshot.json",):
            if (q / name).is_file():
                shutil.copy2(q / name, self.ana / name)
        # Laeufe und die verschobene Fakten-Datei (Beleg der Ursache (c)).
        for n in (206, 207, 208):
            ziel = ensure_dir(self.root / "runs" / f"b{n:03d}")
            for name in ("result.json", "auftrag.md", "harness-facts.md"):
                p = ECHTER_ROOT / "runs" / f"b{n:03d}" / name
                if p.is_file():
                    shutil.copy2(p, ziel / name)
        p = ECHTER_ROOT / "runs" / "b209" / "harness-facts.md"
        if p.is_file():
            shutil.copy2(p, ensure_dir(self.root / "runs" / "b209") / p.name)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---------------------------------------------------------------- (a) C Koepfe
    def test_c_koepfe_ist_ist_die_gemessene_zahl(self):
        text = _echte(208).read_text(encoding="utf-8", errors="replace")
        zahlen = stand._zahlen_aus_text(text)
        # Ist-Spalte der Soll/Ist-Tafel (Paragraph 6) - nicht die Vorhersage (Paragraph 5).
        self.assertEqual((zahlen["c_koepfe"], zahlen["c_faelle"]), (78, 2903))
        # Die alte Anzeige kam so zustande: 78*24 = 1872 (Vorhersage aus B206).
        self.assertNotEqual(zahlen["c_faelle"], 1872)
        # B206 fuehrt noch den alten Fallumfang - dort steht die Zahl aber richtig.
        z206 = stand._zahlen_aus_text(_echte(206).read_text(encoding="utf-8",
                                                           errors="replace"))
        self.assertEqual((z206["c_koepfe"], z206["c_faelle"]), (78, 1872))

    def test_preflight_zeile_wird_gelesen(self):
        reihe = {e["batch"]: e for e in stand.preflight_c_koepfe(self.cfg, 8)}
        self.assertEqual((reihe[207]["koepfe"], reihe[207]["faelle"]), (78, 2903))
        self.assertEqual((reihe[208]["koepfe"], reihe[208]["faelle"]), (78, 2903))
        self.assertEqual(reihe[208]["datei"], "_preflight_208.txt")

    def test_kernzahlen_nehmen_die_preflight_zeile(self):
        reihe = {e["batch"]: e for e in stand.kernzahlen(self.cfg, 8)}
        e = reihe[208]
        self.assertEqual((e["c_koepfe"], e["c_faelle"]), (78, 2903))
        self.assertEqual(e["c_quelle"], "_preflight_208.txt")
        # Delta des Batches: Preflight 207 -> 208 (kein neuer C-Kopf).
        self.assertEqual(e["c_koepfe_vorher"], 78)
        self.assertEqual(e["c_faelle_vorher"], 2903)
        # Der neueste Eintrag der Kopie ist B208 (kein laufender Batch stoert).
        self.assertEqual(list(stand.kernzahlen(self.cfg, 8))[-1]["batch"], 208)

    def test_dokument_widerspruch_verliert_gegen_den_preflight(self):
        """B202/B203: das Dokument nennt 53/1272, gemessen sind 45/1080 bzw. 59/1416.

        Die Dokumente liegen mit in der Kopie - so wird die Regel an echten Dateien
        geprueft, nicht nur an einer Attrappe.
        """
        if _echte(202) is None or _echte(203) is None:
            self.skipTest("B202/B203 nicht vorhanden")
        reihe = {e["batch"]: e for e in stand.kernzahlen(self.cfg, 8)}
        self.assertEqual(stand._zahlen_aus_text(
            _echte(202).read_text(encoding="utf-8", errors="replace"))["c_koepfe"], 53)
        self.assertEqual(reihe[202]["c_koepfe"], 45)
        self.assertEqual(reihe[202]["c_quelle"], "_preflight_202.txt")
        self.assertEqual(reihe[203]["c_koepfe"], 59)
        self.assertEqual(reihe[203]["c_quelle"], "_preflight_203.txt")

    def test_gesamt_block_zeigt_die_gemessenen_zahlen(self):
        text = "\n".join(bilanz.gesamt_block(self.cfg))
        self.assertIn("78 Koepfe / 2903 Faelle", text)
        self.assertIn("(B207 -> B208)", text)
        self.assertNotIn("1872", text)
        self.assertIn("_preflight_208.txt", text)

    # ---------------------------------------------------------------- (b) Paket E
    def test_paket_e_ist_spalte_des_neuesten_dokuments(self):
        text = "\n".join(bilanz.gesamt_block(self.cfg))
        self.assertIn("Paket E offen: 38 Koepfe / 2674 Insn (Bl 17 / 1202)", text)
        self.assertNotIn("Bl 15 / 1083", text)

    def test_b206_paket_e_ist_17_1202_nicht_die_vorhersage(self):
        zahlen = stand._zahlen_aus_text(_echte(206).read_text(encoding="utf-8",
                                                              errors="replace"))
        self.assertEqual((zahlen["paket_e_koepfe"], zahlen["paket_e_insn"]), (38, 2674))
        self.assertEqual((zahlen["paket_e_blatt"], zahlen["paket_e_insn_blatt"]),
                         (17, 1202))

    def test_durchsatz_zeilen_nennen_den_gemessenen_paket_e_stand(self):
        text = "\n".join(stand.durchsatz_zeilen(self.cfg))
        self.assertIn("(Bl 17 / 1202)", text)
        self.assertIn('"Paket E offen", Ist-Spalte', text)
        self.assertIn('"C Koepfe", Preflight', text)

    # ---------------------------------------------------------------- (c) Laufzeit
    def test_plan_ist_liest_die_laufzeit_aus_result_json(self):
        reihen = {r["batch"]: r for r in stand.plan_ist(self.cfg, 6)}
        self.assertEqual(reihen[208]["dauer"], "19m20s")      # 1160,907 s
        self.assertEqual(reihen[207]["dauer"], "47m26s")      # 2846,651 s
        self.assertEqual(reihen[206]["dauer"], "58m01s")      # 3481,19 s
        for n in (206, 207, 208):
            self.assertEqual(reihen[n]["dauer_quelle"], "result.json")
            self.assertEqual(reihen[n]["abbruch"], "kein Abbruch")

    def test_die_alte_verschiebung_taucht_nicht_auf(self):
        """b208 zeigte 47m26s - das ist der Wert von b207 (gemessene Verwechslung)."""
        text = stand.plan_ist_text(self.cfg, 1)
        self.assertIn("B208", text)
        self.assertIn("19m20s", text)
        self.assertNotIn("47m26s", text)

    def test_fakten_datei_im_nachbarordner_ist_die_vorherige(self):
        """Beleg der Ursache (c): `runs/b<N>/harness-facts.md` gehoert zu Batch N-1.

        Gemessen: b208 nennt im Kopf "bewertet wird Batch 207" und die Laufzeit 47m26s
        (b207); b209 nennt "Batch 208" und 19m20s (b208). Die Laufzeit des Batches 208
        steht in `runs/b208/result.json` = 1160,907 s = 19m20s.
        """
        runs = Path(self.cfg.sub("runs"))
        f208 = (runs / "b208" / "harness-facts.md").read_text(encoding="utf-8",
                                                              errors="replace")
        f209 = (runs / "b209" / "harness-facts.md").read_text(encoding="utf-8",
                                                              errors="replace")
        self.assertIn("- Review: bewertet wird Batch 207", f208)
        self.assertIn("47m26s", f208)          # = die Laufzeit von b207
        self.assertIn("- Review: bewertet wird Batch 208", f209)
        self.assertIn("19m20s", f209)          # = die Laufzeit von b208
        res = (runs / "b208" / "result.json").read_text(encoding="utf-8")
        self.assertIn("1160.907", res)

    # ---------------------------------------------------------------- (d) /status
    def test_letzter_batch_kommt_aus_result_json(self):
        zeile = letzter_batch_zeile(self.cfg, {"batch": 208, "requests": 76,
                                               "cost_usd": 0.051239, "output": 0})
        self.assertIn("letzter Batch 208", zeile)
        self.assertIn("$0.1232", zeile)         # result.json, nicht die Live-Zahl
        self.assertIn("118786 Ausgabe-Tokens", zeile)
        self.assertIn("19m20s", zeile)
        self.assertIn("runs/b208/result.json", zeile)
        self.assertNotIn("0.0512", zeile)


# =========================================================== Attrappen
DOKU_ATT = """# Batch {n}

**1. Inventar.** {inv_k} Koepfe / {inv_i} Insn im Programm-Inventar, davon
**{baut_k} Koepfe / {baut_i} Insn** in der Bau-Liste. **OFFEN: {off_k} Koepfe /
{off_i} Insn.** Davon haben **{bl_k} Koepfe / {bl_i} Insn** keinen offenen Ruf.

## 5. VORHERSAGE (Soll je Bilanzzeile)

| Bilanzzeile | Zaehlerdefinition | Soll B{n} |
|---|---|---|
| `C Koepfe` | registrierte Koepfe / Faelle / Abweichungen (`c_kopf_check.py`) | **{ck_soll} / {cf_soll} / 0** |
| `Paket E` offen | `c_kopf.py paket_e` (keine Preflight-Zeile) | **{pek_soll} / {pei_soll} (Blaetter {pbl_soll} / {pbi_soll})** |

## 6. Abweichungen Soll/Ist

| Zeile | Soll | Ist | Abweichung |
|---|---|---|---|
| **`C Koepfe`** | {ck_soll} / {cf_soll} / 0 | **{ck} / {cf} / 0** | keine |
| Paket E offen | {pek_soll} / {pei_soll}, Blaetter {pbl_soll} / {pbi_soll} | **{pek} / {pei}, Blaetter {pbl} / {pbi}** | keine, die Blattzahl steigt um {pbi} gegen die Rechnung |
"""

BILANZDATEI = """## PFLICHT-BILANZ ALLER GETRACKTEN AESTE (Stand: **Batch {n}**)

| Ast / Kern | Vorbatch (B{vm}) | **heute (mit {n})** | Quelle |
|---|---|---|---|
| **R207 rueckwaerts** | **{v}** (a 30 / b 0 / c 0) | **{h}** (a 30 / b 0 / c 0) | `preflight.py` |
"""


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__file__).resolve().parent / "_tmp_r13x"
        if self.tmp.exists():
            import shutil
            shutil.rmtree(self.tmp, ignore_errors=True)
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
        self.orch.say = lambda *a, **k: None

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ------------------------------------------------------------- Fixture
    def dokument(self, n: int, ck: int, cf: int, pek: int, pei: int, pbl: int = 17,
                 pbi: int = 1202, ck_soll: int | None = None, cf_soll: int | None = None,
                 pek_soll: int | None = None, pei_soll: int | None = None,
                 pbl_soll: int = 20, pbi_soll: int = 1434) -> None:
        write_text_atomic(self.ana / f"port-batch{n}-attrappe.md", DOKU_ATT.format(
            n=n, inv_k=2072, inv_i=123771, baut_k=600 + n, baut_i=29000 + n,
            off_k=1400, off_i=94000, bl_k=664, bl_i=31690,
            ck=ck, cf=cf, ck_soll=ck if ck_soll is None else ck_soll,
            cf_soll=cf if cf_soll is None else cf_soll,
            pek=pek, pei=pei, pbl=pbl, pbi=pbi,
            pek_soll=pek if pek_soll is None else pek_soll,
            pei_soll=pei if pei_soll is None else pei_soll,
            pbl_soll=pbl_soll, pbi_soll=pbi_soll))

    def preflight(self, n: int, ck: int, cf: int) -> None:
        write_text_atomic(self.ana / f"_preflight_{n}.txt",
                          "Pruefung           Ergebnis              Urteil\n"
                          f"C Koepfe           {ck} / {cf} / 0        OK\n")

    def bilanzdatei(self, n: int, v: int, h: int) -> None:
        d = ensure_dir(self.ana / f"_m{n}")
        write_text_atomic(d / f"_bilanz{n}.txt", BILANZDATEI.format(n=n, vm=n - 1, v=v, h=h))

    def result(self, n: int, sekunden: float, abbruch: str | None = None,
               kosten: float = 0.1, anfragen: int = 10, ausgabe: int = 5000) -> None:
        d = ensure_dir(self.root / "runs" / f"b{n}")
        write_json_atomic(d / "result.json",
                          {"batch": n, "rc": 0, "duration_s": sekunden,
                           "killed_reason": abbruch, "cost_usd": kosten,
                           "stats": {"requests": anfragen, "output": ausgabe},
                           "finished_at": "2026-09-28T17:21:31+00:00"})

    def fakten(self, ordner: int, bewertet: int, dauer: str = "30m07s",
               abbruch: str = "kein Abbruch") -> None:
        d = ensure_dir(self.root / "runs" / f"b{ordner}")
        write_text_atomic(d / "harness-facts.md",
                          f"- Review: bewertet wird Batch {bewertet}; die Instruktion "
                          f"gilt fuer Batch {bewertet + 1}\n"
                          f"- Exit-Code: 0 | Laufzeit: {dauer} (Wanduhr) | "
                          f"Abbruchgrund: {abbruch}\n")


# ---------------------------------------------------------------- Parser (a/b)
class TestParser(Basis):
    def test_letzte_zeile_gewinnt(self):
        self.dokument(101, ck=78, cf=2903, pek=38, pei=2674, ck_soll=78, cf_soll=1872)
        text = (self.ana / "port-batch101-attrappe.md").read_text(encoding="utf-8")
        zahlen = stand._zahlen_aus_text(text)
        self.assertEqual((zahlen["c_koepfe"], zahlen["c_faelle"]), (78, 2903))
        self.assertEqual((zahlen["paket_e_koepfe"], zahlen["paket_e_insn"]), (38, 2674))
        self.assertEqual((zahlen["paket_e_blatt"], zahlen["paket_e_insn_blatt"]),
                         (17, 1202))

    def test_nur_vorhersagetafel_ergibt_keinen_ist_wert_aus_prosa(self):
        """Ohne Soll/Ist-Tafel wird die Vorhersagezeile NICHT als Messwert ausgegeben."""
        text = ("| Bilanzzeile | Zaehlerdefinition | Soll B101 |\n"
                "|---|---|---|\n"
                "| C Koepfe | registrierte Koepfe / Faelle (`c_kopf_check.py`) "
                "| **78 / 2903 / 0** |\n")
        zeile, wert = stand.ist_wert(text, stand._ETIKETT_CKOPF, stand._RE_ZAHL_CKOPF)
        self.assertEqual(wert, (78, 2903, 0))
        self.assertEqual(zeile, 3)
        # Prosa NACH der Wertspalte wird nicht als Wert gelesen.
        text2 = ("| Zeile | Soll | Ist | Abweichung |\n|---|---|---|---|\n"
                 "| **C Koepfe** | 73 / 1752 / 0 | **78 / 2903 / 0** "
                 "| je Kopf 24 Faelle, 59+5 = 64 |\n")
        _nr, wert2 = stand.ist_wert(text2, stand._ETIKETT_CKOPF, stand._RE_ZAHL_CKOPF)
        self.assertEqual(wert2, (78, 2903, 0))

    def test_prosa_zelle_wird_nicht_als_wert_gelesen(self):
        text = ("| Paket E offen | Vorbatch | Soll |\n|---|---|---|\n"
                "| Paket E offen | 42 / 2974, Blaetter 12 / 1072 "
                "| **43 / 3025, Blaetter 20 / 1434** (Summe der 9: 35+38 = 73) |\n")
        _zeile, wert = stand.ist_wert(text, stand._ETIKETT_PAKET_E, stand._RE_ZAHL_PAKET_E)
        self.assertEqual(wert, (43, 3025, 20, 1434))

    def test_etikett_mit_backticks_und_fetter_erster_spalte(self):
        text = ("| **`C Koepfe`** | EINE Zeile aus `c_kopf_check.py` "
                "(registrierte Koepfe / Faelle) | 78 / 1872 / 0 | **78 / 2903 / 0** |\n")
        _zeile, wert = stand.ist_wert(text, stand._ETIKETT_CKOPF, stand._RE_ZAHL_CKOPF)
        self.assertEqual(wert, (78, 2903, 0))

    def test_ohne_zeile_kein_wert(self):
        _zeile, wert = stand.ist_wert("# nichts\n\nkein Text mit Zahlen\n",
                                      stand._ETIKETT_CKOPF, stand._RE_ZAHL_CKOPF)
        self.assertIsNone(wert)


# ---------------------------------------------------------------- Quellenreihe (a)
class TestKernzahlen(Basis):
    def test_preflight_schlaegt_das_dokument(self):
        """B202/B203-Form: das Dokument nennt 53/1272, gemessen sind 45/1080."""
        self.dokument(202, ck=53, cf=1272, pek=43, pei=3025)
        self.preflight(201, 45, 1080)
        self.preflight(202, 45, 1080)
        reihe = {e["batch"]: e for e in stand.kernzahlen(self.cfg, 8)}
        self.assertEqual(reihe[202]["c_koepfe"], 45)
        self.assertEqual(reihe[202]["c_faelle"], 1080)
        self.assertEqual(reihe[202]["c_quelle"], "_preflight_202.txt")

    def test_ohne_preflight_zaehlt_die_ist_spalte(self):
        self.dokument(202, ck=53, cf=1272, pek=43, pei=3025)
        reihe = {e["batch"]: e for e in stand.kernzahlen(self.cfg, 8)}
        self.assertEqual(reihe[202]["c_koepfe"], 53)
        self.assertEqual(reihe[202]["c_quelle"], "port-batch202-attrappe.md")

    def test_vorgaengerwert_und_luecke(self):
        """Paket E: B206 -> B208, weil B207 die Zeile nicht fuehrt (`vorher_batch`)."""
        self.dokument(206, ck=78, cf=1872, pek=38, pei=2674, pbl=17, pbi=1202)
        write_text_atomic(self.ana / "port-batch207-attrappe.md",
                          "# Batch 207 ohne Paket-E-Zeile\n\n"
                          "| Zeile | Soll | Ist | Abweichung |\n|---|---|---|---|\n"
                          "| **C Koepfe** | 78 / 2903 / 0 | **78 / 2903 / 0** | keine |\n")
        self.dokument(208, ck=78, cf=2903, pek=38, pei=2674, pbl=17, pbi=1202)
        reihe = {e["batch"]: e for e in stand.kernzahlen(self.cfg, 8)}
        self.assertNotIn("paket_e_koepfe", reihe[207])
        self.assertEqual(reihe[207]["c_koepfe"], 78)
        self.assertEqual(reihe[208]["paket_e_koepfe_vorher"], 38)
        self.assertEqual(reihe[208]["vorher_batch"]["paket_e_koepfe"], 206)
        self.assertEqual(reihe[208]["c_koepfe_vorher"], 78)
        self.assertNotIn("vorher_batch", reihe[208].get("c_quelle", ""))

    def test_gesamt_block_nennt_quelle_und_vergleichsbatch(self):
        self.dokument(207, ck=78, cf=2903, pek=38, pei=2674)
        self.dokument(208, ck=78, cf=2903, pek=38, pei=2674)
        self.preflight(207, 78, 2903)
        self.preflight(208, 78, 2903)
        text = "\n".join(bilanz.gesamt_block(self.cfg))
        self.assertIn("78 Koepfe / 2903 Faelle", text)
        self.assertIn("+0 Koepfe / +0 Faelle (B207 -> B208)", text)
        self.assertIn("[B208, _preflight_208.txt]", text)
        self.assertIn("(Bl 17 / 1202)", text)
        self.assertIn("(B207 -> B208): 0 Koepfe / 0 Insn gebaut", text)

    def test_laufender_batch_ohne_zahlen_streicht_die_zeile_nicht(self):
        """Ein gerade Laufender schreibt sein Dokument, bevor die Preflight-Zeile da ist.

        Gemessen an B209 (2026-09-28): dessen Dokument fuehrt die Zeile
        `| C Koepfe | KOPF_DEF-Eintraege | unveraendert 78/2903 | 78/2903 |` - kein
        Zahlen-Tripel und keine Preflight-Datei. Die Anzeige muss dann den **letzten
        Batch MIT Messwert** zeigen (und ihn nennen), nicht die Zeile wegfallen lassen.
        """
        self.dokument(208, ck=78, cf=2903, pek=38, pei=2674)
        self.preflight(208, 78, 2903)
        write_text_atomic(self.ana / "port-batch209-attrappe.md",
                          "# Batch 209 (laeuft)\n\n"
                          "| Zeile | Zaehlerdefinition | Soll | Ist | Abweichung |\n"
                          "|---|---|---|---|---|\n"
                          "| `C Koepfe` | `KOPF_DEF`-Eintraege | unveraendert "
                          "78/2903 | 78/2903 | kein neuer Kopf |\n")
        text = "\n".join(bilanz.gesamt_block(self.cfg))
        self.assertIn("78 Koepfe / 2903 Faelle", text)
        self.assertIn("[B208, _preflight_208.txt]", text)
        self.assertIn("(Bl 17 / 1202)", text)


# ---------------------------------------------------------------- Laufzeit (c)
class TestLaufzeit(Basis):
    def test_result_json_gewinnt(self):
        self.result(208, 1160.907)
        self.fakten(208, 207, dauer="47m26s")          # die verschobene Datei
        self.fakten(209, 208, dauer="19m20s")          # die richtige
        lauf = stand.lauf_ist(self.cfg, 208)
        self.assertEqual(lauf["dauer"], "19m20s")
        self.assertEqual(lauf["quelle"], "result.json")

    def test_die_verschobene_fakten_datei_im_eigenen_ordner_wird_nie_gelesen(self):
        self.fakten(208, 207, dauer="47m26s")          # nur die falsche liegt vor
        lauf = stand.lauf_ist(self.cfg, 208)
        self.assertEqual(lauf["dauer"], "")            # nichts wird geraten
        self.assertEqual(lauf["quelle"], "")

    def test_rueckfall_nur_mit_passender_kopfzeile(self):
        self.result(207, 2846.651, abbruch="hard_wall")
        self.assertEqual(stand.lauf_ist(self.cfg, 207)["abbruch"], "hard_wall")
        self.fakten(208, 207, dauer="47m26s")
        self.fakten(209, 999, dauer="1m00s")           # falscher Batch im Kopf
        (self.root / "runs" / "b207" / "result.json").unlink()
        lauf = stand.lauf_ist(self.cfg, 207)
        self.assertEqual(lauf["dauer"], "47m26s")
        self.assertEqual(lauf["quelle"], "harness-facts.md (b208)")

    def test_tafel_nennt_die_quelle_und_markiert_den_rueckfall(self):
        self.bilanzdatei(207, 675, 681)
        self.fakten(208, 207, dauer="47m26s")
        (self.root / "runs" / "b207").mkdir(parents=True, exist_ok=True)
        write_json_atomic(self.root / "runs" / "b207" / "result.json",
                          {"batch": 207, "duration_s": 2846.651, "killed_reason": None})
        text = stand.plan_ist_text(self.cfg, 1)
        self.assertIn("Laufzeit (result.json)", text)
        self.assertIn("47m26s", text)
        self.assertNotIn("* Laufzeit NICHT aus", text)     # kein Rueckfall noetig

    def test_dauer_sekunden_schneidet_ab(self):
        self.assertEqual(stand.dauer_sekunden(2846.651), "47m26s")
        self.assertEqual(stand.dauer_sekunden(75.9), "1m15s")
        self.assertEqual(stand.dauer_sekunden(3600), "1h00m00s")
        self.assertEqual(stand.dauer_sekunden(None), "")


# ---------------------------------------------------------------- /status (d)
class TestStatus(Basis):
    def test_letzter_batch_aus_result_json(self):
        self.result(207, 2846.651, kosten=0.172692, anfragen=137, ausgabe=137354)
        zeile = letzter_batch_zeile(self.cfg, {"batch": 207, "requests": 135,
                                               "cost_usd": 0.090279, "output": 0})
        self.assertIn("letzter Batch 207", zeile)
        self.assertIn("$0.1727", zeile)
        self.assertIn("137354 Ausgabe-Tokens", zeile)
        self.assertNotIn("0.0902", zeile)
        self.assertIn("runs/b207/result.json", zeile)

    def test_ohne_result_json_bleiben_die_live_zahlen_mit_warnung(self):
        zeile = letzter_batch_zeile(self.cfg, {"batch": 207, "requests": 135,
                                               "cost_usd": 0.090279, "output": 0},
                                    stand="16:05")
        self.assertIn("$0.0903", zeile)
        self.assertIn("OHNE Ausgabe-Tokens", zeile)
        self.assertIn("runs/b207/result.json fehlt", zeile)

    def test_laufender_batch_warnt_vor_den_fehlenden_ausgabe_tokens(self):
        self.orch.state.data["live"] = {"batch": 209, "ts": "2026-09-28T17:45:19+00:00",
                                        "requests": 4, "cost_usd": 0.00714,
                                        "input_miss": 45522, "cache_read": 104064,
                                        "output": 0}
        zeile = self.orch.live_batch_zeile()
        self.assertIn("Laufender Batch 209", zeile)
        self.assertIn("OHNE Ausgabe-Tokens", zeile)

    def test_laufender_batch_mit_ausgabe_tokens_ohne_warnung(self):
        self.orch.state.data["live"] = {"batch": 209, "ts": "2026-09-28T17:45:19+00:00",
                                        "requests": 4, "cost_usd": 0.00714,
                                        "input_miss": 45522, "cache_read": 104064,
                                        "output": 120}
        self.assertNotIn("OHNE Ausgabe-Tokens", self.orch.live_batch_zeile())

    def test_status_zeigt_die_neue_zeile(self):
        self.result(207, 2846.651, kosten=0.172692, anfragen=137, ausgabe=137354)
        self.orch.state.data["live_letzte"] = {"batch": 207, "requests": 135,
                                               "cost_usd": 0.090279, "output": 0,
                                               "ts": "2026-09-28T16:05:00+00:00"}
        self.orch.state.data["live"] = None
        text = self.orch.status_text()
        self.assertIn("letzter Batch 207", text)
        self.assertIn("$0.1727", text)


if __name__ == "__main__":
    unittest.main()
