#!/usr/bin/env python3
"""
Write EA presets (.set) for the picks of the per-timeframe re-calibration (hump_tf_recal.py) that use the
EA's own trailing stop (run 1, files cand_<TF>.pkl): the setups picked on Jan 2025 - May 15 2026 for the given
timeframes, each with its in-sample and unseen (May 16 - Nov 13 2026) figures in the header.

Usage (repository root):
  [HUMP_SYMBOL=BTCUSD] python3 research/make_recal_presets.py <recal_work_dir> <out_dir> <magic_base> <TF> [<TF> ...]
"""
import json, os, pickle, sys
import numpy as np, pandas as pd

sys.path.insert(0, "research")
import hump_tf_recal as R
import hump_search as X
import make_loma_presets as M
import make_loma_top10 as T

WORK, OUT, MAGIC = sys.argv[1], sys.argv[2], int(sys.argv[3])
TFS = sys.argv[4:]
BTC = R.SYM == "BTCUSD"
SCALE = 100                                     # *_Points inputs are 0.01 USD on gold and on BTC (AutoScalePoints)


def ea_inputs(p, magic, comment):
    f_, s_ = p["macd"].split("-"); lo, hi = p["stoch_lv"].split("-")
    o = dict(MagicNumber=magic, TradeComment=comment, TradeDirection={0: 0, -1: 1, 1: 2}[p["sides"]],
             TriggerTimeframe=T.TF[p["tf"]], MACD_Fast=int(f_), MACD_Slow=int(s_), Stoch_K=p["stoch_k"],
             StochLow=float(lo), StochHigh=float(hi), BigHumpHistory=p["hist"], BigHumpMultiplier=p["big_mult"],
             BigHumpMinBars=p["big_min_bars"], RequireStochLevel="true" if p["stoch_req"] else "false",
             TrendBreakRatio=p["break_ratio"], MaxSignalsPerBigHump=p["max_signals"], TrendMaxBars=p["trend_max_bars"],
             PullbackMinBars=p["pb_min_bars"], PullbackMaxRatio=p["pb_max_ratio"],
             SL_Buffer_Points=int(round(p["buf"] * SCALE)), TP_Mode=p["tp_mode"], TP_Anticipation=p["anticip"],
             TP_RR=p["tp_rr"], MinRewardRisk=p["min_rr"], MinSL_Points=int(round(p["min_risk"] * SCALE)),
             UseHTFFilter="false" if p["htf"] == "none" else "true", HTF_Timeframe=T.TF.get(p["htf"], 16388),
             HTF_EMA_Period=p["htf_ema"], RiskPercent=0.5, TrailStartR=p["trail_start"], TrailDistanceR=p["trail_dist"],
             UseTradingHours="false" if M.SESS[p["session"]] is None else "true", SkipBigPullback="true",
             MaxHoldMinutes=int(p["max_hold"]), CloseAtEndOfDay="true" if p["eod"] >= 0 else "false",
             EndOfDayTime=T.hhmm(p["eod"]) if p["eod"] >= 0 else "22:00")
    if BTC:
        o.update(MaxSpread_Points=3000, MaxSlippage_Points=1000, TrailStep_Points=200, CloseBeforeWeekend="false")
    else:
        o.update(MaxSpread_Points=60, CloseBeforeWeekend="true", WeekendCloseTime="23:00")
    if M.SESS[p["session"]]:
        o["TradingHoursStart"], o["TradingHoursEnd"] = M.SESS[p["session"]]
    return o


