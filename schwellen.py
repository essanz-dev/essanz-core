# -*- coding: utf-8 -*-
"""Zielwerte, Ampelbewertung, Glossar und Lesepfade.

Hier stehen die Massstaebe, an denen die Kennzahlen gemessen werden. Sie sind bewusst an
einer Stelle gebuendelt und nicht ueber die Auswertung verteilt — wer den Massstab aendern
will, aendert ihn hier und nirgends sonst.

Konvention je Eintrag:
    schluessel      Kennzahl in kpi
    label           Beschriftung
    format          'eur' | 'pct' | 'x' | 'mon'
    richtung        'hoch' = groesser ist besser, 'runter' = kleiner ist besser
    gruen, gelb     Schwellen. Bei richtung 'hoch': >= gruen ist gruen, >= gelb ist gelb,
                    darunter rot. Bei 'runter' umgekehrt.
    ziel            Klartext des Zielwerts
    warum           Ein Satz, warum diese Schwelle gilt und wer sie anlegt
"""

# Faustregel fuer den Liquiditaetspuffer: so viele Monatsraten sollen frei verfuegbar sein.
PUFFER_MONATE_GRUEN = 3.0
PUFFER_MONATE_GELB = 1.5

REGELN = [
    dict(key='dscr', label='Kapitaldienstdeckung', format='x', richtung='hoch',
         gruen=1.20, gelb=1.05,
         ziel='mindestens 1,20',
         warum='Nettomieteinnahmen geteilt durch Kapitaldienst. Banken rechnen diese Zahl bei '
               'jeder Finanzierung. Unter 1,05 trägt sich das Portfolio nicht mehr aus sich '
               'selbst, jede Mietausfall- oder Reparaturwoche muss dann aus dem Gehalt kommen.'),
    dict(key='eigenkapitalquote', label='Eigenkapitalquote', format='pct', richtung='hoch',
         gruen=30.0, gelb=20.0,
         ziel='mindestens 30 %',
         warum='Nettovermögen geteilt durch Gesamtvermögen. Ab etwa 30 % gilt eine private '
               'Immobilienbilanz als solide finanziert, unter 20 % wird jede weitere '
               'Finanzierung teuer oder unmöglich.'),
    dict(key='inv_ltv', label='Beleihung der Kapitalanlagen', format='pct', richtung='runter',
         gruen=70.0, gelb=85.0,
         ziel='höchstens 70 %',
         warum='Restschuld geteilt durch Verkehrswert. Bis 60 % gibt es die besten '
               'Konditionen, ab 80 % steigt der Zinsaufschlag deutlich. Der Wert hängt an '
               'euren eigenen Verkehrswertschätzungen — er ist nur so belastbar wie die.'),
    dict(key='free_cash', label='Frei verfügbarer Puffer', format='eur', richtung='hoch',
         gruen_key='puffer_ziel', gelb_key='puffer_ziel_gelb',
         gruen=0.0, gelb=0.0,
         ziel_key='puffer_ziel_text', ziel='mindestens drei Monatsraten',
         warum='Guthaben auf den frei verfügbaren Konten, gemessen an der monatlichen Annuität '
               'aller Darlehen. Das Guthaben auf den Objektkonten zählt nicht mit, weil es für '
               'Nebenkosten und Instandhaltung gebunden ist. Als Monatsraten ausgedrückt steht '
               'die Zahl auch in der Kachelzeile darüber.'),
    dict(key='frei_tief', label='Tiefstand der Vorschau', format='eur', richtung='hoch',
         gruen=5000.0, gelb=0.0,
         ziel='bleibt über 5.000 €',
         warum='Niedrigster Stand des frei verfügbaren Guthabens in der konservativen Kante '
               'der Zwölfmonatsvorschau. Unter null bedeutet: Dispo oder Verkauf.'),
    dict(key='top1', label='Größte Depotposition', format='pct', richtung='runter',
         gruen=15.0, gelb=25.0,
         ziel='höchstens 15 % des Kapitalvermögens',
         warum='Ein einzelnes Papier sollte das Depot nicht bestimmen. Über 25 % hängt die '
               'Wertentwicklung des gesamten Kapitalvermögens an einer einzigen Entscheidung.'),
    dict(key='immo_anteil', label='Immobilienanteil am Vermögen', format='pct', richtung='runter',
         gruen=70.0, gelb=85.0,
         ziel='höchstens 70 %',
         warum='Immobilien sind illiquide und regional konzentriert. Gerechnet wird mit dem '
               'Eigenkapital (Verkehrswert minus Darlehen), nicht mit dem Verkehrswert, damit '
               'der Vergleich mit dem ungehebelten übrigen Vermögen fair bleibt. Ein hoher '
               'Anteil ist bei eurem Modell gewollt — die Zahl steht hier, damit die '
               'Entscheidung sichtbar bleibt und nicht unbemerkt weiterläuft.'),
    dict(key='immo_konten', label='Rücklage auf den Objektkonten', format='eur', richtung='hoch',
         gruen_key='ruecklage_soll', gelb_key='ruecklage_soll_halb',
         gruen=0.0, gelb=0.0,
         ziel_key='ruecklage_ziel_text', ziel='mindestens eine Jahresrücklage',
         warum='Guthaben aller Objektkonten gemessen an einer nach Quadratmetern gerechneten '
               'Jahresrücklage (1,10 €/m² und Monat für Altbau vor 1948, 0,80 €/m² für Neubau '
               'ab 1948 — eine begründete Faustregel, kein Gutachten). '
               'Vorsicht bei der Auslegung: auf diesen Konten liegen auch '
               'Nebenkostenvorauszahlungen der Mieter und noch nicht verbaute Darlehensmittel. '
               'Grün heißt hier „Geld ist da", nicht „Geld ist frei". Auf dem eigens dafür '
               'geführten Rücklagenkonto liegt deutlich weniger.'),
]

