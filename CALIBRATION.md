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
| Include commission | Header only: 0.003 USD per oz per side and 30 ticks slippage. On BTC that is $0.61 per round trip, 35-140x below any real venue. Nothing in the logic knew about costs. | Cost inputs (commission %, commission cash per contract per side, slippage per side) drive a cost gate, TP widening by both commissions so the net target equals the input (entry slippage already sits inside the fill price and a limit exit is never slipped), cost-aware risk sizing, a breakeven step at fill plus commissions plus one exit slip, and a referee table that compares the commission the tester actually charged with the modelled figure. Header re-based to BTC. |
| More extensive entry | One level source (confirmed pivot), one trigger (stop straddle), a session filter and a compression gate. The stop was cancelled on every bar whose close sat inside the buffer (F11), so most breaks never had an order resting. | Three level sources (pivot, Donchian of the prior N bars, previous-day high/low; nearest enabled level is used), three triggers (resting stop, close-confirmed market entry with a chase cap, retest limit with a lifetime), an arm latch that keeps the stop resting, plus direction, chart-EMA trend, cooldown, max trades per day, retry cap per level, trade days, session, compression and cost gates. |
| Entry by tick | Bar-close only ("Script execution = ON BAR CLOSE ONLY"). | `calc_on_every_tick=true` with an Execution input. Tick mode re-evaluates arming, cancelling, sizing, the cost gate and the trail on every live tick; state is `varip` so it survives the per-tick rollback. The trail can be handed to the broker emulator (`trail_points`/`trail_offset`), which ratchets intrabar on history and per tick live. Levels still come from confirmed bars because an unconfirmed level cannot be backtested. |

Defects found on the way (all fixed in v2.10, see the script header):

- F11: the buffer was a keep-alive test, not an arming test. At buffer 1.0 ATR
  the exports show 60m armed 4 of 37 confirmed breaks and 15m 10 of 54. In
  tick mode this would have been fatal: the first tick inside the buffer
  cancels the stop and it can never fill.
- F12: `strategy.risk.max_position_size` only constrains `strategy.entry()`;
  v2.01 used `strategy.order()`, so its hard cap was inert.
- F13: ATR geometry recomputed after the fill is a moving target; SL, TP,
  trail trigger and trail distance are now locked per trade at arm time and
  re-anchored to the real fill. Percent geometry is re-derived from the fill
  (the v2.01 form).
- F14: the pre-staged bracket is expressed in ticks from the fill
  (`strategy.exit` loss/profit) rather than absolute prices anchored to the
  level, so a gapped or slipped fill keeps the sized SL and the intended TP on
  the fill bar.
- A `var` trail ratchet re-issued with `strategy.exit` on every tick would
  retreat, because order state is not rolled back between ticks but `var`
  state is. Trail state is `varip`.
