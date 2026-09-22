RECONCILED | 2 regressions found, both fixed in v2.01 | DECISION: hold — smoke v2.01 on 5FFA5 first, then roll to 86AD, 73B7, 9BB1

# XP_CHARTENGINE_UPGRADE v1.1 — RECONCILE BEFORE SHIP (2026-09-22)

Inputs: host census of 2026-09-22 09:37 (`census/2026-09-22/`), the two host sources
(`XP ChartEngine.mar-73B7.mq5`, `XP ChartEngine.aug-5FFA5.mq5`), v2.00 as pushed earlier.
Output: `XP ChartEngine v2.mq5` re-issued as **v2.01** (the union). Everything below is receipt-backed.

## 0. Premise correction: the capability-rich variant is the AUGUST copy, not March

| Copy | Terminals | Written | Bytes | norm sha256 | Content |
|---|---|---|---|---|---|
| March | 73B7A242…, 9BB124B7… | 2026-03-20 06:36 | 4217 | `fc322fd2217401b0…` (the hash quoted in the task, `fc7322fd…`, is a transcription of this one) | prompt base + 6-line Coders Guru header + `link "https://www.xpworx.com"`, no trailing newline. **No lock, no FillRateBar, no UpdateRatesEveryTick.** Verified: stripping the header and diffing against the prompt base leaves only the `link` line. |
| August | 5FFA5681… (`92723dd9…`), 86ADC2D1… (`d7d776d4…`) | 2026-08-24 11:54 / 12:12 | 7282 / 7280 | two hashes, but `divergences.md` shows the only difference is one leading space on `tick_to_push[0] = last_tick;` (L206) | lock + heartbeat, FillRateBar, bar_tick_volume++, bar_spread, bar_close, UpdateRatesEveryTick, bar_ready + final flush |
| Prompt base | (none on host) | — | 3664 | `ddad0226…` | March minus header |

So the regression risk was v2.00 losing something the **August** copy has. The task's capability list is exactly the August feature set; the reconcile below is against `XP ChartEngine.aug-5FFA5.mq5` (line numbers = that file). The March copy is reconciled in §5 as the v1 it is.

## 1. Capability table: v2 vs August

