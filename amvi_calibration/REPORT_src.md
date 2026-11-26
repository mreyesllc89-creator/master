# AMVI strategy on BTCUSDT: every chart timeframe, the trailing stop and the inputs

Date: 2026-11-26. Script: `AMVI_FGF_Inverted_XAUUSD_15m.pine` (closed-candle engine). Market:
BTCUSDT perpetual. Chart timeframes: 1m, 2m, 3m, 5m, 10m, 15m, 30m, 1h, 4h.

110,000 input combinations were backtested over the last three years (2023-11 to 2026-10;
called the search window from section 2 on), each with its stops, targets and trailing stops
filled on the real second-by-second prices. The best were then tested on 2021-01 to 2023-10
(the untouched period), which no search had used (one exception for 4h: section 8, point 5).
Nothing here ran on TradingView: the numbers come from a Python copy of the script, checked
against two more copies written independently from the Pine source and one more independent
copy of the filter part. A calibrated `.pine` file is in `presets/` for the four timeframes
whose pick made money on 2021-2023; each carries its verdict in its title.

Only want the answer for one chart? Read section 1, then that chart's block in section 7.
Sections 2 to 6 and 8 are the evidence. How to load and check a file on TradingView: section 9.

## 1. Short version

1. **The file with its shipped inputs loses on BTC on every chart.** Those inputs were
   calibrated for gold on 15m: 60m filter, trade direction "Inverted". On BTCUSDT they lost on
   all nine charts in both periods: from -98R on 4h to -597R on 1m over the last three years
   (-295R on 5m, -215R on 10m), and from -36R to -616R on 2021-2023. 1R = the amount risked on
   one trade; at 0.5% risk per trade, 200R is the whole account. Your own variant with the
   1-second filter was not tested (point 7); it has the same inverted direction, which lost
   in every test (point 2).

2. **On BTC, trade with the filter, not against it.** A signal in the filter's BUY ZONE is a
   long, in the SELL ZONE a short. Your file is set to "Inverted", so its entry arrows point
   the other way: on BTC the better side was the opposite of the arrow you see now. Set
   **Trade direction** to "Follow the filter" and the arrows point the right way; every pick
   below does. Among settings that trade with the filter, 4% (1m) to 53% (4h) made money over
   the last three years; among inverted ones 1% to 11%. On 2021-2023: 10% to 83% against 2%
   to 16%. This holds on all nine BTC charts in both periods; it is clear from 5m up and small
   on 2m and 3m. It says nothing about gold: the gold record in your file found the opposite
   there (Follow the filter -53.6R), and gold was not re-tested.

3. **No timeframe earned RECOMMENDED. Three files are USABLE (15m, 3m, 4h) and one is
   PAPER-TRADE (1m).** On 1h, 30m, 10m, 5m and 2m the pick did not hold up on 2021-2023, and
   no file was written. That includes the two charts you trade: the 5m pick lost on
   2021-2023, and the 10m pick's gain there rests on a few weeks. There is nothing to load
   for 5m or 10m. Switching your current setup to "Follow the filter" with a 4h filter and no
   trailing stop does not make it a tested setup: of the 5m settings that did all three, 21%
   made money in the last three years (10m: 29%), and the typical one lost 29R (10m: 10R).

<<Verdicts at a glance>>

   *What the grades mean for you.* USABLE = test with alerts first, then small size at most.
   PAPER-TRADE = watch with alerts only, never with money. NOT RECOMMENDED and DO NOT TRADE
   both mean: no file, do not trade this chart with this strategy. The only difference
   between those two is whether the 25 steadiest candidates of that chart, as a group, passed
   the test on 2021-2023: they did on 1h, 10m, 5m and 2m and just failed on 30m (93% of
   resamples instead of 95%). It does not make 30m worse than 5m: on 2021-2023 the 30m pick
   made +4.8R and the 5m pick lost 1.0R.

   *Words used here.* Pick: the one setting chosen for a chart. Candidates: the settings that
   made money in both 18-month halves of the last three years, also at stressed costs.
   Stressed costs: double commission (0.10% per side) and 3 ticks of slippage. Resamples: the
   weeks of a result are drawn again at random thousands of times (some twice, some not at
   all) and added up; "positive in 86% of resamples" means the total stayed above zero in 86%
   of these draws. Below 90%, a few good weeks carry the result. Steadiest: the most even
   result month by month, not the biggest total.

