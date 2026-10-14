import numpy as np, pandas as pd, sys, itertools, time
sys.path.insert(0, "."); from v28 import *
from fg5 import atr as atr14
sys.path.insert(0, "../sm92"); from sm92 import metrics
sym = sys.argv[1]; crossfeed = len(sys.argv) > 2 and sys.argv[2] == "mexc"
SPEC = {"XAUUSD-ECNc": dict(unit=1.0, spread_pts=13.0), "BTCUSD.c": dict(unit=0.01, spread_pts=1703.0)}[sym]
z = np.load(f"../{sym}_ticks.npz"); t = z["t"]; bid = z["bid"]; ask = z["ask"]; tick = 0.01
ext = None
if crossfeed:
    D = "../data/5e97dff0-MEXC_BTCUSDT_1D_59719/"
    def tv(name, tfms):
        d = pd.read_csv(D + name); tt = pd.to_datetime(d["time"], utc=True).values.astype("datetime64[ms]").astype("int64")
        return Bars(tt, d.open.values, d.high.values, d.low.values, d.close.values, tfms)
    d1 = tv("MEXC_BTCUSDT, 1D_59719.csv", 86400000); w1 = tv("MEXC_BTCUSDT, 1W_2431e.csv", 7*86400000)
    dd = pd.DataFrame(dict(t=pd.to_datetime(d1.t, unit="ms"), o=d1.o, h=d1.h, l=d1.l, c=d1.c)).set_index("t")
    m = dd.resample("MS").agg(o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last")).dropna()
    mt = m.index.values.astype("datetime64[ms]").astype("int64"); mclose = (m.index + pd.offsets.MonthBegin(1)).values.astype("datetime64[ms]").astype("int64")
    mn = Bars(mt, m.o.values, m.h.values, m.l.values, m.c.values, 0); mn.tclose_arr = mclose
    # month bars have variable length: store close times via tf_ms=0 and patch rung_state's tclose below
    ext = {"1 Day": d1, "1 Week": w1, "1 Month": mn}; ext_close = {"1 Month": mclose}
b60 = bars_from_ticks(t, bid, 3600000); b120 = resample(b60, 2); b240 = resample(b60, 4); fp = SigParams(spread_pts=SPEC["spread_pts"])
EXITS = {"ATR_default_3.0_1R_trail1.0_0.75": Exits(), "ATR_2.0_2R_notrail": Exits(sl=2.0, tpR=2.0, trail=False), "ATR_1.0_3R_notrail": Exits(sl=1.0, tpR=3.0, trail=False),
         "ATR_1.5_2R_trail1.0_0.5": Exits(sl=1.5, tpR=2.0, trail=True, act=1.0, dist=0.5), "Points_default": Exits(unit="Points")}
rows = []; t0 = time.time()
for tfn, tfm in {"M5": 5, "M15": 15, "M30": 30, "H1": 60}.items():
    chart = bars_from_ticks(t, bid, tfm*60000); n = len(chart.c)
    events, readAt, cidx = ladder_events(chart, t, bid, tfm*60, ext=ext)
    a = atr14(chart.h, chart.l, chart.c, 14)
    gb, gs, _ = fgf_gate(chart, b60, b120, b240, fp, tick, enabled=True)
    for (mode, read), info, rev in itertools.product([("chart", True), ("chart", False), ("every", False)], (True, False), (False, True)):
        be = [entries_for(ev, b, readAt[b], cidx, mode, info, rev, lblRead=read) for b, ev in enumerate(events)]
        nsig = sum(1 for L, S in be if (L and not S) or (S and not L))
        for (ename, ex), mo, fg in itertools.product(EXITS.items(), (20, 1), (False, True)):
            tr = run(chart, t, bid, ask, be, a, gb, gs, ex, maxOpen=mo, fgf=fg, lots=0.1, unit=SPEC["unit"], comm_side=0.30, tick=tick)
            m = metrics(tr, 0.1, SPEC["unit"])
            rows.append(dict(symbol=sym, feed="VT+MEXC D/W/M" if crossfeed else "VT only (D/W/M unavailable)", tf=tfn, rung_mode=("chart+READ" if (mode == "chart" and read) else ("chart only" if mode == "chart" else "every rung")),
                             info_labels=("enter" if info else "off"), reverse_all=rev, exits=ename, max_open=mo, fgf=fg, signal_bars=nsig, **m))
    print(sym, "mexc" if crossfeed else "vt", tfn, "done", len(rows), round(time.time()-t0), "s", flush=True)
pd.DataFrame(rows).to_csv(f"grid28_{sym}{'_mexc' if crossfeed else ''}.csv", index=False); print("saved")
