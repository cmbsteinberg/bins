# Coverage Map Implementation

This document details the implementation of the UK Bin Collection coverage map.

## Overview

The coverage map provides a visual representation of which Local Authority Districts (LADs) are currently supported by the bin collection scrapers. It uses green for supported areas (where a `scraper_id` exists) and red for unsupported areas.

## Components

### 1. Data Processing Script
- **File:** `scripts/generate_coverage_map.py`
- **Purpose:** Fetches UK boundary GeoJSON from the ArcGIS Geoportal API and joins it with coverage data from `api/data/lad_lookup.json` using a simple Python dict/set lookup.
- **Output:**
    - `api/static/coverage.geojson`: Enriched GeoJSON with a `covered` boolean property per feature. Coordinates are rounded to 5 decimal places (~1m accuracy) to reduce file size, and JSON is written with compact separators.
    - `api/static/coverage_map.html`: A standalone Leaflet.js map that renders the GeoJSON.

### 2. Map Rendering
- **Technology:** Leaflet.js (loaded from unpkg CDN)
- **Logic:**
    - Colors features based on `feature.properties.covered`.
    - Includes a legend and interactive popups showing the council name and coverage status.
    - Fetches the data asynchronously from `/static/coverage.geojson`.

### 3. Frontend Integration
- **File:** `api/templates/index.html`
- **Change:** A `<section id="coverage">` at the bottom of the main container embeds the map using an `<iframe src="/static/coverage_map.html">`.

## How to Update
Whenever `api/data/lad_lookup.json` is updated or new scrapers are added, run:

```bash
python scripts/generate_coverage_map.py
```

## Dependencies
- `httpx`
- `leaflet.css` and `leaflet.js` (via CDN in the HTML)
