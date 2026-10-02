<TELEGRAM_SUMMARY>
Ergebnis: B239 (C-Batch) hat die beiden letzten Paket-E-Blätter gebaut: 80085824 (113 Insn) und 80056C60 (432 Insn). Bei beiden ergab der ROM-Vergleich 0 Abweichungen, die Rotprobe war ROT; nachgeprüft bei 56C60 (79 Abweichungen mit Mutation). Die referenzgleichen Köpfe stehen jetzt bei 121/7044/0. Die 605 s des Profil-Laufs sind ein Dauerkosten-Effekt: jeder Batch hat den Cache kalt neu gebaut. Der Cache bleibt jetzt erhalten, der Preflight braucht 520 s. Nebenbei hat der Batch die fehlende Anweisung `mcrf` im Wortinterpreter ergänzt.
Bewertung: gut. FERTIG WENN erreicht: ja. Befunde: 4 Preflight-Läufe, davon 2 als Testlauf; 56C60 ist nur zu 44 von 85 Blöcken geprüft; der Cache-Abdruck deckt den Interpreter nicht ab.
Kosten/Laufzeit: $0,26, 1h32m, 163 Anfragen.
Nächster Batch: B240 = B-Batch, der letzte im Sicherungsfenster. Bewegt sich der echte Halt 8001684C nicht, kommt die Frage zum Aussetzen von Strang B an dich.
B-SCHRITT: kein B-Batch (Strang C)
M239-1: übernommen als B240 TEIL 4 – Wirkung noch nicht belegt -> bleibt offen
M239-2: Mein Teil ist übernommen: ich zähle am echten Halt und entscheide nach B240 daran; die Änderung am Harness-Melder liegt bei dir (siehe OFFENE FRAGE) – offen
M239-3: übernommen als B241 (teilgeprüfte Köpfe getrennt ausweisen) – Wirkung noch nicht belegt -> bleibt offen
M239-4: übernommen als B241 (ganzer Interpreter in den Abdruck, ein kalter Lauf) – offen
M239-5: übernommen: Reviews schlank, Taktfrage an dich – offen
M239-6: übernommen als B240-Regel (Zwischenprüfungen über Einzelgruppen) – offen
UEBERTRAG: keiner - alle Posten erledigt
ENTSCHIEDEN: In B241 wird Paket E fertig: zwei echte Köpfe, darunter 80085408, plus die 41 offenen Blöcke von 56C60.
OFFENE FRAGE: Wochenkontingent bei 81 %, Reset am 06.10. Soll die Aussensicht bis dahin nur alle 6 Batches laufen? Vorschlag: ja, sonst stehen die Reviews etwa drei Tage still. Und soll der Stillstands-Melder im Harness den echten Halt lesen statt der 200M-Zeile? Vorschlag: ja.
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: ghidra-read
program: /830d01.27p.main.bin
</DS_TOOLS>

## VERALLGEMEINERUNG

**F1 – Preflight als Testlauf benutzt** (4 Läufe, darunter `_vor_r3fix` und `_vor_stampfix`; M239-6).
(a) Fehlerklasse: Der volle Preflight dient zur Fehlersuche. Die Regel „ein gültiger Lauf“ ist nur über Archivierung formal eingehalten.
(b) Betroffen ist jede Zwischenprüfung nach einer Änderung an `scripts/` oder `port/`. Die Instruktion verlangt Zwischenprüfungen nur über die betroffene Einzelgruppe (`c_kopf_check`, `m227_profile_live`, `m212_zeilen` oder den Hybrid-Lauf direkt) und genau einen Preflight am Ende. Jeder weitere Lauf braucht eine Ursachenzeile, und Ziel ist 1 Lauf.
(c) Nicht geprüft wird, ob einzelne Gruppen Wechselwirkungen haben, die nur der volle Lauf zeigt.

