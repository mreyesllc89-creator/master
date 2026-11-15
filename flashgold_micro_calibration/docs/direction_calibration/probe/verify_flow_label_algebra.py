#!/usr/bin/env python3
"""verify_flow_label_algebra.py -- enumerate the EA's direction-score / router / label rules (no data needed) to check which
flow-vote patterns can produce a MARKET entry with the label :FA, :FD or none.  Companion of probe_flow_proxy.py.

The rules are transcribed from SpeedAlert_FlashGold_Micro.mq5 v1.501 (parent v1.499 is identical for these functions):
  BuildDirectionState 2322-2346 / ScoreCandle / ScoreMicroBreak / ScoreOrderFlow 2463 / AddFlowVote 2556 / WinnerSide 2639 /
  DecideAction 2742 / MarketEntryAllowedByFlow 2770 / ShortComment 3137,
with the shipped / account inputs: MinDirectionScore 4.0, MinScoreEdge 1.5, SpeedDirectionScore 1.0, CandleBodyScore 1.5,
MicroBreakScore 1.5, SpreadStableScore 0.5, FlowComponentScore 1.0, MinFlowImbalance 5.0, WeakFlowMarketNeedsBodyAndMicro true,
WeakFlowMarketMinScore 5.0, WeakFlowMarketMinScoreEdge 2.0, BlockStrongFlowAgainst false, DowngradeNeutralSellMarketToStop true,
EntryRouterMode 2 (stop + market + limit).

usage: python3 -I verify_flow_label_algebra.py        (prints the tables; writes probe_flow_proxy_label_algebra.csv next to the script)

Inputs of the enumeration (all relative to the burst direction = speedDir = +1; a SELL is the mirror image except for the
neutral-flow downgrade):  body in {with, none, against} (body_pts >= 21), micro-break in {with, none, against},
three flow components each in {vote with, vote against, below threshold}, spread stable, follow21/follow37 true, no exhaustion.
"""
import csv
import itertools
import os

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_SCORE, MIN_EDGE = 4.0, 1.5
S_SPEED, S_BODY, S_MICRO, S_SPREAD, S_FLOW = 1.0, 1.5, 1.5, 0.5, 1.0
WEAK_MIN_SCORE, WEAK_MIN_EDGE = 5.0, 2.0


def evaluate(body, micro, votes, burst=+1, downgrade_neutral_sell=True, flow_fresh=True, spread_stable=True):
    """returns (route, label) for one state; route in {'market','stop','skip'}; votes are +1 (with burst) / -1 (against) / 0."""
    buy = sell = 0.0
    if spread_stable:
        buy += S_SPREAD
        sell += S_SPREAD
    if burst > 0:
        buy += S_SPEED
    else:
        sell += S_SPEED
    body_dir, micro_dir = body * burst, micro * burst                # states are given relative to the burst
    if body_dir > 0:
        buy += S_BODY
    elif body_dir < 0:
        sell += S_BODY
    if micro_dir > 0:
        buy += S_MICRO
    elif micro_dir < 0:
        sell += S_MICRO
    bv = sv = 0
    if flow_fresh:
        for v in votes:
            v = v * burst
            if v > 0:
                bv += 1
                buy += S_FLOW
            elif v < 0:
                sv += 1
                sell += S_FLOW
    flow_dir = 1 if bv >= 2 else (-1 if sv >= 2 else 0)
    if buy >= MIN_SCORE and buy - sell >= MIN_EDGE:
        winner = 1
    elif sell >= MIN_SCORE and sell - buy >= MIN_EDGE:
        winner = -1
    else:
        winner = 0
    agrees = winner != 0 and flow_dir == winner
    disagrees = winner != 0 and flow_dir == -winner
    label = "FA" if agrees else ("FD" if disagrees else "none")
    if not spread_stable or winner == 0:
        return "skip", label
    follow_ok = True
    market = False
    if burst == winner and follow_ok:
        neutral = (not flow_fresh) or flow_dir == 0
        weak = neutral or disagrees
        if winner < 0 and downgrade_neutral_sell and neutral:
            market = False
        elif weak:
            score = buy if winner > 0 else sell
            edge = abs(buy - sell)
            market = (body_dir == winner and micro_dir == winner and score >= WEAK_MIN_SCORE and edge >= WEAK_MIN_EDGE)
        else:
            market = True
    if market:
        return "market", label
    side = winner
    if body_dir == -side:                                             # stopWithBodyAgainst in OnTick
        return "skip", label
    return "stop", label


def main():
    rows = []
    for body, micro in itertools.product((1, 0, -1), repeat=2):
        for votes in itertools.product((1, -1, 0), repeat=3):
            for burst, nm in ((+1, "BUY"), (-1, "SELL")):
                route, label = evaluate(body, micro, votes, burst)
                w = sum(1 for v in votes if v > 0)
                a = sum(1 for v in votes if v < 0)
                rows.append(dict(side=nm, body="with" if body > 0 else ("none" if body == 0 else "against"),
                                 micro="with" if micro > 0 else ("none" if micro == 0 else "against"),
                                 votes_with=w, votes_against=a, votes_neutral=3 - w - a, route=route, label=label))
    with open(os.path.join(HERE, "probe_flow_proxy_label_algebra.csv"), "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    print("MARKET entries only: which (votes with, votes against) patterns and price states give which label")
    for side in ("BUY", "SELL"):
        print(f"\n== {side}")
        for label in ("FA", "FD", "none"):
            sel = [r for r in rows if r["side"] == side and r["route"] == "market" and r["label"] == label]
            pats = sorted({(r["votes_with"], r["votes_against"]) for r in sel})
            price = sorted({(r["body"], r["micro"]) for r in sel})
            print(f"  label {label:4s}: {len(sel):3d} of 243 states (3 body x 3 micro x 27 vote patterns) reach the market route; (with, against) patterns = {pats}; (body, micro) states = {price}")
    print("\nSummary the probe relies on:")
    mk = [r for r in rows if r["route"] == "market"]
    print("  every market entry has at least one vote with the trade:", all(r["votes_with"] >= 1 for r in mk))
    fd = [r for r in mk if r["label"] == "FD"]
    print("  market + FD  <=> (1 with, 2 against) and body, micro with the trade:",
          all((r["votes_with"], r["votes_against"], r["body"], r["micro"]) == (1, 2, "with", "with") for r in fd) and len(fd) > 0)
    nn = [r for r in mk if r["label"] == "none"]
    print("  market + none: sides present", sorted({r["side"] for r in nn}), "| (with, against) patterns", sorted({(r["votes_with"], r["votes_against"]) for r in nn}),
          "| body, micro with the trade:", all(r["body"] == "with" and r["micro"] == "with" for r in nn))
    fa = [r for r in mk if r["label"] == "FA"]
    print("  market + FA  <=> at least 2 votes with the trade:", all(r["votes_with"] >= 2 for r in fa), "| price states reaching it:",
          sorted({(r["body"], r["micro"]) for r in fa}))
    print("  stale feed (no votes, flowFresh=false): market possible?",
          any(evaluate(b, m, (0, 0, 0), +1, flow_fresh=False)[0] == "market" for b in (1, 0, -1) for m in (1, 0, -1)))
    print("  (body, micro) = (with, with), no flow at all: route =", evaluate(1, 1, (0, 0, 0), +1)[0],
          "(base score 4.5 < WeakFlowMarketMinScore 5.0, so the flow feed is what unlocks the market route)")


if __name__ == "__main__":
    main()
