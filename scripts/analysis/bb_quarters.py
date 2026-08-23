import sys
sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")
import pandas as pd, numpy as np
from scripts.analysis.range_strategy_comparison import _wilder_rsi, _adx, BacktestEngine, build_day_context

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

def is_quarter_level(price, grid=25.0, tol_ticks=4, tick=0.25):
    # ES quarters: price % 25 in {0, 25/4=6.25? Actually 25 handles: 00,25,50,75? For ES grid 25, quarters are 0,6.25,12.5,18.75? But Bandits uses GridUnit 25 with 00,20,50,80 nodes (80/20 subgrid). Simpler: use 5 point quarters? Use 00/12.5/25?
    # Use GridUnit 25: levels are baseHandle + 0, 5,12.5,20? For ES, Bandits GridUnit 25, nodes 20 and 80 are 5 pts from handle. For quarters, use 0, 6.25,12.5,18.75 (quarter of 25)
    base=np.floor(price / grid) * grid
    quarters=[base, base+grid*0.25, base+grid*0.5, base+grid*0.75, base+grid]
    tol=tol_ticks*tick
    return any(abs(price - q) <= tol for q in quarters)

def run(use_quarters=False):
    from scripts.analysis.range_strategy_comparison import TradeSignal
    trades=[]
    for t_date in unique_dates:
        ts=pd.Timestamp(t_date)
        if ts.weekday()>=5 or ts.year<2025: continue
        ctx=build_day_context(ts, DF1, DF5, daily_atr2, ib_minutes=30)
        if ctx is None: continue
        for sess in ["NY_MIDDAY","NY_PM"]:
            bars5=ctx.session_5m.get(sess)
            if bars5 is None or len(bars5)<25: continue
            close=bars5["close"]; high=bars5["high"]; low=bars5["low"]
            sma=close.rolling(20).mean(); std=close.rolling(20).std()
            upper=sma+1.8*std; lower=sma-1.8*std
            rsi=_wilder_rsi(close,14); adx_s=_adx(high,low,close,14)
            atr=float(ctx.atr_val) if not np.isnan(ctx.atr_val) and ctx.atr_val>0 else 20.0
            for i in range(2, len(bars5)):
                ct=bars5.index[i]
                if ct.time() < pd.Timestamp("11:30:00").time(): continue
                a0=adx_s.iloc[i]
                if not np.isnan(a0) and a0 >= 25: continue
                c0=close.iloc[i]; c1=close.iloc[i-1]; u0=upper.iloc[i]; l0=lower.iloc[i]; u1=upper.iloc[i-1]; l1=lower.iloc[i-1]; m0=sma.iloc[i]
                r0=rsi.iloc[i]; r1=rsi.iloc[i-1]
                if pd.isna(u0) or pd.isna(r0): continue
                longSetup = (c1 < l1 and r1 < 33 and c0 > l0 and r0 > r1 and c0 < m0 and r0 < 50)
                shortSetup = (c1 > u1 and r1 > 67 and c0 < u0 and r0 < r1 and c0 > m0 and r0 > 50)
                if use_quarters and (longSetup or shortSetup):
                    # require band tag near quarter
                    lvl = l0 if longSetup else u0
                    if not is_quarter_level(lvl, grid=25, tol_ticks=6): continue
                if not (longSetup or shortSetup): continue
                if longSetup:
                    entry=float(c0); atr5=float((high.rolling(14).max()-low.rolling(14).min()).iloc[i]/14) if len(bars5)>20 else atr/6
                    if np.isnan(atr5) or atr5<=0: atr5=atr/6
                    sl=float(min(l0,c0)-1.2*atr5); sl=min(sl, entry-1.0*atr5); risk=entry-sl
                    if risk<=0 or risk>0.70*atr: continue
                    tp1=float(m0); tp2=float(u0)
                    if tp1<=entry: continue
                    sig=TradeSignal("LONG", entry, sl, tp1, tp2, risk, ct, sess); sig.metadata["strategy_name"]="BB_Q"
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
                    sig=TradeSignal("SHORT", entry, sl, tp1, tp2, risk, ct, sess); sig.metadata["strategy_name"]="BB_Q"
                    engine=BacktestEngine("ES", tick_size=0.25, entry_mode="limit")
                    tr=engine.simulate_trade(sig, ctx)
                    if tr is not None: trades.append(tr.__dict__); break
    df=pd.DataFrame(trades)
    if df.empty: return dict(trades=0, wr=0, pf=0, net=0)
    pnl=df["total_pnl_dollars"]; cum=pnl.cumsum(); dd=(cum-cum.cummax()).min()
    wr=(pnl>1).mean()*100; gp=pnl[pnl>0].sum(); gl=abs(pnl[pnl<0].sum()); pf=gp/gl if gl>0 else 999; net=cum.iloc[-1]
    return dict(trades=len(df), wr=round(wr,1), pf=round(pf,2), net=round(net), dd=round(abs(dd)))

for use_q in [False, True]:
    res=run(use_quarters=use_q)
    print(f"Quarters={use_q}: {res}")
