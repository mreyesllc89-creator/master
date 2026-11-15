#!/usr/bin/env python3
"""
The trailing systems that reached a profit factor of 1.3 on the unseen months (16 May - 13 Nov 2026) on at least
100 trades, with the settings of every setup behind each result and the same setups' result on earlier data.

Three levels are listed for the symbol:
  system       one trailing system, its picks of all timeframes together
  combination  one timeframe with one trailing system (the cells of <sym>_23_trailing_by_family.json)
  timeframe    the protocol's own test: the best 10 setups of a timeframe, any trailing system

The picks are re-derived from the stored candidate trades with the protocol's rule and must reproduce the stored
figures of research/results/recal exactly, so the settings listed are those of the setups the figures come from.

Usage (from research/): [HUMP_SYMBOL=BTCUSD] python3 successful_trailing.py <recal_work_dir> <out_json>
"""
import json, os, sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hump_tf_recal as R
import hump_trail as T, hump_trail2 as T2

WORK, OUT = sys.argv[1], sys.argv[2]
RES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "recal")
sym = R.SYM.lower()
BTC = R.SYM == "BTCUSD"
UNIT = "per BTC" if BTC else "per ounce"
SESS = {"all": "all day", "london_07-12": "07:00-12:00", "ldn_ny_07-20": "07:00-20:00", "ny_12-20": "12:00-20:00", "ny_12-1630": "12:00-16:30"}


def start(a):
    return "from the minute after entry" if a <= 0 else f"once the profit reaches {a:g}R"


def describe(p):
    """The trailing rule of one setup in plain words (R = the trade's initial risk)."""
    k, a, b, n, tf = p["trail_kind"], p["trail_start"], p["trail_dist"], int(p.get("trail_p", 0)), p["tf"]
    lvl = lambda what: f"stop beyond {what}, {start(a)}"
    return {
        "none": lambda: "no trailing",
        "R": lambda: f"{b:g}R behind the best price once the profit reaches {a:g}R (the EA's own rule)",
        "points": lambda: f"${b:g} behind the best price once the profit reaches ${a:g} ({UNIT}), stop moved once per closed minute",
        "percent": lambda: f"{b:g}% of price behind the best price once the profit reaches {a:g}%, stop moved once per closed minute",
        "atr": lambda: f"{b:g} x ATR(14) of {tf} at entry behind the best price once the profit reaches {a:g} x ATR, stop moved once per closed minute",
        "breakeven": lambda: f"stop to entry{f' + {b:g}R' if b else ''} once the profit reaches {a:g}R",
        "step": lambda: f"every {a:g}R of profit lifts the stop by {a:g}R, one step behind (breakeven at +{a:g}R)",
        "candles": lambda: lvl(f"the low / high of the last {n} closed {tf} candles"),
        "ema": lambda: lvl(f"the EMA({n}) of {tf} closes"),
        "psar": lambda: lvl(f"the Parabolic SAR ({T.PSAR[n][0]:g} / {T.PSAR[n][1]:g}) of {tf}"),
        "hump": lambda: lvl("the last completed pullback hump"),
        "chandelier": lambda: f"{b:g} x live ATR(14) of {tf} behind the best price, {start(a)}",
        "profitlock": lambda: f"keeps {100 * b:.0f}% of the best open profit once it reaches {a:g}R, stop moved once per closed minute",
        "timestop": lambda: f"stop slides from the initial stop to breakeven over {int(b)} minutes",
        "partial": lambda: f"half closed at +{a:g}R, the rest to breakeven" + (f" and then {b:g}R behind the best price" if b > 0 else ""),
        "supertrend": lambda: lvl(f"the SuperTrend ({T2.SUPERTREND[n][0]} / {T2.SUPERTREND[n][1]:g}) of {tf}"),
        "keltner": lambda: lvl(f"the Keltner band EMA(20) -/+ {T2.KELTNER[n]:g} x ATR(10) of {tf}"),
        "bollinger": lambda: lvl(f"the Bollinger band SMA(20) -/+ {T2.BOLLINGER[n]:g} sd of {tf}"),
        "kijun": lambda: lvl(f"the Ichimoku base line over {n} {tf} bars"),
        "pivots": lambda: lvl(f"the last confirmed {tf} swing with {n} bars on each side"),
        "sma": lambda: lvl(f"the SMA({n}) of {tf} closes"),
        "donchian": lambda: lvl(f"the lowest low / highest high of {n} {tf} bars"),
        "htfcandle": lambda: lvl(f"the low / high of the last closed {n}-minute candle"),
    }[k]()


def pick(P, sc, idx):
    """The protocol's pick inside a set of candidates: best scores, one per (direction, session, trend filter), score >= 1.3."""
    elig = idx[sc[idx] > 0]
    order = elig[np.argsort(-sc[elig], kind="stable")]
    out, fams = [], set()
    for i in order:
        if sc[i] < R.PASS_PF or len(out) >= R.TOPK:
            break
        fam = (P[i]["sides"], P[i]["session"], P[i]["htf"])
        if fam in fams:
            continue
        fams.add(fam); out.append(int(i))
    return out


def setup_row(p, score, b, s):
    isr, _, oor = R.split(*b); _, _, oos = R.split(*s)
    return dict(timeframe=p["tf"], trailing=p["trail_kind"], trailing_rule=describe(p),
                direction={0: "both", -1: "sell", 1: "buy"}[p["sides"]], session=SESS[p["session"]],
                trend_filter="none" if p["htf"] == "none" else f"{p['htf']} EMA {p['htf_ema']}",
                target=f"{p['tp_rr']:g}R" if p["tp_mode"] == 1 else "previous hump", macd=p["macd"],
                in_sample_score=round(float(score), 2), in_sample_trades=int(len(isr)), in_sample_pf=round(R.pf(isr), 2),
                unseen_trades=int(len(oor)), unseen_pf=round(R.pf(oor), 2), unseen_net_r=round(float(oor.sum()), 1),
                unseen_stress_pf=round(R.pf(oos), 2), params=p)


