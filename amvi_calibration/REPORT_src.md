# AMVI strategy on BTCUSDT: every chart timeframe, the trailing stop and the inputs

Date: 2026-11-26. Script: `AMVI_FGF_Inverted_XAUUSD_15m.pine` (closed-candle engine). Market:
BTCUSDT perpetual. Chart timeframes: 1m, 2m, 3m, 5m, 10m, 15m, 30m, 1h, 4h.

110,000 input combinations were backtested over the last three years, each with its stops,
targets and trailing stops filled on the real second-by-second prices; the best were then
tested on the three years before that, which no search had seen. Nothing here ran on
TradingView: the numbers come from a Python copy of the script, checked against two
independent re-implementations of the Pine source and a third of its filter. A calibrated
`.pine` file is in `presets/` for the four timeframes whose pick held up on the older years,
each with its verdict in the title.

## 1. Short version

1. **The file as you run it loses on BTC on every timeframe.** Its inputs were calibrated for
   gold on 15m and it trades against the filter ("Inverted"). On BTCUSDT that lost on all
   nine charts in both periods: from -98R on 4h to -597R on 1m over the last three years, and
   from -36R to -616R on 2021-2023. (1R = the amount risked on one trade.)

2. **Trade with the filter, not against it.** This is the one finding that holds everywhere.
   Among settings that trade with the filter, 4% (1m) to 53% (4h) made money over the last
   three years; among inverted ones 1% to 11%. On 2021-2023, which no search saw: 10% to 83%
   against 2% to 16%. Set **Trade direction** to "Follow the filter"; every pick below does.

3. **No timeframe earned RECOMMENDED. Three files are USABLE (4h, 15m, 3m) and one is
   PAPER-TRADE (1m).** On 1h, 30m, 10m, 5m and 2m the best candidate did not hold up on the
   older data, and no file was written for them. That includes the two charts you trade: the
   5m candidate lost on 2021-2023, and the 10m candidate's gain there rests on a few weeks.

<<Verdicts at a glance>>

   NOT RECOMMENDED and DO NOT TRADE both mean "no file". The difference is only whether the
   search as a whole found more winners than luck would (section 3).

4. **Expect little.** The three USABLE picks each made about +20R on 2021-2023 and +21R to
   +35R on the last three years: +10% to +18% in three years at the files' 0.5% risk per
   trade, with drawdowns of 1.4% to 4%. They trade two to eight times a month. The 1m file
   made more (+55R and +107R) with about one winner in five trades and drawdowns of 15R to
   29R; its older result rests on fewer good weeks, hence PAPER-TRADE.

5. **Fine-tuning does not carry; the direction does.** Inside the last three years none of
   the 27 hold-out tests passes: the best settings of one part made about nothing on the
   other part, and in the most recent year settings chosen on the two years before it landed
   between -6R and +6R. What does carry is the family: the candidates of the last three years
   made money as a group on 2021-2023 on 8 of 9 charts. That period had bigger moves per
   candle, so commission weighed less. Read the strategy as a trend-following filter that
   paid in 2021-2023 and has roughly broken even since for settings not chosen with
   hindsight.

6. **Which charts got a file is partly the luck of one pick.** On 1h, 10m, 5m and 2m the 25
   candidates did well as a group on the older data (72% to 92% of them positive), but the
   one candidate the rule had chosen did not clear the bar. I did not swap picks after seeing
   that: it would be choosing with hindsight.

7. **Filter timeframe: 4h or 1D. Not the chart's own low timeframe, and not seconds.** On
   every chart below 4h a filter several steps above the chart beats a fast one, before fees
   too. The 1-second filter in your screenshot could not be tested (there is no seconds
   history), and with a no-trade band 1.6 USD wide it flips on almost every tick.

8. **Trailing stop: leave it off.** I ran 200 to 300 settings per chart with the trailing
   stop off and with each of the 42 activation / offset pairs, nothing else changed. On 4h it
   makes no difference (14.7% of the settings positive in both halves without it, 14.2% with
   a typical pair). On every chart below 4h it makes them worse: 8 of 336 pairs came out
   above "off", and the shipped pair (1.5 / 1.0 ATR) roughly halves the share of profitable
   settings. **TradingView's tester will tell you the opposite.** It walks the chart's
   candles, which lets a tight trailing stop exit near the best price of every candle. Tested
   that way, 49% of the 4h settings with a 0.5 / 0.5 ATR trailing stop look profitable in both
   halves; on the real second-by-second prices 4% are.

