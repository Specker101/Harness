r"""Aufraeumen nach einem Worker-Lauf (R13v3, 2026-09-28).

Zwei Ebenen, weil eine allein nicht reicht (gemessen, `docs/_r13v_waise.txt`):

1. **Job-Objekt mit `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`.** Der Worker-Prozess wird
   SOFORT nach dem Start (vor seinem ersten Kind) dem Job zugewiesen, so wie es
   `proc.run_stream` tut. Schliesst der Harness den Job am Ende des Laufs, beendet
   Windows alles, was darin laeuft - gemessen auch einen per PowerShell-`Start-Process`
   gestarteten Hintergrundlauf (`docs/_r13v3_beleg_aufraeumen.txt`, Faelle JOB-DIREKT
   und JOB-STARTPROCESS). **Die Reihenfolge ist tragend:** wird der Job erst zugewiesen,
   nachdem das Kind schon existiert, erbt es ihn nicht (erster Messanlauf, im Beleg).

2. **Nachsuche** fuer das, was ein Job-Objekt nicht fassen kann: Prozesse ohne
   Elternbezug (per WMI `Win32_Process.Create` gestartet, Muster B207-PID 4996) landen
   nicht im Job, und bei einem gescheiterten `AssignProcessToJobObject` (verschachtelte
   Jobs) ist die Nachsuche der einzige Riegel. Ein Kandidat muss DREIFACH belegt sein:
   Name aus der Liste der Arbeitsprozesse, juenger als der Batch-Start und
   (a) die Decomp-Wurzel in der Kommandozeile ODER
   (b) waehrend des Laufs als Nachfahre des Workers GESEHEN (`nachfahren_pids`,
       alle 60 s aufgenommen - deckt den B207-Fall ab: der Hintergrundlauf nennt nur
       `scripts/c_kopf.py`, sein startendes Shell ist tot) ODER
   (c) direkter Nachfahre eines Prozesses dieses Laufs.
   **Der Harness selbst wird nie getroffen** (R13i-Lehre): eigener PID-Kreis, die
   Vorfahrenkette des Harness und ausdrueckliche Verbotsmuster (`hx.cli`,
   `harness\hx`, `ghidra`) sind ausgenommen.
"""

from __future__ import annotations

import ctypes
import json
import os
import re
import time

from .proc import run_capture

# ---------------------------------------------------------------------------
# 1) Job-Objekt

JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9


class _IoCounters(ctypes.Structure):
    _fields_ = [(n, ctypes.c_ulonglong) for n in
                ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                 "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class _BasicLimitInformation(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", ctypes.c_ulong),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", ctypes.c_ulong),
                ("Affinity", ctypes.POINTER(ctypes.c_ulong)),
                ("PriorityClass", ctypes.c_ulong),
                ("SchedulingClass", ctypes.c_ulong)]


class _ExtendedLimitInformation(ctypes.Structure):
    _fields_ = [("BasicLimitInformation", _BasicLimitInformation),
                ("IoInfo", _IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t)]


