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

1. Die `.portfolio`-Datei aus Portfolio Performance direkt verwenden, kein Export nötig.
   Essanz liest das Binärformat ohne Passwort. Ist die Datei als XML oder verschlüsselt
   gespeichert, in Portfolio Performance über **Datei → Speichern unter …** eine Kopie im
   Format „Binär“ ohne Passwort anlegen. Essanz schreibt nie in die Datei.
2. `config.example.yaml` nach `config.yaml` kopieren und mit den eigenen Werten befüllen
   (siehe Kommentare in der Datei — Zinsbindungen, Objektstammdaten, Steuerwerte,
   Wechselkurse, Kontenzuordnung). `config.yaml` steht in `.gitignore` und wird nie
   versehentlich committet.
3. Prüfen, wie Essanz die Datei einordnet:

   ```bash
   python3 run_update.py /pfad/zur/eigenen.portfolio --diagnose --config config.yaml
   ```

   Die Diagnose listet jedes Konto und Depot mit seiner Gruppe (Liquidität, Darlehen,
   Objektkonto, Immobilien-Depot …) und dem Grund dafür, die erkannten Objekte und
   Hinweise, wo Datei und `config.yaml` nicht zusammenpassen. Folgt die Datei nicht der
   Namenskonvention unten, schlägt sie einen Abschnitt `konten:` zum Einfügen vor. Es wird
   nichts gerechnet oder geschrieben.
4. Ausführen:

   ```bash
   python3 run_update.py /pfad/zur/eigenen.portfolio --config config.yaml --stichtag 2026-08-31
   ```

Ohne `--stichtag` wird der heutige Tag verwendet. Mit `--anonym` entsteht zusätzlich eine
Fassung ohne Adressen und Mieternamen, gedacht zum Teilen außerhalb der eigenen Familie:
Objektnamen werden überall durch „Objekt N (Ort)“ ersetzt, auch in Konto- und
Darlehensnamen, Quellenangaben entfallen.

Kein Abschnitt in `config.yaml` ist Pflicht — ohne `steuer:` bleiben die Steuerspalten
leer, ohne `zinsbindungen:` fehlt die Fälligkeitsleiste, der Rest funktioniert trotzdem.

### Konten in Portfolio Performance

Essanz braucht für jede Immobilie drei Dinge aus der PP-Datei: ein **Objektkonto** (Miete,
Kosten, Annuität), ein **Wertpapier**, dessen Kurs der Verkehrswert ist (in einem eigenen
Immobilien-Depot), und das **Darlehenskonto** (Auszahlung als Umbuchung vom
Darlehenskonto auf das Objektkonto, Annuität als Umbuchung zurück).

Ohne weitere Angaben erkennt Essanz diese an den Namen `Immobilie 1: Musterstraße 5`
(Konto und Wertpapier), `Darlehenskonto 1` und einem Depot, dessen Name mit `Immo`
beginnt. Wer anders benannt hat, muss nichts umbenennen, sondern ordnet in `config.yaml`
unter `konten:` nach exaktem Namen zu (Beispiel am Ende von `config.example.yaml`).
Alle übrigen Konten zählen als Liquidität, alle übrigen Depots als Wertpapiere. Passt die
Zuordnung nicht, weist der normale Lauf darauf hin; Details zeigt `--diagnose`.

## Im Browser (Prototyp)

Unter `web/` liegt eine Browser-Fassung. Der Python-Kern läuft dort per
[Pyodide](https://pyodide.org/) (Python als WebAssembly) im Browser. Die `.portfolio`-Datei
wird mit dem Datei-Dialog gelesen und verlässt den Rechner nicht. Es gibt keinen Server
und keinen Upload, und Pyodide wird mit ausgeliefert statt von einem CDN geladen. Die Seite
zeigt erst die Diagnose (wie `--diagnose`) und darunter das volle Dashboard, das sich als
HTML-Datei speichern lässt, auf Wunsch anonymisiert. Folgt die Datei nicht der
Namenskonvention, ordnet man im Formular „Zuordnung bearbeiten“ jeder Immobilie Konto,
Wertpapier und Darlehen zu und trägt Zinsbindungen ein; daraus entsteht eine `config.yaml`
zum Herunterladen (oder, nur auf ausdrücklichen Wunsch, im Browser gemerkt). Das Dashboard läuft in einem eigenen
Rahmen (`dashboard.html`), dessen Content Security Policy jede Netzwerkverbindung sperrt.

```bash
python3 web/build.py                                   # lädt Pyodide einmal, baut web/dist/
python3 -m http.server 8771 --directory web/dist       # dann http://localhost:8771/ öffnen
```

`build.py` lädt Pyodide von der offiziellen GitHub-Release-Seite und prüft die Downloads
per SHA-256. `web/dist/` und `web/.cache/` sind gitignored.

## Wie die Konfiguration funktioniert

Alle persönlichen Daten (Adressen, Mieternamen, Darlehenskonditionen, Steuerwerte) liegen
ausschließlich in `config.yaml` — nirgends im Code. `config.py` lädt diese Datei einmal
und cached sie; `objektdaten.py` und `steuer.py` lesen daraus, `analyze.py` liest beim
Import die allgemeinen Schwellwerte (Wechselkurse, welche Objekte selbstgenutzt sind,
Kontenzuordnung, Vergleichsindizes). Wer `essanz-core` klont und nur die eigene
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
| `diagnose.py` | Zeigt mit `--diagnose`, wie Konten, Depots und Objekte eingeordnet werden, und prüft Datei und Config gegeneinander. |
| `formular.py` | Zuordnung per Formular: Auswahllisten aus der Datei, aus den Eingaben eine `config.yaml` bauen (Browser-App). |
| `web/` | Browser-App (Prototyp): `index.html`, `app.js`, `app.css`, `build.py` bündelt Pyodide und Kern nach `web/dist/`. |
| `run_update.py` | Kommandozeilen-Einstieg, übersetzt Fehler in verständliche Meldungen (`--debug` zeigt den vollen Python-Fehler). |
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
