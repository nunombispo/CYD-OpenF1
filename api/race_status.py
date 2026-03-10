"""Aggregate OpenF1 data into race status: session, lap info, standings, fastest lap."""
from openf1_client import (
    get_drivers,
    get_intervals,
    get_laps,
    get_latest_session,
    get_position,
    get_stints,
)


def _latest_position_per_driver(positions: list[dict]) -> dict[int, int]:
    """Map driver_number -> position using the most recent update per driver."""
    by_driver: dict[int, list[dict]] = {}
    for p in positions:
        if p.get("date") is None:
            continue
        dn = p["driver_number"]
        if dn not in by_driver:
            by_driver[dn] = []
        by_driver[dn].append(p)
    out = {}
    for dn, updates in by_driver.items():
        if not updates:
            continue
        latest = max(updates, key=lambda x: x["date"])
        out[dn] = latest["position"]
    return out


def _driver_order(positions: list[dict]) -> list[int]:
    """List of driver_numbers in current position order (1st, 2nd, ...)."""
    pos_to_driver: dict[int, int] = {}
    for dn, pos in _latest_position_per_driver(positions).items():
        pos_to_driver[pos] = dn
    return [pos_to_driver[p] for p in sorted(pos_to_driver)]


def _tyre_and_stint_duration(stints: list[dict], driver_number: int, current_lap: int) -> tuple[str | None, int | None]:
    """Current compound and laps in current stint for driver at current_lap."""
    if current_lap < 1:
        return (None, None)
    driver_stints = [
        s for s in stints
        if s["driver_number"] == driver_number and s.get("lap_start") is not None
    ]
    # Sort by lap_start descending: prefer the most recent stint that covers current_lap
    for s in sorted(driver_stints, key=lambda x: x["lap_start"], reverse=True):
        start = s["lap_start"]
        end = s.get("lap_end")
        # Stint covers current_lap if: started on or before this lap and (no end yet, or end >= current_lap)
        if start <= current_lap and (end is None or end >= current_lap):
            laps_in_stint = current_lap - start + 1
            return (s.get("compound"), laps_in_stint)
    return (None, None)


