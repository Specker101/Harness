"""Tests fuer R13aa (2026-09-28): Aussensicht-Nachbesserung aus `runs/meta-209.md`.

Auftrag (Nutzer, drei Punkte):

  1. **Fehlausloeser**: "Kernzahl ohne Bewegung" hat B208/B209 als C-Batches gezaehlt -
     beide waren B-Batches. Die Pflichtzeile `B-SCHRITT:` fehlte (auch im B210-Review).
     Die Klassifikation darf NICHT allein an der Reviewer-Zeile haengen: zusaetzlich
     `DS_INSTRUCTION` ("Strang B", "B-Batch") und `hybrid-plan.md`. Fehlt die Pflichtzeile,
     wird im Review-Protokoll gewarnt. Test mit den echten Reviews B207-B210.
  2. **Beleg-Regel**: M209-4 wurde verworfen, obwohl die Zahlen aus den Eingabedaten
     stammen. Als Beleg gelten auch "Eingabe <Abschnitt>" bzw. `runs/b<N>/result.json`;
     verworfene Befunde werden nicht weggeworfen, sondern in `/fragen` als
     "verworfen - pruefen?" gezeigt.
  3. **Hochrechnung**: getrennt ausweisen - Durchsatz je C-Batch, Anteil C-Batches
     (Mischverhaeltnis), daraus Kalender-Batches.

Zwei Sorten Tests: **echte Belege** (B207-B210 + `hybrid-plan.md`, nur lesend kopiert,
uebersprungen wenn sie fehlen) und **Attrappen** in `tests/_tmp_r13aa`.
"""

from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import aussensicht, bilanz, fragen, stand              # noqa: E402
from hx.config import load_config                               # noqa: E402
from hx.orchestrator import Orchestrator                        # noqa: E402
from hx.util import Log, ensure_dir, write_json_atomic, write_text_atomic  # noqa: E402

ECHTER_CFG = load_config()
DEC = Path(ECHTER_CFG.decomp)
ECHTER_ROOT = Path(ECHTER_CFG.root)

# Der Befund, an dem die Beleg-Regel gescheitert ist (Wortlaut aus `runs/meta-209.md`).
M209_4 = ("Laufzeiten aus den Kosten und Laufzeiten je Batch: B201 18,1 min, B202 25,2 "
          "min, B208 19,3 min, B209 28,0 min bei einem Budget von 80 min; Entscheidung "
          "aus dem Review in `runs/b206`")


def _echte_fehlen() -> list[str]:
    fehlend: list[str] = []
    for n in (207, 208, 209):
        if not (ECHTER_ROOT / "runs" / f"b{n:03d}" / "auftrag.md").is_file():
            fehlend.append(f"runs/b{n:03d}/auftrag.md")
    if not (DEC / "analysis" / "hybrid-plan.md").is_file():
        fehlend.append("analysis/hybrid-plan.md")
    return fehlend


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13aa"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "harness")
        self.decomp = ensure_dir(self.tmp / "decomp")
        self.ana = ensure_dir(self.decomp / "analysis")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.decomp)
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        cfg.data["paths"]["harness_home"] = str(self.tmp)
        cfg.data["telegram"]["allowlist_user_ids"] = []
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ------------------------------------------------------------- Fixture
    def auftrag(self, batch: int, text: str) -> None:
        d = ensure_dir(self.root / "runs" / f"b{batch:03d}")
        write_text_atomic(d / "auftrag.md", text)

    def review(self, batch: int, summary: str) -> None:
        """`summary` ist die Zusammenfassung des Reviews, das `batch` BEWERTET hat."""
        d = ensure_dir(self.root / "runs" / f"b{batch + 1:03d}")
        write_text_atomic(d / "review.md",
                          f"<TELEGRAM_SUMMARY>\n{summary}\n</TELEGRAM_SUMMARY>\n")

    def preflight(self, batch: int, koepfe: int, faelle: int, abw: int = 0) -> None:
        write_text_atomic(self.ana / f"_preflight_{batch}.txt",
                          f"Lauf B{batch}\nC Koepfe           {koepfe} / {faelle} / {abw}     OK\n")

    def plan(self, zeile: str) -> None:
        write_text_atomic(self.ana / "hybrid-plan.md",
                          f"# Plan fuer Strang B - Hybrid-Laeufer\n\n{zeile}\n")

    def orch(self) -> Orchestrator:
        o = Orchestrator(self.cfg, self.log, mock=True,
                         state_file=self.root / "state" / "run.json")
        o.qroot = self.root
        o.said = []
        o.say = lambda t="", *a, **k: o.said.append(str(t))
        o.state.data["batch"] = 209
        o.state.save()
        return o


