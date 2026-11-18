#!/usr/bin/env python3
"""
The best of the EA's trailing systems on every timeframe, from the tick replay (research/tick_replay.py), as presets
for XAUUSD_Loma_TrendPullback.mq5 v1.35, with the guide and the zip. The choice follows the rule written before the
full replay ran: research/results/tick/best_trailing_rule.md.

Usage (repository root):
  python3 research/make_best_trailing.py all <gold_replay_dir> <btc_replay_dir>
     results  research/results/tick/tick_cells.csv          every timeframe x EA trailing system x period x cost model:
                                                             tick and one-minute trades, PF, net R
              research/results/tick/best_by_timeframe.json/.csv  the choice of every timeframe, its candidates, the check
     presets  presets/best_trailing/{gold,btc}/*.set and presets/best_trailing/BEST_TRAILING_PRESETS.csv
     guide    packages/loma_best_trailing/START_HERE.md
     zip      dist/Loma_BestTrailing_v1_35.zip

The replay directories hold <sym>_picks.json and the run's files <sym>_<pre|main>_w<k>of<n>_{picks.csv,trades.npz}
(tick_replay.py run <dir> pre|main ea all <k> <n>). Every EA pick must be there for every cost model and both spans.
The replay runs a setup whose fixed target equals its minimum reward with MinRewardRisk = TP_RR - 0.05 on both engines
(tick_replay.preset_rr), the presets' rule (make_v135_presets.ea_inputs): preset and figures have the same setting.
"""
import json, os, re, shutil, sys, zipfile
import numpy as np, pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "research"))
import make_v135_presets as MP                       # ea_inputs, write_set, plain, TRAIL_MODE, TRAIL_NAME, SESS_NAME, SIDE

EA_KINDS = list(MP.TRAIL_MODE)                       # the EA's 14 trailing systems, TrailMode 0-13
TFS = ["M1", "M2", "M3", "M5", "M10", "M15", "M30", "H1"]
MIN_N, THIN_N, HOLD_PF = 100, 30, 1.3                # best_trailing_rule.md, points 3 and 5
SYMS = {"XAUUSD": dict(tag="Gold", folder="gold", models=["vt", "duk_raw", "vt_stress"], earlier=["earlier"], magic=26118100),
        "BTCUSD": dict(tag="BTC", folder="btc", models=["vt", "vt_stress"], earlier=["2024", "2023"], magic=26118200)}
COL = {"earlier": "2024h2", "2023": "2023", "2024": "2024"}         # column names of the earlier periods
PERIOD_TEXT = {"earlier": "15 Jul – 31 Dec 2024", "2023": "2023 (from 15 Jan)", "2024": "2024",
               "calibration": "1 Jan 2025 – 15 May 2026", "unseen": "16 May – 13 Nov 2026"}
SESS = {"all": "all day", "london_07-12": "07:00-12:00", "ldn_ny_07-20": "07:00-20:00", "ny_12-20": "12:00-20:00", "ny_12-1630": "12:00-16:30"}
SYSTEM = {"R": "risk multiples (EA default)", "atr": "ATR at entry", "percent": "percent of price", "profitlock": "profit lock",
          "step": "stepped", "chandelier": "chandelier", "candles": "candle lows / highs", "ema": "EMA", "sma": "SMA",
          "psar": "Parabolic SAR", "bollinger": "Bollinger band", "htfcandle": "higher-timeframe candle", "pivots": "swing pivots",
          "hump": "hump structure"}
PSAR = {0: (0.02, 0.2), 1: (0.01, 0.1), 2: (0.04, 0.2)}        # hump_trail.PSAR
BOLLINGER = {0: 1.0, 1: 2.0}                                    # hump_trail2.BOLLINGER
_src1, _src2 = open(os.path.join(ROOT, "research", "hump_trail.py")).read(), open(os.path.join(ROOT, "research", "hump_trail2.py")).read()
assert "PSAR = {0: (0.02, 0.2), 1: (0.01, 0.1), 2: (0.04, 0.2)}" in _src1 and "BOLLINGER = {0: 1.0, 1: 2.0}" in _src2
_OUT = os.environ.get("BT_TEST_OUT")                            # a test run writes everything under this folder instead
OUT_RES = os.path.join(_OUT or ROOT, "research", "results", "tick")
OUT_SETS = os.path.join(_OUT or ROOT, "presets", "best_trailing")
GUIDE = os.path.join(_OUT or ROOT, "packages", "loma_best_trailing", "START_HERE.md")
DIST = os.path.join(_OUT or ROOT, "dist")


ENGINE_NAMES = np.array(["1m", "tick", "1m_raw"], dtype=object)     # tick_replay.ENGINES


def pf(r):
    """hump_tf_recal.pf: gross wins / gross losses (inf without losses, nan without trades)."""
    r = np.asarray(r, float)
    w = r[r > 0].sum(); l = -r[r < 0].sum()
    return float(w / l) if l > 0 else (float("inf") if w > 0 else float("nan"))


def f2(x):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else ("no losses" if np.isinf(x) else f"{x:.2f}")


def is_tie(p):
    return int(p["tp_mode"]) == 1 and abs(p["min_rr"] - p["tp_rr"]) < 1e-9


def start_txt(a):
    return "from the minute after entry" if a <= 0 else f"once the profit reaches {a:g}R"


def describe(p):
    """successful_trailing.describe for the EA's 14 systems: the trailing rule in plain words (R = initial risk)."""
    k, a, b, n, tf = p["trail_kind"], p["trail_start"], p["trail_dist"], int(p.get("trail_p", 0)), p["tf"]
    lvl = lambda what: f"stop beyond {what}, {start_txt(a)}"
    return {
        "R": lambda: f"{b:g}R behind the best price once the profit reaches {a:g}R (the EA's own rule)",
        "percent": lambda: f"{b:g}% of price behind the best price once the profit reaches {a:g}%, stop moved once per closed minute",
        "atr": lambda: f"{b:g} x ATR(14) of {tf} at entry behind the best price once the profit reaches {a:g} x ATR, stop moved once per closed minute",
        "step": lambda: f"every {a:g}R of profit lifts the stop by {a:g}R, one step behind (breakeven at +{a:g}R)",
        "candles": lambda: lvl(f"the low / high of the last closed {tf} candle" if n == 1 else f"the low / high of the last {n} closed {tf} candles"),
        "ema": lambda: lvl(f"the EMA({n}) of {tf} closes"),
        "sma": lambda: lvl(f"the SMA({n}) of {tf} closes"),
        "psar": lambda: lvl(f"the Parabolic SAR ({PSAR[n][0]:g} / {PSAR[n][1]:g}) of {tf}"),
        "hump": lambda: lvl("the last completed pullback hump"),
        "chandelier": lambda: f"{b:g} x live ATR(14) of {tf} behind the best price, {start_txt(a)}",
        "profitlock": lambda: f"keeps {100 * b:.0f}% of the best open profit once it reaches {a:g}R, stop moved once per closed minute",
        "bollinger": lambda: lvl(f"the Bollinger band SMA(20) -/+ {BOLLINGER[n]:g} sd of {tf}"),
        "pivots": lambda: lvl(f"the last confirmed {tf} swing with {n} bars on each side"),
        "htfcandle": lambda: lvl(f"the low / high of the last closed {n}-minute candle"),
    }[k]()


