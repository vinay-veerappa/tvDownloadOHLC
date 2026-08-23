"""Supertrend daily optimizer — independent engine (multi-day holds, no intraday flatten)."""
import sys
sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")
import pandas as pd, numpy as np, itertools
from joblib import Parallel, delayed

def load_nt(sym="ES"):
    df1=pd.read_csv(f"data/derived/nt_{sym.lower()}_09_26_1m_2025_2026_mergeBA.csv", parse_dates=["time"]).set_index("time").sort_index()
    return df1[(df1.index.year>=2025)&(df1.index.year<=2026)]

DF1=load_nt("ES")
df_daily=DF1.resample("D").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()
# daily ATR
tr=pd.concat([df_daily["high"]-df_daily["low"], (df_daily["high"]-df_daily["close"].shift(1)).abs(), (df_daily["low"]-df_daily["close"].shift(1)).abs()],axis=1).max(axis=1)
d_atr=tr.ewm(alpha=1/14, min_periods=14, adjust=False).mean()

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
    st=supertrend(df_daily["high"], df_daily["low"], df_daily["close"], period, mult)
    # simulate daily: enter on flip, exit on opposite flip or trailing ATR
    trades=[]
    pos=0; entry=0; stop=0; entry_date=None
    for i in range(1, len(df_daily)):
        date=df_daily.index[i]
        close=df_daily["close"].iloc[i]
        high=df_daily["high"].iloc[i]; low=df_daily["low"].iloc[i]
        atr=d_atr.iloc[i]
        if np.isnan(atr) or atr<=0: continue
        st0=st.iloc[i]; st1=st.iloc[i-1]
        if pd.isna(st0) or pd.isna(st1): continue
        # manage open position
        if pos!=0:
            if exit_mode=="flip":
                if (pos==1 and st0==-1) or (pos==-1 and st0==1):
                    exit_px=close
                    pnl=(exit_px-entry)*pos
                    trades.append({"date":str(date.date()),"dir":pos,"entry":entry,"exit":exit_px,"pnl":pnl,"days":(date-entry_date).days})
                    pos=0
            elif exit_mode=="trail":
                if pos==1:
                    stop=max(stop, high-trail_mult*atr)
                    if low<=stop:
                        pnl=(stop-entry)
                        trades.append({"date":str(date.date()),"dir":1,"entry":entry,"exit":stop,"pnl":pnl,"days":(date-entry_date).days})
                        pos=0
                else:
                    stop=min(stop, low+trail_mult*atr)
                    if high>=stop:
                        pnl=(entry-stop)
                        trades.append({"date":str(date.date()),"dir":-1,"entry":entry,"exit":stop,"pnl":pnl,"days":(date-entry_date).days})
                        pos=0
        # enter on flip
        if pos==0:
            if st0==1 and st1==-1:
                pos=1; entry=close; entry_date=date
                stop=entry-trail_mult*atr
            elif st0==-1 and st1==1:
                pos=-1; entry=close; entry_date=date
                stop=entry+trail_mult*atr
    # close open at end
    if pos!=0:
        exit_px=df_daily["close"].iloc[-1]
        pnl=(exit_px-entry)*pos
        trades.append({"date":str(df_daily.index[-1].date()),"dir":pos,"entry":entry,"exit":exit_px,"pnl":pnl,"days":(df_daily.index[-1]-entry_date).days})
    if not trades: return dict(period=period,mult=mult,trail=trail_mult,exit=exit_mode,trades=0,wr=0,pf=0,net=0,dd=0)
    df=pd.DataFrame(trades)
    pnl=df["pnl"]; cum=pnl.cumsum(); dd=(cum-cum.cummax()).min()
    wr=(pnl>0).mean()*100; gp=pnl[pnl>0].sum(); gl=abs(pnl[pnl<0].sum()); pf=gp/gl if gl>0 else 999; net=cum.iloc[-1]
    return dict(period=period,mult=mult,trail=trail_mult,exit=exit_mode,trades=len(df),wr=round(wr,1),pf=round(pf,2),net=round(net),dd=round(abs(dd)))

if __name__=="__main__":
    grid=list(itertools.product([7,10,14],[2.0,3.0],[1.5,2.0,2.5,3.0],["flip","trail"]))
    print(f"Supertrend daily grid: {len(grid)} arms, 8 workers")
    results=Parallel(n_jobs=8, backend="loky", verbose=5)(delayed(run_one)(a) for a in grid)
    df=pd.DataFrame(results).sort_values(["pf","net"],ascending=False)
    print(df.head(15).to_string(index=False))
    df.to_csv("data/derived/supertrend_daily_grid.csv", index=False)
    print("Saved data/derived/supertrend_daily_grid.csv")
