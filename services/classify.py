import pandas as pd
import numpy as np
from typing import Dict, List

# Rule-based categories, lowercase keywords; matching is case-insensitive.
# - contains_any: match if ANY of these substrings appears in the column name
# - whole_word:   match if the column name equals any of these tokens
CAT_RULES: Dict[str, Dict[str, List[str]]] = {
    "Time": {
        "contains_any": ["date", "time", "aika", "päivä", "kuukausi", "viikko", "vmi", "vuosi", "timestamp", "datetime", "created", "modified"],
        "whole_word": ["pvm", "pp", "dd", "kk", "mm", "yyyy", "vvvv", "vko"]
    },
    "Coordinates": {
        "contains_any": ["lat", "latitude", "lon", "long", "lng", "longitude", "koord", "coord", "x_", "y_"],
        "whole_word": ["x", "y"]
    },
    # Boolean-like detected by dtype/values, not by name
    "Boolean-like": { "contains_any": [], "whole_word": [] },
    "Region or area": {
        "contains_any": ["maakunta", "region", "county", "province", "country", "block", "stand", "plot", "pinta-ala", "area", "pinta_ala"],
        "whole_word": ["site"]
    },
    "Species": {
        "contains_any": ["species"],
        "whole_word": ["puulaji"]
    },
    "Site type": {
        "contains_any": ["metsätyypp", "metsa", "forest type", "site", "soil", "maaperä", "ground type"],
        "whole_word": ["site.type", "site_type", "maan_laji", "maalaji", "maa_laji"]
    },
    "Counts": {
        "contains_any": ["count", "number", "quantity", "määrä", "lukumäärä", "no_", "lkm", "kpl", "qty"],
        "whole_word": []
    },
    "Lengths": {
        "contains_any": ["length", "pituus", "height", "korkeus", "diameter", "läpimitta"],
        "whole_word": []
    },
}

# ---------- Helpers ----------

# Helper to detect Boolean-like columns
_TRUE  = {"1", "true", "yes", "y", "t", "on", "kyllä"}
_FALSE = {"0", "false", "no", "n", "f", "off", "ei"}

# Name-based category matching 
def _match_category(colname: str, rules: Dict[str, List[str]]) -> bool:
    """Name-based match: substring OR exact token match (case-insensitive)."""
    name = str(colname).strip().lower()

    for w in rules.get("contains_any", []):
        if w.lower() in name:
            return True
        
    for w in rules.get("whole_word", []):
        if name == w.lower():
            return True
    return False

# Map values to 0 and 1
def _map_to_01(value):    
    """
    Map a single value to 0 or 1.
    Return np.nan if the value is not a clear boolean token.
    """
    if pd.isna(value):
        return np.nan
    
    # Already a boolean dtype
    if isinstance(value, (bool, np.bool_)):
        return 1 if value else 0
        
    # Integer type: accept only exact 0 or 1
    if isinstance(value, (int, np.integer)):
        if value == 1:
            return 1
        elif value == 0:
            return 0
        else:
            # any other integer (e.g. 2, -1) is not boolean-like
            return np.nan

    # Float type: accept only exact 0.0 or 1.0
    if isinstance(value, float):
        if value.is_integer() and value in (0.0, 1.0):
            return int(value)
        return np.nan
    
    # String: normalize and check tokens
    s = str(value).strip().lower()
    if s in _TRUE:  
        return 1
    if s in _FALSE: 
        return 0
    if s == "0": 
        return 0
    if s == "1": 
        return 1
    return np.nan

# ---------- Map Boolean-like columns ----------
def is_boolean_like(series: pd.Series) -> bool:
    """
    Return True if ALL non-null values in `series` map to 0 or 1. 
    """
    if series is None or series.size == 0:
        return False

    non_null = series.dropna()
    if non_null.empty:
        return False

    # Fast-path for boolean dtype
    if pd.api.types.is_bool_dtype(non_null):
        return True

    # Convert each value to {0,1} or NaN using helper
    mapped = non_null.map(_map_to_01)

    # Validate: No conversion produced NaN & all unique values are a subset of {0, 1}
    all_values_valid = mapped.notna().all()
    unique_values = set(mapped.dropna().unique())
    only_contains_01 = unique_values.issubset({0, 1})

    return all_values_valid and only_contains_01

# ---------- Categorize columns ----------
def categorize_columns(df: pd.DataFrame) -> Dict[str, List[str]]:
    """
    Rule-based categorization. 
    - If name rules fail: Detect Boolean-like, Numeric, Text, Other by dtype/content.
    - Returns only non-empty categories as dict: {category_name: [col1, col2, ...]} 
    """
    cats: Dict[str, List[str]] = {
        **{name: [] for name in CAT_RULES.keys()},
        "Numeric": [],
        "Text": [],
        "Other": [],
    }

    for col in df.columns:
        s = df[col]

        # 1) Name-based rules (first hit wins, except Boolean-like handled after)
        hit = False
        for cat, rules in CAT_RULES.items():
            if cat == "Boolean-like":  
                continue
            if _match_category(col, rules):
                cats[cat].append(col)
                hit = True
                break
        if hit:
            continue

        # 2) Content-based Boolean
        if is_boolean_like(s):
            cats["Boolean-like"].append(col)
            continue

        # 3) Fallback dtype buckets
        if pd.api.types.is_numeric_dtype(s):
            cats["Numeric"].append(col)
        elif pd.api.types.is_string_dtype(s):
            cats["Text"].append(col)
        else:
            cats["Other"].append(col)

    return {category: cols for category, cols in cats.items() if cols}
