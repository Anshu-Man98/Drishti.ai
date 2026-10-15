"""
Geospatial calculation and spacetime travel feasibility tools for FinShield.
Deterministic mathematical tools for Haversine distance and transit physics.
"""

import math
from datetime import datetime
from typing import Tuple, Dict, Any, Optional


EARTH_RADIUS_KM = 6371.0


def haversine_km(
    a: Any,
    b: Any = None,
    lat2: Optional[float] = None,
    lon2: Optional[float] = None
) -> float:
    """
    Computes great-circle distance between two coordinate pairs in kilometers.
    Supports:
    - haversine_km((lat1, lon1), (lat2, lon2))
    - haversine_km(lat1, lon1, lat2, lon2)
    - haversine_km(event1, event2)
    Returns 0.0 if coordinates are identical or missing.
    """
    if lat2 is not None and lon2 is not None:
        lat1, lon1 = a, b
    elif b is not None:
        if isinstance(a, (list, tuple)):
            lat1, lon1 = a[0], a[1]
        elif hasattr(a, "lat") and hasattr(a, "lng"):
            lat1, lon1 = a.lat, a.lng
        elif isinstance(a, dict):
            lat1, lon1 = a.get("lat"), a.get("lng", a.get("lon"))
        else:
            return 0.0

        if isinstance(b, (list, tuple)):
            lat2, lon2 = b[0], b[1]
        elif hasattr(b, "lat") and hasattr(b, "lng"):
            lat2, lon2 = b.lat, b.lng
        elif isinstance(b, dict):
            lat2, lon2 = b.get("lat"), b.get("lng", b.get("lon"))
        else:
            return 0.0
    else:
        return 0.0

    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return 0.0

    # If coordinates are at origin / missing
    if (lat1 == 0.0 and lon1 == 0.0) or (lat2 == 0.0 and lon2 == 0.0):
        return 0.0

    # Coordinates match
    if math.isclose(lat1, lat2, abs_tol=1e-5) and math.isclose(lon1, lon2, abs_tol=1e-5):
        return 0.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    sin_dphi_2 = math.sin(delta_phi / 2.0)
    sin_dlambda_2 = math.sin(delta_lambda / 2.0)

    val = sin_dphi_2 * sin_dphi_2 + math.cos(phi1) * math.cos(phi2) * sin_dlambda_2 * sin_dlambda_2
    val = min(1.0, max(0.0, val))  # Guard against numerical domain errors

    c = 2.0 * math.atan2(math.sqrt(val), math.sqrt(1.0 - val))
    return round(EARTH_RADIUS_KM * c, 2)


def min_travel_hours(km: float) -> float:
    """
    Calculates minimum realistic travel hours for a given distance in kilometers.
    - Road travel: km / 80.0 km/h for distance <= 300 km
    - Air travel: 2.5h (airport check-in, security, boarding, taxiing) + km / 700.0 km/h flight speed
    """
    if km <= 0.0:
        return 0.0

    if km <= 300.0:
        return round(km / 80.0, 2)
    else:
        return round(2.5 + (km / 700.0), 2)


def is_feasible(event_a: Any, event_b: Any) -> Dict[str, Any]:
    """
    Determines whether travel between two consecutive spacetime events is physically possible.
    Handles:
    - Same location or same city (< 5 km): Always feasible
    - Missing coordinates: Skipped, not flagged
    - Overnight time gaps: Accurately evaluated
    Returns:
      {
        "feasible": bool,
        "km": float,
        "available_h": float,
        "required_h": float,
        "skipped": bool
      }
    """
    # Extract timestamps
    ts_a = getattr(event_a, "ts", None) if hasattr(event_a, "ts") else event_a.get("ts")
    ts_b = getattr(event_b, "ts", None) if hasattr(event_b, "ts") else event_b.get("ts")

    # Extract coordinates
    lat_a = getattr(event_a, "lat", None) if hasattr(event_a, "lat") else event_a.get("lat")
    lon_a = getattr(event_a, "lng", None) if hasattr(event_a, "lng") else event_a.get("lng")
    lat_b = getattr(event_b, "lat", None) if hasattr(event_b, "lat") else event_b.get("lat")
    lon_b = getattr(event_b, "lng", None) if hasattr(event_b, "lng") else event_b.get("lng")

    # Check for missing coordinates
    if (
        lat_a is None or lon_a is None or lat_b is None or lon_b is None
        or (lat_a == 0.0 and lon_a == 0.0) or (lat_b == 0.0 and lon_b == 0.0)
    ):
        return {
            "feasible": True,
            "km": 0.0,
            "available_h": 0.0,
            "required_h": 0.0,
            "skipped": True
        }

    # Parse datetimes if strings
    if isinstance(ts_a, str):
        ts_a = datetime.fromisoformat(ts_a)
    if isinstance(ts_b, str):
        ts_b = datetime.fromisoformat(ts_b)

    if not ts_a or not ts_b:
        return {
            "feasible": True,
            "km": 0.0,
            "available_h": 0.0,
            "required_h": 0.0,
            "skipped": True
        }

    # Normalize timezone awareness between ts_a and ts_b
    if ts_a.tzinfo is None and ts_b.tzinfo is not None:
        ts_a = ts_a.replace(tzinfo=ts_b.tzinfo)
    elif ts_b.tzinfo is None and ts_a.tzinfo is not None:
        ts_b = ts_b.replace(tzinfo=ts_a.tzinfo)

    # Available time in hours
    available_seconds = abs((ts_b - ts_a).total_seconds())
    available_h = round(available_seconds / 3600.0, 2)

    # Distance
    km = haversine_km((lat_a, lon_a), (lat_b, lon_b))

    # Same location or medical complex (< 5 km)
    if km < 5.0:
        return {
            "feasible": True,
            "km": km,
            "available_h": available_h,
            "required_h": 0.05,
            "skipped": False
        }

    required_h = min_travel_hours(km)
    feasible = available_h >= required_h

    return {
        "feasible": feasible,
        "km": km,
        "available_h": available_h,
        "required_h": required_h,
        "skipped": False
    }
