# Repository guide

TradingView Pine Script v6 trading strategies (FlashGold v5 and XPW Orientation TDI, with
`_FGF` variants carrying the FlashGold direction filter block). Skills under
`.claude/skills/` hold the domain knowledge for Pine, MQL5 (MetaTrader 5), Python trading
research, strategy porting, and shell automation; see `.claude/skills/README.md`.

- Editing a `.pine` file: follow the conventions in
  `.claude/skills/pine-script/references/repo-strategies.md` (header changelog, input groups,
  "STRATEGY ADDITION." tooltips, keep plain and `_FGF` versions in sync).
- Porting a strategy to MQL5 or Python: start with the `strategy-porting` skill; use
  `.claude/skills/mql5/assets/EA_Template.mq5` and
  `.claude/skills/python-trading/scripts/indicators.py`.
- No build or test suite exists for the Pine files; MQL5 cannot be compiled in a Linux
  session, so say so when you cannot verify a compile.
