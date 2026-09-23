# XPW Breakout v2.10: BTCUSD calibration

This is the calibration record behind `pine/XPW_Breakout_v2.10_BTCUSD.pine`.
It covers the three asks (include commission, more extensive entry, entry by
tick), what was measured on the five BTCUSD exports, what the shipped
defaults are, and what could not be established from ~600 bars per timeframe.

Read the caveat first: 600 bars per timeframe (15m: 7.6 days, 30m: 12 days,
60m: 25 days, 240m: 99 days, 1m: 10 hours) calibrate cost and geometry
sanity. They do not prove an edge. Every "best" cell in a grid this small is
mostly noise, so the picks below are plateau picks (all grid neighbours also
positive), and the per-timeframe blocks say when even that is not available.

## 1. What changed and why

| Ask | What v2.01 did | What v2.10 does |
|---|---|---|
| Include commission | Header only: 0.003 USD per oz per side and 30 ticks slippage. On BTC that is $0.61 per round trip, 35-140x below any real venue. Nothing in the logic knew about costs. | Cost inputs (commission %, commission cash per contract per side, slippage per side) drive a cost gate, TP widening so the net target equals the input, cost-aware risk sizing, a cost-aware breakeven step, and a referee table that compares the commission the tester actually charged with the modelled figure. Header re-based to BTC. |
| More extensive entry | One level source (confirmed pivot), one trigger (stop straddle), a session filter and a compression gate. The stop was cancelled on every bar whose close sat inside the buffer (F11), so most breaks never had an order resting. | Three level sources (pivot, Donchian of the prior N bars, previous-day high/low; nearest enabled level is used), three triggers (resting stop, close-confirmed market entry with a chase cap, retest limit with a lifetime), an arm latch that keeps the stop resting, plus direction, chart-EMA trend, cooldown, max trades per day, retry cap per level, trade days, session, compression and cost gates. |
| Entry by tick | Bar-close only ("Script execution = ON BAR CLOSE ONLY"). | `calc_on_every_tick=true` with an Execution input. Tick mode re-evaluates arming, cancelling, sizing, the cost gate and the trail on every live tick; state is `varip` so it survives the per-tick rollback. The trail can be handed to the broker emulator (`trail_points`/`trail_offset`), which ratchets intrabar on history and per tick live. Levels still come from confirmed bars because an unconfirmed level cannot be backtested. |

Defects found on the way (all fixed in v2.10, see the script header):

- F11: the buffer was a keep-alive test, not an arming test. At buffer 1.0 ATR
  the exports show 60m armed 4 of 37 confirmed breaks and 15m 10 of 54. In
  tick mode this would have been fatal: the first tick inside the buffer
  cancels the stop and it can never fill.
- F12: `strategy.risk.max_position_size` only constrains `strategy.entry()`;
  v2.01 used `strategy.order()`, so its hard cap was inert.
- F13: ATR geometry recomputed after the fill is a moving target; SL/TP are
  now locked per trade at arm time and re-anchored to the real fill.
- A `var` trail ratchet re-issued with `strategy.exit` on every tick would
  retreat, because order state is not rolled back between ticks but `var`
  state is. Trail state is `varip`.

## 2. Data

| File | Bars | Span | Median close | Median ATR14 | ATR14 % of price |
|---|---|---|---|---|---|
| `calibration/data/BTCUSD_1.csv` | 613 | 10 hours (2026-09-23) | 85,480 | 44 | 0.052 |
| `calibration/data/BTCUSD_15.csv` | 730 | 7.6 days | 81,132 | 197 | 0.240 |
| `calibration/data/BTCUSD_30.csv` | 596 | 12 days | 77,864 | 280 | 0.353 |
| `calibration/data/BTCUSD_60.csv` | 596 | 25 days | 78,552 | 405 | 0.512 |
| `calibration/data/BTCUSD_240.csv` | 596 | 99 days (from 2026-06-16) | 64,546 | 721 | 1.031 |

The exports carry the strategy's own plotted series (Swing High, Swing Low,
Trail). The Python engine's pivot logic reproduces the Swing High / Swing Low
columns exactly on every row of every file, and the Trail column let the
engine be checked against TradingView's own fills (section 8).

## 3. Cost model and presets

Round-trip cost per contract, as the script computes it:

```
rtCost = 2 x (price x CommPct/100 + CommCash + SlipUSD)
```

