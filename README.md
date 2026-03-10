# CYD F1 Pit Wall Display

MicroPython client for the **ESP32-2432S028 (CYD)** — 320×240 ILI9341 touchscreen, WiFi — that shows live F1 standings by polling a single race-status API. No OpenF1 calls from the device; one HTTP request, parse, render.

## Hardware

| Component | Details |
| --------- | ------- |
| **Board** | ESP32-2432S028 (CYD) |
| **Display** | ILI9341 320×240, RGB565 |
| **Touch** | XPT2046 (handled by `cyd` helper) |
| **Connectivity** | WiFi (built-in) |

## Dependencies

- **MicroPython** (ESP32 build with WiFi)
- **`cyd`** — display and touch helper for this board (ILI9341 + XPT2046)
- **urequests**, **ujson** — typically included in MicroPython

## Configuration

Edit the top of `main.py`:

| Variable | Description |
| -------- | ----------- |
| `WIFI_SSID` | Your WiFi network name |
| `WIFI_PASSWORD` | WiFi password |
| `PITWALL_URL` | Full URL of the race-status API, e.g. `http://192.168.1.100:8000/api/race-status` |
| `MY_DRIVER` | 3-letter driver code to highlight (e.g. `"NOR"`, `"VER"`) |
| `POLL_INTERVAL` | Seconds between API polls (default `30`) |

The CYD must be on the same network as the machine running the [API](api/README.md). Use the host’s LAN IP (not `127.0.0.1`) in `PITWALL_URL`.

## Run

1. Flash MicroPython to the ESP32 (CYD-compatible build).
2. Copy `main.py` (and any other project files) onto the device, e.g. with `mpremote` or Thonny.
3. Ensure the [aggregator API](api/README.md) is running and reachable at `PITWALL_URL`.
4. Reset or power the CYD — it connects to WiFi, then polls the API and redraws on lap change or touch.

Touch the screen to force an immediate refresh.

## Project layout

- **`main.py`** — WiFi, API client (`get_pitwall`), `parse_pitwall`, display layout constants, `render_*` functions, main loop.
- **`api/`** — [OpenF1 wrapper API](api/README.md) (aggregator). Run this on a Raspberry Pi, PC, or server; the CYD consumes its `/api/race-status` endpoint.

## Porting

The renderer uses `fill_rectangle`, `fill_circle`, and `draw_text8x8` (8×8 font). If you have another ILI9341 setup, replace the `cyd` display/touch setup with your driver and adjust pin definitions; the layout constants and render logic in `main.py` are independent of the board.
