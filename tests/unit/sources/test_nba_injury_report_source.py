from math import isnan
from pathlib import Path

import pandas as pd
import pytest
import requests
from pytest_mock import MockerFixture

from nbahl.common.constants import NBAInjuryReportSourceConstants
from nbahl.common.exceptions import (
    ColumnNotFoundError,
    DataFrameEmptyError,
    NoTableError,
)
from nbahl.sources.nba_injury_report_source import (
    NBAInjuryReportSource,
    ingest_injury_reports,
)
from nbahl.writers.db_writer import DBWriter
from nbahl.writers.s3_writer import S3Writer


def _make_http_error(status_code: int) -> requests.exceptions.HTTPError:
    """Build a ``requests.HTTPError`` with a real ``Response`` object attached.

    Args:
        status_code: HTTP status code to assign to the attached response.

    Returns:
        An ``HTTPError`` whose ``response.status_code`` equals ``status_code``
        and whose ``response`` passes ``isinstance(..., requests.Response)``,
        satisfying the retry-policy and skip-logic checks in the source.
    """
    response = requests.Response()
    response.status_code = status_code

    return requests.exceptions.HTTPError(response=response)


def test_parse_injury_report_success(
    nba_injury_report_source: NBAInjuryReportSource,
    injury_report_filepath: Path,
) -> None:
    injury_report_df = nba_injury_report_source.parse_injury_report(
        filepath=injury_report_filepath
    )

    assert len(injury_report_df) == 2
    assert set(injury_report_df.columns) == {
        "game_date",
        "game_time",
        "matchup",
        "team",
        "player_name",
        "current_status",
        "reason",
        "reported_at",
    }
    assert injury_report_df.iloc[0]["game_date"] == "06/13/2026"
    assert injury_report_df.iloc[0]["game_time"] == "08:30(ET)"
    assert injury_report_df.iloc[0]["matchup"] == "NYK@SAS"
    assert injury_report_df.iloc[0]["team"] == "NewYorkKnicks"
    assert injury_report_df.iloc[0]["player_name"] == "Robinson,Mitchell"
    assert injury_report_df.iloc[0]["current_status"] == "Available"
    assert (
        injury_report_df.iloc[0]["reason"]
        == "Injury/Illness-RightHand;Fractured Right5thMetacarpal"
    )
    assert injury_report_df.iloc[0]["reported_at"] == "06/13/26 12:45 PM"
    assert isnan(injury_report_df.iloc[1]["game_date"])
    assert isnan(injury_report_df.iloc[1]["game_time"])
    assert isnan(injury_report_df.iloc[1]["matchup"])
    assert injury_report_df.iloc[1]["team"] == "SanAntonioSpurs"
    assert injury_report_df.iloc[1]["player_name"] == "Kornet,Luke"
    assert injury_report_df.iloc[1]["current_status"] == "Questionable"
    assert injury_report_df.iloc[1]["reason"] == 'Injury/Illness-"";Illness'
    assert injury_report_df.iloc[1]["reported_at"] == "06/13/26 12:45 PM"


def test_parse_injury_report_raises_no_table_error(
    mocker: MockerFixture,
    nba_injury_report_source: NBAInjuryReportSource,
    injury_report_filepath: Path,
) -> None:
    mocker.patch.object(
        nba_injury_report_source,
        "extract_columns",
        side_effect=NoTableError("There is no table on the page: 1"),
    )

    with pytest.raises(NoTableError, match="There is no table on the page: 1"):
        nba_injury_report_source.parse_injury_report(
            filepath=injury_report_filepath
        )


def test_parse_injury_report_raises_column_not_found_error(
    mocker: MockerFixture,
    nba_injury_report_source: NBAInjuryReportSource,
    injury_report_filepath: Path,
) -> None:
    mocker.patch.object(
        NBAInjuryReportSource,
        "get_columns_range",
        return_value={},
    )

    with pytest.raises(ColumnNotFoundError):
        nba_injury_report_source.parse_injury_report(
            filepath=injury_report_filepath
        )


