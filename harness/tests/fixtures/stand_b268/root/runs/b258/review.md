**Review B257:** Das FERTIG WENN ist erreicht, mit einer Einschränkung: Der Vorwärmlauf hatte keine Wanduhrgrenze. Gemessen und belegt sind drei Dinge. Das Langsamfenster liegt am Schalter `--nativ-weiter`, und die Korrektur halbiert die Laufzeit bei unverändertem Ergebnis. Die B255-Schrittangabe ist widerlegt. Der Cache-Schlüssel ist jetzt stabil. Die Blockade des Fix-Postens trägt nicht: Der Fix hängt an einer Adresse, nicht an einem Schritt, und Laufzeit ist keine Blockade. B258 baut den Zustandsabzug vor dem zweiten SHARC-Austausch und misst den Fix von dort aus.

<TELEGRAM_SUMMARY>
Ergebnis: Das Langsamfenster liegt am Schalter `--nativ-weiter`. Ursache: zwei 4-MB-Felder wurden vor jedem Kopf-Ruf angelegt. Nach der Korrektur fällt das Fenster von 1671 auf 842 s und der A4-Lauf von 1726 auf 952 s. Das Ergebnis bleibt zeichengleich: 696571792 / 8001684C / Selbstsprung. Der zweite `8000C3A8`-Eintritt liegt bei 215016862 mit Index 4796 (`_m257/_stoppc.txt:3,8`), nicht bei 216571291/4791. Der erste `8000C3E8`-Eintritt steht auf Index 0. Der Cache-Schlüssel ist LF-normalisiert, Grün- und Rotprobe sind belegt. Der native Anteil 0..200M beträgt 101577/200000000.
Bewertung: Saubere Messarbeit. Befunde:
(1) Den Fix-Posten hat der Worker zu Unrecht als blockiert geführt. Der Fix greift an der Adresse `8000C3E8`, nicht an einem Schritt. Laufzeit ist keine Blockade.
(2) Bei den Formlücken wurde „nicht ausgeführt“ als „verifiziert“ geführt (`_m257/_formluecken.txt:5-13`).
(3) Die Vorwärmung lief ohne Wanduhrgrenze.
(4) Laufzeit 155 min, über der Alarmgrenze 150 min.
(5) Der Ankerkopf nennt als Preflight-HEAD `c31005c`, gültig ist `08b33de`.
Die Serie steht bei 3 von 8, keine neue Station. Der Halt hat sich seit B248 nicht bewegt.
FERTIG WENN erreicht: ja – mit Einschränkung (e): Vorwärmung ohne Wanduhrgrenze.
Kosten/Laufzeit: 0,135 $, 155 min, 105 Anfragen, eine Fortsetzung.
Nächster Batch: Abzug vor dem zweiten Austausch, Gegenprobe ab Abzug unter 5 min, Fix-Kurzlauf ab Abzug.
B-SCHRITT: 4/5 Boot bis Hauptschleife, B-Batch 28 (Zählung, keine Grenze – Nutzerentscheid 30.09.)
M256-1: übernommen - Wirkung belegt: `_m257/_stoppc.txt:3,8` (Schritt und Index gemessen, Angabe widerlegt)
M256-2: übernommen - Wirkung belegt: `_m257/_fenster.txt:10-58` (Fenster gemessen, Ursache benannt)
M256-4: übernommen - Wirkung belegt: Batchdokument B257:210 (zwei Läufe über 600 s)
M256-5: übernommen - Wirkung belegt: kein Abbruch, längster Aufruf 1083 s (result.json)
M256-6: übernommen - Wirkung belegt: `_m257/_schluessel_probe.txt:7-8`
M256-3b: übernommen als B258 TEIL 4 - nur 0..200M gemessen, `Hybrid-A4` weiter NICHT GEMESSEN -> bleibt offen
UEBERTRAG: B257 N5 Fix -> B258 TEIL 3
UEBERTRAG: B257 TEIL 5 Abzug -> B258 TEIL 2
UEBERTRAG: B257 TEIL 3 n=3 (dritter Austausch) -> B258 TEIL 3c
UEBERTRAG: Formlücken-Beschriftung -> B258 TEIL 0b
ENTSCHIEDEN: Der Fix bleibt an `8000C3E8` (PC-gesteuert). Keine Neuverankerung auf einen Schritt.
ENTSCHIEDEN: Abzug bei S < 215016862. Er gilt erst, wenn der Hash des Zustands bei S mit und ohne Fix gleich ist.
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: ghidra-read
program: /830d01.27p.main.bin
</DS_TOOLS>

