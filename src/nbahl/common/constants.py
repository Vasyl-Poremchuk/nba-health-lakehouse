from pathlib import Path


class BaseConstants:
    """Project-wide constants: filesystem paths and NBA API request headers.

    Attributes:
        PROJECT_ROOT: Root of the repository (four levels up from this file).
        DATA_DIR: Local directory where ingested Parquet files are written.
        HEADERS: Tuple of browser-mimicking HTTP header dicts rotated on each
            NBA Stats API request to reduce rate-limiting.
        SLEEP_SECONDS: Seconds to wait between consecutive NBA Stats API
            requests to avoid rate-limiting.
        INTERVAL_MINS: Minutes between scheduled ingestion runs.
        MAX_TOTAL_GAME_FAILURE_NUMBER: Maximum number of individual game fetch
            failures tolerated across a full season run before aborting.
    """

    PROJECT_ROOT = Path(__file__).parents[3]
    DATA_DIR = PROJECT_ROOT.joinpath("data")
    HEADERS = (
        {
            "Host": "stats.nba.com",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Origin": "https://stats.nba.com",
            "Referer": "https://stats.nba.com/",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "Sec-Ch-Ua": '"Not:A-Brand";v="99", "Google Chrome";v="130", "Chromium";v="130"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Fetch-Dest": "empty",
        },
        {
            "Host": "stats.nba.com",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0_0) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/18.0 Safari/605.1.15",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Origin": "https://stats.nba.com",
            "Referer": "https://stats.nba.com/",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "Sec-Fetch-Dest": "empty",
        },
        {
            "Host": "stats.nba.com",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/129.0.6668.71 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Origin": "https://stats.nba.com",
            "Referer": "https://stats.nba.com/",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "Sec-Ch-Ua": '"Not:A-Brand";v="99", "Google Chrome";v="129", "Chromium";v="129"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Fetch-Dest": "empty",
        },
        {
            "Host": "stats.nba.com",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone "
            "OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Origin": "https://stats.nba.com",
            "Referer": "https://stats.nba.com/",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "Sec-Fetch-Dest": "empty",
        },
        {
            "Host": "stats.nba.com",
            "User-Agent": "Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.4 Mobile/15E148 Safari/604.1",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Origin": "https://stats.nba.com",
            "Referer": "https://stats.nba.com/",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "Sec-Fetch-Dest": "empty",
        },
        {
            "Host": "stats.nba.com",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; "
            "x64; rv:131.0) Gecko/20100101 Firefox/131.0",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Origin": "https://stats.nba.com",
            "Referer": "https://stats.nba.com/",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "Sec-Fetch-Dest": "empty",
        },
        {
            "Host": "stats.nba.com",
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; SM-G998B) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/129.0.6668.89 Mobile Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Origin": "https://stats.nba.com",
            "Referer": "https://stats.nba.com/",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "Sec-Ch-Ua": '"Not:A-Brand";v="99", "Google Chrome";v="129", "Chromium";v="129"',
            "Sec-Ch-Ua-Mobile": "?1",
            "Sec-Fetch-Dest": "empty",
        },
        {
            "Host": "stats.nba.com",
            "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:132.0) "
            "Gecko/20100101 Firefox/132.0",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Origin": "https://stats.nba.com",
            "Referer": "https://stats.nba.com/",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "Sec-Fetch-Dest": "empty",
        },
        {
            "Host": "stats.nba.com",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_1) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.6613.120 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Origin": "https://stats.nba.com",
            "Referer": "https://stats.nba.com/",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "Sec-Ch-Ua": '"Not:A-Brand";v="99", "Google Chrome";v="128", "Chromium";v="128"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Fetch-Dest": "empty",
        },
        {
            "Host": "stats.nba.com",
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/127.0.6533.72 Mobile Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Origin": "https://stats.nba.com",
            "Referer": "https://stats.nba.com/",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "Sec-Ch-Ua": '"Not:A-Brand";v="99", "Google Chrome";v="127", "Chromium";v="127"',
            "Sec-Ch-Ua-Mobile": "?1",
            "Sec-Fetch-Dest": "empty",
        },
    )
    SLEEP_SECONDS = 0.75
    INTERVAL_MINS = 10
    MAX_TOTAL_GAME_FAILURE_NUMBER = 10


class GameLogNBAApiSourceConstants:
    """Constants for the league game log NBA API source.

    Attributes:
        SOURCE_NAME_PREFIX: Leading segment of the logical source name used to
            construct Parquet filenames and S3 keys.
    """

    SOURCE_NAME_PREFIX = "league-game-logs"


class PlayByPlayNBAApiSourceConstants:
    """Constants for the play-by-play NBA API source.

    Attributes:
        SOURCE_NAME_PREFIX: Leading segment of the logical source name used to
            construct Parquet filenames and S3 keys.
    """

    SOURCE_NAME_PREFIX = "play-by-play-logs"
