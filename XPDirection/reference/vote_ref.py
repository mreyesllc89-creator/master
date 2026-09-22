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


GRADE_NONE, GRADE_EARLY, GRADE_FRESH, GRADE_STALE = 0, 1, 2, 3
GRADE_NAME = {GRADE_NONE: "-", GRADE_EARLY: "EARLY",
              GRADE_FRESH: "FRESH", GRADE_STALE: "STALE_STATE"}


def is_empty(v):
    return v != v or abs(v) >= EMPTY_VALUE


def sign(v):
    return 1 if v > 0 else (-1 if v < 0 else 0)


def advance_cross(series, new_count, carried_sign, cross_dir, cross_age, cross_sep):
    """Walk the newly CLOSED bars oldest -> newest, carrying the sign forward.

    series is [(fast, slow), ...] newest-first; index 0 is the bar that just
    closed and the forming bar is never in it.

    Equality is not a sign: a bar where fast == slow inherits the previous
    closed bar's carried sign, so a touch is not a cross and a touch that
    resumes the same side is not a cross either. Only a strict flip of the
    carried sign is a cross, stamped on the bar where the new non-zero sign
    appears. This deliberately differs from Pine's ta.crossover.

    cross_dir persists: it is the direction of the most recent cross since
    warm-up, held until the next one, and 0 only while none has been seen.
    "Crossed on this bar" is cross_age == 0; there is no separate flag.
    """
    for b in range(new_count - 1, -1, -1):
        f, sl = series[b]
        if is_empty(f) or is_empty(sl):
            continue                       # the map has not processed this bar
        sep = f - sl
        s = sign(sep)
        crossed = False
        if s != 0:
            if carried_sign == 0:
                carried_sign = s           # the first sign of all is not a cross
            elif s != carried_sign:
                carried_sign, cross_dir, cross_sep, cross_age = s, s, sep, 0
                crossed = True
        if not crossed and cross_age >= 0:
            cross_age += 1
    return carried_sign, cross_dir, cross_age, cross_sep


def vote_from_cross(sep_now, bar0_valid, carried_sign, cross_dir, cross_age,
                    cross_sep, age_seconds, interval_seconds, max_stale_bars,
                    cross_max_age_bars, early_sep_mult):
    """Returns (vote, grade, why).

    An unknown age (-1, no cross seen yet) is treated as OLD, not absent: the
    rung still votes its carried sign, marked STALE_STATE. NO_VOTE is only for
    the map's own warm-up, a stale feed, and a sign that is still zero.
    """
    if not bar0_valid:
        return NO_VOTE, GRADE_NONE, "map_invalid"
    if age_seconds > max_stale_bars * interval_seconds:
        return NO_VOTE, GRADE_NONE, "stale"
    if carried_sign == 0:
        return NO_VOTE, GRADE_NONE, "sign_zero"

    if cross_max_age_bars > 0 and 0 <= cross_age <= cross_max_age_bars:
        grade = GRADE_EARLY if (cross_age == 0 or
                                abs(sep_now) <= abs(cross_sep) * early_sep_mult) \
                else GRADE_FRESH
        return cross_dir, grade, "cross"

    # state is the floor, never the signal
    why = "state_no_cross_seen" if cross_age < 0 else "state_cross_aged_out"
    return carried_sign, GRADE_STALE, why


def rule_passes_for(x, parent_vote, s1_vote, s1_fresh, optional_votes,
                    min_with_parent, min_against_parent,
                    s1_required_against_parent, require_fresh_s1):
    """Which rule, if any, carries direction x. 0 = none.

    require_fresh_s1 applies to every rule that NEEDS C1 == X (R1, and R3 when
    s1_required_against_parent) and to no other. R2 is untouched by it, and no
    other rung's grade is ever enforced.
    """
    n_optional = sum(1 for v in optional_votes if v == x)
    s1_counts = (s1_vote == x) and (not require_fresh_s1 or s1_fresh)

    if parent_vote == x:
        if s1_counts:
            return 1                                   # R1 aligned
        if s1_vote != x and n_optional >= min_with_parent:
            return 2                                   # R2 parent carries
        return 0
    # P != X (a NO_VOTE parent lands here: it cannot satisfy R1 or R2)
    n_against = n_optional + (1 if s1_vote == x else 0)   # S1 counts as a child
    if n_against >= min_against_parent and \
       (not s1_required_against_parent or s1_counts):
        return 3                                       # R3 children overrule
    return 0


