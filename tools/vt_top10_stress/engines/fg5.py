"""FlashGold v5 strategy replay (Pine semantics) on real ticks (VT) or OHLC bars (TV export).
Signal on bar close; stop entries with validity; reversal; FGF 60m direction-filter gate;
exits: Pips / ATR / Points, Fixed (SL/TP/trail) or Partial+runner (BE after TP, trail from TP level).
"""
import numpy as np, pandas as pd, math, itertools, time
from dataclasses import dataclass, field

# ---------------- indicators (Pine) ----------------
def rma(x, n):
    out = np.full(len(x), np.nan)
    if len(x) < n: return out
    out[n-1] = np.nanmean(x[:n])
    for i in range(n, len(x)):
        out[i] = (out[i-1]*(n-1) + x[i])/n
    return out
def rsi(c, n):
    d = np.diff(c, prepend=np.nan); up = np.where(d > 0, d, 0.0); dn = np.where(d < 0, -d, 0.0)
    up[0] = np.nan; dn[0] = np.nan
    au = np.full(len(c), np.nan); ad = np.full(len(c), np.nan)
    if len(c) > n:
        au[n] = np.mean(up[1:n+1]); ad[n] = np.mean(dn[1:n+1])
        for i in range(n+1, len(c)):
            au[i] = (au[i-1]*(n-1) + up[i])/n; ad[i] = (ad[i-1]*(n-1) + dn[i])/n
    out = np.where(ad == 0, 100.0, np.where(au == 0, 0.0, 100 - 100/(1 + au/np.where(ad == 0, 1, ad))))
    out[np.isnan(au)] = np.nan
    return out
def sma(x, n):
    out = np.full(len(x), np.nan)
    for i in range(n-1, len(x)):
        w = x[i-n+1:i+1]
        if not np.isnan(w).any(): out[i] = w.mean()
    return out
def atr(h, l, c, n):
    tr = np.maximum(h - l, np.maximum(np.abs(h - np.roll(c, 1)), np.abs(l - np.roll(c, 1)))); tr[0] = h[0] - l[0]
    return rma(tr, n)
def tdi_dir(c, rsi_len, fast_len):
    f = sma(rsi(c, rsi_len), fast_len)
    d = np.zeros(len(c), dtype=int); fp = np.roll(f, 1); fp[0] = np.nan
    d[(f > fp)] = 1; d[(f < fp)] = -1
    return d

# ---------------- bars ----------------
@dataclass
class Bars:
    t: np.ndarray      # open time ms
    o: np.ndarray; h: np.ndarray; l: np.ndarray; c: np.ndarray
    tf_ms: int
    bs: np.ndarray = None   # path start index per bar
    be: np.ndarray = None   # path end (exclusive)
    @property
    def tclose(self): return self.t + self.tf_ms

def bars_from_ticks(t, mid, tf_ms):
    key = t // tf_ms
    starts = np.flatnonzero(np.r_[True, key[1:] != key[:-1]]); ends = np.r_[starts[1:], len(t)]
    return Bars(key[starts]*tf_ms, mid[starts], np.maximum.reduceat(mid, starts), np.minimum.reduceat(mid, starts), mid[ends-1], tf_ms, starts, ends)

def resample(b: Bars, mult, anchor_ms=0):
    tf = b.tf_ms*mult; key = (b.t - anchor_ms) // tf
    starts = np.flatnonzero(np.r_[True, key[1:] != key[:-1]]); ends = np.r_[starts[1:], len(b.t)]
    return Bars(key[starts]*tf + anchor_ms, b.o[starts], np.maximum.reduceat(b.h, starts), np.minimum.reduceat(b.l, starts), b.c[ends-1], tf)

def prev_closed_map(chart: Bars, htf: Bars, val):
    """value of the HTF bar BEFORE the one containing each chart bar (lookahead_on + [1] idiom)."""
    idx = np.searchsorted(htf.t, chart.t, side="right") - 1      # HTF bar containing chart bar
    prev = idx - 1
    out = np.zeros(len(chart.t), dtype=val.dtype)
    ok = prev >= 0
    out[ok] = val[prev[ok]]
    return out, ok

# ---------------- signal ----------------
@dataclass
class SigParams:
    spread_pts: float = 25.0
    burst_atr: float = 0.5
    dist_atr: float = 0.25
    use_zones: bool = True
    min_aligned: int = 2
    use_burst: bool = True
    rsi_len: int = 14
    fast_len: int = 2
    one_per_bar: bool = True

