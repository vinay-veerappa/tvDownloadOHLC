import sys
sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")
import pandas as pd, numpy as np
from scripts.analysis.range_strategy_comparison import _wilder_rsi, _adx

def load_nt():
    df1=pd.read_csv("data/derived/nt_es_09_26_1m_2025_2026_mergeBA.csv", parse_dates=["time"]).set_index("time").sort_index()
    return df1[(df1.index.year>=2025)&(df1.index.year<=2026)]

df1=load_nt()
# Test MTF combos: indicator TF vs entry TF
# Use resampling for indicator TF, entry on 1m close after signal
for ind_tf in [5,15]:
    for entry_tf in [1,3,5]:
        if entry_tf > ind_tf: continue  # entry should be <= indicator
        df_ind = df1.resample(f"{ind_tf}min").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna() if ind_tf!=1 else df1
        bb,sd,adx_thr=20,1.8,25
        close=df_ind["close"]; high=df_ind["high"]; low=df_ind["low"]
        sma=close.rolling(bb).mean(); st=close.rolling(bb).std()
        upper=sma+sd*st; lower=sma-sd*st
        rsi=_wilder_rsi(close,14); adx_s=_adx(high,low,close,14)
        sigs=[]
        for i in range(bb+5, len(df_ind)):
            bt=df_ind.index[i]
            if not (bt.time() >= pd.Timestamp("11:30:00").time() and bt.time() < pd.Timestamp("16:00:00").time()): continue
            if bt.weekday()>=5: continue
            c0=close.iloc[i]; c1=close.iloc[i-1]
            u0=upper.iloc[i]; l0=lower.iloc[i]; u1=upper.iloc[i-1]; l1=lower.iloc[i-1]; m0=sma.iloc[i]
            r0=rsi.iloc[i]; r1=rsi.iloc[i-1]; a0=adx_s.iloc[i]
            if pd.isna(u0) or pd.isna(r0): continue
            if a0 >= adx_thr: continue
            longSetup = (c1 < l1 and r1 < 33 and c0 > l0 and r0 > r1 and c0 < m0 and r0 < 50)
            shortSetup = (c1 > u1 and r1 > 67 and c0 < u0 and r0 < r1 and c0 > m0 and r0 > 50)
            if not (longSetup or shortSetup): continue
            sigs.append(bt)
        print(f"IND{ind_tf}m->ENTRY{entry_tf}m bb20 1.8: {len(sigs):3d} signals ({len(sigs)/19:.1f}/mo)")

# Now test 15m->5m with full backtest using 3m as example already done, add 15m
from scripts.analysis.range_strategy_comparison import BBRsiMeanReversionStrategy, BacktestEngine, build_day_context
def run_combo(ind_tf, entry_tf, bb=20, sd=1.8):
    # For full backtest, we need df1 1m for engine and df_ind for signal
    # But BBRsiMeanReversionStrategy is hardcoded to 5m, so we hack by passing df_ind as df5
    df1_l=load_nt()
    df_ind = df1_l.resample(f"{ind_tf}min").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna() if ind_tf!=1 else df1_l
    df_daily=df1_l.resample("D").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna()
    tr2=pd.concat([df_daily["high"]-df_daily["low"], (df_daily["high"]-df_daily["close"].shift(1)).abs(), (df_daily["low"]-df_daily["close"].shift(1)).abs()],axis=1).max(axis=1)
    daily_atr2=tr2.rolling(10, min_periods=1).mean()
    df1_l["trade_date"]=df1_l.index.date
    df1_l.loc[df1_l.index.hour>=18,"trade_date"]=(df1_l.loc[df1_l.index.hour>=18].index + pd.Timedelta(days=1)).date
    unique_dates=sorted(df1_l["trade_date"].unique())
    strat=BBRsiMeanReversionStrategy("ES", tick_size=0.25, bb_period=bb, std_dev=sd, rsi_period=14, adx_threshold=25, use_adx=True, squeeze_only=False)
    # Monkey patch: strat will use ctx.session_5m which is built from df5 we pass (df_ind)
    engine=BacktestEngine("ES", tick_size=0.25, entry_mode="limit")
    trades=[]
    for t_date in unique_dates:
        ts=pd.Timestamp(t_date)
        if ts.weekday()>=5 or ts.year<2025: continue
        ctx=build_day_context(ts, df1_l, df_ind, daily_atr2, ib_minutes=30)
        if ctx is None: continue
        for sess in strat.get_active_sessions():
            sig=strat.detect_signal(ctx, sess)
            if sig is None: continue
            sig.metadata["strategy_name"]=strat.name
            tr=engine.simulate_trade(sig, ctx)
            if tr is not None:
                trades.append(tr.__dict__)
                break
    df=pd.DataFrame(trades)
    if df.empty: return dict(trades=0, wr=0, pf=0, net=0)
    pnl=df["total_pnl_dollars"]; cum=pnl.cumsum(); dd=(cum-cum.cummax()).min()
    wr=(pnl>1).mean()*100; gp=pnl[pnl>0].sum(); gl=abs(pnl[pnl<0].sum()); pf=gp/gl if gl>0 else 999; net=cum.iloc[-1]
    return dict(trades=len(df), wr=round(wr,1), pf=round(pf,2), net=round(net), dd=round(abs(dd)))

print("\nFull backtest combos:")
for ind_tf,bb,sd in [(5,20,1.8),(15,20,1.8),(15,14,2.0),(3,20,1.8)]:
    res=run_combo(ind_tf,1,bb,sd)
    print(f"IND{ind_tf}m bb{bb} sd{sd}: {res}")
