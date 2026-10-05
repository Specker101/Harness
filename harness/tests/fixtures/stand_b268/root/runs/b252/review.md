<TELEGRAM_SUMMARY>
Ergebnis: Der C-Batch hat den Zwilling 80050F30/8005132C gebaut. Beide Rümpfe sind bytegleich, also ein Rumpf mit zwei Registry-Einträgen. Referenzgleiche Insn 4303→4813 (+510), je Kopf `vergl` 0 und `mut` ROT. Zusätzlich: Zählzeile und Ersatzzahl im Preflight (`_preflight_251.txt:21`), Spalte „Art“ (Spiellogik 46557/823, Menü 11872/71, Hardware 6113/88) und `m53_pool.py` auf den Byte-Index umgestellt (Zeilen 42 und 108).
Bewertung: FERTIG WENN erreicht: ja. Mängel:
- Der Preflight lief kalt 2324 s (`_m251/_preflight_zeiten.txt:41`). Der Zwischenspeicher traf nicht (`_preflight_251.txt:33`), weil jeder neue Kopf `hybrid_lauf.exe` ändert (`Makefile:179`, Schlüssel `m212_zeilen.py:317`). Damit ist M250-3 belegt: Die Entlastung greift im C-Batch nicht.
- Der Preflight lief zweimal über 1800 s, wurde in den Hintergrund geschoben und per Polling abgewartet (R13aj verletzt). Das kostete 60 min, 44 % des Batches.
- Die 510 Insn sind ein Zwillingseffekt und kein Maß für die Reihe: Die eigene Arbeit entspricht 255 Insn.
Kosten/Laufzeit: $0,26, 2 h 17 min, 173 Anfragen.
Nächster Batch: C. Zuerst die Preflight-Dauer unter 1800 s bringen, dann Insn ≥150 (Ziel ~200) mit Zwillingssuche. Die Kopfzahl 4 ist nur Nebenzahl; das Insn-Ziel hat Vorrang vor der Median-Regel.
B-SCHRITT: kein B-Batch (Strang C)
Insn je C-Batch: B244 15, B246 18, B247 14, B251 510 (davon Zwillingszweitkopie 255).
M250-2: übernommen – Wirkung belegt: Batch-Dokument Zeilen 18-35, Fundstellen per Grep. Die Messung des zweiten `c3a8`-Rufs bleibt als Voraussetzung für B im Anker.
M250-3: übernommen – Wirkung noch nicht belegt → offen (der Zwischenspeicher greift im C-Batch nicht, Lösung in B252 TEIL 0)
M250-4: übernommen – Wirkung belegt: `m53_pool.py:42,108`, Grenztest 0 %
M249-4: übernommen – Wirkung belegt: `_preflight_251.txt:21`
M249-5: übernommen – Wirkung belegt: `_preflight_251.txt:21`, 4173/50636
UEBERTRAG: Gegenprobe der Mitleser m54/m58 (Vorhersage „Delta 0“, nicht gemessen) -> B252 NACHRUECKLISTE 4
ENTSCHIEDEN: In B252 hat die Preflight-Dauer Vorrang (Werkzeugbau, zusammen mit dem Kopfbau, nur Zwischenspeicher-Schlüssel ohne Einfluss auf `vergl`/`mut`).
OFFENE FRAGE: Es gibt 64542 offene Spannen-Insn. Bei 150–200 je Batch sind das über 300 Batches; nur Zwillinge und große Blätter beschleunigen das.
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: ghidra-read
program: /830d01.27p.main.bin
</DS_TOOLS>

## VERALLGEMEINERUNG

**Befund 1: Preflight kalt 2324 s, Zwischenspeicher trifft in C-Batches nie.**
- (a) Fehlerklasse: Der Schlüssel des Zwischenspeichers enthält mehr Eingaben als der Lauf braucht (SHA des ganzen Binärs, obwohl nur `ckopf_leaves.cpp` wechselt). Der Beleg „0,3 s nachher“ in B250 maß den Treffer, nicht die Wirkung im nächsten Batch-Typ.
- (b) Die Instruktion verlangt die Liste aller Eingaben des A4-Laufs und je Eingabe die Antwort „ändert sich in C-Batches?“. Außerdem muss der Preflight der Messgröße „Gesamtdauer unter 1800 s“ genügen, nicht nur der Trefferzeile.
- (c) Ob ein neuer Kopf den A4-Lauf verändert, wird nur über die Besuchskarte des Laufs bewiesen. Ohne Besuchskarte bleibt der Schlüssel unverändert.

