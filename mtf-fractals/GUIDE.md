# MTF Fractals + Stage v6 — user guide

This guide explains what the indicator shows, how each stage is decided, how to
read the table and labels, what the alerts mean, and how the settings are
calibrated for XAUUSD and BTCUSD. The technical review of the original script
and the reasoning behind every number is in `REVIEW.md`.

## 1. The idea in one paragraph

On every timeframe, price leaves swing highs and swing lows behind. A Williams
fractal is the simplest objective definition of such a swing: a bar whose high
is higher than the two bars on each side (swing high), or whose low is lower
than the two bars on each side (swing low). The indicator finds the **most
recent** swing high and swing low on the chart timeframe and on up to eleven
other timeframes from 5 seconds to weekly, and then watches what price does
with each of those levels: is it still intact, is price coming back to test it,
has it been broken, did the break fail, is the broken level now being retested
from the other side. Each level is given a **stage** that answers that
question, and a **bias** score sums up across timeframes whether price is
breaking out above resistance or breaking down below support.

## 2. Timeframes

Rows: Chart, 5s, 10s, 15s, 30s, 1m, 5m, 15m, 1H, 4H, D, W.

A row is shown only when its timeframe is **higher than the chart timeframe and
a whole multiple of it**. The reason is technical: TradingView can only return
another timeframe's bars reliably when they are built from several complete
chart bars. The practical consequences:

| Chart | Rows shown |
|-------|------------|
| 1s | Chart (= 1s), 5s, 10s, 15s, 30s, 1m, 5m, 15m, 1H, 4H, D, W |
| 5s | Chart, 10s, 15s, 30s, 1m, 5m, 15m, 1H, 4H, D, W |
| 15s | Chart, 30s, 1m, 5m, 15m, 1H, 4H, D, W |
| 1m | Chart, 5m, 15m, 1H, 4H, D, W |
| 5m | Chart, 15m, 1H, 4H, D, W |
| 15m | Chart, 1H, 4H, D, W |
| 1H | Chart, 4H, D, W |
| 4H | Chart, D, W |
| D | Chart, W |

There is no separate 1s row because nothing is lower than 1s: on a 1s chart
the Chart row **is** the 1s row. Rows that are hidden are summarised in the
tooltip of the Σ row ("3 row(s) below the chart TF, 5m (= chart)"). A row that
is not a whole multiple (the 1H row on a 45m chart, the 15m row on a 2m chart)
is hidden for the same reliability reason.

Seconds rows need a TradingView plan that offers seconds charts. On seconds
charts the loaded history is short, so the D and W rows may show
"only N bars" until enough daily or weekly bars exist to form a fractal.

Everything a higher-timeframe row shows comes from **completed** bars of that
timeframe. The row for the daily timeframe does not change during the day; it
updates once the daily bar has closed. This is what makes the table identical
whether you look at history or at the live bar.

## 3. The table

| Column | Meaning |
|--------|---------|
| TF | The row's timeframe. Hover for how the row is computed. |
| Swing hi | Price of the last confirmed swing high of that timeframe: resistance until broken. Hover for the ATR, the retest band, the break buffer and the level's age. |
| Stage | What price has done with the swing high since it printed (see section 4). Hover for the plain-language meaning. |
| Swing lo | Price of the last confirmed swing low: support until broken. |
| Stage | Same for the swing low. |
| Bias | +1 when the swing high is broken (price above resistance), −1 when the swing low is broken (price below support), 0 otherwise. |

The **Σ row** shows the symbol profile and the active calibration (for example
`XAUUSD · rollover filter  L2/R2  ATR14 ×0.5/0.15`), and the bias total as
`+3 / 5` meaning "+3 summed over 5 rows". Hover the total for the list of hidden
rows.

Prices are printed with 2 decimals for gold, whole dollars for bitcoin, and the
symbol's own tick size for anything else.

## 4. The six stages

Every level has a **retest band** around it and a **break buffer** beyond it.
Both are measured in ATR (average true range), so they scale with the
volatility of the timeframe and the symbol. With default settings:

- retest band = ±0.5 × √(row ATR × chart ATR), never narrower than the buffer
- break buffer = 0.15 × row ATR, never smaller than 0.012 % of the level

| Stage | Colour | Meaning | How it is decided |
|-------|--------|---------|-------------------|
| **Confirmed** | yellow | The fractal has just been confirmed. The level is fresh and untested. | The bar that confirms the fractal has closed (for a higher timeframe: the previous bar of that timeframe). |
| **Holding** | lime | No close through the level yet, and price is away from it. | Level intact and the chart bar is outside the band (or has not left the band since the fractal printed). |
| **Retest** | orange | Price is back at the level and the level is still intact. Watch for a rejection or a break. | Level intact, a chart bar has been entirely outside the band at least once, and the current chart bar's range reaches into the band. |
| **Broken** | red | This timeframe closed through the level by more than the buffer. | The row's own close beyond the level ± buffer. Stays until the level is closed back through (Failed break) or a new fractal replaces it. |
| **Flip retest** | fuchsia | The level was broken, price moved away, and is now back at it from the other side. Old resistance tested as support, or old support as resistance. | Broken, a chart bar has been entirely outside the band since the break, and the current chart bar's range is back inside it. |
| **Failed break** | grey | The level was broken but this timeframe then closed back through it. The break did not hold. | Broken, then the row's own close back on the original side by more than the buffer. Shows Retest while the chart bar is inside the band. A later close beyond the level again returns the row to Broken. |

