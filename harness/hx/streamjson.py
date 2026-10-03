"""stream-json auswerten: deduplizieren, Tokens zaehlen, Kosten rechnen.

Befund aus dem Sandkasten (results-probe.md 2.7): eine API-Antwort erzeugt
MEHRERE assistant-Ereignisse (eines je Inhaltsblock). Ungefiltert summieren sich
die Token dadurch ~2,9-fach. Deshalb: Anfragen werden nach message.id
dedupliziert, Werkzeugaufrufe nach tool_use.id.
"""

from __future__ import annotations

import json
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import pricing, secrets
from .util import append_jsonl, ensure_dir, now_iso, read_text, write_text_atomic

# Punkt 2c (R13e): Der HTTP-Weg auf 127.0.0.1:8089 ist ausdruecklich erlaubt. Er
# kann aber den GEMEINSAMEN Ghidra-Zustand beruehren (Programm wechseln/oeffnen/
# schliessen, Projekt zuruecksetzen, Skript ausfuehren). Das wird nur VERMERKT -
# kein Alarm, keine Sperre.
HTTP_RE = re.compile(r"(?:127\.0\.0\.1|localhost):8089")
HTTP_STATE_ENDPOINTS = (
    "/load_program_from_project", "/load_program", "/switch_program", "/open_program",
    "/close_program", "/open_project", "/close_project", "/create_project",
    "/restore_project", "/archive_project", "/checkin_program",
    "/save_all_programs", "/save_program", "/create_program",
    "/run_script", "/run_ghidra_script", "/script",
    "/import_program", "/import_file", "/export_program",
)
# Nur diese Werkzeuge KOENNEN einen HTTP-Aufruf ausloesen. Ein Read-Ergebnis mit
# einem Dokument, das die Endpunkte zitiert, ist kein Aufruf (gleiche Falle wie
# bei den Ablehnungen - B172/B173).
HTTP_TOOLS = {"PowerShell", "Bash", "Shell", "Write", "Edit", "MultiEdit",
              "NotebookEdit", "Terminal"}

# R13aj (2026-09-29, gemessen an B212-B214): Ein `tool_use` steht immer allein in
# seiner Assistant-Nachricht - aber zwei Aufrufe koennen sich trotzdem UEBERLAPPEN,
# wenn das Ergebnis des ersten erst nach dem Start des zweiten im Mitschnitt steht
# (in B212 `stream.jsonl:14789/14790` und `:37986/37987`: der gekappte
# PowerShell-Aufruf lief im Hintergrund weiter, daneben lief ein Grep). Dann misst
# die Ereignisdistanz nicht die Arbeit des Aufrufs, sondern das Warten mit
# (B212: Grep 602,3 s und 511,0 s, obwohl er normale Treffer lieferte). `parallel`
# ist deshalb 1 + die Zahl der Aufrufe, mit denen sich dieser Aufruf ueberlappt:
# 1 = allein gemessen. Eine Ueberlappung unter dieser Schwelle ist Rundung der
# Zeitstempel, kein Nebenlauf (B212-B214: 14/8/27 echte gegen 16/2/18 winzige).
PARALLEL_TOLERANZ_S = 1.0


