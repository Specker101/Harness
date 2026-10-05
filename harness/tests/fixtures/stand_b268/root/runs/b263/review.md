**Review B262:** Das FERTIG WENN ist erreicht, und der Batch war sauber: 22 Commits, je ein Commit pro Maßnahme, keine Rohdatei im Repo. Das Verlassen der Schleife ist jetzt belegt, mit Rotprobe; die Station B261 gilt damit. Der Präfix stieg von 1 auf 25, weil der Vergleich jetzt das richtige Format nutzt.

Die Blockade „Material fehlt“ für die erste echte Abweichung stimmt aber nicht. Die MAME-Logs mit dem schreibenden PC je Zugriff liegen im Repo. Darin schreiben andere Funktionen das Wort als im Hybrid. Der Hybrid vergleicht also vermutlich ein anderes Bild bzw. einen anderen Codepfad. Wegen dieser falschen Blockade endete der Batch schon nach 77 min.

<TELEGRAM_SUMMARY>
Ergebnis:
- Station B261 belegt: Das Flag wird bei Schritt 257601058 aus `FUN_80008748` auf null gesetzt, der Ausstieg bei `80008ABC` folgt bei Schritt 257859943. Mit `--vblank-aus` gibt es keinen Ausstieg (`_m262/_schleife_aus.txt`).
- Kommandostrom: `--strom` ist jetzt ein adressindiziertes Speicherbild wie die Referenz. Präfix 1 → 25/1880, Wörter 0x01–0x0C gleich, Rotprobe ROT.
- Die Preflight-Zeile hat eindeutige Feldnamen. Die Ausgabe `nach_rueckkehr` (337 MB) ist begrenzt.
- 22 Commits, je Maßnahme einer. Keine Datei über 20 MB.
Bewertung:
- Befund: A2 als „WARTET AUF LIVE-AUFNAHME“ blockiert, mit falschem Grund. `capture/error_boot_f0.log:1711951,1711957` zeigt die MAME-Schreiber von Wort 0x0D: `80017D64` (0003) und `80018218` (0100). Im Hybrid schreibt `800184B4` (`FUN_8001832C`). Es geht um einen anderen Pfad bzw. ein anderes Bild, und das Material liegt vor. Deshalb endete der Batch bei 77 von 135 min.
- Der Präfix stieg durch eine Werkzeugkorrektur. Das ist kein Fortschritt des ROM-Laufs.
FERTIG WENN erreicht: ja, aber mit falscher Blockade bei der Abweichungsfolge.
Kosten/Laufzeit: 0,236 $, 103 min, 167 Anfragen.
Nächster Batch: Referenz mit MAME-Schreib-PCs aus `error_boot_f*.log`, Hybrid-Strom je Bild, passendes Bild finden, Abweichungen abarbeiten.
B-SCHRITT: 4/5 Boot bis Hauptschleife, B-Batch 33 (Zählung, keine Grenze – Nutzerentscheid 30.09.)
UEBERTRAG: A2 Wort 0x0D -> B263 TEIL 1-3
VERWORFEN: TEIL 3b-Rest „Schrittfolge gleich ja“. Die Restverschiebung kommt von 392238 Rufen ohne Kalibrierwert. Gleichheit hieße, den Schattenzähler, also das Zielmaß selbst, aufzugeben. „nein“ mit gemessener Verschiebung bleibt stehen.
ENTSCHIEDEN: Station B261 bestätigt. B262 ist keine Station, Stillstandszähler 1 von 4.
ENTSCHIEDEN: Ein gewachsener Strom-Präfix zählt nur als Station, wenn er aus einer Kern- oder Modelländerung stammt, nicht aus einer Änderung am Vergleichswerkzeug.
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: ghidra-read
program: /830d01.27p.main.bin
</DS_TOOLS>

## VERALLGEMEINERUNG

