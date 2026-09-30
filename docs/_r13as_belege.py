"""R13as: Reihenfolge-Waechter rueckwirkend ueber B208-B219 (MESSUNG, nur lesend).

Der Auftrag (Aussensicht-Befund M218-1) verlangt die Auswertung der vorhandenen
Mitschnitte: wann kam der Vorhersage-Commit, und welche Werkzeugaufrufe haben VORHER
unter `port/` geschrieben? Erwartet wurden laut Aussensicht mindestens B208, B209,
B214 und B218.

Aufruf: python -u docs/_r13as_belege.py             (gibt aus)
        python -u docs/_r13as_belege.py schreiben   (schreibt docs/_r13as_belege.txt)

Warum selbst schreiben: `| Out-File -Encoding utf8` laeuft ueber die Konsole und
verstuemmelt Umlaute (gemessen: `REIHENFOLGE-WAECHTER` kam als `REIHENFOLGE-W─CHTER` an).
"""

from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
HARNESS = HIER.parent / "harness"
sys.path.insert(0, str(HARNESS))

from hx import reihenfolge as rf, streamjson                    # noqa: E402
from hx.config import load_config                                # noqa: E402

BATCHES = list(range(208, 220))
ZIEL = HIER / "_r13as_belege.txt"


def stats_pfad(cfg, b: int) -> Path:
    return Path(cfg.sub("runs")) / f"b{b:03d}" / "stream.jsonl"


def einlesen(pfad: Path):
    st = streamjson.StreamStats()
    for z in pfad.read_text(encoding="utf-8", errors="replace").splitlines():
        st.feed(z)
    return st


def bericht() -> None:
    cfg = load_config()
    decomp = cfg.decomp
    try:
        git_zeilen = rf.git_zeilen(cfg)
        gitfehler = ""
    except Exception as exc:                                        # noqa: BLE001
        git_zeilen, gitfehler = [], str(exc)[:200]
    print("R13as: Reihenfolge-Waechter - rueckwirkende Auswertung B208..B219")
    print(f"Repo: {decomp}")
    if gitfehler:
        print(f"GIT NICHT LESBAR: {gitfehler}")
    print()
    kopf = (f"{'Batch':<7}{'Vorhersage':<22}{'vorher':>7}{'mtime':>7}{'Erkundung':>10}"
            f"{'port ges.':>10}{'Aufrufe':>9}  Befund")
    print(kopf)
    print("-" * (len(kopf) + 30))
    belege: list[str] = []
    for b in BATCHES:
        p = stats_pfad(cfg, b)
        if not p.is_file():
            print(f"{'b' + str(b):<7}{'(kein Mitschnitt)':<22}")
            continue
        st = einlesen(p)
        ts = rf.vorhersage_zeitpunkt(git_zeilen, b)
        erg = rf.pruefe_tools(st.tools, b, ts, decomp)
        vor = len(erg["port_vor_vorhersage"])
        mti = len(erg["mtime_manipulation"])
        erk = len(erg["erkundung"])
        befund = "sauber" if not (vor or mti) else "ABWEICHUNG"
        if not ts:
            befund = "kein Vorhersage-Commit"
        print(f"{'b' + str(b):<7}{str(ts or '-'):<22}{vor:>7}{mti:>7}{erk:>10}"
              f"{erg['port_gesamt']:>10}{len(st.tools):>9}  {befund}")
        for t in erg["port_vor_vorhersage"][:6]:
            belege.append(f"   b{b} stream.jsonl:{t['zeile']} {t['ts']} "
                          f"{t['werkzeug']}: {t['pfad']} - {t['grund']}")
        if vor > 6:
            belege.append(f"   b{b} ... und {vor - 6} weitere")
        for t in erg["mtime_manipulation"]:
            belege.append(f"   b{b} mtime stream.jsonl:{t['zeile']} {t['ts']} "
                          f"{t['grund']}: {t['pfad'][:90]}")
    print()
    print("Belege zu den Abweichungen (Zeile im Mitschnitt):")
    print("\n".join(belege) or "   (keine)")
    print()
    b218 = stats_pfad(cfg, 218)
    if b218.is_file():
        st = einlesen(b218)
        ts = rf.vorhersage_zeitpunkt(git_zeilen, 218)
        erg = rf.pruefe_tools(st.tools, 218, ts, decomp)
        print("Vollstaendige Pruefung B218 (so landet es in result.json):")
        print("  Vorhersage-Commit:", ts)
        for c in rf.vorhersage_commits(git_zeilen, 218):
            print(f"    {c['hash'][:9]} {c['zeit']} {c['betreff'][:90]}")
        print(f"  port/-Schreibzugriffe davor: {len(erg['port_vor_vorhersage'])}")
        print(f"  mtime-Befehle: {len(erg['mtime_manipulation'])}")
        print(f"  Erkundung: {len(erg['erkundung'])}")
        print()
        print("  " + rf.fakten_zeile(erg))
        print()
        print(rf.beleg_text(erg, 218))
    print()
    print("Erkundungs-Strang: es gibt weder Branch noch Worktree `erkundung-b*`")
    print("(git branch -a / git worktree list im Decomp-Repo, Stand 2026-09-30).")


def main() -> int:
    if "schreiben" in sys.argv:
        puffer = io.StringIO()
        with contextlib.redirect_stdout(puffer):
            bericht()
        text = puffer.getvalue()
        ZIEL.write_text(text, encoding="utf-8", newline="\n")
        print(f"geschrieben: {ZIEL.name} ({len(text)} Zeichen, UTF-8)")
        return 0
    bericht()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
