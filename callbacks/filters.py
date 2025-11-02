from dash import Input, Output
from utils.ids import IDS
from utils.helpers import json_to_df
from services.figures import subset_to_active, apply_value_filter, apply_year_filter

def register(app):
    @app.callback(
        Output(IDS.FILTERED_DATA, "data"),
        Input(IDS.DATA, "data"),
        Input(IDS.ACTIVE_COLS, "data"),
        Input(IDS.FILTER_COL, "value"),
        Input(IDS.FILTER_VAL, "value"),
        Input(IDS.TIME_COL, "value"),
        Input(IDS.YEAR_VALUES, "value"),
        prevent_initial_call=True,
    )
    def build_filtered(data_json, active_cols, filter_col, filter_val, time_col, years):
        if not data_json or not active_cols:
            return None
        df = json_to_df(data_json)
        df = subset_to_active(df, active_cols, also_keep=[time_col, filter_col])
        df = apply_value_filter(df, filter_col, filter_val, all_token=IDS.ALL_SENTINEL)
        df = apply_year_filter(df, time_col, years)
        return df.to_json(orient="split", date_format="iso")
