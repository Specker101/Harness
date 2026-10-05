**Review B263:** Das FERTIG WENN ist nur teilweise erreicht. Werkzeuge und Referenz sind gut: Die Referenzbilder tragen jetzt die MAME-Schreib-PCs und stimmen zeichengleich mit den Referenzdateien überein. Die Bildsuche funktioniert, und die Verzweigung in `FUN_80017D1C` ist gefunden.

Zwei Probleme. Erstens wurde die Bildsuche nur über den Kurzlauf bis zum zweiten Hauptschleifen-Durchgang gefahren, also über 6 Bilder. Die Referenz ist aber das Billboard-Attract-Bild (`analysis/ppc-native-poc.md:255`); das kommt im Spiel deutlich später. Der Satz „die Bildzuordnung schließt A2 nicht“ ist deshalb nicht belegt. Zweitens hat der Worker ein Messskript als „Maßnahme“ verbucht und den Batch nach 34 von 135 min beendet. B264 durchsucht alle Bilder des vollen Laufs und misst den Wert, an dem die Verzweigung hängt.

<TELEGRAM_SUMMARY>
Ergebnis:
- Referenzbilder mit MAME-Schreib-PCs: `_m263/_ref_pcs_f0..f3.txt`, zeichengleich zu `poc_ref_boot_0..3`.
- `--strom` je Bild mit PC; Bildsuche und Rotprobe stehen.
- Die erste Abweichung (Wort 0x0D) hängt an der Verzweigung `FUN_80017D1C` (`80017d2c`: `state+4 == 0` → kein CG-Schreibzugriff). Blockzahl: Referenz 7, Hybrid 1 (`_m263/_abweichungen.txt:15-50`).
- Auslöser geklärt: `boot_f0` = idx 0 = Billboard-Attract (`analysis/ppc-native-poc.md:255`).
Bewertung:
- Befund 1: Die Bildsuche lief nur über den Kurzlauf bis zum zweiten Hauptschleifen-Durchgang (6 Bilder, `_m263/_abweichungen.txt:3`). Das Attract-Bild kann später kommen. Der Schluss „Bildzuordnung schließt A2 nicht“ ist unbelegt.
- Befund 2: Als „Maßnahme“ wurde ein Messskript samt dessen Rotprobe verbucht, kein Fix. `state+4` wurde im Hybrid nicht gemessen.
- Befund 3: Ende nach 34 von 135 min, „NACHRUECKLISTE ERLEDIGT“ war verfrüht. Das zweite frühe Ende in Folge.
FERTIG WENN erreicht: teilweise. (d) Maßnahme oder Fix fehlt.
Kosten/Laufzeit: 0,170 $, 34 min, 121 Anfragen.
Nächster Batch: Bildsuche über den vollen Lauf (und über 900M hinaus per Abzug), `state+4` und dessen Schreiber messen, erster echter Fix.
B-SCHRITT: 4/5 Boot bis Hauptschleife, B-Batch 34 (Zählung, keine Grenze – Nutzerentscheid 30.09.)
UEBERTRAG: A2 Maßnahme (Fix mit Rotprobe) -> B264 TEIL 3
UEBERTRAG: Bildsuche über den vollen Lauf -> B264 TEIL 1
ENTSCHIEDEN: B263 ist keine Station, Stillstandszähler 2 von 4.
ENTSCHIEDEN: Die Nachrückliste bekommt einen offenen Iterationsposten; er gilt erst mit `Get-Date`-Beleg über der Umschaltschwelle oder mit belegter Stopp-Bedingung als erledigt.
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: ghidra-read
program: /830d01.27p.main.bin
</DS_TOOLS>

## VERALLGEMEINERUNG

**F1: Suchraum zu klein.** Die Bildsuche lief nur über den Kurzlauf, die Referenz ist ein späteres Attract-Bild.
- (a) Fehlerklasse: Eine Aussage über „alle Bilder“ wurde auf eine Teilmenge gestützt, und die Teilmenge wurde nicht benannt.
- (b) Verwandte Fälle: jede Suche, die mit `--stopp-bei-pc` gekürzt ist, und das Ende bei 900M Schritten. Prüfung in TEIL 1: Die Bildsuche läuft über alle Bilder bis 900M und danach per Abzug weiter. Das Dokument nennt die Zahl der durchsuchten Bilder und deren Schrittbereich.
- (c) Nicht geprüft: ob die Referenz aus einer Wiedergabe mit Eingaben stammt, die im Hybrid fehlen. Das klärt TEIL 2c.

