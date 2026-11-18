#!/usr/bin/env python3
"""
The page (files/index.html) of the "Loma 2026 Results" dashboard artifact, drawn from its three data files
(make_2026_page_data.py). The grids' fixed labels are written here; every number is drawn by the page's script from
the data, and the fixed references of the study (a profit factor of 1.3, 100 trades, 30 trades) are constants of the
script, drawn wherever they show. Usage (repository root): python3 research/make_2026_page.py
-> research/results/tick/page2026/index.html
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "research", "results", "tick", "page2026", "index.html")
TFS = ["M2", "M3", "M5", "M10", "M15", "M30"]
SYSTEMS = [("R", "Risk multiples (EA default)"), ("atr", "ATR at entry"), ("percent", "Percent of price"), ("profitlock", "Profit lock"),
           ("step", "Stepped"), ("chandelier", "Chandelier"), ("candles", "Candle lows / highs"), ("ema", "EMA"), ("sma", "SMA"),
           ("psar", "Parabolic SAR"), ("bollinger", "Bollinger band"), ("htfcandle", "Higher-timeframe candle"), ("pivots", "Swing pivots"),
           ("hump", "Hump structure")]
MODE = {"R": 0, "atr": 1, "percent": 2, "profitlock": 3, "step": 4, "chandelier": 5, "candles": 6, "ema": 7, "sma": 8, "psar": 9,
        "bollinger": 10, "htfcandle": 11, "pivots": 12, "hump": 13}
K = {"bar": '<span data-draw="k" data-k="bar">—</span>', "min": '<span data-draw="k" data-k="min">—</span>',
     "thin": '<span data-draw="k" data-k="thin">—</span>'}


def S(field):
    return f'<b data-draw="sum" data-source="summary2026" data-field="{field}" data-row="0">—</b>'


def grid(sym, name):
    head = "".join(f'<th scope="col">{tf}</th>' for tf in TFS)
    rows = []
    for k, label in SYSTEMS:
        cells = "".join(f'<td class="l26-hc" data-draw="hc" data-sym="{sym}" data-tf="{tf}" data-kind="{k}" tabindex="0"></td>' for tf in TFS)
        rows.append(f'<tr><th scope="row"><span class="l26-sys">{label}</span> <span class="l26-mode">{MODE[k]}</span></th>{cells}</tr>')
    return (f'<figure class="l26-grid" id="grid-{name.lower()}" data-source="cells2026"><figcaption>{name}</figcaption><div class="l26-scroll l26-heatwrap">'
            f'<table class="l26-heat" aria-label="{name}: profit factor of every trailing system on every timeframe, 16 May to 13 Nov 2026">'
            f'<thead><tr><th scope="col">Trailing (TrailMode)</th>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div></figure>')


PAGE = r'''<meta name="dash-one-writer">
<style>
.l26 { display: grid; gap: var(--cds-gap-xl); color: var(--color-fg); font-family: var(--font-anthropic-sans); min-width: 0; }
.l26 * { box-sizing: border-box; }
.l26-head { display: grid; gap: var(--cds-gap-sm); max-width: 78ch; }
.l26-title { font-family: var(--font-anthropic-serif); font-weight: 400; font-size: var(--cds-font-size-title); line-height: 1.15; margin: 0; text-wrap: balance; }
.l26-sub { color: var(--color-fg-muted); margin: 0; line-height: 1.5; }
.l26-take { margin: 0; font-size: var(--cds-font-size-heading); line-height: 1.45; text-wrap: pretty; }
.l26-take b, .l26-p b { font-weight: var(--cds-font-weight-medium); }
.l26-take-warn { margin: 0; line-height: 1.5; max-width: 78ch; }
.l26-sec { display: grid; gap: var(--cds-gap-md); min-width: 0; }
.l26-sec > h2 { font-size: var(--cds-font-size-heading); font-weight: var(--cds-font-weight-medium); margin: 0; text-wrap: balance; }
.l26-p { margin: 0; max-width: 78ch; line-height: 1.5; }
.l26-note { color: var(--color-fg-muted); font-size: var(--cds-font-size-caption); margin: 0; max-width: 86ch; line-height: 1.5; }
.l26-scroll { overflow-x: auto; min-width: 0; }
.l26-table { border-collapse: collapse; font-variant-numeric: tabular-nums; width: 100%; }
.l26-table th, .l26-table td { padding: 7px 10px; border-bottom: 1px solid var(--color-border-line); text-align: right; white-space: nowrap; }
.l26-table th:first-child, .l26-table td:first-child { text-align: left; }
.l26-table thead th { color: var(--color-fg-muted); font-weight: var(--cds-font-weight-medium); font-size: var(--cds-font-size-caption); vertical-align: bottom; white-space: normal; min-width: 4.5em; }
.l26-table thead th:first-child { min-width: 12em; }
.l26-table tbody th { font-weight: 400; text-align: left; }
.l26-table tbody.l26-group th { font-weight: var(--cds-font-weight-medium); color: var(--color-fg-muted); font-size: var(--cds-font-size-caption); padding-top: 16px; }
.l26-yes { color: var(--color-fg); }
.l26-dim { color: var(--color-fg-muted); }
.l26-grids { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(360px, 100%), 1fr)); gap: var(--cds-gap-lg); min-width: 0; }
.l26-grid { margin: 0; display: grid; gap: var(--cds-gap-sm); min-width: 0; }
.l26-grid figcaption { font-weight: var(--cds-font-weight-medium); }
.l26-heatwrap { padding-block: 4px; }
.l26-heat { border-collapse: separate; border-spacing: 2px; font-variant-numeric: tabular-nums; }
.l26-heat thead th { color: var(--color-fg-muted); font-size: var(--cds-font-size-caption); font-weight: var(--cds-font-weight-medium); padding: 2px 4px; text-align: center; }
.l26-heat thead th:first-child { text-align: left; }
.l26-heat tbody th { font-weight: 400; font-size: var(--cds-font-size-caption); text-align: left; padding-right: 8px; white-space: nowrap; }
.l26-mode { color: var(--color-fg-muted); }
.l26-hc { position: relative; width: 52px; min-width: 52px; height: 42px; text-align: center; vertical-align: middle; border-radius: 4px; background: var(--color-panel); line-height: 1.1; outline: none; }
.l26-hc.l26-gain { background: color-mix(in srgb, var(--color-ok) var(--mix, 0%), var(--color-panel)); }
.l26-hc.l26-loss { background: color-mix(in srgb, var(--color-bad) var(--mix, 0%), var(--color-panel)); }
.l26-hc.l26-few .l26-v, .l26-hc.l26-few .l26-n { opacity: 0.6; }
.l26-hc.l26-best { box-shadow: inset 0 0 0 2px var(--color-fg); }
.l26-hc:focus-visible { box-shadow: inset 0 0 0 2px var(--color-fg), 0 0 0 2px var(--color-bg); }
.l26-v { display: block; font-size: var(--cds-font-size-body); }
.l26-hc.l26-reached .l26-v { font-weight: var(--cds-font-weight-medium); }
.l26-n { display: block; font-size: var(--cds-font-size-caption); color: var(--color-fg-muted); }
.l26-none { color: var(--color-fg-muted); font-size: var(--cds-font-size-caption); }
.l26-tip { position: absolute; z-index: 3; left: 50%; bottom: calc(100% + 6px); transform: translateX(-50%); width: max-content; max-width: 230px; text-align: left; white-space: normal;
  background: var(--cds-surface-popover); border: 1px solid var(--cds-border); box-shadow: var(--cds-shadow-popover); border-radius: var(--cds-radius);
  padding: 6px 8px; font-size: var(--cds-font-size-caption); color: var(--color-fg); pointer-events: none; display: none; }
.l26-tip b { display: block; font-weight: var(--cds-font-weight-medium); }
.l26-tip span { display: block; color: var(--cds-text-secondary); }
.l26-hc:hover .l26-tip, .l26-hc:focus .l26-tip { display: block; }
.l26-heat tbody tr:nth-child(-n+3) .l26-tip { bottom: auto; top: calc(100% + 6px); }
.l26-heat td:nth-last-child(-n+2) .l26-tip { left: auto; right: 0; transform: none; }
.l26-heat td:nth-child(2) .l26-tip { left: 0; transform: none; }
.l26-legend { display: flex; flex-wrap: wrap; gap: var(--cds-gap-sm) var(--cds-gap-lg); align-items: center; font-size: var(--cds-font-size-caption); color: var(--color-fg-muted); }
.l26-key { display: inline-flex; align-items: center; gap: 6px; }
.l26-key b { color: var(--color-fg); font-weight: var(--cds-font-weight-medium); }
.l26-sw { width: 18px; height: 14px; border-radius: 3px; display: inline-block; background: var(--color-panel); }
.l26-sw-loss { background: color-mix(in srgb, var(--color-bad) 45%, var(--color-panel)); }
.l26-sw-even { background: var(--color-panel); border: 1px solid var(--color-border-line); }
.l26-sw-gain { background: color-mix(in srgb, var(--color-ok) 45%, var(--color-panel)); }
.l26-sw-pale { background: color-mix(in srgb, var(--color-ok) 16%, var(--color-panel)); }
.l26-sw-best { box-shadow: inset 0 0 0 2px var(--color-fg); }
.l26-mt td.l26-mc { min-width: 4.2em; }
.l26-mt td.l26-mc.l26-gain { background: color-mix(in srgb, var(--color-ok) var(--mix, 0%), transparent); }
.l26-mt td.l26-mc.l26-loss { background: color-mix(in srgb, var(--color-bad) var(--mix, 0%), transparent); }
.l26-mt td.l26-total { font-weight: var(--cds-font-weight-medium); }
.l26-ctl { display: flex; flex-wrap: wrap; gap: var(--cds-gap-sm); align-items: center; }
.l26-ctl label { color: var(--color-fg-muted); font-size: var(--cds-font-size-caption); }
.l26-chart { position: relative; min-height: 300px; min-width: 0; }
.l26-chart svg { display: block; width: 100%; height: auto; overflow: visible; }
.l26-chart .tick text { fill: var(--cds-text-secondary); font-size: var(--cds-font-size-caption); font-family: var(--font-anthropic-sans); }
.l26-chart .tick line { stroke: var(--cds-chart-grid); }
.l26-chart .domain { stroke: var(--cds-chart-axis); }
.l26-ctip { position: absolute; z-index: 3; pointer-events: none; background: var(--cds-surface-popover); border: 1px solid var(--cds-border); box-shadow: var(--cds-shadow-popover);
  border-radius: var(--cds-radius); padding: 6px 8px; font-size: var(--cds-font-size-caption); font-variant-numeric: tabular-nums; white-space: nowrap; }
.l26-ctip b { display: block; font-size: var(--cds-font-size-body); font-weight: var(--cds-font-weight-medium); }
.l26-ctip span { display: block; color: var(--cds-text-secondary); }
.l26-fail { color: var(--color-fg-muted); font-size: var(--cds-font-size-caption); padding: var(--cds-pad-md) 0; }
.l26-caveat { display: grid; gap: var(--cds-gap-sm); background: var(--color-panel); border: 1px solid var(--color-border-line); border-radius: var(--cds-radius); padding: var(--cds-pad-lg); min-width: 0; }
.l26-caveat h3 { margin: var(--cds-gap-sm) 0 0; font-size: var(--cds-font-size-body); font-weight: var(--cds-font-weight-medium); }
.l26-defs { max-width: 86ch; }
.l26-defs summary { cursor: pointer; font-weight: var(--cds-font-weight-medium); }
.l26-defs dl { display: grid; grid-template-columns: max-content 1fr; gap: 6px 16px; margin: var(--cds-gap-sm) 0 0; font-size: var(--cds-font-size-caption); }
.l26-defs dt { font-weight: var(--cds-font-weight-medium); }
.l26-defs dd { margin: 0; color: var(--color-fg-muted); line-height: 1.5; }
@media (max-width: 520px) { .l26-defs dl { grid-template-columns: 1fr; } .l26-defs dd { margin-bottom: 6px; } }
</style>

<div class="l26">
  <header class="l26-head" id="top">
    <h1 class="l26-title">Loma 2026 Results</h1>
    <p class="l26-sub">Every trailing system of the Loma EA (v1.35) on every timeframe from M2 to M30 where it had setups, replayed with the EA's own rules on 16 May – 13 Nov 2026, the months its setups never saw. Gold: every Dukascopy tick at VT Markets' costs. BTC: Binance one-second prices with a $10 spread, no commission.</p>
    <p class="l26-take" id="takeaway">''' + S("reached") + ''' of the ''' + S("eligible") + ''' combinations of symbol, timeframe and trailing system with ''' + K["min"] + ''' or more trades in 2026 reached a profit factor of ''' + K["bar"] + ''': ''' + S("reached_gold") + ''' of ''' + S("eligible_gold") + ''' on gold and ''' + S("reached_btc") + ''' of ''' + S("eligible_btc") + ''' on BTC. The highest was ''' + S("best_label") + ''': ''' + S("best_pf") + ''' on ''' + S("best_trades") + ''' trades, with a gain in ''' + S("best_months_up") + ''' of the ''' + S("best_months_traded") + ''' months it traded.</p>
    <p class="l26-take-warn" id="takeaway-check">On the earlier data, ''' + S("held_before") + ''' of these ''' + S("reached") + ''' reached ''' + K["bar"] + ''' in every period (highest ''' + S("highest_before") + '''), and ''' + S("lost_before") + ''' lost money in at least one: their 2026 figures are what they were picked out on, not proof.</p>
  </header>

  <section class="l26-sec" id="reached">
    <h2>Reached a profit factor of ''' + K["bar"] + ''' on ''' + K["min"] + '''+ trades</h2>
    <div class="l26-scroll">
      <table class="l26-table" data-source="cells2026" data-row-key="combo" aria-label="Combinations that reached the profit factor bar on the minimum number of trades in 2026">
        <thead><tr>
          <th data-field="label">Combination</th><th data-field="setups">Setups</th><th data-field="trades">Trades</th><th data-field="pf">Profit factor</th>
          <th data-field="net_r">Net R</th><th data-field="win_pct">Win %</th><th data-field="max_dd_r">Largest drawdown (R)</th><th data-field="months_up">Months with a gain</th>
          <th data-field="stress_pf">Stressed PF</th><th data-field="one_minute_pf">One-minute engine PF</th><th data-field="chosen">Best of its timeframe</th><th data-field="t15">In Loma_T15</th>
        </tr></thead>
        <tbody data-draw="reached"></tbody>
      </table>
    </div>
    <p class="l26-note">Every row is one symbol, timeframe and trailing system, with all the setups picked for it trading together (each preset is one setup). <i>Best of its timeframe</i>: in Loma_BestTrailing_v1_35.zip. <i>In Loma_T15</i>: also one of the 15 Loma_T15 trailing combinations in Loma_XAUUSD_v1_35.zip and Loma_BTCUSD_v1_35.zip, which the one-minute backtest picked on these same 2026 months, so a yes is not a second test.</p>
  </section>

  <section class="l26-sec" id="grid">
    <h2>Every trailing system on every timeframe from M2 to M30</h2>
    <p class="l26-p">Profit factor in the 2026 months, trades below it. No setup of the EA's trailing systems passed the calibration on ''' + S("no_setup_tfs") + ''', for gold or BTC.</p>
    <div class="l26-legend" aria-hidden="true">
      <span class="l26-key"><span class="l26-sw l26-sw-loss"></span>Lost money (under 1.0)</span>
      <span class="l26-key"><span class="l26-sw l26-sw-even"></span>About even</span>
      <span class="l26-key"><span class="l26-sw l26-sw-gain"></span>Made money (deeper the higher the profit factor, darkest from 1.8)</span>
      <span class="l26-key"><span class="l26-sw l26-sw-pale"></span><span>Pale, numbers faded: under ''' + K["min"] + ''' trades</span></span>
      <span class="l26-key"><span><b>Bold</b>: ''' + K["bar"] + ''' or more on ''' + K["min"] + '''+ trades</span></span>
      <span class="l26-key"><span class="l26-sw l26-sw-best"></span>Best of its timeframe (in the zip)</span>
      <span class="l26-key">·: no setup</span>
    </div>
    <div class="l26-grids">
''' + grid("XAUUSD", "Gold") + "\n" + grid("BTCUSD", "BTC") + r'''
    </div>
  </section>

  <section class="l26-sec" id="months">
    <h2>Month by month, net result in R</h2>
    <div class="l26-scroll">
      <table class="l26-table l26-mt" aria-label="Net result in R by month in 2026">
        <thead><tr><th scope="col">Combination</th><th scope="col">May (from 16th)</th><th scope="col">Jun</th><th scope="col">Jul</th><th scope="col">Aug</th><th scope="col">Sep</th><th scope="col">Oct</th><th scope="col">Nov (to 13th)</th><th scope="col">2026</th></tr></thead>
        <tbody data-draw="months"></tbody>
        <tbody class="l26-group"><tr><th scope="rowgroup" colspan="9">The zip's other sets</th></tr></tbody>
        <tbody data-draw="months2"></tbody>
      </table>
    </div>
    <p class="l26-note">First the combinations that reached a profit factor of ''' + K["bar"] + ''' on ''' + K["min"] + '''+ trades, then the zip's other sets. Months by entry date, server time.</p>
  </section>

  <section class="l26-sec" id="equity">
    <h2>Running total through 2026</h2>
    <div class="l26-ctl">
      <label for="eqsel">Combination</label>
      <select class="dash-select" id="eqsel" data-draw="eqsel" aria-label="Combination to highlight" data-source="cells2026"></select>
    </div>
    <div class="l26-chart" data-draw="equity" data-source="equity2026 cells2026">—</div>
    <p class="l26-note">Each line is one combination's running total of R, by exit day. The one picked in the menu is highlighted (at first the highest profit factor); the others are in grey for comparison.</p>
  </section>

  <section class="l26-sec" id="zipsets">
    <h2>The best trailing of each timeframe (the zip's sets)</h2>
    <div class="l26-scroll">
      <table class="l26-table" data-source="cells2026" data-row-key="combo" aria-label="The best trailing system of each timeframe in 2026">
        <thead><tr>
          <th data-field="label">Combination</th><th data-field="setups">Setups (presets)</th><th data-field="trades">Trades</th><th data-field="pf">Profit factor</th><th data-field="net_r">Net R</th>
          <th data-field="months_up">Months with a gain</th><th data-field="max_dd_r">Largest drawdown (R)</th><th data-field="stress_pf">Stressed PF</th><th data-field="dukascopy_pf">At Dukascopy's spreads (gold)</th>
          <th data-field="before_2024h2_pf">Gold 15 Jul – 31 Dec 2024 PF</th><th data-field="before_2024_pf">BTC 2024 PF</th><th data-field="before_2023_pf">BTC 2023 PF (from 15 Jan)</th>
        </tr></thead>
        <tbody data-draw="zipsets"></tbody>
      </table>
    </div>
    <p class="l26-note">Chosen per timeframe as the highest profit factor in these months among the systems with ''' + K["min"] + '''+ trades (''' + K["thin"] + '''+ on ''' + S("thin_sets") + ''', where none had ''' + K["min"] + '''). Best means the highest profit factor on its timeframe, not a profitable one: ''' + S("zip_lost") + ''' of the ''' + S("zip_sets") + ''' sets lost money in these months.</p>
  </section>

  <section class="l26-sec" id="caveat">
    <h2>Keep in mind</h2>
    <div class="l26-caveat">
      <p class="l26-p">The zip's trailing systems were chosen on these months, and the best of many combinations is flattered by the choice. On the earlier data (gold 15 Jul – 31 Dec 2024, BTC 15 Jan 2023 – 31 Dec 2024), ''' + S("held_before") + ''' of the ''' + S("reached") + ''' combinations that reached ''' + K["bar"] + ''' in 2026 reached it in every earlier period, and ''' + S("lost_before") + ''' lost money (a profit factor under 1.0) in at least one; the highest earlier profit factor among them was ''' + S("highest_before") + '''. Of the zip's ''' + S("zip_sets") + ''' sets, ''' + S("zip_held") + ''' reached ''' + K["bar"] + ''' in every earlier period; their highest earlier profit factor was ''' + S("zip_highest_before") + '''.</p>
      <p class="l26-p">At Dukascopy's own wider spreads, often above the presets' $0.60 limit so that fewer trades open, ''' + S("gold_best_label") + ''' had a profit factor of ''' + S("gold_best_duk_pf") + ''' on ''' + S("gold_best_duk_trades") + ''' trades instead of ''' + S("gold_best_pf") + ''' on ''' + S("gold_best_trades") + ''' at VT's narrow spread (about $0.15). The zip table gives every gold set at Dukascopy's spreads.</p>
      <h3>The combinations that reached the bar in 2026, on the earlier data</h3>
      <div class="l26-scroll">
        <table class="l26-table" data-source="cells2026" data-row-key="combo" aria-label="The combinations that reached the bar in 2026, on the earlier data">
          <thead><tr><th data-field="label">Combination</th><th data-field="pf">2026 PF</th><th data-field="before_2024h2_pf">Gold 15 Jul – 31 Dec 2024 PF</th><th data-field="before_2024h2_trades">Trades</th><th data-field="before_2024_pf">BTC 2024 PF</th><th data-field="before_2024_trades">Trades</th><th data-field="before_2023_pf">BTC 2023 PF (from 15 Jan)</th><th data-field="before_2023_trades">Trades</th></tr></thead>
          <tbody data-draw="before"></tbody>
        </table>
      </div>
    </div>
  </section>

  <details class="l26-defs" id="definitions">
    <summary>What the figures mean</summary>
    <dl>
      <dt>Profit factor (PF)</dt><dd>Gross wins divided by gross losses. Above 1.0 the trades made money; the study's bar is ''' + K["bar"] + ''' on ''' + K["min"] + ''' or more trades.</dd>
      <dt>R</dt><dd>A trade's initial risk, from entry to stop. Net +10R is ten times one trade's risk.</dd>
      <dt>Setups</dt><dd>The settings picked for a timeframe and trailing system on 1 Jan 2025 – 15 May 2026 (up to 10, one per direction, session and trend filter). Each preset is one setup.</dd>
      <dt>Stressed PF</dt><dd>Entries one minute late, slippage on entries and on stop and market exits (gold $0.10, BTC $3), and a higher commission (gold $0.67 per ounce instead of $0.60; BTC $2 per BTC instead of none).</dd>
      <dt>One-minute engine PF</dt><dd>The study's one-minute backtest on the same prices and costs, beside the tick replay.</dd>
      <dt>At Dukascopy's spreads</dt><dd>Gold with Dukascopy's own bid and ask, often above the presets' $0.60 spread limit, so fewer trades are taken.</dd>
      <dt>Largest drawdown</dt><dd>The deepest fall of the running total from its high, in R, all the setups together.</dd>
      <dt>Months with a gain</dt><dd>Months of 2026 (16 May – 13 Nov) whose trades made money, by entry date.</dd>
    </dl>
  </details>
</div>

<script>
(() => {
  const BAR_PF = 1.3, MIN_TRADES = 100, THIN_TRADES = 30;        // the study's bar and trade minimums
  const C = 'cells2026', MON = 'monthly2026', EQ = 'equity2026';
  const MONTHS = ['2026-05', '2026-06', '2026-07', '2026-08', '2026-09', '2026-10', '2026-11'];
  const PF_FIELDS = new Set(['best_pf', 'highest_before', 'gold_best_pf', 'gold_best_duk_pf', 'zip_highest_before']);
  const f2 = (v) => (v == null || !isFinite(v) ? '–' : v.toFixed(2));
  const f1 = (v) => (v == null || !isFinite(v) ? '–' : v.toFixed(1));
  const sr = (v) => (v == null || !isFinite(v) ? '–' : Math.abs(v) < 0.05 ? (v > 0 ? '+0.0' : '0.0') : (v > 0 ? '+' : '') + v.toFixed(1));
  const pfKey = (r) => (r.no_losses ? Infinity : r.pf ?? -1);
  const byPF = (a, b) => pfKey(b) - pfKey(a) || b.net_r - a.net_r;
  const fpf = (r) => (r.no_losses ? 'no loss' : f2(r.pf));
  const mixPF = (pf) => (pf == null ? 0 : pf >= 1 ? Math.min(60, Math.max(0, (pf - 1) / 0.8 * 60)) : Math.min(60, (1 - pf) / 0.5 * 60));
  const mixR = (r) => Math.min(45, Math.abs(r) / 10 * 45);
  window.L26 = window.L26 || { sel: null };

  dash.calc('summary2026', {
    inputs: [C],
    title: '2026 summary',
    description: 'Counts, the best combination and the earlier-data figures of the combinations that reached a profit factor of 1.3 on 100+ trades in 2026 and of the zip sets.',
    fn: (cells) => {
      const BAR = 1.3, MIN = 100;
      const key = (r) => (r.no_losses ? Infinity : r.pf ?? -1);
      const elig = cells.filter((r) => r.trades >= MIN);
      const reached = elig.filter((r) => r.no_losses || r.pf >= BAR).sort((a, b) => key(b) - key(a));
      const zip = cells.filter((r) => r.chosen);
      const best = reached[0] || {};
      const earlier = (r) => (r.symbol === 'XAUUSD' ? [r.before_2024h2_pf] : [r.before_2024_pf, r.before_2023_pf]).filter((v) => v != null);
      const held = (rows) => rows.filter((r) => earlier(r).length && earlier(r).every((v) => v >= BAR)).length;
      const highest = (rows) => { const v = rows.flatMap(earlier); return v.length ? Math.max(...v) : null; };
      const gold = elig.filter((r) => r.symbol === 'XAUUSD').sort((a, b) => key(b) - key(a))[0] || {};
      const tfs = new Set(cells.map((r) => r.tf));
      const thin = zip.filter((r) => r.trades < MIN).map((r) => r.label.split(' ').slice(0, 2).join(' '));
      return [{
        eligible: elig.length, eligible_gold: elig.filter((r) => r.symbol === 'XAUUSD').length, eligible_btc: elig.filter((r) => r.symbol === 'BTCUSD').length,
        reached: reached.length,
        reached_gold: reached.filter((r) => r.symbol === 'XAUUSD').length,
        reached_btc: reached.filter((r) => r.symbol === 'BTCUSD').length,
        best_combo: best.combo ?? null, best_label: best.label ?? null, best_pf: best.pf ?? null, best_trades: best.trades ?? null,
        best_months_up: best.months_up ?? null, best_months_traded: best.months_traded ?? null,
        held_before: held(reached), highest_before: highest(reached),
        lost_before: reached.filter((r) => earlier(r).some((v) => v < 1)).length,
        zip_sets: zip.length, zip_held: held(zip), zip_highest_before: highest(zip), zip_lost: zip.filter((r) => r.pf != null && r.pf < 1).length,
        thin_sets: thin.length ? thin.join(', ') : null,
        no_setup_tfs: ['M1', 'H1'].filter((t) => !tfs.has(t)).join(' or ') || null,
        gold_best_label: gold.label ?? null, gold_best_pf: gold.pf ?? null, gold_best_trades: gold.trades ?? null,
        gold_best_duk_pf: gold.dukascopy_pf ?? null, gold_best_duk_trades: gold.dukascopy_trades ?? null,
      }];
    },
  });

  dash.draw('k', (el) => {
    el.textContent = { bar: String(BAR_PF), min: String(MIN_TRADES), thin: String(THIN_TRADES) }[el.dataset.k] ?? '—';
  });

  dash.draw('sum', (el) => {
    const s = dash.data('summary2026');
    if (s.status !== 'ok' || !Array.isArray(s.data) || !s.data.length) { el.textContent = '—'; return; }
    const f = el.dataset.field, v = s.data[0][f];
    el.textContent = v == null ? '—' : typeof v === 'number' ? (PF_FIELDS.has(f) ? v.toFixed(2) : String(v)) : String(v);
  });

  const mark = (node, source, field, where) => { node.setAttribute('data-source', source); node.setAttribute('data-field', field); node.setAttribute('data-where', where); return node; };
  const span = (text, cls) => { const s = document.createElement('span'); if (cls) s.className = cls; s.textContent = text; return s; };

  dash.draw('hc', (el) => {
    const d = dash.data(C);
    el.replaceChildren();
    el.className = 'l26-hc';
    el.style.removeProperty('--mix');
    el.removeAttribute('aria-label');
    if (d.status !== 'ok') return;
    const r = d.data.find((x) => x.symbol === el.dataset.sym && x.tf === el.dataset.tf && x.trailing === el.dataset.kind);
    if (!r) { el.append(span('·', 'l26-none')); el.setAttribute('aria-label', 'no setup'); return; }
    const where = 'combo=' + r.combo;
    const v = mark(span(fpf(r), 'l26-v'), C, 'pf', where);
    const n = mark(span(String(r.trades), 'l26-n'), C, 'trades', where);
    const tip = document.createElement('span'); tip.className = 'l26-tip'; tip.setAttribute('role', 'tooltip');
    const t1 = document.createElement('b');
    t1.append('PF ', mark(span(fpf(r)), C, 'pf', where), ' on ', mark(span(String(r.trades)), C, 'trades', where), ' trades');
    [...t1.querySelectorAll('span')].forEach((s) => { s.style.display = 'inline'; s.style.color = 'inherit'; });
    const t2 = span(r.label + ', ' + r.setups + (r.setups === 1 ? ' setup' : ' setups'));
    const t3 = document.createElement('span');
    t3.append('Net ', mark(span(sr(r.net_r)), C, 'net_r', where), 'R · stressed PF ', mark(span(f2(r.stress_pf)), C, 'stress_pf', where));
    [...t3.querySelectorAll('span')].forEach((s) => { s.style.display = 'inline'; });
    const extra = [r.chosen ? 'Best of its timeframe (in the zip)' : '', r.trades < MIN_TRADES ? 'Under ' + MIN_TRADES + ' trades' : ''].filter(Boolean).join(' · ');
    tip.append(t1, t2, t3); if (extra) tip.append(span(extra));
    el.append(v, n, tip);
    el.classList.add(r.pf != null && r.pf < 1 && !r.no_losses ? 'l26-loss' : 'l26-gain');
    el.style.setProperty('--mix', ((r.no_losses ? 60 : mixPF(r.pf)) * (r.trades < MIN_TRADES ? 0.35 : 1)).toFixed(0) + '%');
    if (r.trades < MIN_TRADES) el.classList.add('l26-few');
    if (r.chosen) el.classList.add('l26-best');
    if (r.trades >= MIN_TRADES && (r.no_losses || r.pf >= BAR_PF)) el.classList.add('l26-reached');
    el.setAttribute('aria-label', r.label + ': profit factor ' + fpf(r) + ' on ' + r.trades + ' trades');
  });

  const txt = (v) => (v ?? '–');
  const int = (v) => (v == null ? '–' : String(v));
  const yesno = (v) => (v ? 'yes' : '–');
  function rowsInto(tbody, rows, cols) {
    tbody.replaceChildren(...rows.map((r) => {
      const tr = document.createElement('tr'); tr.dataset.key = r.combo;
      cols.forEach(([field, fmt], i) => {
        const td = document.createElement(i === 0 ? 'th' : 'td'); if (i === 0) td.scope = 'row';
        const v = r[field];
        td.textContent = field === 'pf' ? fpf(r) : fmt(v, r);
        if (fmt === yesno) td.className = v ? 'l26-yes' : 'l26-dim';
        tr.append(td);
      });
      return tr;
    }));
  }
  const isReached = (r) => r.trades >= MIN_TRADES && (r.no_losses || r.pf >= BAR_PF);

  dash.draw('reached', (tbody) => {
    const d = dash.data(C);
    if (d.status !== 'ok') { tbody.replaceChildren(); return; }
    rowsInto(tbody, d.data.filter(isReached).sort(byPF),
      [['label', txt], ['setups', int], ['trades', int], ['pf', f2], ['net_r', sr], ['win_pct', f1], ['max_dd_r', f1], ['months_up', int],
       ['stress_pf', f2], ['one_minute_pf', f2], ['chosen', yesno], ['t15', yesno]]);
  });

  dash.draw('zipsets', (tbody) => {
    const d = dash.data(C);
    if (d.status !== 'ok') { tbody.replaceChildren(); return; }
    rowsInto(tbody, d.data.filter((r) => r.chosen).sort((a, b) => (a.symbol < b.symbol ? 1 : a.symbol > b.symbol ? -1 : a.tf_order - b.tf_order)),
      [['label', txt], ['setups', int], ['trades', int], ['pf', f2], ['net_r', sr], ['months_up', int], ['max_dd_r', f1], ['stress_pf', f2], ['dukascopy_pf', f2],
       ['before_2024h2_pf', f2], ['before_2024_pf', f2], ['before_2023_pf', f2]]);
  });

  dash.draw('before', (tbody) => {
    const d = dash.data(C);
    if (d.status !== 'ok') { tbody.replaceChildren(); return; }
    rowsInto(tbody, d.data.filter(isReached).sort(byPF),
      [['label', txt], ['pf', f2], ['before_2024h2_pf', f2], ['before_2024h2_trades', int], ['before_2024_pf', f2], ['before_2024_trades', int],
       ['before_2023_pf', f2], ['before_2023_trades', int]]);
  });

  function monthRows(tbody, rows) {
    const m = dash.data(MON);
    tbody.replaceChildren(...rows.map((r) => {
      const tr = document.createElement('tr');
      const th = document.createElement('th'); th.scope = 'row'; th.textContent = r.label; tr.append(th);
      MONTHS.forEach((mo) => {
        const row = m.data.find((x) => x.combo === r.combo && x.month === mo);
        const td = document.createElement('td'); td.className = 'l26-mc';
        if (row && row.trades) {
          td.append(mark(span(sr(row.net_r)), MON, 'net_r', 'combo=' + r.combo + '&month=' + mo));
          if (row.net_r !== 0) { td.classList.add(row.net_r > 0 ? 'l26-gain' : 'l26-loss'); td.style.setProperty('--mix', Math.max(6, mixR(row.net_r)).toFixed(0) + '%'); }
          td.setAttribute('aria-label', row.month_label + ': ' + sr(row.net_r) + 'R on ' + row.trades + ' trades');
        } else { td.textContent = '–'; }
        tr.append(td);
      });
      const tot = document.createElement('td'); tot.className = 'l26-total';
      tot.append(mark(span(sr(r.net_r)), C, 'net_r', 'combo=' + r.combo));
      tr.append(tot);
      return tr;
    }));
  }
  dash.draw('months', (tbody) => {
    const c = dash.data(C), m = dash.data(MON);
    if (c.status !== 'ok' || m.status !== 'ok') { tbody.replaceChildren(); return; }
    monthRows(tbody, c.data.filter(isReached).sort(byPF));
  });
  dash.draw('months2', (tbody) => {
    const c = dash.data(C), m = dash.data(MON);
    if (c.status !== 'ok' || m.status !== 'ok') { tbody.replaceChildren(); return; }
    monthRows(tbody, c.data.filter((r) => r.chosen && !isReached(r)).sort(byPF));
  });

  const shownRows = (cells) => [...cells.filter(isReached).sort(byPF), ...cells.filter((r) => r.chosen && !isReached(r)).sort(byPF)];

  dash.draw('eqsel', (sel) => {
    const c = dash.data(C);
    if (c.status !== 'ok') { sel.replaceChildren(); return; }
    const shown = shownRows(c.data);
    sel.replaceChildren(...shown.map((r) => new Option(r.label + ' (PF ' + fpf(r) + ')', r.combo)));
    if (!shown.some((r) => r.combo === window.L26.sel) && shown.length) window.L26.sel = shown[0].combo;
    sel.value = window.L26.sel;
    sel.onchange = () => { window.L26.sel = sel.value; dash.draw('equity'); };
  });

  dash.draw('equity', (el) => {
    const e = dash.data(EQ), c = dash.data(C);
    if (e.status !== 'ok' || c.status !== 'ok') {
      el.replaceChildren(); el.textContent = e.status === 'error' || c.status === 'error' ? 'Failed to load' : '—';
      el.className = 'l26-chart' + (e.status === 'error' || c.status === 'error' ? ' l26-fail' : '');
      return;
    }
    el.className = 'l26-chart';
    el.replaceChildren();
    const parse = d3.utcParse('%Y-%m-%d');
    const series = d3.groups(e.data, (r) => r.combo).map(([combo, rows]) => ({ combo, label: rows[0].label, pts: rows.map((r) => ({ d: parse(r.date), v: r.cum_r, n: r.trades, date: r.date })) }));
    const first = shownRows(c.data)[0];
    const selCombo = window.L26.sel || (first && first.combo);
    const sel = series.find((s) => s.combo === selCombo) || series.find((s) => first && s.combo === first.combo) || series[0];
    if (!sel) { el.textContent = '—'; return; }
    const W = Math.max(280, el.clientWidth || 640), H = 300;
    const last = sel.pts[sel.pts.length - 1];
    const svg = d3.select(el).append('svg').attr('viewBox', `0 0 ${W} ${H}`).attr('role', 'img')
      .attr('aria-label', 'Running total of R through 2026; highlighted: ' + sel.label + ', ending at ' + sr(last.v) + 'R');
    const all = series.flatMap((s) => s.pts);
    const y = d3.scaleLinear().domain(d3.extent([0, ...all.map((p) => p.v)])).nice();
    const measure = (s) => { const t = svg.append('text').style('font-size', 'var(--cds-font-size-caption)').text(s); const w = t.node().getComputedTextLength(); t.remove(); return w; };
    const ticks = y.ticks(5);
    const left = Math.ceil(Math.max(...ticks.map((t) => measure(String(t))))) + 12;
    const endTxt = sr(last.v) + 'R';
    const right = Math.ceil(measure(endTxt)) + 16;
    const m = { t: 10, r: right, b: 26, l: left };
    const x = d3.scaleUtc().domain([parse('2026-05-15'), d3.max([parse('2026-11-13'), ...all.map((p) => p.d)])]).range([m.l, W - m.r]);
    y.range([H - m.b, m.t]);
    svg.append('g').attr('transform', `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(5).tickSize(-(W - m.l - m.r)).tickFormat((t) => String(t)))
      .call((g) => g.select('.domain').remove());
    svg.append('g').attr('transform', `translate(0,${H - m.b})`).call(d3.axisBottom(x).ticks(d3.utcMonth.every(1)).tickFormat(d3.utcFormat('%b')).tickSizeOuter(0));
    svg.append('line').attr('x1', m.l).attr('x2', W - m.r).attr('y1', y(0)).attr('y2', y(0)).style('stroke', 'var(--cds-chart-reference)');
    const line = d3.line().x((p) => x(p.d)).y((p) => y(p.v));
    svg.append('g').selectAll('path').data(series.filter((s) => s !== sel)).join('path')
      .attr('d', (s) => line(s.pts)).attr('fill', 'none').style('stroke', 'var(--cds-chart-muted)').attr('stroke-width', 1).attr('stroke-opacity', 0.7);
    svg.append('path').attr('d', line(sel.pts)).attr('fill', 'none').style('stroke', dash.colors[0]).attr('stroke-width', 2).attr('stroke-linejoin', 'round').attr('stroke-linecap', 'round');
    svg.append('circle').attr('cx', x(last.d)).attr('cy', y(last.v)).attr('r', 4).style('fill', dash.colors[0]).style('stroke', 'var(--color-bg)').attr('stroke-width', 2);
    svg.append('text').attr('x', x(last.d) + 8).attr('y', y(last.v)).attr('dy', '0.35em').style('fill', 'var(--color-fg)').style('font-size', 'var(--cds-font-size-caption)')
      .attr('data-source', EQ).attr('data-field', 'cum_r').attr('data-where', 'combo=' + sel.combo + '&date=' + last.date).text(endTxt);
    const hair = svg.append('line').attr('y1', m.t).attr('y2', H - m.b).style('stroke', 'var(--cds-chart-axis)').style('visibility', 'hidden');
    const dot = svg.append('circle').attr('r', 4).style('fill', dash.colors[0]).style('stroke', 'var(--color-bg)').attr('stroke-width', 2).style('visibility', 'hidden');
    const tip = document.createElement('div'); tip.className = 'l26-ctip'; tip.style.visibility = 'hidden';
    const tv = document.createElement('b'), tl = document.createElement('span'), td = document.createElement('span');
    tip.append(tv, tl, td); el.append(tip);
    const fmt = d3.utcFormat('%-d %b %Y');
    const bis = d3.bisector((p) => p.d).center;
    const show = (px) => {
      const p = sel.pts[Math.max(0, Math.min(sel.pts.length - 1, bis(sel.pts, x.invert(px))))];
      hair.attr('x1', x(p.d)).attr('x2', x(p.d)).style('visibility', 'visible');
      dot.attr('cx', x(p.d)).attr('cy', y(p.v)).style('visibility', 'visible');
      tv.textContent = sr(p.v) + 'R'; tl.textContent = sel.label; td.textContent = fmt(p.d) + ' · ' + p.n + ' trades closed';
      tip.style.visibility = 'visible';
      const bw = el.clientWidth, sx = bw / W, tw = tip.offsetWidth;
      tip.style.left = Math.min(Math.max(0, x(p.d) * sx + 10), bw - tw) + 'px';
      tip.style.top = Math.max(0, y(p.v) * sx - 48) + 'px';
    };
    const hide = () => { hair.style('visibility', 'hidden'); dot.style('visibility', 'hidden'); tip.style.visibility = 'hidden'; };
    svg.append('rect').attr('x', m.l).attr('y', m.t).attr('width', W - m.l - m.r).attr('height', H - m.t - m.b).attr('fill', 'transparent')
      .attr('tabindex', 0).attr('aria-label', 'Move along the highlighted line')
      .on('pointermove', (ev) => { const [px] = d3.pointer(ev, svg.node()); show(px); })
      .on('pointerleave', hide)
      .on('focus', () => show(x(last.d))).on('blur', hide);
  });
})();
</script>
'''


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(PAGE)
    print(OUT, len(PAGE.encode()), "bytes")


if __name__ == "__main__":
    main()
