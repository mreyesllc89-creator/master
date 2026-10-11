# XPW calibration — BTCUSD  (1798 bars, 2026-09-04T00:30:00-04:00 .. 2026-10-11T11:00:00-04:00)
TDI port check vs exported Fast/Slow: max |diff| = 0.7813 RSI pts over 1738 bars
Account 10000, risk 1.0% per trade, spread 20.0 per unit round trip, point 0.01
Signals: BOT sq 72, TOP sq 59, turn▲ 48, turn▼ 31, BOT tick 44, TOP tick 5, CONT▲ 33, CONT▼ 29

## mode cont
  SL   1500 act   400 dis    10 both  | trades  56  win  62.5%  PF  1.44  net    3.17%  maxDD  1.56% | pts: SL 150000 act 40000 dis 1000
  SL   1500 act   400 dis    30 both  | trades  56  win  62.5%  PF  1.43  net    3.12%  maxDD  1.58% | pts: SL 150000 act 40000 dis 3000
  SL   1500 act   400 dis    60 both  | trades  56  win  62.5%  PF  1.42  net    3.04%  maxDD  1.62% | pts: SL 150000 act 40000 dis 6000
  SL   1000 act   400 dis    10 both  | trades  57  win  61.4%  PF  1.33  net    3.83%  maxDD  2.18% | pts: SL 100000 act 40000 dis 1000
  SL   1000 act   400 dis    30 both  | trades  57  win  61.4%  PF  1.32  net    3.76%  maxDD  2.18% | pts: SL 100000 act 40000 dis 3000
  SL   1000 act   800 dis    10 long  | trades  26  win  61.5%  PF  1.47  net    3.03%  maxDD  1.73% | pts: SL 100000 act 80000 dis 1000
  CONT thresholds (with SL 1500 act 400 dis 10 both):
    big 1.2 pinch 1.00 after 4 | trades  40  win  65.0%  PF  2.03  net    4.43%  maxDD  1.01%
    big 1.2 pinch 0.75 after 4 | trades  31  win  74.2%  PF  2.65  net    4.15%  maxDD  1.01%
    big 1.2 pinch 1.00 after 6 | trades  41  win  63.4%  PF  1.81  net    3.90%  maxDD  1.01%
    big 1.2 pinch 1.00 after 8 | trades  41  win  63.4%  PF  1.81  net    3.90%  maxDD  1.01%
    big 1.2 pinch 0.75 after 6 | trades  32  win  71.9%  PF  2.20  net    3.62%  maxDD  1.01%

## mode cont_stop
  SL   1500 act   800 dis    10 both  | trades  42  win  61.9%  PF  1.31  net    2.52%  maxDD  1.71% | pts: SL 150000 act 80000 dis 1000
  SL   1500 act   800 dis    30 both  | trades  42  win  61.9%  PF  1.31  net    2.50%  maxDD  1.71% | pts: SL 150000 act 80000 dis 3000
  SL   1500 act   800 dis    60 both  | trades  42  win  61.9%  PF  1.30  net    2.46%  maxDD  1.71% | pts: SL 150000 act 80000 dis 6000
  SL    700 act   800 dis    10 both  | trades  45  win  57.8%  PF  1.34  net    5.81%  maxDD  4.02% | pts: SL 70000 act 80000 dis 1000
  SL   1500 act   800 dis   120 both  | trades  42  win  61.9%  PF  1.28  net    2.30%  maxDD  1.71% | pts: SL 150000 act 80000 dis 12000
  SL    700 act   800 dis    30 both  | trades  45  win  57.8%  PF  1.34  net    5.77%  maxDD  4.03% | pts: SL 70000 act 80000 dis 3000
  CONT thresholds (with SL 1500 act 800 dis 10 both):
    big 1.0 pinch 1.50 after 6 | trades  52  win  61.5%  PF  1.61  net    5.23%  maxDD  1.71%
    big 1.0 pinch 1.50 after 8 | trades  52  win  61.5%  PF  1.61  net    5.23%  maxDD  1.71%
    big 1.5 pinch 1.50 after 4 | trades  18  win  66.7%  PF  2.30  net    3.75%  maxDD  1.01%
    big 1.5 pinch 1.50 after 6 | trades  18  win  66.7%  PF  2.30  net    3.75%  maxDD  1.01%
    big 1.5 pinch 1.50 after 8 | trades  18  win  66.7%  PF  2.30  net    3.75%  maxDD  1.01%

## mode turn_hold
  SL    500 act   200 dis    60 long  | trades  46  win  71.7%  PF  1.98  net    7.50%  maxDD  2.07% | pts: SL 50000 act 20000 dis 6000
  SL    500 act   200 dis   120 long  | trades  45  win  71.1%  PF  1.87  net    6.64%  maxDD  2.07% | pts: SL 50000 act 20000 dis 12000
  SL    500 act   200 dis    10 long  | trades  46  win  71.7%  PF  1.83  net    6.30%  maxDD  2.07% | pts: SL 50000 act 20000 dis 1000
  SL    500 act   200 dis    30 long  | trades  46  win  71.7%  PF  1.81  net    6.19%  maxDD  2.07% | pts: SL 50000 act 20000 dis 3000
  SL    700 act   200 dis    60 long  | trades  45  win  73.3%  PF  1.88  net    4.90%  maxDD  1.51% | pts: SL 70000 act 20000 dis 6000
  SL    300 act   200 dis    60 long  | trades  47  win  66.0%  PF  1.58  net    8.95%  maxDD  4.22% | pts: SL 30000 act 20000 dis 6000

