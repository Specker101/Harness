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
from .util import read_text

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
_EMPFEHLUNG = re.compile(r"(?:Vorschlag|Empfehlung)\s*:?\s*\**\s*(ja|nein|kein\w*)\b",
                         re.IGNORECASE)
_JA_NEIN = re.compile(r"^(?:soll|sollen|ist|sind|bleibt|bleiben|wird|werden|kann|darf|"
                      r"muessen|muss|gibt)\b", re.IGNORECASE)
_BEI = re.compile(r"bei\s+(ja|nein)\s*[:=]\s*([^|;.\n]+)", re.IGNORECASE)


def entscheidbar(text: str) -> dict | None:
    """Versucht aus einem Ankerposten EINE entscheidbare Zeile zu machen.

    Gebraucht werden drei Teile: eine **Ja/Nein-Frage**, eine **Empfehlung** und die
    **Folgen** (bei ja / bei nein). Nur wenn die Prosa sie hergibt, ist der Posten
    entscheidbar - sonst meldet die Anzeige "UNKLAR FORMULIERT" (Nutzerentscheid
    2026-09-28: nichts still umdeuten).

    Die Frage wird NICHT am Zeilenanfang gesucht: die Ankerposten haben oft eine lange
    Vorrede ("die Fallfabrik erreicht … NICHT - **soll** `prof` … fahren?"). Gesucht
    wird also der letzte Satz, der mit einem Ja/Nein-Wort beginnt und mit `?` endet.
    """
    txt = " ".join(str(text or "").split())
    if not txt:
        return None
    treffer = re.search(r"(?P<frage>(?:soll|sollen|ist|sind|bleibt|bleiben|wird|werden|"
                        r"kann|kannst|darf|muss|muessen|gibt)\b[^?]*\?)", txt,
                        re.IGNORECASE)
    if not treffer:
        return None
    frage = treffer.group("frage").strip(" *.")
    # Der Vorschlag steht meist in Klammern IN der Frage - er gehoert zur Empfehlung.
    # Achtung: das Fragezeichen steht HINTER der Klammer und geht beim Abschneiden
    # verloren - es wird deshalb wieder angehaengt.
    frage = re.split(r"\((?:Vorschlag|Empfehlung)", frage)[0].strip(" *.,;")
    if not frage:
        return None
    if not frage.endswith("?"):
        frage += "?"
    m = _EMPFEHLUNG.search(txt)
    if not m:
        return None
    folgen = {k.lower(): " ".join(v.split()) for k, v in _BEI.findall(txt)}
    return {"frage": frage,
            "empfehlung": m.group(1).lower(),
            "bei_ja": folgen.get("ja", ""),
            "bei_nein": folgen.get("nein", "")}


# ------------------------------------------------------------ Batch-Dokumente
_RE_INV = re.compile(r"(\d+)\s*Koepfe\s*/\s*(\d+)\s*Insn\s*\**\s*im Programm-Inventar")
_RE_BAU = re.compile(r"(\d+)\s*Koepfe\s*/\s*(\d+)\s*Insn\s*\**\s*in der\s*Bau-Liste")
_RE_OFFEN = re.compile(r"OFFEN:?\s*\**\s*(\d+)\s*Koepfe\s*/\s*\**\s*(\d+)\s*Insn")
_RE_BLATT = re.compile(r"(\d+)\s*Koepfe\s*/\s*\**\s*(\d+)\s*Insn\s*\**\s*keinen offenen Ruf")
# Tabellenzeile "| **C Koepfe** | 73 / 1752 / 0 | **78 / 1872 / 0** | …"
# ACHTUNG: die drei Zahlen sind Koepfe / FAELLE / Abweichungen (78*24 = 1872) - die
# zweite Zahl ist also NICHT die Insn-Zahl. Die Insn je Batch kommen aus der
# Paket-E-Zeile (dort steht "Insn" wirklich).
_RE_CKOPF = re.compile(r"C Koepfe\**\s*\|\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\s*\|\s*\**\s*"
                       r"(\d+)\s*/\s*(\d+)\s*/\s*(\d+)")
# Tabellenzeile "| Paket E offen | 43 Koepfe / 3025 Insn (Bl 20 / 1434) | **38 / 2674 (Bl 15 / 1083)** |"
_RE_PAKET_TAB = re.compile(
    r"Paket E offen\s*\|\s*(\d+)\s*(?:Koepfe)?\s*/?\s*(\d+)\s*Insn\s*"
    r"\(Bl\s*(\d+)\s*/\s*(\d+)\)\s*\|\s*\**\s*(\d+)\s*/\s*(\d+)\s*"
    r"\(Bl\s*(\d+)\s*/\s*(\d+)\)")
