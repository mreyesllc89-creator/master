ATTACH: components.zip (the EA package) and, if you can, the two live logs SpeedAlertRouter_XAUUSD_scenario_v48_3.csv and SAR_OrderFlowDecision_v2.csv (MetaTrader 5: File > Open Data Folder > MQL5 > Files; a few days are enough, they can be several GB). The session needs internet.

Make the entry direction of my MT5 EA (SpeedAlert FlashGold Micro v1.501, XAUUSD) measurably more accurate, and test it on tick data with a simulated order-flow feed. Folder /home/user/master/flashgold_micro_calibration, branch claude/relaxed-mayer-ysl2wx: commit and push there, no pull request.

Read docs/direction_calibration/PROMPT.md first and follow it: it is the full spec. Then BRIEF.md (verified facts) and PROTOCOL.md (binding acceptance rules) in the same folder.

Scope: calibrate the FlashGold direction filter (my main target), the direction score, the alert size, the continuation filter and the prior-60-minute filter. Frozen, because I tune them by hand: stops, targets, trailing, order types, entry hold, pending expiry, lot size. Use presets/FlashGold_NativeReference_Calibrated_DISABLED.set and report the shipped preset beside it.

What you must know:
- The EA's order-flow feed (five terminal global variables) exists only live. The replay and the Strategy Tester have none. Without it only speed + candle body + micro-break can win, and the market route (74% of my real trades) never fires.
- It cannot be rebuilt from prices (best AUC 0.59). Build a seeded generator of the three imbalance numbers, fitted to my real label tables or, if attached, to my logs. Treat flow as a sensitivity dimension. It is a stand-in, not a copy.
- The shipped direction logic has no measurable skill (gross +0.7 points, standard error 1.2). The calibrated preset's +28 is in-sample, mostly buys, and 96% of its net comes from 5 days of 158. The nine months are burned: accept a change only on untouched periods, as PROTOCOL.md says.
- The FlashGold filter has no flow code: calibrate it first, with flow off.

Deliver: tools/flowsim.py; engine support with golden hashes taken BEFORE any change (start from docs/direction_calibration/prototypes); the MQL5 FlowSim twin for the tester (untested, no MT5 here); tools/run_direction.sh, restartable; calibrated *_DISABLED.set and *_TESTER_OPT.set files; an MT5 checklist.

Rules: one process at a time loads the 7 GB tick data. Keep the 150 ms order delay in searches. Commit no file over 20 MB. Do not stop to ask me questions: take the safe default and note it. "No change" is a valid result.

Messages: first (10 lines): are the zip and the logs there, what they show, your order of work; then continue. Last, in plain English: the outcome first (better, not better, unproven), then what is not verified, then my steps in MT5.
