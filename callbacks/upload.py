# -------------------------------------------------------------------
# Single responsibility: 
# handle file upload -> read -> preprocess -> categorize -> store
# -------------------------------------------------------------------

from __future__ import annotations
import base64, io
import pandas as pd
from dash import Input, Output, State

from utils.ids import IDS
from utils.jsonloaders import load_json_or_geojson
from services.preprocess import preprocess_dataframe
from services.classify import categorize_columns

# --- Internal helper ---
def _read_uploaded(contents: str, filename: str) -> pd.DataFrame:
    """
    Decode the uploaded file and return a DataFrame.
    Supports CSV, Excel, JSON/GeoJSON.
    """
    # contents looks like: "data:application/...;base64,<BASE64>"
    payload = base64.b64decode(contents.split(",", 1)[1])

    # Excel
    if filename and filename.lower().endswith((".xls", ".xlsx")):
        return pd.read_excel(
            io.BytesIO(payload),
            na_values=["", " ", "-", "NA", "N/A", "nan", "NaN"]
        )

    # JSON & GeoJSON via dedicated loader
    if filename and filename.lower().endswith((".json", ".geojson")):
        return load_json_or_geojson(payload)

    # Default: CSV
    return pd.read_csv(io.BytesIO(payload))


def register(app):
    """
    Register the upload callback on the given Dash app instance.
    """
    @app.callback(
        Output(IDS.DATA, "data"),
        Output(IDS.META, "data"),
        Input(IDS.UPLOAD, "contents"),
        State(IDS.UPLOAD, "filename"),
        prevent_initial_call=True,
    )
    def handle_upload(contents, filename):
        """
        1) Read uploaded file into a DataFrame
        2) Run preprocessing (clean cols, parse dates, coords, etc.)
        3) Categorize columns
        4) Store both processed data (JSON) and meta (dict) in dcc.Store
        """
        if not contents:
            return None, None

        try:
            raw_df = _read_uploaded(contents, filename)
            processed = preprocess_dataframe(raw_df).copy()
            meta = categorize_columns(processed)
            # Store dataframe as JSON (orient='split' keeps dtypes nicely)
            return processed.to_json(orient="split", date_format="iso"), meta
        except Exception as exc:
            print(f"[upload] Failed to read/process '{filename}': {exc}")
            return None, None
