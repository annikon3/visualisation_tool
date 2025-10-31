from __future__ import annotations

from typing import Iterable, List, Optional
import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output

from utils.ids import IDS
from utils.helpers import json_to_df, extract_years


# ---------- Internal helpers ----------

def _subset_to_active(df: pd.DataFrame, active_cols: Iterable[str]) -> pd.DataFrame:
    """
    Keep only user-approved columns + lat/lon (if present).
    This reduces the size of frames flowing through callbacks.
    """
    active = set(active_cols or [])
    must_keep = {"latitude", "longitude"} if {"latitude", "longitude"}.issubset(df.columns) else set()
    keep = [c for c in df.columns if (c in active) or (c in must_keep)]
    if not keep: 
        return df.iloc[0:0]  # empty frame if nothing to keep
    return df[keep]


def _apply_value_filter(df: pd.DataFrame, col: Optional[str], val: Optional[str], all_token: Optional[str] = None,) -> pd.DataFrame:
    """Apply equality filter unless value equals the provided all_token."""
    if not col or val is None or col not in df.columns:
        return df
    if all_token is not None and val == all_token:
        return df
    # Compare as string to handle numbers/booleans uniformly
    return df[df[col].astype(str) == str(val)]


def _apply_year_filter(df: pd.DataFrame, time_col: Optional[str], years: Optional[List[int]]) -> pd.DataFrame:
    """
    Filter rows to the given list of years using helpers.extract_years().
    Keeps only rows where the extracted year is in the provided list.
    """
    if not time_col or time_col not in df.columns or not years:
        return df
    
    # Normalize single int -> list[int]
    if not isinstance(years, list):
        years = [years]

    year_series = extract_years(df[time_col])
    mask = year_series.isin(years)
    return df.loc[mask.fillna(False)]


# --- MAP: requires latitude/longitude ---
def _build_map(df: pd.DataFrame, hover_col: Optional[str]):
    """Render a scatter map if latitude/longitude exist; else return an empty figure."""
    if not {"latitude", "longitude"}.issubset(df.columns):
        return px.scatter()

    geo = df.dropna(subset=["latitude", "longitude"])
    if geo.empty:
        return px.scatter()

    fig = px.scatter_map(
        geo,
        lat="latitude",
        lon="longitude",
        hover_name=hover_col if (hover_col in geo.columns) else None,
        zoom=4,
        height=500,
    )
    return fig.update_layout(
        mapbox_style="open-street-map",
        mapbox_accesstoken=None,
        margin=dict(l=0, r=0, t=0, b=0),
    )


# ---------------- BAR ----------------
def _build_bar(df: pd.DataFrame, x_col: Optional[str], y_col: Optional[str]):
    """
    Bar chart:
    - If x and numeric y: show mean(y) by x
    - Else if x only: show counts by x
    - Else: empty figure
    """
    if x_col in df.columns and y_col in df.columns and pd.api.types.is_numeric_dtype(df[y_col]):
        grouped = df.groupby(x_col, dropna=False, observed=True)[y_col].mean(numeric_only=True).reset_index()
        return px.bar(grouped, x=x_col, y=y_col)  

    if x_col in df.columns:
        counts = df[x_col].value_counts(dropna=False).reset_index()
        counts.columns = [x_col, "count"]
        return px.bar(counts, x=x_col, y="count")

    return px.scatter()


# ---------------- PIE ----------------
def _build_pie(df: pd.DataFrame, pie_col: Optional[str]):
    """Pie chart: distribution of a categorical column; else empty figure."""
    if pie_col in df.columns:
        pie_counts = df[pie_col].value_counts(dropna=False).reset_index()
        pie_counts.columns = [pie_col, "count"]
        return px.pie(pie_counts, names=pie_col, values="count", hole=0.3)

    return px.scatter()


# ---------- Public API ----------
def register_charts_callbacks(app: Dash, all_sentinel: str) -> None:
    """
    Wire up the single 'render_figures' callback that drives all three charts.
    `all_sentinel` is the special value meaning "no value filter" (e.g. '__ALL__').
    """
    @app.callback(
        Output(IDS.FIG_MAP, "figure"),
        Output(IDS.FIG_BAR, "figure"),
        Output(IDS.FIG_PIE, "figure"),
        Input(IDS.DATA, "data"),
        Input(IDS.ACTIVE_COLS, "data"),
        Input(IDS.FILTER_COL, "value"),
        Input(IDS.FILTER_VAL, "value"),
        Input(IDS.X_COL, "value"),
        Input(IDS.Y_COL, "value"),
        Input(IDS.PIE_COL, "value"),
        Input(IDS.TIME_COL, "value"),
        Input(IDS.YEAR_VALUES, "value"),
        prevent_initial_call=True,
    )
    def render_figures(data_json, active_cols, filter_col, filter_val, x_col, y_col, pie_col, time_col, year_values):

        # Common fallback
        empty = px.scatter()

        if not data_json or not active_cols:
            return (empty, empty, empty)

        # 1) Load and reduce to relevant columns
        df = json_to_df(data_json)
        df = _subset_to_active(df, active_cols)
        if df.empty:
            return (empty, empty, empty)

        # 2) Apply global value filter (skip if sentinel "all")
        df = _apply_value_filter(df, filter_col, filter_val, all_token=all_sentinel)

        # 3) Apply global year filter (if chosen)
        df = _apply_year_filter(df, time_col, year_values)

        # 4) Build charts
        fig_map = _build_map(df, hover_col=x_col)
        fig_bar = _build_bar(df, x_col, y_col)
        fig_pie = _build_pie(df, pie_col)

        return (fig_map, fig_bar, fig_pie)
