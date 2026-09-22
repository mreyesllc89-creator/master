#!/usr/bin/env python3
"""XPDir vote reference - an independent transliteration of XPDir_Current()'s
rule evaluation from FlashGold_Continuation_v2_XPDIR.mq5.

Written from the prompt's section 4 rules, not by machine-translating the MQL5.
Gate 1 runs the fixtures through BOTH this file and the EA's own compiled rule
core (reference/emu) and requires all three to agree: fixture expectation,
this reference, and the compiled MQL5.

Votes: +1 BUY, -1 SELL, 0 NO_VOTE. NO_VOTE is never counted as disagreement.
"""
from __future__ import annotations

EMPTY_VALUE = 1.7976931348623157e308

BUY, SELL, NO_VOTE = 1, -1, 0


def rung_vote(fast, slow, runlen, age_seconds, interval_seconds,
              max_stale_bars, max_runlen_bars):
    """One rung's vote from the map's own outputs on the last CLOSED bar.

    EMPTY_VALUE in FAST or SLOW is the map's valid flag
    (XPW_ShapeMap_v0.4.mq5: BufFast[i] = fastOk ? fast : EMPTY_VALUE).
    Returns (vote, why).
    """
    for v in (fast, slow):
        if v != v or v in (float("inf"), float("-inf")) or abs(v) >= EMPTY_VALUE:
            return NO_VOTE, "map_invalid"
    if age_seconds > max_stale_bars * interval_seconds:
        return NO_VOTE, "stale"
    if max_runlen_bars > 0 and runlen > max_runlen_bars:
        return NO_VOTE, "runlen_capped"
    if fast > slow:
        return BUY, "ok"          # bullish TDI
    if fast < slow:
        return SELL, "ok"         # bearish TDI
    return NO_VOTE, "fast_eq_slow"


def rule_passes_for(x, parent_vote, s1_vote, optional_votes,
                    min_with_parent, min_against_parent,
                    s1_required_against_parent):
    """Which rule, if any, carries direction x. 0 = none."""
    n_optional = sum(1 for v in optional_votes if v == x)

    if parent_vote == x:
        if s1_vote == x:
            return 1                                   # R1 aligned
        if n_optional >= min_with_parent:
            return 2                                   # R2 parent carries
        return 0
    # P != X (a NO_VOTE parent lands here: it cannot satisfy R1 or R2)
    n_against = n_optional + (1 if s1_vote == x else 0)   # S1 counts as a child
    if n_against >= min_against_parent and \
       (not s1_required_against_parent or s1_vote == x):
        return 3                                       # R3 children overrule
    return 0


def decide(parent_vote, s1_vote, optional_votes,
           min_with_parent=2, min_against_parent=3,
           s1_required_against_parent=True):
    """Returns (direction, rule, conflict)."""
    r_buy = rule_passes_for(BUY, parent_vote, s1_vote, optional_votes,
                            min_with_parent, min_against_parent,
                            s1_required_against_parent)
    r_sell = rule_passes_for(SELL, parent_vote, s1_vote, optional_votes,
                             min_with_parent, min_against_parent,
                             s1_required_against_parent)
    if r_buy and r_sell:
        return NO_VOTE, 0, True
    if r_buy:
        return BUY, r_buy, False
    if r_sell:
        return SELL, r_sell, False
    return NO_VOTE, 0, False


def dir_name(d):
    return {BUY: "BUY", SELL: "SELL", NO_VOTE: "NONE"}[d]


def vote_tag(present, vote):
    if not present:
        return "-"
    return {BUY: "BUY", SELL: "SELL", NO_VOTE: "NV"}[vote]


# --- fixture plumbing -------------------------------------------------------
RUNGS = ["P", "S1", "S5", "S10", "S15", "S30", "S45"]


def parse_rung(spec, max_stale, max_runlen):
    """'-' absent, 'nv' present-but-no-vote, 'fast|slow|runlen|age|interval'."""
    spec = spec.strip()
    if spec == "-":
        return False, NO_VOTE
    if spec == "nv":
        return True, NO_VOTE
    parts = spec.split("|")
    if len(parts) != 5:
        raise ValueError(f"bad rung spec {spec!r}")

    def num(t):
        return EMPTY_VALUE if t == "EMPTY" else (float("nan") if t == "NAN" else float(t))

    vote, _ = rung_vote(num(parts[0]), num(parts[1]), int(parts[2]),
                        int(parts[3]), int(parts[4]), max_stale, max_runlen)
    return True, vote


def evaluate_row(row):
    """row: dict from the fixture CSV. Returns the result dict."""
    max_stale = int(row["max_stale"])
    max_runlen = int(row["max_runlen"])
    present, votes = {}, {}
    for name in RUNGS:
        present[name], votes[name] = parse_rung(row[name], max_stale, max_runlen)

    optional = [votes[n] for n in RUNGS[2:] if present[n]]
    d, rule, conflict = decide(votes["P"], votes["S1"], optional,
                               int(row["min_with"]), int(row["min_against"]),
                               row["s1_required"].strip() in ("1", "true"))
    return {
        "name": row["name"],
        "dir": dir_name(d),
        "rule": f"R{rule}" if rule else "-",
        "conflict": 1 if conflict else 0,
        **{("C1" if n == "S1" else ("P" if n == "P" else "C" + n[1:])):
           vote_tag(present[n], votes[n]) for n in RUNGS},
    }


def load_fixtures(path):
    rows, head = [], None
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            cells = [c.strip() for c in line.split(",")]
            if head is None:
                head = cells
                continue
            rows.append(dict(zip(head, cells)))
    return rows


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "fixtures/vote_rules.csv"
    print("name,dir,rule,conflict,P,C1,C5,C10,C15,C30,C45")
    for row in load_fixtures(path):
        r = evaluate_row(row)
        print(",".join(str(r[k]) for k in
                       ("name", "dir", "rule", "conflict",
                        "P", "C1", "C5", "C10", "C15", "C30", "C45")))