9. **Fees decide the low timeframes.** With a stop of 1 x ATR, the commission of one round
   trip is 0.08R on 4h, 0.34R on 15m, 0.65R on 5m and 1.73R on 1m. Below 15m the typical
   with-the-filter setting loses heavily; the low-timeframe picks survive only by trading
   rarely with a wide stop.

10. **The other inputs mostly change how often it trades, not how well.** Before fees,
    target, time stop, band and High Vol level all land within a few points of each other,
    and stop size matters mostly through commission. After fees the versions that trade less
    look better. Tight targets (1 to 2 ATR) and short time stops are the two things that
    reliably cost money.

**What I would do.** Forward-test the 4h or the 15m file on TradingView with alerts only (your
lab is testnet-only anyway), Script executions on "On bar close", for a few weeks, and compare
its List of Trades with `results/trades_BTCUSDT_4h.csv`. Until that matches, treat every
number here as unverified on TradingView. Do not run the 1-second filter or the inverted
direction on BTC.

**Why this could fail.** The edge is trend following: it disappears in choppy markets, and in
the most recent year settings chosen on earlier data made nothing. The support comes from
2021-2023, when the market moved more than it has since. Each file has 70 to 280 trades per three
years: a few trades decide a year. The data is Binance, your chart is Bitget. And nothing
here has run on TradingView itself.