`CommCash` is where a CFD's half spread goes (plus any per-lot commission),
because the tester charges cash-per-contract commission on every fill,
including TP limit fills, which its slippage setting never touches. `SlipUSD`
is pure execution slip on stop and market fills and must equal the header's
slippage in ticks times `syminfo.mintick`; the table row "Header slippage
should be" prints the tick count for the chart symbol.

| Preset | CommPct | CommCash | SlipUSD | Round trip per BTC | Header | Provenance |
|---|---|---|---|---|---|---|
| none | 0 | 0 | 0 | $0 | commission 0, slippage 0 | frictionless baseline |
| exchange (perp taker) | 0.05 | 1.0 | 5.0 | ~$96 at $84k | `strategy.commission.percent`, 0.05, slippage 600 | Binance USDT-M / Bybit perp taker 0.05-0.055%; spot is 0.1% (RT ~$180). Spread $2 and slip $5 are assumptions. |
| cfd_std (spread only) | 0 | 8.5 | 5.0 | $27 | `cash_per_contract`, 8.5, slippage 500 | VT Markets BTCUSD spread 1,696 points = $16.96 (VT cost FAQ). Pepperstone $10-15, IC Markets ~$12. |
| cfd_raw (shipped default) | 0 | 9.0 | 5.0 | $28 | `cash_per_contract`, 9.0, slippage 500 | VT Raw ECN $3 per lot per side ($6 RT) verified for FX, assumed for BTCUSD; raw spread $12 from IC Markets. If your MT5 statement shows no crypto commission, use 6.0. |
| v2.01 gold header | 0 | 0.003 | 0.30 | $0.61 | as shipped in v2.01 | why v2.01 numbers looked free on BTC |

Tick counts assume `syminfo.mintick` = 0.01 (CRYPTO:BTCUSD and the CFD feeds
quote two decimals). Some BTC feeds use 1.0 or 0.1; use 5/6 or 50/60 there.
Contract facts: 1 TradingView contract = 1 BTC = 1 MT5 lot on the CFD feeds;
minimum 0.01 lot; exchange perps 0.001 BTC steps. CFD feeds on TradingView
are the bid price, so a buy stop that MT5 triggers on the ask pays roughly a
full spread relative to the chart; half spread per side is the usual
compromise. Swap/funding is not modelled by the tester: one night of crypto
CFD swap is $17-46 per BTC, comparable to the whole round trip, and 60m/240m
trades routinely span the rollover.

TradingView stores Properties per chart once touched. On a chart that ran
v2.01 do Properties > Defaults > Reset settings, or type the values in. The
table's "Commission charged / modelled" row turns red when the tester's
commission disagrees with the inputs by more than 10%; it cannot check
slippage ticks.

## 4. Cost versus geometry

Round trip per BTC against the median ATR of each timeframe. "min TP" is the
TP distance at which the round trip is 20% of TP.

| TF | median ATR | preset | RT cost | cost % of price | cost / ATR | cost / SL(0.1%) | cost / SL(1.5 ATR) | min TP | min TP in ATR |
|---|---|---|---|---|---|---|---|---|---|
| 15m | 197 | exchange | $85 | 0.105 | 0.43 | 1.05 | 0.29 | $426 (0.53%) | 2.2 |
| 15m | 197 | cfd_std | $27 | 0.033 | 0.14 | 0.33 | 0.09 | $135 (0.17%) | 0.7 |
| 15m | 197 | cfd_raw | $22-28 | 0.03 | 0.11-0.14 | 0.27-0.33 | 0.08 | $110-140 | 0.6-0.7 |
| 30m | 280 | exchange | $82 | 0.105 | 0.29 | 1.05 | 0.20 | $409 (0.53%) | 1.5 |
| 30m | 280 | cfd_std | $27 | 0.035 | 0.10 | 0.35 | 0.06 | $135 (0.17%) | 0.5 |
| 60m | 405 | exchange | $83 | 0.105 | 0.20 | 1.05 | 0.14 | $413 (0.53%) | 1.0 |
| 60m | 405 | cfd_std | $27 | 0.034 | 0.07 | 0.34 | 0.04 | $135 (0.17%) | 0.3 |
| 240m | 721 | exchange | $69 | 0.106 | 0.10 | 1.06 | 0.06 | $343 (0.53%) | 0.5 |
| 240m | 721 | cfd_std | $27 | 0.042 | 0.04 | 0.42 | 0.03 | $135 (0.21%) | 0.2 |
| 1m | 44 | cfd_std | $27 | 0.032 | 0.61 | 0.32 | 0.41 | $135 | 3.1 |
| 1m | 44 | exchange | $89 | 0.105 | 2.03 | 1.05 | 1.35 | $447 | 10.2 |

