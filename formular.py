# -*- coding: utf-8 -*-
"""Zuordnung per Formular (Browser-App): liefert die Auswahllisten aus der Datei und baut aus
den Eingaben eine config.yaml.

daten(book, basis)        -> was das Formular anzeigt (Konten, Depots, Wertpapiere, Objekte,
                             Zinsbindungen), vorbelegt aus Datei und vorhandener Config
config_bauen(basis, stand) -> neue Config: konten, zinsbindungen, objektstamm und
                             allgemein.selbstgenutzt aus dem Formular, alles andere aus basis
als_yaml(cfg)              -> YAML-Text mit Kopfzeile

Das Formular ist danach die Quelle der Zuordnung: Jedes Konto und jedes Depot wird mit
exaktem Namen eingetragen und die Namensmuster werden abgeschaltet, damit das Ergebnis nicht
davon abhaengt, wie Konten benannt sind.
"""
import copy, datetime

import config as _config

STAMM_FELDER = ('lage', 'lage_anonym', 'baujahr', 'wohnflaeche_m2')


def daten(b, stichtag, basis):
    """basis: vorhandene Config (dict) oder {}; nur daraus werden Zinsbindungen und
    Objektstammdaten vorbelegt, nie aus der mitgelieferten Beispiel-Config."""
    snap = b.snapshot(stichtag)
    depot_von = {}
    wert = {}
    for p in snap['positions']:
        depot_von.setdefault(p['security'], b.pf[p['portfolio']]['name'])
        wert[p['security']] = wert.get(p['security'], 0.0) + p['value']
    konten = [dict(name=a['name'], saldo=round(snap['cash'].get(u, 0.0), 2), gruppe=b.acc_group[u],
                   aufgeloest=a['retired'])
              for u, a in sorted(b.acc.items(), key=lambda x: x[1]['name'].lower())]
    depots = [dict(name=p['name'], gruppe=b.pf_group[u])
              for u, p in sorted(b.pf.items(), key=lambda x: x[1]['name'].lower())]
    wertpapiere = [dict(name=s['name'], wert=round(wert.get(u, 0.0), 2), depot=depot_von.get(u))
                   for u, s in sorted(b.sec.items(), key=lambda x: (-wert.get(x[0], 0.0), x[1]['name']))
                   if not s.get('retired') or u in wert]
    stamm = basis.get('objektstamm') or {}
    selbst = {str(x) for x in (basis.get('allgemein') or {}).get('selbstgenutzt', [])}
    objekte = []
    for no, o in sorted(b.objects.items(), key=lambda x: int(x[0])):
        s = stamm.get(no) or stamm.get(int(no)) or {}
        objekte.append(dict(
            nr=no, name=o['name'],
            konto=b.acc[o['account']]['name'] if o['account'] in b.acc else '',
            wertpapier=b.sec[o['sec']]['name'] if o['sec'] else '',
            darlehen=[b.acc[l]['name'] for l in o['loans']],
            selbstgenutzt=no in selbst,
            **{f: s.get(f) for f in STAMM_FELDER}))
    zb = {}
    for name, z in (basis.get('zinsbindungen') or {}).items():
        if isinstance(z, dict):
            zb[name] = dict(ende=str(z['ende']) if z.get('ende') else '', sollzins=z.get('sollzins'),
                            nennbetrag=z.get('nennbetrag'), sondertilgung=z.get('sondertilgung'),
                            kfw=bool(z.get('kfw', False)))
    return dict(konten=konten, depots=depots, wertpapiere=wertpapiere, objekte=objekte,
                zinsbindungen=zb, gruppen_konto=list(_config.GRUPPEN_KONTO),
                gruppen_depot=list(_config.GRUPPEN_DEPOT))


def _zahl(v):
    if v in (None, ''):
        return None
    f = float(v)
    return int(f) if f.is_integer() else f


