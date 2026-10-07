# Schatten-Aussensicht Batch 289 (claude-sonnet-5-5)

- Zeitpunkt: 2026-10-07T15:40:18+0200
- Anlass: Schattenlauf (dieselbe Eingabe wie die echte Aussensicht: alle 4 Batches (letzte Aussensicht: Batch 285))
- Lauf: rc=0 dauer=411s modell=claude-sonnet-5-5 befunde=7 verworfen=0 zuege=56 runden=31 subtype=success tiefenprobe=B282
- Zuege (Werkzeugrunden): 31 von 70
- Echte Aussensicht: `meta.md` mit `claude-opus-5-5` vom 2026-10-07T11:00:52+00:00
- Tiefenprobe: Batch 282 aus dem Fenster B280..B289 (angeheftet, NICHT gezogen/merken) - vorher gezogen: -
- Nutzerlimit (Abo) VOR dem Lauf: Sitzung (5 h): 25 % (Reset 07.10.2026 16:20 (UTC+02:00)) | Woche (7 Tage): 27 % (Reset 13.10.2026 07:00 (UTC+02:00))
- Nutzerlimit (Abo) NACH dem Lauf: Sitzung (5 h): 60 % (Reset 07.10.2026 16:20 (UTC+02:00)) | Woche (7 Tage): 31 % (Reset 13.10.2026 07:00 (UTC+02:00))
- Hinweis: Mitschnitt und Fehlerdatei lagen in `%TEMP%` (`schatten_aussensicht_b289.jsonl`); dieser Bericht ist das EINZIGE Artefakt im Repo.

## Antwort (roh)

<AUSSENSICHT>
TIEFENPROBE B282 (auftrag, antwort, result.json, reasoning.jsonl, `_m282`-Belege gelesen; SHA-256-Werte nicht neu berechnet, `stream.jsonl` nur an den Stop-Process- und Langlauf-Stellen). Bestätigt: 140 Anfragen, 8949 s, $0,181 (`runs/b282/result.json`) und die 55 min in zwei ungeplanten Langläufen. Die Denkblöcke (`snapshots/b282/reasoning.jsonl`, Zeilen 23, 24, 76, 79) zeigen, was im Bericht fehlt: Der 286/287-Abbruch ist ein Artefakt der Auswertungsgrenze, Rot- und Inertprobe wurden in einem Lauf vermischt, und 551264 wurde um 12:39 aus einer einzigen Messreihe festgelegt.
Stichproben: (1) „805 von 2169 bei 2.7G" ist als Zahl bestätigt (`analysis/_m282/_inhalt.txt:3`), widerspricht aber dem Etikett „Praefix-Charakter" (Befund 2). (2) „EXT1-Einsprünge 1/~149" im Ankerkopf (Commit a6ec84e) widerspricht `analysis/_m289/_irq1_schalter.txt:24` (61,61 je Bild; 149 ist die Paketzahl, nicht die Einsprungzahl je Bild). (3) Die B289-Entscheidung AUS ist bestätigt: Bedingung 1 verfehlt (P126 917 gegen 974, `_irq1_schalter.txt:30`), die übrigen erfüllt.
Messziel: Strang B — Das Ziel ist Präfix und Zahl verschiedener Paket-SHAs. Geführt werden aber P126, Bildzahl, EXT1-Einsprünge und Halt-Art. Das Präfix 124 (erste Abweichung bei MAME 125) steht nur in Einzeldateien, nicht in Vorhersage, Bilanz oder Preflight (`analysis/_preflight_289.txt:32`, `analysis/_m289/_bilanz.txt`). Strang C — 151 referenzgleiche Köpfe, seit 12 Batches unverändert. Die Messgröße ist richtig, bewegt sich aber nicht.
Arbeit vorhanden: Die Aussage „Schreiber von Zelle 0x8018CFC8 unbekannt" ist als offen bestätigt (`analysis/_m286/_paket160_rom.txt:43-46`); kein Dokument schließt sie. Die Adresse `0x40000000` ist seit dem 16.09. als SPU geklärt und wird nicht mehr als Hardware-Frage geführt. Geprüft, nicht mehr offen:
- geprueft: B282-Verallgemeinerung „keine 1 Takt/Instruktion", behoben in B284/B287 (Beleg `analysis/port-batch287-…md:77-84`).
- geprueft: falsche B281-Bedingung „r3 == 0", behoben in B282.
- geprueft: Kürzung der port_suche-Ausgabe, behoben in B289 (Beleg Commit 3b8c9bc, Rotprobe `analysis/_m289/_port_suche_kuerzung.txt:41-49`).
</AUSSENSICHT>

