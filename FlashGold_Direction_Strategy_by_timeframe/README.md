# FlashGold Direction Strategy: results by timeframe

File tested: [`FlashGold_Direction_Strategy.pine`](../FlashGold_Direction_Strategy.pine). It trades the FlashGold Direction Filter's own decisions: by default it buys when a BUY ZONE starts and sells when a SELL ZONE starts, with a stop of 1 x ATR, a target of 3R, risk 0.5% of equity per trade on a 10,000 account.

## Normal vs inverted at the defaults

"Inverted" is the file's own input "Trade direction: Inverted", which it had before Update 1 (Update 1 only numbered the file). It takes the opposite side on the same candle with the same stop and target distances.

- **Data.** BTCUSD: Bitstamp, 2024-11-17 to 2026-11-17. XAUUSD: Dukascopy, 2017-01-02 to 2018-06-19.
- **The filter is always on.** This strategy trades the filter's zones, so with the filter off it takes no trade at all.
- **"As TradingView shows"** has no costs: the file's Properties are commission 0 and slippage 0. **"1-minute fills with our costs"** is the realistic figure: stop and target checked on 1-minute candles, gold $0.30 per ounce per round trip, BTC 0.02% per side + $0.20.
- **Trades** are counted on the 1-minute view; an account that can no longer size a trade stops trading there, so the counts can be lower than in TradingView's view.
- **How it was tested.** A new Python replica: two builds written independently agree on all 3.8 million trades of 1,760 test cases, and an audit against the Pine found no defect.

### BTCUSD

| TF | Trades normal / inverted | As TradingView shows: normal / inverted | 1-minute fills with our costs: normal / inverted | Inverted, both halves (1-minute fills, our costs) | PF inverted (same) |
|---|---|---|---|---|---|
| 1m | 2,391 / 2,524 | +26,274% / +63,461% | -100.0% / **-100.0%** | -100.0% / -45.5% | 0.35 |
| 5m | 5,216 / 5,228 | +101.0% / +2,761% | -100.0% / **-100.0%** | -99.9% / -66.7% | 0.62 |
| 15m | 7,772 / 8,781 | -11.7% / +330.8% | -99.8% / **-99.7%** | -97.3% / -90.1% | 0.71 |
| 30m | 6,769 / 6,769 | -21.1% / +144.1% | -98.3% / **-95.3%** | -84.6% / -69.4% | 0.77 |
| 1h | 3,233 / 3,233 | -35.0% / +99.5% | -80.6% / **-44.4%** | -24.7% / -26.1% | 0.91 |
| 2h | 2,242 / 2,242 | -14.5% / +13.6% | -52.2% / **-36.6%** | -25.4% / -15.0% | 0.90 |
| 4h | 1,465 / 1,465 | +17.4% / +13.4% | -9.2% / **-12.0%** | -3.6% / -8.7% | 0.95 |

### XAUUSD

| TF | Trades normal / inverted | As TradingView shows: normal / inverted | 1-minute fills with our costs: normal / inverted | Inverted, both halves (1-minute fills, our costs) | PF inverted (same) |
|---|---|---|---|---|---|
| 1m | 2,586 / 2,776 | -82.0% / +148.6% | -100.0% / **-100.0%** | -100.0% / -17.0% | 0.16 |
| 5m | 4,650 / 5,442 | -73.6% / +108.2% | -100.0% / **-100.0%** | -99.9% / -98.8% | 0.35 |
| 15m | 4,257 / 4,257 | -47.0% / +55.8% | -99.8% / **-99.4%** | -91.6% / -92.3% | 0.53 |
| 30m | 2,995 / 2,995 | -46.4% / +15.4% | -96.3% / **-92.1%** | -72.4% / -71.5% | 0.60 |
| 1h | 1,473 / 1,473 | +2.0% / +2.8% | -60.0% / **-59.7%** | -37.0% / -36.1% | 0.73 |
| 2h | 1,041 / 1,041 | -19.6% / +20.3% | -50.6% / **-24.5%** | -14.1% / -12.2% | 0.88 |
| 4h | 703 / 703 | -10.4% / +22.1% | -28.3% / **-2.7%** | +8.7% / -10.5% | 0.98 |

### What it shows

- **Every default setting loses with realistic costs, in both directions, on every timeframe of both pairs.** The least bad are gold 4h inverted (-2.7%), BTC 4h normal (-9.2%) and BTC 4h inverted (-12.0%).
- **1m to 15m: the account is wiped out** in both directions on both pairs.
- **TradingView's own view favours inverted almost everywhere** (BTC 1h: -35.0% normal, +99.5% inverted, no costs). Most of that disappears with costs: the strategy trades often, and the costs are larger than the edge.
- **BTC 1m and 5m "as TradingView shows" are not results.** Without costs, both directions grow the account many times over by stacking the file's 50-unit maximum on a tiny stop; with costs the same settings lose everything.

### Limits