def test_parse_injury_report_raises_dataframe_empty_error(
    mocker: MockerFixture,
    nba_injury_report_source: NBAInjuryReportSource,
    injury_report_filepath: Path,
) -> None:
    mocker.patch.object(
        nba_injury_report_source,
        "group_words",
        return_value={},
    )

    with pytest.raises(DataFrameEmptyError):
        nba_injury_report_source.parse_injury_report(
            filepath=injury_report_filepath
        )


def test_extract_columns_filters_slash_headers(
    mocker: MockerFixture,
    nba_injury_report_source: NBAInjuryReportSource,
) -> None:
    mock_page = mocker.MagicMock()
    mock_page.extract_table.return_value = [
        ["Game/Date", "Team", "Player Name", None],
        ["06/13/2026", "NYK", "Robinson", None],
    ]

    columns = nba_injury_report_source.extract_columns(page=mock_page)

    assert "Game/Date" not in columns
    assert None not in columns
    assert "Team" in columns
    assert "Player Name" in columns


def test_extract_columns_raises_no_table_error(
    mocker: MockerFixture,
    nba_injury_report_source: NBAInjuryReportSource,
) -> None:
    mock_page = mocker.MagicMock()
    mock_page.page_number = 1
    mock_page.extract_table.return_value = None

    with pytest.raises(NoTableError, match="page: 1"):
        nba_injury_report_source.extract_columns(page=mock_page)


@pytest.mark.parametrize(
    "words, columns, expected_column, expected_x0",
    [
        (
            [
                {"text": "Team", "x0": 100.0, "x1": 130.0, "bottom": 20.0},
                {"text": "Player", "x0": 200.0, "x1": 250.0, "bottom": 20.0},
            ],
            ["Team"],
            "Team",
            100.0 - NBAInjuryReportSourceConstants.COLUMN_LEFT_OFFSET,
        ),
        (
            [
                {"text": "Current", "x0": 300.0, "x1": 345.0, "bottom": 20.0},
                {"text": "Status", "x0": 347.0, "x1": 385.0, "bottom": 20.0},
            ],
            ["Current Status"],
            "Current Status",
            300.0 - NBAInjuryReportSourceConstants.COLUMN_LEFT_OFFSET,
        ),
    ],
)
def test_extract_column_positions(
    words: list[dict],
    columns: list[str],
    expected_column: str,
    expected_x0: float,
) -> None:
    result = NBAInjuryReportSource.extract_column_positions(
        words=words, columns=columns
    )

    assert result[expected_column] == expected_x0


def test_get_columns_range_interior_columns() -> None:
    columns = ["Team", "Player", "Status"]
    column_positions = {"Team": 10.0, "Player": 100.0, "Status": 200.0}

    result = NBAInjuryReportSource.get_columns_range(
        column_positions=column_positions, columns=columns
    )

    assert result["Team"] == (10.0, 100.0)
    assert result["Player"] == (100.0, 200.0)


def test_get_columns_range_last_column() -> None:
    columns = ["Team", "Status"]
    column_positions = {"Team": 10.0, "Status": 200.0}

    result = NBAInjuryReportSource.get_columns_range(
        column_positions=column_positions, columns=columns
    )

    assert result["Status"] == (
        200.0,
        200.0 + NBAInjuryReportSourceConstants.LAST_COLUMN_WIDTH,
    )


def test_build_row_joins_words() -> None:
    row = {"Team": ["San", "Antonio"]}
    columns = ["Team", "Player"]

    result = NBAInjuryReportSource.build_row(row=row, columns=columns)

    assert result["Team"] == "San Antonio"


def test_build_row_fills_missing_columns_with_none() -> None:
    row: dict[str, list[str]] = {}
    columns = ["Team", "Player"]

    result = NBAInjuryReportSource.build_row(row=row, columns=columns)

    assert result["Team"] is None
    assert result["Player"] is None


