# Schatten-Aussensicht Batch 313 (deepseek-flash[1m])

- Zeitpunkt: 2026-10-09T23:34:29+0200
- Anlass: Schattenlauf (dieselbe Eingabe wie die echte Aussensicht: alle 4 Batches (letzte Aussensicht: Batch 309))
- Lauf: rc=0 dauer=333s modell=deepseek-flash[1m] befunde=4 verworfen=0 zuege=49 runden=28 subtype=success tiefenprobe=B306
- Zuege (Werkzeugrunden): 28 von 70
- Echte Aussensicht: `meta.md` mit `claude-opus-5-5` vom 2026-10-09T09:21:33+00:00
- Tiefenprobe: Batch 306 aus dem Fenster B304..B313 (angeheftet, NICHT gezogen/merken) - vorher gezogen: B305
- Nutzerlimit (Abo) VOR dem Lauf: Sitzung (5 h): 2 % (Reset 10.10.2026 03:10 (UTC+02:00)) | Woche (7 Tage): 87 % (Reset 13.10.2026 07:00 (UTC+02:00))
- Nutzerlimit (Abo) NACH dem Lauf: keine Angaben
- Hinweis: Mitschnitt und Fehlerdatei lagen in `%TEMP%` (`schatten_aussensicht_b313_deepseek.jsonl`); dieser Bericht ist das EINZIGE Artefakt im Repo.

## Antwort (roh)

<AUSSENSICHT>
Geprueft: TIEFENPROBE B306 (Auftrag, antwort+antwort-forts1, result.json, Denkbloecke, Belege `analysis/_m306/_leseregel.txt`/`_bildzahl.txt`/`_nativ_tafel.txt`), Gegenprobe B321 (Ankerkopf, `analysis/_preflight_321.txt`, `_m321/_raster420.txt`, `_m321/_kandidat.txt`, `hybrid_lauf.cpp:2886-2916`), Stichproben gegen Rohbelege, readme/harness.toml. Am meisten Sorgen macht: die B-Zielzahl steht seit B314 (8 B-Batches) unveraendert auf Praefix 15 / SHAs 33-31, waehrend die Batches ueber Ersatzzahlen (EXT1-Raten) gesteuert werden - in 13 Batches (B308..B321) ist keine neue native Kopfzahl entstanden (150->150, R207 704->704 letzte Messung B317) bei $2,18 fuer die belegten zehn Batches B312..B321.
Stichproben: (1) Review zu B320 ("R1 bei 810M: Praefix 15 -> 9, gleich 85 -> 68, erster ungleicher Paket 10") - **bestaetigt** (`analysis/_m320/_kandidat.txt:32`: 68/72, erster 10, Praefix 9); die Rohzeile dazu `port/build/hybrid_cache/m320_kandidat_R1.pkbb.txt:168431` = "PAKETBB 11 639 351732761 15 0:0,1:0" stuetzt die B321-Aussage "zusaetzliche Gruppe 1:0, kein Split". (2) Review zu B306 ("72 von 77 Lesestroemen sind exakt reproduziert") - **widerspricht dem eigenen Beleg**: `analysis/_m306/_leseregel.txt:96` nennt 5 unter 95 % und Laenge gleich in **71/77**; die 72 ist der >=95-%-Zaehler und wurde so in den Folgeauftrag `runs/b307/auftrag.md:73` uebernommen. Denkbloecke `snapshots/b306/reasoning.jsonl` (Zug 5/100): der Worker rechnet dort selbst die 48-Paket-Grenze nach, leitet die Anker-Vorlage aber aus Paket 1104 ab (Lern- = Teststichprobe) und schliesst aus "pc 8000C664 0 Treffer in beiden Logs" auf "`FUN_8000C654` laeuft nicht" - genau der Punkt, den B307 als Befund (3) kassiert hat; in den aufbereiteten Zahlen steht dieser Fehlschluss nicht mehr.
Messziel: Strang B fuehrt die festgelegte Zahl (Praefix 15 **und** verschiedene SHAs 33/31, `analysis/_preflight_321.txt:35`), Ersatzraten sind als Information gekennzeichnet - in Ordnung, aber die Zahl steht seit B314 still (Befund 1). Strang C fuehrt "150 referenzgleich" (`_preflight_321.txt:16`), obwohl dieselbe Zeile 1 Schatten-ungleichen (`FUN_80029A50`) und 36 nur teilgepruefte nennt -> M313-4 offen.
Arbeit vorhanden: geprueft, nichts gefunden - die aktuelle "kein IOCR im Bootloader"-Aussage ist eine Byte-Suche im Image (`analysis/_m321/_iocr_boot.txt:11-12,27`), keine Log-Abwesenheit; die 8000C654-Log-Fehlstelle ist seit B308 durch die Abwesenheits-Regel ersetzt (`analysis/_m308/_abwesenheit.txt:10`).
TIEFENPROBE B306: Das vorab benannte Widerlegungskriterium (">5 von 48 Paketen unter 95 %") wurde mit genau 5 bestanden, und R traegt vier benannte Freiheitsgrade, darunter die aus Paket 1104 abgelesene Vorlage - das "CONFIRMED, R nicht widerlegt" ist damit naeher eine Werkzeugdefinition als ein Messergebnis; heute gegenstandslos, weil B307 R ausserhalb der Stichprobe widerlegt hat (`analysis/r1b-workstream.md:99`). **Nicht geprueft:** den Quelltext `scripts/m306_leseregel.py`, kein Nachlauf der 637-MB-Logs (Tabellen nur gegen die Belegdatei gehalten), und `runs/b306/result.json` meldet `preflight_frueh: 1` neben "ein Preflight, nach dem Marker" (`runs/b307/review.md:13`) - das konnte ich nicht aufloesen.
</AUSSENSICHT>

