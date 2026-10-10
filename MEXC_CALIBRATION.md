# XPW Breakout v2.11: MEXC cost calibration

Script: `xpw_breakout_v2.11_btcusdt_mexc.pine`. Logic is v2.10 unchanged; only the
cost model (group "2. Costs"), the `strategy()` header, the qty step and the
table row 1 changed. Calibrated on 10 Oct 2026 against the BITGET:BTCUSDT exports
(5m, 10m, 15m, 30m, 45m, 60m, 365 bars each after merging the three uploads,
25 Sep to 10 Oct 2026).

## 1. Fee schedule used

| Preset | Maker | Taker | Modelled per side | Slippage per side | Source |
|---|---|---|---|---|---|
| MEXC Futures (web/app), default | 0.00 % | 0.01 % | 0.01 % | 4 USD | MEXC fee announcements of 1 May and 1 Jun 2026 ("web/app BTCUSDT futures: maker 0 %, taker 0.01 %") |
| MEXC Futures (API bot) | 0.06 % | 0.08 % | 0.08 % | 8 USD | Same announcements: API orders maker 0.06 % / taker 0.08 % from 1 Jun 2026 (0.04 / 0.06 in May) |
| MEXC Spot | 0.00 % | 0.05 % | 0.05 % | 4 USD | MEXC fee page and 2026 fee guides. MX-token deduction can halve the taker leg; not modelled |

Why the taker rate on both legs: on MEXC a stop order triggers a market order, so
the entry, the SL, the trail stop and the breakeven stop are all taker fills. Only
the TP limit is a maker fill. TradingView charges one rate per fill, so the
backtest is pessimistic by (taker minus maker) on TP exits only: 0.01 % of
notional, about 8 USD per BTC, with the default preset.

Fee caveats that the user has to confirm on their own account:
- The 0.01 % taker rate is the BTCUSDT special rate for web/app orders. MEXC has
  moved selected regions (CIS, Ukraine, Aug 2026) to 0.01 % maker / 0.04 % taker.
  If the account's fee page shows 0.04 %, use "Custom" with 0.04.
- A TradingView-alert-to-webhook bot sends API orders and pays the API schedule.
  That is 8 to 13 times the web/app cost; the API preset exists for that case.

## 2. Slippage

Measured from the exports: average price velocity on breakout bars (close beyond
the prior 20-bar extreme) is 0.16 to 0.25 USD/s at the bar level across 5m..60m,
and several times that during the breakout burst itself. Components per side:

| Component | USD per BTC | Note |
|---|---|---|
| Half spread, MEXC BTC perp | 0.05 to 0.25 | tick 0.1, spread usually 1 to 5 ticks |
| Book walk below 1 BTC | < 0.5 | TokenInsight Sept 2026: 21 M USD BTC+ETH depth inside 0.03 % |
| Trigger latency, web/app (about 1 s) | 2 to 4 | breakout burst velocity |
| Trigger latency, alert + webhook + API (2 to 3 s) | 5 to 10 | |

Rounded to 4 USD per side (web/app) and 8 USD per side (API). In header ticks:
400 / 800 on a 0.01-tick chart (BITGET:BTCUSDT spot), 40 / 80 on a 0.1-tick chart
(MEXC:BTCUSDT.P). The table row "Header slippage should be" prints the right number
for the chart you are on.

## 3. Round-trip cost at 83 000 USD

- Futures web/app: commission 16.6 USD + slippage 8.0 USD = 24.6 USD per BTC round trip (0.030 % of price)
- Futures API bot: commission 132.8 USD + slippage 16.0 USD = 148.8 USD per BTC round trip (0.179 % of price)
- Spot: commission 83.0 USD + slippage 8.0 USD = 91.0 USD per BTC round trip (0.110 % of price)

For reference, v2.10's VT Markets CFD header was 21 USD commission + 10 USD
slippage = 31 USD per round trip, so the default MEXC preset is about 20 % cheaper
than the CFD calibration and the geometry defaults carry over unchanged.

## 4. Cost against the ATR geometry on the exports

SL = 3 ATR, net TP = 9 ATR (TpR 3). Cost shown as percent of the net TP at the
median ATR and at the 10th percentile ATR (quiet hours). Break-even win rate is for
the default preset with TP widening on.

