# R13ak-Belege (2026-09-29): Postfach — Antworten lesen, Doppelzustellung vermeiden

Auftrag: zwei Fixes aus der Postfach-Prüfung (R13ak) —
(1) `_RE_ANTWORT` toleranter machen (auch „zurückgestellt", auch „für B213 abgelehnt …,
für B216 übernommen" — maßgeblich ist das letzte Verdikt der Zeile), danach **M209-3b** und
**M212-1** im Register nachtragen; (2) nach einem **verworfenen Gate** schon beantwortete
Aussensicht-Nachrichten beim erneuten Zustellen mit einem Vermerk versehen statt sie als neu
vorzulegen. Volle Reihe, Commit.

---

## 0. Anlass (gemessen, nur lesend)

`_RE_ANTWORT` verlangte das Verdikt **direkt** hinter dem Doppelpunkt. Zwei Antworten des
Reviewers fielen deshalb durch, obwohl sie im Review standen:

| Stelle | Zeile | Wirkung |
|---|---|---|
| `runs/b211/review.md:15` | `M209-3b: zurückgestellt (Nutzer), spätestens B216` | Befund blieb `offen` |
| `runs/b213/review.md:11` | `M212-1: für B213 abgelehnt (Werkzeug vor Serie), für B216 übernommen (SOLL-KOEPFE > 0, Liste aus B213)` | Befund blieb `offen` |

Folge: beide standen in `state/meta_befunde.json` als `offen` (`antwort_batch: None`),
wurden nicht mehr vorgelegt (der Queue-Block liefert nur neue Nachrichten; ein „offen"-Block
für Reviewer-Befunde gibt es nicht) und erschienen auch nicht in `/fragen`
(`hx/fragen.py` nimmt nur `empfaenger == "Nutzer"`). Sichtbar waren sie nur als Zahl in der
Quote: `Aussensicht: 40 Befunde, davon 34 uebernommen, 0 abgelehnt, 6 offen`.

Zweitens: ein **verworfenes Gate** lässt seine `/claude`-Nachrichten liegen (R13u,
`hx/orchestrator.py::discard_gate`). Die Antwort steht aber schon im Register
(`aussensicht.antworten_uebernehmen` läuft **vor** der Gate-Entscheidung). Belegt am
28.09.2026: `logs/harness-2026-09-28T204643+0000.log` → `20:50:59 „Verworfener Auftrag:
/claude-Nachrichten bleiben liegen", anzahl 10` + `„Auftrag verworfen (Review angefordert)",
batch 211`; dieselben neun Befundkennungen (`M209-1`, `M209-2`, `M209-3b`, `M209-4`,
`M210-1`…`M210-5`) stehen danach in **zwei** Review-Prompts (`logs/review-prompt-2026-09-28
T203852+0000.md` und `…T205132+0000.md`), beide ohne „ZWEITER VERSUCH", also zwei echte
Reviews. Das war eine Doppelzustellung bereits verarbeiteter Befunde.

---

## 1. Fix 1 — tolerantes Antwortmuster (`hx/aussensicht.py`)

* `_RE_ANTWORT` liest jetzt `M<ddd>-<n>[a-z]?` **plus den Rest der Zeile**
  (`(?P<rest>[^\n]*)`); `_RE_VERDIKT` sucht darin alle Verdikte
  (`uebernommen|übernommen|abgelehnt|erledigt|verworfen|offen|zurueckgestellt|zurückgestellt`)
  und **das letzte gewinnt**. Ohne Verdikt gilt die Zeile **nicht** als Antwort — sonst
  würde jede Prosa-Erwähnung („siehe M212-1") einen Befund stillschweigend zuklappen.
* Umlautschreibweise wird vereinheitlicht („übernommen" → `uebernommen`,
  „zurückgestellt" → `zurueckgestellt`); gespeichert wird das Wort des Reviewers.
* `klasse()` normalisiert zusätzlich Umlaute, und `zurueckgestellt` zählt in die Klasse
  **`uebernommen`** — es ist eine Antwort (der Reviewer nimmt den Befund an und schiebt ihn),
  keine Absage und schon gar nicht „offen". Das Wort selbst bleibt im Register stehen; die
  Quote bleibt damit dreiteilig (R13z: `n uebernommen, a abgelehnt, o offen`).
* Neu: `kennung_aus_text(text)` findet `M214-1` im Text einer Aussensicht-Nachricht
  (`Aussensicht Batch 214 - Befund M214-1 (Gewicht hoch):`) — gebraucht von Fix 2.

### Nachtrag im Register (`docs/_r13ak_nachtrag.py`, Probelauf ohne `--schreiben`)

```
M209-3b (Bewertung Batch 210)  harness\runs\b211\review.md:15
  vorher : status='offen'  antwort_batch=None
  nachher: status='zurueckgestellt'  antwort_batch=210
M212-1  (Bewertung Batch 212)  harness\runs\b213\review.md:11
  vorher : status='offen'  antwort_batch=None
  nachher: status='uebernommen'  antwort_batch=212

Quote vorher : Aussensicht: 40 Befunde, davon 34 uebernommen, 0 abgelehnt, 6 offen
Quote nachher: Aussensicht: 40 Befunde, davon 36 uebernommen, 0 abgelehnt, 4 offen
Offen nachher: M208-5, M209-3a, M213-4a, M214-5a      (alles Nutzer-Posten)
```

`batch` ist der **bewertete** Batch (Review zu Batch N liegt in `runs/b<N+1>/`), genau wie
ihn der Harness beim Review übergibt — so steht z. B. bei `M209-1` schon `antwort_batch 210`.
Das Register behielt beim Schreiben seine anderen Schlüssel (`verworfen`, `tiefenprobe` mit
dem Rotationsstand der Tiefenprobe) — geprüft.

## 2. Fix 2 — Vermerk statt „neu" (`hx/queue.py`, `hx/orchestrator.py`)

* `queue.deliver_block(root, target, delivered_ids, vermerke=None)`: `vermerke` ist eine
  Zuordnung `nachricht-id -> Zusatz` (die Queue kennt das Register nicht, der Aufrufer
  schon). Der Zusatz steht **in der ersten Zeile** des Eintrags — unter einem mehrzeiligen
  Befundtext (Beleg/Aussage/Empfehlung) würde er sonst nicht auffallen.
* `orchestrator._queue_vermerke("claude")`: liest das Register, nimmt nur Nachrichten mit
  `source: aussensicht`, holt die Kennung über `aussensicht.kennung_aus_text` und setzt
  `(bereits beantwortet im verworfenen Review: <Verdikt>)`, sobald der Eintrag nicht mehr
  die Klasse `offen` hat. Wird etwas vermerkt, steht im Block zusätzlich eine Hinweiszeile
  (`… sie werden NICHT erneut beantwortet; der Vermerk nennt das Verdikt.`).
* Nur `target == "claude"` wird vermerkt; `/ds`-Nachrichten bleiben unberührt.

## 3. Tests

`harness/tests/test_r13ak_fixes.py` — **19 Tests**:

| Klasse | was geprüft wird |
|---|---|
| `TestTolerantesAntwortmuster` | beide **echten** Zeilen (wortgleich im Test und in der Datei, mit Zeilennummer), letztes Verdikt gewinnt, `zurueckgestellt` zählt nicht als offen, Quote bleibt dreiteilig, Prosa ohne Verdikt ändert nichts, `abgelehnt`/`offen` bleiben wie sie sind, Kennung aus dem Nachrichtentext, Kurzform gilt weiter für geteilte Befunde |
| `TestVermerkImPostfach` | Vermerk bei beantwortetem Befund (in der ersten Zeile des Eintrags), `zurueckgestellt` mit seinem Wort, kein Vermerk bei `offen`/unbekannter Kennung/`source: telegram`, Hinweiszeile nur wenn vermerkt, leere Queue bleibt leer, gemischte Queue (aussensicht + telegram) |
| `TestZustellungAmEchtenFall` | der 28.09.-Fall: neun beantwortete Befunde ergeben neun Vermerke (vorher wären sie als neu vorgelegt worden) |

Zusätzlich re-gelaufen (Register/Queue berührt): `test_r13z` 24, `test_r13aa` 33,
`test_r13y` 27, `test_r13w` 45, `test_r13ac3` 16, `test_units` 30, `test_r10` 23,
`test_r13b` 18, `test_r13u` 4 — alle OK.

## 4. Was NICHT geprüft ist / bewusste Entscheidungen

* **`zurueckgestellt` zählt in der Quote als „uebernommen"** (kein vierter Topf). Die Quote
  ist seit R13z mit ihrer Form `n uebernommen, a abgelehnt, o offen` festgelegt (Tests,
  Doku, Telegram). Ein eigener Topf „zurückgestellt" wäre eine Nutzerentscheidung — sichtbar
  bleibt das Wort im Register (`status`) und im Vermerk des Postfachs.
* **„Letztes Verdikt gewinnt"** ist gewollt, kann aber von einer Verneinung im späteren
  Satzteil getäuscht werden („M212-1: abgelehnt, weil die Liste nicht übernommen wurde"
  → läse `uebernommen`). Gemessen kommt diese Form bisher nicht vor; die Regel steht als
  Kommentar an `_RE_ANTWORT`.
* Der Nachtrag ist eine **Aktion am lebenden Register** (`state/` ist per
  `harness/.gitignore:3` nicht versioniert); er ist über `docs/_r13ak_nachtrag.py`
  wiederholbar. Während des Schreibens lief der Harness (nur `watch` und ein pausierter
  `run` in `GATE_APPROVAL`) — der Schreibvorgang ist atomar und behält die übrigen
  Registerschlüssel.
