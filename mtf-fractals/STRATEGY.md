# MTF Fractals + Stage v6 — strategy

`mtf_fractals_stage_strategy_v6.pine` turns the indicator into a backtestable
TradingView strategy. The indicator part is `mtf_fractals_stage_v6.pine` with
its `alertcondition()` calls removed (strategies alert on order fills
instead): the same engine, table, labels and lines. A strategy section is
appended that places orders from the chart-timeframe stages.

Important: no backtest could be run here (no TradingView access). The defaults
below are calibrated in ATR units from the same volatility figures as the
indicator and are a sensible starting point, not an optimised result. Section 5
explains how to test and tune them in the Strategy Tester.

## 1. Rules

**Entries** (evaluated on the bar close):

| Entry | Long | Short |
|-------|------|-------|
| Breakout | The chart-TF swing high turns **Broken**: the bar closes above the last swing high by more than the break buffer, and not more than 1.5 × ATR above it (no chasing). A re-break after a failed break counts. | The chart-TF swing low turns Broken, mirrored. |
| Flip retest | The chart-TF swing high is in **Flip retest** (broken earlier, price left and came back to the level from above) and the bar closes above the level. One entry per level. | Mirrored on the swing low. |

Both entry types are on by default; either can be switched off.

**Higher-timeframe bias filter.** The net bias of the visible higher-timeframe
rows (the Chart row excluded: +1 per row whose swing high is broken, −1 per row
whose swing low is broken) must be ≥ *Min net higher-TF bias* for a long and ≤
minus that value for a short. With the default 0 the net higher-timeframe
picture must not be against the trade (one row for and one against still
passes); with 1 the net must lean at least one row in the trade direction. A
value above the number of higher rows visible on the chart (1H chart: 4H, D,
W = 3; D chart: W = 1) blocks every entry.

A long and a short signal can only both qualify on the same bar (the close sits
between a swing high that lies below a swing low) when the net bias is 0; the
direction is then ambiguous and both are skipped.

**Other entry filters.** Backtest date range; trading session on intraday
charts (exchange time, default always; ignored on D and above); gold rollover
window (when the rollover filter is on, i.e. Auto on the XAUUSD profile at a
venue that halts, or On; charts up to 1H only): no entries on chart bars
opening 16:40–18:20 New York, 16:30 for 30m and 45m charts, 16:00 for 1H. One
position at a time.

**Stops.** Every initial stop sits beyond the broken level's **retest zone**
(retest band + break buffer beyond the level, ≈ 0.65 × ATR), so a normal retest
of the level does not stop the trade before breakeven. Once the stop has moved
to the entry (+1 R by default), a retest of the level closes the trade at the
entry price. Every initial stop is also at least *Min stop distance* from the
entry; with the default band the zone is already wider, so that floor only acts
with a narrower retest band or in Percent band mode.

| Entry | ATR mode (default) | Structure mode |
|-------|--------------------|----------------|
| Breakout | the wider of entry − 1.5 × ATR and the far edge of the retest zone | beyond the opposite chart-TF swing plus its buffer, but never inside the zone (a swing inside the zone gives the zone edge); falls back to ATR mode when that swing is missing, at or above the entry, or more than 4 × ATR away |
| Flip retest | just beyond the retested level's zone (≈ 0.65 × ATR past the level) | same |

**Other exits.**

| Exit | Default | Meaning |
|------|---------|---------|
| Target | 2 R | Two times the stop distance from the entry. 0 disables it. |
| Breakeven | at +1 R | Once a bar has reached 1 R in favour **and closed beyond the entry**, the stop moves to the entry price. |
| ATR trail | off | Stop trails `close − N × ATR` when enabled. |
| Opposite break | on | A long is closed when the chart-TF swing low turns Broken (a short mirrored). If that break also passes the entry filters, the position is **reversed** instead, so the breakout is not lost. |
| Any-signal reversal | off | When on, any opposite entry signal reverses the position. |
| Time stop | off | Close after N bars. |

**Position size.** Each trade risks *Risk per trade* (1 %) of current equity,
unless the leverage cap or rounding reduces it: size = equity × 1 % ÷ (stop
distance × point value). That is ounces on gold CFDs, BTC on spot bitcoin, and
contracts on futures (GC, MGC, BTC, MBT, always rounded down to whole
contracts). The size is capped at *Max position size* × equity (10× by
default) and optionally rounded down to a *Quantity step* (1 for OANDA's whole
ounces, 0.0001 for BTC). A size that rounds to 0 skips the signal; skipped
signals are counted in the Data Window and flagged with a label on the last
bar.

Futures need enough equity for one whole contract. At 1 % risk with the default
1H breakout stop, one contract risks about $2,000 on GC, $200 on MGC and $3,900
on CME BTC, so the default $10,000 capital trades none of them. Raise *Initial
capital* to about $20,000 for MGC, $200,000 for GC or $400,000 for CME BTC, or
raise *Risk per trade*. MBT and CFD / spot symbols are fine at $10,000.

**Order model.** `process_orders_on_close` is on: entries and market exits fill
at the close of the signal bar. Stops and targets are resting orders, live from
the next bar. The margin check is off (`margin_long = margin_short = 0`;
Pine v6 would otherwise default to 100 % and reject any position larger than
equity); leverage is controlled by *Max position size* instead.

## 2. Why these defaults

