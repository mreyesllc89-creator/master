"""Glue: parameter dict -> backtest run with caching of indicator/FGF stages."""
import numpy as np
import xpw_data, xpw_engine as E

TF_ENUM = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 10: 10, 12: 12, 15: 15, 20: 20, 30: 30,
           60: 16385, 120: 16386, 180: 16387, 240: 16388, 360: 16390, 480: 16392, 720: 16396,
           1440: 16408}
ENUM_TF = {v: k for k, v in TF_ENUM.items()}

SYMBOLS = {
    # data symbol, gold session filter, tick, spread model, commission model, unit label, usd per price unit per 0.01 lot
    "XAUUSD": dict(data="PAXGUSDT", gold=True, tick=0.01, spreadPts=25.0, spreadPct=0.0, commPts=3.0, commPct=0.0, usd_per_unit=1.0, lot_desc="0.01 lot = 1 oz"),
    "BTCUSD": dict(data="BTCUSDT", gold=False, tick=0.01, spreadPts=0.0, spreadPct=0.0003, commPts=0.0, commPct=0.0001, usd_per_unit=0.01, lot_desc="0.01 lot = 0.01 BTC"),
}

DEFAULTS = dict(
    SigMode=1, SigTF=5, TradeDir=0, EnterTick=False, TurnEntry=0, FailExit=False, OppMode=0, ArmMode=0, PredBuf=100.0,
    CatchUp=True, MaxChase=0.0, ContEntry=0, ContStopBuf=50.0, ContStopBars=3, ExitUnit=0, SlPts=7000.0, TpPts=50000.0,
    ExAtrLen=14, SlAtrM=2.0, TpR=2.0, TrailOn=True, TrActPts=1000.0, TrDisPts=100.0, TrActAtr=4.0, TrDisAtr=0.2, TimeStop=0,
    QtyMode=0, QtyFixed=0.01, RiskPct=1.0, QtyMax=0.01, QtyStep=0.01, MgnCap=False, MgnPct=1.0,
    LossRevOn=True, LossRevWhat=0, LossRevMax=1, LossRevTiny=True, LossRevTinyPts=1500.0,
    RsiLen=14, FastLen=2, SlowLen=7, InvertFill=True, AreaLook=20, LoFrac=0.2, HiFrac=0.67,
    AllOn=True, AllCtx=1, BotOn=True, BotMinW=1, BotMaxW=3, BotCtxIn=2, BotNeedLow=True, BotSepIn=5,
    TopOn=True, TopMinW=1, TopMaxW=2, TopCtxIn=3, TopNeedHigh=True, TopSepIn=5, TurnOn=True, TurnMax=12, TurnHold=2,
    TickOn=True, AtrLen=14, BotWickRange=0.55, BotWickAtr=0.8, TopWickRange=0.7, TopWickAtr=1.2,
    ContOn=True, ContBigAtr=1.0, ContLook=30, ContNeedRed=True, ContRedMax=12, ContPinch=1.0, ContAfter=6, ContSep=5, ContMirror=True,
    fgfOn=True, fgfTf=16385, fgfLvMode=0, fgfLast=0, fgfMinutes=60, fgfBars=1, fgfCheck=0, fgfBandAtr=0.25, fgfAgainst=True,
    fgfAllowBuy=True, fgfAllowSell=True, fgfSpreadPts=25.0, fgfEntryDistPts=50.0, fgfHoldBars=0, fgfHoldFavPts=5.0, fgfOnePerBar=True,
    fgfDistUnit=0, fgfBurstAtr=0.5, fgfEntryDistAtr=0.25, fgfHoldFavAtr=0.1, fgfBurstPts=172.0, fgfUseBurst=True, fgfAnyCombo=False,
    fgfDriftBars=60, fgfUseDrift=False, fgfUseZones=True, fgfParentTf=16385, fgfRsiLen=14, fgfFastLen=2, fgfMinAligned=2,
    fgfFlatParent=False, fgfIgnoreNa=True, fgfHtfClosed=True, fgfUseZ1=True, fgfZTf1=16385, fgfUseZ2=True, fgfZTf2=16386,
    fgfUseZ3=True, fgfZTf3=16388, fgfUseZ4=False, fgfZTf4=16392, fgfUseZ5=False, fgfZTf5=1, fgfUseZ6=False, fgfZTf6=2,
)

