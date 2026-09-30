"""Rechnerlast mitschreiben (R13au, Auftrag 2026-09-30, Teil C).

WARUM
=====
Der Harness läuft auf **einem** Rechner mit 4 Kernen / 8 Threads und 6 GB RAM
(`Get-CimInstance Win32_Processor`/`Win32_ComputerSystem`, gemessen
`docs/_r13au_belege.txt`); dazu kommen der Worker (Node/`claude.exe`), Ghidra (Java,
`-Xmx2g`) und die Port-Bauten. Wenn während eines Batches parallel die **volle**
Testreihe läuft, ist die Maschine überlastet — und niemand kann später sagen, ob ein
Lauf langsam war, weil er schwer war oder weil ihm die CPU weggenommen wurde.

GEMESSEN WIRD DESHALB WÄHREND DES BATCHES, jede Minute (Vorgabe `INTERVALL_S`):

* **CPU gesamt** in Prozent (Mittel über das Intervall, Spitze),
* **freier RAM** in MB (Minimum),
* **Fremdlast:** die Minuten, in denen `python`-/`java`-Prozesse liefen, die **nicht**
  zu uns gehören.

DIE DREI GRUPPEN (Definition, damit die Zahl lesbar ist)
=======================================================
* **eigene** — der Harness selbst und sein Baum (der Worker ist ein Kind des Harness,
  Fortsetzungen ebenso),
* **ghidra** — der Ghidra-Server des Projekts (`java`, erkannt an der Kommandozeile:
  `ghidra`, `GhidraMCP`, `-Dghidra.home`). Er ist **Projektlast**, keine Fremdlast,
  wird aber getrennt gezählt und in der Zeile genannt,
* **fremd** — alles andere an `python`/`java` (ein zweiter Testlauf, ein hängender
  Emulator, ein fremdes Skript). **Nur diese** Zahl erzeugt `fremdlast_minuten`.

Umsetzung: `psutil` (auf diesem Rechner vorhanden, 5.9.8). Fehlt es, wird über die
Windows-Zähler gemessen (`GetSystemTimes`/`GlobalMemoryStatusEx` über `ctypes`); die
Zahl der Prozesse lässt sich dann nur über `tasklist` nach Namen zählen, ohne
Baumzugehörigkeit — das steht als `quelle` in den Messdaten und als Hinweis in der Zeile.

Kein Fehler stört den Batch: jede Ausnahme endet in „nicht gemessen" mit Grund, nie in
einer geratenen Zahl.
"""

from __future__ import annotations

import os
import threading
import time

INTERVALL_S = 60.0          # Vorgabe aus dem Auftrag: "jede Minute"
GEDULD_S = 5.0              # so lange darf eine Aufnahme höchstens rechnen/ausfallen
PROZESSNAMEN = ("python", "pythonw", "java", "javaw")
# Kommandozeilen-Merkmale des Ghidra-Servers dieses Projekts.
GHIDRA_MERKMALE = ("ghidra", "ghidra.home", "ghidramcp")


def _psutil():
    """`psutil` oder None (Rueckfall: Windows-Zaehler)."""
    try:
        import psutil                                                  # noqa: PLC0415
        return psutil
    except Exception:                                                  # noqa: BLE001
        return None


