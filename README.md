# FlashGold / FlashCrypto Continuation v2

Two MetaTrader 5 expert advisors that share one tick-scalping engine:

| File | Market | Status |
| --- | --- | --- |
| `MQL5/Experts/FlashGold_Continuation_v2.mq5` | XAUUSD | Original, unchanged baseline |
| `MQL5/Experts/FlashCrypto_Continuation_v2.mq5` | BTCUSD, ETHUSD, other crypto CFDs | Crypto derivative |
| `MQL5/Include/XPW_TradeWindowFilter.mqh` | both | Shared direction/time gate (unchanged) |

Copy `MQL5/Experts/*.mq5` into your terminal's `MQL5/Experts` folder and
`MQL5/Include/XPW_TradeWindowFilter.mqh` into `MQL5/Include`, then compile in
MetaEditor. Neither file has been compiled in this repository; compile before use.

## Why gold constants do not carry over to crypto

The gold EA measures everything in broker points. On XAUUSD one point is 0.01 USD on
a price near 3,500, so its tuned constants mean roughly:

| Constant | Gold value | As a fraction of price |
| --- | --- | --- |
| Hidden stop cost floor | 47 points = 0.47 USD | 1.3 bps |
| Max entry distance | 60 points | 1.7 bps |
| Max entry spread | 50 points | 1.4 bps |
| Trailing floors | 100 / 200 points | 2.9 / 5.7 bps |
| Burst gate (fixed) | 172 points in 1 s | 4.9 bps |

On BTCUSD at 100,000 a broker point is still 0.01 USD, but the spread alone is
usually 1,000 to 5,000 points. Every gate would either block all entries or place
stops inside the spread. The crypto EA fixes this once, at the unit level, instead of
re-tuning each constant.

## What the crypto version changes

**Strategy points replace broker points.** Every distance the strategy reasons about
(cost floor, entry distance, hold move, burst, trailing floors, spread caps, friction)
is in strategy points. `InpScaleMode` picks how one strategy point is derived:

- `SCALE_PRICE_BPS` (default): `mid * InpUnitBps / 10000`. The default 0.08 bps is about
  three times the gold reference of 0.0286 bps, matching crypto's higher percentage
  volatility. On BTCUSD at 100,000 one point is 0.80 USD, so the cost floor is about
  38 USD and the max entry spread about 40 USD. On ETHUSD at 4,000 one point is 0.032 USD.
- `SCALE_FIXED_PRICE`: one point equals `InpUnitPrice` in price terms (for example 1.0 USD).
- `SCALE_BROKER_POINT`: reproduces the gold EA's geometry exactly.

A strategy point is never smaller than the broker's own point. Broker constraints
(stops level, freeze level, volume step) remain in broker units.

**24/7 market handling.** `InpUseTradingHours`, `InpTradeStartHour`, `InpTradeEndHour`
(server time, wraps midnight), `InpTradeSaturday` and `InpTradeSunday` gate new entries
only. Open positions are always managed. Defaults leave the market fully open.

**Margin-aware sizing.** Crypto CFDs often run 1:2 to 1:10 leverage, so a 1 percent
risk lot can exceed usable margin. `InpMaxMarginUsePct` (default 50) caps the new
position's margin at that share of free margin, shrinking the lot to the volume step or
blocking it with a `MARGIN_CAP_BLOCK` log line when even the minimum lot does not fit.

**Time stop.** `InpMaxHoldSeconds` (default 0, off) closes an own position after that
many seconds, tagged `EXIT_TIME` in the exit attribution telemetry, so a stalled scalp
does not sit through swap or funding rollover.

**Defaults changed for crypto.** Magic number 26090777 (gold keeps 26090555, so both
can run in one terminal). Fixed lots 0.01 and lot cap 1.0 because one lot is usually
one coin. Minimum spread floor is now `InpMinSpreadPoints` = 10 strategy points
(replacing the 1 pip input). Master telemetry prefix is `XPW_CRYPTO_`. Continuation
filter audit unit defaults to one strategy point (`InpCPPriceUnit` = 0) with looser
feed-liquidity thresholds (1 tick/s, 1000 ms median gap).

**Unchanged.** Entry and exit logic, virtual stop and trailing math, risk-percent
sizing, the Continuation v2 filter, the XPWF gate, and both inherited telemetry
modules. The telemetry CSV `*_points` columns from LegAsymmetry and ExitAttribution
stay in broker points.

## Calibration checklist before going live

1. Attach to the target symbol on a demo account and read the `CRYPTO_SCALE` line in
   the Experts log. It prints the strategy point in price, broker points per strategy
   point, the live spread in strategy points, and the cost floor and max entry distance
   in price. The live spread must sit comfortably below `InpMaxEntrySpreadPoints`
   (default 50) or no entry will ever arm. Adjust `InpUnitBps` until it does.
2. Check the Continuation CSV (`MQL5/Files/CP_*.csv`) for your broker's real tick rate
   and median quote gap, then set `InpCPMinTickRate60` and `InpCPMaxMedianGapMs` from
   the observed distribution. The shipped values are placeholders.
3. Check `BROKER_PROFILE` for `volume_min`, `volume_step` and leverage. Set
   `InpMaxLots` to a sensible coin count for the account.
4. If the broker widens spreads massively at weekends, disable `InpTradeSaturday` and
   `InpTradeSunday`, or restrict hours.
5. Back-test in the Strategy Tester with real ticks. `OnTester` reports net points per
   trade against the provisional cost floor, now in strategy points at each trade's
   own price level.