- Four review rounds (five to six lenses, two independent refuters per
  finding) found and fixed thirty-four further defects in the v2.10 drafts,
  among them: the latch was not keyed to the level it armed on (a replaced
  level re-priced the resting stop with no buffer check), a transient
  filter closure dropped the latch, close-based filters flickered per
  tick, the retest invalidation ran on interim ticks in BarClose mode, the
  loss cap never applied in CloseConfirm/Retest, the compression gate
  measured the wrong pair, the day counter differed between history and
  live, a same-bar round trip left the latch armed on history but not live,
  the latch identity was only recorded when an order was placed, and the
  quantity step rounding lost a step on exact multiples. USD inputs are
  converted to price units through `syminfo.pointvalue`; the table flags a
  symbol whose pointvalue is not 1 because the script is calibrated for
  feeds where one contract is one BTC.

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
| cfd_raw | 0 | 9.0 | 5.0 | $28 | `cash_per_contract`, 9.0, slippage 500 | VT Raw ECN $3 per lot per side ($6 RT) verified for FX, assumed for BTCUSD; raw spread $12 from IC Markets. |
| vt_btc (shipped default) | 0 | 10.5 | 5.0 | $31 | `cash_per_contract`, 10.5, slippage 500 | The user's VT Markets MT5 account: BTCUSD spread 2,100 points = $21, no commission shown in the specification or deal history. Within $4 of cfd_std, so the sweep results stand. |
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
1.5 ATR, latch on, cost gate 20% of net TP, cfd_raw costs. One deliberate
difference from the engine: the script locks the trail trigger and distance
at arm time (F13), while the engine (and v2.01) followed the live ATR bar by
bar; over the 8-17 bar holds seen here the ATR drifts little, so this is a
second-order effect. Marginals over
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
latch off, Pivot only with BarsN 5 (Donchian and previous day off), GeoMode
Pct with SL 0.1 and TP 0.25, buffer ATR 1.0, Trail execution Script with
trigger 1.0 and distance 1.5 ATR, cost gate off, TP widening off, cost
sizing off, cost inputs CommPct 0 / CommCash 0.003 / SlipUSD 0.3 (so the
referee rows agree with the gold Properties), Risk 4, FixedQty 10, cap 50,
QtyStep 1, and Properties > Slippage 30 ticks, Commission 0.003 cash per
contract (type them in, then Reset settings and restore the cost inputs
afterwards to return to the BTC header). Entry IDs are still
BuyStop/SellStop. Residual differences: v2.10 snaps order prices to the
symbol's mintick, uses `strategy.entry` so the position-size rail is live (it
does not bind at those settings), locks the trail trigger and distance at
arm time where v2.01 recomputed both from the live ATR every bar, and
pre-stages the fill-bar bracket in ticks from the fill (F14) where v2.01
anchored it to the pivot: on the fill bar both legs are shifted one entry
slippage in the trade direction, so the SL sits that much nearer the pivot
and the TP that much further from it, and a fill-bar extreme inside either
band exits in one script and not the other. From the first run after the
fill both hold the same avg-based bracket.

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

## 13. XAUUSD build

`pine/XPW_Breakout_v2.10_XAUUSD.pine` is the same script with gold defaults.
The logic is byte-identical (checked by stripping comments and inputs and
diffing); the header costs, cost inputs, sizing inputs, geometry defaults
and notes differ.

### Data

OANDA:XAUUSD exports made with the v2.01 build on the chart (its Swing High /
Swing Low columns match the engine's BarsN 5 pivots 99.7 to 100%). A
Pepperstone 10m export made with the v2.10 build was also checked: the
engine's nearest-level pick matched its Level Up / Level Down columns 99.9%
of the time at BarsN 3, which confirms the v2.10 level logic as it runs on
TradingView.

| File | Bars | Span | Median ATR14 | ATR % of price |
|---|---|---|---|---|
| `XAUUSD_5.csv` | 719 | 2.6 days | 4.32 | 0.100 |
| `XAUUSD_10.csv` | 2161 | 22 days | 6.61 | 0.152 |
| `XAUUSD_15.csv` | 1672 | 26 days | 8.28 | 0.190 |
| `XAUUSD_30.csv` | 895 | 28 days | 12.01 | 0.275 |
| `XAUUSD_60.csv` | 895 | 55 days | 17.90 | 0.409 |
| `XAUUSD_240.csv` | 895 | 210 days | 39.19 | 0.880 |

### Costs

| Setting | BTCUSD build | XAUUSD build |
|---|---|---|
| Contract | 1 BTC (1 MT5 lot) | 1 oz (100 oz = 1 MT5 lot) |
| Header commission | cash 10.5 per contract per side (VT: $21 spread, no commission) | cash 0.13 per oz per side (VT: 2.5 pips = $0.25 spread, $0.6 per lot commission) |
| Header slippage | 500 ticks ($5) | 5 ticks ($0.05 per oz) |
| CommCash / SlipUSD inputs | 10.5 / 5.0 | 0.13 / 0.05 |
| FixedQty / cap / step | 0.1 / 2.0 / 0.01 BTC | 10 / 50 / 1 oz |

Round trip at the shipped numbers is $0.36 per ounce ($36 per lot): 3 to 8%
of one ATR on 10m to 240m, so on gold the cost gate never binds and the
geometry question is about noise, not cost. The sweep used $0.31 (raw) and
$0.40 (standard) presets and both give the same picks. The shipped figures
come from the user's VT Markets MT5 account (2.5 pips spread, $0.6 per lot
commission).

