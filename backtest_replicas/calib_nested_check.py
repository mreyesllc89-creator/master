"""Nested picks (rule C2 step 7) on existing grids, without rewriting out/calib_rule_<s>.json.
Usage: python3 -I calib_nested_check.py <strategy> [...]"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calib_analyze as ca
for s in sys.argv[1:]:
    D = json.load(open(ca.W + f'out/calib_{s}_dims.json'))
    n = pos = 0
    for pair in ('BTC', 'XAU'):
        for tf in ca.TFS:
            if not os.path.exists(ca.W + f'out/calib_{s}_{pair}_{tf}.parquet'):
                continue
            r = ca.analyze(s, pair, tf, D, None, verify=False)
            f, v = r['nested_fwd'], r['nested_rev']
            for x in (f, v):
                if 'other_half' in x:
                    n += 1
                    pos += x['other_half'] > 0
            print(s, pair, tf, '| rule C pick', bool(r['pick']), '| fwd', f.get('pass'), f.get('other_half'), f.get('twin_other_half'),
                  '| rev', v.get('pass'), v.get('other_half'), v.get('twin_other_half'), flush=True)
    print(s, 'nested picks', n, 'positive on the other half', pos)
