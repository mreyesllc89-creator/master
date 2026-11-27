# Calibration of every strategy, with the direction as an input

Every strategy that carries the FlashGold Direction Filter was searched per pair (BTCUSD, XAUUSD) and per timeframe (1m to 4h). The search covered the strategy's own inputs, the filter, and the Update 1 option "Inverted direction" (or the file's own "Trade direction: Inverted"): 2,434,321 backtests in all.

**Result: no strategy has a setting that passes on any timeframe, in either direction.** No per-timeframe file was made from this search.

| Strategy | Results by timeframe and calibration | Backtests | Verdict | Closest cell |
|---|---|---|---|---|
| ApexForge Flow Resonance | [ApexForge_HRD_by_timeframe](ApexForge_HRD_by_timeframe/README.md#calibration-by-timeframe-with-the-direction-as-an-input) | 172,368 | none: BTC 5m (inverted) and BTC 4h passed the rule but were refuted by four independent reviews | BTC 5m inverted |
| HRD Full Divergence v1.03 | [ApexForge_HRD_by_timeframe](ApexForge_HRD_by_timeframe/README.md#calibration-by-timeframe-with-the-direction-as-an-input) | 326,592 | none | BTC 1h |
| XPW v2.8 trailing TP | [XPW_by_timeframe](XPW_by_timeframe/README.md#calibration-by-timeframe-with-the-direction-as-an-input) | 381,024 | none | gold 1h |
| XPW v2.8 S2 / S3 exits | [XPW_by_timeframe](XPW_by_timeframe/README.md#the-other-xpw-file-s2--s3-exits-calibration-by-timeframe-with-the-direction-as-an-input) | 226,800 | none | BTC 4h normal (fails one condition) |
| DannyPhantomFX V10.21.1 | [DannyPhantomFX_by_timeframe](DannyPhantomFX_by_timeframe/README.md#calibration-by-timeframe-on-the-new-data-with-the-direction-as-an-input) | 244,945 | none | BTC 4h |
| FlashGold Direction Strategy | [FlashGold_Direction_Strategy_by_timeframe](FlashGold_Direction_Strategy_by_timeframe/README.md#calibration-by-timeframe-with-the-direction-as-an-input) | 302,400 | none | BTC 4h |
| GVLiveV2 | [GVLiveV2_by_timeframe](GVLiveV2_by_timeframe/README.md#calibration-by-timeframe-on-the-new-data-with-the-direction-as-an-input) | 290,304 | none | BTC 4h normal |
| AMVI Full MTF | [AMVI_by_timeframe](AMVI_by_timeframe/README.md#calibration-by-timeframe-on-the-new-data-with-the-direction-as-an-input) | 266,112 | none; the published gold 15m file also loses on this data | BTC 15m, gold 1h |
| FlashGold v5 (BTCUSD) | [FlashGold_v5_by_timeframe](FlashGold_v5_by_timeframe/README.md#calibration-by-timeframe-with-the-direction-as-an-input) | 223,776 | none | gold 30m normal |

Each page also has the results by timeframe at the file's own defaults, normal against inverted, both as TradingView shows them and with fills checked on 1-minute candles and realistic costs.

## How it was done

- **Data.** BTCUSD: Bitstamp 1-minute candles, 2024-11-17 to 2026-11-17. XAUUSD: Dukascopy 1-minute candles, 2017-01-02 to 2018-06-19. Every timeframe is built from these.
- **Replicas.** TradingView cannot be run here, so each Pine file was rebuilt in Python twice, independently. The two builds were compared trade by trade until they agreed, and then an auditor checked them against the Pine line by line. The code is in [backtest_replicas](backtest_replicas/README.md).
- **Scoring.** Every setting was scored on 1-minute fills with costs (gold $0.30 per ounce per round trip; BTC 0.02% per side + $0.20), on the two halves of the window separately.
- **The rule, fixed before looking.** A setting must be profitable in both halves and sit among good neighbours. The 40 best settings of one half must also hold up on the other half, in both directions. The setting must beat the same setting with the direction flipped, and survive stressed costs. Last, a setting chosen on one half alone must be profitable on the other. The full rule and its independent audit are on the [ApexForge / HRD page](ApexForge_HRD_by_timeframe/README.md#the-rule-rule-c).
- **What a pass would have meant.** With no edge in the data, the rule still passes 2% to 19% of the time per cell. So a pass is only a reason for independent reviewers to attack a setting, never a reason to trade it. The two ApexForge settings that passed were refuted that way.

## What it means

- **The direction is not an edge by itself.** On many cells one direction has far more profitable settings than the other, but which one changes from strategy to strategy and from timeframe to timeframe, and the preference does not carry from one half of the data to the other.
- **The fast charts (1m, 5m) lose almost everywhere** once costs are counted and exits are checked on 1-minute candles.
- **TradingView's own report can be far more flattering** than the 1-minute view, above all for strategies with stops or trails smaller than a candle (XPW trailing TP, FlashGold v5 on BTC).
- **Limits.** The windows are short (2 years of BTC, 18 months of gold), the gold data is old, and each strategy has readings of TradingView's engine that cannot be checked here; each page lists its own. Nothing was compiled or run in TradingView.
