"""R13bw-9 Punkt 2 (nur lesen): was sagt die Strang-Klassifikation je Batch?

Zeigt fuer B245..B260 die Klassifikation (`stand.strang_von_batch`), den heutigen
`letzter_c_batch` aus `stand.durchsatz` (Zeilenreihe) und - zum Vergleich - den Wert aus
einem rueckwaerts laufenden Durchgang ueber ALLE Batch-Ordner.
"""

from __future__ import annotations

import pathlib
import sys
import time

HARNESS = pathlib.Path(r"g:\Harness\harness")
sys.path.insert(0, str(HARNESS))

from hx import stand                          # noqa: E402
from hx.config import load_config              # noqa: E402

ZIEL = pathlib.Path(r"g:\Harness\docs\_r13bw9_strang_beleg.txt")
cfg = load_config()

zeilen = [f"R13bw-9 Strang-Beleg {time.strftime('%Y-%m-%d %H:%M:%S')}", ""]
zeilen.append("Klassifikation je Batch (strang_von_batch):")
for b in range(245, 261):
    d = stand.strang_von_batch(cfg, b)
    zeilen.append(f"  B{b:<4} strang={str(d.get('strang') or '?'):<2} quelle={str(d.get('quelle'))[:70]}")

d = stand.durchsatz(cfg)
zeilen.append("")
zeilen.append(f"durchsatz()['letzter_c_batch'] (neue Quelle: strang_lauf) = {d.get('letzter_c_batch')}")
zeilen.append(f"durchsatz()['lauf_b']                                  = {d.get('lauf_b')}")
zeilen.append(f"durchsatz()['anteil_quelle']                           = {d.get('anteil_quelle')}")

# Der ALTE Weg, auf DENSELBEN Daten nachgerechnet (er steht nicht mehr im Code): die
# Zaehlschleife lief ueber `trend['reihe']` - nur TREND_FENSTER+1 Zeilen. Damit ist die
# Vorher-Zahl nicht erinnert, sondern reproduzierbar.
trend = stand.c_trend(cfg, stand.TREND_FENSTER)
arten = [(int(e["batch"]), (stand.strang_von_batch(cfg, int(e["batch"])).get("strang") or "?"))
         for e in (trend.get("reihe") or [])]
lauf_b_alt, letzter_c_alt = 0, 0
for b, a in reversed(arten):
    if a == "B":
        lauf_b_alt += 1
        continue
    if a == "C":
        letzter_c_alt = b
    break
zeilen.append("")
zeilen.append(f"ALTER Weg auf denselben Daten (Zeilenreihe, {len(arten)} Zeilen): "
              f"letzter C-Batch = B{letzter_c_alt}, B-Lauf = {lauf_b_alt}")
zeilen.append("  -> genau die zwei Zahlen, die als 'ab B1; letzter C-Batch B0' in der "
              "Bilanz standen (Nutzerbefund Punkt 2)")

# Gegenprobe: rueckwaerts ueber alle Batch-Ordner klassifizieren.
nummern = sorted((int(p.name[1:]) for p in (pathlib.Path(cfg.root) / "runs").iterdir()
                  if p.is_dir() and p.name.startswith("b") and p.name[1:].isdigit()),
                 reverse=True)
lauf_b, letzter_c, grenze, gesehen = 0, 0, None, []
for n in nummern:
    art = stand.strang_von_batch(cfg, n).get("strang") or "?"
    gesehen.append((n, art))
    if art == "B":
        lauf_b += 1
        continue
    if art == "C":
        letzter_c = n
    else:
        grenze = n
    break
zeilen.append("")
zeilen.append("Gegenprobe (rueckwaerts ueber alle Ordner):")
zeilen.append(f"  letzter C-Batch = B{letzter_c}, B-Lauf am Ende = {lauf_b}, "
              f"Grenze/Stop bei B{grenze} (unbekannt)")
zeilen.append("  erste 30 gesehen: " + ", ".join(f"B{n}:{a}" for n, a in gesehen[:30]))

text = "\n".join(zeilen) + "\n"
ZIEL.write_text(text, encoding="utf-8", newline="\n")
print(text)
