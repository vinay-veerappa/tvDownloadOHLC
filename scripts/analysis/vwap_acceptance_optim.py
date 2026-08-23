"""VWAP acceptance optimizer — independent grid, own parameters (not BB harness)."""
import sys
sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")
import pandas as pd, numpy as np, itertools
from joblib import Parallel, delayed
from scripts.analysis.range_strategy_comparison import _adx, BacktestEngine, build_day_context

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

def prior_day_poc(trade_date, df1):
    prev = trade_date - pd.Timedelta(days=1)
    for off in range(1,5):
        cand = trade_date - pd.Timedelta(days=off)
        if cand.weekday() < 5: prev = cand; break
    rth = df1.loc[f"{prev} 09:30:00":f"{prev} 16:00:00"]
    if len(rth) < 30: return np.nan
    bucket = (rth["close"] // 1.0).astype(int)
    vol = rth.groupby(bucket)["volume"].sum()
    if vol.empty: return np.nan
    return vol.idxmax() * 1.0 + 0.5

def run_one(args):
    level, hold_bars, tol_atr, rvol_thr, target_r = args
    from scripts.analysis.range_strategy_comparison import TradeSignal
    trades=[]
    for t_date in unique_dates:
        ts=pd.Timestamp(t_date)
        if ts.weekday()>=5 or ts.year<2025: continue
        ctx=build_day_context(ts, DF1, DF5, daily_atr2, ib_minutes=30)
        if ctx is None: continue
        # trend skip: prior day range > 1.5*ATR
        try:
            dr = df_daily.loc[ts - pd.Timedelta(days=1), "high"] - df_daily.loc[ts - pd.Timedelta(days=1), "low"]
            atr = daily_atr2.loc[ts - pd.Timedelta(days=1)]
            if not np.isnan(dr) and not np.isnan(atr) and dr > 1.5*atr: continue
        except: pass
        poc = prior_day_poc(ts, DF1)
        for sess in ["NY_MIDDAY","NY_PM"]:
            bars5=ctx.session_5m.get(sess)
            if bars5 is None or len(bars5)<20: continue
            vwap=ctx.progressive_vwap.get(sess)
            if vwap is None: continue
            close=bars5["close"]; high=bars5["high"]; low=bars5["low"]
            vol=bars5["volume"]
            atr=float(ctx.atr_val) if not np.isnan(ctx.atr_val) and ctx.atr_val>0 else 20.0
            atr5=(high.rolling(14).max()-low.rolling(14).min())/14
            hold_count=0; last_hold_vol=0; last_long=-1000; last_short=-1000
            for i in range(2, len(bars5)):
                ct=bars5.index[i]
                if ct.time() < pd.Timestamp("11:30:00").time(): continue
                if 13 <= ct.hour < 14: continue
                vw=vwap.loc[ct] if ct in vwap.index else np.nan
                if np.isnan(vw): continue
                a5=atr5.iloc[i]
                if np.isnan(a5) or a5<=0: a5=atr/6
                # zone selection
                if level=="poc":
                    if np.isnan(poc): continue
                    z=poc
                elif level=="vwap":
                    z=vw
                else:  # both: cluster if within 1 ATR
                    if np.isnan(poc): z=vw
                    elif abs(poc-vw) <= 1.0*a5: z=(poc+vw)/2
                    else: z=vw
                c0=close.iloc[i]
                near_zone = abs(c0 - z) <= tol_atr*a5
                if near_zone:
                    hold_count += 1
                    last_hold_vol = vol.iloc[i]
                else:
                    hold_count = 0
                accepted = hold_count >= hold_bars and vol.iloc[i] > last_hold_vol*0.9
                if rvol_thr > 0:
                    avg_vol=vol.rolling(20).mean().iloc[i]
                    if vol.iloc[i] < rvol_thr*avg_vol: accepted=False
                if accepted and i - last_long > 10:
                    entry=float(c0); sl=float(z - 1.0*a5); risk=entry-sl
                    if risk<=0 or risk>0.70*atr: continue
                    tp1=float(entry + 1.0*risk); tp2=float(entry + target_r*risk)
                    sig=TradeSignal("LONG", entry, sl, tp1, tp2, risk, ct, sess); sig.metadata["strategy_name"]="VWAP_Acc"
                    engine=BacktestEngine("ES", tick_size=0.25, entry_mode="limit")
                    tr=engine.simulate_trade(sig, ctx)
                    if tr is not None: trades.append(tr.__dict__); last_long=i; break
                elif accepted and i - last_short > 10:
                    last_short=i
                    entry=float(c0); sl=float(z + 1.0*a5); risk=sl-entry
                    if risk<=0 or risk>0.70*atr: continue
                    tp1=float(entry - 1.0*risk); tp2=float(entry - target_r*risk)
                    sig=TradeSignal("SHORT", entry, sl, tp1, tp2, risk, ct, sess); sig.metadata["strategy_name"]="VWAP_Acc"
                    engine=BacktestEngine("ES", tick_size=0.25, entry_mode="limit")
                    tr=engine.simulate_trade(sig, ctx)
                    if tr is not None: trades.append(tr.__dict__); break
    df=pd.DataFrame(trades)
    if df.empty: return dict(level=level,hold=hold_bars,tol=tol_atr,rvol=rvol_thr,target=target_r,trades=0,wr=0,pf=0,net=0,dd=0)
    pnl=df["total_pnl_dollars"]; cum=pnl.cumsum(); dd=(cum-cum.cummax()).min()
    wr=(pnl>1).mean()*100; gp=pnl[pnl>0].sum(); gl=abs(pnl[pnl<0].sum()); pf=gp/gl if gl>0 else 999; net=cum.iloc[-1]
    return dict(level=level,hold=hold_bars,tol=tol_atr,rvol=rvol_thr,target=target_r,trades=len(df),wr=round(wr,1),pf=round(pf,2),net=round(net),dd=round(abs(dd)))

if __name__=="__main__":
    grid=list(itertools.product(["poc","vwap","both"],[2,3,4],[0.3,0.5,0.7],[1.0,1.5],[1.5,2.0,2.5]))
    print(f"VWAP acceptance grid: {len(grid)} arms, 8 workers")
    results=Parallel(n_jobs=8, backend="loky", verbose=5)(delayed(run_one)(a) for a in grid)
    df=pd.DataFrame(results).sort_values(["pf","net"],ascending=False)
    print(df.head(15).to_string(index=False))
    df.to_csv("data/derived/vwap_acceptance_grid.csv", index=False)
    print("Saved data/derived/vwap_acceptance_grid.csv")
