# visualisation_tool

**visualisation_tool** is a Plotly Dash web application originally developed for fast visualisation of forestry data.  
It supports `.csv`, `.xls`, `.xlsx`, `.json`, and `.geojson` file formats and automatically preprocesses and categorises uploaded data for instant visual exploration.

While initially created as a part of my thesis and for forestry datasets, the tool can visualise **any structured tabular or spatial data**, making it a general-purpose solution for fast, interactive data analysis.

---

## Main Features

- **Upload -> Preprocess -> Categorise**  
  Automatically reads, cleans, and classifies columns by type (e.g., coordinates, time, numeric, categorical).
- **Interactive Charts**  
  Map, bar, line, scatter, pie, histogram, and box plots — all linked to the same dataset.
- **Dynamic Filtering**  
  Filter by column, value, or time range (with automatic year extraction).
- **GeoJSON Compatibility**  
  Flattens geographic features into a DataFrame, extracting latitude and longitude for mapping.
- **Automatic Smart Defaults**  
  Chooses suitable default axes and chart settings, but allows full manual override.
- **Session Storage**  
  Uses Dash’s `dcc.Store` components to hold active data, metadata, and filters during a session.

---

## Installation

### 1. Clone and enter the project
```
git clone https://github.com/yourusername/visualisation_tool.git
cd visualisation_tool
```
### 2. Create and activate a virtual environment
```
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies
```
pip install -r requirements.txt
```

### 4. Running the Application
```
python app.py
```
### 5. Open browser at
```
http://127.0.0.1:8050/
```

## Usage

1. Click Upload File or drag & drop to select a .csv, .xlsx, .json, or .geojson file.
2. The tool automatically detects column types (e.g. coordinates, time).
3. Choose which columns to include, apply filters, and explore data via interactive charts.
4. Use the Map view for spatial datasets, or the Line, Scatter, and Histogram views for numeric analysis.

---

## Technical Notes

- Uses Plotly Express and Dash Core Components for all charts and controls.
- Data is stored client-side with dcc.Store for fast updates between filters and plots.
- Designed for modularity — each callback file handles a single concern.

## License
Released under the MIT License.
