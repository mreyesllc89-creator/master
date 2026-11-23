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

There is no TradingView compiler in this workspace: every file was reviewed against the Pine v6
rules by two independent reviewers, but none was compiled. If TradingView reports an error when
you paste a file, send it over.

### Files at Update 1

| Strategy | File |
|---|---|
| HRD Full Divergence v1.03 | [HRD_Full_Divergence_Strategy_v1_03_FGF.pine](HRD_Full_Divergence_Strategy_v1_03_FGF.pine) |

More files are added to this table as their review finishes.
