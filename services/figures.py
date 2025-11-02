from __future__ import annotations
from typing import Iterable, Optional, List
import pandas as pd
import plotly.express as px
from utils.helpers import extract_years
from utils.ids import IDS

# Fixed discrete colors for binary 0/1 on map
_BASE_MAP_COLORS = {"0": "#00CC00", "1": "#CC0000"}

# ---------- Internal helpers ----------

def _apply_title(fig, title: str, n: int):
    """Apply a centered title and an N subtext; keep minimal visual noise."""
    fig.update_layout(
        title=dict(text=f"{title}<br><sup>N = {n}</sup>", x=0.5, xanchor="center"),
        uniformtext_minsize=10,
    )
    return fig

def _lock_year_axis(fig, x_series: pd.Series):
    """
    If x looks like a year axis, force categorical ordering to avoid 2009.5 etc. (in bar chart)
    """
    years = pd.to_numeric(x_series, errors="coerce").dropna().astype(int)
    # Basic heuristic: all values are 4-digit-ish and within a sane year range
    if not years.empty and years.between(1800, 2100).all():
        cats = [str(y) for y in sorted(years.unique())]
        fig.update_xaxes(type="category", categoryorder="array", categoryarray=cats)
    return fig


# ---------- Figure builders ----------

def build_map(df: pd.DataFrame, hover_col: Optional[str], color_col: Optional[str] = None):
    """
    Render a scatter map if latitude/longitude exist; else return an empty figure.
    Colors by `color_col` when given; ; otherwise default coloring.
        - numeric & values in {0,1} -> fixed colors (0=green, 1=red)
        - numeric & >2 unique       -> continuous Viridis scale
        - non-numeric               -> fixed colors if only '0'/'1'
    Keeps user's zoom/pan (uirevision), fixes legend order for binary data,
    and applies descriptive title.
    """
    if not {"latitude", "longitude"}.issubset(df.columns):
        return px.scatter()

    geo = df.dropna(subset=["latitude", "longitude"])
    if geo.empty:
        return px.scatter()

    # Determine color logic
    color_arg = None
    discrete_map = None
    continuous_scale = None
    legend_title = None

    if color_col and color_col in geo.columns:
        s = geo[color_col]
        legend_title = color_col

        if pd.api.types.is_numeric_dtype(s):
            uniq = pd.unique(s.dropna())
            # Case: strictly binary 0/1 -> force categorical by casting to string
            if len(uniq) <= 2 and set(uniq).issubset({0, 1}):
                tmp = f"__color_{color_col}"
                geo = geo.copy()
                # normalize to 0/1 -> "0"/"1"
                geo[tmp] = pd.to_numeric(s, errors="coerce").round(0).astype("Int64").astype(str)
                color_arg = tmp
                discrete_map = _BASE_MAP_COLORS
                # force stable order 0 -> 1
                geo[tmp] = pd.Categorical(geo[tmp], categories=["0", "1"], ordered=True)
            else:
                # Numeric multi-valued -> continuous Viridis
                color_arg = color_col
                continuous_scale = "Viridis"
        else:
            # Non-numeric; give fixed colors if only '0'/'1'
            color_arg = color_col
            vals = set(s.dropna().astype(str).unique())
            if vals.issubset({"0", "1"}):
                discrete_map = _BASE_MAP_COLORS

    fig = px.scatter_map(
        geo,
        lat="latitude",
        lon="longitude",
        hover_name=hover_col if (hover_col in geo.columns) else None,
        color=color_arg,
        color_discrete_map=discrete_map,
        color_continuous_scale=continuous_scale,
        zoom=4,
        height=500,
    )

    fig.update_layout(
        map_style="open-street-map",
        margin=dict(l=0, r=0, t=60, b=0), 
        legend_title_text=legend_title,
        coloraxis_showscale=bool(continuous_scale),
        # Preserves the current viewport even when the figure updates
        uirevision="map-viewport",
        legend_traceorder="normal",
    )

    fig = _apply_title(fig, f"Geographical distribution{f' by {color_col}' if color_col else ''}", len(df))

    # Map subplot needs its own uirevision as well
    if getattr(fig.layout, "map", None) is not None:
        fig.layout.map.uirevision = "map-viewport"

    return fig 


def build_bar(df: pd.DataFrame, x_col: Optional[str], y_col: Optional[str]):
    """
    Bar chart:
       - If x and numeric y: show mean(y) by x
       - Else if x only:     show counts by x
       - Else:               empty figure
       - Locks the x-axis to categorical order if x looks like year.
       - Includes value labels, N annotation and descriptive title.
    """
    if not x_col or x_col not in df.columns:
        return px.scatter()
    
    # Make x categorical; for year-like numbers, round -> int -> str 
    df = df.copy()
    x_series = df[x_col]
    if pd.api.types.is_numeric_dtype(x_series):
        # If values look like years, coerce to whole-year categories
        x_num = pd.to_numeric(x_series, errors="coerce")
        if x_num.notna().all() and x_num.between(1800, 2100).any():
            df[x_col] = x_num.round(0).astype("Int64").astype(str)
        else:
            df[x_col] = x_series.astype(str)
    else:
        df[x_col] = x_series.astype(str)

    # Mean(y) by x, roud to 3 decimals
    if y_col in df.columns and pd.api.types.is_numeric_dtype(df[y_col]):
        grouped = (
            df.groupby(x_col, dropna=False, observed=True)[y_col]
            .mean(numeric_only=True)
            .round(3) 
            .reset_index()
        )
        grouped["label"] = grouped[y_col].apply(lambda v: f"{v:.3f}")
        fig = px.bar(grouped, x=x_col, y=y_col, text="label")

        # show values on/above bars; avoid clipping
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig = _lock_year_axis(fig, grouped[x_col])
        description = f"Mean of {y_col} by {x_col}"

    else:
        # Counts by x
        counts = df[x_col].value_counts(dropna=False).reset_index()
        counts.columns = [x_col, "count"]
        # text shows the counts on bars
        fig = px.bar(counts, x=x_col, y="count", text="count")
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig = _lock_year_axis(fig, counts[x_col])
        description = f"Count of records by {x_col}"

    fig = _apply_title(fig, description, len(df))
    fig.update_yaxes(rangemode="tozero")
    fig.update_layout(margin=dict(l=0, r=0, t=60, b=0), bargap=0.2)
    return fig


def build_pie(df: pd.DataFrame, pie_col: Optional[str]):
    """
    Pie chart: category distribution with % and absolute values. 
    Unified title and legend.
    Else empty figure.
    """
    if pie_col not in df.columns:
        return px.scatter()
    
    pie_counts = df[pie_col].value_counts(dropna=False).reset_index()
    pie_counts.columns = [pie_col, "count"]
    fig = px.pie(pie_counts, names=pie_col, values="count", hole=0.3)

    # Show label + percent + absolute value directly on slices
    fig.update_traces(textposition="inside", textinfo="label+percent+value")
    fig.update_layout(showlegend=True)
    fig = _apply_title(fig, f"Distribution of {pie_col} (share of total)", len(df))
    return fig
