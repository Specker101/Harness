# R13ae-Belege (2026-09-29): Preflight-Zeilen tolerant lesen, fehlende Zeile melden,
# Umschaltschwelle 75 min

Auftrag (Nutzer, 2026-09-29): (1) die Preflight-Zeilen-Parser in `hx/stand.py` gegen die
tatsächlich geschriebenen Zeilenformen robust machen — Zusatzwörter **vor** und Zusätze
**hinter** den Zahlen — und eine **fehlende** Zeile laut melden (Log + Review-Fakten)
statt still `None` zu liefern; (2) `limits.umschalt_vor_alarm_s` von 600 auf 900 s
(Schwelle 75 min).

Alles im Harness-Repo (`g:\Harness`). Das Decomp-Repo wurde nur **gelesen** (Preflight-
Dateien, Bilanzdateien); der laufende Batch wurde nicht angefasst.

---

## 1. Was kaputt war (CONFIRMED, gemessen)

`scripts/preflight.py` schreibt die C-Kopfzeile seit **B212** als
`C Koepfe referenzgleich 78 / 4006 / 0`. Der Parser verlangte die Zahlen **direkt** hinter
dem Etikett:

| Datei:Zeile | Muster (vorher) |
|---|---|
| `harness/hx/stand.py:245` | `_RE_PREFLIGHT_CKOPF = re.compile(r"^C Koepfe\s+(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\b")` |

(Zeile 245 ist der Stand **vor** dem Fix; die Konstante steht jetzt in Zeile 266.)

Folge: `preflight_c_koepfe` (`stand.py:764`, Treffer bei `:778`) übersprang die Zeile,
`kernzahlen` lieferte für B212/B213 `None`, und `c_trend` (`stand.py:699`) endete bei
**B211**: die Anzeige zeigte weiter `2795` Fälle, während in `_preflight_213.txt` **4006**
stand. Kein Fehler, keine Warnung — nur eine kürzere Reihe.

**Die vollständige Liste der Preflight-Zeilen-Parser in `stand.py`** (alle drei sind jetzt
gleich tolerant; das ist der Gegenstand von Punkt 1):

| Datei:Zeile | Konstante | gelesen von | Zeile im Preflight |
|---|---|---|---|
| `harness/hx/stand.py:266` | `_RE_PREFLIGHT_CKOPF` | `preflight_c_koepfe` (`:764`, Treffer `:778`) | `C Koepfe … 78 / 4006 / 0` |
| `harness/hx/stand.py:579` | `_RE_BAHN_ZEILE` | `preflight_bahnabdeckung` (`:638`) | `Bahnabdeckung 57/78 \| Bloecke 335/434 \| verifiziert 60 \| teilgeprueft 18` |
| `harness/hx/stand.py:580` | `_RE_NACHRUECK_ZEILE` | `preflight_bahnabdeckung` (`:638`) | `Nachrueckliste 1 62/80 \| verifiziert 62` (optional) |
| `harness/hx/stand.py:589` | `_RE_HYBRID_ZEILE` | — (nur Anwesenheit) | `Hybrid-Lauf 215 \| 800138F0 \| MMIO \| 28/407 \| 0` |

Dazu die Wortmuster **innerhalb** der Zeile (unverändert, weil schon tolerant):
`_RE_WORT_VERIFIZIERT` (`:581`), `_RE_WORT_TEILGEPRUEFT` (`:582`), `_RE_ZAHL_BLOECKE`
(`:583`), `_RE_ZAHL_PAAR` (`:585`).

## 2. Was jetzt gilt

**Ein gemeinsamer Bauplan für alle Zeilen** (`stand.py:_preflight_zeile`, Zeile 246):
`^<Etikett>\b[^\d\n]{0,40}<Zahlen>` — zwischen Etikett und Zahlen dürfen bis zu 40 Zeichen
**Prosa** stehen, aber **keine Ziffer und kein Zeilenwechsel**. Damit kann die Lücke nicht
in eine fremde Zahlenspalte rutschen; eine unvollständige Zeile holt sich ihre Zahlen nicht
aus der nächsten (Testfall `test_die_luecke_enthielt_keine_ziffern_sonst_keine_zeile`).
Hinter den Zahlen ist ein beliebiger Zusatz erlaubt (`referenzgleich`, `| ausgeduennt 12`,
`OK`), weil kein Muster am Zeilenende verankert ist.