| Capability | August lines | v2.00 | v2.01 | Class |
|---|---|---|---|---|
| Lock acquire with owner token, atomic `GlobalVariableSetOnCondition` | L37-67 | different scheme (Temp GV, no owner token) | August scheme adopted, `AcquireCustomSymbolLock()` L290-332 | **ABSENT_FROM_V2 → fixed** (regression 1) |
| Lock heartbeat key touched every second | L69-73, L154-159 | refreshed every 60 s | `TouchCustomSymbolLock()` L334, called once per second in the loop | part of regression 1, fixed |
| Staleness reclaim after 30 s | L46-55 | 180 s | `LockStaleSeconds` default 30 (L62) | part of regression 1, fixed |
| Release only if still the owner | L75-85 | unconditional delete (could clear another instance's lock after a takeover) | `ReleaseCustomSymbolLock()` L340-356, owner-checked | part of regression 1, fixed |
| `FillRateBar()` writes close **and** real_volume | L87-97 (real_volume hardcoded 0) | `CurrentBar()` writes all 8 fields, real_volume = Σ tick volume when the feed has it | unchanged | PRESENT_IN_V2_BETTER |
| `bar_tick_volume++` real tick count | L195 | `b_ticks++` over every tick delivered by CopyTicks (August only counts polled ticks) | unchanged | PRESENT_IN_V2_BETTER |
| `bar_spread` per bar | L167, L196 (= spread of the last polled tick, truncated) | `SpreadMode` LAST/MAX/MIN, rounded | unchanged | PRESENT_IN_V2_BETTER (LAST reproduces August) |
| `bar_close` tracked | L193 | `b_close` | unchanged | PRESENT_IN_V2_EQUIVALENT |
| `input UpdateRatesEveryTick` (default false → bars written only on close) | L28, L179-181, L198-202 | current bar written every poll, no switch | input added L63; `FlushPending(bool)` L784; loop L1041-1042 | **ABSENT_FROM_V2 → fixed** (regression 2). Default false kept from August: 1 `CustomRatesUpdate` per bar instead of up to 20/s |
| `bar_ready` + final bar flush before exit | L148, L169-178, L218-222 | `bar_active` + `FlushPending()` at shutdown | `FlushPending(true)` L1064 | PRESENT_IN_V2_EQUIVALENT |
| Duplicate-instance message | L60 | `BLOCKED_DUPLICATE_INSTANCE` | same, with owner and heartbeat age | PRESENT_IN_V2_EQUIVALENT |
| Explicit count in `CustomRatesUpdate(.., 1)` | L181, L201, L221 | arrays sized exactly | unchanged | PRESENT_IN_V2_EQUIVALENT |
| Lock released on create failure | L132 | `ReleaseLock()` on every early exit | `ReleaseCustomSymbolLock()` on every early exit | PRESENT_IN_V2_EQUIVALENT |
| F1 CopyTicks cursor, F2 tick.time_msc slots, F4/F5 inputs, F6 deterministic base, F7 spec sync, F8 checked writes + fail limit, F9 restart seed, F10 axis modes, F12 heartbeat CSV, funnel prints, AxisCheck | — | present | present | ABSENT_FROM_AUGUST (new in v2) |

Regressions found: **2** (lock scheme, UpdateRatesEveryTick). Both fixed in v2.01. Nothing in August was sounder than v2 except the lock, which is now August's.

## 2. Lock: August's scheme ships, F13's own scheme is withdrawn

Reasons, in order of weight:
1. **Owner token.** August stores an owner id in the lock and releases only if it still matches (L80-84). v2.00 deleted the lock unconditionally, so instance A, having lost its lock to B after a stall, would have cleared B's lock on exit. Scenario E2 now proves the owner check.
2. **Same key names as the copies already deployed.** `XPChartEngine.Lock.<custom>` and `.Heartbeat` are what the August service uses on 5FFA5 and 86AD. During the rollout an August instance and a v2.01 instance on the same terminal therefore exclude each other; v2.00's `XPC2.lock.*` would not have.
3. **Faster, cheaper reclaim.** Heartbeat touched once per second (one `GlobalVariableSet`), stale after 30 s, instead of 60 s refresh / 180 s stale.
4. **Restart-safe either way.** A persistent GV survives a terminal restart with a stale heartbeat, so it is reclaimed on the next start; nothing is lost by dropping `GlobalVariableTemp`.

Two refinements kept, both marked in the source: a lock **without** a heartbeat key counts as stale (August L49-54 would never reclaim such a lock — a crash between L58 and L65 would deadlock the name forever), and the reclaim uses `GlobalVariableSetOnCondition(lock, 0, current_owner)` instead of an unconditional set so two simultaneous reclaimers cannot both proceed. Scenario E4 covers the first.

## 3. v2.01 re-issue and harness

Changes to `XP ChartEngine v2.mq5`: version 2.01; lock functions replaced as above; `LockStaleSeconds` 30; `UpdateRatesEveryTick` input; `FlushPending(include_current)`; heartbeat touch in the main loop; startup print shows the new input. Nothing else moved. C++ stub lint: 0 errors, 0 warnings.

| Scenario | Result |
|---|---|
| A–D, F–L (as before: create/reuse, synthetic axis + restart, seed, write failures, base ranking, override, empty bars, S5, MID/MIN, ASK/LAST/15 s) | PASS |
| E lock held, heartbeat 10 s old | `BLOCKED_DUPLICATE_INSTANCE`, nothing created — PASS |
| E2 lock held, heartbeat 1000 s old → reclaimed; then another owner takes the lock and our release leaves it untouched | PASS |
| E4 lock held, no heartbeat key → treated as stale, engine runs | PASS |
| M `UpdateRatesEveryTick=true` | bars exact, >200 rate writes — PASS |
| N default (close-only) | bars exact, ≤120 rate writes for 111 bars (one per close + final flush) — PASS |

17/17.

## 4. Deploy plan: four service copies, four terminals

All under `C:\Users\maynor\AppData\Roaming\MetaQuotes\Terminal\<ID>\MQL5\Services\`. Every terminal listed has **no** `bases\Custom\XPChart` directory and **no** `XP ChartEngine Active` line in its newest five logs: none of the four services has run recently, and no `*_S1` custom symbol exists anywhere.

| Terminal ID | Current `.mq5` (norm) | Current `.ex5` (raw) | Version on disk | Order | Action |
|---|---|---|---|---|---|
| `5FFA568149E88FCD5B44D926DCFEAA79` | `92723dd9…` | `00e9f84b…` (2026-08-24 11:54) | August (the error-32 terminal) | 1 — SMOKE_TERMINAL | copy `XP ChartEngine v2.ex5`; Ghost adds the service; 10-min acceptance per main report §5 |
| `86ADC2D106E3946A8F8D9E6D2FD89531` | `d7d776d4…` | `0a3f493d…` (2026-08-24 12:12) | August (1-space variant) | 2 | after smoke passes |
| `73B7A2420D6397DFF9014A20F1201F97` | `fc322fd2…` | `a68c55b4…` (2026-03-20) | March (= v1) | 3 | after smoke passes |
| `9BB124B7D418C7FB69DF2865535BA9BF` | `fc322fd2…` | `a68c55b4…` (2026-03-20) | March (= v1) | 4 | after smoke passes |
| other 7 data folders | — | — | no service | — | none |

Per terminal: (1) `tools\XP_Compile.ps1` once, same `.ex5` for all four; (2) copy it in as a **new** file `XP ChartEngine v2.ex5` next to the old one, nothing deleted (R1); (3) if the old service shows as running, Ghost stops it by hand — the shared lock name also guarantees only one of the two can own `<parent>_S1`; (4) Navigator → Services → Refresh → Add `XP ChartEngine v2` with `BaseSymbol=XAUUSD`, `Timeframe=S1`, other inputs default; (5) confirm the `XP ChartEngine Active: … | v2.01` line and the first `HEARTBEAT run` in the Journal; (6) record the terminal ID and the `.ex5` sha256 in this table.

Gate 1 consequence: with no `*_S1` symbol on any terminal, the receipt cannot come from an existing symbol. Run v2.01 in `REAL` on 5FFA5 for two minutes, then `XP_AxisCheck` on `XAUUSD_S1` (main report §1, EMPTY branch), and only then decide `TimeAxis` for the smoke proper.

## 5. D1–D10 reconfirmed against both host variants

March copy: identical to the prompt base after the header, so every verdict from `P0_REPORT.md` holds with line numbers shifted by +6 (D1 L83-84, D2 L79/L118, D3 L101, D4 L102, D5 L87-89/93-94/100, D6 L42-48, D7 L59-66, D8 L105/L113, D9 L109-110, D10 L72-74/86-91).

August copy (`XP ChartEngine.aug-5FFA5.mq5`):

| ID | Verdict vs August | Receipt |
|---|---|---|
| D1 | CONFIRMED | L165 `datetime current_time = TimeCurrent();` L166 `datetime bar_time = (current_time / interval_s) * interval_s;` |
| D2 | CONFIRMED | L161 `if(SymbolInfoTick(actual_symbol, last_tick))` L215 `Sleep(100);` (L163 msc filter) |
| D3 | **NOT_PRESENT** | L195 `bar_tick_volume++;` L94 `rates[0].tick_volume = volume;` — real count of polled ticks (still loses the ticks D2 drops) |
| D4 | DIFFERENT | a per-bar field exists (L145 `int bar_spread=0;`) but L196 `bar_spread = current_spread;` overwrites it with the last polled tick's spread every tick, and L167 still truncates with `(int)` |
| D5 | CONFIRMED | L170-173 `bar_open = last_tick.bid; … bar_close = last_tick.bid;` L192-194 |
| D6 | CONFIRMED | L109-115 same `StringFind(sym, BaseSymbol) >= 0` first-match loop |
| D7 | DIFFERENT | L136 `CustomSymbolSetInteger(… SYMBOL_DIGITS …)` only inside the create branch (L129-137); reuse path sets nothing |
| D8 | CONFIRMED | L181, L201, L221 `CustomRatesUpdate(custom_name, s_bar, 1);` L210 `CustomTicksAdd(custom_name, tick_to_push, 1);` L135 `SymbolSelect(custom_name, true);` — all unchecked |
| D9 | CONFIRMED | L206 `tick_to_push[0] = last_tick;` L207 `tick_to_push[0].time = current_time;` |
| D10 | DIFFERENT | L148 `bool bar_ready=false;` L169-178: the first tick after a restart opens a fresh bar with `bar_tick_volume = 0`; nothing is read back, and with `UpdateRatesEveryTick=false` the partial bar overwrites the stored one at the next boundary (L179-181) instead of every tick |

August-only findings: A1 a lock whose heartbeat key is missing is never reclaimed (L49-54) — fixed in v2.01 §2; A2 with the default `UpdateRatesEveryTick=false` the chart only receives a bar when it closes, so the live bar is whatever the terminal builds from `CustomTicksAdd` — kept as the default, documented as a fidelity item.

## 6. Repo additions

`XP ChartEngine.aug-5FFA5.mq5`, `XP ChartEngine.mar-73B7.mq5` (host copies, CRLF preserved, hashes verified against the census), `census/2026-09-22/` (census_files.csv, deployment_map.md, divergences.md).
