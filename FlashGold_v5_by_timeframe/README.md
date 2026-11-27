# FlashGold v5 Strategy (BTCUSD) FGF: results by timeframe

File tested: [`FlashGold_v5_Strategy_BTCUSD_FGF.pine`](../FlashGold_v5_Strategy_BTCUSD_FGF.pine) at its defaults: stop entry 0.25 ATR beyond the signal candle, valid 3 candles; exits in pips (1 pip = $1): stop $30, take 30% at 5R ($150), the rest runs with breakeven and a $600 trail; a fixed 10 units per trade on a 100,000 account; direction filter on.

## Normal vs inverted at the defaults

"Inverted" is the Update 1 option "Inverted direction: opposite side at the same entries". The stop entry becomes a limit entry at the same price, with the same distances to the stop and targets.

- **Data.** BTCUSD: Bitstamp, 2024-11-17 to 2026-11-17. XAUUSD: Dukascopy, 2017-01-02 to 2018-06-19.
- **Results in R** (1R = the $30 stop x 10 units = $300, 0.3% of the account). Percentages are not used: 10 BTC is about nine times the account, the file sets no margin, and equity goes far below zero on BTC, so a percentage says nothing.
- **"As TradingView shows"** uses the file's own Properties: 0.02% commission per side and 5 ticks of slippage. **"1-minute fills with our costs"**: stop, targets and trail checked on 1-minute candles, gold $0.30 per ounce per round trip, BTC 0.02% per side + $0.20.
- **Halves** are the sums of R of the trades entered in each half of the window.
- **How it was tested.** A new Python replica: two builds written independently agree on all 6.2 million trades of 1,120 test cases, and an auditor's own references written from the Pine agree with it. No defect was found.

### BTCUSD

| TF | Filter | Trades normal / inverted | As TradingView shows: normal / inverted | 1-minute fills with our costs: normal / inverted | Normal, both halves (same) | Inverted, both halves (same) |
|---|---|---|---|---|---|---|
| 1m | off | 85,658 / 160,503 | -36,888R / -208,763R | -37,165R / **-209,620R** | -23,439R / -13,727R | -122,395R / -87,225R |
| 1m | on | 27,775 / 52,369 | -10,838R / -61,058R | -10,939R / **-61,327R** | -6,859R / -4,080R | -37,557R / -23,771R |
| 5m | off | 23,767 / 37,885 | +215R / -47,341R | -7,989R / **-47,114R** | -4,566R / -3,422R | -28,327R / -18,787R |
| 5m | on | 13,399 / 19,707 | +1,250R / -23,433R | -4,244R / **-23,370R** | -2,271R / -1,972R | -14,276R / -9,095R |
| 15m | off | 9,178 / 12,481 | +6,702R / -15,138R | -1,714R / **-14,929R** | -722R / -992R | -8,991R / -5,938R |
| 15m | on | 5,868 / 7,304 | +4,555R / -8,595R | -1,055R / **-8,488R** | -466R / -589R | -5,344R / -3,144R |
| 30m | off | 4,951 / 6,072 | +8,249R / -7,925R | -511R / **-7,635R** | -517R / +6.4R | -4,400R / -3,234R |
| 30m | on | 2,806 / 3,080 | +4,918R / -4,017R | -250R / **-3,834R** | -219R / -30.8R | -2,229R / -1,605R |
| 1h | off | 2,670 / 2,976 | +7,193R / -3,963R | -662R / **-3,602R** | -571R / -90.3R | -2,367R / -1,235R |
| 1h | on | 0 / 0 | no trades | no trades | | |
| 2h | off | 1,319 / 1,424 | +6,657R / -2,204R | +102R / **-1,994R** | -126R / +228R | -1,071R / -923R |
| 2h | on | 241 / 243 | +1,401R / -319R | -24.2R / **-331R** | -63.1R / +38.9R | -163R / -168R |
| 4h | off | 719 / 734 | +5,198R / -1,009R | -124R / **-924R** | -160R / +35.6R | -544R / -380R |
| 4h | on | 163 / 164 | +1,277R / -347R | +155R / **-317R** | -90.2R / +245R | -197R / -121R |

### XAUUSD

