"""R13bp Probe (nur lesend): wie klassifiziert `stand.strang_von_batch` die letzten Batches?

Aufruf:  python -u docs/_r13bp_probe.py            (Ausgabe auf die Konsole)

Gibt je Batch die Klasse samt Quelle aus und zeigt, WELCHE Zeilen der Auftrag/das Review
zum Strang traegt (damit die Quelle nachpruefbar ist, nicht geraten).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "harness"))

from hx import stand                      # noqa: E402
from hx.config import load_config         # noqa: E402
from hx.util import read_text             # noqa: E402

cfg = load_config()


def zeilen_mit(pfad: Path, muster) -> list[str]:
    if not pfad.is_file():
        return []
    text = read_text(pfad) or ""
    return [z.strip()[:150] for z in text.splitlines() if muster.search(z)]


print("Batch | strang | quelle")
print("-" * 100)
for b in range(248, 258):
    s = stand.strang_von_batch(cfg, b)
    print(f"B{b} | {s.get('strang')!r:5} | {s.get('quelle')}")

print()
for b in (253, 254, 255, 256):
    for rolle in ("auftrag.md", "review.md"):
        p = Path(cfg.root) / "runs" / f"b{b:03d}" / rolle
        text, quelle = (stand.auftrags_text(cfg, b) if rolle == "auftrag.md"
                        else (stand.review_zu_batch(cfg, b), "review_zu_batch"))
        print(f"--- B{b} {rolle}  (vorhanden: {p.is_file()})")
        for muster, name in ((stand._RE_STRANG_PFLICHT, "STRANG:"),
                             (stand._RE_SOLL_STRANG, "SOLL-KOEPFE+Strang"),
                             (stand._RE_B_SCHRITT, "B-SCHRITT n/5"),
                             (stand._RE_B_SCHRITT_C, "B-SCHRITT kein B-Batch"),
                             (stand._RE_STRANG_ZEILE, "Zeile beginnt mit Strang")):
            treffer = zeilen_mit(p, muster)
            for t in treffer[:4]:
                print(f"    [{name}] {t}")
        if rolle == "auftrag.md":
            print(f"    auftrags_text-Quelle: {quelle}; "
                  f"_pflicht_strang={stand._pflicht_strang(text)!r}")
            m = stand._auftrag_strang(text, b) if text else ""
            print(f"    _auftrag_strang={m!r}")
        else:
            print(f"    review_zu_batch-Pfad: runs/b{b + 1:03d}/review.md ({len(text)} Zeichen)")
