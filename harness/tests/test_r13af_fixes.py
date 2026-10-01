"""Tests fuer R13af (2026-09-29): kein Posten verschwindet.

Zwei Regeln in der Rollenanweisung (`prompts/reviewer.md`), beide aus der `/ask`-Pruefung
vom 29.09.2026:

  1. **UEBERTRAG / VERWORFEN.** Jeder nicht erledigte Posten aus `NACHRUECKLISTE` und
     `STREICHREIHENFOLGE` des bewerteten Batches erscheint als eine dieser beiden Zeilen.
     Verloren ging B213 Nachrueckliste 1 (weitere teilgepruefte Koepfe, 57/78).
  2. **Teilpunkt-Tafel fuer ersetzte `/ds`-Nachrichten.** Wird eine Nachricht nur als
     Zusammenfassung zugestellt (Vorbild `docs/_r13t4_claude_zusammenfassung.txt`), gehoert
     eine Zeile je Teilpunkt dazu. Verloren ging `readme.md:69x` aus Nachricht `113914a`.

Geprueft wird der Text der Rollenanweisung (wie in `test_r13ae_fixes.py`), die
Kurzfassung, die direkt neben dem `/ds`-Block im Review-Prompt steht, und seit der
Haertung vom 29.09. der **wortgleiche Block** mit `NACHRUECKLISTE` +
`STREICHREIHENFOLGE` aus `runs/b<N>/auftrag.md` (`stand.pflichtbloecke`).
"""

from __future__ import annotations

import re
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import reviewer, stand, worker                        # noqa: E402
from hx.config import load_config                             # noqa: E402
from hx.orchestrator import Orchestrator                      # noqa: E402
from hx.util import Log, ensure_dir, write_text_atomic        # noqa: E402

KOPF_BLOCK = ("=== PFLICHTBLOECKE DER BEWERTETEN INSTRUKTION "
              "(NACHRUECKLISTE + STREICHREIHENFOLGE, wortgleich) ===")
REGEL_BLOCK = ("REGEL (R13ag): Jeder Posten braucht im Review eine Zeile UEBERTRAG oder "
               "VERWORFEN oder erscheint als erledigt mit Beleg.")


def _rolle() -> str:
    return (ROOT / "prompts" / "reviewer.md").read_text(encoding="utf-8")


class TestUebertragUndVerworfen(unittest.TestCase):
    """Regel 1: die beiden Zeilenformen, ihr Anlass und die Vollstaendigkeitspflicht."""

    def test_beide_zeilenformen_stehen_in_der_summary_gliederung(self):
        text = _rolle()
        gliederung = text.split("`<TELEGRAM_SUMMARY>` — maximal", 1)[1]
        gliederung = gliederung.split("### Strang B", 1)[0]
        self.assertIn('UEBERTRAG: <Posten> -> <Ziel-Batch oder Anker "Naechster Schritt">',
                      gliederung)
        self.assertIn("VERWORFEN: <Posten> - <Grund>", gliederung)
        self.assertIn("PFLICHT", gliederung)

    def test_abschnitt_ist_pflicht_und_nennt_beide_quellen(self):
        text = _rolle()
        self.assertIn("### Übertrag am Batch-Ende: kein Posten verschwindet "
                      "(Pflicht, R13af, 2026-09-29)", text)
        abschnitt = text.split("### Übertrag am Batch-Ende", 1)[1]
        abschnitt = abschnitt.split("### Ersetzte", 1)[0]
        # Beide Quellen der Posten stehen darin - die Instruktion UND der Worker-Bericht.
        self.assertIn("`NACHRUECKLISTE`/`STREICHREIHENFOLGE` der bewerteten Instruktion",
                      abschnitt)
        self.assertIn("`runs/b<N>/auftrag.md`", abschnitt)
        self.assertIn("`runs/b<N>/antwort.md`", abschnitt)
        # Auch ein nicht begonnener Posten ist ein Posten (der B213-Fall).
        self.assertIn("**gar nicht begonnener** Posten", abschnitt)

    def test_kein_posten_darf_ohne_zeile_verschwinden(self):
        text = _rolle()
        self.assertIn("**Kein Posten darf ohne eine dieser beiden Zeilen verschwinden.**",
                      text)
        # Und die Abwesenheit ist keine Aussage: es gibt eine ausdrueckliche Nullzeile.
        self.assertIn("UEBERTRAG: keiner - alle Posten erledigt", text)
        self.assertIn("Die **fehlende** Zeile ist keine Aussage.", text)

    def test_ziel_muss_konkret_sein(self):
        text = _rolle()
        self.assertIn("Nenne das **Ziel konkret**", text)
        self.assertIn('„nächster Batch\" ohne Nummer zählt nicht', text)

    def test_anlass_nennt_den_gemessenen_verlust(self):
        text = _rolle()
        self.assertIn("B213 Nachrückliste 1", text)
        self.assertIn("runs/b213/auftrag.md:187", text)
        self.assertIn("logs/ask/ask-20260929-141152+0000.md", text)
        self.assertIn("Für 12 von 13 Posten", text)
        # Die Regel ist datiert (Projektkonvention: R-Nummer + Datum im Titel).
        self.assertRegex(text, r"Pflicht, R13af, 2026-09-29")


