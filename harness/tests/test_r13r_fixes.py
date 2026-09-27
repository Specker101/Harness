"""Tests fuer R13r: `/thinking [N] [voll]` - Denkbloecke des laufenden Batches.

Auftrag (Nutzer, 2026-09-27): "/thinking Befehl in Telegram, der mir die letzten 10
thinking eintraege von DeepSeek parst." Entscheidungen des Nutzers:
  * je Eintrag **200 Zeichen** (wie `watch`), zusaetzlich `/thinking 10 voll` ungekuerzt,
  * **live** den laufenden Batch mitlesen,
  * **nur** der DeepSeek-Worker (nicht der Reviewer),
  * fester Suchdeckel **16 MB** (kein neuer Konfigurationsschluessel).

Alles im Attrappenbetrieb: kein Netz, keine API-Kosten, kein Ghidra.
"""

from __future__ import annotations

import io
import json
import sys
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import denken, retention, telegram                              # noqa: E402
from hx.config import load_config                                       # noqa: E402
from hx.orchestrator import Orchestrator                                # noqa: E402
from hx.util import Log, ensure_dir, now_iso, write_text_atomic         # noqa: E402

STAMP = "2026-09-27T12:00:00.000Z"


def _denkzeile(text: str, stamp: str = STAMP, typ: str = "thinking") -> str:
    """Eine Mitschnittzeile mit einem Denkblock (so schreibt claude sie wirklich)."""
    return json.dumps({"type": "assistant", "timestamp": stamp,
                       "message": {"id": "x", "role": "assistant", "content": [
                           {"type": typ, "thinking": text, "signature": "sig"}]}})


def _verdeckte_zeile() -> str:
    """`redacted_thinking` traegt KEINEN Text - es hat nur `data`."""
    return json.dumps({"type": "assistant", "timestamp": STAMP,
                       "message": {"content": [{"type": "redacted_thinking",
                                                 "data": "base64"}]}})


def _textzeile(text: str = "Antwort") -> str:
    """Normale Assistentenzeile - darf NICHT als Denkblock zaehlen."""
    return json.dumps({"type": "assistant", "timestamp": STAMP,
                       "message": {"content": [{"type": "text", "text": text}]}})


def _werkzeugzeile() -> str:
    return json.dumps({"type": "assistant", "timestamp": STAMP,
                       "message": {"content": [{"type": "tool_use", "name": "Read"}]}})


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__file__).resolve().parent / "_tmp_r13r"
        retention._weg(self.tmp)
        self.root = ensure_dir(self.tmp / "harness")
        self.decomp = ensure_dir(self.tmp / "decomp")
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
        retention._weg(self.tmp)

    # ---------------------------------------------------------------- Fixture
    def stream(self, pfad: Path, eintraege: list[str]) -> Path:
        write_text_atomic(pfad, "\n".join(eintraege) + "\n")
        return pfad

    def batch_stream(self, nummer: int = 7, eintraege: list[str] | None = None) -> Path:
        d = ensure_dir(self.root / "runs" / f"b{nummer}")
        return self.stream(d / "stream.jsonl", eintraege or [_denkzeile("Erster")])