class Job:
    """Windows-Job-Objekt fuer den Worker-Lauf. Ausserhalb von Windows ein No-Op."""

    def __init__(self, log=None, name: str = ""):
        self.log = log
        self.name = name or f"harness-worker-{os.getpid()}-{int(time.time())}"
        self.handle = None
        self.ok = False
        self.grund = ""
        self.zugewiesen: list[int] = []

    def create(self) -> bool:
        if os.name != "nt":
            self.grund = "kein Windows - Job-Objekt nicht verfuegbar"
            return False
        try:
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.CreateJobObjectW.restype = ctypes.c_void_p
            h = k32.CreateJobObjectW(None, ctypes.c_wchar_p(self.name))
            if not h:
                self.grund = f"CreateJobObject fehlgeschlagen (err={ctypes.get_last_error()})"
                return False
            info = _ExtendedLimitInformation()
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            ok = k32.SetInformationJobObject(
                ctypes.c_void_p(h), JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                ctypes.byref(info), ctypes.sizeof(info))
            if not ok:
                self.grund = (f"SetInformationJobObject fehlgeschlagen "
                              f"(err={ctypes.get_last_error()})")
                k32.CloseHandle(ctypes.c_void_p(h))
                return False
            self.handle = h
            self.ok = True
            return True
        except Exception as exc:                                     # noqa: BLE001
            self.grund = f"Job-Objekt nicht einrichtbar: {str(exc)[:150]}"
            return False

    def assign(self, pid: int) -> bool:
        """Worker-Prozess in den Job aufnehmen. Scheitert das, bleibt die Nachsuche."""
        if not self.ok or not self.handle:
            return False
        try:
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.OpenProcess.restype = ctypes.c_void_p
            # PROCESS_SET_QUOTA | PROCESS_TERMINATE reichen fuer AssignProcessToJobObject
            h_proc = k32.OpenProcess(0x0100 | 0x0001, False, int(pid))
            if not h_proc:
                self.grund = (f"OpenProcess({pid}) fehlgeschlagen "
                              f"(err={ctypes.get_last_error()})")
                return False
            try:
                ok = k32.AssignProcessToJobObject(ctypes.c_void_p(self.handle),
                                                  ctypes.c_void_p(h_proc))
            finally:
                k32.CloseHandle(ctypes.c_void_p(h_proc))
            if not ok:
                # Haeufigster Fall: der Harness laeuft selbst in einem Job (z. B. aus
                # dem VS-Code-Terminal) und Windows verweigert die Verschachtelung.
                self.grund = (f"AssignProcessToJobObject fehlgeschlagen "
                              f"(err={ctypes.get_last_error()}) - Nachsuche uebernimmt")
                return False
            self.zugewiesen.append(int(pid))
            return True
        except Exception as exc:                                     # noqa: BLE001
            self.grund = f"Zuweisung fehlgeschlagen: {str(exc)[:150]}"
            return False

    def close(self) -> int:
        """Handle schliessen - KILL_ON_JOB_CLOSE beendet alle Reste. Anzahl zugewiesener."""
        if not self.handle:
            return 0
        try:
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.CloseHandle(ctypes.c_void_p(self.handle))
        except Exception:                                            # noqa: BLE001
            pass
        n = len(self.zugewiesen)
        self.handle = None
        self.ok = False
        return n

    def beschreibung(self) -> str:
        if self.zugewiesen:
            return f"Job {self.name}: {len(self.zugewiesen)} Prozessbaum/Prozessbaeume"
        return f"Job {self.name}: nicht verfuegbar ({self.grund or 'unbekannt'})"


# ---------------------------------------------------------------------------
# 2) Nachsuche

# Nur diese Arbeitsprozesse kommen ueberhaupt in Frage. Alles andere (Shells, Editor,
# Ghidra, Windows-Kram) bleibt unangetastet - der Harness ist selbst ein python.exe.
KILL_NAMEN = re.compile(
    r"^(python[0-9.]*|py|g\+\+|gcc|cc1plus|cc1|c\+\+|clang|clang\+\+|ar|as|ld|collect2|"
    r"mingw32-make|make|cmake|ninja|ppc_poc|port_selftest|port_gl)(\.exe)?$", re.IGNORECASE)

# Nie anfassen, egal wie die Regeln sonst greifen (R13i: der Harness starb schon einmal
# an einem pauschalen Prozessabbau des Workers).
NIE_ANFASSEN = ("hx.cli", "hx\\cli.py", "hx/cli.py", "harness\\hx", "harness/hx",
                "ghidra", "code.exe", "bash.exe", "cmd.exe", "conhost")

# Ein Prozess gilt nur als "von diesem Lauf", wenn er nicht deutlich aelter ist als der
# Batch-Start (Sekunden Nachsicht fuer Uhrenungenauigkeit).
ALTER_NACHSICHT_S = 5.0


def _normal(pfad) -> str:
    return str(pfad).replace("/", "\\").rstrip("\\").lower()


