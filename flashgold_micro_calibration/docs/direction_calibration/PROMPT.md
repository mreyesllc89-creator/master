Calibrate the entry direction of my EA, FlashGold filter first, with a simulated order-flow feed

ATTACH (owner): components.zip (the EA package) and, if possible, two live logs from MetaTrader 5 (File > Open Data Folder > MQL5 > Files): SpeedAlertRouter_XAUUSD_scenario_v48_3.csv and SAR_OrderFlowDecision_v2.csv. A few days are enough; they can be several GB. The session needs internet (huggingface.co, datafeed.dukascopy.com).

GOAL
Make the entry direction of my MetaTrader 5 EA (SpeedAlert FlashGold Micro v1.501, XAUUSD tick scalper) measurably more accurate, and test it on tick data.
In scope: the FlashGold direction filter (my main target), the direction score (speed, M1 candle body, micro-break, spread, order-flow votes), the alert size (MaxTrailingMultiplier sets it, despite its name), the continuation filter and the prior-60-minute filter (InpUsePrior60Filter).
Frozen at presets/FlashGold_NativeReference_Calibrated_DISABLED.set (report the shipped preset as a second column): stops, targets, trailing, order types, entry hold, pending expiry, lot size. I tune them by hand later.
Deliver (A) a simulated order-flow feed (the real one exists only live) with an MQL5 twin for the Strategy Tester, and (B) a fast, rigorous direction-calibration pipeline that I can re-run.

