# What the five CSVs say — 2026-09-22

Files read: `FlashGold_Continuation_v2_LegAsymmetry_v1.csv`,
`FlashGold_Continuation_v2_ExitAttribution_v1.csv`, `CP_1083144984.csv`, and the two
`..._VSL_16642575_XAUUSD-ECNc_{777,26090555}.csv`.

---

## 0. None of this is the direction ladder

There is no `FlashGold_Continuation_v2_XPDir_v1*.csv` among them. The ladder wrote
nothing, so **these files say nothing about whether it works.** They describe the EA as
it ran before it, which makes them the baseline the ladder has to beat.

Both VSL files are **empty**. That is normal if no position was open at the last save —
but note that a restart with positions open and an empty VSL store means the virtual
stops are not restored.

---

## 1. Three data-integrity defects, and one of them breaks attribution

### 1.1 The magic number is shared by at least two different programs

`CP_1083144984.csv` has two rows. Its `ea` column is
`MQLInfoString(MQL_PROGRAM_NAME)` — the compiled program's own name — and it reads:

```
ea = FlashGold_v2_StackSL    magic = 26090555    symbol = XAUUSD-ECNc
2026-09-22 17:39 and 20:52, both ORDER_TYPE_BUY, both filled (retcode 10009)
```

**`FlashGold_v2_StackSL` was trading magic 26090555 on XAUUSD-ECNc.** That is the magic
`FlashGold_Continuation_v2` defaults to. Ownership is `symbol == _Symbol && magic ==
InpMagic`, so those two EAs were claiming each other's positions — each would trail and
close the other's trades.

This is exactly the hazard the second-chart work was about, and it is not hypothetical
here. It also means **the trades in the other files cannot be attributed to one EA.**

The `LegAsymmetry` file alone carries five magics, all appending to one file:

| magic | rows |
|---|---|
| 26090555 | 3,015 |
| 1212 | 11 |
| 2609054 | 1 |
| 4444 | 1 |
| 777 | 1 |

`2609054` is seven digits where `26090555` is eight — almost certainly a magic typed
with a digit dropped. `ExitAttribution` carries 26090555 and 1212.

### 1.2 The ExitAttribution file duplicates every deal ~13×

17,538 rows for magic 26090555 describe **1,358 unique `deal_ticket`s**. One deal
appears **51 times**. Every row says `is_partial_close = false`, so these are not
partial fills — they are the same close written again and again, most likely by
`XA_ReconcileHistory()` re-emitting history on each attach/deinit cycle.

**Anything computed on the raw rows is inflated about 13×.** This was very nearly
misreported here: the first pass through the file produced "1,916 trades, −52,850
points" before deduplication. The real figures are below.

### 1.3 ~1.9% of lines are torn writes

335 of 17,917 lines are malformed, plus 702 blank lines. The damaged ones are
fragments cut mid-write:

```
46A8F8D9E6D2FD89531-26090555-1789705452471-001001
```

That is the tail of a `pair_id` with everything before it lost — the signature of
concurrent appends from several instances into one shared file. It is the
fixed-filename issue in the observers, showing up as real corruption.

---

## 2. The trading result, deduplicated

Magic 26090555, unique deals only, 2026-09-07 → 2026-09-22.

| | n | win % | net points | mean | avg win | avg loss | payoff |
|---|---|---|---|---|---|---|---|
| BUY | 650 | 52.0 | −18,887 | −29.06 | +151.73 | −224.91 | 0.675 |
| SELL | 708 | 53.2 | −19,752 | −27.90 | +167.35 | −250.28 | 0.669 |
| **All** | **1,358** | **52.7** | **−38,639** | **−28.45** | +158 | −238 | **0.672** |

Exit tags: `EXIT_VIRTUAL_TRAILING_STOP` 739, `EXIT_VIRTUAL_INITIAL_STOP` 590.
Median trade duration 26 s (mean 300 s).

**Read this with the caveat in §3 before drawing conclusions from it.**

### Direction is not the thing that is losing the money

BUY and SELL are statistically indistinguishable: **−1.2 percentage points, z = −0.46.**
There is no wrong-sided bias to find. And the win rate is **above half**.

