"""flashgold_backtest.py - Python replica of pine/FlashGold_v5_Strategy_*.pine for calibration.

Reproduces: bid/ask from the spread, TDI direction (Wilder RSI -> SMA fast, fast rising = +1), parent = chart TF,
child zones on the chart TF and on higher timeframes (NON-repainting: the last CLOSED higher bar, the
lookahead_on + [1] idiom the scripts use for higher zones), burst gate, "any combo", entry hold, one entry per
bar, stop entry at ask + distance (bid - distance) with a lifetime, reversal on the opposite signal, optional
market close on the opposite signal, SL / TP / trail evaluated on TradingView's 4-point intrabar path, cash
commission per side and slippage on stop fills. Seconds-based zones cannot be replicated (no seconds exports)
and are off. Burst, entry distance, hold-favourable, SL, TP and trail are expressed in ATR(14) multiples so one
grid serves every symbol; the scripts have the matching ATR units.

CLI:  python3 flashgold_backtest.py sweep --tfs xau5,xau15 --out fg_xau
      python3 flashgold_backtest.py run --tf xau15 --zones htf3 --sl 1.5 --tp-r 1.0 ...
"""
import os, sys, json, math, itertools, argparse, dataclasses
from dataclasses import dataclass, asdict
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xpw_backtest as xb

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

# costs per side: (commission cash per contract, slippage in price units); spread in price units (full)
COSTS = {
    "xau": dict(comm=0.13, slip=0.05, spread=0.25),
    "spx": dict(comm=0.25, slip=0.10, spread=0.50),
    "btc": dict(comm=10.5, slip=5.0,  spread=21.0),
}
TF_MIN = {"xau5": 5, "xau10": 10, "xau15": 15, "xau30": 30, "xau60": 60,
          "spx1": 1, "spx15": 15, "spx30": 30, "spx60": 60,
          "btc5": 5, "15": 15, "30": 30, "60": 60}
def symbol_of(tf):
    return "xau" if tf.startswith("xau") else "spx" if tf.startswith("spx") else "btc"

ZONE_SETS = {            # name: (list of multiples of the chart TF, min aligned)
    "parent":  ([1], 1),
    "htf2":    ([1, 2, 4], 2),
    "htf3":    ([1, 2, 4, 8], 3),
    "htfonly": ([2, 4, 8], 2),
}

# ----------------------------------------------------------------------------- indicators
def rma(x, n):
    out = np.full(len(x), np.nan); a = 1.0 / n
    s = np.nan
    for i in range(len(x)):
        v = x[i]
        if np.isnan(v): continue
        if np.isnan(s):
            # Pine's rma seeds with the SMA of the first n values
            if i + 1 >= n and not np.isnan(x[i - n + 1:i + 1]).any():
                s = x[i - n + 1:i + 1].mean(); out[i] = s
            continue
        s = a * v + (1 - a) * s; out[i] = s
    return out

