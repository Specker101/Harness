<TELEGRAM_SUMMARY>
Ergebnis: Der Preflight braucht jetzt 456 s statt 1799 s. Grund ist eine billige Maschinenkopie: FRONT 200M läuft in 70,6 s statt 1392 s, die Kopierzeit ist 0 s. Der alte und der neue Weg sind gleichwertig: gleicher End-Hash 298FA537, 80009E3C mit 2582 Rufen gleich, Rotprobe ROT. Die SHARC-Lücke (b) ist gemessen und bestimmt den Halt bei 8001684C nicht. Die Rotprobe im Lauf ohne Schatten war wirkungslos; der Worker hat das gefunden und behoben.
Bewertung: FERTIG WENN erreicht: ja, alle 5 Posten sind belegt. Drei Mängel:
- (1) SHARC-Antwort „nicht schließbar“ ist falsch. Der MAME-Mitschnitt enthält 22218 SHARC-Antworten (capture/boot_20260829_194618.log:51637ff), ich habe das nachgeprüft.
- (2) Die Preflight-Zeile Attrappe4 meldet „Werte 00800000“. Gelesen wird aber der eigene Schreibwert (maschine.cpp:485-511), die Zeile gibt also den eingestellten Wert aus und misst nichts.
- (3) Die A4-Zahl stammt aus dem 10M-Lauf, der Hash aus dem 20M-Lauf.
Außerdem wurde R391 zum dritten Mal verletzt (port/ vor der Vorhersage).
Kosten/Laufzeit: $0.21, 2h01m, 167 Anfragen. Fester Aufwand 44 %: 3 Preflight-Läufe, einer davon ein Fehllauf.
Nächster Batch: B237 ist ein C-Batch, Paket E inkl. 800660D4.
B-SCHRITT: 4/5 Boot bis Hauptschleife, B-Batch 19 von max 20 (Grenze aufgehoben, nur Zählung)
UEBERTRAG: Prüfung (2) ohne Schatten bis zum echten Halt + A4 -> B238
UEBERTRAG: SHARC-Antwort aus dem Mitschnitt -> B238
ENTSCHIEDEN: SOLL-KOEPFE 4 (Median nicht gemessen)
ENTSCHIEDEN: Prüfkriterium des Nutzers (22:12) ersetzt das Hash- und Zeitbasis-Urteil
M236-1: übernommen -> B237 TEIL 0 Doku, Modell in B238 -> offen
M236-2: übernommen als OFFENE FRAGE -> offen
M236-4: übernommen, A4-Messung in B238 statt im Preflight (Nutzerentscheid) -> offen
M236-5: übernommen als B237 TEIL 2 -> offen
M236-6: übernommen (Leer-Beleg vor der Vorhersage), Hook-Sperre ist Nutzersache -> offen
M236-7: übernommen, Stillstand gilt trotzdem (2973→2974), die Harness-Ausnahme ist Nutzersache -> offen
M234-5: übernommen - Wirkung belegt: f1_sharc_luecken.txt:79-84 (141 Schreibzugriffe, 0 mit Bit 31) übernommen
M233-4, M234-3: abgelehnt, Grund: Nutzerentscheid 01.10. 22:12 stellt R593/R596 zurück
OFFENE FRAGE: Die Front steht seit B233 still. B weiter im Wechsel 1:1 mit SHARC-Antwort aus dem Mitschnitt (Vorschlag) oder B aussetzen bis Paket E fertig?
OFFENE FRAGE: Preflight jetzt 456 s, die 60-min-Grenze kann zurückgebaut werden.
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: ghidra-read
program: /830d01.27p.main.bin
</DS_TOOLS>

