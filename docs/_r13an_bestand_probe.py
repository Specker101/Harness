"""Statische Bestandsaufnahme (nur lesend): welche Tests fassen den ECHTEN Harness-Zustand?

Geprueft wird je Testdatei:
  * kommt `load_config()` vor (also die echte Konfiguration)?
  * wird `paths.root` / `harness_home` auf ein Wegwerfverzeichnis umgebogen?
  * werden Dateien aus `g:\\Silent Scope Decomp` (DEC/ECHTER... ) gelesen, und welche
    Nummernbereiche? - Dauer-Dokumente (Anker, Plan) sind gefaehrlich, abgeschlossene
    Batch-Artefakte (`_preflight_<N>.txt`) nicht.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent                # docs/
TESTS = HIER.parent / "harness" / "tests"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                            # noqa: BLE001
    pass

RE_LOADS = re.compile(r"load_config\(\)")
RE_TEMP = re.compile(r'paths"\]\["(root|decomp|harness_home)"\]')
RE_ECHT = re.compile(r"DEC\b|ECHTER_ROOT|ECHTER_CFG|Silent Scope Decomp|cfg\.decomp|"
                     r"ECHTER?\b|echt\b", re.IGNORECASE)
RE_DATEI = re.compile(r"\"([A-Za-z0-9_.\-]*\.(?:md|txt|json|jsonl|csv))\"")
RE_RANGE = re.compile(r"for n in \(([^)]*)\)")
RE_BATCH = re.compile(r'runs" / f?"b(\d{3})|b(\d{3})" |_preflight_(\d+)')

print(f"{'Testdatei':28} {'load_config':12} {'Temp-Root':10} echte Dateien / Bereiche")
for p in sorted(TESTS.glob("test_*.py")):
    text = p.read_text(encoding="utf-8", errors="replace")
    if not RE_LOADS.search(text):
        continue
    temp = sorted(set(m.group(1) for m in RE_TEMP.finditer(text)))
    echt = bool(RE_ECHT.search(text))
    dateien = sorted(set(m.group(1) for m in RE_DATEI.finditer(text)))
    bereiche: list[str] = []
    for m in RE_RANGE.finditer(text):
        if m.group(1).strip():
            bereiche.append("(" + " ".join(m.group(1).split()) + ")")
    nummern = sorted(set(g for m in RE_BATCH.finditer(text) for g in m.groups() if g))
    detail = "; ".join(filter(None, [
        (", ".join(dateien[:6]) + (" …" if len(dateien) > 6 else "")) or "",
        ("for n in " + " / ".join(bereiche)) if bereiche else "",
        ("Batches: " + ", ".join(nummern)) if nummern else ""]))
    print(f"{p.name:28} {'ja':12} {(','.join(temp) or '-'):10} "
          f"{'ECHT' if echt else '-':5} {detail[:110]}")
