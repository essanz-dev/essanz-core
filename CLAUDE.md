# essanz-core - Hinweise fuer Claude Code

Oeffentliches Repo (AGPL-3.0). Liest eine Portfolio-Performance-Datei (`.portfolio`, binaeres PPPBV1-Format) und erzeugt
eine Gesamtvermoegensbilanz als Dashboard-HTML. Alles laeuft lokal, ohne Netzwerkzugriff. Sprache der Doku, Kommentare und
Oberflaeche: Deutsch.

## Befehle
- Demo-Lauf: `python3 run_update.py beispiel.portfolio ausgabe --stichtag 2026-08-31` (benoetigt `pyyaml`)
- Mit eigener Konfiguration: `python3 run_update.py <datei.portfolio> ausgabe --config config.yaml [--anonym]`
- Rauchtest: `python3 tests/smoke_test.py` (prueft Kennzahlen gegen feste Referenzwerte, normal + anonym)
- Datenschutz-Check: `scripts/privacy_check.sh` (liest die private Denylist `../privacy-denylist.txt` ausserhalb des Repos)
- Beispiel-Datei neu erzeugen: `python3 tools/make_example_portfolio.py` (muss zu `config.example.yaml` passen)

## Architektur (Datenfluss)
`ppparse.py` (Binaerformat lesen) -> `analyze.py` (`Book`, `build()`: Bilanz, Kennzahlen, Monatsreihe, Rendite; liest Config)
-> `schwellen.py` (Ampeln, Glossar), `stress.py`, `forecast.py` -> `empfehlungen.py` (regelbasierte Texte)
-> `make_dashboard.py` (fuegt `template.html` + `dash.js` + Daten zu einer HTML-Datei zusammen) -> `run_update.py` (CLI).
`config.py` laedt `config.yaml` (Suchreihenfolge: `ESSANZ_CONFIG`, `./config.yaml`, mitgelieferte `config.example.yaml`).
`objektdaten.py` und `steuer.py` lesen nur aus der Config.

## Regeln
1. KEINE persoenlichen Daten im Repo: keine echten Namen, Adressen, Mieter, Darlehens-/Steuerwerte, keine echte
   `.portfolio`. Persoenliches gehoert in `config.yaml` (gitignored). Beispieldaten sind frei erfunden und muessen es bleiben.
2. Vor jedem Commit `scripts/privacy_check.sh` und `python3 tests/smoke_test.py` ausfuehren; beide muessen gruen sein.
3. Rechenlogik nur aendern, wenn der Smoke-Test bewusst angepasst und im Commit begruendet wird. Neue Kennzahlen
   brauchen einen Referenzwert im Smoke-Test.
4. `make_dashboard.py` baut das Daten-Objekt fuer die Seite aus einer expliziten Feldliste. Neue Felder aus `analyze.build()`
   muessen dort ergaenzt werden, sonst fehlen sie im Browser (`undefined`).
5. Vorlage `template.html`/`dash.js` ohne Netzwerk-Abhaengigkeiten halten (kein CDN, kein Tracking).
6. Nicht im offenen Kern: PDF-Bericht, Excel-Export, Pruefroutinen (moeglicher Bezahlteil). Nicht ohne Auftrag ergaenzen.
7. Externe Pull Requests nur mit Contributor-Vereinbarung (CLA) annehmen, solange Dual Licensing offen bleiben soll.
8. Nichts pushen oder veroeffentlichen ohne ausdrueckliche Freigabe des Gruenders.

## Hinweise
- Geldbetraege im Binaerformat: Betraege in Cent, Stueckzahlen und Kurse mit 1e8 skaliert; Datum als Epoch-Sekunden.
- Konten-Konvention: `Immobilie N: <Name>` (Objektkonto/-wertpapier), `Darlehenskonto N` (Darlehen zu Objekt N); Auszahlung
  = Umbuchung vom Darlehenskonto auf das Objektkonto, Annuitaet = Umbuchung zurueck.
- Das Unterverzeichnis `ausgabe/` und `config.yaml` sind gitignored.
