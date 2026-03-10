"""
F1 Pit Wall Display — ESP32 CYD + OpenF1 API
MicroPython basis

Hardware: ESP32-2432S028 (CYD)
Display:  ILI9341 320x240 via cyd.display_setup
Touch:    XPT2046 via cyd (display_setup returns touch)
Libs:     urequests, ujson (built into MicroPython), cyd
"""

import gc
import urequests
import ujson
import time
import cyd

# ── CONFIG ────────────────────────────────────────────────
WIFI_SSID     = "XXXXXXXXXXXX"
WIFI_PASSWORD = "XXXXXXXXXXXX"
MY_DRIVER     = "NOR"          # 3-letter code to highlight
POLL_INTERVAL = 30             # seconds between OpenF1 polls

# Single pitwall API (returns session, standings, fastest lap in one response)
PITWALL_URL = "http://192.168.2.31:5000/api/race-status"
# 192.168.2.70
# PITWALL_URL = "http://192.168.2.70:8000/api/race-status"



# ── DISPLAY SETUP (ILI9341 on CYD) ───────────────────────
# Colours — RGB565
BLACK   = 0x0000
WHITE   = 0xFFFF
RED     = 0xE800  # F1 red  #e10600
YELLOW  = 0xFFE0
PURPLE  = 0xB817  # fastest lap
GREEN   = 0x07E0
GREY    = 0x8410
DGREY   = 0x2104
ORANGE  = 0xFC00

# Tyre colours (RGB565)
TYRE_SOFT   = RED
TYRE_MEDIUM = YELLOW
TYRE_HARD   = WHITE
TYRE_INTER  = GREEN

TYRE_COLORS = {
    "SOFT":   TYRE_SOFT,
    "MEDIUM": TYRE_MEDIUM,
    "HARD":   TYRE_HARD,
    "INTERMEDIATE": TYRE_INTER,
    "WET":    0x001F,  # blue
}

# Touch: set by cyd touch_handler to force immediate refresh
touch_refresh = False


def _on_touch(x, y):
    """Touch handler: request a display refresh on next loop."""
    global touch_refresh
    touch_refresh = True


# ── PITWALL API (single endpoint) ───────────────────────
# Response: session, latest_lap_number, total_laps, current_standings[], fastest_lap{}

def get_pitwall():
    """GET pitwall endpoint, return parsed JSON or None."""
    print("Pitwall URL:", PITWALL_URL)
    try:
        gc.collect()
        r = urequests.request("GET", PITWALL_URL, timeout=10)
        data = ujson.loads(r.content)
        r.close()
        del r
        gc.collect()
        return data
    except OSError as e:
        print("Pitwall OSError:", e, type(e).__name__)
        return None
    except Exception as e:
        print("Pitwall error:", e, type(e).__name__)
        return None


def parse_pitwall(data):
    """Map pitwall JSON to (session, positions, drivers, laps, stints, fastest_driver, fastest_time, current_lap, total_laps, updated).
    positions/drivers/laps/stints are dicts keyed by driver_number (str); order preserved via positions insertion order."""
    if not data or "current_standings" not in data:
        return None
    sess = data.get("session") or {}
    session = {
        "circuit_short_name": sess.get("circuit_name", "???"),
        "country_name": sess.get("country_iso3", "???"),
        "total_laps": data.get("total_laps"),
    }
    current_lap = data.get("latest_lap_number") or 0
    total_laps = data.get("total_laps")
    standings = data.get("current_standings") or []
    positions = {}
    drivers = {}
    laps = {}
    stints = {}
    for row in standings:
        drv = str(row.get("driver_number", ""))
        if not drv:
            continue
        positions[drv] = {
            "position": row.get("position", 99),
            "lap_time_or_gap": row.get("lap_time_or_gap"),
        }
        drivers[drv] = {
            "name_acronym": row.get("name_acronym") or "???",
            "team_name": "",
            "team_colour": row.get("team_colour"),
        }
        laps[drv] = {"lap_duration": row.get("lap_time_seconds")}  # seconds for format_laptime
        tyre = row.get("tyre")
        stints[drv] = {
            "compound": tyre if tyre else "",
            "stint_duration_laps": row.get("stint_duration_laps"),
        }
    fl = data.get("fastest_lap") or {}
    fastest_driver = fl.get("driver_name_acronym") or ""
    fastest_time = fl.get("duration_seconds")
    fastest_lap_number = fl.get("lap_number")
    updated = ""
    return (session, positions, drivers, laps, stints, fastest_driver, fastest_time, fastest_lap_number, current_lap, total_laps, updated)


