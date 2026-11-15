"""Prefix test of hump_wf.Feat (auditor 'features'). A window of the run's one-minute series is the 'whole series';
it is cut at many rows, everything is rebuilt on the cut series, and every feature value at every trigger bar that is
complete in the cut is compared with the whole-series value. Power: the same test applied to (a) every feature shifted
one bar forward, (b) mutants of my own implementation (mine.py) with known look-ahead.
Usage: [HUMP_SYMBOL=BTCUSD] python3 prefix.py <run folder> <window start> <window end> <cuts from> <TF,TF..> <out.json> [n_mut]"""
import json, os, sys, time
import numpy as np, pandas as pd
sys.path.insert(0, "/workspace/master/research")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hump_wf as W, hump_engine as H
import mine as M

work, ws, we, cf, tfs, out_json = sys.argv[1:7]
n_mut = min(20, int(sys.argv[7]) if len(sys.argv) > 7 else 20)
tfs = tfs.split(",")
NAMES = ["tr_h4", "tr_d1", "sl_h4", "sl_d1", "adx_h1", "adx_h4", "atrp", "pdr", "tdr", "pdpos", "dopen", "asia_pos", "nyor_pos",
         "rn", "bos_up", "bos_dn", "hm1", "hm2", "volr", "body_dir", "body_frac", "rng_atr", "xs_dn", "xs_up", "sw_dn", "sw_up"]
MUTANTS = ["htf_from_open", "today_not_yesterday", "range_before_complete", "pivot_unconfirmed", "shift_forward"]


class Light(H.Market):
    def __init__(self, m1):
        super().__init__(m1=m1[["open", "high", "low", "close"]], half_spread=np.zeros(len(m1)))
        self.vol = m1["vol"]

    def feat(self, name):
        self.tf(name)
        return W.Feat(self, name)


def same(a, b):
    a = np.asarray(a); b = np.asarray(b)
    if a.dtype.kind == "f" or b.dtype.kind == "f":
        a = a.astype(float); b = b.astype(float)
        with np.errstate(invalid="ignore"):
            return (np.isnan(a) & np.isnan(b)) | (a == b) | (np.abs(a - b) <= 1e-9 * np.maximum(1.0, np.abs(a)))
    return a == b


def shifted(a):
    a = np.asarray(a)
    fill = np.array([np.nan]) if a.dtype.kind == "f" else np.zeros(1, a.dtype)
    return np.r_[a[1:], fill]


