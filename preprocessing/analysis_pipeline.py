from __future__ import annotations
from typing import Optional, Tuple, List
import pandas as pd
import numpy as np
from pyproj import Transformer

# ---- SETTINGS ----
DECIMALS = 3
EMPTY_TOKENS = ["", " ", "-", "NA", "N/A", "nan", "NaN"]
DATE_KEYWORDS = ["date", "pvm", "päivä", "timestamp", "datetime"]
LAT_NAMES  = ["lat", "latitude"]
LON_NAMES  = ["lon", "long", "lng", "longitude"]

# ---- HELPERS ----
def _norm_cols(cols: List[str]) -> List[str]:
    """
    Normalize and deduplicate column names:
    - Keep only [A-Z, a-z, 0-9, _] (other chars -> single underscore)
    - Trim leading/trailing underscores
    - Ensure uniqueness with suffix '__k' if needed
    """
    def clean(name: str) -> str:
        out, prev_us = [], False
        for ch in str(name).strip():
            if ch.isalnum() or ch == "_":
                out.append(ch)
                prev_us = (ch == "_")
            else:
                if not prev_us:
                    out.append("_")
                    prev_us = True
        s = "".join(out).strip("_") or "col"
        return s
    
    seen, result = set(), []
    for c in cols:
        base = clean(c)
        if base in seen:
            k = 1
            while f"{base}__{k}" in seen:
                k += 1
            base = f"{base}__{k}"
        seen.add(base)
        result.append(base)
    return result
    
    
def _parse_dates(series: pd.Series) -> pd.Series:
    """
    Parse dates robustly:
    1) Try common explicit date formats
    2) Fallback to flexible parser with dayfirst=True (UTC)
    """
    common_formats = ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"]
    for fmt in common_formats:
        try:
            return pd.to_datetime(series, format=fmt, errors="coerce", utc=True)
        except Exception:
            pass
    return pd.to_datetime(series, errors="coerce", dayfirst=True, utc=True)


def _is_likely_date(colname: str) -> bool:
    """Heuristic: does the column name hint a date/time field?"""
    n = str(colname).lower()
    return any(key in n for key in DATE_KEYWORDS)


def _coerce_numbers_from_str(col: pd.Series, thr: float = 0.8) -> pd.Series:
    """
    Convert string-like numerics to numeric dtype if ≥ 'thr' of sample values are numbers.
    - Accepts '1,23' by normalizing comma to dot.
    """
    if not pd.api.types.is_string_dtype(col):
        return col
    sample = col.dropna().astype(str).head(200)
    if sample.empty:
        return col
    
    sample_norm = sample.str.replace(",", ".", regex=False)
    try:
        probe = pd.to_numeric(sample_norm)
    except Exception:
        return col

    # If at least thr portion of values convert --> convert whole column
    if probe.notna().mean() >= thr:
        return pd.to_numeric(col.str.replace(",", ".", regex=False), errors="coerce")
    return col


def _normalize_empty_strings(df: pd.DataFrame) -> pd.DataFrame:
    """
    Replace common "empty" tokens in object/string columns to NA with pandas.NA.
    Keeps non-string dtypes intact.
    """
    # Precompile token set for quick lookups
    empty_tokens = {t.strip() for t in EMPTY_TOKENS}

    def normalize_value(val):
        if isinstance(val, str) and val.strip() in empty_tokens:
            return pd.NA
        return val

    # Go through columns and normalize only textual ones
    for col in df.select_dtypes(include=["object", "string"]).columns:
        df[col] = df[col].map(normalize_value)

    return df


# ---- Coordinate detection and conversion ----
def _find_lat_lon(df: pd.DataFrame) -> Tuple[Optional[str], Optional[str]]:
    """
    Find lat/lon columns by simple name lists. Requires BOTH to exist to be usable.
    """
    lat = next((c for c in df.columns if str(c).lower() in LAT_NAMES), None)
    lon = next((c for c in df.columns if str(c).lower() in LON_NAMES), None)
    return lat, lon


