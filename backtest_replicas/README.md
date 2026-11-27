# Backtest replicas (the code behind the results in this repository)

TradingView cannot be run from here, so every result in the `*_by_timeframe` folders comes from Python replicas of the Pine files. This folder keeps that code so the results can be reproduced and extended. It holds code and notes only, no market data.

**What is here**

| File | What it is |
|---|---|
| `fgf.py` | The FlashGold Direction Filter (buy / sell permission per candle) |
| `xpw.py`, `engine.py`, `sweep_core.py`, `run_tf.py` | XPW Orientation TDI v2.8 (trailing TP): signals, orders, fast sweeps, money model |
| `apex.py` | ApexForge Flow Resonance + filter |
| `hrd.py` | HRD Full Divergence v1.03 + filter |
| `xpw23.py` | XPW Orientation TDI v2.8 with the S2 / S3 exits (signals from `xpw.py`) |
| `danny.py` | Danny Phantom FX V10.21.1 LiveSafe + filter |
| `gvl.py` | GVLiveV2 Polymarket Pre-Candle + filter |
| `fgds.py` | FlashGold Direction Strategy (trades the filter's own zones and signals) |
| `amvi.py` | AMVI Full MTF Strategy + filter (and the unfused original's direction) |
| `run_*.py`, `run_inv_*.py` | Results by timeframe, normal and inverted direction |
| `sweep*.py` | The trailing sweeps |
| `calib_*.py` | The calibration grids and the selection rule (`calib_analyze.py`) |
| `*_tests.py`, `inv_tests_*.py`, `verify_*.py`, `mag_ref.py` | Tests and independent references each replica was checked against |
| `SPEC*.md`, `*_SPEC.md` | The briefs the replicas were built from |
| `reconcile_*.md`, `inv_*_notes.md` | How two independent builds were compared, and every interpretation of the Pine |

**How each replica was checked.** Two builds written independently from the Pine, compared trade by trade until they agree, then an audit against the Pine line by line. Fills are modelled two ways: TradingView's own bar path, and 1-minute fills (Bar Magnifier).

**Data (not included).** BTCUSD: Bitstamp 1-minute candles with volume. XAUUSD: Dukascopy ticks aggregated to 1-minute candles (`fetch_gold.sh`, `ticks_to_1m.py`). `build_bars.py` and `build_vol.py` build every timeframe from the 1-minute files into `data/`.

**To run it elsewhere.** A few files (`xpw.py`, `run_tf.py`, `build_bars.py`, `build_vol.py`, `fetch_gold.sh`) carry the folder path of the session they were written in; point it at your own folder. Python 3 with numpy, pandas, numba, pyarrow.

Nothing here was compiled or run in TradingView.