4. **Expect little, and less than the files show.** The only figures that say something are
   those on 2021-2023, which the picks were not chosen on. There the three USABLE picks made
   about +20R each: about +10% in 34 months at the files' 0.5% risk per trade, with drawdowns
   of 1.4% to 4%. But a file was written because of that result, so these are the picks that
   did best there: the nine picks' median was +8.7R, and the typical candidate on those three
   charts made +7R to +12R, in a period that was easier than the last three years (section
   4.3). Their +21R to +35R on the last three years is not a forecast: they were chosen for
   it, and a setting with no edge chosen the same way shows +24R to +45R there (section 4.4).
   They trade two to eight times a month.

   Only the 15m file made money in each of the three years (2021 +13.5R, 2022 +2.5R, 2023
   +3.7R). The 4h and 3m files made 84% and 80% of their 2021-2023 result between January and
   October 2023 and lost in 2022 (-2.6R, -0.2R). The 1m file made more (+55R and +107R), but
   77% of the +55R came in 2023, +22R of it is one trade still open at the end of the period,
   and two thirds of the +107R came in one month (August 2026: +70R), with about one winner
   in five trades and drawdowns of 15R to 29R; hence PAPER-TRADE.

5. **Fine-tuning does not repeat; the direction does.** Inside the last three years none of
   the 27 hold-out tests passes: the best settings of one part made about nothing on the
   other part, and settings chosen on the first two years made between -6R and +6R in the
   third year. What does repeat is the group result: the 25 steadiest candidates of the last
   three years passed the same test as a group on 2021-2023 on 8 of 9 charts (they made money
   on all nine). That period had bigger moves (ATR 1.4 to 1.5 times higher), so commission
   weighed less. And on 4h, where commission is small, the candidates did no better there
   than random settings of the same direction.

6. **Which charts got a file is partly the luck of one pick.** On 1h, 10m, 5m and 2m the 25
   steadiest candidates did well as a group on 2021-2023 (72% to 92% of them made money), but
   the one the rule had chosen did not pass. I did not swap picks after seeing that: it would
   be choosing with hindsight.

7. **Filter timeframe: 4h (1D is close). Not the chart's own timeframe, and not seconds.** On
   charts up to 15m a 4h filter clearly beats a filter on the chart's own timeframe, before
   fees too (5m chart: 56% of with-the-filter settings positive in both halves before fees
   with a 4h filter, 35% with a 5m filter). On 30m and 1h the gain is 2 to 3 points, which is
   noise; on 4h there is none. Set "Parent obedience timeframe" to the same value or to 1D as
   well: a parent below the filter (your file's 60 under a 4h filter) was never tested. The
   1-second filter in your screenshot was not tested: the Python copy builds its indicators
   from 1-minute candles (the one-second prices of section 2 only fill the orders). The
   fastest filter tested is 1m, and on the 1m chart it is the worst (25% of with-the-filter
   settings positive in both halves before fees, against 44% with a 4h filter). With a
   no-trade band 1.6 USD wide, a 1-second filter flips on almost every tick.

8. **Trailing stop: leave it off.** With the same settings, switching it on made no
   difference on 4h and made results worse on every chart from 2m to 1h (on 1m nothing is
   positive either way). The pair that is the default in your file (1.5 / 1.0 ATR) roughly
   halves the share of profitable settings. On 4h and 1h TradingView's tester will show the
   opposite, because it lets a tight trailing stop exit near the best price of every candle;
   second by second that profit is not there (section 5).

9. **Fees decide the low timeframes.** With a stop of 1 x ATR, the commission of one round
   trip is 0.08R on 4h, 0.34R on 15m, 0.65R on 5m and 1.73R on 1m. Below 15m the typical
   with-the-filter setting loses heavily; the low-timeframe picks survive only by trading
   rarely with a wide stop.

10. **The other inputs mostly change how often it trades, not how well.** Before fees,
    target, time stop, band and High Vol level land within a few points of each other on
    every chart from 2m up, and stop size shows no steady pattern. After fees the versions
    that trade less look better. Tight targets (1 to 2 ATR) and the shortest time stops are
    the two things that cost money on every chart. (The 4h file itself has a 2 ATR target: it
    is the exception, not the rule; section 6.)

**What I would do.**

1. Today: check that TradingView trades like my copy. Open the Binance perpetual
   (BINANCE:BTCUSDT.P, the data used here) on a 15m chart, time zone UTC, load
   `AMVI_FGF_BTCUSDT_15m.pine` and compare the Strategy Tester's List of Trades with
   `results/trades_BTCUSDT_15m.csv` for the dates both cover (the list ends 2026-10-31).
   Entries must be on the same candles and in the same direction. If they are not, do not
   trade the file and send me the tester's list; if the file does not load, send me the error
   line. An exit that differs by a candle or a few USDT is the tester's price path (section 9
   has the details).
