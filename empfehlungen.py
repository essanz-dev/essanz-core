# -*- coding: utf-8 -*-
"""Leitet Handlungsempfehlungen aus den Kennzahlen ab.

Das ist eine bewusst generische Neufassung fuer die Open-Source-Version. Die Regeln folgen
denselben Schwellen wie schwellen.py, aber der Text ist allgemein gehalten — keine
Objektnamen, keine erzaehlerische Einordnung einer einzelnen Situation. Wer eine
persoenlichere, ausfuehrlichere Kommentierung moechte, kann diese Datei durch eine eigene
Fassung ersetzen; make_dashboard.py erwartet nur build(data) -> (html, liste).
"""
import html


def _de(v, d):
    return (f'{v:,.{d}f}'.replace(',', '\x01').replace('.', ',')
            .replace('\x01', '.').replace('-', '−'))


def e(v, d=0):
    return _de(v, d) + ' €'


def p(v, d=1):
    return _de(v, d) + ' %'


def build(data):
    k = data['kpi']; objs = data['objects']
    pos = [x for x in data['positions'] if x['group'] != 'Immobilien']
    recs = []

    # 1) Liquiditätspuffer
    monat = k['annuitaet12'] / 12 if k.get('annuitaet12') else 0.0
    ziel_lo, ziel_hi = monat * 3, monat * 6
    if monat and k['free_cash'] < ziel_lo:
        recs.append(dict(pri='hoch', t='Der frei verfügbare Liquiditätspuffer ist zu dünn',
            body=[
              f'Auf den frei verfügbaren Konten liegen <strong>{e(k["free_cash"])}</strong>, '
              f'dem steht ein monatlicher Kapitaldienst von <strong>{e(monat)}</strong> gegenüber.',
              f'Üblich sind drei bis sechs Monatsraten als Reserve, also '
              f'<strong>{e(ziel_lo)}</strong> bis <strong>{e(ziel_hi)}</strong>. Diese Reserve '
              'sollte getrennt von den Objektkonten liegen, damit im Dashboard sichtbar bleibt, '
              'was wirklich frei verfügbar ist.'],
            facts=[('Frei verfügbar', e(k['free_cash'])), ('Kapitaldienst je Monat', e(monat)),
                   ('Zielreserve', f'{e(ziel_lo)} – {e(ziel_hi)}')]))

    # 2) Hoch beliehene Objekte
    hoch = sorted([o for o in objs if (o['ltv'] or 0) > 85], key=lambda x: -(x['ltv'] or 0))
    if hoch:
        o = hoch[0]
        recs.append(dict(pri='hoch' if o['ltv'] > 95 else 'mittel',
            t=f'Objekt {o["no"]} ist mit {p(o["ltv"],0)} vergleichsweise hoch beliehen',
            body=[
              f'Bei einem Verkehrswert von {e(o["value"])} und {e(o["loan"])} Restschuld bleiben '
              f'nur <strong>{e(o["equity"])}</strong> Eigenkapital.',
              'Solange die Zinsbindung läuft, ist das kein akutes Problem — bei einer '
              'Anschlussfinanzierung oder Neubewertung durch die Bank aber sehr wohl, weil '
              'oberhalb von 80 % Beleihung meist deutlich schlechtere Konditionen gelten.'],
            facts=[('Beleihung', p(o['ltv'])), ('Eigenkapital', e(o['equity'])),
                   ('Bis 80 % Beleihung', e(max(0, o['loan'] - 0.8 * o['value']))),
                   ('Cashflow 12M', e(o['cashflow12']))]))

    # 3) Kapitaldienstdeckung der Kapitalanlagen
    if k.get('dscr') is not None and k['dscr'] < 1.2:
        recs.append(dict(pri='hoch' if k['dscr'] < 1.05 else 'mittel',
            t='Die Kapitaldienstdeckung der vermieteten Objekte ist knapp',
            body=[
              f'Nettomieteinnahmen geteilt durch Kapitaldienst ergibt aktuell '
              f'<strong>{k["dscr"]:.2f}</strong>. Werte unter 1,20 gelten als eng, unter 1,05 '
              'trägt sich das Portfolio nicht mehr sicher aus sich selbst — jede '
              'Mietausfall- oder Reparaturphase muss dann von anderswo kommen.',
              f'Nettomieteinnahmen: {e(k["inv_noi"])}, Kapitaldienst: {e(k["inv_ann"])}.'],
            facts=[('DSCR', f'{k["dscr"]:.2f}'), ('Nettomieteinnahmen', e(k['inv_noi'])),
                   ('Kapitaldienst', e(k['inv_ann']))]))

    # 4) Zinsänderungsrisiko bei günstigen Darlehen
    guenstig = [l for l in data.get('darlehen', [])
                if l['saldo'] > 0 and l['zinssatz'] is not None and l['zinssatz'] < 2.0]
    if guenstig:
        vol = sum(l['saldo'] for l in guenstig)
        ist = sum(l['zins_runrate'] for l in guenstig)
        neu = vol * 0.04
        recs.append(dict(pri='mittel', t='Zinsänderungsrisiko bei günstig finanzierten Darlehen',
            body=[
              f'Auf {len(guenstig)} Darlehen mit zusammen <strong>{e(vol)}</strong> liegt der '
              f'Zins aktuell unter zwei Prozent ({e(ist)} im Jahr). Läuft die Bindung aus und '
              f'wird zu vier Prozent verlängert, steigt der Zinsaufwand dafür auf rund '
              f'<strong>{e(neu)}</strong> — ein Mehraufwand von etwa {e(neu - ist)} im Jahr.',
              'Ohne hinterlegte Zinsbindungsfristen bleibt dieses Risiko unsichtbar. Sie lassen '
              'sich in der Konfiguration je Darlehenskonto eintragen (siehe config.example.yaml), '
              'dann erscheint hier auch eine Fälligkeitsleiste.'],
            facts=[('Günstige Darlehen', e(vol)), ('Zins heute', e(ist)),
                   ('Zins bei 4 %', e(neu)), ('Mehraufwand', e(neu - ist))]))

    # 5) Klumpenrisiko Wertpapiere
    wp = k['wp_total']
    if wp and k['top5'] > 45:
        recs.append(dict(pri='mittel', t='Das Wertpapierdepot ist stark konzentriert',
            body=[
              f'Die fünf größten Positionen machen <strong>{p(k["top5"], 0)}</strong> des '
              f'Wertpapiervermögens von {e(wp)} aus. Ein einzelnes Thema oder eine einzelne '
              'Position bestimmt damit einen großen Teil der Wertentwicklung.',
              f'Größte Einzelposition: {k["top1_name"]} mit {p(k["top1"])}.'],
            facts=[('Top 5', p(k['top5'])), ('Größte Position', p(k['top1']) + ' · ' + k['top1_name']),
                   ('Positionen gesamt', str(k['n_pos'])), ('Wertpapiere gesamt', e(wp))]))

    # 6) Instandhaltungsrücklage
    soll = k.get('ruecklage_soll') or 0.0
    quote = k.get('ruecklage_quote')
    if soll and quote is not None and quote < 50:
        recs.append(dict(pri='mittel', t='Die Instandhaltungsrücklage deckt den Bestand nicht ab',
            body=[
              f'Auf den Objektkonten liegen <strong>{e(k["immo_konten"])}</strong>, die '
              f'nach Wohnfläche gerechnete Sollrücklage läge bei <strong>{e(soll)}</strong> im Jahr.',
              'Eine regelmäßige Überweisung auf ein eigenes Rücklagenkonto macht diese Kosten '
              'planbar und verhindert, dass die nächste größere Reparatur ungeplant das übrige '
              'Vermögen angreift.'],
            facts=[('Guthaben Objektkonten', e(k['immo_konten'])), ('Sollrücklage p.a.', e(soll)),
                   ('Deckungsgrad', p(quote))]))

    # 7) Immobilienanteil am Vermögen
    anteil = k.get('immo_anteil')
    if anteil is not None and anteil > 85:
        recs.append(dict(pri='niedrig', t='Das Vermögen ist stark auf Immobilien konzentriert',
            body=[
              f'Immobilien machen <strong>{p(anteil,0)}</strong> des Nettovermögens aus '
              '(gerechnet mit dem Eigenkapital, nicht dem Verkehrswert). Das kann gewollt sein '
              '— die Zahl steht hier, damit die Entscheidung sichtbar bleibt und nicht unbemerkt '
              'weiterläuft.'],
            facts=[('Immobilienanteil', p(anteil))]))

    # 8) Monatsroutine
    recs.append(dict(pri='niedrig', t='Für das monatliche Update',
        body=[
          'Damit die Zahlen belastbar bleiben, lohnt es sich vor jedem Update: die Kurse in '
          'Portfolio Performance aktualisieren, die Verkehrswerte der Immobilien regelmäßig '
          'nachziehen (z. B. einmal im Quartal) und die Darlehensstände mit den Bankauszügen '
          'abgleichen.'],
        facts=[]))

    out = []
    for i, r in enumerate(recs, 1):
        f = ''.join(f'<span><strong>{html.escape(a)}:</strong> {b}</span>' for a, b in r['facts'])
        out.append(
            f'<div class="rec"><h3><span class="pri {r["pri"]}">{r["pri"].upper()}</span>'
            f'{i}. {r["t"]}</h3>' + ''.join(f'<p>{b}</p>' for b in r['body']) +
            (f'<div class="facts">{f}</div>' if f else '') + '</div>')
    return '\n'.join(out), recs