GLOSSAR = [
    ('Annuität', 'Die feste monatliche Rate an die Bank. Sie besteht aus Zins und Tilgung. '
                 'Der Zinsanteil sinkt über die Laufzeit, der Tilgungsanteil steigt.'),
    ('Kapitaldienst', 'Alles, was im Jahr an die Banken fließt — also die Summe aller '
                      'Annuitäten. Nicht zu verwechseln mit dem Zinsaufwand, der nur der '
                      'Kostenanteil davon ist.'),
    ('Kapitaldienstdeckung (DSCR)',
     'Nettomieteinnahmen geteilt durch Kapitaldienst. Sagt, wie oft die Mieten die Rate an '
     'die Bank decken. 1,0 heißt: es geht genau auf, ohne Reserve.'),
    ('Beleihungsauslauf (LTV)',
     'Restschuld geteilt durch Verkehrswert. Je niedriger, desto günstiger die Konditionen.'),
    ('AfA', 'Absetzung für Abnutzung — die jährliche Abschreibung des Gebäudes, meist 2 oder '
            '2,5 Prozent der Gebäudekosten. Sie mindert die Steuer, kostet aber kein Geld. '
            'Nur bei Vermietung, nicht bei Eigennutzung.'),
    ('NOI', 'Net Operating Income: Kaltmiete plus umgelegte Nebenkosten minus '
            'Bewirtschaftungskosten. Das Ergebnis des Objekts vor Finanzierung und Steuern.'),
    ('Bruttomietrendite', 'Jahreskaltmiete geteilt durch Verkehrswert. Ohne Kosten, ohne '
                          'Finanzierung — eine grobe Vergleichszahl zwischen Objekten.'),
    ('Nettomietrendite', 'Wie oben, aber nach Bewirtschaftungskosten. Näher an der Wahrheit.'),
    ('Eigenkapitalrendite', 'Überschuss nach Zinsen geteilt durch das eingesetzte oder heute '
                            'gebundene Eigenkapital. Steigt mit dem Fremdkapitalanteil, solange '
                            'die Objektrendite über dem Sollzins liegt — der Hebel wirkt aber '
                            'in beide Richtungen.'),
    ('IRR', 'Interner Zinsfuß: die Rendite pro Jahr, die alle tatsächlichen Ein- und '
            'Auszahlungen samt heutigem Wert auf null bringt. Berücksichtigt anders als die '
            'Eigenkapitalrendite auch den Zeitpunkt jeder Zahlung.'),
    ('TWR', 'Zeitgewichtete Rendite: die reine Anlageleistung des Depots, bereinigt um Ein- '
            'und Auszahlungen. So vergleicht man sich mit einem Index.'),
    ('Grenzsteuersatz', 'Der Satz auf den nächsten verdienten Euro. Mit ihm rechnet man, was '
                        'eine zusätzliche Einnahme kostet oder ein zusätzlicher Werbungskosten'
                        'posten spart — nicht mit dem Durchschnittssatz.'),
    ('Modifizierte Dietz', 'Das Verfahren, mit dem die Monatsrendite des Depots aus Anfangs- '
                           'und Endwert und den unterjährigen Zahlungen geschätzt wird.'),
    ('Run-Rate', 'Die letzte Monatsrate mal zwölf. Zeigt die heutige Belastung, während der '
                 'Zwölfmonatswert die Vergangenheit zeigt — bei unterjährig ausgezahlten '
                 'Darlehen liegen die beiden weit auseinander.'),
]

