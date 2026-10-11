#!/usr/bin/env python3
"""Grid-search the EA inputs on exported bars and write the best N as MT5 .set presets.

  python3 presets.py bars.csv --symbol BTCUSD --point 0.01 --n 10 --out calibration/presets_BTCUSD
"""
import argparse, itertools, os, sys
import calibrate as C

EA_DEFAULTS = dict(
    SigMode=1, TradeDir=0, EnterOnTick="false", TurnEntry=0, FailExit="false", OppMode=0,
    ArmMode=0, PredBuf=100, CatchUp="true", MaxChase=0,
    ContEntry=0, ContStopBuf=50, ContStopBars=3,
    ExitUnit=0, SlPts=7000, TpPts=50000, ExAtrLen=14, SlAtrM=2.0, TpR=2.0, TrailOn="true",
    TrActPts=1000, TrDisPts=100, TrActAtr=4.0, TrDisAtr=0.2, TimeStop=0,
    QtyMode=1, LotsFixed=0.10, RiskPct=1.0, LotsMax=5.0, MarginCap="true",
    IndicatorName="XPW_ShapeMap", Magic=90907, SlippagePts=30, ShowMap="true",
    RsiLen=14, FastLen=2, SlowLen=7, InvertFill="true", AreaLook=20, LoFrac=0.20, HiFrac=0.67,
    AllOn="true", AllCtx=1, BotOn="true", BotMinW=1, BotMaxW=3, BotCtxIn=2, BotNeedLow="true", BotSepIn=5,
    TopOn="true", TopMinW=1, TopMaxW=2, TopCtxIn=3, TopNeedHigh="true", TopSepIn=5,
    TurnOn="true", TurnMax=12, TurnHold=2, TickOn="true", AtrLen=14,
    BotWickRange=0.55, BotWickAtr=0.8, TopWickRange=0.70, TopWickAtr=1.20,
    ContOn="true", ContBigAtr=1.0, ContLook=30, ContNeedRed="true", ContRedMax=12, ContPinch=1.0, ContAfter=6, ContSep=5, ContMirror="true")

MODE_MAP = {  # calibrator mode -> EA inputs
    "square":       dict(SigMode=0),
    "turn_predict": dict(SigMode=1, TurnEntry=0),
    "turn_cross":   dict(SigMode=1, TurnEntry=1),
    "turn_hold":    dict(SigMode=1, TurnEntry=2),
    "tick":         dict(SigMode=2),
    "cont":         dict(SigMode=3, ContEntry=0),
    "cont_stop":    dict(SigMode=3, ContEntry=1),
}
DIR_MAP = {"both": 0, "long": 1, "short": 2}
OPP_MAP = {"reverse": 0, "close": 1, "ignore": 2}
CONT_GRID = [(1.0, 1.0, 6), (0.8, 1.5, 4), (0.8, 1.5, 6), (1.2, 1.0, 4), (1.0, 1.5, 4)]

