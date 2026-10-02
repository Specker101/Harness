"""R13bk - ART der weichen Hinweise bestimmen (NUR LESEND).

Der Hauptbeleg `_r13bk_upload_pruefung.txt` meldet 496 "weiche" Treffer des
Musters "Zugangswort mit Wert" - alle in ignorierten Laufprotokollen bzw. in
Decomp-Repo-Dateien. Damit ist noch nicht gesagt, OB dort ein echter Wert steht
oder ein Platzhalter.

Dieses Skript liest nur die im Hauptbeleg genannten Dateien, sucht dieselbe
Stelle wieder und meldet **ausschliesslich** die ART: Suchwort, Laenge und
Zeichenklasse des Werts, ob er mit einem Wert aus `%USERPROFILE%\\.hx-secrets`
identisch ist, und die Fundstelle. **Der Wert selbst wird nie ausgegeben.**
"""
from __future__ import annotations

import io
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"g:/Harness")
HAUPT = ROOT / "docs" / "_r13bk_upload_pruefung.txt"
BELEG = ROOT / "docs" / "_r13bk_hinweise_art.txt"

PAT_ZUGANG = (r"(?i)\b(api[_-]?key|apikey|access[_-]?token|auth[_-]?token|bot[_-]?token"
              r"|client[_-]?secret|passw(?:or)?d|chat[_-]?id|oauth[_-]?token)\b\s*[:=]\s*"
              r"[\"']?([A-Za-z0-9_\-\.:/]{8,})")


def werte_aus_secrets() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    home = Path(os.environ.get("USERPROFILE") or Path.home())
    d = home / ".hx-secrets"
    if not d.is_dir():
        return out
    for p in sorted(d.rglob("*")):
        if not p.is_file():
            continue
        try:
            for ln in io.open(p, encoding="utf-8", errors="replace").read().splitlines():
                v = ln.strip()
                if len(v) >= 12 and not v.startswith("#"):
                    out.append((p.name, v))
        except OSError:
            continue
    return out


def klasse(wert: str) -> str:
    """Zeichenklasse - beschreibt die FORM, nicht den Inhalt."""
    if re.fullmatch(r"\d+", wert):
        return "nur Ziffern"
    if re.fullmatch(r"\d[\d\-]*", wert):
        return "Ziffern mit Bindestrich"
    if re.fullmatch(r"[A-Za-z0-9_\-]+", wert):
        return "Buchstaben/Ziffern/Bindestrich (token-artig)"
    if re.fullmatch(r"[A-Za-z0-9_\-\.:/]+", wert):
        return "enthaelt / . oder : (pfad-artig)"
    return "sonstige Zeichen"


