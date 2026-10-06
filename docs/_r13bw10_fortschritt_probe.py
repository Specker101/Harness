"""R13bw-10 (Punkt 1) - Beleg am lebenden Repo (nur lesen).

Zeigt, was der Harness jetzt rechnet: die Pflichtzeilen je Batch (STATION/BEWEGUNG mit
Quelle), den Ankerkopf-Rueckfall, beide Zaehler und die zwei BILANZ-Zeilen.
"""

from __future__ import annotations

import pathlib
import sys
import time

HARNESS = pathlib.Path(r"g:\Harness\harness")
sys.path.insert(0, str(HARNESS))

from hx import stand                          # noqa: E402
from hx.config import load_config              # noqa: E402

ZIEL = pathlib.Path(r"g:\Harness\docs\_r13bw10_fortschritt_beleg.txt")
cfg = load_config()

zeilen = [f"R13bw-10 Fortschritts-Beleg {time.strftime('%Y-%m-%d %H:%M:%S')}", ""]
zeilen.append("Ankerkopf-Vermerke (stand._anker_bewegung): "
              + ", ".join(f"B{b}={'JA' if v else 'NEIN'}"
                          for b, v in sorted(stand._anker_bewegung(cfg).items())))
zeilen.append("")
zeilen.append("Je Batch: STATION / BEWEGUNG mit Quelle (neueste zuerst):")
for b in sorted(stand._anker_bewegung(cfg), reverse=True)[:6] + [277, 278]:
    s = stand.station_von_batch(cfg, b)
    w = stand.bewegung_von_batch(cfg, b, stand._anker_bewegung(cfg))
    zeilen.append(f"  B{b:<4} STATION={str(s['station']):<5} ({s['quelle'][:52] or '-'})")
    zeilen.append(f"        BEWEGUNG={str(w['bewegung']):<5} ({w['quelle'][:52] or '-'})")

z = stand.stillstand_zaehler(cfg)
f = stand.fortschritt_zaehler(cfg)
zeilen.append("")
zeilen.append(f"Stationszaehler (reine Information): zaehler={z['zaehler']} "
              f"B{z['von']}..B{z['bis']} schwelle={z['schwelle']} "
              f"erreicht={z['schwelle_erreicht']} luecke_ab={z['luecke_ab']}")
zeilen.append(f"Fortschrittszaehler (Hinweis):       zaehler={f['zaehler']} "
              f"B{f['von']}..B{f['bis']} schwelle={f['schwelle']} "
              f"erreicht={f['schwelle_erreicht']} luecke_ab={f['luecke_ab']} "
              f"fehlt_zeile={f['fehlt_zeile'] or '-'}")
zeilen.append("")
zeilen.append("BILANZ-Zeilen (stand.b_phase_zeile):")
zeilen += stand.b_phase_zeile(cfg, z)
txt = stand.fortschritt_hinweis_text(cfg, f)
zeilen.append("")
zeilen.append("Telegram-Hinweis: " + (repr(txt) if txt else "(keiner - Schwelle nicht erreicht)"))

text = "\n".join(zeilen) + "\n"
ZIEL.write_text(text, encoding="utf-8", newline="\n")
print(text)
