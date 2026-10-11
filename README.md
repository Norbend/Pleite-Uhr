# Pleite-Uhr

Schulden, Firmenpleiten, Gewerbe-Neugründungen, Gewerbeaufgaben und Arbeitslose in Deutschland – amtliche Daten, live hochgerechnet, mit Bundesland-Filter, Jahresvergleichen und Verlaufskurven.

Öffnen: `index.html` im Browser (keine Build-Schritte, keine Abhängigkeiten). Für GitHub Pages: Pages auf den Branch dieses Repos zeigen lassen.

## Funktionen

- **Live-Tafel:** Staatsschulden (Bund, Länder, Gemeinden, Sozialversicherung), Firmenpleiten, Gewerbe-Neugründungen und vollständige Gewerbeaufgaben im laufenden Jahr, sekundengenau hochgerechnet; Arbeitslose mit Quote und 25-Monats-Verlauf. Umschaltbar auf „Nur amtliche Werte“.
- **Regionsfilter:** Deutschland, eines der 16 Länder (Schulden von Land und Gemeinden) oder eine von 71 Großstädten ab 100.000 Einwohnern (amtliche Jahreswerte, ohne Hochrechnung und ohne Schuldenzähler).
- **Jahresvergleich:** beliebiger Monat, Quartal, „Januar bis aktueller Monat“ oder Gesamtjahr über 5, 10 oder alle Jahre ab 2014 – mit Veränderung zum Vorjahr und Tabellenansicht.
- **Verlaufskurven:** Monatswerte jedes Jahres übereinandergelegt; langfristiger Trend mit 12-Monats-Durchschnitt.
- **Ranking Länder / Großstädte:** je 100.000 Einwohner (bzw. Quote), mit Veränderung zum Vorjahreszeitraum; für Städte zusätzlich voraussichtliche Forderungen aus Insolvenzen je Einwohner.

## Daten

`scripts/fetch_data.py` lädt alle Reihen aus GENESIS-Online (Destatis) und schreibt `data/data.json` und `data/data.js`:

| Kennzahl | Tabelle | Stand beim letzten Abruf |
|---|---|---|
| Beantragte Unternehmensinsolvenzen, betroffene Beschäftigte | 52411-0010, 52411-0110 | Juli 2026 |
| Gewerbe-Neugründungen | 52311-0010, 52311-0110 | August 2026 |
| Vollständige Gewerbeaufgaben | 52311-0130 | August 2026 |
| Arbeitslose, Arbeitslosenquote (BA) | 13211-0002, 13211-0008 | September 2026 |
| Schulden beim nicht-öffentlichen Bereich | 71311-0001, 71311-0003 | 30.06.2026 |
| Bevölkerung | 12411-0010 | 31.12.2025 |
| Großstädte: Insolvenzen, Forderungen, Beschäftigte | Regionaldatenbank 52411-02-01-4 | 2024 |
| Großstädte: Gewerbe-Neuerrichtungen und -Aufgaben | Regionaldatenbank 52311-01-04-4 | 2025 |
| Großstädte: Arbeitslose, Quote (Jahresdurchschnitt) | Regionaldatenbank 13211-02-05-4 | 2025 |

Aktualisieren: `python3 scripts/fetch_data.py` (nur Standardbibliothek). Der Workflow `.github/workflows/update-data.yml` erledigt das täglich und committet nur bei neuen Daten. Die Städtedaten (Regionaldatenbank, `scripts/regionalstatistik.py`) werden wöchentlich oder mit `--cities` neu geladen; schlägt der Abruf fehl, bleibt der letzte Stand erhalten.

## Hochrechnung

- Flussgrößen: Monate ohne amtlichen Wert = Vorjahresmonat × Veränderung der letzten sechs amtlichen Monate ggü. Vorjahr; der laufende Monat zählt anteilig.
- Schulden: letzter Quartalsstand + Ø Zuwachs der letzten vier Quartale.
- Arbeitslose: keine Hochrechnung (Bestandsgröße).
