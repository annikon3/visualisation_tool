from dash import Dash, Input, Output
import plotly.express as px

from utils.ids import IDS
from utils.helpers import json_to_df
from services.figures import *

# ---------- Public API ----------
def register_charts_callbacks(app: Dash) -> None:
    """Register lightweight callbacks; all distinct callbacks are in services.figures."""

    # MAP: depends only on global filters
    @app.callback(
        Output(IDS.FIG_MAP, "figure"),
        Input(IDS.DATA, "data"),
        Input(IDS.ACTIVE_COLS, "data"),
        Input(IDS.FILTER_COL, "value"),
        Input(IDS.FILTER_VAL, "value"),
        Input(IDS.TIME_COL, "value"),
        Input(IDS.YEAR_VALUES, "value"),
        prevent_initial_call=True,
    )
    def _render_map(data_json, active_cols, filter_col, filter_val, time_col, year_values):
        empty = px.scatter()
        if not data_json or not active_cols:
            return empty

        df = json_to_df(data_json)

        # keep time_col for hover even if not in active list
        df = subset_to_active(df, active_cols, also_keep=[time_col, filter_col])
        if df.empty:
            return empty

        # global value filter
        df = apply_value_filter(df, filter_col, filter_val, all_token=IDS.ALL_SENTINEL)
        # global year filter
        df = apply_year_filter(df, time_col, year_values)
        map_color_col = filter_col if (filter_col in df.columns) else None
        return build_map(df, hover_col=time_col, color_col=map_color_col)
    

    # BAR: its own axes + global filters 
    @app.callback(
        Output(IDS.FIG_BAR, "figure"),
        Input(IDS.DATA, "data"),
        Input(IDS.ACTIVE_COLS, "data"),
        Input(IDS.FILTER_COL, "value"),
        Input(IDS.FILTER_VAL, "value"),
        Input(IDS.TIME_COL, "value"),
        Input(IDS.YEAR_VALUES, "value"),
        Input(IDS.X_COL, "value"),
        Input(IDS.Y_COL, "value"),
        prevent_initial_call=True,
    )
    def _render_bar(data_json, active_cols, filter_col, filter_val, time_col, year_values, x_col, y_col):
        empty = px.scatter()
        if not data_json or not active_cols:
            return empty

        df = json_to_df(data_json)
        df = subset_to_active(df, active_cols, also_keep=[time_col, x_col, y_col])
        if df.empty:
            return empty

        df = apply_value_filter(df, filter_col, filter_val, all_token=IDS.ALL_SENTINEL)
        df = apply_year_filter(df, time_col, year_values)
        return build_bar(df, x_col, y_col)
    
    
    # PIE: its own column + global filters
    @app.callback(
        Output(IDS.FIG_PIE, "figure"),
        Input(IDS.DATA, "data"),
        Input(IDS.ACTIVE_COLS, "data"),
        Input(IDS.FILTER_COL, "value"),
        Input(IDS.FILTER_VAL, "value"),
        Input(IDS.TIME_COL, "value"),
        Input(IDS.YEAR_VALUES, "value"),
        Input(IDS.PIE_COL, "value"),
        prevent_initial_call=True,
    )
    def _render_pie(data_json, active_cols, filter_col, filter_val, time_col, year_values, pie_col):
        empty = px.scatter()
        if not data_json or not active_cols:
            return empty

        df = json_to_df(data_json)
        df = subset_to_active(df, active_cols, also_keep=[time_col, pie_col])
        if df.empty:
            return empty

        df = apply_value_filter(df, filter_col, filter_val, all_token=IDS.ALL_SENTINEL)
        df = apply_year_filter(df, time_col, year_values)
        return build_pie(df, pie_col)

