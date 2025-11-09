# Single source of truth for all Dash component IDs.

class IDS:
    # Stores
    DATA          = "data"
    META          = "meta"
    ACTIVE_COLS   = "active_cols"
    FILTERED_DATA = "filtered_data"

    # File upload
    UPLOAD = "upload"

    # Category browsing
    CATEGORY     = "category"
    COLUMNS_VIEW = "columns-view"

    # Column choosing
    KEEP_COLS = "keep_cols"

    # Generic filtering
    FILTER_COL = "filter_col"
    FILTER_VAL = "filter_val"

    # Time filtering
    TIME_COL    = "time_col"
    # multi-select of selected years
    YEAR_VALUES = "year_values"

    # Single source of truth for the “no filtering” token
    ALL_SENTINEL = "__ALL__"

    # Chart selectors
    X_COL      = "x_col"
    Y_COL      = "y_col"
    PIE_COL    = "pie_col"
    HIST_COL   = "hist_col"
    BOX_X      = "box_x"
    BOX_Y      = "box_y"
    LINE_TIME  = "line_time"
    LINE_Y     = "line_y"

    # Charts
    FIG_MAP    = "fig_map"
    FIG_BAR    = "fig_bar"
    FIG_PIE    = "fig_pie"
    FIG_HIST   = "fig_hist"
    FIG_BOX    = "fig_box"
    FIG_LINE   = "fig_line"