START HERE
Folder /home/user/master/flashgold_micro_calibration, branch claude/relaxed-mayer-ysl2wx. Commit and push there, no pull request, no file over 20 MB; add new data folders to .gitignore first.
Read docs/direction_calibration/PROGRESS.md if it exists, resume from it, and keep it updated (done, next, decisions). Then read REPORT.md, BRIEF.md (verified facts; details in facts/*.json) and PROTOCOL.md (binding acceptance rules), all in docs/direction_calibration/.
Take golden hashes of today's engine BEFORE any change (BRIEF section 4), then apply prototypes/ in a scratch copy as its README says.
Tick data: use data/ticks if it exists; else rebuild it as REPORT.md section 13 says. The direct Dukascopy download is throttled: run it in the background and start with the Hugging Face months. Each extra period gets its own data root (10 study scripts load everything in data/ticks).
Unpack components.zip into a new empty folder, read only; run Python that reads it with -I. pip install what you need (numba, pandas, pyarrow, matplotlib are installed; scipy is not).

FACTS THAT SHAPE THE TASK (BRIEF sections 1 to 5)
1. The live feed is 5 terminal global variables: XPW_XAU_OK, _HEARTBEAT, _FORCE_IMB, _NEAR_IMB, _BOOK_IMB. Each |imbalance| >= 5 is a vote worth +1.0 score; two agreeing votes set the flow direction. Without a feed the score tops out at 4.5 (a winner needs 4.0; the market route needs 5.0 and EntryRouterMode >= 1): only speed + body + micro-break can win, the winning side is always the burst side, and the market route (74% of my real trades) never fires. With a feed, flow creates entries, can flip the side and opens the market route. Live flow numbers change entries only: four exit branches read just the :FA/:FD label and never fired in 2,584 real trades.
2. Entry is first passage over the ticks of an alert window. (Oct 2026, shipped preset) 92.7% of decision ticks have no winner and 74% of those are one correct vote away from winning. So the feed must exist at tick resolution, piecewise constant between updates.
3. The feed cannot be rebuilt from prices: best out-of-sample AUC 0.54 to 0.59 on 1,260 real market entries, and the label does not predict the result (agree minus disagree -9.6 points, 95% range -26 to +7). So build a seeded generator of the three numbers and let the EA's own rules produce labels and routes. It is a stand-in, not a copy.
4. The real numbers exist in my terminal. The first log has force/near/book, flow_fresh, flow_dir and both scores at every decision tick, skips included (time to the second); the second, if my live build writes it, has the heartbeat age (update cadence) in milliseconds. The live trades came from an older build: read the headers. If attached: first measure how well each vote's sign predicts the next 5, 10 and 30 s mid move on ALL logged rows (trading-day bootstrap), then fit scale, cadence, with/against/neutral shares and persistence, and use real triples (the replay model). If not attached, say so in your first message and say what to export.
5. FlashGold is a breakout re-arming gate with no flow code (BRIEF section 2), so calibrate it first, on the neutral replay (flow off). On the calibrated entries the trades it keeps average +31 points gross against +7 for the trades that appear without it. The shipped logic has no measurable skill (gross +0.7 points, standard error 1.2); the calibrated preset's gross edge is +28 (standard error 6), in-sample and mostly on buys.
6. One calibrated trade has an SD of about 200 points, and the best 5 of 158 days make 96% of the calibrated net. The information is in the episodes a candidate changes, clustered by day: PROTOCOL.md.

ORDER OF WORK
0. Housekeeping above; start the background downloads (one earlier year, for example 2022); Gate 0 and the baseline reproduction (PROTOCOL.md section 4).
1. FlashGold filter, flow off. Gate-only inputs (FG_InpBandAtr, FG_InpAgainst, FG_InpLast) re-score exactly from stored state; series inputs (FG_InpBurstAtr, FG_InpEntryDistAtr, timeframes, RSI and fast length, zones, FG_InpMinAligned) need a new filter series (0.1 to 0.3 s per month). Then the four score weights (not explored before) and MinDirectionScore, the alert-size inputs (MaxTrailingMultiplier, MinSpeedAlertPoints, SpeedLookbackSeconds, SpeedAlertHoldSeconds), the body and micro-break definitions, the continuation filter, the prior-60-minute filter.
2. The feed (Part A), in parallel.
3. Re-check the finalists under the flow regimes (PROTOCOL.md section 7).
4. Untouched-period test, stress, independent review, deliver.

PART A: THE FEED
- tools/flowsim.py: FlowSeries(feed, spec) builds the prototype's per-chunk arrays (values quantised to 1/8) from a JSON spec, deterministic from (seed, chunk). Models: neutral; tape (signs follow the last 10 s mid move; with/against/neutral probabilities per component; optional slow regime; outages; update period at least 250 ms, default 1000; publication lag only delays); lead (uses future moves: report only); replay (my logs). Cache in data/cache; at most two series in memory (0.7 GB each at 1 Hz).
- Engine: check each item of the prototype (11 flow inputs, votes, labels, market-route gate, scenario keys, the four label-dependent exits: unit tests only). Neutral flow must stay bit-identical to today's engine.
- Calibrate by simulated method of moments (PROTOCOL.md section 8), then freeze results/direction/flow_spec.json.
- MQL5 twin, tester only: FlowSim.mqh and a ScoreOrderFlow diff (counter hash of seed, time bucket and component; sign from the last 10 s move; bypass the GetTickCount64 age test). Inputs FlowSimMode, FlowSimSeed, FlowSimPWith, FlowSimPAgainst, FlowSimBucketMs, FlowSimPStale. A Python port of its hash must equal flowsim.py; give me 20 test values to compare in MT5. Untested (no MT5 here).

PART B: THE PIPELINE
- The full replay is the primary evaluator (0.3 to 2 s per replay of the nine months). For screening above about 10,000 sets use the prototype's signal-only mode and forward kernel. A decision log (names mirror the live CSV) is for analysis. Anchors and placebos: PROTOCOL.md section 2.
- Unit: the alert episode; weekly chunks; buys and sells scored separately. Metric, gates, multiple testing, untouched periods, stress: PROTOCOL.md sections 1 to 6.
- Ablations: flow on/off, FlashGold on/off, each direction input. Structural changes to the filters only as separate, labelled proposals.

RULES
One process at a time may load the tick data (7 GB each, 16 GB RAM); read the live logs in chunks; follow the tools/run_all.sh pattern with restartable steps; delete results/.done_* after any engine change. Keep the 150 ms order delay in searches (zero-delay searches gave artefacts; 0 and 400 ms are stress cells). Do not stop to ask me questions: take the safe default and note it. "No change" is a valid result.

DELIVER
tools/flowsim.py; the MQL5 FlowSim twin; engine changes with golden-hash self-tests; tools/run_direction.sh (restartable; reruns from the frozen flow spec; writes results/direction/, small csv and json only, and runs make_report.py: add the section to REPORT.template.md and make_report.py, because REPORT.md is generated, and fix sections 12 and 13); calibrated *_DISABLED.set files and *_TESTER_OPT.set ranges around the chosen centre; an MT5 checklist.

MESSAGES
First (10 lines): are components.zip and the logs there, what they show, your order of work; then continue. Last, in plain English: the outcome first (better, not better, or unproven), then what is not verified, then my steps in MT5. Say that the simulated feed is a stand-in, not a copy.

TERMS: FOLM market route; FLXQ stop route; EXHL limit fade; BM/SM buy/sell market; BS/SS buy/sell stop; FA/FD flow agrees/disagrees with the trade.
