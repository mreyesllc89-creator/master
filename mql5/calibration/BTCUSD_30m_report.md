# XPW calibration — BTCUSD  (1798 bars, 2026-09-04T00:30:00-04:00 .. 2026-10-11T11:00:00-04:00)
TDI port check vs exported Fast/Slow: max |diff| = 0.7813 RSI pts over 1738 bars
Account 10000, risk 1.0% per trade, spread 20.0 per unit round trip, point 0.01
Signals: BOT sq 72, TOP sq 59, turn▲ 48, turn▼ 31, BOT tick 44, TOP tick 5, CONT▲ 33, CONT▼ 29

## mode cont
  SL    700 act   400 dis    10 both  | trades  59  win  62.7%  PF  1.60  net   11.54%  maxDD  3.12% | pts: SL 70000 act 40000 dis 1000
  SL   1000 act   400 dis    10 both  | trades  57  win  66.7%  PF  1.85  net   10.08%  maxDD  2.16% | pts: SL 100000 act 40000 dis 1000
  SL    500 act   100 dis    10 both  | trades  62  win  85.5%  PF  2.08  net    9.73%  maxDD  2.07% | pts: SL 50000 act 10000 dis 1000
  SL    500 act   200 dis    10 long  | trades  33  win  75.8%  PF  2.16  net    9.12%  maxDD  1.96% | pts: SL 50000 act 20000 dis 1000
  SL   1000 act   400 dis    30 both  | trades  57  win  66.7%  PF  1.79  net    9.33%  maxDD  2.17% | pts: SL 100000 act 40000 dis 3000
  SL    700 act   100 dis    10 both  | trades  62  win  90.3%  PF  2.72  net    9.02%  maxDD  2.05% | pts: SL 70000 act 10000 dis 1000
  CONT thresholds (with SL 700 act 400 dis 10 both):
    big 0.8 pinch 1.50 after 4 | trades 101  win  61.4%  PF  1.81  net   20.67%  maxDD  2.88%
    big 0.8 pinch 1.50 after 6 | trades 106  win  61.3%  PF  1.73  net   20.12%  maxDD  3.88%
    big 0.8 pinch 1.50 after 8 | trades 106  win  61.3%  PF  1.73  net   20.12%  maxDD  3.88%
    big 1.2 pinch 1.00 after 4 | trades  41  win  68.3%  PF  1.98  net   13.09%  maxDD  2.58%
    big 1.0 pinch 1.50 after 4 | trades  72  win  65.3%  PF  1.67  net   14.56%  maxDD  3.67%

## mode cont_stop
  SL    300 act   100 dis    10 both  | trades  53  win  69.8%  PF  1.78  net   14.60%  maxDD  3.77% | pts: SL 30000 act 10000 dis 1000
  SL    700 act   400 dis    10 both  | trades  50  win  66.0%  PF  1.74  net   11.58%  maxDD  2.48% | pts: SL 70000 act 40000 dis 1000
  SL    700 act   400 dis    30 both  | trades  50  win  66.0%  PF  1.68  net   10.69%  maxDD  2.51% | pts: SL 70000 act 40000 dis 3000
  SL    300 act   100 dis    10 long  | trades  30  win  70.0%  PF  2.04  net   10.97%  maxDD  3.29% | pts: SL 30000 act 10000 dis 1000
  SL    700 act   100 dis    10 both  | trades  53  win  84.9%  PF  2.04  net    8.64%  maxDD  1.78% | pts: SL 70000 act 10000 dis 1000
  SL    700 act   800 dis    10 both  | trades  45  win  57.8%  PF  1.68  net   11.88%  maxDD  4.00% | pts: SL 70000 act 80000 dis 1000
  CONT thresholds (with SL 300 act 100 dis 10 both):
    big 0.8 pinch 1.50 after 6 | trades  97  win  69.1%  PF  1.81  net   26.54%  maxDD  5.50%
    big 0.8 pinch 1.50 after 8 | trades  97  win  69.1%  PF  1.81  net   26.54%  maxDD  5.50%
    big 0.8 pinch 1.50 after 4 | trades  92  win  69.6%  PF  1.88  net   27.24%  maxDD  6.38%
    big 0.8 pinch 2.00 after 4 | trades 107  win  64.5%  PF  1.64  net   24.56%  maxDD  6.38%
    big 0.8 pinch 2.00 after 6 | trades 113  win  63.7%  PF  1.55  net   22.54%  maxDD  5.80%

## mode turn_hold
  SL    500 act   200 dis    10 long  | trades  46  win  80.4%  PF  3.26  net   16.10%  maxDD  2.07% | pts: SL 50000 act 20000 dis 1000
  SL    300 act   200 dis    10 long  | trades  47  win  68.1%  PF  2.12  net   18.05%  maxDD  3.81% | pts: SL 30000 act 20000 dis 1000
  SL    500 act   200 dis    30 long  | trades  46  win  80.4%  PF  3.05  net   14.50%  maxDD  2.07% | pts: SL 50000 act 20000 dis 3000
  SL    500 act   200 dis    60 long  | trades  46  win  80.4%  PF  3.00  net   14.15%  maxDD  2.07% | pts: SL 50000 act 20000 dis 6000
  SL    500 act   200 dis    10 both  | trades  75  win  70.7%  PF  1.82  net   14.93%  maxDD  2.94% | pts: SL 50000 act 20000 dis 1000
  SL    300 act   200 dis    30 long  | trades  47  win  68.1%  PF  1.99  net   15.73%  maxDD  3.88% | pts: SL 30000 act 20000 dis 3000