- **TradingView's report stops at about 9,000 trades**, and BTC 1m, 5m and 15m and gold 1m take more than that at the defaults.
- **Margin** (the file sets 1%) is not modelled: refused orders are only counted, and they matter only on BTC 1m.
- **Not reproduced:** rounding of prices to the tick, TradingView's own Bar Magnifier feed (the 1-minute view uses this data's 1-minute candles), seconds charts, anything live.
- Short windows and old gold data. Nothing here was compiled or run in TradingView.

## Calibration by timeframe, with the direction as an input

The file's inputs were searched per pair and timeframe, with "Trade direction: Inverted" as one of them: 302,400 backtests.

### What was searched

21,600 settings on every timeframe from 1m to 4h of BTCUSD and XAUUSD:

| | Values |
|---|---|
| Filter | filter timeframe 15, 60 or 240 (its parent and zone timeframes move with it); burst threshold 0.25, 0.5, 1.0 x ATR; no-trade band 0, 0.25, 0.75 x ATR; level at the entry price or the signal close; TDI trade-zone check on or off |
| Entry trigger | "Zone start", "Signal confirmed", or "New signal" (the last one ignores the band and the level) |
| Direction | normal ("Follow the filter") or inverted |
| Exits | "Exit when the zone ends" on or off; reverse on an opposite trigger on or off; stop 0.5, 1, 2 x ATR; exit: 3R target, 1.5R target, no target, or an ATR trailing stop |

- **The filter is on in every setting.** This strategy trades the filter's own zones; with the filter off it takes no trade.
- **Scoring.** 1-minute fills with costs (gold $0.30 per ounce per round trip, BTC 0.02% per side + $0.20), on the two halves of the window separately.
- **Sizing.** Risk 0.5% of equity per trade as in the file, but without the file's 50-unit cap; a chosen setting is re-run with the file's own sizing before it counts.

### The rule

