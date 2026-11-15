# Withdrawn: Loma BTC01 to BTC04

These four BTCUSD presets were calibrated on a BTC price file whose clock was wrong: the file was already in
broker server time and was converted to server time a second time, so every bar was stamped 2 hours (US winter)
or 3 hours (US summer) too late. Their trading hours, end-of-day times and H4/D1 trend filters were therefore
fitted to hours that are 2 to 3 hours away from the broker hours the EA uses, and the shift changes with the
season, so no fixed correction exists.

Do not use them. They are kept only as a record. Their replacement is in `presets/btc/`: the BTC M5 presets of the
re-calibration on a corrected clock (`research/hump_tf_recal.py`, which now checks the clock of every series).

The comment headers of these files, their summary table and the out-of-sample figures quoted for them earlier
(profit factor 1.05 on 193 trades) were computed with the same clock error and should be disregarded.
