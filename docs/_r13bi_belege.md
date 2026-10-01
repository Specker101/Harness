# R13bi — Hybrid-Lauf als eigene Bahn: braucht er `c_kopf_check`? (nur gelesen, 2026-10-01)

Auftrag (Wortlaut): Nachfrage zu R13bh, **nur lesen**. 1. Braucht der Hybrid-Lauf-Teil
von `m212_zeilen` irgendetwas aus `c_kopf_check` (Cache, Dateien, Binary)? 2. Wenn nein:
Wie liesse sich der Hybrid-Lauf als eigene Pruefgruppe herausloesen und parallel zu
`c_kopf_check` fahren (nie zwei `hybrid_lauf.exe`)? Erwartete Gesamtzeit, RAM-Bedarf
beider Laeufe zusammen. 3. Falls das traegt: den `/ds`-Vorschlag umschreiben.

Alle Zeilenangaben gelten fuer **Decomp-Repo `7ec9d6a`** (Form `Datei:Zeile@7ec9d6a`,
Projektregel B215). Harness-Belege: `docs/_r13bi_ram.txt`, `docs/_r13bi_ram2.txt`
(Messwerkzeuge `docs/_r13bi_ram.py`, `docs/_r13bi_ram2.py`).

## 1. Frage 1 — NEIN, der Hybrid-Lauf braucht nichts aus `c_kopf_check`

Der Hybrid-Teil besteht aus `_lauf`, `_kurz`, `_neben`, `_anteil`, `_funktionen`,
`_hybrid`, `_NEBEN` und `check_hybrid`. Was er benutzt:

| Was | Stelle | Was er liest/schreibt |
|---|---|---|
| `port/build/hybrid_lauf.exe` | `scripts/m212_zeilen.py:86@7ec9d6a` (`LAUF_EXE`), Existenzpruefung `:387`, `subprocess.run(argv, cwd=WS, capture_output=True, text=True, encoding="utf-8")` `:255-261` | **nur die Rohausgabe des Binaers** (kein Datei-Eingang, keine Belegdatei, kein Cache) |
| Argv des FRONT-Laufs | `:250-268` (`--schritte 200000000 --nativ-weiter`, `LAUF_FRONT` `:230`, `NATIV_WEITER` `:243`) | – |
| Argv des 20M-Laufs | `_lauf(None)` `:463` | – |
| `_hybrid()` | `:373-465` | parst Text (`_kurz` `:270-283`, `_neben` `:286-305`, `_anteil`, `_funktionen`), fuellt `_NEBEN` (`:417-463`), schreibt `analysis/<EV>/_hybrid.txt` (ueber `_schreib` `:91`, Aufruf `:464`) |
| `check_hybrid` | `:592-640` | liest **nur** `_NEBEN` (`:608-634`), das `_hybrid()` selbst gefuellt hat |
| Rotproben-Schalter | `FRONT_TXT_UEBER` `:481` (Vorgabe `None`), benutzt `:389` | – |

**Kein `c_kopf`-Bezug im Hybrid-Pfad.** Die `c_kopf`-Benutzungen des Moduls liegen
alle in den anderen Zeilen: `_fallrueckgang` (`:134`, `:194`), `check_verifiziert`
(`:520` -> `m210_bahnabdeckung.lauf()` -> `c_kopf._DECKUNG_CACHE`, `c_kopf.py:2586`
`deckung` / `:2612` `_vergl_alle`), `check_formen` (`:544`), `check_profile_repro`
(`:706`). Der Hybrid-Pfad liest **keine** Belegdatei eines anderen Moduls.

Die Abhaengigkeit laeuft sogar in die **Gegenrichtung**: `c_kopf_check` importiert
`m212_zeilen` fuer die Zahl der "ausgeduennten" Koepfe (`scripts/c_kopf_check.py:88`),
und zwar `m212_zeilen._fallrueckgang` - **nicht** den Hybrid-Teil.