def _has_kkj_xy(df: pd.DataFrame) -> Tuple[Optional[str], Optional[str]]:
    """
    Detect projected KKJ coordinate columns (Finnish national grid, EPSG:2393)
    by name patterns after normalization.
    E.g. 'KKJx-coordinate' -> 'KKJx_coordinate' -> matches 'kkjx'/'kkjy'.
    """
    # Create lowercase lookup for easier substring search
    col_map = {str(c).lower(): c for c in df.columns}
   
    def find_one(candidates: List[str]) -> Optional[str]:
        for col_lower, orig in col_map.items():
            if any(token in col_lower for token in candidates):
                return orig
        return None
    
    kx = find_one(["kkjx", "kkj_x", "kkjx_coordinate"])
    ky = find_one(["kkjy", "kkj_y", "kkjy_coordinate"])
    return kx, ky


def _kkj_to_wgs84(easting: pd.Series, northing: pd.Series) -> Tuple[pd.Series, pd.Series]:
    """
    Transform KKJ (EPSG:2393) -> WGS84 (EPSG:4326).
    Returns (lat, lon) as series aligned to input index.
    Fallback to NaNs on failure.
    """
    try:
        # (x, y) -> (lon, lat)
        tf = Transformer.from_crs(2393, 4326, always_xy=True)
        x = pd.to_numeric(easting, errors="coerce")
        y = pd.to_numeric(northing, errors="coerce")
        lon, lat = tf.transform(x.values, y.values)
        return pd.Series(lat, index=easting.index), pd.Series(lon, index=easting.index)
    except Exception:
        # pyproj not installed or transform failed
        n = len(easting)
        return pd.Series([np.nan] * n, index=easting.index), pd.Series([np.nan] * n, index=easting.index)


# ---- MAIN FUNCTION ----
def preprocess_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compact preprocessing for visualization:
    1) Normalize headers
    2) Parse date-like columns
    3) Cast non-date objects -> string
    4) Coerce numeric-looking strings -> numbers
    5) Add latitude/longitude either from named lat/lon OR KKJ x/y (EPSG:2393)
    6) Validate coord ranges
    7) Round floats
    8) Normalize 'empty' tokens and drop all-empty rows/cols
    9) Return a defragmented copy
    """
    df = df.copy()

    # 1) Normalize headers
    df.columns = _norm_cols(df.columns.tolist())

    # 2) Parse dates based on header heuristic
    date_cols = [c for c in df.columns if _is_likely_date(c)]
    if date_cols:
        df[date_cols] = df[date_cols].apply(_parse_dates)

    # 3) Non-date objects -> string
    obj_cols = [c for c in df.columns if (df[c].dtype == object) and (not pd.api.types.is_datetime64_any_dtype(df[c]))]
    if obj_cols:
        df[obj_cols] = df[obj_cols].astype("string")

    # 4) Numeric-like strings -> numbers
    for c in df.columns:
        df[c] = _coerce_numbers_from_str(df[c])

    # 5) Coordinates: named lat/lon OR KKJ -> WGS84
    new_cols: dict[str, pd.Series] = {}

    lat_name, lon_name = _find_lat_lon(df)

    if lat_name and lon_name:
        if "latitude" not in df.columns:
            new_cols["latitude"]  = pd.to_numeric(df[lat_name], errors="coerce")
        if "longitude" not in df.columns:
            new_cols["longitude"] = pd.to_numeric(df[lon_name], errors="coerce")
    else:
        kx, ky = _has_kkj_xy(df)
        if kx and ky:
            lat_s, lon_s = _kkj_to_wgs84(df[kx], df[ky])
            new_cols["latitude"]  = lat_s
            new_cols["longitude"] = lon_s

    if new_cols:
        df = pd.concat([df, pd.DataFrame(new_cols, index=df.index)], axis=1)

    # 6) Coordinate sanity (validate ranges and null out invalids)
    if {"latitude", "longitude"} <= set(df.columns):
        ok = df["latitude"].between(-90, 90) & df["longitude"].between(-180, 180)
        df.loc[~ok, ["latitude", "longitude"]] = np.nan

    # 7) Round floats
    float_cols = df.select_dtypes(include="float").columns
    if len(float_cols):
        df[float_cols] = df[float_cols].round(DECIMALS)

    # 8) Normalize empties and drop empty rows/cols
    df = _normalize_empty_strings(df)
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")

    # 9) Defragmented copy back
    return df.copy().reset_index(drop=True)
