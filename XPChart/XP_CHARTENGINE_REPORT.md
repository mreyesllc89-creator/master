BLOCKED_NO_COMPILER | max_ticks_per_second: NOT_CAPTURED (no MT5 terminal reachable from this run; simulated feed reached 28/s) | DECISION: no — not until Ghost attaches the Gate 1 receipt and the 10-minute smoke receipt below

# XP_CHARTENGINE_REPORT — XP ChartEngine v2 (PLUMBING bucket) — 2026-09-22

Prompt: XP_CHARTENGINE_UPGRADE_PROMPT v1. Thread: XP ChartEngine only (no Pine→MQL5 port work started).
Companion: `P0_REPORT.md` (diagnosis, emitted before any edit). v1 (`XP ChartEngine.mq5`) is untouched.

## 0. Where this ran, and what that changes

This run executed in a Linux container holding only the git repository (`README.md` and nothing else).
Not reachable: the Codex tree, the TradingSystems tree, the 41 MT5 installs, metaeditor64.exe,
any running terminal, and `www.mql5.com` (blocked by the egress proxy). Consequences:

| Prompt step | Status here | Delivered instead |
|---|---|---|
| P0.1 census / P0.4 deployment map | BLOCKED_NO_LOCAL_TREE | `tools\XP_Census.ps1` (read-only) |
| P0.3 Gate 1 receipt | PENDING_GHOST | `XP_AxisCheck.mq5` + run steps (§1) |
| P1 build v2 | DONE | `XP ChartEngine v2.mq5` (1029 lines) |
| P2 compile | BLOCKED_NO_COMPILER (paths searched: whole container filesystem, no `metaeditor64.exe`; no Wine) | `tools\XP_Compile.ps1`; both sources pass a C++ stub compile with 0 errors / 0 warnings (§8) |
| P2 smoke | PENDING_GHOST (R5: agent never attaches to a live terminal) | run steps + acceptance mapping (§5) |
| P3 lineage sweep | DONE for this repo, PENDING_GHOST for the host trees | `tools\XP_LineageSweep.ps1` (§6) |

Nothing below is inferred where the prompt demands a receipt; every receipt slot is marked PENDING_GHOST.

## 1. GATE 1 — time-axis verdict: PENDING_GHOST

Receipt slot (paste the Journal line and attach `MQL5\Files\XPChart\axischeck_<symbol>.csv`):

```
XP_AxisCheck VERDICT: ________________ | symbol=XAUUSD_S1 | bars=____ | modal_delta_s=__ (___/___) | non_minute_bars=____ | first=____ | last=____
```

