# nba_api

## 1. Identity

- **Name:** nba_api
- **Version:** `>= 1.11.4` (Python `>= 3.10`)
- **URL:** [Package](https://pypi.org/project/nba_api/), [Repository](https://github.com/swar/nba_api), [Documentation](https://github.com/swar/nba_api/blob/master/README.md)
- **Owner / maintainer:** [swar](https://github.com/swar) & [rsforbes](https://github.com/rsforbes)

## 2. Access pattern

- **Library / method used:** nba_api wraps the publicly accessible NBA.com endpoints. Two sub-packages are available:

  - `nba_api.stats` - 99+ historical and aggregated endpoints, served from `stats.nba.com`.
  - `nba_api.live` - 4 real-time endpoints, served from `cdn.nba.com`.

  ```python
  # stats endpoint (historical)
  from nba_api.stats.endpoints import PlayerCareerStats

  df = PlayerCareerStats(player_id=2544).get_data_frames()[0]

  # live endpoint (real-time)
  from nba_api.live.nba.endpoints import scoreboard

  board = scoreboard.ScoreBoard().get_dict()
  ```

- **Authentication required:** No API key. NBA.com is browser-gated via Cloudflare; the library sends the required headers automatically:

  ```
  User-Agent:          <current browser string>
  Referer:             https://www.nba.com/
  x-nba-stats-origin: stats
  x-nba-stats-token:  true
  ```

  These headers must stay current with NBA.com expectations. v1.11.4 fixed a broken user-agent string that caused all requests to fail; always run the current release.

- **Rate limits:** No officially published limit. Cloudflare-enforced; the community-tested threshold is **≥ 750 ms between requests** before throttling triggers. Sustained batch work should use 1-2 s spacing with exponential backoff on 429 / timeout. `stats.nba.com` **actively blocks cloud IP ranges** (AWS EC2, Heroku, DigitalOcean); `cdn.nba.com` (live endpoints) is less restricted.

  ```python
  import time

  for game_id in game_ids:
      fetch_game(game_id)
      time.sleep(0.75)
  ```

## 3. Refresh cadence

- **How often upstream data changes:**
  - Live game data (`cdn.nba.com`): ~2-3 s TTL during active games; 600 s post-game; 4 h after 7 days.
  - Season stats (`stats.nba.com`): updated post-game, typically once daily during the season.
  - Historical data: stable; changes only for retroactive corrections.
- **How often we plan to ingest:** TBD - to be defined per pipeline.

## 4. Fields used

- **Endpoints / pages consumed:**

  `nba_api.stats` key endpoints:

  | Endpoint | Purpose | Docs |
  |---|---|---|
  | `commonallplayers` | Master player list with IDs | [link](https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoints/commonallplayers.md) |
  | `commonplayerinfo` | Player bio / profile | [link](https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoints/commonplayerinfo.md) |
  | `commonteamroster` | Current team roster | [link](https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoints/commonteamroster.md) |
  | `playercareerstats` | Career totals and per-season stats | [link](https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoints/playercareerstats.md) |
  | `playergamelog` | Player game-by-game log | [link](https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoints/playergamelog.md) |
  | `leaguegamelog` | All games for a season | [link](https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoints/leaguegamelog.md) |
  | `leaguedashplayerstats` | League-wide per-player dashboard stats | [link](https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoints/leaguedashplayerstats.md) |
  | `leaguedashteamstats` | League-wide per-team dashboard stats | [link](https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoints/leaguedashteamstats.md) |
  | `leaguestandingsv3` | Current standings | [link](https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoints/leaguestandingsv3.md) |
  | `boxscoretraditionalv3` | Per-game box scores (pts, reb, ast) | [link](https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoints/boxscoretraditionalv3.md) |
  | `boxscoreadvancedv3` | Advanced metrics (TS%, USG%, etc.) | [link](https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoints/boxscoreadvancedv3.md) |
  | `boxscoresummaryv2` | Game summary (score, officials, attendance) | [link](https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoints/boxscoresummaryv2.md) |
  | `shotchartdetail` | Shot location data per player / game | [link](https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoints/shotchartdetail.md) |
  | `playbyplayv3` | Play-by-play (V2 deprecated - returns empty JSON) | [link](https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoints/playbyplayv3.md) |
  | `scoreboardv3` | Daily scoreboard (V2 deprecated for 2025-26 season) | [link](https://github.com/swar/nba_api/blob/master/src/nba_api/stats/endpoints/scoreboardv3.py) |
  | `drafthistory` | Historical draft picks | [link](https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoints/drafthistory.md) |
  | `leagueleaders` | Season statistical leaders | [link](https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoints/leagueleaders.md) |

  `nba_api.live` endpoints:

  | Endpoint | Purpose | Docs |
  |---|---|---|
  | `scoreboard` | Today's live scores | [link](https://github.com/swar/nba_api/blob/master/docs/nba_api/live/endpoints/scoreboard.md) |
  | `boxscore` | Live in-game box score | [link](https://github.com/swar/nba_api/blob/master/docs/nba_api/live/endpoints/boxscore.md) |
  | `playbyplay` | Live play-by-play | [link](https://github.com/swar/nba_api/blob/master/docs/nba_api/live/endpoints/playbyplay.md) |
  | `odds` | Live betting odds (added v1.9.0) | [link](https://github.com/swar/nba_api/blob/master/docs/nba_api/live/endpoints/odds.md) |

- **Specific fields / columns relied on:** TBD - to be filled as ingestion pipelines are implemented.

## 5. License / terms of use

- **License or terms:** MIT (nba_api package). NBA.com data is subject to the [NBA.com Terms of Use](https://www.nba.com/news/termsofuse).
- **Restrictions on usage:** Commercial redistribution of raw NBA.com data is not permitted.
- **robots.txt position:** `stats.nba.com/robots.txt` redirects to `www.nba.com/stats/robots.txt`; no formal crawl-delay directive is published.
- **Politeness policy:** Minimum 750 ms between requests (community-tested Cloudflare threshold); browser-like User-Agent required; exponential backoff on 429 / timeout; cache all historical responses to avoid redundant calls.

## 6. Known quirks

- **Cloud IP blocking** - `stats.nba.com` actively blocks AWS EC2, Heroku, and DigitalOcean IP ranges; run ingestion jobs from a non-cloud IP or use a residential / datacenter proxy. `cdn.nba.com` (live endpoints) is less affected.
- **Endpoint deprecations** - `PlayByPlayV2` and `ScoreboardV2` return empty data for the 2025-26 season; use V3 equivalents. `BoxScoreTraditionalV2` is deprecated in favour of V3.
- **Dataset order bug** - Fixed in v1.11.2: nine V3 boxscore parsers previously returned datasets in the wrong order. Always run `>= 1.11.2`.
- **`LeagueID` must be explicit** - Pass `league_id="00"` (NBA) explicitly; an empty string has been rejected by NBA.com since approximately the 2023-24 season.
- **Schema instability** - NBA.com changes endpoint response fields without notice; field names and response structure have shifted across seasons.
- **Shot chart gaps** - `shotchartdetail` returns incomplete or obfuscated data for some games.
- **Stale user-agent** - v1.11.4 fixed a broken user-agent string that caused all requests to fail; always run the current release.

## 7. Failure modes

- **What breaks if this source is down or changes:** All `nba_api.stats` pipelines fail if `stats.nba.com` is down or changes its response schema; all `nba_api.live` pipelines fail if `cdn.nba.com` is unavailable. Silent schema drift (fields renamed or removed) can produce corrupted silver-layer data.
- **Detection:** Monitor for HTTP 403 / connection timeouts on ingestion runs; schema validation errors on parsed responses surface schema drift early.
- **Fallback / mitigation:** Historical data already ingested is preserved immutably in the S3 bronze layer and can be re-processed from source. Live endpoint outages require waiting for NBA.com recovery - no public mirror exists. Cache aggressively to minimise re-fetch exposure.
