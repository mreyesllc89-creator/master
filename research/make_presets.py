#!/usr/bin/env python3
"""
Generate every presets/*.set file from the EA's full input list, so each preset
is complete: loading one preset never leaves values behind from another.

Usage: python3 research/make_presets.py   (run from the repository root)
"""
import json
import os
import re

EA = "XAUUSD_M1_LiquidityZeroCross_Bearish.mq5"
ENUMS = {"PERIOD_CURRENT": 0, "PERIOD_M1": 1, "PERIOD_M2": 2, "PERIOD_M3": 3, "PERIOD_M5": 5,
         "PERIOD_M15": 15, "PERIOD_M30": 30, "PERIOD_H1": 16385, "PERIOD_H2": 16386,
         "PERIOD_H4": 16388, "TRAIL_SERVER": 0, "TRAIL_HYBRID": 1}
FGF_KEYS = {"UseFGF_Filter", "FGF_IndicatorName", "FGF_CalcTimeframe", "FGF_Shift", "FGF_BlockIfUnavailable"}


def defaults():
    src = open(EA).read()
    out = {}
    for _typ, name, val in re.findall(r"^input\s+(\w+)\s+(\w+)\s*=\s*([^;]+);", src, re.M):
        v = val.strip().strip('"')
        out[name] = str(ENUMS.get(v, v))
    return out


def write(path, header, overrides, fgf=False):
    vals = defaults()
    for k, v in overrides.items():
        assert k in vals, f"unknown input {k}"
        vals[k] = str(v).lower() if isinstance(v, bool) else str(v)
    lines = [f"; {h}" for h in header]
    lines += [f"{k}={v}" for k, v in vals.items() if fgf or k not in FGF_KEYS]
    open(path, "w").write("\n".join(lines) + "\n")


SERVER_NOTE = ("Session hours are BROKER SERVER TIME (TradingHoursAreGMT=false). They were calibrated "
               "on FTMO data whose clock is GMT+2 winter / GMT+3 summer (New York close).")
UNCAL_NOTE = ("Not calibrated: spec-based settings. Session hours are GMT. MaxSpread 60 because typical "
              "XAUUSD spreads are 40-55 points; a cap below that never trades.")


def fgf_line():
    import pandas as pd
    g = pd.read_csv("research/results/fgf_stage1_grid.csv.gz")
    dl = dict(filter_tf="H1", parent="H1", level_mode=0, zones="align2", any_combo=False, burst_atr=0.5,
              hold_bars=0, band_atr=0.25, window="next", against=True, check=0)
    for k, v in dl.items():
        g = g[g[k] == v]
    r = g[g.base == "M3/H1 chosen"].iloc[0]
    b = pd.read_csv("research/results/fgf_stage1_baselines.csv").set_index("base").loc["M3/H1 chosen"]
    return (f"FlashGold defaults on this setup (in-sample): {r.all_trades:.0f} trades, PF {r.all_pf:.2f}, "
            f"net {r.all_net_r:+.1f}R vs {b.all_trades:.0f} trades, PF {b.all_pf:.2f}, net {b.all_net_r:+.1f}R "
            "without the filter: higher PF, about a third of the trades, less total profit.")


TFM = {"M1": 1, "M2": 2, "M3": 3, "M5": 5}


