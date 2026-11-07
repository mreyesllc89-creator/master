# EA Validation Kit (EVK) v1.0

EVK runs the same validation we used on the XLZC EA on **any** MetaTrader 5 Expert Advisor:
- a **hold-out test**: choose on older data, measure on newer data;
- a rolling **walk-forward**;
- **neighbourhood robustness**;
- **stress tests**;
- a **Monte Carlo** drawdown range;
- an **A/B comparison**, for example a filter off vs on;
- an **HTML report**.

You don't port the EA to Python. MT5's own Strategy Tester runs the EA on your broker's data. EVK records the trades, and a Python tool analyses them.

```
your EA  +  #include <EVK/EVK.mqh>
      │   MT5 Strategy Tester: Optimization over the inputs you choose
      ▼
Common\Files\EVK\<EA>_<symbol>_<time>.csv      (every pass: its inputs + all its trades)
      │
      ▼
python -m evk analyze <file.csv>               → console summary + <file>_report.html
```

## 1. Install

1. Copy `MQL5/Include/EVK/EVK.mqh` into your terminal's `MQL5/Include/EVK/` folder (**File > Open Data Folder**).
2. Install Python 3.9+ with pandas and numpy (`pip install pandas numpy`). Then copy the `evk` folder somewhere, for example next to your CSV files.

## 2. Add EVK to an EA

Add one line after the EA's other `#include` lines:

```mql5
#include <EVK/EVK.mqh>
```

Compile. EVK only reads the tester's deal history; it does not place, change or close trades, and it does nothing on a live chart.

**If the EA already has `OnTester`, `OnTesterInit`, `OnTesterPass` or `OnTesterDeinit`**, put `#define EVK_NO_HANDLERS` before the include. Then call EVK from your own handlers:

```mql5
#define EVK_NO_HANDLERS
#include <EVK/EVK.mqh>

double OnTester()       { /* your code */ return EVK_OnTester(); }
void   OnTesterInit()   { EVK_OnTesterInit(); }
void   OnTesterPass()   { EVK_OnTesterPass(); }
void   OnTesterDeinit() { EVK_OnTesterDeinit(); }
```

If the EA **sends frames of its own** (`FrameAdd`), don't call `EVK_OnTesterPass()`, because it would consume your frames too. Instead, call `EVK_HandleFrame()` for every frame inside your own loop:

```mql5
void OnTesterPass()
  {
   ulong pass; string name; long id; double value; double data[];
   while(FrameNext(pass, name, id, value, data))
      if(!EVK_HandleFrame(pass, name, id, value, data))
        { /* your own frame */ }
  }
```

EVK adds these inputs, in their own group:

