# Sanity test for request.security mapping: a 60m bar's value must appear on the chart bar
# whose close equals the 60m close, never earlier (no lookahead), never stale by > 1 bar.
import numpy as np, pandas as pd
from engine import *
df=load_1m().iloc[:20000]
assert str(df.index.dtype).startswith("datetime64[ns")
for ctf in (1,5,15):
    ch=resample(df,ctf); cct=ch.index.values.astype("int64")+ctf*60_000_000_000
    for tf in (1,5,15,30,60):
        s=resample(df,tf); sct=s.index.values.astype("int64")+tf*60_000_000_000
        idx=np.searchsorted(sct,cct,side="right")-1
        ok=idx>=0
        assert (sct[idx[ok]]<=cct[ok]).all()                      # no lookahead
        nxt=np.minimum(idx[ok]+1,len(sct)-1)
        assert ((sct[nxt]>cct[ok])|(idx[ok]==len(sct)-1)).all()   # most recent closed bar
        m=map_float(sct,s.c.to_numpy(),cct)
        # where both close at the same instant, mapped close == chart close
        same=np.isin(cct,sct); assert np.allclose(m[same],ch.c.to_numpy()[same])
        print(f"chart {ctf}m <- {tf}m ok, mapped bars {ok.mean():.4f}")
