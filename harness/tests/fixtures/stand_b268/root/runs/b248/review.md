<TELEGRAM_SUMMARY>
Ergebnis: B247 hat einen Fehler gefunden, der seit B242 in der Abdeckungskarte stand: Die Karte wurde mit Index = Wort statt Index = Byte gelesen (geprüft an `m242_ausgefuehrt.py:128` und `hybrid_lauf.cpp:140`). Ausgeführte Menge nach der Korrektur: 1081 Spannen, 91 referenzgleich. Die Fallrümpfe von 660D4 liefen nicht (0/100). Cache je Kopf eingebaut: 6 neu, 134 unverändert. Sechs neue Köpfe, zusammen nur 14 Insn.
Bewertung: FERTIG WENN erreicht: ja – alle sechs Posten belegt, Preflight SAUBER. Mängel: Die Köpfe sind fast leer (je 1–3 Insn). Der Preflight brauchte 1446 s, davon 703 s für den kalten Profil-Cache. `m209_boot_zensus.py:99` hat denselben Indexfehler und ist noch offen.
Referenzgleiche Insn je C-Batch: B246 18, B247 14.
Kosten/Laufzeit: $0,16, 2 h 07 min, 121 Anfragen.
Nächster Batch: B248 ist der erste von 3 B-Batches. Ziel: aus ROM und MAME ein Antwortmodell für die PCI-ID-Prüfung (`FUN_8000ab90`) bauen.
B-SCHRITT: kein B-Batch (Strang C)
UEBERTRAG: keiner – alle Posten erledigt (Indexfehler in `m209` -> B248 TEIL 4)
ENTSCHIEDEN: Die Nutzer-Antwort „Option A mit harter Zwischenprüfung“ wird umgesetzt. B248–B250 sind B-Batches. Bewegt sich der Halt-PC danach nicht über 8001684C hinaus, folgt C ohne Rückfrage.
ENTSCHIEDEN: Der A/B-Posten im Anker wird als GESCHLOSSEN geführt (Nutzerentscheid vom 02.10.).
ENTSCHIEDEN: Der Zuschnitt der C-Batches richtet sich ab jetzt nach referenzgleichen Insn: mindestens 150, Ziel etwa 200. Die Kopfzahl ist nur Nebenzahl. Das wird im Anker festgehalten.
ENTSCHIEDEN: Der Halt zählt nur als bewegt, wenn sich der Halt-PC in der Preflight-Zeile `Hybrid-A4` mit unveränderten Schaltern ändert. Die erreichte Selbsttest-Stufe wird nur als Ersatzzahl geführt.
ENTSCHIEDEN: Profil bleibt ghidra-read. Den Wunsch nach `read_memory` lehne ich ab: Die Rohwörter liest der Worker offline aus dem ROM-Abbild (Regel R398).
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: ghidra-read
program: /830d01.27p.main.bin
</DS_TOOLS>

## VERALLGEMEINERUNG

**Befund 1: Abdeckungskarte mit falschem Index gelesen (M247-1).**
- (a) Fehlerklasse: Eine Karte wird mit einer falschen Einheit indiziert (Wort statt Byte). Die Zahl sieht trotzdem glaubwürdig aus, weil kein Wert aus dem Bereich fällt.
- (b) Verwandte Fälle: jedes Skript, das `ppc_coverage.bin` oder `ppc_cov_boot.bin` liest. `m209_boot_zensus.py:99` hat den Fehler nachweislich. TEIL 4 lässt mit Grep alle Leser dieser Karten auflisten, je Leser die Indexformel mit `Datei:Zeile` und den Grenztest aus B247: Anteil der gesetzten Indizes außerhalb des Abbilds, Sollwert 0 %.
- (c) Nicht geprüft: welche älteren Zahlen in Anker oder Batch-Dokumenten aus `m209` stammen. Das wird nur benannt, nicht nachgerechnet.

**Befund 2: Kopfzahl als Zuschnitt erzeugt fast leere Köpfe (14 bzw. 18 Insn je Batch).**
- (a) Fehlerklasse: Die Ersatzzahl wird zum Ziel. Gezählt werden Köpfe, gemeint ist referenzgleicher Code.
- (b) Der Nutzer hat das per Vorgabe korrigiert. Ab dem nächsten C-Batch steht als Ziel die Summe referenzgleicher Insn, die Kopfzahl ist nur Nebenzahl. Dieselbe Gefahr besteht im B-Strang: Eine erreichte Selbsttest-Stufe ist nicht der Halt-PC. Die Instruktion verlangt deshalb beide Zahlen, die Stufe ausdrücklich als Ersatzzahl.
- (c) Ob eine einzelne Prüfung (`vergl` 0) bei Köpfen mit 1 Insn überhaupt etwas aussagt, wird nicht geprüft.

