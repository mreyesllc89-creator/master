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
PERIOD_TEXT = {"earlier": "Jul 15 - Dec 31 2024", "2023": "2023 (from Jan 15)", "2024": "2024",
               "calibration": "Jan 2025 - May 15 2026", "unseen": "May 16 - Nov 13 2026"}
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
        "candles": lambda: lvl(f"the low / high of the last {n} closed {tf} candles"),
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
                                           entry_ms=z["entry_ms"], exit_ms=z["exit_ms"], r=z["r"].astype(float), period=pers[per], span=span)))
    tr = pd.concat(parts, ignore_index=True)
    tr = tr[tr.key.isin({q["key"] for q in picks})]
    dup = tr.duplicated(["key", "model", "engine", "entry_ms"]).sum()
    assert dup == 0, f"{sym}: {dup} trades twice (overlapping worker files?)"
    return cells, tr


def stats(tr, keys, model, period, engine="tick"):
    g = tr[tr.key.isin(keys) & (tr.model == model) & (tr.period == period) & (tr.engine == engine)]
    return dict(n=int(len(g)), pf=pf(g.r.values), net_r=float(g.r.sum()))


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
                row["chosen"] = ch
            best.append(row)
    os.makedirs(OUT_RES, exist_ok=True)
    cells_df = pd.DataFrame(rows)
    cells_df.to_csv(os.path.join(OUT_RES, "tick_cells.csv"), index=False, float_format="%.4f")
    json.dump(dict(rule="research/results/tick/best_trailing_rule.md", min_trades=MIN_N, thin_trades=THIN_N, hold_pf=HOLD_PF,
                   timeframes=best), open(os.path.join(OUT_RES, "best_by_timeframe.json"), "w"), indent=1, default=float)
    flat = []
    for b in best:
        ch = b["chosen"] or {}
        e = {f"earlier_{COL[p]}_{'trades' if k == 'n' else k}": ch.get("earlier", {}).get(p, {}).get(k) for p in SYMS[b["symbol"]]["earlier"] for k in ("n", "pf")}
        flat.append(dict(symbol=b["symbol"], tf=b["tf"], systems_with_setups=b["systems_with_setups"], eligible=b["eligible"], thin=b["thin"],
                         trailing=ch.get("trailing"), trail_mode=ch.get("trail_mode"), setups=ch.get("setups"),
                         unseen_trades=ch.get("unseen", {}).get("n"), unseen_pf=ch.get("unseen", {}).get("pf"),
                         unseen_net_r=ch.get("unseen", {}).get("net_r"), unseen_stress_pf=ch.get("unseen_stress", {}).get("pf"),
                         unseen_one_minute_pf=ch.get("unseen_one_minute", {}).get("pf"), stored_one_minute_pf=ch.get("stored_one_minute", {}).get("pf"),
                         calibration_pf=ch.get("calibration", {}).get("pf"), **e, held=ch.get("held"),
                         runner_up=(ch.get("runner_up") or {}).get("trailing"), runner_up_pf=(ch.get("runner_up") or {}).get("pf")))
    pd.DataFrame(flat).to_csv(os.path.join(OUT_RES, "best_by_timeframe.csv"), index=False, float_format="%.4f")
    return best, data, cells_df


