"""
Test program for the Isochrone Microservice - CS361 Assignment 9.

IMPORTANT (rubric: "test program and microservice are not directly calling
each other"): this file imports ONLY the third-party `requests` library. It does
not import main.py, it does not import any function from the microservice, and
it never touches the microservice's engine. The ONLY channel between this
program and the microservice is HTTP over the REST communication pipe.

Run the microservice first:
    uvicorn main:app --port 8003

Then, in a second terminal:
    python test_program.py
"""

import json

import requests  # third-party HTTP client - NOT microservice code

BASE_URL = "http://localhost:8003"
TIMEOUT = 30

# Real Inland Empire coordinates - inside the loaded map region.
UCR = "33.9737,-117.3281"          # University of California, Riverside


def banner(text: str) -> None:
    print("\n" + "=" * 70)
    print(text)
    print("=" * 70)


def rings(geometry: dict) -> list[list[list[float]]]:
    """Flatten a Polygon or MultiPolygon into a list of coordinate rings.

    GeoJSON stores positions as [lon, lat], which is the opposite order from
    the 'lat,lon' this service accepts in its query string. That flip is the
    single most common source of "my polygon is in the ocean" bugs.
    """
    kind = geometry.get("type")
    if kind == "Polygon":
        return geometry.get("coordinates", [])
    if kind == "MultiPolygon":
        return [ring for polygon in geometry.get("coordinates", []) for ring in polygon]
    return []


def point_in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    """Ray-casting point-in-polygon test. Ring positions are [lon, lat]."""
    inside = False
    count = len(ring)
    for i in range(count):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[(i + 1) % count][0], ring[(i + 1) % count][1]
        if (y1 > lat) != (y2 > lat):
            x_at_lat = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
            if lon < x_at_lat:
                inside = not inside
    return inside


def scenario_1_isochrone() -> None:
    """User Story: Get the area reachable within a travel time."""
    banner("SCENARIO 1 - 10-minute drive-time area  (GET /isochrone)")

    # ---- REQUEST: parameters are sent as a URL query string -----------------
    params = {"location": UCR, "minutes": 10, "mode": "drive"}
    print(f"REQUESTING -> GET {BASE_URL}/isochrone  params={params}")
    response = requests.get(f"{BASE_URL}/isochrone", params=params, timeout=TIMEOUT)

    # ---- RECEIVE: read the status code, then parse the JSON body -----------
    print(f"RECEIVED   <- HTTP {response.status_code} in "
          f"{response.elapsed.total_seconds() * 1000:.0f} ms")
    data = response.json()

    response_geojson = data['geojson']

    if response.status_code != 200:
        print(f"ERROR      <- {data['error']}: {data['message']}")
        return

    feature = response_geojson["features"][0]
    all_rings = rings(feature["geometry"])
    total_points = sum(len(r) for r in all_rings)
    print(f"  type            : {response_geojson['type']}")
    print(f"  location        : {data['location']}")
    print(f"  minutes         : {data['minutes']}")
    print(f"  mode            : {data['mode']}")
    print(f"  feature count   : {len(response_geojson['features'])}")
    print(f"  geometry type   : {feature['geometry']['type']}")
    print(f"  boundary points : {total_points}")
    print(f"  first position  : {all_rings[0][0]}  (GeoJSON order: [lon, lat])")
    print("  (a consumer would hand this straight to a map as a GeoJSON layer)")


def scenario_2_encloses_start() -> None:
    """The returned boundary must encompass the starting coordinate."""
    banner("SCENARIO 2 - The boundary encloses the starting coordinate")

    params = {"location": UCR, "minutes": 10, "mode": "drive"}
    response = requests.get(f"{BASE_URL}/isochrone", params=params, timeout=TIMEOUT)
    if response.status_code != 200:
        print("  could not fetch an isochrone to check")
        return

    data = response.json()
    response_geojson = data['geojson']


    lat, lon = data["location"]
    all_rings = rings(response_geojson["features"][0]["geometry"])

    # A point inside an odd number of rings is inside the shape.
    hits = sum(1 for ring in all_rings if point_in_ring(lon, lat, ring))
    inside = hits % 2 == 1
    print(f"  starting coordinate : {lat}, {lon}")
    print(f"  rings tested        : {len(all_rings)}")
    print(f"  rings containing it : {hits}")
    print(f"  start is inside the reachable area? "
          f"{'yes' if inside else 'NO - CONTRACT VIOLATION'}")