## VERALLGEMEINERUNG

**F1: Blockade mit falschem Grund (Posten 5: „Entscheidung fehlt, Schritt falsch“ und „3096 s Laufzeit“).**
- (a) Fehlerklasse: Eine Blockade wird mit einer überholten Messung begründet. Die 3096 s stammen aus der Zeit vor der Beschleunigung. Dazu kommt ein Missverständnis des Wirkpunkts: Der Fix ist PC-gesteuert, nicht an einen Schritt gebunden.
- (b) Verwandte Fälle: jede Laufzeitangabe aus B255/B256, die vor dem B257-Fix gemessen wurde. Prüfung in der Instruktion: Eine Blockade braucht eine Messung aus demselben Binärstand (HEAD) und ein Zitat der Fix-Bedingung aus dem Code. Laufzeiten aus älteren Ständen gelten nicht.
- (c) Nicht geprüft: ob der Fix inhaltlich der ROM-Logik entspricht, über den ROM-Beleg in TEIL 3a hinaus.

**F2: Begriffsdehnung „verifiziert“ für „nicht ausgeführt“ bzw. „ohne Ausnahme gelaufen“ (Formlücken).**
- (a) Fehlerklasse: Ein Abdeckungsbefund wird als Korrektheitsnachweis ausgegeben.
- (b) Verwandte Fälle: „GESCHLOSSEN“ ohne Referenzvergleich in anderen Postenlisten. Prüfung in TEIL 0b: Die Beschriftung wird zu „nicht ausgeführt (A4)“ bzw. „ausgeführt ohne EXC, kein Referenzvergleich“. Die Ankerzeile übernimmt diese Wörter.
- (c) Nicht geprüft: Referenzvergleich der Form 29 (bleibt offen, für den Halt ohne Belang).

**F3: Langer Lauf ohne Wanduhrgrenze (Vorwärmung über ein Skript).**
- (a) Fehlerklasse: Eine Pflichtgrenze wird über einen Skriptumweg verloren.
- (b) Verwandter Fall: der kalte A4-Lauf im Preflight. Prüfung in der Instruktion: Die Vorwärmung ist zulässig, wenn ihre Dauer im selben Batch bereits unter 1200 s gemessen wurde. Sonst nur mit Wanduhrgrenze. Die Lauftafel weist jede Zeile ohne Grenze aus.
- (c) Nicht geprüft: das Verhalten des Preflights bei einem Cache-Fehlgriff.

**F4: Ankerkopf nennt einen veralteten Preflight-HEAD.**
- (a) Fehlerklasse: Der Anker wird nach einer Fortsetzung nicht nachgezogen.
- (b) Verwandte Fälle: Anker-Bilanzzeile und Batch-Nummer. Prüfung: Der Ankerkopf nennt den HEAD aus Zeile 3 des gültigen Preflights.
- (c) Ansonsten Einmal-Sache.

<DS_INSTRUCTION>
Batch 258 - Silent Scope Decomp

STRANG: B
SOLL-KOEPFE: 0

