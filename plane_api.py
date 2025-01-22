# plane_api.py

from fastapi import FastAPI, HTTPException, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from typing import Optional
import requests
from math import radians, cos, sin, asin, sqrt, atan2, degrees
import os
from dotenv import load_dotenv
from datetime import datetime
from google.cloud import logging as gcp_logging

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
# app
#

app = FastAPI(title=APP_NAME, version=APP_VERSION)

# CORS
allowed_origins = [
    "https://whatsoverhead.rickt.dev",
    "https://whatsoverhead-dev.rickt.dev"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# static dir
from fastapi.staticfiles import StaticFiles

app.mount("/static", StaticFiles(directory="static"), name="static")

#
# gcp logging client
#

logging_client = gcp_logging.Client()
logger = logging_client.logger(GCP_LOG)

#
# templates
#

templates = Jinja2Templates(directory="templates")

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
    alt_geom: Optional[int] = None
    gs: Optional[int] = None
    track: Optional[int] = None
    year: Optional[int] = None
    ownop: Optional[str] = None
    distance_km: float
    bearing: int
    relative_speed_knots: Optional[float] = None
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

def calculate_relative_speed(gs: float, aircraft_track: float, user_to_aircraft_bearing: float) -> float:
    # calculate the bearing from aircraft to user
    aircraft_to_user_bearing = (user_to_aircraft_bearing + 180) % 360

    # calculate the angle difference between the aircraft's track and the bearing to user
    angle_diff = aircraft_track - aircraft_to_user_bearing

    # normalize the angle to be within [-180, 180]
    angle_diff = (angle_diff + 180) % 360 - 180

    # calculate the relative speed
    relative_speed = gs * cos(radians(angle_diff))
    return relative_speed  # positive: approaching, negative: moving away

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

        # skip if altitude < 100ft
        if altitude <= 100:
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
            "description": nearest.get('desc', 'Unknown TIS-B aircraft'),
            "altitude_baro": nearest.get('alt_baro'),
            "altitude_geom": nearest.get('alt_geom'),
            "ground_speed": nearest.get('gs'),
            "track": nearest.get('track'),
            "year": nearest.get('year'),
            "operator": nearest.get('ownOp'),
            "distance_km": min_distance,
            "bearing_deg": calculate_bearing(center_lat, center_lon, nearest.get('lat'), nearest.get('lon')),
            "timestamp": datetime.utcnow().isoformat() + 'Z'
        }

        # log the entry to gcp logging
        logger.log_struct(log_entry, severity="INFO")

    # return
    return nearest, min_distance

def get_aircraft_data(lat: float, lon: float, dist: float):
    # set the external ads-b api url
    url = f"{ADSB_API}/lat/{lat}/lon/{lon}/dist/{dist}"

    try:
        # make a request to the external ads-b api
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        # raise an http exception if there's an error with the request
        raise HTTPException(status_code=502, detail=f"Error fetching data from ads-b api: {e}")
    except ValueError:
        # raise an http exception if there's an error decoding the json response
        raise HTTPException(status_code=502, detail="Error decoding json response from ads-b api.")

def get_ordinal_direction(bearing: int) -> str:
    # determine the ordinal direction from the bearing
    # shift the bearing by 22.5 degrees
    direction_index = int(((bearing + 22.5) % 360) // 45)
    directions = ["north", "northeast", "east", "southeaast", "south", "southwest", "west", "northweest"]
    return directions[direction_index]

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    # calculate the distance between two lat/lon points using the haversine formula
    r_km = 6371.0
    lat1_rad, lon1_rad, lat2_rad, lon2_rad = map(radians, [lat1, lon1, lat2, lon2])
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    distance_km = r_km * c
    return distance_km

#
# api endpoints
#

@app.get("/")
def render_whatsoverhead(request: Request):
    # log it
    log_entry = {
        "message": f"{APP_NAME} v{APP_VERSION} rendering home page",
        "severity": "INFO"
    }
    logger.log_struct(log_entry)

    # serve the whatsoverhead template]
    return templates.TemplateResponse("whatsoverhead.html", {"request": request})

@app.get("/health")
def health_check():
    # log it
    log_entry = {
        "message": f"{APP_NAME} v{APP_VERSION} rendering home page",
        "severity": "INFO"
    }
    logger.log_struct(log_entry)
    
    return {"status": "healthy"}

@app.get("/nearest_plane")
def nearest_plane(lat: float, lon: float, dist: Optional[float] = 5.0, format: Optional[str] = "text"):
    if dist is None:
        dist = float(DISTANCE)

    # get the aircraft data from the ads-b api
    data = get_aircraft_data(lat, lon, dist)
    aircraft_list = data.get('aircraft', [])

    # no aircraft nearby
    if not aircraft_list:
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
            relative_speed_knots=None,
            message=message
        )

    # we have aircraft(s), fine the nearest one
    nearest_aircraft, distance_km = find_nearest_aircraft(aircraft_list, lat, lon)

    # nope
    if not nearest_aircraft:
        message = "No aircraft found within the specified radius."

        # return text
        if format.lower() == "text":
            return Response(content=message, media_type="text/plain")
        
        # return fancy
        return AircraftResponse(
            flight="N/A",
            desc=message,
            alt_baro=None,
            alt_geom=None,
            gs=None,
            track=None,
            distance_km=0.0,
            bearing=0,
            relative_speed_knots=None,
            message=message
        )

    # we have a nearest aircraft, get the details
    flight = nearest_aircraft.get('flight', 'N/A').strip()
    desc = nearest_aircraft.get('desc', 'Unknown TIS-B aircraft')
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

    # ground speed?
    if isinstance(gs, (int, float)):
        gs = int(round(gs))
    else:
        gs = None

    # track speed?
    if isinstance(track, (int, float)):
        track = int(round(track))
    else:
        track = None

    # grok useful altitude data 
    if alt_baro is not None and not isinstance(alt_baro, str):
        used_altitude = alt_baro
    elif alt_geom is not None:
        used_altitude = alt_geom
    else:
        used_altitude = None

    # if we have ground speed and track speed we can calculate the relative speed 
    if gs is not None and track is not None:
        relative_speed_knots = calculate_relative_speed(gs, track, bearing)
    else:
        relative_speed_knots = None

    # assemble the parts of the message
    message_parts = [f"{flight} is a"]

    if year:
        message_parts.append(f"{year}")

    message_parts.append(f"{desc}")

    if ownop:
        message_parts.append(f"operated by {ownop}")

    direction = get_ordinal_direction(bearing)

    message_parts.append(f"at bearing {bearing}º ({direction}),")

    if used_altitude is not None:
        message_parts.append(f"{distance_km} kilometers away at {used_altitude}ft,")
    else:
        message_parts.append(f"{distance_km} kilometers away,")

    if gs is not None:
        message_parts.append(f"speed {gs} knots,")

    if track is not None:
        message_parts.append(f"ground track {track}º,")

    if relative_speed_knots is not None:
        if relative_speed_knots > 0:
            message_parts.append(f"approaching at {relative_speed_knots:.0f} knots.")
        elif relative_speed_knots < 0:
            message_parts.append(f"receding at {abs(relative_speed_knots):.0f} knots.")
        else:
            message_parts.append("maintaining distance.")

    # bundle
    message = ' '.join(message_parts)

    # log it
    log_entry = {
        "message": message,
        "severity": "INFO"
    }
    logger.log_struct(log_entry)

    # return text
    if format.lower() == "text":
        return Response(content=message + "\n", media_type="text/plain")

    # return fancy
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
        relative_speed_knots=relative_speed_knots,
        message=message
    )

# EOF
