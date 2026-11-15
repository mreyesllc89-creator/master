# Tokio732_VolLab (engine 3614, T50) — calibration on XAUUSD and BTCUSD

Date: 2026-11-15. Input: `Tokio732_3614_T50_PARA_MENTOR_4252.rar` (source `Tokio732_VolLab.mq5`,
the 152-input preset, MT5 reports and basket logs). MetaTrader cannot run in this environment, so
the engine was ported to Python (`tools/engine.py`) and run on the M1 bid/ask history already in
this repository (branch `claude/sharp-brown-qqghvg`): XAUUSD 2011 – June 2018 and July–August
2026; BTCUSD 2015–2019 and July–August 2026. There is no 2019–2025 data and no tick data here.

## 1. Short version

1. **The shipped preset's profit lives inside the one-minute bar.** If the basket is evaluated on a
   smooth path inside each M1 bar (best-case execution), the preset makes money in 6 of 8 gold
   years. If it is evaluated once per minute at the recorded close, a 1,000 USD account is ruined
   in 71 % of in-sample starts and 49 % of out-of-sample starts. Your own 1 ms vs 189 ms tests
   show the same split. The cause is the trailing give-back: 2 × factor USD on about 9 oz is
   roughly 0.7 USD of gold price, less than one typical M1 bar.
2. **A calibrated gold preset does not need that precision.** It is profitable in all 8 years
   under both tick models, with no ruined account in 73 monthly starts. Median result of a
   1,000 USD start held to year end: about 1,700 (in-sample) and 2,200 (out-of-sample) with
   one-minute evaluation; median drawdown 32–34 %, worst 81 %.
3. **Neither gold preset made money in July–August 2026**, the only recent data here: shipped
   −19 % to −51 %, calibrated −21 %. That is 31–60 baskets, too few to conclude, but it is not a
   confirmation.
4. **Bitcoin:** the shipped logic rescaled to bitcoin is ruined in 73–82 % of starts with
   one-minute evaluation. A calibrated preset is positive in every year 2015–2019 and flat
   (+2 %) in July–August 2026, with 38–48 % drawdown. The EA refuses any symbol that does not
   start with `XAUUSD` (`CheckAccount732`), so the bitcoin preset needs that check relaxed.
5. These are simulations on rescaled history with a simplified tick model. Treat the presets as
   candidates for your own real-tick Strategy Tester runs, not as verified settings.

## 2. What was ported and how close it is

Ported: trend (EMA on closed bars), volatility factor (Wilder ATR on closed H1 bars, frozen per
basket), lot scale (cushion or balance-scaled, vol gamma), entry window (hours, cooldown, minimum
factor), net-target order logic with with-trend / against-trend lots, centre crossings, minimum
move, new-zone rule, basket trailing, percentage stop, maximum age, margin check. Every module
that is off in the preset was left out (seeds, pyramiding, big-order protection, news, recycle,
trims, inventory guard, and so on). Swaps and commission are not modelled.

Check against your MT5 basket logs, same starting balance, 2 July – 31 August 2026 (Octa M1 data
here covers about two thirds of the trading days of the Exness tick file):

| Run | Baskets | Net USD | Trail (n / USD) | Stop (n / USD) | Age (n / USD) |
|---|---|---|---|---|---|
| MT5 2026, 1 ms (balance 2,257) | 41 | +2,411 | 23 / +4,070 | 5 / −1,371 | 13 / −289 |
| Port, interpolated | 32 | +952 | 16 / +3,274 | 10 / −1,867 | 5 / −231 |
| Port, M1 closes | 29 | −1,060 | 5 / +975 | 14 / −2,035 | 10 / 0 |
| MT5 2026, 189 ms (balance 1,024) | 47 | −844 | 2 / +291 | 35 / −1,135 | 10 / 0 |
| Port, interpolated | 32 | +647 | 9 / +2,069 | 14 / −1,422 | 8 / 0 |
| Port, M1 closes | 31 | −199 | 6 / +1,245 | 16 / −1,444 | 9 / 0 |

Same mechanism and magnitude, not trade-for-trade parity. The two tick models bracket the two
MT5 delays. Full table: `results/fidelity_2026_jul_aug.csv`.

## 3. Method

* **Rescaling.** The preset is written in absolute gold dollars for 2026 volatility; on 2011–2018
  prices its volatility switch would never open a basket. Each historical year is multiplied by
  one constant so its median H1 true range equals the July–August 2026 level (gold 15.0 USD,
  bitcoin 257 USD), and gets the 2026 spread (0.11 USD gold, 17 USD bitcoin). This is a change of
  units, equivalent to rescaling `VolATRRef`, the price inputs and the lots. The constant uses
  the whole year, which a live trader would not know in advance.
