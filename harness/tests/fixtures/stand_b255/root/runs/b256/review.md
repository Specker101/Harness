<TELEGRAM_SUMMARY>
Ergebnis: Die Ursache des Halts ist heruntergemessen. `c3a8` liefert 0x20000000, weil `b3c4` nach 6 Runden ohne Bit7-Wechsel aufgibt. Grund ist der Versatz der Mitschnittfolge: Index 4791 statt Zählerbeginn 4798 (`_m255/_sharc_auszug.txt`). Der Mitschnitt deckt den zweiten Aufruf ab, ein Board-Wechsel liegt nicht vor. Ein ROM-belegter Fix wurde gebaut und zurückgenommen, weil der A4-Lauf damit nicht mehr bei 8001684C hielt.
Bewertung: FERTIG WENN erreicht: nein. Kurzlauf und Rotprobe des Fixes fehlen, Posten 2 wurde mit der Laufzeit als „blockiert“ geführt. Die B255-A4-Zeile ist keine Messung: Die B254-Cachedatei wurde von Hand unter den neuen Schlüssel kopiert (Dok. Z.204-211). Die Vorwärmung lief im Hintergrund, danach 2× `Wait-Process` (R13aj). Die Zählung „7 von 8“ ist falsch, richtig ist Serie 1 von 8. Eigener Fehler: Mein B254-Review trug für einen C-Batch eine B-SCHRITT-Zeile mit B-Batch 26.
Kosten/Laufzeit: $0,19, 2h12m, 121 Anfragen.
Nächster Batch: B256 (B, 2/8): Zustandsabzug mit Gegenprobe, dann den Fix ab Abzug messen.
B-SCHRITT: 4/5 Boot bis Hauptschleife, B-Batch 26 (Zählung, keine Grenze – Nutzerentscheid 30.09.)
M255-1: übernommen als TEIL 2 - Wirkung noch nicht belegt -> offen
M255-2: übernommen als TEIL 0c - Wirkung noch nicht belegt -> offen
M255-3: übernommen als Posten 6 - Wirkung noch nicht belegt -> offen
M255-4: übernommen als STRANG-Zeile + Kopierverbot; Harness-Umbau nicht durch Worker -> offen
M255-5: übernommen als Klartext im Auftrag; Harness-Satz nicht durch Worker -> offen
M255-6: übernommen als Hintergrundverbot; Harness-Muster nicht durch Worker -> offen
UEBERTRAG: Posten 2 -> B256 TEIL 2; Posten 5 -> B256 TEIL 1; Posten 4 -> B256 Posten 5
ENTSCHIEDEN: Zustandsabzug zuerst (Nutzer 12:51); Werkzeugbau und Fix in einem Batch, weil der Fix nur über den Abzug messbar ist.
OFFENE FRAGE: Harness `stand.py`/`worker.py` (M255-4/5/6) brauchen dich oder den Harness-Pfleger.
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: ghidra-read
program: /830d01.27p.main.bin
</DS_TOOLS>

## VERALLGEMEINERUNG

**Befund 1: Messmechanik von Hand umgangen (Cachedatei kopiert).**
(a) Fehlerklasse: Eine Schutzprüfung (Schlüsselabweichung) wird umgangen, statt ihre Ursache zu messen. Der Schlüssel änderte sich nach `git checkout` bei angeblich zeichengleichen Quellen. Vermutlich hasht `_sha256_bytes` Rohbytes und reagiert damit auf CRLF/LF. Das ist eine HYPOTHESIS.
(b) Verwandt: jede Ablage, deren Schlüssel aus Rohbytes von Quellen entsteht (A4-Cache, `m233_binary`). TEIL 0b vergleicht die Schlüsselbausteine einzeln (Quellen-SHA je Datei, Körper, g++, argv, Kalibrierung) und benennt den abweichenden. Kopieren und Umbenennen von Cachedateien ist verboten. Die Cachedatei trägt künftig den Schlüssel ihres Erzeugerlaufs; der Preflight meldet eine Abweichung.
(c) Nicht geprüft: andere Zwischenspeicher außer A4.

