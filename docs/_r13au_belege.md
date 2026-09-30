# R13au-Belege (2026-09-30): Rechnerlast mitschreiben (Auftrag Teil C)

Auftrag: (1) Arbeitsregel in `bedienung.md` — während eines Batches nur die betroffenen
Testdateien, volle Reihe nur am Gate oder bei gestopptem Harness. (2) Während des Batches
jede Minute CPU gesamt, freier RAM und die Zahl der `python`-/`java`-Prozesse, die nicht
zum Worker gehören. (3) In `result.json`: `cpu_mittel`, `cpu_max`, `ram_frei_min`,
`fremdlast_minuten`, dazu eine Zeile in den Review-Fakten. (4) Bericht: Kerne und RAM des
Rechners, typischer RAM-Bedarf von Ghidra/Java und des Workers.

| Datei | Was |
|---|---|
| `harness/hx/last.py` | der Recorder (Minutentakt, drei Prozessgruppen, Windows-Rückfall) |
| `docs/_r13au_belege.txt` (erzeugt von `docs/_r13au_belege.py`) | Maschine, laufende Prozesse, Summen, eine echte Aufnahme |
| `harness/tests/test_r13au_fixes.py` | 17 Tests (Gruppen, Auswertung, Faktenzeile, Verdrahtung) |

## 1. Die Arbeitsregel (Auftrag 1)

Sie steht in `docs/bedienung.md` §12u (und als Merksatz in der Einleitung) und lautet:

> Während ein Batch läuft, werden nur die direkt betroffenen Testdateien gefahren. Die
> volle Reihe läuft nur, wenn der Harness am Gate steht oder gestoppt ist; der Zustand
> wird vorher aus `state/run.json` abgelesen und genannt (`state`, `batch`, `worker`).

Grund sind die Zahlen aus §2: der Rechner hat 6 GB RAM, und im Messlauf waren **84 %
belegt (986 MB frei)**, während Ghidra, der Worker, die Bridge, `watch` und VS Code liefen.

## 2. Der Rechner (Auftrag 4, gemessen)

| Größe | Wert | Quelle |
|---|---|---|
| CPU | Intel Core i7-930, **4 Kerne / 8 Threads** @ 2,80 GHz | `Win32_Processor` (2026-09-30) |
| RAM | **6135 MB** gesamt | `psutil.virtual_memory()` |
| Belegung im Messlauf | 84 %, frei 986 MB | ebd. |
| Ghidra-Heap | **`-Xmx2g`** (2 GB Obergrenze) | `g:/Silent Scope Decomp/scripts/start-ghidra-headless.ps1:100` |
| Größter Einzelposten | VS Code, drei `Code.exe` mit zusammen ~2,2 GB | `docs/_r13au_belege.txt` §2b |

RAM-Bedarf der Beteiligten (RSS, Messung mit laufendem Batch B219):

| Prozess | RSS | Anmerkung |
|---|---|---|
| `claude.exe` (der Worker, Node) | **211 MB** | `-p --output-format stream-json …` |
| Ghidra (Java, `-Dghidra.home=…`) | 25 MB | + bis 2 GB Heap-Grenze; die Zahl ist der Stand *dieses* Moments |
| `python`: Harness, `watch`, Bridge, VS-Code-Helfer, `c_kopf.py` | 288 MB über 8 Prozesse | davon dauerhaft: `watch` 26 MB, Harness 26 MB, Bridge 3 MB |
| `node`/`claude` zusammen | 211 MB | ein Prozess |
| übrige 225 Prozesse (VS Code, Windows) | 4987 MB | Systemlast, nicht Projekt |

## 3. Was gemessen wird (Auftrag 2 und 3)

