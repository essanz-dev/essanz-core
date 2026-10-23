#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Erzeugt beispiel.portfolio: eine kleine, komplett frei erfundene .portfolio-Datei im
PPPBV1-Binaerformat, passend zu config.example.yaml. Dient nur zum Ausprobieren von Essanz
ohne eigene Daten — alle Namen, Adressen und Zahlen sind fiktiv.

Kein Teil der Essanz-Bibliothek selbst; ein Hilfsskript, das den binaeren Encoder-Gegenpart
zu ppparse.py implementiert (nur die Teile, die fuer dieses Beispiel gebraucht werden).
"""
import datetime, os

HERE = os.path.dirname(os.path.abspath(__file__))
EPOCH = datetime.date(1970, 1, 1)


def eday(d):
    return (d - EPOCH).days


def esec(d):
    return int(datetime.datetime(d.year, d.month, d.day, tzinfo=datetime.timezone.utc).timestamp())


# ---------------------------------------------------------------------------
# Minimaler Protobuf-Wire-Encoder (Gegenstueck zu ppparse.fields()).
def varint(n):
    n = int(round(n))
    out = bytearray()
    while True:
        b = n & 0x7f
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def tag(field, wiretype):
    return varint((field << 3) | wiretype)


def wv(field, value):
    return tag(field, 0) + varint(value)


def wb(field, data):
    return tag(field, 2) + varint(len(data)) + data


def ws(field, s):
    return wb(field, s.encode('utf-8'))


def we(field, sub):
    return wb(field, sub)


# ---------------------------------------------------------------------------
def account_msg(uuid, name, currency='EUR'):
    return ws(1, uuid) + ws(2, name) + ws(3, currency)


def portfolio_msg(uuid, name):
    return ws(1, uuid) + ws(2, name)


def price_entry(day, price):
    return wv(1, day) + wv(2, price * 1e8)


def security_msg(uuid, name, currency='EUR', prices=()):
    parts = [ws(1, uuid), ws(3, name), ws(4, currency)]
    for day, price in prices:
        parts.append(we(13, price_entry(day, price)))
    return b''.join(parts)


TX_TYPE_INDEX = {'PURCHASE': 0, 'SALE': 1, 'INBOUND_DELIVERY': 2, 'OUTBOUND_DELIVERY': 3,
                  'SECURITY_TRANSFER': 4, 'CASH_TRANSFER': 5, 'DEPOSIT': 6, 'REMOVAL': 7,
                  'DIVIDEND': 8, 'INTEREST': 9, 'INTEREST_CHARGE': 10, 'TAX': 11,
                  'TAX_REFUND': 12, 'FEE': 13, 'FEE_REFUND': 14}


def tx_msg(uuid, ttype, date, account=None, portfolio=None, otherAccount=None,
           otherPortfolio=None, currency='EUR', amount=0.0, shares=0.0, note=None,
           security=None):
    parts = [ws(1, uuid), wv(2, TX_TYPE_INDEX[ttype])]
    if account: parts.append(ws(3, account))
    if portfolio: parts.append(ws(4, portfolio))
    if otherAccount: parts.append(ws(5, otherAccount))
    if otherPortfolio: parts.append(ws(6, otherPortfolio))
    parts.append(we(9, wv(1, esec(date))))
    parts.append(ws(10, currency))
    parts.append(wv(11, amount * 100))
    parts.append(wv(12, shares * 1e8))
    if note: parts.append(ws(13, note))
    if security: parts.append(ws(14, security))
    return b''.join(parts)


# ---------------------------------------------------------------------------
def months_between(d0, d1):
    y, m = d0.year, d0.month
    out = []
    while (y, m) <= (d1.year, d1.month):
        out.append(datetime.date(y, m, 1))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def build(umbenennen=None):
    """umbenennen: {alter Name: neuer Name} fuer Konten, Depots, Wertpapiere (Tests fremder Kontennamen)."""
    N = lambda name: (umbenennen or {}).get(name, name)
    top = []
    START = datetime.date(2024, 9, 1)
    ASOF = datetime.date(2026, 8, 31)
    n = [0]
    def uid(prefix):
        n[0] += 1
        return f'{prefix}-{n[0]}'

    # ---- Konten ----
    acc = dict(
        giro='acc-giro', tagesgeld='acc-tagesgeld',
        immo1='acc-immo1', immo2='acc-immo2', immo3='acc-immo3',
        d1='acc-d1', d2='acc-d2', d3='acc-d3',
    )
    top.append((3, account_msg(acc['giro'], N('Giro'))))
    top.append((3, account_msg(acc['tagesgeld'], N('Tagesgeld'))))
    top.append((3, account_msg(acc['immo1'], N('Immobilie 1: Bergstraße 14'))))
    top.append((3, account_msg(acc['immo2'], N('Immobilie 2: Ahornweg 7'))))
    top.append((3, account_msg(acc['immo3'], N('Immobilie 3: Lindenallee 22'))))
    top.append((3, account_msg(acc['d1'], N('Darlehenskonto 1'))))
    top.append((3, account_msg(acc['d2'], N('Darlehenskonto 2'))))
    top.append((3, account_msg(acc['d3'], N('Darlehenskonto 3'))))

    # ---- Depots ----
    pf_depot = 'pf-depot'
    pf_immo = 'pf-immo'
    top.append((4, portfolio_msg(pf_depot, N('Depot'))))
    top.append((4, portfolio_msg(pf_immo, N('Immobilien'))))

    # ---- Wertpapiere / Immobilien-Wertpapiere mit Kursreihe ----
    months = months_between(START, ASOF)
    etf_prices = [(eday(m), 40.0 + i * 0.5) for i, m in enumerate(months)]
    msci_prices = [(eday(m), 100.0 + i * 0.75) for i, m in enumerate(months)]
    immo1_prices = [(eday(START), 220000.0), (eday(datetime.date(2025, 9, 1)), 226600.0),
                     (eday(datetime.date(2026, 8, 1)), 233400.0)]
    immo2_prices = [(eday(START), 165000.0), (eday(datetime.date(2025, 9, 1)), 169950.0),
                     (eday(datetime.date(2026, 8, 1)), 175050.0)]
    immo3_prices = [(eday(START), 340000.0), (eday(datetime.date(2025, 9, 1)), 350200.0),
                     (eday(datetime.date(2026, 8, 1)), 360700.0)]

    sec = dict(etf='sec-etf', msci='sec-msci', immo1='sec-immo1', immo2='sec-immo2', immo3='sec-immo3')
    top.append((2, security_msg(sec['etf'], N('Globaler Aktien-ETF'), prices=etf_prices)))
    top.append((2, security_msg(sec['msci'], N('MSCI World'), prices=msci_prices)))
    top.append((2, security_msg(sec['immo1'], N('Immobilie 1: Bergstraße 14'), prices=immo1_prices)))
    top.append((2, security_msg(sec['immo2'], N('Immobilie 2: Ahornweg 7'), prices=immo2_prices)))
    top.append((2, security_msg(sec['immo3'], N('Immobilie 3: Lindenallee 22'), prices=immo3_prices)))

    tx = []

    def T(**kw):
        tx.append(tx_msg(uid('tx'), **kw))

    # ---- Eroeffnungssalden ----
    T(ttype='DEPOSIT', date=START, account=acc['giro'], amount=15000.0, note='Eroeffnung')
    T(ttype='DEPOSIT', date=START, account=acc['tagesgeld'], amount=25000.0, note='Eroeffnung')

    # ---- Objekte: Kauf, Darlehen, laufende Buchungen ----
    objekte = [
        dict(no=1, immo=acc['immo1'], dar=acc['d1'], sec=sec['immo1'], kauf=220000.0,
             darlehen=165000.0, miete=950.0, nk=180.0, kosten=120.0, zins=480.0, tilg=250.0,
             selbst=False),
        dict(no=2, immo=acc['immo2'], dar=acc['d2'], sec=sec['immo2'], kauf=165000.0,
             darlehen=115000.0, miete=780.0, nk=150.0, kosten=100.0, zins=360.0, tilg=220.0,
             selbst=False),
        dict(no=3, immo=acc['immo3'], dar=acc['d3'], sec=sec['immo3'], kauf=340000.0,
             darlehen=220000.0, miete=0.0, nk=0.0, kosten=90.0, zins=585.0, tilg=300.0,
             selbst=True),
    ]

    for o in objekte:
        eigenkapital = o['kauf'] - o['darlehen']
        # Darlehensauszahlung: vom Darlehenskonto auf das Objektkonto
        T(ttype='CASH_TRANSFER', date=START, account=o['dar'], otherAccount=o['immo'],
          amount=o['darlehen'], note='Darlehensauszahlung')
        # Eigenkapital: externe Einlage direkt auf das Objektkonto
        T(ttype='DEPOSIT', date=START, account=o['immo'], amount=eigenkapital, note='Eigenkapital')
        # Kauf: Objektkonto zahlt, Anteil geht ins Immobilien-Depot
        T(ttype='PURCHASE', date=START, account=o['immo'], portfolio=pf_immo,
          security=o['sec'], amount=o['kauf'], shares=1.0, note='Kauf')

        for i, m in enumerate(months[1:], start=1):
            d = m
            if not o['selbst']:
                T(ttype='DIVIDEND', date=d, account=o['immo'], security=o['sec'],
                  amount=o['miete'], note='Kaltmiete')
                T(ttype='DEPOSIT', date=d, account=o['immo'], amount=o['nk'],
                  note='Nebenkostenvorauszahlung')
            T(ttype='REMOVAL', date=d, account=o['immo'], amount=o['kosten'],
              note='Hausverwaltung')
            T(ttype='INTEREST_CHARGE', date=d, account=o['dar'], amount=o['zins'],
              note='Sollzinsen')
            T(ttype='CASH_TRANSFER', date=d, account=o['immo'], otherAccount=o['dar'],
              amount=o['zins'] + o['tilg'], note='Annuität')

    # ---- Wertpapierdepot ----
    T(ttype='PURCHASE', date=START, account=acc['giro'], portfolio=pf_depot, security=sec['etf'],
      amount=500 * 40.0, shares=500.0, note='Ersteinstand')
    for i, m in enumerate(months[1:], start=1):
        price = 40.0 + i * 0.5
        shares = round(300.0 / price, 4)
        T(ttype='PURCHASE', date=m, account=acc['giro'], portfolio=pf_depot, security=sec['etf'],
          amount=300.0, shares=shares, note='Sparplan')
        T(ttype='DEPOSIT', date=m, account=acc['giro'], amount=4200.0, note='Gehalt')
        if m.month in (3, 6, 9, 12):
            T(ttype='DIVIDEND', date=m, account=acc['giro'], security=sec['etf'],
              amount=65.0, note='Ausschüttung')

    for t in tx:
        top.append((5, t))

    body = b''.join(we(f, msg) for f, msg in top)
    return b'PPPBV1' + body


if __name__ == '__main__':
    data = build()
    out = os.path.join(os.path.dirname(HERE), 'beispiel.portfolio')
    with open(out, 'wb') as f:
        f.write(data)
    print('geschrieben:', out, len(data), 'Bytes')