How to get it (SMOKE_TERMINAL, read-only script):
1. `tools\XP_Compile.ps1` (or MetaEditor F7) → `XP_AxisCheck.ex5`; copy it to `<terminal data>\MQL5\Scripts\`.
2. Terminal → Navigator → Scripts → right-click Refresh → drag `XP_AxisCheck` onto any chart.
3. Inputs: `CheckSymbol` = the existing `*_S1` symbol (e.g. `XAUUSD_S1`), `ExpectedIntervalSeconds` = 1. OK.
4. Read the `XP_AxisCheck VERDICT:` line (Experts tab) and the CSV. The script also reports the last 200
   ticks of the custom tick DB and counts ticks whose `time` disagrees with `time_msc` (a D9 receipt).

What the verdict decides:

| Verdict | Meaning | v2 action |
|---|---|---|
| `SECONDS_AXIS_REAL` | one bar per real second exists in the M1 store | keep `TimeAxis = REAL` (shipped default) |
| `M1_AXIS` | second-timed bars collapsed into minute bars; v1 charts were never S1 | run v2 with `TimeAxis = SYNTHETIC` and re-pin the default (`GATE1_DEFAULT` marker, line 50 of v2); use `CustomNameSuffix` (e.g. `_v2`) so synthetic bars never share a symbol with v1's real-time bars |
| `EMPTY` | nothing stored | run v2 in REAL for 2 minutes, then AxisCheck the v2 symbol and decide as above |
| `OTHER_AXIS(n)` | unexpected spacing | attach the histogram; no default change |

The verdict logic was exercised here against three fake histories (60 s spacing → `M1_AXIS`, 1 s spacing with
gaps → `SECONDS_AXIS_REAL`, none → `EMPTY`). That proves the script's arithmetic, not the terminal's behaviour.

## 2. D1–D10 line receipts (v1 = `XP ChartEngine.mq5`, 114 lines, sha256 `ddad0226…5fd9e0`)

| ID | Verdict | Lines | Receipt |
|---|---|---|---|
| D1 | CONFIRMED | 77-78 | `datetime current_time = TimeCurrent();` / `datetime bar_time = (current_time / interval_s) * interval_s;` |
| D2 | CONFIRMED | 73, 112 | `if(SymbolInfoTick(actual_symbol, last_tick))` … `Sleep(100);` (plus the L75 msc filter that also drops same-ms ticks) |
| D3 | CONFIRMED | 95 | `s_bar[0].tick_volume = 1;` |
| D4 | CONFIRMED | 96 | `s_bar[0].spread = (int)((last_tick.ask - last_tick.bid) / SymbolInfoDouble(actual_symbol, SYMBOL_POINT));` (single tick, truncated) |
| D5 | CONFIRMED | 81-83, 87-88, 94 | `bar_open = last_tick.bid; … MathMax(bar_high, last_tick.bid) … s_bar[0].close = last_tick.bid;` no basis input (inputs = L19-21) |
| D6 | CONFIRMED | 36-42 | `for(int i=0; i<SymbolsTotal(false); i++) { … if(StringFind(sym, BaseSymbol) >= 0) { actual_symbol = sym; break; } }` — self-matches `XAUUSD_S1` on restart → `XAUUSD_S1_S1` |
| D7 | DIFFERENT | 53-60 | `SYMBOL_DIGITS` (L59) is set only inside the create branch; the reuse path sets nothing at all |
| D8 | CONFIRMED | 99, 107 | `CustomRatesUpdate(custom_name, s_bar);` / `CustomTicksAdd(custom_name, tick_to_push, 1);` returns discarded; L58 `SymbolSelect` also unchecked |
| D9 | CONFIRMED | 103-104 | `tick_to_push[0] = last_tick; tick_to_push[0].time = current_time;` |
| D10 | CONFIRMED | 66-68, 80-85 | state zeroed at start; first tick after restart re-opens the slot from one tick and L99 overwrites the stored bar |

Full quotes and the extra findings E1-E4 are in `P0_REPORT.md`.

## 3. F1–F14 — applied / not, with v2 line references

| F | Status | Where in `XP ChartEngine v2.mq5` | Notes |
|---|---|---|---|
| F1 lossless CopyTicks cursor | APPLIED | L966 `CopyTicks(actual_symbol, ticks, COPY_TICKS_ALL, (ulong)cursor_msc, count)`; dedupe L978-995; `Sleep(poll_ms)` L1018 (default 50, floor 10) | cursor = current tick at start (R3, L934-947; falls back to `TimeCurrent()` if the market is closed). Boundary millisecond is re-requested and deduped by counting ticks already seen at that ms — no +1 ms skip. `CopyTicksCount` (L58, default 0) exists because the `count=0` line of the reference could not be fetched (§7). No busy loop. |
| F2 tick.time_msc anchoring | APPLIED | L693 `slot = t.time_msc / interval_ms`; boundary → `CloseBar()` + `OpenBar()` L698-709; both bars go out in one `CustomRatesUpdate` (L773-799) | |
| F3 tick_volume / real_volume | APPLIED | L716 `b_ticks++`; L717-718 real_volume = Σ `volume_real`, else Σ `volume`, else 0 | heartbeat column `real_volume_seen` reports whether the feed supplies volume (expected `false` on XAUUSD CFD) |
| F4 SpreadMode | APPLIED | input L49 (default MAX); L719-725; parent `SYMBOL_POINT` read at L909-910 | rounded (`MathRound`), not truncated as in v1 L96 |
| F5 PriceBasis | APPLIED | input L48 (default BID); `TickPrice()` L587-596 | MID is stored unrounded (see open item f) |
| F6 deterministic base | APPLIED | `ResolveBaseSymbol()` L208-279; `BaseSymbolOverride` L46; `SymbolSelect` result printed L902-903 | candidates = non-custom symbols equal to or starting with `BaseSymbol`; rank exact > Market-Watch-selected > most recent tick > name; every candidate printed with rank; zero → `BLOCKED_NO_BASE_SYMBOL`, exit |
| F7 spec sync both paths | APPLIED | `SyncSpecs()` L424-470, helpers L370-423, called after create and after reuse alike (L927-928) | 30 properties set from the parent, read back from both, printed as a PASS / FAIL / NOT_SETTABLE table; derived/dynamic ones shown with the parent value and never set. The reference's settability list could not be fetched, so the runtime set+readback is the receipt (a 5306 = terminal refuses the property) |
| F8 checked writes | APPLIED | `FlushPending()` L748-810; `ErrPrint()` ≤1/s L145-158; `ConsecutiveFailLimit` L56; `BLOCKED_CUSTOM_WRITE` + interruptible 5 s sleep L1002-1009 | failed ticks/bars stay in bounded retry buffers (20000 ticks / 5000 bars, drops counted) — nothing is lost during a short outage; error code and name printed (32 is flagged as not an MQL5 code) |
| F9 restart-safe | APPLIED | `SeedFromStoredBar()` L812-858 | stored last bar's slot == current slot → open/high/low/close/tick_volume/spread/real_volume seeded; otherwise fresh, with a print either way |
| F10 TimeAxis | APPLIED, default REAL pending Gate 1 | inputs L50-54; `LoadAxis()` L520-585; `TickChartMsc()` L474-482; mapping CSV `axismap_<custom>.csv` (`real_start_msc;chart_time;chart_time_str;empty`) written per bar | SYNTHETIC needs two anchors (chart origin `AxisBase`, real origin `AxisOrigin`); auto values are persisted in GlobalVariables and in the CSV header and re-read on restart (GV → CSV → fresh). Fresh chart origin = next-minute+1 so synthetic times never collide with real-time ticks already in the symbol. `WriteEmptyBars` default false; `MaxEmptyBarsPerGap` 600 caps weekend gaps |
| F11 consistent tick times | APPLIED | L736-741 `o.time_msc = cm; o.time = cm / 1000` (as received in REAL, both remapped in SYNTHETIC) | `PushTicks` (L55) is a diagnostic off-switch for the funnel only |
| F12 heartbeat | APPLIED | `Heartbeat()` L860-905; every 60 s + `start` + `stop` rows; `MQL5\Files\XPChart\heartbeat_<custom>.csv` | required columns first: `time_server;time_local;actual_symbol;custom_name;interval_s;ticks_captured;bars_written;max_ticks_per_second;empty_slots;copyticks_errors;write_errors;last_tick_age_ms`, then the acceptance helpers `real_volume_seen;bars_tickvol_gt1;spread_min_seen;spread_max_seen;…;spec_pass;spec_fail;spec_not_settable` |
| F13 one instance | APPLIED | `AcquireLock()` L281-318: `GlobalVariableTemp` + `GlobalVariableSetOnCondition` (atomic), refreshed each heartbeat, released on stop; stale after `LockStaleSeconds` (180) | second instance prints `BLOCKED_DUPLICATE_INSTANCE` and exits before creating anything |
| F14 unchanged | APPLIED | enum L15-23; `"Custom\\XPChart"` L334; naming L918 `<parent>_S<n>`; `#property service` L6, `OnStart`, `while(!IsStopped())` L962; `#define Version "2.00"` L10, printed at start L953; `BaseSymbol` default `"XAUUSD"` L43 | `CustomNameSuffix` (L47, default "") is additive: default naming is byte-identical to v1's |

