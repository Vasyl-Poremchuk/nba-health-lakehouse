from pathlib import Path

import pandas as pd
import pytest
from boto3.exceptions import S3UploadFailedError
from nba_api.stats.endpoints.boxscoretraditionalv3 import BoxScoreTraditionalV3
from pytest_mock import MockerFixture
from requests.exceptions import ConnectionError

from nbahl.common.constants import BaseConstants, BoxScoreNBAApiSourceConstants
from nbahl.common.enums import Period, Status
from nbahl.common.exceptions import DataFrameEmptyError
from nbahl.common.models import BoxScoreContext
from nbahl.sources.box_score_nba_api_source import (
    BoxScoreNBAApiSource,
    ingest_box_score_game_logs,
)
from nbahl.writers.db_writer import DBWriter
from nbahl.writers.s3_writer import S3Writer


def test_get_box_score_logs_success(
    mocker: MockerFixture, box_score_nba_api_source: BoxScoreNBAApiSource
) -> None:
    mock_class = mocker.MagicMock()
    mock_class.return_value.get_data_frames.return_value = [
        pd.DataFrame(data=[{"gameId": "0022500001"}])
    ]

    box_score_context = BoxScoreContext.model_construct(
        box_score_class=mock_class,
        datasets=["player_stats"],
        includes_periods=True,
    )

    box_score_logs = box_score_nba_api_source.get_box_score_logs(
        game_id="0022500001",
        game_id_source_name="play-by-play-logs-0-0",
        box_score_context=box_score_context,
    )

    mock_class.assert_called_once()
    assert "player_stats" in box_score_logs
    assert "source_name" in box_score_logs["player_stats"].columns
    assert len(box_score_logs["player_stats"]) == 1
    assert (
        box_score_logs["player_stats"]["source_name"].iloc[0]
        == "play-by-play-logs-0-0"
    )


def test_get_box_score_logs_success_after_second_attempt(
    mocker: MockerFixture, box_score_nba_api_source: BoxScoreNBAApiSource
) -> None:
    mock_class = mocker.MagicMock()
    mocker.patch("tenacity.nap.time.sleep")
    mock_class.return_value.get_data_frames.side_effect = [
        ConnectionError("Timeout"),
        [pd.DataFrame(data=[{"gameId": "0022500001"}])],
    ]

    box_score_context = BoxScoreContext.model_construct(
        box_score_class=mock_class,
        datasets=["player_stats"],
        includes_periods=True,
    )

    box_score_logs = box_score_nba_api_source.get_box_score_logs(
        game_id="0022500001",
        game_id_source_name="play-by-play-logs-0-0",
        box_score_context=box_score_context,
    )

    assert mock_class.call_count == 2
    assert "player_stats" in box_score_logs
    assert "source_name" in box_score_logs["player_stats"].columns
    assert len(box_score_logs["player_stats"]) == 1
    assert (
        box_score_logs["player_stats"]["source_name"].iloc[0]
        == "play-by-play-logs-0-0"
    )


def test_get_box_score_logs_success_after_third_attempt(
    mocker: MockerFixture, box_score_nba_api_source: BoxScoreNBAApiSource
) -> None:
    mock_class = mocker.MagicMock()
    mocker.patch("tenacity.nap.time.sleep")
    mock_class.return_value.get_data_frames.side_effect = [
        ConnectionError("Timeout"),
        ConnectionError("Timeout"),
        [pd.DataFrame(data=[{"gameId": "0022500001"}])],
    ]

    box_score_context = BoxScoreContext.model_construct(
        box_score_class=mock_class,
        datasets=["player_stats"],
        includes_periods=True,
    )

    box_score_logs = box_score_nba_api_source.get_box_score_logs(
        game_id="0022500001",
        game_id_source_name="play-by-play-logs-0-0",
        box_score_context=box_score_context,
    )

    assert mock_class.call_count == 3
    assert "player_stats" in box_score_logs
    assert "source_name" in box_score_logs["player_stats"].columns
    assert len(box_score_logs["player_stats"]) == 1
    assert (
        box_score_logs["player_stats"]["source_name"].iloc[0]
        == "play-by-play-logs-0-0"
    )


def test_get_box_score_logs_failure_after_all_attempts(
    mocker: MockerFixture, box_score_nba_api_source: BoxScoreNBAApiSource
) -> None:
    mock_class = mocker.MagicMock()
    mocker.patch("tenacity.nap.time.sleep")
    mock_class.return_value.get_data_frames.side_effect = [
        ConnectionError("Timeout"),
        ConnectionError("Timeout"),
        ConnectionError("Timeout"),
    ]

    box_score_context = BoxScoreContext.model_construct(
        box_score_class=mock_class,
        datasets=["player_stats"],
        includes_periods=True,
    )

    with pytest.raises(ConnectionError) as exc_info:
        box_score_nba_api_source.get_box_score_logs(
            game_id="0022500001",
            game_id_source_name="play-by-play-logs-0-0",
            box_score_context=box_score_context,
        )

    assert mock_class.call_count == 3
    assert str(exc_info.value) == "Timeout"