## mode turn_cross
  SL   1000 act   200 dis   120 long  | trades  61  win  55.7%  PF  1.01  net    0.04%  maxDD  1.98% | pts: SL 100000 act 20000 dis 12000
  SL   1000 act   200 dis    60 long  | trades  61  win  55.7%  PF  0.99  net   -0.07%  maxDD  1.98% | pts: SL 100000 act 20000 dis 6000
  SL   1000 act   200 dis    10 long  | trades  61  win  55.7%  PF  0.98  net   -0.11%  maxDD  1.98% | pts: SL 100000 act 20000 dis 1000
  SL   1500 act   200 dis   120 long  | trades  61  win  55.7%  PF  0.87  net   -0.64%  maxDD  1.65% | pts: SL 150000 act 20000 dis 12000
  SL   1000 act   200 dis    30 long  | trades  61  win  55.7%  PF  0.97  net   -0.20%  maxDD  1.98% | pts: SL 100000 act 20000 dis 3000
  SL   1500 act   200 dis    60 long  | trades  61  win  55.7%  PF  0.86  net   -0.71%  maxDD  1.65% | pts: SL 150000 act 20000 dis 6000

## mode turn_predict
  SL   1000 act   400 dis    10 long  | trades  41  win  82.9%  PF  1.93  net    5.84%  maxDD  2.31% | pts: SL 100000 act 40000 dis 1000
  SL    700 act   400 dis    10 long  | trades  47  win  76.6%  PF  1.72  net    7.58%  maxDD  3.51% | pts: SL 70000 act 40000 dis 1000
  SL   1000 act   400 dis    30 long  | trades  41  win  82.9%  PF  1.92  net    5.77%  maxDD  2.31% | pts: SL 100000 act 40000 dis 3000
  SL    700 act   400 dis    30 long  | trades  47  win  76.6%  PF  1.71  net    7.48%  maxDD  3.51% | pts: SL 70000 act 40000 dis 3000
  SL   1000 act   400 dis    60 long  | trades  41  win  82.9%  PF  1.90  net    5.64%  maxDD  2.31% | pts: SL 100000 act 40000 dis 6000
  SL    700 act   400 dis    60 long  | trades  47  win  76.6%  PF  1.69  net    7.28%  maxDD  3.51% | pts: SL 70000 act 40000 dis 6000

## mode square
  SL    500 act   400 dis    10 long  | trades  66  win  71.2%  PF  1.69  net   10.49%  maxDD  3.47% | pts: SL 50000 act 40000 dis 1000
  SL    500 act   400 dis    30 long  | trades  66  win  71.2%  PF  1.68  net   10.34%  maxDD  3.47% | pts: SL 50000 act 40000 dis 3000
  SL    700 act   200 dis    10 long  | trades  65  win  80.0%  PF  2.00  net    7.35%  maxDD  1.68% | pts: SL 70000 act 20000 dis 1000
  SL    500 act   400 dis    60 long  | trades  66  win  71.2%  PF  1.65  net    9.99%  maxDD  3.47% | pts: SL 50000 act 40000 dis 6000
  SL    700 act   200 dis    30 long  | trades  65  win  80.0%  PF  1.99  net    7.24%  maxDD  1.68% | pts: SL 70000 act 20000 dis 3000
  SL    700 act   200 dis    60 long  | trades  65  win  80.0%  PF  1.95  net    6.95%  maxDD  1.68% | pts: SL 70000 act 20000 dis 6000

## mode tick
  SL   1500 act   400 dis    10 both  | trades  37  win  86.5%  PF  1.79  net    3.37%  maxDD  2.02% | pts: SL 150000 act 40000 dis 1000
  SL   1500 act   400 dis   120 both  | trades  37  win  86.5%  PF  1.78  net    3.32%  maxDD  2.02% | pts: SL 150000 act 40000 dis 12000
  SL   1500 act   400 dis    30 both  | trades  37  win  86.5%  PF  1.78  net    3.30%  maxDD  2.02% | pts: SL 150000 act 40000 dis 3000
  SL   1500 act   400 dis    60 both  | trades  37  win  86.5%  PF  1.76  net    3.24%  maxDD  2.02% | pts: SL 150000 act 40000 dis 6000
  SL   1500 act   100 dis    10 both  | trades  44  win  77.3%  PF  1.53  net    1.55%  maxDD  1.01% | pts: SL 150000 act 10000 dis 1000
  SL   1500 act   100 dis    30 both  | trades  44  win  77.3%  PF  1.52  net    1.54%  maxDD  1.01% | pts: SL 150000 act 10000 dis 3000

## best per mode
  square       SL 500 act 400 dis 10 long  | trades  66  win  71.2%  PF  1.69  net   10.49%  maxDD  3.47%
  turn_hold    SL 500 act 200 dis 60 long  | trades  46  win  71.7%  PF  1.98  net    7.50%  maxDD  2.07%
  turn_predict SL 1000 act 400 dis 10 long  | trades  41  win  82.9%  PF  1.93  net    5.84%  maxDD  2.31%
  cont         SL 1500 act 400 dis 10 both  | trades  56  win  62.5%  PF  1.44  net    3.17%  maxDD  1.56%
  tick         SL 1500 act 400 dis 10 both  | trades  37  win  86.5%  PF  1.79  net    3.37%  maxDD  2.02%
  cont_stop    SL 1500 act 800 dis 10 both  | trades  42  win  61.9%  PF  1.31  net    2.52%  maxDD  1.71%
  turn_cross   SL 1000 act 200 dis 120 long  | trades  61  win  55.7%  PF  1.01  net    0.04%  maxDD  1.98%