def kandidaten(prozesse: list[dict], *, wurzel, seit_s: float, ausgenommen=(),
               wurzeln_pids=(), bekannte_pids=(), max_stufen: int = 12) -> list[dict]:
    """Welche Prozesse muss die Nachsuche beenden? (reine Funktion - testbar)

    `prozesse`  : Liste von dicts mit pid/ppid/name/alter_s/cmd (aus `prozess_liste`)
    `wurzel`    : Pfad des Decomp-Repos (muss in der Kommandozeile stehen duerfen)
    `seit_s`    : Alter des Batches in Sekunden (jetzt - Batch-Start)
    `ausgenommen`: PIDs, die NIE angefasst werden (Harness selbst + Vorfahren)
    `wurzeln_pids`: PIDs, deren Nachfahren zu diesem Lauf gehoeren (Worker + Shells)
    `bekannte_pids`: PIDs, die WAEHREND des Laufs als Nachfahren des Workers gesehen
                     wurden (`nachfahren_pids`) - auch wenn der Elternprozess inzwischen
                     tot ist (genau der B207-Fall).

    Regel: Name aus `KILL_NAMEN` UND nicht aelter als der Batch UND (Kommandozeile nennt
    die Wurzel ODER Nachfahre von `wurzeln_pids` ODER in `bekannte_pids`).
    """
    w = _normal(wurzel)
    eltern = {int(p["pid"]): int(p.get("ppid") or 0) for p in prozesse if p.get("pid")}
    verboten = {int(p) for p in ausgenommen}
    zugewiesen = {int(p) for p in wurzeln_pids}
    bekannt = {int(p) for p in bekannte_pids}

    def nachfahre(pid: int) -> bool:
        """Steht `pid` unter einem der Wurzelprozesse dieses Laufs?"""
        gesehen = 0
        while pid and gesehen < max_stufen:
            if pid in zugewiesen:
                return True
            pid = eltern.get(pid, 0)
            gesehen += 1
        return False

    treffer: list[dict] = []
    for p in prozesse:
        pid = int(p.get("pid") or 0)
        if not pid or pid in verboten:
            continue
        name = str(p.get("name") or "")
        if not KILL_NAMEN.match(name):
            continue
        cmd = str(p.get("cmd") or "")
        if any(m in cmd.lower() for m in NIE_ANFASSEN):
            continue
        try:
            alter = float(p.get("alter_s"))
        except (TypeError, ValueError):
            continue
        if alter > seit_s + ALTER_NACHSICHT_S:
            continue                                  # war schon vor dem Batch da
        in_wurzel = bool(w) and w in cmd.lower()
        if in_wurzel:
            grund = "Kommandozeile nennt die Decomp-Wurzel"
        elif pid in bekannt:
            grund = "waehrend des Laufs als Nachfahre des Workers gesehen"
        elif nachfahre(pid):
            grund = "Nachfahre des Worker-Laufs"
        else:
            continue
        treffer.append({"pid": pid, "name": name, "ppid": int(p.get("ppid") or 0),
                        "alter_s": round(alter, 1), "grund": grund, "kurz": cmd[:200]})
    return treffer


PS_LISTE = (
    "Get-CimInstance Win32_Process | ForEach-Object { "
    "[pscustomobject]@{ pid = $_.ProcessId; ppid = $_.ParentProcessId; name = $_.Name; "
    "alter_s = [int]((Get-Date) - $_.CreationDate).TotalSeconds; cmd = $_.CommandLine } } "
    "| ConvertTo-Json -Compress"
)


def prozess_liste(timeout: float = 40.0) -> list[dict]:
    """Alle Prozesse mit PID, Eltern, Name, Alter und Kommandozeile."""
    rc, out, err = run_capture(["powershell", "-NoProfile", "-NonInteractive",
                                "-Command", PS_LISTE],
                               cwd=os.getcwd(), timeout=timeout)
    if rc != 0 or not (out or "").strip():
        raise RuntimeError(f"Prozessliste nicht lesbar (rc={rc}): {str(err or out)[:200]}")
    daten = json.loads(out)
    if isinstance(daten, dict):          # bei EINEM Treffer liefert ConvertTo-Json ein Objekt
        daten = [daten]
    return daten


