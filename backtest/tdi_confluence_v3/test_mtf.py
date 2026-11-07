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

# HTF ATR must equal Pine's request.security(tf, ta.atr(14)[1], lookahead_on): the ATR of the
# HTF bar *before* the one containing the chart bar, also on the chart bar that closes the HTF bar.
for ctf in (1, 5, 15):
    ch = resample(df, ctf)
    for tf in (15, 60):
        s = resample(df, tf); a = atr(s.h.to_numpy(), s.l.to_numpy(), s.c.to_numpy(), 14)
        got = atr_on_chart(df, ch, ctf, tf, 14)
        floor = ch.index.floor(f"{tf}min")
        pos = s.index.get_indexer(floor)
        exp = np.where(pos >= 1, a[np.maximum(pos - 1, 0)], np.nan)
        assert np.allclose(got, exp, equal_nan=True), (ctf, tf)
        print(f"chart {ctf}m ATR({tf}m)[1] ok")
