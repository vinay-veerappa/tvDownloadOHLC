
from fastapi import APIRouter, HTTPException, Query
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

