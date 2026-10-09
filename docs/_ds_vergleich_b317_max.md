# Schatten-Aussensicht Batch 317 (deepseek-flash[1m])

- Zeitpunkt: 2026-10-09T23:59:29+0200
- Anlass: Schattenlauf (dieselbe Eingabe wie die echte Aussensicht: alle 4 Batches (letzte Aussensicht: Batch 313))
- Lauf: rc=0 dauer=389s modell=deepseek-flash[1m] befunde=4 verworfen=0 zuege=67 runden=38 subtype=success tiefenprobe=B316
- Zuege (Werkzeugrunden): 38 von 70
- Echte Aussensicht: `meta.md` mit `claude-opus-5-5` vom 2026-10-09T16:13:29+00:00
- Tiefenprobe: Batch 316 aus dem Fenster B308..B317 (angeheftet, NICHT gezogen/merken) - vorher gezogen: -
- Nutzerlimit (Abo) VOR dem Lauf: Sitzung (5 h): 2 % (Reset 10.10.2026 03:10 (UTC+02:00)) | Woche (7 Tage): 87 % (Reset 13.10.2026 07:00 (UTC+02:00))
- Nutzerlimit (Abo) NACH dem Lauf: keine Angaben
- Hinweis: Mitschnitt und Fehlerdatei lagen in `%TEMP%` (`schatten_aussensicht_b317_deepseek.jsonl`); dieser Bericht ist das EINZIGE Artefakt im Repo.

## Antwort (roh)

<AUSSENSICHT>
Geprueft (TIEFENPROBE B316): Auftrag, antwort.md/antwort-forts1.md, result.json, Denkbloecke, Belegdateien. Stichprobe 1: die Rohzeilen-Summenprobe "2911 Schreibungen auf 0x78000034" - eigene Grep-Zaehlung in `capture/error_boot_attract_frames.log` ergibt exakt 2911, bestaetigt. Stichprobe 2: die B320-Review-Zahlen (R1 gleich 68 | Praefix 9 | erster ungleicher 10 | SHAs 33/32) stehen so in `_m320/_kandidat.txt:32`, bestaetigt; ebenso `_mame_pak_bb.txt:60` und der B321-Ankerverweis `m320_kandidat_R1.pkbb.txt:168431` (`PAKETBB 11 639 351732761 15 0:0,1:0`).
Denkbloecke B316: der Worker hat im Vorhersage-Entwurf Cache-Schluessel-Digits erfunden ("I made up digits") und vor dem Commit durch den echten Schluessel ersetzt - der Vorhersage-Commit `66ae9f9` traegt `166c01a8f8c657d2…`, und genau diese Datei liegt in `port/build/hybrid_cache/`; geprueft, behoben, kein Befund.
Messziel: Strang B fuehrt korrekt Praefix 15 + verschiedene SHAs 33/31 (n=138) - aber unveraendert in acht Preflight-Zeilen B314..B321; Strang C ruht (150 referenzgleich, die Zahl ohne Schatten-ungleiche = 149 steht nur als INFO-Zeile). Arbeit vorhanden: die "fehlt"-Aussage des laufenden Batches (Bootloader schreibt kein IOCR) selbst nachgeprueft - `analysis/_m321/_iocr_boot.txt` stuetzt sie mit BE/LE-Suche UND einer Decoder-Gegenprobe an main.bin (IOCR=2), die Negativaussage ist gedeckt.
Sorgen: sieben Batches ohne Bewegung der B-Zielzahl, waehrend das Wochenkontingent bei 87 % steht (heute +11 Punkte in 13 h - der Rest reicht noch ~15 h), und eine Nutzerentscheidung (R314-2), die im Harness weiter ohne Wirkung ist.
</AUSSENSICHT>