# ------------------------------------------------------ 1) Klassifikation (echt)
@unittest.skipIf(_echte_fehlen(), f"echte Belege fehlen: {_echte_fehlen()}")
class TestEchteBelege(unittest.TestCase):
    """Die Klassifikation an den echten Belegen B207-B210 (der Ausloeser-Fehler selbst)."""

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13aa_echt"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "harness")
        self.decomp = ensure_dir(self.tmp / "decomp")
        self.ana = ensure_dir(self.decomp / "analysis")
        # Eingefrorene Kopien: die laufende Harness-Instanz schreibt staendig neue
        # Reviews/Auftraege - ein Test an "dem Neuesten" waere nach dem naechsten
        # Batch rot, ohne dass sich am Code etwas geaendert haette.
        for n in (207, 208, 209, 210):
            p = ECHTER_ROOT / "runs" / f"b{n:03d}" / "auftrag.md"
            if p.is_file():
                shutil.copy2(p, ensure_dir(self.root / "runs" / f"b{n:03d}") / "auftrag.md")
        for n in (208, 209, 210):
            p = ECHTER_ROOT / "runs" / f"b{n:03d}" / "review.md"
            if p.is_file():
                shutil.copy2(p, ensure_dir(self.root / "runs" / f"b{n:03d}") / "review.md")
        shutil.copy2(DEC / "analysis" / "hybrid-plan.md", self.ana / "hybrid-plan.md")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.decomp)
        cfg.data["paths"]["prompts"] = str(ROOT / "prompts")
        self.cfg = cfg

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_mischverhaeltnis_aus_dem_plan(self):
        p = stand.plan_mischung(self.cfg)
        self.assertAlmostEqual(p["anteil"], 1 / 3, places=3)
        self.assertEqual(p["paare"].get(208), "B")
        self.assertEqual(p["paare"].get(209), "B")
        self.assertEqual(p["paare"].get(210), "C")

    def test_b208_und_b209_sind_b_batches(self):
        # B208: Marker im Auftrag; B209: Zeile "Strang B, Batch 2 ..." im Auftrag.
        self.assertEqual(stand.strang_von_batch(self.cfg, 208)["strang"], "B")
        self.assertEqual(stand.strang_von_batch(self.cfg, 209)["strang"], "B")
        # B210: nur der Plan nennt ihn (der Auftrag entsteht erst, wenn er laeuft).
        self.assertEqual(stand.strang_von_batch(self.cfg, 210)["strang"], "C")
        # B207: kein Beleg -> unbekannt, NICHT geraten (zaehlt wie bisher als C-Batch).
        self.assertEqual(stand.strang_von_batch(self.cfg, 207)["strang"], "")
        self.assertFalse(aussensicht.ist_b_batch(self.cfg, 206))
        self.assertTrue(aussensicht.ist_b_batch(self.cfg, 208))

    def test_fremde_erwaehnung_klassifiziert_nicht(self):
        """Der b209-Auftrag nennt 'B210 = C-Batch' - das macht B209 nicht zum C-Batch."""
        text = stand._auftrag_zu_batch(self.cfg, 209)
        self.assertIn("B210", text)
        self.assertEqual(stand.strang_von_batch(self.cfg, 209)["strang"], "B")

    def test_pflichtzeile_fehlt_in_den_echten_reviews(self):
        fehlend = stand.ohne_pflichtzeile(self.cfg)
        self.assertIn(208, fehlend)
        self.assertIn(209, fehlend)
        self.assertNotIn(207, fehlend)          # kein B-Batch
        self.assertNotIn(210, fehlend)          # kein B-Batch

    def test_beleg_von_m209_4_gilt_jetzt(self):
        self.assertTrue(aussensicht.beleg_gueltig(M209_4))

    def test_bilanz_weist_die_hochrechnung_getrennt_aus(self):
        # Der Fehler war: "ca. 369 Batches" ohne Mischverhaeltnis (Befund M209-3).
        text = "\n".join(stand.durchsatz_zeilen(ECHTER_CFG))
        self.assertIn("je C-Batch", text)
        self.assertIn("KALENDER-Batches", text)
        self.assertIn("Mischung", text)
        self.assertNotIn("Batches fuer die", text)


