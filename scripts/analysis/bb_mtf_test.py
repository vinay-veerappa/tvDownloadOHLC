import sys
sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")
import pandas as pd, numpy as np
from scripts.analysis.range_strategy_comparison import _wilder_rsi, _adx, BacktestEngine, DayContext, build_day_context, BBRsiMeanReversionStrategy
import pathlib

def load_nt():
    df1=pd.read_csv("data/derived/nt_es_09_26_1m_2025_2026_mergeBA.csv", parse_dates=["time"]).set_index("time").sort_index()
    df5=pd.read_csv("data/derived/nt_es_09_26_5m_2025_2026_mergeBA.csv", parse_dates=["time"]).set_index("time").sort_index()
    return df1[(df1.index.year>=2025)&(df1.index.year<=2026)], df5[(df5.index.year>=2025)&(df5.index.year<=2026)]

df1,df5=load_nt()
# Test hybrid: 5m indicators, 1m entry
# For each 5m signal bar, look for next 1m bullish close within 5 min to trigger entry

def hybrid_signals(df1, df5, bb=20, sd=1.8, adx_thr=25):
    close5=df5["close"]; high5=df5["high"]; low5=df5["low"]
    sma=close5.rolling(bb).mean(); st=close5.rolling(bb).std()
    upper=sma+sd*st; lower=sma-sd*st
    rsi5=_wilder_rsi(close5,14)
    adx5=_adx(high5,low5,close5,14)
    # 1m RSI for entry timing
    rsi1=_wilder_rsi(df1["close"],14)
    sigs=[]
    for i in range(bb+5, len(df5)):
        bt=df5.index[i]
        if not (bt.time() >= pd.Timestamp("11:30:00").time() and bt.time() < pd.Timestamp("16:00:00").time()): continue
        if bt.weekday()>=5: continue
        c0=close5.iloc[i]; c1=close5.iloc[i-1]
        u0=upper.iloc[i]; l0=lower.iloc[i]; u1=upper.iloc[i-1]; l1=lower.iloc[i-1]; m0=sma.iloc[i]
        r0=rsi5.iloc[i]; r1=rsi5.iloc[i-1]; a0=adx5.iloc[i]
        if pd.isna(u0) or pd.isna(r0): continue
        if a0 >= adx_thr: continue
        longSetup = (c1 < l1 and r1 < 33 and c0 > l0 and r0 > r1 and c0 < m0 and r0 < 50)
        shortSetup = (c1 > u1 and r1 > 67 and c0 < u0 and r0 < r1 and c0 > m0 and r0 > 50)
        if not (longSetup or shortSetup): continue
        # Now look for 1m entry within next 5 min (3 bars) — 1m close confirms
        # Entry trigger: 1m close > 1m open (bullish) and 1m RSI hook
        # Find 1m bars after bt
        # bt is 5m close time, next 1m bar starts at bt + 1 min
        nxt=df1.loc[bt: bt + pd.Timedelta(minutes=5)]
        # nxt includes bt itself, skip it
        nxt=nxt.loc[bt + pd.Timedelta(minutes=1):]
        if len(nxt) < 1: continue
        # Take first 1m bullish bar
        entry=None
        for _, row in nxt.head(3).iterrows():
            # 1m RSI hook check
            t=row.name
            # get 1m RSI at t
            try:
                rsi1_0=rsi1.loc[t]
                rsi1_prev=rsi1.loc[t - pd.Timedelta(minutes=1)]
            except: continue
            bullish = row["close"] > row["open"]
            bearish = row["close"] < row["open"]
            if longSetup and bullish and rsi1_0 > rsi1_prev:
                entry=t
                break
            if shortSetup and bearish and rsi1_0 < rsi1_prev:
                entry=t
                break
        if entry is not None:
            sigs.append((bt, entry, "LONG" if longSetup else "SHORT"))
    return sigs

for bb,sd in [(20,1.8),(20,2.0)]:
    sigs=hybrid_signals(df1,df5,bb,sd,25)
    print(f"Hybrid 5m->1m bb{bb} sd{sd} adx25: {len(sigs)} signals ({len(sigs)/19:.1f}/mo) sample {sigs[:3]}")

