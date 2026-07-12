from pathlib import Path

import pandas as pd
import pytest
from boto3.exceptions import S3UploadFailedError
from pytest_mock import MockerFixture
from requests.exceptions import ConnectionError

from nbahl.common.enums import Status
from nbahl.common.exceptions import DataFrameEmptyError
from nbahl.common.models import IngestionContext
from nbahl.pipelines import run_ingestion
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

    mock_db_writer.write.assert_called_once()
    mock_s3_writer.write.assert_called_once()
    ingestion_run = mock_db_writer.write.call_args.kwargs["ingestion_run"]
    key = mock_s3_writer.write.call_args.kwargs["key"]

    assert ingestion_run.source == source_name
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

    mock_db_writer.write.assert_called_once()
    ingestion_run = mock_db_writer.write.call_args.kwargs["ingestion_run"]

    assert ingestion_run.source == source_name
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

    mock_s3_writer.write.assert_called_once()
    mock_db_writer.write.assert_called_once()
    ingestion_run = mock_db_writer.write.call_args.kwargs["ingestion_run"]

    assert ingestion_run.source == source_name
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

    mock_db_writer.write.assert_called_once()
    ingestion_run = mock_db_writer.write.call_args.kwargs["ingestion_run"]

    assert ingestion_run.source == source_name
    assert ingestion_run.rows_in is None
    assert ingestion_run.status == Status.FAILURE
    assert ingestion_run.error_message == "DataFrame is empty"