2. Then run that file on your Bitget chart with alerts only for about three months (some 20
   trades). On Bitget a few trades will differ from Binance.
3. Start with the 15m file: it made money in each year of 2021-2023, its candidates did
   better there than random with-the-filter settings (84% of them made money, against 43%),
   and TradingView can replay it. The 3m file comes second (it needs Deep Backtesting to
   check). Treat the 4h file as one with-the-filter setting among many: on 4h the search
   added nothing measurable to the direction, the file passes its one test narrowly (96.6%
   of resamples where 95% is needed), and TradingView can replay it only back to 2024-01.
4. Do not run the 1-second filter or the inverted direction on BTC, and do not put a file on
   another chart timeframe than the one in its name. On a 10m chart also switch off the 15m
   AMVI timeframe (it is on in your file): 15m candles do not line up with 10m candles, so
   the live chart and the reloaded chart take different trades.
5. Only the 15m and 3m files stay inside your lab's holding limit (hours to one day): the 4h
   file holds 28 to 35 hours on average and up to 8 days, the 1m file 3.6 to 6.4 days on
   average.

**Why this could fail.** The files' support comes from 2021-2023, when moves were 1.4 to 1.5
times larger and commission cost less in R; for the 4h, 3m and 1m files it comes mostly from
January to October 2023. Inside the last three years, settings chosen on one part made
nothing on the next. Each file has 70 to 280 trades per three years: a few trades decide a
year. The data is Binance, your chart is Bitget. And nothing here has run on TradingView
itself.

