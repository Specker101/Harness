# R13bd — Tests, die lebende Dateien lesen und leer durchlaufen können (30.09.2026)

**Auftrag (Nutzer).** „Prüfe alle Tests unter `harness/tests/`, die echte Dateien aus
`harness/state` oder `hybrid_verlauf`/andere rollende Fenster lesen, statt Fixtures zu nutzen.
Suche insbesondere nach Tests, die bei leerem oder verschobenem Fenster ohne Assertion
durchlaufen (Schleifen über leere Listen, `if`-Zweige ohne `else`-Assertion). Liste die
Fundstellen als Beleg auf. Stelle nur um, was tatsächlich leer prüfen kann, nach dem Muster von
`test_alle_drei_felder_im_festen_stand` (Fixture plus Zusicherung „Daten liegen im Fenster“).
Zusätzlich: Gib im Beleg der vollen Reihe künftig automatisch Anzahl und Namen aller Skips aus.
Keine Änderung am Gate-Zustand, am Ende volle Reihe am Gate. … Sind es mehr als 5 Fundstellen,
alle als Beleg auflisten, aber nur die 5 wichtigsten umstellen und den Rest als offene Liste.“

## 0. Die zwei Teilfragen, direkt beantwortet (gemessen)

**`harness/state`: kein einziger Test liest das lebende `state/`-Verzeichnis.** Der Audit hat
153 Tests gefunden, die überhaupt lebende Pfade anfassen; darunter ist **null** Zugriff auf
`G:/Harness/harness/state/…` (Abfrage über `docs/_r13bd_audit.json`: Kategorie `state` kommt
nicht vor). Die lebenden Quellen sind ausschließlich das **Decomp-Repo** (`analysis/…`),
das **eigene `runs/`**, `prompts/` und `docs/bedienung.md`.

**Rollende Fenster** (die letzten N Batches statt fester Nummern) werden an genau drei Stellen
auf **lebenden** Daten benutzt:

| Stelle | Fenster | Beleg |
|---|---|---|
| `test_r13ah_fixes::TestHybridStillstand.test_echte_dateien_loesen_keinen_falschen_alarm_aus` | `aussensicht.hybrid_stillstand(load_config())` → letzte N B-Batches | `_r13bd_audit.txt`, Modus A in `_r13bd_leerlauf_vorher.txt` |
| `test_r13ac_fixes::TestTrendMitEchtenDateien` (Klasse) | kopiert `_preflight_198..210` **einmal** in einen Wegwerfordner und prüft dort | Zeilen 236–245 der Datei |
| `test_r13ae_fixes::TestEchteDateien` (Klasse) | kopiert `_preflight_211..213` ebenso | Zeilen 318–330 der Datei |

Die beiden Kopie-Klassen sind schon die halbe Miete (kein Fenster über `das Neueste`), aber
ihre Kopierlisten bzw. die verglichenen Zeilenlisten waren nicht selbst abgesichert — siehe §3.

## 1. Werkzeuge (alle im Repo, alle nachfahrbar)

| Datei | Was |
|---|---|
| `docs/_r13bd_audit.py` → `_r13bd_audit.txt` / `.json` | **Stufe 1 (Laufzeit):** huellt die Datei-Zugriffe (`read_text`/`open`/`glob`/`is_file`/…) und die Leser von `hx` und protokolliert je Test, welche **lebenden** Pfade er anfasst (Wegwerfordner und Fixture ausgenommen). **Stufe 2 (AST):** je Test die drei Leerlauf-Bauformen A (Zusicherung nur im `if`-Zweig), B (Schleife ohne Zusicherung im Rumpf), C (Zusicherung gilt auch für die leere Menge). |
| `docs/_r13bd_verdacht.py` → `_r13bd_verdacht.txt` | die Verdachtsfälle lesbar aufbereitet (Test, lebende Pfade, Bauform) |
| `docs/_r13bd_leerlauf.py` → `_r13bd_leerlauf.txt` (nachher) / `_r13bd_leerlauf_vorher.txt` (vorher) | **die entscheidende Messung:** jeder Verdachtsfall in fünf Modi — `normal`, `A-fenster-leer` (die Fensterfunktionen liefern nichts), `B-datei-leer` (lebende Datei da, Inhalt leer), `C-datei-weg` (Datei verschwunden), `E-format-geaendert` (Datei da, gesuchte Zeile weg). Urteil: **grün und nicht übersprungen = der Test prüft in diesem Zustand nichts**. Ein Modus wird nur gewertet, wenn der Test lebende Pfade **wirklich angefasst** hat. |
| `docs/_r13bd_einzelfall.py` | ein einzelner Fall mit voller Ausgabe (für die Handprüfung, wenn eine Zeile „rot (errors=1)“ sagt) |

