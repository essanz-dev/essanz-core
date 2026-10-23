"""Rechnet aus einer Portfolio-Performance-Datei die Kennzahlen fuer das Vermoegens-Dashboard.

Die Rechenlogik ist identisch zur urspruenglichen, persoenlichen Fassung. Veraendert hat
sich nur, woher die Konstanten kommen, die frueher oben in dieser Datei hartcodiert waren
(Wechselkurse, welche Objekte selbstgenutzt sind, Vergleichsindizes, Kontonamen-Anonymisierung)
— die stehen jetzt in config.py / config.yaml.
"""
import bisect, datetime, json, re
from collections import defaultdict
import ppparse
import forecast as _forecast
import stress as _stress
import schwellen as _schwellen
import steuer as _steuer
import objektdaten as _stamm
import config as _config

_CFG = _config.allgemein()

# Zinssatz-Aufschlag fuer das Anschlussrisiko-Stressszenario in der Faelligkeitsleiste.
ANSCHLUSS_STRESS_PP = _CFG['anschluss_stress_pp']

# Instandhaltungsruecklage nach Quadratmetern statt der pauschalen Ein-Prozent-Regel.
RUECKLAGE_EUR_M2_MONAT_ALTBAU = _CFG['ruecklage_eur_m2_monat_altbau']
RUECKLAGE_EUR_M2_MONAT_NEUBAU = _CFG['ruecklage_eur_m2_monat_neubau']

EPOCH = datetime.date(1970, 1, 1)
FX = _CFG['fx']
FX_DATE = _CFG['fx_date']

# Selbstgenutzte Objekte (Objektnummer aus dem Kontonamen "Immobilie N: ...").
SELBSTGENUTZT = _CFG['selbstgenutzt']

# Welche Konten als P2P, Krypto, Darlehen usw. gelten, steht in config.konten().


def eday(d):
    return (d - EPOCH).days

def month_end(y, m):
    return datetime.date(y + (m == 12), 1 if m == 12 else m + 1, 1) - datetime.timedelta(days=1)


