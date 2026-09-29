"""Aufbewahrung der Laufprotokolle (R13p).

Auftrag (Nutzer, 2026-09-27): `runs/b<N>/stream.jsonl`, `reviewer.jsonl` und die
Snapshots, die aelter als 14 Tage sind, einmal taeglich als ZIP ablegen - und zwar
nur, wenn KEIN Batch laeuft. Unkomprimiert bleiben die taeglich gebrauchten Dateien
(`result.json`, `harness-facts.md`, `antwort.md`, `auftrag.md`, `review.md`).

Warum ueberhaupt: der Mitschnitt eines Batches ist schnell 30 MB (b180: 32 MB), und
er wird von niemandem geloescht. Gemessen am 2026-09-27 liegen 196 Batches unter
`runs/`. Als ZIP schrumpft so ein Mitschnitt auf wenige MB.

Zusaetzlich: Warnung, wenn auf dem Laufwerk des Harness weniger als 20 GB frei sind.

Wichtig: Wer einen Mitschnitt LIEST (watch, rebuild, die Spurenkunde nach einem
harten Tod), muss auch die gepackte Fassung oeffnen koennen - dafuer sind
`mitschnitt_vorhanden()` und `mitschnitt_zeilen()` da.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .util import ensure_dir, now_iso, write_text_atomic

# Diese Dateien je Batch werden gepackt (die `-v1`-Fassungen eines Re-Runs mit).
MIT_ZIP = ("stream.jsonl", "reviewer.jsonl", "stream-v1.jsonl", "handover.jsonl")
# R13ad: Mitschnitte der Fortsetzungen (`stream-forts<N>.jsonl`, ein File je Anstoss). Die
# Zahl haengt an `[limits] max_fortsetzungen` - deshalb als Muster statt als feste Liste.
MIT_ZIP_MUSTER = "stream-forts*.jsonl"
SNAPSHOT_NAME = "snapshots"

ALTER_TAGE = 14.0
FREI_WARN_GB = 20.0
# Je Tag wird nur eine begrenzte Menge gepackt: der erste Lauf nach dieser Aenderung
# haette sonst hunderte Dateien vor sich und wuerde die Schleife lange aufhalten.
MAX_EINHEITEN = 6
TAGE_ZWISCHEN_LAEUFEN = 20 / 24      # einmal taeglich


# --------------------------------------------------------------- Lesen (ZIP-fest)
def mitschnitt_vorhanden(pfad) -> Path | None:
    """Die vorhandene Datei: entweder `<name>` oder `<name>.zip` (sonst None)."""
    p = Path(pfad)
    if p.is_file():
        return p
    z = Path(str(p) + ".zip")
    return z if z.is_file() else None


def mitschnitt_zeilen(pfad) -> list[str] | None:
    """Zeilen eines Mitschnitts - aus der Datei oder aus dem ZIP.

    `None` heisst: gar nichts vorhanden. Ein Lesefehler im ZIP gibt ebenfalls `None`
    (der Aufrufer soll dann melden, dass er nichts zeigen kann - nicht abstuerzen).
    """
    p = Path(pfad)
    if p.is_file():
        return p.read_text(encoding="utf-8", errors="replace").splitlines()
    z = Path(str(p) + ".zip")
    if not z.is_file():
        return None
    try:
        with zipfile.ZipFile(z) as zf:
            namen = zf.namelist()
            name = p.name if p.name in namen else (namen[0] if namen else "")
            if not name:
                return None
            return zf.read(name).decode("utf-8", errors="replace").splitlines()
    except (OSError, zipfile.BadZipFile, KeyError):
        return None


# --------------------------------------------------------------------- Packen
def _weg(pfad: Path) -> None:
    """Loeschen, auch wenn (Git-)Dateien schreibgeschuetzt sind."""
    def zwingend(func, path):
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except OSError:
            pass

    if pfad.is_dir():
        if sys.version_info >= (3, 12):
            shutil.rmtree(pfad, onexc=lambda f, p, _e: zwingend(f, p))
        else:                                                       # pragma: no cover
            shutil.rmtree(pfad, onerror=lambda f, p, _e: zwingend(f, p))
    else:
        try:
            pfad.unlink()
        except OSError:
            pass


def zip_datei(p: Path, log=None) -> tuple[bool, int, int]:
    """Eine Datei packen - Original erst loeschen, wenn das ZIP geprueft ist.

    Geprueft wird die Pruefsumme (`testzip`) UND die Groesse des Eintrags: ein
    abgebrochenes ZIP darf keine Daten kosten.
    """
    z = Path(str(p) + ".zip")
    try:
        vorher = p.stat().st_size
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            zf.write(p, arcname=p.name)
        with zipfile.ZipFile(z) as zf:
            if zf.testzip() is not None:
                raise OSError("Pruefsumme im ZIP stimmt nicht")
            entpackt = zf.getinfo(p.name).file_size
        if entpackt != vorher:
            raise OSError(f"Groesse weicht ab: ZIP {entpackt} != Datei {vorher}")
        nachher = z.stat().st_size
        _weg(p)
        if log:
            log.info("Mitschnitt gepackt", datei=p.name, mb_vorher=round(vorher / 1e6, 1),
                     mb_nachher=round(nachher / 1e6, 1))
        return True, vorher, nachher
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        if log:
            log.warn("Packen fehlgeschlagen - Datei bleibt liegen", datei=str(p),
                     fehler=str(exc)[:150])
        try:
            z.unlink()                      # halbes ZIP nicht liegen lassen
        except OSError:
            pass
        return False, 0, 0


def zip_ordner(d: Path, log=None) -> tuple[bool, int, int]:
    """Einen Ordner (Snapshots eines Batches) packen - mit derselben Pruefung."""
    z = d.with_suffix(".zip")
    try:
        dateien = [p for p in sorted(d.rglob("*")) if p.is_file()]
        if not dateien:
            return False, 0, 0
        vorher = sum(p.stat().st_size for p in dateien)
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for p in dateien:
                zf.write(p, arcname=str(p.relative_to(d)).replace("\\", "/"))
        with zipfile.ZipFile(z) as zf:
            if zf.testzip() is not None:
                raise OSError("Pruefsumme im ZIP stimmt nicht")
            entpackt = sum(i.file_size for i in zf.infolist())
        if entpackt != vorher:
            raise OSError(f"Groesse weicht ab: ZIP {entpackt} != Ordner {vorher}")
        nachher = z.stat().st_size
        _weg(d)
        if log:
            log.info("Snapshots gepackt", ordner=d.name, mb_vorher=round(vorher / 1e6, 1),
                     mb_nachher=round(nachher / 1e6, 1))
        return True, vorher, nachher
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        if log:
            log.warn("Packen fehlgeschlagen - Ordner bleibt liegen", ordner=str(d),
                     fehler=str(exc)[:150])
        try:
            z.unlink()
        except OSError:
            pass
        return False, 0, 0


# ------------------------------------------------------------------ Auswahl/Lauf
def kandidaten(cfg, tage: float = ALTER_TAGE, jetzt: datetime | None = None) -> list[Path]:
    """Dateien und Ordner, die aelter als `tage` sind (aelteste zuerst)."""
    jetzt = jetzt or datetime.now(timezone.utc)
    grenze = jetzt - timedelta(days=tage)
    out: list[tuple[float, Path]] = []
    runs = Path(cfg.sub("runs"))
    if runs.is_dir():
        for bdir in sorted(runs.glob("b*")):
            if not bdir.is_dir():
                continue
            dateien = [bdir / name for name in MIT_ZIP] + list(bdir.glob(MIT_ZIP_MUSTER))
            for p in dateien:
                if p.is_file() and p.stat().st_mtime < grenze.timestamp():
                    out.append((p.stat().st_mtime, p))
    snaps = Path(cfg.sub(SNAPSHOT_NAME))
    if snaps.is_dir():
        for sdir in sorted(snaps.glob("b*")):
            if sdir.is_dir() and sdir.stat().st_mtime < grenze.timestamp():
                out.append((sdir.stat().st_mtime, sdir))
    return [p for _t, p in sorted(out)]


def frei_gb(cfg) -> float:
    """Freier Platz auf dem Laufwerk des Harness in GB (-1, wenn nicht messbar)."""
    try:
        return shutil.disk_usage(str(cfg.root)).free / (1024 ** 3)
    except OSError:
        return -1.0


def lauf(cfg, log=None, notify=None, tage: float = ALTER_TAGE,
         max_einheiten: int = MAX_EINHEITEN, jetzt: datetime | None = None) -> dict:
    """Einen Aufraeumlauf fahren. Rueckgabe: Kennzahlen fuer Zustand und Bericht."""
    alle = kandidaten(cfg, tage, jetzt)
    gezippt: list[str] = []
    gespart = 0
    fehler = 0
    for p in alle[:max_einheiten]:
        ok, vorher, nachher = (zip_ordner(p, log) if p.is_dir() else zip_datei(p, log))
        if ok:
            gezippt.append(p.name)
            gespart += max(0, vorher - nachher)
        else:
            fehler += 1
    frei = frei_gb(cfg)
    warnung = ""
    if 0 <= frei < FREI_WARN_GB:
        warnung = (f"WENIG PLATZ: auf {cfg.root.drive or cfg.root} sind nur noch "
                   f"{frei:.1f} GB frei (Warnschwelle {FREI_WARN_GB:.0f} GB). "
                   f"Alte Mitschnitte liegen als ZIP unter {cfg.sub('runs')} und "
                   f"{cfg.sub(SNAPSHOT_NAME)}.")
        if log:
            log.warn("Wenig Platz auf dem Laufwerk", frei_gb=round(frei, 1))
    rest = max(0, len(alle) - len(gezippt) - fehler)
    if log:
        log.info("Aufbewahrung gelaufen", gezippt=len(gezippt), uebrig=rest,
                 fehler=fehler, gespart_mb=round(gespart / 1e6, 1), frei_gb=round(frei, 1))
    if notify and (gezippt or warnung):
        text = (f"Aufbewahrung: {len(gezippt)} Mitschnitt(e) gepackt, "
                f"{round(gespart / 1e6, 1)} MB gespart"
                + (f", {rest} folgen morgen" if rest else ""))
        notify(text + ("\n" + warnung if warnung else ""))
    return {"ts": now_iso(), "gezippt": len(gezippt), "namen": gezippt, "uebrig": rest,
            "fehler": fehler, "gespart_mb": round(gespart / 1e6, 1),
            "frei_gb": round(frei, 1), "warnung": warnung, "kandidaten": len(alle)}


def faellig(cfg, state, jetzt: datetime | None = None) -> bool:
    """Ist der taegliche Lauf faellig? (Merker liegt im Zustand, ueberlebt Neustart.)"""
    jetzt = jetzt or datetime.now(timezone.utc)
    letzter = (state.data.get("retention") or {}).get("ts")
    if not letzter:
        return True
    try:
        wann = datetime.fromisoformat(str(letzter).replace("Z", "+00:00"))
    except ValueError:
        return True
    return (jetzt - wann) >= timedelta(days=TAGE_ZWISCHEN_LAEUFEN)


def bericht(cfg) -> str:
    """Kurze Zeile fuer /status (leer, wenn noch nie gelaufen)."""
    d = {}
    p = Path(cfg.sub("logs")) / "retention.json"
    if p.is_file():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            d = {}
    if not d:
        return ""
    return (f"{d.get('gezippt')} gepackt am {d.get('ts')}, "
            f"{d.get('gespart_mb')} MB gespart, {d.get('uebrig')} offen, "
            f"{d.get('frei_gb')} GB frei")


def schreibe_bericht(cfg, res: dict) -> Path:
    """Den letzten Lauf ablegen (fuer /status, ohne den Zustand aufzublaehen)."""
    p = Path(cfg.sub("logs")) / "retention.json"
    ensure_dir(p.parent)
    return write_text_atomic(p, json.dumps(res, ensure_ascii=False, indent=1) + "\n")
