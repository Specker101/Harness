"""R13bd-Leerlaufprobe: welcher Verdachtsfall laeuft NACHWEISLICH leer durch?

Der Bauform-Audit (`_r13bd_audit.py`) nennt 24 Verdachtsfaelle. Die Bauform allein beweist
nichts - diese Probe entscheidet es, in DREI Modi, jeweils in einem eigenen Prozess:

  A  fenster-leer   die rollenden Fenster liefern nichts
                    (`stand.preflight_dateien`/`hybrid_verlauf`/`kernzahlen`/
                     `preflight_bahnabdeckung`/`durchsatz_zeilen` -> [], `hybrid_stillstand`
                     -> "", `bilanz.gesamt_block` -> [])
  B  datei-leer     die lebenden Dateien sind da, aber INHALT LEER (jeder Lesezugriff auf
                    Decomp/`state`/`runs`/`sessions`/`prompts`/`harness.toml` -> "")
  C  datei-weg      die lebenden Dateien sind VERSCHWUNDEN (`is_file` -> False, Lesen und
                    `glob`/`iterdir` liefern nichts) - der Fall "Pfad zieht weiter"

Urteil je Modus: GRUEN und dabei NICHT uebersprungen = der Test prueft in diesem Zustand
nichts. Ein Skip zaehlt NICHT als Fund (ein Skip ist sichtbar und steht jetzt mit Namen im
Beleg der vollen Reihe, R13bc). Rot zaehlt ebenfalls nicht (der Test greift hart zu).

Zusaetzlich: Zahl der Zusicherungen im Quelltext (0 = kann gar nichts pruefen).

Aufruf: python -u docs/_r13bd_leerlauf.py
Schreibt: docs/_r13bd_leerlauf.txt
"""

from __future__ import annotations

import ast
import subprocess
import sys
import time
from pathlib import Path

HIER = Path(__file__).resolve().parent
HARNESS = HIER.parent / "harness"
TESTS = HARNESS / "tests"
ZIEL = HIER / "_r13bd_leerlauf.txt"
MODI = ("normal", "A-fenster-leer", "B-datei-leer", "C-datei-weg", "E-format-geaendert")

