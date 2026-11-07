#!/usr/bin/env python3
"""
Backtest the XLZC EA with and without the FlashGold Direction Filter v1.2.

Stage 1  (fgf grid): every FlashGold input combination below x three base EA setups.
Stage 2  (cross)   : selected FlashGold settings x a broad EA grid over all 13
                     trigger/HTF pairs, each paired with the unfiltered run.

The filter gate is applied at the EA's entry time (first tick of the bar after
the signal bar) with the live bid, exactly where the EA calls FGFAllowsSell().
Everything else is the same simulator as xlzc_calibrate.py.

Usage:
  python3 fgf_backtest.py stage1 <data_dir> <out_dir>
  python3 fgf_backtest.py stage2 <data_dir> <out_dir> <fgf_list.json>
"""
import itertools
import json
import os
import sys
from dataclasses import asdict
from multiprocessing import Pool

import numpy as np
import pandas as pd

import fgf_port as F
import xlzc_backtest as B
import xlzc_calibrate as C

CHOSEN = dict(tf="M3/H1", N=40, S=2, buffer=120, NT=120, min_rr=1.5, fb=0.0, stoch="soft",
              session="ny_12-1630", trail=True)
BASES = {
    "M3/H1 chosen": CHOSEN,
    "M2/H1 same inputs": dict(CHOSEN, tf="M2/H1"),
    "M1/M15 shipped defaults": dict(tf="M1/M15", N=25, S=2, buffer=40, NT=0, min_rr=1.0, fb=0.0,
                                    stoch="soft", session="ny_12-1630", trail=False),
}

# Inputs that change the filter itself (one build each) ...
BUILD_GRID = dict(
    filter_tf=["M15", "M30", "H1", "H4"],
    parent=["H1", "same"],                 # indicator default parent is H1 whatever the filter TF
    level_mode=[0, 1],
    zones=["off", "align1", "align2", "align3"],
    any_combo=[False, True],
    burst_atr=[0.25, 0.5, 1.0],
    hold_bars=[0, 2],
)
# ... and inputs that only change the gate the EA reads (cheap, share one build).
GATE_GRID = dict(
    band_atr=[0.0, 0.25, 0.5, 1.0],
    window=["next", "min60", "min240", "bars1", "bars3"],
    against=[True, False],
    check=[0, 1, 2],                       # 0 tick, 1 bar open, 2 previous bar close
)
WINDOWS = {"next": (0, 60, 1), "min60": (1, 60, 1), "min240": (1, 240, 1), "bars1": (2, 60, 1), "bars3": (2, 60, 3)}
ZONES = {"off": (False, 2), "align1": (True, 1), "align2": (True, 2), "align3": (True, 3)}
DEFAULT_LABEL = dict(filter_tf="H1", parent="H1", level_mode=0, zones="align2", any_combo=False, burst_atr=0.5,
                     hold_bars=0, band_atr=0.25, window="next", against=True, check=0)


def cfg_from_label(lab):
    w = WINDOWS[lab["window"]]; z = ZONES[lab["zones"]]
    parent = lab["filter_tf"] if lab["parent"] == "same" else lab["parent"]
    return F.FgfConfig(filter_tf=lab["filter_tf"], parent_tf=parent, level_mode=lab["level_mode"],
                       use_zones=z[0], min_aligned=z[1], any_combo=lab["any_combo"], burst_atr=lab["burst_atr"],
                       hold_bars=lab["hold_bars"], band_atr=lab["band_atr"], window_mode=w[0], minutes=w[1],
                       bars=w[2], against=lab["against"], check_mode=lab["check"])


def build_labels():
    out = []
    for vals in itertools.product(*BUILD_GRID.values()):
        lab = dict(zip(BUILD_GRID, vals))
        if lab["filter_tf"] == "H1" and lab["parent"] == "same":
            continue                          # identical to parent H1
        out.append(lab)
    return out


def gate_labels():
    return [dict(zip(GATE_GRID, v)) for v in itertools.product(*GATE_GRID.values())]


# ----------------------------------------------------------------------------- shared setup
W = {}


def prepare(data_dir, pairs):
    m1, hs = B.load(data_dir)
    path = B.M1Path(m1, hs)
    sigs, sls, pools, entry = {}, {}, {}, {}
    for pair in pairs:
        trig, htf = pair.split("/")
        t, sig = B.build_signals(m1, trig, htf)
        mi = np.searchsorted(path.t, sig["entry_time"].values)
        tol = np.timedelta64(B.TF_MIN[trig], "m")
        ok = (mi < len(path.t))
        mi = np.where(ok & (path.t[np.clip(mi, 0, len(path.t) - 1)] - sig["entry_time"].values <= tol), mi, -1)
        et = sig["entry_time"]
        sigs[pair] = dict(bias=sig["bias"].values, stoch_ok=sig["stoch_ok"].values, et=et.values,
                          tod=(et.dt.hour * 60 + et.dt.minute).values, mi=mi)
        mic = np.clip(mi, 0, len(path.t) - 1)
        prev_bar = np.clip(sig["entry_bar"].values - 1, 0, len(t) - 1)
        entry[pair] = dict(t=path.t[mic].astype("datetime64[s]").astype(np.int64),
                           bid=path.o[mic] - path.hs[mic],
                           prev_close=t["close"].values[prev_bar] - path.hs[mic])
        for S in C.SS:
            shf, slf = B.swing_flags(t["high"].values, t["low"].values, S)
            pools[(pair, S)] = C.low_pools(t, sig, S, slf)
            for N in C.NS:
                sls[(pair, N, S)] = C.sl_structure(t, sig, N, S, shf)
    eng = F.FgfEngine(m1)
    for tf in ["M15", "M30", "H1", "H2", "H4"]:
        eng.bars(tf); eng.dirs(tf, 14, 2)
    return dict(sig=sigs, sls=sls, pools=pools, path=path, entry=entry, eng=eng)


