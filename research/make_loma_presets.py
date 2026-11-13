#!/usr/bin/env python3
"""
Write the .set presets of XAUUSD_Loma_TrendPullback.mq5 from the calibrated setups in
research/results/hump_refined.csv (run from the repository root). Every preset lists every
input of the EA; values not calibrated keep the EA default. Statistics in the header are
recomputed with research/hump_engine.py.
"""
import os, re, sys
import numpy as np, pandas as pd
sys.path.insert(0, "research")
import hump_engine as H, hump_search as X

EA = "XAUUSD_Loma_TrendPullback.mq5"
TF = {"M1": 1, "M2": 2, "M3": 3, "M5": 5, "H1": 16385, "H4": 16388}
ENUMS = {"PERIOD_M1": 1, "PERIOD_M2": 2, "PERIOD_M3": 3, "PERIOD_M5": 5, "PERIOD_H1": 16385, "PERIOD_H4": 16388,
         "DIR_BOTH": 0, "DIR_SELL_ONLY": 1, "DIR_BUY_ONLY": 2, "TP_PREV_HUMP": 0, "TP_FIXED_RR": 1}
SESS = {"all": None, "ldn_ny_07-20": ("07:00", "20:00"), "ny_12-1630": ("12:00", "16:30"),
        "ny_12-20": ("12:00", "20:00"), "london_07-12": ("07:00", "12:00")}
# (file name, row in hump_refined.csv, magic, description)
PICKS = [("Loma_Gold_M5_Buy_H1", 0, 26113011, "Gold M5 buys, H1 trend filter, all day"),
         ("Loma_Gold_M5_Buy_H4", 6, 26113012, "Gold M5 buys, H4 trend filter, all day"),
         ("Loma_Gold_M2_Sell_London_H1", 2, 26113021, "Gold M2 sells, H1 trend filter, 07:00-12:00 server time"),
         ("Loma_Gold_M3_Sell_H4", 8, 26113022, "Gold M3 sells, H4 trend filter, 07:00-20:00 server time"),
         ("Loma_Gold_M2_Sell_NY_H1", 12, 26113023, "Gold M2 sells, H1 trend filter, 12:00-20:00 server time")]


def defaults():
    out = []
    for _t, name, val in re.findall(r"^input\s+([\w]+)\s+(\w+)\s*=\s*([^;]+);", open(EA).read(), re.M):
        v = val.strip()
        if v.startswith('"'):
            out.append((name, v.strip('"'))); continue
        if v in ENUMS: v = str(ENUMS[v])
        elif re.fullmatch(r"[A-Z_][A-Z0-9_]*", v): raise SystemExit(f"unmapped enum {v} for {name}")
        out.append((name, v))
    return out


def pf(r):
    w = r[r > 0].sum(); l = -r[r < 0].sum()
    return w / l if l > 0 else float("inf")


def main():
    L = pd.read_csv("research/results/hump_refined.csv")
    mk = H.Market()
    base = defaults()
    names = {n for n, _ in base}
    os.makedirs("presets", exist_ok=True)
    for fname, row, magic, desc in PICKS:
        p = {k: X.cast(L.iloc[row][k], X.SPACE[k]) for k in X.SPACE}
        df = mk.run(p); t = df.entry_time.values; r = df.r.values
        m25 = t < np.datetime64("2026-01-01")
        s = H.stats(r)
        o = dict(MagicNumber=magic, TradeComment=fname.replace("Loma_Gold_", "LOMA_"),
                 TradeDirection={0: 0, -1: 1, 1: 2}[p["sides"]], TriggerTimeframe=TF[p["tf"]],
                 BigHumpHistory=p["hist"], BigHumpMultiplier=p["big_mult"], BigHumpMinBars=p["big_min_bars"],
                 RequireStochLevel="true" if p["stoch_req"] else "false", TrendBreakRatio=p["break_ratio"],
                 MaxSignalsPerBigHump=p["max_signals"], TrendMaxBars=p["trend_max_bars"],
                 PullbackMinBars=p["pb_min_bars"], PullbackMaxRatio=p["pb_max_ratio"],
                 SL_Buffer_Points=int(round(p["buf"] * 100)), TP_Mode=p["tp_mode"], TP_Anticipation=p["anticip"],
                 TP_RR=p["tp_rr"], MinRewardRisk=p["min_rr"], MinSL_Points=int(round(p["min_risk"] * 100)),
                 UseHTFFilter="false" if p["htf"] == "none" else "true",
                 HTF_Timeframe=TF.get(p["htf"], 16388), RiskPercent=0.5, MaxSpread_Points=60,
                 TrailStartR=p["trail_start"], TrailDistanceR=p["trail_dist"],
                 UseTradingHours="false" if SESS[p["session"]] is None else "true")
        if SESS[p["session"]]:
            o["TradingHoursStart"], o["TradingHoursEnd"] = SESS[p["session"]]
        missing = set(o) - names
        if missing: raise SystemExit(f"preset keys not in the EA: {missing}")
        head = [f"; XAUUSD_Loma_TrendPullback v1.30 - {desc}",
                "; Loma (MACD hump) method: big hump = trend, small pullback hump, entry on the first bar back across zero.",
                f"; Backtest (FTMO XAUUSD M1 path, Jan 2025-May 2026, risk-% sizing): {s['n']} trades, PF {s['pf']:.2f}, "
                f"net {s['net']:+.0f}R, max drawdown {s['dd']:.1f}R; 2025 PF {pf(r[m25]):.2f} ({int(m25.sum())}), "
                f"2026 (out of sample) PF {pf(r[~m25]):.2f} ({int((~m25).sum())} trades).",
                "; Settings were chosen with 2025 data only, but this setup is one of five kept after seeing 2026: expect less live.",
                "; Trailing in R multiples cannot be fully judged on one-minute bars: confirm with real ticks in the MT5 tester.",
                "; Session hours are BROKER SERVER TIME, calibrated on FTMO data (GMT+2 winter / GMT+3 summer).",
                "; UseNewsFilter=true was NOT part of the backtest; set it to false to match the backtest exactly."]
        with open(f"presets/{fname}.set", "w") as f:
            f.write("\n".join(head) + "\n")
            for n, v in base:
                f.write(f"{n}={o.get(n, v)}\n")
        print(fname, s["n"], round(s["pf"], 2), "2026", round(pf(r[~m25]), 2))


if __name__ == "__main__":
    main()