# For comparison, pure 5m signals
close5=df5["close"]; high5=df5["high"]; low5=df5["low"]
sma=close5.rolling(20).mean(); st=close5.rolling(20).std()
upper=sma+1.8*st; lower=sma-1.8*st
rsi5=_wilder_rsi(close5,14); adx5=_adx(high5,low5,close5,14)
pure=[]
for i in range(25, len(df5)):
    bt=df5.index[i]
    if not (bt.time() >= pd.Timestamp("11:30:00").time() and bt.time() < pd.Timestamp("16:00:00").time()): continue
    if bt.weekday()>=5: continue
    c0=close5.iloc[i]; c1=close5.iloc[i-1]; u0=upper.iloc[i]; l0=lower.iloc[i]; u1=upper.iloc[i-1]; l1=lower.iloc[i-1]; m0=sma.iloc[i]
    r0=rsi5.iloc[i]; r1=rsi5.iloc[i-1]; a0=adx5.iloc[i]
    if pd.isna(u0) or pd.isna(r0): continue
    if a0>=25: continue
    longSetup = (c1 < l1 and r1 < 33 and c0 > l0 and r0 > r1 and c0 < m0 and r0 < 50)
    shortSetup = (c1 > u1 and r1 > 67 and c0 < u0 and r0 < r1 and c0 > m0 and r0 > 50)
    if longSetup or shortSetup: pure.append(bt)
print(f"Pure 5m bb20 1.8: {len(pure)} signals")

# Full backtest for hybrid with engine
# For hybrid, we need to adapt BacktestEngine to use 1m entry time
# Simulate hybrid by creating TradeSignal at entry time (1m) but with 5m-derived levels
from scripts.analysis.range_strategy_comparison import TradeSignal
import pandas as pd

