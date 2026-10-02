# R13bl Teil 4 — Fehlerverhalten in zwei Fällen (NUR GEPRUEFT, nichts geaendert)

Stand: 02.10.2026, HEAD `186a1e6`. Harness laeuft (PID 7460), Zustand
`GATE_APPROVAL`, `batch=236`, `worker=None` — **es lief kein Batch**; alle Belege sind
abgeschlossene Laeufe. Zeilenangaben im Code gelten fuer diesen Commit.

Geprueft wurden die zwei vom Nutzer genannten Faelle. **Es wurde nichts umgesetzt.**

---

## Fall A — Worker-Abbruch durch API-/Gateway-Fehler (B235-Fortsetzung, Exit 1 nach 51 min)

### A1 Wie klassifiziert der Harness das, und was folgt danach?

| | |
|---|---|
| **Heutiges Verhalten** | Der Lauf endet mit `rc=1`; `killed_reason=null` und `alarms=[]` — also **kein** Kill durch eine Harness-Grenze. `worker.fortsetzung_pruefen` lehnt einen Anstoss ab, weil `rc != 0` (`worker.py:652-653`): Entscheidung `fortsetzung_grund="rc=1"`, `fortsetzung_uebertrag=false`, `fortsetzungen=[]`. Danach laeuft der **normale** Batch-Abschluss: Ghidra-Save (ok), Snapshot, Telegram „Batch beendet rc=1 … grenze=-", Push, **Review**. |
| **Beleg** | `runs/b235/result.json:5-7` (`rc=1`, `duration_s=3052.361`, `killed_reason=null`); `runs/b235/result.json` Felder `fortsetzung_grund: "rc=1"`, `fortsetzungen: []`; `logs/harness-2026-10-01T*.log` 20:15:36 „Kein Fortsetzungsanstoss | rc=1" und 20:16:08 „Batch beendet | rc=1 dauer=3052s grenze=- anfragen=22 kosten=$0.0401 modell=deepseek-flash[1m] (ok=True)"; `hx/worker.py:649-654` (`fortsetzung_pruefen`: Abbruchgrund -> `rc != 0` -> `stats.is_error()`) |
| **Luecke** | Die Entscheidung haengt **allein an `rc`**. Der Fehlertext wird nicht ausgewertet; ein Infrastruktur-Abbruch ist von einem inhaltlichen genau so wenig zu unterscheiden wie von einem beliebigen `rc=1`. |

### A2 Unterscheidet er Infrastruktur von einem inhaltlichen Abbruch?