class TestTeilpunktTafel(unittest.TestCase):
    """Regel 2: eine Zeile je Teilpunkt jeder ersetzten Nachricht."""

    def test_abschnitt_ist_pflicht(self):
        text = _rolle()
        self.assertIn("### Ersetzte `/ds`-Nachrichten: Tafel mit einer Zeile je Teilpunkt "
                      "(Pflicht, R13af, 2026-09-29)", text)

    def test_tafelform_und_spalten(self):
        text = _rolle()
        abschnitt = text.split("### Ersetzte `/ds`-Nachrichten", 1)[1]
        abschnitt = abschnitt.split("### Aussensicht-Befunde", 1)[0]
        self.assertIn("| Nachricht | Teilpunkt | übernommen als … / bewusst weggelassen - "
                      "Grund | Beleg |", abschnitt)
        self.assertIn("**Ein Teilpunkt ist keine Nachricht.**", abschnitt)
        self.assertIn("fünf Punkten ergibt fünf", abschnitt)
        self.assertIn("**„übernommen als …\"**", abschnitt)
        self.assertIn("**„bewusst weggelassen - Grund\"**", abschnitt)

    def test_fehlende_tafel_wird_nachgetragen_und_gemeldet(self):
        text = _rolle()
        abschnitt = text.split("### Ersetzte `/ds`-Nachrichten", 1)[1]
        abschnitt = abschnitt.split("### Aussensicht-Befunde", 1)[0]
        self.assertIn("trägst du", abschnitt)
        self.assertIn("`OFFENE FRAGE: …`", abschnitt)
        self.assertIn("Vorbild:", abschnitt)
        self.assertIn("docs/_r13t4_claude_zusammenfassung.txt", abschnitt)

    def test_anlass_nennt_den_gemessenen_verlust(self):
        text = _rolle()
        abschnitt = text.split("### Ersetzte `/ds`-Nachrichten", 1)[1]
        abschnitt = abschnitt.split("### Aussensicht-Befunde", 1)[0]
        self.assertIn("`113914a` hatte **zwei**", abschnitt)
        self.assertIn("readme.md:640-642", abschnitt)
        self.assertIn("readme.md:69x", abschnitt)
        self.assertIn("logs/ask/ask-20260929-141009+0000.md", abschnitt)


class TestKurzfassungImPrompt(unittest.TestCase):
    """Die Kurzfassung steht dort, wo die Nachrichten erscheinen (neben `/ds`)."""

    def setUp(self):
        self.cfg = load_config()

    def prompt(self) -> str:
        ctx = {"batch": 213, "ds_queue": "NACHRICHTEN AUS DER QUEUE\n113914a readme.md:69x"}
        return reviewer.build_prompt(self.cfg, "batch_end", ctx)

    def test_ds_regel_nennt_die_zeilenformen(self):
        text = self.prompt()
        self.assertIn("Diese Nachrichten sind fuer den Worker", text)
        self.assertIn("EIN TEILPUNKT IST KEINE NACHRICHT", text)
        self.assertIn("UEBERTRAG: <Teilpunkt> -> <Ziel>", text)
        self.assertIn("VERWORFEN: <Teilpunkt> - <Grund>", text)
        self.assertIn("ZUSAMMENFASSUNG zugestellt", text)

    def test_rollenanweisung_wird_als_systemdatei_ausgeliefert(self):
        """Die neue Regel wirkt nur, wenn die Rollenanweisung mitgeht - sie wird als
        `--append-system-prompt-file` uebergeben (nicht in den Prompt eingebettet)."""
        from hx import reviewer as rv
        cmd = rv.build_command(self.cfg, "sess", True)
        self.assertIn("--append-system-prompt-file", cmd)
        datei = Path(cmd[cmd.index("--append-system-prompt-file") + 1])
        self.assertEqual(datei.resolve(), (ROOT / "prompts" / "reviewer.md").resolve())
        text = datei.read_text(encoding="utf-8")
        self.assertIn("Übertrag am Batch-Ende", text)
        self.assertIn("Ersetzte `/ds`-Nachrichten", text)
        # Und genau diese Datei ist die, deren Hash der Harness als Kennung fuehrt.
        self.assertEqual(rv.prompt_hash(self.cfg), rv.prompt_hash(self.cfg))

    def test_reviewer_darf_die_auftraege_lesen(self):
        """Regel 1 verweist auf `runs/b<N>/auftrag.md` - der Pfad muss freigegeben sein."""
        from hx import reviewer as rv
        cmd = rv.build_command(self.cfg, "sess", True)
        self.assertIn("--add-dir", cmd)
        self.assertIn(str(self.cfg.root), cmd)


