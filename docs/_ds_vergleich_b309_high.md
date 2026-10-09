# Schatten-Aussensicht Batch 309 (deepseek-flash[1m])

- Zeitpunkt: 2026-10-09T23:28:53+0200
- Anlass: Schattenlauf (dieselbe Eingabe wie die echte Aussensicht: alle 4 Batches (letzte Aussensicht: Batch 305); Worker-Abbruch in Batch 309 (event))
- Lauf: rc=0 dauer=210s modell=deepseek-flash[1m] befunde=4 verworfen=0 zuege=57 runden=28 subtype=success tiefenprobe=B305
- Zuege (Werkzeugrunden): 28 von 70
- Echte Aussensicht: `meta.md` mit `claude-opus-5-5` vom 2026-10-09T04:03:16+00:00
- Tiefenprobe: Batch 305 aus dem Fenster B300..B309 (angeheftet, NICHT gezogen/merken) - vorher gezogen: B300
- Nutzerlimit (Abo) VOR dem Lauf: Sitzung (5 h): 2 % (Reset 10.10.2026 03:10 (UTC+02:00)) | Woche (7 Tage): 87 % (Reset 13.10.2026 07:00 (UTC+02:00))
- Nutzerlimit (Abo) NACH dem Lauf: keine Angaben
- Hinweis: Mitschnitt und Fehlerdatei lagen in `%TEMP%` (`schatten_aussensicht_b309_deepseek.jsonl`); dieser Bericht ist das EINZIGE Artefakt im Repo.

## Antwort (roh)

