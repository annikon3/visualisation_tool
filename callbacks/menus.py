# -------------------------------------------------------------------
# Single responsibility: all "menus & selectors" related callbacks:
#   - Category dropdown and category column list
#   - "Keep columns" init + syncing to active columns
#   - Chart selector dropdowns (filter/x/y/pie)
#   - Time column detection + year multi-select values
# -------------------------------------------------------------------

from __future__ import annotations
from io import StringIO
from typing import Dict, List

import pandas as pd
from dash import Input, Output, State, html

from utils.ids import IDS
from utils.helpers import json_to_df, make_options, typed_lists, extract_years


# --- Local config for menu behaviour ---
MAX_PER_CAT = 4                 # how many columns to preselect per category
MAX_KEEP    = 30                # total hard cap for selected (active) columns
CATEGORY_ORDER = [              # priority when collecting from categories
    "Coordinates", "Time", "Boolean-like", "Region or area", "Species", "Site type", "Counts", "Lengths",
    "Numeric", "Text", "Other"
]


# ---------- Internal helper ----------
def _flatten_unique(meta: Dict[str, List[str]]) -> List[str]:
    """Flatten category -> columns mapping into a list of unique column names."""
    seen, out = set(), []
    for cols in meta.values():
        for c in cols:
            if c not in seen:
                out.append(c)
                seen.add(c)
    return out


# ---------- Public API ----------

