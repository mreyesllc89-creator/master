#!/usr/bin/env python3
"""
Write presets/top10/*.set for XAUUSD_Loma_TrendPullback.mq5 (v1.32): the ten best ALL-ROUND gold setups from
both calibration passes (research/results/hump_pool_ranked.csv, column "allround" = the lowest of: worse
half-year PF of 2025, the same under harsh stress, 2026 PF, 2026 PF under harsh stress), one per
timeframe / direction / session / trend-filter family. Run from the repository root.
All the data was used to choose them: there is no out-of-sample test left for this list.
"""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, "research")
os.environ["HUMP_SPACE"] = "2"
import hump_engine as H, hump_search as X
import make_loma_presets as M

SIDE = {0: "Both", -1: "Sell", 1: "Buy"}
SESS_NAME = {"all": "AllDay", "ldn_ny_07-20": "0700-2000", "ny_12-1630": "1200-1630", "ny_12-20": "1200-2000",
             "london_07-12": "0700-1200"}
TF = dict(M.TF, M10=10, M15=15, M30=30, D1=16408)
STRESS = dict(trail_worst=1, delay=1, slip=0.10, comm=0.07, max_spread=5.0)
OVERRIDE = {("M5", 1, "all", "H1"): dict(buf=0.6, tp_rr=6.0)}      # the shipped M5 Buy H1 exits (exit-unit sweep)


def hhmm(m): return f"{int(m) // 60:02d}:{int(m) % 60:02d}"