def main() -> int:
    z: list[str] = []
    z.append("R13bk - ART der weichen Hinweise (Werte werden NICHT ausgegeben)")
    z.append(f"Hauptbeleg: {HAUPT}")
    z.append("")
    if not HAUPT.is_file():
        print("Hauptbeleg fehlt - erst `docs/_r13bk_upload_pruefung.py` laufen lassen.")
        return 1

    text = io.open(HAUPT, encoding="utf-8", errors="replace").read()
    # Abschnitt 4a: "TREFFER <art>: <pfad>:<zeile> ..."
    stelle = re.compile(r"^  TREFFER .*: (.+?):(\d+) ", re.M)
    dateien: dict[str, set[int]] = {}
    for m in stelle.finditer(text):
        dateien.setdefault(m.group(1), set()).add(int(m.group(2)))
    z.append(f"Dateien mit weichen Hinweisen: {len(dateien)}")
    z.append("")

    needles = werte_aus_secrets()
    pat = re.compile(PAT_ZUGANG)
    gesamt: dict[tuple[str, str, str], int] = {}
    beispiele: dict[tuple[str, str, str], list[str]] = {}
    werte: dict[str, list[str]] = {}
    identisch = 0
    fundstellen = 0

    for rel in sorted(dateien):
        p = ROOT / rel
        try:
            txt = io.open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            z.append(f"  {rel}: nicht lesbar - uebersprungen")
            continue
        for nr, ln in enumerate(txt.splitlines(), 1):
            for m in pat.finditer(ln):
                wert = m.group(2)
                fundstellen += 1
                ist_echt = any(wert == v for _q, v in needles)
                if ist_echt:
                    identisch += 1
                werte.setdefault(wert, []).append(f"{rel}:{nr}")
                schluessel = (m.group(1).lower(),
                              f"{len(wert)} Zeichen",
                              ("IDENTISCH mit .hx-secrets" if ist_echt else klasse(wert)))
                gesamt[schluessel] = gesamt.get(schluessel, 0) + 1
                b = beispiele.setdefault(schluessel, [])
                if len(b) < 3:
                    b.append(f"{rel}:{nr}")

    z.append(f"Fundstellen im Arbeitsbaum (dieselbe Suche wie 4a): {fundstellen}")
    z.append(f"davon mit einem Wert AUS .hx-secrets identisch: {identisch}")
    z.append("")
    z.append("Art der Fundstellen (Suchwort | Laenge | Zeichenklasse -> Anzahl):")
    for schluessel in sorted(gesamt, key=lambda k: -gesamt[k]):
        wort, laenge, kl = schluessel
        z.append(f"  {wort:18s} {laenge:14s} {kl:48s} {gesamt[schluessel]:5d}")
        for b in beispiele[schluessel]:
            z.append(f"      z. B. {b}")
    z.append("")
    z.append("## Sind die Werte Platzhalter oder echte Geheimnisse?")
    z.append("Entscheidender Test: derselbe Wert kommt auch in einer GETRACKTEN Datei")
    z.append("vor -> er steht als Beispiel im Repo und ist kein Geheimnis.")
    z.append("")
    # Getrackte Dateien einmal einlesen (das ist der Vergleichsmassstab).
    _l = subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True,
                        stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                        errors="replace")
    getrackt: dict[str, str] = {}
    for rel in _l.stdout.splitlines():
        rel = rel.strip()
        p = ROOT / rel
        try:
            if p.is_file() and p.stat().st_size < 5 * 1024 * 1024 and \
                    p.suffix.lower() in (".py", ".md", ".txt", ".json", ".toml", ".ps1"):
                getrackt[rel] = io.open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
    z.append(f"  (verglichene getrackte Dateien: {len(getrackt)})")
    MARKER = ("xxx", "dein", "your", "example", "secret", "test", "placeholder",
              "changeme", "dummy", "beispiel", "pass", "geheim", "redact", "***")
    unklar: list[str] = []
    for wert, orte in sorted(werte.items(), key=lambda kv: -len(kv[1])):
        marker = sorted({m for m in MARKER if m in wert.lower()})
        wo = sorted(r for r, txt in getrackt.items() if wert in txt)
        if wo:
            urteil = f"steht auch in {len(wo)} getrackten Datei(en) -> Beispiel/Platzhalter"
        elif marker:
            urteil = f"Platzhalter-Marker {marker}"
        else:
            urteil = "KEIN Beleg fuer einen Platzhalter"
            unklar.append((wert, orte[0]))
        z.append(f"  {len(orte):5d}x  {len(wert):3d} Zeichen  {klasse(wert):46s} {urteil}")
        if wo:
            z.append(f"         getrackt z. B.: {wo[0]}")
        if not wo:
            z.append(f"         Fundstelle z. B.: {orte[0]}")
    z.append("")
    if unklar:
        z.append(f"  Werte OHNE Platzhalter-Beleg: {len(unklar)}")
        z.append("  (Fundstelle mit MASKiertem Wert - der Wert selbst steht nirgends.)")
        for wert, ort in unklar[:25]:
            rel, _, nr = ort.rpartition(":")
            zeile = ""
            try:
                zeile = io.open(ROOT / rel, encoding="utf-8",
                                errors="replace").read().splitlines()[int(nr) - 1]
            except (OSError, IndexError, ValueError):
                pass
            maskiert = zeile.replace(wert, "\u00abWERT\u00bb")
            if len(maskiert) > 160:
                i = maskiert.find("\u00abWERT\u00bb")
                maskiert = "..." + maskiert[max(0, i - 60):i + 75] + "..."
            z.append(f"    - {ort}  ({len(wert)} Zeichen, {klasse(wert)})")
            z.append(f"        {maskiert.strip()}")
        z.append("  Diese Stellen von Hand ansehen, bevor irgendetwas aus diesem")
        z.append("  Arbeitsbaum weitergegeben wird.")
    else:
        z.append("  **Alle gefundenen Werte sind als Beispiel/Platzhalter belegt** - kein")
        z.append("  Hinweis auf ein echtes Geheimnis im Arbeitsbaum.")

    z.append("")
    z.append("Lesehilfe: 'nur Ziffern' = kein Geheimnis, sondern eine Kennnummer")
    z.append("(z. B. chat_id). 'token-artig' = Form wie ein Schluessel - dann gehoert")
    z.append("die Datei trotzdem nicht ins Repo, auch wenn sie ignoriert ist.")

    out = "\n".join(z) + "\n"
    BELEG.write_text(out, encoding="utf-8", newline="\n")
    print(out)
    print(f"Beleg: {BELEG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
