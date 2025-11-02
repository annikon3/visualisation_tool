from dash import Dash

from layout import build_layout
from callbacks.charts import register_charts_callbacks
from callbacks.upload import register as register_upload_callbacks
from callbacks.menus import register as register_menu_callbacks
from callbacks.filters import register as register_filter_callbacks


# TODO: Add new charts: line charts, stackable charts? 

# TODO: Add multiselection ticks or boxes for charts opened (don't show all charts by default). 

# TODO: When selecting columns for analysis, if user types a column name and it is already 'active', give feedback e.g. "already selected". 

# TODO: Prevent charts from going on top of each other when switching between screen sizes (map gets covered for some reason)


# Create app; suppress_callback_exceptions=True allows callbacks to 
# reference layout parts that may be loaded or replaced dynamically.
app = Dash(__name__, suppress_callback_exceptions=True)

# Expose the underlying Flask server if deployed on platforms expecting it
# (e.g., Gunicorn). Not strictly required for local dev.
server = app.server

# App Layout (pure UI structure)
app.layout = build_layout() 

# File Upload + preprocessing 
register_upload_callbacks(app)

# Menus & selectors population
register_menu_callbacks(app)

# Populates IDS.FILTERED_DATA
register_filter_callbacks(app) 

# Visualisations rendering 
register_charts_callbacks(app) 

# RUN APP
if __name__ == "__main__":
    app.run(debug=True)