* **Bitcoin transform.** Price inputs × 17.1 (the volatility ratio), lots × 100 / 17.1 (1 BTC
  contract instead of 100 oz), money inputs unchanged.
* **Runs.** Every run starts with 1,000 USD. The search scored each year from two start dates;
  the final tables use every month as a separate start.
* **Tick models.** *M1 close*: one evaluation per minute at the recorded close, nothing assumed
  about the path. *Interpolated*: open → extreme → extreme → close in 0.05 USD steps, which is
  optimistic for tight trailing. The search was scored on M1 close only, after an earlier pass
  showed that interpolated scoring rewards settings that scalp the artificial smooth path.
* **Search.** 3,000 random settings per symbol over 20 EA inputs (`tools/space.py`), scored on
  in-sample years (gold 2011–2014, bitcoin 2015–2017) as mean log growth minus 2 × worst
  drawdown². The 40 leaders were checked out-of-sample (gold 2015–2018, bitcoin 2018–2019); six
  were refined by one-input hill climbing on the in-sample score; the pick is the refined
  candidate with the best out-of-sample score. Choosing among six on out-of-sample data is a mild
  selection bias. July–August 2026 was never used.

## 4. Results

Every monthly start, 1,000 USD, held to the end of that year (`results/final_summary.csv`):

| Symbol | Preset | Sample | Ticks | Starts | Ruined % | Losing % | Median final | 10th pct | Median DD % | Worst DD % |
|---|---|---|---|---|---|---|---|---|---|---|
| XAUUSD | shipped | in | M1 close | 38 | 71 | 76 | 74 | −8 | 95 | 102 |
| XAUUSD | shipped | in | interpolated | 38 | 11 | 13 | 3,029 | 295 | 60 | 99 |
| XAUUSD | shipped | out | M1 close | 35 | 49 | 54 | 695 | 2 | 93 | 116 |
| XAUUSD | shipped | out | interpolated | 35 | 14 | 14 | 3,468 | 187 | 57 | 97 |
| XAUUSD | calibrated | in | M1 close | 38 | 0 | 13 | 1,718 | 931 | 32 | 52 |
| XAUUSD | calibrated | in | interpolated | 38 | 0 | 3 | 2,549 | 1,234 | 28 | 49 |
| XAUUSD | calibrated | out | M1 close | 35 | 0 | 11 | 2,196 | 968 | 34 | 81 |
| XAUUSD | calibrated | out | interpolated | 35 | 0 | 6 | 2,690 | 1,134 | 30 | 55 |
| BTCUSD | shipped | in | M1 close | 33 | 73 | 76 | 2 | −40 | 100 | 139 |
| BTCUSD | shipped | out | M1 close | 22 | 82 | 95 | 4 | −284 | 100 | 119 |
| BTCUSD | calibrated | in | M1 close | 33 | 0 | 0 | 2,913 | 2,059 | 43 | 61 |
| BTCUSD | calibrated | out | M1 close | 22 | 0 | 5 | 1,624 | 1,043 | 44 | 51 |
| BTCUSD | calibrated | out | interpolated | 22 | 0 | 9 | 1,562 | 1,357 | 40 | 51 |

"Ruined" = below 300 USD. A drawdown above 100 % means a gap took equity below zero.

July–August 2026, real bid/ask, no rescaling, one start:

| Symbol | Preset | M1 close | Interpolated |
|---|---|---|---|
| XAUUSD | shipped | 486 | 806 |
| XAUUSD | calibrated | 788 | 795 |
| BTCUSD | shipped (transformed) | 50 | 2,539 |
| BTCUSD | calibrated | 1,018 | 1,066 |

Per year, 1 January start, M1 close (final balance): gold calibrated 2,723 / 2,168 / 2,304 /
2,864 / 4,067 / 3,229 / 2,756 / 1,043 for 2011–2018; bitcoin calibrated 5,083 / 3,218 / 15,357 /
3,288 / 3,967 for 2015–2019. Full table with drawdowns and exit counts: `results/final_yearly.csv`.

Cost stress on the calibrated presets (median year, M1 close): doubling the spread or adding
0.25 gold-USD slippage per fill did not reduce the median (`results/final_summary.csv`).

