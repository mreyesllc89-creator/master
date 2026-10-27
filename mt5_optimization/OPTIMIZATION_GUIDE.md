# XPW ShapeMap v0.9.2 + FlashGold EA — optimization guide for XAUUSD and BTCUSD

Source analysed: `Octa_Tester_Source_547cb988.zip` (EA `XPW_ShapeMap_v092_FGF_EA.mq5`,
includes under `MQL5/Include/XPW` and `MQL5/Include/FlashGold`, the two indicators,
and `XPW_ShapeMap_v092_FGF_EA_Default.set`).

> This guide is derived from reading the EA's code and the author's own calibration
> notes in `FlashGold_v5_Strategy_BTCUSD.pine`. No MetaTrader backtest was run here
> (there is no MT5 terminal or tick data in this environment). The numbers below are
> **starting points and search ranges**, not backtested winners. The two `.set` files
> next to this guide load straight into the MT5 Strategy Tester.

---

## 1. Timeframe — the EA decides most of it for you

`ShapeMapV92Timeframe.mqh` refuses every chart period except **M1, M5, M10, M15**, and
only accepts these chart → signal (`SigTF`) pairs:

| Chart | `SigTF` allowed      | Notes                                   |
|-------|----------------------|-----------------------------------------|
| M1    | blank (=M1) or `5`   | noisiest; spread-heavy                  |
| M5    | blank (=M5) or `1`   | the natural fit for the gold defaults   |
| M10   | blank (=M10) only    | non-standard clock, fine in MT5         |
| M15   | **`10` only**        | blank is refused on M15                 |

Anything else (M30, H1, H4…) fails `OnInit`. The FlashGold direction filter still
reads H1 parent + H1/H2/H4 zones regardless of the chart, so the "higher timeframe
context" is already built in.

### Recommendation

| Symbol  | Primary                    | Second pass                | Why |
|---------|----------------------------|----------------------------|-----|
| XAUUSD  | **M5 chart, `SigTF` blank** | M1 chart, `SigTF=5`        | Every default in the EA is gold-on-M5 scaled: SL 7000 pts = $70, trail 100 pts = $1, spread model 25 pts = $0.25, quantity "contracts = oz". RSI(14)/MA 2-7 turn signals on M5 give a workable trade count without M1 noise. |
| BTCUSD  | **M15 chart, `SigTF=10`**   | M10 chart, `SigTF` blank   | Highest period the EA admits. The author's own BTC calibration (60m–240m, in `FlashGold_v5_Strategy_BTCUSD.pine`) states that below 60m a tight stop "shrinks to a few dollars while the fee stays ~$32 per BTC round trip, so expect losses on 1m to 15m unless the fee is near zero". M15 is the closest admitted period; M5/M1 on BTC should be treated as a sanity check, not a target. |

**Honest caveat for BTC:** the EA's admitted clocks and the regime where the author
showed the FlashGold filter has an edge (H1–H4) do not overlap. Expect BTC results to
be more spread-sensitive and less stable than gold. If BTC on M15 is not positive on
real ticks with your broker's actual spread, the right fix is a code change to admit
H1 (not more parameter tuning).

---

## 2. Things that must be set before any optimization run

1. **`EnableTrading=true`.** The shipped default `.set` has it `false` and the gateway
   (`ShapeMapV92FgfGateway.mqh`) refuses every order when it is false → the tester
   reports zero trades. Both provided `.set` files set it to `true`.
2. **Compile both indicators** (`XPW_ShapeMap_v092_FGF_Map.mq5`, `XPW_ShapeMap_v092_FGF_Filter.mq5`)
   into `MQL5/Indicators`. The EA declares them via `#property tester_indicator` and
   loads the filter with `iCustom`; a missing `.ex5` fails every pass.
3. **Modelling:** never use "Open prices only". `EnterTick=true`, the Predict stop
   orders and the trailing stop all act intrabar. Use **"1 minute OHLC"** for the
   genetic passes and **"Every tick based on real ticks"** to confirm the top 10.
