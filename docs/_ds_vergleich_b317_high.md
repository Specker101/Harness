# Schatten-Aussensicht Batch 317 (deepseek-flash[1m])

- Zeitpunkt: 2026-10-09T23:39:11+0200
- Anlass: Schattenlauf (dieselbe Eingabe wie die echte Aussensicht: alle 4 Batches (letzte Aussensicht: Batch 313))
- Lauf: rc=0 dauer=278s modell=deepseek-flash[1m] befunde=3 verworfen=0 zuege=47 runden=26 subtype=success tiefenprobe=B316
- Zuege (Werkzeugrunden): 26 von 70
- Echte Aussensicht: `meta.md` mit `claude-opus-5-5` vom 2026-10-09T16:13:29+00:00
- Tiefenprobe: Batch 316 aus dem Fenster B308..B317 (angeheftet, NICHT gezogen/merken) - vorher gezogen: -
- Nutzerlimit (Abo) VOR dem Lauf: Sitzung (5 h): 2 % (Reset 10.10.2026 03:10 (UTC+02:00)) | Woche (7 Tage): 87 % (Reset 13.10.2026 07:00 (UTC+02:00))
- Nutzerlimit (Abo) NACH dem Lauf: keine Angaben
- Hinweis: Mitschnitt und Fehlerdatei lagen in `%TEMP%` (`schatten_aussensicht_b317_deepseek.jsonl`); dieser Bericht ist das EINZIGE Artefakt im Repo.

## Antwort (roh)