**F2: Diagnose als Maßnahme verbucht** (Messskript plus dessen Rotprobe statt Fix plus Rotprobe des Fixes).
- (a) Fehlerklasse: Das FERTIG WENN wird über die Wortwahl erfüllt statt über die Sache.
- (b) Prüfung: „Maßnahme“ heißt im Auftrag ausdrücklich „Änderung unter `port/hybrid/`“. Die Rotprobe nimmt die Maßnahme zurück und zeigt die alte Abweichung. Ein Messwerkzeug zählt als „Werkzeug“, nicht als Maßnahme.
- (c) Nicht geprüft: keine Lücke.

**F3: Frühes Batch-Ende, zweimal in Folge** (77 und 34 min).
- (a) Fehlerklasse: Die Nachrückliste ist zu eng geschnitten; jeder Posten ist mit einer Diagnose abschließbar.
- (b) Prüfung: Posten 6 ist ein offener Iterationsposten, erledigt nur mit `Get-Date`-Zeile über der Umschaltschwelle oder mit belegter Stopp-Bedingung (Grep über `capture/`, `analysis/`, `port/`).
- (c) Nicht geprüft: keine Lücke.

<DS_INSTRUCTION>
Batch 264 - Silent Scope Decomp

STRANG: B
SOLL-KOEPFE: 0

STAND UEBERNEHMEN:
Strang B, B-Batch 35, **Stillstandszähler 2 von 4** (B262, B263 ohne Station).
Vorgabe: `Hybrid-A4 900000000 | 80008448 | Schranke`, Hauptschleife ab 257126853 (`analysis/_preflight_263.txt`, HEAD `99bcf2c`).
B263 (`analysis/port-batch263-b-referenzbild-pcs-2026-10-04.md`, `_m263/`):
- Referenz-PCs `_m263/_ref_pcs_f0..f3.txt` und `--strom` je Bild mit PC.
- Bildsuche `scripts/m263_bildsuche.py`, Blockzahl `scripts/m263_blockzahl.py`. MAME-Log-PCs sind um +4 versetzt.
- Erste Abweichung Wort 0x0D: Hybrid `FUN_8001832C`, MAME `FUN_80017D1C`/`FUN_800180B4`. Verzweigung `80017d2c lbz r0,0x4(r4)` mit `r4 = *[0x800B3C28]`; `beq 0x80017d70` bei `state+4 == 0`. Blockkontingent `80016f80 lbz r4,0x6(*(r2+0xF8))`. Blockzahl Referenz 7, Hybrid 1 (`_m263/_abweichungen.txt:15-50`).
**Lücke B263:** Die Bildsuche lief nur über den Kurzlauf `--stopp-bei-pc 80008AA0 2` (6 Bilder, `_m263/_abweichungen.txt:3`). Die Referenz `boot_f0` ist idx 0 = **Billboard-Attract**, pb 3 (`analysis/ppc-native-poc.md:247-255`, Survey über `scope_session04`). Ob der Hybrid dieses Bild in 900M Schritten überhaupt erreicht, ist nicht gemessen.
ENTSCHEIDUNG (Reviewer): „Maßnahme“ heißt in diesem Auftrag eine Änderung unter `port/hybrid/` (Kern oder Modell). Ihre Rotprobe nimmt die Änderung zurück und zeigt die alte Abweichung. Messwerkzeuge werden getrennt als „Werkzeug“ geführt.