# Prosafassung (steht so in den Instruktionen): "Paket E offen 43 Koepfe / 3025 Insn (Blaetter 20/1434)"
_RE_PAKET_TEXT = re.compile(r"Paket E offen\s*(\d+)\s*Koepfe?\s*/\s*(\d+)\s*Insn\s*"
                            r"\(Blaetter\s*(\d+)\s*/\s*(\d+)\)", re.IGNORECASE)

_DOKU = re.compile(r"port-batch(\d+)")
_MDIR = re.compile(r"_m(\d+)$")
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
    je_dokument = {e["batch"]: e for e in c_zahlen(cfg, MAX_DOKUMENTE)}
    fenster: list[dict] = []
    for eintrag in reversed(reihe):                    # neueste zuerst
        e = dict(eintrag)
        d = je_dokument.get(e["batch"]) or {}
        if "paket_e_insn" in d and "paket_e_insn_vorher" in d:
            e["insn"] = d["paket_e_insn_vorher"] - d["paket_e_insn"]
        else:
            e["insn"] = None
        e["c_koepfe"] = d.get("c_koepfe")
        e["c_faelle"] = d.get("c_faelle")
        e["c_abweichungen"] = d.get("c_abweichungen")
        fenster.append(e)
        if len(fenster) >= n:
            break
    pe: dict = {}
    for eintrag in reversed(c_zahlen(cfg, MAX_DOKUMENTE)):
        if eintrag.get("paket_e_koepfe") is not None:
            pe = eintrag
            break
    erg: dict = {"fenster": fenster, "n": len(fenster), "paket_e": pe,
                 "mittel_koepfe": 0.0, "mittel_insn": 0.0,
                 "batches_koepfe": None, "batches_insn": None, "quelle": ""}
    if fenster:
        erg["letzter"] = fenster[0]
        erg["mittel_koepfe"] = sum(e["koepfe"] for e in fenster) / len(fenster)
        insn_werte = [e["insn"] for e in fenster if e.get("insn")]
        erg["mittel_insn"] = sum(insn_werte) / len(insn_werte) if insn_werte else 0.0
        erg["quelle"] = fenster[0].get("dokument", "")
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


def _zahlen_aus_text(text: str) -> dict:
    """Die Bilanzzahlen EINES Dokuments (fehlende Schluessel bleiben weg)."""
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
    m = _RE_CKOPF.search(text)
    if m:
        out["c_koepfe_vorher"] = int(m.group(1))
        out["c_faelle_vorher"] = int(m.group(2))
        out["c_koepfe"] = int(m.group(4))
        out["c_faelle"] = int(m.group(5))
        out["c_abweichungen"] = int(m.group(6))
    m = _RE_PAKET_TAB.search(text)
    if m:
        out["paket_e_koepfe_vorher"] = int(m.group(1))
        out["paket_e_insn_vorher"] = int(m.group(2))
        out["paket_e_blatt_vorher"] = int(m.group(3))
        out["paket_e_insn_blatt_vorher"] = int(m.group(4))
        out["paket_e_koepfe"] = int(m.group(5))
        out["paket_e_insn"] = int(m.group(6))
        out["paket_e_blatt"] = int(m.group(7))
        out["paket_e_insn_blatt"] = int(m.group(8))
    else:
        m = _RE_PAKET_TEXT.search(text)
        if m:
            out["paket_e_koepfe"] = int(m.group(1))
            out["paket_e_insn"] = int(m.group(2))
            out["paket_e_blatt"] = int(m.group(3))
            out["paket_e_insn_blatt"] = int(m.group(4))
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


