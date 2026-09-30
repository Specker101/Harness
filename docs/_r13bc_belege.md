# R13bc — Realtests auf eingefrorene Fixtures (Aufräumrunde, 30.09.2026)

**Auftrag (Nutzer).** „Alle Tests, die gegen lebende Dateien im Decomp-Repo prüfen und sich
bei weiterziehendem Stand per `skipTest` abschalten (u. a. `test_r13ay`, `test_r13ba`,
`test_r13bb` Realtests), auf eingefrorene Fixtures unter `tests/fixtures/` umstellen. Pro
Test ein fester Stand, der dauerhaft geprüft wird."

## Warum (gemessen, in dieser Session)

Der Fehler ist in den letzten drei Runden dreimal aufgetreten: während der Arbeit an den
Fixes sind B222, B224 und B225 gelaufen und haben `analysis/_m<N>/…`, `_preflight_<N>.txt`
und `hybrid-plan.md` verändert. Folge:

* `test_r13ay::test_median_der_echten_zuwaechse_ist_sechs` — B224 kam als Kopf-Batch mit
  `+3` dazu, der Median wurde 5 statt 6 → Test rot, dann per Bedingung entschärft.
* `test_r13ba` — die neueste Messung war nicht mehr B222 (25/2011), sondern B224
  (20/1657) → `skipTest`.
* `test_r13bb::TestEchterPlanMischregel` — die Zeilennummer der Gilt-Zeile wanderte
  (354 → 368, der Worker schreibt den Plan fort) → `skipTest`.

Ein Test, der sich abschaltet, prüft nichts mehr: die Regel steht dann nur noch im Code,
ohne Prüfung. Deshalb jetzt ein fester Stand.

## Die Fixture

`harness/tests/fixtures/stand_b224/` — 86 Dateien, 645 KB, **byteweise** kopiert:
Decomp-Abzug (`hybrid-plan.md`, `_preflight_*.txt` B200–B225, `_m<N>/_bilanz*.txt`,
`_m210|219|222|224/_c_paket_e*.txt`, die drei `_preflight_<N>_fehllauf1.txt`) und
Harness-Abzug (`runs/b200..b225/auftrag.md`, `runs/b218|223|224/preflight-aufrufe.jsonl`).
Byte-Kopien sind nötig, weil das **UTF-8-BOM** von `_m224/_c_paket_e_nachher.txt` und die
**fehlende** Datumszeile in `_m222/_c_paket_e.txt` selbst Prüfgegenstand sind.

Aufbau, Bauanleitung und die Zahlen des Stands: `tests/fixtures/stand_b224/README.md`.
Messwerte aus der Fixture: `docs/_r13bc_fixture.txt` (Erzeuger `docs/_r13bc_fixture.py`) —
u. a. Paket E offen **20/1657** (B224), Vorher-Paar **B222 22/1849 → +2/+192**,
Rate **Median 4 / Mittel 2,375**, PLAN/IST (n=12) **Median 5**, Mischregel **1 B : 1 C,
Anteil 0,5, `hybrid-plan.md:368`**, Preflight-Rückblick **B218 2+1=3, B223 1+1=2,
B224 1+1=2**.

**Byte-Treue (wichtig für die Fixture).** `.gitattributes` nimmt `harness/tests/fixtures/**`
mit `-text` von der Zeilenenden-Konvertierung aus. Ohne diese Regel hätte `core.autocrlf=true`
beim `git add` das UTF-8-BOM der Messdatei abgeschnitten — genau das Merkmal, das Punkt 4
prüft (nachgemessen: ohne die Regel begann der Blob mit `23 20 4d 65`, mit der Regel mit
`ef bb bf 23`). Kodierungen des Abzugs: `docs/_r13bc_kodierung.txt` (Erzeuger
`docs/_r13bc_kodierung.py`) — `_preflight_216.txt` ist UTF-16 LE, 215/223/224 sind
UTF-8-BOM, die Messdatei B224 ebenfalls UTF-8-BOM.

