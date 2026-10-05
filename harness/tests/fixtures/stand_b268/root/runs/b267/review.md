Ich habe genug Belege und schreibe jetzt das Review.

<TELEGRAM_SUMMARY>
Ergebnis: Der Hänger nach B265 ist geklärt. Die Hauptschleife wartete in ihrer mittleren Schleife auf das Flag `0x800AEC65` (18,8 Mio. Umläufe). Drei Hardware-Maßnahmen lösen ihn, jede mit Gegenschalter (`7ab1288`, `da7eb08`): FUN_80026C34 läuft jetzt 561× statt 2×, Loop B nur noch 54×, c=2, e=0x11. Die Belege stimmen (`_m266/_bildtakt.txt:47`, `_a4_cg3_900m.txt:20537`).
Bewertung: Gut, aber zwei Lücken. Erstens ist nicht gezeigt, ob jede der drei Maßnahmen nötig ist (Rotprobe nur als Grundlauf). Zweitens steht die Erklärung für e=0x11 schon im Port: Ohne gültigen Buchhaltungssatz zeigt das Spiel „PLEASE SET the TIME for the BOOK KEEPING" und wartet (`opmode_payload.cpp:890-907`), das wurde nicht genutzt. Die Vorwärmung wirkte nicht, deshalb liefen drei Preflights mit zusammen 33 min.
FERTIG WENN erreicht: ja – (a)–(g), Ende an der Schwelle mit Get-Date.
Kosten/Laufzeit: $0.24, 2h15m, 142 Anfragen; gültiger Preflight e3efa14.
Nächster Batch: Einzel-Rotproben, Maßnahmen auf Vorgabe EIN, Buchhaltungssatz im NVRAM klären.
B-SCHRITT: 4/5 Boot bis Hauptschleife, B-Batch 37 (Zählung, keine Grenze – Nutzerentscheid 30.09.)
STATION: nein
UEBERTRAG: TEIL 2c (Vorgabe EIN) -> B267 TEIL 1
ENTSCHIEDEN: R265-1 übernommen – Strang B bis B275, neuer Wartepunkt mit Maßnahme zählt als Bewegung
ENTSCHIEDEN: B266 = Bewegung (Wartepunkt Loop B + 3 Maßnahmen), Zähler ohne Station und ohne Bewegung 0/2
ENTSCHIEDEN: Ankerposten (1) „A oder B" geschlossen (Nutzerantwort R265-1)
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: ghidra-read
program: /830d01.27p.main.bin
</DS_TOOLS>

## VERALLGEMEINERUNG