def format_laptime(ms):
    """Convert milliseconds to M:SS.mmm string."""
    if ms is None:
        return "  --:--.---"
    ms = int(ms * 1000) if ms < 1000 else int(ms)
    minutes = ms // 60000
    seconds = (ms % 60000) // 1000
    millis  = ms % 1000
    return f"{minutes}:{seconds:02d}.{millis:03d}"


def format_gap(gap_seconds):
    """Format gap for display. OpenF1 uses seconds for gap_to_leader."""
    if gap_seconds is None or gap_seconds == 0:
        return "LEADER"
    return f"+{gap_seconds:.3f}"


def hex_to_rgb565(hex_str):
    """Convert hex "00D7B6" or "#00D7B6" to RGB565 for display."""
    if not hex_str or not isinstance(hex_str, str):
        return None
    s = hex_str.lstrip("#")
    if len(s) != 6:
        return None
    try:
        r = int(s[0:2], 16)
        g = int(s[2:4], 16)
        b = int(s[4:6], 16)
        return (r & 0xF8) << 8 | (g & 0xFC) << 3 | b >> 3
    except ValueError:
        return None


# ── DISPLAY RENDERING ─────────────────────────────────────
# Uses ili9341: fill_rectangle, fill_circle, draw_text8x8 (8x8 built-in font)

ROW_H    = 19
TOP_BAR  = 22
BOT_BAR  = 20
MAX_ROWS = 10  # (240 - 22 - 20) / 19 = 10 rows, order by position

# Column x positions (more spacing between position, driver #, strip, name, tyre, stint, lap time, gap)
COL_POS = 5
COL_DRIVER_NUM = 30
COL_STRIP = 50
COL_CODE = 60
COL_TYRE = 105
COL_STINT = 125
COL_LAP_TIME = 160
COL_GAP = 250
TOP_BAR_LAP_X = 265


def render_top_bar(display, session, lap_number, total_laps, sc_active):
    """Red top bar: race name + SC badge + lap counter."""
    display.fill_rectangle(0, 0, 320, TOP_BAR, RED)
    circuit = session.get("circuit_short_name", "???").upper()
    country = session.get("country_name", "")[:3].upper()
    label   = f"{country} {circuit}"
    lap_str = f"LAP {lap_number}"
    display.draw_text8x8(8, 6, label, WHITE, RED)
    if sc_active:
        display.fill_rectangle(200, 4, 28, 14, YELLOW)
        display.draw_text8x8(203, 6, "SC", BLACK, YELLOW)
    display.draw_text8x8(TOP_BAR_LAP_X, 6, lap_str, WHITE, RED)


def render_row(display, y, pos, driver, lap, stint, pos_data, current_lap, is_highlight, driver_number):
    """Render one driver row. driver_number is the F1 car number (e.g. 44), shown in team colour."""
    bg = DGREY if is_highlight else (BLACK if pos % 2 == 0 else 0x0841)
    display.fill_rectangle(0, y, 320, ROW_H, bg)

    if is_highlight:
        display.fill_rectangle(0, y, 2, ROW_H, YELLOW)

    # Position: single colour (white). Driver number and strip: team colour
    team_colour_rgb565 = hex_to_rgb565(driver.get("team_colour")) if driver.get("team_colour") else None
    if team_colour_rgb565 is not None:
        tcolor = team_colour_rgb565
        driver_strip_color = team_colour_rgb565
    else:
        tcolor = GREY
        driver_strip_color = GREY
    display.draw_text8x8(COL_POS, y + 6, f"{pos:02d}", WHITE, bg)
    display.draw_text8x8(COL_DRIVER_NUM, y + 6, str(driver_number), driver_strip_color, bg)
    display.fill_rectangle(COL_STRIP, y + 4, 3, 14, tcolor)

    code = driver.get("name_acronym", "???") or "???"
    display.draw_text8x8(COL_CODE, y + 6, code, WHITE, bg)

    compound = (stint.get("compound") or "?")[0] if stint else "?"
    tyre_key = (stint.get("compound") or "") if stint else ""
    tcolor = TYRE_COLORS.get(tyre_key, GREY)
    tyre_age = None
    if stint and stint.get("stint_duration_laps") is not None:
        tyre_age = stint["stint_duration_laps"]
    else:
        lap_start = stint.get("lap_start", 0) if stint else 0
        tyre_age = max(0, current_lap - lap_start) if current_lap and lap_start else lap_start
    display.fill_circle(COL_TYRE + 6, y + 10, 7, tcolor)
    display.draw_text8x8(COL_TYRE + 3, y + 6, compound, BLACK, tcolor)
    display.draw_text8x8(COL_STINT, y + 6, str(tyre_age), GREY, bg)

    gap_str = None
    if pos_data and pos_data.get("lap_time_or_gap") is not None:
        gap_str = str(pos_data["lap_time_or_gap"])
    if gap_str is None:
        gap = pos_data.get("gap_to_leader") if pos_data else None
        if gap is None and lap:
            gap = lap.get("gap_to_leader")
        gap_str = format_gap(gap)
        if gap_str == "LEADER" and pos_data and pos_data.get("lap_time_or_gap") is None and pos_data.get("position", 1) != 1:
            gap_str = "--"
    lap_gap = (pos_data.get("lap_time_or_gap") or "") if pos_data else ""
    gap_color = RED if (not lap_gap or lap_gap == "+0.000s") else GREY
    lap_sec = lap.get("lap_duration") if lap else None
    lap_str = format_laptime(lap_sec)
    display.draw_text8x8(COL_LAP_TIME, y + 6, lap_str[:9], WHITE, bg)

    # Always show gap (position 1 = leader: "+0.000s" or "LEADER")
    display.draw_text8x8(COL_GAP, y + 6, (gap_str or "--")[:9], gap_color, bg)