| TF | Filter | Trades normal / inverted | As TradingView shows: normal / inverted | 1-minute fills with our costs: normal / inverted | Normal, both halves (same) | Inverted, both halves (same) |
|---|---|---|---|---|---|---|
| 1m | off | 16,658 / 16,658 | -335R / -289R | -162R / **-172R** | -84.0R / -77.6R | -83.8R / -87.7R |
| 1m | on | 2,109 / 2,109 | -46.2R / -32.8R | -24.3R / **-17.9R** | -15.0R / -9.3R | -6.5R / -11.4R |
| 5m | off | 4,374 / 4,374 | -91.6R / -72.1R | -46.4R / **-41.1R** | -28.1R / -18.3R | -16.9R / -24.2R |
| 5m | on | 1,479 / 1,479 | -37.4R / -18.0R | -22.0R / **-7.6R** | -14.3R / -7.8R | -0.9R / -6.7R |
| 15m | off | 1,521 / 1,521 | -31.9R / -25.0R | -16.1R / **-14.3R** | -9.8R / -6.4R | -5.6R / -8.7R |
| 15m | on | 883 / 883 | -24.1R / -9.0R | -14.9R / **-2.7R** | -10.2R / -4.7R | +1.3R / -4.0R |
| 30m | off | 727 / 729 | -2.7R / -24.7R | +4.9R / **-19.6R** | +3.8R / +1.1R | -11.2R / -8.4R |
| 30m | on | 475 / 480 | -3.7R / -13.7R | +1.3R / **-10.3R** | +2.0R / -0.8R | -6.4R / -3.9R |
| 1h | off | 434 / 438 | -11.8R / -4.7R | -7.4R / **-1.6R** | -2.9R / -4.4R | -1.4R / -0.2R |
| 1h | on | 0 / 0 | no trades | no trades | | |
| 2h | off | 245 / 251 | -7.1R / -3.2R | -4.6R / **-1.4R** | -2.2R / -2.4R | -0.8R / -0.7R |
| 2h | on | 63 / 65 | -1.7R / -0.4R | -1.1R / **+0.1R** | -1.0R / -0.0R | +2.0R / -1.9R |
| 4h | off | 120 / 127 | -3.7R / -1.8R | -2.4R / **-0.9R** | -2.0R / -0.4R | +0.9R / -1.7R |
| 4h | on | 28 / 37 | +1.4R / -4.0R | +1.7R / **-3.7R** | +1.7R / -0.1R | -2.2R / -1.5R |

### What it shows

- **BTC: TradingView's own figures for the normal direction are not real.** It shows +1,250R to +8,249R from 5m to 4h. On BTC a $30 stop is a small fraction of one candle, so TradingView's single assumed path through each candle decides most trades. With fills checked on 1-minute candles and costs, normal loses on every BTC timeframe except 2h with the filter off (+102R) and 4h with the filter on (+155R), and both of those have a losing half.
- **BTC inverted loses heavily everywhere.** It also trades more than normal (the limit entries fill on a touch).
- **Gold: the file's dollar distances only make sense at BTC prices.** On gold a $30 stop is 13 ATR on the 1h chart and no default trade reaches the $150 target, so the defaults become a stop-and-reverse system. Only one gold cell is positive in both halves: 30m normal with the filter off (+4.9R over 727 trades).
- **1h with the filter on takes no trade at all,** on both pairs and in both directions. On that chart the strategy's own signal is the filter's 1h signal, and the filter's level puts the signal candle's close on the other side.
- **1m to 15m lose on both pairs in both directions.**

### Limits

- **No margin.** This Pine v5 file sets none (the v5 default is no margin check), so TradingView keeps trading with negative equity, as the replica does.
- **TradingView's report** stops at about 9,000 trades in Pine v5; BTC 1m, 5m and 15m exceed it at the defaults.
- **Not reproduced:** rounding of the entry prices and the 30% partial to the symbol's tick and lot, TradingView's own Bar Magnifier feed, seconds timeframes, anything live. The file's header quotes MEXC / Bitfinex BTC and OANDA gold; these are other feeds.
- Short windows and old gold data. Nothing here was compiled or run in TradingView.

## Calibration by timeframe, with the direction as an input

The file's inputs were searched per pair and timeframe, with the Update 1 option "Inverted direction" as one of them: 223,776 backtests.

### What was searched

15,984 settings on every timeframe from 1m to 4h of BTCUSD and XAUUSD:

| | Values |
|---|---|
| Signals | burst threshold 0.3, 0.5, 1.0 x ATR; zones that must align 1, 2 or 3 |
| Filter and direction | filter off or on; normal or inverted |
| Entry | entry distance 0, 0.25, 0.5 x ATR; reverse on an opposite signal on or off |
| Exits | the file's default ($30 stop, 30% at 5R, runner with a $600 trail); or in ATR: a fixed stop and target, the file's "Partial + runner" (30% at the target, the rest trailing), or all runner; stop 0.25, 0.5, 1, 2 x ATR; target 1.5, 3, 5R; time stop off or 12 candles |

