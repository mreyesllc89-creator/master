# Indicators and cross-platform parity

`scripts/indicators.py` implements everything below with pandas; run
`python scripts/indicators.py --selftest` to check it.

## Smoothing primitives
| Name | Pine | MT5 | pandas |
|------|------|-----|--------|
| SMA | `ta.sma(x, n)` | `iMA(..., MODE_SMA)` | `x.rolling(n).mean()` |
| EMA | `ta.ema(x, n)` | `iMA(..., MODE_EMA)` | `x.ewm(span=n, adjust=False).mean()` (Pine seeds with SMA) |
| RMA / Wilder | `ta.rma(x, n)` | smoothing inside RSI/ADX | `x.ewm(alpha=1/n, adjust=False).mean()` seeded with SMA of first n |
| WMA | `ta.wma` | `MODE_LWMA` | weights `1..n` dot product |
| Stdev | `ta.stdev(x, n)` (population) | `iStdDev` (population) | `x.rolling(n).std(ddof=0)` |

Pine EMA/RMA seed: the first value is the SMA of the first `n` values, then the recursion.
pandas `ewm(adjust=False)` seeds with the first observation. The two differ for the first
few hundred bars; use the SMA-seeded implementation in the script when parity matters.

## RSI (Wilder)
```
gain = max(close - close[1], 0); loss = max(close[1] - close, 0)
avgGain = rma(gain, n); avgLoss = rma(loss, n)
rsi = 100 - 100 / (1 + avgGain / avgLoss)   (100 when avgLoss == 0)
```
Pine `ta.rsi` and MT5 `iRSI` agree on this. Default here: `n=14` (`tdiRsiLen`), applied to close.

## TDI (Traders Dynamic Index) as these strategies use it
- `rsi = RSI(close, tdiRsiLen=14)`
- `fast = SMA(rsi, tdiFastLen=2)` (the "white" line), `slow = SMA(rsi, tdiSlowLen=7)`
- Direction: fast rising (`fast > fast[1]`) = BUY, falling = SELL, equal = flat/MIX.
- The zone filter evaluates this direction on a parent timeframe and six child
  timeframes; a child "agrees" when its direction equals the parent's. The strategy needs
  `minAlignedZones` children agreeing with a non-flat parent.
- The classic TDI also has volatility bands (Bollinger on RSI, length 34, 1.6185 std) and a
  market base line (SMA 34); these scripts do not use them, so do not add them unless asked.

## ATR
- Pine `ta.atr(n)` = `rma(tr, n)` with `tr = max(high-low, |high-close[1]|, |low-close[1]|)`.
- MT5 `iATR(n)` = **simple** moving average of `tr` (MetaQuotes' ATR.mq5). Values differ
  from Pine by a few percent in trending volatility. Port the Pine behaviour to MQL5 by
  hand when you need the same stop distances.
- First bar: `tr = high - low` (no previous close).

## Highest / lowest / cum
- `ta.highest(x, n)` = `x.rolling(n).max()`; `ta.lowest` likewise. These scripts use them
  for burst and drift measurements.
- `ta.cum(x)` = `x.cumsum()`.

## Units
- **Point** (MT5 `_Point`, Pine `syminfo.mintick`): smallest price increment.
  BTCUSD with 2 decimals → 0.01; XAUUSD typically 0.01; EURUSD 0.00001.
- **Pip**: a convention, not a symbol property. The BTCUSD strategy defines 1 pip = $1
  (`pipSize` input). Forex 5-digit pairs: pip = 10 points.
- **ATR multiple**: unit-free, portable across symbols; the strategies' "calibrated form".
- Convert: `price_distance = points * point_size`; `points = price_distance / point_size`.

## Validation recipe
1. Export the indicator values from the platform (TradingView: chart → export data;
   MT5: a tiny script writing `CopyBuffer` output to CSV).
2. Load both into pandas on a UTC index; `np.testing.assert_allclose(a, b, atol=tick/2)`
   after dropping the first `5*n` bars.
3. If they disagree, check in order: timezone/alignment, smoothing seed, SMA vs RMA ATR,
   applied price (close vs typical price), and whether the platform value is from the
   closed bar or the forming bar.
