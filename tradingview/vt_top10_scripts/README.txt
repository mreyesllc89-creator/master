VT MARKETS XAUUSD-ECNc  -  TOP 10 PER STRATEGY  -  ONE TRADINGVIEW SCRIPT PER CONFIG
====================================================================================

What is in this zip
  FlashGold_v5/          10 scripts  (Pine v5)   FG5_<rank>_<tf>_<settings>.pine
  ShapeMap_v0.9.2/       10 scripts  (Pine v6)   SM92_<rank>_<tf>_<settings>.pine
  Orientation_TDI_v2.8/  10 scripts  (Pine v6)   OTDI28_<rank>_<tf>_<settings>.pine
  manifest.json          every script with its strategy, timeframe, settings label, the input defaults that were
                         hard-coded, and the screen numbers
  _diffs/                base_<FG5|SM92|OTDI28>.pine = your strategy source assembled unchanged; one .diff per script
                         showing exactly which lines differ from it (header comment, strategy() costs, input defaults)
  stress/                top30_stress_results_long.csv  (30 configs x 7 cost levels, one row each)
                         top30_stress_results_wide.csv  (one row per config, net / PF / trades per level, robustness flags)
                         top30_stress_summary.md        (same, as tables)
                         ledgers/<engine>_<rank>.csv    (the trade-by-trade ledger of each base re-run)

How each script was built
  1. Your pasted strategy source, byte for byte (the three strategies reassemble identically from the stored parts).
  2. The input DEFAULTS of the tested configuration are written into the input.* calls, so the script opens with the
     screened settings already loaded. Nothing else in the logic was touched.
  3. strategy() costs set for a VT cent lot on a TradingView XAUUSD chart (1 contract = 1 oz):
        default_qty_value = 0.1            0.10 cent lot = 0.1 oz
        commission_type   = strategy.commission.cash_per_contract
        commission_value  = 0.30           USD per contract per side = VT 0.60 round trip per lot
        slippage          = 10             ticks per side: about half of the 13-tick VT spread plus ~3 ticks execution
                                           (TradingView fills at one price series; it has no bid/ask, so the spread
                                           has to be charged through slippage)
     Quantity inputs: Fixed 0.1 contracts, quantity step 0.01 (so 0.1 does not round down to 0). Spread inputs 13 pts.
     Direction filter (FGF) off in all 30, as in the screen.
  4. A header comment at the top of every script repeats the settings, the screen numbers and the warnings.

Re-run with commission and slippage (stress/)
  Every config was re-run in its replay engine on the same VT XAUUSD-ECNc July 2026 bid/ask ticks with the cost applied
  IN THE ENGINE (fills worsened by N ticks per side, commission per side):
     c0.30_s0   VT actual: 0.30 per lot per side, real spread, no extra slippage   -> reproduces the screen exactly
     c0.30_s2 / s5 / s10   plus 2 / 5 / 10 ticks of slippage per side on every fill
     c0.60_s0   commission doubled (1.20 round trip per lot)
     c0.60_s5 / s10        doubled commission plus 5 / 10 ticks per side  (s10 = worst level)
  21 of 30 keep PF >= 1.35 at the worst level. The nine that fall below: FlashGold ranks 3-6, 8-10; ShapeMap ranks 9-10.
  Where the net RISES with slippage (FlashGold 1-2 at 10 ticks) the trade count changed: a 0.10 USD shift in a stop
  level moved one fill past a signal bar and one losing trade vanished. That is tick-timing sensitivity, not a benefit.

Before trusting any of these
  - All 30 are a FOUR-WEEK SCREEN (July 2026, gold has a six-day hole), 15-275 trades, no held-out block, no second
    month. They are candidates, not calibrated settings. The locked v8 protocol showed what a held-out test does to
    one-month winners.
  - TradingView's XAUUSD feed (OANDA, FXCM, ...) is not VT's tick feed. Signals and fills will differ; use the TV
    strategy tester to see if the pattern survives on another feed, not to confirm these numbers.
  - Orientation v2.8: the replay had no Day / Week / Month bars, so those three rungs were empty. On TradingView they
    are populated and the ladder (and the trades) will change. Its nets are large because it stacks up to 20 entries
    of 0.10 lot; drawdowns scale the same way (43 USD on rank 1).
  - FlashGold v5 runs with autoTf zones (chart, 2x, 4x) and the 3-bar stop-entry validity, as in the screen.
  - ShapeMap v0.9.2 scripts run on every tick (calc_on_every_tick); the replay did the same.
