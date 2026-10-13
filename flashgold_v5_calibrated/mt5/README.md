# FlashGold v5 for MetaTrader 5: one preset per calibrated setting

`FlashGold_v5.mq5` is the September MT5 port (v0.10, unchanged, from branch
`claude/confident-einstein-uzfabw`). It already takes every parameter the TradingView sweep used,
so the calibrations ship as 23 preset files in `presets/`, not as code changes. Each file is the
best cell of the exit sweep for one export, the same cell as the matching Pine script in
`../` (VT Markets costs) and `../mexc/` (MEXC percent fee, 0.1 % risk).

Nothing here was compiled or run: this environment has no MetaEditor and no Strategy Tester.
Compile `FlashGold_v5.mq5` with F7 first; if the Errors tab reports anything, send it to me.

## How to use a preset

1. Copy `FlashGold_v5.mq5` to `MQL5\Experts`, compile it, copy the `.set` files to `MQL5\Presets`.
2. Open the chart for the symbol and the timeframe in the file name (M15, M30, H1).
3. Attach the EA, Inputs tab, Load, pick the preset. The preset uses `InpPreset=3` (Custom) and
   `InpZoneMode=1` (manual zone list), so nothing is taken from the built-in symbol presets.
4. Strategy Tester: model "Every tick based on real ticks"; the trailing stop needs ticks.

Every preset sets the zone list explicitly, the parent is the chart, and trail activation 1.0 ATR,
distance 0.75 ATR, entry stop lifetime 3 bars and reversal on, as swept.

## Sizing and costs

- **VT presets** use fixed lots: the EA default 0.10 lot. That equals the Pine fixed quantity for
  gold (10 oz) and BTC (0.1 BTC). For SPX500 check your broker's contract size: Pine used 1
  contract at $1 per point. Set `InpLots` to taste.
- **MEXC presets** use `InpRiskPct=0.1` (0.1 % of equity per trade, sized from the ATR stop
  distance, capped by `InpMaxLots=1`).
- The EA does not charge commission. MT5 takes commission and spread from the broker's symbol
  specification, so the VT and MEXC cost assumptions only matter in how you test: use a symbol
  that carries those costs. I could not confirm that a MEXC MT5 symbol with the 0.02 % taker fee
  exists. If you trade on VT Markets, use the VT presets.

## Differences from the Pine build to expect

- MT5 has no 8m, 40m or similar timeframes. Zone timeframes use the nearest MT5 timeframe at or
  above the multiple. Only SPX500 1m changed (8x = 8m becomes M10); gold 5m uses M10 and M20, which
  exist. BTC 5m and gold 10m are chart-only, so nothing changed.
- The entry stop is placed from the live Ask and Bid at the bar close, not from close plus or
  minus half the modelled spread, and the trailing stop moves on server ticks. Expect the trade
  list to differ slightly from TradingView, not the profit factor by much.
- The data is short (days to months), so each profit factor is an upper bound. The thin ones are
  XAUUSD 5m and 10m (VT) and BTCUSD 5m.

## VT Markets presets

