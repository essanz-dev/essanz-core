#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Erzeugt das Dashboard aus einer .portfolio-Datei.

    python3 run_update.py <pfad/zur/datei.portfolio> [ausgabeordner] [--stichtag JJJJ-MM-TT]
                           [--config config.yaml] [--anonym] [--diagnose] [--debug]

Ohne --config wird zuerst ./config.yaml gesucht, sonst die mitgelieferte
config.example.yaml mit frei erfundenen Demo-Zahlen verwendet (siehe README).
Mit --diagnose wird nichts gerechnet: Essanz zeigt nur, wie es Konten, Depots und Objekte
der Datei einordnet und wo Datei und Konfiguration nicht zusammenpassen.
"""
import argparse, datetime, json, os, sys, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

ISSUES = 'https://github.com/essanz-dev/essanz-core/issues'


def _datum(s):
    try:
        return datetime.date.fromisoformat(s).isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError(f'{s!r} ist kein Datum im Format JJJJ-MM-TT (z. B. 2026-08-31)')


def main():
    ap = argparse.ArgumentParser(description='Essanz — Gesamtvermögensbilanz aus Portfolio Performance')
    ap.add_argument('portfolio', help='Pfad zur .portfolio-Datei')
    ap.add_argument('out', nargs='?', default='ausgabe', help='Ausgabeordner')
    ap.add_argument('--stichtag', default=None, type=_datum, help='Stichtag JJJJ-MM-TT, sonst heute')
    ap.add_argument('--config', default=None,
                     help='Pfad zur eigenen config.yaml (Objektdaten, Steuerwerte, Kontenkonventionen). '
                          'Ohne Angabe: ./config.yaml, sonst die mitgelieferte Beispiel-Konfiguration.')
    ap.add_argument('--anonym', action='store_true',
                     help='Anonymisierte Fassung: Adressen auf Stadt/Stadtteil verkürzt, '
                          'Mieternamen entfernt. Zum Teilen außerhalb der Familie.')
    ap.add_argument('--diagnose', action='store_true',
                     help='Nur anzeigen, wie die Datei eingeordnet wird (Konten, Depots, Objekte, '
                          'Hinweise). Schreibt nichts.')
    ap.add_argument('--debug', action='store_true', help='Bei Fehlern den vollständigen Python-Fehler zeigen.')
    a = ap.parse_args()

    if a.config:
        if not os.path.isfile(a.config):
            ap.error(f'Die Konfiguration {a.config} gibt es nicht.')
        os.environ['ESSANZ_CONFIG'] = a.config

    try:
        return lauf(a)
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        import config, ppparse
        if a.debug:
            traceback.print_exc()
        if isinstance(e, (config.ConfigFehler, ppparse.FormatFehler)):
            print(f'\nFehler: {e}', file=sys.stderr)
        else:
            print(f'\nUnerwarteter Fehler: {type(e).__name__}: {e}', file=sys.stderr)
            print('Das ist vermutlich ein Fehler in Essanz. Hilfreich ist zuerst\n'
                  f'  python3 run_update.py {a.portfolio} --diagnose\n'
                  'und, wenn das nicht weiterhilft, ein Issue mit der Ausgabe von --debug '
                  f'(ohne Kontonamen und Beträge): {ISSUES}', file=sys.stderr)
        return 1


def lauf(a):
    # Erst jetzt importieren, damit ESSANZ_CONFIG vor dem Laden der Konfiguration gesetzt ist.
    import analyze, diagnose, make_dashboard

    stichtag = a.stichtag or datetime.date.today().isoformat()

    print(f'Lese {a.portfolio} …', flush=True)
    book = analyze.Book(a.portfolio, stichtag)
    if a.diagnose:
        hw = diagnose.ausgeben(book, stichtag)
        return 1 if any(s == 'Fehler' for s, _ in hw) else 0

    hw = diagnose.hinweise(book, book.snapshot(stichtag))
    d = analyze.build(a.portfolio, stichtag, book=book)
    if a.anonym:
        d = analyze.anonymisieren(d)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'daten.json'), 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=1)

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

    n = {s: sum(1 for x, _ in hw if x == s) for s in ('Fehler', 'Warnung')}
    if n['Fehler'] or n['Warnung']:
        teile = [f'{v} {s if v == 1 else s + ("" if s == "Fehler" else "en")}' for s, v in n.items() if v]
        print(f'\n  Achtung: {" und ".join(teile)} zur Zuordnung der Konten. Die Zahlen können deshalb '
              f'falsch sein.\n  Details: python3 run_update.py {a.portfolio} --diagnose'
              + (f' --config {a.config}' if a.config else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