**F1: Falsche Blockade „Material fehlt“ (A2), obwohl die MAME-Logs mit Schreib-PCs im Repo liegen.**
- (a) Fehlerklasse: R13az b. Die Grep-Pflicht wurde nur auf `analysis/`, `port/` und `mame/` angewendet, nicht auf `capture/`. Die Referenzdatei wurde ohne ihre Quelle gelesen.
- (b) Verwandte Fälle: jede Abweichung gegen `poc_ref_*` (Quelle `capture/error_*.log`), jeder „fehlt“-Befund zu Laufdaten. Prüfung in der Instruktion: Die Grep-Pflicht umfasst `capture/`. Jede Referenzzeile wird mit Schreib-PC und Log-Zeile aus der Quell-Log belegt. „WARTET AUF LIVE-AUFNAHME“ braucht den Grep-Beleg „nicht in capture/“.
- (c) Nicht geprüft: ob die MAME-Logs vollständig sind (Bankwechsel, Board 1).

**F2: Präfixwachstum durch eine Werkzeugkorrektur.**
- (a) Fehlerklasse: Messgröße gegen Zielgröße. Der Präfix misst auch die Güte des Vergleichers, nicht nur den Hybrid.
- (b) Prüfung: Eine Station über den Präfix zählt nur, wenn der Commit unter `port/hybrid/` Kern oder Modelle ändert. Werkzeugänderungen werden im Dokument getrennt ausgewiesen.
- (c) Nicht geprüft: ob die Referenz selbst bildgenau ist.

**F3: Bildvergleich ohne Bildzuordnung.** Der Hybrid vergleicht sein Endbild bei 900M gegen ein einzelnes MAME-Bild nach dem Auslöser `POC-DUMP-DONE`.
- (a) Fehlerklasse: Zeitpunkte werden verglichen, ohne gleichgesetzt worden zu sein.
- (b) Prüfung in TEIL 2: Der Hybrid-Strom wird an den Bildmarken (`78000000` HIGH = `0002`, wie `scripts/ppc_poc_refstream.py:49-51`) in Bilder zerlegt. Je Bild gibt es eine Schreib-PC-Folge, gesucht wird das Bild mit dem längsten Präfix.
- (c) Nicht geprüft: Bank 1 und Board 1.

<DS_INSTRUCTION>
Batch 263 - Silent Scope Decomp

STRANG: B
SOLL-KOEPFE: 0

STAND UEBERNEHMEN:
Strang B, B-Batch 34. **Stillstandszähler 1 von 4.** B261 ist durch `_m262/_schleife_aus.txt@225a9c9` als Station bestätigt, B262 ist keine Station: der Präfix stieg durch eine Werkzeugkorrektur.
Vorgabe: `Hybrid-A4 900000000 | 80008448 | Schranke`, Hauptschleife ab 257126853, Schleifenausstieg `80008ABC` bei 257859943 (`analysis/_preflight_262.txt`, HEAD `3f42461`).
Strom: `--strom` ist ein adressindiziertes Speicherbild. `scripts/m262_stromvergleich.py` liefert Präfix 25/1880 gegen `capture/poc_ref_boot_0.txt`, Wörter 0x01–0x0C gleich (`_m262/_wortvergleich.txt`).
**A2 ist nicht blockiert (R13az, Fehlstelle geklärt):**
- Die Referenz stammt aus `capture/error_boot_f0.log` (Kopf `poc_ref_boot_0.txt:1` „trigger line 1711923“, Erzeuger `scripts/ppc_poc_refstream.py`).
- Dort schreiben Wort 0x0D (`78000034`) die PCs **`80017D64`** (HIGH `0003`, Zeile 1711951) und **`80018218`** (LOW `0100`, Zeile 1711957).
- Der Hybrid schreibt es aus `800184B4` (`FUN_8001832C`).
- Der Hybrid läuft also an dieser Stelle einen anderen Pfad oder vergleicht ein anderes Bild. Belegt ist das durch `poc/stream_consumer/main.cpp:178-181`: „das 37-Wort-Paket von FUN_8001832c gilt im Gameplay-Frame nicht“.
- Weitere MAME-Bildlogs: `capture/error_boot_f1..f3.log`, `capture/error_poc_f*.log`.
ENTSCHEIDUNG (Reviewer): Ein gewachsener Präfix zählt nur als Station, wenn er aus einem Commit unter `port/hybrid/` stammt, der Kern oder Modelle ändert (Vorgabe EIN, gültiger Preflight).
ENTSCHEIDUNG (Reviewer): „Schrittfolge gleich nein“ bleibt mit gemessener Verschiebung stehen. Gleichheit würde den Schattenzähler aufgeben, also das Zielmaß.

