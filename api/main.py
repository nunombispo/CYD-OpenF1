"""OpenF1 wrapper API: aggregated race status endpoint."""
import time

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from race_status import get_race_status

app = FastAPI(
    title="OpenF1 Wrapper API",
    description="Aggregates OpenF1 data for latest session, lap info, standings, and fastest lap.",
    version="0.1.0",
)

CACHE_TTL_SECONDS = 60
_race_status_cache: tuple[dict | None, float] = (None, 0.0)


@app.get("/api/race-status")
async def race_status():
    """
    Returns aggregated race status from the latest OpenF1 session (cached 1 minute):

    - **session**: circuit name and country ISO3
    - **latest_lap_number** / **total_laps**: current lap and total (total_laps may be null; OpenF1 does not expose scheduled distance)
    - **current_standings**: for each driver — position, driver number, name, tyre compound, stint duration (laps), and lap time (leader) or gap to leader (others)
    - **fastest_lap**: driver, lap number, and duration (so far in the session)
    """
    global _race_status_cache
    now = time.monotonic()
    cached, expiry = _race_status_cache
    if cached is not None and now < expiry:
        return cached
    try:
        data = await get_race_status()
        _race_status_cache = (data, now + CACHE_TTL_SECONDS)
        return data
    except Exception as e:
        return JSONResponse(
            status_code=502,
            content={"error": "OpenF1 aggregation failed", "detail": str(e)},
        )


@app.get("/")
async def root():
    return {"message": "OpenF1 Wrapper", "docs": "/docs", "race_status": "/api/race-status"}

    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)