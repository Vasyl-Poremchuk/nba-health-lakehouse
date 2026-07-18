from pathlib import Path

import pandas as pd
import pytest
from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import ClientError
from pytest_mock import MockerFixture
from requests.exceptions import ConnectionError

from nbahl.common.enums import Status
from nbahl.common.exceptions import DataFrameEmptyError
from nbahl.common.models import IngestionContext
from nbahl.pipelines import reconcile, run_ingestion
from nbahl.protocols import GameLogSource
from nbahl.sources.game_log_nba_api_source import GameLogNBAApiSource
from nbahl.sources.play_by_play_nba_api_source import PlayByPlayNBAApiSource
from nbahl.writers.db_writer import DBWriter
from nbahl.writers.s3_writer import S3Writer


@pytest.mark.parametrize(
    "source_name, season, source_class, source_df",
    [
        (
            "league-game-logs-00-t-regular-season",
            "2025-26",
            GameLogNBAApiSource,
            "league_game_logs_00_t_regular_season_df",
        ),
        (
            "play-by-play-logs-0-0",
            "2025-26",
            PlayByPlayNBAApiSource,
            "play_by_play_logs_0_0_df",
        ),
    ],
    indirect=["source_df"],
)
def test_run_ingestion_success(
    mocker: MockerFixture,
    data_dir: Path,
    source_name: str,
    season: str,
    source_class: GameLogSource,
    source_df: pd.DataFrame,
) -> None:
    filepath = data_dir / season / f"{source_name}.parquet"

    mock_source = mocker.MagicMock(spec=source_class)
    mock_source.get_game_logs.return_value = source_df

    mock_db_writer = mocker.MagicMock(spec=DBWriter)
    mock_s3_writer = mocker.MagicMock(spec=S3Writer)

    context = IngestionContext(
        source_name=source_name,
        season=season,
        filepath=filepath,
        s3_key=f"{season}/{source_name}.parquet",
        source=mock_source,
    )

    run_ingestion(
        context=context, db_writer=mock_db_writer, s3_writer=mock_s3_writer
    )

    ingestion_run = mock_db_writer.update.call_args.kwargs["ingestion_run"]
    key = mock_s3_writer.write.call_args.kwargs["key"]

    mock_db_writer.update.assert_called_once()
    mock_s3_writer.write.assert_called_once()
    assert ingestion_run.s3_key == f"{season}/{source_name}.parquet"
    assert ingestion_run.rows_in == len(source_df)
    assert ingestion_run.status == Status.SUCCESS
    assert ingestion_run.error_message is None
    assert key == f"{season}/{source_name}.parquet"


@pytest.mark.parametrize(
    "source_name, season, source_class",
    [
        (
            "league-game-logs-00-t-regular-season",
            "2025-26",
            GameLogNBAApiSource,
        ),
        ("play-by-play-logs-0-0", "2025-26", PlayByPlayNBAApiSource),
    ],
)
def test_run_ingestion_api_failure(
    mocker: MockerFixture,
    data_dir: Path,
    source_name: str,
    season: str,
    source_class: GameLogSource,
) -> None:
    filepath = data_dir / season / f"{source_name}.parquet"

    mock_source = mocker.MagicMock(spec=source_class)
    mock_source.get_game_logs.side_effect = ConnectionError("Timeout")

    mock_db_writer = mocker.MagicMock(spec=DBWriter)
    mock_s3_writer = mocker.MagicMock(spec=S3Writer)

    context = IngestionContext(
        source_name=source_name,
        season=season,
        filepath=filepath,
        s3_key=f"{season}/{source_name}.parquet",
        source=mock_source,
    )

    with pytest.raises(ConnectionError, match="Timeout"):
        run_ingestion(
            context=context, db_writer=mock_db_writer, s3_writer=mock_s3_writer
        )

    ingestion_run = mock_db_writer.update.call_args.kwargs["ingestion_run"]

    mock_db_writer.update.assert_called_once()
    assert ingestion_run.s3_key == f"{season}/{source_name}.parquet"
    assert ingestion_run.rows_in is None
    assert ingestion_run.status == Status.FAILURE
    assert ingestion_run.error_message == "Timeout"


