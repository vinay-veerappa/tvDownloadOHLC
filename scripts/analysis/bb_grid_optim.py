"""Parallel BB grid optimizer — 48 arms on shared NT MergeBA ES+NQ 2025-2026."""
import sys
sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")
import itertools, pandas as pd, numpy as np
from joblib import Parallel, delayed
from scripts.analysis.range_strategy_comparison import _wilder_rsi, _adx, BBRsiMeanReversionStrategy, BacktestEngine, build_day_context

def load_nt(sym):
    df1=pd.read_csv(f"data/derived/nt_{sym.lower()}_09_26_1m_2025_2026_mergeBA.csv", parse_dates=["time"]).set_index("time").sort_index()
    df5=pd.read_csv(f"data/derived/nt_{sym.lower()}_09_26_5m_2025_2026_mergeBA.csv", parse_dates=["time"]).set_index("time").sort_index()
    df1=df1[(df1.index.year>=2025)&(df1.index.year<=2026)]
    df5=df5[(df5.index.year>=2025)&(df5.index.year<=2026)]
    return df1, df5

# Pre-load both symbols once (broadcast to workers via closure pickling is ok for 550k rows ~ 30MB)
DF1_ES, DF5_ES = load_nt("ES")
# Try NQ, fallback to ES if NQ file missing (not exported yet)
try:
    DF1_NQ, DF5_NQ = load_nt("NQ")
    HAS_NQ=True
    print(f"Loaded NQ: {len(DF1_NQ)} 1m, {len(DF5_NQ)} 5m")
except Exception as e:
    HAS_NQ=False
    print(f"NQ not found: {e}, using ES only")

print(f"Loaded ES: {len(DF1_ES)} 1m, {len(DF5_ES)} 5m")

