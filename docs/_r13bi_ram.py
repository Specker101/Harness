"""R13bi (nur lesend): RAM-Bedarf von `c_kopf.exe` und `hybrid_lauf.exe`.

Frage (Nutzerauftrag 2026-10-01): koennen `c_kopf.exe` (aus `c_kopf_check`) und
`hybrid_lauf.exe` (aus `m212_zeilen`) GLEICHZEITIG laufen - gegen ~1 GB freien Speicher?

Gemessen wird die **Spitze des RSS** jedes Prozesses, einmal allein und einmal
gleichzeitig. Es wird NICHTS geschrieben: `hybrid_lauf.exe` schreibt nur mit `--s-log`,
`c_kopf.exe` gibt auf stdout aus (beide Aufrufe wie im Preflight ohne Ausgabeschalter);
der Lauf ist kurz (2M Schritte bzw. EIN Kopf).

    python -u docs/_r13bi_ram.py        -> docs/_r13bi_ram.txt
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import time

DEC = pathlib.Path("g:/Silent Scope Decomp")
HARNESS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEC / "scripts"))

import c_kopf                                                       # noqa: E402

ROM = DEC / "rom" / "build" / "830d01.27p.be.bin"
C_KOPF = DEC / "port" / "build" / "c_kopf.exe"
HYBRID = DEC / "port" / "build" / "hybrid_lauf.exe"
SCHRITTE = 2000000
PROFILE = DEC / "analysis" / "_m197" / "_ck_09DE0.case"


def _psutil():
    import psutil
    return psutil


def _frei_mb() -> float:
    return _psutil().virtual_memory().available / 1048576.0


class Lauf:
    """Ein gestarteter Prozess mit RSS-Spitze."""

    def __init__(self, name: str, argv: list[str]):
        self.name = name
        self.argv = argv
        self.proc: subprocess.Popen | None = None
        self.spitze = 0.0
        self.start = 0.0

    def starten(self) -> None:
        self.start = time.time()
        self.proc = subprocess.Popen(self.argv, cwd=str(DEC), stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)

    def messen(self) -> bool:
        """RSS aufnehmen; `False`, wenn der Prozess fertig ist."""
        if self.proc is None:
            return False
        if self.proc.poll() is not None:
            return False
        try:
            rss = _psutil().Process(self.proc.pid).memory_info().rss / 1048576.0
            self.spitze = max(self.spitze, rss)
        except Exception:                                          # noqa: BLE001
            pass
        return True

    def warten(self, grenze_s: float = 600.0) -> float:
        while time.time() - self.start < grenze_s:
            if not self.messen():
                break
            time.sleep(0.2)
        if self.proc is not None and self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait(timeout=30)
        return time.time() - self.start


def _durchlauf(lauefe: list[Lauf], grenze_s: float = 600.0) -> tuple[float, float]:
    frei0 = _frei_mb()
    frei_min = frei0
    for l in lauefe:
        l.starten()
    while any(l.proc is not None and l.proc.poll() is None for l in lauefe):
        for l in lauefe:
            l.messen()
        frei_min = min(frei_min, _frei_mb())
        if time.time() - max(l.start for l in lauefe) > grenze_s:
            break
        time.sleep(0.2)
    for l in lauefe:
        if l.proc is not None and l.proc.poll() is None:
            l.proc.kill()
            l.proc.wait(timeout=30)
    return frei0, frei_min


def main() -> int:
    z: list[str] = []
    z.append("R13bi - RAM-Bedarf der zwei Port-Laeufe (nur lesend)")
    z.append(f"Binaerien: {C_KOPF.name} (ein Kopf {PROFILE.name}), "
             f"{HYBRID.name} --schritte {SCHRITTE}")
    z.append(f"ROM: {ROM.name}, Profil: {PROFILE.name} (vorhanden: "
             f"{PROFILE.is_file()})")
    z.append("")
    z.append(f"freier Speicher VOR allen Messungen: {_frei_mb():.0f} MB")
    for l in (C_KOPF, HYBRID):
        if not l.is_file():
            z.append(f"FEHLT: {l}")
    einzel: dict[str, float] = {}
    for name, argv in (("c_kopf.exe (1 Kopf)", [str(C_KOPF), str(ROM), str(PROFILE)]),
                       ("hybrid_lauf.exe (2M)", [str(HYBRID), "--schritte", str(SCHRITTE)])):
        l = Lauf(name, argv)
        frei0, frei_min = _durchlauf([l])
        einzel[name] = l.spitze
        z.append(f"  allein: {name:<24} Spitze {l.spitze:>7.1f} MB RSS   "
                 f"Dauer {time.time() - l.start:>5.1f} s   frei min {frei_min:>6.0f} MB "
                 f"(vorher {frei0:.0f})")
    z.append("")
    a = Lauf("c_kopf.exe (1 Kopf)", [str(C_KOPF), str(ROM), str(PROFILE)])
    b = Lauf("hybrid_lauf.exe (2M)", [str(HYBRID), "--schritte", str(SCHRITTE)])
    t0 = time.time()
    frei0, frei_min = _durchlauf([a, b])
    dauer = time.time() - t0
    z.append("  GLEICHZEITIG:")
    z.append(f"    {a.name:<24} Spitze {a.spitze:>7.1f} MB RSS")
    z.append(f"    {b.name:<24} Spitze {b.spitze:>7.1f} MB RSS")
    z.append(f"    Summe der Spitzen      {a.spitze + b.spitze:>7.1f} MB")
    z.append(f"    Dauer gemeinsam {dauer:.1f} s   freier Speicher {frei0:.0f} -> "
             f"min {frei_min:.0f} MB (Abnahme {frei0 - frei_min:.0f} MB)")
    z.append("")
    z.append("Einordnung: gemessen mit KURZEN Laeufen (2M statt 200M Schritte, EIN Kopf")
    z.append("statt 115). Der RSS ist vom geladenen Programm/Zustand bestimmt, nicht von")
    z.append("der Schritt- oder Kopfzahl - die Spitze ist also die relevante Groesse.")
    text = "\n".join(z) + "\n"
    ziel = HARNESS / "docs" / "_r13bi_ram.txt"
    ziel.write_text(text, encoding="utf-8", newline="\n")
    print(text)
    print(f"Beleg: {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
