# -*- coding: utf-8 -*-
"""Zeigt, wie Essanz eine Portfolio-Performance-Datei einordnet, bevor gerechnet wird.

    python3 run_update.py <datei.portfolio> --diagnose [--config config.yaml]

Gedacht fuer die erste Begegnung mit einer fremden Datei: Welche Konten zaehlen als
Darlehen, welche als Objektkonto, welche Depots als Immobilien, welche Objekte wurden
erkannt, und wo passen Datei und config.yaml nicht zusammen. Die Ausgabe enthaelt
Kontonamen und Salden und bleibt im Terminal; es wird nichts geschrieben.
"""
import config as _config


def _eur(v):
    return f'{v:>14,.2f} €'.replace(',', ' ')


def hinweise(b, snap):
    """Liste von (stufe, text) mit stufe in 'Fehler', 'Warnung', 'Info'."""
    out = []
    k = b.kontenregeln
    namen_konto = {a['name'] for a in b.acc.values()}
    namen_depot = {p['name'] for p in b.pf.values()}
    namen_wp = {s['name'] for s in b.sec.values()}

    if not b.objects:
        out.append(('Warnung', 'Keine Immobilie erkannt. Essanz erwartet Objektkonten wie '
                    '„Immobilie 1: Musterstraße 5“ oder eine Zuordnung unter konten.objekte in '
                    'config.yaml. Ohne Objekte fehlen Beleihung, Kapitaldienst und Zinsbindungen.'))

    for no, o in sorted(b.objects.items(), key=lambda x: int(x[0])):
        cfg = k['objekte'].get(no, {})
        if o['account'] not in b.acc:
            out.append(('Fehler', f'Objekt {no}: Konto {cfg.get("konto")!r} aus konten.objekte '
                        'gibt es in der Datei nicht (Schreibweise exakt wie in PP).'))
        for name in ([cfg['darlehen']] if isinstance(cfg.get('darlehen'), str) else cfg.get('darlehen') or []):
            if name not in namen_konto:
                out.append(('Fehler', f'Objekt {no}: Darlehenskonto {name!r} aus konten.objekte '
                            'gibt es in der Datei nicht.'))
        if cfg.get('wertpapier') and cfg['wertpapier'] not in namen_wp:
            out.append(('Fehler', f'Objekt {no}: Wertpapier {cfg["wertpapier"]!r} aus '
                        'konten.objekte gibt es in der Datei nicht.'))
        if o['sec'] is None:
            out.append(('Warnung', f'Objekt {no} ({o["name"]}): kein Immobilien-Wertpapier gefunden. '
                        'Der Verkehrswert ist dann 0 und Mieten werden nicht zugeordnet. In PP das '
                        'Objekt als Wertpapier mit gleichem Namen anlegen oder unter konten.objekte '
                        '„wertpapier:“ angeben.'))
        else:
            depots = {pos['portfolio'] for pos in snap['positions'] if pos['security'] == o['sec']}
            falsch = [b.pf[d]['name'] for d in depots if b.pf_group.get(d) != 'Immobilien']
            if falsch:
                out.append(('Warnung', f'Objekt {no}: Das Wertpapier liegt im Depot '
                            f'{", ".join(repr(x) for x in falsch)}, das als Wertpapier-Depot zählt. '
                            'Dann landet die Immobilie in den Wertpapieren. Abhilfe: unter '
                            'konten.depot_gruppe das Depot auf „Immobilien“ setzen.'))
            if not depots and o['sec'] is not None:
                out.append(('Info', f'Objekt {no}: Das Wertpapier ist zum Stichtag in keinem Depot '
                            '(nicht gekauft oder schon verkauft).'))
        if not o['loans']:
            out.append(('Info', f'Objekt {no} ({o["name"]}): kein Darlehen zugeordnet. Stimmt das, '
                        'ist alles in Ordnung (Objekt ist schuldenfrei).'))

    obj_loans = {l for o in b.objects.values() for l in o['loans']}
    for u, a in b.acc.items():
        saldo = snap['cash'].get(u, 0.0)
        if b.acc_group[u] == 'Darlehen':
            if u not in obj_loans and abs(saldo) >= 1:
                out.append(('Warnung', f'Darlehen {a["name"]!r} gehört zu keinem Objekt. Es zählt in '
                            'der Bilanz, fehlt aber bei Beleihung und Kapitaldienst des Objekts.'))
            if saldo > 1:
                out.append(('Warnung', f'Darlehen {a["name"]!r} hat einen positiven Saldo '
                            f'({_eur(saldo).strip()}). Essanz erwartet Darlehen als negatives '
                            'Konto: Auszahlung als Umbuchung vom Darlehenskonto auf das Objektkonto.'))
        elif saldo < -1000 and b.acc_group[u] == 'Liquidität' and not a.get('retired'):
            out.append(('Info', f'Konto {a["name"]!r} steht bei {_eur(saldo).strip()} und zählt als '
                        f'{b.acc_group[u]}. Ist es ein Kredit, unter konten.konten_gruppe auf '
                        '„Darlehen“ setzen.'))

    if beispiel_config():
        out.append(('Info', 'Es läuft die mitgelieferte Beispiel-Konfiguration mit erfundenen Daten. '
                    'Für die eigene Datei: config.example.yaml nach config.yaml kopieren und anpassen '
                    '(Vorschlag für den Abschnitt „konten:“ siehe unten).'))
        return out + _waehrungen(b)

    for name in k['konten_gruppe']:
        if name not in namen_konto and name not in _config.DEFAULT_KONTEN['konten_gruppe']:
            out.append(('Warnung', f'konten.konten_gruppe nennt {name!r}, das Konto gibt es nicht.'))
    for name in k['depot_gruppe']:
        if name not in namen_depot and name not in _config.DEFAULT_KONTEN['depot_gruppe']:
            out.append(('Warnung', f'konten.depot_gruppe nennt {name!r}, das Depot gibt es nicht.'))
    darlehen_namen = {b.acc[u]['name'] for u in b.acc if b.acc_group[u] == 'Darlehen'}
    for name in _config.zinsbindungen():
        if name not in darlehen_namen:
            out.append(('Warnung', f'zinsbindungen nennt {name!r}, das ist aber kein erkanntes '
                        'Darlehenskonto. Der Schlüssel muss exakt dem Kontonamen in PP entsprechen.'))
    for name in sorted(darlehen_namen - set(_config.zinsbindungen())):
        out.append(('Info', f'Für Darlehen {name!r} fehlt ein Eintrag unter zinsbindungen; '
                    'es erscheint dann nicht in der Fälligkeitsleiste.'))
    for no in _config.objektstamm():
        if str(no) not in b.objects:
            out.append(('Warnung', f'objektstamm nennt Objekt {no}, das in der Datei nicht erkannt wurde.'))
    return out + _waehrungen(b)