<BEFUND n="1" gewicht="hoch" empfaenger="Reviewer">
Beleg: `analysis/_preflight_314.txt:35`, `_preflight_315.txt:35`, `_preflight_316.txt:35`, `_preflight_317.txt:35`, `_preflight_318.txt:35`, `_preflight_319.txt:35` und `_preflight_321.txt:35` tragen alle "gleich 85 | ungleich 53 | erster ungleicher 16 | Praefix 15 | verschiedene SHAs 33/31"; Eingabe BILANZ: "Fortschritt: 4 B-Batches in Folge weder Station noch Bewegung (B317..B320); Hinweisgrenze 6 (R277-1)".
Aussage: Die Zielzahl des Strangs B steht seit B315 (7 Batches, acht Preflight-Zeilen) wortgleich still, und mit B321 (Raster kollabiert auf 1,14/Bild, R2 kein Treffer, kein Vorgabewechsel) ist der fuenfte Batch ohne Bewegung erreicht - die Hinweisgrenze 6 ist mit B322 erreicht, ohne dass eine Entscheidung ansteht.
Empfehlung: Vor B322 entscheiden, was die Grenze ausloest (R277-1 neu bewerten, Obergrenze fuer reine Modellschalter-Arbeit), statt einen weiteren Modellschalter zu messen.
</BEFUND>

<BEFUND n="2" gewicht="mittel" empfaenger="Reviewer">
Beleg: Grep "DisplayBank|display_bank" ueber `port/`: Treffer nur in `port/src/*` und `port/include/*` (u. a. `port/src/display_bank.cpp:116-119` `reg.add(kDisplaySwitch, …)`), **kein** Treffer in `port/hybrid/*`; `port/include/port/display_bank.h:31-33` ("die MMIO … wird GEZAEHLT, nicht nachgebildet"); `analysis/_m316/_nativ16.txt:47-48`.
Aussage: Der Anzeigeschalter ist im PORT nativ (HostRegistry), im HYBRID-Laeufer aber nirgends eingebaut - die B315-Vorlage ("sechs RAM-Wirkungen nativ, MMIO nur gezaehlt") und die N2-Messung (`--kopf-verstecken 8000D08C`, strukturell blind, da der Schalter laut `port/hybrid/hybrid_lauf.cpp:5746-5760` nur einen Zaehler ausblendet) vermischen Port-Hosts und Hybrid-Registry `ckopf::heads()`; das hat in B315/B316 eine Batchhaelfte gekostet.
Empfehlung: Im Anker beide Registry-Begriffe trennen (Hybrid = `ckopf::heads()`, Port = `HostRegistry`) und vor jedem "nativ/interpretiert"-Test den Traeger mit Datei:Zeile nennen.
</BEFUND>

<BEFUND n="3" gewicht="mittel" empfaenger="Nutzer">
Beleg: Eingabe KOSTEN ("Woche (7 Tage): 87 % (Reset 13.10.2026 07:00)"), Eingabe Kopf ("Takt: alle 4 Batches"), `g:\Harness\harness\harness.toml:185` (`aussensicht_takt = 4`, unveraendert) und der Beleg zu M317-1a (0,65-0,85 Punkte/h).
Aussage: Die Entscheidung R314-2 (Takt bis 13.10. senken, keine Ueberziehung) ist im Harness weiterhin ohne Wirkung; nach der heutigen Messung (76 % um 07:19Z -> 87 % um 20:21Z, also ~0,85 Punkte/h) sind die restlichen 13 % in etwa 15 h erschoepft, danach ruht der Lauf bis zum Reset am 13.10. 07:00.
Empfehlung: Den Takt jetzt in `harness.toml:185` eintragen oder den Stopp bis 13.10. bewusst annehmen.
</BEFUND>

<BEFUND n="4" gewicht="niedrig" empfaenger="Reviewer">
Beleg: `analysis/_m316/_nativ16.txt:15` und `:31` ("Dauer **-1.0 s**") gegen `runs/b316/result.json` (langsamster Aufruf `m316_nativ16.py`: 881,1 s) und `runs/b316/antwort.md:30` (Roh-Stdouts von N1/N2 nicht archiviert); dazu `analysis/port-batch321-b-zustellraster-2026-10-10.md` (Dateiname) gegen `git show 78fab5d` (Datum 2026-10-09 23:00).
Aussage: Zwei Belegangaben des Belegapparats sind nicht gemessen bzw. falsch datiert: die Laufdauer der N1/N2-Laeufe steht als Sentinel `-1.0 s` in der Belegdatei (die Auftragsgrenze "unter 25 min" ist damit nicht belegt), und ein am 09.10. gelaufener Batch traegt ein Dokument mit dem Datum 10.10.
Empfehlung: Nicht gemessene Belegfelder als "nicht gemessen" kennzeichnen (mit der echten Dauer aus dem Lauf) und das Batchdatum aus der BATCH-UHR uebernehmen.
</BEFUND>

