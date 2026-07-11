
from fastapi import APIRouter, HTTPException, Query, Body
from .service import ProfilerService
from scripts.libs_py.nqstats.engine import NQStatsEngine
from api.features.shared.data_loader import load_parquet
import pandas as pd
import json

router = APIRouter()


def _load_engine_df(ticker: str) -> pd.DataFrame:
    """
    Load 1m parquet data (with live fusion) and convert to DatetimeIndex
    as required by NQStatsEngine.
    """
    df = load_parquet(ticker, "1m")
    if df is None or df.empty:
        return None
    # load_parquet returns 'time' as Unix seconds (int)
    df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df = df.set_index('datetime')
    df.index.name = 'datetime'
    return df


@router.get("/{ticker}/status", tags=["Stats"])
def get_profiler_live_status(ticker: str):
    """
    Get current NQStats live status summarizing all sessions in the current trading day.
    Returns session statuses (asiabox_status, london_status, etc.) for use as filter context.
    """
    ticker = ticker.upper()
    df = _load_engine_df(ticker)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {ticker}")
    
    engine = NQStatsEngine(df, ticker=ticker)
    engine.process()
    latest = engine.get_latest_status()
    # Convert numpy types to native Python for JSON serialization
    return ({k: (v.item() if hasattr(v, 'item') else v) for k, v in latest.items()})


@router.get("/stats/profiler/{ticker}", tags=["Stats"])
def get_profiler_stats(ticker: str, days: int = Query(50)):
    """
    Get pre-computed profiler sessions.
    PRIORITY 1: Pre-computed JSON
    PRIORITY 2: Calculate from Parquet (Cached)
    """
    result = ProfilerService.analyze_profiler_stats(ticker, days=days)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result




@router.post("/{ticker}/filtered", tags=["Stats"])
def get_profiler_filtered_stats(
    ticker: str,
    payload: dict = Body(...)
):
    """
    Get pre-aggregated profiler stats using filter criteria.
    Payload: {
        "target_session": str,
        "filters": { "Asia": "Short True", ... },
        "broken_filters": { "Asia": "Broken", ... },
        "intra_state": "Any"
    }
    Returns: matched_dates, count, distribution, range_stats
    """
    target_session = payload.get("target_session", "NY1")
    filters = payload.get("filters", {})
    broken_filters = payload.get("broken_filters", {})
    intra_state = payload.get("intra_state", "Any")
    
    result = ProfilerService.get_filtered_stats(
        ticker, target_session, filters, broken_filters, intra_state
    )
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/{ticker}/price-model", tags=["Stats"])
def get_profiler_filtered_price_model(
    ticker: str,
    payload: dict = Body(...)
):
    """
    Get Price Model using filter criteria instead of explicit date list.
    Payload: {
        "target_session": str (e.g. "Daily", "NY1"),
        "filters": { "Asia": "Short True", ... },
        "broken_filters": { "Asia": "Broken", ... },
        "intra_state": "Any"
    }
    Returns: median path, extreme path, count
    """
    target_session = payload.get("target_session", "Daily")
    filters = payload.get("filters", {})
    broken_filters = payload.get("broken_filters", {})
    intra_state = payload.get("intra_state", "Any")
    
    result = ProfilerService.get_filtered_price_model(
        ticker, target_session, filters, broken_filters, intra_state
    )
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@router.get("/stats/hod-lod/{ticker}", tags=["Stats"])
def get_hod_lod_stats(ticker: str):
    """
    Get pre-computed HOD/LOD time statistics.
    """
    ticker = ProfilerService._normalize_ticker(ticker)
    json_path = DATA_DIR / f"{ticker}_hod_lod.json"
    
    if not json_path.exists():
        raise HTTPException(status_code=404, detail=f"HOD/LOD data for {ticker} not found. Run precompute script.")
    
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    return data

@router.get("/stats/profiler/{ticker}/levels", tags=["Stats"])
def get_profiler_level_stats(ticker: str):
    """
    Get pre-computed daily level hit probability stats (Hit Rate, Median Time, Mode).
    Returns nested dict by Context (All, Green, Red).
    """
    result = ProfilerService.get_level_stats(ticker)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
        
    return result

@router.get("/stats/range-dist/{ticker}", tags=["Stats"])
def get_range_distribution(ticker: str):
    """
    Get pre-computed price range distribution (high/low relative to open).
    """
    ticker = ProfilerService._normalize_ticker(ticker)
    json_path = DATA_DIR / f"{ticker}_range_dist.json"
    
    if not json_path.exists():
        raise HTTPException(status_code=404, detail=f"Range distribution for {ticker} not found. Run precompute script.")
    
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    return data

@router.post("/stats/clear-cache/{ticker}", tags=["Stats"])
def clear_profiler_cache(ticker: str = "NQ1"):
    """
    Clear the in-memory cache for profiler data.
    This forces the server to reload from the JSON file on next request.
    """
    from api.features.profiler.service import ProfilerService
    return ProfilerService.clear_cache(ticker)

@router.post("/stats/clear-cache", tags=["Stats"])
def get_all_profiler_cache():
    """Clear all in-memory cache."""
    from api.features.profiler.service import ProfilerService
    return ProfilerService.clear_cache()

@router.get("/stats/daily-hod-lod/{ticker}", tags=["Stats"])
def get_daily_hod_lod(
    ticker: str, 
    unadjusted: bool = Query(False),
    start_date: str = Query(None),
    end_date: str = Query(None)
):
    """
    Get pre-computed true daily HOD/LOD times (from 1-minute data) in columnar format.
    """
    data = ProfilerService.get_daily_hod_lod(ticker, unadjusted=unadjusted, start_date=start_date, end_date=end_date)
    
    if "error" in data:
        raise HTTPException(status_code=404, detail=data["error"])
        
    return data