def test_get_box_score_game_logs_success(
    mocker: MockerFixture, box_score_nba_api_source: BoxScoreNBAApiSource
) -> None:
    mock_class = mocker.MagicMock()
    mocker.patch("nbahl.common.utils.time.sleep")
    mocker.patch.object(
        box_score_nba_api_source,
        "get_box_score_logs",
        side_effect=[
            {
                "player_stats": pd.DataFrame(
                    data=[
                        {
                            "gameId": "0022500001",
                            "source_name": "play-by-play-logs-0-0",
                        }
                    ]
                )
            },
            {
                "player_stats": pd.DataFrame(
                    data=[
                        {
                            "gameId": "0022500002",
                            "source_name": "play-by-play-logs-0-0",
                        }
                    ]
                )
            },
        ],
    )
    box_score_context = BoxScoreContext.model_construct(
        box_score_class=mock_class,
        datasets=["player_stats"],
        includes_periods=True,
    )

    box_score_game_logs = box_score_nba_api_source.get_box_score_game_logs(
        game_ids_by_source={
            "play-by-play-logs-0-0": ["0022500001", "0022500002"]
        },
        box_score_context=box_score_context,
    )

    assert "player_stats" in box_score_game_logs
    assert "source_name" in box_score_game_logs["player_stats"].columns
    assert len(box_score_game_logs["player_stats"]) == 2
    assert (
        box_score_game_logs["player_stats"]["source_name"].iloc[0]
        == "play-by-play-logs-0-0"
    )


def test_get_box_score_game_logs_multiple_sources(
    mocker: MockerFixture, box_score_nba_api_source: BoxScoreNBAApiSource
) -> None:
    mock_class = mocker.MagicMock()
    mocker.patch("nbahl.common.utils.time.sleep")
    mocker.patch.object(
        box_score_nba_api_source,
        "get_box_score_logs",
        side_effect=[
            {
                "player_stats": pd.DataFrame(
                    data=[
                        {
                            "gameId": "0022500001",
                            "source_name": "play-by-play-logs-0-0",
                        }
                    ]
                )
            },
            {
                "player_stats": pd.DataFrame(
                    data=[
                        {
                            "gameId": "0022500002",
                            "source_name": "play-by-play-logs-0-1",
                        }
                    ]
                )
            },
        ],
    )
    box_score_context = BoxScoreContext.model_construct(
        box_score_class=mock_class,
        datasets=["player_stats"],
        includes_periods=True,
    )

    box_score_game_logs = box_score_nba_api_source.get_box_score_game_logs(
        game_ids_by_source={
            "play-by-play-logs-0-0": ["0022500001"],
            "play-by-play-logs-0-1": ["0022500002"],
        },
        box_score_context=box_score_context,
    )

    assert "player_stats" in box_score_game_logs
    assert len(box_score_game_logs["player_stats"]) == 2
    assert set(box_score_game_logs["player_stats"]["source_name"]) == {
        "play-by-play-logs-0-0",
        "play-by-play-logs-0-1",
    }


def test_get_box_score_game_logs_no_dataframes(
    mocker: MockerFixture, box_score_nba_api_source: BoxScoreNBAApiSource
) -> None:
    mock_class = mocker.MagicMock()
    mocker.patch("nbahl.common.utils.time.sleep")
    mocker.patch.object(
        box_score_nba_api_source,
        "get_box_score_logs",
        return_value={},
    )

    box_score_context = BoxScoreContext.model_construct(
        box_score_class=mock_class,
        datasets=["player_stats"],
        includes_periods=True,
    )

    with pytest.raises(
        DataFrameEmptyError, match="No DataFrames for any 'game_id'"
    ):
        box_score_nba_api_source.get_box_score_game_logs(
            game_ids_by_source={"play-by-play-logs-0-0": ["0022500001"]},
            box_score_context=box_score_context,
        )