def main():
    m = json.load(open("research/results/m3_h1_verify.json"))
    ch = next(v for v in m["variants"] if v["label"] == "chosen")
    wf = json.load(open("research/results/walkforward.json")) if os.path.exists("research/results/walkforward.json") else {}
    head = (f"In-sample backtest (all 17 months used for selection): {ch['all_trades']:.0f} trades, "
            f"PF {ch['all_pf']:.2f}; per period {ch['2025H1_pf']:.2f} / {ch['2025H2_pf']:.2f} / "
            f"{ch['2026_pf']:.2f}. Same-bar trailing worst case PF {m.get('worst_pf', float('nan')):.2f}.")
    wf_note = wf.get("note", "See the calibration report for the walk-forward (hold-out) result.")
    if "chosen" in wf:
        c = wf["chosen"]
        wf_note += (f" This exact setup ranked {c['rank_on_2025_only']} of {c['of']} on 2025 alone and made "
                    f"PF {c['pf_2026']:.2f} on {c['trades_2026']} trades in 2026: the M2/M3-trigger + H1-bias "
                    "family held up out of sample, the exact parameter values are not proven.")
    m3 = dict(MagicNumber=20261110, TradeComment="XLZC_M3H1", RiskPercent=0.5, MaxSpread_Points=60,
              MaxSlippage_Points=30, MaxEntryDelaySeconds=30, HTF_Timeframe=16385, TriggerTimeframe=3,
              LiquidityLookbackBars=40, SwingStrength=2, SL_Buffer_Points=208, MinRewardRisk=1.5,
              TP_LookbackBars=120, TP_FallbackRR=0, MinSL_Points=87, MaxSL_Points=1732,
              EnableTrailing=True, TrailingMode=0, TrailingStart_Points=260, TrailingDistance_Points=173,
              TrailingStep_Points=10, UseTradingHours=True, TradingHoursAreGMT=False,
              TradingHoursStart="12:00", TradingHoursEnd="16:30", UseNewsFilter=True)
    news = ("UseNewsFilter=true was NOT part of the backtest (no calendar history); live trade count "
            "and results will differ. Set it to false to match the backtest exactly.")
    write("presets/XLZC_Bearish_M3_H1_NY.set",
          ["XAUUSD_M1_LiquidityZeroCross_Bearish v1.10 - M3 trigger / H1 bias / 12:00-16:30 server time",
           head, wf_note, SERVER_NOTE, news,
           "Points are 2-digit gold units (AutoScalePoints handles 3-digit feeds). Signals use M3 on any chart."], m3)
    write("presets/XLZC_Bearish_M3_H1_NY_FGF.set",
          ["XAUUSD_M1_LiquidityZeroCross_Bearish_FGF v1.10 - same as XLZC_Bearish_M3_H1_NY plus the "
           "FlashGold Direction Filter v1.2 (indicator default inputs).",
           "Base-EA figures without the filter: " + head, wf_note, SERVER_NOTE, news,
           fgf_line()],
          dict(m3, MagicNumber=20261111, TradeComment="XLZC_M3H1_FGF", UseFGF_Filter=True), fgf=True)
    v2 = json.load(open("research/results/m2_h1_verify.json"))
    c2, w2, f2 = v2["chosen"], v2["trailing same-bar: worst"], v2["with FlashGold defaults"]
    write("presets/XLZC_Bearish_M2_H1_NY.set",
          ["XAUUSD_M1_LiquidityZeroCross_Bearish v1.10 - M2 trigger / H1 bias / 12:00-16:30 server time",
           "Chosen with 2025 data ONLY (median of the setup and its neighbouring settings, >=30 trades per half-year); "
           "2026 was not used, so the 2026 figure is out of sample.",
           f"Backtest: {c2['all_trades']:.0f} trades, PF {c2['all_pf']:.2f}, net {c2['all_net_r']:+.1f}R, max DD "
           f"{c2['all_maxdd_r']:.1f}R; PF {c2['2025H1_pf']:.2f} / {c2['2025H2_pf']:.2f} (2025, in-sample) / "
           f"{c2['2026_pf']:.2f} on {c2['2026_trades']:.0f} trades (2026, out of sample).",
           f"Depends on trailing: if every same-bar trailing touch counts as a stop, PF is {w2['all_pf']:.2f}. "
           f"With the FlashGold filter PF falls to {f2['all_pf']:.2f} ({f2['all_trades']:.0f} trades): not recommended here.",
           "When no liquidity pool pays MinRewardRisk, TP is a fixed 1.5R (TP_FallbackRR=1.5).",
           SERVER_NOTE, news,
           "Points are 2-digit gold units scaled by sqrt(2) for M2 (AutoScalePoints handles 3-digit feeds). Signals use M2 on any chart."],
          dict(MagicNumber=20261112, TradeComment="XLZC_M2H1", RiskPercent=0.5, MaxSpread_Points=60,
               MaxSlippage_Points=30, MaxEntryDelaySeconds=30, HTF_Timeframe=16385, TriggerTimeframe=2,
               LiquidityLookbackBars=15, SwingStrength=4, SL_Buffer_Points=57, MinRewardRisk=1.5,
               TP_LookbackBars=120, TP_FallbackRR=1.5, MinSL_Points=71, MaxSL_Points=1414,
               EnableTrailing=True, TrailingMode=0, TrailingStart_Points=212, TrailingDistance_Points=141,
               TrailingStep_Points=10, UseTradingHours=True, TradingHoursAreGMT=False,
               TradingHoursStart="12:00", TradingHoursEnd="16:30", UseNewsFilter=True))
    #---------------------------------------------------------------- BTCUSD
    bt = json.load(open("research/results/btc_select_verify_spread5.json"))
    bt20 = json.load(open("research/results/btc_select_verify.json"))
    tfnum = {"M2": 2, "M3": 3, "M5": 5, "M15": 15, "M30": 30, "H1": 16385}
    for i, pr in enumerate(bt["presets"]):
        cfg, vf = pr["cfg"], pr["verify"]
        c, w = vf["chosen"], vf["trailing same-bar: worst"]
        trig, htf = cfg["tf"].split("/")
        k = 32.6 * TFM[trig] ** 0.5               # gold points x instrument scale x sqrt(trigger minutes)
        sess = {"ny_12-1630": ("12:00", "16:30"), "ldn_ny_07-20": ("07:00", "20:00")}[cfg["session"]]
        name = f"presets/XLZC_Bearish_BTCUSD_{trig}_{htf}.set"
        write(name,
              [f"XAUUSD_M1_LiquidityZeroCross_Bearish v1.10 - BTCUSD {trig} trigger / {htf} bias / {sess[0]}-{sess[1]} server time",
               "LOW-COST BROKERS ONLY. Calibrated assuming a 5 USD BTCUSD spread; MaxSpread_Points=1000 (10 USD) "
               "blocks entries when the spread is wider. Commission counts as cost too.",
               "Chosen with 2025 data ONLY (median of the setup and its neighbouring settings, >=30 trades per half-year).",
               f"Backtest (Binance BTCUSDT M1, Jan 2025-May 2026, 5 USD spread): {c['all_trades']:.0f} trades, PF {c['all_pf']:.2f}, "
               f"net {c['all_net_r']:+.1f}R, max DD {c['all_maxdd_r']:.1f}R; PF {c['2025H1_pf']:.2f} / {c['2025H2_pf']:.2f} (2025) / "
               f"{c['2026_pf']:.2f} on {c['2026_trades']:.0f} trades (2026, out of sample).",
               f"Weak spots: worst-case trailing fills PF {w['all_pf']:.2f}. At a 20 USD spread no BTC setup held up "
               "out of sample, so do not raise MaxSpread_Points to make it trade.",
               "Points are 0.01 USD steps (AutoScalePoints rescales other BTC quote digits). Short-only EA: no trades "
               "while the trend filter is not bearish.",
               "Session hours are BROKER SERVER TIME (TradingHoursAreGMT=false): the Binance UTC data was converted to "
               "a GMT+2 winter / GMT+3 summer (New York close) server clock. Shift the hours if your broker differs.", news],
              dict(MagicNumber=20261120 + i, TradeComment=f"XLZC_BTC_{trig}{htf}", RiskPercent=0.5,
                   MaxSpread_Points=1000, MaxSlippage_Points=1000, MaxEntryDelaySeconds=30,
                   HTF_Timeframe=tfnum[htf], TriggerTimeframe=tfnum[trig],
                   LiquidityLookbackBars=cfg["N"], SwingStrength=cfg["S"],
                   SL_Buffer_Points=round(cfg["buffer"] * k), MinRewardRisk=cfg["min_rr"],
                   TP_LookbackBars=cfg["NT"], TP_FallbackRR=cfg["fb"],
                   MinSL_Points=round(50 * k), MaxSL_Points=round(1000 * k),
                   StochHardBlock=(cfg["stoch"] == "hard"),
                   EnableTrailing=bool(cfg["trail"]), TrailingMode=0,
                   TrailingStart_Points=round(150 * k), TrailingDistance_Points=round(100 * k),
                   TrailingStep_Points=100, UseTradingHours=True, TradingHoursAreGMT=False,
                   TradingHoursStart=sess[0], TradingHoursEnd=sess[1], UseNewsFilter=True))
    write("presets/XLZC_Bearish_Calibrated_M1_M15.set",
          ["XAUUSD_M1_LiquidityZeroCross_Bearish v1.10 - first-pass calibration (M1 trigger / M15 bias)",
           "In-sample first pass: 51 trades, PF ~1.7 (swing 3, buffer 80, trailing). Fragile: lookback 40 drops PF to ~1.05.",
           SERVER_NOTE],
          dict(MagicNumber=20261109, TradeComment="XLZC_Bear_Cal", RiskPercent=0.5, MaxSpread_Points=60,
               HTF_Timeframe=15, LiquidityLookbackBars=25, SwingStrength=3, SL_Buffer_Points=80,
               EnableTrailing=True, TrailingStart_Points=150, TrailingDistance_Points=100,
               TrailingStep_Points=20, TradingHoursAreGMT=False, TradingHoursStart="12:00",
               TradingHoursEnd="16:30"))
    write("presets/XLZC_Bearish_Conservative.set",
          ["XAUUSD_M1_LiquidityZeroCross_Bearish v1.10 - CONSERVATIVE (spec defaults, M1 / M15)", UNCAL_NOTE],
          dict(MagicNumber=20261107, TradeComment="XLZC_Bear_C", RiskPercent=0.5, MaxSpread_Points=60,
               MaxSlippage_Points=15, StochHardBlock=True, SwingStrength=3, SL_Buffer_Points=50,
               MinRewardRisk=1.5, MinSL_Points=60, MaxSL_Points=800, EnableTrailing=True,
               TrailingStart_Points=200, TrailingDistance_Points=150, TrailingStep_Points=20))
    write("presets/XLZC_Bearish_Aggressive.set",
          ["XAUUSD_M1_LiquidityZeroCross_Bearish v1.10 - AGGRESSIVE (spec defaults, M1 / M5)", UNCAL_NOTE],
          dict(MagicNumber=20261108, TradeComment="XLZC_Bear_A", RiskPercent=1.0, MaxSpread_Points=60,
               MaxSlippage_Points=25, HTF_Timeframe=5, LiquidityLookbackBars=30, SL_Buffer_Points=30,
               MinSL_Points=40, MaxSL_Points=1200, EnableTrailing=True, TrailingMode=1,
               TrailingStart_Points=120, TrailingDistance_Points=100, TrailingStep_Points=10,
               EnablePartialClose=True, TradingHoursStart="07:00", TradingHoursEnd="20:00"))
    print("presets written")


if __name__ == "__main__":
    main()
