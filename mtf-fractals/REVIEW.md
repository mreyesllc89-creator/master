# MTF Fractals + Stage — review, v6 migration and XAUUSD / BTCUSD calibration

Files:

- `mtf_fractals_stage_v6.pine` — the Pine Script v6 rewrite (paste into the Pine Editor).
- `GUIDE.md` — how to read the table, the six stages, the bias, the alerts and every setting.
- `original_v5.pine` — the script as received, kept for reference.

No Pine compiler exists outside TradingView, so the v6 script was checked by three
rounds of independent review (two compile-rule readers, a bar-by-bar logic tracer,
a repaint checker, a calibration checker, a runtime-limits checker and a
diff-against-original reader, every finding challenged by two adversarial
verifiers) rather than compiled. If the Pine Editor reports anything on first
paste, send the message and the line number.

## 1. What was wrong with the v5 script

Confirmed findings, most serious first. Each is fixed in the v6 file unless the
Status column says otherwise.

| # | Severity | Finding | Status |
|---|----------|---------|--------|
| 1 | critical | `biasScore` has the sign inverted. It adds +1 while the swing **high** is intact and −1 while the swing **low** is intact, so a timeframe that just broke out above resistance scores −1 (bearish) and a breakdown scores +1. | Fixed: +1 per TF whose last swing high is Broken / Flip retest, −1 per broken swing low, 0 otherwise. |
| 2 | high | Higher-TF rows repaint. `request.security(..., tfEngine(), lookahead_off)` evaluates the fractal engine on the **forming** HTF bar in real time but on the **completed** bar in history, so levels, "Confirmed" and the bias differ after a reload. | Fixed: every HTF value is taken from the previous completed bar (`[1]` offset inside the engine + `lookahead_on`), the documented non-repainting pattern. |
| 3 | high | Rows whose TF is lower than the chart TF (5m / 15m on a 1H or D chart) are single-intrabar samples with truncated history, and they carry equal weight in the bias. | Fixed: such rows are hidden and excluded; the Σ row tooltip lists them. |
| 4 | high | The Chart row duplicates a fixed row when the chart is on 5 / 15 / 60 / 240 / D / W and is counted twice in the bias. | Fixed: a fixed row equal to the chart TF is always hidden (through `request.security` it would only be the Chart row one bar late). |
| 5 | high | "Broken" is stateless: one close through the level flips the stage, and it flips back to Holding / Retest as soon as price returns inside. With a zero buffer, one tick (0.001 on OANDA gold, $1 on Bitstamp) is enough. | Fixed: break buffer (0.15 × ATR with a spread floor) plus a latched break state judged on each TF's own close, with Flip retest and Failed break outcomes. The stateless mode was dropped rather than kept as an option, because it could never be made consistent with the non-repainting HTF rows. |
| 6 | high | The retest band is a fixed 0.15 % of price on every timeframe and both symbols. It is about 0.5 × ATR on 1H gold, ~1 × ATR on 15m gold, 0.1 × ATR on daily gold and under 0.5 × ATR on every BTC timeframe above 5m. | Fixed: bands are ATR multiples; the % band survives as "Percent" mode. |
| 7 | high | Alerts: only chart-TF confirmation alerts exist, and they fire on the first intrabar tick that satisfies the fractal test, then roll back. | Fixed: the Chart row confirms fractals, updates its level and stage and fires its fractal and break alerts only on the bar close (input, default on); break and retest alerts were added for the chart TF and for higher TFs. |
| 8 | medium | Equal highs or lows on either side disqualify a fractal, so a double top or bottom with a tied extreme (round numbers on gold, $1 ticks on Bitstamp BTC) never produces a level. | Fixed: ties are allowed on the left (older) side, strict on the right, as in the built-in Williams Fractal. Input to restore the strict rule. |
| 9 | medium | Retest is judged on the close only: a wick that tags the level and closes away, the textbook retest, never registers. | Fixed: a bar counts as near the level when its range reaches into the band. |
| 10 | medium | "Confirmed" on an HTF row is only visible while the fractal is provisional and disappears when it is actually confirmed. | Fixed by the non-repainting change: Confirmed shows for the HTF bar after the confirming bar closed (Retest wins if the chart bar is back in the band). |
| 11 | medium | On the first `leftBars + rightBars` bars every bar is a fractal because comparisons against `na` are false. | Fixed: bar-index guard. |
| 12 | medium | D / W rows on low chart timeframes may have too few HTF bars to ever form a fractal and silently show "—". | Fixed: the row says "only N bars" when the context is too short. |
| 13 | low | `upAge` / `dnAge` are computed and never used; `upPxNow` / `dnPxNow` are redundant. | Fixed: ages drive level lines, tooltips and expiry. |
| 14 | low | `format.mintick` prints meaningless precision (0.01 at $80k BTC, 0.001 on OANDA gold). | Fixed: gold 2 decimals, BTC whole dollars, other symbols mintick. |
| 15 | low | No level lines, no bias in the table, bias only in the Data Window. | Fixed: chart-TF level lines, optional HTF lines, bias column, Σ row, optional background tint. |
| 16 | low | Table is allocated 5×9 but at most 8 rows are painted; labels are deleted and recreated every tick. | Harmless, left as is (table now 6×10, labels unchanged). |