**Befund 3: Preflight dauerte 1446 s, davon 703 s für den kalten Profil-Cache.**
- (a) Fehlerklasse: Ein Cache hängt an einer Prüfsumme, die ein anderer Umbau ungültig macht. Die Folge sind stille Kaltläufe nahe an der 30-min-Grenze.
- (b) Die Instruktion lässt die Dauer jeder Preflight-Gruppe aufschreiben. Liegt der Preflight über 900 s, wird die Ursache je Gruppe benannt.
- (c) In B248 wird nichts am Cache umgebaut, weil es ein B-Batch ist.

<DS_INSTRUCTION>
Batch 248 - Silent Scope Decomp

Strang B, B-Batch 23 (B-SCHRITT 4/5 „Boot bis Hauptschleife“). Erster von DREI B-Batches der harten Zwischenprüfung (Nutzerentscheid 02.10.2026).
SOLL-KOEPFE: 0 (B-Batch, kein Kopfbau)

STAND UEBERNEHMEN:
- HEAD 95c726a, Baum sauber. Gültiger Preflight `_preflight_247.txt` (SAUBER). C Köpfe 139/7748/0. Ausgeführte Menge korrigiert (M247-1, Index = adresse − 0x80000000).
- Letzter Hybrid-Stand: `Hybrid-A4 655951355 | davon nativ 1511 | Halt-PC 8001684C`. Zahlen aus `_preflight_247.txt` übernehmen und mit Zeile zitieren.
- Der Halt 8001684C ist das Fehlerende des Frame-Treibers `FUN_80016758`: Der Selbsttest `FUN_8000be40` gibt 5 zurück, weil Stufe 5 `FUN_8000ab90` mit 0x10000001 endet. Quellen: `analysis/port-batch245-b-sharc-ankopplung-2026-10-02.md:106-124@95c726a` und `analysis/_m245/_wegtafel.txt:25-37@95c726a`.
- `FUN_8000ab90` liest über die Proxys `FUN_8000c2b4` (Kommando 0x0F) und `FUN_8000c30c` (Kommando 0x0E) den PCI-Config-Raum des K033906 (Busadresse 0x3500000). Erwartet werden:
  - Reg 0x00 = 0x0001121A oder 0x0002121A,
  - Reg 0x02 = 0x0400,
  - Reg 0x04 = 0xFF000000 nach dem Schreiben von 0xFFFFFFFF,
  - bei Typ 1 ein Sweep über Reg 0x04 und 0x0F.
  Quelle: `analysis/bucket-c-rest-2026-09-15.md:208-252@95c726a`. MAME: `mame/mame/src/devices/machine/k033906.cpp:28,57-61,74-113`.
- NUTZERENTSCHEID (02.10., bindend), wörtlich ins Batch-Dokument übernehmen:
  - Nach B247 folgen 3 B-Batches (B248, B249, B250).
  - Ziel: Der echte Halt kommt über 8001684C hinaus, zuerst über ein ROM- und MAME-belegtes Modell der PCI-ID-Prüfung.
  - Bewegt sich der Halt nach B250 nicht, geht es ohne weitere Frage zurück zu C. B ruht dann bis zum Ende der ausgeführten Menge.
  - Bewegt er sich, kommt ein Plan bis zum ersten Attract-Bild als Frage an den Nutzer.
  - „Den Halt nicht umdefinieren.“
- ZWEITER NUTZERENTSCHEID (C-Zuschnitt, gilt ab dem nächsten C-Batch): Ziel je C-Batch ist die Summe neuer referenzgleicher Insn, Soll mindestens 150, Ziel etwa 200. Die Kopfzahl ist Nebenzahl. Köpfe unter 10 Insn gibt es nur als Beifang. In B248 wird das nur im Anker festgehalten, nicht angewendet.

ARBEITSWEISE:
- Startroutine nach `AGENTS.md`: `git status`, Memory-Status, Mesa-Prüfung, g++-Fassung.
- Vorhersage-Commit `B248: Vorhersage` VOR der ersten Änderung unter `port/`. Er nennt für jede Bilanzzeile Sollwert und Zählerdefinition, insbesondere:
  - `Hybrid-A4`: Schritte, nativ, Halt-PC,
  - Rückgabewert von `FUN_8000ab90`,
  - Rückgabewert und Stufe von `FUN_8000be40`.
- „Halt bewegt“ heißt genau: Der Halt-PC in der Preflight-Zeile `Hybrid-A4` ist ungleich 8001684C, gemessen mit DENSELBEN Schaltern wie in `_preflight_247.txt`.
  - Die Schalterliste vorher und nachher wird ins Dokument geschrieben.
  - Das neue Modell darf in diesem Standardpfad eingeschaltet sein, wenn es ROM- und MAME-belegt ist. Es braucht dann einen Aus-Schalter und eine Rotprobe.
  - Eine erreichte Selbsttest-Stufe ist eine ERSATZZAHL und wird so beschriftet. Sie ist nie „Halt bewegt“.