# ----------------------------------------------------------------------------- results
def load_replay(rdir, sym):
    """The replay's EA picks and every trade of both spans; asserts that no pick, model or worker file is missing."""
    lo = sym.lower()
    pk = json.load(open(os.path.join(rdir, f"{lo}_picks.json")))
    cells = [c for c in pk["cells"] if c["kind"] in EA_KINDS]
    picks = [q for c in cells for q in c["picks"]]
    pat = re.compile(rf"^{lo}_(pre|main)_w(\d+)of(\d+)_(picks\.csv|trades\.npz)$")
    files = {}
    for fn in sorted(os.listdir(rdir)):
        m = pat.match(fn)
        if m:
            files.setdefault((m.group(1), m.group(4)), []).append((int(m.group(2)), int(m.group(3)), fn))
    parts = []
    for span in ("pre", "main"):
        for what in ("picks.csv", "trades.npz"):
            ws = files.get((span, what), [])
            ns = {n for _, n, _ in ws}
            assert len(ns) == 1 and sorted(w for w, _, _ in ws) == list(range(next(iter(ns)))), f"{sym} {span} {what}: worker files {ws}"
        got = set()
        for _, _, fn in files[(span, "picks.csv")]:
            d = pd.read_csv(os.path.join(rdir, fn))
            got |= set(zip(d.key, d.model))
        want = {(q["key"], m) for q in picks for m in SYMS[sym]["models"]}
        assert want <= got, f"{sym} {span}: {len(want - got)} pick x model runs missing, e.g. {sorted(want - got)[:3]}"
        for _, _, fn in files[(span, "trades.npz")]:
            z = np.load(os.path.join(rdir, fn), allow_pickle=False)
            keys = np.array([str(k) for k in z["keys"]], dtype=object)
            mods = np.array([str(k) for k in z["models"]], dtype=object)
            pers = np.array([str(k) for k in z["periods"]] + ["none"], dtype=object)
            per = z["period"].astype(int); per[per < 0] = len(pers) - 1
            parts.append(pd.DataFrame(dict(key=keys[z["key"]], model=mods[z["model"]], engine=ENGINE_NAMES[z["engine"]],
                                           entry_ms=z["entry_ms"], exit_ms=z["exit_ms"], r=z["r"].astype(float), reason=z["reason"].astype(int),
                                           period=pers[per], span=span)))
    tr = pd.concat(parts, ignore_index=True)
    tr = tr[tr.key.isin({q["key"] for q in picks})]
    dup = tr.duplicated(["key", "model", "engine", "entry_ms"]).sum()
    assert dup == 0, f"{sym}: {dup} trades twice (overlapping worker files?)"
    return cells, tr


def stats(tr, keys, model, period, engine="tick"):
    g = tr[tr.key.isin(keys) & (tr.model == model) & (tr.period == period) & (tr.engine == engine)]
    return dict(n=int(len(g)), pf=pf(g.r.values), net_r=float(g.r.sum()))


def exits(tr, keys, period=None, model="vt"):
    """Replay trades (tick engine) of some picks: how many the trailing decided (closed at market by the trailing, reason 3, or
    stopped at a stop above the initial one: R > -0.999, as an initial-stop exit costs at least 1R) and how many a time rule
    closed (maximum hold, end of day, Friday: reasons 4-6)."""
    g = tr[tr.key.isin(keys) & (tr.model == model) & (tr.engine == "tick")]
    if period:
        g = g[g.period == period]
    trail = int(((g.reason == 3) | ((g.reason == 1) & (g.r > -0.999))).sum())
    return dict(n=int(len(g)), trail=trail, time=int(g.reason.isin([4, 5, 6]).sum()))


def to_csv(df, path, ints):
    """CSV with whole numbers as whole numbers (nullable Int64) and 4 decimals elsewhere."""
    df = df.copy()
    for c in ints:
        if c in df:
            df[c] = pd.to_numeric(df[c]).round().astype("Int64")
    df.to_csv(path, index=False, float_format="%.4f")


def results(rdirs):
    rows, best = [], []
    data = {}
    for sym, rdir in rdirs.items():
        cells, tr = load_replay(rdir, sym)
        data[sym] = (cells, tr)
        S = SYMS[sym]
        periods = S["earlier"] + ["calibration", "unseen"]
        for c in cells:
            if not c["picked"]:
                continue
            keys = [q["key"] for q in c["picks"]]
            for m in S["models"]:
                for per in periods:
                    t, y = stats(tr, keys, m, per, "tick"), stats(tr, keys, m, per, "1m")
                    rows.append(dict(symbol=sym, tf=c["tf"], trailing=c["kind"], trail_mode=MP.TRAIL_MODE[c["kind"]], setups=len(keys),
                                     model=m, period=per, tick_trades=t["n"], tick_pf=t["pf"], tick_net_r=t["net_r"],
                                     one_minute_trades=y["n"], one_minute_pf=y["pf"], one_minute_net_r=y["net_r"]))
        for tf in TFS:
            cand = []
            for c in cells:
                if c["tf"] != tf or not c["picked"]:
                    continue
                keys = [q["key"] for q in c["picks"]]
                u = stats(tr, keys, "vt", "unseen")
                cand.append(dict(trailing=c["kind"], setups=len(keys), trades=u["n"], pf=u["pf"], net_r=u["net_r"]))
            elig = [x for x in cand if x["trades"] >= MIN_N]
            thin = False
            if not elig:
                elig = [x for x in cand if x["trades"] >= THIN_N]
                thin = bool(elig)
            cand.sort(key=lambda x: (-(x["pf"] if not np.isnan(x["pf"]) else -1), -x["net_r"]))
            row = dict(symbol=sym, tf=tf, systems_with_setups=len(cand), eligible=len(elig), thin=thin,
                       candidates=cand, chosen=None)
            if elig:
                b = max(elig, key=lambda x: (x["pf"], x["net_r"]))
                c = next(c for c in cells if c["tf"] == tf and c["kind"] == b["trailing"])
                keys = [q["key"] for q in c["picks"]]
                ch = dict(trailing=b["trailing"], trail_mode=MP.TRAIL_MODE[b["trailing"]], setups=len(keys), keys=keys,
                          unseen=stats(tr, keys, "vt", "unseen"), unseen_stress=stats(tr, keys, "vt_stress", "unseen"),
                          unseen_one_minute=stats(tr, keys, "vt", "unseen", "1m"),
                          stored_one_minute=dict(n=c["stored"]["oos_n"], pf=c["stored"]["oos_pf"], stress_pf=c["stored"]["oos_stress_pf"]),
                          calibration=stats(tr, keys, "vt", "calibration"),
                          earlier={p: stats(tr, keys, "vt", p) for p in S["earlier"]},
                          earlier_stress={p: stats(tr, keys, "vt_stress", p) for p in S["earlier"]})
                if sym == "XAUUSD":
                    ch["unseen_dukascopy"] = stats(tr, keys, "duk_raw", "unseen")
                ch["held"] = all(ch["earlier"][p]["n"] > 0 and ch["earlier"][p]["pf"] >= HOLD_PF for p in S["earlier"])
                runner = [x for x in elig if x["trailing"] != b["trailing"]]
                ch["runner_up"] = max(runner, key=lambda x: (x["pf"], x["net_r"])) if runner else None
                ch["eligible_at_1_3"] = sum(1 for x in elig if x["pf"] >= 1.3)
                above = [x for x in cand if x["trades"] < (THIN_N if thin else MIN_N) and x["trades"] > 0 and x["pf"] > ch["unseen"]["pf"]]
                ch["higher_on_fewer_trades"] = sorted(above, key=lambda x: -x["pf"])
                ch["exits_2026"] = exits(tr, keys, "unseen")
                row["chosen"] = ch
            best.append(row)
    os.makedirs(OUT_RES, exist_ok=True)
    cells_df = pd.DataFrame(rows)
    to_csv(cells_df, os.path.join(OUT_RES, "tick_cells.csv"), ["trail_mode", "setups", "tick_trades", "one_minute_trades"])
    json.dump(dict(rule="research/results/tick/best_trailing_rule.md", min_trades=MIN_N, thin_trades=THIN_N, hold_pf=HOLD_PF,
                   note="'unseen' = 16 May - 13 Nov 2026: unseen when the setups were picked, but the trailing system of each timeframe "
                        "was chosen on these months, so for the chosen systems it is not a test. 'earlier' periods are the check.",
                   timeframes=best), open(os.path.join(OUT_RES, "best_by_timeframe.json"), "w"), indent=1, default=float)
    flat = []
    for b in best:
        ch = b["chosen"] or {}
        g = lambda k, f: (ch.get(k) or {}).get(f)
        row = dict(symbol=b["symbol"], tf=b["tf"], systems_with_setups=b["systems_with_setups"], eligible=b["eligible"], thin=b["thin"],
                   trailing=ch.get("trailing"), trail_mode=ch.get("trail_mode"), setups=ch.get("setups"),
                   chosen_on_2026_trades=g("unseen", "n"), chosen_on_2026_pf=g("unseen", "pf"), chosen_on_2026_net_r=g("unseen", "net_r"),
                   chosen_on_2026_stress_pf=g("unseen_stress", "pf"), chosen_on_2026_one_minute_pf=g("unseen_one_minute", "pf"),
                   chosen_on_2026_dukascopy_trades=g("unseen_dukascopy", "n"), chosen_on_2026_dukascopy_pf=g("unseen_dukascopy", "pf"),
                   study_one_minute_2026_pf=g("stored_one_minute", "pf"), picked_on_tick_pf=g("calibration", "pf"))
        for p in ("earlier", "2024", "2023"):
            e = (ch.get("earlier") or {}).get(p) or {}
            row[f"earlier_{COL[p]}_trades"] = e.get("n"); row[f"earlier_{COL[p]}_pf"] = e.get("pf")
        row.update(trailing_decided_2026=(ch.get("exits_2026") or {}).get("trail"), time_exits_2026=(ch.get("exits_2026") or {}).get("time"),
                   held=ch.get("held"), runner_up=(ch.get("runner_up") or {}).get("trailing"), runner_up_pf=(ch.get("runner_up") or {}).get("pf"),
                   runner_up_trades=(ch.get("runner_up") or {}).get("trades"))
        flat.append(row)
    fl = pd.DataFrame(flat)
    to_csv(fl, os.path.join(OUT_RES, "best_by_timeframe.csv"), ["systems_with_setups", "eligible", "trail_mode", "setups", "trailing_decided_2026",
                                                                 "time_exits_2026"] + [c for c in fl if c.endswith("_trades")])
    return best, data, cells_df


