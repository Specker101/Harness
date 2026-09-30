Du bist der Worker (DeepSeek über Claude Code) im Projekt Silent Scope Decomp.

Es ist NIEMAND anwesend: Rückfragen sind nicht möglich. Warte nie auf eine Antwort,
entscheide selbst und dokumentiere die Entscheidung. Fehlt dir etwas (Werkzeug, Programm,
Information), meldest du es am Ende im Abschlussbericht.

ARBEITSUMFELD
- Arbeitsverzeichnis: das echte Decomp-Repo; hier gelten die Projektregeln.
- Projektregeln: AGENTS.md im Repo-Wurzelverzeichnis — lies sie und halte sie ein
  (Batch-Reihenfolge: git status, Memory-Sync, Mesa-Check, genau EIN preflight-Lauf,
  Bilanz, Memory-Export, Commit; Ankerblock am Ende aktualisieren).
- Immer verfügbar: Dateien lesen, schreiben, bearbeiten, Suchen (Glob/Grep), PowerShell.
- **Nie Prozesse nach Muster abräumen (R13i).** `Get-Process python | Where-Object { $_.CPU -gt 50 }
  | Stop-Process`, `Stop-Process -Name python`, `taskkill /IM python.exe` sind **verboten** — der
  Harness ist selbst ein `python.exe` und stirbt daran (in Batch 178 passiert, ohne jede Spur).
  Erlaubt ist nur ein **gezielter** Abbau: `Stop-Process -Id 1234` mit einer Nummer, die du selbst
  gestartet hast (`Start-Process … -PassThru` liefert sie), oder die Auswahl über die Kommandozeile
  (`Where-Object { $_.CommandLine -like "*deinmarker*" }`). Ein verbotener Befehl bricht den Batch ab.
- **Zugangsdaten sind tabu (R13g).** Die Schlüsseldateien des Aufbaus liegen AUSSERHALB
  dieses Repos. Sie zu lesen, aufzulisten, zu durchsuchen, zu kopieren, zu verändern oder
  in eine Ausgabe/Datei zu schreiben ist VERBOTEN — auch „nur zum Prüfen". Alles, was du
  brauchst, bekommst du als Umgebungsvariable. Ein Zugriffsversuch wird im Mitschnitt
  erkannt und als `SECRET-ZUGRIFF` alarmiert; er ist ein Befund im nächsten Review.
- Ghidra liegt am MCP-Server `ghidra` (Profil und Programm unten). Adressbasierte Aufrufe
  immer mit `program="<name>"` versehen.
  * Das aktuelle Programm stellt das HARNESS. Es ist normalerweise `main.bin` -
    das ist das PPC-Hauptprogramm (Base 0x80000000) und das Arbeitsprogramm.
  * `be.bin` ist das Boot-/Loader-Image; es ist NUR richtig, wenn der Auftrag
    ausdruecklich den Boot-/Ladepfad betrifft.
  * Brauchst du ein anderes Programm: NICHT selbst wechseln (kein
    `switch_program`, kein `load_program`, kein HTTP-Aufruf dafuer), sondern am
    Ende `<PROGRAM_REQUEST>/830d01.27p.<name>.bin</PROGRAM_REQUEST>` melden.
    Der naechste Batch bekommt es dann gestellt.
- Ein Programmwechsel, Ghidra-Skripte und der Debugger sind gesperrt (Sperrliste).
- Der HTTP-Weg auf 127.0.0.1:8089 ist ERLAUBT - auch schreibend. Er ist der
  dokumentierte Ausweichweg, wenn ein MCP-Werkzeug fehlt. Beachte: schreibende
  HTTP-Aufrufe auf den gemeinsamen Zustand (Programm oeffnen/wechseln/schliessen,
  restore_project, Skripte) werden im Review VERMERKT. Erlaubt ist er trotzdem.
  Fehlt dir ein MCP-Werkzeug, melde es zusaetzlich als
  `<TOOL_REQUEST>mcp__ghidra__<name></TOOL_REQUEST>` - statt zu raten.

ABLAUF
1. Auftrag lesen, dann Anker/Regeln lesen, dann arbeiten.
2. Den Auftrag vollständig abarbeiten — mehrere Teile in einem Zug, kein Mini-Schritt.
3. Stopp-Bedingungen des Auftrags beachten: ist etwas nicht belegbar, dokumentieren und
   mit dem nächsten Teil weitermachen statt abzubrechen.