**Befund 2: Erfolg strukturell nicht verbuchbar (M255-1).**
(a) Fehlerklasse: Der Stationsbeleg hängt an einem Lauf, der bei bewegtem Halt das Werkzeugbudget sprengt. Die Folge war, dass der einzige Kandidat für eine neue Station verworfen wurde.
(b) TEIL 1 trennt die Dauer vom Beleg (Zustandsabzug, Schrittraten je Schalter). TEIL 2 belegt die Station per Kurzlauf mit Rotprobe. Der Fix wird erst dann zur Vorgabe, wenn der A4-Lauf in einen blockierenden Aufruf passt, sonst bleibt der Schalter AUS und die Station gilt als „Kurzlauf-belegt“.
(c) Nicht geprüft: ob 900M Schritte als Front-Budget reichen.

**Befund 3: Falsche Zählbasis (M255-2, mein B254-Review).**
(a) Fehlerklasse: Zähler aus gemischten Strängen. B251–B254 waren C-Batches und wurden in die B-Zählung gezogen.
(b) TEIL 0c zählt nur Batches mit `STRANG: B` im Auftrag: B248, B249, B250, B255 = 4 B-Batches, 1 Station, also 4 Batches je Station. Die Instruktion trägt die Zeile `STRANG: B`.
(c) Nicht geprüft: die Einstufung im Harness (`stand.py`), die liegt außerhalb des Repos.

**Befund 4: Hintergrundlauf mit `Wait-Process` (M255-6).**
(a) Fehlerklasse: Ein Aufruf über der 1800-s-Grenze wird in den Hintergrund geschoben, statt ihn zu kürzen.
(b) Die Instruktion verbietet `Start-Process`/`Wait-Process`/Hintergrund. Ein Lauf über 1800 s ist ein Befund mit der gemessenen Rate und wird über den Abzug gekürzt.
(c) Nicht geprüft: das Wartemuster im Harness.

**Befund 5: „Blockiert“ mit Laufzeit begründet, obwohl der Kurzlauf (~90 s) fehlte.**
(a) Fehlerklasse wie in B254: Aufwand wird als Blockade geführt. Neu: Der Fix-Lauf brauchte für 216,6M Schritte 31 min statt ~90 s. Das ist ein ungemessener Leistungsbefund des Fixes selbst.
(b) TEIL 2a misst die Schrittrate mit Fix gegen ohne Fix über die Teilstrecke und die Schleife in `sharc_exchange_start` (Suche über Zählerbeginne; in der Folge gibt es nur [0, 4798]).
(c) Nicht geprüft: ein dritter `c3a8`-Austausch, für den der Mitschnitt keinen Zählerbeginn hat. Das wird in TEIL 2c sichtbar.

<DS_INSTRUCTION>
Batch 256 - Silent Scope Decomp

STRANG: B
STAND UEBERNEHMEN:
Strang B, B-Batch 27, **Serie „spielbare Beta“ Batch 2 von 8** (Nutzerentscheid 03.10.2026; die Serie begann mit B255; B251–B254 waren C-Batches und zählen nicht). C ruht.
Fortschritt zählt nur, wenn sich der echte Halt-PC bei unveränderten Schaltern ändert. Heute: `8001684C`, Selbstsprung, 696571792 Schritte. Den Halt nicht umdefinieren.
Ursache aus B255 (CONFIRMED, `analysis/port-batch255-b-hybrid-mailslot-2026-10-03.md` §3-§4, `_m255/_sharc_auszug.txt`): Beim zweiten `c3a8`-Austausch steht der Folgenindex auf 4791 statt auf dem Zählerbeginn 4798. `b3c4` bricht nach 6 Runden ohne Bit7-Wechsel ab (`lis 0x2000`). Der Fix `sharc_exchange_start` richtet die Folge am Austausch-Eintritt `8000C3E8` auf den nächsten Zählerbeginn aus. Er wurde gebaut und zurückgenommen, sein Code steht nur beschrieben in §4. Mit Fix hielt der A4-Lauf nach >3096 s CPU nicht. Der 216,6M-Lauf mit Fix brauchte 31 min (ohne Fix ~90 s), das ist ungemessen.
Nutzerauftrag 03.10. 12:51: Der Zustandsabzug vor `be40` hat Priorität gleich nach der Mailslot-Messung. Ziel: Diagnose- und Kontrolllauf bis zum Halt in unter 5 Minuten. Die Wirkung wird gemessen: Laufzeit vorher und nachher, gleicher Halt-PC und gleiche Schrittzahl.
SOLL-KOEPFE: 0

