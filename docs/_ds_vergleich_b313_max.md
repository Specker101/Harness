# Schatten-Aussensicht Batch 313 (deepseek-flash[1m])

- Zeitpunkt: 2026-10-09T23:52:56+0200
- Anlass: Schattenlauf (dieselbe Eingabe wie die echte Aussensicht: alle 4 Batches (letzte Aussensicht: Batch 309))
- Lauf: rc=0 dauer=395s modell=deepseek-flash[1m] befunde=3 verworfen=0 zuege=55 runden=27 subtype=success tiefenprobe=B306
- Zuege (Werkzeugrunden): 27 von 70
- Echte Aussensicht: `meta.md` mit `claude-opus-5-5` vom 2026-10-09T09:21:33+00:00
- Tiefenprobe: Batch 306 aus dem Fenster B304..B313 (angeheftet, NICHT gezogen/merken) - vorher gezogen: B305
- Nutzerlimit (Abo) VOR dem Lauf: Sitzung (5 h): 2 % (Reset 10.10.2026 03:10 (UTC+02:00)) | Woche (7 Tage): 87 % (Reset 13.10.2026 07:00 (UTC+02:00))
- Nutzerlimit (Abo) NACH dem Lauf: keine Angaben
- Hinweis: Mitschnitt und Fehlerdatei lagen in `%TEMP%` (`schatten_aussensicht_b313_deepseek.jsonl`); dieser Bericht ist das EINZIGE Artefakt im Repo.

## Antwort (roh)

