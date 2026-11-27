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

The calibration of this file, with the direction as an input, is a separate run.