KANDIDATEN = [
    ("test_r11_fixes", "TestTokenZaehlung", "test_ganze_datei_b159"),
    ("test_r13ac_fixes", "TestBatchArtPflichtzeilen", "test_echte_batches_211_und_212_sind_b"),
    ("test_r13ac_fixes", "TestGegenprobeEchteDaten",
     "test_startzeit_aus_result_json_stimmt_mit_dem_bericht"),
    ("test_r13ac_fixes", "TestTrendLogik", "test_r207_fenster_mit_luecke_wird_benannt"),
    ("test_r13ac_fixes", "TestTrendMitEchtenDateien",
     "test_die_kopie_stimmt_mit_dem_lebenden_repo"),
    ("test_r13ad_fixes", "TestNachruecklisteErkennung", "test_gegen_den_echten_b213_auftrag"),
    ("test_r13ad_fixes", "TestNachruecklisteErkennung",
     "test_gegen_die_echten_b211_b212_auftraege"),
    ("test_r13ae_fixes", "TestEchteDateien", "test_c_trend_endet_nicht_mehr_bei_b211"),
    ("test_r13ae_fixes", "TestEchteDateien", "test_die_kopie_stimmt_mit_dem_laufenden_repo"),
    ("test_r13af_fixes", "TestDokumentation", "test_bedienung_hat_den_abschnitt"),
    ("test_r13ah_fixes", "TestGemesseneKappungen",
     "test_b212_hat_gekappte_aufrufe_ohne_eigenes_timeout"),
    ("test_r13ah_fixes", "TestHybridStillstand",
     "test_fester_stand_loest_keinen_falschen_alarm_aus"),
    # Alte Fassung derselben Stelle (nur vorhanden, wenn die R13bd-Umstellung zurueckgenommen
    # ist). Fuer den Vorher/Nachher-Vergleich mit demselben Werkzeug steht sie in der Liste.
    ("test_r13ah_fixes", "TestHybridStillstand",
     "test_echte_dateien_loesen_keinen_falschen_alarm_aus"),
    ("test_r13aj_fixes", "TestEchterMitschnitt", "test_b212_grep_paar_traegt_parallel_zwei"),
    ("test_r13ak_fixes", "TestTolerantesAntwortmuster",
     "test_echte_zeilen_stehen_wirklich_so_im_repo"),
    ("test_r13aq_fixes", "TestGelaufen", "test_der_echte_meta_217_ist_das_beispiel"),
    ("test_r13aq_fixes", "TestZurKenntnis", "test_die_echte_zeile_aus_b217"),
    ("test_r13ar_fixes", "TestRunden", "test_echte_laeufe_und_num_turns_sind_verschieden"),
    ("test_r13az_fixes", "TestAnlassImRepo", "test_bericht_b221_zaehlt_null_prozent"),
    ("test_r13az_fixes", "TestAnlassImRepo", "test_bucket_d_klart_0x40000000"),
    ("test_r13az_fixes", "TestAnlassImRepo", "test_hybrid_plan_nennt_das_ziel"),
    ("test_r13az_fixes", "TestAnlassImRepo", "test_reviewer_gesteht_den_fehler_ein"),
    ("test_r13p_fixes", "TestReviewHistorie", "test_reviewer_darf_nur_lese_git"),
    ("test_r13x_fixes", "TestEchteBelege",
     "test_dokument_widerspruch_verliert_gegen_den_preflight"),
    ("test_r13x_fixes", "TestEchteBelege", "test_ohne_messung_kein_alter_wert"),
]