def main():
    d = pd.read_csv("research/results/hump_pool_ranked.csv").sort_values("allround", ascending=False)
    top = d.drop_duplicates("fam").head(10)
    mk = H.Market()
    base = M.defaults(); names = {n for n, _ in base}
    os.makedirs("presets/top10", exist_ok=True)
    for f in os.listdir("presets/top10"):
        os.remove(os.path.join("presets/top10", f))
    out = []
    for rank, (_, r) in enumerate(top.iterrows(), 1):
        p = {k: X.cast(r[k], X.SPACE[k]) for k in X.SPACE}
        p.update(OVERRIDE.get((p["tf"], p["sides"], p["session"], p["htf"]), {}))
        c = X.engine_cfg(dict(p, skip_big_pb=1, weekend_close=1))
        res = {}
        for lab, cfg in (("base", c), ("stress", dict(c, **STRESS))):
            df = mk.run(cfg); t = df.entry_time.values; x = df.r.values
            m26 = t >= np.datetime64("2026-01-01"); h1 = t < np.datetime64("2025-07-01"); s = H.stats(x)
            res[lab] = dict(n=s["n"], pf=s["pf"], net=s["net"], dd=s["dd"], w25=min(M.pf(x[h1]), M.pf(x[~m26 & ~h1])),
                            pf26=M.pf(x[m26]), n26=int(m26.sum()))
        b, st = res["base"], res["stress"]
        f_, s_ = p["macd"].split("-"); lo, hi = p["stoch_lv"].split("-")
        fname = (f"Loma_Top{rank:02d}_Gold_{p['tf']}_{SIDE[p['sides']]}_{SESS_NAME[p['session']]}_"
                 f"{p['htf'] if p['htf'] != 'none' else 'NoFilter'}")
        o = dict(MagicNumber=26113200 + rank, TradeComment=f"LOMA_T{rank:02d}",
                 TradeDirection={0: 0, -1: 1, 1: 2}[p["sides"]], TriggerTimeframe=TF[p["tf"]],
                 MACD_Fast=int(f_), MACD_Slow=int(s_), Stoch_K=p["stoch_k"], StochLow=float(lo), StochHigh=float(hi),
                 BigHumpHistory=p["hist"], BigHumpMultiplier=p["big_mult"], BigHumpMinBars=p["big_min_bars"],
                 RequireStochLevel="true" if p["stoch_req"] else "false", TrendBreakRatio=p["break_ratio"],
                 MaxSignalsPerBigHump=p["max_signals"], TrendMaxBars=p["trend_max_bars"],
                 PullbackMinBars=p["pb_min_bars"], PullbackMaxRatio=p["pb_max_ratio"],
                 SL_Buffer_Points=int(round(p["buf"] * 100)), TP_Mode=p["tp_mode"], TP_Anticipation=p["anticip"],
                 TP_RR=p["tp_rr"], MinRewardRisk=p["min_rr"], MinSL_Points=int(round(p["min_risk"] * 100)),
                 UseHTFFilter="false" if p["htf"] == "none" else "true", HTF_Timeframe=TF.get(p["htf"], 16388),
                 HTF_EMA_Period=p["htf_ema"], RiskPercent=0.5, MaxSpread_Points=60,
                 TrailStartR=p["trail_start"], TrailDistanceR=p["trail_dist"],
                 UseTradingHours="false" if M.SESS[p["session"]] is None else "true",
                 SkipBigPullback="true", CloseBeforeWeekend="true", WeekendCloseTime="23:00",
                 MaxHoldMinutes=int(p["max_hold"]), CloseAtEndOfDay="true" if p["eod"] >= 0 else "false",
                 EndOfDayTime=hhmm(p["eod"]) if p["eod"] >= 0 else "22:00")
        if M.SESS[p["session"]]:
            o["TradingHoursStart"], o["TradingHoursEnd"] = M.SESS[p["session"]]
        assert not (set(o) - names), set(o) - names
        head = [f"; XAUUSD_Loma_TrendPullback v1.32 - ALL-ROUND TOP 10, rank {rank}: gold {p['tf']} {SIDE[p['sides']].lower()}, "
                f"session {SESS_NAME[p['session']]} server time, trend filter {p['htf']}",
                f"; Backtest Jan 2025-May 2026 (FTMO XAUUSD M1 path, risk-% sizing): {b['n']} trades, PF {b['pf']:.2f}, net {b['net']:+.0f}R, "
                f"max drawdown {b['dd']:.1f}R. 2025 worse half-year PF {b['w25']:.2f}; 2026 PF {b['pf26']:.2f} ({b['n26']} trades).",
                f"; Harsh stress (1 min late, pessimistic trailing, 0.10 slippage, commission): PF {st['pf']:.2f}; 2025 worse half {st['w25']:.2f}; 2026 PF {st['pf26']:.2f}.",
                "; Chosen with ALL the data (2025 and 2026): there is no unseen test behind these numbers. Expect roughly PF 1.1-1.4 live.",
                "; UNPROVEN: Strategy Tester (real ticks) and demo only. Session, weekend and end-of-day times are BROKER SERVER TIME (FTMO clock).",
                "; UseNewsFilter was not in the backtest."]
        with open(f"presets/top10/{fname}.set", "w") as f:
            f.write("\n".join(head) + "\n")
            for n, v in base:
                f.write(f"{n}={o.get(n, v)}\n")
        out.append(dict(rank=rank, file=fname, timeframe=p["tf"], direction=SIDE[p["sides"]], session=SESS_NAME[p["session"]],
                        trend_filter=f"{p['htf']} EMA{p['htf_ema']}" if p["htf"] != "none" else "none", macd=p["macd"], stoch_k=p["stoch_k"],
                        max_hold_min=int(p["max_hold"]), eod_close=hhmm(p["eod"]) if p["eod"] >= 0 else "off", target=f"{p['tp_rr']}R" if p["tp_mode"] else "prev hump",
                        trailing=f"{p['trail_start']}/{p['trail_dist']}R" if p["trail_start"] > 0 else "off",
                        trades=b["n"], pf=round(b["pf"], 2), dd=round(b["dd"], 1), worse_half_2025=round(b["w25"], 2), pf_2026=round(b["pf26"], 2),
                        trades_2026=b["n26"], stress_pf=round(st["pf"], 2), stress_2025=round(st["w25"], 2), stress_2026=round(st["pf26"], 2)))
    s = pd.DataFrame(out); s.to_csv("presets/top10/TOP10_SUMMARY.csv", index=False)
    pd.set_option("display.width", 300); print(s.drop(columns=["file"]).to_string(index=False))


if __name__ == "__main__":
    main()