Reading:

- On exchange taker fees the round trip (~$85) exceeds a 0.1% stop (~$80) and
  is 42% of a 0.25% TP. The gold geometry needs a 61% win rate to break even
  there; with CFD costs it needs 38% instead of the frictionless 29%.
- 1m is not viable on any preset (round trip 0.6-2.0 ATR). The cost gate
  blocks it at the defaults, which is the intended behaviour.
- The gold SL 0.1% is 0.4 ATR on 15m and 0.2 ATR on 60m: it is hit by noise
  long before cost matters.

## 5. Why the gold geometry looked fine on BTC and is not

The v2.01 defaults (SL 0.1%, TP 0.25%, BarsN 5, buffer 1.0 ATR) on the exports,
fixed 1 BTC, engine replica of the tester without bar magnifier:

| TF | cost | trades | win % | net | cost / gross | PF | bars held | exits inside the fill bar |
|---|---|---|---|---|---|---|---|---|
| 15m | cfd_std | 19 | 47 | +796 | 0.15 | 1.82 | 0.9 | 37% |
| 15m | exchange | 19 | 47 | -546 | 0.61 | 0.67 | 0.8 | 37% |
| 30m | cfd_std | 18 | 50 | +751 | 0.15 | 1.83 | 0.4 | 72% |
| 30m | exchange | 18 | 50 | -402 | 0.59 | 0.72 | 0.4 | 72% |
| 60m | cfd_std | 12 | 67 | +1047 | 0.12 | 3.56 | 0.1 | 92% |
| 60m | exchange | 12 | 67 | +280 | 0.52 | 1.44 | 0.1 | 92% |
| 240m | cfd_std | 17 | 65 | +1196 | 0.14 | 3.22 | 0.2 | 76% |
| 240m | exchange | 17 | 71 | +473 | 0.51 | 1.65 | 0.2 | 76% |

Both SL ($80) and TP ($200) sit inside a single BTC bar on every timeframe,
so 37-92% of the trades open and close on the fill bar. Without bar
magnifier the tester decides those by its open-low-high-close path
assumption, and that assumption favours the entry direction (after a stop
fill on the way to the bar's extreme, the path continues to that extreme
before it can revisit the stop). The apparent profit is a path artefact, and
under exchange costs it is negative anyway. The sweep excludes any
configuration where more than half the trades resolve inside the fill bar.

## 6. The arm latch (F11)

Mean trades and mean net over the whole grid per timeframe, pivot levels,
cfd_raw costs, engine replica:

| TF | v2.01 arming, buffer 1.0 ATR | v2.01 arming, buffer 0.5 | latch, buffer 1.0 | latch, buffer 0.5 |
|---|---|---|---|---|
| 15m | 15 trades, net -538 | 30, +993 | 33, +1049 | 38, +1593 |
| 30m | 14, +763 | 24, +2115 | 28, +732 | 32, +1679 |
| 60m | 13, +1401 | 25, +564 | 31, +710 | 36, +175 |
| 240m | 15, +1596 | 27, -441 | 34, -682 | 37, -124 |

With v2.01 arming, a buffer of 2.0 ATR produces 0-5 trades per 600 bars; the
order is almost never resting when the break happens. The latch roughly
doubles trade frequency at the same buffer and makes the buffer mean what
the MT5 original meant by it: a minimum distance to place a pending order.
More trades is not the same as more profit (60m and 240m show that), which
is why the geometry blocks below were re-derived under the latch rather
than copied from the v2.01 sweep.

## 7. Sweep and recommended settings

