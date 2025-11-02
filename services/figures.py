from __future__ import annotations
from typing import Iterable, Optional, List
import pandas as pd
import plotly.express as px
from utils.helpers import extract_years
from utils.ids import IDS

# Fixed discrete colors for binary 0/1 on map
_BASE_MAP_COLORS = {"0": "#00CC00", "1": "#CC0000"}

# ---------- Helpers (pure, no Dash) ----------

def subset_to_active(df: pd.DataFrame, active_cols: Iterable[str], also_keep: Optional[List[str]] = None) -> pd.DataFrame:
    """
    Keep only active columns + latitude/longitude (if present) + optional also_keep.
    Allow keeping extra columns (e.g., time_col) even if not in active list. 
    Returns a copy to avoid chained-assignment warnings.
    """
    active = set(active_cols or [])
    extra  = {c for c in (also_keep or []) if c in df.columns}
    must   = {"latitude", "longitude"} if {"latitude", "longitude"}.issubset(df.columns) else set()
    keep   = [c for c in df.columns if (c in active) or (c in must) or (c in extra)]
    if not keep: 
        return df.iloc[0:0].copy()  # empty frame if nothing to keep
    return df[keep].copy()


def apply_value_filter(df: pd.DataFrame, col: Optional[str], val: Optional[str], all_token: Optional[str] = None) -> pd.DataFrame:
    """Apply equality filter unless value equals all_token."""
    if not col or val is None or col not in df.columns:
        return df
    if all_token is not None and val == all_token:
        return df
    # Compare as string to handle numbers/booleans uniformly
    return df[df[col].astype(str) == str(val)]


def apply_year_filter(df: pd.DataFrame, time_col: Optional[str], years: Optional[List[int]]) -> pd.DataFrame:
    """
    Filter rows to the given list of years using helpers.extract_years().
    Keeps only rows where the extracted year is in the provided list.
    Skips filtering if the special ALL token is present.
    """
    if not time_col or time_col not in df.columns or not years:
        return df
    
    # Skip if All is selected
    if isinstance(years, (list, tuple, set)) and IDS.ALL_SENTINEL in years:
        return df
    
    # Normalize single int -> list[int]
    if not isinstance(years, list):
        years = [years]

    # Convert possible string values like "2009" -> 2009
    years = [int(y) for y in years if str(y).isdigit()]

    # Extract numeric years from the time column
    year_series = extract_years(df[time_col]).astype("Int64")
    mask = year_series.isin(years)
    return df.loc[mask.fillna(False)]


# ---------- Internal helper ----------
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
    The point title (hover_name) becomes `hover_col` when present in the frame. 
    Colors by `color_col` when given; ; otherwise default coloring.
        - numeric & values in {0,1} -> fixed colors (0=green, 1=red)
        - numeric & >2 unique       -> continuous Viridis scale
        - non-numeric               -> fixed colors if only '0'/'1'
    Keeps the user's viewport (zoom/pan) across filter updates via uirevision.
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
        margin=dict(l=0, r=0, t=0, b=0),
        legend_title_text=legend_title,
        coloraxis_showscale=bool(continuous_scale),
        # Preserves the current viewport even when the figure updates
        uirevision="map-viewport",
    )
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
    Locks the x-axis to categorical order if x looks like year.
    Adds value labels and a small N annotation for clarity.
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
    else:
        # Counts by x
        counts = df[x_col].value_counts(dropna=False).reset_index()
        counts.columns = [x_col, "count"]
        # text shows the counts on bars
        fig = px.bar(counts, x=x_col, y="count", text="count")
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig = _lock_year_axis(fig, counts[x_col])

    # Small total N annotation (top-right)
    total_n = len(df)
    fig.update_layout(
        uniformtext_minsize=10,
        annotations=[
            dict(
                text=f"N = {total_n}",
                x=1, y=1.12, xref="paper", yref="paper",
                xanchor="right", showarrow=False,
                font=dict(size=12)
            )
        ] + (fig.layout.annotations or [])
    )
    return fig


def build_pie(df: pd.DataFrame, pie_col: Optional[str]):
    """Pie chart: distribution for a categorical column with clear labels; else empty figure."""
    if pie_col in df.columns:
        pie_counts = df[pie_col].value_counts(dropna=False).reset_index()
        pie_counts.columns = [pie_col, "count"]
        fig = px.pie(pie_counts, names=pie_col, values="count", hole=0.3)

        # Show label + percent + absolute value directly on slices
        fig.update_traces(textposition="inside", textinfo="label+percent+value")

        # Keep legend for color/key reference
        fig.update_layout(showlegend=True)

        return fig
    
    return px.scatter()