4. **Spread:** set the tester to "Current" or a fixed value matching your broker, and
   set `fgfSpreadPts` to the same value (it feeds the filter's entry-level model).
5. **Sizing is Risk % (`QtyMode=1`), fixed at 1 %.** Do not optimize `RiskPct`; it only
   scales the equity curve and the optimizer will always pick the maximum.
6. **Optimization criterion:** `OnTester()` returns `TesterStatistics(STAT_PROFIT)`, so
   "Custom max" = net profit, which over-fits. Prefer **"Complex Criterion max"** for
   the genetic passes, and always enable **Forward = 1/3** so each result has an
   out-of-sample column.
7. **Tester period:** at least 12 months (ideally 2024-01 → today). M5 gold gives
   plenty of trades; BTC M15 gives fewer, so do not shorten below a year.
8. **Visuals off** (`Show*`, `fgfShow*`, `ShowTable`, `ShowMap`, `EnableCSV=false`).
   They do not affect signals and they slow every pass. Already done in the files.

---

## 3. Why the gold defaults cannot be reused on BTC (and what was changed)

Every "pts" input is in **trade-tick units** (`SYMBOL_TRADE_TICK_SIZE`), not a
percentage. With tick 0.01 on both symbols:

| Input            | Gold default | Means on gold (~$4,000) | Same number on BTC (~$100k) | BTC preset value |
|------------------|--------------|-------------------------|------------------------------|------------------|
| `SlPts`          | 7000         | $70 (1.75 %)            | $70 (0.07 %) — inside one M15 bar | `ExitUnit=1` (ATR) so unused; 150000 if you switch back |
| `TrDisPts`       | 100          | $1 trail                | $1 trail on a $400 ATR bar — tester artifact | ATR mode, `TrDisAtr ≥ 0.25` |
| `PredBuf`        | 100          | $1 past the cross       | $1                           | 2500 ($25)       |
| `ContStopBuf`    | 50           | $0.50                   | $0.50                        | 1500 ($15)       |
| `LossRevTinyPts` | 1500         | $15 "tiny profit"       | $15                          | 37500 ($375)     |
| `fgfSpreadPts`   | 25           | $0.25 spread            | $0.25 (real BTC spread ≈ $20–60) | 3000 ($30) — set to yours |
| `DeviationPoints`| 20           | $0.20 slippage allowance| $0.20 → rejected fills       | 5000 ($50)       |
| `QtyFixed` / `QtyMax` | 10 / 50 | 10 oz / 50 oz (0.1 / 0.5 lot) | 10 BTC / 50 BTC (!)    | 0.1 / 1.0 BTC    |
| `MgnPct`         | 1.0          | 1:100 leverage          | most brokers give 1:5–1:10 on BTC | 10.0 (set to your symbol's margin %) |

The author's BTC notes also found that a $10 trail on BTC "books exits at the bar
extreme, which live fills cannot do" (+219k in the tester, –12k with fees). That is
exactly what `TrDisPts=100` would do here, so both presets use **ATR exits**
(`ExitUnit=1`) with a trail distance floor of 0.25 ATR.

If your broker quotes BTCUSD with tick size 1.0 instead of 0.01, divide every `*Pts`
value in the BTC file by 100.

---

## 4. Suggested starting configuration (before optimization)

| Group            | XAUUSD M5                              | BTCUSD M15 (`SigTF=10`)                |
|------------------|----------------------------------------|----------------------------------------|
| Signal           | `SigMode=1` Turn ▲/▼, `TurnEntry=0` Predict, `OppMode=0` Reverse, `ArmMode=0` | same |
| Exits            | ATR: `SlAtrM=2.0`, `TpR=2.0`, trail on, `TrActAtr=4`, `TrDisAtr=0.5` | ATR: `SlAtrM=1.5`, `TpR=3.0`, trail on, `TrActAtr=3`, `TrDisAtr=0.75` |
| Loss reversal    | on, max 1, tiny ≤ $15                  | on, max 1, tiny ≤ $375                 |
| FlashGold filter | on, H1 parent, zones H1/H2/H4, band 0.25 ATR, burst 0.5 ATR, min aligned 2 | same |
| Sizing           | Risk 1 %, max 50 oz                    | Risk 1 %, max 1 BTC                    |

---

## 5. Optimization plan (genetic, three passes per symbol)

Load the symbol's `.set`, then run the passes below. After each pass, right-click the
best forward-stable result → "Set input parameters", then flip the next pass's
inputs to optimize (the ranges are already stored in the file; only the Y/N flag
changes).

### Pass 1 — structure + exits (flags already **Y** in the files)

| Input       | Range (XAU)         | Range (BTC)         | What it decides |
|-------------|---------------------|---------------------|-----------------|
| `SigMode`   | 0–3                 | 0–3                 | square / turn / wick tick / CONT entries |
| `TurnEntry` | 0–2                 | 0–2                 | predictive stop vs at-cross vs after-hold |
| `OppMode`   | 0–2                 | 0–2                 | reverse / close / ignore opposite signal |
| `ArmMode`   | 0–1                 | 0–1                 | arm on squares only vs every cross |
| `FailExit`  | off/on              | off/on              | exit if cross fails to hold |
| `SlAtrM`    | 1.0–4.0 step 0.5    | 0.5–3.0 step 0.5    | stop distance |
| `TpR`       | 1.0–5.0 step 0.5    | 1.0–5.0 step 0.5    | target as R-multiple |
| `TrailOn`   | off/on              | off/on              | author found no trail helped on BTC |
| `TrActAtr`  | 1–6 step 1          | 1–6 step 1          | trail activation |
| `TrDisAtr`  | 0.25–1.5 step 0.25  | 0.25–1.5 step 0.25  | trail distance (floor 0.25 avoids the bar-extreme artifact) |
| `LossRevOn` | off/on              | off/on              | open opposite trade after a loss |
| `fgfOn`     | off/on              | off/on              | whether the FlashGold filter helps at all |

Expected outcome: `SigMode` 1 (Turn) or 3 (CONT) and `TurnEntry` 0 or 2 should
dominate on gold; on BTC `TrailOn=false` with `TpR` 3–5 is the likely winner given
the author's 60m–240m results (SL 0.1 ATR / TP 5R there, but that strategy entered on
burst stop orders, so expect this EA's turn entries to need a wider 1–2 ATR stop).

### Pass 2 — shape-map signal parameters (flip to **Y**)

`RsiLen` 10–21, `FastLen` 2–3, `SlowLen` 5–9, `TurnMax` 6–20, `TurnHold` 1–3,
`AreaLook` 14–30, `LoFrac` 0.10–0.30, `HiFrac` 0.60–0.90, `AllOn` on/off.
If pass 1 chose `SigMode=2` add the wick thresholds (`BotWickRange`, `BotWickAtr`,
`TopWickRange`, `TopWickAtr`); if it chose `SigMode=3` add `ContBigAtr`, `ContLook`,
`ContRedMax`, `ContPinch`, `ContAfter`, `ContSep`, `ContEntry`, `ContStopBuf`.
Keep `FastLen < SlowLen` (the prediction code requires it).

### Pass 3 — FlashGold filter (flip to **Y** only if pass 1 kept `fgfOn=true`)

`fgfBandAtr` 0–0.5, `fgfBurstAtr` 0.3–1.0, `fgfMinAligned` 1–3, `fgfAgainst` on/off,
`fgfLast` 0–2 with `fgfBars` 1–4, `fgfUseDrift` on/off. Try `fgfParentTf=16388` (H4)
by hand as one extra run; the author's direction-score table in the filter shows the
TDI parent only separated from a coin flip at 1D on BTC, so do not expect pass 3 to
move the result much on BTC.

### Robustness checks (do these before trusting any result)

- Forward period ≥ 1/3 must stay positive and the parameters must sit on a plateau
  (neighbours within one step also positive), not on a spike.
- Re-run the top 5 with **real ticks** and with spread 1.5× your broker's typical.
- Re-run the best on the *other* admitted clock (gold: M1/`SigTF=5`; BTC: M10) — a
  real edge degrades gently, an over-fit one disappears.
- `LossRevOn` doubles exposure after a loss; check max drawdown, not just profit.

---

## 6. Files

| File | Use |
|------|-----|
| `XPW_v092_FGF_XAUUSD_M5_opt.set` | Load in Strategy Tester → Inputs, XAUUSD, **M5** chart, `SigTF` blank |
| `XPW_v092_FGF_BTCUSD_M15_opt.set` | Load in Strategy Tester → Inputs, BTCUSD, **M15** chart (`SigTF=10` is inside the file) |

Both files keep every input of the shipped default `.set`, set `EnableTrading=true`,
turn visuals off, use ATR exits and Risk-% sizing, and carry pass-1 optimization
flags with all pass-2/3 ranges stored but switched to `N`.
