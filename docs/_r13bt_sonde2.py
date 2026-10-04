"""R13bt-Sonde (nur lesend): die neue B-Phase-Zeile gegen die ECHTEN runs/b26x.

Schreibt den Beleg SELBST als UTF-8/LF (`_r13bt_sonde2.txt`) - eine PowerShell-Umleitung
(`*>` oder `>`) legt UTF-16 an, und der Beleg waere dann binaer (Lehre aus B157/R382).
"""
import io
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "harness"))
ZIEL = pathlib.Path(__file__).with_suffix(".txt")


def lauf() -> str:
    from hx.config import load_config
    from hx import stand

    buf = io.StringIO()
    cfg = load_config()
    print("root:", cfg.root, file=buf)
    z = stand.stillstand_zaehler(cfg, anzahl=12)
    print("zaehler:", {k: z[k] for k in ("zaehler", "von", "bis", "luecke_ab", "grenze_ab",
                                         "station_bei", "schwelle_erreicht", "offen")},
          file=buf)
    print("reihe:", z["reihe"], file=buf)
    print("--- b_phase_zeile ---", file=buf)
    for zeile in stand.b_phase_zeile(cfg, z):
        print(zeile, file=buf)
    print("--- Mischung (Fenster) ---", file=buf)
    d = stand.durchsatz(cfg) if hasattr(stand, "durchsatz") else {}
    for zeile in stand._mischung_zeile(cfg, d if isinstance(d, dict) else {}):
        print(zeile, file=buf)
    return buf.getvalue()


if __name__ == "__main__":
    text = lauf()
    ZIEL.write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"geschrieben: {ZIEL} ({len(text)} Zeichen)")
    print(text)