| Preset file | Magic | Zones (chart = the chart TF) | Aligned | Signal | Dist ATR | Hold | SL ATR | TP R | Trail | Close opp | Trades | Win | PF |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FG_VT_XAUUSD_5m.set | 220101 | chart+M10+M20 | 2 | burst 1.0 | 0.25 | 0 | 3.0 | 1.5 | on | off | 37 | 76% | 1.23 |
| FG_VT_XAUUSD_10m.set | 220102 | chart | 1 | burst 0.25 | 0.25 | 3 | 1.0 | 3.0 | off | on | 70 | 36% | 1.29 |
| FG_VT_XAUUSD_15m.set | 220103 | chart+M30+H1+H2 | 3 | burst 1.0 | 0.25 | 0 | 3.0 | 1.0 | off | off | 43 | 67% | 2.15 |
| FG_VT_XAUUSD_30m.set | 220104 | chart | 1 | any combo | 0.25 | 3 | 2.0 | 3.0 | off | on | 31 | 55% | 2.61 |
| FG_VT_XAUUSD_60m.set | 220105 | chart+H2+H4 | 2 | burst 0.5 | 0.25 | 0 | 2.0 | 3.0 | on | on | 88 | 72% | 1.95 |
| FG_VT_BTCUSD_5m.set | 220106 | chart | 1 | burst 0.5 | 0.25 | 3 | 1.5 | 3.0 | on | off | 40 | 65% | 1.77 |
| FG_VT_BTCUSD_15m.set | 220107 | chart+M30+H1+H2 | 3 | burst 1.0 | 0.1 | 0 | 3.0 | 3.0 | on | on | 30 | 80% | 2.24 |
| FG_VT_BTCUSD_30m.set | 220108 | chart | 1 | burst 1.0 | 0.1 | 0 | 2.0 | 2.0 | on | off | 37 | 73% | 2.3 |
| FG_VT_BTCUSD_60m.set | 220109 | chart+H2+H4+H8 | 3 | burst 0.25 | 0.1 | 0 | 3.0 | 2.0 | off | off | 31 | 52% | 2.57 |
| FG_VT_SPX500_1m.set | 220110 | chart+M2+M4+M10 | 3 | burst 1.0 | 0.1 | 3 | 1.0 | 3.0 | on | off | 42 | 62% | 2.23 |
| FG_VT_SPX500_15m.set | 220111 | chart | 1 | burst 0.5 | 0.25 | 3 | 3.0 | 1.5 | on | off | 46 | 83% | 1.95 |
| FG_VT_SPX500_30m.set | 220112 | chart | 1 | burst 0.5 | 0.25 | 3 | 1.5 | 0.5 | on | off | 51 | 78% | 2.71 |
| FG_VT_SPX500_60m.set | 220113 | chart+H2+H4 | 2 | burst 0.5 | 0.25 | 3 | 1.0 | 0.5 | on | off | 36 | 89% | 4.96 |

## MEXC presets (percent fee, 0.1 % risk)

| Preset file | Magic | Zones (chart = the chart TF) | Aligned | Signal | Dist ATR | Hold | SL ATR | TP R | Trail | Close opp | Trades | Win | PF |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FG_MEXC_BTCUSD_5m.set | 220114 | chart | 1 | burst 0.5 | 0.25 | 3 | 1.5 | 3.0 | on | off | 44 | 57% | 1.48 |
| FG_MEXC_BTCUSD_15m.set | 220115 | chart+M30+H1+H2 | 3 | burst 0.5 | 0.25 | 0 | 3.0 | 3.0 | on | on | 52 | 83% | 2.54 |
| FG_MEXC_BTCUSD_30m.set | 220116 | chart+H1+H2 | 2 | any combo | 0.1 | 3 | 3.0 | 0.5 | on | on | 30 | 80% | 2.65 |
| FG_MEXC_BTCUSD_60m.set | 220117 | chart+H2+H4+H8 | 3 | burst 0.25 | 0.1 | 0 | 3.0 | 2.0 | off | off | 32 | 50% | 2.53 |
| FG_MEXC_XAUUSD_15m.set | 220118 | chart+M30+H1+H2 | 3 | burst 1.0 | 0.25 | 0 | 3.0 | 1.0 | off | off | 43 | 65% | 1.9 |
| FG_MEXC_XAUUSD_30m.set | 220119 | chart | 1 | any combo | 0.25 | 3 | 2.0 | 3.0 | off | on | 31 | 55% | 2.34 |
| FG_MEXC_XAUUSD_60m.set | 220120 | chart+H2+H4 | 2 | burst 0.5 | 0.1 | 0 | 3.0 | 3.0 | off | off | 52 | 40% | 1.85 |
| FG_MEXC_SPX500_15m.set | 220121 | chart | 1 | burst 0.5 | 0.25 | 3 | 3.0 | 1.5 | on | off | 46 | 78% | 1.6 |
| FG_MEXC_SPX500_30m.set | 220122 | chart | 1 | burst 0.5 | 0.25 | 3 | 1.5 | 0.5 | on | off | 51 | 78% | 2.11 |
| FG_MEXC_SPX500_60m.set | 220123 | chart+H2+H4+H8 | 3 | burst 0.25 | 0.25 | 3 | 2.0 | 1.5 | on | off | 43 | 81% | 4.39 |

Not shipped for MEXC: XAUUSD 5m and 10m and SPX500 1m, where no setting held up at MEXC fees.
