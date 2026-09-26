"""Schluesseldateien aus dem Harness-Ordner herauslegen (Option 3, 2026-09-26).

Warum: der Worker hat PowerShell und laeuft als derselbe Windows-Benutzer. Eine
Pfadbindung der Werkzeuge schliesst ihn nicht (gemessen,
`docs/_ask_zugriff_regeln.txt`). Ein Schlüssel, der in einem Ordner liegt, den
der Worker aus seiner Vorgeschichte kennt, ist deshalb eine Einladung. Dieses
Werkzeug legt die Dateien nach `%USERPROFILE%\\.hx-secrets` um und setzt die
Zugriffsrechte auf **nur diesen Benutzer** - die Huerde wird hoeher, dicht wird
es erst mit einer eigenen Identitaet (Option 4).

Idempotent: liegen die Dateien schon am Ziel, passiert nichts. Ausgegeben werden
NIE Werte, nur Name, Groesse, Fingerabdruck (8 Zeichen) und die ACL.

    python -u tools\\setup_secrets.py            # umziehen + Rechte setzen
    python -u tools\\setup_secrets.py --check    # nur pruefen, nichts aendern
    python -u tools\\setup_secrets.py --ziel PFAD
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import secrets                                                  # noqa: E402

# Alle drei Dateien, die im Harness vorkommen.
NAMEN = (secrets.DEEPSEEK, secrets.TELEGRAM, secrets.CLAUDE_OAUTH)
STD_ALT = Path("g:/Harness/secrets")
STD_NEU = Path(os.environ.get("USERPROFILE", str(Path.home()))) / ".hx-secrets"


def fingerprint(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:8]


def acl_zeilen(p: Path) -> list[str]:
    r = subprocess.run(["icacls", str(p)], capture_output=True, text=True)
    return [z.strip() for z in (r.stdout or "").splitlines() if z.strip() and "Erfolg" not in z]


def setze_rechte(p: Path) -> tuple[bool, str]:
    """Nur der aktuelle Benutzer: Vererbung aus, alles andere entfernen."""
    user = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    if not user:
        return False, "Benutzername nicht ermittelbar"
    r1 = subprocess.run(["icacls", str(p), "/inheritance:r"], capture_output=True, text=True)
    if r1.returncode != 0:
        return False, (r1.stdout + r1.stderr).strip()[:200]
    r2 = subprocess.run(["icacls", str(p), "/grant:r", f"{user}:(OI)(CI)F", "/T", "/C"],
                        capture_output=True, text=True)
    if r2.returncode != 0:
        return False, (r2.stdout + r2.stderr).strip()[:200]
    return True, user


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--alt", default=str(STD_ALT), help="bisheriger Ordner")
    ap.add_argument("--ziel", default=str(STD_NEU), help="neuer Ordner")
    ap.add_argument("--check", action="store_true", help="nur pruefen")
    a = ap.parse_args()
    alt, ziel = Path(a.alt), Path(a.ziel)

    zeilen = ["Umzug der Schluesseldateien (Option 3)",
              f"  alt : {alt}",
              f"  ziel: {ziel}",
              f"  Modus: {'PRUEFEN' if a.check else 'UMZIEHEN'}",
              ""]
    ok = True
    if not a.check:
        ziel.mkdir(parents=True, exist_ok=True)

    for name in NAMEN:
        q, z = alt / name, ziel / name
        zeile = f"{name:22s}"
        if q.is_file():
            fp, groesse = fingerprint(q), q.stat().st_size
            if a.check:
                zeilen.append(zeile + f" NOCH AM ALTEN ORT ({groesse} B, fp {fp})")
                ok = False
                continue
            shutil.copy2(q, z)
            if fingerprint(z) != fp:
                zeilen.append(zeile + " FEHLER: Kopie weicht ab - Original bleibt liegen")
                ok = False
                continue
            q.unlink()
            zeilen.append(zeile + f" umgezogen ({groesse} B, fp {fp})")
        elif z.is_file():
            zeilen.append(zeile + f" schon am Ziel (fp {fingerprint(z)})")
        else:
            zeilen.append(zeile + " FEHLT (weder alt noch neu)")
            ok = False

    if not a.check:
        gut, info = setze_rechte(ziel)
        zeilen += ["", f"Rechte setzen: {'ok' if gut else 'FEHLER'} ({info})"]
        ok = ok and gut
        zeilen += ["", "ACL jetzt:", "  " + "\n  ".join(acl_zeilen(ziel))]
    else:
        zeilen += ["", "ACL jetzt:", "  " + "\n  ".join(acl_zeilen(ziel))]

    # Der alte Ordner muss leer sein; liegen bleiben darf nur Nichts.
    if alt.is_dir():
        rest = [p.name for p in alt.iterdir()]
        zeilen += ["", f"alter Ordner: {'leer' if not rest else 'NICHT leer: ' + ', '.join(rest)}"]
        if rest:
            ok = False
    else:
        zeilen += ["", "alter Ordner: existiert nicht mehr"]

    # Leseprobe ueber die neue Wurzel - nur Fingerabdruecke.
    zeilen += ["", "Leseprobe (Werte werden nie ausgegeben):"]
    for name in NAMEN:
        try:
            w = secrets.load(ziel, name)
            zeilen.append(f"  {name:22s} lesbar, {len(w)} Zeichen, fp {secrets.fingerprint(w)}")
        except Exception as exc:                                  # noqa: BLE001
            zeilen.append(f"  {name:22s} NICHT lesbar: {str(exc)[:80]}")
            ok = False

    text = "\n".join(zeilen)
    print(text)
    beleg = Path("g:/Harness/docs/_secrets_umzug.txt")
    try:
        beleg.write_text(text + "\n", encoding="utf-8")
        print(f"\nBeleg: {beleg}")
    except OSError:
        pass
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