IND_KEYS = ("RsiLen", "FastLen", "SlowLen", "InvertFill", "AreaLook", "AtrLen", "ExAtrLen")
EVT_KEYS = IND_KEYS + ("LoFrac", "HiFrac", "AllOn", "AllCtx", "BotOn", "BotMinW", "BotMaxW", "BotCtxIn", "BotNeedLow", "BotSepIn",
                       "TopOn", "TopMinW", "TopMaxW", "TopCtxIn", "TopNeedHigh", "TopSepIn", "TurnOn", "TurnMax", "TurnHold", "ArmMode",
                       "TickOn", "BotWickRange", "BotWickAtr", "TopWickRange", "TopWickAtr",
                       "ContOn", "ContBigAtr", "ContLook", "ContNeedRed", "ContRedMax", "ContPinch", "ContAfter", "ContSep", "ContMirror")
FGF_KEYS = ("fgfOn", "fgfTf", "fgfLvMode", "fgfLast", "fgfMinutes", "fgfBars", "fgfBandAtr", "fgfAgainst", "fgfAllowBuy", "fgfAllowSell",
            "fgfSpreadPts", "fgfEntryDistPts", "fgfHoldBars", "fgfHoldFavPts", "fgfOnePerBar", "fgfDistUnit", "fgfBurstAtr", "fgfEntryDistAtr",
            "fgfHoldFavAtr", "fgfBurstPts", "fgfUseBurst", "fgfAnyCombo", "fgfDriftBars", "fgfUseDrift", "fgfUseZones", "fgfParentTf",
            "fgfRsiLen", "fgfFastLen", "fgfMinAligned", "fgfFlatParent", "fgfIgnoreNa", "fgfHtfClosed",
            "fgfUseZ1", "fgfZTf1", "fgfUseZ2", "fgfZTf2", "fgfUseZ3", "fgfZTf3")