full = pd.read_pickle(os.path.join(work, "m1.pkl"))
m1 = full[(full.index >= ws) & (full.index < we)].copy()
del full
idx = m1.index
tm = M.minutes(idx)
n = len(m1)
tod = tm % 1440; dow = ((tm // 1440) + 3) % 7
r0 = int(np.searchsorted(idx.values, np.datetime64(cf)))
rng = np.random.default_rng(20261115 + len(tfs))
print(f"{W.SYM} window {idx[0]} .. {idx[-1]}: {n} rows; cuts from row {r0} ({idx[r0]})", flush=True)

# ---------------------------------------------------------------- cut rows, by kind
cuts = {}
def add(kind, rows):
    for r in rows:
        r = int(r)
        if r0 <= r < n - 1:
            cuts.setdefault(r, set()).add(kind)

add("random", rng.integers(r0, n - 1, 14))
for tf in tfs:
    b = tm // M.TFM[tf]
    last = np.flatnonzero(np.diff(b)) ; first = last + 1             # last row of a bar / first row of the next one
    last = last[last >= r0]; first = first[first >= r0]
    add(f"bar_last_row_{tf}", rng.choice(last, 18, replace=False))
    add(f"bar_first_row_{tf}", rng.choice(first, 6, replace=False))
for hh, mm, nm in ((23, 59, "midnight"), (0, 0, "midnight"), (0, 1, "midnight"), (0, 59, "reopen"), (1, 0, "reopen"), (1, 5, "reopen"),
                   (8, 59, "0900"), (9, 0, "0900"), (9, 1, "0900"), (16, 29, "1630"), (16, 30, "1630"), (16, 31, "1630"),
                   (17, 29, "1730"), (17, 30, "1730"), (17, 31, "1730")):
    rows = np.flatnonzero((tod == hh * 60 + mm) & (np.arange(n) >= r0))
    if len(rows):
        add(nm, rng.choice(rows, min(3, len(rows)), replace=False))
gap = np.diff(tm)
for g, nm in ((24 * 60, "weekend"), (30, "break")):
    pos = np.flatnonzero(gap >= g)
    pos = pos[pos >= r0]
    if len(pos):
        pk = rng.choice(pos, min(5, len(pos)), replace=False)
        add(nm, pk); add(nm, pk + 1); add(nm, pk - 1)
if W.BTC:                                                             # BTC weekend days
    rows = np.flatnonzero((dow >= 5) & (np.arange(n) >= r0))
    add("weekend", rng.choice(rows, 10, replace=False))
# clock changes: the days of the US changes (2nd Sunday of March, 1st Sunday of November), the Friday before and the
# Monday after (calendar Sundays: gold has no Sunday bars)
norm = idx.normalize()
sundays = []
for y in range(idx[0].year, idx[-1].year + 1):
    mar = pd.Timestamp(year=y, month=3, day=8); mar += pd.Timedelta(days=(6 - mar.dayofweek) % 7)
    nov = pd.Timestamp(year=y, month=11, day=1); nov += pd.Timedelta(days=(6 - nov.dayofweek) % 7)
    sundays += [mar, nov]
for d in sundays:
    for dd in (d, d + pd.Timedelta(days=1), d - pd.Timedelta(days=2)):
        sel = np.flatnonzero(norm == dd)
        if len(sel):
            add("clock_change", [sel[0], sel[min(len(sel) - 1, 1)], sel[len(sel) // 3], sel[len(sel) // 2], sel[-1]])
    # around 08:50-10:10 server time of the change day (BTC: the lost / repeated hour)
    sel = np.flatnonzero((idx >= d + pd.Timedelta(hours=8, minutes=50)) & (idx <= d + pd.Timedelta(hours=10, minutes=10)))
    add("clock_change", sel[::5])
# data-source seams (gold)
for s in ("2025-01-02 01:05", "2026-05-18 01:00", "2026-05-15 23:49"):
    k = int(np.searchsorted(idx.values, np.datetime64(s)))
    if 0 < k < n:
        add("seam", [k - 1, k, k + 1, k + 30, k + 200])
rows = sorted(cuts)
kinds = {}
for r in rows:
    for k in cuts[r]:
        kinds[k] = kinds.get(k, 0) + 1
print(f"{len(rows)} cut rows; by kind {kinds}", flush=True)

# ---------------------------------------------------------------- whole window
t0 = time.time()
mk = Light(m1)
FULL = {}; BAR_LAST = {}; MINE_FULL = {}
for tf in tfs:
    F = mk.feat(tf)
    FULL[tf] = {nm: np.asarray(getattr(F, nm)).copy() for nm in NAMES}
    b = tm // M.TFM[tf]
    BAR_LAST[tf] = np.r_[np.flatnonzero(np.diff(b)), n - 1]           # last row of every trigger bar
    assert len(BAR_LAST[tf]) == len(FULL[tf]["tr_h4"])
    MINE_FULL[tf] = {} if os.environ.get("NO_MUT") else {mu: M.features(tm, m1.open.values, m1.high.values, m1.low.values, m1.close.values, m1.vol.values, tf, W.HTF_UP[tf], mutant=mu)["F"]
                     for mu in [None] + MUTANTS}
del mk
print(f"whole window built in {time.time() - t0:.0f}s", flush=True)

res = {tf: dict(cuts=0, cuts_exact_last_row=0, values=0, last_bar_values=0,
                bad={nm: [0, 0] for nm in NAMES}, last_notnan={nm: 0 for nm in NAMES},
                shift_fail={nm: 0 for nm in NAMES}, shift_cuts=0,
                mine_bad=0, mutant_fail={mu: 0 for mu in MUTANTS}, mutant_cuts=0, mutant_feat={mu: {} for mu in MUTANTS},
                fails=[]) for tf in tfs}
mut_rows = set(rng.choice(rows, min(n_mut, len(rows)), replace=False).tolist())
mut_rows |= {r for r in rows if cuts[r] & {"1630", "1730", "0900"}}
if os.environ.get("NO_MUT"):
    mut_rows = set()
t0 = time.time()
for q, r in enumerate(rows):
    part = m1.iloc[:r + 1]
    mk = Light(part)
    for tf in tfs:
        R = res[tf]
        F2 = mk.feat(tf)
        nc = int(np.searchsorted(BAR_LAST[tf], r, side="right"))   # bars whose last row is in the cut
        if nc < 2:
            continue
        exact = BAR_LAST[tf][nc - 1] == r
        R["cuts"] += 1; R["cuts_exact_last_row"] += int(exact)
        for nm in NAMES:
            a = FULL[tf][nm][:nc]; b = np.asarray(getattr(F2, nm))[:nc]
            ok = same(a, b)
            R["values"] += nc
            if not ok.all():
                R["bad"][nm][0] += 1; R["bad"][nm][1] += int((~ok).sum())
                if len(R["fails"]) < 30:
                    j = int(np.flatnonzero(~ok)[-1])
                    R["fails"].append(dict(tf=tf, cut=str(idx[r]), feature=nm, bar=j, full=str(a[j]), cut_value=str(b[j]), kinds=sorted(cuts[r])))
            last_full = a[nc - 1]
            R["last_notnan"][nm] += int(not (isinstance(last_full, float) and np.isnan(last_full)))
            # power: the same feature shifted one bar forward (its value at bar i is the value of bar i + 1)
            sa = shifted(FULL[tf][nm])[:nc]; sb = shifted(np.asarray(getattr(F2, nm)))[:nc]
            R["shift_fail"][nm] += int(not same(sa[nc - 1:nc], sb[nc - 1:nc]).all())
        R["last_bar_values"] += len(NAMES)
        R["shift_cuts"] += 1
        if r in mut_rows:
            R["mutant_cuts"] += 1
            for mu in [None] + MUTANTS:
                G2 = M.features(tm[:r + 1], part.open.values, part.high.values, part.low.values, part.close.values, part.vol.values, tf, W.HTF_UP[tf], mutant=mu)["F"]
                badf = [nm for nm in G2 if not same(MINE_FULL[tf][mu][nm][:nc], np.asarray(G2[nm])[:nc]).all()]
                if mu is None:
                    R["mine_bad"] += int(bool(badf))
                else:
                    R["mutant_fail"][mu] += int(bool(badf))
                    for nm in badf:
                        R["mutant_feat"][mu][nm] = R["mutant_feat"][mu].get(nm, 0) + 1
    del mk
    if q % 25 == 0:
        print(f"  {q}/{len(rows)} cuts, {time.time() - t0:.0f}s; failing so far: " +
              str({tf: {k: v for k, v in res[tf]['bad'].items() if v[0]} for tf in tfs}), flush=True)

out = dict(symbol=W.SYM, window=[str(idx[0]), str(idx[-1])], cuts_from=str(idx[r0]), n_cut_rows=len(rows), kinds=kinds, res=res)
json.dump(out, open(out_json, "w"), indent=1, default=str)
for tf in tfs:
    R = res[tf]
    print(f"== {W.SYM} {tf}: {R['cuts']} cuts ({R['cuts_exact_last_row']} exactly at a bar's last row), {R['values']} values compared")
    print("   feature: [cuts failing, values failing] / last bar not NaN / shifted-forward copy fails at the last bar (power)")
    for nm in NAMES:
        print(f"   {nm:10s} {R['bad'][nm]}  {R['last_notnan'][nm]:4d}  shift fails {R['shift_fail'][nm]:4d}/{R['shift_cuts']}")
    print(f"   my implementation on {R['mutant_cuts']} cuts: unmutated fails {R['mine_bad']}; mutants fail {R['mutant_fail']}")
    print(f"   mutant failing features: {R['mutant_feat']}")
    if R["fails"]:
        print("   FAILS:", R["fails"][:10])
print("PREFIX_DONE", W.SYM, tfs)