# ----------------------------------------------------------------------------- presets
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
                u, us = stats(tr, [q["key"]], "vt", "unseen"), stats(tr, [q["key"]], "vt_stress", "unseen")
                cal = stats(tr, [q["key"]], "vt", "calibration")
                e = {per: stats(tr, [q["key"]], "vt", per) for per in S["earlier"]}
                e_txt = "; ".join(f"{PERIOD_TEXT[per]}, {v['n']} trades, PF {f2(v['pf'])}" for per, v in e.items())
                trend = "none" if p["htf"] == "none" else f"{p['htf']} EMA {p['htf_ema']}"
                target = f"{p['tp_rr']:g}R" if p["tp_mode"] == 1 else "previous hump"
                costs = ("VT costs: Dukascopy ticks with VT's 0.15 spread (scaled by Dukascopy's own spread), 0.60 USD commission per ounce"
                         if not btc else "Binance BTCUSDT one-second prices with a 10 USD spread, no commission")
                held = ch["held"]
                head = [MP.plain(f"XAUUSD_Loma_TrendPullback v{MP.EA_VERSION} on {sym} - best trailing of {p['tf']} (tick replay): {name} trailing "
                                 f"(TrailMode {ch['trail_mode']}), setup {k} of {k_total}: {side.lower()}, session {sess} server time, trend filter {trend}, "
                                 f"target {target}. " + ("DO NOT LOAD ON GOLD." if btc else "DO NOT LOAD ON BTC.")),
                        MP.plain(f"Trailing: {describe(p)}. Needs EA v1.35 or later (TrailMode {ch['trail_mode']}, TrailParam {int(p.get('trail_p', 0))})."),
                        MP.plain(f"Picked on Jan 2025 - May 15 2026 only, by the one-minute backtest at the study's costs "
                                 f"({'10 USD spread' if btc else 'FTMO spread, no commission'}; score {q['is_score']:.2f}): "
                                 f"{q['stored']['is_n']} trades, PF {q['stored']['is_pf']:.2f}. Tick replay of the same months: {cal['n']} trades, PF {f2(cal['pf'])}."),
                        MP.plain(f"TICK REPLAY (every tick, the EA's rules; {costs}). Unseen May 16 - Nov 13 2026: this setup {u['n']} trades, "
                                 f"PF {f2(u['pf'])}, net {u['net_r']:+.1f}R (stressed PF {f2(us['pf'])}); the {k_total} setups of {p['tf']} + {name} together "
                                 f"{grp_u['n']} trades, PF {f2(grp_u['pf'])}, net {grp_u['net_r']:+.1f}R (stressed {f2(grp_s['pf'])})."),
                        MP.plain(f"{name} was chosen as the best of the EA's trailing systems on {p['tf']} by that 2026 result"
                                 + (" (fewer than 100 trades: thin)" if b["thin"] else "") + ": the 2026 figure is the score it was chosen by, not a test."
                                 + (f" Even so the set lost money in those months (PF {f2(grp_u['pf'])}): it is here only because the zip has the best "
                                    f"system of every timeframe." if grp_u["pf"] < 1.0 else "")),
                        MP.plain(f"EARLIER DATA, not used for any choice (tick replay, same costs): this setup: {e_txt}. The {k_total} setups together: {grp_e}. "
                                 + ("They held (PF 1.3 or more in every earlier period), but nothing here is proven: Strategy Tester and demo only."
                                    if held else "They did not hold (under 1.3): UNPROVEN, Strategy Tester and demo only.")),
                        *([MP.plain(f"Its target ({p['tp_rr']:g}R) equaled its minimum reward in the backtest; the preset sets MinRewardRisk "
                                    f"{rr:g} so the EA takes every such signal (the tick figures above are with this setting).")] if is_tie(p) else []),
                        ("Data: Binance BTCUSDT, broker server time. Points are 0.01 USD: 2000 points = 20 USD." if btc else
                         "Data: Dukascopy XAUUSD ticks, broker server time. Commission is in the figures: set CommissionPerLot to your round-trip commission per lot."),
                        "Times are BROKER SERVER TIME (New York + 7 h: GMT+2 in the US winter, GMT+3 in the US summer).",
                        "UseNewsFilter was not in the backtest."]
                MP.write_set(os.path.join(sub, fname + ".set"), head, o)
                rows.append(dict(file=fname, symbol=sym, timeframe=p["tf"], trailing=name, trail_mode=ch["trail_mode"], trail_param=int(p.get("trail_p", 0)),
                                 trailing_rule=describe(p), setup=f"{k} of {k_total}", direction=side.lower(), session=SESS[p["session"]],
                                 trend_filter=trend, target=target, min_reward_risk=o["MinRewardRisk"], target_equals_min_reward=is_tie(p),
                                 in_sample_score=round(q["is_score"], 3), in_sample_trades=q["stored"]["is_n"], in_sample_pf=round(q["stored"]["is_pf"], 3),
                                 tick_calibration_trades=cal["n"], tick_calibration_pf=cal["pf"],
                                 tick_unseen_trades=u["n"], tick_unseen_pf=u["pf"], tick_unseen_net_r=u["net_r"], tick_unseen_stress_pf=us["pf"],
                                 **{f"tick_earlier_{COL[per]}_trades": v["n"] for per, v in e.items()},
                                 **{f"tick_earlier_{COL[per]}_pf": v["pf"] for per, v in e.items()},
                                 combination_unseen_trades=grp_u["n"], combination_unseen_pf=grp_u["pf"], combination_unseen_stress_pf=grp_s["pf"],
                                 combination_held=held, combination_thin=b["thin"], magic=magic, key=q["key"]))
    s = pd.DataFrame(rows)
    s.to_csv(os.path.join(OUT_SETS, "BEST_TRAILING_PRESETS.csv"), index=False, float_format="%.4f")
    assert s.magic.is_unique and s.file.is_unique
    return s


