"""R13bi Nachtrag (nur lesend, schreibfrei im Decomp-Repo):

1. Der Speicher des **Python-Treibers** mit wachsendem `c_kopf._DECKUNG_CACHE`.
   Gemessen wird der RSS DIESES Prozesses vor und nach je einem Kopf
   (`c_kopf.deckung`, der Wortinterpreter) - zehn Koepfe, danach die
   Hochrechnung auf 115 (als Hochrechnung MARKIERT, nicht als Messung).
   `deckung()` schreibt nichts (`c_kopf.py:2586-2606`); die Belege schreibt erst
   `_vergl_alle` am Ende (`c_kopf.py:2652/2655`) - dieser Aufruf kommt hier nicht vor.

2. Der FRONT-RSS aus `docs/_r13bi_ram2.txt` (falls der Lauf inzwischen fertig ist).

Ergebnis: `docs/_r13bi_ram3.txt`.
"""
from __future__ import annotations

import io
import os
import pathlib
import sys
import time

DEC = pathlib.Path("g:/Silent Scope Decomp")
HARNESS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEC / "scripts"))
os.chdir(DEC)

import psutil                                                     # noqa: E402


def rss_mb() -> float:
    return psutil.Process().memory_info().rss / 1048576.0


def teil_a(zeilen: list[str], koepfe: int = 10) -> None:
    import c_kopf as K
    zeilen.append("### A) Python-Treiber: RSS mit wachsendem DECKUNG-Cache")
    zeilen.append("Aufruf: c_kopf.deckung(read_profile(prof_path(tag)), tag) "
                  "- Wortinterpreter, schreibfrei.")
    frei0 = psutil.virtual_memory().available / 1048576.0
    r0 = rss_mb()
    zeilen.append(f"  vor dem ersten Kopf: {r0:7.1f} MB RSS   frei {frei0:.0f} MB")
    t0 = time.time()
    for i in range(koepfe):
        f = K.PROFILES[i]
        tag = f()[0]
        prof = K.read_profile(K.prof_path(tag))
        K.deckung(prof, tag)
        zeilen.append(f"  Kopf {i + 1:2d} ({tag:>6s}): {rss_mb():7.1f} MB RSS"
                      f"   {time.time() - t0:6.1f} s")
    r1 = rss_mb()
    n = len(K.PROFILES)
    zeilen.append(f"  nach {koepfe} Koepfen:    {r1:7.1f} MB RSS  "
                  f"(+{r1 - r0:.1f} MB, {time.time() - t0:.1f} s)")
    zeilen.append(f"  Registry: {n} Koepfe -> lineare Hochrechnung "
                  f"{r0 + (r1 - r0) * n / koepfe:.0f} MB (HOCHRECHNUNG, keine Messung;")
    zeilen.append("  der Cache waechst je Kopf um die Zahl der angelaufenen PCs, "
                  "die Kopfgroessen sind nicht gleich)")
    zeilen.append(f"  frei danach: {psutil.virtual_memory().available / 1048576.0:.0f} MB")
    zeilen.append("")


def teil_b(zeilen: list[str]) -> None:
    p = HARNESS / "docs" / "_r13bi_ram2.txt"
    zeilen.append("### B) FRONT-Lauf (200M, --nativ-weiter): RSS-Spitze und Dauer")
    if not p.is_file():
        zeilen.append("  NOCH NICHT FERTIG: docs/_r13bi_ram2.txt fehlt (Lauf laeuft noch).")
        return
    txt = io.open(p, encoding="utf-8", errors="replace").read()
    for ln in txt.splitlines():
        if ln.startswith(("FRONT", "c_kopf", "Zusammen", "freier Speicher")):
            zeilen.append("  " + ln.strip())
    zeilen.append("")


def main() -> int:
    zeilen = ["R13bi Nachtrag - Treiber-RSS und FRONT-RSS (nur lesend)", ""]
    teil_b(zeilen)
    teil_a(zeilen, 10)
    text = "\n".join(zeilen) + "\n"
    (HARNESS / "docs" / "_r13bi_ram3.txt").write_text(text, encoding="utf-8", newline="\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
