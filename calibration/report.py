import json, os, sys
D = sys.argv[1] if len(sys.argv) > 1 else "results3"
for tf in (1, 5, 15, 30, 60, 120, 240, 480, 1440):
    f = f"{D}/preset_{tf}.json"
    if not os.path.exists(f):
        print(f"--- {tf}: pending"); continue
    r = json.load(open(f))
    s = r["signal"]
    print(f"\n=== {tf}m  entry={r['entry']}  filter={r['filter']}\n    exits={r['exits']}")
    if s.get("is_n"):
        print(f"    signals: IS n={s['is_n']:.0f} p(+1ATR first)={s['is_p1']:.3f} fwd20={s['is_f20']:.3f} ATR t={s['is_t']:.2f} minYear={s['is_y_min']:.3f} | OOS n={s['oos_n']:.0f} p={s['oos_p1']:.3f} fwd20={s['oos_f20']:.3f} t={s['oos_t']:.2f}")
    for k, v in r["results"].items():
        g = lambda x: v.get(x, float('nan'))
        print(f"    {k:60s} IS n={g('is_n'):4.0f} mean={g('is_mean'):6.3f} pf={g('is_pf'):5.2f} win={g('is_win'):4.2f} dd={g('is_dd'):6.1f} sum={g('is_sum'):7.1f} yrs={g('sum_2023'):6.1f}/{g('sum_2024'):6.1f}/{g('sum_2025'):6.1f} | OOS n={g('oos_n'):4.0f} mean={g('oos_mean'):6.3f} pf={g('oos_pf'):5.2f} win={g('oos_win'):4.2f} sum={g('oos_sum'):7.1f} re={g('n_re'):.0f}")
