"""Re-run each top-10 config in its replay engine with commission and slippage applied IN-ENGINE (fills worsened by
slip ticks per side, commission per side), on the same VT XAUUSD-ECNc July 2026 bid/ask ticks as the screen."""
import sys, os, re, json, time, types, csv
import numpy as np, pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "fg5"))
KEY = sys.argv[1]           # fg5 | sm92 | v28
LEVELS = [(0.30, 0), (0.30, 2), (0.30, 5), (0.30, 10), (0.60, 0), (0.60, 5), (0.60, 10)]   # (commission USD per lot per side, slippage ticks per side)
SYM = "XAUUSD-ECNc"; UNIT = 1.0; SPREAD = 13.0; TICK = 0.01; LOTS = 0.1
TFM = {"M5": 5, "M15": 15, "M30": 30, "H1": 60}

def load_patched(path, modname, edits, run_slip=None):
    src = open(path, encoding="utf-8").read()
    for old, new, cnt in edits:
        assert src.count(old) == cnt, (modname, old[:60], src.count(old)); src = src.replace(old, new)
    if run_slip:
        start, end, exp = run_slip
        i = src.index(start); j = src.index(end, i) if end else len(src); body = src[i:j]
        n = (len(re.findall(r"\bask\[kk\]", body)), len(re.findall(r"\bbid\[kk\]", body)), len(re.findall(r"\bbid\[-1\]", body)), len(re.findall(r"\bask\[-1\]", body)))
        assert n == exp, (modname, n)
        body = re.sub(r"\bask\[kk\]", "(ask[kk]+slip)", body); body = re.sub(r"\bbid\[kk\]", "(bid[kk]-slip)", body)
        body = re.sub(r"\bbid\[-1\]", "(bid[-1]-slip)", body); body = re.sub(r"\bask\[-1\]", "(ask[-1]+slip)", body)
        src = src[:i] + body + src[j:]
    mod = types.ModuleType(modname); mod.__file__ = path
    exec(compile(src, path, "exec"), mod.__dict__); sys.modules[modname] = mod
    open(os.path.join(ROOT, "stress", f"patched_{modname}.py"), "w", encoding="utf-8").write(src)
    return mod

z = np.load(os.path.join(ROOT, f"{SYM}_ticks.npz")); t = z["t"]; bid = z["bid"]; ask = z["ask"]; mid = (bid + ask)/2
top = [r for r in csv.DictReader(open(os.path.join(ROOT, "deliver", "top10_per_strategy.csv"), encoding="utf-8"))]
NAME = {"fg5": "FlashGold v5", "sm92": "ShapeMap v0.9.2", "v28": "Orientation v2.8 (partial ladder)"}[KEY]
rows = [r for r in top if r["strategy"] == NAME]; assert len(rows) == 10
out = []; ledg = os.path.join(ROOT, "stress", "ledgers"); os.makedirs(ledg, exist_ok=True); t0 = time.time()

def rec(rank, r, c, s, m, tr):
    out.append(dict(strategy=NAME, rank=rank, symbol=SYM, tf=r["tf"], settings=r["settings"], comm_side=c, comm_rt_per_lot=2*c, slip_ticks=s,
                    trades=m["trades"], net=round(float(m["net"]), 3), pf=round(float(m["pf"]), 3), win=round(float(m["win"]), 3), maxdd=round(float(m["maxdd"]), 3),
                    pos_weeks=round(float(m["pos_weeks"]), 3), halves=m["halves"], screen_net=float(r["net"]), screen_trades=int(r["trades"])))
    if c == 0.30 and s == 0: tr.to_csv(os.path.join(ledg, f"{KEY}_{rank:02d}.csv"), index=False)