@router.get("/stats/level-touches/{ticker}", tags=["Stats"])
def get_level_touches(
    ticker: str,
    start_date: str = Query(None),
    end_date: str = Query(None)
):
    """
    Get pre-computed reference level touch data (PDH/PDL/PDM, P12 H/L/M) in columnar format.
    """
    data = ProfilerService.get_level_touches(ticker, start_date=start_date, end_date=end_date)
    
    if "error" in data:
        raise HTTPException(status_code=404, detail=data["error"])
        
    return data

@router.get("/stats/reference", tags=["Stats"])
def get_reference_stats():
    """
    Get Reference Data (aggregated stats and medians) from docs folder.
    """
    docs_dir = DATA_DIR.parent / "docs" / "reference_data"
    ref_all_path = docs_dir / "ReferenceAll.json"
    ref_med_path = docs_dir / "ReferenceMedian.json"
    
    if not ref_all_path.exists() or not ref_med_path.exists():
        raise HTTPException(status_code=404, detail="Reference data not found in docs/ directory.")
        
    with open(ref_all_path, 'r') as f:
        ref_all = json.load(f)
        
    with open(ref_med_path, 'r') as f:
        ref_med = json.load(f)
        
    return {
        "stats": ref_all,
        "median": ref_med
    }

@router.get("/{ticker}/price-model", tags=["Stats"])
def get_price_model(
    ticker: str,
    session: str,
    outcome: str,
    days: int = Query(50)
):
    """
    Get Price Model (Composite High/Low) for a specific outcome.
    Returns Average and Extreme models.
    """
    result = ProfilerService.get_price_model_data(ticker, session, outcome, days)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result



# ============================================================================
# NEW: Filter-Based Endpoints (Architecture Refactor)
# ============================================================================

@router.post("/stats/filtered-stats", tags=["Stats"])
def get_filtered_profiler_stats(
    payload: dict = Body(...)
):
    """
    Get pre-aggregated profiler stats using filter criteria.
    Payload: {
        "ticker": str,
        "target_session": str,
        "filters": { "Asia": "Short True", ... },
        "broken_filters": { "Asia": "Broken", ... },
        "intra_state": "Any",
        "start_date": "2026-01-01",
        "end_date": "2026-06-24"
    }
    Returns: matched_dates, count, distribution, range_stats
    """
    ticker = payload.get("ticker", "NQ1")
    target_session = payload.get("target_session", "NY1")
    filters = payload.get("filters", {})
    broken_filters = payload.get("broken_filters", {})
    intra_state = payload.get("intra_state", "Any")
    start_date = payload.get("start_date")
    end_date = payload.get("end_date")
    
    result = ProfilerService.get_filtered_stats(
        ticker, target_session, filters, broken_filters, intra_state, start_date, end_date
    )
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/stats/filtered-price-model", tags=["Stats"])
def get_filtered_price_model(
    payload: dict = Body(...)
):
    """
    Get Price Model using filter criteria instead of explicit date list.
    Payload: {
        "ticker": str,
        "target_session": str (price model session, e.g. "Daily", "NY1"),
        "filters": { "Asia": "Short True", ... },
        "broken_filters": { "Asia": "Broken", ... },
        "intra_state": "Any",
        "start_date": "2026-01-01",
        "end_date": "2026-06-24"
    }
    Returns: average path, extreme path, count
    """
    ticker = payload.get("ticker", "NQ1")
    target_session = payload.get("target_session", "Daily")
    filters = payload.get("filters", {})
    broken_filters = payload.get("broken_filters", {})
    intra_state = payload.get("intra_state", "Any")
    bucket_minutes = payload.get("bucket_minutes", 1)
    start_date = payload.get("start_date")
    end_date = payload.get("end_date")
    
    result = ProfilerService.get_filtered_price_model(
        ticker, target_session, filters, broken_filters, intra_state, bucket_minutes, start_date, end_date
    )
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/stats/custom-price-model", tags=["Stats"])
def get_custom_price_model(
    payload: dict = Body(...)
):
    """
    Get Price Model for an explicit list of dates.
    Used by the Pine Script generator for cross-day filtered models.
    Payload: {
        "ticker": str,
        "target_session": str,
        "dates": [str],
        "bucket_minutes": int
    }
    """
    ticker = payload.get("ticker", "NQ1")
    target_session = payload.get("target_session", "Daily")
    dates = payload.get("dates", [])
    bucket_minutes = payload.get("bucket_minutes", 5)
    
    if not dates:
        raise HTTPException(status_code=400, detail="No dates provided")
    
    result = ProfilerService.get_custom_price_model(
        ticker, target_session, dates, bucket_minutes
    )
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ============================================================================
# NEW: Prediction Endpoints (Profiler Expansion)
# ============================================================================

@router.get("/stats/prediction/asia", tags=["Stats"])
def get_asia_prediction(
    prev_ny1: str = Query(..., description="Status of previous day's NY1 session (e.g. 'Long True')"),
    prev_ny2: str = Query(..., description="Status of previous day's NY2 session")
):
    """
    Get probability distribution for the upcoming Asia session.
    """
    result = ProfilerService.get_asia_prediction(prev_ny1, prev_ny2)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@router.get("/stats/prediction/london", tags=["Stats"])
def get_london_prediction(
    prev_ny2: str = Query(..., description="Status of previous day's NY2 session"),
    asia_status: str = Query(..., description="Status of current day's Asia session")
):
    """
    Get probability distribution for the upcoming London session.
    """
    result = ProfilerService.get_london_prediction(prev_ny2, asia_status)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
