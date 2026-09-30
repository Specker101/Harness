"""R13aw: den ersten Abschlussbericht der alten Batches nachtragen (Aussensicht B219, Befund 1).

Der Harness hat bis Batch 219 bei jeder Fortsetzung `runs/b<N>/antwort.md` ueberschrieben -
dort stand danach nur noch `NACHRUECKLISTE ERLEDIGT`, waehrend der Pflichtbericht (Abschnitte
1-6) nur noch im Mitschnitt lag. Dieses Skript holt ihn aus `runs/b<N>/stream.jsonl`
(erstes `result`-Ereignis) und legt ihn als **`runs/b<N>/antwort-bericht.md`** daneben.

**`antwort.md` wird NICHT angefasst** (Auftrag). Das Skript ist ein Probelauf, bis
`--schreiben` dabei steht.

Aufruf: python -u docs/_r13aw_nachtrag.py [BEREICH] [--schreiben]
        Bereich: 214-218 (Vorgabe) oder einzelne Nummern, z. B. 214,215,219
"""

from __future__ import annotations

import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
HARNESS = HIER.parent / "harness"
sys.path.insert(0, str(HARNESS))

from hx import streamjson, worker                                # noqa: E402
from hx.config import load_config                                # noqa: E402
from hx.util import write_text_atomic                            # noqa: E402

BEREICH = "214-218"


def batches(angabe: str) -> list[int]:
    aus: list[int] = []
    for teil in str(angabe).split(","):
        teil = teil.strip()
        if not teil:
            continue
        if "-" in teil:
            a, b = teil.split("-", 1)
            aus += list(range(int(a), int(b) + 1))
        else:
            aus.append(int(teil))
    return aus


def erster_bericht(pfad: Path) -> str:
    """Der erste nicht-leere `result`-Text des Mitschnitts ("" wenn keiner)."""
    if not pfad.is_file():
        return ""
    st = streamjson.StreamStats()
    for z in pfad.read_text(encoding="utf-8", errors="replace").splitlines():
        st.feed(z)
    teile = worker.antwort_teile(st)
    return teile[0] if teile else ""


def main() -> int:
    cfg = load_config()
    schreiben = "--schreiben" in sys.argv
    angabe = next((a for a in sys.argv[1:] if not a.startswith("--")), BEREICH)
    liste = batches(angabe)
    print(f"R13aw-Nachtrag: erster Abschlussbericht aus dem Mitschnitt "
          f"({'SCHREIBEN' if schreiben else 'Probelauf'}) - Batches {liste}")
    print()
    kopf = f"{'Batch':<7}{'Bericht':>9}{'antwort.md':>12}{'gleich?':>9}  Urteil"
    print(kopf)
    print("-" * (len(kopf) + 30))
    gelungen: list[int] = []
    for b in liste:
        rd = Path(cfg.sub("runs")) / f"b{b:03d}"
        stream = rd / "stream.jsonl"
        if not stream.is_file():
            print(f"{'b' + str(b):<7}{'-':>9}{'-':>12}{'-':>9}  kein Mitschnitt vorhanden")
            continue
        bericht = erster_bericht(stream)
        alt = rd / "antwort.md"
        alt_text = alt.read_text(encoding="utf-8", errors="replace").strip() \
            if alt.is_file() else ""
        gleich = bool(bericht) and bericht.strip() == alt_text
        if not bericht:
            urteil = "kein result-Text im Mitschnitt"
        elif gleich:
            urteil = "antwort.md ist schon der Bericht - nichts zu tun"
        else:
            urteil = f"Bericht nachtragen ({len(bericht)} Zeichen)"
        print(f"{'b' + str(b):<7}{(len(bericht) if bericht else 0):>9}"
              f"{len(alt_text):>12}{('ja' if gleich else 'nein'):>9}  {urteil}")
        if bericht and not gleich:
            gelungen.append(b)
            if schreiben:
                write_text_atomic(rd / "antwort-bericht.md", bericht.rstrip() + "\n")
    print()
    if schreiben:
        print(f"geschrieben: antwort-bericht.md fuer {len(gelungen)} Batch(es): "
              + (", ".join(f"B{b}" for b in gelungen) or "keinen"))
    else:
        print(f"Probelauf - mit --schreiben werden {len(gelungen)} Datei(en) angelegt: "
              + (", ".join(f"B{b}" for b in gelungen) or "keine"))
    print("antwort.md wurde NICHT angefasst.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