def render_bottom_bar(display, fastest_driver, fastest_time, fastest_lap_number=None):
    """Purple fastest lap on left; bottom right = fastest lap number (e.g. LAP 42)."""
    display.fill_rectangle(0, 220, 320, BOT_BAR, DGREY)
    fl_str = f"FL: {fastest_driver} {format_laptime(fastest_time)}"[:24]
    if fl_str:
        display.draw_text8x8(8, 225, fl_str, PURPLE, DGREY)
    lap_num_str = f"LAP {fastest_lap_number}" if fastest_lap_number is not None else ""
    if lap_num_str:
        display.draw_text8x8(265, 225, lap_num_str, GREY, DGREY)


def render_frame(display, session, positions, drivers, laps, stints, rc,
                 current_lap=None, fastest_driver=None, fastest_time=None, fastest_lap_number=None, updated=None):
    """Full screen render. Pass current_lap/fastest_driver/fastest_time/updated when using pitwall API."""
    sc_active = False
    if rc:
        msg = rc.get("message", "").upper()
        sc_active = "SAFETY CAR" in msg or "SC DEPLOYED" in msg

    if current_lap is None:
        current_lap = max((l.get("lap_number", 0) for l in laps.values()), default=0)
    total_laps = session.get("total_laps") if session.get("total_laps") is not None else "??"

    render_top_bar(display, session, current_lap, total_laps, sc_active)

    if fastest_driver is None or fastest_time is None:
        fastest_time = None
        fastest_driver = ""
        for drv_num, lap in laps.items():
            t = lap.get("lap_duration")
            if t and (fastest_time is None or t < fastest_time):
                fastest_time = t
                fastest_driver = drivers.get(drv_num, {}).get("name_acronym", "???")

    shown = 0
    by_position = sorted(positions.items(), key=lambda x: x[1].get("position", 99))
    for drv_num, pos_data in by_position:
        if shown >= MAX_ROWS:
            break
        pos = pos_data.get("position", 99)
        driver = drivers.get(drv_num, {})
        lap = laps.get(drv_num, {})
        stint = stints.get(drv_num, {})
        code = driver.get("name_acronym", "")
        y = TOP_BAR + shown * ROW_H
        render_row(display, y, pos, driver, lap, stint, pos_data, current_lap,
                   is_highlight=(code == MY_DRIVER), driver_number=drv_num)
        shown += 1

    render_bottom_bar(display, fastest_driver or "", fastest_time, fastest_lap_number)


# ── MAIN LOOP ─────────────────────────────────────────────

def main():
    global touch_refresh
    # Display + touch via cyd (touch handler sets touch_refresh for manual refresh)
    display, backlight, touch = cyd.display_setup(320, 240, rotation=90, touch_handler=_on_touch)
    cyd.set_backlight_brightness(backlight, 90)

    cyd.display_loading(display, "Connecting...", RED)
    if not cyd.connect_wifi(WIFI_SSID, WIFI_PASSWORD):
        return

    display.clear(BLACK)
    time.sleep(1)
    gc.collect()

    last_lap = -1
    while True:
        data = get_pitwall()
        parsed = parse_pitwall(data) if data else None
        if parsed:
            (session, positions, drivers, laps, stints,
             fastest_driver, fastest_time, fastest_lap_number, current_lap, total_laps, updated) = parsed
            if session.get("total_laps") is None and total_laps is not None:
                session["total_laps"] = total_laps
            if current_lap != last_lap or touch_refresh:
                render_frame(display, session, positions, drivers, laps, stints, None,
                             current_lap=current_lap, fastest_driver=fastest_driver,
                             fastest_time=fastest_time, fastest_lap_number=fastest_lap_number)
                last_lap = current_lap
                touch_refresh = False
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
