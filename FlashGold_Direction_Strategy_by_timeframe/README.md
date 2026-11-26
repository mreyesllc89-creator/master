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

The calibration of this file, with the direction as an input, is a separate run.
