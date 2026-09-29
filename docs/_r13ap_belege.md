# R13ap-Belege (2026-09-30): Preflight-Dateien kodierungstolerant lesen + Tippfehler

Auftrag (drei Punkte): **(1)** die Zählregel aus R13ao bleibt (nur echte Starts) —
bestätigt, nichts geändert. **(2)** „Umschwellschwelle" → „Umschaltschwelle" (Hook, Tests,
Doku). **(3)** `analysis/_preflight_*.txt` kodierungstolerant lesen: BOM erkennen
(UTF-16 LE/BE, UTF-8-BOM), sonst UTF-8, NUL-Bytes ohne BOM als UTF-16 LE versuchen; **eine
zentrale Lesefunktion**, alle Leser darauf umstellen (Liste mit Datei:Zeile); bei UTF-16
ein Hinweis in den Review-Fakten; Test mit einer UTF-16-Kopie von `_preflight_216.txt`;
berichten, ob die R13ae-Warnung im Review zu B216 angeschlagen hat.

Zeilennummern unten gelten für den Commit dieser Runde (`@HEAD`).

## 1. Punkt 1 — Zählregel bestätigt, unverändert

`streamjson.ist_preflight_aufruf` (Interpreter + `preflight.py`, Befehlsteil kein Filter)
bleibt die Regel für Hook, `result.json` und den Bericht. Kein Code geändert.

## 2. Punkt 2 — Tippfehler korrigiert

| Datei:Zeile | vorher | nachher |
|---|---|---|
| `harness/hx/uhr.py:149` | `"Preflight vor der Umschwellschwelle …"` | `"… Umschaltschwelle …"` |
| `harness/tests/test_r13ao_fixes.py:36` | derselbe Wortlaut im Test | derselbe Wortlaut, korrigiert |
| `docs/bedienung.md` (§12p, Beispielzeile) | `Umschwellschwelle` | `Umschaltschwelle` |
| `docs/_r13ao_belege.md` (§1, Beispielzeile) | `Umschwellschwelle` + Absatz „absichtlich nicht korrigiert" | korrigiert + Nachtrag, dass die Schreibweise aus dem Auftrag ein Tippfehler war |

Der Hinweis **bleibt** ansonsten wortgleich; `test_r13ao_fixes.py` hat ihn weiterhin
wörtlich im Quelltext stehen (eine Änderung fällt auf), und `test_r13ap_fixes.py`
prüft zusätzlich, dass „Umschwellschwelle" nirgends mehr vorkommt
(`test_hinweistext_schreibt_umschaltschwelle`).

## 3. Punkt 3 — Kodierung

### 3a. Anlass, gemessen (`docs/_r13ap_messung.txt`)

`analysis/_preflight_216.txt` ist **UTF-16 LE mit BOM** (`FF FE`, 4866 B) — B211–B215 sind
**UTF-8-BOM**. `util.read_text` liest UTF-8; jede Zeile kam damit als
`= NUL = NUL …` an, kein Pflichtmuster passte. Über die 62 vorhandenen Preflight-Dateien:

| Kodierung | Dateien | Beispiele |
|---|---|---|
| `utf-8-bom` | 53 | B159–B215 |
| `utf-16-le` | **5** | **B155, B156, B157, B158, B216** |
| `utf-8` (ohne BOM) | 4 | B172, B181, B184, B210 |

Die Form ist also nicht neu — sie war nur lange nicht aufgefallen.

### 3b. Die zentrale Lesefunktion