def decide(parent_vote, s1_vote, s1_fresh, optional_votes,
           min_with_parent=2, min_against_parent=3,
           s1_required_against_parent=True, require_fresh_s1=False):
    """Returns (direction, rule, conflict)."""
    r_buy = rule_passes_for(BUY, parent_vote, s1_vote, s1_fresh, optional_votes,
                            min_with_parent, min_against_parent,
                            s1_required_against_parent, require_fresh_s1)
    r_sell = rule_passes_for(SELL, parent_vote, s1_vote, s1_fresh, optional_votes,
                             min_with_parent, min_against_parent,
                             s1_required_against_parent, require_fresh_s1)
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
OUT_COLS = ("name", "dir", "rule", "conflict", "p_grade", "c1_grade",
            "P", "C1", "C5", "C10", "C15", "C30", "C45")


def parse_rung(spec, row):
    """'-' absent, 'nv' present-but-no-vote, or
    'f:s/f:s/...|age|interval|carried|crossdir|crossage|crosssep'.

    The trailing four are the rung's PERSISTED state going into this read -
    the carried sign, and the most recent cross as it stands. 'x' means the
    default (0 / -1 / 0.0), i.e. a rung reading for the very first time.
    """
    spec = spec.strip()
    if spec == "-":
        return False, NO_VOTE, GRADE_NONE
    if spec == "nv":
        return True, NO_VOTE, GRADE_NONE
    parts = spec.split("|")
    if len(parts) != 7:
        raise ValueError(f"bad rung spec {spec!r}")

    def num(t):
        return EMPTY_VALUE if t == "EMPTY" else float(t)

    series = []
    for bar in parts[0].split("/"):
        f, sl = bar.split(":")
        series.append((num(f), num(sl)))

    carried = 0 if parts[3] == "x" else int(parts[3])
    cdir = 0 if parts[4] == "x" else int(parts[4])
    cage = -1 if parts[5] == "x" else int(parts[5])
    csep = 0.0 if parts[6] == "x" else float(parts[6])

    carried, cdir, cage, csep = advance_cross(series, len(series),
                                              carried, cdir, cage, csep)
    bar0_valid = not (is_empty(series[0][0]) or is_empty(series[0][1]))
    sep_now = (series[0][0] - series[0][1]) if bar0_valid else 0.0
    vote, grade, _ = vote_from_cross(sep_now, bar0_valid, carried, cdir, cage,
                                     csep, int(parts[1]), int(parts[2]),
                                     int(row["max_stale"]),
                                     int(row["cross_max_age"]),
                                     float(row["early_sep_mult"]))
    return True, vote, grade


def evaluate_row(row):
    """row: dict from the fixture CSV. Returns the result dict."""
    present, votes, grades = {}, {}, {}
    for name in RUNGS:
        present[name], votes[name], grades[name] = parse_rung(row[name], row)

    optional = [votes[n] for n in RUNGS[2:] if present[n]]
    s1_fresh = grades["S1"] in (GRADE_EARLY, GRADE_FRESH)
    d, rule, conflict = decide(votes["P"], votes["S1"], s1_fresh, optional,
                               int(row["min_with"]), int(row["min_against"]),
                               row["s1_required"].strip() in ("1", "true"),
                               row["require_fresh_s1"].strip() in ("1", "true"))
    out = {
        "name": row["name"],
        "dir": dir_name(d),
        "rule": f"R{rule}" if rule else "-",
        "conflict": 1 if conflict else 0,
        "p_grade": GRADE_NAME[grades["P"]],
        "c1_grade": GRADE_NAME[grades["S1"]],
    }
    out.update({("C1" if n == "S1" else ("P" if n == "P" else "C" + n[1:])):
                vote_tag(present[n], votes[n]) for n in RUNGS})
    return out


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
    print(",".join(OUT_COLS))
    for row in load_fixtures(path):
        r = evaluate_row(row)
        print(",".join(str(r[k]) for k in OUT_COLS))
