# Schatten-Aussensicht Batch 309 (deepseek-flash[1m])

- Zeitpunkt: 2026-10-09T23:46:17+0200
- Anlass: Schattenlauf (dieselbe Eingabe wie die echte Aussensicht: alle 4 Batches (letzte Aussensicht: Batch 305); Worker-Abbruch in Batch 309 (event))
- Lauf: rc=0 dauer=423s modell=deepseek-flash[1m] befunde=4 verworfen=0 zuege=52 runden=12 subtype=success tiefenprobe=B305
- Zuege (Werkzeugrunden): 12 von 70
- Echte Aussensicht: `meta.md` mit `claude-opus-5-5` vom 2026-10-09T04:03:16+00:00
- Tiefenprobe: Batch 305 aus dem Fenster B300..B309 (angeheftet, NICHT gezogen/merken) - vorher gezogen: B300
- Nutzerlimit (Abo) VOR dem Lauf: Sitzung (5 h): 2 % (Reset 10.10.2026 03:10 (UTC+02:00)) | Woche (7 Tage): 87 % (Reset 13.10.2026 07:00 (UTC+02:00))
- Nutzerlimit (Abo) NACH dem Lauf: keine Angaben
- Hinweis: Mitschnitt und Fehlerdatei lagen in `%TEMP%` (`schatten_aussensicht_b309_deepseek.jsonl`); dieser Bericht ist das EINZIGE Artefakt im Repo.

## Antwort (roh)

<AUSSENSICHT>
TIEFENPROBE B305: Die Kernzahlen des Berichts halten der Rohprobe stand — Walk 0 von 48 mit erster Abweichung 1104/Position 209/Offset M17-W18 (`_m305/_walk_reihenfolge.txt:106-107`), PPM-Identitaet k1104/k1106 (`:113-115`), Hybrid 198 Dreiecke/0 von 48/SHA 0 von 93 (`_m305/_bild_hybrid.txt:109-110`), Paket-4-Folge und Urteil UNENTSCHEIDBAR (`_m305/_paket4_nutzlast.txt:273-287`), Rohzeilenprobe Saat 305 (`_m305/_roh_auszuege.txt:1`); EINE Belegzeile ist falsch (`runs/b305/antwort.md:16` zitiert `_lesung_erklaert.txt:88-96`, das Zitat steht `:163`/`:265-271`; die Datei ist seit `a7262a3` unveraendert, `git log` auf die Datei = ein Commit). Der Denkblock zeigt, dass der Worker die Schwaechen des eigenen H11-Urteils kannte (`snapshots/b305/reasoning.jsonl:25`: "near-tautological ... partially WEAKENS H11"), was der Bericht nur in der Schlusszeile sagt — der Reviewer hat es in B306 korrekt als "Werkzeugprobe" herabgestuft (`runs/b306/review.md:7`).
Messziel: Strang B fuehrt Praefix + verschiedene SHAs korrekt als Zielzahl (Raten nur Information, `analysis/r1b-workstream.md:6`), steht aber seit B314 unveraendert bei 15|33/31 — 7 B-Batches (B315..B321) ohne Bewegung (`_preflight_321.txt:35`); Strang C fuehrt "150 / 8510 / 0 referenzgleich", obwohl 1 Kopf im Schatten nachweislich ungleich ist (`_preflight_321.txt:16`) — die Zahl misst nicht ganz ihr Ziel.
Arbeit vorhanden: keine offene "fehlt"-Behauptung in Anker/Auftrag/Fragen zu B321 gefunden; die juengste Luecke ist belegt geschlossen (`_m321/_iocr_boot.txt:11-27`: Bootloader schreibt kein IOCR, BE+LE geprueft). Stichproben bestaetigt: Review B320 gegen `runs/b320/antwort.md:12`/`result.json` (R1 gleich 68/Praefix 9/erster 10/33-32; 50,5 min, 73 Anfragen, $0,13) und Review B311 gegen `runs/b311/antwort.md:11`/`result.json` (168/168 indexgleich, +4-Regel; 36 min, 118 Anfragen).
Sorgen: 7 B-Batches ohne Bewegung der Fortschrittszahl, ~30 B-Batches (B292..B321) ohne C-Arbeit, letzter `port/src`-Commit `fafb734` (B282, nur Sonden — heute per `git log -1 -- port/src` gemessen); gleichzeitig ist das Wochenkontingent bei 87 % (09.10. 20:21Z) und bei ~0,65-1,1 Punkten/h rechnerisch am 10.10. erschoepft (Reset erst 13.10. 07:00) — die beschlossene Takt-Senkung haengt unveraendert in `g:\Harness\harness\harness.toml:185`. Ein Aussenstehender wuerde fragen, warum eine Serie ohne bewegte Fortschrittszahl unveraendert weiterlaeuft, bis das Kontingent sie stoppt.
</AUSSENSICHT>