| Datei:Zeile | Was |
|---|---|
| `harness/hx/util.py:170` | `erkenne_kodierung(b)` — BOM (UTF-8, UTF-16 LE/BE) schlägt alles; sonst UTF-8, bei NUL-Bytes in den ersten 4096 als `utf-16-le-ohne-bom` |
| `harness/hx/util.py:188` | `dekodiere(b, kodierung)` — wandelt in Text, entfernt das BOM, `errors="replace"` |
| `harness/hx/util.py:204` | `ist_utf16(kodierung)` — für den Hinweis |
| `harness/hx/util.py:209` | `read_text_erkannt(path)` → `(text, kodierung)`, fehlende Datei `("", "")` |
| `harness/hx/util.py:151` | `read_bytes_shared(path)` — binär, mit denselben Freigaben wie `open_shared_read` (R13d: ein Leser darf kein `unlink` blockieren) |
| `harness/hx/util.py:108` | `open_shared_read` — unverändert im Verhalten, teilt sich jetzt den Windows-Teil mit dem Binärleser |

Vokabular: `utf-8`, `utf-8-bom`, `utf-16-le`, `utf-16-be`, `utf-16-le-ohne-bom`.

### 3c. Alle Leser von `analysis/_preflight_*.txt` (Datei:Zeile)

Vorher lasen vier Stellen den Inhalt selbst — alle mit `read_text(pfad)[:200000]`:

| Leser | vorher | jetzt |
|---|---|---|
| `stand.preflight_zeilen_pruefen` (R13ae) | `harness/hx/stand.py:621` | `preflight_text(pfad)[0].splitlines()` — `stand.py:668` |
| `stand.preflight_bahnabdeckung` (R13ac) | `stand.py:655` | `preflight_text(pfad)[0]` — `stand.py:698` |
| `stand.hybrid_verlauf` (R13ah) | `stand.py:717` | `preflight_text(pfad)[0]` — `stand.py:760` |
| `stand.preflight_c_koepfe` (R13x, Trend) | `stand.py:866` | `preflight_text(pfad)[0]` — `stand.py:909` |

Die eine Lesestelle: `stand.preflight_text(pfad)` — `stand.py:578`, Kürzung auf
200 000 Zeichen wie vorher (`PREFLIGHT_GRENZE`).

**Ohne Inhalt lesen diese Stellen** (deshalb nicht umgestellt, zur Vollständigkeit):

* `stand.preflight_dateien` (`stand.py:547`) — nur die **Namen** der Dateien;
* `orchestrator.py:2288` — nur `preflight_dateien(...)`, für den Namen in der positiven
  Zeile;
* `worker.archiviere_preflight_vor_fortsetzung` (`worker.py:442`) — kopiert die Datei
  **byteweise** (`shutil.copy2`), dekodiert also nichts und darf das auch nicht.
* Das Decomp-Werkzeug selbst (`scripts/preflight.py` im Decomp-Repo) ist nicht Teil des
  Harness; die Schreibweise dort ist die Ursache, nicht die Gegenmaßnahme.

Der Test `test_r13ap_fixes.TestLeser.test_eine_lesestelle_fuer_alle_vier` prüft
mechanisch, dass die vier Leser über `preflight_text` gehen und `read_text` nicht mehr
selbst benutzen.

### 3d. Hinweis in den Review-Fakten

`stand.preflight_kodierung_hinweis(cfg, anzahl=1, log)` — `stand.py:590`; der Orchestrator
hängt ihn als **eigenen** Fakten-Block an (`orchestrator.py:2283-2288`), damit die positive
Zeile „erwartete Zeilen gelesen, keine Luecke" stehen bleibt (genau der Fallstrick, der
beim Mischverhältnis in R13an zugeschlagen hat). Zeile:

```
- Preflight B216 in UTF-16, gelesen (_preflight_216.txt, utf-16-le)
```

dazu eine WARN-Zeile ins Log (`Preflight-Datei ist UTF-16`). Ohne UTF-16-Datei passiert
nichts (kein Rauschen).

### 3e. Fixture und Test

`harness/tests/fixtures/preflight_216_utf16.txt` — **Byte-Kopie** von
`analysis/_preflight_216.txt` (4866 B, Kopf `FF FE`, Vergleich im Test). Damit prüfen
`harness/tests/test_r13ap_fixes.py` (22 Tests):

