import sweep
ind_grid = list(sweep.grid(
    chart_tf=["M5", "M15", "M30", "H1"], er_period=[10, 20, 30], enter=[0.30, 0.42, 0.55], exit=[0.10, 0.18, 0.28],
    atr_period=[10, 14, 20], atr_mult=[2.0, 3.0, 4.0, 5.0], min_dwell=[2, 6, 10], shock_mult=[2.5, 3.0, 5.0]))
