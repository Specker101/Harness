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

RECHENZEIT (R13v, gemessen 2026-09-28 - bitte einhalten)
- **Lange Laeufe laufen SYNCHRON, nicht im Hintergrund.** Das Werkzeug kappt bei
  600 s und schiebt den Befehl dann in den Hintergrund ("Command did not complete
  within its 600s timeout and was moved to the background"). Genau das fuehrte in
  B207 zu zwei Abfrageschleifen und **1084 s verlorener Wartezeit**, in B174 zu 1993 s.
- **Der erlaubte Weg fuer alles, was laenger als ein paar Minuten dauert:**
  1. **Synchron mit ausdruecklicher Zeitgrenze:** beim Werkzeugaufruf `timeout`
     mitgeben (Millisekunden, bis 600000 = 10 min). Das ist der Normalfall fuer
     `c_kopf.py prof`, `vergl alle`, `preflight.py`, `port_build.ps1`, Mutationslaeufe.
  2. **Nur wenn es laenger als 10 min dauern kann:** `Start-Process … -PassThru` und
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
Ghidra-Profil dieses Laufs: none
Kein Ghidra-Programm gestellt (Profil ohne Ghidra-Zugriff).

=== AUFTRAG (vom Reviewer) ===
Batch 209 - Silent Scope Decomp

STAND UEBERNEHMEN:
HEAD 036ca59 (B208). Bilanz: R207 686, C Koepfe 78/2903/0, C Einbindung 8/20/51, nachzuegler 64/30 (6/3) + (d) 9/3, S1-DOKU 1693, Paket E offen 38/2674.
Strang B, Batch 2 von hoechstens 20; Abbruch nach 10 ohne Boot bis zur Hauptschleife. Der Kern `port/hybrid/ppc_kern.*` ist GLEICH mit `m114_matrix`. Nicht bewiesen ist, dass er der ISA entspricht (Aussensicht M208-2). Die Zahl „139867 von 178342 Woertern" mischt Code und Daten (M208-4: `_m208/_formen_rom.txt:3-7`, 22215 Datenwoerter mit Opcode 0).
Nachgeprueft: `capture/poc_ref_boot_*.txt` enthaelt nur Kommandostrom-Worte („W : value : producerPC"), keine Speicherkarte und kein MMIO.

ARBEITSWEISE:
- Batch-Beginn nach AGENTS.md. Startzeit mit `Get-Date`.
- Reihenfolge der Commits: Werkzeug/Doku, dann `B209: Vorhersage`, dann `port/`. **Beim Vorhersage-Commit muss `git status --porcelain port/ Makefile` LEER sein; die Ausgabe gehoert in den Commit-Text.** Die Vorhersage enthaelt KEINE Messwerte aus port-Code (in B208 geschehen, R391 im Sinn verletzt).
- Genau EIN gueltiger `preflight`-Lauf, danach Bilanz `--batch 209 --from-preflight … --write-anchor`, Memory-Export vor dem Commit und der Ankerblock am Ende.
- Keine Abfrageschleifen. Uhrzeit nur ueber `Get-Date`. Budget 80 min; Ende erst ab 70 min oder wenn FERTIG WENN erfuellt ist.
- Profil none. Speicherkarte und MMIO liest du aus `mame/` (Treiber und Adresskarte) und `analysis/decompressed-ppc-analysis.md`; MAME ist Dokumentation, kein Beweis.

TEIL 1 - Unabhaengige Kern-Gegenprobe (M208-2), Werkzeug-Commit:
a) Die dritte Welt ist Unicorn (QEMU-PPC32, Big Endian). Installation in eine eigene venv unter `tools/` (nicht im Port), Version und Wheel-SHA protokollieren. Zuerst ein Rauchtest mit bekannten Vektoren: `addc` (setzt CA, liest es nicht), `subfc.` (CR0) und `rlwinm`.
b) `scripts/m209_isa_orakel.py`: Es liest die Schrittdatei aus B208 (oder erzeugt sie neu mit `c_kopf.py schritte`, SHA-Abgleich zu `_m208/_schritte_sha.txt`) und dazu die Zufallsschritte. Jeden Schritt fuehrt es in Unicorn aus: GPR, CR, XER und LR/CTR aus dem Vorzustand setzen, Lesezellen abbilden, ein Wort ausfuehren, dann Nachzustand und Schreibzugriffe mit `m114_matrix` vergleichen. Ausgabe je Form: Schritte, Abweichungen, erstes Beispiel. Beleg `_m209/_isa_orakel.txt`.
c) Abweichungen einordnen: Fehler in m114 bzw. im Kern (gemeinsamer Referenzfehler), Unicorn-Eigenheit (mit ISA-Zitat) oder Nachbildungsfehler. In diesem Batch KEINE Aenderung an `m114_matrix` oder am Kern. Befunde kommen als Liste in den Anker; die Korrektur beider Welten mit Neuvergleich aller 78 Koepfe ist Arbeit fuer den C-Batch.
d) Ersatzweg, falls Unicorn nicht installierbar ist oder die Register nicht setzen kann: Ursache belegen und stattdessen ISA-Handvektoren schreiben, je modellierter Form mindestens 3 Vektoren. Die Erwartungswerte werden aus dem ISA-Pseudocode von Hand gerechnet, mit Abschnittsangabe.
e) Anker und `hybrid-plan.md` Schritt 1: Die Formulierung „bewiesen" wird zu „Python-gleich (Schritt-Differenz) + ISA-Orakel X/Y".