| | |
|---|---|
| **Heutiges Verhalten** | **Nein — mechanisch gar nicht.** Es gibt keine Fehlerklasse „Netz/Gateway"; das dafuer vorgesehene Feld `api_errors` ist **leer**. Die einzige inhaltliche Spur ist der Antworttext: die synthetische Fehlermeldung landet als `antwort.md` und laeuft als „Bericht des Workers" weiter. **Der Reviewer** hat den Fehler im Freitext erkannt („Der Lauf endete nach 51 min mit einem API-Fehler am Gateway, also einem Infrastrukturfehler") — das ist die Bewertung des Modells, keine Messung des Harness. |
| **Beleg** | `runs/b235/antwort.md:1` enthaelt **genau** den Fehlertext („API Error: API returned an empty or malformed response (HTTP 200) … watchdog; 0 stream events received."); `runs/b235/stream.jsonl:28441` = dieselbe Zeile als synthetische Assistenten-Nachricht (`"model":"<synthetic>"`, `"stop_reason":"stop_sequence"`); `runs/b236/review.md:2` (Bewertung des Reviewers) |
| **Luecke** | Der Worker-„Bericht" enthaelt keine Arbeit, sondern die Fehlermeldung — der Reviewer muss sie als solche erkennen. Fehlt die Erkennung, sieht ein Infrastruktur-Abbruch wie ein schwacher Batch aus. |

### A3 Warum steht in `result.json` `api_errors: []`?

| | |
|---|---|
| **Heutiges Verhalten** | **Kein Parser-, Ordner- oder Fortsetzungsproblem.** Die Liste wird **nirgends gefuellt**: `streamjson.py:773` deklariert `self.api_errors: list[str] = []`, `worker.py:1382` kopiert sie nach `result.json` (`res.stats["api_errors"] = list(stats.api_errors)[:5]`) — ein `append` gibt es im ganzen Repo **nicht** (Grep ueber `harness/**`: nur diese zwei Fundstellen; in **allen** `runs/b*/result.json` von b001 bis b235 steht `"api_errors": []`). Die Fehlerzeile selbst liegt vollstaendig im Mitschnitt des laufenden Laufs (`stream.jsonl:28441`); der **erste** Lauf ist unversehrt als `lauf1/` daneben (R13bj), seine Dateien stehen im Feld `vorgaenger`. |
| **Beleg** | `hx/streamjson.py:773`, `hx/worker.py:1382`, Grep „api_errors" ueber `harness/**` (kein `.append`), `runs/b235/stream.jsonl:28441`, `runs/b235/lauf1/*` + `result.json -> stats.vorgaenger` (9 Dateien) |
| **Luecke** | **Totes Feld seit dem ersten Batch.** Es sieht wie eine Messung aus, ist aber immer `[]` — wer danach urteilt, haelt jeden Lauf fuer fehlerfrei. |

### A4 Was kam beim Nutzer an? (Nebenbeobachtung)

| | |
|---|---|
| **Heutiges Verhalten** | Waehrend des ganzen Fensters warnt der Harness wiederholt `Telegram haengt` (R13l-Zeitgrenze): **29-mal zwischen 20:00 und 20:15 UTC**, danach weiter bis 22:00. Ob die Batch-Ende-Meldung (20:16:08) und die Limit-Meldung ankamen, ist daraus **nicht belegbar** — es gibt keine Quittung im Protokoll. |
| **Beleg** | `logs/harness-2026-10-01T*.log`, Zeilen `WARN Telegram haengt` (20:00:15 … 21:59:48) |
| **Luecke** | Fuer „ist die Meldung rausgegangen?" fehlt ein Beleg (heute nur der Warnzaehler). |

---

## Fall B — Session-Limit des Reviewers (01.10., `review-verworfen-20261001-201654-v1.md`)

Die Datei liegt in **`runs/b236/`** — nach der Ordner-Konvention ist das das Review, das
**Batch 235** bewertet. Zeitstempel 01.10. 22:16:54 lokal = 20:16:54 UTC.

### B1 Wodurch wurde verworfen, und wird die Reset-Uhrzeit gelesen?

| | |
|---|---|
| **Heutiges Verhalten** | Der Reviewer-Lauf endet nach **2 s** mit `rc=1`, `modell=<synthetic>`, `limit=True`, `status=incomplete` (`probleme=DS_TOOLS fehlt; TELEGRAM_SUMMARY fehlt; …`). Zusaetzlich `ERROR REVIEWER-MODELL-ABWEICHUNG erwartet=claude-opus-5-5 gesehen=<synthetic>`. Die Rohantwort („You've hit your session limit · resets 11:40pm (Europe/Berlin)", 64 B) wird als `review-verworfen-…-v1.md` abgelegt. **Die Reset-Zeit wird gelesen und benutzt:** `protocol.looks_like_limit` erkennt die Meldung, `protocol.parse_limit_reset` liest die Form **ohne** „at" (`resets 11:40pm`, lokale Zeit) -> 21:40 UTC; der Zustand geht auf `LIMIT_WAIT` mit `limit_wait_until`. Der Harness setzt **von selbst** fort — genau zur Minute. |
| **Beleg** | `runs/b236/review-verworfen-20261001-201654-v1.md:1`; Log 20:16:54 „REVIEWER-MODELL-ABWEICHUNG" und „Review fertig | rc=1 dauer=2s modell=<synthetic> limit=True status=incomplete"; `hx/protocol.py:24-25` (`LIMIT_PATTERNS`, u. a. `you'?ve hit your`, `resets at`), `hx/protocol.py:52` (Muster `resets?\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am\|pm)?`); `hx/orchestrator.py:1929-1940` (`if res.limit_reached:` -> `limit_wait_ziel`, `st.LIMIT_WAIT`, Telegram-Text, `return`); `hx/orchestrator.py:1486-1497` (`limit_wait_ziel`); Log **21:40:17** „Limit-Wartezustand abgelaufen - Fortsetzung" |
| **Luecke** | Der Limit-Zweig steht **vor** `review_ok` (`orchestrator.py:1929` vs. `:1941`) — trotzdem entsteht zusaetzlich ein **„verworfen"**-Beleg. Dieselbe Antwort wird also als „Review verworfen" archiviert **und** als Wartezustand weitergefuehrt; wer nur die Verzeichnisliste liest, haelt es fuer einen inhaltlichen Fehlversuch. |

### B2 Wurde dasselbe Review nach dem Reset wiederholt — und zu welchem Batch?

| | |
|---|---|
| **Heutiges Verhalten** | **Ja, genau einmal, automatisch.** 21:40:17 Wartezustand abgelaufen -> 21:41:18 „Review-Verzeichnis" (`bewerteter_batch=235`, `freigabe_fuer=236`) -> 21:44:28 „Review fertig | rc=0 dauer=182s modell=claude-opus-5-5 limit=False status=ok". Das gueltige Review liegt als `runs/b236/review.md` und beginnt mit „Die Fortsetzung von B235 (Lauf 2) hat nur TEIL 0 erledigt …". |
| **Beleg** | Log 21:40:17, 21:41:18, 21:44:28; `runs/b236/review.md:2`; mtime `runs/b236/review.md` = 01.10. 23:44:28 lokal |
| **Luecke** | Der zweite Lauf startet **sofort** nach Ablauf, ohne Streuung. Bei einem Limit, das in Stufen frei wird, kann das wieder ins Limit laufen (hier nicht passiert). |

### B3 Lief der Worker in der Zwischenzeit ohne Review weiter?

| | |
|---|---|
| **Heutiges Verhalten** | **Nein.** Zwischen 20:16:54 und 21:40:17 steht im Protokoll **keine** Zeile ausser `WARN Telegram haengt` — kein Batchstart, kein Worker. B236 begann erst 21:51:37 („Git-Checkpoint", „Queue zugestellt", „Worker-Umgebung geprueft"), also **nach** dem gueltigen Review (21:44:28). |
| **Beleg** | Log-Auszug 20:16:54 … 21:51:37 (dazwischen nur Telegram-Warnungen); `runs/b236/auftrag.md` mtime 01.10. 23:51:37 lokal = 21:51:37 UTC |
| **Luecke** | Keine. Die Sperre greift: ohne gueltiges Review kein Workerstart. |

### B4 Gilt das Gleiche fuer Waechter und Aussensicht?

| | |
|---|---|
| **„Waechter" (Watchdog)** | **Es gibt ihn nicht** — nur zwei Code-Reste: `hx/reviewer.py:349` kennt einen Prompt-Typ `"watchdog"` („WATCHDOG-CHECK. Bewerte nur den Zwischenstand …"), `orchestrator.review_ok` einen Zweig „Watchdog-Review: nur die Entscheidung" (`orchestrator.py:1971`) — **kein Aufrufer** (Grep `watchdog` ueber `harness/**`: nur diese Stellen). `orchestrator.py:3` sagt „Kein Watchdog in diesem Schritt (Entscheidung R4)", `streamjson.py:1315` nennt das Signal „fuer den Watchdog (Spaeter)". `hx/watch.py` ist reine Anzeige **ohne Modellaufruf** und kann kein Kontingent-Limit treffen. **Antwort: fuer den Waechter gilt nichts, weil er nicht laeuft.** |
| **Aussensicht** | **Anderer Weg, schwächer abgesichert.** Sie laeuft nicht ueber `do_review`, sondern ueber `aussensicht.run`; es gibt **keinen** `limit_reached`-Zweig und **keinen** `LIMIT_WAIT`. Eine Limit-Antwort gilt als „nicht gelaufen" (`aussensicht.gelaufen(res)` = `rc == 0` **und** Antwortblock), und laut R13aq wird der Lauf **beim naechsten Batch-Ende** genau einmal wiederholt — **nicht** zur Reset-Zeit. |
| **Beleg** | `hx/aussensicht.py::gelaufen` (rc + Antwortblock), `hx/orchestrator.py::_do_aussensicht`, `harness.toml [meta]`; R13aq (30.09.): `docs/_r13aq_belege.md` — Anlass war `error_max_turns`, dieselbe Bauform (rc/Block statt Limit-Uhr). Erfolgreiche Gegenprobe: Log 02.10. 00:00:38 „Aussensicht beendet | batch=236 befunde=7 … runden=41" |
| **Luecke** | Die Aussensicht **liest die Reset-Uhrzeit nicht**. Faellt sie ins Limit, verliert sie einen Lauf und wartet bis zum naechsten Batch-Ende (Minuten bis Stunden) — bei einem 3er-Takt praktisch bis in den naechsten Batch. |

---

## Vorschlaege (nur Vorschlaege, **keine** Umsetzung)

**Fall A**

1. **`api_errors` wirklich fuellen — Aufwand klein (~30 min).** In `streamjson` beim
   Einlesen einer Assistenten-Nachricht mit `model == "<synthetic>"` **oder** Textbeginn
   `API Error:` einen gekuerzten Eintrag anhaengen; dazu eine Faktenzeile
   `- API-FEHLER: …` in `harness-facts.md`. Wirkung: der Fehler ist nach dem Lauf
   maschinell belegbar, der Reviewer muss ihn nicht aus Prosa erraten.
2. **Infrastruktur-Abbruch als eigene Klasse — Aufwand mittel (~2 h, braucht eine
   Entscheidung).** Ein Feld `infra_abbruch` (rc!=0 **und** synthetische Antwort);
   Folge: **kein** normaler Batch-Abschluss, stattdessen Telegram „Lauf abgebrochen
   (Infrastruktur) — wird nach N Minuten einmal wiederholt" und Wiedervorlage statt
   Review. Kostet Zeit und braucht eine Grenze, deshalb nur Vorschlag.

**Fall B**

1. **Wartezustand nicht als „verworfen" ablegen — Aufwand klein (~20 min).** Bei
   `limit_reached` die Rohantwort als `review-limit-<stempel>.md` ablegen (statt
   `review-verworfen-…`); die Meldung an den Nutzer nennt dann „Limit — ich wiederhole zur
   Reset-Zeit" statt „Review verworfen". Wirkung: die Beleglage sagt die Wahrheit.
2. **Aussensicht an dieselbe Uhr haengen — Aufwand klein-mittel (~45 min).** In
   `aussensicht.run` `limit_reached` auswerten und wie beim Review `LIMIT_WAIT` mit der
   Reset-Zeit setzen; die Wiederholung beim naechsten Batch-Ende bleibt als Rueckfall.