def test_group_words_assigns_to_correct_bucket(
    nba_injury_report_source: NBAInjuryReportSource,
) -> None:
    # First FIRST_COLUMN_INDEX (5) words are skipped; data words start at index 5.
    header_words = [
        {"text": f"header{i}", "x0": 0.0, "x1": 10.0, "bottom": 5.0}
        for i in range(NBAInjuryReportSourceConstants.FIRST_COLUMN_INDEX)
    ]
    data_words = [
        {"text": "NYK", "x0": 50.0, "x1": 80.0, "bottom": 30.0},
        {"text": "Robinson", "x0": 100.0, "x1": 160.0, "bottom": 60.0},
    ]
    words = header_words + data_words
    columns = ["SomeOtherColumn"]
    horizontal_line_coordinates = [40.0, 70.0, 100.0]

    result = nba_injury_report_source.group_words(
        words=words,
        columns=columns,
        horizontal_line_coordinates=horizontal_line_coordinates,
    )

    assert 40.0 in result
    assert result[40.0][0]["text"] == "NYK"
    assert 70.0 in result
    assert result[70.0][0]["text"] == "Robinson"


def test_group_words_excludes_column_headers(
    nba_injury_report_source: NBAInjuryReportSource,
) -> None:
    header_words = [
        {"text": f"header{i}", "x0": 0.0, "x1": 10.0, "bottom": 5.0}
        for i in range(NBAInjuryReportSourceConstants.FIRST_COLUMN_INDEX)
    ]
    data_words = [
        {"text": "Team", "x0": 50.0, "x1": 80.0, "bottom": 30.0},
        {"text": "NYK", "x0": 50.0, "x1": 80.0, "bottom": 30.0},
    ]
    words = header_words + data_words
    columns = ["Team"]
    horizontal_line_coordinates = [40.0]

    result = nba_injury_report_source.group_words(
        words=words,
        columns=columns,
        horizontal_line_coordinates=horizontal_line_coordinates,
    )

    texts_in_bucket = [w["text"] for w in result.get(40.0, [])]
    assert "Team" not in texts_in_bucket
    assert "NYK" in texts_in_bucket


@pytest.mark.parametrize(
    "text, columns, expected",
    [
        ("Current", ["Current Status"], True),
        ("Status", ["Current Status"], True),
        ("NYK", ["Current Status", "Team"], False),
    ],
)
def test_is_column(text: str, columns: list[str], expected: bool) -> None:
    assert (
        NBAInjuryReportSource.is_column(text=text, columns=columns) is expected
    )


@pytest.mark.parametrize(
    "input_col, expected_col",
    [
        ("CurrentStatus", "current_status"),
        ("Game Date", "game_date"),
    ],
)
def test_normalize_columns(input_col: str, expected_col: str) -> None:
    df = pd.DataFrame(columns=[input_col])

    result = NBAInjuryReportSource.normalize_columns(df=df)

    assert list(result.columns) == [expected_col]


def test_build_date_range_excludes_off_season_months(
    nba_injury_report_source: NBAInjuryReportSource,
) -> None:
    date_range = nba_injury_report_source._build_date_range()

    months = {int(date_str[5:7]) for date_str in date_range}

    assert 7 not in months
    assert 8 not in months
    assert 9 not in months


def test_build_date_range_includes_season_months(
    nba_injury_report_source: NBAInjuryReportSource,
) -> None:
    date_range = nba_injury_report_source._build_date_range()

    months = {int(date_str[5:7]) for date_str in date_range}

    assert 10 in months
    assert 6 in months


def test_build_injury_report_urls_format(
    nba_injury_report_source: NBAInjuryReportSource,
) -> None:
    urls = nba_injury_report_source._build_injury_report_urls()

    assert len(urls) > 0
    for url in urls:
        assert url.startswith(NBAInjuryReportSourceConstants.BASE_URL)
        assert NBAInjuryReportSourceConstants.FILENAME_SUFFIX in url
        assert url.endswith(".pdf")