<BEFUND n="1" gewicht="hoch" empfaenger="Reviewer">
Beleg: `analysis/_preflight_289.txt:32`; `analysis/_m289/_bilanz.txt`; `analysis/port-batch282-b-bildtakt-2026-10-06.md:26-35,62-68`; `analysis/_m289/_irq1_schalter.txt:33` (Präfix 124 erfüllt, versch. SHAs 33 gegen 62)
Aussage: Das festgelegte Ziel von Strang B (Präfix plus Zahl verschiedener Paket-SHAs) ist nicht die Fortschrittszahl, die geführt wird. Sie steht weder in den Vorhersagen noch in der Bilanz oder im Preflight. Geführt werden stattdessen P126, Bildzahlen und Einsprünge, die ein anderes Ziel messen. Das Präfix ist bei 124 geblieben (B282, B287, B289), und die vielen Batches mit Zeit-, Takt- und IRQ-Arbeit haben es nicht bewegt. Die SHA-Zahl hat zudem zwei Definitionen: „5/13" in B282 und „33/62" in B289. Ein Vergleich über Batches ist so nicht möglich.
Empfehlung: Präfix und verschiedene Paket-SHAs mit einer festen Definition als Zeile in Vorhersage und Bilanz führen. Daneben könnte jeder Batch-Auftrag sein FERTIG-WENN an dieser Zahl ausrichten statt an der Lieferung eines Schalters oder Belegs.
</BEFUND>

<BEFUND n="2" gewicht="mittel" empfaenger="Reviewer">
Beleg: `analysis/_m282/_inhalt.txt:3`; `snapshots/b282/reasoning.jsonl` Zeilen 23-24
Aussage: Das B282-Etikett „Praefix-Charakter" für 805 von 2169 Fenstern bei 2.7G überzieht den Umfang. Die Zahl stimmt, aber 805 von 2169 sind 37 %, und der Präfix-Begriff des Ziels meint die Länge der belegten Fensterfolge gegen MAME (124). Die Denkblöcke zeigen, dass die „286/287"-Grenze ein Auswertungsartefakt war. Die Klassenbehauptung „dieselbe Klasse" ist damit nicht belegt.
Empfehlung: Das Etikett auf „Anteil gleicher Fenster" ändern oder streichen und den Präfix-Begriff nur für die Folgelänge verwenden.
</BEFUND>

<BEFUND n="3" gewicht="mittel" empfaenger="Reviewer">
Beleg: `analysis/_m286/_paket160_rom.txt:43-46`; `runs/b283/auftrag.md` bis `runs/b286/auftrag.md` (P160-Quelle viermal beauftragt); `runs/b289/auftrag.md:209`
Aussage: Die erste Abweichung liegt bei MAME 125, und der Schreiber von Zelle 0x8018CFC8 ist seit vier Batches offen. B289 stuft ihn auf „nachrangig" herab, ohne dass er gefunden oder ausgeschlossen wäre. Zugleich bleiben die Abweichungen 130/159/172 unter `--kaltboot` bestehen (`port-batch287-…md:77-84`). B289 hat stattdessen den IRQ1-Schalter gebaut (Ausgang AUS, P126 917). Die Arbeit hat damit das Hindernis des Präfixes umgangen, nicht geöffnet.
Empfehlung: Prüfen, ob die Herabstufung begründet ist (etwa durch eine Messreihe, die den Schreiber ausschließt) oder ob die Wiederholung des Problems über vier Batches ein Vorgehensproblem ist. Der Beleg dafür müsste in `analysis/` stehen.
</BEFUND>

<BEFUND n="4" gewicht="mittel" empfaenger="Reviewer">
Beleg: `analysis/_m289/_irq1_schalter.txt:13` (~149) gegen `:24` (61,61); Ankerkopf `analysis/r1b-workstream.md` (Stand B289, Einsprünge 1/~149)
Aussage: Die Zahl „~149 Einsprünge je Hauptbild" ist falsch. 67096/1089 ergibt 61,6; 149 ist die Paketzahl. Der Ankerkopf trägt die falsche Zahl weiter, und sie ging nicht durch die Rotprobe, die dieselbe Datei an anderer Stelle korrekt ausweist.
Empfehlung: Zahl im Anker und in der Datei auf 61,6 korrigieren und die Quelle des Quotienten angeben.
</BEFUND>