![Cumulative result of each timeframe's pick](results/equity_all.png)

![Trade direction and cost per timeframe](results/direction_and_costs.png)

## 2. What was run, and how faithfully

**The strategy.** `AMVI_FGF_Inverted_XAUUSD_15m.pine` in its closed-candle version (one decision
per candle at its close, fill at the next open: the version from earlier today). TradingView
does not run in this environment, so the script was rebuilt in Python
(`tools/amvi_engine.py`): the AMVI trigger on every enabled timeframe, the FlashGold direction
filter (signal, zones, band, permission), and the orders (reversal, ATR stop, target, trailing
stop, volatility exit, time stop, wait). It was checked four ways:

- two more copies were written independently from the Pine source; the engine agrees with
  them bar for bar on the signals and trade for trade on the orders, on 72 + 72 random
  settings (`results/checks/difftest_*.txt`) and on the picks themselves
  (`results/checks/replicate_picks.txt`);
- a third, literal statement-by-statement copy of the filter agreed on 49.8 million chart bars;
- 8 hand-computed order scenarios (`tools/test_orders.py`);
- a look-ahead test: no decision reads a candle that has not closed.

It has **not** been compared with TradingView itself, and the Pine files were not compiled
there. Before relying on any number, load the file and compare the Strategy Tester's List of
Trades with `results/trades_BTCUSDT_<tf>.csv`.

**Data.** Binance BTCUSDT perpetual from the exchange's public archive: 1-minute candles
2020-01 to 2026-10, and every trade 2021-01 to 2026-10 (file checksums verified) reduced to
one-second bars (180 million of them; 99.996% of all minutes have their seconds,
`results/checks/seconds_coverage.txt`). Funding: Binance's 8-hourly rates. 367 minutes in which
the exchange did not trade are not candles, as on TradingView. Your chart is Bitget's
BTCUSDT.P: the same market, a few dollars apart, with its own wicks and funding.

**Order fills.** Market orders fill at the next candle's open, 1 tick against you. Stops, targets and
trailing stops are followed **second by second** through the real trades. A coarser path
flatters a trailing stop: it assumes price ran straight to the candle's high and only then
came back (section 5). TradingView's Strategy Tester walks the chart's own candles unless Bar
Magnifier is on, so its trailing-stop results are the most flattering of all.

**Costs.** Base: 0.05% commission per side, 1 tick slippage on market and stop fills, funding
(your crypto lab's rule). Stress: 0.10% per side and 3 ticks. Bitget's standard taker fee of
0.06% is shown for every pick, and the calibrated files ship with 0.06%.

**Results are in R.** 1R = the amount risked on one trade (stop distance x position size).
With the files' Risk 0.5% sizing, 1R = 0.5% of the account: +20R is about +10%. Where a stop
is so tight that 0.5% risk would need more than 5x leverage, the files' 5x cap makes the
position smaller; the per-timeframe sections give the result in % with that cap applied.

**Timeframes.** Chart: 1m, 2m, 3m, 5m, 10m, 15m, 30m, 1h, 4h. AMVI timeframes and filter
timeframe: 1m, 5m, 15m, 30m, 1h, 4h, 1D, with two restrictions so that a result can be
replayed on TradingView:

- a timeframe at or above the chart must be a whole multiple of it (15m on a 10m chart reads
  a different candle live than after a reload);
- a timeframe below the chart must be at least 15m (TradingView keeps about 100,000 intrabars
  per request: 69 days of 1m, 347 days of 5m). In an earlier run without this rule, settings
  that used 1m or 5m under a higher chart were profitable about half as often
  (`results/first_run_low_timeframes.txt`).

Seconds timeframes (1s to 45s) are off everywhere: there is no long seconds history of the
indicator to test them on.

**Inputs searched.** Everything that changes a trade: AMVI periods (fast and slow ATR, StdDev,
candle range, normalisation), the four weights (five presets), High Vol level, which
timeframes are on and how many must be hot, trade direction (with the filter / inverted),
filter timeframe, level mode and entry distance, band, trades against the signal, allowed
side, burst and zone rules, drift filter, parent timeframe, minimum aligned zones, TDI
lengths, permission (until next signal / n candles), check price on, stop, target, trailing
stop with activation and offset, volatility exit and Low Vol level, time stop, exit ATR
length, and candles to wait after an entry. Sizing inputs do not change a result in R and were
set to your lab's limits (0.5% risk, 5x leverage cap). Display inputs were left alone.

## 3. How a setting was judged

1. **Random search.** 110,000 settings in total (16,000 per chart on 4h, 1h, 30m and 15m,
   12,000 on 10m and 5m, 8,000 on 3m and 2m, 6,000 on 1m), each backtested over the search
   window 2023-11-01 to 2026-10-31.
2. **Hold-out tests inside the window.** Take the 40 steadiest settings of the first half and
   score them on the second half, which they have never seen; the same the other way round;
   and the best of the first two years on the third. A test passes when those 40 are positive
   on average, beat 95% of random groups of 40, and stay positive in 95% of resamples of the
   months. If the best of one half are not good on the other, "the best setting" is the
   luckiest of thousands, not a find.
3. **Candidates and the pick.** Settings positive in both halves at base and stressed costs
   are candidates. For the 20 steadiest, every numeric input is moved one step, one at a time.
   The pick is the candidate with the largest share of neighbours still positive in both
   halves (ties: the steadier neighbourhood). This screens out settings that hang on one
   input's exact value. It does not screen out luck: neighbours take mostly the same trades,
   and a lucky candidate passes it about nine times in ten.
4. **The untouched period.** 2021-01-01 to 2023-10-31 (the 2021 top, the May 2021 crash, the
   2022 bear market, FTX) was not used to find or choose anything. Each pick is run on it
   once. Separately, the candidates of a timeframe are compared there with 400 random
   settings, and with random settings of their own trade direction: does choosing on the
   search window help on data it never saw, and does it help beyond choosing the direction?
5. **Luck-only benchmark.** The same counts are repeated in 1,000 shuffled worlds per
   timeframe in which no setting has an edge (`tools/luck.py`). They show how many "winners"
   chance alone produces, what a pick looks like when nothing is there, and how often chance
   would earn each verdict.
6. **Verdict** (`tools/report.py`). "Holds up on the untouched period" = positive there at base
   and at stressed costs with at least 50 trades, and not fragile.

   | Verdict | Means | Luck alone earns it or better |
   |---|---|---|
   | RECOMMENDED | holds up on the untouched period, that result stays positive in 95% of resamples of its weeks, and all four hold-out tests pass | never in 9,000 shuffled worlds |
   | USABLE | holds up, positive in 95% of resamples, and at least one hold-out test passes | 0.1% to 1.1% of timeframes |
   | PAPER-TRADE | holds up and is positive in 90% of resamples, but the hold-out tests fail: watch it, do not fund it | 4.6% to 7.3% of timeframes |
   | NOT RECOMMENDED | the search shows more than luck would, but the pick does not hold up on the untouched period | |
   | DO NOT TRADE | the search found no more winners than luck would, and the best candidate does not hold up | |

   A calibrated file is written only for PAPER-TRADE and better: a file is an invitation to
   trade. The rules were tightened after an independent statistics review and before the
   final run. The first version gave PAPER-TRADE to a setting with no edge about one time in
   three; the review measured that in shuffled worlds, and the last column is the same
   measurement for the final rules. RECOMMENDED is strict on purpose: a moderate real edge
   would rarely reach it in three years of data.

## 4. Results

### 4.1 The pick of each timeframe

<<Results by timeframe>>

### 4.2 What the search itself says

<<What the search itself says>>

**None of the 27 hold-out tests inside the last three years passes.** The 40 steadiest
settings of one part made between -10R and +11R on the other part: around zero. They do far
better than random settings, which lose from 4R on 4h to more than 700R on 1m, but "less bad
than random" is not a profit. The walk-forward column is the most recent year, scored with settings chosen on the
two years before it: between -6R and +6R on every chart.

**The last column does pass, on 8 of 9 charts.** The candidates of the whole three years, run
on the older years they never saw, made money as a group: +12R to +60R on average, 68% to
92% of them positive. On 30m the same result misses the bar by a hair (93% of resamples
instead of 95%). On the low timeframes they beat random settings of their own direction by a
wide margin, but mostly because random settings there are eaten by commission; on 4h, where
commission is small, the candidates do no better than a random with-the-filter setting
(+12.5R against +11.9R). The direction is the find, not the fine-tuning.

### 4.3 The two trade directions on data the search never saw

<<The two trade directions on data the search never saw>>

**With the filter is the better side in both periods, on every chart.** The share of
with-the-filter settings that made money rises with the timeframe, because commission weighs
less: from 4% on 1m to 53% on 4h in the last three years, from 10% to 83% on 2021-2023. The
inverted direction, which the shipped file uses, stays between 1% and 16% everywhere. From 3m
up the gap is as wide before costs (last two columns), so it is not a commission effect; on
1m and 2m it narrows.

**2021-2023 was the kinder period.** On every chart more with-the-filter settings made money
then than in the last three years (4h: 83% against 53%; 15m: 43% against 25%). The market
moved more per candle, so the same commission cost less in R (section 4.6). A result on that
period is real evidence, but it flatters what the same file would have done since.

### 4.4 Is there more here than luck?

<<Is there more here than luck?>>

Inside the search window the share of settings positive in both halves sits above what luck
typically produces (1.3 to 2.1 times the luck-only median) but mostly inside its range: on 4h
and 1h one no-skill world in five to seven finds as many winners. Only on 3m, 2m, 5m and 15m
is it at or beyond the 95% mark. The direction gap is clearer: on 2m, 3m, 5m, 15m and 30m
fewer than 5% of the no-skill worlds show a gap this large, on 10m, 1h and 1m about 5% to 6%,
on 4h 11%.

The second table is the yardstick for the verdicts. When nothing is there, the pick still
shows +24R to +65R on the search window (it was chosen for that) and loses on fresh months.
It is positive on fresh months one time in three, which is why "positive on the untouched
period" alone proves little. With the final rules luck earns PAPER-TRADE or better on about
5% to 7% of timeframes, USABLE on 0.1% to 1.1%, RECOMMENDED never in 9,000 worlds. Over
nine timeframes that is roughly a 40% chance of at least one PAPER-TRADE from luck alone, and
roughly 4% of at least one USABLE. Three USABLE files are not a coin-toss result. But the
coin-toss worlds have no good and bad years, and the real market does (section 4.3): the
test says the older period really paid, not that the next one will.

### 4.5 The file as shipped (your current inputs) on BTCUSDT

<<The file as shipped (your current inputs) on BTCUSDT>>

### 4.6 What one trade costs

<<What one trade costs>>

This table explains most of the rest. On the 5m chart a round trip costs two thirds of the
amount risked before the trade has earned anything; on 1m more than one and a half times.
A setting survives there only by trading rarely and with a wide stop, which is what every
low-timeframe pick does. Your own crypto lab dropped 5m bars on 2026-11-13 after all 34
five-minute combinations of its first run lost to fees: the same wall.

## 5. Trailing stop

<<Trailing stop>>

**No pair of trailing settings improves the strategy.** On 4h the trailing stop is neutral:
17 of 42 pairs are a little above "off", 25 at or below it, and the best pair chosen on half
of the settings is only slightly ahead on the other half (20.7% against 17.3%), which is
within noise for 150 settings. The pairs that do best there have a wide offset (3 ATR). On
every chart below 4h the typical pair cuts the share of profitable settings: by about a third
on 1h and 30m, by half or more below that (1h: 13.0% without, 9.2% with; 15m: 11.3% and 6.8%;
5m: 4.5% and 1.5%). The best pair found on one half of the settings is below "off" on the
other half on every one of those charts except 1m, where both are zero. Of the 336 pairs
below 4h only 8 are above "off": one on 30m and seven on 1m, where next to nothing is
positive either way (0 of 200 settings without trailing, 1 of 200 with).

The shipped pair (activation 1.5, offset 1.0) is one of the weaker ones. It makes somewhat
more settings worse than better (on 1h 53% worse, 33% better, 13% unchanged), and the share
of settings positive in both halves falls to about 60% of the "off" figure on 4h, about half
on 1h and 15m, and a third or less from 10m down.

**Why TradingView shows the opposite.** The last two columns are the same settings with a
tight trailing stop (0.5 / 0.5 ATR), walked the way the Strategy Tester walks them without Bar
Magnifier (open, nearer extreme, other extreme, close of each chart candle) and on the real
second-by-second prices. The chart-candle walk lets the stop trail up to the candle's high
and then exit just below it, as if price had gone there in a straight line. That is worth
0.05R to 0.10R per trade of profit that never existed: on 4h it turns 4% of settings positive
in both halves into 49%, on 1h 3% into 43%. If a trailing stop has looked excellent in your
own TradingView tests, this is the most likely reason.

### How fine must the price path be?

The pick of each timeframe, and the same pick with a tight trailing stop (activation 0.5 x ATR,
offset 0.5 x ATR), with the orders walked on ever finer bars. Search window, net of costs.

<<include results/convergence.md>>

For the picks the price path hardly matters. Only the three that can have two orders close
together inside one candle change at all when the candle is opened up: 4h (stop and target;
+32.9R on chart candles, +35.2R from 1-minute bars down), 10m (trailing stop; +16.8R and
+14.5R) and 30m (trailing stop; +21.4R down to +20.2R).

With a tight trailing stop the chart-candle figure is too good on every chart, by 2R to 14R
over the three years. One-minute bars remove most of that error, and the 5-second and
1-second walks agree to within 0.1R in 16 of the 18 rows (0.7R in the other two: the 30m pick
and the tight stop on 2m). Going finer than one second should not move these results by more
than a fraction of an R.

## 6. Inputs

<<Direction and exits across timeframes>>

**Before costs, only one input clearly separates good from bad: the trade direction.** From
5m up, 41% to 48% of with-the-filter settings are positive in both halves before costs,
against 8% to 16% of inverted ones; below 5m the gap narrows (1m: 38% against 33%). Trailing
on or off, target or none, time stop or none: before costs each pair lands within a few
points of the other. Stop size matters a little before costs (a 0.5 ATR stop is the worst)
and a lot after.

**After costs, what looks like "a better value" is mostly a cheaper one.** A stop of 4 ATR or
more pays a fraction of the commission in R of a stop of 1 ATR or less, and looks better for
that reason alone. The same holds for a wider no-trade band, a higher High Vol level, fewer
timeframes switched on, and not allowing trades against the signal's side: each trades less
often. Two things cost money after fees on every chart: a tight target (1 to 2 ATR) and a
short time stop (a dozen candles or fewer). Both close trades early and pay commission again
on the next one.

**Filter timeframe: 4h, or 1D.** Among with-the-filter settings, a filter several steps above
the chart beats a filter on the chart's own timeframe on every chart below 4h, before
costs too (5m chart: 56% positive in both halves before costs with a 4h filter, 35% with a 5m
filter). On the 4h chart the filter timeframe hardly matters. Seconds filters could not be
tested (no history); nothing here suggests a faster filter helps.

## 7. Settings per timeframe

<<Settings per timeframe>>

## 8. What these numbers do not tell you

1. **Not TradingView.** Every number comes from the Python copy. It matches three independent
   re-implementations of the Pine source, but it has not been compared with TradingView, and
   the Pine files (the closed-candle engine included) have not been compiled there from here.
   If a file does not load, send me the error line.
2. **Binance, not Bitget.** Same market, different exchange: wicks, the exact second a stop is
   touched and funding differ. Expect the same picture, not the same trades.
3. **Three years, one market.** The search window is 2023-11 to 2026-10: a bull market with
   two deep pullbacks. The untouched period adds the 2021 top and the 2022 bear market, but it
   is one more sample, not proof, and it lies before the search window, not after it.
4. **Nine timeframes, one label each.** With nine timeframes tested, one of them looking good
   by chance is expected. Section 4.4 says how often chance alone earns each result.
5. **The untouched period was looked at before the final run, for the 4h chart only.** In a
   dry run of an earlier version I saw the untouched result of three preliminary 4h settings.
   After that look the rules changed, for reasons that came from the code review and not from
   those numbers: ties between plateau candidates go to the steadier one, more inputs are
   stepped in the plateau test, the verdict rules became stricter, fills became second by
   second. Later, while testing the report step, I saw the untouched result of one more 4h
   candidate and of the 4h candidates as a group. Nothing that chooses a pick or a verdict was
   changed after that (the comparison with settings of the same direction was added; it
   decides no verdict). For 4h the untouched period is therefore not as clean as for the
   other charts.
6. **Trailing stop at candle closes.** The script re-sends its exit order at every candle
   close. I assumed TradingView keeps an already trailing stop where it is; I found no
   official statement either way. If it starts the trailing again, trailing settings do
   worse; that variant is shown for every pick that uses a trailing stop, and such a pick
   cannot be rated above PAPER-TRADE unless it survives it.
7. **What TradingView can replay.** A chart holds 5,000 to 40,000 candles depending on the
   plan (20,000 on Premium: 69 days of 5m candles), and a request for a lower timeframe about
   100,000 intrabars. A long test of a low timeframe needs Deep Backtesting; the files that
   read 15m candles from a higher chart say in their header how far back they can be checked.
8. **Small things not modelled.** Liquidation, partial fills, the filter's entry hold (off in
   the shipped file), TradingView's rounding of stop prices to the tick (at most 0.1 USDT). A
   trade's result is booked to the month in which it was opened.
9. **Gold was not calibrated.** This run is BTCUSDT only: there is no recent gold history in
   this checkout (the 2011-2018 files are on another branch). The shipped file's gold
   calibration is untouched by this work.

## 9. Files, and how to rebuild everything

| Path | What it is |
|---|---|
| `presets/AMVI_FGF_BTCUSDT_<tf>.pine` | the script with that timeframe's input defaults; the verdict is in the title and the full record in the header |
| `results/trades_BTCUSDT_<tf>.csv` | every trade of the pick, untouched period and search window, to compare with TradingView's List of Trades |
| `results/equity_all.png`, `results/direction_and_costs.png` | the two charts above |
| `results/INPUTS.md` | every input, value by value, for every timeframe |
| `results/holdout_*.txt`, `plateau_*.txt`, `untouched_check.txt`, `trailing_*.txt`, `luck_*.txt` | the printed output of each step |
| `results/final_<tf>m.json` | every number of a pick |
| `results/checks/` | the engine against the reference versions, the second-by-second walk, data coverage |
| `tools/` | the Python copy of the script and every step (`README.md` lists them) |

Rebuild from public data (about two hours on four cores, 47 GB of downloads streamed and
reduced to 4 GB):

```bash
sh tools/run_all.sh
```

To check a file on TradingView: open BTCUSDT.P on the file's timeframe, paste the file into
the Pine Editor and add it to the chart. In Settings, Properties, leave Script executions on
"On bar close" only (the tick options off), commission 0.06%, slippage 1 tick. The header of
each file says roughly what the Strategy Tester should show. On the lower timeframes the
normal tester only reaches back a few weeks (5,000 to 40,000 candles depending on the plan);
Deep Backtesting (Premium and above) covers up to two million candles.