STAND UEBERNEHMEN:
Strang B, B-Batch 29, **Serie „spielbare Beta“ Batch 4 von 8** (Nutzerentscheid 03.10.2026; bisher 0 neue Stationen in B255–B257). C ruht.
Halt unverändert: `8001684C`, Selbstsprung, 696571792 Schritte, `nativ_bis_dahin 1511`. Den Halt nicht umdefinieren.
B257 hat gemessen:
- Langsamfenster wegen `--nativ-weiter`, Ursache waren die 4-MB-Felder je Kopf-Ruf, behoben in `c31005c`. Fenster bis 216,6M 842,1 s, voller A4 952,4 s, zeichengleich (`analysis/_m257/_a4_vorwaermung.txt@8f164b7`).
- `KOPF-ZEIT` vor dem Fix: ROM-Aufbau ~79 s je 240-s-Lauf, 3,2 ms je Ruf (`_m257/_fenster.txt:10@8f164b7`).
- 1. `8000C3E8`-Eintritt bei Schritt 173423457 mit Index 0. 2. `8000C3A8`-Eintritt bei 215016862, 2. `8000C3E8`-Eintritt bei 215016878, Index 4796/13794 (`_m257/_stoppc.txt:3,8`, `_m257/_stoppc_c3e8.txt:4-10@31edbd9`). Nächster Zählerbeginn laut B255: 4798.
- Gültiger Preflight `_preflight_257.txt` mit HEAD `08b33de`.
ENTSCHEIDUNG (Reviewer): Der Fix `sharc_exchange_start` (B255 §4) greift **an der Adresse `8000C3E8`**, nicht an einem Schritt. Am 1. Eintritt (Index 0 = Zählerbeginn) bleibt er wirkungslos, am 2. Eintritt richtet er 4796 auf 4798 aus. Eine „Neuverankerung auf einen Schritt“ entfällt. Die B257-Blockade von Posten 5 ist aufgehoben (Laufzeit ist keine Blockade; die 3096 s stammen aus der Zeit vor dem B257-Fix).
ENTSCHEIDUNG (Reviewer): Der Zustandsabzug (Nutzerpriorität 03.10. 12:51, Ziel Kontrolllauf unter 5 min) liegt jetzt **unmittelbar vor dem 2. `8000C3A8`-Eintritt**. Danach braucht A4 laut B257 nur noch ~110 s (952 s gesamt minus ~845 s bis 215M). Der Fix kann erst ab dort wirken.

ARBEITSWEISE:
- Batch-Beginn nach `AGENTS.md`. `Get-Process hybrid_lauf,python` EINMAL notieren, nichts stoppen.
- Vorhersage-Commit `B258: Vorhersage` VOR jedem `port/`- und `scripts/`-Diff. Je Bilanzzeile Sollwert und Zählerdefinition. Messvorhersagen: Fensterzeit nach TEIL 1, Abzug-Schritt S, Laufzeit der Gegenprobe ab Abzug, `c3a8`/`be40` mit und ohne Fix, Halt mit Fix.
- **Jeder `hybrid_lauf.exe`-Aufruf trägt `--wanduhr-grenze` ≤ 1500**, blockierend mit `timeout=1800000`. Einzige Ausnahme ist die Vorwärmung über `m257_prewarm.py`/`m212`: zulässig, wenn ihre Dauer in diesem Batch schon unter 1200 s gemessen ist. Sonst vorher eine Wanduhrgrenze in den Aufruf. `preflight.py`, `port_build` und `c_kopf.py mutalle` laufen als normaler Aufruf mit `timeout=1800000`.
- **Verboten:** `Start-Process`, `Wait-Process`, Hintergrund, Warteschleifen, Abräumen über `Get-Process`/Variable/Pipe.
- Höchstens **3 Läufe über 600 s**. Lauftafel im Batch-Dokument mit argv, Grenze, Wanduhr, Schritten und Ende. Jede Zeile ohne Grenze wird als solche ausgewiesen.
- „Blockiert“ nur mit einer Messung aus **demselben Binärstand (HEAD)** und dem Zitat der Bedingung (`Datei:Zeile@commit`). Laufzeit und ältere Messungen sind keine Blockade. Gestrichen wird nur ab der Umschaltschwelle mit `Get-Date`-Zeile.
- Belege als `Datei:Zeile@commit`. Rohläufe über 20 MB heißen `*_roh.txt`. Cachedateien schreiben nur die Skripte. Modelle tragen „Hybrid-Gerüst, im Port zu ersetzen“ und einen ROM-Beleg. Kein `disassemble_bytes`.
- Preflight als einzige Zeile `python -u scripts/preflight.py before *> analysis/_preflight_258.txt`, Ausgabe im Folgeaufruf lesen. Keine weiteren Befehle in derselben Zeile (B257 wurde damit abgelehnt).

TEIL 0 - Klein:
0a. Vorhersage-Commit.
0b. Formlücken-Beschriftung berichtigen (`_m257/_formluecken.txt:5-13@08b33de`). Die 8 Formen heißen „nicht ausgeführt (A4), für den Halt ohne Belang – nicht verifiziert“, Form 29 heißt „ausgeführt ohne EXC, kein Referenzvergleich“. Als neue Datei `_m258/_formluecken.txt`; die alte Datei bleibt stehen. Ankerzeile entsprechend.

