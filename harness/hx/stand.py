"""Stand des Projekts aus den Belegdateien (R13s, Auftrag 2026-09-28).

Der Nutzer will zwei Dinge sehen, die bisher in Prosa versteckt waren:
  1. **Was sich bewegt hat** (in Prozent, gegen den Batch davor) und **wie schnell**
     (verifizierte C-Koepfe/Insn je Batch, Mittel der letzten 5, Hochrechnung).
  2. **Welche Fragen an IHN offen sind** - jede als eine entscheidbare Zeile.

Quellen (alle nur LESEND, kein Ghidra, kein Netz, kein Mitschnitt):
  * `analysis/r1b-workstream.md` - der Ankerkopf mit `**Stand:**`, `**Fertig:**`,
    `**Naechster Schritt:**`, `**Offene Entscheidung:**`. Die Zeilen sind lang (eine
    Zeile je Block) und werden hier in ihre `(n) …`-Posten zerlegt.
  * `analysis/port-batch<N>-*.md` - je Batch die **Soll/Ist-Bilanztafel**. Dort stehen
    die harten Zahlen als Tabellenzeilen, z. B.

        | **C Koepfe** | 73 / 1752 / 0 | **78 / 1872 / 0** | `c_kopf.py vergl alle` |
        | Paket E offen | 43 Koepfe / 3025 Insn (Bl 20 / 1434) | **38 / 2674 (Bl 15 / 1083)** | `c_kopf.py paket_e` |

    Die Vorbatch-Spalte und die fette Ist-Spalte geben **vorher -> nachher** je Batch:
    daraus entsteht der Durchsatz und die PLAN/IST-Tafel im Review.
  * `runs/b<N>/result.json` und `runs/b<N>/harness-facts.md` - Laufzeit und
    Abbruchgrund des Batches.
  * `runs/b<N>/auftrag.md` - die Instruktion, die der Worker bekam (fuer die
    PLAN-Spalte: die dort genannten Kopf-Adressen).
  * das letzte Review (`runs/b<N>/review.md`) - die Marker-Zeilen des Reviewers
    (`ENTSCHEIDUNG NOETIG:`, `OFFENE FRAGE:`, `WARTET AUF LIVE-AUFNAHME:`,
    `ENTSCHIEDEN:`) ueber `protocol.parse_offene_punkte`.

Grundsatz: was nicht dasteht, wird NICHT geschaetzt - es steht als "nicht ermittelbar"
bzw. "UNKLAR FORMULIERT" in der Ausgabe (Nutzerentscheid 2026-09-28).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from . import protocol
from .util import (read_json, read_text, read_text_erkannt, ist_utf16)

# Bloecke des Ankerkopfs (Projektkonvention, AGENTS.md "Session-Kontinuitaet").
BLOECKE = ("Stand", "Fertig", "Naechster Schritt", "Offene Entscheidung", "Fallstricke")
STANDARD_FENSTER = 5
MAX_DOKUMENTE = 12
# R13ac (M210-2): Das Fenster der C-Koepfe-Trendzeile. Es ist dasselbe wie im
# Aussensicht-Prompt ("BILANZ: TREND DER LETZTEN 12 BATCHES", aussensicht.grenzen) -
# damit Reviewer, Aussensicht und Bilanz dieselbe Spanne nennen.
TREND_FENSTER = 12
# R13bn (M242-3): so viele C-Batches am ENDE der Reihe belegen, dass Strang B ruht -
# dann gilt fuer die Kalender-Hochrechnung der Anteil 100 % (alle Batches sind C).
# Ein einzelner C-Batch nach einem B-Batch ist der normale Wechsel und zaehlt nicht.
C_LAUF_MINDESTENS = 2

# --------------------------------------------------------------- Ankerkopf
_KOPFZEILE = re.compile(r"^\*\*(?P<name>[^:*]{2,30}):\*\*\s*(?P<text>.*)$")
# Die Posten stehen fett in der Zeile: "**(5) NEU:** …" - deshalb muss vor der
# Klammer auch ein `*` erlaubt sein (erster Anlauf scheiterte daran und zeigte
# "keine offenen Fragen", obwohl (5) und (6) offen sind).
_POSTEN = re.compile(r"(?:^|[\s*])\((?P<nr>\d+)\)\s*")


def anchor_bloecke(cfg) -> dict[str, str]:
    """Die Kopfbloecke des Ankers als `{Name: Text}` (leer, wenn nicht lesbar)."""
    text = ""
    try:
        text = read_text(cfg.anchor_file)
    except OSError:
        return {}
    out: dict[str, str] = {}
    for zeile in text.splitlines()[:12]:
        m = _KOPFZEILE.match(zeile.strip())
        if m:
            out.setdefault(m.group("name").strip(), m.group("text").strip())
    return out


def _posten(text: str) -> list[tuple[str, str]]:
    """Eine Blockzeile in ihre `(n) …`-Posten zerlegen: [("(5)", "NEU: …"), …]."""
    treffer = list(_POSTEN.finditer(text or ""))
    if not treffer:
        return [("", (text or "").strip())] if (text or "").strip() else []
    out: list[tuple[str, str]] = []
    for i, t in enumerate(treffer):
        ende = treffer[i + 1].start() if i + 1 < len(treffer) else len(text)
        out.append((f"({t.group('nr')})", text[t.end():ende].strip(" *.\t")))
    return out


def offene_entscheidungen(text: str) -> tuple[list[tuple[str, str]], int]:
    """Offene Posten `[(nr, text)]` und Anzahl der GESCHLOSSENen.

    R13ac2 (Nutzerauftrag 2026-09-29): siehe `posten_status` - Posten, die ein
    **Sammel-Schluss** mitzieht, zaehlen NICHT als offen. Diese Funktion bleibt der
    schmale Zugang fuer die Anzeigen; wer die mitgezogenen Posten nennen will, nimmt
    `posten_status`.
    """
    offen, geschlossen, _ohne = posten_status(text)
    return offen, geschlossen


# R13ac2 (Nutzerauftrag 2026-09-29): ein Block schliesst seine Posten auch SAMMELWEISE.
# Gemessen am echten Anker (`analysis/r1b-workstream.md`, Zeile "Offene Entscheidung"):
#   "Alle Posten GESCHLOSSEN. **(1)** R391 …: GESCHLOSSEN … **(4)** A1 MEM-Varianten,
#    **(5)** `42704`, **(6)** Schrittdatei/`mutalle`: GESCHLOSSEN als Entscheidungsposten –
#    … **Keine offene Nutzerfrage.**"
# (4) und (5) tragen KEIN eigenes Statuswort, wurden aber als A4/A5 unter "OFFENE FRAGEN
# AN DICH" gefuehrt. Solche Posten sind keine Fragen - aber sie verschwinden auch nicht
# still, sondern stehen unter "ZUR KENNTNIS" mit dem Grund.
_RE_SAMMEL_SCHLUSS = re.compile(
    r"alle\s+posten\s+geschlossen"
    r"|geschlossen\s+als\s+(?:entscheidungs|anker)[-\s]?(?:posten|frage)"
    r"|keine\s+offene\s+(?:nutzer|anker)?frage",
    re.IGNORECASE)
# Ein eigenes Statuswort eines Postens. Fehlt es UND schliesst der Block sammelweise,
# ist der Posten mitgezogen.
_RE_EIGENER_STATUS = re.compile(
    r"\b(?:GESCHLOSSEN|ENTSCHEIDEN|ENTSCHIEDEN|ZURUECKGESTELLT|ZURÜCKGESTELLT|NEU|OFFEN|"
    r"FRAGE|WARTET)\b", re.IGNORECASE)


def posten_status(text: str) -> tuple[list[tuple[str, str]], int, list[tuple[str, str]]]:
    """(offen, Anzahl geschlossener, sammelweise geschlossene ohne eigenes Wort).

    Ein Posten ist **offen**, wenn er weder "GESCHLOSSEN" traegt noch von einem
    Sammel-Schluss mitgezogen wird. Die dritte Liste nennt die Mitgezogenen, damit die
    Anzeige sie zeigen kann, statt sie zu verschweigen.
    """
    posten = _posten(text)
    sammel = bool(_RE_SAMMEL_SCHLUSS.search(text or ""))
    offen: list[tuple[str, str]] = []
    geschlossen = 0
    ohne: list[tuple[str, str]] = []
    for nr, txt in posten:
        if "GESCHLOSSEN" in txt.upper():
            geschlossen += 1
            continue
        if sammel and not _RE_EIGENER_STATUS.search(txt):
            ohne.append((nr, txt))
            continue
        offen.append((nr, txt))
    return offen, geschlossen, ohne


# --------------------------------------------------- entscheidbare Frage (R13s)
# R13z (Nutzerauftrag 2026-09-28): eine Frage darf auch zwischen **zwei Wegen** waehlen
# (A/B) - dann heissen die Folgen "bei A:" / "bei B:" und die Empfehlung ist der
# Buchstabe. Die Frageform bleibt dieselbe (Satz mit Fragewort, endet auf "?"); steht in
# ihr ausdruecklich eine Alternative (`(A) … (B)` oder `A oder B`), genuegt auch das.
_EMPFEHLUNG = re.compile(r"(?:Vorschlag|Empfehlung)\s*:?\s*\**\s*(ja|nein|kein\w*|[ab])\b",
                         re.IGNORECASE)
_BEI = re.compile(r"bei\s+(ja|nein|a|b)\s*[:=]\s*([^|;.\n]+)", re.IGNORECASE)
_FRAGEWORT = (r"(?:soll|sollen|ist|sind|bleibt|bleiben|wird|werden|kann|kannst|darf|muss|"
              r"muessen|gibt)\b")
_ALTERNATIVEN = re.compile(r"\((?:A|B)\)|\bA\s*(?:oder|/)\s*B\b|\b(?:Weg|Variante)\s+[AB]\b")


def entscheidbar(text: str) -> dict | None:
    """Versucht aus einem Ankerposten EINE entscheidbare Zeile zu machen.

    Gebraucht werden drei Teile: eine **Frage**, eine **Empfehlung** und die **Folgen**.
    Die Frage ist entweder eine **Ja/Nein-Frage** (Satz, der mit einem Fragewort beginnt
    und auf `?` endet) oder eine **A/B-Frage** (R13z); die Folgen heissen dann
    `bei ja:`/`bei nein:` bzw. `bei A:`/`bei B:`. Nur wenn die Prosa sie hergibt, ist der
    Posten entscheidbar - sonst meldet die Anzeige "UNKLAR FORMULIERT" (Nutzerentscheid
    2026-09-28: nichts still umdeuten).

    Die Frage wird NICHT am Zeilenanfang gesucht: die Ankerposten haben oft eine lange
    Vorrede ("die Fallfabrik erreicht … NICHT - **soll** `prof` … fahren?"). Gesucht
    wird der letzte Satz, der mit einem Ja/Nein-Wort beginnt und mit `?` endet.
    """
    txt = " ".join(str(text or "").split())
    if not txt:
        return None
    m = _EMPFEHLUNG.search(txt)
    if not m:
        return None
    frage = _fragesatz(txt, alternativen=bool(_ALTERNATIVEN.search(txt)))
    if not frage:
        return None
    folgen = {k.lower(): " ".join(v.split()) for k, v in _BEI.findall(txt)}
    wert = m.group(1).lower()
    return {"frage": frage,
            "empfehlung": wert.upper() if wert in ("a", "b") else wert,
            "bei_ja": folgen.get("ja", ""),
            "bei_nein": folgen.get("nein", ""),
            "bei_a": folgen.get("a", ""),
            "bei_b": folgen.get("b", "")}


def _fragesatz(txt: str, alternativen: bool) -> str:
    """Der Fragesatz aus dem Posten ('' = keiner gefunden).

    Regel zuerst: der Satz, der mit einem Fragewort beginnt und mit `?` endet - alles
    nach dem `?` interessiert nicht. Nur wenn in dem Posten eine **A/B-Alternative**
    steht (`(A)`/`(B)`, `A oder B`, `Weg A`), genuegt auch ein Fragesatz ohne Fragewort
    ("…: (A) Wähler oder (B) Nahtliste?") - dann wird der LETZTE Fragesatz genommen.
    """
    treffer = re.search(r"(?P<frage>" + _FRAGEWORT + r"[^?]*\?)", txt, re.IGNORECASE)
    roh = treffer.group("frage") if treffer else ""
    if not roh and alternativen:
        saetze = re.findall(r"[^?]*\?", txt)
        roh = saetze[-1] if saetze else ""
    roh = roh.strip(" *.")
    # Der Vorschlag steht meist in Klammern IN der Frage - er gehoert zur Empfehlung.
    # Achtung: das Fragezeichen steht HINTER der Klammer und geht beim Abschneiden
    # verloren - es wird deshalb wieder angehaengt.
    roh = re.split(r"\((?:Vorschlag|Empfehlung)", roh)[0].strip(" *.,;")
    if not roh:
        return ""
    return roh if roh.endswith("?") else roh + "?"


# ------------------------------------------------------------ Batch-Dokumente
_RE_INV = re.compile(r"(\d+)\s*Koepfe\s*/\s*(\d+)\s*Insn\s*\**\s*im Programm-Inventar")
_RE_BAU = re.compile(r"(\d+)\s*Koepfe\s*/\s*(\d+)\s*Insn\s*\**\s*in der\s*Bau-Liste")
_RE_OFFEN = re.compile(r"OFFEN:?\s*\**\s*(\d+)\s*Koepfe\s*/\s*\**\s*(\d+)\s*Insn")
_RE_BLATT = re.compile(r"(\d+)\s*Koepfe\s*/\s*\**\s*(\d+)\s*Insn\s*\**\s*keinen offenen Ruf")

# ---------------------------------------------- Soll/Ist-Zeilen der Dokumente (R13x)
# Befund M208-3 (Aussensicht, 2026-09-28): die alten Muster schnitten die ERSTE
# passende Tabellenzeile irgendwo im Dokument heraus. In jedem Batch-Dokument steht
# aber die **Vorhersagetafel** (Paragraph 5) VOR der **Soll/Ist-Tafel** (Paragraph 6) -
# die erste Zeile traegt also den Sollwert, nicht die Messung. Gemessen an den echten
# Dateien: b208 Paragraph 5 "Soll B208 78 / 2903 / 0" (nur eine Zahlspalte) und
# Paragraph 6 "Soll 78/2903 | Ist 78/2903"; b207 schreibt das Etikett in Backticks
# (`**`C Koepfe`**`), b204 schreibt die Ist-Spalte fett - beides fiel durch die alten
# Muster, die Anzeige fiel still auf ein AELTERES Dokument zurueck (B206: 78/1872).
#
# Neue Regel, gegen alle Dokumente B198..B208 geprueft (docs/_r13x_belege.md):
#   1. alle Markdown-Zeilen, deren ERSTE Zelle (ohne `*`/Backticks) das Etikett ist;
#   2. die LETZTE dieser Zeilen (die Soll/Ist-Tafel steht hinten);
#   3. in ihr die LETZTE Zelle, die MIT dem Zahlenmuster BEGINNT (die Spalte
#      "Abweichung/Quelle" am Zeilenende beginnt mit Text und faellt damit heraus).
# Die drei Zahlen der C-Koepfe-Zeile sind Koepfe / FAELLE / Abweichungen (78*24 = 1872) -
# die zweite Zahl ist also NICHT die Insn-Zahl. Die Insn je Batch kommen aus der
# Paket-E-Zeile (dort steht "Insn" wirklich) oder aus der Preflight-Zeile.
_RE_ZAHL_CKOPF = re.compile(r"(\d+)\s*/\s*(\d+)\s*/\s*(\d+)")
# "| Paket E offen | 38 / 2674 (Bl 17 / 1202) |" und "| 42 / 2974, Blaetter 12 / 1072 |"
_RE_ZAHL_PAKET_E = re.compile(r"(\d+)\s*(?:Koepfe)?\s*/\s*(\d+)\s*(?:Insn)?\s*[,(]?\s*"
                             r"Bl(?:aetter)?\s*(\d+)\s*/\s*(\d+)\s*\)?")
_ETIKETT_CKOPF = "c koepfe"
_ETIKETT_PAKET_E = "paket e offen"

_DOKU = re.compile(r"port-batch(\d+)")
_MDIR = re.compile(r"_m(\d+)$")
# Preflight-Datei des Decomp-Repos: `analysis/_preflight_<N>.txt` (gueltige Laeufe;
# Fehllaeufe heissen `_preflight_<N>_fehllauf<k>.txt` und liegen in `analysis/_m<N>/`).
_RE_PREFLIGHT_NAME = re.compile(r"_preflight_(\d+)\.txt$")


def _preflight_zeile(etikett: str, zahlen: str, luecke: int = 40) -> re.Pattern[str]:
    """Ein tolerantes Muster fuer eine maschinengeschriebene Preflight-Zeile (R13ae).

    Anlass (Befund 2026-09-29): ab B212 schrieb `scripts/preflight.py`
    `C Koepfe referenzgleich 78 / 4006 / 0` statt `C Koepfe           78 / 4006 / 0`.
    Das alte Muster `^C Koepfe\\s+(\\d+)` verlangte die Zahlen **direkt** hinter dem
    Etikett und erkannte die Zeile deshalb nicht mehr - der Parser lieferte still
    `None`, `c_trend` endete bei B211 und zeigte weiter 2795 statt 4006.

    Deshalb: zwischen Etikett und Zahlen duerfen bis zu `luecke` Zeichen **Prosa**
    stehen (`[^\\d\\n]`, also kein Zeilenwechsel und keine Ziffer - damit kann die Luecke
    nicht in eine andere Zahlenspalte rutschen), und **hinter** den Zahlen ist ein
    Zusatz erlaubt (`| ausgeduennt 12`, `referenzgleich`, `OK`), weil keins der Muster
    am Zeilenende verankert ist.
    """
    return re.compile(rf"^{re.escape(etikett)}\b[^\d\n]{{0,{luecke}}}{zahlen}")


# C-Kopfzeile: "C Koepfe           78 / 2903 / 0     OK" und
#               "C Koepfe referenzgleich 78 / 4006 / 0        OK" (ab B212).
_RE_PREFLIGHT_CKOPF = _preflight_zeile("C Koepfe", r"(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\b")
# Zeile der kanonischen Bilanzdatei:
#   | **R207 rueckwaerts** | **681** (a 30 …) | **686** (a 30 …) | `preflight.py` … |
_RE_R207_DATEI = re.compile(r"R207 rueckwaerts\*\*\s*\|\s*[^|]*?\*\*(\d+)\*\*[^|]*\|\s*"
                            r"[^|]*?\*\*(\d+)\*\*")
# Dieselbe Zeile im Batch-Dokument:  | R207 rueckwaerts | 681 (a 30/b 0/c 0) | **686** … |
_RE_R207_DOKU = re.compile(r"R207 rueckwaerts\s*\|\s*(\d+)[^|]*\|\s*\*\*(\d+)\*\*")


def bilanz_je_batch(cfg, anzahl: int = MAX_DOKUMENTE) -> list[dict]:
    """Die kanonischen Bilanzdateien `analysis/_m<N>/_bilanz*.txt` je Batch.

    Diese Dateien schreibt `scripts/m149_bilanz.py` am Batch-Ende selbst - sie tragen
    je Ast die Spalten "Vorbatch (B<N-1>)" und "heute (mit N)", also **vorher ->
    nachher** ohne Prosa-Raten. Genau daraus entsteht der Durchsatz.
    Die Dateinamen sind historisch uneinheitlich (`_bilanz.txt`, `_bilanz_196.txt`,
    `_bilanz204.txt`) - deshalb wird je `_m<N>`-Ordner die neueste passende genommen.
    """
    try:
        adir = Path(cfg.decomp) / "analysis"
        ordner: list[tuple[int, Path]] = []
        for d in adir.glob("_m*"):
            m = _MDIR.search(d.name)
            if d.is_dir() and m:
                ordner.append((int(m.group(1)), d))
    except OSError:
        return []
    out: list[dict] = []
    for nummer, d in sorted(ordner)[-max(1, anzahl):]:
        kandidaten = sorted(d.glob("_bilanz*.txt"), key=lambda p: p.stat().st_mtime,
                            reverse=True)
        if not kandidaten:
            continue
        try:
            text = read_text(kandidaten[0])[:200000]
        except OSError:
            continue
        m = _RE_R207_DATEI.search(text)
        if not m:
            continue
        out.append({"batch": nummer, "dokument": f"{d.name}/{kandidaten[0].name}",
                    "r207_vorher": int(m.group(1)), "r207": int(m.group(2)),
                    "koepfe": int(m.group(2)) - int(m.group(1))})
    return out


def _r207_aus_dokumenten(cfg, reihe: list[dict]) -> None:
    """Fehlende Batches aus den Batch-Dokumenten nachtragen (R207 steht in beiden)."""
    haben = {e["batch"] for e in reihe}
    for batch, pfad in dokumente(cfg, MAX_DOKUMENTE):
        if batch in haben:
            continue
        try:
            text = read_text(pfad)[:200000]
        except OSError:
            continue
        m = _RE_R207_DOKU.search(text)
        if m:
            reihe.append({"batch": batch, "dokument": pfad.name,
                          "r207_vorher": int(m.group(1)), "r207": int(m.group(2)),
                          "koepfe": int(m.group(2)) - int(m.group(1))})
    reihe.sort(key=lambda e: e["batch"])


# R13aw (Aussensicht B219, Befund M219-3): die Zeile `Paket E offen` der Soll/Ist-Tafel
# ist als QUELLE unbrauchbar geworden - B219 rechnete noch mit dem B208-Stand (38/2674),
# waehrend gemessen 26/2114 waren. Massgeblich ist die MESSUNG selbst
# (`python scripts/c_kopf.py paket_e`), die ihr Protokoll nach
# `analysis/_m<N>/_c_paket_e*.txt` schreibt - mit Datum und HEAD im Kopf.
RE_PAKET_E_GESAMT = re.compile(
    r"Paket E,\s*offen GESAMT\s*:\s*(\d+)\s*Koepfe\s*/\s*(\d+)\s*Insn")
RE_PAKET_E_ORDNER = re.compile(r"^_m(\d+)$")
# R13ba-Nachtrag: das Messdatum steht in zwei Formaten in den Dateien (im Kopf nachgesehen,
# 30.09.2026 - nicht geraten):
#   `_m219/_c_paket_e_nachher.txt:2`  "# Messung: 2026-09-30 03:33, HEAD 5b7eaf6, …"
#   `_m222/_c_paket_e_vorher.txt:1`   "# PAKET-E-STAND VORHER - Batch 222, Datum
#                                      2026-09-30, HEAD babf57c"
# `_m222/_c_paket_e.txt` traegt GAR KEIN Datum - dafuer gilt die Dateizeit (s. u.).
RE_PAKET_E_DATUM = (
    re.compile(r"^#\s*Messung:\s*([0-9]{4})-([0-9]{2})-([0-9]{2})"
               r"(?:[ ,T]+([0-9]{1,2}:[0-9]{2}))?", re.M),
    re.compile(r"\bDatum:?\s+([0-9]{4})-([0-9]{2})-([0-9]{2})"
               r"(?:[ ,T]+([0-9]{1,2}:[0-9]{2}))?", re.I),
)
# "im Kopf nachsehen": nur die ersten Zeilen werden fuer das Datum gelesen.
PAKET_E_KOPF_ZEILEN = 15


def paket_e_datum(text: str, mtime: float = 0.0) -> tuple[str, str]:
    """`(datum, quelle)` aus dem Kopf einer Paket-E-Messdatei (R13ba-Nachtrag).

    Gelesen werden nur die ersten `PAKET_E_KOPF_ZEILEN` Zeilen und nur die zwei Formate,
    die die Messdateien wirklich tragen (`# Messung: <Tag> [Zeit]`, `Datum <Tag> [Zeit]`).
    Fehlt beides, gilt die **Aenderungszeit der Datei** - `quelle` heisst dann
    `"dateizeit"`, die Anzeige schreibt "(Datum aus Dateizeit)", und die Review-Fakten
    melden `PARSER: Messdatum in <Datei> nicht erkannt`.

    `("", "")` heisst: weder Datum noch Dateizeit lesbar (Datei nicht mehr da).
    """
    kopf = "\n".join((text or "").splitlines()[:PAKET_E_KOPF_ZEILEN])
    for muster in RE_PAKET_E_DATUM:
        m = muster.search(kopf)
        if m:
            tag = "-".join(m.group(1, 2, 3))
            return (f"{tag} {(m.group(4) or '').strip()}".strip(), "kopf")
    if mtime:
        return (datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"), "dateizeit")
    return ("", "")


def paket_e_messung(cfg, log=None) -> dict:
    """Die JUENGSTE Paket-E-Messung aus `analysis/_m<N>/_c_paket_e*.txt` (R13aw).

    Rueckgabe `{}`, wenn es keine gibt. Sonst:

        {"koepfe": 25, "insn": 2011, "batch": 222, "zeile": 127,
         "datei": "_m222/_c_paket_e.txt", "datum": "2026-09-30 13:44",
         "kopf": False, "datum_quelle": "dateizeit", "stand": "",
         "vorher": {...} oder None}

    **Auswahl (R13ba-Nachtrag, Nutzerauftrag 30.09.2026):** primaer nach der
    **Batchnummer aus dem Ordnernamen** (`_m<N>`), dann `nachher` vor der blossen Messung
    vor `vorher`; das Datum aus dem Dateikopf ist nur noch **Anzeige** und
    **Gleichstand-Entscheider** (innerhalb eines Batches), **nie** Hauptkriterium.
    Anlass (Befund aus R13ba): die B222-Dateien tragen kein `# Messung:`-Datum, deshalb
    standen sie mit dem alten Schluessel `(datum, mtime, …)` HINTEN - gewaehlt wurde
    weiter B219 (26 statt 25 Koepfe), und der Vorher-Vergleich kippte zu
    `(B222 -> B219: -1 Koepfe / -103 Insn gebaut)`.

    Das Datum wird **tolerant** gelesen (`paket_e_datum`); fehlt es, gilt die Dateizeit
    (gekennzeichnet). `vorher` ist die naechstaeltere Messung mit ANDEREM Wert (fuer das
    Delta "gebaut"), `vorher_gleich` eine aeltere Datei mit demselben Wert (Befund
    M219-4: die "Vorher"-Messung des Werkzeugs war keine).
    """
    basis = Path(cfg.decomp) / "analysis"
    kandidaten: list[dict] = []
    try:
        dateien = sorted(basis.glob("_m*/_c_paket_e*.txt"))
    except OSError:
        dateien = []
    for p in dateien:
        if not RE_PAKET_E_ORDNER.match(p.parent.name):
            continue
        # R13bb (M224-4, Punkt 4): dieselbe Lesefunktion wie bei den Preflight-Dateien -
        # `_m224/_c_paket_e_nachher.txt` ist UTF-8-**BOM**, und mit `read_text` (UTF-8) stand
        # das BOM vor dem `#`, das Messdatum passte nicht und die Datei galt als datumslos.
        try:
            text, kodierung = read_text_erkannt(p)
            text = text[:200000]
        except OSError:
            continue
        m = RE_PAKET_E_GESAMT.search(text)
        if not m:
            continue
        zeile = next((i for i, z in enumerate(text.splitlines(), 1)
                      if RE_PAKET_E_GESAMT.search(z)), 0)
        stand = ("nachher" if "nachher" in p.name.lower()
                 else ("vorher" if "vorher" in p.name.lower() else ""))
        try:
            mtime = p.stat().st_mtime
        except OSError:
            mtime = 0.0
        datum, datum_quelle = paket_e_datum(text, mtime)
        batch = int(p.parent.name[2:])
        kandidaten.append({
            "koepfe": int(m.group(1)), "insn": int(m.group(2)),
            "batch": batch, "zeile": zeile,
            "datei": p.relative_to(basis).as_posix(), "datum": datum,
            "datum_quelle": datum_quelle, "kopf": datum_quelle == "kopf",
            "stand": stand, "kodierung": kodierung,
            # Rang des Dateinamens INNERHALB eines Batches: nachher (2) vor der blossen
            # Messung (1) vor vorher (0); danach erst das Datum, dann die Zeit, der Name.
            "_sort": (batch, 2 if stand == "nachher" else (1 if not stand else 0),
                      datum, mtime, p.name)})
    if not kandidaten:
        if log:
            log.info("Paket-E-Messung: keine Datei gefunden",
                     suchmuster=str(basis / "_m*/_c_paket_e*.txt"))
        return {}
    kandidaten.sort(key=lambda e: e["_sort"])
    neu = kandidaten[-1]
    aeltere = kandidaten[:-1]
    # `vorher`: die naechstaeltere Messung mit ANDEREM Wert (das ist ein echter Schritt).
    aelter = next((e for e in reversed(aeltere)
                   if e["koepfe"] != neu["koepfe"] or e["insn"] != neu["insn"]), None)
    # `vorher_gleich`: eine aeltere Datei mit DEMSELBEN Wert. In B219 liegen `_vorher` und
    # `_nachher` beide bei 26 (Befund M219-4: die "Vorher"-Messung des Werkzeugs war keine).
    # Das wird benannt, statt es zu verschweigen.
    gleich = next((e for e in reversed(aeltere)
                   if e["batch"] == neu["batch"] and e["koepfe"] == neu["koepfe"]
                   and e["insn"] == neu["insn"]), None)
    aus = {k: v for k, v in neu.items() if not k.startswith("_")}
    aus["vorher"] = ({k: v for k, v in aelter.items() if not k.startswith("_")}
                      if aelter else None)
    aus["vorher_gleich"] = ({k: v for k, v in gleich.items() if not k.startswith("_")}
                             if gleich else None)
    if log:
        log.info("Paket-E-Messung gelesen", datei=aus["datei"], koepfe=aus["koepfe"],
                 insn=aus["insn"], datum=aus["datum"] or "(kein Datum)",
                 datum_quelle=aus["datum_quelle"], stand=aus["stand"] or "-")
    return aus


def paket_e_datum_hinweis(cfg, log=None) -> list[str]:
    """PARSER-Hinweis fuer die Review-Fakten: Messdatum nicht erkannt (R13ba-Nachtrag).

    Nur der Fehlerfall wird gemeldet: die gewaehlte Messdatei traegt kein lesbares Datum,
    es gilt die **Dateizeit** (die Anzeige sagt es mit "(Datum aus Dateizeit)"). Der
    Fachbegriff steht am Zeilenanfang (`PARSER:`), damit er maschinell auffindbar ist.

    R13bb (Punkt 4): wurde die Datei als **UTF-16** gelesen, steht das in der Meldung -
    dann ist die Kodierung die Ursache und keine fehlende Datumszeile. Ist das Datum trotz
    UTF-16 lesbar (der Regelfall seit R13bb), meldet die Funktion die Kodierung als eigene
    Zeile, damit die Lesetoleranz nachpruefbar bleibt.
    """
    m = paket_e_messung(cfg, log=log)
    if not m:
        return []
    utf16 = ist_utf16(m.get("kodierung"))
    if m.get("datum_quelle") == "dateizeit":
        zeile = (f"PARSER: Messdatum in {m['datei']} nicht erkannt"
                 + (f" ({m.get('kodierung')} gelesen)" if utf16 else "")
                 + f" - es gilt die Dateizeit ({m['datum']}); gemessen B{m['batch']}, "
                 f"{m['koepfe']} Koepfe / {m['insn']} Insn")
        if log:
            log.info("PARSER: Messdatum nicht erkannt", datei=m["datei"],
                     dateizeit=m["datum"], batch=m["batch"], kodierung=m.get("kodierung"))
        return [zeile]
    if not m.get("datum"):
        return [f"PARSER: Weder Messdatum noch Dateizeit in {m['datei']} lesbar"]
    if utf16:
        return [(f"PAKET-E-KOPFZEILE: {m['datei']} in {m['kodierung']} gelesen - "
                 f"Datum erkannt ({m['datum']}), gemessen B{m['batch']}")]
    return []


def paket_e_offen_text(messung: dict | None, letzter_dok_batch: int | None = None) -> str:
    """`26 Koepfe / 2114 Insn [gemessen B219, …]` oder der ehrliche Fehlvermerk. """
    if messung:
        herkunft = f"gemessen B{messung['batch']}"
        if messung.get("datum"):
            herkunft += f", {messung['datum']}"
        if messung.get("datum_quelle") == "dateizeit":
            herkunft += " (Datum aus Dateizeit)"
        return (f"{messung['koepfe']} Koepfe / {messung['insn']} Insn"
                f"   [{herkunft}: {messung['datei']}]")
    seit = f" seit B{int(letzter_dok_batch)}" if letzter_dok_batch else ""
    return (f"nicht gemessen{seit} (keine Datei analysis/_m*/_c_paket_e*.txt)")


def preflight_archiv(cfg, batch: int) -> dict:
    """Archivierte Preflight-Laeufe EINES Batches aus `analysis/_m<N>/` (M224-4, R13bb).

    Gezaehlt werden:

      * `_preflight_<N>_fehllauf*.txt` - ein Lauf, der nicht als gueltig gilt. Genau diese
        Laeufe fehlten dem Zaehler des Harness in B218, B223 und B224 (Befund M224-4): der
        PostToolUse-Hook schreibt nur, was er sieht.
      * `_preflight_<N>*ueberholt*.txt` - ein Lauf, den ein spaeterer ueberholt hat.

    **Nicht** gezaehlt wird `_preflight_<N>_vor_fortsetzung<k>.txt`: das ist die byteweise
    Kopie eines Laufs, der schon gezaehlt ist (R13ah). Ebenfalls aussen vor bleiben die
    Nicht-Lauf-Dateien desselben Ordners (`_preflight_zeiten.txt`, `_preflight_vergleich.txt`,
    `_preflight_stderr*.txt`, `*zwischenlauf*`).

    Rueckgabe: `{"fehllauf": [rel…], "ueberholt": [rel…], "ungezaehlt": int, "dateien":
    [rel…], "ordner": "_m<N>", "gefunden": bool}`. `ungezaehlt` ist die **Differenz**, um
    die der gezaehlte Wert zu niedrig liegt.
    """
    ordner = Path(cfg.decomp) / "analysis" / f"_m{int(batch)}"
    fehllauf: list[str] = []
    ueberholt: list[str] = []
    try:
        dateien = sorted(ordner.glob(f"_preflight_{int(batch)}*.txt"))
    except OSError:
        dateien = []
    for p in dateien:
        if "vor_fortsetzung" in p.name:
            continue
        rel = p.relative_to(Path(cfg.decomp)).as_posix()
        if "fehllauf" in p.name:
            fehllauf.append(rel)
        elif "ueberholt" in p.name:
            ueberholt.append(rel)
    return {"fehllauf": fehllauf, "ueberholt": ueberholt, "ungezaehlt": len(fehllauf),
            "dateien": fehllauf + ueberholt, "ordner": f"_m{int(batch)}",
            "gefunden": bool(fehllauf or ueberholt)}


def _mitschnitt_dateien(rd) -> list[Path]:
    """`stream.jsonl` und die Fortsetzungen in zeitlicher Reihenfolge (R13be-1)."""
    rd = Path(rd)
    haupt = rd / "stream.jsonl"
    forts = sorted(rd.glob("stream-forts*.jsonl"),
                   key=lambda p: int("".join(c for c in p.stem if c.isdigit()) or 0))
    return [p for p in ([haupt] + forts) if p.is_file()]


def _iso_zeit(text) -> datetime | None:
    """`2026-09-30T16:53:04.123Z` -> datetime (aware), sonst None."""
    try:
        return datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def mitschnitt_preflight_aufrufe(cfg, batch: int, start_zeit: datetime | None = None,
                                 umschalt_min: float | None = None,
                                 nachrueckliste: bool = False) -> dict:
    """Jeder PREFLIGHT-**Start** im Mitschnitt von `runs/b<N>` (R13be-1, Nutzerauftrag).

    **Warum aus dem Mitschnitt.** Der PostToolUse-Hook `tools/batch_uhr.py` schreibt seine
    Zeile nur nach **erfolgreichen** Werkzeugaufrufen. Gemessen (B220-B229): ein Preflight
    mit Befunden endet mit Exit 2, das ist `is_error=true` - der Hook laeuft dann nicht.
    B228 hatte **zwei** echte Starts (`22:44:54`, `23:00:58`) und `preflight_laeufe=0`;
    die Zaehldatei fehlt vollstaendig. Der Mitschnitt kennt beide, der Hook keinen.
    Ueber B220-B228 gilt exakt: Zaehldatei-Zeilen = Starts - Aufrufe mit `is_error`
    (17 - 6 = 11, `docs/_r13be_belege.md`).

    Gezaehlt wird mit `streamjson.ist_preflight_aufruf` - derselben Regel wie beim Hook und
    beim Fortsetzungs-Check (`worker.preflight_gestartet`). Bloße Erwaehnungen
    (`Select-String -Path scripts/preflight.py`) zaehlen nicht.

    `frueh` = Aufruf **vor** der Umschaltschwelle `umschalt_min`, wenn `nachrueckliste`
    gilt - dieselbe Definition wie beim Hook (`tools/batch_uhr.py`). Ohne `start_zeit`
    wird sie aus `result.json` abgeleitet (`finished_at - duration_s`).

    Rueckgabe: `{"laeufe", "frueh", "aufrufe": [{"ts", "min", "is_error", "werkzeug"}],
    "dateien": [Name, …], "start": iso|None}`.
    """
    from . import streamjson
    rd = Path(cfg.sub("runs")) / f"b{int(batch):03d}"
    start = start_zeit
    if start is None:
        d = read_json(rd / "result.json", None)
        if isinstance(d, dict) and d.get("finished_at") and d.get("duration_s"):
            ende = _iso_zeit(d["finished_at"])
            if ende is not None:
                start = ende - timedelta(seconds=float(d["duration_s"]))
    starts: dict[str, dict] = {}
    ergebnisse: dict[str, bool] = {}
    ergebnis_ts: dict[str, str] = {}
    dateien: list[str] = []
    for p in _mitschnitt_dateien(rd):
        dateien.append(p.name)
        for zeile in (read_text(p) or "").splitlines():
            # Nur Zeilen mit einem Aufruf oder einem Ergebnis ansehen - die `system`-Zeilen
            # sind die Masse des Mitschnitts. WICHTIG: NICHT auf den Text "preflight"
            # filtern, das ERGEBNIS eines Preflight-Aufrufs nennt ihn nicht (nur `exit=0`
            # oder `Exit code 2`) - genau daran scheiterte der erste Anlauf dieser Zaehlung.
            if '"tool_use"' not in zeile and '"tool_result"' not in zeile:
                continue
            try:
                satz = json.loads(zeile)
            except ValueError:
                continue
            for block in ((satz.get("message") or {}).get("content") or []):
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    if streamjson.ist_preflight_aufruf(block.get("name"), block.get("input")):
                        starts[str(block.get("id"))] = {
                            "ts": str(satz.get("timestamp") or ""),
                            "werkzeug": str(block.get("name") or "")}
                elif block.get("type") == "tool_result":
                    kennung = str(block.get("tool_use_id"))
                    ergebnisse[kennung] = bool(block.get("is_error"))
                    ergebnis_ts[kennung] = str(satz.get("timestamp") or "")
    aufrufe: list[dict] = []
    for kennung, s in starts.items():
        t = _iso_zeit(s["ts"])
        minuten = None
        if t is not None and start is not None:
            minuten = max(0.0, (t - start).total_seconds() / 60.0)
        # R13bf (Aussensicht B233, Befund M233-7): die DAUER jedes Laufs. Ohne sie zaehlt
        # die Kennzahl "Preflight-Anteil" nur einen Lauf (B233: 10,2 min statt ~37 min).
        dauer_s: float | None = None
        e = _iso_zeit(ergebnis_ts.get(kennung) or "")
        if t is not None and e is not None and e >= t:
            dauer_s = round((e - t).total_seconds(), 1)
        aufrufe.append({"ts": s["ts"], "min": (round(minuten, 1) if minuten is not None
                                                else None),
                        "is_error": ergebnisse.get(kennung),
                        "dauer_s": dauer_s,
                        "ende": ergebnis_ts.get(kennung) or "",
                        "werkzeug": s["werkzeug"]})
    aufrufe.sort(key=lambda a: a["ts"])
    frueh = 0
    if nachrueckliste and umschalt_min is not None:
        frueh = sum(1 for a in aufrufe
                    if a["min"] is not None and a["min"] < float(umschalt_min))
    return {"laeufe": len(aufrufe), "frueh": frueh, "aufrufe": aufrufe,
            "dauer_s": round(sum(float(a["dauer_s"] or 0.0) for a in aufrufe), 1),
            "ohne_dauer": sum(1 for a in aufrufe if a["dauer_s"] is None),
            "dateien": dateien,
            "start": (start.isoformat() if start is not None else None)}


def preflight_zaehler_zeile(cfg, batch: int, laeufe: int | None = None,
                            frueh: int | None = None, hook: int | None = None,
                            mitschnitt: int | None = None) -> list[str]:
    """Eine Zeile fuer die Review-Fakten: Preflight-Zaehler gegen das Archiv (R13bb).

    **R13be-1:** Die belastbare Zahl kommt aus dem **Mitschnitt** (`mitschnitt_preflight_
    aufrufe`), der Hook-Zaehler steht als Kontrolle daneben. Weichen sie ab, wird das als
    HINWEIS markiert - der Hook sieht nur erfolgreiche Aufrufe (Exit 0), ein Preflight mit
    Befunden (Exit 2) fehlt dort. Wortlaut: `PREFLIGHT-AUFRUFE: 2 (Quelle Stream),
    Hook-Zaehler: 0 [HINWEIS: …]; 2 Aufruf(e) im Mitschnitt (davon 1 zu frueh), …`.

    `laeufe`/`frueh` sind die wirksamen Zahlen (Vorgabe: die groessere der beiden Quellen).
    Sind sie `None`, werden beide Quellen hier gelesen - so benutzt der Rueckblick fuer
    aeltere Batches dieselbe Funktion.
    """
    ms: dict | None = None
    if mitschnitt is None:
        ms = mitschnitt_preflight_aufrufe(cfg, batch)
        mitschnitt = ms["laeufe"]
    hook_frueh: int | None = None
    if hook is None:
        hook, hook_frueh = zaehle_preflight_aufrufe(cfg, batch)
    if laeufe is None:
        laeufe = max(int(hook), int(mitschnitt))
    if frueh is None:
        if hook_frueh is None:
            _h, hook_frueh = zaehle_preflight_aufrufe(cfg, batch)
        if ms is None:
            ms = mitschnitt_preflight_aufrufe(cfg, batch)
        frueh = max(int(ms["frueh"]), int(hook_frueh))
    quelle = "Stream" if int(mitschnitt) else "Hook"
    teile = (f"PREFLIGHT-AUFRUFE: {int(laeufe)} (Quelle {quelle}), "
             f"Hook-Zaehler: {int(hook)}")
    if int(hook) != int(mitschnitt):
        teile += ("  [HINWEIS: die beiden Zahlen weichen ab - der Hook zaehlt nur "
                  "erfolgreiche Aufrufe (Exit 0), Aufrufe mit Befunden (Exit 2) oder "
                  "Fehllaeufe fehlen dort]")
    teile += (f"; {int(laeufe)} Aufruf(e) im Mitschnitt "
              f"(davon {int(frueh)} zu frueh)")
    arch = preflight_archiv(cfg, batch)
    gesamt = max(int(laeufe), int(hook) + int(arch["ungezaehlt"]))
    if arch["fehllauf"]:
        gezeigt = ", ".join(arch["fehllauf"][:3])
        if len(arch["fehllauf"]) > 3:
            gezeigt += f", +{len(arch['fehllauf']) - 3} weitere"
        if gesamt > int(laeufe):
            teile += (f", {arch['ungezaehlt']} archivierte(r) Fehllauf/Fehllaeufe nicht "
                      f"gezaehlt ({gezeigt}) -> {gesamt} Laeufe")
        else:
            teile += (f", {arch['ungezaehlt']} Fehllauf/Fehllaeufe archiviert "
                      f"({gezeigt} - im Mitschnitt enthalten)")
    else:
        teile += f", keine archivierten Fehllaeufe ({arch['ordner']})"
    if arch["ueberholt"]:
        teile += (f"; {len(arch['ueberholt'])} ueberholt abgelegt "
                  f"({', '.join(arch['ueberholt'][:3])} - dort evtl. schon gezaehlt)")
    return [teile]


# Werkzeuge, die eine Datei SCHREIBEN. Der erste solche Aufruf ist der Anker fuer
# "erste inhaltliche Arbeit" - alles davor (Anker lesen, git status, Memory-Sync,
# Preflight) ist Startroutine. Absichtlich als Teilwort-Treffer, weil Modell und MCP
# dieselbe Sache verschieden benennen (`Edit`, `str_replace_in_file`, `create_file`, …).
SCHREIB_WERKZEUGE = ("edit", "write", "replace", "create", "notebookedit")


def _mitschnitt_werkzeuge(rd) -> list[dict]:
    """Alle `tool_use`-Bloecke im Mitschnitt mit Zeitstempel (R13be-3).

    Nur Zeilen mit `"tool_use"` ansehen - die `system`-Zeilen sind die Masse des
    Mitschnitts (FALLSTRICK aus R13be-1: ein Textfilter auf "preflight" verliert die
    Ergebniszeilen, weil sie den Aufruf nicht nennen).
    """
    treffer: list[dict] = []
    for p in _mitschnitt_dateien(rd):
        for zeile in (read_text(p) or "").splitlines():
            if '"tool_use"' not in zeile:
                continue
            try:
                satz = json.loads(zeile)
            except ValueError:
                continue
            for block in ((satz.get("message") or {}).get("content") or []):
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    treffer.append({"ts": str(satz.get("timestamp") or ""),
                                    "name": str(block.get("name") or ""),
                                    "id": str(block.get("id") or "")})
    return treffer


def aufwand_anteile(cfg, batch: int, start_zeit=None, ende_zeit=None) -> dict:
    """Fester Aufwand gegen Arbeitszeit (R13be-3, Nutzerauftrag 01.10.2026).

    **Die Frage.** Der feste Aufwand eines Batches (Startroutine, Preflight, Bilanz,
    Memory-Export) faellt bei JEDEM Batch einmal an. Bei kurzen Batches frisst er einen
    grossen Teil der Wanduhr; nur laengere Batches strecken ihn. Diese Kennzahl macht
    das messbar, statt es zu schaetzen.

    **Definition (vier Teile, in Minuten und Prozent der Wanduhr):**

    * `startroutine` = Startzeit bis zum **ersten schreibenden Werkzeugaufruf**
      (`SCHREIB_WERKZEUGE`). Enthaelt Anker lesen, `git status`, Memory-Sync, einen
      frueh gestarteten Preflight. Gibt es keinen Schreibaufruf im Mitschnitt (reine
      Mess-/Analyse-Batches), bleibt der Anteil **0** - das ist nicht "kein Aufwand",
      sondern "kein Anker", und steht so in der Zeile.
    * `preflight` = **Summe der Dauer ALLER Preflight-Laeufe** des Batches (Mitschnitt
      inklusive Fortsetzungen, je Aufruf `Werkzeugstart -> Werkzeugergebnis`).
      **R13bf (Aussensicht B233, Befund M233-7):** vorher war das nur der Fensteranteil
      "letzter Start bis Laufende" - bei vier Laeufen wie in B233 (je ~9 min) standen
      dort 10,2 min statt rund 37 min.
    * `schluss` = Ende des **letzten** Preflights bis Laufende (Bilanz, Memory-Export,
      Antwort schreiben) - der Rest des frueheren "Schluss"-Anteils.
    * `arbeit` = Wanduhr minus `startroutine` + `preflight` + `schluss` (nie negativ).
      `fester_min`/`fester_pct` ist die Summe der drei festen Teile - die Zahl, um die es
      bei der Batch-Laenge geht.

    **Zeitquelle.** `Start` = `worker.started_at` aus dem Zustand (live) bzw.
    `result.json: finished_at - duration_s` (Rueckblick). `Ende` = `finished_at`
    (live: der Augenblick, in dem `result.json` geschrieben wird). Beide Wege liefern
    dieselbe Zahl, der Rueckblick ist also keine zweite Rechnung.

    Rueckgabe: `{"wand_min", "startroutine_min", "preflight_min", "schluss_min",
    "arbeit_min", "fester_min", "*_pct", "erste_arbeit", "letzter_preflight",
    "letzter_preflight_ende", "preflight_aufrufe", "preflight_ohne_dauer", "aufrufe",
    "quelle"}` - alle Zahlen `None`, wenn keine Start-/Endzeit vorliegt.
    """
    rd = Path(cfg.sub("runs")) / f"b{int(batch):03d}"
    d = read_json(rd / "result.json", None)
    d = d if isinstance(d, dict) else {}
    ende = ende_zeit or _iso_zeit(d.get("finished_at"))
    start = start_zeit
    quelle = "zustand" if start is not None else ""
    if start is None and d.get("finished_at") and d.get("duration_s"):
        e2 = _iso_zeit(d["finished_at"])
        if e2 is not None:
            start = e2 - timedelta(seconds=float(d["duration_s"]))
            quelle = "result.json"
    leer = {"wand_min": None, "startroutine_min": None, "preflight_min": None,
            "schluss_min": None, "arbeit_min": None, "fester_min": None,
            "startroutine_pct": None, "preflight_pct": None, "schluss_pct": None,
            "arbeit_pct": None, "fester_pct": None, "erste_arbeit": "",
            "letzter_preflight": "", "letzter_preflight_ende": "",
            "preflight_aufrufe": 0, "preflight_ohne_dauer": 0,
            "aufrufe": 0, "quelle": ""}
    if start is None or ende is None:
        return leer
    wand_min = (ende - start).total_seconds() / 60.0
    if wand_min <= 0:
        return leer
    ereignisse = _mitschnitt_werkzeuge(rd)
    erste = ""
    for e in ereignisse:
        if not any(w in e["name"].lower() for w in SCHREIB_WERKZEUGE):
            continue
        t = _iso_zeit(e["ts"])
        if t is not None and start <= t <= ende:
            erste = e["ts"]
            break
    pf = mitschnitt_preflight_aufrufe(cfg, batch, start_zeit=start)
    drin = [a for a in pf["aufrufe"] if (_iso_zeit(a["ts"]) or start) <= ende]
    letzter = drin[-1]["ts"] if drin else ""
    # Ende des letzten Laufs: sein Ergebniszeitpunkt; ohne Ergebnis (Abbruch mitten im
    # Lauf) bleibt nur der Start - dann deckt der Schlussanteil ihn ab.
    letzter_ende = (drin[-1].get("ende") or "") if drin else ""
    sr_min = ((_iso_zeit(erste) - start).total_seconds() / 60.0) if erste else 0.0
    sr_min = max(0.0, min(sr_min, wand_min))
    # M233-7: die SUMME aller Laeufe, nicht das Fenster ab dem letzten Start.
    pf_min = sum(float(a["dauer_s"] or 0.0) for a in drin) / 60.0
    pf_min = max(0.0, min(pf_min, wand_min))
    if drin:
        ab = _iso_zeit(letzter_ende) or _iso_zeit(letzter) or ende
        schluss_min = max(0.0, (ende - ab).total_seconds() / 60.0)
    else:
        schluss_min = 0.0
    fester = min(wand_min, sr_min + pf_min + schluss_min)
    arbeit_min = max(0.0, wand_min - fester)

    def pct(x: float) -> float:
        return round(x / wand_min * 100.0, 1)

    return {"wand_min": round(wand_min, 1), "startroutine_min": round(sr_min, 1),
            "preflight_min": round(pf_min, 1), "schluss_min": round(schluss_min, 1),
            "arbeit_min": round(arbeit_min, 1), "fester_min": round(fester, 1),
            "startroutine_pct": pct(sr_min), "preflight_pct": pct(pf_min),
            "schluss_pct": pct(schluss_min), "arbeit_pct": pct(arbeit_min),
            "fester_pct": pct(fester), "erste_arbeit": erste,
            "letzter_preflight": letzter, "letzter_preflight_ende": letzter_ende,
            "preflight_aufrufe": len(drin),
            "preflight_ohne_dauer": sum(1 for a in drin if a["dauer_s"] is None),
            "aufrufe": len(ereignisse), "quelle": quelle}


def aufwand_zeile(cfg, batch: int, res: dict | None = None) -> list[str]:
    """Eine Zeile fuer die Review-Fakten: fester Aufwand gegen Arbeitszeit (R13be-3).

    Nimmt die Kennzahl aus `result.json` (`aufwand`), wenn sie dort steht **und die neue
    Form hat** (`fester_min`, R13bf) - sonst wird sie aus Mitschnitt und `result.json`
    nachgerechnet. Damit gilt derselbe Wortlaut fuer den laufenden Batch und fuer den
    Rueckblick aelterer Batches (B220-B234 tragen die alte Drei-Teile-Form).
    """
    a = None
    if isinstance(res, dict):
        a = res.get("aufwand") if isinstance(res.get("aufwand"), dict) else None
    else:
        d = read_json(Path(cfg.sub("runs")) / f"b{int(batch):03d}" / "result.json", None)
        if isinstance(d, dict) and isinstance(d.get("aufwand"), dict):
            a = d["aufwand"]
    # R13bf: ein Feld aus der ALTEN Definition (drei Teile, R13be-3) wird nicht angezeigt -
    # ihm fehlt `fester_min`, und `schluss` steckte damals im Preflight-Anteil. Statt eine
    # 0 zu zeigen, wird nachgerechnet (B220-B234 tragen alle noch die alte Form).
    if a is None or a.get("wand_min") is None or a.get("fester_min") is None:
        a = aufwand_anteile(cfg, batch)
    if a.get("wand_min") is None:
        return [f"AUFWAND: nicht messbar (keine Start-/Endzeit fuer b{int(batch):03d})"]
    def m(x) -> str:
        return f"{float(x):.0f} min"
    n = int(a.get("preflight_aufrufe") or 0)
    teile = (f"AUFWAND: {m(a['wand_min'])} gesamt = "
             f"{m(a['startroutine_min'])} Startroutine ({a['startroutine_pct']:.0f} %) + "
             f"{m(a['preflight_min'])} Preflight ({n} Lauf/Laeufe, "
             f"{a['preflight_pct']:.0f} %) + "
             f"{m(a.get('schluss_min') or 0)} Schluss/Bilanz ({a.get('schluss_pct', 0):.0f} %)"
             f"  -> fester Aufwand {m(a.get('fester_min') or 0)} "
             f"({a.get('fester_pct', 0):.0f} %), Arbeit {m(a['arbeit_min'])} "
             f"({a['arbeit_pct']:.0f} %)")
    if not a.get("erste_arbeit"):
        teile += " [ohne schreibenden Werkzeugaufruf im Mitschnitt - Startroutine umfasst den ganzen Vorlauf]"
    if not a.get("letzter_preflight"):
        teile += " [kein Preflight im Mitschnitt - Preflight- und Schlussanteil 0]"
    if a.get("preflight_ohne_dauer"):
        teile += (f" [davon {int(a['preflight_ohne_dauer'])} Lauf/Laeufe ohne Ergebnis "
                  "im Mitschnitt - Dauer nicht messbar]")
    if a.get("quelle") == "result.json":
        teile += " (Start aus result.json nachgerechnet)"
    return [teile]


def zaehle_preflight_aufrufe(cfg, batch: int) -> tuple[int, int]:
    """`(Aufrufe, davon frueh)` aus `runs/b<N>/preflight-aufrufe.jsonl` (R13bb).

    Dieselbe Definition wie im Worker (`worker.zaehle_preflight_aufrufe`) - hier nur mit der
    Batchnummer statt dem Ordner, damit der Rueckblick aelterer Batches nichts nachbaut.
    """
    p = Path(cfg.sub("runs")) / f"b{int(batch):03d}" / "preflight-aufrufe.jsonl"
    if not p.is_file():
        return 0, 0
    laeufe = 0
    frueh = 0
    for zeile in (read_text(p) or "").splitlines():
        if not zeile.strip():
            continue
        try:
            daten = json.loads(zeile)
        except ValueError:
            continue
        if not isinstance(daten, dict):
            continue
        laeufe += 1
        if daten.get("frueh"):
            frueh += 1
    return laeufe, frueh


def rate_text(median: float | None, mittel: float | None) -> str:
    """`Median Zuwachs (Kopf-Batches): 6 | Mittel ueber alle C-Batches: 3,0` (M221-5).

    Beide Zahlen mit ihrer Grundmenge im Namen - die Definition steht in der Zeile,
    nicht in einer Fussnote (die Aussensicht liest nur die Zeile).
    """
    med = f"{median:.0f}" if median is not None else "nicht gemessen"
    alle = f"{mittel:.1f}".replace(".", ",") if mittel is not None else "nicht gemessen"
    return (f"Median Zuwachs (Kopf-Batches): {med} | "
            f"Mittel ueber alle C-Batches: {alle}")


def c_rate(cfg, n: int = STANDARD_FENSTER, reihen: list[dict] | None = None) -> dict:
    """Die Rate "Koepfe je C-Batch" - ZWEI Grundmengen, getrennt ausgewiesen (R13ba).

    Anlass (Aussensicht **M221-5**, gemessen 30.09.2026): derselbe Restvorrat (26 Koepfe)
    wurde in EINER Eingabe mit zwei Raten hochgerechnet - `MEDIAN ... 6 Koepfe je C-Batch`
    (PLAN/IST-Tafel) gegen `+3.0 je C-Batch ... -> 9 C-Batches` (Durchsatzzeile der
    BILANZ). Der Unterschied ist die **Grundmenge**:

      * **Median (Kopf-Batches)**: die Zuwaechse der C-Batches mit `SOLL-KOEPFE > 0` -
        die Batches, in denen C Koepfe bauen SOLLTE. B-Batches und Aufraeum-Batches
        zaehlen nicht mit (sie trugen den Nenner vorher auf 0 bzw. auf 3.0).
        Real: +7 (B216), +5 (B219) -> **6**.
      * **Mittel (alle C-Batches)**: jeder gemessene C-Batch-Schritt der Preflight-Reihe,
        auch die ohne Koepfe. Real: 0, 0, +7, +5 -> **3.0**.

    **Gerechnet wird mit dem Median**; das Mittel steht daneben, damit die Zahl
    nachpruefbar bleibt. Faellt der Median aus (kein Kopf-Batch im Fenster), tritt das
    Mittel an seine Stelle - `quelle` sagt, welche der beiden Zahlen gerechnet wurde.

    **R13bn (Aussensicht M242-3).** Beide Zahlen kommen jetzt aus DERSELBEN lueckenlosen
    Quelle: der **Preflight-Reihe** (`c_trend`, Zeile `C Koepfe` je
    `analysis/_preflight_<N>.txt`). Vorher nahm der Median die Zuwaechse aus der
    PLAN/IST-Reihe - die haengt an den **kanonischen Bilanzdateien**
    (`analysis/_m<N>/_bilanz<N>.txt`), und die fehlen fuer einzelne Batches (gemessen:
    B241, `git show --stat c9660c3`). Der Median liess diesen Batch damit still weg und
    stand zu hoch (B237-B243: +3 statt +2 mit den Zuwaechsen +4, +2, +2). Das Mittel kam
    schon immer aus der Preflight-Reihe - jetzt also beide.

    `n` und `reihen` bleiben in der Signatur (Aufrufer `plan_ist_text`), bestimmen die
    Grundmenge aber NICHT mehr: die ist das Trendfenster `TREND_FENSTER` (so wie beim
    Mittel), damit Median und Mittel dieselben Schritte zaehlen.
    """
    trend = c_trend(cfg, TREND_FENSTER)
    schritte = list(trend.get("c_schritte") or [])
    kopf = [(int(s["bis"]), int(s["delta"])) for s in schritte
            if s.get("delta") is not None
            and (soll_koepfe(auftrags_text(cfg, int(s["bis"]))[0]) or 0) > 0]
    kopf.sort(key=lambda p: -p[0])                 # neueste zuerst (wie bisher)
    med = median([d for _b, d in kopf])
    mittel = ((sum(s["delta"] for s in schritte) / len(schritte)) if schritte else None)
    med_quelle = ("Median der Zuwaechse der Kopf-Batches ("
                  + ", ".join(f"{d:+d} (B{b})" for b, d in kopf) + ")"
                  if kopf else "Median: kein C-Batch mit SOLL-KOEPFE > 0 im Fenster")
    mittel_quelle = ("Mittel ueber alle C-Batches der Preflight-Reihe B"
                      f"{trend['erst']['batch']}..B{trend['letzt']['batch']} ("
                      + ", ".join(f"{s['delta']:+d}" for s in schritte) + ")"
                      if (schritte and trend.get("erst") and trend.get("letzt")) else
                      "Mittel ueber alle C-Batches: nicht gemessen ("
                      + str(trend.get("grund") or "keine Preflight-Reihe") + ")")
    return {"median": med, "mittel": mittel, "rate": med if med is not None else mittel,
            "kopf_batches": kopf, "c_schritte": schritte,
            "quelle": (med_quelle if med is not None else
                       (mittel_quelle if mittel is not None else "keine Rate messbar")),
            "text": rate_text(med, mittel)}


def durchsatz(cfg, n: int = STANDARD_FENSTER) -> dict:
    """Verifizierte Koepfe und Insn je Batch plus Hochrechnung (R13s).

    "Verifiziert" ist die Zeile **`R207 rueckwerts`** der kanonischen Bilanzdatei
    (`analysis/_m<N>/_bilanz*.txt`, maschinengeschrieben): sie fuehrt die GEBAUTEN
    Koepfe mit Vorbatch- und Heute-Spalte. Die Differenz ist das, was dieser Batch
    verifiziert hat. **Insn** stehen dort nicht - sie kommen deshalb nur aus der
    Paket-E-Zeile der Batch-Dokumente, wo es sie gibt. "offen" ist der offene
    Paket-E-Vorrat (der Arbeitsvorrat, den C gerade abarbeitet).
    """
    reihe = bilanz_je_batch(cfg, max(3, n + 2))
    _r207_aus_dokumenten(cfg, reihe)
    je_batch = {e["batch"]: e for e in kernzahlen(cfg, MAX_DOKUMENTE)}
    fenster: list[dict] = []
    for eintrag in reversed(reihe):                    # neueste zuerst
        e = dict(eintrag)
        d = je_batch.get(e["batch"]) or {}
        if d.get("paket_e_insn") is not None and d.get("paket_e_insn_vorher") is not None:
            e["insn"] = d["paket_e_insn_vorher"] - d["paket_e_insn"]
        else:
            e["insn"] = None
        e["c_koepfe"] = d.get("c_koepfe")
        e["c_faelle"] = d.get("c_faelle")
        e["c_abweichungen"] = d.get("c_abweichungen")
        e["c_quelle"] = d.get("c_quelle")
        e["c_zeile"] = d.get("c_zeile")
        e["paket_e_zeile"] = d.get("paket_e_zeile")
        fenster.append(e)
        if len(fenster) >= n:
            break
    pe: dict = {}
    for eintrag in reversed(kernzahlen(cfg, MAX_DOKUMENTE)):
        if eintrag.get("paket_e_koepfe") is not None:
            pe = eintrag
            break
    # R13aw (M219-3): der OFFENE Vorrat kommt aus der Messung, nicht aus der
    # Soll/Ist-Tafel (die stand seit B208 still). Fehlt jede Messung, wird NICHTS
    # geschaetzt - die Anzeige sagt dann "nicht gemessen seit B<k>".
    messung = paket_e_messung(cfg)
    erg: dict = {"fenster": fenster, "n": len(fenster), "paket_e": pe,
                 "paket_e_messung": messung,
                 "mittel_koepfe": 0.0, "mittel_insn": 0.0, "c_quelle": "",
                 "batches_koepfe": None, "batches_insn": None, "quelle": ""}
    if fenster:
        erg["letzter"] = fenster[0]
        erg["mittel_koepfe"] = sum(e["koepfe"] for e in fenster) / len(fenster)
        insn_werte = [e["insn"] for e in fenster if e.get("insn")]
        erg["mittel_insn"] = sum(insn_werte) / len(insn_werte) if insn_werte else 0.0
        erg["quelle"] = fenster[0].get("dokument", "")
        erg["c_quelle"] = fenster[0].get("c_quelle") or ""
    offen_koepfe = (messung.get("koepfe") if messung else None)
    offen_insn = (messung.get("insn") if messung else None)
    erg["offen_koepfe"] = offen_koepfe
    erg["offen_insn"] = offen_insn
    if offen_koepfe and erg["mittel_koepfe"] > 0:
        erg["batches_koepfe"] = offen_koepfe / erg["mittel_koepfe"]
    if offen_insn and erg["mittel_insn"] > 0:
        erg["batches_insn"] = offen_insn / erg["mittel_insn"]
    # R13aa (Punkt 3, M209-3): der Durchsatz wird GETRENNT ausgewiesen - je C-Batch,
    # mit dem Mischverhaeltnis, daraus Kalender-Batches. Das "Mittel der letzten 5"
    # mischte B- und C-Batches und ergab eine Zahl, die den C-Stillstand (B207-B210:
    # kein neuer Kopf) nicht enthielt.
    c_fenster = [e for e in fenster
                 if strang_von_batch(cfg, int(e["batch"])).get("strang") != "B"]
    plan = plan_mischung(cfg)
    erg["c_fenster"] = c_fenster
    erg["mittel_c_koepfe_r207"] = (sum(e["koepfe"] for e in c_fenster) / len(c_fenster)
                                    if c_fenster else 0.0)
    # R13ac (M210-2): die C-Koepfe kommen aus der PREFLIGHT-Reihe - nicht aus dem
    # R207-Zaehler (das war der Befund: "verifiziert: +0 (78 -> 78)", waehrend die
    # Preflight-Datei B198 17 -> B210 78 zeigt). Ohne lueckenlose Quelle wird fuer die
    # C-Zeile NICHTS gerechnet; der R207-Wert bleibt als eigener, benannter Zaehler.
    trend = c_trend(cfg, TREND_FENSTER)
    erg["c_trend"] = trend
    # R13bn (M243-3): derselbe Trend fuer die VOLL verifizierten Koepfe (Bahnabdeckung).
    # Er gehoert hierher, nicht in `durchsatz_zeilen` - die Kalender-Hochrechnung
    # (`kalender_zeilen`) und die BILANZ lesen dieselbe Zahl.
    ver = verifiziert_trend(cfg, TREND_FENSTER)
    erg["c_verifiziert"] = ver
    erg["rate_c_verifiziert"] = (ver.get("median_je_c_batch")
                                  if ver.get("median_je_c_batch") is not None
                                  else ver.get("mittel_je_c_batch"))
    erg["rate_c_verifiziert_quelle"] = (
        "Median der verifizierten Zuwaechse je C-Batch ("
        + ", ".join(f"{s['delta']:+d} (B{s['bis']})" for s in ver["c_schritte"]) + ")"
        if ver.get("gemessen") and ver.get("c_schritte") else "")
    if trend["gemessen"] and trend.get("mittel_je_c_batch") is not None:
        erg["mittel_c_koepfe"] = trend["mittel_je_c_batch"]
        erg["mittel_c_quelle"] = ("Preflight-Messung: C Koepfe je C-Batch "
                                   f"B{trend['erst']['batch']}..B{trend['letzt']['batch']}")
    else:
        erg["mittel_c_koepfe"] = 0.0
        erg["mittel_c_quelle"] = ("nicht gemessen (" +
                                   (trend.get("grund") or "keine Preflight-Reihe") + ")")
    erg["anteil_gemessen"] = (len(c_fenster) / len(fenster)) if fenster else None
    # R13bn (M242-3): der TATSAECHLICHE C-Anteil. Gemessen wird an der lueckenlosen
    # Preflight-Reihe und nur an Batches mit BELEGTEM Strang (B/C); unbekannte zaehlen
    # nicht mit (vorher zaehlten sie als C und blaehten den Anteil auf).
    arten = [(int(e["batch"]), (strang_von_batch(cfg, int(e["batch"])).get("strang") or "?"))
             for e in (trend.get("reihe") or [])]
    bekannt = [a for _b, a in arten if a in ("B", "C")]
    erg["anteil_gemessen"] = (sum(1 for a in bekannt if a == "C") / len(bekannt)
                              if bekannt else None)
    erg["anteil_gemessen_basis"] = (f"{len(bekannt)} Batches mit belegtem Strang"
                                     + (f", {len(arten) - len(bekannt)} ohne Beleg"
                                        if len(arten) > len(bekannt) else ""))
    # Der LAUFENDE ABSCHNITT am Ende der Reihe: endet sie mit mehreren C-Batches, ruht
    # Strang B - dann ist der Anteil fuer die Hochrechnung 100 %, nicht der Mittelwert
    # ueber eine Zeit, in der B noch mitlief (gemessen 02.10.2026: B241, B242, B243 sind
    # C, davor B238/B240).
    lauf_c, lauf_von = 0, 0
    for b, a in reversed(arten):
        if a != "C":
            break
        lauf_c += 1
        lauf_von = b
    erg["c_lauf"] = lauf_c
    erg["c_lauf_von"] = lauf_von
    erg["anteil_c"] = plan.get("anteil")
    # R13bb (M224-5): die Zeile nennt Quelle (Datei:Zeile) UND Stand der Regel (z. B.
    # "ab B222, Nutzerentscheidung R221-1, 2026-09-30") - vorher stand nur der Wortlaut da,
    # und der kam aus der ueberholten 2:1-Zeile.
    if plan.get("anteil"):
        ort = f"{plan['datei']}:{plan['zeile_nr']}" if plan.get("zeile_nr") else plan["datei"]
        plan_quelle = (f"Regel {ort} \"{plan.get('regel') or ''}\""
                       + (f" ({plan['stand']})" if plan.get("stand") else ""))
        erg["anteil_quelle"] = plan_quelle
    else:
        plan_quelle = ""
        erg["anteil_quelle"] = ""
    if lauf_c >= C_LAUF_MINDESTENS:
        # R13bn: der gemessene Abschnitt schlaegt die Plan-Regel - die Regel beschreibt
        # den geplanten Wechsel, der Abschnitt zeigt, dass Strang B ruht.
        erg["anteil_c"] = 1.0
        regel_kurz = (f"; Plan-Regel nennt {plan['anteil'] * 100:.0f} % "
                      f"({plan.get('datei')}:{plan.get('zeile_nr') or '-'})"
                      if plan.get("anteil") else "")
        erg["anteil_quelle"] = (
            f"gemessen: die letzten {lauf_c} Batches sind C "
            f"(B{lauf_von}..B{arten[-1][0]}; Strang B ruht)" + regel_kurz)
    elif not erg["anteil_c"]:
        if erg["anteil_gemessen"] is not None:
            erg["anteil_c"] = erg["anteil_gemessen"]
            erg["anteil_quelle"] = ("gemessen an der Preflight-Reihe "
                                     f"({erg['anteil_gemessen_basis']}): "
                                     f"{erg['anteil_gemessen'] * 100:.0f} % C-Batches "
                                     "(kein Mischverhaeltnis in hybrid-plan.md)")
        else:
            erg["anteil_quelle"] = ""
    return erg


def kalender_zeilen(cfg, offen: float, d: dict, einheit: str = "Koepfe",
                    einzug: str = "                   ") -> list[str]:
    """`-> x C-Batches -> ca. y KALENDER-Batches` - die getrennte Hochrechnung (R13aa).

    Drei Schritte, jeder einzeln lesbar:
      * Durchsatz **je C-Batch** (nicht je Kalender-Batch - B-Batches bauen keine Koepfe),
      * **Anteil** der C-Batches (Mischverhaeltnis aus `hybrid-plan.md`, sonst gemessen),
      * daraus die **Kalender-Batches** (C-Batches ÷ Anteil).
    Fehlt eine Zahl, wird nichts gerechnet (keine Schaetzung ohne Grundlage).

    **Gerechnet wird mit `d['rate_c_koepfe']`** - dem MEDIAN der Kopf-Batches (R13ba,
    M221-5). Vorher stand hier das Mittel ueber ALLE C-Batches (3.0 gegen 6), und dieselbe
    Eingabe nannte fuer denselben Vorrat zwei verschiedene Zahlen.
    """
    mittel_c = float(d.get("rate_c_koepfe") or d.get("mittel_c_koepfe") or 0)
    quelle = d.get("rate_c_quelle") or d.get("mittel_c_quelle") or ""
    if not offen or mittel_c <= 0:
        return []
    c_need = float(offen) / mittel_c
    reihe = ", ".join(f"B{e['batch']}" for e in (d.get("c_fenster") or []))
    zeilen = [f"{einzug}-> {c_need:.0f} C-Batches bei +{mittel_c:.1f} {einheit} je C-Batch"
              + (f" (Grundlage: {quelle})" if quelle else "")]
    anteil = d.get("anteil_c")
    if anteil:
        zeilen.append(f"{einzug}-> ca. {c_need / anteil:.0f} KALENDER-Batches "
                      f"({c_need:.0f} C-Batches / Anteil {anteil * 100:.0f} % = "
                      f"{d.get('anteil_quelle') or 'gemessen'})")
    else:
        zeilen.append(f"{einzug}-> Kalender-Batches: nicht rechenbar (kein Anteil der "
                      f"C-Batches belegbar)")
    # R13bn (M243-3): die zweite Rechnung auf die VOLL verifizierten Koepfe. Der
    # Kopfzaehler zaehlt Koepfe mit offenem Rumpf mit (800660D4) - diese Zeile zeigt,
    # wie sich dieselbe Restmenge rechnet, wenn nur Verifiziertes zaehlt.
    ver = float(d.get("rate_c_verifiziert") or 0)
    if ver > 0:
        zeilen.append(f"{einzug}-> mit dem VERIFIZIERTEN Zuwachs (+{ver:.1f} {einheit} je "
                      f"C-Batch; {d.get('rate_c_verifiziert_quelle') or 'Bahnabdeckung'}): "
                      f"ca. {float(offen) / ver:.0f} C-Batches (HYPOTHESIS - zaehlt nur "
                      f"voll verifizierte Koepfe)")
    return zeilen


def dokumente(cfg, anzahl: int = MAX_DOKUMENTE) -> list[tuple[int, Path]]:
    """Die neuesten Batch-Dokumente als `[(batch, pfad)]`, aufsteigend nach Nummer."""
    try:
        adir = Path(cfg.decomp) / "analysis"
        gefunden: list[tuple[int, Path]] = []
        for p in adir.glob("port-batch*.md"):
            m = _DOKU.search(p.name)
            if m:
                gefunden.append((int(m.group(1)), p))
    except OSError:
        return []
    gefunden.sort()
    return gefunden[-max(1, anzahl):]


def tabellen_zellen(zeile: str) -> list[str]:
    """Die Zellen einer Markdown-Tabellenzeile (ohne die Randstriche)."""
    return [z.strip() for z in zeile.strip().strip("|").split("|")]


def zellen_etikett(zelle: str) -> str:
    """Der Zelleninhalt als Etikett: Markup weg, klein ("`**C Koepfe**`" -> "c koepfe")."""
    return re.sub(r"[`*_\s]+", " ", zelle or "").strip().lower()


def ist_zellen(text: str, etikett: str) -> list[tuple[int, list[str]]]:
    """Alle Tabellenzeilen mit diesem Etikett in der ERSTEN Zelle: [(Zeilennr., Zellen)]."""
    out: list[tuple[int, list[str]]] = []
    for i, zeile in enumerate((text or "").splitlines(), 1):
        if not zeile.lstrip().startswith("|"):
            continue
        zellen = tabellen_zellen(zeile)
        if zellen and zellen_etikett(zellen[0]) == etikett:
            out.append((i, zellen))
    return out


# R13bf (Aussensicht B234, Befund M234-1): eine Spalte, die **Soll** heisst, ist eine
# Vorhersage und nie ein Messwert. Anlass: die Soll/Ist-Tafel von B234 hat die Spalten
# `Ist (B233) | Soll (B234)`; `ist_wert` nahm die LETZTE numerische Zelle und damit die
# Soll-Spalte - die Bilanz fuehrte so `115` als gemessenen Stand, obwohl kein Preflight
# gelaufen war.
_RE_SOLL_SPALTE = re.compile(r"\bsoll\b", re.IGNORECASE)


def tabellen_kopf(text: str, datenzeile: int) -> list[str]:
    """Die Kopfzeile der Tabelle ueber `datenzeile` (1-basiert) - sonst `[]`.

    Gesucht wird rueckwaerts: die Trennerzeile (`|---|---|`) und darueber die Kopfzeile.
    Gibt es keine (einfache Beispieltabelle ohne Kopf), ist das Ergebnis leer - dann
    wird wie vorher die letzte numerische Zelle genommen.
    """
    zeilen = (text or "").splitlines()
    j = int(datenzeile) - 2                      # Zeile ueber der Datenzeile
    if j < 0:
        return []
    while j >= 0:
        if not zeilen[j].lstrip().startswith("|"):
            j -= 1
            continue
        zellen = tabellen_zellen(zeilen[j])
        if zellen and all(re.fullmatch(r":?-{2,}:?", z.replace(" ", ""))
                          for z in zellen if z != ""):
            j -= 1                               # Trennerzeile -> eine Zeile hoeher
            continue
        return zellen
    return []


def ist_wert(text: str, etikett: str,
             muster: re.Pattern) -> tuple[int, tuple | None]:
    """(Zeilennr., Wert) der **letzten** Zeile mit diesem Etikett.

    Genommen wird die letzte solche Zeile (die Soll/Ist-Tafel steht hinter der
    Vorhersagetafel) und in ihr die letzte Zelle, die MIT dem Zahlenmuster BEGINNT -
    die Spalte "Abweichung/Quelle" am Zeilenende beginnt mit Text und zaehlt nicht.
    **R13bf:** Zellen unter einer Spaltenueberschrift mit dem Wort `Soll` zaehlen NIE
    (Vorhersage, kein Messwert - M234-1); die Ueberschrift kommt aus der Kopfzeile der
    Tabelle (`tabellen_kopf`).
    `(0, None)`, wenn es keine solche Zeile oder keinen solchen Wert gibt.
    """
    zeilen = ist_zellen(text, etikett)
    if not zeilen:
        return 0, None
    nummer, zellen = zeilen[-1]
    kopf = tabellen_kopf(text, nummer)
    for i in range(len(zellen) - 1, 0, -1):
        if i < len(kopf) and _RE_SOLL_SPALTE.search(zellen_etikett(kopf[i])):
            continue
        roh = (zellen[i] or "").replace("*", "").replace("`", "").strip()
        m = muster.match(roh)
        if m:
            return nummer, tuple(int(g) for g in m.groups())
    return nummer, None


def _zahlen_aus_text(text: str) -> dict:
    """Die Bilanzzahlen EINES Dokuments (fehlende Schluessel bleiben weg).

    Die C-Koepfe- und die Paket-E-Zeile kommen aus der **Soll/Ist-Tafel** (`ist_wert`),
    nicht aus der Vorhersagetafel - Begruendung oben bei den Mustern (R13x).
    """
    out: dict = {}
    m = _RE_INV.search(text)
    if m:
        out["inventar"] = (int(m.group(1)), int(m.group(2)))
    m = _RE_BAU.search(text)
    if m:
        out["baut"] = (int(m.group(1)), int(m.group(2)))
    m = _RE_OFFEN.search(text)
    if m:
        out["offen"] = (int(m.group(1)), int(m.group(2)))
    m = _RE_BLATT.search(text)
    if m:
        out["blatt"] = (int(m.group(1)), int(m.group(2)))
    zeile, wert = ist_wert(text, _ETIKETT_CKOPF, _RE_ZAHL_CKOPF)
    if wert:
        out["c_koepfe"], out["c_faelle"], out["c_abweichungen"] = wert
        out["c_zeile"] = zeile
    zeile, wert = ist_wert(text, _ETIKETT_PAKET_E, _RE_ZAHL_PAKET_E)
    if wert:
        (out["paket_e_koepfe"], out["paket_e_insn"],
         out["paket_e_blatt"], out["paket_e_insn_blatt"]) = wert
        out["paket_e_zeile"] = zeile
    return out


def c_zahlen(cfg, anzahl: int = MAX_DOKUMENTE) -> list[dict]:
    """Je Batch-Dokument die Bilanzzahlen (aufsteigend nach Batch-Nummer)."""
    reihe: list[dict] = []
    for batch, pfad in dokumente(cfg, anzahl):
        try:
            text = read_text(pfad)[:400000]
        except OSError:
            continue
        eintrag = {"batch": batch, "dokument": pfad.name}
        eintrag.update(_zahlen_aus_text(text))
        reihe.append(eintrag)
    return reihe


# ------------------------------------------------- Preflight-Zeilen (R13x, M208-3a)
def preflight_dateien(cfg, anzahl: int = 4) -> list[tuple[int, Path]]:
    """Die gueltigen Preflight-Dateien `analysis/_preflight_<N>.txt`, neueste zuletzt.

    Diese Dateien schreibt das Decomp-Werkzeug `scripts/preflight.py` am Batch-Ende -
    je Batch genau ein gueltiger Lauf (Fehllaeufe liegen als
    `analysis/_m<N>/_preflight_<N>_fehllauf<k>.txt` und werden hier NICHT gelesen).
    Sie sind damit die maschinengeschriebene Messung des Batch-Endes und die einzige
    Quelle der Zeile `C Koepfe`, die nicht aus Worker-Prosa stammt.
    """
    try:
        adir = Path(cfg.decomp) / "analysis"
        gefunden: list[tuple[int, Path]] = []
        for p in adir.glob("_preflight_*.txt"):
            m = _RE_PREFLIGHT_NAME.search(p.name)
            if m:
                gefunden.append((int(m.group(1)), p))
    except OSError:
        return []
    gefunden.sort()
    return gefunden[-max(1, anzahl):]


# Die EINE Lesestelle fuer `analysis/_preflight_<N>.txt` (R13ap).
# Anlass (gemessen 2026-09-30): `_preflight_216.txt` ist **UTF-16 LE mit BOM** (FF FE),
# B211-B215 sind UTF-8-BOM. `read_text` liest UTF-8 - jede Zeile kam mit NUL-Bytes an,
# kein Pflichtmuster passte, und der Review von B216 trug drei
# `PARSER: Zeile ... nicht erkannt`, obwohl die Datei die Zeilen hat (genau dafuer wurde
# die R13ae-Warnung gebaut; Beleg `docs/_r13ap_belege.md`). Aeltere Faelle: B155-B158.
PREFLIGHT_GRENZE = 200000


def preflight_text(pfad) -> tuple[str, str]:
    """Inhalt **und Kodierung** einer Preflight-Datei -> `(text, kodierung)` (R13ap).

    Kodierungserkennung in `util.read_text_erkannt`: BOM (UTF-8, UTF-16 LE/BE) schlaegt
    alles, sonst UTF-8, und NUL-Bytes ohne BOM werden als UTF-16 LE gelesen. Fehlende
    Datei: `("", "")` - wie vorher meldet der Aufrufer dann `nicht erkannt`; echte
    Lesefehler (`OSError`) werden durchgereicht und dort als `nicht lesbar` gemeldet.
    """
    text, kodierung = read_text_erkannt(Path(pfad))
    return text[:PREFLIGHT_GRENZE], kodierung


def preflight_kodierung_hinweis(cfg, anzahl: int = 1, log=None) -> list[str]:
    """Vermerkt eine als UTF-16 gelesene Preflight-Datei (R13ap) - fuer die Review-Fakten.

    Der Text kommt trotzdem an (das ist der Punkt der Kodierungserkennung) - der Reviewer
    soll aber wissen, dass dieser Batch seine Datei in einer anderen Kodierung geschrieben
    hat als alle anderen: das ist ein Werkzeugfehler im Decomp-Repo, kein Messwert.
    Rueckgabe: Liste mit hoechstens einer Zeile je gepruefter Datei.
    """
    out: list[str] = []
    for batch, pfad in preflight_dateien(cfg, max(1, int(anzahl))):
        _text, kodierung = preflight_text(pfad)
        if ist_utf16(kodierung):
            out.append(f"Preflight B{batch} in UTF-16, gelesen "
                       f"({pfad.name}, {kodierung})")
            if log is not None:
                log.warn("Preflight-Datei ist UTF-16", batch=batch, datei=pfad.name,
                         kodierung=kodierung)
    return out


# ------------------------------------------------- Zeilen der Bahnabdeckung (R13ac)
# Maschinengeschriebene Zeilen der Preflight-Datei (Beispiel B210):
#   "Bahnabdeckung      55/78 | Bloecke 326/434 | verifiziert 55 | teilgeprueft 23 OK"
# Ab B211 kommt laut Reviewer-Regel eine **Nachrueckliste 1** dazu (Format noch nicht
# gesehen - deshalb wird die Zeile tolerant gesucht: Label `Nachrueckliste`, darin
# `verifiziert <n>`). Ist sie da, hat SIE den Vorrang (Befund M210-3).
# Beide Muster sind seit R13ae gleich tolerant wie `_RE_PREFLIGHT_CKOPF` (Prosa zwischen
# Etikett und Zahlen, Zusatz dahinter). Die Nachrueckliste steht **nicht** in der Liste
# der Pflichtzeilen (`PREFLIGHT_ERWARTET`): sie ist optional, sonst warnte der Harness
# in jedem Batch.
_RE_BAHN_ZEILE = _preflight_zeile("Bahnabdeckung", r"(\d+)\s*/\s*(\d+)\b(?P<rest>.*)$")
_RE_NACHRUECK_ZEILE = _preflight_zeile("Nachrueckliste", r"(\d+)?\s*(?P<rest>.*)$")
_RE_WORT_VERIFIZIERT = re.compile(r"verifiziert\s+(\d+)")
_RE_WORT_TEILGEPRUEFT = re.compile(r"teilgeprueft\s+(\d+)")
_RE_ZAHL_BLOECKE = re.compile(r"Bloecke\s+(\d+)\s*/\s*(\d+)")
# Das Zahlenpaar der Zeile selbst: "55/78" (Bahnabdeckung) bzw. "62/80" (Nachrueckliste).
_RE_ZAHL_PAAR = re.compile(r"(\d+)\s*/\s*(\d+)")
# Zeile "Hybrid-Lauf        215 | 800138F0 | MMIO | 28/407 | 0              OK".
# Seit R13ah wird sie GELESEN: Feld 2 ist der Halt-PC, Feld 4 das Wegmass (Zaehler/Gesamt).
# Der Stillstands-Ausloeser der Aussensicht vergleicht genau diese zwei Felder - das Feld
# `B-SCHRITT:` des Reviews mass nichts (Aussensicht B214, Befund 4).
_RE_HYBRID_FELDER = _preflight_zeile(
    "Hybrid-Lauf",
    r"(?P<nr>\S+)\s*\|\s*(?P<halt>[0-9A-Fa-fx]+)\s*\|\s*(?P<art>[^|\n]*?)\s*\|\s*"
    r"(?P<weg>\d+)\s*/\s*(?P<weg_ges>\d+)\s*\|(?P<rest>[^\n]*)")
_RE_HYBRID_ZEILE = _preflight_zeile("Hybrid-Lauf", r".*$")


# Die Zeilen, die der Harness aus `analysis/_preflight_<N>.txt` liest (R13ae).
# `parsen` nennt die Funktion, die die Zahlen auswertet; "" heisst: nur die Anwesenheit
# wird geprueft. `muster` ist dasselbe, mit dem geparst wird - so kann eine Zeile nicht
# "erkannt" heissen und trotzdem leer bleiben.
PREFLIGHT_ERWARTET: tuple[dict, ...] = (
    {"name": "C Koepfe", "muster": _RE_PREFLIGHT_CKOPF, "parsen": "preflight_c_koepfe"},
    {"name": "Bahnabdeckung", "muster": _RE_BAHN_ZEILE,
     "parsen": "preflight_bahnabdeckung"},
    {"name": "Hybrid-Lauf", "muster": _RE_HYBRID_ZEILE, "parsen": ""},
)


def preflight_zeilen_pruefen(cfg, log=None, anzahl: int = 1) -> list[str]:
    """Meldet Pflichtzeilen, die in einer vorhandenen Preflight-Datei fehlen (R13ae).

    Rueckgabe: fertige Zeilen fuer die Review-Fakten, z. B.
    `PARSER: Zeile C Koepfe in _preflight_213.txt nicht erkannt`. Leer heisst: alle
    erwarteten Zeilen wurden mit **demselben** Muster gelesen, mit dem die Zahlen
    geholt werden. Je Fall geht zusaetzlich eine WARN-Zeile ins Log (`log`), damit der
    Ausfall nicht nur im Review-Text steht.

    Geprueft werden nur die neuesten `anzahl` Dateien: die alten Batches (B155..B197)
    fuehren noch gar keine Zeile `C Koepfe` - das waere Rauschen, kein Befund.
    """
    dateien = preflight_dateien(cfg, max(1, int(anzahl)))
    if not dateien:
        return ["PARSER: keine Preflight-Datei (analysis/_preflight_<N>.txt) gefunden"]
    warnungen: list[str] = []
    for batch, pfad in dateien:
        try:
            zeilen = preflight_text(pfad)[0].splitlines()
        except OSError as exc:
            warnungen.append(f"PARSER: {pfad.name} nicht lesbar ({exc.__class__.__name__})")
            continue
        for eintrag in PREFLIGHT_ERWARTET:
            if any(eintrag["muster"].match(z) for z in zeilen):
                continue
            warnungen.append(f"PARSER: Zeile {eintrag['name']} in {pfad.name} "
                             "nicht erkannt")
            if log is not None:
                log.warn("Preflight-Zeile nicht erkannt", batch=batch, datei=pfad.name,
                         zeile=eintrag["name"],
                         parsen=eintrag["parsen"] or "(nur Anwesenheit)")
    return warnungen


def preflight_bahnabdeckung(cfg, anzahl: int = 4) -> list[dict]:
    """`verifiziert`/`teilgeprueft` je Batch aus der Bahnabdeckungszeile (R13ac, M210-3).

    Bis R13ac behauptete der Bilanz-Kopf "C verifiziert: 78 Koepfe" - das war die
    **Kopfzahl** (C Koepfe, gleich zur Referenz), waehrend dieselbe Preflight-Datei
    `verifiziert 55 | teilgeprueft 23` auswies. Zwei verschiedene Dinge mit einem Wort.

    Rueckgabe je Batch: `{batch, datei, koepfe, bloecke, bloecke_gesamt, verifiziert,
    teilgeprueft, quelle}`. `quelle` nennt die Zeile ("Nachrueckliste 1" oder
    "Bahnabdeckung"). Fehlt beides, fehlt der Eintrag - es wird nichts geschaetzt.
    """
    out: list[dict] = []
    for batch, pfad in preflight_dateien(cfg, anzahl):
        try:
            text = preflight_text(pfad)[0]
        except OSError:
            continue
        bahn: dict | None = None
        nach: dict | None = None
        for zeile in text.splitlines():
            m = _RE_BAHN_ZEILE.match(zeile)
            if m and bahn is None:
                bahn = {"koepfe": int(m.group(1)), "gesamt": int(m.group(2)),
                        "rest": m.group("rest")}
                continue
            m = _RE_NACHRUECK_ZEILE.match(zeile)
            if m and nach is None:
                nach = {"nummer": int(m.group(1) or 1), "rest": m.group("rest")}
                paar = _RE_ZAHL_PAAR.search(m.group("rest"))
                if paar:
                    nach["koepfe"] = int(paar.group(1))
                    nach["gesamt"] = int(paar.group(2))
        quelle = ""
        quelle_zeile = bahn or nach
        if nach is not None and _RE_WORT_VERIFIZIERT.search(nach["rest"]):
            quelle = f"Nachrueckliste {nach['nummer']}"
            quelle_zeile = nach
        elif bahn is not None:
            quelle = "Bahnabdeckung"
        if quelle_zeile is None:
            continue
        rest = quelle_zeile["rest"]
        v = _RE_WORT_VERIFIZIERT.search(rest)
        t = _RE_WORT_TEILGEPRUEFT.search(rest)
        b = _RE_ZAHL_BLOECKE.search(rest)
        koepfe = quelle_zeile.get("koepfe")
        gesamt = quelle_zeile.get("gesamt")
        if koepfe is None:
            koepfe = int(v.group(1)) if v else None
        out.append({
            "batch": batch, "datei": pfad.name, "quelle": quelle,
            "koepfe": koepfe,
            "gesamt": gesamt,
            "bloecke": int(b.group(1)) if b else None,
            "bloecke_gesamt": int(b.group(2)) if b else None,
            "verifiziert": int(v.group(1)) if v else None,
            "teilgeprueft": int(t.group(1)) if t else None,
        })
    return out


# ------------------------------------------------- Hybrid-Lauf + Preflight-Dauer (R13ah)
def hybrid_verlauf(cfg, anzahl: int = 8) -> list[dict]:
    """Die Zeile `Hybrid-Lauf` je Preflight-Datei (R13ah, Aussensicht B214 Befund 4).

    Rueckgabe je Batch, in dem die Zeile steht: `{batch, datei, nr, halt_pc, art, weg,
    weg_gesamt, rest}`. `halt_pc` ist Feld 2 (Halt-PC), `weg` der Zaehler aus Feld 4
    ("28/407" -> 28), `weg_gesamt` der Nenner. Fehlt die Zeile (vor B212), fehlt der
    Eintrag - es wird nichts geschaetzt.

    Anlass: der Preflight liegt **vor** dem Review vor; der Ausloeser "Stillstand" kann
    damit frueher und an einer gemessenen Zahl haengen statt am Feld `B-SCHRITT:`.
    """
    out: list[dict] = []
    for batch, pfad in preflight_dateien(cfg, max(1, int(anzahl))):
        try:
            text = preflight_text(pfad)[0]
        except OSError:
            continue
        for zeile in text.splitlines():
            m = _RE_HYBRID_FELDER.match(zeile)
            if m:
                out.append({"batch": batch, "datei": pfad.name, "nr": m.group("nr"),
                            "halt_pc": m.group("halt").upper(),
                            "art": m.group("art").strip(),
                            "weg": int(m.group("weg")),
                            "weg_gesamt": int(m.group("weg_ges")),
                            "rest": m.group("rest").strip()})
                break
    return out


# Der Preflight-Aufruf in `stats.laufzeit.langsamste` (`runs/b<N>/result.json`) - erkannt
# am Befehl, nicht am Werkzeugnamen (der ist immer "PowerShell").
_RE_PREFLIGHT_AUFRUF = re.compile(r"preflight\.py", re.IGNORECASE)


def preflight_dauer(cfg, anzahl: int = 6, log=None) -> dict | None:
    """Dauer des Preflight-Aufrufs aus dem NEUESTEN Batch, der ihn ALLEIN gemessen hat.

    Rueckgabe `{batch, minuten, dauer_s, befehl, parallel, uebersprungen}` oder `None`
    (keine Messung). Quelle ist die Liste der langsamsten Werkzeugaufrufe in
    `runs/b<N>/result.json` - nur dort steht die Dauer EINZELNER Aufrufe. Gemessen
    B213: 602 s, B214: 601,8 s.

    R13aj (2026-09-29): Ueberlappt sich der Aufruf mit einem anderen (`parallel` > 1,
    z. B. weil ein gekappter Vorgaenger im Hintergrund weiterlief), misst die Zahl die
    Wartezeit mit und ist fuer die Schwelle unbrauchbar - in B212 standen so 602,3 s und
    511,0 s fuer einen Grep mit normalen Treffern. Es zaehlt deshalb nur `parallel == 1`;
    hat der neueste Batch keinen solchen Aufruf, wird der naechstaeltere mit einem
    gueltigen Wert genommen und das im Log vermerkt (`log.warn`). Altdateien ohne das
    Feld gelten als `parallel = 1` (damals wurde nicht unterschieden).
    """
    runs = Path(cfg.root) / "runs"
    try:
        ordner = sorted(((int(p.name[1:]), p) for p in runs.glob("b*")
                         if p.is_dir() and p.name[1:].isdigit()), reverse=True)
    except OSError:
        return None
    uebersprungen: list[int] = []
    for batch, d in ordner[:max(1, int(anzahl))]:
        res = read_json(d / "result.json", {}) or {}
        lang = ((res.get("stats") or {}).get("laufzeit") or {}).get("langsamste") or []
        treffer = [e for e in lang
                   if _RE_PREFLIGHT_AUFRUF.search(str(e.get("kurz") or ""))]
        if not treffer:
            continue
        allein = [e for e in treffer if int(e.get("parallel") or 1) == 1]
        if not allein:
            # Nur parallel gemessen: NICHT als Dauer nehmen (siehe Docstring).
            uebersprungen.append(int(batch))
            if log is not None:
                log.warn(f"Preflight-Dauer aus B{int(batch)} nur parallel gemessen - "
                         f"uebersprungen (parallel="
                         f"{max(int(e.get('parallel') or 1) for e in treffer)})",
                         batch=int(batch), datei="runs/%s/result.json" % d.name)
            continue
        bester = max(allein, key=lambda e: float(e.get("dauer_s") or 0.0))
        sek = float(bester.get("dauer_s") or 0.0)
        if uebersprungen and log is not None:
            log.info(f"Preflight-Dauer aus B{int(batch)}, "
                     f"B{uebersprungen[0]} nur parallel gemessen",
                     batch=int(batch), uebersprungen=list(uebersprungen))
        return {"batch": int(batch), "dauer_s": sek, "minuten": sek / 60.0,
                "befehl": str(bester.get("kurz") or "")[:160],
                "parallel": int(bester.get("parallel") or 1),
                "uebersprungen": list(uebersprungen)}
    return None


def c_trend(cfg, n: int = 12) -> dict:
    """Die C-Koepfe-Reihe aus den Preflight-Dateien - lueckenlos gemittelt (M210-2).

    `n` ist die **Spanne in Batches** (die Zahl der Vergleichsschritte), nicht die Zahl
    der Dateien: fuer "B198 -> B210" (Spanne 12) werden **13** Preflight-Dateien gelesen.
    Genau diese Spanne nennt der Aussensicht-Prompt ("TREND DER LETZTEN 12 BATCHES").

    Anlass (Aussensicht B210): die Trendzeile des Harness stand auf dem **R207-Zaehler**
    ("verifiziert: +0 Koepfe (78 -> 78)") und im Durchsatzfenster fehlte B209 (die
    kanonischen Bilanzdateien `analysis/_m209/_bilanz*.txt` gibt es nicht). Der Befund:
    "tatsaechlich sind es +61 Koepfe seit B198, nicht +0".

    Quelle ist deshalb die maschinengeschriebene Zeile `C Koepfe` **je**
    `analysis/_preflight_<N>.txt` (dieselbe, die schon `kernzahlen` nimmt): eine Datei je
    Batch, lueckenlos von B198 bis heute. Gemittelt wird nur ueber **benachbarte**
    gemessene Batches; fehlt ein Batch im Fenster, wird er als **Luecke** benannt und
    nicht als Null gezahlt.

    Rueckgabe: `{gemessen, reihe:[{batch,koepfe,datei}], erst, letzt, delta,
    anzahl_batches, luecken:[…], schritte:[…], mittel_je_batch, mittel_je_c_batch,
    c_batches:[…], grund}`. `gemessen=False` heisst: keine Reihe -> "nicht gemessen".
    """
    spanne = max(1, int(n))
    reihe = preflight_c_koepfe(cfg, spanne + 1)
    leer = {"gemessen": False, "reihe": reihe, "erst": None, "letzt": None, "delta": None,
            "anzahl_batches": 0, "luecken": [], "schritte": [], "mittel_je_batch": None,
            "mittel_je_c_batch": None, "c_batches": [], "n_gemessen": len(reihe)}
    if len(reihe) < 2:
        leer["grund"] = (f"nur {len(reihe)} Preflight-Datei(en) mit der Zeile 'C Koepfe' "
                         "im Fenster")
        return leer
    erst, letzt = reihe[0], reihe[-1]
    haben = {e["batch"] for e in reihe}
    luecken = [b for b in range(erst["batch"] + 1, letzt["batch"]) if b not in haben]
    schritte: list[dict] = []
    for a, b in zip(reihe, reihe[1:]):
        schritte.append({"von": a["batch"], "bis": b["batch"], "delta": b["koepfe"] - a["koepfe"],
                         "benachbart": b["batch"] - a["batch"] == 1})
    c_batches = [e for e in reihe
                 if strang_von_batch(cfg, int(e["batch"])).get("strang") != "B"]
    c_nummern = {int(e["batch"]) for e in c_batches}
    spanne = letzt["batch"] - erst["batch"]
    delta = letzt["koepfe"] - erst["koepfe"]
    # Der C-Durchsatz zaehlt nur die SCHRITTE, die in einem C-Batch enden (das sind die
    # Uebergaenge, in denen C Koepfe dazugekommen sein koennen). Die Zahl der C-Batches
    # waere der falsche Nenner: der erste Batch des Fensters hat keinen Vorgaenger im
    # Fenster und wuerde den Durchsatz systematisch zu klein machen.
    c_schritte = [s for s in schritte if s["benachbart"] and s["bis"] in c_nummern]
    return {
        "gemessen": True,
        "reihe": reihe,
        "erst": erst, "letzt": letzt, "delta": delta,
        "anzahl_batches": spanne,
        "n_gemessen": len(reihe),
        "luecken": luecken,
        "schritte": schritte,
        "mittel_je_batch": (delta / spanne) if spanne else None,
        "mittel_je_c_batch": (sum(s["delta"] for s in c_schritte) / len(c_schritte)
                              if c_schritte else None),
        "c_batches": c_batches,
        "c_schritte": c_schritte,
        "grund": "",
    }


def verifiziert_trend(cfg, n: int = TREND_FENSTER) -> dict:
    """Die Reihe **`C verifiziert`** (Bahnabdeckungszeile) aus den Preflight-Dateien.

    R13bn (Aussensicht M243-3): der Kopfzaehler (`C Koepfe`, gleich zur Referenz) zaehlt
    Koepfe mit, deren Rumpf fehlt - gemessen an 800660D4: der Vergleich endet in beiden
    Welten am `bctr`, sobald die Fallruempfe erreichbar sind, scheitert er. Die Zahl der
    VOLL verifizierten Koepfe bewegt sich langsamer (B240 91 -> B243 92, waehrend der
    Kopfzaehler 122 -> 123 zeigt). Der Trend fuehrt deshalb beide Zahlen.

    Quelle ist wie bei `c_trend` eine maschinengeschriebene Zeile derselben
    Preflight-Dateien (`Bahnabdeckung … verifiziert <n> | teilgeprueft <m>` bzw.
    `Nachrueckliste`), eine Datei je Batch - lueckenlos. Rueckgabe wie `c_trend`, nur mit
    `median_je_c_batch`/`mittel_je_c_batch` aus den verifizierten Zuwaechsen.
    """
    spanne = max(1, int(n))
    reihe = [e for e in preflight_bahnabdeckung(cfg, spanne + 1)
             if e.get("verifiziert") is not None]
    leer = {"gemessen": False, "reihe": reihe, "erst": None, "letzt": None, "delta": None,
            "anzahl_batches": 0, "luecken": [], "schritte": [], "c_schritte": [],
            "median_je_c_batch": None, "mittel_je_c_batch": None, "n_gemessen": len(reihe)}
    if len(reihe) < 2:
        leer["grund"] = (f"nur {len(reihe)} Preflight-Datei(en) mit der Zeile "
                         "'Bahnabdeckung … verifiziert' im Fenster")
        return leer
    erst, letzt = reihe[0], reihe[-1]
    haben = {e["batch"] for e in reihe}
    luecken = [b for b in range(erst["batch"] + 1, letzt["batch"]) if b not in haben]
    schritte = [{"von": a["batch"], "bis": b["batch"],
                 "delta": int(b["verifiziert"]) - int(a["verifiziert"]),
                 "benachbart": b["batch"] - a["batch"] == 1}
                for a, b in zip(reihe, reihe[1:])]
    c_nummern = {int(e["batch"]) for e in reihe
                 if strang_von_batch(cfg, int(e["batch"])).get("strang") != "B"}
    c_schritte = [s for s in schritte if s["benachbart"] and s["bis"] in c_nummern]
    deltas = [s["delta"] for s in c_schritte]
    return {
        "gemessen": True,
        "reihe": reihe,
        "erst": erst, "letzt": letzt,
        "delta": int(letzt["verifiziert"]) - int(erst["verifiziert"]),
        "anzahl_batches": letzt["batch"] - erst["batch"],
        "n_gemessen": len(reihe),
        "luecken": luecken,
        "schritte": schritte,
        "c_schritte": c_schritte,
        "median_je_c_batch": median(deltas),
        "mittel_je_c_batch": (sum(deltas) / len(deltas)) if deltas else None,
        "grund": "",
    }


def preflight_c_koepfe(cfg, anzahl: int = 4) -> list[dict]:
    """Die Zeile `C Koepfe` der letzten `anzahl` Preflight-Dateien.

    Rueckgabe: `[{batch, datei, koepfe, faelle, abweichungen}]`, aufsteigend nach Batch.
    Fehlt die Zeile (vor dem C-Strang, B155..B197), fehlt der Eintrag - es wird nichts
    geschaetzt.
    """
    out: list[dict] = []
    for batch, pfad in preflight_dateien(cfg, anzahl):
        try:
            text = preflight_text(pfad)[0]
        except OSError:
            continue
        for zeile in text.splitlines():
            m = _RE_PREFLIGHT_CKOPF.match(zeile)
            if m:
                out.append({"batch": batch, "datei": pfad.name,
                            "koepfe": int(m.group(1)), "faelle": int(m.group(2)),
                            "abweichungen": int(m.group(3))})
                break
    return out


# Die Schluessel, fuer die `kernzahlen` den Vorgaengerwert mitfuehrt.
VORGAENGER_SCHLUESSEL = ("c_koepfe", "c_faelle", "c_abweichungen",
                         "paket_e_koepfe", "paket_e_insn",
                         "paket_e_blatt", "paket_e_insn_blatt")


def kernzahlen(cfg, anzahl: int = MAX_DOKUMENTE) -> list[dict]:
    """Die C-Kernzahlen JE BATCH - die eine Quelle fuer alle Anzeigen (R13x).

    Quellen, in dieser Reihenfolge:
      1. **Preflight-Zeile** (`analysis/_preflight_<N>.txt`, maschinengeschrieben) fuer
         `C Koepfe`/`C Faelle`/`C Abweichungen` - die gemessene Zahl des Batches N.
         Grund (M208-3a): die Dokumente tragen die Zahl nicht immer richtig weiter
         (B202/B203 nennen 53/1272, gemessen sind 45/1080 bzw. 59/1416).
      2. **Ist-Spalte** der Soll/Ist-Tafel des Batch-Dokuments (`ist_wert`) fuer alles,
         was die Preflight-Datei nicht fuehrt (**Paket E** hat dort keine Zeile) und fuer
         Batches ganz ohne Preflight-Datei - aber nur **vor** der Preflight-Aera.

    **R13bf (Aussensicht B234, Befund M234-1): in der Preflight-Aera gibt es keinen
    Rueckfall mehr.** Innerhalb der Aera (es gibt `_preflight_<N>.txt`-Dateien, und der
    Batch liegt nicht davor) bedeutet eine fehlende eigene Preflight-Datei: **nicht
    gemessen**. Die Zeile traegt dann keine C-Zahl (`c_nicht_gemessen: True`), und die
    Anzeige bleibt beim letzten gemessenen Stand. Anlass: B234 brach vor dem Preflight ab
    (`preflight_laeufe: 0`), die Bilanz fuehrte trotzdem „115 referenzgleich" - das war
    die **Soll-Spalte** des Batch-Dokuments (`port-batch234-…md:49`).

    `c_quelle` nennt je Eintrag, woher die C-Koepfe-Zahl kommt; `*_vorher` ist der Wert
    des letzten Eintrags MIT diesem Wert (nicht zwingend der direkte Vorgaenger - bei
    Paket E z. B. B206 -> B208, weil B207 die Zeile nicht fuehrt), `vorher_batch` dessen
    Nummer. Nichts wird fortgeschrieben oder geschaetzt; was fehlt, fehlt.
    """
    fenster = max(2, int(anzahl))
    dok = {e["batch"]: e for e in c_zahlen(cfg, fenster)}
    pre = {e["batch"]: e for e in preflight_c_koepfe(cfg, fenster + 2)}
    # Die Aera beginnt beim aeltesten PREFLIGHT-Batch im Fenster (nicht beim aeltesten
    # Batch, der die Zeile `C Koepfe` fuehrt - vor B198 gibt es die Dateien nicht).
    vorhanden = {b for b, _p in preflight_dateien(cfg, fenster + 2)}
    aera_ab = min(vorhanden) if vorhanden else None
    reihe: list[dict] = []
    gesehen: dict[str, tuple[int, int]] = {}
    for batch in sorted(set(dok) | set(pre))[-fenster:]:
        e = dict(dok.get(batch) or {})
        e["batch"] = batch
        p = pre.get(batch)
        if p:
            e["c_koepfe"] = p["koepfe"]
            e["c_faelle"] = p["faelle"]
            e["c_abweichungen"] = p["abweichungen"]
            e["c_quelle"] = p["datei"]
        elif aera_ab is not None and batch >= aera_ab:
            for schluessel in ("c_koepfe", "c_faelle", "c_abweichungen", "c_zeile"):
                e.pop(schluessel, None)
            e["c_nicht_gemessen"] = True
            e["c_erwartet"] = f"_preflight_{int(batch)}.txt"
        elif e.get("c_koepfe") is not None:
            e["c_quelle"] = e.get("dokument") or ""
        vorher: dict[str, int] = {}
        for schluessel in VORGAENGER_SCHLUESSEL:
            if schluessel not in e:
                continue
            alt = gesehen.get(schluessel)
            if alt is not None:
                vorher[schluessel] = alt[1]
                e[schluessel + "_vorher"] = alt[1]
                if alt[0] != batch - 1:
                    e.setdefault("vorher_batch", {})[schluessel] = alt[0]
            gesehen[schluessel] = (batch, int(e[schluessel]))
        reihe.append(e)
    return reihe


def stand_zahlen(cfg) -> dict:
    """Die neuesten Zahlen (neuestes Dokument, fehlende Schluessel aus dem Ankerkopf)."""
    reihe = kernzahlen(cfg, 4)
    zahlen = dict(reihe[-1]) if reihe else {}
    kopf = anchor_bloecke(cfg)
    for name in ("Stand", "Fertig"):
        for schluessel, wert in _zahlen_aus_text(kopf.get(name, "")).items():
            zahlen.setdefault(schluessel, wert)
    if zahlen and "batch" not in zahlen:
        zahlen["batch"] = _batch_aus_anker(kopf)
    return zahlen


def _batch_aus_anker(kopf: dict) -> int:
    m = re.search(r"BATCH\s+(\d+)", kopf.get("Stand", ""))
    return int(m.group(1)) if m else 0


def c_offen_gesamt(cfg, anzahl: int = MAX_DOKUMENTE) -> dict:
    """Der **C-Gesamtvorrat** ("OFFEN: X Koepfe / Y Insn") aus dem neuesten Dokument.

    Steht nur in Planungsdokumenten (B196 §6.1: "OFFEN: 1481 Koepfe / 94913 Insn",
    Quelle `analysis/_m196/_plan_c.txt`); die laufenden Batch-Dokumente fuehren ihn
    nicht mit. Deshalb wird das Dokument mitgeliefert - die Anzeige muss den Stand
    ("abgeleitet, Stand B196") nennen duerfen.
    """
    for batch, pfad in reversed(dokumente(cfg, anzahl)):
        try:
            text = read_text(pfad)[:400000]
        except OSError:
            continue
        zahlen = _zahlen_aus_text(text)
        if "offen" in zahlen:
            koepfe, insn = zahlen["offen"]
            baut = zahlen.get("baut")
            return {"batch": batch, "dokument": pfad.name,
                    "koepfe": koepfe, "insn": insn,
                    "bau": baut[0] if baut else None,
                    "bau_insn": baut[1] if baut else None}
    return {}


# ------------------------------------------------- Port-Relevanz (R13t, Punkt 2)
_PORT_RELEVANZ = ("docs", "_port_relevanz.json")


def port_relevanz(cfg) -> dict | None:
    """Ausgefuehrt vs. gebaut vs. verifiziert - der Cache aus `tools/r13t_cov_relevanz.py`.

    Die Messung selbst (4 MiB Coverage + 2072 Funktionen + Rumpf-Fenster bis zum ersten
    `blr`) dauert Sekunden; `/bilanz` liest deshalb nur die abgelegte Zahl. Fehlt die
    Datei, sagt die Anzeige "nicht gemessen" - sie raet nicht.
    """
    p = Path(cfg.harness_home).joinpath(*_PORT_RELEVANZ)
    try:
        d = read_json(p)
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) and d.get("ausgefuehrt") else None


# ------------------------------------------- /ds-Nachrichten im Review (R13t)
QUEUE_KOPF = "NACHRICHTEN AUS DER QUEUE"


def ds_nachrichten(cfg, batch: int) -> str:
    """Der `/ds`-Block, den der **bewertete Batch** in seinem Auftrag hatte (R13t).

    Quelle ist `runs/b<N>/auftrag.md` - dort haengt `worker.build_prompt` den Block
    ganz am Ende an (Kopfzeile `NACHRICHTEN AUS DER QUEUE …`). Die Queue-Dateien
    selbst sind zu diesem Zeitpunkt schon archiviert (`inbox/done/`), der Auftrag
    ist die einzige verlaessliche Quelle des Wortlauts.

    Rueckgabe: der Block ab der Kopfzeile (leer, wenn der Auftrag keine Nachricht
    enthielt oder nicht lesbar ist).
    """
    if batch <= 0:
        return ""
    p = Path(cfg.root) / "runs" / f"b{batch:03d}" / "auftrag.md"
    try:
        text = read_text(p)
    except OSError:
        return ""
    i = text.find(QUEUE_KOPF)
    return text[i:].strip() if i >= 0 else ""


# ------------------------------------ Pflichtbloecke der Instruktion (R13ag)
# `NACHRUECKLISTE` und `STREICHREIHENFOLGE` sind die beiden Bloecke, aus denen die
# `UEBERTRAG:`/`VERWORFEN:`-Zeilen des Reviews entstehen (R13af). Bis R13ag musste der
# Reviewer sie sich selbst aus `runs/b<N>/auftrag.md` holen - und genau dabei verschwand
# **B213 Nachrueckliste 1** (Befund der /ask-Pruefung 2026-09-29). Jetzt stehen sie
# **wortgleich** im Review-Prompt.
#
# Erkennung: dieselbe Zeilenform wie `worker.hat_nachrueckliste` (R13ad, Bedingung (d)) -
# optionaler `#`/`*`-Praefix, Label am Zeilenanfang, Umlaut- oder UE-Schreibweise. Die
# Gleichheit wird in `tests/test_r13af_fixes.py` ueber die echten Auftraege geprueft, damit
# "der Auftrag hat eine Nachrueckliste" und "der Block steht im Review" nicht auseinander
# laufen.
_RE_AUFTRAG_BLOCK: dict[str, re.Pattern[str]] = {
    "NACHRUECKLISTE": re.compile(r"^[ \t]*(?:[#*]+[ \t]*)*NACHR(?:Ü|UE)CKLISTE\b",
                                 re.IGNORECASE | re.MULTILINE),
    "STREICHREIHENFOLGE": re.compile(r"^[ \t]*(?:[#*]+[ \t]*)*STREICHREIHENFOLGE\b",
                                     re.IGNORECASE | re.MULTILINE),
}
# Ende eines Blocks: naechste Ueberschrift, `===`-Trennzeile, der andere Pflichtblock oder
# ein anderer bekannter Blockanfang der Instruktion. Geschnitten wird **nur an harten
# Grenzen** - lieber zu viel Kontext als ein verlorener Posten.
_RE_BLOCK_ENDE = re.compile(
    r"^[ \t]*(?:#{1,6}[ \t]+\S|={2,}|NACHR(?:Ü|UE)CKLISTE\b|STREICHREIHENFOLGE\b|"
    r"FERTIG\s+WENN\b|NICHT\s+TUN\b|BATCH-ENDE\b|NACHRICHTEN\s+AUS\s+DER\s+QUEUE\b)",
    re.IGNORECASE | re.MULTILINE)


def _auftrag_abschnitt(text: str, pos: int) -> str:
    """Der Block ab der Zeile mit `pos` bis zur naechsten harten Blockgrenze (R13ag)."""
    zeilen_ende = text.find("\n", pos)
    if zeilen_ende < 0:
        return text[pos:].rstrip()
    m = _RE_BLOCK_ENDE.search(text, zeilen_ende + 1)
    return text[pos:(m.start() if m else len(text))].strip("\n").rstrip()


def pflichtbloecke(cfg, batch: int) -> str:
    """`NACHRUECKLISTE` und `STREICHREIHENFOLGE` der bewerteten Instruktion, wortgleich.

    Quelle ist `runs/b<N>/auftrag.md` - derselbe Auftrag, den der Worker bekommen hat und
    den der Reviewer fuer die `UEBERTRAG:`/`VERWORFEN:`-Zeilen braucht (R13ag).

    Rueckgabe (mehrzeilig, Reihenfolge wie im Auftrag): je Block die Zeilen von der
    Etikettzeile bis zur naechsten harten Grenze. Fehlt ein Block, steht dort ausdruecklich
    `NACHRUECKLISTE: keine im Auftrag` bzw. `STREICHREIHENFOLGE: keine im Auftrag`; ist der
    Auftrag nicht lesbar, sagt der Block genau das (kein stilles Nichts).
    """
    nr = int(batch or 0)
    if nr <= 0:
        return "(kein bewerteter Batch - Pflichtbloecke nicht ermittelbar)"
    p = Path(cfg.root) / "runs" / f"b{nr:03d}" / "auftrag.md"
    # `read_text` liefert fuer eine fehlende Datei "" (kein Fehler) - hier wird die
    # Abwesenheit ausdruecklich geprueft, sonst behauptete der Block "keine im Auftrag".
    if not p.is_file():
        return (f"(Auftrag runs/b{nr:03d}/auftrag.md nicht lesbar - Pflichtbloecke "
                "nicht ermittelbar)")
    try:
        text = read_text(p)
    except OSError:
        return (f"(Auftrag runs/b{nr:03d}/auftrag.md nicht lesbar - Pflichtbloecke "
                "nicht ermittelbar)")
    gefunden: list[tuple[int, str, str]] = []
    for name, muster in _RE_AUFTRAG_BLOCK.items():
        m = muster.search(text)
        if m:
            gefunden.append((m.start(), name, _auftrag_abschnitt(text, m.start())))
    namen = {name for _p, name, _t in gefunden}
    if not gefunden:
        # Quergeprueft mit der Fortsetzungs-Erkennung (R13ad): meldet SIE eine Liste, die
        # hier nicht als Abschnitt lesbar ist, ist das Muster auseinandergelaufen - das
        # steht dann da, statt "keine im Auftrag" zu behaupten.
        try:
            from .worker import hat_nachrueckliste            # spaet: kein Importzyklus
            erkannt = bool(hat_nachrueckliste(text))
        except Exception:                                     # noqa: BLE001
            erkannt = False
        if erkannt:
            return ("NACHRUECKLISTE: im Auftrag erkannt, aber nicht als Abschnitt lesbar "
                    "- Muster pruefen (worker.hat_nachrueckliste)\n"
                    "STREICHREIHENFOLGE: keine im Auftrag")
        return ("NACHRUECKLISTE: keine im Auftrag\n"
                "STREICHREIHENFOLGE: keine im Auftrag")
    teile = [t for _p, _n, t in sorted(gefunden)]
    teile += [f"{name}: keine im Auftrag"
              for name in _RE_AUFTRAG_BLOCK if name not in namen]
    return "\n\n".join(teile)


# ------------------------------------------------- Strang je Batch (R13aa)
# Auftrag (Aussensicht-Nachbesserung aus `runs/meta-209.md`, Punkt 1): der Ausloeser
# "Kernzahl ohne Bewegung" hat B208/B209 als C-Batches gezaehlt - beide waren B-Batches,
# die C-Zahl durfte sich also gar nicht bewegen. Ursache: `ist_b_batch` hing ALLEIN an
# der Pflichtzeile `B-SCHRITT:` des Reviewers, und die fehlt in jedem Review seit B205
# (gemessen). Klassifiziert wird jetzt aus mehreren Belegen; jede Antwort nennt ihre
# Quelle, damit die Anzeige nichts behauptet, was sie nicht belegen kann.
_RE_B_SCHRITT = re.compile(r"B-SCHRITT:\s*(\d+)\s*/\s*5", re.IGNORECASE)
_RE_B_SCHRITT_C = re.compile(r"B-SCHRITT:\s*(?:kein|keinen)\s+B-Batch"
                             r"|B-SCHRITT:[^\n]{0,60}?Strang\s+C", re.IGNORECASE)
_RE_B_MARKER = re.compile(r"Strang\s+B\b|\bB-Batch\b|\bB-Schritt\b", re.IGNORECASE)
_RE_C_MARKER = re.compile(r"Strang\s+C\b|\bC-Batch\b", re.IGNORECASE)
_RE_MISCHUNG = re.compile(r"mischverh(?:ae|ä)ltnis", re.IGNORECASE)
# R13bb (M224-5): die GELTENDE Regel steht als "AB B222 GILT 1 B : 1 C (NUTZERENTSCHEIDUNG
# R221-1, 2026-09-30, wortgetreu):" im Plan - ohne das Wort "Mischverhaeltnis". Genau diese
# Zeile muss die Prognose nehmen, sonst rechnet sie mit dem ueberholten 2:1 weiter.
_RE_MISCH_GILT = re.compile(r"\b(?:gilt|g(?:ue|ü)ltig)\b", re.IGNORECASE)
_RE_MISCH_PAAR = re.compile(r"\bB(\d{1,4})\s*[=:]?\s*([BC])\b")
_RE_MISCH_ZAHL = re.compile(r"(\d+)\s*B\s*[:\-/]\s*(\d+)\s*C\b", re.IGNORECASE)
# Zeile, die MIT dem Strang beginnt ("Strang B, Batch 2 von hoechstens 20; …") - in
# einem Auftrag beschreibt so eine Zeile den Batch, um den es in dem Auftrag geht.
_RE_STRANG_ZEILE = re.compile(r"^\s*\**\s*Strang\s+([BC])\b", re.IGNORECASE | re.MULTILINE)
# R13ac2 (Nutzerauftrag 2026-09-29): die zwei PFlichtzeilen, die die Batch-ART
# ausdruecklich nennen. Beide Formen sind gemessen:
#   "STRANG: B (B-Batch 4 von hoechstens 20; …). SOLL-KOEPFE: 0."   (runs/b212/review.md:51)
#   "SOLL-KOEPFE: 0 (Strang B, B-Batch 3 von hoechstens 20; …)"     (runs/b211/auftrag.md:97)
# Anlass: B211 trug NUR die zweite Form; keine Quelle griff, der Batch galt als C-Batch
# und loeste eine Aussensicht aus (runs/meta-211.md).
_RE_STRANG_PFLICHT = re.compile(r"^\s*\**\s*STRANG\s*:\s*([BC])\b", re.IGNORECASE | re.MULTILINE)
_RE_SOLL_STRANG = re.compile(r"SOLL-KOEPFE[^\n]{0,80}?\bStrang\s+([BC])\b", re.IGNORECASE)

STRANG_QUELLEN = ("Pflichtzeile STRANG/SOLL-KOEPFE im Auftrag",
                  "Pflichtzeile B-SCHRITT im Review", "Auftrag runs/b<N>/auftrag.md",
                  "analysis/hybrid-plan.md")


def _pflicht_strang(text: str) -> str:
    """`B`/`C` aus den Pflichtzeilen `STRANG:` bzw. `SOLL-KOEPFE: … (Strang B, …)`.

    Nur diese zwei Zeilenformen werden gelesen - sie beschreiben den Batch, fuer den die
    Instruktion geschrieben ist. Ein blosses "Strang B" im Fliesstext bleibt absichtlich
    unberuecksichtigt (dort stehen oft FREMDE Batches).
    """
    for muster in (_RE_STRANG_PFLICHT, _RE_SOLL_STRANG):
        m = muster.search(text or "")
        if m:
            return m.group(1).upper()
    return ""


def auftrags_text(cfg, batch: int) -> tuple[str, str]:
    """Die Instruktion, die Batch `batch` bestellt hat - mit Quellenangabe.

    Reihenfolge:
      1. `runs/b<N>/auftrag.md`, Abschnitt ab `=== AUFTRAG (vom Reviewer) ===` -
         das ist der Auftrag, wie er wirklich gesendet wurde.
      2. sonst `runs/b<N>/review.md`, Block ab `<DS_INSTRUCTION>` - der Review, der ihn
         bestellt hat (der Ordner `b<N>` traegt den Review von N-1). Das ist der Fall,
         solange der Batch am Gate steht und noch nicht gestartet ist (B212).

    Durchsucht wird NUR der Auftrags-/Instruktionsteil, nicht die Prosa des Reviews -
    dort stehen Beschreibungen fremder Batches.
    """
    nummer = int(batch or 0)
    if nummer <= 0:
        return "", ""
    p = Path(cfg.root) / "runs" / f"b{nummer:03d}" / "auftrag.md"
    try:
        text = read_text(p)
    except OSError:
        text = ""
    if text:
        i = text.find("=== AUFTRAG")
        return (text[i:] if i >= 0 else text), f"runs/b{nummer:03d}/auftrag.md"
    p = Path(cfg.root) / "runs" / f"b{nummer:03d}" / "review.md"
    try:
        text = read_text(p)
    except OSError:
        return "", ""
    i = text.find("<DS_INSTRUCTION>")
    return (text[i:] if i >= 0 else text), f"runs/b{nummer:03d}/review.md"


def review_zu_batch(cfg, batch: int) -> str:
    """Der Review, der Batch `batch` bewertet hat ('' = keiner).

    Konvention (R13x belegt): das Review von Batch N liegt im Ordner des NAECHSTEN
    Batches, also `runs/b<N+1>/review.md`.
    """
    if int(batch or 0) <= 0:
        return ""
    return read_text(Path(cfg.root) / "runs" / f"b{int(batch)+1:03d}" / "review.md") or ""


def plan_mischung(cfg) -> dict:
    """Das **geltende** Mischverhaeltnis aus `analysis/hybrid-plan.md` (R13an, R13bb).

    Gesucht werden Zeilen mit dem Wort "Mischverhaeltnis" **oder** einem Gilt-Wort
    ("AB B222 GILT 1 B : 1 C …") und einem Verhaeltnis der Form `n B : m C` (auch
    `n B:m C`, beliebige Leerzeichen). Ausgewaehlt wird in dieser Reihenfolge:

      1. die **letzte Zeile mit Gilt-Wort** - das ist die geltende Regel,
      2. sonst die letzte Zeile mit dem Wort `ENTSCHEIDUNG`,
      3. sonst die letzte Zeile mit einem Verhaeltnis.

    Anlass (gemessen 2026-09-29, B216): der Plan bekam eine NEUE Zeile
    `Mischverhaeltnis 2:1 ab B217 voraussichtlich **B221** (B217 B, …)` **vor** die
    historische `**Mischverhaeltnis 2 B : 1 C (ENTSCHEIDUNG Reviewer):** B208 B, B209 B,
    B210 C`. Die alte Regel "erste Trefferzeile" nahm die neue, fand darin kein
    `n B : m C` und lieferte still `anteil=None` (der Test `test_mischverhaeltnis_aus_dem_
    plan` lief deshalb auf einen `TypeError`).

    **R13bb (Aussensicht M224-5).** Danach galt weiter die **alte** Regel 2 B : 1 C: die
    historische Zeile trug das Wort "ENTSCHEIDUNG" und war die letzte mit Verhaeltnis,
    waehrend die **gueltige** Zeile `**AB B222 GILT 1 B : 1 C (NUTZERENTSCHEIDUNG
    R221-1, 2026-09-30, wortgetreu):**` das Wort "Mischverhaeltnis" gar nicht enthaelt.
    Die Prognose rechnete deshalb mit Anteil 33 % statt 50 % (Paket E ca. 15 statt ca. 10
    Kalender-Batches). Jetzt gewinnt das Gilt-Wort; die Zeile nennt Quelle **und Stand**:
    `zeile_nr`, `ab_batch` und `stand` ("ab B222, Nutzerentscheidung R221-1, 2026-09-30")
    gehen an die Anzeige.

    Rueckgabe: `{"paare": {batch: "B"|"C"}, "anteil": float|None, "regel": str,
    "zeile": str, "zeile_nr": int, "ab_batch": int|None, "stand": str, "zustand": str,
    "datei": "hybrid-plan.md", "erkannt": bool, "grund": str, "kandidaten": int}`.
    `erkannt=False` heisst: keine Zeile trug ein Verhaeltnis - der Aufrufer meldet das
    (`plan_mischung_pruefen`), es bleibt nicht still.
    """
    try:
        text = read_text(Path(cfg.decomp) / "analysis" / "hybrid-plan.md")
    except OSError:
        text = ""
    alle = list(enumerate((text or "").splitlines(), 1))
    kandidaten = [(nr, z) for nr, z in alle
                  if _RE_MISCHUNG.search(z) or _RE_MISCH_GILT.search(z)]
    if not kandidaten:
        return {"paare": {}, "anteil": None, "regel": "", "zeile": "", "zeile_nr": 0,
                "ab_batch": None, "stand": "", "zustand": "",
                "datei": "hybrid-plan.md", "erkannt": False,
                "grund": ("Datei nicht lesbar" if not text
                          else "keine Zeile mit \"Mischverhaeltnis\" gefunden"),
                "kandidaten": 0}
    mit_zahl = [(nr, z) for nr, z in kandidaten if _RE_MISCH_ZAHL.search(z)]
    gueltig = [(nr, z) for nr, z in mit_zahl if _RE_MISCH_GILT.search(z)]
    entschieden = [(nr, z) for nr, z in mit_zahl if "entscheidung" in z.lower()]
    if gueltig:
        zeile_nr, zeile = gueltig[-1]
        zustand, erkannt, grund = "gilt", True, ""
    elif entschieden:
        zeile_nr, zeile = entschieden[-1]
        zustand, erkannt, grund = "entschieden", True, ""
    elif mit_zahl:
        zeile_nr, zeile = mit_zahl[-1]
        zustand, erkannt, grund = "letzte", True, ""
    else:
        zeile_nr, zeile = kandidaten[-1]     # ohne Verhaeltnis: die Paare der letzten Zeile
        zustand, erkannt = "", False
        grund = ("kein Verhaeltnis \"n B : m C\" in einer der "
                 f"{len(kandidaten)} Mischverhaeltnis-Zeilen")
    # Die Paarliste kommt NUR aus der gewaehlten Zeile (R13an): die ueberholte Aufzaehlung
    # darf keinen Batch umdeuten. Die geltende Zeile nennt keine Einzelbatches -> leer;
    # `strang_von_batch` faellt dann auf Instruktion/Review/Auftrag zurueck.
    paare = {int(m.group(1)): m.group(2).upper() for m in _RE_MISCH_PAAR.finditer(zeile)}
    m = _RE_MISCH_ZAHL.search(zeile)
    anteil = None
    regel = ""
    if m:
        b, c = int(m.group(1)), int(m.group(2))
        anteil = c / (b + c) if (b + c) else None
        regel = " ".join(m.group(0).split())
    ab = re.search(r"\bAB\s+B(\d+)\b", zeile, re.IGNORECASE)
    teile: list[str] = []
    if ab:
        teile.append(f"ab B{int(ab.group(1))}")
    wer = re.search(r"\b(NUTZERENTSCHEIDUNG|ENTSCHEIDUNG)\b[^,)]*", zeile, re.IGNORECASE)
    if wer:
        teile.append(" ".join(wer.group(0).split()))
    datum = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", zeile)
    if datum:
        teile.append(datum.group(1))
    return {"paare": paare, "anteil": anteil, "regel": regel,
            "zeile": " ".join(zeile.split())[:160], "zeile_nr": zeile_nr,
            "ab_batch": int(ab.group(1)) if ab else None, "stand": ", ".join(teile),
            "zustand": zustand, "datei": "hybrid-plan.md",
            "erkannt": bool(erkannt), "grund": grund, "kandidaten": len(kandidaten)}


def plan_mischung_pruefen(cfg, log=None) -> list[str]:
    """Meldet ein NICHT erkanntes Mischverhaeltnis in `hybrid-plan.md` (R13an).

    Wie `preflight_zeilen_pruefen` (R13ae): die Meldung geht ins Log **und** in die
    Review-Fakten - ein stilles `None` hat schon einmal einen Test und den Trend
    verfaelscht. Rueckgabe: Liste mit hoechstens einer Zeile.

    Zwei Wortlaute, weil zwei verschiedene Faelle:
      * Datei da, aber keine Zeile traegt `n B : m C` -> "nicht erkannt" (das ist der
        Fall, der am 29.09. den Test brach);
      * Datei fehlt/ist nicht lesbar -> "nicht lesbar" (in einem Echtlauf eine
        Anomalie, in Tests mit umgebogenem Wurzelverzeichnis normal).
    Beide Male bleibt es nicht still.
    """
    plan = plan_mischung(cfg)
    if plan.get("erkannt"):
        return []
    grund = str(plan.get("grund") or "unbekannt")
    meldung = ("PARSER: hybrid-plan.md nicht lesbar"
               if grund == "Datei nicht lesbar"
               else "PARSER: Mischverhaeltnis in hybrid-plan.md nicht erkannt")
    if log is not None:
        log.warn(meldung, datei="hybrid-plan.md", grund=grund,
                 kandidaten=plan.get("kandidaten"))
    return [f"{meldung} ({grund})"]


def _auftrag_zu_batch(cfg, batch: int) -> str:
    """Der Auftrag, mit dem Batch `batch` gelaufen ist ('' = keiner)."""
    if int(batch or 0) <= 0:
        return ""
    return read_text(Path(cfg.root) / "runs" / f"b{int(batch):03d}" / "auftrag.md") or ""


def _auftrag_strang(text: str, batch: int) -> str:
    """Strang aus dem Auftragstext - belegt aus dem Auftrag, nicht geraten.

    Drei Formen, in dieser Reihenfolge:
      * der Auftrag nennt DIESEN Batch bei einem Strang-Wort ("B208 ist der ERSTE Batch
        von Strang B", "B210 ist ein C-Batch");
      * eine Zeile beginnt mit dem Strang ("Strang B, Batch 2 von hoechstens 20; …") -
        im Auftrag beschreibt das den Batch, um den der Auftrag geht;
      * der Auftrag nennt den Batch und ein Strang-Wort in beliebiger Reihenfolge.
    Alles andere bleibt leer: ein Auftrag erwaehnt oft FREMDE Batches ("B210 = C-Batch"
    im b209-Auftrag, "Arbeit fuer den C-Batch") - daraus wird nichts geschlossen.
    """
    num = rf"\bB{int(batch)}\b"
    m = re.search(num + r"[^.\n;]{0,80}?(?:Strang\s+([BC])|([BC])-Batch)", text, re.I)
    if not m:
        m = re.search(r"(?:Strang\s+([BC])|([BC])-Batch)[^.\n;]{0,40}?" + num, text, re.I)
    if m:
        return (m.group(1) or m.group(2) or "").upper()
    m = _RE_STRANG_ZEILE.search(text)
    return m.group(1).upper() if m else ""


def strang_von_batch(cfg, batch: int) -> dict:
    """`{"strang": "B"|"C"|"", "quelle": "…"}` - ist dieser Batch ein B- oder C-Batch?

    Quellen in dieser Reihenfolge (die erste, die etwas sagt, gewinnt):

      0. **Pflichtzeile** `STRANG: B|C` bzw. `SOLL-KOEPFE: <n> (Strang B, …)` der
         Instruktion, die diesen Batch bestellt hat (`runs/b<N>/auftrag.md`, sonst
         `runs/b<N>/review.md` → `auftrags_text`, R13ac2).
      1. **Pflichtzeile** `B-SCHRITT: <n>/5 …` bzw. `B-SCHRITT: kein B-Batch (Strang C)`
         in der Review-Zusammenfassung dieses Batches (R13w).
      2. **Auftrag** `runs/b<N>/auftrag.md`, wenn er diesen Batch ausdruecklich nennt
         ("B208 ist der ERSTE Batch von Strang B", "B210 ist ein C-Batch").
      3. **`analysis/hybrid-plan.md`**, Zeile "Mischverhaeltnis …" (`B208 B, B209 B, B210 C`).
      4. **Auftrag**, sonst: eine Zeile, die mit dem Strang beginnt ("Strang B, Batch 2
         von hoechstens 20; …" nennt den Batch, um den der Auftrag geht).

    Bleibt es leer (`strang == ""`), wird **nichts** geraten: der Batch zaehlt dann wie
    bisher als C-Batch (die vorsichtige Seite - ein C-Batch zu viel zeigt eine Bewegung
    zu viel, aber verschluckt keinen Befund).
    """
    # R13ac2 ZUERST: die ausdrueckliche Pflichtzeile der Instruktion ist der beste Beleg -
    # B211 trug nur sie ("SOLL-KOEPFE: 0 (Strang B, …)") und galt sonst als C-Batch.
    text, quelle = auftrags_text(cfg, batch)
    s = _pflicht_strang(text)
    if s in ("B", "C"):
        return {"strang": s, "quelle": f"{STRANG_QUELLEN[0]} ({quelle})"}
    review = review_zu_batch(cfg, batch)
    if review:
        if _RE_B_SCHRITT.search(review):
            return {"strang": "B", "quelle": STRANG_QUELLEN[1]}
        if _RE_B_SCHRITT_C.search(review):
            return {"strang": "C", "quelle": STRANG_QUELLEN[1]}
    auftrag = _auftrag_zu_batch(cfg, batch)
    if auftrag:
        s = _auftrag_strang(auftrag, batch)
        if s in ("B", "C"):
            return {"strang": s, "quelle": STRANG_QUELLEN[2]}
    plan = plan_mischung(cfg)
    if plan.get("paare", {}).get(int(batch)):
        return {"strang": plan["paare"][int(batch)],
                "quelle": f"{STRANG_QUELLEN[3]} ({plan['zeile'][:80]})"}
    return {"strang": "", "quelle": ""}


def ist_b_batch(cfg, batch: int) -> bool:
    """Ist dieser Batch ein B-Batch? (`strang_von_batch`; unbekannt = nein)"""
    return strang_von_batch(cfg, batch).get("strang") == "B"


def ohne_pflichtzeile(cfg, anzahl: int = 6) -> list[int]:
    """B-Batches der letzten `anzahl` Bewertungen, deren Review die Pflichtzeile fehlen laesst."""
    out: list[int] = []
    try:
        ordner = sorted(((int(p.name[1:]), p) for p in (Path(cfg.root) / "runs").iterdir()
                         if p.is_dir() and p.name.startswith("b")
                         and p.name[1:].isdigit()), reverse=True)
    except (OSError, ValueError):
        return []
    for nummer, p in ordner[: max(1, int(anzahl))]:
        bewertet = nummer - 1
        if bewertet <= 0:
            continue
        if not (p / "review.md").is_file():
            continue
        if strang_von_batch(cfg, bewertet).get("strang") != "B":
            continue
        if not _RE_B_SCHRITT.search(read_text(p / "review.md") or ""):
            out.append(bewertet)
    return sorted(out)


def pflichtzeile_hinweis(cfg, batch: int) -> str:
    """Was der Review ueber den Strang des BEWERTETEN Batches schreiben muss ('' = nichts).

    R13aa (Punkt 1): fehlt die Pflichtzeile in einem B-Batch, wird das im Review-Protokoll
    gemeldet - vorher fiel es still aus, und der Ausloeser "Kernzahl ohne Bewegung" hielt
    den B-Batch fuer einen C-Batch. Fuer C-Batches steht die Kurzform bereit, damit die
    Klassifikation sich selbst erklaert.
    """
    if int(batch or 0) <= 0:
        return ""
    s = strang_von_batch(cfg, int(batch))
    fehlend = ohne_pflichtzeile(cfg, 6)
    zusatz = ("" if not fehlend else
              " In den letzten Reviews fehlte sie in: "
              + ", ".join(f"B{n}" for n in fehlend) + ".")
    if s.get("strang") == "B":
        # R13bl (02.10.2026, Nutzerentscheid 30.09.): die Grenze von 20 B-Batches ist
        # aufgehoben - die Zahl ist eine Zaehlung, kein Budget. Wortlaut wie in
        # `prompts/reviewer.md`; der Parser (`_RE_B_SCHRITT`) liest ohnehin nur `n/5`.
        return (f"B{batch} ist ein B-Batch ({s.get('quelle')}). In DEINER TELEGRAM_SUMMARY "
                f"muss die Pflichtzeile `B-SCHRITT: <n>/5 <Name>, B-Batch <k> "
                f"(Zaehlung, keine Grenze - Nutzerentscheid 30.09.)` "
                f"stehen (Stand nach diesem Batch).{zusatz}")
    if s.get("strang") == "C":
        return (f"B{batch} ist ein C-Batch ({s.get('quelle')}). In DEINER TELEGRAM_SUMMARY "
                f"gehoert die Zeile `B-SCHRITT: kein B-Batch (Strang C)`.{zusatz}")
    return (f"Fuer B{batch} ist der Strang nicht belegbar (keine Pflichtzeile im Review, "
            f"kein Marker im Auftrag, kein Eintrag in hybrid-plan.md). Schreibe die "
            f"Pflichtzeile, damit die Zuordnung belegt ist.{zusatz}")


def _mischung_zeile(cfg, d: dict) -> list[str]:
    """Die Mischungs-Zeile: wieviele C-Batches im Fenster - und was die Regel sagt (R13aa).

    Zwei Zahlen, bewusst getrennt: **gemessen** (Anteil im Fenster, nur Batches mit
    belegtem Strang) und **Regel** (Mischverhaeltnis aus `hybrid-plan.md`).

    R13bn (M242-3): die Kalender-Rechnung nimmt den **gemessenen Abschnitt**, wenn die
    Reihe mit mehreren C-Batches endet (Strang B ruht) - die Plan-Regel beschreibt den
    geplanten Wechsel und stand im Widerspruch zu dem, was die Batches wirklich taten.
    Welche Zahl gilt, steht im Text (`anteil_quelle`).
    """
    gem = d.get("anteil_gemessen")
    n = int(d.get("n") or 0)
    c = len(d.get("c_fenster") or [])
    if not n:
        return []
    teile = [f"  Mischung     : {c} C von {n} Batches im Fenster ({gem * 100:.0f} %)"
             if gem is not None else "  Mischung     : nicht ermittelbar"]
    quelle = str(d.get("anteil_quelle") or "")
    regel = d.get("anteil_c")
    if d.get("c_lauf"):
        teile[0] += (f"; die letzten {int(d['c_lauf'])} Batches sind C (ab B{int(d['c_lauf_von'])}) "
                     f". Anteil fuer die Rechnung: {(regel or 0) * 100:.0f} %")
    elif regel and quelle.startswith("Regel"):
        teile[0] += (f"; Regel {quelle[6:]} -> jeder "
                     f"{1 / regel:.0f}. Batch ist ein C-Batch ({regel * 100:.0f} %)")
    elif regel:
        teile[0] += f"; Anteil fuer die Rechnung: {regel * 100:.0f} % ({quelle})"
    return teile

def durchsatz_alt(cfg, n: int = STANDARD_FENSTER) -> dict:
    """(entfernt) - frueher aus den C-Koepfe-Zeilen der Batch-Dokumente."""
    return {}


def durchsatz_zeilen(cfg, n: int = STANDARD_FENSTER) -> list[str]:
    """Die Zeilen des Durchsatz-Blocks.

    R13ac (M210-2): ZWEI Zaehler, klar getrennt und benannt -

    * **C Koepfe** aus der maschinengeschriebenen Preflight-Zeile (`_preflight_<N>.txt`),
      lueckenlos ueber das Trendfenster; fehlt die Quelle, steht dort "NICHT GEMESSEN".
    * **R207** (gebaut, alle Straenge) aus den kanonischen Bilanzdateien - dieser Zaehler
      hat in B209 keine Datei und wird deshalb als Fenster mit Luecke ausgewiesen.

    Vorher stand unter "Durchsatz" nur der R207-Zaehler mit dem Wort "Koepfe", und die
    Trendzahl daneben kam aus einer anderen Quelle als der Rest - genau das hat die
    Aussensicht zu B210 als "mischt zwei Zaehler" beanstandet.
    """
    d = durchsatz(cfg, n)
    # R13ba (M221-5): EINE Rate je C-Batch fuer alle Hochrechnungen - der MEDIAN der
    # Kopf-Batches, nicht das Mittel ueber alle C-Batches. Die beiden Grundmengen stehen
    # als eigene Zeile darunter (`rate_text`), damit die Zahl nachpruefbar bleibt.
    raten = c_rate(cfg, n)
    d["c_rate"] = raten
    d["rate_c_koepfe"] = raten["rate"]
    d["rate_c_quelle"] = raten["quelle"]
    ver = d.get("c_verifiziert") or {}
    if not d["fenster"]:
        return ["  Durchsatz    : nicht ermittelbar (keine Bilanzdatei gefunden)"]
    letzter = d["letzter"]
    pe = d.get("paket_e") or {}
    reihe = ", ".join(f"{e['batch']}: {e['koepfe']:+d}" for e in d["fenster"])
    trend = d.get("c_trend") or {}
    zeilen = ["  Durchsatz    : C Koepfe (Preflight-Messung, analysis/_preflight_<N>.txt "
              "Zeile \"C Koepfe\")"]
    if trend.get("gemessen"):
        e, l = trend["erst"], trend["letzt"]
        zeilen.append(f"                 letzter gemessener Batch B{l['batch']}: {l['koepfe']} "
                      f"Koepfe ({trend['delta']:+d} seit B{e['batch']})")
        spanne = (f"{trend['anzahl_batches']} Batches"
                  + (", lueckenlos" if not trend["luecken"] else
                     ", Luecken: " + ", ".join(f"B{b}" for b in trend["luecken"])))
        zeilen.append(f"                 Trend B{e['batch']} {e['koepfe']} -> B{l['batch']} "
                      f"{l['koepfe']} = {trend['delta']:+d} Koepfe ({spanne}, "
                      f"{trend['n_gemessen']} Dateien)")
        mittel = trend.get("mittel_je_batch")
        if mittel is not None:
            zeilen.append(f"                 Mittel: {mittel:+.1f} Koepfe je Batch"
                          + (f" (B und C zusammen, ueber {trend['anzahl_batches']} "
                             "Schritte)")
                          + (f"; {trend['mittel_je_c_batch']:+.1f} je C-Batch "
                             f"({len(trend['c_schritte'])} C-Batch-Schritte im Fenster)"
                             if trend.get("mittel_je_c_batch") is not None else ""))
        zeilen.append(f"                 Quelle dieser Zeilen: analysis/{e['datei']} bis "
                      f"analysis/{l['datei']} (Zeile \"C Koepfe\", "
                      f"{trend['n_gemessen']} Dateien)")
        # R13bn (M243-3): dieselbe Reihe fuer die VOLL verifizierten Koepfe.
        if ver.get("gemessen"):
            ve, vl = ver["erst"], ver["letzt"]
            vspanne = (f"{ver['anzahl_batches']} Batches"
                       + (", lueckenlos" if not ver["luecken"] else
                          ", Luecken: " + ", ".join(f"B{b}" for b in ver["luecken"])))
            zeilen.append(f"                 Trend C verifiziert (Bahnabdeckung, gleiche "
                          f"Dateien) B{ve['batch']} {ve['verifiziert']} -> "
                          f"B{vl['batch']} {vl['verifiziert']} = {ver['delta']:+d} Koepfe "
                          f"({vspanne})")
            if ver.get("median_je_c_batch") is not None:
                zeilen.append(f"                 Rate C verifiziert: Median "
                              f"{ver['median_je_c_batch']:+.0f} je C-Batch | Mittel "
                              f"{ver['mittel_je_c_batch']:+.1f} je C-Batch "
                              f"({len(ver['c_schritte'])} C-Batch-Schritte) - die Zahl der "
                              f"VOLL verifizierten Koepfe; der Kopfzaehler oben zaehlt "
                              f"Koepfe mit offenem Rumpf mit")
        else:
            zeilen.append("                 C verifiziert: nicht gemessen ("
                          + str(ver.get("grund") or "keine Bahnabdeckungszeile") + ")")
    else:
        zeilen.append("                 NICHT GEMESSEN: "
                      + str(trend.get("grund") or "keine Preflight-Reihe gefunden"))
    # Der zweite Zaehler bleibt - aber GETRENNT und benannt (M210-2: nicht mischen).
    # Eine LUECKE wird aus den erwarteten Batchnummern bestimmt, nicht aus der Anzahl
    # der Eintraege: das Fenster kann fuenf Eintraege haben und trotzdem einen Batch
    # ueberspringen (genau der B210-Fall: B209 fehlt, B205 rueckt nach).
    erwartet = {letzter["batch"] - i for i in range(1, d["n"])}
    fehlend = sorted(erwartet - {x["batch"] for x in d["fenster"]})
    zeilen += [
        f"                 Zaehler R207 (gebaut, ALLE Straenge - nicht mit den C Koepfen "
        f"mischen) letzter Batch {letzter['batch']}: "
        f"{letzter['r207_vorher']} -> {letzter['r207']} ({letzter['koepfe']:+d})",
        f"                 Mittel der letzten {d['n']} nach R207 (B+C gemischt): "
        f"+{d['mittel_koepfe']:.1f} Koepfe je Batch   (Fenster: {reihe}"
        + ("   - LUECKENHAFT: die kanonischen Bilanzdateien fehlen fuer "
           + ", ".join(f"B{b}" for b in fehlend) + ")" if fehlend else ")"),
    ]
    if d["mittel_insn"]:
        letzte_insn = next(((x["batch"], x["insn"]) for x in d["fenster"]
                            if x.get("insn")), None)
        zeilen.append(f"                 Insn (nur wo belegt, Paket-E-Zeile): "
                      + (f"letzter belegter Batch B{letzte_insn[0]}: "
                         f"{letzte_insn[1]} Insn / " if letzte_insn else "kein Einzelwert / ")
                      + f"Mittel {d['mittel_insn']:.0f} Insn")
    else:
        zeilen.append("                 Insn: je Batch nicht durchgaengig belegt "
                      "(die Bilanzdatei fuehrt nur Koepfe)")
    # R13aa (Punkt 3): Durchsatz je C-Batch + Mischverhaeltnis GETRENNT nennen.
    c_batches = d.get("c_fenster") or []
    if c_batches:
        namen = ", ".join(f"B{e['batch']}" for e in c_batches)
        zeilen.append(f"                 C-Batches im R207-Fenster: "
                      f"+{d.get('mittel_c_koepfe_r207', 0.0):.1f} Koepfe je C-Batch "
                      f"(R207-Zaehler, {len(c_batches)} von {d['n']}: {namen})")
    zeilen += _mischung_zeile(cfg, d)
    if raten.get("text"):
        zeilen.append(f"                 C-Rate je C-Batch: {raten['text']}")
    messung = d.get("paket_e_messung") or {}
    if messung:
        zeilen.append("                 offen (Paket E, C-Arbeitsvorrat): "
                      + paket_e_offen_text(messung))
    else:
        zeilen.append("                 offen (Paket E, C-Arbeitsvorrat): "
                      + paket_e_offen_text(None, (pe.get("batch")
                                                  if pe.get("paket_e_koepfe") is not None
                                                  else None)))
    hoch = kalender_zeilen(cfg, (messung.get("koepfe") if messung else 0), d)
    if hoch:
        zeilen.append("                 HYPOTHESIS (Paket E, Arbeitsvorrat):")
        zeilen += hoch
    else:
        zeilen.append("                 HYPOTHESIS: keine Hochrechnung moeglich")
    zeilen += _c_gesamt_zeilen(cfg, d)
    zeilen += _relevanz_zeilen(cfg, d)
    messung = d.get("paket_e_messung") or {}
    pe_quelle = (f" + analysis/{messung['datei']} (\"Paket E offen GESAMT\", "
                 f"gemessen B{messung['batch']}"
                 + (f", {messung['datum']}" if messung.get("datum") else "") + ")"
                 if messung else
                 " + KEINE Paket-E-Messung (analysis/_m*/_c_paket_e*.txt fehlt)")
    zeilen.append(f"                 Quelle: analysis/{d['quelle']} (Zeile \"R207 "
                  "rueckwaerts\")" + pe_quelle
                  + _c_quelle_notiz(d.get("c_quelle"), d.get("c_zeile")))
    return zeilen


def _c_quelle_notiz(quelle: str, zeile: int | None) -> str:
    """Der Zusatz `+ analysis/… ("C Koepfe", …)` in der Quellenzeile (R13x).

    Ist die Zahl die **Preflight-Zeile**, wird das gesagt; kommt sie aus dem Dokument
    (Rueckfall vor dem C-Strang), ebenfalls - mit der Zeilennummer der Soll/Ist-Tafel,
    damit die Aussensicht den Beleg sofort nachschlagen kann.
    """
    if not quelle:
        return ""
    if str(quelle).startswith("_preflight"):
        return f" + analysis/{quelle} (\"C Koepfe\", Preflight)"
    return (f" + analysis/{quelle} (\"C Koepfe\", Ist-Spalte"
            + (f", Zeile {zeile}" if zeile else "") + ")")


def _c_gesamt_zeilen(cfg, d: dict) -> list[str]:
    """Die zweite, GETRENNTE Hochrechnung: das ganze C-Programm (R13t, Punkt 3).

    Zwei Quellen, in dieser Reihenfolge:
      1. **gemessen** - die drei Klassen des Arbeitsvorrats aus dem Relevanz-Cache
         (Inventar minus gebaut); das ist die frischeste Zahl.
      2. **abgeleitet** - der Vorrat steht sonst nur in den Planungsdokumenten (B196
         §6.1: "OFFEN: 1481 Koepfe / 94913 Insn", Quelle `analysis/_m196/_plan_c.txt`)
         und wird ueber das R207-Delta auf heute gerechnet; die Insn-Zahl ist dann
         eine Schaetzung.
    """
    r = port_relevanz(cfg) or {}
    klassen = r.get("klassen") or {}
    if klassen:
        offen = sum(k["koepfe"] for k in klassen.values())
        insn = sum(k["insn"] for k in klassen.values())
        zeilen = [f"                 HYPOTHESIS (C gesamt, GEMESSEN): offen {offen} Koepfe / "
                  f"{insn} Insn (Inventar minus gebaut, s. Klassen unten)"]
        zeilen += kalender_zeilen(cfg, offen, d)
        return zeilen
    g = c_offen_gesamt(cfg)
    if not g or not d.get("letzter"):
        return ["                 HYPOTHESIS (C gesamt): nicht ermittelbar - kein "
                "Relevanz-Cache (tools/r13t_cov_relevanz.py) und kein Dokument mit "
                "der Zeile \"OFFEN: <K> Koepfe / <I> Insn\""]
    heute = d["letzter"].get("r207")
    if not heute or not g.get("bau"):
        return [f"                 HYPOTHESIS (C gesamt): Vorrat "
                f"{g['koepfe']} Koepfe / {g['insn']} Insn (Stand B{g['batch']}), "
                "seitheriger Bau nicht rechenbar"]
    seitdem = max(0, heute - g["bau"])
    offen = max(0, g["koepfe"] - seitdem)
    schnitt = g["insn"] / g["koepfe"] if g["koepfe"] else 0.0
    insn = max(0.0, g["insn"] - seitdem * schnitt)
    zeilen = [f"                 HYPOTHESIS (C gesamt, ABGELEITET): offen "
              f"{offen} Koepfe / ~{insn / 1000:.1f}k Insn (Schaetzung)"]
    zeilen += kalender_zeilen(cfg, offen, d)
    zeilen.append(f"                   Rechenweg: analysis/{g['dokument']} "
                  f"(\"OFFEN: {g['koepfe']} Koepfe / {g['insn']} Insn\", Stand B"
                  f"{g['batch']}; Bau-Liste damals {g['bau']}) minus R207-Delta "
                  f"{heute} - {g['bau']} = {seitdem} Koepfe; Insn-Anteil je Kopf "
                  f"({schnitt:.1f}) fortgeschrieben - kein Insn-Beleg je Batch")
    return zeilen


def _relevanz_zeilen(cfg, d: dict | None = None) -> list[str]:
    """Port-Relevanz, die drei Klassen des C-Arbeitsvorrats und die Aufnahmen (R13t2)."""
    r = port_relevanz(cfg)
    if not r:
        return ["  Port-Relevanz: nicht gemessen (tools/r13t_cov_relevanz.py fahren)"]
    d = d or {}
    # R13aa: gerechnet wird mit dem Durchsatz JE C-BATCH - die Klasse "nicht gebaut"
    # wird nur in C-Batches abgearbeitet, nicht in jedem Kalender-Batch. R13ba: das ist
    # der MEDIAN der Kopf-Batches (dieselbe Zahl wie in der Hochrechnung), nicht das
    # Mittel ueber alle C-Batches.
    mittel = d.get("rate_c_koepfe") or d.get("mittel_c_koepfe") or 0.0
    zeilen = [
        f"  Port-Relevanz: ausgefuehrt {r['ausgefuehrt']} | davon gebaut "
        f"{r['gebaut_ausgefuehrt']} | davon verifiziert {r['verifiziert_ausgefuehrt']}"
        f" von {r['ausgefuehrt']}"
        f"  (Fenster: {r.get('fenster', '?')}; Messung {r.get('ts', 'Zeit unbekannt')}"
        f" durch {r.get('erzeuger', '?')})",
        f"                 Paket-E-Wurzeln {r['paket_e_wurzeln_ausgefuehrt']}"
        f"/{r['paket_e_wurzeln']} ausgefuehrt, offene Blaetter "
        f"{r['paket_e_blaetter_ausgefuehrt']}/{r['paket_e_blaetter']}",
    ]
    klassen = r.get("klassen") or {}
    if klassen:
        gesamt = sum(k["koepfe"] for k in klassen.values())
        namen = {"1_ausgefuehrt_nicht_gebaut": "(1) ausgefuehrt, noch nicht gebaut  ",
                 "2_nicht_ausgefuehrt_paket_e": "(2) nicht ausgefuehrt, Paket E   ",
                 "3_nicht_ausgefuehrt_rest": "(3) nicht ausgefuehrt, sonstiger Rest"}
        zeilen.append(f"  C-Arbeitsvorrat: {gesamt} Koepfe nicht gebaut (von "
                      f"{r.get('inventar', '?')} im Inventar)")
        for schluessel, k in klassen.items():
            hoch = (f" -> ca. {k['koepfe'] / mittel:.0f} C-Batches" if mittel > 0 else "")
            zeilen.append(f"                 {namen.get(schluessel, schluessel)}: "
                          f"{k['koepfe']:4d} Koepfe / {k['insn']:6d} Insn{hoch}")
        zeilen.append("                 \"nicht ausgefuehrt\" = in den VORHANDENEN Aufnahmen "
                      "nicht ausgefuehrt - NICHT \"unnoetig\" (die Aufnahmen decken nur "
                      "Boot + einen Teil von Level 1 ab)")
        if r.get("paket_e_huelle"):
            # R13aw: die Projektzahl stand hier fest als "274 / 38" (B208-Stand). Sie kommt
            # jetzt aus derselben Quelle wie ueberall sonst - der juengsten Messung.
            messung = d.get("paket_e_messung") or {}
            projekt = (f"{messung['koepfe']} / {messung['insn']} (gemessen B{messung['batch']})"
                       if messung else "nicht gemessen")
            zeilen.append(f"                 (Paket-E-Huelle eigene Nachrechnung: "
                          f"{r['paket_e_huelle']} Koepfe, davon offen "
                          f"{r.get('paket_e_huelle_offen', '?')}; Projektzahl "
                          f"`c_kopf.py paket_e`: {projekt})")
    a = r.get("aufnahmen") or {}
    if a:
        zeilen.append(f"  Aufnahmen    : {a.get('beschreibung', '?')}")
        zeilen.append(f"                 Quelle: {a.get('quelle', '?')}; "
                      f"gemessen {r.get('ts', '?')}")
    return zeilen


# ------------------------------------------------------------------ PLAN/IST
# Die Instruktionen schreiben Kopfadressen BEIDES: mit und ohne `0x` ("`8005BF74` (51)").
_RE_ADDR = re.compile(r"\b(?:0x)?(80[0-9A-Fa-f]{6})\b")
_RE_KLAMMER = re.compile(r"\((\d{1,4})\)")
_RE_DAUER = re.compile(r"Laufzeit:\s*(?:(\d+)h)?(\d+)m(\d+)s")
_RE_ABBRUCH = re.compile(r"Abbruchgrund:\s*([^|\n]+)")
_RE_TEIL = re.compile(r"^TEIL\s*3\b.*$", re.IGNORECASE | re.MULTILINE)
# R13ac (M210-4): die ausdrueckliche Soll-Zeile der DS_INSTRUCTION. Sie ist die EINZIGE
# PLAN-Quelle; B211 hat sie erstmals. Die alte Heuristik (gezaehlte Kopfadressen) wird
# NICHT mehr als PLAN gezeigt - sie las in B210 "6 Koepfe", waehrend der Auftrag
# "keine neuen Koepfe" sagte.
_RE_SOLL = re.compile(r"SOLL-KOEPFE\s*:?\s*\**\s*(\d+)", re.IGNORECASE)


def dauer_text(treffer) -> str:
    """`30m07s` bzw. `1h20m03s` aus dem Laufzeit-Treffer der Harness-Fakten."""
    if not treffer:
        return ""
    stunden, minuten, sekunden = treffer.groups()
    vor = f"{stunden}h" if stunden else ""
    return f"{vor}{minuten}m{sekunden}s"


def dauer_sekunden(sekunden) -> str:
    """`30m07s` bzw. `1h20m03s` aus Sekunden (Wanduhr des Laufs).

    ABGESCHNITTEN, nicht gerundet: die Harness-Fakten zeigen denselben Wert ebenfalls
    abgeschnitten (2846,651 s -> "47m26s"), und genau diese Zahl steht in den
    Batch-Dokumenten - gerundet stuende dort "47m27s" und der Vergleich stimmte nicht.
    """
    try:
        gesamt = int(float(sekunden))
    except (TypeError, ValueError):
        return ""
    if gesamt < 0:
        return ""
    h, rest = divmod(gesamt, 3600)
    m, s = divmod(rest, 60)
    return (f"{h}h{m:02d}m{s:02d}s" if h else f"{m}m{s:02d}s")


def lauf_ist(cfg, batch: int) -> dict:
    """Laufzeit und Abbruchgrund EINES Batches - aus dem Ergebnis SEINES Laufs (R13x).

    Quelle ist `runs/b<batch>/result.json`: diesen Beleg schreibt der Lauf in seinen
    EIGENEN Ordner. **Nicht** `runs/b<batch>/harness-facts.md` - diese Datei legt
    `orchestrator.review` in den Ordner des NAECHSTEN Batches (`runs/b<N+1>`), weil dort
    das Review liegt; `runs/b<N>/harness-facts.md` traegt deshalb die Fakten von b<N-1>.
    Gemessen (M208-3c): b208/harness-facts.md nennt 47m26s (= b207), b208/result.json
    1160,9 s = 19m20s. Genau diese Verwechslung hatte die Laufzeitspalte um einen Batch
    verschoben.

    Rueckfall: die Fakten-Datei **des naechsten Ordners** (`runs/b<N+1>/harness-facts.md`),
    und nur, wenn ihre Kopfzeile ausdruecklich diesen Batch nennt ("Review: bewertet wird
    Batch N"). Die Fakten im eigenen Ordner werden NIE gelesen.
    """
    runs = Path(cfg.sub("runs"))
    res = read_json(runs / f"b{int(batch):03d}" / "result.json", {}) or {}
    dauer = dauer_sekunden(res.get("duration_s"))
    if dauer:
        return {"dauer": dauer, "quelle": "result.json",
                "abbruch": " ".join(str(res.get("killed_reason") or "").split())
                or "kein Abbruch",
                "rc": res.get("rc")}
    text = read_text(runs / f"b{int(batch) + 1:03d}" / "harness-facts.md")
    kopf = f"- Review: bewertet wird Batch {int(batch)};"
    if text and any(z.startswith(kopf) for z in text.splitlines()):
        m = _RE_DAUER.search(text)
        a = _RE_ABBRUCH.search(text)
        return {"dauer": dauer_text(m),
                "quelle": f"harness-facts.md (b{int(batch) + 1:03d})",
                "abbruch": " ".join(a.group(1).split()) if a else ""}
    return {"dauer": "", "quelle": "", "abbruch": ""}


def soll_koepfe(instruktion: str) -> int | None:
    """Die Zeile `SOLL-KOEPFE: <n>` der DS_INSTRUCTION - oder None (R13ac, M210-4).

    Der Reviewer gibt die Sollzahl seit B211 mit dieser Zeile selbst vor. Steht sie
    nicht da, bleibt PLAN leer ("-") - es wird NICHT aus Adressen geraten.
    """
    m = _RE_SOLL.search(instruktion or "")
    return int(m.group(1)) if m else None


def geplante_koepfe(instruktion: str) -> tuple[int, int, str]:
    """(Kopfzahl, Insn-Summe, Quelle) aus einer DS_INSTRUCTION - **Heuristik**.

    Gezaehlt werden die genannten **Kopfadressen** (`0x80xxxxxx`) und die Insn-Zahlen in
    Klammern direkt dahinter; genommen wird der Abschnitt ab der Ueberschrift `TEIL 3`
    (dort steht die Bau-Liste).

    R13ac (M210-4): Diese Heuristik ist **nicht mehr die PLAN-Spalte** der Tafel (das ist
    `soll_koepfe`). Sie bleibt als Zaehlhilfe erhalten, weil sie die im Auftrag GENANNTEN
    Adressen beschreibt - als PLAN taugt sie nicht: in B210 zeigte sie "6 Koepfe",
    waehrend der Auftrag ausdruecklich "keine neuen Koepfe" verlangte.
    """
    text = instruktion or ""
    m = _RE_TEIL.search(text)
    quelle = "TEIL 3 der Instruktion"
    if m:
        # WICHTIG: ab `m.start()`, nicht ab `m.end()` - das Muster deckt die ganze
        # Zeile ab (`.*$`), und die Adressen stehen IN dieser Zeile (erster Anlauf
        # schnitt sie weg und meldete "0 Koepfe geplant").
        rest = text[m.start():]
        naechste = re.search(r"^TEIL\s*\d", rest[1:], re.IGNORECASE | re.MULTILINE)
        text = rest[:naechste.start() + 1] if naechste else rest
    else:
        quelle = "ganze Instruktion (kein TEIL 3)"
    adressen = set(_RE_ADDR.findall(text))
    insn = 0
    for treffer in _RE_ADDR.finditer(text):
        fenster = text[treffer.end():treffer.end() + 8]
        k = _RE_KLAMMER.search(fenster)
        if k:
            insn += int(k.group(1))
    return len(adressen), insn, quelle


def plan_ist(cfg, n: int = STANDARD_FENSTER) -> list[dict]:
    """PLAN/IST je Batch der letzten `n` (neueste zuerst).

    PLAN  = die Zeile `SOLL-KOEPFE: <n>` der DS_INSTRUCTION (`runs/b<N>/auftrag.md`);
            fehlt sie, bleibt PLAN leer ("-") - R13ac (M210-4)
    IST   = die Differenz der Zeile `R207 rueckwerts` (gebaut, ALLE Straenge) aus der
            kanonischen Bilanzdatei
    C-KOEPFE = die gemessene C-Koepfe-Zahl der Preflight-Datei (`_preflight_<N>.txt`),
            als Delta gegenueber dem vorigen gemessenen Batch - der ZWEITE Zaehler,
            bewusst getrennt von R207 (M210-2)
    LAUFZEIT/ABBRUCH = `runs/b<N>/result.json` DIESES Laufs (Rueckfall: die Fakten-Datei
            im Ordner des naechsten Batches - s. `lauf_ist`)
    """
    d = durchsatz(cfg, n)
    runs = Path(cfg.sub("runs"))
    reihe = {e["batch"]: e for e in kernzahlen(cfg, MAX_DOKUMENTE)}
    c_reihe = {e["batch"]: e for e in preflight_c_koepfe(cfg, TREND_FENSTER)}
    out: list[dict] = []
    for e in d["fenster"]:
        batch = e["batch"]
        # R13ac2: PLAN kommt aus der Instruktion, die DIESEN Batch bestellt hat (Auftrag,
        # sonst der Review davor) - so ist auch die Zeile sichtbar, die noch am Gate steht.
        auftrag, plan_quelle = auftrags_text(cfg, batch)
        geplant_k, geplant_i, quelle = geplante_koepfe(auftrag)
        lauf = lauf_ist(cfg, batch)
        dok = reihe.get(batch) or {}
        c_jetzt = c_reihe.get(batch)
        c_vor = c_reihe.get(batch - 1)
        out.append({
            "batch": batch,
            "soll_koepfe": soll_koepfe(auftrag),
            "strang": strang_von_batch(cfg, batch).get("strang") or "?",
            "geplant_koepfe": geplant_k or None,
            "geplant_insn": geplant_i or None,
            "plan_quelle": plan_quelle or quelle,
            "ist_koepfe": e["koepfe"],
            "ist_insn": e.get("insn"),
            "ist_faelle": dok.get("c_faelle"),
            "c_koepfe": c_jetzt["koepfe"] if c_jetzt else None,
            "c_delta": ((c_jetzt["koepfe"] - c_vor["koepfe"])
                        if (c_jetzt and c_vor and batch - 1 in c_reihe) else None),
            "c_quelle": c_jetzt["datei"] if c_jetzt else "",
            "dauer": lauf["dauer"],
            "dauer_quelle": lauf["quelle"],
            "abbruch": lauf["abbruch"],
        })
    return out


def median(werte: list) -> float | None:
    zahlen = sorted(float(w) for w in werte if isinstance(w, (int, float)))
    if not zahlen:
        return None
    mitte = len(zahlen) // 2
    if len(zahlen) % 2:
        return zahlen[mitte]
    return (zahlen[mitte - 1] + zahlen[mitte]) / 2


def plan_ist_text(cfg, n: int = STANDARD_FENSTER) -> str:
    """Tafel fuer den Review-Prompt: PLAN | IST (R207) | C Koepfe | LAUFZEIT | ABBRUCH.

    R13ac (M210-2/M210-4): PLAN kommt aus der Zeile `SOLL-KOEPFE:` der Instruktion
    (sonst "-"), und die beiden Zaehler stehen in GETRENNTEN Spalten - der R207-Zaehler
    (alle Straenge) und die gemessenen C Koepfe aus der Preflight-Datei. Der MEDIAN wird
    nur ueber **C-Batches mit Soll > 0** gebildet (B- und Aufraeum-Batches zaehlten
    vorher als Null-Batches mit und ergaben fuer den naechsten C-Batch die Obergrenze 0).

    Die Laufzeit kommt aus dem Ergebnis des jeweiligen Laufs (`runs/b<N>/result.json`);
    wird sie aus dem Rueckfall gelesen, steht ein `*` daran und die Herkunft darunter (R13x).
    """
    reihen = plan_ist(cfg, n)
    if not reihen:
        return "(keine PLAN/IST-Daten - keine Soll/Ist-Tafel in den Batch-Dokumenten)"
    zeilen = ["Batch | PLAN (SOLL-KOEPFE der Instruktion) | IST (R207 gebaut, alle "
              "Straenge) | C Koepfe (Preflight) | Laufzeit (result.json) | Abbruch"]
    rueckfall: list[str] = []
    for r in reihen:
        plan = (f"{r['soll_koepfe']} Koepfe" if r.get("soll_koepfe") is not None else "-")
        ist = (f"+{r['ist_koepfe']} Koepfe"
               + (f" / +{r['ist_insn']} Insn" if r.get("ist_insn") else "")
               if r["ist_koepfe"] is not None else "nicht ermittelbar")
        if r.get("c_koepfe") is None:
            c_spalte = "nicht gemessen"
        elif r.get("c_delta") is None:
            c_spalte = f"{r['c_koepfe']} (Vorgaenger nicht gemessen)"
        else:
            c_spalte = f"{r['c_koepfe']} ({r['c_delta']:+d})"
        marke = ""
        if r["dauer"] and r.get("dauer_quelle") != "result.json":
            marke = "*"
            rueckfall.append(f"B{r['batch']}: {r.get('dauer_quelle')}")
        zeilen.append(f"B{r['batch']} | {plan} | {ist} | {c_spalte} | "
                      f"{r['dauer'] or '?'}{marke} | {r['abbruch'] or '?'}")
    # R13aw (M219-3): der MEDIAN wird ueber die ZUWaeCHSE der C Koepfe je C-Batch
    # gebildet, nicht ueber die Gesamtzahl. GEMESSEN: die Summen sind 88, 96, 90 … -
    # ein Median daraus (88) beschreibt keinen Zuwachs, sondern den halben Bestand; die
    # echten Zuwaechse waren +7 (B216) und +5 (B219). R13ba (M221-5): dieselbe Rechnung
    # liefert `c_rate` - die Durchsatzzeile der BILANZ rechnet mit DIESER Zahl.
    raten = c_rate(cfg, n, reihen=reihen)
    basis = [{"batch": b, "c_delta": dlt} for b, dlt in raten["kopf_batches"]]
    med = raten["median"]
    if med is None:
        zeilen.append("MEDIAN: nicht gemessen (kein C-Batch im Fenster mit "
                      "SOLL-KOEPFE > 0 und gemessenem Zuwachs)")
    else:
        einzeln = ", ".join(f"{r['c_delta']:+d} (B{r['batch']})" for r in basis)
        zeilen.append(f"MEDIAN der {len(basis)} Zuwaechse der C Koepfe je C-Batch "
                      f"mit SOLL-KOEPFE > 0 ({einzeln}): {med:.0f} Koepfe je C-Batch "
                      f"(Ziel des naechsten Batches: hoechstens ca. {med * 1.3:.0f})")
        zeilen.append("  (" + raten["text"] + ")")
    if rueckfall:
        zeilen.append("* Laufzeit NICHT aus runs/b<N>/result.json, sondern aus dem "
                      "Rueckfall (" + "; ".join(rueckfall) + ")")
    return "\n".join(zeilen)


# ------------------------------------------------------- Fragen an den Nutzer
def _letztes_review(cfg) -> str:
    """Der Review-Mitschnitt des zuletzt bewerteten Batches (oder leer)."""
    runs = Path(cfg.sub("runs"))
    try:
        kandidaten = sorted(((int(p.name[1:]), p) for p in runs.iterdir()
                             if p.is_dir() and p.name.startswith("b") and p.name[1:].isdigit()),
                            reverse=True)
    except OSError:
        return ""
    for _nummer, d in kandidaten[:2]:
        text = read_text(d / "review.md")
        if text:
            return text
    return ""


def fragen_text(cfg, gate: dict | None = None, review_text: str | None = None) -> str:
    """`/fragen`: NAECHSTER SCHRITT + OFFENE FRAGEN AN DICH (mit Kennung, R13y).

    Steht hier nur noch als Eingang: die Ausgabe baut `hx/fragen.py` (dort liegen die
    Kennungen `A5`/`R209-1`/`M208-1`, der Antwortstatus und der Anhang fuer `/claude`).
    Der Import geschieht ABSICHTLICH erst im Aufruf: `fragen` liest `stand` (Kopf, Zahlen,
    Formate), und ein Import auf Modulebene waere ein Kreis.
    """
    from . import fragen as fragenmod
    return fragenmod.fragen_text(cfg, gate=gate, review_text=review_text)


def _kurz(text: str, grenze: int) -> str:
    txt = " ".join(str(text or "").split())
    return txt if len(txt) <= grenze else txt[:grenze - 3] + "..."
