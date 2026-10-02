<TELEGRAM_SUMMARY>
Ergebnis: B237 (C-Batch, Paket E) hat vier neue Köpfe gebaut: 8003C254, 8005B33C, 8005B38C und 800660D4. Jeder Vergleich mit dem ROM ergab 0 Abweichungen, jede Rotprobe war ROT (nachgeprüft bei 660D4: 2293 Zeilen gleich, mit Mutation 144 Abweichungen). Die referenzgleichen Köpfe stehen jetzt bei 119/6913/0 (`_preflight_237.txt:16`). In Paket E sind noch 8 Köpfe mit 836 Insn offen. Die neuen Köpfe kommen im Bootlauf nicht vor (0 KOPFWEIT-Treffer, nachgeprüft).
Bewertung: gut. FERTIG WENN erreicht: ja – 4 Köpfe mit vergl 0 und mut ROT, Zeile „C Koepfe live“ vorhanden, R391 OK, Bilanz geschrieben. Gültig ist der letzte Preflight (0 Befunde). Die Fortsetzung meldete nur „NACHRUECKLISTE ERLEDIGT“, ein zweiter Lauf war deshalb nicht nötig. Befund: es gab 4 Preflight-Läufe (36 min, 51 % des Batches), weil die neue Preflight-Zeile den Bilanz-Parser brach. Kleiner Befund: der Code-Kommentar verweist auf „M237-1“, diese Kennung gibt es nicht. Der B-Anteil nativ liegt unverändert bei 47527/900M.
Kosten/Laufzeit: $0,19, 1h11m, 152 Anfragen, 1 Fortsetzung.
Nächster Batch: B238 als B-Batch nach Nutzerentscheid R236-1: SHARC-Antwortfolge aus dem Mitschnitt nachbilden, vorher prüfen, ob sie vom gesendeten Inhalt abhängt.
B-SCHRITT: kein B-Batch (Strang C)
M236-3: übernommen als B238 TEIL 0 (Stillstandszählung je B-Batch, echter Halt + Preflight-Front). Wirkung noch nicht belegt -> bleibt offen
UEBERTRAG: keiner - alle Posten erledigt
ENTSCHIEDEN: R236-1 (Option A) und R236-2 (Zeitgrenze für einzelne Befehle 30 min) umgesetzt. Ankerfrage (1) wird mit GESCHLOSSEN geführt.
ENTSCHIEDEN: B238 baut keine Köpfe (SOLL-KOEPFE 0, B-Batch). Die Median-Regel betrifft nur C-Batches.
ENTSCHIEDEN: Die Sicherung zählt B238 und den nächsten B-Batch (B240).
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: ghidra-read
program: /830d01.27p.main.bin
</DS_TOOLS>

## VERALLGEMEINERUNG

**Befund 1 – neue Preflight-Zeile bricht den Bilanz-Parser (4 Preflight-Läufe, 36 min).**
(a) Fehlerklasse: Mehrere Muster suchen über dieselbe Preflight-Ausgabe, und ein Teilstring kollidiert. Ein Muster ohne Anker trifft dann Klartext in einer anderen Zeile. Das fällt erst auf, wenn die Bilanz nach einem vollen Preflight läuft.
(b) Verwandte Fälle: jede neue oder geänderte Preflight-Zeile gegen alle Muster in `m149_bilanz.py:m_preflight`. Ebenfalls betroffen sind die übrigen unverankerten Muster (`Hybrid-SPU`, `C Fallrueckgang`, `Formen …`). Die Instruktion verlangt deshalb vor dem Preflight einen Grep der neuen Zeilentexte gegen alle Schlüssel aus `m_preflight`, mit einer Trefferliste im Batch-Dokument.
(c) Nicht geprüft: die semantische Richtigkeit der Werte, die die Bilanz übernimmt. Es geht nur um Kollisionen.

**Befund 2 – Kommentar mit der Kennung „M237-1“.**
(a) Fehlerklasse: eine Herkunftskennung wird zitiert, die es nicht gibt. Damit ist sie eine unbelegte Referenz.
(b) Verwandte Fälle sind alle neuen Kommentare und Dokumentzeilen mit M/R-Kennungen. Die Instruktion verlangt, dass jede neu zitierte Kennung per Grep in `analysis/` oder im Auftrag nachgewiesen ist.
(c) Alte Kommentare werden nicht nachgezogen.