### Sweep (latch on, gold presets, fixed 1 oz; multiply net by 100 for one lot)

Grid as for BTC (SL pct/ATR bands x TP R x BarsN x buffer x trail x
levels). Results: `calibration/results/xau/`.

Shipped gold defaults: ATR mode, SL 1.5 ATR, TP 2.5R, BarsN 3, buffer 1.0,
Emulator trail (trigger 1.0, distance 1.5 ATR). Net per ounce at those
settings, pivot levels, raw costs:

| TF | trades | net per oz (Emulator trail) | net per oz (Script trail) |
|---|---|---|---|
| 5m | 48 | -59 | -21 |
| 10m | 134 | +99 | +64 |
| 15m | 101 | +213 | +260 |
| 30m | 54 | +194 | +275 |
| 60m | 55 | +171 | +178 |
| 240m | 53 | +487 | +1122 |

The BTC defaults (SL 3 ATR, TP 3R, buffer 0.5) are marginal on gold: negative
on 5m and 10m at BarsN 3, and +106 to +127 per ounce on 30m and 60m. Gold
wants a tighter stop and a less greedy target than BTC. Marginals over the
measurable grid (10m to 240m): SL 1.5 ATR has the best positive fraction
(86%), TP 2.5R the best mean net, BarsN 3 and 5 beat 8, buffer 1.0 edges
0.5, and the bar-close trail beats the tick trail on mean net (128 vs 94
per ounce) while the tick trail has the higher positive fraction (82 vs
80%). Emulator execution is kept as the default for history-versus-live
consistency; switch to Script if you prefer the v2.01 close-anchored
ratchet.

Per-timeframe plateau picks (every grid neighbour positive), pivot levels,
raw costs:

| TF | pick | trades | win % | net per oz | PF | max DD per oz |
|---|---|---|---|---|---|---|
| 10m | Pct SL 0.5%, TP 2.5R, BarsN 8, buffer 0.5, no trail | 23 | 57 | +452 | 3.06 | 44 |
| 15m | ATR 3.0, 2.5R, BarsN 3, buffer 2.0, no trail | 18 | 56 | +551 | 3.46 | 56 |
| 30m | ATR 3.0, 1.5R, BarsN 3, buffer 2.0, tick trail | 35 | 69 | +389 | 6.20 | 40 |
| 60m | ATR 3.0, 2.5R, BarsN 3, buffer 0.5, bar trail | 39 | 54 | +579 | 2.50 | 106 |
| 240m | ATR 3.0, 1.5R, BarsN 3, buffer 1.0, bar trail | 34 | 76 | +1526 | 2.69 | 176 |

These beat the shipped defaults on their own timeframe but are single cells
with 18 to 39 trades; the shipped defaults were chosen for being positive
everywhere rather than best anywhere. 5m is not worth trading with this
system: 2.6 days of data, and every geometry that survives costs elsewhere
is negative there.

The v2.01 gold geometry (SL 0.1%, TP 0.25%) is not sub-noise on gold the way
it is on BTC (SL 0.1% is 0.65 ATR on 10m), and with the latch it is mildly
positive on 10m to 30m (PF 1.1 to 1.5 over 56 to 114 trades). On 60m and
240m 67 to 88% of its trades resolve inside the fill bar, the same emulator
artefact seen on BTC, so those rows do not count.

Adding Donchian 20 levels raises trade counts by 30 to 60% and helps on 10m
(79 trades, +287 per ounce at SL 1.0%, 2R, BarsN 8) and 240m (+1661 at SL
1.5 ATR, 3R) but not elsewhere; it stays off by default.

### Walk-forward

