# Schatten-Aussensicht Batch 285 (claude-sonnet-5-5)

- Zeitpunkt: 2026-10-07T15:33:24+0200
- Anlass: Schattenlauf (dieselbe Eingabe wie die echte Aussensicht: alle 4 Batches (letzte Aussensicht: Batch 281))
- Lauf: rc=0 dauer=191s modell=claude-sonnet-5-5 befunde=3 verworfen=0 zuege=37 runden=18 subtype=success tiefenprobe=B277
- Zuege (Werkzeugrunden): 18 von 70
- Echte Aussensicht: `meta.md` mit `claude-opus-5-5` vom 2026-10-07T00:27:57+00:00
- Tiefenprobe: Batch 277 aus dem Fenster B276..B285 (angeheftet, NICHT gezogen/merken) - vorher gezogen: B276, B279
- Nutzerlimit (Abo) VOR dem Lauf: Sitzung (5 h): 25 % (Reset 07.10.2026 16:20 (UTC+02:00)) | Woche (7 Tage): 27 % (Reset 13.10.2026 07:00 (UTC+02:00))
- Nutzerlimit (Abo) NACH dem Lauf: Sitzung (5 h): 46 % (Reset 07.10.2026 16:20 (UTC+02:00)) | Woche (7 Tage): 30 % (Reset 13.10.2026 07:00 (UTC+02:00))
- Hinweis: Mitschnitt und Fehlerdatei lagen in `%TEMP%` (`schatten_aussensicht_b285.jsonl`); dieser Bericht ist das EINZIGE Artefakt im Repo.

## Antwort (roh)

<AUSSENSICHT>
TIEFENPROBE B277: Ich habe Auftrag, Bericht, `result.json`, Denkblöcke (Zeilen 56–58, 100–105) und die Belege `_m277/_pakete_inhalt.txt`, `_weitere_abw.txt` und `_fortsetzung2700.txt` gegengelesen. Die Zahlen stimmen. SHA-Präfix 124, Offset 108 (`000003C0` gegen `050003C0`), Rückwirkungs-SHA `d89ac2ba` und 2,7G Kette gleich am Stück (0 ungleiche Fenster) sind belegt. Nicht belegt war die Deutung: Der Bericht nennt die board/bank-Lücke STRONG INFERENCE und sagt voraus, das Präfix „muss über 124 wachsen". B278 widerlegte das (`runs/b279/review.md:2`, 2×2-Modell gebaut, Lauf byteidentisch, Präfix 124). `_weitere_abw.txt:10` hat für Paket 159 nur „SHA verschieden", der Bericht verallgemeinert trotzdem „ebenso einzelne Wörter". Erst B282 belegte das (Eingabe Review zu B282). B277 lief 9145 s (`runs/b277/result.json`, Alarm) und füllte die Preflight-Sperre mit 3,6G/2,7G/Fortsetzungs-Läufen (1467/1111/964 s).

Stichproben gegen `result.json`: B286 (24,0 min Preflight, 161 Anfragen, 163,9 min) und B289 (17,5 min, 159 Anfragen, $0,2317) bestätigt. Aus den Denkblöcken geht hervor: Der Worker fand beim Abbild-Header einen Etikettenfehler (Wortindex statt Byteoffset) und umging den Neulauf, indem er in Python umrechnete. Der Bericht erwähnt das nicht.