def run_one(args):
    bb, sd, adx_thr, rsi_long, atr_mult, squeeze_pct = args
    # Use ES+NQ pooled if available, else ES
    total_trades=[]
    for sym, DF1, DF5 in ([("ES", DF1_ES, DF5_ES)] + ([("NQ", DF1_NQ, DF5_NQ)] if HAS_NQ else [])):
        df_daily=DF1.resample("D").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna()
        tr2=pd.concat([df_daily["high"]-df_daily["low"], (df_daily["high"]-df_daily["close"].shift(1)).abs(), (df_daily["low"]-df_daily["close"].shift(1)).abs()],axis=1).max(axis=1)
        daily_atr2=tr2.rolling(10, min_periods=1).mean()
        # need copy for trade_date
        DF1c=DF1.copy()
        DF1c["trade_date"]=DF1c.index.date
        DF1c.loc[DF1c.index.hour>=18,"trade_date"]=(DF1c.loc[DF1c.index.hour>=18].index + pd.Timedelta(days=1)).date
        unique_dates=sorted(DF1c["trade_date"].unique())
        # patch atr_mult via monkey: BBRsi uses atr5 internally, not daily_atr, but risk cap uses ctx.atr_val (daily)
        # For atr_mult sweep we need to override GetCustomStopPrice? Instead pass via strat param and hack atr_mult scaling
        # Simplest: after strat creation, monkey patch its atr multiplier by wrapping GetCustomStopPrice
        squeeze_only = squeeze_pct is not None
        strat=BBRsiMeanReversionStrategy(sym, tick_size=0.25, bb_period=bb, std_dev=sd, rsi_period=14, adx_threshold=adx_thr, use_adx=True, squeeze_only=squeeze_only, squeeze_pct=squeeze_pct if squeeze_only else 30)
        # Monkey patch rsi thresholds: strat uses hardcoded 33/67, we need variable rsi_long
        # Patch by replacing detect_signal logic via closure: we can't easily, so we set attributes and hack detect
        strat._rsi_long = rsi_long
        strat._rsi_short = 70 if rsi_long==33 else 67  # mirror
        strat._atr_mult = atr_mult
        # Override detect_signal to use custom thresholds
        orig_detect = strat.detect_signal
        def patched_detect(ctx, sess, _orig=orig_detect, _rsi_long=rsi_long, _atr_mult=atr_mult):
            from scripts.analysis.range_strategy_comparison import _wilder_rsi, _adx
            import numpy as np
            if sess not in ("NY_MIDDAY","NY_PM"): return None
            if _rsi_long is not None and strat.squeeze_only and not strat._is_squeeze_day(ctx): return None
            bars5=ctx.session_5m.get(sess)
            if bars5 is None or len(bars5) < strat.bb_period + 10: return None
            close=bars5["close"]; high=bars5["high"]; low=bars5["low"]
            sma=close.rolling(strat.bb_period).mean(); std=close.rolling(strat.bb_period).std()
            upper=sma+strat.std_dev*std; lower=sma-strat.std_dev*std
            rsi=_wilder_rsi(close, strat.rsi_period); adx_s=_adx(high,low,close,14)
            atr=float(ctx.atr_val) if not np.isnan(ctx.atr_val) and ctx.atr_val>0 else 20.0
            for i in range(2, len(bars5)):
                ct=bars5.index[i]
                if ct.time() < pd.Timestamp("11:30:00").time(): continue
                adx_val=adx_s.iloc[i]
                if strat.use_adx and not np.isnan(adx_val) and adx_val >= strat.adx_threshold: continue
                long_setup = (close.iloc[i-1] < lower.iloc[i-1] and rsi.iloc[i-1] < _rsi_long and close.iloc[i] > lower.iloc[i] and rsi.iloc[i] > rsi.iloc[i-1] and close.iloc[i] < sma.iloc[i] and rsi.iloc[i] < 50)
                if longSetup:=long_setup:
                    entry=float(close.iloc[i])
                    atr5=float((high.rolling(14).max()-low.rolling(14).min()).iloc[i]/14) if len(bars5)>20 else atr/6
                    if np.isnan(atr5) or atr5<=0: atr5=atr/6
                    sl=float(min(lower.iloc[i], close.iloc[i]) - _atr_mult*atr5)
                    sl=min(sl, entry - 1.0*atr5)
                    risk=entry - sl
                    if risk<=0 or risk>(0.70*atr): continue
                    tp1=float(sma.iloc[i]); tp2=float(upper.iloc[i])
                    if tp1 <= entry: continue
                    from scripts.analysis.range_strategy_comparison import TradeSignal
                    return TradeSignal("LONG", entry, sl, tp1, tp2, risk, ct, sess, metadata={"rsi":float(rsi.iloc[i])})
                short_thr = 67 if _rsi_long==33 else 70
                shortSetup = (close.iloc[i-1] > upper.iloc[i-1] and rsi.iloc[i-1] > short_thr and close.iloc[i] < upper.iloc[i] and rsi.iloc[i] < rsi.iloc[i-1] and close.iloc[i] > sma.iloc[i] and rsi.iloc[i] > 50)
                if shortSetup:
                    entry=float(close.iloc[i])
                    atr5=float((high.rolling(14).max()-low.rolling(14).min()).iloc[i]/14) if len(bars5)>20 else atr/6
                    if np.isnan(atr5) or atr5<=0: atr5=atr/6
                    sl=float(max(upper.iloc[i], close.iloc[i]) + _atr_mult*atr5)
                    sl=max(sl, entry + 1.0*atr5)
                    risk=sl - entry
                    if risk<=0 or risk>(0.70*atr): continue
                    tp1=float(sma.iloc[i]); tp2=float(lower.iloc[i])
                    if tp1 >= entry: continue
                    from scripts.analysis.range_strategy_comparison import TradeSignal
                    return TradeSignal("SHORT", entry, sl, tp1, tp2, risk, ct, sess, metadata={"rsi":float(rsi.iloc[i])})
            return None
        strat.detect_signal = patched_detect
        engine=BacktestEngine(sym, tick_size=0.25, entry_mode="limit")
        for t_date in unique_dates:
            ts=pd.Timestamp(t_date)
            if ts.weekday()>=5 or ts.year<2025: continue
            ctx=build_day_context(ts, DF1c, DF5, daily_atr2, ib_minutes=30)
            if ctx is None: continue
            for sess in strat.get_active_sessions():
                sig=strat.detect_signal(ctx, sess)
                if sig is None: continue
                sig.metadata["strategy_name"]=strat.name
                tr=engine.simulate_trade(sig, ctx)
                if tr is not None:
                    total_trades.append(tr.__dict__)
                    break
        # end sym loop
    df=pd.DataFrame(total_trades)
    if df.empty:
        return dict(bb=bb, sd=sd, adx=adx_thr, rsi_long=rsi_long, atr_mult=atr_mult, squeeze_pct=str(squeeze_pct), trades=0, wr=0, pf=0, net=0, dd=0, prop=0)
    pnl=df["total_pnl_dollars"]; cum=pnl.cumsum(); dd=(cum-cum.cummax()).min()
    wr=(pnl>1).mean()*100; gp=pnl[pnl>0].sum(); gl=abs(pnl[pnl<0].sum()); pf=gp/gl if gl>0 else 999; net=cum.iloc[-1]
    target=3000; mdd=2000; cur=0; peak=0; passes=fails=0
    for v in pnl:
        cur+=v
        if cur>peak: peak=cur
        if abs(cur-peak)>=mdd: fails+=1; cur=0; peak=0
        elif cur>=target: passes+=1; cur=0; peak=0
    prop=passes/(passes+fails)*100 if passes+fails>0 else 0
    return dict(bb=bb, sd=sd, adx=adx_thr, rsi_long=rsi_long, atr_mult=atr_mult, squeeze_pct=str(squeeze_pct), trades=len(df), wr=round(wr,1), pf=round(pf,2), net=round(net), dd=round(abs(dd)), prop=round(prop,1), passes=passes, fails=fails)

if __name__=="__main__":
    grid=list(itertools.product([14,20],[1.8,2.0,2.2],[25,28],[30,33],[1.2,1.5],[None,30]))
    print(f"Grid {len(grid)} combos (2*3*2*2*2*2=96) — 8 cores")
    results=Parallel(n_jobs=8, backend="loky", verbose=5)(delayed(run_one)(args) for args in grid)
    df=pd.DataFrame(results).sort_values(["pf","net"], ascending=False)
    print(df.to_string(index=False))
    df.to_csv("data/derived/bb_grid_48arm_ESNQ_NTshared_2025_2026.csv", index=False)
    print("Saved to data/derived/bb_grid_48arm_ESNQ_NTshared_2025_2026.csv")