**Befund 3 – B-Messgröße steht still (Prüfpunkt a).**
(a) Fehlerklasse: Die Zahl, die das Ziel von Strang B misst, ist der Anteil nativ, also 47527 von 200M bzw. 900M. Sie bewegt sich nicht, solange die Front steht (B233, B235, B236). Halt-PC und Wegmaß sind nur Ersatzzahlen.
(b) Der B238-Bericht muss beide Zahlen nennen: die Schritte gesamt und den nativen Anteil. Halt-PC und Wegmaß werden darin ausdrücklich als Ersatz geführt.
(c) Ob mehr Schritte nach der Front den nativen Anteil heben, wird nicht geprüft. Das zeigt sich erst bei einer Bewegung.

**Prüfpunkt b – „fehlt“ wurde geprüft:**
- Die Antwortfolge ist vorhanden: `capture/boot_20260829_194618.log:51637-51659`. Dort antwortet der SHARC mit 80/01/82/03/84, der PPC schreibt FF/7E/FD/7C/FB.
- Die Prüfsumme ist dokumentiert in `analysis/bucket-c-rest-2026-09-15.md:67`. Dort wird `(u4&0x7F)|(u5&0x7F)<<7` mit `Summe&0x3FFF` verglichen. Eine Abhängigkeit vom gesendeten Inhalt ist damit eine STRONG INFERENCE und muss gemessen werden.
- Ein ROM-abgeleitetes Protokollmodell ist zulässig: `analysis/r1b-workstream.md:135-140`.

<DS_INSTRUCTION>
Batch 238 - Silent Scope Decomp

STAND UEBERNEHMEN:
- HEAD 7798b35, Arbeitsbaum sauber. Gültig ist der Preflight `analysis/_preflight_237.txt` (510,5 s, 0 Befunde).
- C Köpfe 119/6913/0. Paket E: 8 Köpfe / 836 Insn offen.
- Hybrid-Anteil nativ: 47527/200000000 (Preflight) und 47527/900000000 (`_m237/_lauf900m.txt:36`).
- Front: 200M Halt `8000844C`, echter Halt bei 900M `8001684C` (`_m237/_lauf900m.txt:22`). Beide unverändert seit B233.
- B238 ist ein **B-Batch** (Strang B, B-Batch 20, Zählung ohne Grenze).
- SOLL-KOEPFE: 0. Dieser Batch baut keine Köpfe; die Median-Regel betrifft nur C-Batches.

NUTZERENTSCHEIDE (bindend, wortgetreu ins Dokument übernehmen):
- **R236-1 (2026-10-02 00:09, Option A):**
  „B238 bildet die SHARC-Antwortfolge aus dem MAME-Mitschnitt (capture/boot_20260829_194618.log) als Hybrid-Gerüst nach: gekennzeichnet "im Port durch den nativen SHARC-Code zu ersetzen", ROM-Stelle und Mitschnitt als Quelle, Gegenprobe "Gerüst aus = alter Halt 8001684C". Vorher prüfen, ob die Antworten vom gesendeten Inhalt abhängen (Prüfsumme FUN_8000c3a8). Wenn ja, die Folge nicht blind abspielen, sondern belegen, dass PPC-Daten und Mitschnitt übereinstimmen, oder die Abhängigkeit als Befund melden. Sicherung: Bewegt sich der echte Halt nach B238 und dem darauf folgenden B-Batch nicht über 8001684C hinaus, wird Strang B ausgesetzt, bis Paket E fertig ist, und die Frage kommt erneut an mich. Diese Grenze nicht durch Umdefinieren der Front umgehen.“
- **M236-3:**
  „Die Stillstandszählung in hybrid-plan.md wird je B-Batch fortgeschrieben, gemessen am ECHTEN Halt (900M-Lauf bzw. Lauf bis zum Halt) und zusätzlich an der Preflight-Front. Eine Umdefinition der Front (R600, Budget 200M/900M) setzt die Zählung nicht zurück. Der aktuelle Stand gilt als erfüllt: B233, B235 und B236 ohne Bewegung des echten Halts. Die Sicherung aus R236-1 ersetzt für die nächsten zwei B-Batches die Eskalation; danach gilt wieder die Regel "3 B-Batches still -> Frage an mich".“
- **R236-2:** Lange Aufrufe (Preflight, `port_build`, `c_kopf.py mutalle`) laufen als **blockierender** Aufruf mit `timeout=1800000`. Nicht im Hintergrund starten, keine Warteschleifen.

ARBEITSWEISE:
- Startroutine nach AGENTS.md: `git status`, Memory-Status, Mesa-Check, g++-Fassung.
- Der Harness sperrt Edit und Write unter `port/` und `scripts/`, bis der Commit `B238: Vorhersage` steht. Deshalb kommt der Vorhersage-Commit direkt nach TEIL 0. Er enthält die leere Ausgabe von `git status --porcelain port/ scripts/`.
- Die Mitschnitt-Auswertung in TEIL 1 läuft per `Select-String` oder mit einem Skript unter `scripts/` nach der Vorhersage. Keine neue `.py` unter `analysis/`.
- Einstufen nach CONFIRMED / STRONG INFERENCE / HYPOTHESIS. Belege als `Datei:Zeile@commit`.
- Jedes Urteil stützt sich auf **eine** benannte Lauf-Datei.
- Vor jedem „fehlt“ per Grep auf den Bezeichner suchen, in `analysis/`, `port/` und `capture/`.
- Jede neu zitierte M- oder R-Kennung (Kommentar oder Dokument) muss per Grep belegt sein. Ohne Beleg wird keine Kennung zitiert.

