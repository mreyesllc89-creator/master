"""Write complete 157-input MT5 .set presets for XPW_ShapeMap_v092_FGF_EA (UTF-16LE, CRLF)."""
import xpw_run as R

KEY_ORDER = ['EnableTrading', 'SigMode', 'SigTF', 'TradeDir', 'EnterTick', 'TurnEntry', 'FailExit', 'OppMode', 'ArmMode', 'PredBuf', 'CatchUp', 'MaxChase', 'ContEntry', 'ContStopBuf', 'ContStopBars', 'ExitUnit', 'SlPts', 'TpPts', 'ExAtrLen', 'SlAtrM', 'TpR', 'TrailOn', 'TrActPts', 'TrDisPts', 'TrActAtr', 'TrDisAtr', 'TimeStop', 'QtyMode', 'QtyFixed', 'RiskPct', 'QtyMax', 'QtyStep', 'MgnCap', 'MgnPct', 'LossRevOn', 'LossRevWhat', 'LossRevMax', 'LossRevTiny', 'LossRevTinyPts', 'RsiLen', 'FastLen', 'SlowLen', 'InvertFill', 'AreaLook', 'LoFrac', 'HiFrac', 'ShowBotBox', 'ShowBotLbl', 'ShowTopBox', 'ShowTopLbl', 'ShowTurnUp', 'ShowTurnDn', 'ShowBotTick', 'ShowTopTick', 'ShowContMark', 'ShowContTick', 'AllOn', 'AllCtx', 'BotOn', 'BotMinW', 'BotMaxW', 'BotCtxIn', 'BotNeedLow', 'BotSepIn', 'TopOn', 'TopMinW', 'TopMaxW', 'TopCtxIn', 'TopNeedHigh', 'TopSepIn', 'TurnOn', 'TurnMax', 'TurnHold', 'TickOn', 'AtrLen', 'BotWickRange', 'BotWickAtr', 'TopWickRange', 'TopWickAtr', 'ContOn', 'ContBigAtr', 'ContLook', 'ContNeedRed', 'ContRedMax', 'ContPinch', 'ContAfter', 'ContSep', 'ContMirror', 'ShowTable', 'Magic', 'ShowMap', 'MapIndicator', 'EnableCSV', 'StateTag', 'DeviationPoints', 'fgfOn', 'fgfTf', 'fgfLvMode', 'fgfLast', 'fgfMinutes', 'fgfBars', 'fgfCheck', 'fgfBandAtr', 'fgfAgainst', 'fgfAllowBuy', 'fgfAllowSell', 'fgfShowBg', 'fgfShowLv', 'fgfSigMark', 'fgfShowTbl', 'fgfTblPos', 'fgsShow', 'fgsWin', 'fgsH', 'fgfSpreadPts', 'fgfEntryDistPts', 'fgfHoldBars', 'fgfHoldFavPts', 'fgfOnePerBar', 'fgfDistUnit', 'fgfBurstAtr', 'fgfEntryDistAtr', 'fgfHoldFavAtr', 'fgfBurstPts', 'fgfUseBurst', 'fgfAnyCombo', 'fgfDriftBars', 'fgfUseDrift', 'fgfUseZones', 'fgfParentTf', 'fgfRsiLen', 'fgfFastLen', 'fgfMinAligned', 'fgfFlatParent', 'fgfIgnoreNa', 'fgfHtfClosed', 'fgfUseZ1', 'fgfZTf1', 'fgfUseZ2', 'fgfZTf2', 'fgfUseZ3', 'fgfZTf3', 'fgfUseZ4', 'fgfZTf4', 'fgfUseZ5', 'fgfZTf5', 'fgfUseZ6', 'fgfZTf6', 'FenceTestNamespace', 'FenceCapitalUSC', 'FenceAllowExecution', 'CentBtcSymbol', 'CentGoldSymbol', 'CentFixedLots', 'CentMaxEquityDD', 'CentDailyMaxLoss', 'CentSessionGuardSeconds']

