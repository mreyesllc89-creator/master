"""Tick-level backtest of XPW Shape Map v0.6 (Turn Predict) on MT5 bid/ask tick exports.

Bars are built from BID (what MT5 / TradingView broker charts show). Orders follow MT5 rules:
buy stop / short SL / short trail trigger on ASK, sell stop / long SL / long trail trigger on BID.
A triggered stop or market order fills at the NEXT tick (one-tick latency), so the spread
and the jump between ticks are paid as they really were. TP is a limit and fills at its price.
Commission is charged per unit per side, in price units (e.g. $0.03/oz = $3 per 100 oz lot).
"""
import sys, numpy as np, pandas as pd
from numba import njit
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from xpw import indicators, signals

def load_ticks(path):
    df = pd.read_csv(path, sep='\t', usecols=[0, 1, 2, 3], names=['d', 't', 'bid', 'ask'], header=0)
    ts = pd.to_datetime(df['d'] + ' ' + df['t'], format='%Y.%m.%d %H:%M:%S.%f')
    df = pd.DataFrame({'ts': ts, 'bid': df['bid'].ffill(), 'ask': df['ask'].ffill()}).dropna()
    df = df[df['ask'] >= df['bid']]
    return df.reset_index(drop=True)

def build(df, rule, rsiLen=14, fastLen=2, slowLen=7, turnMax=12, turnHold=2):
    """Bid OHLC bars (only periods that have ticks, like MT5) + per-tick bar id."""
    key = df['ts'].dt.floor(rule)
    g = df.groupby(key, sort=True)['bid']
    bars = pd.DataFrame({'o': g.first(), 'h': g.max(), 'l': g.min(), 'c': g.last()})
    bid_ = pd.Index(bars.index).get_indexer(key)
    D = dict(t=[str(x) for x in bars.index], o=bars['o'].values, h=bars['h'].values, l=bars['l'].values, c=bars['c'].values)
    n = len(D['c'])
    D.update(fastx=np.full(n, np.nan), slowx=np.full(n, np.nan), xpx=np.full(n, np.nan))
    D = signals(indicators(D, rsiLen, fastLen, slowLen), turnMax=turnMax, turnHold=turnHold)
    return D, bid_.astype(np.int64)