# Der Vorspann laeuft im Kindprozess VOR dem Laden des Testmoduls.
VORSPANN = r'''
import sys
from pathlib import Path
MODUS = "__MODUS__"
if MODUS != "normal":
    from hx import stand, aussensicht, bilanz
    if MODUS == "A-fenster-leer":
        GEMELDET = {}

        def _merker(name, ergebnis):
            def f(*a, **k):
                GEMELDET[name] = True
                return ergebnis
            return f

        stand.preflight_dateien = _merker("preflight_dateien", [])
        stand.hybrid_verlauf = _merker("hybrid_verlauf", [])
        stand.kernzahlen = _merker("kernzahlen", [])
        stand.preflight_bahnabdeckung = _merker("preflight_bahnabdeckung", [])
        stand.durchsatz_zeilen = _merker("durchsatz_zeilen", [])
        stand.preflight_zaehler_zeile = _merker("preflight_zaehler_zeile", "")
        aussensicht.hybrid_stillstand = _merker("hybrid_stillstand", "")
        aussensicht.hybrid_neuester_b = _merker("hybrid_neuester_b", None)
        bilanz.gesamt_block = _merker("gesamt_block", [])
    else:
        LEERDATEI = "__LEERDATEI__"
        # Modus E: die lebende Datei ist da, aber die gesuchte Zeile ist weg (Format geaendert).
        FORMAT_TEXT = ("=== PREFLIGHT (before) ===\n"
                       "Pruefung           Ergebnis                      Urteil\n"
                       "Bahnabdeckung      1/2 | Bloecke 3/4                 OK\n"
                       "=> BEFORE SAUBER\n")
        LIVE = ("g:/silent scope decomp", "g:/harness/harness/state",
                "g:/harness/harness/runs", "g:/harness/harness/sessions",
                "g:/harness/harness/prompts", "g:/harness/docs/bedienung.md")
        # `harness.toml` gehoert NICHT dazu: die Konfiguration ist keine Messdatei. Wird sie
        # mitgeleert, scheitert schon `load_config()` in `setUpClass`, und der Modus meldete
        # faelschlich "greift hart zu" (gemessen: TOMLDecodeError in Zeile 1).

        def ist_live(p):
            s = str(p).replace("\\", "/").lower()
            if "/tests/_tmp" in s or "/tests/fixtures/" in s:
                return False
            return any(s.startswith(x) for x in LIVE)

        ZUGRIFF = {}

        def merken(p):
            """Ein LEBENDER Zugriff ist passiert - nur dann sagt der Modus etwas aus."""
            if ist_live(p):
                ZUGRIFF[str(p).replace("\\", "/")[-60:]] = True
            return ist_live(p)

        _read_text = Path.read_text
        _read_bytes = Path.read_bytes
        _oeffnen_path = Path.open
        _ist_datei = Path.is_file
        _glob = Path.glob
        _iterdir = Path.iterdir
        _glob_orig = Path.glob
        _builtin_open = open

        def read_text(self, *a, **k):
            if merken(self):
                if MODUS == "B-datei-leer":
                    return ""
                if MODUS == "E-format-geaendert":
                    return FORMAT_TEXT
                raise FileNotFoundError(str(self))
            return _read_text(self, *a, **k)

        def read_bytes(self, *a, **k):
            if merken(self):
                if MODUS == "B-datei-leer":
                    return b""
                if MODUS == "E-format-geaendert":
                    return FORMAT_TEXT.encode("utf-8")
                raise FileNotFoundError(str(self))
            return _read_bytes(self, *a, **k)

        def oeffnen(self, *a, **k):
            if merken(self):
                if MODUS == "B-datei-leer":
                    return _builtin_open(LEERDATEI, "r", encoding="utf-8")
                if MODUS == "E-format-geaendert":
                    _p = Path(LEERDATEI + ".fmt")
                    _p.write_bytes(FORMAT_TEXT.encode("utf-8"))
                    return _builtin_open(_p, *a, **k)
                raise FileNotFoundError(str(self))
            return _oeffnen_path(self, *a, **k)

        def ist_datei(self, *a, **k):
            if merken(self):
                return MODUS != "C-datei-weg"
            return _ist_datei(self, *a, **k)

        def globen(self, muster, *a, **k):
            if merken(self):
                return iter(())
            return _glob(self, muster, *a, **k)

        def verzeichnis(self, *a, **k):
            if merken(self):
                return iter(())
            return _iterdir(self, *a, **k)

        def geb_open(file, *a, **k):
            if merken(file):
                if MODUS == "B-datei-leer":
                    return _builtin_open(LEERDATEI, "r", encoding="utf-8")
                if MODUS == "E-format-geaendert":
                    # Der angeforderte Modus bleibt erhalten: `shutil.copy2` liest BINAER,
                    # ein Text-Handle waere dort ein TypeError und wuerde den Modus
                    # faelschlich als "greift hart zu" melden.
                    _p = Path(LEERDATEI + ".fmt")
                    _p.write_bytes(FORMAT_TEXT.encode("utf-8"))
                    return _builtin_open(_p, *a, **k)
                raise FileNotFoundError(str(file))
            return _builtin_open(file, *a, **k)

        Path.read_text = read_text
        Path.read_bytes = read_bytes
        Path.open = oeffnen
        Path.is_file = ist_datei
        Path.glob = globen
        Path.iterdir = verzeichnis
        import builtins
        builtins.open = geb_open

        # ZUSAETZLICH auf der hx-Ebene einhaengen. Grund (gemessen): `hx.util.open_shared_read`
        # liest auf Windows ueber einen DATEIDESKRIPTOR (`_winapi.CreateFile` + `open(fd)`),
        # die `Path`-Patches greifen dort nicht - die Datei kam mit vollem Inhalt an, obwohl
        # der Modus "leer" aktiv war. Ausserdem importieren `hx.stand` und andere Module die
        # Leser direkt (`from .util import read_text`), ein Patch nur auf `hx.util` wuerde
        # dort nicht ankommen. Deshalb: jedes hx-Modul, das einen dieser Namen haelt.
        import importlib
        import pkgutil
        import hx as _hx
        for _m in pkgutil.iter_modules(_hx.__path__):
            importlib.import_module("hx." + _m.name)
        LESER = ("read_text", "read_bytes_shared", "read_text_erkannt", "open_shared_read",
                 "open_shared_read_bytes", "read_json")
        ORIGINALE = {}
        for _name, _mod in list(sys.modules.items()):
            if not _name.startswith("hx"):
                continue
            for _l in LESER:
                _f = getattr(_mod, _l, None)
                if callable(_f) and _l not in ORIGINALE:
                    ORIGINALE[_l] = _f

        def _leer(p, *a, **k):
            if MODUS == "B-datei-leer":
                return "" if not str(p).lower().endswith("bytes") else ""
            raise FileNotFoundError(str(p))

        def neuer_leser(name, original):
            def f(pfad, *a, **k):
                if not merken(pfad):
                    return original(pfad, *a, **k)
                if MODUS == "C-datei-weg":
                    raise FileNotFoundError(str(pfad))
                if name in ("read_bytes_shared", "open_shared_read_bytes"):
                    return b"" if MODUS == "B-datei-leer" else FORMAT_TEXT.encode("utf-8")
                if name == "read_text_erkannt":
                    return ("" if MODUS == "B-datei-leer" else FORMAT_TEXT), "utf-8"
                if name == "read_json":
                    return a[0] if a else k.get("default")
                if name.startswith("open_shared_read"):
                    _p = Path(LEERDATEI + ".fmt")
                    _p.write_bytes(("" if MODUS == "B-datei-leer"
                                    else FORMAT_TEXT).encode("utf-8"))
                    return _builtin_open(_p, *a, **k)
                return "" if MODUS == "B-datei-leer" else FORMAT_TEXT
            return f

        for _name, _mod in list(sys.modules.items()):
            if not _name.startswith("hx"):
                continue
            for _l in LESER:
                if callable(getattr(_mod, _l, None)) and _l in ORIGINALE:
                    setattr(_mod, _l, neuer_leser(_l, ORIGINALE[_l]))
'''


