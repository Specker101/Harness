"""Tests fuer R13br (2026-10-04): Ablage der Aussensicht im Batch-Ordner.

Auftrag (Nutzer, Harness-Wartung): die Dateien der AUSSENSICHT lagen lose in `runs/`
(`meta-<N>.md`, `.json`, `.jsonl`, `.err.txt`, `-hooks.json`) und gehoeren in den Ordner
des BEWERTETEN Batches: `runs/b<N>/meta.md|meta.json|meta.jsonl|meta.err.txt|meta-hooks.json`.

Vorgaben des Auftrags:

  1. Der neue Ort wird geschrieben; der Ordner wird bei Bedarf angelegt.
  2. Alle Leser akzeptieren BEIDE Orte: zuerst der neue, als Rueckfall der alte
     (`runs/meta-<N>.*`) - alte Aussensichten und der Zustand (Verdikte, Takt, offene
     Befunde, Fensterlogik) bleiben damit gueltig.
  3. Die vorhandenen losen Dateien werden NICHT geloescht oder verschoben (Belege).
     Ein Wandler KOPIERT sie (Trockenlauf als Vorgabe, `--ausfuehren` kopiert).
  4. Der neue Ort darf bestehende Dateien im Batch-Ordner nicht ueberschreiben: eine
     fremde Datei bricht den Lauf VOR dem (bezahlten) API-Aufruf mit klarer Meldung ab.

Alles ohne API-Kosten: Laeufe nur im Attrappenmodus (`mock=True`), Zustand und
Arbeitsordner liegen in Wegwerf-Verzeichnissen (`tests/_tmp_r13br*`). Das laufende
Harness-Verzeichnis wird NICHT angefasst.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import aussensicht, fragen                              # noqa: E402
from hx.config import load_config                                 # noqa: E402
from hx.orchestrator import Orchestrator                          # noqa: E402
from hx.util import Log, ensure_dir, read_text, write_text_atomic  # noqa: E402


def _bericht_json(batch: int, **rest) -> str:
    d = {"batch": int(batch), "rc": 0, "befunde": [{"n": 1}]}
    d.update(rest)
    return json.dumps(d)


class Basis(unittest.TestCase):
    """Wegwerf-Wurzel; `cfg.root` zeigt dorthin, `runs/` entsteht wie im Betrieb."""

    def setUp(self):
        self.tmp = Path(ROOT) / "tests" / f"_tmp_r13br_{type(self).__name__}"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.root = ensure_dir(self.tmp / "root")
        self.decomp = ensure_dir(self.tmp / "decomp")
        ensure_dir(self.decomp / "analysis")
        cfg = load_config()
        cfg.data["paths"]["root"] = str(self.root)
        cfg.data["paths"]["decomp"] = str(self.decomp)
        cfg.data["paths"]["harness_home"] = str(self.tmp)
        cfg.data["paths"]["inbox"] = str(self.root / "inbox")
        cfg.data["paths"]["secrets"] = str(ensure_dir(self.tmp / "secrets"))
        cfg.data["mock"]["enabled"] = True
        self.cfg = cfg
        self.log = Log(self.tmp / "log.jsonl", echo=False)
        self.gesagt: list[str] = []

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---------------------------------------------------------------- Hilfen
    def runs(self) -> Path:
        return self.root / "runs"

    def alt(self, batch: int, art: str) -> Path:
        return aussensicht.pfad_alt(self.cfg, batch, art)

    def neu(self, batch: int, art: str) -> Path:
        return aussensicht.pfad_neu(self.cfg, batch, art)

    def alt_bericht(self, batch: int, **rest) -> Path:
        return write_text_atomic(self.alt(batch, "json"), _bericht_json(batch, **rest))

    def neu_bericht(self, batch: int, **rest) -> Path:
        return write_text_atomic(self.neu(batch, "json"), _bericht_json(batch, **rest))

    def orch(self, batch: int = 208) -> Orchestrator:
        o = Orchestrator(self.cfg, self.log, mock=True,
                         state_file=self.root / "state" / "run.json")
        o.qroot = self.root
        o.state.data["batch"] = batch
        o.state.data["meta"] = {"letzter_lauf_batch": 207, "geprueft_batch": 207}
        o.state.save()
        o.say = lambda *a, **k: self.gesagt.append(str(a[0] if a else ""))
        self.gesagt.clear()
        return o


# ------------------------------------------------- 1) Der neue Ort wird geschrieben
class TestSchreiben(Basis):
    def test_mocklauf_schreibt_in_den_batchordner(self):
        self.orch(208)._do_aussensicht("Befehl /meta")
        for art in ("md", "json", "jsonl"):
            self.assertTrue(self.neu(208, art).is_file(), f"{art} fehlt am neuen Ort")
            self.assertFalse(self.alt(208, art).exists(),
                             f"{art} darf nicht mehr lose in runs/ liegen")
        self.assertEqual(self.neu(208, "json").parent.name, "b208")
        # Das stderr des Laufs entsteht nur bei einem ECHTEN Lauf (`run_stream`) - hier
        # wird nur der Ort geprueft (mock schreibt keine err.txt, wie vorher auch).
        self.assertEqual(self.neu(208, "err").name, "meta.err.txt")
        self.assertEqual(self.neu(208, "err").parent.name, "b208")

    def test_ordner_wird_bei_bedarf_angelegt(self):
        """Nummer ohne Worker-Lauf (z. B. `/meta` im Gate): der Ordner entsteht hier."""
        self.assertFalse((self.runs() / "b259").exists())
        self.orch(259)._do_aussensicht("Befehl /meta")
        self.assertTrue((self.runs() / "b259" / "meta.md").is_file())

    def test_hook_einstellungen_liegen_im_batchordner(self):
        pfad = aussensicht.write_hook_settings(self.cfg, 217)
        self.assertEqual(Path(pfad).parent.name, "b217")
        self.assertEqual(Path(pfad).name, "meta-hooks.json")

    def test_bericht_meldet_den_neuen_pfad(self):
        self.orch(208)._do_aussensicht("Befehl /meta")
        self.assertTrue(any("b208" in z and "meta.md" in z for z in self.gesagt),
                        self.gesagt)

    def test_berichtskopf_ist_wiedererkennbar(self):
        self.orch(208)._do_aussensicht("Befehl /meta")
        self.assertTrue(read_text(self.neu(208, "md")).startswith("# Aussensicht Batch 208"))


# --------------------------------------- 2) Der alte Ort bleibt lesbar (Rueckfall)
class TestAlterOrt(Basis):
    def test_bericht_zustand_liest_den_alten_ort(self):
        """Der neueste Bericht ist der gescheiterte - der gelungene davor zaehlt (R13aq)."""
        for batch, rest in ((216, {}),
                            (217, {"rc": 1, "subtype": "error_max_turns",
                                   "gescheitert_grund": "rc=1, error_max_turns, 31 Zuege"})):
            p = self.alt_bericht(batch, **rest)
            t = 1_700_000_000 + batch
            os.utime(p, (t, t))
        z = aussensicht.bericht_zustand(self.cfg)
        self.assertEqual(z["anzahl_berichte"], 2)
        self.assertEqual(z["neuester_gescheitert"], 217)
        self.assertEqual(z["letzte_gelungen"], 216)
        self.assertIn("error_max_turns", z["gescheitert_grund"])

    def test_letzte_bericht_batches_liest_den_alten_ort(self):
        self.alt_bericht(211)
        self.alt_bericht(212)
        self.assertEqual(aussensicht.letzte_bericht_batches(self.cfg), [211, 212])

    def test_alle_fuenf_arten_werden_am_alten_ort_gefunden(self):
        for art in aussensicht.ABLAGE:
            p = write_text_atomic(self.alt(211, art), "alt")
            self.assertEqual(aussensicht.pfad(self.cfg, 211, art), p)
            self.assertFalse(self.neu(211, art).exists())

    def test_neuer_ort_hat_vorrang(self):
        for art in aussensicht.ABLAGE:
            write_text_atomic(self.alt(211, art), "alt")
            p = write_text_atomic(self.neu(211, art), "neu")
            self.assertEqual(aussensicht.pfad(self.cfg, 211, art), p)

    def test_bei_beiden_orten_zaehlt_der_neue(self):
        self.alt_bericht(211, befunde=[{}, {}])
        self.neu_bericht(211, befunde=[{}])
        z = aussensicht.bericht_zustand(self.cfg)
        self.assertEqual(z["anzahl_berichte"], 1, "derselbe Batch darf nicht doppelt zaehlen")
        self.assertEqual(z["letzte_gelungen"], 211)
        self.assertEqual(z["befunde"], 1, "der neue Ort gewinnt")
        self.assertEqual(aussensicht.letzte_bericht_batches(self.cfg), [211])

    def test_fensterlogik_liefert_gemischte_orte_wie_alte(self):
        """Dieselbe Lage zweimal: einmal ganz alt, einmal gemischt (alt/neu/neu).

        216 gelungen, 217 gelungen, 218 GESCHEITERT (der neueste) - damit laufen beide
        Zweige von `bericht_zustand` durch (gescheitert merken, erster gelungener
        beendet die Suche).
        """
        lage = [(216, 0, "alt"), (217, 0, "alt"), (218, 1, "neu")]

        def baue(gemischt: bool) -> tuple:
            shutil.rmtree(self.runs(), ignore_errors=True)
            for batch, rc, ort in lage:
                ziel = self.neu(batch, "json") if (gemischt and ort == "neu") \
                    else self.alt(batch, "json")
                rest = {"subtype": "error_max_turns"} if rc else {}
                write_text_atomic(ziel, _bericht_json(batch, rc=rc, **rest))
                # Reihenfolge der Berichte festlegen (mtime), unabhaengig von der Uhr.
                t = 1_700_000_000 + batch
                os.utime(ziel, (t, t))
            return (aussensicht.bericht_zustand(self.cfg), aussensicht.zeile(self.cfg),
                    aussensicht.letzte_bericht_batches(self.cfg))

        alt = baue(False)
        gemischt = baue(True)
        self.assertEqual(alt, gemischt)
        self.assertEqual(alt[2], [216, 217, 218])
        self.assertEqual(alt[0]["letzte_gelungen"], 217)
        self.assertEqual(alt[0]["neuester_gescheitert"], 218)
        self.assertEqual(alt[0]["anzahl_berichte"], 3)
        self.assertIn("letzte Aussensicht: Batch 217", alt[1])
        self.assertIn("zuletzt gescheitert: Batch 218", alt[1])

    def test_quelle_zeigt_den_ort_an_dem_die_datei_liegt(self):
        self.alt_bericht(208)
        write_text_atomic(self.alt(208, "md"), "# Aussensicht Batch 208\n")
        self.assertEqual(aussensicht.anzeige_pfad(self.cfg, 208), "runs/meta-208.md")
        write_text_atomic(self.neu(208, "md"), "# Aussensicht Batch 208\n")
        self.assertEqual(aussensicht.anzeige_pfad(self.cfg, 208), "runs/b208/meta.md")

    def test_fragen_nennt_den_neuen_ort(self):
        aussensicht.ledger_schreiben(self.cfg, [
            {"id": "M208-1", "batch": 208, "gewicht": "hoch", "empfaenger": "Nutzer",
             "aussage": "Aussage", "empfehlung": "Empfehlung", "beleg": "a:1", "status": "offen"}])
        write_text_atomic(self.neu(208, "md"), "# Aussensicht Batch 208\n")
        posten = fragen._aussensicht_posten(self.cfg)                  # noqa: SLF001
        self.assertEqual(posten[0]["quelle"], "runs/b208/meta.md")


# --------------------------------------------------------- 3) Der Ablage-Waechter
class TestWaechter(Basis):
    def test_ohne_dateien_kein_konflikt(self):
        self.assertEqual(aussensicht.ablage_konflikt(self.cfg, 208), [])
        aussensicht.ablage_pruefen(self.cfg, 208)                      # wirft nicht

    def test_fremde_datei_wird_gemeldet(self):
        p = write_text_atomic(self.neu(208, "md"), "FREMD - gehoert nicht zur Aussensicht\n")
        self.assertEqual(aussensicht.ablage_konflikt(self.cfg, 208), [str(p)])
        with self.assertRaises(aussensicht.AblageKonflikt) as ctx:
            aussensicht.ablage_pruefen(self.cfg, 208)
        text = str(ctx.exception)
        self.assertIn("Ablage-Kollision", text)
        self.assertIn("meta.md", text)
        self.assertIn("NICHT gestartet", text)

    def test_fremder_bericht_bricht_vor_dem_lauf_ab(self):
        fremd = write_text_atomic(self.neu(208, "md"), "FREMD\n")
        self.orch(208)._do_aussensicht("Befehl /meta")
        self.assertEqual(read_text(fremd), "FREMD\n", "die fremde Datei bleibt unberuehrt")
        for art in ("json", "jsonl", "err"):
            self.assertFalse(self.neu(208, art).exists(), f"{art} darf nicht entstehen")
        self.assertTrue(any("Ablage-Kollision" in z for z in self.gesagt), self.gesagt)

    def test_auch_eine_fremde_json_fassung_bricht_ab(self):
        write_text_atomic(self.neu(208, "json"), json.dumps({"fremd": True}))
        self.orch(208)._do_aussensicht("Befehl /meta")
        self.assertFalse(self.neu(208, "jsonl").exists())
        self.assertFalse(self.neu(208, "md").exists())

    def test_eine_unlesbare_mitschnittdatei_bricht_ab(self):
        write_text_atomic(self.neu(208, "jsonl"), "kein JSON, nur Text\n")
        self.assertEqual(len(aussensicht.ablage_konflikt(self.cfg, 208)), 1)

    def test_eigene_dateien_erlauben_den_wiederholungslauf(self):
        """Ein zweiter Lauf derselben Nummer (z.B. nach Session-Limit) muss gehen."""
        write_text_atomic(self.neu(208, "md"), "# Aussensicht Batch 208\n\nalt\n")
        write_text_atomic(self.neu(208, "json"), _bericht_json(208, ts="alt"))
        write_text_atomic(self.neu(208, "jsonl"), json.dumps({"type": "result"}) + "\n")
        self.assertEqual(aussensicht.ablage_konflikt(self.cfg, 208), [])
        self.orch(208)._do_aussensicht("Befehl /meta")
        neu = json.loads(read_text(self.neu(208, "json")))
        self.assertNotEqual(neu.get("ts"), "alt", "der neue Lauf hat geschrieben")
        self.assertIn("befunde", neu)
        self.assertFalse(self.alt(208, "json").exists())

    def test_hilfsdateien_blockieren_nicht(self):
        """`err` und `hooks` sind Hilfsdateien dieses Harness - sie duerfen neu entstehen."""
        write_text_atomic(self.neu(208, "err"), "stderr des vorigen Versuchs\n")
        write_text_atomic(self.neu(208, "hooks"), json.dumps({"hooks": {}}))
        self.assertEqual(aussensicht.ablage_konflikt(self.cfg, 208), [])


# ------------------------------------------------------------- 4) Der Wandler
class TestWandler(Basis):
    def _alt_lage(self) -> None:
        for batch in (208, 209):
            write_text_atomic(self.alt(batch, "md"), f"# Aussensicht Batch {batch}\n")
            write_text_atomic(self.alt(batch, "json"), _bericht_json(batch))
            write_text_atomic(self.alt(batch, "jsonl"), json.dumps({"type": "result"}) + "\n")
            write_text_atomic(self.alt(batch, "err"), "")

    def test_trockenlauf_aendert_nichts(self):
        self._alt_lage()
        vorher = {p.name: read_text(p) for p in sorted(self.runs().iterdir())}
        erg = aussensicht.ablage_wandeln(self.cfg)
        self.assertFalse(erg["ausgefuehrt"])
        self.assertEqual(erg["quellen"], 8)
        self.assertEqual(erg["kopiert"], 0)
        self.assertEqual(erg["geloescht"], 0)
        self.assertEqual({z["aktion"] for z in erg["zeilen"]}, {"kopieren"})
        self.assertEqual({z["vorhanden"] for z in erg["zeilen"]}, {"nein"})
        self.assertEqual({z["hash_gleich"] for z in erg["zeilen"]}, {"-"})
        for batch in (208, 209):
            for art in ("md", "json", "jsonl", "err"):
                self.assertFalse(self.neu(batch, art).exists())
        self.assertEqual({p.name: read_text(p) for p in sorted(self.runs().iterdir())}, vorher)

    def test_trockenlauf_zeigt_hash_spalte_und_bilanz(self):
        self._alt_lage()
        tafel = aussensicht.ablage_tafel(aussensicht.ablage_wandeln(self.cfg))
        kopf = [z for z in tafel.splitlines() if "Datei" in z and "Aktion" in z][0]
        for spalte in ("Datei", "Ziel", "Hash gleich", "Aktion"):
            self.assertIn(spalte, kopf)
        self.assertIn("runs/b208/meta.md", tafel)
        self.assertIn("Trockenlauf", tafel)
        self.assertIn("kopiert: 0, geloescht: 0, behalten: 0", tafel)

    def test_ausfuehren_kopiert_und_laesst_die_originale(self):
        """Ohne --verschieben bleibt das Original liegen (Beleg, Rueckweg)."""
        self._alt_lage()
        erg = aussensicht.ablage_wandeln(self.cfg, ausfuehren=True)
        self.assertEqual(erg["kopiert"], 8)
        self.assertEqual(erg["belegt"], 0)
        self.assertEqual(erg["geloescht"], 0)
        for batch in (208, 209):
            for art in ("md", "json", "jsonl", "err"):
                quelle, ziel = self.alt(batch, art), self.neu(batch, art)
                self.assertTrue(ziel.is_file(), f"{ziel} fehlt")
                self.assertTrue(quelle.is_file(), "Original muss liegen bleiben")
                self.assertEqual(read_text(quelle), read_text(ziel))

    def test_zweiter_lauf_erkennt_schon_da(self):
        self._alt_lage()
        aussensicht.ablage_wandeln(self.cfg, ausfuehren=True)
        erg = aussensicht.ablage_wandeln(self.cfg, ausfuehren=True)
        self.assertEqual(erg["kopiert"], 0)
        self.assertEqual(erg["gleich"], 8)
        self.assertEqual({z["aktion"] for z in erg["zeilen"]}, {"schon da"})
        self.assertEqual({z["hash_gleich"] for z in erg["zeilen"]}, {"ja"})

    def test_belegtes_ziel_wird_nicht_ueberschrieben(self):
        self._alt_lage()
        fremd = write_text_atomic(self.neu(208, "json"), "FREMD\n")
        erg = aussensicht.ablage_wandeln(self.cfg, ausfuehren=True)
        self.assertEqual(erg["belegt"], 1)
        self.assertEqual(read_text(fremd), "FREMD\n")
        zeile = [z for z in erg["zeilen"] if z["batch"] == 208 and z["art"] == "json"]
        self.assertEqual(zeile[0]["aktion"],
                         "Ziel belegt (Hash verschieden) - Original bleibt")
        self.assertEqual(zeile[0]["hash_gleich"], "nein")
        self.assertIn("Ziel belegt", aussensicht.ablage_tafel(erg))

    # --------------------------------------------------- verschieben (R13bs)
    def test_verschieben_loescht_das_original(self):
        """Gleiche Datei: kopiert und danach das lose Original entfernt."""
        self._alt_lage()
        erg = aussensicht.ablage_wandeln(self.cfg, ausfuehren=True, verschieben=True)
        self.assertEqual(erg["kopiert"], 8)
        self.assertEqual(erg["geloescht"], 8)
        self.assertEqual(erg["behalten"], 0)
        self.assertEqual({z["aktion"] for z in erg["zeilen"]},
                         {"kopiert + Original geloescht"})
        for batch in (208, 209):
            for art in ("md", "json", "jsonl", "err"):
                self.assertTrue(self.neu(batch, art).is_file(), f"Kopie {art} fehlt")
                self.assertFalse(self.alt(batch, art).exists(), f"Original {art} liegt noch")
        self.assertIn("kopiert: 8, geloescht: 8, behalten: 0",
                      aussensicht.ablage_tafel(erg))

    def test_verschieben_loescht_auch_ohne_neue_kopie(self):
        """Die Ziele sind schon gleich - die Originale verschwinden trotzdem (kein Kopieren)."""
        self._alt_lage()
        aussensicht.ablage_wandeln(self.cfg, ausfuehren=True)      # nur kopieren
        erg = aussensicht.ablage_wandeln(self.cfg, ausfuehren=True, verschieben=True)
        self.assertEqual(erg["kopiert"], 0)
        self.assertEqual(erg["geloescht"], 8)
        self.assertEqual(erg["behalten"], 0)
        self.assertEqual({z["aktion"] for z in erg["zeilen"]},
                         {"Original geloescht (Kopie gleich)"})
        self.assertFalse(self.alt(208, "md").exists())
        self.assertTrue(self.neu(208, "md").is_file())

    def test_verschieben_laesst_abweichendes_original_liegen(self):
        """Verschiedener Inhalt: nichts wird kopiert, nichts geloescht, Grund in der Tafel."""
        self._alt_lage()
        fremd = write_text_atomic(self.neu(208, "json"), "FREMD\n")
        erg = aussensicht.ablage_wandeln(self.cfg, ausfuehren=True, verschieben=True)
        self.assertEqual(erg["kopiert"], 7)
        self.assertEqual(erg["geloescht"], 7)
        self.assertEqual(erg["behalten"], 1)
        self.assertEqual(read_text(fremd), "FREMD\n", "das Ziel bleibt unberuehrt")
        self.assertTrue(self.alt(208, "json").is_file(), "das Original bleibt liegen")
        self.assertIn("Ziel belegt", aussensicht.ablage_tafel(erg))

    def test_verschieben_trockenlauf_aendert_nichts(self):
        self._alt_lage()
        vorher = {p.name: read_text(p) for p in sorted(self.runs().iterdir())}
        erg = aussensicht.ablage_wandeln(self.cfg, verschieben=True)     # ohne --ausfuehren
        self.assertTrue(erg["verschieben"])
        self.assertFalse(erg["ausgefuehrt"])
        self.assertEqual(erg["kopiert"], 0)
        self.assertEqual(erg["geloescht"], 0)
        self.assertEqual(erg["geplant_kopieren"], 8)
        self.assertEqual(erg["geplant_loeschen"], 8)
        self.assertEqual({z["aktion"] for z in erg["zeilen"]},
                         {"kopieren + Original loeschen"})
        for batch in (208, 209):
            for art in ("md", "json", "jsonl", "err"):
                self.assertFalse(self.neu(batch, art).exists())
                self.assertTrue(self.alt(batch, art).is_file())
        self.assertEqual({p.name: read_text(p) for p in sorted(self.runs().iterdir())}, vorher)
        tafel = aussensicht.ablage_tafel(erg)
        self.assertIn("Trockenlauf", tafel)
        self.assertIn("geplant loeschen: 8", tafel)

    def test_batches_einschraenken(self):
        self._alt_lage()
        erg = aussensicht.ablage_wandeln(self.cfg, batches=[208])
        self.assertEqual(erg["quellen"], 4)
        self.assertEqual({z["batch"] for z in erg["zeilen"]}, {208})

    def test_alle_fuenf_arten_werden_erkannt(self):
        for art, (_neu, alt) in aussensicht.ABLAGE.items():
            name = alt.format(n=7)
            self.assertEqual(aussensicht._alt_art_und_batch(name), (art, 7))  # noqa: SLF001
        for fremd in ("meta-hooks.json", "meta.json", "meta-x.md", "meta-217.md.bak",
                      "meta-.md", "stream.jsonl"):
            self.assertEqual(aussensicht._alt_art_und_batch(fremd), (None, None))  # noqa: SLF001


# --------------------------------------------- 5) Der Befehl in der CLI
class TestCli(Basis):
    def test_cli_kennt_den_befehl(self):
        from hx import cli
        args = cli.build_parser().parse_args(["meta-ablage"])
        self.assertEqual(args.cmd, "meta-ablage")
        self.assertFalse(args.ausfuehren, "Trockenlauf ist die Vorgabe")
        self.assertFalse(args.verschieben, "Verschieben ist nicht die Vorgabe")
        self.assertEqual(args.batches, "")
        args = cli.build_parser().parse_args(["meta-ablage", "--batches", "208-210,215",
                                              "--ausfuehren", "--verschieben"])
        self.assertTrue(args.ausfuehren)
        self.assertTrue(args.verschieben)
        self.assertEqual(args.batches, "208-210,215")

    def test_cli_batchliste_und_tafel(self):
        """Der Befehl selbst laeuft gegen die Wegwerf-Wurzel (kein fremder Baum)."""
        from hx import cli
        write_text_atomic(self.alt(209, "md"), "# Aussensicht Batch 209\n")
        args = cli.build_parser().parse_args(["meta-ablage", "--batches", "209"])
        args.config = None
        cfg = self.cfg
        erg = aussensicht.ablage_wandeln(cfg, ausfuehren=bool(args.ausfuehren),
                                        batches=[209])
        tafel = aussensicht.ablage_tafel(erg)
        self.assertIn("runs/meta-209.md", tafel)
        self.assertIn("runs/b209/meta.md", tafel)
        self.assertFalse(self.neu(209, "md").exists())


if __name__ == "__main__":
    unittest.main()
