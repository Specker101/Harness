# Fixture `stand_b243` - eingefrorener Stand (02.10.2026, nach B243)

Gebaut mit `docs/_r13bn_fixture_b243.py` fuer R13bn Punkt 3 (Aussensicht M242-3/M243-3):
der Test der Prognose laeuft gegen die **Reihe B237-B243**.

**Regel: Diese Dateien werden NICHT nachgezogen.** Ein neuer Stand bekommt ein eigenes
Verzeichnis (`stand_b<N>`), die Erwartungen im Test gehoeren zu genau dieser Fixture.

## Aufbau

```
stand_b243/
  decomp/analysis/_preflight_236..243.txt   (8 Dateien, wortgetreu)
      Zeilen: "C Koepfe  <n> / <faelle> / <abw>"  und
              "Bahnabdeckung ... verifiziert <n> | teilgeprueft <m> ..."
  root/runs/b236..243/auftrag.md            (Instruktionen, wortgetreu)
  root/runs/b237..244/review.md             (die Reviews zu 236..243, wortgetreu -
      sie tragen die Pflichtzeile "B-SCHRITT:" und damit den Strang-Beleg)
  decomp/analysis/hybrid-plan.md            (traegt die Regel "1 B : 1 C", gegen die der
      gemessene Abschnitt steht)
  decomp/analysis/_m<N>/_bilanz<N>.txt      (die kanonischen Bilanzdateien, SOWEIT IM REPO
      VORHANDEN: B241 fehlt - das ist der Anlass von M242-3)
```

Gemessen an diesem Stand (siehe `tests/test_r13bn_fixes.py`):

* Zuwaechse der C Koepfe im Fenster B236..B243: +4 (B237), +2 (B239), +2 (B241) ->
  **Median 2**. B241 hat KEINE kanonische Bilanzdatei (`analysis/_m241/_bilanz_241.txt`
  fehlt) - der Median aus den Bilanzdateien liess ihn weg und stand auf **3**.
* Strang: B238 und B240 sind B-Batches, ab B241 sind alle C (Strang B ruht nach R236-1)
  -> Anteil fuer die Rechnung **100 %**.
* `C verifiziert` (Bahnabdeckung): B236 87 -> B243 92 = **+5**; die Reihe B237..B243
  darin: 90 -> 92 = **+2**.
