**Review B261:** Inhaltlich der stärkste Batch der Serie. Drei Dinge sind nicht in Ordnung:
- Acht rohe Laufmitschnitte bis 432 MB wurden committet. Das hat den Push blockiert und eine Bereinigung der History erzwungen; fünf Dateien sind verloren.
- Die Preflight-Zeile vermischt zwei verschiedene Werte unter demselben Namen.
- Die Station ist nur schwach belegt.

B262 gleicht den Kommandostrom an der richtigen Stelle ab, belegt das Verlassen der Schleife und schaltet die neuen Dateigrößen-Wachen ein.

<TELEGRAM_SUMMARY>
Ergebnis:
- DCR-Halbtausch im Kern behoben: 70 von 107 Zugriffen hatten den falschen Index (`_m261/_dcr.txt`).
- Eingabe-Attrappe eingebaut, dazu `orc`, `wrteei` und `rfi`, je mit Rotprobe.
- `--vblank` ist jetzt Vorgabe EIN: 1926 Interrupts, 1207 Quittungen. A4 endet bei `900000000 | 80008448 | Schranke` (`_preflight_261c.txt:32`).
- Die Ausgabe des Kommandostroms ist gebaut. Präfix 1/1880, weil der Strom mit 16384 Nullwörtern beginnt und die Ausrichtung fehlt.
- Echter Messwert nativer Anteil: 1658360/900000000 (0,18 %).
Bewertung:
- Die Station gilt nur vorläufig. Als Beleg dient „Hauptschleife erreicht“, aber die wurde schon in B260 erreicht. Das Verlassen der Schleife (Flag-Schreiber, PC nach `while`) ist nicht gemessen.
- Die Preflight-Zeile führt „Anteil nativ NICHT GEMESSEN“ und „Anteil nativ 1658360“ nebeneinander. „referenzgleich ja“ misst nur, ob die Schattenrufe gleich sind, nicht ob die Schrittfolge gleich ist.
- Acht Rohdumps (213–432 MB) wurden committet. Der Push war blockiert, die History musste bereinigt werden, 5 Dumps sind verloren.
- Zum dritten Mal ein Sammelcommit.
FERTIG WENN erreicht: teilweise. (f) „ein Commit je Maßnahme“ nein, (d) Urteil zur Schrittfolge fehlt.
Kosten/Laufzeit: 0,255 $, 124 min, 192 Anfragen.
Nächster Batch: Strom ab dem ersten Kommando vergleichen und Abweichungen abarbeiten, Schleifenausstieg belegen, Preflight-Zeile berichtigen, Dateigrößen-Wachen einschalten.
B-SCHRITT: 4/5 Boot bis Hauptschleife, B-Batch 32 (Zählung, keine Grenze – Nutzerentscheid 30.09.)
M260-1: übernommen - Feld steht, misst aber nicht die Schrittfolge -> bleibt offen
M260-2: übernommen - Wirkung belegt: `_m261/_dcr_rot.txt`/`_dcr_gruen.txt`, `_m261/_dcr.txt`
M260-3: übernommen - Wirkung belegt: `_m261/_haltfolge.txt:8-10` (Halt 800237B4 überwunden)
M260-4: übernommen - Strom gebaut, Präfix ohne Ausrichtung 1/1880 -> bleibt offen
M260-6: übernommen - Wirkung belegt: `analysis/r1b-workstream.md:12` („Station: nein“ für B260)
UEBERTRAG: B261 TEIL 5a Zeitbasis im Schattenlauf -> B262 TEIL 3
ENTSCHIEDEN: Station B261 vorläufig (STRONG INFERENCE). Sie wird zurückgenommen, falls B262 TEIL 2 das Verlassen der Schleife nicht belegt.
ENTSCHIEDEN: Solange A4 an der Schranke endet, zählt als Station auch ein belegt gewachsener Strom-Präfix. Der Halt selbst bleibt unverändert definiert.
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: ghidra-read
program: /830d01.27p.main.bin
</DS_TOOLS>

## VERALLGEMEINERUNG

**F1: Rohdumps über 20 MB wurden committet (8 Dateien, bis 432 MB). Der Push war blockiert, die History musste bereinigt werden, 5 Belege sind verloren.**
- (a) Fehlerklasse: Eine Hausregel („`*_roh.txt` nicht tracken“) wirkt nur über die Benennung. Ein Treiberskript (`_m261/_lauf.py`) schrieb die Dumps unter anderen Namen.
- (b) Verwandte Fälle: jede Ausgabe von `hybrid_lauf` über ein Treiberskript, `--strom`- und `--pc-fenster`-Ausgaben. Prüfung in der Instruktion: Batch-Beginn mit `git config core.hooksPath scripts/hooks` (Wache pre-commit/pre-push). Batch-Ende mit `rohlauf_aufraeumen.py --komprimieren` und `check_dateigroesse.py --getrackt`, Ausgabe im Batch-Dokument.
- (c) Nicht geprüft: ob die fünf verlorenen Belege wiederherstellbar sind (die abgeleiteten Zahlen stehen in den Auszügen).