ARBEITSWEISE:
- Batch-Beginn nach `AGENTS.md`. `git config core.hooksPath` muss `scripts/hooks` sein. `Get-Process hybrid_lauf,python` EINMAL notieren, nichts stoppen.
- Vorhersage-Commit `B263: Vorhersage` VOR jedem `port/`/`scripts/`-Diff, mit Sollwert und Zählerdefinition je Bilanzzeile sowie der Vorhersage, welches Hybrid-Bild zu `boot_f0` passt.
- Je Maßnahme bauen, messen, committen, dann weiter (wie in B262 gut umgesetzt).
- **Grep-Pflicht (R13az) umfasst jetzt auch `capture/`:** Jede Referenzabweichung wird mit Schreib-PC und Log-Zeile aus der Quell-Log belegt. „WARTET AUF LIVE-AUFNAHME“ nur mit `Fehlstelle: gesucht in capture/, analysis/, port/, nicht gefunden (Grep "<Bezeichner>")`. Eine solche Blockade beendet nur den Posten, nicht den Batch.
- Rohausgaben über 20 MB heißen `*_roh.txt` und werden nur komprimiert gesichert. Läufe über 20M Schritte tragen `--wanduhr-grenze` ≤ 1500, blockierend mit `timeout=1800000` (auch Preflight, `port_build`). Verboten: `Start-Process`, `Wait-Process`, Hintergrund, Warteschleifen, Abräumen über `Get-Process`/Variable/Pipe.
- Werkzeugänderungen (Vergleicher, Ausgabeformat) und Hybrid-Änderungen (Kern/Modelle) stehen im Dokument in getrennten Tafeln.
- Belege als `Datei:Zeile@commit`. Preflight als einzige Zeile `python -u scripts/preflight.py before *> analysis/_preflight_263.txt`. Der Batch endet nicht vor der Umschaltschwelle, solange ein Posten bearbeitbar ist.

TEIL 1 - Referenz mit Schreib-PCs:
1a. Skript `scripts/m263_ref_pcs.py` (R355): Aus `capture/error_boot_f0..f3.log` und denselben Regeln wie `ppc_poc_refstream.py` (Auslöser, Bildmarke, Board 0, `0x78000000..0x7800FFFF`) je Halbwort Wert, Schreib-PC, Bank und Log-Zeile ausgeben, nach `_m263/_ref_pcs_f0..f3.txt`. Gegenprobe: Die Werte sind zeichengleich zu `poc_ref_boot_0..3.txt`.
1b. Zu den PCs `80017D64`, `80018218` und den übrigen Schreib-PCs der ersten 64 Wörter die Funktion bestimmen (`get_function_by_address`, Grep in `analysis/`/`port/`). Tafel: Funktion, Aufrufer, Port-Fundstelle.

TEIL 2 - Hybrid-Strom je Bild:
2a. `--strom` um Schreib-PC je Halbwort und eine Zerlegung an der Bildmarke erweitern (`78000000` HIGH `0002`, wie `ppc_poc_refstream.py:49-51`). Ausgabe je Bild: Bildnummer, Schritt, Speicherbild und PC-Folge. Kurzlauf zeichengleich zu B262 (Bild am Laufende = B262-Bild).
2b. Vergleicher `scripts/m263_bildsuche.py`: Für jedes Hybrid-Bild Präfixlänge und Übereinstimmung der Schreib-PC-Folge gegen `_ref_pcs_f0`; das beste Bild mit Bildnummer und Schritt. Rotprobe: ein verfälschtes Bild verliert den Spitzenplatz.
2c. Was im MAME-Lauf den Auslöser `POC-DUMP-DONE` setzt und welches Bild `boot_f0..f3` sind: Grep in `capture/`, `scripts/` und `analysis/` (u. a. `analysis/cgrom-upload-batch35-2026-09-17.md:146`). Ergebnis als Zeile im Dokument.

