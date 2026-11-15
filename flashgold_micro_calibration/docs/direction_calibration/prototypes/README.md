# Engine prototype for the order-flow feed, the decision log and signal-only replays (not applied)

Written and tested by an agent on 2026-11-15 against `tools/` at commit `171be4d`. Nothing here is applied to `tools/`.
Take golden hashes of today's engine BEFORE applying anything (see `../BRIEF.md` section 4, self-test plan). Then work in a scratch copy first:

```bash
cd flashgold_micro_calibration
X=/path/to/scratch                                  # any folder outside the repo
mkdir -p $X && cp -r tools $X/tools && rm -rf $X/tools/__pycache__
ln -s $PWD/data $X/data; ln -s $PWD/results $X/results; ln -s $PWD/shipped_presets $X/shipped_presets
git show 171be4d:flashgold_micro_calibration/tools/engine.py > $X/tools/engine_orig.py     # pristine copy for the parity tests
cd $X/tools
for f in engine sim params selftest; do patch $f.py < <repo>/flashgold_micro_calibration/docs/direction_calibration/prototypes/prototype_$f.diff; done
cp <repo>/flashgold_micro_calibration/docs/direction_calibration/prototypes/{flowproto,fwd,rescore}.py .
export PROTO_TOOLS=$X/tools
python3 -I selftest.py ../data                      # 1,218 unit + 1,222 data checks pass (checked 2026-11-15)
python3 -I <repo>/.../prototypes/tests/t1_compile.py 2026-11    # neutral parity: trades and 21 counters bit-identical for 5 configs
```

All four diffs apply cleanly to `tools/` at commit `171be4d` (checked with `patch --dry-run` and for real on a copy). `prototype_selftest.diff` only
adds the six new `run_chunk` arguments to the call in `selftest.py` (the prototype's `run_chunk` takes 31 arguments instead of 25).
After the engine is changed in the repo, delete `results/.done_*`, or `run_all.sh` skips every study.

What the diffs add: four per-chunk flow arrays and the flow inputs in `run_chunk` (votes, flow direction, `:FA/:FD` labels carried on pending
orders, market orders and positions, the market-route gate, scenario keys, the four label-dependent exits); a decision log (one row per
direction evaluation, 288 bytes) behind a flag; `X_SignalOnly` (entry chain only, placements written as signal rows); `X_LogMinGapMs`;
caches built before the thread pool (fixes a latent race in `Sim._cand`). `flowproto.py` is a toy series that tests the plumbing: it is NOT a
model of the real feed. `fwd.py` is the forward-outcome kernel (both sides, nine horizons, six SL/TP brackets, calibrated fills).
`rescore.py` re-scores direction inputs from a decision log.

What the agent measured (one month of ticks at a time, 2026-11 unless stated; its own words in `../BRIEF.md` section 4):
- neutral flow reproduces today's trades (18 columns) and all 21 counters bit for bit, for 5 presets;
- log rows equal the engine's decision counter; every trade links to its log row (545/545); trades are identical with logging on or off;
  logs and trades are byte-identical for 1, 2 and 3 worker threads;
- re-scoring winner, router action, scenario key and flow label from a base-set log equals the engine on 100% of the rows both runs evaluated,
  for 15 direction-input variants; FlashGold gate-only inputs re-score exactly for 6 variants;
- the forward kernel in pure-bracket mode equals the engine on 3,603 of 3,603 market trades;
- the signal-only placement list equals a full replay with caps, lockout and speed-exit coupling switched off (2,532 of 2,532 and 465 of 465).

Not validated: the four label-dependent exits (they almost never fire; needs forced-state unit tests), anything on the whole feed at once
(7 GB), a second month with a different tick rate (2026-03), the stop-order variant of the forward kernel.

`tests/` are the agent's scripts. They read the patched copy of `tools/` from the environment variable `PROTO_TOOLS` and the helper modules from
this folder; `t1_compile.py` was re-run this way on 2026-11-15 and passes. Memory: one month of ticks at a time (0.6 to 1.4 GB).
