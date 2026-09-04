# -*- coding: utf-8 -*-
"""Steuerliche Sicht auf die Immobilien.

Die Rechenlogik ist unveraendert gegenueber der urspruenglichen, persoenlichen Fassung —
nur die Werte (Grenzsteuersatz, AfA je Objekt, Ergebnis, Mehrjahresreihe) kommen jetzt aus
config.py statt aus Konstanten in dieser Datei. Ist in der Konfiguration kein 'steuer'-
Abschnitt hinterlegt, rechnet das Modul mit Nullen — Essanz funktioniert auch ganz ohne
steuerliche Angaben, nur die Steuerspalten bleiben dann leer.
"""
import config


def build(objs, kpi):
    s = config.steuer()
    satz = s['grenzsteuersatz'] / 100
    afa_tab = s['afa']
    ergebnis_tab = s['ergebnis']

    zeilen = []
    for o in objs:
        no = str(o['no'])
        eintrag = afa_tab.get(no, {})
        afa_satz = eintrag.get('satz', 0.0)
        afa = eintrag.get('betrag', 0.0)
        eigentum = eintrag.get('eigentum', '')
        selbst = o['selbstgenutzt']
        einnahmen = 0.0 if selbst else o['rent12'] + o['nk12']
        # Bei Eigennutzung sind weder AfA noch Schuldzinsen abziehbar.
        wk_afa = 0.0 if selbst else afa
        wk_zins = 0.0 if selbst else o['interest12']
        wk_bewirt = 0.0 if selbst else o['cost12']
        wk_erhalt = 0.0 if selbst else o['capex12']
        wk = wk_afa + wk_zins + wk_bewirt + wk_erhalt
        ergebnis = einnahmen - wk
        steuer_last = ergebnis * satz
        zeilen.append(dict(
            no=o['no'], name=o['name'], selbstgenutzt=selbst, eigentum=eigentum,
            afa_satz=afa_satz, afa=wk_afa, afa_nominal=afa,
            bemessung=afa / (afa_satz / 100) if afa_satz else 0.0,
            einnahmen=einnahmen, bewirtschaftung=wk_bewirt, zinsen=wk_zins,
            erhaltung=wk_erhalt, werbungskosten=wk,
            ergebnis=ergebnis, steuer=steuer_last,
            cashflow=o['cashflow12'],
            cashflow_nach_steuern=o['cashflow12'] - steuer_last,
            ergebnis_erklaerung=ergebnis_tab.get(no),
        ))

    inv = [z for z in zeilen if not z['selbstgenutzt']]
    eig = [z for z in zeilen if z['selbstgenutzt']]
    sm = lambda L, k: sum(x[k] for x in L)

    eig_verlust = 0.0
    eig_verlust_12m = 0.0
    for o in objs:
        if o['selbstgenutzt']:
            eintrag = afa_tab.get(str(o['no']), {})
            afa = eintrag.get('betrag', 0.0)
            eig_verlust += (o.get('interest_runrate', o['interest12']) + afa) * satz
            eig_verlust_12m += (o['interest12'] + afa) * satz

    vuv_gesamt = s['vuv_person1'] + s['vuv_person2']

    return dict(
        satz=s['grenzsteuersatz'], durchschnitt=s['durchschnittsatz'], quelle=s['quelle'],
        zve=s['zve'], soli=s['soli'], kirchensteuer=s['kirchensteuer'],
        zeilen=zeilen,
        einnahmen=sm(inv, 'einnahmen'), afa=sm(inv, 'afa'), zinsen=sm(inv, 'zinsen'),
        bewirtschaftung=sm(inv, 'bewirtschaftung'), erhaltung=sm(inv, 'erhaltung'),
        werbungskosten=sm(inv, 'werbungskosten'), ergebnis=sm(inv, 'ergebnis'),
        steuer=sm(inv, 'steuer'), cashflow=sm(inv, 'cashflow'),
        cashflow_nach_steuern=sm(inv, 'cashflow_nach_steuern'),
        afa_wirkung=sm(inv, 'afa') * satz,
        eigenheim_steuernachteil=eig_verlust,
        eigenheim_steuernachteil_12m=eig_verlust_12m,
        eigenheim_zins_runrate=sum(o.get('interest_runrate', 0.0) for o in objs if o['selbstgenutzt']),
        eigenheim_zinsen=sm(eig, 'zinsen') or sum(o['interest12'] for o in objs if o['selbstgenutzt']),
        rendite_nach_steuern=((sm(inv, 'einnahmen') - sm(inv, 'bewirtschaftung') - sm(inv, 'zinsen')
                               - sm(inv, 'steuer')) / kpi['inv_equity'] * 100
                              if kpi['inv_equity'] else 0.0),
        jahr=s['jahr'],
        ergebnis_erklaerung_summe=sum(v for v in ergebnis_tab.values()),
        vuv_erklaerung_person1=s['vuv_person1'], vuv_erklaerung_person2=s['vuv_person2'],
        vuv_erklaerung_gesamt=vuv_gesamt,
        anlage_v_zeile85=s['anlage_v_zeile85'],
        historie=[dict(h, vuv=h.get('vuv_person1', 0) + h.get('vuv_person2', 0),
                       gesamtsteuer=h.get('est', 0) + h.get('kist', 0) + h.get('soli', 0))
                  for h in s['historie']],
    )
