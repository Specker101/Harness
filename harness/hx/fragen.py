"""Fragenregister (R13y): jede Frage an den Nutzer bekommt eine Kennung.

Auftrag (Nutzer, 2026-09-28): kein neuer Befehl, nur Ergaenzungen zu `/fragen` und zur
Aussensicht.

  * **Kennungen** - jede offene Frage an den Nutzer traegt eine eindeutige Kennung,
    sofern sie nicht schon eine hat:
        Ankerposten          `A5`        (aus dem Posten `(5)` im Ankerkopf)
        Reviewer-Fragen      `R209-1`    (Review, das Batch 209 bewertet hat)
        Aussensicht-Befunde  `M208-1`    (so vergibt die Aussensicht sie selbst)
  * **Antworten** - beginnt eine `/claude`-Nachricht mit einer solchen Kennung
    ("M208-1: ja", "A5 nein, erst spaeter"), haengt der Harness **Wortlaut der Frage und
    Empfehlung** an die Nachricht an und die Frage steht als "beantwortet, wartet auf
    Review" da. Mehrere Kennungen in einer Nachricht sind erlaubt. Eine unbekannte
    Kennung am Anfang wird gemeldet (mit den gueltigen) und die Nachricht NICHT
    eingereiht. Sobald das Review die Nachricht gelesen hat (`claude_queue_ids` des
    Gates) bzw. sie nach `inbox/done/` archiviert ist, verschwindet die Frage aus
    `/fragen`.

**Kein eigener Zustandsspeicher.** Alles wird aus den vorhandenen Belegen ABGELEITET:
Ankerkopf, letztes Review, Aussensicht-Register (`state/meta_befunde.json`) und die
Queue-Dateien (`inbox/claude/*.md`, `inbox/done/*.md`). So kann nichts auseinanderlaufen,
wenn ein Batch abbricht oder der Harness neu startet - die Kennung ist aus der Quelle
berechenbar, nicht gespeichert.

Der Wortlaut im Anhang ist wichtig: der Ankerposten `(5)` kann in einem spaeteren Batch
eine andere Frage tragen. Die Antwort wird deshalb **mit dem Text von jetzt** zusammen
zugestellt (der Reviewer sieht, worauf sich "ja" bezieht).
"""

from __future__ import annotations

import re
from pathlib import Path

from . import aussensicht, protocol, queue, stand
from .util import read_text

# Kennungen: A<n> | R<batch>-<n> | M<batch>-<n> (mit optionalem Teilbuchstaben a/b) und
# M<batch>-v<n> fuer einen VERWORFENEN Aussensicht-Befund (R13aa, Punkt 2).
# Gelesen wird ohne Ruecksicht auf Gross-/Kleinschreibung; ausgegeben wird die Form, die
# das Register benutzt (`A5`, `R209-1`, `M208-5a`, `M209-v1`) - der Nutzer tippt "a5"
# und meint A5.
_RE_ID = re.compile(r"(?P<id>A\d+|R\d{1,4}-\d+|M\d{1,4}-v?\d+(?:[a-z])?)\b",
                    re.IGNORECASE)

# Marker des Reviewers -> Beschriftung in der Anzeige (Reihenfolge = Dringlichkeit).
MARKER = (("entscheidung", "ENTSCHEIDUNG NOETIG (bremst)", "Reviewer (bremst)"),
          ("frage", "OFFENE FRAGE", "Reviewer-Frage"),
          ("live", "WARTET AUF LIVE-AUFNAHME", "Reviewer (Live-Aufnahme)"),
          ("entschieden", "ENTSCHIEDEN (Veto per /claude moeglich)",
           "Reviewer (entschieden)"))

# So viele Queue-Dateien werden fuer die Statusableitung hoechstens gelesen (die Namen
# beginnen mit dem Zeitstempel, sortiert wird also chronologisch).
MAX_QUEUE_DATEIEN = 300