def test_get_horizontal_line_coordinates(
    mocker: MockerFixture,
    nba_injury_report_source: NBAInjuryReportSource,
) -> None:
    mock_page = mocker.MagicMock()
    mock_page.lines = [
        {"bottom": 50.0},
        {"bottom": 20.0},
        {"bottom": 50.0},
        {"bottom": 80.0},
    ]

    result = nba_injury_report_source.get_horizontal_line_coordinates(
        page=mock_page
    )

    assert result == [20.0, 50.0, 80.0]


def test_fetch_injury_report_success_on_first_attempt(
    mocker: MockerFixture,
    nba_injury_report_source: NBAInjuryReportSource,
    tmp_path: Path,
) -> None:
    mock_get = mocker.patch(
        "nbahl.sources.nba_injury_report_source.requests.get"
    )
    mocker.patch("nbahl.sources.nba_injury_report_source.save_to_pdf")

    nba_injury_report_source.fetch_injury_report(
        url="https://example.com/test.pdf",
        filepath=tmp_path / "test.pdf",
    )

    mock_get.assert_called_once()
    mock_get.return_value.raise_for_status.assert_called_once()


@pytest.mark.parametrize(
    "num_failures, expected_call_count",
    [(1, 2), (2, 3)],
)
def test_fetch_injury_report_success_after_nth_attempt(
    mocker: MockerFixture,
    nba_injury_report_source: NBAInjuryReportSource,
    tmp_path: Path,
    num_failures: int,
    expected_call_count: int,
) -> None:
    mocker.patch("tenacity.nap.time.sleep")
    mocker.patch("nbahl.sources.nba_injury_report_source.save_to_pdf")
    mock_get = mocker.patch(
        "nbahl.sources.nba_injury_report_source.requests.get"
    )
    fail_responses = [mocker.MagicMock() for _ in range(num_failures)]
    for mock_fail in fail_responses:
        mock_fail.raise_for_status.side_effect = _make_http_error(500)
    mock_success = mocker.MagicMock()
    mock_get.side_effect = [*fail_responses, mock_success]

    nba_injury_report_source.fetch_injury_report(
        url="https://example.com/test.pdf",
        filepath=tmp_path / "test.pdf",
    )

    assert mock_get.call_count == expected_call_count


def test_fetch_injury_report_reraises_after_all_attempts_exhausted(
    mocker: MockerFixture,
    nba_injury_report_source: NBAInjuryReportSource,
    tmp_path: Path,
) -> None:
    mocker.patch("tenacity.nap.time.sleep")
    mocker.patch("nbahl.sources.nba_injury_report_source.save_to_pdf")
    mock_get = mocker.patch(
        "nbahl.sources.nba_injury_report_source.requests.get"
    )
    mock_fail = mocker.MagicMock()
    mock_fail.raise_for_status.side_effect = _make_http_error(429)
    mock_get.return_value = mock_fail

    with pytest.raises(requests.exceptions.HTTPError):
        nba_injury_report_source.fetch_injury_report(
            url="https://example.com/test.pdf",
            filepath=tmp_path / "test.pdf",
        )

    assert mock_get.call_count == 3


@pytest.mark.parametrize("status_code", [403, 404])
def test_fetch_injury_reports_skips_missing_report(
    mocker: MockerFixture,
    nba_injury_report_source: NBAInjuryReportSource,
    status_code: int,
) -> None:
    mocker.patch.object(
        nba_injury_report_source,
        "_build_injury_report_urls",
        return_value=["https://example.com/url1.pdf"],
    )
    mock_fetch = mocker.patch.object(
        nba_injury_report_source,
        "fetch_injury_report",
        side_effect=_make_http_error(status_code),
    )

    nba_injury_report_source.fetch_injury_reports()

    mock_fetch.assert_called_once()