def test_get_box_score_game_logs_exceeded_max_total_failure_number(
    mocker: MockerFixture, box_score_nba_api_source: BoxScoreNBAApiSource
) -> None:
    mocker.patch.object(BaseConstants, "MAX_TOTAL_FAILURE_NUMBER", new=3)
    mock_class = mocker.MagicMock()
    mocker.patch.object(
        box_score_nba_api_source,
        "get_box_score_logs",
        side_effect=[
            ConnectionError("Timeout"),
            ConnectionError("Timeout"),
            ConnectionError("Timeout"),
            ConnectionError("Timeout"),
        ],
    )
    mocker.patch("nbahl.common.utils.time.sleep")

    box_score_context = BoxScoreContext.model_construct(
        box_score_class=mock_class,
        datasets=["player_stats"],
        includes_periods=True,
    )

    with pytest.raises(ConnectionError, match="Timeout"):
        box_score_nba_api_source.get_box_score_game_logs(
            game_ids_by_source={
                "play-by-play-logs-0-0": [
                    "0022500001",
                    "0022500002",
                    "0022500003",
                    "0022500004",
                ]
            },
            box_score_context=box_score_context,
        )


def test_ingest_box_score_game_logs_success(
    mocker: MockerFixture, data_dir: Path
) -> None:
    mocker.patch.object(
        BoxScoreNBAApiSourceConstants,
        "BOX_SCORE_SOURCES",
        new={(BoxScoreTraditionalV3, "traditional"): ["player_stats"]},
    )
    mocker.patch(
        "nbahl.sources.box_score_nba_api_source.get_game_ids_by_source",
        return_value={"play-by-play-logs-0-0": ["0022500001"]},
    )
    mocker.patch.object(
        BoxScoreNBAApiSource,
        "get_box_score_game_logs",
        return_value={
            "player_stats": pd.DataFrame(
                data=[
                    {
                        "gameId": "0022500001",
                        "source_name": "play-by-play-logs-0-0",
                    }
                ]
            )
        },
    )
    mock_db_writer = mocker.MagicMock(spec=DBWriter)
    mock_s3_writer = mocker.MagicMock(spec=S3Writer)
    mocker.patch("nbahl.sources.box_score_nba_api_source.reconcile")

    ingest_box_score_game_logs(
        season="2025-26",
        start_period=Period.ALL,
        end_period=Period.ALL,
        db_writer=mock_db_writer,
        s3_writer=mock_s3_writer,
    )

    ingestion_run = mock_db_writer.update.call_args.kwargs["ingestion_run"]
    key = mock_s3_writer.write.call_args.kwargs["key"]

    mock_s3_writer.write.assert_called_once()
    mock_db_writer.update.assert_called_once()
    assert (
        ingestion_run.s3_key
        == "2025-26/box-score-logs-0-0-traditional-player-stats.parquet"
    )
    assert ingestion_run.rows_in == 1
    assert ingestion_run.status == Status.SUCCESS
    assert ingestion_run.error_message is None
    assert key == "2025-26/box-score-logs-0-0-traditional-player-stats.parquet"


def test_ingest_box_score_game_logs_api_failure(
    mocker: MockerFixture, data_dir: Path
) -> None:
    mocker.patch.object(
        BoxScoreNBAApiSourceConstants,
        "BOX_SCORE_SOURCES",
        new={(BoxScoreTraditionalV3, "traditional"): ["player_stats"]},
    )
    mocker.patch(
        "nbahl.sources.box_score_nba_api_source.get_game_ids_by_source",
        return_value={"play-by-play-logs-0-0": ["0022500001"]},
    )
    mocker.patch.object(
        BoxScoreNBAApiSource,
        "get_box_score_game_logs",
        side_effect=ConnectionError("Timeout"),
    )
    mock_db_writer = mocker.MagicMock(spec=DBWriter)
    mock_s3_writer = mocker.MagicMock(spec=S3Writer)
    mocker.patch("nbahl.sources.box_score_nba_api_source.reconcile")

    with pytest.raises(ConnectionError, match="Timeout"):
        ingest_box_score_game_logs(
            season="2025-26",
            start_period=Period.ALL,
            end_period=Period.ALL,
            db_writer=mock_db_writer,
            s3_writer=mock_s3_writer,
        )

    ingestion_run = mock_db_writer.update.call_args.kwargs["ingestion_run"]

    mock_db_writer.update.assert_called_once()
    mock_s3_writer.write.assert_not_called()
    assert (
        ingestion_run.s3_key
        == "2025-26/box-score-logs-0-0-traditional-player-stats.parquet"
    )
    assert ingestion_run.rows_in is None
    assert ingestion_run.status == Status.FAILURE
    assert ingestion_run.error_message == "Timeout"


