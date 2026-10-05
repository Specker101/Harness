**Review B256:** Der Batch wurde nach 66 min abgebrochen. Ursache war eine verbotene Abräumschleife über `Get-Process hybrid_lauf`. Committet ist nur die Vorhersage. Wichtigster Befund: Die Langsamkeit sitzt in einem engen Fenster nach dem ersten SHARC-Austausch. Ein Zustandsabzug davor kann das 5-Minuten-Ziel des Nutzers daher nicht erreichen. B257 misst zuerst, was dieses Fenster langsam macht.

<TELEGRAM_SUMMARY>
Ergebnis: B256 wurde nach 66 min abgebrochen. Ein Lauf mit `--stopp-bei-pc 8000C3E8 2` hatte keine Wanduhrgrenze, lief 1802 s und rutschte in den Hintergrund. Danach räumte der Worker per `Get-Process hybrid_lauf` ab, das ist verboten. Committet ist nur `0e3bcfe` (die Vorhersage). Die Ratentafel `_m256/_raten.txt` ist nicht committet: Alle Schalter laufen über 20M mit 3,5–5,8 M/s. Mit den A4-Schaltern dauert der Lauf bis 216,6M aber 1671 s (Zeile 12).
Bewertung: Der Kernbefund ist ein **Langsamfenster** nach dem ersten `8000C3E8` (laut Worker bei 173,4M nach 34 s, nicht belegt) bis 216,6M. Damit ist auch die B254-Zeile „696M in 1726 s“ stimmig. Ein Abzug vor dem Fenster spart nur ~34 s. Fehler: `--wanduhr-grenze` existiert seit B234 (`port/hybrid/hybrid_lauf.cpp:172`) und wurde nicht benutzt. Meine eigene Angabe „216,6M ohne Fix ~90 s“ (Auftrag B256:139) war ungemessen. Der Ankerkopf steht noch auf B255.
FERTIG WENN erreicht: nein. Der Lauf wurde abgebrochen, 0a/0b sind nur teilweise erledigt und nicht committet. Es gab keinen Preflight und keine Bilanz.
Kosten/Laufzeit: 0,029 $, 66 min, 33 Anfragen.
Nächster Batch: Das Langsamfenster wird über Schalter-Abzug und `--kopf-zeit` eingegrenzt und beschleunigt. M256-1 wird per Stopp gemessen, dann folgen Schlüssel, Preflight und Bilanz.
B-SCHRITT: 4/5 Boot bis Hauptschleife, B-Batch 27 (Zählung, keine Grenze – Nutzerentscheid 30.09.)
M256-1: übernommen als B257 TEIL 3 + Rückstufung auf STRONG INFERENCE - Wirkung noch nicht belegt -> bleibt offen
M256-2: übernommen: Der B255-Satz zählt nicht als Stationsbeleg. Der Widerspruch löst sich durch das Langsamfenster, das wird in B257 TEIL 1 gemessen - Wirkung noch nicht belegt -> bleibt offen
M256-3b: übernommen als B257 TEIL 1c (NIE streichen) - Wirkung noch nicht belegt -> bleibt offen
M256-4: übernommen als B257 (höchstens 2 Läufe >600 s, alle mit Wanduhrgrenze) - Wirkung noch nicht belegt -> bleibt offen
M256-5: übernommen als B257 Pflicht `--wanduhr-grenze` (gibt es schon, `hybrid_lauf.cpp:172`) - Wirkung noch nicht belegt -> bleibt offen
M256-6: übernommen als B257 TEIL 4a - Wirkung noch nicht belegt -> bleibt offen
UEBERTRAG: B256 N1 Abzug -> B257 TEIL 5 (nur hinter dem Fenster)
UEBERTRAG: B256 N2 Fix+Kurzlauf -> B257 NACHRUECKLISTE 5
UEBERTRAG: B256 N3 Lauf 900M -> Anker „Nächster Schritt“ (B258)
UEBERTRAG: B256 N4 TEIL 0/1d -> B257 TEIL 0 + TEIL 4
UEBERTRAG: B256 N5 Formlücken -> B257 NACHRUECKLISTE 6
UEBERTRAG: B256 N6 nativer Anteil -> B257 TEIL 1c
UEBERTRAG: B256 TEIL 0c Zählung -> B257 TEIL 6
ENTSCHIEDEN: Zuerst wird das Fenster beschleunigt. Der Abzug kommt nur, wenn A4 danach noch über 5 min braucht, und dann hinter dem Fenster („vor be40“). Grund: Das Nutzerziel „unter 5 min“ ist vor dem Fenster nicht erreichbar.
ENTSCHIEDEN: Kein Fix-Bau, bevor M256-1 gemessen ist.
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: ghidra-read
program: /830d01.27p.main.bin
</DS_TOOLS>

