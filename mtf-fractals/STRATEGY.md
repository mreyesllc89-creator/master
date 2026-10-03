# MTF Fractals + Stage v6 — strategy

`mtf_fractals_stage_strategy_v6.pine` turns the indicator into a backtestable
TradingView strategy. The indicator part is identical to
`mtf_fractals_stage_v6.pine` (same engine, table, labels and lines); a strategy
section is appended that places orders from the chart-timeframe stages.

Important: no backtest could be run here (no TradingView access). The defaults
below are calibrated in ATR units from the same volatility figures as the
indicator and are a sensible starting point, not an optimised result. Section 5
explains how to test and tune them in the Strategy Tester.

## 1. Rules

**Entries** (on the bar close, filtered by the higher-timeframe bias):

| Entry | Long | Short |
|-------|------|-------|
| Breakout | The chart-TF swing high turns **Broken**: the bar closes above the last swing high by more than the break buffer. | The chart-TF swing low turns Broken. |
| Flip retest | The chart-TF swing high is in **Flip retest** (broken earlier, price pulled away and is now back at the level from above) and the bar closes above the level. One entry per level. | Mirrored on the swing low. |

Both entry types are on by default; either can be switched off.

**Higher-timeframe bias filter.** The bias of the visible higher-timeframe rows
(the Chart row excluded) must be ≥ *Min higher-TF bias* for a long and ≤ minus
that value for a short. With the default 0 the higher timeframes must simply
not be against the trade; with 1 at least one higher timeframe must already
have broken in the trade direction.

**Other entry filters.** Backtest date range, trading session (exchange time,
default always), and the gold rollover window (no entries on chart bars that
open in the 16:40–18:20 New York window on the XAUUSD profile; 16:30 for 30m
and 45m charts, 16:00 for 1H). Only one position at a time; an opposite signal
flips the position only if *Allow reversal* is on.

**Exits.**

| Exit | Default | Meaning |
|------|---------|---------|
| Stop | entry − 1.5 × chart ATR | *Structure* mode instead puts it beyond the opposite chart-TF swing (breakout) or beyond the retested level (flip retest), plus the break buffer, falling back to ATR if that level is missing or on the wrong side. |
| Target | 2 R | Two times the stop distance. 0 disables it. |
| Breakeven | at +1 R | Once price has moved one stop distance in favour, the stop moves to the entry price. |
| ATR trail | off | Stop trails `close − N × ATR` when enabled. |
| Opposite break | on | A long is closed when the chart-TF swing low turns Broken; a short when the swing high turns Broken. |
| Time stop | off | Close after N bars. |

**Position size.** Each trade risks *Risk per trade* (1 %) of current equity:
quantity = equity × 1 % ÷ stop distance, in units of the symbol (ounces for
gold, BTC for bitcoin). The same setting therefore means the same account risk
on both markets, whatever their price.

**Order model.** `process_orders_on_close` is on, so entries fill at the close
of the signal bar, the same bar the indicator's alerts fire on. Stops and
targets are live from the next bar. Commission is 0.03 % per side and slippage
2 ticks; adjust both in the strategy's Properties tab to your broker (see
section 4).

## 2. Why these defaults

| Setting | Gold (1H) | BTC (1H) | Reasoning |
|---------|-----------|----------|-----------|
| Stop 1.5 × ATR | ≈ $20 | ≈ $780 | Beyond the retest band (0.5 ATR) plus a push through it, so a normal retest of the broken level does not stop the trade out. |
| Target 2 R | ≈ $40 | ≈ $1,560 | About three hourly ATRs: reachable within a session on a real breakout, far enough to pay for the losers at a 40 % win rate. |
| Breakeven at 1 R | | | Converts a breakout that ran one stop distance and came back into a scratch instead of a full loss. |
| Risk 1 % | $100 → ≈ 5 oz | $100 → ≈ 0.13 BTC | Standard fixed-fractional sizing; survives a run of ten losses with a 10 % drawdown. |
| Bias ≥ 0 | | | The chart-timeframe break is the trigger; the higher timeframes only veto. Raise to 1 for fewer, more aligned trades. |

On 5m charts the same multipliers give a $6 stop on gold and $225 on BTC; the
spread and commission then matter more (section 4) and *Min higher-TF bias* of
1 is worth testing.

## 3. Alerts

Strategies cannot use `alertcondition`. Create a **Strategy alert** on the
script (alert dialog → condition: the strategy → "Order fills and alert()
function events"); every entry, stop, target and close carries a message such
as `MTF Fractals: LONG XAUUSD at 4172.50`.

## 4. Costs to set in Properties

| Market | Commission | Slippage |
|--------|------------|----------|
| Gold CFD (OANDA, FOREX.com, FXCM) | 0 % commission, but the spread is ≈ $0.30 in liquid hours and $1–3 at the rollover. Enter the spread as slippage: 30 ticks on a 0.01-tick feed, 300 on a 0.001-tick feed. | |
| COMEX GC / MGC | per-contract commission (set `commission_type` to per contract) | 1–2 ticks |
| BTC spot (Coinbase, Bitstamp, Binance) | 0.05–0.1 % per side taker; set 0.1 % to be conservative | 1 tick on a $1 tick, 100 on a $0.01 tick |

The 0.03 % / 2-tick defaults are a middle ground; the backtest is only as
honest as these two numbers.

## 5. How to test and tune

1. Load the strategy on the chart and timeframe you trade (gold 15m–1H, BTC
   15m–4H are the natural ranges for these rules).
2. In the Strategy Tester check the number of trades (fewer than 100 is not
   enough to judge), profit factor, maximum drawdown and average trade in R.
3. Tune one thing at a time, in this order: *Min higher-TF bias* (0 → 1),
   *Stop distance* (1.0–2.5 ATR), *Target* (1.5–3 R), *Breakeven* (off / 1 R /
   1.5 R), then *Stop placement* (ATR vs Structure). Do not tune the indicator's
   band and buffer for the strategy: they define what a break and a retest are.
4. Walk forward: tune on one period, confirm on the next. A setting that only
   works on one year is noise.
5. Compare entry types: run with only breakouts, then only flip retests. They
   behave differently; on gold the flip retest is usually the cleaner entry.

## 6. Known limits

- Entries and stops use the chart timeframe's ATR at the signal bar; the stop
  does not widen if volatility rises after entry (the trail can be used for
  that).
- One position at a time, no scaling in or out.
- The bias filter counts the higher-timeframe rows that are visible on the
  chart; on a 4H chart only D and W contribute.
- The script computes on the bar close; "Recalculate on every tick" in
  Properties would change the fills and is not recommended.
