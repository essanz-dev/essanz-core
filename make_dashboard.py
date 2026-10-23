# -*- coding: utf-8 -*-
"""Setzt Template, Daten, Charts und Empfehlungen zum fertigen Dashboard zusammen."""
import json, os, sys
import empfehlungen

HERE = os.path.dirname(os.path.abspath(__file__))

def html(data):
    """Das fertige Dashboard als HTML-Text (fuer Datei und Browser-App)."""
    tpl = open(os.path.join(HERE, 'template.html'), encoding='utf-8').read()
    js  = open(os.path.join(HERE, 'dash.js'), encoding='utf-8').read()
    payload = dict(
        asof=data['asof'], fx_date=data['fx_date'], kpi=data['kpi'],
        buckets=data['buckets'], objects=data['objects'], years=data['years'],
        herkunft=data['herkunft'], benchmarks=data['benchmarks'],
        vorschau=data['vorschau'], stress=data['stress'], steuer=data['steuer'],
        darlehen=data['darlehen'], konsolidiert=data['konsolidiert'],
        faelligkeitsleiste=data['faelligkeitsleiste'],
        bewertungshinweise=data['bewertungshinweise'], totals=data['totals'],
        vergleich=data['vergleich'], bewertung=data['bewertung'],
        glossar=data['glossar'], lesepfade=data['lesepfade'],
        wp_index=data['wp_index'],
        positions=[p for p in data['positions'] if p['group'] != 'Immobilien'],
        months=[{kk: m.get(kk) for kk in
                 ('month','net','assets','debt','Immobilien','Wertpapiere','P2P','Liquidität',
                  'Krypto-Konten','Immobilien-Konten','Darlehen','delta','extern','wp_change',
                  'immo_change','laufend','liquid')} for m in data['months']],
        accounts=sorted([a for a in data['accounts'].values() if abs(a['balance']) > 0.005],
                        key=lambda a: -a['balance']),
    )
    empf, _ = empfehlungen.build(data)
    return (tpl.replace('/*__DATA__*/null', json.dumps(payload, ensure_ascii=False))
               .replace('/*__JS__*/', js)
               .replace('<!--__EMPF__-->', empf))


def build(data, out_path):
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html(data))
    return out_path

if __name__ == '__main__':
    data = json.load(open(os.path.join(HERE, 'data.json'), encoding='utf-8'))
    print(build(data, sys.argv[1] if len(sys.argv) > 1 else 'dashboard.html'))
