# Fixture `stand_b268` - eingefrorener Stand (05.10.2026, nach B268)

Gebaut mit `docs/_r13bw_fixture_b268.py` fuer **R13bw-4**: der Test
`test_r13aa_fixes.TestEchteBelege.test_bilanz_weist_die_hochrechnung_getrennt_aus` hat die
**lebende** Bilanz gelesen und wurde rot, sobald die lebende Preflight-Reihe in den Zustand
„Strang C ruht" kam - der Wortlaut dieses Zustands war mit R13bt-1 umgestellt worden.

**Regel: Diese Dateien werden NICHT nachgezogen.** Ein neuer Stand bekommt ein eigenes
Verzeichnis (`stand_b<N>`), die Erwartungen im Test gehoeren zu genau dieser Fixture.

## Aufbau

```
stand_b268/
  decomp/analysis/_preflight_248..268.txt   (soweit vorhanden; B256 fehlt - das ist echt)
      Zeilen: "C Koepfe  <n> / <faelle> / <abw>", "Bahnabdeckung ... verifiziert <n>"
  decomp/analysis/_m<N>/_bilanz*.txt        (kanonische Bilanzdateien, je Ordner die
      neueste: tragen "R207 <vorher> -> <nachher>")
  decomp/analysis/_m<N>/_c_paket_e*.txt     (die juengste Paket-E-Messung)
  decomp/analysis/hybrid-plan.md            (Mischverhaeltnis-Regel; Zustand nach B216)
  root/runs/b<N>/auftrag.md                 (Instruktionen: Strang, SOLL-KOEPFE)
  root/runs/b<N>/review.md                  (die Reviews: Pflichtzeile B-SCHRITT/STATION)
```

## Was der Stand zeigt (gemessen im Test)

* Der Durchsatz-Block ist rechenbar (13 Preflight-Dateien im Fenster, Luecke bei B256).
* Strang C **ruht**: die letzten Batches sind B-Batches -> die Kalender-Hochrechnung nennt
  einen Grund statt einer Zahl („die C-Hochrechnung ruht (kein Anteil aus der Plan-Regel)",
  R13bt-1) - kein Plan-Anteil als Rechengroesse.
* Die kanonischen Bilanzdateien fehlen fuer einzelne Batches (z. B. B264) - der R207-Zaehler
  weist das Fenster als lueckenhaft aus.