def test_ingest_box_score_game_logs_s3_failure(
    mocker: MockerFixture, data_dir: Path
) -> None:
    mocker.patch.object(
        BoxScoreNBAApiSourceConstants,
        "BOX_SCORE_SOURCES",
        new={(BoxScoreTraditionalV3, "traditional"): ["player_stats"]},
    )
    mocker.patch(
        "nbahl.sources.box_score_nba_api_source.get_game_ids_by_source",
        return_value={"play-by-play-logs-0-0": ["0022500001"]},
    )
    mocker.patch.object(
        BoxScoreNBAApiSource,
        "get_box_score_game_logs",
        return_value={
            "player_stats": pd.DataFrame(
                data=[
                    {
                        "gameId": "0022500001",
                        "source_name": "play-by-play-logs-0-0",
                    }
                ]
            )
        },
    )
    mock_db_writer = mocker.MagicMock(spec=DBWriter)
    mock_s3_writer = mocker.MagicMock(spec=S3Writer)
    mocker.patch("nbahl.sources.box_score_nba_api_source.reconcile")
    mock_s3_writer.write.side_effect = S3UploadFailedError(
        "Failed to upload nbahl/data/2025-26/box-score-logs-0-0-traditional-player-stats.parquet "
        "to nbahl/2025-26/box-score-logs-0-0-traditional-player-stats: "
        "An error occured (NoSuchBucket) when calling the PutObject operation: "
        "The specified bucket does not exist"
    )

    with pytest.raises(S3UploadFailedError, match="NoSuchBucket"):
        ingest_box_score_game_logs(
            season="2025-26",
            start_period=Period.ALL,
            end_period=Period.ALL,
            db_writer=mock_db_writer,
            s3_writer=mock_s3_writer,
        )

    ingestion_run = mock_db_writer.update.call_args.kwargs["ingestion_run"]

    mock_db_writer.update.assert_called_once()
    mock_s3_writer.write.assert_called_once()
    assert (
        ingestion_run.s3_key
        == "2025-26/box-score-logs-0-0-traditional-player-stats.parquet"
    )
    assert ingestion_run.rows_in is None
    assert ingestion_run.status == Status.FAILURE
    assert "NoSuchBucket" in ingestion_run.error_message


def test_ingest_box_score_game_logs_df_empty_failure(
    mocker: MockerFixture, data_dir: Path
) -> None:
    mocker.patch.object(
        BoxScoreNBAApiSourceConstants,
        "BOX_SCORE_SOURCES",
        new={(BoxScoreTraditionalV3, "traditional"): ["player_stats"]},
    )
    mocker.patch(
        "nbahl.sources.box_score_nba_api_source.get_game_ids_by_source",
        return_value={"play-by-play-logs-0-0": ["0022500001"]},
    )
    mocker.patch.object(
        BoxScoreNBAApiSource,
        "get_box_score_game_logs",
        return_value={"player_stats": pd.DataFrame()},
    )
    mock_db_writer = mocker.MagicMock(spec=DBWriter)
    mock_s3_writer = mocker.MagicMock(spec=S3Writer)
    mocker.patch("nbahl.sources.box_score_nba_api_source.reconcile")

    with pytest.raises(DataFrameEmptyError, match="DataFrame is empty"):
        ingest_box_score_game_logs(
            season="2025-26",
            start_period=Period.ALL,
            end_period=Period.ALL,
            db_writer=mock_db_writer,
            s3_writer=mock_s3_writer,
        )

    ingestion_run = mock_db_writer.update.call_args.kwargs["ingestion_run"]

    mock_db_writer.update.assert_called_once()
    mock_s3_writer.write.assert_not_called()
    assert (
        ingestion_run.s3_key
        == "2025-26/box-score-logs-0-0-traditional-player-stats.parquet"
    )
    assert ingestion_run.rows_in is None
    assert ingestion_run.status == Status.FAILURE
    assert ingestion_run.error_message == "DataFrame is empty"


def test_ingest_box_score_game_logs_no_run_id(
    mocker: MockerFixture, data_dir: Path
) -> None:
    mocker.patch.object(
        BoxScoreNBAApiSourceConstants,
        "BOX_SCORE_SOURCES",
        new={(BoxScoreTraditionalV3, "traditional"): ["player_stats"]},
    )
    mocker.patch(
        "nbahl.sources.box_score_nba_api_source.get_game_ids_by_source",
        return_value={"play-by-play-logs-0-0": ["0022500001"]},
    )
    mock_db_writer = mocker.MagicMock(spec=DBWriter)
    mock_s3_writer = mocker.MagicMock(spec=S3Writer)
    mock_db_writer.write.side_effect = RuntimeError(
        "INSERT INTO ingestion_runs returned no run_id"
    )
    mocker.patch("nbahl.sources.box_score_nba_api_source.reconcile")

    with pytest.raises(
        RuntimeError, match="INSERT INTO ingestion_runs returned no run_id"
    ):
        ingest_box_score_game_logs(
            season="2025-26",
            start_period=Period.ALL,
            end_period=Period.ALL,
            db_writer=mock_db_writer,
            s3_writer=mock_s3_writer,
        )

    mock_db_writer.update.assert_not_called()