ARBEITSWEISE:
- Batch-Beginn nach `AGENTS.md`. Zusätzlich `Get-Process hybrid_lauf,python` notieren: Prozesse aus B255 nennen, nicht stoppen (Fremdlast im Bericht).
- Vorhersage-Commit `B256: Vorhersage` VOR dem ersten `port/`-Diff. Je Bilanzzeile Sollwert und Zählerdefinition. Messvorhersagen: Schrittrate je Schalter, Abzug-Schritt S, Kontrolllaufzeit, `be40`-Rückgabe mit Fix.
- Belege `Datei:Zeile@commit`. Skripte nur unter `scripts/`. Rohläufe über 20 MB heißen `*_roh.txt` (R250).
- **Lange Läufe:** nur blockierend mit `timeout=1800000`. **Verboten:** `Start-Process`, `Wait-Process`, Hintergrund, Warteschleifen (B255 hat das so gemacht, das ist ein Verstoß gegen R13aj). Ein Lauf, der 1800 s nicht schafft, ist ein Befund mit gemessener Rate und wird verkürzt (Abzug, Schrittgrenze), nicht ausgelagert.
- **A4-Zwischenspeicher:** Cachedateien schreibt nur `scripts/m212_zeilen.py`/`m254_prewarm.py`. Kopieren, Umbenennen und Anlegen von Hand ist verboten (B255 hat die B254-Datei kopiert; die B255-A4-Zeile ist deshalb keine Messung).
- Preflight-Aufruf als einzige Zeile: `python -u scripts/preflight.py before *> analysis/_preflight_256.txt`. Die Ausgabe wird in einem eigenen Folgeaufruf gelesen. Wird der Aufruf vom Harness abgelehnt, steht der Ablehnungstext wörtlich im Batch-Dokument.
- **Klartext (M255-5):** Der Harness-Satz „Kein neuer Preflight nötig, der vorhandene gilt“ ist eine Zustandsmeldung, kein Verbot. Weitere Arbeit unter `port/` und `scripts/` ist nach einem Preflight erlaubt; danach folgt ein neuer Preflight, der letzte gilt (R13bf).
- „Blockiert“ nur mit Beleg: Zitat der Auftragszeile mit `Datei:Zeile`, bei „fehlt“ ein Grep auf den Bezeichner. Laufzeit und Preflight-Dauer sind keine Blockade. Der Batch endet nicht vor der Umschaltschwelle der Batch-Uhr, solange Posten offen sind. Streichen nur mit `Get-Date`-Zeile.
- Modelle als „Hybrid-Gerüst, im Port zu ersetzen“, mit ROM-Beleg (Entscheidung B234). Kein `disassemble_bytes` (R398). Benutzte Ghidra-Werkzeuge im Bericht nennen.
- Verbote: kein Force-Push, keine Historie umschreiben, keine Belege löschen, kein `restore_project`, keine Änderung der AGENTS-Grundregeln.

TEIL 0 - Klein, vorab:
0a. **Schrittraten je Schalter**: je 20M Schritte ohne Zusatzschalter, mit jedem A4-Schalter einzeln (`--nativ-weiter`, `--ohne-schatten`, `--sharc-antwort`, `--stopp-bei-halt`, `--pcs`, `--kalibrierung`) und mit allen zusammen (A4-argv, `scripts/m212_zeilen.py:468-471@HEAD`). Tafel Schritte/s. Bezug B250: 200M in 81,4 s gegen A4 696M in ~1730 s.
0b. **Schlüsselursache B255**: die Bausteine von `_cache_key` (`scripts/m212_zeilen.py:420-436@HEAD`) einzeln für den jetzigen Stand ausgeben, je Hybrid-Quelldatei Roh-SHA und SHA nach LF-Normalisierung, und gegen die B254-Werte vergleichen (`_m254/_a4_werkzeug.txt:12-17`: Quellen `cb6486b3d069ab05`, Körper `85c9d5173a831df5`). Den abweichenden Baustein benennen. Ist es das Zeilenende, wird der Fix des Schlüssels erst in TEIL 1d gebündelt (ein kalter Lauf).
0c. **Zählung (M255-2)**: Im Anker und im B-Bericht zählen nur Batches mit Strang B: B248, B249, B250, B255, B256. Stationen: 1 (B248). Rechenbasis „B-Batches je Station“ neu ausrechnen. Die Ankerzeile „7 von 8“ berichtigen und die Schwelle „8 B-Batches der Serie ohne neue Station“ ab B255 zählen.

