"""Kleinere Helfer: Pfade, atomares Schreiben, JSONL, Logging (UTF-8)."""

from __future__ import annotations

import codecs
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------- Zeit / IDs

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().isoformat(timespec="seconds")


def stamp(compact: bool = False) -> str:
    fmt = "%Y%m%d-%H%M%S" if compact else "%Y-%m-%d %H:%M:%S"
    return datetime.now().strftime(fmt)


def new_id() -> str:
    return uuid.uuid4().hex[:12].upper()


# ------------------------------------------------------------- Dateisystem

def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def batch_ordner(runs: str | Path) -> list[tuple[int, Path]]:
    """Alle `runs/b<N>`-Ordner als `[(N, Pfad)]`, nach Nummer aufsteigend (R13bj).

    `runs/` enthaelt auch Ordner, die NICHT `b<Zahl>` heissen: Sicherungen wie
    `b235_lauf1_sicherung`, dazu `env-proof`, `ghidra-smoke`, `reviewer-proof`,
    `_verworfen_b000`. Wer `glob("b*")` ohne Ziffernpruefung liest, zaehlt sie mit
    oder stuerzt (`int(name[1:])` -> ValueError). EINE Stelle, die das richtig macht.
    """
    out: list[tuple[int, Path]] = []
    try:
        for p in Path(runs).iterdir():
            if p.is_dir() and p.name.startswith("b") and p.name[1:].isdigit():
                out.append((int(p.name[1:]), p))
    except OSError:
        return []
    return sorted(out)


# ------------------------------------------------- Teilungsfehler (D/R13d)
#
# Am 2026-09-26 starb der Harness ZWEIMAL an derselben Zeile:
#   PermissionError: [WinError 5] Zugriff verweigert: '...run.json.tmp' -> '...run.json'
# Ursache war kein Fehler im Zustand, sondern ein LESER: `hx.cli watch` liest
# `run.json` alle 1,5 s. Solange diese Datei offen ist, verweigert Windows das
# Ersetzen - der ganze Prozess stirbt. Der belastbare Teil der Abhilfe ist die
# Nachsicht beim Schreiben (`replace_with_retry`); zusaetzlich oeffnen unsere
# eigenen Leser die Datei so, dass spaetere Loeschungen nicht blockiert werden
# (`open_shared_read`).

# Win32: FILE_SHARE_READ / _WRITE / _DELETE (winnt.h); `_winapi` stellt sie nicht bereit.
_FILE_SHARE_READ = 0x00000001
_FILE_SHARE_WRITE = 0x00000002
_FILE_SHARE_DELETE = 0x00000004

# Win32-Fehler, die "ein anderer Prozess haelt die Datei offen" bedeuten:
# ERROR_ACCESS_DENIED (5) und ERROR_SHARING_VIOLATION (32).
_SHARING_WINERRORS = (5, 32)

_REPLACE_TRIES = 40
_REPLACE_PAUSE_S = 0.005     # erste Wartezeit
_REPLACE_PAUSE_MAX_S = 0.05  # Deckel -> insgesamt rund 1,8 s Nachsicht


def _ist_teilungsfehler(exc: OSError) -> bool:
    """Nur unter Windows: Zugriff verweigert bzw. Teilungsverletzung."""
    if os.name != "nt":
        return False
    return int(getattr(exc, "winerror", 0) or 0) in _SHARING_WINERRORS


