# master

Pine Script v6 strategies and the shared Directional Time Filter (DTF).

## Directional Time Filter

| File | What it is |
| --- | --- |
| `directional_time_filter_v1.4.pine` | DTF as a standalone indicator (can also be linked into a strategy through `input.source`). |
| `dtf_block_v1.4.pine` | The DTF as a paste-ready block for adding to any strategy. |

## Scripts with the DTF built in

Every script below carries the DTF block (group "Directional time filter") and gates its entries with it. Exits are never gated. Each file's header has a "DIRECTIONAL TIME FILTER" section that says exactly which orders are gated in that script.

| File | Host | How the filter is wired in |
| --- | --- | --- |
| `xpw_orientation_tdi_v2.4_strategy.pine` | XPW Orientation TDI v2.4 strategy | ENTER LONG / ENTER SHORT entries. |
| `xpw_orientation_tdi_v2.5_tick_strategy.pine` | XPW Orientation TDI v2.5 strategy, tick entry | ENTER entries, market and limit mode. |
| `xpw_orientation_tdi_v2.7_strategy.pine` | XPW Orientation TDI v2.7 strategy, every label | Every stacked ENTER entry of a bar. |
| `xpw_breakout_v2.11_mtf_strategy.pine` | XPW Breakout v2.11 MTF (XAUUSD) | One more soft gate: a blocked side lifts its resting order, the arm latch survives (Stop, CloseConfirm and Retest). The table lists "dtf" under Filters. |
| `xpw_breakout_v2.10_mtf_strategy.pine` | XPW Breakout v2.10-MTF (XAUUSD) | Same as v2.11. |
| `xpw_breakout_v2.10_strategy.pine` | XPW Breakout v2.10 (XAUUSD), no MTF labels | Same as v2.11. |
| `xpw_refusal_log_v0.3_strategy.pine` | XPW Refusal Log v0.3 strategy | FIRST LEG long / SECOND LEG short entries. The ENTER triangles only mark allowed signals. |
| `xpw_shape_map_v0.8_strategy.pine` | XPW Shape Map v0.8 strategy | Market entries, Predict stop orders and catch-up entries. |
| `xpw_shape_map_v0.6_strategy.pine` | XPW Shape Map v0.6 strategy | Market entries and Predict stop orders. |
| `tdi_plus_enhanced_btcusd_strategy.pine` | TDI+ (Enhanced) strategy, BTCUSD | The two `strategy.entry` calls. |
| `flashgold_v5_xauusd_strategy.pine` | FlashGold v5 strategy, XAUUSD (Pine v5) | The two stop-order placements. The block is the v1.4 block without its `force_overlay` arguments, since this script is Pine v5 and draws on the price chart. |
| `xpw_shape_map_v0.6_indicator.pine` | XPW Shape Map v0.6 indicator (map only) | Nothing to gate: the block is a display layer and exports "DTF buy allowed" / "DTF sell allowed". |

The block ships with the filter ON and nothing armed, so every entry is blocked until you arm it (ACTIVATE NOW or Start time) or switch "Enable filter" off. ACTIVATE NOW re-arms on every reload of the script, so use Start time for anything left running or driven by alerts.

All scripts are Pine v6 except FlashGold, which is Pine v5 and carries the same block with the `force_overlay` arguments removed.

Scripts that run in their own pane (the TDI and Shape Map ones) draw the filter's shading, level and status box on the price chart. Where the host already has a table in the top right corner (Breakout, Refusal Log, TDI+), the DTF status box defaults to the top left; change it under "Status box position".

## Adding the Directional Time Filter to another strategy

1. Open `dtf_block_v1.4.pine` and copy everything between the `BEGIN DIRECTIONAL TIME FILTER` and `END DIRECTIONAL TIME FILTER` markers.
2. Paste it into the strategy below its own inputs, anywhere above the entry orders.
3. Set `DTF_FORCE_OVERLAY` to `true` if the strategy runs in its own pane (`overlay=false`), or `false` if it draws on the price chart (`overlay=true`).
4. Gate the entries only. Exits stay as they are.

```pine
if myBuySignal and dtfBuyOk
    strategy.entry("Long", strategy.long)
if mySellSignal and dtfSellOk
    strategy.entry("Short", strategy.short)
```
