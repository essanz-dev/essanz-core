# Essanz — Gesamtvermögensbilanz aus Portfolio Performance

Essanz liest eine `.portfolio`-Datei aus [Portfolio Performance](https://www.portfolio-performance.info/)
und baut daraus ein Dashboard: Nettovermögen über die Zeit, eine Aufschlüsselung nach
Immobilien / Wertpapieren / Liquidität, Kennzahlen zu Beleihung und Kapitaldienstdeckung,
eine Fälligkeitsleiste für Anschlussfinanzierungen, ein paar Stresstests und eine
kurzfristige Liquiditätsvorschau. Alles läuft **lokal** — es gibt keinen Server, keinen
Upload, keine Cloud. Die einzige Eingabe ist die Datei, die Portfolio Performance ohnehin
schon auf deinem Rechner hat.

Dieses Repository ist der offene Kern von Essanz. Es rechnet mit den Kontoständen und
Transaktionen, die Portfolio Performance sowieso schon kennt. Aufwendigere Auswertungen
(ein bankfertiger PDF-Bericht, Excel-Export, automatische Prüfroutinen) sind bewusst nicht
Teil dieses Kerns — mehr dazu unten unter [Umfang](#umfang-dieses-kerns).

## Schnellstart

```bash
git clone https://github.com/essanz-dev/essanz-core.git
cd essanz-core
pip install pyyaml
python3 run_update.py beispiel.portfolio
```

Das erzeugt `ausgabe/Dashboard_<Datum>.html` mit frei erfundenen Beispieldaten (drei
fiktive Objekte, ein ETF-Depot) — zum Ausprobieren, ohne eigene Daten preiszugeben. Die
Datei einfach im Browser öffnen.

## Mit eigenen Daten

1. In Portfolio Performance: **Datei → Exportieren → Alle Buchungen …** bzw. die
   `.portfolio`-Datei selbst verwenden (Essanz liest das native Binärformat direkt, kein
   Export nötig).
2. `config.example.yaml` nach `config.yaml` kopieren und mit den eigenen Werten befüllen
   (siehe Kommentare in der Datei — Zinsbindungen, Objektstammdaten, Steuerwerte,
   Wechselkurse). `config.yaml` steht in `.gitignore` und wird nie versehentlich
   committet.
3. Ausführen:

   ```bash
   python3 run_update.py /pfad/zur/eigenen.portfolio --config config.yaml --stichtag 2026-08-31
   ```

Ohne `--stichtag` wird der heutige Tag verwendet. Mit `--anonym` entsteht zusätzlich eine
Fassung ohne Adressen und Mieternamen, gedacht zum Teilen außerhalb der eigenen Familie.

Kein Abschnitt in `config.yaml` ist Pflicht — ohne `steuer:` bleiben die Steuerspalten
leer, ohne `zinsbindungen:` fehlt die Fälligkeitsleiste, der Rest funktioniert trotzdem.

## Wie die Konfiguration funktioniert

Alle persönlichen Daten (Adressen, Mieternamen, Darlehenskonditionen, Steuerwerte) liegen
ausschließlich in `config.yaml` — nirgends im Code. `config.py` lädt diese Datei einmal
und cached sie; `objektdaten.py` und `steuer.py` lesen daraus, `analyze.py` liest beim
Import die allgemeinen Schwellwerte (Wechselkurse, welche Objekte selbstgenutzt sind,
P2P-/Krypto-Kontenlisten, Vergleichsindizes). Wer `essanz-core` klont und nur die eigene
`config.yaml` schreibt, bekommt sofort ein persönliches Dashboard, ohne eine Zeile Code
anzufassen. Wer mehr ändern will — andere Kennzahlen, andere Texte — findet unten, welche
Datei wofür zuständig ist.

## Aufbau

| Datei | Zuständigkeit |
|---|---|
| `ppparse.py` | Liest das binäre PPPBV1-Format von Portfolio Performance (Konten, Depots, Wertpapiere, Kursreihen, Buchungen). Rein generisch, keine Konfiguration nötig. |
| `config.py` | Lädt `config.yaml` (oder `config.example.yaml` als Fallback), stellt typisierte Zugriffsfunktionen bereit. |
| `objektdaten.py` | Objektstammdaten (Baujahr, Wohnfläche, Lage, Verkehrswertherleitung) je Objektnummer, aus der Config. |
| `steuer.py` | Steuerliche Kennzahlen je Objekt (AfA, Werbungskosten, Ergebnis) aus der Config. |
| `analyze.py` | Das Herzstück: baut aus Konten/Buchungen die monatliche Bilanz, berechnet Beleihung, DSCR, Eigenkapitalrendite, TWR/IRR, Stresstests, Fälligkeitsleiste usw. |
| `schwellen.py` | Schwellwerte, Ampelfarben, Glossar und Lesepfade für die fünf zentralen Kennzahlen (DSCR, Eigenkapitalquote, Beleihung Kapitalanlagen, freie Liquidität, Instandhaltungsrücklage). |
| `stress.py` | Stresstest-Szenarien (Zinsen, Mieten, Leerstand, Wertverfall). |
| `forecast.py` | Kurzfristige Liquiditätsvorschau anhand erkannter Daueraufträge. |
| `empfehlungen.py` | Regelbasierte Handlungsempfehlungen aus den Kennzahlen — generisch formuliert, ohne Objektnamen. Eigene, persönlichere Fassung ist einfach eine andere Datei mit derselben `build(data)`-Signatur. |
| `make_dashboard.py` | Setzt Template, Daten, Chart-JS (`dash.js`) und Empfehlungen zum fertigen HTML zusammen. |
| `run_update.py` | Kommandozeilen-Einstieg. |
| `tools/make_example_portfolio.py` | Erzeugt `beispiel.portfolio` — die fiktive Demo-Datei. Kein Teil der Bibliothek selbst. |

## Umfang dieses Kerns

Dieser Kern deckt das ab, was für ein ehrliches, selbst gehostetes Bild des eigenen
Gesamtvermögens nötig ist: Bilanz, Kennzahlen, Fälligkeiten, Stresstests, Vorschau. Nicht
enthalten sind aufwendigere Auswertungen wie ein bankfertiger PDF-Bericht, ein
Excel-Export oder automatische Prüfroutinen gegen die Buchungsdaten — diese sind als
möglicher kostenpflichtiger Zusatz für später vorgesehen, deshalb (noch) nicht Teil
dieses Repos. Der Kern bleibt unabhängig davon vollständig nutzbar und quelloffen.

## Lizenz

[GNU Affero General Public License v3.0](LICENSE) (AGPL-3.0). Kurz gesagt: frei nutzbar,
veränderbar und weiterverbreitbar — wer eine veränderte Fassung öffentlich anbietet (auch
als reiner Online-Dienst), muss den veränderten Quellcode ebenfalls unter der AGPL zur
Verfügung stellen.

## Datenschutz

Essanz liest deine Portfolio-Performance-Datei ausschließlich lokal auf deinem eigenen
Rechner. Es gibt keinen Netzwerkzugriff, keinen Upload, keine Telemetrie. `config.yaml`
mit den eigenen Daten verlässt deinen Rechner nur, wenn du sie selbst irgendwohin
kopierst.
