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

import re
from pathlib import Path

from . import protocol
from .util import read_json, read_text

# Bloecke des Ankerkopfs (Projektkonvention, AGENTS.md "Session-Kontinuitaet").
BLOECKE = ("Stand", "Fertig", "Naechster Schritt", "Offene Entscheidung", "Fallstricke")
STANDARD_FENSTER = 5
MAX_DOKUMENTE = 12

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
    """Offene Posten `[(nr, text)]` und Anzahl der vom Reviewer GESCHLOSSENen."""
    offen: list[tuple[str, str]] = []
    geschlossen = 0
    for nr, txt in _posten(text):
        kopf = txt.upper()
        if "GESCHLOSSEN" in kopf:
            geschlossen += 1
            continue
        offen.append((nr, txt))
    return offen, geschlossen


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
# Maschinengeschriebene Zeile (Festbreite): "C Koepfe           78 / 2903 / 0     OK"
_RE_PREFLIGHT_CKOPF = re.compile(r"^C Koepfe\s+(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\b")
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
    erg: dict = {"fenster": fenster, "n": len(fenster), "paket_e": pe,
                 "mittel_koepfe": 0.0, "mittel_insn": 0.0, "c_quelle": "",
                 "batches_koepfe": None, "batches_insn": None, "quelle": ""}
    if fenster:
        erg["letzter"] = fenster[0]
        erg["mittel_koepfe"] = sum(e["koepfe"] for e in fenster) / len(fenster)
        insn_werte = [e["insn"] for e in fenster if e.get("insn")]
        erg["mittel_insn"] = sum(insn_werte) / len(insn_werte) if insn_werte else 0.0
        erg["quelle"] = fenster[0].get("dokument", "")
        erg["c_quelle"] = fenster[0].get("c_quelle") or ""
    offen_koepfe = pe.get("paket_e_koepfe")
    offen_insn = pe.get("paket_e_insn")
    if offen_koepfe and erg["mittel_koepfe"] > 0:
        erg["batches_koepfe"] = offen_koepfe / erg["mittel_koepfe"]
    if offen_insn and erg["mittel_insn"] > 0:
        erg["batches_insn"] = offen_insn / erg["mittel_insn"]
    return erg


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


def ist_wert(text: str, etikett: str,
             muster: re.Pattern) -> tuple[int, tuple | None]:
    """(Zeilennr., Wert) der **letzten** Zeile mit diesem Etikett.

    Genommen wird die letzte solche Zeile (die Soll/Ist-Tafel steht hinter der
    Vorhersagetafel) und in ihr die letzte Zelle, die MIT dem Zahlenmuster BEGINNT -
    die Spalte "Abweichung/Quelle" am Zeilenende beginnt mit Text und zaehlt nicht.
    `(0, None)`, wenn es keine solche Zeile oder keinen solchen Wert gibt.
    """
    zeilen = ist_zellen(text, etikett)
    if not zeilen:
        return 0, None
    nummer, zellen = zeilen[-1]
    for i in range(len(zellen) - 1, 0, -1):
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


