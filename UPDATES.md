# Updates

Each numbered update is marked in the script itself, so versions can't be mixed up:

- the script's title ends with the update number, for example `[Update 1]`;
- the header at the top of the file starts with a block `UPDATE 1 (date)` saying what changed.

A script without a number in its title is older than Update 1.

## Update 1 (2026-11-23): Inverted direction

New option on every strategy that carries the FlashGold Direction Filter:
**"Inverted direction: opposite side at the same entries"**, in the settings group
"Inverted direction (Update 1)". It is off by default, and off means exactly the previous version.

With it on:

- **Entries.** Every entry the strategy would take is placed on the opposite side, on the same
  candle and at the same price. The filter keeps deciding in the normal direction: a buy it
  allows (BUY ZONE) is placed as a sell, a sell it allows (SELL ZONE) as a buy, and an entry it
  blocks stays blocked.
- **Exits.** Stops, targets and trailing keep their distances, mirrored to the new side.
- **Long only / Short only** settings mean the orders really placed.
- **Existing reverse options stay** ("Reverse every label" in XPW, "Reverse Trading" in HRD,
  "Signal direction" in DannyPhantomFX). They flip the signal before the filter; this option
  flips the order after it. Each file's header says how the two differ.

**Three scripts already had this option and get no new setting.** AMVI Full MTF (direction
filter version), its XAUUSD 15m file and the FlashGold Direction Strategy trade the opposite
side through their existing setting "Trade direction: Follow the filter / Inverted". Update 1
changes no order in them: the title carries the number, the header explains the option, and a
few header sentences that were wrong with Inverted are corrected. Leave "Trade direction" as you
had it. The AMVI XAUUSD 15m file is calibrated with Inverted, so Inverted is its tested setting.

**After pasting an update into TradingView:** open the strategy's Settings once and check that
"Inverted direction" is off (it is the last setting, at the bottom of the Inputs tab) and that
your other settings are still as you left them. The new option is declared after every other
setting on purpose, so no existing setting changes its place.

There is no TradingView compiler in this workspace: every file was reviewed against the Pine v6
rules by two independent reviewers, but none was compiled. If TradingView reports an error when
you paste a file, send it over.

### Files at Update 1

| Strategy | File |
|---|---|
| HRD Full Divergence v1.03 | [HRD_Full_Divergence_Strategy_v1_03_FGF.pine](HRD_Full_Divergence_Strategy_v1_03_FGF.pine) |
| ApexForge Flow Resonance | [ApexForge_Flow_Resonance_Strategy_FGF.pine](ApexForge_Flow_Resonance_Strategy_FGF.pine) |
| XPW Orientation TDI v2.8, trailing TP | [xpw_orientation_tdi_v2.8_strategy_trailtp_FGF.pine](xpw_orientation_tdi_v2.8_strategy_trailtp_FGF.pine) |
| FlashGold v5 Strategy (BTCUSD) | [FlashGold_v5_Strategy_BTCUSD_FGF.pine](FlashGold_v5_Strategy_BTCUSD_FGF.pine) |
| GVLiveV2 Pre-Candle | [GVLiveV2_Polymarket_PreCandle_Strategy_FGF.pine](GVLiveV2_Polymarket_PreCandle_Strategy_FGF.pine) and the 9 per-timeframe files in [GVLiveV2_by_timeframe/](GVLiveV2_by_timeframe/) |
| DannyPhantomFX V10.21.1 LiveSafe | [DannyPhantomFX_V10_21_1_LiveSafe_FGF.pine](DannyPhantomFX_V10_21_1_LiveSafe_FGF.pine) and the 7 per-timeframe files in [DannyPhantomFX_by_timeframe/](DannyPhantomFX_by_timeframe/) |
| AMVI Full MTF (already had "Trade direction: Inverted") | [AMVI_Full_MTF_Strategy_FGF.pine](AMVI_Full_MTF_Strategy_FGF.pine) and [AMVI_by_timeframe/AMVI_FGF_XAUUSD_15m.pine](AMVI_by_timeframe/AMVI_FGF_XAUUSD_15m.pine) |
| FlashGold Direction Strategy (already had "Trade direction: Inverted") | [FlashGold_Direction_Strategy.pine](FlashGold_Direction_Strategy.pine) |

More files are added to this table as their review finishes.