class Market:
    """Holds resampled bars for one symbol at every timeframe needed."""

    def __init__(self, symbol, start=None, end=None):
        self.symbol = symbol
        self.spec = SYMBOLS[symbol]
        t, o, h, l, c = xpw_data.load_1m(self.spec["data"])
        if self.spec["gold"]:
            m = xpw_data.gold_session_mask(t)
            t, o, h, l, c = t[m], o[m], h[m], l[m], c[m]
        if start is not None:
            m = t >= start
            t, o, h, l, c = t[m], o[m], h[m], l[m], c[m]
        if end is not None:
            m = t < end
            t, o, h, l, c = t[m], o[m], h[m], l[m], c[m]
        self.m1 = (t, o, h, l, c)
        self._bars = {}
        self._tdi = {}
        self._ind = {}
        self._evt = {}
        self._fgf = {}

    def bars(self, minutes):
        if minutes not in self._bars:
            self._bars[minutes] = xpw_data.resample(*self.m1, minutes)
        return self._bars[minutes][:5]

    def subranges(self, minutes):
        self.bars(minutes)
        return self._bars[minutes][5], self._bars[minutes][6]

    def tdi(self, minutes, rsiLen, fastLen):
        key = (minutes, rsiLen, fastLen)
        if key not in self._tdi:
            bt, bo, bh, bl, bc = self.bars(minutes)
            self._tdi[key] = E.tdi_dirs(bc, rsiLen, fastLen)
        return self._tdi[key]

    def indicators(self, minutes, p):
        key = (minutes,) + tuple(p[k] for k in IND_KEYS)
        if key not in self._ind:
            if len(self._ind) > 6: self._ind.clear()
            bt, bo, bh, bl, bc = self.bars(minutes)
            self._ind[key] = E.indicators(bo, bh, bl, bc, int(p["RsiLen"]), int(p["FastLen"]), int(p["SlowLen"]), bool(p["InvertFill"]),
                                          int(p["AreaLook"]), int(p["AtrLen"]), int(p["ExAtrLen"]))
        return self._ind[key]

    def events(self, minutes, p):
        key = (minutes,) + tuple(p[k] for k in EVT_KEYS)
        if key not in self._evt:
            if len(self._evt) > 6: self._evt.clear()
            bt, bo, bh, bl, bc = self.bars(minutes)
            rsi, up, dn, validRsi, fast, slow, validFast, validSlow, isRed, atr, validAtr, pos, exAtr, validExAtr, exAtrOpen = self.indicators(minutes, p)
            self._evt[key] = E.events(bo, bh, bl, bc, rsi, up, dn, validRsi, fast, slow, validFast, validSlow, isRed, atr, validAtr, pos,
                                      int(p["RsiLen"]), int(p["FastLen"]), int(p["SlowLen"]), float(p["LoFrac"]), float(p["HiFrac"]),
                                      bool(p["AllOn"]), int(p["AllCtx"]),
                                      bool(p["BotOn"]), int(p["BotMinW"]), int(p["BotMaxW"]), int(p["BotCtxIn"]), bool(p["BotNeedLow"]), int(p["BotSepIn"]),
                                      bool(p["TopOn"]), int(p["TopMinW"]), int(p["TopMaxW"]), int(p["TopCtxIn"]), bool(p["TopNeedHigh"]), int(p["TopSepIn"]),
                                      bool(p["TurnOn"]), int(p["TurnMax"]), int(p["TurnHold"]), int(p["ArmMode"]) == 1,
                                      bool(p["TickOn"]), float(p["BotWickRange"]), float(p["BotWickAtr"]), float(p["TopWickRange"]), float(p["TopWickAtr"]),
                                      bool(p["ContOn"]), float(p["ContBigAtr"]), int(p["ContLook"]), bool(p["ContNeedRed"]), int(p["ContRedMax"]),
                                      float(p["ContPinch"]), int(p["ContAfter"]), int(p["ContSep"]), bool(p["ContMirror"]))
        return self._evt[key]

    def fgf(self, chart_minutes, p):
        key = (chart_minutes,) + tuple(p[k] for k in FGF_KEYS)
        if key not in self._fgf:
            if len(self._fgf) > 12: self._fgf.clear()
            ct, co, ch, cl, cc = self.bars(chart_minutes)
            tick = self.spec["tick"]
            if not p["fgfOn"]:
                n = len(cc); self._fgf[key] = (np.ones(n, np.uint8), np.ones(n, np.uint8))
                return self._fgf[key]
            fmin = ENUM_TF[int(p["fgfTf"])] if int(p["fgfTf"]) != 0 else chart_minutes
            pmin = ENUM_TF[int(p["fgfParentTf"])] if int(p["fgfParentTf"]) != 0 else chart_minutes
            ft, fo, fh, fl, fc = self.bars(fmin)
            pt = self.bars(pmin)[0]
            pdirs = self.tdi(pmin, int(p["fgfRsiLen"]), int(p["fgfFastLen"]))
            zt = []; zd = []; zp = []; zo = []
            for z in (1, 2, 3):
                on = bool(p[f"fgfUseZ{z}"])
                zm = ENUM_TF[int(p[f"fgfZTf{z}"])] if int(p[f"fgfZTf{z}"]) != 0 else chart_minutes
                if on:
                    zt.append(self.bars(zm)[0]); zd.append(self.tdi(zm, int(p["fgfRsiLen"]), int(p["fgfFastLen"])))
                else:
                    zt.append(np.zeros(1, np.int64)); zd.append(np.zeros(1, np.int8))
                zp.append(zm * 60); zo.append(on)
            arm = E.fgf_filter(ft, fo, fh, fl, fc, fmin * 60, pt, pdirs, pmin * 60,
                               zt[0], zd[0], zp[0], zo[0], zt[1], zd[1], zp[1], zo[1], zt[2], zd[2], zp[2], zo[2], bool(p["fgfHtfClosed"]),
                               tick, float(p["fgfSpreadPts"]), float(p["fgfEntryDistPts"]), int(p["fgfHoldBars"]), float(p["fgfHoldFavPts"]),
                               bool(p["fgfOnePerBar"]), int(p["fgfDistUnit"]), float(p["fgfBurstAtr"]), float(p["fgfEntryDistAtr"]),
                               float(p["fgfHoldFavAtr"]), float(p["fgfBurstPts"]), bool(p["fgfUseBurst"]), bool(p["fgfAnyCombo"]),
                               int(p["fgfDriftBars"]), bool(p["fgfUseDrift"]), bool(p["fgfUseZones"]), int(p["fgfMinAligned"]),
                               bool(p["fgfFlatParent"]), bool(p["fgfIgnoreNa"]), int(p["fgfLvMode"]))
            self._fgf[key] = E.fgf_permissions(ct, cc, chart_minutes * 60, ft, fmin * 60, arm[0], arm[1], arm[2], arm[3], arm[5],
                                               True, int(p["fgfLast"]), int(p["fgfMinutes"]), int(p["fgfBars"]), float(p["fgfBandAtr"]),
                                               bool(p["fgfAgainst"]), bool(p["fgfAllowBuy"]), bool(p["fgfAllowSell"]), tick)
        return self._fgf[key]

    def run(self, p, cost_mult=1.0, trade_from=None):
        """trade_from: no entry is allowed on bars that open before this time (indicator warm-up prefix)."""
        minutes = int(p["SigTF"])
        bt, bo, bh, bl, bc = self.bars(minutes)
        s0, s1 = self.subranges(minutes)
        mt, mo, mh, ml, mc = self.m1
        rsi, up, dn, validRsi, fast, slow, validFast, validSlow, isRed, atr, validAtr, pos, exAtr, validExAtr, exAtrOpen = self.indicators(minutes, p)
        ev = self.events(minutes, p)
        fb, fs = self.fgf(minutes, p)
        if trade_from is not None:
            k = int(np.searchsorted(bt, trade_from))
            if k > 0:
                fb = fb.copy(); fs = fs.copy(); fb[:k] = 0; fs[:k] = 0
        s = self.spec
        res = E.simulate(bo, bh, bl, bc, s0, s1, mo, mh, ml, mc, exAtr, exAtrOpen, validExAtr, fast, slow, validFast, validSlow, *ev, fb, fs,
                         int(p["SigMode"]), int(p["TradeDir"]), int(p["TurnEntry"]), bool(p["FailExit"]), int(p["OppMode"]), int(p["ArmMode"]) == 1,
                         float(p["PredBuf"]), bool(p["CatchUp"]), float(p["MaxChase"]), int(p["ContEntry"]), float(p["ContStopBuf"]), int(p["ContStopBars"]),
                         int(p["ExitUnit"]), float(p["SlPts"]), float(p["TpPts"]), float(p["SlAtrM"]), float(p["TpR"]), bool(p["TrailOn"]),
                         float(p["TrActPts"]), float(p["TrDisPts"]), float(p["TrActAtr"]), float(p["TrDisAtr"]), int(p["TimeStop"]), int(p["TurnHold"]),
                         bool(p["LossRevOn"]), int(p["LossRevWhat"]), int(p["LossRevMax"]), bool(p["LossRevTiny"]), float(p["LossRevTinyPts"]),
                         s["tick"], s["spreadPts"] * cost_mult, s["spreadPct"] * cost_mult, s["commPts"] * cost_mult, s["commPct"] * cost_mult, 400000)
        nt, ei, xi, side, epx, xpx, pnl, reason, kind, equity = res
        return dict(n=nt, entry_i=ei, exit_i=xi, side=side, entry_px=epx, exit_px=xpx, pnl=pnl, reason=reason, kind=kind,
                    equity=equity, time=bt)


