
from fastapi import APIRouter, HTTPException, Query, Body
from api.services.profiler_service import ProfilerService
from api.services.data_loader import DATA_DIR
import json

router = APIRouter()

@router.get("/stats/profiler/{ticker}", tags=["Stats"])
async def get_profiler_stats(
    ticker: str, 
    days: int = Query(50, description="Number of days to analyze")
):
    """
    Get Profiler Statistics (Status, Broken) for the last N days.
    """
    result = ProfilerService.analyze_profiler_stats(ticker, days)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
        
    return result


@router.post("/stats/profiler/{ticker}/filtered", tags=["Stats"])
async def get_profiler_filtered_stats(
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


@router.post("/stats/profiler/{ticker}/price-model", tags=["Stats"])
async def get_profiler_filtered_price_model(
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
    Returns: average path, extreme path, count
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
async def get_hod_lod_stats(ticker: str):
    """
    Get pre-computed HOD/LOD time statistics.
    """
    json_path = DATA_DIR / f"{ticker}_hod_lod.json"
    
    if not json_path.exists():
        raise HTTPException(status_code=404, detail=f"HOD/LOD data for {ticker} not found. Run precompute script.")
    
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    return data

@router.get("/stats/range-dist/{ticker}", tags=["Stats"])
async def get_range_distribution(ticker: str):
    """
    Get pre-computed price range distribution (high/low relative to open).
    """
    json_path = DATA_DIR / f"{ticker}_range_dist.json"
    
    if not json_path.exists():
        raise HTTPException(status_code=404, detail=f"Range distribution for {ticker} not found. Run precompute script.")
    
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    return data

@router.post("/stats/clear-cache/{ticker}", tags=["Stats"])
async def clear_profiler_cache(ticker: str = "NQ1"):
    """
    Clear the in-memory cache for profiler data.
    This forces the server to reload from the JSON file on next request.
    """
    from api.services.profiler_service import ProfilerService
    return ProfilerService.clear_cache(ticker)

@router.post("/stats/clear-cache", tags=["Stats"])
async def clear_all_profiler_cache():
    """Clear all in-memory cache."""
    from api.services.profiler_service import ProfilerService
    return ProfilerService.clear_cache()

@router.get("/stats/daily-hod-lod/{ticker}", tags=["Stats"])
async def get_daily_hod_lod(ticker: str):
    """
    Get pre-computed true daily HOD/LOD times (from 1-minute data).
    Returns dict mapping date -> {hod_time, lod_time, hod_price, lod_price, ...}
    """
    json_path = DATA_DIR / f"{ticker}_daily_hod_lod.json"
    
    if not json_path.exists():
        raise HTTPException(status_code=404, detail=f"Daily HOD/LOD data for {ticker} not found. Run precompute_daily_hod_lod.py")
    
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    return data

@router.get("/stats/level-touches/{ticker}", tags=["Stats"])
async def get_level_touches(ticker: str):
    """
    Get pre-computed reference level touch data (PDH/PDL/PDM, P12 H/L/M).
    Returns dict mapping date -> {pdh: {level, touched, touch_time}, ...}
    """
    json_path = DATA_DIR / f"{ticker}_level_touches.json"
    
    if not json_path.exists():
        raise HTTPException(status_code=404, detail=f"Level touch data for {ticker} not found. Run precompute_level_touches.py")
    
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    return data

@router.get("/stats/reference", tags=["Stats"])
async def get_reference_stats():
    """
    Get Reference Data (aggregated stats and medians) from docs folder.
    """
    docs_dir = DATA_DIR.parent / "docs"
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

@router.get("/stats/price-model/{ticker}", tags=["Stats"])
async def get_price_model(
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

@router.post("/stats/price-model/custom", tags=["Stats"])
async def get_custom_price_model(
    payload: dict = Body(...)
):
    """
    Get Price Model for a specific list of dates (Global Filter Intersection).
    Payload: { "ticker": str, "target_session": str, "dates": List[str] }
    """
    ticker = payload.get("ticker", "NQ1")
    target = payload.get("target_session")
    dates = payload.get("dates", [])
    bucket_minutes = payload.get("bucket_minutes", 1)
    
    result = ProfilerService.get_custom_price_model(ticker, target, dates, bucket_minutes)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

# ============================================================================
# NEW: Filter-Based Endpoints (Architecture Refactor)
# ============================================================================

@router.post("/stats/filtered-stats", tags=["Stats"])
async def get_filtered_profiler_stats(
    payload: dict = Body(...)
):
    """
    Get pre-aggregated profiler stats using filter criteria.
    Payload: {
        "ticker": str,
        "target_session": str,
        "filters": { "Asia": "Short True", ... },
        "broken_filters": { "Asia": "Broken", ... },
        "intra_state": "Any"
    }
    Returns: matched_dates, count, distribution, range_stats
    """
    ticker = payload.get("ticker", "NQ1")
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


@router.post("/stats/filtered-price-model", tags=["Stats"])
async def get_filtered_price_model(
    payload: dict = Body(...)
):
    """
    Get Price Model using filter criteria instead of explicit date list.
    Payload: {
        "ticker": str,
        "target_session": str (price model session, e.g. "Daily", "NY1"),
        "filters": { "Asia": "Short True", ... },
        "broken_filters": { "Asia": "Broken", ... },
        "intra_state": "Any"
    }
    Returns: average path, extreme path, count
    """
    ticker = payload.get("ticker", "NQ1")
    target_session = payload.get("target_session", "Daily")
    filters = payload.get("filters", {})
    broken_filters = payload.get("broken_filters", {})
    intra_state = payload.get("intra_state", "Any")
    bucket_minutes = payload.get("bucket_minutes", 1)
    
    result = ProfilerService.get_filtered_price_model(
        ticker, target_session, filters, broken_filters, intra_state, bucket_minutes
    )
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

