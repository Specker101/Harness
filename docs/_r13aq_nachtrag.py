"""R13aq-Nachtrag (2026-09-30): „zur Kenntnis" als Verdikt nachtragen (M213-4a).

Das Antwortmuster (`hx/aussensicht.py::_RE_VERDIKT`) kannte das Wort „zur Kenntnis" nicht.
`runs/b217/review.md:15` antwortet aber:

    M213-4a: zur Kenntnis - die Batch-Uhr bleibt das Maß

Der Befund stand deshalb weiter als **offen** im Register - sichtbar in
`runs/meta-217.json` (`offen_alt: ["M213-4a"]`). Dieses Werkzeug liest die Zeile und ruft
den regulaeren Weg (`aussensicht.antworten_uebernehmen`) mit dem **bewerteten** Batch auf
(der Review zu Batch N liegt in `runs/b<N+1>/`, hier also Batch 216).

Ohne `--schreiben` wird nur gezeigt, was passieren wuerde (kein Schreibzugriff).
Idempotent: ein bereits beantworteter Eintrag wird nur neu gesetzt, wenn die Zeile es
hergibt - der Nachtrag kann also gefahrlos wiederholt werden.
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

# (Review-Ordner, Kennung, bewerteter Batch)
FAELLE = (("b217", "M213-4a", 216),)


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
    ap.add_argument("--beleg", default="",
                    help="Ausgabe zusaetzlich als UTF-8-Datei schreiben "
                         "(die Konsole schreibt Umlaute sonst in der Codepage um)")
    args = ap.parse_args()
    cfg = load_config()

    zeilen: list[str] = []

    def zeig(text: str = "") -> None:
        print(text)
        zeilen.append(text)

    register = {str(b.get("id")): b for b in aussensicht.ledger(cfg)}
    zeig(f"Register: {aussensicht.ledger_pfad(cfg)}  ({len(register)} Eintraege)")
    zeig(f"Quote vorher:   {aussensicht.zeile(cfg) or '(keine)'}\n")

    for ordner, bid, batch in FAELLE:
        p = HARNESS / "runs" / ordner / "review.md"
        nr, zeile = zeile_mit_kennung(p, bid)
        zeig(f"--- {bid} (Bewertung Batch {batch}) ---")
        if not zeile:
            zeig(f"    {p} nennt '{bid}:' nicht - uebersprungen")
            continue
        zeig(f"    {p.relative_to(HARNESS.parent)}:{nr}")
        zeig(f"    {zeile}")
        alt = dict(register.get(bid) or {})
        zeig(f"    vorher: status={alt.get('status')!r} "
             f"antwort_batch={alt.get('antwort_batch')}")
        if not args.schreiben:
            zeig("    (Probelauf - nicht geschrieben)")
            continue
        geaendert = aussensicht.antworten_uebernehmen(cfg, zeile, batch)
        jetzt = {b["id"]: b for b in aussensicht.ledger(cfg)}.get(bid) or {}
        zeig(f"    nachher: status={jetzt.get('status')!r} "
             f"antwort_batch={jetzt.get('antwort_batch')} geaendert={geaendert}")
        zeig(f"    Antwort im Register: {str(jetzt.get('antwort') or '')[:80]!r}")
        zeig(f"    Klasse (zaehlt wie 'erledigt'): {aussensicht.klasse(jetzt)}")

    zeig(f"\nQuote nachher:  {aussensicht.zeile(cfg) or '(keine)'}")
    zeig(f"Offene Befunde: {[b.get('id') for b in aussensicht.offene(cfg)] or 'keine'}")
    if args.beleg:
        ziel = Path(args.beleg)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        with open(ziel, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(zeilen) + "\n")
        print(f"Beleg: {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
