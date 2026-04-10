"""
FastAPI Indicator Service
Provides technical indicator calculations using pandas-ta
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import ORJSONResponse
from api.features.indicators import router as indicators
from api.features.sessions import router as sessions
from api.features.profiler import router as profiler

app = FastAPI(
    title="Trading Indicators API",
    description="Technical indicator calculations for chart display and backtesting",
    version="1.0.0",
    default_response_class=ORJSONResponse
)

# Enable GZip Compression for payloads > 1KB
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Allow Next.js frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# app.include_router(indicators.router, prefix="/api/indicators", tags=["indicators"])
# app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
# app.include_router(profiler.router)

@app.get("/")
async def root():
    return {"message": "Trading Indicators API", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


# Import routers from features
from api.features.indicators.router import router as indicators_router
from api.features.sessions.router import router as sessions_router
from api.features.profiler.router import router as profiler_router
from api.features.candle_science.router import router as candle_science_router

# Include specific routers first, greedy ones last
app.include_router(indicators_router, prefix="/api/indicators", tags=["indicators"])
app.include_router(profiler_router, tags=["profiler"])
app.include_router(candle_science_router, prefix="/api/candle-science", tags=["candle-science"])
app.include_router(sessions_router, prefix="/api/sessions", tags=["sessions"]) # Greedy /{ticker} last


@app.on_event("startup")
async def startup_event():
    """Run pre-warming logic on startup."""
    prewarm_enabled = os.getenv("PROFILER_PREWARM_ENABLED", "1") == "1"
    if not prewarm_enabled:
        print("Profiler pre-warm disabled (PROFILER_PREWARM_ENABLED=0)")
        return

    print("Pre-warming cache...")
    from api.features.profiler.service import ProfilerService

    # Warm up for default ticker NQ1. Session scope is controlled by
    # PROFILER_PREWARM_SESSIONS (default in service is NY1 only).
    ProfilerService.prewarm_cache("NQ1")


# Force Reload Touch

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)