def replace_with_retry(tmp: str | Path, ziel: str | Path,
                       versuche: int = _REPLACE_TRIES,
                       pause_s: float = _REPLACE_PAUSE_S) -> None:
    """`os.replace` mit wachsender Nachsicht bei Windows-Teilungsfehlern.

    GEMESSEN (2026-09-26, C: und G:, siehe tests/test_r13d_fixes.py):
    solange ein anderer Prozess die Zieldatei offen haelt, scheitert das
    Ersetzen mit WinError 5 - auch dann, wenn dieser Leser FILE_SHARE_DELETE
    vergibt (dann geht `DeleteFile`, aber kein Rename-Ersetzen). Der einzige
    verlaesslicher Ausweg ist also: warten, bis der Leser fertig ist. Genau der
    Fall aus dem Absturzbericht - `hx.cli watch` liest `run.json` alle 1,5 s und
    haelt sie nur Millisekunden - ist damit erledigt; die Wartezeit waechst
    (5 ms, 8 ms, 13 ms, ... gedeckelt bei 50 ms), damit der Normalfall billig
    bleibt. Fehler, die KEIN Teilungsproblem sind (fehlender Pfad,
    schreibgeschuetzt), werden sofort weitergegeben; die Atomaritaet ("nie halbe
    Zustandsdateien") bleibt erhalten - statt still in die Zieldatei zu schreiben
    wird nach erschoepfter Nachsicht weiterhin ein Fehler gemeldet.
    """
    versuche = max(1, int(versuche))
    pause = max(0.0, float(pause_s))
    letzter: OSError | None = None
    for versuch in range(versuche):
        try:
            os.replace(tmp, ziel)
            return
        except OSError as exc:
            if not _ist_teilungsfehler(exc):
                raise
            letzter = exc
            if versuch < versuche - 1:
                time.sleep(pause)
                pause = min(pause * 1.6, _REPLACE_PAUSE_MAX_S)
    raise letzter if letzter is not None else OSError("os.replace fehlgeschlagen")


def open_shared_read(path: str | Path):
    """Datei zum Lesen oeffnen, ohne spaetere Loeschungen zu blockieren (R13d).

    Auf Windows vergibt `open()` (CRT) nur FILE_SHARE_READ|WRITE. Ein Leser
    blockiert damit jedes `unlink()` auf dieselbe Datei (WinError 32/5) -
    betroffen sind `control.take()` (.ctl), Log-Rotation und Git-Laeufe, die
    waehrend `watch` mitliest. Hier wird deshalb mit
    FILE_SHARE_READ|WRITE|DELETE geoeffnet; alle anderen Systeme bleiben beim
    normalen `open()`.

    GEMESSEN (2026-09-26): das Loeschen geht damit durch, das *Rename-Ersetzen*
    einer offenen Datei aber nicht (siehe `replace_with_retry`) - diese Funktion
    ersetzt also nicht die Nachsicht beim Schreiben.
    """
    return _oeffne_shared(path, binaer=False)


def _oeffne_shared(path: str | Path, binaer: bool):
    """Gemeinsamer Teil von `open_shared_read` und `open_shared_read_bytes`."""
    p = str(path)
    if os.name != "nt" or not p.isascii():
        # GEMESSEN (R13bt-3, 2026-10-04): `_winapi.CreateFile` scheitert an JEDEM
        # Nicht-ASCII-Zeichen im Pfad - bei einem Umlaut im Dateinamen mit
        # FileNotFoundError/WinError 2, bei einem Umlaut im Elternordner mit
        # WinError 3 - obwohl `Path.is_file()` True sagt und `open()` dieselbe
        # Datei problemlos liest (Vier-Faelle-Probe:
        # docs/_r13bt3_pfade.py). Ein Lauf-Ordner oder ein Clone unter einem
        # Benutzernamen mit Umlaut haette damit JEDE geteilte Lesung (Review,
        # Zustand, Log) als fehlende Datei oder als Absturz erscheinen lassen.
        # Die Freigabe zum Loeschen brauchen wir fuer unsere eigenen Dateien
        # (Zeilenenden-tolerant, immer ASCII) - fuer alles andere ist Lesen
        # ohne diese Freigabe besser als ein Fehler.
        if binaer:
            return open(p, "rb")
        return open(p, "r", encoding="utf-8", errors="replace")
    import _winapi
    import msvcrt
    share = _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE
    # 0 = NULL fuer SECURITY_ATTRIBUTES und Vorlage-Handle (keine Angabe).
    handle = _winapi.CreateFile(p, _winapi.GENERIC_READ, share, 0,
                                _winapi.OPEN_EXISTING, 0, 0)
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except OSError:
        _winapi.CloseHandle(handle)
        raise
    if binaer:
        return open(fd, "rb")
    # `os.O_BINARY` steht auch hier: die Dekodierung macht der Text-Wrapper, und ohne
    # das Flag wuerde Windows \r\n vorher in \n verwandeln (Zeilenenden unveraendert
    # durchreichen ist die Regel).
    return open(fd, "r", encoding="utf-8", errors="replace")


