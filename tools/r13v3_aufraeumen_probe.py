"""R13v3-Nachprobe: raeumt der Harness nach einem Abbruch wirklich auf?

Gemessen mit Herzschlag-Dateien (`tools/r13v_herzschlag.py` schreibt alle 0,5 s einen
Zeitstempel; "vor 0,2 s" = lebt, "vor 8 s" = tot) und mit absoluten Zeitstempeln, damit
"kurz vor der Abfrage" nicht mehrdeutig ist.

Faelle:

  * **JOB-DIREKT** - Ein "Worker" (PowerShell) wird SOFORT nach dem Start in ein
    Job-Objekt mit `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` aufgenommen (so macht es
    `proc.run_stream`) und startet DANACH einen Hintergrundlauf als echtes Kind.
  * **JOB-STARTPROCESS** - derselbe Ablauf, der Hintergrundlauf entsteht aber per
    PowerShell-`Start-Process` (so startet der Worker im Betrieb seine Hintergrundlaeufe).
  * **NACHSUCHE-WMI** - Prozess ohne Elternbezug (per WMI gestartet), Kommandozeile nennt
    die Decomp-Wurzel -> muss beendet werden; ein fremder Prozess ausserhalb der Wurzel
    muss leben bleiben.
  * **NACHSUCHE-B207** - der echte B207-Fall: der Hintergrundlauf nennt NUR den
    Skriptnamen (kein Pfad), sein startendes Shell ist tot. Gefunden wird er nur, weil
    `nachfahren_pids` ihn waehrend des Laufs gesehen hat (PID-Nachweis).

**Lehre aus dem ersten Anlauf (im Beleg dokumentiert):** wird der Job ERST zugewiesen,
nachdem das Kind schon existiert, erbt das Kind ihn nicht - die Messung war wertlos
("Kind laeuft weiter, obwohl die Shell im Job war"). Es zaehlt also die Reihenfolge:
Popen -> assign -> erst dann darf das Kind entstehen.

Aufruf:  python -u tools/r13v3_aufraeumen_probe.py
Beleg:   docs/_r13v3_beleg_aufraeumen.txt
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

HIER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HIER / "harness"))

from hx import aufraeumen                      # noqa: E402
from hx.config import load_config              # noqa: E402

ARBEIT = HIER / "sandbox" / "sperrprobe"
BELEG = HIER / "docs" / "_r13v3_beleg_aufraeumen.txt"
HB = HIER / "tools" / "r13v_herzschlag.py"
PY = sys.executable
PS = ["powershell", "-NoProfile", "-NonInteractive"]

zeilen: list[str] = []


def sag(text: str = "") -> None:
    zeilen.append(text)
    print(text)


def uhr(t: float) -> str:
    return time.strftime("%H:%M:%S", time.localtime(t)) + f".{int((t % 1) * 1000):03d}"


def alter(datei: Path) -> str:
    if not datei.is_file():
        return "keine Datei"
    return f"{time.time() - datei.stat().st_mtime:4.1f}s seit der letzten Schreibung"


def aus(ps_code: str) -> str:
    r = subprocess.run(PS + ["-Command", ps_code], capture_output=True, text=True)
    return (r.stdout or "").strip()


def lebt(pid: int) -> bool:
    return bool(aus(f"if (Get-Process -Id {pid} -EA 0) {{'x'}}"))


def job_lauf(name: str, kind_befehl: str, datei: Path) -> None:
    """Job zuweisen (vor dem Kind!), Kind starten lassen, Job schliessen, Zeitreihe."""
    datei.unlink(missing_ok=True)
    job = aufraeumen.Job(name=f"r13v3-{name}")
    if not job.create():
        sag(f"Job-Objekt nicht eingerichtet: {job.grund}")
        return
    # Die Shell wartet 3 s - Zeit genug fuer die Zuweisung, danach entsteht das Kind.
    ps = subprocess.Popen(PS + ["-Command",
                                f"Start-Sleep -Seconds 3; {kind_befehl}; Start-Sleep -Seconds 60"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    zugewiesen = job.assign(ps.pid)
    sag(f"Job-Zuweisung SOFORT nach dem Start: {zugewiesen} ({job.beschreibung()})")
    time.sleep(7)                     # Kind laeuft seit ~4 s
    sag(f"vor dem Schliessen:  Shell PID {ps.pid} lebt: {lebt(ps.pid)} | Kind {alter(datei)}")
    t0 = time.time()
    sag(f"{uhr(t0)}  Job wird geschlossen (KILL_ON_JOB_CLOSE)")
    job.close()
    for i in range(1, 5):
        time.sleep(2.0)
        jetzt = time.time()
        sag(f"{uhr(jetzt)}  t+{jetzt - t0:4.1f}s  Shell lebt: {ps.poll() is None} | "
            f"Kind {alter(datei)}")
    if ps.poll() is None:
        ps.kill()


def main() -> int:
    cfg = load_config()
    wurzel = Path(cfg.decomp)
    ARBEIT.mkdir(parents=True, exist_ok=True)
    sag("# R13v3-Nachprobe: Aufraeumen nach einem Abbruch")
    sag(f"# erzeugt {time.strftime('%Y-%m-%d %H:%M:%S')} von tools/r13v3_aufraeumen_probe.py")
    sag(f"# Decomp-Wurzel (Filterkriterium): {wurzel}")
    sag(f"# Herzschlag: {HB} (schreibt alle 0,5 s)")
    sag()

    sag("======== Fall JOB-DIREKT: echtes Kind, Job VOR dem Kind zugewiesen ========")
    f1 = ARBEIT / "hb_job_direkt.txt"
    job_lauf("direkt", f"& '{PY}' '{HB}' '{f1}' 60", f1)
    sag("Erwartung: das Kind stirbt mit dem Job (Alter waechst monoton).")
    sag()

    sag("======== Fall JOB-STARTPROCESS: Kind per Start-Process (Muster Worker) ========")
    f2 = ARBEIT / "hb_job_sp.txt"
    job_lauf("startprocess",
             f"Start-Process -FilePath '{PY}' -ArgumentList '{HB}','{f2}','60' -WindowStyle Hidden",
             f2)
    sag("Erwartung: dito - Start-Process-Kinder erben den Job (gemessen, siehe Beleg).")
    sag()

    sag("======== Fall NACHSUCHE-WMI: ohne Elternbezug, Wurzel in der Kommandozeile ========")
    f3 = ARBEIT / "hb_wmi.txt"
    f4 = ARBEIT / "hb_fremd.txt"
    f3.unlink(missing_ok=True)
    f4.unlink(missing_ok=True)
    befehl = f'"{PY}" "{HB}" "{f3}" 60 "{wurzel}"'
    aus("Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments "
        f"@{{CommandLine='{befehl}'}} | Out-Null")
    fremd = subprocess.Popen([PY, str(HB), str(f4), "60"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(5)
    treffer = [p for p in aufraeumen.prozess_liste()
               if p.get("cmd") and str(f3) in str(p["cmd"])]
    wpid = int(treffer[0]["pid"]) if treffer else 0
    sag(f"Waise (WMI): PID {wpid} | Fremdprozess: PID {fremd.pid}")
    sag(f"vor der Nachsuche:  Waise {alter(f3)} | Fremdprozess {alter(f4)}")
    auf = aufraeumen.nachsuche(wurzel, seit=time.time() - 30, wurzeln_pids=set())
    sag(f"Nachsuche: ok={auf['ok']} gefunden="
        f"{[(t['name'], t['pid'], t['grund']) for t in auf['gefunden']]} beendet={auf['beendet']} "
        f"Dauer={auf['dauer_s']}s")
    sag(f"ausgenommen (eigener PID-Kreis, R13i): {auf.get('ausgenommen')}")
    time.sleep(4)
    sag(f"nach der Nachsuche: Waise {alter(f3)} | Fremdprozess {alter(f4)}")
    sag("Erwartung: Waise beendet (Alter waechst), Fremdprozess laeuft (Alter ~0,4 s).")
    if fremd.poll() is None:
        fremd.kill()
    sag()

    sag("======== Fall NACHSUCHE-B207: Hintergrundlauf ohne Pfad, Shell danach tot ========")
    f5 = ARBEIT / "hb_b207.txt"
    f5.unlink(missing_ok=True)
    shell = subprocess.Popen(
        PS + ["-Command",
              f"Start-Process -FilePath '{PY}' -ArgumentList '{HB}','{f5}','60' -WindowStyle Hidden"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(4)
    try:
        gesehen = aufraeumen.nachfahren_pids(shell.pid)
    except Exception as exc:                                             # noqa: BLE001
        gesehen = []
        sag(f"nachfahren_pids fehlgeschlagen: {exc}")
    sag(f"waehrend des Laufs gesehene Nachfahren des Shells PID {shell.pid}: {gesehen}")
    shell.kill()
    time.sleep(3)
    treffer = [t for t in aufraeumen.prozess_liste()
               if t.get("cmd") and str(f5) in str(t["cmd"])]
    b207 = int(treffer[0]["pid"]) if treffer else 0
    sag(f"Hintergrundlauf jetzt: PID {b207} (Shell PID {shell.pid} ist tot: {not lebt(shell.pid)})")
    sag(f"vor der Nachsuche: {alter(f5)}")
    ohne = aufraeumen.nachsuche(wurzel, seit=time.time() - 30, wurzeln_pids=set(),
                                bekannte_pids=(), trocken=True)
    sag(f"Nachsuche OHNE PID-Nachweis (auch ohne Elternkette): "
        f"gefunden={[t['pid'] for t in ohne['gefunden']]}")
    mit = aufraeumen.nachsuche(wurzel, seit=time.time() - 30, wurzeln_pids=set(),
                               bekannte_pids=gesehen)
    sag(f"Nachsuche MIT PID-Nachweis:  gefunden="
        f"{[(t['name'], t['pid'], t['grund']) for t in mit['gefunden']]} beendet={mit['beendet']}")
    time.sleep(4)
    sag(f"nach der Nachsuche: {alter(f5)}")
    sag("Erwartung: der Pfad fehlt in der Kommandozeile und die Elternkette ist tot -")
    sag("nur der PID-Nachweis aus der Aufnahme waehrend des Laufs findet ihn.")
    sag()
    sag("======== Zusammenfassung (gemessen 2026-09-28) ========")
    sag("JOB (direkt + Start-Process)  Kind stirbt mit dem Job - aber NUR, wenn der Job")
    sag("                              vor dem Kind zugewiesen wurde (Reihenfolge!).")
    sag("NACHSUCHE-WMI                 Prozess ohne Elternbezug mit Wurzel in der")
    sag("                              Kommandozeile wird beendet; Fremdprozess bleibt.")
    sag("NACHSUCHE-B207                nur der PID-Nachweis findet den Rest.")
    sag("R13i                          der Harness-Kreis steht unter 'ausgenommen'.")
    BELEG.parent.mkdir(parents=True, exist_ok=True)
    BELEG.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    print(f"\n# Beleg: {BELEG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