TEIL 3 - Abweichungsfolge auf dem passenden Bild:
3a. Mit dem besten Bild aus 2b die erste Abweichung bestimmen. Klasse (Pfad/Verzweigung, Kern-Form, Modell, Zeitbasis), Schreib-PC Hybrid gegen MAME, die Verzweigung, an der die Pfade auseinandergehen (Ghidra, Bedingung, gelesene Adresse), dann Maßnahme, Rotprobe und eigener Commit. Fortsetzen in `_m263/_abweichungen.txt` bis zur Umschaltschwelle.
3b. Ist A2 (Wort 0x0D) nach der Bildzuordnung verschwunden, wird es als „Bildzuordnung“ geschlossen.

TEIL 4 - Preflight, Bilanz, Aufräumen, Anker:
Vorwärmung blockierend, Preflight, `m149_bilanz.py --batch 263 --from-preflight analysis/_preflight_263.txt --write-anchor` (nie durch eine Pipe). Nach dem Preflight nichts mehr unter `scripts/` ändern. `rohlauf_aufraeumen.py --komprimieren` und `check_dateigroesse.py --getrackt` als Auszug ins Dokument.
Ankerkopf B263 mit:
- Preflight-HEAD aus Zeile 3,
- Stationszeile in fester Form (Regel und Beleg; Präfix nur aus Hybrid-Commit),
- Stillstandszähler,
- bestes Bild und Präfix je `boot_f0..f3`,
- „Nächster Schritt“ mit Batch-Nummer 264.
Memory-Export, `git status` lesen, `ghidra-mcp-notes.md` mitcommitten (Bremse >50 Zeilen), Ankerblock mit `UEBERTRAG:`/`GESCHLOSSEN`.

BATCH-ENDE:
`python -u scripts/m151_memory_sync.py export`, `git status` lesen, Commit `B263: …`. Abweichungen von der Vorhersage erklären.

FERTIG WENN: (a) `_m263/_ref_pcs_f0..f3.txt` mit Werten zeichengleich zur Referenz und Schreib-PCs; (b) Hybrid-Strom je Bild mit PC-Folge, Kurzlauf zeichengleich zu B262; (c) Bildsuche mit bestem Bild (Nummer, Schritt, Präfix) und Rotprobe; (d) mindestens eine Abweichung auf dem passenden Bild mit Klasse, Verzweigungsstelle, Maßnahme, Rotprobe und eigenem Commit, oder belegte Stopp-Bedingung mit Grep über `capture/`; (e) gültiger Preflight + Bilanz, Aufräumen und Größenwache im Dokument; (f) Ankerkopf mit Stationszeile und Stillstandszähler.

STREICHREIHENFOLGE: 1. `f1..f3` in TEIL 1a/2b über `f0` hinaus, 2. weitere Abweichungen in 3a nach der ersten, 3. TEIL 2c. NIE: Vorhersage-Commit, TEIL 1a für `f0`, TEIL 1b, TEIL 2a-2b, erste Abweichung in 3a, Preflight, Bilanz, Aufräumen, Memory-Export, Ankerkopf.

## NACHRUECKLISTE
1. TEIL 1a/1b Referenz-PCs; FERTIG WENN: `scripts/m263_ref_pcs.py` und `_m263/_ref_pcs_f0.txt` committet, Gegenprobe zeichengleich, Funktionstafel der Schreib-PCs.
2. TEIL 2a Strom je Bild; FERTIG WENN: `--strom` mit PC je Halbwort und Bildzerlegung committet, Kurzlauf zeichengleich zu B262.
3. TEIL 2b Bildsuche; FERTIG WENN: `scripts/m263_bildsuche.py` und `_m263/_bildsuche.txt` mit bestem Bild, Präfix und Rotprobe.
4. TEIL 3a erste Abweichung; FERTIG WENN: Zeile in `_m263/_abweichungen.txt` mit Klasse, Verzweigungsstelle, Maßnahme, Rotprobe und eigenem Commit, oder Stopp-Bedingung mit Grep über `capture/`.
5. TEIL 4 Abschluss; FERTIG WENN: gültiger Preflight, Bilanz, Aufräum- und Größenwache-Auszug, Ankerkopf B263 mit Stationszeile.
6. TEIL 3a weitere + `f1..f3` + 2c; FERTIG WENN: je Abweichung Zeile und Commit, Präfix je Referenzbild, Auslöserzeile im Dokument.
</DS_INSTRUCTION>
