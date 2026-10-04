"""R13bt-3 (2026-10-04): geteiltes Lesen auf Pfaden mit Nicht-ASCII-Zeichen.

GEMESSEN (CONFIRMED): `_winapi.CreateFile` scheitert an jedem Nicht-ASCII-Zeichen im
Pfad, obwohl die Datei da ist (`Path.is_file()` True) und `open()` sie problemlos liest.
Die mittlere Spalte ruft die Windows-Funktion ROH auf - sie zeigt den Defekt auch nach
dem Ausweichen (die Zeile darunter nicht mehr). Schreibt den Beleg selbst als UTF-8/LF -
keine PowerShell-Umleitung (die legt UTF-16 an und der Beleg waere binaer).
"""
import io
import os
import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "harness"))
ZIEL = pathlib.Path(__file__).with_suffix(".txt")


def roh_winapi(p: pathlib.Path) -> str:
    """Derselbe Aufruf, den `_oeffne_shared` auf Windows macht - ohne Ausweichen."""
    if os.name != "nt":
        return "n/a (kein Windows)"
    import _winapi
    share = 0x01 | 0x02 | 0x04                      # READ | WRITE | DELETE
    try:
        handle = _winapi.CreateFile(str(p), _winapi.GENERIC_READ, share, 0,
                                    _winapi.OPEN_EXISTING, 0, 0)
    except OSError as e:
        return f"FAIL errno={e.errno} winerror={getattr(e, 'winerror', '?')}"
    _winapi.CloseHandle(handle)
    return "ok"


def mit_open(p: pathlib.Path) -> str:
    try:
        with open(p, encoding="utf-8") as fh:
            fh.read()
        return "ok"
    except OSError as e:
        return f"FAIL errno={e.errno}"


def geteilt(p: pathlib.Path) -> str:
    try:
        from hx.util import read_text
        return repr(read_text(p))
    except OSError as e:
        return f"FAIL errno={e.errno} winerror={getattr(e, 'winerror', '?')}"


def main() -> str:
    from hx.util import write_text_atomic
    base = pathlib.Path(__file__).resolve().parents[1] / "harness" / "tests" / "_sonde_pfade"
    shutil.rmtree(base, ignore_errors=True)
    buf = io.StringIO()
    print("Vier Faelle, je Datei VORHANDEN (geschrieben mit write_text_atomic):", file=buf)
    print(f"  {'Pfad':28s} {'is_file':8s} {'open()':10s} {'_winapi roh':30s} "
          "read_text (nach R13bt-3)", file=buf)
    for titel, p in (("ascii/ascii", base / "a" / "x.md"),
                     ("ascii/umlaut-name", base / "b" / "gr\u00fc\u00dfe.md"),
                     ("umlaut-dir/ascii", base / "\u00e4" / "x.md"),
                     ("umlaut-dir/umlaut-name", base / "\u00f6" / "pr\u00fcf.md")):
        write_text_atomic(p, "x\n")
        print(f"  {titel:28s} {str(p.is_file()):8s} {mit_open(p):10s} "
              f"{roh_winapi(p):30s} {geteilt(p)}", file=buf)
    shutil.rmtree(base, ignore_errors=True)
    print("\nDeutung: WinError 2 = Dateiname nicht ASCII, WinError 3 = Elternordner nicht"
          "\nASCII. `_oeffne_shared` weicht seit R13bt-3 fuer solche Pfade auf `open()` aus"
          "\n(die Freigabe FILE_SHARE_DELETE brauchen nur unsere eigenen ASCII-Dateien)."
          "\nEin Clone unter einem Benutzernamen mit Umlaut haette sonst jede geteilte"
          "\nLesung (Review, Zustand, Log) als fehlende Datei oder als Absturz erscheinen"
          "\nlassen - der Stillstandszähler (R13bt-2) haette eine Luecke gemeldet, die es"
          "\nnicht gibt.", file=buf)
    return buf.getvalue()


if __name__ == "__main__":
    text = main()
    ZIEL.write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"geschrieben: {ZIEL}")
    print(text)