## VERALLGEMEINERUNG
**F1: „SHARC-Antwort mit vorhandenem Material nicht schließbar“ (`_m236/f1_sharc_luecken.txt:75-76@144f1f6`). Der Mitschnitt `capture/boot_20260829_194618.log` enthält 22218 `dsp_comm_sharc_w`-Zeilen (geprüft).**
- (a) Fehlerklasse: Eine Fehlstelle wird behauptet, ohne nach dem Bezeichner zu suchen. Das ist der vierte Fall, und die Suche schloss `capture/` nicht ein. Auch mein Prüfpunkt b suchte bisher nur in `analysis/` und `port/`.
- (b) Jede Aussage „fehlt“ oder „nicht belegt“ braucht ab jetzt einen Grep auf den Bezeichner über `analysis/`, `port/` **und** `capture/`, mit Fundstelle oder „nicht gefunden“. B237 TEIL 0 korrigiert die Aussage im Anker.
- (c) Ob die Antwortfolge aus dem Mitschnitt die Front bewegt, misst erst B238.

**F2: Die Preflight-Zeile `Hybrid-Attrappe4 … Werte 00800000` gibt den eingestellten Wert aus. Das ROM liest aber seinen eigenen Schreibwert (`port/hybrid/maschine.cpp:485-511@144f1f6`).**
- (a) Fehlerklasse: Eine Zeile druckt Konfiguration statt Messung. Seit wann, ist offen; `_m220/_attr4_vergleich.txt` („unverändert mit 0 und 0x800000“) passt zu „nie wirksam“ (HYPOTHESIS).
- (b) Verwandt sind alle Attrappen-Zeilen im Preflight (SPU, Attrappe4) und der Kopf von `_hybrid.txt` mit den 9 Attrappen. B237 TEIL 0 dokumentiert den Befund. B238 vergleicht je Attrappe den gemeldeten mit dem tatsächlich gelesenen Wert.
- (c) In B237 wird kein Code geändert.

**F3: Die Ankerzeile „ohne Schatten referenzgleich, A4 99,99962 %“ setzt zwei Läufe zusammen (10M für A4, 20M für den Hash, Kopfsatz 8 gegen 193 Rufe).**
- (a) Fehlerklasse: Ein Urteil wird aus Zahlen verschiedener Läufe gebildet.
- (b) Jedes Urteil nennt genau eine Lauf-Datei. B237 TEIL 0 begrenzt die Ankerzeile. Die gültige Prüfung ist Kriterium (2) des Nutzers in B238.
- (c) Prüfung (2) selbst findet erst in B238 statt.

**F4: R391 zum dritten Mal verletzt (B228, B230, B236).**
- (a) Fehlerklasse: Die Reihenfolge-Regel wird nur nachträglich geprüft.
- (b) Der Vorhersage-Commit muss die Ausgabe `git status --porcelain port/ scripts/` (leer) enthalten. Ein Wächter im Hook ist Harness-Sache.
- (c) Eine technische Sperre gibt es nicht.

<DS_INSTRUCTION>
Batch 237 - Silent Scope Decomp

Strang C, C-Batch Paket E, B-Batch-Zählung bleibt bei 19.
SOLL-KOEPFE: 4

STAND UEBERNEHMEN:
- HEAD 144f1f6. Gültiger Preflight: `analysis/_preflight_236.txt` (456 s). Er hat einen benannten Befund, R391 (iii). Sonst gilt: C Köpfe 115 / 6475 / 0, Hybrid-Funktionen nativ 7/94.
- B236 hat die billige Maschinenkopie gebaut; FRONT 200M läuft in 70,6 s (`_m236/f1_front.txt`).
- Paket E: Laut Anker sind 12 Köpfe / 1024 Insn offen, kleinste Blätter: 8003C254 (14), 8005B33C (20), 8005B38C (21), 800660D4 (133). Das ist nicht frisch gemessen. Zuerst `python -u scripts/c_kopf.py paket_e` fahren und die Ausgabe nach `_m237/_paket_e_vorher.txt` schreiben.

