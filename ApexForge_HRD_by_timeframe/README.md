# ApexForge Flow Resonance and HRD Full Divergence v1.03: results by timeframe, filter off vs on

Files tested:
- [`ApexForge_Flow_Resonance_Strategy_FGF.pine`](../ApexForge_Flow_Resonance_Strategy_FGF.pine)
- [`HRD_Full_Divergence_Strategy_v1_03_FGF.pine`](../HRD_Full_Divergence_Strategy_v1_03_FGF.pine)

With "Enable filter" off, each one trades exactly like your original file. Every other input is at the file's defaults.

## How it was tested

- **Replicas.** A Python replica of each fused file, built independently twice. The two builds agree on 100% of trades. A third auditor checked each one line by line against the Pine and found no defects. For ApexForge, the auditor also wrote its own independent replica, which matches on every trade on all 14 pair / timeframe cells.
- **Filter.** The direction filter's permissions come from the same verified replica used for the XPW tests.
- **Fills.** As in TradingView's Strategy Tester without Bar Magnifier: orders fill at the next candle's open, and the stop / target are checked along the candle's high / low.
- **Data.**
  - BTCUSD: Bitstamp, 2024-11-17 to 2026-11-17, real volume.
  - XAUUSD: Dukascopy, 2017-01-02 to 2018-06-19, tick volume, as TradingView shows for CFD gold.
- **Money.** $1,000,000 start, the Pine default; results are in % so the capital doesn't matter.
  - ApexForge puts 1% of equity in each trade, so its percentages are small: -0.27% means it lost 27% of one position's size over the whole window.
  - HRD risks 1% over a 2% stop, which is about 50% of equity per trade.
- **"As TradingView shows"** uses each script's own Properties: ApexForge pays 0.04% commission per side, HRD pays nothing. **"With our costs"** replaces that with the costs used in every other test here:
  - gold $0.30 per ounce per round trip;
  - BTC 0.02% per side + $0.20 per round trip.

  For ApexForge our costs are lower than its own 0.04%, so it loses less with them.
- **Halves** is the change in equity in each half of the window. **Labels reversed** swaps every buy and sell, with the filter off: HRD's own "Reverse Trading" input, and a swap done in the replica for ApexForge. A strategy whose signals have a real direction should do clearly worse reversed.

## ApexForge Flow Resonance

### BTCUSD

| TF | Trades off / on | **Net % as TradingView shows, off / on** | Net % with our costs, off / on | PF off / on | Max DD % off / on | Halves on (1st / 2nd) | Labels reversed, filter off |
|---|---|---|---|---|---|---|---|
| 1m | 34,602 / 17,221 | **-23.999% / -12.971%** | -12.787% / -6.802% | 0.44 / 0.45 | 24.011 / 12.977 | -6.279% / -6.692% | -24.304% |
| 5m | 4,955 / 3,076 | **-3.709% / -2.960%** | -1.793% / -1.766% | 0.72 / 0.66 | 3.808 / 3.054 | -1.462% / -1.498% | -3.679% |
| 15m | 1,180 / 861 | **-0.470% / -0.565%** | -0.002% / -0.223% | 0.92 / 0.87 | 0.820 / 0.912 | -0.365% / -0.199% | -0.986% |
| 30m | 359 / 274 | **+0.585% / +0.050%** | +0.729% / +0.160% | 1.23 / 1.02 | 0.309 / 0.331 | -0.057% / +0.108% | -1.006% |
| 1h | 131 / 76 | **-0.217% / -0.272%** | -0.165% / -0.241% | 0.86 / 0.72 | 0.530 / 0.329 | -0.207% / -0.065% | -0.415% |
| 2h | 52 / 26 | **-0.330% / -0.300%** | -0.309% / -0.290% | 0.59 / 0.35 | 0.416 / 0.324 | -0.204% / -0.096% | +0.651% |
| 4h | 31 / 10 | **+0.004% / -0.118%** | +0.016% / -0.114% | 1.01 / 0.48 | 0.354 / 0.223 | -0.034% / -0.084% | -0.305% |

### XAUUSD