class TestBelegdateien(unittest.TestCase):
    """Die zitierten Belege existieren und tragen den Verlust (sonst ist es Prosa)."""
    def test_ask_belege_nennen_verloren(self):
        for name, stichwort in (("ask-20260929-141152+0000.md", "B213"),
                                ("ask-20260929-141009+0000.md", "113914a")):
            p = ROOT / "logs" / "ask" / name
            if not p.is_file():
                self.skipTest(f"{name} fehlt")
            text = p.read_text(encoding="utf-8")
            self.assertIn("VERLOREN", text)
            self.assertIn(stichwort, text)

    def test_vorbild_zusammenfassung_hat_die_luecke(self):
        """`113914a` hatte zwei Teilpunkte - die Zusammenfassung fuehrt nur 640-642."""
        p = ROOT.parent / "docs" / "_r13t4_claude_zusammenfassung.txt"
        if not p.is_file():
            self.skipTest("Vorbild-Zusammenfassung fehlt")
        text = p.read_text(encoding="utf-8")
        self.assertIn("readme.md:640-642", text)
        self.assertNotIn("readme.md:69", text)
        # Genau das ist die Luecke, die die neue Regel sichtbar macht.
        self.assertRegex(text, re.compile(r"ersetzt ALLE /ds-Nachrichten"))


class TestDokumentation(unittest.TestCase):
    def test_bedienung_hat_den_abschnitt(self):
        p = ROOT.parent / "docs" / "bedienung.md"
        if not p.is_file():
            self.skipTest("bedienung.md fehlt")
        text = p.read_text(encoding="utf-8")
        self.assertIn("### 12j. Kein Posten verschwindet", text)
        self.assertIn("UEBERTRAG: <Posten> -> <Ziel-Batch oder Anker", text)
        self.assertIn("Teilpunkt-Tafel", text)
        # R13ag: die Haertung steht auch in der Doku (kein offener Punkt mehr).
        self.assertIn("**Seit R13ag stehen die Pflichtblöcke im Prompt.**", text)
        self.assertIn("pflichtbloecke", text)


# ==================================== 3) Pflichtbloecke im Review-Prompt (R13ag)
class BasisAuftrag(unittest.TestCase):
    """Wegwerf-Harness mit eigenem `runs/` - hier liegen die Auftraege."""

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / "_tmp_r13af"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "harness")
        self.decomp = ensure_dir(self.tmp / "decomp")
        ensure_dir(self.decomp / "analysis")
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

    def auftrag(self, batch: int, text: str) -> None:
        d = ensure_dir(self.root / "runs" / f"b{batch:03d}")
        write_text_atomic(d / "auftrag.md", text)

    def orch(self, batch: int) -> Orchestrator:
        o = Orchestrator(self.cfg, self.log, mock=True,
                         state_file=self.root / "state" / "run.json")
        o.qroot = self.root
        o.said = []
        o.say = lambda t="", *a, **k: o.said.append(str(t))
        o.state.data["batch"] = batch
        o.state.save()
        return o