<BEFUND n="1" gewicht="hoch" empfaenger="Reviewer">
Beleg: `analysis/r1b-workstream.md:6` ("Zielzahl (B): Praefix je Board/Bank 15 | verschiedene SHAs 33/31 (seit B314, unveraendert)") und `analysis/_preflight_321.txt:35` ("... Praefix 15 | verschiedene SHAs 33/31") gegen `runs/b320/antwort.md:29` (derselbe Wert, "unveraendert seit B314"); Eingabe BILANZ: "4 B-Batches in Folge weder Station noch Bewegung (B317..B320)".
Aussage: Die einzige Fortschrittszahl von Strang B steht seit sieben B-Batches (B315..B321) still, die Kandidatenhebel seit B315 (Quittung, Phase, R1, Raster, R2) blieben ohne Treffer, und keine Bedingung uebersetzt den Stillstand in einen Planwechsel (Anker-Zielzahlzeile und Preflight-Zeile tragen ihn unveraendert weiter).
Empfehlung: Fuer den naechsten B-Batch vorab belegen lassen, dass der gewaehlte Hebel die Zielzahl selbst (nicht nur eine Ersatzrate) bewegen kann, sonst zuerst A2/M317-2 klaeren, bevor weitere Kandidaten gemessen werden.
</BEFUND>

<BEFUND n="2" gewicht="mittel" empfaenger="Reviewer">
Beleg: Eingabe "KOSTEN UND LAUFZEITEN JE BATCH" (B312 45,4 | B317 62,6 | B318 74,2 | B320 50,5 | B321 39,9 min) und die Review-Zeilen in der Eingabe (B317 "nur 63 von 150 min", B318 "74 von 150 min", B320 "Wieder kurz: 51 min") sowie `runs/b306/review.md:7` ("Der Batch war wieder zu klein (43 min, 44 % fester Aufwand)").
Aussage: Fuenf der letzten zehn Batches enden nach 40-75 der rund 150 Minuten; das Muster ist seit B305 in fuenf Reviews benannt, der Zuschnitt wurde nicht geaendert, B321 war mit 39,9 min der kuerzeste.
Empfehlung: Den Zuschnitt an der Uhr messen (Mindest-Arbeitsanteil oder ein zweites Pflichtpaket je Batch) und die Ursache des fruehen Endens ("FERTIG WENN" erreicht) im Review adressieren.
</BEFUND>

<BEFUND n="3" gewicht="mittel" empfaenger="Reviewer">
Beleg: `analysis/_preflight_321.txt:16` ("150 / 8510 / 0 referenzgleich | ... | davon im Schatten ungleich: 1 (FUN_80029A50)") gegen Eingabe BILANZ ("C Koepfe: 150 referenzgleich (150 -> 150: +0), 0 Abweichungen") und `analysis/_m321/_schatten_ungleich.txt` (ein Kopf: 80029A50).
Aussage: Die C-Zielzahl "referenzgleiche Koepfe" zaehlt weiter einen im Schatten nachweislich ungleichen Kopf mit; die Korrektur existiert nur als Nebenast ("C Koepfe ohne Schatten-ungleiche NEU in diesem Batch"), die Hauptzeile bleibt falsch (M313-4).
Empfehlung: Die Hauptzeile auf 149 ohne Schatten-ungleiche umstellen und "teilgeprueft 36" getrennt fuehren, damit M313-4 geschlossen werden kann.
</BEFUND>

