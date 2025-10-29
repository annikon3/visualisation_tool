import pandas as pd
from typing import Dict, List

# Rule-based categories - write keywords in lowercase as they are compare in lowercase.
CAT_RULES: Dict[str, Dict[str, List[str]]] = {
    "Time": {
        "contains_any": ["date", "time", "aika", "päivä", "kuukausi", "viikko", "vmi", "vuosi", "timestamp", "datetime", "created", "modified"],
        "whole_word": ["pvm", "pp", "dd", "kk", "mm", "yyyy", "vvvv", "vko"]
    },
    "Coordinates": {
        "contains_any": ["lat", "latitude", "lon", "long", "lng", "longitude", "koord", "coord", "x_", "y_"],
        "whole_word": ["x", "y"]
    },
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
        "contains_any": ["count", "number", "quantity", "määrä", "lukumäärä", "no", "lkm", "kpl", "qty"],
        "whole_word": []
    },
    "Lengths": {
        "contains_any": ["length", "pituus", "height", "korkeus", "diameter", "läpimitta"],
        "whole_word": []
    },
}

def match_category(colname: str, rules: Dict[str, List[str]]) -> bool:
    """Return True if column name matches rule (substring or exact match), case-insensitive."""
    name = str(colname).strip().lower()
    # 1) substring
    for w in rules.get("contains_any", []):
        if w.lower() in name:
            return True
    # 2) exact match
    for w in rules.get("whole_word", []):
        if name == w.lower():
            return True
    return False

def categorize_columns(df: pd.DataFrame) -> Dict[str, List[str]]:
    """
    Rule-based categorization. If no rule matches, fallback to dtype buckets:
    Numeric / Text / Other. 
    Returns only non-empty categories.
    """
    cats: Dict[str, List[str]] = {k: [] for k in list(CAT_RULES.keys()) + ["Numeric", "Text", "Other"]}

    for col in df.columns:
        # first match matters
        for category, rules in CAT_RULES.items():
            if match_category(col, rules):
                cats[category].append(col)
                break
        else:
            # fallback: dtypes
            s = df[col]
            if pd.api.types.is_numeric_dtype(s):
                cats["Numeric"].append(col)
            elif pd.api.types.is_string_dtype(s):
                cats["Text"].append(col)
            else:
                cats["Other"].append(col)

    return {k: v for k, v in cats.items() if v}