Two details matter in practice:

- **Break and Failed break are judged on the row's own close**; Retest and Flip
  retest are judged on the live chart bar's range. So a daily level reads
  "Retest" while price tests it during the day and "Broken" only once the daily
  bar has closed beyond it. On the Chart row, with "Chart-TF signals on bar
  close only" on, the break is judged when the chart bar closes.
- **A new fractal replaces the level.** The table always shows the latest swing
  of each side. When a new swing high confirms, its stage starts at Confirmed
  and the old level is no longer tracked (its line disappears).

### Worked example (gold, 1H chart, swing high at 4,170.00, hourly ATR ≈ 13)

Retest band ≈ ±6.5, break buffer ≈ 2.0 (0.15 × 13; the 0.012 % floor is 0.50).

| Hourly close / range | Stage | Why |
|------|-------|-----|
| confirms at 4,160 | Confirmed | the bar after the swing closed, two lower highs on the right |
| 4,155 (bar range 4,152–4,158) | Holding | outside the band, no break |
| range 4,165–4,169 | Retest | bar reaches into the band after being outside it |
| close 4,172.5 | Broken | close more than 2.0 above 4,170 |
| close 4,181 | Broken | away from the level, "armed" for a flip retest |
| range 4,166–4,173 | Flip retest | back inside the band from above |
| close 4,167.5 | Failed break | closed back below 4,170 by more than 2.0 |
| range 4,166–4,172 | Retest | inside the band after the failed break |
| close 4,173 | Broken | broke again; the "swing high broken" alert fires again |

## 5. Bias

Each visible row contributes +1 if its swing high is Broken or Flip retest, −1
if its swing low is Broken or Flip retest, and 0 otherwise. The Σ row shows the
sum and the number of rows counted. The same value is plotted as "MTF fractal
bias" in the Data Window and can tint the chart background (Display settings).

Read it as structure, not as a signal: +3 / 5 means three of five timeframes
have closed above their last swing high and none has closed below its last
swing low. A value near zero means the levels are intact (range) or the
timeframes disagree. Note that this is the **opposite sign to the v5 script**,
which scored intact levels.

## 6. Chart drawings

- **Triangles** mark confirmed fractals on the chart timeframe. They are placed
  on the swing bar itself, two bars back from the bar that confirms it. Large
  by default; the "large" box next to "Plot fractal marks" switches to small.
- **Level lines** extend the chart-timeframe swing high and swing low from the
  swing bar to the current bar. Optional dashed lines do the same for the
  higher-timeframe levels.
- **Labels** at the right edge show the chart-timeframe levels on two lines:
  the price, then the stage and the level's age in bars. Hover a label for the
  stage meaning and the band / buffer in price units. Label size is an input
  (large by default); table text size is a separate input.

## 7. Alerts

Create alerts from the indicator with "Once per bar close" unless noted.

| Alert | Fires when |
|-------|-----------|
| Chart up fractal / Chart dn fractal | A fractal is confirmed on the chart timeframe. |
| Chart swing high broken / Chart swing low broken | The chart timeframe closes through its last swing high / low by more than the buffer, including a re-break after a failed break. |
| Chart swing high retest / Chart swing low retest | The chart bar comes back into the band of the chart-timeframe level (Retest or Flip retest). This is a range event, so "Once per bar" is fine. |
| HTF swing high broken / HTF swing low broken | Any visible higher-timeframe row closes through its last swing high / low. Fires on the first chart bar after that timeframe's bar closes. |

Only visible rows can trigger the HTF alerts; hidden rows never do.

## 8. Settings

**Symbol profile.** Auto detects gold (XAU…, GOLD, GC and MGC futures) and
bitcoin (BTC…, XBT…, BTC and MBT futures) from the symbol. The profile only sets
what genuinely differs between the two markets: gold gets the rollover-window
fractal filter and 2-decimal prices; bitcoin prints whole dollars. Every
calibration input below applies to every profile.

**Fractal.**

- *Bars left / Bars right* — 2 / 2 is the classic Williams fractal. More bars
  on the right means later confirmation; more on the left means fewer, more
  significant swings.
- *Allow equal highs / lows on the left side* — on by default so a double top
  or bottom at exactly the same price registers. Off reproduces the strict v5
  test, under which tied extremes never form a fractal.
