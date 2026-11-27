# AMVI strategy on BTCUSDT: every chart timeframe, the trailing stop and the inputs

Date: 2026-11-26. Script: `AMVI_FGF_Inverted_XAUUSD_15m.pine` (closed-candle engine). Market:
BTCUSDT perpetual. Chart timeframes: 1m, 2m, 3m, 5m, 10m, 15m, 30m, 1h, 4h.

110,000 input combinations were backtested over the last three years (2023-11 to 2026-10;
called the search window from section 2 on), each with its stops, targets and trailing stops
filled on the real second-by-second prices. The best were then tested on 2021-01 to 2023-10
(the untouched period), which no search had used (one exception for 4h: section 8, point 5).
Nothing here ran on TradingView: the numbers come from a Python copy of the script, checked
against a second version written independently from the Pine source (in two parts: one for
the signals, one for the orders) and against a literal copy of the filter part. A calibrated
`.pine` file is in `presets/` for the four timeframes whose pick held up on 2021-2023 (15m,
3m, 4h and 1m; what "held up" means: section 3); each carries its verdict in its title.

Only want the answer for one chart? Read section 1, then that chart's block in section 7.
Sections 2 to 6 and 8 are the evidence. How to load and check a file on TradingView: section 9.

## 1. Short version

1. **The file with its shipped inputs loses on BTC on every chart.** Those inputs were
   calibrated for gold on 15m: 60m filter, trade direction "Inverted". On BTCUSDT they lost on
   all nine charts in both periods: from -98R on 4h to -597R on 1m over the last three years
   (-295R on 5m, -215R on 10m), and from -36R to -616R on 2021-2023. 1R = the amount risked on
   one trade; at 0.5% risk per trade, 200R is the whole account. Your own variant with the
   1-second filter was not tested: that filter is faster than anything in the search, and
   for a filter that fast the tests support neither trade direction (points 2 and 7).

2. **On BTC, trade with the filter, not against it, once the filter is slow.** A signal in
   the filter's BUY ZONE is a long, in the SELL ZONE a short. Your file is set to "Inverted",
   so its entries point the other way. (Entries are the order markers that begin with "AMVI
   L" for a long and "AMVI S" for a short, with a small triangle under or over the candle
   before (the candle whose close decided the entry). The tiny triangles in the same
   colours are the filter's own signals: they do not change with this input and are not
   entries; "Signal marks" hides them.) Among settings that
   trade with the filter, 4% (1m) to 53% (4h) made money over the last three years; among
   inverted ones 1% to 11% (settings with at least 30 trades in each half). On 2021-2023: 10%
   to 83% against 2% to 16%. This holds on all nine BTC charts in both periods. It is clear
   from 5m up; on 2m and 3m it is clear in the last three years (3m: 11% against 2%) and
   small on 2021-2023 (15% against 10%).

   **For the arrows in your screenshot there is no right direction.** That chart has the
   filter on 1 second, and the advantage of trading with the filter shrinks as the filter
   gets faster. On a 5m chart the gap between the two directions (settings positive in both
   halves before fees) is 44 points with a 4h filter, 23 with a 15m filter and 14 with a 5m
   filter. With the fastest filters tested (1m and 5m on the 1m chart, 2m on the 2m chart)
   the order is even reversed before fees (1m chart, 1m filter: 41% of inverted settings
   against 25% with the filter; chance alone produces a gap that size about one time in
   17), and after fees almost nothing made money on either side (0% to 5% of settings). A
   1-second filter is faster again and was not tested. So change the filter first (point
   7), then set **Trade direction** to "Follow the filter"; every pick below does. The table
   is in section 6. None of this says anything about gold: the gold record in your file
   found the opposite there (Follow the filter -53.6R), and gold was not re-tested.

3. **No timeframe earned RECOMMENDED. Three files are USABLE (15m, 3m, 4h) and one is
   PAPER-TRADE (1m).** On 1h, 30m, 10m, 5m and 2m the pick did not hold up on 2021-2023, and
   no file was written. That includes the two charts you trade: the 5m pick lost on
   2021-2023, and the 10m pick's gain there rests on a few weeks. There is nothing to load
   for 5m or 10m. Switching your current setup to "Follow the filter" with a 4h filter and no
   trailing stop does not make it a tested setup: of the 5m settings that did all three, 22%
   made money in the last three years (10m: 27%), and the typical one lost 25R (10m: 11R).