LESEPFADE = [
    dict(titel='Bankgespräch',
         text='Überblick, Immobilien und Darlehen. Dort stehen Bilanz, Beleihung, '
              'Kapitaldienstdeckung und jede einzelne Tranche. Für den Termin selbst die '
              'PDF-Vermögensaufstellung mitnehmen, nicht das Dashboard.',
         reiter=['ueberblick', 'immobilien', 'risiko']),
    dict(titel='Steuerberater',
         text='Die Steuersicht mit dem Abgleich zur letzten Erklärung und der Entwicklung '
              'über die Jahre. Platz auch für offene Punkte wie Gebäudeanteil oder '
              'Sanierungsabzüge, die im Einzelfall noch zu klären sind.',
         reiter=['steuern']),
    dict(titel='Monatsupdate',
         text='Liquidität und Risiko für die Vorschau, danach die Empfehlungen. Die '
              'Veränderung zum Vormonat steht oben auf jeder Kachel.',
         reiter=['risiko', 'empfehlungen']),
    dict(titel='Einmal komplett',
         text='Von links nach rechts durch alle sechs Reiter. Dauert etwa zwanzig Minuten '
              'und lohnt sich einmal im Quartal.',
         reiter=[]),
]


def _stufe(regel, wert):
    if wert is None:
        return 'unbekannt'
    if regel['richtung'] == 'hoch':
        return 'gruen' if wert >= regel['gruen'] else ('gelb' if wert >= regel['gelb'] else 'rot')
    return 'gruen' if wert <= regel['gruen'] else ('gelb' if wert <= regel['gelb'] else 'rot')


def build(kpi, vorschau, vergleich=None):
    """Ergaenzt abgeleitete Kennzahlen und bewertet alle Regeln."""
    # Puffer in Monatsraten
    rate = kpi['annuitaet12'] / 12 if kpi.get('annuitaet12') else 0.0
    kpi['monatsrate'] = rate
    kpi['puffer_monate'] = kpi['free_cash'] / rate if rate else None
    kpi['puffer_ziel'] = rate * PUFFER_MONATE_GRUEN
    kpi['puffer_ziel_gelb'] = rate * PUFFER_MONATE_GELB
    kpi['puffer_ziel_text'] = ('mindestens %.0f Monatsraten, also %s €'
                               % (PUFFER_MONATE_GRUEN,
                                  f'{rate * PUFFER_MONATE_GRUEN:,.0f}'.replace(',', '.')))
    kpi['puffer_luecke'] = max(0.0, rate * PUFFER_MONATE_GRUEN - kpi['free_cash'])
    kpi['immo_anteil'] = kpi['immo_equity'] / kpi['net'] * 100 if kpi.get('net') else None
    # Sollrücklage: aus den Objektstammdaten (Wohnflächen) je Quadratmeter gerechnet
    # (siehe config.py/analyze.py, kpi['ruecklage_soll_m2']); nur wo für ein Objekt keine
    # Wohnfläche in der Konfiguration hinterlegt ist, fällt die alte Ein-Prozent-Faustregel
    # für dieses Objekt ersatzweise auf den Verkehrswert zurück.
    soll_m2 = kpi.get('ruecklage_soll_m2') or 0.0
    soll_pauschal = kpi['inv_val'] * 0.01
    soll = soll_m2 if soll_m2 else soll_pauschal
    kpi['ruecklage_soll'] = soll
    kpi['ruecklage_soll_pauschal'] = soll_pauschal
    kpi['ruecklage_quote'] = kpi['immo_konten'] / soll * 100 if soll else None
    kpi['ruecklage_soll_halb'] = soll / 2
    kpi['ruecklage_ziel_text'] = ('mindestens %s €' % f'{soll:,.0f}'.replace(',', '.'))
    kpi['frei_tief'] = vorschau['frei_tief']

    ampeln = []
    for r in REGELN:
        # Schwellen koennen auf eine andere Kennzahl zeigen, wenn sie sich aus den Daten ergeben.
        if 'gruen_key' in r:
            r = dict(r, gruen=kpi.get(r['gruen_key'], r['gruen']),
                     gelb=kpi.get(r['gelb_key'], r['gelb']))
        if 'ziel_key' in r:
            r = dict(r, ziel=kpi.get(r['ziel_key'], r['ziel']))
        wert = kpi.get(r['key'])
        stufe = _stufe(r, wert)
        v = (vergleich or {}).get('werte', {}).get(r['key'])
        bau = HERLEITUNG.get(r['key'])
        ampeln.append(dict(r, wert=wert, stufe=stufe,
                           delta=v['delta'] if v else None,
                           rechnung=bau(kpi, vorschau) if bau else [],
                           quelle=QUELLEN.get(r['key'], '')))
    zahl = lambda st: sum(1 for a in ampeln if a['stufe'] == st)
    return dict(ampeln=ampeln, n_rot=zahl('rot'), n_gelb=zahl('gelb'), n_gruen=zahl('gruen'))