# --------------------------------------------------------------- Windows-Zaehler
class _WindowsZaehler:
    """CPU-Auslastung und freier Speicher ohne `psutil` (nur Windows)."""

    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self._ctypes = ctypes
        self._wintypes = wintypes

        class FILETIME(ctypes.Structure):
            _fields_ = [("dwLowDateTime", wintypes.DWORD),
                        ("dwHighDateTime", wintypes.DWORD)]

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", wintypes.DWORD),
                        ("dwMemoryLoad", wintypes.DWORD),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        self._filetime = FILETIME
        self._memstatus = MEMORYSTATUSEX
        self._kernel32 = ctypes.windll.kernel32
        self._vorher = self._zeiten()

    def _zeiten(self) -> tuple[float, float, float]:
        idle, kern, user = self._filetime(), self._filetime(), self._filetime()
        ok = self._kernel32.GetSystemTimes(self._ctypes.byref(idle),
                                           self._ctypes.byref(kern),
                                           self._ctypes.byref(user))
        if not ok:
            raise OSError("GetSystemTimes fehlgeschlagen")
        def als_zahl(ft) -> float:
            return (ft.dwHighDateTime << 32) | ft.dwLowDateTime
        return (als_zahl(idle), als_zahl(kern), als_zahl(user))

    def cpu_prozent(self) -> float:
        """CPU-Auslastung seit der letzten Abfrage (Prozent, 0..100)."""
        idle, kern, user = self._zeiten()
        i0, k0, u0 = self._vorher
        self._vorher = (idle, kern, user)
        gesamt = (kern - k0) + (user - u0)
        if gesamt <= 0:
            return 0.0
        return max(0.0, min(100.0, 100.0 * (gesamt - (idle - i0)) / gesamt))

    def ram_frei_mb(self) -> float:
        m = self._memstatus()
        m.dwLength = self._ctypes.sizeof(self._memstatus)
        if not self._kernel32.GlobalMemoryStatusEx(self._ctypes.byref(m)):
            raise OSError("GlobalMemoryStatusEx fehlgeschlagen")
        return float(m.ullAvailPhys) / (1024.0 * 1024.0)


