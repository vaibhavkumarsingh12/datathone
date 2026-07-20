# SPEAR-themed Streamlit dashboard (Option 1)

New files only — your original `app/streamlit_app.py` is NOT changed.

## Install (copy 2 things into your repo `ksp-crime-intel/`)

1. Copy `streamlit_app_spear.py` into your `app/` folder:
   ```
   ksp-crime-intel/app/streamlit_app_spear.py
   ```

2. Copy the `.streamlit/` folder to the **repo root** (next to `app/`, `src/`, `data/`):
   ```
   ksp-crime-intel/.streamlit/config.toml
   ```

## Run

From inside `ksp-crime-intel/`:

```bash
streamlit run app/streamlit_app_spear.py
```

Your old app still runs exactly as before:

```bash
streamlit run app/streamlit_app.py
```

(Note: the old app will also pick up the dark theme from config.toml but keeps its
original look otherwise. Delete `.streamlit/config.toml` if you ever want the
default white theme back.)

## What's different in the SPEAR version

- Dark "command-center" theme (SPEAR design system colors, IBM Plex fonts)
- Custom stat cards with risk-color accent bars instead of plain st.metric
- Every Plotly chart: transparent background, themed fonts, subtle grid lines,
  SPEAR series colors, dark map style (carto-darkmatter)
- Charts wrapped in bordered cards
- No emoji in tabs — clean labels
- SPEAR brand block in the sidebar
- Same data, same filters, same logic — only the presentation changed
