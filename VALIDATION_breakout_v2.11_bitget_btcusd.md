# XPW Breakout v2.11 MTF: validation for Bitget BTCUSD

File audited: `xpw_breakout_v2.11_mtf_strategy.pine` (imported from the pasted XAUUSD build, then part zero applied).
Slots used: slippage 1,000 ticks, commission percent 0.06 per side, fixed quantity 0.1.

## Part zero: declaration fix (applied)

| Item | Before | After |
|---|---|---|
| `commission_type` | `strategy.commission.cash_per_contract` | `strategy.commission.percent` |
| `commission_value` | 0.10 | 0.06 |
| `slippage` | 5 | 1000 |
| `default_qty_type` | not set | `strategy.fixed` |
| `default_qty_value` | not set | 0.1 |
| `UseRiskSize` input default | true (risk percent) | false (FixedQty) |
| `FixedQty` input default | 10.0 | 0.1 |
| `QtyStep` input default | 1.0 | 0.001 |

One change beyond the four slots and the Quantity default was unavoidable: `QtyStep`.
`calcQty` floors the quantity to the step (`math.floor(q / QtyStep) * QtyStep`). At step 1.0 a 0.1 quantity
floors to 0, `qL > 0` fails, the arm is dropped and no order is ever placed. Verified arithmetically:
step 1.0 gives 0.0, step 0.001 gives 0.1. Without this change the "declared quantity" would never reach an
entry. Nothing else was touched: title, comments, input labels (still worded in ounces) and all logic are as pasted.

## Part one: exit trace (read-only)

Defaults in effect: GeoMode ATR, ATR length 14, SL 1.5 ATR, TP 2.5 R (= 3.75 ATR), UseTrail on, TrailExec Emulator,
TrailMode ATR, trail trigger 1.0 ATR, trail distance 1.5 ATR, UseBE off, MaxBarsHeld 0, EntryMode Stop, pyramiding 0.

| # | Path | Where | Trigger condition | Inputs it depends on (current value) |
|---|---|---|---|---|
| 1 | Fill-bar stop loss | `stageLong/stageShort` → `strategy.exit("XL"/"XS", loss=…)` | Price moves `armSl` ticks against the fill on the fill bar | SlAtrMult 1.5, AtrLen 14, GeoMode ATR (ATR of the arm-time closed bar) |
| 2 | Fill-bar take profit | same call, `profit=…` | Price reaches `armTp` ticks from the fill | TpR 2.5 × SlAtrMult 1.5 = 3.75 ATR net, plus `commRt` when TPNetOfCost is on (true). `commRt = 2 × (px × CommPct/100 + CommCash)` = 2 × (0 + 0.10) = $0.20 with the current model inputs |
| 3 | Fill-bar emulator trail | same call, `trail_points` / `trail_offset` | Activates once price is `trail_points` in favour, then a stop follows the best price at `trail_offset` | UseTrail true, TrailExec Emulator, TrgAtrMult 1.0, TrlAtrMult 1.5 |
| 4 | Managed stop | `exitLong/exitShort` → `strategy.exit("XL"/"XS", stop=…)`, re-issued every evaluation while in position | Stop at `avg − slDistL` (long), locked from the arm-time ATR | same as 1; `trailL` only rises via paths 5 and 6 |
| 5 | Managed take profit | same call, `limit=…` | Limit at `avg + tpLock` | same as 2 |
| 6 | Managed emulator trail | same call, `trail_points` / `trail_offset` | same as 3, carried for the life of the trade | same as 3 |
| 7 | Script ratchet trail | `trailL := max(trailL, close − dstLockL)` | Only when `TrailExec == "Script"` and `close − avg > trgLock` | OFF (TrailExec is Emulator) |
| 8 | Breakeven step | `trailL := max(trailL, beL)` | `UseBE and close − avg ≥ BeTrigR × SL` | OFF (UseBE false; BeTrigR 1.0) |
| 9 | Time stop | `strategy.close("BuyStop"/"SellStop", comment="Time")` | `MaxBarsHeld > 0` and bars held ≥ MaxBarsHeld on a confirmed bar | OFF (MaxBarsHeld 0) |
| 10 | Opposite-signal close | none | Entries are issued only while flat (`hardOK` requires `flat`), pyramiding 0, and the OCA group only cancels the other unfilled stop | n/a |
| 11 | Gate-driven cancel | `strategy.cancel("BuyStop"/"SellStop")` | Soft or hard gate closes | Cancels unfilled entries only; never closes a position |