Inputs added beyond the prompt list, all defaulting to the prompted behaviour: `CustomNameSuffix`, `AxisOrigin`,
`MaxEmptyBarsPerGap`, `PushTicks`, `CopyTicksCount`, `LockStaleSeconds`, `FunnelPolls`, `OutputDir`, `PollSleepMs`, `HeartbeatSeconds`.

R6 output path: no tree was visible, so no D-drive convention could be found → `MQL5\Files\XPChart\` (input `OutputDir`).
`XP_Census.ps1` greps the trees for `D:\` literals (`out\ddrive_convention.txt`); an MQL5 program cannot write outside
`MQL5\Files` without a DLL, so a D-drive landing would be a directory junction on `MQL5\Files\XPChart`, not an engine change.

## 4. Spec sync table

Format printed at every start (Journal) and counted in the heartbeat (`spec_pass;spec_fail;spec_not_settable`):

```
F7 SPEC <property>                     parent=<value>          custom=<value>          PASS | FAIL(set=<bool> err=<code> <name>) | NOT_SETTABLE(err 5306) | NOT_SETTABLE(derived/dynamic, parent shown)
F7 SPEC SYNC done: PASS=<n> FAIL=<n> NOT_SETTABLE=<n>
```

Rows (in order): SYMBOL_DIGITS, SYMBOL_POINT*, SYMBOL_TRADE_TICK_SIZE, SYMBOL_TRADE_TICK_VALUE, SYMBOL_TRADE_TICK_VALUE_PROFIT,
SYMBOL_TRADE_TICK_VALUE_LOSS, SYMBOL_TRADE_CONTRACT_SIZE, SYMBOL_VOLUME_MIN, SYMBOL_VOLUME_MAX, SYMBOL_VOLUME_STEP, SYMBOL_VOLUME_LIMIT,
SYMBOL_TRADE_STOPS_LEVEL, SYMBOL_TRADE_FREEZE_LEVEL, SYMBOL_CURRENCY_BASE, SYMBOL_CURRENCY_PROFIT, SYMBOL_CURRENCY_MARGIN, SYMBOL_TRADE_MODE,
SYMBOL_TRADE_CALC_MODE, SYMBOL_TRADE_EXEMODE, SYMBOL_FILLING_MODE, SYMBOL_ORDER_MODE, SYMBOL_ORDER_GTC_MODE, SYMBOL_EXPIRATION_MODE,
SYMBOL_CHART_MODE, SYMBOL_SPREAD_FLOAT, SYMBOL_SWAP_MODE, SYMBOL_SWAP_LONG, SYMBOL_SWAP_SHORT, SYMBOL_SWAP_ROLLOVER3DAYS, SYMBOL_MARGIN_INITIAL,
SYMBOL_MARGIN_MAINTENANCE, SYMBOL_DESCRIPTION, SYMBOL_ISIN, SYMBOL_SPREAD*, SYMBOL_CUSTOM*, SYMBOL_SELECT*   (* = shown, never set).

Real table: PENDING_GHOST (paste the Journal block here after the smoke). Simulated run (stub terminal that refuses
SYMBOL_SPREAD_FLOAT and recomputes SYMBOL_TRADE_TICK_VALUE): `PASS=30 FAIL=1 NOT_SETTABLE=5`, proving that all three
branches print and count. Acceptance is `FAIL=0`; a FAIL row on the real terminal is a finding for the port stage,
not something v2 hides.

## 5. Smoke receipt: PENDING_GHOST

Run steps (SMOKE_TERMINAL = `<Ghost fills: terminal folder / broker>`):
1. `powershell -NoProfile -ExecutionPolicy Bypass -File tools\XP_Census.ps1` → `tools\out\` (hashes, divergences, deployment map, compilers).
2. `powershell -NoProfile -ExecutionPolicy Bypass -File tools\XP_Compile.ps1` → `tools\out\build\XP ChartEngine v2.ex5`, `XP_AxisCheck.ex5`, compile logs. Target 0 warnings; list any that remain in §9.
3. Gate 1 (§1) on the existing `*_S1` symbol → choose `TimeAxis`.
4. Copy `XP ChartEngine v2.ex5` into `<terminal data>\MQL5\Services\`. Terminal → Navigator → Services → right-click → Refresh →
   right-click `XP ChartEngine v2` → Add service. Inputs: `BaseSymbol=XAUUSD`, `Timeframe=S1`, `TimeAxis=<Gate 1>`,
   `CustomNameSuffix=""` (REAL) or `"_v2"` (SYNTHETIC on a terminal that already has a v1 `XAUUSD_S1`), everything else default. OK. (Ghost's click, R5.)
5. Journal/Experts, in this order: `F6 candidate rank=…` lines → `F6 base chosen … SymbolSelect=true` → `custom symbol CREATED|REUSED` →
   the `F7 SPEC` table → `F10 axis=…` → `F9 …` → `XP ChartEngine Active: … | v2.00 …` → `FUNNEL poll=1..20 CopyTicks=<n> err=0` →
   `FUNNEL CustomTicksAdd ok=…` / `FUNNEL CustomRatesUpdate ok=…` → `HEARTBEAT run` every 60 s.
6. After ≥10 minutes in market hours: `MQL5\Files\XPChart\heartbeat_XAUUSD_S1.csv` and `XP_AxisCheck` on the v2 symbol.

Acceptance (from the heartbeat CSV, last row minus `start` row):

| Criterion | Column / receipt | Threshold |
|---|---|---|
| bars_written ≥ 500/600 slots | `bars_written` | ≥ 500 after 10 min (REAL: also `empty_slots` ≤ 100) |
| max_ticks_per_second > 1 | `max_ticks_per_second` | > 1 |
| tick_volume not all 1 | `bars_tickvol_gt1` (closed bars with >1 tick) | > 0 |
| spread not constant | `spread_min_seen` ≠ `spread_max_seen` | true |
| spec table all PASS or NOT_SETTABLE | `spec_fail` + Journal table | 0 |
| write_errors = 0 | `write_errors` (and `copyticks_errors`) | 0 |
| AxisCheck on v2 symbol matches TimeAxis | `XP_AxisCheck VERDICT` | REAL → `SECONDS_AXIS_REAL`; SYNTHETIC → `M1_AXIS` with delta 60 |

Receipt slot:
```
heartbeat last row: ______________________________________________
AxisCheck v2 symbol: ____________________________________________
Journal F7 block: attached / not
```

ZERO-RESULT CONTINGENCY (zero bars or zero ticks = broken until proven). The funnel is already instrumented — read it top-down and
stop at the first blocking value:
1. `F6 candidate` lines (none → `BLOCKED_NO_BASE_SYMBOL`) → 2. `F6 base chosen … SymbolSelect=` → 3. `FUNNEL poll=k CopyTicks=<n> err=<e>`
(n stays 0 while the parent ticks → set `CopyTicksCount=4000` and retry; n=-1 → `copyticks_errors`, code printed → `BLOCKED_NO_TICKS`) →
4. `FUNNEL CustomRatesUpdate ok=` / `FUNNEL CustomTicksAdd ok=` and `XP ChartEngine v2 ERROR:` lines with `err=<code> <name>`
(`BLOCKED_CUSTOM_WRITE` after 20 consecutive failures; try `PushTicks=false` to separate the tick path from the bar path).
ONE swap allowed: `BaseSymbolOverride=<other gold variant>` or another terminal. Still zero → report the first blocking condition with its value and continue with the remaining items. No third configuration.

## 6. Lineage sweep

This repository (run here with the same patterns as `tools\XP_LineageSweep.ps1`):

| file | class | P1 polling loop | P2 tick_volume=1 | P3 StringFind first-match | P4 TimeCurrent anchor | P5 unchecked Custom* | action |
|---|---|---|---|---|---|---|---|
| `XPChart\XP ChartEngine.mq5` (v1) | CHARTENGINE_CLONE (the original) | L73 + L112 | L95 | L38 | L77 | L59, L99, L107 | v2 delivered |
| `XPChart\XP ChartEngine v2.mq5` | PARTIAL (report-only) | no — `SymbolInfoTick` only at start (L238 ranking, L938 cursor seed) | — | — | — | — | none |
| `XPChart\XP_AxisCheck.mq5` | CLEAN | — | — | — | — | — | none |

Host trees (Codex, TradingSystems, every `MQL5\Services`): PENDING_GHOST → `tools\XP_LineageSweep.ps1` → `out\lineage_sweep.md` / `.csv`
(path, line, pattern, matched text; named suspects `XPW_MT5_Tick_Publisher.mq5`, the ContinuousCopyTicksRecorder task's recorder, every
`*Recorder*` / `*Observer*` / `*Publisher*` are flagged in the `Suspect` column). Classification rule: `CHARTENGINE_CLONE` = polling loop
(P1) + TimeCurrent anchoring (P4) + unchecked Custom* (P5) → the identical v2 loop is applied as a `<name> v2.mq5` sibling in the next round
(send the file); `PARTIAL` → report line only, proposed fix per pattern: P1 → CopyTicks cursor (F1), P2 → count ticks (F3),
P3 → deterministic candidates (F6), P4 → `tick.time_msc` slot (F2), P5 → check return + `GetLastError` + rate-limited print + fail limit (F8).

## 7. Reference verification (F1: "verify CopyTicks from/count semantics before relying on them")

`www.mql5.com` is blocked from this run. What could be confirmed from reference excerpts returned by web search, and what could not:

| Item | Status | Source / consequence |
|---|---|---|
| `CopyTicks` `from` = left border with the minimum time, ticks counted forward from it; `from=0` = now, counted backwards | CONFIRMED (excerpt of the CopyTicks reference page) | cursor design is correct; ticks at `from` are included → the boundary-ms dedupe is required and implemented |
| First `CopyTicks` call synchronises the tick DB; EAs/scripts (separate thread, as services are) wait ≤45 s, then return what is available and keep synchronising | CONFIRMED (same page) | first poll may take up to 45 s once; never blocks the loop afterwards |
| No `from` and no `count` → last ≤2000 ticks | CONFIRMED | not used (would be a backfill, R3) |
| `count=0` with `from>0` → all ticks from `from` | NOT VERBATIM CONFIRMED | Ghost: read the `count` parameter line at https://www.mql5.com/en/docs/series/copyticks; the `FUNNEL` prints show the truth on the first polls; `CopyTicksCount` input is the switch |
| `CustomTicksAdd` needs the symbol selected in Market Watch; array ascending by `time_msc`; `time_msc` takes precedence over `time` | CONFIRMED (excerpt of the CustomTicksAdd reference page) | v2 selects and verifies (L354-363); pushes are monotone; explains D9 as cosmetic for the tick DB but still fixed (F11) |
| `CustomRatesUpdate` behaviour with second-resolution bar times | NOT VERIFIED — this is Gate 1 | receipt required (§1) |
| Which properties `CustomSymbolSet*` accepts | NOT VERIFIED | runtime set+readback table is the receipt (§4) |
| Whether the terminal accepts custom ticks dated in the future (SYNTHETIC runs 60× real time) | NOT VERIFIED | shows up as `write_errors` / err 5309 in the smoke; `PushTicks=false` keeps bars flowing while it is investigated |

Sources: [CopyTicks reference](https://www.mql5.com/en/docs/series/copyticks), [CustomTicksAdd reference](https://www.mql5.com/en/docs/customsymbols/customticksadd), [CopyTicksRange reference](https://www.mql5.com/en/docs/series/copyticksrange), [MQL5 book: MqlTick arrays](https://www.mql5.com/en/book/applications/timeseries/timeseries_ticks_mqltick), [MQL5 book: adding ticks to custom symbols](https://www.mql5.com/en/book/advanced/custom_symbols/custom_symbols_ticks).

## 8. Validation performed in this run (substitute for compile + smoke, not a replacement)

1. Both `.mq5` files were mechanically translated to C++ against a hand-written stub of the MQL5 API (types, structs, enums, 60 functions)
   and compiled with `g++ -std=c++17 -Wall -Wextra -Wshadow`: 0 errors, 0 warnings for both files. This catches typos, undeclared
   identifiers, wrong argument counts (it caught three missing `CopyRates` array arguments in the first draft) and type mismatches; it cannot
   see MQL5-only diagnostics.
2. The engine was then run in-process against a fake terminal: 100 pre-start ticks + 2000 live ticks (15% same-millisecond, 3.5 s gaps
   every 300 ticks, varying spread), delivered in random-sized chunks so same-ms groups split across polls. Every scenario recomputes the
   expected bars independently and compares.

| Scenario | Proves | Result |
|---|---|---|
| A REAL, create path | F6 exact match beats a Market-Watch-selected variant and the custom `XAUUSD_S1` is never a candidate; name/path/origin (F14); F7 table prints PASS/FAIL/NOT_SETTABLE; 2001/2001 ticks pushed in order with consistent `time`/`time_msc` (F1, F11); 111/111 bars with OHLC, tick_volume, MAX spread exactly as recomputed (F2-F5); tick_volume not all 1; spread varies; max_tps 28; heartbeat CSV; lock released | PASS |
| B SYNTHETIC, reuse path | fresh axis = next-minute+1 > all real-time data; off-axis stored bar ignored (F9); every tick and bar remapped exactly per formula and monotone (F10/F11); mapping CSV = header + one row per bar; axis persisted in GlobalVariables; restart re-reads it from GV, then from the CSV when the GV is gone | PASS |
| C REAL, stored bar in the current slot | F9 seed merges open/high/low/tick_volume/spread with the new ticks | PASS |
| D first 25 bar writes + 25 tick writes fail with err 32 | `BLOCKED_CUSTOM_WRITE` after 20 consecutive failures, error name printed, prints rate-limited, retry buffers keep everything: still 2001/2001 ticks and 111/111 bars afterwards (F8) | PASS |
| E lock held 10 s ago | `BLOCKED_DUPLICATE_INSTANCE`, nothing created or pushed (F13) | PASS |
| E2 lock stale (1000 s) | taken over, engine runs | PASS |
| F no exact match | Market-Watch-selected `XAUUSD.crp` beats unselected `XAUUSDm` → `XAUUSD.crp_S1` | PASS |
| G no candidates | `BLOCKED_NO_BASE_SYMBOL`, nothing created | PASS |
| H / H2 override | `BaseSymbolOverride=XAUUSDm` used as is; override to a custom symbol refused | PASS |
| I SYNTHETIC + WriteEmptyBars | gap slots counted and written as flat bars at previous close, chart minutes contiguous (delta 60), ticks still lossless | PASS |
| J S5 | 5-second slots, naming `XAUUSD_S5`, bars exact | PASS |
| K MID basis + MIN spread | bars exact under the alternate basis/mode | PASS |
| L ASK + LAST + manual 15 s | naming `XAUUSD_S15`, bars exact | PASS |
| AxisCheck M1 / seconds / empty histories | verdict arithmetic | `M1_AXIS` / `SECONDS_AXIS_REAL` / `EMPTY` |

## 9. Compile: BLOCKED_NO_COMPILER

Searched here: the entire container filesystem for `metaeditor64.exe` / `terminal64.exe` (none), no Wine. On the host `tools\XP_Compile.ps1`
looks in `-MetaEditor`, then `tools\out\compilers.csv` (from the census), then `%ProgramFiles%`, `%ProgramFiles(x86)%`, `C:\MT5`, `D:\`
(depth 4), and prints `BLOCKED_NO_COMPILER` with the searched paths if nothing is found. It launches only `metaeditor64.exe /compile /log`.
Warnings remaining after Ghost's compile: PENDING_GHOST (list here with reason). Known candidates: `#property strict` is kept from v1 for
parity and is MQL4-only; drop it if the MQL5 compiler flags it.

