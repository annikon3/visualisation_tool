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
        html.P(
            "Columns are automatically grouped based on their name or type (e.g. 'year' or numeric). "
            "These categories help understand which fields can be used for specific charts.", 
            className="help-text"
            ),
        html.Div(id=IDS.COLUMNS_VIEW, className="columns-list"),

        # B) User picks columns to keep for all charts/filters
        html.H2("Choose columns for analysis"),
        html.P(
            "Select one or more columns from your dataset to include in visualisations. "
            "Active columns will appear in filters and charts below.", 
            className="help-text"
            ),
        dcc.Dropdown(
            id=IDS.KEEP_COLS, 
            multi=True, 
            placeholder="Choose columns for analysis", 
            className="column-picker"
        ),
        
        # C) Visualisation controls (vis filters + axes + time filter)
        html.H2("Choose filters"),
        html.P(
                "Use the dropdowns below to filter data globally. "
                "Filters update all charts simultaneously.", 
                className="help-text"
            ),
        html.Div([
            # Generic filter (column -> value)
            dcc.Dropdown(id=IDS.FILTER_COL, placeholder="Choose a column to filter by..."),
            dcc.Dropdown(id=IDS.FILTER_VAL, placeholder="Choose a value to filter..."),

            # Time filtering (column -> multi-year values)
            dcc.Dropdown(id=IDS.TIME_COL,   placeholder="Time column"),
            dcc.Checklist(
                id=IDS.YEAR_VALUES,
                options=[],        # filled by menus callback
                value=[],          # default set by menus callback
                labelStyle={"display": "inline-block", "marginRight": "10px"},
                inputClassName="year-chip", 
                className="year-checklist"
            ),
        ], className="vis-controls"),

        # D) Charts grid
        # per-chart controls together with each chart
        html.H2("Visualisations"),
        html.Div([
            html.H3("Map Chart"), 
            html.Div(
                [dcc.Graph(id=IDS.FIG_MAP, className="chart-plot", config={"responsive": True})], 
                className="chart-card chart-card--wide", id="map_card"),
            
            # --- Bar chart ---
            html.Div([
                html.H3("Bar Chart"), 
                html.Div([
                    dcc.Dropdown(id=IDS.X_COL, placeholder="Bar X (categorical)"),
                    dcc.Dropdown(id=IDS.Y_COL, placeholder="Bar Y (numeric)"),
                ], className="chart-controls"),
                dcc.Graph(id=IDS.FIG_BAR, className="chart-plot", config={"responsive": True}),
                ],
                className="chart-card", id="bar_card"
            ),

            # --- Pie chart ---
            html.Div([
                html.H3("Pie Chart"), 
                html.Div([
                    dcc.Dropdown(id=IDS.PIE_COL, placeholder="Pie column (categorical)"),
                ], className="chart-controls"),
                dcc.Graph(id=IDS.FIG_PIE, className="chart-plot"),
            ], className="chart-card", id="pie_card"),

            # --- Histogram ---
            html.Div([
                html.H3("Histogram"), 
                html.Div([
                    dcc.Dropdown(id=IDS.HIST_COL, placeholder="Histogram (numeric)"),
                ], className="chart-controls"),
                dcc.Graph(id=IDS.FIG_HIST, className="chart-plot"),
            ], className="chart-card", id="hist_card"),

            # --- Box chart ---
            html.Div([
                html.H3("Box Chart"), 
                html.Div([
                    dcc.Dropdown(id=IDS.BOX_X, placeholder="Box: X (categorical)"),
                    dcc.Dropdown(id=IDS.BOX_Y, placeholder="Box: Y (numeric)"),
                ], className="chart-controls"),
                dcc.Graph(id=IDS.FIG_BOX, className="chart-plot"),
            ], className="chart-card", id="box_card"),

            # --- Line chart ---
            html.Div([
                html.H3("Line Chart"), 
                html.Div([
                    dcc.Dropdown(id=IDS.LINE_TIME, placeholder="Line: time column"),
                    dcc.Dropdown(id=IDS.LINE_Y,    placeholder="Line: Y (numeric)"),
                ], className="chart-controls"),
                dcc.Graph(id=IDS.FIG_LINE, className="chart-plot"),
            ], className="chart-card", id="line_card"),
        ], className="charts-grid")
    ])