**F2: Ein Name für zwei Größen („Anteil nativ“ doppelt, „referenzgleich“ = Rufgleichheit statt Schrittfolge).**
- (a) Fehlerklasse: Etiketten sind nicht eindeutig, zum dritten Mal am nativen Anteil (B258, B259, B261).
- (b) Prüfung in TEIL 3: Die Felder heißen fest `Kalibriersumme`, `Anteil nativ (Schatten)`, `Schattenrufe gleich ja/nein`, `Schrittfolge gleich ja/nein` (Schritte und Halt-PC mit gegen ohne Schatten). Ich lese die Zeile im nächsten Review wörtlich nach.
- (c) Nicht geprüft: die 239931 nicht vergleichbaren Rufe (Host/Gerät).

**F3: Station mit einem Beleg, der nicht die Regel trifft.**
- (a) Fehlerklasse: Ein Ersatzbeleg wird statt des verlangten verwendet: „Hauptschleife erreicht“ statt „Schleife verlassen“.
- (b) Prüfung in TEIL 2: Schreibzugriff auf `0x800AEC63` (Schritt, PC, Wert 0) und der erste Schritt am PC nach der `while`-Schleife in `FUN_800089A0`, mit Rotprobe `--vblank-aus` (kein solcher Schritt).
- (c) Nicht geprüft: ob die Attract-Logik inhaltlich richtig läuft. Das misst der Stromvergleich.

**F4: Sammelcommit zum dritten Mal.**
- (a) Fehlerklasse: Eine Arbeitsregel ohne prüfbare Folge.
- (b) Die Regel wird jetzt Teil des FERTIG WENN: Ich zähle die Commits gegen die Zeilen der Haltfolge bzw. Abweichungsfolge. Ein Lauf nach einem unkommittierten Fix ist ein Befund.

<DS_INSTRUCTION>
Batch 262 - Silent Scope Decomp

STRANG: B
SOLL-KOEPFE: 0

STAND UEBERNEHMEN:
Strang B, B-Batch 33.
**Stillstandszähler 0 von 4, vorläufig:** Die Station B261 gilt erst, wenn TEIL 2 das Verlassen der Schleife belegt. Sonst wird sie zurückgenommen (Zähler 2 von 4).
Vorgabe seit B261 (`analysis/_preflight_261c.txt:32`, HEAD vor der History-Bereinigung `d305e76`; Zuordnung in `analysis/_m261/_commit_umschreibung.txt`): `--sharc-handschlag`, `--vblank` EIN, DCR-Halbtausch, IN0/IN1-Attrappe, `orc`/`wrteei`/`rfi`. A4: `900000000 | 80008448 | Schranke`, Hauptschleife ab 257126853, ~200 s.
Kommandostrom: `--strom` + `scripts/m261_stromvergleich.py`. Präfix 1/1880 gegen `capture/poc_ref_boot_0.txt`, weil die ersten 16384 Halbwörter Nullen sind; die Kommandos beginnen bei Index 0x4000 (PC `80009E30`, `analysis/_m261/_strom.txt`, Batch-Dokument B261).
**Neue Regeln seit B261 (`AGENTS.md`, Abschnitt „Zu grosse Dateien“):** Rohausgaben werden komprimiert (`scripts/rohlauf_komprimieren.py`). Nach jedem Batch läuft `scripts/rohlauf_aufraeumen.py`. Die Wache ist `scripts/check_dateigroesse.py` mit den Haken `scripts/hooks`. Anlass: B261 hatte acht Rohdumps bis 432 MB committet.
ENTSCHEIDUNG (Reviewer): Solange `Hybrid-A4` an der Schranke endet, zählt als Station auch ein belegt gewachsener Präfix im Kommandostrom-Vergleich (Vorgabe EIN, gültiger Preflight). Der Halt selbst bleibt unverändert definiert.