def read_bytes_shared(path: str | Path) -> bytes:
    """Eine Datei binaer lesen, ohne spaetere Loeschungen zu blockieren (R13ap)."""
    with _oeffne_shared(path, binaer=True) as fh:
        return fh.read()


# ------------------------------------------------- Kodierung erkennen (R13ap)
# Anlass (gemessen 2026-09-30): `analysis/_preflight_216.txt` wurde als **UTF-16 LE mit
# BOM** geschrieben (FF FE), B211-B215 dagegen als UTF-8-BOM. `read_text` liest UTF-8 -
# jede Zeile kam mit NUL-Bytes an, der Parser fand keine Pflichtzeile, und der Review von
# B216 trug drei "PARSER: Zeile ... nicht erkannt" (R13ae-Warnung, s.
# `docs/_r13ap_belege.md`). Aeltere Faelle derselben Art: B155-B158.
KODIERUNGEN = ("utf-8", "utf-8-bom", "utf-16-le", "utf-16-be", "utf-16-le-ohne-bom")
_BOM_UTF8 = codecs.BOM_UTF8                    # EF BB BF
_BOM_UTF16_LE = codecs.BOM_UTF16_LE            # FF FE
_BOM_UTF16_BE = codecs.BOM_UTF16_BE            # FE FF
NUL_KOPF_BYTES = 4096


def erkenne_kodierung(b: bytes) -> str:
    """Die Kodierung aus den Bytes ableiten (R13ap) - Name aus `KODIERUNGEN`.

    Reihenfolge: BOM (UTF-8/UTF-16 LE/BE) schlaegt alles; ohne BOM gilt UTF-8, es sei
    denn, in den ersten `NUL_KOPF_BYTES` steht ein NUL-Byte - dann wird UTF-16 LE
    versucht (das ist die Form, die PowerShell ohne BOM schreibt).
    """
    if b.startswith(_BOM_UTF8):
        return "utf-8-bom"
    if b.startswith(_BOM_UTF16_LE):
        return "utf-16-le"
    if b.startswith(_BOM_UTF16_BE):
        return "utf-16-be"
    if b"\x00" in b[:NUL_KOPF_BYTES]:
        return "utf-16-le-ohne-bom"
    return "utf-8"


def dekodiere(b: bytes, kodierung: str) -> str:
    """Bytes mit der erkannten Kodierung in Text wandeln; BOM wird entfernt (R13ap).

    `errors="replace"` ist Absicht: eine defekte Stelle soll den Harness nicht anhalten.
    """
    if kodierung == "utf-8-bom":
        return b.decode("utf-8-sig", errors="replace")
    if kodierung == "utf-16-le":
        return b.decode("utf-16-le", errors="replace").lstrip("\ufeff")
    if kodierung == "utf-16-be":
        return b.decode("utf-16-be", errors="replace").lstrip("\ufeff")
    if kodierung == "utf-16-le-ohne-bom":
        return b.decode("utf-16-le", errors="replace")
    return b.decode("utf-8", errors="replace")


def ist_utf16(kodierung) -> bool:
    """Wurde als UTF-16 gelesen? (R13ap) - fuer den Hinweis in den Review-Fakten."""
    return str(kodierung or "").startswith("utf-16")


def read_text_erkannt(path: str | Path, default: str = "") -> tuple[str, str]:
    """Text mit **erkannter** Kodierung lesen -> `(text, kodierung)` (R13ap).

    Fehlt die Datei, kommt `(default, "")`. Fuer Dateien, die nicht ASCII/UTF-8 sind -
    `read_text` bleibt fuer alles andere die richtige Wahl, es liest weiter UTF-8.
    """
    p = Path(path)
    if not p.is_file():
        return default, ""
    b = read_bytes_shared(p)
    kodierung = erkenne_kodierung(b)
    return dekodiere(b, kodierung), kodierung