TEIL 1 - Zweite Beschleunigung (nur messen und bauen, Ergebnis zeichengleich):
1a. Kurzer Lauf (A4-argv, `--schritte 216600000 --wanduhr-grenze 240 --kopf-zeit`) auf HEAD: neue Aufteilung der Kopf-Rufkosten nach dem B257-Fix.
1b. Ist `ROM-Aufbau` weiter der größte Posten: das ROM-Abbild nur einmal je Prozess aufbauen und wiederverwenden. Geändert wird nur der Weg, nicht der Inhalt. Andere Hauptursache: benennen und, wenn klein, ebenso beheben. Kurzlauf 20M zeichengleich und Rotprobe (`--mutation`) ROT. Ändert die Beschleunigung ein Ergebnis: zurücknehmen, belegen, weiter mit TEIL 2.
1c. Die Fensterzeit wird im Abzugslauf von TEIL 2a mitgemessen (vorher 842,1 s). Kein eigener Langlauf.

TEIL 2 - Zustandsabzug (Nutzerpriorität):
2a. Abzug bei S = letzter Schritt vor dem 2. `8000C3A8`-Eintritt (≤ 215016861). Inhalt: alles, was der Lauf braucht – Kern, RAM, Gerätemodelle, SHARC-Folgenindex und Schrittzähler, `pending`, Zeitbasis, Zähler, Zählerstände des nativen Wegs (`nativ_bis_dahin`, Kalibrier- und Rufzähler) und `--pcs`-Menge. Ablage gitignoriert unter `port/build/`, Größe und SHA im Beleg. Laden über einen neuen Schalter, z. B. `--abzug-laden <datei>`.
2b. **Gleichheit bei S:** Hash des Abzugs mit `--sharc-handschlag` (TEIL 3a) und ohne muss gleich sein. Damit ist belegt, dass der Fix vor S nicht wirkt. Gibt es TEIL 3a noch nicht, wird 2b nach 3a nachgeholt.
2c. **Gegenprobe:** Lauf ab Abzug bis zum Halt, A4-Schalter, `--wanduhr-grenze 600`. Soll: 696571792 / 8001684C / Selbstsprung / `nativ_bis_dahin 1511`, zeichengleich zur Vollzeile. Laufzeit ab Abzug gegen 952,4 s. **Ziel unter 300 s.** Ist sie ungleich: erste Abweichung mit Schritt und PC belegen, dann TEIL 3 mit Vollläufen (≤1500 s).
2d. **Rotprobe:** Abzug mit Folgenindex +1 laden. Soll: abweichende Zeile.

TEIL 3 - Fix messen (ab Abzug):
3a. `sharc_exchange_start` nach B255 §4 neu bauen, PC-gesteuert an `8000C3E8`, Schalter `--sharc-handschlag`, **Vorgabe AUS**. ROM-Beleg für den Zählerbeginn (Folge `[0, 4798]`) im Dokument.
3b. Kurzlauf ab Abzug mit `--stopp-bei-pc` hinter dem 2. `be40`-Ruf. Soll mit Fix: `c3a8` = 0, `be40` = 0. Rotprobe ohne Fix: 2 bzw. 0x20000000, auf **diesem** HEAD gemessen.
3c. Lauf ab Abzug mit Fix bis Halt oder `--wanduhr-grenze 1500`. Ergebnis: Halt-PC, Halt-Art und Schritte. Bei WANDUHR-HALT: Schritte, PC-Histogramm der letzten 10M und die erste fehlschlagende Prüfung (Vergleich, erwartet gegen geliefert, Ursachenklasse). Ein dritter `c3a8`-Austausch bekommt eine eigene Zeile mit Schritt und Index.
3d. Vorgabe EIN nur, wenn 3c einen neuen Halt liefert **und** der volle A4-Lauf mit Fix unter 1500 s gemessen ist. Dann Vorwärmung und Preflight; der neue Halt-PC in `Hybrid-A4` ist die neue Station. Andernfalls bleibt die Vorgabe AUS und die Station heißt „Kurzlauf-belegt, A4 ausstehend“ (zählt noch nicht).