- **Scoring in R.** The file trades a fixed 10 units with no margin, so on BTC the equity goes far below zero and a percentage says nothing. Each setting is scored in R (multiples of its own stop), on 1-minute fills with costs (gold $0.30 per ounce per round trip, BTC 0.02% per side + $0.20), on the two halves of the window separately.

### The rule

The same rule as for ApexForge and HRD ([how it works and what its audit found](../ApexForge_HRD_by_timeframe/README.md#the-rule-rule-c)), applied to R, plus the step added after that audit: the selection is repeated on one half only, and the setting it picks must be profitable on the other half and beat its direction-flipped twin there, both ways. A pass is a reason to review a setting, never a reason to trade it.

### Results

How to read the table:

- **Different results**: settings with the same trades count once.
- **Positive in both halves**: how many of those are profitable in both halves with 30+ trades in each, per direction.
- **Typical result**: the median over settings with 30+ trades per half.
- **Best normal / inverted**: the setting with the best worst half, as net R (first half / second half, trades). In-sample: the best of thousands always looks good.
- **Hold-outs**: what the 40 best of one half made on the other half, against the 95th percentile of random draws.
- **Chosen on one half**: what the single setting picked on one half made on the other.

#### BTCUSD

| TF | Different results | Positive in both halves: normal / inverted | Typical result: normal / inverted | Best normal (halves, trades) | Best inverted (halves, trades) | Forward hold-out | Reverse hold-out | Chosen on one half, result on the other: first to second / second to first | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| 1m | 15,647 | 0 / 0 | -42,125.1R / -138,087.3R | -2,120.1R (-1,009.2R / -1,111.0R, 9675 trades) | -6,786.2R (-3,273.1R / -3,513.1R, 12374 trades) | -1,448.5R vs -60,009.4R, 0% positive: FAIL | -2,079.8R vs -55,047.8R, 0% positive: FAIL | none / none | no setting: no setting is positive in both halves with 30+ trades in each |
| 5m | 15,348 | 11 / 0 | -3,154.5R / -8,715.3R | +206.1R (+90.3R / +115.9R, 3108 trades) | -13.4R (-11.6R / -1.8R, 2640 trades) | -20.2R vs -3,803.2R, 35% positive: FAIL | -70.8R vs -3,784.2R, 22% positive: FAIL | none / none | no setting: none of the 11 best candidates sits on a plateau |
| 15m | 15,147 | 86 / 23 | -490.0R / -1,307.8R | +217.4R (+82.9R / +134.5R, 3437 trades) | +128.8R (+42.8R / +86.0R, 886 trades) | -143.0R vs -620.3R, 25% positive: FAIL | -47.2R vs -613.5R, 28% positive: FAIL | +49.8R / +35.6R | no setting: forward hold-out failed; reverse hold-out failed |
| 30m | 14,897 | 718 / 53 | -81.0R / -437.8R | +356.9R (+230.5R / +126.4R, 2335 trades) | +114.1R (+52.8R / +61.3R, 827 trades) | -46.3R vs -178.2R, 25% positive: FAIL | -40.2R vs -183.5R, 40% positive: FAIL | -68.1R / +28.8R | no setting: forward hold-out failed; reverse hold-out failed; nested forward pick failed |
| 1h | 11,478 | 1,141 / 265 | -21.2R / -94.7R | +294.7R (+153.1R / +141.5R, 1097 trades) | +202.4R (+98.7R / +103.7R, 1564 trades) | -140.7R vs -41.7R, 20% positive: FAIL | -67.9R vs -45.9R, 35% positive: FAIL | +69.3R / -70.7R | no setting: forward hold-out failed; reverse hold-out failed; nested reverse pick failed |
| 2h | 13,105 | 871 / 324 | -12.1R / -39.2R | +454.6R (+183.1R / +271.5R, 1049 trades) | +141.6R (+64.4R / +77.2R, 1137 trades) | +4.7R vs -8.6R, 52% positive: FAIL | -100.1R vs -20.4R, 22% positive: FAIL | +3.0R / -267.8R | no setting: stressed costs; forward hold-out failed; reverse hold-out failed; nested reverse pick failed |
| 4h | 13,099 | 1,073 / 793 | -4.3R / -16.3R | +536.1R (+131.3R / +404.8R, 783 trades) | +125.8R (+46.6R / +79.1R, 347 trades) | -8.3R vs -0.6R, 30% positive: FAIL | -59.7R vs -6.6R, 12% positive: FAIL | -36.5R / +131.3R | no setting: stressed costs; forward hold-out failed; reverse hold-out failed; nested forward pick failed |

#### XAUUSD

| TF | Different results | Positive in both halves: normal / inverted | Typical result: normal / inverted | Best normal (halves, trades) | Best inverted (halves, trades) | Forward hold-out | Reverse hold-out | Chosen on one half, result on the other: first to second / second to first | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| 1m | 15,072 | 0 / 0 | -20,910.5R / -27,430.1R | -16.1R (-11.0R / -5.1R, 1123 trades) | -6.4R (-0.2R / -6.2R, 1123 trades) | -9.5R vs -16,617.6R, 0% positive: FAIL | -8.9R vs -16,154.4R, 2% positive: FAIL | none / none | no setting: no setting is positive in both halves with 30+ trades in each |
| 5m | 14,974 | 0 / 0 | -2,687.7R / -3,083.5R | -6.7R (-4.2R / -2.4R, 539 trades) | +1.2R (+1.2R / -0.0R, 988 trades) | -30.8R vs -2,093.8R, 0% positive: FAIL | -4.9R vs -1,994.9R, 5% positive: FAIL | none / none | no setting: no setting is positive in both halves with 30+ trades in each |
| 15m | 14,829 | 53 / 2 | -558.7R / -691.9R | +70.9R (+41.4R / +29.5R, 493 trades) | +22.7R (+8.3R / +14.4R, 486 trades) | -20.4R vs -448.8R, 12% positive: FAIL | -21.4R vs -418.2R, 25% positive: FAIL | -19.9R / -23.5R | no setting: none of the 40 best candidates sits on a plateau |
| 30m | 14,618 | 306 / 4 | -150.1R / -248.2R | +96.9R (+48.5R / +48.4R, 419 trades) | +26.6R (+22.8R / +3.8R, 523 trades) | +11.8R vs -135.9R, 70% positive: pass | -18.6R vs -151.0R, 30% positive: FAIL | +19.8R / +11.2R | no setting: reverse hold-out failed |
| 1h | 11,102 | 649 / 34 | -29.6R / -94.3R | +79.7R (+43.5R / +36.3R, 394 trades) | +85.8R (+48.0R / +37.8R, 444 trades) | -52.8R vs -49.3R, 28% positive: FAIL | -46.6R vs -43.6R, 0% positive: FAIL | +24.2R / -33.2R | no setting: forward hold-out failed; reverse hold-out failed; nested reverse pick failed |
| 2h | 11,961 | 896 / 67 | -7.3R / -56.7R | +60.9R (+31.9R / +29.0R, 223 trades) | +43.7R (+19.5R / +24.2R, 254 trades) | -14.1R vs -16.4R, 20% positive: FAIL | -54.8R vs -22.5R, 2% positive: FAIL | -56.9R / -64.4R | no setting: forward hold-out failed; reverse hold-out failed; nested forward pick failed; nested reverse pick failed |
| 4h | 11,632 | 1,029 / 252 | +5.1R / -16.8R | +153.4R (+70.6R / +82.8R, 179 trades) | +79.0R (+42.4R / +36.6R, 173 trades) | -9.5R vs -5.0R, 40% positive: FAIL | +5.0R vs +4.0R, 55% positive: FAIL | +13.3R / +23.3R | no setting: forward hold-out failed; reverse hold-out failed |

### What it shows

- **No setting passes on any timeframe of either pair, in either direction.**
- **1m and 5m: almost nothing.** Not one setting with 30+ trades per half is profitable in both halves on 1m of either pair or on gold 5m; BTC 5m has 11.
- **Normal is far ahead of inverted** on every timeframe of both pairs (BTC 1h: 1,141 against 265 profitable settings; gold 30m: 306 against 4).
- **Closest: gold 30m, normal.** From the first half to the second the 40 best settings average +11.8R and 70% are profitable, which passes. From the second half to the first only 30% are, which fails. The settings chosen on one half alone were profitable on the other in both directions (+19.8R and +11.2R).
- **Also near: gold 4h and BTC 15m,** where the settings chosen on one half were profitable on the other in both directions, but both hold-outs fail. Gold 4h is the only cell where the typical normal setting is profitable (+5.1R).
- **Chosen on one half, scored on the other:** 11 of 20 such picks were profitable on the other half, more than for any other strategy here, but none of the cells passes the hold-outs as well.

These near misses are worth knowing, but under the rule fixed in advance they are fails, and no file was made from them.

### Data

Every setting of every timeframe, with its inputs, trades, net R, profit factor, drawdown and both halves in R: [`calibration_fgv5.csv.gz`](calibration_fgv5.csv.gz) (223,776 rows; `net_r`, `h1_r`, `h2_r` are in R, `max_dd_pct_money` is the drawdown in % of the account).

### Limits

- The same limits as the by-timeframe section above: no margin, TradingView's 9,000-trade report limit, the BTC-sized dollar inputs on gold, the short windows and the old gold data.
- Nothing here was compiled or run in TradingView.
