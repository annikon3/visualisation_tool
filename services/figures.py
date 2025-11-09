from __future__ import annotations
from typing import Optional
import pandas as pd
import numpy as np
import plotly.express as px
import statsmodels

# ---------- Internal helpers ----------

# --- Common layout defaults ---
_DEFAULT_MARGIN = dict(l=0, r=0, t=60, b=0)

# Fixed discrete colors for binary 0/1 on map
_BASE_MAP_COLORS = {"0": "#00CC00", "1": "#CC0000"}

# --- Bar sizing & readability constants ---
_BAR_BASE_H   = 360   # base height for small charts
_BAR_PER_CAT  = 22    # extra px per category
_BAR_MAX_H    = 1600  # cap height to avoid absurdly tall figures
_BAR_TILT_TH  = 12    # tilt x tick labels if categories exceed this
_BAR_HIDE_TXT = 28    # hide value labels if categories exceed this

# --- Labelling controls --- 
_LABELS_ON = True          # master switch
_LABELS_MAX_POINTS = 30    # don't paint labels if more points than this
_LABEL_DECIMALS = 3        # numeric label precision

def _apply_title(fig, title: str, n: int):
    """Apply a centered title and an N subtext; keep minimal visual noise."""
    fig.update_layout(
        title=dict(text=f"{title}<br><sup>N = {n}</sup>", x=0.5, xanchor="center"),
        uniformtext_minsize=10,
    )
    return fig

def _auto_numeric_texttemplate(y_values, decimals: int = _LABEL_DECIMALS) -> str:
    """
    Decide texttemplate for numeric labels:
      - If all finite and integer-like -> "%{y}"
      - Else -> "%{y:.Nf}" where N = decimals
    Safe with lists/Series/ndarray; falls back to integer style on parsing errors.
    """
    try:
        arr = np.asarray(y_values, dtype=float)
        if np.isfinite(arr).all() and np.allclose(arr, np.round(arr)):
            return "%{y}"  # integer style
        return f"%{{y:.{decimals}f}}"
    except Exception:
        return "%{y}"

def _apply_data_labels(fig):
    """
    Add always-visible labels to most common trace types with safety rails.
    - Skips if LABELS_ON is False or point count exceeds LABELS_MAX_POINTS.
    - Respects existing labels: if a trace already has 'text', it won't be overwritten.
    """
    if not _LABELS_ON or not getattr(fig, "data", None):
        return fig

    # Rough point count for clutter control
    def _n(tr):
        # Pie traces expose the slice count via `labels` (may be a numpy array)
        if getattr(tr, "type", None) == "pie":
            labels = getattr(tr, "labels", None)
            try:
                return 0 if labels is None else len(labels)
            except Exception:
                return 0

        # For bar/line/scatter/histogram, prefer x then y length
        for attr in ("x", "y"):
            seq = getattr(tr, attr, None)
            if seq is not None:
                try:
                    return len(seq)
                except Exception:
                    continue
        return 0

    total = sum(_n(tr) for tr in fig.data)
    if total > _LABELS_MAX_POINTS:
        return fig
    
    for tr in fig.data:
        t = getattr(tr, "type", "")
        has_text = getattr(tr, "text", None) is not None

        if t == "bar":
            if not has_text:
                tr.update(
                    texttemplate=_auto_numeric_texttemplate(getattr(tr, "y", None)),
                    textposition="outside",
                    cliponaxis=False,
                )

        elif t == "scatter":  # covers line/points charts
            if not has_text:
                tr.update(
                    mode="lines+markers+text",
                    textposition="top center",
                    texttemplate=_auto_numeric_texttemplate(getattr(tr, "y", None)),
                )

        elif t == "histogram":
            if not has_text:
                # histogram counts live in 'y'
                tr.update(texttemplate="%{y}", textposition="outside", cliponaxis=False)

        elif t == "pie":
            # Pie works best with this trio; don't fight existing config
            if not has_text:
                tr.update(textposition="inside", textinfo="label+percent+value")

        elif t == "box":
            # Boxes are typically cleaner without per-point text; show mean line instead
            tr.update(boxmean=True)

        # other trace types: leave as-is
    return fig

