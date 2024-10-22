# plane_api.py

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware  # import cors middleware
from pydantic import BaseModel, Field
from typing import Optional
import requests
from math import radians, cos, sin, asin, sqrt, atan2, degrees

app = FastAPI(title="nearest aircraft api", version="2.0")

# configure cors to allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all origins
    allow_credentials=False,  # do not allow credentials
    allow_methods=["*"],  # allow all http methods
    allow_headers=["*"],  # allow all headers
)

class AircraftRequest(BaseModel):
    lat: float = Field(..., description="latitude of the location.")
    lon: float = Field(..., description="longitude of the location.")
    dist: float = Field(5.0, description="search radius in kilometers (default: 5 km).")
    format: Optional[str] = Field(
        "json",
        description="response format: 'json' or 'text'. defaults to 'json'."
    )

class AircraftResponse(BaseModel):
    flight: str
    desc: str
    alt_geom: Optional[int] = None  # made optional
    gs: Optional[int] = None         # made optional
    track: Optional[int] = None      # made optional
    year: Optional[int] = None
    ownop: Optional[str] = None
    distance_mi: float
    bearing: int
    message: Optional[str] = None

@app.get("/health")
def health_check():
    return {"status": "healthy"}

def get_aircraft_data(lat: float, lon: float, dist: float):
    # set the external ads-b api url
    url = f"https://adsb.rickt.dev/adsb.fi/v2/lat/{lat}/lon/{lon}/dist/{dist}"

    try:
        # make a get request to the external ads-b api
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        # raise an http exception if there's an error with the request
        raise HTTPException(status_code=502, detail=f"error fetching data from ads-b api: {e}")
    except ValueError:
        # raise an http exception if there's an error decoding the json response
        raise HTTPException(status_code=502, detail="error decoding json response from ads-b api.")

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    # calculate the distance between two lat/lon points using the haversine formula
    r_mi = 3958.8
    lat1_rad, lon1_rad, lat2_rad, lon2_rad = map(radians, [lat1, lon1, lat2, lon2])
    dlon = lon2_rad - lon1_rad 
    dlat = lat2_rad - lat1_rad 
    a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    distance_mi = r_mi * c
    return distance_mi

def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    # calculate the bearing between two lat/lon points
    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    delta_lon = radians(lon2 - lon1)

    x = sin(delta_lon) * cos(lat2_rad)
    y = cos(lat1_rad) * sin(lat2_rad) - sin(lat1_rad) * cos(lat2_rad) * cos(delta_lon)

    initial_bearing_rad = atan2(x, y)
    initial_bearing_deg = (degrees(initial_bearing_rad) + 360) % 360
    return int(round(initial_bearing_deg))

def find_nearest_aircraft(aircraft_list: list, center_lat: float, center_lon: float):
    # find the nearest aircraft that is airborne with valid speed
    if not aircraft_list:
        return None, None

    nearest = None
    min_distance = float('inf')

    for aircraft in aircraft_list:
        # get the geometric altitude and ground speed
        alt_geom = aircraft.get('alt_geom')
        gs = aircraft.get('gs')

        # exclude aircraft on the ground or with speed 0 or null
        if alt_geom is None or alt_geom <= 0:
            continue  # skip aircraft on the ground
        if gs is None or gs == 0:
            continue  # skip aircraft with speed 0 or null

        # get the latitude and longitude of the aircraft
        aircraft_lat = aircraft.get('lat')
        aircraft_lon = aircraft.get('lon')
        if aircraft_lat is None or aircraft_lon is None:
            continue  # skip if lat or lon is missing

        # calculate the distance from the center point
        distance = haversine_distance(center_lat, center_lon, aircraft_lat, aircraft_lon)
        if distance < min_distance:
            min_distance = distance
            nearest = aircraft

    return nearest, min_distance

@app.post("/nearest_plane")
def nearest_plane(request: AircraftRequest):
    # get the aircraft data from the external ads-b api
    data = get_aircraft_data(request.lat, request.lon, request.dist)
    aircraft_list = data.get('aircraft', [])

    if not aircraft_list:
        # return a 200 response with a message if no aircraft are found
        message = "no aircraft found within the specified radius."
        if request.format.lower() == "text":
            return Response(content=message, media_type="text/plain")
        return AircraftResponse(
            flight="n/a",
            desc=message,
            alt_geom=None,
            gs=None,
            track=None,
            distance_mi=0.0,
            bearing=0,
            message=message
        )

    # find the nearest aircraft with valid altitude and speed
    nearest_aircraft, distance_mi = find_nearest_aircraft(aircraft_list, request.lat, request.lon)

    if not nearest_aircraft:
        # return a 200 response with a message if no valid aircraft are found
        message = "no aircraft found within the specified radius."
        if request.format.lower() == "text":
            return Response(content=message, media_type="text/plain")
        return AircraftResponse(
            flight="n/a",
            desc=message,
            alt_geom=None,
            gs=None,
            track=None,
            distance_mi=0.0,
            bearing=0,
            message=message
        )

    # extract necessary information from the nearest aircraft
    flight = nearest_aircraft.get('flight', 'n/a').strip()
    desc = nearest_aircraft.get('desc', 'unknown aircraft')
    alt_geom = nearest_aircraft.get('alt_geom')  # optional[int]
    gs = nearest_aircraft.get('gs')              # optional[int]
    track = nearest_aircraft.get('track')        # optional[int]

    year = nearest_aircraft.get('year')
    ownop = nearest_aircraft.get('ownOp')

    aircraft_lat = nearest_aircraft.get('lat')
    aircraft_lon = nearest_aircraft.get('lon')
    bearing = calculate_bearing(request.lat, request.lon, aircraft_lat, aircraft_lon)

    distance_mi = round(distance_mi, 2)

    # ensure gs and track are integers or None
    if isinstance(gs, (int, float)):
        gs = int(round(gs))
    else:
        gs = None  # set to none instead of 'n/a'

    if isinstance(track, (int, float)):
        track = int(round(track))
    else:
        track = None  # set to none instead of 'n/a'

    # construct the message
    message_parts = [f"{flight} is a"]

    if year:
        message_parts.append(f"{year}")

    message_parts.append(f"{desc}")

    if ownop:
        message_parts.append(f"operated by {ownop}")

    message_parts.append(f"at bearing {bearing}º,")

    if alt_geom is not None:
        message_parts.append(f"{distance_mi} miles away at {alt_geom}ft.")
    else:
        message_parts.append(f"{distance_mi} miles away.")

    if gs is not None:
        message_parts.append(f"Speed {gs} kts,")
    if track is not None:
        message_parts.append(f"Heading {track}º.")

    message = ' '.join(message_parts)

    # return the response based on the requested format
    if request.format.lower() == "text":
        return Response(content=message + "\n", media_type="text/plain")

    return AircraftResponse(
        flight=flight,
        desc=desc,
        alt_geom=alt_geom,
        gs=gs,
        track=track,
        year=year,
        ownop=ownop,
        distance_mi=distance_mi,
        bearing=bearing,
        message=message
    )