| TF | Trades off / on | **Net % as TradingView shows, off / on** | Net % with our costs, off / on | PF off / on | Max DD % off / on | Halves on (1st / 2nd) | Labels reversed, filter off |
|---|---|---|---|---|---|---|---|
| 1m | 3,651 / 2,164 | **-3.198% / -1.994%** | -1.179% / -0.787% | 0.28 / 0.29 | 3.204 / 2.005 | -0.926% / -1.068% | -2.561% |
| 5m | 875 / 606 | **-0.758% / -0.410%** | -0.267% / -0.068% | 0.54 / 0.62 | 0.773 / 0.431 | -0.174% / -0.236% | -0.653% |
| 15m | 290 / 229 | **-0.332% / -0.303%** | -0.168% / -0.174% | 0.65 / 0.60 | 0.341 / 0.320 | -0.197% / -0.105% | -0.128% |
| 30m | 194 / 138 | **-0.273% / -0.162%** | -0.163% / -0.084% | 0.63 / 0.69 | 0.298 / 0.184 | -0.039% / -0.123% | -0.060% |
| 1h | 74 / 40 | **-0.039% / -0.103%** | +0.003% / -0.081% | 0.90 / 0.56 | 0.122 / 0.159 | -0.037% / -0.066% | -0.126% |
| 2h | 37 / 17 | **-0.153% / -0.035%** | -0.132% / -0.025% | 0.44 / 0.66 | 0.188 / 0.110 | +0.028% / -0.063% | -0.031% |
| 4h | 10 / 2 | **-0.106% / -0.041%** | -0.100% / -0.040% | 0.09 / 0.00 | 0.111 / 0.044 | -0.041% / +0.000% | -0.087% |

**What it shows**

- **Commission decides the result.** Before commission the P/L is close to zero everywhere: -0.5% to +0.9% of capital. The 0.04% per side then turns almost every cell into a loss that grows with the trade count. On BTC 1m with the filter off it makes +0.2% before commission and pays 24.2% in commission: -24.0% net.
- **3 of the 28 TradingView figures are positive:** BTC 30m off +0.585%, BTC 30m on +0.050%, BTC 4h off +0.004%. Only BTC 30m with the filter off is positive in both halves. Gold loses on every timeframe, filter off and on.
- **The filter mostly loses less by trading less.** It halves the trades on 1m (BTC -24.0% to -13.0%). Its P/L before commission beats filter off on only 6 of 14 cells, and on the best cell, BTC 30m, it lowers the result from +0.585% to +0.050%.
- **With the filter on, most low-timeframe trades end with the "blocked opposite signal still closes the trade" close.** On BTC 1m that is 15,488 of 17,221 trades. Turning that option off loses less on 7 of 14 cells (BTC 1m: -3.9% instead of -13.0%).
- **No consistent direction edge.** Reversed labels do better than the real ones on 6 of 7 gold timeframes. On BTC the real labels do better on 5 of 7, most clearly on 30m (+0.585% against -1.006%).

## HRD Full Divergence v1.03

### BTCUSD

| TF | Trades off / on | **Net % as TradingView shows, off / on** | Net % with our costs, off / on | PF off / on | Max DD % off / on | Halves on (1st / 2nd) | Labels reversed, filter off |
|---|---|---|---|---|---|---|---|
| 1m | 25,630 / 10,186 | **-11.59% / -11.56%** | -99.49% / -88.61% | 0.98 / 0.95 | 21.18 / 15.41 | -7.59% / -3.97% | +5.16% |
| 5m | 5,648 / 2,282 | **-5.86% / -5.03%** | -69.78% / -39.99% | 0.98 / 0.96 | 17.84 / 12.77 | -6.91% / +1.89% | +0.58% |
| 15m | 2,105 / 909 | **+13.58% / -2.61%** | -25.63% / -18.89% | 1.07 / 0.97 | 9.89 / 6.98 | -0.87% / -1.74% | -9.38% |
| 30m | 1,185 / 576 | **-5.85% / -6.78%** | -25.82% / -16.98% | 0.96 / 0.91 | 11.69 / 12.58 | -6.56% / -0.23% | +0.65% |
| 1h | 621 / 248 | **+2.72% / +4.66%** | -9.34% / -0.44% | 1.02 / 1.11 | 10.73 / 6.37 | +7.36% / -2.70% | -4.97% |
| 2h | 333 / 97 | **+13.34% / -6.70%** | +6.00% / -8.50% | 1.15 / 0.75 | 8.68 / 13.56 | -2.22% / -4.47% | -20.09% |
| 4h | 190 / 48 | **-8.66% / -6.07%** | -12.08% / -6.97% | 0.87 / 0.63 | 20.65 / 9.16 | -5.70% / -0.37% | +9.67% |