def stand_zahlen(cfg) -> dict:
    """Die neuesten Zahlen (neuestes Dokument, fehlende Schluessel aus dem Ankerkopf)."""
    reihe = c_zahlen(cfg, 4)
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
                         f"{pe.get('paket_e_koepfe')} offenen Paket-E-Koepfe")
        if d["batches_insn"]:
            teile.append(f"ca. {d['batches_insn']:.0f} Batches fuer "
                         f"{pe.get('paket_e_insn')} offene Insn")
        zeilen.append("                 HYPOTHESIS: noch " + " / ".join(teile)
                      + f" (offen / Mittel der letzten {d['n']}, Rate unveraendert)")
    else:
        zeilen.append("                 HYPOTHESIS: keine Hochrechnung moeglich")
    zeilen.append(f"                 Quelle: analysis/{d['quelle']} (Zeile \"R207 "
                  "rueckwaerts\")"
                  + (f" + analysis/{pe['dokument']} (\"Paket E offen\")"
                     if pe.get("dokument") else ""))
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
    LAUFZEIT/ABBRUCH = `runs/b<N>/harness-facts.md`
    """
    d = durchsatz(cfg, n)
    runs = Path(cfg.sub("runs"))
    reihe = {e["batch"]: e for e in c_zahlen(cfg, MAX_DOKUMENTE)}
    out: list[dict] = []
    for e in d["fenster"]:
        batch = e["batch"]
        auftrag = read_text(runs / f"b{batch}" / "auftrag.md")
        geplant_k, geplant_i, quelle = geplante_koepfe(auftrag)
        facts = read_text(runs / f"b{batch}" / "harness-facts.md")
        dauer = _RE_DAUER.search(facts)
        abbruch = _RE_ABBRUCH.search(facts)
        dok = reihe.get(batch) or {}
        out.append({
            "batch": batch,
            "geplant_koepfe": geplant_k or None,
            "geplant_insn": geplant_i or None,
            "plan_quelle": quelle,
            "ist_koepfe": e["koepfe"],
            "ist_insn": e.get("insn"),
            "ist_faelle": dok.get("c_faelle"),
            "dauer": dauer_text(dauer),
            "abbruch": " ".join(abbruch.group(1).split()) if abbruch else "",
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
    """Tafel fuer den Review-Prompt: PLAN | IST | LAUFZEIT | ABBRUCH."""
    reihen = plan_ist(cfg, n)
    if not reihen:
        return "(keine PLAN/IST-Daten - keine Soll/Ist-Tafel in den Batch-Dokumenten)"
    zeilen = ["Batch | PLAN (Instruktion) | IST (verifiziert, C Koepfe) | Laufzeit | Abbruch"]
    for r in reihen:
        plan = (f"{r['geplant_koepfe'] or '?'} Koepfe"
                + (f" / {r['geplant_insn']} Insn" if r["geplant_insn"] else ""))
        ist = (f"+{r['ist_koepfe']} Koepfe / +{r['ist_insn']} Insn"
               if r["ist_koepfe"] is not None else "nicht ermittelbar")
        zeilen.append(f"B{r['batch']} | {plan} | {ist} | {r['dauer'] or '?'} | "
                      f"{r['abbruch'] or '?'}")
    med = median([r["ist_koepfe"] for r in reihen])
    if med is not None:
        zeilen.append(f"MEDIAN der letzten {len(reihen)} Batches: {med:.0f} Koepfe "
                      f"(Ziel des naechsten Batches: hoechstens ca. {med * 1.3:.0f})")
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
    """`/fragen`: NAECHSTER SCHRITT + OFFENE FRAGEN AN DICH (entscheidbar)."""
    kopf = anchor_bloecke(cfg)
    batch = _batch_aus_anker(kopf)
    zeilen = [f"FRAGEN AN DICH (Anker: BATCH {batch or '?'})"]
    if kopf.get("Naechster Schritt"):
        zeilen.append("")
        zeilen.append("NAECHSTER SCHRITT")
        zeilen.append("  " + _kurz(kopf["Naechster Schritt"], 300))
    offen, geschlossen = offene_entscheidungen(kopf.get("Offene Entscheidung", ""))
    zeilen.append("")
    zeilen.append("OFFENE FRAGEN AN DICH")
    if not offen:
        zeilen.append("  keine - der Reviewer entscheidet den Regelfall selbst (R13f)")
    for nr, txt in offen:
        e = entscheidbar(txt)
        if not e:
            zeilen.append(f"  {nr or '-'} UNKLAR FORMULIERT: {_kurz(txt, 160)}")
            continue
        zeilen.append(f"  {nr or '-'} {e['frage']}")
        folgen = f"bei ja: {e['bei_ja'] or '-'} / bei nein: {e['bei_nein'] or '-'}"
        zeilen.append(f"      Empfehlung: {e['empfehlung']} | {_kurz(folgen, 160)}")
    if geschlossen:
        zeilen.append(f"  ({geschlossen} Posten hat der Reviewer selbst geschlossen - "
                      "Veto per /claude)")
    review = _letztes_review(cfg) if review_text is None else review_text
    punkte = protocol.parse_offene_punkte(review)
    zeilen.append("")
    zeilen.append("AUS DEM LETZTEN REVIEW")
    kurz = protocol.offene_punkte_kurz(punkte, breite=170)
    zeilen += ["  " + z for z in kurz] if kurz else ["  keine Marker"]
    if len(punkte.get("entschieden") or []) > 0 and not any(
            z.startswith("Entschieden") for z in kurz):
        zeilen.append(f"  {len(punkte['entschieden'])} eigene Entscheidung(en) des "
                      "Reviewers")
    if gate and gate.get("instruction"):
        quelle = (gate.get("tools") or {}).get("source") or "reviewer"
        zeilen.append("")
        zeilen.append(f"OFFENER AUFTRAG ({'VOM NUTZER' if quelle == 'user' else 'vom Reviewer'})")
        zeilen.append("  " + _kurz(str(gate["instruction"]), 200))
    return "\n".join(zeilen)


def _kurz(text: str, grenze: int) -> str:
    txt = " ".join(str(text or "").split())
    return txt if len(txt) <= grenze else txt[:grenze - 3] + "..."
