"""Denkbloecke des DeepSeek-Workers lesen (R13r, Auftrag 2026-09-27).

Der Nutzer will mit `/thinking [N] [voll]` **live** mitlesen, was der laufende Batch
denkt: die letzten N Denkbloecke, je auf 200 Zeichen gekuerzt (wie `watch`), auf Wunsch
(`voll`) ungekuerzt.

Datenquelle ist der Worker-Mitschnitt `runs/b<N>/stream.jsonl` - die Zeile

    {"type":"assistant","message":{"content":[
        {"type":"thinking","thinking":"…","signature":"…"}]},"timestamp":"…"}

GEMESSEN an den echten Mitschnitten (2026-09-27): solche Zeilen gibt es in JEDEM Batch
(b180/b195 je ~16, b196 mehr); der Text ist meist 200-800 Zeichen, die JSON-Zeile
650-1900. Es gibt auch Bloecke mit LEEREM Text (nur `signature`) - die zaehlen nicht.
`thinking_delta` kommt NICHT vor, die zusammengesetzte Fassung ist die Quelle.

Warum ein TAIL-Leser und kein `read_text`: der Mitschnitt ist bis zu **32 MB** gross
(b180), und `/thinking` laeuft im TaktThread des Harness (`tick -> poll ->
handle_command`). Der Lauf soll nicht auf einen 32-MB-Lesevorgang warten. Gelesen wird
deshalb rueckwaerts in 256-KB-Bloecken, bis N Treffer da sind - mit festem Deckel
`MAX_SCAN_BYTES = 16 MB` (Nutzerentscheid: kein neuer Konfigurationsschluessel).
Alte, gepackte Mitschnitte (`stream.jsonl.zip`, R13p) werden streamweise gelesen.
"""

from __future__ import annotations

import json
import zipfile
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

BLOCK = 256 * 1024                 # Rueckwaerts-Schrittweite
MAX_SCAN_BYTES = 16 * 1024 * 1024  # fester Suchdeckel (Nutzerentscheid)
GRENZE_ZEICHEN = 200               # Standard-Kuerzung je Eintrag (wie watch.THINK_MAX)
STANDARD_N = 10
MAX_N = 50
VOLL_WORTE = ("voll", "full", "ganz", "ungekuerzt", "unverkuerzt")


# ------------------------------------------------------------------ Argumente
def argumente(rest: str) -> tuple[int, bool, str]:
    """`/thinking [N] [voll]` auswerten: (N, voll, Fehlertext).

    N wird auf 1..MAX_N geklemmt (Vorgabe STANDARD_N). Unbekannte Woerter sind ein
    Fehler - lieber die Nutzung zeigen als still etwas anderes tun.
    """
    n = STANDARD_N
    voll = False
    for wort in (rest or "").split():
        w = wort.strip().lower()
        if not w:
            continue
        if w in VOLL_WORTE:
            voll = True
        elif w.isdigit():
            n = min(MAX_N, max(1, int(w)))
        else:
            return n, voll, f"unbekanntes Argument {wort!r}"
    return n, voll, ""


# ------------------------------------------------------------- Zeile -> Denkblock
def _treffer_aus_zeile(zeile: str) -> dict | None:
    """Denkblock einer Mitschnittzeile - None, wenn keiner MIT TEXT darin steht."""
    if '"thinking"' not in zeile:
        return None
    try:
        obj = json.loads(zeile)
    except ValueError:
        return None
    if not isinstance(obj, dict) or obj.get("type") != "assistant":
        return None
    content = ((obj.get("message") or {}).get("content")) or []
    texte: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") not in ("thinking", "redacted_thinking"):
            continue
        text = str(block.get("thinking") or "")
        if text.strip():
            texte.append(text)
    if not texte:
        return None
    return {"roh": "\n".join(texte), "stamp": obj.get("timestamp")}


def _uhrzeit(stamp) -> tuple[str, float | None]:
    """`('15:42:11', epoch)` aus dem ISO-Zeitstempel (leer/None, wenn er fehlt)."""
    try:
        dt = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return "", None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    try:
        return dt.astimezone().strftime("%H:%M:%S"), dt.timestamp()
    except (OSError, OverflowError, ValueError):
        return "", None


def _kurz(text: str, grenze: int | None) -> tuple[str, bool]:
    """Leerraum normalisieren und auf `grenze` Zeichen kuerzen (None = ungekuerzt)."""
    t = " ".join(str(text or "").split())
    if not grenze or len(t) <= grenze:
        return t, False
    return t[:grenze], True


def _eintrag(roh: dict, grenze: int | None) -> dict:
    text, gekuerzt = _kurz(roh.get("roh") or "", grenze)
    zeit, epoch = _uhrzeit(roh.get("stamp"))
    zeichen = len(" ".join(str(roh.get("roh") or "").split()))
    return {"text": text, "gekuerzt": gekuerzt, "zeichen": zeichen,
            "zeit": zeit, "epoch": epoch, "stamp": roh.get("stamp")}


