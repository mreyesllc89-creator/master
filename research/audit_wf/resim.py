"""Re-simulation of all 12000 setups of one timeframe (single process), for three audit tests.

mode placebo : (a) the 59 real masks, aggregated with the module's aggregate(), must equal the stored array;
               (b) placebo masks (same selection and pass rule later, in wfcore):
                   SHIFT r=0,1 : each bar-decided condition (regime, location, confirmation, xlzc; 45) read at the bar
                                 S bars earlier (circular; S random in [10%, 90%] of the series, one S per condition
                                 and replicate): same per-bar structure and clustering, no link to the signals;
                   TOFF  r=0,1 : each timing condition (10) evaluated on an entry clock displaced by a random whole
                                 number of hours per calendar day and a random weekday shift per week;
                   KEEP        : every condition (55) as an independent per-bar random mask with the condition's own
                                 keep share (measured on the real masks);
               (c) the 59 real masks aggregated WITHOUT trades whose exit falls in a later calendar year than their
                   entry (the year-boundary overlap between a calibration year and the next year).
mode anchor:<p0> : outcomes with the price anchor set to p0 (ps and the spread rescaled), real masks only.

Arrays go to <out_dir>/<name>_<TF>.npy (float32 [setups, masks, cost, year, 4]); evaluation happens elsewhere.
Usage: [HUMP_SYMBOL=BTCUSD] python3 resim.py <work> <TF> <mode> <out_dir> [n_setups]
"""
import json, os, pickle, resource, sys, time
import numpy as np
import numba as nb

work, tf, mode, out_dir = sys.argv[1:5]
NSET = int(sys.argv[5]) if len(sys.argv) > 5 else 12000
sys.path.insert(0, "/workspace/master/research")
import hump_wf as W

os.makedirs(out_dir, exist_ok=True)
sym = "btc" if W.BTC else "gold"
t0 = time.time()
W.MK = MK = W.Mk(work)
p0_file = MK.p0
if mode.startswith("anchor:"):
    p0_new = float(mode.split(":")[1])
    k = p0_file / p0_new
    MK.ps = MK.ps * k
    MK.hs = MK.hs * k
    print(f"anchor {p0_file:.4f} -> {p0_new:.4f}: ps and half spread x {k:.6f}", flush=True)
F = MK.feat(tf)
d = pickle.load(open(os.path.join(work, f"wf_{tf}_params.pkl"), "rb"))
cand = W.candidates(tf, 12000)
assert cand == d["params"] and d["keys"] == W.KEYS and d["years"] == MK.years, "stored params are not candidates(tf, 12000)"
stored = np.load(os.path.join(work, f"wf_{tf}.npy"), mmap_mode="r")
NC = len(W.CONDS); ny = len(MK.years)
GROUP = [c[1] for c in W.CONDS]
BAR = [v for v in range(NC) if GROUP[v] in ("regime", "location", "confirmation", "xlzc")]
TIM = [v for v in range(NC) if GROUP[v] == "timing"]
REAL55 = BAR + TIM
assert len(BAR) == 45 and len(TIM) == 10


@nb.njit(cache=True)
def aggregate_noboundary(masks, kidx, e, j, r, costr, yr, ny):
    """The module's aggregate() (one position at a time, sums per entry year) except that a trade whose exit is in a
    later year than its entry is not counted (it still blocks new entries while open)."""
    nv = masks.shape[0]
    out = np.zeros((nv, ny, 4))
    for v in range(nv):
        busy = -1
        for i in range(len(e)):
            if not masks[v, kidx[i]] or e[i] <= busy:
                continue
            busy = j[i]
            y = yr[e[i]]
            if yr[j[i]] != y:
                continue
            out[v, y, 0] += 1.0
            if r[i] > 0:
                out[v, y, 1] += r[i]
            else:
                out[v, y, 2] -= r[i]
            out[v, y, 3] += costr[i]
    return out


placebo = mode == "placebo"
tt = MK._tf[tf]["t"].index.values
nbar = len(tt)
rs = np.random.default_rng(777 + (1 if W.BTC else 0) + 10 * W.TFS.index(tf))
names = []
if placebo:
    allb = np.arange(nbar); dum = np.zeros(nbar, np.int64)
    CB = np.empty((len(BAR), nbar), np.bool_); CS = np.empty((len(BAR), nbar), np.bool_)
    for a, v in enumerate(BAR):
        CB[a] = W.CONDS[v][3](F, allb, np.ones(nbar, np.int8), dum, dum)
        CS[a] = W.CONDS[v][3](F, allb, -np.ones(nbar, np.int8), dum, dum)
    SH = rs.integers(int(0.1 * nbar), int(0.9 * nbar), (2, len(BAR)))
    tmin = MK.t.astype("datetime64[m]").astype(np.int64)
    dayn = tmin // 1440; dayn = dayn - dayn[0]
    dow0 = int(MK.dow[0]); weekn = (dayn + dow0) // 7
    WD = 7 if W.BTC else 5
    OFFD = rs.integers(0, 24, (2, int(dayn.max()) + 1)) * 60
    OFFW = rs.integers(0, WD, (2, int(weekn.max()) + 1))
    U8 = rs.integers(0, 256, (len(REAL55), nbar), dtype=np.uint8)
    # keep shares of the real conditions, from the first setups with signals
    ks = np.zeros(NC); kn = 0
    for p in cand[:400]:
        c, sg, ix, er = W.prepare(p)
        if len(sg):
            ks += W.masks_of(tf, ix, sg[:, 1].astype(np.int8), er).sum(axis=1); kn += len(ix)
    share = ks / max(kn, 1)
    thr = np.array([min(255, int(round(share[v] * 256))) for v in REAL55], np.int64)
    names = [f"SHIFT{r}:{W.KEYS[v]}" for r in range(2) for v in BAR] + [f"TOFF{r}:{W.KEYS[v]}" for r in range(2) for v in TIM] + \
            [f"KEEP:{W.KEYS[v]}" for v in REAL55]
    NPL = len(names)
    PL = np.lib.format.open_memmap(os.path.join(out_dir, f"placebo_{sym}_{tf}.npy"), mode="w+", dtype=np.float32, shape=(NSET, NPL, 2, ny, 4))
    NB = np.lib.format.open_memmap(os.path.join(out_dir, f"noboundary_{sym}_{tf}.npy"), mode="w+", dtype=np.float32, shape=(NSET, NC, 2, ny, 4))
