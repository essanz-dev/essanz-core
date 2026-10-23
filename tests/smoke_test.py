#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rauchtest: laesst die Pipeline mit der mitgelieferten Beispiel-Konfiguration und der
fiktiven beispiel.portfolio laufen und prueft die Kennzahlen gegen feste Referenzwerte.

Aufruf (aus dem Repo-Wurzelverzeichnis):  python3 tests/smoke_test.py

Aendern sich die Referenzwerte absichtlich (z. B. neue Rechenlogik), die Zahlen unten bewusst
anpassen und im Commit begruenden. Aendern sie sich unbeabsichtigt, ist das ein Regressionsfehler.
"""
import json, os, subprocess, sys, tempfile

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STICHTAG = '2026-08-31'

# Referenzwerte (frei erfundene Beispieldaten, Stand: erste Veroeffentlichung)
ERWARTET = {
    'net': 420295.54,
    'assets': 902585.54,
    'debt': 482290.00,
    'eigenkapitalquote': 46.57,
    'delta_m': 27247.48,
    'delta_ytd': 61225.82,
    'dscr': 1.40,
}
TOLERANZ = {'eigenkapitalquote': 0.01, 'dscr': 0.01}  # Rest: 0.01 absolut


def lauf(args, env_extra=None):
    env = dict(os.environ, **(env_extra or {}))
    env.pop('ESSANZ_CONFIG', None)
    return subprocess.run([sys.executable, os.path.join(ROOT, 'run_update.py')] + args,
                          cwd=ROOT, env=env, capture_output=True, text=True)


def kpi_pruefen(d, fehler, wo=''):
    for key, soll in ERWARTET.items():
        ist = d['kpi'].get(key)
        tol = TOLERANZ.get(key, 0.01)
        if ist is None or abs(ist - soll) > tol:
            fehler.append(f'{wo}kpi[{key}] = {ist}, erwartet {soll} (Toleranz {tol})')


# Dieselbe Beispieldatei mit Kontennamen, die nicht der Essanz-Konvention folgen
# (so wie eine fremde PP-Datei aussehen koennte). Mit konten.objekte in der Config muessen
# exakt dieselben Kennzahlen herauskommen.
UMBENENNEN = {
    'Immobilie 1: Bergstraße 14': 'Mietkonto Bergstraße',
    'Immobilie 2: Ahornweg 7': 'Mietkonto Ahornweg',
    'Immobilie 3: Lindenallee 22': 'Hauskonto Lindenallee',
    'Darlehenskonto 1': 'Baufi Bergstraße',
    'Darlehenskonto 2': 'KfW Ahornweg',
    'Darlehenskonto 3': 'Baufi Lindenallee',
    'Immobilien': 'Sachwerte',
}


def fremde_namen(tmp, fehler):
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    import make_example_portfolio as gen
    # Konten und Wertpapiere heissen im Beispiel gleich, der Generator benennt beide um.
    datei = os.path.join(tmp, 'fremd.portfolio')
    with open(datei, 'wb') as f:
        f.write(gen.build(UMBENENNEN))

    # Ohne Zuordnung: Diagnose muss warnen, der normale Lauf muss darauf hinweisen.
    r = lauf([datei, '--diagnose', '--stichtag', STICHTAG])
    if 'Keine Immobilie erkannt' not in r.stdout:
        fehler.append('Diagnose ohne konten.objekte meldet fehlende Objekte nicht:\n' + r.stdout[-800:])
    r = lauf([datei, os.path.join(tmp, 'fremd_ohne'), '--stichtag', STICHTAG])
    if r.returncode != 0 or 'Achtung' not in r.stdout:
        fehler.append('Lauf ohne konten.objekte zeigt keinen Zuordnungshinweis:\n' + r.stdout[-800:] + r.stderr)

    cfg = yaml.safe_load(open(os.path.join(ROOT, 'config.example.yaml'), encoding='utf-8'))
    cfg['zinsbindungen'] = {UMBENENNEN[k]: v for k, v in cfg['zinsbindungen'].items()}
    alt = {'1': 'Immobilie 1: Bergstraße 14', '2': 'Immobilie 2: Ahornweg 7',
           '3': 'Immobilie 3: Lindenallee 22'}
    cfg['konten'] = dict(
        depot_gruppe={'Sachwerte': 'Immobilien'},
        objekte={no: dict(name=n.split(': ', 1)[1], konto=UMBENENNEN[n],
                          darlehen=[UMBENENNEN['Darlehenskonto %s' % no]], wertpapier=UMBENENNEN[n])
                 for no, n in alt.items()},
    )
    cfg_pfad = os.path.join(tmp, 'fremd.yaml')
    with open(cfg_pfad, 'w', encoding='utf-8') as f:
        yaml.safe_dump(cfg, f, allow_unicode=True)

    r = lauf([datei, '--diagnose', '--stichtag', STICHTAG, '--config', cfg_pfad])
    if r.returncode != 0 or '[Fehler]' in r.stdout or '[Warnung]' in r.stdout:
        fehler.append('Diagnose mit konten.objekte nicht sauber:\n' + r.stdout[-1500:] + r.stderr)
    ausgabe = os.path.join(tmp, 'fremd')
    r = lauf([datei, ausgabe, '--stichtag', STICHTAG, '--config', cfg_pfad])
    if r.returncode != 0:
        fehler.append('Lauf mit konten.objekte fehlgeschlagen:\n' + r.stderr)
        return
    kpi_pruefen(json.load(open(os.path.join(ausgabe, 'daten.json'), encoding='utf-8')), fehler, 'fremd: ')


def formular_weg(tmp, fehler):
    """Wie in der Browser-App: Datei mit fremden Namen, Zuordnung per Formular, daraus eine
    config.yaml bauen und rechnen. Ergebnis muss den Referenzwerten entsprechen."""
    skript = f"""