# ------------------------------------------------------------------ Kennungen
def ids_am_anfang(text: str) -> list[str]:
    """Die Kennungen, mit denen eine Nachricht BEGINNT (in Reihenfolge, ohne Dubletten).

    Erlaubt sind Trenner zwischen mehreren Kennungen (`A5, M208-1: ja` oder
    `A5 M208-1 ja`). Sobald ein Wort kommt, das keine Kennung ist, endet die Suche -
    eine Kennung mitten im Text ist KEINE Antwort (Nutzerauftrag: "beginnt eine
    /claude-Nachricht mit einer solchen Kennung").
    """
    rest = (text or "").strip()
    gefunden: list[str] = []
    while rest:
        m = _RE_ID.match(rest)
        if not m:
            break
        kennung = kennung_normalisieren(m.group("id"))
        if kennung not in gefunden:
            gefunden.append(kennung)
        rest = rest[m.end():].lstrip(" \t,;:-\u2013\u2014")
    return gefunden


def kennung_normalisieren(kennung: str) -> str:
    """`a5` -> `A5`, `m208-5A` -> `M208-5a` (so steht es im Register)."""
    t = (kennung or "").strip()
    if not t:
        return ""
    art, rest = t[0].upper(), t[1:]
    return art + rest


# ------------------------------------------------------------------ Quellen
def bewerteter_batch(ordner: Path) -> int:
    """Welcher Batch wurde in diesem Review-Ordner bewertet?

    Der Harness legt das Review von Batch N in `runs/b<N+1>` (Zielordner = naechster
    Batch). Die Fakten-Datei im selben Ordner nennt es ausdruecklich ("- Review:
    bewertet wird Batch N") - sie ist die verlaessliche Quelle; fehlt sie, wird der
    Vorgaenger des Ordnernamens genommen.
    """
    text = read_text(Path(ordner) / "harness-facts.md")
    for zeile in (text or "").splitlines():
        if zeile.startswith("- Review: bewertet wird Batch "):
            kopf = zeile[len("- Review: bewertet wird Batch "):].split(";")[0].strip()
            if kopf.isdigit():
                return int(kopf)
    m = re.fullmatch(r"b(\d+)", Path(ordner).name)
    return max(0, int(m.group(1)) - 1) if m else 0


def neuestes_review(cfg, review_text: str | None = None) -> tuple[int, Path, str]:
    """(bewerteter Batch, Ordner, Text) des neuesten Reviews mit Inhalt.

    Mit `review_text` wird genau dieser Text benutzt (Batch 0 = unbekannt - dann heissen
    die Kennungen `R?-n`; geraten wird nicht).
    """
    if review_text is not None:
        return 0, Path(cfg.root) / "runs", review_text
    try:
        kandidaten = sorted(((int(p.name[1:]), p) for p in (Path(cfg.root) / "runs").iterdir()
                             if p.is_dir() and p.name.startswith("b")
                             and p.name[1:].isdigit()), reverse=True)
    except OSError:
        return 0, Path(cfg.root) / "runs", ""
    for nummer, d in kandidaten[:3]:
        text = read_text(d / "review.md")
        if text.strip():
            return bewerteter_batch(d), d, text
    return 0, Path(cfg.root) / "runs", ""


def fragen_posten(cfg, review_text: str | None = None, gate: dict | None = None) -> list[dict]:
    """Alle Fragen an den Nutzer mit Kennung und Status (Anker, Review, Aussensicht).

    Aufsteigend in der Reihenfolge Anker -> Review -> Aussensicht; jede Kennung genau
    einmal. `status` ist "offen", "beantwortet" (Nachricht liegt noch in der Queue) oder
    "aufgenommen" (das Review hat sie gelesen - dann steht sie nicht mehr in `/fragen`).
    """
    posten: list[dict] = []
    posten += _anker_posten(cfg)
    posten += _review_posten(cfg, review_text)
    posten += _aussensicht_posten(cfg)
    aufgenommen = _aufgenommene(cfg, gate)
    for p in posten:
        p["status"] = _status(cfg, p["id"], aufgenommen)
    return posten


