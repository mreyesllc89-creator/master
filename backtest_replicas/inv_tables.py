"""Markdown tables of the Inverted direction by-timeframe runs (out/inv_<s>_<PAIR>_<TF>.json).
Usage: python3 -I inv_tables.py <strategy> <decimals>"""
import json, sys
s, dec = sys.argv[1], int(sys.argv[2])
TFS = ['1', '5', '15', '30', '60', '120', '240']; TFL = {'1': '1m', '5': '5m', '15': '15m', '30': '30m', '60': '1h', '120': '2h', '240': '4h'}
def runs(pair, tf):
    d = json.load(open(f'out/inv_{s}_{pair}_{tf}.json'))
    return d['runs']
def get(r, key):
    for k in (key, key.replace('/', '_'), key.replace('/', '|')):
        if isinstance(r, dict) and k in r:
            return r[k]
    x = r
    for part in key.split('/'):          # nested form: runs[direction][filter][path][cost]
        x = x[part]
    return x
f = lambda x: 'n/a' if x is None else f'{x:+.{dec}f}%'
for pair in ('BTC', 'XAU'):
    print(f'\n#### {pair}\n')
    print('| TF | Filter | Trades normal / inverted | As TradingView shows: normal / inverted | 1-minute fills with our costs: normal / inverted | Inverted, both halves (1-minute fills, our costs) | PF inverted (same) |')
    print('|---|---|---|---|---|---|---|')
    for tf in TFS:
        r = runs(pair, tf)
        for flt in ('off', 'on'):
            n_tv, i_tv = get(r, f'normal/{flt}/tv/script'), get(r, f'inverted/{flt}/tv/script')
            n_mg, i_mg = get(r, f'normal/{flt}/mag/ours'), get(r, f'inverted/{flt}/mag/ours')
            pf = i_mg.get('pf')
            print(f"| {TFL[tf]} | {flt} | {n_mg['trades']:,} / {i_mg['trades']:,} | {f(n_tv['net_pct'])} / {f(i_tv['net_pct'])} | {f(n_mg['net_pct'])} / **{f(i_mg['net_pct'])}** | {f(i_mg.get('h1r_pct'))} / {f(i_mg.get('h2r_pct'))} | {'n/a' if pf is None else f'{pf:.2f}'} |")
