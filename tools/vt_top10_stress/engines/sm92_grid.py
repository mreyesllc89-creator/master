import numpy as np, pandas as pd, sys, itertools, time
sys.path.insert(0, "."); from sm92 import *
sym = sys.argv[1]
SPEC = {"XAUUSD-ECNc": dict(unit=1.0, spread_pts=13.0), "BTCUSD.c": dict(unit=0.01, spread_pts=1703.0)}[sym]
z = np.load(f"../{sym}_ticks.npz"); t = z["t"]; bid = z["bid"]; ask = z["ask"]; tick = 0.01
b60 = bars_from_ticks(t, bid, 3600000); b120 = resample(b60, 2); b240 = resample(b60, 4)
fp = SigParams(spread_pts=SPEC["spread_pts"])
rows = []; t0 = time.time()
EXITS = {"Points_default": dict(exitUnit="Points"),
         "ATR_default_2.0_2R_4.0_0.2": dict(exitUnit="ATR", slAtrM=2.0, tpR=2.0, trActAtr=4.0, trDisAtr=0.2),
         "ATR_1.5_2R_1.0_0.5": dict(exitUnit="ATR", slAtrM=1.5, tpR=2.0, trActAtr=1.0, trDisAtr=0.5),
         "ATR_2.5_2R_1.0_0.5": dict(exitUnit="ATR", slAtrM=2.5, tpR=2.0, trActAtr=1.0, trDisAtr=0.5),
         "ATR_1.0_3R_notrail": dict(exitUnit="ATR", slAtrM=1.0, tpR=3.0, trailOn=False)}
SIGS = {"Turn_Predict_Squares": dict(sigMode="Turn", turnEntry="Predict"), "Turn_Predict_EveryCross": dict(sigMode="Turn", turnEntry="Predict"),
        "Turn_AtCross": dict(sigMode="Turn", turnEntry="AtCross"), "Turn_AfterHold": dict(sigMode="Turn", turnEntry="AfterHold"),
        "Square": dict(sigMode="Square"), "Tick": dict(sigMode="Tick"), "CONT_Close": dict(sigMode="CONT", contEntry="Close"), "CONT_Stop": dict(sigMode="CONT", contEntry="Stop")}
REVS = {"off": dict(lossRevOn=False), "any+tiny": dict(lossRevOn=True, lossRevWhat="Any", lossRevTiny=True),
        "SLtrail+tiny": dict(lossRevOn=True, lossRevWhat="SL", lossRevTiny=True), "any_notiny": dict(lossRevOn=True, lossRevWhat="Any", lossRevTiny=False)}
for tfn, tfm in {"M5": 5, "M15": 15, "M30": 30, "H1": 60}.items():
    chart = bars_from_ticks(t, bid, tfm*60000); n = len(chart.c)
    dets = {False: detect_all(chart, Det(armEvery=False), tick), True: detect_all(chart, Det(armEvery=True), tick)}
    exa = ex_atr(chart, 14)
    gb, gs, _ = fgf_gate(chart, b60, b120, b240, fp, tick, enabled=True)
    med_atr = float(np.nanmedian(exa))
    for (sname, sk), (ename, ek), (rname, rk), fg in itertools.product(SIGS.items(), EXITS.items(), REVS.items(), (False, True)):
        st = Strat(**sk, **ek, **rk, fgf=fg)
        det = dets[sname == "Turn_Predict_EveryCross"]
        tr, info = run(chart, t, bid, ask, det, exa, gb, gs, st, lots=0.1, unit=SPEC["unit"], comm_side=0.30, tick=tick)
        m = metrics(tr, 0.1, SPEC["unit"])
        rows.append(dict(symbol=sym, tf=tfn, signal=sname, exits=ename, lossrev=rname, fgf=fg, placed=info["placed"], blocked=info["blocked"], med_atr=med_atr, **m))
    print(sym, tfn, "done", len(rows), round(time.time()-t0), "s", flush=True)
pd.DataFrame(rows).to_csv(f"grid92_{sym}.csv", index=False); print("saved")
