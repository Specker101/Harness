# Belege R13bp (2026-10-03) — vier Punkte Harness-Wartung

Auftrag (Nutzer): vier Punkte, **je Punkt ein Commit**, betroffene Tests, am Gate die volle
Reihe, danach Neustart im eigenen PowerShell-Fenster. Das Decomp-Repo wird **nicht**
angefasst (nur lesend gelesen, wo ein Beleg es verlangt).

Commits (in dieser Reihenfolge):

| Punkt | Commit | Inhalt |
|---|---|---|
| 1 | `f593940` | Strangerkennung liest den Auftrag des Batches selbst |
| 2 | `5d38d7e` | Fortsetzungssatz sagt, dass weitere Arbeit erlaubt ist |
| 3 | `8ae8a15` | `Wait-Process` zählt als Wartezeit (ohne Notbremse) |
| 4 | `66e7e94` | A4-Zwischenspeicher-Treffer fallen aus der Stillstandsreihe |

Belege tragen `Datei:Zeile@commit` (Projektregel). „gemessen" heißt: am 2026-10-03 im
laufenden Bestand nachgezählt, nicht aus dem Gedächtnis.

---

## 1. Strangerkennung — Primärquelle ist der Auftrag des Batches (CONFIRMED)

**Befund (gemessen).** Die Klassifikation las als zweite Quelle die Pflichtzeile
`B-SCHRITT:` des Reviews, das den Batch **bewertet** hat. Dieses Review liegt nach der
Ordner-Konvention (R13x) in `runs/b<N+1>/`, trägt in der Zusammenfassung aber dennoch die
Zahl des **nächsten** Batches:

* `runs/b255/review.md` (bewertet **B254**, ein C-Batch) enthält
  `B-SCHRITT: 4/5 Boot bis Hauptschleife, B-Batch 26` → B254 galt als **B-Batch**.
* `runs/b254/auftrag.md` sagt dagegen in der ersten Zeile der Instruktion
  `Strang C (Handport). Messziel: Insn.` — der Batch war nie ein B-Batch.
* B255 (echter B-Batch) bekam „B" nur zufällig richtig, weil auch seine Review-Zeile
  (in `runs/b256/review.md`) „B-SCHRITT: 4/5 …" trägt.
* `runs/b256/auftrag.md` trägt die neue Pflichtzeile `STRANG: B` (Zeile 1 der Instruktion).

**Neu** (`hx/stand.py:2306@f593940` `STRANG_QUELLEN`, `hx/stand.py:2518@f593940`
`strang_von_batch`): Reihenfolge der Quellen

0. Pflichtzeile `STRANG: B|C` bzw. `SOLL-KOEPFE: <n> (Strang B, …)` im Auftrag des
   Batches selbst (`runs/b<N>/auftrag.md`; am Gate die `<DS_INSTRUCTION>` des Reviews),
