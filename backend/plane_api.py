# plane_api.py

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware  # import cors middleware
from pydantic import BaseModel, Field
from typing import Optional
import requests
from math import radians, cos, sin, asin, sqrt, atan2, degrees
import os
from dotenv import load_dotenv
from datetime import datetime
from google.cloud import logging as gcp_logging  # import gcp logging

#
# env
#
load_dotenv(override=True)
ADSB_API = os.getenv("ADSB_API")
APP_NAME = os.getenv("APP_NAME")
APP_VERSION = os.getenv("APP_VERSION")
DISTANCE = os.getenv("DISTANCE")
GCP_LOG = os.getenv("GCP_LOG")

#
# app / cors (todo: fix)
#
app = FastAPI(title=APP_NAME, version=APP_VERSION)
allowed_origins = [
    "https://whatsoverhead.rickt.dev",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins, 
    allow_credentials=False, 
    allow_methods=["GET"], 
    allow_headers=["*"], 
)

#
# gcp logging client
#
logging_client = gcp_logging.Client()
logger = logging_client.logger(GCP_LOG) 

#
# classes
#

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
    alt_baro: Optional[str] = None
    alt_geom: Optional[int] = None  # made optional
    gs: Optional[int] = None         # made optional
    track: Optional[int] = None      # made optional
    year: Optional[int] = None
    ownop: Optional[str] = None
    distance_km: float
    bearing: int
    message: Optional[str] = None

# 
# funcs
#

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

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    # calculate the distance between two lat/lon points using the haversine formula
    r_km = 6371.0  # earth's radius in kilometers
    lat1_rad, lon1_rad, lat2_rad, lon2_rad = map(radians, [lat1, lon1, lat2, lon2])
    dlon = lon2_rad - lon1_rad 
    dlat = lat2_rad - lat1_rad 
    a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    distance_km = r_km * c
    return distance_km

def find_nearest_aircraft(aircraft_list: list, center_lat: float, center_lon: float):
    # find the nearest aircraft that is airborne with valid speed
    if not aircraft_list:
        return None, None

    nearest = None
    min_distance = float('inf')

    for aircraft in aircraft_list:
        # get the geometric & barometric altitude and ground speed
        alt_geom = aircraft.get('alt_geom')
        alt_baro = aircraft.get('alt_baro')
        gs = aircraft.get('gs')

        # exclude aircraft on the ground
        if isinstance(alt_baro, str) and alt_baro.lower() == "ground":
            continue
        # determine aircraft's altitude by various means
        if alt_baro is not None:
            # barometric altitude
            try:
                altitude = float(alt_baro)
            except (ValueError, TypeError):
                continue
        elif alt_geom is not None:
            # wgs84 altitude
            try:
                altitude = float(alt_geom)
            except (ValueError, TypeError):
                continue
        else:
            # can't find good altitude for this aircraft, skip it
            continue
        # skip if altitude < 155ft
        if altitude <= 155:
            # skip aircraft with altitude <= 155ft
            continue 
        if gs is None or gs == 0:
            # skip aircraft with speed 0 or null
            continue  

        # aircraft is good. get its lat/lon
        aircraft_lat = aircraft.get('lat')
        aircraft_lon = aircraft.get('lon')
        if aircraft_lat is None or aircraft_lon is None:
            # skip if lat or lon is missing
            continue  

        # calculate the distance from reported user position
        distance_km = haversine_distance(center_lat, center_lon, aircraft_lat, aircraft_lon)
        if distance_km < min_distance:
            min_distance = distance_km
            nearest = aircraft

    if nearest:
        # prepare log entry
        log_entry = {
            "flight": nearest.get('flight', 'N/A').strip(),
            "description": nearest.get('desc', 'unknown tis-b aircraft'),
            "altitude_baro": nearest.get('alt_baro'),
            "altitude_geom": nearest.get('alt_geom'),
            "ground_speed": nearest.get('gs'),
            "track": nearest.get('track'),
            "year": nearest.get('year'),
            "operator": nearest.get('ownOp'),
            "distance_km": min_distance,
            "bearing_deg": calculate_bearing(center_lat, center_lon, nearest.get('lat'), nearest.get('lon')),
            "timestamp": datetime.utcnow().isoformat() + 'Z'  # iso 8601 format
        }

        # log the entry to gcp logging
        logger.log_struct(log_entry)

    # return 
    return nearest, min_distance