# ------------------------------------------------------------------ Tail-Leser
class TestTailLeser(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__file__).resolve().parent / "_tmp_r13r_tail"
        retention._weg(self.tmp)
        ensure_dir(self.tmp)

    def tearDown(self):
        retention._weg(self.tmp)

    def _datei(self, zeilen: list[str], name: str = "stream.jsonl") -> Path:
        p = self.tmp / name
        write_text_atomic(p, "\n".join(zeilen) + "\n")
        return p

    def test_letzte_n_chronologisch(self):
        p = self._datei([_denkzeile(f"Denken {i}") for i in range(1, 6)]
                        + [_textzeile(), _werkzeugzeile()])
        erg = denken.denkbloecke(p, n=3)
        self.assertEqual([e["text"] for e in erg["eintraege"]],
                         ["Denken 3", "Denken 4", "Denken 5"])
        self.assertEqual([e["nr"] for e in erg["eintraege"]], [1, 2, 3])
        self.assertEqual(erg["gefunden"], 3)
        self.assertFalse(erg["deckel"])
        self.assertLessEqual(erg["gelesen_bytes"], erg["groesse_bytes"])

    def test_leere_bloecke_zaehlen_nicht(self):
        p = self._datei([_denkzeile(" echt "), _denkzeile(""), _denkzeile("   "),
                         _verdeckte_zeile(),
                         _denkzeile("zuletzt")])
        erg = denken.denkbloecke(p, n=10)
        self.assertEqual([e["text"] for e in erg["eintraege"]], ["echt", "zuletzt"])
        self.assertEqual(erg["gefunden"], 2)

    def test_angefangene_letzte_zeile_stoert_nicht(self):
        """Bricht der Mitschnitt mitten in einer Zeile ab (Schreiben laeuft), ignorieren."""
        p = self.tmp / "stream.jsonl"
        write_text_atomic(p, "\n".join([_denkzeile("fertig")]) + "\n"
                          + '{"type":"assistant","message":{"content":[{"type":"thin')
        erg = denken.denkbloecke(p, n=5)
        self.assertEqual([e["text"] for e in erg["eintraege"]], ["fertig"])
        self.assertEqual(erg["fehler"], "")

    def test_zwei_bloecke_in_einer_zeile_ergeben_einen_eintrag(self):
        zeile = json.dumps({"type": "assistant", "timestamp": STAMP,
                            "message": {"content": [
                                {"type": "thinking", "thinking": "erst"},
                                {"type": "thinking", "thinking": "dann"}]}})
        erg = denken.denkbloecke(self._datei([zeile]), n=3)
        self.assertEqual(len(erg["eintraege"]), 1)
        self.assertEqual(erg["eintraege"][0]["text"], "erst dann")

    def test_deckel_begrenzt_die_suche(self):
        p = self._datei([_denkzeile(f"Denken {i}") for i in range(1, 21)])
        erg = denken.denkbloecke(p, n=20, max_bytes=400)
        self.assertTrue(erg["deckel"])
        self.assertLess(erg["gefunden"], 20)
        # Der Deckel begrenzt das Fenster; gelesen wird in BLOCK-Schritten.
        self.assertLessEqual(erg["gelesen_bytes"], 400 + denken.BLOCK)

    def test_gepackter_mitschnitt_wird_gelesen(self):
        roh = "\n".join([_denkzeile("alt 1"), _denkzeile("alt 2")]) + "\n"
        z = self.tmp / "stream.jsonl.zip"
        with zipfile.ZipFile(z, "w") as zf:
            zf.writestr("stream.jsonl", roh)
        erg = denken.denkbloecke(z, n=5)
        self.assertTrue(erg["gepackt"])
        self.assertEqual([e["text"] for e in erg["eintraege"]], ["alt 1", "alt 2"])

    def test_fehlende_datei_meldet_fehler_statt_ausnahme(self):
        erg = denken.denkbloecke(self.tmp / "gibtsnicht.jsonl", n=3)
        self.assertEqual(erg["eintraege"], [])
        self.assertIn("Datei fehlt", erg["fehler"])
        self.assertIn("FEHLER", denken.beschreibe(erg))

    def test_ohne_treffer_klare_meldung(self):
        erg = denken.denkbloecke(self._datei([_textzeile(), _werkzeugzeile()]), n=5)
        text = denken.beschreibe(erg)
        self.assertIn("kein Denkblock MIT TEXT gefunden", text)
        self.assertIn("Mitschnitt:", text)

    def test_kuerzung_und_voll(self):
        lang = "A" * 500
        p = self._datei([_denkzeile(lang)])
        kurz = denken.denkbloecke(p, n=1)
        e = kurz["eintraege"][0]
        self.assertEqual(len(e["text"]), 200)
        self.assertTrue(e["gekuerzt"])
        self.assertEqual(e["zeichen"], 500)
        self.assertIn("[+300 Zeichen]", denken.beschreibe(kurz))
        voll = denken.denkbloecke(p, n=1, grenze_zeichen=None)
        self.assertEqual(len(voll["eintraege"][0]["text"]), 500)
        self.assertFalse(voll["eintraege"][0]["gekuerzt"])
        self.assertIn("ungekuerzt", denken.beschreibe(voll))

    def test_zeilenumbrueche_werden_zu_leerzeichen(self):
        """Ein Eintrag bleibt EINE Zeile - sonst wird der Monospace-Block unlesbar."""
        p = self._datei([_denkzeile("erste Zeile\n\n  zweite\tZeile")])
        e = denken.denkbloecke(p, n=1)["eintraege"][0]
        self.assertEqual(e["text"], "erste Zeile zweite Zeile")

    def test_mitschnittgrosse_wird_nicht_gelesen(self):
        """Der Deckel ist fest 16 MB (Nutzerentscheid) - kein neuer Schluessel."""
        self.assertEqual(denken.MAX_SCAN_BYTES, 16 * 1024 * 1024)
        self.assertEqual(denken.GRENZE_ZEICHEN, 200)
        self.assertEqual(denken.STANDARD_N, 10)
        self.assertEqual(denken.MAX_N, 50)