ARBEITSWEISE:
- Startroutine nach AGENTS.md.
- Lange Aufrufe (Preflight, `port_build`, `c_kopf.py mutalle`) laufen blockierend mit `timeout=3600000`. Nicht im Hintergrund, keine Warteschleifen.
- Einstufung jeder Aussage: CONFIRMED, STRONG INFERENCE oder HYPOTHESIS. Fundstellen als `Datei:Zeile@commit`. Belege unter `analysis/_m237/`.
- Regel „fehlt“: Jede Aussage „fehlt“, „nicht belegt“ oder „nicht schließbar“ braucht einen Grep auf den Bezeichner (Adresse oder Symbol) über `analysis/`, `port/` UND `capture/`. Nenne die Fundstelle oder schreibe „nicht gefunden (Grep "<x>")“.
- Ein Urteil nennt genau EINE Lauf-Datei. Zahlen aus verschiedenen Läufen werden nicht zu einem Urteil zusammengesetzt.
- Messziel C sind referenzgleiche Köpfe: `vergl` mit 0 Abweichungen UND eine ROT gewordene Rotprobe (`mut`) je neuem Kopf. Folgende Zahlen sind ERSATZZAHLEN und werden so beschriftet: „Paket E offen“, „C Einbindung“, Bahnabdeckung, die Live-Zeile aus TEIL 2.

TEIL 0 (nur Doku, ein Commit, VOR der Vorhersage):
- Trage den Nutzerentscheid vom 2026-10-01 22:12 UTC wortgetreu in `analysis/hybrid-plan.md` ein und als eine Zeile im Ankerkopf. Inhalt: Ein bitgleicher Hash ohne Schatten ist kein Pflichtkriterium. Referenzbeweis sind (1) KOPFWEIT/B/A und (2) ein Lauf ohne Schatten mit gleichem Kopfsatz, der denselben ECHTEN Halt erreicht, mit gleicher Funktionsmenge und gleicher Reihenfolge der ERSTEN Eintritte. Prüfung (2) läuft einmal je B-Batch, nicht im Preflight. R593/R596 ruhen.
- Ankerkorrektur 1: Die Zeile „ohne Schatten referenzgleich (End-Hash 2AA9ECE1, A4 99,99962 %)“ wird ersetzt durch „10M: gleicher Kopfsatz, 1 Kopf/38 Schritte; 20M: Hash gleich bei 8 vs 193 Rufen - Kriterium (2) noch NICHT geprüft (B238)“.
- Ankerkorrektur 2: Die SHARC-Lücke (a) heißt jetzt „Antwortfolge im MAME-Mitschnitt vorhanden (`capture/boot_20260829_194618.log:51637-51656`, `dsp_comm_sharc_w`, Grep-Zahl selbst messen), Modell nicht gebaut“. Die alte Aussage in `_m236/f1_sharc_luecken.txt` bleibt unverändert stehen.
- Befund ins Batch-Dokument: Die Preflight-Zeile `Hybrid-Attrappe4 … Werte 00800000` gibt den eingestellten Wert aus. Das ROM liest seinen eigenen Schreibwert (`port/hybrid/maschine.cpp:485-511@144f1f6`). Einstufung CONFIRMED für heute; „seit wann“ ist HYPOTHESIS. In diesem Batch keinen Code dazu ändern.
- „Offene Entscheidung:“ im Ankerkopf bekommt diesen Wortlaut: „(1) Die Front steht seit B233 am SHARC-Handschlag 8001684C. Soll Strang B im Wechsel 1:1 weiterlaufen und als Nächstes die SHARC-Antwort aus dem MAME-Mitschnitt nachbilden (A), oder ausgesetzt werden, bis Paket E fertig ist (B)? (Vorschlag: A. bei A: B238 baut die Antwortfolge als Hybrid-Gerüst, die Front kann sich bewegen. bei B: nur C-Batches, die Front bleibt stehen.)“

TEIL 1 - Vorhersage (R391, eigener Commit `B237: Vorhersage`):
- Davor `git status --porcelain port/ scripts/` fahren. Die Ausgabe muss leer sein und kommt wörtlich ins Dokument.
- Sollwerte je Bilanzzeile mit Zählerdefinition. C Köpfe Soll 119/>6475/0. Hybrid-Zeilen unverändert zu `_preflight_236.txt:24-29`, außer wenn ein neuer Kopf im Bootpfad liegt; dann wird das vorhergesagt.
- Erst danach dürfen Dateien unter port/ oder scripts/ geändert werden.

