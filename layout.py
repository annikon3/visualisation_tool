from dash import dcc, html

def build_layout():
    """Return the full Dash layout (no callbacks here)."""
    return html.Div([
        html.Header(html.H1("Forestry Data Visualisation"), className="app-header"),

        # Upload area
        dcc.Upload(
            id="upload",
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
        dcc.Store(id="data", storage_type="session"),
        dcc.Store(id="meta", storage_type="session"),
        dcc.Store(id="active_cols", storage_type="session"),

        # A) Category browser (read-only list)
        dcc.Dropdown(id="category", placeholder="Choose category", className="category-dropdown"),
        html.Div(id="columns-view", className="columns-list"),

        # B) User picks columns to keep for all charts/filters
        html.H2("Choose columns for analysis"),
        dcc.Dropdown(
            id="keep_cols", 
            multi=True, 
            placeholder="Choose columns for analysis", 
            className="column-picker"
        ),
        
        # C) Visualisation controls (vis filters + axes + time filter)
        html.H2("Choose filters"),
        html.Div([
            # Generic filter (column -> value)
            dcc.Dropdown(id="filter_col", placeholder="Filter column"),
            dcc.Dropdown(id="filter_val", placeholder="Filter value"),

            # Time filtering (column -> multi-year values)
            dcc.Dropdown(id="time_col",   placeholder="Time column"),
            dcc.Dropdown(id="year_values", multi=True, placeholder="Years (multi-select)"),

            # Axes for bar + column for pie
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
