"""R13bf (Teil B): die Bilanz-Luecke von B234 vorher/nachher belegen.

Rechnet auf der eingefrorenen Fixture `tests/fixtures/stand_b234_luecke` (echter
Dokumentstand 01.10.2026 10:51, **ohne** `_preflight_234.txt`):

* "vorher" = was die alte Regel las (letzte numerische Zelle der Zeile - ohne
  Kopfzeilen-Pruefung und mit Rueckfall auf das Dokument),
* "nachher" = `stand.ist_wert` (Ist-Spalte), `stand.kernzahlen`, `bilanz.gesamt_block`.

    python -u docs/_r13bf_bilanz.py        -> docs/_r13bf_bilanz.txt
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "harness"
sys.path.insert(0, str(HARNESS))

from hx import bilanz, stand                                          # noqa: E402
from hx.config import load_config                                     # noqa: E402
from hx.util import ensure_dir                                        # noqa: E402

FIXTURE = HARNESS / "tests" / "fixtures" / "stand_b234_luecke"
DOK = "port-batch234-c-ausgefuehrte-koepfe-2026-10-01.md"
TMP = Path("g:/Harness/harness/tests/_tmp_r13bf_bilanz")


def _cfg(decomp: Path):
    cfg = load_config()
    cfg.data["paths"]["root"] = str(TMP / "harness")
    cfg.data["paths"]["decomp"] = str(decomp)
    cfg.data["paths"]["prompts"] = str(HARNESS / "prompts")
    return cfg


def alt_lesen(text: str) -> tuple | None:
    """Die Regel VOR R13bf: letzte numerische Zelle der letzten `C Koepfe`-Zeile."""
    zeilen = stand.ist_zellen(text, stand._ETIKETT_CKOPF)
    if not zeilen:
        return None
    _nr, zellen = zeilen[-1]
    for i in range(len(zellen) - 1, 0, -1):
        roh = (zellen[i] or "").replace("*", "").replace("`", "").strip()
        m = stand._RE_ZAHL_CKOPF.match(roh)
        if m:
            return tuple(int(g) for g in m.groups())
    return None


def main() -> int:
    shutil.rmtree(TMP, ignore_errors=True)
    dec = ensure_dir(TMP / "decomp")
    shutil.copytree(FIXTURE / "decomp" / "analysis", dec / "analysis")
    text = (dec / "analysis" / DOK).read_text(encoding="utf-8")
    z: list[str] = []
    z.append("R13bf Teil B - Bilanz ohne Preflight (Befund M234-1)")
    z.append("Fixture: tests/fixtures/stand_b234_luecke (Dokumentstand 01.10.2026 10:51)")
    z.append("Dateien: " + ", ".join(sorted(p.name for p in (dec / "analysis").glob("*"))))
    z.append("")
    zeile_nr, _w = stand.ist_zellen(text, stand._ETIKETT_CKOPF)[-1]
    z.append(f"Dokumentzeile {zeile_nr} (Soll/Ist-Tafel):")
    z.append("  " + text.splitlines()[zeile_nr - 1].strip())
    z.append("")
    z.append(f"  vorher (letzte Zahlzelle)      : {alt_lesen(text)}")
    _nr, neu = stand.ist_wert(text, stand._ETIKETT_CKOPF, stand._RE_ZAHL_CKOPF)
    z.append(f"  nachher (Ist-Spalte, R13bf)    : {neu}")
    z.append("")
    cfg = _cfg(dec)
    reihe = {e["batch"]: e for e in stand.kernzahlen(cfg, 8)}
    for b in sorted(reihe):
        e = reihe[b]
        marke = "NICHT GEMESSEN" if e.get("c_nicht_gemessen") else "gemessen"
        z.append(f"  kernzahlen B{b}: c_koepfe={e.get('c_koepfe')} "
                 f"c_quelle={e.get('c_quelle')!r} {marke}"
                 + (f" erwartet={e.get('c_erwartet')}" if e.get("c_nicht_gemessen") else ""))
    z.append("")
    z.append("  bilanz.gesamt_block:")
    block = bilanz.gesamt_block(cfg)
    for line in block:
        z.append("    " + line)
    z.append("")
    z.append("  Gegenprobe: '115' in den Bilanzzeilen oben? "
             + ("JA (Fehler!)" if re.search(r"\b115\b", "\n".join(block))
                else "nein - die Soll-Spalte ist keine Messung"))
    # Rotprobe: dieselbe Fixture MIT _preflight_234.txt (115/6271/0).
    roh = (dec / "analysis" / "_preflight_233.txt").read_bytes()
    (dec / "analysis" / "_preflight_234.txt").write_bytes(
        roh.replace(b"110 / 6187 / 0", b"115 / 6271 / 0"))
    z.append("")
    z.append("  Rotprobe (mit _preflight_234.txt):")
    for line in bilanz.gesamt_block(cfg):
        if "C Koepfe" in line or "nicht gemessen" in line:
            z.append("    " + line)
    text_out = "\n".join(z) + "\n"
    ziel = ROOT / "docs" / "_r13bf_bilanz.txt"
    ziel.write_text(text_out, encoding="utf-8", newline="\n")
    print(text_out)
    print(f"Beleg: {ziel}")
    shutil.rmtree(TMP, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