Was das Binaer selbst anfasst (alles lesend, `port/hybrid/hybrid_lauf.cpp:75/331/334/335`):
ROM `rom/build/830d01.27p.main.bin`, Coverage `capture/ppc_cov_boot.bin`,
`analysis/_rumpfspannen.txt`, `analysis/_m225/_funktionen.txt`,
`analysis/_m225/_koepfe.txt`. Geschrieben wird **nur** mit `--s-log`
(`hybrid_lauf.cpp:605-608`), und dieser Schalter wird im Preflight nicht gesetzt.
`port/build/c_kopf.exe` schreibt ebenfalls **keine** Datei: die beiden `fopen` im
Treiber sind `"rb"`/`"r"` (`port/src/c_kopf_drv.cpp:103/129`), alles andere ist
`std::printf`/`std::fprintf` (`:120-252`).

**Ergebnis Frage 1: der Hybrid-Lauf braucht nichts aus `c_kopf_check`** - kein Cache,
keine Belegdatei, kein Binaer, keinen Prozesszustand. Die Trennung ist rein
dateiseitig sauber (verschiedene Schreibziele) **und** prozessseitig sauber (kein
gemeinsamer Speicher).

## 2. Frage 2 — Herausloesen und parallel fahren: traegt, mit vier Bahnen

### 2a Was herausgeloest wird

Neues Modul `scripts/m212_hybrid.py` mit `VERDICTS` = die sechs heutigen Zeilen
(`Hybrid-Lauf`, `Hybrid-Lauf 20M`, `Hybrid-SPU`, `Hybrid-Attrappe4`,
`Hybrid-Anteil nativ`, `Hybrid-Funktionen nativ`) und den Teilen `_lauf`, `_kurz`,
`_neben`, `_anteil`, `_funktionen`, `_hybrid`, `_NEBEN`, `check_hybrid` sowie den
Konstanten (`LAUF_FRONT`, `KOPF_EINSTIEG`, `NATIV_WEITER`, `OHNE_REGISTRY`,
`FRONT_TXT_UEBER`). In `m212_zeilen.py` bleiben `C verifiziert`, `Formen der
C-Koepfe orakelgeprueft`, `C Fallrueckgang`, `analysis neue .py`,
`Profile reproduzierbar`, `Bauliste subset Registry` - und **`_fallrueckgang`
muss dort bleiben** (`c_kopf_check.py:88` ruft es).

Die **zwei** `hybrid_lauf.exe`-Laeufe bleiben **seriell im selben Prozess**
(`_hybrid()` ruft `_lauf(LAUF_FRONT)` und danach `_lauf(None)`, `:387-390`) -
die Auflage "nie zwei `hybrid_lauf.exe`" ist damit erfuellt, ohne dass der
Bahn-Planer davon wissen muss.

### 2b Bahnen muessen PROZESSE sein, nicht Threads

`verdict.capture` (`scripts/verdict.py:78`) leitet `sys.stdout` **prozessweit** um
(`contextlib.redirect_stdout`), und diesen Weg benutzen die meisten Gruppen:
`c_kopf_check.py:67`, `m104_built.py:2497`, `m114_pass.py:549`, `m115_pass.py:341`,
`m116_pass.py:541`, `m130_ast.py:852`, `m200_einbindung.py:385`,
`port_regression.py:4042`. Zwei Bahnen als **Threads** im selben Prozess wuerden sich
gegenseitig die Rohausgabe in den jeweils anderen Puffer schreiben - das waere ein
stiller Belegfehler. Also: **eine Bahn = ein Prozess** (eigener `sys.stdout`).
Das passt zum Bestand: der Belegpfad kommt schon heute aus der Umgebung
(`evidence.py:98` `_OUT_DIR = _strip_argv() or os.environ.get("EV_OUT", "")`).

### 2c Zeilenreihenfolge bleibt gleich (der Elternteil druckt)