FIXED = dict(
    EnableTrading=False, ShowBotBox=True, ShowBotLbl=True, ShowTopBox=True, ShowTopLbl=True, ShowTurnUp=True, ShowTurnDn=True,
    ShowBotTick=True, ShowTopTick=True, ShowContMark=True, ShowContTick=True, ShowTable=True,
    Magic=92020261013, ShowMap=False, MapIndicator="XPW_ShapeMap_v092_FGF_Map", EnableCSV=True, DeviationPoints=20,
    fgfCheck=0, fgfShowBg=True, fgfShowLv=True, fgfSigMark=True, fgfShowTbl=True, fgfTblPos=0, fgsShow=False, fgsWin=500, fgsH=10,
    FenceTestNamespace="", FenceCapitalUSC=10000.0, FenceAllowExecution=False,
    CentBtcSymbol="BTCUSD.c", CentGoldSymbol="XAUUSD-ECNc", CentFixedLots=0.01, CentMaxEquityDD=5.0, CentDailyMaxLoss=5.0,
    CentSessionGuardSeconds=60,
)
FLOAT_KEYS = {"PredBuf", "MaxChase", "ContStopBuf", "SlPts", "TpPts", "SlAtrM", "TpR", "TrActPts", "TrDisPts", "TrActAtr", "TrDisAtr",
              "QtyFixed", "RiskPct", "QtyMax", "QtyStep", "MgnPct", "LossRevTinyPts", "LoFrac", "HiFrac", "BotWickRange", "BotWickAtr",
              "TopWickRange", "TopWickAtr", "ContBigAtr", "ContPinch", "fgfBandAtr", "fgfSpreadPts", "fgfEntryDistPts", "fgfHoldFavPts",
              "fgfBurstAtr", "fgfEntryDistAtr", "fgfHoldFavAtr", "fgfBurstPts", "FenceCapitalUSC", "CentFixedLots", "CentMaxEquityDD",
              "CentDailyMaxLoss"}
CHART_SYMBOL = {"XAUUSD": "XAUUSD-ECNc", "BTCUSD": "BTCUSD.c"}
TF_LABEL = {1: "M1", 5: "M5", 15: "M15", 30: "M30", 60: "H1", 240: "H4"}


def fmt(k, v):
    if isinstance(v, bool): return "true" if v else "false"
    if k in FLOAT_KEYS: return repr(float(v)) if float(v) != int(float(v)) else "%.1f" % float(v)
    if isinstance(v, float): return "%.1f" % v if v == int(v) else repr(v)
    return str(v)


def write_set(path, params, symbol, tf, state_tag, header_lines):
    p = dict(R.DEFAULTS); p.update(params); p.update(FIXED)
    p["SigTF"] = str(int(tf))
    p["EnterTick"] = False
    p["QtyMode"] = 0; p["QtyFixed"] = 1.0 if symbol == "XAUUSD" else 0.01; p["QtyMax"] = p["QtyFixed"]; p["QtyStep"] = 0.01
    p["RiskPct"] = 1.0; p["MgnCap"] = False; p["MgnPct"] = 1.0
    p["StateTag"] = state_tag
    lines = ["; " + h for h in header_lines]
    for k in KEY_ORDER:
        lines.append(f"{k}={fmt(k, p[k])}")
    data = "\r\n".join(lines) + "\r\n"
    with open(path, "wb") as f:
        f.write(b"\xff\xfe" + data.encode("utf-16-le"))
    return p


if __name__ == "__main__":
    import sys
    p = write_set("/tmp/claude-0/-home-user-master/eaac335e-3af3-501b-81bd-bfb21d6f851a/scratchpad/calib/test.set", {"SigTF": 5}, "XAUUSD", 5, "TEST", ["test header"])
    s = open("/tmp/claude-0/-home-user-master/eaac335e-3af3-501b-81bd-bfb21d6f851a/scratchpad/calib/test.set", "rb").read().decode("utf-16")
    keys = [l.split("=")[0] for l in s.splitlines() if "=" in l and not l.startswith(";")]
    print(len(keys), keys == KEY_ORDER)
    print(s[:600])
