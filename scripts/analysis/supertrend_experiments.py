import sys
sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")
import pandas as pd, numpy as np
from scripts.analysis.range_strategy_comparison import _adx, BacktestEngine, build_day_context

def supertrend(high, low, close, period=10, mult=3.0):
    """Seban Supertrend. Returns +1 (long) / -1 (short) series."""
    hl2 = (high + low) / 2.0
    tr = pd.concat([high-low, (high-close.shift(1)).abs(), (low-close.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    upper = hl2 + mult*atr
    lower = hl2 - mult*atr
    # final bands: upper can't rise, lower can't fall
    fu = upper.copy(); fl = lower.copy()
    for i in range(1, len(upper)):
        if fu.iloc[i] > fu.iloc[i-1]: fu.iloc[i] = fu.iloc[i-1]
        if fl.iloc[i] < fl.iloc[i-1]: fl.iloc[i] = fl.iloc[i-1]
    st = pd.Series(np.nan, index=close.index)
    for i in range(1, len(close)):
        if close.iloc[i] > fu.iloc[i-1]:
            st.iloc[i] = 1
        elif close.iloc[i] < fl.iloc[i-1]:
            st.iloc[i] = -1
        else:
            st.iloc[i] = st.iloc[i-1]
    return st, fu, fl

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

def run(period=10, mult=3.0, use_regime=True, use_daily_filter=False, skip_lunch=True):
    from scripts.analysis.range_strategy_comparison import TradeSignal
    trades=[]
    for t_date in unique_dates:
        ts=pd.Timestamp(t_date)
        if ts.weekday()>=5 or ts.year<2025: continue
        ctx=build_day_context(ts, DF1, DF5, daily_atr2, ib_minutes=30)
        if ctx is None: continue
        if use_regime and ctx.ib_range >= 0.40*ctx.atr_val: continue
        # daily ST filter: compute on daily closes up to prior day
        daily_up = True
        if use_daily_filter:
            try:
                dclose=df_daily.loc[:ts - pd.Timedelta(days=1), "close"]
                dhigh=df_daily.loc[:ts - pd.Timedelta(days=1), "high"]
                dlow=df_daily.loc[:ts - pd.Timedelta(days=1), "low"]
                if len(dclose) > 20:
                    dst,_,_ = supertrend(dhigh, dlow, dclose, 10, 3)
                    daily_up = dst.iloc[-1] == 1
            except: daily_up=True
        for sess in ["NY_AM","NY_MIDDAY","NY_PM"]:
            bars5=ctx.session_5m.get(sess)
            if bars5 is None or len(bars5)<period+5: continue
            close=bars5["close"]; high=bars5["high"]; low=bars5["low"]
            st, fu, fl = supertrend(high, low, close, period, mult)
            atr=float(ctx.atr_val) if not np.isnan(ctx.atr_val) and ctx.atr_val>0 else 20.0
            atr5=(high.rolling(14).max()-low.rolling(14).min())/14
            last_long=-1000; last_short=-1000
            for i in range(2, len(bars5)):
                ct=bars5.index[i]
                if ct.time() < pd.Timestamp("11:30:00").time(): continue
                if skip_lunch and 13 <= ct.hour < 14: continue
                a5=atr5.iloc[i]
                if np.isnan(a5) or a5<=0: a5=atr/6
                st0=st.iloc[i]; st1=st.iloc[i-1]
                if pd.isna(st0) or pd.isna(st1): continue
                # flip detection
                long_flip = st0==1 and st1==-1
                short_flip = st0==-1 and st1==1
                if use_daily_filter and not daily_up and long_flip: long_flip=False
                if use_daily_filter and daily_up and short_flip: short_flip=False
                c0=close.iloc[i]
                if long_flip and i - last_long > 10:
                    entry=float(c0); sl=float(c0 - 2.0*a5); risk=entry-sl
                    if risk<=0 or risk>0.70*atr: continue
                    tp1=float(c0 + 1.5*a5); tp2=float(c0 + 3.0*a5)
                    sig=TradeSignal("LONG", entry, sl, tp1, tp2, risk, ct, sess); sig.metadata["strategy_name"]="ST"
                    engine=BacktestEngine("ES", tick_size=0.25, entry_mode="limit")
                    tr=engine.simulate_trade(sig, ctx)
                    if tr is not None: trades.append(tr.__dict__); last_long=i; break
                elif short_flip and i - last_short > 10:
                    last_short=i
                    entry=float(c0); sl=float(c0 + 2.0*a5); risk=sl-entry
                    if risk<=0 or risk>0.70*atr: continue
                    tp1=float(c0 - 1.5*a5); tp2=float(c0 - 3.0*a5)
                    sig=TradeSignal("SHORT", entry, sl, tp1, tp2, risk, ct, sess); sig.metadata["strategy_name"]="ST"
                    engine=BacktestEngine("ES", tick_size=0.25, entry_mode="limit")
                    tr=engine.simulate_trade(sig, ctx)
                    if tr is not None: trades.append(tr.__dict__); break
    df=pd.DataFrame(trades)
    if df.empty: return dict(trades=0, wr=0, pf=0, net=0, dd=0)
    pnl=df["total_pnl_dollars"]; cum=pnl.cumsum(); dd=(cum-cum.cummax()).min()
    wr=(pnl>1).mean()*100; gp=pnl[pnl>0].sum(); gl=abs(pnl[pnl<0].sum()); pf=gp/gl if gl>0 else 999; net=cum.iloc[-1]
    return dict(trades=len(df), wr=round(wr,1), pf=round(pf,2), net=round(net), dd=round(abs(dd)))

if __name__=="__main__":
    import csv, pathlib, datetime
    rows=[]
    for label, kw in [("S01 ST(10,3) no-regime", {"use_regime":False}), ("S02 ST(10,3) regime", {"use_regime":True}), ("S03 +daily ST", {"use_regime":True,"use_daily_filter":True}), ("S04 ST(7,2)", {"period":7,"mult":2.0}), ("S05 ST(14,3)", {"period":14,"mult":3.0})]:
        res=run(**kw)
        print(f"{label}: {res}")
        rows.append((label,res))
    p=pathlib.Path("data/derived/supertrend_experiments_log.csv")
    if not p.exists():
        with open(p,"w",newline="") as f: csv.writer(f).writerow(["id","date","variant","trades","wr","pf","net","dd","mo_es"])
    with open(p,"a",newline="") as f:
        w=csv.writer(f); today=datetime.date.today().isoformat()
        for label,res in rows:
            w.writerow([label.split()[0], today, label, res["trades"], res["wr"], res["pf"], res["net"], res["dd"], round(res["trades"]/19,1)])
    print("logged")