def write_text_atomic(path: str | Path, text: str) -> Path:
    """Schreibt ueber eine .tmp-Datei und os.replace -> nie halbe Zustandsdateien."""
    p = Path(path)
    ensure_dir(p.parent)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    replace_with_retry(tmp, p)
    return p


def write_json_atomic(path: str | Path, obj) -> Path:
    return write_text_atomic(path, json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def read_json(path: str | Path, default=None):
    p = Path(path)
    if not p.is_file():
        return default
    try:
        with open_shared_read(p) as fh:
            return json.loads(fh.read())
    except (json.JSONDecodeError, OSError):
        return default


def read_text(path: str | Path, default: str = "") -> str:
    p = Path(path)
    if not p.is_file():
        return default
    with open_shared_read(p) as fh:
        return fh.read()


def append_text(path: str | Path, text: str) -> Path:
    p = Path(path)
    ensure_dir(p.parent)
    with open(p, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return p


def append_jsonl(path: str | Path, obj) -> Path:
    # R13e: `default=str` - ein Logwert, der sich nicht serialisieren laesst (z. B.
    # ein Objekt aus einem Test oder ein Mock), darf den Harness nicht umbringen.
    # GEMESSEN: ein solcher Wert liess json.dumps mit TypeError abbrechen und riss
    # den ganzen Prozess mit.
    return append_text(path, json.dumps(obj, ensure_ascii=False, default=str) + "\n")


def read_jsonl_tolerant(path: str | Path) -> list:
    """Liest JSONL; eine halb geschriebene letzte Zeile wird verworfen."""
    p = Path(path)
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def tail_lines(path: str | Path, n: int) -> list:
    p = Path(path)
    if not p.is_file():
        return []
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-n:]


# ------------------------------------------------------------------ Konsole (R13bq)
# Der Harness schreibt JEDE Log-Zeile mit `print(..., flush=True)` (`Log._emit` oben).
# Steht das Konsolenfenster im Markiermodus (QuickEdit, Windows-Standard), BLOCKIERT
# dieser Schreibvorgang, bis die Auswahl aufgehoben wird - der druckende Thread steht.
# Waehrend eines Batches drucken der Takt-Thread (Telegram-/Limit-Warnungen) und der
# Haupt-Thread; ein stehender Takt-Thread sieht dann auch /stop und /pause nicht mehr,
# denn der STOP-Marker wird in `orchestrator.poll()` (Takt-Thread) gelesen. Der WORKER
# ist nicht betroffen: seine Ausgabe geht in `runs/b<N>/stream*.jsonl` (Datei, kein
# Konsolenhandle) - das Fenster steht, der Batch laeuft weiter. Gemeldet 2026-10-03
# (B257: Fenster zeigte nichts mehr, der Mitschnitt wuchs weiter).
STD_INPUT_HANDLE = -10
ENABLE_QUICK_EDIT = 0x0040
ENABLE_EXTENDED_FLAGS = 0x0080


def ohne_quickedit_modus(mode: int) -> int:
    """Konsolen-EINGABEmodus ohne QuickEdit (reine Rechnung, damit pruefbar)."""
    return (int(mode) & ~ENABLE_QUICK_EDIT) | ENABLE_EXTENDED_FLAGS


def konsole_quickedit_aus(log=None) -> bool:
    """QuickEdit im EIGENEN Konsolenfenster abschalten; `True` = steht jetzt aus.

    Ohne Konsolenhandle (umgeleitete Ausgabe, Testlauf, Dienst) gibt es nichts zu
    schalten - dann `False`. Fehler werden geschluckt und geloggt: die Abschaltung ist
    eine Bequemlichkeit, kein Betriebsmittel. Rueckgabe `True` heisst auch "war schon
    aus" - der Aufrufer soll nicht zwischen beiden Faellen unterscheiden muessen.
    """
    if os.name != "nt":
        return False
    try:
        import ctypes
        k = ctypes.windll.kernel32
        handle = k.GetStdHandle(STD_INPUT_HANDLE)
        mode = ctypes.c_uint32()
        if not k.GetConsoleMode(handle, ctypes.byref(mode)):
            if log:
                log.info("Konsole: kein Konsolenhandle - QuickEdit bleibt, wie es ist")
            return False
        neu = ohne_quickedit_modus(mode.value)
        if neu == mode.value:
            return True                      # war schon aus
        if not k.SetConsoleMode(handle, neu):
            if log:
                log.warn("Konsole: SetConsoleMode fehlgeschlagen")
            return False
        return True
    except Exception as exc:                 # noqa: BLE001 - nie toedlich
        if log:
            log.warn("Konsole: QuickEdit nicht abgeschaltet", fehler=str(exc)[:120])
        return False


def stille_warnung(dauer_s: float, schwelle_s: float, letzte_stufe: int) -> tuple[int, str]:
    """(neue Stufe, Text) fuer die Stillstands-Warnung des Mitschnitts (R13bq).

    Anlass (gemessen 2026-10-03, B257): zwischen dem Start der Fortsetzung (20:21) und
    dem ersten sichtbaren Inhalt schien der Mitschnitt 45 min leer - das Harness-Fenster
    sagte dazu nichts. Die Zeit steckte in blockierenden Werkzeugaufrufen (93,7 % der
    Batch-Zeit, Einzelaufrufe bis 1323 s) und in der Pufferung der claude-CLI.

    Gemeldet wird bei jeder VOLLEN Schwelle (1x, 2x, 3x …): eine lange Stille soll
    sichtbar bleiben, ohne das Protokoll zuzumuellen. `Text == ""` heisst: jetzt nicht
    melden. Reine Rechnung - der Aufrufer (proc.run_stream) entscheidet ueber Log/Text.
    """
    if schwelle_s is None or float(schwelle_s) <= 0:
        return 0, ""
    dauer = max(0.0, float(dauer_s))
    stufe = int(dauer // float(schwelle_s))
    if stufe <= int(letzte_stufe):
        return int(letzte_stufe), ""
    return stufe, (f"kein Mitschnitt-Zeichen seit {dauer / 60.0:.0f} min "
                   f"(Schwelle {float(schwelle_s) / 60.0:.0f} min, {stufe}. Meldung)")


# ------------------------------------------------------------------- Logging

class Log:
    """JSONL-Logdatei + knappe Konsolenausgabe (UTF-8-tolerant)."""

    def __init__(self, path: str | Path, echo: bool = True, tag: str = "harness"):
        self.path = Path(path)
        self.echo = echo
        self.tag = tag
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    def _emit(self, level: str, msg: str, **extra):
        rec = {"ts": now_iso(), "level": level, "msg": msg}
        if extra:
            rec.update(extra)
        try:
            append_jsonl(self.path, rec)
        except OSError:
            pass
        if self.echo:
            line = f"[{datetime.now().strftime('%H:%M:%S')}] {level:<5} {msg}"
            if extra:
                line += "  " + " ".join(f"{k}={v}" for k, v in extra.items())
            print(line, flush=True)

    def info(self, msg: str, **extra):
        self._emit("INFO", msg, **extra)

    def warn(self, msg: str, **extra):
        self._emit("WARN", msg, **extra)

    def error(self, msg: str, **extra):
        self._emit("ERROR", msg, **extra)

    def event(self, name: str, **extra):
        self._emit("EVENT", name, **extra)


def secs_human(seconds: float) -> str:
    seconds = int(max(0, seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def sleep_until(ts: float, max_chunk: float = 30.0, interrupt=None) -> None:
    """Schlaeft bis Zeitstempel, in Stuecken; interrupt() darf frueher abbrechen."""
    while True:
        left = ts - time.time()
        if left <= 0:
            return
        if interrupt is not None and interrupt():
            return
        time.sleep(min(max_chunk, left))
