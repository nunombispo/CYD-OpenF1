# OpenF1 Wrapper API

Aggregates [OpenF1](https://openf1.org/docs/) data into a single **race status** endpoint.

## Endpoint: `GET /api/race-status`

Returns JSON with:

| Field                 | Description                                                                                                                                   |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| **session**           | `circuit_name`, `country_iso3` for the latest session                                                                                         |
| **latest_lap_number** | Last completed lap number                                                                                                                     |
| **total_laps**        | Scheduled total (null; not provided by OpenF1)                                                                                                |
| **current_standings** | Per driver: `position`, `driver_number`, `name`, `tyre`, `stint_duration_laps`, `lap_time_or_gap` (leader = lap time, others = gap to leader) |
| **fastest_lap**       | So far: `driver_number`, `driver_name`, `lap_number`, `duration_seconds`, `duration_formatted`                                                |

Data is built from OpenF1’s **sessions**, **drivers**, **laps**, **position**, **stints**, and **intervals** endpoints using `session_key=latest`.

## Run locally

```bash
cd api
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0
```

- API: http://127.0.0.1:8000
- Docs: http://127.0.0.1:8000/docs
- Race status: http://127.0.0.1:8000/api/race-status

Use `--host 0.0.0.0` so the CYD (or other devices on your LAN) can reach the API. Set `PITWALL_URL` on the CYD to `http://<this machine's LAN IP>:8000/api/race-status`.

## Requirements

- Python 3.10+
- No API key for historical OpenF1 data; real-time may require a [paid subscription](https://openf1.org/auth.html).