# --------------------------------------------------------- 1) Klassifikation (Attrappen)
class TestKlassifikation(Basis):
    def test_auftrag_nennt_den_batch(self):
        self.auftrag(208, "B208 ist der ERSTE Batch von Strang B (Nutzerentscheidung A4).")
        self.assertEqual(stand.strang_von_batch(self.cfg, 208)["strang"], "B")
        self.auftrag(210, "Naechster Batch: B210 ist ein C-Batch. Er korrigiert F1/F2.")
        self.assertEqual(stand.strang_von_batch(self.cfg, 210)["strang"], "C")

    def test_auftragszeile_beginnt_mit_dem_strang(self):
        self.auftrag(209, "Lage: ...\nStrang B, Batch 2 von hoechstens 20; Abbruch nach 10.\n"
                          "TEIL 1: x\n")
        self.assertEqual(stand.strang_von_batch(self.cfg, 209)["strang"], "B")

    def test_plan_ist_die_dritte_quelle(self):
        self.plan("- **Mischverhaeltnis 2 B : 1 C (ENTSCHEIDUNG Reviewer):** "
                  "B208 B, B209 B, B210 C")
        self.assertEqual(stand.strang_von_batch(self.cfg, 210)["strang"], "C")
        self.assertIn("hybrid-plan", stand.strang_von_batch(self.cfg, 210)["quelle"])

    def test_pflichtzeile_schlaegt_alle_anderen_quellen(self):
        self.plan("- **Mischverhaeltnis 2 B : 1 C:** B208 B, B209 B, B210 C")
        self.review(210, "Ergebnis: x\nB-SCHRITT: kein B-Batch (Strang C)")
        self.assertEqual(stand.strang_von_batch(self.cfg, 210)["strang"], "C")
        self.review(210, "Ergebnis: x\nB-SCHRITT: 3/5 Kern, B-Batch 3 von max 20")
        self.assertEqual(stand.strang_von_batch(self.cfg, 210)["strang"], "B")
        self.assertIn("B-SCHRITT", stand.strang_von_batch(self.cfg, 210)["quelle"])

    def test_unbekannt_bleibt_unbekannt(self):
        self.auftrag(207, "Bau 23 Koepfe, Bilanz, Preflight.")     # kein Marker
        s = stand.strang_von_batch(self.cfg, 207)
        self.assertEqual(s["strang"], "")
        self.assertEqual(s["quelle"], "")
        self.assertFalse(aussensicht.ist_b_batch(self.cfg, 207))

    def test_fremder_batch_macht_keinen_b_batch(self):
        self.auftrag(209, "Der naechste Batch B210 ist ein C-Batch; B211 wird wieder B.")
        self.assertEqual(stand.strang_von_batch(self.cfg, 209)["strang"], "")

    def test_kaputte_planzeile_ergibt_nichts(self):
        self.plan("- **Mischverhaeltnis** offen (noch nicht entschieden)")
        self.assertEqual(stand.plan_mischung(self.cfg), {})

    def test_hinweis_und_warnung(self):
        # B208 ist ein B-Batch (Marker im Auftrag), sein Review nennt die Pflichtzeile nicht
        # -> genau die Lage aus dem Auftrag.
        self.auftrag(208, "B208 ist der ERSTE Batch von Strang B.")
        self.review(208, "Ergebnis: x (ohne Pflichtzeile)")
        h = stand.pflichtzeile_hinweis(self.cfg, 208)
        self.assertIn("B208 ist ein B-Batch", h)
        self.assertIn("B-SCHRITT", h)
        self.assertIn("B208", h)                      # die fehlenden werden genannt
        self.review(208, "B-SCHRITT: 2/5 Maschine, B-Batch 2 von max 20")
        self.assertNotIn("fehlte sie in", stand.pflichtzeile_hinweis(self.cfg, 208))
        self.auftrag(210, "B210 ist ein C-Batch.")
        self.assertIn("kein B-Batch (Strang C)", stand.pflichtzeile_hinweis(self.cfg, 210))
        # Gar kein Beleg: dann wird das gesagt - und die Zeile verlangt.
        self.assertIn("nicht belegbar", stand.pflichtzeile_hinweis(self.cfg, 211))