def _lauf(modul: str, klasse: str, test: str, modus: str,
          leerdatei: str) -> tuple[bool, bool, str, bool]:
    """(gruen, uebersprungen, Meldung, modus_angewendet)."""
    vor = VORSPANN.replace("__MODUS__", modus).replace("__LEERDATEI__", leerdatei)
    code = (
        "import sys, unittest\n"
        f"sys.path.insert(0, r'{HARNESS}')\n"
        f"sys.path.insert(0, r'{TESTS}')\n"
        + vor
        + f"\nimport {modul} as m\n"
        "\n"
        "class _R(unittest.TextTestResult):\n"
        "    def startTest(self, test):\n"
        "        # Das Merker-Diktat erst HIER leeren: Zugriffe aus `setUpClass` (die oft nur\n"
        "        # die Temp-Kopie aufbauen) wuerden den Modus sonst faelschlich als anwendbar\n"
        "        # melden. `setUp` laeuft NACH `startTest` und zaehlt damit mit.\n"
        "        import __main__\n"
        "        getattr(__main__, 'GEMELDET', {}).clear()\n"
        "        super().startTest(test)\n"
        "\n"
        f"s = unittest.TestLoader().loadTestsFromName('{klasse}.{test}', m)\n"
        "r = unittest.TextTestRunner(verbosity=0, resultclass=_R).run(s)\n"
        "print('SKIPS', len(r.skipped), 'RUNS', r.testsRun)\n"
        "print('GEMELDET', sorted(globals().get('GEMELDET', {}) or []))\n"
        "print('ZUGRIFF', len(globals().get('ZUGRIFF', {}) or {}))\n"
        "sys.exit(0 if r.wasSuccessful() else 1)\n"
    )
    p = subprocess.run([sys.executable, "-c", code], cwd=str(HARNESS),
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=420)
    text = (p.stdout or "") + (p.stderr or "")
    uebersprungen = "SKIPS 1" in text or "SKIPS 2" in text
    zeile = [z for z in text.splitlines() if z.startswith("GEMELDET")]
    angewendet = bool(zeile and zeile[0].strip() != "GEMELDET []")
    zz = [z for z in text.splitlines() if z.startswith("ZUGRIFF")]
    if zz and zz[0].strip() != "ZUGRIFF 0":
        angewendet = True
    rest = [z for z in text.splitlines()
            if z.startswith(("FAILED", "OK", "AssertionError", "KeyError", "TypeError",
                             "AttributeError", "ValueError", "FileNotFoundError"))]
    return p.returncode == 0, uebersprungen, (rest[-1][:80] if rest else f"rc={p.returncode}"), \
        angewendet