@pytest.mark.parametrize(
    "source_name, season, source_class, source_df",
    [
        (
            "league-game-logs-00-t-regular-season",
            "2025-26",
            GameLogNBAApiSource,
            "league_game_logs_00_t_regular_season_df",
        ),
        (
            "play-by-play-logs-0-0",
            "2025-26",
            PlayByPlayNBAApiSource,
            "play_by_play_logs_0_0_df",
        ),
    ],
    indirect=["source_df"],
)
def test_run_ingestion_s3_failure(
    mocker: MockerFixture,
    data_dir: Path,
    source_name: str,
    season: str,
    source_class: GameLogSource,
    source_df: pd.DataFrame,
) -> None:
    filepath = data_dir / season / f"{source_name}.parquet"

    mock_source = mocker.MagicMock(spec=source_class)
    mock_source.get_game_logs.return_value = source_df

    mock_db_writer = mocker.MagicMock(spec=DBWriter)
    mock_s3_writer = mocker.MagicMock(spec=S3Writer)
    mock_s3_writer.write.side_effect = S3UploadFailedError(
        "Failed to upload nbahl/data/2025-26/league-game-logs-00-t-regular-season.parquet "
        "to nbahl/2025-26/league-game-logs-00-t-regular-season: "
        "An error occured (NoSuchBucket) when calling the PutObject operation: "
        "The specified bucket does not exist"
    )

    context = IngestionContext(
        source_name=source_name,
        season=season,
        filepath=filepath,
        s3_key=f"{season}/{source_name}.parquet",
        source=mock_source,
    )

    with pytest.raises(S3UploadFailedError, match="NoSuchBucket"):
        run_ingestion(
            context=context, db_writer=mock_db_writer, s3_writer=mock_s3_writer
        )

    ingestion_run = mock_db_writer.update.call_args.kwargs["ingestion_run"]

    mock_s3_writer.write.assert_called_once()
    mock_db_writer.update.assert_called_once()
    assert ingestion_run.s3_key == f"{season}/{source_name}.parquet"
    assert ingestion_run.status == Status.FAILURE
    assert ingestion_run.rows_in is None
    assert "NoSuchBucket" in ingestion_run.error_message


@pytest.mark.parametrize(
    "source_name, season, source_class, source_df",
    [
        (
            "league-game-logs-00-t-regular-season",
            "2025-26",
            GameLogNBAApiSource,
            pd.DataFrame(),
        ),
        (
            "play-by-play-logs-0-0",
            "2025-26",
            PlayByPlayNBAApiSource,
            pd.DataFrame(),
        ),
    ],
)
def test_run_ingestion_df_empty_failure(
    mocker: MockerFixture,
    data_dir: Path,
    source_name: str,
    season: str,
    source_class: GameLogSource,
    source_df: pd.DataFrame,
) -> None:
    filepath = data_dir / season / f"{source_name}.parquet"

    mock_source = mocker.MagicMock(spec=source_class)
    mock_source.get_game_logs.return_value = source_df

    mock_db_writer = mocker.MagicMock(spec=DBWriter)
    mock_s3_writer = mocker.MagicMock(spec=S3Writer)

    context = IngestionContext(
        source_name=source_name,
        season=season,
        filepath=filepath,
        s3_key=f"{season}/{source_name}.parquet",
        source=mock_source,
    )

    with pytest.raises(DataFrameEmptyError, match="DataFrame is empty"):
        run_ingestion(
            context=context, db_writer=mock_db_writer, s3_writer=mock_s3_writer
        )

    ingestion_run = mock_db_writer.update.call_args.kwargs["ingestion_run"]

    mock_db_writer.update.assert_called_once()
    assert ingestion_run.s3_key == f"{season}/{source_name}.parquet"
    assert ingestion_run.rows_in is None
    assert ingestion_run.status == Status.FAILURE
    assert ingestion_run.error_message == "DataFrame is empty"