**Befund 2: `MEM_KOMBI_DEF` steht nicht im `_kopf_hash`** (Fallstrick des Workers).
- (a) Fehlerklasse: derselbe wie Befund 1, nur unvollständig statt zu breit (ein Hash deckt nicht alle Eingaben ab).
- (b) Die Instruktion verlangt die Eingabeliste von `_kopf_hash` und eine Rotprobe: Wert ändern, Hash muss sich ändern.
- (c) Nur `c_kopf.py`. Die übrigen Hashes im Repo werden nicht durchgesehen.

**Befund 3: Hintergrundlauf und Polling trotz R13aj.**
- (a) Fehlerklasse: Der Worker schiebt einen Lauf über 1800 s in den Hintergrund, weil der Aufruf nicht fertig wird.
- (b) Die Instruktion verbietet Hintergrund und Warten ausdrücklich. Vor dem Preflight wird die erwartete Dauer aus `_preflight_zeiten.txt` gerechnet.
- (c) Ob der Harness einen Aufruf über 1800 s abbrechen würde, wird nicht geprüft.

**Befund 4: Insn-Reihe verzerrt durch Zwilling.**
- (a) Fehlerklasse: Die Messgröße zählt den Aufwand nicht. Eine Zweitkopie hat dieselben Insn wie der Rumpf, kostet aber fast nichts.
- (b) Die Tafel weist „Insn davon Zwillingszweitkopie“ gesondert aus. Daneben läuft die MAME-Coverage-Ersatzzahl (4173 gegen 4813), ausdrücklich als Ersatzzahl gekennzeichnet.
- (c) Ob Zwillinge ohne Aufruf (`bl`) in nennenswerter Zahl existieren, misst B252 TEIL 1.

**Befund 5 (Stichprobe der Art-Regel):** Hardware-Boot-Init war bei 4 von 5 Einträgen eindeutig. Einmalige Unschärfe, im Zweifel gilt Spiellogik; in TEIL 1 wird sie nur dokumentiert.

<DS_INSTRUCTION>
Batch 252 - Silent Scope Decomp

Strang C (C-Batch, ausgeführte Menge). Kein B-Batch: B ruht bis zum Ende der ausgeführten Menge (Nutzerentscheid 02.10.).
SOLL-INSN: mindestens 150 neue referenzgleiche Insn, Ziel ~200 (Nutzerentscheid 02.10., hat Vorrang vor der Median-Regel)
SOLL-KOEPFE: 4 (nur Nebenzahl)
Ersatzzahl (so kennzeichnen): MAME-Coverage `referenzgleich/ausgeführt` (Preflight-Zeile „Ausgefuehrte Menge“). Sie ist nicht das Soll.

STAND UEBERNEHMEN:
- HEAD 42d4c5b, Baum sauber, `_preflight_251.txt` gültig. C Köpfe 141/7856/0. Referenzgleiche Insn 4813, offene Spannen-Insn 64542, MAME-Coverage 4173/50636.
- Art-Summen offen (Insn/Köpfe): Spiellogik 46557/823, Menü-Service 11872/71, Hardware-Boot-Init 6113/88 (`_m251/_ausgefuehrt_kandidaten.txt`).
- Nutzerregeln (bindend):
  - Reihenfolge Spiellogik und Menü/Service zuerst, Boot-Init ans Ende (nicht streichen).
  - Köpfe unter 10 Insn nur als Beifang.
  - Im Bericht die Insn nach Art aufschlüsseln.
- Messung aus B251: Der Preflight war kalt 2324 s (`_m251/_preflight_zeiten.txt:41`). Davon Hybrid-Lauf 1762,7 s (:33), C Köpfe 473 s (:24). Der A4-Zwischenspeicher traf nicht (`_preflight_251.txt:33`), weil `hybrid_lauf.exe` `ckopf_leaves.cpp` einbindet (`Makefile:179@42d4c5b`) und der Schlüssel den SHA des Binärs enthält (`scripts/m212_zeilen.py:317@42d4c5b`). Jeder neue Kopf macht den Preflight also kalt, über die 30-min-Grenze. B251 lief deshalb zweimal in den Hintergrund (R13aj-Verstoß).