def metrics(r, t_lo=None, t_hi=None):
    """Trade metrics restricted to trades whose EXIT time is in [t_lo, t_hi).
    Max drawdown is the larger of the closed-trade drawdown and the mark-to-market
    drawdown of the bar-close equity curve inside the window (open positions count)."""
    t = r["time"]
    xt = t[r["exit_i"]] if r["n"] else np.zeros(0, np.int64)
    m = np.ones(r["n"], bool)
    if t_lo is not None: m &= xt >= t_lo
    if t_hi is not None: m &= xt < t_hi
    pnl = r["pnl"][m]
    n = len(pnl)
    e = r["equity"]
    i0 = int(np.searchsorted(t, t_lo)) if t_lo is not None else 0
    i1 = int(np.searchsorted(t, t_hi)) if t_hi is not None else len(t)
    eq_dd = 0.0
    if i1 > i0:
        base = e[i0 - 1] if i0 > 0 else 0.0
        seg = e[i0:i1]
        eq_dd = float((np.maximum(np.maximum.accumulate(seg), base) - seg).max())
    if n == 0:
        return dict(trades=0, wins=0, net=0.0, pf=0.0, win=0.0, maxdd=max(eq_dd, 0.0), avg=0.0, rf=0.0, sharpe=0.0)
    gp = pnl[pnl > 0].sum(); gl = -pnl[pnl < 0].sum()
    eq = np.cumsum(pnl)
    peak = np.maximum.accumulate(np.concatenate(([0.0], eq)))
    dd = max(float((peak[1:] - eq).max()), eq_dd)
    net = pnl.sum()
    sd = pnl.std()
    return dict(trades=int(n), wins=int((pnl > 0).sum()), net=float(net), pf=float(gp / gl) if gl > 0 else 99.0, win=float((pnl > 0).mean()),
                maxdd=float(dd), avg=float(pnl.mean()), rf=float(net / dd) if dd > 0 else 99.0,
                sharpe=float(pnl.mean() / sd * np.sqrt(n)) if sd > 0 else 0.0)