<AUSSENSICHT>
TIEFENPROBE B305 (Auftrag, Bericht, result.json, Denkbloecke, Belege): die Kernzahlen halten gegen die Rohdateien — 221288/221288 (`analysis/_m305/_lesung_erklaert.txt:271`), 0 von 48 Paketen (`_m305/_walk_reihenfolge.txt:106`), Walk-Abbruch 0x12=FFFF (`_m305/_roh_auszuege.txt:20-22`); Laufzeit/Kosten passen (`runs/b305/result.json`: 2578 s, 109 Anfragen, $0,188). Zwei Review-Stichproben bestaetigt: `analysis/_m320/_kandidat.txt:32` („R1 … 68 | 72 | 10 | 9 | 33/32 | 140") deckt die Review-Aussage zu B320, `_m319/_ext1_matrix.txt:20,62` (2218 Eintritte = 17,24/Bild, Halt 8002BDC8) die zu B319. Die Denkbloecke zeigen dagegen, was der Bericht verschweigt: der Worker hielt die H11-Probe selbst fuer „trivial"/„by construction" (`snapshots/b305/reasoning.jsonl:29`) und meldete sie als „CONFIRMED — 100,00 %".
Messziel: B fuehrt Praefix UND die Zahl der verschiedenen SHAs korrekt (`_preflight_321.txt:35`, Praefix 15 | SHAs 33/31), C fuehrt seit B321 zusaetzlich „referenzgleich 149 / teilgeprueft 36 / Schatten-ungleich 1" (`_bilanz_snapshot.json:27255-27259`) — die Messgroessen treffen ihre Ziele; der Befund ist der Stillstand, nicht die Definition. Arbeit vorhanden: die Behauptung „SHARC-Lesestrom fehlt im Hybrid" ist selbst geprueft und traegt — sie steht als benannte Luecke im Port (`port/hybrid/maschine.cpp:329-331`).
Am meisten Sorgen macht der Kassenstand: 87 % der Wochenquote am 09.10. bei Reset am 13.10. (Eingabe KOSTEN), waehrend die B-Zielzahl seit B314 (7 Batches) und der native Port seit 30 B-Batches unbewegt sind — und seit B318 fehlt die kanonische Bilanzdatei, aus der der Harness seinen Bilanzblock liest.
geprueft: H11 „CONFIRMED (100 %)" als Konstruktionswahrheit (B305), behoben in B306 (Beleg: `runs/b306/review.md:7,33`; die Gegenergebnis-Pflicht wird angewandt in `analysis/port-batch321-b-zustellraster-2026-10-10.md:32-34`).
</AUSSENSICHT>

<BEFUND n="1" gewicht="hoch" empfaenger="Reviewer">
Beleg: Fehlstelle: `analysis/_m318/_bilanz*.txt`, `_m319/…`, `_m320/…`, `_m321/…` gesucht, nicht gefunden (Glob); juengste kanonische Datei ist `analysis/_m317/_bilanz.txt`. Der Harness liest genau diese: `G:\Harness\harness\hx\stand.py:287-306` („Die kanonischen Bilanzdateien `analysis/_m<N>/_bilanz*.txt` … schreibt `scripts/m149_bilanz.py` am Batch-Ende selbst"). Eingabe BILANZ: „Quelle: analysis/port-batch321-b-zustellraster-2026-10-10.md (B321) - Bau-Liste/Vorrat/Inventar fuehrt es nicht".
Aussage: Seit B318 (vier Batches) fehlt die kanonische Bilanzdatei `_m<N>/_bilanz.txt`; der Bilanzblock der Aussensicht faellt deshalb auf das Batch-Dokument zurueck und verliert Bau-Liste/Vorrat/Inventar, obwohl die B243-Regel den Dateinamen festgelegt hat (`runs/b243/review.md:108`).
Empfehlung: Das Batch-Ende wieder mit Umlenkung fahren (`… --write-anchor *> analysis/_m<N>/_bilanz.txt`, wie B300–B317) und die nicht leere Datei im Dokument per Glob belegen.
</BEFUND>

<BEFUND n="2" gewicht="hoch" empfaenger="Nutzer">
Beleg: Eingabe BILANZ („Zielzahl (Praefix/SHAs) … Praefix **15** | ver…") und `analysis/_preflight_321.txt:35` (Praefix 15 | verschiedene SHAs 33/31) gegen den Ankerkopf „Praefix je Board/Bank 15 | … (seit B314, unveraendert)"; dazu Eingabe BILANZ („Strang B laeuft in dieser Reihe ohne C-Batch (B292..B321, 30 Batches)").
Aussage: Die einzige B-Fortschrittszahl steht seit 7 B-Batches (B314→B321) unveraendert, und nach M317-2 haben 30 B-Batches keinen nativen Port-Kopf bewegt; der naechste Schritt („Fensterbreite") ist erneut ein Parameter des Hybrid-Hardwaremodells, das laut `readme.md` „im Port zu ersetzen" ist.
Empfehlung: Den offenen A2-Entscheid zusammen mit dieser Zahl treffen und wie in M317-2 eine Obergrenze fuer reine Modellarbeit oder eine zweite, port-bezogene B-Zahl festlegen.
</BEFUND>

<BEFUND n="3" gewicht="mittel" empfaenger="Reviewer">
Beleg: `analysis/_m305/_lesung_erklaert.txt:163,265,271` (die zitierten 100-%-Zeilen) gegen `runs/b305/antwort.md:16` („Beleg `analysis/_m305/_lesung_erklaert.txt:88-96@b16ba6a`"); Zeilen 88-96 sind Tabellenzeilen. Die Datei ist seit `a7262a3` unveraendert (`git log --oneline -- analysis/_m305/_lesung_erklaert.txt`), die Fundstelle war also schon bei b16ba6a falsch.
Aussage: Der Beleg im B305-Abschlussbericht zeigt auf Tabellenzeilen statt auf die zitierte Quote; das `@commit` macht die Stelle eindeutig, aber nicht richtig.
Empfehlung: Belege vor dem Abschluss maschinell gegen die Zeile pruefen (Zitattext gegen Dateiinhalt) und Abweichungen im Dokument nennen.
</BEFUND>

<BEFUND n="4" gewicht="niedrig" empfaenger="Reviewer">
Beleg: `analysis/_m305/_roh_auszuege.txt:8-16` — alle drei Paare der Rohzeilenprobe (A) sind „Paket 1104, Lesung Z1425013/Z1426193/Z1426176" (Saat 305).
Aussage: Die Rohzeilenprobe zieht alle drei Eintraege aus demselben ersten Paket und prueft damit nur eine Zeilengruppe der Tafel, nicht die Tafel.
Empfehlung: Die drei Zufallseintraege ueber verschiedene Pakete streuen (Saat nennen) — sonst faengt die Probe keine paketuebergreifenden Werkzeugfehler.
</BEFUND>

<PRUEFUNG id="M242-3" status="erledigt"/>
<PRUEFUNG id="M254-2" status="offen"/>
<PRUEFUNG id="M254-3" status="offen"/>
<PRUEFUNG id="M254-4" status="offen"/>
<PRUEFUNG id="M260-5" status="offen"/>
<PRUEFUNG id="M274-4" status="erledigt"/>
<PRUEFUNG id="M309-4a" status="erledigt"/>
<PRUEFUNG id="M313-4" status="erledigt"/>
<PRUEFUNG id="M317-1a" status="offen"/>
<PRUEFUNG id="M317-2" status="offen"/>