<BEFUND n="4" gewicht="niedrig" empfaenger="Reviewer">
Beleg: `runs/b305/antwort.md:16` zitiert `analysis/_m305/_lesung_erklaert.txt:88-96@b16ba6a`; in der seither unveraenderten Datei (`git log --oneline -- analysis/_m305/_lesung_erklaert.txt` = nur `a7262a3`) stehen die Quoten auf `:163` und `:265-271`, die Zeilen 88-96 sind Tabellenzeilen.
Aussage: Die Belegstelle der zentralen H11-Aussage in B305 zeigt auf die falschen Zeilen (Tiefenprobe B305).
Empfehlung: Im laufenden Batch-Dokument richtigstellen; alte `_m`-Belege bleiben nach dem B313-Entscheid unangetastet.
</BEFUND>

<PRUEFUNG id="M242-3" status="offen" beleg="Eingabe BILANZ: 'Median Zuwachs (Kopf-Batches): nicht gemessen'; die +3-Prognose ist ersetzt, der Median aus der Preflight-Reihe fehlt weiter"/>
<PRUEFUNG id="M254-2" status="offen" beleg="`git log -1 --format=%h -- port/src`=fafb734 (heute); C ruht, Nachrueckliste 2 weiter 'BLOCKIERT (orc)', analysis/r1b-workstream.md:1375"/>
<PRUEFUNG id="M254-3" status="offen" beleg="analysis/r1b-workstream.md:1380 traegt 'Ein NICHT betretener neuer Kopf aendert den Schluessel NICHT' weiter als UEBERTRAG (ohne STRONG-INFERENCE-Kennzeichnung), die geforderte Messung fehlt"/>
<PRUEFUNG id="M254-4" status="offen" beleg="Eingabe BILANZ: C-Arbeitsvorrat 1403 Koepfe/53535 Insn, 'die C-Hochrechnung ruht' - Zielband-/Umstiegsentscheidung unbeantwortet"/>
<PRUEFUNG id="M260-5" status="offen" beleg="readme.md:775 'status at Batch 215' und :790 'Mix since B208: 2 B : 1 C' - heute gelesen, unveraendert"/>
<PRUEFUNG id="M274-4" status="offen" beleg="Musterfall B305: snapshots/b305/reasoning.jsonl:25 ('partially WEAKENS H11') gegen runs/b305/antwort.md:16 ('CONFIRMED - H11'); B306 regelte nur die Falsifizierbarkeit ('Gegenergebnis je CONFIRMED', runs/b306/review.md:34), nicht die Gegenprobe der eigenen Rohdaten"/>
<PRUEFUNG id="M309-4a" status="erledigt" beleg="Eingabe 'OFFENE FRAGEN UND ENTSCHEIDUNGEN': A2 (Bildzahl als Zielzahl) und R320-1 (Budget/Takt) sind fuer den Nutzer sichtbar"/>
<PRUEFUNG id="M313-4" status="offen" beleg="analysis/_preflight_321.txt:16 'davon im Schatten ungleich: 1' gegen Eingabe BILANZ '150 referenzgleich ... 0 Abweichungen'"/>
<PRUEFUNG id="M317-1a" status="offen" beleg="g:\Harness\harness\harness.toml:185 'aussensicht_takt = 4' unveraendert; logs/rate-limit.json 0.87 (2026-10-09T20:21Z)"/>
<PRUEFUNG id="M317-2" status="offen" beleg="`git log -1 --format=%h -- port/src`=fafb734; die Entscheidung (Obergrenze/zweite B-Zahl) steht als A2 offen"/>
