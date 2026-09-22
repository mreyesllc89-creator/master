# XPChart — XP ChartEngine v2 (plumbing)

Start with `XP_CHARTENGINE_REPORT.md` (line 1 = verdict; §11 = run order). `P0_REPORT.md` is the pre-edit diagnosis of v1.

| File | What |
|---|---|
| `XP ChartEngine.mq5` | v1, as supplied, unchanged (last known good) |
| `XP ChartEngine v2.mq5` | v2.01 service: CopyTicks cursor, tick-anchored bars, spec sync, restart-safe, heartbeat, August-scheme lock, UpdateRatesEveryTick |
| `XP_RECONCILE_REPORT.md` | v1.1 reconcile against the host census: capability table, lock decision, per-terminal deploy plan |
| `XP ChartEngine.aug-5FFA5.mq5` / `XP ChartEngine.mar-73B7.mq5` | host copies from the census (reference, unchanged) |
| `census/2026-09-22/` | host census outputs |
| `XP_AxisCheck.mq5` | read-only Gate 1 script: which time axis an existing `*_S1` custom symbol really holds |
| `tools/XP_Census.ps1` | read-only census of the Windows trees and MT5 installs (hashes, divergences, deployment map, compilers) |
| `tools/XP_Compile.ps1` | compile with `metaeditor64.exe /compile` |
| `tools/XP_LineageSweep.ps1` | grep both trees for the v1 patterns |

Hard rules honoured: running terminals are read-only, no tick backfill, nothing broker-specific hardcoded, the agent never attaches v2 to a live terminal.
