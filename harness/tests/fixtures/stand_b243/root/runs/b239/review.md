<TELEGRAM_SUMMARY>
Ergebnis: B238 (B-Batch 20) hat die SHARC-Antwortfolge aus dem Mitschnitt als Hybrid-Gerüst gebaut (`port/hybrid/sharc_folge.inc`, standardmäßig an).
- Der Handschlag ist ein Zähler/Toggle und hängt nicht vom Inhalt ab. Die Prüfsumme stimmt überein: Lauf `0x3CC9`, Mitschnitt C9/79 → `0x3CC9` (`_lauf900m_an.txt:36`, nachgerechnet).
- Gegenprobe „aus“ = 8001684C, bitgleich mit B237. Rotprobe ROT: 2 statt 132 Folgeschritte.
- Der echte Halt steht weiter bei **8001684C**. Er ist ein Selbstsprung im Fehlerzweig nach `FUN_8000be40` ≠ 0.

Bewertung: solide, ehrlich gezählt: B238 ist der 1. Batch im Sicherungsfenster, ohne Bewegung. Befunde:
(1) Zwei Preflight-Zahlen sind gesprungen und nicht erklärt: Profil-Lauf 0,6 → 605 s (Preflight 510 → 1118 s), „nicht vergleichbar“ 4 → 1876.
(2) Kriterium (2) wurde „mit benannter Abweichung erfüllt“ erklärt. Gemessen wurde aber eine PC-Menge, keine Funktionsmenge. Die Erklärung „Schatten-Pfade“ für die 97 PCs ist unbelegt.
(3) Der nächste Blocker ist nur gefolgert; der Rückgabecode von be40 wurde nicht gemessen. Der Mitschnitt enthält 8424 SHARC-Schreibzugriffe auf Offset 1–7, die nicht abgespielt werden.
(4) Zählfehler in `hybrid-plan.md:263`.
B-Anteil: 57819 von 900M Schritten nativ (vorher 47527).
FERTIG WENN erreicht: ja.

Kosten/Laufzeit: $0,19, 1h23m, 112 Anfragen.
Nächster Batch: B239 als C-Batch für den Rest von Paket E; SOLL 2 Blätter mit zusammen 545 Insn. Das liegt unter dem Median 4, weil nur noch 2 Blätter offen sind.
B-SCHRITT: 4/5 Boot bis Hauptschleife, B-Batch 20 (Zählung, keine Grenze – Nutzerentscheid 30.09.)
UEBERTRAG: keiner - alle Posten erledigt
ENTSCHIEDEN: B239 = C-Batch (Wechsel 1:1); B240 ist der letzte B-Batch im Sicherungsfenster.
ENTSCHIEDEN: In B240 wird der Rückgabecode von be40 gemessen. Außerdem: Abweichung vom Mitschnitt ab Index 132, Offsets 1–7, Prüfung (2) neu.
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: ghidra-read
program: /830d01.27p.main.bin
</DS_TOOLS>

## VERALLGEMEINERUNG

**F1 – Preflight-Zahlen springen ohne Erklärung.** Gemeint sind Profil-Lauf (m227) `0.6 s` → `604.9 s` (`_preflight_238.txt:21`) und „nicht vergleichbar“ `4` → `1876` (`:29`). Im Batch-Dokument steht dazu nur „Messwert (vorhergesagt)“ (`port-batch238-…md:313`).
(a) Fehlerklasse: Eine Zahl wird übernommen, ohne dass ihre Änderung gegen den Vorlauf erklärt wird.
(b) Verwandt sind alle Preflight-Zeilen, deren Wert sich gegen den vorigen gültigen Preflight ändert. Die Instruktion verlangt einen Zeilendiff `_preflight_238` → `_preflight_239`. Jede geänderte Zeile bekommt einen Erklärungssatz oder die Kennzeichnung UNERKLÄRT. Für die m227-Zeit verlangt sie eine eigene Ursachenmessung.
(c) „nicht vergleichbar 1876“ ist eine B-Größe und wird in B239 nur notiert, aber nicht diagnostiziert. Die Diagnose folgt in B240.