import json, os, sys
sys.path.insert(0, {ROOT!r}); sys.path.insert(0, {os.path.join(ROOT, 'tools')!r})
os.environ['ESSANZ_CONFIG'] = {os.path.join(ROOT, 'config.example.yaml')!r}
import yaml, analyze, formular
basis = yaml.safe_load(open({os.path.join(ROOT, 'config.example.yaml')!r}, encoding='utf-8'))
b = analyze.Book({os.path.join(ROOT, 'beispiel.portfolio')!r}, {STICHTAG!r})
d = formular.daten(b, {STICHTAG!r}, basis)
assert [o['nr'] for o in d['objekte']] == ['1', '2', '3'], d['objekte']
assert d['objekte'][2]['selbstgenutzt'] and d['objekte'][0]['darlehen'] == ['Darlehenskonto 1']
assert d['zinsbindungen']['Darlehenskonto 1']['ende'] == '2031-08-31'
umb = json.loads({json.dumps(UMBENENNEN, ensure_ascii=False)!r})
f = analyze.Book({os.path.join(tmp, 'fremd.portfolio')!r}, {STICHTAG!r})
df = formular.daten(f, {STICHTAG!r}, dict())
assert not df['objekte'], 'fremde Datei: Objekte ohne Zuordnung erkannt'
stand = dict(
    objekte=[dict(nr=o['nr'], name=o['name'], konto=umb[o['konto']], wertpapier=umb[o['wertpapier']],
                  darlehen=[umb[x] for x in o['darlehen']], selbstgenutzt=o['selbstgenutzt'],
                  lage=o['lage'], lage_anonym=o['lage_anonym'], baujahr=o['baujahr'],
                  wohnflaeche_m2=o['wohnflaeche_m2']) for o in d['objekte']],
    konten_gruppe=dict((k['name'], k['gruppe']) for k in df['konten']),
    depot_gruppe=dict((x['name'], 'Immobilien' if x['name'] == umb['Immobilien'] else 'Wertpapiere')
                      for x in df['depots']),
    zinsbindungen=dict((umb[k], v) for k, v in d['zinsbindungen'].items()),
)
rest = dict((k, v) for k, v in basis.items() if k not in ('zinsbindungen', 'objektstamm', 'konten'))
open({os.path.join(tmp, 'formular.yaml')!r}, 'w', encoding='utf-8').write(
    formular.als_yaml(formular.config_bauen(rest, stand)))