def max_open(tr, keys):
    """Most positions open at the same time (tick replay, VT costs, every period): one EA instance per key."""
    g = tr[tr.key.isin(keys) & (tr.model == "vt") & (tr.engine == "tick")]
    if not len(g):
        return 0
    t = np.r_[g.entry_ms.values, g.exit_ms.values]
    d = np.r_[np.ones(len(g), int), -np.ones(len(g), int)]
    o = np.lexsort((d, t))                                   # an exit before an entry at the same millisecond
    return int(np.cumsum(d[o]).max())


# ----------------------------------------------------------------------------- guide
def guide(best, data, sets):
    L = []
    def table(sym):
        S = SYMS[sym]
        ep = S["earlier"]
        head = ("| Timeframe | Best trailing (TrailMode) | Presets | Unseen 2026: PF (trades) | Stressed | One-minute engine, same months | "
                + " | ".join(f"{PERIOD_TEXT[p]}: PF (trades)" for p in ep) + " | Held on earlier data | Runner-up (2026 PF) |")
        out = [head, "|" + "---|" * (head.count("|") - 1)]
        for b in [b for b in best if b["symbol"] == sym]:
            ch = b["chosen"]
            if not ch:
                why = ("no setup passed the calibration" if not b["systems_with_setups"] else
                       f"no system with {THIN_N} or more trades in the 2026 months")
                out.append(f"| {b['tf']} | none: {why} | – | – | – | – | " + " | ".join("–" for _ in ep) + " | – | – |")
                continue
            ru = ch["runner_up"]
            out.append(f"| {b['tf']} | {SYSTEM[ch['trailing']]} ({ch['trail_mode']}){' – thin' if b['thin'] else ''} | {ch['setups']} | "
                       f"**{f2(ch['unseen']['pf'])} ({ch['unseen']['n']})**{' lost' if ch['unseen']['pf'] < 1.0 else ''} | "
                       f"{f2(ch['unseen_stress']['pf'])} | {f2(ch['unseen_one_minute']['pf'])} | "
                       + " | ".join(f"{f2(ch['earlier'][p]['pf'])} ({ch['earlier'][p]['n']})" for p in ep)
                       + f" | {'yes' if ch['held'] else 'no'} | {(SYSTEM[ru['trailing']] + ' ' + f2(ru['pf'])) if ru else '–'} |")
        return out

    chosen = [b for b in best if b["chosen"]]
    held = [b for b in chosen if b["chosen"]["held"]]
    lost = [b for b in chosen if b["chosen"]["unseen"]["pf"] < 1.0]
    n_g = sum(1 for b in chosen if b["symbol"] == "XAUUSD"); n_b = len(chosen) - n_g
    held_txt = (f"{len(held)} of the {len(chosen)} chosen systems held there (profit factor 1.3 or more in every earlier period): "
                + ", ".join(f"{b['symbol']} {b['tf']} {SYSTEM[b['chosen']['trailing']]}" for b in held)
                if held else f"none of the {len(chosen)} chosen systems held there (profit factor 1.3 or more in every earlier period)")
    tick_vs = []
    for sym in SYMS:
        cells, tr = data[sym]
        for per in ("unseen", "calibration") + tuple(SYMS[sym]["earlier"]):
            g = tr[(tr.model == "vt") & (tr.period == per)]
            t, y = g[g.engine == "tick"].r.values, g[g.engine == "1m"].r.values
            tick_vs.append((sym, per, len(t), pf(t), t.sum(), len(y), pf(y), y.sum()))
    ov = {sym: max_open(data[sym][1], list(sets[sets.symbol == sym].key)) for sym in SYMS}
    ov_tf = {(sym, tf): max_open(data[sym][1], list(sets[(sets.symbol == sym) & (sets.timeframe == tf)].key)) for sym in SYMS for tf in TFS
             if len(sets[(sets.symbol == sym) & (sets.timeframe == tf)])}

    L += [f"# Loma EA v{MP.EA_VERSION}: the best trailing system per timeframe (tick replay), start here", "",
          f"`XAUUSD_Loma_TrendPullback.mq5` v{MP.EA_VERSION} (the same file as in the gold and BTC zips) with one set of presets per timeframe: "
          "the trailing system that did best on that timeframe when the re-calibration's setups were replayed tick by tick with the EA's own rules. "
          f"{n_g} gold and {n_b} BTC timeframes have a set. **The file names say Gold or BTC: do not load gold presets on BTC or BTC presets on gold.**", "",
          "> **Nothing in this zip is proven. Strategy Tester and demo only.**",
          "> - Each timeframe's trailing system was chosen by its result in the unseen months of 2026 (16 May – 13 November). "
          "That makes the 2026 figure the score it was chosen by, not a test, and the best of up to 14 systems is flattered by the choice.",
          f"> - The check is the earlier data, which played no part in any choice (gold: 15 July – 31 December 2024; BTC: 2023 and 2024): {held_txt}."]
    if lost:
        L += [f"> - On {len(lost)} timeframes even the best system lost money in the 2026 months it was chosen on: "
              + ", ".join(f"{'gold' if b['symbol'] == 'XAUUSD' else 'BTC'} {b['tf']} ({f2(b['chosen']['unseen']['pf'])})" for b in lost)
              + ". They are here only because the zip has one set per timeframe."]
    L += [""]
    L += ["## How it was measured", "",
          "- **The setups** are the re-calibration's picks (November 2026): for every timeframe and trailing system, up to 10 setups chosen on "
          "1 January 2025 – 15 May 2026 only, one per direction, session and trend filter, each with an in-sample score of 1.3 or more. "
          "M1 and H1 had no setup that passed, for gold or BTC, so they have no presets.",
          "- **The replay** runs every setup tick by tick with the EA's execution rules: entry on the first tick of the entry minute at the ask (buys) "
          "or the bid (sells) after the spread check; stop and target checked on every tick, a stop filled at the tick price (worse on a gap); "
          "the trailing systems updated as the EA does (TrailMode 0 and 4 on every tick in steps of `TrailStep_Points`, the others once per closed "
          "one-minute bar); the time exits, the Friday close (gold) and one position per preset. It was checked against the EA's own code run on "
          "the same ticks in a simulated terminal, on samples of setups covering every TrailMode: 470 of 470 gold trades and 804 of 804 BTC trades "
          "identical in entry, stop, target, stop moves, exit and result. An independent re-trace of all 20,087 gold trades of July – December 2024 "
          "found the same trades.",
          "- **Gold prices:** Dukascopy ticks. **VT costs:** Dukascopy's mid price with VT Markets' 0.15 spread, scaled by Dukascopy's own spread "
          "so its spikes stay, and $0.60 commission per ounce. **Stressed:** one minute late, $0.10 slippage, $0.67 commission.",
          "- **BTC prices:** Binance BTCUSDT one-second prices (the same source as the study's one-minute bars), with a $10 spread and no "
          "commission. **Stressed:** one minute late, $3 slippage, $2 commission per BTC.",
          f"- **The choice** (written down before the full replay ran, `research/results/tick/best_trailing_rule.md`): on each timeframe, among the "
          f"EA's trailing systems with at least {MIN_N} trades in the 2026 months (at least {THIN_N} where none had {MIN_N}: marked thin), "
          "the highest profit factor at VT costs. **Held** = profit factor 1.3 or more in every earlier period.", ""]
    L += ["## Gold (XAUUSD)", ""] + table("XAUUSD") + ["", "## BTC (BTCUSD)", ""] + table("BTCUSD") + [""]
    L += ["- PF = profit factor (gross wins / gross losses). Trades of all the setups of a timeframe's set together.",
          "- *One-minute engine, same months*: the study's one-minute backtest on the same prices and costs, for comparison with the tick replay.",
          "- Every preset's header gives its own figures; `BEST_TRAILING_PRESETS.csv` lists them all, `BEST_TRAILING_BY_TIMEFRAME.csv` the "
          "choice of every timeframe with its runner-up, and `TICK_REPLAY_ALL_CELLS.csv` every trailing system on every timeframe, period and cost model, "
          "tick and one-minute.", ""]
    dpf = [pt - py for _, _, _, pt, _, _, py, _ in tick_vs]
    L += ["## Ticks against one minute", "",
          f"All the setups of the EA's 14 systems together, VT costs. The tick replay takes almost the same trades as the one-minute engine on the "
          f"same prices and costs, and its profit factor is {min(-x for x in dpf):.2f} to {max(-x for x in dpf):.2f} lower: the one-minute "
          "figures of the study were close, slightly optimistic.", "",
          "| Symbol | Period | Tick replay: trades, PF, net | One-minute engine: trades, PF, net |", "|---|---|---|---|"]
    for sym, per, nt, pt, st, ny, py, sy in tick_vs:
        lab = PERIOD_TEXT[per] + (" (the setups were picked on it)" if per == "calibration" else "")
        L.append(f"| {sym} | {lab} | {nt}, {f2(pt)}, {st:+.0f}R | {ny}, {f2(py)}, {sy:+.0f}R |")
    L += ["", "## The 15 earlier trailing results, tick by tick", "",
          "The combinations of timeframe and trailing system that had reached a profit factor of 1.3 on the 2026 months in the one-minute "
          "backtest (the `Loma_T15` presets of the gold and BTC zips), re-measured here. The one-minute figures were at the study's costs "
          "(gold: FTMO spread, no commission; BTC: $10 spread); the tick figures are at VT costs.", "",
          "| Symbol | Timeframe | Trailing | 2026 one-minute (study): PF (trades) | 2026 tick, VT costs: PF (trades) | Stressed | Earlier data, tick: PF (trades) |",
          "|---|---|---|---|---|---|---|"]
    for sym in SYMS:
        cells, tr = data[sym]
        t15 = json.load(open(os.path.join(ROOT, "research", "results", "recal", f"{sym.lower()}_successful_trailing.json")))["combinations"]
        for c15 in t15:
            c = next(c for c in cells if c["tf"] == c15["timeframe"] and c["kind"] == c15["trailing"])
            keys = [q["key"] for q in c["picks"]]
            u, us = stats(tr, keys, "vt", "unseen"), stats(tr, keys, "vt_stress", "unseen")
            e = "; ".join(f"{PERIOD_TEXT[p]}: {f2(stats(tr, keys, 'vt', p)['pf'])} ({stats(tr, keys, 'vt', p)['n']})" for p in SYMS[sym]["earlier"])
            L.append(f"| {sym} | {c15['timeframe']} | {SYSTEM[c15['trailing']]} | {c15['unseen_pf']:.2f} ({c15['unseen_trades']}) | "
                     f"{f2(u['pf'])} ({u['n']}) | {f2(us['pf'])} | {e} |")
    L += ["", "## How to run the presets", "",
          "- **One timeframe's set is one result:** its setups were tested together. Run them together on one **hedging** account (on a netting "
          "account the presets on one symbol share one position).",
          "- **Overlap:** in the replay the most positions open at once were "
          + ", ".join(f"{sym} {tf}: {n}" for (sym, tf), n in ov_tf.items())
          + f"; all gold sets together {ov['XAUUSD']}, all BTC sets together {ov['BTCUSD']}. Each preset has `RiskPercent=0.5`: "
          "lower it (for example to 0.1) if you run several sets at once.",
          "- **Gold commission:** the figures include $0.60 per ounce. Set `CommissionPerLot` to your round-trip commission per lot in the account "
          "currency, so a stop-out costs `RiskPercent` including commission.",
          "- **BTC:** points are 0.01 USD (`AutoScalePoints=true`); `MaxSpread_Points=3000` ($30), `TrailStep_Points=200` ($2), no weekend close. "
          "BTC stops are wide (hundreds of dollars): with a 0.01 minimum lot a trade is skipped when the equity is too small for its stop "
          "(`SkipIfBelowMinLot=true`); test with a large deposit first.",
          "- **Server time:** sessions and the end-of-day close are broker server time (New York + 7 h: GMT+2 in the US winter, GMT+3 in the US "
          "summer), the clock of VT Markets and FTMO.",
          "- **News filter** is on in the presets but was not in the replay; it does nothing in the Strategy Tester.", "",
          "## If you want to test it", "",
          "1. **Strategy Tester:** \"Every tick based on real ticks\" on your broker's symbol, one timeframe's set at a time, over 16 May – 13 November "
          "2026 and over the earlier period, and compare with the tables above. In the tester the Load dialog usually opens in "
          "`MQL5\\Profiles\\Tester`; browse to `MQL5\\Presets`.",
          "2. **Then demo.** A tester run that matches shows that the EA trades its backtest, not that the edge is real.", "",
          "## What is in the zip", "", "| File | What it is |", "|---|---|",
          f"| `MQL5/Experts/XAUUSD_Loma_TrendPullback.mq5` | The EA, v{MP.EA_VERSION}. |",
          "| `MQL5/Include/EVK/EVK.mqh` | Records trades in the Strategy Tester only (EA Validation Kit). The EA needs it to compile. |",
          f"| `MQL5/Presets/Loma_BT_Gold_*.set` | {int((sets.symbol == 'XAUUSD').sum())} gold presets: every setup of each gold timeframe's best system. |",
          f"| `MQL5/Presets/Loma_BT_BTC_*.set` | {int((sets.symbol == 'BTCUSD').sum())} BTC presets: every setup of each BTC timeframe's best system. |",
          "| `BEST_TRAILING_BY_TIMEFRAME.csv` | The choice of every timeframe, with its runner-up and the earlier-data check. |",
          "| `BEST_TRAILING_PRESETS.csv` | Every preset with its figures. |",
          "| `TICK_REPLAY_ALL_CELLS.csv` | Every trailing system on every timeframe: each period and cost model, tick replay and one-minute engine. |", "",
          "## Install", "",
          "1. In MT5 choose **File > Open Data Folder**.",
          "2. Copy the zip's `MQL5` folder over the data folder's `MQL5` folder.",
          "3. In MetaEditor open `MQL5/Experts/XAUUSD_Loma_TrendPullback.mq5` and press **F7** (compile). It has not been compiled in MetaEditor "
          "yet: if the compiler reports anything, send the log rather than editing the file.",
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
        best, data, cells_df = results({"XAUUSD": sys.argv[2], "BTCUSD": sys.argv[3]})
        sets = presets(best, data)
        guide(best, data, sets)
        make_zip(sets)
        pd.set_option("display.width", 250)
        print(pd.read_csv(os.path.join(OUT_RES, "best_by_timeframe.csv")).round(3).to_string(index=False))
