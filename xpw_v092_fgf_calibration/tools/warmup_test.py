"""No entry before the in-sample start (warm-up prefix), and drawdown is mark-to-market."""
import random
import numpy as np
import xpw_run as R, xpw_search2 as S
bad = 0; n = 0; dd_up = 0
for symbol, tf in (("XAUUSD", 15), ("BTCUSD", 240), ("XAUUSD", 240)):
    w = S.windows(symbol, tf); mk = R.Market(symbol, start=w["start"]); rng = random.Random(3)
    bt = mk.bars(tf)[0]
    assert bt[0] < w["is_"][0] - 100 * 86400, "warm-up data missing"
    for si, style in enumerate(S.STYLES):
        for d, _ in S.DIRS:
            p = S.sample(rng, symbol, tf, style, d, True); res = S.run(mk, p, w); n += 1
            if res["n"] and bt[res["entry_i"]].min() < w["is_"][0]: bad += 1; print("EARLY ENTRY", symbol, tf, style[3])
            m = R.metrics(res, *w["is_"]); mo = R.metrics(res, *w["oos"]); mf = R.metrics(res, *w["fwd"]); ma = R.metrics(res, w["is_"][0], w["oos"][1])
            # windows add up: every dollar is booked exactly once
            assert abs(m["net"] + mo["net"] + mf["net"] - float(res["pnl"].sum())) < 1e-6, (symbol, tf, style[3])
            assert abs(m["net"] + mo["net"] - ma["net"]) < 1e-6
            i1 = int(np.searchsorted(bt, w["oos"][1]))
            assert abs(ma["net"] - float(res["equity"][i1 - 1])) < 1e-6      # in+out of sample net == equity at the out-of-sample end
            if m["maxdd"] > 0: dd_up += 1
print("runs", n, "early entries", bad, "runs with drawdown", dd_up)