# ------------------------------------------------------------------ Tail-Leser
def _tail(datei: Path, n: int, deckel: int) -> tuple[list[dict], int, bool]:
    """Die letzten n Denkbloecke vom DATEIENDE her.

    Rueckgabe: (Treffer neueste-zuerst, gelesene Bytes, Deckel erreicht).
    """
    groesse = datei.stat().st_size
    untergrenze = max(0, groesse - max(0, deckel))
    treffer: list[dict] = []
    puffer = b""
    gelesen = 0
    pos = groesse
    with open(datei, "rb") as fh:
        while pos > untergrenze and len(treffer) < n:
            start = max(untergrenze, pos - BLOCK)
            fh.seek(start)
            stueck = fh.read(pos - start)
            gelesen += len(stueck)
            pos = start
            # Die ERSTE Teilzeile kann angeschnitten sein (der Block beginnt mitten in
            # einer Zeile) - sie wandert in den Puffer fuer den naechsten Schritt. Am
            # Dateianfang ist sie vollstaendig und wird dann mit ausgewertet.
            teile = (stueck + puffer).split(b"\n")
            puffer = teile[0]
            for roh in reversed(teile[1:]):
                if not roh:
                    continue
                t = _treffer_aus_zeile(roh.decode("utf-8", errors="replace"))
                if t:
                    treffer.append(t)
                    if len(treffer) >= n:
                        break
        if pos == 0 and len(treffer) < n and puffer.strip():
            # Der Puffer ist jetzt die erste Zeile der DATEI (nicht angeschnitten).
            t = _treffer_aus_zeile(puffer.decode("utf-8", errors="replace"))
            if t:
                treffer.append(t)
    # Deckel erreicht = wir haben die Dateispitze NICHT gesehen und wollen noch mehr.
    # (Nur `pos > untergrenze` waere falsch: das ist auch wahr, wenn wir genug haben.)
    return treffer, gelesen, bool(pos > 0 and len(treffer) < n)


def _aus_zip(datei: Path, n: int, deckel: int) -> tuple[list[dict], int, bool]:
    """Gepackter Altschnitt: streamweise vorwaerts lesen, nur die letzten n behalten.

    Rueckgabe wie `_tail`: NEUESTE ZUERST (der Aufrufer dreht einmal um).
    """
    letzte: deque[dict] = deque(maxlen=max(1, n))
    gelesen = 0
    deckel_erreicht = False
    with zipfile.ZipFile(datei) as zf:
        namen = zf.namelist()
        name = next((x for x in namen if x.endswith(".jsonl")), namen[0] if namen else "")
        if not name:
            return [], 0, False
        with zf.open(name) as fh:
            for roh in fh:
                gelesen += len(roh)
                t = _treffer_aus_zeile(roh.decode("utf-8", errors="replace"))
                if t:
                    letzte.append(t)
    return list(reversed(letzte)), gelesen, deckel_erreicht


# ------------------------------------------------------------------ Oeffentlich
def denkbloecke(pfad, n: int = STANDARD_N, grenze_zeichen: int | None = GRENZE_ZEICHEN,
                max_bytes: int = MAX_SCAN_BYTES) -> dict:
    """Die letzten `n` Denkbloecke aus einem Mitschnitt (Datei oder ZIP).

    `grenze_zeichen=None` = ungekuerzt (`/thinking … voll`).
    Das Ergebnis enthaelt die Eintraege in der Reihenfolge des Laufs (aelteste zuerst)
    und alle Zahlen, die die Anzeige braucht - so bleibt das Rendern testbar.
    """
    p = Path(pfad)
    ergebnis: dict = {"pfad": str(p), "n": int(n), "gefunden": 0, "eintraege": [],
                      "gelesen_bytes": 0, "groesse_bytes": 0, "deckel": False,
                      "grenze_zeichen": grenze_zeichen, "max_bytes": int(max_bytes),
                      "gepackt": p.suffix.lower() == ".zip", "fehler": ""}
    if not p.is_file():
        ergebnis["fehler"] = f"Datei fehlt: {p}"
        return ergebnis
    ergebnis["groesse_bytes"] = p.stat().st_size
    try:
        if ergebnis["gepackt"]:
            roh, gelesen, deckel = _aus_zip(p, n, max_bytes)
        else:
            roh, gelesen, deckel = _tail(p, n, max_bytes)
    except (OSError, zipfile.BadZipFile) as exc:
        ergebnis["fehler"] = f"{type(exc).__name__}: {str(exc)[:150]}"
        return ergebnis
    roh.reverse()                      # aelteste zuerst
    for i, e in enumerate(roh, start=1):
        eintrag = _eintrag(e, grenze_zeichen)
        eintrag["nr"] = i
        ergebnis["eintraege"].append(eintrag)
    ergebnis.update(gelesen_bytes=gelesen, gefunden=len(roh), deckel=bool(deckel))
    return ergebnis