def _ensure_year_axis(fig, x_series: pd.Series):
    """
    If x series looks like years (integer 1800..2100), force a categorical
    x-axis with explicit year order to avoid 2009.5-style ticks.
    """
    years = pd.to_numeric(x_series, errors="coerce").dropna().astype(int)
    if not years.empty and years.between(1800, 2100).all():
        cats = [str(y) for y in sorted(years.unique())]
        fig.update_xaxes(type="category", categoryorder="array", categoryarray=cats)
    return fig

def _finalize_figure(
    fig,
    title: str,
    n: int,
    *,
    x_series_for_year_lock: Optional[pd.Series] = None,
    add_labels: bool = True,
    margin: Optional[dict] = None,
):
    """
    One-stop finisher for all builders:
      - set margins
      - lock year axis if provided
      - set centered title with N
      - add always-visible labels (guarded)
    """
    fig.update_layout(margin=(margin or _DEFAULT_MARGIN))
    if x_series_for_year_lock is not None:
        fig = _ensure_year_axis(fig, x_series_for_year_lock)
    fig = _apply_title(fig, title, n)
    if add_labels:
        fig = _apply_data_labels(fig)
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
        legend_title_text=legend_title,
        coloraxis_showscale=bool(continuous_scale),
        # Preserves the current viewport even when the figure updates
        uirevision="map-viewport",
        legend_traceorder="normal",
    )

    # Map subplot needs its own uirevision as well
    if getattr(fig.layout, "map", None) is not None:
        fig.layout.map.uirevision = "map-viewport"

    # Use the unified finisher; keep labels off for maps to avoid clutter
    return _finalize_figure(
        fig,
        title=f"Geographical distribution{f' by {color_col}' if color_col else ''}",
        n=len(df),
        x_series_for_year_lock=None,
        add_labels=False,
        margin=_DEFAULT_MARGIN,
    )


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
        fig = px.bar(grouped, x=x_col, y=y_col)
        fig.update_traces(
            hovertemplate=f"%{{x}}<br>{y_col}: %{{y:.3f}}<extra></extra>",
            cliponaxis=False
        )
        fig = _ensure_year_axis(fig, grouped[x_col])
        description = f"Mean of {y_col} by {x_col}"

    else:
        # Counts by x
        counts = df[x_col].value_counts(dropna=False).reset_index()
        counts.columns = [x_col, "count"]
        # text shows the counts on bars
        fig = px.bar(counts, x=x_col, y="count")
        fig.update_traces(hovertemplate="%{x}<br>count: %{y}<extra></extra>", cliponaxis=False)
        fig = _ensure_year_axis(fig, counts[x_col])
        description = f"Count of records by {x_col}"

    # ---- Adaptive sizing & readability ----

    # Count number of categories actually plotted
    if y_col in df.columns and pd.api.types.is_numeric_dtype(df[y_col]):
        n_cats = len(grouped[x_col].unique())
        x_for_lock = grouped[x_col]
    else:
        n_cats = len(counts[x_col].unique())
        x_for_lock = counts[x_col]

    # Dynamic height: base + per-category growth, with a safe cap
    dynamic_h = min(_BAR_MAX_H, _BAR_BASE_H + _BAR_PER_CAT * n_cats)
    fig.update_layout(height=dynamic_h, autosize=True)

    # Expose computed category count for downstream use (if needed)
    meta = dict(fig.layout.meta) if fig.layout.meta else {}
    meta["n_cats"] = int(n_cats)
    fig.update_layout(meta=meta)

    # Tilt x tick labels for readability
    if n_cats > _BAR_TILT_TH:
        fig.update_xaxes(tickangle=-60, automargin=True)
    
    # Hide value labels when there are many bars (hover still shows values)
    if n_cats > _BAR_HIDE_TXT:
        fig.update_traces(textposition="none")

    fig.update_yaxes(rangemode="tozero")

    # Unified finisher (locks year axis, sets title+N, margins, labels)
    return _finalize_figure(
        fig,
        title=description,
        n=len(df),
        x_series_for_year_lock=x_for_lock,
        margin=_DEFAULT_MARGIN
    )


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
    fig = _apply_data_labels(fig)
    return fig


