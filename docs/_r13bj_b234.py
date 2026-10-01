"""R13bj: laesst sich das Review zu B234 wiederherstellen? (nur lesend)

1. Den Handover-Text der ALTEN Reviewer-Session (die B234 bewertet hat) voll
   ausgeben - er liegt in `runs/b235/handover.jsonl`.
2. Pruefen, ob derselbe Text noch woanders steht (logs/, runs/).
3. `runs/b234/` und ein etwaiges `runs/b236/` auflisten (Ordner-Konvention).

Belege: `docs/_r13bj_handover.txt`, `docs/_r13bj_b234sichtung.txt`.
"""
from __future__ import annotations

import io
import json
import pathlib
import time

H = pathlib.Path("g:/Harness/harness")
D = pathlib.Path("g:/Harness/docs")


def handover_text() -> tuple[str, dict]:
    p = H / "runs" / "b235" / "handover.jsonl"
    with io.open(p, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            try:
                d = json.loads(ln)
            except ValueError:
                continue
            if d.get("type") == "result":
                return (d.get("result") or ""), d
    return "", {}


def main() -> int:
    txt, d = handover_text()
    kopf = ["R13bj - Handover-Text der B234-Reviewer-Session (Quelle: "
            "runs/b235/handover.jsonl)",
            f"session_id: {d.get('session_id')} | subtype: {d.get('subtype')} "
            f"| is_error: {d.get('is_error')} | num_turns: {d.get('num_turns')}",
            f"Laenge: {len(txt)} Zeichen", "", txt]
    (D / "_r13bj_handover.txt").write_text("\n".join(kopf) + "\n",
                                           encoding="utf-8", newline="\n")

    zeilen = ["R13bj - wo steht das Review zu B234 noch?", ""]
    nadel = "Der Fehler im Kopf 80009E3C"
    nadel2 = "Stand:** B234"
    for base in (H / "logs", H / "runs", H / "state"):
        for p in base.rglob("*"):
            if not p.is_file() or p.stat().st_size > 60 * 1024 * 1024:
                continue
            try:
                roh = p.read_bytes()
            except OSError:
                continue
            for marke in (nadel, nadel2):
                if marke.encode("utf-8") in roh:
                    zeilen.append(f"  TREFFER {marke!r}: {p.relative_to(H).as_posix()}"
                                  f"  ({len(roh)} B)")
    zeilen += ["", "## runs/b234 und runs/b236", ""]
    for name in ("b234", "b236"):
        p = H / "runs" / name
        if not p.is_dir():
            zeilen.append(f"  {name}: FEHLT")
            continue
        zeilen.append(f"  {name}/")
        for f in sorted(p.iterdir()):
            if f.is_file():
                zeilen.append(f"    {f.name:26} {f.stat().st_size:>9} B  "
                              f"{time.strftime('%d.%m %H:%M:%S', time.localtime(f.stat().st_mtime))}")
    (D / "_r13bj_b234sichtung.txt").write_text("\n".join(zeilen) + "\n",
                                               encoding="utf-8", newline="\n")
    print("\n".join(zeilen))
    print()
    print(kopf[1])
    print("---- Anfang des Handover-Textes ----")
    print(txt[:700])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
