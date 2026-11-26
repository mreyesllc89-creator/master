#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ref_orders.py -- independent REFERENCE of the ORDER side of the TradingView Pine Script v6 strategy
AMVI_FGF_Inverted_XAUUSD_15m.pine, written for differential testing against another implementation.

Sources: ONLY the Pine file (its strategy() declaration, the "Trade direction", "Closed-candle engine"
and "Strategy - Exits" inputs, and the code between the "STRATEGY ENGINE" and "PLOTS" banners) and the
Pine Script v6 reference definitions of the built-ins.  No other implementation was read.  Python 3
standard library + numpy only (no numba): numpy for whole-array maths, plain loops where state is
carried from bar to bar.

Public functions
    reference_trades(m1, chart_tf, trig, zone, volc, p, fee, slip_ticks, i_start=0, i_end=None)
    build_bars(m1, tf)                      chart bars of tf minutes built from the 1-minute bars
    pine_true_range(h, l, c)                ta.tr(true)
    pine_rma(src, length)                   ta.rma
    pine_atr(h, l, c, length)               ta.atr
    pine_round(x)                           math.round
Module constants: MINTICK (0.1), TIE_EPS (float guard, decision D17; set it to 0.0 for literal float
comparisons).

====================================================================================================
1. RULES GIVEN FOR THIS REFERENCE
====================================================================================================
Market and data
  * 24/7 crypto perpetual, syminfo.mintick = 0.1.
  * m1 is a dict of numpy arrays of ONE-MINUTE bars: 't' (int64, bar OPEN time in ms since the epoch,
    strictly increasing; missing minutes are tolerated), 'o', 'h', 'l', 'c' (float64).
  * Higher timeframes are built as TradingView does for a 24/7 symbol: a bar of T minutes (T divides
    1440; 1440 is the Pine timeframe "D") opens at every multiple of T minutes since the epoch,
    contains the 1-minute bars whose open time lies in [open, open + T), has open = first,
    high = max, low = min, close = last, and does not exist when no 1-minute bar falls inside it.
Execution model
  * Properties -> Script executions = "On bar close" only: the script runs once per chart bar, at its
    close, with barstate.isconfirmed and barstate.ishistory true.  amviCcDups stays 0, so amviCcBad
    is false and amviDecide is true on every bar.  inRange is true on every bar.
Pine built-ins (reference definitions)
  * ta.sma: na until the window is full.  ta.rma(src, n): na until n values exist, then the SMA of
    the first full window, then alpha * src + (1 - alpha) * rma[1] with alpha = 1 / n.
    ta.tr(true) = max(high - low, |high - close[1]|, |low - close[1]|), and high - low on the first
    bar.  ta.atr(n) = ta.rma(ta.tr(true), n).  math.round: nearest integer, ties rounded up.
    Any comparison with na is false.
  * ta.stdev (population), ta.highest / ta.lowest (na until full), ta.rsi, ta.crossover(a, b) =
    a > b and a[1] <= b[1], ta.crossunder(a, b) = a < b and a[1] >= b[1], and request.security
    (for a context bar with open time t and timeframe C and a requested timeframe R -- R > C with
    lookahead_on and [1]: the requested bar BEFORE the one containing t; R > C with lookahead_off:
    the last requested bar whose close time <= the context bar's close time; R == C: the context's
    own bar; R < C with lookahead_off: the last requested bar inside the context bar; none yet: na)
    belong to the SIGNAL side.  The order side never evaluates them: the script's `trigger`, the
    filter direction (amviDirUp / amviDirDn) and `volCollapse` are INPUT arrays that hold the values
    these expressions have at each chart bar's close.  The only indicator computed here is the exit
    ATR, ta.atr(exitAtrLen) on the chart timeframe.
Inputs taken from the dict p
    inverted (amviTradeDir == "Inverted"), sl (slMult), tp (tpMult), trail (useTrail),
    trail_act (trailActMul), trail_off (trailOffMul), vol_exit (useVolExit), max_bars (maxBars),
    wait (amviWait), exit_atr (exitAtrLen).
Quantity
  * s3Qty is taken as > 0 whenever the stop distance slMult * atrX is a positive number, and as 0
    otherwise (sl == 0, or the ATR still na): then the entry is skipped and the script's
    "Reverse (qty 0)" branch applies.  Everything is reported per unit of quantity.

====================================================================================================
2. BROKER EMULATOR CONVENTIONS (given, implemented as stated)
====================================================================================================
  1. A market order created at the close of bar N (strategy.entry, strategy.close,
     strategy.close_all) fills at the OPEN of bar N+1.  Slippage = slip_ticks x mintick against the
     trader on market fills and on stop / trailing-stop fills (a buy fills higher, a sell lower);
     none on limit (take-profit) fills.
  2. strategy.entry against an open position closes it and opens the new one in the same fill
     (pyramiding = 0); both legs fill at the same price.
  3. The exit bracket (strategy.exit: stop, limit, trail_points, trail_offset) is live from the
     moment the entry fills; the script re-issues it at every bar close while a position is open.
  4. Inside a chart bar, price is replayed on the 1-minute bars it contains, in order.  A 1-minute
     bar is walked as four ticks: open, the extreme NEARER to the open, the other extreme, close
     (if high - open < open - low the high comes first, otherwise the low).  Price moves
     continuously between consecutive ticks and jumps from one bar's close to the next bar's open.
  5. A stop (fixed or trailing) fills when price reaches or passes it: at the stop price when
     reached inside a move, at the tick price when price is already at or beyond it on a 1-minute
     bar's open tick (a gap).  A limit fills at the limit price when reached inside a move, at the
     open tick price when the bar opens at or beyond it.  On the open tick the stop is tested
     before the limit.
  6. Trailing stop: trail_points / trail_offset are ticks, as the script computes them.  It
     activates when price reaches entry price +/- trail_points x mintick in the favourable
     direction (entry price = actual average fill price).  From then on a stop sits
     trail_offset x mintick behind the best price reached since activation (best price updated at
     every tick of the walk; at activation it is the price of the tick, or of the end of the move,
     that carried price through the activation level) and only moves favourably.  The fixed stop
     stays in force: the exit happens at whichever stop is closer to price.  An active trailing
     stop is not reset when the bracket is re-issued.
  7. Commission: fee = fraction per side of the fill value, on the entry and on the exit fill.
     Net profit per unit = dir x (exit_px - entry_px) - fee x (entry_px + exit_px).
  8. A position still open after the last bar is closed at the last chart bar's close, without
     slippage, why = "end".
  9. Order of events in a chart bar: (a) fills at the open of the orders created at the previous
     close: first the closing of an existing position (a close or an opposite entry is pending),
     then the new entry; (b) the walk of the 1-minute bars with the bracket of whatever position
     is open (one opened at this very open included); (c) the script's execution at the close.
  why values: "stop", "tp", "trail", "reverse" (closed by an opposite entry or by the
  "Reverse (qty 0)" close), "vol", "time", "end".