TEIL 0 – Doku (nur `analysis/`):
- `analysis/hybrid-plan.md`: STILLSTANDSZAEHLUNG fortschreiben, unter der Zeile von B229 (`:253-256`):
  - echter Halt `8001684C` (900M) still in B233, B235 und B236;
  - Preflight-Front `8000844C` (200M) still;
  - beide Nutzerentscheide wortgetreu;
  - Sicherungsfenster = **B238 und der nächste B-Batch (planmäßig B240)**.
- Ankerkopf: Offene Entscheidung (1) mit **GESCHLOSSEN** führen. Beleg: „Nutzer R236-1, 2026-10-02 00:09, Option A“.
- Grep-Beleg für beides ins Batch-Dokument `analysis/port-batch238-b-sharc-antwortfolge-2026-10-02.md`.
- Danach Commit `B238: TEIL 0`.

VORHERSAGE (eigener Commit `B238: Vorhersage`, vor jedem Diff unter `port/` oder `scripts/`):
- Je Bilanzzeile ein Sollwert und die Definition des Zählers.
- Für die B-Zeilen beide Ausgänge benennen: Halt jenseits `8001684C` **oder** Halt unverändert.
- Dazu den Hybrid-Anteil nativ (Zähler und Nenner).

TEIL 1 – Messen, bevor gebaut wird:
- a) Aus dem Mitschnitt die Folge ab `:51637` herausziehen: alle `dsp_comm_sharc_w`, dazu PPC `cgboard_dsp_comm_r/w_ppc` mit PC und Wert. Ablage: `analysis/_m238/_sharc_folge.txt`, mit Zeilenzahl je Typ und Gesamtzahl. Zum Vergleich steht in `r1b-workstream.md:15`: 22218 `dsp_comm_sharc_w`.
- b) Klassifizieren:
  - **Handschlag-Antworten**: Zähler bzw. Toggle (80/01/82/03/84 gegen PPC FF/7E/FD/7C/FB). Die Regel ableiten und angeben, ob sie vom PPC-Wert abhängt.
  - **Inhaltsabhängige Antworten**: die Prüfsumme in `FUN_8000c3a8`, dokumentiert in `bucket-c-rest-2026-09-15.md:67`. Per Ghidra die genaue ROM-Stelle für u4/u5 und die Summe angeben.
- c) Inhaltsprobe: Im Hybrid-Lauf bis 900M die Summe über die Daten bilden, die der PPC tatsächlich in den Shared-RAM schreibt (0x380×6 Wörter). Mit den u4/u5-Werten im Mitschnitt vergleichen.
  - Ergebnis „gleich“: Die Abspielfolge ist für diesen Teil belegt.
  - Ergebnis „ungleich“: als **Befund** melden. Dann ein ROM-abgeleitetes Prüfsummenmodell statt Abspielen (zulässig nach `r1b-workstream.md:135-140`).
- d) Klären, auf welche Adresse und welchen Wert die Schleife bei `8001684C` (`FUN_80016758`) wartet. Ghidra-Disassembly und Beleg.
- Wenn c) nicht messbar ist (z. B. die Daten werden im Lauf nie geschrieben): genau das mit Lauf-Datei belegen und TEIL 2 nur für den Handschlag-Teil bauen.

TEIL 2 – Hybrid-Gerüst bauen (`port/hybrid/`):
- Antwortfolge bzw. Modell nach TEIL 1, mit Schalter.
- Kommentar am Code: „Hybrid-Gerüst, im Port durch den nativen SHARC-Code zu ersetzen“, dazu die ROM-Stelle und die Zeilen im Mitschnitt.
- Gegenprobe **Gerüst aus**: 900M-Lauf mit Halt `8001684C`, gleicher End-Hash/Schrittzahl wie `_m237/_lauf900m.txt`.
- **Gerüst an**: 900M-Lauf, neuer echter Halt (PC, Grund, Art). Zusätzlich der 200M-Preflight-Front-Wert.
- Rotprobe: eine Antwort der Folge verfälschen. Der Lauf muss an der Handschlag-Stelle hängen bleiben oder abweichen (ROT), mit Lauf-Datei.
- Den Schalter erst nach grüner Gegenprobe und ROTer Rotprobe als Vorgabe einschalten.
- Ohne Umdefinition der Front: Budget 900M, die Halt-Definition bleibt unverändert.

