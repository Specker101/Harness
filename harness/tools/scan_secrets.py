"""Belege und Mitschnitte auf Schluesselwerte durchsuchen (Bereinigung, 2026-09-26).

Gesucht werden die WERTE der drei Schluesseldateien - verglichen wird nur im
Speicher. Ausgegeben werden ausschliesslich Dateiname, Schluesselname und Anzahl;
der Wert selbst steht in keiner Ausgabe und in keiner Belegdatei.

    python -u tools\\scan_secrets.py                  # nur suchen (Bericht)
    python -u tools\\scan_secrets.py --redact         # Fundstellen unkenntlich machen
    python -u tools\\scan_secrets.py --redact --delete-ext .jsonl,.txt

Gelesen wird in Bloecken (Dateien koennen gross sein); die Blockgrenze wird mit
einer Ueberlappung von len(Wert)-1 Zeichen ueberbrueckt, damit ein Wert nicht
durch den Schnitt verloren geht.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import secrets                                          # noqa: E402
from hx.config import load_config                               # noqa: E402

# Ordner, die durchsucht werden (relativ zur Harness-Wurzel bzw. absolut).
UNTER = ("runs", "logs", "state", "cc-worker", "cc-reviewer", "snapshots", "sessions",
         "inbox", "outbox", "preview")
ABSOLUT = ("g:/Harness/sandbox", "g:/Harness/docs", "g:/Harness/nachrichten")
BLOCK = 1 << 20
ERSATZ = "<SCHLUESSEL-ENTFERNT>"

# NICHT absteigen: Entwicklungsordner und - wichtiger - VERKNÜPFUNGEN.
# `sandbox/decomp-link` ist eine Junction ins Decomp-Repo: `rglob` folgt ihr und
# meldet 69 GB statt 30 MB (am 2026-09-26 genau so passiert). Deshalb `os.walk`
# mit `followlinks=False`.
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "decomp-link"}

# Binaerartige Dateien: ein Schluesselwert ist ASCII, aber 70 GB Bauartefakte und
# ROMs zu durchsuchen bringt nichts - sie sind keine Mitschnitte. Bewusst NICHT
# enthalten sind .jsonl/.txt/.md/.log: das sind genau die Belege.
SKIP_EXT = {".exe", ".dll", ".zip", ".7z", ".gz", ".tar", ".png", ".jpg", ".jpeg",
            ".gif", ".ppm", ".bmp", ".o", ".obj", ".a", ".lib", ".pyc", ".whl",
            ".pdf", ".mp3", ".wav", ".mp4", ".iso", ".bin", ".rom"}


def dateien(wurzel: Path):
    """Alle Dateien unter `wurzel` - ohne Verknuepfungen und ohne Binaerartefakte."""
    import os
    for pfad, dirs, namen in os.walk(wurzel, followlinks=False):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for n in namen:
            p = Path(pfad) / n
            if p.suffix.lower() in SKIP_EXT:
                continue
            yield p


def treffer_in_text(text: str, werte: dict[str, str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for name, wert in werte.items():
        if not wert:
            continue
        n = text.count(wert)
        if n:
            out[name] = n
    return out


def scanne_datei(p: Path, werte: dict[str, str]) -> dict[str, int]:
    """Blockweise suchen, ohne die ganze Datei zu halten."""
    maxlen = max((len(w) for w in werte.values() if w), default=1)
    gesamt: dict[str, int] = {}
    rest = ""
    try:
        with open(p, "rb") as fh:
            while True:
                block = fh.read(BLOCK)
                if not block:
                    break
                text = rest + block.decode("utf-8", errors="replace")
                for name, n in treffer_in_text(text, werte).items():
                    gesamt[name] = gesamt.get(name, 0) + n
                rest = text[-(maxlen - 1):] if maxlen > 1 else ""
    except OSError as exc:
        return {"<nicht lesbar>": 1} if False else {"_fehler": str(exc)[:60]}  # type: ignore[dict-item]
    return gesamt


def kontexte(p: Path, werte: dict[str, str], breite: int = 120) -> list[str]:
    """Redigierte Fundstellen einer Datei (Wert -> <WERT>) fuer die Herkunft."""
    try:
        text = p.read_bytes().decode("utf-8", errors="replace")
    except OSError as exc:
        return [f"nicht lesbar: {exc}"]
    out: list[str] = []
    for name, wert in werte.items():
        if not wert:
            continue
        start = 0
        while True:
            i = text.find(wert, start)
            if i < 0:
                break
            roh = text[max(0, i - breite):i + len(wert) + breite]
            out.append(f"[{name}] ...{roh.replace(wert, '<WERT>')}...")
            start = i + len(wert)
    return out


def entschaerfe(p: Path, werte: dict[str, str]) -> tuple[bool, str]:
    """Fundstelle unkenntlich machen. Binaerdateien werden NICHT angefasst."""
    try:
        raw = p.read_bytes()
    except OSError as exc:
        return False, str(exc)[:60]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return False, "binaer - nicht entschaerft (bitte loeschen)"
    neu = text
    for wert in werte.values():
        if wert:
            neu = neu.replace(wert, ERSATZ)
    try:
        p.write_text(neu, encoding="utf-8")
    except OSError as exc:
        return False, str(exc)[:60]
    return True, "entschaerft"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--redact", action="store_true", help="Fundstellen unkenntlich machen")
    ap.add_argument("--delete-ext", default="",
                    help="kommagetrennte Endungen, die stattdessen GELOESCHT werden")
    ap.add_argument("--kontext", action="store_true",
                    help="redigierten Kontext je Fundstelle zeigen (Herkunft)")
    ap.add_argument("--beleg", default="g:/Harness/docs/_secret_scan.txt")
    a = ap.parse_args()

    cfg = load_config()
    werte: dict[str, str] = {}
    for name in secrets.NAMEN:
        try:
            werte[name] = secrets.load(cfg.secrets_dir, name)
        except Exception as exc:                                  # noqa: BLE001
            print(f"  {name}: nicht ladbar ({exc})")

    wurzeln = [cfg.root / u for u in UNTER] + [Path(x) for x in ABSOLUT]
    loeschen = tuple(e.strip().lower() for e in a.delete_ext.split(",") if e.strip())

    zeilen = ["Suche nach Schluesselwerten in Mitschnitten und Belegen",
              f"  Modus  : {'BEREINIGEN' if a.redact else 'NUR SUCHEN'}",
              "  Muster : " + ", ".join(f"{n} (fp {secrets.fingerprint(v)})"
                                       for n, v in sorted(werte.items())),
              "  Werte werden nie ausgegeben - nur Datei, Name und Anzahl.", ""]
    treffer: list[tuple[Path, dict]] = []
    dateien_gezaehlt = 0
    for w in wurzeln:
        if not w.is_dir():
            continue
        for p in dateien(w):
            if not p.is_file():
                continue
            dateien_gezaehlt += 1
            t = scanne_datei(p, werte)
            t.pop("_fehler", None)
            if t:
                treffer.append((p, t))

    zeilen.append(f"  durchsuchte Dateien: {dateien_gezaehlt}")
    zeilen.append("  uebersprungen: Verknuepfungen (sandbox/decomp-link), "
                  ".git/__pycache__/node_modules, Binaerartefakte "
                  f"({', '.join(sorted(SKIP_EXT))})")
    zeilen.append(f"  Dateien mit Fund  : {len(treffer)}")
    zeilen.append("")
    for p, t in treffer:
        zeilen.append(f"  {p}  -> " + ", ".join(f"{k}: {v}x" for k, v in sorted(t.items())))
        if a.kontext:
            for k in kontexte(p, werte):
                zeilen.append("      " + k)
        if a.redact:
            if loeschen and p.suffix.lower() in loeschen:
                try:
                    p.unlink()
                    zeilen.append("      GELOESCHT (Endung in --delete-ext)")
                except OSError as exc:
                    zeilen.append(f"      loeschen fehlgeschlagen: {exc}")
                continue
            ok, info = entschaerfe(p, werte)
            zeilen.append(f"      {info}" + ("" if ok else "  <-- offen"))
    if not treffer:
        zeilen.append("  (keine Fundstelle)")

    text = "\n".join(zeilen)
    print(text)
    Path(a.beleg).parent.mkdir(parents=True, exist_ok=True)
    Path(a.beleg).write_text(text + "\n", encoding="utf-8")
    print(f"\nBeleg: {a.beleg}")
    # Gegenprobe: der Beleg selbst darf keinen Wert enthalten.
    eigen = scanne_datei(Path(a.beleg), werte)
    print("Beleg enthaelt Werte?", "JA - FEHLER" if eigen else "nein")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