def config_bauen(basis, stand):
    """stand: {objekte: [{nr, name, konto, wertpapier, darlehen, selbstgenutzt, lage, ...}],
    konten_gruppe: {name: gruppe}, depot_gruppe: {name: gruppe},
    zinsbindungen: {konto: {ende, sollzins, nennbetrag, sondertilgung, kfw}}}"""
    cfg = copy.deepcopy(basis) if basis else {}
    cfg.pop('_pfad', None)

    objekte, stamm_neu, selbst = {}, {}, []
    objekt_konten = set()
    for o in stand.get('objekte', []):
        nr = str(o['nr'])
        if not nr.isdigit():
            raise _config.ConfigFehler(f'Objektnummer {nr!r} ist keine Zahl.')
        eintrag = {'name': (o.get('name') or '').strip() or f'Objekt {nr}'}
        if o.get('konto'):
            eintrag['konto'] = o['konto']; objekt_konten.add(o['konto'])
        if o.get('darlehen'):
            eintrag['darlehen'] = list(o['darlehen']); objekt_konten.update(o['darlehen'])
        if o.get('wertpapier'):
            eintrag['wertpapier'] = o['wertpapier']
        objekte[nr] = eintrag
        if o.get('selbstgenutzt'):
            selbst.append(nr)
        stamm_neu[nr] = o

    k = cfg.get('konten') or {}
    k['objekte'] = objekte
    k['konten_gruppe'] = {n: g for n, g in (stand.get('konten_gruppe') or {}).items()
                          if n not in objekt_konten}
    k['depot_gruppe'] = dict(stand.get('depot_gruppe') or {})
    # Zuordnung kommt vollstaendig aus dem Formular, Namensmuster nicht mehr anwenden.
    k['objekt_muster'] = None
    k['darlehen_muster'] = None
    cfg['konten'] = k

    zb = cfg.get('zinsbindungen') or {}
    for name, z in (stand.get('zinsbindungen') or {}).items():
        if not z.get('ende') or z.get('sollzins') in (None, ''):
            zb.pop(name, None)
            continue
        alt = zb.get(name) if isinstance(zb.get(name), dict) else {}
        zb[name] = dict(ende=str(z['ende']), sollzins=_zahl(z['sollzins']),
                        sondertilgung=_zahl(z.get('sondertilgung')), nennbetrag=_zahl(z.get('nennbetrag')),
                        kfw=bool(z.get('kfw')), quelle=alt.get('quelle') or 'Eingabe im Browser')
    cfg['zinsbindungen'] = zb

    stamm = cfg.get('objektstamm') or {}
    for nr, o in stamm_neu.items():
        s = dict(stamm.get(nr) or stamm.get(int(nr)) or {})
        stamm.pop(int(nr), None)
        for f in STAMM_FELDER:
            v = o.get(f)
            if f in ('baujahr', 'wohnflaeche_m2'):
                v = _zahl(v)
            elif isinstance(v, str):
                v = v.strip() or None
            if v is None:
                s.pop(f, None)
            else:
                s[f] = v
        if s:
            stamm[nr] = s
        else:
            stamm.pop(nr, None)
    cfg['objektstamm'] = stamm

    a = cfg.get('allgemein') or {}
    a['selbstgenutzt'] = selbst
    cfg['allgemein'] = a
    return cfg


def als_yaml(cfg):
    import yaml
    kopf = ('# Essanz-Konfiguration, im Browser erstellt am %s.\n'
            '# Enthält persönliche Daten: nicht veröffentlichen, nicht ins Repo legen.\n'
            '# Kommentare einer vorher geladenen config.yaml sind hier nicht mehr enthalten.\n\n'
            % datetime.date.today().isoformat())
    zuerst = ('zinsbindungen', 'objektstamm', 'konten', 'allgemein')
    geordnet = {k: cfg[k] for k in zuerst if k in cfg}
    geordnet.update((k, v) for k, v in cfg.items() if k not in geordnet)
    return kopf + yaml.safe_dump(geordnet, allow_unicode=True, sort_keys=False, default_flow_style=False)
