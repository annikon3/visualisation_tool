from dash import Dash, Input, Output, State, no_update
import plotly.express as px

from utils.ids import IDS
from utils.helpers import json_to_df
from services.figures import build_map, build_bar, build_pie

# ---------- Public API ----------
def register_charts_callbacks(app: Dash) -> None:
    """
    Register lightweight callbacks; 
    all distinct callbacks are in services.figures; 
    all global filtering is done in Filters callback.
    """

    # MAP: depends only on global filters
    @app.callback(
        Output(IDS.FIG_MAP, "figure"),
        Input(IDS.FILTERED_DATA, "data"),
        Input(IDS.TIME_COL, "value"),
        Input(IDS.FILTER_COL, "value"),
        State(IDS.FIG_MAP, "figure"), 
        prevent_initial_call=True,
    )
    def _render_map(filtered_json, time_col, filter_col, current_fig):
        empty = px.scatter()
        if not filtered_json:
            return empty

        df = json_to_df(filtered_json)
        if df.empty:
            return empty

        map_color_col = filter_col if (filter_col in df.columns) else None
        new_fig = build_map(df, hover_col=time_col, color_col=map_color_col)
        
        # Preserve user viewport (center, zoom etc.) when switching filters
        try:
            if current_fig and "layout" in current_fig and "map" in current_fig["layout"]:
                old_map = current_fig["layout"]["map"]
                new_fig.update_layout(
                    map=dict(
                        center=old_map.get("center", None),
                        zoom=old_map.get("zoom", None),
                        bearing=old_map.get("bearing", None),
                        pitch=old_map.get("pitch", None),
                        style=new_fig.layout.map.style,
                        uirevision="map-viewport",
                    ),
                    uirevision="map-viewport",
                )
        except Exception:
            pass

        return new_fig
    

    # BAR: its own axis selectors + global filters 
    @app.callback(
        Output(IDS.FIG_BAR, "figure"),
        Input(IDS.FILTERED_DATA, "data"),
        Input(IDS.X_COL, "value"),
        Input(IDS.Y_COL, "value"),
        prevent_initial_call=True,
    )
    def _render_bar(filtered_json, x_col, y_col):
        empty = px.scatter()
        if not filtered_json:
            return empty
        df = json_to_df(filtered_json)
        if df.empty:
            return empty
        return build_bar(df, x_col, y_col)
        

    # PIE: its own column selector + global filters
    @app.callback(
        Output(IDS.FIG_PIE, "figure"),
        Input(IDS.FILTERED_DATA, "data"), 
        Input(IDS.PIE_COL, "value"),
        prevent_initial_call=True,
    )
    def _render_pie(filtered_json, pie_col):
        empty = px.scatter()
        if not filtered_json:
            return empty
        df = json_to_df(filtered_json)
        if df.empty:
            return empty        
        return build_pie(df, pie_col)