**F2 – Abdruck des Caches unvollständig** (`c_kopf.py:3973-3985`: nur ausgewählte Funktionen und `rlwinm_mask`; `mcrf` steckt im Interpreter; M239-4).
(a) Fehlerklasse: Der Cache-Schlüssel deckt nicht alle Eingaben ab. Ein dauerhafter Cache macht daraus einen stillen Altstand.
(b) Verwandt sind alle Cache-Schlüssel mit Stempel: `_mess_hash` sowie `_LAUF_CACHE` in `m212_zeilen` (nur prozessintern, unkritisch). In B241 kommt der ganze Quelltext von `m114_matrix` und dem Interpreter-Teil von `c_kopf` in den Abdruck, dazu ein kalter Lauf mit Zeitangabe und dem Ergebnis „abweichend 0“.
(c) B240 prüft das nicht. Die Zeile „Profile reproduzierbar“ in B240 gilt als eingeschränkt (Cache-Vergleich).

**F3 – Ein teilgeprüfter Kopf zählt als fertig** (56C60: 44/85, 41 Blöcke ohne Begründung, `_bahnabdeckung_preflight.txt:287`; M239-3).
(a) Fehlerklasse: Die Fortschrittszahl mischt voll und teilweise geprüfte Köpfe.
(b) Betroffen sind alle 30 teilgeprüften Köpfe. B241 weist sie in der C-Zeile und in der Paket-E-Zählung getrennt aus, zusammen mit der Zahl der Blöcke ohne Begründung.
(c) Ob einzelne offene Blöcke grundsätzlich unerreichbar sind, wird nicht geprüft.

**F4 – Die A4-Zahl misst gegen das Budget, nicht gegen den Lauf** (57819/200M gleich 57819/900M, `_m239/_lauf200m_an.txt:38`, `_lauf900m_an.txt:38`; M239-1).
(a) Fehlerklasse: Der Nenner hängt an der Schrittgrenze, meist an der Endlosschleife. Damit ist er eine Ersatzzahl, kein Anteil.
(b) B240 TEIL 4 erhebt A4 ohne Schatten über einen festen Abschnitt: vom Start bis zum ersten Eintritt in den echten Halt. Daneben steht B/A als Codeanteil, und das Verhältnis zum Budget wird als Ersatzzahl gekennzeichnet.
(c) Wie stabil der Bezugsabschnitt bleibt, wenn sich der Halt verschiebt, wird nicht geprüft. Der Abschnitt wird dann neu benannt; die Zählung fängt deshalb nicht neu an.

**Prüfpunkt b:** Das Material für den zweiten Handschlag liegt im Mitschnitt (8424 `dsp_comm_sharc_w` auf Offset 1–7, Grep im B238-Review).

<DS_INSTRUCTION>
Batch 240 - Silent Scope Decomp

STAND UEBERNEHMEN:
- HEAD dfafcc7, Arbeitsbaum sauber.
- Gültiger Preflight `analysis/_preflight_239.txt` (520 s, 0 Befunde). C Köpfe 121/7044/0.
- B-Stand: Das SHARC-Gerüst (Offset 0, 13794 Bytes) ist standardmäßig an; der Handschlag läuft bis Index 132.
- Echter Halt `8001684C`: Selbstsprung im Fehlerzweig, wenn `FUN_8001b76c`→`FUN_8000be40` ≠ 0 liefert (`port-batch238-…md:156-169`).
- B240 ist ein **B-Batch (Strang B, B-Batch 21)** und der **letzte im Sicherungsfenster R236-1**. Bewegt sich der echte Halt nicht über `8001684C` hinaus, wird Strang B ausgesetzt, und die Frage geht an den Nutzer (stellt der Reviewer). **Front nicht umdefinieren.**
- SOLL-KOEPFE: 0.
- Der Auftrag (a)–(e) steht im Ankerkopf (`r1b-workstream.md:59-64`).

