"""Perpetual-futures backtester for the night lab. Bar-close decisions, next-bar-open fills.

Costs modelled on every trade: taker fee per side (default 0.05 %), slippage in ticks per fill,
funding paid/received at each funding timestamp while in position (sign-correct), and a
per-trade R sizing on account risk. No look-ahead: a strategy returns a target position
(-1, 0, +1) and an optional stop distance computed from bars up to and including the current
one; the position is entered at the NEXT bar's open.

Strategy interface:
    signals(df) -> DataFrame with columns ['target', 'stop'] aligned to df.index
    target in {-1, 0, 1}; stop = stop distance in price units (NaN = no stop; time stop via max_hold)
"""
import numpy as np
import pandas as pd

TICK = {"BTCUSDT": 0.1, "ETHUSDT": 0.01, "SOLUSDT": 0.001}


def load(data_dir, sym, tf):
    df = pd.read_parquet(f"{data_dir}/{sym}_{tf}.parquet").set_index("time")
    return df[["open", "high", "low", "close", "volume", "quote_volume", "trades", "taker_buy_base"]].astype(float)


def load_funding(data_dir, sym):
    f = pd.read_parquet(f"{data_dir}/{sym}_funding.parquet").set_index("time")
    return f["last_funding_rate"].astype(float)


def run(df, sig, funding, sym, capital=10000.0, risk_pct=0.5, fee_pct=0.05, slip_ticks=1,
        max_lev=5.0, max_hold=None):
    """Returns (trades DataFrame, equity Series). Position size = risk / stop distance, capped at max_lev."""
    o, h, l, c = df.open.values, df.high.values, df.low.values, df.close.values
    idx = df.index
    tgt = sig["target"].reindex(idx).fillna(0).values.astype(int)
    stp = sig["stop"].reindex(idx).values.astype(float)
    tick = TICK.get(sym, 0.01)
    fee = fee_pct / 100
    fund = funding.reindex(idx, method=None)  # funding only at exact timestamps
    fund_at = fund.fillna(0).values
    n = len(df)
    pos = 0; qty = 0.0; entry = 0.0; e_i = -1; e_stop = np.nan; stop_px = np.nan
    eq = capital
    equity = np.full(n, np.nan)
    trades = []
    funding_acc = 0.0
    for i in range(n):
        # 1. fills decided at the previous close
        if i > 0:
            want = tgt[i - 1]
            if want != pos:
                if pos != 0:  # close
                    px = o[i] - pos * slip_ticks * tick
                    pnl = (px - entry) * pos * qty - fee * px * qty - fee * entry * qty + funding_acc
                    eq += pnl
                    trades.append(dict(entry_time=idx[e_i], exit_time=idx[i], side=pos, qty=qty, entry=entry, exit=px,
                                       pnl=pnl, r=pnl / (e_stop * qty) if e_stop > 0 else np.nan, bars=i - e_i, reason="signal"))
                    pos = 0; funding_acc = 0.0
                if want != 0 and not np.isnan(stp[i - 1]) and stp[i - 1] > 0:
                    px = o[i] + want * slip_ticks * tick
                    q = eq * risk_pct / 100 / stp[i - 1]
                    q = min(q, eq * max_lev / px)
                    pos = want; qty = q; entry = px; e_i = i; e_stop = stp[i - 1]
                    stop_px = entry - pos * e_stop
        # 2. stop on this bar's path (gap fills at open)
        if pos != 0:
            hit = (pos > 0 and l[i] <= stop_px) or (pos < 0 and h[i] >= stop_px)
            if hit:
                px = min(o[i], stop_px) if pos > 0 else max(o[i], stop_px)
                px -= pos * slip_ticks * tick
                pnl = (px - entry) * pos * qty - fee * px * qty - fee * entry * qty + funding_acc
                eq += pnl
                trades.append(dict(entry_time=idx[e_i], exit_time=idx[i], side=pos, qty=qty, entry=entry, exit=px,
                                   pnl=pnl, r=pnl / (e_stop * qty), bars=i - e_i, reason="stop"))
                pos = 0; funding_acc = 0.0
                tgt[i] = 0  # a stopped trade is not re-entered on the same signal bar
        # 3. funding while holding (long pays positive funding)
        if pos != 0 and fund_at[i] != 0:
            funding_acc -= pos * fund_at[i] * c[i] * qty
        # 4. time stop
        if pos != 0 and max_hold and i - e_i >= max_hold:
            tgt[i] = 0
        equity[i] = eq + ((c[i] - entry) * pos * qty + funding_acc if pos != 0 else 0)
    return pd.DataFrame(trades), pd.Series(equity, index=idx)


def summarize(trades, equity, capital=10000.0):
    if len(trades) == 0:
        return dict(trades=0)
    pnl = trades.pnl.values
    peak = equity.cummax()
    dd = ((peak - equity) / peak).max() * 100
    gp = pnl[pnl > 0].sum(); gl = -pnl[pnl < 0].sum()
    streak = cur = 0
    for p in pnl:
        cur = cur + 1 if p < 0 else 0; streak = max(streak, cur)
    days = max((equity.index[-1] - equity.index[0]).days, 1)
    return dict(trades=len(trades), net=round(float(pnl.sum()), 2), ret_pct=round(100 * pnl.sum() / capital, 2),
                pf=round(gp / gl, 2) if gl else 99.0, win=round(100 * (pnl > 0).mean(), 1),
                avg_r=round(float(np.nanmean(trades.r)), 3), maxdd_pct=round(float(dd), 2), losing_streak=int(streak),
                trades_per_month=round(len(trades) / days * 30, 1),
                sharpe=round(float(pnl.mean() / pnl.std() * np.sqrt(len(trades) / days * 365)), 2) if pnl.std() > 0 and len(pnl) > 2 else 0.0)


def walk_forward(df, funding, sym, strategy, grid, train_months=6, test_months=3, **kw):
    """Rolling: pick the grid point with the best train avg_r*sqrt(n) (min 30 trades), apply to the next test block.
    Returns the concatenated out-of-sample trades and the per-window choices. Strategy = callable(df, **params)."""
    start = df.index[0]; end = df.index[-1]
    t0 = start
    oos, picks = [], []
    while True:
        t1 = t0 + pd.DateOffset(months=train_months); t2 = t1 + pd.DateOffset(months=test_months)
        if t1 >= end:
            break
        tr_df = df[t0:t1]
        best = None
        for params in grid:
            sig = strategy(tr_df, **params)
            t, e = run(tr_df, sig, funding, sym, **kw)
            if len(t) < 30:
                continue
            score = np.nanmean(t.r) * np.sqrt(len(t))
            if best is None or score > best[0]:
                best = (score, params)
        if best is not None:
            te_df = df[t0:t2]  # warm-up included, trades filtered to the test block
            sig = strategy(te_df, **best[1])
            t, e = run(te_df, sig, funding, sym, **kw)
            t = t[t.entry_time >= t1]
            oos.append(t); picks.append(dict(train_start=t0, test_start=t1, test_end=min(t2, end), params=best[1], n=len(t)))
        t0 = t0 + pd.DateOffset(months=test_months)
    return (pd.concat(oos) if oos else pd.DataFrame()), picks


def regime_table(trades):
    """Net R per calendar quarter, so bull / bear / chop behaviour is visible."""
    if len(trades) == 0:
        return pd.DataFrame()
    g = trades.groupby(trades.exit_time.dt.tz_convert(None).dt.to_period("Q"))
    return pd.DataFrame(dict(trades=g.size(), net_r=g.r.sum().round(1), win=(g.pnl.apply(lambda s: 100 * (s > 0).mean())).round(0)))