ARBEITSWEISE:
- Startroutine nach `AGENTS.md`.
- Vorhersage-Commit `B252: Vorhersage` VOR jeder Änderung unter `port/` und `scripts/`. Er nennt je Bilanzzeile Sollwert und Zählerdefinition: referenzgleiche Insn vorher/nachher, Ersatzzahl, Insn je Art, davon Zwillingszweitkopien, `C Koepfe`, und zusätzlich die erwartete Preflight-Gesamtdauer (Sekunden, aus `_preflight_zeiten.txt` gerechnet).
- Je Kopf `vergl` 0 + `mut` ROT in `_m252/`. Bei einem Zwilling gilt das je Registry-Eintrag.
- `c_kopf.py`, `port_build` und Preflight als EIN blockierender Aufruf mit `timeout=1800000`. Kein Hintergrund, kein Polling (`Get-CimInstance`, Schleifen). Überschreitet ein Aufruf 1800 s, ist das ein Befund: im Dokument melden, nicht umgehen.
- „Fehlt“ nur mit Grep auf den Bezeichner in `analysis/` und `port/`, mit Fundstelle `Datei:Zeile@commit`.
- Eigene Entscheidungen als `ENTSCHEIDUNG (Worker): …`.
- Werkzeugbau (TEIL 0) und Kopfbau stehen hier ausnahmsweise im selben Batch (Reviewer-Entscheid): TEIL 0 ändert nur Zwischenspeicher-Schlüssel und Profil-Hash, nicht `vergl`/`mut`.

TEIL 0 - Preflight unter 1800 s:
- 0a Messung, ohne neuen Lauf. Lies `scripts/m212_zeilen.py:246-370` und `_m251/_preflight_zeiten.txt`. Nenne je Hybrid-Lauf (A4 900M mit `--stopp-bei-halt`, FRONT 200M, 20M) Dauer, ob gespeichert und welche Eingaben den Schlüssel bilden. Tafel in `_m252/_preflight_dauer.txt`.
- 0b A4-Schlüssel. Eine Änderung nur unter `ckopf_leaves.cpp` darf den A4-Treffer nicht verwerfen, WENN belegt ist, dass die Köpfe den A4-Lauf nicht berühren.
  - Beleg: Der Lauf weist eine Besuchskarte oder Rufliste aus (Grep `Boot-Coverage`, `--cov`, `Registry-Kopf` in `port/hybrid/hybrid_lauf.cpp`). Die Eintritts-PCs ALLER seit dem zwischengespeicherten Lauf neuen Registry-Köpfe haben vor dem Halt 0 Rufe.
  - Schlüssel dann: SHA der Quellen unter `port/hybrid/`, `port/src/ram.cpp` und des Kerns (ohne `ckopf_leaves.cpp`) + argv + Kalibrierdatei + Kopfliste (PC + Rumpf-Hash) der im Lauf gerufenen Köpfe.
  - Der Lauf aus B251 (`port/build/hybrid_cache/`, Binär HEAD 4a6ffa4) wird unter dem neuen Schlüssel eingetragen; die Herkunft steht als Zeile im Dokument.
  - Rotprobe: Eine Änderung unter `port/hybrid/` verwirft den Treffer. Ein neuer Kopf mit Rufen vor dem Halt verwirft ihn ebenfalls.
  - Ist der Beleg nicht möglich (keine Besuchskarte, nur Rohdaten), dokumentiere „nicht belegbar“, ändere den Schlüssel NICHT und gehe zu 0c.
- 0c Nur wenn 0b nicht gilt: den A4-Lauf einzeln vorwärmen (Aufruf von `_lauf_a4()` aus `m212_zeilen` per python, blockierend, `timeout=1800000`), erst nach der letzten Änderung unter `port/` und `scripts/`. Danach nichts mehr dort ändern. Der Preflight liest dann den Treffer. Dauert der Einzelaufruf ≥1800 s, dokumentiere das und lasse den Preflight mit dem Treffer-Versuch laufen; der Reviewer entscheidet in B253 neu (Zustandsabzug vor `be40`).
- 0d `_kopf_hash` in `scripts/c_kopf.py`: Liste seiner Eingaben, `MEM_KOMBI_DEF` und `_ZWILLING_KOMBI` aufnehmen. Rotprobe: Wert ändern, Hash ändert sich. Danach die `_ck_*.case` neu erzeugen, soweit betroffen, und `vergl alle` fahren.

TEIL 1 - Zwillingssuche und Auswahl:
- 1a Offline-Skript `scripts/m252_zwillinge.py`. Je offener Kandidat (Art Spiellogik und Menü-Service) der SHA der Rumpfwörter. Gruppen ≥2.
  - Nur Gruppen OHNE Sprung oder Aufruf aus dem Rumpf hinaus (`bl`, `b`/`bc` auf Ziele außerhalb) gelten als echte Zwillinge: Ein relativer `bl` in gleichen Bytes ruft sonst ein anderes Ziel.
  - Tafel: Gruppe | Köpfe | Insn je Rumpf | Aufrufe nach außen (0/n) | Art.