TEIL 2 - Zensus nur ueber Code (M208-4), im selben Werkzeug-Commit:
Das Format von `capture/ppc_cov_boot.bin` und `capture/ppc_coverage.bin` im Repo nachschlagen (Grep auf die Dateinamen in `scripts/`). Die Formenzaehlung nur ueber die ausgefuehrten Adressen: (i) Bootpfad, (ii) Gesamtlauf. Je Form ausweisen: Woerter, Modelliert ja/nein, FPU getrennt. Beleg `_m209/_formen_bootpfad.txt`.
Ergebnis ist die Luecke fuer den Boot-Schritt: die Liste der NICHT modellierten Formen im Bootpfad, sortiert nach dem ersten Auftreten. Im Anker ersetzt diese Zahl die B208-Zahl als Fortschrittsmass.

TEIL 3 - Maschine (B-Schritt 2), Vorhersage, dann `port/hybrid/`:
a) Plan anpassen (ENTSCHEIDUNG Reviewer): Die Gegenprobe fuer „Maschine" ist nicht `poc_ref_boot`, sondern ein erster Lauf ab dem Einsprung des Hauptprogramms. Einsprung und Anfangszustand nach dem Lader aus `decompressed-ppc-analysis.md` belegen; was unklar ist, als HYPOTHESIS kennzeichnen.
b) `port/hybrid/maschine.{h,cpp}`: Speicherkarte mit RAM, ROM-Bild und den MMIO-Bereichen, die im Bootpfad laut Coverage und Code vorkommen. Kopfkommentar „Hybrid-Geruest, im Port zu ersetzen". Jeder Zugriff ausserhalb der Karte und jedes nicht modellierte MMIO-Register fuehrt zu lauter Ablehnung `EXC mmio <addr> <breite>`, wie beim Kern. MMIO-Lesewerte bekommen nur Attrappen mit Quellenangabe (MAME-Zeile oder ROM-Stelle).
c) Laeufer `port/hybrid/hybrid_lauf.cpp`, Makefile-Ziel `hybrid`: Er startet am Einsprung, laeuft bis zum ersten `EXC` oder bis zu einer Schrittgrenze und protokolliert: Schrittzahl, Halt-PC mit Grund und die Menge der ausgefuehrten PCs. Beleg `_m209/_lauf1.txt`.
d) FERTIG WENN fuer „Maschine" im Plan und hier:
   - (1) Alle ausgefuehrten PCs liegen in `ppc_cov_boot.bin`; jede Abweichung wird einzeln benannt, als Befund und nicht geglaettet.
   - (2) Der erste Halt ist benannt (Form, MMIO oder Schrittgrenze), mit Adresse.
   - (3) Rotprobe: eine MMIO-Attrappe verstellen oder ein Wort im frueh ausgefuehrten Pfad mutieren. Der Lauf verlaesst die Coverage-Karte oder haelt anders; danach Ruecknahme.
   - (4) Erreicht der Lauf Schreibzugriffe in den Kommandostrom, werden die ersten N Worte gegen `poc_ref_boot_0.txt` verglichen. Sonst steht im Plan, ab welchem Schritt das moeglich wird.