How fast the shipped preset degrades with evaluation granularity is in
`results/granularity_shipped.csv` and `results/execution_sensitivity_shipped.csv`: per-fill
slippage up to 0.25 USD costs little; what breaks it is not being able to act within about
1 USD of the trailing level.

## 5. The calibrated presets

`presets/TOKIO_VolLab_XAUUSD_calibrated.set` and `presets/TOKIO_VolLab_BTCUSD_calibrated.set`
are the shipped 152 inputs with these changed:

| Input | Shipped | XAUUSD | BTCUSD |
|---|---|---|---|
| MainTimeframe / MicroTimeframe | M6 | M10 | M10 |
| MainFastEMA / MainSlowEMA | 20 / 50 | 13 / 65 | 9 / 44 |
| UpdateTrendInsideBasket | true | true | false |
| LotsWithTrend | 0.10 | 0.0309 | 0.6052 |
| LotsAgainstTrend | 0.01 | 0.0155 | 0.0006 (rounds to zero) |
| CushionEnabled | true (fixed lot) | true | false (lot follows balance) |
| VolLotGamma | 1.0 | 1.0 | 1.5 |
| VolATRRef | 4.74 | 4.74 | 81.22 |
| MinVolFactor | 2 | 2 | 3.5 |
| CrossAboveCenter / Below | 220 / 110 | 20 / 20 | 342.7 / 342.7 |
| MinMoveBetweenOrders | 0.5 | 0.63 | 29.99 |
| NewZonesEnabled / Padding | true / 4.0 | true / 2.73 | false / — |
| TrailArm / Giveback / Floor USD | 50 / 2 / 1 | 34.8 / 2.5 / 3.8 | 97.9 / 17.1 / 41.1 |
| CycleLossPct | 8 | 5.6 | 3.7 |
| StopCooldownMinutes | 240 | 0 | 240 |
| EntryHourFrom / To | 0 / 12 | 0 / 8 | 7 / 20 |
| MaxBasketAgeMinutes | 2880 | 360 | 2880 |
| ExitSlippageReservePrice | 0.5 | 0.5 | 8.57 |

What changed in substance on gold: the with-trend lot is about one third of the shipped one
(0.03 lots at a factor near 3), so the 5.6 % basket stop sits several dollars of gold away instead
of inside the noise; baskets are opened only in the first 8 server hours and closed after 6 hours
instead of 2 days. On bitcoin the lot follows the balance, which keeps the stop distance constant
in price terms.

## 6. On the questions in LEEME.md

Only what this work can support:

* **Q1/Q2 (stop and lot sizing).** Consistent with your hypothesis. With the shipped lot the 8 %
  stop at 1,000 USD is a few dollars of gold; the gold pick keeps a fixed lot but one third the
  size, and the bitcoin pick uses `CushionEnabled=false`, which makes stop distance independent
  of balance. No setting with the shipped lot size survived one-minute evaluation near the top
  of the search. I did not isolate the stop alone.
* **Q3 (give-back).** The tight give-back is the part that depends on execution speed. The search
  allowed give-back up to 60 % of the arm level; the picks use 7 % (gold) and 17 % (bitcoin) with
  a higher floor.
* **Q4 (age exits).** The gold pick cuts at 6 hours. Not tested in isolation.
* **Q6 (out-of-sample).** Run both presets in the Strategy Tester on your Exness ticks for
  2022–2026, at 1 ms and 189 ms, from several start months. The shipped preset fails that test
  in your own runs; a preset worth forwarding should give similar results at both delays.

## 7. Limits

* No tick data and no 2019–2025 data; history is rescaled, not native.
* The interpolated model flatters tight trailing; the M1-close model is slower than a live EA.
* Constant spread on historical years; no swaps, commission, requotes or stop-out rules beyond a
  simple margin check.
* 3,000 settings were tried per symbol; the picks passed an out-of-sample check but the recent
  two-month window was flat to negative.

## 8. Reproduce

```bash
git fetch origin claude/sharp-brown-qqghvg
```

Extract `calibration/data/*.npz` from that branch into a folder, then from `tools/`:

```bash
TOKIO_DATA=/path/to/data python sweep.py XAUUSD 3000 11
```

```bash
TOKIO_DATA=/path/to/data python refine.py XAUUSD
```

```bash
TOKIO_DATA=/path/to/data python final_eval.py /path/to/TOKIO_3614_T50_PREDETERMINADO.set
```

Use seed 12 for BTCUSD. `fidelity.py`, `baseline.py` and `execution.py` produce the other tables.
