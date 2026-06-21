# static_reference_data

## 1. Identity

- **Name:** static_reference_data
- **Version:** N/A - internal files maintained in this repository; version-controlled via git
- **URL:** No external URL. Files live at `data/reference/` in this repo.
- **Owner / maintainer:** This project. Values compiled from public sources (see Section 5).

## 2. Access pattern

- **Library / method used:** Direct CSV read - no HTTP requests, no authentication, no rate limits.

  ```python
  from pathlib import Path

  import pandas as pd

  REF = Path("data/reference")

  arenas = pd.read_csv(REF / "arenas.csv")
  teams  = pd.read_csv(REF / "teams.csv")
  ```

  Both files are checked into the repository and loaded at pipeline startup. They do not change during a pipeline run.

- **Authentication required:** None.

- **Rate limits:** None - local file read.

## 3. Refresh cadence

- **How often upstream data changes:** Extremely rarely. NBA team/arena assignments change only on expansion, relocation, or arena replacement - historically a few times per decade. The last major change was the Seattle SuperSonics -> Oklahoma City Thunder relocation in 2008. The next expected change is Las Vegas expansion (~2027).
- **How often we plan to ingest:** Files are loaded once per pipeline run; no scheduled re-fetch. Update the CSVs manually and commit when a real-world change occurs (new arena, relocated franchise, conference realignment).

## 4. Fields used

- **Files:**

  **`data/reference/arenas.csv`**

  | Column | Type | Example | Notes |
  |---|---|---|---|
  | `team_abbreviation` | string | `BOS` | Matches NBA.com / nba_api abbreviation |
  | `arena_name` | string | `TD Garden` | Official current name |
  | `city` | string | `Boston` |  |
  | `state` | string | `MA` | 2-letter US state; `ON` for Toronto |
  | `country` | string | `USA` | `CAN` for Toronto |
  | `latitude` | float | `42.3662` | Decimal degrees, WGS84 |
  | `longitude` | float | `-71.0621` | Decimal degrees, WGS84 |
  | `capacity` | integer | `19156` |  |
  | `opened_year` | integer | `1995` |  |

  **`data/reference/teams.csv`**

  | Column | Type | Example | Notes |
  |---|---|---|---|
  | `team_id` | integer | `1610612738` | NBA.com internal team ID |
  | `abbreviation` | string | `BOS` | 3-letter abbreviation used across all pipelines |
  | `full_name` | string | `Boston Celtics` |  |
  | `city` | string | `Boston` |  |
  | `conference` | string | `East` | `East` or `West` |
  | `division` | string | `Atlantic` | One of the six NBA divisions |
  | `arena_name` | string | `TD Garden` | Foreign key to `arenas.csv` |

## 5. License / terms of use

- **License or terms:** The CSV files are original compilations of publicly available facts (coordinates, names, division assignments). Facts are not copyrightable; no third-party license governs these files. The files themselves are released under this project's license.
- **Origin of values:**
  - Arena coordinates: compiled from Wikipedia's [List of NBA arenas](https://en.wikipedia.org/wiki/List_of_NBA_arenas) and cross-checked via geocoding.
  - Conference / division mapping: from [NBA.com team pages](https://www.nba.com/teams) (current season alignment).
  - Team IDs: from `nba_api` `commonallplayers` endpoint (`TEAM_ID` field).
  - Arena capacity and opening year: from Wikipedia arena articles.
- **Restrictions on usage:** None - internal data.
- **robots.txt position:** N/A - no external source is crawled.
- **Politeness policy:** N/A - local file read.

## 6. Known quirks

- **Name-matching across sources** - Arena names differ between sources (e.g., "Crypto.com Arena" vs "Staples Center" in older records). Always join on `team_abbreviation`, not arena name.
- **Toronto time zone** - The Raptors' arena is in Ontario (`America/Toronto`); pipelines computing local game time must handle this as the only non-US venue.
- **Naming rights churn** - Arena sponsorship names change every few years. The `arena_name` column should hold the current name at time of last update; historical records may reference an older name. Add a `former_names` note in a comment within the CSV or a companion `arenas_history.csv` if historical matching is needed.
- **Las Vegas expansion** - An expansion franchise is expected ~2027. The files will need a new row when the team and arena are confirmed.
- **Team ID source of truth** - The `team_id` values come from `nba_api`; if NBA.com ever reassigns IDs (historically it has not), these must be updated.

## 7. Failure modes

- **What breaks if this source is down or changes:** Pipelines that join on `team_abbreviation` or look up arena coordinates will produce nulls or fail if the CSV is missing a team or has an incorrect abbreviation. Unlike external sources, there is no HTTP dependency - failures are caused by stale data in the files, not network issues.
- **Detection:** At pipeline startup, assert that `arenas.csv` contains exactly 30 rows and `teams.csv` contains exactly 30 rows (or the current team count). Raise on any null in `latitude`, `longitude`, `conference`, or `division`.
- **Fallback / mitigation:** The files are version-controlled; roll back to the previous commit if a bad edit is introduced. Keep the Wikipedia and NBA.com source links in Section 5 current so values can be re-verified quickly after any real-world change.