Slippage interaction (header 1,000 ticks per side): the stop entry fills 1,000 ticks worse than the level, the SL
and trail stops fill another 1,000 ticks worse, the TP limit is never slipped. A stopped trade therefore loses
1.5 ATR plus 2,000 ticks; a TP trade must travel 3.75 ATR plus 1,000 ticks from the level. At mintick 0.1 that
is $100 per side, at mintick 0.01 it is $10 per side (read mintick off table row 18).

**Most likely early-close path: the emulator trail (paths 3 and 6).** The trail arms after 1.0 ATR in favour,
and at that moment the stop jumps from fill − 1.5 ATR to fill − 0.5 ATR. From then on any 1.5 ATR pullback from
the running high closes the trade. To reach TP the move has to run 3.75 ATR (plus widening) without ever
retracing 1.5 ATR from its peak after the first ATR. On BTC intraday bars ATR(14) is a one-bar range measure and a
3.75 ATR run spans many bars, so a 1.5 ATR retrace inside that run is the common case: most winners will print the
"Trail" comment at well under 2.5 R, and "TP" will be rare. Second most likely is the fill-bar SL (path 1): a
breakout bar on BTC is often wider than 1.5 ATR, and without Bar Magnifier the emulator's open-high-low-close path
assumption can hit the SL on the same bar it filled. Confirm from the trade list by counting exit comments
"Trail", "TP", "SL" and "SL/Trail". Timeframe-specific numbers were not produced because the timeframe slot was
not filled in.

## Part two: cost audit (read-only)

| Setting | Expected (Bitget BTCUSD) | Actual in file | Result |
|---|---|---|---|
| `commission_type` | percent | percent | match |
| `commission_value` | 0.06 | 0.06 | match |
| `slippage` | 1000 | 1000 | match |
| `default_qty_type` | fixed | fixed | match |
| `default_qty_value` | 0.1 | 0.1 | match |
| `UseRiskSize` | false | false | match |
| `FixedQty` | 0.1 | 0.1 | match |
| `QtyStep` | ≤ 0.1 and dividing 0.1 | 0.001 | match (was 1.0, which produced qty 0) |
| `MaxQtyHard` / `strategy.risk.max_position_size` | ≥ 0.1 | 50 | match, not binding |
| Quantity used by `strategy.entry` | 0.1 | `qty=calcQty(...)` on all six entry calls (Stop, Retest, CloseConfirm, long and short) = FixedQty 0.1 | match. Note `default_qty_value` itself is never read because every entry passes `qty=`; keep it equal to FixedQty by hand |
| Spread input | none | none exists | match: the only costs charged to P&L are header commission and header slippage |
| Funding / swap | not modelled | not modelled | n/a (stated in the script notes) |
| `CommPct` (model input) | 0.06 | 0.0 | **mismatch** |
| `CommCash` (model input) | 0 | 0.10 | **mismatch** |
| `SlipUSD` (model input) | 1000 × mintick (100 at mintick 0.1) | 0.05 | **mismatch** |

The three model-input mismatches do not charge anything to P&L, but they drive behaviour and were left as pasted
under "change nothing else":

- Table row 11 (commission charged vs modelled) will show red "HEADER != INPUTS": the tester charges 0.06 % per
  side, the model expects $0.20 per round trip.
- Table row 10 ("Header slippage should be") will print 0 or 1 tick against the header's 1,000.
- TP widening (TPNetOfCost on) adds `commRt` = $0.20 instead of 0.12 % of price, so the net result at TP falls
  about 0.12 % of price short of the typed 2.5 R. Correcting `CommPct` to 0.06 would widen every TP by roughly
  $120 at a $100k BTC price.
- Cost gate: with the current inputs the round trip is modelled at $0.30, so the gate never closes. With corrected
  inputs (CommPct 0.06, SlipUSD 100 at mintick 0.1) the modelled round trip is about $320 at $100k, and the gate
  (max 20 % of net TP) then needs a net TP of at least $1,600, i.e. ATR(14) ≥ about $427. On timeframes where
  BTC's ATR is below that the gate blocks every arm. Correcting the inputs therefore changes the trade list; it
  is a decision, not a silent fix.