**F2 – Nutzerkriterium mit Ersatzmaß gemessen und Abweichung wegerklärt.** Kriterium (2) verlangt dieselbe Funktionsmenge. Gemessen wurde die Menge der distinkten PCs, und 97 PCs nur im Lauf mit Schatten gelten als „Schatten-Pfade“ (`port-batch238-…md:229-234`). Diese Erklärung ist nicht belegt.
(a) Fehlerklasse: Ein Kriterium aus einem Nutzerentscheid wird umformuliert zu „erfüllt mit Abweichung“.
(b) Verwandt sind alle Urteile zu Nutzerkriterien (R236-1 Halt, Prüfung (2)). Ab B240 lautet das Urteil nur „erfüllt“ oder „nicht erfüllt + Grund“. Die 97 PCs werden Funktionen zugeordnet und gegen die Körper der nativen Registry-Köpfe gelegt. Ein Hinweis: `8000CE14` ist ein Paket-E-Kopf (`_m237/_paket_e_nachher.txt:39`).
(c) In B239 (C-Batch) wird nichts davon geprüft.

**F3 – Ursache benannt, ohne den direkt messbaren Wert zu messen.** Der „nächste Blocker Bit-4-Sync“ ist nur STRONG INFERENCE, obwohl sich die Rückgabe von `FUN_8000be40` (Stufencode 2/3/5/7/8/10/11) direkt messen lässt.
(a) Fehlerklasse: Eine Schlussfolgerung steht dort, wo eine Messung möglich wäre.
(b) Prüfpunkt b: Die Folge spielt nur Offset 0 ab (13794 Bytes). Der Mitschnitt enthält zusätzlich **8424** `dsp_comm_sharc_w` auf Offset 1–7 (Grep über `capture/boot_20260829_194618.log`). Das Material für den zweiten Handschlag ist also vorhanden. B240 muss den Stufencode, die Stelle, ab der der Lauf vom Mitschnitt abweicht (ab Index 132), und die Offsets 1–7 auswerten.
(c) B239 baut keinen Teil davon.

**F4 – Zählfehler `hybrid-plan.md:263`.** Dort steht „(mit B238) drei“, richtig ist vier; Zeile 275 zählt korrekt. Das ist eine Einmal-Sache und wird in TEIL 0 korrigiert.

**Prüfpunkt a:**
- C: Zielzahl sind die referenzgleichen Köpfe, Stand 119/6913/0. B239 muss diese Zahl erhöhen.
- B: Der Anteil nativ wurde mit beiden Zahlen berichtet. Er stieg von 47527 auf 57819 von 900M; das kommt vom längeren Lauf, nicht von neuen Köpfen (Hybrid-Funktionen nativ weiter 7).

<DS_INSTRUCTION>
Batch 239 - Silent Scope Decomp

STAND UEBERNEHMEN:
- HEAD f8e4ebd, Arbeitsbaum sauber.
- Gültiger Preflight `analysis/_preflight_238.txt` (1118 s, 0 Befunde). C Köpfe 119/6913/0.
- Paket E offen laut `_m237/_paket_e_nachher.txt:126-135`: 8 Köpfe / 836 Insn. Davon sind 4 R215-Artefakte oder Haken, 4 echte Köpfe mit 777 Insn. Blätter: `80085824` (113) und `80056C60` (432, auch im Spielpfad).
- B-Stand: Das SHARC-Gerüst ist standardmäßig an. Echter Halt 8001684C (900M), Preflight-Schranke 8000EC3C.
- B238 war der 1. Batch im Sicherungsfenster R236-1; B240 ist der 2. und letzte.
- B239 ist ein **C-Batch (Strang C)**.
- SOLL-KOEPFE: 2 (Minimum). Höchstens 4, falls nach den Blättern weitere echte Paket-E-Köpfe zu Blättern werden.