if __name__ == "__main__":
    import time, datetime as dt
    for sym, tf in (("XAUUSD", 5), ("BTCUSD", 1), ("XAUUSD", 60), ("BTCUSD", 240)):
        mk = Market(sym, start=int(dt.datetime(2025, 5, 1).timestamp()) if sym == "XAUUSD" else None)
        p = dict(DEFAULTS); p["SigTF"] = tf
        if sym == "BTCUSD": p.update(SlPts=20000.0)
        t0 = time.time(); r = mk.run(p); t1 = time.time()
        print(sym, tf, "bars", len(mk.bars(tf)[0]), "first run %.1fs" % (t1 - t0))
        t0 = time.time(); r = mk.run(p); t1 = time.time()
        print("  cached run %.3fs" % (t1 - t0), metrics(r))
        p2 = dict(p); p2["SlAtrM"] = 1.5; p2["ExitUnit"] = 1
        t0 = time.time(); r = mk.run(p2); print("  exec-only rerun %.3fs" % (time.time() - t0), metrics(r))
        p3 = dict(p); p3["RsiLen"] = 9
        t0 = time.time(); r = mk.run(p3); print("  new indicators %.3fs" % (time.time() - t0), metrics(r))
        p4 = dict(p); p4["fgfTf"] = 16388
        t0 = time.time(); r = mk.run(p4); print("  new fgf %.3fs" % (time.time() - t0), metrics(r))
        fb, fs = mk.fgf(tf, p)
        print("  fgf buy-allowed share %.2f sell-allowed %.2f" % (fb.mean(), fs.mean()))
        ev = mk.events(tf, p)
        names = "botSq topSq turnUp turnDn botCross topCross crossUp crossDn armL armS botTick topTick contUp contDn".split()
        print("  events:", {nm: int(a.sum()) for nm, a in zip(names, ev[:14])})