def signal(chart: Bars, z2: Bars, z3: Bars, p: SigParams, tick):
    """Returns dict with buy, sell, buy_px, sell_px, atr14, parent side."""
    c = chart.c
    parent = tdi_dir(c, p.rsi_len, p.fast_len)
    z1 = parent.copy()
    d2 = tdi_dir(z2.c, p.rsi_len, p.fast_len); d3 = tdi_dir(z3.c, p.rsi_len, p.fast_len)
    z2d, ok2 = prev_closed_map(chart, z2, d2); z3d, ok3 = prev_closed_map(chart, z3, d3)
    a = atr(chart.h, chart.l, c, 14)
    half = p.spread_pts*tick*0.5
    burst_pts = (c - np.roll(c, 1)); burst_pts[0] = 0
    thr = p.burst_atr*a; dist = p.dist_atr*a
    side = parent
    active = 1 + ok2.astype(int) + ok3.astype(int)        # z1 always has data
    aligned = (side != 0).astype(int)*1 + ((z2d == side) & (side != 0) & ok2) + ((z3d == side) & (side != 0) & ok3)
    required = np.minimum(p.min_aligned, active)
    ready = (active == 0) | (aligned >= required)
    buy_allowed = (~np.bool_(p.use_zones)) | ((side == 1) & ready)
    sell_allowed = (~np.bool_(p.use_zones)) | ((side == -1) & ready)
    bb = burst_pts >= thr if p.use_burst else np.ones(len(c), bool); bs_ = burst_pts <= -thr if p.use_burst else np.ones(len(c), bool)
    valid = ~np.isnan(a) & ~np.isnan(thr)
    buy = buy_allowed & bb & valid; sell = sell_allowed & bs_ & valid
    # one entry per bar: if both, buy is processed first and sets lastEntryBar -> sell suppressed
    both = buy & sell; sell[both] = False
    return dict(buy=buy, sell=sell, buy_px=c + half + dist, sell_px=c - half - dist, atr=a, parent=parent, aligned=aligned, active=active)

def fgf_gate(chart: Bars, f_bars: Bars, f_z2: Bars, f_z3: Bars, p: SigParams, tick, band_atr=0.25, against=True, enabled=True):
    """Direction filter on filter bars (60m). Returns buy_ok, sell_ok per chart bar (checked at chart bar close vs close price)."""
    n = len(chart.t)
    if not enabled: return np.ones(n, bool), np.ones(n, bool), np.zeros(n, int)
    s = signal(f_bars, f_z2, f_z3, p, tick)
    sig = np.where(s["buy"], 1, np.where(s["sell"], -1, 0))
    sig_idx = np.flatnonzero(sig != 0)
    if len(sig_idx) == 0: return np.zeros(n, bool), np.zeros(n, bool), np.zeros(n, int)
    level = np.where(sig == 1, s["buy_px"], s["sell_px"])[sig_idx]
    dirn = sig[sig_idx]; satr = s["atr"][sig_idx]; fclose = f_bars.tclose[sig_idx]
    # latest filter signal candle closed by the chart bar's close
    k = np.searchsorted(fclose, chart.tclose, side="right") - 1
    armed = k >= 0; kk = np.maximum(k, 0)
    lv = level[kk]; d = dirn[kk]; band = band_atr*np.nan_to_num(satr[kk])
    up = np.where(band > 0, np.ceil((lv + band)/tick - 1e-9)*tick, lv); dn = np.where(band > 0, np.floor((lv - band)/tick + 1e-9)*tick, lv)
    v = chart.c
    in_up = np.where(band > 0, v > up + tick/2, v > lv); in_dn = np.where(band > 0, v < dn - tick/2, v < lv)
    buy_ok = armed & in_up & (against | (d > 0)); sell_ok = armed & in_dn & (against | (d < 0))
    return buy_ok, sell_ok, np.where(armed, d, 0)