ARBEITSWEISE:
- Batch-Beginn nach `AGENTS.md`. Zusätzlich `git config core.hooksPath` lesen und, falls leer, `git config core.hooksPath scripts/hooks` setzen; im Dokument vermerken. `Get-Process hybrid_lauf,python` EINMAL notieren, nichts stoppen.
- Vorhersage-Commit `B262: Vorhersage` VOR jedem `port/`/`scripts/`-Diff, mit Sollwert und Zählerdefinition je Bilanzzeile sowie dem erwarteten Präfix nach der Ausrichtung.
- **Commit-Pflicht als Prüfpunkt:** Nach jeder Maßnahme (Fix, Modell, Werkzeug) erst committen, dann den nächsten Lauf starten. Ich zähle im Review die Commits gegen die Zeilen von `_m262/_abweichungen.txt` bzw. `_m262/_haltfolge.txt`; ein Lauf auf einem nicht committeten Fix ist ein Befund.
- **Rohausgaben:** Jede Ausgabe über 20 MB heißt `*_roh.txt`, liegt nie im Index und wird nach Gebrauch mit `python scripts/rohlauf_komprimieren.py <pfad>` gesichert. Ins Repo kommen nur Auszüge.
- Läufe über 20M Schritte tragen `--wanduhr-grenze` ≤ 1500, blockierend mit `timeout=1800000` (auch Preflight, `port_build`). Verboten: `Start-Process`, `Wait-Process`, Hintergrund, Warteschleifen, Abräumen über `Get-Process`/Variable/Pipe. `--pc-fenster` höchstens 1M.
- Grep-Pflicht (R13az) je Abweichung und Halt: PC, Funktionsadresse, Aufrufer in `analysis/`, `port/` und `mame/mame/src/`, mit Fundstelle. Modelle tragen „Hybrid-Gerüst, im Port zu ersetzen“, ROM- und MAME-Beleg und einen Gegenschalter.
- Belege als `Datei:Zeile@commit`. Preflight als einzige Zeile `python -u scripts/preflight.py before *> analysis/_preflight_262.txt`, ohne weitere Befehle in derselben Zeile. Der Batch endet nicht vor der Umschaltschwelle, solange ein Posten offen ist.

TEIL 1 - Kommandostrom ausgerichtet vergleichen (Hauptarbeit, NIE streichen):
1a. Die Referenz prüfen: Enthält `poc_ref_boot_0..3.txt` die Nullfüllung nicht, oder ist sie dort anders kodiert? (Kopf der Datei, `poc/stream_consumer/main.cpp`, Fundstellen.) Die Ausrichtungsregel festlegen und begründen, z. B. „ab dem ersten Halbwort ≠ 0“ oder „ab Index 0x4000“.
1b. `m261_stromvergleich.py` um `--versatz`/`--ab-erstem-kommando` erweitern (neues Skript `scripts/m262_stromvergleich.py` oder Schalter). Ausgabe: Präfixlänge, erste Abweichung (Index, erwartet gegen geliefert, Producer-PC), dazu die Zahl der gleichen Halbwörter insgesamt. Rotprobe: ein verfälschtes Halbwort ergibt einen kürzeren Präfix. Reicht die Stromausgabe nicht bis zum Ende der Referenz, die Grenze von 65536 anheben.
1c. **Abweichungsfolge** in `_m262/_abweichungen.txt`, wie die Haltfolge: je erster Abweichung die Klasse (Kern-Form / Modell / Zeitbasis / Reihenfolge), die Fundstelle (Producer-PC → Funktion → Grep) und die Maßnahme, dann Fix, Rotprobe, **Commit**, neuer Vergleich. Wiederholen bis zur Umschaltschwelle oder bis zu einer belegten Stopp-Bedingung. Lässt sich eine Abweichung nicht ohne neues Material klären: Zeile mit Grep-Beleg und `WARTET AUF LIVE-AUFNAHME`-Kandidat. Danach `poc_ref_boot_1..3` auf dieselbe Weise.

TEIL 2 - Schleifenausstieg belegen (Station B261):
2a. In `FUN_800089A0` (`decompile_function`/`disassemble_function`) den PC unmittelbar nach der `while (Flag)`-Schleife bestimmen.
2b. Lauf mit Vorgabe (Wanduhr ≤ 600): erster Schreibzugriff mit Wert 0 auf `0x800AEC63` (Schritt, PC, aus welcher Funktion) und erster Schritt am Ausstiegs-PC. Rotprobe `--vblank-aus`: kein Ausstieg. Ergebnis `_m262/_schleife_aus.txt`. Ohne Beleg wird die Station B261 im Anker zurückgenommen („Station: nein, Zähler 2 von 4“).

TEIL 3 - Preflight-Zeile eindeutig (M260-1):
3a. Feste Feldnamen in `Hybrid-A4`: `Kalibriersumme <n> (Untergrenze, <k> Rufe ohne Wert)` statt „Anteil nativ NICHT GEMESSEN (…)“; `Anteil nativ (Schatten) x/Schritte`; `Schattenrufe gleich ja/nein` statt „referenzgleich“; neu `Schrittfolge gleich ja/nein` (Schritte und Halt-PC mit gegen ohne Schatten).
3b. Ursache der Schrittverschiebung beseitigen, wenn möglich (B261: `schritte += s` im Schattenweg; die Zeitbasis mit Kalibrierwerten statt Schattenschritten führen, ohne den Schattenzähler zu ändern). Soll: `Schrittfolge gleich ja`. Gelingt das nicht: `nein` mit der gemessenen Verschiebung.

