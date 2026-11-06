# Claude Code skills for this repository

Skills load automatically when a task matches their description; nothing to install.
Each folder has a `SKILL.md` (what and when) plus `references/` read on demand.

| Skill | Covers |
|-------|--------|
| `python` | Modern Python engineering: style, typing, pytest, packaging, pandas/numpy, automation scripts |
| `python-trading` | Indicators with Pine/MT5 parity (`scripts/indicators.py`), bar-by-bar backtests, MetaTrader5 Python package |
| `mql5` | MetaTrader 5 EAs, indicators, trade operations, tester, errors; `assets/EA_Template.mq5` |
| `pine-script` | Pine v6 strategy API, repainting, and how the FlashGold / XPW TDI strategies here are built |
| `strategy-porting` | Pine ↔ MQL5 ↔ Python porting workflow with mapping tables and a parity checklist |
| `shell-scripting` | Bash, PowerShell/cmd, cron/Task Scheduler, MetaEditor and tester command-line automation |

Verify the indicator library at any time:

```bash
python3 .claude/skills/python-trading/scripts/indicators.py --selftest
```
