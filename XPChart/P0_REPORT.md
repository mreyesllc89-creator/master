# P0_REPORT — XP ChartEngine v1 diagnosis (no edits)

Prompt: XP_CHARTENGINE_UPGRADE_PROMPT v1 — 2026-09-22. Bucket: PLUMBING. Run mode: FULL.
Environment of this run: Linux container holding only the git repository `mreyesllc89-creator/master`
(one file, `README.md`). The Windows host (Codex tree, TradingSystems tree, the 41 MT5 installs,
metaeditor64.exe, running terminals) is NOT reachable from here. Everything that needs the host is
delivered as a read-only script plus run steps for Ghost, and is marked BLOCKED_* below. Nothing
below is inferred from docs where the prompt demands a receipt.

## P0.1 Census — BLOCKED_NO_LOCAL_TREE (script delivered)

| Item | Status |
|---|---|
| `C:\Users\maynor\Documents\Codex` | not mounted here → `tools\XP_Census.ps1` |
| `C:\Users\maynor\Documents\TradingSystems` | not mounted here → `tools\XP_Census.ps1` |
| `MQL5\Services` of the 41 installs | not mounted here → `tools\XP_Census.ps1` (auto-discovers `*\MQL5\Services`) |
| Base source used for P0.2 / P1 | the v1 text supplied inline in the prompt, saved byte-for-byte as `XPChart\XP ChartEngine.mq5` (LF, no BOM) |
| Base hash (sha256, LF-normalised) | `ddad0226f8d85be1010a452c6b1cb0d943cc70ddd5d63b695b1cee88c55fd9e0` (114 lines) |
| Divergences between copies | UNKNOWN until `XP_Census.ps1` runs; it prints raw + LF-normalised sha256 per copy, groups by hash, and diffs every divergent copy against the newest one and against the hash above |

