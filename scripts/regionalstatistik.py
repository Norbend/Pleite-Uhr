"""Abruf von Tabellen aus der Regionaldatenbank Deutschland (www.regionalstatistik.de).

Die Webservice-Schnittstelle verlangt dort ein Benutzerkonto. Die öffentliche
Weboberfläche liefert dieselben Tabellen ohne Anmeldung; dieses Modul bedient sie
wie ein Browser: Tabelle öffnen, Zeitraum wählen, Werte abrufen, CSV laden.
Nur Standardbibliothek.
"""
import csv
import http.cookiejar
import io
import re
import time
import urllib.parse
import urllib.request

BASE = "https://www.regionalstatistik.de/genesis/online"


class Session:
    def __init__(self):
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.opener.addheaders = [("User-Agent", "Mozilla/5.0 (Pleite-Uhr Datenabruf)")]

    def get(self, params, timeout=240):
        url = BASE + "?" + urllib.parse.urlencode(params, encoding="utf-8")
        for attempt in range(4):
            try:
                with self.opener.open(url, timeout=timeout) as r:
                    return r.read()
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(2 ** (attempt + 1))


def _levelid(html):
    m = re.search(r'name="levelid" value="(\d+)"', html)
    if not m:
        raise RuntimeError("levelid nicht gefunden – Seitenaufbau geändert?")
    return m.group(1)


def fetch_table(code, last_years=12, span=None):
    """Liefert die Tabelle als Liste von dicts (ffcsv-Format der Regionaldatenbank).

    last_years: die letzten N Zeitpunkte; span=(von, bis): Jahresbereich (für große Tabellen).
    """
    s = Session()
    html = s.get({"operation": "table", "code": code, "levelindex": 0, "levelid": 1}).decode("utf-8", "replace")
    lid = _levelid(html)
    common = {
        "operation": "abruftabelleBearbeiten", "levelindex": 0, "levelid": lid,
        "auswahloperation": "abruftabelleAuspraegungAuswaehlen",
        "auswahlverzeichnis": "ordnungsstruktur", "auswahlziel": "werteabruf",
        "code": code, "auswahltext": "",
    }
    # Zeitauswahl öffnen (Name des Buttons enthält die Position der Zeitdimension)
    tbtn = re.search(r'name="(auspraegungen\$\$\$\d+)" value="Zeit ausw', html)
    if tbtn and (last_years or span):
        z = s.get({**common, tbtn.group(1): "Zeit auswählen"}).decode("utf-8", "replace")
        zlid = _levelid(z)
        sel = ({"ziauswahl": "zeitspannen", "ZI_VON": span[0], "ZI_BIS": span[1]} if span
               else {"ziauswahl": "zeitscheiben", "ZI_ANZ_LETZTE": last_years})
        html = s.get({
            "levelindex": 1, "levelid": zlid, "operation": "abruftabelleAuspraegungAuswaehlen",
            "auswahlziel": "werteabruf", **sel, "auspraegungenWaehlen": "übernehmen",
        }).decode("utf-8", "replace")
        common["levelid"] = _levelid(html)
        m = re.search(r'name="levelindex" value="(\d+)"', html)
        common["levelindex"] = m.group(1) if m else 1
    res = s.get({**common, "werteabruf": "Werteabruf"}).decode("utf-8", "replace")
    m = re.search(r"ergebnistabelleDownload&amp;levelindex=(\d+)&amp;levelid=(\d+)", res)
    if not m:
        raise RuntimeError(f"{code}: kein Download-Link im Ergebnis")
    raw = s.get({"operation": "ergebnistabelleDownload", "levelindex": m.group(1),
                 "levelid": m.group(2), "option": "ffcsv"})
    text = raw.decode("iso-8859-1")
    return list(csv.DictReader(io.StringIO(text), delimiter=";"))


def number(v):
    """Wert aus der Regionaldatenbank: '-' = 0, '.'/'...'/'x' = fehlt."""
    v = (v or "").strip()
    if v in ("-",):
        return 0.0
    try:
        return float(v.replace(",", "."))
    except ValueError:
        return None


def fetch_years(code, first, last, chunk=4):
    """Große Tabellen blockweise abrufen und zusammenführen."""
    rows, errors = [], []
    for a in range(first, last + 1, chunk):
        try:
            rows += fetch_table(code, span=(a, min(last, a + chunk - 1)))
        except RuntimeError as exc:  # z. B. Jahre, die noch nicht veröffentlicht sind
            errors.append(str(exc))
    if not rows:
        raise RuntimeError("; ".join(errors) or f"{code}: keine Daten")
    return rows
