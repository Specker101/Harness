<TELEGRAM_SUMMARY>
Ergebnis: B241 hat die letzten 2 Paket-E-Köpfe gebaut, 80085408 und 800859E8. Bei beiden ergab der Vergleich mit dem ROM 0 Abweichungen, die Rotprobe war ROT. Der Cache-Abdruck deckt jetzt den ganzen Interpreter ab; ein kalter Lauf brauchte 688 s mit 0 Abweichungen. Prüfung (2) ist korrekt mit „nicht erfüllt“ beurteilt.
Bewertung: FERTIG WENN formal ja. „Paket E fertig“ stimmt aber nicht:
- Die Teilprüf-Zeile zählt nur ungebaute Köpfe und steht deshalb immer auf 0. 80085408 ist nur zu 15 von 57 Blöcken geprüft, 800660D4 zu 3 von 23.
- 15 Blöcke von 56C60 sind als „Material fehlt“ eingestuft, obwohl es eine Grenze des Prüfstands ist.
- Mein Fehler: Die A4-Zeile, die ich als Wirkung von M239-1 abgehakt hatte, zählt eine Kalibrierkonstante, keinen Messwert.
Kosten/Laufzeit: $0,32, 68 min, 219 Anfragen.
Nächster Batch: B242 (C) mit 0 neuen Köpfen: Paket E wirklich fertig prüfen, die Messfehler beheben und die ausgeführte Menge messen.
B-SCHRITT: kein B-Batch (Strang C)
M241-1: übernommen als B242 TEIL 1+2 – offen
M241-2b: übernommen als B242 TEIL 3 – offen
M241-3b: übernommen; die Ankerfrage wird neu gestellt – offen
M241-4: Harness-Sache; Taktfrage siehe unten – offen
M240-1: übernommen als B242 TEIL 1d; meine Abhakung von M239-1 nehme ich zurück – offen
M240-2: übernommen als B242 TEIL 1c/2 – offen
M240-3: übernommen als B242 TEIL 0. Die Ursache war mein eigener B240-Wortlaut – offen
M240-4b: übernommen als OFFENE FRAGE – offen
UEBERTRAG: keiner - alle Posten erledigt
ENTSCHIEDEN: Paket E gilt erst als fertig, wenn alle gebauten Köpfe 0 Blöcke ohne Begründung haben. Danach gilt dein Rahmen vom 01.10.: ausgeführte Funktionen zuerst.
OFFENE FRAGE: Strang B ruht jetzt. Soll er nach Paket E wieder anlaufen (nächster Schritt kommt einem SHARC-Modell nahe) oder ruhen? Vorschlag: ruhen.
OFFENE FRAGE: Der Audio-Rest (68K, 1808 Insn offen) kommt laut readme:48 direkt nach Paket E, dein Rahmen vom 01.10. nennt ihn nicht. Soll er sofort kommen (A) oder in die ausgeführte Menge eingereiht werden (B)? Vorschlag: B.
OFFENE FRAGE: Kontingent bei 84 %. Soll die Aussensicht bis zum 06.10. seltener laufen, und soll eine Abbruch-Marke sie nur einmal auslösen?
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: ghidra-read
program: /830d01.27p.main.bin
</DS_TOOLS>

## VERALLGEMEINERUNG

**F1 – Teilprüf-Zähler misst die falsche Menge** (`_m241/_c_paket_e.txt:130` „teilgeprueft 0“ gegen `_bahnabdeckung_preflight.txt:303/265/346`; M241-1).
(a) Fehlerklasse: Eine neue Kennzahl wird über eine Menge erhoben, in der das Gesuchte nicht vorkommen kann. Sie bestätigt sich dadurch selbst.
(b) Verwandt sind alle Abschlusszahlen einer Phase („Paket E fertig“, C-Zeile, künftig „ausgeführte Menge fertig“). Für jede neue Kennzahl verlangt die Instruktion eine **Gegenprobe mit einem bekannten Positivfall**: Die Paket-E-Zeile muss 80085408 als teilgeprüft zeigen. Zeigt sie 0, ist die Zeile falsch.
(c) Ob die Blockzählung selbst (`_bloecke`) richtig ist, wird nicht geprüft.

