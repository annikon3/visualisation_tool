from __future__ import annotations
from typing import Iterable, Optional, List
import pandas as pd
from utils.helpers import extract_years
from utils.ids import IDS

# ---------- Helpers to visualisation filtering (pure, no Dash) ----------

def subset_to_active(df: pd.DataFrame, active_cols: Iterable[str], also_keep: Optional[List[str]] = None) -> pd.DataFrame:
    """Keep only active + lat/lon + optional also_keep; return a copy."""
    active = set(active_cols or [])
    extra  = {c for c in (also_keep or []) if c in df.columns}
    must   = {"latitude", "longitude"} if {"latitude", "longitude"}.issubset(df.columns) else set()
    keep   = [c for c in df.columns if (c in active) or (c in must) or (c in extra)]
    if not keep: 
        return df.iloc[0:0].copy()  # empty frame if nothing to keep
    return df[keep].copy()

def apply_value_filter(df: pd.DataFrame, col: Optional[str], val: Optional[str], all_token: Optional[str] = None) -> pd.DataFrame:
    """Apply equality filter unless value equals all_token."""
    if not col or val is None or col not in df.columns:
        return df
    if all_token is not None and val == all_token:
        return df
    # Compare as string to handle numbers/booleans uniformly
    return df[df[col].astype(str) == str(val)]

def apply_year_filter(df: pd.DataFrame, time_col: Optional[str], years: Optional[List[int]]) -> pd.DataFrame:
    """
    Filter rows to the given list of years using helpers.extract_years().
    Keeps only rows where the extracted year is in the provided list.
    Skips filtering if IDS.ALL_SENTINEL present.
    """
    if not time_col or time_col not in df.columns or not years:
        return df
    
    # Skip if All is selected
    if isinstance(years, (list, tuple, set)) and IDS.ALL_SENTINEL in years:
        return df
    
    # Normalize single int -> list[int]
    if not isinstance(years, list):
        years = [years]

    # Convert possible string values like "2009" -> 2009
    years = [int(y) for y in years if str(y).isdigit()]

    # Extract numeric years from the time column
    year_series = extract_years(df[time_col]).astype("Int64")
    mask = year_series.isin(years)
    return df.loc[mask.fillna(False)]