@njit(cache=True)
def engine(bid, ask, bar, wantL, wantS, xpx, fast, slow, atr, tick, slA, tpR, actA, disA, comm, turnHold, failExit, startBar):
    n = len(bid); nb = len(xpx)
    out_ret = np.zeros(n // 10 + 1000); out_pnl = np.zeros_like(out_ret); out_bar = np.zeros(len(out_ret), np.int64); out_kind = np.zeros(len(out_ret), np.int64)
    nt = 0
    pos = 0; ep = 0.0; eb = 0; best = 0.0; sl = 0.0; tp = 0.0; act = 0.0; dis = 0.0
    pd_dir = 0; pd_px = 0.0           # pending stop entry
    act_kind = 0                      # scheduled action for next tick: 1 open long, -1 open short, 2 close
    act_reason = 0
    cb = bar[0]
    for k in range(n):
        b = bar[k]; bi = bid[k]; ak = ask[k]
        # 1. execute action scheduled on the previous tick
        if act_kind != 0:
            if act_kind == 2 or (pos != 0 and act_kind != pos):
                fill = bi if pos == 1 else ak
                g = (fill - ep) * pos - 2 * comm
                out_ret[nt] = g / ep * 100; out_pnl[nt] = g; out_bar[nt] = eb; out_kind[nt] = act_reason; nt += 1
                pos = 0
            if act_kind == 1 or act_kind == -1:
                pos = act_kind; ep = ak if pos == 1 else bi; eb = b; best = bi if pos == 1 else ak
                a = atr[b - 1] if b >= 1 else atr[b]
                sl = slA * a; tp = tpR * sl if tpR > 0 else 0.0; act = actA * a; dis = disA * a
            act_kind = 0
        # 2. bar close of cb (first tick of a new bar)
        if b != cb:
            if cb >= startBar:
                posc = pos
                # Pine: orders placed at close with pos as of the close
                pd_dir = 0
                if not np.isnan(xpx[cb]):
                    if wantL[cb] and posc <= 0:
                        pd_dir = 1; pd_px = np.ceil(xpx[cb] / tick - 1e-9) * tick
                    elif wantS[cb] and posc >= 0:
                        pd_dir = -1; pd_px = np.floor(xpx[cb] / tick + 1e-9) * tick
                if failExit and pos != 0 and cb - eb <= turnHold:
                    if (pos == 1 and fast[cb] <= slow[cb]) or (pos == -1 and fast[cb] >= slow[cb]):
                        fill = bi if pos == 1 else ak
                        g = (fill - ep) * pos - 2 * comm
                        out_ret[nt] = g / ep * 100; out_pnl[nt] = g; out_bar[nt] = eb; out_kind[nt] = 4; nt += 1
                        pos = 0
            cb = b
        # 3. triggers on this tick
        if pos != 0:
            if pos == 1:
                if bi > best: best = bi
                if tp > 0 and bi >= ep + tp:
                    g = tp - 2 * comm
                    out_ret[nt] = g / ep * 100; out_pnl[nt] = g; out_bar[nt] = eb; out_kind[nt] = 3; nt += 1
                    pos = 0
                elif sl > 0 and bi <= ep - sl:
                    act_kind = 2; act_reason = 1
                elif dis > 0 and best >= ep + act and bi <= best - dis:
                    act_kind = 2; act_reason = 2
            else:
                if ak < best: best = ak
                if tp > 0 and ak <= ep - tp:
                    g = tp - 2 * comm
                    out_ret[nt] = g / ep * 100; out_pnl[nt] = g; out_bar[nt] = eb; out_kind[nt] = 3; nt += 1
                    pos = 0
                elif sl > 0 and ak >= ep + sl:
                    act_kind = 2; act_reason = 1
                elif dis > 0 and best <= ep - act and ak >= best + dis:
                    act_kind = 2; act_reason = 2
        if act_kind == 0 and pd_dir != 0 and pd_dir != pos:
            if (pd_dir == 1 and ak >= pd_px) or (pd_dir == -1 and bi <= pd_px):
                act_kind = pd_dir; act_reason = 5; pd_dir = 0
    if pos != 0:
        fill = bid[n - 1] if pos == 1 else ask[n - 1]
        g = (fill - ep) * pos - 2 * comm
        out_ret[nt] = g / ep * 100; out_pnl[nt] = g; out_bar[nt] = eb; out_kind[nt] = 6; nt += 1
    return out_ret[:nt], out_pnl[:nt], out_bar[:nt], out_kind[:nt]

def run(df, D, barid, slA, tpR, actA, disA, comm, tick, spread=True, start=60, turnHold=2, failExit=True):
    bid = df['bid'].values; ask = df['ask'].values if spread else bid
    return engine(bid, ask, barid, D['wantL'], D['wantS'], D['xpxc'], D['fast'], D['slow'], D['atr'], tick,
                  slA, tpR, actA, disA, comm, turnHold, failExit, start)


@njit(cache=True)
def engine2(bid, ask, bar, wantL, wantS, xpx, fast, slow, unit, slDL, slDS, exitL, exitS,
            tick, tpR, actU, disU, comm, turnHold, failExit, timeStop, startBar):
    """Generalised engine.  Per signal bar b (the bar whose close armed the stop):
    unit[b]  = distance unit for trail activation / trail distance / nothing else
    slDL[b], slDS[b] = stop-loss distance (price) for a long / short filled on bar b+1
    exitL[b], exitS[b] = close the long / short at the close of bar b (extra exit rule)
    timeStop = close after this many bars (0 = off).  Returns R, pnl, entry bar, exit kind, SL distance."""
    n = len(bid)
    cap = n // 10 + 1000
    out_pnl = np.zeros(cap); out_sl = np.zeros(cap); out_bar = np.zeros(cap, np.int64); out_kind = np.zeros(cap, np.int64)
    nt = 0
    pos = 0; ep = 0.0; eb = 0; best = 0.0; sl = 0.0; tp = 0.0; act = 0.0; dis = 0.0
    pd_dir = 0; pd_px = 0.0; act_kind = 0; act_reason = 0
    cb = bar[0]
    for k in range(n):
        b = bar[k]; bi = bid[k]; ak = ask[k]
        if act_kind != 0:
            if act_kind == 2 or (pos != 0 and act_kind != pos):
                fill = bi if pos == 1 else ak
                out_pnl[nt] = (fill - ep) * pos - 2 * comm; out_sl[nt] = sl; out_bar[nt] = eb; out_kind[nt] = act_reason; nt += 1
                pos = 0
            if act_kind == 1 or act_kind == -1:
                pos = act_kind; ep = ak if pos == 1 else bi; eb = b; best = bi if pos == 1 else ak
                sb = b - 1 if b >= 1 else b
                u = unit[sb]
                sl = slDL[sb] if pos == 1 else slDS[sb]
                tp = tpR * sl if tpR > 0 else 0.0; act = actU * u; dis = disU * u
            act_kind = 0
        if b != cb:
            if cb >= startBar:
                posc = pos
                pd_dir = 0
                if not np.isnan(xpx[cb]):
                    if wantL[cb] and posc <= 0:
                        pd_dir = 1; pd_px = np.ceil(xpx[cb] / tick - 1e-9) * tick
                    elif wantS[cb] and posc >= 0:
                        pd_dir = -1; pd_px = np.floor(xpx[cb] / tick + 1e-9) * tick
                if pos != 0:
                    close_it = 0
                    if failExit and cb - eb <= turnHold:
                        if (pos == 1 and fast[cb] <= slow[cb]) or (pos == -1 and fast[cb] >= slow[cb]):
                            close_it = 4
                    if close_it == 0 and ((pos == 1 and exitL[cb]) or (pos == -1 and exitS[cb])):
                        close_it = 7
                    if close_it == 0 and timeStop > 0 and cb - eb + 1 >= timeStop:
                        close_it = 8
                    if close_it != 0:
                        fill = bi if pos == 1 else ak
                        out_pnl[nt] = (fill - ep) * pos - 2 * comm; out_sl[nt] = sl; out_bar[nt] = eb; out_kind[nt] = close_it; nt += 1
                        pos = 0
            cb = b
        if pos != 0:
            if pos == 1:
                if bi > best: best = bi
                if tp > 0 and bi >= ep + tp:
                    out_pnl[nt] = tp - 2 * comm; out_sl[nt] = sl; out_bar[nt] = eb; out_kind[nt] = 3; nt += 1
                    pos = 0
                elif sl > 0 and bi <= ep - sl:
                    act_kind = 2; act_reason = 1
                elif dis > 0 and best >= ep + act and bi <= best - dis:
                    act_kind = 2; act_reason = 2
            else:
                if ak < best: best = ak
                if tp > 0 and ak <= ep - tp:
                    out_pnl[nt] = tp - 2 * comm; out_sl[nt] = sl; out_bar[nt] = eb; out_kind[nt] = 3; nt += 1
                    pos = 0
                elif sl > 0 and ak >= ep + sl:
                    act_kind = 2; act_reason = 1
                elif dis > 0 and best <= ep - act and ak >= best + dis:
                    act_kind = 2; act_reason = 2
        if act_kind == 0 and pd_dir != 0 and pd_dir != pos:
            if (pd_dir == 1 and ak >= pd_px) or (pd_dir == -1 and bi <= pd_px):
                act_kind = pd_dir; act_reason = 5; pd_dir = 0
    if pos != 0:
        fill = bid[n - 1] if pos == 1 else ask[n - 1]
        out_pnl[nt] = (fill - ep) * pos - 2 * comm; out_sl[nt] = sl; out_bar[nt] = eb; out_kind[nt] = 6; nt += 1
    return out_pnl[:nt], out_sl[:nt], out_bar[:nt], out_kind[:nt]