![Cumulative result of each timeframe's pick](results/equity_all.png)

![Trade direction and cost per timeframe](results/direction_and_costs.png)

## 2. What was run, and how faithfully

**The strategy.** `AMVI_FGF_Inverted_XAUUSD_15m.pine` in its closed-candle version (one decision
per candle at its close, fill at the next open: the version from earlier today). TradingView
does not run in this environment, so the script was rebuilt in Python
(`tools/amvi_engine.py`): the AMVI trigger on every enabled timeframe, the FlashGold direction
filter (signal, zones, band, permission), and the orders (reversal, ATR stop, target, trailing
stop, volatility exit, time stop, wait). It was checked five ways (logs in `results/checks/`):

- two more copies were written independently from the Pine source (`tools/ref/`). The engine
  agrees with them bar for bar on the signals and trade for trade on the orders, on 72 + 72
  random settings (two three-month slices, six chart timeframes) and on the nine picks
  themselves over 2025-08 to 2026-04;
- a third, literal statement-by-statement copy of the filter agrees with the engine on the
  filter zone of all nine picks, including the 4h and 5m picks, whose filter mode ("Level at
  candle open" with a filter above the chart) the other two copies do not implement. During
  the review it agreed on 49.8 million chart bars;
- 8 hand-computed order scenarios;
- a look-ahead test: prices after a time T were replaced by another path, and nothing the
  engine shows for candles closed by T changed;
- the second-by-second order walk gives the same trades as walking every single second.

An independent audit then rebuilt all 1,074 trades of the four calibrated files from the raw
minute and second data with its own code: every entry, exit, fee and funding charge agreed,
and no stop or target could have been reached earlier than listed.

It has **not** been compared with TradingView itself, and the Pine files were not compiled
there.

**Data.** Binance BTCUSDT perpetual from the exchange's public archive: 1-minute candles
2020-01 to 2026-10, and every trade 2021-01 to 2026-10 (file checksums verified) reduced to
one-second bars (180 million of them; 99.996% of all minutes have their seconds). Funding:
Binance's 8-hourly rates. Two blemishes of the archive: 367 rows of the 1-minute file are
empty and are not candles here, although in 192 of them the exchange did trade (TradingView
may show candles there; rebuilding them changes no entry of the four files). And in 27
minutes the one-second prices contradict the exchange's own 1-minute candle (off-market
prints); there the candle is used. One trade of the 1m file (entry 2022-08-19) would be
-1.0R instead of +3.8R if those prints counted as fills. Your chart is Bitget's BTCUSDT.P:
the same market, a few dollars apart, with its own wicks and funding.

**Order fills.** Market orders fill at the next candle's open, 1 tick against you. Stops,
targets and trailing stops are followed **second by second** through the real trades (why
this matters: section 5).

**Costs.** Base: 0.05% commission per side, 1 tick slippage on market and stop fills, funding
(your crypto lab's rule). Stress: 0.10% per side and 3 ticks. Bitget's standard taker fee of
0.06% is shown for every pick, and the calibrated files ship with 0.06%. Funding is charged
on a position's entry value; charged on its value at each funding time it would cost the 1m
file about 1R more per period and the other files less than 0.01R.

**Results are in R.** 1R = the amount risked on one trade (stop distance x position size).
With the files' Risk 0.5% sizing, 1R = 0.5% of the account: +20R is about +10%. Where a stop
is so tight that 0.5% risk would need more than 5x leverage, the files' 5x cap makes the
position smaller; the per-timeframe blocks give the result in % with that cap applied.

**Timeframes.** Chart: 1m, 2m, 3m, 5m, 10m, 15m, 30m, 1h, 4h. AMVI timeframes and filter
timeframe: 1m, 5m, 15m, 30m, 1h, 4h, 1D, with two restrictions so that a result can be
replayed on TradingView:

- a timeframe at or above the chart must be a whole multiple of it (15m on a 10m chart reads
  a different candle live than after a reload);
- a timeframe below the chart must be at least 15m. TradingView keeps about 100,000 candles
  of a lower timeframe per request: 69 days of 1m, 347 days of 5m. In an earlier run without
  this rule, settings that read 1m or 5m candles from a higher chart were profitable 0.4 to
  0.5 times as often (0.8 times on 4h; `results/first_run_low_timeframes.txt`).

Seconds timeframes (1s to 45s) are off everywhere: the search did not include them.

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
2. **Hold-out tests inside the search window.** Take the 40 steadiest settings of the first
   half and score them on the second half, which they were not chosen on; the same the other
   way round; and the best of the first two years on the third (walk-forward). A test passes
   when those 40 are positive on average, beat 95% of random groups of 40, and stay positive
   in 95% of resamples of the months. If the best of one half are not good on the other,
   "the best setting" is the luckiest of thousands, not a find.
3. **Candidates and the pick.** Settings positive in both halves at base and stressed costs
   are candidates. For the 20 steadiest, every numeric input is moved one step, one at a time
   (the neighbours). The pick is the candidate with the largest share of neighbours still
   positive in both halves (ties: the steadier neighbourhood). This screens out settings that
   hang on one input's exact value. It does not screen out luck: neighbours take mostly the
   same trades, and a lucky candidate passes it about nine times in ten.
4. **The untouched period.** 2021-01-01 to 2023-10-31 (BTC +58% in 2021, -65% in 2022, +110%
   from January to October 2023) was not used to find or choose anything. Each pick is run
   on it once. Separately there is a group test: the 25 steadiest candidates of a timeframe
   (12 on 1m) are scored there with the same three conditions as a hold-out test, against
   400 random settings and against random settings of their own trade direction. Does
   choosing on the search window help on data it was not chosen on, and does it help beyond
   choosing the direction?
5. **Luck-only benchmark.** The same counts are repeated in 1,000 scrambled worlds per
   timeframe in which no setting has an edge (`tools/luck.py`; section 4.4). They show how
   many "winners" chance alone produces, what a pick looks like when nothing is there, and
   how often chance would earn each verdict.
6. **Verdict** (`tools/report.py`). "Holds up on the untouched period" = positive there at base
   and at stressed costs with at least 50 trades, still positive in at least 90% of
   resamples of its weeks, and not fragile. "The four tests" = the three hold-out tests
   inside the search window and the group test on the untouched period.

   | Verdict | Means | Luck alone earns it or better |
   |---|---|---|
   | RECOMMENDED | holds up, positive in 95% of resamples, and all four tests pass | never in 9,000 luck-only worlds |
   | USABLE | holds up, positive in 95% of resamples, and at least one of the four tests passes (for 15m, 3m and 4h it is the group test; the three hold-out tests fail on every chart) | in 0.1% to 1.1% of the luck-only worlds, depending on the chart |
   | PAPER-TRADE | holds up, but is positive in fewer than 95% of resamples (1m: 93%) or passes none of the four tests: watch it, do not fund it | in 4.6% to 7.3% |
   | NOT RECOMMENDED | the pick does not hold up, although one of the four tests passes (here always the group test) | |
   | DO NOT TRADE | the pick does not hold up and none of the four tests passes | |

   A file is written only for PAPER-TRADE and better; the PAPER-TRADE file is for watching,
   not for money. The rules were tightened after an independent statistics review and before
   the final run (what that changed: section 8, point 5). RECOMMENDED is strict on purpose: a
   moderate real edge would rarely reach it in three years of data.

## 4. Results

### 4.1 The pick of each timeframe

<<Results by timeframe>>

### 4.2 What the search itself says

<<What the search itself says>>

**None of the 27 hold-out tests inside the search window passes.** The 40 steadiest settings
of one part made between -10R and +11R on the other part: around zero. On the charts up to
1h they do far better than random settings, which lose from 10R on 1h to more than 700R on
1m, but less bad than random is not a profit. On 4h, where random settings lose only 4R to
7R, the best 40 are no better than a random group in any of the three tests. The
walk-forward column is the most recent year, scored with settings chosen on the two years
before it: between -6R and +6R on every chart.

**The last column passes on 8 of 9 charts.** The 25 steadiest candidates of the whole search
window, run on the untouched period, made money as a group on all nine charts: +12R to +60R
on average, 68% to 92% of them positive. On 30m the result just fails the test (93.2% of
resamples instead of 95%). The 4h result passes by as little (96.6%), and it is the only one
of the four tests that 4h passes; had it missed, the 4h file would be PAPER-TRADE. On the
low timeframes the candidates beat random settings of their own direction by a wide margin,
but mostly because random settings there lose to commission; on 4h, where commission is
small, the candidates do no better than random with-the-filter settings (+12.5R against
+11.9R). The direction is the find, not the fine-tuning.

### 4.3 The two trade directions on data the search never saw

<<The two trade directions on data the search never saw>>

**With the filter is the better side in both periods, on every chart.** The share of
with-the-filter settings that made money rises with the timeframe, because commission weighs
less: from 4% on 1m to 53% on 4h in the search window, from 10% to 83% on the untouched
period. The inverted direction, which the shipped file uses, stays between 1% and 16%
everywhere. The gap is clear from 5m up and small on 2m and 3m on the untouched period (16%
against 11%, 15% against 10%). From 3m up it is as wide before costs (last two columns), so
it is not a commission effect.

**The untouched period was the easier one.** On every chart more with-the-filter settings
made money there than in the search window (4h: 83% against 53%; 15m: 43% against 25%). The
market moved more per candle, so the same commission cost less in R (section 4.6). A result
on that period is real evidence, but expect less in years like the last three.

### 4.4 Is there more here than luck?

<<Is there more here than luck?>>

Inside the search window the share of settings positive in both halves sits above what luck
typically produces (1.3 to 2.1 times the luck-only median) but mostly inside its range: on 4h
and 1h one luck-only world in five to seven finds as many winners. Only on 3m, 2m, 5m and 15m
is it at or beyond the 95% mark. The direction gap is clearer: on 2m, 3m, 5m, 15m and 30m
fewer than 5% of the luck-only worlds show a gap this large, on 10m, 1h and 1m about 5% to
6%, on 4h 11%.

The second table is the yardstick for the verdicts. When nothing is there, the pick still
shows +24R to +65R where it was chosen (it was chosen for that) and loses on months it was
not chosen on. It is positive there one time in three, which is why "positive on the
untouched period" alone proves little. With the final rules luck earns PAPER-TRADE or better
on about 5% to 7% of timeframes, USABLE on 0.1% to 1.1%, RECOMMENDED never in 9,000 worlds.

If the nine timeframes were independent, that would be roughly a 40% chance of at least one
PAPER-TRADE from luck alone and roughly 4% of at least one USABLE. They are not independent:
they share one market and the same months, so three USABLE files are not three separate
confirmations. The luck-only worlds also pay the search window's commission on the months a
pick was not chosen on; on the real untouched period commission in R was about a third
lower, so luck does a little better there than this table says. And the luck-only worlds
have no good and bad years, while the real market does (section 4.3): the test says the
untouched period really paid, not that the next one will.

### 4.5 The shipped inputs (gold calibration: 60m filter, Inverted) on BTCUSDT

<<The shipped inputs on BTCUSDT>>

### 4.6 What one trade costs

<<What one trade costs>>

This table explains most of the rest. On the 5m chart a round trip costs two thirds of the
amount risked before the trade has earned anything; on 1m more than one and a half times.
A setting survives there only by trading rarely and with a wide stop, which is what every
low-timeframe pick does. Your own crypto lab dropped 5m bars on 2026-11-13 after all 34
five-minute combinations of its first run lost to fees: the same problem.

## 5. Trailing stop

**No pair of trailing settings improves the strategy.** On 4h the trailing stop is neutral:
17 of 42 pairs are a little above "off", 25 at or below it, and the best pair chosen on half
of the settings is only slightly ahead on the other half (20.7% against 17.3%), which is
within noise for 150 settings. On every chart from 2m to 1h the typical pair cuts the share
of profitable settings: by about a third on 1h and 30m, by 40% on 15m, by half or more from
10m down (on 2m to 5m, 6 to 13 profitable settings of 200 become 2 or 3). The best pair
found on one half of the settings is below "off" on the other half on each of those charts.
On 1m nothing is positive either way (0 of 200 settings without trailing, 1 of 200 with the
best pairs). Of the 336 pairs below 4h only 8 are above "off": one on 30m and those seven
on 1m.

The shipped pair (activation 1.5, offset 1.0) is one of the weaker ones. On every chart but
2m it makes more settings worse than better (on 1h 53% worse, 33% better, 13% unchanged),
and the share of settings positive in both halves falls to about 60% of the "off" figure on
4h, about half on 1h and 15m, 43% on 30m, about a third from 10m to 3m, and 15% on 2m.

**Why TradingView shows the opposite on 4h and 1h.** Without Bar Magnifier the Strategy
Tester knows only each candle's open, high, low and close. It assumes price went straight to
the high before coming back, so a trailing stop seems to exit near the best price of every
candle. Walked that way, 30 of the 42 pairs look better than "off" on 4h and 14 on 1h, the
tight ones most: with a 0.5 / 0.5 ATR pair, 49% of the 4h settings look profitable in both
halves, and on the real second-by-second prices 4% are (1h: 43% and 3%). That is 0.05R to
0.10R per trade of profit that never existed. From 15m down even the chart-candle walk shows
most pairs below "off". If a trailing stop has looked excellent in your own TradingView
tests on the higher timeframes, this is the most likely reason.

<<Trailing stop>>

### How fine must the price path be?

The pick of each timeframe, and the same pick with a tight trailing stop (activation 0.5 x ATR,
offset 0.5 x ATR), with the orders walked on ever finer bars. Search window, net of costs.

<<include results/convergence.md>>

For the picks the price path hardly matters. Only the three that can have two orders close
together inside one candle change at all when the candle is opened up: 4h (stop and target;
+32.9R on chart candles, +35.2R from 1-minute bars down), 10m (trailing stop; +16.8R and
+14.5R) and 30m (trailing stop; +21.4R down to +20.2R).

With a tight trailing stop the chart-candle figure is too good on every chart, by 2R to 14R
over the three years. From the 3m chart up, one-minute bars remove most of that error. The
5-second and 1-second walks agree to within 0.1R in 16 of the 18 rows; in the other two (the
30m pick, which trails, and the tight stop on 2m) the result still moved 0.6R to 0.7R at the
last step, so a path finer than one second could take off a little more there.

## 6. Inputs

<<Direction and exits across timeframes>>

**Before costs, only one input clearly separates good from bad: the trade direction.** From
5m up, 41% to 48% of with-the-filter settings are positive in both halves before costs,
against 8% to 16% of inverted ones; below 5m the gap narrows (1m: 38% against 33%). Trailing
on or off, target or none, time stop or none: before costs each pair lands within a few
points of the other (except on 1m, where trailing and target differ by 6 to 9 points). Stop
size shows no steady pattern before costs: a 0.5 ATR stop is the worst on 15m and 4h but
among the best on 1m, 3m and 5m. After costs it is the worst on every chart.

**After costs, what looks like "a better value" is mostly a cheaper one.** A stop of 4 ATR or
more pays a fraction of the commission in R of a stop of 1 ATR or less, and looks better for
that reason alone. The same holds for a wider no-trade band, a higher High Vol level, and
not allowing trades against the signal's side: each trades less often.

**Two things cost money after fees for another reason:** a tight target (1 to 2 ATR), on
every chart, and a very short time stop (12 candles or fewer; on 4h only the 6-candle one).
Settings with them pay about the same commission as settings without (15m chart: 25R with a
1 ATR target, 22R with none), so the loss is not extra trading; they simply end trades
before the move is over. The 4h file is the exception to its own chart: its target is 2 ATR
with a 1.5 ATR stop, a value that did worse than no target among 4h settings as a group (12%
against 19% positive in both halves). Do not read the file's value as a rule, and do not
change it either: the file was tested as it is.

**Filter timeframe: 4h.** Among with-the-filter settings a 4h filter beats a filter on the
chart's own timeframe on every chart up to 15m, before costs too (5m chart: 56% against 35%
positive in both halves; 1m chart: 44% against 25%). On 30m and 1h the difference before
costs is 2 to 3 points, which is noise, and on 4h there is none. A 1D filter comes second on
most charts. These figures are for with-the-filter settings only; `results/INPUTS.md` pools
both directions, where the effect partly cancels. Seconds filters were not tested.

## 7. Settings per timeframe

<<Settings per timeframe>>

## 8. What these numbers do not tell you

1. **Not TradingView.** Every number comes from the Python copy. It matches two independent
   copies of the Pine source and a third copy of its filter on all nine picks, and an
   independent audit rebuilt the four files' trades from raw data. But it has not been
   compared with TradingView, and the Pine files (the closed-candle engine included) have
   not been compiled there from here. If a file does not load, send me the error line.
2. **Binance, not Bitget.** Same market, different exchange: wicks, the exact second a stop is
   touched and funding differ. Expect the same picture, not the same trades.
3. **Six years, one market.** The search window is 2023-11 to 2026-10: a bull market to
   October 2025 (35,000 to 125,000 USDT, with pullbacks of 26% and 28%), then a 53% fall to
   June 2026 and a partial recovery; it ends 38% below its peak (daily closes). The untouched period adds
   the 2021 top and the 2022 bear market. It is one more sample, not proof, and it lies
   before the search window, not after it.
4. **Nine timeframes, one market.** The nine charts share the same months, so their results
   are not nine separate confirmations. Section 4.4 says how often chance alone earns each
   verdict on one chart.
5. **The untouched period was looked at before the final run, for the 4h chart only.** In a
   dry run of an earlier version I saw the untouched result of three preliminary 4h
   settings. Later, while testing the report step, I saw the untouched result of one more 4h
   candidate and of the 4h candidates as a group. After that, and before the final run, the
   statistics review changed two things: the verdict rules (the untouched result itself must
   be positive in 95%, or 90%, of resamples of its weeks) and the neighbour test (neighbours
   that take exactly the candidate's trades are no longer counted). Both changes are
   stricter: with the final numbers the earlier rules would have rated 1h and 10m USABLE and
   2m and 30m PAPER-TRADE; 4h, 15m, 3m, 1m and 5m come out the same under both. For 4h the
   untouched period is therefore not as clean as for the other charts. From here on, any
   further change to the rules would need a fresh unseen period (data after 2026-11-01).
6. **Trailing stop at candle closes.** The script re-sends its exit order at every candle
   close. I assumed TradingView keeps an already trailing stop where it is; I found no
   official statement either way. If it starts the trailing again, trailing settings do
   worse. None of the four files uses the trailing stop; the 10m and 30m picks do, and their
   blocks in section 7 show that variant.
7. **What TradingView can replay.** A chart holds 5,000 to 40,000 candles depending on the
   plan, and a request for a lower timeframe about 100,000 candles (section 9).
8. **Small things not modelled.** Liquidation, partial fills, the filter's entry hold (off in
   the shipped file), TradingView's rounding of stop prices to the tick (at most 0.1 USDT).
   A stop fills 1 tick beyond its level; if every stop had filled at the worst price of its
   second, the four files would lose 0.1R to 0.8R more per period (the 1m file 2.7R). A
   trade's result is booked to the month in which it was opened.
9. **Gold was not calibrated.** This run is BTCUSDT only: there is no recent gold history in
   this checkout (the 2011-2018 files are on another branch). The shipped file's gold
   calibration is untouched by this work.

## 9. Files, how to check a file on TradingView, and how to rebuild everything

| Path | What it is |
|---|---|
| `presets/AMVI_FGF_BTCUSDT_<chart>.pine` | the script with that chart's input defaults (15m, 3m, 4h, 1m); the verdict is in the title and at the top of the file |
| `results/trades_BTCUSDT_<chart>.csv` | every trade of a pick, untouched period and search window (UTC, Binance prices), to compare with TradingView's List of Trades |
| `results/equity_all.png`, `results/direction_and_costs.png` | the two charts of section 1 |
| `results/INPUTS.md`, `results/TRAILING.md` | every input value by value, and every trailing pair, for every chart |
| `results/final_<minutes>m.json` | every number of a pick (4h = 240, 1h = 60) |
| `results/holdout_*.txt`, `plateau_*.txt`, `untouched_check.txt`, `trailing_*.txt`, `luck_*.txt` | the printed output of each step |
| `results/checks/` | the engine against the reference copies, the look-ahead test, the second-by-second walk, data coverage, the output check |
| `tools/` | the Python copy of the script and every step (`README.md` lists them) |

### How to load and check a file on TradingView

1. Open BINANCE:BTCUSDT.P (the data used here) on the file's timeframe, time zone UTC.
2. Paste the file into the Pine Editor and add it to the chart.
3. Change nothing in Settings, Properties: the file already sets 0.06% commission, 1 tick
   slippage and 20% margin. Keep Script executions on "On bar close" only (the tick options
   off) and Bar Magnifier off.
4. Compare the Strategy Tester's List of Trades with `results/trades_BTCUSDT_<chart>.csv`,
   trade by trade, for the dates both cover. Entry candle and side must agree. Compare
   trades, not totals.

What the tester can show. It shows money, not R: with the file's sizing, net profit in % is
about R x 0.5. It covers only the candles your plan loads, up to today: 20,000 candles are
9 years of 4h, 208 days of 15m, 42 days of 3m and 14 days of 1m. For the full search window
use Deep Backtesting (Premium plans and above, up to two million candles) and switch on the
input "Limit Backtest Date Range" (group "Backtest range") with 2023-11-01 to 2026-10-31. The
header of each file says what the tester should then show. The 4h file can be replayed only
from 2024-01-19, because it reads 15m candles and TradingView keeps about 100,000 of them.
Two million 1m candles reach back to early 2023, so most of the 1m file's untouched period
cannot be replayed at all.

If it differs. Entries on other candles or in the other direction: do not trade the file,
and send me the tester's list. An exit that differs by a candle or a few USDT is the
tester's price path. A file that does not load: send me the error line.

### Rebuild

From public data (about two hours on four cores; 47 GB of downloads, streamed and reduced to
4 GB):

```bash
sh tools/run_all.sh
```