**F2 – Begründungsklasse falsch gewählt** („Material fehlt“ für eine Prüfstandsgrenze, `_m241/_teil3_56C60.txt:16-21`).
(a) Fehlerklasse: Eine Kategorie wird so gewählt, dass die Zahl „ohne Begründung“ auf 0 fällt.
(b) Betroffen sind alle Einträge in `analysis/_luecken_begruendet.txt` mit der Klasse „Material fehlt“. Neue Klasse „Prüfstand kann nicht erzeugen“. Jeder Eintrag „Material fehlt“ muss die fehlende Aufnahme benennen, sonst wird er umgeklassifiziert. Die Zählung kommt ins Dokument.
(c) Ob ein „unerreichbar“ wirklich unerreichbar ist, wird nur über die ROM-Stelle belegt, nicht über eine Pfadsuche.

**F3 – Mein eigener Fehler: Wirkung nicht nachgeprüft.** M239-1 habe ich als „Wirkung belegt“ geschlossen, obwohl die Zahl 1511 die Kalibrierkonstante ist (`_m240/_a4.txt:41`, `_m231/_tb_kalibrierung.txt`).
(a) Fehlerklasse: Ich habe aus dem Vorhandensein einer Zeile auf ihre Bedeutung geschlossen.
(b) Ab jetzt schließe ich einen Befund erst, wenn der Wert gegen seine Quelle gerechnet ist (Zähler-Mechanik `hybrid_lauf.cpp:1293-1297`). Die Instruktion beschriftet die Zeile richtig.
(c) Den echten Zähler aus den nicht interpretierten Schritten baut B242 nicht; das ruht mit Strang B.

**F4 – Nutzerregel ins Gegenteil verkehrt** („Strang B wird hier **nicht** ausgesetzt“, `hybrid-plan.md:294`, `r1b-workstream.md:26`; M240-3). Die Ursache ist mein B240-Auftrag („ohne Strang B selbst auszusetzen“).
(a) Fehlerklasse: Ein Auftragssatz widerspricht dem wortgetreuen Nutzerentscheid.
(b) Die Instruktion korrigiert beide Stellen (Grep `nicht\*?\*? ?ausgesetzt` danach leer). Sie hält fest: Nutzerentscheide und binäre Urteile werden nicht umformuliert.
(c) Ältere Batch-Dokumente werden nicht nachgezogen.

**Prüfpunkt a:** Das C-Ziel sind die referenzgleichen Köpfe (123). Ab B242 wird zusätzlich „davon teilgeprüft / Blöcke ohne Begründung“ über **gebaute** Köpfe ausgewiesen. B ruht.
**Prüfpunkt b:** Die ausgeführte Menge „fehlt“ wirklich: M241-2b hat per Grep keinen Treffer gefunden. Die Quellen liegen vor: `capture/ppc_coverage.bin`, `capture/ppc_cov_boot.bin` (Glob).

<DS_INSTRUCTION>
Batch 242 - Silent Scope Decomp

STAND UEBERNEHMEN:
- HEAD f2f285e, Arbeitsbaum sauber.
- Gültiger Preflight `analysis/_preflight_241.txt`. C Köpfe 123 referenzgleich.
- Paket E: alle Köpfe sind gebaut. Drei davon sind teilgeprüft:
  - `80085408`: 15/57 Blöcke, 42 ohne Begründung (`_m241/_bahnabdeckung_preflight.txt:303`);
  - `800660D4`: 3/23, die Fallrümpfe 8006612C..800662D4 sind nicht portiert (`:265`, `port/src/ckopf_leaves.cpp:4420-4442`);
  - `800859E8`: 11/12 (`:346`).
- `80056C60` hat 15 Blöcke als „Material fehlt“ eingestuft; das ist eine Prüfstandsgrenze, keine fehlende Aufnahme.
- **Strang B ruht** nach Nutzerregel R236-1.
- B242 ist ein **C-Batch (Strang C)**.
- SOLL-KOEPFE: 0. Abdeckung und Messgrundlage statt neuer Köpfe.

ARBEITSWEISE:
- Startroutine nach AGENTS.md.
- Erst `B242: Vorhersage` committen (mit leerer `git status --porcelain port/ scripts/`-Ausgabe), dann Edit und Write unter `port/` und `scripts/`.
- Preflight genau einmal am Ende. Zwischenprüfungen nur über Einzelgruppen.
- Lange Aufrufe blockierend mit `timeout=1800000`.
- Keine neue `.py` unter `analysis/`.
- **Nutzerentscheide werden wortgetreu übernommen und nicht umformuliert. Urteile nur „erfüllt“ oder „nicht erfüllt + Grund“.**
- Jede neue Kennzahl braucht eine **Gegenprobe mit einem bekannten Positivfall**: Sie muss einen Fall, von dem man weiß, dass er zählt, auch zählen.
- Einstufen nach CONFIRMED / STRONG INFERENCE / HYPOTHESIS. Belege als `Datei:Zeile@commit`.