def rsi(close, n=14):
    d = np.diff(close, prepend=np.nan)
    up = np.where(d > 0, d, 0.0); dn = np.where(d < 0, -d, 0.0)
    up[0] = np.nan; dn[0] = np.nan
    ru, rd = rma(up, n), rma(dn, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.where(rd == 0, 100.0, np.where(ru == 0, 0.0, 100.0 - 100.0 / (1.0 + ru / rd)))
    r[np.isnan(ru) | np.isnan(rd)] = np.nan
    return r

def sma(x, n):
    s = pd.Series(x).rolling(n).mean().to_numpy(); return s

def tdi_dir(close):
    f = sma(rsi(close, 14), 2)
    d = np.zeros(len(close), dtype=int)
    prev = np.roll(f, 1); prev[0] = np.nan
    d[f > prev] = 1; d[f < prev] = -1
    d = d.astype(float); d[np.isnan(f) | np.isnan(prev)] = np.nan
    return d

# ----------------------------------------------------------------------------- data
class Data:
    def __init__(self, tf):
        d = xb.load_tf(tf, assert_pivots=False)
        self.tf = tf; self.sym = symbol_of(tf)
        self.o, self.h, self.l, self.c = d.open, d.high, d.low, d.close
        self.n = len(self.c)
        self.atr = xb.atr_wilder(self.h, self.l, self.c, 14)
        t = pd.to_datetime(pd.Series(d.time), utc=True)
        # bar time in the export's own offset: use the string's clock time (chart-local)
        clock = pd.to_datetime(pd.Series([s[:19] for s in d.time]))
        self.date = clock.dt.date.to_numpy()
        self.mod = (clock.dt.hour * 60 + clock.dt.minute).to_numpy()
        self.tfmin = TF_MIN[tf]
        self.dir_chart = tdi_dir(self.c)
        self._htf = {}
    def htf_dir(self, mult):
        """TDI direction of the last CLOSED higher-TF bar (mult x chart TF), aligned to the first bar of each day."""
        if mult == 1: return self.dir_chart
        if mult in self._htf: return self._htf[mult]
        n = mult * self.tfmin
        # anchor: first bar's minute-of-day per date
        df = pd.DataFrame(dict(date=self.date, mod=self.mod))
        anchor = df.groupby("date")["mod"].transform("min").to_numpy()
        slot = (self.mod - anchor) // n
        key = pd.Series([f"{d}_{s}" for d, s in zip(self.date, slot)])
        codes, uniq = pd.factorize(key, sort=False)          # bar ids in time order (data is sorted)
        # HTF close = close of the last chart bar of the group
        last_idx = pd.Series(np.arange(self.n)).groupby(codes).max().to_numpy()
        htf_close = self.c[last_idx]
        htf_d = tdi_dir(htf_close)
        # value visible on chart bar i = dir of the HTF bar BEFORE the one containing i (last closed)
        prev_code = codes - 1
        out = np.full(self.n, np.nan)
        ok = prev_code >= 0
        out[ok] = htf_d[prev_code[ok]]
        self._htf[mult] = out
        return out

_DATA = {}
def get_data(tf):
    if tf not in _DATA: _DATA[tf] = Data(tf)
    return _DATA[tf]

# ----------------------------------------------------------------------------- config
@dataclass
class Cfg:
    tf: str = "xau15"
    zones: str = "parent"
    any_combo: bool = True
    burst_atr: float = 0.5
    dist_atr: float = 0.25
    hold_bars: int = 0
    hold_fav_atr: float = 0.1
    sl_atr: float = 1.5
    tp_r: float = 1.0
    trail: bool = False
    trail_act_atr: float = 1.0
    trail_dst_atr: float = 0.75
    valid_bars: int = 3
    exit_opp: bool = False
    allow_reverse: bool = True
    allow_neutral_parent: bool = False

# ----------------------------------------------------------------------------- emulator
def path_points(o, h, l, c):
    # TradingView: open closer to high -> O H L C, else O L H C
    return (o, h, l, c) if (h - o) <= (o - l) else (o, l, h, c)

def run(cfg: Cfg, d: Data = None):
    d = d or get_data(cfg.tf)
    cost = COSTS[d.sym]; comm, slip, half = cost["comm"], cost["slip"], cost["spread"] / 2.0
    mults, min_al = ZONE_SETS[cfg.zones]
    zdirs = [d.htf_dir(m) for m in mults]
    parent = d.dir_chart
    o, h, l, c, atr = d.o, d.h, d.l, d.c, d.atr
    n = d.n
    trades = []
    # state
    hold_active = False; hold_buy = False; hold_bar = -1; hold_mid = np.nan; last_entry_bar = -1
    pend = {}          # side -> dict(price, placed, sl_d, tp_d)
    pos = None         # dict(side, entry, qty=1, sl, tp, hi, lo, trail_on, bar)
    close_at_open = False
    mid_prev = np.nan

    def close_pos(px, i, reason):
        nonlocal pos
        pnl = (px - pos["entry"]) * pos["side"] - 2 * comm
        trades.append(dict(side=pos["side"], entry_bar=pos["bar"], exit_bar=i, pnl=pnl, reason=reason, bars=i - pos["bar"], entry=pos["entry"]))
        pos = None

    for i in range(n):
        mid = c[i]                      # (bid + ask) / 2 == close
        ai = atr[i]
        # ---------- 1. process this bar's price action against pending orders / open position ----------
        if close_at_open and pos is not None:
            px = o[i] - pos["side"] * slip
            close_pos(px, i, "opp")
        close_at_open = False
        pts = path_points(o[i], h[i], l[i], c[i])
        # walk the 4-point path; entries may fill and exits may hit in path order
        cur = pts[0]
        for k in range(1, 4):
            nxt = pts[k]
            up = nxt >= cur
            # -- pending stop entries on this segment
            for side in (1, -1):
                p = pend.get(side)
                if p is None: continue
                hit = (up and side == 1 and cur <= p["price"] <= nxt) or ((not up) and side == -1 and nxt <= p["price"] <= cur) \
                      or (k == 1 and ((side == 1 and o[i] >= p["price"]) or (side == -1 and o[i] <= p["price"])))
                if not hit: continue
                fill = p["price"] if not (k == 1 and ((side == 1 and o[i] >= p["price"]) or (side == -1 and o[i] <= p["price"]))) else o[i]
                fill += side * slip
                if pos is not None and pos["side"] == -side:
                    close_pos(fill, i, "reverse")
                if pos is None:
                    pos = dict(side=side, entry=fill, bar=i, sl=fill - side * p["sl_d"] if p["sl_d"] > 0 else np.nan,
                               tp=fill + side * p["tp_d"] if p["tp_d"] > 0 else np.nan, ext=fill, trail_on=False,
                               act=p["act_d"], dst=p["dst_d"])
                    pend.pop(-side, None)     # OCA cancel
                pend.pop(side, None)
                cur_after = fill            # continue the segment from the fill point
                # exits on the remainder of this segment
                pos, done = _seg_exits(pos, cur_after, nxt, i, slip, close_pos)
                if done: break
            if pos is not None:
                pos, done = _seg_exits(pos, cur, nxt, i, slip, close_pos)
            cur = nxt
        # ---------- 2. bar-close logic (signals, orders) ----------
        # cancel stale entries
        for side in (1, -1):
            p = pend.get(side)
            if p is not None and cfg.valid_bars > 0 and i - p["placed"] >= cfg.valid_bars:
                pend.pop(side)
        if np.isnan(ai) or np.isnan(parent[i]):
            mid_prev = mid; continue
        pside = 1 if parent[i] > 0 else -1 if parent[i] < 0 else 0
        active = 0; aligned = 0
        for z in zdirs:
            v = z[i]
            if np.isnan(v): continue           # ignoreNaZones
            active += 1
            if pside != 0 and v == pside: aligned += 1
        req = min(min_al, active)
        flat_ok = cfg.allow_neutral_parent and pside == 0
        zone_ready = active == 0 or aligned >= req
        buy_ok = (pside == 1 or flat_ok) and zone_ready
        sell_ok = (pside == -1 or flat_ok) and zone_ready
        burst = (mid - mid_prev) if not np.isnan(mid_prev) else 0.0
        bth = cfg.burst_atr * ai
        burst_buy = burst >= bth; burst_sell = burst <= -bth
        if cfg.any_combo:
            buy_c = buy_ok and (burst_buy or pside == 1); sell_c = sell_ok and (burst_sell or pside == -1)
        else:
            buy_c = buy_ok and burst_buy; sell_c = sell_ok and burst_sell
        can_fire = last_entry_bar != i
        buy_sig = sell_sig = False
        dist = cfg.dist_atr * ai
        if buy_c and can_fire:
            if cfg.hold_bars == 0:
                buy_sig = True; last_entry_bar = i
            elif not hold_active:
                hold_active = True; hold_buy = True; hold_bar = i; hold_mid = mid
            elif hold_buy:
                if i - hold_bar >= cfg.hold_bars and (mid - hold_mid) >= cfg.hold_fav_atr * ai:
                    buy_sig = True; last_entry_bar = i; hold_active = False
        if sell_c and can_fire:
            if cfg.hold_bars == 0:
                sell_sig = True; last_entry_bar = i
            elif not hold_active:
                hold_active = True; hold_buy = False; hold_bar = i; hold_mid = mid
            elif not hold_buy:
                if i - hold_bar >= cfg.hold_bars and (hold_mid - mid) >= cfg.hold_fav_atr * ai:
                    sell_sig = True; last_entry_bar = i; hold_active = False
        if hold_active and ((hold_buy and not buy_ok) or ((not hold_buy) and not sell_ok)):
            hold_active = False
        # strategy orders
        in_long = pos is not None and pos["side"] == 1
        in_short = pos is not None and pos["side"] == -1
        flat = pos is None
        if cfg.exit_opp and ((sell_sig and in_long) or (buy_sig and in_short)):
            close_at_open = True
        sl_d = cfg.sl_atr * ai; tp_d = sl_d * cfg.tp_r
        act_d = cfg.trail_act_atr * ai if cfg.trail else 0.0; dst_d = cfg.trail_dst_atr * ai if cfg.trail else 0.0
        if buy_sig and not in_long and (flat or cfg.allow_reverse or cfg.exit_opp):
            pend[1] = dict(price=mid + half + dist, placed=i, sl_d=sl_d, tp_d=tp_d, act_d=act_d, dst_d=dst_d)
            pend.pop(-1, None)
        if sell_sig and not in_short and (flat or cfg.allow_reverse or cfg.exit_opp):
            pend[-1] = dict(price=mid - half - dist, placed=i, sl_d=sl_d, tp_d=tp_d, act_d=act_d, dst_d=dst_d)
            pend.pop(1, None)
        mid_prev = mid
    if pos is not None:
        close_pos(c[n - 1], n - 1, "end")
    return trades

def _seg_exits(pos, a, b, i, slip, close_pos):
    """Exits along one monotone segment a -> b. Returns (pos, closed)."""
    if pos is None: return None, False
    s = pos["side"]
    up = b >= a
    lo, hi = (a, b) if up else (b, a)
    # trailing activation / ratchet: the emulator activates when price reaches entry + act, then trails the extreme
    if pos["act"] > 0:
        act_px = pos["entry"] + s * pos["act"]
        if lo <= act_px <= hi or (s == 1 and lo > act_px) or (s == -1 and hi < act_px):
            pos["trail_on"] = True
        if pos["trail_on"]:
            ext = hi if s == 1 else lo
            if (s == 1 and ext > pos["ext"]) or (s == -1 and ext < pos["ext"]):
                pos["ext"] = ext
    # candidate exit levels
    tp = pos["tp"]; sl = pos["sl"]
    tstop = (pos["ext"] - s * pos["dst"]) if pos["trail_on"] else np.nan
    if not np.isnan(tstop):
        sl = tstop if np.isnan(sl) else (max(sl, tstop) if s == 1 else min(sl, tstop))
    # which is reached first along the direction of travel?
    if s == 1:
        if up:
            if not np.isnan(tp) and a <= tp <= b: close_pos(tp, i, "tp"); return None, True
        else:
            if not np.isnan(sl) and b <= sl <= a: close_pos(sl - slip, i, "sl"); return None, True
    else:
        if not up:
            if not np.isnan(tp) and b <= tp <= a: close_pos(tp, i, "tp"); return None, True
        else:
            if not np.isnan(sl) and a <= sl <= b: close_pos(sl + slip, i, "sl"); return None, True
    # gap through at segment start (first segment only matters, harmless elsewhere)
    if s == 1 and not np.isnan(sl) and a < sl and a == lo and not up: pass
    return pos, False

# ----------------------------------------------------------------------------- metrics
def metrics(trades, n_bars):
    if not trades:
        return dict(n=0, win=np.nan, net=0.0, pf=np.nan, dd=0.0, avg_bars=np.nan, n1=0, net1=0.0, pf1=np.nan, n2=0, net2=0.0, pf2=np.nan, same_bar=np.nan)
    p = np.array([t["pnl"] for t in trades]); eb = np.array([t["entry_bar"] for t in trades]); bars = np.array([t["bars"] for t in trades])
    def pf(x):
        g = x[x > 0].sum(); l = -x[x < 0].sum()
        return g / l if l > 0 else (np.inf if g > 0 else np.nan)
    eq = np.cumsum(p); dd = float((np.maximum.accumulate(eq) - eq).max())
    half = n_bars // 2
    p1, p2 = p[eb < half], p[eb >= half]
    return dict(n=len(p), win=float((p > 0).mean()), net=float(p.sum()), pf=float(pf(p)), dd=dd, avg_bars=float(bars.mean()),
                n1=len(p1), net1=float(p1.sum()), pf1=float(pf(p1)) if len(p1) else np.nan,
                n2=len(p2), net2=float(p2.sum()), pf2=float(pf(p2)) if len(p2) else np.nan,
                same_bar=float((bars == 0).mean()))

# ----------------------------------------------------------------------------- sweep
# signal variants: with "any combo" the burst threshold only matters when the parent is flat, so it is swept once there
SIGNALS = [dict(any_combo=True, burst_atr=0.5), dict(any_combo=False, burst_atr=0.25), dict(any_combo=False, burst_atr=0.5), dict(any_combo=False, burst_atr=1.0)]
GRID = dict(zones=["parent", "htf2", "htf3", "htfonly"], dist_atr=[0.1, 0.25], hold_bars=[0, 3],
            sl_atr=[1.0, 1.5, 2.0, 3.0], tp_r=[0.5, 1.0, 1.5, 2.0, 3.0], trail=[False, True], exit_opp=[False, True])

def _one(args):
    tf, kw = args
    cfg = Cfg(tf=tf, **kw)
    d = get_data(tf)
    m = metrics(run(cfg, d), d.n)
    return dict(tf=tf, **kw, **m)

def sweep(tfs, out, jobs):
    import multiprocessing as mp
    outdir = os.path.join(RESULTS_DIR, out); os.makedirs(outdir, exist_ok=True)
    keys = list(GRID.keys())
    for tf in tfs:
        combos = [dict(zip(keys, v)) | sig for v in itertools.product(*GRID.values()) for sig in SIGNALS]
        tasks = [(tf, kw) for kw in combos]
        get_data(tf)
        with mp.Pool(jobs) as pool:
            rows = pool.map(_one, tasks, chunksize=32)
        df = pd.DataFrame(rows); df.to_csv(os.path.join(outdir, f"sweep_{tf}.csv"), index=False)
        m = df[(df.n >= 30)]
        print(f"{tf}: {len(df)} configs, {len(m)} with >=30 trades, positive {(m.net > 0).mean():.2f}, best PF {m.pf.replace(np.inf, np.nan).max():.2f}", flush=True)

def main(argv=None):
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("sweep"); s.add_argument("--tfs", default="xau15"); s.add_argument("--out", default="fg"); s.add_argument("--jobs", type=int, default=max(1, os.cpu_count() or 1))
    r = sub.add_parser("run"); r.add_argument("--tf", default="xau15")
    for k, v in Cfg.__dataclass_fields__.items():
        if k == "tf": continue
        r.add_argument("--" + k.replace("_", "-"), type=type(v.default) if not isinstance(v.default, bool) else lambda x: x.lower() in ("1", "true", "yes"), default=v.default)
    a = ap.parse_args(argv)
    if a.cmd == "sweep":
        sweep(a.tfs.split(","), a.out, a.jobs)
    elif a.cmd == "run":
        kw = {k: getattr(a, k) for k in Cfg.__dataclass_fields__ if k != "tf"}
        cfg = Cfg(tf=a.tf, **kw); d = get_data(a.tf); tr = run(cfg, d)
        print(json.dumps(asdict(cfg))); print(json.dumps({k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in metrics(tr, d.n).items()}, indent=1))
        for t in tr[:15]: print(t)

if __name__ == "__main__":
    main()
