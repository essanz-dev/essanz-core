# -*- coding: utf-8 -*-
"""Liquiditaetsvorschau.

Grundlage sind drei Quellen, in dieser Rangfolge:
  1. In Portfolio Performance geplante Buchungen (je Konto und Monat, wo vorhanden)
  2. Fortgeschriebene Dauerauftraege aus den letzten sechs Monaten (fuer alles uebrige)
  3. Ein konservativer Aufschlag: Sondervorgaenge der letzten sechs Monate, soweit sie
     Abfluesse waren, als Dauerlast fortgeschrieben. Ergibt die untere Kante der Bandbreite.
"""

from collections import defaultdict

HORIZONT_MONATE = 12
EINMALIG = 3000.0
BASIS_MONATE = 6
# Eine Buchung gilt als Dauerauftrag, wenn sie in mindestens so vielen der Basismonate vorkommt
# und ihr Betrag dabei um hoechstens BETRAG_TOLERANZ vom Median abweicht.
WIEDERKEHR_MIN = 4
BETRAG_TOLERANZ = 0.25


def _monate(start, n):
    y, m = int(start[:4]), int(start[5:7])
    out = []
    for _ in range(n):
        out.append('%04d-%02d' % (y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _wirkung(t):
    ty = t['type']; out = []
    if ty == 'PURCHASE':
        out = [(t['account'], -t['amount'])]
    elif ty == 'SALE':
        out = [(t['account'], +t['amount'])]
    elif ty == 'CASH_TRANSFER':
        out = [(t['account'], -t['amount']), (t['otherAccount'], +t['amount'])]
    elif ty in ('DEPOSIT', 'DIVIDEND', 'INTEREST', 'TAX_REFUND', 'FEE_REFUND'):
        out = [(t['account'], +t['amount'])]
    elif ty in ('REMOVAL', 'INTEREST_CHARGE', 'TAX', 'FEE'):
        out = [(t['account'], -t['amount'])]
    return [(a, v) for a, v in out if a]


def build(b, snap, months, label=None):
    asof = b.asof
    if label is None:
        label = lambda u: b.acc[u]['name'] if u in b.acc else str(u)

    def einmalig(t):
        note = (t['note'] or '').lower()
        return (t['amount'] >= EINMALIG
                or any(w in note for w in b.CAPEX_WORDS)
                or any(w in note for w in b.CAPITAL_WORDS))

    horizont = _monate(asof[:7], HORIZONT_MONATE + 1)[1:]

    # 1. Geplante Buchungen
    geplant = defaultdict(lambda: defaultdict(float))
    plan_monate = defaultdict(set)
    n_geplant = 0
    for t in b.tx:
        if t['date'] <= asof or t['date'][:7] not in horizont:
            continue
        n_geplant += 1
        for a, v in _wirkung(t):
            geplant[t['date'][:7]][a] += v
            plan_monate[a].add(t['date'][:7])

    # 2. und 3. Profile aus der Vergangenheit.
    # Nur abgeschlossene Monate; der laufende Monat ist am Stichtag noch unvollstaendig
    # und wuerde die Monatsraten nach unten verzerren.
    voll = [m['month'] for m in months if m['month'] < asof[:7]]
    basis = voll[-BASIS_MONATE:]

    def _basis_key(t):
        """Vorgangsart, Konto, Gegenkonto, Wertpapier. Bewusst OHNE Buchungstext: ein Vermerk,
        der in einem Monat gesetzt und im naechsten weggelassen wird, darf eine Serie nicht
        auseinanderreissen. Getrennt wird stattdessen ueber die Betragshoehe."""
        return (t['type'], t['account'], t.get('otherAccount'), t.get('security'))

    fenster = [t for t in b.tx if t['date'] <= asof and t['date'][:7] in basis]

    # Innerhalb eines Basisschluessels werden die Buchungen nach Betragshoehe gruppiert. So
    # bleibt die monatliche Einlage von 1.000 Euro eine Reihe, waehrend Sanierungsrechnungen
    # von 500 bis 12.500 Euro auf demselben Konto in getrennte Reihen fallen und damit nicht
    # als Dauerauftrag durchgehen.
    nach_basis = defaultdict(list)
    for t in fenster:
        nach_basis[_basis_key(t)].append(t)
    cluster_of = {}
    for bk, ts in nach_basis.items():
        gruppen = []                                  # je Gruppe: [kleinster Betrag, Buchungen]
        for t in sorted(ts, key=lambda x: abs(x['amount'])):
            a = abs(t['amount'])
            if gruppen and a <= gruppen[-1][0] * (1 + BETRAG_TOLERANZ) + 1.0:
                gruppen[-1][1].append(t)
            else:
                gruppen.append([a, [t]])
        for i, (_, gruppe) in enumerate(gruppen):
            for t in gruppe:
                cluster_of[id(t)] = i

    def _key(t):
        return _basis_key(t) + (cluster_of[id(t)],)

    je_reihe = defaultdict(lambda: defaultdict(float))   # (Vorgang, Konto) -> Monat -> Betrag
    tx_je_key = defaultdict(list)
    for t in fenster:
        k = _key(t)
        tx_je_key[k].append(t)
        for a, v in _wirkung(t):
            je_reihe[(k, a)][t['date'][:7]] += v

    def _median(xs):
        xs = sorted(xs); n = len(xs)
        return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2

    lauf = defaultdict(float)
    sonder = defaultdict(lambda: defaultdict(float))   # Konto -> Monat -> Sonderposten
    einmalige = []
    dauer = []
    for (k, a), je_monat in je_reihe.items():
        werte = [je_monat.get(m, 0.0) for m in basis]
        treffer = sum(1 for v in werte if abs(v) > 0.005)
        rate = _median(werte)
        # Ein Dauerauftrag wiederholt sich nicht nur, er ist auch der Hoehe nach stabil.
        # Sonst wuerden mehrere unabhaengige Einmalzahlungen auf demselben Konto — etwa
        # Sanierungsrechnungen in vier verschiedenen Monaten — als Monatsrate fortgeschrieben.
        toleranz = max(abs(rate) * BETRAG_TOLERANZ, 25.0)
        stabil = sum(1 for v in werte if abs(v - rate) <= toleranz and abs(v) > 0.005)
        if treffer >= WIEDERKEHR_MIN and stabil >= WIEDERKEHR_MIN and abs(rate) > 0.005:
            # Der Median haelt einen Ausreissermonat aus der Rate heraus, der Rest wandert
            # in die Sonderposten und damit nur in die konservative Kante.
            lauf[a] += rate
            for m, v in zip(basis, werte):
                sonder[a][m] += v - rate
            if abs(rate) > 1.0:
                dauer.append(dict(konto=label(a),
                                  typ=k[0], rate=round(rate, 2),
                                  monate=treffer, stabil=stabil))
        else:
            for m, v in zip(basis, werte):
                sonder[a][m] += v
            for t in tx_je_key[k]:
                if abs(t['amount']) >= 250 and t['account'] == a:
                    einmalige.append(dict(datum=t['date'], typ=t['type'], betrag=round(t['amount'], 2),
                                          konto=label(a),
                                          text=(t['note'] or '')[:60]))
    lauf = {a: v for a, v in lauf.items() if abs(v) > 1.0}
    # Konservative Kante: unregelmaessige Ausgaben laufen im *typischen* Monatsumfang weiter.
    # Der Median statt des Durchschnitts ist hier entscheidend — sonst wuerde eine einzelne
    # Sanierungsrechnung von 99.000 Euro als Dauerlast von 16.500 Euro im Monat fortgeschrieben
    # und die Vorschau waere unbrauchbar. Nur die Abflussseite wird unterstellt, Zufluesse nicht.
    sonder_summe = {a: sum(je.values()) for a, je in sonder.items()}
    sonder = {a: min(_median([je.get(m, 0.0) for m in basis]), 0.0) for a, je in sonder.items()}
    sonder = {a: v for a, v in sonder.items() if v < -1.0}
    einmalige.sort(key=lambda x: -abs(x['betrag']))
    dauer.sort(key=lambda x: x['rate'])
    # Was in den Basismonaten tatsaechlich an Einmaligem abgeflossen ist — nicht fortgeschrieben,
    # aber die Zahl gehoert daneben, damit die Vorschau nicht harmloser wirkt, als die Lage ist.
    einmalig_abfluss = -sum(v for a, v in sonder_summe.items()
                            if v < 0 and b.acc_group.get(a) != 'Darlehen')

    def gruppen(stand):
        g = defaultdict(float)
        for a, v in stand.items():
            g[b.acc_group.get(a, 'Liquidität')] += v
        return g

    reihe = []
    stand = dict(snap['cash'])
    stand_k = dict(snap['cash'])
    for m in horizont:
        konten = set(list(lauf) + list(geplant[m]) + list(sonder))
        for a in konten:
            if m in plan_monate.get(a, ()):
                v = geplant[m].get(a, 0.0)
            else:
                v = lauf.get(a, 0.0)
            stand[a] = stand.get(a, 0.0) + v
            stand_k[a] = stand_k.get(a, 0.0) + v + sonder.get(a, 0.0)
        g, gk = gruppen(stand), gruppen(stand_k)
        reihe.append(dict(
            month=m,
            quelle='geplant' if any(m in plan_monate.get(a, ()) for a in konten) else 'fortgeschrieben',
            frei=round(g['Liquidität'] + g['Krypto-Konten'], 2),
            frei_k=round(gk['Liquidität'] + gk['Krypto-Konten'], 2),
            objektkonten=round(g['Immobilien-Konten'], 2),
            objektkonten_k=round(gk['Immobilien-Konten'], 2),
            p2p=round(g['P2P'], 2),
            gesamt=round(g['Liquidität'] + g['Krypto-Konten'] + g['Immobilien-Konten'] + g['P2P'], 2),
            gesamt_k=round(gk['Liquidität'] + gk['Krypto-Konten'] + gk['Immobilien-Konten'] + gk['P2P'], 2),
            konten={a: round(v, 2) for a, v in stand_k.items() if b.acc_group.get(a) != 'Darlehen'},
        ))

    warnungen = []
    for a in set(k for r in reihe for k in r['konten']):
        werte = [(r['month'], r['konten'].get(a, 0.0)) for r in reihe]
        tief = min(werte, key=lambda x: x[1])
        if tief[1] < -1:
            warnungen.append(dict(konto=label(a), gruppe=b.acc_group.get(a),
                                  heute=round(snap['cash'].get(a, 0.0), 2),
                                  tiefstand=round(tief[1], 2), monat=tief[0]))
    warnungen.sort(key=lambda w: w['tiefstand'])

    frei_start = sum(v for a, v in snap['cash'].items()
                     if b.acc_group.get(a) in ('Liquidität', 'Krypto-Konten'))
    tief_frei = min(reihe, key=lambda r: r['frei_k'])
    return dict(
        horizont=horizont, reihe=reihe, warnungen=warnungen,
        n_geplant=n_geplant,
        planende=max((t['date'] for t in b.tx if t['date'] > asof), default=None),
        basis_von=basis[0], basis_bis=basis[-1], basis_monate=len(basis),
        wiederkehr_min=WIEDERKEHR_MIN, einmalige=einmalige[:12], dauerauftraege=dauer,
        einmalig_abfluss=round(einmalig_abfluss, 2),
        einmalig_saldo=round(sum(e['betrag'] * (1 if e['typ'] in ('SALE', 'DEPOSIT', 'DIVIDEND', 'INTEREST', 'TAX_REFUND', 'FEE_REFUND') else -1)
                                 for e in einmalige), 2),
        konten_fortgeschrieben=sorted({b.acc[a]['name'] for a in lauf
                                       if a not in plan_monate and b.acc_group.get(a) != 'Darlehen'}),
        sonder_je_monat=round(sum(v for a, v in sonder.items()
                                  if b.acc_group.get(a) != 'Darlehen'), 2),
        frei_start=round(frei_start, 2),
        frei_ende=reihe[-1]['frei'], frei_ende_k=reihe[-1]['frei_k'],
        frei_tief=tief_frei['frei_k'], frei_tief_monat=tief_frei['month'],
        objekt_start=round(sum(v for a, v in snap['cash'].items()
                               if b.acc_group.get(a) == 'Immobilien-Konten'), 2),
        objekt_ende=reihe[-1]['objektkonten'], objekt_ende_k=reihe[-1]['objektkonten_k'],
        gesamt_ende=reihe[-1]['gesamt'], gesamt_ende_k=reihe[-1]['gesamt_k'],
    )