- 1b Auswahl: zuerst echte Zwillingsgruppen mit den meisten Insn, danach die größten eigenständigen Blätter der Arten Spiellogik und Menü-Service (Tafel `_m251/_ausgefuehrt_kandidaten.txt`). Hardware-Boot-Init nur, wenn das Insn-Soll sonst nicht erreichbar ist (Begründung).
- 1c Die Art jedes gewählten Kopfes wird nach der Regel (Aufrufer-Kette, MMIO-/Proxy-Konstanten, Textbezug; im Zweifel Spiellogik) im Dokument belegt, mit Fundstelle. Eine Unschärfe wie die eine unklare Stichprobe in B251 wird benannt.

TEIL 2 - Köpfe:
- Bauen nach `c_kopf.py`/`ckopf_leaves.cpp` wie in B251. Je Kopf `vergl` 0 + `mut` ROT.
- Tafel: Kopf | Art | Insn | davon Zwillingszweitkopie | `vergl` | `mut`. Summen gesamt, je Art und Zweitkopien getrennt. „Eigene Insn“ = gesamt − Zweitkopien.
- Danach `vergl alle` (alle Köpfe weiter gleich).

TEIL 3 - Abschluss:
- Den Preflight erst fahren, wenn TEIL 2 fertig und `port/` und `scripts/` unverändert sind. Genau ein gültiger Lauf (`_preflight_251`-Muster: `_preflight_252.txt`, blockierend). Danach Bilanz, Memory-Export, Commit, Baum leer.
- Preflight-Dauer (Soll <1800 s) und tatsächliche Dauer in die Bilanz: Zeile „Preflight Dauer <s>“ im Dokument gegen die Vorhersage.
- Ankerkopf: Stand B252 (C), Reihe „Insn je C-Batch: B244 15, B246 18, B247 14, B251 510 (davon 255 Zweitkopie), B252 <n> (davon Zweitkopie <z>)“, Insn je Art, Preflight-Dauer, `GESCHLOSSEN` bei erledigten Posten. Ersatzzahl als Ersatzzahl kennzeichnen.

FERTIG WENN: mindestens 150 neue referenzgleiche Insn (Preflight-Zeile zeigt das Delta; Tafel mit Zweitkopien getrennt) mit `vergl` 0 + `mut` ROT je Kopf + Insn je Art + Zwillingstafel `_m252_zwillinge` + `_kopf_hash`-Rotprobe + Preflight-Dauer unter 1800 s mit Beleg (`_preflight_zeiten.txt`: Gesamtwanduhr) bzw. dokumentierter Befund aus 0c + genau ein gültiger Preflight ohne Hintergrund und Polling + Bilanz + leerer Baum.

STREICHREIHENFOLGE:
- Gestrichen wird erst, wenn die Batch-Uhr die Umschaltschwelle erreicht hat, mit einer `Get-Date`-Zeile im Dokument.
- Reihenfolge:
  1. TEIL 0 Schlüssel (0b); ersatzweise 0c, die Vorwärmung (dann Übertrag in B253)
  2. Gegenprobe m54/m58 (Nachrückliste 4)
  3. `_kopf_hash` 0d
  4. Köpfe über 200 Insn hinaus
- NIE: Vorhersage, 150 Insn, Preflight (ein gültiger Lauf), Bilanz, Memory-Export, Ankerkopf, `vergl`/`mut` je Kopf.

## NACHRUECKLISTE
1. Köpfe. FERTIG WENN: neue referenzgleiche Insn ≥150 (Zweitkopien getrennt ausgewiesen), je Kopf `vergl` 0 + `mut` ROT, Tafel mit Insn je Art, `_m252/_zwillinge`-Tafel liegt vor.
2. Abschluss. FERTIG WENN: gültiger `_preflight_252.txt` (ein Lauf, blockierend, ohne Hintergrund) + `_m252/_bilanz.txt` + Ankerkopf mit Insn-Reihe und Preflight-Dauer + leerer Baum.
3. Preflight-Dauer. FERTIG WENN: `_m252/_preflight_dauer.txt` (0a) liegt vor und die Gesamtwanduhr des gültigen Preflights steht gegen 1800 s im Dokument; bei Überschreitung steht der Befund samt Ursache da.
4. A4-Schlüssel 0b oder 0c. FERTIG WENN: 0b mit Besuchskarten-Beleg und Rotprobe umgesetzt oder „nicht belegbar“ dokumentiert und 0c gefahren.
5. `_kopf_hash`. FERTIG WENN: Eingabeliste im Dokument, `MEM_KOMBI_DEF` im Hash, Rotprobe (Hash ändert sich).
6. Mitleser m54/m58. FERTIG WENN: gemessenes Delta vorher/nachher der Byte-Index-Korrektur in `_m252/` (Vorhersage aus B251: 0), bei Abweichung erklärt.
</DS_INSTRUCTION>
