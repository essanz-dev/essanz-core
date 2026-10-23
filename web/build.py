#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Baut die Browser-App nach web/dist/.

    python3 web/build.py            # danach: python3 -m http.server 8771 --directory web/dist

Was passiert:
  1. Pyodide (Python als WebAssembly) wird einmal von der offiziellen GitHub-Release-Seite
     geladen, per SHA-256 geprueft und nach dist/pyodide/ entpackt. Dazu kommt das
     PyYAML-Paket aus der Pyodide-Distribution (Pruefsumme aus pyodide-lock.json).
     Die Downloads liegen danach in web/.cache/ und werden nicht erneut geladen.
  2. Der Essanz-Kern (*.py, Vorlage, Beispieldatei, Beispiel-Config) wird nach dist/core/
     kopiert, dazu ein manifest.json mit der Dateiliste.
  3. Die Seite selbst (index.html, app.js, app.css, Dashboard-Rahmen) wird nach dist/ kopiert.

Die App laedt zur Laufzeit nur Dateien aus dist/ (gleiche Herkunft, kein CDN). Die
.portfolio-Datei der Nutzer:innen wird im Browser gelesen und nie gesendet.
"""
import hashlib, json, os, shutil, sys, tarfile, urllib.request

PYODIDE_VERSION = '0.26.4'
PYODIDE_URL = ('https://github.com/pyodide/pyodide/releases/download/'
               f'{PYODIDE_VERSION}/pyodide-core-{PYODIDE_VERSION}.tar.bz2')
PYODIDE_SHA256 = '70dba93432f3653155998cc9001f9c200182343c2f95165a2f9e9e4673fa35e8'
PAKET_URL = f'https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/'
PAKETE = ['pyyaml']
# Nur diese Dateien aus dem Pyodide-Archiv werden ausgeliefert.
PYODIDE_DATEIEN = ['pyodide.js', 'pyodide.mjs', 'pyodide.asm.js', 'pyodide.asm.wasm',
                   'python_stdlib.zip', 'pyodide-lock.json']

WEB = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(WEB)
CACHE = os.path.join(WEB, '.cache')
DIST = os.path.join(WEB, 'dist')
SEITE = ['index.html', 'app.js', 'app.css', 'formular.js', 'dashboard.html', 'dashboard-rahmen.js']
# Kern-Dateien, die im Browser gebraucht werden (run_update.py ist die Kommandozeile, nicht noetig).
KERN = ['analyze.py', 'config.py', 'diagnose.py', 'empfehlungen.py', 'forecast.py', 'formular.py',
        'make_dashboard.py', 'objektdaten.py', 'ppparse.py', 'schwellen.py', 'steuer.py',
        'stress.py', 'template.html', 'dash.js', 'config.example.yaml', 'beispiel.portfolio']


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def holen(url, ziel, soll):
    if os.path.exists(ziel) and sha256(ziel) == soll:
        return
    print(f'  lade {url}')
    tmp = ziel + '.part'
    with urllib.request.urlopen(url) as r, open(tmp, 'wb') as f:
        shutil.copyfileobj(r, f)
    ist = sha256(tmp)
    if ist != soll:
        os.remove(tmp)
        sys.exit(f'Pruefsumme passt nicht fuer {url}\n  erwartet {soll}\n  erhalten {ist}')
    os.replace(tmp, ziel)


def main():
    os.makedirs(CACHE, exist_ok=True)
    if os.path.isdir(DIST):
        shutil.rmtree(DIST)
    os.makedirs(os.path.join(DIST, 'pyodide'))
    os.makedirs(os.path.join(DIST, 'core'))

    print('Pyodide', PYODIDE_VERSION)
    archiv = os.path.join(CACHE, os.path.basename(PYODIDE_URL))
    holen(PYODIDE_URL, archiv, PYODIDE_SHA256)
    with tarfile.open(archiv, 'r:bz2') as t:
        for name in PYODIDE_DATEIEN:
            quelle = t.extractfile('pyodide/' + name)
            with open(os.path.join(DIST, 'pyodide', name), 'wb') as f:
                shutil.copyfileobj(quelle, f)

    lock = json.load(open(os.path.join(DIST, 'pyodide', 'pyodide-lock.json'), encoding='utf-8'))
    for paket in PAKETE:
        p = lock['packages'][paket]
        if p['depends']:
            sys.exit(f'{paket} hat Abhaengigkeiten {p["depends"]}, build.py muss erweitert werden')
        ziel = os.path.join(CACHE, p['file_name'])
        holen(PAKET_URL + p['file_name'], ziel, p['sha256'])
        shutil.copy(ziel, os.path.join(DIST, 'pyodide', p['file_name']))

    print('Essanz-Kern')
    for name in KERN:
        shutil.copy(os.path.join(ROOT, name), os.path.join(DIST, 'core', name))
    with open(os.path.join(DIST, 'core', 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(dateien=KERN, pyodide=PYODIDE_VERSION, pakete=PAKETE), f, indent=1)

    for name in SEITE:
        shutil.copy(os.path.join(WEB, name), os.path.join(DIST, name))

    groesse = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(DIST) for f in fs)
    print(f'fertig: {DIST} ({groesse / 1e6:.1f} MB)')
    print('Starten: python3 -m http.server 8771 --directory web/dist  →  http://localhost:8771/')


if __name__ == '__main__':
    main()
