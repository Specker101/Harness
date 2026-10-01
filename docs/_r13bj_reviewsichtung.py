"""R13bj: gibt es `logs/review-<ts>.md` je Review - und welches ist B234? (nur lesend)

Sucht in `logs/` nach den Volltext-Kopien der Reviews, prueft jedes gegen
Kennphrasen des B234-Reviews (aus dem Handover-Text) und schreibt den Befund
nach `docs/_r13bj_reviewsichtung.txt`.
"""
from __future__ import annotations

import io
import json
import pathlib
import time

H = pathlib.Path("g:/Harness/harness")
D = pathlib.Path("g:/Harness/docs")

# Kennphrasen: B234-Review (aus runs/b235/handover.jsonl) und B235-Review.
B234 = "2450 von 2582"
B234B = "Front: 200M Schranke, bei 900M Fehlerschleife 8001684C"
B235 = "ist gefunden und behoben"


def passt(txt: str, p: str) -> str:
    n = []
    if B234 in txt:
        n.append("B234-A")
    if B234B in txt:
        n.append("B234-B")
    if B235 in txt:
        n.append("B235")
    return ",".join(n) or "-"


def main() -> int:
    zeilen = ["R13bj - Review-Volltexte in logs/ (nur lesend)", ""]
    p = H / "state" / "run.json"
    d = json.loads(io.open(p, encoding="utf-8").read())
    zeilen.append("## state/run.json - Felder mit Review-Bezug")
    for k, v in d.items():
        s = json.dumps(v, ensure_ascii=False)
        if any(w in s for w in ("review", "Batch 234", "B234", "summary")):
            zeilen.append(f"  {k}: {s[:300]}")
    zeilen.append("")
    zeilen.append("## logs/review-*.md (ohne -prompt)")
    treffer = []
    for f in sorted((H / "logs").glob("review-*.md")):
        if "prompt" in f.name:
            continue
        txt = io.open(f, encoding="utf-8", errors="replace").read()
        marke = passt(txt, f.name)
        treffer.append((f, marke, len(txt)))
    for f, marke, ln in treffer[-25:]:
        zeilen.append(f"  {f.name:44} {ln:>7} B  {marke:>8}  "
                      f"{time.strftime('%d.%m %H:%M:%S', time.localtime(f.stat().st_mtime))}")
    zeilen.append("")
    treffer234 = [t for t in treffer if t[1].startswith("B234")]
    zeilen.append(f"B234-Volltexte gefunden: {len(treffer234)}")
    for f, marke, ln in treffer234:
        zeilen.append(f"  -> {f.name} ({ln} B, Marker {marke})")
    (D / "_r13bj_reviewsichtung.txt").write_text("\n".join(zeilen) + "\n",
                                                 encoding="utf-8", newline="\n")
    print("\n".join(zeilen))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
