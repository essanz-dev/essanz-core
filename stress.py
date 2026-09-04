# -*- coding: utf-8 -*-
"""Stresstest der Bilanz: einzelne Schocks und ein kombiniertes Szenario."""

SZENARIEN = [
    dict(key='zins',   label='Zinsen +2 Punkte',
         beschreibung='Anschlussfinanzierung aller Darlehen zwei Punkte über dem heutigen Satz',
         d_zins=2.0),
    dict(key='miete',  label='Mieten −10 %',
         beschreibung='Mietniveau sinkt dauerhaft um zehn Prozent',
         d_miete=-0.10),
    dict(key='leerstand', label='3 Monate Leerstand',
         beschreibung='Jedes vermietete Objekt steht ein Vierteljahr leer, Kosten laufen weiter',
         d_miete=-0.25),
    dict(key='immo',   label='Immobilienwerte −15 %',
         beschreibung='Bewertungskorrektur am Wohnimmobilienmarkt',
         d_immo=-0.15),
    dict(key='wp',     label='Wertpapiere −30 %',
         beschreibung='Kursrückgang wie 2022, verstärkt durch die Technologielastigkeit',
         d_wp=-0.30),
    dict(key='kombi',  label='Alles zusammen',
         beschreibung='Zinsen +2 Punkte, Mieten −10 %, Immobilien −15 %, Wertpapiere −30 %',
         d_zins=2.0, d_miete=-0.10, d_immo=-0.15, d_wp=-0.30),
]


def build(k, months, forecast):
    cur = months[-1]
    basis = dict(
        key='basis', label='Heute', beschreibung='Ausgangslage zum Stichtag',
        net=k['net'], assets=k['assets'], debt=k['debt'],
        ek_quote=k['eigenkapitalquote'], inv_ltv=k['inv_ltv'], ltv=k['ltv'],
        zins=k['zins12'], miete=k['inv_rent'],
        cashflow=k['inv_cf'], frei=forecast['frei_ende_k'],
    )
    out = [basis]
    for s in SZENARIEN:
        d_zins = s.get('d_zins', 0.0)
        d_miete = s.get('d_miete', 0.0)
        d_immo = s.get('d_immo', 0.0)
        d_wp = s.get('d_wp', 0.0)

        immo_val = k['immo_val'] * (1 + d_immo)
        inv_val = k['inv_val'] * (1 + d_immo)
        wp = k['wp_total'] * (1 + d_wp)
        assets = k['assets'] + (immo_val - k['immo_val']) + (wp - k['wp_total'])
        debt = k['debt']
        net = assets - debt

        zins = k['zins12'] + debt * d_zins / 100
        inv_zins = k['inv_int'] + k['inv_debt'] * d_zins / 100
        miete = k['inv_rent'] * (1 + d_miete)
        nk = k['inv_nk'] * (1 + d_miete if s['key'] == 'leerstand' else 1.0)
        noi = miete + nk - k['inv_cost']
        # Kapitaldienst: Tilgung bleibt, Zins steigt
        annuitaet = k['inv_ann'] + k['inv_debt'] * d_zins / 100
        cashflow = noi - annuitaet
        # Wirkung aufs freie Konto ueber zwoelf Monate
        frei = forecast['frei_ende_k'] + (cashflow - k['inv_cf'])

        out.append(dict(
            key=s['key'], label=s['label'], beschreibung=s['beschreibung'],
            net=net, assets=assets, debt=debt,
            ek_quote=net / assets * 100 if assets else 0,
            inv_ltv=k['inv_debt'] / inv_val * 100 if inv_val else 0,
            ltv=debt / immo_val * 100 if immo_val else 0,
            zins=zins, miete=miete, cashflow=cashflow, frei=frei,
            d_net=net - k['net'], d_cashflow=cashflow - k['inv_cf'],
        ))

    # Wie viel Wertverlust vertraegt die Bilanz?
    puffer = {}
    for ziel in (30.0, 20.0, 0.0):
        # net/assets = ziel/100, wenn Vermoegen um x faellt: (assets-x-debt)/(assets-x) = ziel
        # => assets - x - debt = ziel*(assets-x)  => assets-x-debt = ziel*assets - ziel*x
        # => x*(ziel-1) = ziel*assets - assets + debt  => x = (ziel*assets - assets + debt)/(ziel-1)
        z = ziel / 100
        x = (z * k['assets'] - k['assets'] + k['debt']) / (z - 1)
        puffer[str(int(ziel))] = dict(verlust=x, anteil=x / k['assets'] * 100)
    return dict(szenarien=out, puffer=puffer)