`preflight.py:305-308` druckt die eingesammelten Zeilen in Sammelreihenfolge. Da jede
Bahn ihre Zeilen als **Text** an den Elternteil gibt, druckt der Elternteil sie in der
festgelegten Reihenfolge (`ZEILEN_ORDNUNG`) - dann ist die Ausgabe **zeilengleich** zur
heutigen, obwohl die sechs `Hybrid-*`-Zeilen aus einem anderen Prozess kommen. Eine
Zeile, die in keiner Liste steht, wird angehaengt und als FEHLER gemeldet (kein stiller
Verlust). Mitzusammeln sind: die Zeittafel (`zeiten_schreiben` `:208`), der
Archivbericht (`saved = EV.archived()` `:283`, `EV.report(saved)` `:310`) und der eine
geteilte Schreibvorgang `analysis/_archiv/MANIFEST.txt` (Append, `evidence.py:141`).
Die 5 %-Gegenprobe (`:217-220`) gilt fuer parallele Bahnen nicht mehr (Summe der
Teilschritte > Gesamtuhr) - neue Form: **je Bahn** `Summe Teilschritte <= Bahn-Uhr + 5 %`.

### 2d Erwartete Gesamtzeit (gerechnet aus `_m230..234/_preflight_zeiten.txt`)

| Batch | heute seriell | A1 (Kette ohne Hybrid) | A2 (Hybrid) | B (Bau) | C (Rest) | neu = max(A1, A2, B+C) | Ersparnis |
|---|---|---|---|---|---|---|---|
| 230 | 524,9 | 327,1 | **150,8** | 34,1 | 12,8 | **327,1** | -197,8 (-37,7 %) |
| 231 | 533,5 | 313,8 | 165,3 | 33,8 | 20,6 | **313,8** | -219,7 (-41,2 %) |
| 232 | 547,6 | 328,2 | 164,6 | 34,1 | 20,6 | **328,2** | -219,4 (-40,1 %) |
| 233 | 549,3 | 326,9 | 166,9 | 34,7 | 20,9 | **326,9** | -222,4 (-40,5 %) |
| 234 | 1578,5 | 340,6 | **1181,3** | 34,5 | 21,9 | **1181,3** | -397,2 (-25,2 %) |
| Ø | 746,7 | 327,3 | 365,8 | 34,2 | 19,4 | **495,5** | -251,2 (-33,6 %) |

A1 = `m227_profile_live` + `c_kopf_check` + `m210_bahnabdeckung` + alle
`m212_zeilen`-Teilschritte **ohne** `Hybrid-Lauf` (Mittel 17,0 s: Formen 8,2 +
Fallrueckgang 8,1 + verifiziert 0,1 + analysis .py 0,2 + Profile 0,0 + Bauliste 0,4).
B = `m116_pass` + `m5_kopf_check` + `port_regression` (+ `m233_binary` am Ende).
C = `m104_built` + `m115_pass` + `m114_pass` + `m130_ast` + `m200_einbindung` +
`m210_r391` + `m214_archiv`.

**Regelfall: 327 s statt 525 s (-38 %); B234: 1181 s statt 1579 s (-25 %).**
Die drei kurzen Bahnen verstecken sich vollstaendig hinter A1 - die kritische Bahn ist
im Regelfall A1, in B234 die Hybrid-Bahn A2.

**WIDERLEGT (Messung, s. 2e):** die Spalte `neu = max(...)` gilt **nicht**. Sie
unterstellt, dass sich A1 und A2 nicht gegenseitig bremsen. Genau das ist gemessen
**falsch**: waehrend des FRONT-Laufs brauchte eine `c_kopf.exe`-Kopfrunde das
**Dreißig- bis Siebzigfache** (28 s je Kopf statt 0,4-2,7 s). Die Bahnsummen
A1/A2/B/C selbst bleiben gueltig (je Bahn allein gemessen); die Gesamtzeiten dieser
Zeile sind **zurueckgezogen**.

**Was von der Rechnung bleibt:** die Zerlegung (A1 327,3 s, A2 365,8 s Ø, B 34,2 s,
C 19,4 s) und damit die Erkenntnis, **welche** Bahn die kritische ist. Sie zu
parallelisieren ist auf dieser Maschine aber erst sinnvoll, wenn der Speicherbedarf
des Hybrid-Laufs kleiner ist (2e/2g): sonst zahlt die kurze Bahn den Preis der
langen.

### 2e Speicher (**gemessen** - und die Annahme kippt)

