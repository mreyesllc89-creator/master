#!/usr/bin/env python3
"""Add the XPW direction veto to a SpeedAlert continuation EA.

  usage: apply_xpdir.py <source_dir> [--out <dir>]

<source_dir> is the SpeedAlert package's `source/` folder, the one holding
SpeedAlert_ExitGate68_Continuation_BurstSettle.mq5 and its .mqh files.

Five surgical edits to ONE file - the main .mq5. Every .mqh in the package,
including SpeedAlertContinuationFilter.mqh, is left byte-identical, because the
veto is applied by subclassing CContinuationTrade in the main file rather than
editing the shared filter. That keeps the package's own audited files untouched
and means this patch survives their next version of those .mqh files.

Every entry in this EA goes through CContinuationTrade::OrderSend - verified:
the only two raw OrderSend() calls (the auto-close path in the .mq5 and
CFRClose in ContinuationExecution.mqh) both set request.position, so they are
closes, and XPDir_IsEntryRequest would pass them anyway.
"""
import os
import shutil
import sys

MAIN = "SpeedAlert_ExitGate68_Continuation_BurstSettle.mq5"
LADDER = "XPW_DirectionLadder.mqh"

EDITS = [
    # 1. the include + the veto subclass, replacing the trade declaration
    ("S1 veto subclass",
     '#include "TheoryJourneyQualityShadowV2.mqh"\n'
     '\n'
     'CContinuationTrade trade;\n',
     '#include "TheoryJourneyQualityShadowV2.mqh"\n'
     '#include "XPW_DirectionLadder.mqh"   // XPDIR: the direction ladder\n'
     '\n'
     '//+------------------------------------------------------------------+\n'
     '//| XPDIR: the direction veto.                                        |\n'
     '//|                                                                    |\n'
     '//| This EA keeps its own trigger AND its own direction. The ladder    |\n'
     '//| only refuses an ENTRY whose side it disagrees with, and only when  |\n'
     '//| InpDirMode = DIR_VETO. In DIR_OFF (the default) XPDir_AllowsRequest|\n'
     '//| returns true for everything and this class is a pass-through.      |\n'
     '//|                                                                    |\n'
     '//| Subclassed here rather than edited into SpeedAlertContinuationFilter|\n'
     '//| .mqh so that every .mqh in the package stays byte-identical.        |\n'
     '//|                                                                    |\n'
     '//| Closes are never blocked: XPDir_IsEntryRequest passes anything with|\n'
     '//| request.position or position_by set, every SLTP/MODIFY/REMOVE, and |\n'
     '//| on a netting account any order that reduces an open position.      |\n'
     '//+------------------------------------------------------------------+\n'
     'class CXPDirContinuationTrade : public CContinuationTrade\n'
     '{\n'
     'public:\n'
     '   virtual bool OrderSend(const MqlTradeRequest &request, MqlTradeResult &result)\n'
     '   {\n'
     '      if(XPDir_AllowsRequest(request))\n'
     '         return CContinuationTrade::OrderSend(request, result);\n'
     '      ZeroMemory(result);\n'
     '      result.retcode = TRADE_RETCODE_REJECT;\n'
     '      result.comment = "XPDIR_VETO";\n'
     '      return false;\n'
     '   }\n'
     '};\n'
     '\n'
     'CXPDirContinuationTrade trade;\n'),

    # 2. OnInit
    ("S2 OnInit",
     '   return INIT_SUCCEEDED;\n}\n',
     '   // XPDIR: DIR_OFF creates no indicator handle and reads nothing.\n'
     '   if(!XPDir_Init(MagicNumber))\n'
     '      return INIT_FAILED;\n'
     '\n'
     '   return INIT_SUCCEEDED;\n}\n'),

    # 3. OnDeinit
    ("S3 OnDeinit",
     '   CP_Deinit();\n',
     '   XPDir_Deinit();          // XPDIR: IndicatorRelease on every rung handle\n'
     '   CP_Deinit();\n'),

    # 4. OnTimer - the funnel says why the ladder is silent, unprompted
    ("S4 OnTimer",
     'void OnTimer()\n{\n#ifdef SAR_CAPTURE_SMOKE\n   return;\n#endif\n',
     'void OnTimer()\n{\n#ifdef SAR_CAPTURE_SMOKE\n   return;\n#endif\n'
     '   XPDir_FunnelHeartbeat();   // XPDIR: explains a silent ladder in the log\n'),
]


def patch(src_dir, out_dir):
    main_in = os.path.join(src_dir, MAIN)
    if not os.path.exists(main_in):
        sys.exit(f"{MAIN} not found in {src_dir}")
    text = open(main_in, newline=None).read()

    for name, old, new in EDITS:
        n = text.count(old)
        if n != 1:
            sys.exit(f"{name}: anchor found {n} times, expected 1 - "
                     f"this SpeedAlert version differs from the ones this "
                     f"patcher was written against; do not guess, re-check it")
        text = text.replace(old, new, 1)
        print(f"  applied {name}")

    # 5. rename: the EA's name in MT5 is its file name; say so in the header too
    ver_old = [l for l in text.split("\n") if l.startswith("#property version")][0]
    ver = ver_old.split('"')[1]
    text = text.replace(ver_old, f'#property version   "{ver}-XPDIR"', 1)
    desc_old = [l for l in text.split("\n") if l.startswith("#property description")][0]
    desc = desc_old.split('"')[1]
    text = text.replace(
        desc_old,
        f'#property description "{desc} | XPW direction veto (InpDirMode=DIR_OFF reproduces the unfiltered EA)."',
        1)
    print(f"  renamed: version {ver} -> {ver}-XPDIR")

    os.makedirs(out_dir, exist_ok=True)
    main_out = os.path.join(out_dir, MAIN.replace(".mq5", "_XPDIR.mq5"))
    open(main_out, "w", newline="\r\n").write(text)
    print(f"  wrote {main_out}")

    here = os.path.dirname(os.path.abspath(__file__))
    ladder = os.path.join(here, "..", "..", "include", LADDER)
    shutil.copy(ladder, os.path.join(out_dir, LADDER))
    print(f"  copied {LADDER}")
    return main_out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    src = sys.argv[1]
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else src
    print(f"patching {src}")
    patch(src, out)
    print("done - every .mqh in the package is unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