TEIL 4 - Nativer Anteil (M256-3b, NIE streichen):
Lauf ab Abzug **mit Schatten** (A4-argv ohne `--ohne-schatten`, Vorgabe-Fix AUS, `--wanduhr-grenze 600`). Ergebnis: Schattenschritte bei nativen Rufen gegen Gesamtschritte für S..Halt, als `nativ x / Schritte` mit Bereich. Dazu B257 0..200M (101577/200000000) und die Lücke 200M..S benennen. Weicht der Halt mit Schatten ab, ist das eine eigene Zeile. Im B-Bericht stehen beide Zahlen; `57819/200000000` ist die Ersatzzahl.

TEIL 5 - Vorwärmung, Preflight, Bilanz, B-Bericht:
Nach den `port/hybrid/`-Diffs ist der Cache kalt: Vorwärmung blockierend (Regel oben), dann Preflight und `m149_bilanz.py --batch 258 --from-preflight analysis/_preflight_258.txt --write-anchor`. Nach dem Preflight nichts mehr unter `scripts/` ändern.
Ankerkopf auf B258: Preflight-HEAD aus Zeile 3 des gültigen Preflights (B257-Kopf nannte fälschlich `c31005c`), Station, Abzugswirkung (Laufzeit vorher/nachher), Fix-Ergebnis, nativer Anteil mit Bereich, „Serie 4 von 8, ohne neue Station m“. Zählung nur aus B-Batches. Memory-Export, `git status` lesen, `ghidra-mcp-notes.md` mitcommitten (Bremse >50 Zeilen). Ankerblock mit `UEBERTRAG:` und `GESCHLOSSEN`.

BATCH-ENDE:
`python -u scripts/m151_memory_sync.py export`, `git status` lesen, Commit `B258: …`. Abweichungen von der Vorhersage erklären.

FERTIG WENN: (a) Abzug mit Gegenprobe zeichengleich, Laufzeit vorher/nachher und Rotprobe ROT; (b) Hash-Gleichheit bei S mit und ohne Fix; (c) Kurzlauf 3b mit Fix `be40` = 0, ohne Fix = 2, auf demselben HEAD; (d) Ergebnis 3c (Halt oder WANDUHR-HALT mit Histogramm und erster fehlschlagender Prüfung); (e) nativer Anteil S..Halt als Messwert; (f) jeder `hybrid_lauf` mit Grenze bzw. belegter Ausnahme, kein Lauf über 1800 s; (g) ein gültiger Preflight + Bilanz, Ankerkopf B258 mit richtigem HEAD.

STREICHREIHENFOLGE: 1. TEIL 0b (Beschriftung), 2. TEIL 1 (zweite Beschleunigung), 3. TEIL 3d (Vorgabe EIN), 4. TEIL 3c über das erste Ergebnis hinaus. NIE: Vorhersage-Commit, TEIL 2a-2d, TEIL 3a-3b, TEIL 4, Preflight, Bilanz, Memory-Export, Ankerkopf/B-Bericht.

## NACHRUECKLISTE
1. TEIL 2a-2d Abzug; FERTIG WENN: Gegenprobe ab Abzug zeichengleich 696571792/8001684C/Selbstsprung/1511, Laufzeit vorher und nachher im Dokument, Rotprobe ROT.
2. TEIL 3a/3b + 2b; FERTIG WENN: Hash bei S mit und ohne Fix gleich, `be40` 2. Ruf = 0 mit Fix und = 2 ohne Fix, beide ab Abzug auf demselben HEAD.
3. TEIL 4 nativer Anteil; FERTIG WENN: `nativ x / Schritte` für S..Halt mit Bereich im B-Bericht, Lücke 200M..S benannt.
4. TEIL 3c Lauf mit Fix; FERTIG WENN: Halt-PC/Art/Schritte, oder WANDUHR-HALT mit Histogramm der letzten 10M und erster fehlschlagender Prüfung.
5. TEIL 1 zweite Beschleunigung; FERTIG WENN: `KOPF-ZEIT` vorher/nachher, Kurzlauf zeichengleich, Rotprobe ROT, Fensterzeit gegen 842,1 s.
6. TEIL 0b Formlücken-Beschriftung; FERTIG WENN: `_m258/_formluecken.txt` mit den neuen Wörtern committet, Ankerzeile angepasst.
</DS_INSTRUCTION>