1. der übrige Auftragstext des Batches (`_auftrag_strang`: „Strang C (Handport)…",
   „B208 ist der ERSTE Batch von Strang B"),
2. **Rückfall**: die `B-SCHRITT:`-Zeile des Reviews, das den Batch bewertet hat,
3. `analysis/hybrid-plan.md` (Paarliste).

Damit wird die Pflichtzeile erstmals auch **verlangt**: `prompts/reviewer.md:448@f593940`
schreibt `STRANG: B` bzw. `STRANG: C` als erste Zeile jeder Instruktion vor (vorher stand
die Zeile in keinem Prompt — sie kam nur zufällig in einzelnen Aufträgen vor).

**Messung (aus `docs/_r13bp_probe.py`, Gegenprobe der Reihe):**

| Batch | vorher | nachher | Quelle nachher |
|---|---|---|---|
| B249, B250 | B | **B** | Auftrag `runs/b249|b250/auftrag.md` |
| B251, B252, B253 | C | **C** | Auftrag `runs/b25{1,2,3}/auftrag.md` |
| **B254** | **B** (falsch) | **C** | Auftrag `runs/b254/auftrag.md` |
| B255 | B | **B** | Auftrag `runs/b255/auftrag.md` |
| B256 | B | **B** | Pflichtzeile `STRANG: B` im Auftrag |

**Tests.** `tests/test_r13bp_fixes.py` (neu, 17 Tests) mit der neuen Fixture
`tests/fixtures/stand_b255` (Kopien der echten Dateien, byteweise; README mit Bauanleitung).
Klassen: `TestEchterStandB255` (B254 = C, B255 = B, die Reihe, die irreführende Zeile, der
Reviewer-Prompt) und `TestReihenfolge` (Attrappen: Auftrag schlägt `B-SCHRITT`, Pflichtzeile
bleibt Quelle 0, Rückfall greift, Plan bleibt letzte Quelle, fremde Erwähnungen zählen
nicht). Mitgelaufen: `test_r13aa`, `test_r13ac`, `test_r13ah`, `test_r13an`, `test_r13w`,
`test_r13bo`, `test_r13bo5`, `test_r13z`, `test_r13s`, `test_r13bn` — alle grün.

---

## 2. Fortsetzungssatz — weitere Arbeit ist erlaubt (CONFIRMED)

Der Gilt-Satz lautete nur „Kein neuer Preflight nötig, der vorhandene gilt - seit dem
letzten Preflight wurde unter port/ oder scripts/ nichts geändert." Er ließ damit offen, ob
unter `port/`/`scripts/` überhaupt noch gearbeitet werden darf — gelesen werden konnte er
als Verbot weiterer Arbeit.

**Neu** (`hx/worker.py:536@5d38d7e`): angehängt
„ Weitere Arbeit unter port/ und scripts/ ist erlaubt; danach ein neuer Preflight, der
letzte gilt (R13bf)." Der Erledigt-Satz steht weiterhin **zuletzt** und übersteuert beide
Preflight-Sätze.

**Tests.** `tests/test_r13bf_fixes.py`: `test_gilt_satz_erlaubt_weitere_arbeit_und_verlangt_
danach_einen_preflight` (Wortlaut + Erledigt-Satz zuletzt),
`test_die_neuen_saetze_schliessen_sich_aus`. Doku nachgezogen:
`docs/bedienung.md` (Tabelle der Fortsetzungsregel).

---

## 3. `Wait-Process` zählt als Wartezeit (CONFIRMED, gemessen)

**Befund (gemessen).** B255 wartete zweimal je 600 s auf den Hybrid-Lauf:

* `runs/b255/stream.jsonl:98809` — `$p=Get-Process hybrid_lauf …; Wait-Process -Id $pid2
  -Timeout 600 …`, Werkzeugdauer **602,5 s**
* `runs/b255/stream.jsonl:101715` — dieselbe Form, Werkzeugdauer **602,3 s**
  (beide Dauern aus `runs/b255/result.json`, `stats.laufzeit.langsamste`)

Gemeldet hat `runs/b255/result.json` dagegen `stats.laufzeit.warteschleifen = 0`,
`warte_s = 0,5`, `warteschleifen_s = 0`. Ursache: `streamjson.warte_muster` gab für
`Wait-Process` `None` zurück (R13v führte ihn als „benannten erlaubten Weg") — damit
zählte ihn weder die Liste noch die Schätzung.

**Neu** (`hx/streamjson.py:295@8ae8a15` `WARTE_WAITPROC_GRUND`, `:325` `warte_erlaubt`,
`:335` `warte_verstoesse`, `:340` `warte_muster`, `:396` `warte_sekunden`):

* `warte_muster` erkennt `Wait-Process` und nennt den Grund; `Start-Process -Wait` bleibt
  erlaubt **und** ungezählt (dort gibt es keine Zahl zum Schätzen).
* die **verbotenen** Muster werden zuerst geprüft — vorher machte ein `Wait-Process` im
  selben Befehl auch eine Abfrageschleife still erlaubt;
* `warte_sekunden` schätzt `Wait-Process … -Timeout N` mit der Obergrenze `N`;
* die Notbremse (`hx/worker.py:930@8ae8a15`) sieht nur die **verbotenen** Muster
  (`warte_verstoesse`); ein erlaubtes Warten wird protokolliert, nicht abgebrochen.

**Messung** (`docs/_r13bp_wait_b255.py` → `docs/_r13bp_wait_b255.txt`, liest nur):

```
stream.jsonl      :98809   PowerShell Warten auf einen Prozess (Wait-Process)    600.0 s  erlaubt
stream.jsonl      :101715  PowerShell Warten auf einen Prozess (Wait-Process)    600.0 s  erlaubt
Summe: 2 Aufrufe / 1200.0 s Wartezeit   (davon erlaubt: 2 / 1200.0 s, verboten: 0 / 0.0 s)
```

Also **1200 s statt 0,5 s** gemeldete Wartezeit — und **0 Verstöße**, der Lauf wäre auch
mit der neuen Regel nicht abgebrochen worden (gewollt: gezählt, nicht verboten).

**Tests.** `tests/test_r13v_fixes.py`: die beiden Fälle `test_wait_process_wird_gezaehlt_
ist_aber_erlaubt` (mit dem **wörtlichen** Aufruf aus `runs/b255/stream.jsonl:98809`,
Gleichheit gegen den Mitschnitt geprüft), `test_wait_process_macht_eine_abfrageschleife_
nicht_erlaubt`, `test_die_echte_b255_wartezeit_steht_in_der_bilanz` (1200,0 s in der
Wartebilanz), `test_nur_erlaubte_befehle_ergeben_keinen_abbruch`; zwei alte Erwartungen
angepasst (`test_erlaubter_weg_ist_erlaubt`, `test_mitschnitt_zaehlt_die_warteschleifen`).

---

## 4. A4-Zwischenspeicher in der Stillstandsreihe (CONFIRMED + Teil „nur prüfen")

**Befund (gemessen).** Die `Hybrid-A4`-Zeile der Preflights B249–B255 trägt fünfmal
denselben Wert (`696571792` / `Halt-PC 8001684C`). Er ist aber **nur zweimal gemessen**:

| Batch | `Hybrid-A4` | Zeile `Zwischenspeicher` | eigene Messung? |
|---|---|---|---|
| B249 | 696571792 / 8001684C | *fehlt* (Zeile gibt es erst ab B250) | ja (Wert entstand neu) |
| B250 | 696571792 / 8001684C | `Zwischenspeicher Treffer` | **nein** |
| B251 | 696571792 / 8001684C | `Zwischenspeicher neu` | **ja** |
| B252–B255 | 696571792 / 8001684C | `Zwischenspeicher Treffer` | **nein** |

Ohne die Ausnahme hätte der Melder aus **drei** (B249/B250/B255) von fünf Wiederholungen
einen Stillstand abgeleitet. Die Herkunftszeile schreibt der Preflight selbst
(`g:\Silent Scope Decomp\scripts\m212_zeilen.py:934-937`, „B250 TEIL 1").

**Neu** (`hx/stand.py:1679@66e7e94` `_RE_ZWISCHEN_ZEILE`, `:1682` `cache_herkunft`,
`:1713` `hybrid_a4_verlauf` mit den Feldern `cache`/`cache_text`;
`hx/aussensicht.py:679@66e7e94` `hybrid_stillstand`, Filter in `:710`):

* `cache` = `True` (Treffer), `False` (eigener Lauf), `None` (Zeile fehlt — jeder Lauf vor
  B250). Bei `None` wird **nichts** behauptet, der Eintrag bleibt in der Reihe.
* `hybrid_stillstand` vergleicht nur Einträge, deren Wert im **eigenen** Lauf entstand, und
  nennt die ausgelassenen Batches im Meldetext
  („ausgelassen (Zwischenspeicher-Treffer, keine eigene Messung): B250, B255").
* Die Marke (`hybrid_neuester_b`) nimmt **alle** Einträge: aus der gefilterten Reihe
  gebildet stünde sie auf einem älteren Batch, und derselbe Stand würde bei jeder Prüfung
  erneut gemeldet (Dauerfeuer).

**Teil „nur prüfen": trägt die Cachedatei einen Herkunftsvermerk? — NEIN (gemessen).**
Gelesen wurde `g:\Silent Scope Decomp\port\build\hybrid_cache\` (nur lesend):

* 6 Dateien, je 226.277.669 B bzw. 226.334.705 B (215,8 MiB), angelegt am 03.10.2026
  zwischen 03:12:57 und 16:43:01.
* Der **Name** ist der Zwischenspeicher-Schlüssel (`sha256`-Hex, 64 Zeichen) — er nennt
  **keinen** Batch: er ist ein Abdruck der Hybrid-Quellen ohne `ckopf_leaves.cpp`, der
  Körper der betretenen Köpfe, der `g++`-Fassung, von `argv` und der Kalibrierdatei
  (`m212_zeilen.py:420` `_cache_key`).
* Der **Inhalt** ist die reine Rohausgabe des Laufs (erste Zeilen: „# Hybrid-Laeufer,
  LAUFMODUS …", „# ROM-Abbild : …", „# Schrittgrenze: …"), also **kein** Vermerk über
  Erzeuger, Batch oder Zeitpunkt.
* Erkennbar ist die Herkunft **je Batch** allein über die Zeile `Zwischenspeicher` in der
  Preflight-Datei des **verbrauchenden** Batches — genau die Quelle, die Punkt 4 auswertet.
  Zweite Spur (nicht benutzt): die Dateizeit der Cachedatei (`LastWriteTime`), die zeigt,
  **wann** ein Eintrag entstand — für eine Zuordnung „welcher Batch hat ihn benutzt" ist sie
  untauglich, weil mehrere Batches denselben Schlüssel treffen.
  **Vorschlag, falls mehr gebraucht wird** (klein, Decomp-Repo): `_cache_schreiben` legt
  neben der Rohausgabe eine Zeile `# erzeugt: Batch <N>, <Zeit>` in die Cachedatei — dann
  ist die Herkunft auch ohne Preflight-Zeile lesbar. **Nicht umgesetzt**, weil das
  Decomp-Repo in diesem Auftrag nicht angefasst wird.

**Tests.** `tests/test_r13bp_fixes.py::TestA4Reihe` (6 Fälle) gegen die Fixture
`stand_b255`: Herkunft wird gelesen (B250/B252–B255 Treffer, B251 eigen, B249 ohne Zeile),
Treffer fallen heraus (**kein** Fehlalarm mehr), Gegenprobe „Werte als eigener Lauf" meldet
wieder (mit B249/B250/B255 im Text), ausgelassene Batches werden genannt, die Marke bleibt
der neueste B-Batch. Mitgelaufen: `test_r13ah`, `test_r13w`, `test_r13bo5`, `test_r13aq`,
`test_r13bn`, `test_r13az` — alle grün.

---

## Werkzeuge und Fixtures

* `tests/fixtures/stand_b255/` — eingefrorener Stand (16 Dateien, 190 KB): Preflights
  B249–B255 (byteweise, UTF-8-BOM), Aufträge B249–B255, Reviews `b255` (bewertet B254,
  irreführende `B-SCHRITT`-Zeile) und `b256` (bewertet B255). README mit Bauanleitung und
  den gemessenen Erwartungen.
  **Byte-Treue geprüft:** alle 16 Dateien MD5-gleich zur lebenden Quelle, Blob-Länge gleich
  der Arbeitsbaum-Länge (`.gitattributes`: `harness/tests/fixtures/** -text`). Achtung
  Falle: ein Vergleich über `git hash-object <lebende Datei>` täuscht, weil dort `text=auto`
  greift und CRLF→LF normalisiert — die 7 Preflight-Kopien erschienen damit fälschlich
  abweichend.
* `docs/_r13bp_probe.py` — liest **nur** und zeigt je Batch die Klasse samt Quelle sowie
  die Zeilen, die jede Quelle tragen würde (Gegenprobe zur Tabelle in Punkt 1).
* `docs/_r13bp_wait_b255.py` + `docs/_r13bp_wait_b255.txt` — fährt den echten Mitschnitt
  von B255 durch den Leser; Beleg zu Punkt 3.

## Volle Reihe am Gate

`docs/_r13av_volle_reihe.txt` (gefahren im Gate-Fenster, Zustand `GATE_APPROVAL batch=256`,
kein Worker):

```
HEAD: 976ee00 R13bp-5: Belege der vier Punkte
Harness-Zustand: state=GATE_APPROVAL batch=256 worker=False
Dauer: 492.1 s
Tests: 1479 | Fehler: 0 | Fehlschläge: 0 | übersprungen: 0
ERGEBNIS: OK
```

Vor dieser Runde waren es 1457 Tests (R13bo-5); die 22 neuen sind die Fälle aus
`test_r13bp_fixes.py` (17) und den erweiterten `test_r13v_fixes.py` (+2) bzw.
`test_r13bf_fixes.py` (+2), dazu die angepassten Erwartungen.