What loses the money is the payoff ratio. Expectancy per trade:

```
0.527 × 158  −  0.473 × 238  =  −29.3 points      (observed mean: −28.45)
```

At a 52.7% win rate, breakeven needs a payoff of **0.899**. The actual payoff is
**0.672** — the average loss is 1.5× the average win.

Mean favourable excursion ≈ mean adverse excursion (BUY 201 / 213, SELL 216 / 216), so
after entry price travels about as far in favour as against. The entry has a slight
edge in *how often* it is right and none at all in *how far*.

Two ways out, and only one of them is the ladder's job:

- raise the win rate to **≥ 59.8%** at the current payoff — that is a **7.1-point**
  improvement, and it is what the direction ladder would have to deliver; or
- raise the payoff to **≥ 0.899** at the current win rate — cut the average loss from
  238 points to about 176.

With `InpMinTrailingFloorPoints = 100` and `InpMaxTrailingFloorPoints = 200`, the stop
sits 100–200 points away while the average favourable excursion is about 210. The
geometry is risking ~200 to make ~160. **That is the larger lever of the two, and it is
not the ladder.**

---

## 3. The caveat that limits all of §2

Win rate by day is not stable, and not by a little:

| day | trades | net pts | win % |
|---|---|---|---|
| 09-07 | 45 | −1,013 | 86.7 |
| 09-08 | 86 | −4,067 | 84.9 |
| 09-10 | 97 | +2,025 | 87.6 |
| 09-16 | 101 | −5,629 | 76.2 |
| 09-17 | 94 | −8,793 | 55.3 |
| 09-18 | 78 | −3,234 | 14.1 |
| 09-22 | 565 | −10,529 | 23.4 |

A win rate moving from 87% to 14% is not one strategy having a bad week. It is
**different configurations, or different programs, running under one magic.** The early
days show the classic win-often-lose-big profile (excluding 09-22: 73.5% win rate at a
payoff of 0.279 — average loss 3.6× average win); the later days show something else
entirely.

So the §2 aggregate is a blend of heterogeneous runs, not a measurement of one system.
Treat it as an order-of-magnitude read, not a performance figure. To get a clean
baseline you need one EA, one magic, one configuration, writing its own file.

---

## 4. One thing the ladder fixes that needs no predictive power at all

From `LegAsymmetry`, magic 26090555, 3,015 arming events:

- **1,199 (39.8%) filled a first leg**; 1,816 (60.2%) never filled. The trigger is
  selective, which is the intent.
- **103 of those 1,199 entries — 8.6% — filled BOTH legs.** Price crossed the buy stop
  *and* the sell stop: the EA bought and sold the same move. Median 151 points of
  traversal between the two fills, median 92 seconds apart.

`DIR_LOCK` removes all 103 by construction, because only one side is ever armed. That
is a countable, guaranteed improvement that does not depend on the ladder being right
about direction — it only depends on it having an opinion.

Also from the same file:

- first-fill slippage: **median 36 points**, mean 72.9, max 2,230
- spread at fill: median 11 points
- trigger gap (buy level to sell level): median 138 points

Median slippage of 36 points against an average win of 158 points is **23% of the
average win, given away at entry.** Next to a 47-point stated cost floor, that deserves
its own look.

---

## 5. What to do next

1. **Stop the magic collision.** Decide which program owns 26090555 on XAUUSD-ECNc and
   give every other instance its own. The 1.05-XPDIR build warns about this at attach
   (`XPDIR WARN_DUPLICATE_INSTANCE`), but only for instances running the ladder.
2. **Get a clean baseline.** One EA, one magic, one configuration, long enough to matter.
   Until then no before/after comparison of the ladder means anything.
3. **Look at `XA_ReconcileHistory`** — 13× duplication makes the exit file unusable
   without deduplication, and it is the file you would measure the ladder against.
4. **Then run the ladder** and compare like with like. The target is explicit: at the
   current exit geometry it has to move the win rate about 7 points.

None of §5 is in the ladder's scope, and none of it has been changed. It is what the
data says.