class TestStillstand(Basis):
    def test_b_batches_werden_ausgelassen(self):
        """Der Fehlausloeser selbst: gleiche C-Zahlen in einem B-Batch duerfen nicht feuern."""
        for n in (205, 206, 207, 208, 209):
            self.preflight(n, 78, 2903)
        self.auftrag(208, "B208 ist der ERSTE Batch von Strang B.")
        self.auftrag(209, "Strang B, Batch 2 von hoechstens 20.")
        stehend = aussensicht.kernzahl_stillstand(self.cfg)
        self.assertTrue(stehend, "B206/B207 stehen still - das MUSS melden")
        text = " ".join(stehend)
        self.assertIn("wie B207", text)
        self.assertNotIn("B209", text)          # B209 ist ein B-Batch

    def test_ohne_klassifikation_feuert_es_falsch(self):
        """Gegenprobe: waeren alle Batches C, wuerde der Ausloeser B208/B209 melden."""
        for n in (205, 206, 207, 208, 209):
            self.preflight(n, 78, 2903)
        text = " ".join(aussensicht.kernzahl_stillstand(self.cfg))
        self.assertIn("B208 wie B209", text)

    def test_meldung_im_review(self):
        self.auftrag(209, "Strang B, Batch 2 von hoechstens 20.")
        self.review(209, "Ergebnis: x (ohne Pflichtzeile)")
        o = self.orch()
        res = type("R", (), {})()
        res.parsed = type("P", (), {"summary": "Ergebnis: x ohne Zeile"})()
        res.review_file = "runs/b210/review.md"
        self.assertEqual(o.pflichtzeile_melden(res), ["B209: B-SCHRITT fehlt"])
        self.assertIn("Pflichtzeile B-SCHRITT fehlt",
                      (self.tmp / "log.jsonl").read_text(encoding="utf-8"))
        # Mit Pflichtzeile: keine Meldung.
        res.parsed.summary = "Ergebnis: x\nB-SCHRITT: 2/5 Maschine, B-Batch 2 von max 20"
        self.assertEqual(o.pflichtzeile_melden(res), [])

    def test_review_prompt_traegt_die_warnung(self):
        from hx import reviewer
        self.auftrag(209, "Strang B, Batch 2 von hoechstens 20.")
        o = self.orch()
        ctx = o.review_context("(Snapshot)")
        self.assertIn("B209 ist ein B-Batch", ctx["protokoll_warnung"])
        prompt = reviewer.build_prompt(self.cfg, "batch_end", ctx)
        self.assertIn("=== PROTOKOLL-WARNUNG (Pflichtzeilen im Review) ===", prompt)
        self.assertIn("B209 ist ein B-Batch", prompt)
        leer = reviewer.build_prompt(self.cfg, "batch_end", {"batch": 1})
        self.assertIn("nichts offen", leer)


