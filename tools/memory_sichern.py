"""Memory-Sicherung: ALLE Copilot-Memory-Profile in einen zeitgestempelten Ordner kopieren.

Warum.  Das Copilot-Gedaechtnis (Scope `repo`) liegt im VS-Code-Profil und haengt am
Workspace-Hash:

    %APPDATA%\\Code\\User\\workspaceStorage\\<HASH>\\GitHub.copilot-chat\\memory-tool\\memories\\repo

Ein `git clone` bringt diese Dateien nicht mit.  GEMESSEN am 2026-10-10 liegen hier ZWEI
getrennte Profile:

  * Hash `764c8a21…` - 21 Dateien (Decomp-Workspace).  Dieses Profil ist im Repo gespiegelt
    (`analysis/_memory/`, Werkzeug `Silent Scope Decomp/scripts/m151_memory_sync.py`) und
    damit durch git geschuetzt.
  * Hash `474534577e…` - 3 Dateien (Multi-Root-Sitzung): `ghidra-harness.md` und
    `harness-dev.md` (132 KB mit allen R13*-Erkenntnissen).  Fuer dieses Profil gibt es
    **keinen** Spiegel - es existiert genau EINMAL.  Wird die Datei verkuerzt, ist das
    Wissen weg (genau die Gefahr aus `AGENTS.md`).

Dieses Werkzeug legt darum von JEDEM gefundenen Profil eine Kopie an.

WEGGELASSEN
    Es wird nichts darueber geprueft, ob ein Inhalt richtig, vollstaendig oder aktuell ist -
    nur kopiert und gehasht.
NICHT ZULAESSIG
    Aussagen darueber, welches Profil "das echte" ist.  Gesichert wird alles, was da ist;
    ein kuenftiges Profil mit anderem Hash wird automatisch mitgenommen.

Verhalten: legt `backups/memory-<YYYY-MM-DD_HHMM>/` an, je Profil einen Unterordner
`profil-<erste 8 Hashzeichen>/`, dazu `_manifest.txt` mit Groesse und SHA-256 je Datei.
Danach wird JEDE Kopie erneut gehasht und gegen das Original geprueft.  Ein vorhandener
Zielordner wird NIE ueberschrieben - derselbe Zeitstempel zweimal ist ein Fehler, kein Fall.

Mit `--spiegel` wird zusaetzlich der VERSIONIERTE Spiegel `docs/_memory/` aktualisiert.
`backups/` ist ungetrackt und liegt auf derselben Platte - gegen Plattenverlust hilft nur
git.  Der Spiegel schreibt nur Dateien neu, deren Inhalt sich geaendert hat, und LOESCHT
NIE etwas: verschwindet eine Profildatei, wird sie gemeldet, nicht entfernt.

Aufruf:

    python tools/memory_sichern.py                 # nur lokale Sicherung
    python tools/memory_sichern.py --spiegel       # Sicherung + versionierter Spiegel
    python tools/memory_sichern.py --trocken       # nur zeigen, was kopiert wuerde
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Wo die Profile liegen.  `$APPDATA` wird aufgeloest, damit nichts fest verdrahtet ist.
PROFIL_MUSTER = "Code/User/workspaceStorage/*/GitHub.copilot-chat/memory-tool/memories/repo"
# Zielordner: neben dem Harness, nicht darin - Sicherungen gehoeren nicht ins Repo.
SICHERUNG = Path(__file__).resolve().parent.parent / "backups"
# Versionierter Spiegel IM Repo (git-geschuetzt, per Push off-site).
SPIEGEL = Path(__file__).resolve().parent.parent / "docs" / "_memory"


def profile_finden() -> list[Path]:
    """Alle vorhandenen `memories/repo`-Ordner, stabil sortiert."""
    appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    treffer = [p for p in Path(appdata).glob(PROFIL_MUSTER) if p.is_dir()]
    return sorted(treffer, key=lambda p: str(p))


def hash_und_groesse(p: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for stueck in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(stueck)
    return h.hexdigest(), p.stat().st_size


def hashname(profil: Path) -> str:
    """`474534577e` aus `…/workspaceStorage/<32 Hex>/GitHub.copilot-chat/…`.

    GEMESSEN: VS Code benutzt **32** Hexzeichen, nicht 64 - mit der falschen Laenge fiel
    die Erkennung durch und alle drei Profile hiessen `profil-GitHub.c` (Kollision).
    """
    for teil in profil.parts:
        t = teil.lower()
        if len(t) == 32 and all(z in "0123456789abcdef" for z in t):
            return t[:8]
    return "ohne-hash"


def freier_name(ziel: Path, basis: str) -> Path:
    """`ziel/basis`, sonst `basis-2`, `basis-3` … - nie ein vorhandener Ordner."""
    kandidat = ziel / basis
    k = 2
    while kandidat.exists():
        kandidat = ziel / f"{basis}-{k}"
        k += 1
    return kandidat


def sichern(trocken: bool) -> int:
    profile = profile_finden()
    if not profile:
        print("KEIN Profil gefunden - Muster:", PROFIL_MUSTER)
        return 1
    stempel = datetime.now().strftime("%Y-%m-%d_%H%M")
    ziel = SICHERUNG / f"memory-{stempel}"
    print(f"Profile: {len(profile)}")
    for p in profile:
        dateien = sorted(f for f in p.iterdir() if f.is_file())
        print(f"  {hashname(p)}  {len(dateien):>3} Datei(en)  {p}")
    if ziel.exists():
        print(f"ABBRUCH: {ziel} ist schon da - nichts wird ueberschrieben. "
              "Eine Minute warten und erneut starten.")
        return 1
    if trocken:
        print(f"\n--trocken: Ziel waere {ziel} - kein Schreiben.")
        return 0
    ziel.mkdir(parents=True, exist_ok=False)
    zeilen = [f"# Memory-Sicherung {datetime.now().isoformat(timespec='seconds')}",
              f"# Profile: {len(profile)}", ""]
    gesamt = 0
    fehler: list[str] = []
    for p in profile:
        unter = freier_name(ziel, f"profil-{hashname(p)}")
        unter.mkdir()
        for quelle in sorted(f for f in p.iterdir() if f.is_file()):
            kopie = unter / quelle.name
            shutil.copy2(quelle, kopie)          # copy2: Zeitstempel mitnehmen
            vor_hash, vor_groesse = hash_und_groesse(quelle)
            nach_hash, nach_groesse = hash_und_groesse(kopie)
            if (vor_hash, vor_groesse) != (nach_hash, nach_groesse):
                fehler.append(f"{quelle.name}: Kopie weicht ab "
                              f"({vor_hash[:12]} gegen {nach_hash[:12]})")
            zeilen.append(f"{nach_hash}  {nach_groesse:>9}  "
                          f"profil-{hashname(p)}/{quelle.name}")
            gesamt += 1
        zeilen.append("")
    manifest = ziel / "_manifest.txt"
    manifest.write_text("\n".join(zeilen) + "\n", encoding="utf-8", newline="\n")
    print(f"\n{gesamt} Datei(en) kopiert, jede einzeln nachgehasht.")
    print(f"Sicherung : {ziel}")
    print(f"Manifest  : {manifest}")
    if fehler:
        print("ABWEICHUNGEN:")
        for f in fehler:
            print("  " + f)
        return 1
    print("Pruefung : alle Kopien identisch (SHA-256 und Groesse).")
    return 0


def spiegeln(profile: list[Path], trocken: bool) -> int:
    """`docs/_memory/profil-<hash>/` aktualisieren - nur Geaendertes, nie loeschen."""
    neu, gleich, gemeldet = 0, 0, []
    for p in profile:
        unter = SPIEGEL / f"profil-{hashname(p)}"
        if not trocken:
            unter.mkdir(parents=True, exist_ok=True)
        # ALLE Dateitypen, nicht nur `*.md`: mit `*.md` galt `harness-dev.md.vorher`
        # dauerhaft als "NEU", obwohl sie laengst im Spiegel lag (falsche Meldung).
        vorhanden = {f.name for f in unter.iterdir() if f.is_file()} if unter.is_dir() else set()
        jetzt = {f.name for f in p.iterdir() if f.is_file()}
        for name in sorted(jetzt - vorhanden):
            gemeldet.append(f"NEU   profil-{hashname(p)}/{name}")
        for name in sorted(vorhanden - jetzt):
            gemeldet.append(f"WEG   profil-{hashname(p)}/{name}  (im Profil nicht mehr da; "
                            "bleibt im Spiegel stehen)")
        for quelle in sorted(f for f in p.iterdir() if f.is_file()):
            ziel = unter / quelle.name
            if ziel.is_file() and hash_und_groesse(ziel) == hash_und_groesse(quelle):
                gleich += 1
                continue
            neu += 1
            if not trocken:
                shutil.copy2(quelle, ziel)
    for z in gemeldet:
        print("  " + z)
    print(f"  Spiegel: {neu} neu/geaendert, {gleich} unveraendert "
          f"({SPIEGEL})" + ("  [--trocken, nichts geschrieben]" if trocken else ""))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--trocken", action="store_true",
                    help="nur zeigen, was kopiert wuerde - schreibt nichts")
    ap.add_argument("--spiegel", action="store_true",
                    help="zusaetzlich den versionierten Spiegel docs/_memory/ aktualisieren")
    args = ap.parse_args(argv)
    if args.spiegel:
        print(f"\n=== versionierter Spiegel ({SPIEGEL}) ===")
        return spiegeln(profile_finden(), args.trocken)
    return sichern(args.trocken)


if __name__ == "__main__":
    sys.exit(main())