| Chart | Verdict | What it means for you | On 2021-2023, which it was not chosen on | Last three years, where it was chosen | File |
|---|---|---|---|---|---|
| [1m](#1m-paper-trade) | PAPER-TRADE | watch with alerts only; no money | +54.8R in 93 trades, positive in 93% of resamples; 77% of it in 2023 | +107.1R in 145 trades | `AMVI_FGF_BTCUSDT_1m.pine` |
| [2m](#2m-not-recommended) | NOT RECOMMENDED | nothing to load | +1.3R in 108 trades (-3.4R at stressed costs); 96% of it in 2023 | +12.0R in 97 trades | none |
| [3m](#3m-usable) | USABLE | test with alerts first; small size at most | +20.6R in 72 trades; 80% of it in 2023 | +23.4R in 79 trades | `AMVI_FGF_BTCUSDT_3m.pine` |
| [5m](#5m-not-recommended) | NOT RECOMMENDED | nothing to load | -1.0R in 70 trades | +16.1R in 68 trades | none |
| [10m](#10m-not-recommended) | NOT RECOMMENDED | nothing to load | +8.7R in 65 trades, positive in 81% of resamples; all of it in 2023 (the other years together lost) | +14.5R in 85 trades | none |
| [15m](#15m-usable) | USABLE | test with alerts first; small size at most | +19.7R in 232 trades; 69% of it in 2021 | +21.1R in 284 trades | `AMVI_FGF_BTCUSDT_15m.pine` |
| [30m](#30m-do-not-trade) | DO NOT TRADE | nothing to load | +4.8R in 68 trades, positive in 77% of resamples; 80% of it in 2022 | +20.2R in 74 trades | none |
| [1h](#1h-not-recommended) | NOT RECOMMENDED | nothing to load | +7.5R in 98 trades, positive in 86% of resamples | +22.0R in 101 trades | none |
| [4h](#4h-usable) | USABLE | test with alerts first; small size at most | +21.4R in 69 trades; 84% of it in 2023 | +35.2R in 100 trades | `AMVI_FGF_BTCUSDT_4h.pine` |

   *What the grades mean for you.* USABLE = test with alerts first, then small size at most
   (what the alerts must show, and what "small" is: What I would do, step 2). PAPER-TRADE =
   watch with alerts only, never with money. NOT RECOMMENDED and DO NOT TRADE both mean: no
   file, do not trade this chart with this strategy. The only difference between those two
   is whether the 25 steadiest candidates of that chart, as a group, passed the test on
   2021-2023: they did on 1h, 10m, 5m and 2m and just failed on 30m (93% of resamples
   instead of 95%). It does not make 30m worse than 5m: on 2021-2023 the 30m pick made +4.8R
   and the 5m pick lost 1.0R.

   *Words used here.* Pick: the one setting chosen for a chart. Candidates: the settings that
   made money in both 18-month halves of the last three years, also at stressed costs (only
   settings with at least 30 trades in each half count). Stressed costs: double commission
   (0.10% per side) and 3 ticks of slippage. Resamples: the weeks of a result are drawn
   again at random thousands of times (some twice, some not at all) and added up; "positive
   in 86% of resamples" means the total stayed above zero in 86% of these draws. Below 90%,
   a few good weeks carry the result. Steadiest: the most even result month by month, not
   the biggest total.

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
   than random settings with the same trade directions.

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

   This is advice for your own file. The calibrated files keep the filter they were tested
   with: 1D with a 1D parent in the 15m, 4h and 1m files, 4h with a 4h parent in the 3m
   file. Leave every input of a calibrated file as it is: a changed file is an untested
   one, and its trades no longer match the list.

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

1. Now: check that TradingView trades like my copy. On BINANCE:BTCUSDT.P (the data used
   here), time zone UTC, load a file on its own timeframe and change no input except the
   date range below. Compare the Strategy Tester's List of Trades with that file's list in
   `results/`, up to 2026-10-31 (the list ends there): entries must be on the same candles
   and in the same direction. If a file does not load, send me the error line.
   - With Deep Backtesting (Premium plans and above), check the 15m file
     `AMVI_FGF_BTCUSDT_15m.pine` on a 15m chart. Set the Deep Backtesting period to
     2023-05-01 to 2026-10-31, and in the script's inputs switch on "Limit Backtest Date
     Range" (group "Backtest range") with 2023-11-01 to 2026-10-31. The range only blocks
     entries; the six months before it give the script its history. Every trade must then
     match, exits included: in my simulation all 284 do, and with the period starting on
     2023-11-01 itself the first 4 do not. If one does not match, do not trade the file and
     send me the tester's list.
   - Without Deep Backtesting, check the 4h file `AMVI_FGF_BTCUSDT_4h.pine` on a 4h chart
     first; it runs the same code with other inputs. Compare from two weeks after the
     oldest 15m candle the tester has (about 2024-02-02 if you check on 26 November, a day
     later every day): about 92 trades. On a 5,000-candle chart (Basic plan) compare from
     five months after the chart's first candle: about 60 trades. List trades missing before
     those dates are expected, and one exit of this list is expected to differ (section 9).
     An entry on another candle or on the other side after them is a mismatch: then do not
     run the 15m file either, and send me the tester's list. A 4h match does not check the
     15m file's time stop, which ends 159 of its 284 list trades; the 4h file has it off,
     and none of its trades ends by reversal. So on Essential and Plus also load the 15m
     file on a 15m chart and compare from four weeks after its first candle: about 12 list
     trades if you check on 26 November, 8 of them time stops. This is a loose check (a
     missing or extra trade there proves nothing, section 9), but where an entry matches,
     its exit should be in the same candle; a time stop one candle off means TradingView
     counts it differently, so send me the list. On Basic no 15m list trade is left: the
     15m file cannot be compared with my list at all, so keep it on alerts only.
2. Then run the 15m file on your Bitget chart with alerts only until about 20 trades have
   come: about three months on 15m (seven to ten months for the 3m and 4h files). The file
   has no alert() call: create the alert on the strategy itself (order fills). Do not judge
   these months by profit: 20 trades cannot show it. In the backtest itself about one run
   of 20 trades in four lost (the average run made +1.5R, the worst -4.4R). Check instead
   that every alert shows up in the Strategy Tester's list on the same candle and side, and
   how far Bitget's price is from that entry; a few trades will differ from Binance. Check
   each alert there within a week of it, not at the end: a 15m chart holds only the last 52
   days on Basic (104 on Essential and Plus), and a trade in a chart's first weeks can be
   missing without anything being wrong (section 9). The alerts compare TradingView with
   itself, not with my list; they do not replace step 1. Only if both hold: small size
   means no more than the file's own sizing, 0.5% of the account at risk per trade with the
   position capped at 5x, which is your lab's limit, and your lab's own rule comes first
   (testnet until you write "go live").
3. Start with the 15m file: it made money in each year of 2021-2023, its candidates did
   better there than random with-the-filter settings (84% of them made money, against 43%),
   and with Deep Backtesting TradingView can replay all of it (without it only loosely, and
   on Basic not at all). The 3m file comes second (it can be checked only with Deep
   Backtesting). Treat the 4h file as one with-the-filter setting among many: on 4h the search
   added nothing measurable to the direction, the file passes its one test narrowly (96.6%
   of resamples where 95% is needed), and on plans up to Premium TradingView can replay it
   only back to about 2024-01-19 (as of 26 November; a day later every day).
4. On your 5m and 10m charts: do not trade this strategy now. The one setting chosen for
   each did not pass (the 5m pick lost on 2021-2023, the 10m pick's gain there rests on a
   few weeks), so there is no file. If you keep your own file on such a chart to watch it:
   "Follow the filter", a 4h filter with a 4h or 1D parent, trailing stop off. On 10m also
   untick "15m" in the group "Timeframes (enabled = fetched, plotted, used for signals)",
   not the "15m" under "Overlay": 15m candles do not line up with 10m candles, so the live
   chart and the reloaded chart take different trades. That setup stays untested (point 3).
5. Do not run the 1-second filter on BTC, do not run the inverted direction with a slower
   filter, and do not put a file on another chart timeframe than the one in its name.
6. Only the 15m and 3m files stay inside your lab's holding limit (hours to one day): the 4h
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

- two reference versions were written independently from the Pine source (`tools/ref/`):
  one of the signal side, one of the order side. The engine agrees with the first bar for
  bar on the signals and with the second trade for trade on the orders (the order version
  is given the engine's signals), on 72 + 72 random settings (two three-month slices, six
  chart timeframes) and on the nine picks themselves over 2025-08 to 2026-04. So each part
  has one independent check, not two;
- a literal statement-by-statement copy of the filter agrees with the engine on the filter
  zone of all nine picks, including the 4h and 5m picks, whose filter mode ("Level at
  candle open" with a filter above the chart) the signal version does not implement;
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

**Timeframes.** Chart: 1m, 2m, 3m, 5m, 10m, 15m, 30m, 1h, 4h. AMVI timeframes: 1m, 5m, 15m,
30m, 1h, 4h, 1D. Filter timeframe: the same list, or the chart's own timeframe (2m, 3m and
10m filters exist only on those charts). Two restrictions apply to both, so that a result
can be replayed on TradingView:

- a timeframe at or above the chart must be a whole multiple of it (15m on a 10m chart reads
  a different candle live than after a reload);
- a timeframe below the chart must be at least 15m. TradingView keeps about 100,000 candles
  of a lower timeframe per request on plans up to Premium (200,000 on Ultimate): 69 days of
  1m, 347 days of 5m. In an earlier run without this rule, settings that read 1m or 5m
  candles from a higher chart were profitable 0.4 to 0.5 times as often (0.8 times on 4h;
  `results/first_run_low_timeframes.txt`).

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
3. **Candidates and the pick.** Settings with at least 30 trades in each half, and a trade
   in at least 60% of its months, that are positive in both halves at base and stressed
   costs are candidates. For the 20 steadiest, every numeric input is moved one step, one at
   a time (the neighbours). The pick is the candidate with the largest share of neighbours
   still positive in both halves (ties: the steadier neighbourhood). This screens out
   settings that hang on one input's exact value. It does not screen out luck: neighbours
   take mostly the same trades, and a lucky candidate passes it about nine times in ten.
4. **The untouched period.** 2021-01-01 to 2023-10-31 (BTC +60% in 2021, -64% in 2022, +110%
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
   | RECOMMENDED | holds up, positive in 95% of resamples (there and in the search window), and all four tests pass | never in 9,000 luck-only worlds |
   | USABLE | holds up, positive in 95% of resamples, and at least one of the four tests passes (for 15m, 3m and 4h it is the group test; the three hold-out tests fail on every chart) | in 0.1% to 1.1% of the luck-only worlds, depending on the chart |
   | PAPER-TRADE | holds up, but is positive in fewer than 95% of resamples (1m: 93%) or passes none of the four tests: watch it, do not fund it | in 4.6% to 7.3% |
   | NOT RECOMMENDED | the pick does not hold up, although one of the four tests passes (here always the group test) or the search found more candidates than 95% of the luck-only worlds (that rule decided no chart) | |
   | DO NOT TRADE | the pick does not hold up and neither of those is true | |

   A pick that uses the trailing stop can be USABLE or better only if it also stays positive
   in both periods when the trailing stop starts again at every candle close (section 8,
   point 6); none of the four files uses the trailing stop. A file is written only for
   PAPER-TRADE and better; the PAPER-TRADE file is for watching, not for money. The rules were tightened after an independent statistics review and before
   the final run (what that changed: section 8, point 5). RECOMMENDED is strict on purpose: a
   moderate real edge would rarely reach it in three years of data.

## 4. Results

### 4.1 The pick of each timeframe

Net of 0.05% per side, 1 tick slippage and funding. R = amount risked per trade; PF = profit factor (gross profit / gross loss);
DD = largest drawdown. The untouched period comes first because the pick was not chosen on it; the search-window figure is the best
of thousands of settings and is flattered by that choice.

| Chart | Verdict | Untouched 2021-01 to 2023-10 (not chosen on it) | Stressed costs | Positive in resamples of its weeks | Search window 2023-11 to 2026-10 (chosen here) | Halves | File |
|---|---|---|---|---|---|---|---|
| 1m | PAPER-TRADE | +54.8R, 93 trades, PF 1.75, DD 15.2R | +49.0R | 93% | +107.1R, 145 trades, PF 1.83, DD 29.2R | +50.2 / +56.9R | `presets/AMVI_FGF_BTCUSDT_1m.pine` |
| 2m | NOT RECOMMENDED | +1.3R, 108 trades, PF 1.05, DD 4.2R | -3.4R | 60% | +12.0R, 97 trades, PF 1.81, DD 2.6R | +6.5 / +5.5R | none |
| 3m | USABLE | +20.6R, 72 trades, PF 2.56, DD 2.9R | +16.9R | 100% | +23.4R, 79 trades, PF 2.13, DD 2.9R | +11.3 / +12.0R | `presets/AMVI_FGF_BTCUSDT_3m.pine` |
| 5m | NOT RECOMMENDED | -1.0R, 70 trades, PF 0.98, DD 6.7R | -4.8R | 45% | +16.1R, 68 trades, PF 1.51, DD 5.2R | +7.1 / +9.1R | none |
| 10m | NOT RECOMMENDED | +8.7R, 65 trades, PF 1.31, DD 6.4R | +6.0R | 81% | +14.5R, 85 trades, PF 1.44, DD 5.7R | +7.3 / +7.2R | none |
| 15m | USABLE | +19.7R, 232 trades, PF 1.41, DD 7.0R | +14.7R | 99% | +21.1R, 284 trades, PF 1.35, DD 3.7R | +10.7 / +10.4R | `presets/AMVI_FGF_BTCUSDT_15m.pine` |
| 30m | DO NOT TRADE | +4.8R, 68 trades, PF 1.22, DD 3.8R | +3.1R | 77% | +20.2R, 74 trades, PF 2.22, DD 3.3R | +12.3 / +8.0R | none |
| 1h | NOT RECOMMENDED | +7.5R, 98 trades, PF 1.29, DD 6.0R | +3.8R | 86% | +22.0R, 101 trades, PF 2.32, DD 3.2R | +11.1 / +10.9R | none |
| 4h | USABLE | +21.4R, 69 trades, PF 1.71, DD 8.3R | +18.9R | 98% | +35.2R, 100 trades, PF 1.84, DD 5.7R | +22.4 / +12.9R | `presets/AMVI_FGF_BTCUSDT_4h.pine` |

### 4.2 What the search itself says

Best 40 = the 40 steadiest settings of one part of the search window, scored on another part. A test passes when their mean is
positive, above 95% of random groups of 40, and stays positive in 95% of resamples of the months. The last column is the same test
for the 25 steadiest candidates (12 on 1m), chosen on the whole search window and scored on the untouched period.
The three "Positive" columns are shares of the settings with at least 30 trades in each half and a trade in at least 60% of its
months: 57,920 of the 110,000 tried. "Beaten" in the last column: the candidates' mean is above 95% of random groups with
their own trade directions (results/untouched_check.txt prints this comparison with the 95% resample condition included, so its
line for 30m reads "fail").

| Chart | Settings tried | Positive before costs | Positive after costs | Positive in both halves | First half -> second (best 40) | Second -> first | Walk-forward (two years -> the third) | Search window -> untouched period (25 steadiest candidates) |
|---|---|---|---|---|---|---|---|---|
| 1m | 6,000 | 58% | 2% | 0.9% | -9.9R, 25% positive, 22% of resamples (fail) | -0.3R, 50% positive, 46% of resamples (fail) | -3.2R, 38% positive, 38% of resamples (fail) | +60.3R, 83% positive, 96.9% of resamples (pass); random settings of the same directions -1438.1R (beaten) |
| 2m | 8,000 | 51% | 6% | 2.8% | -3.7R, 48% positive, 25% of resamples (fail) | +10.6R, 52% positive, 87% of resamples (fail) | +6.2R, 62% positive, 77% of resamples (fail) | +54.0R, 72% positive, 96.1% of resamples (pass); random settings of the same directions -50.2R (beaten) |
| 3m | 8,000 | 52% | 6% | 3.3% | -5.0R, 40% positive, 12% of resamples (fail) | +3.3R, 60% positive, 61% of resamples (fail) | -1.1R, 50% positive, 35% of resamples (fail) | +18.6R, 80% positive, 98.7% of resamples (pass); random settings of the same directions -72.3R (beaten) |
| 5m | 12,000 | 54% | 7% | 3.2% | -6.2R, 32% positive, 16% of resamples (fail) | +9.4R, 55% positive, 80% of resamples (fail) | -4.5R, 32% positive, 22% of resamples (fail) | +27.0R, 76% positive, 99.1% of resamples (pass); random settings of the same directions -150.2R (beaten) |
| 10m | 12,000 | 51% | 13% | 6.3% | -4.3R, 35% positive, 3% of resamples (fail) | +1.1R, 50% positive, 56% of resamples (fail) | +0.7R, 48% positive, 59% of resamples (fail) | +25.3R, 80% positive, 99.5% of resamples (pass); random settings of the same directions -19.8R (beaten) |
| 15m | 16,000 | 49% | 15% | 7.1% | -5.5R, 28% positive, 11% of resamples (fail) | -3.3R, 40% positive, 9% of resamples (fail) | -2.8R, 32% positive, 18% of resamples (fail) | +14.7R, 84% positive, 100.0% of resamples (pass); random settings of the same directions -16.1R (beaten) |
| 30m | 16,000 | 50% | 19% | 8.6% | -5.0R, 42% positive, 20% of resamples (fail) | +2.2R, 57% positive, 80% of resamples (fail) | -6.3R, 35% positive, 20% of resamples (fail) | +12.1R, 84% positive, 93.2% of resamples (fail); random settings of the same directions -8.6R (beaten) |
| 1h | 16,000 | 51% | 23% | 9.9% | -2.0R, 45% positive, 37% of resamples (fail) | +0.9R, 55% positive, 79% of resamples (fail) | -2.8R, 32% positive, 26% of resamples (fail) | +17.1R, 92% positive, 99.6% of resamples (pass); random settings of the same directions +4.7R (beaten) |
| 4h | 16,000 | 50% | 32% | 15.3% | -3.6R, 30% positive, 17% of resamples (fail) | -1.1R, 45% positive, 16% of resamples (fail) | -2.6R, 35% positive, 31% of resamples (fail) | +12.5R, 68% positive, 96.6% of resamples (pass); random settings of the same directions +11.9R (not beaten) |

**None of the 27 hold-out tests inside the search window passes.** The 40 steadiest settings
of one part made between -10R and +11R on the other part: around zero. On the charts up to
1h random settings lose from 10R (1h) to more than 700R (1m), and the best 40 do far better
than that in 23 of the 24 tests (the exception is the 30m walk-forward: -6.3R, inside the
range of random groups); but less bad than random is not a profit. On 4h, where random
settings lose only 4R to 7R, the best 40 are no better than a random group in any of the
three tests. The walk-forward column is the most recent year, scored with settings chosen
on the two years before it: between -6R and +6R on every chart.

**The last column passes on 8 of 9 charts.** The 25 steadiest candidates of the whole search
window, run on the untouched period, made money as a group on all nine charts: +12R to +60R
on average, 68% to 92% of them positive. On 30m the result just fails the test (93.2% of
resamples instead of 95%). The 4h result passes by as little (96.6%), and it is the only one
of the four tests that 4h passes; had it missed, the 4h file would be PAPER-TRADE. On the
low timeframes the candidates beat random settings of their own direction by a wide margin,
but mostly because random settings there lose to commission; on 4h, where commission is
small, the candidates do no better than random settings with the same trade directions
(+12.5R against +11.9R; 22 of the 25 trade with the filter, 3 are inverted). The direction
is the find, not the fine-tuning.

### 4.3 The two trade directions on data the search never saw

400 random settings of the search per timeframe (at least 30 trades in each half of the search window), run over the untouched
period and split by trade direction; then the same split on the search window for all settings of the search with at least 30
trades in each half (58,800 of the 110,000).
"Positive" = net result above zero over the whole period after 0.05% per side, 1 tick and funding. The last two columns:
positive in both halves of the search window, after costs / before costs.

| Chart | Untouched: with the filter positive | Median | Untouched: inverted positive | Median | Search window: with the filter positive | Median | Inverted positive | Median | Both halves, with the filter | Both halves, inverted |
|---|---|---|---|---|---|---|---|---|---|---|
| 1m | 10% of 202 | -134.5R | 2% of 198 | -181.1R | 4% | -241.3R | 1% | -292.3R | 1.4% / 38.3% | 0.4% / 33.0% |
| 2m | 16% of 198 | -28.4R | 11% of 202 | -28.0R | 8% | -45.0R | 3% | -48.1R | 4.1% / 30.6% | 1.4% / 23.1% |
| 3m | 15% of 202 | -26.3R | 10% of 198 | -34.6R | 11% | -41.1R | 2% | -60.4R | 5.8% / 41.9% | 0.9% / 19.0% |
| 5m | 26% of 184 | -24.0R | 6% of 216 | -55.6R | 13% | -47.3R | 2% | -76.7R | 6.0% / 48.0% | 0.6% / 16.1% |
| 10m | 30% of 212 | -9.6R | 16% of 188 | -15.8R | 21% | -15.1R | 6% | -29.0R | 10.4% / 41.0% | 2.2% / 13.7% |
| 15m | 43% of 208 | -3.4R | 9% of 192 | -25.1R | 25% | -12.7R | 5% | -34.7R | 12.8% / 47.7% | 1.6% / 12.0% |
| 30m | 55% of 199 | +1.4R | 10% of 201 | -28.3R | 31% | -7.9R | 7% | -29.8R | 15.0% / 48.3% | 2.3% / 11.9% |
| 1h | 66% of 210 | +5.1R | 4% of 190 | -26.0R | 37% | -4.4R | 8% | -24.7R | 16.7% / 47.0% | 3.0% / 10.7% |
| 4h | 83% of 203 | +8.1R | 10% of 197 | -14.1R | 53% | +0.7R | 11% | -12.6R | 27.1% / 47.7% | 3.5% / 8.2% |

**With the filter is the better side in both periods, on every chart.** The share of
with-the-filter settings that made money rises with the timeframe, because commission weighs
less: from 4% on 1m to 53% on 4h in the search window, from 10% to 83% on the untouched
period. The inverted direction, which the shipped file uses, stays between 1% and 16%
everywhere. The gap is clear from 5m up and small on 2m and 3m on the untouched period (16%
against 11%, 15% against 10%). From 3m up it is as wide before costs (last two columns), so
it is not a commission effect. It does depend on the filter's timeframe: with the fastest
filters on the 1m and 2m charts the order is reversed before costs (section 6).

**The untouched period was the easier one.** On every chart more with-the-filter settings
made money there than in the search window (4h: 83% against 53%; 15m: 43% against 25%). The
market moved more per candle, so the same commission cost less in R (section 4.6). A result
on that period is real evidence, but expect less in years like the last three.

### 4.4 Is there more here than luck?

To see what luck alone produces, the search results were scrambled 1,000 times per chart: months were drawn at random and, in
each month, the before-cost results of all settings were flipped together by one coin toss. No setting has an edge after that,
but fees, trade counts and the similarity between settings stay as they are. These are the luck-only worlds. A real count inside
the luck-only range is no evidence of an edge.

| Chart | Positive in both halves: real | Luck alone (5% to 95% of worlds) | Worlds with at least as many | Candidates: real | Luck alone | Worlds with at least as many | With the filter minus inverted: real | Luck alone | Worlds with a gap this large |
|---|---|---|---|---|---|---|---|---|---|
| 1m | 0.9% | 0.5% (0.2 to 1.1%) | 10% | 12 | 5 (1 to 20) | 17% | +1.1 points | -0.5 to +1.1 | 6% |
| 2m | 2.8% | 1.4% (0.6 to 2.7%) | 4% | 39 | 13 (3 to 37) | 5% | +2.8 points | -1.7 to +1.9 | 3% |
| 3m | 3.3% | 1.6% (0.7 to 2.9%) | 2% | 52 | 18 (6 to 44) | 2% | +5.0 points | -1.8 to +2.8 | 0% |
| 5m | 3.2% | 1.6% (0.8 to 3.2%) | 5% | 79 | 32 (12 to 88) | 7% | +5.3 points | -2.1 to +3.1 | 1% |
| 10m | 6.3% | 4.1% (2.2 to 7.1%) | 10% | 115 | 66 (27 to 152) | 12% | +8.4 points | -6.1 to +7.4 | 5% |
| 15m | 7.1% | 4.2% (2.3 to 7.1%) | 5% | 221 | 111 (49 to 236) | 7% | +11.3 points | -6.3 to +7.6 | 2% |
| 30m | 8.6% | 5.4% (3.2 to 8.9%) | 7% | 302 | 167 (82 to 341) | 9% | +12.9 points | -8.1 to +9.7 | 2% |
| 1h | 9.9% | 7.1% (4.0 to 11.9%) | 15% | 423 | 262 (128 to 526) | 14% | +14.0 points | -10.3 to +13.6 | 6% |
| 4h | 15.3% | 11.9% (7.0 to 19.3%) | 20% | 751 | 551 (291 to 1074) | 22% | +23.8 points | -23.0 to +25.6 | 11% |

What a pick is worth when nothing is there: the steadiest candidate of each luck-only world, on the months it was chosen on and
on further months it was not chosen on, and how often luck alone meets the conditions of each verdict (the neighbour test of
section 3 taken as passed, months standing in for weeks).

| Chart | Luck's pick where it was chosen (median, 95th percentile) | Luck's pick on months it was not chosen on | Positive there | Positive there at base and stressed costs with 50+ trades | Luck passes at least one of the four tests | Luck earns PAPER-TRADE or better | USABLE or better | RECOMMENDED |
|---|---|---|---|---|---|---|---|---|
| 1m | +65.4R, +365.5R | -12.1R | 33% | 20% | 2.9% | 6.5% | 1.1% | 0.0% |
| 2m | +52.2R, +236.4R | -9.0R | 32% | 20% | 3.4% | 4.9% | 0.6% | 0.0% |
| 3m | +45.3R, +180.9R | -7.9R | 33% | 21% | 3.3% | 4.9% | 0.3% | 0.0% |
| 5m | +36.1R, +152.0R | -8.4R | 28% | 17% | 3.1% | 4.8% | 0.1% | 0.0% |
| 10m | +31.0R, +122.8R | -5.1R | 32% | 20% | 3.7% | 5.4% | 0.2% | 0.0% |
| 15m | +28.9R, +95.4R | -4.6R | 33% | 21% | 3.3% | 5.1% | 0.4% | 0.0% |
| 30m | +28.4R, +103.0R | -4.9R | 32% | 20% | 3.4% | 4.6% | 0.7% | 0.0% |
| 1h | +27.3R, +88.7R | -3.9R | 34% | 22% | 5.2% | 5.2% | 0.3% | 0.0% |
| 4h | +24.3R, +74.7R | -2.7R | 36% | 27% | 6.4% | 7.3% | 0.7% | 0.0% |

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

The inputs of AMVI_FGF_Inverted_XAUUSD_15m.pine unchanged (calibrated for gold on 15m: 60m filter, trade direction Inverted), run on
each BTC chart timeframe. On the 2m and 10m charts the 15m AMVI does not line up with the chart's candles; the numbers there are what
a reloaded chart shows.

| Chart | Search window (2023-11 to 2026-10) | Stressed costs | Untouched 2021-01 to 2023-10 |
|---|---|---|---|
| 1m | -597.0R, 726 trades, PF 0.52, DD 686.9R | -1187.4R | -616.0R, 674 trades, PF 0.40 |
| 2m | -507.2R, 742 trades, PF 0.54, DD 541.6R | -946.0R | -376.1R, 652 trades, PF 0.57 |
| 3m | -420.7R, 754 trades, PF 0.60, DD 453.1R | -794.4R | -376.1R, 657 trades, PF 0.56 |
| 5m | -294.8R, 755 trades, PF 0.69, DD 372.4R | -598.3R | -372.4R, 688 trades, PF 0.56 |
| 10m | -214.8R, 561 trades, PF 0.68, DD 285.6R | -394.8R | -35.7R, 527 trades, PF 0.94 |
| 15m | -188.7R, 597 trades, PF 0.72, DD 244.6R | -338.1R | -49.6R, 541 trades, PF 0.91 |
| 30m | -137.5R, 529 trades, PF 0.75, DD 177.5R | -239.0R | -72.0R, 472 trades, PF 0.85 |
| 1h | -105.0R, 902 trades, PF 0.87, DD 141.6R | -239.5R | -238.0R, 811 trades, PF 0.68 |
| 4h | -97.6R, 671 trades, PF 0.80, DD 115.2R | -149.8R | -57.7R, 575 trades, PF 0.86 |

### 4.6 What one trade costs

Commission of a round trip at 0.05% per side, in R, when the stop is 1 x ATR(14) of the chart (a 2 x ATR stop halves it). The market
moved more per candle on the untouched period, so the same commission was a smaller share of the risk then.

| Chart | Search window: median ATR(14) as % of price | Round-trip commission in R | Untouched period: median ATR(14) | Round-trip commission in R |
|---|---|---|---|---|
| 1m | 0.058% | 1.73R | 0.089% | 1.12R |
| 2m | 0.089% | 1.12R | 0.134% | 0.75R |
| 3m | 0.114% | 0.88R | 0.170% | 0.59R |
| 5m | 0.155% | 0.65R | 0.229% | 0.44R |
| 10m | 0.231% | 0.43R | 0.334% | 0.30R |
| 15m | 0.295% | 0.34R | 0.419% | 0.24R |
| 30m | 0.433% | 0.23R | 0.607% | 0.16R |
| 1h | 0.630% | 0.16R | 0.883% | 0.11R |
| 4h | 1.305% | 0.08R | 1.859% | 0.05R |

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

**Why TradingView shows the opposite on 4h and 1h.** With Bar detalization on its default
(the former "Bar Magnifier" off) the Strategy Tester knows only each candle's open, high,
low and close. It assumes price ran in straight lines from the open to one extreme, on to
the other and then to the close, so a trailing stop seems to exit just behind the best
price of every candle. Walked that way, 30 of the 42 pairs look better than "off" on 4h,
14 on 1h and 13 on 30m (there mostly the pairs with an offset of 0.5 or 1 ATR), and at most
7 on the charts from 15m down to 2m. The tight pairs gain most: with a 0.5 / 0.5 ATR pair,
49% of the 4h settings look profitable in both halves, and on the real second-by-second
prices 4% are (1h: 43% and 3%). That is 0.05R to 0.10R per trade of profit that never
existed. If a trailing stop has looked excellent in your own TradingView tests on the
higher timeframes, this is the most likely reason.

The same settings (a random sample of the search: 300 per timeframe, 200 on 5m and below) with the trailing stop off and with
each of the 42 Trail Activation x Trail Offset pairs, nothing else changed, on the second-by-second price path. "Both halves" =
share of the settings positive after costs in both halves of the search window. The best of 42 pairs is partly the luckiest of
42, so it was chosen on one random half of the settings and is read on the other half. The last three columns are for a tight
pair (0.5 / 0.5 ATR): what a walk on the chart's candles shows, how much profit per trade that invents, and the real figure.

| Chart | Trailing off: both halves | With trailing: median of the 42 pairs | Pairs above "off" | Best pair chosen on half the settings (activation / offset) | On the other half: with it vs trailing off | Shipped pair 1.5 / 1.0 | It makes a setting better / leaves it unchanged / worse | Tight pair on chart candles | Profit it invents per trade | Tight pair second by second |
|---|---|---|---|---|---|---|---|---|---|---|
| 1m | 0.0% | 0.0% | 7 of 42 | 0.5 / 0.5 | 0.0% vs 0.0% | 0.0% | 42% / 10% / 49% | 0.0% | +0.07R | 0.0% |
| 2m | 6.5% | 1.0% | 0 of 42 | 1 / 2 | 0.0% vs 7.0% | 1.0% | 44% / 18% / 38% | 0.5% | +0.05R | 0.0% |
| 3m | 3.0% | 1.0% | 0 of 42 | 2 / 0.5 | 1.0% vs 3.0% | 1.0% | 42% / 10% / 48% | 0.0% | +0.07R | 0.0% |
| 5m | 4.5% | 1.5% | 0 of 42 | 6 / 3 | 0.0% vs 1.0% | 1.5% | 34% / 16% / 50% | 1.5% | +0.08R | 0.0% |
| 10m | 7.3% | 3.5% | 0 of 42 | 6 / 1.5 | 4.7% vs 8.7% | 2.7% | 37% / 16% / 48% | 7.7% | +0.07R | 0.7% |
| 15m | 11.3% | 6.8% | 0 of 42 | 6 / 1.5 | 12.0% vs 14.0% | 6.0% | 38% / 13% / 49% | 13.3% | +0.09R | 0.3% |
| 30m | 10.0% | 6.8% | 1 of 42 | 3 / 3 | 5.3% vs 8.7% | 4.3% | 33% / 16% / 51% | 20.0% | +0.09R | 0.7% |
| 1h | 13.0% | 9.2% | 0 of 42 | 4 / 3 | 7.3% vs 11.3% | 7.0% | 33% / 13% / 53% | 43.0% | +0.10R | 3.3% |
| 4h | 14.7% | 14.2% | 17 of 42 | 0.5 / 3 | 20.7% vs 17.3% | 8.7% | 38% / 17% / 45% | 49.0% | +0.08R | 4.3% |

All 42 pairs for every timeframe: `results/TRAILING.md`.

### How fine must the price path be?

The pick of each timeframe, and the same pick with a tight trailing stop (activation 0.5 x ATR,
offset 0.5 x ATR), with the orders walked on ever finer bars. Search window, net of costs.

| Chart | Setting | Chart candles | 1-minute bars | 15-second bars | 5-second bars | 1-second bars |
|---|---|---|---|---|---|---|
| 1m | the pick | +107.1R | +107.1R | +107.1R | +107.1R | +107.1R |
| 1m | the pick with a 0.5 / 0.5 trailing stop | -9.3R | -9.3R | -12.1R | -12.8R | -12.8R |
| 2m | the pick | +12.0R | +12.0R | +12.0R | +12.0R | +12.0R |
| 2m | the pick with a 0.5 / 0.5 trailing stop | +2.2R | +1.5R | +1.3R | +1.3R | +0.6R |
| 3m | the pick | +23.4R | +23.4R | +23.4R | +23.4R | +23.4R |
| 3m | the pick with a 0.5 / 0.5 trailing stop | +2.7R | +0.5R | -0.3R | -0.4R | -0.5R |
| 5m | the pick | +16.1R | +16.1R | +16.1R | +16.1R | +16.1R |
| 5m | the pick with a 0.5 / 0.5 trailing stop | -0.3R | -1.8R | -2.5R | -2.8R | -2.9R |
| 10m | the pick (uses the trailing stop) | +16.8R | +14.5R | +14.5R | +14.5R | +14.5R |
| 10m | the pick with a 0.5 / 0.5 trailing stop | +5.4R | +3.5R | +3.1R | +3.0R | +3.0R |
| 15m | the pick | +21.1R | +21.1R | +21.1R | +21.1R | +21.1R |
| 15m | the pick with a 0.5 / 0.5 trailing stop | +11.4R | -2.0R | -2.6R | -2.6R | -2.6R |
| 30m | the pick (uses the trailing stop) | +21.4R | +21.5R | +21.4R | +20.9R | +20.2R |
| 30m | the pick with a 0.5 / 0.5 trailing stop | +11.3R | +3.7R | +3.2R | +3.2R | +3.2R |
| 1h | the pick | +22.0R | +22.0R | +22.0R | +22.0R | +22.0R |
| 1h | the pick with a 0.5 / 0.5 trailing stop | +16.9R | +7.2R | +6.9R | +6.9R | +6.8R |
| 4h | the pick | +32.9R | +35.2R | +35.2R | +35.2R | +35.2R |
| 4h | the pick with a 0.5 / 0.5 trailing stop | +12.6R | -0.5R | -0.5R | -0.5R | -0.5R |

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

Share of the search's settings positive in both halves, by one input's value (all other inputs random). Each cell: after costs /
before costs / the commission a typical setting of the group paid in three years. Where two values differ after costs but not
before, the difference is commission, not better trades.

| Chart | With the filter | Inverted | Trailing off | Trailing on | Stop up to 1 ATR | Stop 4 ATR and more | No target | Target on | No time stop | Time stop on |
|---|---|---|---|---|---|---|---|---|---|---|
| 1m | 1.4% / 38.3% / 257R | 0.4% / 33.0% / 284R | 1.4% / 32.2% / 267R | 0.1% / 40.9% / 277R | 0.7% / 46.9% / 809R | 1.3% / 30.5% / 119R | 2.3% / 39.8% / 242R | 0.2% / 33.6% / 284R | 1.6% / 35.6% / 286R | 0.1% / 35.7% / 253R |
| 2m | 4.1% / 30.6% / 48R | 1.4% / 23.1% / 42R | 3.9% / 26.1% / 45R | 1.1% / 28.1% / 46R | 0.4% / 26.3% / 165R | 4.3% / 31.1% / 18R | 5.8% / 25.3% / 47R | 1.3% / 27.7% / 45R | 4.7% / 26.2% / 44R | 0.6% / 27.7% / 47R |
| 3m | 5.8% / 41.9% / 51R | 0.9% / 19.0% / 51R | 4.8% / 29.5% / 50R | 1.2% / 31.1% / 52R | 0.5% / 29.8% / 173R | 5.2% / 30.6% / 22R | 5.3% / 30.6% / 47R | 2.3% / 30.0% / 54R | 5.0% / 30.5% / 51R | 1.4% / 29.8% / 50R |
| 5m | 6.0% / 48.0% / 61R | 0.6% / 16.1% / 63R | 4.2% / 32.0% / 62R | 1.8% / 31.2% / 63R | 1.0% / 34.3% / 226R | 4.5% / 29.3% / 27R | 6.1% / 34.3% / 60R | 1.8% / 30.4% / 65R | 4.7% / 32.4% / 64R | 1.5% / 30.8% / 62R |
| 10m | 10.4% / 41.0% / 22R | 2.2% / 13.7% / 21R | 7.7% / 27.5% / 21R | 4.4% / 27.1% / 22R | 2.3% / 27.6% / 78R | 8.6% / 27.4% / 8R | 9.5% / 27.9% / 20R | 4.7% / 27.1% / 22R | 8.5% / 28.7% / 21R | 3.7% / 25.8% / 22R |
| 15m | 12.8% / 47.7% / 24R | 1.6% / 12.0% / 24R | 8.8% / 30.3% / 24R | 4.7% / 28.2% / 24R | 2.6% / 26.6% / 81R | 9.7% / 29.4% / 9R | 9.8% / 28.7% / 22R | 5.7% / 29.8% / 24R | 9.3% / 30.4% / 24R | 4.6% / 28.4% / 24R |
| 30m | 15.0% / 48.3% / 19R | 2.3% / 11.9% / 19R | 10.1% / 30.9% / 19R | 6.3% / 27.9% / 19R | 4.4% / 29.3% / 68R | 9.7% / 26.7% / 7R | 12.7% / 31.8% / 19R | 6.5% / 28.6% / 19R | 9.7% / 29.3% / 19R | 7.2% / 30.1% / 19R |
| 1h | 16.7% / 47.0% / 14R | 3.0% / 10.7% / 15R | 11.6% / 29.7% / 14R | 7.3% / 27.4% / 15R | 4.8% / 26.5% / 56R | 11.7% / 26.1% / 6R | 13.6% / 31.0% / 14R | 8.0% / 27.6% / 15R | 11.0% / 29.1% / 14R | 8.5% / 28.4% / 15R |
| 4h | 27.1% / 47.7% / 6R | 3.5% / 8.2% / 6R | 16.0% / 27.6% / 6R | 14.3% / 28.2% / 6R | 10.5% / 25.1% / 23R | 16.1% / 26.1% / 2R | 19.3% / 30.4% / 6R | 13.3% / 26.6% / 6R | 15.6% / 27.8% / 6R | 14.9% / 27.9% / 6R |

Every input, value by value, for every timeframe: `results/INPUTS.md`.

**Before costs, the trade direction is the only input that clearly separates good from bad
on its own.** (The filter timeframe does too once the direction is fixed, on charts up to
15m: last two paragraphs.) From 5m up, 41% to 48% of with-the-filter settings are positive
in both halves before costs, against 8% to 16% of inverted ones; below 5m the gap narrows
(1m: 38% against 33%). Trailing on or off, target or none, time stop or none: before costs
each pair lands within a few points of the other (except on 1m, where trailing and target
differ by 6 to 9 points). Stop size shows no steady pattern before costs: a 0.5 ATR stop is
the worst on 15m and 4h but among the best on 1m, 3m and 5m. After costs it is the worst on
every chart.

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

**The faster the filter, the less the direction is worth.** Settings positive in both halves
before costs, with the filter / inverted, by filter timeframe (settings with at least 30
trades in each half; `tools/direction_by_filter.py`, log in
`results/direction_by_filter.txt`):

| Chart | Filter on the chart's own timeframe | 5m filter | 15m filter | 30m filter | 1h filter | 4h filter | 1D filter |
|---|---|---|---|---|---|---|---|
| 1m | 25% / 41% * | 31% / 47% * | 39% / 36% | 45% / 29% | 46% / 23% | 44% / 26% | 39% / 29% |
| 2m | 20% / 35% * | - | - | 29% / 27% | 32% / 19% | 35% / 20% | 37% / 15% |
| 3m | 27% / 25% | - | 30% / 29% | 44% / 17% | 46% / 17% | 53% / 14% | 50% / 13% |
| 5m | 35% / 22% | see first column | 43% / 20% | 51% / 15% | 55% / 13% | 56% / 12% | 48% / 15% |
| 10m | 34% / 18% | - | - | 34% / 19% | 39% / 15% | 48% / 7% | 48% / 10% |
| 15m | 39% / 14% | - | see first column | 46% / 15% | 49% / 11% | 55% / 9% | 51% / 11% |
| 30m | 48% / 12% | - | 48% / 15% | see first column | 44% / 14% | 51% / 8% | 50% / 10% |
| 1h | 48% / 11% | - | 44% / 12% | 45% / 12% | see first column | 51% / 8% | 49% / 9% |
| 4h | 48% / 8% | - | 47% / 8% | 48% / 8% | 49% / 7% | see first column | 45% / 10% |

\* inverted ahead.

With a 4h filter the with-the-filter side is 15 to 46 points ahead on every chart; on the
charts from 3m to 1h fewer than 2% of luck-only worlds show a gap that large (1m: 3%, 4h:
11%, 2m: 23%). With the filter on the chart's own timeframe the gap shrinks to 14 and 17
points on the 5m and 10m charts, is gone on 3m (2 points) and is reversed on 1m and 2m: on
the 1m chart with a 1m or 5m filter and on the 2m chart with a 2m filter the inverted side
is ahead by 15 to 17 points. Chance produces a gap that size in 5% to 10% of luck-only
worlds, so the reversal may be luck; what it rules out is reading "trade with the filter"
as a rule for fast filters. After costs it matters little there: in those three cells 1% to
5% of with-the-filter settings and 0% to 3% of inverted ones made money over the three
years. Two charts show no gap beyond the luck-only range at any filter timeframe before
costs: 2m (5% to 77% of luck-only worlds show a gap as large) and 4h (7% to 13%; with few
trades per setting luck alone produces gaps of 40 points there about one time in ten). On 2m
the advantage of section 4.4 shows only after costs.

## 7. Settings per timeframe

### 1m: PAPER-TRADE

PAPER-TRADE because it made money on 2021-2023, which it was not chosen on, at base and stressed costs, but only in 93% of resamples of its weeks (95% needed). File: `presets/AMVI_FGF_BTCUSDT_1m.pine` (watch with alerts only; no money).

- On data it was not chosen on (untouched 2021-01 to 2023-10): 93 trades (49L/44S), +54.8R, PF 1.75, 26% winners, max DD 15.2R, longest losing streak 12, 16 of 34 months positive; stressed costs +49.0R; positive in 93% of resamples of its weeks. 77% of that result came in 2023. +22.1R of it is a trade still open at the end of the period, marked at the last close (without it +32.7R).
- Where it was chosen (search window): 145 trades (73L/72S), +107.1R, PF 1.83, 18% winners, max DD 29.2R, longest losing streak 11, 13 of 36 months positive; halves +50.2 / +56.9R. The best month (2026-08) made +70.3R of it. In luck-only worlds, where no setting has an edge, a pick chosen the same way still shows about +65R here (95th percentile +365R) and -12R on months it was not chosen on.
- Holding time: 3.6 days on average and 47.7 days at most in the search window (6.4 days and 46.5 days on the untouched period): longer than your lab's holding limit (hours to one day).
- With 0.5% of equity at risk per trade and the position capped at 5x equity (the calibrated files' sizing), the search-window result is about +53.6% in three years with a worst drawdown of about 14.6% (no compounding), and the untouched period about +27.4% with a worst drawdown of 7.6%. The stop is 1.29% of price on average, so 0.5% risk asks for about 0.4x leverage.
- Costs (search window): Bitget 0.06% +104.3R; no costs +124.5R; stressed +92.8R; break-even commission 0.424% per side. Fees took 14.3R and funding +3.0R.
- Price path (search window): second by second +107.1R; on 1-minute bars +107.1R; on the chart's candles +107.1R.
- On TradingView (chart candles, 0.06% commission, no funding) the Strategy Tester should show about 145 trades, 18% profitable, profit factor about 1.8, net profit about +54% for 2023-11-01 to 2026-10-31.
- The selection method on this timeframe, search window -> untouched period: the 12 steadiest candidates made +60.3R on average (83% of them made money; positive in 96.9% of resamples of the months): pass. Random groups with the candidates' trade directions (1 of 12 inverted) made -1438.1R on average; the candidates beat 95% of such groups, so the choice adds something beyond the direction.
- Not fragile: 88% of 25 neighbouring settings positive in both halves; sensitive to: Time Stop; Normalization Period; Take Profit.
- Concentration (search window): 10 biggest trades +207.5R, all others -100.4R; positive in 91.0% of resamples of its weeks.
- Same inputs, other trade direction: -22.5R.

| Input | Shipped | This file |
|---|---|---|
| Fast ATR Period (`fastATRPeriod`) | 7 | 14 |
| StdDev Period (`stdDevPeriod`) | 20 | 10 |
| Candle Range Period (`candleRangePeriod`) | 20 | 30 |
| AATR Weight (`aatrWeight`) | 0.35 | 0.55 |
| VR Weight (`vrWeight`) | 0.25 | 0.15 |
| NSD Weight (`nsdWeight`) | 0.25 | 0.15 |
| Trade direction (`amviTradeDir`) | "Inverted" | "Follow the filter" |
| Stop Loss (x ATR, 0 = off) (`slMult`) | 1.0 | 8.0 |
| Filter timeframe (`fgfTf`) | "60" | "D" |
| Parent obedience timeframe (`fgfParentTf`) | "60" | "D" |
| Minimum child zones aligned (`fgfMinAligned`) | 0 | 1 |
| 15m (`en15`) | true | false |
| 4h (`en240`) | true | false |

| Year | Trades | Net R | Winners | Max DD |
|---|---|---|---|---|
| 2021 (untouched) | 23 | +18.4 | 35% | 11.1 |
| 2022 (untouched) | 39 | -5.6 | 18% | 14.1 |
| 2023 (Jan-Oct, untouched) | 31 | +42.0 | 29% | 13.3 |
| 2023 (Nov-Dec) | 10 | +7.4 | 10% | 5.6 |
| 2024 | 43 | +35.0 | 28% | 10.9 |
| 2025 | 55 | -14.7 | 15% | 22.5 |
| 2026 (Jan-Oct) | 37 | +79.4 | 14% | 12.0 |

| Exit (search window) | Trades | Net R | Average |
|---|---|---|---|
| stop loss | 118 | -129.6 | -1.10 |
| reversal | 27 | +236.7 | +8.77 |

### 2m: NOT RECOMMENDED

NOT RECOMMENDED because it does not hold up on 2021-2023 (it loses there at stressed costs), although the 25 steadiest candidates passed the test there as a group. No file was written. The inputs below are listed only so that the result can be reproduced; they are not a setup to trade.

- On data it was not chosen on (untouched 2021-01 to 2023-10): 108 trades (53L/55S), +1.3R, PF 1.05, 77% winners, max DD 4.2R, longest losing streak 4, 16 of 34 months positive; stressed costs -3.4R; positive in 60% of resamples of its weeks. 96% of that result came in 2023.
- Where it was chosen (search window): 97 trades (46L/51S), +12.0R, PF 1.81, 86% winners, max DD 2.6R, longest losing streak 2, 24 of 36 months positive; halves +6.5 / +5.5R. The best month (2024-05) made +1.4R of it. In luck-only worlds, where no setting has an edge, a pick chosen the same way still shows about +52R here (95th percentile +236R) and -9R on months it was not chosen on.
- Holding time: 6 hours on average and 5.5 days at most in the search window (6 hours and 2.3 days on the untouched period): longer than your lab's holding limit (hours to one day).
- With 0.5% of equity at risk per trade and the position capped at 5x equity (the calibrated files' sizing), the search-window result is about +6.0% in three years with a worst drawdown of about 1.3% (no compounding), and the untouched period about +0.6% with a worst drawdown of 2.1%. The stop is 2.20% of price on average, so 0.5% risk asks for about 0.2x leverage.
- Costs (search window): Bitget 0.06% +10.9R; no costs +17.1R; stressed +6.8R; break-even commission 0.166% per side. Fees took 5.2R and funding -0.0R.
- Price path (search window): second by second +12.0R; on 1-minute bars +12.0R; on the chart's candles +12.0R.
- On TradingView (chart candles, 0.06% commission, no funding) the Strategy Tester should show about 97 trades, 86% profitable, profit factor about 1.7, net profit about +5% for 2023-11-01 to 2026-10-31.
- The selection method on this timeframe, search window -> untouched period: the 25 steadiest candidates made +54.0R on average (72% of them made money; positive in 96.1% of resamples of the months): pass. Random groups with the candidates' trade directions (4 of 25 inverted) made -50.2R on average; the candidates beat 95% of such groups, so the choice adds something beyond the direction.
- Not fragile: 92% of 25 neighbouring settings positive in both halves; sensitive to: No-trade band, ATR mult; Time Stop.
- Concentration (search window): 10 biggest trades +3.5R, all others +8.4R; positive in 99.5% of resamples of its weeks.
- Same inputs, other trade direction: -22.4R.

| Input | Shipped | This pick |
|---|---|---|
| Fast ATR Period (`fastATRPeriod`) | 7 | 10 |
| StdDev Period (`stdDevPeriod`) | 20 | 30 |
| AATR Weight (`aatrWeight`) | 0.35 | 0.2 |
| VR Weight (`vrWeight`) | 0.25 | 0.5 |
| NSD Weight (`nsdWeight`) | 0.25 | 0.15 |
| High Vol Threshold (`highVolThreshold`) | 60.0 | 50.0 |
| Trade direction (`amviTradeDir`) | "Inverted" | "Follow the filter" |
| Candles to wait after an entry (0 = off) (`amviWait`) | 0 | 20 |
| Stop Loss (x ATR, 0 = off) (`slMult`) | 1.0 | 8.0 |
| Take Profit (x ATR, 0 = off) (`tpMult`) | 0.0 | 3.0 |
| Filter timeframe (`fgfTf`) | "60" | "240" |
| Level (`fgfLvMode`) | "Signal close" | "Entry price" |
| No-trade band, ATR mult (`fgfBandAtr`) | 0.5 | 1.5 |
| Entry distance, ATR mult (ATR unit) (`fgfEntryDistAtr`) | 0.25 | 0.1 |
| Parent obedience timeframe (`fgfParentTf`) | "60" | "D" |
| 15m (`en15`) | true | false |
| 30m (`en30`) | false | true |
| 1h (`en60`) | true | false |
| 4h (`en240`) | true | false |

| Year | Trades | Net R | Winners | Max DD |
|---|---|---|---|---|
| 2021 (untouched) | 30 | -0.9 | 73% | 2.8 |
| 2022 (untouched) | 40 | +1.0 | 78% | 3.1 |
| 2023 (Jan-Oct, untouched) | 38 | +1.2 | 79% | 2.6 |
| 2023 (Nov-Dec) | 6 | +2.0 | 100% | 0.0 |
| 2024 | 36 | +3.6 | 83% | 1.8 |
| 2025 | 24 | +2.1 | 83% | 2.1 |
| 2026 (Jan-Oct) | 31 | +4.4 | 87% | 1.1 |

| Exit (search window) | Trades | Net R | Average |
|---|---|---|---|
| stop loss | 14 | -14.7 | -1.05 |
| take profit | 83 | +26.7 | +0.32 |

### 3m: USABLE

USABLE because it made money on 2021-2023, which it was not chosen on, at base and stressed costs and in 100% of resamples of its weeks; the 25 steadiest candidates did too as a group; the three hold-out tests inside the last three years fail. File: `presets/AMVI_FGF_BTCUSDT_3m.pine` (test with alerts first; small size at most).

- On data it was not chosen on (untouched 2021-01 to 2023-10): 72 trades (37L/35S), +20.6R, PF 2.56, 54% winners, max DD 2.9R, longest losing streak 4, 20 of 34 months positive; stressed costs +16.9R; positive in 100% of resamples of its weeks. 80% of that result came in 2023.
- Where it was chosen (search window): 79 trades (45L/34S), +23.4R, PF 2.13, 61% winners, max DD 2.9R, longest losing streak 4, 19 of 36 months positive; halves +11.3 / +12.0R. The best month (2024-08) made +4.4R of it. In luck-only worlds, where no setting has an edge, a pick chosen the same way still shows about +45R here (95th percentile +181R) and -8R on months it was not chosen on.
- Holding time: 4 hours on average and 5 hours at most in the search window (4 hours and 5 hours on the untouched period): inside your lab's holding limit (hours to one day).
- With 0.5% of equity at risk per trade and the position capped at 5x equity (the calibrated files' sizing), the search-window result is about +11.7% in three years with a worst drawdown of about 1.4% (no compounding), and the untouched period about +10.3% with a worst drawdown of 1.4%. The stop is 1.72% of price on average, so 0.5% risk asks for about 0.3x leverage.
- Costs (search window): Bitget 0.06% +22.2R; no costs +29.0R; stressed +17.7R; break-even commission 0.258% per side. Fees took 5.6R and funding +0.1R.
- Price path (search window): second by second +23.4R; on 1-minute bars +23.4R; on the chart's candles +23.4R.
- On TradingView (chart candles, 0.06% commission, no funding) the Strategy Tester should show about 79 trades, 58% profitable, profit factor about 2.1, net profit about +11% for 2023-11-01 to 2026-10-31.
- The selection method on this timeframe, search window -> untouched period: the 25 steadiest candidates made +18.6R on average (80% of them made money; positive in 98.7% of resamples of the months): pass. Random groups with the candidates' trade directions (2 of 25 inverted) made -72.3R on average; the candidates beat 95% of such groups, so the choice adds something beyond the direction.
- Not fragile: 93% of 28 neighbouring settings positive in both halves; sensitive to: Burst threshold, ATR mult; Min TFs Above High Vol.
- Concentration (search window): 10 biggest trades +14.4R, all others +9.0R; positive in 99.6% of resamples of its weeks.
- Same inputs, other trade direction: -24.3R.

| Input | Shipped | This file |
|---|---|---|
| Fast ATR Period (`fastATRPeriod`) | 7 | 5 |
| Slow ATR Period (`slowATRPeriod`) | 100 | 50 |
| Candle Range Period (`candleRangePeriod`) | 20 | 30 |
| Normalization Period (`normalizationPeriod`) | 200 | 400 |
| AATR Weight (`aatrWeight`) | 0.35 | 0.2 |
| VR Weight (`vrWeight`) | 0.25 | 0.5 |
| NSD Weight (`nsdWeight`) | 0.25 | 0.15 |
| High Vol Threshold (`highVolThreshold`) | 60.0 | 70.0 |
| Trade direction (`amviTradeDir`) | "Inverted" | "Follow the filter" |
| Candles to wait after an entry (0 = off) (`amviWait`) | 0 | 20 |
| Exit ATR Length (`exitAtrLen`) | 14 | 7 |
| Stop Loss (x ATR, 0 = off) (`slMult`) | 1.0 | 4.0 |
| Take Profit (x ATR, 0 = off) (`tpMult`) | 0.0 | 6.0 |
| Time Stop (bars, 0 = off) (`maxBars`) | 0 | 96 |
| Filter timeframe (`fgfTf`) | "60" | "240" |
| No-trade band, ATR mult (`fgfBandAtr`) | 0.5 | 1.5 |
| Allow trading against the signal (`fgfAgainst`) | true | false |
| Require burst gate (`fgfUseBurst`) | false | true |
| Allow any combo (`fgfAnyCombo`) | true | false |
| Parent obedience timeframe (`fgfParentTf`) | "60" | "240" |
| Minimum child zones aligned (`fgfMinAligned`) | 0 | 2 |
| 15m (`en15`) | true | false |
| 30m (`en30`) | false | true |
| 1h (`en60`) | true | false |

| Year | Trades | Net R | Winners | Max DD |
|---|---|---|---|---|
| 2021 (untouched) | 24 | +4.4 | 58% | 2.5 |
| 2022 (untouched) | 15 | -0.2 | 40% | 2.9 |
| 2023 (Jan-Oct, untouched) | 33 | +16.4 | 58% | 1.7 |
| 2023 (Nov-Dec) | 6 | -0.8 | 50% | 1.2 |
| 2024 | 22 | +11.9 | 73% | 2.2 |
| 2025 | 31 | +6.0 | 55% | 2.9 |
| 2026 (Jan-Oct) | 20 | +6.3 | 60% | 2.9 |

| Exit (search window) | Trades | Net R | Average |
|---|---|---|---|
| stop loss | 14 | -15.1 | -1.08 |
| take profit | 23 | +32.5 | +1.41 |
| time stop | 42 | +6.0 | +0.14 |

### 5m: NOT RECOMMENDED

NOT RECOMMENDED because it does not hold up on 2021-2023 (it lost there), although the 25 steadiest candidates passed the test there as a group. No file was written. The inputs below are listed only so that the result can be reproduced; they are not a setup to trade.

- On data it was not chosen on (untouched 2021-01 to 2023-10): 70 trades (44L/26S), -1.0R, PF 0.98, 46% winners, max DD 6.7R, longest losing streak 5, 20 of 34 months positive; stressed costs -4.8R; positive in 45% of resamples of its weeks.
- Where it was chosen (search window): 68 trades (38L/30S), +16.1R, PF 1.51, 56% winners, max DD 5.2R, longest losing streak 3, 20 of 36 months positive; halves +7.1 / +9.1R. The best month (2024-02) made +5.0R of it. In luck-only worlds, where no setting has an edge, a pick chosen the same way still shows about +36R here (95th percentile +152R) and -8R on months it was not chosen on.
- Holding time: 22 hours on average and 8.5 days at most in the search window (23 hours and 7.9 days on the untouched period): longer than your lab's holding limit (hours to one day).
- With 0.5% of equity at risk per trade and the position capped at 5x equity (the calibrated files' sizing), the search-window result is about +8.1% in three years with a worst drawdown of about 2.6% (no compounding), and the untouched period about -0.5% with a worst drawdown of 3.3%. The stop is 1.80% of price on average, so 0.5% risk asks for about 0.3x leverage.
- Costs (search window): Bitget 0.06% +15.2R; no costs +20.7R; stressed +11.6R; break-even commission 0.229% per side. Fees took 4.5R and funding +0.0R.
- Price path (search window): second by second +16.1R; on 1-minute bars +16.1R; on the chart's candles +16.1R.
- On TradingView (chart candles, 0.06% commission, no funding) the Strategy Tester should show about 68 trades, 56% profitable, profit factor about 1.5, net profit about +8% for 2023-11-01 to 2026-10-31.
- The selection method on this timeframe, search window -> untouched period: the 25 steadiest candidates made +27.0R on average (76% of them made money; positive in 99.1% of resamples of the months): pass. Random groups with the candidates' trade directions (4 of 25 inverted) made -150.2R on average; the candidates beat 95% of such groups, so the choice adds something beyond the direction.
- Not fragile: 96% of 28 neighbouring settings positive in both halves; sensitive to: Burst threshold, ATR mult.
- Concentration (search window): 10 biggest trades +13.0R, all others +3.2R; positive in 96.0% of resamples of its weeks.
- Same inputs, other trade direction: -26.8R.

| Input | Shipped | This pick |
|---|---|---|
| Slow ATR Period (`slowATRPeriod`) | 100 | 200 |
| Candle Range Period (`candleRangePeriod`) | 20 | 30 |
| Normalization Period (`normalizationPeriod`) | 200 | 400 |
| AATR Weight (`aatrWeight`) | 0.35 | 0.2 |
| VR Weight (`vrWeight`) | 0.25 | 0.5 |
| NSD Weight (`nsdWeight`) | 0.25 | 0.15 |
| Trade direction (`amviTradeDir`) | "Inverted" | "Follow the filter" |
| Candles to wait after an entry (0 = off) (`amviWait`) | 0 | 10 |
| Exit ATR Length (`exitAtrLen`) | 14 | 21 |
| Stop Loss (x ATR, 0 = off) (`slMult`) | 1.0 | 6.0 |
| Take Profit (x ATR, 0 = off) (`tpMult`) | 0.0 | 8.0 |
| Filter timeframe (`fgfTf`) | "60" | "240" |
| Level (`fgfLvMode`) | "Signal close" | "Entry price" |
| Check price on (`fgfCheckIn`) | "Tick" | "Level at candle open" |
| No-trade band, ATR mult (`fgfBandAtr`) | 0.5 | 1.5 |
| Allow trading against the signal (`fgfAgainst`) | true | false |
| Entry distance, ATR mult (ATR unit) (`fgfEntryDistAtr`) | 0.25 | 0.1 |
| Require burst gate (`fgfUseBurst`) | false | true |
| Allow any combo (`fgfAnyCombo`) | true | false |
| Parent obedience timeframe (`fgfParentTf`) | "60" | "240" |
| 5m (`en5`) | false | true |
| 15m (`en15`) | true | false |
| 1h (`en60`) | true | false |
| 4h (`en240`) | true | false |

| Year | Trades | Net R | Winners | Max DD |
|---|---|---|---|---|
| 2021 (untouched) | 19 | +0.9 | 47% | 5.5 |
| 2022 (untouched) | 24 | -2.2 | 42% | 5.9 |
| 2023 (Jan-Oct, untouched) | 27 | +0.4 | 48% | 5.4 |
| 2023 (Nov-Dec) | 3 | -0.9 | 33% | 2.1 |
| 2024 | 23 | +8.3 | 61% | 3.1 |
| 2025 | 23 | +1.1 | 48% | 5.2 |
| 2026 (Jan-Oct) | 19 | +7.6 | 63% | 2.2 |

| Exit (search window) | Trades | Net R | Average |
|---|---|---|---|
| stop loss | 30 | -31.9 | -1.06 |
| take profit | 38 | +48.0 | +1.26 |

### 10m: NOT RECOMMENDED

NOT RECOMMENDED because it does not hold up on 2021-2023 (its gain there stays positive in only 81% of resamples of its weeks, so a few good weeks carry it), although the 25 steadiest candidates passed the test there as a group. No file was written. The inputs below are listed only so that the result can be reproduced; they are not a setup to trade.

- On data it was not chosen on (untouched 2021-01 to 2023-10): 65 trades (38L/27S), +8.7R, PF 1.31, 58% winners, max DD 6.4R, longest losing streak 6, 14 of 34 months positive; stressed costs +6.0R; positive in 81% of resamples of its weeks. All of that result came in 2023; the other years together lost.
- Where it was chosen (search window): 85 trades (45L/40S), +14.5R, PF 1.44, 62% winners, max DD 5.7R, longest losing streak 4, 18 of 36 months positive; halves +7.3 / +7.2R. The best month (2025-11) made +3.8R of it. In luck-only worlds, where no setting has an edge, a pick chosen the same way still shows about +31R here (95th percentile +123R) and -5R on months it was not chosen on.
- Holding time: 17 hours on average and 6.8 days at most in the search window (22 hours and 6.8 days on the untouched period): longer than your lab's holding limit (hours to one day).
- With 0.5% of equity at risk per trade and the position capped at 5x equity (the calibrated files' sizing), the search-window result is about +7.3% in three years with a worst drawdown of about 2.9% (no compounding), and the untouched period about +4.4% with a worst drawdown of 3.2%. The stop is 2.13% of price on average, so 0.5% risk asks for about 0.2x leverage.
- Costs (search window): Bitget 0.06% +13.6R; no costs +19.2R; stressed +10.2R; break-even commission 0.211% per side. Fees took 4.5R and funding +0.1R.
- Price path (search window): second by second +14.5R; on 1-minute bars +14.5R; on the chart's candles +16.8R.
- On TradingView (chart candles, 0.06% commission, no funding) the Strategy Tester should show about 85 trades, 62% profitable, profit factor about 1.5, net profit about +8% for 2023-11-01 to 2026-10-31.
- The selection method on this timeframe, search window -> untouched period: the 25 steadiest candidates made +25.3R on average (80% of them made money; positive in 99.5% of resamples of the months): pass. Random groups with the candidates' trade directions (4 of 25 inverted) made -19.8R on average; the candidates beat 95% of such groups, so the choice adds something beyond the direction.
- Not fragile: 94% of 31 neighbouring settings positive in both halves; sensitive to: Candle Range Period; Time Stop.
- Concentration (search window): 10 biggest trades +14.3R, all others +0.2R; positive in 95.3% of resamples of its weeks.
- Same inputs, other trade direction: -28.7R.
- Trailing stop restarted at every candle close (if TradingView does that): search window +15.4R, untouched +7.8R.

| Input | Shipped | This pick |
|---|---|---|
| Fast ATR Period (`fastATRPeriod`) | 7 | 10 |
| StdDev Period (`stdDevPeriod`) | 20 | 30 |
| Normalization Period (`normalizationPeriod`) | 200 | 400 |
| AATR Weight (`aatrWeight`) | 0.35 | 0.2 |
| VR Weight (`vrWeight`) | 0.25 | 0.15 |
| NSD Weight (`nsdWeight`) | 0.25 | 0.5 |
| High Vol Threshold (`highVolThreshold`) | 60.0 | 80.0 |
| Trade direction (`amviTradeDir`) | "Inverted" | "Follow the filter" |
| Candles to wait after an entry (0 = off) (`amviWait`) | 0 | 1 |
| Stop Loss (x ATR, 0 = off) (`slMult`) | 1.0 | 4.0 |
| Take Profit (x ATR, 0 = off) (`tpMult`) | 0.0 | 6.0 |
| Use ATR Trailing Stop (`useTrail`) | false | true |
| Trail Activation (x ATR) (`trailActMul`) | 1.5 | 4.0 |
| Trail Offset (x ATR) (`trailOffMul`) | 1.0 | 1.5 |
| Filter timeframe (`fgfTf`) | "60" | "240" |
| Allow trading against the signal (`fgfAgainst`) | true | false |
| Prior drift bars (`fgfDriftBars`) | 60 | 120 |
| Use prior drift filter (`fgfUseDrift`) | false | true |
| Parent obedience timeframe (`fgfParentTf`) | "60" | "240" |
| 15m (`en15`) | true | false |
| 30m (`en30`) | false | true |
| 4h (`en240`) | true | false |

| Year | Trades | Net R | Winners | Max DD |
|---|---|---|---|---|
| 2021 (untouched) | 17 | -1.0 | 47% | 6.4 |
| 2022 (untouched) | 20 | -2.7 | 50% | 6.0 |
| 2023 (Jan-Oct, untouched) | 28 | +12.4 | 71% | 2.1 |
| 2023 (Nov-Dec) | 8 | -0.2 | 50% | 2.1 |
| 2024 | 23 | +5.6 | 65% | 3.1 |
| 2025 | 27 | +8.8 | 70% | 3.2 |
| 2026 (Jan-Oct) | 27 | +0.4 | 56% | 5.7 |

| Exit (search window) | Trades | Net R | Average |
|---|---|---|---|
| stop loss | 31 | -32.6 | -1.05 |
| take profit | 10 | +14.3 | +1.43 |
| trailing stop | 43 | +33.1 | +0.77 |
| open at the end | 1 | -0.3 | -0.29 |

### 15m: USABLE

USABLE because it made money on 2021-2023, which it was not chosen on, at base and stressed costs and in 99% of resamples of its weeks; the 25 steadiest candidates did too as a group; the three hold-out tests inside the last three years fail. File: `presets/AMVI_FGF_BTCUSDT_15m.pine` (test with alerts first; small size at most).

- On data it was not chosen on (untouched 2021-01 to 2023-10): 232 trades (112L/120S), +19.7R, PF 1.41, 56% winners, max DD 7.0R, longest losing streak 5, 22 of 34 months positive; stressed costs +14.7R; positive in 99% of resamples of its weeks. 69% of that result came in 2021.
- Where it was chosen (search window): 284 trades (134L/150S), +21.1R, PF 1.35, 54% winners, max DD 3.7R, longest losing streak 5, 24 of 36 months positive; halves +10.7 / +10.4R. The best month (2026-06) made +3.8R of it. In luck-only worlds, where no setting has an edge, a pick chosen the same way still shows about +29R here (95th percentile +95R) and -5R on months it was not chosen on.
- Holding time: 19 hours on average and 24 hours at most in the search window (18 hours and 24 hours on the untouched period): inside your lab's holding limit (hours to one day).
- With 0.5% of equity at risk per trade and the position capped at 5x equity (the calibrated files' sizing), the search-window result is about +10.6% in three years with a worst drawdown of about 1.8% (no compounding), and the untouched period about +9.8% with a worst drawdown of 3.5%. The stop is 4.27% of price on average, so 0.5% risk asks for about 0.1x leverage.
- Costs (search window): Bitget 0.06% +19.6R; no costs +28.8R; stressed +13.6R; break-even commission 0.191% per side. Fees took 7.5R and funding +0.1R.
- Price path (search window): second by second +21.1R; on 1-minute bars +21.1R; on the chart's candles +21.1R.
- On TradingView (chart candles, 0.06% commission, no funding) the Strategy Tester should show about 284 trades, 54% profitable, profit factor about 1.3, net profit about +10% for 2023-11-01 to 2026-10-31.
- The selection method on this timeframe, search window -> untouched period: the 25 steadiest candidates made +14.7R on average (84% of them made money; positive in 100.0% of resamples of the months): pass. Random groups with the candidates' trade directions (1 of 25 inverted) made -16.1R on average; the candidates beat 95% of such groups, so the choice adds something beyond the direction.
- Not fragile: 100% of 23 neighbouring settings positive in both halves.
- Concentration (search window): 10 biggest trades +7.4R, all others +13.7R; positive in 98.9% of resamples of its weeks.
- Same inputs, other trade direction: -32.6R.

| Input | Shipped | This file |
|---|---|---|
| Slow ATR Period (`slowATRPeriod`) | 100 | 50 |
| Candle Range Period (`candleRangePeriod`) | 20 | 10 |
| Normalization Period (`normalizationPeriod`) | 200 | 400 |
| AATR Weight (`aatrWeight`) | 0.35 | 0.55 |
| VR Weight (`vrWeight`) | 0.25 | 0.15 |
| NSD Weight (`nsdWeight`) | 0.25 | 0.15 |
| High Vol Threshold (`highVolThreshold`) | 60.0 | 70.0 |
| Trade direction (`amviTradeDir`) | "Inverted" | "Follow the filter" |
| Stop Loss (x ATR, 0 = off) (`slMult`) | 1.0 | 8.0 |
| Take Profit (x ATR, 0 = off) (`tpMult`) | 0.0 | 6.0 |
| Time Stop (bars, 0 = off) (`maxBars`) | 0 | 96 |
| Filter timeframe (`fgfTf`) | "60" | "D" |
| Parent obedience timeframe (`fgfParentTf`) | "60" | "D" |
| 1h (`en60`) | true | false |
| 4h (`en240`) | true | false |

| Year | Trades | Net R | Winners | Max DD |
|---|---|---|---|---|
| 2021 (untouched) | 75 | +13.5 | 64% | 1.9 |
| 2022 (untouched) | 75 | +2.5 | 53% | 3.0 |
| 2023 (Jan-Oct, untouched) | 82 | +3.7 | 51% | 7.0 |
| 2023 (Nov-Dec) | 15 | -0.2 | 47% | 1.5 |
| 2024 | 105 | +10.7 | 55% | 3.7 |
| 2025 | 98 | +3.7 | 51% | 3.6 |
| 2026 (Jan-Oct) | 66 | +7.0 | 56% | 2.9 |

| Exit (search window) | Trades | Net R | Average |
|---|---|---|---|
| stop loss | 25 | -25.7 | -1.03 |
| take profit | 93 | +67.2 | +0.72 |
| reversal | 7 | -4.2 | -0.60 |
| time stop | 159 | -16.2 | -0.10 |

### 30m: DO NOT TRADE

DO NOT TRADE because it does not hold up on 2021-2023 (its gain there stays positive in only 77% of resamples of its weeks, so a few good weeks carry it), and none of the four tests passes. No file was written. The inputs below are listed only so that the result can be reproduced; they are not a setup to trade.

- On data it was not chosen on (untouched 2021-01 to 2023-10): 68 trades (35L/33S), +4.8R, PF 1.22, 65% winners, max DD 3.8R, longest losing streak 3, 18 of 34 months positive; stressed costs +3.1R; positive in 77% of resamples of its weeks. 80% of that result came in 2022.
- Where it was chosen (search window): 74 trades (38L/36S), +20.2R, PF 2.22, 76% winners, max DD 3.3R, longest losing streak 2, 23 of 36 months positive; halves +12.3 / +8.0R. The best month (2026-08) made +3.6R of it. In luck-only worlds, where no setting has an edge, a pick chosen the same way still shows about +28R here (95th percentile +103R) and -5R on months it was not chosen on.
- Holding time: 46 hours on average and 15.8 days at most in the search window (2.2 days and 25.2 days on the untouched period): longer than your lab's holding limit (hours to one day).
- With 0.5% of equity at risk per trade and the position capped at 5x equity (the calibrated files' sizing), the search-window result is about +10.1% in three years with a worst drawdown of about 1.7% (no compounding), and the untouched period about +2.4% with a worst drawdown of 1.9%. The stop is 3.83% of price on average, so 0.5% risk asks for about 0.1x leverage.
- Costs (search window): Bitget 0.06% +19.8R; no costs +22.4R; stressed +18.0R; break-even commission 0.510% per side. Fees took 2.2R and funding -0.1R.
- Price path (search window): second by second +20.2R; on 1-minute bars +21.5R; on the chart's candles +21.4R.
- On TradingView (chart candles, 0.06% commission, no funding) the Strategy Tester should show about 72 trades, 75% profitable, profit factor about 2.3, net profit about +10% for 2023-11-01 to 2026-10-31.
- The selection method on this timeframe, search window -> untouched period: the 25 steadiest candidates made +12.1R on average (84% of them made money; positive in 93.2% of resamples of the months): fail. Random groups with the candidates' trade directions (1 of 25 inverted) made -8.6R on average; the candidates beat 95% of such groups, so the choice adds something beyond the direction.
- Not fragile: 100% of 25 neighbouring settings positive in both halves.
- Concentration (search window): 10 biggest trades +12.2R, all others +8.1R; positive in 99.8% of resamples of its weeks.
- Same inputs, other trade direction: -17.2R.
- Trailing stop restarted at every candle close (if TradingView does that): search window +24.0R, untouched +6.7R.

| Input | Shipped | This pick |
|---|---|---|
| Fast ATR Period (`fastATRPeriod`) | 7 | 14 |
| StdDev Period (`stdDevPeriod`) | 20 | 10 |
| Normalization Period (`normalizationPeriod`) | 200 | 100 |
| AATR Weight (`aatrWeight`) | 0.35 | 0.25 |
| ACR Weight (`acrWeight`) | 0.15 | 0.25 |
| High Vol Threshold (`highVolThreshold`) | 60.0 | 50.0 |
| Trade direction (`amviTradeDir`) | "Inverted" | "Follow the filter" |
| Candles to wait after an entry (0 = off) (`amviWait`) | 0 | 20 |
| Stop Loss (x ATR, 0 = off) (`slMult`) | 1.0 | 6.0 |
| Use ATR Trailing Stop (`useTrail`) | false | true |
| Trail Activation (x ATR) (`trailActMul`) | 1.5 | 4.0 |
| Trail Offset (x ATR) (`trailOffMul`) | 1.0 | 1.5 |
| Filter timeframe (`fgfTf`) | "60" | "30" |
| No-trade band, ATR mult (`fgfBandAtr`) | 0.5 | 2.0 |
| 15m (`en15`) | true | false |
| 30m (`en30`) | false | true |

| Year | Trades | Net R | Winners | Max DD |
|---|---|---|---|---|
| 2021 (untouched) | 14 | -1.3 | 57% | 3.3 |
| 2022 (untouched) | 30 | +3.9 | 67% | 3.4 |
| 2023 (Jan-Oct, untouched) | 24 | +2.3 | 67% | 3.8 |
| 2023 (Nov-Dec) | 4 | -0.7 | 50% | 2.1 |
| 2024 | 23 | +9.7 | 87% | 2.0 |
| 2025 | 28 | +7.7 | 75% | 2.1 |
| 2026 (Jan-Oct) | 19 | +3.5 | 68% | 2.7 |

| Exit (search window) | Trades | Net R | Average |
|---|---|---|---|
| stop loss | 15 | -15.4 | -1.03 |
| trailing stop | 56 | +36.8 | +0.66 |
| reversal | 3 | -1.2 | -0.39 |

### 1h: NOT RECOMMENDED

NOT RECOMMENDED because it does not hold up on 2021-2023 (its gain there stays positive in only 86% of resamples of its weeks, so a few good weeks carry it), although the 25 steadiest candidates passed the test there as a group. No file was written. The inputs below are listed only so that the result can be reproduced; they are not a setup to trade.

- On data it was not chosen on (untouched 2021-01 to 2023-10): 98 trades (98L/0S), +7.5R, PF 1.29, 74% winners, max DD 6.0R, longest losing streak 3, 19 of 34 months positive; stressed costs +3.8R; positive in 86% of resamples of its weeks.
- Where it was chosen (search window): 101 trades (101L/0S), +22.0R, PF 2.32, 84% winners, max DD 3.2R, longest losing streak 3, 25 of 36 months positive; halves +11.1 / +10.9R. The best month (2026-08) made +2.2R of it. In luck-only worlds, where no setting has an edge, a pick chosen the same way still shows about +27R here (95th percentile +89R) and -4R on months it was not chosen on.
- Holding time: 13 hours on average and 5.8 days at most in the search window (8 hours and 3.2 days on the untouched period): longer than your lab's holding limit (hours to one day).
- With 0.5% of equity at risk per trade and the position capped at 5x equity (the calibrated files' sizing), the search-window result is about +11.0% in three years with a worst drawdown of about 1.6% (no compounding), and the untouched period about +3.7% with a worst drawdown of 3.0%. The stop is 2.63% of price on average, so 0.5% risk asks for about 0.2x leverage.
- Costs (search window): Bitget 0.06% +21.2R; no costs +26.5R; stressed +17.8R; break-even commission 0.312% per side. Fees took 4.2R and funding +0.3R.
- Price path (search window): second by second +22.0R; on 1-minute bars +22.0R; on the chart's candles +22.0R.
- On TradingView (chart candles, 0.06% commission, no funding) the Strategy Tester should show about 101 trades, 84% profitable, profit factor about 2.3, net profit about +11% for 2023-11-01 to 2026-10-31.
- The selection method on this timeframe, search window -> untouched period: the 25 steadiest candidates made +17.1R on average (92% of them made money; positive in 99.6% of resamples of the months): pass. Random groups of with-the-filter settings made +4.7R on average; the candidates beat 95% of such groups, so the choice adds something beyond the direction.
- Not fragile: 100% of 22 neighbouring settings positive in both halves.
- Concentration (search window): 10 biggest trades +4.7R, all others +17.3R; positive in 100.0% of resamples of its weeks.
- Same inputs, other trade direction: -23.4R.

| Input | Shipped | This pick |
|---|---|---|
| Fast ATR Period (`fastATRPeriod`) | 7 | 10 |
| Slow ATR Period (`slowATRPeriod`) | 100 | 200 |
| StdDev Period (`stdDevPeriod`) | 20 | 10 |
| Candle Range Period (`candleRangePeriod`) | 20 | 30 |
| Normalization Period (`normalizationPeriod`) | 200 | 100 |
| High Vol Threshold (`highVolThreshold`) | 60.0 | 70.0 |
| Trade direction (`amviTradeDir`) | "Inverted" | "Follow the filter" |
| Candles to wait after an entry (0 = off) (`amviWait`) | 0 | 5 |
| Exit ATR Length (`exitAtrLen`) | 14 | 30 |
| Stop Loss (x ATR, 0 = off) (`slMult`) | 1.0 | 4.0 |
| Take Profit (x ATR, 0 = off) (`tpMult`) | 0.0 | 2.0 |
| No-trade band, ATR mult (`fgfBandAtr`) | 0.5 | 2.0 |
| Allow sells (`fgfAllowSell`) | true | false |
| Parent obedience timeframe (`fgfParentTf`) | "60" | "240" |
| TDI RSI length (`fgfRsiLen`) | 14 | 7 |
| 15m (`en15`) | true | false |
| 30m (`en30`) | false | true |
| 4h (`en240`) | true | false |
| 1D (`enD`) | false | true |

| Year | Trades | Net R | Winners | Max DD |
|---|---|---|---|---|
| 2021 (untouched) | 26 | +1.6 | 73% | 2.6 |
| 2022 (untouched) | 38 | +4.2 | 76% | 2.2 |
| 2023 (Jan-Oct, untouched) | 34 | +1.7 | 74% | 6.0 |
| 2023 (Nov-Dec) | 5 | +0.8 | 80% | 1.0 |
| 2024 | 34 | +9.6 | 88% | 1.6 |
| 2025 | 33 | +3.0 | 76% | 3.2 |
| 2026 (Jan-Oct) | 29 | +8.7 | 90% | 1.1 |

| Exit (search window) | Trades | Net R | Average |
|---|---|---|---|
| stop loss | 16 | -16.7 | -1.04 |
| take profit | 85 | +38.7 | +0.46 |

### 4h: USABLE

USABLE because it made money on 2021-2023, which it was not chosen on, at base and stressed costs and in 98% of resamples of its weeks; the 25 steadiest candidates did too as a group; the three hold-out tests inside the last three years fail. File: `presets/AMVI_FGF_BTCUSDT_4h.pine` (test with alerts first; small size at most).

- On data it was not chosen on (untouched 2021-01 to 2023-10): 69 trades (41L/28S), +21.4R, PF 1.71, 58% winners, max DD 8.3R, longest losing streak 6, 19 of 34 months positive; stressed costs +18.9R; positive in 98% of resamples of its weeks. 84% of that result came in 2023.
- Where it was chosen (search window): 100 trades (46L/54S), +35.2R, PF 1.84, 60% winners, max DD 5.7R, longest losing streak 5, 24 of 36 months positive; halves +22.4 / +12.9R. The best month (2025-04) made +5.1R of it. In luck-only worlds, where no setting has an edge, a pick chosen the same way still shows about +24R here (95th percentile +75R) and -3R on months it was not chosen on.
- Holding time: 28 hours on average and 8.4 days at most in the search window (35 hours and 4.9 days on the untouched period): longer than your lab's holding limit (hours to one day).
- With 0.5% of equity at risk per trade and the position capped at 5x equity (the calibrated files' sizing), the search-window result is about +17.6% in three years with a worst drawdown of about 2.8% (no compounding), and the untouched period about +10.7% with a worst drawdown of 4.1%. The stop is 2.33% of price on average, so 0.5% risk asks for about 0.2x leverage.
- Costs (search window): Bitget 0.06% +34.3R; no costs +40.0R; stressed +30.5R; break-even commission 0.422% per side. Fees took 4.7R and funding +0.0R.
- Price path (search window): second by second +35.2R; on 1-minute bars +35.2R; on the chart's candles +32.9R.
- On TradingView (chart candles, 0.06% commission, no funding) the Strategy Tester should show about 100 trades, 59% profitable, profit factor about 1.7, net profit about +16% for 2023-11-01 to 2026-10-31; on plans up to Premium TradingView can replay this file only from about 2024-01-19 (as of 2026-11-26; a day later every day): from then about 94 trades, 61% profitable, net profit about +17%.
- The selection method on this timeframe, search window -> untouched period: the 25 steadiest candidates made +12.5R on average (68% of them made money; positive in 96.6% of resamples of the months): pass. Random groups with the candidates' trade directions (3 of 25 inverted) made +11.9R on average; the candidates do not beat 95% of such groups, so the choice adds nothing measurable beyond the direction.
- Not fragile: 100% of 30 neighbouring settings positive in both halves.
- Concentration (search window): 10 biggest trades +13.2R, all others +22.1R; positive in 99.8% of resamples of its weeks.
- Same inputs, other trade direction: -31.0R.
- This setting reads 15m candles from a 4h chart. TradingView keeps about 100,000 candles of a lower timeframe per request on plans up to Premium (Ultimate is documented with 200,000; not checked), so on those plans its tester can replay it only back to about 2024-01-19 as of 2026-11-26, a day later for every later day (the day you check minus about 1,042 days); earlier trades of this record cannot be checked there.

| Input | Shipped | This file |
|---|---|---|
| Fast ATR Period (`fastATRPeriod`) | 7 | 10 |
| Candle Range Period (`candleRangePeriod`) | 20 | 10 |
| Normalization Period (`normalizationPeriod`) | 200 | 400 |
| AATR Weight (`aatrWeight`) | 0.35 | 0.2 |
| VR Weight (`vrWeight`) | 0.25 | 0.5 |
| NSD Weight (`nsdWeight`) | 0.25 | 0.15 |
| High Vol Threshold (`highVolThreshold`) | 60.0 | 65.0 |
| Trade direction (`amviTradeDir`) | "Inverted" | "Follow the filter" |
| Stop Loss (x ATR, 0 = off) (`slMult`) | 1.0 | 1.5 |
| Take Profit (x ATR, 0 = off) (`tpMult`) | 0.0 | 2.0 |
| Filter timeframe (`fgfTf`) | "60" | "D" |
| Check price on (`fgfCheckIn`) | "Tick" | "Level at candle open" |
| No-trade band, ATR mult (`fgfBandAtr`) | 0.5 | 1.5 |
| Burst threshold, ATR mult (ATR unit) (`fgfBurstAtr`) | 0.5 | 0.25 |
| Require burst gate (`fgfUseBurst`) | false | true |
| Allow any combo (`fgfAnyCombo`) | true | false |
| Prior drift bars (`fgfDriftBars`) | 60 | 120 |
| Use prior drift filter (`fgfUseDrift`) | false | true |
| Parent obedience timeframe (`fgfParentTf`) | "60" | "D" |
| Minimum child zones aligned (`fgfMinAligned`) | 0 | 2 |
| 1h (`en60`) | true | false |
| 4h (`en240`) | true | false |

| Year | Trades | Net R | Winners | Max DD |
|---|---|---|---|---|
| 2021 (untouched) | 28 | +6.1 | 54% | 3.1 |
| 2022 (untouched) | 16 | -2.6 | 38% | 7.0 |
| 2023 (Jan-Oct, untouched) | 25 | +17.9 | 76% | 2.1 |
| 2023 (Nov-Dec) | 4 | +0.4 | 50% | 2.1 |
| 2024 | 33 | +14.5 | 64% | 5.7 |
| 2025 | 31 | +12.0 | 61% | 2.1 |
| 2026 (Jan-Oct) | 32 | +8.3 | 56% | 3.2 |

| Exit (search window) | Trades | Net R | Average |
|---|---|---|---|
| stop loss | 40 | -41.8 | -1.04 |
| take profit | 60 | +77.0 | +1.28 |

## 8. What these numbers do not tell you

1. **Not TradingView.** Every number comes from the Python copy. On all nine picks it matches
   a reference version of the signal side and another of the order side, both written
   independently from the Pine source, and a literal copy of the filter: one independent
   check per part, two for the filter zone (one on the 4h and 5m picks). An independent
   audit also rebuilt the four files' trades from raw data. But it has not been
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
   official statement either way. If it starts the trailing again, the two picks that trail
   change by 1R to 4R, for the better in three of four results (10m: +15.4R instead of
   +14.5R in the search window, +7.8R instead of +8.7R on 2021-2023; 30m: +24.0R instead of
   +20.2R, +6.7R instead of +4.8R). No other trailing setting was run that way, so the
   trailing study of section 5 holds only under my assumption. None of the four files uses
   the trailing stop.
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
| `results/trades_BTCUSDT_<chart>.csv` | every trade of a pick, untouched period and search window (UTC, Binance prices), to compare with TradingView's List of Trades. R columns are rounded to three decimals: one 3m trade (2024-01-08) reads +0.000R and counts as a winner in the 3m block |
| `results/equity_all.png`, `results/direction_and_costs.png` | the two charts of section 1 |
| `results/INPUTS.md`, `results/TRAILING.md` | every input value by value, and every trailing pair, for every chart |
| `results/final_<minutes>m.json` | every number of a pick (4h = 240, 1h = 60) |
| `results/holdout_*.txt`, `plateau_*.txt`, `untouched_check.txt`, `trailing_*.txt`, `luck_*.txt` | the printed output of each step |
| `results/checks/` | the engine against the reference versions, the look-ahead test, the second-by-second walk, data coverage, the output check, and what the tester shows differently (`tester_view.txt`) |
| `results/direction_by_filter.txt` | the two trade directions by filter timeframe (section 6) |
| `tools/` | the Python copy of the script and every step (`README.md` lists them) |

### How to load and check a file on TradingView

1. Open BINANCE:BTCUSDT.P (the data used here) on the file's timeframe, time zone UTC.
2. Paste the file into the Pine Editor and add it to the chart.
3. Change nothing in Settings: no input (the date range below is the one exception), and
   nothing under Properties, where the file already sets 0.06% commission, 1 tick slippage
   and 20% margin. Keep Script executions on "On bar close" only (the tick options off) and
   Bar detalization on its default (the former "Bar Magnifier": off).
4. Compare the Strategy Tester's List of Trades with `results/trades_BTCUSDT_<chart>.csv`,
   trade by trade, up to 2026-10-31 (the list ends there; later trades of the tester are not
   in it). Entry candle and side must agree. Compare trades, not totals. Where to start
   comparing depends on how you run the file:

| File | With Deep Backtesting (Premium plans and above): the tester's period 2023-05-01 to 2026-10-31, and the input "Limit Backtest Date Range" (group "Backtest range") on, 2023-11-01 to 2026-10-31 | On an ordinary chart: 5,000 candles on Basic, 10,000 on Essential and Plus, 20,000 on Premium, 25,000 on Expert, 40,000 on Ultimate |
|---|---|---|
| 15m | every trade from the first | a loose check only: skip the chart's first four weeks, and see below |
| 3m | every trade from the first | not possible: even 40,000 candles reach back only to 2026-09-03 (3 list trades) |
| 1m | every trade from the first (two million 1m candles reach back to 2023-05-01 only until about 2027-02-17) | not possible: 40,000 candles reach back only to 2026-10-29 (no list trade) |
| 4h | from two weeks after the oldest 15m candle the tester has (below) | with 10,000 candles or more: the same; with 5,000, from five months after the chart's first candle |

The oldest 15m candle (4h file). The 4h file's AMVI reads 15m candles, of which TradingView
keeps about 100,000 on plans up to Premium (200,000 on Ultimate, from a web search of its
documentation; not checked). On 26 November the oldest is 2024-01-19 08:00, and it moves a
day later every day: it is the day you check minus about 1,042 days.

Why the start differs. The trade lists were made with years of history before every trade,
and they start flat on 2023-11-01. "Limit Backtest Date Range" only blocks entries outside
its dates; the history comes from the period the tester computes over. With Deep
Backtesting from six months before the range, the script has that history. I simulated it
with my copy, letting every request start on the first day of the period, the cautious case
(`tools/tester_view.py`, log in `results/checks/tester_view.txt`): all trades of the 15m, 3m
and 1m lists then match, and the 4h list does from 3.3 days after its oldest 15m candle. With
the period starting on 2023-11-01 itself, the first 2 to 4 trades of the 15m, 3m and 1m
lists do not match, and on the 4h file the first 6 after its oldest 15m candle (up to 45
days after it).

An ordinary chart starts where its candles start. The AMVI needs history before it has a
value: 418 candles in the 15m file, which normalises over 400 (4.4 days of that chart). The
filter reads daily candles (4h candles in the 3m file), and whether TradingView loads those
from before the chart's first candle I could not check: its site cannot be reached from
here. I simulated both cases, for checks every 12 hours over the five weeks from 26
November and every plan size. If TradingView loads them, every difference on the 15m and 4h
files came within 5.3 days of the start. If it does not, the filter's ATR and RSI start from
other values and keep part of that difference for weeks. On the 15m file differences then
came up to 16.5 days after the chart's first candle with 5,000 candles, 50.2 days with
10,000, 28.2 with 20,000, 23.7 with 25,000 and 24.5 with 40,000. On the 4h file with 5,000
candles they came up to 124 days after it, because its filter compares each daily close with
the close 120 days earlier; with 10,000 4h candles or more the chart starts long before the
oldest 15m candle and nothing changes. Almost every difference is a list trade missing in
the tester; sometimes the tester takes a trade the list does not have; never one on the
other side. So on an ordinary 15m chart a missing or extra trade, even after four weeks, is
no proof of a mismatch; a trade on the other side is.

How many trades that leaves, at 00:00 UTC on 26 November (fewer every week, because the chart
moves on and the list ends on 2026-10-31). The 4h file: 92 list trades from two weeks after
its oldest 15m candle; on a 5,000-candle chart 61 from five months after the chart's first
candle. The 15m file, four weeks skipped: none on 5,000 candles, 12 on 10,000, 31 on 20,000,
44 on 25,000 and 81 on 40,000.

What the tester can show. It shows money, not R: with the file's sizing, net profit in % is
about R x 0.5. On an ordinary chart it covers only the candles your plan loads, up to today:
20,000 candles are 9 years of 4h, 208 days of 15m, 42 days of 3m and 14 days of 1m. For the
full search window use Deep Backtesting with the period and the date range above. The
header of each file says what the tester should then show. The 4h file is the exception: it
can be replayed only from its oldest 15m candle. The untouched period can be checked the same
way on the 15m and 3m files, with the period 2020-07-01 to 2023-10-31 and the date range
2021-01-01 to 2023-10-31: in my simulation all 232 and 72 trades then match (with the period
starting on 2021-01-01, the first 7 and 1 do not). Two million 1m candles reach back only to
early 2023, so the 1m file's untouched period cannot be replayed.

If it differs. An entry on another candle or in the other direction, from the start given in
the table on: do not trade the file, and send me the tester's list. On an ordinary 15m chart
send me the list before deciding, unless a trade is on the other side. Exits: the list gives
the exact second, the tester only the candle. On the 15m, 3m and 1m files every exit should
still be in the same candle and at the same price, because my copy takes the same trades on
chart candles as second by second. On the 4h file one exit is the opposite one: the long
entered 2024-02-28 16:00 is a target in the list (63,098.6, +1.29R) and a stop in the tester
(about 59,426, -1.04R). Both prices lie inside that one 4h candle. The tester knows only the
candle's open, high, low and close and assumes the low came first; second by second the
target came first (17:06, the low at 17:31). That one trade is the whole gap between +35.2R
and +32.9R in the 4h block, and it is not a mismatch. A file that does not load: send me the
error line.

### Rebuild

From public data (about two hours on four cores; 47 GB of downloads, streamed and reduced to
4 GB):

```bash
sh tools/run_all.sh
```