**F1 – Port-Wissen zum nächsten Engpass nicht genutzt.**
- (a) Fehlerklasse: Der Worker stuft den Engpass als STRONG INFERENCE ein („Werte 08/10/11 stammen aus anderen Stufen"), obwohl Handler 8, 16 und 17 im Port gebaut sind (`port/src/opmode_payload.cpp:872-907`). Schon das B265-Orakel zeigte die Folge e 0→8→16→17. Das ist das vierte Auftreten dieser Klasse nach B260, B264 und B265.
- (b) Prüfung: Für jede Funktion und jeden Schreib-PC der Kette (hier `8002651C`, `800264C0`, `80026498`, die Schreiber von `0x800B3A60`) kommt die Ausgabe von `python scripts/port_suche.py <adresse>` ins Dokument, und zwar vor jeder Einstufung.
- (c) Nicht geprüft: ob der gebaute Port-Handler in allen Zweigen ROM-gleich ist. Das zeigt nur das Orakel für den gemessenen Zustand.

**F2 – Maßnahmenbündel ohne Einzelnachweis.**
- (a) Fehlerklasse: Drei Maßnahmen wirken nur zusammen gemessen. Die „Rotprobe" ist der Grundlauf, weil alle drei Vorgabe AUS sind. Ob jede einzelne nötig ist, ist offen. `_takt_beide_kurz` zeigt nur, dass zwei nicht reichen.
- (b) Prüfung: Je Maßnahme ein Lauf mit „alle EIN außer dieser". Nur Maßnahmen, deren Wegnahme Loop B wieder öffnet, werden Vorgabe EIN.
- (c) Nicht geprüft: ob die Werte der Maßnahmen (Status `0x3FA`, Quittung 0) im späteren Spiel richtig bleiben.

**F3 – Vorwärmung wirkungslos.**
- (a) Fehlerklasse: Nach der letzten Änderung unter `port/hybrid/` lief keine wirksame Vorwärmung. `Hybrid-Lauf` brauchte 411 s statt 4 s (`_m266/_preflight_zeiten.txt:33` gegen `_m265/…:33`), und das bei drei Preflights.
- (b) Prüfung: Die Vorwärmung läuft nach dem letzten `port/`-Commit. Im Dokument stehen die Sekunden für `Hybrid-Lauf` aus `_preflight_zeiten.txt`, Soll unter 30 s.
- (c) Nicht geprüft: warum ein Lauf mit Maßnahmen etwa 4× länger dauert (989 s gegen 230 s). Das wird nur gemessen, nicht behoben.

<DS_INSTRUCTION>
STRANG: B
Batch 267 - Silent Scope Decomp

SOLL-KOEPFE: 0

STAND UEBERNEHMEN:
Strang B, B-Batch 38.
**Nutzerentscheid R265-1 (2026-10-04, wortgetreu):** „Strang B laeuft die naechsten 10 B-Batches (B266 bis B275) weiter, ohne Rueckfrage und ohne Wechsel zu C. Der Stillstandszaehler 4 von 4 loest in dieser Zeit keine Rueckfrage und keinen Strangwechsel aus. Als Bewegung zaehlt zusaetzlich zur Stationsregel ein belegter neuer Wartepunkt der Hauptschleife, fuer den eine Massnahme mit Gegenschalter, Rotprobe und eigenem Commit vorliegt. Die Frage B oder C kommt nach B275 oder frueher, wenn zwei B-Batches in Folge weder Station noch solche Bewegung zeigen. Die Stationsregel selbst und der Halt werden nicht umdefiniert."
**ENTSCHEIDUNG (Reviewer):**
- B266 ist keine Station (opmode 00, c 02).
- B266 ist eine **Bewegung**: Wartepunkt Loop B (`80008B1C..80008B34`, Flag `0x800AEC65`), drei Maßnahmen mit Gegenschalter in `7ab1288`/`da7eb08`.
- Zähler „B-Batches in Folge ohne Station und ohne Bewegung": **0 von 2**.
- B-Fenster: B266 ist Batch 1 von 10.
Vorgabe: `Hybrid-A4 900000000 | 80008BB0 | Schranke` (`_preflight_266.txt`, HEAD `e3efa14`). Die Maßnahmen `--cg-quittung`, `--vblank1`, `--cg-status` sind Vorgabe AUS. Mit allen dreien: c=02, e=0x11, opmode 00, Halt-PC 80008450, Loop B 54 (`_m266/_a4_cg3_900m.txt:20537`).
**Nächster Engpass (Reviewer-Befund, Port belegt):**
- `FUN_800261C4` beendet die Init-Kette erst bei e ≥ 0x12.
- Handler 16 (`0x800264C0`): Ist das Byte `[SDA(0xBC)]` = `0x800B3A60` („NVRAM-RAM-Satz", `port/include/port/opmode.h:454`) ≠ 0, setzt er e = 0xFF (fertig). Sonst zeigt er „PLEASE SET the TIME for the BOOK KEEPING" (`opmode.h:498`) und setzt e = 0x11 bei `8002651C` (`port/src/opmode_payload.cpp:897-907`). Genau dieser Schreiber wurde in `_m266/_takt_opmode_350m.txt` gemessen.
- Handler 17 wartet auf das Eingabebit `[SDA(0xB0)]+0x1C & kInputWait` (`opmode_payload.cpp:890-896`, `:831-833`).
- Der Buchhaltungssatz ist also ungültig. Die Hybrid-Maschine lädt das NVRAM `capture/nvram/sscope/m48t58` (`port/hybrid/maschine.cpp:125-138`). Der Port hat die NVRAM-Schicht dazu (`port/include/port/bookkeeping.h:77`, `port/src/blockstore.cpp:57-70` `block_verify`).
**Stationsregel:** (a) Halt-Art ≠ Schranke, (b) opmode ≠ 0 oder c ≥ 3, (c) Präfix gegen Kaltstart-Referenz. Jeweils durch eine Kern- oder Modelländerung, mit Vorgabe EIN und im gültigen Preflight.
**Bewegung:** neuer Wartepunkt der Hauptschleife mit Maßnahme, Gegenschalter, Rotprobe und eigenem Commit (R265-1).
**Zielmaß:** `Anteil nativ (Schatten)` (B266: 1658327/900000000), wird berichtet. **Ersatzzahlen, kein Fortschritt:** Bildtakt, Loop-Umläufe, e-Wert, Halt-PC.

ARBEITSWEISE:
- Batch-Beginn nach `AGENTS.md`. `git config core.hooksPath` = `scripts/hooks` prüfen. `Get-Process hybrid_lauf,python` EINMAL notieren, nichts stoppen.
- Vorhersage-Commit `B267: Vorhersage` VOR jedem `port/`/`scripts/`-Diff. Inhalt:
  - Sollwert und Zählerdefinition je Bilanzzeile,
  - die Vorhersage je Einzel-Rotprobe,
  - die Vorhersage zum Wert von `0x800B3A60` und zur Ursache.
- **ROM-Adressen zuerst mit `python scripts/port_suche.py <adresse>`.** Die Ausgabe kommt ins Dokument, für jede Funktion und jeden Schreib-PC, bevor etwas als STRONG INFERENCE oder HYPOTHESIS eingestuft wird. Pflicht mindestens für `800261C4`, `800264C0`, `80026498`, `8002651C`, `800B3A60` und jeden Schreiber von `800B3A60`.
- Jedes Selbsturteil (Station, Bewegung, Stopp-Bedingung, FERTIG WENN) steht als Zeile mit drei Teilen: Regelwortlaut, verglichene Zahlen, Ja/Nein.
- „Maßnahme" heißt eine Änderung unter `port/hybrid/` mit Gegenschalter, ROM-Beleg und Port- oder MAME-Beleg. Je Maßnahme ein eigener Commit. **Eine Rotprobe nimmt genau diese eine Maßnahme zurück, die übrigen bleiben EIN.**
- Läufe über 20M Schritte mit `--wanduhr-grenze` ≤ 1500. Läufe, Preflight und `port_build` blockierend mit `timeout=1800000`. Verboten: `Start-Process`, `Wait-Process`, Hintergrund, Warteschleifen.
- Stopp-Bedingungen: (i) Bedingung mit Adresse, Schreiber und Sollwert belegt, und sie hängt an Material außerhalb des Repos (Grep bzw. `port_suche.py`-Fundstellen); (ii) Umschaltschwelle mit `Get-Date`-Zeile. „Schrittgrenze erreicht" ist keine Stopp-Bedingung.
- Nach einem Preflight sind weitere Arbeiten erlaubt (R13bf), danach folgt ein neuer Preflight. **Die Vorwärmung (`scripts/m265_prewarm.py`) läuft blockierend nach dem LETZTEN `port/`-Commit und vor dem Preflight.** Die Sekunden für `Hybrid-Lauf` aus `_m267/_preflight_zeiten.txt` kommen ins Dokument, Soll unter 30 s.
- Belege als `Datei:Zeile@commit`. Rohausgaben über 20 MB heißen `*_roh.txt` und werden komprimiert gesichert.

TEIL 0 - Klein:
0a. Vorhersage-Commit.
0b. Ankerkopf und `analysis/hybrid-plan.md` (eigener Commit):
- R265-1 wortgetreu (oben) in `hybrid-plan.md` unter der Stationsregel eintragen.
- Im Ankerkopf zwei Zähler führen: „Stillstandszähler (Station): 5 B-Batches ohne Station – laut R265-1 ohne Folge bis B275" und „ohne Station und ohne Bewegung: 0 von 2 (B266 Bewegung: Loop B + 3 Maßnahmen)". Dazu „B-Fenster B266–B275: B266 = 1/10, B267 = 2/10".
- Posten (1) unter `**Offene Entscheidung:**` mit **GESCHLOSSEN** führen: „Nutzer R265-1: A erweitert, B bis B275".

TEIL 1 - Einzel-Rotproben und Vorgabe EIN (Übertrag B266 TEIL 2c):
1a. Drei Läufe zu je 300M Schritten, jeweils alle Maßnahmen EIN außer einer. Je Lauf festhalten: Loop-A/B/C-Umläufe, Eintritte `FUN_80026C34`, c/e, Halt-PC. Tafel `_m267/_einzel_rotprobe.txt` mit „Maßnahme nötig ja/nein".
1b. Nur die nötigen Maßnahmen werden Vorgabe EIN (ein Commit). Dafür zwei gleiche A4-Läufe (900M) unter 1500 s, ohne `--takt`/`--besuch-ab`, mit Wanduhr je Lauf, Ausgaben zeichengleich verglichen. Ist der Vorwärmlauf von `m265_prewarm.py` derselbe Aufruf, darf er einer der beiden Läufe sein, wenn der Vergleich belegt ist.
1c. Die Wanduhr eines A4-Laufs mit Maßnahmen (B266: 989 s) gegen den Lauf ohne (230 s) ins Dokument. Nur messen, nicht optimieren.

TEIL 2 - Der Buchhaltungssatz (e = 0x11):
2a. Im Lauf mit Vorgabe EIN messen: den Wert von `0x800B3A60` beim Eintritt in Handler 16, dazu alle Schreibzugriffe auf `0x800B3A60` mit PC und Schritt (vorhandenes Zellenwerkzeug `--zelle` bzw. `TAKT-OPMODE` nutzen). Außerdem das Eingabebit `[SDA(0xB0)]+0x1C` in Handler 17.
2b. Orakel: Den nativen `port::OpMode` (Vorbild `scripts/m265_orakel.cpp`) auf den Zustand bei e = 0x10 setzen und zeigen, dass er e = 0x11 liefert und dann auf das Eingabebit wartet. Ergebnis `_m267/_orakel_e11.txt`.
2c. NVRAM-Weg: Wer setzt `0x800B3A60` aus dem NVRAM? Ghidra-Xrefs auf den Schreiber, dazu `port_suche.py`. Dann die NVRAM-Schicht des Ports (`port/src/blockstore.cpp` `block_verify`, `port/include/port/bookkeeping.h`) auf `capture/nvram/sscope/m48t58` anwenden: Besteht der Buchhaltungsblock die Prüfsumme in beiden Kopien? Ist die Buchhaltungszeit gesetzt? Liest der Hybrid dieselben Bytes (Zugriffe auf `0x7D020000..0x7D021FFF` mit Offset und Wert, inklusive RTC-Register)? Ergebnis `_m267/_nvram_buchhaltung.txt`.

TEIL 3 - Maßnahme und Iteration:
- Ist der Satz im Capture gültig und liest der Hybrid ihn falsch: das NVRAM- oder RTC-Modell berichtigen, mit Gegenschalter, Rotprobe und eigenem Commit, danach Vorgabe EIN wie in 1b.
- Ist der Satz im Capture selbst ungültig: Stopp-Bedingung (i) belegen. Dann `WARTET AUF LIVE-AUFNAHME` im Anker (ein MAME-NVRAM von sscope nach dem Stellen der Buchhaltungszeit im Testmenü). Zusätzlich eine **Erkundungsmaßnahme Vorgabe AUS** mit Gegenschalter: das Eingabebit für Handler 17 einmal als Flanke setzen. Damit zeigen, was dahinter kommt (opmode, c, e, nächster Wartepunkt), eingestuft als HYPOTHESIS-Pfad und nie Vorgabe EIN.
- Weiter nach der Kette: Wartepunkt → `port_suche.py` / Orakel → Maßnahme → Rotprobe → Commit. Ziel: opmode ≠ 0, also `FUN_80025B7C` läuft und die Blockzahl ist > 1. Ende an einer Stopp-Bedingung.

TEIL 4 - Abschluss:
- Vorwärmung blockierend, Preflight, dann `python -u scripts/m149_bilanz.py --batch 267 --from-preflight analysis/_preflight_267.txt --write-anchor` (nie durch eine Pipe).
- `python scripts/rohlauf_aufraeumen.py --komprimieren` und `python scripts/check_dateigroesse.py --getrackt` als Auszug ins Dokument.
- Ankerkopf B267 mit:
  - Preflight-HEAD,
  - Station- und Bewegungszeile im Dreierformat,
  - beiden Zählern und B-Fenster 2/10,
  - Einzel-Rotproben-Tafel,
  - Ergebnis NVRAM,
  - „Nächster Schritt" mit Batch-Nummer 268.
- Memory-Export, `git status` lesen, `ghidra-mcp-notes.md` mitcommitten (Bremse > 50 Zeilen).

BATCH-ENDE:
`python -u scripts/m151_memory_sync.py export`, `git status` lesen, Commit `B267: …`. Abweichungen von der Vorhersage als Tafel „Vorhersage / Ist / Treffer / Erklärung".

FERTIG WENN: (a) `_m267/_einzel_rotprobe.txt` mit „nötig ja/nein" je Maßnahme; (b) die nötigen Maßnahmen Vorgabe EIN nach zwei zeichengleichen A4-Läufen unter 1500 s, im gültigen Preflight; (c) `_m267/_orakel_e11.txt` und `_m267/_nvram_buchhaltung.txt` mit Wert und Schreibern von `0x800B3A60` und dem Prüfsummenergebnis beider Kopien; (d) Maßnahme mit Rotprobe oder belegte Stopp-Bedingung (i) samt Erkundungsmaßnahme; (e) `port_suche.py`-Ausgaben für die Pflichtadressen im Dokument; (f) gültiger Preflight mit `Hybrid-Lauf` < 30 s, Bilanz, Aufräumen, Ankerkopf mit beiden Zählern; (g) kein Ende vor der Umschaltschwelle ohne gültige Stopp-Bedingung.
STREICHREIHENFOLGE: 1. TEIL 1c, 2. die Erkundungsmaßnahme aus TEIL 3, 3. TEIL 3 über die erste Maßnahme hinaus. NIE: Vorhersage-Commit, TEIL 0b, TEIL 1a, 1b, TEIL 2a-2c, Vorwärmung, Preflight, Bilanz, Aufräumen, Memory-Export, Ankerkopf.

## NACHRUECKLISTE
1. TEIL 0b: FERTIG WENN R265-1 wortgetreu in `hybrid-plan.md` steht und der Ankerkopf beide Zähler, B-Fenster 2/10 und Posten (1) GESCHLOSSEN führt, committet.
2. TEIL 1a: FERTIG WENN `_m267/_einzel_rotprobe.txt` (drei Läufe à 300M, Loop-Umläufe, c/e, „nötig ja/nein") committet ist.
3. TEIL 1b: FERTIG WENN ein Commit „Vorgabe EIN" für die nötigen Maßnahmen vorliegt, mit zwei zeichengleichen A4-Läufen unter 1500 s (Wanduhr je Lauf im Dokument).
4. TEIL 2a-2c: FERTIG WENN `_m267/_orakel_e11.txt` und `_m267/_nvram_buchhaltung.txt` committet sind (Wert und Schreiber von `0x800B3A60`, Prüfsumme beider Kopien, Hybrid-Zugriffe auf `0x7D02xxxx`, `port_suche.py`-Ausgaben).
5. TEIL 3: FERTIG WENN eine Maßnahme mit Gegenschalter, Rotprobe und eigenem Commit vorliegt, oder Stopp-Bedingung (i) belegt ist und die Erkundungsmaßnahme (Vorgabe AUS) ihr Ergebnis gemessen hat, oder eine `Get-Date`-Zeile an der Umschaltschwelle steht.
6. TEIL 4: FERTIG WENN Vorwärmung, gültiger Preflight mit `Hybrid-Lauf` < 30 s, Bilanz, Aufräumauszug und Ankerkopf mit Station- und Bewegungszeile im Dreierformat committet sind.
</DS_INSTRUCTION>