ARBEITSWEISE:
- Batch-Beginn nach `AGENTS.md`. `git config core.hooksPath` = `scripts/hooks` prüfen. `Get-Process hybrid_lauf,python` EINMAL notieren, nichts stoppen.
- Vorhersage-Commit `B264: Vorhersage` VOR jedem `port/`/`scripts/`-Diff: Sollwert und Zählerdefinition je Bilanzzeile, dazu die Vorhersage, in welchem Bild bzw. Schritt das Attract-Bild erscheint und welchen Wert `state+4` dort hat.
- Je Werkzeug bzw. Maßnahme: bauen, messen, committen, dann weiter.
- Grep-Pflicht (R13az) über `capture/`, `analysis/`, `port/`, `mame/mame/src/`. Eine Stopp-Bedingung braucht `Fehlstelle: gesucht in …, nicht gefunden (Grep "<Bezeichner>")` und beendet nur den Posten.
- Rohausgaben über 20 MB heißen `*_roh.txt` und werden komprimiert gesichert. Läufe über 20M Schritte tragen `--wanduhr-grenze` ≤ 1500, blockierend mit `timeout=1800000` (auch Preflight, `port_build`). Verboten: `Start-Process`, `Wait-Process`, Hintergrund, Warteschleifen, Abräumen über `Get-Process`/Variable/Pipe.
- **Der Batch endet nicht vor der Umschaltschwelle der Batch-Uhr.** „NACHRUECKLISTE ERLEDIGT“ nur, wenn Posten 6 mit `Get-Date`-Zeile über der Schwelle oder mit belegter Stopp-Bedingung geschlossen ist.
- Belege als `Datei:Zeile@commit`. Preflight als einzige Zeile `python -u scripts/preflight.py before *> analysis/_preflight_264.txt`.

TEIL 1 - Bildsuche über den vollen Lauf:
1a. A4-Lauf ab 0 mit `--strom` bis 900M (Wanduhr ≤ 1500). Je Bild ein Auszug (Bildnummer, Schritt, Zahl der Halbwörter, Blockzahl, PC-Folge-Hash) statt der vollen Bilder; die Rohausgabe nur komprimiert. Tafel `_m264/_bilder_900m.txt`: Zahl der Bilder, Schritte je Bild, Verlauf der Blockzahl.
1b. `m263_bildsuche.py` über alle Bilder gegen `_ref_pcs_f0..f3`: bestes Bild je Referenz mit Präfix. Rotprobe wie B263.
1c. Erscheint kein Bild mit Blockzahl ≥ 7 bis 900M: Abzug bei 900M (`--abzug-speichern`) und Fortsetzung ab Abzug um weitere 900M (Wanduhr ≤ 1500), gleiche Auswertung. Ergebnis: erster Schritt mit Blockzahl > 1 und erster Schritt mit Präfix > 25, oder „bis 1800M nicht erreicht“ mit dem Verlauf.

TEIL 2 - Den Verzweigungswert messen:
2a. Werkzeug: Protokoll der Schreibzugriffe auf `*[0x800B3C28]+4` und `*(r2+0xF8)+6` (Schritt, PC, Funktion, Wert), Schalter wie `--flag-log`. Ergebnis `_m264/_state4.txt` über den vollen Lauf.
2b. Statisch: Schreiber dieser Bytes (Ghidra-Querverweise, Grep in `analysis/`/`port/`). Welcher Spielzustand bzw. welche Szene setzt `state+4 ≠ 0`, und was löst diese Szene aus (Zeit, Eingabe, Gerätezustand)?
2c. Grep in `capture/` und `analysis/`: Läuft die MAME-Referenz als Wiedergabe mit Eingaben (`scope_session04`, `pb`)? Wenn ja: Welche Eingaben liegen bis pb 3 an, und fehlen sie im Hybrid?

TEIL 3 - Erste echte Maßnahme:
3a. Aus TEIL 1/2 die Ursache, warum der Hybrid das Attract-Bild nicht bzw. anders baut. Eine Maßnahme unter `port/hybrid/` (Modell, Kern, Eingabe-Attrappe), Gegenschalter, ROM- und MAME-Beleg. Rotprobe: Gegenschalter → alte Abweichung. Eigener Commit.
3b. Wirkung: Präfix gegen `boot_f0` und Blockzahl vor und nach der Maßnahme. Steigt der Präfix durch die Maßnahme und gilt das auch mit Vorgabe EIN im gültigen Preflight, ist das eine Station. In dem Fall Vorgabe EIN nur mit zwei gleichen A4-Läufen unter 1500 s.

