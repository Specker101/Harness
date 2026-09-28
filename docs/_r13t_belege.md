# Belege R13t (2026-09-28) - R535, Punkt 4b, Punkt 3, Punkt 4, Punkt 6

Alles rein LESEND erzeugt: kein Ghidra-Schreibzugriff, kein MAME-Lauf, keine Aenderung im
Decomp-Repo (`git status --porcelain` dort ist leer, s. Punkt 4b).

## 1. R535 - URTEIL: FEHLALARM (Interpreter ist richtig), aber ein echter Port-Fund

**Datei:Zeile - der Originalwortlaut von R535.**
`g:\Silent Scope Decomp\analysis\port-batch206-rc-bit-und-paket-e-2026-09-28.md:209-232`
(§5), Kernsaetze: "GEMESSEN: `m114_matrix` rechnet `rD = rA + rB`, das Handbuch verlangt
`rD = rA + rB + CA`" / "die Probe `+ self.ca` machte **12 von 74** Koepfen rot
(**210977** Abweichungen …)" / "danach zurueckgenommen (wieder 74/1776/0)" /
"**`8005BF74` ist die Ausnahme:** sein `addc` folgt direkt auf das `subfc.` und ist
HARDWARE-TREU mit CA gebaut".

**Wie die Probe "12 von 74 rot" gebaut war.** Geaendert wurde **nur der Wortinterpreter**:
in `scripts/m114_matrix.py` wurde beim XO-10-Zweig (`addc`, Zeile 394-405) `+ self.ca` an
die Summe gehaengt; danach lief `vergl alle`, danach wurde die Aenderung
**zurueckgenommen** (74 Koepfe / 1776 Faelle / 0 Abweichungen). Die 12 roten Koepfe
(`80010E9C`, `8003C17C`, `80010A20`, `8000F7E4` (207287), `800159B0`, `800156CC`,
`800662E8`, `8005BC90`, `8000CE14`, `8003B808`, `8004721C`, `800564D4`) sind also
diejenigen Koepfe, in deren **Falldaten** das CA ueberhaupt wirkt - **kein** Defektbeweis.

**Wie Interpreter und Port heute rechnen.**
* Der **Interpreter** rechnet ISA-konform: `scripts/m114_matrix.py:394-405`
  (`elif xo == 10:  # addc / addc.`) `s = R[ra] + R[rb]; R[rt] = s & 0xFFFFFFFF;
  self.ca = 1 if s > 0xFFFFFFFF else 0` - das eingehende CA wird **nicht** addiert
  ✔. Sein **Kommentar** (Zeile 395-397) behauptet das Gegenteil (falsche ISA-Lesart).
* CA-**lesende** Formen (`adde` 138, `addze` 202, `addme` 234, `subfe` 136, `subfze` 200,
  `subfme` 232) sind im Interpreter **gar nicht** implementiert (grep leer); sie stehen nur
  in `XO_ARITH_ALLE` fuer die strenge Rc/OE-Ablehnung. In den 78 gruenen Koepfen kommen sie
  auch nicht vor: der Zensus (`tools/r13s_ca_zensus.py`) findet **nur `addc` und `subfc`**
  (34 CA-Formen), `addc`/`subfc` schreiben CA nur.