| Setting | Gold (1H) | BTC (1H) | Reasoning |
|---------|-----------|----------|-----------|
| Breakout stop 1.5 × ATR | ≈ $20 | ≈ $780 | Beyond the retest zone (0.65 ATR) plus a push through it. |
| Flip-retest stop | ≈ $8.50 past the level | ≈ $340 past the level | The flip has failed once price closes back through the zone; a wider stop would keep the trade after its premise is gone. |
| Min stop 0.5 × ATR | ≈ $6.50 | ≈ $260 | A safety floor. With the default band every stop is already ≥ 0.65 × ATR (the retest zone), so it only binds with a retest band below ≈ 0.35 × ATR or in Percent band mode. |
| Max extension 1.5 × ATR | | | A close more than 1.5 ATR past the level needs a 2+ ATR stop to clear the zone; skipping those avoids chasing. |
| Target 2 R | ≈ $40 | ≈ $1,560 | About three hourly ATRs: reachable within a session on a real breakout, enough to pay for the losers at a 40 % win rate. |
| Breakeven at 1 R | | | Turns a breakout that ran one stop distance and came back into a scratch instead of a full loss. |
| Risk 1 % | $100 → ≈ 5 oz (≈ 2× equity) | $100 → ≈ 0.13 BTC (≈ 1× equity) | Fixed-fractional sizing; ten losses in a row cost about 10 %. |
| Max size 10× equity | | | Covers 1 % risk on breakouts down to 5m gold (≈ 4–7× equity). Flip-retest stops are only ≈ 0.65–1.15 ATR, so they need ≈ 3–5× on 1H gold and ≈ 9–16× on 5m gold; on 5m the cap binds and those trades risk less than 1 %. Set 1 for spot BTC without leverage: flip retests and most trades below 1H are then capped below 1 % risk. |
| Net bias ≥ 0 | | | The chart-timeframe break is the trigger; the higher timeframes only veto. Raise to 1 for fewer, more aligned trades. |

On 5m charts the same multipliers give a ≈ $6 stop on gold and ≈ $225 on BTC;
costs then matter far more (section 4), and a net bias of 1 is worth testing.

## 3. Alerts

Strategies cannot use `alertcondition`. Create a **Strategy alert** on the
script (alert dialog → condition: the strategy → "Order fills and alert()
function events") and use `{{strategy.order.alert_message}}` in the message
box. Every entry, stop, target and close carries a ready-made text such as
`MTF Fractals: LONG XAUUSD at 4172.50 · position 5.13 · stop 4152.40 · target 4212.70`
or `MTF Fractals: long exit XAUUSD (stop 4152.40, target 4212.70)`.

A reversal is a single order: its text reads `REVERSE long to SHORT …` and
gives the new position size. The old position is closed by the same order, so
no separate exit or "closed" text is sent. A bridge that sizes orders itself
should treat LONG / SHORT as "go to this position" or use
`{{strategy.position_size}}`.

## 4. Costs to set in Properties

The script's defaults (0.02 % commission per side, 2 ticks slippage) are a
middle ground between the two markets and are wrong for both: too high for a
gold CFD, too low for BTC spot. Set your venue's numbers in the strategy's
**Properties** tab before trusting a result:

| Venue | Commission (% per side) | Slippage |
|-------|-------------------------|----------|
| Gold CFD (OANDA, FOREX.com, FXCM) | 0.005 % (≈ $0.21 per oz per side, covering the ≈ $0.30 spread) | 2 ticks |
| COMEX GC / MGC | switch to a per-contract commission | 1–2 ticks |
| BTC perpetual (Binance, Bybit) | 0.05 % taker | 2–5 ticks |
| BTC spot (Coinbase, Bitstamp) | 0.1–0.4 % depending on fee tier | 2 ticks; also set Direction to Long only and Max position size to 1 |

The loss at a stop is the 1 % risk **plus** costs. On 1H charts with the
defaults that is about 1.1 %; on 5m gold with a CFD spread it is about 1.05 %.

## 5. How to test and tune

1. Load the strategy on the chart and timeframe you trade (gold 15m–1H and BTC
   15m–4H are the natural ranges for these rules) and set the costs.
2. In the Strategy Tester check the number of trades (fewer than 100 is not
   enough to judge), profit factor, maximum drawdown and average trade in R.
   The margin check is off, so the tester never shows a margin call; check
   leverage instead: the largest position value in the List of trades should
   stay within what your account allows. The Data Window's "Signals skipped
   (size 0)" should be 0 or small.
3. Tune one thing at a time, in this order: *Min net higher-TF bias* (0 → 1),
   *Breakout stop* (1.0–2.5 ATR), *Target* (1.5–3 R), *Breakeven* (off / 1 R /
   1.5 R), then *Breakout stop placement* (ATR vs Structure). Do not tune the
   indicator's band and buffer for the strategy: they define what a break and
   a retest are.
4. Walk forward: tune on one period, confirm on the next. A setting that only
   works on one year is noise.
5. Compare entry types: run with only breakouts, then only flip retests. They
   behave differently and may deserve different settings.

## 6. Known limits

- Stops are sized from the chart timeframe's ATR at the signal bar and never
  widen after entry. The ATR trail uses the current ATR but only ratchets
  toward price, so it does not help when volatility rises.
- One position at a time, no scaling in or out.
- The bias filter counts the higher-timeframe rows visible on the chart; on a
  4H chart only D and W contribute.
- The script computes on the bar close; "Recalculate on every tick" in
  Properties changes the fills and is not recommended.
- Sizing ignores costs, so the realised loss at a stop is slightly above the
  risk setting.