fam = json.load(open(os.path.join(RES, f"{sym}_23_trailing_by_family.json")))
main = {x["tf"]: x for x in json.load(open(os.path.join(RES, f"{sym}_23_trailing.json")))["timeframes"]}
pre_name = f"{sym}_23_trailing_on_2023_2024.json" if BTC else f"{sym}_23_trailing_on_2024h2.json"
pre = {x["group"]: x for x in json.load(open(os.path.join(RES, pre_name)))["groups"]}
PERIODS = ["2024", "2023"] if BTC else ["2024H2"]
cells = {(c["tf"], c["kind"]): c for c in fam["cells"]}
kinds_all = {c["kind"]: c for c in fam["by_kind_all_timeframes"]}


def earlier(group):
    x = pre[group]
    return {f"y{y}": dict(pf=round(x[f"y{y}_pf"], 2), trades=int(x[f"y{y}_n"])) for y in PERIODS}


def passes(c):
    return bool(c.get("oos_n")) and c["oos_n"] >= R.PASS_N and c["oos_pf"] >= R.PASS_PF


out = dict(symbol=R.SYM, unseen="2026-05-16 to 2026-11-13", earlier_periods=PERIODS, systems=[], combinations=[], timeframes=[])
by_kind = {}                                    # kind -> setups of all timeframes (for the system level)
for tf in R.TFS:
    P, Bs, Ss = R.load_cands(WORK, "candx+candy", tf)
    sc = np.array([R.is_score(Bs[i], Ss[i]) for i in range(len(P))])
    allidx = np.arange(len(P))
    kind_of = np.array([p["trail_kind"] for p in P])
    for kind in dict.fromkeys(kind_of):
        got = pick(P, sc, allidx[kind_of == kind])
        rows = [setup_row(P[i], sc[i], Bs[i], Ss[i]) for i in got]
        by_kind.setdefault(kind, []).extend((i, rows[j], R.split(*Bs[i])[2], R.split(*Ss[i])[2]) for j, i in enumerate(got))
        c = cells[(tf, kind)]
        if got:                                 # the re-derived picks must be the stored cell
            r = np.concatenate([R.split(*Bs[i])[2] for i in got])
            assert len(got) == c["picked"] and len(r) == c["oos_n"] and abs(R.pf(r) - c["oos_pf"]) < 1e-9, (tf, kind)
        if passes(c):
            out["combinations"].append(dict(timeframe=tf, trailing=kind, setups=len(got), unseen_trades=int(c["oos_n"]),
                                            unseen_pf=round(c["oos_pf"], 2), unseen_stress_pf=round(c["oos_stress_pf"], 2),
                                            earlier=earlier(f"{tf} + {kind}"), picks=rows))
    m = main[tf]
    if m.get("picked") and m["oos_n"] >= R.PASS_N and m["oos_pf"] >= R.PASS_PF:
        got = pick(P, sc, allidx)
        r = np.concatenate([R.split(*Bs[i])[2] for i in got])
        assert len(r) == m["oos_n"] and abs(R.pf(r) - m["oos_pf"]) < 1e-9, tf
        out["timeframes"].append(dict(timeframe=tf, setups=len(got), unseen_trades=int(m["oos_n"]), unseen_pf=round(m["oos_pf"], 2),
                                      unseen_stress_pf=round(m["oos_stress_pf"], 2), earlier=earlier(f"timeframe {tf}"),
                                      picks=[setup_row(P[i], sc[i], Bs[i], Ss[i]) for i in got]))
for kind, items in by_kind.items():
    k = kinds_all[kind]
    r = np.concatenate([x[2] for x in items]) if items else np.zeros(0)
    assert len(r) == k.get("oos_n", 0) and (not len(r) or abs(R.pf(r) - k["oos_pf"]) < 1e-9), kind
    if passes(k):
        out["systems"].append(dict(trailing=kind, setups=len(items), unseen_trades=int(k["oos_n"]), unseen_pf=round(k["oos_pf"], 2),
                                   unseen_stress_pf=round(k["oos_stress_pf"], 2), earlier=earlier(f"trailing {kind}"),
                                   picks=[x[1] for x in items]))
json.dump(out, open(OUT, "w"), indent=1, default=float)

pd.set_option("display.width", 260); pd.set_option("display.max_colwidth", 120)
for level in ("systems", "combinations", "timeframes"):
    print(f"\n===== {R.SYM} {level}: {len(out[level])} reached PF {R.PASS_PF} on {R.PASS_N}+ unseen trades")
    for g in out[level]:
        e = "; ".join(f"{y[1:]}: {v['pf']:.2f} ({v['trades']})" for y, v in g["earlier"].items())
        name = " ".join(str(g[k]) for k in ("timeframe", "trailing") if k in g)
        print(f"\n--- {name}: {g['setups']} setups, unseen PF {g['unseen_pf']:.2f} on {g['unseen_trades']} trades (stressed {g['unseen_stress_pf']:.2f}) | earlier data: {e}")
        if level != "systems":
            t = pd.DataFrame(g["picks"])[["trailing", "trailing_rule", "direction", "session", "trend_filter", "target", "in_sample_score", "unseen_trades", "unseen_pf", "unseen_net_r"]]
            print(t.to_string(index=False))