**Melden statt schweigen** (`stand.py:preflight_zeilen_pruefen`, Zeile 604):

* Geprüft wird mit **denselben Mustern**, mit denen geparst wird (`PREFLIGHT_ERWARTET`
  `stand.py:596` hält Muster und Parser-Funktion zusammen; Test
  `test_erwartete_zeilen_sind_dieselben_muster_wie_die_parser`).
* Fehlt eine Zeile, gibt es eine `WARN`-Zeile im Harness-Log (`msg` =
  `"Preflight-Zeile nicht erkannt"`, mit `batch`, `datei`, `zeile`, `parsen`) **und** eine
  Zeile in den Review-Fakten:
  `- PARSER: Zeile <Name> in _preflight_<N>.txt nicht erkannt`
  (`hx/orchestrator.py`, `harness_facts`, direkt nach der Kostenzeile).
* Ist nichts offen, steht dort ausdrücklich
  `- Parser (R13ae): erwartete Zeilen gelesen, keine Luecke (_preflight_213.txt: C Koepfe,
  Bahnabdeckung, Hybrid-Lauf)` — die **Abwesenheit** der Warnung ist damit eine Aussage.
* **Geprüft wird nur die neueste Datei** (`anzahl=1`): die alten Batches führen die Zeilen
  gar nicht (`Bahnabdeckung` erst ab B210, `Hybrid-Lauf` erst ab B212) — ein Fenster über
  13 Dateien ergäbe 20 Meldungen über Zeilen, die damals niemand erwartet hat. Der
  Fensterlauf steht im Beleg `_r13ae_retro.txt` als Beweis dieses Verhaltens.