def build_hist(df: pd.DataFrame, col: Optional[str]):
    """Histogram of a numeric column with robust bin selection."""
    if not col or col not in df.columns:
        return px.scatter()

    # Coerce to numeric; keep only finite values
    s = pd.to_numeric(df[col], errors="coerce")
    s = s[np.isfinite(s)]
    if s.empty:
        return px.scatter()
    
    # Heuristic: sqrt rule with sane caps; also cap by number of unique values
    n_unique = s.nunique(dropna=True)
    n = int(np.sqrt(len(s))) if len(s) > 0 else 1
    nbins = max(5, min(60, n, int(n_unique)))  # 5..60, not more than unique values
    
    fig = px.histogram(s, x=s, nbins=nbins, opacity=0.9, marginal="rug")
    fig.update_layout(bargap=0.05)

    return _finalize_figure(
        fig,
        title=f"Distribution of {col}",
        n=len(s),
        x_series_for_year_lock=None,
        margin=_DEFAULT_MARGIN,
    )


def build_box(df: pd.DataFrame, x_col: Optional[str], y_col: Optional[str]):
    """Box/violin-like summary; robust against outliers."""
    if not x_col or x_col not in df.columns or not y_col or y_col not in df.columns:
        return px.scatter()
    if not pd.api.types.is_numeric_dtype(df[y_col]):
        return px.scatter()
    fig = px.box(df, x=x_col, y=y_col, points="outliers")
    return _finalize_figure(
        fig,
        title=f"Distribution of {y_col} by {x_col}",
        n=len(df),
        x_series_for_year_lock=None,
        margin=_DEFAULT_MARGIN,
    )


def build_line(df: pd.DataFrame, t_col: Optional[str], y_col: Optional[str]):
    """Simple time series: mean(Y) by time (year or exact timestamp)."""
    if not t_col or t_col not in df.columns or not y_col or y_col not in df.columns:
        return px.scatter()
    if not pd.api.types.is_numeric_dtype(df[y_col]):
        return px.scatter()
    
    # If datetime -> group by exact period; if numeric (year-like) -> group by int year
    s = df[t_col]
    if pd.api.types.is_datetime64_any_dtype(s):
        g = df.groupby(s.dt.to_period("M"))[y_col].mean().reset_index()
        g[t_col] = g[t_col].astype(str)  # Period -> str for axis
    else:
        # Coerce to whole-year categories
        yrs = pd.to_numeric(s, errors="coerce").round(0).astype("Int64")
        g = (
            df.assign(__year=yrs)
              .dropna(subset=["__year"])
              .groupby("__year")[y_col].mean()
              .reset_index()
              .rename(columns={"__year": t_col})
        )
        # Make the x-axis categorical with exact year labels
        g[t_col] = g[t_col].astype("Int64").astype(str)

    fig = px.line(g, x=t_col, y=y_col)

    # For year-like numeric time we already casted to str -> categorical axis;
    # For real datetimes we keep temporal axis (no year lock needed).
    x_for_lock = g[t_col] if not pd.api.types.is_datetime64_any_dtype(df[t_col]) else None

    return _finalize_figure(
        fig,
        title=f"Mean of {y_col} over {t_col}",
        n=len(df),
        x_series_for_year_lock=x_for_lock,
        margin=_DEFAULT_MARGIN,
    )


def build_scatter(df: pd.DataFrame, x_col: Optional[str], y_col: Optional[str], color_col: Optional[str] = None, trendline: bool = False):
    """Basic scatter: X vs Y, optional categorical color and OLS trendline."""
    if not x_col or not y_col or x_col not in df.columns or y_col not in df.columns:
        return px.scatter()
    if not pd.api.types.is_numeric_dtype(df[y_col]):
        return px.scatter()

    trend_arg = None
    if trendline:
        # Try to enable OLS; if statsmodels missing, fall back silently
        try:
            trend_arg = "ols"
        except Exception:
            trend_arg = None  # no hard dependency

    color = color_col if (color_col in df.columns) else None
    fig = px.scatter(df, x=x_col, y=y_col, color=color, opacity=0.85, trendline=trend_arg, trendline_color_override="#111827")
    fig.update_traces(
        hovertemplate=f"%{{x}}<br>{y_col}: %{{y:.{_LABEL_DECIMALS}f}}<extra></extra>"
    )

    # If x looks like years, ensure categorical axis
    x_for_lock = df[x_col]
    fig = _finalize_figure(
        fig,
        title=f"{y_col} vs {x_col}" + (f" by {color_col}" if color else ""),
        n=len(df),
        x_series_for_year_lock=x_for_lock,
        margin=_DEFAULT_MARGIN,
    )
    return fig