if KEY == "fg5":
    import fg5 as F0
    F = load_patched(os.path.join(ROOT, "fg5", "fg5.py"), "fg5s", [("if synthetic: px = px - side*slip", "px = px - side*slip", 1), ("if synthetic: px = px + sd*slip", "px = px + sd*slip", 1)])
    b60 = F.bars_from_ticks(t, mid, 3600000); b120 = F.resample(b60, 2); b240 = F.resample(b60, 4)
    cache = {}
    for rank, r in enumerate(rows, 1):
        m_ = re.fullmatch(r"ATR SL ([\d.]+) TP ([\d.]+)R (Fixed\+trail|Fixed|Partial), burst ([\d.]+), filter (off|on)", r["settings"]); sl, tp, style, bm, f = m_.groups()
        tfn = r["tf"]; bm = float(bm)
        if tfn not in cache:
            chart = F.bars_from_ticks(t, mid, TFM[tfn]*60000); z2 = F.resample(chart, 2); z3 = F.resample(chart, 4)
            fp = F.SigParams(spread_pts=SPREAD)
            cache[tfn] = dict(chart=chart, z2=z2, z3=z3, gates={"off": F.fgf_gate(chart, b60, b120, b240, fp, TICK, enabled=False)[:2], "on": F.fgf_gate(chart, b60, b120, b240, fp, TICK, enabled=True)[:2]}, sig={})
        C = cache[tfn]
        if bm not in C["sig"]: C["sig"][bm] = F.signal(C["chart"], C["z2"], C["z3"], F.SigParams(spread_pts=SPREAD, burst_atr=bm), TICK)
        xp = F.ExitParams(mode="ATR", sl_atr=float(sl), tpr_atr=float(tp), style="Fixed" if style.startswith("Fixed") else "Partial + runner", use_trail=(style == "Fixed+trail"))
        gb, gs = C["gates"][f]
        for c, s in LEVELS:
            cost = F.Costs(qty=LOTS, unit=UNIT, comm_side_per_qty=c, comm_pct=0.0, slip_ticks=s, tick=TICK)
            tr, info = F.run(C["chart"], t, bid, ask, C["sig"][bm], gb, gs, xp, cost)
            rec(rank, r, c, s, F.metrics(tr, cost), tr)
        print(KEY, rank, r["tf"], r["settings"], "base net", out[-7]["net"], "vs screen", r["net"], round(time.time()-t0), "s", flush=True)

elif KEY == "sm92":
    import fg5 as F
    M = load_patched(os.path.join(ROOT, "sm92", "sm92.py"), "sm92s",
                     [("comm_side=0.30, tick=0.01):\n    n = len(b.c); trades = []", "comm_side=0.30, tick=0.01, slip_ticks=0):\n    slip = slip_ticks*tick\n    n = len(b.c); trades = []", 1)],
                     run_slip=("def run(b: Bars, t, bid, ask, det, exa, gb, gs, s: Strat", "def metrics(", (3, 3, 1, 1)))
    b60 = F.bars_from_ticks(t, bid, 3600000); b120 = F.resample(b60, 2); b240 = F.resample(b60, 4); fp = F.SigParams(spread_pts=SPREAD)
    SIGS = {"Turn_Predict_Squares": dict(sigMode="Turn", turnEntry="Predict"), "Turn_AtCross": dict(sigMode="Turn", turnEntry="AtCross"), "Turn_AfterHold": dict(sigMode="Turn", turnEntry="AfterHold"),
            "Square": dict(sigMode="Square"), "Tick": dict(sigMode="Tick"), "CONT_Close": dict(sigMode="CONT", contEntry="Close"), "CONT_Stop": dict(sigMode="CONT", contEntry="Stop")}
    EXITS = {"Points_default": dict(exitUnit="Points"), "ATR_default_2.0_2R_4.0_0.2": dict(exitUnit="ATR", slAtrM=2.0, tpR=2.0, trActAtr=4.0, trDisAtr=0.2),
             "ATR_1.5_2R_1.0_0.5": dict(exitUnit="ATR", slAtrM=1.5, tpR=2.0, trActAtr=1.0, trDisAtr=0.5), "ATR_2.5_2R_1.0_0.5": dict(exitUnit="ATR", slAtrM=2.5, tpR=2.0, trActAtr=1.0, trDisAtr=0.5),
             "ATR_1.0_3R_notrail": dict(exitUnit="ATR", slAtrM=1.0, tpR=3.0, trailOn=False)}
    REVS = {"off": dict(lossRevOn=False), "any+tiny": dict(lossRevOn=True, lossRevWhat="Any", lossRevTiny=True), "SLtrail+tiny": dict(lossRevOn=True, lossRevWhat="SL", lossRevTiny=True), "any_notiny": dict(lossRevOn=True, lossRevWhat="Any", lossRevTiny=False)}
    cache = {}
    for rank, r in enumerate(rows, 1):
        m_ = re.fullmatch(r"(\w+), ([\w.]+), lossrev ([\w+]+), filter (off|on)", r["settings"]); sig, ex, rev, f = m_.groups(); tfn = r["tf"]
        if tfn not in cache:
            chart = F.bars_from_ticks(t, bid, TFM[tfn]*60000)
            cache[tfn] = dict(chart=chart, det=M.detect_all(chart, M.Det(armEvery=False), TICK), exa=M.ex_atr(chart, 14), gate=M.fgf_gate(chart, b60, b120, b240, fp, TICK, enabled=True))
        C = cache[tfn]; gb, gs, _ = C["gate"]
        st = M.Strat(**SIGS[sig], **EXITS[ex], **REVS[rev], fgf=(f == "on"))
        for c, s in LEVELS:
            tr, info = M.run(C["chart"], t, bid, ask, C["det"], C["exa"], gb, gs, st, lots=LOTS, unit=UNIT, comm_side=c, tick=TICK, slip_ticks=s)
            rec(rank, r, c, s, M.metrics(tr, LOTS, UNIT), tr)
        print(KEY, rank, r["tf"], r["settings"], "base net", out[-7]["net"], "vs screen", r["net"], round(time.time()-t0), "s", flush=True)