ARBEITSWEISE:
- Startroutine nach AGENTS.md.
- Edit und Write unter `port/` und `scripts/` sind gesperrt bis zum Commit `B240: Vorhersage`. Er enthält die leere Ausgabe von `git status --porcelain port/ scripts/`.
- **Preflight genau einmal, am Ende (M239-6).** Zwischenprüfungen laufen nur über die Einzelgruppe: `hybrid_lauf.exe` direkt oder das betroffene Skript direkt. Jeder weitere Preflight-Lauf braucht eine Ursachenzeile im Dokument.
- Lange Aufrufe blockierend mit `timeout=1800000`.
- Einstufen nach CONFIRMED / STRONG INFERENCE / HYPOTHESIS. Belege als `Datei:Zeile@commit`.
- Urteile zu Nutzerkriterien nur als „erfüllt“ oder „nicht erfüllt + Grund“.
- Vor jedem „fehlt“ per Grep auf den Bezeichner in `analysis/`, `port/` und `capture/`.

TEIL 0 – Doku:
- In `hybrid-plan.md` vermerken: B240 ist der letzte Batch im Sicherungsfenster; gezählt wird am echten Halt.
- Commit `B240: TEIL 0`.

VORHERSAGE (Commit `B240: Vorhersage`):
- Je Bilanzzeile ein Sollwert mit Definition des Zählers.
- Für den echten Halt beide Ausgänge benennen.
- Für die neue A4-Zeile aus TEIL 4 Zähler und Nenner mit Definition.

TEIL 1 – Messen (Anker a, b, c):
- a) Rückgabe von `FUN_8000be40` im Lauf mit Gerüst an messen, als Stufencode 1/2/3/5/7/8/10/11. Die ROM-Stelle des fehlschlagenden Schritts in der Kette `c3a8 → afec → ab90 → ab0c → a7f4 → a110 → b048` benennen.
- b) PPC-Schreibfolge am Mailslot im Hybrid ab Index 120 gegen den Mitschnitt legen. Die erste Abweichung angeben: Index, PC, Wert Hybrid gegen Mitschnitt.
- c) Die 8424 `dsp_comm_sharc_w` auf Offset 1–7 auswerten (`_m240/_sharc_offsets.txt`):
  - Zahl je Offset;
  - die PPC-Lese-PCs, die sie abholen;
  - Bezug zu `FUN_8000c7b8` (Bit-4-Sync auf `0x780C0000`, Ghidra).
  - Klären, ob die Antworten inhaltsabhängig sind, gleiche Probe wie die Prüfsumme in B238.

TEIL 2 – Gerüst erweitern (nur wenn TEIL 1 die fehlende Antwort belegt):
- Den zweiten Handschlag aus dem Mitschnitt nachbilden, oder als ROM-abgeleitetes Modell (zulässig nach `r1b-workstream.md:135-140`).
- Kennzeichnung wie B238: „Hybrid-Gerüst, im Port durch den nativen SHARC-Code zu ersetzen“, dazu ROM-Stelle und Mitschnitt-Zeilen.
- Eigener Schalter für An und Aus.
- Gegenprobe „Erweiterung aus“ = Stand B238 (900M: Halt `8001684C`, Speicher-Hash `AA800106`).
- Rotprobe ROT.
- 900M-Lauf mit Erweiterung: echter Halt mit PC, Grund und Art.
- Lässt sich die fehlende Antwort nicht belegen: das mit Lauf-Datei dokumentieren (Befund) und kein Gerüst bauen.

TEIL 3 – Prüfung (2) neu (Anker d):
- Lauf mit und ohne Schatten bis zum echten Halt.
- Die distinkten PCs Funktionen zuordnen (Ghidra-Funktionsgrenzen oder `_rumpfspannen.txt`).
- Den Rest „nur MIT“ gegen die Körper der nativen Registry-Köpfe legen.
- Urteil zur Funktionsmenge und zur Reihenfolge der ersten Eintritte: nur erfüllt / nicht erfüllt.

