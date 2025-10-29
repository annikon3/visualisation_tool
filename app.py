import json
import base64, io
from io import StringIO
import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html, Input, Output, State

from preprocessing.analysis_pipeline import preprocess_dataframe
from preprocessing.column_classifier import categorize_columns

# --- preselect & cap settings ---
MAX_PER_CAT = 4     # how many per category
MAX_KEEP    = 40    # total cap for selected columns
ALL = "__ALL__"     # sentinel value meaning "no filtering"
CATEGORY_ORDER = [  # priority when collecting from categories
    "Coordinates", "Time", "Species", "Region or area", "Site type", "Counts", "Lengths",
    "Numeric", "Text", "Other"
]

# TODO: Year filters / timeline separately 
# TODO: charts should move responsively if smaller screen
# TODO: Assign separate filters for each chart? OR allow to choose a visualisation (map/bar/pie/line chart etc.) Probably the first. 

app = Dash(__name__)

# ---------- APP LAYOUT ----------
app.layout = html.Div([
    html.Header(html.H1("Forestry Data Visualisation"), className="app-header"),
    dcc.Upload(
        id="upload",
        children=html.Button(
            "Upload File (.csv, .xls, .xlsx, .json/.geojson)",
            className="upload-btn"
        ),
        multiple=False,
        accept=".csv, .xls, .xlsx, .json, .geojson",
        className="upload-as-button",
        style={"display": "inline-block"}
    ),

    # Session stores: save processed data JSON & categorizecd columns
    dcc.Store(id="data", storage_type="session"),
    dcc.Store(id="meta", storage_type="session"),
    dcc.Store(id="active_cols", storage_type="session"), 

    # A) Category browser (read-only list)
    dcc.Dropdown(id="category", placeholder="Choose category", className="category-dropdown"),
    html.Div(id="columns-view", className="columns-list"),

    # B) User picks columns to keep for all charts/filters
    html.H2("Choose columns for analysis"),
    dcc.Dropdown(id="keep_cols", multi=True, placeholder="Choose columns for analysis", className="column-picker"),

    # C) Visualisation controls
    html.H2("Choose filters"),
    html.Div([
        # Filter: choose a column and then its value
        dcc.Dropdown(id="filter_col", placeholder="Filter column"),
        dcc.Dropdown(id="filter_val", placeholder="Filter value"),
        # Axes for bar chart + column for pie
        dcc.Dropdown(id="x_col", placeholder="Bar X (categorical)"),
        dcc.Dropdown(id="y_col", placeholder="Bar Y (numeric)"),
        dcc.Dropdown(id="pie_col", placeholder="Pie column (categorical)"),
    ], className="vis-controls"),

    # D) Charts grid
    html.H2("Visualisations"),
    html.Div([
        dcc.Graph(id="fig_map", className="chart"),
        dcc.Graph(id="fig_bar", className="chart"),
        dcc.Graph(id="fig_pie", className="chart"),
    ], className="charts-grid")
])

# ---------- Upload + preprocessing ----------
@app.callback(
    Output("data", "data"),
    Output("meta", "data"),
    Input("upload", "contents"),
    State("upload", "filename"),
    prevent_initial_call=True
)
def handle_upload(contents, filename):
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
    """Populate the category dropdown after column classification."""
    if not meta: 
        return [], None
    # Build dropdown options like:  "Time (3)", "Species (5)", etc.
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
    """Display a list of columns for the selected category."""
    if not meta or not selected_category: 
        return "No columns found"
    
    # Create a bulleted list of all columns under the chosen category
    columns = meta.get(selected_category, [])
    return html.Ul([html.Li(col) for col in columns])


# ---- Helper: collect unique column names from all categories ----
def _flatten_unique(meta: dict) -> list:
    """Return a flat list of unique column names from all category mappings."""
    seen = set()
    unique_columns = []

    for category_columns in meta.values():
        for column in category_columns:
            if column not in seen:
                unique_columns.append(column)
                seen.add(column)
    
    return unique_columns

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
    """
    if not meta or not data_json:
        return [], []
    df = pd.read_json(StringIO(data_json), orient="split")

    # Build all available column options
    all_columns = _flatten_unique(meta)
    options = [{"label": c, "value": c} for c in all_columns]

    # Initialize lists for tracking selections (no duplicates, cap from MAX_PER_CAT)
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
    Update the list of 'active' columns based on user's selections.

    This limits how many columns are carried forward to visualization
    and dropdown menus, to avoid performance issues with large datasets.
    """
    selected_cols = selected_cols or []
    return selected_cols[:MAX_KEEP]  # hard limit for downstream processing


# ---- C) Populate dropdown menus options (filter, bar, pie selectors) ----
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
    """
    Populate dropdown menus (filter, bar, pie selectors) 
    using only the currently active columns.

    - X & Pie menus suggest categorical (string) columns.
    - Y menu suggests numeric columns.
    - Filter menu lists all active columns.
    """
    if not active_cols or not data_json:
        return [], [], [], []

    df = pd.read_json(StringIO(data_json), orient="split")

    # Keep only valid active columns 
    cols = [c for c in active_cols if c in df.columns]

    # Split columns by type
    string_cols = [c for c in cols if df[c].dtype == "string"]
    numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]

    # Helper for dropdown formatting
    make_options = lambda lst: [{"label": c, "value": c} for c in lst]

    # Return menu options
    return (
        make_options(cols),                  # Filter column (all active)
        make_options(string_cols or cols),   # Bar X-axis (categorical preferred)
        make_options(numeric_cols or cols),  # Bar Y-axis (numeric preferred)
        make_options(string_cols or cols)    # Pie column (categorical preferred)
    )


# Populate filter values from selected column
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
    Populate the filter value dropdown based on the selected column.
    Adds an 'All' option that represents no filtering.
    """

    if not selected_col or not data_json or not active_cols:
        return [], None

    df = pd.read_json(StringIO(data_json), orient="split")

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
    prevent_initial_call=True
)
def render_figures(data_json, active_cols, filter_col, filter_val, x_col, y_col, pie_col):
    """
    Render map, bar, and pie figures from the current dataset and selections.

    - Only columns in `active_cols` are used (plus latitude/longitude if present).
    - An optional filter (column + value) is applied; "ALL" means no filtering.
    - Map draws points if latitude/longitude exist.
    - Bar: mean(Y) by X if numeric Y is provided; otherwise counts by X.
    - Pie: distribution of the selected categorical column.
    """
    # Safe fallback
    empty = px.scatter()
    if not data_json or not active_cols:
        return empty, empty, empty

    # Load DataFrame and keep only active columns (+ lat/lon if available) 
    df = pd.read_json(StringIO(data_json), orient="split")
    must_keep = {"latitude", "longitude"} if {"latitude", "longitude"}.issubset(df.columns) else set()
    keep_cols = [c for c in df.columns if c in (set(active_cols) | must_keep)]
    if not keep_cols:
        return empty, empty, empty
    df = df[keep_cols]

    # Optional filter (skip if "ALL")
    if filter_col and filter_col in df.columns and filter_val not in (None, ALL):
        # Compare as string to handle numbers/booleans uniformly
        df = df[df[filter_col].astype(str) == str(filter_val)]
    
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