Messzahlen: **1268 Tests in 57 Dateien**, davon **153 mit lebendem Zugriff** und **24 mit
Leerlauf-Bauform**. Die Verdachtsfälle sind in `_r13bd_verdacht.txt` vollständig aufgelistet.

## 2. Vorher → Nachher (dieselbe Messung, dasselbe Werkzeug)

| | vorher (`…_vorher.txt`) | nachher (`…txt`) |
|---|---|---|
| grün-durchgelaufene Paare | **9** auf 3 Tests | **5** auf 2 Tests |
| darunter echte Funde | alle drei Tests | die zwei verbliebenen sind **widerlegt** (§4) |

Vorher (gezählt wurden Paare Test × Modus):
`r13ah::…loesen_keinen_falschen_alarm_aus` (A, B, E), `r13ae::test_c_trend_endet_nicht_mehr_bei_b211`
(B, E), `r13p::test_reviewer_darf_nur_lese_git` (B, C, E), `r13ae::…die_kopie_stimmt_mit_dem_laufenden_repo` (C).

Nachher sind die ersten drei verschwunden; was übrig bleibt, ist in §4 widerlegt.

## 3. Die vier Umstellungen (mehr waren nicht belegbar)

| # | Test | gemessener Leerlauf | Umstellung |
|---|---|---|---|
| 1 | `test_r13ah_fixes::TestHybridStillstand` `test_echte_dateien_loesen_keinen_falschen_alarm_aus` → **`test_fester_stand_loest_keinen_falschen_alarm_aus`** | Modus A grün (Fenster leer ⇒ `hybrid_stillstand() == ""` ⇒ die Zusicherung hält) | Muster R13bc: Preflight-Dateien aus `tests/fixtures/stand_b224` ins Wegwerf-Repo kopieren, Fenster **14** (B212–B225) und die eigene Zusicherung „B212, B213 und B214 liegen im Fenster“. Danach: Modus A **rot**, Modi B/C/E „nicht anwendbar (kein lebender Zugriff)“ |
| 2 | `test_r13ac_fixes::TestTrendMitEchtenDateien.test_die_kopie_stimmt_mit_dem_lebenden_repo` | beide verglichenen Listen stammen aus derselben Datei — fehlt die Zeile `C Koepfe` (Format geändert), sind **beide leer** und `assertEqual([] , [])` hält | Zusicherung „die Zeile wurde im lebenden Repo gefunden“ vor dem Vergleich. Danach: Modi B/E **rot** |
| 3 | `test_r13ae_fixes::TestEchteDateien.test_die_kopie_stimmt_mit_dem_laufenden_repo` | dasselbe **plus** Modus C: ist `self.kopiert` leer (die lebenden Dateien waren beim Kopieren weg), läuft die `for`-Schleife **kein einziges Mal** — der Test war grün, ohne eine Zusicherung auszuführen | beide Zusicherungen: Kopie nicht leer, Zeile gefunden. Danach: Modi B, C, E **rot** |
| 4 | `docs/_r13av_lauf.py` (Beleg der vollen Reihe) | nicht ein Test, sondern das Werkzeug: `verbosity=1` schrieb nur „OK (skipped=1)“ — in R13bc musste der eine Skip mit einem eigenen Skript gesucht werden | eigener `unittest.TestResult`, der jeden Skip mit Name und Grund sammelt; der Beleg endet jetzt mit `Übersprungen (N) - Name und Grund:` und je Zeile `- <modul>.<Klasse>.<test>  [Grund]` (bzw. `Übersprungen: keine`). Die Kurzfassung auf der Konsole nennt dieselben Zeilen. |

## 4. Die zwei verbliebenen Treffer — widerlegt, mit Begründung

