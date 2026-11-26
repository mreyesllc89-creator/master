"""Markdown tables of the calibration (out/calib_rule_<strategy>.json, written by calib_analyze.py).
Usage: python3 -I calib_tables.py <strategy> <decimals>"""
import json
import sys

s, dec = sys.argv[1], int(sys.argv[2])
R = json.load(open(f'out/calib_rule_{s}.json'))
TFS = ['1', '5', '15', '30', '60', '120', '240']
TFL = {'1': '1m', '5': '5m', '15': '15m', '30': '30m', '60': '1h', '120': '2h', '240': '4h'}
PN = {'BTC': 'BTCUSD', 'XAU': 'XAUUSD'}


def f(x):
    return 'n/a' if x is None else f'{x:+.{dec}f}%'


def hold(h):
    if 'mean' not in h:
        return 'too few settings with 30+ trades per half: FAIL'
    return f"{f(h['mean'])} vs {f(h['q95'])}, {h['share_pos']:.0%} positive: {'pass' if h['pass'] else 'FAIL'}"


def best(b):
    if not b:
        return 'none'
    return f"{f(b['net_pct'])} ({f(b['h1r_pct'])} / {f(b['h2r_pct'])}, {int(b['trades'])} trades)"


for pair in ('BTC', 'XAU'):
    print(f'\n#### {PN[pair]}\n')
    print('| TF | Different results | Positive in both halves: normal / inverted | Typical result: normal / inverted | Best normal (halves, trades) | Best inverted (halves, trades) | Forward hold-out | Reverse hold-out | Verdict |')
    print('|---|---|---|---|---|---|---|---|---|')
    for tf in TFS:
        r = R.get(f'{pair}|{tf}')
        if not r:
            continue
        n, i = r['by_direction']['normal'], r['by_direction']['inverted']
        if r['passes']:
            v = '**rule passed**: ' + r['pick']['setting']
        elif r['pick']:
            v = 'no setting: ' + '; '.join(x.split(':')[0] for x in r['reasons'])
        else:
            v = 'no setting: ' + r['why_no_pick'].split(' (')[0]
        print(f"| {TFL[tf]} | {r['pool']:,} | {n['candidates']:,} / {i['candidates']:,} | {f(n['median_net_eligible'])} / {f(i['median_net_eligible'])} | "
              f"{best(n['best_worst_half'])} | {best(i['best_worst_half'])} | {hold(r['forward'])} | {hold(r['reverse'])} | {v} |")
