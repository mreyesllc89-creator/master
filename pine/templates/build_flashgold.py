import sys
tpl = open("/home/user/master/pine/templates/FlashGold_v5_template.pine").read()
common = dict(Z4="480", Z5="1", Z6="2", Z5U="false", Z6U="false")
builds = {
 "XAUUSD": dict(SYMBOL="XAUUSD", QTY="10", COMM="0.13", COMM_NOTE="USD per oz per side: half of a 2.5 pip ($0.25) spread + $0.6/lot commission (VT Markets)", SLIP="5", SLIP_NOTE="mintick 0.01 -> $0.05/oz",
    SPREAD="25.0", EDIST="50.0", HOLDFAV="5.0", BURST="172.0", SLPTS="150", TPPTS="300", TRAILACT="150", TRAILDST="100", QTY_UNIT=" = oz, 100 = 1 lot", MAXQTY="50", QTYSTEP="1",
    POINTS_NOTE="Gold: mintick 0.01, so 25 pts = $0.25 = 2.5 pips; the indicator's own point defaults are kept for the Points unit.",
    ANYCOMBO="false", BURST_ATR="0.5", EDIST_ATR="0.25", HOLD="0", MINALIGN="2", PARENT="60",
    Z1="60", Z1U="true", Z2="120", Z2U="true", Z3="240", Z3U="true", Z4U="false",
    SL_ATR="2.0", TP_R="2.0", TRAIL="true", EXITOPP="false", MTF1="15", MTF2="30", MTF3="240", MTF4="10", MTF3U="false", MTF4U="false", MTFAGREE="2",
    CAL_TF="60m", CAL_DATA="OANDA:XAUUSD 10m to 60m exports (2 to 16 weeks)",
    CAL_STATS="60m: 87 trades, 76% win, +541 per oz, PF 1.93, halves 2.09 / 1.82, max DD 107 per oz. The same settings are positive on 15m (PF 1.23) and 30m (PF 1.34); 10m is flat and 5m loses. Zones = chart, 2x, 4x with 2 aligned."),
 "SPX500": dict(SYMBOL="SPX500", QTY="1", COMM="0.25", COMM_NOTE="index points per contract per side: half of a 0.5 point spread (placeholder until the broker spec is confirmed)", SLIP="10", SLIP_NOTE="mintick 0.01 -> 0.10 index points",
    SPREAD="50.0", EDIST="50.0", HOLDFAV="10.0", BURST="150.0", SLPTS="300", TPPTS="600", TRAILACT="300", TRAILDST="200", QTY_UNIT=", $1 per point each", MAXQTY="10", QTYSTEP="1",
    POINTS_NOTE="SPX: mintick 0.01, so 100 pts = 1 index point.",
    ANYCOMBO="false", BURST_ATR="0.5", EDIST_ATR="0.25", HOLD="3", MINALIGN="1", PARENT="15",
    Z1="15", Z1U="true", Z2="30", Z2U="false", Z3="60", Z3U="false", Z4U="false",
    SL_ATR="3.0", TP_R="1.5", TRAIL="true", EXITOPP="false", MTF1="30", MTF2="60", MTF3="240", MTF4="5", MTF3U="true", MTF4U="false", MTFAGREE="2",
    CAL_TF="15m", CAL_DATA="SPCFD:SPX cash-session exports, 1m to 60m (2.5 to 18 months)",
    CAL_STATS="15m: 46 trades, 83% win, +344 per contract, PF 1.95, halves 1.79 / 2.17, max DD 133. Same settings on 60m: 37 trades, 92% win, +1,282, PF 5.4 (few trades); on 1m: 426 trades, 69% win, PF 1.13. Zones = the chart only (parent direction), entry hold 3 bars."),
 "BTCUSD": dict(SYMBOL="BTCUSD", QTY="0.1", COMM="10.5", COMM_NOTE="USD per BTC per side: half of the VT Markets 2100-point ($21) spread, no commission", SLIP="500", SLIP_NOTE="mintick 0.01 -> $5",
    SPREAD="2100.0", EDIST="1000.0", HOLDFAV="200.0", BURST="5000.0", SLPTS="15000", TPPTS="30000", TRAILACT="15000", TRAILDST="10000", QTY_UNIT=" = BTC", MAXQTY="2", QTYSTEP="0.01",
    POINTS_NOTE="BTC: mintick 0.01, so 100 pts = $1.",
    ANYCOMBO="false", BURST_ATR="0.25", EDIST_ATR="0.25", HOLD="0", MINALIGN="3", PARENT="60",
    Z1="60", Z1U="true", Z2="120", Z2U="true", Z3="240", Z3U="true", Z4U="true",
    SL_ATR="3.0", TP_R="1.0", TRAIL="true", EXITOPP="false", MTF1="240", MTF2="15", MTF3="30", MTF4="D", MTF3U="true", MTF4U="false", MTFAGREE="2",
    CAL_TF="60m", CAL_DATA="CRYPTO:BTCUSD 15m to 60m and MEXC:BTCUSDT 5m exports (1 to 4 weeks)",
    CAL_STATS="60m: 56 trades, 75% win, +9,850 per BTC, PF 1.92, halves 1.47 / 2.48, max DD 2,096. On 15m use burst 0.5 ATR instead: 52 trades, 83% win, +3,688, PF 1.82. 5m loses at every setting. Zones = chart, 2x, 4x, 8x with 3 aligned."),
}
for name, d in builds.items():
    out = tpl
    for k, v in (common | d).items(): out = out.replace("{{" + k + "}}", v)
    assert "{{" not in out, [l for l in out.splitlines() if "{{" in l][:3]
    open(f"/home/user/master/pine/FlashGold_v5_Strategy_{name}.pine", "w").write(out); print(name, len(out))
