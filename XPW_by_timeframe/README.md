# XPW Orientation TDI v2.8 (trailing TP): results by timeframe

File tested: [`xpw_orientation_tdi_v2.8_strategy_trailtp_FGF.pine`](https://github.com/mreyesllc89-creator/master/blob/claude/exciting-tesla-xk8lqw/xpw_orientation_tdi_v2.8_strategy_trailtp_FGF.pine). With "Enable filter" off it trades exactly like your pasted v2.8 (`xpw_orientation_tdi_v2.8_strategy_trailtp.pine`). With it on, it uses the FlashGold Direction Filter defaults. Every other input is at the file's defaults: trailing TP on, $2.0 activation, $1.0 offset (price units), no stop loss, 10% of equity per entry, up to 20 open entries.

## How it was tested

- **Replica.** A Python replica of the script, built independently twice for each part (the filter, the XPW ladder and labels, the orders and TradingView's broker), then compared trade by trade and audited line by line against the Pine. The two builds agree on every trade. The audit found no code defects.
- **Fills.** Same rules as TradingView's Strategy Tester without Bar Magnifier. Signals fill at the close of the label's candle. Inside a candle, TradingView assumes price goes open → high → low → close when the high is nearer the open, otherwise open → low → high → close.
- **BTCUSD.** Bitstamp 1-minute data, 2024-11-17 to 2026-11-17 (2 years, average price about $89,000).
- **XAUUSD.** Dukascopy 1-minute data, 2017-01-02 to 2018-06-19 (gold near $1,280). This is the most recent gold history available here.
- **Money.** $10,000 start. Each entry is 10% of equity, compounding.
- **Costs** (the bold columns): gold $0.30 per ounce per round trip; BTC 0.02% per side plus $0.20 per round trip. TradingView shows the "no costs" figure, because the script's properties have commission 0 and slippage 0.
- **Control column.** "Labels reversed" is the script with "Reverse every label" on (every buy becomes a sell and vice versa). If the reversed script makes about the same money, the profit does not come from the signals.

## Results

### BTCUSD (2024-11 to 2026-11)

| TF | Filter off: trades | no costs | with costs | win % | PF (costs) | Filter on: trades | no costs | with costs | win % | PF (costs) | Labels reversed, filter off, with costs |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1m | 63,358 | +249.0% | **-72.7%** | 88 | 0.45 | 22,169 | +49.9% | **-38.6%** | 88 | 0.42 | -73.7% |
| 5m | 23,789 | +288.0% | **+49.0%** | 94 | 1.55 | 8,831 | +59.5% | **+11.8%** | 93 | 1.37 | +39.9% |
| 15m | 11,644 | +261.7% | **+126.4%** | 97 | 3.62 | 4,728 | +66.0% | **+37.2%** | 97 | 3.32 | +124.3% |
| 30m | 6,945 | +196.9% | **+124.5%** | 98 | 5.02 | 2,943 | +58.7% | **+41.0%** | 98 | 4.62 | +130.5% |
| 1h | 3,886 | +143.7% | **+108.4%** | 98 | 6.96 | 1,807 | +50.6% | **+40.0%** | 98 | 5.17 | +126.1% |
| 2h | 1,826 | +87.0% | **+73.8%** | 99 | 9.17 | 849 | +33.5% | **+29.0%** | 99 | 7.00 | +78.1% |
| 4h | 1,094 | +69.1% | **+61.8%** | 99 | 14.01 | 486 | +25.7% | **+23.3%** | 99 | 12.75 | +72.3% |

**These BTC profits are not real, and TradingView will show them too.**

- **Why.** On BTC the default trail ($2 activation, $1 offset) is about 0.002% of the price. A typical 1-minute BTC candle moves about $30 (0.034%), so the trail is about 15-30 times smaller than one candle.
- **What the backtest does with it.** With a trail that small, the backtest exit is decided by the assumed path inside the next candle. That candle almost always rises $2 above a long's entry at some point, so the trail arms. The assumed path then has price fall back, so the long exits $1 under the candle's high. Shorts mirror this and exit $1 above the low.
- **What that produces.**
  - Win rates of 94-99% and profit factors up to 14.
  - The reversed labels make the same money, or more.
  - The 1m chart only loses because its costs are larger.
- **What happens live.** Price moves $1 in a fraction of a second, so the trail is hit almost as soon as it arms. That leaves at most about $1 per trade, which is less than the spread.

### XAUUSD (2017-01 to 2018-06)

| TF | Filter off: trades | no costs | with costs | win % | PF (costs) | Filter on: trades | no costs | with costs | win % | PF (costs) | Labels reversed, filter off, with costs |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1m | 29,828 | +2.6% | **-49.1%** | 51 | 0.48 | 10,795 | +0.4% | **-22.1%** | 50 | 0.46 | -49.3% |
| 5m | 11,022 | +0.9% | **-22.1%** | 56 | 0.65 | 4,268 | +1.0% | **-8.6%** | 56 | 0.66 | -18.8% |
| 15m | 5,395 | +2.0% | **-10.1%** | 62 | 0.77 | 2,213 | +2.4% | **-2.8%** | 63 | 0.84 | -10.6% |
| 30m | 3,117 | +4.3% | **-3.1%** | 67 | 0.90 | 1,312 | +1.7% | **-1.4%** | 68 | 0.90 | -4.8% |
| 1h | 1,772 | -0.1% | **-4.2%** | 73 | 0.83 | 811 | -1.5% | **-3.4%** | 73 | 0.75 | +2.9% |
| 2h | 855 | +7.1% | **+5.0%** | 84 | 1.49 | 398 | +2.5% | **+1.6%** | 82 | 1.31 | +3.1% |
| 4h | 544 | +4.0% | **+2.6%** | 84 | 1.31 | 247 | +1.6% | **+1.0%** | 81 | 1.24 | +3.1% |

On gold near $1,280, $2 / $1 is 0.16% / 0.08% of the price, a sensible size.

- **1m to 1h.** About break-even before costs, and costs make every one of these timeframes lose.
- **2h and 4h.** Small gains of +5.0% and +2.6% over 18 months. The reversed labels make about the same, so this is not a signal edge either.

### Filter on vs off

The filter removes 53-65% of the entries on both pairs.

- **Where the strategy makes money,** it cuts the profit by at least as much as the trades: BTC 15m goes from +126% to +37%, and gold 2h from +5.0% to +1.6%.
- **Where the strategy loses to costs** (BTC 1m, gold 1m-30m), it loses less, only because it trades less.
- **Overall,** it does not turn any timeframe from losing to winning. This matches the October finding on the S2/S3 version.

## Limits of this test

- **Margin.** Margin calls are not modelled. On gold the default stacks up to 20 open entries, about 2x equity. TradingView, whose v6 default margin is 100%, would cut some of those positions.
- **Lower-timeframe history.** The script reads the 1m and 5m ladder rungs on higher charts. TradingView may only serve the most recent part of that lower-timeframe history. Here it is complete, so very old windows on TradingView can show fewer "<<" entries.
- **FIFO pairing.** TradingView's default FIFO rule can pair a trail exit with an older open entry in its List of Trades. Totals are unaffected; per-trade win rate and PF can differ.
- **Gold data age.** The gold data is from 2017-2018. Gold now trades at several times that price, so fixed dollar distances behave differently today. Distances in percent carry over.

## Every trailing setting on every timeframe

**What was swept.** For each pair, timeframe (1m to 4h) and filter setting (off / on):

- trail activation 0, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1, 1.5, 2, 3 and 5% of the entry price;
- trail offset 0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1, 1.5, 2, 3 and 5%;
- stop loss off, or 0.1, 0.25, 0.5, 1, 2 and 4%;
- plus trailing TP off, and your default ($2 / $1).

That is 1,380 settings per cell. Each one was run four ways:

- **Fills:** TradingView's standard backtest, and with exits checked on the 1-minute candles inside each chart candle. The second is what TradingView's Bar Magnifier does and is much closer to live trading.
- **Labels:** as the script gives them, and with every label reversed (the control).

In total 154,560 backtests. Everything below uses 1-minute fills and costs unless it says otherwise. The full grid is in [`trailing_sweep_all.csv.gz`](trailing_sweep_all.csv.gz).

### What it shows

1. **TradingView's standard backtest ranks the tiniest trail first on every timeframe** (activation 0.02%, offset 0.01%) and shows it making +30% to +300%. On 1-minute data with costs, every one of those settings loses. The reason is the same as for your $2 / $1 default above. Don't trust a TradingView result whose trail offset is smaller than a few 1-minute candles. Turn on Bar Magnifier, or use a wider trail.
2. **1m to 1h: no trailing setting makes money after costs** on either pair. The few exceptions (BTC 30m and gold 30m with the filter on) make at most +4.4%, and only with an offset under the 1-minute noise or with positions stacked above 1x equity.
3. **2h and 4h are the only timeframes with a profitable area.**
   - On BTC it is wide trails: activation 3-5% and offset 1-3%. Those hardly ever trigger, so the signals and the filter do the exiting.
   - On gold it is offsets of 0.75% or more.
   - Most of these settings stack open entries above 1x equity, up to 2x. TradingView's default margin of 100% would liquidate part of those positions.
4. **No trailing setting is worth adopting on any timeframe.** Two settings passed the hold-out test (rule below), but a review then refuted both, so neither gets a file (see "Review of the two picks").
   - **BTCUSD 2h, filter on.** The best setting is effectively no trailing take profit at all. With the trail off it makes +18.6% instead of +15.7% for the pick (3% / 1%), and the whole edge is fragile.
   - **XAUUSD 4h.** Nothing usable.
5. **The filter.** On BTC 2h, the filter's closes on blocked opposite signals carry the result: without them +10.2%, and with the filter off +8.6% with a 30% drawdown. Elsewhere it changes how much you lose, not whether you lose.

### By timeframe

"Settings that make money" is the share of the 1,380 settings with a positive result. "Needs over 1x margin" means open entries go above 1x equity at some point.

#### BTCUSD

| TF | Filter | Settings that make money | Best setting (activation / offset) | Needs over 1x margin | TradingView's top setting: TradingView shows / 1-minute data | Your default ($2/$1): TradingView / 1-minute data | Hold-out verdict |
|---|---|---|---|---|---|---|---|
| 1m | off | 0% | 0.02% / 0.01%, SL 0.1%: -71.5% | no | +264.8% / -71.5% | +249.0% / -72.7% | no file |
| 1m | on | 0% | 0.02% / 0.01%, SL 0.1%: -37.2% | no | +53.2% / -37.2% | +49.9% / -38.6% | no file |
| 5m | off | 0% | 0.15% / 0.01%: -29.0% | yes (1.7x) | +299.8% / -29.5% | +288.0% / -33.5% | no file |
| 5m | on | 0% | 0.02% / 0.01%, SL 0.5%: -15.2% | no | +60.7% / -15.6% | +59.5% / -17.3% | no file |
| 15m | off | 0% | 0.3% / 0.01%: -5.0% | yes (2.0x) | +293.5% / -11.8% | +261.7% / -14.6% | no file |
| 15m | on | 0% | 0.1% / 0.01%, SL 0.5%: -6.0% | no | +71.7% / -6.5% | +66.0% / -7.8% | no file |
| 30m | off | 0% | 0.1% / 0.01%, SL 1%: -5.5% | yes (1.1x) | +231.2% / -9.4% | +196.9% / -10.4% | no file |
| 30m | on | 18% | 0.5% / 0.01%: +4.4% | yes (1.6x) | +70.3% / -2.8% | +58.7% / -5.6% | no file |
| 1h | off | 0% | 0.02% / 0.01%, SL 2%: -4.2% | no | +181.9% / -4.2% | +143.7% / -6.6% | no file |
| 1h | on | 0% | 0.3% / 0.01%, SL 2%: -1.6% | no | +61.1% / -4.3% | +50.6% / -5.5% | no file |
| 2h | off | 7% | 5% / 3%: +23.3% | yes (2.0x) | +105.0% / -3.6% | +87.0% / -4.0% | no file (every profitable setting needs over 1x margin) |
| 2h | on | 18% | 5% / 3%: +24.4% | yes (1.2x) | +39.9% / -1.4% | +33.5% / -3.0% | passed (3% / 1%, no SL, +15.7%), **withdrawn after review**: the trail costs money here (trail off +18.6%), and the edge is fragile |
| 4h | off | 3% | 5% / 1.5%: +12.9% | yes (2.0x) | +85.2% / -2.1% | +69.1% / -2.5% | no file (every profitable setting needs over 1x margin) |
| 4h | on | 11% | 5% / 3%: +12.9% | yes (1.2x) | +31.8% / -0.9% | +25.7% / -1.2% | no file (pick 2% / 2%, +3.8%: reversed labels do as well; forward hold-out fails) |

#### XAUUSD

| TF | Filter | Settings that make money | Best setting (activation / offset) | Needs over 1x margin | TradingView's top setting: TradingView shows / 1-minute data | Your default ($2/$1): TradingView / 1-minute data | Hold-out verdict |
|---|---|---|---|---|---|---|---|
| 1m | off | 0% | 0.02% / 0.01%: -43.9% | no | +13.0% / -43.9% | +2.6% / -49.1% | no file |
| 1m | on | 0% | 0% / 0.01%: -19.3% | no | +4.0% / -19.3% | +0.4% / -22.1% | no file |
| 5m | off | 0% | 0.05% / 0.01%: -18.0% | yes (1.1x) | +15.8% / -18.6% | +0.9% / -23.4% | no file |
| 5m | on | 0% | 0.1% / 0.01%, SL 0.25%: -6.6% | no | +6.4% / -7.2% | +1.0% / -9.2% | no file |
| 15m | off | 0% | 0.3% / 0.01%, SL 1%: -6.8% | yes (2.0x) | +17.7% / -9.2% | +2.0% / -12.9% | no file |
| 15m | on | 0% | 1% / 0.01%, SL 1%: -0.3% | yes (1.3x) | +7.9% / -3.0% | +2.4% / -4.4% | no file |
| 30m | off | 0% | 0.3% / 0.01%, SL 1%: -1.3% | yes (1.6x) | +15.7% / -4.9% | +4.3% / -6.9% | no file |
| 30m | on | 37% | 1% / 0.01%, SL 1%: +1.2% | yes (1.4x) | +6.7% / -1.9% | +1.7% / -2.9% | no file |
| 1h | off | 0% | 0.05% / 0.01%, SL 1%: -2.1% | no | +13.9% / -2.9% | -0.1% / -8.8% | no file |
| 1h | on | 0% | 0.05% / 0.01%, SL 1%: -0.5% | no | +7.1% / -0.8% | -1.5% / -5.5% | no file |
| 2h | off | 55% | 0.75% / 1.5%: +8.7% | yes (2.0x) | +14.6% / +6.7% | +7.1% / +0.2% | no file (within 1x margin, only isolated settings are positive in both halves: no plateau) |
| 2h | on | 64% | 0.75% / 1.5%: +3.1% | yes (1.3x) | +6.0% / +2.4% | +2.5% / -0.3% | no file (pick 0.5% / 0.75%, SL 0.5%, +2.2%: both hold-outs fail) |
| 4h | off | 60% | 0.02% / 1.5%, SL 2%: +5.5% | yes (1.2x) | +10.8% / +0.0% | +4.0% / -1.9% | passed (0.75% / 0.05%, SL 0.5%, +1.65%), **withdrawn after review**: not significant, carried by 2018 |
| 4h | on | 48% | 0.75% / 1.5%, SL 2%: +1.7% | no | +4.8% / +0.1% | +1.6% / -1.1% | no file (pick 0.75% / 0.05%, SL 0.5%, +1.1%: both hold-outs fail) |

The gold percentages carry over to today's prices; dollar distances do not. At gold near $4,000, for example, 0.75% is $30.

### Heatmaps

Each panel shows activation (up) against offset (across), coloured by net % with costs on 1-minute data. Hatched cells have an offset under the 1-minute noise; a dot means open entries went above 1x equity; the box is the pick.

![BTCUSD heatmaps](img/trail_heatmaps_BTC.png)

![XAUUSD heatmaps](img/trail_heatmaps_XAU.png)

What TradingView shows against 1-minute data, and the signal edge (normal minus reversed labels), on the 1h chart with the filter off:

![BTCUSD 1h: TradingView vs 1-minute data](img/tv_vs_1m_BTC_60.png)

![XAUUSD 1h: TradingView vs 1-minute data](img/tv_vs_1m_XAU_60.png)

On 1h, reversing every label does better than the labels themselves, for almost every trailing setting on both pairs.

### The rule (rule T)

The same rule was applied to every pair, timeframe and filter setting.

- **Pool.**
  - Offsets of at least twice the median 1-minute candle range (BTC 0.1%, gold 0.05%). Below that, even 1-minute data decides the exit.
  - Open entries never above 1x equity.
  - Settings with identical results count once.
- **Pick.**
  - Candidates: settings positive in both halves of the window, with 30+ trades in each half. Each half is scored from a fresh $10,000.
  - Take the 40 best by their worse half. Score each as 0.5 x its worse half + 0.5 x the mean worse half of its grid neighbours (at least 5 neighbours, positive mean).
  - The best score is the pick.
- **A file is published only if all of these pass:**
  1. **Forward.** The 40 best settings chosen on the first half beat 95% of random 40-setting draws on the second half, and are 60%+ positive there with a positive mean.
  2. **Reverse.** The 40 best chosen on the second half beat 95% of random draws on the first half.
  3. **Signal control.** The pick beats the same setting with every label reversed, in both halves.
  4. **Stressed costs.** It stays positive (BTC 0.035% per side + $0.20 + 1 tick per side; gold $0.50 + 1 tick per side).

### Review of the two picks

Two independent sceptics re-ran each pick with a separate 1-minute reference and reproduced every trade exactly. An auditor re-implemented the rule and got the same verdicts in all 28 cells. Both picks were refuted.

**BTCUSD 2h, filter on, activation 3%, offset 1%, no stop loss (+15.7%, PF 1.20)**

- **The trail does not help.** Trail off makes +18.6%, and is better in both halves. Capped at 10 open entries (the same exposure as the pick), trail off makes +20.6%.
  - The 144 trades the trail closed would each have made 0.24% more if held.
  - The grid is a ramp toward "never trail": activation 2% about +7%, 3% about +15%, 5% about +22%. The pick won only because it is the least-trailing setting that stays within 1x margin.
- **Where the profit does come from.** The signals and the filter's closes on blocked opposite signals. Without those closes: +10.2%. Filter off: +8.6% with a 30% drawdown.
- **That edge is fragile.**
  - Starting 1, 2 or 3 months later gives +13.8%, +6.9% and +2.8%.
  - Without the 10 best entry days: +0.7%.
  - Shorts make +13.6%; longs make +1.9%.
  - Trades entered from March 2025 to August 2026 lose money.
  - Statistically it is not distinguishable from zero (t = 1.24; 11% chance the true total is at or below 0).
- **What TradingView would show.** +24.2% without Bar Magnifier and costs. Its own top settings show +38-40% and all lose on 1-minute data.

**XAUUSD 4h, filter off, activation 0.75%, offset 0.05%, stop loss 0.5% (+1.65%, PF 1.12)**

- **Not significant.** t = 1.0-1.3; 16% chance the true total is at or below 0.
- **Concentrated.** 2018 carries +1.50 of the +1.65, and 2017 makes +0.14 in 12 months. Without the 10 best entry days it loses.
- **Thin against costs.** Break-even is 1.28x the cost; at 2x the cost it makes +0.36%.
- **It doesn't hold up.** Starting 2 or 3 months later, the first half turns negative. The trail adds only 0.48 points over trail off and acts like a fixed take profit near +0.75%.
- **It is borderline under the rule too.** It fails under several equally reasonable readings: a stricter random baseline, the reverse hold-out's own mean (-0.29%), or stressed costs required positive in each half.

**About the rule.** The hold-out tests measure whether a ranking of exits persists from one half to the other. They also pass on reversed labels in several cells, so only the label-reversal control tests the signals. The pick itself uses both halves, so its figures are in-sample: picking on the second half and scoring on the first loses money in both cells.

### Limits

- The windows are short: 2 years of BTC in a strong market, 18 months of gold in 2017-2018.
- On BTC 2h and 4h the best results come from wide or no trailing with fewer open entries: trail off capped at 10 open entries made +20.6% on BTC 2h. That variant was not put through the hold-out rule. It inherits the same fragility (dates, shorts, a few days).
- 1-minute fills still assume a path inside each 1-minute candle, so offsets near the noise floor remain slightly optimistic.

## Inverted direction (Update 1): results by timeframe

The file now has the option "Inverted direction: opposite side at the same entries" ([UPDATES.md](../UPDATES.md)). These are the results with it on, at the default inputs ($2.0 activation, $1.0 offset, no stop loss), next to the normal direction.

- **How it was tested.** The option was added to the backtest replica and checked trade by trade against a separately written reference, on every pair and timeframe, with the filter off and on and both fill models. With the option off, the replica reproduces every earlier result exactly.
- **"As TradingView shows"** is the standard backtest with the script's own costs (none). **"1-minute fills with our costs"** is the realistic figure: exits checked on the 1-minute candles, and gold $0.30 per ounce per round trip, BTC 0.02% per side + $0.20.
- **Filter off.** Inverted gives the same trades as "Reverse every label" (the "Labels reversed" control above). The new information is the filter-on rows.
- **Halves** are the trades entered in each half of the window, each half from a fresh start.

### BTCUSD

| TF | Filter | Trades normal / inverted | As TradingView shows: normal / inverted | 1-minute fills with our costs: normal / inverted | Inverted, both halves (1-minute fills, our costs) | PF inverted (same) |
|---|---|---|---|---|---|---|
| 1m | off | 63,358 / 63,358 | +248.97% / +236.32% | -72.73% / **-73.72%** | -52.12% / -45.10% | 0.43 |
| 1m | on | 22,169 / 22,169 | +49.92% / +51.36% | -38.56% / **-37.96%** | -22.70% / -19.74% | 0.42 |
| 5m | off | 23,789 / 23,789 | +288.04% / +264.29% | -33.46% / **-35.39%** | -21.45% / -17.74% | 0.50 |
| 5m | on | 8,831 / 8,831 | +59.52% / +65.32% | -17.26% / **-13.95%** | -7.76% / -6.71% | 0.50 |
| 15m | off | 11,644 / 11,644 | +261.72% / +258.35% | -14.62% / **-15.63%** | -10.22% / -6.02% | 0.58 |
| 15m | on | 4,728 / 4,728 | +65.98% / +69.43% | -7.78% / **-6.29%** | -4.19% / -2.19% | 0.58 |
| 30m | off | 6,945 / 6,945 | +196.86% / +204.84% | -10.36% / **-9.99%** | -6.86% / -3.36% | 0.58 |
| 30m | on | 2,943 / 2,943 | +58.67% / +59.02% | -5.57% / **-3.94%** | -2.34% / -1.64% | 0.61 |
| 1h | off | 3,886 / 3,886 | +143.66% / +164.30% | -6.62% / **-4.47%** | -2.35% / -2.17% | 0.64 |
| 1h | on | 1,807 / 1,807 | +50.61% / +57.79% | -5.45% / **-2.10%** | -1.27% / -0.84% | 0.65 |
| 2h | off | 1,826 / 1,826 | +87.01% / +91.64% | -3.95% / **-2.70%** | -1.95% / -0.77% | 0.58 |
| 2h | on | 849 / 849 | +33.48% / +36.05% | -3.02% / **-0.58%** | -0.34% / -0.24% | 0.74 |
| 4h | off | 1,094 / 1,094 | +69.11% / +80.03% | -2.51% / **+0.14%** | -0.07% / +0.21% | 1.07 |
| 4h | on | 486 / 486 | +25.73% / +29.49% | -1.16% / **-0.22%** | -0.16% / -0.06% | 0.81 |

### XAUUSD

| TF | Filter | Trades normal / inverted | As TradingView shows: normal / inverted | 1-minute fills with our costs: normal / inverted | Inverted, both halves (1-minute fills, our costs) | PF inverted (same) |
|---|---|---|---|---|---|---|
| 1m | off | 29,828 / 29,828 | +2.62% / +2.22% | -49.07% / **-49.27%** | -29.98% / -27.55% | 0.48 |
| 1m | on | 10,795 / 10,795 | +0.41% / +0.92% | -22.09% / **-21.69%** | -12.12% / -10.89% | 0.47 |
| 5m | off | 11,022 / 11,022 | +0.86% / +5.15% | -23.39% / **-19.82%** | -10.84% / -10.07% | 0.68 |
| 5m | on | 4,268 / 4,268 | +1.02% / +0.64% | -9.19% / **-9.44%** | -4.02% / -5.64% | 0.63 |
| 15m | off | 5,395 / 5,399 | +2.04% / +1.46% | -12.93% / **-13.01%** | -7.50% / -5.95% | 0.70 |
| 15m | on | 2,213 / 2,213 | +2.40% / -1.75% | -4.39% / **-7.58%** | -4.17% / -3.56% | 0.62 |
| 30m | off | 3,117 / 3,117 | +4.27% / +2.48% | -6.91% / **-8.45%** | -3.06% / -5.56% | 0.73 |
| 30m | on | 1,312 / 1,312 | +1.73% / -0.27% | -2.93% / **-4.72%** | -1.33% / -3.43% | 0.68 |
| 1h | off | 1,772 / 1,782 | -0.15% / +7.25% | -8.77% / **-2.38%** | +0.91% / -3.27% | 0.88 |
| 1h | on | 811 / 811 | -1.50% / +1.83% | -5.52% / **-2.55%** | -0.01% / -2.54% | 0.76 |
| 2h | off | 855 / 855 | +7.09% / +5.22% | +0.16% / **-1.95%** | -0.14% / -1.81% | 0.83 |
| 2h | on | 398 / 398 | +2.55% / +1.60% | -0.29% / **-1.46%** | -0.54% / -0.92% | 0.75 |
| 4h | off | 544 / 544 | +3.97% / +4.39% | -1.89% / **-1.57%** | -0.67% / -0.90% | 0.79 |
| 4h | on | 247 / 247 | +1.55% / +1.86% | -1.06% / **-0.49%** | -0.13% / -0.36% | 0.85 |

### What it shows

- **Inverted does not make the default trailing TP profitable.** With 1-minute fills and costs, both directions lose on every timeframe of both pairs. The two exceptions are within noise: BTC 4h inverted with the filter off (+0.14% over 2 years, first half -0.07%) and gold 2h normal with the filter off (+0.16%).
- **BTC: the TradingView figures are the same artifact in both directions.** Normal and inverted both show +25% to +290% without Bar Magnifier, because the $2 / $1 trail is far smaller than one candle (see "Results" above). With 1-minute fills the win rate falls from 88-99% to 30-43% and both directions lose.
- **BTC 30m to 4h: inverted loses less** (1h with the filter on: -5.45% normal, -2.10% inverted), but apart from the 4h case above it still loses in both halves.
- **Gold: no pattern.** Inverted is better on 1h and 4h, worse on 15m, 30m and 2h.
- **Trade counts** can differ by a few between normal and inverted. The entries are decided the same way, but the trailing exits fall on different candles, so the number of open entries is not always the same.

Nothing here was compiled or run in TradingView. These are the script defaults; the calibration with direction as an input is a separate run.

## Calibration by timeframe, with the direction as an input

Everything above used fixed inputs or swept the trailing only. Here the inputs were searched together, per pair and timeframe, with the Update 1 option "Inverted direction" as one of them: 381,024 backtests of the trailing-TP file.

### What was searched

27,216 settings on every timeframe from 1m to 4h of BTCUSD and XAUUSD, the full product of:

| | Values |
|---|---|
| Signals | "RSI length" 8, 13, 21; "Also trade / label the READ HERE rung" on, off; labels that trade: all, legs only (the two divergence rows off), divergences only (the four leg rows off) |
| Filter | off; on; on with "Blocked opposite signal still closes the trade" off |
| Direction | normal; inverted ("Reverse every label" stays off) |
| Exits, in percent of price | trailing off, or activation 0.2 / 0.5 / 1 / 2 / 4% with offset 0.1 / 0.3 / 1 / 3%; stop loss off, 0.5, 1.5, 4%; "Max open entries" 1, 5, 20 |

Every setting was scored on 1-minute fills with costs (gold $0.30 per ounce per round trip, BTC 0.02% per side + $0.20), 10% of equity per entry, on the two halves of the window separately. The file's own default trail ($2 / $1 in price units) is not on this grid; it is covered in the sections above.

### The rule

The same rule as for ApexForge and HRD ([how it works and what its audit found](../ApexForge_HRD_by_timeframe/README.md#the-rule-rule-c)), with one step added after that audit and before these results were looked at:

- **Chosen on one half, scored on the other.** The selection is repeated using the first half only, and the setting it picks must be profitable on the second half and beat its direction-flipped twin there. The same from the second half to the first.

A setting that passes everything would then go to independent reviewers. A pass is a reason to review a setting, never a reason to trade it.

### Results

How to read the table:

- **Different results**: settings with the same trades count once.
- **Positive in both halves**: how many of those are profitable in both halves with 30+ trades in each, per direction.
- **Typical result**: the median over settings with 30+ trades per half.
- **Best normal / inverted**: the setting with the best worst half, as net result (first half / second half, trades). In-sample: the best of thousands always looks good.
- **Hold-outs**: what the 40 best of one half made on the other half, against the 95th percentile of random draws.
- **Chosen on one half**: what the single setting picked on one half made on the other.

#### BTCUSD

| TF | Different results | Positive in both halves: normal / inverted | Typical result: normal / inverted | Best normal (halves, trades) | Best inverted (halves, trades) | Forward hold-out | Reverse hold-out | Chosen on one half, result on the other: first to second / second to first | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| 1m | 12,489 | 0 / 44 | -54.93% / -40.27% | -9.03% (-4.71% / -4.53%, 4260 trades) | +31.00% (+14.74% / +14.18%, 14678 trades) | -2.91% vs -25.80%, 28% positive: FAIL | -11.76% vs -26.55%, 12% positive: FAIL | -5.05% / -7.05% | no setting: none of the 40 best candidates sits on a plateau |
| 5m | 21,057 | 5 / 125 | -24.09% / -13.40% | +4.74% (+2.52% / +2.17%, 3171 trades) | +25.84% (+12.95% / +11.41%, 4362 trades) | -10.99% vs -9.45%, 10% positive: FAIL | -13.93% vs -9.87%, 0% positive: FAIL | -7.83% / -18.12% | no setting: none of the 40 best candidates sits on a plateau |
| 15m | 20,880 | 20 / 726 | -11.96% / -5.85% | +8.03% (+3.44% / +4.44%, 1487 trades) | +44.39% (+18.06% / +22.29%, 1911 trades) | +5.69% vs -3.62%, 57% positive: FAIL | +1.34% vs -4.14%, 52% positive: FAIL | -5.83% / -1.07% | no setting: forward hold-out failed; reverse hold-out failed; nested forward pick failed; nested reverse pick failed |
| 30m | 19,994 | 1,586 / 161 | -3.18% / -6.02% | +75.64% (+16.49% / +50.79%, 662 trades) | +34.43% (+12.76% / +19.22%, 903 trades) | -5.22% vs -1.01%, 55% positive: FAIL | -13.77% vs -1.18%, 2% positive: FAIL | +6.88% / -6.36% | no setting: forward hold-out failed; reverse hold-out failed; nested reverse pick failed |
| 1h | 18,253 | 307 / 1,567 | -4.44% / -0.68% | +46.83% (+12.32% / +30.72%, 2008 trades) | +15.66% (+7.71% / +7.38%, 782 trades) | -13.85% vs -0.49%, 5% positive: FAIL | -1.06% vs -0.48%, 45% positive: FAIL | -17.17% / -10.68% | no setting: forward hold-out failed; reverse hold-out failed; nested forward pick failed; nested reverse pick failed |
| 2h | 16,192 | 599 / 1,290 | -1.57% / -0.22% | +60.00% (+10.86% / +44.33%, 973 trades) | +11.67% (+5.77% / +5.58%, 1826 trades) | -17.50% vs +0.73%, 0% positive: FAIL | -7.05% vs +0.70%, 32% positive: FAIL | -55.83% / -18.39% | no setting: forward hold-out failed; reverse hold-out failed; nested forward pick failed; nested reverse pick failed |
| 4h | 15,350 | 796 / 1,465 | -1.15% / -0.07% | +40.76% (+16.32% / +21.01%, 452 trades) | +10.51% (+5.55% / +4.70%, 226 trades) | -20.03% vs +0.72%, 0% positive: FAIL | -7.37% vs +0.95%, 32% positive: FAIL | -55.83% / -18.39% | no setting: forward hold-out failed; reverse hold-out failed; nested forward pick failed; nested reverse pick failed |

#### XAUUSD

| TF | Different results | Positive in both halves: normal / inverted | Typical result: normal / inverted | Best normal (halves, trades) | Best inverted (halves, trades) | Forward hold-out | Reverse hold-out | Chosen on one half, result on the other: first to second / second to first | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| 1m | 3,605 | 10 / 0 | -15.51% / -17.80% | +0.83% (+0.25% / +0.58%, 7435 trades) | -1.07% (-0.49% / -0.58%, 1430 trades) | -7.80% vs -8.32%, 15% positive: FAIL | -1.38% vs -8.54%, 30% positive: FAIL | -10.56% / none | no setting: none of the 10 best candidates sits on a plateau |
| 5m | 7,660 | 49 / 0 | -5.87% / -6.67% | +5.67% (+1.75% / +3.85%, 2132 trades) | -0.44% (-0.18% / -0.27%, 670 trades) | -3.37% vs -3.01%, 0% positive: FAIL | -0.44% vs -2.85%, 50% positive: FAIL | -2.62% / -1.29% | no setting: none of the 40 best candidates sits on a plateau |
| 15m | 9,222 | 386 / 0 | -1.11% / -4.31% | +8.97% (+6.96% / +1.87%, 673 trades) | -0.84% (-0.45% / -0.39%, 389 trades) | -4.94% vs -1.08%, 0% positive: FAIL | -8.71% vs -1.00%, 0% positive: FAIL | -5.58% / -11.42% | no setting: forward hold-out failed; reverse hold-out failed; nested forward pick failed; nested reverse pick failed |
| 30m | 9,951 | 642 / 67 | -0.45% / -2.61% | +4.04% (+1.95% / +2.05%, 407 trades) | +2.37% (+1.68% / +0.69%, 1359 trades) | -0.76% vs -0.40%, 28% positive: FAIL | -5.10% vs -0.48%, 0% positive: FAIL | -0.21% / -4.85% | no setting: forward hold-out failed; reverse hold-out failed; nested forward pick failed; nested reverse pick failed |
| 1h | 13,061 | 504 / 1,343 | -1.44% / -0.32% | +3.87% (+2.29% / +1.54%, 184 trades) | +10.09% (+4.60% / +5.25%, 468 trades) | -3.35% vs -0.02%, 0% positive: FAIL | +3.04% vs +0.02%, 100% positive: pass | -4.81% / +2.06% | no setting: forward hold-out failed; nested forward pick failed |
| 2h | 13,101 | 473 / 351 | -0.57% / -0.49% | +7.22% (+3.27% / +3.82%, 831 trades) | +5.23% (+2.26% / +2.91%, 90 trades) | -2.51% vs +0.17%, 0% positive: FAIL | -0.54% vs +0.27%, 35% positive: FAIL | -2.86% / -0.24% | no setting: forward hold-out failed; reverse hold-out failed; nested forward pick failed; nested reverse pick failed |
| 4h | 13,452 | 509 / 353 | -0.29% / -0.55% | +3.19% (+1.60% / +1.56%, 559 trades) | +5.20% (+2.26% / +2.88%, 90 trades) | -1.14% vs +0.29%, 20% positive: FAIL | -1.62% vs +0.22%, 20% positive: FAIL | -1.62% / -0.24% | no setting: forward hold-out failed; reverse hold-out failed; nested forward pick failed; nested reverse pick failed |

### What it shows

- **No setting passes on any timeframe of either pair, in either direction.** On every one of the 14 cells, the 40 best settings of one half fail on the other half in at least one of the two tests, and usually in both.
- **The best settings look good only in-sample.** BTC 30m normal reaches +75.6% and BTC 15m inverted +44.4% over the two years, but the settings chosen on one half alone lose on the other half in 25 of the 27 cases where one could be chosen.
- **Closest to passing: gold 1h.** From the second half to the first it passes (the 40 best average +3.0%, all positive). From the first half to the second it fails completely (none of the 40 positive).
- **The direction is not an edge by itself.** On gold from 1m to 15m only normal settings are profitable in both halves; on BTC from 1m to 15m almost only inverted ones; on the higher timeframes it goes both ways (BTC 30m normal, BTC 1h to 4h inverted, gold 30m normal, gold 1h inverted, gold 2h and 4h normal). No side wins consistently.
- **1m and 5m: almost nothing.** With costs, fewer than 1% of the settings are profitable in both halves on the 1-minute and 5-minute charts of either pair.
- **2h and 4h are not independent.** The XPW ladder has no 2-hour rung, so the 2h chart reads the 4-hour rung. Settings without a trailing stop or stop loss make the same trades on both charts (checked on BTC).

### Data

Every setting of every timeframe, with its inputs, trades, net result, profit factor, drawdown and both halves: [`calibration_xpw.csv.gz`](calibration_xpw.csv.gz) (381,024 rows).

### Limits

- The windows are short: 2 years of BTC (2024-11 to 2026-11), 18 months of gold (2017-01 to 2018-06). The gold data is old.
- Only the "Signal tick" entry mode was searched, with trailing and stop distances in percent of price.
- Margin calls are not modelled; with 20 open entries at 10% of equity each, the exposure can reach twice the equity.
- Nothing here was compiled or run in TradingView.

## The other XPW file (S2 / S3 exits): normal vs inverted by timeframe

Everything above is about the trailing-TP file. This section is about [`xpw_orientation_tdi_v2.8_strategy_FGF.pine`](../xpw_orientation_tdi_v2.8_strategy_FGF.pine), the version with the ATR stop, the target in R, the ATR trailing stop and its own sizing. Its signals are the same code as the trailing-TP file's (the two blocks are identical line for line), so only the orders and exits differ.

- **Inputs.** The file's defaults: stop 3 ATR, target 1R, trailing 1.0 / 0.75 ATR, no time stop, 0.1 unit per entry, up to 20 open entries, 10,000 account. Normal = the file as it is; inverted = the Update 1 option on.
- **Money.** A fixed 0.1 unit per entry on a 10,000 account. On gold that is about $130 per entry, so the percentages are small. On BTC it is about $9,000 per entry and entries stack, so the percentages are large and can go below -100% (the account would be gone; TradingView's margin is not modelled).
- **"As TradingView shows"**: the standard backtest with the file's own costs (none). **"1-minute fills with our costs"**: exits checked on 1-minute candles, gold $0.30 per ounce per round trip, BTC 0.02% per side + $0.20.
- **How it was tested.** A new Python replica of the orders and exits: two builds written independently agree on all 8.45 million trades of 1,536 settings, and an auditor's own separately written reference agrees on another 878,810 trades. No defect was found.

### BTCUSD

| TF | Filter | Trades normal / inverted | As TradingView shows: normal / inverted | 1-minute fills with our costs: normal / inverted | Inverted, both halves (1-minute fills, our costs) | PF inverted (same) |
|---|---|---|---|---|---|---|
| 1m | off | 63,358 / 63,358 | +477.9% / +364.2% | -1800.7% / **-1914.3%** | -1148.1% / -766.2% | 0.45 |
| 1m | on | 22,169 / 22,169 | +178.3% / +227.1% | -618.4% / **-569.6%** | -334.3% / -235.3% | 0.54 |
| 5m | off | 23,789 / 23,789 | +384.0% / +199.7% | -559.6% / **-761.0%** | -443.9% / -317.1% | 0.70 |
| 5m | on | 8,831 / 8,831 | +110.0% / +160.9% | -245.8% / **-199.5%** | -105.7% / -93.8% | 0.80 |
| 15m | off | 11,644 / 11,644 | +316.5% / +158.7% | -187.8% / **-368.4%** | -272.5% / -95.9% | 0.81 |
| 15m | on | 4,728 / 4,728 | +56.6% / +173.0% | -160.2% / **-62.8%** | -45.6% / -17.2% | 0.93 |
| 30m | off | 6,945 / 6,945 | +254.7% / +216.7% | -87.5% / **-147.4%** | -142.1% / -5.4% | 0.91 |
| 30m | on | 2,943 / 2,943 | +134.2% / +137.4% | -14.7% / **-40.4%** | -50.6% / +10.2% | 0.95 |
| 1h | off | 3,886 / 3,886 | +63.3% / +242.3% | -158.4% / **-46.8%** | -37.0% / -9.9% | 0.96 |
| 1h | on | 1,807 / 1,807 | +47.9% / +189.1% | -68.8% / **+31.1%** | -31.3% / +62.4% | 1.05 |
| 2h | off | 1,826 / 1,826 | +48.9% / +226.1% | -99.5% / **+62.8%** | +25.4% / +37.4% | 1.07 |
| 2h | on | 849 / 849 | +19.9% / +134.9% | -47.1% / **+57.5%** | +47.9% / +9.6% | 1.13 |
| 4h | off | 1,094 / 1,094 | -41.7% / +161.0% | -137.3% / **+46.9%** | +1.0% / +45.9% | 1.07 |
| 4h | on | 486 / 486 | -62.0% / +75.2% | -98.3% / **+25.3%** | +33.7% / -8.4% | 1.07 |

### XAUUSD

| TF | Filter | Trades normal / inverted | As TradingView shows: normal / inverted | 1-minute fills with our costs: normal / inverted | Inverted, both halves (1-minute fills, our costs) | PF inverted (same) |
|---|---|---|---|---|---|---|
| 1m | off | 29,828 / 29,828 | +0.5% / +0.7% | -8.4% / **-8.3%** | -4.2% / -4.1% | 0.20 |
| 1m | on | 10,795 / 10,795 | +0.1% / +0.4% | -3.1% / **-2.9%** | -1.5% / -1.4% | 0.24 |
| 5m | off | 11,022 / 11,022 | +0.4% / +0.5% | -3.2% / **-3.0%** | -1.6% / -1.4% | 0.48 |
| 5m | on | 4,268 / 4,268 | +0.2% / +0.3% | -1.2% / **-1.1%** | -0.5% / -0.6% | 0.58 |
| 15m | off | 5,399 / 5,399 | +0.3% / +0.2% | -1.6% / **-1.7%** | -0.9% / -0.8% | 0.63 |
| 15m | on | 2,213 / 2,213 | +0.1% / +0.1% | -0.7% / **-0.8%** | -0.3% / -0.4% | 0.66 |
| 30m | off | 3,117 / 3,117 | +0.3% / +0.1% | -0.9% / **-1.0%** | -0.3% / -0.7% | 0.72 |
| 30m | on | 1,312 / 1,312 | +0.1% / +0.1% | -0.4% / **-0.5%** | -0.1% / -0.3% | 0.76 |
| 1h | off | 1,782 / 1,782 | +0.0% / +0.4% | -0.8% / **-0.5%** | -0.1% / -0.4% | 0.83 |
| 1h | on | 811 / 811 | +0.1% / +0.1% | -0.3% / **-0.3%** | -0.1% / -0.2% | 0.81 |
| 2h | off | 855 / 855 | +0.2% / +0.2% | -0.2% / **-0.3%** | -0.1% / -0.2% | 0.84 |
| 2h | on | 398 / 398 | +0.2% / -0.1% | -0.0% / **-0.3%** | -0.1% / -0.1% | 0.74 |
| 4h | off | 544 / 544 | +0.4% / -0.2% | +0.1% / **-0.5%** | -0.1% / -0.4% | 0.74 |
| 4h | on | 247 / 247 | +0.2% / -0.2% | +0.1% / **-0.4%** | -0.1% / -0.2% | 0.64 |

### What it shows

- **BTC, normal direction: loses on every timeframe** with 1-minute fills and costs.
- **BTC, inverted: positive in both halves on 2h (filter off +62.8%, filter on +57.5%) and on 4h with the filter off (+46.9%).** It is also positive overall on 1h and 4h with the filter on, with one losing half each.
- **Those inverted results are thin.** Profit factor 1.07 to 1.13, about $3 to $7 per 0.1 BTC entry, and a drawdown of 31% to 85% of the account on the way. They are single default runs, not tested by any hold-out. The calibration below is what decides whether they are real.
- **1m to 30m lose in both directions on both pairs.**
- **Gold loses in both directions on every timeframe**, apart from +0.1% on 4h normal.
- **TradingView's own figures flatter the trailing stop.** With the trail on, 15-17% of trades end differently once the exit is checked on 1-minute candles, and every BTC timeframe above 1m is worse. That is why "as TradingView shows" is positive almost everywhere on BTC and the realistic column is not.

### Limits

- **BTC figures ignore margin.** With TradingView's default 100% margin, 0.1 BTC per entry on a 10,000 account would be cut by refused orders and margin calls. Read the BTC rows as money per 0.1 BTC entry.
- **TradingView's order matching (FIFO)** can pair exits with other entries than the replica does. Net profit is the same; TradingView's win rate would read 1 to 7 points lower.
- **Not reproduced:** "Require rung agreement" on, the seconds rungs, and anything that only happens live.
- Short windows and old gold data, as above. Nothing here was compiled or run in TradingView.