def vorfahren(prozesse: list[dict], pid: int, max_stufen: int = 12) -> set[int]:
    """Der eigene PID-Kreis: Prozess und alle Vorfahren (Harness + seine Fenster)."""
    eltern = {int(p["pid"]): int(p.get("ppid") or 0) for p in prozesse if p.get("pid")}
    kreis: set[int] = set()
    p = int(pid)
    while p and p not in kreis and len(kreis) < max_stufen:
        kreis.add(p)
        p = eltern.get(p, 0)
    return kreis


def nachfahren_pids(wurzel_pid: int, timeout: float = 25.0) -> list[int]:
    """Alle LEBENDEN Nachfahren eines Prozesses (BFS ueber ParentProcessId).

    Wird waehrend des Laufs immer wieder aufgerufen: was JETZT als Nachfahre des
    Workers sichtbar ist, gehoert zu diesem Lauf - auch wenn sein Elternprozess
    spaeter stirbt und der Nachweis damit nicht mehr zu fuehren waere.
    """
    if not wurzel_pid:
        return []
    prozesse = prozess_liste(timeout=timeout)
    kinder: dict[int, list[int]] = {}
    for p in prozesse:
        kinder.setdefault(int(p.get("ppid") or 0), []).append(int(p.get("pid")))
    gesehen = {int(wurzel_pid)}
    rand = [int(wurzel_pid)]
    while rand:
        neu = [k for k in kinder.get(rand.pop(), []) if k not in gesehen]
        for k in neu:
            gesehen.add(k)
            rand.append(k)
    gesehen.discard(int(wurzel_pid))
    return sorted(gesehen)


def nachsuche(wurzel, *, seit: float, wurzeln_pids=(), bekannte_pids=(), log=None,
              trocken: bool = False) -> dict:
    """Prozessreste dieses Laufs finden und beenden (gezielt, je PID).

    `seit` = `time.monotonic()`/`time.time()` vom Batch-Start; `trocken=True` beendet
    nichts (fuer Belege und Tests).
    """
    t0 = time.time()
    try:
        prozesse = prozess_liste()
    except Exception as exc:                                         # noqa: BLE001
        if log:
            log.warn("Nachsuche: Prozessliste nicht lesbar", fehler=str(exc)[:200])
        return {"ok": False, "gefunden": [], "beendet": [], "fehler": str(exc)[:200],
                "dauer_s": round(time.time() - t0, 2)}
    ausgenommen = vorfahren(prozesse, os.getpid())
    treffer = kandidaten(prozesse, wurzel=wurzel, seit_s=max(0.0, time.time() - seit),
                         ausgenommen=ausgenommen, wurzeln_pids=wurzeln_pids,
                         bekannte_pids=bekannte_pids)
    beendet: list[int] = []
    if treffer and not trocken:
        ids = ",".join(str(t["pid"]) for t in treffer)
        rc, out, err = run_capture(["powershell", "-NoProfile", "-NonInteractive",
                                    "-Command", f"Stop-Process -Id {ids} -Force"],
                                   cwd=os.getcwd(), timeout=60)
        if rc == 0:
            beendet = [t["pid"] for t in treffer]
        elif log:
            log.warn("Nachsuche: Stop-Process fehlgeschlagen", rc=rc,
                     fehler=str(err or out)[:200])
    if log and treffer:
        log.warn("Nachsuche: Prozessreste des Laufs beendet" if beendet else
                 "Nachsuche: Prozessreste gefunden (nicht beendet)", anzahl=len(treffer),
                 treffer=[f"{t['name']}:{t['pid']} ({t['grund']})" for t in treffer[:6]])
    return {"ok": True, "gefunden": treffer, "beendet": beendet, "fehler": None,
            "ausgenommen": sorted(ausgenommen), "dauer_s": round(time.time() - t0, 2)}


def zeile(auf: dict | None) -> str:
    """Eine Zeile fuer Meldung/Review."""
    if not auf:
        return "keine"
    if not auf.get("ok"):
        return f"nicht moeglich ({auf.get('fehler') or 'unbekannt'})"
    n = len(auf.get("gefunden") or [])
    if not n:
        return "keine Reste gefunden"
    return (f"{len(auf.get('beendet') or [])} von {n} Resten beendet: "
            + ", ".join(f"{t['name']}:{t['pid']}" for t in (auf.get("gefunden") or [])[:6]))