Grid per timeframe: SL {pct 0.1, 0.25, 0.5, 1.0 | ATR 1.0, 1.5, 2.0, 3.0} x TP
{1, 1.5, 2, 2.5, 3 R} x BarsN {3, 5, 8} x buffer {0.5, 1.0, 2.0 ATR} x trail
{off, bar, tick} x cost {none, exchange, cfd_std, cfd_raw} x arming {v2.01,
latch} x levels {pivot, pivot + Donchian 20}. 17,280 configurations per
timeframe, fixed 1 BTC, initial capital 100,000. Full tables:
`calibration/results/SWEEP_NOTES.md` (v2.01 arming) and
`calibration/results/latch/SWEEP_NOTES.md` (both arming modes), CSVs beside
them. Trail "tick" in the engine is the emulator-style intrabar ratchet;
"bar" is the v2.01 close-anchored ratchet. In the script those are Trail
execution = Emulator and Script.

Latch mode, pivot levels, plateau picks (every grid neighbour also positive
unless noted):

| TF | cost | geometry | BarsN | buffer | trail | trades | win % | net | PF | max DD | neighbourhood mean / min |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 15m | cfd_raw | Pct: SL 1.0%, TP 2.5% (2.5R) | 3 | 0.5 | bar | 29 | 52 | +5957 | 2.30 | 2387 | +4891 / +2426 |
| 15m | exchange | same | 3 | 0.5 | bar | 31 | 48 | +4587 | 1.94 | 2928 | +3444 / +1121 |
| 30m | cfd_raw | ATR: SL 3.0 ATR, TP 3R | 3 | 0.5 | bar | 24 | 58 | +5660 | 1.91 | 4625 | +4751 / +1727 |
| 30m | exchange | ATR: SL 3.0 ATR, TP 3R | 8 | 0.5 | bar | 17 | 65 | +6507 | 3.26 | 2151 | +4512 / +258 |
| 60m | cfd_raw | ATR: SL 3.0 ATR, TP 3R | 3 | 0.5 | tick | 30 | 67 | +10184 | 2.38 | 2944 | +5497 / +507 |
| 60m | exchange | same | 3 | 0.5 | tick | 29 | 59 | +9604 | 2.42 | 2935 | +4823 / -251 (5 of 6 neighbours positive) |
| 240m | any | inconclusive, see below | | | | | | | | | |

Shipped defaults are the 60m block: GeoMode ATR, SL 3.0 ATR, TP 3R, BarsN 3,
buffer 0.5 ATR, trail on with Emulator execution, trigger 1.0 ATR, distance
1.5 ATR, latch on, cost gate 20% of net TP, cfd_raw costs. Marginals over
the whole latch grid (cfd_raw, measurable configurations): trail tick beats
bar beats off; buffer 0.5 beats 1.0 beats 2.0; TP 3R is the best R; BarsN 3
and 8 beat 5.

Per-timeframe notes:

- 15m: percent geometry wins. SL 1.0% is about 4 ATR on 15m; the ATR-3.0 band
  is positive but thinner (36 trades, +4509 cfd_raw / +2154 exchange at
  BarsN 3). Set GeoMode Pct, SL 1.0, TP 2.5, BarsN 3, buffer 0.5.
- 30m: ATR 3.0 / 3R. BarsN 8 is the stronger pick under exchange costs (17
  trades) and BarsN 3 under CFD costs (24 trades); BarsN 5 is the weak middle
  (30 trades, +1411 cfd_raw, -486 exchange). Set BarsN 3 or 8, not 5.
- 60m: the shipped defaults. Sensitive to BarsN: 5 and 8 drop to +2356 and
  +2573 (cfd_raw). Adding Donchian 20 levels keeps it positive (32 trades,
  +9765 at BarsN 8, buffer 1.0) but does not improve the plateau.
- 240m: not calibrated. 99 days give 20-46 trades and the sign flips between
  neighbouring cells; the ATR-3.0 band is net negative (SL 3 ATR is 3% of
  price there), the percent 0.25-0.5% bands look good only through fill-bar
  artefacts (35-50% same-bar exits), and the best latch pick (SL 0.5%, 2R,
  buffer 2.0) has 49% same-bar exits. Use 240m for context, not for trading
  the defaults, until more history is exported.
- 1m: 10 hours of one session. Ignore; the cost gate blocks it anyway.
- Donchian 20 as an additional level source: raises trade counts by 30-40%
  and helps on 15m (+7511 at SL 1.0% / 3R) and 60m, hurts on 30m under
  exchange costs. It is off by default; turn it on per timeframe with the
  numbers above in mind.

Risk sizing was spot-checked, not swept: the 60m pick at 1% risk of
equity with the shipped 2 BTC cap (cost reserved in the denominator) keeps
the same 30 trades, +8015 net, max drawdown 2517.

