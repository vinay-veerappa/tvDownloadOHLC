import sys
sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")
import pandas as pd, numpy as np
from scripts.analysis.range_strategy_comparison import _wilder_rsi, _adx, BBRsiMeanReversionStrategy, BacktestEngine, build_day_context

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

# Pick two arms to contrast: winner (bb20 2.2 sq, 11 trades PF1.19) and frequent loser (bb14 1.8 no-sq, 337 trades PF0.77)
for label, bb,sd,adx_thr,rsi_long,sq in [("WINNER bb20 2.2 sq",20,2.2,25,30,True), ("LOSER bb14 1.8 no-sq",14,1.8,25,30,False)]:
    strat=BBRsiMeanReversionStrategy("ES", tick_size=0.25, bb_period=bb, std_dev=sd, rsi_period=14, adx_threshold=adx_thr, use_adx=True, squeeze_only=sq, squeeze_pct=30)
    # patch rsi threshold
    orig_rsi_long=rsi_long
    # monkey patch detect to use rsi_long
    import types
    from scripts.analysis.range_strategy_comparison import _wilder_rsi as wr, _adx as adxfn
    def make_patched(_rsi_long):
        def patched(ctx, sess):
            if sess not in ("NY_MIDDAY","NY_PM"): return None
            if strat.squeeze_only and not strat._is_squeeze_day(ctx): return None
            bars5=ctx.session_5m.get(sess)
            if bars5 is None or len(bars5) < strat.bb_period+10: return None
            close=bars5["close"]; high=bars5["high"]; low=bars5["low"]
            sma=close.rolling(strat.bb_period).mean(); std=close.rolling(strat.bb_period).std()
            upper=sma+strat.std_dev*std; lower=sma-strat.std_dev*std
            rsi=wr(close, strat.rsi_period); adx_s=adxfn(high,low,close,14)
            atr=float(ctx.atr_val) if not np.isnan(ctx.atr_val) and ctx.atr_val>0 else 20.0
            for i in range(2, len(bars5)):
                ct=bars5.index[i]
                if ct.time() < pd.Timestamp("11:30:00").time(): continue
                adx_val=adx_s.iloc[i]
                if strat.use_adx and not np.isnan(adx_val) and adx_val >= strat.adx_threshold: continue
                longSetup = (close.iloc[i-1] < lower.iloc[i-1] and rsi.iloc[i-1] < _rsi_long and close.iloc[i] > lower.iloc[i] and rsi.iloc[i] > rsi.iloc[i-1] and close.iloc[i] < sma.iloc[i] and rsi.iloc[i] < 50)
                if longSetup:
                    entry=float(close.iloc[i]); atr5=float((high.rolling(14).max()-low.rolling(14).min()).iloc[i]/14) if len(bars5)>20 else atr/6
                    if np.isnan(atr5) or atr5<=0: atr5=atr/6
                    sl=float(min(lower.iloc[i], close.iloc[i]) - 1.2*atr5); sl=min(sl, entry-1.0*atr5); risk=entry-sl
                    if risk<=0 or risk>(0.70*atr): continue
                    tp1=float(sma.iloc[i]); tp2=float(upper.iloc[i])
                    if tp1 <= entry: continue
                    from scripts.analysis.range_strategy_comparison import TradeSignal
                    return TradeSignal("LONG", entry, sl, tp1, tp2, risk, ct, sess, metadata={"rsi":float(rsi.iloc[i]), "adx":float(adx_val), "bw":float((upper.iloc[i]-lower.iloc[i])/sma.iloc[i]) if sma.iloc[i]!=0 else 0})
                short_thr=67 if _rsi_long==33 else 70
                # for 30 use 70
                short_thr=70
                shortSetup = (close.iloc[i-1] > upper.iloc[i-1] and rsi.iloc[i-1] > short_thr and close.iloc[i] < upper.iloc[i] and rsi.iloc[i] < rsi.iloc[i-1] and close.iloc[i] > sma.iloc[i] and rsi.iloc[i] > 50)
                if shortSetup:
                    entry=float(close.iloc[i]); atr5=float((high.rolling(14).max()-low.rolling(14).min()).iloc[i]/14) if len(bars5)>20 else atr/6
                    if np.isnan(atr5) or atr5<=0: atr5=atr/6
                    sl=float(max(upper.iloc[i], close.iloc[i]) + 1.2*atr5); sl=max(sl, entry+1.0*atr5); risk=sl-entry
                    if risk<=0 or risk>(0.70*atr): continue
                    tp1=float(sma.iloc[i]); tp2=float(lower.iloc[i])
                    if tp1 >= entry: continue
                    from scripts.analysis.range_strategy_comparison import TradeSignal
                    return TradeSignal("SHORT", entry, sl, tp1, tp2, risk, ct, sess, metadata={"rsi":float(rsi.iloc[i]), "adx":float(adx_val), "bw":float((upper.iloc[i]-lower.iloc[i])/sma.iloc[i]) if sma.iloc[i]!=0 else 0})
            return None
        return patched
    strat.detect_signal = make_patched(rsi_long)
    engine=BacktestEngine("ES", tick_size=0.25, entry_mode="limit")
    trades=[]
    for t_date in unique_dates:
        ts=pd.Timestamp(t_date)
        if ts.weekday()>=5 or ts.year<2025: continue
        ctx=build_day_context(ts, DF1, DF5, daily_atr2, ib_minutes=30)
        if ctx is None: continue
        for sess in strat.get_active_sessions():
            sig=strat.detect_signal(ctx, sess)
            if sig is None: continue
            sig.metadata["strategy_name"]=strat.name
            tr=engine.simulate_trade(sig, ctx)
            if tr is not None:
                # enrich with context
                tr_dict=tr.__dict__.copy()
                tr_dict["rsi_entry"]=sig.metadata.get("rsi")
                tr_dict["adx_entry"]=sig.metadata.get("adx")
                tr_dict["bw_entry"]=sig.metadata.get("bw")
                # add IB range, VWAP distance, session
                tr_dict["ib_range"]=ctx.ib_range
                tr_dict["atr"]=ctx.atr_val
                tr_dict["hour"]=pd.Timestamp(tr.entry_time).hour + pd.Timestamp(tr.entry_time).minute/60
                trades.append(tr_dict)
                break
    df=pd.DataFrame(trades)
    if df.empty:
        print(f"\n{label}: 0 trades")
        continue
    print(f"\n{'='*80}\n{label}: {len(df)} trades WR{(df['total_pnl_dollars']>1).mean()*100:.1f}% PF{(df[df['total_pnl_dollars']>0]['total_pnl_dollars'].sum()/abs(df[df['total_pnl_dollars']<0]['total_pnl_dollars'].sum()) if (df['total_pnl_dollars']<0).any() else 999):.2f}")
    # Failure breakdown
    df["is_win"]=df["total_pnl_dollars"]>1
    df["is_loss"]=~df["is_win"]
    # Tag failures
    print("Loss rate by hour:")
    print(df.groupby(pd.cut(df["hour"], bins=[11,12,13,14,15,16]))["is_loss"].mean().to_string())
    print("Loss rate by ADX bucket:")
    print(df.groupby(pd.cut(df["adx_entry"], bins=[0,15,20,25,30,50]))["is_loss"].mean().to_string())
    print("Loss rate by BW bucket:")
    print(df.groupby(pd.cut(df["bw_entry"], bins=5))["is_loss"].mean().to_string())
    print("Loss rate by direction:")
    print(df.groupby("direction")["is_loss"].mean().to_string())
    print("Avg loser vs winner R:")
    print(df.groupby("is_win")["r_multiple"].mean().to_string())
    print("T1 hit rate:", df["t1_hit"].mean(), "T2", df["t2_hit"].mean(), "stopped", df["stopped_out"].mean())
    # Show few losers with context
    losers=df[df["is_loss"]].head(3)[["date","direction","entry_time","rsi_entry","adx_entry","bw_entry","ib_range","atr","r_multiple","t1_hit"]]
    print("Sample losers:")
    print(losers.to_string(index=False))
