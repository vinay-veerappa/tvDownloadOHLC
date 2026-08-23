"""BB sweep optimizer on shared NT MergeBA data — 12 arms, limit mode, 2025-2026."""
import itertools, pathlib, sys
sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")
import pandas as pd, numpy as np
from scripts.analysis.range_strategy_comparison import BBRsiMeanReversionStrategy, DayContext, BacktestEngine, build_day_context

def load_nt(sym="ES"):
    df1=pd.read_csv(f"data/derived/nt_{sym.lower()}_09_26_1m_2025_2026_mergeBA.csv", parse_dates=["time"])
    df1=df1.set_index("time").sort_index()
    df5=pd.read_csv(f"data/derived/nt_{sym.lower()}_09_26_5m_2025_2026_mergeBA.csv", parse_dates=["time"])
    df5=df5.set_index("time").sort_index()
    if df1.index.tz is not None: df1.index=df1.index.tz_convert("America/New_York").tz_localize(None)
    if df5.index.tz is not None: df5.index=df5.index.tz_convert("America/New_York").tz_localize(None)
    df1=df1[(df1.index.year>=2025)&(df1.index.year<=2026)]
    df5=df5[(df5.index.year>=2025)&(df5.index.year<=2026)]
    return df1, df5

def run_one(sym, bb, sd, adx_thr, sym_file="ES"):
    df1, df5 = load_nt(sym_file)
    tr=pd.concat([df1["high"]-df1["low"], (df1["high"]-df1["close"].shift(1)).abs(), (df1["low"]-df1["close"].shift(1)).abs()],axis=1).max(axis=1)
    daily_atr=tr.resample("D").max().rolling(10, min_periods=1).mean()  # approx daily ATR from 1m TR
    # Need daily OHLC for build_day_context? We'll use resampled D
    df_daily=df1.resample("D").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna()
    tr2=pd.concat([df_daily["high"]-df_daily["low"], (df_daily["high"]-df_daily["close"].shift(1)).abs(), (df_daily["low"]-df_daily["close"].shift(1)).abs()],axis=1).max(axis=1)
    daily_atr2=tr2.rolling(10, min_periods=1).mean()

    strat=BBRsiMeanReversionStrategy(sym, tick_size=0.25, bb_period=bb, std_dev=sd, rsi_period=14, adx_threshold=adx_thr, use_adx=True, squeeze_only=False)
    # Build contexts day by day
    df1["trade_date"]=df1.index.date
    evening=df1.index.hour>=18
    df1.loc[evening,"trade_date"]=(df1.loc[evening].index + pd.Timedelta(days=1)).date
    unique_dates=sorted(df1["trade_date"].unique())
    engine=BacktestEngine(sym, tick_size=0.25, entry_mode="limit")
    trades=[]
    for t_date in unique_dates:
        ts=pd.Timestamp(t_date)
        if ts.weekday()>=5: continue
        if ts.year<2025 or ts.year>2026: continue
        ctx=build_day_context(ts, df1, df5, daily_atr2, ib_minutes=30)
        if ctx is None: continue
        for sess in strat.get_active_sessions():
            sig=strat.detect_signal(ctx, sess)
            if sig is None: continue
            sig.metadata["strategy_name"]=strat.name
            tr=engine.simulate_trade(sig, ctx)
            if tr is not None:
                tr.strategy_name=strat.name
                trades.append(tr.__dict__)
    df=pd.DataFrame(trades)
    if df.empty:
        return dict(trades=0, wr=0, pf=0, net=0, dd=0, prop=0)
    pnl=df["total_pnl_dollars"]
    cum=pnl.cumsum()
    dd=(cum-cum.cummax()).min()
    wr=(pnl>1).mean()*100
    gp=pnl[pnl>0].sum(); gl=abs(pnl[pnl<0].sum())
    pf=gp/gl if gl>0 else 999
    net=cum.iloc[-1]
    # prop sim: $3k target $2k trail
    target=3000; mdd=2000
    cur=0; peak=0; passes=fails=0
    for v in pnl:
        cur+=v
        if cur>peak: peak=cur
        if abs(cur-peak)>=mdd:
            fails+=1; cur=0; peak=0
        elif cur>=target:
            passes+=1; cur=0; peak=0
    prop=passes/(passes+fails)*100 if passes+fails>0 else 0
    return dict(trades=len(df), wr=round(wr,1), pf=round(pf,2), net=round(net), dd=round(abs(dd)), prop=round(prop,1), passes=passes, fails=fails)

if __name__=="__main__":
    combos=list(itertools.product([14,20],[1.8,2.0,2.2],[25,28]))
    print(f"Running {len(combos)} combos on NT MergeBA ES 2025-2026...")
    rows=[]
    for bb,sd,adx_thr in combos:
        res=run_one("ES", bb, sd, adx_thr, sym_file="ES")
        rows.append({"bb":bb,"sd":sd,"adx":adx_thr, **res})
        print(f"bb{bb} sd{sd} adx{adx_thr}: {res['trades']:3d} trades WR{res['wr']:4.1f}% PF{res['pf']:4.2f} Net${res['net']:6.0f} DD${res['dd']:4.0f} Prop{res['prop']:4.1f}% ({res['passes']}/{res['fails']})")
    df=pd.DataFrame(rows).sort_values(["pf","net"], ascending=False)
    print("\nRanked by PF:")
    print(df.to_string(index=False))
    df.to_csv("data/derived/bb_sweep_12arm_ES_NTshared_2025_2026.csv", index=False)
    print("Saved to data/derived/bb_sweep_12arm_ES_NTshared_2025_2026.csv")