else:
    import fg5 as F
    sys.path.insert(0, os.path.join(ROOT, "sm92")); import sm92 as M0
    V = load_patched(os.path.join(ROOT, "v28", "v28.py"), "v28s",
                     [("comm_side=0.30, tick=0.01):\n    n = len(chart.c); trades = []", "comm_side=0.30, tick=0.01, slip_ticks=0):\n    slip = slip_ticks*tick\n    n = len(chart.c); trades = []", 1)],
                     run_slip=("def run(chart, t, bid, ask, bar_entries, atr, gb, gs, ex: Exits", None, (2, 2, 1, 1)))
    b60 = F.bars_from_ticks(t, bid, 3600000); b120 = F.resample(b60, 2); b240 = F.resample(b60, 4); fp = F.SigParams(spread_pts=SPREAD)
    EXITS = {"ATR_default_3.0_1R_trail1.0_0.75": V.Exits(), "ATR_2.0_2R_notrail": V.Exits(sl=2.0, tpR=2.0, trail=False), "ATR_1.0_3R_notrail": V.Exits(sl=1.0, tpR=3.0, trail=False),
             "ATR_1.5_2R_trail1.0_0.5": V.Exits(sl=1.5, tpR=2.0, trail=True, act=1.0, dist=0.5), "Points_default": V.Exits(unit="Points")}
    cache = {}
    for rank, r in enumerate(rows, 1):
        m_ = re.fullmatch(r"(chart\+READ|chart only|every rung), info (enter|off), reverse (off|on), ([\w.]+), maxOpen (\d+), filter (off|on)", r["settings"]); rung, inf, rev, ex, mo, f = m_.groups(); tfn = r["tf"]
        if tfn not in cache:
            chart = F.bars_from_ticks(t, bid, TFM[tfn]*60000)
            events, readAt, cidx = V.ladder_events(chart, t, bid, TFM[tfn]*60, ext=None)
            cache[tfn] = dict(chart=chart, events=events, readAt=readAt, cidx=cidx, atr=F.atr(chart.h, chart.l, chart.c, 14), gate=M0.fgf_gate(chart, b60, b120, b240, fp, TICK, enabled=True))
        C = cache[tfn]; gb, gs, _ = C["gate"]
        mode = "every" if rung == "every rung" else "chart"; read = rung == "chart+READ"
        be = [V.entries_for(ev, b, C["readAt"][b], C["cidx"], mode, inf == "enter", rev == "on", lblRead=read) for b, ev in enumerate(C["events"])]
        for c, s in LEVELS:
            tr = V.run(C["chart"], t, bid, ask, be, C["atr"], gb, gs, EXITS[ex], maxOpen=int(mo), fgf=(f == "on"), lots=LOTS, unit=UNIT, comm_side=c, tick=TICK, slip_ticks=s)
            rec(rank, r, c, s, M0.metrics(tr, LOTS, UNIT), tr)
        print(KEY, rank, r["tf"], r["settings"], "base net", out[-7]["net"], "vs screen", r["net"], round(time.time()-t0), "s", flush=True)

df = pd.DataFrame(out); df.to_csv(os.path.join(ROOT, "stress", f"stress_{KEY}.csv"), index=False)
base = df[(df.comm_side == 0.30) & (df.slip_ticks == 0)]
print("BASE MATCH:", [(int(a), round(float(b), 3), round(float(c), 3)) for a, b, c in zip(base["rank"], base.net, base.screen_net)])
print("done", round(time.time()-t0), "s")