**Nachgeprüft, dass die Regel auch beim Auschecken greift** (`docs/_r13bc_checkout.py`,
Ergebnis `docs/_r13bc_checkout.txt`): `git checkout-index -f --prefix=<temp>` legt die Dateien
so ab, wie ein frischer Clone sie bekäme; verglichen mit der Arbeitskopie sind **6 von 6**
byte-identisch — `_m224/_c_paket_e_nachher.txt` beginnt mit `ef bb bf 23`, `_preflight_216.txt`
mit `ff fe 3d 00`, `hybrid-plan.md` (CRLF) unverändert. Ohne die `-text`-Regel fällt das BOM
beim nächsten `git add`/Checkout weg.

## Umgestellte Tests (Liste)

| Testdatei | vorher | jetzt |
|---|---|---|
| `tests/test_r13ay_fixes.py` | `TestEchteWerte` (Klassen-`skipIf` auf `_m219/_c_paket_e_nachher.txt` + `_m210/_c_paket_e.txt`; 1 Test) | **`TestMedianDerZuwaechseGefroren`** (Basis + Fixture-Kopie): `MEDIAN der 3 Zuwaechse … (+3 (B224), +5 (B219), +7 (B216)): 5 Koepfe` und „Ziel … höchstens ca. 6"; kein `skipTest` mehr |
| `tests/test_r13ba_fixes.py` | `TestEchteDateienB222` (2 Tests, 2 `skipTest`), `TestEchteWerte` (5 Tests, 3 `skipTest`), Modulkonstanten `ECHTER_CFG`/`ECHTER_STAND`/`ECHTER_MESSUNG` (lasen beim Import das lebende Repo) | **`TestFesterStandB224`** (3: neueste Messung/UTF-8-BOM/Datum ohne PARSER-Meldung, Vorher-Paar `B222 → B224` ohne Verdrehung, Fakten-Anbindung) und **`TestFesterStandRate`** (4: Kopf-Batches `(224,3)`,`(219,5)`, Median 4 / Mittel 2,375 / Zeile, Durchsatzzeile, Hochrechnung `5 C-Batches bei +4.0`, PLAN/IST n=12 mit Median 5). Die Konstanten sind durch feste Standwerte (`STAND_TEXT`, `STAND_QUELLE`) ersetzt; die selbst gebauten Fixtures (`TestRateAusDenDaten`, `TestAuswahlDerMessdatei`, `TestHochrechnungNutztDenMedian`) bleiben unverändert |
| `tests/test_r13bb_fixes.py` | `TestRueckblickEchteBatches` (2 `skipTest`), `TestEchterPlanMischregel` (4 `skipTest`), `TestEchtePaketEDateiB224` (4 `skipTest`) | **`TestRueckblickFesterStand`** (2: 218/223/224 gegen den Abzug, keine überholten Dateien), **`TestPlanMischregelFesterStand`** (3: `1 B : 1 C`, `hybrid-plan.md:368`, „jeder 2. Batch ist ein C-Batch (50 %)" und die Kalenderzeile mit „Anteil 50 %"), **`TestPaketEDateiFesterStand`** (2: BOM-Datei mit Datum, keine PARSER-Meldung, Gegenprobe der BOM-losen Datei) |

Damit ist in diesen drei Dateien **kein `skipTest` auf Repo-Zustände** mehr übrig
(`test_r13bb` behält nur die Punkt-1-Skips der Fortsetzungslogik, die nichts mit Dateien zu
tun haben).

## Was bewusst NICHT umgestellt wurde (und warum)

* **Zitatprüfungen** (`test_r13az_fixes::TestAnlassImRepo` gegen `bucket-d-fun80013d80.md`,
  `hybrid-plan.md`, `bericht-b221-berichtspunkt-hybrid.md`, `runs/b222/review.md`): diese
  Tests **sollen** das lebende Repo prüfen — sie belegen, dass die Zitate im Prompt
  (`R13az`) stimmen. Sie schalten sich nur ab, wenn eine Datei fehlt; ein verschobenes Zitat
  macht sie **rot** (nicht still). Eine Fixture würde den Zweck zerstören.
* **Abgeschlossene Nummernbereiche** (`test_r13x::TestEchteBelege` kopiert B202/203/206–208,
  `test_r13ah` liest `_preflight_212..214.txt`, `test_r13ac`/`test_r13ae` vergleichen Kopien
  gegen das Original, `test_r13aa` liest `runs/b207..209`): sie ziehen mit dem Stand **nicht**
  weiter, der `skipTest` feuert nur, wenn eine Datei verschwindet. Kein Drift, keine
  falschen Erwartungen.
