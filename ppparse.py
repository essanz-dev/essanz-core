"""Parser fuer Portfolio-Performance-Dateien (Binaerformat PPPBV1, Protobuf)."""
import struct, zipfile, io, datetime

def _rv(b, i):
    r = 0; s = 0
    while True:
        x = b[i]; i += 1
        r |= (x & 0x7f) << s
        if not x & 0x80:
            return r, i
        s += 7

def fields(b):
    i = 0; out = []; n = len(b)
    while i < n:
        k, i = _rv(b, i)
        f = k >> 3; w = k & 7
        if w == 0:
            v, i = _rv(b, i)
        elif w == 2:
            l, i = _rv(b, i); v = b[i:i+l]; i += l
        elif w == 5:
            v = struct.unpack('<f', b[i:i+4])[0]; i += 4
        elif w == 1:
            v = struct.unpack('<d', b[i:i+8])[0]; i += 8
        else:
            raise ValueError('unbekannter wire type %d' % w)
        out.append((f, w, v))
    return out

def _d(b, repeated=()):
    o = {}
    for f, w, v in fields(b):
        if f in repeated:
            o.setdefault(f, []).append(v)
        else:
            o[f] = v
    return o

def _s(v, default=''):
    if v is None: return default
    return v.decode('utf-8') if isinstance(v, bytes) else v

TX_TYPES = {0:'PURCHASE',1:'SALE',2:'INBOUND_DELIVERY',3:'OUTBOUND_DELIVERY',
            4:'SECURITY_TRANSFER',5:'CASH_TRANSFER',6:'DEPOSIT',7:'REMOVAL',
            8:'DIVIDEND',9:'INTEREST',10:'INTEREST_CHARGE',11:'TAX',12:'TAX_REFUND',
            13:'FEE',14:'FEE_REFUND'}
UNIT_TYPES = {0:'GROSS_VALUE', 1:'TAX', 2:'FEE'}


def load(path):
    raw = open(path, 'rb').read()
    if raw[:2] == b'PK':
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            name = 'data.portfolio' if 'data.portfolio' in z.namelist() else z.namelist()[0]
            raw = z.read(name)
    if raw[:6] != b'PPPBV1':
        raise ValueError('Kein Portfolio-Performance-Binaerformat (PPPBV1).')
    top = fields(raw[6:])

    accounts, portfolios, securities, prices, txs, taxonomies = {}, {}, {}, {}, [], []

    for f, w, v in top:
        if f == 3:
            a = _d(v)
            accounts[_s(a.get(1))] = dict(uuid=_s(a.get(1)), name=_s(a.get(2)),
                                          currency=_s(a.get(3), 'EUR'), retired=bool(a.get(6, 0)))
        elif f == 4:
            p = _d(v)
            portfolios[_s(p.get(1))] = dict(uuid=_s(p.get(1)), name=_s(p.get(2)),
                                            retired=bool(p.get(6, 0)))
        elif f == 2:
            s = _d(v, repeated=(13,))
            uid = _s(s.get(1))
            pr = []
            for x in s.get(13, []):
                xf = _d(x)
                pr.append((xf.get(1, 0), xf.get(2, 0) / 1e8))
            pr.sort()
            latest = None
            if 16 in s:
                lf = _d(s[16]); latest = (lf.get(1, 0), lf.get(2, 0) / 1e8)
            prices[uid] = pr
            securities[uid] = dict(uuid=uid, name=_s(s.get(3), '?'), currency=_s(s.get(4), 'EUR'),
                                   isin=_s(s.get(7)), ticker=_s(s.get(8)), wkn=_s(s.get(9)),
                                   feed=_s(s.get(11)), latest=latest, retired=bool(s.get(20, 0)))
        elif f == 5:
            t = _d(v, repeated=(15,))
            secs = _d(t[9]).get(1, 0)
            date = datetime.datetime.utcfromtimestamp(secs).date()
            units = []
            for u in t.get(15, []):
                uf = _d(u)
                units.append(dict(type=UNIT_TYPES.get(uf.get(1, 0)), amount=uf.get(2, 0) / 100.0))
            txs.append(dict(uuid=_s(t.get(1)), type=TX_TYPES.get(t.get(2, 0)), date=date.isoformat(),
                            account=_s(t.get(3)) or None, portfolio=_s(t.get(4)) or None,
                            otherAccount=_s(t.get(5)) or None, otherPortfolio=_s(t.get(6)) or None,
                            currency=_s(t.get(10), 'EUR'), amount=t.get(11, 0) / 100.0,
                            shares=t.get(12, 0) / 1e8, security=_s(t.get(14)) or None,
                            note=_s(t.get(13)) or None, units=units))
        elif f == 8:
            tx = _d(v, repeated=(5,))
            cls = []
            for c in tx.get(5, []):
                cf = _d(c, repeated=(9,))
                cls.append(dict(id=_s(cf.get(1)), parent=_s(cf.get(2)) or None,
                                name=_s(cf.get(3)), color=_s(cf.get(5)),
                                assignments=[dict(target=_s(_d(x)[1]), weight=_d(x).get(2, 10000) / 10000.0)
                                             for x in cf.get(9, [])]))
            taxonomies.append(dict(uuid=_s(tx.get(1)), name=_s(tx.get(2)), classifications=cls))

    txs.sort(key=lambda t: t['date'])
    return dict(accounts=accounts, portfolios=portfolios, securities=securities,
                prices=prices, transactions=txs, taxonomies=taxonomies)
