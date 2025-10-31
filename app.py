import base64, io
from io import StringIO
import pandas as pd
import plotly.express as px
from dash import Dash, html, Input, Output, State

from layout import build_layout
from utils.helpers import json_to_df, flatten_unique, make_options, typed_lists, extract_years

from services.preprocess import preprocess_dataframe
from services.classify import categorize_columns


# ---------- Settings for preselect & cap ----------
MAX_PER_CAT = 4     # how many columns per category to preselect
MAX_KEEP    = 40    # total cap for selected (active) columns
ALL = "__ALL__"     # sentinel value meaning no filtering
CATEGORY_ORDER = [  # priority when collecting from categories
    "Coordinates", "Time", "Boolean", "Region or area", "Species", "Site type", "Counts", "Lengths",
    "Numeric", "Text", "Other"
]

# TODO: Time filters as always visible multi-selects or checkboxes that changes choice for all charts at once. Add a "all" option. 
# TODO: Different color dots for generic filter applied to map. 
# TODO: Move Bar axes filters to sit with bar chart, pie column with pie chart. Keep year choices and common "Filter column" under "Choose filters" text. 
# TODO: Add multiselection ticks or boxes for charts opened (don't show all charts by default). 
# TODO: Add description or guidelines to categorized columns (describe what the list is)
# TODO: Add description: what "Choose columns for analysis" is and what it does. 

# TODO: Add descriptions to filters. 
# TODO: When selecting columns for analysis, if user types a column name and it is already 'active', give feedback e.g. "already selected". 

# Create app; enabling suppress_callback_exceptions helps 
# if parts of the layout are loaded dynamically or replaced later.
app = Dash(__name__, suppress_callback_exceptions=True)

# ---------- APP LAYOUT ----------
app.layout = build_layout() 

# ---------- Upload + preprocessing ----------
@app.callback(
    Output("data", "data"),
    Output("meta", "data"),
    Input("upload", "contents"),
    State("upload", "filename"),
    prevent_initial_call=True
)
def handle_upload(contents, filename):
    """Read uploaded file, preprocess it, categorize columns and store JSON/meta."""
    if not contents:
        return None, None
    try:
        decoded = base64.b64decode(contents.split(",")[1])
        if filename and filename.lower().endswith((".xls", ".xlsx")):
            df = pd.read_excel(
                io.BytesIO(decoded),
                na_values=["", " ", "-", "NA", "N/A", "nan", "NaN"]
            )
        elif filename and filename.lower().endswith((".geojson", ".json")):
            df = pd.read_json(io.BytesIO(decoded))
        else:
            df = pd.read_csv(io.BytesIO(decoded))

        # Preprocess and categorize the DataFrame
        processed_df = preprocess_dataframe(df).copy()
        meta = categorize_columns(processed_df)
        return processed_df.to_json(orient="split", date_format="iso"), meta
    except Exception as e:
        print(f"Failed to read uploaded file: {e}")
        return None, None
    
# ---------- Category menu + list ----------      

# ---- A) Category list ----  
@app.callback(
    Output("category", "options"),
    Output("category", "value"),
    Input("meta", "data"),
    prevent_initial_call=True
)
def fill_categories(meta):
    """Populate category dropdown after column classification."""
    if not meta: 
        return [], None
    
    # Build dropdown options with 'Name (count)' like:  "Time (3)", etc.
    options = [
        {"label": f"{category} ({len(columns)})", "value": category}
        for category, columns in meta.items()
    ]

    # Default: select the first category (if any)
    default_value = options[0]["value"] if options else None
    return options, default_value


@app.callback(
    Output("columns-view", "children"),
    Input("meta", "data"),
    Input("category", "value"),
    prevent_initial_call=True
)
def show_columns(meta, selected_category):
    """Display a bulleted list of columns for the selected category."""
    if not meta or not selected_category: 
        return "No columns found"
    columns = meta.get(selected_category, [])
    return html.Ul([html.Li(col) for col in columns])


