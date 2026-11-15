# Tokio732 R6 CENT — MT5 optimization package for XAUUSD and BTCUSD

Status: **not run**. `R6_CENT_100K_USC_ULTIMO_SET_1964.rar` ships only the compiled
`Tokio732_R6_CENT_100K_ULTIMO.ex5` and its 41-input preset, no `.mq5` source. An `.ex5` runs only
inside MetaTrader 5, which cannot be installed in the cloud session (the MetaQuotes download host
is blocked by the network policy), and without the source the logic cannot be ported to the
Python backtester used for `danny_phantom_calibration/`. These files are the ready-to-run
optimization setup for your own terminal.

## Files

| File | Purpose |
|---|---|
| `R6_XAUUSD_M5_optimize.set` | The 41 shipped values, with search ranges on 15 inputs |
| `R6_BTCUSD_M5_optimize.set` | Same, price and USC inputs multiplied by 16 for bitcoin |
| `tester_XAUUSD.ini`, `tester_BTCUSD.ini` | Strategy Tester settings (M5, real ticks, 2026.01.01-2026.11.13, 100000 USC, genetic, forward 1/3, recovery factor) |

## Run

1. Copy the `.ex5` to `MQL5\Experts\` and both `.set` files to `MQL5\Profiles\Tester\`.
2. In each `.ini`, change `Symbol=` if your broker's names differ from `XAUUSDc` / `BTCUSDc`.
3. Start `terminal64.exe /config:C:\path\tester_XAUUSD.ini`, then the BTCUSD one.
4. Export the optimization results (right-click, Export to XML) and the forward results and send
   them back for the robustness analysis.

## Assumptions to check

* Optimized inputs: both EMA pairs, `CrossAboveCenter`, `CrossBelowCenter`,
  `MinMoveBetweenOrders`, the three trailing inputs, `NewZonePaddingPrice`, and four switches
  (`UpdateTrendInsideBasket`, `ProtectOnlyWithTrend`, `NewZonesEnabled`, `BigCloseBeforeNews`).
  Ranges are roughly 0.5x to 2-4x the shipped value. The input meanings are inferred from their
  names; nothing here was verified against the EA's code.
* Lots, timeframes (M6), `TrendSource`, news minutes and the magic number are left as shipped.
* BTCUSD factor 16: on the July-August 2026 Octa M1 data in this repository bitcoin is 15.0x the
  gold price and its median M5 range is 15.8x gold's. `CrossAboveCenter`, `CrossBelowCenter`,
  `MinMoveBetweenOrders`, `ExitSlippageReservePrice`, `NewZonePaddingPrice` and the three
  `Trail*USC` inputs are scaled by it. This assumes a 1 BTC contract; with the bitcoin spread
  (about $17) a 0.10 lot costs about 170 USC per entry, more than the shipped 50 USC trailing arm.
* The EA has no stop loss. Rank optimization passes by drawdown and forward result, not profit.
* `LogActions` and `DashboardEnabled` are left on as shipped; turning them off speeds up passes.