def init_worker(payload):
    W.update(payload)
    C.G.update(sig=dict(payload["sig"]), sls=payload["sls"], pools=payload["pools"], path=payload["path"])


def run_with_mask(base_cfg, mask):
    pair = base_cfg["tf"]
    orig = W["sig"][pair]
    if mask is None:
        C.G["sig"][pair] = orig
    else:
        C.G["sig"][pair] = dict(orig, bias=orig["bias"] & mask)
    _, trades = C.run_cfg(base_cfg)
    C.G["sig"][pair] = orig
    return trades


def build_key(cfg):
    # gate-only fields do not change the filter build
    from dataclasses import replace
    return replace(cfg, band_atr=0.0, window_mode=0, minutes=60, bars=1, against=True, check_mode=0)


def fgf_mask(cfg, pair, state_cache):
    key = build_key(cfg)
    st = state_cache.get(key)
    if st is None:
        st = W["eng"].build(cfg)
        state_cache.clear(); state_cache[key] = st
    e = W["entry"][pair]
    return F.sell_allowed(cfg, st, e["t"], e["bid"], e["prev_close"])


def stage1_job(blab):
    cache = {}
    rows = []
    for glab in gate_labels():
        lab = dict(blab, **glab)
        cfg = cfg_from_label(lab)
        for name, base in BASES.items():
            mask = fgf_mask(cfg, base["tf"], cache)
            tr = run_with_mask(base, mask)
            r = dict(lab); r["base"] = name; r.update(C.seg_stats(tr))
            r["gate_open_share"] = float(mask[W["sig"][base["tf"]]["bias"]].mean())
            rows.append(r)
    return rows


def stage2_job(item):
    fgf_id, label, cfg, base = item
    mask = None if cfg is None else fgf_mask(cfg, base["tf"], W.setdefault("s2cache", {}))
    tr = run_with_mask(base, mask)
    r = dict(base); r["fgf_id"] = fgf_id; r["fgf"] = json.dumps(label) if label else "off"
    r.update(C.seg_stats(tr))
    return r


def main():
    stage, data_dir, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(out_dir, exist_ok=True)
    if stage == "stage1":
        payload = prepare(data_dir, sorted({b["tf"] for b in BASES.values()}))
        init_worker(payload)
        base_rows = []
        for name, base in BASES.items():
            r = {"base": name, "fgf": "off"}; r.update(C.seg_stats(run_with_mask(base, None))); base_rows.append(r)
        pd.DataFrame(base_rows).to_csv(os.path.join(out_dir, "stage1_baselines.csv"), index=False)
        items = build_labels()
        print(f"stage1: {len(items)} filter builds x {len(gate_labels())} gate settings x {len(BASES)} bases",
              flush=True)
        rows = []
        with Pool(4, initializer=init_worker, initargs=(payload,)) as pool:
            for i, rs in enumerate(pool.imap_unordered(stage1_job, items, chunksize=1)):
                rows.extend(rs)
                if i % 50 == 0:
                    print(i, flush=True)
        pd.DataFrame(rows).to_csv(os.path.join(out_dir, "stage1_fgf_grid.csv"), index=False)
        print("done", len(rows))
    else:
        sel = json.load(open(sys.argv[4]))  # list of {"id":..., "label": {...}}
        payload = prepare(data_dir, C.PAIRS)
        fgfs = [(s["id"], s["label"], cfg_from_label(s["label"])) for s in sel]
        fgfs = [("off", None, None)] + fgfs
        bases = [dict(tf=p, N=N, S=S, buffer=buf, NT=nt, min_rr=rr, fb=0.0, stoch="soft", session=se, trail=tr)
                 for p, N, S, buf, nt, rr, se, tr in itertools.product(
                     C.PAIRS, C.NS, C.SS, [40, 80, 120], [60, 120], [1.0, 1.5, 2.0],
                     ["ny_12-1630", "ldn_ny_07-20", "all_day"], [False, True])]
        # group by (fgf, pair) so each worker reuses one filter build per run of items
        items = [(fid, lab, cfg, b) for fid, lab, cfg in fgfs for b in bases]
        print(f"stage2: {len(fgfs)} filter settings (incl. off) x {len(bases)} EA setups = {len(items)}", flush=True)
        rows = []
        with Pool(4, initializer=init_worker, initargs=(payload,)) as pool:
            for i, r in enumerate(pool.imap(stage2_job, items, chunksize=256)):
                rows.append(r)
                if i % 20000 == 0:
                    print(i, flush=True)
        pd.DataFrame(rows).to_csv(os.path.join(out_dir, "stage2_cross.csv"), index=False)
        print("done", len(rows))


if __name__ == "__main__":
    main()