The same rule as for ApexForge and HRD ([how it works and what its audit found](../ApexForge_HRD_by_timeframe/README.md#the-rule-rule-c)), plus the step added after that audit: the selection is repeated on one half only, and the setting it picks must be profitable on the other half and beat its direction-flipped twin there, both ways. A pass is a reason to review a setting, never a reason to trade it.

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
| 1m | 14,952 | 8 / 0 | -100.00% / -100.00% | +319.77% (+116.74% / +93.67%, 608 trades) | -18.25% (-10.22% / -8.94%, 910 trades) | -23.10% vs -76.02%, 22% positive: FAIL | -23.94% vs -92.75%, 20% positive: FAIL | none / +8.54% | no setting: none of the 8 best candidates sits on a plateau |
| 5m | 16,719 | 27 / 10 | -100.00% / -99.99% | +660.72% (+171.77% / +179.91%, 586 trades) | +114.40% (+34.93% / +58.89%, 1635 trades) | -7.53% vs -73.17%, 28% positive: FAIL | -18.63% vs -80.65%, 18% positive: FAIL | -4.24% / -10.24% | no setting: none of the 37 best candidates sits on a plateau |
| 15m | 16,677 | 93 / 49 | -95.13% / -90.49% | +260.49% (+66.27% / +116.81%, 321 trades) | +177.18% (+67.54% / +65.44%, 1079 trades) | -14.29% vs -53.95%, 35% positive: FAIL | -23.03% vs -55.24%, 15% positive: FAIL | -56.95% / -57.17% | no setting: forward hold-out failed; reverse hold-out failed; nested forward pick failed; nested reverse pick failed |
| 30m | 17,130 | 209 / 169 | -73.94% / -68.19% | +310.74% (+93.49% / +112.28%, 465 trades) | +407.06% (+203.24% / +67.22%, 1207 trades) | +3.46% vs -38.28%, 42% positive: FAIL | -19.05% vs -37.63%, 18% positive: FAIL | +64.85% / -45.76% | no setting: the direction-flipped twin does as well in a half; forward hold-out failed; reverse hold-out failed; nested reverse pick failed |
| 1h | 16,815 | 246 / 165 | -42.52% / -39.01% | +156.43% (+47.01% / +74.44%, 845 trades) | +67.02% (+26.45% / +32.09%, 769 trades) | -18.25% vs -21.08%, 18% positive: FAIL | -26.32% vs -21.30%, 10% positive: FAIL | -48.24% / -27.61% | no setting: forward hold-out failed; reverse hold-out failed; nested forward pick failed; nested reverse pick failed |
| 2h | 16,549 | 251 / 416 | -24.33% / -16.10% | +47.67% (+23.09% / +19.97%, 161 trades) | +70.66% (+26.49% / +34.93%, 511 trades) | -16.24% vs -10.29%, 12% positive: FAIL | -13.85% vs -10.58%, 28% positive: FAIL | +2.94% / +1.15% | no setting: none of the 40 best candidates sits on a plateau |
| 4h | 15,329 | 308 / 533 | -11.60% / -10.32% | +32.51% (+15.90% / +14.33%, 595 trades) | +165.25% (+57.10% / +68.84%, 433 trades) | +7.68% vs -4.46%, 50% positive: FAIL | +2.21% vs -5.03%, 42% positive: FAIL | -21.48% / -4.60% | no setting: forward hold-out failed; reverse hold-out failed; nested forward pick failed; nested reverse pick failed |

#### XAUUSD

| TF | Different results | Positive in both halves: normal / inverted | Typical result: normal / inverted | Best normal (halves, trades) | Best inverted (halves, trades) | Forward hold-out | Reverse hold-out | Chosen on one half, result on the other: first to second / second to first | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| 1m | 12,915 | 0 / 0 | -100.00% / -100.00% | -36.05% (-19.56% / -20.49%, 144 trades) | -24.10% (-12.40% / -13.36%, 302 trades) | -48.60% vs -81.96%, 0% positive: FAIL | -49.72% vs -91.42%, 0% positive: FAIL | none / none | no setting: no setting is positive in both halves with 30+ trades in each |
| 5m | 16,564 | 9 / 4 | -99.93% / -99.82% | +51.38% (+33.87% / +13.08%, 443 trades) | +28.75% (+10.73% / +16.27%, 322 trades) | -27.25% vs -72.17%, 8% positive: FAIL | -36.99% vs -76.33%, 10% positive: FAIL | -13.15% / -17.40% | no setting: none of the 13 best candidates sits on a plateau |
| 15m | 16,422 | 72 / 22 | -87.91% / -87.77% | +299.05% (+74.22% / +129.04%, 98 trades) | +64.27% (+23.16% / +33.38%, 110 trades) | -9.83% vs -51.78%, 20% positive: FAIL | -16.14% vs -51.08%, 20% positive: FAIL | -2.14% / -9.20% | no setting: none of the 40 best candidates sits on a plateau |
| 30m | 16,937 | 208 / 16 | -61.81% / -65.76% | +63.52% (+24.09% / +31.77%, 496 trades) | +34.60% (+18.26% / +13.82%, 167 trades) | -12.90% vs -35.96%, 10% positive: FAIL | -18.45% vs -35.53%, 8% positive: FAIL | -19.49% / -6.21% | no setting: none of the 40 best candidates sits on a plateau |
| 1h | 16,419 | 275 / 40 | -33.61% / -41.14% | +53.85% (+31.24% / +17.24%, 285 trades) | +24.90% (+11.78% / +11.73%, 103 trades) | -19.19% vs -21.31%, 8% positive: FAIL | -20.56% vs -20.36%, 0% positive: FAIL | -25.32% / -12.94% | no setting: none of the 40 best candidates sits on a plateau |
| 2h | 16,637 | 534 / 62 | -17.26% / -27.62% | +58.24% (+25.13% / +26.46%, 379 trades) | +17.76% (+9.89% / +7.16%, 83 trades) | -6.71% vs -11.90%, 18% positive: FAIL | -6.28% vs -11.89%, 28% positive: FAIL | -7.47% / -13.37% | no setting: forward hold-out failed; reverse hold-out failed; nested forward pick failed; nested reverse pick failed |
| 4h | 15,275 | 896 / 155 | -5.30% / -15.29% | +85.86% (+29.91% / +43.06%, 221 trades) | +33.59% (+13.23% / +17.98%, 618 trades) | -1.55% vs -5.26%, 35% positive: FAIL | +2.90% vs -4.50%, 52% positive: FAIL | -12.75% / +5.70% | no setting: forward hold-out failed; reverse hold-out failed; nested forward pick failed |

### What it shows

- **No setting passes on any timeframe of either pair, in either direction.**
- **The typical setting loses on every timeframe, in both directions.** On 1m and 5m most settings lose the whole account.
- **The best settings look very large only in-sample** (BTC 5m normal +661%, BTC 30m inverted +407%, at 0.5% risk per trade compounding). Settings chosen on one half do not carry over: of the 40 best of one half, at most half are profitable on the other, and of the 25 single settings chosen on one half, 5 were profitable on the other.
- **Closest: BTC 4h and BTC 2h.** On BTC 4h the 40 best of the first half average +7.7% on the second, but only 50% of them are profitable (60% needed). On BTC 2h the settings chosen on one half were profitable on the other in both directions (+2.9% and +1.1%), but no setting has enough profitable neighbours and both hold-outs fail.
- **Direction.** On gold, normal has far more profitable settings than inverted on every timeframe from 5m up (gold 4h: 896 against 155). On BTC it goes both ways: normal on 5m to 1h, inverted on 2h and 4h. Neither carries from one half to the other.

### Data

Every setting of every timeframe, with its inputs, trades, net result, profit factor, drawdown and both halves: [`calibration_fgds.csv.gz`](calibration_fgds.csv.gz) (302,400 rows).

### Limits

- The same limits as the by-timeframe section above: margin is not modelled, TradingView's report stops at about 9,000 trades, the windows are short and the gold data is old.
- Nothing here was compiled or run in TradingView.
