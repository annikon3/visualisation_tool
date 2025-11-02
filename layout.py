from dash import dcc, html
from utils.ids import IDS

def build_layout():
    """Return the full Dash layout (no callbacks here)."""
    return html.Div([
        html.Header(html.H1("Forestry Data Visualisation"), className="app-header"),

        # Upload area
        dcc.Upload(
            id=IDS.UPLOAD,
            children=html.Button(
                "Upload File (.csv, .xls, .xlsx, .json/.geojson)",
                className="upload-btn"
            ),
            multiple=False,
            accept=".csv, .xls, .xlsx, .json, .geojson",
            className="upload",
            style={"display": "inline-block"}
        ),

        # Session stores: processed data + categorized columns + active columns
        dcc.Store(id=IDS.DATA, storage_type="session"),
        dcc.Store(id=IDS.META, storage_type="session"),
        dcc.Store(id=IDS.ACTIVE_COLS, storage_type="session"),
        dcc.Store(id=IDS.FILTERED_DATA, storage_type="session"),

        # A) Category browser (read-only list)
        dcc.Dropdown(id=IDS.CATEGORY, placeholder="Choose category", className="category-dropdown"),
        html.Div(id=IDS.COLUMNS_VIEW, className="columns-list"),

        # B) User picks columns to keep for all charts/filters
        html.H2("Choose columns for analysis"),
        dcc.Dropdown(
            id=IDS.KEEP_COLS, 
            multi=True, 
            placeholder="Choose columns for analysis", 
            className="column-picker"
        ),
        
        # C) Visualisation controls (vis filters + axes + time filter)
        html.H2("Choose filters"),
        html.Div([
            # Generic filter (column -> value)
            dcc.Dropdown(id=IDS.FILTER_COL, placeholder="Filter column"),
            dcc.Dropdown(id=IDS.FILTER_VAL, placeholder="Filter value"),

            # Time filtering (column -> multi-year values)
            dcc.Dropdown(id=IDS.TIME_COL,   placeholder="Time column"),
            dcc.Dropdown(id=IDS.YEAR_VALUES, multi=True, placeholder="Years (multi-select)"),
        ], className="vis-controls"),

        # D) Charts grid
        # per-chart controls together with each chart
        html.H2("Visualisations"),
        html.Div([
            html.Div([dcc.Graph(id=IDS.FIG_MAP, className="chart-plot", config={"responsive": True}),], className="chart-card map-card"),
            
            # --- Bar chart + its own local axis selectors ---
            html.Div([
                html.Div([
                    dcc.Dropdown(id=IDS.X_COL, placeholder="Bar X (categorical)"),
                    dcc.Dropdown(id=IDS.Y_COL, placeholder="Bar Y (numeric)"),
                ], className="chart-controls"),
                dcc.Graph(id=IDS.FIG_BAR, className="chart-plot", config={"responsive": True}),
            ], className="chart-card"),

            # --- Pie chart + its own local column selector ---
            html.Div([
                html.Div([
                    dcc.Dropdown(id=IDS.PIE_COL, placeholder="Pie column (categorical)"),
                ], className="chart-controls"),
                dcc.Graph(id=IDS.FIG_PIE, className="chart-plot"),
            ], className="chart-card"),
        ], className="charts-grid")
    ])
