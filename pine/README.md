# TokioXAU SinLimites V3 — TradingView port

`TokioXAU_SinLimites_V3.pine` is a Pine Script v6 strategy that reproduces the
MT5 expert advisor in `../mql5/` (`TokioXAU_SinLimites_V3.mq5` + `Core/*.mqh`).
Its defaults are the values of `../mql5/TokioXAU_SinLimites_V3.set`.

## Install

1. TradingView → Pine Editor → paste the file → **Add to chart**.
2. Use XAUUSD, ideally on the **1-minute** chart.
3. Set **"Zona horaria del servidor MT5"** to your broker's server time (MT5 Market Watch clock).

## How it simulates the EA

- **Virtual ledger.** The EA runs buys and sells at the same time (hedging account).
  TradingView strategies cannot, so the script keeps its own book of positions and
  computes the basket P/L in account money (100 oz per lot). The ledger is the
  exact simulation (dashboard and chart); the Strategy Tester mirrors it below.
- **Strategy Tester.** TradingView strategies hold one net position, so the
  strategy keeps the ledger's **net exposure** (buy lots − sell lots, lock included;
  1 lot = 100 oz, see "Cantidad de la estrategia por 1 lote"). A hedged basket gains
  or loses exactly what its net exposure does, so the tester's equity curve follows
  the ledger. Differences: on history the net is adjusted at each bar close (the
  ledger fills inside the bar at the replayed prices), and the tester has no spread
  unless you add slippage/commission in Properties. The tester's "trades" are net
  position changes, not individual grid positions. Starting balance = *Initial
  capital* in Properties (also used for the % of balance rules). Margin is set to
  1% (1:100) so TradingView does not liquidate the simulation.
- **Ticks.** Mode "Cada tick": on live bars the engine runs on every price update,
  like `OnTick`. History has no ticks, so each bar is replayed as a price path
  (optionally from lower-timeframe sub-bars), with synthetic ticks so no grid level
  is skipped. Mode "Al cierre de la vela" runs the same replay once per closed bar.
- **Not simulated:** spread history (an assumed spread is used), margin level
  (`InpMarginMin`, `InpBrkMarginFloor`), recovery by DD%, hedge, compound interest
  and the learning optimizer (all off in the preset), Telegram/DB/CSV.

## Chart markers

| Marker | Meaning |
|---|---|
| green ▲ / pink ▼ | buy / sell opened (seed, grid, refill, trend) |
| label with amount | basket closed (hover for the reason) |
| `$` | scalp of a deep position |
| `x` | bank paid the worst position |
| `L` / `U` | hedge lock on / off |
| `-` | circuit-breaker cut |

## Alerts

Create an alert on the strategy with the condition **"Any alert() function call"**.
Alerts are only sent in real time (never for replayed history).

Text example:

```
TokioXAU_V3 XAUUSD | open buy 0.01 @ 2650.35 | GridBuy N3 #42 | pos 5
```

JSON example (format "JSON", for webhooks / broker bridges):

```json
{"ea":"TokioXAU_V3","symbol":"XAUUSD","event":"open","side":"buy","lot":0.01,
 "price":2650.35,"id":42,"tag":"GridBuy N3","net":0.00,"positions":5,"time":1791100000000}
```

| `event` | Meaning | Bridge action |
|---|---|---|
| `open` | a position was opened (`tag`: Seed, GridBuy N…, GridSell N…, Refill, TrendSeed, TrendAdd, lock) | open `side` `lot`, remember it under `id` |
| `close_one` | one position closed (`tag`: scalp, paydown, breaker_cut, unlock) | close the position stored under `id` |
| `close_all` | the whole basket and any lock closed (`tag` = reason: basket_tp, ratchet_tp, trail_tp, basket_stop_hard, deep_stop, time_cut, weekend_flat, breaker_close, external_close) | close everything for this `ea` |

`net` is the basket result in account money (for `close_one`, that position's result);
`positions` is the number of grid positions left open after the event.

## Live vs. history

Live tick results are kept only while the chart stays loaded. A reload or a settings
change replays that period as history, so the numbers can shift slightly.