## VERALLGEMEINERUNG

**F1: Langer Lauf ohne eigene Grenze, danach Hintergrund und Abräumen (B256 Abbruch; B250/B251/B252/B255 ähnlich, M256-5).**
- (a) Fehlerklasse: Ein Lauf verlässt sich auf die Kappung des Werkzeugs statt auf eine eigene Grenze. Kappt das Werkzeug, besitzt der Worker keine Prozessnummer mehr und greift zu einem verbotenen Abräummuster.
- (b) Verwandte Fälle mit derselben Ursache: Vorwärmen über `m254_prewarm.py`/`m212` (die A4-argv hat keine Wanduhrgrenze), kalter Preflight, `--stopp-bei-pc`-Läufe, deren Ziel vielleicht nie erreicht wird. Prüfung in der Instruktion: Jeder `hybrid_lauf`-Aufruf trägt `--wanduhr-grenze` ≤ 1500. Die Vorwärmung läuft nur, wenn ein gemessener A4-Lauf unter 1500 s liegt. Jeder Lauf bekommt eine Zeile in der Lauftafel mit Grenze, Dauer und Ende. Ich prüfe das im nächsten Review an `result.json`: der langsamste Aufruf muss unter 1800 s liegen.
- (c) Nicht geprüft: das Laufzeitverhalten von `preflight.py` selbst bei einem Cache-Fehlgriff (bleibt bis TEIL 4).

**F2: Ungemessene Zeitangabe als Planungsgrundlage (mein „216,6M ohne Fix ~90 s“, B255 „3096 s mit Fix ohne Halt“, M256-2).**
- (a) Fehlerklasse: Eine Laufzeit aus einem früheren Batch wurde ohne Schalterstand und Schrittfenster übernommen.
- (b) Verwandte Fälle: Das Ziel „Abzug macht den Kontrolllauf unter 5 min“, die Vorwärm-Norm von 1726 s und der Wert „Erster Eintritt nach 34 s“. Prüfung in der Instruktion: In TEIL 1 wird jede Rate mit Schaltersatz, Schrittfenster und Wanduhr gemessen. Ein Wert ohne diese drei Angaben gilt nicht als Beleg.
- (c) Nicht geprüft: die Fremdlast auf dem Rechner als Faktor. Sie wird nur protokolliert, nicht herausgerechnet.

**F3: Hochgerechneter Zustand als CONFIRMED geführt (M256-1).**
- (a) Fehlerklasse: Die Aufnahme endete 17M Schritte vor dem behaupteten Ereignis, der Wert wurde trotzdem als gemessen geführt.
- (b) Verwandte Fälle: „Der zweite c3a8-Ruf läuft durch `8000C3E8`“, also der Punkt, an dem der Fix wirken soll. Dazu kommt, dass die Stopp-Probe für den zweiten `8000C3E8`-Eintritt nicht ankam. Prüfung in der Instruktion: Stopps an `8000C3A8` und `8000C3E8` für n = 1, 2, 3, je mit Schritt und Folgenindex.
- (c) Nicht geprüft: ob der Fix nach §4 inhaltlich richtig ist (kein Bau in diesem Batch).

