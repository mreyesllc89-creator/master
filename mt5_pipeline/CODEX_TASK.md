# CODEX TASK - MT5 tick validation of xpw_engine.py (BTCUSD, VT Markets)

Project folder: `C:\Users\maynor\Documents\Codex\2026-07-12\i`
Existing files: xpw_engine.py, mexc_data.py, backtest.py, shadow.py, shadow_report.py.
**Read all of them first. Change nothing in them.** All new work is in the
files of this folder (`mt5_pipeline\`). Copy them into the project folder
next to xpw_engine.py before running.

Work one step at a time. Finish and report each step before starting the
next. **Do not optimize anything at any step.** Never tune a parameter,
never pick a "better" offset, range or quantity than the one the rules give.

MT5: use the running VT Markets terminal (it holds the BTCUSD tick history
forced on 2026-10-09). If more than one terminal is open, pass that
terminal's `terminal64.exe` path with `--terminal`.

Python packages needed: MetaTrader5, pandas, numpy, pyarrow (openpyxl only
if the TradingView export is .xlsx).

## STEP 0 - bind the adapter (once, before Step 2)

`engine_adapter.py` is the only file that imports xpw_engine. Run:

    python engine_adapter.py --probe

It prints the engine's functions, classes, signatures and every constant
whose name mentions commission/slippage/qty/spread/leverage/trail/stop.
Then open engine_adapter.py and make the three BIND blocks match the real
engine:

- BIND 1: the entry point that turns an M30 OHLC DataFrame into signals.
- BIND 2: `_normalise()` -> columns `enter_long, enter_short, exit_long,
  exit_short` (bool, one row per bar, aligned to bars["time"]). The exit
  flags are the END-label / "exit once" signals of the Pine strategy, not
  trailing-TP exits.
- BIND 3a/3b: the names of the trail/SL settings and the cost constants.
  If a name is not found the Pine v2.4 defaults are used and the report
  says so.

Smoke test: `python engine_adapter.py --bars data\mt5\BTCUSD_M30.csv`
(after Step 1) must print non-zero enter counts.

## STEP 1 - mt5_data.py

    python mt5_data.py --symbol BTCUSD --start 2022-01-01 [--terminal "<path>"]

Writes `data\mt5\BTCUSD_spec.json` (digits, point, tick size, stops level,
freeze level, contract size, volume min/max/step, filling mode, account
currency - nothing hardcoded anywhere later), `BTCUSD_M30.csv`,
`BTCUSD_ticks.parquet` (CSV fallback if pyarrow is missing), and
`outputs\step1_report.md`.
Report: bar count, tick count, first and last timestamp, every tick gap
longer than 2 hours. Times are broker server time, unconverted.

## STEP 2 - parity_mt5.py

    python parity_mt5.py --tv-utc-offset-hours <H>

`<H>` = hours to ADD to the TradingView export times to reach MT5 server
time (chart timezone -> broker time). Determine it from the chart settings
and the broker's server offset; do not search for the offset that maximises
the match rate. The report's "offset check" row shows the first TV signal
bar next to the nearest MT5 bar and the fill prices, so a wrong offset is
visible. Fix the offset from evidence, rerun once.
Report: match rate, trade count on each side, first ten mismatches with
bar time and cause.

## STEP 3 - cost audit, then backtest_ticks.py

First, read-only, before any tick run:

    python cost_audit.py

Fill the two MANUAL items in `outputs\cost_audit.md` by reading the quoted
source lines of xpw_engine.py:
  4. the quantity used by entries is the fixed contract quantity and no
     calcQty / risk-percent path overrides it;
  5. no spread input is charged on top of bid/ask tick fills.
Report the audit (all five items + the SIBLING CHECK section) **before**
the first run.

Then:

    python backtest_ticks.py --commission-pct 0.02 --slippage-usd 5 --leverage 10 --qty <contracts>

`<contracts>` = the fixed quantity the audit confirmed. Fill rule and cost
model are in the file's docstring. Report: profit factor, win rate, max
drawdown, trade count, largest single winner as a share of net profit,
same-bar trade count (entries that exit inside the same M30 bar are flagged
in `outputs\ticks_trades.csv`), break-even slippage per side.

## STEP 4 - final report

    python final_report.py

`outputs\final_report.md` opens with one line: verdict word, the single
deciding number (tick-replay profit factor), decision yes or no. Then the
three step reports. Stop there.

## ZERO-RESULT CONTINGENCY (built into every script)

A zero-trade, zero-tick or zero-signal result is a broken run until proven
true. Each script allows at most ONE data-range swap (`--fallback-start`,
default 2024-01-01). If the rerun also zeros, the script instruments the
decision funnel (signals fired, orders attempted, first blocking condition
with its value) and names the defect (BLOCKED_NO_TICKS, BLOCKED_NO_BARS,
BLOCKED_NO_SIGNALS, BLOCKED_NO_TRADES, BLOCKED_NO_TERMINAL). Report it and
continue with the next step. **Never try a third range.**

## SIBLING CHECK

If the cost audit or the parity check finds a defect in the engine or its
cost path, `outputs\cost_audit.md` already lists every matching line in
backtest.py and shadow.py. Report where else the defect appears. Report
only; do not fix.
