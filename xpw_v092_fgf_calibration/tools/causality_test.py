"""No-look-ahead check: trades closed before a cut date must be identical with and without the later data."""
import random, datetime as dt
import numpy as np
import xpw_run as R, xpw_search2 as S
TS = S.TS
total = 0; bad = 0
for symbol, tf, cut in (("XAUUSD", 60, TS(2025, 3, 5)), ("BTCUSD", 15, TS(2024, 9, 18)), ("XAUUSD", 5, TS(2026, 2, 11)), ("BTCUSD", 240, TS(2025, 6, 3))):
    w = S.windows(symbol, tf)
    full = R.Market(symbol, start=w["start"]); part = R.Market(symbol, start=w["start"], end=cut)
    rng = random.Random(5)
    for si, style in enumerate(S.STYLES):
        for d, _ in S.DIRS:
            for rep in range(2):
                p = S.sample(rng, symbol, tf, style, d, rep == 0)
                a = S.run(full, p, w); b = S.run(part, p, w)
                lim = cut - 2 * 86400
                ta = a["time"]; tb = b["time"]
                ma = ta[a["exit_i"]] < lim; mb = tb[b["exit_i"]] < lim
                # the truncated run force-closes its last open trade at the cut; that trade exits after `lim`
                same = (ma.sum() == mb.sum() and np.array_equal(ta[a["entry_i"]][ma], tb[b["entry_i"]][mb]) and np.array_equal(ta[a["exit_i"]][ma], tb[b["exit_i"]][mb])
                        and np.allclose(a["pnl"][ma], b["pnl"][mb], rtol=0, atol=1e-9) and np.array_equal(a["side"][ma], b["side"][mb]))
                total += 1
                if not same:
                    bad += 1; print("MISMATCH", symbol, tf, style[3], d, rep, int(ma.sum()), int(mb.sum()))
    print(symbol, tf, "checked", flush=True)
print("configs", total, "mismatches", bad)