def beispiel_config():
    import os
    return os.path.basename(_config.pfad() or '') == 'config.example.yaml'


def _waehrungen(b):
    out = []
    fx = _config.allgemein()['fx']
    waehrungen = {a['currency'] for a in b.acc.values()} | {s['currency'] for s in b.sec.values()}
    for c in sorted(w for w in waehrungen if w and w not in fx):
        out.append(('Warnung', f'Währung {c} kommt vor, unter allgemein.fx steht aber kein Kurs. '
                    'Beträge in dieser Währung werden 1:1 als Euro gerechnet.'))
    return out


def _q(name):
    return '"%s"' % name.replace('\\', '\\\\').replace('"', '\\"')


def konten_vorschlag(b, snap):
    """YAML-Entwurf fuer den Abschnitt konten:, wenn die Datei der Konvention nicht folgt."""
    kredite = [a['name'] for u, a in sorted(b.acc.items(), key=lambda x: snap['cash'].get(x[0], 0.0))
               if b.acc_group[u] == 'Liquidität' and snap['cash'].get(u, 0.0) < -1000 and not a['retired']]
    if b.objects and not kredite:
        return ''
    zeilen = ['konten:']
    if kredite:
        zeilen.append('  konten_gruppe:          # Konten mit negativem Saldo, vermutlich Kredite')
        zeilen += ['    %s: Darlehen' % _q(n) for n in kredite]
    if not b.objects:
        depots = [p['name'] for u, p in b.pf.items() if b.pf_group[u] == 'Wertpapiere']
        zeilen.append('  # depot_gruppe:          # Depot, in dem die Immobilien als Wertpapier liegen')
        zeilen += ['  #   %s: Immobilien' % _q(n) for n in depots]
        zeilen += ['  objekte:                # je Immobilie eine Nummer (dieselbe wie in objektstamm)',
                   '    "1":',
                   '      name: "Wohnung Musterstraße"',
                   '      konto: "<Konto, auf dem Miete und Kosten laufen>"',
                   '      darlehen: [%s]' % (_q(kredite[0]) if kredite else '"<Darlehenskonto>"'),
                   '      wertpapier: "<Wertpapier, das den Verkehrswert trägt>"']
    return '\n'.join(zeilen)


