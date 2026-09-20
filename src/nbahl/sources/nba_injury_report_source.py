import random
import re
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from functools import partial
from itertools import zip_longest
from pathlib import Path

import pandas as pd
import pdfplumber
import requests
import structlog
from pdfplumber.page import Page

from nbahl.common.constants import (
    BaseConstants,
    NBAInjuryReportSourceConstants,
)
from nbahl.common.enums import DirType
from nbahl.common.exceptions import (
    ColumnNotFoundError,
    DataFrameEmptyError,
    NoTableError,
)
from nbahl.common.models import IngestionContext
from nbahl.common.retry import nba_api_retry
from nbahl.common.utils import get_s3_key, save_to_pdf
from nbahl.config import Settings
from nbahl.pipelines import reconcile, run_ingestion, run_raw_ingestion
from nbahl.writers.db_writer import DBWriter
from nbahl.writers.s3_writer import S3Writer

log = structlog.get_logger()


class NBAInjuryReportSource:
    """Fetches and parses NBA injury report PDFs into a structured DataFrame.

    Args:
        year: Season year to fetch and parse reports for.
        frequency: Pandas offset alias for report time slots. Use ``"1h"``
            for years up to and including early 2025, and ``"15min"`` for
            late 2025 and later.
        date_format: strftime format matching the PDF filename timestamps.
            Use ``"%Y-%m-%d_%I%p"`` for years up to and including early
            2025, and ``"%Y-%m-%d_%I_%M%p"`` for late 2025 and later.
        _start: ISO date string for January 1st of ``year``
            (``"YYYY-01-01"``). Derived from ``year`` in ``__init__``.
        _end: ISO date string for December 31st of ``year``
            (``"YYYY-12-31"``). Derived from ``year`` in ``__init__``.

    2025 itself uses both formats because the NBA switched from hourly to
    15-minute reporting mid-season.
    """

    def __init__(self, year: int, frequency: str, date_format: str) -> None:
        self.year = year
        self.frequency = frequency
        self.date_format = date_format
        self._start = f"{self.year}-01-01"
        self._end = f"{self.year}-12-31"

    def _build_date_range(self) -> list[str]:
        """Build the list of formatted date strings for the season, skipping
        off-season months.

        Returns:
            List of date strings formatted with ``self.date_format``, one per
            time slot, excluding July through September.
        """
        date_range = [
            date_point.strftime(format=self.date_format)
            for date_point in pd.date_range(
                start=self._start, end=self._end, freq=self.frequency
            )
            if not (7 <= date_point.month <= 9)
            and date_point <= datetime.now()
        ]

        return date_range

    def _build_injury_report_urls(self) -> list[str]:
        """Build the list of PDF URLs for every time slot in the season date
        range.

        Returns:
            List of fully qualified PDF URLs, one per date string from
            ``_build_date_range``.
        """
        injury_report_urls = [
            f"{NBAInjuryReportSourceConstants.BASE_URL}"
            f"/{NBAInjuryReportSourceConstants.FILENAME_SUFFIX}{date_point}.pdf"
            for date_point in self._build_date_range()
        ]

        return injury_report_urls

    def get_base_dir(self, dir_type: DirType) -> Path:
        """Return the base directory for raw or parsed injury report files for
        the configured year.

        Args:
            dir_type: ``DirType.RAW`` for downloaded PDFs or ``DirType.PARSED``
                for the output Parquet file.

        Returns:
            Path of the form ``DATA_DIR/injuries/<year>/<dir_type>``.
        """
        base_dir = BaseConstants.DATA_DIR.joinpath(
            NBAInjuryReportSourceConstants.SOURCE_DIR, str(self.year), dir_type
        )

        return base_dir

    def _build_raw_filepath(self, url: str, dir_type: DirType) -> Path:
        """Derive the local file path for a PDF from its URL and the target
        directory type.

        Args:
            url: Full URL of the PDF; the filename is extracted from the last
                path segment.
            dir_type: Directory tier under which the file will be stored.

        Returns:
            Absolute path of the form ``<base_dir>/<filename>``.
        """
        _, filename = url.rsplit("/", maxsplit=1)
        base_dir = self.get_base_dir(dir_type=dir_type)

        raw_filepath = base_dir.joinpath(filename)

        return raw_filepath

    @staticmethod
    def _build_headers() -> dict[str, str]:
        """Build a randomised browser-mimicking header dict for the NBA injury
        report request.

        Returns:
            Dict with ``User-Agent`` (randomly chosen from ``BaseConstants.HEADERS``)
            and ``Referer`` set to ``"https://www.nba.com/"``.
        """
        user_agent = random.choice(BaseConstants.HEADERS)["User-Agent"]
        headers = {
            "User-Agent": user_agent,
            "Referer": NBAInjuryReportSourceConstants.REFERER,
        }

        return headers

    @nba_api_retry(logger=log)
    def fetch_injury_report(self, url: str, filepath: Path) -> None:
        """Fetch a single injury report PDF from the given URL and write it to
        disk.

        Args:
            url: Full URL of the PDF to download.
            filepath: Local path where the PDF will be saved.

        Raises:
            requests.exceptions.HTTPError: Raised for HTTP errors not covered by
                the retry policy (i.e. status codes other than 408, 429, 500,
                502, 503, or 504), or re-raised after retries are exhausted.
        """
        response = requests.get(
            url=url, headers=self._build_headers(), timeout=30
        )
        response.raise_for_status()

        filepath.parent.mkdir(parents=True, exist_ok=True)
        save_to_pdf(filepath=filepath, content=response.content)
        log.info("Saved injury report", url=url)

    def fetch_injury_reports(self) -> None:
        """Fetch all injury report PDFs for the configured year, skipping
        missing time slots.

        Raises:
            requests.exceptions.HTTPError: Re-raised for any HTTP error that is
                not a 403 or 404 (those indicate no report exists for that slot
                and are silently skipped).
        """
        urls = self._build_injury_report_urls()
        log.info("Starting fetching", total_urls=len(urls))

        for url in urls:
            try:
                self.fetch_injury_report(
                    url=url,
                    filepath=self._build_raw_filepath(
                        url=url, dir_type=DirType.RAW
                    ),
                )
            except requests.exceptions.HTTPError as exc:
                if isinstance(
                    exc.response, requests.Response
                ) and exc.response.status_code in (403, 404):
                    log.debug(
                        "Skipping URL, no report available",
                        url=url,
                        status_code=exc.response.status_code,
                    )
                    continue

                raise exc

        log.info("Completed fetching")

    def extract_columns(self, page: Page) -> list[str]:
        """Extract the column header names from the table on the given PDF
        page.

        Args:
            page: A pdfplumber Page object to extract the table from.

        Returns:
            List of column header strings, with any header containing ``"/"``
            filtered out.

        Raises:
            NoTableError: If no table is detected on the page.
        """
        table = page.extract_table()

        if table is None:
            raise NoTableError(
                f"There is no table on the page: {page.page_number}"
            )

        columns = [
            column
            for column in table[0]
            if isinstance(column, str) and "/" not in column
        ]

        return columns

    @staticmethod
    def extract_column_positions(
        words: list[dict[str, str | float]], columns: list[str]
    ) -> dict[str, float]:
        """Map each column header name to the x0 coordinate of its leftmost
        word on the page.

        Args:
            words: Ordered list of word dicts extracted by pdfplumber.
            columns: Column header names to locate.

        Returns:
            Mapping of column name to its x0 position (adjusted by COLUMN_LEFT_OFFSET).
        """
        column_positions = {}

        for current_word, next_word in zip_longest(words, words[1:]):
            for column in columns:
                current_text = str(current_word["text"])
                next_text = str(next_word["text"])
                is_column = column.startswith(
                    current_text
                ) and column.endswith(next_text)

                if (
                    current_text == column or is_column
                ) and column not in column_positions:
                    column_positions[column] = (
                        float(current_word["x0"])
                        - NBAInjuryReportSourceConstants.COLUMN_LEFT_OFFSET
                    )
                    break

            if set(columns) == set(column_positions):
                break

        return column_positions

    @staticmethod
    def get_columns_range(
        column_positions: dict[str, float], columns: list[str]
    ) -> dict[str, tuple[float, float]]:
        """Compute the (left_x0, right_x0) bounding range for each column.

        The right boundary of each column is the left boundary of the next column.
        The last column's right boundary is its x0 plus LAST_COLUMN_WIDTH.

        Args:
            column_positions: Mapping of column name to its x0 position.
            columns: Column names in left-to-right order.

        Returns:
            Mapping of column name to its (left_x0, right_x0) range.
        """
        columns_range = {}

        for left_column, right_column in zip_longest(
            columns, columns[1:], fillvalue="last_column_stop"
        ):
            left_x0 = column_positions[left_column]

            if right_column != "last_column_stop":
                right_x0 = column_positions[right_column]
            else:
                right_x0 = (
                    left_x0 + NBAInjuryReportSourceConstants.LAST_COLUMN_WIDTH
                )

            columns_range[left_column] = left_x0, right_x0

        return columns_range

    def get_horizontal_line_coordinates(self, page: Page) -> list[float]:
        """Return a sorted list of unique bottom-y coordinates for all
        horizontal lines on the page.

        Args:
            page: A pdfplumber Page object whose ``lines`` attribute is inspected.

        Returns:
            Deduplicated, ascending list of ``bottom`` y-coordinates from all
            horizontal lines on the page.
        """
        horizontal_line_coordinates = []

        for line in page.lines:
            bottom = line["bottom"]

            if bottom not in horizontal_line_coordinates:
                horizontal_line_coordinates.append(bottom)

        return sorted(horizontal_line_coordinates)

    @staticmethod
    def is_column(text: str, columns: list[str]) -> bool:
        """Return True if text matches the start or end of any known column
        header name.

        Args:
            text: A single word extracted from the PDF page.
            columns: List of full column header strings to match against.

        Returns:
            ``True`` if any column header starts or ends with ``text``,
            ``False`` otherwise.
        """
        is_true = any(
            column.startswith(text) or column.endswith(text)
            for column in columns
        )

        return is_true

    def group_words(
        self,
        words: list[dict[str, str | float]],
        columns: list[str],
        horizontal_line_coordinates: list[float],
    ) -> dict[float, list[dict[str, str | float]]]:
        """Group data words by the horizontal line (row boundary) they fall
        above.

        Column header words are excluded. Each word is assigned to the first
        horizontal line whose bottom-y is >= the word's bottom-y.

        Args:
            words: All words extracted from the page.
            columns: Column header names to skip.
            horizontal_line_coordinates: Sorted list of line bottom-y coordinates.

        Returns:
            Mapping of line bottom-y to the list of words in that row.
        """
        grouped_words: dict[float, list[dict[str, str | float]]] = {}

        for word in words[NBAInjuryReportSourceConstants.FIRST_COLUMN_INDEX :]:
            text = str(word["text"])

            if text in columns or self.is_column(text=text, columns=columns):
                continue

            for line in horizontal_line_coordinates:
                if float(word["bottom"]) <= line:
                    grouped_words.setdefault(line, []).append(word)
                    break

        return grouped_words

    @staticmethod
    def build_row(
        row: dict[str, list[str]], columns: list[str]
    ) -> dict[str, str | None]:
        """Build a finalized row dict by joining accumulated word lists into
        strings.

        Words for each column are joined with spaces and stripped. An empty result
        or a column with no words mapped to it is represented as None.

        Args:
            row: Mapping of column name to the list of word strings collected for it.
            columns: Full column list, used to fill in None for columns with no words.

        Returns:
            Mapping of column name to its string value, or None if no words were found.
        """
        updated_row: dict[str, str | None] = {}

        for column, substrings in row.items():
            value = " ".join(substrings).strip()

            updated_row[column] = value if value else None

        updated_row.update(
            {column: None for column in columns if column not in row}
        )

        return updated_row

    def parse_injury_report(self, filepath: Path) -> pd.DataFrame:
        """Parse a single injury report PDF into a DataFrame.

        Extracts all player rows across all pages, attaches a reported_at
        timestamp from the PDF header, and normalises column names.

        Args:
            filepath: Path to the local PDF file.

        Returns:
            DataFrame with one row per player entry, a ``reported_at`` column
            derived from the PDF header, and snake_case column names.

        Raises:
            NoTableError: If a page contains no detectable table.
            ColumnNotFoundError: If a word's x-position falls outside every
                known column's bounding range.
            DataFrameEmptyError: If the PDF yields no data rows.
        """
        columns = None
        reported_at = None
        column_positions = None
        columns_range = None
        rows = []

        reported_at_slice = slice(
            NBAInjuryReportSourceConstants.INJURY_REPORT_HEADER_INDEX,
            NBAInjuryReportSourceConstants.FIRST_COLUMN_INDEX,
        )

        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                horizontal_line_coordinates = (
                    self.get_horizontal_line_coordinates(page=page)
                )
                words = page.extract_words()

                if columns is None:
                    columns = self.extract_columns(page=page)

                grouped_words = self.group_words(
                    words=words,
                    horizontal_line_coordinates=horizontal_line_coordinates,
                    columns=columns,
                )

                if reported_at is None:
                    reported_at = " ".join(
                        word["text"] for word in words[reported_at_slice]
                    )

                if column_positions is None and columns_range is None:
                    column_positions = self.extract_column_positions(
                        words=words, columns=columns
                    )
                    columns_range = self.get_columns_range(
                        column_positions=column_positions, columns=columns
                    )

                for words_group in grouped_words.values():
                    row: dict[str, list[str]] = {}

                    for word in words_group:
                        text = str(word["text"])

                        if self.is_column(text=text, columns=columns):
                            continue

                        for column in columns:
                            x0 = float(word["x0"])
                            x1 = float(word["x1"])

                            if isinstance(
                                columns_range, dict
                            ) and not columns_range.get(column):
                                raise ColumnNotFoundError(
                                    f"{column!r} column not found, columns: {list(columns_range)}"
                                )

                            left_x0, right_x0 = columns_range[column]  # type: ignore[index]

                            if x0 >= left_x0 and x1 <= right_x0:
                                row.setdefault(column, []).append(text)

                    built_row = self.build_row(row=row, columns=columns)
                    rows.append(built_row)

        injury_report_df = pd.DataFrame(data=rows)

        if injury_report_df.empty:
            raise DataFrameEmptyError(
                f"No data could be extracted from: {filepath}"
            )

        injury_report_df["reported_at"] = reported_at
        injury_report_df = self.normalize_columns(df=injury_report_df)

        return injury_report_df

    @staticmethod
    def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Normalize DataFrame column names to snake_case, splitting on
        whitespace and camelCase boundaries.

        Args:
            df: DataFrame whose column names should be normalized.

        Returns:
            The same DataFrame with column names converted to lowercase
            snake_case (e.g. ``"CurrentStatus"`` -> ``"current_status"``).
        """
        normalized_columns = [
            "_".join(
                re.split(r"\s", re.sub(r"(\w)([A-Z])", r"\1 \2", column))
            ).lower()
            for column in df.columns
        ]

        df.columns = normalized_columns

        return df

    def get_raw_filepaths(self) -> list[Path]:
        """Return all PDF file paths found recursively under the raw directory
        for this year.

        Returns:
            List of ``Path`` objects matching ``*.pdf`` under
            ``get_base_dir(DirType.RAW)``; empty when no files exist yet.
        """
        base_dir = self.get_base_dir(dir_type=DirType.RAW)
        raw_filepaths = list(base_dir.rglob("*.pdf"))

        return raw_filepaths

    def parse_injury_reports(self, raw_filepaths: list[Path]) -> pd.DataFrame:
        """Parse all raw injury report PDFs in parallel and return a combined
        DataFrame.

        Args:
            raw_filepaths: List of local PDF paths to parse.

        Returns:
            Concatenated DataFrame of all parsed injury report rows.
        """
        log.info(
            "Parsing injury reports started",
            total_injury_reports=len(raw_filepaths),
        )

        with ProcessPoolExecutor() as executor:
            injury_reports = executor.map(
                self.parse_injury_report, raw_filepaths
            )

        injury_reports_df = pd.concat(objs=injury_reports)

        log.info("Parsing injury reports completed")

        return injury_reports_df


def ingest_injury_reports(
    year: int,
    frequency: str,
    date_format: str,
    db_writer: DBWriter,
    s3_writer: S3Writer,
) -> None:
    """Fetch, parse, and ingest NBA injury reports for the given year into S3
    and the database.

    Runs two sequential ingestion stages. Stage 1 (``run_raw_ingestion``)
    downloads all PDF files for the season and bulk-uploads them to S3 as raw
    files. Stage 2 (``run_ingestion``) parses the downloaded PDFs into a single
    DataFrame, writes it as a Parquet file, and uploads it to S3. A
    ``reconcile`` call in the ``finally`` block always runs regardless of
    outcome to resolve any stale ``PENDING`` records left by a mid-flight crash.

    Args:
        year: Season year to fetch and ingest.
        frequency: Pandas offset alias for the report time slots
            (e.g. ``"1h"`` or ``"15min"``).
        date_format: strftime format matching the PDF filename timestamps.
        db_writer: Writer used to record ingestion run metadata.
        s3_writer: Writer used to upload raw PDFs and the parsed Parquet file.
    """
    source = NBAInjuryReportSource(
        year=year, frequency=frequency, date_format=date_format
    )

    try:
        run_raw_ingestion(
            source=source, db_writer=db_writer, s3_writer=s3_writer
        )

        filepath = source.get_base_dir(dir_type=DirType.PARSED).joinpath(
            f"{NBAInjuryReportSourceConstants.SOURCE_NAME}.parquet"
        )
        s3_key = get_s3_key(filepath=filepath, num_trailing_parts=4)
        context = IngestionContext(
            source_name=NBAInjuryReportSourceConstants.SOURCE_NAME,
            s3_key=s3_key,
            season=str(year),
            filepath=filepath,
            fetch_function=partial(
                source.parse_injury_reports,
                raw_filepaths=source.get_raw_filepaths(),
            ),
        )
        run_ingestion(
            context=context, db_writer=db_writer, s3_writer=s3_writer
        )
    finally:
        reconcile(db_writer=db_writer, s3_writer=s3_writer)


if __name__ == "__main__":
    settings = Settings()
    db_writer = DBWriter(settings=settings)
    db_writer.create_table()
    ingest_injury_reports(
        year=2026,
        frequency="15min",
        date_format="%Y-%m-%d_%I_%M%p",
        db_writer=db_writer,
        s3_writer=S3Writer(
            bucket=f"nbahl-bronze-{settings.nbahl_env}",
            profile_name=settings.profile_name.get_secret_value(),
        ),
    )