# ---------------- exits ----------------
@dataclass
class ExitParams:
    mode: str = "Pips"           # Pips | ATR | Points
    pip: float = 1.0
    sl_pips: float = 30; tpr_pips: float = 5; run_pips: float = 600; act_pips: float = 150; trail_pips: float = 600
    sl_pts: float = 3900; tp_pts: float = 19500; act_pts: float = 4500; trail_pts: float = 1000; run_pts: float = 58000
    sl_atr: float = 0.1; tpr_atr: float = 2.0; act_atr: float = 1.0; trail_atr: float = 0.25; run_atr: float = 1.5
    style: str = "Partial + runner"   # or Fixed
    part_pct: float = 30; run_be: bool = True; use_trail: bool = False
    time_stop: int = 0
    def dists(self, a, tick):
        """SL, TP, trail act, trail dist, runner dist in PRICE units for ATR value a."""
        if self.mode == "Pips":
            sl = self.sl_pips*self.pip; tp = sl*self.tpr_pips; act = self.act_pips*self.pip; tr = max(self.trail_pips*self.pip, tick); run = max(self.run_pips*self.pip, tick)
        elif self.mode == "Points":
            sl = self.sl_pts*tick; tp = self.tp_pts*tick; act = self.act_pts*tick; tr = max(self.trail_pts*tick, tick); run = max(self.run_pts*tick, tick)
        else:
            sl = self.sl_atr*a; tp = sl*self.tpr_atr; act = self.act_atr*a; tr = max(self.trail_atr*a, tick); run = max(self.run_atr*a, tick)
        return sl, tp, act, tr, run

@dataclass
class Costs:
    qty: float = 0.1             # lots (VT) or contracts (TV)
    unit: float = 1.0            # price-unit value per 1 qty: VT gold 1 oz/lot, VT BTC 0.01, TV BTC 1
    comm_side_per_qty: float = 0.30   # USD per qty per side (VT: 0.60 RT per lot)
    comm_pct: float = 0.0        # % notional per side (TV crypto 0.02)
    slip_ticks: int = 0          # adverse ticks per side (TV synthetic path 5)
    tick: float = 0.01