def _zeit(wert) -> float | None:
    """ISO-Zeitstempel eines Ereignisses in Sekunden (None, wenn unbrauchbar)."""
    if not wert:
        return None
    try:
        return datetime.fromisoformat(str(wert).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def kurz_input(eingabe, grenze: int = 90) -> str:
    """Kurzbeschreibung eines Werkzeugaufrufs fuer die Messdaten (ohne Werte)."""
    if isinstance(eingabe, str):
        text = eingabe
    elif isinstance(eingabe, dict):
        for feld in ("command", "file_path", "path", "pattern", "query", "prompt"):
            if eingabe.get(feld):
                text = str(eingabe[feld])
                break
        else:
            text = json.dumps(eingabe, ensure_ascii=False)
    else:
        text = str(eingabe)
    return " ".join(text.split())[:grenze]


def _norm(text: str) -> str:
    """Vergleichsform fuer Pfade: klein, nur `/`, keine Doppel-Schraegstriche."""
    return re.sub(r"/+", "/", str(text).lower().replace("\\", "/"))


def runden_aus_zeilen(zeilen) -> int:
    """Werkzeugrunden aus beliebigen stream-json-Zeilen (R13ar).

    Gelesen wird damit das **Transcript** einer Sitzung (Feld `transcript_path` der
    Hook-Eingabe, gemessen in `docs/_r13ar_hook_eingabe.txt`) - dieselbe Zaehlweise wie
    `StreamStats.runden()`, damit Hook und Bericht dieselbe Zahl nennen. Unbekannte
    Zeilentypen (das Transcript traegt auch `queue-operation`, `attachment`, …) werden
    von `StreamStats.feed` ignoriert. Kaputte Zeilen zaehlen nicht.
    """
    st = StreamStats()
    for z in zeilen:
        if not str(z).strip():
            continue
        try:
            st.feed(z)
        except Exception:                                            # noqa: BLE001
            continue
    return st.runden()


class TaktThread:
    """Ruft `takt()` auch dann weiter, wenn KEINE Zeile im Mitschnitt ankommt (R13h).

    Befund 2026-09-26: ein Werkzeugaufruf kann 600 s dauern (68K-Emulation, Port-Bau).
    In dieser Zeit schreibt der Kindprozess nichts, `on_event` wird nicht gerufen - und
    damit auch kein `poll()`. Folge: `/stop`, `/pause` oder eine Nachricht des Nutzers
    wirken bis zu 10 Minuten nicht. Der Takt-Thread schliesst genau diese Luecke.
    Er ist ein Daemon und wird nach dem Lauf sauber beendet.
    """

    def __init__(self, takt, intervall_s: float = 2.0, log=None):
        self.takt = takt
        self.intervall = max(0.2, float(intervall_s or 2.0))
        self.log = log
        self.aufrufe = 0
        self._ende = threading.Event()
        self._faden = threading.Thread(target=self._lauf, name="hx-takt", daemon=True)

    def _lauf(self) -> None:
        while not self._ende.wait(self.intervall):
            try:
                self.takt()
                self.aufrufe += 1
            except Exception as exc:                             # noqa: BLE001
                if self.log:
                    self.log.warn("Takt-Thread fehlgeschlagen", fehler=str(exc)[:120])

    def start(self) -> "TaktThread":
        self._faden.start()
        return self

    def stop(self, timeout: float = 5.0) -> None:
        self._ende.set()
        if self._faden.is_alive():
            self._faden.join(timeout=timeout)


class TaktGeber:
    """Darf jetzt gerechnet werden? (R13h)

    Der Mitschnitt wird ZEILENWEISE verarbeitet. Summen und Kosten duerfen dabei
    nicht je Zeile neu gerechnet werden: `cost_usd()` kostet ~1 ms (gemessen
    2026-09-26, 272 Anfragen) - bei 156.493 Zeilen sind das ~179 s Rechenzeit im
    Leser-Thread, der eigentlich nur die Ausgabe des Kindprozesses abnehmen soll.
    """

    def __init__(self, intervall_s: float):
        self.intervall = float(intervall_s or 0)
        self.letzter = 0.0

    def faellig(self, jetzt: float | None = None) -> bool:
        jetzt = time.monotonic() if jetzt is None else jetzt
        if jetzt - self.letzter >= self.intervall:
            self.letzter = jetzt
            return True
        return False


_ABBau = re.compile(r"stop-process|taskkill", re.IGNORECASE)
_ABBau_CPU = re.compile(r"\$_\.\s*cpu", re.IGNORECASE)
_ABBau_NAME = re.compile(r"stop-process[^;|]*-name\b|taskkill\s+/im", re.IGNORECASE)
_ABBau_LISTE = re.compile(r"get-process\s+\w|get-ciminstance", re.IGNORECASE)
_ABBau_ID = re.compile(r"stop-process\s+-id\s+(?:@\()?\d|\$_\.id\s+-eq\s*\d",
                       re.IGNORECASE)
_ABBau_FILTER = re.compile(r"commandline\s+-like", re.IGNORECASE)
# R13bf (Aussensicht B234, Befund M234-2): eine WOERTLICHE Liste fester Nummern ist ein
# gezielter Abbau - auch wenn die Nummer ueber eine Schleifenvariable in `Stop-Process`
# geht. Anlass: `foreach ($id in @(704,13960,18296)) { Stop-Process -Id $id }` brach B234
# ab (Fehlalarm), obwohl drei feste, eigene `hybrid_lauf.exe`-Prozesse gemeint waren.
_ABBau_SCHLEIFE = re.compile(
    r"(?:foreach|for)\s*\(\s*\$(\w+)\s+in\s+(.{0,120}?)\)\s*[;{]",
    re.IGNORECASE | re.DOTALL)
# Und die Gegenprobe: eine Schleife ueber eine QUELLE OHNE woertliche Nummern bleibt
# verdaechtig (Variable, `Get-Process`/`Get-CimInstance`-Auswahl) - die Nummer weiss hier
# niemand, also kann sie auch den Harness treffen. Genau dafuer wird die Quellspalte
# getrennt geprueft statt geraten. Die schliessende Klammer der Liste ist optional, weil
# der Schleifenkopf sie in `group(2)` mitnehmen kann (`@(704,…)` bzw. `@(704,…`).
_ABBau_LISTE_WORT = re.compile(r"@\(\s*\d+(?:\s*,\s*\d+)*\s*\)?$", re.IGNORECASE)


def _abbau_stelle(text: str, var: str) -> bool:
    """Wird `$<var>` (oder `$_`) als `-Id` eines `Stop-Process` benutzt?"""
    v = re.escape(var)
    muster = [rf"stop-process\b[^;|]*-id\s+\${v}\b"]
    if var == "_":
        muster = [r"stop-process\b[^;|]*-id\s+\$_\.\w+"]
    for m in muster:
        if re.search(m, text, re.IGNORECASE):
            return True
    return False


def _abbau_feste_liste(text: str) -> bool:
    """Geht der Abbau auf eine WOERTLICHE Liste fester Nummern zurueck? (R13bf)

    Verlangt werden **beide** Haelften: eine rein numerische Liste in der
    Schleifenkopfzeile (`foreach ($id in @(704,13960,18296))`) UND dieselbe Variable als
    `-Id` eines `Stop-Process`. Eine Zuweisung an eine Variable VOR der Schleife
    (`$ids = 704,13960,18296; foreach ($id in $ids) …`) erkennt diese Regel bewusst
    NICHT - sie raet nicht, und der Fehlalarm war die teurere Richtung (B234 verloren).
    """
    for m in _ABBau_SCHLEIFE.finditer(text):
        if not _ABBau_LISTE_WORT.search(m.group(2).strip()):
            continue
        if _abbau_stelle(text, m.group(1)):
            return True
    return False


def _abbau_schleife_variable(text: str) -> bool:
    """Laeuft der Abbau ueber eine Schleife OHNE woertliche Nummern? (R13bf)"""
    for m in _ABBau_SCHLEIFE.finditer(text):
        if _ABBau_LISTE_WORT.search(m.group(2).strip()):
            continue                    # woertliche Liste = gezielt (s. o.)
        if _abbau_stelle(text, m.group(1)):
            return True
    return False


def abbau_gefahr(befehl) -> str | None:
    """Erkennt Prozessabbau, der den HARNESS SELBST treffen kann (R13i, 2026-09-26).

    Anlass: der Worker raeumte in Batch 178 mit
    `Get-Process python | Where-Object { $_.CPU -gt 50 } | Stop-Process`
    **jeden** Python-Prozess mit ueber 50 s CPU-Zeit ab - darunter den Harness
    (`python.exe -m hx.cli run`, ~370 s CPU). Der Harness starb ohne Crash-Bericht,
    ohne stderr und ohne Ereigniseintrag: ein hartes `TerminateProcess`.

    Erlaubt und NICHT gemeldet: ein gezielter Abbau mit festen Nummern - direkt
    (`Stop-Process -Id 1234`) oder als **woertliche Liste** in einer Schleife
    (`foreach ($id in @(704,13960,18296)) { Stop-Process -Id $id }`, R13bf nach dem
    Fehlalarm in B234) - sowie die Auswahl ueber die Kommandozeile
    (`Where-Object { $_.CommandLine -like "*port4c2*" }`).

    Gemeldet wird dagegen weiter alles, was den Harness treffen KANN: CPU-/Namensmuster,
    eine pauschale Prozessliste - und seit R13bf auch eine Schleife, deren Nummernquelle
    keine woertlichen Zahlen sind (Variable oder `Get-Process`/`Get-CimInstance`-Auswahl).
    Belege: `docs/_r13i_belege.md`, `docs/_r13bf_belege.md` (Gegenprobe ueber ALLE
    Mitschnitte: 26 Abbau-Befehle, vorher 1 Fehlalarm, nachher 0).
    """
    t = " ".join(str(befehl or "").split())
    if not t or not _ABBau.search(t):
        return None
    if _ABBau_CPU.search(t):
        return ("Prozesse nach CPU-Zeit abgeraeumt - das trifft den Harness "
                "(python.exe mit viel CPU-Zeit)")
    if _ABBau_NAME.search(t):
        return "Prozesse nach NAME abgeraeumt - das trifft jeden python.exe"
    if _ABBau_FILTER.search(t):
        return None                     # CommandLine-Filter: gezielte Auswahl (R13i)
    if _ABBau_ID.search(t) or _abbau_feste_liste(t):
        return None                     # feste Nummer(n) - gezielt
    if _abbau_schleife_variable(t):
        return ("Prozesse in einer Schleife abgeraeumt, deren Nummernquelle keine "
                "woertlichen Zahlen sind (Variable oder Get-Process/Get-CimInstance) "
                "- kann den Harness treffen")
    if _ABBau_LISTE.search(t):
        return ("Prozessliste pauschal abgeraeumt (ohne feste Nummer und ohne "
                "CommandLine-Filter) - kann den Harness treffen")
    return None


_SLEEP_RE = re.compile(r"start-sleep\s+(?:-seconds\s+)?(\d+(?:\.\d+)?)"
                       r"|start-sleep\s+-milliseconds\s+(\d+)"
                       r"|\bsleep\s+(\d+)\b", re.IGNORECASE)
_SCHLEIFE_RE = re.compile(r"for\s*\(\s*\$[a-z]+\s*=\s*0;", re.IGNORECASE)

# ---------------------------------------------------------------------------
# R13v (2026-09-28): WARTESCHLEIFEN.
# Gemessen in B207 (`runs/b207/stream.jsonl`): das Werkzeug kappte einen Lauf bei
# 600 s und schob ihn in den HINTERGRUND (Zeile 76897: "Command did not complete
# within its 600s timeout and was moved to the background"). Der Worker wartete
# danach in ZWEI Abfrageschleifen auf PID 4996 - 601,9 s (Zeile 76873) und 481,8 s
# (Zeile 77152), zusammen 1083,7 s von 2846 s Laufzeit. In B174 waren es 1993 s.
# Der Vorspann verbot das nur in Prosa und empfahl sogar "kurze Schritte (10-20 s)" -
# das ist genau das Muster. Hier wird es ERKANNT; `warte_entscheidung` sagt, wann
# der Lauf abgebrochen wird.
_WA_POLL = re.compile(r"(?:for|while)\s*\(|do\s*\{", re.IGNORECASE)
_WA_SLEEP = re.compile(r"start-sleep|\bsleep\s+\d", re.IGNORECASE)
_WA_PROC = re.compile(r"get-process|get-ciminstance|tasklist", re.IGNORECASE)
# R13bp (2026-10-03, Nutzerauftrag): `Wait-Process` gehoert in die Wartebilanz. Gemessen in
# B255 (`runs/b255/stream.jsonl:98809` und `:101715`): das Modell wartete zweimal
# `Wait-Process -Id $pid2 -Timeout 600` auf den Hybrid-Lauf - je Aufruf 602,5 s / 602,3 s
# (also gut 20 min), waehrend `result.json` "warteschleifen: 0, warte_s: 0,5 s" meldete.
# Der Aufruf ist ERLAUBT (der Abbruch haengt an den verbotenen Mustern, s. `warte_erlaubt`),
# er wird nur gezaehlt. `Start-Process -Wait` bleibt wie bisher erlaubt UND ungezaehlt
# (dort gibt es keine Zeitangabe, die man schaetzen koennte).
_WA_WAITPROC = re.compile(r"\bwait-process\b", re.IGNORECASE)
_WA_STARTPROC_WAIT = re.compile(r"start-process[^\n]*-wait\b", re.IGNORECASE)
_WA_WAITPROC_TIMEOUT = re.compile(r"wait-process[^\n]*?-timeout\s+(\d+)", re.IGNORECASE)
# Der Grund, an dem `warte_erlaubt` ein ERLAUBTES Wartemuster erkennt.
WARTE_WAITPROC_GRUND = "Warten auf einen Prozess (Wait-Process)"
# Ein Warten auf eine feste Zeit ist auch ohne Schleife eine Warteschleife im Geist.
_WA_FEST = re.compile(r"start-sleep\s+(?:-seconds\s+)?(\d+(?:\.\d+)?)", re.IGNORECASE)
WARTE_FEST_AB_S = 30.0          # ab hier ist ein fester Schlaf keine Pause mehr
WARTE_EINZEL_AB_S = 300.0       # ein EINZELNER Aufruf mit so viel Wartezeit bricht ab
WARTE_SUMME_AB_S = 300.0        # aufsummierte Wartezeit im Lauf bricht ab


def warte_normalisiert(text) -> str:
    """Schreibweisen auf die Form bringen, die `_SLEEP_RE` versteht (R13v2, 2026-09-28).

    Anlass ist eine Messung mit ECHTEM claude-Lauf (`tools/r13v_sperrprobe.py`,
    Beleg `docs/_r13v_sperrprobe.txt`): die Sperre `PowerShell(Start-Sleep*)` lehnt
    `Start-Sleep` an JEDER Stelle des Befehls ab - auch in `if (…) { … }`, hinter
    `;` und in einer `for`-Schleife - und loest dabei den PowerShell-Alias `sleep`
    auf. `[Threading.Thread]::Sleep(2000)` ist dagegen NICHT gesperrt. Damit auch
    solche Befehle eine GESCHAETZTE Wartezeit bekommen (sonst bliebe es beim Alarm
    statt beim Abbruch), werden die verbreiteten Schreibweisen hier vereinheitlicht.
    """
    t = str(text or "")
    if not t or ("sleep" not in t.lower()):
        return t
    t = re.sub(r"\bsleep\s+-seconds\s+", "start-sleep -seconds ", t, flags=re.IGNORECASE)
    t = re.sub(r"\bsleep\s+-milliseconds\s+", "start-sleep -milliseconds ", t,
               flags=re.IGNORECASE)
    t = re.sub(r"(?:[\w.]*\b)?sleep\s*\(\s*(\d+)\s*\)",
               r"start-sleep -milliseconds \1", t, flags=re.IGNORECASE)
    return t


def warte_erlaubt(grund) -> bool:
    """Ist das ein ERLAUBTES Wartemuster? (R13bp) `True` = zaehlt mit, bricht aber nicht ab.

    Die Unterscheidung ist noetig, seit `Wait-Process` gezaehlt wird: die Notbremse
    (`warte_entscheidung`) darf einen Aufruf nicht toeten, den der Harness selbst als
    erlaubten Weg nennt.
    """
    return str(grund or "").startswith(WARTE_WAITPROC_GRUND)


def warte_verstoesse(warteschleifen) -> list:
    """Die NICHT erlaubten Eintraege einer Warteschleifen-Liste (R13bp)."""
    return [w for w in (warteschleifen or []) if not warte_erlaubt((w or {}).get("grund"))]


def warte_muster(befehl) -> str | None:
    """Erkennt Warteschleifen in einem Befehl (R13v, R13bp). `None` = keine Wartezeit.

    ERLAUBT und NICHT gemeldet (aber ab R13bp GEZAEHLT, s. `warte_erlaubt`):
      * `Wait-Process … -Timeout <s>` bzw. ein nacktes `Wait-Process`
        (Grund `WARTE_WAITPROC_GRUND`; die Notbremse sieht nur die verbotenen Muster),
      * `Start-Process -Wait`,
    erlaubt UND ungezaehlt:
      * ein fester `Start-Sleep` unter 30 s (kurze Kunstpause),
      * jeder Befehl ohne Schlaf/Prozessabfrage.
    Gemeldet:
      * Poll-Schleife: `for`/`while`/`do` MIT `Start-Sleep`/`Get-Process`,
      * fester Schlaf ab 30 s,
      * Schleife, die einen Prozess abfragt (auch ohne Schlaf-Schaetzung).

    R13bp: die VERBOTENEN Muster werden ZUERST geprueft. Vorher stand `Wait-Process` ganz
    oben und machte einen Befehl still erlaubt, auch wenn er eine Abfrageschleife enthielt.
    """
    t = warte_normalisiert(befehl)
    if not t:
        return None
    if _WA_POLL.search(t) and (_WA_SLEEP.search(t) or _WA_PROC.search(t)):
        return "Abfrageschleife (for/while + Start-Sleep/Get-Process)"
    m = _WA_FEST.search(t)
    if m:
        try:
            if float(m.group(1)) >= WARTE_FEST_AB_S:
                return f"fester Start-Sleep {m.group(1)} s"
        except (TypeError, ValueError):
            pass
    if _WA_POLL.search(t) and _WA_PROC.search(t):
        return "Schleife mit Prozessabfrage"
    if _WA_WAITPROC.search(t):
        return WARTE_WAITPROC_GRUND
    if _WA_STARTPROC_WAIT.search(t):
        return None
    return None


def warte_entscheidung(anzahl: int, summe_s: float, einzel_s: float) -> tuple[str | None, str]:
    """Was mit erkannten Warteschleifen geschehen soll (R13v).

    Rueckgabe: ("kill"|"alarm"|None, Begruendung).
      * `kill`  - der Lauf wird abgebrochen (Notbremse, wie beim Prozessabbau R13i):
                  ein einzelner Aufruf >= 300 s geschaetzter Wartezeit ODER die Summe
                  im Lauf >= 300 s. Die Zeit fehlt sonst am Ende fuer die Arbeit.
      * `alarm` - der erste Fund wird gemeldet (Telegram + Zusammenfassung), aber
                  der Lauf darf weiterarbeiten (eine kurze Pause ist kein Verbrechen).
    """
    if einzel_s >= WARTE_EINZEL_AB_S or summe_s >= WARTE_SUMME_AB_S:
        return "kill", (f"Warteschleife: {anzahl} Aufrufe, zusammen ~{summe_s:.0f} s "
                        f"(dieser ~{einzel_s:.0f} s) - Grenze {WARTE_SUMME_AB_S:.0f} s")
    return "alarm", (f"Warteschleife erkannt ({anzahl}): ~{summe_s:.0f} s geschaetzte "
                     f"Wartezeit")


def warte_sekunden(befehl) -> float:
    """Reine Wartezeit in einem Befehl schaetzen (R13h, R13bp).

    `Start-Sleep -Seconds 300` garantiert Wanduhr - auch wenn die Arbeit laengst
    fertig ist. Bei einer Poll-Schleife (`for ($i=0; ...)`) wird der Schritt mit der
    Schleifenzahl multipliziert, weil das die Obergrenze des Wartens ist.
    (Gemessen 2026-09-26: b174 hatte 19 solcher Befehle, zusammen 1993 s.)

    R13bp: `Wait-Process … -Timeout N` zaehlt mit der Obergrenze `N`. Gemessen in B255:
    zweimal `-Timeout 600`, die beiden Aufrufe dauerten 602,5 s und 602,3 s
    (`runs/b255/stream.jsonl:98809` / `:101715`, Dauer aus `result.json`).
    """
    text = warte_normalisiert(befehl)
    if not text:
        return 0.0
    klein = text.lower()
    if "sleep" not in klein and "wait-process" not in klein:
        return 0.0
    summe = 0.0
    for t in _SLEEP_RE.findall(text):
        if t[0]:
            wert = float(t[0])
        elif t[1]:
            wert = float(t[1]) / 1000.0
        else:
            wert = float(t[2])
        summe += wert
    m = _SCHLEIFE_RE.search(text)
    if m and summe:
        zahlen = re.findall(r"-lt\s+(\d+)", text)
        summe *= max(1, int(zahlen[0]) if zahlen else 1)
    # R13bp: Wait-Process steht NACH der Schleifen-Vielfachen-Regel - die Obergrenze gilt
    # je Aufruf, nicht je Schleifenschritt (das Modell setzt Wait-Process einzeln ab).
    for n in _WA_WAITPROC_TIMEOUT.findall(text):
        summe += float(n)
    return summe


# ---------------------------------------------------------------------------
# R13ao (2026-09-29, Auftrag Teil B): PREFLIGHT-AUFRUFE ZAEHLEN.
# Der Preflight (`scripts/preflight.py`, ~10 min) gehoert ans Batch-ENDE. Laeuft er
# vorher, muss er spaeter wiederholt werden - er kostet dann doppelt. Der Hook
# (`tools/batch_uhr.py`) weist den Worker darauf hin und schreibt je Aufruf eine Zeile;
# `hx/worker.py:_finish_run` zaehlt sie nach `result.json`. Drei Leser, EINE Regel -
# deshalb steht sie hier und nicht dreimal.
PREFLIGHT_WORT = "preflight.py"
# Die Werkzeugnamen, unter denen ein Shell-Aufruf im Mitschnitt steht (R13i/R13v).
SHELL_WERKZEUGE = ("PowerShell", "Bash", "Shell", "Terminal")
# Ein START ist ein Interpreter (`python`, `python.exe`, `py`) mit `preflight.py` als
# Argument. GEMESSEN an B206-B215 (`docs/_r13ao_messung.txt`): die blosse Erwaehnung ist
# haeufig - `Select-String -Path scripts/preflight.py`, `git add … scripts/preflight.py`,
# `Get-CimInstance … -like '*preflight.py*before*'` (Ueberwachung des Laufs). Von 23
# Treffern der reinen Textsuche waren so nur 8 echte Starts.
_RE_PREFLIGHT_START = re.compile(
    r"\b(?:python[0-9.]*(?:\.exe)?|py)\b[^|;&\n]{0,60}?preflight\.py", re.IGNORECASE)
# Und ein FILTER ist die Suche/Ueberwachung im SELBEN Befehlsteil: sie nennt den Aufruf
# nur (`-like`, `CommandLine`, `Select-String`, `Get-Content`, `git add`).
_RE_PREFLIGHT_FILTER = re.compile(
    r"-like\b|\bCommandLine\b|Select-String|Get-Content|\bgit\s+add\b", re.IGNORECASE)


def _befehls_teile(befehl) -> list[str]:
    """Einen Shell-Befehl an `;`, `|` und Zeilenumbruch in Teile zerlegen.

    Wichtig fuer die Filter-Regel: der echte Preflight-Lauf in B206 steht in einem
    Verbund, dessen SPAETERER Teil `Get-Content analysis/_preflight_206.txt` ist. Ueber
    den ganzen Befehl geprueft haette dieser Filter den echten Lauf verschluckt.
    """
    return [t for t in re.split(r"[;|\n]|&&", str(befehl or "")) if t.strip()]


def ist_preflight_aufruf(name, eingabe=None) -> bool:
    """**Startet** dieser Werkzeugaufruf den Preflight? (R13ao)

    Geprueft werden **beide** Seiten: das Shell-Werkzeug (`name`) UND die Befehlsspalte
    `input.command` - nicht das ganze `input`: `description`-Texte nennen den Preflight
    oft, ohne ihn zu starten; das ERGEBNIS eines `Read`/`Grep` (das denselben Text
    enthaelt) ist nie ein Aufruf.

    Ein Treffer muss ein **Start** sein (Interpreter + `preflight.py`) und darf kein
    **Filter** sein (dieselbe Befehlsteil durchsucht/ueberwacht den Aufruf nur).
    Definition und Messung: `docs/_r13ao_belege.md`, `docs/_r13ao_messung.txt`.
    """
    if str(name or "") not in SHELL_WERKZEUGE:
        return False
    if not isinstance(eingabe, dict):
        return False
    for teil in _befehls_teile(eingabe.get("command")):
        if (_RE_PREFLIGHT_START.search(teil)
                and not _RE_PREFLIGHT_FILTER.search(teil)):
            return True
    return False


def nennt_preflight_nur(name, eingabe=None) -> bool:
    """Nennt der Aufruf `preflight.py`, OHNE ihn zu starten? (R13ao, nur Bericht)

    Fuer die Nachzaehlung: wie viele Treffer der reinen Textsuche sind keine Starts.
    Fuer den Hook und die Zaehler ist das **kein** Aufruf.
    """
    if str(name or "") not in SHELL_WERKZEUGE or not isinstance(eingabe, dict):
        return False
    return PREFLIGHT_WORT in str(eingabe.get("command") or "")


class SecretWatch:
    """Sucht Schluessel-ZUGRIFFE in Werkzeugaufrufen und Schluessel-WERTE im Mitschnitt.

    Zwei getrennte Suchen, aus gutem Grund (R13g, 2026-09-26):

    * **Werte**: JEDE Zeile wird geprueft. Ein Schluesselwert hat im Mitschnitt
      nichts zu suchen; ein Treffer ist ein Leck. Verglichen wird nur im Speicher
      (`str in str`), ausgegeben wird der NAME der Datei - nie der Wert.
    * **Pfade**: nur **Werkzeugaufrufe** werden geprueft. Der Pfad darf in
      Dokumenten, Prompts und Modellantworten vorkommen, ohne dass jemand zugreift;
      wer den ganzen Mitschnitt danach durchsucht, meldet Fehlalarme (dieselbe
      Falle wie bei den "abgelehnten Werkzeugaufrufen", B172/B173). Bei
      schreibenden Werkzeugen zaehlt nur das ZIEL, nicht der Textinhalt.
    """

    SCHREIBER = ("Write", "Edit", "MultiEdit", "NotebookEdit")
    ZIEL_FELDER = ("file_path", "path", "notebook_path", "target_file")

    def __init__(self, pfade=(), werte: dict | None = None):
        self.pfade = [_norm(p).rstrip("/") for p in pfade if p]
        # Kurze Werte waeren als Suchmuster wertlos (und traegt ein Testtoken der
        # Harness-Suite zufaellig dieselbe Zeichenfolge, waere das ein Fehlalarm).
        self.werte = {k: v for k, v in (werte or {}).items() if v and len(v) >= 8}

    def werte_in(self, text: str) -> list[str]:
        """Namen der Schluessel, deren WERT im Text steht (nie der Wert selbst)."""
        if not text or not self.werte:
            return []
        return [name for name, wert in self.werte.items() if wert in text]

    def pfad_in(self, werkzeug: str, eingabe) -> list[str]:
        """Pfadmuster in einem Werkzeugaufruf (bei Schreibern nur das Ziel).

        Achtung Normierung: `json.dumps` schreibt Windows-Pfade als `g:\\Harness\\...`.
        Erst backslash->slash und dann mehrfache Schraegstriche zusammenziehen, sonst
        passt `g:/harness/secrets` nicht auf `g:\\harness\\secrets` (am 2026-09-26
        genau so gemessen - der Fall "Read auf den alten Ort" blieb unentdeckt).
        """
        if not self.pfade or not eingabe:
            return []
        if werkzeug in self.SCHREIBER:
            teile = []
            if isinstance(eingabe, dict):
                teile = [str(eingabe.get(f) or "") for f in self.ZIEL_FELDER]
            pruef = " ".join(teile)
        else:
            pruef = eingabe if isinstance(eingabe, str) else json.dumps(eingabe,
                                                                        ensure_ascii=False)
        low = _norm(pruef)
        return [m for m in self.pfade if m and m in low]

    def entschaerfen(self, text: str, grenze: int = 160) -> str:
        """Kurzfassung eines Werkzeugaufrufs als Beleg - Schluesselwerte ersetzt.

        Ohne diesen Schritt koennte ein Aufruf wie `$k = "sk-..."` den Wert in die
        Belegdatei tragen; genau das soll die Ueberwachung verhindern.
        """
        out = " ".join(str(text or "").split())
        for wert in self.werte.values():
            if wert:
                out = out.replace(wert, "<WERT>")
        return out[:grenze]


def secret_watch(cfg) -> SecretWatch:
    """Ueberwachung mit den Werten und Pfaden DIESER Konfiguration bauen."""
    werte: dict[str, str] = {}
    for name in secrets.NAMEN:
        try:
            werte[name] = secrets.load(cfg.secrets_dir, name)
        except Exception:                                        # noqa: BLE001
            continue
    return SecretWatch([str(cfg.secrets_dir), *secrets.ALT_ORTE], werte)


def secret_beleg_pfad(cfg):
    return Path(cfg.sub("logs")) / "secret-zugriff.jsonl"


def schreibe_secret_beleg(cfg, treffer: list[dict], rolle: str, batch: int | None) -> str:
    """Treffer als Beleg ablegen - ohne Werte, ohne Prompt-Text."""
    if not treffer:
        return ""
    ziel = secret_beleg_pfad(cfg)
    for t in treffer:
        append_jsonl(ziel, {"ts": now_iso(), "rolle": rolle, "batch": int(batch or 0),
                            "art": t.get("art"), "werkzeug": t.get("werkzeug"),
                            "name": t.get("name"), "stelle": t.get("stelle") or ""})
    return str(ziel)


def secret_alarm_text(treffer: list[dict], rolle: str, batch: int | None) -> str:
    """Telegram-Text fuer einen Treffer. Enthaelt nur Art, Werkzeug und Dateinamen."""
    if not treffer:
        return ""
    teile = []
    for t in treffer[:5]:
        if t.get("art") == "wert":
            teile.append(f"Schluesselwert in der Ausgabe ({t.get('name')})")
        else:
            teile.append(f"{t.get('werkzeug')} -> {t.get('name')}")
    mehr = "" if len(treffer) <= 5 else f" (+{len(treffer) - 5} weitere)"
    return (f"SECRET-ZUGRIFF: {len(treffer)} Treffer im {rolle}-Lauf"
            f"{f' (Batch {batch})' if batch else ''}: " + "; ".join(teile) + mehr)


def secret_meldungen(cfg, batch: int | None = None) -> list[dict]:
    """Belegte Treffer zuruecklesen (fuer den Review-Messdatenblock)."""
    p = secret_beleg_pfad(cfg)
    if not p.is_file():
        return []
    out = []
    for ln in read_text(p).splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if batch and int(obj.get("batch") or 0) != int(batch):
            continue
        out.append(obj)
    return out


def scanne_mitschnitt(cfg, pfad) -> list[dict]:
    """Einen fertigen Mitschnitt auf Schluessel-Zugriffe/Werte pruefen."""
    p = Path(pfad)
    if not p.is_file():
        return []
    w = secret_watch(cfg)
    stats = StreamStats(secret_watch=w)
    with open(p, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            stats.feed(line)
    return stats.secret_hits


# ------------------------------------------------------- Nutzerlimit (R13p)
# Der Abo-Verbrauch steht in JEDEM Abo-Mitschnitt: Claude Code schreibt ein
# `rate_limit_event` mit `unifiedWindows.{five_hour,seven_day}` (Auslastung 0..1
# und resetsAt). Der DeepSeek-Worker hat kein Claude-Kontingent und liefert es
# nicht - die Werte kommen also aus Review, Uebergabe und /ask.
RATE_SCHWELLE = 0.8
RATE_FENSTER = (("five_hour", "Sitzung (5 h)"), ("seven_day", "Woche (7 Tage)"))


def resets_zeit(stamp) -> str:
    """`resetsAt` (Unix-Sekunden) in deutscher Zeit: `27.09.2026 18:30 (UTC+02:00)`."""
    try:
        dt = datetime.fromtimestamp(int(stamp), tz=timezone.utc).astimezone()
    except (TypeError, ValueError, OSError, OverflowError):
        return "?"
    off = dt.utcoffset() or timedelta(0)
    vorz = "+" if off >= timedelta(0) else "-"
    std, rest = divmod(abs(int(off.total_seconds())), 3600)
    return f"{dt:%d.%m.%Y %H:%M} (UTC{vorz}{std:02d}:{rest // 60:02d})"


def rate_limit_werte(info: dict) -> list[dict]:
    """Beide Fenster als Liste: Schluessel, Name, Anteil (0..1), Reset-Zeit."""
    fenster = (info or {}).get("unifiedWindows") or {}
    out: list[dict] = []
    for schluessel, name in RATE_FENSTER:
        d = fenster.get(schluessel) if isinstance(fenster, dict) else None
        if not isinstance(d, dict):
            continue
        try:
            anteil = float(d.get("utilization"))
        except (TypeError, ValueError):
            continue
        out.append({"schluessel": schluessel, "name": name, "anteil": anteil,
                    "resets_at": d.get("resetsAt"), "reset": resets_zeit(d.get("resetsAt"))})
    return out


def rate_limit_zeile(info: dict) -> str:
    """Eine Zeile fuer /status: beide Fenster mit Prozent und Ruectsetzzeit."""
    teile = [f"{w['name']}: {w['anteil'] * 100:.0f} % (Reset {w['reset']})"
             for w in rate_limit_werte(info)]
    return " | ".join(teile) if teile else "keine Angaben"


def rate_limit_hoch(info: dict, schwelle: float = RATE_SCHWELLE) -> list[dict]:
    return [w for w in rate_limit_werte(info) if w["anteil"] >= schwelle]


def rate_limit_warnung(info: dict, schwelle: float = RATE_SCHWELLE) -> str:
    """Telegram-Text, solange ein Fenster ueber der Schwelle liegt (sonst leer)."""
    hoch = rate_limit_hoch(info, schwelle)
    if not hoch:
        return ""
    zeilen = [f"NUTZERLIMIT: {w['name']} zu {w['anteil'] * 100:.0f} % verbraucht "
              f"(Schwelle {schwelle * 100:.0f} %), Reset {w['reset']}" for w in hoch]
    zeilen.append("Bei 100 % ist bis zum Reset Schluss - das Abo hat kein Nachkaufen "
                  "(overageStatus: rejected).")
    return "\n".join(zeilen)


def rate_limit_schluessel(info: dict, schwelle: float = RATE_SCHWELLE) -> str:
    """Schluessel fuer `notify_once`: eine Warnung je Fenster UND Reset-Zeitpunkt."""
    return ";".join(f"{w['schluessel']}@{w.get('resets_at')}"
                    for w in rate_limit_hoch(info, schwelle))


def rate_limit_pfad(cfg) -> Path:
    return Path(cfg.sub("logs")) / "rate-limit.json"


def schreibe_rate_limit(cfg, info: dict, quelle: str = "") -> Path | None:
    """Letzte bekannte Auslastung ablegen (der Takt liest sie von dort)."""
    if not rate_limit_werte(info or {}):
        return None
    p = rate_limit_pfad(cfg)
    ensure_dir(p.parent)
    write_text_atomic(p, json.dumps({"ts": now_iso(), "quelle": quelle, "info": info,
                                     "zeile": rate_limit_zeile(info)}, ensure_ascii=False,
                                    indent=1) + "\n")
    return p


def lies_rate_limit(cfg) -> dict:
    """Zuletzt gemeldete Auslastung (leer, wenn noch keine gemessen wurde)."""
    p = rate_limit_pfad(cfg)
    if not p.is_file():
        return {}
    try:
        d = json.loads(read_text(p))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def rate_limit_aus_mitschnitt(cfg, pfad) -> dict:
    """Die LETZTE Limit-Angabe aus einem fertigen Mitschnitt (oder `{}`).

    Gedacht fuer Laeufe, bei denen die Zahlen nicht schon im Speicher stehen
    (Reviewer, /ask). Der grosse Worker-Mitschnitt wird NICHT noch einmal gelesen -
    dort liegen die Werte ohnehin schon im `StreamStats` des Laufs.
    """
    p = Path(pfad)
    if not p.is_file():
        return {}
    stats = StreamStats()
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if "rate_limit_event" in line:
                    stats.feed(line)
    except OSError:
        return {}
    return stats.rate_limit



# ----------------------------------------------- Kontext-Messung (Auftrag 2026-09-29)
# Die Kontextgroesse einer Anfrage ist die Summe der drei Eingabewerte ihrer Antwort
# (`input_tokens` + `cache_read_input_tokens` + `cache_creation_input_tokens`) - das ist
# der Prompt, den das Modell in DIESEM Schritt gesehen hat. Die Feldnamen sind am ECHTEN
# Mitschnitt geprueft (`runs/b205..b212/stream.jsonl`): `assistant.message.usage` traegt
# genau diese drei Schluessel. `system` fuehrt `subtype` `init|thinking_tokens|task_*` -
# ein `compact_boundary` kam in B205-B212 NICHT vor (Auto-Compact lief nie).
KONTEXT_VERLAUF_SCHRITT = 25
# Als Kompaktierung gilt: ein `compact_boundary`-Ereignis ODER ein sprunghafter
# Rueckgang der Kontextsumme um mindestens so viele Tokens UND mindestens diesen Anteil.
KOMPAKT_RUECKGANG_MIN = 20000
KOMPAKT_RUECKGANG_ANTEIL = 0.20


# ------------------------------------------------- API-/Gateway-Fehler (R13bm)
# Die CLI schreibt einen Verbindungs-/Gateway-Fehler als **synthetische**
# Assistenten-Nachricht in den Mitschnitt. Gemessen an B235
# (`runs/b235/stream.jsonl:28441`, Fixture `tests/fixtures/b235_api_fehler.jsonl`):
#
#   {"type":"assistant","message":{"model":"<synthetic>","role":"assistant",
#    "content":[{"type":"text","text":"API Error: API returned an empty or
#                 malformed response (HTTP 200) …"}]}}
#
# Bis R13bl hat das NICHTS ausgewertet: `api_errors` war ein Feld ohne Schreiber
# (immer `[]`, Beleg `docs/_r13bl_fehlerverhalten.md` Fall A3).
API_FEHLER_TEXT = 300
_RE_API_ERROR = re.compile(r"^\s*API\s*Error\b", re.IGNORECASE)


def ist_api_fehler(msg: dict, text: str) -> bool:
    """Ist diese Assistenten-Nachricht ein API-/Gateway-Fehler der CLI?

    Zwei Kennzeichen, beide am echten Beleg gemessen:

      * der Text **beginnt** mit `API Error` (so schreibt die CLI den Fehler), oder
      * das Modellfeld ist der Platzhalter `<synthetic>` - dann ist die Nachricht
        keine Modellantwort, sondern von der CLI selbst erzeugt.

    Ein normaler Bericht, der den Fehler nur **erwaehnt** (nicht am Textanfang),
    zaehlt nicht.
    """
    if _RE_API_ERROR.match(text or ""):
        return True
    return str((msg or {}).get("model") or "").strip().lower() == "<synthetic>"


class StreamStats:
    def __init__(self, secret_watch: "SecretWatch | None" = None):
        # R13g: Ueberwachung der Schluessel. Ohne Watch kostet das nichts.
        self.secret_watch = secret_watch
        self.secret_hits: list[dict] = []
        self.session_id: str | None = None
        self.model: str | None = None
        self.models: dict[str, int] = {}
        # R13p: Nutzerlimit des Abos. Claude Code schreibt im Mitschnitt ein
        # `rate_limit_event` mit `rate_limit_info.unifiedWindows.{five_hour,seven_day}`
        # (Auslastung 0..1 + resetsAt). Es kommt nur bei den Abo-Laeufen (Reviewer,
        # Uebergabe, /ask) - der DeepSeek-Worker hat kein Claude-Kontingent.
        self.rate_limit: dict = {}
        self.mcp_servers: dict = {}
        self.permission_mode: str | None = None
        self.tools_available: int | None = None

        self._msg_ids: set[str] = set()
        self._by_msg: dict[str, dict] = {}       # message.id -> Eintrag (in place aktualisiert)
        self.requests: list[dict] = []          # je Anfrage: {ts, id, miss, hit, creation, output}
        self._tool_ids: set[str] = set()
        self._tool_names: dict[str, str] = {}   # tool_use.id -> Werkzeugname
        self.tools: list[dict] = []             # je Aufruf: {zeile, ts, id, name, input}
        # R13as: die ZEILE im Mitschnitt. Der Reihenfolge-Waechter zitiert Fundstellen
        # wie einen Beleg (`runs/b218/stream.jsonl:1071`), damit der Leser nachsehen kann.
        # Gezaehlt wird jeder Aufruf von `feed` - genau einmal je gelesener Zeile
        # (`hx/proc.py` liest zeilenweise und zaehlt dort dasselbe in `res.lines`).
        self.zeilen: int = 0
        self.tool_counts: dict[str, int] = {}
        # R13ar (30.09.2026): WERKZEUGRUNDEN = Modellantworten MIT Werkzeugaufruf.
        # GEMESSEN: ein `--max-turns N` bricht nach N solchen Antworten ab
        # (`error_max_turns`, Beleg `docs/_r13ar_limit_probe_reviewer.txt`: Limit 2 ->
        # Abbruch nach 2 Runden, `num_turns=3`). `num_turns` im Ergebnis-Ereignis ist
        # eine ANDERE Zahl (Werkzeugergebnisse + 1: `runs/meta-214` 34 Aufrufe -> 35,
        # aber nur 23 Runden). Gezaehlt wird nach `message.id` - die CLI schreibt je
        # Inhaltsblock ein eigenes `assistant`-Ereignis (Modul-Docstring).
        self._runden_ids: set[str] = set()
        self.runden_ohne_id: int = 0

        self.texts: list[str] = []
        self.tool_results: list[str] = []
        self.reasoning_blocks: int = 0
        self.thinking_tokens: int = 0
        self.denials: list[str] = []
        self.tool_errors: list[dict] = []       # echte Werkzeugfehler: {id, name, text}
        self.http_state: list[dict] = []        # HTTP-Beruehrungen des Ghidra-Zustands
        # R13bm: API-/Gateway-Fehler der CLI mit Zeitpunkt, gekuerztem Text und der
        # Zeile im Mitschnitt (`zeilen` ist 1-basiert, wie ein Leser zaehlt).
        self.api_errors: list[dict] = []
        # R13bm: kam der LETZTE Modelltext aus einer API-Fehlermeldung? Das ist die
        # Bedingung der Klasse "Infrastrukturabbruch" (`killed_reason = "infra"`).
        self.letzter_text_api_fehler: bool = False
        self.result: dict | None = None
        # Auftrag 2026-09-29: Fortsetzungen laufen im SELBEN Chat - der Mitschnitt traegt
        # dann MEHRERE `result`-Ereignisse. `self.result` bleibt das letzte (Antworttext,
        # Fehlerflag), `result_ereignisse` sind alle (Summen).
        self.result_ereignisse: list[dict] = []
        # Auftrag 2026-09-29: Kontextmessung + Kompaktierung.
        self.kompakt_marker: list[int] = []      # Anfrage-Nr je `compact_boundary`
        self._msg_werkzeug: dict[str, bool] = {}  # message.id -> trug einen Werkzeugaufruf
        self.letzte_msg_id: str | None = None
        self.raw_events: int = 0
        # R13h: Laufzeit-Profil (aus den Zeitstempeln des Mitschnitts, nichts geraten).
        self.t_erste: float | None = None
        self.t_letzte: float | None = None
        self._offen: dict[str, tuple[float, str, str]] = {}
        # R13aj: abgeschlossene Aufrufe als Zeitintervalle [(t0, t1), ...] - daraus
        # kommt `parallel` (siehe PARALLEL_TOLERANZ_S).
        self._intervalle: list[tuple[float, float]] = []
        self.tool_seconds: float = 0.0
        self.wait_seconds: float = 0.0
        self.slow_tools: list[dict] = []     # die laengsten Werkzeugaufrufe (max 5)
        # R13i: Muster-Prozessabbau (kann den Harness selbst toeten)
        self.abbau: list[dict] = []
        # R13v: Warteschleifen (Abfrageschleifen, feste Schlafe) - mit Wartezeit
        self.warteschleifen: list[dict] = []

    # ------------------------------------------------------------------ Feed
    def feed(self, line: str) -> dict | None:
        self.zeilen += 1
        line = line.strip()
        if not line:
            return None
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(ev, dict):
            return None
        self.raw_events += 1
        etype = ev.get("type")
        t_ev = _zeit(ev.get("timestamp"))
        if t_ev is not None:
            self.t_erste = t_ev if self.t_erste is None else min(self.t_erste, t_ev)
            self.t_letzte = t_ev if self.t_letzte is None else max(self.t_letzte, t_ev)

        # R13g: Werte in JEDER Zeile suchen (ein Schluesselwert gehoert nirgends hin).
        if self.secret_watch is not None:
            for name in self.secret_watch.werte_in(line):
                self._secret("wert", "-", name)

        if etype == "system" and ev.get("subtype") == "init":
            self.session_id = ev.get("session_id") or self.session_id
            self.model = ev.get("model") or self.model
            if self.model:
                self.models[self.model] = self.models.get(self.model, 0) + 1
            servers = ev.get("mcp_servers")
            if isinstance(servers, list):
                self.mcp_servers = {s.get("name"): s.get("status") for s in servers if isinstance(s, dict)}
            elif isinstance(servers, dict):
                self.mcp_servers = servers
            self.permission_mode = ev.get("permissionMode") or self.permission_mode
            tools = ev.get("tools")
            if isinstance(tools, list):
                self.tools_available = len(tools)

        elif etype == "system" and ev.get("subtype") == "compact_boundary":
            # Auftrag 2026-09-29: ausdrueckliche Kompaktierungsgrenze. In B205-B212 kam
            # keine vor; die Erkennung ist vorbereitet und wird ueber die Zahl der bis
            # dahin gesehenen Anfragen verankert.
            self.kompakt_marker.append(len(self.requests))

        elif etype == "rate_limit_event":
            info = ev.get("rate_limit_info")
            if isinstance(info, dict) and info:
                self.rate_limit = info

        elif etype == "assistant":
            msg = ev.get("message") or {}
            mid = msg.get("id")
            usage = msg.get("usage") or {}
            if mid:
                eintrag = self._by_msg.get(mid)
                if eintrag is None:
                    eintrag = {"ts": ev.get("timestamp") or "", "id": mid,
                               "model": msg.get("model"), "miss": 0, "hit": 0,
                               "creation": 0, "output": 0, "thinking": 0, "events": 0}
                    self._by_msg[mid] = eintrag
                    self.requests.append(eintrag)
                    if msg.get("model"):
                        self.models[msg["model"]] = self.models.get(msg["model"], 0) + 1
                eintrag["events"] = int(eintrag.get("events") or 0) + 1
                # R11-2: NICHT den ersten Wert nehmen. Eine Antwort erzeugt mehrere
                # assistant-Ereignisse, und die Nutzung waechst darin mit; es gilt
                # das MAXIMUM je message.id (Gegenprobe: usage im result-Ereignis).
                for key, ukey in (("miss", "input_tokens"),
                                  ("hit", "cache_read_input_tokens"),
                                  ("creation", "cache_creation_input_tokens"),
                                  ("output", "output_tokens")):
                    wert = int(usage.get(ukey) or 0)
                    if wert > int(eintrag.get(key) or 0):
                        eintrag[key] = wert
                details = usage.get("output_tokens_details") or {}
                think = int(details.get("thinking_tokens") or 0)
                if think > int(eintrag.get("thinking") or 0):
                    eintrag["thinking"] = think
                if msg.get("model"):
                    eintrag["model"] = msg["model"]
                self.thinking_tokens = sum(int(e.get("thinking") or 0) for e in self.requests)
            for block in (msg.get("content") or []):
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "text":
                    txt = block.get("text") or ""
                    if txt.strip():
                        self.texts.append(txt)
                        if ist_api_fehler(msg, txt):
                            # R13bm: festhalten - Zeitpunkt, gekuerzter Text, Zeile.
                            self.letzter_text_api_fehler = True
                            self.api_errors.append(
                                {"zeile": self.zeilen,
                                 "ts": ev.get("timestamp") or "",
                                 "text": " ".join(txt.split())[:API_FEHLER_TEXT]})
                        else:
                            self.letzter_text_api_fehler = False
                elif btype in ("thinking", "redacted_thinking"):
                    self.reasoning_blocks += 1
                elif btype == "tool_use":
                    tid = block.get("id")
                    if tid and tid in self._tool_ids:
                        continue
                    if tid:
                        self._tool_ids.add(tid)
                    name = block.get("name") or "?"
                    if tid:
                        self._tool_names[tid] = name
                    self.tools.append({"zeile": self.zeilen, "ts": ev.get("timestamp") or "",
                                       "id": tid, "name": name,
                                       "input": block.get("input") or {}})
                    self.tool_counts[name] = self.tool_counts.get(name, 0) + 1
                    # R13ar: diese Nachricht hat einen Werkzeugaufruf -> sie ist EINE
                    # Runde (mehrere Aufrufe in derselben Nachricht zaehlen einmal).
                    if mid:
                        self._runden_ids.add(str(mid))
                    else:
                        self.runden_ohne_id += 1
                    if self.secret_watch is not None:
                        self._secret_pfad(name, block.get("input") or {}, tid)
                    # R13i: Prozessabbau nach Muster erkennen (vor der Ausfuehrung:
                    # der Harness kann den Lauf noch abbrechen).
                    if name in ("PowerShell", "Bash", "Shell", "Terminal"):
                        eingabe = block.get("input") or {}
                        befehl_roh = eingabe.get("command") if isinstance(eingabe, dict) else ""
                        grund = abbau_gefahr(befehl_roh)
                        if grund:
                            self.abbau.append({"werkzeug": name, "grund": grund,
                                               "kurz": kurz_input(eingabe)})
                        # R13v: Warteschleifen erkennen (Abfrageschleife/fester Schlaf).
                        grund_warte = warte_muster(befehl_roh)
                        if grund_warte:
                            self.warteschleifen.append(
                                {"werkzeug": name, "grund": grund_warte,
                                 "kurz": " ".join(str(befehl_roh).split())[:150],
                                 "warte_s": round(warte_sekunden(befehl_roh), 1)})
                    # R13h: Werkzeugzeit und Wartezeit laufend mitschreiben.
                    if t_ev is not None:
                        self._offen[str(tid)] = (t_ev, name, kurz_input(block.get("input")))
                    self.wait_seconds += warte_sekunden(
                        (block.get("input") or {}).get("command")
                        if isinstance(block.get("input"), dict) else "")
                    if name in HTTP_TOOLS:
                        self._scan_http(json.dumps(block.get("input") or {},
                                                   ensure_ascii=False))
            # Auftrag 2026-09-29: trug DIESE Antwort einen Werkzeugaufruf? Gebraucht fuer
            # die Fortsetzungs-Bedingung (a): ein regulaeres Ende liegt vor, wenn die
            # LETZTE Antwort des Modells keinen Werkzeugaufruf mehr enthaelt.
            mid_key = str(mid or "")
            hat_wz = any(isinstance(b, dict) and b.get("type") == "tool_use"
                         for b in (msg.get("content") or []))
            if mid_key:
                self._msg_werkzeug[mid_key] = bool(self._msg_werkzeug.get(mid_key)) or hat_wz
                self.letzte_msg_id = mid_key

        elif etype == "user":
            # Kann Werkzeugergebnisse oder Verweigerungen tragen.
            content = ((ev.get("message") or {}).get("content")) or []
            for block in (content if isinstance(content, list) else []):
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    body = block.get("content")
                    text = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
                    # R13h: Ende eines Werkzeugaufrufs - Dauer festhalten.
                    self._tool_ende(str(block.get("tool_use_id")), t_ev)
                    if text:
                        self.tool_results.append(text[:20000])
                    art = self._fehlerart(block, text)
                    if art:
                        tid = block.get("tool_use_id")
                        self.tool_errors.append({"id": tid,
                                                 "name": self._tool_name(tid),
                                                 "art": art, "text": text[:300]})
                        if art == "gesperrt":
                            self.denials.append(text[:300])

        elif etype == "result":
            self.result = ev
            self.result_ereignisse.append(ev)
            for d in (ev.get("permission_denials") or []):
                self.denials.append(str(d)[:300])

        return ev

    # ------------------------------------------------------- Fehler erkennen
    def _secret(self, art: str, werkzeug: str, name: str, stelle: str = "") -> None:
        """Treffer festhalten - nie den Wert, nur Art, Werkzeug und Dateiname."""
        for t in self.secret_hits:
            if t["art"] == art and t["werkzeug"] == werkzeug and t["name"] == name:
                t["anzahl"] = int(t.get("anzahl") or 1) + 1
                return
        self.secret_hits.append({"art": art, "werkzeug": werkzeug, "name": name,
                                 "stelle": stelle, "anzahl": 1})

    def _secret_pfad(self, werkzeug: str, eingabe, tid) -> None:
        """Zugriffsversuch auf einen Schluesselort in einem Werkzeugaufruf."""
        muster = self.secret_watch.pfad_in(werkzeug, eingabe)
        if not muster:
            return
        roh = eingabe if isinstance(eingabe, str) else json.dumps(eingabe, ensure_ascii=False)
        stelle = self.secret_watch.entschaerfen(roh)
        for m in muster:
            self._secret("pfad", werkzeug, m, stelle=stelle)

    def _scan_http(self, text: str) -> None:
        """Vorbeigehende HTTP-Aufrufe auf den Ghidra-Port bemerken (Punkt 2c).

        Kein Alarm und keine Wertung: das ist der dokumentierte Ausweichweg.
        Vermerkt werden nur die Endpunkte, die den gemeinsamen Zustand beruehren.
        """
        if not text or "8089" not in text or not HTTP_RE.search(text):
            return
        for ep in HTTP_STATE_ENDPOINTS:
            if ep in text:
                self.http_state.append({"endpoint": ep, "text": text[:200]})
                return

    def _tool_name(self, tool_use_id) -> str:
        return self._tool_names.get(str(tool_use_id), "?")

    def _tool_ende(self, tid: str, t_ende: float | None) -> None:
        """Dauer eines Werkzeugaufrufs festhalten (R13h).

        R13aj: Dazu die Zahl der Aufrufe, mit denen sich dieser ueberlappt
        (`parallel`, 1 = allein). Noch offene Aufrufe ueberlappen bis jetzt, sie
        zaehlen mit; abgeschlossene nur, wenn sich die Intervalle um mehr als
        `PARALLEL_TOLERANZ_S` schneiden.
        """
        e = self._offen.pop(str(tid), None)
        if not e or t_ende is None:
            return
        dauer = max(0.0, t_ende - e[0])
        parallel = 1 + len(self._offen) + self._parallel_dazu(e[0], t_ende)
        self._intervalle.append((e[0], t_ende))
        self.tool_seconds += dauer
        self.slow_tools.append({"name": e[1], "kurz": e[2], "dauer_s": round(dauer, 1),
                                "parallel": parallel})
        self.slow_tools.sort(key=lambda w: -w["dauer_s"])
        del self.slow_tools[5:]

    def _parallel_dazu(self, t0: float, t1: float) -> int:
        """Zahl der ABGESCHLOSSENEN Aufrufe, die sich mit [t0, t1] ueberlappen (R13aj)."""
        return sum(1 for a0, a1 in self._intervalle
                   if min(a1, t1) - max(a0, t0) > PARALLEL_TOLERANZ_S)

    def laufzeit_profil(self) -> dict:
        """Wo ging die Zeit hin? (R13h) - Werkzeuge, Modell, Warten, Harness-Rest.

        Alles aus den Zeitstempeln des Mitschnitts; nichts geschaetzt. `modell_s`
        ist die Spanne minus Werkzeugzeit (Denken + API), `rest_s` vergibt der
        Aufrufer gegen die Wanduhr, die er selbst gemessen hat.
        """
        spanne = ((self.t_letzte - self.t_erste)
                  if (self.t_erste is not None and self.t_letzte is not None) else 0.0)
        return {"spanne_s": round(spanne, 1),
                "werkzeug_s": round(self.tool_seconds, 1),
                "modell_s": round(max(0.0, spanne - self.tool_seconds), 1),
                "warte_s": round(self.wait_seconds, 1),
                # R13v: Warteschleifen getrennt ausweisen (Anzahl, geschaetzte Summe,
                # die schlimmsten) - sie kosten dieselbe Zeit wie `warte_s`, sind aber
                # eine VERMEIDBARE Ursache (der erlaubte Weg steht im Vorspann).
                "warteschleifen": len(self.warteschleifen),
                "warteschleifen_s": round(sum(float(w.get("warte_s") or 0)
                                              for w in self.warteschleifen), 1),
                "warteschleifen_liste": list(self.warteschleifen[:5]),
                "langsamste": list(self.slow_tools)}

    @staticmethod
    def _fehlerart(block: dict, text: str) -> str | None:
        """Art des Werkzeugergebnisses: None = Erfolg, sonst 'gesperrt' oder 'fehler'.

        R13e (gemessen an B172/B173): Die alte Regel suchte den Satz
        "no such tool available" IRGENDWO im Ergebnis. Liest der Worker ein
        Dokument, das diesen Satz zitiert (Batch-Dokument, ghidra-mcp-notes.md),
        landete der DATEIINHALT als "abgelehnter Werkzeugaufruf" in der Bilanz -
        B173 meldete so vier Ablehnungen, von denen genau eine echt war. Ein
        echtes Fehlerergebnis traegt den Wrapper <tool_use_error> oder is_error.
        """
        if not text and not block.get("is_error"):
            return None
        low = text.lower()
        # R13e: drei Formulierungen bedeuten "gesperrt": das Werkzeug ist gar nicht
        # vorhanden, im Client abgeschaltet, oder es braucht eine Freigabe, die es
        # hier nicht gibt (headless ohne Rueckfrage). Die dritte Form war die
        # haeufigste der Nacht (search_tools/check_tools/load_tool_group).
        gesperrt = ("no such tool available" in low
                    or "disabled for this session" in low
                    or "requires approval" in low
                    or "permission for this tool use was denied" in low)
        if text.lstrip().startswith("<tool_use_error>"):
            return "gesperrt" if gesperrt else "fehler"
        if block.get("is_error"):
            return "gesperrt" if gesperrt else "fehler"
        return None

    # --------------------------------------------------------------- Auswertung
    def output_total(self) -> int:
        """Ausgabe-Tokens: Summe je Nachricht, sonst aus dem result-Ereignis.

        Gemessen an B159 (DeepSeek ueber den Anthropic-Endpunkt): die Nutzung der
        assistant-Ereignisse traegt Eingabe und Cache EXAKT, aber KEINE Ausgabe
        (alle 0). Die richtige Gesamtzahl steht im result-Ereignis; sie wird
        genommen, sobald sie groesser ist als die Summe - und die Abweichung
        wird gemeldet, nicht verschwiegen.
        """
        summe = sum(int(r.get("output") or 0) for r in self.requests)
        return max(summe, self.result_usage()["output"])

    def totals(self) -> dict:
        miss = sum(r["miss"] for r in self.requests)
        hit = sum(r["hit"] for r in self.requests)
        creation = sum(r["creation"] for r in self.requests)
        return {"requests": len(self.requests), "input_miss": miss, "cache_read": hit,
                "cache_creation": creation, "output": self.output_total()}

    # ------------------------------------------------- Kontext (Auftrag 2026-09-29)
    @staticmethod
    def kontext_summe(eintrag: dict) -> int:
        """Kontextgroesse EINER Anfrage: input + cache_read + cache_creation."""
        return (int(eintrag.get("miss") or 0) + int(eintrag.get("hit") or 0)
                + int(eintrag.get("creation") or 0))

    def kontext_werte(self) -> list[int]:
        return [self.kontext_summe(r) for r in self.requests]

    def kompaktierungen(self) -> list[list[int]]:
        """Hinweise auf eine Kontext-Kompaktierung: `[[Anfrage-Nr, vorher, nachher], …]`.

        Zwei Quellen: ein ausdrueckliches `compact_boundary`-Ereignis (in B205-B212 nie
        gesehen) und ein sprunghafter Rueckgang der Kontextsumme zwischen zwei Anfragen
        (mindestens `KOMPAKT_RUECKGANG_MIN` Tokens UND mindestens
        `KOMPAKT_RUECKGANG_ANTEIL` des Vorwerts).
        """
        werte = self.kontext_werte()
        out: list[list[int]] = []
        gesehen: set[int] = set()
        for idx in self.kompakt_marker:
            i = int(idx)
            vor = werte[i - 1] if 0 < i <= len(werte) else (werte[-1] if werte else 0)
            nach = werte[i] if 0 <= i < len(werte) else vor
            out.append([i, vor, nach])
            gesehen.add(i)
        for i in range(1, len(werte)):
            if i in gesehen:
                continue
            vor, nach = werte[i - 1], werte[i]
            if (vor - nach >= KOMPAKT_RUECKGANG_MIN
                    and nach <= vor * (1.0 - KOMPAKT_RUECKGANG_ANTEIL)):
                out.append([i, vor, nach])
        out.sort()
        return out

    def kontext_stats(self, schritt: int = KONTEXT_VERLAUF_SCHRITT) -> dict:
        """Kontextmessung fuer `result.json` (Auftrag 2026-09-29).

        `kontext_letzte_anfrage` = Summe der LETZTEN Anfrage, `kontext_max` = Maximum
        ueber alle, `kontext_verlauf` = dieselbe Summe alle `schritt` Anfragen (kompakt;
        die LETZTE Anfrage steht immer mit dabei), `kompaktierungen` = erkannte
        Kompaktierungen.
        """
        werte = self.kontext_werte()
        n = max(1, int(schritt))
        idx = list(range(0, len(werte), n))
        if werte and idx[-1] != len(werte) - 1:
            idx.append(len(werte) - 1)
        return {"kontext_letzte_anfrage": (werte[-1] if werte else 0),
                "kontext_max": (max(werte) if werte else 0),
                "kontext_verlauf": [werte[i] for i in idx],
                "kompaktierungen": self.kompaktierungen()}

    def summe_feld(self, key: str) -> float:
        """Summe eines Zahlenfelds ueber ALLE `result`-Ereignisse (0.0 ohne Treffer)."""
        return sum(float(ev.get(key)) for ev in self._result_liste()
                   if isinstance(ev.get(key), (int, float)))

    def letzte_antwort_ohne_werkzeug(self) -> bool | None:
        """Trug die LETZTE Antwort des Modells keinen Werkzeugaufruf? (None = keine)"""
        if not self.letzte_msg_id:
            return None
        return not bool(self._msg_werkzeug.get(self.letzte_msg_id))

    def werkzeug_enthaelt(self, *worte: str) -> bool:
        """Kam in den Argumenten IRGENDEINES Werkzeugaufrufs jedes dieser Worte vor?

        Gebraucht fuer die Fortsetzungs-Bedingung (Punkt 4): "schon Preflight und Bilanz
        gemacht?" - geprueft wird der Werkzeugaufruf (Aufrufweg), nicht der Fliesstext.
        """
        for t in self.tools:
            try:
                roh = json.dumps(t.get("input") or {}, ensure_ascii=False)
            except (TypeError, ValueError):
                roh = str(t.get("input"))
            klein = roh.lower()
            if all(w.lower() in klein for w in worte):
                return True
        return False

    def cost_usd(self, extra_offpeak_dates: list[str] | None = None) -> float:
        """Kosten nach dem Tarif JEDES Aufrufs (Fenster darf mitten im Batch wechseln).

        Fehlt die Ausgabe in den Ereignissen, wird die Gesamtausgabe gleichmaessig
        auf die Aufrufe verteilt - so bleibt der Tarif je Aufruf wirksam.
        """
        summe_out = sum(int(r.get("output") or 0) for r in self.requests)
        gesamt_out = self.output_total()
        anteil = 0.0
        if gesamt_out > summe_out and self.requests:
            anteil = gesamt_out / len(self.requests)
        total = 0.0
        for r in self.requests:
            dt = None
            ts = r.get("ts") or ""
            if ts:
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
                except ValueError:
                    dt = None
            out = int(r["output"]) if gesamt_out <= summe_out else anteil
            total += pricing.cost_usd(r["miss"], r["hit"], r["creation"], out,
                                      dt, extra_offpeak_dates)
        return round(total, 6)

    def cost_naive_usd(self, extra_offpeak_dates: list[str] | None = None) -> float:
        """Gegenprobe: alles zum JETZIGEN Tarif (fuer die Messdifferenz)."""
        t = self.totals()
        return round(pricing.cost_usd(t["input_miss"], t["cache_read"], t["cache_creation"],
                                      t["output"], None, extra_offpeak_dates), 6)

    # ------------------------------------------------- Nutzung: Gegenprobe
    def _result_liste(self) -> list[dict]:
        """Alle `result`-Ereignisse (Fortsetzungen im selben Chat tragen mehrere)."""
        if self.result_ereignisse:
            return list(self.result_ereignisse)
        return [self.result] if isinstance(self.result, dict) else []

    def result_usage(self) -> dict:
        """Nutzung aus den `result`-Ereignissen (Gesamtlauf laut Claude Code).

        Auftrag 2026-09-29: bei einer Fortsetzung liegen MEHRERE result-Ereignisse im
        Mitschnitt - die Gesamtwerte sind dann ihre Summe (sonst zaehlte nur der letzte
        Teillauf und die Gegenprobe `usage_check` schluege falsch Alarm).
        """
        summe = {"input_miss": 0, "cache_read": 0, "cache_creation": 0, "output": 0}
        for ev in self._result_liste():
            u = (ev or {}).get("usage") or {}
            summe["input_miss"] += int(u.get("input_tokens") or 0)
            summe["cache_read"] += int(u.get("cache_read_input_tokens") or 0)
            summe["cache_creation"] += int(u.get("cache_creation_input_tokens") or 0)
            summe["output"] += int(u.get("output_tokens") or 0)
        return summe

    def usage_check(self, tolerance: float = 0.01) -> dict:
        """Summe je Nachricht gegen das result-Ereignis stellen (R11-2).

        Stimmt beides ueberein, ist die Zaehlung belegt. Weicht es ab, wird das
        GEMELDET - nicht stillschweigend eine der beiden Zahlen benutzt.
        """
        summe = self.totals()
        res = self.result_usage()
        if not any(res.values()):
            return {"ok": None, "hinweis": "kein result-Ereignis mit usage"}
        diff = {k: int(summe[k]) - int(res[k]) for k in res}
        summe_ereignisse = sum(int(r.get("output") or 0) for r in self.requests)
        ok = all(abs(d) <= max(2, int(tolerance * max(1, abs(res[k])))) for k, d in diff.items())
        return {"ok": bool(ok),
                "summe": {k: int(summe[k]) for k in res},
                "result": res, "diff": diff,
                "quelle_output": "ereignisse" if summe_ereignisse >= res["output"] else "result"}

    def final_text(self) -> str:
        if self.result and isinstance(self.result.get("result"), str) and self.result["result"].strip():
            return self.result["result"]
        return "\n\n".join(self.texts).strip()

    def is_error(self) -> bool:
        return bool(self.result and self.result.get("is_error"))

    def terminal_reason(self) -> str | None:
        return (self.result or {}).get("terminal_reason")

    def num_turns(self) -> int | None:
        werte = [int(ev.get("num_turns")) for ev in self._result_liste()
                 if isinstance(ev.get("num_turns"), int)]
        return sum(werte) if werte else None

    def letzter_aufruf(self) -> str:
        """Der zuletzt BEGONNENE Werkzeugaufruf als kurze Zeile ('' = keiner). (R13bq)

        Fuer die Stillstands-Warnung (`proc.run_stream` -> `stille_info`): sie soll sagen,
        WORAUF gewartet wird, nicht nur dass gewartet wird.
        """
        if not self.tools:
            return ""
        t = self.tools[-1]
        return f"{t.get('name')}: {kurz_input(t.get('input') or {})}"[:200]

    def runden(self) -> int:
        """Werkzeugrunden: Modellantworten MIT Werkzeugaufruf (R13ar).

        Das ist die Zahl, gegen die die CLI ihr `--max-turns` prueft (gemessen,
        `docs/_r13ar_limit_probe_reviewer.txt`), NICHT `num_turns` aus dem
        Ergebnis-Ereignis (Werkzeugergebnisse + 1).
        """
        return len(self._runden_ids) + int(self.runden_ohne_id or 0)

    def total_cost_usd_field(self) -> float | None:
        werte = [float(ev.get("total_cost_usd")) for ev in self._result_liste()
                 if isinstance(ev.get("total_cost_usd"), (int, float))]
        return round(sum(werte), 6) if werte else None

    def duration_field(self) -> tuple[float | None, str]:
        """Die vom Worker-Prozess SELBST gemeldete Laufzeit + ihre Herkunft (R13c).

        `duration_ms` ist die Wanduhr-Zeit des `claude`-Prozesses, `duration_api_ms`
        nur die darin verbrachte API-Zeit. Fuer die Bilanz ist die Wanduhr massgeblich:
        B159 stand mit `duration_api_ms` (288 s) in der Bilanz, waehrend der Prozess
        377 s lief - der Unterschied ist Ausfuehrungszeit im Kind (Werkzeuge, Rueckstau).

        Auftrag 2026-09-29: bei Fortsetzungen werden die Teillaufzeiten SUMMIERT.
        """
        summe = {"duration_ms": 0.0, "duration_api_ms": 0.0}
        for ev in self._result_liste():
            for key in summe:
                v = (ev or {}).get(key)
                if isinstance(v, (int, float)) and v > 0:
                    summe[key] += float(v)
        for key in ("duration_ms", "duration_api_ms"):
            if summe[key] > 0:
                return round(summe[key] / 1000.0, 3), key
        return None, ""

    def tool_table(self) -> list[tuple[str, int]]:
        return sorted(self.tool_counts.items(), key=lambda kv: (-kv[1], kv[0]))

    def repeated_calls(self) -> list[tuple[str, int]]:
        """Identische Aufrufe (Name + Argumente) - Signal fuer den Watchdog (Spaeter)."""
        seen: dict[str, int] = {}
        for t in self.tools:
            key = t["name"] + "|" + json.dumps(t["input"], sort_keys=True, ensure_ascii=False)
            seen[key] = seen.get(key, 0) + 1
        return sorted(((k, v) for k, v in seen.items() if v > 1), key=lambda kv: -kv[1])