class Book:
    def __init__(self, path, asof=None):
        self.d = ppparse.load(path)
        self.acc = self.d['accounts']
        self.pf = self.d['portfolios']
        self.sec = self.d['securities']
        self.tx = self.d['transactions']
        self.pidx = {k: ([p[0] for p in v], [p[1] for p in v]) for k, v in self.d['prices'].items()}
        real = [t['date'] for t in self.tx]
        if not real:
            raise ppparse.FormatFehler(
                'Die Datei enthält keine Buchungen. Essanz braucht mindestens die Einzahlungen '
                'und Käufe, aus denen sich die Kontostände ergeben.')
        today = datetime.date.today()
        self.asof = asof or today.isoformat()
        self.start = real[0]
        self.classify()

    # ---------- Klassifikation der Konten und Depots ----------
    def classify(self):
        """Ordnet Konten, Depots und Objekte nach den Regeln aus config.konten() zu.

        Reihenfolge: exakter Name (konten_gruppe/depot_gruppe) > explizite Objekte >
        Namensanfang (Praefixe) > Liquiditaet bzw. Wertpapiere. Der Grund jeder Zuordnung
        steht in acc_reason/pf_reason (fuer run_update.py --diagnose).
        """
        k = _config.konten()
        self.kontenregeln = k
        by_name = defaultdict(list)
        for u, a in self.acc.items():
            by_name[a['name']].append(u)
        sec_by_name = defaultdict(list)
        for u, s in self.sec.items():
            sec_by_name[s['name']].append(u)

        # Objekte: zuerst explizit aus der Config, dann nach Namensmuster
        self.objects = {}
        self.obj_reason = {}
        obj_acc, obj_loan = {}, {}
        for no, o in k['objekte'].items():
            konto = o.get('konto')
            # Platzhalter statt None, damit ein fehlendes Konto keine Buchungen ohne Konto erfasst
            u = by_name.get(konto, ['<fehlt: Objekt %s>' % no])[0] if konto else '<fehlt: Objekt %s>' % no
            self.objects[no] = dict(no=no, name=o.get('name') or konto or 'Objekt %s' % no,
                                    account=u, loans=[], sec=None)
            self.obj_reason[no] = 'config: konten.objekte'
            if u in self.acc:
                obj_acc[u] = no
            dl = o.get('darlehen') or []
            for name in ([dl] if isinstance(dl, str) else dl):
                for lu in by_name.get(name, []):
                    self.objects[no]['loans'].append(lu); obj_loan[lu] = no
            ws = o.get('wertpapier')
            if ws and sec_by_name.get(ws):
                self.objects[no]['sec'] = sec_by_name[ws][0]
        muster = re.compile(k['objekt_muster']) if k['objekt_muster'] else None
        dmuster = re.compile(k['darlehen_muster']) if k['darlehen_muster'] else None
        if muster:
            for u, a in self.acc.items():
                m = muster.match(a['name'])
                if m and m.group(1) not in self.objects and u not in obj_acc:
                    self.objects[m.group(1)] = dict(no=m.group(1), name=m.group(2), account=u,
                                                    loans=[], sec=None)
                    self.obj_reason[m.group(1)] = 'Namensmuster „%s“' % k['objekt_muster']
                    obj_acc[u] = m.group(1)
        if dmuster:
            for u, a in self.acc.items():
                m = dmuster.match(a['name'])
                if (m and u not in obj_loan and m.group(1) in self.objects
                        and self.obj_reason[m.group(1)] != 'config: konten.objekte'):
                    self.objects[m.group(1)]['loans'].append(u); obj_loan[u] = m.group(1)
        if muster:
            for u, s in self.sec.items():
                m = muster.match(s['name'])
                if (m and m.group(1) in self.objects and self.objects[m.group(1)]['sec'] is None):
                    self.objects[m.group(1)]['sec'] = u

        self.acc_group, self.acc_reason = {}, {}
        for u, a in self.acc.items():
            n = a['name']
            if n in k['konten_gruppe']:
                g, r = k['konten_gruppe'][n], 'config: exakter Name'
            elif u in obj_loan:
                g, r = 'Darlehen', 'Darlehen zu Objekt %s' % obj_loan[u]
            elif u in obj_acc:
                g, r = 'Immobilien-Konten', 'Objektkonto zu Objekt %s' % obj_acc[u]
            elif any(n.startswith(p) for p in k['darlehen_praefix']):
                g, r = 'Darlehen', 'Name beginnt mit „%s“' % next(p for p in k['darlehen_praefix'] if n.startswith(p))
            elif any(n.startswith(p) for p in k['immobilien_konto_praefix']):
                g, r = 'Immobilien-Konten', 'Name beginnt mit „%s“' % next(
                    p for p in k['immobilien_konto_praefix'] if n.startswith(p))
            else:
                g, r = 'Liquidität', 'keine Regel passt (Standard)'
            self.acc_group[u], self.acc_reason[u] = g, r
        self.pf_group, self.pf_reason = {}, {}
        for u, p in self.pf.items():
            n = p['name']
            if n in k['depot_gruppe']:
                g, r = k['depot_gruppe'][n], 'config: exakter Name'
            elif any(n.startswith(x) for x in k['immobilien_depot_praefix']):
                g, r = 'Immobilien', 'Name beginnt mit „%s“' % next(
                    x for x in k['immobilien_depot_praefix'] if n.startswith(x))
            else:
                g, r = 'Wertpapiere', 'keine Regel passt (Standard)'
            self.pf_group[u], self.pf_reason[u] = g, r
        immo_pf = [u for u, g in self.pf_group.items() if g == 'Immobilien']
        self.immo_pf = set(immo_pf)

    # ---------- Kurse ----------
    def price(self, sid, day):
        ds, vs = self.pidx.get(sid, ([], []))
        if not ds:
            return 0.0
        i = bisect.bisect_right(ds, day) - 1
        return vs[i] if i >= 0 else 0.0

    def price_eur(self, sid, day):
        cur = self.sec[sid]['currency']
        return self.price(sid, day) * FX.get(cur, 1.0)

    # ---------- Bestand ----------
    def state(self, asof):
        cash = defaultdict(float)
        shares = defaultdict(lambda: defaultdict(float))
        for t in self.tx:
            if t['date'] > asof:
                break
            ty = t['type']; a = t['account']; p = t['portfolio']
            amt = t['amount']; sh = t['shares']; s = t['security']
            if ty == 'PURCHASE':
                cash[a] -= amt; shares[p][s] += sh
            elif ty == 'SALE':
                cash[a] += amt; shares[p][s] -= sh
            elif ty == 'INBOUND_DELIVERY':
                shares[p][s] += sh
            elif ty == 'OUTBOUND_DELIVERY':
                shares[p][s] -= sh
            elif ty == 'SECURITY_TRANSFER':
                shares[p][s] -= sh; shares[t['otherPortfolio']][s] += sh
            elif ty == 'CASH_TRANSFER':
                cash[a] -= amt; cash[t['otherAccount']] += amt
            elif ty in ('DEPOSIT', 'DIVIDEND', 'INTEREST', 'TAX_REFUND', 'FEE_REFUND'):
                cash[a] += amt
            elif ty in ('REMOVAL', 'INTEREST_CHARGE', 'TAX', 'FEE'):
                cash[a] -= amt
        return cash, shares

    def snapshot(self, asof):
        cash, shares = self.state(asof)
        day = eday(datetime.date.fromisoformat(asof))
        pos = []
        for p, ss in shares.items():
            for sid, q in ss.items():
                if abs(q) < 1e-9:
                    continue
                pr = self.price_eur(sid, day)
                pos.append(dict(portfolio=p, security=sid, shares=q, price=pr, value=q * pr,
                                group=self.pf_group[p]))
        g = defaultdict(float)
        for u, v in cash.items():
            g[self.acc_group[u]] += v
        for p in pos:
            g['Immobilien' if p['group'] == 'Immobilien' else 'Wertpapiere'] += p['value']
        assets = sum(v for k, v in g.items() if k != 'Darlehen')
        return dict(asof=asof, cash=dict(cash), positions=pos, groups=dict(g),
                    assets=assets, debt=-g['Darlehen'], net=assets + g['Darlehen'])

    # ---------- Monatsreihe ----------
    def monthly(self):
        y0, m0 = int(self.start[:4]), int(self.start[5:7])
        y1, m1 = int(self.asof[:4]), int(self.asof[5:7])
        out = []
        y, m = y0, m0
        while (y, m) <= (y1, m1):
            me = month_end(y, m)
            asof = min(me.isoformat(), self.asof)
            snap = self.snapshot(asof)
            row = dict(month='%04d-%02d' % (y, m), asof=asof, net=snap['net'],
                       assets=snap['assets'], debt=snap['debt'])
            obj = {}
            for no, o in self.objects.items():
                wert = next((x['value'] for x in snap['positions'] if x['security'] == o['sec']), 0.0)
                dar = -sum(snap['cash'].get(l, 0.0) for l in o['loans'])
                obj[no] = dict(wert=round(wert, 2), darlehen=round(dar, 2),
                               konto=round(snap['cash'].get(o['account'], 0.0), 2))
            row['objekte'] = obj
            for k in ('Immobilien', 'Wertpapiere', 'Liquidität', 'P2P', 'Krypto-Konten',
                      'Immobilien-Konten', 'Darlehen'):
                row[k] = snap['groups'].get(k, 0.0)
            out.append(row)
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        return out

    # ---------- Zahlungsstroeme pro Monat ----------
    CAPEX_WORDS = _CFG['capex_words']
    GIFT_WORDS = _CFG['gift_words']
    FIN_WORDS = _CFG['fin_words']
    CAPITAL_WORDS = GIFT_WORDS + FIN_WORDS

    def _immo_sec(self):
        out = set()
        for t in self.tx:
            if t['portfolio'] in self.immo_pf and t['security']:
                out.add(t['security'])
        return out

    def flows(self):
        immo_sec = self._immo_sec()
        f = defaultdict(lambda: defaultdict(float))
        for t in self.tx:
            if t['date'] > self.asof:
                continue
            k = t['date'][:7]; ty = t['type']; a = t['account']
            grp = self.acc_group.get(a) if a else None
            immo_acc = grp == 'Immobilien-Konten'
            note = (t['note'] or '').lower()
            amt = t['amount']
            if ty == 'DEPOSIT':
                if any(w in note for w in self.GIFT_WORDS):
                    f[k]['Schenkung'] += amt
                elif immo_acc and any(w in note for w in self.FIN_WORDS):
                    f[k]['Fremdmittel'] += amt
                elif immo_acc and amt >= 20000:
                    f[k]['Eigeneinlage'] += amt
                elif immo_acc:
                    f[k]['Nebenkosten_Mieter'] += amt
                else:
                    f[k]['Einzahlungen'] += amt
            elif ty == 'REMOVAL':
                if immo_acc:
                    if any(w in note for w in self.CAPEX_WORDS) or amt >= 3000:
                        f[k]['Modernisierung'] += amt
                    else:
                        f[k]['Bewirtschaftung'] += amt
                else:
                    f[k]['Entnahmen'] += amt
            elif ty == 'DIVIDEND':
                if t['security'] in immo_sec:
                    f[k]['Kaltmiete'] += amt
                else:
                    f[k]['Dividenden'] += amt
            elif ty == 'INTEREST':
                f[k]['Zinsertraege'] += amt
                if grp == 'P2P':
                    f[k]['Zinsertraege_P2P'] += amt
            elif ty == 'INTEREST_CHARGE':
                f[k]['Zinsaufwand'] += amt
                if grp == 'Darlehen':
                    f[k]['Zinsaufwand_Darlehen'] += amt
            elif ty == 'TAX':
                f[k]['Grundsteuer' if immo_acc else 'Kapitalsteuern'] += amt
            elif ty == 'TAX_REFUND':
                f[k]['Grundsteuer' if immo_acc else 'Kapitalsteuern'] -= amt
            elif ty == 'FEE':
                f[k]['Bewirtschaftung' if immo_acc else 'Gebuehren'] += amt
            elif ty == 'FEE_REFUND':
                f[k]['Bewirtschaftung' if immo_acc else 'Gebuehren'] -= amt
            elif ty == 'PURCHASE':
                if t['portfolio'] in self.immo_pf:
                    f[k]['Immokaeufe'] += amt
                    for u in t['units']:
                        if u['type'] == 'FEE':
                            f[k]['Kaufnebenkosten'] += u['amount']
                        elif u['type'] == 'TAX':
                            f[k]['Grunderwerbsteuer'] += u['amount']
                else:
                    f[k]['Wertpapierkaeufe'] += amt
                    for u in t['units']:
                        if u['type'] == 'FEE':
                            f[k]['Ordergebuehren'] += u['amount']
                        elif u['type'] == 'TAX':
                            f[k]['Kapitalsteuern'] += u['amount']
            elif ty == 'SALE':
                tag = 'Immoverkaeufe' if t['portfolio'] in self.immo_pf else 'Wertpapierverkaeufe'
                f[k][tag] += amt
            elif ty in ('INBOUND_DELIVERY', 'OUTBOUND_DELIVERY'):
                sign = 1 if ty == 'INBOUND_DELIVERY' else -1
                tag = 'Immoeinlieferung' if t['portfolio'] in self.immo_pf else 'Einlieferung'
                f[k][tag] += sign * amt
            elif ty == 'CASH_TRANSFER':
                if self.acc_group.get(t['otherAccount']) == 'Darlehen':
                    f[k]['Annuitaet'] += amt
                elif grp == 'Darlehen':
                    f[k]['Darlehensauszahlung'] += amt
            if ty == 'DIVIDEND':
                for u in t['units']:
                    if u['type'] == 'TAX':
                        f[k]['Kapitalsteuern'] += u['amount']
        return {k: dict(v) for k, v in f.items()}

    # ---------- FIFO-Einstand je Position ----------
    def cost_basis(self):
        lots = defaultdict(list)
        realized = defaultdict(float)
        for t in self.tx:
            if t['date'] > self.asof:
                continue
            ty = t['type']; key = (t['portfolio'], t['security'])
            if ty in ('PURCHASE', 'INBOUND_DELIVERY'):
                if t['shares'] > 0:
                    lots[key].append([t['shares'], t['amount'] / t['shares']])
            elif ty in ('SALE', 'OUTBOUND_DELIVERY'):
                rest = t['shares']; proceeds = t['amount']
                cost = 0.0
                while rest > 1e-9 and lots[key]:
                    lot = lots[key][0]
                    take = min(rest, lot[0])
                    cost += take * lot[1]; lot[0] -= take; rest -= take
                    if lot[0] <= 1e-9:
                        lots[key].pop(0)
                if ty == 'SALE':
                    realized[t['security']] += proceeds - cost
            elif ty == 'SECURITY_TRANSFER':
                rest = t['shares']; dst = (t['otherPortfolio'], t['security'])
                while rest > 1e-9 and lots[key]:
                    lot = lots[key][0]
                    take = min(rest, lot[0])
                    lots[dst].append([take, lot[1]]); lot[0] -= take; rest -= take
                    if lot[0] <= 1e-9:
                        lots[key].pop(0)
        cb = {}
        for key, ls in lots.items():
            q = sum(l[0] for l in ls); c = sum(l[0] * l[1] for l in ls)
            if q > 1e-9:
                cb[key] = dict(shares=q, cost=c, unit=c / q)
        return cb, dict(realized)


