# cs-361-microservice-isochrone
For the isochrone microservice in CS 361

## Requesting Data from the microservice
Send an HTTP GET request to the microservice, with a coordinate, travel mode, and time budget as query parameters.<br>
**Base URL:** http://localhost:8003<br>
**Endpoint:** /isochrone<br>
**Method:** GET<br>
Query Parameters:
| **Parameter** | **Type**   | **Required** | **Description**                          |
|-----------|--------|----------|---------------------------------------|
| `location` | string | Yes      | start coordinate as "lat,lon"  |
| `mode` | string | Yes      | travel mode - one of `drive`, `walk`, `bike`  |
| `minutes` | integer | No (default `10`)      | travel time budget in minutes; must be a positive integer  |
**Example call:**
```
import requests
BASE_URL = "http://localhost:8003"
# Request: get a 10-minute drive-time area
isochrone_response = requests.get(
    f"{BASE_URL}/isochrone",
    params={"location": "33.9737,-117.3281", "mode": "drive", "minutes": 10},
    timeout=10,
)
```
## Receiving Data from the microservice
Microservice responds with JSON. On success returns HTTP 200 with the reachable area as a GeoJSON FeatureCollection. On error will return an error code and a message. Refer to table below for details.<br>
<br>
**Successful response:**
| **Field** | **Type**  | **Description** |
|-----------|--------|----------|
| `location` | array of floats     | `[lat, lon]` of the point the isochrone was generated from |
| `mode` | string | the travel mode used, as sent  |
| `minutes` | integer | the travel time budget used, as sent  |
| `geojson` | object | a GeoJSON FeatureCollection whose feature geometry is the reachable-area polygon using the desired transport mode |
**Example success response:**
```
{
  "location": [33.9721, -117.3254],
  "mode": "bike",
  "minutes": 5,
  "geojson": {
    "type": "FeatureCollection",
    "features": [
      {
        "type": "Feature",
        "properties": {
          "fill-opacity": 0.33,
          "fillColor": "#90EE90",
          "opacity": 0.33,
          "fill": "#90EE90",
          "fillOpacity": 0.33,
          "color": "#90EE90",
          "contour": 5,
          "metric": "time"
        },
        "geometry": {
          "type": "Polygon",
          "coordinates": [[[-117.3254, 33.979305], [-117.3274, 33.979699], "..."]]
        }
      }
    ]
  }
}
```
**Error responses:**
| **Status Codes** | **Type**  | **Description** |
|-----------|--------|----------|
| `400` | missing_location    | `location` was missing/blank  |
| `400` | missing_mode   | `mode` was missing/blank  |
| `400` | invalid_time    | `minutes` was not a positive integer  |
| `400` | invalid_coordinate    | `location` was not formatted as `lat,lon`, contained non-numeric values, or was out of range  |
| `400` | invalid_mode    | `mode` was not one of `drive`, `walk`, `bike`  |
| `404` | no_isochrone_found    | the routing engine could not build an isochrone from that location  |
| `502` | routing_engine_unavailable    | the Valhalla routing engine is unreachable  |
**Example error response:**
```
{
  "error": "invalid_mode",
  "message": "Parameter 'mode' must be one of: bike, drive, walk."
}
```