def main():
    base = M.defaults(); names = {n for n, _ in base}
    os.makedirs(OUT, exist_ok=True)
    rows = []; k = 0
    sym = "BTC" if BTC else "Gold"
    for tf in TFS:
        d = pickle.load(open(os.path.join(WORK, f"cand_{tf}.pkl"), "rb"))
        P, Bs, Ss = d["params"], d["base"], d["stress"]
        sc = np.array([R.is_score(Bs[i], Ss[i]) for i in range(len(P))])
        elig = np.where(sc > 0)[0]
        order = elig[np.argsort(-sc[elig], kind="stable")]
        picked, fams = [], set()
        for i in order:
            if sc[i] < R.PASS_PF or len(picked) >= R.TOPK:
                break
            fam = (P[i]["sides"], P[i]["session"], P[i]["htf"])
            if fam in fams:
                continue
            fams.add(fam); picked.append(int(i))
        pooled = np.concatenate([R.split(*Bs[i])[2] for i in picked]) if picked else np.zeros(0)
        pooled_s = np.concatenate([R.split(*Ss[i])[2] for i in picked]) if picked else np.zeros(0)
        for rank, i in enumerate(picked, 1):
            k += 1
            p = P[i]
            isr, _, oor = R.split(*Bs[i]); iss, _, oos = R.split(*Ss[i])
            side = T.SIDE[p["sides"]]; sess = T.SESS_NAME[p["session"]]
            filt = p["htf"] if p["htf"] != "none" else "NoFilter"
            fname = f"Loma_{sym}_{tf}_R{rank:02d}_{side}_{sess}_{filt}"
            o = ea_inputs(p, MAGIC + k, f"LOMA_{sym[0]}{tf}_{rank:02d}")
            assert not (set(o) - names), set(o) - names
            trail = "off" if p["trail_start"] <= 0 else f"from {p['trail_start']}R, {p['trail_dist']}R behind"
            head = [f"; XAUUSD_Loma_TrendPullback v{M.EA_VERSION} on {'BTCUSD' if BTC else 'XAUUSD'} - re-calibration pick {rank} of {len(picked)} "
                    f"for {tf}: {side.lower()}, session {sess} server time, trend filter {p['htf']}, trailing {trail}."
                    + (" DO NOT LOAD ON GOLD." if BTC else " DO NOT LOAD ON BTC."),
                    f"; Picked on Jan 2025 - May 15 2026 only (lowest of six profit factors, normal and stressed costs: {sc[i]:.2f}): "
                    f"{len(isr)} trades, PF {R.pf(isr):.2f}, stressed {R.pf(iss):.2f}.",
                    f"; UNSEEN May 16 - Nov 13 2026 (never used to pick it): {len(oor)} trades, PF {R.pf(oor):.2f}, net {oor.sum():+.1f}R; "
                    f"stressed PF {R.pf(oos):.2f}. All {len(picked)} {tf} picks together: {len(pooled)} trades, PF {R.pf(pooled):.2f} "
                    f"(stressed {R.pf(pooled_s):.2f}).",
                    ("; Data: Binance BTCUSDT M1 in broker server time, assumed spread 10 USD. Points are 0.01 USD: 2000 points = 20 USD."
                     if BTC else "; Data: FTMO XAUUSD M1 to May 15 2026, Dukascopy after; FTMO spread table."),
                    "; Times are BROKER SERVER TIME (New York + 7 h: GMT+2 in the US winter, GMT+3 in the US summer). Demo and Strategy Tester first.",
                    "; UseNewsFilter was not in the backtest."]
            with open(os.path.join(OUT, fname + ".set"), "w") as f:
                f.write("\n".join(head) + "\n")
                for n, v in base:
                    f.write(f"{n}={o.get(n, v)}\n")
            rows.append(dict(file=fname, timeframe=tf, rank=rank, direction=side, session=sess, trend_filter=p["htf"],
                             htf_ema=p["htf_ema"], macd=p["macd"], target=f"{p['tp_rr']}R" if p["tp_mode"] == 1 else "previous hump",
                             trailing=trail, max_hold_min=int(p["max_hold"]), eod_close=T.hhmm(p["eod"]) if p["eod"] >= 0 else "off",
                             in_sample_score=round(float(sc[i]), 2), in_sample_trades=len(isr), in_sample_pf=round(R.pf(isr), 2),
                             unseen_trades=len(oor), unseen_pf=round(R.pf(oor), 2), unseen_net_r=round(float(oor.sum()), 1),
                             unseen_stress_pf=round(R.pf(oos), 2), magic=MAGIC + k))
    s = pd.DataFrame(rows)
    s.to_csv(os.path.join(OUT, f"{sym.upper()}_RECAL_PRESETS_SUMMARY.csv"), index=False)
    pd.set_option("display.width", 250)
    print(s.drop(columns=["file", "magic"]).to_string(index=False))


if __name__ == "__main__":
    main()
