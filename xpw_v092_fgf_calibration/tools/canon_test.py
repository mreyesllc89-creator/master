"""Soundness of canonicalize(): resetting 'inert' inputs must never change a single trade.
Runs each raw (un-canonicalized) parameter set and its canonical form and compares the trade lists."""
import random, sys
import numpy as np
import xpw_run as R, xpw_search2 as S
reps = int(sys.argv[1]) if len(sys.argv) > 1 else 6
total = 0; bad = 0; changed = 0
for symbol, tf in (("XAUUSD", 240), ("BTCUSD", 240), ("XAUUSD", 60)):
    w = S.windows(symbol, tf); mk = R.Market(symbol, start=w["start"]); rng = random.Random(11)
    for si, style in enumerate(S.STYLES):
        for d, _ in S.DIRS:
            for rep in range(reps):
                raw = S.sample_raw(rng, symbol, tf, style, d, rep % 2 == 0)
                if rep >= reps // 2:
                    # start from a canonical set and poke raw values back in, as a mutation would before canonicalize
                    raw = S.canonicalize(dict(raw))
                    for _ in range(rng.choice([1, 2, 4])):
                        k = rng.choice(S.MUT_KEYS)
                        if k in S.SPECIAL: S._set_special(rng, raw, k, tf)
                        elif k == "fgfOn": raw[k] = not raw[k]
                        elif k in S.GOLD_PTS: raw[k] = float(rng.choice(S.GOLD_PTS[k]) * (1 if symbol == "XAUUSD" else 50))
                        else: raw[k] = rng.choice(S.SPACE[k])
                can = S.canonicalize(dict(raw))
                if int(raw["SlowLen"]) <= int(raw["FastLen"]): raw["SlowLen"] = can["SlowLen"]   # the one deliberate, behaviour-changing repair
                total += 1
                if S.key_of(can) != S.key_of(raw): changed += 1
                if S.trade_sig(S.run(mk, raw, w)) != S.trade_sig(S.run(mk, can, w)):
                    bad += 1
                    diff = {k: (raw[k], can[k]) for k in raw if raw[k] != can[k]}
                    print("MISMATCH", symbol, tf, style[3], d, diff, flush=True)
    print(symbol, tf, "done", flush=True)
print("cases", total, "canonicalization changed something in", changed, "mismatches", bad)
