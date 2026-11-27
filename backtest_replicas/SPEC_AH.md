# Python replicas of two fused strategies: ApexForge Flow Resonance + FGF, HRD Full Divergence v1.03 + FGF

Work dir `$W` = `/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/`.
Python 3, numpy, pandas, numba, pyarrow. Run Python as `python3 -I`. 4-CPU machine shared
with other agents: at most 2 processes each. Do not edit files you were not asked to write.
Do not read the other implementation of your strategy (`*_a.py` vs `*_b.py`).

Ground truth = the Pine files. Where this spec and the Pine disagree, the Pine wins; say so.
- ApexForge: `/home/user/master/ApexForge_Flow_Resonance_Strategy_FGF.pine` (with "Enable
  filter" off it trades exactly like `/home/user/master/ApexForge_Flow_Resonance_Strategy.pine`).
- HRD: `/home/user/master/HRD_Full_Divergence_Strategy_v1_03_FGF.pine` (filter off = the
  original `/home/user/master/HRD_Full_Divergence_Strategy_v1_03.pine`).
Both use the FlashGold Direction Filter block. Its permissions are already replicated and
verified: use `$W/fgf.py` (`fgf.fgf_permissions(pair, chart_tf, start, end, {})` returns per
chart bar `buyOk`, `sellOk`; read its docstring). Do not reimplement the filter.

## Data

- `$W/data/<PAIR>_<TF>.parquet`: open, high, low, close, t_open, t_close (UTC epoch s; t_close
  = bar complete), sess. PAIR in {BTC, XAU}; TF in "1","5","15","30","60","120","240","D","W","M".
  Read the docstring of `$W/build_bars.py` (BTC on a UTC grid; XAU on a TradingView-style
  18:00-17:00 New York session; D = session, W = Monday-Friday sessions, M = calendar month of
  the session date).
- `$W/data/<PAIR>_<TF>_vol.parquet`: column `volume`, same rows (BTC: Bitstamp volume; XAU:
  Dukascopy tick count, TradingView-style tick volume).
- Windows (evaluate from these chart bars, warm everything up from the start of the data):
  BTC 1731801600..1794873600 (2024-11-17..2026-11-17), XAU 1483315200..1529366400
  (2017-01-02..2018-06-19) by t_close. Positions start flat at the window start.
- Symbol constants: mintick 0.01, pointvalue 1 for both.

## request.security on history (same rule as `$W/SPEC.md`)

`request.security(tickerid, TF, expr)` with lookahead off: on a chart bar closing at Tc take
expr on the LAST TF bar with t_close <= Tc (na if none). With `lookahead=barmerge.lookahead_on`
and `expr[1]` (HRD's horizons): the TF bar that CONTAINS the chart bar (t_open <= chart t_open
< t_close), then its previous TF bar's value, i.e. the previous completed D / W / M bar.

## Pine semantics to respect

ta.rsi = Wilder RMA (seeded with the SMA of the first `length` changes); ta.ema seeded with
the first value (`na(sum[1]) ? src : alpha*src + (1-alpha)*sum[1]`); ta.macd line =
ema(12) - ema(26); ta.stoch(close, high, low, n) = 100*(close - lowest(low,n)) /
(highest(high,n) - lowest(low,n)); ta.sma includes the current bar; any comparison with na
is false; float division by zero gives na. ta.pivothigh(src, L, R) / ta.pivotlow: on bar i
returns src[i-R] when it is a pivot over bars i-L-R .. i, else na. TIES: implement the pivot
as STRICTLY greater (pivothigh) / strictly smaller (pivotlow) than every other bar in the
window, and add a param `pivotTies` with values 'strict' (default) and 'left_strict'
(strict against the left bars, >= / <= against the right bars) so the reconciler can measure
how much the tie rule matters.

## The broker (TradingView Strategy Tester, history, no Bar Magnifier)

Both strategies have process_orders_on_close = false (default) and run once per chart bar at
its close on history (HRD's calc_on_every_tick only matters live).
1. Orders placed by the script on bar i (strategy.entry / strategy.close / strategy.close_all,
   all market) fill at the OPEN of bar i+1, in the order they were placed.
2. strategy.entry in the direction opposite to the open position closes it and opens the new
   one (reversal) in that same fill. pyramiding = 0 (default): an entry in the direction of
   the open position is ignored.
3. strategy.exit(id, from_entry, stop, limit) placed on bar i applies to that entry's trade
   from its fill on: on the fill bar i+1 the bracket is checked along the rest of the bar's
   path after the open fill. Calling strategy.exit again with the same id replaces its prices
   from the next bar on. An exit whose entry trade has closed is cancelled.
4. Intrabar path: if (high - open) < (open - low): open -> high -> low -> close, else
   open -> low -> high -> close. A stop or limit already beyond at the bar open fills at the
   open; else at its price when the path reaches it; if both are reached, the first along the
   path wins.
5. Orders placed on the window's last bar do not fill; trades open at the end are closed at
   the last close (kind "end").
6. strategy.position_size / strategy.position_avg_price / strategy.equity seen by the script
   on bar i: the position after bar i's open fills and intrabar exits; equity = initial
   capital + closed P/L + open P/L at bar i's close (minus commissions paid).
7. Initial capital 1,000,000 for both: neither strategy() sets initial_capital, and the Pine
   default is 1,000,000. (Sizing is a share of equity, so net % does not depend on it.)

## Sizing and costs

- ApexForge: default_qty_type percent_of_equity, value 1: each entry's quantity =
  1% x strategy.equity at the bar where the order is placed / that bar's close.
  commission_type percent, 0.04% of the order value per side (each fill).
- HRD: no default qty; every entry passes qty = calculatePositionSize(...) (read the Pine):
  risk 1% of strategy.equity over the 2% stop distance, floor 0.01. No commission in
  strategy() (TradingView shows no costs).
- Cost modes, a param `cost` in {'tv', 'ours'}:
  'tv' = the script's own properties (Apex 0.04% per side; HRD none);
  'ours' = our standard costs, replacing the script's commission: XAU $0.30 per ounce per
  round trip (charge $0.15 per unit per fill), BTC 0.02% of the fill value per fill + $0.20
  per unit per round trip ($0.10 per unit per fill).
  Costs reduce equity at each fill, so they affect later sizing.

## What to replicate

Every signal, gate, order and exit of the fused files, including:
- ApexForge: HTF high/low on "15"; swing order blocks (box top = swing*1.008, bottom =
  swing*0.992; replaced on each new pivot; na before the first); flow / volume detection;
  resonance; the filter gate (apxGoLong / apxGoShort); the blocked-opposite close
  (apxBlkClose, default true; strategy.close of the open trade); the stop / target formulas;
  the exit update when a same-side resonance appears while already in that position (also when
  blocked); reversals.
- HRD: D / W / M horizons; breakouts; RSI / MACD / stoch oscillator; pivots and the
  regular / hidden divergence state machine (prevPl*/prevPh* updated on every pivot);
  Reverse Trading and Trade Direction (defaults false / Both); the filter gate on the traded
  side (hrdWantLong / hrdWantShort, fgfBuyOk / fgfSellOk); hrdBlkClose (default true);
  the time exit (entryBarIndex rules, exactly as written, including its quirks on reversals);
  the SL / TP bracket from the signal bar's close; the hybrid decay-slip exit with its var
  globals (they reset when flat); strategy.close_all ordering relative to entries on the same
  bar (placement order).

## Interface (one module per strategy and implementation)

    run(pair, chart_tf, params=None) -> (trades: DataFrame, summary: dict)

params: `fgfOn` (bool, default True), `blkClose` (apxBlkClose / hrdBlkClose, default True),
`cost` ('tv' default / 'ours'), `reverse` (Apex: swap long and short signals before the gate,
a replica-only control; HRD: InpReverseTrading), `pivotTies`, plus any input of the Pine by
its variable name. trades: one row per trade: dir, entry_time, entry_px, qty, exit_time,
exit_px, exit_kind ('sl', 'tp', 'reverse', 'blocked_close', 'time', 'hybrid', 'end'), pnl
(after costs), entry_bar, exit_bar. summary: trades, net_pct (equity change % of the initial capital),
pf, win_pct, max_dd_pct (on the bar-close equity curve incl. open P/L), long / short counts,
signals raw / blocked per side (the FGD counts), half1_pct / half2_pct (equity change in each
half of the window, split at start + (end-start)//2, as % of initial capital), exposure
(share of bars with a position).

## Self-checks before finishing

- Runs on BTC "60" and XAU "60" over the full windows, and on BTC "1" (about 1.04M bars) in
  under 5 minutes (numba for hot loops).
- Hand-trace at least 5 trades of each kind you can find (entry, stop, target, reversal,
  blocked close, time exit, hybrid exit) and print the bars that prove each.
- Filter off: `fgfOn=False` must give the original's trades (the gate is always true).
- Save `$W/out/<apex|hrd>_<a|b>_BTC_60.parquet` and `$W/out/<apex|hrd>_<a|b>_XAU_60.parquet`
  (trades, default params, cost 'tv').
- Write `$W/<apex|hrd>_<a|b>_notes.md`: every interpretation you made of the Pine, and
  anything you could not implement.