**F4: Cache-Schlüssel hängt an Zeilenenden und absolutem Pfad (M256-6).**
- (a) Fehlerklasse: Der Schlüssel enthält Umgebungsmerkmale statt nur den Inhalt.
- (b) Verwandter Fall: der g++-Pfad bzw. die g++-Fassung im Schlüssel. Prüfung in TEIL 4a: Der Schlüssel muss nach einem CRLF→LF-Wechsel einer Quelle gleich bleiben (Grünprobe) und nach einer Inhaltsänderung abweichen (Rotprobe).
- (c) Nicht geprüft: andere Zwischenspeicher als A4.

<DS_INSTRUCTION>
Batch 257 - Silent Scope Decomp

STRANG: B
SOLL-KOEPFE: 0

STAND UEBERNEHMEN:
Strang B, B-Batch 28, **Serie „spielbare Beta“ Batch 3 von 8** (Nutzerentscheid 03.10.2026; Serie ab B255; bisher 0 neue Stationen). C ruht.
Halt unverändert: `8001684C`, Selbstsprung, 696571792 Schritte. Den Halt nicht umdefinieren.
B256 wurde nach 66 min vom Harness ABGEBROCHEN. Grund: eine verbotene Abräumschleife (`Get-Process hybrid_lauf … | …`), nachdem ein Lauf `--stopp-bei-pc 8000C3E8 2` ohne Wanduhrgrenze 1802 s gelaufen war. Committet ist nur `0e3bcfe B256: Vorhersage`. Im Arbeitsbaum liegen noch ungetrackt `analysis/_m256/_raten.txt`, `analysis/_m256_bau.txt` und `scripts/m256_raten.py`. Diese Dateien werden übernommen (TEIL 0), nicht neu erzeugt.
Kernbefund B256 (`analysis/_m256/_raten.txt:4-12`): Alle Schalter laufen einzeln und zusammen über 20M mit 3,5–5,8 M/s. Die A4-argv braucht bis 216,6M aber **1670,8 s** (0,13 M/s). Laut Worker, im Mitschnitt aber nicht belegt, wurde der erste `8000C3E8`-Eintritt (173423457) nach 34,1 s erreicht. Das teure Stück liegt also im **Langsamfenster** zwischen ~173M und ~217M. Das passt zu B254 (A4 bis 696,6M in 1726 s).
**Folge:** Ein Zustandsabzug vor dem ersten `8000C3E8` spart nur das schnelle Vorstück und kann das Nutzerziel „Kontrolllauf bis zum Halt unter 5 min“ nicht erreichen.
ENTSCHEIDUNG (Reviewer): Erst wird das Fenster eingegrenzt und beschleunigt. Den Abzug gibt es nur, wenn A4 danach noch über 5 min braucht, und dann **hinter** dem Fenster (vor dem zweiten `be40`-Ruf, wörtlich „vor be40“ wie im Nutzerauftrag vom 03.10. 12:51). Begründung: siehe Folge oben. Das Ziel „unter 5 min, gleicher Halt-PC, gleiche Schritte“ bleibt unverändert.
**Rückstufung (M256-1):** Die B255-Ursache („Folgenindex 4791 beim zweiten c3a8-Ruf“) ist STRONG INFERENCE, nicht CONFIRMED. Die Aufnahme `_m255/_sharc_auszug.txt:5-8` endet bei Schritt 199234649, der zweite Ruf liegt laut B255 bei 216571291. Der B255-Satz „A4 mit Fix nach 3096 s ohne Halt“ zählt nicht als Stationsbeleg (M256-2).