VERGLEICH_KPIS = {
    'net': ('Nettovermögen', 'eur'),
    'assets': ('Vermögen', 'eur'),
    'debt': ('Verbindlichkeiten', 'eur'),
    'eigenkapitalquote': ('Eigenkapitalquote', 'pct'),
    'free_cash': ('Frei verfügbare Liquidität', 'eur'),
    'immo_konten': ('Guthaben Objektkonten', 'eur'),
    'wp_total': ('Wertpapierdepots', 'eur'),
    'immo_val': ('Immobilien Verkehrswert', 'eur'),
    'inv_ltv': ('Beleihung Kapitalanlagen', 'pct'),
    'dscr': ('Kapitaldienstdeckung', 'x'),
    'rent12': ('Kaltmiete 12 Monate', 'eur'),
    'inv_cf': ('Cashflow Kapitalanlagen', 'eur'),
    'twr_pa': ('Wertpapierrendite p. a.', 'pct'),
    'puffer_monate': ('Liquiditätspuffer in Monatsraten', 'mon'),
    'immo_anteil': ('Immobilienanteil am Vermögen', 'pct'),
    'top1': ('Größte Depotposition', 'pct'),
    'frei_tief': ('Tiefstand der Vorschau', 'eur'),
    'ruecklage_quote': ('Rücklage auf den Objektkonten', 'pct'),
}


def _vormonat(asof):
    d = datetime.date.fromisoformat(asof)
    return (d.replace(day=1) - datetime.timedelta(days=1)).isoformat()