TEIL 2 - Neue Preflight-Zeile direkt unter `C Koepfe`. Nur Anzeige, die Messung bleibt dieselbe; das ist die Begründung für die Skriptänderung im C-Batch:
- Format: `C Koepfe live    <n>/115 live verglichen gleich (Hybrid-Lauf 200M)`. Die Zahl stammt aus dem vorhandenen Hybrid-Lauf („verglichen gleich“).
- Die Zeile `C Koepfe` selbst bleibt unverändert, damit der Parser sie weiter liest.

TEIL 3 - Paket-E-Köpfe:
- 800660D4 plus die drei kleinsten offenen Blätter laut frischer `paket_e`-Liste.
- Je Kopf: `vergl` mit 0 Abweichungen, `mut` ROT (Ausgabe in `_m237/`), Bahnabdeckung.
- `_m237/_paket_e_nachher.txt` mit offener Zahl und Insn.

TEIL 4 - Live-Lage der neuen Köpfe:
- Je neuem Kopf ein Grep im 200M-Lauf und im 900M-Lauf (`--nativ-weiter`, jetzt ca. 70 s bzw. 175 s).
- Ergebnis je Kopf: entweder eine KOPFWEIT-Zeile oder „im Lauf nicht ausgeführt“ mit der Lauf-Datei.

BATCH-ENDE:
- Preflight einmal, nach der letzten Änderung an port/ und scripts/: `python -u scripts/preflight.py before *> analysis/_preflight_237.txt` (blockierend).
- Bilanz mit `--write-anchor`.
- Ankerkopf: `**Stand:** BATCH 237`, „Naechster Schritt: B238 = B-Batch: SHARC-Antwortfolge aus dem Mitschnitt + Prüfung (2) ohne Schatten bis zum echten Halt + Attrappen-Lesewerte“. Dazu ein Grep-Beleg.
- Memory-Export.
- `git status --porcelain` leer, die Ausgabe steht im Batch-Dokument.
- Commit.

FERTIG WENN: mindestens 2 neue Köpfe (darunter 800660D4) mit vergl 0 und mut ROT; `C Koepfe` ≥ 117; die neue Zeile `C Koepfe live` steht im Preflight; genau ein gültiger Preflight ohne R391-Befund; Bilanz geschrieben; Ankerkopf BATCH 237 mit den beiden Korrekturen aus TEIL 0.

STREICHREIHENFOLGE: Gestrichen wird erst, wenn die Batch-Uhr die Umschaltschwelle erreicht. Unmittelbar davor kommt eine `Get-Date`-Zeile ins Dokument. Reihenfolge:
1. TEIL 4.
2. Köpfe über 2 hinaus.
NIE streichen: TEIL 0, TEIL 1, TEIL 2, 800660D4, Preflight, Bilanz, Memory-Export, Ankerkopf, git-status-Zeile.

## NACHRUECKLISTE
1. Doku und Nutzerentscheid. FERTIG WENN: `hybrid-plan.md` enthält den Entscheid 22:12 wortgetreu, und der Ankerkopf trägt Korrektur 1, Korrektur 2 und die Offene Entscheidung (1) im A/B-Format (Grep-Beleg).
2. Vorhersage. FERTIG WENN: Der Commit `B237: Vorhersage` steht vor dem ersten port/- oder scripts/-Diff und enthält die leere `git status --porcelain port/ scripts/`-Ausgabe.
3. 800660D4. FERTIG WENN: `vergl` hat 0 Abweichungen und `mut` ist ROT, beide Ausgaben liegen in `_m237/`.
4. Weitere Köpfe. FERTIG WENN: Insgesamt 4 neue Köpfe haben `vergl` 0 und `mut` ROT, und `_m237/_paket_e_nachher.txt` liegt vor.
5. Preflight und Bilanz. FERTIG WENN: `_preflight_237.txt` hat die Zeile `C Koepfe live`, es gibt keinen R391-Befund, und die Bilanz ist geschrieben.
6. Live-Lage. FERTIG WENN: Je neuem Kopf gibt es eine KOPFWEIT-Zeile oder die Aussage „nicht ausgeführt“, jeweils mit Lauf-Datei.
</DS_INSTRUCTION>