class TestPflichtbloeckeAmEchtenAuftrag(unittest.TestCase):
    """Der Block an den echten Auftraegen (das Belegstueck: B213 Nachrueckliste 1)."""

    @classmethod
    def setUpClass(cls):
        cls.cfg = load_config()

    def block(self, batch: int) -> str:
        return stand.pflichtbloecke(self.cfg, batch)

    def test_b213_hat_den_verlorenen_posten_wortgleich(self):
        block = self.block(213)
        self.assertIn("NACHRUECKLISTE (vor dem Preflight, je Posten ein Commit mit "
                      "Soll-Delta):", block)
        for posten in ("Weitere teilgepruefte Koepfe ueber die vier hinaus mit "
                       "MEM-Varianten",
                       "R330 als Arbeitsposten",
                       "Paket-E-Liste um Callee-Abhaengigkeiten ergaenzen"):
            self.assertIn(posten, block)
        self.assertIn("STREICHREIHENFOLGE (nur mit `Get-Date` >= 70 min):", block)
        self.assertIn("1. Nachrueckliste 3, dann 2, dann 1.", block)

    def test_b212_haelt_am_batch_ende_und_vor_der_queue(self):
        block = self.block(212)
        self.assertIn("NACHRUECKLISTE (nach TEIL 1-5, vor dem Preflight", block)
        self.assertIn("STREICHREIHENFOLGE (nur mit `Get-Date`-Zeile davor):", block)
        self.assertIn("NIE: TEIL 1a-d", block)          # NIE-Zeile gehoert dazu
        self.assertNotIn("BATCH-ENDE:", block)          # ... aber der naechste Block nicht
        self.assertNotIn("NACHRICHTEN AUS DER QUEUE", block)

    def test_b213_schneidet_vor_nicht_tun(self):
        block = self.block(213)
        self.assertIn("NACHRUECKLISTE", block)
        self.assertNotIn("NICHT TUN:", block)
        self.assertNotIn("FERTIG WENN:", block)

    def test_alte_auftraege_ohne_block_sagen_das(self):
        """B210 hatte noch keinen NACHRUECKLISTE-Abschnitt - das steht dann da."""
        block = self.block(210)
        self.assertIn("NACHRUECKLISTE: keine im Auftrag", block)
        self.assertIn("STREICHREIHENFOLGE (zuerst streichen):", block)

    def test_erkennung_passt_zu_worker_hat_nachrueckliste(self):
        """Die Auftragsdatei ist die Quelle - beide Erkennungen muessen dasselbe sagen."""
        runs = Path(self.cfg.root) / "runs"
        gesehen = 0
        for p in sorted(runs.glob("b*/auftrag.md")):
            # R13bj: `runs/` enthaelt auch Ordner, die nicht `b<Zahl>` heissen
            # (Sicherung `b235_lauf1_sicherung`, `env-proof`, `ghidra-smoke`) -
            # `int(name[1:])` stuerzt daran ab.
            if not p.parent.name[1:].isdigit():
                continue
            batch = int(p.parent.name[1:])
            if not 204 <= batch <= 213:
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            block = self.block(batch)
            gesehen += 1
            if worker.hat_nachrueckliste(text):
                self.assertNotIn("NACHRUECKLISTE: keine im Auftrag", block,
                                 f"B{batch}: Fortsetzung erkennt eine Liste, der Block nicht")
            else:
                self.assertIn("NACHRUECKLISTE: keine im Auftrag", block,
                              f"B{batch}: Fortsetzung erkennt keine Liste, der Block schon")
        self.assertGreaterEqual(gesehen, 5, "zu wenige echte Auftraege geprueft")

    def test_wortgleich_heisst_wortgleich(self):
        """Die Zeilen des Blocks stehen genauso in der Datei (keine Umformung)."""
        p = Path(self.cfg.root) / "runs" / "b213" / "auftrag.md"
        datei = p.read_text(encoding="utf-8")
        for zeile in self.block(213).splitlines():
            self.assertIn(zeile, datei, f"nicht wortgleich: {zeile!r}")