| Prozess | Aufruf | RSS-Spitze | Dauer |
|---|---|---|---|
| `c_kopf.exe` | 1 Kopf (`analysis/_m197/_ck_09DE0.case`) | 13,8 MB | 0,4 s |
| `hybrid_lauf.exe` | `--schritte 2000000` (ohne `--nativ-weiter`) | 89,6 MB | 1,2 s |
| beide gleichzeitig (kurz) | wie oben | 13,1 + 89,5 = **102,6 MB** | 1,0 s |
| **`hybrid_lauf.exe`** | **`--schritte 200000000 --nativ-weiter`** = der echte FRONT-Lauf, Aufruf wie im Preflight | **1402,1 MB** | **1264,2 s** |
| `c_kopf.exe` **daneben** | 44 Koepfe, hoechstens einer gleichzeitig | 15,7 MB | **~28 s je Kopf** |
| python-Treiber | Import + `deckung()` fuer 10 Koepfe | 28,4 -> 31,0 MB | 13,2 s |

Freier Speicher: 998-1033 MB vor den kurzen Messungen, **940 MB vor dem FRONT-Lauf,
29 MB in seiner Spitze** (Abnahme 910 MB), **1802 MB** nach seinem Ende.

#### 2e-1 Der FRONT-Lauf ist der Speicherfresser - und er waechst mit den Schritten

| Schritte | RSS-Spitze |
|---|---|
| 2 000 000 | 89,6 MB |
| 200 000 000 | **1402,1 MB** |

Das sind **~6,6 Byte je ausgefuehrtem Schritt** ((1402,1 - 89,6) MB / 198 Mio Schritte).
Der Verdacht (STRONG INFERENCE, kein Beweis): der Laeufer sammelt je Schritt etwas, das
nie gekuerzt wird. Dass ueberhaupt etwas mitwaechst, steht in den Rohausgaben selbst:
`MMIO-Adressen 42 distinkt` bei 2M gegen **21504** bei 20M (`docs/_r13bi_ram.txt`,
`_r13bi_laufprobe.py`). 6-8 Byte je Schritt waere ein Zeiger- oder Registerpaar je
Schritt. Das ist eine **Port-Frage**, keine Harness-Frage.

