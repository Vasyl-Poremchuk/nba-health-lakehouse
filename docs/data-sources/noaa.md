# noaa

## 1. Identity

- **Name:** noaa (NOAA National Weather Service API)
- **Version:** No versioning (stable REST API; breaking changes are rare and announced)
- **URL:** [API documentation](https://www.weather.gov/documentation/services-web-api), [OpenAPI spec](https://api.weather.gov/openapi.json), [NCEI historical data](https://www.ncdc.noaa.gov/cdo-web/api/v2/) (separate API for archival records)
- **Owner / maintainer:** NOAA National Weather Service (US government, public domain)

## 2. Access pattern

- **Library / method used:** Direct HTTP REST calls to `https://api.weather.gov/`. No API key required. A `User-Agent` header identifying the application is mandatory.

  Two-step workflow for forecast / current observations at an NBA venue:

  ```python
  import requests

  HEADERS = {
      "User-Agent": "(nba-health-lakehouse, your-email@example.com)",
      "Accept": "application/geo+json",
  }

  def get_grid_info(lat: float, lon: float) -> dict:
      """Step 1: resolve lat/lon to NWS grid coordinates."""
      resp = requests.get(
          f"https://api.weather.gov/points/{lat},{lon}",
          headers=HEADERS,
          timeout=10,
      )
      resp.raise_for_status()
      props = resp.json()["properties"]

      return {
          "office": props["gridId"],
          "gridX": props["gridX"],
          "gridY": props["gridY"],
          "station_url": props["observationStations"],
      }

  def get_forecast(office: str, grid_x: int, grid_y: int) -> dict:
      """Step 2: fetch the 7-day forecast for the resolved grid."""
      resp = requests.get(
          f"https://api.weather.gov/gridpoints/{office}/{grid_x},{grid_y}/forecast",
          headers=HEADERS,
          timeout=15,
      )
      resp.raise_for_status()

      return resp.json()["properties"]["periods"]

  def get_latest_observation(station_id: str) -> dict:
      """Fetch the most recent surface observation from a nearby station."""
      resp = requests.get(
          f"https://api.weather.gov/stations/{station_id}/observations/latest",
          headers=HEADERS,
          timeout=10,
      )
      resp.raise_for_status()

      return resp.json()["properties"]
  ```

  For historical game-day weather (past observations), use the **NOAA NCEI CDO API** - a separate service requiring a free token:

  ```python
  NCEI_TOKEN = "<token from ncdc.noaa.gov/cdo-web/token>"

  resp = requests.get(
      "https://www.ncdc.noaa.gov/cdo-web/api/v2/data",
      headers={"token": NCEI_TOKEN},
      params={
          "datasetid": "GHCND",  # Global Historical Climatology Network - Daily
          "stationid": "GHCND:USW00014739",  # e.g., Boston Logan
          "startdate": "2024-01-01",
          "enddate": "2024-01-31",
          "datatypeid": "TMAX,TMIN,PRCP,AWND",
          "limit": 1000,
      },
      timeout=30,
  )
  ```

- **Authentication required:**
  - `api.weather.gov` (forecast / observations): No key. Requires `User-Agent: (app-name, contact-email)` header.
  - `ncdc.noaa.gov/cdo-web/api/v2/` (historical): Free token required; register at [https://www.ncdc.noaa.gov/cdo-web/token](https://www.ncdc.noaa.gov/cdo-web/token).

- **Rate limits:**
  - `api.weather.gov`: Not published. NOAA describes the limit as "generous for typical use"; requests exceeding it receive an error that "typically clears within 5 seconds." No sustained-batch concern for ~30 venues.
  - NCEI CDO API: 1,000 requests/day and 10,000 records/request on the free tier.

- **Coverage note:** `api.weather.gov` covers **the United States only**. The Toronto Raptors' home arena is not covered. For Toronto games, use [OpenWeatherMap](https://openweathermap.org/api) (paid tier for historical) or [Environment and Climate Change Canada](https://api.weather.gc.ca/).

## 3. Refresh cadence

- **How often upstream data changes:** TBD - to be defined when pipeline is implemented.
- **How often we plan to ingest:** TBD - to be defined per pipeline.

## 4. Fields used

- **Endpoints / pages consumed:** TBD - to be filled as ingestion pipelines are implemented.
- **Specific fields / columns relied on:** TBD - to be filled as ingestion pipelines are implemented.

## 5. License / terms of use

- **License or terms:** US government public domain. NWS API data carries no copyright restriction. NCEI CDO data is similarly public domain.
- **Restrictions on usage:** None for non-commercial and commercial use. Attribution to NOAA/NWS is recommended but not legally required.
- **robots.txt position:** N/A - calls are direct API requests, not web crawling.
- **Politeness policy:** Include a meaningful `User-Agent` with contact email on every request (as required by the API). Cache venue grid coordinates (`/points/`) after the first lookup - they never change for a fixed lat/lon.

## 6. Known quirks

- TBD - to be defined when pipeline is implemented.

## 7. Failure modes

- TBD - to be defined when pipeline is implemented.
