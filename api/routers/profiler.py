
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