# --------------------------------------------------------------- 2) Beleg-Regel
class TestBeleg(Basis):
    def test_m209_4_gilt(self):
        self.assertTrue(aussensicht.beleg_gueltig(M209_4))

    def test_neue_formen(self):
        for gut in ("Eingabe Kosten und Laufzeiten je Batch",
                    "Eingabe: /fragen",
                    "=== KOSTEN UND LAUFZEITEN JE BATCH ===",
                    "runs/b209",
                    "runs/b209/result.json",
                    "runs\\b206"):
            self.assertTrue(aussensicht.beleg_gueltig(gut), gut)

    def test_alte_formen_bleiben(self):
        for gut in ("port/src/ckopf_leaves.cpp:1977", "137 Anfragen in runs/b207/result.json",
                    "Fehlstelle: gesucht in analysis/, nicht gefunden"):
            self.assertTrue(aussensicht.beleg_gueltig(gut), gut)

    def test_ohne_beleg_bleibt_verworfen(self):
        for schlecht in ("", "   ", "ich glaube, das ist ungenau",
                         "das Gefuehl sagt mir etwas anderes"):
            self.assertFalse(aussensicht.beleg_gueltig(schlecht), schlecht)


class TestVerworfene(Basis):
    def test_verworfene_bekommen_eine_kennung_und_bleiben(self):
        ids = aussensicht.verworfene_speichern(self.cfg, 209, [
            {"n": 4, "gewicht": "mittel", "aussage": "Vier Batches kein Kopf",
             "beleg": M209_4, "empfehlung": "Nachrueckliste in den Auftrag."}])
        self.assertEqual(ids, ["M209-v1"])
        e = aussensicht.verworfene(self.cfg, 209)
        self.assertEqual(len(e), 1)
        self.assertEqual(e[0]["status"], "offen")
        self.assertEqual(e[0]["verworfen"], "Beleg-Regel")
        # Ein Register-Schreibvorgang OHNE `verworfen` darf die Liste nicht loeschen.
        aussensicht.ledger_schreiben(self.cfg, [{"id": "M209-1", "status": "offen"}])
        self.assertEqual(len(aussensicht.verworfene(self.cfg, 209)), 1)
        self.assertEqual(len(aussensicht.ledger(self.cfg)), 1)

    def test_fragen_zeigt_sie_als_verworfen_pruefen(self):
        aussensicht.verworfene_speichern(self.cfg, 209, [
            {"n": 4, "gewicht": "mittel", "aussage": "Vier Batches kein Kopf.",
             "beleg": M209_4, "empfehlung": "Nachrueckliste."}])
        text = fragen.fragen_text(self.cfg)
        self.assertIn("M209-v1", text)
        self.assertIn("verworfen - pruefen?", text)
        self.assertIn("nicht anerkannt", text)
        p = fragen.nachschlagen(self.cfg, "M209-v1")
        self.assertIsNotNone(p)
        self.assertEqual(p["frage"], "Vier Batches kein Kopf.")
        vor = fragen.nachricht_vorbereiten(self.cfg, "M209-v1 pruefen")
        self.assertTrue(vor["ok"])
        self.assertIn("M209-v1", vor["text"])
        self.assertIn("Rohantwort", vor["text"])

    def test_kennung_ist_vorne_erlaubt(self):
        self.assertEqual(fragen.ids_am_anfang("M209-v1 pruefen"), ["M209-v1"])
        self.assertEqual(fragen.ids_am_anfang("m209-v1: pruefen"), ["M209-v1"])
        self.assertEqual(fragen.ids_am_anfang("M209-1 ja"), ["M209-1"])

    def test_neuerer_lauf_ohne_verwerfungen_zeigt_nichts(self):
        aussensicht.verworfene_speichern(self.cfg, 209, [
            {"n": 4, "gewicht": "mittel", "aussage": "alt", "beleg": M209_4}])
        self.assertIn("M209-v1", fragen.fragen_text(self.cfg))
        # Ein spaeterer Lauf OHNE Verwerfungen: die alten gehoeren nicht mehr auf die Liste.
        write_text_atomic(self.root / "runs" / "meta-211.json",
                          json.dumps({"batch": 211, "befunde": []}))
        self.assertNotIn("M209-v1", fragen.fragen_text(self.cfg))
        # Im Register bleibt er (nicht wegwerfen).
        self.assertEqual(len(aussensicht.verworfene(self.cfg, 209)), 1)

    def test_quote_zaehlt_sie_nicht_mit(self):
        aussensicht.ledger_schreiben(self.cfg, [
            {"id": "M209-1", "status": "offen", "empfaenger": "Reviewer"}])
        aussensicht.verworfene_speichern(self.cfg, 209, [
            {"n": 4, "gewicht": "mittel", "aussage": "x", "beleg": M209_4}])
        q = aussensicht.quote(self.cfg)
        self.assertEqual(q["gesamt"], 1)
        self.assertIn("1 Befunde", aussensicht.zeile(self.cfg))


