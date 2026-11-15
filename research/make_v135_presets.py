#!/usr/bin/env python3
"""
Presets that need XAUUSD_Loma_TrendPullback.mq5 v1.35 (TrailMode, TrailParam, the Stochastic turn filter,
ScaleWithPrice). Run from the repository root.

  trailing <out_dir>
      The 15 timeframe-and-trailing combinations that reached a profit factor of 1.3 on at least 100 unseen trades
      in 16 May - 13 Nov 2026 (research/results/recal/<sym>_successful_trailing.json, "combinations"): one preset per
      setup, 16 for gold and 38 for BTC, in <out_dir>/gold and <out_dir>/btc, each with a summary CSV. Every setup is
      also run on its own on the earlier data (gold: July - December 2024; BTC: 2024 and 2023), and the header says
      what the setup and its combination did there.
      Needs RECAL_PRE_GOLD=<Dukascopy folder Jul-Dec 2024> and RECAL_PRE_BTC=<Binance zips 2023-2024>.

  wf <work_dir> <TF> <condition> <out_dir> <magic_base>
      A combination of the year-by-year test (hump_wf.py) that passed: its setups for the year ahead, picked by the
      same rule on the last three years of the data. [HUMP_SYMBOL=BTCUSD] for BTC.
"""
import json, os, re, sys
import numpy as np, pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EA = os.environ.get("LOMA_EA") or os.path.join(ROOT, "XAUUSD_Loma_TrendPullback.mq5")       # LOMA_EA: another copy of the EA
TF = {"M1": 1, "M2": 2, "M3": 3, "M5": 5, "M10": 10, "M15": 15, "M30": 30, "H1": 16385, "H4": 16388, "D1": 16408}
ENUMS = {"PERIOD_M1": 1, "PERIOD_M2": 2, "PERIOD_M3": 3, "PERIOD_M5": 5, "PERIOD_H1": 16385, "PERIOD_H4": 16388,
         "DIR_BOTH": 0, "DIR_SELL_ONLY": 1, "DIR_BUY_ONLY": 2, "TP_PREV_HUMP": 0, "TP_FIXED_RR": 1}
TRAIL_MODE = {"R": 0, "atr": 1, "percent": 2, "profitlock": 3, "step": 4, "chandelier": 5, "candles": 6, "ema": 7, "sma": 8,
              "psar": 9, "bollinger": 10, "htfcandle": 11, "pivots": 12, "hump": 13}
TRAIL_NAME = {"R": "Risk", "atr": "ATRentry", "percent": "Percent", "profitlock": "ProfitLock", "step": "Step", "chandelier": "Chandelier",
              "candles": "Candles", "ema": "EMA", "sma": "SMA", "psar": "PSAR", "bollinger": "Bollinger", "htfcandle": "HTFcandle",
              "pivots": "Pivots", "hump": "Hump"}
ENUM_NAMES = ["TRAIL_RISK", "TRAIL_ATR_ENTRY", "TRAIL_PERCENT", "TRAIL_PROFIT_LOCK", "TRAIL_STEP", "TRAIL_CHANDELIER", "TRAIL_CANDLES",
              "TRAIL_EMA", "TRAIL_SMA", "TRAIL_PSAR", "TRAIL_BOLLINGER", "TRAIL_HTF_CANDLE", "TRAIL_PIVOTS", "TRAIL_HUMP"]
ENUMS.update({n: i for i, n in enumerate(ENUM_NAMES)})
SESS = {"all": None, "ldn_ny_07-20": ("07:00", "20:00"), "ny_12-1630": ("12:00", "16:30"), "ny_12-20": ("12:00", "20:00"),
        "london_07-12": ("07:00", "12:00")}
SESS_NAME = {"all": "AllDay", "ldn_ny_07-20": "0700-2000", "ny_12-1630": "1200-1630", "ny_12-20": "1200-2000", "london_07-12": "0700-1200"}
SIDE = {0: "Both", -1: "Sell", 1: "Buy"}


