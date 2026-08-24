import sys
sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")
import pandas as pd, numpy as np
from scripts.analysis.range_strategy_comparison import BacktestEngine, build_day_context
from scripts.analysis.supertrend_experiments import supertrend

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

def run(period=10, mult=3.0, trail_mult=2.5, use_trail=True):
    """Daily Supertrend flip, trailing 2.5xATR exit (research-corrected)."""
    from scripts.analysis.range_strategy_comparison import TradeSignal
    # daily ST series
    dst, dfu, dfl = supertrend(df_daily["high"], df_daily["low"], df_daily["close"], period, mult)
    d_atr = tr2.rolling(10, min_periods=1).mean()
    trades=[]
    for t_date in unique_dates:
        ts=pd.Timestamp(t_date)
        if ts.weekday()>=5 or ts.year<2025: continue
        # prior day ST state
        try:
            prior = df_daily.index[df_daily.index < ts][-1]
            st_prior = dst.loc[prior]
            st_prev2 = dst.loc[df_daily.index[df_daily.index < prior][-1]] if len(df_daily.index[df_daily.index < prior])>0 else np.nan
        except: continue
        if pd.isna(st_prior) or pd.isna(st_prev2): continue
        ctx=build_day_context(ts, DF1, DF5, daily_atr2, ib_minutes=30)
        if ctx is None: continue
        atr=float(ctx.atr_val) if not np.isnan(ctx.atr_val) and ctx.atr_val>0 else 20.0
        # flip on prior day close
        long_flip = st_prior==1 and st_prev2==-1
        short_flip = st_prior==-1 and st_prev2==1
        if long_flip:
            entry=float(df_daily.loc[prior,"close"]); sl=float(entry - trail_mult*d_atr.loc[prior]); risk=entry-sl
            if risk<=0: continue
            tp1=float(entry + 1.0*risk); tp2=float(entry + 2.0*risk)
            sig=TradeSignal("LONG", entry, sl, tp1, tp2, risk, ts, "NY_AM"); sig.metadata["strategy_name"]="ST_Daily"
            engine=BacktestEngine("ES", tick_size=0.25, entry_mode="limit")
            tr=engine.simulate_trade(sig, ctx)
            if tr is not None: trades.append(tr.__dict__)
        elif short_flip:
            entry=float(df_daily.loc[prior,"close"]); sl=float(entry + trail_mult*d_atr.loc[prior]); risk=sl-entry
            if risk<=0: continue
            tp1=float(entry - 1.0*risk); tp2=float(entry - 2.0*risk)
            sig=TradeSignal("SHORT", entry, sl, tp1, tp2, risk, ts, "NY_AM"); sig.metadata["strategy_name"]="ST_Daily"
            engine=BacktestEngine("ES", tick_size=0.25, entry_mode="limit")
            tr=engine.simulate_trade(sig, ctx)
            if tr is not None: trades.append(tr.__dict__)
    df=pd.DataFrame(trades)
    if df.empty: return dict(trades=0, wr=0, pf=0, net=0, dd=0)
    pnl=df["total_pnl_dollars"]; cum=pnl.cumsum(); dd=(cum-cum.cummax()).min()
    wr=(pnl>1).mean()*100; gp=pnl[pnl>0].sum(); gl=abs(pnl[pnl<0].sum()); pf=gp/gl if gl>0 else 999; net=cum.iloc[-1]
    return dict(trades=len(df), wr=round(wr,1), pf=round(pf,2), net=round(net), dd=round(abs(dd)))

if __name__=="__main__":
    import csv, pathlib, datetime
    rows=[]
    for label, kw in [("S06 ST daily 10,3", {}), ("S07 ST daily 7,2", {"period":7,"mult":2.0}), ("S08 ST daily 14,3", {"period":14,"mult":3.0})]:
        res=run(**kw)
        print(f"{label}: {res}")
        rows.append((label,res))
    p=pathlib.Path("data/derived/supertrend_experiments_log.csv")
    with open(p,"a",newline="") as f:
        w=csv.writer(f); today=datetime.date.today().isoformat()
        for label,res in rows:
            w.writerow([label.split()[0], today, label, res["trades"], res["wr"], res["pf"], res["net"], res["dd"], round(res["trades"]/19,1)])
    print("logged")