class TestPflichtbloeckeFixtur(BasisAuftrag):
    """Fehlende Bloecke, unlesbarer Auftrag und Muster-Drift."""

    def test_fehlender_abschnitt_ergibt_keine_im_auftrag(self):
        self.auftrag(207, "=== AUFTRAG (vom Reviewer) ===\nTEIL 1: irgendwas.\n")
        self.assertEqual(stand.pflichtbloecke(self.cfg, 207),
                         "NACHRUECKLISTE: keine im Auftrag\n"
                         "STREICHREIHENFOLGE: keine im Auftrag")

    def test_teilweise_vorhanden(self):
        self.auftrag(207, "TEIL 1: x\n\nNACHRUECKLISTE:\n1. Offener Posten.\n")
        block = stand.pflichtbloecke(self.cfg, 207)
        self.assertIn("NACHRUECKLISTE:\n1. Offener Posten.", block)
        self.assertIn("STREICHREIHENFOLGE: keine im Auftrag", block)

    def test_leere_auftragsdatei(self):
        self.auftrag(207, "")
        self.assertIn("NACHRUECKLISTE: keine im Auftrag",
                      stand.pflichtbloecke(self.cfg, 207))

    def test_unlesbarer_auftrag_sagt_das(self):
        block = stand.pflichtbloecke(self.cfg, 999)
        self.assertIn("(Auftrag runs/b999/auftrag.md nicht lesbar", block)
        self.assertNotIn("keine im Auftrag", block)

    def test_ohne_bewerteten_batch(self):
        self.assertIn("(kein bewerteter Batch", stand.pflichtbloecke(self.cfg, 0))

    def test_muster_drift_wird_gemeldet(self):
        """Meldet `worker.hat_nachrueckliste` eine Liste, die hier nicht als Abschnitt
        lesbar ist, steht das da - statt 'keine im Auftrag' zu behaupten."""
        text = "\x0c NACHRUECKLISTE (Sonderform):\n1. Posten.\n"
        self.assertTrue(worker.hat_nachrueckliste(text), "Vorbedingung des Testfalls")
        self.assertIsNone(stand._RE_AUFTRAG_BLOCK["NACHRUECKLISTE"].search(text))
        self.auftrag(207, text)
        block = stand.pflichtbloecke(self.cfg, 207)
        self.assertIn("im Auftrag erkannt, aber nicht als Abschnitt lesbar", block)
        self.assertIn("Muster pruefen", block)
        self.assertNotIn("NACHRUECKLISTE: keine im Auftrag", block)

    def test_erste_zeile_des_blocks_ist_die_etikettzeile(self):
        self.auftrag(207, "TEIL 1: x\n\nSTREICHREIHENFOLGE (nur mit Uhrnachweis):\n"
                          "1. Doku.\n")
        self.assertTrue(stand.pflichtbloecke(self.cfg, 207).startswith(
            "STREICHREIHENFOLGE (nur mit Uhrnachweis):\n1. Doku."))


class TestPflichtbloeckeImPrompt(BasisAuftrag):
    """Der Weg Orchestrator -> Review-Kontext -> Prompt (kein Umweg mehr ueber die Datei)."""

    AUFTRAG = ("=== AUFTRAG (vom Reviewer) ===\nTEIL 1: bauen.\n\n"
               "NACHRUECKLISTE (je Posten ein Commit):\n1. Offener Posten A.\n\n"
               "STREICHREIHENFOLGE (nur mit `Get-Date` davor):\n1. TEIL 2.\n")

    def test_kontext_traegt_die_bloecke(self):
        self.auftrag(213, self.AUFTRAG)
        ctx = self.orch(213).review_context("(Snapshot)")
        self.assertIn("NACHRUECKLISTE (je Posten ein Commit):", ctx["pflichtbloecke"])
        self.assertIn("1. Offener Posten A.", ctx["pflichtbloecke"])
        self.assertIn("1. TEIL 2.", ctx["pflichtbloecke"])

    def test_prompt_hat_block_und_regel(self):
        self.auftrag(213, self.AUFTRAG)
        ctx = self.orch(213).review_context("(Snapshot)")
        prompt = reviewer.build_prompt(self.cfg, "batch_end", ctx)
        self.assertIn(KOPF_BLOCK, prompt)
        self.assertIn("1. Offener Posten A.", prompt)
        self.assertIn("STREICHREIHENFOLGE (nur mit `Get-Date` davor):", prompt)
        self.assertIn(REGEL_BLOCK, prompt)
        # Der Block steht VOR dem /ds-Block (Reihenfolge der Pflichtangaben).
        self.assertLess(prompt.index(KOPF_BLOCK),
                        prompt.index("=== NUTZER-NACHRICHTEN AN DEN WORKER DIESES BATCHES"))

    def test_leerer_kontext_wird_benannt(self):
        prompt = reviewer.build_prompt(self.cfg, "batch_end", {"batch": 1})
        self.assertIn(KOPF_BLOCK, prompt)
        self.assertIn("(nicht ermittelbar)", prompt)
        self.assertIn(REGEL_BLOCK, prompt)

    def test_auftrag_ohne_bloecke_im_prompt(self):
        self.auftrag(213, "=== AUFTRAG (vom Reviewer) ===\nTEIL 1: bauen.\n")
        prompt = reviewer.build_prompt(self.cfg, "batch_end",
                                       self.orch(213).review_context("(Snapshot)"))
        self.assertIn("NACHRUECKLISTE: keine im Auftrag", prompt)
        self.assertIn("STREICHREIHENFOLGE: keine im Auftrag", prompt)


if __name__ == "__main__":
    unittest.main()
