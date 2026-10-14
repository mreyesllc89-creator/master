import numpy as np, pandas as pd, sys, itertools, time, json
sys.path.insert(0, "."); from fg5 import *
sym = sys.argv[1]
SPEC = {"XAUUSD-ECNc": dict(unit=1.0, spread_pts=13.0), "BTCUSD.c": dict(unit=0.01, spread_pts=1703.0)}[sym]
z = np.load(f"../{sym}_ticks.npz"); t = z["t"]; bid = z["bid"]; ask = z["ask"]; mid = (bid + ask)/2
tick = 0.01
cost = Costs(qty=0.1, unit=SPEC["unit"], comm_side_per_qty=0.30, comm_pct=0.0, slip_ticks=0, tick=tick)
rt_cost = 0.60*cost.qty + np.median(ask - bid)*cost.qty*cost.unit
# filter bars: H1 from ticks, zones H2/H4 (server-time aligned)
b60 = bars_from_ticks(t, mid, 3600000); b120 = resample(b60, 2); b240 = resample(b60, 4)
rows = []; t0 = time.time()
TFS = {"M5": 5, "M15": 15, "M30": 30, "H1": 60}
for tfn, tfm in TFS.items():
    chart = bars_from_ticks(t, mid, tfm*60000); z2 = resample(chart, 2); z3 = resample(chart, 4)
    bursts = {}
    for bm in (0.3, 0.5, 0.7):
        bursts[bm] = signal(chart, z2, z3, SigParams(spread_pts=SPEC["spread_pts"], burst_atr=bm), tick)
    sig_nozone = signal(chart, z2, z3, SigParams(spread_pts=SPEC["spread_pts"], use_zones=False), tick)
    fp = SigParams(spread_pts=SPEC["spread_pts"])
    gates = {"off": fgf_gate(chart, b60, b120, b240, fp, tick, enabled=False)[:2], "on": fgf_gate(chart, b60, b120, b240, fp, tick, enabled=True)[:2]}
    med_atr = float(np.nanmedian(bursts[0.5]["atr"]))
    configs = []
    # defaults audit
    for mode in ("Pips", "ATR", "Points"):
        for style in ("Partial + runner", "Fixed"):
            configs.append((f"DEF_{mode}_{'partial' if style[0]=='P' else 'fixed'}", 0.5, True, ExitParams(mode=mode, style=style)))
    configs.append(("DEF_ATR_partial_nozones", 0.5, "nozone", ExitParams(mode="ATR")))
    # ATR grid
    for sl, tpr, st, bm in itertools.product((0.1, 0.25, 0.5, 1.0, 2.0), (2.0, 3.0, 5.0), ("partial", "fixed", "fixedtrail"), (0.3, 0.5, 0.7)):
        xp = ExitParams(mode="ATR", sl_atr=sl, tpr_atr=tpr, style="Partial + runner" if st == "partial" else "Fixed", use_trail=(st == "fixedtrail"))
        configs.append((f"ATR_sl{sl}_tp{tpr}_{st}_b{bm}", bm, True, xp))
    # Pips grid (pip = 1.0 price unit, as shipped)
    for sl, rn in itertools.product((20, 30, 40), (450, 600, 800)):
        configs.append((f"PIPS_sl{sl}_run{rn}", 0.5, True, ExitParams(mode="Pips", sl_pips=sl, run_pips=rn)))
    for cid, bm, zones, xp in configs:
        sig = sig_nozone if zones == "nozone" else bursts[bm]
        for gname, (gb, gs) in gates.items():
            tr, info = run(chart, t, bid, ask, sig, gb, gs, xp, cost)
            m = metrics(tr, cost)
            rows.append(dict(symbol=sym, tf=tfn, config=cid, filter=gname, mode=xp.mode, style=xp.style, sl=xp.sl_atr if xp.mode == "ATR" else (xp.sl_pips if xp.mode == "Pips" else xp.sl_pts),
                             tpr=xp.tpr_atr if xp.mode == "ATR" else xp.tpr_pips, burst=bm, zones=zones, placed=info["placed"], blocked=info["blocked"], med_atr=med_atr, rt_cost=rt_cost,
                             **{k: m.get(k) for k in ("trades", "net", "gross", "fee", "pf", "win", "maxdd", "pos_weeks", "weeks", "halves", "meanR", "sumR", "longs", "shorts")},
                             reasons=json.dumps(m.get("reasons", {}))))
    print(sym, tfn, "done", len(rows), "rows", round(time.time() - t0), "s", flush=True)
pd.DataFrame(rows).to_csv(f"grid_{sym}.csv", index=False); print("saved")