TEIL 0 – Doku (nur `analysis/`):
- `hybrid-plan.md:294` und `r1b-workstream.md:26` korrigieren auf „Strang B ist nach Nutzerregel R236-1 ausgesetzt, bis Paket E fertig ist“. Danach muss Grep `nicht\*?\*? ?ausgesetzt` in beiden Dateien leer sein.
- Ankerkopf: „Paket E FERTIG“ ersetzen durch „Paket E gebaut; fertig erst, wenn alle gebauten Paket-E-Köpfe 0 Blöcke ohne Begründung haben (Reviewer B241)“.
- „Nächster Schritt“ auf B242 setzen.
- Offene Entscheidung: Der alte A/B-Posten zur Strang-Frage wird **GESCHLOSSEN**, Beleg: „die C-Richtung ist durch den Nutzerrahmen 01.10. beantwortet (readme.md:74-82)“. Dafür zwei neue Posten (wortgetreu):
  - „(1) Soll Strang B nach Paket E wieder anlaufen – mit dem nächsten SHARC-Schritt FUN_8000ab90 (A) – oder ruhen, bis die ausgeführte Menge fertig ist (B)? (Vorschlag: B. bei A: B baut Gerüst nahe an einem SHARC-Modell, die Front kann sich bewegen. bei B: nur C, der echte Halt bleibt 8001684C.)“
  - „(2) Soll der Audio-Rest (68K, 1808 Insn offen) laut readme.md:48 sofort nach Paket E kommen (A) oder in die ausgeführte Menge nach dem Rahmen vom 01.10. eingereiht werden (B)? (Vorschlag: B. bei A: die nächsten C-Batches bauen 68K-Köpfe. bei B: Audio kommt nach der gemessenen Reihenfolge der ausgeführten Menge.)“
- Commit `B242: TEIL 0`.

VORHERSAGE (Commit `B242: Vorhersage`):
- Je Bilanzzeile ein Sollwert mit Definition des Zählers.
- Erwartete Werte der neuen Zeilen aus TEIL 1 und TEIL 3.
- C Köpfe 123 (unverändert).

TEIL 1 – Messgrundlage:
- a) **(M241-1)** `c_kopf.py paket_e` und die C-Zeile weisen „teilgeprüft n / Blöcke ohne Begründung m“ über die **gebauten** Paket-E-Köpfe bzw. alle gebauten Köpfe aus. Gegenprobe: vor TEIL 2 muss die Zeile 80085408, 800660D4 und 800859E8 als teilgeprüft zählen.
- b) **(M241-1)** Neue Lückenklasse „Prüfstand kann nicht erzeugen“ in `_luecken_begruendet.txt` und `m210_bahnabdeckung`.
  - Jeder Eintrag „Material fehlt“ muss die fehlende Aufnahme benennen, sonst wird er umgeklassifiziert. Das gilt mindestens für die 15 Einträge von 56C60.
  - Die Bahnabdeckung führt beide Klassen getrennt. Zählung vorher/nachher im Dokument.
- c) **(M240-2)** Köpfe mit nicht portierten Blöcken innerhalb der eigenen Funktionsgrenze werden als „Rumpf offen: k Insn“ ausgewiesen, mindestens 800660D4. Diese Insn zählen in Paket E als offen.
- d) **(M240-1)** Die Preflight-Zeile `Hybrid-A4` wird beschriftet: „nativ = Kalibriersumme (B231), kein Messwert“. Dazu „Rufe ohne Kalibrierwert <n>“.
- Für jede neue oder geänderte Zeile: Grep gegen die Muster in `m149_bilanz.py:m_preflight`, Liste im Dokument.

