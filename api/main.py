"""
FastAPI Indicator Service
Provides technical indicator calculations using pandas-ta
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers import indicators
from api.routers import sessions

app = FastAPI(
    title="Trading Indicators API",
    description="Technical indicator calculations for chart display and backtesting",
    version="1.0.0"
)

# Allow Next.js frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(indicators.router, prefix="/api/indicators", tags=["indicators"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])


@app.get("/")
async def root():
    return {"message": "Trading Indicators API", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
