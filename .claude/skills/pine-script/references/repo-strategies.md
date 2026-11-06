# The strategies in this repository

| File | What it is |
|------|------------|
| `FlashGold_v5_Strategy_BTCUSD.pine` | Strategy conversion of the "FlashGold Continuation v5 - TDI Trade Zone Filter" indicator (© ghostsmartfire). BTCUSD calibration. |
| `FlashGold_v5_Strategy_BTCUSD_FGF.pine` | Same, plus the FlashGold Direction Filter block (`// ===== BEGIN FLASHGOLD DIRECTION FILTER =====`). |
| `FlashGold_Direction_Filter_v1_2.pine` | Indicator: the FlashGold signal used only as BUY ZONE / SELL ZONE / NO TRADE permission for other strategies. |
| `xpw_orientation_tdi_v2.4_strategy.pine` | XPW Orientation TDI v2.4 indicator turned into a strategy; trades the v2.4 event labels. |
| `xpw_orientation_tdi_v2.8_strategy.pine` | v2.8: any timeframe, every label can trade (enter / enter opposite / exit only), reverse option, money management groups S2/S3. |
| `xpw_orientation_tdi_v2.8_strategy_FGF.pine` | v2.8 with the FGF direction-filter block. |

"FGF" = FlashGold Filter: the direction-filter inputs (`GRP_FGF = "Direction filter"`,
variables `fgf*`) pasted as a block so a strategy only takes entries the filter allows.

## FlashGold v5 logic (kept from the indicator, "unchanged")
- **Bid/ask model** from `spreadPoints` (half the spread each side of the single series).
- **TDI direction**: `ta.rsi(close, tdiRsiLen=14)` → `ta.sma(rsi, tdiFastLen=2)` (white,
  fast) and `ta.sma(rsi, tdiSlowLen=7)`; fast rising = BUY.
- **Zone alignment filter**: a parent timeframe (`tdiParentTf`, default 60, or the chart
  with `autoTf`) and six child zones (chart, 2x, 4x the chart when `autoTf`); need
  `minAlignedZones` children agreeing with the parent; `allowNeutralParent`,
  `ignoreNaZones`, `htfNoRepaint` (lookahead_on + [1]).
- **Burst gate**: a move of `burstAtrMult × ATR(14)` (or `burstPointsInput` points),
  `useAnyCombo`, `usePriorFilter` over `priorDriftBars`.
- **Entry hold** (virtual stop) `entryHoldBars`, `entryHoldMinFavPoints`; **one entry per bar**.
- **Entry price**: ask + entry distance (buy) / bid − entry distance (sell) placed as a
  **stop order**; distance in ATR multiple (`entryDistAtrMult`) or points.

## Strategy additions (groups S1..S3)
- **S1 Entries**: `Direction` Both/Long/Short; `entryValidBars` cancels the unfilled stop;
  `allowReverse`; `exitOnOpposite`.
- **S2 Exits**: `ExitMode` Pips/ATR/Points; `pipSize` (BTC: 1 pip = $1); SL (`slPips` 30,
  `slAtrMult` 0.1, `slPoints` 3900); TP as R multiple (`tpRPips` 5, `tpR` 2) or `tpPoints`;
  `useTrail` with activation/distance; `maxBarsHeld` time stop; `TpStyle` Fixed or
  Partial + runner (`partPct` 30, `runBE`, `runTrailAtr` 1.5, `runTrailPts`, `runTrailPips` 600).
- **S3 Sizing**: `QtyMode` Fixed (`fixedQty` 10 BTC) or Risk %.
- Tooltips carry the calibration ("Calibrated: 0.1. Tested range 0.08 to 0.12, all
  positive"); respect them when proposing new defaults and record new calibrations the
  same way.

## XPW Orientation TDI (v2.4 → v2.8)
- A "ladder" of 13 timeframe rungs (1 Sec … 1 Month); the chart rung is `*`, the READ
  HERE rung `<<`. Labels: 1st/2nd LEG ENTER LONGS/SHORTS, DIVERGENCE LONG/SHORT ZONE,
  END 2nd LEG, Info "look for X"/"continue".
- v2.8: `Signal rung` input (chart rung / every rung / a fixed rung); each label row has
  show, colour and TRADE action (off / enter / enter opposite / exit only); "Reverse every
  label"; order comments name the rung and the label; `pyramiding=100`,
  `process_orders_on_close=true`, `calc_on_every_tick=true`.
- Heavy use of arrays (`array.from`, `array.get/set/push/remove`) for the rung map and
  label rows, `request.security` per rung (watch the 40-call limit), tables for the zone
  display.

## Conventions when editing
- Header block: title line with version, dashed rule, prose explaining what is kept from
  the indicator and what the strategy adds, then a per-version "what changed" list. Add
  a new version entry at the top of that list; never rewrite old entries.
- Inputs: `group = gXxx` constants, `tooltip` on anything non-obvious, "STRATEGY
  ADDITION." prefix for behaviour the source indicator lacks, options as strings matched
  with `==`.
- Keep the indicator's calculation blocks intact ("line for line"); put strategy logic
  after them.
- Labels use `labelTimeZone` (default `America/New_York`) via `str.format_time`.
- Both an `_FGF` and a plain version exist for the same strategy: apply a core fix to
  both files, and keep the FGF block identical across files that carry it (diff them).
- Filenames: `Name_vX_Y_Strategy_SYMBOL[_FGF].pine`; versions in the header and the
  `strategy()` title.