TEIL 2 – Paket E wirklich fertig:
- Ziel je Kopf: „ohne Begründung“ = 0.
- Der Weg: Blöcke erreichen (Fälle aus `WERTE_DEF`/`RET_DEF`/MEM, wie bei 56C60) oder einzeln korrekt begründen.
- Reihenfolge:
  1. `800859E8` (1 Block);
  2. `80085408` (42 Blöcke);
  3. `800660D4`: die Fallrümpfe nativ portieren und über Fälle mit Verteilerwert erreichen. `vergl` bleibt 0, die Rotprobe auf einen Fallrumpf muss ROT werden.
- Ergebnis als `_m242/_paket_e_nachher.txt` und Bahnabdeckung.

TEIL 3 – Ausgeführte Menge messen (M241-2b; Nutzerrahmen 01.10. Punkt 2):
- Zuerst belegen, was `capture/ppc_coverage.bin` und `capture/ppc_cov_boot.bin` abdecken (Erzeuger und Phase Boot/Attract/Level 1, per Grep in `analysis/`).
- Daraus messen: Zahl der Funktionen, Insn, davon **referenzgleich** (C-Registry mit `vergl` 0) und davon teilgeprüft. Nicht „R207 gebaut“.
- Neue Preflight-Zeile `Ausgefuehrte Menge` mit Quelle und Datum der Coverage-Datei. Gegenprobe: ein bekannter Bootkopf (z. B. aus „C Koepfe live“) wird als ausgeführt gezählt.
- Die Differenz zur Hybrid-Menge A=98 in einem Satz erklären.

BATCH-ENDE:
- Preflight einmal: `python -u scripts/preflight.py before *> analysis/_preflight_242.txt`, blockierend mit `timeout=1800000`.
- Zeilendiff zu `_preflight_241`, mit Erklärung je geänderter Zeile.
- Bilanz mit `--write-anchor`. Memory-Export, Commit.
- Ankerkopf `**Stand:** BATCH 242` mit Grep-Beleg und `git status --porcelain` leer.

FERTIG WENN: Der Grep aus TEIL 0 ist leer, und beide Ankerposten stehen wortgetreu UND die Teilprüf-Zeile zählt gebaute Köpfe (Gegenprobe mit 80085408 bestanden) UND „Material fehlt“ ist nur noch mit benannter Aufnahme vergeben UND `800859E8` und `80085408` haben „ohne Begründung“ 0 UND die Zeile `Ausgefuehrte Menge` steht mit Funktionen/Insn/referenzgleich im Preflight UND genau ein gültiger Preflight + Bilanz liegen vor.

STREICHREIHENFOLGE: Gestrichen wird erst, wenn die Batch-Uhr die Umschaltschwelle erreicht. Unmittelbar davor kommt eine `Get-Date`-Zeile ins Dokument. Reihenfolge:
1. `800660D4`-Fallrümpfe (dann bleibt „Rumpf offen“ aus TEIL 1c sichtbar).
2. TEIL 1d.
NIE streichen: TEIL 0, Vorhersage, TEIL 1a/1b/1c, `800859E8`, `80085408`, TEIL 3, Preflight, Zeilendiff, Bilanz, Memory-Export, Ankerkopf.

## NACHRUECKLISTE
1. Doku. FERTIG WENN: Der Grep `nicht\*?\*? ?ausgesetzt` ist leer in `hybrid-plan.md` und `r1b-workstream.md`, der alte Posten ist GESCHLOSSEN, und die zwei neuen Posten stehen wortgetreu.
2. Vorhersage. FERTIG WENN: `B242: Vorhersage` steht vor dem ersten Diff unter `port/` oder `scripts/`.
3. Messgrundlage. FERTIG WENN: Die Paket-E- und C-Zeile zählen gebaute teilgeprüfte Köpfe (Gegenprobe im Dokument), die Klasse „Prüfstand kann nicht erzeugen“ existiert mit Zählung, und „Rumpf offen“ ist für 800660D4 ausgewiesen.
4. Zwei Köpfe. FERTIG WENN: `800859E8` und `80085408` haben „ohne Begründung“ 0, und `vergl` bleibt 0.
5. Ausgeführte Menge. FERTIG WENN: Die Preflight-Zeile `Ausgefuehrte Menge` nennt Quelle, Datum, Funktionen, Insn, referenzgleich und teilgeprüft, und die Gegenprobe ist im Dokument.
6. `800660D4`. FERTIG WENN: Die Fallrümpfe sind portiert, `vergl` ist 0, die Rotprobe auf einen Fallrumpf ist ROT, und „ohne Begründung“ ist 0.
</DS_INSTRUCTION>