else:
    AN = np.lib.format.open_memmap(os.path.join(out_dir, f"anchor_{sym}_{tf}.npy"), mode="w+", dtype=np.float32, shape=(NSET, NC, 2, ny, 4))
print(f"{sym} {tf} {mode}: ready in {time.time() - t0:.0f}s, {nbar} bars, {len(names)} placebo masks", flush=True)

n_diff = 0; max_abs = 0.0; n_mask_chk = 0; n_sig = 0; n_boundary = np.zeros(2); r_boundary = np.zeros(2)
for i in range(NSET):
    p = cand[i]
    c, sg, ix, er = W.prepare(p)
    if not len(sg):
        if placebo:
            assert not np.asarray(stored[i]).any()
        continue
    s = sg[:, 1].astype(np.int8)
    M = W.masks_of(tf, ix, s, er)
    n_sig += len(ix)
    if placebo:
        buy = s > 0
        ok = er >= 0; erc = np.clip(er, 0, None)
        te = np.where(ok, MK.tod[erc], -10000); de = np.where(ok, MK.dow[erc], -1)
        Mp = np.empty((NPL, len(ix)), np.bool_)
        row = 0
        for r in range(2):
            for a in range(len(BAR)):
                jx = (ix - SH[r, a]) % nbar
                Mp[row] = np.where(buy, CB[a][jx], CS[a][jx]); row += 1
        for r in range(2):
            te2 = np.where(ok, (te + OFFD[r][dayn[erc]]) % 1440, -10000)
            de2 = np.where(ok, (de + OFFW[r][weekn[erc]]) % WD, -1)
            for v in TIM:
                Mp[row] = W.CONDS[v][3](F, ix, s, te2, de2); row += 1
        for a in range(len(REAL55)):
            Mp[row] = U8[a][ix] < thr[a]; row += 1
        if n_mask_chk < 60:                                    # my per-bar gather against the module's masks
            for a, v in enumerate(BAR):
                assert np.array_equal(np.where(buy, CB[a][ix], CS[a][ix]), M[v])
            n_mask_chk += 1
    res = np.zeros((NC, 2, ny, 4)); resp = np.zeros((len(names), 2, ny, 4)) if placebo else None; resb = np.zeros((NC, 2, ny, 4)) if placebo else None
    for ci, cost in enumerate(W.COSTS):
        o = W.run_outcomes(c, sg, er, cost)
        if not len(o):
            continue
        kk = o[:, 0].astype(np.int64); e = o[:, 1].astype(np.int64); j = o[:, 2].astype(np.int64)
        res[:, ci] = W.aggregate(M, kk, e, j, o[:, 4], o[:, 6], MK.year, ny)
        if placebo:
            resp[:, ci] = W.aggregate(Mp, kk, e, j, o[:, 4], o[:, 6], MK.year, ny)
            resb[:, ci] = aggregate_noboundary(M, kk, e, j, o[:, 4], o[:, 6], MK.year, ny)
    if placebo:
        st = np.asarray(stored[i])
        if not np.array_equal(res.astype(np.float32), st):
            n_diff += 1; max_abs = max(max_abs, float(np.abs(res.astype(np.float32) - st).max()))
            if n_diff <= 3:
                print("STORED ARRAY DIFFERS", tf, i, max_abs, flush=True)
        PL[i] = resp; NB[i] = resb
        n_boundary += (res[0, :, :, 0] - resb[0, :, :, 0]).sum(axis=1)
        r_boundary += np.abs(res[0, :, :, 1] - resb[0, :, :, 1]).sum(axis=1) + np.abs(res[0, :, :, 2] - resb[0, :, :, 2]).sum(axis=1)
    else:
        AN[i] = res
    if i % 1000 == 0 or i == NSET - 1:
        print(f"  {sym} {tf} {mode} setup {i}: {time.time() - t0:.0f}s, maxrss {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024} MB", flush=True)
summary = dict(symbol=sym, tf=tf, mode=mode, nset=NSET, signals=int(n_sig), anchor_file=p0_file, seconds=round(time.time() - t0))
if placebo:
    PL.flush(); NB.flush()
    summary.update(placebo_names=names, keep_share={W.KEYS[v]: float(share[v]) for v in range(NC)}, stored_rows_differing=n_diff, max_abs_diff=max_abs,
                   mask_checks=n_mask_chk, boundary_trades_base_cond_by_cost=n_boundary.tolist(), boundary_abs_r_base_cond_by_cost=r_boundary.tolist(),
                   shifts=SH.tolist())
else:
    AN.flush(); summary.update(anchor_new=p0_new)
json.dump(summary, open(os.path.join(out_dir, f"resim_{sym}_{tf}_{mode.replace(':', '_')}.json"), "w"), indent=1)
print("RESIM_DONE", json.dumps({k: v for k, v in summary.items() if k not in ("placebo_names", "keep_share", "shifts")}), flush=True)
