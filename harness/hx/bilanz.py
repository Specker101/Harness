"""Bilanz-Bericht fuer Telegram (`/bilanz`) und die Konsole (R13q).

Auftrag (Nutzer, 2026-09-27): ein Befehl, der zeigt,
  * an welchen Aufgaben gearbeitet wird,
  * welche Aeste wieviel Prozent haben - **im Vergleich zum Batch davor** (oder zu
    einem weiter zurueckliegenden Batch, `/bilanz 5`),
  * wie der Projektstand in Teil C steht (Koepfe/Insn gebaut/gesamt),
  * was die letzten 24 Stunden gekostet haben und wie das Abo ausgelastet ist.

Datenquellen (alle nur LESEND, keine Messung, kein Ghidra, kein Netz):
  * `analysis/_bilanz_snapshot.json` im Decomp-Repo - je Batch die 13 Aeste und die
    Zusatzzahlen. Der Schnappschuss wird vom Port-Batch selbst fortgeschrieben
    (`scripts/m149_bilanz.py`), hier wird er nur gelesen.
  * die neueste Batch-Datei `analysis/port-batch<N>-*.md` und der Ankerkopf fuer die
    C-Zahlen (Inventar/gebaut/offen) - sie stehen dort ausdruecklich und gemessen.
  * `runs/b*/result.json` fuer die Kosten der letzten 24 Stunden (bleibt laut R13p
    IMMER unkomprimiert).
  * `logs/rate-limit.json` fuer die Abo-Auslastung (R13p).

Das Format ist FEST: gleiche Zeilenreihenfolge, gleiche Spalten, gleiche Worte -
damit man zwei Berichte ueberlesen kann. Telegram bekommt den Bericht als
Monospace-Block (`say(..., mono=True)`).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import stand
from . import streamjson
from .util import read_json, read_text

SNAPSHOT = "_bilanz_snapshot.json"
KOSTEN_FENSTER_H = 24.0
SPALTEN = 26          # Breite der Namensspalte
WERTE = 22            # Breite je Wert ("vorher"/"jetzt") - laenger wird gekuerzt


# ------------------------------------------------------------------ Daten lesen
def snapshot_pfad(cfg) -> Path:
    return Path(cfg.decomp) / "analysis" / SNAPSHOT


def snapshot(cfg) -> dict:
    """Der Bilanz-Schnappschuss (leer, wenn er fehlt oder unlesbar ist)."""
    d = read_json(snapshot_pfad(cfg), {}) or {}
    return d if isinstance(d, dict) else {}


def snapshot_stand(cfg) -> str:
    """Wann der Schnappschuss zuletzt geschrieben wurde (leer, wenn es ihn nicht gibt)."""
    try:
        ts = snapshot_pfad(cfg).stat().st_mtime
    except OSError:
        return ""
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().strftime(
            "%d.%m.%Y %H:%M")
    except (OSError, OverflowError, ValueError):
        return ""


def batch_nummern(daten: dict) -> list[int]:
    out: list[int] = []
    for k in (daten.get("batches") or {}):
        try:
            out.append(int(k))
        except (TypeError, ValueError):
            continue
    return sorted(out)


def vergleichs_batch(nummern: list[int], jetzt: int, abstand: int) -> int | None:
    """Der Batch, mit dem verglichen wird: der naechste vorhandene <= jetzt-abstand.

    Batch 154 fehlt im Schnappschuss - mit dem direkten Vorgaenger wuerde ein solcher
    Sprung den Vergleich verfaelschen, deshalb wird der naechste VORHANDENE genommen.
    """
    if not nummern or jetzt is None:
        return None
    ziel = jetzt - max(1, int(abstand))
    kleiner = [n for n in nummern if n <= ziel]
    if kleiner:
        return kleiner[-1]
    return None


# ------------------------------------------------------------- Zeilen (festes Format)
def _kuerzen(text: str, breite: int = WERTE) -> str:
    t = " ".join(str(text or "-").split())
    return t if len(t) <= breite else t[:breite - 2] + ".."


def wert(row: dict | None) -> tuple[str, float | None]:
    """Der wichtigste Wert einer Ast-Zeile als KURZtext + Zahl fuer das Delta.

    Bewusst kurz: die Details einer Zeile stehen in `detail()` in einer eigenen
    Unterzeile, sonst muesste die Zahl mitten im Wort abgeschnitten werden (im ersten
    Anlauf passiert: "Insn 4627/7959 (offe.."). Die REIHENFOLGE ist fest - Prozent
    zuerst, dann Insn, dann gebaute Koepfe, dann Paare, dann Modi, dann Knoten.
    """
    if not row:
        return "-", None
    if row.get("pct") is not None:
        von = row.get("s1", row.get("gelesen", row.get("gebaut")))
        total = row.get("total")
        txt = f"{float(row['pct']):.1f} %" + (f" ({von}/{total})" if total else "")
        return txt, float(row["pct"])
    if row.get("insn_gebaut") is not None:
        return (f"Insn {row['insn_gebaut']}/{row.get('insn_gesamt', '?')}",
                float(row["insn_gebaut"]))
    if row.get("named") is not None:
        return f"{row.get('gebaut', '?')} gebaut", float(row.get("gebaut") or 0)
    if row.get("gebaut") is not None and row.get("offen") is not None:
        return f"{row['gebaut']}/{row['offen']}", float(row["gebaut"])
    if row.get("gebaut") is not None and row.get("total") is not None:
        return f"{row['gebaut']}/{row['total']}", float(row["gebaut"])
    if row.get("modi") is not None:
        return str(row["modi"]), float(row["modi"])
    if row.get("a_knoten") is not None:
        return f"A {row['a_knoten']}/{row.get('a_offen', '?')}", float(row["a_knoten"])
    if row.get("knoten") is not None:
        return f"{row['knoten']} Knoten", float(row["knoten"])
    return _kuerzen(row.get("_text") or "-", WERTE), None


def detail(row: dict | None) -> str:
    """Die Nebenzahlen einer Ast-Zeile als eine kurze Zeile (leer, wenn keine)."""
    if not row:
        return ""
    teile: list[str] = []
    if row.get("insn_gebaut") is not None:
        if row.get("koepfe_gesamt"):
            teile.append(f"Koepfe {row.get('koepfe_gebaut', '?')}/{row['koepfe_gesamt']}")
        if row.get("insn_offen") is not None:
            teile.append(f"offen {row['insn_offen']} Insn")
    if row.get("named") is not None:
        teile.append(f"check {row.get('gebaut', '?')}/{row['named']}/{row.get('unnamed', '?')}")
    if row.get("nz_ziel") is not None:
        teile.append(f"NZ {row.get('nz', '?')}/{row['nz_ziel']} "
                     f"({row.get('nz_a', '?')}/{row.get('nz_b', '?')})")
    if row.get("knoten") is not None and row.get("gebaut") is not None:
        teile.append(f"{row['knoten']} Knoten")
    if row.get("insn") is not None:
        teile.append(f"{row['insn']} Insn")
    if row.get("b") is not None:
        teile.append(f"{row['b']} B")
    if row.get("offen_b"):
        teile.append(f"{row['offen_b']} B offen")
    if row.get("a_knoten") is not None and row.get("b_knoten") is not None:
        teile.append(f"B {row['b_knoten']}/{row.get('b_offen', '?')}")
    if not teile:
        return ""
    return _kuerzen(", ".join(teile), 2 * WERTE)


def _delta(alt: float | None, neu: float | None, prozent: bool) -> str:
    if alt is None or neu is None:
        return "?"
    d = neu - alt
    grenze = 0.05 if prozent else 0.5
    if abs(d) < grenze:
        return "="
    return f"{d:+.1f} pp" if prozent else f"{d:+.0f}"


def ast_zeilen(alt_rows: dict, neu_rows: dict,
               nur_prozent: bool = False) -> tuple[list[str], int]:
    """Die feste Ast-Tabelle (Reihenfolge = Reihenfolge im Schnappschuss).

    Gezaehlt wird ein Ast als geaendert, wenn sich die Hauptzahl ODER eine Nebenzahl
    bewegt hat - sonst wuerde ein Ast, dessen Nachzuegler sich verschieben, als
    unveraendert erscheinen. `nur_prozent=True` (R13s, Nutzerentscheid) laesst Zeilen
    OHNE Prozentzahl weg - deren Inhalt steht im Aenderungsblock.
    """
    namen = list(neu_rows.keys())
    breite = max((len(n) for n in namen), default=12) + 2
    zeilen = [f"{'Ast':<{breite}} {'vorher':<{WERTE}} -> {'jetzt':<{WERTE}} Delta"]
    geaendert = 0
    for name in namen:
        alt, neu = alt_rows.get(name), neu_rows.get(name)
        a_txt, a_zahl = wert(alt)
        n_txt, n_zahl = wert(neu)
        prozent = bool((neu or {}).get("pct") is not None)
        d = _delta(a_zahl, n_zahl, prozent)
        det_alt, det_neu = detail(alt), detail(neu)
        if d != "=" or det_alt != det_neu:
            geaendert += 1
        if nur_prozent and fortschritt(neu)[0] is None:
            continue
        zeilen.append(f"{name:<{breite}} {_kuerzen(a_txt):<{WERTE}} -> "
                      f"{_kuerzen(n_txt):<{WERTE}} {d}")
        if det_neu:
            zeilen.append(f"{'':<{breite}} {det_neu}")
        if det_alt and det_alt != det_neu:
            zeilen.append(f"{'':<{breite}} vorher: {det_alt}")
    return zeilen, geaendert


# ------------------------------------------------- Fortschritt in Prozent (R13s)
# Nutzerauftrag 2026-09-28: "ganz oben in der Liste brauche ich das, was sich geaendert
# hat, und das am besten in Prozent, sofern im Vergleich zum Batch davor". Viele Aeste
# haben im Schnappschuss KEINE Prozentzahl, aber eine Gesamtheit - die wird hier
# gerechnet (Nutzerentscheid: selbst rechnen, wo eine Gesamtheit existiert).
OFFEN_ZEILEN = ("Unterbau (B)",)          # Zeilen, die den OFFENEN Rest messen


def fortschritt(row: dict | None) -> tuple[float | None, str]:
    """(Prozent 0..100 oder None, Basis-Text) einer Ast-Zeile.

    Regel (in `docs/bedienung.md` dokumentiert):
      * `pct` vorhanden      -> direkt (327er-Pool, Programm-Inventar)
      * `insn_gebaut`        -> Insn gebaut / Insn gesamt (Audio)
      * `gebaut` + `offen`   -> gebaut / (gebaut + offen)
      * `gebaut` + `total`   -> gebaut / total (Platte B129_PLATE)
      * `gebaut` + `named`   -> gebaut / benannt (R207 rueckwerts)
      * `a_knoten`/`b_knoten`-> (a+b) / (a+b+offen_a+offen_b) (Strang A / B)
      * sonst                -> None (Modi, Unterbau (A)/(B), offene Reste)
    """
    if not row:
        return None, ""
    if row.get("pct") is not None:
        von = row.get("s1", row.get("gelesen", row.get("gebaut")))
        return float(row["pct"]), f"{von}/{row.get('total', '?')}"
    if row.get("insn_gebaut") is not None and row.get("insn_gesamt"):
        g, t = int(row["insn_gebaut"]), int(row["insn_gesamt"])
        return (100.0 * g / t if t else None), f"{g}/{t} Insn"
    if row.get("gebaut") is not None and row.get("offen") is not None:
        g = int(row["gebaut"])
        t = g + int(row["offen"])
        return (100.0 * g / t if t else None), f"{g}/{t}"
    if row.get("gebaut") is not None and row.get("named"):
        g, t = int(row["gebaut"]), int(row["named"])
        return (100.0 * g / t if t else None), f"{g}/{t} benannt"
    if row.get("gebaut") is not None and row.get("total"):
        g, t = int(row["gebaut"]), int(row["total"])
        return (100.0 * g / t if t else None), f"{g}/{t}"
    if row.get("a_knoten") is not None and row.get("b_knoten") is not None:
        g = int(row["a_knoten"]) + int(row["b_knoten"])
        t = g + int(row.get("a_offen") or 0) + int(row.get("b_offen") or 0)
        return (100.0 * g / t if t else None), f"{g}/{t}"
    return None, ""


def _absolut(row: dict | None, einheit: bool = True) -> tuple[int | None, str]:
    """Die Hauptzahl einer Zeile fuer den absoluten Vergleich (None, wenn es keine gibt)."""
    if not row:
        return None, ""
    for schluessel in ("insn_gebaut", "gebaut", "gelesen", "s1", "knoten", "modi"):
        if row.get(schluessel) is not None:
            return int(row[schluessel]), schluessel
    return None, ""


def aenderungen(alt_rows: dict, neu_rows: dict) -> list[dict]:
    """Die BEWEGTEN Aeste, groesste Aenderung zuerst.

    Je Eintrag: Name, Prozent vorher/jetzt, Delta in Prozentpunkten, absolute Zahl
    vorher/jetzt und ihre Einheit. Sortiert nach |pp| (ohne pp: nach |absolut|).
    """
    out: list[dict] = []
    for name in list(neu_rows.keys()) + [n for n in alt_rows if n not in neu_rows]:
        alt, neu = alt_rows.get(name), neu_rows.get(name)
        p_alt, basis_alt = fortschritt(alt)
        p_neu, basis_neu = fortschritt(neu)
        z_alt, _s_alt = _absolut(alt)
        z_neu, _s_neu = _absolut(neu)
        pp = (p_neu - p_alt) if (p_alt is not None and p_neu is not None) else None
        absolut = (z_neu - z_alt) if (z_alt is not None and z_neu is not None) else None
        offen_zeile = name in OFFEN_ZEILEN
        if offen_zeile:
            # Offene Reste: die Insn-Zahl ist das Mass (kleiner ist besser).
            i_alt = (alt or {}).get("insn") or (alt or {}).get("offen_insn")
            i_neu = (neu or {}).get("insn") or (neu or {}).get("offen_insn")
            if i_alt is not None and i_neu is not None:
                absolut = int(i_neu) - int(i_alt)
                z_alt, z_neu = int(i_alt), int(i_neu)
        bewegt = ((pp is not None and abs(pp) >= 0.005)
                  or (absolut is not None and absolut != 0)
                  or (alt is None) != (neu is None))
        if not bewegt:
            continue
        out.append({"name": name, "pp": pp, "p_alt": p_alt, "p_neu": p_neu,
                    "basis_alt": basis_alt, "basis_neu": basis_neu,
                    "z_alt": z_alt, "z_neu": z_neu, "absolut": absolut,
                    "offen": offen_zeile, "neu": alt is None, "weg": neu is None})
    out.sort(key=lambda e: (-(abs(e["pp"]) if e["pp"] is not None else -1.0),
                            -(abs(e["absolut"]) if e["absolut"] is not None else 0)))
    return out


def _bewegt_zeile(e: dict) -> str:
    """Eine Zeile des Aenderungsblocks."""
    name = e["name"]
    if e["neu"]:
        return f"  {name:<18} NEU in diesem Batch"
    if e["weg"]:
        return f"  {name:<18} entfallen (davor {e['basis_alt'] or _z(e['z_alt'])})"
    if e["offen"]:
        d = e["absolut"]
        return (f"  {name:<18} offen {e['z_alt']} -> {e['z_neu']} Insn"
                + (f"   {d:+d}" if d else "   ="))
    if e["pp"] is not None:
        return (f"  {name:<18} {e['p_alt']:5.1f} % -> {e['p_neu']:5.1f} %"
                f"   {e['pp']:+.2f} pp   ({e['basis_alt']} -> {e['basis_neu']})")
    d = e["absolut"]
    return (f"  {name:<18} {e['z_alt']} -> {e['z_neu']}"
            + (f"   {d:+d}" if d else "   ="))


def _z(wert_: int | None) -> str:
    return "?" if wert_ is None else str(wert_)


def aenderungs_block(cfg, alt_rows: dict, neu_rows: dict, batch: int,
                     alt: int | None) -> list[str]:
    """`WAS SICH GEAENDERT HAT` - nur Bewegtes, in Prozent, zuerst die Kernzahlen.

    Vorangestellt sind die Zahlen, die den Batch wirklich ausmachen: die verifizierten
    C-Koepfe (`C Koepfe`) und der gebaute Paket-E-Vorrat. Danach die bewegten Aeste.
    """
    kopf = "WAS SICH GEAENDERT HAT" + (f" ({alt} -> {batch})" if alt else f" (Batch {batch})")
    zeilen = [kopf]
    jetzt = stand.stand_zahlen(cfg)
    if jetzt.get("c_koepfe") is not None and jetzt.get("c_koepfe_vorher") is not None:
        zeilen.append(f"  verifiziert  : +{jetzt['c_koepfe'] - jetzt['c_koepfe_vorher']} "
                      f"Koepfe ({jetzt['c_koepfe_vorher']} -> {jetzt['c_koepfe']}), "
                      f"{jetzt.get('c_abweichungen', 0)} Abweichungen")
    if (jetzt.get("paket_e_koepfe") is not None
            and jetzt.get("paket_e_koepfe_vorher") is not None):
        dk = jetzt["paket_e_koepfe_vorher"] - jetzt["paket_e_koepfe"]
        di = jetzt.get("paket_e_insn_vorher", 0) - jetzt.get("paket_e_insn", 0)
        zeilen.append(f"  Paket E      : {dk} Koepfe / {di} Insn gebaut "
                      f"(offen {jetzt['paket_e_koepfe_vorher']} -> "
                      f"{jetzt['paket_e_koepfe']})")
    bewegt = aenderungen(alt_rows, neu_rows)
    if not bewegt:
        zeilen.append("  Aeste        : keine Zahl bewegt")
        return zeilen
    for e in bewegt:
        zeilen.append(_bewegt_zeile(e))
    prozent_zeilen = sum(1 for e in bewegt if e["pp"] is not None)
    zeilen.append(f"  Aeste        : {len(bewegt)} von {len(neu_rows)} bewegt"
                  + (f", davon {prozent_zeilen} mit Prozentzahl" if prozent_zeilen else ""))
    return zeilen


def zusatz_zeile(neu: dict) -> str:
    z = (neu or {}).get("zusatz") or {}
    if not z:
        return "Zusatz: keine Angaben"
    return ("Zusatz: Faelle %s | R216 a/b/c/d %s/%s/%s/%s | reg_a %s | reg_f %s"
            % (z.get("faelle", "?"), z.get("r216a", "?"), z.get("r216b", "?"),
               z.get("r216c", "?"), z.get("r216d", "?"), z.get("reg_a", "?"),
               z.get("reg_f", "?")))


# ------------------------------------------------------- Projektstand (Teil C)
# R13s: Die Muster und die Dokumentauswahl liegen jetzt in `hx/stand.py` (eine Quelle
# fuer `/bilanz`, `/fragen` und die PLAN/IST-Tafel des Reviews). Hier bleibt nur der
# duenne Verweis, damit die oeffentlichen Namen erhalten bleiben.
_INV = stand._RE_INV
_BAU = stand._RE_BAU
_OFFEN = stand._RE_OFFEN
_BLATT = stand._RE_BLATT


def c_stand(cfg) -> dict:
    """Zahlen fuer den Projektstand aus den Belegdateien des Decomp-Repos (R13q/R13s).

    Gesucht wird in den Batch-Dokumenten `analysis/port-batch<N>-*.md` (Nummer aus dem
    Dateinamen, neuestes zuerst) und, wenn sie nichts hergeben, im Ankerkopf. Nichts
    wird geschaetzt: was nicht dasteht, bleibt leer und wird als "nicht ermittelbar"
    ausgewiesen.
    """
    return stand.stand_zahlen(cfg)


def _pct_teil(ist: int, gesamt: int) -> str:
    return f"{100.0 * ist / gesamt:.1f} %" if gesamt else "?"


def _delta_pp(alt: float | None, neu: float | None) -> str:
    if alt is None or neu is None:
        return ""
    d = neu - alt
    return "=" if abs(d) < 0.05 else f"{d:+.1f} pp"


def _stand_reihe(cfg) -> tuple[dict, dict]:
    """(neuestes, vorheriges) Zahlen-Dokument aus `stand.c_zahlen`."""
    reihe = [e for e in stand.c_zahlen(cfg, 8) if "baut" in e or "c_koepfe" in e]
    if not reihe:
        return {}, {}
    return reihe[-1], (reihe[-2] if len(reihe) > 1 else {})


def gesamt_block(cfg) -> list[str]:
    """`GESAMT` - Projektstand in Prozent, mit Delta zum Vorbatch und Durchsatz.

    Quellen: die Zeilen `C Koepfe` (verifizierte Koepfe/Faelle) und `Paket E offen`
    aus den Batch-Dokumenten (`stand.c_zahlen`), die Bau-Liste/offen-Zahlen, wo ein
    Dokument sie (noch) als Prosa traegt, das Programm-Inventar aus dem
    Bilanz-Schnappschuss und der Durchsatz aus `stand.durchsatz`. Nichts wird
    geschaetzt - was fehlt, steht als "nicht ermittelbar" da.
    """
    jetzt, vorher = _stand_reihe(cfg)
    zeilen = ["GESAMT (Teil C - der systematische Durchgang)"]
    if jetzt.get("c_koepfe") is not None:
        delta = ""
        if jetzt.get("c_koepfe_vorher") is not None:
            dk = jetzt["c_koepfe"] - jetzt["c_koepfe_vorher"]
            df = (jetzt.get("c_faelle", 0) - jetzt.get("c_faelle_vorher", 0))
            delta = f"   ({dk:+d} Koepfe / {df:+d} Faelle in diesem Batch)"
        zeilen.append(f"  C verifiziert: {jetzt['c_koepfe']} Koepfe / "
                      f"{jetzt.get('c_faelle', '?')} Faelle / "
                      f"{jetzt.get('c_abweichungen', 0)} Abweichungen" + delta)
    if jetzt.get("paket_e_koepfe") is not None:
        k, i = jetzt["paket_e_koepfe"], jetzt.get("paket_e_insn", 0)
        bl, bl_i = jetzt.get("paket_e_blatt"), jetzt.get("paket_e_insn_blatt")
        delta = ""
        if jetzt.get("paket_e_koepfe_vorher") is not None:
            dk = jetzt["paket_e_koepfe_vorher"] - k
            di = jetzt.get("paket_e_insn_vorher", 0) - i
            delta = f"   (in diesem Batch: {dk} Koepfe / {di} Insn gebaut)"
        zeilen.append(f"  Paket E offen: {k} Koepfe / {i} Insn"
                      + (f" (Bl {bl} / {bl_i})" if bl is not None else "") + delta)
    else:
        zeilen.append("  Paket E offen: nicht ermittelbar (keine Zeile "
                      "'Paket E offen')")
    inv = jetzt.get("inventar") or vorher.get("inventar")
    baut, baut_alt = jetzt.get("baut"), vorher.get("baut")
    offen, offen_alt = jetzt.get("offen"), vorher.get("offen")
    if inv:
        zeilen.append(f"  Inventar     : {inv[0]:>5} Koepfe / {inv[1]:>6} Insn"
                      "   (Nenner der Prozente, aus dem Batch-Dokument)")
    if baut:
        p_alt = (100.0 * baut_alt[1] / inv[1]) if (baut_alt and inv) else None
        p_neu = (100.0 * baut[1] / inv[1]) if inv else None
        delta = ""
        if baut_alt:
            delta = (f"   {baut[0] - baut_alt[0]:+d} Koepfe / "
                     f"{baut[1] - baut_alt[1]:+d} Insn   {_delta_pp(p_alt, p_neu)}")
        zeilen.append(f"  Bau-Liste    : {baut[0]:>5} Koepfe / {baut[1]:>6} Insn"
                      + (f"  ({_pct_teil(baut[0], inv[0])} / "
                         f"{_pct_teil(baut[1], inv[1])})" if inv else "") + delta)
    if offen:
        p_alt = (100.0 * offen_alt[1] / inv[1]) if (offen_alt and inv) else None
        p_neu = (100.0 * offen[1] / inv[1]) if inv else None
        delta = ""
        if offen_alt:
            delta = (f"   {offen[0] - offen_alt[0]:+d} Koepfe / "
                     f"{offen[1] - offen_alt[1]:+d} Insn   {_delta_pp(p_alt, p_neu)}")
        zeilen.append(f"  offen        : {offen[0]:>5} Koepfe / {offen[1]:>6} Insn"
                      + (f"  ({_pct_teil(offen[0], inv[0])} / "
                         f"{_pct_teil(offen[1], inv[1])})" if inv else "") + delta)
    if jetzt.get("blatt"):
        zeilen.append(f"  davon Blaetter (kein offener Ruf): {jetzt['blatt'][0]} Koepfe / "
                      f"{jetzt['blatt'][1]} Insn")
    zeilen.append(f"  Programm-Inventar (S1-Doku): {inventar_prozent(cfg)}")
    zeilen += stand.durchsatz_zeilen(cfg)
    if jetzt.get("dokument"):
        zeilen.append(f"  Quelle: analysis/{jetzt['dokument']}"
                      + (f" (davor {vorher['dokument']})" if vorher.get("dokument") else ""))
    return zeilen


def projekt_block(cfg) -> list[str]:
    """Alter Name fuer `gesamt_block` (R13q-Aufrufer bleiben gueltig)."""
    return gesamt_block(cfg)


def inventar_prozent(cfg) -> str:
    """`1664 von 2072 = 80,3 %` aus dem Bilanz-Schnappschuss (Programm-Inventar)."""
    daten = snapshot(cfg)
    nummern = batch_nummern(daten)
    if not nummern:
        return "nicht ermittelbar"
    rows = ((daten["batches"].get(str(nummern[-1])) or {}).get("rows") or {})
    row = rows.get("Programm-Inventar") or {}
    if row.get("pct") is None:
        return "nicht ermittelbar"
    return (f"{row.get('s1', '?')} von {row.get('total', '?')} = "
            f"{float(row['pct']):.1f} % (Batch {nummern[-1]})")


# ------------------------------------------------------------------ Kostenblock
def kosten_block(cfg, jetzt: datetime | None = None, fenster_h: float = KOSTEN_FENSTER_H):
    """Kosten der letzten 24 Stunden + Anzahl Batches + Abo-Auslastung (R13q)."""
    jetzt = jetzt or datetime.now(timezone.utc)
    grenze = (jetzt - timedelta(hours=fenster_h)).timestamp()
    summe, anzahl, neueste = 0.0, 0, 0
    try:
        for p in (Path(cfg.sub("runs"))).glob("b*/result.json"):
            try:
                if p.stat().st_mtime < grenze:
                    continue
                d = json.loads(read_text(p)) or {}
            except (OSError, ValueError):
                continue
            summe += float(d.get("cost_usd") or 0)
            anzahl += 1
            try:
                neueste = max(neueste, int(p.parent.name.lstrip("b")))
            except ValueError:
                pass
    except OSError:
        pass
    st = read_json(Path(cfg.sub("state")) / "run.json", {}) or {}
    # Der Zustand fuehrt die Tageskosten unter dem UTC-Datum (`/status` und
    # `budget_text` nehmen `datetime.now(timezone.utc).date()`) - hier dieselbe Basis,
    # sonst zeigt die Bilanz an einem Abend einen anderen Tag als /status.
    heute = jetzt.astimezone(timezone.utc).date().isoformat()
    heute_usd = float(((st.get("spent") or {}).get(heute) or 0))
    budget = float(cfg.get("limits", "daily_budget_usd", 10))
    rl = streamjson.lies_rate_limit(cfg)
    quelle = "logs/rate-limit.json"
    if not rl:
        # Rueckfall: die Datei entsteht erst beim ersten Review nach R13p. Dann wird
        # der NEUESTE vorhandene Review-Mitschnitt ausgewertet (nur die Zeilen mit
        # `rate_limit_event` werden gelesen, `runs/b*/reviewer.jsonl` ist klein) -
        # der Worker-Mitschnitt bleibt ausdruecklich unangetastet.
        try:
            kandidaten = sorted(Path(cfg.sub("runs")).glob("b*/review*.jsonl"),
                                key=lambda p: p.stat().st_mtime, reverse=True)[:3]
        except OSError:
            kandidaten = []
        for p in kandidaten:
            try:
                info = streamjson.rate_limit_aus_mitschnitt(cfg, p)
            except Exception:                                    # noqa: BLE001
                info = {}
            if info:
                rl = {"info": info, "quelle": f"{p.parent.name}/{p.name}",
                      "zeile": streamjson.rate_limit_zeile(info), "ts": ""}
                quelle = rl["quelle"]
                break
    abo = (str(rl.get("zeile") or "keine Angaben") if rl
           else "noch nicht gemessen (kommt aus Review, Uebergabe und /ask)")
    return ["KOSTEN (DeepSeek) UND ABO",
            f"  letzte {fenster_h:.0f} h : ${summe:.4f} aus {anzahl} Batch(es)"
            + (f", neuester b{neueste}" if neueste else ""),
            f"  heute        : ${heute_usd:.4f} von ${budget:.2f}",
            f"  Abo-Auslastung: {abo}",
            f"  Quelle Abo   : {quelle}"
            + (f" (Stand {rl.get('ts')})" if rl and rl.get("ts") else "")]


# ------------------------------------------------------------------ Aufgabenblock
def aufgaben_block(cfg, batch: int | None = None, anzahl: int = 10) -> list[str]:
    """Woran gearbeitet wird: Ankerkopf, offener Auftrag, letzte Batches aus git."""
    zeilen = ["AUFGABEN"]
    try:
        kopf = [ln.strip() for ln in read_text(cfg.anchor_file).splitlines()
                if ln.strip().startswith("**Stand:**")]
    except OSError:
        kopf = []
    if kopf:
        zeilen.append("  Anker: "
                      + _kuerzen(kopf[0].replace("**Stand:**", "").strip(), 200))
    else:
        zeilen.append("  Anker: nicht lesbar")
    st = read_json(Path(cfg.sub("state")) / "run.json", {}) or {}
    gate = st.get("gate") or {}
    instr = str(gate.get("instruction") or "").splitlines()
    if instr:
        zeilen.append("  Offener Auftrag: " + _kuerzen(instr[0], 180))
    else:
        zeilen.append("  Offener Auftrag: keiner")
    betreffe = batch_betreffe(cfg, anzahl)
    if betreffe:
        zeilen.append("  Letzte Batches (git):")
        zeilen += betreffe
    return zeilen


def batch_betreffe(cfg, anzahl: int = 10) -> list[str]:
    """Die Betreffe der letzten Batches aus git (nur lesend, kein Schreibzugriff)."""
    from .gitsafe import Git
    try:
        roh = Git(cfg).out("log", f"--max-count={anzahl * 4}", "--pretty=%h %s")
    except Exception:                                                # noqa: BLE001
        return []
    out: list[str] = []
    for ln in roh.splitlines():
        if re.search(r"\bB\d{2,}\b", ln):
            out.append("  " + _kuerzen(ln, 90))
        if len(out) >= anzahl:
            break
    return out


def _kurz_satz(text: str, grenze: int = 200) -> str:
    """Ersten Satz/Anfang kuerzen, ohne mitten im Wort zu enden."""
    txt = " ".join(str(text or "").split())
    if len(txt) <= grenze:
        return txt
    schnitt = txt[:grenze]
    leer = schnitt.rfind(" ")
    return (schnitt[:leer] if leer > grenze * 0.6 else schnitt) + " ..."


# ------------------------------------------------------------------ Gesamtbericht
def bericht(cfg, n: int = 1, batch: int | None = None, jetzt: datetime | None = None,
            voll: bool = False) -> str:
    """Der komplette Bilanz-Bericht (festes Format, Telegram-tauglich, R13s).

    Reihenfolge (Nutzerauftrag 2026-09-28):
      1. Kopf + `ZULETZT` (was der Batch laut Anker geschafft hat)
      2. `WAS SICH GEAENDERT HAT` - nur Bewegtes, in Prozent, gegen den Batch davor
      3. `GESAMT` - Bau-Liste/Paket E/Inventar in Prozent + DURCHSATZ (HYPOTHESIS)
      4. Aeste-Tabelle (nur Zeilen MIT Prozentzahl; `voll=True` zeigt alle)
      5. Zusatzzahlen, Kosten/Abo, Aufgaben
    """
    jetzt_dt = jetzt or datetime.now(timezone.utc)
    daten = snapshot(cfg)
    alle = batch_nummern(daten)
    letzte = int(batch) if batch else (alle[-1] if alle else 0)
    vor = vergleichs_batch(alle, letzte, max(1, int(n)))
    kopfzeilen: list[str] = []
    if not alle:
        kopfzeilen.append("BILANZ: kein Bilanz-Schnappschuss gefunden "
                          f"({snapshot_pfad(cfg)}).")
        return "\n".join(kopfzeilen + [""] + gesamt_block(cfg) + [""]
                         + kosten_block(cfg, jetzt=jetzt_dt))

    neu_rows = ((daten["batches"].get(str(letzte)) or {}).get("rows") or {})
    alt_rows = ((daten["batches"].get(str(vor)) or {}).get("rows") or {}) if vor else {}
    kopf = f"BILANZ Batch {letzte}"
    if vor:
        kopf += f" gegen {vor}   (Abstand {letzte - vor})"
    else:
        kopf += "   (kein frueherer Batch vorhanden)"
    kopfzeilen.append(kopf)
    kopf = stand.anchor_bloecke(cfg)
    anker_batch = stand._batch_aus_anker(kopf)
    kopfzeilen.append(f"Anker: BATCH {anker_batch or '?'} | Bilanz: {letzte}"
                      + ("   ACHTUNG: Anker und Bilanz sind verschiedene Batches"
                         if anker_batch and anker_batch != letzte else ""))
    if kopf.get("Fertig"):
        kopfzeilen.append("ZULETZT: " + _kurz_satz(kopf["Fertig"], 220))

    zeilen = kopfzeilen + [""]
    zeilen += aenderungs_block(cfg, alt_rows, neu_rows, letzte, vor)
    zeilen.append("")
    zeilen += gesamt_block(cfg)
    zeilen.append("")
    tabelle, geaendert = ast_zeilen(alt_rows, neu_rows, nur_prozent=not voll)
    zeilen += tabelle
    zeilen.append(f"Geaendert: {geaendert} von {len(neu_rows)} Aesten"
                  + ("   (volle Tabelle: /bilanz voll)" if not voll else ""))
    if n != 1:
        zeilen.append(f"(Vergleichsabstand {n} - '/bilanz 1' zeigt den direkten "
                      "Vorgaenger)")
    zeilen.append("")
    zeilen.append(zusatz_zeile(daten["batches"].get(str(letzte)) or {}))
    zeilen.append("")
    # R13w: die letzte Aussensicht (Meta-Review) mit offenen Befunden.
    try:
        from . import aussensicht as aussichtmod
        az = aussichtmod.zeile(cfg)
    except Exception:                                                    # noqa: BLE001
        az = ""
    if az:
        zeilen.append(az)
        zeilen.append("")
    zeilen += kosten_block(cfg, jetzt=jetzt_dt)
    zeilen.append("")
    zeilen += aufgaben_block(cfg, batch=letzte)
    return "\n".join(zeilen)