| TF | bars | window (UTC-4) | median ATR14 | p10 ATR14 | SL 3 ATR | net TP 9 ATR | web/app cost % TP (med / p10) | API cost % TP (med / p10) | Spot cost % TP (med / p10) | web/app break-even win % |
|---|---|---|---|---|---|---|---|---|---|---|
| 5m | 365 | 2026-10-09T10:10 .. 2026-10-10T16:30 | 40 | 26 | 121 | 362 | 6.8 / 10.5 | 41.0 / 63.7 | 25.1 / 38.9 | 28.6 |
| 10m | 365 | 2026-10-08T03:50 .. 2026-10-10T16:30 | 124 | 52 | 371 | 1113 | 2.2 / 5.2 | 13.3 / 31.3 | 8.1 / 19.2 | 26.2 |
| 15m | 365 | 2026-10-06T21:30 .. 2026-10-10T16:30 | 190 | 76 | 570 | 1710 | 1.4 / 3.6 | 8.7 / 21.8 | 5.3 / 13.3 | 25.8 |
| 30m | 365 | 2026-10-03T02:30 .. 2026-10-10T16:30 | 260 | 105 | 780 | 2341 | 1.1 / 2.6 | 6.4 / 16.0 | 3.9 / 9.8 | 25.6 |
| 45m | 365 | 2026-09-29T07:15 .. 2026-10-10T16:15 | 348 | 162 | 1044 | 3131 | 0.8 / 1.7 | 4.8 / 10.3 | 2.9 / 6.3 | 25.4 |
| 60m | 365 | 2026-09-25T12:00 .. 2026-10-10T16:00 | 390 | 201 | 1170 | 3509 | 0.7 / 1.4 | 4.3 / 8.3 | 2.6 / 5.1 | 25.4 |

Reading:
- With the default preset the 20 % cost gate never closes on 5m..60m. Costs are
  below 2 % of TP from 15m up; 5m is the only timeframe where cost is a visible
  fraction of the target.
- With the API preset the gate shuts 5m off entirely (41 % of TP at the median
  ATR) and closes 10m during quiet hours (31 %). That is the right behaviour: a
  webhook bot paying 0.08 % per side cannot trade 5m BTC breakouts with this
  geometry.
- The spot preset is cost-viable from 15m up but spot has no shorts: set
  Direction = Long. The table flags Spot + shorts in red.

## 5. Funding (not modelled)

MEXC perps settle funding every 8 h. At a typical 0.01 % per interval that is
about 8 USD per BTC, a third of the default round trip. A 60m trade with the 3 ATR
stop can run 10 to 30 bars, so one or two intervals per trade are normal. Use the
time stop (group "9. Exits") if you want to bound it; the tester cannot see
funding either way.

## 6. Properties checklist (TradingView)

1. Properties > Commission: 0.01 %, type percent (API: 0.08 %, Spot: 0.05 %).
2. Properties > Slippage: 400 ticks on a 0.01-tick chart, 40 on a 0.1-tick chart
   (API preset: 800 / 80). Read the table row "Header slippage should be".
3. A chart that carried v2.10 or v2.01 keeps the old cash commission and slippage
   in Properties. Do Properties > Defaults > Reset settings first.
4. The table row "Commission charged / modelled" goes red when Properties and the
   preset disagree. It cannot check slippage, only commission.
5. Qty step 0.0001 (one MEXC perp contract). FixedQty 0.01 BTC.

## 7. Sources

- MEXC, "Updates to API Futures Trading Fees (May 1, 2026)": https://www.mexc.com/announcements/article/updates-to-api-futures-trading-fees-may-1-2026-17827791535194
- MEXC, "Updates to API Futures Trading Fees (Jun 1, 2026)": https://www.mexc.com/announcements/article/updates-to-api-futures-trading-fees-jun-1-2026-17827791535742
- MEXC fee guide (spot 0 / 0.05 %): https://www.mexc.com/crypto-pulse/article/mexc-trading-fees-complete-guide-39643
- MEXC Futures contract info (contract size 0.0001 BTC): https://www.mexc.com/api-docs/futures/market-endpoints/get-contract-info
- TokenInsight September 2026 liquidity report (BTC+ETH futures depth): https://bitcoinist.com/tokeninsight-september-report-mexc-posts-deepest-btc-and-eth-futures-depth-at-21-03m-lowest-silver-slippage-at-0-002/amp/

mexc.com is not reachable from this environment, so the fee figures come from
search excerpts of those pages, not from the live fee page. Confirm the rate on
the account's own fee page before going live.
