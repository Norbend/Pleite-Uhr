#!/usr/bin/env python3
"""Lädt die amtlichen Reihen für die Pleite-Uhr aus GENESIS-Online (Destatis)
und schreibt sie kompakt nach data/data.json und data/data.js.

Nur Standardbibliothek. Aufruf:  python3 scripts/fetch_data.py

Quelle ist die öffentliche REST-Schnittstelle hinter der GENESIS-Weboberfläche
(https://www-genesis.destatis.de/genesis/api/rest/tables/<code>/data), die ohne
Anmeldung JSON-stat liefert. Statuszeichen: "..." / "." = (noch) kein Wert,
"-" = genau null.
"""
import itertools
import json
import pathlib
import sys
import time
import urllib.request
from datetime import date

API = "https://www-genesis.destatis.de/genesis/api/rest/tables/{}/data"
FIRST_YEAR = 2014
ROOT = pathlib.Path(__file__).resolve().parent.parent

LAENDER = {
    "08": "Baden-Württemberg", "09": "Bayern", "11": "Berlin", "12": "Brandenburg",
    "04": "Bremen", "02": "Hamburg", "06": "Hessen", "13": "Mecklenburg-Vorpommern",
    "03": "Niedersachsen", "05": "Nordrhein-Westfalen", "07": "Rheinland-Pfalz",
    "10": "Saarland", "14": "Sachsen", "15": "Sachsen-Anhalt",
    "01": "Schleswig-Holstein", "16": "Thüringen",
}
KUERZEL = {
    "08": "BW", "09": "BY", "11": "BE", "12": "BB", "04": "HB", "02": "HH", "06": "HE",
    "13": "MV", "03": "NI", "05": "NW", "07": "RP", "10": "SL", "14": "SN", "15": "ST",
    "01": "SH", "16": "TH",
}


def fetch(code):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(API.format(code), timeout=180) as r:
                return json.load(r)
        except Exception as exc:  # Netzwerkfehler: kurz warten, erneut
            if attempt == 3:
                raise
            print(f"  {code}: {exc} – neuer Versuch", file=sys.stderr)
            time.sleep(2 ** (attempt + 1))


def rows(code):
    """Liefert (Dimensionen-dict, Wert) für jede Zelle; fehlende Werte als None."""
    raw = fetch(code)
    for ds in raw["data"]:
        ids, dims = ds["id"], ds["dimension"]
        cats = [
            [k for k, _ in sorted(dims[d]["category"]["index"].items(), key=lambda kv: kv[1])]
            for d in ids
        ]
        vals, status = ds["value"], ds.get("status") or []
        for i, combo in enumerate(itertools.product(*cats)):
            v = vals[i] if isinstance(vals, list) else vals.get(str(i))
            s = status[i] if isinstance(status, list) and i < len(status) else (
                status.get(str(i)) if isinstance(status, dict) else None)
            if s in ("...", ".", "x", "/"):
                v = None
            elif s == "-":
                v = 0
            yield dict(zip(ids, combo)), v


def month_key(k):
    return f"{k['JAHR']}-{k['MONAT'][-2:]}"


def monthly(code, content, region_dim, extra=None, sum_over=None):
    """dict region -> {YYYY-MM: Wert}. sum_over: Dimension, über die summiert wird."""
    out, missing = {}, set()
    for k, v in rows(code):
        if k["content"] != content + "$QMU":
            continue
        if extra and any(k.get(d) != val for d, val in extra.items()):
            continue
        if int(k["JAHR"]) < FIRST_YEAR:
            continue
        reg = k.get(region_dim, "DG")
        reg = "DG" if reg in ("DG", "%TOTAL%") else reg
        series = out.setdefault(reg, {})
        mk = month_key(k)
        if sum_over:
            if v is None:
                missing.add((reg, mk))
            series[mk] = (series.get(mk) or 0) + (v or 0)
        else:
            series[mk] = v
    # Summen mit fehlenden Teilwerten verwerfen
    for reg, mk in missing:
        out[reg][mk] = None
    return out


def to_array(series, months):
    return [None if series.get(m) is None else round(series[m], 1) for m in months]


def trim(months, all_series):
    """Schneidet Monate am Ende ab, für die keine Reihe einen Wert hat."""
    last = 0
    for s in all_series:
        for i, v in enumerate(s):
            if v is not None:
                last = max(last, i)
    return last + 1