TEIL 4 – A4 neu messen (M239-1):
- Im Lauf **ohne Schatten** zählen: Schritte vom Start bis zum **ersten Eintritt** in den echten Halt, und davon die Schritte in nativen Köpfen.
- Beides als neue Rohzeile im Hybrid-Lauf und als Preflight-Zeile.
- Vor dem Preflight: Grep der neuen Zeile gegen alle Muster in `m149_bilanz.py:m_preflight`.
- Die bisherige Zahl (nativ/Budget) ausdrücklich als **Ersatzzahl** kennzeichnen.
- Daneben B/A (Hybrid-Funktionen nativ) als Codeanteil.

TEIL 5 – „nicht vergleichbar 4→1876“ erklären (Anker e):
- Welche Köpfe welche Ursache haben, als Tabelle mit Lauf-Datei.

BATCH-ENDE:
- STILLSTANDSZAEHLUNG B240 in `hybrid-plan.md` eintragen (echter Halt, Preflight-Front).
- Bewegt sich der echte Halt nicht: als „Sicherungsfenster R236-1 ausgeschöpft“ vermerken, **ohne** Strang B selbst auszusetzen (das entscheidet der Nutzer über den Reviewer).
- Preflight einmal: `python -u scripts/preflight.py before *> analysis/_preflight_240.txt`, blockierend mit `timeout=1800000`.
- Zeilendiff `_preflight_239` → `_preflight_240`, mit Erklärung je geänderter Zeile.
- Bilanz mit `--write-anchor`.
- B-Bericht mit beiden Zahlen aus TEIL 4.
- Memory-Export, Commit.
- Ankerkopf `**Stand:** BATCH 240` mit Grep-Beleg und `git status --porcelain` leer.

FERTIG WENN: Stufencode aus (a), erste Abweichung aus (b) und Offset-Auswertung aus (c) sind mit Lauf-Datei belegt UND entweder (Gerüst erweitert + Gegenprobe grün + Rotprobe ROT + gemessener echter Halt 900M) oder (Befund, warum nicht, mit Beleg) UND die A4-Zeile aus TEIL 4 nennt Zähler und Nenner UND die Stillstandszählung B240 ist eingetragen UND genau ein gültiger Preflight + Bilanz liegen vor.

STREICHREIHENFOLGE: Gestrichen wird erst, wenn die Batch-Uhr die Umschaltschwelle erreicht. Unmittelbar davor kommt eine `Get-Date`-Zeile ins Dokument. Reihenfolge:
1. TEIL 5.
2. TEIL 3.
NIE streichen: TEIL 0, Vorhersage, TEIL 1, TEIL 2 bzw. den Befund, TEIL 4, Stillstandszählung, Preflight, Zeilendiff, Bilanz, Memory-Export, Ankerkopf.

## NACHRUECKLISTE
1. Doku und Vorhersage. FERTIG WENN: Die Commits `B240: TEIL 0` und `B240: Vorhersage` stehen vor dem ersten Diff unter `port/` oder `scripts/`, mit der leeren Porcelain-Ausgabe.
2. Messung (a)–(c). FERTIG WENN: Stufencode, erste Abweichung und `_m240/_sharc_offsets.txt` sind im Dokument mit Lauf-Datei belegt.
3. Gerüst oder Befund. FERTIG WENN: entweder Gegenprobe, Rotprobe und 900M-Halt je als Datei in `_m240/`, oder der Befund mit Beleg.
4. A4 neu. FERTIG WENN: Die neue Preflight-Zeile nennt die Schritte bis zum ersten Halteintritt und die nativen Schritte darin, und die Kollisionsprüfung steht im Dokument.
5. Prüfung (2). FERTIG WENN: Die Funktionszuordnung der nur-MIT-PCs und das Urteil erfüllt/nicht erfüllt liegen in `_m240/`.
6. „nicht vergleichbar“. FERTIG WENN: Die Ursachentabelle für 1876 liegt mit Lauf-Datei vor.
</DS_INSTRUCTION>