* `Nachrueckliste` steht **nicht** in der Pflichtliste: sie ist optional (Projektregel
  „ab B211", in keiner echten Datei vorhanden) — sonst warnte der Harness in jedem Batch.

## 3. Umschaltschwelle 900 s = 75 min

| Ort | vorher | jetzt |
|---|---|---|
| `harness/harness.toml:66` `limits.umschalt_vor_alarm_s` | 600 | **900** |

**R13ah (2026-09-29) hat den Vorlauf erweitert:** die Schwelle ist jetzt
`Alarm − max(umschalt_vor_alarm_s, Preflightdauer + 5 min)`, `umschalt_vor_alarm_s = 900`
bleibt die Untergrenze des Vorlaufs. Gemessen: Preflight 10,03 min (B214) → Vorlauf 15,03 min
→ Schwelle 74,97 min; ein 20-Minuten-Preflight schiebt sie auf 65 min
(`docs/_r13ah_belege.md` §2).
| `hx/worker.py` Vorgabe in `cfg.get(...)` (3 Stellen: Hook, `fortsetzung_pruefen`, `lim`) | 600 | **900** |
| `hx/uhr.py` Rückfall ohne `umschalt_min` | `weich - 10` | `weich - 15` |
| `prompts/reviewer.md` Beispielzeile | `(Umschalten ab 80)` | `(Umschalten ab 75)` |
| `hx/worker.py` Vorspann (`WORKER_PREAMBLE`) | „Alarmgrenze minus 10 min" | „900 s = 15 min" |

Begründung (Auftrag, mit Messwert belegt): der Preflight-Lauf selbst braucht ~10 min
(`runs/b213/result.json`, langsamster Werkzeugaufruf `preflight.py` = **602 s**), danach
folgen Bilanz und Memory-Export. Bei 80 min lief deshalb jeder volle Batch über den
90-min-Alarm: B213 = **104 min** (`logs/harness-2026-09-29T111144+0000.log:191`,
`"Kein Fortsetzungsanstoss", grund: "Batch-Uhr 104 min >= Umschaltschwelle 80 min"`).
`alarm_wall_s = 5400` bleibt unverändert — es gibt weiterhin **eine** Zeitquelle.

## 4. Tests

`harness/tests/test_r13ae_fixes.py` — **25 Tests**, alle grün:

* Formen: B211-Form (`C Koepfe           78 / 2795 / 0`), B212/B213-Form mit
  `referenzgleich` davor, Zusatz dahinter (`| ausgeduennt 12`, doppeltes
  `referenzgleich`), Bahnabdeckung mit `referenzgleich`, Nachrückliste mit Vorrang.
* Abgrenzung: eine unvollständige Zeile zieht keine Zahlen aus der nächsten; `C Einbindung`
  wird nicht als `C Koepfe` gelesen.
* Warnungen: fehlende `C Koepfe`-, `Bahnabdeckung`- und `Hybrid-Lauf`-Zeile geben genau
  die geforderte Faktenzeile **und** genau eine `WARN`-Zeile im Log; vollständige Datei und
  fehlende Datei haben je ihren eigenen Text; `anzahl=2` prüft zwei Dateien.
* Faktenweg: `Orchestrator.harness_facts` schreibt die Warnzeile in die Datei (gemessen an
  `runs/…/harness-facts.md` im Wegwerfordner) bzw. die positive Zeile.
* Gegenprobe an den **echten** B211/B212/B213-Dateien (eingefroren kopiert): B211 = 2795,
  B212 = 2795, B213 = **4006**; `c_trend(2)` endet bei B213; die einzige echte Lücke ist
  `Hybrid-Lauf` in `_preflight_211.txt`.
* Schwelle: `5400 - 900 = 4500 s = 75 min`; Fortsetzungsanstoss bei 74 min **ja**, bei
  76 min **nein** (Grund nennt „Umschaltschwelle 75 min"); `uhr_text` ohne `umschalt_min`
  sagt „Umschalten ab 75"; der Hook bekommt `--umschalt 75`; Vorspann und
  `prompts/reviewer.md` nennen die 75 und nicht mehr „Alarmgrenze minus 10 min".

## 5. Rückblick B201–B213 (Beleg: `docs/_r13ae_retro.txt`, Skript `docs/_r13ae_retro.py`)

| | altes Muster | neues Muster |
|---|---|---|
| letzter erkannter Batch | B211 (2795 Fälle) | **B213 (4006 Fälle)** |
| Spanne im Fenster `c_trend(12)` | 10 Batches / 11 Dateien | **12 Batches / 13 Dateien** |
| Durchsatzzeile „letzter gemessener Batch" | B211 | **B213** |

Die **Kopfzahl** bleibt dabei 78 (`C Koepfe`): `78 / 2795 / 0` → `78 / 4006 / 0`. Die
zweite Zahl sind die **Fälle** (Prüffälle je Kopf), die dritte die Abweichungen. Der
Durchsatz „+33 Koepfe von B201 bis B213" und die Hochrechnung (+2.8 Koepfe je Batch,
+4.1 je C-Batch, 13 Dateien) ändern sich durch den Fix **nicht** — sie standen schon vorher
auf der Kopfzahl; geändert hat sich, dass die Reihe nicht mehr zwei Batches zu früh endet
und die **Fälle**-Zahl (4006) wieder sichtbar ist.

## 6. Nicht geprüft (offen)

* **Kein Live-Lauf mit der neuen Schwelle**: die 75 min wirken erst im nächsten Batch; die
  Mechanik ist über Config, Hook-Datei und `fortsetzung_pruefen` getestet, der reale
  Batch-Verlauf nicht.
* **Kein echter Fehlfall** einer kaputten Preflight-Datei aus dem Decomp-Repo (alle
  simuliert). Der einzige echte Fund ist die fehlende `Hybrid-Lauf`-Zeile in B211 und
  davor — er wird bewusst nur beim Fensterlauf sichtbar, nicht im Review.
* Die **Bilanz- und Durchsatz-Anzeige** (`/bilanz`, `durchsatz_zeilen`) wurde nicht
  verändert: sie liest jetzt nur eine längere, richtige Reihe.