The census script never writes into any MQL5 folder, never opens `bases\Custom\history`, and never
touches a terminal process (R1). Its output goes to `<script dir>\out\`.

## P0.2 Defect confirmation (line numbers = `XPChart\XP ChartEngine.mq5`, the supplied v1)

| ID | Verdict | Receipt (quoted line) | What it does |
|---|---|---|---|
| D1 | **CONFIRMED** | L77 `datetime current_time = TimeCurrent();` L78 `datetime bar_time = (current_time / interval_s) * interval_s;` | Bar slot comes from the poll-time server clock, not `last_tick.time_msc` (L75 only uses it as a change filter). `TimeCurrent()` is the last server time seen on ANY symbol, so it can even run ahead of this symbol's tick. Ticks near a second boundary land in the wrong bar. |
| D2 | **CONFIRMED** | L73 `if(SymbolInfoTick(actual_symbol, last_tick))` L112 `Sleep(100);` (filter L75 `if(last_tick.time_msc != last_tick_time_msc)`) | Snapshot polling: only the latest tick at each 100 ms poll is seen; all ticks between polls are lost. Gold at 10-50 ticks/s loses most ticks. The L75 filter also drops a tick that shares the millisecond of the previous processed tick. |
| D3 | **CONFIRMED** | L95 `s_bar[0].tick_volume = 1;` | Every bar carries tick_volume 1 regardless of ticks seen. |
| D4 | **CONFIRMED** | L96 `s_bar[0].spread = (int)((last_tick.ask - last_tick.bid) / SymbolInfoDouble(actual_symbol, SYMBOL_POINT));` | Spread = spread of the single polled tick; also truncated with `(int)` instead of rounded (floating error can drop one point). |
| D5 | **CONFIRMED** | L81-L83 `bar_open = last_tick.bid; bar_high = last_tick.bid; bar_low = last_tick.bid;` L87-L88 `bar_high = MathMax(bar_high, last_tick.bid); bar_low = MathMin(bar_low, last_tick.bid);` L94 `s_bar[0].close = last_tick.bid;` | Bid only. The only inputs are L19-L21 (`BaseSymbol`, `Timeframe`, `ManualSeconds`); no basis input exists. |
| D6 | **CONFIRMED** | L36 `for(int i=0; i<SymbolsTotal(false); i++) {` L37 `string sym = SymbolName(i, false);` L38 `if(StringFind(sym, BaseSymbol) >= 0) {` L39-L40 `actual_symbol = sym; break;` | Iterates ALL symbols including custom ones, matches the substring anywhere, takes the first hit in terminal list order. With several gold variants the winner depends on list order. On restart the engine's own output `XAUUSD_S1` matches `XAUUSD` → `actual_symbol = "XAUUSD_S1"` → `custom_name = "XAUUSD_S1_S1"` (a custom symbol fed from a custom symbol). Note also L19 default `BaseSymbol = "BTCUSD"`, not XAUUSD. |
| D7 | **DIFFERENT** | L53 `if(!SymbolSelect(custom_name, true)) {` L54 `if(!CustomSymbolCreate(custom_name, "Custom\\XPChart", actual_symbol)) {` L58 `SymbolSelect(custom_name, true);` L59 `CustomSymbolSetInteger(custom_name, SYMBOL_DIGITS, (int)SymbolInfoInteger(actual_symbol, SYMBOL_DIGITS));` L60 `}` | In this copy the `SYMBOL_DIGITS` set (L59) sits INSIDE the create branch. The reuse path (SymbolSelect true) sets nothing at all — worse than "only digits". Either way: no spec re-sync on reuse. Other copies may differ; census will show. |
| D8 | **CONFIRMED** | L99 `CustomRatesUpdate(custom_name, s_bar);` L107 `CustomTicksAdd(custom_name, tick_to_push, 1);` | Both return values discarded, no `GetLastError`, no counter; the loop re-polls every 100 ms → silent failure loop (the error-32 loop). L58 `SymbolSelect` return is also ignored, and `CustomTicksAdd` requires the custom symbol to be selected in Market Watch. |
| D9 | **CONFIRMED** | L103 `tick_to_push[0] = last_tick;` L104 `tick_to_push[0].time = current_time;` | `.time` is overwritten with `TimeCurrent()` while `.time_msc` keeps the received value → the two fields disagree. |
| D10 | **CONFIRMED** | L66-L68 `double bar_open=0, bar_high=0, bar_low=0; datetime last_bar_time=0; long last_tick_time_msc = 0;` L80-L85 `if(bar_time != last_bar_time) { bar_open = last_tick.bid; ... last_bar_time = bar_time; }` | After a restart `last_bar_time` is 0, so the first tick opens a fresh bar from that one tick and L99 overwrites the stored bar for that slot. The stored bar is never read back. |

Additional findings recorded in passing (not in the D-list, no action unless F-items cover them):

| ID | Line | Note |
|---|---|---|
| E1 | L19 | default `BaseSymbol = "BTCUSD"`; v2 default is `"XAUUSD"` (F14). |
| E2 | L73 | parent symbol is never `SymbolSelect`-ed; if it is not in Market Watch, `SymbolInfoTick` returns false/stale forever with no message. |
| E3 | L53-L57 | a `SymbolSelect` failure for an EXISTING custom symbol falls into `CustomSymbolCreate`, which then fails with "exists" and the service exits. |
| E4 | L7 | `#property strict` is an MQL4 property; ignored by the MQL5 compiler. Kept in v2 for parity. |

## P0.3 GATE 1 — TIME-AXIS TRUTH — PENDING_RECEIPT (script delivered)

MT5 stores custom-symbol history as M1 bars; whether `CustomRatesUpdate` with second-resolution
`time` values yields one bar per second or collapses into the minute bar is exactly what v1 relies
on and what nobody has measured. No verdict is issued here.

Deliverable: `XPChart\XP_AxisCheck.mq5` (script, read-only). It runs
`CopyRates(symbol, PERIOD_M1, 0, 500)`, prints and writes:
histogram of consecutive bar-time deltas, count of bars whose time is not on a minute boundary,
first/last bar time, bar count, `Bars()` total, plus the last N ticks of the custom tick DB
(`CopyTicks(symbol, ..., 0, N)`, read-only) with their time_msc span.
Verdict rule printed by the script:

| Verdict | Rule |
|---|---|
| `SECONDS_AXIS_REAL` | modal delta == ExpectedIntervalSeconds, or any bar time not on a minute boundary |
| `M1_AXIS` | modal delta == 60 and every bar time is minute-aligned |
| `EMPTY` | 0 bars |
| `OTHER_AXIS(<delta>)` | anything else — report the histogram |

Ghost run: SMOKE_TERMINAL → open any chart → Navigator → Scripts → XP_AxisCheck → input
`CheckSymbol` = the existing `*_S1` symbol (e.g. `XAUUSD_S1`), `ExpectedIntervalSeconds` = 1 →
copy the `XP_AxisCheck VERDICT:` line from Experts/Journal and the file
`MQL5\Files\XPChart\axischeck_<symbol>.csv` into `XP_CHARTENGINE_REPORT.md` § Gate 1.

What the verdict changes in v2: the `TimeAxis` input default. v2 ships with `TimeAxis = REAL`
(v1 behaviour, no silent change of axis). If the receipt says `M1_AXIS`, Ghost re-pins the default
to `SYNTHETIC` (one-line change, marked `GATE1_DEFAULT` in the source) or passes it as an input.

## P0.4 Deployment map — BLOCKED_NO_LOCAL_TREE (script delivered)

`tools\XP_Census.ps1` produces `out\deployment_map.md` with, per terminal data folder found:
services present (`MQL5\Services\*.ex5|*.mq5` with hashes), custom symbols under
`bases\Custom\XPChart` (directory listing only — names and sizes, files are not opened),
the last `XP ChartEngine Active` line from `logs\*.log` (opened read-only with share-read/write so a
running terminal is not disturbed), and every `metaeditor64.exe` found (compiler census for P2).

## P0 exit state

- RUN_MODE = FULL → proceeding to P1 on the supplied v1 source.
- Receipts still owed by Ghost before any verdict word other than BLOCKED_*: census hashes,
  Gate 1 axis verdict, deployment map, compile log, 10-minute smoke heartbeat CSV.