## 10. OPEN ITEMS FOR THE PORT STAGE

(a) **Axis mode.** If Gate 1 says `M1_AXIS`, the S1 chart is SYNTHETIC: one real second = one chart minute, chart time runs 60× real time.
Every time-based Pine construct (sessions, `timenow`, `time`, bar durations, `timeframe.*`, `barstate.*` timers) must be back-converted through
`axismap_<custom>.csv` (`real_start_msc → chart_time`) or read the real time from the parent symbol; nothing on the custom chart's clock is real.
If Gate 1 says `SECONDS_AXIS_REAL`, bar times are real but MT5 still labels the period M1, so anything keyed on `PERIOD_*` is wrong by 60×.

(b) **Price basis of the TradingView feed** the filter was built on is unknown (TradingView XAUUSD feeds are typically bid or mid depending on
the broker/data source). v2 defaults to BID (matches MT5 native bars and the parent chart) and never changes basis silently; fidelity cannot be
claimed until the TV basis is established and `PriceBasis` set to match. MID is stored unrounded (parent digits, not digits+1).

(c) **Empty bars.** TradingView draws no bar for an interval without ticks; v2 matches that with `WriteEmptyBars=false` (gap → missing bar,
counted in `empty_slots`). Pine indexing (`[1]` = previous bar, not previous second) therefore skips empty seconds exactly as TV does; if the
port needs a bar per second, `WriteEmptyBars=true` writes flat bars capped at `MaxEmptyBarsPerGap` per gap — a fidelity difference to log.

