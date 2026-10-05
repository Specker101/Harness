"""R13bw-8 Punkt 3 (nur lesen): feuert der "Hybrid-Lauf haengt"-Alarm an der Schranke?

Zeigt die A4-Reihe (Halt-Art, Schritte, Halt-PC) und den Alarm-Text, den der Harness
daraus baut.
"""

from __future__ import annotations

import pathlib
import sys
import time

HARNESS = pathlib.Path(r"g:\Harness\harness")
sys.path.insert(0, str(HARNESS))

from hx import aussensicht, stand                          # noqa: E402
from hx.config import load_config                          # noqa: E402

ZIEL = pathlib.Path(r"g:\Harness\docs\_r13bw8_hybrid_beleg.txt")
cfg = load_config()

zeilen = [f"R13bw-8 Hybrid-A4-Beleg {time.strftime('%Y-%m-%d %H:%M:%S')}", ""]
verlauf = stand.hybrid_a4_verlauf(cfg, 8)
zeilen.append("A4-Reihe (neueste Preflight-Dateien):")
for e in verlauf:
    zeilen.append(f"  B{e['batch']:<4} art={str(e['art']):<10} weg={int(e['weg']):>12} "
                  f"halt_pc={e['halt_pc']:<10} cache={e['cache']} datei={e['datei']}")
b_reihe = [e for e in verlauf if aussensicht.ist_b_batch(cfg, int(e["batch"]))]
zeilen.append("")
zeilen.append("davon B-Batches: " + ", ".join(f"B{e['batch']}" for e in b_reihe))
alarm = aussensicht.hybrid_stillstand(cfg)
zeilen.append("")
zeilen.append("ALARM hybrid_stillstand: " + (alarm if alarm else "(kein Alarm)"))
zeilen.append(f"Anzahl A4-Eintraege mit Halt-Art Schranke (von {len(verlauf)}): "
              f"{sum(1 for e in verlauf if str(e['art']).strip().lower() == 'schranke')}")
text = "\n".join(zeilen) + "\n"
ZIEL.write_text(text, encoding="utf-8", newline="\n")
print(text)