def _anker_posten(cfg) -> list[dict]:
    kopf = stand.anchor_bloecke(cfg)
    offen, _geschlossen = stand.offene_entscheidungen(kopf.get("Offene Entscheidung", ""))
    out: list[dict] = []
    for nr, txt in offen:
        ziffern = "".join(c for c in str(nr) if c.isdigit())
        e = stand.entscheidbar(txt)
        out.append({"id": f"A{ziffern or '?'}", "art": "Ankerposten",
                    "label": "ANKERPOSTEN " + (nr or ""),
                    "quelle": "Ankerkopf r1b-workstream.md",
                    "bremst": False,
                    "frage": (e or {}).get("frage") or "",
                    "rohtext": " ".join(str(txt).split()),
                    "empfehlung": (e or {}).get("empfehlung") or "",
                    "bei_ja": (e or {}).get("bei_ja") or "",
                    "bei_nein": (e or {}).get("bei_nein") or "",
                    # R13z: A/B-Fragen haben ihre Folgen unter "bei A:"/"bei B:".
                    "bei_a": (e or {}).get("bei_a") or "",
                    "bei_b": (e or {}).get("bei_b") or "",
                    "entscheidbar": bool(e)})
    return out


def _review_posten(cfg, review_text: str | None = None) -> list[dict]:
    batch, ordner, text = neuestes_review(cfg, review_text)
    if not text:
        return []
    punkte = protocol.parse_offene_punkte(text)
    out: list[dict] = []
    n = 0
    for key, label, art in MARKER:
        for wert in punkte.get(key) or []:
            n += 1
            satz = " ".join(str(wert).split())
            out.append({"id": f"R{batch}-{n}" if batch else f"R?-{n}", "art": art,
                        "label": label,
                        "quelle": f"{ordner.name}/review.md"
                                  if ordner.name.startswith("b") else "letztes Review",
                        "bremst": key == "entscheidung",
                        "frage": satz, "rohtext": satz, "empfehlung": "",
                        "bei_ja": "", "bei_nein": "", "bei_a": "", "bei_b": "",
                        "entscheidbar": False,
                        "review_batch": batch, "marker": key})
    return out


def _aussensicht_posten(cfg) -> list[dict]:
    out: list[dict] = []
    try:
        rows = [b for b in aussensicht.offene(cfg)
                if str(b.get("empfaenger")) == "Nutzer"]
    except Exception:                                            # noqa: BLE001
        return []
    for b in rows:
        out.append({"id": str(b.get("id")),
                    "art": f"Aussensicht ({b.get('gewicht')})",
                    "label": f"AUSSENSICHT (Gewicht {b.get('gewicht')})",
                    "quelle": f"runs/meta-{int(b.get('batch') or 0):03d}.md",
                    "bremst": False,
                    "frage": str(b.get("aussage") or ""), "rohtext": "",
                    "empfehlung": str(b.get("empfehlung") or ""),
                    "bei_ja": "", "bei_nein": "", "bei_a": "", "bei_b": "",
                    "entscheidbar": False,
                    "beleg": str(b.get("beleg") or "")})
    out += _verworfene_posten(cfg)
    return out


def _verworfene_posten(cfg) -> list[dict]:
    """Befunde, die die **Beleg-Regel** verworfen hat - als "verworfen - pruefen?" (R13aa).

    Auftrag (Aussensicht-Nachbesserung aus `runs/meta-209.md`, Punkt 2): M209-4 wurde
    verworfen, obwohl die Zahlen aus den Eingabedaten stammten. Wegwerfen ist keine
    Loesung - die Frage "war die Regel zu streng?" gehoert an den Nutzer. Gezeigt werden
    die Verwerfungen des **neuesten Laufs** (hat er nichts verworfen, steht hier nichts);
    das Register behaelt alle (`aussensicht.verworfene`).
    """
    try:
        alle = aussensicht.verworfene(cfg)
    except Exception:                                            # noqa: BLE001
        return []
    if not alle:
        return []
    letzte = max(int(b.get("batch") or 0) for b in alle)
    try:
        laeufe = aussensicht.letzte_bericht_batches(cfg)
    except Exception:                                            # noqa: BLE001
        laeufe = []
    if laeufe and laeufe[-1] != letzte:
        return []                        # der neueste Lauf hat nichts verworfen
    out: list[dict] = []
    for b in alle:
        if int(b.get("batch") or 0) != letzte:
            continue
        beleg = str(b.get("beleg") or "").strip()
        out.append({"id": str(b.get("id")),
                    "art": f"Aussensicht (verworfen, Gewicht {b.get('gewicht')})",
                    "label": "AUSSENSICHT (verworfen - pruefen?)",
                    "quelle": f"runs/meta-{letzte:03d}.md (Rohantwort dort)",
                    "bremst": False,
                    "frage": str(b.get("aussage") or ""), "rohtext": "",
                    "empfehlung": str(b.get("empfehlung") or ""),
                    "bei_ja": "", "bei_nein": "", "bei_a": "", "bei_b": "",
                    "entscheidbar": False,
                    # Der Beleg ist der GRUND der Verwerfung - so kennzeichnen.
                    "beleg": (f"nicht anerkannt: {beleg[:150]}" if beleg else
                              "kein Beleg angegeben")})
    return out