## mode turn_cross
  SL    300 act   100 dis    10 long  | trades  71  win  71.8%  PF  1.90  net   16.36%  maxDD  2.12% | pts: SL 30000 act 10000 dis 1000
  SL    300 act   100 dis    30 long  | trades  71  win  71.8%  PF  1.70  net   12.57%  maxDD  2.12% | pts: SL 30000 act 10000 dis 3000
  SL    300 act   200 dis    10 long  | trades  69  win  52.2%  PF  1.42  net   10.73%  maxDD  3.22% | pts: SL 30000 act 20000 dis 1000
  SL    500 act   100 dis    10 long  | trades  69  win  73.9%  PF  1.66  net    8.17%  maxDD  1.53% | pts: SL 50000 act 10000 dis 1000
  SL    300 act   100 dis    60 long  | trades  71  win  71.8%  PF  1.44  net    7.80%  maxDD  2.12% | pts: SL 30000 act 10000 dis 6000
  SL    500 act   100 dis    30 long  | trades  69  win  73.9%  PF  1.49  net    6.03%  maxDD  1.76% | pts: SL 50000 act 10000 dis 3000

## mode turn_predict
  SL    300 act   400 dis    10 long  | trades  69  win  53.6%  PF  1.84  net   30.57%  maxDD  7.23% | pts: SL 30000 act 40000 dis 1000
  SL    300 act   100 dis    10 long  | trades  87  win  72.4%  PF  1.88  net   23.96%  maxDD  2.95% | pts: SL 30000 act 10000 dis 1000
  SL    300 act   400 dis    30 long  | trades  69  win  53.6%  PF  1.78  net   27.96%  maxDD  7.23% | pts: SL 30000 act 40000 dis 3000
  SL    300 act   100 dis    30 long  | trades  82  win  73.2%  PF  1.83  net   20.82%  maxDD  3.14% | pts: SL 30000 act 10000 dis 3000
  SL    300 act   400 dis    60 long  | trades  69  win  53.6%  PF  1.73  net   26.35%  maxDD  7.23% | pts: SL 30000 act 40000 dis 6000
  SL    300 act   200 dis    10 long  | trades  75  win  62.7%  PF  1.65  net   20.58%  maxDD  4.08% | pts: SL 30000 act 20000 dis 1000

## mode square
  SL    300 act   100 dis    10 long  | trades  71  win  74.6%  PF  2.12  net   20.58%  maxDD  3.90% | pts: SL 30000 act 10000 dis 1000
  SL    700 act   200 dis    10 long  | trades  65  win  83.1%  PF  3.25  net   15.37%  maxDD  1.14% | pts: SL 70000 act 20000 dis 1000
  SL    300 act   200 dis    10 long  | trades  70  win  65.7%  PF  1.95  net   21.86%  maxDD  5.85% | pts: SL 30000 act 20000 dis 1000
  SL    500 act   200 dis    10 long  | trades  68  win  76.5%  PF  2.29  net   17.16%  maxDD  2.76% | pts: SL 50000 act 20000 dis 1000
  SL    300 act   100 dis    30 long  | trades  71  win  74.6%  PF  2.01  net   18.31%  maxDD  3.96% | pts: SL 30000 act 10000 dis 3000
  SL    700 act   200 dis    30 long  | trades  65  win  83.1%  PF  3.06  net   14.01%  maxDD  1.14% | pts: SL 70000 act 20000 dis 3000

## mode tick
  SL    500 act   100 dis    10 both  | trades  48  win  83.3%  PF  2.27  net   11.09%  maxDD  2.87% | pts: SL 50000 act 10000 dis 1000
  SL    500 act   100 dis    10 long  | trades  43  win  86.0%  PF  2.64  net   10.56%  maxDD  2.87% | pts: SL 50000 act 10000 dis 1000
  SL    500 act   200 dis    10 both  | trades  47  win  74.5%  PF  1.79  net   10.30%  maxDD  2.75% | pts: SL 50000 act 20000 dis 1000
  SL    500 act   200 dis    10 long  | trades  42  win  76.2%  PF  1.88  net    9.48%  maxDD  2.75% | pts: SL 50000 act 20000 dis 1000
  SL    500 act   400 dis    10 both  | trades  47  win  63.8%  PF  1.55  net   10.06%  maxDD  3.27% | pts: SL 50000 act 40000 dis 1000
  SL    500 act   100 dis    30 both  | trades  47  win  83.0%  PF  2.10  net    9.49%  maxDD  2.91% | pts: SL 50000 act 10000 dis 3000

## best per mode
  turn_predict SL 300 act 400 dis 10 long  | trades  69  win  53.6%  PF  1.84  net   30.57%  maxDD  7.23%
  square       SL 300 act 100 dis 10 long  | trades  71  win  74.6%  PF  2.12  net   20.58%  maxDD  3.90%
  turn_cross   SL 300 act 100 dis 10 long  | trades  71  win  71.8%  PF  1.90  net   16.36%  maxDD  2.12%
  turn_hold    SL 500 act 200 dis 10 long  | trades  46  win  80.4%  PF  3.26  net   16.10%  maxDD  2.07%
  cont_stop    SL 300 act 100 dis 10 both  | trades  53  win  69.8%  PF  1.78  net   14.60%  maxDD  3.77%
  cont         SL 700 act 400 dis 10 both  | trades  59  win  62.7%  PF  1.60  net   11.54%  maxDD  3.12%
  tick         SL 500 act 100 dis 10 both  | trades  48  win  83.3%  PF  2.27  net   11.09%  maxDD  2.87%
