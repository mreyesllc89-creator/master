#!/usr/bin/env python3
"""
Write presets/btc/*.set for XAUUSD_Loma_TrendPullback.mq5 (v1.32) on BTCUSD: the setups of
research/results/hump_btc_pool_ranked.csv that stay at PF >= 1.3 on all six measures (whole period, worse
half-year of 2025, 2026, and the same three under harsh stress), one per family. Run from the repository
root with HUMP_SYMBOL=BTCUSD HUMP_BTC_DATA=<dir> (and HUMP_BTC_SPREAD for another spread).
Chosen with all the data: no out-of-sample test is left. BTC distances are in dollars x 100 points.
"""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, "research")
os.environ["HUMP_SPACE"] = "2"
import hump_engine as H, hump_search as X
import make_loma_presets as M
import make_loma_top10 as T

assert H.SYMBOL == "BTCUSD"
STRESS = dict(trail_worst=1, delay=1, slip=3.0, comm=2.0, max_spread=1e9)


def measure(mk, c):
    df = mk.run(c); t = df.entry_time.values; x = df.r.values
    m26 = t >= np.datetime64("2026-01-01"); h1 = t < np.datetime64("2025-07-01"); s = H.stats(x)
    return dict(n=s["n"], pf=s["pf"], net=s["net"], dd=s["dd"], w25=min(M.pf(x[h1]), M.pf(x[~m26 & ~h1])),
                pf26=M.pf(x[m26]), n26=int(m26.sum()))


def main():
    d = pd.read_csv("research/results/hump_btc_pool_ranked.csv").sort_values("allround", ascending=False).drop_duplicates("fam")
    for c in ["pf", "w25", "pf26", "st_pf", "st_w25", "st_pf26"]:
        d = d[d[c] >= 1.3]
    mk = H.Market()
    base = M.defaults(); names = {n for n, _ in base}
    os.makedirs("presets/btc", exist_ok=True)
    for f in os.listdir("presets/btc"):
        os.remove(os.path.join("presets/btc", f))
    out = []
    for rank, (_, r) in enumerate(d.iterrows(), 1):
        p = {k: X.cast(r[k], X.SPACE[k]) for k in X.SPACE if k in r.index}
        c = X.engine_cfg(dict(X.BASE, **p))
        b, st = measure(mk, c), measure(mk, dict(c, **STRESS))
        f_, s_ = p["macd"].split("-"); lo, hi = p["stoch_lv"].split("-")
        fname = (f"Loma_BTC{rank:02d}_{p['tf']}_{T.SIDE[p['sides']]}_{T.SESS_NAME[p['session']]}_"
                 f"{p['htf'] if p['htf'] != 'none' else 'NoFilter'}")
        o = dict(MagicNumber=26113300 + rank, TradeComment=f"LOMA_BTC{rank:02d}",
                 TradeDirection={0: 0, -1: 1, 1: 2}[p["sides"]], TriggerTimeframe=T.TF[p["tf"]],
                 MACD_Fast=int(f_), MACD_Slow=int(s_), Stoch_K=p["stoch_k"], StochLow=float(lo), StochHigh=float(hi),
                 BigHumpHistory=p["hist"], BigHumpMultiplier=p["big_mult"], BigHumpMinBars=p["big_min_bars"],
                 RequireStochLevel="true" if p["stoch_req"] else "false", TrendBreakRatio=p["break_ratio"],
                 MaxSignalsPerBigHump=p["max_signals"], TrendMaxBars=p["trend_max_bars"],
                 PullbackMinBars=p["pb_min_bars"], PullbackMaxRatio=p["pb_max_ratio"],
                 SL_Buffer_Points=int(round(p["buf"] * 100)), TP_Mode=p["tp_mode"], TP_Anticipation=p["anticip"],
                 TP_RR=p["tp_rr"], MinRewardRisk=p["min_rr"], MinSL_Points=int(round(p["min_risk"] * 100)),
                 UseHTFFilter="false" if p["htf"] == "none" else "true", HTF_Timeframe=T.TF.get(p["htf"], 16388),
                 HTF_EMA_Period=p["htf_ema"], RiskPercent=0.5, MaxSpread_Points=3000,
                 TrailStartR=p["trail_start"], TrailDistanceR=p["trail_dist"],
                 UseTradingHours="false" if M.SESS[p["session"]] is None else "true",
                 SkipBigPullback="true", CloseBeforeWeekend="false",
                 MaxHoldMinutes=int(p["max_hold"]), CloseAtEndOfDay="true" if p["eod"] >= 0 else "false",
                 EndOfDayTime=T.hhmm(p["eod"]) if p["eod"] >= 0 else "22:00")
        if M.SESS[p["session"]]:
            o["TradingHoursStart"], o["TradingHoursEnd"] = M.SESS[p["session"]]
        assert not (set(o) - names), set(o) - names
        sp = H.BTC_SPREAD
        head = [f"; XAUUSD_Loma_TrendPullback v1.32 on BTCUSD - rank {rank}: {p['tf']} {T.SIDE[p['sides']].lower()}, session "
                f"{T.SESS_NAME[p['session']]} server time, trend filter {p['htf']}. DO NOT LOAD ON GOLD.",
                f"; Backtest Jan 2025-May 2026 (Binance BTCUSDT M1, assumed spread {sp:.0f} USD, risk-% sizing): {b['n']} trades, PF {b['pf']:.2f}, "
                f"net {b['net']:+.0f}R, max drawdown {b['dd']:.1f}R. 2025 worse half-year PF {b['w25']:.2f}; 2026 PF {b['pf26']:.2f} ({b['n26']} trades).",
                f"; Harsh stress (1 min late, pessimistic trailing, 3 USD slippage, 2 USD commission): PF {st['pf']:.2f}; 2025 worse half {st['w25']:.2f}; 2026 PF {st['pf26']:.2f}.",
                "; Chosen with ALL the data: no unseen test. Across the whole BTC search a good 2025 did not predict 2026 (median 2026 PF about 1.0).",
                "; UNPROVEN: Strategy Tester (real ticks) and demo only. Points are 0.01 USD: 2000 points = 20 USD. MaxSpread_Points=3000 allows a 30 USD spread.",
                "; Times are BROKER SERVER TIME (New York + 7h). The weekend close is off: BTC trades through the weekend at most brokers."]
        with open(f"presets/btc/{fname}.set", "w") as f:
            f.write("\n".join(head) + "\n")
            for n, v in base:
                f.write(f"{n}={o.get(n, v)}\n")
        out.append(dict(rank=rank, file=fname, trades=b["n"], pf=round(b["pf"], 2), dd=round(b["dd"], 1),
                        worse_half_2025=round(b["w25"], 2), pf_2026=round(b["pf26"], 2), trades_2026=b["n26"],
                        stress_pf=round(st["pf"], 2), stress_2025=round(st["w25"], 2), stress_2026=round(st["pf26"], 2)))
    s = pd.DataFrame(out)
    if os.environ.get("HUMP_BTC_SPREAD", "10") == "10":
        s.to_csv("presets/btc/BTC_PRESETS_SUMMARY.csv", index=False)
    pd.set_option("display.width", 250); print(f"spread {H.BTC_SPREAD}"); print(s.to_string(index=False))


if __name__ == "__main__":
    main()