# ----------------------------------------------------------------------------- presets
def read_set(path):
    return dict(x.split("=", 1) for x in open(path, encoding="ascii").read().splitlines() if x and not x.startswith(";"))


def never_trails(p):
    """A fixed target at or before the trailing start (systems whose start is in R): the stop cannot move before the target."""
    return int(p["tp_mode"]) == 1 and p["trail_kind"] not in ("atr", "percent") and p["trail_start"] > 0 and p["trail_start"] >= p["tp_rr"] - 1e-9


def presets(best, data):
    shutil.rmtree(OUT_SETS, ignore_errors=True)
    rows = []
    for sym, S in SYMS.items():
        cells, tr = data[sym]
        btc = sym == "BTCUSD"
        sub = os.path.join(OUT_SETS, S["folder"]); os.makedirs(sub)
        magic = S["magic"]
        for b in [b for b in best if b["symbol"] == sym and b["chosen"]]:
            ch = b["chosen"]
            c = next(c for c in cells if c["tf"] == b["tf"] and c["kind"] == ch["trailing"])
            k_total = len(c["picks"])
            name = MP.TRAIL_NAME[ch["trailing"]]
            grp_u, grp_s = ch["unseen"], ch["unseen_stress"]
            grp_e = "; ".join(f"{PERIOD_TEXT[p]}, {v['n']} trades, PF {f2(v['pf'])}" for p, v in ch["earlier"].items())
            for k, q in enumerate(c["picks"], 1):
                p = dict(q["params"])
                assert p["tf"] == b["tf"] and p["trail_kind"] == ch["trailing"], (q["key"], p["tf"], p["trail_kind"])
                magic += 1
                side = MP.SIDE[p["sides"]]; sess = MP.SESS_NAME[p["session"]]; filt = p["htf"] if p["htf"] != "none" else "NoFilter"
                fname = f"Loma_BT_{S['tag']}_{p['tf']}_{name}_{k}of{k_total}_{side}_{sess}_{filt}"
                o = MP.ea_inputs(p, btc, magic, f"LOMA_B{p['tf']}{name[:4]}{k}")
                rr = round(p["tp_rr"] - 0.05, 2) if is_tie(p) else p["min_rr"]          # tick_replay.preset_rr
                assert abs(o["MinRewardRisk"] - rr) < 1e-9 and o["TrailMode"] == ch["trail_mode"], (q["key"], o["MinRewardRisk"], rr)
                t15 = os.path.join(ROOT, "presets", "trailing15", S["folder"], fname.replace("Loma_BT_", "Loma_T15_") + ".set")
                same_as = None
                if os.path.exists(t15):                            # the same setup in the gold / BTC zip
                    v15 = read_set(t15); vo = {n: str(o.get(n, v)) for n, v in MP.defaults()}
                    diff = [n for n in vo if n not in ("MagicNumber", "TradeComment") and str(v15.get(n)) != vo[n]]
                    assert not diff, (fname, diff)
                    same_as = os.path.basename(t15)[:-4]
                u, us = stats(tr, [q["key"]], "vt", "unseen"), stats(tr, [q["key"]], "vt_stress", "unseen")
                cal = stats(tr, [q["key"]], "vt", "calibration")
                ex_all = exits(tr, [q["key"]])
                e = {per: stats(tr, [q["key"]], "vt", per) for per in S["earlier"]}
                e_txt = "; ".join(f"{PERIOD_TEXT[per]}, {v['n']} trades, PF {f2(v['pf'])}" for per, v in e.items())
                trend = "none" if p["htf"] == "none" else f"{p['htf']} EMA {p['htf_ema']}"
                target = f"{p['tp_rr']:g}R" if p["tp_mode"] == 1 else "previous hump"
                held = ch["held"]
                replay = ("REPLAY ON BINANCE BTCUSDT ONE-SECOND PRICES (four price points per second; the EA's rules; 10 USD spread, no commission)"
                          if btc else "TICK REPLAY (every Dukascopy tick, the EA's rules; VT costs: VT's 0.15 spread scaled by Dukascopy's own spread, "
                          "0.60 USD commission per ounce)")
                head = [MP.plain(f"XAUUSD_Loma_TrendPullback v{MP.EA_VERSION} on {sym} - best trailing of {p['tf']}: {name} trailing "
                                 f"(TrailMode {ch['trail_mode']}), setup {k} of {k_total}: {side.lower()}, session {sess} server time, trend filter {trend}, "
                                 f"target {target}. " + ("DO NOT LOAD ON GOLD." if btc else "DO NOT LOAD ON BTC.")),
                        MP.plain(f"Trailing: {describe(p)}. Needs EA v1.35 or later (TrailMode {ch['trail_mode']}, TrailParam {int(p.get('trail_p', 0))})."
                                 + (f" Its trailing starts at or beyond its {target} target, so the stop never moves before the target: this setup's "
                                    "result comes from its stop, target and time exits." if never_trails(p) else "")),
                        *([MP.plain(f"Same setup as {same_as} in Loma_{'BTCUSD' if btc else 'XAUUSD'}_v1_35.zip (only the magic number and the "
                                    "trade comment differ): run one or the other, not both. Its Loma_T15 header gives the one-minute backtest's figures; "
                                    "the replay's are here.")] if same_as else []),
                        MP.plain(f"Picked on {PERIOD_TEXT['calibration']} only, by the one-minute backtest at the study's costs "
                                 f"({'10 USD spread' if btc else 'FTMO spread, no commission'}; score {q['is_score']:.2f}): "
                                 f"{q['stored']['is_n']} trades, PF {q['stored']['is_pf']:.2f}. Replay of the same months: {cal['n']} trades, PF {f2(cal['pf'])}."),
                        MP.plain(f"{replay}. {PERIOD_TEXT['unseen']} (the trailing was chosen on these months): this setup {u['n']} trades, "
                                 f"PF {f2(u['pf'])}, net {u['net_r']:+.1f}R (stressed PF {f2(us['pf'])}); the {k_total} setups of {p['tf']} + {name} together "
                                 f"{grp_u['n']} trades, PF {f2(grp_u['pf'])}, net {grp_u['net_r']:+.1f}R (stressed {f2(grp_s['pf'])})."),
                        MP.plain(f"{name} trailing with its own setups was chosen as the best on {p['tf']} (highest PF of the EA's trailing systems "
                                 + (f"with {MIN_N}+ trades in those months" if not b["thin"] else
                                    f"with {THIN_N}+ trades in those months: no system had {MIN_N} on {p['tf']}, a thin result")
                                 + "; each system has its own setups), so the 2026 figure is the score it was chosen by, not a test."
                                 + (f" Even so the set lost money in those months (PF {f2(grp_u['pf'])}): it is here only because the zip has the best "
                                    f"system of every timeframe." if grp_u["pf"] < 1.0 else "")),
                        MP.plain(f"EARLIER DATA, not used for any choice (same replay and costs): this setup: {e_txt}. The {k_total} setups together: {grp_e}. "
                                 + ("They held (PF 1.3 or more in every earlier period), but nothing here is proven: Strategy Tester and demo only."
                                    if held else "They did not hold (under 1.3): UNPROVEN, Strategy Tester and demo only.")),
                        *([MP.plain(f"Needs a spread near VT's 0.15 USD: at Dukascopy's own wider spreads the {k_total} setups took "
                                    f"{ch['unseen_dukascopy']['n']} of the {grp_u['n']} trades in those months, PF {f2(ch['unseen_dukascopy']['pf'])}.")]
                          if not btc else []),
                        *([MP.plain(f"In the replay this setup's trailing never decided an exit ({ex_all['n']} trades in all periods: "
                                    f"{ex_all['time']} closed by a time rule, the others at the target or the initial stop).")]
                          if ex_all["trail"] == 0 and not never_trails(p) else []),
                        *([MP.plain(f"Its target ({p['tp_rr']:g}R) equaled its minimum reward in the backtest; the preset sets MinRewardRisk "
                                    f"{rr:g} so the EA takes every such signal (the replay figures above are with this setting).")] if is_tie(p) else []),
                        ("Data: Binance BTCUSDT, broker server time. Points are 0.01 USD: 2000 points = 20 USD." if btc else
                         "Data: Dukascopy XAUUSD ticks, broker server time. Commission is in the figures: set CommissionPerLot to your round-trip commission per lot."),
                        "Times are BROKER SERVER TIME (New York + 7 h: GMT+2 in the US winter, GMT+3 in the US summer).",
                        "UseNewsFilter is on: on demo or live the EA skips entries within 30 minutes of high-impact USD news, which the replay did not "
                        "do (no effect in the Strategy Tester). Set it to false to trade exactly what was replayed."]
                MP.write_set(os.path.join(sub, fname + ".set"), head, o)
                rows.append(dict(file=fname, symbol=sym, timeframe=p["tf"], trailing=name, trail_mode=ch["trail_mode"], trail_param=int(p.get("trail_p", 0)),
                                 trailing_rule=describe(p), setup=f"{k} of {k_total}", direction=side.lower(), session=SESS[p["session"]],
                                 trend_filter=trend, target=target, min_reward_risk=o["MinRewardRisk"], target_equals_min_reward=is_tie(p),
                                 trailing_never_moves=never_trails(p), trailing_decided_exits_all_periods=ex_all["trail"],
                                 trades_all_periods=ex_all["n"], same_setup_as=same_as or "",
                                 picked_on_score=round(q["is_score"], 3), picked_on_trades=q["stored"]["is_n"], picked_on_pf=round(q["stored"]["is_pf"], 3),
                                 picked_on_replay_trades=cal["n"], picked_on_replay_pf=cal["pf"],
                                 chosen_on_2026_trades=u["n"], chosen_on_2026_pf=u["pf"], chosen_on_2026_net_r=u["net_r"], chosen_on_2026_stress_pf=us["pf"],
                                 **{f"earlier_{COL[per]}_trades": e[per]["n"] if per in e else None for per in ("earlier", "2024", "2023")},
                                 **{f"earlier_{COL[per]}_pf": e[per]["pf"] if per in e else None for per in ("earlier", "2024", "2023")},
                                 set_chosen_on_2026_trades=grp_u["n"], set_chosen_on_2026_pf=grp_u["pf"], set_chosen_on_2026_stress_pf=grp_s["pf"],
                                 set_held=held, set_thin=b["thin"], magic=magic, key=q["key"]))
    s = pd.DataFrame(rows)
    to_csv(s, os.path.join(OUT_SETS, "BEST_TRAILING_PRESETS.csv"), ["trail_mode", "trail_param", "magic"] + [c for c in s if c.endswith("_trades")])
    assert s.magic.is_unique and s.file.is_unique
    return s


