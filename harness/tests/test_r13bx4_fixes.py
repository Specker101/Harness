"""Tests fuer R13bx-4: die Limit-Pruefung laeuft nur auf dem Abo-Pfad.

Nutzerbefund 2026-10-10: nach dem Neustart startete die Aussensicht auf DeepSeek
(`[DeepSeek-Takt]`, Takt 2 - R13bx-2 wirkt), brach aber nach ~2 min ab mit

    "Aussensicht B321 ist ins Session-Limit gelaufen (rc=0). Ich warte bis
     2026-10-10T00:36+00:00 (kein Zeitpunkt in der Meldung - stuendliche Pruefung)"

GEMESSEN (`runs/b321/meta.jsonl`): der Lauf war **fehlerfrei** (rc=0, `meta.err.txt` trug
nur die harmlose Zeile `[claude-code:unrecognized_model]`).  Ausgeloest hat es das Muster
`quota` aus `protocol.LIMIT_PATTERNS` - im **englischen Denktext** des Modells:

    Z2984 : "... the reason for lowering was to save weekly quota ..."
    Z11290: "... Weekly quota now 87%. Hmm - actually the header of this run says ..."
    Z14921: "... R314-2 (lower the takt to save quota). But now there's a NEWER ..."

Die anderen sechs Muster hatten 0 Treffer.  Das ist kein Zufall: die Aussensicht **soll**
ueber das Wochenkontingent reden (ihre haeufigsten Befunde M309-3b, M313-3, M317-1b zitieren
alle `logs/rate-limit.json`).  Jeder englische Satz mit "quota" haette den Harness wieder
fuer eine Stunde pausiert - und in der Zeit startet er keinen Batch.

REGEL (Nutzerentscheid 2026-10-10, "mach A"): ein Lauf auf DeepSeek kann das
**Claude-Abo**-Limit nicht erreichen - seine Umgebung traegt kein Abo-Token
(`envs.precheck(env, "aussensicht")` bricht sonst ab).  Die Pruefung entfaellt dort ganz.
Die Musterliste selbst bleibt unangetastet (Teil b wurde bewusst NICHT gemacht): auf dem
Abo-Pfad ist sie weiter scharf.

Alles im Attrappenbetrieb: kein Netz, keine API-Kosten.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import aussensicht                                          # noqa: E402

# Der echte Denktext aus B321 - die Zeile, die den Fehlalarm ausgeloest hat.
DENKEN_B321 = ('{"type":"assistant","message":{"content":[{"type":"thinking","thinking":'
               '"so the reason for lowering was to save weekly quota. Weekly quota now '
               '87%."}]}}')


class TestLimitNurBeimAbo(unittest.TestCase):
    def test_der_fall_aus_b321_ist_kein_limit_mehr(self):
        """Genau der Mitschnitt, der den Harness eine Stunde pausiert hat."""
        self.assertFalse(aussensicht.limit_erreicht("deepseek", DENKEN_B321,
                                                    "Aussensicht: 4 Befunde"))
        # Auf dem Abo bleibt dieselbe Zeile ein Treffer - die Musterliste ist unveraendert.
        self.assertTrue(aussensicht.limit_erreicht("abo", DENKEN_B321, ""))

    def test_deepseek_auch_bei_echtem_limittext_nicht(self):
        """Die Pruefung entfaellt ganz - nicht nur das eine Muster."""
        for text in ("Claude usage limit reached", "You've hit your limit",
                     "rate limit", "out of extra usage", "resets at 3pm",
                     "quota exceeded"):
            self.assertFalse(aussensicht.limit_erreicht("deepseek", text, ""), msg=text)

    def test_abo_erkennt_das_limit_weiter(self):
        for text in ("usage limit", "limit reached", "you've hit your", "rate limit",
                     "out of extra usage", "resets at", "quota"):
            self.assertTrue(aussensicht.limit_erreicht("abo", text, ""), msg=text)

    def test_abo_erkennt_das_limit_auch_im_text(self):
        """Der Text allein genuegt - so steht die Meldung oft nur unvollstaendig im Stream."""
        self.assertTrue(aussensicht.limit_erreicht("abo", "", "Your usage limit resets at 3pm"))

    def test_ohne_limitmeldung_bleibt_es_false(self):
        self.assertFalse(aussensicht.limit_erreicht("abo", "alles gut", "nichts"))
        self.assertFalse(aussensicht.limit_erreicht("abo", "", ""))

    def test_leerer_anbieter_gilt_als_abo(self):
        """Altbestand und Tests rufen ohne Anbieter - dann bleibt die Pruefung scharf."""
        self.assertTrue(aussensicht.limit_erreicht("", "usage limit", ""))


if __name__ == "__main__":
    unittest.main()