- Sizing and breakeven read these inputs too, but both are off (fixed quantity, UseBE false).

## Part three: exit optimization (not run)

Blocked, for two reasons that are outside this environment:

1. There is no TradingView backtester or Bitget price history here, and the strategy's results depend on the
   broker emulator (stop fills, intrabar path, trailing stop in ticks), so a reimplementation would not report the
   tester's own profit factor, drawdown or trade count.
2. The `[RANGES]` and `[TIMEFRAME]` slots of the prompt were not filled in.

Protocol to run it in TradingView once the slots are filled, so the result matches the prompt's rules:

- Keep everything outside group "9. Exits" and `SlAtrMult` / `TpR` untouched (entries, filters, costs from part zero).
- Sweep `TrlAtrMult` (trail distance), `SlAtrMult` (stop) and `TpR` (target). Leave `TrgAtrMult` at 1.0 or sweep it
  as a fourth axis only if the ranges name it.
- Use Deep Backtesting with the full period, then the same combination on the first and second half of the dates.
- Reject any combination with fewer than 100 closed trades on the full period.
- Record profit factor, percent profitable, max drawdown and total closed trades for the full period and each half.
- Recommend the widest `TrlAtrMult` that stays in the top five on both halves. Report input values only.

## Part four: lineage

The only other strategy in the repository is `xpw_orientation_tdi_v2.4_strategy.pine`. It shares the pattern
(gold-calibrated defaults, `strategy.exit` emulator trail, no cost model in the declaration) and has the same defect
classes, in a worse form:

| Defect | Breakout v2.11 (this file) | TDI v2.4 (`xpw_orientation_tdi_v2.4_strategy.pine`) |
|---|---|---|
| Declaration costs not Bitget | commission cash 0.10 per oz, slippage 5 (fixed in part zero) | Line 84: no `commission_type`, no `commission_value`, no `slippage`. The tester charges zero costs |
| Quantity not fixed | `UseRiskSize` true, risk 1 % (fixed) | Line 84: `default_qty_type=strategy.percent_of_equity`, `default_qty_value=10`. Entries at lines 542 and 544 pass no `qty`, so the declaration is the only sizing. Fix is header-only: `strategy.fixed`, 0.1. No QtyStep issue there |
| Gold-sized exit geometry | ATR-based, so it scales with BTC | Lines 135 to 139: `trailUnit` "price", `trailAct` 2.0, `trailOff` 1.0, `slDist` 3.0 (stop off). The tooltip says "2.0 on XAUUSD = $2". On BTC a $2 activation and $1 trailing offset mean the trail arms within the first tick and closes on any $1 pullback. With 1,000 ticks of slippage per side added, each round trip pays about $200 at mintick 0.1 against a trail that captures a few dollars: systematic loss. This is the early-close defect of part one in its extreme form |
| Early-close paths | Trail 1.0 / 1.5 ATR (part one) | Lines 534 to 540: `strategy.close` on END labels ("exit once") and on opposite ENTER in one-side mode; in "Both" mode an opposite ENTER reverses through `strategy.entry` (an opposite-signal close, which the Breakout script does not have). Lines 556 to 560: `strategy.exit` with `trail_points`, `trail_offset`, `loss` |
| Spread or extra cost charged on top | none | none; but there is also no referee table, so a header/Properties mismatch is invisible |
| Symbol wording | Title and labels still say XAUUSD / oz | Header note documents an XAUUSD 1m history test |

For the TDI file the equivalent of part zero is: add `commission_type=strategy.commission.percent`,
`commission_value=0.06`, `slippage=1000`, change `default_qty_type` to `strategy.fixed` and `default_qty_value`
to 0.1, and, before any exit sweep, move `trailUnit` to "percent" (or rescale `trailAct` / `trailOff` to BTC
prices), otherwise every sweep result will be dominated by the $1 trail.

Update: the TDI v2.4 file has since received both the part-zero declaration fix and a new exit block
(group "Strategy exits": Points or ATR unit, stop 5000 pts, target 300000 pts, trailing stop armed at 15000 pts
of profit trailing 10000 pts behind, ATR-mode alternatives 2 / 2 R / 1 / 0.75, time stop off). The raw-price
$2 / $1 trail described above no longer exists.