- Strang-B-Maß (Entscheidung A4): Der Bericht nennt BEIDE Zahlen, also die ausgeführten Schritte der ROM und den Anteil, den der native Kern davon trägt.
- Jedes neue Modell wird im Code mit „Hybrid-Geruest, im Port zu ersetzen“ markiert. Jede Antwort im Modell nennt ihre Quelle mit `Datei:Zeile`: die ROM-Adresse des Lesers und die MAME-Zeile des Werts.
- Die SHARC-Seite der Kommandos 0x0E/0x0F ist nicht analysiert. Wo eine Antwort im Shared-RAM landet, wird deshalb aus der PPC-Leseseite abgeleitet und als STRONG INFERENCE eingestuft, nicht als CONFIRMED.
- Rohwörter: `disassemble_function`/`decompile_function` auf bestehenden Funktionen oder ein Offline-Dekoder auf dem ROM-Abbild. `read_memory` steht nicht zur Verfügung und wird nicht gebraucht. `/disassemble_bytes` ist verboten (R398).
- „Fehlt“ oder „Blocker“ nur mit Grep auf den Bezeichner (Adresse oder Symbol) über `analysis/` und `port/`, mit Fundstelle oder „gesucht, nicht gefunden (Grep …)“.
- Preflight, `port_build` und `c_kopf.py`-Läufe als normalen blockierenden Aufruf mit `timeout=1800000`, nie im Hintergrund.

TEIL 1 - Proxy-Protokoll aus dem ROM lesen (Spezifikation des Modells):
- Disassembly von `FUN_8000c2b4`, `FUN_8000c30c`, `FUN_8000b51c` und `FUN_8000b484`.
- Tafel in `analysis/_m248/_proxy_protokoll.txt` mit je einer Zeile pro Zugriff:
  - welche Shared-RAM-Adresse bzw. welches Register an 0x780C0000 geschrieben oder gelesen wird,
  - welches Kommando,
  - auf welche Quittung gewartet wird,
  - wo der Rückgabewert gelesen wird (0x78000004/06?),
  - wie viele Versuche bzw. welches Timeout.
- Abgleich mit dem vorhandenen Lese-Modell (`--sharc-antwort`, `port/hybrid/maschine.cpp` und `sharc_folge.inc`): Wie beantwortet es heute ein Kommando 0x0E? Messung im Hybrid-Trace bis zur Rückkehr von ab90: Folge der Proxy-Aufrufe und an welchem Vergleich 0x10000001 entsteht.
- Ergebnis-Einstufung je Zeile: CONFIRMED, STRONG INFERENCE oder HYPOTHESIS.

TEIL 2 - Modell des K033906-PCI-Config-Raums im Hybrid:
- Kleines Registerfeld nach MAME `k033906.cpp`:
  - Reg 0x00 = 0x0001121A (Voodoo 1; Silent Scope 1 ist Typ 1, Beleg aus `mame/…/hornet.cpp` zitieren),
  - Reg 0x02 = 0x04000000,
  - Reg 0x04 nach der Schreibregel `k033906.cpp:80-90`,
  - Reg 0x0F, 0x10, 0x11, 0x12, 0x14, 0x38 wie in MAME.
- Angesprochen wird es über das Proxy-Protokoll aus TEIL 1.
- Schalter `--k033906-aus` (Modell aus) und `--k033906-rot` (Reg 0x00 falsch, z. B. 0x0003121A).
- Messung je Lauf, mit demselben Schaltersatz wie der Preflight, in `analysis/_m248/_ab90_an.txt`, `_ab90_aus.txt` und `_ab90_rot.txt`:
  - Rückgabe von ab90,
  - Rückgabe und Stufe von be40,
  - Halt-PC,
  - Schritte und nativer Anteil.
- Sollwerte:
  - aus/rot: ab90 = 0x10000001, Halt 8001684C,
  - an: ab90 ≠ 0x10000001.
  Bleibt ab90 fehlerhaft, wird der neue Fehlercode samt Stelle benannt (0x1000000x je Stufe laut bucket-c §5.5).

TEIL 3 - Nächste Stufen, nur wenn ab90 in TEIL 2 durchkommt:
- Was nach ab90 als Nächstes scheitert, wird gemessen, nicht vermutet. Erwartet ist `FUN_8000ab0c` mit Zugriffen auf 0x2480000–0x2480093.
- Jede Leseadresse dort wird einem Voodoo-Register zugeordnet (`mame/…/voodoo*.cpp`, Zeile).
- Antworten nur ergänzen, wenn sie MAME-belegt sind, je Zusatz mit Rotprobe. Tafel `analysis/_m248/_stufen_nach_ab90.txt`.
- Ziel des Batches bleibt die Halt-PC-Messung. Erreicht be40 die Rückgabe 0 und der Frame-Treiber läuft weiter, wird der neue Halt-PC mit Art (Schleife, MMIO, Trap) und Disassembly benannt.

