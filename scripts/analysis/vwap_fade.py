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

def _macd(close, fast=12, slow=26, signal=9):
    ef=close.ewm(span=fast, adjust=False).mean(); es=close.ewm(span=slow, adjust=False).mean()
    line=ef-es; sig=line.ewm(span=signal, adjust=False).mean()
    return line, sig, line-sig

def run(vwap_mult=1.5, use_regime=True, use_rvol=False, use_macd=False, reversal=True):
    """VWAP mean-reversion fade: price extends >vwap_mult*ATR from VWAP, first close back toward VWAP."""
    from scripts.analysis.range_strategy_comparison import TradeSignal
    trades=[]
    for t_date in unique_dates:
        ts=pd.Timestamp(t_date)
        if ts.weekday()>=5 or ts.year<2025: continue
        ctx=build_day_context(ts, DF1, DF5, daily_atr2, ib_minutes=30)
        if ctx is None: continue
        if use_regime and ctx.ib_range >= 0.40*ctx.atr_val: continue
        for sess in ["NY_MIDDAY","NY_PM"]:
            bars5=ctx.session_5m.get(sess)
            if bars5 is None or len(bars5)<20: continue
            vwap=ctx.progressive_vwap.get(sess)
            if vwap is None: continue
            close=bars5["close"]; high=bars5["high"]; low=bars5["low"]
            adx_s=_adx(high,low,close,14)
            macd_line, macd_sig, macd_hist=_macd(close)
            vol=bars5["volume"]
            atr=float(ctx.atr_val) if not np.isnan(ctx.atr_val) and ctx.atr_val>0 else 20.0
            atr5=(high.rolling(14).max()-low.rolling(14).min())/14
            last_long=-1000; last_short=-1000
            for i in range(2, len(bars5)):
                ct=bars5.index[i]
                if ct.time() < pd.Timestamp("11:30:00").time(): continue
                if 13 <= ct.hour < 14: continue
                a0=adx_s.iloc[i]
                if not np.isnan(a0) and a0 >= 25: continue
                vw=vwap.loc[ct] if ct in vwap.index else np.nan
                if np.isnan(vw): continue
                a5=atr5.iloc[i]
                if np.isnan(a5) or a5<=0: a5=atr/6
                c0=close.iloc[i]; c1=close.iloc[i-1]; h0=high.iloc[i]; l0=low.iloc[i]
                # Fade long: was extended below VWAP (c1 < vw - mult*a5), now first close back up (c0 > c1)
                long_fade = c1 < vw - vwap_mult*a5 and c0 > c1 and c0 < vw + 0.2*a5
                short_fade = c1 > vw + vwap_mult*a5 and c0 < c1 and c0 > vw - 0.2*a5
                if use_rvol:
                    avg_vol=vol.rolling(20).mean().iloc[i]
                    if vol.iloc[i] < 1.5*avg_vol: long_fade = short_fade = False
                if use_macd:
                    mh=macd_hist.iloc[i]; mh_prev=macd_hist.iloc[i-1]
                    if long_fade and not (mh > mh_prev): long_fade=False
                    if short_fade and not (mh < mh_prev): short_fade=False
                if long_fade and i - last_long > 15:
                    entry=float(c0); sl=float(min(l0, c0) - 1.5*a5); risk=entry-sl
                    if risk<=0 or risk>0.70*atr: continue
                    tp1=float(vw); tp2=float(vw)+1.5*a5
                    if tp1<=entry: continue
                    sig=TradeSignal("LONG", entry, sl, tp1, tp2, risk, ct, sess); sig.metadata["strategy_name"]="VWAP_Fade"
                    engine=BacktestEngine("ES", tick_size=0.25, entry_mode="limit")
                    tr=engine.simulate_trade(sig, ctx)
                    if tr is not None: trades.append(tr.__dict__); last_long=i; break
                elif short_fade and i - last_short > 15:
                    last_short=i
                    entry=float(c0); sl=float(max(h0, c0) + 1.5*a5); risk=sl-entry
                    if risk<=0 or risk>0.70*atr: continue
                    tp1=float(vw); tp2=float(vw)-1.5*a5
                    if tp1>=entry: continue
                    sig=TradeSignal("SHORT", entry, sl, tp1, tp2, risk, ct, sess); sig.metadata["strategy_name"]="VWAP_Fade"
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
    for label, kw in [("F01 base 1.5x", {"vwap_mult":1.5}), ("F02 +RVOL", {"use_rvol":True}), ("F03 +MACD", {"use_macd":True}), ("F04 1.0x", {"vwap_mult":1.0}), ("F05 2.0x", {"vwap_mult":2.0})]:
        res=run(**kw)
        print(f"{label}: {res}")
        rows.append((label,res))
    p=pathlib.Path("data/derived/vwap_experiments_log.csv")
    if not p.exists():
        with open(p,"w",newline="") as f: csv.writer(f).writerow(["id","date","variant","trades","wr","pf","net","dd","mo_es"])
    with open(p,"a",newline="") as f:
        w=csv.writer(f)
        today=datetime.date.today().isoformat()
        for label,res in rows:
            w.writerow([label.split()[0], today, label, res["trades"], res["wr"], res["pf"], res["net"], res["dd"], round(res["trades"]/19,1)])
    print("logged")