# ---------------- engine ----------------
def run(chart: Bars, path_t, path_b, path_a, sig, gate_buy, gate_sell, xp: ExitParams, cost: Costs,
        valid_bars=3, allow_reverse=True, direction="Both", synthetic=False, worst_case=False, start_bar=0):
    tick = cost.tick; q = cost.qty; unit = cost.unit; slip = cost.slip_ticks*tick
    trades = []
    pos = None   # dict(side, px, qty_frac, best, part_done, be_on, entry_bar, entry_t, sl, tp, act, tr, run)
    pend = {1: None, -1: None}   # side -> dict(px, bar, sl, tp, act, tr, run)
    nb = len(chart.t)
    blocked = 0; placed = 0
    allowL = direction != "Short"; allowS = direction != "Long"
    def fee(price, frac):
        return (cost.comm_side_per_qty*q*frac) + (cost.comm_pct/100.0*price*q*unit*frac)
    def close_part(frac, price, t, reason, bar):
        nonlocal pos
        gross = (price - pos["px"])*pos["side"]*q*unit*frac
        f = fee(price, frac) + pos["fee_in"]*frac
        trades.append(dict(entry_t=pos["entry_t"], exit_t=t, entry_bar=pos["entry_bar"], exit_bar=bar, side=pos["side"], frac=frac, entry=pos["px"], exit=price,
                           sl_dist=pos["sl"], gross=gross, fee=f, net=gross - f, reason=reason))
        pos["qty_frac"] -= frac
        if pos["qty_frac"] <= 1e-9: pos = None
    for i in range(start_bar, nb):
        s0, s1 = chart.bs[i], chart.be[i]
        tb = path_t[s0:s1]; bb = path_b[s0:s1]; ba = path_a[s0:s1]
        if synthetic and worst_case and pos is not None:
            # adverse extreme first for the open side
            o, hi, lo, c = chart.o[i], chart.h[i], chart.l[i], chart.c[i]
            seq = np.array([o, lo, hi, c]) if pos["side"] > 0 else np.array([o, hi, lo, c])
            bb = seq; ba = seq; tb = np.array([chart.t[i]]*4) + np.array([0, 1, 2, 3])
        k0 = 0
        # ---- intrabar events (loop until no more events in this bar) ----
        while True:
            n = len(tb) - k0
            if n <= 0: break
            ev = []  # (idx, priority, kind)
            b = bb[k0:]; a = ba[k0:]
            if pos is not None:
                side = pos["side"]; ex = b if side > 0 else a            # price that closes the position
                # running best
                cm = np.maximum.accumulate(ex*side)  # signed
                best_sig = np.maximum(cm, pos["best"]*side)
                stop_lvl = pos["px"] - side*pos["sl"]
                if xp.style == "Partial + runner" and xp.part_pct < 100:
                    tp_lvl = pos["px"] + side*pos["tp"]
                    hit_sl = np.flatnonzero((ex - stop_lvl)*side <= 0)
                    if len(hit_sl): ev.append((hit_sl[0], 0, "SL"))
                    if pos["be_on"]:
                        hit_be = np.flatnonzero((ex - pos["px"])*side <= 0)
                        if len(hit_be): ev.append((hit_be[0], 0, "BE"))
                    if xp.part_pct > 0 and not pos["part_done"]:
                        hit_tp = np.flatnonzero((ex - tp_lvl)*side >= 0)
                        if len(hit_tp): ev.append((hit_tp[0], 1, "TP part"))
                    # runner trail: active once best >= entry + tp
                    active = best_sig >= (pos["px"]*side + pos["tp"])
                    tstop = best_sig - pos["run"]          # signed
                    hit_tr = np.flatnonzero(active & ((ex*side) <= tstop))
                    if len(hit_tr): ev.append((hit_tr[0], 2, "runner"))
                else:
                    tp_lvl = pos["px"] + side*pos["tp"]
                    hit_sl = np.flatnonzero((ex - stop_lvl)*side <= 0)
                    if len(hit_sl): ev.append((hit_sl[0], 0, "SL"))
                    if pos["tp"] > 0:
                        hit_tp = np.flatnonzero((ex - tp_lvl)*side >= 0)
                        if len(hit_tp): ev.append((hit_tp[0], 1, "TP"))
                    if xp.use_trail:
                        active = best_sig >= (pos["px"]*side + pos["act"])
                        tstop = best_sig - pos["tr"]
                        hit_tr = np.flatnonzero(active & ((ex*side) <= tstop))
                        if len(hit_tr): ev.append((hit_tr[0], 2, "trail"))
                if pos["time_exit"]:
                    ev.append((0, -1, "time stop"))
            for sd in (1, -1):
                pd_ = pend[sd]
                if pd_ is None: continue
                if sd > 0: hit = np.flatnonzero(a >= pd_["px"])
                else: hit = np.flatnonzero(b <= pd_["px"])
                if len(hit): ev.append((hit[0], 3, "ENTRY_L" if sd > 0 else "ENTRY_S"))
            if not ev: break
            ev.sort(key=lambda e: (e[0], e[1]))
            idx, _, kind = ev[0]; kk = k0 + idx
            t_ev = tb[kk]
            def fill_px(level, up_cross, raw):
                # synthetic path: fill at level unless gapped at the bar open
                if synthetic:
                    if kk == 0: return raw
                    return level
                return raw
            if kind in ("SL", "BE", "TP part", "TP", "runner", "trail", "time stop"):
                side = pos["side"]; raw = (bb[kk] if side > 0 else ba[kk])
                if kind == "SL": level = pos["px"] - side*pos["sl"]
                elif kind == "BE": level = pos["px"]
                elif kind in ("TP part", "TP"): level = pos["px"] + side*pos["tp"]
                elif kind == "runner":
                    best_now = max(pos["best"]*side, np.max((bb[k0:kk+1] if side > 0 else ba[k0:kk+1])*side))*side
                    level = best_now - side*pos["run"]
                elif kind == "trail":
                    best_now = max(pos["best"]*side, np.max((bb[k0:kk+1] if side > 0 else ba[k0:kk+1])*side))*side
                    level = best_now - side*pos["tr"]
                else: level = raw
                px = fill_px(level, side < 0, raw)
                if synthetic: px = px - side*slip
                # update best up to kk
                segment = (bb[k0:kk+1] if side > 0 else ba[k0:kk+1])
                pos["best"] = max(pos["best"]*side, np.max(segment*side))*side
                if kind == "TP part":
                    close_part(pos["qty_frac"]*xp.part_pct/100.0, px, t_ev, kind, i); 
                    if pos is not None: pos["part_done"] = True
                else:
                    close_part(pos["qty_frac"], px, t_ev, kind, i)
                k0 = kk + 1 if kind != "TP part" else kk   # after a partial, same tick may trigger runner
                if kind == "TP part": k0 = kk + 1
                continue
            # entry fill
            sd = 1 if kind == "ENTRY_L" else -1; pd_ = pend[sd]
            raw = ba[kk] if sd > 0 else bb[kk]
            px = fill_px(pd_["px"], sd > 0, raw)
            if synthetic: px = px + sd*slip
            if pos is not None and pos["side"] == -sd:
                # reversal: close at the same price
                segment = (bb[k0:kk+1] if pos["side"] > 0 else ba[k0:kk+1])
                pos["best"] = max(pos["best"]*pos["side"], np.max(segment*pos["side"]))*pos["side"]
                close_part(pos["qty_frac"], px, t_ev, "reverse", i)
            pos = dict(side=sd, px=px, qty_frac=1.0, best=px, part_done=False, be_on=False, entry_bar=i, entry_t=t_ev,
                       sl=pd_["sl"], tp=pd_["tp"], act=pd_["act"], tr=pd_["tr"], run=pd_["run"], fee_in=fee(px, 1.0), time_exit=False)
            pend[sd] = None; pend[-sd] = None     # OCA cancel
            k0 = kk + 1
        # ---- bar close ----
        if pos is not None:
            # best over whole bar
            seg = bb[k0:] if pos["side"] > 0 else ba[k0:]
            if len(seg): pos["best"] = max(pos["best"]*pos["side"], np.max(seg*pos["side"]))*pos["side"]
            # BE flag from the close of the bar that reached TP (chart high/low)
            if xp.style == "Partial + runner" and xp.run_be and xp.part_pct < 100:
                if pos["side"] > 0 and chart.h[i] >= pos["px"] + pos["tp"]: pos["be_on"] = True
                if pos["side"] < 0 and chart.l[i] <= pos["px"] - pos["tp"]: pos["be_on"] = True
            if xp.time_stop > 0 and i - pos["entry_bar"] >= xp.time_stop: pos["time_exit"] = True
        # stale pending cancellation
        for sd in (1, -1):
            if pend[sd] is not None and valid_bars > 0 and i - pend[sd]["bar"] >= valid_bars: pend[sd] = None
        # new entries
        a_now = sig["atr"][i]
        if sig["buy"][i] and allowL and (pos is None or pos["side"] < 0) and (pos is None or allow_reverse):
            if gate_buy[i]:
                sl, tp, act, tr, run = xp.dists(a_now, tick)
                if sl > 0: pend[1] = dict(px=sig["buy_px"][i], bar=i, sl=sl, tp=tp, act=act, tr=tr, run=run); placed += 1
            else: blocked += 1
        if sig["sell"][i] and allowS and (pos is None or pos["side"] > 0) and (pos is None or allow_reverse):
            if gate_sell[i]:
                sl, tp, act, tr, run = xp.dists(a_now, tick)
                if sl > 0: pend[-1] = dict(px=sig["sell_px"][i], bar=i, sl=sl, tp=tp, act=act, tr=tr, run=run); placed += 1
            else: blocked += 1
    # end: close open position at last price
    if pos is not None:
        px = path_b[-1] if pos["side"] > 0 else path_a[-1]
        close_part(pos["qty_frac"], px, path_t[-1], "end", nb-1)
    return pd.DataFrame(trades), dict(placed=placed, blocked=blocked)