| Input | Meaning |
|---|---|
| `EVK_Enable` | Record and export. It only acts in the Strategy Tester. |
| `EVK_Magic` | Only count trades with this magic number (-1 = all). Use it when other EAs or manual trades share the account. |
| `EVK_Criterion` | Value returned to the optimizer when you choose **Custom max**. It is computed even when `EVK_Enable` is false. The default is the worst profit factor across `EVK_Periods` time slices, which favours settings that work in every part of the period. |
| `EVK_MinTrades` | Passes with fewer trades score 0. |
| `EVK_Periods` | Number of time slices for the worst-period criterion. |
| `EVK_RunName` | Prefix of the CSV name (default: the EA's name). |

## 3. Run the optimization in MT5

1. Open the Strategy Tester. Pick the EA, the symbol and the **whole period** you want to study, for example 18 months or more.
2. Set **Modelling** to *Every tick based on real ticks*, the most realistic choice.
3. Set **Optimization** to *Slow complete algorithm* if the grid is small enough; it gives the best robustness analysis. The genetic algorithm also works but tests fewer neighbours.
4. Set **Forward** to **No**. EVK does the out-of-sample split itself, after the run, so you can try several splits without re-running MT5.
5. Set **Criterion** to *Custom max* to rank by EVK's criterion, or keep MT5's own criterion. The CSV is the same either way.
6. In the **Inputs** tab, tick only the inputs to optimize, with start/step/stop values. Keep the grid modest: 50 to 2,000 passes is a good range.
7. Start. MT5 reuses cached results when you re-run an identical optimization, and cached passes send nothing to EVK. **Before re-running the same optimization, delete the files in `<terminal data folder>\Tester\cache`**, or change `EVK_RunName`. EVK prints a warning when it receives no passes.
8. When it finishes, the Journal prints the path of the CSV:
   `[EVK] 640 pass(es) written to <Common Data Folder>\Files\EVK\MyEA_XAUUSD_20261107_153000.csv`

   The Common Data Folder is `C:\Users\<you>\AppData\Roaming\MetaQuotes\Terminal\Common\`.

A **single test** (no optimization) also writes a CSV with that one pass, named `..._single.csv`, which is useful for the stress tests of one setting. Repeated single tests get `_2`, `_3` and so on, so no file is overwritten. A single-test file has no input columns, so note which settings you used. Use local tester agents: frames from MQL5 Cloud agents also work, but a single test on a remote agent writes its file on that machine.

## 4. Analyse

```
python -m evk analyze MyEA_XAUUSD_20261107_153000.csv --split 2026-01-01
```

| Option | Default | Meaning |
|---|---|---|
| `--split DATE` | last 25% of the period | Start of the hold-out. Everything before is used to choose; everything after is the out-of-sample test. |
| `--value` | `auto` | `r` = results in R, which needs a stop loss on every trade; `profit` = money; `auto` = R when available. |
| `--criterion` | `min_period_pf` | How passes are ranked on the training data: `min_period_pf`, `pf`, `net`, `expectancy`, `net_over_dd`. |
| `--min-trades` | 30 | Minimum training trades for a pass to be ranked. |
| `--no-smooth` | off | Rank each pass alone instead of by the median of the pass and its neighbours. Smoothing avoids lucky isolated peaks. |
| `--train / --test` | 6 / 2 | Walk-forward window lengths in months. |
| `--anchored` | off | Walk-forward training always starts at the beginning instead of rolling. |
| `--compare OTHER.csv` | | A second run with the same optimized inputs, for example the EA with a filter switched on. |
| `--labels "A,B"` | `A,B` | Names of the two runs in the comparison. |
| `--out file.html` | next to the CSV | Report path. |

### A/B test of a filter or option

Run the same optimization twice, once with the option off and once with it on. Change only that input; keep everything else identical. Then:

```
python -m evk analyze off.csv --compare on.csv --labels "Without filter,With filter"
```

EVK pairs every pass with its twin and reports how often the option raised the profit factor and the net result, and how many trades it kept.

## 5. Reading the report

- **Verdict.** It says the selection held up only if three things are true:
  - the top picks made on in-sample data stayed profitable out of sample;
  - they did better than the **base rate**, the share of all passes that were profitable out of sample;
  - the walk-forward was profitable.
- **Hold-out.** The pass chosen before the split, and how it did after it. Only the out-of-sample column estimates the future.
- **Walk-forward.** Re-choose on each training window, trade the next test window, and join the test windows. This is the closest backtest to running the EA with periodic re-optimization. Many different picks across windows means the best setting is unstable.
- **Stress tests.**
  - Extra cost per trade.
  - Removing the best trades, to show whether a few lucky trades carry the result.
  - Drawdown with the trades in random order, to show the drawdown you should be ready for.
  - A bootstrap of the profit factor. It is conditional on the chosen pass and ignores how that pass was chosen, so it overstates confidence.
- **Top passes.** Ranked on training data only, with their out-of-sample results next to them.

## Example

`examples/` contains an example built from the XLZC research engine:
- `xlzc_m2h1_off.csv`: 81 passes of the M2/H1 setup without a filter;
- `xlzc_m2h1_fgf.csv`: the same passes with the FlashGold filter;
- `xlzc_m2h1_report.html`: the resulting report.

To produce them yourself:

```
cd EVK
python -m evk analyze examples/xlzc_m2h1_off.csv --split 2026-01-01 --compare examples/xlzc_m2h1_fgf.csv --labels "No filter,FlashGold"
```

## Limits

- Trades are rebuilt per position from the deal history:
  - scale-ins average the entry price;
  - partial closes are summed;
  - a netting reversal (`INOUT`) closes the open part and opens a new trade.
- Positions still open when the test ends are left out.
- **R** uses the stop loss set on the opening order. If **any** trade has no initial stop loss, the whole run is analysed in money and the tool says how many trades lacked a stop. With `--value r`, trades without R are left out.
- Net profit includes commission, swap and fees. The deposit currency is shown only for single tests. For an optimization the header says "tester deposit currency"; check it in the tester settings.
- Times are broker server time, as MT5 records them.
- EVK measures what the Strategy Tester produced. If the tester's modelling is unrealistic (for example *Open prices only* on an intrabar EA), the analysis inherits that.
- Tests: `python -m unittest discover -s EVK/tests`.
