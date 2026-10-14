# VT top-10 scripts: generator, engines and cost-stress runner

Tooling behind `tradingview/vt_top10_scripts/`. Nothing here is needed to use the Pine scripts.

- `gen_scripts.py` assembles each strategy from the verbatim Pine parts (`parts/` lived in the scratchpad: fgf_block + A/B halves of
  each strategy, byte-identical to the pasted sources) and writes one script per row of `stress/top10_per_strategy.csv`
  with the config as input defaults and VT cent-lot costs in `strategy()`.
- `stress_run.py <fg5|sm92|v28>` re-runs the ten configs of one strategy on the VT XAUUSD-ECNc July 2026 tick file
  (`XAUUSD-ECNc_ticks.npz`, not committed: 1.2 GB of ticks) with slippage patched into the engine fill sites and commission
  per side, at seven cost levels. Base level reproduces the screen exactly.
- `engines/` the Python tick-replay engines used for the screen (FlashGold v5, ShapeMap v0.9.2, Orientation v2.8 partial
  ladder) and their grid runners; `ExportBars_VT.mq5` exports MN1/W1/D1/H4/H1 bars from MT5 so v2.8 can be rerun with a
  full ladder.

Cost model: 0.10 cent lot, XAUUSD-ECNc = 1 oz per lot, commission 0.30 USD per lot per side (0.60 round trip), real bid/ask
fills. Results are a four-week screen, not a calibration.