<BEFUND n="1" gewicht="hoch" empfaenger="Reviewer">
Beleg: Eingabe BILANZ ("C Koepfe 150 referenzgleich (150 -> 150: +0)", "R207 rueckwaerts 704 gebaut -> 704 gebaut", "B-Phase: 6 B-Batches in Folge ohne Station (B315..B320)", "Median: nicht gemessen") + `analysis/_preflight_321.txt:35` (Praefix 15 | verschiedene SHAs 33/31) + Ankerkopf ("seit B314, unveraendert") + Eingabe "Kosten und Laufzeiten je Batch"
Aussage: Ueber 13 Batches (B308..B321) ist keine einzige neue native Kopfzahl entstanden und die B-Zielzahl steht seit acht B-Batches unveraendert, waehrend die belegten zehn Batches B312..B321 $2,18 gekostet haben; der Plan schneidet trotzdem weiter B-Batches mit SOLL-KOEPFE 0 und hat keine gemessene Durchsatz- oder Abbruchgrenze (die Bilanz sagt selbst "keine Hochrechnung moeglich").
Empfehlung: Im Ankerkopf eine benannte Wechsel-Grenze fuer reine Modellbatches festlegen (z. B. nach N Batches ohne Bewegung der Zielzahl Hebel oder Strangreihenfolge wechseln) und den naechsten Zuschnitt daran binden.
</BEFUND>

<BEFUND n="2" gewicht="mittel" empfaenger="Reviewer">
Beleg: Eingabe BILANZ ("Paket E offen: 4 Koepfe / 59 Insn [gemessen B242, 2026-10-02 10:19: _m242/_c_paket_e.txt]") gegen `analysis/_preflight_321.txt:16` ("Rumpf offen 1 (106 Insn)")
Aussage: Die Paket-E-Zeile des C-Arbeitsvorrats ist ein Stand von B242 (79 Batches alt) und traegt den offenen Rumpf nicht mit - genau die Zeile, die M242-3 verlangt hat; der im readme zuerst abzuarbeitende Vorrat wird also mit einer Zahl geplant, die niemand neu gemessen hat.
Empfehlung: Den Paket-E-Vorrat neu messen (oder die Zeile mit Datum, Quelle und dem Zusatz "veraltet" fuehren) und M242-3 erst danach als erledigt buchen.
</BEFUND>

<BEFUND n="3" gewicht="mittel" empfaenger="Reviewer">
Beleg: `analysis/_m306/_bildzahl.txt:8` ("Bildzahl (PROBE P1-B): 6/48") und die Tafel `:17-64` (die sechs "ja"-Zeilen sind k1120=6, k1123=0, k1124=6, k1154=6, k1158=0, k1196=0 Dreiecke) gegen `analysis/_m307/_bildzahl_b1.txt:13` (39/48) und Eingabe /fragen A2
Aussage: Die Nutzerfrage A2 ("Soll die Bildzahl Zielzahl von Strang B werden?") steht ohne Zahlen und ohne Basis, obwohl die beiden letzten Messungen um Faktor 6,5 streuen und die "6/48" ausschliesslich aus Paketen mit 0 oder 6 Dreiecken stammt, also keinen Teilerfolg belegt; der Ankerkopf B321 fuehrt die Zahl inzwischen gar nicht mehr.
Empfehlung: A2 erst mit Basis, Zahl und getrennt gezaehlten trivialen Paketen vorlegen oder zurueckziehen, solange der Anker die Bildzahl nicht fuehrt.
</BEFUND>

<BEFUND n="4" gewicht="niedrig" empfaenger="Reviewer">
Beleg: `analysis/_m319/_ext1_matrix.txt:21-24` (420M: Bildzahl AKTIV 128,72 | EXT1 1,05 bzw. Pmv 17,24) gegen `analysis/_m320/_kandidat.txt:20` (810M: R0 1,03 | R1 16,98) und `analysis/_m321/_kandidat.txt:19` (R0 1,03 | R2 1,16) - der Ankerkopf fuehrt nur "Pegel 1,05 / Pmv 17,11 / Pmvr 1,14"
Aussage: Derselbe Schalter traegt je Lauf verschiedene Werte (Pmv 17,11 gegen 16,98, Pegel 1,05 gegen 1,03), weil der Nenner "(Schritte - Hauptschleifeneintritt)/551264" mit der Lauflaenge wechselt; die Ankerliste nennt weder Lauf noch Nenner, die Raten sind daher untereinander nicht vergleichbar.
Empfehlung: Bei jeder Rate den Lauf (Schrittzahl) und die Bildzahl AKTIV mitfuehren oder die Liste auf eine einzige, benannte Matrix beschraenken.
</BEFUND>

<PRUEFUNG id="M242-3" status="offen"/>
<PRUEFUNG id="M254-2" status="offen"/>
<PRUEFUNG id="M254-3" status="offen"/>
<PRUEFUNG id="M254-4" status="offen"/>
<PRUEFUNG id="M260-5" status="offen"/>
<PRUEFUNG id="M274-4" status="offen"/>
<PRUEFUNG id="M309-4a" status="erledigt"/>
<PRUEFUNG id="M313-4" status="offen"/>
<PRUEFUNG id="M317-1a" status="offen"/>
<PRUEFUNG id="M317-2" status="offen"/>