ARBEITSWEISE:
- Startroutine nach AGENTS.md.
- Edit und Write unter `port/` und `scripts/` sind gesperrt, bis der Commit `B239: Vorhersage` steht. Er enthält die leere Ausgabe von `git status --porcelain port/ scripts/`.
- Preflight, `port_build` und `c_kopf.py mutalle` laufen blockierend mit `timeout=1800000`. Nicht im Hintergrund starten, keine Warteschleifen.
- Einstufen nach CONFIRMED / STRONG INFERENCE / HYPOTHESIS. Belege als `Datei:Zeile@commit`.
- Ein Kopf zählt nur mit `vergl` = 0 Abweichungen **und** `mut` = ROT.
- Fortschrittszahl ist „C Koepfe … referenzgleich“. „C Koepfe live“ und Paket-E-Insn sind **Ersatzzahlen**.
- Jede neu zitierte M- oder R-Kennung muss per Grep belegt sein.

TEIL 0 – Doku (nur `analysis/`):
- `hybrid-plan.md:263` korrigieren: mit B238 sind es **vier** B-Batches ohne Bewegung des echten Halts (B233/B235/B236/B238).
- Im Ankerkopf unter „Nächster Schritt“ den B240-Auftrag vormerken (wortgetreu):
  „B240 (letzter B-Batch im Sicherungsfenster R236-1): (a) Rückgabe von FUN_8000be40 mit Gerüst an messen (Stufencode); (b) PPC-Schreibfolge am Mailslot ab Index 132 gegen den Mitschnitt legen und die erste Abweichung benennen; (c) die 8424 dsp_comm_sharc_w auf Offset 1–7 im Mitschnitt auswerten; (d) Prüfung (2) neu: 97 nur-MIT-PCs Funktionen zuordnen, Urteil nur erfüllt/nicht erfüllt; (e) Preflight ‚nicht vergleichbar 4→1876‘ erklären.“
- Commit `B239: TEIL 0`.

TEIL 1 – Ursache Profil-Lauf 605 s (nur messen, vor der Vorhersage):
- In `_preflight_237.txt:21` stand `prof rc 0 0.6 s`, in `_preflight_238.txt:21` steht `604.9 s`.
- Herausfinden, wovon `c_kopf.py prof` (aufgerufen aus `scripts/m227_profile_live.py:85`) abhängt: Cache, Schlüssel, Binärzeit.
- Einmal von Hand mit Zeitmessung aufrufen. Ergebnis nach `_m239/_m227_ursache.txt`.
- Urteil, ob die Zeit **einmalig** (Cache nach `port/hybrid`-Änderung neu gebaut) oder **dauerhaft** ist.
- Nur wenn dauerhaft **und** die Ursache belegt ist: nach der Vorhersage beheben. Nachweis: dieselbe Profilzeile (`koepfe 119, gleich 119, abweichend 0`) bei kürzerer Zeit. Sonst nur dokumentieren.

VORHERSAGE (Commit `B239: Vorhersage`, vor jedem Diff unter `port/` oder `scripts/`):
- Je Bilanzzeile ein Sollwert mit Definition des Zählers.
- C Köpfe ≥ 121/…/0; Paket E offen neu.
- Erwartete Preflight-Dauer mit Begründung aus TEIL 1.

TEIL 2 – Köpfe (Blätter zuerst, kleinster zuerst):
- Paket E vorher frisch messen: `_m239/_paket_e_vorher.txt`.
- Erst `80085824`, dann `80056C60`. Je Kopf:
  - Ghidra-Dekompilat und Disassembly, `rumpf_end` gemessen;
  - Port in `port/src/ckopf_leaves.cpp` mit Registry-Eintrag, KOPF_DEF und MUT in `scripts/c_kopf.py`, Fall-Datei `_m197/_ck_*.case`;
  - Ausgaben `_m239/_vergl_<k>.txt` und `_m239/_mut_<k>.txt`.