TEIL 3 – Prüfung (2) ohne Schatten (einmal in diesem Batch):
- Lauf ohne Schatten bis zum echten Halt (mit Gerüst an).
- Funktionsmenge und Reihenfolge der ersten Eintritte gegen den Lauf mit Schatten vergleichen. Diff-Datei in `_m238/`.

TEIL 4 – Attrappen-Lesewerte:
- Die Preflight-Zeile `Hybrid-Attrappe4` soll die **tatsächlich gelesenen** Werte zeigen (distinkt, mit Anzahl), nicht den eingestellten Wert (`maschine.cpp:475,485-489@144f1f6`).
- Bevor der Preflight läuft: den neuen Zeilentext gegen alle Muster in `scripts/m149_bilanz.py:m_preflight` greppen (Teilstring-Kollision). Die Trefferliste kommt ins Dokument.
- Das gilt auch für jede andere neue oder geänderte Preflight-Zeile.

BATCH-ENDE:
- Genau ein gültiger Preflight, nach der letzten Änderung an `port/` und `scripts/`:
  `python -u scripts/preflight.py before *> analysis/_preflight_238.txt`
  Blockierend mit `timeout=1800000`.
- Bilanz mit `--write-anchor`. Abweichungen von der Vorhersage erklären.
- **B-Bericht mit beiden Zahlen:** Schritte, die die ROM ausführt, und den Anteil, den der native Kern trägt (Hybrid-Anteil nativ, 200M und 900M). Halt-PC und Wegmaß ausdrücklich als **Ersatzzahl** kennzeichnen.
- STILLSTANDSZAEHLUNG in `hybrid-plan.md` für B238 eintragen: bewegt oder nicht, echter Halt und Preflight-Front.
- Memory-Export, danach `git status` lesen. Commit.
- Ankerkopf: `**Stand:** BATCH 238`. Dazu die Grep-Zeile, die `git status --porcelain` leer nach dem Commit zeigt.

FERTIG WENN: TEIL 1 c) ist mit Ergebnis „gleich“, „ungleich (Befund)“ oder „nicht messbar mit Beleg“ dokumentiert UND die Gegenprobe „Gerüst aus = Halt 8001684C“ ist grün UND der Lauf mit Gerüst an hat einen gemessenen echten Halt (900M) UND die Rotprobe ist ROT UND die Stillstandszählung ist für B238 eingetragen UND genau ein gültiger Preflight + Bilanz liegen vor.

STREICHREIHENFOLGE: Gestrichen wird erst, wenn die Batch-Uhr die Umschaltschwelle erreicht. Unmittelbar davor kommt eine `Get-Date`-Zeile ins Dokument. Reihenfolge:
1. TEIL 4 (dann bleibt die Preflight-Zeile unverändert, Grep-Kollisionsprüfung entfällt).
2. TEIL 3.
NIE streichen: TEIL 0, Vorhersage, TEIL 1, TEIL 2 inkl. Gegenprobe und Rotprobe, Stillstandszählung, Preflight, Bilanz, Memory-Export, Ankerkopf.

## NACHRUECKLISTE
1. Doku. FERTIG WENN: `hybrid-plan.md` enthält R236-1 und M236-3 wortgetreu und die Stillstandszählung B233/B235/B236, UND die Ankerfrage (1) steht auf GESCHLOSSEN (Grep-Beleg).
2. Vorhersage. FERTIG WENN: Der Commit `B238: Vorhersage` steht vor dem ersten Diff unter `port/` oder `scripts/` und enthält die leere `git status --porcelain port/ scripts/`-Ausgabe.
3. Inhaltsabhängigkeit. FERTIG WENN: `_m238/_sharc_folge.txt` liegt vor, und das Batch-Dokument nennt das Ergebnis der Prüfsummenprobe mit ROM-Stelle und Lauf-Datei.
4. Gerüst. FERTIG WENN: Die Gegenprobe „aus“ zeigt Halt `8001684C`, der Lauf „an“ zeigt einen gemessenen Halt, die Rotprobe ist ROT – je eine Datei in `_m238/`.
5. Prüfung (2). FERTIG WENN: Die Diff-Datei Funktionsmenge/Ersteintritte ohne Schatten gegen mit Schatten liegt in `_m238/`.
6. Attrappen-Lesewerte. FERTIG WENN: Die Preflight-Zeile `Hybrid-Attrappe4` zeigt gelesene Werte, und die Grep-Kollisionsliste gegen `m_preflight` steht im Dokument.
</DS_INSTRUCTION>
