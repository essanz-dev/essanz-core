#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Erzeugt das Dashboard aus einer .portfolio-Datei.

    python3 run_update.py <pfad/zur/datei.portfolio> [ausgabeordner] [--stichtag JJJJ-MM-TT]
                           [--config config.yaml] [--anonym]

Ohne --config wird zuerst ./config.yaml gesucht, sonst die mitgelieferte
config.example.yaml mit frei erfundenen Demo-Zahlen verwendet (siehe README).
"""
import argparse, datetime, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def main():
    ap = argparse.ArgumentParser(description='Essanz — Gesamtvermögensbilanz aus Portfolio Performance')
    ap.add_argument('portfolio', help='Pfad zur .portfolio-Datei')
    ap.add_argument('out', nargs='?', default='ausgabe', help='Ausgabeordner')
    ap.add_argument('--stichtag', default=None, help='Stichtag JJJJ-MM-TT, sonst heute')
    ap.add_argument('--config', default=None,
                     help='Pfad zur eigenen config.yaml (Objektdaten, Steuerwerte, Kontenkonventionen). '
                          'Ohne Angabe: ./config.yaml, sonst die mitgelieferte Beispiel-Konfiguration.')
    ap.add_argument('--anonym', action='store_true',
                     help='Anonymisierte Fassung: Adressen auf Stadt/Stadtteil verkürzt, '
                          'Mieternamen entfernt. Zum Teilen außerhalb der Familie.')
    a = ap.parse_args()

    if a.config:
        os.environ['ESSANZ_CONFIG'] = a.config

    # Erst jetzt importieren, damit ESSANZ_CONFIG vor dem Laden der Konfiguration gesetzt ist.
    import analyze, make_dashboard

    os.makedirs(a.out, exist_ok=True)
    stichtag = a.stichtag or datetime.date.today().isoformat()

    print(f'Lese {a.portfolio} …')
    d = analyze.build(a.portfolio, stichtag)
    if a.anonym:
        d = analyze.anonymisieren(d)
    json.dump(d, open(os.path.join(a.out, 'daten.json'), 'w'), ensure_ascii=False, indent=1)

    tag = stichtag.replace('-', '') + ('_anonym' if a.anonym else '')
    k = d['kpi']
    html_p = os.path.join(a.out, f'Dashboard_{tag}.html')
    make_dashboard.build(d, html_p)
    print('  ✓', html_p)

    print(f"""
Stichtag {stichtag}
  Nettovermögen        {k['net']:>14,.2f} €
  Vermögen             {k['assets']:>14,.2f} €
  Verbindlichkeiten    {k['debt']:>14,.2f} €
  Eigenkapitalquote    {k['eigenkapitalquote']:>14.1f} %
  Veränderung Monat    {k['delta_m']:>14,.2f} €
  Veränderung YTD      {k['delta_ytd']:>14,.2f} €""".replace(',', ' '))


if __name__ == '__main__':
    main()
