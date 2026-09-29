"""R13ap: Kodierung der Preflight-Dateien und Wirkung der Erkennung (nur LESEND).

Beantwortet die drei Fragen des Auftrags mit Messwerten:
  1. Welche Kodierung haben die Preflight-Dateien wirklich? (BOM-Bytes je Datei)
  2. Was liest der Harness jetzt? (`stand.preflight_text`, C-Koepfe-Reihe)
  3. Hat die Parser-Warnung aus R13ae beim Review zu B216 angeschlagen?
     (Die Review-Fakten zu B216 liegen im Ordner von B217 - Ordner-Konvention.)

Aufruf: python -u docs/_r13ap_probe.py
Es wird NICHTS geschrieben ausser der Ausgabe auf stdout.
"""

from __future__ import annotations

import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
ROOT = HIER.parent                       # g:\Harness
sys.path.insert(0, str(ROOT / "harness"))

from hx import stand                                              # noqa: E402
from hx.config import load_config                                 # noqa: E402
from hx.util import erkenne_kodierung, read_text                   # noqa: E402


def main() -> int:
    cfg = load_config()
    adir = Path(cfg.decomp) / "analysis"
    print("== 1) Kodierung der Preflight-Dateien (BOM-Bytes) ==")
    zaehler: dict[str, int] = {}
    erste: dict[str, list[str]] = {}
    for p in sorted(adir.glob("_preflight_*.txt")):
        b = p.read_bytes()
        kod = erkenne_kodierung(b)
        kopf = b[:2].hex(" ").upper() if b else "(leer)"
        zaehler[kod] = zaehler.get(kod, 0) + 1
        erste.setdefault(kod, [])
        if len(erste[kod]) < 3:
            erste[kod].append(f"{p.name} (Kopf {kopf})")
    for kod, n in sorted(zaehler.items(), key=lambda kv: -kv[1]):
        print(f"   {kod:<20} {n:>3} Dateien   z.B. {', '.join(erste[kod])}")

    print()
    print("== 2) Was liest der Harness JETZT ==")
    dateien = stand.preflight_dateien(cfg, 3)
    for batch, p in dateien:
        _text, kod = stand.preflight_text(p)
        print(f"   B{batch}: {p.name}  ->  gelesen als {kod}")
    print(f"   preflight_zeilen_pruefen(anzahl=1) -> "
          f"{stand.preflight_zeilen_pruefen(cfg, anzahl=1) or '[] (alle Pflichtzeilen erkannt)'}")
    print(f"   preflight_kodierung_hinweis(anzahl=1) -> "
          f"{stand.preflight_kodierung_hinweis(cfg, 1) or '[] (keine UTF-16-Datei)'}")
    reihe = stand.preflight_c_koepfe(cfg, 4)
    print("   preflight_c_koepfe(4):")
    for e in reihe:
        print(f"      B{e['batch']}: {e['koepfe']} / {e['faelle']} / {e['abweichungen']}")
    trend = stand.c_trend(cfg, 12)
    print(f"   c_trend(12): gemessen={trend.get('gemessen')} erst={trend.get('erst')} "
          f"letzt={trend.get('letzt')} delta={trend.get('delta')} "
          f"luecken={trend.get('luecken')}")

    print()
    print("== 3) R13ae-Warnung im Review zu B216 ==")
    for kandidat in (ROOT / "harness" / "runs" / "b217" / "harness-facts.md",
                     ROOT / "harness" / "runs" / "b216" / "harness-facts.md"):
        print(f"   --- {kandidat.relative_to(ROOT)}")
        if not kandidat.is_file():
            print("       (fehlt)")
            continue
        treffer = 0
        for i, z in enumerate(read_text(kandidat).splitlines(), 1):
            if "PARSER" in z or "UTF-16" in z or "erwartete Zeilen gelesen" in z:
                print(f"       {i}: {z.strip()[:150]}")
                treffer += 1
        if not treffer:
            print("       (keine PARSER-Zeile)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
