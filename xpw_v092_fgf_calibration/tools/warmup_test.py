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
            m = R.metrics(res, *w["is_"])
            pnl = res["pnl"][(bt[res["exit_i"]] >= w["is_"][0]) & (bt[res["exit_i"]] < w["is_"][1])]
            closed = float((np.maximum.accumulate(np.concatenate(([0.0], np.cumsum(pnl))))[1:] - np.cumsum(pnl)).max()) if len(pnl) else 0.0
            assert m["maxdd"] >= closed - 1e-9
            if m["maxdd"] > closed + 1e-9: dd_up += 1
            assert m["wins"] == int((pnl > 0).sum())
print("runs", n, "early entries", bad, "runs where mark-to-market drawdown exceeds closed-trade drawdown", dd_up)
