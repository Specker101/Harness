"""R13ak-Nachtrag (2026-09-29): zwei beantwortete Befunde ins Register nachtragen.

Das Antwortmuster (`hx/aussensicht.py::_RE_ANTWORT`) war zu streng und hat zwei
Antworten des Reviewers nicht erkannt. Beide Zeilen stehen unveraendert in den
Review-Dateien; dieses Werkzeug liest sie und ruft den regulaeren Weg
(`aussensicht.antworten_uebernehmen`) mit dem Batch auf, der bewertet wurde.

  runs/b211/review.md  "M209-3b: zurueckgestellt (Nutzer), spaetestens B216"  -> Batch 210
  runs/b213/review.md  "M212-1: fuer B213 abgelehnt …, fuer B216 uebernommen …" -> Batch 212

`batch` ist der **bewertete** Batch (Review zu Batch N liegt in `runs/b<N+1>/`), so wie
ihn der Harness beim Review selbst uebergibt (`state.batch`).

Ohne `--schreiben` wird nur gezeigt, was passieren wuerde (kein Schreibzugriff).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent                 # docs/
HARNESS = HIER.parent / "harness"
sys.path.insert(0, str(HARNESS))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                            # noqa: BLE001
    pass

from hx import aussensicht                                     # noqa: E402
from hx.config import load_config                              # noqa: E402
from hx.util import read_text                                  # noqa: E402

# (Review-Datei, Kennung, bewerteter Batch)
FAELLE = (("b211", "M209-3b", 210), ("b213", "M212-1", 212))


def zeile_mit_kennung(pfad: Path, bid: str) -> tuple[int, str]:
    """Die Zeile der Review-Datei, die die Kennung als Antwort nennt (1-basiert)."""
    if not pfad.is_file():
        return 0, ""
    for nr, z in enumerate(read_text(pfad).splitlines(), 1):
        if z.strip().startswith(f"{bid}:"):
            return nr, z.strip()
    return 0, ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--schreiben", action="store_true",
                    help="das Register wirklich schreiben (sonst nur zeigen)")
    args = ap.parse_args()
    cfg = load_config()

    register = {str(b.get("id")): b for b in aussensicht.ledger(cfg)}
    print(f"Register: {aussensicht.ledger_pfad(cfg)}  ({len(register)} Eintraege)")
    print(f"Quote vorher:   {aussensicht.zeile(cfg) or '(keine)'}\n")

    vorher = {bid: dict(register.get(bid) or {}) for _d, bid, _b in FAELLE}
    for ordner, bid, batch in FAELLE:
        p = HARNESS / "runs" / ordner / "review.md"
        nr, zeile = zeile_mit_kennung(p, bid)
        print(f"--- {bid} (Bewertung Batch {batch}) ---")
        if not zeile:
            print(f"    {p} nennt '{bid}:' nicht - uebersprungen")
            continue
        print(f"    {p.relative_to(HARNESS.parent)}:{nr}")
        print(f"    {zeile}")
        alt = vorher.get(bid) or {}
        print(f"    vorher: status={alt.get('status')!r} antwort_batch={alt.get('antwort_batch')}")
        if not args.schreiben:
            print("    (Probelauf - nicht geschrieben)")
            continue
        geaendert = aussensicht.antworten_uebernehmen(cfg, zeile, batch)
        jetzt = {b["id"]: b for b in aussensicht.ledger(cfg)}.get(bid) or {}
        print(f"    nachher: status={jetzt.get('status')!r} "
              f"antwort_batch={jetzt.get('antwort_batch')} geaendert={geaendert}")
        print(f"    Antwort im Register: {str(jetzt.get('antwort') or '')[:80]!r}")
        print()

    print(f"Quote nachher:  {aussensicht.zeile(cfg) or '(keine)'}")
    offen = [str(b.get("id")) for b in aussensicht.offene(cfg)]
    print(f"Offen ({len(offen)}): {', '.join(offen)}")
    for bid in vorher:
        e = {b["id"]: b for b in aussensicht.ledger(cfg)}.get(bid) or {}
        print(f"  {bid}: {vorher.get(bid, {}).get('status')!r} -> {e.get('status')!r} "
              f"(Klasse {aussensicht.klasse(e)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