### XAUUSD

| TF | Trades off / on | **Net % as TradingView shows, off / on** | Net % with our costs, off / on | PF off / on | Max DD % off / on | Halves on (1st / 2nd) | Labels reversed, filter off |
|---|---|---|---|---|---|---|---|
| 1m | 17,905 / 7,237 | **-0.99% / -3.59%** | -87.90% / -58.78% | 0.99 / 0.93 | 3.07 / 4.55 | -1.33% / -2.26% | -1.12% |
| 5m | 4,091 / 1,731 | **-2.32% / -2.42%** | -39.57% / -20.37% | 0.96 / 0.91 | 5.88 / 4.71 | +1.00% / -3.42% | +2.67% |
| 15m | 1,484 / 646 | **-6.44% / -2.22%** | -21.40% / -9.36% | 0.84 / 0.89 | 7.62 / 4.15 | -0.41% / -1.81% | +6.31% |
| 30m | 770 / 357 | **+2.81% / +0.65%** | -6.09% / -3.49% | 1.10 / 1.04 | 2.59 / 2.58 | +1.63% / -0.98% | -1.84% |
| 1h | 394 / 165 | **+2.97% / +0.67%** | -1.69% / -1.27% | 1.14 / 1.07 | 2.31 / 1.53 | +0.34% / +0.33% | -2.81% |
| 2h | 249 / 74 | **-4.86% / -2.09%** | -7.60% / -2.94% | 0.78 / 0.72 | 5.69 / 2.96 | +0.46% / -2.55% | +4.25% |
| 4h | 141 / 38 | **-3.15% / -0.04%** | -4.75% / -0.48% | 0.84 / 0.99 | 7.38 / 3.27 | +1.08% / -1.12% | +5.45% |

**What it shows**

- **Our costs sink it.** Each trade carries about 50% of equity and lasts about 6 candles, so everything under 30m loses heavily once costs are counted: BTC 1m -99% off / -89% on, gold 1m -88% / -59%. TradingView shows no costs for this script. The only cell positive with our costs is BTC 2h with the filter off (+6.0%).
- **The filter adds no consistent edge.** Under TradingView's costs it beats filter off on 6 of 14 cells, ties on 2 and loses on 6.
  - It wipes out the two best BTC cells: 15m +13.6% to -2.6%, and 2h +13.3% to -6.7%.
  - It shrinks the two positive gold cells: 30m +2.8% to +0.7%, and 1h +3.0% to +0.7%.
  - What it reliably does is cut trades to 25-49%, time in the market to 4-12% of candles, and the drawdown on 11 of 14 cells.
- **The signals' direction is not stable.** With the filter off, reversed labels do better than the real ones on 8 of 14 cells. The best filter-off cells (BTC 15m and 2h) earn almost all of it in the second half.
- **Best with the filter on:** BTC 1h, +4.7% as TradingView shows it, PF 1.11, drawdown 6.4%. But it earns +7.4% in the first half, gives back 2.7% in the second, and is -0.4% with our costs.
- **Exits.** 54-92% of trades end with the 5-candle time exit. With the filter on, gold never reaches the 2% stop or the 4% target.

## Limits of this test

- **Pivot ties.** Both scripts find pivots with `ta.pivothigh` / `ta.pivotlow`. How TradingView treats two equal highs or lows can't be checked here, so the replica requires a strictly higher or lower pivot. On BTC 1m the other reading gives HRD about 17% more trades and moves it by 5-7 points. From 1h up it changes HRD by at most about 2 points and ApexForge by a fraction of a point.
- **HRD reversal sizing.** HRD reverses with an entry while the time exit closes on the same candle. Whether TradingView sizes that entry when it is placed or when it fills can't be checked here.
  - With the filter on, the other reading moves results by at most 0.9 points.
  - With the filter off it moves them by up to about 4 points (for example BTC 15m +13.6% to +15.1%, BTC 1h +2.7% to -0.2%). So the filter-off column and the off-vs-on comparison are the less certain ones.
- **Live vs backtest.** HRD runs on every tick live, so live divergence and breakout entries can differ from this backtest (see the file's header). ApexForge's 15m levels differ live on charts below 15m.
- **A trade open at the end.** It is closed at the last candle here; TradingView leaves it as open P/L. That moves each figure by at most about 0.14 points.
- **Data.** The gold data is from 2017-2018; percentages carry over to today's prices, dollar distances do not. Two years of BTC is a short window.
