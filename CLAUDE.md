# Trading scripts: TradingView (Pine Script) and MetaTrader 5 (MQL5)

This repo holds TradingView indicators and strategies and MT5 Expert Advisors
and indicators for the XPW and FlashGold systems, mostly on XAUUSD and BTCUSD.

## Read before writing code

| Working on | Read first |
|---|---|
| any `.pine` file | [docs/rules/pine.md](docs/rules/pine.md) |
| any `.mq5` / `.mqh` file | [docs/rules/mql5.md](docs/rules/mql5.md) |
| any backtest, calibration or result claim | [docs/rules/validation.md](docs/rules/validation.md) |
| finding a script or its latest version | [docs/INVENTORY.md](docs/INVENTORY.md) |

## Systems

- **XPW Orientation TDI**: TDI (RSI → fast/slow SMA) direction strategy. Latest
  version is v2.8, with an `_FGF` build.
- **FlashGold v5**: TDI continuation with a parent zone plus six child zones,
  a burst gate, prior-drift filter and entry hold. XAUUSD and BTCUSD builds.
- **FlashGold Direction Filter (FGF) v1.2**: a level filter that the `_FGF`
  builds fuse in (buy only above the level, sell only below it).
- **XPW Shape Map, XPW Breakout, Asia–London Breakout, RegimeTrend,
  Directional Time Filter**: see the inventory.

## Ground rules

- No repainting and no lookahead on either platform. Signals read closed bars.
- The Pine strategy and the MQL5 EA for the same system keep the same logic and
  version number. Each header lists the fill-model differences.
- No result is quoted without the worst-case and with-costs numbers next to it.
- A new version is a new file. Calibrate it before retiring the old one.
- Most work still sits on unmerged `claude/*` branches (see the inventory).
  Before starting on a script, check which branch has its newest copy.
