# plane_api.py

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware  # Import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import requests
from math import radians, cos, sin, asin, sqrt, atan2, degrees

app = FastAPI(title="Nearest Aircraft API", version="2.0")

# Configure CORS to allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=False,  # Do not allow credentials
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

class AircraftRequest(BaseModel):
    lat: float = Field(..., description="Latitude of the location.")
    lon: float = Field(..., description="Longitude of the location.")
    dist: float = Field(5.0, description="Search radius in kilometers (default: 5 km).")

class AircraftResponse(BaseModel):
    flight: str
    desc: str
    alt_geom: Optional[int] = None  # Made Optional
    gs: Optional[int] = None         # Made Optional
    track: Optional[int] = None      # Made Optional
    year: Optional[int] = None
    ownop: Optional[str] = None
    distance_mi: float
    bearing: int
    message: Optional[str] = None

@app.get("/health")
def health_check():
    return {"status": "healthy"}

def get_aircraft_data(lat: float, lon: float, dist: float):
    # Updated URL as per your latest code
    url = f"https://adsb.rickt.dev/adsb.fi/v2/lat/{lat}/lon/{lon}/dist/{dist}"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Error fetching data from ADS-B API: {e}")
    except ValueError:
        raise HTTPException(status_code=502, detail="Error decoding JSON response from ADS-B API.")

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R_mi = 3958.8
    lat1_rad, lon1_rad, lat2_rad, lon2_rad = map(radians, [lat1, lon1, lat2, lon2])
    dlon = lon2_rad - lon1_rad 
    dlat = lat2_rad - lat1_rad 
    a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    distance_mi = R_mi * c
    return distance_mi

def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    delta_lon = radians(lon2 - lon1)

    x = sin(delta_lon) * cos(lat2_rad)
    y = cos(lat1_rad) * sin(lat2_rad) - sin(lat1_rad) * cos(lat2_rad) * cos(delta_lon)

    initial_bearing_rad = atan2(x, y)
    initial_bearing_deg = (degrees(initial_bearing_rad) + 360) % 360
    return int(round(initial_bearing_deg))

def find_nearest_aircraft(aircraft_list: list, center_lat: float, center_lon: float):
    if not aircraft_list:
        return None, None

    nearest = None
    min_distance = float('inf')

    for aircraft in aircraft_list:
        # Exclude planes on the ground by checking alt_geom
        alt_geom = aircraft.get('alt_geom')
        if alt_geom is None or alt_geom <= 0:
            continue  # Skip aircraft on the ground

        aircraft_lat = aircraft.get('lat')
        aircraft_lon = aircraft.get('lon')
        if aircraft_lat is None or aircraft_lon is None:
            continue
        distance = haversine_distance(center_lat, center_lon, aircraft_lat, aircraft_lon)
        if distance < min_distance:
            min_distance = distance
            nearest = aircraft

    return nearest, min_distance

@app.post("/nearest_plane", response_model=AircraftResponse)
def nearest_plane(request: AircraftRequest):
    data = get_aircraft_data(request.lat, request.lon, request.dist)
    aircraft_list = data.get('aircraft', [])

    if not aircraft_list:
        # Changed to return 200 instead of 404
        return AircraftResponse(
            flight="N/A",
            desc="No aircraft found within the specified radius.",
            alt_geom=None,
            gs=None,
            track=None,
            distance_mi=0.0,
            bearing=0,
            message="No aircraft found within the specified radius."
        )

    nearest_aircraft, distance_mi = find_nearest_aircraft(aircraft_list, request.lat, request.lon)

    if not nearest_aircraft:
        # Changed to return 200 instead of 404
        return AircraftResponse(
            flight="N/A",
            desc="No aircraft found within the specified radius.",
            alt_geom=None,
            gs=None,
            track=None,
            distance_mi=0.0,
            bearing=0,
            message="No aircraft found within the specified radius."
        )

    flight = nearest_aircraft.get('flight', 'N/A').strip()
    desc = nearest_aircraft.get('desc', 'Unknown Aircraft')
    alt_geom = nearest_aircraft.get('alt_geom')  # Optional[int]
    gs = nearest_aircraft.get('gs')              # Optional[int]
    track = nearest_aircraft.get('track')        # Optional[int]

    year = nearest_aircraft.get('year')
    ownop = nearest_aircraft.get('ownop')

    aircraft_lat = nearest_aircraft.get('lat')
    aircraft_lon = nearest_aircraft.get('lon')
    bearing = calculate_bearing(request.lat, request.lon, aircraft_lat, aircraft_lon)

    distance_mi = round(distance_mi, 2)

    if isinstance(gs, (int, float)):
        gs = int(round(gs))
    else:
        gs = None  # Set to None instead of 'N/A'

    if isinstance(track, (int, float)):
        track = int(round(track))
    else:
        track = None

    message_parts = [f"{flight} is a"]

    if year:
        message_parts.append(f"{year}")

    message_parts.append(f"{desc}")

    if ownop:
        message_parts.append(f"operated by {ownop}")

    if alt_geom is not None:
        message_parts.append(f"{distance_mi} miles away at {alt_geom}ft.")
    else:
        message_parts.append(f"{distance_mi} miles away.")

    message_parts.append(f"Bearing {bearing}º.")

    if gs is not None:
        message_parts.append(f"Speed {gs}kts.")
    if track is not None:
        message_parts.append(f"Heading {track}º")

    message = ' '.join(message_parts)

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