TEIL 4 - Fehlerklasse M247-1 einmal vollständig prüfen (nur messen, kleine Korrektur):
- Grep über `scripts/` und `port/` nach Lesern von `ppc_coverage.bin`, `ppc_cov_boot.bin` und SSCOV1. Je Leser eine Zeile mit `Datei:Zeile@HEAD` und Indexformel in `analysis/_m248/_coverage_leser.txt`.
- `m209_boot_zensus.py:99` auf `adresse − 0x80000000` umstellen. Nachweis mit Grenztest: Anteil der gesetzten Indizes außerhalb des Abbilds vorher und nachher, Soll nachher 0 %.
- Benennen, ob eine Preflight- oder Bilanzzeile aus `m209` gespeist wird. Wenn ja, steht das Delta in der Vorhersage.

TEIL 5 - Abschluss:
- Genau ein gültiger Preflight (`analysis/_preflight_248.txt`), danach die Bilanz (`m149_bilanz.py --batch 248 … --write-anchor`). Die Dauer jeder Preflight-Gruppe kommt aus dem Preflight-Kopf ins Dokument. Über 900 s gesamt: Ursache je Gruppe benennen.
- Memory-Export, dann Commit.
- Ankerkopf:
  - Stand B248 (B-Batch 1 von 3 der Zwischenprüfung), Halt-PC vorher und nachher, A4-Zahlen.
  - Unter „Offene Entscheidung“ den A/B-Posten mit dem Wort GESCHLOSSEN führen: „Nutzerentscheid 02.10.2026: Option A mit harter Zwischenprüfung über B248–B250; ohne Halt-Bewegung zurück zu C“.
  - Unter „Fallstricke/Regeln“ die neue C-Regel: Insn-Soll ≥150, Ziel ~200, Kopfzahl nur Nebenzahl, Köpfe <10 Insn nur Beifang.
  - Zeile „Zwischenprüfung: B248 [Ergebnis], B249 offen, B250 offen“.
- Für jede eigene Entscheidung `ENTSCHEIDUNG (Reviewer): …` ins Batch-Dokument.

FERTIG WENN: `_proxy_protokoll.txt` liegt vor + Modell gebaut + Rotprobe (aus/rot → ab90 = 0x10000001, Halt 8001684C) und An-Lauf gemessen, mit Halt-PC und beiden A4-Zahlen im Dokument + `_coverage_leser.txt` mit `m209` korrigiert + genau EIN gültiger Preflight + Bilanz + Ankerkopf mit GESCHLOSSEN-Posten und Zwischenprüfungszeile.

STREICHREIHENFOLGE:
- Gestrichen wird erst, wenn die Batch-Uhr die Umschaltschwelle erreicht hat, mit einer unmittelbar davor gemessenen `Get-Date`-Zeile im Dokument.
- Reihenfolge:
  1. TEIL 3 über die erste gemessene Folgestufe hinaus
  2. TEIL 4 Korrektur von `m209` (die Leserliste bleibt)
  3. TEIL 3 ganz
- NIE: TEIL 1, TEIL 2 samt Rotprobe, Vorhersage-Commit, Preflight, Bilanz, Memory-Export, Ankerkopf.

## NACHRUECKLISTE
1. Proxy-Protokoll. FERTIG WENN: `_m248/_proxy_protokoll.txt` mit ROM-Belegen je Zugriff und Einstufung liegt vor.
2. K033906-Modell. FERTIG WENN: `_ab90_an/aus/rot.txt` liegen vor; aus/rot zeigen 0x10000001 und 8001684C; an nennt die Rückgabe von ab90, be40-Stufe, Halt-PC, Schritte und nativen Anteil.
3. Abschluss. FERTIG WENN: gültiger `_preflight_248.txt` + `_m248/_bilanz.txt` + Ankerkopf mit GESCHLOSSEN-Posten, C-Insn-Regel und Zwischenprüfungszeile.
4. Coverage-Leser. FERTIG WENN: `_m248/_coverage_leser.txt` listet alle Leser mit Indexformel; `m209` ist korrigiert mit Grenztest 0 %.
5. Folgestufe. FERTIG WENN: `_m248/_stufen_nach_ab90.txt` nennt die nächste scheiternde Stufe mit Adresse und MAME-Zuordnung je Leseadresse (nur wenn ab90 durchkommt; sonst „nicht erreicht“ mit Beleg).
</DS_INSTRUCTION>