def batch_aus_pfad(pfad) -> str:
    """`b197` aus `…/runs/b197/stream.jsonl` - sonst der Ordnername (z. B. env-proof)."""
    p = Path(str(pfad))
    eltern = p.parent.name
    if eltern.startswith("b") and eltern[1:].isdigit():
        return eltern
    return eltern or p.name


def mitschnitt_fuer_batch(cfg, batch) -> Path | None:
    """Mitschnitt zu einer Batch-Nummer (`b196/stream.jsonl`, auch als .zip)."""
    from . import retention
    try:
        nummer = int(batch)
    except (TypeError, ValueError):
        return None
    return retention.mitschnitt_vorhanden(
        Path(cfg.sub("runs")) / f"b{nummer}" / "stream.jsonl")


def neuester_mitschnitt(cfg) -> Path | None:
    """Mitschnitt des neuesten Batches - nur echte `b<N>`-Ordner.

    Wichtig: `runs/` enthaelt auch `env-proof` und `ghidra-smoke`; ohne die Zahlenpruefung
    wuerde die Namenssortierung einen dieser Nebenlaeufe als "neuester Batch" liefern.
    """
    try:
        kandidaten = []
        for d in Path(cfg.sub("runs")).iterdir():
            if d.is_dir() and d.name.startswith("b") and d.name[1:].isdigit():
                kandidaten.append((int(d.name[1:]), d))
    except OSError:
        return None
    from . import retention
    for _nummer, d in sorted(kandidaten, reverse=True):
        p = retention.mitschnitt_vorhanden(d / "stream.jsonl")
        if p:
            return p
    return None


# ------------------------------------------------------------------- Anzeige
def _mb(bytes_: int) -> str:
    mb = float(bytes_ or 0) / (1024 * 1024)
    return (f"{mb:.1f} MB" if mb < 10 else f"{mb:.0f} MB").replace(".", ",")


def beschreibe(ergebnis: dict, zusatz: str = "") -> str:
    """Telegram-tauglicher Text (Monospace) zu einem `denkbloecke`-Ergebnis."""
    batch = batch_aus_pfad(ergebnis.get("pfad") or "")
    grenze = ergebnis.get("grenze_zeichen")
    deckel_mb = _mb(int(ergebnis.get("max_bytes") or MAX_SCAN_BYTES))
    art = "ungekuerzt" if not grenze else f"je {int(grenze)} Zeichen"
    kopf = (f"DENKEN {batch} - letzte {ergebnis.get('n')} Denkbloecke ({art})")
    if zusatz:
        kopf += f"\n{zusatz}"
    eintraege = ergebnis.get("eintraege") or []
    if ergebnis.get("fehler"):
        return kopf + f"\nFEHLER: {ergebnis['fehler']}"
    if not eintraege:
        hinweis = ("kein Denkblock MIT TEXT gefunden"
                   + (f" (nur die letzten {deckel_mb} durchsucht)"
                      if ergebnis.get("deckel") else ""))
        return kopf + f"\n{hinweis}\nMitschnitt: {ergebnis.get('pfad')}"
    zeilen = [kopf]
    for e in eintraege:
        rest = (f" [+{e['zeichen'] - int(grenze)} Zeichen]"
                if e.get("gekuerzt") and grenze else "")
        kennung = f"{e.get('zeit') or '?'} ({e.get('zeichen')} Z.)"
        zeilen.append(f"{e.get('nr'):>2}. {kennung} {e.get('text')}{rest}")
    jung = next((e for e in reversed(eintraege) if e.get("epoch")), None)
    if jung:
        alter = max(0.0, datetime.now(timezone.utc).timestamp() - float(jung["epoch"]))
        if alter < 90:
            zeilen.append(f"juengster Eintrag: vor {alter:.0f} s")
        else:
            zeilen.append(f"juengster Eintrag: vor {alter / 60:.0f} min")
    if ergebnis.get("gefunden", 0) < ergebnis.get("n", 0):
        teil = f"nur {ergebnis['gefunden']} gefunden"
        if ergebnis.get("deckel"):
            teil += f" (nur die letzten {deckel_mb} durchsucht)"
        zeilen.append(teil)
    zeilen.append(f"Mitschnitt: {ergebnis.get('pfad')} "
                  f"({_mb(ergebnis.get('groesse_bytes'))}, gelesen "
                  f"{_mb(ergebnis.get('gelesen_bytes'))})")
    zeilen.append(f"Mehr: /thinking {min(MAX_N, ergebnis.get('n', 0) * 2)}   "
                  "Ungekuerzt: /thinking 10 voll")
    return "\n".join(zeilen)
