#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rauchtest: laesst die Pipeline mit der mitgelieferten Beispiel-Konfiguration und der
fiktiven beispiel.portfolio laufen und prueft die Kennzahlen gegen feste Referenzwerte.

Aufruf (aus dem Repo-Wurzelverzeichnis):  python3 tests/smoke_test.py

Aendern sich die Referenzwerte absichtlich (z. B. neue Rechenlogik), die Zahlen unten bewusst
anpassen und im Commit begruenden. Aendern sie sich unbeabsichtigt, ist das ein Regressionsfehler.
"""
import json, os, subprocess, sys, tempfile

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


def main():
    fehler = []
    with tempfile.TemporaryDirectory() as tmp:
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
            if not anonym:
                d = json.load(open(os.path.join(ausgabe, 'daten.json'), encoding='utf-8'))
                for key, soll in ERWARTET.items():
                    ist = d['kpi'].get(key)
                    tol = TOLERANZ.get(key, 0.01)
                    if ist is None or abs(ist - soll) > tol:
                        fehler.append(f'kpi[{key}] = {ist}, erwartet {soll} (Toleranz {tol})')
    if fehler:
        print('FEHLER:')
        for f in fehler:
            print(' -', f)
        return 1
    print('OK: Rauchtest bestanden (normal + anonym)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