- *Ignore gold rollover-window fractals* — gold CFDs and COMEX halt 17:00–18:00
  New York; the thin bars around the halt and the Sunday open print isolated
  extremes that are not tradable levels. On timeframes up to 1H, fractals whose
  centre bar opens 16:40–18:20 New York time are ignored. Auto turns this on
  for the XAUUSD profile on venues that halt; tokenised gold on crypto
  exchanges and bitcoin are exempt. Select On to force it on any symbol.
- *Chart-TF signals on bar close only* — on by default: the Chart row confirms
  fractals and judges breaks when the bar closes, so marks, levels and the
  break alert cannot appear mid-bar and vanish. Off reproduces the v5
  behaviour.

**Stage calibration.**

- *Band mode* — ATR (recommended) or Percent (a fixed % of the level, the v5
  width; the stage logic is the same in both modes).
- *ATR length* — 14.
- *Retest band (× ATR)* — 0.50. Multiplied by the geometric mean of the row's
  ATR and the chart ATR so a daily level seen from a 5m chart gets a band a few
  5m-ATRs wide instead of half a daily range.
- *Break buffer (× ATR)* — 0.15 of the row's own ATR, both for the break and
  for the failed break.
- *Min break buffer (% of level)* — 0.012 %, about $0.50 on gold, so a close
  inside the spread never counts as a break when ATR collapses in thin
  sessions.
- *Retest band % / Break buffer % (Percent mode)* — 0.15 % / 0.045 %. A fixed
  percent cannot fit every timeframe; use ATR mode unless you need the v5
  width.
- *Expire level N bars after confirmation* — 0 = never. Removes a level that
  has been on the table for N bars of its own timeframe.

**Timeframes.** Toggle rows. Hidden rows cost nothing.

**Display.** Marks, table, labels, level lines, bias tint, label size, table
text size, table position and colours.

## 9. Calibration for XAUUSD and BTCUSD

Reference volatility on 2 October 2026: gold ≈ $4,170 with a daily ATR of about
$50–90, bitcoin ≈ $77,000 with a daily ATR of about 3.3 %. Intraday ATR scales
roughly with the square root of the bar length, which gives these default
bands on the Chart row:

| TF | Gold ATR | Gold retest ±0.5 ATR | Gold break buffer | BTC ATR | BTC retest ±0.5 ATR | BTC break buffer |
|----|---------|----------------------|-------------------|---------|---------------------|------------------|
| 5s | ≈ $0.9 | ±$0.45 | $0.50 (floor) | ≈ $35 | ±$17 | $9 (floor) |
| 1m | ≈ $2 | ±$1 | $0.50 (floor) | ≈ $70 | ±$35 | $11 |
| 5m | ≈ $4 | ±$2 | $0.6 | ≈ $150 | ±$75 | $23 |
| 15m | ≈ $6 | ±$3 | $0.9 | ≈ $260 | ±$130 | $39 |
| 1H | ≈ $13 | ±$6.5 | $2 | ≈ $520 | ±$260 | $78 |
| 4H | ≈ $26 | ±$13 | $4 | ≈ $1,040 | ±$520 | $156 |
| D | ≈ $63 | ±$32 | $9.5 | ≈ $2,540 | ±$1,270 | $380 |
| W | ≈ $140 | ±$70 | $21 | ≈ $6,700 | ±$3,350 | $1,000 |

Once everything is expressed in ATR, the two markets need the same multipliers.
What differs is handled by the profile: gold's daily halt and weekend gap (the
rollover filter) and the price format. On seconds charts of gold the spread is
larger than the ATR-based buffer, which is why the 0.012 % floor exists.

Suggested setups:

- **Scalping gold or BTC on 5s–1m**: keep all rows on; the 1m, 5m and 15m rows
  give the levels that matter, the 1H and 4H rows give context. Expect D and W
  rows to show "only N bars" until history fills.
- **Intraday on 5m–15m**: the default. The 1H and 4H rows are the structure,
  the D and W rows the big levels.
- **Swing trading on 1H–4H**: D and W rows carry the weight; consider enabling
  the higher-TF level lines.

## 10. Questions

**Why does a row say "= chart" or "< chart"?** A row at or below the chart
timeframe cannot be computed reliably from chart bars, so it is hidden. Switch
to a lower chart timeframe to see it, or read the Chart row.

**Why does the Chart row show Holding when price is sitting on the level?**
Retest requires price to have left the band at least once since the fractal
printed. Right after confirmation price is usually still near the swing, which
is not a retest.

**Why did a daily level not turn Broken when price went through it today?**
Breaks on higher-timeframe rows are judged on that timeframe's close. The row
reads Retest while the test is in progress and Broken once the daily bar has
closed beyond the level plus buffer.

**Why did the level jump?** A new fractal confirmed on that timeframe. The
table always tracks the most recent swing of each side.

**Does it repaint?** Higher-timeframe rows use completed bars only and are
identical on history and live. The Chart row waits for the bar close when
"Chart-TF signals on bar close only" is on. Retest and Flip retest follow the
live bar range, so they can appear during a bar but cannot vanish.