<PRUEFUNG id="M242-3" status="erledigt">Eingabe PLAN/IST zeigt keine +3-Prognose mehr ("MEDIAN: nicht gemessen"), Eingabe BILANZ: "C-Rate je C-Batch: nicht gemessen … HYPOTHESIS: keine Hochrechnung moeglich" - die zu hohe Hochrechnung existiert nicht mehr.</PRUEFUNG>
<PRUEFUNG id="M254-2" status="offen">Strang C ruht seit B292 (Eingabe BILANZ: "B292..B321, 30 Batches"), kein C-Batch hat Treffer-Koepfe gebuendelt gebaut; die Kostenfrage des A4-Caches ist unberuehrt und wird bei C-Wiederaufnahme wieder akut.</PRUEFUNG>
<PRUEFUNG id="M254-3" status="offen">Die Ankerzeile steht weiter als blanke Tatsache ohne STRONG-INFERENCE-Kennzeichnung: `analysis/r1b-workstream.md:1380` ("Ein NICHT betretener neuer Kopf aendert den Schluessel NICHT"); die geforderte Vorher/Nachher-Messung fehlt.</PRUEFUNG>
<PRUEFUNG id="M254-4" status="offen">Der C-Zuschnitt (Zielband 300-420, Insn-Durchsatz) wurde nie aus dem Kandidatenvorrat abgeleitet und ist mit dem Ruhen von Strang C suspendiert, nicht entschieden - ein Beleg fuer eine Wirkung fehlt.</PRUEFUNG>
<PRUEFUNG id="M260-5" status="offen">Heute erneut geprueft: `readme.md:775` fuehrt "STRAND B … status at Batch 215 (2026-09-29)", `readme.md:790` "Mix since B208: 2 B : 1 C" - bei B321 also 106 Batches alt und im Mischungsverhaeltnis falsch (Eingabe BILANZ: 30 B-Batches ohne C-Batch).</PRUEFUNG>
<PRUEFUNG id="M274-4" status="offen">Das Muster ist erneut aufgetreten (B315-Urteil "der Schreiber laeuft nicht" wurde in B316 als Log-Artefakt widerlegt, `analysis/_m316/_aufrufer16.txt:53-58`); die geforderte Gegenprobe im Batch-Dokument selbst ist nicht fester Bestandteil des Abschlusses.</PRUEFUNG>
<PRUEFUNG id="M309-4a" status="erledigt">Beide Fragen sind heute sichtbar: die Bildzahl-Frage steht als A2 in `Eingabe OFFENE FRAGEN UND ENTSCHEIDUNGEN`, die Kontingent-Frage ist als R314-2/R320-1 im Umlauf (der B316-Auftrag fuehrt sie als Nutzerentscheide).</PRUEFUNG>
<PRUEFUNG id="M313-4" status="offen">Die Zaehlzeile ist unveraendert `analysis/_preflight_321.txt:16` ("C Koepfe 150 / 8510 / 0 referenzgleich … davon im Schatten ungleich: 1"); die geforderte Zahl ohne Schatten-ungleiche existiert nur als ausdruecklich "reine INFO" gekennzeichnete Zusatzzeile (`analysis/_m317/_bilanz.txt:40`: referenzgleich 149).</PRUEFUNG>
<PRUEFUNG id="M317-1a" status="offen">`harness.toml:185` steht weiter auf `aussensicht_takt = 4`; dieser Lauf ist der 4er-Takt nach B317, und der Verbrauch liegt nach Eingabe KOSTEN bei 87 % der Woche.</PRUEFUNG>
<PRUEFUNG id="M317-2" status="offen">Der Befund gilt heute unveraendert: `_preflight_321.txt:35` zeigt dieselbe Zielzahl wie `_m316/_nativ16.txt:47-48` (Registry aus/an ohne Wirkung); die vorgeschlagene zweite Zahl liegt als Frage A2 beim Nutzer, eine Obergrenze fuer reine Modellarbeit ist nicht gesetzt.</PRUEFUNG>