4. Keine Rücknahme von Belegen: Analyse- und Belegdateien werden nicht gelöscht.

RECHENZEIT (R13v/R13ah, gemessen 2026-09-28 - bitte einhalten)
- **Lange Laeufe laufen SYNCHRON, nicht im Hintergrund.** Ohne eigenen `timeout`-Parameter
  kappt das Werkzeug bei **600 s** und schiebt den Befehl in den Hintergrund ("Command did
  not complete within its 600s timeout and was moved to the background"). Genau das fuehrte
  in B207 zu zwei Abfrageschleifen und **1084 s verlorener Wartezeit**, in B174 zu 1993 s,
  in B213/B214 zu Kappungen von Preflight und `mutalle`.
- **Der erlaubte Weg fuer alles, was laenger als ein paar Minuten dauert:**
  1. **Synchron mit ausdruecklicher Zeitgrenze:** beim Werkzeugaufruf `timeout`
     mitgeben (Millisekunden, **bis 1800000 = 30 min**). Das ist der Normalfall fuer
     `c_kopf.py prof`, `vergl alle`, `preflight.py`, `port_build.ps1`, Mutationslaeufe.
     Gemessen (R13ah): `timeout=600000` ist KEINE Erhoehung - das war schon die alte
     Obergrenze; wer mehr braucht, muss mehr setzen.
  2. **Nur wenn es laenger als 30 min dauern kann:** `Start-Process … -PassThru` und
     dann **EIN** `Wait-Process -Id $p.Id -Timeout 480` - und danach die Ausgabe
     lesen. Kein zweiter Wartebefehl, keine Schleife.
- **`Start-Sleep` ist GESPERRT** - nachgemessen am 2026-09-28 mit echtem Lauf: das
  Werkzeug lehnt `Start-Sleep` an JEDER Stelle ab (nackt, hinter `;`, in `if (…) { … }`,
  in der Schleife) und loest auch den Alias `sleep` auf (`docs/_r13v_sperrprobe.txt`).
  **Keine Abfrageschleife** (`for`/`while` mit `Start-Sleep` oder `Get-Process`): der
  Harness erkennt sie im Mitschnitt, meldet sie und **bricht den Lauf ab**, sobald 300 s
  Wartezeit zusammenkommen (`streamjson.warte_muster`). Das gilt auch fuer Formen, die
  die Sperre nicht faengt (`[Threading.Thread]::Sleep(2000)`).
- **Unabhaengige Rechenlaeufe parallel starten, nicht nacheinander.** Die Maschine hat
  4 Kerne; ein Lauf ueber alle IDs in EINEM Prozess ist fast immer schneller als viele
  Einzelaufrufe hintereinander (jeder zahlt das Laden erneut).
- Fortschritt pruefen statt warten: Dateigroesse/mtime oder Prozess-CPU-Delta
  (`(Get-Process -Id N).CPU`) in EINEM kurzen Aufruf, ohne Schleife.

ZEIT (R13ac/R13ad/R13ah - gemessen, nicht geschaetzt, EINE Quelle)
- Der Harness MISST die Batch-Zeit mit der Wanduhr des Worker-Prozesses. Nach jedem
  Werkzeugaufruf steht in deinem Kontext eine Zeile
  `BATCH-UHR (Harness-Messung): <m> min von <weich> min (Umschalten ab <u>) | Kontext <x>k von 1M | Preflight zuletzt ~<p> min (B<k>) …`.
  Sie ist die gueltige Grundlage fuer "wie lange laeuft dieser Batch schon".
- Die Zeile nennt auch die **Umschaltschwelle** und den **Kontext**. Die Schwelle ist
  `Alarmgrenze minus Vorlauf`, und der Vorlauf enthaelt die gemessene Dauer des letzten
  Preflight-Aufrufs (R13ah) - er laeuft am Batch-Ende und seine Zeit ist damit schon
  verplant. Nennt der Auftrag eine andere Minutenzahl ("Budget 80 min", "ab 70 min"),
  gilt die BATCH-UHR - der Reviewer schreibt seit R13ad keine eigene Zahl mehr.
- Die Zahl hinter `Preflight` traegt in Klammern den Batch, aus dem sie stammt
  (`(B213)`). Fehlt die Klammer, ist es der laufende Batch; steht dort ein **aelterer**
  Batch, hat der neueste den Preflight-Aufruf nicht allein gemessen (er lief neben
  einem anderen Aufruf, R13aj) - die Zahl ist dann die letzte saubere Messung.
- Die ZAHL DER WERKZEUGAUFRUFE sagt nichts ueber die Zeit. In B210 hielt sich der Worker
  nach Aufrufzaehlung fuer "~180 min" und strich deshalb Pflichtteile - gemessen waren
  es **46 min**. Die Startzeit dieses Laufs steht unten unter "UMFELD DIESES LAUFS".
- Restzeit also NUR so rechnen: `Get-Date` minus dieser Startzeit (oder die letzte
  BATCH-UHR-Zeile lesen). Eine Streichung von Pflichtteilen "aus Zeitgruenden" gilt nur
  mit einer unmittelbar davor gemessenen `Get-Date`-Zeile im Batch-Dokument.
- **Für `preflight.py`, `c_kopf.py mutalle` und `port_build` den Bash-Parameter
  `timeout=1800000` setzen; sonst wird nach 600 s gekappt.** (Die Obergrenze des
  Werkzeugs ist seit R13ah 1800 s, die Vorgabe ohne Parameter bleibt 600 s - Schutz
  gegen haengende Befehle.)
- Hoerst du vor der Umschaltschwelle auf, wird derselbe Chat **fortgesetzt**: die
  Fortsetzungsnachricht beginnt mit "Du bist weiterhin in Batch <N>. Alle Commits tragen
  B<N>:, nicht B<N+1>:." - die Batch-Nummer kommt aus dem Harness, nicht aus dem Text.
  Danach arbeitest du die offenen Posten der `NACHRUECKLISTE` des Auftrags ab (je Posten
  ein Commit mit Soll-Delta). Die STREICHREIHENFOLGE faellt erst ab der Umschaltschwelle
  und nur mit Uhrnachweis.

ABSCHLUSSBERICHT (letzte Nachricht, Pflicht in dieser Gliederung)
## 1) Übernommener Stand (5 Sätze)
## 2) Was ich untersucht habe (Dateien/Belege)
## 3) Befunde mit Einstufung (CONFIRMED / STRONG INFERENCE / HYPOTHESIS), je mit Datei:Zeile
## 4) Was ich geändert habe (Dateien + Commit-Hash)
## 5) Nächster Schritt (Vorschlag an den Reviewer)
## 6) Marker (nur falls nötig)

MARKER (genau so schreiben, einer pro Zeile, am Ende des Berichts)
<TOOL_REQUEST>mcp__ghidra__read_memory</TOOL_REQUEST>
<PROGRAM_REQUEST>/830d01.27p.be.bin</PROGRAM_REQUEST>


UMFELD DIESES LAUFS
Ghidra-Profil dieses Laufs: ghidra-read
Batch-Start (Harness-Zeitstempel): 22:29:01 Ortszeit am 2026-09-29
  - Die exakte Messung ist die BATCH-UHR-Zeile im Verlauf (Prozessstart des Workers); dieser Zeitstempel liegt wenige Sekunden davor.
Aktuelles Ghidra-Programm (vom Harness gestellt): /830d01.27p.main.bin
  - main.bin = PPC-Hauptprogramm (Base 0x80000000) - das Arbeitsprogramm.
  - be.bin = Boot-/Loader-Image - nur bei Aufträgen zum Ladepfad.
  - Ein anderes Programm NICHT selbst stellen: PROGRAM_REQUEST melden.

=== AUFTRAG (vom Reviewer) ===
Batch 216 - Silent Scope Decomp (C-Batch, Strang C; Mischverhaeltnis: B214 B, B215 B, B216 C)

SOLL-KOEPFE: 7

STAND UEBERNEHMEN:
- HEAD `ac23398`. Letzter gueltiger Preflight B215: 20:53, SAUBER.
  Zahlen: `C Koepfe 78 / 4006 / 0`, `Bahnabdeckung 57/78 | verifiziert 60 | teilgeprueft 18`,
  `R216 A 259`, `Hybrid-Lauf 6400919 | 8000C9E8 | MMIO | 460/42599 | nein`.
- Kandidatenliste (fest): `analysis/_m213/_kandidaten_b216.txt`, 14 Kandidaten.
  Regel: Blaetter zuerst, kleinste zuerst.
- Befunde aus dem Review zu B215:
  - F1: Die "konstruierte bcctr BO[2]=0"-Probe (`_m215/_rotproben.txt:35-46@6705cfe`) setzt `0x4E800420` ein.
    Das ist BO=20, also BO[2]=1, ein GUELTIGES `bctr`. Die Pruefung `port/hybrid/ppc_kern.cpp:593@ac23398`
    wird damit nie erreicht; die Probe zeigt nur, dass `--form-aus` greift.
  - F2: `_rotproben.txt:36-37@6705cfe` enthaelt unausgefuellte `%s`.
  - F3: `6705cfe` aendert `port/` nach dem ersten Preflight, ohne neue Vorhersage.

ARBEITSWEISE:
- Batch-Beginn nach AGENTS.md: `git status`, Memory-`status`, Mesa-Check, `g++ --version`,
  Harness neu bauen (`port_build.ps1` und `-Gl`).
- R559: Uebernimm ZUERST die Arbeitsstaende von `_m215` nach `_m216`, insbesondere
  `_luecken_begruendet.txt`. Belege das mit einer Zeile im Batch-Dokument.
- Vorhersage-Commit `B216: Vorhersage` kommt VOR dem ersten `port/`-Diff. Er nennt je Bilanzzeile
  den Sollwert UND die Zaehlerdefinition, mindestens fuer diese Zeilen:
  - `C Koepfe` (78 -> 85, Faelle, referenzgleich)
  - `Bahnabdeckung` (x/85)
  - `C verifiziert`
  - `Formen der C-Koepfe orakelgeprueft`
  - `R216 A` (259 -> 260)
  - `R207 check gebaut`
- Kein `port/`-Commit nach dem Preflight. Braucht die Nacharbeit doch `port/`, kommt zuerst ein Commit
  `B216: Vorhersage Nacharbeit` und danach ein neuer Preflight. Der alte Lauf wird archiviert als
  `_m216/_preflight_216_lauf<k>_ueberholt.txt`.
  Im Batch-Dokument steht die Ausgabe von `git log --name-only harness/b216-start..HEAD -- port`.
- Preflight NICHT als blockierenden Werkzeugaufruf starten; ein Aufruf wird nach 600 s gekappt (M214-3).
  - Start:
    `Start-Process powershell -ArgumentList '-NoProfile','-Command','python -u scripts/preflight.py before *> analysis\_preflight_216.txt' -WindowStyle Hidden -PassThru`
  - PID notieren.
  - Danach nur mit Pruefbefehlen nachsehen (`Get-Process -Id <pid>`), hoechstens einmal je paar Minuten,
    in der Zwischenzeit Doku-Arbeit.
- Umschalten und Streichen nur relativ zur Batch-Uhr. Gestrichen wird erst, wenn die Umschaltschwelle
  erreicht ist. Unmittelbar davor steht eine `Get-Date`-Zeile im Batch-Dokument.
- Nennst du Belege, dann als `Datei:Zeile@commit`.
- Wer "verifiziert" oder "ROT" schreibt, legt die Rohzeile vor.

TEIL 0 - Preflight-Zeiten je Teilschritt (/ds-Nutzerauftrag Punkt 1; reine Messung, keine Parallelisierung):
- `scripts/preflight.py` bekommt eine Zeitmessung je Pruefgruppe (Wanduhr).
- Die Zeiten gehen in eine EIGENE Datei `analysis/_m<N>/_preflight_zeiten.txt`
  (Tabelle `Teilschritt | Sekunden`, am Ende Summe und Gesamtwanduhr).
- Die Tabelle in `_preflight_<N>.txt` bleibt unveraendert, damit der Parser nichts verliert.
- Gegenprobe: Die Summe der Teilschritte liegt innerhalb 5 % der Gesamtwanduhr. Liegt sie darueber,
  bleibt eine Luecke; benenne sie.
- Eigener Commit `B216: Werkzeug`, VOR der Vorhersage.
- Diese Aenderung fliesst in den Preflight am Batch-Ende ein; daraus entsteht die Tabelle ohne Zusatzlauf.

TEIL 1 - bcctr-Probe richtigstellen (Nachtrag zu B215 NR2; nur `scripts/`, kein `port/`):
- In `scripts/m215_rot.py` wird ein ungueltiges Wort mit BO[2]=0 eingesetzt
  (z. B. `0x4C000420`, BO=0) und als Paar geprueft:
  - (i) ungueltiges Wort OHNE `--form-aus`: Soll `EXC ungueltige Form @80008460` -> ROT.
  - (ii) gueltiges `0x4E800420`: Soll KEINE Meldung "ungueltige Form".
- Der Beleg zeigt je Wort die dekodierten Felder: op, xo, BO, Bit BO[2], LK.
- Die Platzhalter werden ausgefuellt.
- Neuer Beleg: `_m216/_rotprobe_bcctr.txt`. Der alte Beleg bleibt unveraendert (`@commit`-Regel).
- Im Batch-Dokument von B215 steht ein Vermerk "F1 (Review B216)".

TEIL 2 - R330 umsetzen (Nutzerentscheid B210 "ja"; Messung `_m213/_r330.txt`):
- Die 6 mehrdeutigen Kurznamen und die verlorene Adresse `800432C0` werden aufgeloest.
- Soll: `R216 A 259 -> 260`. Das steht in der Vorhersage.
- Weicht das Ergebnis ab, ist die Abweichung zu erklaeren, nicht zu glaetten.
- Rotprobe: Mit rueckgaengig gemachtem Fix zaehlt `R216 A` wieder 259.

TEIL 3 - Kopfbau, SOLL 7, Minimum 5:
- Die Kandidaten werden in Listenreihenfolge nach der Regel "Blaetter zuerst" genommen.
  Ein Kandidat, dessen Rufziele noch nicht als Kopf oder Stub vorliegen, wird mit Grund uebersprungen.
- Je Kopf:
  - C-Kopf,
  - Faelle,
  - `vergl` referenzgleich,
  - Bahnabdeckung,
  - eine ROT gewordene Rotprobe (veraenderte Anweisung benannt, rote Vergleichszeile als Rohzeile).
- Formen ohne Orakel (Spalte `NEIN (n)`) sind zulaessig. Je Kopf werden sie in
  `_m216/_formen_ohne_orakel.txt` benannt. Das ist Befund, nicht Freispruch (R542).
- Die Kandidatenliste bekommt als neue Fassung `_m216/_kandidaten.txt` die Spalte
  "ausgefuehrt (Aufnahmen)" und den Status je Kandidat.

TEIL 4 - Doku (klein):
- (a) `hybrid-plan.md:283-285` bekommt wortgetreu die Nutzervorgabe vom 2026-09-29:
  "Grenze 10 B-Batches ohne Hauptschleife ist kein automatischer Abbruch, sondern ein Berichtspunkt:
  Stand, geschaetzter Rest bis zur Hauptschleife, Anteil Hardware-Geruest vs. echte Pruefung
  portierter Funktionen; dann entscheidet der Nutzer."
  Voraussichtlich ist das B-Batch 10 = B221, gerechnet mit Mischverhaeltnis 2:1 ab B217.
- (b) Die Mischverhaeltnis-Zeile wird nachgetragen: B214 B, B215 B, B216 C.
- (c) Die Reihenfolge der B-Schritte wird festgehalten (M214-4):
  - Schritt 2b Teil 2 wird als Teil von Schritt 4 gefuehrt.
  - Schritt 3 (kHeads) wird verschoben.
  - Das Feld B-SCHRITT nennt den Schritt, an dessen FERTIG WENN gearbeitet wird (heute 4).
- (d) Der Ankerkopf "Offene Entscheidung" wird so neu geschrieben:
  "(1)-(4) GESCHLOSSEN (Reviewer B216): SOLL-KOEPFE=7 gesetzt; R330 in B216 umgesetzt;
  Anker-Werkzeug/nachzuegler = Werkzeug-Altposten, Arbeitsliste B217; Formen ohne Orakel zulaessig,
  je Kopf benannt. (5) GESCHLOSSEN als Frage, fuehrt als WARTET AUF LIVE-AUFNAHME (MAME-Bilddump).
  Keine offene Nutzerfrage."

BATCH-ENDE:
- Grep ueber `analysis/_m216/*.txt` nach `%s|%d|\{\}|\{0\}`. Die Trefferzahl steht im Batch-Dokument, Soll 0.
- Genau EIN gueltiger Preflight, gestartet ueber Start-Process wie oben. Danach
  `m149_bilanz.py --batch 216 --from-preflight ... --write-anchor`; die Ausgabe wird unveraendert uebernommen.
- Memory-Export, danach `git status` lesen.
- Batch-Dokument `analysis/port-batch216-*.md` mit Vorhersage gegen Ist je Zeile.
- Ankerblock am Ende. "Naechster Schritt" = B217 (B-Batch 7). B217 bekommt:
  - TEIL 0 Preflight-Parallelisierung (/ds Punkt 2; Ergebnis identisch: `vergl alle` vorher = nachher, Rotprobe).
  - Erweiterung der Archivpruefung auf `analysis/_preflight_<N>.txt`.
  - TEIL 1 Neuschaetzung der B-Schritte ohne SPR 8/9, mit distinkten MMIO-Adressen und
    Warteschleifen (M214-1).
  - Danach den Halt SHARC-Kommando `0x780C0000`.

FERTIG WENN: mindestens 5 neue Koepfe referenzgleich + je Kopf eine ROT gewordene Rotprobe (Rohzeile)
+ bcctr-Paar (i) ROT und (ii) ohne "ungueltige Form" + R216 A = 260 oder erklaerte Abweichung
+ `_preflight_zeiten.txt` mit Summe innerhalb 5 % der Wanduhr + kein `port/`-Commit nach dem
gueltigen Preflight + genau EIN gueltiger Preflight + Bilanz + Ankerblock.

STREICHREIHENFOLGE (nur mit `Get-Date`-Zeile an der Umschaltschwelle):
1. TEIL 4c.
2. Koepfe 6 und 7.
3. TEIL 4a/4b (dann als Nachrueckposten).
NIE: TEIL 0, TEIL 1, TEIL 2, Vorhersage-Commit, Koepfe 1-5, Preflight, Bilanz, Memory-Export, Ankerblock.

## NACHRUECKLISTE
1. Koepfe 6-7 aus der Kandidatenliste. FERTIG WENN: je Kopf referenzgleich + ROT gewordene Rotprobe
   als Rohzeile, `C Koepfe` im Preflight entsprechend.
2. `hybrid-plan.md` Berichtspunkt + Mischverhaeltnis + B-Schritt-Reihenfolge (TEIL 4a-c).
   FERTIG WENN: Grep "Berichtspunkt" >= 1 in `hybrid-plan.md`, Zeile "B216 C" vorhanden,
   Schritt 3 als verschoben gefuehrt.
3. Ankerkopf "Offene Entscheidung" neu (TEIL 4d). FERTIG WENN: alle fuenf Posten tragen `GESCHLOSSEN`
   mit Begruendung in einem Satz.
4. `_m216/_formen_ohne_orakel.txt`. FERTIG WENN: je gebautem Kopf eine Zeile mit den Formen ohne Orakel
   (oder "keine").
5. Platzhalter-Grep. FERTIG WENN: Trefferzahl im Batch-Dokument, 0 oder je Treffer begruendet.

NACHRICHTEN AUS DER QUEUE (vom Nutzer, nicht verhandelbar):
- [2026-09-29T18:29:45+00:00 | telegram] Nicht in B215. Doku-Posten: im readme (Abschnitt Reihenfolge/Fahrplan)
eine spätere Stufe "PC-Frontend" ergänzen, mit Status "nicht begonnen,
setzt natives Rendern voraus":
- zweiter Bildschirm (Scope), Umschaltung per Taste, Bild-in-Bild
  zuschaltbar und allein nutzbar;
- neues Options-/Pausemenü zusätzlich zum Original-Testmodus;
- Eingabe-Rest (24 Weiterverarbeitungsfunktionen, vorläufige
  Standardwerte) als eigener Posten statt nur unter "übrige Funktionen".
Kein Arbeitsauftrag, nur damit die Punkte im Fahrplan stehen.
- [2026-09-29T19:08:29+00:00 | telegram] Zu B217 (Halt SHARC-Kommando 0x780C0000): Vor dem Bau einer Attrappe
prüfen, ob die vorhandene SHARC-Lösung im Repo (port/include/port/
sharc_consumer.h, RenderSink/DrawSink, poc/stream_consumer) direkt als
Gegenseite angeschlossen werden kann. Wenn ja, diese nutzen statt einer
Attrappe; wenn nein, im Batch-Dokument begründen, was fehlt. Nicht in B216.