ARBEITSWEISE:
- Batch-Beginn nach `AGENTS.md`. `Get-Process hybrid_lauf,python` EINMAL notieren (nur lesen, nichts stoppen).
- Vorhersage-Commit `B257: Vorhersage` VOR jedem `port/`- und `scripts/`-Diff. Je Bilanzzeile gehören Sollwert und Zählerdefinition hinein. Messvorhersagen: welcher Schalter das Fenster verlangsamt, A4-Dauer nach Beschleunigung, Schritt und Index des 2. `c3a8`-Rufs.
- **JEDER `hybrid_lauf.exe`-Aufruf trägt `--wanduhr-grenze <s>` mit s ≤ 1500** (vorhanden: `port/hybrid/hybrid_lauf.cpp:38,172-209@0e3bcfe`; das Programm endet dann mit `WANDUHR-HALT <s> | im Kopf <adr> | Schritte <n>`). Den Werkzeugaufruf blockierend mit `timeout=1800000` starten. Das gilt auch für `preflight.py`, `port_build` und `c_kopf.py mutalle`: normaler Aufruf mit `timeout=1800000`.
- **Verboten** (ein Verstoß bricht den Batch ab): `Start-Process`, `Wait-Process`, Hintergrund, Warteschleifen und jedes Abräumen über `Get-Process`/Variable/Pipe. Mit Wanduhrgrenze ist kein Abräumen nötig. Falls doch, nur `Stop-Process -Id <wörtliche Zahl>` eines selbst gestarteten Prozesses.
- **Höchstens 2 Läufe über 600 s** im ganzen Batch (M256-4). Jeder Lauf bekommt eine Zeile in der Lauftafel des Batch-Dokuments: argv, Grenze, Wanduhr, erreichte Schritte, Ende (Halt/Schranke/WANDUHR-HALT).
- Cachedateien schreiben nur `m212_zeilen.py`/`m254_prewarm.py`. Hand-Kopie ist verboten.
- Belege als `Datei:Zeile@commit`. Rohläufe über 20 MB heißen `*_roh.txt`. „Blockiert“ nur mit Beleg (Zitat bzw. Grep auf den Bezeichner). Laufzeit ist keine Blockade. Gestrichen wird nur mit `Get-Date`-Zeile ab der Umschaltschwelle der Batch-Uhr.
- Modelle tragen die Kennzeichnung „Hybrid-Gerüst, im Port zu ersetzen“ und einen ROM-Beleg. Kein `disassemble_bytes` (R398).

TEIL 0 - Reste B256 sichern:
0a. Nach dem Vorhersage-Commit `_m256/_raten.txt`, `_m256_bau.txt` und `scripts/m256_raten.py` committen. Den Beleg im Batch-Dokument B257 nennen.
0b. Die B256-Schlüsselmessung (Quellen-SHA `08b1dddf…` roh gegen `cb6486b3…` B254; Körper gleich; Ursache CRLF in den rohen Bytes, `scripts/m212_zeilen.py:365@0e3bcfe`) mit einem kurzen Aufruf neu erzeugen und als `_m257/_schluessel.txt` ablegen.

TEIL 1 - Langsamfenster eingrenzen (nur messen, kein `port/`-Diff):
1a. **Schalter-Abzug:** Für die volle A4-argv (`scripts/m212_zeilen.py:468-471@0e3bcfe`) und für A4 jeweils OHNE einen der sechs Schalter (`--nativ-weiter`, `--ohne-schatten`, `--sharc-antwort`, `--stopp-bei-halt`, `--pcs`, `--kalibrierung`) einen Lauf mit `--schritte 216600000 --wanduhr-grenze 240 --kopf-zeit`. Tafel `_m257/_fenster.txt` mit erreichten Schritten, Wanduhr, `WANDUHR-HALT … im Kopf` und Kopf-Zeit-Zeile. Den Schalter (oder Kopf) benennen, ohne den das Fenster schnell wird.
1b. **Ortsauflösung:** Mit der vollen A4-argv drei Läufe mit `--wanduhr-grenze` 60/120/180, je Schritt und `im Kopf`. Daraus die Rate im Fenster (Schritte je s) und den Kopf bzw. die PC-Zone bestimmen, in der die Zeit vergeht. Eine reine Ausgabe- oder Messlast (z. B. `--pcs`, `--kalibrierung`, Schattenkopie) ist eine andere Ursachenklasse als ein langsamer nativer Kopf. Die Klasse benennen.
1c. **Nativer Anteil (M256-3b, NIE streichen):** Aus dem Abzugslauf „ohne `--ohne-schatten`“ (also mit Schatten) die Schattenschritte bei nativen Rufen und die Gesamtschritte über das erreichte Fenster als Messwert eintragen: `nativ <x> / <Schritte>` mit Schrittbereich. **Beide Zahlen** gehören in den B-Bericht. Die Zeile `Hybrid-Anteil nativ 57819/200000000` ist dabei die **Ersatzzahl** des Vorgabelaufs, kein A4-Wert.