# ------------------------------------------------------------------- Argumente
class TestArgumente(unittest.TestCase):
    def test_vorgabe_und_zahlen(self):
        self.assertEqual(denken.argumente(""), (10, False, ""))
        self.assertEqual(denken.argumente("20"), (20, False, ""))
        self.assertEqual(denken.argumente("10 voll"), (10, True, ""))
        self.assertEqual(denken.argumente("voll"), (10, True, ""))

    def test_grenzen_werden_geklemmt(self):
        self.assertEqual(denken.argumente("0")[0], 1)
        self.assertEqual(denken.argumente("999")[0], 50)

    def test_unbekanntes_ist_ein_fehler(self):
        n, voll, fehler = denken.argumente("abc")
        self.assertTrue(fehler)
        self.assertIn("abc", fehler)


# ---------------------------------------------------------------- Anzeige/Text
class TestAnzeige(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__file__).resolve().parent / "_tmp_r13r_anzeige"
        retention._weg(self.tmp)
        ensure_dir(self.tmp)

    def tearDown(self):
        retention._weg(self.tmp)

    def _erg(self, n=10, grenze=200):
        p = self.tmp / "b9" / "stream.jsonl"
        ensure_dir(p.parent)
        write_text_atomic(p, "\n".join([_denkzeile("Erster Block"),
                                        _denkzeile("Zweiter Block")]) + "\n")
        return denken.denkbloecke(p, n=n, grenze_zeichen=grenze)

    def test_kopf_und_fusszeile(self):
        text = denken.beschreibe(self._erg(), zusatz="laeuft seit 12m34s")
        self.assertIn("DENKEN b9 - letzte 10 Denkbloecke (je 200 Zeichen)", text)
        self.assertIn("laeuft seit 12m34s", text)
        self.assertIn(" 1. 14:00:00 (12 Z.) Erster Block", text)
        self.assertIn("juengster Eintrag:", text)
        self.assertIn("nur 2 gefunden", text)
        self.assertIn("Ungekuerzt: /thinking 10 voll", text)

    def test_batch_aus_pfad(self):
        self.assertEqual(denken.batch_aus_pfad("g:/x/runs/b196/stream.jsonl"), "b196")
        self.assertEqual(denken.batch_aus_pfad("g:/x/runs/env-proof/stream.jsonl"),
                         "env-proof")
        self.assertEqual(denken.batch_aus_pfad("g:/x/runs/b196/stream.jsonl.zip"), "b196")

    def test_mb_mit_komma(self):
        self.assertEqual(denken._mb(28 * 1024 * 1024), "28 MB")
        self.assertEqual(denken._mb(int(1.5 * 1024 * 1024)), "1,5 MB")


# ------------------------------------------------------- Mitschnitt-Auswahl
class TestAuswahl(Basis):
    def test_neuester_batch_ignoriert_nebenlaeufe(self):
        """`runs/` enthaelt auch env-proof und ghidra-smoke - die sind KEIN Batch."""
        for name in ("env-proof", "ghidra-smoke", "b7", "b6x"):
            d = ensure_dir(self.root / "runs" / name)
            write_text_atomic(d / "stream.jsonl", _denkzeile("x") + "\n")
        p = denken.neuester_mitschnitt(self.cfg)
        self.assertEqual(p.parent.name, "b7")

    def test_ohne_batch_kein_mitschnitt(self):
        ensure_dir(self.root / "runs" / "env-proof")
        self.assertIsNone(denken.neuester_mitschnitt(self.cfg))

    def test_mitschnitt_fuer_batch(self):
        p = self.batch_stream(196)
        self.assertEqual(denken.mitschnitt_fuer_batch(self.cfg, 196), p)
        self.assertEqual(denken.mitschnitt_fuer_batch(self.cfg, "196"), p)
        self.assertIsNone(denken.mitschnitt_fuer_batch(self.cfg, "abc"))
        self.assertIsNone(denken.mitschnitt_fuer_batch(self.cfg, 999))