# ---------------------------------------------------------------------------
# Herleitung je Kennzahl: die Rechnung Schritt fuer Schritt, mit denselben Zahlen,
# die auch in den Tabellen stehen. Jede Zeile ist (Beschriftung, Wert, Format, Art);
# Art steuert nur die Darstellung: '' normal, 'summe' Zwischensumme, 'ergebnis' Endwert,
# 'info' Zusatzangabe ohne Rechenbezug.
# ---------------------------------------------------------------------------

def _z(label, wert, fmt, art=''):
    return dict(label=label, wert=wert, format=fmt, art=art)


HERLEITUNG = {
    'dscr': lambda k, v: [
        _z('Kaltmiete der vermieteten Objekte (aktueller Monat × 12)', k['inv_rent_run'], 'eur'),
        _z('zuzüglich umgelegte Nebenkosten (aktueller Monat × 12)', k['inv_nk_run'], 'eur'),
        _z('abzüglich Bewirtschaftungskosten (letzte 12 Monate)', -k['inv_cost'], 'eur'),
        _z('Nettomieteinnahmen', k['inv_rent_run'] + k['inv_nk_run'] - k['inv_cost'], 'eur', 'summe'),
        _z('geteilt durch Kapitaldienst der vermieteten Objekte (letzte 12 Monate)', k['inv_ann'], 'eur'),
        _z('Kapitaldienstdeckung', k['dscr'], 'x', 'ergebnis'),
        _z('darin Zinsanteil', k['inv_int'], 'eur', 'info'),
        _z('darin Tilgungsanteil', k['inv_red'], 'eur', 'info'),
        _z('Überschuss nach Kapitaldienst (mit hochgerechneter Kaltmiete/Nebenkosten)',
           k['inv_rent_run'] + k['inv_nk_run'] - k['inv_cost'] - k['inv_ann'], 'eur', 'info'),
    ],
    'eigenkapitalquote': lambda k, v: [
        _z('Vermögen', k['assets'], 'eur'),
        _z('abzüglich Verbindlichkeiten', -k['debt'], 'eur'),
        _z('Nettovermögen', k['net'], 'eur', 'summe'),
        _z('geteilt durch Vermögen', k['assets'], 'eur'),
        _z('Eigenkapitalquote', k['eigenkapitalquote'], 'pct', 'ergebnis'),
    ],
    'inv_ltv': lambda k, v: [
        _z('Restschuld der vermieteten Objekte', k['inv_debt'], 'eur'),
        _z('geteilt durch deren Verkehrswert', k['inv_val'], 'eur'),
        _z('Beleihung der Kapitalanlagen', k['inv_ltv'], 'pct', 'ergebnis'),
        _z('zum Vergleich: Eigenheim', k['eig_ltv'], 'pct', 'info'),
        _z('zum Vergleich: alle Objekte', k['ltv'], 'pct', 'info'),
    ],
    'free_cash': lambda k, v: [
        _z('Kapitaldienst zwölf Monate', k['annuitaet12'], 'eur'),
        _z('geteilt durch zwölf ergibt die Monatsrate', k['monatsrate'], 'eur', 'summe'),
        _z('mal drei ergibt den Zielpuffer', k['puffer_ziel'], 'eur', 'summe'),
        _z('Guthaben auf den frei verfügbaren Konten', k['free_cash'], 'eur', 'ergebnis'),
        _z('Lücke zum Ziel', -k['puffer_luecke'], 'eur', 'info'),
        _z('Puffer in Monatsraten', k['puffer_monate'], 'mon', 'info'),
        _z('nicht mitgezählt: Guthaben auf den Objektkonten', k['immo_konten'], 'eur', 'info'),
    ],
    'frei_tief': lambda k, v: [
        _z('Stand heute', v['frei_start'], 'eur'),
        _z('in zwölf Monaten, Basisfall', v['frei_ende'], 'eur'),
        _z('in zwölf Monaten, konservativ', v['frei_ende_k'], 'eur'),
        _z('niedrigster Stand im Zeitraum', v['frei_tief'], 'eur', 'ergebnis'),
        _z('erreicht im Monat ' + v['frei_tief_monat'], None, 'text', 'info'),
        _z('unregelmäßige Abflüsse der letzten sechs Monate',
           v['einmalig_abfluss'], 'eur', 'info'),
    ],
    'top1': lambda k, v: [
        _z(k['top1_name'], k['top1_wert'], 'eur'),
        _z('geteilt durch das Kapitalvermögen ohne Immobilien', k['wp_total'], 'eur'),
        _z('Anteil der größten Position', k['top1'], 'pct', 'ergebnis'),
        _z('die fünf größten zusammen', k['top5'], 'pct', 'info'),
        _z('Anzahl Positionen', k['n_pos'], 'anz', 'info'),
    ],
    'immo_anteil': lambda k, v: [
        _z('Immobilien zum Verkehrswert', k['immo_val'], 'eur'),
        _z('abzüglich Darlehen', -k['immo_debt'], 'eur'),
        _z('Immobilien-Eigenkapital', k['immo_equity'], 'eur', 'summe'),
        _z('geteilt durch das Nettovermögen', k['net'], 'eur'),
        _z('Immobilienanteil', k['immo_anteil'], 'pct', 'ergebnis'),
        _z('davon vermietet', k['inv_val'], 'eur', 'info'),
        _z('davon selbstgenutzt', k['eig_val'], 'eur', 'info'),
    ],
    'immo_konten': lambda k, v: [
        _z('Sollrücklage nach Wohnfläche, alle vermieteten Objekte', k['ruecklage_soll_m2'], 'eur'),
        _z('zum Vergleich: alte Ein-Prozent-Faustregel', k['ruecklage_soll_pauschal'], 'eur', 'info'),
        _z('Guthaben auf allen Objektkonten', k['immo_konten'], 'eur', 'ergebnis'),
        _z('Deckungsgrad', k['ruecklage_quote'], 'pct', 'info'),
        _z('Modernisierung der letzten zwölf Monate', k['modern12'], 'eur', 'info'),
    ],
}

