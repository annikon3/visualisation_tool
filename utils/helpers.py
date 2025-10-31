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


# ---------- Time helpers ----------

def extract_years(df: pd.DataFrame, time_col: str) -> pd.Series:
    """
    Return a Series of integer years from a time-like column:
    - datetime64 -> .dt.year
    - else -> numeric coercion to int (invalid -> NA)
    """
    s = df[time_col]
    if pd.api.types.is_datetime64_any_dtype(s):
        return s.dropna().dt.year.astype("Int64")
    return pd.to_numeric(s, errors="coerce").dropna().astype("Int64")
