"""Einmaliger Rueckblick (R13ae, 2026-09-29): werden B212/B213 jetzt erkannt?

**Auftrag:** "Einmal rueckwirkend laufen lassen: Werden B212/B213 jetzt mit 4006 erkannt?
`c_trend` und Durchsatzrechnung ueber B201-B213 neu zeigen."

Liest die ECHTEN Preflight-Dateien B201..B213 und die kanonischen Bilanzdateien
`_m200.._m213` - **kopiert** in ein Wegwerf-Verzeichnis, weil waehrend der Testreihe ein
Batch laeuft und neue `_preflight_<N>.txt` schreibt (FALLSTRICK aus R13ac: das lebende
Fenster ist kein stabiler Bezug). Zeigt Trend und Durchsatzblock einmal mit dem neuen,
toleranten Muster und einmal mit dem alten aus der Zeit vor dem Fix.

Aufruf (aus `harness/`):

    python -u ../docs/_r13ae_retro.py

Schreibt den Bericht nach `docs/_r13ae_retro.txt` (UTF-8, LF) - das ist der Beleg.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent                # docs/
HARNESS = HIER.parent / "harness"
sys.path.insert(0, str(HARNESS))

from hx import stand                                  # noqa: E402
from hx.config import load_config                     # noqa: E402
from hx.util import ensure_dir                        # noqa: E402

VON, BIS = 201, 213
FENSTER = 12

echt = Path(load_config().decomp) / "analysis"
tmp = HIER / "_tmp_r13ae_retro"
shutil.rmtree(tmp, ignore_errors=True)
ana = ensure_dir(tmp / "decomp" / "analysis")

kopiert: list[int] = []
for b in range(VON, BIS + 1):
    p = echt / f"_preflight_{b}.txt"
    if p.is_file():
        shutil.copy2(p, ana / p.name)
        kopiert.append(b)
bilanz: list[int] = []
for d in sorted(echt.glob("_m*")):
    if d.is_dir() and d.name[2:].isdigit() and VON - 1 <= int(d.name[2:]) <= BIS:
        ziel = ensure_dir(ana / d.name)
        for f in d.glob("_bilanz*.txt"):
            shutil.copy2(f, ziel / f.name)
        bilanz.append(int(d.name[2:]))

cfg = load_config()
cfg.data["paths"]["decomp"] = str(tmp / "decomp")

zeilen: list[str] = []


def sag(text: str = "") -> None:
    zeilen.append(text)
    print(text)


sag(f"R13ae Rueckblick {VON}..{BIS} - Preflight-Kopfzeile und Durchsatz "
    f"(erzeugt {__import__('datetime').datetime.now():%Y-%m-%d %H:%M})")
sag(f"Kopierte Preflight-Dateien: {kopiert}")
sag(f"Kopierte Bilanz-Ordner: {bilanz}")
sag()

sag("=== C-Kopfzeile je Batch (neuer, toleranter Parser) ===")
for e in stand.preflight_c_koepfe(cfg, len(kopiert)):
    sag(f"  B{e['batch']}: {e['koepfe']} Koepfe / {e['faelle']} Faelle / "
        f"{e['abweichungen']} Abweichungen   ({e['datei']})")

sag()
sag(f"=== c_trend({FENSTER}) = B{VON}..B{BIS} (neu) ===")
t = stand.c_trend(cfg, FENSTER)
sag(f"  gemessen={t['gemessen']} erst=B{t['erst']['batch']} "
    f"letzt=B{t['letzt']['batch']} ({t['letzt']['koepfe']} Koepfe / "
    f"{t['letzt']['faelle']} Faelle)")
sag(f"  Batches={t['anzahl_batches']} Dateien={t['n_gemessen']} Luecken={t['luecken']}")
sag(f"  Koepfe B{t['erst']['batch']}->B{t['letzt']['batch']}: {t['erst']['koepfe']} -> "
    f"{t['letzt']['koepfe']} ({t['delta']:+d})")

sag()
sag("=== dasselbe mit dem ALTEN Muster (Stand vor dem Fix) ===")
neu = stand._RE_PREFLIGHT_CKOPF
stand._RE_PREFLIGHT_CKOPF = re.compile(r"^C Koepfe\s+(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\b")
alt = stand.c_trend(cfg, FENSTER)
sag(f"  gemessen={alt['gemessen']} erst=B{alt['erst']['batch']} "
    f"letzt=B{alt['letzt']['batch']} ({alt['letzt']['koepfe']} Koepfe / "
    f"{alt['letzt']['faelle']} Faelle)")
sag(f"  Batches={alt['anzahl_batches']} Dateien={alt['n_gemessen']}  "
    f"-> die beiden neuen Zeilenformen fehlten still")
stand._RE_PREFLIGHT_CKOPF = neu          # zurueck auf das neue Muster

sag()
sag(f"=== Durchsatzblock (neu, Fenster {FENSTER}) ===")
for z in stand.durchsatz_zeilen(cfg, FENSTER):
    sag(z)

sag()
sag("=== Parser-Pruefung ALLER kopierten Dateien (anzahl=13) ===")
sag("(der Harness prueft nur die NEUESTE Datei - anzahl=1 - sonst warnt er alte "
    "Zeilenformen)")
for z in stand.preflight_zeilen_pruefen(cfg, log=None, anzahl=len(kopiert)):
    sag("  " + z)

ziel = HIER / "_r13ae_retro.txt"
ziel.write_text("\n".join(zeilen) + "\n", encoding="utf-8", newline="\n")
print(f"\n-> {ziel} ({ziel.stat().st_size} B)")
shutil.rmtree(tmp, ignore_errors=True)
