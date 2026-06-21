# pro_sports_transactions

## 1. Identity

- **Name:** pro_sports_transactions
- **Version:** [`pro_sports_transactions`](https://pypi.org/project/pro_sports_transactions/) Python library (PyPI) wraps the site; no versioning on the site itself
- **URL:** [Site](https://www.prosportstransactions.com), [PyPI library](https://pypi.org/project/pro_sports_transactions/), [Library repository](https://github.com/rsforbes/pro_sports_transactions)
- **Owner / maintainer:** Pro Sports Transactions (site). Python library by [rsforbes](https://github.com/rsforbes) (same maintainer as `nba_api`).

## 2. Access pattern

- **Library / method used:** Web scraping of paginated HTML search results. Direct `requests` calls are blocked by Cloudflare; two practical approaches exist:

  **Option A - `pro_sports_transactions` library (recommended for simplicity):**
  Requires a separately running [Unflare](https://github.com/Zaczero/unflare) proxy service that bypasses Cloudflare on the library's behalf.

  ```python
  from pro_sports_transactions import ProSportsTransactionsAPI

  api = ProSportsTransactionsAPI()

  # Fetch NBA IL moves for a date range
  results = api.search(
      league="NBA",
      start_date="2024-01-01",
      end_date="2024-01-31",
      transaction_type="IL",  # IL, Movement, Disciplinary, etc.
  )
  # Returns list of dicts with Date, Team, Acquired, Relinquished, Notes
  ```

  **Option B - Manual scraping with Playwright:**

  ```python
  import time

  from playwright.sync_api import sync_playwright

  BASE_URL = (
      "https://www.prosportstransactions.com/basketball/Search/SearchResults.php"
      "?Player=&Team=&BeginDate={start}&EndDate={end}&ILChkBx=yes&Submit=Search"
      "&start={offset}"
  )

  with sync_playwright() as p:
      browser = p.chromium.launch(headless=True)
      page = browser.new_page()
      page.goto(BASE_URL.format(start="2024-01-01", end="2024-01-31", offset=0))
      html = page.content()
      time.sleep(1)
  ```

  Pagination: **25 rows per page**; advance with `&start=25`, `&start=50`, etc.

- **Authentication required:** None (public site). No API key. Cloudflare protection must be bypassed via Unflare (Option A) or a stealth browser (Option B).

- **Rate limits:** No officially published limit. Given Cloudflare enforcement and the all-rights-reserved terms, use **≥ 1 s between page requests** and avoid concurrent sessions.

## 3. Refresh cadence

- **How often upstream data changes:** Transaction entries are added as events occur during the season (typically within 24 hours of the official announcement). The site does not publish a formal update schedule.
- **How often we plan to ingest:** TBD - to be defined per pipeline.

## 4. Fields used

- **Pages consumed:**

  | Search filter | Transaction types covered | Example URL suffix |
  |---|---|---|
  | `ILChkBx=yes` | IL placements and activations | `&ILChkBx=yes` |
  | `InjuriesChkBx=yes` | Game-time injury designations | `&InjuriesChkBx=yes` |
  | `MovementChkBx=yes` | Trades, waivers, free agent signings, draft picks | `&MovementChkBx=yes` |
  | `DisciplinaryChkBx=yes` | Suspensions, fines | `&DisciplinaryChkBx=yes` |
  | `PersonalChkBx=yes` | Personal reasons (DNPs) | `&PersonalChkBx=yes` |
  | `LegalChkBx=yes` | Legal / criminal actions | `&LegalChkBx=yes` |

  Each result row returns: `Date`, `Team`, `Acquired` (player joining roster), `Relinquished` (player leaving roster), `Notes` (free-text description).

- **Specific fields / columns relied on:** TBD - to be filled as ingestion pipelines are implemented.

## 5. License / terms of use

- **License or terms:** No published terms of use page (the site's `/robots.txt` and terms pages returned HTTP 403 via Cloudflare at time of writing and could not be retrieved). The `pro_sports_transactions` PyPI library disclaimer states: "usage of all information obtained via the Pro Sports Transactions API is subject to all rights reserved by Pro Sports Transactions."
- **Restrictions on usage:** Treat as all-rights-reserved. Use for internal research only; do not republish or redistribute the raw transaction data.
- **robots.txt position:** Inaccessible - `https://www.prosportstransactions.com/robots.txt` returned HTTP 403 (Cloudflare blocks the request before serving the file). No crawl-delay directive could be verified. Apply a conservative ≥ 1 s between requests as the default politeness policy.
- **Politeness policy:** Minimum 1 s between requests; no concurrent scraping sessions; cache responses so historical date ranges are never re-fetched; run ingestion from a non-cloud IP where possible.

## 6. Known quirks

- **Cloudflare protection** - Direct `requests` calls return a Cloudflare JS challenge page rather than data, with no HTTP error code (silent failure). Always validate that the returned HTML contains the expected table before parsing.
- **Unreliable recovery dates** - Academic research using this dataset found reliable injury *placement* dates but inconsistent *return-to-play* dates. Cross-validate recovery dates against game logs or NBA.com official transactions.
- **25-row pagination** - Full historical backfills require iterating `start=0, 25, 50, ...` until a page returns fewer than 25 rows. An off-by-one in the cursor can cause the last partial page to be silently skipped.
- **Notes field is free text** - The `Notes` column contains unstructured natural language descriptions (e.g., "placed on IL with right knee soreness"). Parsing injury body parts or severity requires NLP post-processing; no controlled vocabulary is used.
- **No bulk export** - There is no CSV download or API endpoint; every date range must be fetched page-by-page.
- **Unflare dependency** - Option A (library) requires Unflare running as a local service. This adds an operational dependency that must be included in the ingestion environment setup.

## 7. Failure modes

- **What breaks if this source is down or changes:** All injury/transaction pipelines fail if the site is unreachable or if Cloudflare tightens its challenge. Silent HTML structure changes (table class names or column order altered) produce incorrect parses with no exception.
- **Detection:** Check that the parsed HTML contains the expected `<table>` element and that row count > 0 before inserting to bronze. Log a warning if Cloudflare challenge keywords (`cf-browser-verification`, `Just a moment`) appear in the response body.
- **Fallback / mitigation:** Historical transaction records already ingested are preserved immutably in the S3 bronze layer. There is no public mirror of this dataset; outages require waiting for site recovery. Cache all fetched pages so historical ranges never need re-scraping.