def ausgeben(b, stichtag):
    snap = b.snapshot(stichtag)
    print(f'Konfiguration: {_config.pfad()}')
    print(f'Stichtag {stichtag}, Buchungen von {b.start} bis {b.tx[-1]["date"]}, '
          f'{len(b.tx)} Buchungen\n')

    print('KONTEN')
    for u, a in sorted(b.acc.items(), key=lambda x: (x[1]['retired'], b.acc_group[x[0]], x[1]['name'])):
        saldo = snap['cash'].get(u, 0.0)
        alt = '  (aufgelöst)' if a['retired'] else ''
        print(f'  {a["name"][:40]:<40} {b.acc_group[u]:<18}{_eur(saldo)}   {b.acc_reason[u]}{alt}')

    print('\nDEPOTS')
    for u, p in sorted(b.pf.items(), key=lambda x: x[1]['name']):
        wert = sum(x['value'] for x in snap['positions'] if x['portfolio'] == u)
        print(f'  {p["name"][:40]:<40} {b.pf_group[u]:<18}{_eur(wert)}   {b.pf_reason[u]}')

    print('\nOBJEKTE')
    if not b.objects:
        print('  (keine erkannt)')
    for no, o in sorted(b.objects.items(), key=lambda x: int(x[0])):
        konto = b.acc[o['account']]['name'] if o['account'] in b.acc else '—'
        sec = b.sec[o['sec']]['name'] if o['sec'] else '—'
        loans = ', '.join(b.acc[l]['name'] for l in o['loans']) or '—'
        print(f'  {no}: {o["name"]}   ({b.obj_reason[no]})')
        print(f'       Konto {konto} · Wertpapier {sec} · Darlehen {loans}')

    g = snap['groups']
    print('\nSUMMEN')
    for key in ('Immobilien', 'Wertpapiere', 'Liquidität', 'Immobilien-Konten', 'P2P', 'Krypto-Konten'):
        if abs(g.get(key, 0.0)) >= 0.005:
            print(f'  {key:<20}{_eur(g[key])}')
    print(f'  {"Darlehen":<20}{_eur(-snap["debt"])}')
    print(f'  {"Nettovermögen":<20}{_eur(snap["net"])}')

    hw = hinweise(b, snap)
    print('\nHINWEISE')
    if not hw:
        print('  Keine. Die Zuordnung passt zur Konfiguration.')
    for stufe in ('Fehler', 'Warnung', 'Info'):
        for s, text in hw:
            if s == stufe:
                print(f'  [{s}] {text}')
    vorschlag = konten_vorschlag(b, snap)
    if vorschlag:
        print('\nVORSCHLAG FÜR config.yaml (prüfen und anpassen)')
        print(vorschlag)
    print('\nZuordnung ändern: Abschnitt „konten:“ in config.yaml (Beispiel in config.example.yaml).')
    return hw
