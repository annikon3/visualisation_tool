import json
import pandas as pd
from typing import Any, Dict, List, Tuple, Optional

# ------ Public API ------
def load_json_or_geojson(raw_bytes: bytes) -> pd.DataFrame:
    """
    Convert raw JSON/GeoJSON bytes into a flat pandas DataFrame.
    - GeoJSON FeatureCollection -> flattens 'properties' and adds latitude/longitude
    - Regular JSON (list of dicts or dict with "data"/"items"/"rows") -> DataFrame
    Raises ValueError on unsupported/invalid payload.
    """
    # Decode bytes safely (handles UTF-8 BOM)
    text = raw_bytes.decode("utf-8-sig")

    # Parse JSON content
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e.msg} (position {e.pos})")
    
    # --- Case 1: GeoJSON FeatureCollection ---
    if _is_geojson(obj):
        return _geojson_to_dataframe(obj)

    # --- Case 2: Plain list of dictionaries ---
    if isinstance(obj, list) and all(isinstance(x, dict) for x in obj):
        return pd.DataFrame(obj)

    # --- Case 3: JSON object with embedded list ---
    if isinstance(obj, dict):
        for key in ("data", "items", "rows"):
            value = obj.get(key)
            if isinstance(value, list) and all(isinstance(x, dict) for x in value):
                return pd.DataFrame(value)

    # --- Unsupported JSON structure ---
    raise ValueError("Unsupported JSON structure (not GeoJSON or list of records).")


# --- Internal helpers ---
def _is_geojson(obj: Any) -> bool:
    """Return True if the object is a GeoJSON FeatureCollection."""
    return isinstance(obj, dict) and obj.get("type") == "FeatureCollection"


def _geojson_to_dataframe(fc: Dict[str, Any]) -> pd.DataFrame:
    """
    Convert a GeoJSON FeatureCollection into a simple DataFrame:
    - Extract all 'properties' fields
    - Derive 'longitude' and 'latitude' from geometry
    """
    features = fc.get("features", [])
    rows: List[Dict[str, Any]] = []

    for feat in features:
        if not isinstance(feat, dict):
            continue
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})

        lon, lat = _get_lonlat(geom)
        if lon is None or lat is None:
            continue

        row = dict(props)
        row["longitude"] = lon
        row["latitude"] = lat
        rows.append(row)

    # Return an empty DataFrame if nothing was usable
    if not rows:
        return pd.DataFrame(columns=["latitude", "longitude"])
    return pd.DataFrame(rows)


def _get_lonlat(geom: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    """
    Extract (longitude, latitude) from a geometry object.
    - For Point: return its coordinates
    - For LineString/Polygon: return simple centroid (average of all vertices)
    """
    if not isinstance(geom, dict):
        return None, None

    gtype = geom.get("type")
    coords = geom.get("coordinates")

    # Case: Point geometry
    if gtype == "Point" and isinstance(coords, (list, tuple)) and len(coords) >= 2:
        return _validate(coords[0], coords[1])

    # Case: Polygon or LineString -> compute average of all vertex points
    points = _flatten_coordinates(coords)
    if not points:
        return None, None

    lon = sum(p[0] for p in points) / len(points)
    lat = sum(p[1] for p in points) / len(points)
    return _validate(lon, lat)


def _flatten_coordinates(coords: Any) -> List[Tuple[float, float]]:
    """Flatten nested coordinate lists into a list of (lon, lat) tuples."""
    points: List[Tuple[float, float]] = []

    def walk(obj):
        if isinstance(obj, (list, tuple)):
            # Nested list: keep walking deeper
            if obj and isinstance(obj[0], (list, tuple)):
                for child in obj:
                    walk(child)
            # Base case: single coordinate pair
            elif len(obj) >= 2:
                x, y = obj[0], obj[1]
                if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                    points.append((float(x), float(y)))

    walk(coords)
    return points


def _validate(lon: float, lat: float) -> Tuple[Optional[float], Optional[float]]:
    """Ensure coordinates are within valid WGS84 range."""
    if not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)):
        return None, None
    if -180 <= lon <= 180 and -90 <= lat <= 90:
        return lon, lat
    return None, None