# ---- B) Column selection dropdown ----
@app.callback(
    Output("keep_cols", "options"),
    Output("keep_cols", "value"),
    Input("meta", "data"),
    Input("data", "data"),
    prevent_initial_call=True
)
def init_keep_cols(meta, data_json):
    """
    Initialize the column selection dropdown:
    - Build all available column options.
    - Preselect a subset (e.g. coordinates + first N per category).
    - Take up to MAX_PER_CAT from CATEGORY_ORDER, then fill up to MAX_KEEP.
    """
    if not meta or not data_json:
        return [], []
    df = json_to_df(data_json) 

    # Build all available column options
    all_cols = flatten_unique(meta)
    options = make_options(all_cols)

    # Initialize lists for tracking selections
    picked = []   # columns to preselect
    seen = set()  # prevent duplicates

    # If coordinates present, always keep them
    if {"latitude", "longitude"}.issubset(df.columns):
        for c in ["latitude", "longitude"]:
            if c not in seen:
                picked.append(c)
                seen.add(c)

    # Pick top columns per category (by priority order)
    for cat in CATEGORY_ORDER:
        for col in meta.get(cat, [])[:MAX_PER_CAT]:
            if col not in seen:
                picked.append(col)
                seen.add(col)
            if len(picked) >= MAX_KEEP:
                break
        if len(picked) >= MAX_KEEP:
            break

    # If still below limit, fill remaining slots with other columns
    if len(picked) < MAX_KEEP:
        for columns in meta.values():
            for col in columns:
                if col not in seen:
                    picked.append(col)
                    seen.add(col)
                if len(picked) >= MAX_KEEP:
                    break
            if len(picked) >= MAX_KEEP:
                break

    # Return all dropdown options and preselected values
    return options, picked


@app.callback(
    Output("active_cols", "data"),
    Input("keep_cols", "value"),
    prevent_initial_call=True
)
def update_active_cols(selected_cols):
    """
    Store a capped list of active columns based on user's selections and used by all selectors/plots.
    This limits how many columns are carried forward to visualization
    and dropdown menus, to avoid performance issues with large datasets.
    """
    selected_cols = selected_cols or []
    return selected_cols[:MAX_KEEP]


# ---- C) Populate dropdown menus options = selectors for filters, axes for bar, pie ----
@app.callback(
    Output("filter_col","options"),
    Output("x_col","options"),
    Output("y_col","options"),
    Output("pie_col","options"),
    Input("active_cols","data"),
    Input("data","data"),
    prevent_initial_call=True
)
def fill_selectors(active_cols, data_json):
    """Populate dropdown menus (filter, bar, pie selectors). 
    - Offer only active columns. 
    - Prefer strings (categoricals) for X/Pie and numerics for Y.
    """
    if not active_cols or not data_json:
        return [], [], [], []
    df = json_to_df(data_json)

    # Keep only valid active columns 
    cols = [c for c in active_cols if c in df.columns]

    # Split columns by type
    str_cols, num_cols = typed_lists(df, cols)

    # Return menu options
    return (
        make_options(cols),               # Filter column (all active)
        make_options(str_cols or cols),   # Bar X-axis (categorical preferred)
        make_options(num_cols or cols),   # Bar Y-axis (numeric preferred)
        make_options(str_cols or cols)    # Pie column (categorical preferred)
    )


# ---------- Filter value dropdown ----------
@app.callback(
    Output("filter_val", "options"),
    Output("filter_val", "value"),
    Input("filter_col", "value"),
    Input("data", "data"),
    State("active_cols","data"),
    prevent_initial_call=True
)
def fill_filter_values(selected_col, data_json, active_cols):
    """
    Populate filter values dropdown based on the selected column.
    'All' option represents no filtering.
    """
    if not selected_col or not data_json or not active_cols:
        return [], None
    df = json_to_df(data_json)

    # Ensure the column exists and is active 
    if selected_col not in active_cols or selected_col not in df:
        return [], None

    # Collect unique non-null values as strings (for stable display)
    unique_values = (
        df[selected_col]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )
    unique_values.sort()

    # Add "All" option to allow showing all values 
    options = [{"label": "All", "value": ALL}] + [
        {"label": v, "value": v} for v in unique_values
    ]

    # Default selection is "All" 
    return options, ALL


# ---------- Time column (pick a single time-like column) ----------
@app.callback(
    Output("time_col", "options"),
    Output("time_col", "value"),
    Input("meta", "data"),
    Input("active_cols", "data"),
    Input("data", "data"),
    prevent_initial_call=True
)
def fill_time_column_options(meta, active_cols, data_json):
    """Suggest time columns from 'Time' category, limited to active columns."""
    if not meta or not active_cols or not data_json:
        return [], None

    df = json_to_df(data_json)
    
    # Pick candidates from Time category that exist in df and are active
    time_candidates = [c for c in meta.get("Time", []) if c in active_cols and c in df.columns]

    # Prefer datetime/int/string (in that order); fall back to all time candidates
    def rank(c):
        s = df[c]
        if pd.api.types.is_datetime64_any_dtype(s): 
            return 0
        if pd.api.types.is_integer_dtype(s):       
            return 1
        if pd.api.types.is_string_dtype(s):        
            return 2
        return 3
    time_candidates.sort(key=rank)

    options = make_options(time_candidates)
    default = time_candidates[0] if time_candidates else None
    return options, default

