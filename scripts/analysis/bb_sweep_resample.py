import sys
sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")
import pandas as pd, numpy as np, itertools
from scripts.analysis.range_strategy_comparison import _wilder_rsi, _adx

def load_nt():
    df1=pd.read_csv("data/derived/nt_es_09_26_1m_2025_2026_mergeBA.csv", parse_dates=["time"]).set_index("time").sort_index()
    return df1[(df1.index.year>=2025)&(df1.index.year<=2026)]

df1=load_nt()
for tf in [1,3,5]:
    if tf==1:
        df=df1
    else:
        df=df1.resample(f"{tf}min").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()
    for bb,sd,adx_thr in [(20,1.8,25),(20,2.0,25),(14,2.0,25)]:
        close=df["close"]; high=df["high"]; low=df["low"]
        sma=close.rolling(bb).mean(); st=close.rolling(bb).std()
        upper=sma+sd*st; lower=sma-sd*st
        rsi=_wilder_rsi(close,14)
        adx_s=_adx(high,low,close,14)
        sigs=[]
        for i in range(bb+5, len(df)):
            bt=df.index[i]
            if not (bt.time() >= pd.Timestamp("11:30:00").time() and bt.time() < pd.Timestamp("16:00:00").time()): continue
            if bt.weekday()>=5: continue
            c0=close.iloc[i]; c1=close.iloc[i-1]
            u0=upper.iloc[i]; l0=lower.iloc[i]; u1=upper.iloc[i-1]; l1=lower.iloc[i-1]; m0=sma.iloc[i]
            r0=rsi.iloc[i]; r1=rsi.iloc[i-1]; a0=adx_s.iloc[i]
            if pd.isna(u0) or pd.isna(r0): continue
            longSetup = (c1 < l1 and r1 < 33 and c0 > l0 and r0 > r1 and c0 < m0 and r0 < 50)
            shortSetup = (c1 > u1 and r1 > 67 and c0 < u0 and r0 < r1 and c0 > m0 and r0 > 50)
            if a0 >= adx_thr: continue
            if longSetup or shortSetup: sigs.append(bt)
        print(f"TF{tf:1d}m bb{bb} sd{sd} adx{adx_thr}: {len(sigs):3d} signals ({len(sigs)/19:.1f}/mo)")

# Now full backtest for 1m and 3m best (bb20 1.8 and bb20 2.0) to get PF
from scripts.analysis.range_strategy_comparison import BBRsiMeanReversionStrategy, BacktestEngine, build_day_context

def run_tf(tf, bb, sd, adx_thr):
    df1_load=load_nt()
    if tf==5:
        df5=df1_load.resample("5min").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()
        df1=df1_load
    elif tf==3:
        df5=df1_load.resample("3min").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()
        df1=df1_load
    else:
        # 1m: use 1m for both signal and fill? Use 1m for signal too
        df5=df1_load  # signal on 1m
        df1=df1_load
    df_daily=df1.resample("D").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna()
    tr2=pd.concat([df_daily["high"]-df_daily["low"], (df_daily["high"]-df_daily["close"].shift(1)).abs(), (df_daily["low"]-df_daily["close"].shift(1)).abs()],axis=1).max(axis=1)
    daily_atr2=tr2.rolling(10, min_periods=1).mean()
    df1["trade_date"]=df1.index.date
    df1.loc[df1.index.hour>=18,"trade_date"]=(df1.loc[df1.index.hour>=18].index + pd.Timedelta(days=1)).date
    unique_dates=sorted(df1["trade_date"].unique())
    # Need to override detect_signal to use tf df5 - easiest: monkey patch by creating custom strat that uses df5 we built
    # Instead just reuse BBRsi but it expects session_5m from ctx which is built from df5 we pass
    strat=BBRsiMeanReversionStrategy("ES", tick_size=0.25, bb_period=bb, std_dev=sd, rsi_period=14, adx_threshold=adx_thr, use_adx=True, squeeze_only=False)
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
            if tr is not None: trades.append(tr.__dict__)
    df=pd.DataFrame(trades)
    if df.empty: return dict(trades=0, wr=0, pf=0, net=0, dd=0)
    pnl=df["total_pnl_dollars"]; cum=pnl.cumsum(); dd=(cum-cum.cummax()).min()
    wr=(pnl>1).mean()*100; gp=pnl[pnl>0].sum(); gl=abs(pnl[pnl<0].sum()); pf=gp/gl if gl>0 else 999; net=cum.iloc[-1]
    return dict(trades=len(df), wr=round(wr,1), pf=round(pf,2), net=round(net), dd=round(abs(dd)))

print("\nFull backtest PF:")
for tf,bb,sd in [(1,20,1.8),(3,20,1.8),(5,20,1.8),(1,20,2.0),(3,20,2.0)]:
    res=run_tf(tf,bb,sd,25)
    print(f"TF{tf}m bb{bb} sd{sd} adx25: {res['trades']:3d} WR{res['wr']:4.1f}% PF{res['pf']:4.2f} Net${res['net']:6.0f} DD${res['dd']:4.0f}")
