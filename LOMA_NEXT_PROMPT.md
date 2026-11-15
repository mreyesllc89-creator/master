# Prompt for the next round: better results from the Loma EA

Copy everything in the box, fill in point 4 if you can, and send it.

Why it is written this way: exits, trailing stops and timeframes have been tested to the end (23 trailing systems, 69,000 setups per timeframe) and they do not create an edge. What can still change the result is more years of data, new entry conditions, and what you see when you trade the method by eye. The prompt asks for those three, under the same honest test.

```
Goal: find a version of my Loma EA (XAUUSD_Loma_TrendPullback.mq5, repo mreyesllc89-creator/master,
branch claude/xauusd-m1-liquidity-ea-va5g23) that keeps a profit factor of 1.3 or more on data it was
never fitted to, on XAUUSD or BTCUSD, at VT Markets costs (gold: 1.5 pips spread plus $0.60 per lot,
1 lot = 1 ounce).

Already tested, do not repeat: every timeframe from M1 to H1 with 23 trailing systems, 69,000 setups
per timeframe (research/hump_tf_recal.py, research/results/recal/, report section 5). Gold: nothing
holds. BTC: M5 passes the 2026 months and loses on 2023 and 2024. Changing exits, trailing or timeframe
is finished. The entry rule and the amount of data are what is left.

Do this, in order:

1. More history. Get gold M1 from 2019 (Dukascopy) and BTC M1 from 2020 (Binance), check the clock of
   every series, and test year by year: calibrate on three years, test on the next year, roll forward.
   A setup counts only if it holds PF 1.3 or more over all the unseen years together, 1.1 or more with
   stressed costs, and is not below 1.0 in any unseen year that has 50 or more trades.

2. New entry conditions, added to the hump signal one at a time, each judged by that same
   year-by-year test:
   - market regime: trade only with the daily or H4 trend; trend strength (ADX or EMA slope);
     volatility level (ATR percentile); skip flat days
   - location: distance from the previous day's high and low, the session's opening range, round
     numbers, the last swing
   - confirmation: the same hump on a higher timeframe; a jump in tick volume; the candle at the signal
   - timing: hour of the day, day of the week, minutes around high-impact news
   - the XLZC signal that is already in this repository, as a second condition

3. Costs. Show the cost per trade in R for every candidate and drop setups whose usual stop is less
   than 8 times the round-trip cost.

4. My own rules. Test these first:
   - I take a Loma trade by eye only when: ______
   - I skip it when: ______
   (I can also send screenshots of good and bad trades.)

5. If gold and BTC both fail, run the same test on EURUSD and US500 and tell me which symbol the
   method fits best.

Rules of evidence: choose on calibration data only; report the unseen years, with stressed costs and
VT costs; run one more check on a period that was never touched; have independent checkers verify the
simulator and every number; tell me plainly if nothing passes. Do not show me in-sample numbers as
results.

Deliver: first a short table of what passed and what failed (PF and trades for each unseen year).
Then, only for what passes: the EA change, the presets, both zips and the GitHub link.
```