def hhmm(m):
    return f"{int(m) // 60:02d}:{int(m) % 60:02d}"


def defaults():
    """Every input of the EA in declaration order with its default (enums as numbers)."""
    out = []
    for _t, name, val in re.findall(r"^input\s+([\w]+)\s+(\w+)\s*=\s*([^;]+);", open(EA).read(), re.M):
        v = val.strip()
        if v.startswith('"'):
            out.append((name, v.strip('"'))); continue
        if v in ENUMS:
            v = str(ENUMS[v])
        elif re.fullmatch(r"[A-Z_][A-Z0-9_]*", v):
            raise SystemExit(f"unmapped enum {v} for {name}")
        out.append((name, v))
    return out


EA_SRC = open(EA).read()
EA_VERSION = re.search(r'#property version\s+"([\d.]+)"', EA_SRC).group(1)
for name in ("TrailMode", "TrailParam", "UseStochTurnFilter", "ScaleWithPrice", "ReferencePrice"):
    assert re.search(rf"^input\s+\w+\s+{name}\s*=", EA_SRC, re.M), f"{EA} has no input {name}: v1.35 is needed"
for i, n in enumerate(ENUM_NAMES):                                   # the enum values of the EA are the ones used here
    assert re.search(rf"\b{n}\s*=\s*{i}\b", EA_SRC), f"{n} is not {i} in the EA"


def ea_inputs(p, btc, magic, comment):
    f_, s_ = p["macd"].split("-"); lo, hi = p["stoch_lv"].split("-")
    o = dict(MagicNumber=magic, TradeComment=comment, TradeDirection={0: 0, -1: 1, 1: 2}[p["sides"]],
             TriggerTimeframe=TF[p["tf"]], MACD_Fast=int(f_), MACD_Slow=int(s_), Stoch_K=p["stoch_k"],
             StochLow=float(lo), StochHigh=float(hi), BigHumpHistory=p["hist"], BigHumpMultiplier=p["big_mult"],
             BigHumpMinBars=p["big_min_bars"], RequireStochLevel="true" if p["stoch_req"] else "false",
             TrendBreakRatio=p["break_ratio"], MaxSignalsPerBigHump=p["max_signals"], TrendMaxBars=p["trend_max_bars"],
             PullbackMinBars=p["pb_min_bars"], PullbackMaxRatio=p["pb_max_ratio"],
             SL_Buffer_Points=int(round(p["buf"] * 100)), TP_Mode=p["tp_mode"], TP_Anticipation=p["anticip"],
             TP_RR=p["tp_rr"], MinRewardRisk=p["min_rr"], MinSL_Points=int(round(p["min_risk"] * 100)),
             UseHTFFilter="false" if p["htf"] == "none" else "true", HTF_Timeframe=TF.get(p["htf"], 16388),
             HTF_EMA_Period=p["htf_ema"], RiskPercent=0.5,
             TrailMode=TRAIL_MODE[p.get("trail_kind", "R")], TrailStartR=p["trail_start"], TrailDistanceR=p["trail_dist"],
             TrailParam=int(p.get("trail_p", 0)),
             UseTradingHours="false" if SESS[p["session"]] is None else "true", SkipBigPullback="true",
             MaxHoldMinutes=int(p["max_hold"]), CloseAtEndOfDay="true" if p["eod"] >= 0 else "false",
             EndOfDayTime=hhmm(p["eod"]) if p["eod"] >= 0 else "22:00")
    if p.get("trail_kind", "R") == "R" and p["trail_start"] <= 0:
        o["TrailStartR"] = 0.0
    if p["tp_mode"] == 1 and abs(p["min_rr"] - p["tp_rr"]) < 1e-9:
        o["MinRewardRisk"] = round(p["tp_rr"] - 0.05, 2)       # a reward equal to the minimum: the EA's tick rounding would decide
    if btc:
        o.update(MaxSpread_Points=3000, MaxSlippage_Points=1000, TrailStep_Points=200, CloseBeforeWeekend="false")
    else:
        o.update(MaxSpread_Points=60, CloseBeforeWeekend="true", WeekendCloseTime="23:00")
    if SESS[p["session"]]:
        o["TradingHoursStart"], o["TradingHoursEnd"] = SESS[p["session"]]
    return o