# ------------------------------------------------------------------ Aufnahme
class Recorder:
    """Minutentakt der Rechnerlast. `start()`/`stop()` sind idempotent und still."""

    def __init__(self, log=None, intervall_s: float = INTERVALL_S, eigene: set[int] | None = None):
        self.log = log
        self.intervall = max(5.0, float(intervall_s or INTERVALL_S))
        self.psutil = _psutil()
        self.eigene = set(eigene or ())
        self.proben: list[dict] = []
        self.quelle = "psutil" if self.psutil is not None else "windows"
        self.fehler = ""
        self._ende = threading.Event()
        self._faden: threading.Thread | None = None
        self._win = None
        if self.psutil is None:
            try:
                self._win = _WindowsZaehler()
            except Exception as exc:                                  # noqa: BLE001
                self.fehler = f"Zaehler nicht verfuegbar: {str(exc)[:120]}"
                self.quelle = "keine"
        if self.psutil is not None:
            # Kein Vorwaermen noetig: `probe()` misst mit `interval=1.0` (siehe dort).
            pass

    # ---------------------------------------------------------------- Aufbau
    def eigene_pids(self) -> set[int]:
        """Der eigene Baum: Harness + Nachfahren (der Worker ist ein Kind des Harness)."""
        pids = set(self.eigene) | {os.getpid()}
        if self.psutil is None:
            return pids
        try:
            alle = {p.info["pid"]: p.info.get("ppid") for p in
                    self.psutil.process_iter(["pid", "ppid"])}
            wachsen = True
            while wachsen:
                wachsen = False
                for pid, ppid in alle.items():
                    if ppid in pids and pid not in pids:
                        pids.add(pid)
                        wachsen = True
        except Exception:                                              # noqa: BLE001
            pass
        return pids

    def _prozesse(self) -> tuple[int, int, list[str]]:
        """(eigene, ghidra, fremde Namen) unter den python-/java-Prozessen."""
        if self.psutil is None:
            return 0, 0, self._tasklist_fremd()
        eigene = self.eigene_pids()
        eigene_n = ghidra_n = 0
        fremde: list[str] = []
        for p in self.psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                name = str(p.info.get("name") or "").lower()
                stamm = name[:-4] if name.endswith(".exe") else name
                if stamm not in PROZESSNAMEN:
                    continue
                if p.info["pid"] in eigene:
                    eigene_n += 1
                    continue
                zeile = " ".join(p.info.get("cmdline") or []).lower()
                if stamm.startswith("java") and any(m in zeile for m in GHIDRA_MERKMALE):
                    ghidra_n += 1
                    continue
                fremde.append(name or f"pid {p.info['pid']}")
            except Exception:                                          # noqa: BLE001
                continue
        return eigene_n, ghidra_n, fremde

    def _tasklist_fremd(self) -> list[str]:
        """Rueckfall ohne psutil: nur die NAMEN der laufenden python-/java-Prozesse."""
        import subprocess
        try:
            r = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True,
                               text=True, timeout=20)
        except Exception:                                              # noqa: BLE001
            return []
        aus = []
        for z in (r.stdout or "").splitlines():
            teil = [t.strip('"') for t in z.split('","')]
            if teil and teil[0].lower() in tuple(f"{n}.exe" for n in PROZESSNAMEN):
                aus.append(teil[0].lower())
        return aus

    # ------------------------------------------------------------ Messpunkte
    def probe(self) -> dict:
        """Eine Aufnahme (CPU %, freier RAM, Prozesszahlen)."""
        eintrag = {"ts": time.time(), "cpu": None, "ram_frei_mb": None,
                   "eigene": 0, "ghidra": 0, "fremd": 0, "fremde_namen": []}
        try:
            if self.psutil is not None:
                # GEMESSEN (2026-09-30): `cpu_percent(None)` direkt nach dem Start liefert
                # `0.0 %` - das Intervall war null. Deshalb ein echtes Messfenster von
                # einer Sekunde (der Aufruf laeuft im eigenen Faden, er stoert den Batch
                # nicht) - die Zahl ist damit die Auslastung JETZT, nicht geraten.
                eintrag["cpu"] = float(self.psutil.cpu_percent(interval=1.0))
                eintrag["ram_frei_mb"] = float(self.psutil.virtual_memory().available) / \
                    (1024.0 * 1024.0)
            elif self._win is not None:
                eintrag["cpu"] = self._win.cpu_prozent()
                eintrag["ram_frei_mb"] = self._win.ram_frei_mb()
        except Exception as exc:                                       # noqa: BLE001
            self.fehler = self.fehler or f"Aufnahme fehlgeschlagen: {str(exc)[:120]}"
        try:
            eigene, ghidra, fremde = self._prozesse()
            eintrag.update({"eigene": eigene, "ghidra": ghidra,
                            "fremd": len(fremde), "fremde_namen": sorted(set(fremde))[:8]})
        except Exception as exc:                                       # noqa: BLE001
            self.fehler = self.fehler or f"Prozessliste fehlgeschlagen: {str(exc)[:120]}"
        return eintrag

    def _lauf(self) -> None:
        while not self._ende.wait(self.intervall):
            try:
                self.proben.append(self.probe())
            except Exception:                                          # noqa: BLE001
                pass

    def start(self) -> "Recorder":
        if self._faden is not None or self.quelle == "keine":
            return self
        # Erste Probe SOFORT: ein kurzer Batch (unter einer Minute) haette sonst nichts.
        try:
            self.proben.append(self.probe())
        except Exception:                                              # noqa: BLE001
            pass
        self._faden = threading.Thread(target=self._lauf, name="hx-last", daemon=True)
        self._faden.start()
        return self

    def stop(self) -> "Recorder":
        self._ende.set()
        if self._faden is not None:
            self._faden.join(timeout=GEDULD_S)
            self._faden = None
        return self

    # ------------------------------------------------------------- Auswertung
    def werte(self) -> dict:
        """Die Zahlen für `result.json` und die Review-Fakten (nie geraten)."""
        cpus = [p["cpu"] for p in self.proben if p.get("cpu") is not None]
        rams = [p["ram_frei_mb"] for p in self.proben if p.get("ram_frei_mb") is not None]
        fremd_minuten = sum(1 for p in self.proben if int(p.get("fremd") or 0) > 0)
        namen: list[str] = []
        for p in self.proben:
            for n in p.get("fremde_namen") or []:
                if n not in namen:
                    namen.append(n)
        return {
            "cpu_mittel": round(sum(cpus) / len(cpus), 1) if cpus else None,
            "cpu_max": round(max(cpus), 1) if cpus else None,
            "ram_frei_min": round(min(rams), 0) if rams else None,
            "fremdlast_minuten": fremd_minuten,
            "fremd_max": max([int(p.get("fremd") or 0) for p in self.proben] or [0]),
            "proben": len(self.proben),
            "intervall_s": self.intervall,
            "ghidra_prozesse_max": max([int(p.get("ghidra") or 0) for p in self.proben] or [0]),
            "eigene_prozesse_max": max([int(p.get("eigene") or 0) for p in self.proben] or [0]),
            "fremde_namen": namen[:8],
            "quelle": self.quelle,
            "fehler": self.fehler,
        }