def metrics(tr: pd.DataFrame, cost: Costs):
    if len(tr) == 0: return dict(trades=0, net=0.0, gross=0.0, fee=0.0, pf=np.nan, win=np.nan, maxdd=0.0, pos_weeks=np.nan, weeks=0, halves="")
    # group partial fills by entry into one trade for counting
    g = tr.groupby(["entry_t", "side"]).agg(net=("net", "sum"), gross=("gross", "sum"), fee=("fee", "sum"), exit_t=("exit_t", "max"), sl=("sl_dist", "first")).reset_index().sort_values("exit_t")
    cum = g.net.cumsum(); dd = (cum.cummax() - cum).max()
    w = g.net[g.net > 0].sum(); l = -g.net[g.net < 0].sum()
    wk = g.set_index(pd.to_datetime(g.exit_t, unit="ms")).net.resample("W").sum()
    half = len(g)//2
    R = g.net/(g.sl*cost.qty*cost.unit)
    return dict(trades=len(g), net=g.net.sum(), gross=g.gross.sum(), fee=g.fee.sum(), pf=(w/l if l > 0 else np.inf), win=(g.net > 0).mean(), maxdd=dd,
                pos_weeks=(wk > 0).mean(), weeks=len(wk), halves=f"{g.net.iloc[:half].sum():.2f}/{g.net.iloc[half:].sum():.2f}", meanR=R.mean(), sumR=R.sum(),
                reasons=tr.reason.value_counts().to_dict(), longs=int((g.side > 0).sum()), shorts=int((g.side < 0).sum()))
