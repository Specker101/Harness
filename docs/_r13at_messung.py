"""R13at: Runden der letzten Aussensicht-Laeufe messen (MESSUNG, nur lesend).

Der Auftrag nennt "meta-218 brauchte 41 von 50 Zuegen (82 %)". `41` ist `num_turns` aus
`runs/meta-218.json` - die CLI prueft `--max-turns` aber gegen die **Werkzeugrunden**
(R13ar, `docs/_r13ar_limit_probe_reviewer.txt`). Dieses Skript stellt beide Zahlen
nebeneinander und zieht das Sitzungs-Transcript als zweite Quelle heran.

Aufruf: python -u docs/_r13at_messung.py            (gibt aus)
        python -u docs/_r13at_messung.py schreiben  (schreibt docs/_r13at_messung.txt)
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
HARNESS = HIER.parent / "harness"
sys.path.insert(0, str(HARNESS))
from hx import streamjson                                     # noqa: E402

BATCHES = (208, 209, 210, 211, 212, 213, 214, 217, 218)
ZIEL = HIER / "_r13at_messung.txt"


def sitzung(jsonl: Path) -> str:
    for z in jsonl.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            e = json.loads(z)
        except ValueError:
            continue
        if e.get("type") == "system" and e.get("subtype") == "init":
            return str(e.get("session_id") or "")
    return ""


def transcript(sid: str) -> Path | None:
    if not sid:
        return None
    treffer = sorted((HARNESS / "cc-reviewer" / "projects").glob(f"*/{sid}.jsonl"))
    return treffer[0] if treffer else None


def mitschnitt_runden(p: Path) -> int | None:
    """Nur die Runden (fuer Einzelabfragen)."""
    return mitschnitt(p)[0]


def mitschnitt(p: Path):
    """(Runden, num_turns) aus einem Mitschnitt - oder (None, None)."""
    if not p.is_file():
        return None, None
    st = streamjson.StreamStats()
    for z in p.read_text(encoding="utf-8", errors="replace").splitlines():
        st.feed(z)
    return st.runden(), st.num_turns()


# Das Limit galt je Lauf: 30 von R13w bis R13aq (meta-217 brach damit bei 30 Runden ab),
# 50 ab dem R13aq-Commit (meta-218), 70 seit R13at.
def limit_je_lauf(b: int) -> int:
    if b <= 217:
        return 30
    if b == 218:
        return 50
    return 70


def bericht() -> None:
    print("R13at: Runden statt num_turns - die Zahlen der letzten Aussensicht-Laeufe")
    print()
    kopf = (f"{'Lauf':<10}{'rc':>4}{'num_turns':>11}{'Runden (jsonl)':>16}"
            f"{'Runden (Transcript)':>20}{'Aufrufe':>9}{'Limit':>7}  Anteil")
    print(kopf)
    print("-" * (len(kopf) + 12))
    for b in BATCHES:
        pj = HARNESS / "runs" / f"meta-{b}.json"
        d = json.loads(pj.read_text(encoding="utf-8")) if pj.is_file() else {}
        r_jsonl, num_turns = mitschnitt(HARNESS / "runs" / f"meta-{b}.jsonl")
        t = transcript(sitzung(HARNESS / "runs" / f"meta-{b}.jsonl"))
        if t is None:
            r_trans, aufrufe = None, None
        else:
            zeilen = t.read_text(encoding="utf-8", errors="replace").splitlines()
            r_trans = streamjson.runden_aus_zeilen(zeilen)
            st = streamjson.StreamStats()
            for z in zeilen:
                st.feed(z)
            aufrufe = len(st.tools)
        limit = limit_je_lauf(b)
        anteil = f"{100.0 * (r_jsonl or 0) / limit:.0f} %" if r_jsonl else "-"
        print(f"{'meta-' + str(b):<10}{str(d.get('rc')):>4}"
              f"{str(d.get('zuege') or num_turns):>11}{str(r_jsonl):>16}"
              f"{str(r_trans):>20}{str(aufrufe):>9}{limit:>7}  {anteil}")
    print()
    print("Lesehilfe: `num_turns` ist das Feld `zuege` aus runs/meta-<N>.json (= das")
    print("Ergebnis-Feld `num_turns` der CLI, Werkzeugergebnisse + 1). Die CLI prueft")
    print("`--max-turns` gegen die WERKZEUGRUNDEN - beide Spalten davor. Limit war 30")
    print("(R13w..R13aq) und 50 (ab R13aq); seit R13at steht es auf 70.")


def main() -> int:
    if "schreiben" in sys.argv:
        puffer = io.StringIO()
        with contextlib.redirect_stdout(puffer):
            bericht()
        text = puffer.getvalue()
        ZIEL.write_text(text, encoding="utf-8", newline="\n")
        print(f"geschrieben: {ZIEL.name} ({len(text)} Zeichen, UTF-8)")
        return 0
    bericht()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