def maschine() -> dict:
    """Kerne und RAM des Rechners (fuer den Bericht, ohne Zusatzpaket)."""
    aus = {"kerne": None, "threads": None, "ram_gesamt_mb": None, "cpu": "",
           "quelle": ""}
    ps = _psutil()
    if ps is not None:
        try:
            aus["kerne"] = ps.cpu_count(logical=False)
            aus["threads"] = ps.cpu_count(logical=True)
            aus["ram_gesamt_mb"] = round(ps.virtual_memory().total / (1024.0 * 1024.0))
            aus["quelle"] = "psutil"
            return aus
        except Exception:                                              # noqa: BLE001
            pass
    try:
        import subprocess
        r = subprocess.run(["wmic", "computersystem", "get",
                            "NumberOfLogicalProcessors,TotalPhysicalMemory", "/format:csv"],
                           capture_output=True, text=True, timeout=30)
        for z in (r.stdout or "").splitlines():
            teil = [t.strip() for t in z.split(",")]
            if len(teil) >= 3 and teil[-2].isdigit():
                aus["threads"] = int(teil[-2])
                aus["ram_gesamt_mb"] = round(int(teil[-1]) / (1024.0 * 1024.0))
                aus["quelle"] = "wmic"
    except Exception:                                                  # noqa: BLE001
        pass
    return aus


def fakten_zeile(res: dict | None) -> str:
    """Die Zeile fuer die Review-Fakten (`harness-facts.md`)."""
    res = res or {}
    if res.get("cpu_mittel") is None and res.get("ram_frei_min") is None:
        grund = res.get("last_fehler") or res.get("last_quelle") or "nicht gemessen"
        return f"RECHNERLAST: nicht gemessen ({grund})"
    teile = [f"CPU {res.get('cpu_mittel')} % (Spitze {res.get('cpu_max')} %)",
             f"RAM frei min {int(res.get('ram_frei_min') or 0)} MB"]
    n = int(res.get("fremdlast_minuten") or 0)
    von = int(res.get("last_proben") or 0)
    text = f"{n} von {von} Minuten" if von else f"{n} Minuten"
    spitze = int(res.get("last_fremd_max") or 0)
    namen = ", ".join(res.get("last_fremde_namen") or []) or "Namen nicht erfasst"
    if n:
        # Die Spitze steht dabei, weil ein Teil der Prozesse (watch, Bridge, VS Code)
        # DAUERHAFT mitlaeuft: die Zahl ist ein Grundrauschen, keine Warnung.
        teile.append(f"FREMDLAST in {text} (bis {spitze} Prozesse: {namen})")
    else:
        teile.append(f"keine Fremdlast in {text}")
    if int(res.get("last_ghidra_max") or 0) > 0:
        teile.append(f"Ghidra lief mit ({int(res['last_ghidra_max'])} Java-Prozess)")
    if res.get("last_quelle") and res["last_quelle"] != "psutil":
        teile.append(f"Quelle {res['last_quelle']}")
    return "RECHNERLAST: " + ", ".join(teile)


def in_result(werte: dict | None) -> dict:
    """Die Feldnamen, wie sie in `runs/b<N>/result.json` stehen (Auftragsnamen)."""
    w = werte or {}
    return {
        "cpu_mittel": w.get("cpu_mittel"),
        "cpu_max": w.get("cpu_max"),
        "ram_frei_min": w.get("ram_frei_min"),
        "fremdlast_minuten": w.get("fremdlast_minuten"),
        "last_fremd_max": w.get("fremd_max"),
        "last_proben": w.get("proben"),
        "last_intervall_s": w.get("intervall_s"),
        "last_ghidra_max": w.get("ghidra_prozesse_max"),
        "last_eigene_max": w.get("eigene_prozesse_max"),
        "last_fremde_namen": w.get("fremde_namen") or [],
        "last_quelle": w.get("quelle") or "",
        "last_fehler": w.get("fehler") or "",
    }