- Recorder-Arität prüfen (B237: `n=1` statt 2 ergab 80 Falschabweichungen).
- Teilgeprüfte Köpfe mit gemessener Blockzahl ausweisen.
- Paket E nachher messen: `_m239/_paket_e_nachher.txt`.
- Werden echte Paket-E-Köpfe dadurch zu Blättern, die nächsten (kleinster zuerst) bis höchstens 4 Köpfe insgesamt.
- Die 4 R215-Artefakte oder Haken je mit einem Satz einordnen: was sie sind, und ob sie zu „Paket E fertig“ zählen. Beleg aus `c_kopf.py` bzw. R215-Quelle per Grep.

TEIL 3 – Live-Lage:
- Je neuem Kopf ein Grep auf KOPFWEIT im 200M-Lauf und im 900M-Lauf (Gerüst an, `--nativ-weiter`).
- Ergebnis: KOPFWEIT-Zeile oder „nicht ausgeführt“, jeweils mit Lauf-Datei.

BATCH-ENDE:
- Preflight genau einmal nach der letzten Änderung:
  `python -u scripts/preflight.py before *> analysis/_preflight_239.txt`
  Blockierend mit `timeout=1800000`.
- **Zeilendiff** `_preflight_238.txt` → `_preflight_239.txt` als `_m239/_preflight_diff.txt`. Jede geänderte Zeile bekommt im Batch-Dokument einen Erklärungssatz oder die Kennzeichnung **UNERKLÄRT**.
- Bilanz mit `--write-anchor`. Abweichungen von der Vorhersage erklären.
- Memory-Export, `git status` lesen, Commit.
- Ankerkopf `**Stand:** BATCH 239` mit Grep-Beleg, dazu `git status --porcelain` leer nach dem Commit.

FERTIG WENN: `80085824` und `80056C60` haben je `vergl` 0 und `mut` ROT (Dateien in `_m239/`) UND der Preflight zeigt C Köpfe ≥ 121/…/0 UND `_m239/_m227_ursache.txt` enthält das Urteil einmalig/dauerhaft UND `_m239/_preflight_diff.txt` hat für jede geänderte Zeile eine Erklärung UND genau ein gültiger Preflight + Bilanz liegen vor.

STREICHREIHENFOLGE: Gestrichen wird erst, wenn die Batch-Uhr die Umschaltschwelle erreicht. Unmittelbar davor kommt eine `Get-Date`-Zeile ins Dokument. Reihenfolge:
1. Köpfe über 2 hinaus.
2. Einordnung der R215-Artefakte.
3. TEIL 3 (Live-Lage).
NIE streichen: TEIL 0, TEIL 1 (Messung), Vorhersage, `80085824`, `80056C60`, Preflight, Preflight-Zeilendiff, Bilanz, Memory-Export, Ankerkopf.

## NACHRUECKLISTE
1. Doku. FERTIG WENN: `hybrid-plan.md` zählt vier stille B-Batches, und der Ankerkopf enthält den B240-Auftrag (a)–(e) wortgetreu (Grep-Beleg).
2. m227-Ursache. FERTIG WENN: `_m239/_m227_ursache.txt` liegt vor, mit Zeitmessung und dem Urteil einmalig/dauerhaft.
3. Vorhersage. FERTIG WENN: `B239: Vorhersage` steht vor dem ersten Diff unter `port/` oder `scripts/`, mit der leeren Porcelain-Ausgabe.
4. Zwei Blätter. FERTIG WENN: `80085824` und `80056C60` haben `vergl` 0 und `mut` ROT, und `_m239/_paket_e_nachher.txt` liegt vor.
5. Preflight, Diff und Bilanz. FERTIG WENN: `_preflight_239.txt` ist SAUBER, `_m239/_preflight_diff.txt` hat eine Erklärung je geänderter Zeile, und die Bilanz ist geschrieben.
6. Live-Lage und R215. FERTIG WENN: Je neuem Kopf gibt es eine KOPFWEIT-Zeile oder „nicht ausgeführt“ mit Lauf-Datei, und die 4 Artefakte sind je mit einem Satz eingeordnet.
</DS_INSTRUCTION>