Findings reviewed and deliberately **not** changed:

- The engine tracks the **most recent** fractal of each side, not the most
  significant unbroken one, so in a downtrend the active resistance is the latest
  lower high. That is the v5 semantics and the more actionable level for breakout
  trading; a "structural level" mode is a possible extension.
- All six `request.security` calls still run even when a row is disabled or
  hidden (v6 dynamic requests would allow skipping them, but tuple destructuring
  inside an `if` block is block-scoped, so each gated request needs a dozen extra
  lines). Instead, a disabled or hidden row's request is pointed at the weekly
  series, so a D chart no longer loads and processes the full 5m / 15m / 1H
  history only to discard it.
- Heikin Ashi / Renko / Kagi charts feed synthetic OHLC into the fractal engine.
  Use a standard candle chart with this script.
- Daily and 4H bars are anchored differently across gold feeds (17:00 ET on OANDA /
  FOREXCOM / FXCM, 18:00 ET on COMEX GC, 00:00 UTC on BTC exchanges). Calibrate
  on the feed you execute on; levels are not transferable between feeds.

## 2. v6 migration

The original compiles under v6 after changing the version tag; nothing in it uses
a construct v6 removed (no `na` booleans, no implicit numeric-to-bool casts, no
removed built-ins). Two v6 behaviour changes matter for the rewrite:

- `and` / `or` short-circuit in v6. A function that reads its parameter's history
  (`st[1]`) must be called on every bar, so every alert helper is evaluated at
  global scope and only the resulting booleans are combined.
- `bool` values can no longer be `na`. Bool history on bar 0 reads `false`, which
  the stage machine relies on.

v6 features adopted: `switch` for stage names / colours / table position, a
user-defined `Row` type with a `for … in` loop for the table and bias, `simple`
parameter qualifiers, named `gaps` / `lookahead` arguments and `tooltip` /
`inline` on inputs.

## 3. Calibration for XAUUSD and BTCUSD

### Volatility reference (2 Oct 2026)

| | XAUUSD | BTCUSD |
|---|---|---|
| Price | ≈ $4,170 | ≈ $77,000 |
| Daily ATR(14) | ≈ $50–90 (1.2–2.1 %) | ≈ $2,500 (3.3 %) |

Intraday ATR scales roughly with the square root of the bar length. Expected ATR
per timeframe, and the defaults that follow from it:

| TF | Gold ATR | Gold break buffer 0.15 ATR | BTC ATR | BTC break buffer 0.15 ATR | v5 fixed 0.15 % |
|----|---------|---------------------------|---------|---------------------------|-----------------|
| 5m | ≈ $4 (0.09 %) | $0.6 (floor $0.50) | ≈ $150 (0.19 %) | $23 | gold $6 / BTC $115 on every TF |
| 15m | ≈ $6 (0.15 %) | $0.9 | ≈ $260 (0.34 %) | $39 | |
| 1H | ≈ $13 (0.31 %) | $2 | ≈ $520 (0.67 %) | $78 | |
| 4H | ≈ $26 (0.6 %) | $4 | ≈ $1,040 (1.35 %) | $156 | |
| D | ≈ $63 (1.5 %) | $9.5 | ≈ $2,540 (3.3 %) | $380 | |
| W | ≈ $140 (3.4 %) | $21 | ≈ $6,700 (8.7 %) | $1,000 | |

Retest band = 0.5 × √(row ATR × chart ATR), never narrower than the row's break
buffer. On the Chart row that is 0.5 × ATR (±$6.5 on 1H gold, the same as the
v5 band there; ±$260 on 1H BTC). Seen from a 5m chart, the D row's band is
±0.5 × √(63 × 4) ≈ ±$8 on gold (its buffer, $9.5, is the floor) instead of
±$32, so "Retest" means price actually came to the daily level rather than
being anywhere within half a daily range of it.

The v5 band of 0.15 % was only right for gold on 1H (and roughly BTC on 15m); on
daily gold it was a tenth of what a retest needs, on BTC it was too tight on every
timeframe above 5m.

### Parameter decisions