====================================================================================================
3. WHAT THE SCRIPT DOES AT EACH CLOSE (read from the Pine code, in its own order)
====================================================================================================
    amviWaitOk = amviWait == 0 or na(amviLastEntryBar) or bar_index - amviLastEntryBar > amviWait
    longSig    = amviWaitOk and trigger and (inverted ? amviDirDn : amviDirUp)
    shortSig   = amviWaitOk and trigger and (inverted ? amviDirUp : amviDirDn)
    goLong     = longSig  and strategy.position_size <= 0
    goShort    = shortSig and strategy.position_size >= 0
    enterLong  = goLong  and s3Qty > 0            enterShort = goShort and s3Qty > 0
    if enterLong / enterShort:  entryAtr := atrX; amviLastEntryBar := bar_index; strategy.entry(...)
    if goLong  and not enterLong  and position_size < 0:  strategy.close("Short", "Reverse (qty 0)")
    if goShort and not enterShort and position_size > 0:  strategy.close("Long",  "Reverse (qty 0)")
    trailPts = useTrail and not na(entryAtr) ? max(1, round(entryAtr * trailActMul / mintick)) : na
    trailOff = useTrail and not na(entryAtr) ? max(1, round(entryAtr * trailOffMul / mintick)) : na
    hasBracket = slMult > 0 or tpMult > 0 or useTrail
    if hasBracket and (position_size > 0 or enterLong):
        ep = position_size > 0 ? strategy.position_avg_price : close
        strategy.exit("L-Exit", "Long", stop = slMult > 0 ? ep - entryAtr * slMult : na,
                      limit = tpMult > 0 ? ep + entryAtr * tpMult : na, trail_points, trail_offset)
    if hasBracket and (position_size < 0 or enterShort):   (mirror image, "S-Exit" / "Short")
    if useVolExit and position_size != 0 and volCollapse:               strategy.close_all("Vol Collapse")
    if maxBars > 0 and strategy.opentrades > 0
       and bar_index - strategy.opentrades.entry_bar_index(0) >= maxBars: strategy.close_all("Time Stop")

====================================================================================================
4. MODELLING DECISIONS
====================================================================================================
 D1  Chart bar time.  A chart bar's open time is the multiple of T minutes that starts it, also when
     its first 1-minute bars are missing; entry_t and the exit_t of fills at a bar's open use it.
     The bar's open PRICE is the open of its first existing 1-minute bar.
 D2  Exit ATR.  ta.atr(exit_atr) is computed over ALL chart bars built from m1, from the very first
     one, whatever i_start is; it is na on the first exit_atr - 1 chart bars.
 D3  Window.  Only chart bars i_start .. i_end-1 are simulated.  At i_start the strategy is flat,
     entryAtr = na, amviLastEntryBar = na and nothing is pending.  The first decision is taken at
     the close of bar i_start, so the first fill can only happen at the open of bar i_start + 1.
     Orders created at the close of bar i_end-1 never fill.  A position still open then is closed
     at close[i_end-1], no slippage, why "end", exit_t = open time of that chart bar.
 D4  Quantity.  s3Qty > 0 exactly when slMult * atrX > 0 (false for na and for 0).  So sl == 0
     never trades.  When the quantity is 0 neither entryAtr nor amviLastEntryBar is touched, and an
     opposite position is closed at the next open by "Reverse (qty 0)" (why "reverse").  (A position
     needs sl > 0 and an existing ATR, and the ATR never becomes na again, so in practice this
     branch cannot fire; it is implemented because the script has it.)
 D5  Position seen by the script.  strategy.position_size / strategy.opentrades at a close are the
     position left after ALL fills of that bar (fills at its open and bracket fills inside it).  A
     position stopped out inside a bar is therefore flat for that bar's decisions.
 D6  Wait rule.  amviLastEntryBar is the bar_index of the SIGNAL bar of the last entry order that
     was actually sent (not the fill bar, not a qty-0 signal).  A trigger on bar k is accepted when
     wait == 0, or no entry was sent yet, or k - amviLastEntryBar > wait.  The rule gates entries,
     reversals and the "Reverse (qty 0)" close; it gates neither the vol-collapse exit nor the
     time stop.  bar_index counts the chart bars that exist (a missing chart bar is not counted),
     here and in the time stop; only differences of bar_index are used.
 D7  Direction.  zone +1 (amviDirUp) = long when following, short when inverted; zone -1 the other
     way round; zone 0 = nothing.  goLong needs a flat or short position, goShort a flat or long
     one: a trigger in the direction of the open position does nothing at all (no re-entry,
     entryAtr and the wait counter unchanged).
 D8  entryAtr.  It is a `var`, overwritten with the signal bar's ATR on every accepted entry signal,
     reversal signals included, BEFORE the bracket lines run.  The new position's stop, target,
     trailing ticks and risk therefore use the ATR of its own signal bar.  On a reversal signal bar
     the script also re-issues the bracket of the position that is about to be closed with the NEW
     ATR; this is reproduced, but it can never fill: the reversal closes that position at the next
     open, before any price walk (convention 9a).
 D9  Bracket reference price.  On the signal bar the position does not exist, so ep = close of the
     signal bar: during the whole FILL bar the stop is signal close -/+ entryAtr * sl and the target
     is signal close +/- entryAtr * tp, whatever the fill price was.  From the close of the fill bar
     on, ep = strategy.position_avg_price = the actual fill price (slippage included): the stop and
     the target hang from the fill price and stay constant until the exit.  When price is already
     beyond a re-issued level, the order fills on the next 1-minute bar's open tick (convention 5).
D10  Trailing ticks.  trail_points = max(1, round_half_up(entryAtr * trailActMul / mintick)),
     trail_offset = max(1, round_half_up(entryAtr * trailOffMul / mintick)); both na (no trailing)
     when useTrail is off.  The activation level is the actual fill price +/- trail_points * mintick
     from the fill on (the fill bar included), never the signal close.
D11  Tick walk.  On an open tick: the stops are tested (with the trailing stop as it stood before
     the tick), then the limit, then the trailing stop activates / the best price is updated.
     The open tick of the fill bar's first 1-minute bar is the entry tick itself: the bracket is
     already tested there, so a fill bar that opens beyond the stop (or the target) of the signal
     close exits on the entry tick, at the tick price.
     In a move against the position only the stops can fill.  In a favourable move the limit is
     tested first (a target inside the move fills even when the trailing activation level also lies
     inside it), then the trailing stop activates or the best price is updated with the END price
     of the move.  A move of zero length does nothing.  A move's direction is taken from its two end
     prices; the bars are not repaired (h >= max(o, c) and l <= min(o, c) are assumed).
D12  Stop label.  With an active trailing stop the effective stop is the one closer to price, also
     for a gap fill; why = "trail" only when the trailing stop is STRICTLY closer than the fixed
     stop, otherwise "stop".
D13  Time stop.  At the close of bar k: a position is open and k - F >= maxBars, where F is the index
     of the chart bar whose open filled the entry -> close_all -> exit at the open of bar k + 1.
     The first close that qualifies is the one of bar F + maxBars, so the time stop closes a
     position filled at the open of bar F at the open of bar F + maxBars + 1 (it lives maxBars + 1
     full bars), unless something else closes it before.  Not gated by the wait rule.
D14  Vol-collapse exit.  At the close of bar k: a position is open (after that bar's fills; the fill
     bar itself counts) and volc[k] -> close_all -> exit at the open of bar k + 1.  A volCollapse
     on the signal bar of an entry from flat does nothing (no position yet).