def register(app):
    """
    Register all "menus" callbacks on the given Dash app instance.
    """

    # --- A) Category dropdown: options + default value ---
    @app.callback(
        Output(IDS.CATEGORY, "options"),
        Output(IDS.CATEGORY, "value"),
        Input(IDS.META, "data"),
        prevent_initial_call=True,
    )
    def fill_categories(meta):
        """Populate category dropdown with counts, select the first by default."""
        if not meta:
            return [], None

        # Build dropdown options with 'Name (count)' like: "Time (3)", etc.
        options = [
            {"label": f"{cat} ({len(cols)})", "value": cat}
            for cat, cols in meta.items()
        ]
        # Default: select the first category (if any)
        default_value = options[0]["value"] if options else None
        return options, default_value

    # --- A) Category columns list (read-only view) ---
    @app.callback(
        Output(IDS.COLUMNS_VIEW, "children"),
        Input(IDS.META, "data"),
        Input(IDS.CATEGORY, "value"),
        prevent_initial_call=True,
    )
    def show_columns(meta, selected_category):
        """Render a bulleted list of columns for the selected category."""
        if not meta or not selected_category:
            return "No columns found"
        cols = meta.get(selected_category, [])
        return html.Ul([html.Li(c) for c in cols])

    # --- B) Keep columns: initial options + auto-preselect (coords + top per category) ---
    @app.callback(
        Output(IDS.KEEP_COLS, "options"),
        Output(IDS.KEEP_COLS, "value"),
        Input(IDS.META, "data"),
        Input(IDS.DATA, "data"),
        prevent_initial_call=True,
    )
    def init_keep_cols(meta, data_json):
        """
        Build "keep columns" options and preselect a limited subset to avoid flooding the UI.
        - Always keep latitude/longitude if present
        - Take up to MAX_PER_CAT from categories in CATEGORY_ORDER
        - Fill up to MAX_KEEP with rest
        """
        if not meta or not data_json:
            return [], []

        df = json_to_df(data_json)

        # Available options (all unique meta columns)
        all_cols = _flatten_unique(meta)
        options = make_options(all_cols)

        picked = []   # columns to preselect
        seen = set()  # prevent duplicates

        # 1) Always keep coords if present
        if {"latitude", "longitude"}.issubset(df.columns):
            for c in ("latitude", "longitude"):
                if c not in seen:
                    picked.append(c)
                    seen.add(c)

        # 2) Take up to MAX_PER_CAT per category by priority
        for cat in CATEGORY_ORDER:
            for c in meta.get(cat, [])[:MAX_PER_CAT]:
                if c not in seen:
                    picked.append(c)
                    seen.add(c)
                if len(picked) >= MAX_KEEP:
                    break
            if len(picked) >= MAX_KEEP:
                break

        # 3) Fill remaining slots
        if len(picked) < MAX_KEEP:
            for cols in meta.values():
                for c in cols:
                    if c not in seen:
                        picked.append(c)
                        seen.add(c)
                    if len(picked) >= MAX_KEEP:
                        break
                if len(picked) >= MAX_KEEP:
                    break

        return options, picked

    # --- B) Keep columns -> Active columns (cap for downstream) ---
    @app.callback(
        Output(IDS.ACTIVE_COLS, "data"),
        Input(IDS.KEEP_COLS, "value"),
        prevent_initial_call=True,
    )
    def update_active_cols(selected):
        """Sync user's kept columns to a capped list used by all downstream menus/plots."""
        selected = selected or []
        return selected[:MAX_KEEP]

    # --- C) Fill selectors (filter/x/y/pie etc.) from active columns ---
    @app.callback(
        Output(IDS.FILTER_COL, "options"),
        Output(IDS.X_COL, "options"),
        Output(IDS.Y_COL, "options"),
        Output(IDS.PIE_COL, "options"),
        Output(IDS.HIST_COL,  "options"),
        Output(IDS.BOX_X,     "options"),
        Output(IDS.BOX_Y,     "options"),
        Output(IDS.LINE_Y,    "options"),
        Output(IDS.SCATTER_X,   "options"),
        Output(IDS.SCATTER_Y,   "options"),
        Output(IDS.SCATTER_COLOR, "options"),
        Input(IDS.ACTIVE_COLS, "data"),
        Input(IDS.DATA, "data"),
        prevent_initial_call=True,
    )
    def fill_selectors(active_cols, data_json):
        """
        Populate chart selector dropdowns using currently active columns.
        - X & Pie & Box_X:                   prefer string columns
        - Y / Hist / Box_Y / Line_Y: prefer numeric columns
        - Filter:                    all active columns
        """
        if not active_cols or not data_json:
            empty = []
            return (empty, empty, empty, # filter, x, y
                    empty, empty,        # pie, hist
                    empty, empty,        # box_x, box_y
                    empty,               # line_y
                    empty, empty, empty) # scatter: x, y, color
        
        df = json_to_df(data_json)

        # Keep only valid active columns 
        cols = [c for c in active_cols if c in df.columns]

        # Split columns by type
        str_cols, num_cols = typed_lists(df, cols)

        # Return menu options
        return (
            make_options(cols),               # Filter          (all active)
            make_options(str_cols or cols),   # X-axis          (categorical preferred)
            make_options(num_cols or cols),   # Y-axis          (numeric preferred)
            make_options(str_cols or cols),   # Pie             (categorical preferred)
            make_options(num_cols or cols),   # Hist            (numeric preferred)
            make_options(str_cols or cols),   # Box_X           (categorical preferred)
            make_options(num_cols or cols),   # Box_Y           (numeric preferred)
            make_options(num_cols or cols),   # Line_Y          (numeric preferred)
            make_options(num_cols or cols),   # Scatter X       (numeric preferred)
            make_options(num_cols or cols),   # Scatter Y       (numeric preferred)
            make_options(str_cols or cols),   # Scatter color   (categorical preferred)
        )

    # --- C) Filter values (with "All" sentinel) ---
    @app.callback(
        Output(IDS.FILTER_VAL, "options"),
        Output(IDS.FILTER_VAL, "value"),
        Input(IDS.FILTER_COL, "value"),
        Input(IDS.DATA, "data"),
        State(IDS.ACTIVE_COLS, "data"),
        prevent_initial_call=True,
    )
    def fill_filter_values(selected_col, data_json, active_cols):
        """
        Populate filter values for the selected column:
        - Cast to string for stable display
        - 'All' is the default option and represents no filtering.
        """
        if not selected_col or not data_json or not active_cols:
            return [], None

        df = json_to_df(data_json)

        # Ensure the column exists and is active 
        if selected_col not in active_cols or selected_col not in df.columns:
            return [], None

        # Collect unique non-null values as strings (for stable display)
        vals = (
            df[selected_col]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )
        vals.sort()

        # Add "All" option to allow showing all values 
        opts = [{"label": "All", "value": IDS.ALL_SENTINEL}] + [
            {"label": v, "value": v} for v in vals
        ]

        return opts, IDS.ALL_SENTINEL


    # --- Time column suggestions from "Time" category, limited to active cols ---
    @app.callback(
        Output(IDS.TIME_COL, "options"),
        Output(IDS.TIME_COL, "value"),
        Input(IDS.META, "data"),
        Input(IDS.ACTIVE_COLS, "data"),
        Input(IDS.DATA, "data"),
        prevent_initial_call=True,
    )
    def fill_time_column_options(meta, active_cols, data_json):
        """Suggest time columns from 'Time' category, limited to active (selected) columns."""
        if not meta or not active_cols or not data_json:
            return [], None

        df = json_to_df(data_json)

        # Keep only active + present in df
        candidates = [c for c in meta.get("Time", []) if c in active_cols and c in df.columns]

        # Prefer datetime64 -> integer -> string; fall back to all time candidates
        def rank(c):
            s = df[c]
            if pd.api.types.is_datetime64_any_dtype(s): 
                return 0
            if pd.api.types.is_integer_dtype(s):       
                return 1
            if pd.api.types.is_string_dtype(s):        
                return 2
            return 3

        candidates.sort(key=rank)
        options = make_options(candidates)
        default = candidates[0] if candidates else None
        return options, default

    # --- List distinct years or times for multi-select that drives all charts ---
    @app.callback(
        Output(IDS.YEAR_VALUES, "options"),
        Output(IDS.YEAR_VALUES, "value"),
        Input(IDS.TIME_COL, "value"),
        Input(IDS.DATA, "data"),
        prevent_initial_call=True,
    )
    def fill_year_values(time_col, data_json):
        """
        Given the chosen time column, populate distinct years/times for multi-select:
        - If datetime -> use .dt.year
        - Else try numeric coercion to int
        - Default: select all available years/times
        """
        if not time_col or not data_json:
            return [], []

        df = json_to_df(data_json)
        if time_col not in df.columns:
            return [], []
        
        # returns Int64 series of years
        years = extract_years(df, time_col)  
        if years.empty:
            return [], []
        
        uniq = sorted(int(y) for y in years.dropna().unique().tolist())
        opts = [{"label": "All years", "value": IDS.ALL_SENTINEL}] + [
        {"label": str(y), "value": int(y)} for y in uniq]

        # Default: select all years
        return opts, [IDS.ALL_SENTINEL]
    
    # --- Sync TIME_COL -> LINE_TIME (options + default value) ---
    @app.callback(
        Output(IDS.LINE_TIME, "options"),
        Output(IDS.LINE_TIME, "value"),
        Input(IDS.TIME_COL, "options"),
        Input(IDS.TIME_COL, "value"),
        prevent_initial_call=True,
    )
    def sync_line_time_selector(time_opts, time_val):
        """
        Reuse the global Time options for the line chart's time selector.
        Keeps a single source of truth for time-like columns.
        """
        return (time_opts or []), (time_val if time_opts else None)
