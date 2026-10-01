# Fixture `stand_b234_luecke` — Bilanz ohne Preflight (R13bf, Befund M234-1)

**Anlass.** Die Aussensicht B234 (2026-10-01, 10:51) fand: die Harness-Bilanz führte
„C Koepfe 115 referenzgleich“, obwohl B234 **vor** dem Preflight abbrach
(`runs/b234/result.json`: `rc 1`, `killed_reason: event`, `preflight_laeufe: 0`) und
`analysis/_preflight_234.txt` nicht existierte. Die 115 stammten aus der **Soll-Spalte**
des Batch-Dokuments (`hx/bilanz.py` → `stand.ist_wert` nahm die letzte numerische Zelle).

**Inhalt (eingefroren, Stand 01.10.2026 10:51).**

| Datei | Herkunft |
|---|---|
| `decomp/analysis/port-batch234-c-ausgefuehrte-koepfe-2026-10-01.md` | die **ersten 59 Zeilen** des echten Batch-Dokuments (Kopf + §1-Vorhersage mit der Soll/Ist-Tafel `\| Bilanzzeile \| Ist (B233) \| Soll (B234) \| Begruendung \|`) |
| `decomp/analysis/_preflight_233.txt` | **byteweise** Kopie (3483 B, UTF-8-BOM) — der letzte *gemessene* Stand (`C Koepfe 110 / 6187 / 0`) |

Absichtlich **nicht** enthalten: `_preflight_234.txt` (existiert in der Fixture nicht —
genau das ist der Fall), die zweite Tafel des Dokuments ab Zeile 300 (`| Bilanzzeile |
Soll (Vorhersage) | Ist (_preflight_234.txt) | Urteil |`, die erst der wiederholte Lauf
schrieb) und alle `_m234/`-Dateien.

**Was die Fixture zeigt (Kennzahlen, mit `hx/stand.py` gelesen).**

* `stand.preflight_dateien` → nur `_preflight_233.txt`; die „Preflight-Ära“ beginnt bei
  B233, B234 liegt darin und hat keine eigene Datei.
* `stand.ist_wert(text, _ETIKETT_CKOPF, _RE_ZAHL_CKOPF)` → **110 / 6187 / 0** (die
  Ist-Spalte). Vor R13bf lieferte dieselbe Zeile **115 / 6271 / 0** (die Soll-Spalte).
* `stand.kernzahlen(cfg, 8)` → für B234 **kein** `c_koepfe`, dafür `c_nicht_gemessen=True`
  und `c_erwartet="_preflight_234.txt"`; die letzte Zahl mit Wert bleibt B233 (110).

**Gebaut mit** `docs/_r13bf_fixture.py` (kopiert Zeilen 1–59 und die Preflight-Datei).
Die Anlage ist per `.gitattributes` (`harness/tests/fixtures/**  -text`) vor
Zeilenenden-Umschreibung geschützt — sonst schneidet `core.autocrlf=true` das BOM ab.
