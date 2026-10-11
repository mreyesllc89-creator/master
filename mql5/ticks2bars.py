import sys, glob, os
files = sorted(glob.glob(os.path.join(sys.argv[1], "*", "*.csv")))
out_dir = sys.argv[2]; os.makedirs(out_dir, exist_ok=True)
tfs = {"M15": 900, "M30": 1800, "H1": 3600}
bars = {k: [] for k in tfs}; cur = {k: None for k in tfs}
spreads = []; n = 0
import datetime as dt
for fn in files:
    with open(fn) as f:
        next(f)
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) < 4 or not p[2] or not p[3]: continue
            bid = float(p[2]); ask = float(p[3])
            if bid <= 0 or ask <= 0: continue
            d, t = p[0], p[1]
            ts = dt.datetime(int(d[0:4]), int(d[5:7]), int(d[8:10]), int(t[0:2]), int(t[3:5]), int(t[6:8]))
            epoch = int(ts.timestamp())
            n += 1
            if n % 50 == 0: spreads.append(ask - bid)
            for k, sec in tfs.items():
                b0 = epoch - epoch % sec
                c = cur[k]
                if c is None or c[0] != b0:
                    if c is not None: bars[k].append(c)
                    cur[k] = [b0, bid, bid, bid, bid, 1]
                else:
                    c[2] = max(c[2], bid); c[3] = min(c[3], bid); c[4] = bid; c[5] += 1
for k in tfs:
    if cur[k] is not None: bars[k].append(cur[k])
    with open(os.path.join(out_dir, f"XAUUSD_{k}.csv"), "w") as f:
        f.write("<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\n")
        for b0, o, h, l, c, v in bars[k]:
            ts = dt.datetime.fromtimestamp(b0)
            f.write(f"{ts:%Y.%m.%d}\t{ts:%H:%M:%S}\t{o:.2f}\t{h:.2f}\t{l:.2f}\t{c:.2f}\t{v}\n")
    print(k, len(bars[k]), "bars")
spreads.sort()
print(f"ticks {n}, spread median {spreads[len(spreads)//2]:.3f}, mean {sum(spreads)/len(spreads):.3f}, p90 {spreads[int(len(spreads)*0.9)]:.3f}")