# ------------------------------------------------------------------ Status
def _queue_dateien(cfg) -> list[Path]:
    """Die neuesten Queue-Dateien (claude offen + done), hoechstens MAX_QUEUE_DATEIEN."""
    root = Path(cfg.root)
    dateien: list[Path] = []
    for ordner in (root / "inbox" / "done", root / "inbox" / "claude"):
        try:
            dateien += [p for p in ordner.glob("*.md") if p.is_file()]
        except OSError:
            continue
    dateien.sort(key=lambda p: p.name)
    return dateien[-MAX_QUEUE_DATEIEN:]


def _aufgenommene(cfg, gate: dict | None) -> set[str]:
    """Kennungen, deren Nachricht das Review gelesen hat ("aufgenommen").

    Quellen: die `/claude`-Kennungen des offenen Gates (`claude_queue_ids` - setzt der
    Harness beim Review) und die archivierten Nachrichten in `inbox/done/`.
    """
    gelesen = {str(mid) for mid in ((gate or {}).get("claude_queue_ids") or [])}
    aufgenommen: set[str] = set()
    for p in _queue_dateien(cfg):
        if p.parent.name != "done" and p.stem not in gelesen:
            continue
        for kennung in ids_am_anfang(_nachrichtentext(p)):
            aufgenommen.add(kennung)
    return aufgenommen


def _nachrichtentext(p: Path) -> str:
    """Der Nutzertext einer Queue-Datei (ohne Frontmatter) - leer, wenn nicht lesbar."""
    try:
        raw = read_text(p)
    except OSError:
        return ""
    if raw.startswith("---"):
        teile = raw.split("---", 2)
        return teile[2] if len(teile) >= 3 else raw
    return raw


def _status(cfg, kennung: str, aufgenommen: set[str]) -> str:
    """Status EINER Kennung: offen | beantwortet | aufgenommen (abgeleitet, nicht gespeichert)."""
    if kennung in aufgenommen:
        return "aufgenommen"
    for p in _queue_dateien(cfg):
        if p.parent.name == "done":
            continue
        if kennung in ids_am_anfang(_nachrichtentext(p)):
            return "beantwortet"
    return "offen"


def status_zeilen(cfg, gate: dict | None = None) -> list[str]:
    """Kurze Statuszeilen fuer `/status` (je Status eine Zahl, dann die Kennungen)."""
    posten = fragen_posten(cfg, gate=gate)
    if not posten:
        return ["Fragen an dich: keine"]
    zaehler: dict[str, int] = {}
    for p in posten:
        zaehler[str(p.get("status"))] = zaehler.get(str(p.get("status")), 0) + 1
    teile = [f"{n} {k}" for k, n in sorted(zaehler.items())]
    offen_ids = [p["id"] for p in posten if p.get("status") == "offen"]
    ids = ", ".join(offen_ids) if offen_ids else "-"
    return ["Fragen an dich: " + ", ".join(teile) + f"  (offen: {ids})"]


