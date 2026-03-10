"""HTTP client for OpenF1 API (https://api.openf1.org/v1)."""
import httpx

BASE_URL = "https://api.openf1.org/v1"


async def get_latest_session():
    """Fetch latest/current session. Returns list (may be one item or empty)."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(f"{BASE_URL}/sessions", params={"session_key": "latest"})
        r.raise_for_status()
        return r.json()


async def get_session_by_key(session_key: int):
    """Fetch a single session by key."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(f"{BASE_URL}/sessions", params={"session_key": session_key})
        r.raise_for_status()
        data = r.json()
        return data[0] if data else None


async def get_drivers(session_key):
    """Drivers in session (driver_number, full_name, etc.)."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(f"{BASE_URL}/drivers", params={"session_key": session_key})
        r.raise_for_status()
        return r.json()


async def get_laps(session_key, lap_number=None):
    """Laps for session. Optionally filter by lap_number."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        params = {"session_key": session_key}
        if lap_number is not None:
            params["lap_number"] = lap_number
        r = await client.get(f"{BASE_URL}/laps", params=params)
        r.raise_for_status()
        return r.json()


async def get_position(session_key):
    """Position updates for session (date, driver_number, position)."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(f"{BASE_URL}/position", params={"session_key": session_key})
        r.raise_for_status()
        return r.json()


async def get_stints(session_key):
    """Stints (compound, driver_number, lap_start, lap_end, etc.)."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(f"{BASE_URL}/stints", params={"session_key": session_key})
        r.raise_for_status()
        return r.json()


async def get_intervals(session_key):
    """Intervals (gap_to_leader, interval, driver_number). Updated ~every 4s during race."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(f"{BASE_URL}/intervals", params={"session_key": session_key})
        r.raise_for_status()
        return r.json()