"""
    r = subprocess.run([sys.executable, '-c', skript], capture_output=True, text=True)
    if r.returncode != 0:
        fehler.append('Formular-Weg fehlgeschlagen:\n' + r.stderr[-1500:])
        return
    cfg = os.path.join(tmp, 'formular.yaml')
    r = lauf([os.path.join(tmp, 'fremd.portfolio'), '--diagnose', '--stichtag', STICHTAG, '--config', cfg])
    if r.returncode != 0 or '[Warnung]' in r.stdout or '[Fehler]' in r.stdout:
        fehler.append('Diagnose mit Formular-Config nicht sauber:\n' + r.stdout[-1500:] + r.stderr)
    ausgabe = os.path.join(tmp, 'formular')
    r = lauf([os.path.join(tmp, 'fremd.portfolio'), ausgabe, '--stichtag', STICHTAG, '--config', cfg])
    if r.returncode != 0:
        fehler.append('Lauf mit Formular-Config fehlgeschlagen:\n' + r.stderr)
        return
    kpi_pruefen(json.load(open(os.path.join(ausgabe, 'daten.json'), encoding='utf-8')), fehler, 'formular: ')


def run_rate(tmp, fehler):
    """Mietrendite und DSCR rechnen mit der aktuellen Miete x 12 (Run-Rate), nicht mit der
    Summe der letzten zwoelf Buchungen. Objekt 1 bekommt drei Monate vor dem Stichtag eine
    hoehere Miete; die Kennzahl wird unabhaengig aus den Beispielwerten nachgerechnet."""
    import datetime
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    import make_example_portfolio as gen
    datei = os.path.join(tmp, 'mieterhoehung.portfolio')
    with open(datei, 'wb') as f:
        f.write(gen.build(mieterhoehung={1: (datetime.date(2026, 6, 1), 1100.0)}))
    ausgabe = os.path.join(tmp, 'mieterhoehung')
    r = lauf([datei, ausgabe, '--stichtag', STICHTAG])
    if r.returncode != 0:
        fehler.append('Lauf mit Mieterhöhung fehlgeschlagen:\n' + r.stderr)
        return
    d = json.load(open(os.path.join(ausgabe, 'daten.json'), encoding='utf-8'))
    inv = [o for o in d['objects'] if not o['selbstgenutzt']]
    inv_val = sum(o['value'] for o in inv)
    miete_run = (1100.0 + 780.0) * 12            # Objekt 1 nach Erhoehung, Objekt 2 unveraendert
    nk_run = (180.0 + 150.0) * 12
    kosten = sum(o['cost12'] for o in inv)
    ann = sum(o['annuitaet12'] for o in inv)
    soll = dict(mietrendite=miete_run / inv_val * 100,
                dscr=(miete_run + nk_run - kosten) / ann)
    for k, v in soll.items():
        if abs(d['kpi'][k] - v) > 1e-6:
            fehler.append(f'Run-Rate: kpi[{k}] = {d["kpi"][k]}, erwartet {v}')
    o1 = next(o for o in d['objects'] if o['no'] == 1)
    if abs(o1.get('rent_runrate', 0) - 1100.0 * 12) > 1e-6 or abs(o1['rent12'] - (950.0 * 9 + 1100.0 * 3)) > 1e-6:
        fehler.append(f'Run-Rate Objekt 1: rent_runrate={o1.get("rent_runrate")}, rent12={o1["rent12"]}')


def fehlerfaelle(tmp, fehler):
    """Kaputte Eingaben enden mit einer Meldung, nicht mit einem Python-Traceback."""
    kaputt = os.path.join(tmp, 'kaputt.portfolio')
    open(kaputt, 'wb').write(b'kein portfolio' * 50)
    xml = os.path.join(tmp, 'xml.portfolio')
    open(xml, 'w').write('<?xml version="1.0" encoding="UTF-8"?>\n<client><version>66</version></client>')
    verschl = os.path.join(tmp, 'verschluesselt.portfolio')
    open(verschl, 'wb').write(b'PORTFOLIO\x01' + b'\x00' * 64)
    abgeschnitten = os.path.join(tmp, 'abgeschnitten.portfolio')
    raw = open(os.path.join(ROOT, 'beispiel.portfolio'), 'rb').read()
    open(abgeschnitten, 'wb').write(raw[:len(raw) // 2])
    yaml_kaputt = os.path.join(tmp, 'kaputt.yaml')
    open(yaml_kaputt, 'w').write('zinsbindungen:\n  "x": [1, 2\n\tende: 3\n')
    beispiel = os.path.join(ROOT, 'beispiel.portfolio')
    faelle = [
        ('kaputte Datei', [kaputt], 'PPPBV1'),
        ('XML-Datei', [xml], 'XML'),
        ('verschluesselte Datei', [verschl], 'verschlüsselt'),
        ('abgeschnittene Datei', [abgeschnitten], 'nicht vollständig lesen'),
        ('fehlende Datei', [os.path.join(tmp, 'gibtsnicht.portfolio')], 'gibt es nicht'),
        ('kaputte config', [beispiel, '--config', yaml_kaputt], 'kein gültiges YAML'),
        ('falscher Stichtag', [beispiel, '--stichtag', '31.08.2026'], 'JJJJ-MM-TT'),
    ]
    for name, args, erwartet in faelle:
        r = lauf(args + ['--diagnose'])
        if r.returncode == 0 or 'Traceback' in r.stderr or erwartet not in r.stderr:
            fehler.append(f'{name}: rc={r.returncode}, erwartet Meldung mit {erwartet!r}:\n{r.stderr[-600:]}')


def web_vollstaendig(fehler):
    """Die Browser-App bekommt nur die Dateien aus web/build.py KERN; kein Modul darf fehlen."""
    sys.path.insert(0, os.path.join(ROOT, 'web'))
    import build
    module = {f for f in os.listdir(ROOT) if f.endswith('.py') and f != 'run_update.py'}
    fehlt = sorted(module - set(build.KERN))
    if fehlt:
        fehler.append(f'web/build.py KERN fehlt: {", ".join(fehlt)}')


def main():
    fehler = []
    web_vollstaendig(fehler)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = os.environ.get('ESSANZ_TEST_ORDNER') or tmp
        os.makedirs(tmp, exist_ok=True)
        fremde_namen(tmp, fehler)
        formular_weg(tmp, fehler)
        run_rate(tmp, fehler)
        fehlerfaelle(tmp, fehler)
        r = lauf([os.path.join(ROOT, 'beispiel.portfolio'), '--diagnose', '--stichtag', STICHTAG])
        if r.returncode != 0 or 'OBJEKTE' not in r.stdout or '[Warnung]' in r.stdout:
            fehler.append('Diagnose der Beispieldatei nicht sauber:\n' + r.stdout[-1500:] + r.stderr)
        for anonym in (False, True):
            ausgabe = os.path.join(tmp, 'anonym' if anonym else 'normal')
            args = [os.path.join(ROOT, 'beispiel.portfolio'), ausgabe, '--stichtag', STICHTAG]
            if anonym:
                args.append('--anonym')
            r = lauf(args)
            if r.returncode != 0:
                fehler.append(f'run_update ({"anonym" if anonym else "normal"}) fehlgeschlagen:\n{r.stderr}')
                continue
            html = [f for f in os.listdir(ausgabe) if f.endswith('.html')]
            if not html:
                fehler.append('Kein Dashboard-HTML erzeugt')
            else:
                text = open(os.path.join(ausgabe, html[0]), encoding='utf-8').read()
                for marker in ('/*__DATA__*/null', '/*__JS__*/', '<!--__EMPF__-->'):
                    if marker in text:
                        fehler.append(f'Platzhalter nicht ersetzt: {marker}')
            if anonym:
                # Keine Strasse aus der Beispiel-Config darf in der anonymen Fassung stehen.
                stamm = yaml.safe_load(open(os.path.join(ROOT, 'config.example.yaml'),
                                            encoding='utf-8'))['objektstamm']
                strassen = [v['lage'].split(', ', 1)[1] for v in stamm.values() if ', ' in v['lage']]
                for datei in [html[0], 'daten.json'] if html else ['daten.json']:
                    text = open(os.path.join(ausgabe, datei), encoding='utf-8').read()
                    for st in strassen:
                        if st in text:
                            fehler.append(f'anonyme Fassung enthält {st!r} in {datei}')
            if not anonym:
                kpi_pruefen(json.load(open(os.path.join(ausgabe, 'daten.json'), encoding='utf-8')), fehler)
    if fehler:
        print('FEHLER:')
        for f in fehler:
            print(' -', f)
        return 1
    print('OK: Rauchtest bestanden (normal + anonym, fremde Kontennamen, Diagnose, Fehlerfälle, Web-Kern, Anonymisierung, Formular, Run-Rate)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
