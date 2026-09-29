# R13an-Belege (2026-09-29): `plan_mischung` robust + Tests entkoppelt

Auftrag A: (1) `plan_mischung` wählt die Zeile mit der Form `n B : m C` (bei mehreren: die
mit `ENTSCHEIDUNG`, sonst die letzte); fehlt ein Verhältnis, **Warnung ins Log und in die
Review-Fakten** (`PARSER: Mischverhaeltnis in hybrid-plan.md nicht erkannt`), kein stilles
`None`. (2) `test_mischverhaeltnis_aus_dem_plan` auf eine eingefrorene Fixture umstellen
(Stand vor 23:04, aus git) + zweiter Test mit dem heutigen Stand. (3) **Nur berichten:**
welche weiteren Tests lebende Dateien aus `g:\Silent Scope Decomp` lesen.

---

## 0. Anlass (gemessen)

`test_r13aa_fixes.py::test_mischverhaeltnis_aus_dem_plan` las `analysis/hybrid-plan.md`
**lebend**. Der laufende Batch B216 hat die Datei (Auftrag `runs/b216/auftrag.md:260`
„`hybrid-plan.md` Berichtspunkt + **Mischverhaeltnis** + B-Schritt-Reihenfolge") um 23:04
erweitert:

```
hybrid-plan.md:299  Mischverhaeltnis 2:1 ab B217 voraussichtlich **B221** (B217 B, B218 B, B219 C,
hybrid-plan.md:301  - **Mischverhaeltnis 2 B : 1 C (ENTSCHEIDUNG Reviewer):** B208 B, B209 B, B210 C
```

Alte Regel = **erste** Trefferzeile → Zeile 299; deren `2:1` paßt nicht auf
`_RE_MISCH_ZAHL = (\d+)\s*B\s*[:\-/]\s*(\d+)\s*C` → `anteil = None`, `paare` = B217/218/219
→ `assertAlmostEqual(None, 1/3)` → `TypeError`. Die volle Reihe lief damit auf **947 Tests,
1 Fehler**; der Fehler war reproduzierbar, solange die neue Zeile in der Datei steht.

## 1. Fix 1 — Auswahlregel und Meldung (`hx/stand.py`)

* `plan_mischung` sammelt jetzt **alle** Zeilen mit dem Wort „Mischverhaeltnis"
  (`kandidaten`) und wählt daraus die mit einem Verhältnis (`mit_zahl`);
  gibt es mehrere, die mit `ENTSCHEIDUNG`, sonst die **letzte**.
* Trägt **keine** Zeile ein Verhältnis: Rückfall auf die **letzte** Kandidatenzeile (die
  Paare bleiben so nutzbar) mit `erkannt=False` und benanntem `grund` — **kein stilles
  `None`**. Rückgabe zusätzlich `erkannt`, `grund`, `kandidaten`.
* Neu `plan_mischung_pruefen(cfg, log=None)` (Muster R13ae): meldet
  `PARSER: Mischverhaeltnis in hybrid-plan.md nicht erkannt (<grund>)` und schreibt eine
  WARN-Zeile ins Log. Zwei Wortlaute, weil zwei Faelle: fehlt die Datei selbst, lautet die
  Zeile `PARSER: hybrid-plan.md nicht lesbar (<grund>)` — in einem Echtlauf eine Anomalie,
  in Tests mit umgebogenem Wurzelverzeichnis normal. Beide Male bleibt es nicht still.
  Der Orchestrator hängt sie in den Review-Fakten an **eigener** Stelle an (nicht in den
  `if/else`-Zweig der Preflight-Prüfung: die positive Zeile „erwartete Zeilen gelesen,
  keine Luecke" sagt etwas über die Preflight-Datei, nicht über den Plan — der erste
  Versuch hatte sie verdrängt, `test_r13ae_fixes.py::test_ohne_luecke_steht_die_positive_
  zeile` schlug an, der Zweig ist jetzt getrennt).
* Die Aufrufer `stand.kennzahlen`/`strang_von_batch` lesen weiter nur `paare`/`anteil`/
  `regel`/`zeile`/`datei` (unverändert vorhanden).

## 2. Fix 2 — Fixtures statt lebender Datei (`tests/fixtures/`)

| Datei | Decomp-Revision | Inhalt |
|---|---|---|
| `hybrid-plan_vor_b216.md` | `bd92910` (29.09., 20:09) | nur die Zeile `… 2 B : 1 C (ENTSCHEIDUNG Reviewer): B208 B, B209 B, B210 C` (`:286`) |
| `hybrid-plan_mit_b216.md` | `4f60f45` (29.09., 23:15) | beide Zeilen (`:299` ohne Verhältnis, `:301` mit) |

Beide sind **wortgleich** aus `git show <rev>:analysis/hybrid-plan.md` erzeugt, UTF-8 ohne
BOM, LF, **ohne Vorspann** — die Zeilennummern stimmen dadurch mit der Originaldatei
überein (299/301). Werkzeug: `tests/_tmp_fixtures/make.py` (einmalig; nicht getrackt).
`test_r13aa_fixes.py` kopiert jetzt `hybrid-plan_vor_b216.md` (die Prüfung „echte Belege
fehlen" bezieht sich auf die Fixture, nicht mehr auf die lebende Datei); neu
`harness/tests/test_r13an_fixes.py` (13 Tests) prüft beide Fixtures, die Auswahlregel
(mehrere Verhältnis-Zeilen → letzte; `ENTSCHEIDUNG` schlägt die spätere Zeile; Form
`2B:1C`), die Parser-Meldung, das fehlende Dokument und die Kompatibilität der Rückgabe.

## 3. Punkt 3 — Bestandsaufnahme: Tests an lebenden Decomp-Dateien

Statische Sonde `docs/_r13an_bestand_probe.py`, Ausgabe `docs/_r13an_bestand.txt`
(je Datei: `load_config`, umgebogene Pfade, gelesene Dateinamen und Nummernbereiche).

**Befund:** Nach der Umstellung liest **kein** Test mehr ein *Dauer-Dokument* des
Decomp-Repos. Die verbleibenden Lesezugriffe gelten **abgeschlossenen** Batches:

| Test | liest | Bereich | Bewertung |
|---|---|---|---|
| `test_r13aa_fixes.py` | `hybrid-plan.md` | Dauer-Dokument | **umgestellt auf Fixture** (dieser Auftrag) |
| `test_r13ac_fixes.py` | `_preflight_198..210.txt`, `_m203..210/_bilanz*.txt` | fest 198–210 | geschlossen — der laufende Batch schreibt nur sein eigenes `N` |
| `test_r13ae_fixes.py` | `_preflight_211/212/213.txt` | fest 211–213 | geschlossen |
| `test_r13ah_fixes.py` | `_preflight_214.txt` (u. `_preflight_207_vor_fortsetzung1.txt`) | fest | geschlossen |
| `test_r13x_fixes.py` | `port-batch{202,203,206,207,208}-*.md`, `_preflight_{202,203,206,207,208}.txt`, `_m*`, `runs/b206..208`, `runs/b209/harness-facts.md` | fest | geschlossen |

Alle fünf kopieren die Dateien in ein Wegwerfverzeichnis und überspringen sich, wenn eine
fehlt (`skipIf`) — das Muster stammt aus R13x/R13ac und ist dort ausdrücklich als Antwort
auf den „das Neueste ist kein stabiler Bezug"-Fallstrick dokumentiert.

**Bewusste Entscheidung (nicht umgestellt):** die vier Dateien mit **festen,
abgeschlossenen** Nummernbereichen sind *nicht* auf Fixtures umgestellt. Grund: der
Fehlermechanismus, der R13aa getroffen hat (Dauer-Dokument wird mitten in der Reihe
umgeschrieben), kann dort nicht auftreten; eine Umstellung würde ~30 Dateien aus dem
Decomp-Repo in dieses Repo kopieren, ohne die Aussage zu ändern. **Eine Restunsicherheit
bleibt und ist bekannt:** `test_r13x._echte(nummer)` nimmt per `glob(...)[-1]` die *letzte*
Datei zu einem Nummernbereich — legt ein künftiger Batch ein zweites `port-batch206-*.md`
an, wandert der Bezug. Wird das gewünscht, ist die Umstellung dieser vier Dateien ein
eigener, kleiner Auftrag (Fixture-Ordner `tests/fixtures/decomp_belege/`, Revision je Datei
im Docstring).

## 4. Tests

* `harness/tests/test_r13an_fixes.py` — **13 Tests** (Fixtures, Auswahlregel, Meldung,
  fehlende Datei, Kompatibilität).
* `harness/tests/test_r13aa_fixes.py` — **33 Tests OK**, jetzt gegen die Fixture; die
  beiden an die alte Rückgabeform gekoppelten Tests sind mitgezogen
  (`plan_mischung` liefert kein leeres `dict` mehr, sondern `erkannt=False`).
* Mitgeprüft (unverändert, weil die Parser-Zeile in den Review-Fakten ein gemeinsamer
  Ausgabepfad ist): `test_r13ae_fixes.py` 25 OK, `test_r13ah_fixes.py` 49 OK,
  `test_r13x_fixes.py` 32 OK, `test_r13ac_fixes.py` 46 OK, `test_r13al_fixes.py` 26 OK,
  `test_units.py` 30 OK.

**Zwischenfall, der zur getrennten Verzweigung führte (gemessen):** der erste Entwurf
hing die Mischverhältnis-Meldung an dieselbe Liste wie die Preflight-Meldungen. In
`TestFaktenZeile.test_ohne_luecke_steht_die_positive_zeile` schreibt der Test einen
*gültigen* Preflight in ein Wegwerf-Wurzelverzeichnis, in dem kein `hybrid-plan.md`
liegt: die Meldung „Datei nicht lesbar“ machte die Liste nicht leer, die positive
Zeile entfiel, `test_r13ae_fixes.py` meldete **1 Fehler** (Zuruf des Belegs, nicht
vermutet). Genau deshalb sind es zwei getrennte Zweige und zwei Wortlaute.

## 5. Nicht geprüft / offen

* Das Verhalten in einem **Echtlauf**: dass die Fakten-Zeile im Review-Prompt auch
  ankommt, ist aus dem Code abgeleitet, nicht an einem laufenden Review gemessen — der
  Harness läuft gerade (B216), es wurde nichts an `state/` oder `runs/` angefasst.
* Die vier Tests mit festen Nummernbereichen (Abschnitt 3) sind **nicht** auf Fixtures
  umgestellt; die Restunsicherheit `glob(...)[-1]` in `test_r13x` bleibt benannt.