def run_hybrid_full(bb=20, sd=1.8, adx_thr=25):
    df1_l, df5_l = load_nt()
    df_daily=df1_l.resample("D").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna()
    tr2=pd.concat([df_daily["high"]-df_daily["low"], (df_daily["high"]-df_daily["close"].shift(1)).abs(), (df_daily["low"]-df_daily["close"].shift(1)).abs()],axis=1).max(axis=1)
    daily_atr2=tr2.rolling(10, min_periods=1).mean()
    df1_l["trade_date"]=df1_l.index.date
    df1_l.loc[df1_l.index.hour>=18,"trade_date"]=(df1_l.loc[df1_l.index.hour>=18].index + pd.Timedelta(days=1)).date
    unique_dates=sorted(df1_l["trade_date"].unique())
    engine=BacktestEngine("ES", tick_size=0.25, entry_mode="limit")
    trades=[]
    close5=df5_l["close"]; high5=df5_l["high"]; low5=df5_l["low"]
    sma=close5.rolling(bb).mean(); st=close5.rolling(bb).std()
    upper=sma+sd*st; lower=sma-sd*st
    rsi5=_wilder_rsi(close5,14); adx5=_adx(high5,low5,close5,14)
    atr5=(high5.rolling(14).max()-low5.rolling(14).min())/14
    rsi1=_wilder_rsi(df1_l["close"],14)
    for t_date in unique_dates:
        ts=pd.Timestamp(t_date)
        if ts.weekday()>=5 or ts.year<2025: continue
        ctx=build_day_context(ts, df1_l, df5_l, daily_atr2, ib_minutes=30)
        if ctx is None: continue
        for sess in ["NY_MIDDAY","NY_PM"]:
            bars5=ctx.session_5m.get(sess)
            if bars5 is None or len(bars5)<25: continue
            # need to map to df5 index for indicator lookup
            for i in range(2, len(bars5)):
                bt=bars5.index[i]
                # get indicator values at bt from df5 series
                if bt not in close5.index: continue
                # use precomputed series via loc
                c0=close5.loc[bt]; c1=close5.loc[bars5.index[i-1]] if bars5.index[i-1] in close5.index else np.nan
                u0=upper.loc[bt] if bt in upper.index else np.nan
                l0=lower.loc[bt] if bt in lower.index else np.nan
                u1=upper.loc[bars5.index[i-1]] if bars5.index[i-1] in upper.index else np.nan
                l1=lower.loc[bars5.index[i-1]] if bars5.index[i-1] in lower.index else np.nan
                m0=sma.loc[bt] if bt in sma.index else np.nan
                r0=rsi5.loc[bt] if bt in rsi5.index else np.nan
                r1=rsi5.loc[bars5.index[i-1]] if bars5.index[i-1] in rsi5.index else np.nan
                a0=adx5.loc[bt] if bt in adx5.index else np.nan
                if pd.isna(u0) or pd.isna(r0): continue
                if a0 >= adx_thr: continue
                longSetup = (c1 < l1 and r1 < 33 and c0 > l0 and r0 > r1 and c0 < m0 and r0 < 50)
                shortSetup = (c1 > u1 and r1 > 67 and c0 < u0 and r0 < r1 and c0 > m0 and r0 > 50)
                if not (longSetup or shortSetup): continue
                # Find 1m entry
                nxt=df1_l.loc[bt + pd.Timedelta(minutes=1): bt + pd.Timedelta(minutes=5)]
                entry=None
                for t2,row in nxt.head(3).iterrows():
                    try:
                        r1_0=rsi1.loc[t2]; r1_prev=rsi1.loc[t2 - pd.Timedelta(minutes=1)]
                    except: continue
                    bullish=row["close"]>row["open"]; bearish=row["close"]<row["open"]
                    if longSetup and bullish and r1_0>r1_prev:
                        entry=t2; break
                    if shortSetup and bearish and r1_0<r1_prev:
                        entry=t2; break
                if entry is None: continue
                # Build signal at entry time
                atr=float(atr5.loc[bt]) if bt in atr5.index and not pd.isna(atr5.loc[bt]) else 8
                if longSetup:
                    sl=float(min(l0, df1_l.loc[entry,"close"]) - 1.5*atr) if not pd.isna(l0) else df1_l.loc[entry,"close"]-atr
                    entry_px=float(df1_l.loc[entry,"close"])
                    tp1=float(m0); tp2=float(u0)
                    risk=entry_px - sl
                    if risk<=0 or risk>50: continue
                    sig=TradeSignal("LONG", entry_px, sl, tp1, tp2, risk, entry, sess)
                else:
                    sl=float(max(u0, df1_l.loc[entry,"close"]) + 1.5*atr) if not pd.isna(u0) else df1_l.loc[entry,"close"]+atr
                    entry_px=float(df1_l.loc[entry,"close"])
                    tp1=float(m0); tp2=float(l0)
                    risk=sl - entry_px
                    if risk<=0 or risk>50: continue
                    sig=TradeSignal("SHORT", entry_px, sl, tp1, tp2, risk, entry, sess)
                sig.metadata["strategy_name"]="BB_MTF"
                tr=engine.simulate_trade(sig, ctx)
                if tr is not None:
                    trades.append(tr.__dict__)
                    break  # one per session like pure
    df=pd.DataFrame(trades)
    if df.empty:
        return dict(trades=0, wr=0, pf=0, net=0, dd=0)
    pnl=df["total_pnl_dollars"]; cum=pnl.cumsum(); dd=(cum-cum.cummax()).min()
    wr=(pnl>1).mean()*100; gp=pnl[pnl>0].sum(); gl=abs(pnl[pnl<0].sum()); pf=gp/gl if gl>0 else 999; net=cum.iloc[-1]
    return dict(trades=len(df), wr=round(wr,1), pf=round(pf,2), net=round(net), dd=round(abs(dd)))

for bb,sd in [(20,1.8),(20,2.0)]:
    res=run_hybrid_full(bb,sd,25)
    print(f"MTF Hybrid TF5m->1m bb{bb} sd{sd} adx25: {res}")