def get_aircraft_data(lat: float, lon: float, dist: float):
    # set the external ads-b api url
    url = f"{ADSB_API}/lat/{lat}/lon/{lon}/dist/{dist}"

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

def log_message(message):
    # log the aircraft spot to gcp logging
    log_entry = {
        "message": message,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    logger.log_struct(log_entry)

#
# api endpoints
#

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.get("/nearest_plane")
def nearest_plane(lat: float, lon: float, dist: Optional[float] = 5.0, format: Optional[str] = "text"):
    if dist is None:
        dist = float(DISTANCE)
        
    # get the aircraft data from the external ads-b api
    data = get_aircraft_data(lat, lon, dist)
    aircraft_list = data.get('aircraft', [])

    if not aircraft_list:
        # return a 200 response with a message if no aircraft are found
        message = "No aircraft found within the specified radius."
        if format.lower() == "text":
            return Response(content=message, media_type="text/plain")
        return AircraftResponse(
            flight="N/A",
            desc=message,
            alt_baro=None,
            alt_geom=None,
            gs=None,
            track=None,
            distance_km=0.0,
            bearing=0,
            message=message
        )

    # find the nearest aircraft with valid altitude and speed
    nearest_aircraft, distance_km = find_nearest_aircraft(aircraft_list, lat, lon)

    if not nearest_aircraft:
        # return a 200 response with a message if no valid aircraft are found
        message = "No aircraft found within the specified radius."
        if format.lower() == "text":
            return Response(content=message, media_type="text/plain")
        return AircraftResponse(
            flight="N/A",
            desc=message,
            alt_baro=None,
            alt_geom=None,
            gs=None,
            track=None,
            distance_km=0.0,
            bearing=0,
            message=message
        )

    # extract necessary information from the nearest aircraft
    flight = nearest_aircraft.get('flight', 'N/A').strip()
    desc = nearest_aircraft.get('desc', 'unknown tis-b aircraft')
    alt_baro = nearest_aircraft.get('alt_baro')
    alt_geom = nearest_aircraft.get('alt_geom')
    gs = nearest_aircraft.get('gs')
    track = nearest_aircraft.get('track')

    year = nearest_aircraft.get('year')
    ownop = nearest_aircraft.get('ownOp')

    aircraft_lat = nearest_aircraft.get('lat')
    aircraft_lon = nearest_aircraft.get('lon')
    bearing = calculate_bearing(lat, lon, aircraft_lat, aircraft_lon)

    distance_km = round(distance_km, 1)

    # ensure gs and track are integers or none
    if isinstance(gs, (int, float)):
        gs = int(round(gs))
    else:
        gs = None  # set to none instead of 'N/A'

    if isinstance(track, (int, float)):
        track = int(round(track))
    else:
        track = None  # set to none instead of 'N/A'

    # determine which altitude to use
    if alt_baro is not None and not isinstance(alt_baro, str):
        used_altitude = alt_baro
    elif alt_geom is not None:
        used_altitude = alt_geom
    else:
        used_altitude = None

    # construct the message
    message_parts = [f"{flight} is a"]

    if year:
        message_parts.append(f"{year}")

    message_parts.append(f"{desc}")

    if ownop:
        message_parts.append(f"operated by {ownop}")

    message_parts.append(f"at bearing {bearing}º,")

    if used_altitude is not None:
        message_parts.append(f"{distance_km} kilometers away at {used_altitude}ft,")
    else:
        message_parts.append(f"{distance_km} kilometers away,")

    if gs is not None:
        message_parts.append(f"speed {gs} knots,")
    if track is not None:
        message_parts.append(f"ground track {track}º.")

    message = ' '.join(message_parts)

    # return the response based on the requested format
    if format.lower() == "text":
        return Response(content=message + "\n", media_type="text/plain")

    # log the aircraft spot
    log_message(f"{message}")

    return AircraftResponse(
        flight=flight,
        desc=desc,
        alt_baro=alt_baro,
        alt_geom=alt_geom,
        gs=gs,
        track=track,
        year=year,
        ownop=ownop,
        distance_km=distance_km,
        bearing=bearing,
        message=message
    )

# eof