`calibration/walkforward.py` splits each gold export in half, picks on the
first half only, and scores on the second half (full tables in
`calibration/results/xau/walkforward.md`). Three candidates per timeframe:
the shipped defaults, the first-half plateau pick, and the first-half best
cell. Out-of-sample net per ounce:

| TF | shipped defaults | first-half plateau pick | first-half best cell |
|---|---|---|---|
| 10m | +8 | +80 | +143 |
| 15m | +177 | -42 | +223 |
| 30m | +79 | -13 | +22 |
| 60m | +186 | -85 | -396 |
| 240m | +294 | +435 | +435 |
| positive out of sample | 5 of 5 | 2 of 5 | 4 of 5 |

Reading: settings optimised on one timeframe's first half fail on its second
half two or three times out of five, and the 60m best cell (5 in-sample
trades, PF 11) loses 396 per ounce out of sample, which is why the report
ships one cross-timeframe geometry instead of the per-timeframe picks. Two
honest caveats: the shipped defaults were chosen on the full exports, so
the second halves were not unseen by that choice (although choosing one
geometry for five timeframes is a far weaker selection than choosing a cell
per timeframe), and the 10m result is a coin flip at +8. On 240m the whole
grid is only 46% positive in the second half, so the 240m number rests on
the trend of that period more than on the geometry.

Not modelled: the daily maintenance break and weekend gap (use the session
and trade-day inputs), and gold swaps, which are charged per lot per night
with a triple Wednesday and can exceed the round-trip cost on a 60m or 240m
hold.

## 14. BTC 5m and sub-minute exports (MEXC:BTCUSDT)

Three further BTC exports were checked: 5m (2,258 bars, 7.8 days, Sept 16 to
24), 30s (566 bars, 4.7 hours) and 15s (615 bars, 2.6 hours). Cost presets:
`vt_btc` (the VT Markets account: $21 spread, no commission, $5 slip; round
trip $31) and `mexc` (0.02% taker per side, round trip about $38). Results
in `calibration/results/btc5/`.

**Sub-minute bars are not tradeable with this system at any real cost.** The
round trip is 1.5 ATR on 30s and 2.3 ATR on 15s at VT costs (4 to 6 ATR at
exchange taker fees). Frictionless, 93 to 100% of configurations are
positive; at VT costs 14 to 23%; at MEXC costs 2 to 8%. Costs eat 66 to 126%
of gross. Nothing to calibrate there.

**5m: the shipped BTC defaults lose.** SL 3 ATR, TP 3R, BarsN 3, buffer 0.5,
latch on, pivot levels: 109 trades, -6,519 per BTC at VT costs, and -3,064
even frictionless. Only 8% of measurable 5m configurations are positive; the
one band that works is a percent stop of 1.0% (about 8 ATR on 5m) with
BarsN 8, 16 to 45 trades, which is the 15m/60m geometry in dollar terms and
gains nothing from 5m bars.

To separate the week from the timeframe, the same defaults were run over
the same Sept 16 to 23 window on the CRYPTO:BTCUSD exports:

| TF, same week | trades | net per BTC (VT costs) | PF |
|---|---|---|---|
| 5m (MEXC) | 109 | -6,519 | 0.49 |
| 15m | 37 | +4,314 | 1.81 |
| 30m | 22 | +805 | 1.12 |
| 60m | 8 | +8,085 | 7.44 |

Same market, same week, same settings: positive from 15m up, negative on
5m. The 5m pivots churn (about 14 trades per day), the buffer and stop are
sized to a bar that is a quarter of the size of a 15m bar, and the round
trip is 0.3 ATR instead of 0.08 on 60m. The BTC calibration therefore
stands as shipped, with an explicit rule: do not run the BTC build below
15m. If a 5m chart must be used, GeoMode Pct with SL 1.0%, TP 1R to 3R,
BarsN 8 is the only band with evidence, and that evidence is one week.

MEXC's exported Swing High/Low columns match the engine's BarsN 5 pivots
96 to 97% (the MEXC feed's highs and lows differ slightly from the
CRYPTO index), so the engine was validated on this feed as well.

