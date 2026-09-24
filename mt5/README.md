# XPW Breakout for MT5

MQL5 port of `pine/XPW_Breakout_v2.10_*.pine`, built in six steps. Each step is
a working EA that runs in the Strategy Tester before the next one lands.

| Step | Content | Status |
|---|---|---|
| 1 | Skeleton: presets, ATR + confirmed pivots on closed bars, stop straddle with attached SL/TP, buffer-arms latch, OCA, panel | in repo (`XPW_Breakout.mq5`, v0.10) |
| 2 | Cost model, TP widening, risk sizing, deal-history commission referee | next |
| 3 | Hard/soft gates, MaxDist, loss cap per level, cooldown, day cap, session | |
| 4 | Trail, breakeven, time stop on every tick | |
| 5 | Donchian + previous-day levels, CloseConfirm + Retest triggers | |
| 6 | Panel polish, tick-mode arming, alerts | |

## Compile and run step 1

1. MetaEditor > File > Open, pick `mt5/XPW_Breakout.mq5`, press F7. It uses only
   the standard `Trade` library. If the compiler reports anything, paste the
   Errors tab back into the chat.
2. Strategy Tester: symbol XAUUSD or BTCUSD, the timeframe you exported (the
   gold defaults were swept on 10m to 240m OANDA data; 30m or 60m is the
   steadiest), model **Every tick based on real ticks**, preset input set to
   the symbol. Leave lots at 0 to take the preset default (0.10).
3. Compare the tester's trade list with the Pine build on the same symbol and
   timeframe in Execution = BarClose, ArmLatch on, pivot levels only, trail off
   (step 1 has no trail yet; set UseTrail off in Pine for the comparison), cost
   gate off, TP widening off, cost sizing off. Entry prices should match to the
   spread and fill quality; the bar of each entry should match exactly.

## What step 1 deliberately leaves out

- No trail, breakeven or time stop: the position exits on the attached SL/TP.
- No cost gate, TP widening or risk sizing: fixed lots.
- No filters (session, trend, cooldown, day cap, loss cap).
- Decisions once per bar on the closed bar. Orders rest and fill on ticks,
  which is what the Pine build could only approximate.

## Notes

- Presets carry the VT Markets figures from the account holder: BTCUSD spread
  about 2,100 points ($21), no commission; XAUUSD spread 2.5 pips ($0.25),
  commission $0.6 per lot. They are informational in step 1.
- The broker's `SYMBOL_TRADE_STOPS_LEVEL` is respected: a level closer to the
  current price than the stop level is not armed.
- The EA identifies its own orders and positions by magic number and symbol,
  so one chart per symbol with a different magic is fine.