TEIL 4 - Abschluss:
Vorwärmung blockierend, Preflight, `m149_bilanz.py --batch 264 --from-preflight analysis/_preflight_264.txt --write-anchor` (nie durch eine Pipe). Nach dem Preflight nichts mehr unter `scripts/` ändern. `rohlauf_aufraeumen.py --komprimieren` und `check_dateigroesse.py --getrackt` als Auszug ins Dokument.
Ankerkopf B264 mit:
- Preflight-HEAD aus Zeile 3,
- Stationszeile in fester Form,
- Stillstandszähler,
- Bildzahl und bester Präfix je Referenz über den vollen Lauf,
- `state+4`-Befund,
- „Nächster Schritt“ mit Batch-Nummer 265.
Memory-Export, `git status` lesen, `ghidra-mcp-notes.md` mitcommitten (Bremse >50 Zeilen), Ankerblock mit `UEBERTRAG:`/`GESCHLOSSEN`.

BATCH-ENDE:
`python -u scripts/m151_memory_sync.py export`, `git status` lesen, Commit `B264: …`. Abweichungen von der Vorhersage erklären.

FERTIG WENN: (a) `_m264/_bilder_900m.txt` mit allen Bildern bis 900M und Bildsuche gegen `f0..f3`; (b) Ergebnis über 900M hinaus per Abzug oder belegter Treffer davor; (c) `_m264/_state4.txt` mit Schreibern und Werten von `state+4` und `*(r2+0xF8)+6`; (d) mindestens eine Maßnahme unter `port/hybrid/` mit Gegenschalter, Rotprobe und eigenem Commit sowie Präfix/Blockzahl vorher und nachher, oder belegte Stopp-Bedingung mit Grep über `capture/`, `analysis/`, `port/`; (e) gültiger Preflight + Bilanz, Aufräumen und Größenwache; (f) Ankerkopf mit Stationszeile und Stillstandszähler; (g) Batch-Ende nicht vor der Umschaltschwelle ohne belegte Stopp-Bedingung.

STREICHREIHENFOLGE: 1. TEIL 2c, 2. `f1..f3` in TEIL 1b, 3. TEIL 3b-Vorgabe EIN. NIE: Vorhersage-Commit, TEIL 1a, TEIL 1b für `f0`, TEIL 1c, TEIL 2a, TEIL 2b, TEIL 3a, Preflight, Bilanz, Aufräumen, Memory-Export, Ankerkopf.

## NACHRUECKLISTE
1. TEIL 1a/1b volle Bildsuche; FERTIG WENN: `_m264/_bilder_900m.txt` mit Bildzahl, Schritt und Blockzahl je Bild sowie Bildsuche gegen `f0` mit bestem Bild und Rotprobe, committet.
2. TEIL 1c über 900M hinaus; FERTIG WENN: Abzugslauf bis 1800M mit erstem Schritt mit Blockzahl > 1 bzw. Präfix > 25, oder „nicht erreicht“ mit Verlauf.
3. TEIL 2a/2b `state+4`; FERTIG WENN: `_m264/_state4.txt` mit Schreib-PCs, Funktionen und Werten sowie statische Schreibertafel mit Szene bzw. Auslöser.
4. TEIL 3a Maßnahme; FERTIG WENN: Änderung unter `port/hybrid/` mit Gegenschalter, ROM- und MAME-Beleg, Rotprobe (Gegenschalter → alte Abweichung) und eigenem Commit, oder Stopp-Bedingung mit Grep-Beleg.
5. TEIL 4 Abschluss; FERTIG WENN: gültiger Preflight, Bilanz, Aufräum- und Größenwache-Auszug, Ankerkopf B264 mit Stationszeile.
6. Offener Iterationsposten Abweichungsfolge (nach TEIL 3: nächste Abweichung → Maßnahme → Rotprobe → Commit); FERTIG WENN: `Get-Date`-Zeile im Dokument zeigt die Umschaltschwelle erreicht, oder belegte Stopp-Bedingung mit Grep über `capture/`, `analysis/`, `port/`.
</DS_INSTRUCTION>