# ------------------------------------------------------------------ Nachricht
def nachschlagen(cfg, kennung: str, gate: dict | None = None) -> dict | None:
    """Die Frage zu einer Kennung (oder None)."""
    ziel = str(kennung or "").strip().upper()
    for p in fragen_posten(cfg, gate=gate):
        if str(p.get("id")).upper() == ziel:
            return p
    # Ein geteilter Aussensicht-Befund (`M208-5a`/`M208-5b`) ist auch ohne Buchstaben
    # auffindbar - der Nutzer schreibt die Kennung selten genau ab.
    for p in fragen_posten(cfg, gate=gate):
        if str(p.get("id")).upper().startswith(ziel):
            return p
    return None


def anhang(posten: list[dict]) -> str:
    """Wortlaut + Empfehlung der beantworteten Fragen, als Anhang an die Nachricht."""
    if not posten:
        return ""
    bloecke: list[str] = ["[Antwort auf Frage(n) - Wortlaut zum Zeitpunkt der Antwort]"]
    for p in posten:
        bloecke.append(f"--- {p['id']} ({p.get('art')}) ---")
        bloecke.append("Frage: " + (p.get("frage") or p.get("rohtext") or "(kein Text)"))
        if p.get("empfehlung"):
            zeile = "Empfehlung: " + str(p["empfehlung"])
            folgen = _folgen(p)
            if folgen:
                zeile += " | " + " / ".join(folgen)
            bloecke.append(zeile)
        if p.get("beleg"):
            bloecke.append("Beleg: " + str(p["beleg"]))
        if p.get("quelle"):
            # R13aa: bei einem VERWORFENEN Befund zeigt die Quelle, wo der Wortlaut steht
            # (`runs/meta-209.md`) - ohne sie waere die Nachfrage nicht nachpruefbar.
            bloecke.append("Quelle: " + str(p["quelle"]))
    return "\n".join(bloecke)


def nachricht_vorbereiten(cfg, text: str, gate: dict | None = None) -> dict:
    """Eine `/claude`-Nachricht auf Antwortkennungen pruefen und ergaenzen (R13y).

    Rueckgabe: {"ok", "text", "bekannt": [ids], "unbekannt": [ids], "meldung": str}
    `ok = False` heisst: NICHT einreihen (unbekannte Kennung am Anfang) - die Meldung
    nennt die gueltigen Kennungen, damit der Nutzer nur die Ziffern tauschen muss.
    """
    kennungen = ids_am_anfang(text)
    if not kennungen:
        return {"ok": True, "text": text, "bekannt": [], "unbekannt": [], "meldung": ""}
    posten = fragen_posten(cfg, gate=gate)
    index = {str(p["id"]).upper(): p for p in posten}
    bekannt, unbekannt = [], []
    for k in kennungen:
        (bekannt if k.upper() in index else unbekannt).append(k)
    if unbekannt:
        gueltig = [p["id"] for p in posten if p.get("status") != "aufgenommen"]
        meldung = (f"Unbekannte Kennung: {', '.join(unbekannt)}. Die Nachricht wurde "
                   "NICHT in die Queue gelegt.")
        meldung += ("\nGueltige Kennungen: " + ", ".join(gueltig) if gueltig
                    else "\nEs ist gerade keine Frage offen (/fragen).")
        return {"ok": False, "text": text, "bekannt": [], "unbekannt": unbekannt,
                "meldung": meldung}
    zu = [index[k.upper()] for k in bekannt]
    meldung = ("In die Queue gelegt. Beantwortet: " + ", ".join(p["id"] for p in zu)
               + " - die Frage(n) stehen jetzt als \"beantwortet, wartet auf Review\".")
    return {"ok": True, "text": text + "\n\n" + anhang(zu), "bekannt": bekannt,
            "unbekannt": [], "meldung": meldung}


