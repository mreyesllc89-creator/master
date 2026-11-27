"""Markdown tables of the calibration (out/calib_rule_<strategy>.json, written by calib_analyze.py).
Usage: python3 -I calib_tables.py <strategy> <decimals>"""
import json
import sys

s, dec = sys.argv[1], int(sys.argv[2])
UNIT = sys.argv[3] if len(sys.argv) > 3 else '%'   # 'R' for strategies scored in R
R = json.load(open(f'out/calib_rule_{s}.json'))
TFS = ['1', '5', '15', '30', '60', '120', '240']
TFL = {'1': '1m', '5': '5m', '15': '15m', '30': '30m', '60': '1h', '120': '2h', '240': '4h'}
PN = {'BTC': 'BTCUSD', 'XAU': 'XAUUSD'}


def f(x):
    return 'n/a' if x is None else (f'{x:+,.{dec}f}R' if UNIT == 'R' else f'{x:+.{dec}f}%')


def hold(h):
    if 'mean' not in h:
        return 'too few settings with 30+ trades per half: FAIL'
    return f"{f(h['mean'])} vs {f(h['q95'])}, {h['share_pos']:.0%} positive: {'pass' if h['pass'] else 'FAIL'}"


def best(b):
    if not b:
        return 'none'
    return f"{f(b['net_pct'])} ({f(b['h1r_pct'])} / {f(b['h2r_pct'])}, {int(b['trades'])} trades)"


def nest(r):
    out = []
    for k in ('nested_fwd', 'nested_rev'):
        x = r.get(k) or {}
        out.append(f(x['other_half']) if 'other_half' in x else 'none')
    return ' / '.join(out)


NESTED = any('nested_fwd' in r for r in R.values())
for pair in ('BTC', 'XAU'):
    print(f'\n#### {PN[pair]}\n')
    print('| TF | Different results | Positive in both halves: normal / inverted | Typical result: normal / inverted | Best normal (halves, trades) | Best inverted (halves, trades) | Forward hold-out | Reverse hold-out |' + (' Chosen on one half, result on the other: first to second / second to first |' if NESTED else '') + ' Verdict |')
    print('|---|---|---|---|---|---|---|---|' + ('---|' if NESTED else '') + '---|')
    for tf in TFS:
        r = R.get(f'{pair}|{tf}')
        if not r:
            continue
        n, i = r['by_direction']['normal'], r['by_direction']['inverted']
        ok = r.get('passes_c2', r['passes']) if NESTED else r['passes']
        rs = r.get('reasons_c2', r['reasons']) if NESTED else r['reasons']
        if ok:
            v = '**rule passed**: ' + r['pick']['setting']
        elif r['pick']:
            v = 'no setting: ' + '; '.join(dict.fromkeys(x.split(':')[0] for x in rs))
        else:
            v = 'no setting: ' + r['why_no_pick'].split(' (')[0]
        print(f"| {TFL[tf]} | {r['pool']:,} | {n['candidates']:,} / {i['candidates']:,} | {f(n['median_net_eligible'])} / {f(i['median_net_eligible'])} | "
              f"{best(n['best_worst_half'])} | {best(i['best_worst_half'])} | {hold(r['forward'])} | {hold(r['reverse'])} | " + (f"{nest(r)} | " if NESTED else '') + f"{v} |")