<AUSSENSICHT>
TIEFENPROBE B316: fünf nachprüfbare Behauptungen gegen die Rohdaten gehalten, alle bestätigt — TRACE-Zählungen 3953/3758/1/1/2/92/1 (`_m316/_trace16.txt:15214-15222`), „2911 Schreibungen auf 78000034" und „372 über pc 8000C728" **selbst nachgezählt = 2911/372** (Grep in `capture/error_boot_attract_frames.log`), MAME-Paket 16 (1:1) `dcbe298920b5` (`_m291/_mame_pak_bb.txt:18`); einzige Lücke: `_m316/_nativ16.txt:15,31` führt die Läufe N1/N2 als „Dauer -1.0 s", die 25-min-Grenze des Auftrags ist damit nicht belegt (result.json: beide in 881,1 s). Stichproben: Review B320 „R1 810M Präfix 15→9, gleich 85→68, erster ungleicher 10" — bestätigt (`_m321/_r1_verschiebung.txt:26,40`); Review B319 „EXT1 nur einmal je Fenster, Merker `ext1_gemeldet`" — bestätigt (`hybrid_lauf.cpp:2886-2892`). Denkblöcke B316: der Worker hat selbst gefunden, dass die Meldung „Gesamt 98 -> 97" eine **feste Zeichenkette** war (`snapshots/b316/reasoning.jsonl:30`, `hybrid_lauf.cpp:5709`) — behoben in B318 (`hybrid_lauf.cpp:5737-5765`).
Messziel: Strang B nennt Präfix **und** verschiedene SHAs (Ankerkopf „Präfix je Board/Bank 15 | verschiedene SHAs 33/31") — zielkonform; die flache Variante derselben Zeile (erster ungleicher 125) ist daneben nur Information. Strang C: 150 referenzgleich ist die Zielfrage, steht aber seit B294 unverändert (28 Batches). Arbeit vorhanden: geprüft — B316 „`FUN_8000D08C`/`FUN_8000C6B4` nicht in `kHeads`": Grep in `port/src/ckopf_leaves.cpp` zeigt `8000C6B4` gar nicht, `8000D08C` nur als `host.call`-Ziel, keinen Tabelleneintrag → Behauptung hält; keine falsche „fehlt"-Aussage in diesem Lauf gefunden.
Am meisten Sorge machen die zwei stillstehenden Fortschrittszahlen bei laufender Rechnung (F1) und eine Bilanzzeile, die seit B314 eine um 1 zu kleine Zahl führt (F2). Die Nutzerentscheidung R314-2 (Aussensicht-Takt senken) ist im Harness weiterhin ohne Wirkung (M317-1a).
</AUSSENSICHT>

<BEFUND n="1" gewicht="hoch" empfaenger="Reviewer">
Beleg: `analysis/_preflight_293.txt:16` (151) gegen `analysis/_preflight_294.txt:16` bis `analysis/_preflight_321.txt:16` (150, unverändert = 28 Batches); `analysis/_preflight_314.txt:35` gegen `analysis/_preflight_321.txt:35` („gleich 85 | ungleich 53 | erster ungleicher 16 | Praefix 15 | verschiedene SHAs 33/31", unverändert = 8 Batches); Eingabe „Kosten und Laufzeiten je Batch" (B314..B321 = 8 Batches, 10,4 h, $1,42); Eingabe „BILANZ" („C-Arbeitsvorrat: 1403 Köpfe nicht gebaut").
Aussage: Beide führenden Fortschrittszahlen stehen auf demselben Wert — C seit 28 Batches bei 150 (bei 1403 offenen Köpfen), B seit 8 Batches bei 15/33-31 —, obwohl für den B-Stillstand 10,4 h und $1,42 verbraucht wurden; nirgends ist eine Abbruch- oder Wiederaufnahmebedingung notiert.
Empfehlung: Für beide Stränge eine Zahl mit Frist in den Anker schreiben (B: wie viele Batches darf das Paket-16-Rätsel noch kosten, bevor die Fensterbreite als einziger Hebel abgelöst wird; C: ab welchem Batch läuft die systematische Reihe wieder).
</BEFUND>

<BEFUND n="2" gewicht="mittel" empfaenger="Reviewer">
Beleg: `scripts/m149_bilanz.py:567-573` (`m_ckoepfe_schatten`: `n = ref - schat`) gegen `scripts/c_kopf_check.py:241-247` (`_ref = koepfe - _rumpf[0] - _n_schatten`, erste Zahl = 152−1−1 = 150) und `analysis/_preflight_321.txt:16` (150 / … / „davon im Schatten ungleich: 1") → die Bilanzzeile meldet **149** (Eingabe BILANZ: „C Koepfe ohne Schatten-ungleiche … referenzgleich **149").
Aussage: Die seit B314 geführte Zeile zieht den Schatten-ungleichen Kopf ein zweites Mal ab; die erste Zahl der Preflight-Zeile enthält diesen Abzug seit B294 TEIL 3 (`analysis/port-batch294-b-busy-2026-10-08.md:38`: „Registry-Koepfe minus Rumpf-offen minus Schatten-ungleich (151 − 0 − 1)") bereits, die richtige Zahl ist 150.
Empfehlung: In `m_ckoepfe_schatten` `n = referenzgleich` setzen (ohne zweiten Abzug) oder die Doppelzeile ersatzlos streichen — sie ist seit B314 eine Doppelzählung, die die verlangte Gegenprobe aus M313-4 unnötig machte.
</BEFUND>

<BEFUND n="3" gewicht="mittel" empfaenger="Reviewer">
Beleg: Eingabe „Kosten und Laufzeiten je Batch" (B317 62,6 | B318 74,2 | B319 107,0 | B320 50,5 | B321 39,9 min gegen ein 150-min-Fenster) und `runs/b316/result.json` („aufwand": wand_min 107,9, fester_min 23,5, preflight_min 10,2, arbeit_pct 78,2); dazu die eigenen Reviewbemerkungen „mein Zuschnitt war zu klein" (`runs/b319/review.md`, zu B318) und „Wieder kurz: 51 min, Arbeit 32 min" (`runs/b321/review.md`, zu B320).
Aussage: Fünf der letzten sechs Batches blieben unter der Hälfte des Zeitfensters, während je Batch rund 10 min Preflight und ~13 min Start/Schluss fest anfallen (B316: 21,8 % der Batchzeit) — der Zuschnitt kostet damit mehrfach den festen Anteil, ohne dass die Strangarbeit wächst; das wiederholt sich über B317–B321 statt einmalig aufzutreten.
Empfehlung: Den Auftrag mit einem gemessenen Arbeitsbudget (Arbeitsminuten statt Wandfenster) versehen oder zwei kleine Posten zu einem Batch zusammenlegen, damit der feste Anteil je Arbeitsstunde sinkt.
</BEFUND>

<PRUEFUNG id="M242-3" status="erledigt"/>
<PRUEFUNG id="M254-2" status="offen"/>
<PRUEFUNG id="M254-3" status="offen"/>
<PRUEFUNG id="M254-4" status="offen"/>
<PRUEFUNG id="M260-5" status="offen"/>
<PRUEFUNG id="M274-4" status="offen"/>
<PRUEFUNG id="M309-4a" status="erledigt"/>
<PRUEFUNG id="M313-4" status="verworfen"/>
<PRUEFUNG id="M317-1a" status="offen"/>
<PRUEFUNG id="M317-2" status="offen"/>
