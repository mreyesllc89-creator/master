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

## Next: every trailing setting on every timeframe

The trailing sweep (activation x offset x stop loss, filter off and on, with and without Bar Magnifier) is running. Its results will be added here.