| Parameter | Default | Why |
|-----------|---------|-----|
| Fractal left / right | 2 / 2 | Classic Williams. A wider left side for BTC was considered and rejected: it removes ~17 % of fractals without reducing lag, and the ATR band already normalises BTC's larger noise. Ties allowed on the left so equal-high double tops register. |
| ATR length | 14 | Standard; seeded with an expanding mean so the first 13 bars of each context are classified too. |
| Retest band | ±0.50 × √(row ATR × chart ATR), floored at the break buffer | A normal pullback reaches the level; half an ATR keeps Retest from showing on every bar near it. Geometric mean with the chart ATR keeps D / W bands readable on intraday charts; the floor keeps a level price is sitting on from reading Holding. |
| Break buffer | 0.15 × row ATR, floor 0.012 % of the level | Gold: above one CFD spread even on 5m, and the floor (≈ $0.50) holds when the 5m ATR collapses in the 21:00–23:00 UTC lull. BTC: filters marginal closes in a fat-tailed market; the floor (≈ $9) is irrelevant next to its ATR buffer. On D it is $9.5 / $380, far below a real breakout close, so no real break is delayed. |
| Rollover filter | XAUUSD profile only | Gold CFDs and COMEX halt 17:00–18:00 ET; the thin bars around the halt and the Sunday open print isolated extremes that are not tradable levels. Fractals whose centre bar opens 16:40–18:20 New York time on timeframes up to 1H are ignored. BTC trades continuously. |
| Price format | gold 2 decimals, BTC whole dollars | Readability. |
| Rows | 5s, 10s, 15s, 30s, 1m, 5m, 15m, 1H, 4H, D, W, all on | A row is shown only when it is higher than the chart timeframe and a whole multiple of it, so on a 1s chart every row is available and the Chart row is the 1s row; on a 5m chart the rows are 15m and up. Hidden rows cost nothing: their request is redirected to the weekly series. |
| Percent mode | 0.15 % retest, 0.045 % buffer | The v5 band width with a buffer in the same 3 : 10 ratio as the ATR defaults. Only the width is v5's: the retest and break logic is the same as in ATR mode. Set the buffer to 0 for any close through the level to count. |

After ATR normalisation the two instruments need the same multipliers, so every
calibration input applies to every symbol. The symbol profile ("Auto" resolves it
from the symbol: XAU / GOLD / GC / MGC futures → XAUUSD; BTC / XBT / BTC / MBT
futures → BTCUSD; equities and funds such as GLD or IBIT, and CRYPTOCAP:BTC.D,
are excluded) sets only what genuinely differs: the rollover filter and the
price format.

## 4. Behaviour that changed on purpose

- **Bias sign** is the opposite of v5 (finding 1). Re-create any alert or script
  built on the old "MTF fractal bias" plot.
- **Break state is latched** and judged on each timeframe's own close: a break
  fires one alert and keeps the row in Broken / Flip retest until that
  timeframe closes back through the level by the buffer (Failed break) or the
  next fractal of that side prints; a re-break fires the alert again. A daily
  level reads "Retest" while price tests it intraday and "Broken" once the
  daily bar has closed beyond it. With "Chart-TF signals on bar close only" on,
  the Chart row's level and break state also wait for the bar close.
- **Retest requires a departure first**: a level shows Holding until a chart bar
  has been entirely outside the band once, so the bar after confirmation does not
  immediately read Retest.
- **Confirmed on HTF rows** appears for the HTF bar after confirmation instead of
  flickering while provisional.
- Rows that are lower than the chart TF, equal to it, or not a whole multiple of
  it (2m chart with the 5m and 15m rows, 45m with 1H and 4H, 3H with 4H) are
  hidden. Standard chart timeframes from 1m to D keep every row above them.
- **Equal highs on the left side** now produce a fractal (input `tieLeft`, default
  on); the v5 strict rule is one click away. The rule is looser than the built-in
  Williams Fractal, which caps the plateau at 4 bars.
- **Gold rollover filter** is on for the XAUUSD profile on venues that halt
  (tokenised gold on crypto exchanges is excluded); the Σ row says
  "rollover filter" when it is active.
- **Rows** now run from 5s to W and are all on by default; rows at or below the
  chart timeframe are hidden rather than shown. Weekly is on (the only
  higher-TF row a D chart can show).
- **Labels** show two lines (price, then stage and age) with a tooltip that
  explains the stage; label size, table text size and fractal-mark size are
  inputs (large labels and marks by default). Every table cell has a tooltip.

## 5. Known limits

- Non-repainting is guaranteed for row timeframes that are whole multiples of the
  chart timeframe; other rows are hidden rather than shown with a caveat.
- Tick-based charts (`100T`) have no time length, so all higher-TF rows are hidden
  there and the rollover filter is skipped.
- Seconds rows need a TradingView plan with seconds charts. They are only
  requested when the chart itself is a lower seconds timeframe, so on plans
  without seconds data they are never requested.
- Higher-TF contexts only cover the chart's own history, so on a 1m chart the W
  row may never have enough bars for a fractal. The row says "only N bars".
- Higher-TF ages and levels are as of that timeframe's last completed bar; the
  tooltip says so.
- The calibration numbers are starting points grounded in current volatility, not
  the output of a backtest. The Σ row shows the active profile and multipliers,
  and the level tooltips show the band and buffer in price units so you can judge
  them on your feed.