TEIL 4 - Vormerkung fuer B210 (nur `analysis/`):
Deine Vorgabe fuer B210 kommt woertlich in Anker und `hybrid-plan.md`. Bahnabdeckung wird Pflichtgroesse: „verifiziert" heisst 100 % Bloecke ODER jede Luecke einzeln begruendet, sonst „gebaut, teilgeprueft". Neue Bilanzzeile „Bahnabdeckung (Koepfe 100 % / Bloecke gesamt)". Fallfabrik fuer die 23 Koepfe unter 100 %, schlechteste zuerst (`80056684` 3/15, `80017A8C` 4/14, `8008579C` 3/10, `80062C78` 7/18). Dazu A1 und A2 sowie die Korrekturen aus dem ISA-Orakel.

FERTIG WENN:
- ISA-Orakel (oder Ersatzweg) je Form belegt, Befunde eingeordnet, Anker auf „Python-gleich" herabgestuft.
- Bootpfad-Zensus liegt vor, mit Lueckenliste.
- `maschine` und `hybrid_lauf` gebaut; Lauf 1 mit PCs in der Coverage-Karte bzw. Abweichungen benannt, erster Halt benannt, Rotprobe ROT.
- B210-Vormerkung steht im Anker.
- Genau ein Preflight-Lauf, Bilanz, Arbeitsbaum sauber.

STREICHREIHENFOLGE (zuerst streichen):
1. TEIL 3d(4), der Stromvergleich.
2. Gesamtlauf-Zensus (ii); der Bootpfad (i) bleibt.
3. Orakel nur ueber eine Stichprobe von mindestens 100.000 Schritten plus alle Zufallsschritte statt ueber alle Schritte.
NIE gestrichen werden TEIL 1 in irgendeiner Form, der Bootpfad-Zensus, der erste Halt und die Rotprobe von Lauf 1, Preflight und Bilanz.

NICHT TUN:
- keine C-Koepfe;
- keine Aenderung an `m114_matrix` oder `ppc_kern` (Befunde nur dokumentieren);
- keine neuen Befehlsformen nachruesten (das ist der Boot-Schritt);
- `host_registry.h` nicht anfassen;
- keine Hardware-Modelle ohne Quellenangabe;
- Unicorn gehoert NICHT in den Port und nicht in den Standardbau.

BATCH-ENDE:
Preflight (genau ein gueltiger Lauf; ein Fehllauf wird archiviert und mit Ursache genannt), Bilanz, Soll/Ist erklaeren, Memory-Export, git status lesen, Commit, Ankerblock. Im Ankerblock steht als „Naechster Schritt": „B210 = C-Batch (Bahnabdeckung Pflicht, 23 Koepfe, ISA-Korrekturen, A1/A2)". Im Batch-Dokument stehen die Zeilen `ENTSCHEIDUNG (Reviewer):` zu Gegenprobe Maschine, Vorhersage bei leerem port-Status, M208-2 und M208-4. Im Abschlussbericht stehen Start- und Endzeit laut `Get-Date`.

NACHRICHTEN AUS DER QUEUE (vom Nutzer, nicht verhandelbar):
- [2026-09-28T17:38:54+00:00 | telegram] Nutzerentscheidung zu Aussensicht M208-1 (bitte als ENTSCHIEDEN (Nutzer, 2026-09-28) in Anker und hybrid-plan.md): In den B-Plan kommt ein eigener Schritt "Kontrollfluss/Supervisor" zwischen "Maschine" und "kHeads-Uebernahme/Boot": blr ueber LR, bctr/bcctr, sc/rfi, mtmsr/mfmsr, mtspr/mfspr, Decrementer bzw. VBL-Interrupt, FPU-Anteil im Bootpfad - mit eigenem FERTIG WENN und Gegenprobe (ISA-Orakel aus TEIL 1 plus Coverage). In B209 wird er NUR geplant, nicht gebaut; haelt Lauf 1 an einer solchen Stelle, ist das der erwartete erste Halt und wird so benannt. Budget: "hoechstens 20" und "Abbruch nach 10" zaehlen B-Batches, nicht Kalender-Batches; nach Lauf 1 schaetzt der Plan den Bedarf je B-Schritt neu (HYPOTHESIS). Antwort auf die offene Frage: die 21 Referenzstroeme stammten aus einer Harness-Zaehlung; es gilt die gezaehlte Zahl 20.