QUELLEN = {
    'dscr': 'Nur die vermieteten Objekte. Kaltmiete und umgelegte Nebenkosten sind eine '
            'Run-Rate: die zuletzt gebuchte Monatszahlung je Objekt mal zwölf, nicht die Summe '
            'der letzten zwölf Buchungen. Mieterhöhungen und neu vermietete Einheiten zählen so '
            'sofort voll. Bewirtschaftungskosten und Kapitaldienst sind die tatsächlichen '
            'Buchungen der letzten zwölf Monate. Kaltmiete sind die Mietbuchungen auf die Immobilien-Wertpapiere, der '
            'Kapitaldienst die Überweisungen auf die Darlehenskonten. Nachzulesen im Reiter '
            'Immobilien, Spalten Kaltmiete und Kapitaldienst.',
    'eigenkapitalquote': 'Stichtagswerte aus der Bilanz im Reiter Überblick.',
    'inv_ltv': 'Stichtagswerte. Der Verkehrswert ist eine eigene Schätzung, kein Gutachten — '
               'die Kennzahl ist nur so belastbar wie diese Schätzung.',
    'free_cash': 'Guthaben der Giro- und Verrechnungskonten zum Stichtag. Die Monatsrate ist '
                 'der Kapitaldienst der letzten zwölf Monate geteilt durch zwölf.',
    'frei_tief': 'Aus der Liquiditätsvorschau im selben Reiter. Sie kennt nur, was in Portfolio '
                 'Performance gebucht oder als Dauerauftrag erkennbar ist.',
    'top1': 'Positionen desselben Papiers in mehreren Depots sind zusammengefasst. Immobilien '
            'zählen nicht mit.',
    'immo_anteil': 'Stichtagswerte. Gerechnet mit dem Eigenkapital der Immobilien (Verkehrswert '
                   'minus Darlehen), nicht mit dem Verkehrswert, damit die Immobilien mit dem '
                   'übrigen, ungehebelten Vermögen vergleichbar bleiben. Der hohe Anteil ist '
                   'gewollt; die Zahl steht hier, damit die Entscheidung sichtbar bleibt.',
    'immo_konten': 'Wohnflächen und Baujahr aus der eigenen Konfiguration (Objektstammdaten). '
                   'Weiterhin eine Faustregel, aber näher an der üblichen Praxis als der '
                   'pauschale ein Prozent des Verkehrswerts.',
}