def preflight_c_koepfe(cfg, anzahl: int = 4) -> list[dict]:
    """Die Zeile `C Koepfe` der letzten `anzahl` Preflight-Dateien.

    Rueckgabe: `[{batch, datei, koepfe, faelle, abweichungen}]`, aufsteigend nach Batch.
    Fehlt die Zeile (vor dem C-Strang, B155..B197), fehlt der Eintrag - es wird nichts
    geschaetzt.
    """
    out: list[dict] = []
    for batch, pfad in preflight_dateien(cfg, anzahl):
        try:
            text = read_text(pfad)[:200000]
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
         Batches ganz ohne Preflight-Datei.

    `c_quelle` nennt je Eintrag, woher die C-Koepfe-Zahl kommt; `*_vorher` ist der Wert
    des letzten Eintrags MIT diesem Wert (nicht zwingend der direkte Vorgaenger - bei
    Paket E z. B. B206 -> B208, weil B207 die Zeile nicht fuehrt), `vorher_batch` dessen
    Nummer. Nichts wird fortgeschrieben oder geschaetzt; was fehlt, fehlt.
    """
    fenster = max(2, int(anzahl))
    dok = {e["batch"]: e for e in c_zahlen(cfg, fenster)}
    pre = {e["batch"]: e for e in preflight_c_koepfe(cfg, fenster + 2)}
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


# ------------------------------------------------------------ Durchsatz (R13s)
def durchsatz_alt(cfg, n: int = STANDARD_FENSTER) -> dict:
    """(entfernt) - frueher aus den C-Koepfe-Zeilen der Batch-Dokumente."""
    return {}


def durchsatz_zeilen(cfg, n: int = STANDARD_FENSTER) -> list[str]:
    """Die Zeilen des Durchsatz-Blocks (HYPOTHESIS klar gekennzeichnet)."""
    d = durchsatz(cfg, n)
    if not d["fenster"]:
        return ["  Durchsatz    : nicht ermittelbar (keine Bilanzdatei gefunden)"]
    letzter = d["letzter"]
    pe = d.get("paket_e") or {}
    reihe = ", ".join(f"{e['batch']}: {e['koepfe']:+d}" for e in d["fenster"])
    zeilen = [
        f"  Durchsatz    : Koepfe (R207 gebaut) letzter Batch {letzter['batch']}: "
        f"{letzter['r207_vorher']} -> {letzter['r207']} ({letzter['koepfe']:+d})",
        f"                 Mittel der letzten {d['n']}: +{d['mittel_koepfe']:.1f} Koepfe "
        f"je Batch   (Fenster: {reihe})",
    ]
    if d["mittel_insn"]:
        zeilen.append(f"                 Insn (nur wo belegt, Paket-E-Zeile): letzter "
                      f"Batch {letzter.get('insn')} / Mittel {d['mittel_insn']:.0f} Insn")
    else:
        zeilen.append("                 Insn: je Batch nicht durchgaengig belegt "
                      "(die Bilanzdatei fuehrt nur Koepfe)")
    if pe.get("paket_e_koepfe") is not None:
        zeilen.append(f"                 offen (Paket E, C-Arbeitsvorrat): "
                      f"{pe['paket_e_koepfe']} Koepfe / {pe.get('paket_e_insn', '?')} Insn"
                      + (f" (Bl {pe.get('paket_e_blatt')} / {pe.get('paket_e_insn_blatt')})"
                         if pe.get("paket_e_blatt") is not None else ""))
    if d["batches_koepfe"] or d["batches_insn"]:
        teile = []
        if d["batches_koepfe"]:
            teile.append(f"ca. {d['batches_koepfe']:.0f} Batches fuer die "
                         f"{pe.get('paket_e_koepfe')} offenen Koepfe")
        if d["batches_insn"]:
            teile.append(f"ca. {d['batches_insn']:.0f} Batches fuer "
                         f"{pe.get('paket_e_insn')} offene Insn")
        zeilen.append("                 HYPOTHESIS (Paket E, Arbeitsvorrat): noch "
                      + " / ".join(teile)
                      + f" (offen / Mittel der letzten {d['n']}, Rate unveraendert)")
    else:
        zeilen.append("                 HYPOTHESIS: keine Hochrechnung moeglich")
    zeilen += _c_gesamt_zeilen(cfg, d)
    zeilen += _relevanz_zeilen(cfg, d)
    zeilen.append(f"                 Quelle: analysis/{d['quelle']} (Zeile \"R207 "
                  "rueckwaerts\")"
                  + (f" + analysis/{pe['dokument']} (\"Paket E offen\", Ist-Spalte"
                     + (f", Zeile {pe['paket_e_zeile']}" if pe.get("paket_e_zeile") else "")
                     + ")" if pe.get("dokument") else "")
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
        if d.get("mittel_koepfe", 0) > 0:
            zeilen.append(f"                   -> ca. {offen / d['mittel_koepfe']:.0f} Batches bei "
                          f"+{d['mittel_koepfe']:.1f} Koepfen/Batch (Mittel der letzten "
                          f"{d['n']})")
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
    if d["mittel_koepfe"] > 0:
        zeilen.append(f"                   -> ca. {offen / d['mittel_koepfe']:.0f} "
                      f"Batches bei +{d['mittel_koepfe']:.1f} Koepfen/Batch "
                      f"(Mittel der letzten {d['n']})")
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
    mittel = d.get("mittel_koepfe") or 0.0
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
            hoch = (f" -> ca. {k['koepfe'] / mittel:.0f} Batches" if mittel > 0 else "")
            zeilen.append(f"                 {namen.get(schluessel, schluessel)}: "
                          f"{k['koepfe']:4d} Koepfe / {k['insn']:6d} Insn{hoch}")
        zeilen.append("                 \"nicht ausgefuehrt\" = in den VORHANDENEN Aufnahmen "
                      "nicht ausgefuehrt - NICHT \"unnoetig\" (die Aufnahmen decken nur "
                      "Boot + einen Teil von Level 1 ab)")
        if r.get("paket_e_huelle"):
            zeilen.append(f"                 (Paket-E-Huelle eigene Nachrechnung: "
                          f"{r['paket_e_huelle']} Koepfe, davon offen "
                          f"{r.get('paket_e_huelle_offen', '?')}; Projektzahl "
                          f"`c_kopf.py paket_e`: 274 / 38)")
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


def geplante_koepfe(instruktion: str) -> tuple[int, int, str]:
    """(Kopfzahl, Insn-Summe, Quelle) aus einer DS_INSTRUCTION.

    Heuristik, in `bedienung.md` dokumentiert: gezaehlt werden die **genannten
    Kopfadressen** (`0x80xxxxxx`) und die **Insn-Zahlen in Klammern** direkt dahinter.
    Genommen wird der Abschnitt ab der Ueberschrift `TEIL 3` (dort steht die Bau-Liste);
    fehlt sie, die ganze Instruktion - dann steht das in der Quelle.
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

    PLAN  = die in der Instruktion genannten Koepfe/Insn (`runs/b<N>/auftrag.md`)
    IST   = die Differenz der Zeile `R207 rueckwerts` (gebaute Koepfe) aus der
            kanonischen Bilanzdatei; Insn aus der Paket-E-Zeile, wo es sie gibt
    LAUFZEIT/ABBRUCH = `runs/b<N>/result.json` DIESES Laufs (Rueckfall: die Fakten-Datei
            im Ordner des naechsten Batches - s. `lauf_ist`)
    """
    d = durchsatz(cfg, n)
    runs = Path(cfg.sub("runs"))
    reihe = {e["batch"]: e for e in kernzahlen(cfg, MAX_DOKUMENTE)}
    out: list[dict] = []
    for e in d["fenster"]:
        batch = e["batch"]
        auftrag = read_text(runs / f"b{batch}" / "auftrag.md")
        geplant_k, geplant_i, quelle = geplante_koepfe(auftrag)
        lauf = lauf_ist(cfg, batch)
        dok = reihe.get(batch) or {}
        out.append({
            "batch": batch,
            "geplant_koepfe": geplant_k or None,
            "geplant_insn": geplant_i or None,
            "plan_quelle": quelle,
            "ist_koepfe": e["koepfe"],
            "ist_insn": e.get("insn"),
            "ist_faelle": dok.get("c_faelle"),
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
    """Tafel fuer den Review-Prompt: PLAN | IST | LAUFZEIT | ABBRUCH.

    Die Laufzeit kommt aus dem Ergebnis des jeweiligen Laufs (`runs/b<N>/result.json`);
    wird sie aus dem Rueckfall gelesen, steht ein `*` daran und die Herkunft darunter (R13x).
    """
    reihen = plan_ist(cfg, n)
    if not reihen:
        return "(keine PLAN/IST-Daten - keine Soll/Ist-Tafel in den Batch-Dokumenten)"
    zeilen = ["Batch | PLAN (Instruktion) | IST (verifiziert, C Koepfe) | "
              "Laufzeit (result.json) | Abbruch"]
    rueckfall: list[str] = []
    for r in reihen:
        plan = (f"{r['geplant_koepfe'] or '?'} Koepfe"
                + (f" / {r['geplant_insn']} Insn" if r["geplant_insn"] else ""))
        ist = (f"+{r['ist_koepfe']} Koepfe / +{r['ist_insn']} Insn"
               if r["ist_koepfe"] is not None else "nicht ermittelbar")
        marke = ""
        if r["dauer"] and r.get("dauer_quelle") != "result.json":
            marke = "*"
            rueckfall.append(f"B{r['batch']}: {r.get('dauer_quelle')}")
        zeilen.append(f"B{r['batch']} | {plan} | {ist} | {r['dauer'] or '?'}{marke} | "
                      f"{r['abbruch'] or '?'}")
    med = median([r["ist_koepfe"] for r in reihen])
    if med is not None:
        zeilen.append(f"MEDIAN der letzten {len(reihen)} Batches: {med:.0f} Koepfe "
                      f"(Ziel des naechsten Batches: hoechstens ca. {med * 1.3:.0f})")
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
