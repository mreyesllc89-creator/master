#!/usr/bin/env python3
"""
Write presets/top10/*.set: the ten best refined Loma setups ranked by the worse half-year PF of
2025 (v1.31 rules on), for XAUUSD_Loma_TrendPullback.mq5. Run from the repository root.
The rank uses 2025 only; the 2026 result and a harsh-stress PF are printed in each header.
"""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, "research")
import hump_engine as H, hump_search as X
import make_loma_presets as M

SIDE = {0: "Both", -1: "Sell", 1: "Buy"}
SESS_NAME = {"all": "AllDay", "ldn_ny_07-20": "0700-2000", "ny_12-1630": "1200-1630", "ny_12-20": "1200-2000",
             "london_07-12": "0700-1200"}


def main():
    L = pd.read_csv("research/results/hump_refined.csv")
    mk = H.Market()
    rows = []
    for i in range(len(L)):
        p = {k: X.cast(L.iloc[i][k], X.SPACE[k]) for k in X.SPACE}
        q = dict(p, skip_big_pb=1, weekend_close=1)
        df = mk.run(q); t = df.entry_time.values; r = df.r.values
        m26 = t >= np.datetime64("2026-01-01"); h1 = t < np.datetime64("2025-07-01")
        w = mk.run(dict(q, trail_worst=1, delay=1, slip=0.1, comm=0.07, max_spread=5)).r.values
        rows.append(dict(i=i, p=p, n=len(r), pf=M.pf(r), net=float(r.sum()), dd=H.stats(r)["dd"],
                         w25=min(M.pf(r[h1]), M.pf(r[~m26 & ~h1])), pf25=M.pf(r[~m26]), pf26=M.pf(r[m26]),
                         n26=int(m26.sum()), stress=M.pf(w), key=(p["tf"], p["sides"], p["session"], p["htf"], len(r))))
    seen, top = set(), []
    for x in sorted(rows, key=lambda x: -x["w25"]):
        if x["key"] in seen: continue
        seen.add(x["key"]); top.append(x)
        if len(top) == 10: break
    base = M.defaults(); names = {n for n, _ in base}
    os.makedirs("presets/top10", exist_ok=True)
    for f in os.listdir("presets/top10"):
        os.remove(os.path.join("presets/top10", f))
    out = []
    for rank, x in enumerate(top, 1):
        p = x["p"]
        fname = f"Loma_Top{rank:02d}_Gold_{p['tf']}_{SIDE[p['sides']]}_{SESS_NAME[p['session']]}_{p['htf'] if p['htf'] != 'none' else 'NoFilter'}"
        o = dict(MagicNumber=26113100 + rank, TradeComment=f"LOMA_T{rank:02d}",
                 TradeDirection={0: 0, -1: 1, 1: 2}[p["sides"]], TriggerTimeframe=M.TF[p["tf"]],
                 BigHumpHistory=p["hist"], BigHumpMultiplier=p["big_mult"], BigHumpMinBars=p["big_min_bars"],
                 RequireStochLevel="true" if p["stoch_req"] else "false", TrendBreakRatio=p["break_ratio"],
                 MaxSignalsPerBigHump=p["max_signals"], TrendMaxBars=p["trend_max_bars"],
                 PullbackMinBars=p["pb_min_bars"], PullbackMaxRatio=p["pb_max_ratio"],
                 SL_Buffer_Points=int(round(p["buf"] * 100)), TP_Mode=p["tp_mode"], TP_Anticipation=p["anticip"],
                 TP_RR=p["tp_rr"], MinRewardRisk=p["min_rr"], MinSL_Points=int(round(p["min_risk"] * 100)),
                 UseHTFFilter="false" if p["htf"] == "none" else "true", HTF_Timeframe=M.TF.get(p["htf"], 16388),
                 RiskPercent=0.5, MaxSpread_Points=60, TrailStartR=p["trail_start"], TrailDistanceR=p["trail_dist"],
                 UseTradingHours="false" if M.SESS[p["session"]] is None else "true",
                 SkipBigPullback="true", CloseBeforeWeekend="true", WeekendCloseTime="23:00")
        if M.SESS[p["session"]]:
            o["TradingHoursStart"], o["TradingHoursEnd"] = M.SESS[p["session"]]
        assert not (set(o) - names), set(o) - names
        verdict = "held in 2026" if x["pf26"] >= 1.15 else ("about break-even in 2026" if x["pf26"] >= 0.95 else "LOST in 2026")
        head = [f"; XAUUSD_Loma_TrendPullback v1.31 - TOP 10 by 2025, rank {rank}: gold {p['tf']} {SIDE[p['sides']].lower()}, "
                f"session {SESS_NAME[p['session']]} server time, trend filter {p['htf']}",
                f"; Rank uses 2025 only (worse half-year PF {x['w25']:.2f}). Out of sample 2026: PF {x['pf26']:.2f} on {x['n26']} trades -> {verdict}.",
                f"; Backtest Jan 2025-May 2026 (FTMO XAUUSD M1 path, risk-% sizing): {x['n']} trades, PF {x['pf']:.2f}, net {x['net']:+.0f}R, "
                f"max drawdown {x['dd']:.1f}R. Harsh stress (1 min late, pessimistic trailing, slippage, commission): PF {x['stress']:.2f}.",
                "; UNPROVEN: for Strategy Tester (real ticks) and demo only. A high 2025 rank did not predict 2026: read the header line above.",
                "; Session hours are BROKER SERVER TIME (FTMO clock, GMT+2 winter / GMT+3 summer). UseNewsFilter was not in the backtest."]
        with open(f"presets/top10/{fname}.set", "w") as f:
            f.write("\n".join(head) + "\n")
            for n, v in base:
                f.write(f"{n}={o.get(n, v)}\n")
        out.append((rank, fname, x["n"], round(x["pf"], 2), round(x["w25"], 2), round(x["pf26"], 2), x["n26"], round(x["stress"], 2), verdict))
    pd.DataFrame(out, columns=["rank", "file", "trades", "pf", "worse_half_2025", "pf_2026", "trades_2026", "stress_pf", "verdict"]) \
        .to_csv("presets/top10/TOP10_SUMMARY.csv", index=False)
    for o in out: print(*o)


if __name__ == "__main__":
    main()