# ------------------------------------------------------------------ /thinking
class TestBefehl(Basis):
    def test_live_nimmt_den_laufenden_batch(self):
        laufend = self.batch_stream(198, [_denkzeile("Ich lese den Anker"),
                                          _denkzeile("Ich baue die Naht")])
        self.batch_stream(197, [_denkzeile("alter Batch")])      # neuerer Ordner nein
        self.orch.state.data["worker"] = {"pid": 1, "started_at": now_iso(),
                                          "log": str(laufend), "session_id": "s"}
        self.orch.state.data["live"] = {"batch": 198, "requests": 12, "cost_usd": 0.03}
        self.assertTrue(self.orch.handle_command("/thinking 1"))
        text, mono = self.gesagt[-1]
        self.assertTrue(mono)
        self.assertIn("DENKEN b198", text)
        self.assertIn("laeuft seit", text)
        self.assertIn("12 Anfragen", text)
        self.assertIn("Ich baue die Naht", text)
        self.assertNotIn("Ich lese den Anker", text)             # nur die letzten 1

    def test_ohne_worker_der_neueste_batch(self):
        self.batch_stream(7, [_denkzeile("Gedanke 7")])
        self.assertTrue(self.orch.handle_command("/thinking"))
        text, _mono = self.gesagt[-1]
        self.assertIn("DENKEN b7", text)
        self.assertIn("Batch beendet", text)

    def test_voll_zeigt_den_ganzen_text(self):
        lang = "B" * 400
        self.batch_stream(7, [_denkzeile(lang)])
        self.orch.handle_command("/thinking 1 voll")
        self.assertIn(lang, self.gesagt[-1][0])
        self.assertNotIn("[+200 Zeichen]", self.gesagt[-1][0])

    def test_unsinn_zeigt_nutzung(self):
        self.assertTrue(self.orch.handle_command("/thinking abc"))
        text, mono = self.gesagt[-1]
        self.assertIn("Nutzung: /thinking", text)
        self.assertFalse(mono)
        self.assertIn("/thinking", telegram.HELP)

    def test_ohne_mitschnitt_klare_meldung(self):
        self.assertTrue(self.orch.handle_command("/thinking"))
        self.assertIn("Kein Mitschnitt gefunden", self.gesagt[-1][0])

    def test_denken_ist_ein_alias(self):
        self.batch_stream(7, [_denkzeile("Alias")])
        self.assertTrue(self.orch.handle_command("/denken"))
        self.assertIn("Alias", self.gesagt[-1][0])

    def test_zusatz_bei_beendetem_batch(self):
        self.batch_stream(7, [_denkzeile("x")])
        self.assertIn("Batch beendet", self.orch.thinking_zusatz(False))

    def test_cli_parser_kennt_thinking(self):
        from hx.cli import build_parser
        a = build_parser().parse_args(["thinking"])
        self.assertEqual((a.n, a.batch, a.voll), (10, 0, False))
        b = build_parser().parse_args(["thinking", "--n", "5", "--batch", "196",
                                       "--voll"])
        self.assertEqual((b.n, b.batch, b.voll), (5, 196, True))

    def test_cli_ausgabe(self):
        from hx.cli import cmd_thinking
        self.batch_stream(7, [_denkzeile("Aus der Konsole")])
        args = type("A", (), {"config": None, "n": 5, "batch": 7, "voll": False})()
        puffer = io.StringIO()
        with mock.patch("hx.cli.load_config", return_value=self.cfg):
            with redirect_stdout(puffer):
                rc = cmd_thinking(args)
        self.assertEqual(rc, 0)
        self.assertIn("DENKEN b7", puffer.getvalue())
        self.assertIn("Aus der Konsole", puffer.getvalue())

    def test_text_mit_backticks_ueberlebt_den_mono_versand(self):
        """Denktexte enthalten Code (`15a24c0`) - der Sender entschaerft sie (R13q)."""
        self.batch_stream(7, [_denkzeile("Committed as `15a24c0`, tree clean")])
        tg = telegram.Telegram("token", ["1"])
        gesendet: list[dict] = []
        tg.call = lambda method, params=None, timeout=40.0, grenze=None: (
            gesendet.append(dict(params or {})) or {"ok": True})
        self.orch.tg = tg
        self.orch.handle_command("/thinking")
        text = [t for t, _m in self.gesagt][-1]
        self.assertIn("15a24c0", text)
        # Der Text selbst darf die Backticks behalten - der Versand entschaerft sie.
        tg.send(text, mono=True)
        block = gesendet[0]["text"]
        self.assertTrue(block.startswith("```\n"))
        self.assertEqual(block.count("`"), 6)
        self.assertIn("15a24c0", block)


if __name__ == "__main__":
    unittest.main()