## 8. How faithful the engine is

The engine (`calibration/xpw_backtest.py`) replicates the tester without bar
magnifier: bar-close logic, next-bar order activation, the four-point
intrabar path, stop fills at the level or the open with adverse slippage,
limit fills without slippage, OCA cancel on the fill bar, the bracket live
from the fill point, and both trail modes. Against the TradingView Trail
column (non-null only while TradingView held a position) the export turned
out to have been made with TP 0.5% and trail distance 1.9 ATR rather than the
v2.01 header defaults; with those inferred settings the engine reproduces
every episode on 30m (Jaccard 1.0), 4 of 4 on 240m, 11 of 12 on 15m and 8 of
10 on 1m, and the trail values match to 1e-11 where both hold. The
remaining differences are consistent with bar magnifier having been on in
TradingView (three fills at the bar close plus slippage, three engine
episodes that TradingView did not take). Details: `python3
calibration/xpw_backtest.py parity` and `calibration/results/parity.json`.

## 9. Tick execution: what is and is not backtestable

- Historical bars run once, at the close, in both Execution modes. The
  Strategy Tester result for Tick equals BarClose up to the first realtime
  bar; the blue shading and the "TICK MODE from here" label mark that bar.
- What changes live in Tick mode: arming and cancelling on every tick
  (latched, so no churn), sizing on live equity, the cost gate, the script
  trail ratchet per tick, breakeven per tick, retest lifetime per tick.
- What never changes intrabar: pivot confirmation (latched on close),
  Donchian and previous-day levels (built from prior bars), the
  close-confirm trigger (needs a close), the time stop, the ATR used for
  geometry (frozen to the last closed bar).
- Trail execution = Emulator is the closest thing to a backtestable tick
  trail: the emulator ratchets it on the intrabar path in history and on
  every tick live, and can exit on the same bar the trigger was reached.
  The engine's "tick" trail is a four-node approximation of that, and it is
  the trail mode with the best mean net across the grid.
- Realtime trades made intrabar disappear on reload (the bars are
  re-simulated at bar close). Validation is two chart instances, one in
  each Execution mode, paper-traded side by side for at least two weeks,
  then a diff of their trade lists.
- `calc_on_order_fills` stays off. On historical bars it would let the
  fill-triggered execution see the bar's final high, low and close.

## 10. v2.01 acceptance recipe

To reproduce the v2.01 trade population with v2.10: Execution BarClose, Arm
latch off, Pivot only (Donchian and previous day off), GeoMode Pct with SL
0.1 and TP 0.25, buffer 1.0 ATR, Trail execution Script with trigger 1.0
and distance 1.5 ATR, cost gate off, TP widening off, cost sizing off, Risk
4, FixedQty 10, cap 50, step 1, commission and slippage as the v2.01 header.
Entry IDs are still BuyStop/SellStop. Two residual differences: v2.10 snaps
order prices to the symbol's mintick, and v2.10 uses `strategy.entry` so the
position-size rail is live (it does not bind at those settings).

## 11. Not modelled, or only partly

- Swap and funding (see section 3).
- Bid/ask: the tester and the engine fill at last/bid prices; half spread per
  side in `CommCash` is the compromise.
- Limit fills (Retest trigger) are never slipped by the tester; the cost
  model still charges `SlipUSD` on them, so the gate, TP and sizing stay
  conservative while the tester's P&L is optimistic by about half a spread.
- The compression gate needs 200 bars of history, so on a 600-bar export it
  is closed for a third of the window; it was exercised, not calibrated.
- Exchange presets assume taker fills for stop entries and stop exits; TP
  limit fills could be maker, which would lower the exchange round trip to
  roughly $70-75.

## 12. Reproduce

```bash
pip install pandas numpy
python3 calibration/xpw_backtest.py sweep                                   # v2.01 arming, pivot levels -> results/
python3 calibration/xpw_backtest.py sweep --arm v201,latch --levels pivot,pivot+don20 --out latch
python3 calibration/xpw_backtest.py parity
python3 calibration/xpw_backtest.py run --tf 60 --sl-mode atr --sl 3 --tp-r 3 --barsn 3 --buf 0.5 --trail tick --cost cfd_raw --arm latch
python3 calibration/xpw_backtest.py geometry
```
