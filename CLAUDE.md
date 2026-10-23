# essanz-core - Hinweise fuer Claude Code

Oeffentliches Repo (AGPL-3.0). Liest eine Portfolio-Performance-Datei (`.portfolio`, binaeres PPPBV1-Format) und erzeugt
eine Gesamtvermoegensbilanz als Dashboard-HTML. Alles laeuft lokal, ohne Netzwerkzugriff. Sprache der Doku, Kommentare und
Oberflaeche: Deutsch.

## Befehle
- Demo-Lauf: `python3 run_update.py beispiel.portfolio ausgabe --stichtag 2026-08-31` (benoetigt `pyyaml`)
- Mit eigener Konfiguration: `python3 run_update.py <datei.portfolio> ausgabe --config config.yaml [--anonym]`
- Rauchtest: `python3 tests/smoke_test.py` (Kennzahlen gegen Referenzwerte: normal, anonym und mit fremden Kontennamen
  ueber `konten.objekte`; dazu Diagnose und Fehlerfaelle ohne Traceback)
- Datenschutz-Check: `scripts/privacy_check.sh` (liest die private Denylist `../privacy-denylist.txt` ausserhalb des Repos)
- Browser-App bauen: `python3 web/build.py`, ansehen mit `python3 -m http.server 8771 --directory web/dist`
  (Port 8765 ist lokal belegt). Neue Kern-Module in `web/build.py` KERN eintragen, der Rauchtest prueft das.
- Beispiel-Datei neu erzeugen: `python3 tools/make_example_portfolio.py` (muss zu `config.example.yaml` passen)

## Architektur (Datenfluss)
`ppparse.py` (Binaerformat lesen) -> `analyze.py` (`Book`, `build()`: Bilanz, Kennzahlen, Monatsreihe, Rendite; liest Config)
-> `schwellen.py` (Ampeln, Glossar), `stress.py`, `forecast.py` -> `empfehlungen.py` (regelbasierte Texte)
-> `diagnose.py` (Einordnung pruefen, `bericht()` liefert JSON fuer Terminal und Browser)
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
5. Vorlage `template.html`/`dash.js` und die Browser-App `web/` ohne Netzwerk-Abhaengigkeiten zur Laufzeit halten
   (kein CDN, kein Tracking; Pyodide wird von `web/build.py` mit ausgeliefert, CSP in `web/index.html`).
6. Nicht im offenen Kern: PDF-Bericht, Excel-Export, Pruefroutinen (moeglicher Bezahlteil). Nicht ohne Auftrag ergaenzen.
7. Externe Pull Requests nur mit Contributor-Vereinbarung (CLA) annehmen, solange Dual Licensing offen bleiben soll.
8. Nichts pushen oder veroeffentlichen ohne ausdrueckliche Freigabe des Gruenders.

## Hinweise
- Geldbetraege im Binaerformat: Betraege in Cent, Stueckzahlen und Kurse mit 1e8 skaliert; Datum als Epoch-Sekunden.
- Konten-Konvention (Voreinstellung in `config.DEFAULT_KONTEN`): `Immobilie N: <Name>` (Objektkonto/-wertpapier),
  `Darlehenskonto N` (Darlehen zu Objekt N), Depot mit Praefix `Immo`; Auszahlung = Umbuchung vom Darlehenskonto auf
  das Objektkonto, Annuitaet = Umbuchung zurueck. Abweichende Namen ordnet `konten:` in der Config zu (exakter Name
  vor Praefix). Keine Kontonamen mehr in `analyze.py` hartcodieren.
- Diagnose: `python3 run_update.py <datei> --diagnose [--config ...]` (Modul `diagnose.py`). Fehler fuer Nutzer:innen als
  `ppparse.FormatFehler` bzw. `config.ConfigFehler` werfen; `run_update.py` zeigt sie ohne Traceback (`--debug` mit).
- Das Unterverzeichnis `ausgabe/` und `config.yaml` sind gitignored.