def _asserts(datei: str, klasse: str, test: str) -> int:
    p = TESTS / f"{datei}.py"
    baum = ast.parse(p.read_text(encoding="utf-8"))
    for cls in [k for k in ast.walk(baum) if isinstance(k, ast.ClassDef) and k.name == klasse]:
        for fn in [k for k in cls.body if isinstance(k, ast.FunctionDef) and k.name == test]:
            n = 0
            for k in ast.walk(fn):
                if isinstance(k, ast.Call):
                    f = k.func
                    if isinstance(f, ast.Attribute) and (f.attr.startswith("assert")
                                                         or f.attr in ("fail", "skipTest")):
                        n += 1
                    elif isinstance(f, ast.Name) and f.id == "assert":
                        n += 1
            return n
    return -1


def main() -> int:
    # Die Leerdatei liegt im WEGWERF-Verzeichnis der Tests (`tests/_tmp*` ist ignoriert), damit
    # ein Lauf im Repo keine unversionierten Dateien hinterlaesst.
    kratz = HARNESS / "tests" / "_tmp_r13bd"
    kratz.mkdir(parents=True, exist_ok=True)
    leer = kratz / "leer.txt"
    leer.write_text("", encoding="utf-8", newline="\n")     # Ziel fuer `open(...)` in Modus B
    zeilen = [f"R13bd-Leerlaufprobe {time.strftime('%Y-%m-%d %H:%M:%S')}",
              "Modi: normal | A-fenster-leer | B-datei-leer | C-datei-weg",
              "Urteil: GRUEN und nicht uebersprungen = der Test prueft in diesem Zustand "
              "nichts.", ""]
    funde: list[tuple[str, str]] = []
    for datei, klasse, test in KANDIDATEN:
        name = f"{datei}:{klasse}.{test}"
        a = _asserts(datei, klasse, test)
        zeilen.append(f"{name}   (Zusicherungen im Quelltext: {a})")
        for modus in MODI:
            gruen, uebersprungen, meldung, angewendet = _lauf(datei, klasse, test, modus, str(leer))
            if modus == "normal":
                marke = "OK" if gruen else f"ROT ({meldung})"
            elif not angewendet:
                marke = "Modus nicht anwendbar (kein lebender Zugriff im Test)"
            elif gruen and not uebersprungen:
                marke = "GRUEN OHNE SKIP   <-- prueft nichts"
                funde.append((name, modus))
            elif uebersprungen:
                marke = "uebersprungen (sichtbar, kein Fund)"
            else:
                marke = f"rot ({meldung}) - greift hart zu"
            zeilen.append(f"    {modus:16} {marke}")
        zeilen.append("")
    zeilen += [f"Funde (gruen durchgelaufen, obwohl die Quelle leer oder weg ist): {len(funde)}"]
    for name, modus in funde:
        zeilen.append(f"  - {name}   in Modus {modus}")
    text = "\n".join(zeilen) + "\n"
    ZIEL.write_text(text, encoding="utf-8", newline="\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