def scenario_3_reproducibility() -> None:
    """The same request twice must return the same result."""
    banner("SCENARIO 3 - Reproducibility: identical requests, identical results")

    params = {"location": UCR, "minutes": 10, "mode": "drive"}
    print(f"REQUESTING -> GET {BASE_URL}/isochrone  params={params}   (twice)")
    first = requests.get(f"{BASE_URL}/isochrone", params=params, timeout=TIMEOUT)
    second = requests.get(f"{BASE_URL}/isochrone", params=params, timeout=TIMEOUT)

    if first.status_code != 200 or second.status_code != 200:
        print("  could not fetch two isochrones to compare")
        return

    # Compare the parsed bodies with sorted keys, so the check is about the
    # data and not about incidental key ordering.
    a = json.dumps(first.json(), sort_keys=True)
    b = json.dumps(second.json(), sort_keys=True)
    print(f"  response 1 length : {len(a)} characters")
    print(f"  response 2 length : {len(b)} characters")
    print(f"  identical? {'yes' if a == b else 'NO - CONTRACT VIOLATION'}")


def scenario_4_invalid_mode() -> None:
    """Error path: an unsupported mode is rejected and names what IS supported."""
    banner("SCENARIO 4 - Unsupported mode is rejected  (GET /isochrone)")

    params = {"location": UCR, "minutes": 10, "mode": "hovercraft"}
    print(f"REQUESTING -> GET {BASE_URL}/isochrone  params={params}")
    response = requests.get(f"{BASE_URL}/isochrone", params=params, timeout=TIMEOUT)

    print(f"RECEIVED   <- HTTP {response.status_code}")
    data = response.json()

    print(f"  error   : {data['error']}")
    print(f"  message : {data['message']}")
    print(f"  lists the accepted modes? "
          f"{'yes' if all(m in data['message'] for m in ('drive', 'walk', 'bike')) else 'NO'}")
    print(f"  features present in body? "
          f"{'YES - CONTRACT VIOLATION' if 'features' in data else 'no (correct)'}")


def scenario_5_mode_sizes() -> None:
    """A walk isochrone must cover less ground than a drive isochrone."""
    banner("SCENARIO 5 - Slower modes reach less far in the same time")

    for mode in ("walk", "bike", "drive"):
        params = {"location": UCR, "minutes": 10, "mode": mode}
        response = requests.get(f"{BASE_URL}/isochrone", params=params, timeout=TIMEOUT)
        if response.status_code != 200:
            print(f"  {mode:6s} -> ERROR {response.json().get('error')}")
            continue
        data = response.json()
        response_geojson = data['geojson']
        all_rings = rings(response_geojson["features"][0]["geometry"])
        lons = [p[0] for ring in all_rings for p in ring]
        lats = [p[1] for ring in all_rings for p in ring]
        span_lon = max(lons) - min(lons)
        span_lat = max(lats) - min(lats)
        print(f"  {mode:6s} -> bounding box {span_lon:.4f}° lon x {span_lat:.4f}° lat")
    print("  (drive should span the widest box, walk the narrowest)")


def main() -> None:
    print("Isochrone Microservice - test program")
    print(f"Communication pipe: REST over HTTP, base URL {BASE_URL}")

    try:
        scenario_1_isochrone()
        scenario_2_encloses_start()
        scenario_3_reproducibility()
        scenario_4_invalid_mode()
        scenario_5_mode_sizes()
    except requests.exceptions.ConnectionError:
        print(f"\nCould not connect to {BASE_URL}. "
              "Start the microservice with:  uvicorn main:app --port 8006")
        return

    banner("All scenarios finished")


if __name__ == "__main__":
    main()