* `_preflight_216.txt` in UTF-16: `preflight_zeilen_pruefen` → **`[]`** (alle drei
  Pflichtzeilen erkannt, keine Log-Warnung), `preflight_c_koepfe` → **85 / 4446 / 0**,
  `preflight_bahnabdeckung` → 62/85, Blöcke 382/486, verifiziert 65, teilgeprüft 20,
  `hybrid_verlauf` → Halt-PC `8000C9E8`, Art `MMIO`, Wegmaß 460/42599;
* derselbe Inhalt als UTF-8-BOM und als UTF-8 ohne BOM liefert **dieselben** Werte
  („die Kodierung darf das Ergebnis nicht verändern");
* der Hinweis erscheint genau einmal und nur bei UTF-16;
* in den Review-Fakten stehen **Hinweis und positive Zeile nebeneinander**, und
  „nicht erkannt" kommt **nicht** vor.

### 3f. Bericht: Hat die R13ae-Warnung im Review zu B216 angeschlagen? — **Ja, dreimal.**

Beleg `harness/runs/b217/harness-facts.md:23-25` (der Review von B216 liegt im Ordner von
B217 — Ordner-Konvention):

```
- PARSER: Zeile C Koepfe in _preflight_216.txt nicht erkannt
- PARSER: Zeile Bahnabdeckung in _preflight_216.txt nicht erkannt
- PARSER: Zeile Hybrid-Lauf in _preflight_216.txt nicht erkannt
```

Der Review von B215 (`harness/runs/b216/harness-facts.md:23`) trug dagegen die positive
Zeile. Die R13ae-Warnung hat also **funktioniert** — sie hat den Kodierungsfehler sichtbar
gemacht; die Zahl dahinter fehlte trotzdem (der C-Trend endete auf B215). Nach der
Umstellung, live gemessen:

```
preflight_zeilen_pruefen(anzahl=1) -> []
preflight_c_koepfe(4):  B213 78/4006/0 | B214 78/4006/0 | B215 78/4006/0 | B216 85/4446/0
c_trend(12): erst B204 (64), letzt B216 (85), delta +21, keine Luecken
```

## 4. Tests und Reihe

* `harness/tests/test_r13ap_fixes.py` — **22 Tests** (Erkennung aller fünf Kodierungen,
  fehlende/leere Datei, Fixture als Byte-Kopie, die vier Leser, Gleichheit UTF-8 ↔ UTF-16,
  eine Lesestelle, Hinweis + Review-Fakten, Tippfehler).
* Mitgezogen und grün: `test_r13ae` 25, `test_r13an` 13, `test_r13ao` 23, `test_r13ac` 46,
  `test_r13x` 32, `test_r13aa` 33, `test_r13s` 28, `test_units` 30.
* Volle Reihe: **1005 Tests OK** in 488,3 s (`docs/_r13ap_volle_reihe.txt`). `pyflakes`
  gegen die geänderten Dateien meldet nur die fünf Warnungen, die schon vor dieser Runde
  dort standen (unbenutzte Importe/Variablen in `stand.py`/`orchestrator.py`) - keine neue.

## 5. Nicht geprüft / offen

* Die **Ursache** der UTF-16-Schreibweise liegt im Decomp-Repo (B216 hat den Preflight
  über `Start-Process powershell -Command "python … *> analysis\_preflight_216.txt"`
  gefahren — ein `*>`-Redirect in einer PowerShell **5.1** schreibt UTF-16 LE). Der Harness
  heilt das nicht, er liest es. Wenn die Dateien dauerhaft UTF-8 sein sollen, ist das ein
  Auftrag ans Decomp-Werkzeug (nicht Teil dieser Runde).
* `utf-16-le-ohne-bom` ist eine Heuristik (NUL in den ersten 4096 Bytes): eine UTF-8-Datei
  mit eingebettetem NUL würde falsch dekodiert. Gemessen kommt das in den Preflight-Dateien
  nicht vor (53/5/4 siehe 3a).
* Punkt 1 (Zählregel) wurde nicht neu gemessen — die Bestätigung des Nutzers steht oben.