def max_open(tr, keys):
    """Most positions open at the same time (replay, VT costs, every period): one EA instance per key."""
    g = tr[tr.key.isin(keys) & (tr.model == "vt") & (tr.engine == "tick")]
    if not len(g):
        return 0
    t = np.r_[g.entry_ms.values, g.exit_ms.values]
    d = np.r_[np.ones(len(g), int), -np.ones(len(g), int)]
    o = np.lexsort((d, t))                                   # an exit before an entry at the same millisecond
    return int(np.cumsum(d[o]).max())


def study_pooled(rdir, sym, cells):
    """The study's own stored one-minute trades of every EA pick (its costs), 2026 months: trades and PF."""
    z = np.load(os.path.join(rdir, f"{sym.lower()}_picks_trades.npz"))
    cut = np.datetime64("2026-05-16T03:00").astype("datetime64[m]").astype(np.int64)        # hump_tf_recal.IS_END
    r = np.concatenate([z[q["key"] + ":base_r"][z[q["key"] + ":base_t"].astype(np.int64) >= cut] for c in cells for q in c["picks"]])
    return len(r), pf(r)


# ----------------------------------------------------------------------------- guide
def guide(best, data, sets, rdirs):
    def rng(v):
        return f"{min(v):.2f} to {max(v):.2f}" if len(v) > 1 else f"{v[0]:.2f}"
    chosen = [b for b in best if b["chosen"]]
    held = [b for b in chosen if b["chosen"]["held"]]
    lost = [b for b in chosen if b["chosen"]["unseen"]["pf"] < 1.0]
    sym_name = {"XAUUSD": "gold", "BTCUSD": "BTC"}
    n_g = sum(1 for b in chosen if b["symbol"] == "XAUUSD"); n_b = len(chosen) - n_g
    eg = [b["chosen"]["earlier"]["earlier"]["pf"] for b in chosen if b["symbol"] == "XAUUSD"]
    e23 = [b["chosen"]["earlier"]["2023"]["pf"] for b in chosen if b["symbol"] == "BTCUSD"]
    e24 = [b["chosen"]["earlier"]["2024"]["pf"] for b in chosen if b["symbol"] == "BTCUSD"]
    if held:
        held_txt = (f"{len(held)} of the {len(chosen)} chosen sets held there (profit factor 1.3 or more in every earlier period): "
                    + ", ".join(f"{sym_name[b['symbol']]} {b['tf']} {SYSTEM[b['chosen']['trailing']]}" for b in held))
    else:
        held_txt = (f"none of the {len(chosen)} chosen sets held there (held = profit factor 1.3 or more in every earlier period). "
                    + (f"Every gold set lost money from 15 Jul to 31 Dec 2024 ({rng(eg)}). " if max(eg) < 1 else f"Gold sets: {rng(eg)}. ")
                    + (f"Every BTC set lost money in 2023 ({rng(e23)}); " if max(e23) < 1 else f"BTC sets in 2023: {rng(e23)}; ")
                    + f"in 2024 the BTC sets made {rng(e24)}")
    dup = sets[sets.same_setup_as != ""]
    dup_sets = sorted({(r.symbol, r.timeframe) for r in dup.itertuples()}, key=lambda x: (x[0], TFS.index(x[1])))
    never = sets[sets.trailing_never_moves]
    never_replay = sets[(sets.trailing_decided_exits_all_periods == 0) & ~sets.trailing_never_moves]
    rare = [b for b in chosen if b["chosen"]["exits_2026"]["trail"] < 0.1 * b["chosen"]["exits_2026"]["n"]]
    lost_presets = sets[sets.chosen_on_2026_pf < 1.0]
    lost_in_good = lost_presets[lost_presets.set_chosen_on_2026_pf >= 1.0]
    # the replay against the one-minute engine: pooled, per system and timeframe, per chosen set
    tick_vs, per_cell, per_set = [], [], []
    chosen_cells = {(b["symbol"], b["tf"], b["chosen"]["trailing"]) for b in chosen}
    for sym in SYMS:
        cells, tr = data[sym]
        for per in ("unseen", "calibration") + tuple(SYMS[sym]["earlier"]):
            g = tr[(tr.model == "vt") & (tr.period == per)]
            t, y = g[g.engine == "tick"].r.values, g[g.engine == "1m"].r.values
            tick_vs.append((sym, per, len(t), pf(t), t.sum(), len(y), pf(y), y.sum()))
        for c in cells:
            keys = [q["key"] for q in c["picks"]]
            for per in ("unseen", "calibration") + tuple(SYMS[sym]["earlier"]):
                t, y = stats(tr, keys, "vt", per), stats(tr, keys, "vt", per, "1m")
                if t["n"] >= THIN_N and y["n"] >= THIN_N and np.isfinite(t["pf"]) and np.isfinite(y["pf"]):
                    x = (t["pf"] - y["pf"], sym, c["tf"], c["kind"], per, y["pf"], t["pf"])
                    per_cell.append(x)
                    if (sym, c["tf"], c["kind"]) in chosen_cells:
                        per_set.append(x)
    dpf = [py - pt for _, _, _, pt, _, _, py, _ in tick_vs]
    lo_c, hi_c, lo_s, hi_s = min(per_cell), max(per_cell), min(per_set), max(per_set)
    st_n, st_pf = study_pooled(rdirs["XAUUSD"], "XAUUSD", data["XAUUSD"][0])
    gold_tick_2026 = next(x for x in tick_vs if x[0] == "XAUUSD" and x[1] == "unseen")
    ov = {sym: max_open(data[sym][1], list(sets[sets.symbol == sym].key)) for sym in SYMS}
    ov_tf = {(sym, tf): max_open(data[sym][1], list(sets[(sets.symbol == sym) & (sets.timeframe == tf)].key)) for sym in SYMS for tf in TFS
             if len(sets[(sets.symbol == sym) & (sets.timeframe == tf)])}
    top = max(ov_tf.items(), key=lambda x: x[1])
    gch = [b for b in chosen if b["symbol"] == "XAUUSD"]
    duk_share = sum(b["chosen"]["unseen_dukascopy"]["n"] for b in gch) / max(1, sum(b["chosen"]["unseen"]["n"] for b in gch))
    n_sets_g, n_sets_b = int((sets.symbol == "XAUUSD").sum()), int((sets.symbol == "BTCUSD").sum())
    cellname = lambda x: f"{sym_name[x[1]]} {x[2]} {SYSTEM[x[3]]}, {PERIOD_TEXT[x[4]]}: {x[5]:.2f} to {x[6]:.2f}"

    def table(sym):
        S = SYMS[sym]
        ep = S["earlier"]
        cols = (["Timeframe", "Best trailing (TrailMode)", "Presets", "16 May – 13 Nov 2026, chosen on it: PF (trades)", "Stressed",
                 "One-minute engine, same prices and costs", "Trailing decided (2026)"]
                + (["At Dukascopy's own spreads: PF (trades)"] if sym == "XAUUSD" else [])
                + [f"{PERIOD_TEXT[p]}: PF (trades)" for p in ep] + ["Runner-up among the eligible: PF (trades)"])
        out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
        for b in [b for b in best if b["symbol"] == sym]:
            ch = b["chosen"]
            if not ch:
                why = ("no setup of the EA's systems passed the calibration" if not b["systems_with_setups"] else
                       f"no system with {THIN_N} or more trades in the 2026 months")
                out.append(f"| {b['tf']} | none: {why} |" + " – |" * (len(cols) - 2))
                continue
            ru, ex = ch["runner_up"], ch["exits_2026"]
            cells_ = [b["tf"], f"{SYSTEM[ch['trailing']]} ({ch['trail_mode']})" + (", thin" if b["thin"] else ""), str(ch["setups"]),
                      f"{f2(ch['unseen']['pf'])} ({ch['unseen']['n']})" + (", lost" if ch["unseen"]["pf"] < 1.0 else ""),
                      f2(ch["unseen_stress"]["pf"]), f2(ch["unseen_one_minute"]["pf"]), f"{ex['trail']} of {ex['n']}"]
            if sym == "XAUUSD":
                cells_.append(f"{f2(ch['unseen_dukascopy']['pf'])} ({ch['unseen_dukascopy']['n']})")
            cells_ += [f"{f2(ch['earlier'][p]['pf'])} ({ch['earlier'][p]['n']})" for p in ep]
            cells_.append(f"{SYSTEM[ru['trailing']]} {f2(ru['pf'])} ({ru['trades']})" if ru else "none: no other eligible system")
            out.append("| " + " | ".join(cells_) + " |")
        return out

    L = [f"# Loma EA v{MP.EA_VERSION}: the best trailing system per timeframe (tick replay), start here", "",
         f"`XAUUSD_Loma_TrendPullback.mq5` v{MP.EA_VERSION} (the same file as in the gold and BTC zips) with one set of presets per timeframe. "
         f"On each timeframe the set is the trailing system whose own setups made the highest profit factor in the 2026 months, among those with "
         f"at least {MIN_N} trades there (at least {THIN_N} where none had {MIN_N}), when the re-calibration's setups were replayed with the EA's "
         "own rules on every tick (gold) or every second (BTC). Each trailing system was calibrated with its own setups (no two share one), so "
         "this compares setups and trailing together, not trailing systems on the same trades. "
         f"{n_g} gold and {n_b} BTC timeframes have a set ({len(sets)} presets). "
         "**The file names say Gold or BTC: do not load gold presets on BTC or BTC presets on gold.**", "",
         "> **Nothing in this zip is proven. Strategy Tester and demo only.**",
         "> - Each timeframe's set was chosen by its result in the 2026 months (16 May – 13 Nov), which its setups had not seen. That makes the "
         "2026 figure the score it was chosen by, not a test, and the best of up to 14 systems is flattered by the choice.",
         f"> - The check is the earlier data, which played no part in any choice (gold: 15 Jul – 31 Dec 2024; BTC: 2023 and 2024): {held_txt}."]
    if lost:
        L += [f"> - On {len(lost)} timeframes even the best set lost money in the 2026 months it was chosen on: "
              + ", ".join(f"{sym_name[b['symbol']]} {b['tf']} ({f2(b['chosen']['unseen']['pf'])})" for b in lost)
              + ". They are here only because the zip has one set per timeframe."]
    if rare:
        parts = [f"{b['chosen']['exits_2026']['trail']} of {sym_name[b['symbol']]} {b['tf']}'s {b['chosen']['exits_2026']['n']} trades" for b in rare]
        L += ["> - On some sets the trailing rarely decides a trade: in the 2026 months it decided "
              + (", ".join(parts[:-1]) + " and " + parts[-1] if len(parts) > 1 else parts[0])
              + ". Their results come mostly from the entries, the stop, the target and the time exits."]
    if dup_sets:
        L += [f"> - {len(dup_sets)} of the {len(chosen)} sets ({len(dup)} presets: "
              + ", ".join(f"{sym_name[s]} {tf}" for s, tf in dup_sets)
              + ") are the same setups as `Loma_T15` presets of the gold and BTC zips, with other magic numbers. Load one or the other, not both, "
              "or every trade is taken twice."]
    L += [f"> - The gold figures assume VT's narrow spread (about $0.15) and $0.60 commission per ounce. At Dukascopy's own wider spreads only "
          f"{duk_share:.0%} of the gold sets' 2026 trades were taken and their profit factors moved (column *At Dukascopy's own spreads*).",
          "> - The EA v1.35 has not been compiled or run in MetaTrader yet: its trailing systems were checked only in a simulated terminal (see "
          "*Checks of the replay*). If the compiler reports anything, send the log.", ""]
    L += ["## How it was measured", "",
          "- **The setups** are the re-calibration's picks (November 2026): for every timeframe and trailing system, up to 10 setups chosen on "
          "1 Jan 2025 – 15 May 2026 only, one per direction, session and trend filter, each with a score of 1.3 or more (score = its lowest "
          "profit factor in three parts of those months, Jan – Jun 2025, Jul – Dec 2025 and Jan – 15 May 2026, at normal and at stressed costs, "
          "with at least 20 trades in each part). No setup of the EA's 14 trailing systems passed on M1 or H1, for gold or BTC, so they have no presets.",
          "- **The replay** runs every setup with the EA's execution rules: entry on the first price of the entry minute at the ask (buys) or the "
          "bid (sells) after the spread check; stop and target checked on every price, a stop filled at that price (worse on a gap); the trailing "
          "systems updated as the EA does (TrailMode 0 and 4 on every price, moving the stop only when it gains at least `TrailStep_Points`, "
          "TrailMode 4 in steps of `TrailStartR` x R; the others once per closed one-minute bar); the time exits, the Friday close (gold) and one "
          "position per preset. Gold: every Dukascopy tick. BTC: Binance BTCUSDT one-second prices, four points per second (open, the extreme "
          "nearer the open, the other extreme, close; on 33 of the 68 BTC combinations of timeframe and system, Jan 2025 – Nov 2026, the other "
          "order changes 1 of 12,310 trades).",
          "- **Checks of the replay.** The EA's code (translated from the MQL5 source and run in a simulated terminal) took the same trades on "
          "samples of setups covering every TrailMode: gold, 33 setups on Dukascopy's prices of Sep – Oct 2024 with VT's constant 0.15 spread, "
          "470 of 470 trades identical in entry, stop, target, stop moves, exit and result; BTC, 32 setups on 16 May – 16 Aug 2026, 804 of 804. "
          "The gold figures use a spread that varies with Dukascopy's; that part was not in the EA check. An independent re-trace from the ticks "
          "of the final 15 Jul – 31 Dec 2024 gold run agreed on 25,383 of the 25,399 trades it compared (the 6 still open at the end of 2024 were "
          "left out): 16 sells with a previous-hump target differ, 15 of them reaching the target a moment earlier or later (R within 0.02) and "
          "one leaving at its stop instead, and one trade is only in the re-trace; none of them is in the chosen sets. BTC's one-minute trades "
          "equal the study's stored trades in 326 of 326 runs.",
          "- **Gold costs (VT):** Dukascopy's mid price with VT Markets' 0.15 spread, scaled by Dukascopy's own spread so its spikes stay, and $0.60 "
          "commission per ounce. **Stressed:** one minute late, $0.10 slippage, $0.67 commission. The presets refuse an entry above a $0.60 spread.",
          "- **BTC costs:** a constant $10 spread (the presets accept up to $30), no commission. **Stressed:** one minute late, $3 slippage, $2 "
          "commission per BTC.",
          f"- **The choice** follows a rule written down before the full replay ran (`BEST_TRAILING_RULE.md`): on each timeframe, among the EA's "
          f"trailing systems with at least {MIN_N} trades in the 2026 months (at least {THIN_N} where none had {MIN_N}: marked thin), the "
          "highest profit factor at VT costs. For gold no 2026 replay result existed before the rule. For BTC a test run with every setup's 2026 "
          "result had already been computed (only its M10 and M15 rows had been looked at), and an earlier replay of four BTC combinations "
          "(among them M2 ATR at entry, the later M2 choice) too, so for BTC the timing does not protect the choice. "
          "**Held** = profit factor 1.3 or more in every earlier period.", ""]
    L += ["## Gold (XAUUSD)", ""] + table("XAUUSD") + ["", "## BTC (BTCUSD)", ""] + table("BTCUSD") + [""]
    few = [(b["symbol"], b["tf"], b["chosen"]) for b in chosen if b["chosen"]["higher_on_fewer_trades"]]
    L += ["- PF = profit factor (gross wins / gross losses), all the setups of a timeframe's set together. R = a trade's initial risk (entry "
          "to stop): a 1.5R target is 1.5 times the risk, and net +4.1R is 4.1 times one trade's risk. *lost* = the set lost money in the months "
          "it was chosen on.",
          "- *One-minute engine, same prices and costs*: the study's one-minute backtest run on the same prices, for comparison with the replay. "
          "*Trailing decided*: trades the trailing closed, at market or at a stop it had moved (at least that many).",
          f"- Eligible = at least {MIN_N} trades in the 2026 months (at least {THIN_N} on a thin timeframe: gold M30). The runner-up column "
          "leaves out the others too. Some of them had a higher profit factor than the chosen set on fewer trades: "
          + "; ".join(f"{sym_name[s]} {tf} (chosen {f2(ch['unseen']['pf'])}): "
                      + ", ".join(f"{SYSTEM[x['trailing']]} "
                                  + (f"{x['pf']:.3f} against {ch['unseen']['pf']:.3f}" if f2(x["pf"]) == f2(ch["unseen"]["pf"]) else f2(x["pf"]))
                                  + f" ({x['trades']})" for x in ch["higher_on_fewer_trades"])
                      for s, tf, ch in few) + "."]
    if len(never) or len(never_replay):
        L += ["- The trailing never decided an exit of "
              + ", ".join(f"`{r.file}`" for r in list(never.itertuples()) + list(never_replay.itertuples()))
              + (f": in the first the trailing starts at or beyond the fixed target, so the stop cannot move before the target; in the others "
                 "it never came into play in the replay (most of their trades end at their time limit). Their results come from the stop, the "
                 "target and the time exits." if len(never) and len(never_replay) else
                 ": the trailing starts at or beyond the fixed target, so the stop cannot move before the target." if len(never) else
                 ": it never came into play in the replay; their results come from the stop, the target and the time exits.")]
    L += [f"- {len(lost_presets)} of the {len(sets)} presets lost money on their own in the 2026 months, {len(lost_in_good)} of them in sets that "
          "made money. A set's figure needs all its presets: dropping the losers would be one more choice made on those months.",
          "- Every preset's header gives its own figures. `BEST_TRAILING_PRESETS.csv` lists them all, `BEST_TRAILING_BY_TIMEFRAME.csv` the "
          "choice of every timeframe, and `TICK_REPLAY_ALL_CELLS.csv` every trailing system that has setups on a timeframe "
          f"({sum(1 for sym in SYMS for c in data[sym][0] if c['picked'])} of the {sum(len(data[sym][0]) for sym in SYMS)} combinations of "
          "symbol, timeframe and system; the others had no setup), with every period and cost model, replay and one-minute engine.",
          "- CSV names. Models: `vt` = VT costs (gold) or the $10 spread (BTC), `vt_stress` = stressed, `duk_raw` = Dukascopy's own bid and ask "
          "with $0.60 commission (gold). Periods: `earlier` and `earlier_2024h2_*` = 15 Jul – 31 Dec 2024 (gold), `2023` (from 15 Jan) and "
          "`2024` (BTC), `calibration` and `picked_on_*` = 1 Jan 2025 – 15 May 2026 (the setups were picked on it), `unseen` and "
          "`chosen_on_2026_*` = 16 May – 13 Nov 2026 (the trailing was chosen on it). `tick_*` = the replay (BTC: one-second prices), "
          "`one_minute_*` = the one-minute engine on the same prices; `picked_on_score`, `picked_on_trades`, `picked_on_pf` and "
          "`study_one_minute_2026_pf` = the study's own one-minute figures at its costs (gold: FTMO spread, no commission); `picked_on_replay_*` "
          "and `picked_on_tick_pf` = the replay of the calibration months; `runner_up*` = the best other eligible system. Systems: `R` = risk "
          "multiples, `atr` = ATRentry = ATR at entry, `percent`, `profitlock`, `step` = stepped, `chandelier`, `candles` = candle lows / highs, "
          "`ema`, `sma`, `psar` = Parabolic SAR, `bollinger`, `htfcandle` = higher-timeframe candle, `pivots` = swing pivots, `hump` = hump "
          "structure.", ""]
    L += ["## The replay against the one-minute backtest", "",
          f"All the setups of the EA's 14 systems pooled, VT costs. The replay takes almost the same trades as the one-minute engine on the same "
          f"prices and costs, and its pooled profit factor is {min(dpf):.3f} to {max(dpf):.3f} lower. For the setups of one system on one "
          f"timeframe and period (at least {THIN_N} trades) the difference runs from {-lo_c[0]:.2f} lower ({cellname(lo_c)}) to {hi_c[0]:.2f} "
          f"higher ({cellname(hi_c)}"
          + (", not in this zip" if (hi_c[1], hi_c[2], hi_c[3]) not in chosen_cells else "")
          + f"); for the {len(chosen)} sets in this zip, from {-lo_s[0]:.2f} lower to {hi_s[0]:.2f} higher ({cellname(hi_s)}). "
          f"The study's own gold figures were at FTMO's spread without commission, and higher: all its gold setups together made {st_pf:.2f} in "
          f"the 2026 months ({st_n:,} trades) against {gold_tick_2026[3]:.2f} in the replay at VT costs, so for gold most of the drop comes from "
          "VT's costs, not from the ticks.", "",
          "| Symbol | Period | Replay: trades, PF, net | One-minute engine: trades, PF, net |", "|---|---|---|---|"]
    for sym, per, nt, pt, st, ny, py, sy in tick_vs:
        lab = PERIOD_TEXT[per] + (" (the setups were picked on it)" if per == "calibration" else "")
        L.append(f"| {sym} | {lab} | {nt:,}, {f2(pt)}, {st:+,.0f}R | {ny:,}, {f2(py)}, {sy:+,.0f}R |")
    t15_rows, t15_early, t15_hold, gold_vt_zip = [], [], 0, []
    for sym in SYMS:
        cells, tr = data[sym]
        for c15 in json.load(open(os.path.join(ROOT, "research", "results", "recal", f"{sym.lower()}_successful_trailing.json")))["combinations"]:
            c = next(c for c in cells if c["tf"] == c15["timeframe"] and c["kind"] == c15["trailing"])
            keys = [q["key"] for q in c["picks"]]
            u, us, y = stats(tr, keys, "vt", "unseen"), stats(tr, keys, "vt_stress", "unseen"), stats(tr, keys, "vt", "unseen", "1m")
            es = {p: stats(tr, keys, "vt", p) for p in SYMS[sym]["earlier"]}
            t15_early += [v["pf"] for v in es.values()]
            t15_hold += u["pf"] >= 1.3
            if sym == "XAUUSD":
                gold_vt_zip.append((c15["timeframe"], SYSTEM[c15["trailing"]], c15["vt_unseen_pf"], c15["vt_unseen_trades"], y["pf"], u["pf"]))
            t15_rows.append(f"| {sym} | {c15['timeframe']} | {SYSTEM[c15['trailing']]} | {c15['unseen_pf']:.2f} ({c15['unseen_trades']}) | "
                            f"{f2(y['pf'])} ({y['n']}) | {f2(u['pf'])} ({u['n']}) | {f2(us['pf'])} | "
                            + "; ".join(f"{PERIOD_TEXT[p]}: {f2(v['pf'])} ({v['n']})" for p, v in es.items()) + " |")
    L += ["", "## The 15 earlier trailing results, re-measured", "",
          "The combinations of timeframe and trailing system that had reached a profit factor of 1.3 on the 2026 months in the one-minute "
          "backtest (the `Loma_T15` presets of the gold and BTC zips). They were selected on these same months, so this is a re-measurement, not "
          f"a test: {t15_hold} of the 15 stay at 1.3 or more in the replay. On the earlier data none of the 15 reaches 1.3 in the replay "
          f"(highest {max(t15_early):.2f}).", "",
          "| Symbol | Timeframe | Trailing | 2026, study (one minute, its costs): PF (trades) | 2026, one-minute engine on the replay's prices at "
          "VT costs: PF (trades) | 2026, replay at VT costs: PF (trades) | Stressed | Earlier data, replay: PF (trades) |",
          "|---|---|---|---|---|---|---|---|"] + t15_rows
    L += ["", "- The study's costs: gold FTMO spread and no commission, BTC a $10 spread (the same as the BTC VT costs).",
          "- The gold zip and its presets give these four gold combinations at VT's costs as "
          + ", ".join(f"{tf} {nm} {v:.2f} ({n})" for tf, nm, v, n, _, _ in gold_vt_zip)
          + ": that was the study's one-minute backtest on its own price file with VT's constant spread. On the replay's prices, with the spread "
          "scaled by Dukascopy's, the one-minute engine gives " + ", ".join(f"{f2(y)}" for *_, y, _ in gold_vt_zip)
          + " and the replay " + ", ".join(f"{f2(u)}" for *_, u in gold_vt_zip) + ".", "",
          "## How to run the presets", "",
          "- **One timeframe's set is one result:** its setups were tested together, each as its own EA with one position. Run them together on "
          "one **hedging** account (on a netting account the presets on one symbol share one position).",
          f"- **Overlap and risk:** in the replay the most positions open at once were "
          + ", ".join(f"{sym_name[sym]} {tf}: {n}" for (sym, tf), n in ov_tf.items())
          + f". Each preset has `RiskPercent=0.5`, so one set alone can have up to {0.5 * top[1]:.1f}% at risk at once ({sym_name[top[0][0]]} "
          f"{top[0][1]}: {top[1]} presets). All gold sets together had up to {ov['XAUUSD']} positions open in the replay "
          f"({0.5 * ov['XAUUSD']:.1f}%) and all BTC sets {ov['BTCUSD']} ({0.5 * ov['BTCUSD']:.1f}%), but the {n_sets_g} gold presets can hold "
          f"{0.5 * n_sets_g:.1f}% at once and the {n_sets_b} BTC presets {0.5 * n_sets_b:.1f}%. Lower `RiskPercent` (for example to 0.1) when you "
          "run a whole set or several sets. On BTC a lower `RiskPercent` needs a larger deposit before the 0.01 minimum lot fits a stop.",
          "- **Gold commission:** the figures include $0.60 per ounce. Set `CommissionPerLot` to your round-trip commission per lot in the account "
          "currency, so a stop-out costs `RiskPercent` including commission.",
          "- **BTC:** points are 0.01 USD (`AutoScalePoints=true`); `MaxSpread_Points=3000` ($30), `TrailStep_Points=200` ($2), no weekend close. "
          "BTC stops are wide (hundreds of dollars): with a 0.01 minimum lot a trade is skipped when the equity is too small for its stop "
          "(`SkipIfBelowMinLot=true`); test with a large deposit first.",
          "- **Server time:** sessions and the end-of-day close are broker server time (New York + 7 h: GMT+2 in the US winter, GMT+3 in the US "
          "summer), the clock of VT Markets and FTMO.",
          "- **News filter:** `UseNewsFilter` is on, as in the other presets: on demo or live the EA skips entries within 30 minutes of high-impact "
          "USD news (BTC too), which the replay did not do. It does nothing in the Strategy Tester. Set it to false to trade exactly what was "
          "replayed.", "",
          "## If you want to test it", "",
          "1. **Strategy Tester:** \"Every tick based on real ticks\" on your broker's symbol. The figures assume the replay's costs: for gold a "
          "spread near VT's $0.15 and $0.60 commission per ounce, for BTC a $10 spread and no commission; with other costs expect other trades "
          "and figures. The tester runs one preset at a time: run each preset of a timeframe's set on its own, over 16 May – 13 Nov 2026 and over "
          "the earlier period, compare each run with its preset's header, and add the set's runs up to compare with the tables above. In the "
          "tester the Load dialog usually opens in `MQL5\\Profiles\\Tester`; browse to `MQL5\\Presets`.",
          "2. **Then demo.** A tester run that matches shows that the EA trades its backtest, not that the edge is real.", "",
          "## What is in the zip", "", "| File | What it is |", "|---|---|",
          f"| `MQL5/Experts/XAUUSD_Loma_TrendPullback.mq5` | The EA, v{MP.EA_VERSION}. |",
          "| `MQL5/Include/EVK/EVK.mqh` | Records trades in the Strategy Tester only (EA Validation Kit). The EA needs it to compile. |",
          f"| `MQL5/Presets/Loma_BT_Gold_*.set` | {n_sets_g} gold presets: every setup of each gold timeframe's best system. |",
          f"| `MQL5/Presets/Loma_BT_BTC_*.set` | {n_sets_b} BTC presets: every setup of each BTC timeframe's best system. |",
          "| `BEST_TRAILING_RULE.md` | The rule of the choice, as written before the full replay ran, with a note added after an independent check. |",
          "| `BEST_TRAILING_BY_TIMEFRAME.csv` | The choice of every timeframe, with its runner-up and the earlier-data check. |",
          "| `BEST_TRAILING_PRESETS.csv` | Every preset with its figures. |",
          "| `TICK_REPLAY_ALL_CELLS.csv` | Every trailing system that has setups on a timeframe: each period and cost model, replay and one-minute engine. |", "",
          "## Install", "",
          "1. In MT5 choose **File > Open Data Folder**.",
          "2. Copy the zip's `MQL5` folder over the data folder's `MQL5` folder.",
          "3. In MetaEditor open `MQL5/Experts/XAUUSD_Loma_TrendPullback.mq5` and press **F7** (compile). If the compiler reports anything, send "
          "the log rather than editing the file.",
          "4. Attach the EA to an XAUUSD or BTCUSD chart (any timeframe: it reads its own from the preset). In **Inputs** click **Load** and pick a "
          "preset of that symbol.",
          "5. Enable **Algo Trading**.", ""]
    os.makedirs(os.path.dirname(GUIDE), exist_ok=True)
    open(GUIDE, "w", encoding="utf-8").write("\n".join(L))
    return GUIDE