TEIL 4 - Vorwärmung, Preflight, Bilanz, Aufräumen, Anker:
4a. Vorwärmung blockierend, Preflight, `m149_bilanz.py --batch 262 --from-preflight analysis/_preflight_262.txt --write-anchor`. Nach dem Preflight nichts mehr unter `scripts/` ändern.
4b. `python scripts/rohlauf_aufraeumen.py --komprimieren` und `python scripts/check_dateigroesse.py --getrackt`. Beide Ausgaben als Auszug ins Batch-Dokument. Keine getrackte Datei über 20 MB.
4c. Ankerkopf B262 mit:
- Preflight-HEAD aus Zeile 3,
- Stationszeile in fester Form (Regel, Beleg: Halt oder Präfix oder Schleifenausstieg),
- Stillstandszähler,
- Präfix je `poc_ref_boot_0..3`,
- Feldwerte aus TEIL 3,
- „Nächster Schritt“ mit Batch-Nummer 263.
Memory-Export, `git status` lesen, `ghidra-mcp-notes.md` mitcommitten (Bremse >50 Zeilen), Ankerblock mit `UEBERTRAG:`/`GESCHLOSSEN`.

BATCH-ENDE:
`python -u scripts/m151_memory_sync.py export`, `git status` lesen, Commit `B262: …`. Abweichungen von der Vorhersage erklären.

FERTIG WENN: (a) ausgerichteter Stromvergleich mit Präfixlänge und erster Abweichung für `poc_ref_boot_0`, Rotprobe ROT; (b) `_m262/_abweichungen.txt` mit mindestens einer bearbeiteten Abweichung (Fix + Rotprobe + eigener Commit) oder belegter Stopp-Bedingung; (c) `_m262/_schleife_aus.txt` mit Flag-Schreiber und Ausstiegs-PC plus Rotprobe, oder Station B261 zurückgenommen; (d) `Hybrid-A4` mit den festen Feldnamen aus TEIL 3 und `Schrittfolge gleich ja/nein`; (e) gültiger Preflight + Bilanz; (f) Aufräumen + Größenwache im Dokument, keine getrackte Datei über 20 MB; (g) Commits je Maßnahme nachweisbar.

STREICHREIHENFOLGE: 1. `poc_ref_boot_1..3` in TEIL 1c, 2. weitere Abweichungen in 1c nach der ersten, 3. TEIL 3b (die Feldnamen aus 3a bleiben Pflicht). NIE: Vorhersage-Commit, Hooks-Prüfung, TEIL 1a-1b, erste Abweichung in 1c, TEIL 2, TEIL 3a, Preflight, Bilanz, TEIL 4b, Memory-Export, Ankerkopf.

## NACHRUECKLISTE
1. TEIL 1a/1b Ausrichtung; FERTIG WENN: Ausrichtungsregel mit Fundstelle, Vergleichsskript mit Versatz committet, `_m262/_strom.txt` mit Präfix und erster Abweichung, Rotprobe ROT.
2. TEIL 2 Schleifenausstieg; FERTIG WENN: `_m262/_schleife_aus.txt` mit Schreibzugriff auf `0x800AEC63`, Ausstiegs-PC und Rotprobe `--vblank-aus`, oder Station B261 im Anker zurückgenommen.
3. TEIL 1c erste Abweichung; FERTIG WENN: Zeile in `_m262/_abweichungen.txt` mit Klasse, Fundstelle, Maßnahme, Rotprobe und eigenem Commit, danach neuer Präfix.
4. TEIL 3a Feldnamen; FERTIG WENN: Preflight-Zeile `Hybrid-A4` mit `Kalibriersumme`, `Anteil nativ (Schatten)`, `Schattenrufe gleich`, `Schrittfolge gleich`.
5. TEIL 4b Aufräumen; FERTIG WENN: Auszüge von `rohlauf_aufraeumen.py --komprimieren` und `check_dateigroesse.py --getrackt` im Dokument, keine getrackte Datei über 20 MB.
6. TEIL 1c weitere Abweichungen + `poc_ref_boot_1..3` + TEIL 3b; FERTIG WENN: je Abweichung Zeile und Commit, Präfix je Referenzdatei, `Schrittfolge gleich ja` oder gemessene Verschiebung.
</DS_INSTRUCTION>
