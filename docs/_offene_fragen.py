#!/usr/bin/env python
"""Sammelt alle offenen Punkte aus den Review-Berichten des Harness.

Quellen: runs/b*/review*.md (Batch-Zuordnung aus harness-facts.md) und die
aelteren logs/review-*.md. Gezaehlt wird nur, was am ZEILENANFANG mit einem Marker
steht - dieselbe Regel wie /status und watch. Der Text laeuft bis zur Leerzeile
bzw. bis zum Schluss-Tag weiter, damit mehrzeilige Fragen vollstaendig sind.

  ENTSCHEIDUNG NOETIG:       echte Bremse im Dauerbetrieb
  OFFENE FRAGE:              unbeantwortet, bremst aber nicht
  WARTET AUF LIVE-AUFNAHME:  kann nur der Nutzer liefern

Aufruf aus g:\\Harness:   python docs\\_offene_fragen.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

HARNESS = Path(r"g:\Harness\harness")
RUNS = HARNESS / "runs"
LOGS = HARNESS / "logs"
OUT = Path(__file__).with_name("_offene_fragen.txt")

MARKER = (("entscheidung", "ENTSCHEIDUNG NOETIG:"),
          ("frage", "OFFENE FRAGE:"),
          ("live", "WARTET AUF LIVE-AUFNAHME:"))
ART = {"entscheidung": "ENTSCHEIDUNG NOETIG", "frage": "OFFENE FRAGE",
       "live": "WARTET AUF LIVE-AUFNAHME"}


def kopfzeile(s: str) -> str:
    return s.strip().lstrip("-*># ").strip().upper().replace("Ö", "OE") \
        .replace("Ä", "AE").replace("Ü", "UE")


def punkte_aus(text: str) -> list[tuple[str, str]]:
    """Marker am Zeilenanfang plus Fortsetzungszeilen bis Leerzeile/Schluss-Tag."""
    zeilen = (text or "").splitlines()
    treffer: list[tuple[str, str]] = []
    i = 0
    while i < len(zeilen):
        roh = zeilen[i]
        k = kopfzeile(roh)
        art = None
        for key, marker in MARKER:
            if k.startswith(marker):
                art = key
                teile = [(roh.split(":", 1)[1] if ":" in roh else "").strip()]
                break
        if art is None:
            i += 1
            continue
        j = i + 1
        while j < len(zeilen):
            nxt = zeilen[j].strip()
            if not nxt or nxt.startswith("<"):
                break
            if any(kopfzeile(nxt).startswith(m) for _k, m in MARKER):
                break
            teile.append(nxt)
            j += 1
        text_ganz = " ".join(t for t in teile if t).strip()
        if text_ganz:
            treffer.append((art, text_ganz))
        i = j
    return treffer


def bewerteter_batch(rd: Path, fallback: str) -> str:
    f = rd / "harness-facts.md"
    if f.is_file():
        for l in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if l.startswith("- Review: bewertet wird Batch "):
                return l[len("- Review: bewertet wird Batch "):].split(";")[0].strip()
    return fallback


def nummer(b: str) -> int:
    m = re.search(r"\d+", b or "")
    return int(m.group()) if m else 0


def main() -> int:
    eintraege: list[dict] = []
    dateien = sorted(RUNS.glob("b*/review*.md")) + sorted(RUNS.glob("_verworfen_b000/review*.md"))
    for f in dateien:
        b = bewerteter_batch(f.parent, f.parent.name)
        for art, text in punkte_aus(f.read_text(encoding="utf-8", errors="replace")):
            eintraege.append({"batch": b, "art": art, "text": text,
                              "quelle": f"{f.parent.name}/{f.name}"})
    log_dateien = sorted(LOGS.glob("review-*.md"))
    for f in log_dateien:
        for art, text in punkte_aus(f.read_text(encoding="utf-8", errors="replace")):
            eintraege.append({"batch": "?", "art": art, "text": text,
                              "quelle": f"logs/{f.name}"})

    for e in eintraege:
        e["schluessel"] = re.sub(r"\W+", " ", e["text"].lower()).strip()[:80]
    # Doppelte (Log-Kopie + runs-Datei) zusammenfassen: die runs-Datei gewinnt.
    best: dict[str, dict] = {}
    for e in eintraege:
        alt = best.get(e["schluessel"])
        if alt is None or (alt["batch"] == "?" and e["batch"] != "?"):
            best[e["schluessel"]] = e
    liste = sorted(best.values(), key=lambda e: (nummer(e["batch"]), e["art"]))

    puffer: list[str] = []
    puffer.append("# Offene Punkte aus den Review-Berichten des Harness")
    puffer.append("")
    puffer.append(f"Aus {len(dateien)} Review-Dateien unter runs/ und {len(log_dateien)} "
                  f"unter logs/; daraus {len(liste)} verschiedene Punkte.")
    puffer.append("")

    abschnitte = (("entscheidung", "## A) ENTSCHEIDUNG NOETIG - hier wartet der Harness auf dich",
                   "der Reviewer nennt ausdruecklich KEINE akute Entscheidung"),
                  ("frage", "## B) OFFENE FRAGEN (bremsen den Betrieb nicht)", ""),
                  ("live", "## C) WARTET AUF LIVE-AUFNAHME (nur du kannst das liefern)", ""))
    for key, titel, sondertitel in abschnitte:
        puffer.append(titel)
        puffer.append("")
        for e in liste:
            if e["art"] != key:
                continue
            if sondertitel and re.match(r"^keine\b", e["text"], re.IGNORECASE):
                puffer.append(f"- ({sondertitel}) {e['text']}")
            else:
                puffer.append(f"- {e['text']}")
            puffer.append(f"  _(Review von Batch {e['batch']}, {e['quelle']})_")
        puffer.append("")

    puffer.append("## D) Vom Reviewer als BEREITS ENTSCHIEDEN gefuehrt (Uebergabe-Text)")
    puffer.append("")
    try:
        st = json.loads((HARNESS / "state" / "run.json").read_text(encoding="utf-8"))
        ho = (st.get("reviewer") or {}).get("pending_handover") or {}
        puffer += [l.rstrip() for l in str(ho.get("text") or "").splitlines()]
    except Exception as exc:                                    # noqa: BLE001
        puffer.append(f"(Zustand nicht lesbar: {exc})")
    puffer.append("")

    OUT.write_text("\n".join(puffer) + "\n", encoding="utf-8")
    print(f"geschrieben: {OUT} ({len(liste)} Punkte)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
