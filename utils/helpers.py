from __future__ import annotations
from io import StringIO
from typing import Dict, List, Tuple
import pandas as pd

# ---------- Data helpers ----------

def json_to_df(data_json: str) -> pd.DataFrame:
    """Load a DataFrame from dcc.Store JSON (orient='split')."""
    if not data_json:
        return pd.DataFrame()
    return pd.read_json(StringIO(data_json), orient="split")


# ---------- Columns & options ----------
# Sentinel meaning no filtering 
ALL_SENTINEL = "__ALL__"

def flatten_unique(meta: dict) -> list:
    """Return a flat list of unique categorized columns."""
    seen = set()
    unique_columns = []

    for category_columns in meta.values():
        for column in category_columns:
            if column not in seen:
                unique_columns.append(column)
                seen.add(column)
    
    return unique_columns


def make_options(values: List[str]) -> List[Dict[str, str]]:
    """Map a list of strings to Dash dropdown options."""
    return [{"label": v, "value": v} for v in values]


def typed_lists(df: pd.DataFrame, cols: List[str]) -> Tuple[List[str], List[str]]:
    """
    Split a list of columns into (string_cols, numeric_cols) based on dtypes.
    Only columns present in df are considered.
    """
    present = [c for c in cols if c in df.columns]
    str_cols = [c for c in present if df[c].dtype == "string"]
    num_cols = [c for c in present if pd.api.types.is_numeric_dtype(df[c])]
    return str_cols, num_cols


# ---------- Time helper ----------
def extract_years(obj, time_col: str | None = None) -> pd.Series:
    """
    Return a Series of year integers derived from a time column.
    - Flexible signature:
      * extract_years(df, "col")  # DataFrame + column name
      * extract_years(series)     # directly a Series
    - Works with datetime64, integer-like, and string year columns.
    """
    if time_col is not None and isinstance(obj, pd.DataFrame):
        s = obj[time_col]
    else:
        # assume Series
        s = obj

    if pd.api.types.is_datetime64_any_dtype(s):
        years = s.dt.year
    else:
        years = pd.to_numeric(s, errors="coerce").astype("Int64")

    return years