<BEFUND n="5" gewicht="mittel" empfaenger="Reviewer">
Beleg: `runs/b282/result.json`; `snapshots/b282/reasoning.jsonl` Zeile 76, 79; `analysis/port-batch282-b-bildtakt-2026-10-06.md:84`
Aussage: Das FERTIG-WENN von B282 misst Lieferung, nicht Wirkung. Der Takt 551264 wurde um 12:39 aus einer Messreihe festgelegt und mit 55 min ungeplanter Laufzeit in zwei Langläufen erreicht. Eine eigene Vorhersagezeile für die Wirkung auf Präfix oder SHA-Zahl fehlt, daher lässt sich nicht nachprüfen, ob der Takt etwas gebracht hat. Das Präfix blieb 124.
Empfehlung: Für Zeit- und Takt-Batches vor dem Lauf eine Soll/Ist-Zeile für die Wirkung auf das Präfix festschreiben, mit Laufzeitgrenze für Langläufe.
</BEFUND>

<BEFUND n="6" gewicht="niedrig" empfaenger="Reviewer">
Beleg: `readme.md:775-796` gegen `analysis/hybrid-plan.md:9-10`; `analysis/r1b-workstream.md:1141`
Aussage: `readme.md:775-796` führt einen veralteten B215-Block, dessen Zielsatz zwar angeglichen wurde, dessen Inhalt aber nicht auf den aktuellen Stand gebracht ist. Im Anker steht (`r1b-workstream.md:1141`) eine alte, nie nachgemessene UEBERTRAG-Zeile. Beides ist geeignet, Zahlen ungeprüft weiterzutragen.
Empfehlung: Den B215-Block auf den Stand B289 bringen oder als historisch markieren, und die UEBERTRAG-Zeile neu messen oder streichen.
</BEFUND>

<BEFUND n="7" gewicht="niedrig" empfaenger="Reviewer">
Beleg: `analysis/r1b-workstream.md` (Ankerkopf, Strang C „ruht"); Eingabe Bilanz-Trend der letzten 12 Batches
Aussage: Strang C steht seit 12 Batches bei 151 referenzgleichen Köpfen. Die Messgröße ist richtig gewählt (referenzgleich, nicht „gebaut"), bewegt sich aber nicht, und „ruht" ist im Anker als Zustand eingetragen, nicht als Entscheidung mit Beleg. Der Plan bis zum Ziel eines eigenständigen nativen Ports hängt damit bei gleichbleibendem Durchsatz allein an Strang B, dessen Präfix ebenfalls stillsteht (Befund 1).
Empfehlung: Festhalten, ob „ruht" bewusst ist. Falls ja, sollte die Priorisierung im Anker mit Begründung stehen. Sollte die Priorität des Ziels (nativer Port) geändert werden, wäre das eine Nutzerentscheidung.
</BEFUND>

<PRUEFUNG id="M242-3" status="erledigt" beleg="`analysis/_m289/_port_suche_kuerzung.txt:41-49`: Wirkung mit Rotprobe belegt (alt 0 Port-Treffer, neu PORT-TREFFER-Zeile)"/>
<PRUEFUNG id="M254-2" status="offen" beleg="keine belegte Wirkung in Eingabe Offene frühere Befunde"/>
<PRUEFUNG id="M254-3" status="offen" beleg="keine belegte Wirkung in Eingabe Offene frühere Befunde"/>
<PRUEFUNG id="M254-4" status="offen" beleg="keine belegte Wirkung in Eingabe Offene frühere Befunde"/>
<PRUEFUNG id="M260-5" status="offen" beleg="keine belegte Wirkung in Eingabe Offene frühere Befunde"/>
<PRUEFUNG id="M272-4" status="offen" beleg="keine belegte Wirkung in Eingabe Offene frühere Befunde"/>
<PRUEFUNG id="M274-4" status="offen" beleg="keine belegte Wirkung in Eingabe Offene frühere Befunde"/>
<PRUEFUNG id="M285-5a" status="offen" beleg="keine belegte Wirkung in Eingabe Offene frühere Befunde"/>
<PRUEFUNG id="M289-1" status="offen" beleg="Wirkung noch nicht gemessen; Präfix bleibt 124 (`analysis/_m289/_irq1_schalter.txt:33`)"/>
<PRUEFUNG id="M289-2" status="offen" beleg="Wirkung noch nicht gemessen; Messgröße steht nicht in `analysis/_m289/_bilanz.txt`"/>
<PRUEFUNG id="M289-3" status="offen" beleg="Wirkung noch nicht gemessen; Schreiber von 0x8018CFC8 weiter offen (`analysis/_m286/_paket160_rom.txt:43-46`)"/>
<PRUEFUNG id="M289-4" status="erledigt" beleg="Commit 3b8c9bc, Rotprobe `analysis/_m289/_port_suche_kuerzung.txt:41-49`: alt 0 Port-Trefferzeilen, neu 1"/>
<PRUEFUNG id="M289-5" status="offen" beleg="Wirkung noch nicht gemessen; im B289-Review erst gemeldet"/>
