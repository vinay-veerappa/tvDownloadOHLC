"""
FastAPI Indicator Service
Provides technical indicator calculations using pandas-ta
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import ORJSONResponse
from api.routers import indicators
from api.routers import sessions

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
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(indicators.router, prefix="/api/indicators", tags=["indicators"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
from api.routers import profiler
app.include_router(profiler.router)


@app.get("/")
async def root():
    return {"message": "Trading Indicators API", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
