# XPDir — why is nothing detected?

Every failure below prints **one decisive line in the Experts tab** at attach. Open
Terminal → Experts, filter on `XPDIR`, and match the line. The build also dumps a
per-rung funnel by itself when the ladder produces nothing (see §5), so in most cases
the answer is already in the log without you asking for it.

## 1. `XPDIR MODE mode=DIR_OFF - direction ladder inert, 1.03 behaviour`

**This is the most common one, and it is not a fault.** `InpDirMode` defaults to
`DIR_OFF`, which is deliberate: it is what makes the build reproduce 1.03 for Gate 0.
In `DIR_OFF` the ladder creates **no indicator handle**, reads nothing, and prints
nothing further — there is nothing to detect because nothing is running.

**Fix:** set `InpDirMode = DIR_LOCK` (Gate 2) or `DIR_TRANSLATE` (Gate 3) in the EA's
Inputs tab. You should then immediately see `XPDIR INIT mode=DIR_LOCK …` and one
`XPDIR RUNG_INIT` line per rung.

## 2. `XPDIR_INIT_ABORT rung=S1 reason=symbol_missing symbol=XAUUSD-ECNc_S1_S1`

Look at the symbol in that message. If it has **two** `_S` parts, the EA is attached to
a seconds chart instead of the parent. The ladder derives every rung from `_Symbol`, so
an EA on `XAUUSD-ECNc_S1` goes looking for `XAUUSD-ECNc_S1_S1`, which nothing will ever
create. The build says so directly:

```
XPDIR HINT _Symbol=XAUUSD-ECNc_S1 is itself a seconds symbol. Attach this EA to the
PARENT (XAUUSD-ECNc), not to a _S<n> chart. Custom symbols do not trade, and the
ladder derives every rung from _Symbol.
XPDIR DIAG wanted=XAUUSD-ECNc_S1_S1 found_rung_symbols=[] count=0 symbols_known_to_terminal=…
```

**Fix:** attach the EA to the **parent** `XAUUSD-ECNc` chart, M1. Custom `_S<n>` symbols
cannot be traded at all — the map's own header says so. The seconds charts are for the
engine and for looking at; the EA lives on the parent and reads them through `iCustom`.

If instead the symbol looks right and the list is empty:

```
XPDIR HINT nothing named XAUUSD-ECNc_S1* exists. Start the XP ChartEngine service for
this parent and let it create the custom symbol before attaching the EA.
```

**Fix:** start the engine service for that seconds value first, confirm the symbol
appears under `Custom\XPChart\`, then attach.

The `found_rung_symbols=[…]` list tells you exactly which rungs the terminal can see —
useful when S1 exists but, say, S10 never got its service started.

## 3. `XPDIR_INIT_ABORT rung=S1 reason=handle_invalid` (or `rung=P`)

`iCustom` could not load the indicator.

```
XPDIR HINT iCustom could not load 'XPW_ShapeMap_v0.4'. It resolves relative to
MQL5\Indicators: the compiled .ex5 must sit there, the input carries no .ex5
extension, and a subfolder must be part of the name (e.g. Subfolder\\XPW_ShapeMap_v0.4).
```

**Fix, in order:**
1. `XPW_ShapeMap_v0.4.mq5` must be in `MQL5\Indicators\` and **compiled** (an `.ex5`
   next to it), 0 errors.
2. `InpDirMapIndicator` must be `XPW_ShapeMap_v0.4` — no `.ex5`, no leading slash.
3. If you put it in a subfolder, the input must carry it: `MyFolder\\XPW_ShapeMap_v0.4`.

## 4. `XPDIR BLOCKED_MAP_CONTRACT_MISMATCH rung=… fast_idx=1 slow_idx=2 fast=… slow=…`

The indicator answering is not the one this build was compiled against. FAST and SLOW
are SMAs of RSI and must be inside [0, 100]; these were not. The rung is silenced rather
than voted on.

**Fix:** install the `XPW_ShapeMap_v0.4.mq5` from `XPMap_ShapeMap_v0.4.zip`
(sha256 `5653130d…b52120`). The 37-line file from the original prompt is a **different
program** with a different buffer map — it puts FAST at 24 and SLOW at 25.

## 5. It initialised, but no `XPDIR DIR_STATE` line ever appears

The build tells you why, unprompted. Once a second the timer checks, and while the
ladder has produced **no** decision at all it dumps the whole funnel every 30 seconds:

```
XPDIR FUNNEL_DUMP #1 mode=DIR_LOCK ready=1 evaluations=12 state_lines=0 dir=NONE …
XPDIR FUNNEL rung=S1 symbol=XAUUSD-ECNc_S1 enabled=1 handle=10 bars=18 bar1_time=…
   vote=NV grade=- cross_dir=0 cross_age=-1 … why=map_invalid
