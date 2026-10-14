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
                         top10_per_strategy.csv         (the 30 screened configs these scripts were built from)
                         all_configs_PF_1.35_plus.csv   (every screened config with PF >= 1.35)
                         ledgers/<engine>_<rank>.csv    (the trade-by-trade ledger of each base re-run)

How each script was built
  1. Your pasted strategy source, byte for byte (_diffs/base_*.pine is that source; every script's .diff is against it).
  2. The input DEFAULTS of the tested configuration are written into the input.* calls, so the script opens with the
     screened settings already loaded. Nothing else in the logic was touched.
  3. strategy() costs set for a VT cent lot on a TradingView XAUUSD chart (1 contract = 1 oz):
        default_qty_value = 0.1            0.10 cent lot = 0.1 oz
        commission_type   = strategy.commission.cash_per_contract
        commission_value  = 0.30           USD per contract per side = VT 0.60 round trip per lot
        slippage          = 10             ticks per side: about half of the 13-tick VT spread plus ~3 ticks execution
                                           (TradingView fills at one price series; it has no bid/ask, so the spread
                                           has to be charged through slippage)
     Quantity inputs: Fixed 0.1 contracts; quantity step 0.01 in FlashGold and v2.8 (the shipped FlashGold step of 1 would have
     rounded 0.1 down to 0 = no trades), 0.001 in v0.9.2 (author default, fine). Spread inputs 13 pts.
     Direction filter (FGF) off in all 30, as in the screen.
     ShapeMap v0.9.2: 'Enter on tick' set to false. The replay decided every signal on the CLOSED candle and used ticks only
     for fills and stops; with the author's default (true) the LIVE script would enter on unconfirmed intrabar signals.
     The historical tester is unaffected either way.
     Orientation v2.8: margin_long = margin_short = 1 added, so TradingView's default 100% margin never silently caps the
     20-entry stack (0.1 oz x 20 x ~4100 USD = ~8.2k notional on a 10k account); the replay had no equity cap.
  4. A header comment at the top of every script (in FlashGold directly above strategy(), after the author's original
     BTCUSD comment block, which still describes the author's own calibration) repeats the settings, the screen numbers, the stress numbers and the warnings.

CHECK THE TICK SIZE FIRST
  Every point-denominated input (spread 13 pts, slippage 10 ticks, Points-mode SL / TP / trail) assumes mintick 0.01 as on
  VT XAUUSD-ECNc. On a TradingView gold symbol quoted to 3 decimals (mintick 0.001) they are 10x too small: OTDI28_02-06 and
  SM92_03 (Points-mode exits) would run too tight: OTDI28_02-06 (SL 10000 pts) with a 10 USD stop
  instead of 100, SM92_03 (SL 7000 pts) with 7 USD instead of 70. Multiply those inputs and strategy() slippage by
  10 on such a symbol. Also confirm 1 contract = 1 oz (syminfo.pointvalue = 1) and that the List of Trades shows qty 0.1 on
  the first fill; if TradingView rounds a 0.1-contract order away, use quantity 1 and divide every USD result by 10.

Re-run with commission and slippage (stress/)
  Every config was re-run in its replay engine on the same VT XAUUSD-ECNc July 2026 bid/ask ticks with the cost applied
  IN THE ENGINE (fills worsened by N ticks per side, commission per side):
     c0.30_s0   VT actual: 0.30 per lot per side, real spread, no extra slippage   -> reproduces the screen exactly
     c0.30_s2 / s5 / s10   plus 2 / 5 / 10 ticks of slippage per side on every fill
     c0.60_s0   commission doubled (1.20 round trip per lot)
     c0.60_s5 / s10        doubled commission plus 5 / 10 ticks per side  (s10 = worst level)
  21 of 30 keep PF >= 1.35 at the worst level. The nine that fall below: FlashGold ranks 3-6, 8-10; ShapeMap ranks 9-10.
  Slippage does not lower the net uniformly: the largest rises (FlashGold 1-2 at 10 ticks, about +1.9 USD) come with the
  trade count falling by one (a 0.10 USD shift in a stop level moved one fill past a signal bar and one losing trade
  vanished); a few smaller rises happen with the trade count unchanged because slipped fills shift the stop and target
  levels by a few ticks. All of it is tick-timing sensitivity, not a benefit of slippage.

Before trusting any of these
  - All 30 are a FOUR-WEEK SCREEN (July 2026, gold has a six-day hole), 15-275 trades, no held-out block, no second
    month. They are candidates, not calibrated settings. The locked v8 protocol showed what a held-out test does to
    one-month winners.
  - TradingView's XAUUSD feed (OANDA, FXCM, ...) is not VT's tick feed. Signals and fills will differ; use the TV
    strategy tester to see if the pattern survives on another feed, not to confirm these numbers.
  - Orientation v2.8: the replay had no Day / Week / Month bars, the seconds rungs were off and every rung started cold
    on 1 July. On TradingView all 13 rungs are live and the 1 Month rung orients the ladder, so the screened result is NOT
    reproducible there; the ten OTDI28 scripts carry the tested inputs, not a reproducible backtest. Its nets are large because it stacks up to 20 entries
    of 0.10 lot; drawdowns scale the same way (43 USD on rank 1).
  - FlashGold v5 runs with autoTf zones (chart, 2x, 4x) and the 3-bar stop-entry validity, as in the screen.
  - ShapeMap v0.9.2 scripts still run calc_on_every_tick (for stops and trails); signals are taken on the closed candle.
  - Known engine-vs-Pine gaps that can move single trades: TradingView fills on bar OHLC (no tick path), so the tight v0.9.2
    trails (0.2 ATR / 100 pts) will differ; v0.9.2 ATR-mode exits use the signal candle's ATR in Pine and the next candle's
    ATR in the replay; SM92_05 (CONT stop) can keep a reversing stop working in Pine where the replay cancelled it after 3
    candles; the replay force-closed the last open position at the end of the data (counted as a trade), TradingView does not.
  - FG5_03 / FG5_05 / FG5_06 / FG5_08 share one 58-trade signal set (identical entries) with different exits; FG5_05 and
    FG5_06 are identical trades (the trailing stop in FG5_05 never acted in July). FG5_09 (M15) is a different signal set
    that also has 58 trades. FG5_09 (PF 1.22) and SM92_10 (PF 1.33) are below PF 1.35 even at actual costs.