## 15. Continually moved stops: Donchian levels and the Follow policy

Question asked: does re-pricing the buy stop and sell stop continually,
instead of parking them on the last confirmed pivot, raise net and profit
factor? Two things were separated, because "moving the stop" can mean
either:

- **the level itself moves every bar**: Donchian prior-N high / low
  (`UseDonchian`, `DonLen`) instead of the BarsN pivot, tested at N = 5,
  10, 20 and 50 alongside the pivot;
- **what a latched stop does when its level is replaced**: `Recheck` (the
  engine's "latch" since this sweep: the new level must pass the buffer
  again) or `Follow` (the engine's "hold": the resting stop is re-priced
  to the new level at once, no buffer re-check). Both are now the
  `LvlMove` input in both builds.

A correction that came out of this sweep: until the "hold" mode was added,
the engine's latch never re-checked the buffer when a level was replaced,
so every earlier number in this report (the BTC latch sweep in section 7,
the shipped 60m block, the gold sweep and walk-forward in section 13, the
5m check in section 14) was measured under what is now called Follow. The
v2.10 script, after the review fix that keyed the latch to its level, had
been re-checking the buffer, which is Recheck. The script default is
therefore set to Follow so that it matches what was calibrated; Recheck is
the option. On BTC 60m the two are within 70 per BTC of each other
(+10,004 against +9,937); on gold the shipped-default rows of section 13
(+99, +213, +194, +171, +487 per ounce on 10m to 240m) are Follow, and
Recheck gives +19, +216, +92, +86, +648.

Full grid (SL band x TP R x BarsN x buffer x trail) for every level source
and both policies: BTC 15m/30m/60m/240m at `vt_btc` and gold 10m to 240m
at `gold_raw`. Results in `calibration/results/don_btc/` and `don_xau/`.
Net per BTC and per ounce, 1 unit fixed.

### Follow versus Recheck: no consistent edge

Paired over every grid cell (same geometry, same level source, both
policies measurable): the share of cells where Follow beat Recheck on net,
and the median PF difference (Follow minus Recheck).

| TF | pivot | don5 | don10 | don20 | don50 |
|---|---|---|---|---|---|
| BTC 15m | 54% / +0.04 | 49% / +0.06 | 1% / -0.35 | 84% / +0.13 | 19% / -0.05 |
| BTC 30m | 25% / -0.10 | 13% / -0.25 | 27% / -0.07 | 27% / -0.06 | (identical) |
| BTC 60m | 12% / -0.12 | 84% / +0.16 | 17% / -0.23 | 9% / -0.04 | (identical) |
| BTC 240m | 31% / -0.06 | 44% / -0.13 | 86% / +0.18 | 83% / +0.09 | 63% / +0.08 |
| gold 10m | 64% / +0.03 | 82% / +0.11 | 49% / -0.05 | 78% / +0.04 | 4% / -0.13 |
| gold 15m | 86% / +0.08 | 48% / -0.02 | 45% / -0.07 | 75% / +0.03 | 7% / -0.07 |
| gold 30m | 55% / 0.00 | 55% / 0.00 | 63% / +0.02 | 51% / -0.05 | 26% / -0.05 |
| gold 60m | 68% / +0.07 | 40% / -0.05 | 23% / -0.16 | 54% / -0.01 | 34% / -0.03 |
| gold 240m | 45% / 0.00 | 72% / +0.02 | 34% / -0.10 | 44% / 0.00 | 3% / -0.01 |

Follow adds trades (median 2 to 12 more per file, more on the short
Donchian lengths) and its PF moves by less than 0.1 in most cells, in both
directions. It wins on BTC 15m and loses on BTC 30m/60m with the same
level source. On gold it is slightly ahead with pivot levels on 15m and
60m and behind with don10/don50. There is no timeframe or level source
where it is better on both symbols. Conclusion: continually re-pricing the
stop is not an edge in itself; it is a neutral option. Follow is the
default because sections 7, 13 and 14 were measured with it (see the
correction above); the acceptance recipe in section 10 runs with the latch
off, where the policy does not apply.