def build(path, asof=None, mit_vergleich=True, book=None):
    b = book or Book(path, asof)
    snap = b.snapshot(b.asof)
    months = b.monthly()
    fl = b.flows()
    cb, realized = b.cost_basis()

    positions = []
    for p in snap['positions']:
        s = b.sec[p['security']]
        c = cb.get((p['portfolio'], p['security']), dict(cost=0.0, unit=0.0))
        div = sum(t['amount'] for t in b.tx
                  if t['security'] == p['security'] and t['type'] == 'DIVIDEND' and t['date'] <= b.asof)
        positions.append(dict(
            depot=b.pf[p['portfolio']]['name'], name=s['name'], isin=s['isin'], ticker=s['ticker'],
            currency=s['currency'], shares=p['shares'], price=p['price'], value=p['value'],
            cost=c['cost'], unit_cost=c['unit'],
            gain=p['value'] - c['cost'], gain_pct=(p['value'] / c['cost'] - 1) * 100 if c['cost'] > 0 else None,
            dividends=div, group=p['group'], sec=p['security']))
    positions.sort(key=lambda x: -x['value'])

    _agg = {}
    for p in positions:
        if p['group'] == 'Immobilien':
            continue
        key = p['isin'] or p['name']
        if key in _agg:
            a = _agg[key]
            a['value'] += p['value']; a['cost'] += p['cost']; a['shares'] += p['shares']
            a['dividends'] += p['dividends']
            a['depots'].append(p['depot'])
        else:
            _agg[key] = dict(p, depots=[p['depot']])
    konsolidiert = sorted(_agg.values(), key=lambda x: -x['value'])
    for a in konsolidiert:
        a['depot'] = ' + '.join(sorted(set(a['depots'])))
        a['gain'] = a['value'] - a['cost']
        a['gain_pct'] = (a['value'] / a['cost'] - 1) * 100 if a['cost'] > 0 else None
        a.pop('depots', None)

    _asof_d = datetime.date.fromisoformat(b.asof)
    bewertungshinweise = []
    for p in positions:
        if p['group'] == 'Immobilien':
            continue
        reihe = b.d['prices'].get(p['sec']) or []
        if not reihe:
            bewertungshinweise.append(dict(name=p['name'], depot=p['depot'], wert=p['value'],
                                           letzter_kurs=None, alter_tage=None))
            continue
        letzt = datetime.date(1970, 1, 1) + datetime.timedelta(days=max(x[0] for x in reihe))
        alter = (_asof_d - letzt).days
        if alter > 30:
            bewertungshinweise.append(dict(name=p['name'], depot=p['depot'], wert=p['value'],
                                           letzter_kurs=letzt.isoformat(), alter_tage=alter))
    bewertungshinweise.sort(key=lambda x: -x['wert'])

    objs = []
    for no, o in sorted(b.objects.items(), key=lambda x: int(x[0])):
        val = next((p['value'] for p in positions if p['sec'] == o['sec']), 0.0)
        loan = -sum(snap['cash'].get(l, 0.0) for l in o['loans'])
        opacc = snap['cash'].get(o['account'], 0.0)
        win = set(m['month'] for m in months[-12:])
        inwin = lambda t: t['date'][:7] in win and t['date'] <= b.asof
        rent = sum(t['amount'] for t in b.tx if t['type'] == 'DIVIDEND' and t['security'] == o['sec']
                   and t['date'] <= b.asof)
        cost = sum(t['amount'] for t in b.tx if t['type'] in ('REMOVAL', 'FEE', 'TAX') and t['account'] == o['account']
                   and t['date'] <= b.asof)
        interest = sum(t['amount'] for t in b.tx if t['type'] == 'INTEREST_CHARGE' and t['account'] in o['loans']
                       and t['date'] <= b.asof)
        nk = sum(t['amount'] for t in b.tx if t['type'] == 'DEPOSIT' and t['account'] == o['account']
                 and t['date'] <= b.asof
                 and not (any(w in (t['note'] or '').lower() for w in Book.CAPITAL_WORDS) or t['amount'] >= 20000))
        r12 = sum(t['amount'] for t in b.tx if t['type'] == 'DIVIDEND' and t['security'] == o['sec'] and inwin(t))
        nk12 = sum(t['amount'] for t in b.tx if t['type'] == 'DEPOSIT' and t['account'] == o['account'] and inwin(t)
                   and not (any(w in (t['note'] or '').lower() for w in Book.CAPITAL_WORDS) or t['amount'] >= 20000))
        c12 = sum(t['amount'] for t in b.tx if t['type'] in ('REMOVAL', 'FEE', 'TAX') and t['account'] == o['account'] and inwin(t)
                  and not (t['type'] == 'REMOVAL' and (any(w in (t['note'] or '').lower() for w in Book.CAPEX_WORDS) or t['amount'] >= 3000)))
        cap12 = sum(t['amount'] for t in b.tx if t['type'] == 'REMOVAL' and t['account'] == o['account'] and inwin(t)
                    and (any(w in (t['note'] or '').lower() for w in Book.CAPEX_WORDS) or t['amount'] >= 3000))
        i12 = sum(t['amount'] for t in b.tx if t['type'] == 'INTEREST_CHARGE' and t['account'] in o['loans'] and inwin(t))
        i_run = 0.0
        for l in o['loans']:
            last = max((t for t in b.tx if t['type'] == 'INTEREST_CHARGE' and t['account'] == l
                        and t['date'] <= b.asof), key=lambda t: t['date'], default=None)
            if last is not None:
                i_run += last['amount'] * 12
        t12 = sum(t['amount'] for t in b.tx if t['type'] == 'CASH_TRANSFER'
                  and t['otherAccount'] in o['loans'] and inwin(t))
        cap_total = sum(t['amount'] for t in b.tx if t['type'] == 'REMOVAL' and t['account'] == o['account']
                        and t['date'] <= b.asof
                        and (any(w in (t['note'] or '').lower() for w in Book.CAPEX_WORDS) or t['amount'] >= 3000))
        ann_total = sum(t['amount'] for t in b.tx if t['type'] == 'CASH_TRANSFER'
                        and t['otherAccount'] in o['loans'] and t['date'] <= b.asof)
        ausz = sum(t['amount'] for t in b.tx if t['type'] == 'CASH_TRANSFER'
                   and t['account'] in o['loans'] and t['date'] <= b.asof)
        kauf = [t for t in b.tx if t['security'] == o['sec'] and t['type'] == 'PURCHASE'
                and t['date'] <= b.asof]
        kaufpreis = sum(t['amount'] for t in kauf)
        kaufdatum = min((t['date'] for t in kauf), default=None)
        selbst = no in SELBSTGENUTZT
        tilg12 = t12 - i12
        noi12 = r12 + nk12 - c12
        objs.append(dict(no=int(no), name=o['name'], selbstgenutzt=selbst,
                         nutzung='Eigennutzung' if selbst else 'Kapitalanlage',
                         capex_total=cap_total, value=val, loan=loan, equity=val - loan,
                         ltv=loan / val * 100 if val else None, opaccount=opacc,
                         rent12=r12, nk12=nk12, cost12=c12, capex12=cap12,
                         interest12=i12, interest_runrate=i_run,
                         annuitaet12=t12, redemption12=tilg12,
                         noi12=noi12,
                         cashflow12=noi12 - t12,
                         ueberschuss12=noi12 - i12,
                         net_yield=None if selbst else (noi12 / val * 100 if val else None),
                         gross_yield=None if selbst else (r12 / val * 100 if val else None),
                         zinssatz=i12 / loan * 100 if loan else None,
                         tilgungssatz=tilg12 / loan * 100 if loan else None,
                         kaufpreis=kaufpreis, kaufdatum=kaufdatum, darlehensauszahlung=ausz,
                         ek_einsatz=kaufpreis - ausz,
                         tilgung_total=ann_total - interest,
                         wertaenderung=val - kaufpreis,
                         rent_total=rent, nk_total=nk, cost_total=cost, interest_total=interest))

    for o in objs:
        no = str(o['no'])
        stamm = _stamm.stamm_fuer(no) or {}
        wfl = stamm.get('wohnflaeche_m2')
        o['baujahr'] = stamm.get('baujahr')
        o['wohnflaeche_m2'] = wfl
        o['grundstueck_m2'] = stamm.get('grundstueck_m2')
        o['miteigentumsanteil'] = stamm.get('miteigentumsanteil')
        o['mieter_seit'] = stamm.get('mieter_seit')
        o['mieter_seit_hinweis'] = stamm.get('mieter_seit_hinweis')
        o['mieter_name'] = stamm.get('mieter_name')
        o['lage'] = stamm.get('lage')
        o['bodenrichtwert'] = stamm.get('bodenrichtwert')
        o['bodenrichtwert_datum'] = stamm.get('bodenrichtwertdatum')
        o['bodenrichtwert_hinweis'] = stamm.get('bodenrichtwert_hinweis')
        o['stamm_quelle'] = stamm.get('quelle')
        o['miete_pro_m2_kalt'] = (o['rent12'] / 12 / wfl) if (wfl and not o['selbstgenutzt']) else None

        if wfl:
            faktor = (RUECKLAGE_EUR_M2_MONAT_ALTBAU if (o['baujahr'] or 0) < 1948
                      else RUECKLAGE_EUR_M2_MONAT_NEUBAU)
            o['ruecklage_soll_m2_faktor'] = faktor
            o['ruecklage_soll_m2'] = wfl * faktor * 12
        else:
            o['ruecklage_soll_m2_faktor'] = None
            o['ruecklage_soll_m2'] = None

        vw = _stamm.verkehrswert_fuer(no)
        if vw:
            o['verkehrswert_methode'] = vw.get('methode')
            o['verkehrswert_stichtag'] = vw.get('stichtag')
            o['verkehrswert_gutachter'] = vw.get('gutachter')
            o['verkehrswert_hinweis'] = vw.get('hinweis')
            o['verkehrswert_quelle'] = vw.get('quelle')
            o['verkehrswert_gesamtobjekt'] = vw.get('marktwert_gesamtobjekt')
        else:
            o['verkehrswert_methode'] = None
            o['verkehrswert_hergeleitet'] = None

    from collections import defaultdict as _dd
    gruppen = _dd(list)
    for o in objs:
        if o.get('verkehrswert_gesamtobjekt'):
            gruppen[(o['verkehrswert_quelle'], o['verkehrswert_gesamtobjekt'])].append(o)
    for (_, gesamt), gr in gruppen.items():
        flsum = sum(g['wohnflaeche_m2'] or 0 for g in gr)
        for g in gr:
            if flsum and g['wohnflaeche_m2']:
                g['verkehrswert_hergeleitet'] = round(gesamt * g['wohnflaeche_m2'] / flsum, -2)
                g['verkehrswert_hergeleitet_anteil'] = g['wohnflaeche_m2'] / flsum * 100
            else:
                g['verkehrswert_hergeleitet'] = None
        if len(gr) > 1:
            for g in gr:
                g['verkehrswert_differenz_kurs'] = ((g['value'] - g['verkehrswert_hergeleitet'])
                                                     if g.get('verkehrswert_hergeleitet') else None)
    for (_, gesamt), gr in gruppen.items():
        kurs_summe = sum(g['value'] for g in gr)
        for g in gr:
            g['verkehrswert_gesamtobjekt_kurs'] = kurs_summe
            g['verkehrswert_gesamtobjekt_differenz'] = gesamt - kurs_summe

    for i, m in enumerate(months):
        f = fl.get(m['month'], {})
        g = f.get
        m['ein'] = g('Einzahlungen', 0.0)
        m['ent'] = g('Entnahmen', 0.0)
        m['schenkung'] = g('Schenkung', 0.0)
        m['fremdmittel'] = g('Fremdmittel', 0.0)
        m['eigeneinlage'] = g('Eigeneinlage', 0.0)
        m['sondereinlagen'] = m['schenkung'] + m['fremdmittel'] + m['eigeneinlage']
        m['kaltmiete'] = g('Kaltmiete', 0.0)
        m['nk_mieter'] = g('Nebenkosten_Mieter', 0.0)
        m['bewirtschaftung'] = g('Bewirtschaftung', 0.0)
        m['modernisierung'] = g('Modernisierung', 0.0)
        m['grundsteuer'] = g('Grundsteuer', 0.0)
        m['zinsaufwand'] = g('Zinsaufwand', 0.0)
        m['zinsertrag'] = g('Zinsertraege', 0.0)
        m['zinsertrag_p2p'] = g('Zinsertraege_P2P', 0.0)
        m['dividenden'] = g('Dividenden', 0.0)
        m['kapitalsteuern'] = g('Kapitalsteuern', 0.0)
        m['gebuehren'] = g('Gebuehren', 0.0) + g('Ordergebuehren', 0.0)
        m['kaufnebenkosten'] = g('Kaufnebenkosten', 0.0) + g('Grunderwerbsteuer', 0.0)
        m['annuitaet'] = g('Annuitaet', 0.0)
        m['zins_darlehen'] = g('Zinsaufwand_Darlehen', 0.0)
        m['tilgung'] = m['annuitaet'] - m['zins_darlehen']
        m['kaeufe'] = g('Wertpapierkaeufe', 0.0)
        m['verkaeufe'] = g('Wertpapierverkaeufe', 0.0)
        m['immokaeufe'] = g('Immokaeufe', 0.0)
        m['darlehensauszahlung'] = g('Darlehensauszahlung', 0.0)
        prev = months[i - 1]['net'] if i else 0.0
        m['delta'] = m['net'] - prev
        m['extern'] = m['ein'] - m['ent'] + m['sondereinlagen']
        m['immo_cf'] = (m['kaltmiete'] + m['nk_mieter'] - m['bewirtschaftung']
                        - m['grundsteuer'] - m['zinsaufwand'])
        m['ergebnis'] = m['delta'] - m['extern']
        pm = months[i - 1] if i else None
        m['wp_change'] = (m['Wertpapiere'] - (pm['Wertpapiere'] if pm else 0.0)
                          - m['kaeufe'] + m['verkaeufe'] - f.get('Einlieferung', 0.0))
        m['immo_change'] = (m['Immobilien'] - (pm['Immobilien'] if pm else 0.0)
                            - m['immokaeufe'] + f.get('Immoverkaeufe', 0.0)
                            - f.get('Immoeinlieferung', 0.0))
        m['laufend'] = m['ergebnis'] - m['wp_change'] - m['immo_change']
        m['liquid'] = m['Wertpapiere'] + m['P2P'] + m['Liquidität'] + m['Krypto-Konten']

    wp = []
    prevv = None
    chain = 1.0
    for m in months:
        v = m['Wertpapiere']
        f = fl.get(m['month'], {})
        net_in = (f.get('Wertpapierkaeufe', 0.0) - f.get('Wertpapierverkaeufe', 0.0)
                  + f.get('Einlieferung', 0.0))
        r = ((v - prevv - net_in) / (prevv + 0.5 * net_in)) if (prevv and prevv > 2000) else 0.0
        chain *= (1 + r)
        wp.append(dict(month=m['month'], value=v, flow=net_in, r=r * 100, index=chain * 100))
        prevv = v

    yrs = (datetime.date.fromisoformat(b.asof) - datetime.date.fromisoformat(months[0]['asof'])).days / 365.25
    twr_total = (chain - 1) * 100
    twr_pa = ((chain ** (1 / yrs)) - 1) * 100 if yrs > 0 else 0.0

    BENCHMARKS = _CFG['benchmarks']
    benchmarks = []
    for bmdef in BENCHMARKS:
        secname = bmdef['security']
        sid = next((u for u, sc in b.sec.items() if sc['name'] == secname), None)
        if not sid or not b.d['prices'].get(sid):
            continue
        werte = [b.price(sid, eday(datetime.date.fromisoformat(m['asof']))) for m in months]
        i0 = next((i for i, v in enumerate(werte) if v and v > 0), None)
        if i0 is None or i0 >= len(werte) - 12:
            continue
        basis = werte[i0]
        idx = [None] * i0 + [(v / basis * 100 if v and v > 0 else None) for v in werte[i0:]]
        letzte = idx[-1]
        pchain = 1.0
        for e in wp[i0 + 1:]:
            pchain *= (1 + e['r'] / 100)
        d0 = datetime.date.fromisoformat(months[i0]['asof'])
        jahre = (datetime.date.fromisoformat(b.asof) - d0).days / 365.25
        bm_pa = (((letzte / 100) ** (1 / jahre)) - 1) * 100 if letzte and jahre > 0 else None
        pf_pa = ((pchain ** (1 / jahre)) - 1) * 100 if jahre > 0 else None
        benchmarks.append(dict(
            label=bmdef['label'], security=secname, kurz=bmdef['kurz'], art=bmdef['art'],
            leitindex=bmdef['leitindex'], warnung=bmdef.get('warnung', False),
            waehrung='CAD' if bmdef.get('warnung') else b.sec[sid]['currency'],
            ticker=b.sec[sid]['ticker'], isin=b.sec[sid]['isin'],
            von=months[i0]['month'], jahre=round(jahre, 2),
            index=[dict(month=m['month'], index=i) for m, i in zip(months, idx)],
            total=letzte - 100 if letzte else None, pa=bm_pa,
            pf_total=(pchain - 1) * 100, pf_pa=pf_pa,
            differenz_pa=(pf_pa - bm_pa) if (pf_pa is not None and bm_pa is not None) else None,
        ))
    benchmarks.sort(key=lambda x: (not x['leitindex'], x['warnung']))

    years = defaultdict(lambda: defaultdict(float))
    for m in months:
        y = m['month'][:4]
        for k in ('ein', 'ent', 'sondereinlagen', 'schenkung', 'fremdmittel', 'eigeneinlage',
                  'kaltmiete', 'nk_mieter', 'bewirtschaftung',
                  'modernisierung', 'grundsteuer', 'zinsaufwand', 'zinsertrag', 'dividenden',
                  'kapitalsteuern', 'gebuehren', 'kaufnebenkosten', 'tilgung', 'annuitaet',
                  'zins_darlehen', 'darlehensauszahlung', 'kaeufe',
                  'verkaeufe', 'immokaeufe', 'delta', 'extern', 'ergebnis', 'immo_cf',
                  'wp_change', 'immo_change', 'laufend'):
            years[y][k] += m[k]
        years[y]['net_end'] = m['net']
        years[y]['liquid_end'] = m['liquid']

    obj_of_loan = {l: o for o, od in b.objects.items() for l in od['loans']}

    def _acc_label(u):
        name = b.acc[u]['name']
        no = obj_of_loan.get(u)
        if no and no in b.objects:
            return '%s · %s' % (name, b.objects[no]['name'])
        return name

    darlehen = []
    for a, acc in b.acc.items():
        if b.acc_group.get(a) != 'Darlehen':
            continue
        saldo = -snap['cash'].get(a, 0.0)
        if abs(saldo) < 1:
            continue
        zins12 = sum(t['amount'] for t in b.tx if t['type'] == 'INTEREST_CHARGE'
                     and t['account'] == a and t['date'][:7] in set(m['month'] for m in months[-12:])
                     and t['date'] <= b.asof)
        letzte = max((t for t in b.tx if t['type'] == 'INTEREST_CHARGE' and t['account'] == a
                      and t['date'] <= b.asof), key=lambda t: t['date'], default=None)
        run = letzte['amount'] * 12 if letzte else 0.0
        ann12 = sum(t['amount'] for t in b.tx if t['type'] == 'CASH_TRANSFER'
                    and t['otherAccount'] == a and t['date'][:7] in set(m['month'] for m in months[-12:])
                    and t['date'] <= b.asof)
        no = obj_of_loan.get(a)
        od = b.objects.get(no) if no else None
        darlehen.append(dict(
            konto=acc['name'], label=_acc_label(a), objekt=int(no) if no else None,
            objektname=od['name'] if od else '', saldo=saldo,
            selbstgenutzt=(no in SELBSTGENUTZT) if no else False,
            zins12=zins12, zins_runrate=run,
            zinssatz=run / saldo * 100 if saldo else None,
            zinssatz12=zins12 / saldo * 100 if saldo else None,
            annuitaet12=ann12, tilgung12=ann12 - zins12,
            tilgungssatz=(ann12 - zins12) / saldo * 100 if saldo else None,
            letzte_zinsbuchung=letzte['date'] if letzte else None))
    darlehen.sort(key=lambda x: -x['saldo'])

    asof_d = datetime.date.fromisoformat(b.asof)
    for l in darlehen:
        zb = _stamm.zinsbindung_fuer(l['konto'])
        if not zb:
            l.update(zinsbindung_ende=None, zinsbindung_sollzins=None, zinsbindung_sondertilgung=None,
                     zinsbindung_nennbetrag=None, zinsbindung_kfw=False, zinsbindung_quelle=None,
                     zinsbindung_tage_bis_ende=None, zinsbindung_monate_bis_ende=None)
            continue
        ende_d = datetime.date.fromisoformat(zb['ende'])
        tage = (ende_d - asof_d).days
        l.update(zinsbindung_ende=zb['ende'], zinsbindung_sollzins=zb['sollzins'],
                 zinsbindung_sondertilgung=zb['sondertilgung'], zinsbindung_nennbetrag=zb['nennbetrag'],
                 zinsbindung_kfw=zb['kfw'], zinsbindung_quelle=zb['quelle'],
                 zinsbindung_tage_bis_ende=tage, zinsbindung_monate_bis_ende=round(tage / 30.44, 1))

    faelligkeitsleiste = []
    mit_bindung = [l for l in darlehen if l.get('zinsbindung_ende')]
    if mit_bindung:
        jahre = sorted({int(l['zinsbindung_ende'][:4]) for l in mit_bindung})
        gesamt_restschuld = sum(l['saldo'] for l in mit_bindung)
        for jahr in jahre:
            gruppe = [l for l in mit_bindung if int(l['zinsbindung_ende'][:4]) == jahr]
            restschuld = sum(l['saldo'] for l in gruppe)
            zins_gewichtet = (sum(l['saldo'] * l['zinsbindung_sollzins'] for l in gruppe) / restschuld
                              if restschuld else None)
            faelligkeitsleiste.append(dict(
                jahr=jahr,
                konten=[dict(konto=l['konto'], label=l['label'], saldo=l['saldo'],
                             sollzins=l['zinsbindung_sollzins'], ende=l['zinsbindung_ende'],
                             kfw=l['zinsbindung_kfw']) for l in gruppe],
                restschuld=restschuld,
                anteil_gesamt=restschuld / gesamt_restschuld * 100 if gesamt_restschuld else None,
                zins_gewichtet=zins_gewichtet,
                mehrkosten_stress_pa=restschuld * ANSCHLUSS_STRESS_PP / 100,
                kfw_hinweis=any(l['zinsbindung_kfw'] for l in gruppe)))
        faellig_12m = sum(l['saldo'] for l in mit_bindung
                          if l['zinsbindung_tage_bis_ende'] is not None and 0 <= l['zinsbindung_tage_bis_ende'] <= 365)
        faellig_36m = sum(l['saldo'] for l in mit_bindung
                          if l['zinsbindung_tage_bis_ende'] is not None and 0 <= l['zinsbindung_tage_bis_ende'] <= 1096)
        naechste = min(mit_bindung, key=lambda l: l['zinsbindung_tage_bis_ende'])
    else:
        faellig_12m = faellig_36m = 0.0
        naechste = None
    ohne_bindung = [l for l in darlehen if not l.get('zinsbindung_ende')]

    cur = months[-1]
    last12 = months[-12:]
    ytd = [m for m in months if m['month'][:4] == b.asof[:4]]
    def s12(k): return sum(m[k] for m in last12)
    def sytd(k): return sum(m[k] for m in ytd)

    immo_val = sum(o['value'] for o in objs)
    immo_debt = sum(o['loan'] for o in objs)
    inv = [o for o in objs if not o['selbstgenutzt']]
    eig = [o for o in objs if o['selbstgenutzt']]
    inv_val = sum(o['value'] for o in inv); inv_debt = sum(o['loan'] for o in inv)
    eig_val = sum(o['value'] for o in eig); eig_debt = sum(o['loan'] for o in eig)
    inv_rent = sum(o['rent12'] for o in inv); inv_cost = sum(o['cost12'] for o in inv)
    inv_int = sum(o['interest12'] for o in inv); inv_red = sum(o['redemption12'] for o in inv)
    inv_nk = sum(o['nk12'] for o in inv)
    inv_ann = sum(o['annuitaet12'] for o in inv)
    inv_ek0 = sum(o['ek_einsatz'] for o in inv)
    inv_kp = sum(o['kaufpreis'] for o in inv)
    inv_opacc = sum(o['opaccount'] for o in inv)
    eig_int = sum(o['interest12'] for o in eig); eig_cost = sum(o['cost12'] for o in eig)
    eig_int_run = sum(o['interest_runrate'] for o in eig)
    inv_int_run = sum(o['interest_runrate'] for o in inv)
    eig_red = sum(o['redemption12'] for o in eig); eig_capex = sum(o['capex12'] for o in eig)
    liquid = cur['liquid']
    wp_pos = [p for p in positions if p['group'] != 'Immobilien']
    top = wp_pos[:10]
    wp_total = sum(p['value'] for p in wp_pos)

    buckets = defaultdict(float)
    for p in positions:
        if p['group'] == 'Immobilien':
            continue
        dep = p['depot']
        key = {'Aktien': 'Einzelaktien', 'ETF': 'ETF', 'Crypto': 'Krypto',
               'Crowdinvesting': 'Crowdinvesting', 'Riester Depot': 'Riester',
               'Immo Depot': 'ETF'}.get(dep, dep)
        buckets[key] += p['value']
    buckets['P2P-Kredite'] += cur['P2P']
    buckets['Tagesgeld / Giro'] += cur['Liquidität'] + cur['Krypto-Konten']

    kpi = dict(
        net=cur['net'], assets=cur['assets'], debt=cur['debt'],
        liquid=liquid, immo_val=immo_val, immo_debt=immo_debt,
        immo_equity=immo_val - immo_debt,
        ltv=immo_debt / immo_val * 100 if immo_val else 0,
        eigenkapitalquote=cur['net'] / cur['assets'] * 100 if cur['assets'] else 0,
        wp_total=wp_total,
        immo_konten=cur['Immobilien-Konten'],
        rent12=s12('kaltmiete'), nk12=s12('nk_mieter'), bewirt12=s12('bewirtschaftung'),
        modern12=s12('modernisierung'), grundsteuer12=s12('grundsteuer'),
        zins12=s12('zinsaufwand'), tilgung12=s12('tilgung'),
        immo_cf12=s12('immo_cf'), div12=s12('dividenden'), zinsertrag12=s12('zinsertraege')
        if 'zinsertraege' in cur else s12('zinsertrag'),
        zinsertrag_p2p12=s12('zinsertrag_p2p'),
        extern12=s12('extern'), delta12=s12('delta'), ergebnis12=s12('ergebnis'),
        wp_change12=s12('wp_change'), immo_change12=s12('immo_change'), laufend12=s12('laufend'),
        delta_ytd=sytd('delta'), extern_ytd=sytd('extern'), ergebnis_ytd=sytd('ergebnis'),
        wp_change_ytd=sytd('wp_change'), immo_change_ytd=sytd('immo_change'),
        laufend_ytd=sytd('laufend'),
        delta_m=cur['delta'], month=cur['month'],
        annuitaet12=s12('annuitaet'),
        neu_darlehen12=s12('darlehensauszahlung'),
        zinssatz=s12('zins_darlehen') / immo_debt * 100 if immo_debt else 0,
        tilgungssatz=s12('tilgung') / immo_debt * 100 if immo_debt else 0,
        mietrendite=inv_rent / inv_val * 100 if inv_val else 0,
        nettomietrendite=(inv_rent + inv_nk - inv_cost) / inv_val * 100 if inv_val else 0,
        inv_zinssatz=inv_int / inv_debt * 100 if inv_debt else 0,
        inv_tilgungssatz=inv_red / inv_debt * 100 if inv_debt else 0,
        inv_noi=inv_rent + inv_nk - inv_cost,
        inv_ueberschuss=inv_rent + inv_nk - inv_cost - inv_int,
        eigenkapitalrendite=((inv_rent + inv_nk - inv_cost - inv_int) / (inv_val - inv_debt) * 100
                             if inv_val - inv_debt > 0 else 0),
        eigenkapitalrendite_einsatz=((inv_rent + inv_nk - inv_cost - inv_int) / inv_ek0 * 100
                                     if inv_ek0 > 0 else None),
        inv_ek0=inv_ek0, inv_kaufpreis=inv_kp, inv_wertaenderung=inv_val - inv_kp,
        inv_opacc=inv_opacc,
        inv_val=inv_val, inv_debt=inv_debt, inv_equity=inv_val - inv_debt,
        inv_ltv=inv_debt / inv_val * 100 if inv_val else 0,
        inv_rent=inv_rent, inv_cost=inv_cost, inv_int=inv_int, inv_red=inv_red, inv_nk=inv_nk,
        inv_ann=inv_ann,
        inv_cf=inv_rent + inv_nk - inv_cost - inv_ann,
        dscr=(inv_rent + inv_nk - inv_cost) / inv_ann if inv_ann else None,
        dscr_gesamt=((inv_rent + inv_nk - inv_cost) / s12('annuitaet')
                     if s12('annuitaet') else None),
        n_inv=len(inv), n_eig=len(eig),
        eig_val=eig_val, eig_debt=eig_debt, eig_equity=eig_val - eig_debt,
        eig_ltv=eig_debt / eig_val * 100 if eig_val else 0,
        eig_int=eig_int, eig_int_run=eig_int_run, inv_int_run=inv_int_run, eig_cost=eig_cost, eig_red=eig_red, eig_capex=eig_capex,
        eig_kosten12=eig_int + eig_cost,
        eig_annuitaet12=sum(o['annuitaet12'] for o in eig),
        eig_ek0=sum(o['ek_einsatz'] for o in eig),
        eig_kaufpreis=sum(o['kaufpreis'] for o in eig),
        eig_capex_total=sum(o['capex_total'] for o in eig),
        eig_int_total=sum(o['interest_total'] for o in eig),
        eig_cost_total=sum(o['cost_total'] for o in eig),
        eig_rent_total=sum(o['rent_total'] for o in eig),
        eig_nk_total=sum(o['nk_total'] for o in eig),
        cash=cur['Liquidität'] + cur['Immobilien-Konten'] + cur['Krypto-Konten'],
        top1=konsolidiert[0]['value'] / wp_total * 100 if (wp_total and konsolidiert) else 0,
        top1_name=konsolidiert[0]['name'] if konsolidiert else '—',
        top1_wert=konsolidiert[0]['value'] if konsolidiert else 0.0,
        top5=sum(x['value'] for x in konsolidiert[:5]) / wp_total * 100 if wp_total else 0,
        bewertungshinweis_summe=sum(x['wert'] for x in bewertungshinweise),
        n_bewertungshinweise=len(bewertungshinweise),
        n_pos=len(wp_pos),
        krypto_quote=sum(p['value'] for p in wp_pos if p['depot'] == 'Crypto') / liquid * 100 if liquid else 0,
        free_cash=cur['Liquidität'] + cur['Krypto-Konten'],
        immo_cash=cur['Immobilien-Konten'],
        twr_total=twr_total, twr_pa=twr_pa,
        zb_faellig_12m=faellig_12m, zb_faellig_36m=faellig_36m,
        zb_faellig_12m_anteil=faellig_12m / immo_debt * 100 if immo_debt else None,
        zb_naechste_konto=naechste['label'] if naechste else None,
        zb_naechste_datum=naechste['zinsbindung_ende'] if naechste else None,
        zb_naechste_monate=naechste['zinsbindung_monate_bis_ende'] if naechste else None,
        zb_mehrkosten_12m_stress=faellig_12m * ANSCHLUSS_STRESS_PP / 100,
        zb_mehrkosten_36m_stress=faellig_36m * ANSCHLUSS_STRESS_PP / 100,
        zb_anzahl_ohne_daten=len(ohne_bindung),
        ruecklage_soll_m2=sum(o['ruecklage_soll_m2'] or 0 for o in objs if not o['selbstgenutzt']),
        ruecklage_m2_objekte_ohne_wohnflaeche=sum(1 for o in objs if not o['selbstgenutzt']
                                                   and not o['wohnflaeche_m2']),
    )
    buckets = dict(sorted(buckets.items(), key=lambda x: -x[1]))

    inv_nos = {str(o['no']) for o in inv}
    keys = [m['month'] for m in months]

    def _cashflows(nos):
        accs = {b.objects[n]['account'] for n in nos if n in b.objects}
        loans = {l for n in nos if n in b.objects for l in b.objects[n]['loans']}
        secs = {b.objects[n]['sec'] for n in nos if n in b.objects}
        cf = defaultdict(float)
        for t in b.tx:
            if t['date'] > b.asof:
                continue
            m = t['date'][:7]; ty = t['type']; a = t['account']
            note = (t['note'] or '').lower()
            if ty == 'PURCHASE' and t['security'] in secs:
                cf[m] -= t['amount']
            elif ty == 'DIVIDEND' and t['security'] in secs:
                cf[m] += t['amount']
            elif ty == 'CASH_TRANSFER' and a in loans:
                cf[m] += t['amount']
            elif ty == 'CASH_TRANSFER' and t['otherAccount'] in loans:
                cf[m] -= t['amount']
            elif a in accs and ty == 'DEPOSIT':
                if not (any(w in note for w in Book.CAPITAL_WORDS) or t['amount'] >= 20000):
                    cf[m] += t['amount']
            elif a in accs and ty in ('REMOVAL', 'FEE', 'TAX'):
                cf[m] -= t['amount']
        return cf

    def _irr(cf, endwert):
        flows = [cf.get(k, 0.0) for k in keys]
        flows[-1] += endwert
        first = next((i for i, v in enumerate(flows) if abs(v) > 1e-9), None)
        if first is None:
            return None
        flows = flows[first:]

        def npv(rate):
            return sum(v / (1 + rate) ** (i / 12) for i, v in enumerate(flows))

        if len(flows) <= 2 or flows[0] >= 0:
            return None
        lo, hi = -0.95, 3.0
        if npv(lo) * npv(hi) >= 0:
            return None
        for _ in range(200):
            mid = (lo + hi) / 2
            if npv(lo) * npv(mid) <= 0:
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2 * 100

    endwert = inv_val - inv_debt
    irr = _irr(_cashflows(inv_nos), endwert)

    for o in objs:
        no = str(o['no'])
        cfo = _cashflows({no})
        o['irr'] = _irr(cfo, o['value'] - o['loan'])
        if o['irr'] is None:
            reihe = [cfo.get(kk, 0.0) for kk in keys]
            erste = next((v for v in reihe if abs(v) > 1e-9), 0.0)
            o['irr_hinweis'] = (
                'Nicht berechenbar: Kaufpreis und Nebenkosten wurden vollständig aus Darlehen '
                'bezahlt, es floss zu keinem Zeitpunkt eigenes Kapital ab. Eine Rendite auf das '
                'eingesetzte Eigenkapital gibt es damit nicht.'
                if erste > 0 else
                'Nicht berechenbar: die Zahlungsreihe wechselt nicht eindeutig das Vorzeichen.')
        else:
            o['irr_hinweis'] = None
        o['haltedauer'] = (
            (datetime.date.fromisoformat(b.asof) - datetime.date.fromisoformat(o['kaufdatum'])).days / 365.25
            if o['kaufdatum'] else None)
        o['verlauf'] = [dict(month=m['month'], wert=m['objekte'][no]['wert'],
                             darlehen=m['objekte'][no]['darlehen'],
                             konto=m['objekte'][no]['konto'])
                        for m in months if m['objekte'].get(no, {}).get('wert', 0) > 0
                        or m['objekte'].get(no, {}).get('darlehen', 0) > 0]
    kpi['irr_immobilien'] = irr
    kpi['irr_endwert'] = endwert

    tot = lambda key: sum(m[key] for m in months)
    herkunft = [
        ('Eigene Sparleistung', tot('ein') - tot('ent') + tot('eigeneinlage')),
        ('Schenkung und Erbe', tot('schenkung')),
        ('Fremdmittel und Zuschüsse', tot('fremdmittel')),
        ('Wertsteigerung Immobilien', tot('immo_change')),
        ('Kursgewinne Wertpapiere', tot('wp_change')),
        ('Laufendes Ergebnis nach Kosten', tot('laufend')),
    ]
    kpi['schenkung_total'] = tot('schenkung')
    kpi['fremdmittel_total'] = tot('fremdmittel')
    kpi['eigeneinlage_total'] = tot('eigeneinlage')
    kpi['herkunft_summe'] = sum(v for _, v in herkunft)
    totals = dict(
        ertrag=tot('kaltmiete') + tot('nk_mieter') + tot('dividenden') + tot('zinsertrag'),
        zins=tot('zinsaufwand'),
        bewirt=tot('bewirtschaftung') + tot('grundsteuer'),
        modern=tot('modernisierung'),
        kaufnebenkosten=tot('kaufnebenkosten'),
        laufend=tot('laufend'),
        eigenheim=kpi['eig_int_total'] + kpi['eig_cost_total'],
        eigenheim_ertrag=kpi['eig_rent_total'] + kpi['eig_nk_total'],
        eigenheim_saldo=(kpi['eig_rent_total'] + kpi['eig_nk_total']
                         - kpi['eig_int_total'] - kpi['eig_cost_total']),
        laufend_invest=(tot('laufend') - kpi['eig_rent_total'] - kpi['eig_nk_total']
                        + kpi['eig_int_total'] + kpi['eig_cost_total']),
    )

    steuern = _steuer.build(objs, kpi)
    kpi['grenzsteuersatz'] = steuern['satz']
    kpi['steuer_ergebnis'] = steuern['ergebnis']
    kpi['steuer_last'] = steuern['steuer']
    kpi['cashflow_nach_steuern'] = steuern['cashflow_nach_steuern']
    kpi['afa_wirkung'] = steuern['afa_wirkung']
    kpi['rendite_nach_steuern'] = steuern['rendite_nach_steuern']
    kpi['eigenheim_steuernachteil'] = steuern['eigenheim_steuernachteil']
    vorschau = _forecast.build(b, snap, months, _acc_label)
    stresstest = _stress.build(kpi, months, vorschau)
    kpi['frei_ende'] = vorschau['frei_ende']
    kpi['frei_ende_k'] = vorschau['frei_ende_k']
    kpi['frei_tief'] = vorschau['frei_tief']
    kpi['frei_tief_monat'] = vorschau['frei_tief_monat']
    kpi['n_warnungen'] = len(vorschau['warnungen'])
    kpi['stress_kombi_net'] = stresstest['szenarien'][-1]['net']
    kpi['stress_kombi_ek'] = stresstest['szenarien'][-1]['ek_quote']
    kpi['stress_zins_cf'] = next(x['cashflow'] for x in stresstest['szenarien'] if x['key'] == 'zins')

    _schwellen.build(kpi, vorschau)
    vergleich = None
    if mit_vergleich:
        vor = _vormonat(b.asof)
        if vor >= months[0]['asof']:
            alt = build(path, vor, mit_vergleich=False)
            av = alt['kpi']
            vergleich = dict(
                stichtag=vor, monat=alt['kpi']['month'],
                werte={k: dict(label=lab, format=fmt,
                               jetzt=kpi.get(k), vorher=av.get(k),
                               delta=(None if kpi.get(k) is None or av.get(k) is None
                                      else kpi[k] - av[k]))
                       for k, (lab, fmt) in VERGLEICH_KPIS.items()})

    bewertung = _schwellen.build(kpi, vorschau, vergleich)

    return dict(
        asof=b.asof, fx=FX, fx_date=FX_DATE, kpi=kpi, darlehen=darlehen,
        faelligkeitsleiste=faelligkeitsleiste,
        konsolidiert=konsolidiert, bewertungshinweise=bewertungshinweise,
        vorschau=vorschau, stress=stresstest, steuer=steuern, buckets=buckets, herkunft=herkunft, totals=totals,
        vergleich=vergleich, bewertung=bewertung, glossar=_schwellen.GLOSSAR, lesepfade=_schwellen.LESEPFADE,
        accounts={u: dict(name=a['name'], label=_acc_label(u), group=b.acc_group[u],
                          balance=snap['cash'].get(u, 0.0))
                  for u, a in b.acc.items()},
        portfolios={u: p['name'] for u, p in b.pf.items()},
        snapshot={k: v for k, v in snap.items() if k != 'positions'},
        positions=positions, months=months, flows=fl, objects=objs,
        years={y: dict(v) for y, v in years.items()},
        wp_index=wp, twr_total=twr_total, twr_pa=twr_pa, benchmarks=benchmarks,
        realized={b.sec[k]['name']: v for k, v in realized.items() if abs(v) > 0.005},
    )


