# Strategy Tester and optimisation

## Modelling modes
| Mode | Use |
|------|-----|
| Every tick based on real ticks | Most accurate, needs broker tick history; slow |
| Every tick | Generated ticks from M1 OHLC; standard for stop/limit order strategies |
| 1 minute OHLC | 4 price points per M1 bar; fast, fine for bar-close strategies with wide stops |
| Open prices only | One tick per bar; only valid when the EA acts strictly on new bars and uses no intrabar stops |
| Math calculations | `OnTester` only, no ticks |

Pine's default fill model (bar-by-bar, no magnifier) is closer to "1 minute OHLC" or
"Open prices only"; MT5 "Every tick" is more realistic for stop entries and SL/TP in the
same bar.

## Settings that change results
- **Spread**: "Current" uses the live spread for all history; set a fixed spread in points
  that matches the strategy's `spreadPoints` input when comparing with TradingView.
- **Delay**: execution delay in ms; keep 0 for parity tests, add realistic delay for live
  expectations.
- **Deposit / leverage / currency**; **Profit in pips** toggle; **Date range**.
- Margin and swaps come from the symbol specification; commission from the broker or an
  input you add.

## Inputs for optimisation
- Each `input` gets Start/Step/Stop in the Inputs tab; tick the ones to vary. `sinput`
  cannot be optimised.
- Keep the grid small: 3 parameters × 10 values = 1000 passes. Use genetic optimisation
  beyond ~10k combinations.
- Criteria: Balance max, Profit Factor, Expected Payoff, Drawdown min, Recovery Factor,
  Sharpe, Custom (`OnTester`), Complex Criterion.
- Forward testing: set "Forward: 1/2 or 1/3" so each pass is re-run on unseen data; read
  the Forward tab, not the Back tab.

## OnTester custom criterion
```mql5
double OnTester()
{
   double trades = TesterStatistics(STAT_TRADES);
   if(trades < 30) return 0;                                 // reject small samples
   double pf  = TesterStatistics(STAT_PROFIT_FACTOR);
   double dd  = TesterStatistics(STAT_EQUITY_DDREL_PERCENT); // relative DD %
   double net = TesterStatistics(STAT_PROFIT);
   if(net <= 0 || dd <= 0) return 0;
   return net / dd * MathMin(pf, 3.0);
}
```
Other stats: `STAT_INITIAL_DEPOSIT, STAT_GROSS_PROFIT, STAT_GROSS_LOSS, STAT_MAX_PROFITTRADE,
STAT_EXPECTED_PAYOFF, STAT_SHARPE_RATIO, STAT_RECOVERY_FACTOR, STAT_BALANCE_DD,
STAT_EQUITY_DD, STAT_PROFIT_TRADES, STAT_LOSS_TRADES, STAT_CONPROFITMAX, STAT_MAX_CONLOSSES`.

## Reading results
- Journal tab for your `Print` output and server-side rejections.
- Backtest tab → right-click → Report (HTML/XML) and "Save as" the deals list for
  comparison with TradingView's "List of Trades".
- Equity graph: a smooth line with many trades is the thing to look for; a hockey stick
  from one trade is noise.

## Tester-aware code
```mql5
bool inTester = MQLInfoInteger(MQL_TESTER);
bool optimising = MQLInfoInteger(MQL_OPTIMIZATION);
if(!optimising) Print(...);   // avoid logs during optimisation (slow)
if(MQLInfoInteger(MQL_VISUAL_MODE)) DrawObjects();
```
`TesterStop()` ends a pass early; `TesterWithdrawal(amount)` simulates withdrawals.
`INIT_PARAMETERS_INCORRECT` from `OnInit` skips invalid parameter combinations
(e.g. fast ≥ slow) and saves optimisation time.

## Command-line runs (automation)
Create `tester.ini`:
```ini
[Tester]
Expert=Experts\FlashGold\FlashGold_v5.ex5
Symbol=BTCUSD
Period=M5
Model=1                 ; 0 every tick, 1 1-minute OHLC, 2 open prices, 3 math, 4 real ticks
Optimization=0          ; 0 off, 1 slow complete, 2 fast genetic, 3 all symbols
FromDate=2024.01.01
ToDate=2024.12.31
Deposit=10000
Leverage=100
Report=reports\flashgold_2024
ReplaceReport=1
ShutdownTerminal=1
ExpertParameters=flashgold.set
```
Run: `terminal64.exe /config:C:\path\tester.ini`. The `.set` file (saved from the tester's
Inputs tab) carries input values. Compile first with
`metaeditor64.exe /compile:"C:\...\FlashGold_v5.mq5" /log`. The `shell-scripting` skill has
a PowerShell wrapper.