D15  Several market orders created on the same bar all fill at the next open, at the same price.
     They are handled in the order the script created them: strategy.entry (lines 979 / 983),
     strategy.close "Reverse (qty 0)" (985 / 987), close_all "Vol Collapse" (1018), close_all
     "Time Stop" (1022).  Hence:
       - opposite entry + vol-collapse and / or time stop on the same bar: the entry closes the old
         position (why "reverse") and opens the new one; the close_all order was created for the
         old position, finds nothing left of it and does NOT close the new position;
       - "Reverse (qty 0)" + close_all on the same bar: why "reverse";
       - vol-collapse + time stop on the same bar, no opposite entry: both calls address the same
         order ("Close position order"), the later call replaces the earlier: why "time".
D16  No tick rounding of prices.  Stop / limit levels, and fills at them, are used exactly as the
     script computes them (floats, generally off the tick grid); only trail_points / trail_offset
     and the slippage are whole ticks.
D17  Float guard.  "Price has reached a level" is tested with a tolerance TIE_EPS = 1e-7 (a
     millionth of a tick): on a 0.1 price grid an exact touch of a trailing level is common, and
     literal float arithmetic misses some of them (100.1 - 7 * 0.1 = 99.39999999999999 < 99.4).
     The same guard is used for "high - open < open - low" (100.6 - 100.4 < 100.4 - 100.2 in
     floats, although both are 0.2): mathematically equal distances walk the low first.  Levels
     and fill prices themselves are NOT snapped; they keep their float value.  Set
     ref_orders.TIE_EPS = 0.0 to get literal float comparisons.
D18  Slippage.  slip = slip_ticks * mintick.  Market fills: open + dir * slip for an entry, open -
     dir * slip for the close of a position of direction dir (so both legs of a reversal share one
     price).  Stop / trailing fills: stop price (or the gap tick price) - dir * slip.  Target
     fills (also on an open tick): no slippage.
D19  Output.  One dict per closed trade, in closing order, with exactly the keys entry_t, exit_t,
     dir, entry_px, exit_px, risk, r, why.  risk = entryAtr * sl with the ATR of the trade's own
     signal bar; r = (dir * (exit_px - entry_px) - fee * (entry_px + exit_px)) / risk.