# ------------------------------------------------------------------ Ausgabe
def fragen_text(cfg, gate: dict | None = None, review_text: str | None = None) -> str:
    """`/fragen`: NAECHSTER SCHRITT, offene Fragen MIT KENNUNG, Review-Punkte, Auftrag.

    Was hier steht, ist aus den Belegdateien abgeleitet (siehe Modulkopf) - nichts wird
    gespeichert und nichts wird geschaetzt. `UNKLAR FORMULIERT` bleibt stehen, statt eine
    Frage still umzudeuten (Nutzerentscheid 2026-09-28).
    """
    kopf = stand.anchor_bloecke(cfg)
    batch = stand._batch_aus_anker(kopf)
    _offen, geschlossen = stand.offene_entscheidungen(kopf.get("Offene Entscheidung", ""))
    posten = fragen_posten(cfg, review_text=review_text, gate=gate)
    offen = [p for p in posten if p.get("status") == "offen"]
    beantwortet = [p for p in posten if p.get("status") == "beantwortet"]
    aufgenommen = [p for p in posten if p.get("status") == "aufgenommen"]

    zeilen = [f"FRAGEN AN DICH (Anker: BATCH {batch or '?'})"]
    if kopf.get("Naechster Schritt"):
        zeilen += ["", "NAECHSTER SCHRITT",
                   "  " + stand._kurz(kopf["Naechster Schritt"], 300)]
    zeilen += ["", "OFFENE FRAGEN AN DICH"]
    if not offen:
        zeilen.append("  keine - der Reviewer entscheidet den Regelfall selbst (R13f)")
    for p in offen:
        if p.get("frage"):
            zeilen.append(f"  {p['id']:<9} {str(p.get('label') or '').strip()}: "
                          + stand._kurz(p["frage"], 150))
            zeilen.append("            " + stand._kurz(_empfehlung_zeile(p), 165))
        else:
            zeilen.append(f"  {p['id']:<9} UNKLAR FORMULIERT: "
                          + stand._kurz(p.get("rohtext", ""), 145))
            zeilen.append("            (so nicht entscheidbar - bitte in /claude den "
                          "Wortlaut nennen)")
        if p.get("beleg"):
            zeilen.append("            Beleg: " + stand._kurz(str(p["beleg"]), 150))
        if p.get("quelle"):
            zeilen.append("            Quelle: " + stand._kurz(str(p["quelle"]), 150))
    if geschlossen:
        zeilen.append(f"  ({geschlossen} Posten hat der Reviewer selbst geschlossen - "
                      "Veto per /claude)")
    if beantwortet:
        zeilen += ["", "BEANTWORTET, WARTET AUF REVIEW"]
        for p in beantwortet:
            zeilen.append(f"  {p['id']:<9} "
                          + stand._kurz(p.get("frage") or p.get("rohtext"), 150))
    if aufgenommen:
        zeilen.append("  aufgenommen (nicht mehr offen): "
                      + ", ".join(p["id"] for p in aufgenommen))
    kandidaten = offen or beantwortet
    beispiel = (f'   (z. B. "/claude {kandidaten[0]["id"]} ja" - Kennung am Anfang, '
                "dann der Text)") if kandidaten else ""
    zeilen += ["", "ANTWORTEN: /claude <Kennung> <Text>" + beispiel]
    if gate and gate.get("instruction"):
        quelle = (gate.get("tools") or {}).get("source") or "reviewer"
        zeilen += ["", f"OFFENER AUFTRAG ({'VOM NUTZER' if quelle == 'user' else 'vom Reviewer'})",
                   "  " + stand._kurz(str(gate["instruction"]), 200)]
    return "\n".join(zeilen)


def _folgen(p: dict) -> list[str]:
    """Die Folgen einer Frage als `["bei ja: …", "bei nein: …"]`.

    R13z: eine Frage darf auch zwischen zwei Wegen waehlen (A/B) - dann stehen die Folgen
    unter `bei A:`/`bei B:`. Was dasteht, wird gezeigt; was fehlt, wird nicht erfunden.
    """
    out: list[str] = []
    for wort, schluessel in (("ja", "bei_ja"), ("nein", "bei_nein"),
                             ("A", "bei_a"), ("B", "bei_b")):
        if p.get(schluessel):
            out.append(f"bei {wort}: " + str(p[schluessel]))
    return out


def _empfehlung_zeile(p: dict) -> str:
    teile = []
    if p.get("empfehlung"):
        teile.append("Empfehlung: " + str(p["empfehlung"]))
    folgen = _folgen(p)
    if folgen:
        teile.append(" / ".join(folgen))
    if not teile:
        teile.append("keine Empfehlung angegeben")
    return " | ".join(teile)
