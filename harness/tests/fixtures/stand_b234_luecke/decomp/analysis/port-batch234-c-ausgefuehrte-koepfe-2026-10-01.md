# Batch 234 - Strang C (C-Batch A = ausgefuehrte Funktionen)

SOLL-KOEPFE: 5

## 0. Ausgangsstand (gueltiger Preflight B233, `analysis/_preflight_233.txt`)

    C Koepfe           110 / 6187 / 0 referenzgleich
    C verifiziert      82
    Bahnabdeckung      81/110 | Bloecke 596/736
    Formen der C-Koepfe 42 / 69 | Koepfe 110 | Faelle 20180 | Abweichungen 0
    Hybrid-Lauf        200000000 | 8000844C | Schranke | 2973/42599 | nein
    Hybrid-Funktionen nativ 6/94 | verglichen gleich: 6 | Host noetig: 2 | Gesamt 110/2087
    Profile reproduzierbar 110/110
    R391 Commit-Reihenfolge OK

**HAUPTMASS (Nutzerentscheidung, `hybrid-plan.md:387-392`):** der Anteil der
AUSGEFUEHRTEN Funktionen, die nativ laufen und referenzgleich geprueft sind
(**B/A**), plus der Gesamtstand (`Gesamt`). Die Schrittzahl ist NEBENZAHL.

---

## 1. VORHERSAGE (R391) - VOR jedem `port/`-Diff

**Zaehlerdefinitionen (R387).**

* `C Koepfe a / b / c` - `a` = Zahl der Eintraege in `c_kopf.PROFILES`
  (Registry-Kopf-Tafel `scripts/c_kopf.py`), `b` = Summe der Insn-Zahlen der
  Rumpfspannen, `c` = Zahl der Koepfe mit Abweichung in `c_kopf.py vergl alle`.
* `C verifiziert` - Zahl `verifiziert` aus `m210_bahnabdeckung.lauf()`.
* `Bahnabdeckung x/y | Bloecke` - `m210_bahnabdeckung.lauf()`.
* `Formen der C-Koepfe x/y` - `m227_formen.py gruen` (3 Welten), Beleg
  `_m234/_formen_gruen.txt`.
* `Hybrid-Lauf` - Rohausgabe FRONT `hybrid_lauf.exe --schritte 200000000
  --nativ-weiter`: Schritte | Halt-PC | Halt-Art | Wegmass (distinkte PCs auf
  der Karte / Kartenzellen) | Hauptschleife.
* `Hybrid-Funktionen nativ B/A` - **B** = Funktionen mit ausgefuehrtem PC, deren
  Registry-Kopf BETRETEN wurde, deren Aufrufe ALLE gleich waren, OHNE
  Host-Ruf und ohne Fehler; **A** = Funktionen mit mindestens einem
  ausgefuehrten PC; `Gesamt n/N` = Eintraege der LAUFZEIT-Registry
  (`port::ckopf::heads()`) / Funktionen des Programms (`_m225/_funktionen.txt`,
  N = 2087).
* `Profile reproduzierbar` - `scripts/m227_profile_live.py`, vergleicht jedes
  erzeugte Profil bytegleich mit `analysis/_m197`.

**Sollwerte.**

| Bilanzzeile | Ist (B233) | Soll (B234) | Begruendung |
|---|---|---|---|
| `C Koepfe` | 110 / 6187 / 0 | **115 / 6271 / 0** | +5 Koepfe, +84 Insn (11+13+18+19+23), 0 Abweichungen |
| `C verifiziert` | 82 | **87** | die 5 neuen Koepfe sind referenzgleich geprueft |
| `Bahnabdeckung` | 81/110 | **86/115** | je neuer Kopf eine gedeckte Bahn |
| `Formen der C-Koepfe` | 42 / 69 | **42 / 69 oder kleiner** | neue Formen nur, wenn ein Rumpf sie einbringt |
| `Hybrid-Lauf` (FRONT) | 200000000 \| 8000844C \| Schranke \| 2973/42599 \| nein | **unveraendert** (RISIKOZEILE: das Ersetzen kann die Zeitbasis verschieben) | gleiche Schranke, gleicher Halt |
| `Hybrid-Funktionen nativ` | 6/94 | **B >= 6 + n, A = 94** | n = Zahl der neuen Koepfe, die im FRONT-Lauf gleich verglichen und ersetzt werden (Soll n = 5; B wird je Kopf gemessen, nicht geraten) |
| `Gesamt` | 110/2087 | **115/2087** | +5 Registry-Eintraege |
| `Profile reproduzierbar` | 110/110 | **115/115** | jedes erzeugte Profil bytegleich |
| `Binary Quellen` | OK | **OK** | nach `port_build` juenger als alle Quellen |
| `R391 Commit-Reihenfolge` | OK | **OK** | dieser Commit steht VOR jedem `port/`-Diff |
| `analysis neue .py` | 0 | **0** | Werkzeuge unter `scripts/` |
