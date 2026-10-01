# R13bg — Rechnerlast B228–B234 (nur lesend, Auftrag 2026-10-01)

Quelle: `runs/b228…b234/result.json` (Felder `cpu_mittel`, `cpu_max`, `ram_frei_min`,
`fremdlast_minuten`, `last_proben`), erhoben von `hx/last.py` (`Recorder`, Takt 60 s,
psutil). Rohbeleg: `docs/_r13bg_last.txt` (Werkzeug `docs/_r13bg_last.py`).

Maschine (2026-10-01 ~14:35 gelesen, `Win32_Processor`/`Win32_OperatingSystem`/
`Win32_PageFileUsage`): **Intel Core i7-930 @ 2.80 GHz, 4 Kerne / 8 Threads,
6135 MB RAM**, Auslagerungsdatei 7473 MB (Spitze **3483 MB**, aktuell 1008 MB,
82 % RAM belegt **ohne** laufenden Batch).

## Kennzahlen je Batch

| Batch | Proben | cpu_mittel % | cpu_max % | RAM frei min MB | fremdlast | fremd_max | ghidra_max |
|---|---|---|---|---|---|---|---|
| 228 | 84 | 12,7 | 23,4 | 1200 | 84/84 | 1 | 1 |
| 229 | 78 | 23,3 | **87,2** | 462 | 78/78 | 4 | 1 |
| 230 | 107 | 15,8 | 69,1 | 789 | 107/107 | 2 | 1 |
| 231 | 73 | 12,1 | 43,2 | **373** | 73/73 | 1 | 1 |
| 232 | 59 | 12,7 | 27,7 | **2475** | 59/59 | 1 | 1 |
| 233 | 106 | 14,4 | 51,2 | 385 | 106/106 | 1 | 1 |
| 234 | 125 | 13,4 | 28,4 | 1094 | 125/125 | 2 | 1 |

`last_proben` ≈ Batchminuten (Takt 60 s); `fremdlast_minuten` = **jede** Minute, weil in
jeder Minute ein fremder `python.exe` lief (`last_fremde_namen` = nur `python.exe`) — das
ist die stehende Infrastruktur (MCP-Bridge/`watch`), **kein** echter Fremdlauf.

## Die Minutenfrage — was `result.json` hergibt und was nicht

**Nicht hergebbar:** die Zahl der Minuten unter/über einer Schwelle. `result.json` trägt nur
**Kennzahlen** (Mittel, Spitze, Minimum); die Minutenreihe selbst (`hx/last.py:Recorder.proben`)
lebt **nur im Speicher** des Harness und wird nicht abgelegt. Ableitbar sind **Schranken**:

| Batch | RAM < 500 MB | RAM < 200 MB | CPU > 90 % |
|---|---|---|---|
| 228 | 0 min (Minimum 1200 ≥ 500) | 0 min | 0 min |
| 229 | **1 … 78 min** (Minimum 462) | 0 min | 0 min |
| 230 | 0 min (789) | 0 min | 0 min |
| 231 | **1 … 73 min** (373) | 0 min | 0 min |
| 232 | 0 min (2475) | 0 min | 0 min |
| 233 | **1 … 106 min** (385) | 0 min | 0 min |
| 234 | 0 min (1094) | 0 min | 0 min |

* „0 min" ist **bewiesen** (das Minimum lag über der Schwelle).
* „1 … N min" heisst: mindestens die eine Minute mit dem Tiefstwert, höchstens alle.
* **CPU > 90 %: in keinem der sieben Batches** (höchste Spitze 87,2 % in B229).

## Welche Minuten belegt waren (aus den Werkzeug-Zeitstempeln, nicht aus der Lastmessung)

| Batch | Wanduhr | Preflight | hybrid_lauf | Bau |
|---|---|---|---|---|
| 228 | 87 m | 62…85 (16 min) | 0…0 (1 min) | 0…61 (11 min) |
| 229 | 80 m | 54…78 (16 min) | **1…54 (46 min)** | 0…14 (6 min) |
| 230 | 110 m | 70…108 (37 min) | 0…61 (37 min) | 0…43 (15 min) |
| 231 | 74 m | 52…73 (20 min) | **3…40 (33 min)** | 0…0 (1 min) |
| 232 | 60 m | 37…59 (20 min) | — | 0…17 (7 min) |
| 233 | 110 m | 61…108 (31 min) | **1…67 (56 min)** | 0…13 (13 min) |
| 234 | 129 m | 92…119 (28 min) | 0…92 (54 min) | 0…128 (12 min) |

(Tool-Aufrufe mit `hybrid_lauf`/`port_build`/`mingw32-make`/`g++` bzw.
`streamjson.ist_preflight_aufruf`; der abgebrochene Vorgängerlauf `stream-v1.jsonl` von B234
ist **nicht** mitgezählt. Ein kurzer Treffer kann auch nur eine Prozessabfrage sein.)

**Zusammenhang (STRONG INFERENCE, kein Beweis):** Genau die drei Batches mit RAM-Tiefstwert
unter 500 MB (B229 462, B231 373, B233 385) haben die längsten `hybrid_lauf`-Phasen
(46/33/56 min); der einzige Batch **ohne** jeden `hybrid_lauf` (B232) hat mit 2475 MB den
höchsten Wert. Gegenbeispiel in den eigenen Zahlen: B234 (54 min `hybrid_lauf`) blieb bei
1094 MB. Die exakte Minute des Tiefstwerts ist aus `result.json` **nicht** bestimmbar.

## Einschätzung: Engpass Speicher oder CPU?

**Rechenleistung ist NICHT der Engpass.** Mittel 12–23 %, Spitze 87 % in einer einzigen
Minute, **nie über 90 %** — auf 8 Threads sind das im Mittel ~1–2 beschäftigte Threads. Die
Arbeit ist seriell (ein `hybrid_lauf`, ein `claude.exe`, ein Ghidra); mehr Kerne würden die
Batchzeit kaum bewegen.

**Der Speicher ist die knappe Ressource.** 6135 MB gesamt; in 3 von 7 Batches fiel der freie
RAM unter 500 MB (tiefster Wert 373 MB = 6 % frei). Unter 200 MB ging er nie — es kam also
**nicht** zum harten Auslagern im Batch —, aber die Reserve ist dünn, und die Auslagerungsdatei
hat eine **Spitze von 3483 MB** (Zeitpunkt nicht je Batch erfasst: irgendwann wurde real
ausgelagert). Auch **ohne** laufenden Batch sind 82 % des RAM belegt (VS Code ~2,5 GB über
fünf Prozesse, `MemCompression` 252 MB — Windows komprimiert bereits). Ghidra läuft mit
`-Xmx2g` in **jedem** Batch mit (`last_ghidra_max` = 1).

Wenn es eng wird, trifft es genau die langen seriellen Schritte (Preflight, Bau, `hybrid_lauf`),
weil ein ausgelagerter Speicherseiten-Fehler den wartenden Thread blockiert — deshalb ist
„eher Speicher" die richtige Antwort, obwohl im Messfenster **keiner** der beiden Werte
gesättigt war.

**Ansatzpunkte (nur benannt, nichts geändert):** VS Code während eines Batches schließen
(≈2,5 GB = mehr als das Doppelte der heutigen Reserve), die volle Testreihe nicht parallel zu
einem Batch fahren (R13au-Regel; jeder Testlauf bringt weitere `python.exe` und RAM), und für
künftige Messungen die Minutenreihe ablegen (`hx/last.py` schreibt heute nur die Kennzahlen —
ein `runs/b<N>/last.jsonl` würde die Minutenfrage exakt beantworten).