TEIL 2 - Beschleunigen (nur wenn 1a/1b eine Ursache benennt):
2a. Den Mangel beheben, ohne die Ergebniszeile zu ändern (z. B. Messlast hinter einen Schalter, Kopie-/Vergleichsweg im Fenster abkürzen). Wenn es um einen nativen Kopf geht, das Ziel der Beschleunigung mit dem Ergebnis aus 1b belegen.
2b. **Gegenprobe:** Voller A4-Lauf mit `--wanduhr-grenze 1500`. Soll: 696571792 / 8001684C / Selbstsprung, `nativ_bis_dahin 1511`, identisch zu B254. Laufzeit vorher (1726 s, `_m254/_a4_vorwaermung.txt:2`) und nachher. Ziel unter 300 s.
2c. **Rotprobe:** Ein absichtlich falscher Wert (z. B. `--mutation` an einer Fensteradresse) muss eine abweichende Zeile ergeben.
Wenn 1a/1b keine Ursache benennen: dokumentieren, was ausgeschlossen ist, und mit TEIL 3 weitermachen.

TEIL 3 - M256-1 messen:
Mit `--stopp-bei-pc 8000C3A8 n` und `--stopp-bei-pc 8000C3E8 n` für n = 1, 2, 3 (Wanduhrgrenze ≤ 1500; nur sinnvoll, wenn TEIL 2 das Fenster schnell gemacht hat, sonst nur n = 2 an `8000C3A8` als einer der zwei langen Läufe) je Schritt und SHARC-Folgenindex bzw. `pending` erfassen. Fehlt eine Ausgabe des Index: Grep auf den Bezeichner in `port/hybrid/`. Danach eine Diagnosezeile hinter einem Schalter einbauen, gebündelt mit dem TEIL-2-Diff, damit es nur einen kalten Cachelauf gibt. Ergebnis: Die Ursache wird CONFIRMED oder widerlegt. Läuft der zweite Ruf NICHT durch `8000C3E8`, ist der Wirkpunkt des Fixes falsch. Das gehört dann als eigene Zeile ins Dokument.

TEIL 4 - Schlüssel, Vorwärmung, Preflight:
4a. **M256-6:** In `_cache_key` die Quellen LF-normalisiert hashen und argv ohne absoluten Arbeitsverzeichnispfad aufnehmen. Grünprobe: Nach CRLF→LF einer Quelle bleibt der Schlüssel gleich. Rotprobe: Ein geändertes Byte ändert den Schlüssel.
4b. Vorwärmung (`m254_prewarm.py`) nur, wenn 2b unter 1500 s gemessen ist; dann blockierend. Ist A4 nicht unter 1500 s: 4a NICHT einspielen, keine Vorwärmung. Der Preflight nimmt dann die vorhandene Datei, und das Dokument vermerkt „Herkunft: Kopie B255, keine Messung“.
4c. Preflight als einzige Zeile: `python -u scripts/preflight.py before *> analysis/_preflight_257.txt` (`timeout=1800000`), Ausgabe im Folgeaufruf lesen. Danach Bilanz `m149_bilanz.py --batch 257 --from-preflight analysis/_preflight_257.txt --write-anchor`. Nach dem Preflight nichts mehr unter `scripts/` ändern.