def test_fetch_injury_reports_reraises_non_404_500_error(
    mocker: MockerFixture,
    nba_injury_report_source: NBAInjuryReportSource,
) -> None:
    mocker.patch.object(
        nba_injury_report_source,
        "_build_injury_report_urls",
        return_value=["https://example.com/url1.pdf"],
    )
    mocker.patch.object(
        nba_injury_report_source,
        "fetch_injury_report",
        side_effect=_make_http_error(500),
    )

    with pytest.raises(requests.exceptions.HTTPError):
        nba_injury_report_source.fetch_injury_reports()


def test_ingest_injury_reports_success(
    mocker: MockerFixture,
) -> None:
    mocker.patch.object(
        NBAInjuryReportSource, "get_raw_filepaths", return_value=[]
    )
    mock_run_raw = mocker.patch(
        "nbahl.sources.nba_injury_report_source.run_raw_ingestion"
    )
    mock_run = mocker.patch(
        "nbahl.sources.nba_injury_report_source.run_ingestion"
    )
    mock_reconcile = mocker.patch(
        "nbahl.sources.nba_injury_report_source.reconcile"
    )
    mock_db_writer = mocker.MagicMock(spec=DBWriter)
    mock_s3_writer = mocker.MagicMock(spec=S3Writer)

    ingest_injury_reports(
        year=2026,
        frequency="15min",
        date_format="%Y-%m-%d_%I_%M%p",
        db_writer=mock_db_writer,
        s3_writer=mock_s3_writer,
    )

    mock_run_raw.assert_called_once()
    mock_run.assert_called_once()
    mock_reconcile.assert_called_once()


def test_ingest_injury_reports_raw_ingestion_raises_reconcile_still_runs(
    mocker: MockerFixture,
) -> None:
    mocker.patch.object(
        NBAInjuryReportSource, "get_raw_filepaths", return_value=[]
    )
    mocker.patch(
        "nbahl.sources.nba_injury_report_source.run_raw_ingestion",
        side_effect=RuntimeError("network failure"),
    )
    mock_run = mocker.patch(
        "nbahl.sources.nba_injury_report_source.run_ingestion"
    )
    mock_reconcile = mocker.patch(
        "nbahl.sources.nba_injury_report_source.reconcile"
    )
    mock_db_writer = mocker.MagicMock(spec=DBWriter)
    mock_s3_writer = mocker.MagicMock(spec=S3Writer)

    with pytest.raises(RuntimeError, match="network failure"):
        ingest_injury_reports(
            year=2026,
            frequency="15min",
            date_format="%Y-%m-%d_%I_%M%p",
            db_writer=mock_db_writer,
            s3_writer=mock_s3_writer,
        )

    mock_run.assert_not_called()
    mock_reconcile.assert_called_once()


def test_ingest_injury_reports_run_ingestion_raises_reconcile_still_runs(
    mocker: MockerFixture,
) -> None:
    mocker.patch.object(
        NBAInjuryReportSource, "get_raw_filepaths", return_value=[]
    )
    mocker.patch("nbahl.sources.nba_injury_report_source.run_raw_ingestion")
    mocker.patch(
        "nbahl.sources.nba_injury_report_source.run_ingestion",
        side_effect=RuntimeError("parse failure"),
    )
    mock_reconcile = mocker.patch(
        "nbahl.sources.nba_injury_report_source.reconcile"
    )
    mock_db_writer = mocker.MagicMock(spec=DBWriter)
    mock_s3_writer = mocker.MagicMock(spec=S3Writer)

    with pytest.raises(RuntimeError, match="parse failure"):
        ingest_injury_reports(
            year=2026,
            frequency="15min",
            date_format="%Y-%m-%d_%I_%M%p",
            db_writer=mock_db_writer,
            s3_writer=mock_s3_writer,
        )

    mock_reconcile.assert_called_once()