* **`test_r13ae_fixes::TestEchteDateien.test_c_trend_endet_nicht_mehr_bei_b211`** (Modi B, E):
  **Messfehler des Instruments, nicht des Tests.** Die Klasse kopiert die lebenden Preflight-
  Dateien mit `shutil.copy2`; auf Windows läuft das über `_winapi.CopyFile2`, also **am
  Patch vorbei** — nachgemessen: im Modus „Datei leer“ hatten die Kopien weiter 1909/2345 Byte,
  `c_trend` fand dieselben Zahlen wie normal. Der Test prüft also sehr wohl; der Modus konnte
  seinen Zustand nur nicht herstellen. (Der Messfehler ist in §6 vermerkt.)
* **`test_r13p_fixes::TestReviewHistorie.test_reviewer_darf_nur_lese_git`** (Modi B, C, E):
  der Test liest `prompts/reviewer.md` **nur mittelbar** (`reviewer.build_command` baut den
  Befehl daraus), seine Zusicherungen gelten aber der Kommandozeile
  (`--allowedTools`/`--disallowedTools` gegen `profiles.nur_lese_git_regeln()`). Ob der Prompt
  leer ist oder nicht, ändert an diesen Zusicherungen nichts — grün in allen Modi ist hier
  **korrekt**. Kein Fund.

## 5. Offene Liste (bewusst nicht umgestellt)

Die restlichen 22 Verdachtsfälle aus `_r13bd_verdacht.txt` sind **gemessen unfundig**: sie
gehen in den Modi A/B/C/E **rot** („greift hart zu“) oder **übersprungen** (sichtbar, und seit
Punkt 4 mit Namen im Beleg). Die Begründung je Fall steht in `_r13bd_leerlauf_vorher.txt`
(Zeile „Urteil“). Namentlich die zehn wichtigsten:

`test_r11_fixes::TestTokenZaehlung.test_ganze_datei_b159` · `test_r13ac_fixes::TestBatchArtPflichtzeilen.test_echte_batches_211_und_212_sind_b` ·
`test_r13ac_fixes::TestGegenprobeEchteDaten.test_startzeit_aus_result_json_stimmt_mit_dem_bericht` ·
`test_r13ad_fixes::TestNachruecklisteErkennung.test_gegen_den_echten_b213_auftrag` ·
`test_r13ad_fixes::TestNachruecklisteErkennung.test_gegen_die_echten_b211_b212_auftraege` ·
`test_r13af_fixes::TestDokumentation.test_bedienung_hat_den_abschnitt` ·
`test_r13ah_fixes::TestGemesseneKappungen.test_b212_hat_gekappte_aufrufe_ohne_eigenes_timeout` ·
`test_r13ak_fixes::TestTolerantesAntwortmuster.test_echte_zeilen_stehen_wirklich_so_im_repo` ·
`test_r13aq_fixes::TestGelaufen.test_der_echte_meta_217_ist_das_beispiel` ·
`test_r13x_fixes::TestEchteBelege.test_dokument_widerspruch_verliert_gegen_den_preflight`

Ebenfalls offen und **nicht** umgestellt: die Zitatprüfungen (`test_r13az::TestAnlassImRepo`) und
die geschlossenen Nummernkreise (`test_r13x::TestEchteBelege`, `test_r13aa`), weil sie den
lebenden Stand prüfen **sollen** — siehe `docs/_r13bc_belege.md` §„Was bewusst NICHT umgestellt
wurde“.

## 6. Grenzen der Messung (ehrlich vermerkt)

* `shutil.copy2` umgeht das Instrument auf Windows (native Kopie, §4). Tests, die ihre Vorlage
  **kopieren**, sind damit nur in den Modi A/C prüfbar, nicht in B/E.
* `harness.toml` ist von der Leerung ausgenommen: wird die Konfiguration mitgeleert, scheitert
  schon `load_config()` im `setUpClass` und der Modus meldete fälschlich „greift hart zu“.
* „Grün in einem Modus“ belegt **nicht** automatisch einen Fund: es zählt nur, wenn der Test
  lebende Pfade wirklich angefasst hat (Kennzahl „kein lebender Zugriff im Test“ prüft das)
  **und** die Zusicherung am lebenden Inhalt hängt. Die zweite Hälfte dieser Bedingung bleibt
  Handarbeit — deshalb steht bei jedem Fund eine Begründung und nicht nur eine Zahl.