TEIL 5 - Abzug (nur wenn 2b nicht unter 300 s):
Abzug hinter dem Fenster, unmittelbar vor dem zweiten `8000C3A8`-Ruf (Schritt aus TEIL 3). Gegenprobe ab Abzug bis zum Halt identisch, Laufzeit vorher und nachher, Rotprobe (Folgenindex +1 → abweichende Zeile). Ablage gitignoriert unter `port/build/`, Größe und SHA im Beleg.

TEIL 6 - B-Bericht und Doku (Pflicht):
Ankerkopf auf **B257** fortschreiben: Ursache als STRONG INFERENCE (bzw. Ergebnis aus TEIL 3), Langsamfenster mit Rate und Ursachenklasse, Zählung nur aus B-Batches (B248, B249, B250, B255, B256, B257; Stationen 1) und „Serie 3 von 8, davon ohne neue Station m“. Die Fortschrittszahl nennt Schritte UND nativen Anteil (1c), keine Ersatzzahl als Fortschritt. Memory-Export, `git status` lesen, `analysis/ghidra-mcp-notes.md` mitcommitten (Bremse >50 Zeilen). Ankerblock mit `UEBERTRAG:`- und `GESCHLOSSEN`-Zeilen.

BATCH-ENDE:
`python -u scripts/m151_memory_sync.py export`, `git status` lesen, Commit `B257: …`. Abweichungen von der Vorhersage erklären.

FERTIG WENN: (a) B256-Reste committet; (b) Tafel `_m257/_fenster.txt` mit benanntem Schalter/Kopf und Ursachenklasse (oder dokumentierter Ausschluss); (c) nativer Anteil als Messwert mit Schrittbereich; (d) Schritt und Index des 2. `c3a8`-Rufs gemessen (M256-1 CONFIRMED oder widerlegt); (e) jeder `hybrid_lauf` mit Wanduhrgrenze, kein Lauf über 1800 s, kein Abräumen; (f) ein gültiger Preflight + Bilanz; (g) Ankerkopf auf B257.

STREICHREIHENFOLGE: 1. TEIL 5 (Abzug), 2. TEIL 4a+4b (Schlüssel/Vorwärmung; dann bleibt der Preflight auf der Kopie mit Vermerk), 3. TEIL 2c, 4. TEIL 3 n = 1 und 3 (n = 2 bleibt). NIE: Vorhersage-Commit, TEIL 0, TEIL 1a-1c, TEIL 3 n = 2, Preflight, Bilanz, Memory-Export, TEIL 6.

## NACHRUECKLISTE
1. TEIL 1a-1c; FERTIG WENN: `_m257/_fenster.txt` committet, Ursachenklasse benannt, nativer Anteil als `nativ x / Schritte` mit Bereich.
2. TEIL 3 n = 2; FERTIG WENN: Schritt und Folgenindex des 2. `8000C3A8`-Rufs gemessen, Ankerzeile CONFIRMED oder widerlegt.
3. TEIL 2a-2c; FERTIG WENN: A4-Gegenprobe identisch, Laufzeit vorher/nachher im Dokument, Rotprobe ROT, oder Ausschluss mit Beleg.
4. TEIL 4a/4b; FERTIG WENN: Schlüssel-Grünprobe und -Rotprobe, Vorwärmung blockierend unter 1500 s, Preflight „Treffer“ aus eigenem Lauf.
5. Fix `sharc_exchange_start` (B255 §4) hinter `--sharc-handschlag`, Vorgabe AUS, nur wenn TEIL 3 die Ursache bestätigt; FERTIG WENN: Kurzlauf mit Fix `be40` 2. Ruf = 0, ohne Fix = 2.
6. Formlücken `_m249/_formluecken.txt` (`19/0, 19/150, 27, 29, 31/26, 31/163, 31/412, 31/597, 31/725`); FERTIG WENN: je Form „verifiziert oder offen mit Grund“, mindestens eine geschlossen.
</DS_INSTRUCTION>