def main():
    today = date.today()
    months = [f"{y}-{m:02d}" for y in range(FIRST_YEAR, today.year + 1) for m in range(1, 13)]
    regions = ["DG"] + sorted(LAENDER, key=lambda c: LAENDER[c])

    print("Insolvenzen …")
    ins_de = monthly("52411-0010", "ISV006", "DINSG")
    ins_l = monthly("52411-0110", "ISV006", "DLAND")
    emp_de = monthly("52411-0010", "ERW020", "DINSG")
    emp_l = monthly("52411-0110", "ERW020", "DLAND")
    print("Gewerbeanzeigen …")
    gru_de = monthly("52311-0010", "GEW009", "DINSG", sum_over="GEWNG1")
    gru_l = monthly("52311-0110", "GEW009", "DLAND", sum_over="GEWNG1")
    auf_l = monthly("52311-0130", "GEW010", "DLAND", sum_over="GEWAU1")
    print("Arbeitsmarkt …")
    alo_de = monthly("13211-0002", "ERW006", "DINSGF", extra={"DINSGF": "%TOTAL%"})
    alq_de = monthly("13211-0002", "ERW112", "DINSGF", extra={"DINSGF": "%TOTAL%"})
    alo_l = monthly("13211-0008", "ERW006", "DLAND")
    alq_l = monthly("13211-0008", "ERW112", "DLAND")

    # Vollständige Gewerbeaufgaben Deutschland = Summe der Länder (nur wenn alle 16 vorliegen)
    auf_de = {}
    for m in months:
        vals = [auf_l.get(c, {}).get(m) for c in LAENDER]
        auf_de[m] = None if any(v is None for v in vals) else sum(vals)

    print("Schulden …")
    debt = {"DG": {}}
    for k, v in rows("71311-0001"):
        if k["HSHAT1"] == k["SLDAT4"] == k["KRPGR8"] == "%TOTAL%" and v is not None:
            debt["DG"][k["STAGV"]] = v
    for k, v in rows("71311-0003"):
        if k["HSHAT1"] == k["SLDAT4"] == k["KRPGR9"] == "%TOTAL%" and v is not None:
            debt.setdefault(k["DLAND"], {})[k["STAGV"]] = v

    print("Bevölkerung …")
    pop = {}
    for k, v in rows("12411-0010"):
        if v is not None:
            pop.setdefault(k["DLAND"], {})[k["STAG"]] = v
    pop_latest = {c: s[max(s)] for c, s in pop.items()}
    pop_stag = max(max(s) for s in pop.values())
    pop_latest["DG"] = sum(pop_latest[c] for c in LAENDER)

    pick = lambda de, l, c: (de if c == "DG" else l).get(c, {})
    raw = {
        c: {
            "ins": pick(ins_de, ins_l, c),
            "emp": pick(emp_de, emp_l, c),
            "gru": pick(gru_de, gru_l, c),
            "auf": auf_de if c == "DG" else auf_l.get(c, {}),
            "alo": pick(alo_de, alo_l, c),
            "alq": pick(alq_de, alq_l, c),
        }
        for c in regions
    }
    n = trim(months, [to_array(s, months) for r in raw.values() for s in r.values()])
    months = months[:n]

    def last_month(key):
        return max(m for m in months if raw["DG"][key].get(m) is not None)

    data = {
        "generated": today.isoformat(),
        "start": months[0],
        "months": len(months),
        "regions": [
            {"code": c, "name": "Deutschland" if c == "DG" else LAENDER[c],
             "short": "DE" if c == "DG" else KUERZEL[c], "pop": pop_latest[c]}
            for c in regions
        ],
        "popStag": pop_stag,
        "latest": {k: last_month(k) for k in ("ins", "emp", "gru", "auf", "alo", "alq")},
        "series": {c: {k: to_array(s, months) for k, s in r.items()} for c, r in raw.items()},
        "debt": {c: sorted(debt[c].items()) for c in regions},
        "sources": {
            "ins": "Destatis, Statistik über beantragte Insolvenzverfahren (52411-0010, 52411-0110)",
            "gru": "Destatis, Gewerbeanzeigenstatistik – Neugründungen (52311-0010, 52311-0110)",
            "auf": "Destatis, Gewerbeanzeigenstatistik – vollständige Aufgaben (52311-0130)",
            "alo": "Bundesagentur für Arbeit via Destatis (13211-0002, 13211-0008)",
            "debt": "Destatis, Vierteljährliche Schuldenstatistik (71311-0001, 71311-0003)",
            "pop": "Destatis, Fortschreibung des Bevölkerungsstandes (12411-0010)",
        },
    }
    out = ROOT / "data"
    out.mkdir(exist_ok=True)
    old = out / "data.json"
    if old.exists():
        prev = json.loads(old.read_text(encoding="utf-8"))
        prev["generated"] = data["generated"]
        if prev == json.loads(json.dumps(data, ensure_ascii=False)):
            print("Keine neuen amtlichen Werte – Dateien bleiben unverändert.")
            return
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    (out / "data.json").write_text(text, encoding="utf-8")
    (out / "data.js").write_text("window.PLEITE_DATA=" + text + ";\n", encoding="utf-8")
    print(f"OK: {len(months)} Monate ({months[0]} … {months[-1]}), latest={data['latest']}")
    print(f"Schulden DE: {data['debt']['DG'][-1]}  ({len(text)//1024} KB)")


if __name__ == "__main__":
    main()
