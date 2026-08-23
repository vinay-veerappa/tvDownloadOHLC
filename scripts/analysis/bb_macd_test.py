import sys
sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")
import pandas as pd, numpy as np
from scripts.analysis.range_strategy_comparison import _wilder_rsi, _adx, BacktestEngine, build_day_context

def macd(close, fast=12, slow=26, signal=9):
    ema_fast=close.ewm(span=fast, adjust=False).mean()
    ema_slow=close.ewm(span=slow, adjust=False).mean()
    line=ema_fast-ema_slow
    sig=line.ewm(span=signal, adjust=False).mean()
    hist=line-sig
    return line, sig, hist

def load_nt(sym="ES"):
    df1=pd.read_csv(f"data/derived/nt_{sym.lower()}_09_26_1m_2025_2026_mergeBA.csv", parse_dates=["time"]).set_index("time").sort_index()
    df5=pd.read_csv(f"data/derived/nt_{sym.lower()}_09_26_5m_2025_2026_mergeBA.csv", parse_dates=["time"]).set_index("time").sort_index()
    return df1[(df1.index.year>=2025)&(df1.index.year<=2026)], df5[(df5.index.year>=2025)&(df5.index.year<=2026)]

DF1,DF5=load_nt("ES")
df_daily=DF1.resample("D").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna()
tr2=pd.concat([df_daily["high"]-df_daily["low"], (df_daily["high"]-df_daily["close"].shift(1)).abs(), (df_daily["low"]-df_daily["close"].shift(1)).abs()],axis=1).max(axis=1)
daily_atr2=tr2.rolling(10, min_periods=1).mean()
DF1["trade_date"]=DF1.index.date
DF1.loc[DF1.index.hour>=18,"trade_date"]=(DF1.loc[DF1.index.hour>=18].index + pd.Timedelta(days=1)).date
unique_dates=sorted(DF1["trade_date"].unique())

def run(use_macd=False):
    from scripts.analysis.range_strategy_comparison import TradeSignal
    trades=[]
    for t_date in unique_dates:
        ts=pd.Timestamp(t_date)
        if ts.weekday()>=5 or ts.year<2025: continue
        ctx=build_day_context(ts, DF1, DF5, daily_atr2, ib_minutes=30)
        if ctx is None: continue
        if ctx.ib_range >= 0.40*ctx.atr_val: continue
        for sess in ["NY_MIDDAY","NY_PM"]:
            bars5=ctx.session_5m.get(sess)
            if bars5 is None or len(bars5)<30: continue
            close=bars5["close"]; high=bars5["high"]; low=bars5["low"]
            sma=close.rolling(20).mean(); std=close.rolling(20).std()
            upper=sma+1.8*std; lower=sma-1.8*std
            rsi=_wilder_rsi(close,14); adx_s=_adx(high,low,close,14)
            macd_line, macd_sig, macd_hist = macd(close)
            atr=float(ctx.atr_val) if not np.isnan(ctx.atr_val) and ctx.atr_val>0 else 20.0
            for i in range(2, len(bars5)):
                ct=bars5.index[i]
                if ct.time() < pd.Timestamp("11:30:00").time() or (13 <= ct.hour < 14): continue
                a0=adx_s.iloc[i]
                if not np.isnan(a0) and a0 >= 25: continue
                c0=close.iloc[i]; c1=close.iloc[i-1]; u0=upper.iloc[i]; l0=lower.iloc[i]; u1=upper.iloc[i-1]; l1=lower.iloc[i-1]; m0=sma.iloc[i]
                r0=rsi.iloc[i]; r1=rsi.iloc[i-1]
                if pd.isna(u0) or pd.isna(r0): continue
                longSetup = (c1 < l1 and r1 < 33 and c0 > l0 and r0 > r1 and c0 < m0 and r0 < 50)
                shortSetup = (c1 > u1 and r1 > 67 and c0 < u0 and r0 < r1 and c0 > m0 and r0 > 50)
                if use_macd and (longSetup or shortSetup):
                    ml=macd_line.iloc[i]; ms=macd_sig.iloc[i]; mh=macd_hist.iloc[i]; ml_prev=macd_line.iloc[i-1]
                    # MACD bullish divergence for longs: histogram rising and line > signal
                    # Simplified: require MACD histogram >0 and rising for longs, <0 and falling for shorts
                    if longSetup and not (mh > macd_hist.iloc[i-1]): continue
                    if shortSetup and not (mh < macd_hist.iloc[i-1]): continue
                if not (longSetup or shortSetup): continue
                if longSetup:
                    entry=float(c0); atr5=float((high.rolling(14).max()-low.rolling(14).min()).iloc[i]/14) if len(bars5)>20 else atr/6
                    if np.isnan(atr5) or atr5<=0: atr5=atr/6
                    sl=float(min(l0,c0)-1.2*atr5); sl=min(sl, entry-1.0*atr5); risk=entry-sl
                    if risk<=0 or risk>0.70*atr: continue
                    tp1=float(m0); tp2=float(u0)
                    if tp1<=entry: continue
                    sig=TradeSignal("LONG", entry, sl, tp1, tp2, risk, ct, sess); sig.metadata["strategy_name"]="BB_MACD"
                    engine=BacktestEngine("ES", tick_size=0.25, entry_mode="limit")
                    tr=engine.simulate_trade(sig, ctx)
                    if tr is not None: trades.append(tr.__dict__); break
                elif shortSetup:
                    entry=float(c0); atr5=float((high.rolling(14).max()-low.rolling(14).min()).iloc[i]/14) if len(bars5)>20 else atr/6
                    if np.isnan(atr5) or atr5<=0: atr5=atr/6
                    sl=float(max(u0,c0)+1.2*atr5); sl=max(sl, entry+1.0*atr5); risk=sl-entry
                    if risk<=0 or risk>0.70*atr: continue
                    tp1=float(m0); tp2=float(l0)
                    if tp1>=entry: continue
                    sig=TradeSignal("SHORT", entry, sl, tp1, tp2, risk, ct, sess); sig.metadata["strategy_name"]="BB_MACD"
                    engine=BacktestEngine("ES", tick_size=0.25, entry_mode="limit")
                    tr=engine.simulate_trade(sig, ctx)
                    if tr is not None: trades.append(tr.__dict__); break
    df=pd.DataFrame(trades)
    if df.empty: return dict(trades=0, wr=0, pf=0, net=0, dd=0)
    pnl=df["total_pnl_dollars"]; cum=pnl.cumsum(); dd=(cum-cum.cummax()).min()
    wr=(pnl>1).mean()*100; gp=pnl[pnl>0].sum(); gl=abs(pnl[pnl<0].sum()); pf=gp/gl if gl>0 else 999; net=cum.iloc[-1]
    return dict(trades=len(df), wr=round(wr,1), pf=round(pf,2), net=round(net), dd=round(abs(dd)))

for use_macd in [False, True]:
    res=run(use_macd=use_macd)
    label="BB+MACD hist" if use_macd else "BB RSI base (IB+Lunch)"
    print(f"{label}: {res}")