# ---------- Year multi-select, driven by chosen time_col ----------
@app.callback(
    Output("year_values", "options"),
    Output("year_values", "value"),
    Input("time_col", "value"),
    Input("data", "data"),
    prevent_initial_call=True
)
def fill_year_values(time_col, data_json):
    """Populate the multi-select with distinct years from the chosen time column."""
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
    # Integer values are fine; labels are strings for UI
    opts = [{"label": str(y), "value": int(y)} for y in uniq]

    # Default: select all years
    return opts, uniq


# ---------- Visualisations: map + bar + pie ----------
@app.callback(
    Output("fig_map", "figure"),
    Output("fig_bar", "figure"),
    Output("fig_pie", "figure"),
    Input("data", "data"),
    Input("active_cols","data"),
    Input("filter_col", "value"),
    Input("filter_val", "value"),
    Input("x_col", "value"),
    Input("y_col", "value"),
    Input("pie_col", "value"),
    Input("time_col", "value"),
    Input("year_values", "value"),
    prevent_initial_call=True
)
def render_figures(data_json, active_cols, filter_col, filter_val, x_col, y_col, pie_col, time_col, year_values):
    """
    Render map, bar, and pie figures from the current dataset and selections.
    - Only columns in `active_cols` are used (plus latitude/longitude if present).
    - Apply (optional) generic filter (column + value), "ALL" means no filtering.
    - Apply (optional) year multi-select.
    - Map draws points if latitude/longitude exist.
    - Bar: mean(Y) by X if numeric Y is provided; else counts by X.
    - Pie: distribution of selected categorical column.
    """
    # Safe fallback
    empty = px.scatter()
    if not data_json or not active_cols:
        return empty, empty, empty
    
    df = json_to_df(data_json)

    # Keep only active columns (+ lat/lon if available) 
    must_keep = {"latitude", "longitude"} if {"latitude", "longitude"}.issubset(df.columns) else set()
    keep_cols = [c for c in df.columns if c in set(active_cols).union(must_keep)]
    if not keep_cols:
        return empty, empty, empty
    df = df[keep_cols]

    # Optional generic filter (skip if "ALL")
    if filter_col and filter_col in df.columns and filter_val not in (None, ALL):
        # Compare as string to handle numbers/booleans uniformly
        df = df[df[filter_col].astype(str) == str(filter_val)]

    # Optional year multi-select filter
    if time_col and time_col in df.columns and year_values:
        years = extract_years(df, time_col)
        df = df.loc[years.isin(set(year_values)).fillna(False)]
       
    # --- MAP: requires latitude/longitude ---
    fig_map = empty
    if {"latitude", "longitude"}.issubset(df.columns):
        geo = df.dropna(subset=["latitude", "longitude"])
        if not geo.empty:
            fig_map = px.scatter_map(
                geo,
                lat="latitude",
                lon="longitude",
                hover_name=(x_col if x_col in geo.columns else None),
                zoom=4,
                height=500,
            ).update_layout(
                mapbox_style="open-street-map",
                mapbox_accesstoken=None,
                margin=dict(l=0, r=0, t=0, b=0),
            )

    # ---------------- BAR ----------------
    if x_col in df.columns and y_col in df.columns and pd.api.types.is_numeric_dtype(df[y_col]):
        # Mean of Y by X, if both selected and valid
        grouped = df.groupby(x_col, dropna=False, observed=True)[y_col].mean(numeric_only=True).reset_index()
        fig_bar = px.bar(grouped, x=x_col, y=y_col)
    elif x_col in df.columns:
        # Counts by X
        counts = df[x_col].value_counts(dropna=False).reset_index()
        counts.columns = [x_col, "count"]
        fig_bar = px.bar(counts, x=x_col, y="count")
    else:
        fig_bar = empty

    # ---------------- PIE ----------------
    # distribution of selected categorical
    if pie_col in df.columns:
        pie_counts = df[pie_col].value_counts(dropna=False).reset_index()
        pie_counts.columns = [pie_col, "count"]
        fig_pie = px.pie(pie_counts, names=pie_col, values="count", hole=0.3)
    else:
        fig_pie = empty

    return fig_map, fig_bar, fig_pie

# ---------- RUN APP ----------
if __name__ == "__main__":
    app.run(debug=True)
