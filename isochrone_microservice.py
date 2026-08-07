"""
Isochrone Microservice - CS361 Small Pool (Big Pool Microservice 4)
Map Questers: Kevin McDougal, Suvam Patel

Runs as a standalone HTTP service. Consumers call it over REST/HTTP and receive
JSON. Nothing in this file is imported by consumers, and this file imports
nothing from any consumer's main program.

Endpoints:
     GET /isochrone?json={"lat"}

     Example call from Valhalla isochrone API reference:
     https://valhalla.github.io/valhalla/api/isochrone/
     {"locations":[{"lat":40.744014,"lon":-73.990508}],"costing":"pedestrian","contours":[{"time":15.0,"color":"ff0000"}]}&id=Walk_From_Office

Run:
     uvicorn isochrone_microservice:app --reload --port 8003
"""

import os
import time

import httpx
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
import json

# ---------------------------------------------------------------------------
# Configuration - this service calls Valhalla routing engine
# Override with environment variables if your Docker ports differ.
# ---------------------------------------------------------------------------
VALHALLA_URL = os.getenv("VALHALLA_URL", "http://localhost:8002")
ENGINE_TIMEOUT = float(os.getenv("ENGINE_TIMEOUT", "8.0"))

VALID_COSTINGS = {"auto", "bicycle", "pedestrian"}

app = FastAPI(title="Isochrone Microservice", version="1.0.0")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def error(status: int, code: str, message: str) -> JSONResponse:
    """Every failure leaves through here, so consumers can branch on status
    code alone and always find an `error` field in the body."""
    return JSONResponse(status_code=status, content={"error": code, "message": message})


def parse_coordinate(raw: str, name: str) -> tuple[float, float]:
    """Parse a 'lat,lon' string. Raises ValueError with a consumer-facing message."""
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) != 2:
        raise ValueError(f"Parameter '{name}' must be formatted as 'lat,lon'.")
    try:
        lat, lon = float(parts[0]), float(parts[1])
    except ValueError:
        raise ValueError(f"Parameter '{name}' must contain two numbers, e.g. '33.9737,-117.3281'.")
    if not -90.0 <= lat <= 90.0:
        raise ValueError(f"Latitude in '{name}' must be between -90 and 90.")
    if not -180.0 <= lon <= 180.0:
        raise ValueError(f"Longitude in '{name}' must be between -180 and 180.")
    return lat, lon


@app.middleware("http")
async def log_elapsed(request: Request, call_next):
    """Prints elapsed milliseconds per request. Used to demonstrate the
    Responsiveness non-functional requirement (< 3000 ms) on camera."""
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    print(f"[isochrone-ms] {request.method} {request.url.path} -> "
          f"{response.status_code} in {elapsed_ms:.0f} ms")
    response.headers["X-Elapsed-Ms"] = f"{elapsed_ms:.0f}"
    return response


# ---------------------------------------------------------------------------
# GET isochrone
# ---------------------------------------------------------------------------
@app.get("/isochrone")
async def isochrone(
    location: str = Query(default="", description="Start coordinate as 'lat,lon'"),
    costing: str = Query(default="", description="modes as auto, bicycle, or pedestrian"),
    minutes: int = Query(default=10, decription="travel time in minutes")
):

    if not location.strip() or not costing.strip():
        return error(400, "missing_parameter", "Parameters 'start' and 'end' are both required.")

    if minutes <= 0:
        return error(400, "invalid_time", "Travel time in minutes must be a postive integer")

    try:
        lat, lon = parse_coordinate(location, "location")
    except ValueError as exc:
        # No partial route is returned - the request stops here.
        return error(400, "invalid_coordinate", str(exc))

    if costing not in VALID_COSTINGS:
        return error(
            400,
            "invalid_costing",
            f"Parameter 'costing' must be one of: {', '.join(sorted(VALID_COSTINGS))}.",
        )

    payload = {
        "locations": [{"lat": lat, "lon": lon}],
        "costing": costing,
        "polygons": True,
        "contours": [{"time": minutes, "color": "90EE90"}], #green, can change if you want different color
    }

    # Call to Valhalla engine
    try:
        async with httpx.AsyncClient(timeout=ENGINE_TIMEOUT) as client:
            resp = await client.post(f"{VALHALLA_URL}/isochrone", json=payload)
    except httpx.HTTPError as exc:
        return error(502, "routing_engine_unavailable", f"Could not reach the routing engine: {exc}")


    if resp.status_code != 200:
        return error(404, "no_isochrone_found", "The routing engine could not create an isochrone from that location")

    geojson = resp.json()

    #echo back location, costing and travel_time
    return {
        "location": [lat, lon],
        "costing": costing,
        "minutes": minutes,
        "geojson": geojson,
    }

# ---------------------------------------------------------------------------
# Convenience endpoint - not part of the communication contract
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    status = {"service": "ok", "nominatim": "unknown", "valhalla": "unknown"}
    async with httpx.AsyncClient(timeout=3.0) as client:
        for name, url in ("valhalla", f"{VALHALLA_URL}/status"):
            try:
                r = await client.get(url)
                status[name] = "ok" if r.status_code < 500 else f"http {r.status_code}"
            except httpx.HTTPError:
                status[name] = "unreachable"
    return status