Messziel B: Das Präfix steht seit B277 bei 124 und hat sich in 13 Batches nicht bewegt. Es steht weder in `_preflight_289.txt` noch in `_m289/_bilanz.txt` (kein Treffer auf „Praefix|SHAs"). Messziel C: Die Zahl bleibt konstant bei 151, weil C ruht (Nutzerentscheid), das ist kein Messfehler. Arbeit vorhanden: „Quelle Paket 160" ist nicht „fehlt", sondern aufgeschoben (Fundstellen unten). Geprüft: `port_suche` wird nicht mehr abgeschnitten, behoben in B289-Nachzug (Beleg: Commit 3b8c9bc, Rotprobe 0→1 Zähler).
</AUSSENSICHT>

<BEFUND n="1" gewicht="hoch" empfaenger="Reviewer">
Beleg: Fehlstelle: gesucht in `analysis/_preflight_289.txt` und `analysis/_m289/_bilanz.txt`, nicht gefunden (Grep "Praefix|SHAs"); `analysis/hybrid-plan.md:325-328` („Stationszaehler ist das Fortschrittsmass; `Anteil nativ (Schatten)` bleibt das Zielmass") gegen `analysis/hybrid-plan.md:9-11` und `readme.md:793-796` (Präfix zusammen mit der Zahl verschiedener Paket-SHAs, Anteil nur Information).
Aussage: Das für Strang B festgelegte Fortschrittsmaß (Präfix und SHA-Zahl) wird in keiner maschinell erhobenen Zeile geführt, und `hybrid-plan.md` widerspricht sich selbst, indem es dem Anteil nativ weiter den Rang eines Zielmaßes gibt.
Empfehlung: Eine Preflight-/Bilanzzeile „Präfix | SHA-Zahl über festes Paketfenster MAME 1..476 | Quelldatei" einführen und `hybrid-plan.md:325-328` an `:9-11` angleichen (damit M285-5a und M289-2 schließen).
</BEFUND>

<BEFUND n="2" gewicht="hoch" empfaenger="Nutzer">
Beleg: Präfix 124 in `analysis/_m277/_pakete_inhalt.txt:53` (B277) und im Ankerkopf B289 („Praefix weiter 124"); Eingabe Letzte Review-Zusammenfassungen (B282, B283, B285, B286, B287: „BEWEGUNG: ja" bei „Paketinhalt neutral", „Präfix unverändert", „nur Information"); Eingabe Bilanz („3 B-Batches in Folge weder Station noch Bewegung (B287..B289); Hinweisgrenze 6"); Eingabe Kosten und Laufzeiten je Batch (B280–B289 zusammen 1507 min).
Aussage: Die einzige Bremse für Strang B (Hinweisgrenze 6) misst „Bewegung", nicht das Präfix. Der Zähler wurde durch präfixneutrale Änderungen mehrfach zurückgesetzt und steht deshalb bei 3, obwohl das Fortschrittsmaß 13 Batches und allein für B280–B289 rund 25 h lang flach blieb.
Empfehlung: Dem Nutzer die flache Zahl (124 seit B277) als Information vorlegen und entscheiden lassen, ob der Hinweis an das Präfix statt an „Bewegung" gebunden wird. Die Entscheidung R285-1 bleibt unberührt, sie betraf die Zählregel, nicht die Sichtbarkeit.
</BEFUND>

<BEFUND n="3" gewicht="mittel" empfaenger="Reviewer">
Beleg: Eingabe Letzte Review-Zusammenfassungen (UEBERTRAG „Paket 160 Quellzelle/Quellpuffer" in den Reviews zu B283, B284, B285, B287, B288 und B289, zuletzt „nachrangig"); `analysis/r1b-workstream.md:7` (Schritt 2 unverändert, Quellpuffer `r31` 0x8018CFC4); `runs/b279/review.md:2` (B277-Hypothese board/bank widerlegt); `analysis/_m277/_pakete_inhalt.txt:65` (Ursache als STRONG INFERENCE ohne Probe).
Aussage: Die Hebel, die den Paketinhalt bewegen könnten (Paket 160, Quelle von Paket 125/159), wurden sechs Reviews lang vertagt, während fünf Zeitmodelle gebaut wurden, die nachweislich denselben Inhalt liefern (M289-1); die Ursachenaussagen B277 (board/bank), B284 (CONFIRMED 1,455) und B288 („kein Modellwert") wurden nacheinander widerlegt.
Empfehlung: Als nächsten Zuschnitt die Paket-160-Quelle (`--zell-log` auf 0x8018CFC4..0x8018D008) vor jedem weiteren Modellbau ansetzen und jede Ursachenaussage mit „muss das Präfix heben" erst nach einer Probe, die das Paket-SHA ändert, über STRONG INFERENCE führen.
</BEFUND>

<PRUEFUNG id="M242-3" status="erledigt"/>
<PRUEFUNG id="M254-2" status="offen"/>
<PRUEFUNG id="M254-3" status="offen"/>
<PRUEFUNG id="M254-4" status="offen"/>
<PRUEFUNG id="M260-5" status="offen"/>
<PRUEFUNG id="M272-4" status="offen"/>
<PRUEFUNG id="M274-4" status="offen"/>
<PRUEFUNG id="M285-5a" status="offen"/>
<PRUEFUNG id="M289-1" status="offen"/>
<PRUEFUNG id="M289-2" status="offen"/>
<PRUEFUNG id="M289-3" status="offen"/>
<PRUEFUNG id="M289-4" status="erledigt"/>
<PRUEFUNG id="M289-5" status="offen"/>