# ------------------------------------------------------------- 3) Hochrechnung
class TestHochrechnung(Basis):
    def _d(self, **kw) -> dict:
        d = {"n": 5, "mittel_koepfe": 3.8, "mittel_c_koepfe": 4.8,
             "c_fenster": [{"batch": 207}, {"batch": 206}, {"batch": 205}, {"batch": 204}],
             "anteil_c": 1 / 3, "anteil_quelle": 'Regel hybrid-plan.md: "2 B : 1 C"',
             "anteil_gemessen": 0.8}
        d.update(kw)
        return d

    def test_zwei_getrennte_zeilen(self):
        d = self._d(anteil_c=1 / 3, anteil_quelle='Regel hybrid-plan.md: "2 B : 1 C"')
        zeilen = stand.kalender_zeilen(self.cfg, 960, d)      # 960 Koepfe / +4.8 = 200
        self.assertIn("200 C-Batches", zeilen[0])
        self.assertIn("je C-Batch", zeilen[0])
        self.assertIn("B207", zeilen[0])
        self.assertIn("ca. 600 KALENDER-Batches", zeilen[1])  # 200 / (1/3)
        self.assertIn("33 %", zeilen[1])
        self.assertIn("2 B : 1 C", zeilen[1])

    def test_ohne_anteil_keine_kalenderzahl(self):
        zeilen = stand.kalender_zeilen(self.cfg, 100,
                                       self._d(anteil_c=None, anteil_quelle=""))
        self.assertEqual(len(zeilen), 2)
        self.assertIn("nicht rechenbar", zeilen[1])

    def test_ohne_c_durchsatz_keine_zeile(self):
        self.assertEqual(stand.kalender_zeilen(self.cfg, 100, self._d(mittel_c_koepfe=0)), [])
        self.assertEqual(stand.kalender_zeilen(self.cfg, 0, self._d()), [])

    def test_mischung_nennt_beide_zahlen(self):
        zeile = stand._mischung_zeile(self.cfg, self._d())[0]
        self.assertIn("4 C von 5 Batches im Fenster (80 %)", zeile)
        self.assertIn('Regel hybrid-plan.md: "2 B : 1 C"', zeile)
        self.assertIn("33 %", zeile)

    def test_ohne_regel_zaehlt_die_messung(self):
        d = self._d(anteil_c=0.8, anteil_quelle="gemessen im Fenster")
        self.assertIn("80 %", stand._mischung_zeile(self.cfg, d)[0])


class TestBilanzBlock(Basis):
    def test_keine_alte_sammelzahl_mehr(self):
        """Die alte Zeile 'noch ca. N Batches fuer die K offenen Koepfe' ist ersetzt."""
        quelle = (ROOT / "hx" / "stand.py").read_text(encoding="utf-8")
        self.assertNotIn("Batches fuer die", quelle)
        self.assertIn("KALENDER-Batches", quelle)


if __name__ == "__main__":
    unittest.main()