"""

import math
import time

import numpy as np

__all__ = ['reference_trades', 'build_bars', 'pine_true_range', 'pine_rma', 'pine_atr', 'pine_round',
           'MINTICK', 'TIE_EPS']

MINTICK = 0.1            # syminfo.mintick
TIE_EPS = 1e-7           # float guard of decision D17 (0.0 = literal float comparisons)
_MS_PER_MIN = 60000
_WHY = ('stop', 'tp', 'trail', 'reverse', 'vol', 'time', 'end')
_KEYS = ('entry_t', 'exit_t', 'dir', 'entry_px', 'exit_px', 'risk', 'r', 'why')


# ====================================================================================================
# Bars and Pine built-ins
# ====================================================================================================
def build_bars(m1, tf):
    """Chart bars of `tf` minutes built from the 1-minute bars `m1`.

    Returns a dict of arrays with one entry per existing chart bar: 't' (open time = multiple of tf
    minutes, ms), 'o', 'h', 'l', 'c', and the half-open range ['first', 'end') of the indices of the
    1-minute bars the chart bar contains."""
    tf = int(tf)
    if tf < 1:
        raise ValueError('the timeframe must be a positive number of minutes')
    t = np.asarray(m1['t'], dtype=np.int64)
    o = np.asarray(m1['o'], dtype=np.float64)
    h = np.asarray(m1['h'], dtype=np.float64)
    l = np.asarray(m1['l'], dtype=np.float64)
    c = np.asarray(m1['c'], dtype=np.float64)
    n = t.size
    if not (o.size == h.size == l.size == c.size == n):
        raise ValueError('the m1 arrays must have the same length')
    if n == 0:
        ei = np.zeros(0, dtype=np.int64)
        ef = np.zeros(0, dtype=np.float64)
        return {'t': ei, 'o': ef, 'h': ef, 'l': ef, 'c': ef, 'first': ei, 'end': ei}
    if n > 1 and not bool(np.all(t[1:] > t[:-1])):
        raise ValueError("m1['t'] must be strictly increasing")
    span = tf * _MS_PER_MIN
    bucket = t // span                                   # which tf-minute interval each minute is in
    first = np.flatnonzero(np.concatenate(([True], bucket[1:] != bucket[:-1])))
    end = np.concatenate((first[1:], [n]))
    return {
        't': bucket[first] * span,
        'o': o[first],
        'h': np.maximum.reduceat(h, first),
        'l': np.minimum.reduceat(l, first),
        'c': c[end - 1],
        'first': first,
        'end': end,
    }


def pine_true_range(h, l, c):
    """ta.tr(true): max(high - low, |high - close[1]|, |low - close[1]|); high - low on the first bar."""
    h = np.asarray(h, dtype=np.float64)
    l = np.asarray(l, dtype=np.float64)
    c = np.asarray(c, dtype=np.float64)
    tr = h - l
    if tr.size > 1:
        pc = c[:-1]
        tr[1:] = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - pc), np.abs(l[1:] - pc)))
    return tr


def pine_rma(src, length):
    """ta.rma(src, length) for a source without na: na on the first length - 1 bars, the SMA of the
    first full window on bar length - 1, then alpha * src + (1 - alpha) * rma[1], alpha = 1 / length."""
    length = int(length)
    if length < 1:
        raise ValueError('length must be >= 1')
    x = np.asarray(src, dtype=np.float64).tolist()
    n = len(x)
    out = np.full(n, np.nan)
    if n < length:
        return out
    alpha = 1.0 / length
    prev = math.fsum(x[:length]) / length               # ta.sma of the first full window
    vals = [prev]
    for v in x[length:]:
        prev = alpha * v + (1.0 - alpha) * prev
        vals.append(prev)
    out[length - 1:] = vals
    return out


def pine_atr(h, l, c, length):
    """ta.atr(length) = ta.rma(ta.tr(true), length)."""
    return pine_rma(pine_true_range(h, l, c), length)


def pine_round(x):
    """math.round(x): the nearest integer, ties rounded up."""
    return int(math.floor(x + 0.5))


# ====================================================================================================
# An open position and its exit bracket
# ====================================================================================================
class _Position(object):
    """One open position, per unit of quantity, with the bracket strategy.exit placed for it.

    The price walk works with direction-adjusted prices q = d * price, so that for a long (d = +1)
    and for a short (d = -1) alike a HIGHER q is the favourable side: a stop is reached when q falls
    to d * stop, a limit when q rises to d * limit.  Negation is exact in floating point, so this is
    the same arithmetic as two mirrored copies of the code."""

    __slots__ = ('d', 'entry_px', 'entry_t', 'entry_bar', 'risk',
                 'stop', 'limit', 'pts', 'off', 'q_act', 'trail_on', 'best_q')

    def __init__(self, d, entry_px, entry_t, entry_bar, risk):
        self.d = d                      # +1 long, -1 short
        self.entry_px = entry_px        # strategy.position_avg_price: the fill price, slippage included
        self.entry_t = entry_t          # open time of the chart bar whose open filled the entry
        self.entry_bar = entry_bar      # strategy.opentrades.entry_bar_index(0)
        self.risk = risk                # entryAtr * slMult of the trade's own signal bar
        self.stop = None                # fixed stop price, None = na
        self.limit = None               # take-profit price, None = na
        self.pts = None                 # trail_points (ticks), None = na
        self.off = None                 # trail_offset (ticks), None = na
        self.q_act = None               # direction-adjusted trailing activation level
        self.trail_on = False           # the trailing stop has been activated
        self.best_q = None              # direction-adjusted best price since the activation

    def set_bracket(self, stop, limit, pts, off):
        """strategy.exit(stop=, limit=, trail_points=, trail_offset=): place or re-issue the bracket.
        An already active trailing stop (trail_on, best_q) is kept (convention 6)."""
        self.stop = stop
        self.limit = limit
        self.pts = pts
        self.off = off
        if pts is None or off is None:
            self.q_act = None
            self.trail_on = False
        else:
            # entry price +/- trail_points x mintick in the favourable direction
            self.q_act = self.d * self.entry_px + pts * MINTICK

    def _stop_q(self):
        """(direction-adjusted price, why) of the stop that is closer to price, or (None, None)."""
        q = None
        why = None
        if self.stop is not None:
            q = self.d * self.stop
            why = 'stop'
        if self.trail_on:
            tq = self.best_q - self.off * MINTICK       # trail_offset x mintick behind the best price
            if q is None or tq > q:                     # strictly closer to price than the fixed stop
                q = tq
                why = 'trail'
        return q, why

    def _trail_update(self, q):
        """Activate the trailing stop, or record a new best price, at direction-adjusted price q."""
        if self.q_act is None:
            return
        if not self.trail_on:
            if q >= self.q_act - TIE_EPS:
                self.trail_on = True
                self.best_q = q
        elif q > self.best_q:
            self.best_q = q

    def open_tick(self, px, slip):
        """The open tick of a 1-minute bar (price may have jumped).  Returns (exit_px, why) or None."""
        d = self.d
        q = d * px
        sq, why = self._stop_q()
        if sq is not None and q <= sq + TIE_EPS:        # already at or beyond the stop: gap fill
            return px - d * slip, why
        if self.limit is not None and q >= d * self.limit - TIE_EPS:
            return px, 'tp'                             # opens at or beyond the limit: tick price
        self._trail_update(q)
        return None

    def move(self, a, b, slip):
        """A continuous move of price from tick a to tick b.  Returns (exit_px, why) or None."""
        d = self.d
        qa = d * a
        qb = d * b
        if qb < qa:                                     # against the position: only stops can fill
            sq, why = self._stop_q()
            if sq is not None and qb <= sq + TIE_EPS:
                return d * sq - d * slip, why           # at the stop price, slippage against
        elif qb > qa:                                   # favourable: limit, then the trailing stop
            if self.limit is not None and qb >= d * self.limit - TIE_EPS:
                return self.limit, 'tp'                 # at the limit price, no slippage
            self._trail_update(qb)
        return None

    def walk_minute(self, o, h, l, c, slip):
        """Walk one 1-minute bar: open, the extreme nearer to the open, the other extreme, close."""
        hit = self.open_tick(o, slip)
        if hit is not None:
            return hit
        if (h - o) < (o - l) - TIE_EPS:                 # the high is nearer to the open
            x1, x2 = h, l
        else:                                           # otherwise the low comes first
            x1, x2 = l, h
        hit = self.move(o, x1, slip)
        if hit is None:
            hit = self.move(x1, x2, slip)
            if hit is None:
                hit = self.move(x2, c, slip)
        return hit


# ====================================================================================================
# The reference
# ====================================================================================================
def reference_trades(m1, chart_tf, trig, zone, volc, p, fee, slip_ticks, i_start=0, i_end=None):
    """trig / zone / volc: arrays with one entry per chart bar of timeframe chart_tf built from m1
    (bool, int8 in {-1, 0, +1}, bool): the script's `trigger`, the filter direction
    (+1 = amviDirUp, -1 = amviDirDn, 0 = neither) and `volCollapse` at each bar's close.
    Script executions (decisions) happen at the close of chart bars i_start .. i_end-1; fills can
    happen from bar i_start on. Returns a list of dicts, one per closed trade, in order:
    entry_t (ms, open time of the chart bar whose open filled the entry), exit_t (ms: open time of the
    chart bar for a fill at its open, or open time of the 1-minute bar inside which a stop / target /
    trailing stop filled), dir (+1 / -1), entry_px, exit_px, risk (price distance = Stop Loss multiple x
    the entry ATR), r (net profit of the trade divided by risk, per unit of quantity), why (string).

    p: dict with inverted, sl, tp, trail, trail_act, trail_off, vol_exit, max_bars, wait, exit_atr.
    fee: commission per side as a fraction of the fill value.  slip_ticks: slippage in ticks.
    See the module docstring for the rules, the broker conventions and the modelling decisions."""
    bars = build_bars(m1, chart_tf)
    nb = int(bars['t'].size)
    trig = np.asarray(trig)
    zone = np.asarray(zone)
    volc = np.asarray(volc)
    if trig.shape != (nb,) or zone.shape != (nb,) or volc.shape != (nb,):
        raise ValueError('trig / zone / volc must have one entry per chart bar (%d bars of %s min); got '
                         '%s / %s / %s' % (nb, chart_tf, trig.shape, zone.shape, volc.shape))
    i_start = int(i_start)
    if i_start < 0:
        raise ValueError('i_start must be >= 0')
    i_end = nb if i_end is None else min(int(i_end), nb)

    # ---- inputs of the script --------------------------------------------------------------------
    inverted = bool(p['inverted'])             # amviTradeDir == "Inverted"
    sl = float(p['sl'])                        # slMult
    tp = float(p['tp'])                        # tpMult
    use_trail = bool(p['trail'])               # useTrail
    trail_act_mul = float(p['trail_act'])      # trailActMul
    trail_off_mul = float(p['trail_off'])      # trailOffMul
    use_vol_exit = bool(p['vol_exit'])         # useVolExit
    max_bars = int(p['max_bars'])              # maxBars
    wait = int(p['wait'])                      # amviWait
    exit_atr = int(p['exit_atr'])              # exitAtrLen

    # ---- series as plain Python lists (floats / ints / bools) for the bar-by-bar loops -------------
    atr = pine_atr(bars['h'], bars['l'], bars['c'], exit_atr).tolist()   # atrX, nan = na
    ct = bars['t'].tolist()
    co = bars['o'].tolist()
    cc = bars['c'].tolist()
    first = bars['first'].tolist()
    end = bars['end'].tolist()
    mt = np.asarray(m1['t'], dtype=np.int64).tolist()
    mo = np.asarray(m1['o'], dtype=np.float64).tolist()
    mh = np.asarray(m1['h'], dtype=np.float64).tolist()
    ml = np.asarray(m1['l'], dtype=np.float64).tolist()
    mc = np.asarray(m1['c'], dtype=np.float64).tolist()
    trig_l = trig.astype(bool).tolist()
    zone_l = zone.astype(np.int64).tolist()
    volc_l = volc.astype(bool).tolist()

    fee = float(fee)
    slip = float(slip_ticks) * MINTICK                   # slippage as a price distance
    has_bracket = sl > 0 or tp > 0 or use_trail          # bool hasBracket
    trades = []

    def book(pos, exit_t, exit_px, why):
        net = pos.d * (exit_px - pos.entry_px) - fee * (pos.entry_px + exit_px)
        trades.append({'entry_t': int(pos.entry_t), 'exit_t': int(exit_t), 'dir': int(pos.d),
                       'entry_px': float(pos.entry_px), 'exit_px': float(exit_px),
                       'risk': float(pos.risk), 'r': float(net / pos.risk), 'why': why})

    # ---- state -----------------------------------------------------------------------------------
    entry_atr = math.nan          # var float entryAtr = na
    last_entry_bar = None         # var int amviLastEntryBar = na
    pos = None                    # the open position (strategy.position_size != 0) or None
    pend_entry = None             # entry order created at the previous close, with its bracket
    pend_close = None             # why of the market order that closes the open position at the open

    for i in range(i_start, i_end):
        # ==========================================================================================
        # (a) fills at the open of bar i of the market orders created at the close of bar i - 1:
        #     first the closing of the existing position, then the new entry (same price)
        # ==========================================================================================
        bar_open = co[i]
        if pos is not None and pend_close is not None:
            book(pos, ct[i], bar_open - pos.d * slip, pend_close)
            pos = None
        if pend_entry is not None:
            assert pos is None                           # an entry order always meets a flat book here
            d = pend_entry['d']
            pos = _Position(d, bar_open + d * slip, ct[i], i, pend_entry['risk'])
            pos.set_bracket(pend_entry['stop'], pend_entry['limit'], pend_entry['pts'], pend_entry['off'])
        pend_entry = None
        pend_close = None

        # ==========================================================================================
        # (b) the walk of the 1-minute bars of chart bar i with the bracket of the open position
        # ==========================================================================================
        if pos is not None:
            for j in range(first[i], end[i]):
                hit = pos.walk_minute(mo[j], mh[j], ml[j], mc[j], slip)
                if hit is not None:
                    book(pos, mt[j], hit[0], hit[1])
                    pos = None
                    break

        # ==========================================================================================
        # (c) the script's execution at the close of bar i (Pine statements in their own order)
        # ==========================================================================================
        size = 0 if pos is None else pos.d               # sign of strategy.position_size
        close_i = cc[i]
        atr_x = atr[i]                                   # float atrX = ta.atr(exitAtrLen)

        # amviWaitOk = amviWait == 0 or na(amviLastEntryBar) or bar_index - amviLastEntryBar > amviWait
        wait_ok = wait == 0 or last_entry_bar is None or i - last_entry_bar > wait
        trigger = trig_l[i]
        dir_up = zone_l[i] > 0                           # amviDirUp
        dir_dn = zone_l[i] < 0                           # amviDirDn
        long_sig = wait_ok and trigger and (dir_dn if inverted else dir_up)
        short_sig = wait_ok and trigger and (dir_up if inverted else dir_dn)
        go_long = long_sig and size <= 0
        go_short = short_sig and size >= 0

        qty_ok = (sl * atr_x) > 0.0                      # s3Qty > 0; False while the ATR is na
        enter_long = go_long and qty_ok
        enter_short = go_short and qty_ok

        if enter_long:
            entry_atr = atr_x                            # entryAtr := atrX
            last_entry_bar = i                           # amviLastEntryBar := bar_index
            pend_entry = {'d': 1, 'risk': entry_atr * sl, 'stop': None, 'limit': None, 'pts': None, 'off': None}
        if enter_short:
            entry_atr = atr_x
            last_entry_bar = i
            pend_entry = {'d': -1, 'risk': entry_atr * sl, 'stop': None, 'limit': None, 'pts': None, 'off': None}
        # strategy.close(<opposite id>, comment="Reverse (qty 0)")
        reverse_qty0 = (go_long and not enter_long and size < 0) or (go_short and not enter_short and size > 0)

        # trailPts / trailOff (ticks), from the entryAtr just updated
        if use_trail and not math.isnan(entry_atr):
            trail_pts = max(1, pine_round(entry_atr * trail_act_mul / MINTICK))
            trail_off = max(1, pine_round(entry_atr * trail_off_mul / MINTICK))
        else:
            trail_pts = None
            trail_off = None

        if has_bracket and (size > 0 or enter_long):
            ep = pos.entry_px if size > 0 else close_i   # strategy.position_avg_price : close
            long_sl = ep - entry_atr * sl if sl > 0 else None
            long_tp = ep + entry_atr * tp if tp > 0 else None
            if size > 0:                                 # strategy.exit("L-Exit", "Long", ...): re-issue
                pos.set_bracket(long_sl, long_tp, trail_pts, trail_off)
            else:                                        # ... or the bracket of the pending "Long" entry
                pend_entry.update(stop=long_sl, limit=long_tp, pts=trail_pts, off=trail_off)

        if has_bracket and (size < 0 or enter_short):
            ep = pos.entry_px if size < 0 else close_i
            short_sl = ep + entry_atr * sl if sl > 0 else None
            short_tp = ep - entry_atr * tp if tp > 0 else None
            if size < 0:                                 # strategy.exit("S-Exit", "Short", ...): re-issue
                pos.set_bracket(short_sl, short_tp, trail_pts, trail_off)
            else:
                pend_entry.update(stop=short_sl, limit=short_tp, pts=trail_pts, off=trail_off)

        # if useVolExit and strategy.position_size != 0 and volCollapse -> close_all("Vol Collapse")
        vol_close = use_vol_exit and size != 0 and volc_l[i]
        # if maxBars > 0 and strategy.opentrades > 0
        #    and bar_index - strategy.opentrades.entry_bar_index(0) >= maxBars -> close_all("Time Stop")
        time_close = max_bars > 0 and size != 0 and i - pos.entry_bar >= max_bars

        # Which of these orders closes the open position at the next open (decision D15):
        # the orders are handled in the order the script created them.
        if size != 0:
            if pend_entry is not None:                   # opposite strategy.entry: reversal
                pend_close = 'reverse'
            elif reverse_qty0:                           # strategy.close "Reverse (qty 0)"
                pend_close = 'reverse'
            elif time_close:                             # the later close_all replaces the earlier
                pend_close = 'time'
            elif vol_close:
                pend_close = 'vol'

    # ---- convention 8: a position still open after the last bar ------------------------------------
    if pos is not None:
        last = i_end - 1
        book(pos, ct[last], cc[last], 'end')
    return trades


# ====================================================================================================
# Self-test
# ====================================================================================================
_T0 = 1750032000000          # 2025-06-16 00:00:00 UTC: a multiple of one day, hence of every timeframe
_BASE = dict(inverted=False, sl=1.0, tp=0.0, trail=False, trail_act=1.5, trail_off=1.0,
             vol_exit=False, max_bars=0, wait=0, exit_atr=1)
_P = (100.0, 101.0, 99.0, 100.0)       # warm-up bar: true range 2
_CALM = (100.0, 100.5, 99.5, 100.0)    # a bar that touches nothing: true range 1


def _m1_from_rows(rows, minutes=None):
    a = np.asarray(rows, dtype=np.float64)
    k = np.arange(len(rows), dtype=np.int64) if minutes is None else np.asarray(minutes, dtype=np.int64)
    return {'t': _T0 + _MS_PER_MIN * k, 'o': a[:, 0].copy(), 'h': a[:, 1].copy(),
            'l': a[:, 2].copy(), 'c': a[:, 3].copy()}


def _case(name, rows, sig, expected, tf=1, minutes=None, volc_at=(), fee=0.001, slip_ticks=1,
          i_start=0, i_end=None, **params):
    """One hand-computed scenario.  sig: {chart bar: zone} (trigger true there); expected: tuples
    (entry minute, exit minute, dir, entry_px, exit_px, risk, why), minutes counted from _T0."""
    m1 = _m1_from_rows(rows, minutes)
    nb = int(build_bars(m1, tf)['t'].size)
    trig = np.zeros(nb, dtype=bool)
    zone = np.zeros(nb, dtype=np.int8)
    volc = np.zeros(nb, dtype=bool)
    for i, z in sig.items():
        trig[i] = True
        zone[i] = z
    for i in volc_at:
        volc[i] = True
    p = dict(_BASE)
    p.update(params)
    got = reference_trades(m1, tf, trig, zone, volc, p, fee, slip_ticks, i_start, i_end)
    ok = len(got) == len(expected)
    if ok:
        for g, e in zip(got, expected):
            net = e[2] * (e[4] - e[3]) - fee * (e[3] + e[4])
            ok = (ok and tuple(g.keys()) == _KEYS
                  and g['entry_t'] == _T0 + _MS_PER_MIN * e[0] and g['exit_t'] == _T0 + _MS_PER_MIN * e[1]
                  and g['dir'] == e[2] and abs(g['entry_px'] - e[3]) < 1e-9 and abs(g['exit_px'] - e[4]) < 1e-9
                  and abs(g['risk'] - e[5]) < 1e-9 and abs(g['r'] - net / e[5]) < 1e-9 and g['why'] == e[6])
    if not ok:
        raise AssertionError('scenario %r failed\n  expected %r\n  got      %r' % (name, expected, got))
    return 1


def _unit_scenarios():
    """Small hand-computed cases: chart bars of 1 minute and exit_atr = 1 (ATR = the bar's true range),
    signal on bar 1 (ATR 2, close 100), fee 0.001, slippage 1 tick, unless stated otherwise."""
    n = 0
    L = {1: 1}                                       # trigger on bar 1 in the BUY zone -> long (not inverted)
    # ---- fixed stop: reference price on the fill bar and afterwards ------------------------------
    n += _case('stop hangs from the fill price after the fill bar',
               [_P, _P, (100.5, 101, 99.5, 100), (100, 100.2, 98.5, 99), (99, 99.5, 98.8, 99.2)], L,
               [(2, 3, 1, 100.6, 98.5, 2.0, 'stop')])
    n += _case('stop hangs from the signal close on the fill bar',
               [_P, _P, (100.5, 101, 97.9, 100), _CALM], L,
               [(2, 2, 1, 100.6, 97.9, 2.0, 'stop')])
    n += _case('fill bar opens beyond the stop: gap fill on the entry tick',
               [_P, _P, (97.5, 98, 97, 97.8), _CALM], L,
               [(2, 2, 1, 97.6, 97.4, 2.0, 'stop')])
    n += _case('re-issued stop already passed: fills on the next 1-minute open',
               [_P, _P, (103, 103.5, 99, 99.5), (99.6, 100, 99.2, 99.9), _CALM], L,
               [(2, 3, 1, 103.1, 99.5, 2.0, 'stop')])
    n += _case('inverted: BUY zone goes short',
               [_P, _P, (99.5, 100.5, 99, 100), (100, 101.5, 99.8, 101.2), _CALM], L,
               [(2, 3, -1, 99.4, 101.5, 2.0, 'stop')], inverted=True)
    # ---- target ----------------------------------------------------------------------------------
    n += _case('target hangs from the signal close on the fill bar',
               [_P, _P, (100.5, 103.2, 100.4, 103.1), _CALM], L,
               [(2, 2, 1, 100.6, 103.0, 2.0, 'tp')], tp=1.5)
    n += _case('fill bar opens beyond the target: open tick price, no slippage',
               [_P, _P, (103.5, 104, 103.2, 103.8), _CALM], L,
               [(2, 2, 1, 103.6, 103.5, 2.0, 'tp')], tp=1.5)
    n += _case('target hangs from the fill price after the fill bar',
               [_P, _P, (100.5, 102.9, 100.4, 102.8), (102.8, 103.4, 102.7, 103.2),
                (103.2, 103.7, 103.1, 103.5), _CALM], L,
               [(2, 4, 1, 100.6, 103.6, 2.0, 'tp')], tp=1.5)
    # ---- trailing stop: 20 ticks to activate, 10 ticks behind --------------------------------------
    tr = dict(trail=True, trail_act=1.0, trail_off=0.5)
    head = [_P, _P, (100.5, 101, 100.2, 100.8), (100.8, 103.0, 100.7, 102.9), (102.9, 104.0, 102.8, 103.5)]
    n += _case('trailing stop: activation, ratchet, exit',
               head + [(103.4, 103.6, 102.5, 102.7), _CALM], L,
               [(2, 5, 1, 100.6, 102.9, 2.0, 'trail')], **tr)
    n += _case('trailing stop: low first, the old stop is hit before the new high',
               head + [(103.4, 104.5, 102.9, 104.2), _CALM], L,
               [(2, 5, 1, 100.6, 102.9, 2.0, 'trail')], **tr)
    n += _case('trailing stop: high first, it ratchets and is hit inside the same minute',
               head + [(103.4, 104.6, 102.0, 103.0), _CALM], L,
               [(2, 5, 1, 100.6, 103.5, 2.0, 'trail')], **tr)
    n += _case('trailing stop: gap through it',
               head + [(102.4, 102.6, 102.0, 102.2), _CALM], L,
               [(2, 5, 1, 100.6, 102.3, 2.0, 'trail')], **tr)
    n += _case('trailing stop active but the fixed stop is closer',
               [_P, _P, (100.5, 101.8, 100.4, 101.7), (101.7, 101.9, 98.0, 98.2), _CALM], L,
               [(2, 3, 1, 100.6, 98.5, 2.0, 'stop')], trail=True, trail_act=0.5, trail_off=3.0)
    n += _case('float guard: exact touch of a trailing stop (100.1 - 7 ticks = 99.4)',
               [_P, _P, (99.0, 99.3, 98.9, 99.2), (99.2, 100.1, 99.1, 100.0), (100.0, 100.0, 99.4, 99.8),
                (99.8, 101.0, 99.7, 100.9)], L,
               [(2, 4, 1, 99.1, 99.3, 2.0, 'trail')], trail=True, trail_act=0.5, trail_off=0.35)
    n += _case('float guard: equal distances to high and low walk the low first',
               [_P, _P, (100.0, 100.1, 99.9, 100.0), (100.0, 100.5, 99.9, 100.4), (100.4, 100.6, 100.2, 100.5),
                _CALM], L,
               [(2, 4, 1, 100.1, 100.2, 2.0, 'trail')], trail=True, trail_act=0.15, trail_off=0.1)
    # ---- reversal, wait rule, time stop, vol-collapse ----------------------------------------------
    n += _case('reversal: both legs at the same price, new ATR for the new position',
               [_P, _P, (100.5, 101, 99.5, 100), (100.2, 100.4, 99.8, 100.0), (100.0, 101.7, 99.9, 101.0), _CALM],
               {1: 1, 2: -1},
               [(2, 3, 1, 100.6, 100.1, 2.0, 'reverse'), (3, 4, -1, 100.1, 101.7, 1.5, 'stop')])
    calm8 = [_P, _P] + [_CALM] * 6
    rev = {1: 1, 2: -1, 3: -1, 4: -1}
    n += _case('wait 0: the next candle may reverse', calm8, rev,
               [(2, 3, 1, 100.1, 99.9, 2.0, 'reverse'), (3, 7, -1, 99.9, 100.0, 1.0, 'end')])
    n += _case('wait 1', calm8, rev,
               [(2, 4, 1, 100.1, 99.9, 2.0, 'reverse'), (4, 7, -1, 99.9, 100.0, 1.0, 'end')], wait=1)
    n += _case('wait 2', calm8, rev,
               [(2, 5, 1, 100.1, 99.9, 2.0, 'reverse'), (5, 7, -1, 99.9, 100.0, 1.0, 'end')], wait=2)
    tstop = [_P, _P, _CALM, _CALM, _CALM, (100.3, 100.6, 100, 100.4), _CALM]
    n += _case('time stop 2: decided at the close of fill bar + 2', tstop, L,
               [(2, 5, 1, 100.1, 100.2, 2.0, 'time')], max_bars=2)
    n += _case('vol-collapse on the fill bar; ignored on the signal bar (flat)',
               [_P, _P, _CALM, (100.3, 100.6, 100, 100.4), _CALM], L,
               [(2, 3, 1, 100.1, 100.2, 2.0, 'vol')], vol_exit=True, volc_at=(1, 2))
    n += _case('opposite entry and vol-collapse on the same bar: reverse, new position kept',
               [_P, _P, _CALM, _CALM, _CALM], {1: 1, 2: -1},
               [(2, 3, 1, 100.1, 99.9, 2.0, 'reverse'), (3, 4, -1, 99.9, 100.0, 1.0, 'end')],
               vol_exit=True, volc_at=(2,))
    n += _case('opposite entry and time stop on the same bar: reverse, new position kept',
               [_P, _P, _CALM, _CALM, _CALM, _CALM], {1: 1, 3: -1},
               [(2, 4, 1, 100.1, 99.9, 2.0, 'reverse'), (4, 5, -1, 99.9, 100.0, 1.0, 'end')], max_bars=1)
    n += _case('vol-collapse and time stop on the same bar: time',
               [_P, _P, _CALM, _CALM, _CALM, _CALM], L,
               [(2, 4, 1, 100.1, 99.9, 2.0, 'time')], vol_exit=True, volc_at=(3,), max_bars=1)
    # ---- quantity 0, window, end -------------------------------------------------------------------
    n += _case('ATR still na on the first trigger: no entry; the next trigger enters',
               [_P, _P, _CALM, _CALM, _CALM], {1: 1, 2: 1},
               [(3, 4, 1, 100.1, 100.0, 5.0 / 3.0, 'end')], exit_atr=3)
    n += _case('quantity 0 against an open position (ATR 0): "Reverse (qty 0)" closes it, nothing opens',
               [_P, _P, _CALM, (100, 100, 100, 100), (100.2, 100.6, 100, 100.4), _CALM], {1: 1, 3: -1},
               [(2, 4, 1, 100.1, 100.1, 2.0, 'reverse')])
    n += _case('stop loss 0: no quantity, no trade', [_P, _P, _CALM, _CALM], L, [], sl=0.0, tp=2.0, trail=True)
    n += _case('no direction: no trade', [_P, _P, _CALM, _CALM], {1: 0}, [])
    n += _case('i_end: open position closed at the close of bar i_end - 1',
               [_P, _P, (100.5, 101, 99.5, 100), (100, 100.2, 98.5, 99), (99, 99.5, 98.8, 99.2)], L,
               [(2, 2, 1, 100.6, 100.0, 2.0, 'end')], i_end=3)
    n += _case('i_start: a trigger before the window is not seen',
               [_P, _P, (100.5, 101, 99.5, 100), (100, 100.2, 98.5, 99), (99, 99.5, 98.8, 99.2)], L, [], i_start=2)
    n += _case('an order created at the last close never fills', [_P, _P], L, [])
    # ---- chart bars of 5 minutes, first minute of the fill bar missing ------------------------------
    rows5 = [_P] * 10 + [(100.5, 100.8, 100.2, 100.6), (100.6, 100.7, 97.5, 98.2), (98.2, 98.5, 98.0, 98.3),
                         (98.3, 98.6, 98.1, 98.4)] + [(98.4, 98.6, 98.2, 98.4)] * 5
    mins5 = list(range(10)) + [11, 12, 13, 14] + list(range(15, 20))
    n += _case('5-minute chart: entry_t is the bar time, exit_t the minute of the fill',
               rows5, L, [(10, 12, 1, 100.6, 97.9, 2.0, 'stop')], tf=5, minutes=mins5)
    return n


def _unit_builtins():
    """build_bars and pine_atr against naive loops."""
    rng = np.random.default_rng(3)
    n = 3000
    keep = rng.random(n) > 0.2
    keep[400:460] = False
    t = (_T0 + _MS_PER_MIN * np.arange(n, dtype=np.int64))[keep]
    c = 500.0 + np.cumsum(rng.normal(0.0, 1.0, size=n))[keep]
    o = c + rng.normal(0.0, 0.5, size=c.size)
    h = np.maximum(o, c) + rng.random(c.size)
    l = np.minimum(o, c) - rng.random(c.size)
    m1 = {'t': t, 'o': o, 'h': h, 'l': l, 'c': c}
    for tf in (1, 5, 15, 60, 240, 1440):
        b = build_bars(m1, tf)
        groups = {}
        for k in range(t.size):
            groups.setdefault(int(t[k]) // (tf * _MS_PER_MIN), []).append(k)
        keys = sorted(groups)
        assert b['t'].tolist() == [k * tf * _MS_PER_MIN for k in keys]
        for idx, k in enumerate(keys):
            g = groups[k]
            assert b['first'][idx] == g[0] and b['end'][idx] == g[-1] + 1
            assert b['o'][idx] == o[g[0]] and b['c'][idx] == c[g[-1]]
            assert b['h'][idx] == max(h[j] for j in g) and b['l'][idx] == min(l[j] for j in g)
        # ta.atr the slow way
        for length in (1, 3, 14):
            got = pine_atr(b['h'], b['l'], b['c'], length)
            prev = None
            trs = []
            for i in range(b['t'].size):
                hl = b['h'][i] - b['l'][i]
                tr_i = hl if i == 0 else max(hl, abs(b['h'][i] - b['c'][i - 1]), abs(b['l'][i] - b['c'][i - 1]))
                trs.append(tr_i)
                if i < length - 1:
                    assert math.isnan(got[i])
                    continue
                prev = sum(trs) / length if i == length - 1 else (tr_i + (length - 1) * prev) / length
                assert abs(got[i] - prev) <= 1e-9 * max(1.0, abs(prev))
    assert [pine_round(x) for x in (0.4, 0.5, 1.5, 2.5, 2.49, 7.0)] == [0, 1, 2, 3, 2, 7]
    return 1


def _synthetic_m1(n=20000, seed=20261126):
    """Exactly n one-minute bars of a seeded random walk on the 0.1 tick grid, with a few opening
    jumps and a few missing minutes (the bars are strictly increasing in time but not gap-free)."""
    rng = np.random.default_rng(seed)
    raw = n + n // 50 + 50                             # minutes generated before some are removed
    t = _T0 + _MS_PER_MIN * np.arange(raw, dtype=np.int64)
    c = 30000.0 + np.cumsum(rng.normal(0.0, 12.0, size=raw))
    jump = np.where(rng.random(raw) < 0.05, rng.normal(0.0, 8.0, size=raw), 0.0)
    o = np.empty(raw)
    o[0] = 30000.0
    o[1:] = c[:-1] + jump[1:]
    h = np.maximum(o, c) + np.abs(rng.normal(0.0, 6.0, size=raw))
    l = np.minimum(o, c) - np.abs(rng.normal(0.0, 6.0, size=raw))
    o, h, l, c = (np.round(x * 10.0) / 10.0 for x in (o, h, l, c))
    h = np.maximum(h, np.maximum(o, c))
    l = np.minimum(l, np.minimum(o, c))
    keep = rng.random(raw) >= 0.003                    # isolated missing minutes
    keep[5000:5013] = False                            # a hole that swallows whole 5-minute bars
    idx = np.flatnonzero(keep)[:n]
    assert idx.size == n
    return {'t': t[idx], 'o': o[idx], 'h': h[idx], 'l': l[idx], 'c': c[idx]}


def _check_trades(trades, m1, tf, trig, zone, p, fee, slip_ticks):
    """Structural checks of a result on arbitrary data."""
    bars = build_bars(m1, tf)
    bt = bars['t']
    slip = slip_ticks * MINTICK
    tol = 1e-6
    prev_exit = None
    for k, tr in enumerate(trades):
        assert tuple(tr.keys()) == _KEYS, tr
        assert tr['why'] in _WHY and tr['dir'] in (1, -1) and tr['risk'] > 0
        assert tr['exit_t'] >= tr['entry_t']
        assert prev_exit is None or tr['entry_t'] >= prev_exit
        prev_exit = tr['exit_t']
        net = tr['dir'] * (tr['exit_px'] - tr['entry_px']) - fee * (tr['entry_px'] + tr['exit_px'])
        assert abs(tr['r'] - net / tr['risk']) < 1e-12
        # the entry fills at the open of a chart bar that follows an accepted trigger
        i = int(np.searchsorted(bt, tr['entry_t']))
        assert bt[i] == tr['entry_t'] and i >= 1
        assert abs(tr['entry_px'] - (bars['o'][i] + tr['dir'] * slip)) < tol
        assert bool(trig[i - 1]) and int(zone[i - 1]) == (-tr['dir'] if p['inverted'] else tr['dir'])
        why = tr['why']
        if why in ('reverse', 'vol', 'time'):
            e = int(np.searchsorted(bt, tr['exit_t']))
            assert bt[e] == tr['exit_t'] and e > i
            assert abs(tr['exit_px'] - (bars['o'][e] - tr['dir'] * slip)) < tol
            if why == 'time':
                assert e - 1 - i >= p['max_bars'] > 0
        elif why == 'end':
            assert k == len(trades) - 1 and tr['exit_t'] == bt[-1] and tr['exit_px'] == bars['c'][-1]
        else:
            j = int(np.searchsorted(m1['t'], tr['exit_t']))
            assert m1['t'][j] == tr['exit_t']
            lo, hi = m1['l'][j], m1['h'][j]
            if why == 'tp':
                assert p['tp'] > 0 and lo - tol <= tr['exit_px'] <= hi + tol
            else:
                assert lo - tol <= tr['exit_px'] + tr['dir'] * slip <= hi + tol
                assert why != 'trail' or p['trail']
        assert why != 'vol' or p['vol_exit']
    for a, b in zip(trades, trades[1:]):               # a reversal hands over at one price and time
        if a['why'] == 'reverse' and b['entry_t'] == a['exit_t']:
            assert b['dir'] == -a['dir'] and abs(b['entry_px'] - a['exit_px']) < tol


def _self_test():
    t_begin = time.perf_counter()
    print('unit scenarios (hand-computed): %d passed' % _unit_scenarios())
    _unit_builtins()
    print('build_bars / ta.atr against naive loops: passed')

    chart_tf = 5
    m1 = _synthetic_m1(20000)
    bars = build_bars(m1, chart_tf)
    nb = int(bars['t'].size)
    rng = np.random.default_rng(7)
    trig = rng.random(nb) < 0.03
    zone = rng.choice(np.array([-1, 0, 1], dtype=np.int8), size=nb, p=[0.4, 0.2, 0.4])
    volc = rng.random(nb) < 0.02
    print('synthetic walk: %d one-minute bars -> %d chart bars of %d min, %d triggers (%.1f %%), '
          '%d with a direction' % (m1['t'].size, nb, chart_tf, int(trig.sum()), 100.0 * trig.mean(),
                                   int((trig & (zone != 0)).sum())))
    base = dict(inverted=True, sl=1.0, tp=0.0, trail=False, trail_act=1.5, trail_off=1.0,
                vol_exit=False, max_bars=0, wait=0, exit_atr=14)
    sets = [
        ('calibrated: inverted, sl 1', {}),
        ('follow the filter, sl 1', dict(inverted=False)),
        ('tp 2', dict(tp=2.0)),
        ('trailing 1.5 / 1.0', dict(trail=True)),
        ('trailing 0.5 / 0.3, sl 2', dict(trail=True, trail_act=0.5, trail_off=0.3, sl=2.0)),
        ('trailing + tp 3 + vol exit', dict(trail=True, tp=3.0, vol_exit=True)),
        ('max_bars 12', dict(max_bars=12)),
        ('wait 30', dict(wait=30)),
        ('all: trail, tp 2.5, vol, max_bars 20, wait 5', dict(trail=True, trail_act=1.0, trail_off=0.5, tp=2.5,
                                                             vol_exit=True, max_bars=20, wait=5, exit_atr=7)),
        ('sl 0 (no quantity)', dict(sl=0.0, tp=2.0, trail=True)),
        ('window i_start 500, i_end 3000', dict(_window=(500, 3000), trail=True, tp=2.0)),
    ]
    fee, slip_ticks = 0.0006, 1
    for name, over in sets:
        p = dict(base)
        p.update(over)
        window = p.pop('_window', (0, None))
        t0 = time.perf_counter()
        trades = reference_trades(m1, chart_tf, trig, zone, volc, p, fee, slip_ticks, window[0], window[1])
        dt = time.perf_counter() - t0
        if window == (0, None):
            _check_trades(trades, m1, chart_tf, trig, zone, p, fee, slip_ticks)
        counts = {}
        for tr in trades:
            counts[tr['why']] = counts.get(tr['why'], 0) + 1
        per_why = ' '.join('%s=%d' % (w, counts[w]) for w in _WHY if w in counts) or '-'
        total_r = sum(tr['r'] for tr in trades)
        print('  %-44s trades=%4d  %-52s sumR=%+9.3f  %.3fs' % (name, len(trades), per_why, total_r, dt))
    print('self-test OK in %.2fs' % (time.perf_counter() - t_begin))


if __name__ == '__main__':
    _self_test()