XPDIR FUNNEL rung=P  symbol=XAUUSD-ECNc   enabled=1 handle=12 bars=5000 … why=cross
```

Read the `why=` on each rung:

| `why=` | Meaning | What to do |
|---|---|---|
| `map_invalid` | the map has not produced a valid bar yet | **wait** — this is warm-up, ~21 closed bars: S1 ≈ 30 s, S10 ≈ 4 min, S45 ≈ 16 min |
| `no_data` | `CopyBuffer` returned nothing | the indicator is loaded but has no history on that symbol yet; check the seconds chart has bars |
| `no_bar_time` | `iTime` returned 0 | the custom symbol has no bars at all — the engine service is not running |
| `stale_<n>s` | the newest closed bar is `<n>` seconds old | the engine stopped, or the market is thin. Raise `InpDirMaxRungStaleBars` if `<n>` is only just over the limit (default 3 gives S1 a 3-second window) |
| `sign_zero` | fast and slow are exactly equal and never resolved | very rare; wait |
| `buffer_contract` | see §4 | install the right indicator |
| `disabled` | that optional rung is switched off | expected for S15/S30/S45 at defaults |
| `state_no_cross_seen` / `state_cross_aged_out` / `cross` | **the rung is voting** | nothing wrong here |

If every enabled rung says `cross` or `state_…` and the direction is still `NONE`, the
ladder is working and the rungs simply disagree — read the `XPDIR DIR_STATE` line's
per-rung tags against the rules in report §3.

The funnel stops on its own as soon as the ladder starts deciding, and after 30 dumps
it prints `XPDIR FUNNEL_STOP` and goes quiet rather than filling your log.

## 6. Running it on a second chart

Supported, and the usual reason to want it is comparing two settings side by side —
`DIR_LOCK` against `DIR_TRANSLATE`, or `InpDirRequireFreshS1` off against on. One rule
decides whether it is safe:

### Same symbol on both charts → **give the second chart its own `InpMagic`**

Position ownership is `symbol == _Symbol && magic == InpMagic`. Two instances on the
same symbol with the same magic both claim the same positions: **both will trail them
and both will close them.** The build now says so at attach:

```
XPDIR WARN_DUPLICATE_INSTANCE symbol=XAUUSD-ECNc magic=26090555 is ALREADY running on
chart 132496... Give this chart its own InpMagic before you let it trade.
```

Change `InpMagic` on the second chart (any distinct number, e.g. `26090556`) and the two
separate cleanly — positions, the virtual-SL store, and the XPDir CSV all key off it.
The warning only fires when `InpDirMode != DIR_OFF`; a chart left at `DIR_OFF` changes
nothing at all, including this.

### Different symbols on the two charts → nothing to do

The symbol filter already separates them. But the second symbol needs **its own engine
services**: a chart on `EURUSD` makes the ladder look for `EURUSD_S1`, `EURUSD_S5`, …
If those do not exist you get the §2 message naming the missing symbol.

### What is per-instance, and what is shared

| | Keyed by | Safe on a second chart |
|---|---|---|
| Positions | symbol + magic | **only with different magic** on the same symbol |
| Virtual-SL store | account + symbol + magic | yes |
| XPDir CSV | symbol + magic (one file each, and every row carries both) | yes |
| Dashboard labels | the chart itself | yes |
| Indicator handles | symbol + timeframe + parameters | yes — MT5 shares one instance, so a second chart on the same parent costs nothing |
| `LA_` / `XA_` / MasterVwap CSVs | **fixed filenames** | both instances append to the same files |

That last row is a 1.03 property and was left alone deliberately: those are the
observers, and rewriting their file naming would be a change to code this build promised
not to touch. They are observational only and never gate trading. If you need them
separated per chart, say so and it becomes its own change with its own gate.

## 7. Nothing at all in the Experts tab

Check, in this order:

1. **The EA is actually attached** — a smiley face, top-right of the chart, not a sad
   face. A sad face means `OnInit` returned a failure; the reason is in the log above it.
2. **AutoTrading is on** — the toolbar button is green.
3. **You are on the right chart** — the Experts tab shows lines from every chart; look
   for the ones naming your symbol.
4. **`FlashGold_Continuation_v2_XPDIR.ex5` compiled with 0 errors.** If MetaEditor
   reported anything, send the message verbatim rather than fixing it locally — a silent
   local fix breaks the diff the Gate 0 audit rests on.