### Level source: where Donchian beats the pivot

Shipped geometry (BTC: ATR 3.0 / 3R / BarsN 3 / buffer 0.5 / Emulator
trail; gold: ATR 1.5 / 2.5R / BarsN 3 / buffer 1.0 / Emulator trail),
Recheck policy, whole file and then first half / second half. Trades in
brackets. The Follow rows are in `docs/XPW_Settings_by_Timeframe.pdf` and
in the CSVs.

| TF | pivot | best Donchian | first half / second half of the best |
|---|---|---|---|
| BTC 15m | +1818, PF 1.34 (35) | don20 +5159, PF 2.57 (33) | +1165 / +3579 (pivot: -2007 / +3825) |
| BTC 30m | -51, PF 0.99 (30) | don50 +7585, PF 3.90 (24) | +651 / +3979 (11 trades each half) |
| BTC 60m | +9937, PF 2.29 (31) | don10 +7387, PF 2.00 (32) | -1794 / +8456 (pivot: +397 / +8815) |
| BTC 240m | +1528, PF 1.10 (32) | don20 +4096, PF 1.35 (25) | +860 / +3862; Follow +885 / +5591 |
| gold 10m | +19, PF 1.04 (101) | don10 +182, PF 1.36 (111) | +148 / +33 (pivot: +74 / -56) |
| gold 15m | +216, PF 1.65 (81) | don10 +128, PF 1.29 (81) | pivot wins both halves: +66 / +145 |
| gold 30m | +92, PF 1.34 (44) | don20 +109, PF 1.28 (46) | +40 / +28 (pivot: -3 / +51; pivot Follow +71 / +79) |
| gold 60m | +86, PF 1.17 (48) | don50 +286, PF 2.49 (29) | +167 / +65 (don20: +213, PF 1.61, +174 / +49) |
| gold 240m | +648, PF 1.59 (47) | don10 +656, PF 1.60 (48) | +446 / +163 (pivot: +283 / +365) |

Robustness across the whole grid (share of measurable cells positive,
Recheck): BTC 60m pivot 0.65 against don10 0.90 and don20 0.88, but the
pivot keeps the higher net at the shipped geometry and is the only source
positive in both halves there; BTC 15m don20 0.71 and don50 0.85 against
pivot 0.65; BTC 30m don50 0.79 against pivot 0.76; BTC 240m every
Donchian length below 0.55 and don50 0.02. Gold: pivot 0.90 on 15m and
0.82 on 30m, the highest; don20 0.74 to 0.84 on 10m to 30m; don50 0.84 on
60m (pivot 0.60); don5/don10 0.92 to 0.99 on 240m (pivot 0.63).

Reading: the pivot is not beaten where the builds are meant to run (BTC
60m, gold 15m to 30m), so the defaults do not change. Donchian is the
better level source on the edges: BTC 15m and 240m with length 20, BTC 30m
with length 50 (few trades), gold 10m with length 10 to 20, gold 60m with
length 20 to 50, gold 240m with length 5 to 10. Long Donchian lengths on
short timeframes and short lengths on 240m both fail (don50 on BTC 240m
loses in every band; don5 on BTC 240m loses 13,624).

### What to set

- Defaults: pivot levels, `LvlMove` = Follow (the calibrated policy).
- To trade the timeframes above with a rolling level: `UsePivot` off,
  `UseDonchian` on, `DonLen` as in the table, geometry as shipped. BarsN
  no longer matters once the pivot is off.
- `LvlMove` = Recheck is free to try live; the policy changes trade count
  more than PF. Recheck is ahead on BTC 30m/60m and on gold don10/don50,
  Follow on BTC 15m/240m with don20 and on gold pivots.
- The engine's `--levels` and `--arm` flags reproduce every cell:
  `python3 calibration/xpw_backtest.py run --tf 60 --levels don20 --arm hold --sl-mode atr --sl 3 --tp-r 3 --barsn 3 --buf 0.5 --trail tick --cost vt_btc`.