def _format_duration(seconds: float | None) -> str | None:
    """Format seconds as M:SS.mmm or +N.NNs for gap. None stays None."""
    if seconds is None:
        return None
    if seconds < 0:
        return f"+{-seconds:.3f}s"
    if seconds >= 60:
        m = int(seconds // 60)
        s = seconds % 60
        return f"{m}:{s:06.3f}"
    return f"{seconds:.3f}s"


async def get_race_status():
    """
    Returns:
    - session: { circuit_name, country_iso3 }
    - latest_lap_number, total_laps (total_laps from API if available, else None)
    - current_standings: list of { position, driver_number, name, tyre, stint_duration_laps, lap_time_or_gap }
    - fastest_lap: { driver_number, driver_name, lap_number, duration_seconds, duration_formatted }
    """
    sessions_raw = await get_latest_session()
    if not sessions_raw:
        return {
            "session": None,
            "latest_lap_number": None,
            "total_laps": None,
            "current_standings": [],
            "fastest_lap": None,
            "error": "No latest session found",
        }

    session_row = sessions_raw[0]
    session_key = session_row["session_key"]
    circuit_name = session_row.get("circuit_short_name") or session_row.get("location") or "Unknown"
    country_iso3 = session_row.get("country_code") or None

    session = {"circuit_name": circuit_name, "country_iso3": country_iso3}

    # Laps: last completed lap and fastest lap
    all_laps = await get_laps(session_key)
    all_laps = [l for l in all_laps if l.get("lap_number") is not None]
    racing_laps = [l for l in all_laps if not l.get("is_pit_out_lap", False) and l.get("lap_duration") is not None]
    latest_lap_number = max((l["lap_number"] for l in all_laps), default=None) if all_laps else None
    total_laps = None  # OpenF1 doesn't expose scheduled race distance

    fastest_lap_data = None
    if racing_laps:
        best = min(racing_laps, key=lambda x: x["lap_duration"])
        fastest_lap_data = {
            "driver_number": best["driver_number"],
            "lap_number": best["lap_number"],
            "duration_seconds": best["lap_duration"],
            "duration_formatted": _format_duration(best["lap_duration"]),
        }

    # Drivers for names (and fastest lap name)
    drivers_list = await get_drivers(session_key)
    drivers_by_num = {d["driver_number"]: d for d in drivers_list}
    if fastest_lap_data and fastest_lap_data["driver_number"] in drivers_by_num:
        d = drivers_by_num[fastest_lap_data["driver_number"]]
        fastest_lap_data["driver_name"] = d.get("full_name")
        fastest_lap_data["driver_name_acronym"] = d.get("name_acronym")
        fastest_lap_data["team_colour"] = d.get("team_colour")

    # Current standings: position, driver, tyre, stint duration, lap time (leader) or gap (others)
    positions = await get_position(session_key)
    stints = await get_stints(session_key)

    if not positions:
        return {
            "session": session,
            "latest_lap_number": latest_lap_number,
            "total_laps": total_laps,
            "current_standings": [],
            "fastest_lap": fastest_lap_data,
        }

    order = _driver_order(positions)
    # Each driver's last completed lap time (from all_laps), so lapped drivers get their actual last lap
    last_lap_times: dict[int, float] = {}
    laps_with_duration = [l for l in all_laps if l.get("lap_duration") is not None]
    by_driver_lap: dict[int, list[dict]] = {}
    for l in laps_with_duration:
        dn = l["driver_number"]
        if dn not in by_driver_lap:
            by_driver_lap[dn] = []
        by_driver_lap[dn].append(l)
    for dn, driver_laps in by_driver_lap.items():
        last = max(driver_laps, key=lambda x: x["lap_number"])
        last_lap_times[dn] = last["lap_duration"]
    leader_duration = last_lap_times.get(order[0]) if order else None

    # Optional: use intervals for gap_to_leader (more real-time during race)
    intervals_list = await get_intervals(session_key)
    gap_to_leader: dict[int, float | str | None] = {}
    if intervals_list:
        # Latest interval per driver (skip entries with no date)
        by_driver: dict[int, list] = {}
        for i in intervals_list:
            if i.get("date") is None:
                continue
            dn = i["driver_number"]
            if dn not in by_driver:
                by_driver[dn] = []
            by_driver[dn].append(i)
        for dn, updates in by_driver.items():
            if not updates:
                continue
            latest = max(updates, key=lambda x: x["date"])
            gap_to_leader[dn] = latest.get("gap_to_leader")  # can be "+1 LAP" string

    standings = []
    lap_for_stint = latest_lap_number or 0
    for idx, driver_number in enumerate(order):
        position = idx + 1
        driver_info = drivers_by_num.get(driver_number, {})
        name = driver_info.get("full_name") or f"Driver {driver_number}"
        name_acronym = driver_info.get("name_acronym")  # 3-letter e.g. VER, HAM
        team_colour = driver_info.get("team_colour")  # hex RRGGBB e.g. 3671C6
        tyre, stint_laps = None, None
        # Try current lap first, then earlier laps so lapped drivers (+1 LAP, +2 LAPS, etc.) get a stint
        for lap in range(lap_for_stint, 0, -1):
            tyre, stint_laps = _tyre_and_stint_duration(stints, driver_number, lap)
            if tyre is not None or stint_laps is not None:
                break
        lap_time_seconds = last_lap_times.get(driver_number) if latest_lap_number is not None else None
        lap_time = _format_duration(lap_time_seconds) if lap_time_seconds is not None else None
        lap_time_or_gap = None
        if latest_lap_number is not None:
            dur = last_lap_times.get(driver_number)
            if position == 1 and dur is not None:
                lap_time_or_gap = _format_duration(dur)
            else:
                gap = gap_to_leader.get(driver_number)
                if gap is not None:
                    if isinstance(gap, str):
                        lap_time_or_gap = gap  # e.g. "+1 LAP"
                    else:
                        lap_time_or_gap = f"+{gap:.3f}s"  # gap to leader in seconds
                elif dur is not None and leader_duration is not None:
                    lap_time_or_gap = f"+{(dur - leader_duration):.3f}s"
        standings.append({
            "position": position,
            "driver_number": driver_number,
            "name": name,
            "name_acronym": name_acronym,
            "team_colour": team_colour,
            "tyre": tyre,
            "stint_duration_laps": stint_laps,
            "lap_time_seconds": lap_time_seconds,
            "lap_time": lap_time,
            "lap_time_or_gap": lap_time_or_gap,
        })

    return {
        "session": session,
        "latest_lap_number": latest_lap_number,
        "total_laps": total_laps,
        "current_standings": standings,
        "fastest_lap": fastest_lap_data,
    }
