from dash import Dash, Input, Output, State, no_update
import plotly.express as px

from utils.ids import IDS
from utils.helpers import json_to_df
from services.figures import build_map, build_bar, build_pie, build_hist, build_box, build_line, build_scatter

# ---------- Helpers ----------
# Threshold: Over 10 columns on x-axis -> use wide card for chart
_WIDE_THRESHOLD = 10

# Toggle base class with "hidden" -> hide or show charts
def _with_visibility(base_class: str, show: bool) -> str:
    """Return base class + ' hidden' when show=False; keep base otherwise."""
    return f"{base_class} hidden" if not show else base_class


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
        Output("map_card", "className"),
        Input(IDS.FILTERED_DATA, "data"),
        Input(IDS.TIME_COL, "value"),
        Input(IDS.FILTER_COL, "value"),
        Input(IDS.SHOW_CHARTS, "value"),
        State(IDS.FIG_MAP, "figure"), 
        prevent_initial_call=True,
    )
    def _render_map(filtered_json, time_col, filter_col, visible, current_fig):
        empty = px.scatter()

        # Decide visibility first
        show = isinstance(visible, (list, tuple, set)) and ("map" in visible)
        base_class = "chart-card chart-card--wide"
        if not filtered_json:
            return empty, _with_visibility(base_class, show)

        df = json_to_df(filtered_json)
        if df.empty:
            return empty, _with_visibility(base_class, show)

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

        return new_fig, _with_visibility(base_class, show)
    

    # BAR: its own axis selectors + global filters 
    @app.callback(
        Output(IDS.FIG_BAR, "figure"),
        Output("bar_card", "className"),
        Input(IDS.FILTERED_DATA, "data"),
        Input(IDS.X_COL, "value"),
        Input(IDS.Y_COL, "value"),
        Input(IDS.SHOW_CHARTS, "value"),
        prevent_initial_call=True,
    )
    def _render_bar(filtered_json, x_col, y_col, visible):
        empty = px.scatter()      
        show = isinstance(visible, (list, tuple, set)) and ("bar" in visible)
        # When hidden, still compute figure cautiously (keeps sizing meta available),
        if not filtered_json or not x_col:
            return empty, _with_visibility("chart-card", show)

        df = json_to_df(filtered_json)
        if df.empty:
            return empty, _with_visibility("chart-card", show)

        fig = build_bar(df, x_col, y_col)

        # Read category count 
        def _read_n_cats(fig, df, x_col) -> int:
            """
            Prefer reading from figure.layout.meta['n_cats'] set by build_bar in figures.py.
            Fallback to traces (len(x) or len(y)), and lastly to df[x_col] if valid.
            """
            # 1) Preferred: figure meta
            try:
                meta = getattr(fig.layout, "meta", None)
                if isinstance(meta, (dict,)):
                    val = meta.get("n_cats", None)
                    if isinstance(val, (int,)) and val >= 0:
                        return val
            except Exception:
                pass

            # 2) Fallback: try traces
            try:
                if fig and getattr(fig, "data", None):
                    for tr in fig.data:
                        if getattr(tr, "x", None) is not None:
                            return len(tr.x)
                        if getattr(tr, "y", None) is not None:
                            return len(tr.y)
            except Exception:
                pass

            # 3) Fallback: df[x_col] if available 
            try:
                if x_col and (x_col in df.columns):
                    return df[x_col].astype(str).nunique()
            except Exception:
                pass

            # unknown -> treat as no categories (not wide card)
            return 0  
        # ----------------------------------------

        n_cats = _read_n_cats(fig, df, x_col)
        base_class = "chart-card chart-card--wide" if n_cats > _WIDE_THRESHOLD else "chart-card"
        return fig, _with_visibility(base_class, show)


    # PIE: its own column selector + global filters
    @app.callback(
        Output(IDS.FIG_PIE, "figure"),
        Output("pie_card", "className"),
        Input(IDS.FILTERED_DATA, "data"),
        Input(IDS.PIE_COL, "value"),
        Input(IDS.SHOW_CHARTS, "value"),
        prevent_initial_call=True,
    )
    def _render_pie(filtered_json, pie_col, visible):
        empty = px.scatter()
        show = isinstance(visible, (list, tuple, set)) and ("pie" in visible)
        base_class = "chart-card"

        # Hard skip: no computation when hidden (small optimization) 
        if not show:
            return empty, _with_visibility(base_class, False)

        if not filtered_json:
            return empty, _with_visibility(base_class, True)
        
        df = json_to_df(filtered_json)
        if df.empty:
            return empty, _with_visibility(base_class, True)
        
        fig = build_pie(df, pie_col)
        return fig, _with_visibility(base_class, True)
    
    
    # HISTOGRAM: its own column selector + global filters
    @app.callback(
        Output(IDS.FIG_HIST, "figure"),
        Output("hist_card", "className"),
        Input(IDS.FILTERED_DATA, "data"),
        Input(IDS.HIST_COL, "value"),
        Input(IDS.SHOW_CHARTS, "value"),
        prevent_initial_call=True,
    )
    def _render_hist(filtered_json, col, visible):
        empty = px.scatter()
        show = isinstance(visible, (list, tuple, set)) and ("hist" in visible)
        base_class = "chart-card"

        if not show:
            return empty, _with_visibility(base_class, False)

        if not filtered_json:
            return empty, _with_visibility(base_class, True)
        
        df = json_to_df(filtered_json)
        if df.empty:
            return empty, _with_visibility(base_class, True)

        fig = build_hist(df, col)
        return fig, _with_visibility(base_class, True)


    # BOX: its own column selector + global filters
    @app.callback(
        Output(IDS.FIG_BOX, "figure"),
        Output("box_card", "className"),
        Input(IDS.FILTERED_DATA, "data"),
        Input(IDS.BOX_X, "value"),
        Input(IDS.BOX_Y, "value"),
        Input(IDS.SHOW_CHARTS, "value"),
        prevent_initial_call=True,
    )
    def _render_box(filtered_json, x_col, y_col, visible):
        empty = px.scatter()
        show = isinstance(visible, (list, tuple, set)) and ("box" in visible)
        base_class = "chart-card"

        if not show:
            return empty, _with_visibility(base_class, False)

        if not filtered_json or not x_col or not y_col:
            return empty, _with_visibility(base_class, True)

        df = json_to_df(filtered_json)
        if df.empty:
            return empty, _with_visibility(base_class, True)

        fig = build_box(df, x_col, y_col)
        return fig, _with_visibility(base_class, True)

    
    # LINE: its own column selector + global filters
    @app.callback(
        Output(IDS.FIG_LINE, "figure"),
        Output("line_card", "className"),
        Input(IDS.FILTERED_DATA, "data"),
        Input(IDS.LINE_TIME, "value"),
        Input(IDS.LINE_Y, "value"),
        Input(IDS.SHOW_CHARTS, "value"),
        prevent_initial_call=True,
    )
    def _render_line(filtered_json, t_col, y_col, visible):
        empty = px.scatter()
        show = isinstance(visible, (list, tuple, set)) and ("line" in visible)
        base_class = "chart-card"

        if not show:
            return empty, _with_visibility(base_class, False)

        if not filtered_json or not t_col or not y_col:
            return empty, _with_visibility(base_class, True)

        df = json_to_df(filtered_json)
        if df.empty:
            return empty, _with_visibility(base_class, True)

        fig = build_line(df, t_col, y_col)
        return fig, _with_visibility(base_class, True)
    

    # SCATTER: its own column selector + global filters
    @app.callback(
        Output(IDS.FIG_SCATTER, "figure"),
        Output("scatter_card", "className"),
        Input(IDS.FILTERED_DATA, "data"),
        Input(IDS.SCATTER_X, "value"),
        Input(IDS.SCATTER_Y, "value"),
        Input(IDS.SCATTER_COLOR, "value"),
        Input(IDS.SCATTER_TREND, "value"),
        Input(IDS.SHOW_CHARTS, "value"),
        prevent_initial_call=True,
    )
    def _render_scatter(filtered_json, x_col, y_col, color_col, trend_val, visible):
        empty = px.scatter()
        show = isinstance(visible, (list, tuple, set)) and ("scatter" in visible)
        base_class = "chart-card"

        if not show:
            return empty, _with_visibility(base_class, False)

        if not filtered_json or not x_col or not y_col:
            return empty, _with_visibility(base_class, True)

        df = json_to_df(filtered_json)
        if df.empty:
            return empty, _with_visibility(base_class, True)
        
        trend_on = isinstance(trend_val, (list, tuple, set)) and ("ols" in trend_val)
        fig = build_scatter(df, x_col, y_col, color_col, trendline=trend_on)
        return fig, _with_visibility(base_class, True)