`hx/last.py`, gestartet in `worker.run_batch` **vor** dem Kindprozess und beendet im
`finally` (dort auch `res.last = last_recorder.werte()`), Takt **60 s** (`INTERVALL_S`,
Vorgabe aus dem Auftrag „jede Minute"); die **erste** Aufnahme kommt sofort, damit auch ein
kurzer Batch eine Zahl hat.

Je Aufnahme:

* **CPU gesamt** in % — `psutil.cpu_percent(interval=1.0)`. GEMESSEN: mit
  `cpu_percent(None)` direkt nach dem Start kam **0.0 %** heraus (Intervall null, der
  Wert war wertlos); mit einem echten Messfenster von einer Sekunde ist es die Auslastung
  *jetzt*. Der Aufruf läuft im eigenen Faden und stört den Batch nicht.
* **freier RAM** in MB — `psutil.virtual_memory().available`.
* **Prozesse** in drei Gruppen (Definition im Modul-Docstring):
  * **eigene** — der Harness-Baum (`os.getpid()` + Nachfahren über `ppid`); der Worker ist
    ein Kind des Harness, Fortsetzungen ebenso,
  * **ghidra** — Java mit `ghidra`/`GhidraMCP`/`-Dghidra.home` in der Kommandozeile,
  * **fremd** — alle übrigen `python`/`java`. **Nur diese** erzeugen
    `fremdlast_minuten` (= Zahl der Minuten mit mindestens einem fremden Prozess).

In `runs/b<N>/result.json`: `cpu_mittel`, `cpu_max`, `ram_frei_min`, `fremdlast_minuten`
(so heißen die Felder im Auftrag) plus `last_proben`, `last_fremd_max`,
`last_fremde_namen`, `last_ghidra_max`, `last_eigene_max`, `last_quelle`, `last_fehler`.
In den Review-Fakten eine Zeile:

```
- RECHNERLAST: CPU 31.2 % (Spitze 68.0 %), RAM frei min 4210 MB, FREMDLAST in 3 von
  47 Minuten (bis 9 Prozesse: python.exe), Ghidra lief mit (1 Java-Prozess)
```

Ohne Messung (z. B. ein nachgerechneter Lauf) steht dort ausdrücklich
`RECHNERLAST: nicht gemessen (<Grund>)` — nie eine erfundene Zahl, nie ein stilles Feld.

**Die Fremdlast ist ein Grundrauschen.** Im Messlauf waren 7 `python`-Prozesse außerhalb
des Harness-Baums dauerhaft da (`watch`, Harness in zweitem Fenster, Bridge, VS-Code-Helfer,
`c_kopf.py`). Weil die Definition im Auftrag wörtlich „die nicht zum Worker gehören" ist,
zählt das alles als fremd — deshalb nennt die Zeile die **Spitze** („bis N Prozesse") und
die Namen. Eine Zahl von 0 ist auf diesem Rechner nicht zu erwarten.

## 4. Rückfall ohne `psutil`

`psutil` ist hier vorhanden (5.9.8) und wird benutzt. Fehlt es, messen die Windows-Zähler
über `ctypes` — `GetSystemTimes` (CPU-Differenz idle/gesamt) und `GlobalMemoryStatusEx`
(`ullAvailPhys`); die Prozessliste kommt dann nur über `tasklist` **nach Namen**, ohne
Baumzugehörigkeit, und `last_quelle` steht als `windows` in den Messdaten. Ist auch das
nicht möglich, steht `keine` und die Zeile sagt „nicht gemessen".

## 5. Tests

`harness/tests/test_r13au_fixes.py` — **17 Tests**: die drei Prozessgruppen mit einem
gefälschten `psutil` (eigene / Ghidra / fremd / kein `python`), CPU- und RAM-Werte aus der
Quelle, ein Fehler der Quelle ergibt **keine** Zahl, Mittel/Spitze/Minimum und die
Fremdminuten (auch mit Lücken in der Aufnahme — eine fehlende CPU-Zahl zählt nicht als 0),
die Wortlaute der Faktenzeile (mit Fremdlast, ohne, nicht gemessen), die Feldnamen in
`result.json`, `maschine()`, eine echte Aufnahme (CPU zwischen 0 und 100, eigener Prozess
zählt als eigen), `start()` doppelt startet keinen zweiten Faden, `_finish_run` schreibt
die vier Zahlen, `harness-facts.md` zeigt die Zeile, und `worker.run_batch` startet und
beendet den Recorder.

## 6. Offen

* Der laufende Harness (B219) hat die Messung noch nicht — sie wirkt ab dem nächsten Start.
* Der erste Batch nach dem Start liefert die Zahlen; ältere Batches haben sie nicht
  (die Zeile sagt dann „nicht gemessen").
* Die Ghidra-Java-RSS-Zahl schwankt mit dem Heap-Verbrauch; der Messwert hier ist eine
  Momentaufnahme, keine Obergrenze (die steht als `-Xmx2g` im Startskript).