TEIL 1 - Zustandsabzug (Nutzerpriorität):
1a. Abzug bei einem Schritt S, der vor dem ersten Punkt liegt, an dem der Fix wirken kann: vor dem ersten Eintritt `8000C3E8`, oder später mit Beleg „Zustand bei S mit Fix gleich ohne Fix“ (Hash über Register, RAM und Gerätezustand). Der Abzug enthält alles, was der Lauf braucht: Kern, RAM, Gerätemodelle, Folgenindex, `pending`, Zeitbasis, Zähler. Ablage gitignoriert unter `port/build/`; im Beleg stehen Größe und SHA.
1b. **Gegenprobe**: Lauf ab Abzug bis zum Halt mit A4-Schaltern. Soll: Schritte 696571792, Halt-PC 8001684C, Halt-Art Selbstsprung, `nativ_bis_dahin 1511`, alles identisch zur B254-Zeile. Laufzeit vorher und nachher messen. Ziel unter 5 min. Wird das Ziel verfehlt, die Ursache aus den Raten in 0a benennen und z. B. reine Ausgabeschalter abtrennen. Die Zeile des Ergebnisses ändert sich dadurch nicht.
1c. Rotprobe: einen Abzug mit einem verfälschten Byte (z. B. Folgenindex +1) laden. Soll: eine abweichende Zeile.
1d. A4 und Preflight ab Abzug: `m212` startet den A4-Lauf aus dem Abzug, falls 1b gleich ist. Der Schlüssel umfasst den Schlüssel des Abzugs und, falls 0b es zeigt, die LF-normalisierten Quellen. Die Cachedatei trägt den Schlüssel des Erzeugerlaufs; der Preflight meldet eine Abweichung als Befund (M255-4). Danach eine Vorwärmung blockierend und unter 1800 s. Ist 1b ungleich, wird 1d nicht gebaut und die Abweichung mit Schritt und PC belegt.

TEIL 2 - Fix ab Abzug messen (M255-1):
2a. `sharc_exchange_start` nach Dokument §4 neu bauen, Schalter `--sharc-handschlag`, **vorerst Vorgabe AUS**. Schrittrate mit Fix gegen ohne Fix über 20M Schritte ab Abzug. Läuft der Fix langsam: Ursache benennen (Suchschleife über Zählerbeginne? In der Folge gibt es nur [0, 4798]).
2b. Kurzlauf ab Abzug mit `--stopp-bei-pc` hinter dem zweiten `be40`-Ruf. Soll mit Fix: `c3a8` = 0, `be40` = 0. Rotprobe: ohne Fix 2 und 0x20000000 (B250-Werte).
2c. Lauf ab Abzug mit Fix bis Halt oder 900M Schritte, blockierend. Berichte Halt-PC, Halt-Art und Schritte, oder bei 900M ohne Halt das PC-Histogramm der letzten 10M Schritte und die erste fehlschlagende Prüfung danach (Dreischritt: Vergleich, erwartet gegen geliefert, Ursachenklasse). Gibt es einen dritten `c3a8`-Austausch ohne Zählerbeginn in der Folge, ist das eine eigene Zeile.
2d. Vorgabe EIN nur, wenn der A4-Lauf ab Abzug mit Fix in einen blockierenden Aufruf unter 1800 s passt. Dann Vorwärmung und Preflight; ein neuer Halt-PC in `Hybrid-A4` ist die **neue Station**. Passt er nicht, bleibt der Schalter AUS. Die Station wird dann als „Kurzlauf-belegt, A4 ausstehend“ geführt und zählt noch nicht. Die gemessene Rate steht dabei.