def write_set(path, head, o):
    base = defaults(); names = {n for n, _ in base}
    assert not (set(o) - names), set(o) - names
    lines = [h if h.startswith(";") else "; " + h for h in head]
    assert all(x.isascii() for x in lines), [x for x in lines if not x.isascii()]
    with open(path, "w", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
        for n, v in base:
            f.write(f"{n}={o.get(n, v)}\n")


def plain(x):
    """ASCII for the .set headers (MT5 reads them as ANSI)."""
    return (x.replace("–", "-").replace("—", "-").replace("−", "-").replace("×", "x").replace("’", "'"))


# ----------------------------------------------------------------------------- trailing combinations
def trailing(out_dir):
    sys.path.insert(0, os.path.join(ROOT, "research"))
    os.environ["HUMP_SPACE"] = "2"
    import importlib
    res = {}
    for sym in ("XAUUSD", "BTCUSD"):
        os.environ["HUMP_SYMBOL"] = sym
        for m in [m for m in list(sys.modules) if m in ("hump_engine", "hump_search", "hump_trail", "hump_trail2", "hump_tf_recal", "xlzc_backtest")]:
            del sys.modules[m]
        import hump_engine as H, hump_search as X, hump_trail2 as T2, hump_tf_recal as R, xlzc_backtest as B
        btc = sym == "BTCUSD"
        d = json.load(open(os.path.join(ROOT, "research", "results", "recal", f"{sym.lower()}_successful_trailing.json")))
        # the earlier period
        if btc:
            raw = R.read_binance_zips([os.environ["RECAL_PRE_BTC"]])
            m1 = raw.copy(); m1.index = R.utc_to_server(raw.index); m1 = m1[~m1.index.duplicated()].sort_index()
            hs = np.full(len(m1), H.BTC_SPREAD / 2.0)
            periods = {"2024": ("2024-01-01", "2025-01-01"), "2023": ("2023-01-15", "2024-01-01")}
        else:
            import duk_to_m1 as D
            m1, _ = D.load(os.environ["RECAL_PRE_GOLD"]); m1 = m1[["open", "high", "low", "close"]].astype(float)
            _, hourly = B.load(H.DATA); hs = hourly[B.server_to_utc_hour(m1.index)] / 2.0
            first = m1.index[0] + pd.Timedelta(days=14)
            periods = {"Jul-Dec 2024": (str(first), "2025-01-01")}
        R.clock_check(m1[["open", "high", "low", "close"]], f"{sym} earlier period")
        mk = T2.MarketY(m1=m1[["open", "high", "low", "close"]], half_spread=hs)
        sub = os.path.join(out_dir, "btc" if btc else "gold"); os.makedirs(sub, exist_ok=True)
        rows = []; magic = 26113600 if btc else 26113500
        tag = "BTC" if btc else "Gold"
        for c in d["combinations"]:
            k_total = len(c["picks"])
            early_all = {y: [] for y in periods}
            per_pick = []
            for q in c["picks"]:
                p = q["params"]
                if p["tp_mode"] == 1 and abs(p["min_rr"] - p["tp_rr"]) < 1e-9:     # the preset takes every signal (see ea_inputs)
                    p = dict(p, min_rr=round(p["tp_rr"] - 0.05, 2))
                cfg = X.engine_cfg(dict(X.BASE, **p))
                df = mk.run_y(cfg); t = df.entry_time.values.astype("datetime64[m]")
                e = {}
                for y, (a, b) in periods.items():
                    r = df.r.values[(t >= np.datetime64(a)) & (t < np.datetime64(b))]
                    e[y] = r; early_all[y].append(r)
                per_pick.append(e)
            grp_early = {y: np.concatenate(v) for y, v in early_all.items()}
            stored = {y.replace("y", ""): v for y, v in c["earlier"].items()}
            has_tie = any(q["params"]["tp_mode"] == 1 and abs(q["params"]["min_rr"] - q["params"]["tp_rr"]) < 1e-9 for q in c["picks"])
            for y, r in grp_early.items():                                 # the group must equal the stored check
                key = "2024H2" if y.startswith("Jul") else y
                if not has_tie:
                    assert len(r) == stored[key]["trades"] and abs(R.pf(r) - stored[key]["pf"]) < 0.006, (sym, c["timeframe"], c["trailing"], y, len(r), stored[key])
            tie_fig = {}
            if has_tie:                                                    # in-sample and unseen figures of the tie setup at the preset's setting
                work = os.environ["RECAL_WORK_BTC" if btc else "RECAL_WORK_GOLD"]
                mk26 = R.market(work)
                for q in c["picks"]:
                    p0 = q["params"]
                    if p0["tp_mode"] == 1 and abs(p0["min_rr"] - p0["tp_rr"]) < 1e-9:
                        df = mk26.run_y(X.engine_cfg(dict(X.BASE, **dict(p0, min_rr=round(p0["tp_rr"] - 0.05, 2)))))
                        t = df.entry_time.values.astype("datetime64[m]"); r = df.r.values.astype(float)
                        isr, oor = r[t < R.IS_END], r[t >= R.IS_END]
                        tie_fig[id(q)] = dict(is_n=len(isr), is_pf=R.pf(isr), oos_n=len(oor), oos_pf=R.pf(oor), oos_net=float(oor.sum()))
            for k, (q, e) in enumerate(zip(c["picks"], per_pick), 1):
                p = q["params"]; magic += 1
                side = SIDE[p["sides"]]; sess = SESS_NAME[p["session"]]; filt = p["htf"] if p["htf"] != "none" else "NoFilter"
                fname = f"Loma_T15_{tag}_{p['tf']}_{TRAIL_NAME[p['trail_kind']]}_{k}of{k_total}_{side}_{sess}_{filt}"
                o = ea_inputs(p, btc, magic, f"LOMA_T{p['tf']}{TRAIL_NAME[p['trail_kind']][:4]}{k}")
                early_txt = "; ".join(f"{y}: this setup {len(r)} trades, PF {R.pf(r):.2f}" for y, r in e.items())
                grp_txt = "; ".join(f"{y} PF {R.pf(r):.2f} ({len(r)} trades)" for y, r in grp_early.items())
                tf_ = tie_fig.get(id(q))
                tie_line = ([plain(f"Its target ({p['tp_rr']}R) equals its minimum reward: the backtest takes every such signal, the EA would refuse "
                                   f"some by tick rounding, so this preset sets MinRewardRisk {round(p['tp_rr'] - 0.05, 2)}. At that setting: "
                                   f"Jan 2025 - May 15 2026 {tf_['is_n']} trades PF {tf_['is_pf']:.2f}; unseen 2026 {tf_['oos_n']} trades PF {tf_['oos_pf']:.2f}, net {tf_['oos_net']:+.1f}R.")]
                            if tf_ else [])
                head = [plain(f"XAUUSD_Loma_TrendPullback v{EA_VERSION} on {sym} - trailing result {c['timeframe']} + {TRAIL_NAME[c['trailing']]} trailing, setup {k} of {k_total}: "
                              f"{side.lower()}, session {sess} server time, trend filter {q['trend_filter']}, target {q['target']}. "
                              + ("DO NOT LOAD ON GOLD." if btc else "DO NOT LOAD ON BTC.")),
                        plain(f"Trailing: {q['trailing_rule']}. Needs EA v1.35 or later (TrailMode {TRAIL_MODE[p['trail_kind']]}, TrailParam {int(p.get('trail_p', 0))})."),
                        plain(f"Picked on Jan 2025 - May 15 2026 only (score {q['in_sample_score']:.2f}): {q['in_sample_trades']} trades, PF {q['in_sample_pf']:.2f}."),
                        plain(f"UNSEEN May 16 - Nov 13 2026, at the backtest's costs ({'assumed 10 USD spread' if btc else 'FTMO spread table'}, no commission): "
                              f"this setup {q['unseen_trades']} trades, PF {q['unseen_pf']:.2f}, net {q['unseen_net_r']:+.1f}R; "
                              f"the {k_total} setups of this combination together {c['unseen_trades']} trades, PF {c['unseen_pf']:.2f} (stressed {c['unseen_stress_pf']:.2f})."),
                        *([] if btc else [plain(f"At VT Markets' costs (1.5-pip spread, 0.60 USD commission per ounce) on the same months: this setup "
                                                f"{q['vt_unseen_trades']} trades, PF {q['vt_unseen_pf']:.2f}; the {k_total} setups together "
                                                f"{c['vt_unseen_trades']} trades, PF {c['vt_unseen_pf']:.2f} (stressed {c['vt_unseen_stress_pf']:.2f}).")]),
                        plain(f"EARLIER DATA, before the calibration period: {early_txt}. The combination together: {grp_txt}. "
                              "The 2026 result did NOT hold on earlier data: UNPROVEN, demo and Strategy Tester only."),
                        *tie_line,
                        ("Data: Binance BTCUSDT M1 in broker server time, assumed spread 10 USD. Points are 0.01 USD: 2000 points = 20 USD."
                         if btc else "Data: FTMO XAUUSD M1 to May 15 2026, Dukascopy after; FTMO spread table; no commission in the test (VT: set CommissionPerLot)."),
                        "Times are BROKER SERVER TIME (New York + 7 h: GMT+2 in the US winter, GMT+3 in the US summer).",
                        "UseNewsFilter was not in the backtest."]
                write_set(os.path.join(sub, fname + ".set"), head, o)
                rows.append(dict(file=fname, timeframe=p["tf"], trailing=TRAIL_NAME[p["trail_kind"]], trailing_rule=q["trailing_rule"], setup=f"{k} of {k_total}",
                                 direction=side, session=sess, trend_filter=q["trend_filter"], target=q["target"],
                                 in_sample_score=q["in_sample_score"], in_sample_trades=q["in_sample_trades"], in_sample_pf=q["in_sample_pf"],
                                 unseen_trades=q["unseen_trades"], unseen_pf=q["unseen_pf"], unseen_net_r=q["unseen_net_r"], unseen_stress_pf=q["unseen_stress_pf"],
                                 combination_unseen_trades=c["unseen_trades"], combination_unseen_pf=c["unseen_pf"], combination_unseen_stress_pf=c["unseen_stress_pf"],
                                 costs="assumed 10 USD spread, no commission" if btc else "FTMO spread table, no commission",
                                 **({} if btc else dict(vt_unseen_trades=q["vt_unseen_trades"], vt_unseen_pf=q["vt_unseen_pf"],
                                                        combination_vt_unseen_trades=c["vt_unseen_trades"], combination_vt_unseen_pf=c["vt_unseen_pf"],
                                                        combination_vt_unseen_stress_pf=c["vt_unseen_stress_pf"])),
                                 **{f"earlier_{y.replace(' ', '_').replace('-', '_')}_trades": len(r) for y, r in e.items()},
                                 **{f"earlier_{y.replace(' ', '_').replace('-', '_')}_pf": round(R.pf(r), 2) for y, r in e.items()},
                                 **{f"combination_earlier_{y.replace(' ', '_').replace('-', '_')}_pf": round(R.pf(r), 2) for y, r in grp_early.items()},
                                 magic=magic))
        s = pd.DataFrame(rows)
        s.to_csv(os.path.join(sub, f"{tag.upper()}_TRAILING15_SUMMARY.csv"), index=False)
        res[sym] = s
        pd.set_option("display.width", 250)
        print(f"{sym}: {len(s)} presets in {sub}")
        print(s[["file", "unseen_pf", "unseen_trades"] + [c for c in s.columns if c.startswith("earlier_") and c.endswith("_pf")]].to_string(index=False))
    return res


# ----------------------------------------------------------------------------- year-by-year pass
COND_TEXT = {"xlzc_stoch": "entries only when the Stochastic (7,1,7) of the trigger timeframe came from 80 (sells) / 20 (buys) within 5 bars and turned (UseStochTurnFilter)",
             "xlzc_both": "entries only after the Stochastic turn and a liquidity sweep"}


def wf(work, tf, key, out_dir, magic, detail_json=None):
    sys.path.insert(0, os.path.join(ROOT, "research"))
    import pickle
    import hump_wf as W
    btc = W.BTC
    A = np.load(os.path.join(work, f"wf_{tf}.npy")).astype(np.float64)
    d = pickle.load(open(os.path.join(work, f"wf_{tf}_params.pkl"), "rb"))
    P, years = d["params"], d["years"]; v = d["keys"].index(key)
    cal = list(range(len(years) - 3, len(years)))                 # the last three years of the data
    picks, score, cost, n_ok, n_cost = W.window_pick(A, P, v, cal)
    meta = json.load(open(os.path.join(work, "meta.json")))
    hist = ""
    if detail_json:
        dj = json.load(open(detail_json)); a = dj["all_unseen_years"]
        hist = ("Year by year, setups picked by this rule on the three years before each year: "
                + ", ".join(f"{y} PF {v['pf']:.2f} ({v['n']} trades)" for y, v in a["by_year"].items())
                + f". The last year ({max(a['by_year'])}) was kept back: it was not used to pick the setups or to decide the pass "
                f"({min(a['by_year'])} - {sorted(a['by_year'])[-2]} decided it).")
    os.makedirs(out_dir, exist_ok=True)
    tag = "BTC" if btc else "Gold"
    rows = []
    for k, i in enumerate(picks, 1):
        p = P[i]
        c = A[i, v, :, :, :]                                        # [cost, year, 4]
        yr = {years[y]: (int(c[0, y, 0]), float(W.pf_of(c[0, y, 1], c[0, y, 2]))) for y in cal}
        o = ea_inputs(dict(p, trail_kind="R"), btc, magic + k, f"LOMA_W{tf}{k:02d}")
        o.update(ScaleWithPrice="true", ReferencePrice=round(meta["anchor_price"], 2),
                 RiskPercent=0.1)                                   # the presets run together: up to 9 positions at once
        if key in ("xlzc_stoch", "xlzc_both"):
            o.update(UseStochTurnFilter="true")
        side = SIDE[p["sides"]]; sess = SESS_NAME[p["session"]]; filt = p["htf"] if p["htf"] != "none" else "NoFilter"
        fname = f"Loma_WF_{tag}_{tf}_{key}_{k:02d}_{side}_{sess}_{filt}"
        head = [plain(f"XAUUSD_Loma_TrendPullback v{EA_VERSION} on {'BTCUSD' if btc else 'XAUUSD'} - year-by-year result {tf}, setup {k} of {len(picks)}: "
                      f"{side.lower()}, session {sess} server time, trend filter {p['htf']}" + (f" EMA {p['htf_ema']}" if p['htf'] != 'none' else "")
                      + f"; {COND_TEXT.get(key, key)}. " + ("DO NOT LOAD ON GOLD." if btc else "DO NOT LOAD ON BTC.")),
                plain(f"Picked for the year ahead on {years[cal[0]]} - 13 Nov {years[cal[-1]]} by the year-by-year rule: lowest of six profit factors {score[i]:.2f}; "
                      + ", ".join(f"{y}: {n} trades PF {pf:.2f}" for y, (n, pf) in yr.items()) + ". These are calibration figures."),
                *([plain(hist)] if hist else []),
                plain(f"ScaleWithPrice: SL_Buffer_Points, MinSL_Points and MaxSL_Points were calibrated at {meta['anchor_price']:.2f} (ReferencePrice) "
                      "and follow the price; the spread, slippage and trailing-step limits do not."),
                plain("UNPROVEN: the rule met the year-by-year pass rule, but with 472 combinations tested one or two such passes are expected by "
                      "chance, and the 2026 months kept back gave PF 1.26, under 1.3. Demo only."),
                f"RiskPercent 0.1: the {len(picks)} presets are meant to run together on one hedging account, and they overlap.",
                "Times are BROKER SERVER TIME (New York + 7 h: GMT+2 in the US winter, GMT+3 in the US summer). Demo and Strategy Tester first.",
                "UseNewsFilter was not in the backtest."]
        write_set(os.path.join(out_dir, fname + ".set"), head, o)
        rows.append(dict(file=fname, timeframe=tf, condition=key, direction=side, session=sess, trend_filter=p["htf"], htf_ema=p["htf_ema"],
                         macd=p["macd"], target=f"{p['tp_rr']}R" if p["tp_mode"] == 1 else "previous hump",
                         trailing=("off" if p["trail_start"] <= 0 else
                                   f"never active (would start at {p['trail_start']}R, {'at' if p['trail_start'] == p['tp_rr'] else 'beyond'} the {p['tp_rr']}R target)" if p["tp_mode"] == 1 and p["trail_start"] >= p["tp_rr"] else
                                   f"from {p['trail_start']}R, {p['trail_dist']}R behind"),
                         score=round(float(score[i]), 3), **{f"cal_{y}_trades": n for y, (n, pf) in yr.items()},
                         **{f"cal_{y}_pf": round(pf, 2) for y, (n, pf) in yr.items()}, magic=magic + k))
    s = pd.DataFrame(rows)
    s.to_csv(os.path.join(out_dir, f"{tag.upper()}_WF_{tf}_{key}_SUMMARY.csv"), index=False)
    pd.set_option("display.width", 250)
    print(s.to_string(index=False))


# ----------------------------------------------------------------------------- existing presets
def upgrade(paths):
    """Rewrite earlier presets for this EA version: the same values, every input of the EA in its order (new
    inputs at their defaults, which keep the earlier behaviour), and the version in the header updated."""
    base = defaults(); names = [n for n, _ in base]
    for path in paths:
        lines = open(path, encoding="ascii").read().splitlines()
        head = [x for x in lines if x.startswith(";")]
        vals = dict(x.split("=", 1) for x in lines if x and not x.startswith(";"))
        unknown = set(vals) - set(names)
        assert not unknown, (path, unknown)
        head = [re.sub(r"XAUUSD_Loma_TrendPullback v1\.3\d", f"XAUUSD_Loma_TrendPullback v{EA_VERSION}", h) for h in head]
        assert f"v{EA_VERSION}" in head[0], (path, head[0])
        tmp = path + ".tmp"
        with open(tmp, "w", newline="\n") as f:
            f.write("\n".join(head) + "\n")
            for n, v in base:
                f.write(f"{n}={vals.get(n, v)}\n")
        os.replace(tmp, path)
        added = [n for n in names if n not in vals]
        print(f"{os.path.basename(path)}: {len(vals)} inputs kept, {len(added)} added at their defaults")


if __name__ == "__main__":
    if sys.argv[1] == "upgrade":
        upgrade(sys.argv[2:])
    elif sys.argv[1] == "trailing":
        trailing(sys.argv[2])
    elif sys.argv[1] == "wf":
        wf(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], int(sys.argv[6]), sys.argv[7] if len(sys.argv) > 7 else None)
