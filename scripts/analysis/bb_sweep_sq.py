import sys
sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")
import pandas as pd, numpy as np, itertools
from scripts.analysis.range_strategy_comparison import BBRsiMeanReversionStrategy, BacktestEngine, build_day_context

def load_nt():
    df1=pd.read_csv("data/derived/nt_es_09_26_1m_2025_2026_mergeBA.csv", parse_dates=["time"]).set_index("time").sort_index()
    df5=pd.read_csv("data/derived/nt_es_09_26_5m_2025_2026_mergeBA.csv", parse_dates=["time"]).set_index("time").sort_index()
    df1=df1[(df1.index.year>=2025)&(df1.index.year<=2026)]
    df5=df5[(df5.index.year>=2025)&(df5.index.year<=2026)]
    return df1, df5

df1,df5=load_nt()
df_daily=df1.resample("D").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna()
tr2=pd.concat([df_daily["high"]-df_daily["low"], (df_daily["high"]-df_daily["close"].shift(1)).abs(), (df_daily["low"]-df_daily["close"].shift(1)).abs()],axis=1).max(axis=1)
daily_atr2=tr2.rolling(10, min_periods=1).mean()
df1["trade_date"]=df1.index.date
df1.loc[df1.index.hour>=18,"trade_date"]=(df1.loc[df1.index.hour>=18].index + pd.Timedelta(days=1)).date
unique_dates=sorted(df1["trade_date"].unique())

combos=list(itertools.product([14,20],[1.8,2.0],[25,28]))
rows=[]
for bb,sd,adx_thr in combos:
    strat=BBRsiMeanReversionStrategy("ES", tick_size=0.25, bb_period=bb, std_dev=sd, rsi_period=14, adx_threshold=adx_thr, use_adx=True, squeeze_only=True, squeeze_pct=30, squeeze_lookback=20)
    engine=BacktestEngine("ES", tick_size=0.25, entry_mode="limit")
    trades=[]
    for t_date in unique_dates:
        ts=pd.Timestamp(t_date)
        if ts.weekday()>=5 or ts.year<2025: continue
        ctx=build_day_context(ts, df1, df5, daily_atr2, ib_minutes=30)
        if ctx is None: continue
        for sess in strat.get_active_sessions():
            sig=strat.detect_signal(ctx, sess)
            if sig is None: continue
            sig.metadata["strategy_name"]=strat.name
            tr=engine.simulate_trade(sig, ctx)
            if tr is not None:
                trades.append(tr.__dict__)
    df=pd.DataFrame(trades)
    if df.empty:
        rows.append({"bb":bb,"sd":sd,"adx":adx_thr,"trades":0,"wr":0,"pf":0,"net":0,"dd":0})
        print(f"Sq bb{bb} sd{sd} adx{adx_thr}: 0 trades")
        continue
    pnl=df["total_pnl_dollars"]; cum=pnl.cumsum(); dd=(cum-cum.cummax()).min()
    wr=(pnl>1).mean()*100; gp=pnl[pnl>0].sum(); gl=abs(pnl[pnl<0].sum()); pf=gp/gl if gl>0 else 999; net=cum.iloc[-1]
    rows.append({"bb":bb,"sd":sd,"adx":adx_thr,"trades":len(df),"wr":round(wr,1),"pf":round(pf,2),"net":round(net),"dd":round(abs(dd))})
    print(f"Sq bb{bb} sd{sd} adx{adx_thr}: {len(df):3d} WR{wr:4.1f}% PF{pf:4.2f} Net${net:6.0f} DD${abs(dd):4.0f}")

df=pd.DataFrame(rows).sort_values(["pf","net"],ascending=False)
print("\nSq Ranked by PF:")
print(df.to_string(index=False))
df.to_csv("data/derived/bb_sweep_Sq_12arm_ES_NTshared_2025_2026.csv", index=False)
print("Saved Sq to data/derived/bb_sweep_Sq_12arm_ES_NTshared_2025_2026.csv")
