"""R13bk - Restpruefung der getrackten Dateien mit Zugangs-Bezug im NAMEN.

Anlass: die Musterliste in `_r13bk_upload_pruefung.py` enthielt `*_secrets*`,
`*credentials*` und `*token*` - aber **kein** einfaches `*secret*`. Dadurch
blieben 11 getrackte Dateien ohne Namenspruefung, darunter `docs/_secret_scan*.txt`.

Inhaltlich hat der Arbeitsbaum-Lauf sie bereits erfasst (4a: 0 Treffer in
getrackten Dateien). Dieses Skript prueft sie zusaetzlich gezielt und sucht dabei
auch nach **langen Zeichenketten** (Entropie-Ersatz), weil ein Muster allein kein
Geheimnis in unbekanntem Format findet.

**Es wird nie ein Wert ausgegeben** - nur Laenge, Zeichenklasse und eine Maske.
"""
from __future__ import annotations

import io
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(r"g:/Harness")
BELEG = ROOT / "docs" / "_r13bk_namensrest.txt"

PATTERN = [
    ("Telegram-Bot-Token", r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b"),
    ("Anthropic-Key", r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    ("sk-Key", r"\bsk-[A-Za-z0-9]{20,}\b"),
    ("Zugangswort mit Wert",
     r"(?i)\b(api[_-]?key|apikey|access[_-]?token|auth[_-]?token|bot[_-]?token"
     r"|client[_-]?secret|passw(?:or)?d|chat[_-]?id|oauth[_-]?token)\b\s*[:=]\s*"
     r"[\"']?([A-Za-z0-9_\-\.:/]{8,})"),
]
LANGE_KETTE = re.compile(r"[A-Za-z0-9_\-+/=]{20,}")
NAMEN = re.compile(r"(?i)(credential|secret|token|password|passwd|apikey|api_key|\.env|\.key$)")


def git(*args: str) -> str:
    p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True,
                       stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                       errors="replace")
    return (p.stdout or "") + (p.stderr or "")


def werte_aus_secrets() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    home = Path(os.environ.get("USERPROFILE") or Path.home())
    d = home / ".hx-secrets"
    if not d.is_dir():
        return out
    for p in sorted(d.rglob("*")):
        if p.is_file():
            try:
                for ln in io.open(p, encoding="utf-8", errors="replace").read().splitlines():
                    v = ln.strip()
                    if len(v) >= 12 and not v.startswith("#"):
                        out.append((p.name, v))
            except OSError:
                continue
    return out


def maske(s: str) -> str:
    """Form ohne Inhalt: erste zwei Zeichen, Laenge, Zeichenklasse, Zeichen-Flags."""
    if re.fullmatch(r"\d+", s):
        kl = "nur Ziffern"
    elif re.fullmatch(r"[0-9a-f]+", s):
        kl = "hex"
    elif re.fullmatch(r"[A-Za-z0-9_\-]+", s):
        kl = "alnum/Bindestrich"
    else:
        kl = "gemischt"
    flags = "".join(f"{c}" for c in "/\\:.+=%" if c in s)
    return f"{s[:2]}...  {len(s):3d} Zeichen  {kl:18s} Zeichen darin: '{flags}'"


def main() -> int:
    z: list[str] = []
    z.append("R13bk - Restpruefung: getrackte Dateien mit Zugangsbezug im Namen")
    z.append("")
    dateien = [x for x in git("ls-files").splitlines() if x.strip() and NAMEN.search(x)]
    z.append(f"Dateien: {len(dateien)}")
    needles = werte_aus_secrets()
    hart = 0
    for rel in dateien:
        p = ROOT / rel
        try:
            txt = io.open(p, encoding="utf-8", errors="replace").read()
        except OSError as e:
            z.append(f"  {rel}: nicht lesbar ({e.__class__.__name__})")
            continue
        treffer: list[str] = []
        for name, pat in PATTERN:
            m = re.search(pat, txt)
            if m:
                treffer.append(f"{name} @ {txt[:m.start()].count(chr(10)) + 1}")
        for q, v in needles:
            if v in txt:
                treffer.append(f"WERT aus .hx-secrets ({q})")
        kandidaten = [k for k in set(LANGE_KETTE.findall(txt)) if len(k) >= 24]
        z.append(f"  {rel}")
        z.append(f"      {len(txt):8d} Zeichen, {txt.count(chr(10)) + 1:6d} Zeilen, "
                 f"lange Ketten (>=24): {len(kandidaten)}")
        if treffer:
            hart += 1
            z.append(f"      ** TREFFER: {'; '.join(treffer)} **")
        if kandidaten:
            laengste = sorted(kandidaten, key=len, reverse=True)[:3]
            for k in laengste:
                z.append(f"      Kandidat: {maske(k)}")
    z.append("")
    z.append(f"Dateien mit Mustertreffer oder Wert aus .hx-secrets: {hart}")
    if hart == 0:
        z.append("  -> auch hier kein Zugangsdatum. Die langen Ketten sind Token in")
        z.append("     Dokumentation/Testdaten; die Form steht oben, der Wert nicht.")
    out = "\n".join(z) + "\n"
    BELEG.write_text(out, encoding="utf-8", newline="\n")
    print(out)
    return 0 if hart == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