def _minus12(asof):
    d = datetime.date.fromisoformat(asof)
    return d.replace(year=d.year - 1).isoformat()


def anonymisieren(d):
    """Anonymisierte Fassung zum Teilen ausserhalb der Familie: Objektadressen auf Stadt/
    Stadtteil verkuerzt, Mieternamen entfernt, konfigurierte Kontonamen ersetzt. Aendert
    nichts an den Zahlen selbst."""
    import copy
    d = copy.deepcopy(d)
    kontoname_anonym = _CFG['kontoname_anonym']
    for o in d['objects']:
        stamm = _stamm.stamm_fuer(o['no'], anonym=True) or {}
        o['lage'] = stamm.get('lage', o.get('lage'))
        o['mieter_name'] = None
        if o.get('stamm_quelle'):
            o['stamm_quelle'] = 'siehe Konfiguration (anonymisierte Fassung)'
    for a in d['accounts'].values():
        neu = kontoname_anonym.get(a['name'])
        if neu:
            a['name'] = neu
            a['label'] = neu if ' · ' not in a['label'] else neu + a['label'][a['label'].index(' · '):]

    # Objektnamen stammen aus den Kontonamen ("Immobilie 1: Bergstrasse 14") und tauchen
    # deshalb in vielen Feldern auf (Konten, Darlehen, Dauerauftraege, Steuer, Positionen).
    # Darum ueberall ersetzen, nicht nur in d['objects'].
    ersatz = dict(kontoname_anonym)
    for o in d['objects']:
        no = str(o['no'])
        voll = _stamm.stamm_fuer(no) or {}
        kurz = voll.get('lage_anonym')
        if voll.get('lage') and kurz and voll['lage'] != kurz:
            ersatz[voll['lage']] = kurz
        if voll.get('mieter_name'):
            ersatz[voll['mieter_name']] = 'Mieter:in'
        if o.get('name') and len(o['name']) >= 4:
            ersatz[o['name']] = 'Objekt %s' % no + (' (%s)' % kurz if kurz else '')
            o['name'] = ersatz[o['name']]
    muster = sorted((k for k in ersatz if k), key=len, reverse=True)

    def weg(v, schluessel=''):
        if isinstance(v, dict):
            return {k: (v2 if k in ('glossar', 'lesepfade') else weg(v2, k)) for k, v2 in v.items()}
        if isinstance(v, list):
            return [weg(x, schluessel) for x in v]
        if isinstance(v, str):
            if schluessel.endswith('quelle') and v:
                return 'siehe Konfiguration (anonymisierte Fassung)'
            for m in muster:
                if m in v:
                    v = v.replace(m, ersatz[m])
        return v
    return weg(d)


if __name__ == '__main__':
    import sys
    r = build(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    json.dump(r, open('data.json', 'w'), ensure_ascii=False, indent=1)
    print('Stichtag', r['asof'])
    print('Vermoegen %.0f  Schulden %.0f  Netto %.0f' % (r['snapshot']['assets'], r['snapshot']['debt'], r['snapshot']['net']))
    print('TWR Wertpapiere gesamt %.1f%%  p.a. %.1f%%' % (r['twr_total'], r['twr_pa']))
