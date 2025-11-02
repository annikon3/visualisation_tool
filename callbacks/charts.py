from dash import Dash, Input, Output, State, no_update
import plotly.express as px

from utils.ids import IDS
from utils.helpers import json_to_df
from services.figures import build_map, build_bar, build_pie

# ---------- Helper ----------
# Threshold: Over 10 columns on x-axis -> use wide card for chart
_WIDE_THRESHOLD = 10

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
        Output("bar_card", "className"),
        Input(IDS.FILTERED_DATA, "data"),
        Input(IDS.X_COL, "value"),
        Input(IDS.Y_COL, "value"),
        prevent_initial_call=True,
    )
    def _render_bar(filtered_json, x_col, y_col):
        empty = px.scatter()
        if not filtered_json:
            return empty, "chart-card"
        
        df = json_to_df(filtered_json)
        if df.empty:
            return empty, "chart-card"
        
        fig = build_bar(df, x_col, y_col)

        # Category count 
        def _n_cats(fig, df, x_col):
            """
            Prefer reading categories from the built figure.
            Fallback to df[x_col] only if x_col is valid.
            """
            try:
                # If there are traces with x-values, use the first (bar charts usually have one)
                if fig and getattr(fig, "data", None):
                    for tr in fig.data:
                        # try x first (vertical bars); if missing, try y (horizontal)
                        if getattr(tr, "x", None) is not None:
                            return len(tr.x)
                        if getattr(tr, "y", None) is not None:
                            return len(tr.y)
                # Fallback to df only when x_col looks valid
                if x_col and (x_col in df.columns):
                    return df[x_col].astype(str).nunique()
            except Exception:
                pass
            return 0  # unknown -> treat as no categories (not wide card)
        # ----------------------------------------

        n_cats = _n_cats(fig, df, x_col)
        class_name = "chart-card chart-card--wide" if n_cats > _WIDE_THRESHOLD else "chart-card"
        return fig, class_name


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