# ----------------------------------------------------------------------------- zip
def make_zip(sets):
    ver = MP.EA_VERSION
    name = f"Loma_BestTrailing_v{ver.replace('.', '_')}"
    build = os.path.join(DIST, "_build_bt")
    root = os.path.join(build, name)
    shutil.rmtree(build, ignore_errors=True)
    for d in ("MQL5/Experts", "MQL5/Include/EVK", "MQL5/Presets"):
        os.makedirs(os.path.join(root, d))
    shutil.copy(MP.EA, os.path.join(root, "MQL5/Experts", os.path.basename(MP.EA)))
    shutil.copy(os.path.join(ROOT, "EVK/MQL5/Include/EVK/EVK.mqh"), os.path.join(root, "MQL5/Include/EVK/EVK.mqh"))
    n = 0
    for sub in ("gold", "btc"):
        for f in sorted(os.listdir(os.path.join(OUT_SETS, sub))):
            if f.endswith(".set"):
                head = open(os.path.join(OUT_SETS, sub, f), encoding="ascii").readline()
                assert f"v{ver}" in head, (f, head)
                shutil.copy(os.path.join(OUT_SETS, sub, f), os.path.join(root, "MQL5/Presets", f)); n += 1
    assert n == len(sets), (n, len(sets))
    g = open(GUIDE, encoding="utf-8").read()
    assert f"v{ver}" in g.splitlines()[0]
    shutil.copy(GUIDE, os.path.join(root, "START_HERE.md"))
    shutil.copy(os.path.join(ROOT, "research", "results", "tick", "best_trailing_rule.md"), os.path.join(root, "BEST_TRAILING_RULE.md"))
    shutil.copy(os.path.join(OUT_RES, "best_by_timeframe.csv"), os.path.join(root, "BEST_TRAILING_BY_TIMEFRAME.csv"))
    shutil.copy(os.path.join(OUT_SETS, "BEST_TRAILING_PRESETS.csv"), os.path.join(root, "BEST_TRAILING_PRESETS.csv"))
    shutil.copy(os.path.join(OUT_RES, "tick_cells.csv"), os.path.join(root, "TICK_REPLAY_ALL_CELLS.csv"))
    z = os.path.join(DIST, name + ".zip")
    if os.path.exists(z):
        os.remove(z)
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as f:
        for dp, _, fs in sorted(os.walk(root)):
            for fn in sorted(fs):
                full = os.path.join(dp, fn)
                f.write(full, os.path.relpath(full, build))
    shutil.rmtree(build)
    print(z)
    for i in zipfile.ZipFile(z).infolist():
        print(f"  {i.file_size:9d}  {i.filename}")
    return z


if __name__ == "__main__":
    if sys.argv[1] == "all":
        rd = {"XAUUSD": sys.argv[2], "BTCUSD": sys.argv[3]}
        best, data, cells_df = results(rd)
        sets = presets(best, data)
        guide(best, data, sets, rd)
        make_zip(sets)
        pd.set_option("display.width", 250)
        print(pd.read_csv(os.path.join(OUT_RES, "best_by_timeframe.csv")).round(3).to_string(index=False))