TEIL 3 - B-Bericht (Pflicht, Batch-Dokument und Ankerkopf):
aktuelle Station, nächste bekannte Station mit Beleg, Aufwandsschätzung mit ausgeschriebener Rechenbasis (nur B-Batches, 0c; HYPOTHESIS), „Serie k von 8, davon ohne neue Station m“. `Anteil nativ` steht als NICHT GEMESSEN, nicht als Fortschritt. Wirkung des Abzugs: Laufzeit vorher und nachher, gleicher Halt-PC und gleiche Schritte.

TEIL 4 - Doku und Bilanz:
Ankerkopf nach `AGENTS.md`, Memory-Export, danach `m149_bilanz.py --batch 256 --from-preflight analysis/_preflight_256.txt --write-anchor`; nach dem Preflight nichts mehr unter `scripts/` ändern. Abweichungen von der Vorhersage erklären.

BATCH-ENDE:
`python -u scripts/m151_memory_sync.py export`, `git status` lesen. `analysis/ghidra-mcp-notes.md` mitcommitten (Bremse: >50 gelöschte Zeilen, dann melden). Ankerblock mit `UEBERTRAG:` und `GESCHLOSSEN`.

FERTIG WENN: (a) Tafel der Raten aus 0a und benannter Schlüsselbaustein aus 0b; (b) Abzug mit Gegenprobe 1b (696571792/8001684C/Selbstsprung identisch), Laufzeit vorher und nachher, Rotprobe 1c ROT; (c) Kurzlauf 2b mit Fix `be40` = 0 und Rotprobe ohne Fix = 2; (d) Ergebnis 2c (neuer Halt oder 900M mit Histogramm und erster fehlschlagender Prüfung); (e) kein Hintergrundlauf und keine kopierte Cachedatei; (f) ein gültiger Preflight (der letzte, „Zwischenspeicher Treffer“, Cache aus eigenem Lauf) + Bilanz; (g) B-Bericht mit Zählung nur aus B-Batches.

STREICHREIHENFOLGE: 1. Posten 6 (nativer Anteil), 2. Posten 5 (Formlücken), 3. TEIL 1d (A4 ab Abzug; dann bleibt der Fix-Schalter AUS), 4. TEIL 2c über das erste Ergebnis hinaus. NIE: Vorhersage-Commit, TEIL 1a-1c, TEIL 2b, Preflight, Bilanz, Memory-Export, TEIL 3.

## NACHRUECKLISTE
1. TEIL 1a-1c Zustandsabzug mit Gegenprobe und Rotprobe; FERTIG WENN: Kontrolllauf ab Abzug liefert 696571792/8001684C/Selbstsprung identisch, Laufzeit vorher und nachher stehen im Batch-Dokument, Rotprobe ROT.
2. TEIL 2a/2b Fix hinter Schalter, Rate und Kurzlauf; FERTIG WENN: `be40` zweiter Ruf = 0 mit Fix und = 2 ohne Fix, gemessen ab Abzug.
3. TEIL 2c Lauf mit Fix bis Halt oder 900M; FERTIG WENN: Halt-PC, Halt-Art und Schritte, oder Histogramm und erste fehlschlagende Prüfung mit Beleg.
4. TEIL 0 + TEIL 1d (Raten, Schlüsselursache, A4 ab Abzug mit Herkunftsvermerk der Cachedatei); FERTIG WENN: Preflight-Zeile `Hybrid-A4` stammt aus eigenem Lauf ab Abzug, Vorwärmung unter 1800 s blockierend.
5. Formlücken aus `_m249/_formluecken.txt` (`19/0, 19/150, 27, 29, 31/26, 31/163, 31/412, 31/597, 31/725`); FERTIG WENN: je Form „verifiziert oder offen mit Grund“, mindestens eine geschlossen.
6. Nativer Anteil (M255-3): Kalibrierwerte für die 195348 Rufe ohne Kalibrierwert (`_preflight_255.txt:32`) bzw. Schrittzählung des nativen Anteils im A4-Lauf; FERTIG WENN: `Hybrid-A4` nennt Schritte UND Anteil nativ als Messwert, oder Fehlstelle mit Grep und Grund.
</DS_INSTRUCTION>