def halves(m, rows):
    mid = rows[len(rows) // 2]["t"]
    a = sum(t["pnl"] for t in m["list"] if t["t"] < mid) / C.START_EQUITY * 100
    b = sum(t["pnl"] for t in m["list"] if t["t"] >= mid) / C.START_EQUITY * 100
    return a, b

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file"); ap.add_argument("--symbol", required=True, choices=list(C.SYMBOLS))
    ap.add_argument("--point", type=float, default=None); ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--out", default=None); ap.add_argument("--risk", type=float, default=1.0)
    a = ap.parse_args()
    sym = dict(C.SYMBOLS[a.symbol]); pt = a.point or sym["point"]; sym["point"] = pt
    rows = C.load(a.file); ind = C.indicators(rows, C.P)
    sigcache = {}
    def sigs(big, pinch, after):
        k = (big, pinch, after)
        if k not in sigcache: sigcache[k] = C.signals(rows, ind, dict(C.P, contBigAtr=big, contPinch=pinch, contAfter=after))
        return sigcache[k]
    cands = []
    for mode in C.MODES:
        contGrid = CONT_GRID if mode.startswith("cont") else [CONT_GRID[0]]
        bufGrid = [0, 50, 100, 200] if mode == "turn_predict" else [0]
        for (big, pinch, after), pb in itertools.product(contGrid, bufGrid):
            S = sigs(big, pinch, after)
            for sl, act, dis, tdir, opp in itertools.product(sym["sl_usd"], sym["act_usd"], sym["dis_usd"], ("both", "long", "short"), ("reverse", "close")):
                if dis >= act: continue
                m = C.backtest(rows, ind, S, sym, mode, sl, 0, act, dis, risk=a.risk, opp=opp, tradeDir=tdir,
                               predBuf=pb, contStopBuf=50 * pt)
                if m["trades"] < 15: continue
                h1, h2 = halves(m, rows)
                robust = h1 > 0 and h2 > 0
                sc = C.score(m) + (10 if robust else -20)
                cands.append(dict(score=sc, mode=mode, sl=sl, act=act, dis=dis, dir=tdir, opp=opp, pb=pb, big=big, pinch=pinch, after=after, m=m, h1=h1, h2=h2, robust=robust))
    cands.sort(key=lambda x: -x["score"])
    # keep variety: at most 3 presets per mode
    picked, per = [], {}
    for cnd in cands:
        if per.get(cnd["mode"], 0) >= 3: continue
        picked.append(cnd); per[cnd["mode"]] = per.get(cnd["mode"], 0) + 1
        if len(picked) >= a.n: break
    lines = [f"# Best {len(picked)} EA presets — {a.symbol}, point {pt}, {len(rows)} bars {rows[0]['t']} .. {rows[-1]['t']}",
             f"Risk {a.risk}% per trade, ${C.START_EQUITY:.0f} start, spread {sym['spread']} per unit. 'half 1 / half 2' = net % on each half of the data.", "",
             "| # | mode | dir | opp | SL $ | act $ | dis $ | pred buf | CONT big/pinch/after | trades | win | PF | net | maxDD | half 1 / half 2 |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    if a.out: os.makedirs(a.out, exist_ok=True)
    for k, cnd in enumerate(picked, 1):
        m = cnd["m"]
        lines.append(f"| {k} | {cnd['mode']} | {cnd['dir']} | {cnd['opp']} | {cnd['sl']} | {cnd['act']} | {cnd['dis']} | {cnd['pb']} | {cnd['big']}/{cnd['pinch']}/{cnd['after']} | {m['trades']} | {m['win']:.0f}% | {m['pf']:.2f} | {m['net']:.1f}% | {m['maxdd']:.1f}% | {cnd['h1']:.1f}% / {cnd['h2']:.1f}% |")
        if a.out:
            d = dict(EA_DEFAULTS); d.update(MODE_MAP[cnd["mode"]])
            d.update(TradeDir=DIR_MAP[cnd["dir"]], OppMode=OPP_MAP[cnd["opp"]],
                     SlPts=int(round(cnd["sl"] / pt)), TpPts=0, TrActPts=int(round(cnd["act"] / pt)), TrDisPts=int(round(cnd["dis"] / pt)),
                     PredBuf=int(round(cnd["pb"] / pt)), ContStopBuf=50,
                     ContBigAtr=cnd["big"], ContPinch=cnd["pinch"], ContAfter=cnd["after"], RiskPct=a.risk)
            name = f"{k:02d}_{a.symbol}_{cnd['mode']}_{cnd['dir']}_SL{cnd['sl']}.set"
            with open(os.path.join(a.out, name), "w", encoding="utf-16") as f:
                f.write(f"; XPW Shape Map EA preset {k} — {a.symbol} point {pt}: {cnd['mode']} {cnd['dir']} {cnd['opp']} SL ${cnd['sl']} trail {cnd['act']}/{cnd['dis']}\n")
                f.write(f"; net {m['net']:.1f}%  maxDD {m['maxdd']:.1f}%  trades {m['trades']}  PF {m['pf']:.2f}\n")
                for kk, vv in d.items(): f.write(f"{kk}={vv}\n")
            lines[-1] += f" `{name}`"
    txt = "\n".join(lines); print(txt)
    if a.out:
        with open(os.path.join(a.out, "PRESETS.md"), "w") as f: f.write(txt + "\n")

if __name__ == "__main__":
    main()
