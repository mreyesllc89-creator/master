#!/usr/bin/env python3
"""
Write EA presets (.set) for the picks of the per-timeframe re-calibration (hump_tf_recal.py) that use the
EA's own trailing stop (run 1, files cand_<TF>.pkl): the setups picked on Jan 2025 - May 15 2026 for the given
timeframes, each with its in-sample and unseen (May 16 - Nov 13 2026) figures in the header.

With RECAL_PRE_DIR=<directory of Binance zips for 2023-2024> (BTC only) each preset is also run on those two
earlier years, which lie before the calibration data, and the result is written into the header and the CSV.

<SYM>_RECAL_PRESETS_DETAIL.json holds what the guide quotes for each timeframe's picks: stop sizes in dollars, the
unseen months one by one, the unseen result at twice the spread and without the three largest winners.

Usage (repository root):
  [HUMP_SYMBOL=BTCUSD] [RECAL_PRE_DIR=<dir>] python3 research/make_recal_presets.py <recal_work_dir> <out_dir> <magic_base> <TF> [<TF> ...]
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


def trail_text(p):
    if p["trail_start"] <= 0:
        return "off"
    if p["tp_mode"] == 1 and p["trail_start"] >= p["tp_rr"]:
        return f"never active (would start at {p['trail_start']}R, the target)"
    return f"from {p['trail_start']}R, {p['trail_dist']}R behind"


def earlier_market(spread=None):
    """BTC 2023-2024 from raw Binance zips, converted to server time once (None when RECAL_PRE_DIR is not set)."""
    pre = os.environ.get("RECAL_PRE_DIR")
    if not (BTC and pre):
        return None
    raw = R.read_binance_zips([pre])
    m1 = raw.copy(); m1.index = R.utc_to_server(raw.index)
    m1 = m1[~m1.index.duplicated()].sort_index()
    R.clock_check(m1, "BTC 2023-2024")
    return R.T2.MarketY(m1=m1, half_spread=np.full(len(m1), (R.H.BTC_SPREAD if spread is None else spread) / 2.0))


def picks_of(tf):
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
        fams.add(fam); picked.append(P[i])
    return picked


def exposure(frames, mk, risk_pct=0.5):
    """Position size in multiples of the balance at RiskPercent, per trade and for all picks together, and how
    often positions of two different presets are open at the same time."""
    rows = []
    for k, df in enumerate(frames):
        for e, x, sd, rk in zip(df.entry_row.astype(int), df.exit_row.astype(int), df.side, df.risk):
            rows.append((e, x, sd, 0.01 * risk_pct * mk.o[e] / rk, k))
    if not rows:
        return {}
    a = np.array(rows, float); lev = a[:, 3]
    together = [float(lev[(a[:, 0] <= e) & (a[:, 1] >= e)].sum()) for e in a[:, 0]]
    n_open = [int(((a[:, 0] <= e) & (a[:, 1] >= e)).sum()) for e in a[:, 0]]
    pairs = same = 0
    for i in range(len(a)):
        for j in range(i + 1, len(a)):
            if a[i, 4] != a[j, 4] and a[i, 0] <= a[j, 1] and a[j, 0] <= a[i, 1]:
                pairs += 1; same += a[i, 2] == a[j, 2]
    return dict(per_trade_median=float(np.median(lev)), per_trade_p90=float(np.quantile(lev, 0.9)), per_trade_max=float(lev.max()),
                all_presets_max=float(max(together)), max_positions_open=int(max(n_open)), pairs_open_together=int(pairs), pairs_same_direction=int(same))


def detail(tfs):
    """Figures quoted in the guide, per timeframe: all picks of the timeframe together on the unseen months."""
    mk = R.market(WORK)
    wide = R.market(WORK, flat_spread=2 * R.H.BTC_SPREAD) if BTC else None
    pre_free = earlier_market(spread=0.0)
    costs_only = dict(R.STRESS, delay=0)
    out = {}
    for tf in tfs:
        frames = []; wr = []; allrisk = []; full = []; cost_r = []; extra = {10: [], 20: [], 40: [], 45: []}; free = {"2024": [], "2023": []}
        for p in picks_of(tf):
            c = dict(X.BASE); c.update(p)
            df = mk.run(X.engine_cfg(c)); allrisk.append(df.risk.values.astype(float)); full.append(df)
            df = df[df.entry_time.values >= R.IS_END]
            frames.append(df[["entry_time", "side", "r", "risk", "entry_row", "exit_row"]])
            q = mk.run(X.engine_cfg(dict(c, **costs_only))); cost_r.append(q.r.values[q.entry_time.values >= R.IS_END])
            if BTC:
                for usd in extra:                                   # extra round-trip cost per BTC on top of the spread
                    q = mk.run(X.engine_cfg(dict(c, comm=float(usd)))); extra[usd].append(q.r.values[q.entry_time.values >= R.IS_END])
            if wide is not None:
                w = wide.run(X.engine_cfg(c)); wr.append(w.r.values[w.entry_time.values >= R.IS_END])
            if pre_free is not None:
                q = pre_free.run(X.engine_cfg(c)); t = q.entry_time.values.astype("datetime64[m]")
                free["2024"].append(q.r.values[(t >= np.datetime64("2024-01-01")) & (t < np.datetime64("2025-01-01"))])
                free["2023"].append(q.r.values[(t >= np.datetime64("2023-01-15")) & (t < np.datetime64("2024-01-01"))])
        if not frames:
            continue
        a = pd.concat([f.assign(preset=k + 1) for k, f in enumerate(frames)]).sort_values("entry_time")
        shared = {}
        for minute, g in a.groupby("entry_time"):
            if g.preset.nunique() > 1:
                key = "+".join(f"R{int(x):02d}" for x in sorted(g.preset.unique())); shared[key] = shared.get(key, 0) + 1
        month = a.entry_time.dt.strftime("%Y-%m")
        r = a.r.values.astype(float); top3 = np.sort(r)[:-3] if len(r) > 3 else r
        eq = np.cumsum(r); dd = float((np.maximum.accumulate(np.maximum(eq, 0)) - eq).max()) if len(r) else 0.0
        unseen = mk.m1["close"][mk.m1.index >= pd.Timestamp(str(R.IS_END))]
        mon = unseen.groupby(unseen.index.strftime("%Y-%m")).agg(["first", "last"])
        falling = set(mon.index[mon["last"] < mon["first"]])
        fall = month.isin(falling).values; sell = (a.side < 0).values; rr = a.r.values.astype(float)
        out[tf] = dict(
            unseen_first_close=float(unseen.iloc[0]), unseen_last_close=float(unseen.iloc[-1]),
            unseen_low_close=float(unseen.min()), unseen_low_date=str(unseen.idxmin().date()),
            unseen_high_close=float(unseen.max()), unseen_high_date=str(unseen.idxmax().date()),
            falling_months=sorted(falling), rising_months=sorted(set(mon.index) - falling),
            sells_in_falling_months=dict(trades=int((sell & fall).sum()), net_r=float(rr[sell & fall].sum())),
            sells_in_rising_months=dict(trades=int((sell & ~fall).sum()), net_r=float(rr[sell & ~fall].sum())),
            buys_all=dict(trades=int((~sell).sum()), net_r=float(rr[~sell].sum())),
            pf_extra_costs_without_late_entry=R.pf(np.concatenate(cost_r)),
            pf_by_extra_cost_per_btc=({str(k): R.pf(np.concatenate(v)) for k, v in extra.items()} if BTC else None),
            earlier_years_no_spread=({y: R.pf(np.concatenate(v)) for y, v in free.items()} if pre_free is not None else None),
            shared_entry_minutes=shared,
            exposure_unseen=exposure(frames, mk), exposure_whole_series=exposure(full, mk),
            picks=len(frames), trades=int(len(a)), pf=R.pf(r), net_r=float(r.sum()), win_rate=float((r > 0).mean()),
            distinct_entry_minutes=int(a.entry_time.nunique()), buys=int((a.side > 0).sum()), sells=int((a.side < 0).sum()),
            pf_without_3_largest_wins=R.pf(top3), max_drawdown_r=dd,
            pf_at_double_spread=(R.pf(np.concatenate(wr)) if wr else None), double_spread_trades=(int(sum(len(x) for x in wr)) if wr else None),
            stop_usd=dict(median=float(a.risk.median()), p10=float(a.risk.quantile(0.10)), p90=float(a.risk.quantile(0.90)),
                          max=float(a.risk.max())),
            stop_usd_whole_series=dict(trades=int(len(np.concatenate(allrisk))), median=float(np.median(np.concatenate(allrisk))),
                                       p90=float(np.quantile(np.concatenate(allrisk), 0.90)), max=float(np.concatenate(allrisk).max())),
            months=[dict(month=m, trades=int(len(g)), net_r=float(g.r.sum()), pf=R.pf(g.r.values.astype(float)))
                    for m, g in a.groupby(month.values)])
    return out


def main():
    base = M.defaults(); names = {n for n, _ in base}
    pre_mk = earlier_market()
    years = {"2024": (np.datetime64("2024-01-01"), np.datetime64("2025-01-01")),
             "2023": (np.datetime64("2023-01-15"), np.datetime64("2024-01-01"))}
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
        early = {}
        if pre_mk is not None:
            for i in picked:
                c = dict(X.BASE); c.update(P[i])
                df = pre_mk.run(X.engine_cfg(c)); t = df.entry_time.values.astype("datetime64[m]"); r = df.r.values.astype(float)
                early[i] = {y: r[(t >= a) & (t < b)] for y, (a, b) in years.items()}
        for rank, i in enumerate(picked, 1):
            k += 1
            p = P[i]
            isr, _, oor = R.split(*Bs[i]); iss, _, oos = R.split(*Ss[i])
            side = T.SIDE[p["sides"]]; sess = T.SESS_NAME[p["session"]]
            filt = p["htf"] if p["htf"] != "none" else "NoFilter"
            fname = f"Loma_{sym}_{tf}_R{rank:02d}_{side}_{sess}_{filt}"
            o = ea_inputs(p, MAGIC + k, f"LOMA_{sym[0]}{tf}_{rank:02d}")
            assert not (set(o) - names), set(o) - names
            trail = trail_text(p)
            head = [f"; XAUUSD_Loma_TrendPullback v{M.EA_VERSION} on {'BTCUSD' if BTC else 'XAUUSD'} - re-calibration pick {rank} of {len(picked)} "
                    f"for {tf}: {side.lower()}, session {sess} server time, trend filter {p['htf']}, trailing {trail}."
                    + (" DO NOT LOAD ON GOLD." if BTC else " DO NOT LOAD ON BTC."),
                    f"; Picked on Jan 2025 - May 15 2026 only (lowest of six profit factors, normal and stressed costs: {sc[i]:.2f}): "
                    f"{len(isr)} trades, PF {R.pf(isr):.2f}, stressed {R.pf(iss):.2f}.",
                    f"; UNSEEN May 16 - Nov 13 2026 (never used to pick it): {len(oor)} trades, PF {R.pf(oor):.2f}, net {oor.sum():+.1f}R; "
                    f"stressed PF {R.pf(oos):.2f}. All {len(picked)} {tf} picks together: {len(pooled)} trades, PF {R.pf(pooled):.2f} "
                    f"(stressed {R.pf(pooled_s):.2f}).",
                    *([f"; EARLIER DATA, before the calibration period: 2024 {len(early[i]['2024'])} trades, PF {R.pf(early[i]['2024']):.2f}; "
                       f"2023 {len(early[i]['2023'])} trades, PF {R.pf(early[i]['2023']):.2f}. All {len(picked)} {tf} picks together: 2024 PF "
                       f"{R.pf(np.concatenate([early[q]['2024'] for q in picked])):.2f}, 2023 PF {R.pf(np.concatenate([early[q]['2023'] for q in picked])):.2f}. "
                       "The 2026 result did not repeat there: UNPROVEN."] if early else []),
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
                             unseen_stress_pf=round(R.pf(oos), 2),
                             **({"y2024_trades": len(early[i]["2024"]), "y2024_pf": round(R.pf(early[i]["2024"]), 2),
                                 "y2023_trades": len(early[i]["2023"]), "y2023_pf": round(R.pf(early[i]["2023"]), 2)} if early else {}),
                             magic=MAGIC + k))
    s = pd.DataFrame(rows)
    s.to_csv(os.path.join(OUT, f"{sym.upper()}_RECAL_PRESETS_SUMMARY.csv"), index=False)
    json.dump(detail(TFS), open(os.path.join(OUT, f"{sym.upper()}_RECAL_PRESETS_DETAIL.json"), "w"), indent=1, default=float)
    pd.set_option("display.width", 250)
    print(s.drop(columns=["file", "magic"]).to_string(index=False))


if __name__ == "__main__":
    main()
