# ourairports

## 1. Identity

- **Name:** ourairports
- **Version:** No API versioning; static dataset files pinned by git commit SHA. Updated weekly.
- **URL:** [Data page](https://ourairports.com/data/), [GitHub repository](https://github.com/davidmegginson/ourairports-data), [About](https://ourairports.com/about.html)
- **Owner / maintainer:** [David Megginson](https://github.com/davidmegginson) and community contributors

## 2. Access pattern

- **Library / method used:** Direct file download - no API, no authentication, no rate limits. Files are served as raw CSV from GitHub. Pin to a specific commit SHA for reproducible pipelines.

  Available files:

  | File | Records | Update frequency | Notes |
  |---|---|---|---|
  | [`airports.csv`](https://davidmegginson.github.io/ourairports-data/airports.csv) | 74,000+ airports | Weekly | Primary file for this project |
  | [`runways.csv`](https://davidmegginson.github.io/ourairports-data/runways.csv) | Runway metadata | Weekly | Not needed for NBA travel use case |
  | [`countries.csv`](https://davidmegginson.github.io/ourairports-data/countries.csv) | Country codes | Rarely | ISO 3166 reference |
  | [`regions.csv`](https://davidmegginson.github.io/ourairports-data/regions.csv) | Region codes | Rarely | ISO 3166-2 reference |

  `airports.csv` key fields (header row included):

  | Field | Type | Example | Notes |
  |---|---|---|---|
  | `id` | integer | `3448` | OurAirports internal ID |
  | `ident` | string (ICAO) | `KBOS` | ICAO code; globally unique |
  | `type` | string | `large_airport` | Filter to `large_airport` / `medium_airport` |
  | `name` | string | `General Edward Lawrence Logan International Airport` | Official name |
  | `latitude_deg` | float | `42.36429977` | WGS84 decimal degrees |
  | `longitude_deg` | float | `-71.00520325` | WGS84 decimal degrees |
  | `elevation_ft` | integer | `20` | Elevation above sea level |
  | `continent` | string | `NA` | Two-letter continent code |
  | `iso_country` | string | `US` | ISO 3166-1 alpha-2 |
  | `iso_region` | string | `US-MA` | ISO 3166-2 region |
  | `municipality` | string | `Boston` | City name |
  | `iata_code` | string | `BOS` | IATA 3-letter code; blank for smaller airports |

  ```python
  import pandas as pd

  AIRPORTS_URL = (
      "https://davidmegginson.github.io/ourairports-data/airports.csv"
  )
  # Pin to a specific commit for reproducibility:
  # AIRPORTS_URL = (
  #     "https://raw.githubusercontent.com/davidmegginson/ourairports-data"
  #     "/<commit-sha>/airports.csv"
  # )

  airports = pd.read_csv(AIRPORTS_URL, low_memory=False)

  # Filter to large/medium airports in the US and Canada (covers all NBA cities)
  nba_airports = airports[
      airports["type"].isin(["large_airport", "medium_airport"])
      & airports["iso_country"].isin(["US", "CA"])
  ]

  # Join to NBA arena reference by IATA code
  nba_iata = ["BOS", "LAX", "JFK", "ORD", "MIA", "YYZ", ...]  # all 30 markets
  arena_airports = nba_airports[nba_airports["iata_code"].isin(nba_iata)]
  ```

- **Authentication required:** None. No API key. GitHub raw file downloads are unauthenticated.

- **Rate limits:** None for individual file downloads. Download once at pipeline setup time and cache in the bronze layer rather than fetching on every run.

## 3. Refresh cadence

- **How often upstream data changes:** Weekly automated updates. Airport coordinates, IATA codes, and names for established NBA city airports are extremely stable - changes occur only when airports open, close, or are renamed.
- **How often we plan to ingest:** Download once per pipeline bootstrapping; re-fetch at most seasonally or when a franchise relocates. Cache the raw CSV in S3 bronze and reload from there on each pipeline run.

## 4. Fields used

- **Files consumed:**

  | File | Purpose |
  |---|---|
  | `airports.csv` | Airport lat/lon and IATA codes for NBA home cities; input for travel-distance calculations and weather station lookups |

- **Specific fields / columns relied on:** `ident` (ICAO), `iata_code`, `municipality`, `latitude_deg`, `longitude_deg`, `iso_country`, `type`.

## 5. License / terms of use

- **License or terms:** [CC0 1.0 Universal (Public Domain Dedication)](https://creativecommons.org/publicdomain/zero/1.0/). No copyright restrictions whatsoever.
- **Restrictions on usage:** None. Commercial use, redistribution, and derivative works are all permitted without attribution (though attribution is appreciated).
- **robots.txt position:** N/A - files are downloaded directly from GitHub, not crawled from the OurAirports website.
- **Politeness policy:** Download each file once and cache; do not poll GitHub more than once per week.

## 6. Known quirks

- **Blank `iata_code` values** - Smaller airports have an empty `iata_code`. Always filter to `type IN ('large_airport', 'medium_airport')` before joining on IATA codes to avoid unexpected nulls.
- **Toronto included** - Unlike `api.weather.gov` (US-only), OurAirports covers Toronto Pearson International (`YYZ`, `CYYZ`). This makes it the right reference for any pipeline that must handle the Raptors' home games.
- **`municipality` ≠ arena city in some markets** - Los Angeles area has multiple airports in different municipalities (LAX in Los Angeles, SNA in Santa Ana for OC). Join on IATA code explicitly rather than city name string-matching.
- **Header row present** - Unlike OpenFlights' headerless `.dat` files, `airports.csv` includes a header row; `pd.read_csv` works out of the box without manually specifying column names.
- **Coordinate precision** - Coordinates are given to 8 decimal places; for travel-distance purposes via the Haversine formula, 4-5 decimal places is more than sufficient.

## 7. Failure modes

- **What breaks if this source is down or changes:** GitHub outages prevent initial download; pipelines that depend on the bronze-cached CSV are unaffected. Column renames in the CSV (rare) would break field lookups silently.
- **Detection:** Assert that `airports.csv` contains the expected columns (`ident`, `iata_code`, `latitude_deg`, `longitude_deg`) immediately after loading. Validate that all NBA IATA codes resolve to a non-null row before proceeding.
- **Fallback / mitigation:** The raw CSV is cached immutably in the S3 bronze layer after first download. Since airport data for established NBA cities changes almost never, the cached version remains valid indefinitely. Pin the GitHub commit SHA in the pipeline config to guarantee exact reproducibility.