<AUSSENSICHT>
Stichproben (3): (1) Review zu B320 (runs/b321/review.md: „Pmv 17,11 EXT1/Bild, MAME 14,34") — bestaetigt (`analysis/_m320/_rate420.txt:31` bzw. `:44`). (2) dieselbe Review: „R1 810M: Praefix 9, erster ungleich 10, gleich 68" — bestaetigt (`analysis/_m320/_kandidat.txt:38-39`). (3) Anker B321: „`--irq-raster` wird im PEGELPFAD gelesen" — bestaetigt (`port/hybrid/hybrid_lauf.cpp:2904-2905`, Gate `:2906-2908`). Denkbloecke B306: in `snapshots/b306/reasoning.jsonl:13,15` steht „R gives too many freedoms" und „I believe the INTENDED R is …" — R wurde aus der Aufgabenstellung erschlossen und behaelt 4 Freiheitsgrade; im Bericht erscheint dieselbe Regel als gefundener „Ring-Scan". Reihenfolge Marker->Preflight ist in `reasoning.jsonl:92` als Plan belegt („write the marker … then the preflight"), die Review hat sie so bewertet.
TIEFENPROBE B306: alle pruefbaren Behauptungen halten gegen die Rohbelege — K2 5/48 unter 95 % (`analysis/_m306/_leseregel.txt:96-99`), (a) 48/48 und Bildzahl 6/48 (`_m306/_bildzahl.txt:8,10`), PCZ `80008930 18` (`_m306/_nativ_tafel.txt:29`), kein `port/`-Diff (git diff 73a1a61^ 4e7ffc2 -- port/ leer), zwei `ENTSCHEIDUNG (Reviewer, B306)` (`analysis/hybrid-plan.md:903,916`), Rohzeilenprobe 3+3+3 (`_m306/_roh_auszuege.txt`). Drei Punkte sind heute ueberholt und daher keine Befunde: „72/77" -> 71 korrigiert (B314 TEIL 0, `analysis/r1b-workstream.md:105`); „FUN_8000C654 laeuft nicht" -> B307 „im Log nicht sichtbar" -> B308 „liest im aufgezeichneten Zeitraum nicht vom CG-Port" (`r1b-workstream.md:94`); „5 Commits nicht gepusht" -> behoben (`origin/main` = HEAD `c561ddb`, 0 Commits voraus). Restfehler: Zitatdrift (der Bericht nennt `_leseregel.txt:93` fuer die K2-Zeile, sie steht `:96-99`).
Messziel: B fuehrt Praefix 15 | SHAs 33/31 als Zielzahl und kennzeichnet EXT1-Raten/Paketzahlen als Information (`analysis/_preflight_321.txt:35`, `r1b-workstream.md:6`) — richtige Groesse; C fuehrt 150 referenzgleich, die Bilanz zusaetzlich 149 ohne Schatten-ungleiche + 36 teilgeprueft (`analysis/_bilanz_snapshot.json:27255-27259`). Arbeit vorhanden: geprueft — die „fehlenden" Zaehlpunkte 8001B644/8001B6FC/8001B724 sind in `port/` belegt (`port/include/port/render_transport.h:61,113`) und in `analysis/` mehrfach gemessen, die B321-Fehlstelle „Bootloader schreibt kein IOCR" traegt eine Gegenprobe (EXIER 0x042, `analysis/_m321/_iocr_boot.txt:14-28`); kein Fall von falsch fuer fehlend erklaerter Arbeit gefunden. Sorge: Die B-Zielzahl steht seit B314 unveraendert (B315..B321, 7 Batches), sie bewegte sich seit B291 genau einmal und dann ueber einen Hardwaremodell-Schalter; C ruht per Nutzerentscheid, und der Traeger der B-Bewegung ist der laut `readme.md` zu ersetzende Hybrid — der Port selbst hat seit B282 (`git log -- port/src port/include`: fafb734, nur Sonden) nichts hinzugefuegt.
</AUSSENSICHT>

<BEFUND n="1" gewicht="hoch" empfaenger="Reviewer">
Beleg: `analysis/_preflight_321.txt:35` („Praefix 15 | verschiedene SHAs 33/31"), `analysis/r1b-workstream.md:6` („seit B314, unveraendert"), Eingabe BILANZ („B-Phase: 6 B-Batches in Folge ohne Station (B315..B320)"; „Fortschritt: 4 B-Batches … weder Station noch Bewegung"), `git log --format="%h %s" -- port/src port/include` -> letzter Eintrag `fafb734` (B282, 2026-10-06, nur Sonden); Eingabe Review zu B314 („Die Zielzahl bewegt sich zum ersten Mal seit B291", Ursache IRQ0-Pegel = Modellschalter).
Aussage: Die B-Zielzahl steht seit B314 auf demselben Wert (7 Batches B315..B321 ohne Bewegung), die einzige Bewegung seit B291 kam aus einem Hardwaremodell-Schalter in `port/hybrid`, und der Plan kennt keine Regel, was nach N Batches ohne Bewegung der Zielzahl geschehen soll — die Hinweisgrenze 6 (R277-1) laeuft folgenlos aus.
Empfehlung: Fuer den B-Strang eine Schwelle festlegen (z. B. nach N Batches ohne Bewegung Zuschnitt aendern oder einen nativen Hebel ziehen) statt die Reihe fortzusetzen; die Ziel-/Messfrage selbst liegt bereits als M317-2 beim Nutzer.
</BEFUND>

<BEFUND n="2" gewicht="mittel" empfaenger="Reviewer">
Beleg: `analysis/r1b-workstream.md:6` (B321-Kopf fuehrt „Daneben (Information): EXT1-Raten … und Paketzahlen" — ohne Bildzahl) gegen `analysis/r1b-workstream.md:13` (B320-Kopf: „Daneben (Information): Bildzahl 39/48") und `:7` (Offene Entscheidung (2) zur Bildzahl unveraendert offen); Zahl selbst: `analysis/_m307/_bildzahl_b1.txt:13` (39/48, B307).
Aussage: Die Bildzahl (PROBE B1) 39/48 ist mit dem B321-Ankerkopf aus dem gefuehrten Stand verschwunden, obwohl die Nutzerfrage (2), ob sie Zielzahl wird, offen ist und die Zahl seit B307 nicht neu gemessen wurde.
Empfehlung: Die Bildzahl im Ankerkopf weiterfuehren oder die Frage (2) schliessen, damit ueber keine Zahl entschieden wird, die der Kopf nicht mehr zeigt.
</BEFUND>

<BEFUND n="3" gewicht="mittel" empfaenger="Nutzer">
Beleg: `analysis/r1b-workstream.md:7` (Frage (2): „Soll die Bildzahl Zielzahl von Strang B werden? (Vorschlag: nein, solange die Leseregel nur in 1104..1196 gilt)") gegen `analysis/r1b-workstream.md:99` (B307 TEIL 1: „60,10 % (swap) / 48,20 % (swap2) der Stroeme unter 95 % -> R AUSSERHALB DER STICHPROBE WIDERLEGT, szenen-gebunden") und `git log` (B314 wurde die Zielzahl ueber IRQ0-Pegel bewegt, nicht ueber Port-Arbeit).
Aussage: Die offene Frage (2) ruht auf einer Praemisse, die die eigene Messung nicht mehr traegt — die Leseregel ist ausserhalb 1104..1196 nicht nur beschraenkt, sondern widerlegt; ein „ja" wuerde eine Zahl zum Fortschrittsmass machen, deren Regel szenen-gebunden und seit 14 Batches nicht nachgemessen ist.
Empfehlung: Die Frage (2) mit dem B307-Ergebnis neu stellen (Wortlaut/Formulierung ist Reviewer-Sache), bevor der Nutzer entscheidet.
</BEFUND>

<PRUEFUNG id="M242-3" status="offen"/>
<PRUEFUNG id="M254-2" status="offen"/>
<PRUEFUNG id="M254-3" status="offen"/>
<PRUEFUNG id="M254-4" status="offen"/>
<PRUEFUNG id="M260-5" status="offen"/>
<PRUEFUNG id="M274-4" status="erledigt"/>
<PRUEFUNG id="M309-4a" status="erledigt"/>
<PRUEFUNG id="M313-4" status="erledigt"/>
<PRUEFUNG id="M317-1a" status="offen"/>
<PRUEFUNG id="M317-2" status="offen"/>
