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


def ast_zeilen(alt_rows: dict, neu_rows: dict) -> tuple[list[str], int]:
    """Die feste Ast-Tabelle (Reihenfolge = Reihenfolge im Schnappschuss).

    Gezaehlt wird ein Ast als geaendert, wenn sich die Hauptzahl ODER eine Nebenzahl
    bewegt hat - sonst wuerde ein Ast, dessen Nachzuegler sich verschieben, als
    unveraendert erscheinen.
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
        zeilen.append(f"{name:<{breite}} {_kuerzen(a_txt):<{WERTE}} -> "
                      f"{_kuerzen(n_txt):<{WERTE}} {d}")
        if det_neu:
            zeilen.append(f"{'':<{breite}} {det_neu}")
        if det_alt and det_alt != det_neu:
            zeilen.append(f"{'':<{breite}} vorher: {det_alt}")
    return zeilen, geaendert


def zusatz_zeile(neu: dict) -> str:
    z = (neu or {}).get("zusatz") or {}
    if not z:
        return "Zusatz: keine Angaben"
    return ("Zusatz: Faelle %s | R216 a/b/c/d %s/%s/%s/%s | reg_a %s | reg_f %s"
            % (z.get("faelle", "?"), z.get("r216a", "?"), z.get("r216b", "?"),
               z.get("r216c", "?"), z.get("r216d", "?"), z.get("reg_a", "?"),
               z.get("reg_f", "?")))


# ------------------------------------------------------- Projektstand (Teil C)
# Die Zahlen stehen als Prosa in den Belegdateien (Batch-Dokument + Ankerkopf) und
# sind dort FETT gesetzt ("**591 Koepfe / 28858 Insn** in der Bau-Liste"). Die Muster
# lassen die Fettmarken und Zeilenumbrueche zu - im ersten Anlauf scheiterten sie
# daran und die Bilanz zeigte "offen: 2072 Koepfe" (die Inventarzeile, falsch).
_INV = re.compile(r"(\d+)\s*Koepfe\s*/\s*(\d+)\s*Insn\s*\**\s*im Programm-Inventar")
_BAU = re.compile(r"(\d+)\s*Koepfe\s*/\s*(\d+)\s*Insn\s*\**\s*in der Bau-Liste")
_OFFEN = re.compile(r"OFFEN:?[^\d]{0,12}(\d+)\s*Koepfe\s*/\s*\**\s*(\d+)\s*Insn")
_BLATT = re.compile(r"(\d+)\s*Koepfe\s*/\s*\**\s*(\d+)\s*Insn\s*\**\s*keinen offenen Ruf")


def c_stand(cfg) -> dict:
    """Zahlen fuer den Projektstand aus den Belegdateien des Decomp-Repos.

    Gesucht wird in der NEUESTEN Batch-Datei (`analysis/port-batch<N>-*.md`) und, wenn
    sie nichts hergibt, im Ankerkopf. Nichts wird geschaetzt: was nicht dasteht, bleibt
    leer und wird als "nicht ermittelbar" ausgewiesen.
    """
    texte: list[tuple[str, str]] = []
    try:
        adir = Path(cfg.decomp) / "analysis"
        docs = sorted(adir.glob("port-batch*.md"),
                      key=lambda p: p.stat().st_mtime, reverse=True)[:2]
        for p in docs:
            texte.append((f"analysis/{p.name}", read_text(p)[:200000]))
    except OSError:
        pass
    try:
        texte.append((str(Path(cfg.anchor_file).name), read_text(cfg.anchor_file)[:80000]))
    except OSError:
        pass

    out: dict = {}
    for quelle, text in texte:
        m = _INV.search(text)
        if m and "inventar" not in out:
            out["inventar"] = (int(m.group(1)), int(m.group(2)))
            out["quelle"] = quelle
        m = _BAU.search(text)
        if m and "baut" not in out:
            out["baut"] = (int(m.group(1)), int(m.group(2)))
        m = _OFFEN.search(text)
        if m and "offen" not in out:
            out["offen"] = (int(m.group(1)), int(m.group(2)))
        m = _BLATT.search(text)
        if m and "blatt" not in out:
            out["blatt"] = (int(m.group(1)), int(m.group(2)))
        if {"inventar", "offen", "baut"} <= set(out):
            break
    return out


def projekt_block(cfg) -> list[str]:
    st = c_stand(cfg)
    inv, offen, baut = st.get("inventar"), st.get("offen"), st.get("baut")
    zeilen = ["PROJEKTSTAND (Teil C - der systematische Durchgang)"]
    if not inv:
        zeilen.append("  Koepfe/Insn: nicht ermittelbar (kein Beleg gefunden)")
    if inv and offen:
        keb, insb = None, None
        if baut:
            keb, insb = baut
        else:                                   # selbst rechnen statt raten
            keb, insb = inv[0] - offen[0], inv[1] - offen[1]
        def pct(v, g):
            return f"{100.0 * v / g:.1f} %" if g else "?"
        zeilen.append(f"  Inventar : {inv[0]:>5} Koepfe / {inv[1]:>6} Insn")
        zeilen.append(f"  gebaut   : {keb:>5} Koepfe / {insb:>6} Insn  "
                      f"({pct(keb, inv[0])} / {pct(insb, inv[1])})")
        zeilen.append(f"  offen    : {offen[0]:>5} Koepfe / {offen[1]:>6} Insn  "
                      f"({pct(offen[0], inv[0])} / {pct(offen[1], inv[1])})")
        if st.get("blatt"):
            zeilen.append(f"  davon Blaetter (kein offener Ruf): "
                          f"{st['blatt'][0]} Koepfe / {st['blatt'][1]} Insn")
    doc = inventar_prozent(cfg)
    zeilen.append(f"  Programm-Inventar (S1-Doku): {doc}")
    if st.get("quelle"):
        zeilen.append(f"  Quelle: {st['quelle']}"
                      + (" und Ankerkopf" if "port-batch" in str(st.get("quelle")) else ""))
    return zeilen


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


# ------------------------------------------------------------------ Gesamtbericht
def bericht(cfg, n: int = 1, batch: int | None = None, jetzt: datetime | None = None) -> str:
    """Der komplette Bilanz-Bericht (festes Format, Telegram-tauglich)."""
    jetzt_dt = jetzt or datetime.now(timezone.utc)
    daten = snapshot(cfg)
    alle = batch_nummern(daten)
    letzte = int(batch) if batch else (alle[-1] if alle else 0)
    vor = vergleichs_batch(alle, letzte, max(1, int(n)))
    zeilen: list[str] = []

    if not alle:
        zeilen.append("BILANZ: kein Bilanz-Schnappschuss gefunden "
                      f"({snapshot_pfad(cfg)}).")
    else:
        neu_rows = ((daten["batches"].get(str(letzte)) or {}).get("rows") or {})
        alt_rows = ((daten["batches"].get(str(vor)) or {}).get("rows") or {}) if vor else {}
        kopf = f"BILANZ Batch {letzte}"
        if vor:
            kopf += f"   Vergleich: {vor} -> {letzte}   (Abstand {letzte - vor})"
        else:
            kopf += "   Vergleich: kein frueherer Batch vorhanden"
        zeilen.append(kopf)
        stand = snapshot_stand(cfg)
        zeilen.append("Quelle: analysis/" + SNAPSHOT
                      + (f", Stand {stand}" if stand else " (Zeit unbekannt)"))
        zeilen.append("")
        tabelle, geaendert = ast_zeilen(alt_rows, neu_rows)
        zeilen += tabelle
        zeilen.append(f"Geaendert: {geaendert} von {len(neu_rows)} Aesten")
        if n != 1:
            zeilen.append(f"(Vergleichsabstand {n} - '/bilanz 1' zeigt den direkten "
                          "Vorgaenger)")
        zeilen.append("")
        zeilen.append(zusatz_zeile(daten["batches"].get(str(letzte)) or {}))

    zeilen.append("")
    zeilen += projekt_block(cfg)
    zeilen.append("")
    zeilen += kosten_block(cfg, jetzt=jetzt_dt)
    zeilen.append("")
    zeilen += aufgaben_block(cfg, batch=letzte)
    return "\n".join(zeilen)