* **Port:** vier R535-Stellen spiegeln den Interpreter korrekt
  (`port/src/ckopf_leaves.cpp:2026`, `:2112`, `:2183`, `:2276` - "das eingehende CA bleibt
  unbeachtet"). **Eine** Stelle nicht: `port/src/ckopf_leaves.cpp:1977`
  `if (r0 >= r10) r0 += 1u;   // CA aus 'subfc'` - direkt danach `r0 += r10; // addc`.

**Das ist die Entscheidung (ROM-Dekodierung, `tools/r13s_ca_zensus.py --kopf 0x8005BF74`).**
```
+18  0x7CAA0011  subfc.  r5,r10,r0     (setzt CA und CR0)
+1C  0x90810040  stw
+20  0x7C005014  addc    r0,r0,r10     XO = (0x7C005014>>1)&0x3FF = 10 = addc, Rc = 0
```
An der strittigen Stelle steht also ein **`addc`**, kein `adde`. Fuer `addc` ist das
Addieren des eingehenden CA (`adde`-Semantik) **falsch** - der Port weicht dort von ISA
UND Interpreter ab. Der Vergleich sieht es nicht (±1 dreht in den Fallfaellen keine
Vergleichsrichtung um).

**Urteil.** R535 als Aussage "der Interpreter ist falsch" ist ein **FEHLALARM** (die
Annahme "addc addiert das eingehende CA" ist falsch; die Probe war die falsche Praemisse,
ihr Zuruecknehmen war richtig). **Echt** bleibt der kleine Port-Fund in `8005BF74`
(eine Zeile, `ckopf_leaves.cpp:1977`). Vorschlag: eigener kleiner Posten mit Rotprobe
(CA=1 an dieser Stelle) statt eines Interpreter-Batches; der Kommentar in
`m114_matrix.py:395-397` ist zu berichtigen.

**Laeuft gerade ein Batch zu R535?** Nein. Der Harness stand auf `REVIEW_DUE`, Batch 206,
`gate: None`; `runs/b207` existiert nicht, und `R535` kommt **0x** in
`runs/b206/auftrag.md` vor. Die Korrektur wurde als `/ds`-Nachricht
(`harness/inbox/ds/20260928_002842_0000_7F4DFA95ED1D.md`) **und** als `/claude`-Nachricht
(`..._80203C3143AD.md`) in die Queue gelegt - die Reviewer-Nachricht erreicht den Reviewer
vor der B207-Instruktion, die als naechstes ansteht.

## 2. (Punkt 4b) ausgefuehrt / gebaut / verifiziert mit Rumpf-Fenstern

Werkzeug `tools/r13t_cov_relevanz.py` (neu), Beleg `docs/_r13t_beleg_4b.txt`. Quelle der
"Ist laeuft"-Aussage ist die **Coverage** (`capture/ppc_coverage.bin` + `ppc_cov_boot.bin`,
SSCOV1) im **Rumpf-Fenster** ab Eintritt bis zum ersten `blr` (max 0x400 B):

| Menge | Anzahl | davon ausgefuehrt |
|---|---|---|
| Funktionen im Inventar (`analysis/_m60_funcs.json`) | 2072 | **1086** (52,4 %) |
| gebaut (`m104_built.built_map()`) | 686 | **416** (60,6 %) |
| verifiziert (`scripts/c_kopf.py` `KOPF_DEF`) | 78 | **56** (71,8 %) |
| Paket-E-Wurzeln (`_m206/_c_paket_e.txt`) | 86 | **66** (76,7 %) |
| Paket-E-Blaetter (offen) | 17 | **12** (70,6 %) |

Feste Zeile in `/bilanz`: `Port-Relevanz: ausgefuehrt 1086 | davon gebaut 416 | davon
verifiziert 56 von 1086`. Zum Vergleich die strenge Fassung ("nur Eintrittsbyte"): 1066.
Die Mengen stimmen nicht ueberein, weil "die Aufnahme" (Coverage) nur das zeigt, was im
aufgezeichneten Lauf wirklich lief - 270 gebaute Koepfe liegen ausserhalb.

## 3. (Punkt 3) zwei getrennte Hochrechnungen

`/bilanz` zeigt jetzt **zwei** HYPOTHESIS-Zeilen (vorher eine):
`(Paket E, Arbeitsvorrat)` - 38 offene Koepfe / 2674 Insn ÷ Mittel = ca. 8 Batches; und
`(C gesamt, ABGELEITET)` - Quelle B196 §6.1 ("OFFEN: 1481 Koepfe / 94913 Insn",
`_m196/_plan_c.txt`) minus R207-Delta (686 - 591 = 95) = **1386 offene Koepfe**, Insn ueber
den damaligen Schnitt (64,1) fortgeschrieben = ~88,8k -> ca. 292 Batches bei +4,8 K/Batch.
Die Zeile nennt Quelle, Stand-Batch und Rechenweg selbst und markiert die Insn-Zahl als
Schaetzung. Doku: `docs/bedienung.md` §14c.

## 4. (Punkt 6/7 des Review-Prompts) FERTIG WENN, STREICHREIHENFOLGE, PLAN/IST

* `harness/prompts/reviewer.md:101-112` - "**Zwei Pflichtbloecke am Ende jeder
  `DS_INSTRUCTION`**": `FERTIG WENN:` (eine pruefbare Zeile) und
  `STREICHREIHENFOLGE:` (was bei Zeitknappheit zuerst entfaellt, in dieser Ordnung).
* `harness/prompts/reviewer.md:73-76` - der **Review prueft** das `FERTIG WENN` der
  bewerteten Instruktion und nennt das Ergebnis in der `TELEGRAM_SUMMARY`, und er prueft die
  verifizierte Menge gegen die PLAN/IST-Tafel (Median-Regel).
* `harness/prompts/reviewer.md:85-90` - Median-Regel (Ziel ≤ ca. 1,3 × Median der letzten
  Batches, Abweichung in einem Satz begruenden).
* `harness/hx/reviewer.py:375-384` - der Prompt-Block `=== PLAN/IST DER LETZTEN BATCHES
  …===` samt Median-Regel; gefuellt aus `harness/hx/orchestrator.py` (`"plan_ist":
  standmod.plan_ist_text(self.cfg)`).
* Echter Ausschnitt (von `reviewer.build_prompt` erzeugt, nicht nachgebaut):
  `docs/_r13t_beleg_4_prompt.txt`, Werkzeug `tools/r13t_prompt_probe.py`.

## 5. (Punkt 5/R13t) `/ds`-Nachrichten im Review-Prompt

`harness/hx/stand.py` (`ds_nachrichten`, `QUEUE_KOPF`), `harness/hx/orchestrator.py`
(Schluessel `"ds_queue"` in `review_context`), `harness/hx/reviewer.py` (Block
`=== NUTZER-NACHRICHTEN AN DEN WORKER DIESES BATCHES (/ds) ===` + Regel). Tests:
`harness/tests/test_r13t_fixes.py` (10 Tests). Doku: `docs/bedienung.md` §14d.
Realer Prompt-Ausschnitt: `docs/_r13t_beleg_4_prompt.txt` (B206 ohne Nachricht `(keine)`;
B207 mit den zwei jetzt in der Queue liegenden Nachrichten).

## 6. (Punkt 6) sechs Altposten - Nutzerentscheidung

Als **eine** `/ds`-Nachricht in die Queue gelegt:
`harness/inbox/ds/20260928_003247_0000_937B697C6608.md` (Text:
`docs/_r13t_ds_altposten.txt`). Inhalt: (1) R330 **ja**, (2) `M60_NO_EVID` **ja**,
(3) `NEG_IMM_LO` **nein (jetzt nicht)**, (4) `setup_mesa.ps1` bei EINER DLL **ja**,
(5) die Pins (R381) **ja**, (6) der "Later"-Abschnitt **ja** - mit dem Auftrag, den
Ankerposten (6) so als `ENTSCHIEDEN (Nutzer, 2026-09-28)` zu fuehren.

## Tests

`harness/tests/test_r13t_fixes.py` (neu, 10 Tests) + volle Suite:
**446 Tests, OK** (vorher 436).
