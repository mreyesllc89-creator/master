#!/usr/bin/env python3
"""Generate XPW_DirectionLadder.mqh from the audited EA.

The ladder is written once, inside FlashGold_Continuation_v2_XPDIR.mq5, and
extracted from there between the XPDIR_LADDER_BEGIN / XPDIR_LADDER_END markers
plus the input group. Nothing is retyped, so the include cannot drift from the
build that Gate 0 and Gate 1 audit.

  usage: make_include.py <ea.mq5> <out.mqh> [--check]
         --check  exit 1 if <out.mqh> is not what this would produce

What travels: the map reading, the cross detection, the rules, the decision,
the logging, the CSV, the funnel, and the veto. What does not: FlashGold's own
arming/translating wiring, which lives after XPDIR_LADDER_END and only makes
sense for an EA built on two virtual stop levels.
"""
import re
import sys

HEADER = """//+------------------------------------------------------------------+
//|                                        XPW_DirectionLadder.mqh   |
//|                                                                  |
//|  GENERATED - do not edit. Produced by                            |
//|  XPDirection/reference/emu/make_include.py from                  |
//|  XPDirection/FlashGold_Continuation_v2_XPDIR.mq5 between the     |
//|  XPDIR_LADDER_BEGIN / XPDIR_LADDER_END markers. Edit the EA and  |
//|  regenerate; the Gate 0 pre-check fails if the two disagree.     |
//|                                                                  |
//|  A fractal ladder of XPW Shape Map instances (1 s .. 45 s plus   |
//|  one parent timeframe) that answers one question: which way.     |
//|                                                                  |
//|  HOST CONTRACT - four calls, nothing else:                       |
//|    OnInit    : if(!XPDir_Init(InpMagic)) return INIT_FAILED;     |
//|    OnDeinit  : XPDir_Deinit();                                   |
//|    OnTimer   : XPDir_FunnelHeartbeat();   // needs EventSetTimer |
//|    entry     : if(!XPDir_Allows(isBuy)) return;                  |
//|                or, with CTrade, include XPW_DirectionVeto.mqh    |
//|                                                                  |
//|  The ladder touches no order, no position, no stop and no chart  |
//|  object of the host. In DIR_OFF it creates no indicator handle   |
//|  and XPDir_Allows() returns true for everything.                 |
//+------------------------------------------------------------------+
#property strict

"""


def build(ea_path):
    src = open(ea_path, newline=None).read()

    a = src.index("enum ENUM_XPDIR ")
    b = src.index("\n", src.rindex("input ENUM_XPDIR_ON_NONE"))
    inputs = src[a:b]

    m0 = src.index("XPDIR_LADDER_BEGIN")
    m0 = src.index("\n", src.index("//| XPW Direction Ladder v1", m0)) + 1
    m0 = src.rindex("//+---", 0, m0)
    m1 = src.rindex("//+------------------------------------------------------------------+",
                    0, src.index("XPDIR_LADDER_END"))
    ladder = src[m0:m1]

    return (HEADER
            + "//--- inputs (same names, order and defaults as the EA)\n"
            + inputs + "\n\n" + ladder.rstrip() + "\n")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    out = build(sys.argv[1])
    if "--check" in sys.argv:
        try:
            have = open(sys.argv[2], newline=None).read()
        except FileNotFoundError:
            print(f"{sys.argv[2]} does not exist")
            return 1
        if have != out:
            print(f"{sys.argv[2]} is STALE - regenerate it from the EA")
            return 1
        print(f"{sys.argv[2]} matches the EA")
        return 0
    open(sys.argv[2], "w", newline="\r\n").write(out)
    print(f"wrote {sys.argv[2]}: {out.count(chr(10))} lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
