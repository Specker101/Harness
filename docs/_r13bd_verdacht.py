"""R13bd: Verdachtsfaelle aus dem Audit lesbar aufbereiten (nur lesend).

Nimmt `docs/_r13bd_audit.json` und druckt je Verdachtsfall den Test, die lebenden Pfade
und die Bauform - die Grundlage fuer die Handpruefung ("kann der leer durchlaufen?").
Schreibt `docs/_r13bd_verdacht.txt`.
"""

from __future__ import annotations

import json
from pathlib import Path

HIER = Path(__file__).resolve().parent
ROH = HIER / "_r13bd_audit.json"
ZIEL = HIER / "_r13bd_verdacht.txt"


def kompakt(pfade: list[str]) -> list[str]:
    """Pfadmuster je Ordner zusammenfassen: viele Namen in einem Ordner = eine Zeile."""
    gruppen: dict[tuple[str, str], list[str]] = {}
    for p in pfade:
        art, _, muster = p.partition(": ")
        ordner = muster.rsplit("/", 1)[0] if "/" in muster else muster
        gruppen.setdefault((art, ordner), []).append(muster.rsplit("/", 1)[-1])
    zeilen = []
    for (art, ordner), namen in sorted(gruppen.items()):
        if len(namen) > 3:
            zeilen.append(f"{art}: {ordner}/  ({len(namen)} Namen, z. B. "
                          f"{', '.join(sorted(namen)[:3])} …)")
        else:
            zeilen += [f"{art}: {ordner}/{n}" for n in sorted(namen)]
    return zeilen


def main() -> int:
    daten = json.loads(ROH.read_text(encoding="utf-8"))
    verdacht = [e for e in daten if e.get("if_ohne_else") or e.get("for_ohne_assert")
                or e.get("leere_zusicherung")]
    zeilen = [f"Verdachtsfaelle aus {ROH.name}: {len(verdacht)} von {len(daten)} "
              f"live lesenden Tests", ""]
    for e in verdacht:
        formen = []
        if e.get("if_ohne_else"):
            formen.append(f"A if ohne else in Zeile {e['if_ohne_else']}")
        if e.get("for_ohne_assert"):
            formen.append(f"B Schleife ohne Zusicherung in Zeile {e['for_ohne_assert']}")
        if e.get("leere_zusicherung"):
            formen.append("C Zusicherung gilt auch fuer die leere Menge")
        pfade = kompakt(e["pfade"])
        zeilen += [e["test"], f"  Zusicherungen: {e.get('asserts')}",
                   f"  Lebende Pfade ({len(pfade)}):"]
        zeilen += [f"    {p}" for p in pfade[:8]]
        if len(pfade) > 8:
            zeilen.append(f"    … und {len(pfade) - 8} weitere")
        zeilen += ["  Bauform: " + "; ".join(formen), ""]
    ZIEL.write_text("\n".join(zeilen) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(zeilen))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