**Meine erste Einschaetzung in dieser Runde (\"der RSS haengt nicht an der Schrittzahl\")
ist damit widerlegt.** Sie war aus zwei kurzen Laeufen geschlossen worden - die kurzen
Laeufe zeigen 90 MB, der echte Lauf 1402 MB. Das ist der Grund, warum hier eine
Bestaetigungsmessung des echten Aufrufs gemacht wurde und keine Hochrechnung.

#### 2e-2 Die Ueberlappung selbst ist gemessen - sie kostet mehr, als sie bringt

Im **selben** Lauf wie der FRONT lief ein Strom von `c_kopf.exe`-Koepfen (genau der
Aufruf aus `c_kopf._port_lauf`: `c_kopf.exe <rom> <profil>`, ein Kopf je Prozess,
nacheinander): **44 Koepfe in 1264 s = ~28 s je Kopf**.

Vergleichswerte (alle belegt):

| Aufruf | je Kopf | Quelle |
|---|---|---|
| `c_kopf.exe`, allein | 0,4 s | `docs/_r13bi_ram.txt` |
| Wortinterpreter, allein | 0,1-1,0 s | `docs/_r13bi_ram3.txt` (10 Koepfe in 13,2 s) |
| `C Koepfe` im Preflight (Interpreter **und** `c_kopf.exe`) | 2,7 s | `analysis/_m234/_preflight_zeiten.txt` (310 s / 115) |
| **`c_kopf.exe` neben dem FRONT-Lauf** | **~28 s** | `docs/_r13bi_ram2.txt` |

Damit ist eine Beschleunigung der Gegenseite **ausgeschlossen**: die Nebenlaeufigkeit
bremst sie um **mindestens eine Groessenordnung** (10x bis 70x gemessen; STRONG
INFERENCE, die Ursache ist mit hoher Wahrscheinlichkeit das Auslagern - der freie
Speicher fiel im selben Lauf auf 29 MB).

#### 2e-3 Antwort auf die RAM-Frage

Beide Laeufe zusammen brauchen **bis zu 1417,8 MB** RSS (FRONT 1402,1 + `c_kopf.exe`
15,7) - **nicht ~105 MB**, wie die kurzen Messungen nahelegten. Gegen die gemessenen
940 MB freien Speicher ist das **nicht tragbar**: es bleibt ein Rest von 29 MB, und die
Gegenseite wird um eine Groessenordnung langsamer. Im echten Batch kommen VS Code
(~2,5 GB) und Ghidra (`-Xmx2g`) dazu; der Tiefstwert der sieben Batches war schon heute
373 MB (`docs/_r13bg_belege.md`).

Der **Python-Treiber** der zweiten Bahn ist dagegen harmlos: 28,4 MB leer, +0,26 MB je
Kopf (10 Koepfe gemessen), ~59 MB bei 115 Koepfen (HOCHRECHNUNG). Der Treiber war nie
das Problem.

#### 2e-4 Was zu tun ist (Vorschlag, keine Aenderung)

Nicht die Bahnen zuerst, sondern **den FRONT-Lauf**: (a) die RSS-Kurve ueber die
Schritte aufnehmen (ein Lauf, alle 10 s messen - Werkzeug liegt bereit:
`docs/_r13bi_ram2.py`, diesmal mit **mitgelesener** Ausgabe), (b) das wachsende Feld
finden (`~6,6 Byte/Schritt`, Kandidaten sind Schatten-/Ersatzlisten, MMIO-Adresstabellen
und die native Kopfspur in `port/hybrid/`), (c) es begrenzen (Ringpuffer/Deckel statt
Wachstum). Danach ist die Nebenbahn billig - und **beide** Zahlen, die den Batch heute
druecken (1264 s Laufzeit, 1,4 GB RSS), sind kleiner. Diese Spur ist der groessere
Hebel: die Bahn-Rechnung versprach -38 % (und traegt so nicht), ein begrenzter
FRONT-Lauf wuerde die 310 s der Bahn A1 **und** die Zeit der Bahn A2 senken.

### 2f Randbefunde, die in den `/ds`-Text gehoeren

1. **`m233_binary` ans Ende.** Es prueft Binaer-Alter gegen die Quellen
   (`scripts/m233_binary.py`, Ausgabe `_binary_quellen.txt`). Mit Bahnen kann es
   urteilen, **waehrend** eine Bahn baut (`m5_kopf_check` baut `m193_head.exe`,
   `port_regression` baut `port_selftest.exe`/`port_gl.exe`) oder ein Binaer laeuft -
   der Befund waere dann ein Artefakt der Nebenlaeufigkeit. Es ist mit 0,3 s zu billig,
   um dafuer ein Risiko zu tragen.
2. **A2 startet erst nach `m227_profile_live`.** Dieses startet
   `python -u scripts/c_kopf.py prof --out analysis/<EV>/_prof_live`
   (`scripts/m227_profile_live.py:85`) - also die `c_kopf`-**Familie**, auch wenn es
   `c_kopf.py` und nicht `c_kopf.exe` ist. Der Lauf dauert 0,1-0,6 s; danach ist die
   Familie fuer die gesamte A1-Kette bis `c_kopf_check` belegt. Bis dahin wartet A2
   (ein Sekundenbruchteil, kein Zeitverlust).

3. **Keine Bahn kann `hybrid_lauf.exe` neu linken.** `scripts/port_build.ps1` (der
   uebliche Bauaufruf) baut **nur** `ppc_poc.exe`, `port_selftest.exe` und
   `port_gl.exe` (`scripts/m233_binary.py:18-23`); `m5_kopf_check` baut
   `m193_head.exe`, `c_kopf_check` bei Bedarf `c_kopf.exe` (`c_kopf.py:3155`,
   Makefile-Ziel `ckopf` mit **eigenem** Objektstand `port/build/obj_ckopf`,
   `Makefile:157`). Ein laufendes `hybrid_lauf.exe` oder `c_kopf.exe` wird also von
   keinem Bau angefasst; die zwei Baeue der Bahn B sind dort seriell.

4. **Harness-Seite unveraendert.** Das Zeitlimit des Preflights liegt bei 30 min
   (`timeout=1800000`, Harness-Auftraege seit B216), der erkannte Befehlstext bleibt
   `python -u scripts/preflight.py before` - die Parallelisierung verkuerzt nur die
   Dauer. `hx/stand.py:530` **liest** `_preflight_zeiten.txt` nicht, es blendet die
   Datei nur aus der Fehllauf-Zaehlung aus; kein Harness-Parser haengt an ihrem
   Inhalt (Grep ueber `harness/hx/**` und `scripts/**`: nur Kommentare/Fundstellen).

5. **Folge fuer die Bilanz (erwartet, kein Defekt).** `hx/stand.py:831` rechnet
   `preflight_min` als **Summe der Laufzeiten** aller Preflight-Aufrufe des Batches und
   `fester_min = startroutine + preflight + schluss` (`:838`). Ein kuerzerer Preflight
   senkt also `fester Aufwand` und hebt `arbeit_min` - die Zeile im Batch-Report bewegt
   sich, ohne dass sich am Vorgehen etwas geaendert hat. Das gehoert in den Batch-Text
   des Umbaus, damit es nicht als Rueckschritt gelesen wird.

6. **Der Messaufruf ist zeilengenau derselbe wie im Preflight - und der Zustand ist
   unveraendert.** Die Rohausgabe des FRONT-Laufs in `docs/_r13bi_ram2.txt` nennt
   `200000000 | 8000844C | Schranke | 2985/42599 | nein`, `SPU 2 Lesezugriffe, 9
   Schreibzugriffe, erste PC L 80013DFC / S 80013FB4, 7 distinkte Offsets`,
   `Attrappe-4 135 Lesezugriffe, erste PC 8000C898`, `Anteil nativ 20577/200000000 |
   Aufrufe alle Registry-Koepfe 2633 gleich 179 ungleich 2450 | nicht vergleichbar: 4 |
   Schatten-Zustand: 0 | Schritte im Schatten 20577 | Zeitbasis 179` und
   `Hybrid-Funktionen nativ 6/94 | Gesamt 115/2087` - **Zeichen fuer Zeichen dieselben
   Werte** wie die Zeilen 24-29 des letzten gueltigen Preflights
   (`analysis/_preflight_234.txt@HEAD`). Damit ist belegt: (a) die Messung traf genau
   den Aufruf aus `m212_zeilen._lauf(LAUF_FRONT)`, und (b) die Messung ist
   deterministisch - dieselbe Zahl, zwei Laeufe.

7. **Der rote Hybrid-Befund ist alt, nicht neu.** `analysis/_preflight_234.txt:28/29`
   meldet `Hybrid-Anteil nativ` und `Hybrid-Funktionen nativ` als **FEHLER**
   (`... 2450 | Summe gleich: ja`), dazu `Binary Quellen` - `Befunde: 3 ... => BEFORE
   MIT BEFUNDEN`. Meine Messung reproduziert diese Zeilen; sie sind **kein** neuer
   Fund dieser Runde und gehoeren in die B234-Bewertung, nicht hierher.

## 3. Frage 3 — der umgeschriebene `/ds`-Vorschlag

`docs/_r13bi_ds_vorschlag.txt` steht jetzt als **Fassung 3**. Fassung 2 liegt als
`docs/_r13bi_ds_vorschlag_f2_zurueckgezogen.txt` daneben (umbenannt, nicht geloescht -
sie ist der Beleg dafuer, was gemessen wurde und was daraus folgt). Fassung 1
(`docs/_r13bh_ds_vorschlag.txt`) bleibt **unveraendert** stehen - Projektregel: alte
Belege werden nicht nachgezogen.

**Fassung 2 (der Hybrid-Lauf parallel zu `c_kopf_check`) ist zurueckgezogen.** Sie
stuetzte sich auf die Annahme, die Ueberlappung koste nichts; die Messung aus 2e zeigt
das Gegenteil (1,4 GB RSS, freier Speicher 29 MB, Gegenseite um eine Groessenordnung
langsamer). In Fassung 3 gilt wieder: **die zwei Port-Laeufe ueberlappen nicht**.

Was Fassung 3 aus Fassung 2 **behaelt** (weil es unabhaengig von der RAM-Frage richtig
ist):

* **Der Hybrid-Lauf bleibt ein eigenes Modul** (`scripts/m212_hybrid.py`, Zeilen
  unveraendert) - das ist die Voraussetzung fuer jede spaetere Parallelitaet und
  aendert am Verhalten nichts. In Fassung 3 laeuft es **hinter**
  `m210_bahnabdeckung` in derselben Bahn A (`m227_profile_live` -> `c_kopf_check` ->
  `m210_bahnabdeckung` -> `m212_hybrid` -> `m212_zeilen`), also **nie** neben
  `c_kopf.exe`.
* **Bahn C:** `m233_binary` als **letztes** (2f-1).
* **Bahnen sind Prozesse, nicht Threads** (2f-3, `verdict.capture` ist
  prozessweit); **Zeilenordnung** als Pflichtmechanismus (4.) und **Zeittafel je
  Bahn** (5.).

Was Fassung 3 **neu** vorschreibt: der eigentliche Auftrag dieser Runde ist **nicht**
die Bahn, sondern der **Speicherbedarf des FRONT-Laufs** (2e-1/2e-4): RSS-Kurve
aufnehmen, das Feld mit ~6,6 Byte je Schritt finden, begrenzen. Erst danach ist der
Parallelbetrieb zu messen - und dann mit dem Nachweis aus 2e-3 (Speicherwache), nicht
mit einer Annahme.

## 4. Was hier NICHT gemacht wurde - und die Grenzen der Messung

* Keine Aenderung an `scripts/`, `port/` oder `hx/` - beide Repos sind unberuehrt;
  der Harness ist weiter pausiert (`state=GATE_APPROVAL batch=234`).
* Kein Preflight-Lauf (er schreibt Belege und haette "nur lesen" gebrochen).
* Die `hybrid_lauf.exe`-Messungen liefen **ohne** `--s-log` (kein Schreibzugriff);
  `c_kopf.exe` lief mit stdout nach `DEVNULL`. `git status --porcelain` war vor und
  nach den Messungen leer (Decomp `7ec9d6a`).
* **Grenze 1 (Dauer):** `docs/_r13bi_ram2.py` liest die Kindausgabe erst nach der
  Messschleife (`p.stdout.read()`). Ist die Kindausgabe groesser als der
  Pipe-Puffer (64 KB), wartet das Kind - die Dauer 1264,2 s waere dann eine
  Obergrenze. Die sichtbaren Ausgabeteile sind klein (Kopf + Ergebnis, ~40+30
  Zeilen), und 1264 s liegen dicht an den 1181,3 s des Preflights B234 (dort ohne
  Pipe) - ein grosser Blockadeanteil ist unwahrscheinlich, aber **nicht
  ausgeschlossen**. Die **RSS-Spitze** ist davon nicht betroffen (sie wurde
  waehrend des Laufs gemessen). Fuer die Wiederholung: Ausgabe mitlesen (so steht
  es in TEIL 1 des `/ds`).
* **Grenze 2 (Stichprobe):** `c_kopf.exe` wurde **einmal** einsam gemessen (ein
  Kopf, 0,4 s) und **einmal** unter Last (44 Koepfe, ~28 s je Kopf). Die
  Kreuzprobe - derselbe Kopf allein, derselbe Kopf unter Last - fehlt; die
  Verlangsamung ist deshalb "mindestens eine Groessenordnung", nicht genauer.
* **Grenze 3 (Ursache):** dass das Auslagern die Ursache der Verlangsamung ist,
  folgt aus dem Speicherverlauf (940 -> 29 MB), ist aber nicht isoliert bewiesen
  (kein Gegenversuch mit gedeckeltem FRONT-Lauf). Genau diesen Versuch schreibt
  TEIL 1 des `/ds` vor.
  nach der Messung: `git status --porcelain` leer (Decomp `7ec9d6a`).