@pytest.mark.parametrize(
    "source_name, season, source_class",
    [
        (
            "league-game-logs-00-t-regular-season",
            "2025-26",
            GameLogNBAApiSource,
        ),
        ("play-by-play-logs-0-0", "2025-26", PlayByPlayNBAApiSource),
    ],
)
def test_run_ingestion_no_run_id(
    mocker: MockerFixture,
    data_dir: Path,
    source_name: str,
    season: str,
    source_class: GameLogSource,
) -> None:
    filepath = data_dir / season / f"{source_name}.parquet"

    mock_source = mocker.MagicMock(spec=source_class)

    mock_db_writer = mocker.MagicMock(spec=DBWriter)
    mock_s3_writer = mocker.MagicMock(spec=S3Writer)

    mock_db_writer.write.side_effect = RuntimeError(
        "INSERT INTO ingestion_runs returned no run_id"
    )

    context = IngestionContext(
        source_name=source_name,
        season=season,
        filepath=filepath,
        s3_key=f"{season}/{source_name}.parquet",
        source=mock_source,
    )

    with pytest.raises(
        RuntimeError, match="INSERT INTO ingestion_runs returned no run_id"
    ):
        run_ingestion(
            context=context, db_writer=mock_db_writer, s3_writer=mock_s3_writer
        )

    mock_db_writer.update.assert_not_called()


@pytest.mark.parametrize(
    "stale_rows, object_exists, expected_success_ids, expected_failure_ids",
    [
        (
            [
                {
                    "run_id": 1,
                    "s3_key": "2025-26/league-game-logs-00-t-regular-season.parquet",
                }
            ],
            [True],
            [1],
            [],
        ),
        (
            [
                {
                    "run_id": 1,
                    "s3_key": "2025-26/league-game-logs-00-t-regular-season.parquet",
                }
            ],
            [False],
            [],
            [1],
        ),
        (
            [
                {
                    "run_id": 1,
                    "s3_key": "2025-26/league-game-logs-00-t-regular-season.parquet",
                },
                {"run_id": 2, "s3_key": "2025-26/play-by-play-logs-0-0"},
            ],
            [True, True],
            [1, 2],
            [],
        ),
        (
            [
                {
                    "run_id": 1,
                    "s3_key": "2025-26/league-game-logs-00-t-regular-season.parquet",
                },
                {"run_id": 2, "s3_key": "2025-26/play-by-play-logs-0-0"},
            ],
            [False, False],
            [],
            [1, 2],
        ),
        (
            [
                {
                    "run_id": 1,
                    "s3_key": "2025-26/league-game-logs-00-t-regular-season.parquet",
                },
                {"run_id": 2, "s3_key": "2025-26/play-by-play-logs-0-0"},
            ],
            [False, True],
            [2],
            [1],
        ),
        ([], [], [], []),
    ],
)
def test_reconcile_success_routes(
    mocker: MockerFixture,
    stale_rows: list[dict[str, int | str]],
    object_exists: list[bool],
    expected_success_ids: list[int],
    expected_failure_ids: list[int],
) -> None:
    mock_db_writer = mocker.MagicMock(spec=DBWriter)
    mock_s3_writer = mocker.MagicMock(spec=S3Writer)

    mock_db_writer.get_stale_rows.return_value = stale_rows
    mock_s3_writer.object_exists.side_effect = object_exists

    reconcile(db_writer=mock_db_writer, s3_writer=mock_s3_writer)

    calls = mock_db_writer.update_status.call_args_list
    success, failure = calls
    success_ids = success.kwargs["run_ids"]
    success_status = success.kwargs["status"]
    failure_ids = failure.kwargs["run_ids"]
    failure_status = failure.kwargs["status"]

    assert mock_db_writer.update_status.call_count == 2
    assert mock_s3_writer.object_exists.call_count == len(object_exists)
    assert success_ids == expected_success_ids
    assert success_status == Status.SUCCESS
    assert failure_ids == expected_failure_ids
    assert failure_status == Status.FAILURE


def test_reconcile_non_404_error(mocker: MockerFixture) -> None:
    error_payload = ClientError(
        error_response={"Error": {"Code": "403", "Message": "Forbidden"}},
        operation_name="HeadObject",
    )

    mock_db_writer = mocker.MagicMock(spec=DBWriter)
    mock_s3_writer = mocker.MagicMock(spec=S3Writer)

    mock_db_writer.get_stale_rows.return_value = [
        {"run_id": 2, "s3_key": "2025-26/play-by-play-logs-0-0"}
    ]
    mock_s3_writer.object_exists.side_effect = error_payload

    with pytest.raises(ClientError) as exc_info:
        reconcile(db_writer=mock_db_writer, s3_writer=mock_s3_writer)

    error_response = exc_info.value.response["Error"]

    assert error_response["Code"] == "403"
    assert error_response["Message"] == "Forbidden"