(d) **Trading.** Custom symbols cannot be traded. An EA on `XAUUSD_S1` must send orders on the PARENT (`actual_symbol`, printed at start and
in the heartbeat) and read stops/freeze levels from the parent, not from the custom symbol's synced copies.

(e) SYNTHETIC pushes ticks time-stamped in the future relative to server time; acceptance by `CustomTicksAdd` is unverified (§7).
(f) Reusing a v1 custom name under SYNTHETIC mixes two axes in one symbol; use `CustomNameSuffix`.
(g) The terminal's own background tick synchronisation after the first `CopyTicks` is outside the engine (R3 covers only what the engine requests).
(h) The historic "error 32" is not an MQL5 runtime code (Windows sharing violation = 32 is a hypothesis); v2 now prints the code on every failure.

## 11. Deliverables and Ghost run order

| File | Purpose |
|---|---|
| `XPChart\XP ChartEngine.mq5` | v1 as supplied (reference copy, unchanged) |
| `XPChart\XP ChartEngine v2.mq5` | deliverable |
| `XPChart\XP_AxisCheck.mq5` | Gate 1 script (read-only) |
| `XPChart\P0_REPORT.md` | diagnosis |
| `XPChart\XP_CHARTENGINE_REPORT.md` | this report; receipt slots to fill |
| `XPChart\tools\XP_Census.ps1` | P0.1 + P0.4 + compiler census (read-only) |
| `XPChart\tools\XP_Compile.ps1` | P2 compile via metaeditor64.exe |
| `XPChart\tools\XP_LineageSweep.ps1` | P3 sweep (read-only) |

Order: census → compile → Gate 1 → decide `TimeAxis` → add service (Ghost) → 10-min smoke → AxisCheck on v2 symbol → sweep → fill §1, §4, §5, §6, §9 → line 1 verdict.
