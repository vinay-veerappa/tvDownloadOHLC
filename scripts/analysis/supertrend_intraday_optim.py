"""Supertrend intraday optimizer — trend-following version (trailing exit, no range gate)."""
import sys
sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")
import pandas as pd, numpy as np, itertools
from joblib import Parallel, delayed

def load_nt(sym="ES"):
    df1=pd.read_csv(f"data/derived/nt_{sym.lower()}_09_26_1m_2025_2026_mergeBA.csv", parse_dates=["time"]).set_index("time").sort_index()
    df5=pd.read_csv(f"data/derived/nt_{sym.lower()}_09_26_5m_2025_2026_mergeBA.csv", parse_dates=["time"]).set_index("time").sort_index()
    return df1[(df1.index.year>=2025)&(df1.index.year<=2026)], df5[(df5.index.year>=2025)&(df5.index.year<=2026)]

DF1,DF5=load_nt("ES")
df_daily=DF1.resample("D").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()
tr2=pd.concat([df_daily["high"]-df_daily["low"], (df_daily["high"]-df_daily["close"].shift(1)).abs(), (df_daily["low"]-df_daily["close"].shift(1)).abs()],axis=1).max(axis=1)
daily_atr2=tr2.rolling(10, min_periods=1).mean()
DF1["trade_date"]=DF1.index.date
DF1.loc[DF1.index.hour>=18,"trade_date"]=(DF1.loc[DF1.index.hour>=18].index + pd.Timedelta(days=1)).date
unique_dates=sorted(DF1["trade_date"].unique())

def supertrend(high, low, close, period, mult):
    hl2=(high+low)/2.0
    tr=pd.concat([high-low,(high-close.shift(1)).abs(),(low-close.shift(1)).abs()],axis=1).max(axis=1)
    atr=tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    upper=hl2+mult*atr; lower=hl2-mult*atr
    fu=upper.copy(); fl=lower.copy()
    for i in range(1,len(upper)):
        if fu.iloc[i]>fu.iloc[i-1]: fu.iloc[i]=fu.iloc[i-1]
        if fl.iloc[i]<fl.iloc[i-1]: fl.iloc[i]=fl.iloc[i-1]
    st=pd.Series(np.nan,index=close.index)
    for i in range(1,len(close)):
        if close.iloc[i]>fu.iloc[i-1]: st.iloc[i]=1
        elif close.iloc[i]<fl.iloc[i-1]: st.iloc[i]=-1
        else: st.iloc[i]=st.iloc[i-1]
    return st

def run_one(args):
    period, mult, trail_mult, exit_mode = args
    from scripts.analysis.range_strategy_comparison import build_day_context
    trades=[]
    for t_date in unique_dates:
        ts=pd.Timestamp(t_date)
        if ts.weekday()>=5 or ts.year<2025: continue
        ctx=build_day_context(ts, DF1, DF5, daily_atr2, ib_minutes=30)
        if ctx is None: continue
        # use full day 5m (09:30-16:00) for trend-following
        bars5=ctx.day_bars_5m
        if bars5 is None or len(bars5)<period+5: continue
        close=bars5["close"]; high=bars5["high"]; low=bars5["low"]
        st=supertrend(high, low, close, period, mult)
        atr5=(high.rolling(14).max()-low.rolling(14).min())/14
        # intraday sim: enter on flip, trail stop, exit on opposite flip or 16:00
        pos=0; entry=0; stop=0; entry_idx=0
        for i in range(1, len(bars5)):
            ct=bars5.index[i]
            a5=atr5.iloc[i]
            if np.isnan(a5) or a5<=0: continue
            st0=st.iloc[i]; st1=st.iloc[i-1]
            if pd.isna(st0) or pd.isna(st1): continue
            c0=close.iloc[i]; h0=high.iloc[i]; l0=low.iloc[i]
            # manage open
            if pos!=0:
                if exit_mode=="flip":
                    if (pos==1 and st0==-1) or (pos==-1 and st0==1):
                        pnl=(c0-entry)*pos
                        trades.append({"date":str(ts.date()),"dir":pos,"entry":entry,"exit":c0,"pnl":pnl,"bars":i-entry_idx})
                        pos=0
                elif exit_mode=="trail":
                    if pos==1:
                        stop=max(stop, h0-trail_mult*a5)
                        if l0<=stop:
                            pnl=(stop-entry)
                            trades.append({"date":str(ts.date()),"dir":1,"entry":entry,"exit":stop,"pnl":pnl,"bars":i-entry_idx})
                            pos=0
                    else:
                        stop=min(stop, l0+trail_mult*a5)
                        if h0>=stop:
                            pnl=(entry-stop)
                            trades.append({"date":str(ts.date()),"dir":-1,"entry":entry,"exit":stop,"pnl":pnl,"bars":i-entry_idx})
                            pos=0
            # enter on flip
            if pos==0:
                if st0==1 and st1==-1:
                    pos=1; entry=c0; entry_idx=i; stop=entry-trail_mult*a5
                elif st0==-1 and st1==1:
                    pos=-1; entry=c0; entry_idx=i; stop=entry+trail_mult*a5
        # EOD flatten
        if pos!=0:
            exit_px=close.iloc[-1]
            pnl=(exit_px-entry)*pos
            trades.append({"date":str(ts.date()),"dir":pos,"entry":entry,"exit":exit_px,"pnl":pnl,"bars":len(bars5)-entry_idx})
    if not trades: return dict(period=period,mult=mult,trail=trail_mult,exit=exit_mode,trades=0,wr=0,pf=0,net=0,dd=0)
    df=pd.DataFrame(trades)
    pnl=df["pnl"]; cum=pnl.cumsum(); dd=(cum-cum.cummax()).min()
    wr=(pnl>0).mean()*100; gp=pnl[pnl>0].sum(); gl=abs(pnl[pnl<0].sum()); pf=gp/gl if gl>0 else 999; net=cum.iloc[-1]
    return dict(period=period,mult=mult,trail=trail_mult,exit=exit_mode,trades=len(df),wr=round(wr,1),pf=round(pf,2),net=round(net),dd=round(abs(dd)))

if __name__=="__main__":
    grid=list(itertools.product([7,10,14],[2.0,3.0],[1.5,2.0,2.5,3.0],["flip","trail"]))
    print(f"Supertrend intraday grid: {len(grid)} arms, 8 workers")
    results=Parallel(n_jobs=8, backend="loky", verbose=5)(delayed(run_one)(a) for a in grid)
    df=pd.DataFrame(results).sort_values(["pf","net"],ascending=False)
    print(df.head(20).to_string(index=False))
    df.to_csv("data/derived/supertrend_intraday_grid.csv", index=False)
    print("Saved data/derived/supertrend_intraday_grid.csv")
