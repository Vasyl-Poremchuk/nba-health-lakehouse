# basketball_reference

## 1. Identity

- **Name:** basketball_reference
- **Version:** N/A (website; no versioned API or package required)
- **URL:** [Site](https://www.basketball-reference.com), [About](https://www.basketball-reference.com/about/), [Terms](https://www.sports-reference.com/termsofuse.html), [Data use](https://www.sports-reference.com/data_use.html)
- **Owner / maintainer:** Sports Reference LLC ([sports-reference.com](https://www.sports-reference.com))

## 2. Access pattern

- **Library / method used:** No official API. Data is accessed by scraping HTML pages with `requests` + `BeautifulSoup` or `pandas.read_html`. A community wrapper, [`basketball-reference-scraper`](https://pypi.org/project/basketball-reference-scraper/), covers players, teams, seasons, box scores, play-by-play, shot charts, and injury reports.

  Typical URL patterns:

  | Resource | URL pattern |
  |---|---|
  | Player page | `https://www.basketball-reference.com/players/{letter}/{player_id}.html` |
  | Player game log | `https://www.basketball-reference.com/players/{letter}/{player_id}/gamelog/{season}/` |
  | Team season | `https://www.basketball-reference.com/teams/{TEAM}/{season}.html` |
  | Box score | `https://www.basketball-reference.com/boxscores/{game_id}.html` |
  | Injury report | `https://www.basketball-reference.com/friv/injuries.fcgi` |
  | Season stats | `https://www.basketball-reference.com/leagues/NBA_{season}_per_game.html` |

  ```python
  import time

  import pandas as pd
  import requests
  from bs4 import BeautifulSoup

  HEADERS = {
      "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
      "Referer": "https://www.basketball-reference.com/",
  }

  def fetch_page(url: str) -> BeautifulSoup:
      resp = requests.get(url, headers=HEADERS, timeout=15)
      resp.raise_for_status()

      return BeautifulSoup(resp.text, "html.parser")

  # Many tables are hidden in HTML comments; pd.read_html misses them.
  # Uncomment before parsing:
  def uncomment_tables(soup: BeautifulSoup) -> BeautifulSoup:
      from bs4 import Comment

      for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
          comment.replace_with(BeautifulSoup(comment, "html.parser"))

      return soup
  ```

- **Authentication required:** None. No API key. Requests must carry a realistic `User-Agent`; bare `python-requests` user-agents are likely to be blocked by Cloudflare.

- **Rate limits:** Sports Reference enforces **≤ 20 requests per minute** (FBref and Stathead: ≤ 10 req/min). Exceeding the limit locks the session for up to one day. The `robots.txt` specifies `Crawl-delay: 3`, so maintain at least 3 s between requests:

  ```python
  for url in page_urls:
      soup = fetch_page(url)
      process(soup)
      time.sleep(3)
  ```

  Sustained batch work should add exponential backoff on 429 / timeout responses.

## 3. Refresh cadence

- **How often upstream data changes:**
  - Season stats and game logs: updated post-game, typically within hours of game end.
  - Historical data (pre-current season): stable; changes only for retroactive corrections.
  - Injury report page: updated in near-real-time during the season.
  - Salary data: updated when transactions are finalized.
- **How often we plan to ingest:** TBD - to be defined per pipeline.

## 4. Fields used

- **Pages consumed:**

  | Page | Purpose | Docs |
  |---|---|---|
  | `per_game` season stats | League-wide per-game averages per player | [example](https://www.basketball-reference.com/leagues/NBA_2025_per_game.html) |
  | `advanced` season stats | PER, TS%, BPM, VORP, WS, USG%, etc. | [example](https://www.basketball-reference.com/leagues/NBA_2025_advanced.html) |
  | `injuries.fcgi` | Current injury designations | [link](https://www.basketball-reference.com/friv/injuries.fcgi) |
  | Player game log | Per-game box score for one player / season | [example](https://www.basketball-reference.com/players/j/jamesle01/gamelog/2025/) |
  | Box score | Full game box score (traditional) | [example](https://www.basketball-reference.com/boxscores/202406170BOS.html) |
  | Team schedule + results | Win/loss, travel, back-to-back detection | [example](https://www.basketball-reference.com/teams/BOS/2025_games.html) |
  | `draft/{year}.html` | Historical draft picks | [example](https://www.basketball-reference.com/draft/NBA_2024.html) |

- **Specific fields / columns relied on:** TBD - to be filled as ingestion pipelines are implemented.

## 5. License / terms of use

- **License or terms:** No open license. Data is proprietary to Sports Reference LLC and their third-party data providers. Use is governed by the [Sports Reference Terms of Use](https://www.sports-reference.com/termsofuse.html) and [data use policy](https://www.sports-reference.com/data_use.html).
- **Restrictions on usage:**
  - Automated scraping that "adversely impacts site performance or access" is prohibited.
  - Cannot create a database, archive, or tool that competes with Sports Reference or substitutes for its services.
  - Cannot use scraped data to train generative AI models without permission.
  - Bulk / custom data downloads: minimum $5,000 fee - use scraping for research-scale access only.
  - Most data originates from licensed third-party providers; wholesale redistribution is not permitted.
- **robots.txt position** (`https://www.basketball-reference.com/robots.txt`):
  - `Crawl-delay: 3`
  - Disallows (for `User-agent: *`): `/basketball/`, `/blazers/`, `/dump/`, `/fc/`, `/my/`, `/play-index/*.cgi?*`, `*/gamelog/`, `*/splits/`, `*/on-off/`, `*/lineups/`, `*/shooting/`, `/req/`, `/short/`, `/nocdn/`
  - `AhrefsBot` and `GPTBot` are fully blocked.
  - **Note:** The `gamelog`, `splits`, `lineups`, and `shooting` paths we rely on are listed as disallowed. This creates a legal / ethical tension; use conservatively, cache aggressively, and never hammer the site.
- **Politeness policy:** Minimum 3 s between requests (matching `Crawl-delay`); realistic browser `User-Agent`; exponential backoff on 429; cache all responses so historical pages are never re-fetched.

## 6. Known quirks

- **Commented-out tables** - Many stats tables are wrapped in HTML comments (`<!-- ... -->`) to discourage `pd.read_html`. You must extract and re-parse the comment text before the table is visible to BeautifulSoup or pandas. Forgetting this produces empty DataFrames with no error.
- **Cloud IP blocking** - Cloudflare CDN (added Oct 2022) actively filters bot traffic; AWS and other cloud IP ranges may receive JS challenges or silent drops. Run ingestion from a non-cloud IP.
- **Rate-limit session jail** - A 429 response locks the offending session for up to one day, not just the next few seconds. Build detection and a long backoff (15-60 min minimum) rather than a short retry loop.
- **Salary coverage gaps** - Historical salary data is incomplete for seasons before the mid-1990s and for some players who played outside the US.
- **Page structure drift** - HTML class names and table IDs change without notice across seasons; scrapers tied to specific selectors will break silently.
- **No bulk export** - There is no CSV export button or download endpoint; every table requires a separate HTTP request.

## 7. Failure modes

- **What breaks if this source is down or changes:** All Basketball-Reference pipelines fail if the site is unreachable. Silent HTML structure changes (table IDs renamed, columns reordered) produce corrupted or empty DataFrames without raising exceptions.
- **Detection:** Monitor for HTTP 403 (Cloudflare block), 429 (rate limit jail), or connection timeouts on ingestion runs. Add column-count and dtype assertions immediately after `read_html` / `find` calls to surface schema drift.
- **Fallback / mitigation:** Historical pages already ingested are preserved immutably in the S3 bronze layer. Sports Reference outages are typically short; retry after ≥ 1 hour. For schema drift, the raw HTML is in bronze so the parse layer can be reprocessed without re-scraping. Cache aggressively - most historical pages are fully static.
