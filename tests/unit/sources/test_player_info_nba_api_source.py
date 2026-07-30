from pathlib import Path

import pandas as pd
import pytest
from pytest_mock import MockerFixture
from requests.exceptions import ConnectionError

from nbahl.common.enums import Status
from nbahl.common.exceptions import ColumnNotFoundError, DataFrameEmptyError
from nbahl.common.utils import write_to_parquet
from nbahl.sources.player_info_nba_api_source import (
    PlayerInfoNBAApiSource,
    ingest_all_players_info,
    ingest_players_detail_info,
)
from nbahl.writers.db_writer import DBWriter
from nbahl.writers.s3_writer import S3Writer


def test_get_all_players_info_success(
    mocker: MockerFixture, player_info_nba_api_source: PlayerInfoNBAApiSource
) -> None:
    mock_class = mocker.patch(
        "nbahl.sources.player_info_nba_api_source.CommonAllPlayers"
    )
    mock_class.return_value.get_data_frames.return_value = [
        pd.DataFrame(data=[{"PERSON_ID": 1, "PLAYER": "Player 1"}])
    ]

    output_df = player_info_nba_api_source.get_all_players_info(
        season="2025-26"
    )
    call_kwargs = mock_class.call_args.kwargs

    mock_class.assert_called_once()
    assert call_kwargs["season"] == "2025-26"
    assert output_df["PLAYER"].iloc[0] == "Player 1"


def test_get_all_players_info_success_after_second_attempt(
    mocker: MockerFixture, player_info_nba_api_source: PlayerInfoNBAApiSource
) -> None:
    mock_class = mocker.patch(
        "nbahl.sources.player_info_nba_api_source.CommonAllPlayers"
    )
    mocker.patch("tenacity.nap.time.sleep")
    mock_class.return_value.get_data_frames.side_effect = [
        ConnectionError("Timeout"),
        [pd.DataFrame(data=[{"PERSON_ID": 1, "PLAYER": "Player 1"}])],
    ]

    output_df = player_info_nba_api_source.get_all_players_info(
        season="2025-26"
    )
    call_kwargs = mock_class.call_args.kwargs

    assert mock_class.call_count == 2
    assert call_kwargs["season"] == "2025-26"
    assert output_df["PLAYER"].iloc[0] == "Player 1"


def test_get_all_players_info_success_after_third_attempt(
    mocker: MockerFixture, player_info_nba_api_source: PlayerInfoNBAApiSource
) -> None:
    mock_class = mocker.patch(
        "nbahl.sources.player_info_nba_api_source.CommonAllPlayers"
    )
    mocker.patch("tenacity.nap.time.sleep")
    mock_class.return_value.get_data_frames.side_effect = [
        ConnectionError("Timeout"),
        ConnectionError("Timeout"),
        [pd.DataFrame(data=[{"PERSON_ID": 1, "PLAYER": "Player 1"}])],
    ]

    output_df = player_info_nba_api_source.get_all_players_info(
        season="2025-26"
    )
    call_kwargs = mock_class.call_args.kwargs

    assert mock_class.call_count == 3
    assert call_kwargs["season"] == "2025-26"
    assert output_df["PLAYER"].iloc[0] == "Player 1"


def test_get_all_players_info_failure_after_all_attempts(
    mocker: MockerFixture, player_info_nba_api_source: PlayerInfoNBAApiSource
) -> None:
    mock_class = mocker.patch(
        "nbahl.sources.player_info_nba_api_source.CommonAllPlayers"
    )
    mocker.patch("tenacity.nap.time.sleep")
    mock_class.return_value.get_data_frames.side_effect = ConnectionError(
        "Timeout"
    )

    with pytest.raises(ConnectionError) as exc_info:
        player_info_nba_api_source.get_all_players_info(season="2025-26")

    assert mock_class.call_count == 3
    assert str(exc_info.value) == "Timeout"


def test_get_player_info_success(
    mocker: MockerFixture, player_info_nba_api_source: PlayerInfoNBAApiSource
) -> None:
    mock_class = mocker.patch(
        "nbahl.sources.player_info_nba_api_source.CommonPlayerInfo"
    )
    mock_class.return_value.get_data_frames.return_value = [
        pd.DataFrame(
            data=[
                {
                    "PERSON_ID": 1,
                    "PLAYER": "Player 1",
                    "HEIGHT": "6-5",
                    "WEIGHT": "250",
                }
            ]
        )
    ]

    output_df = player_info_nba_api_source.get_player_info(player_id=1)
    call_kwargs = mock_class.call_args.kwargs

    mock_class.assert_called_once()
    assert call_kwargs["player_id"] == 1
    assert output_df["PLAYER"].iloc[0] == "Player 1"


def test_get_player_info_success_after_second_attempt(
    mocker: MockerFixture, player_info_nba_api_source: PlayerInfoNBAApiSource
) -> None:
    mock_class = mocker.patch(
        "nbahl.sources.player_info_nba_api_source.CommonPlayerInfo"
    )
    mocker.patch("tenacity.nap.time.sleep")
    mock_class.return_value.get_data_frames.side_effect = [
        ConnectionError("Timeout"),
        [
            pd.DataFrame(
                data=[
                    {
                        "PERSON_ID": 1,
                        "PLAYER": "Player 1",
                        "HEIGHT": "6-5",
                        "WEIGHT": "250",
                    }
                ]
            )
        ],
    ]

    output_df = player_info_nba_api_source.get_player_info(player_id=1)
    call_kwargs = mock_class.call_args.kwargs

    assert mock_class.call_count == 2
    assert call_kwargs["player_id"] == 1
    assert output_df["PLAYER"].iloc[0] == "Player 1"


def test_get_player_info_success_after_third_attempt(
    mocker: MockerFixture, player_info_nba_api_source: PlayerInfoNBAApiSource
) -> None:
    mock_class = mocker.patch(
        "nbahl.sources.player_info_nba_api_source.CommonPlayerInfo"
    )
    mocker.patch("tenacity.nap.time.sleep")
    mock_class.return_value.get_data_frames.side_effect = [
        ConnectionError("Timeout"),
        ConnectionError("Timeout"),
        [
            pd.DataFrame(
                data=[
                    {
                        "PERSON_ID": 1,
                        "PLAYER": "Player 1",
                        "HEIGHT": "6-5",
                        "WEIGHT": "250",
                    }
                ]
            )
        ],
    ]

    output_df = player_info_nba_api_source.get_player_info(player_id=1)
    call_kwargs = mock_class.call_args.kwargs

    assert mock_class.call_count == 3
    assert call_kwargs["player_id"] == 1
    assert output_df["PLAYER"].iloc[0] == "Player 1"


def test_get_player_info_failure_after_all_attempts(
    mocker: MockerFixture, player_info_nba_api_source: PlayerInfoNBAApiSource
) -> None:
    mock_class = mocker.patch(
        "nbahl.sources.player_info_nba_api_source.CommonPlayerInfo"
    )
    mocker.patch("tenacity.nap.time.sleep")
    mock_class.return_value.get_data_frames.side_effect = ConnectionError(
        "Timeout"
    )

    with pytest.raises(ConnectionError) as exc_info:
        player_info_nba_api_source.get_player_info(player_id=1)

    assert mock_class.call_count == 3
    assert str(exc_info.value) == "Timeout"


def test_concat_players_detail_info_success(
    mocker: MockerFixture,
    data_dir: Path,
    player_info_nba_api_source: PlayerInfoNBAApiSource,
) -> None:
    mocker.patch(
        "nbahl.sources.player_info_nba_api_source.get_column_ids",
        return_value=[1, 2, 3],
    )
    mocker.patch("nbahl.common.utils.time.sleep")
    mocker.patch.object(
        player_info_nba_api_source,
        "get_player_info",
        side_effect=[
            pd.DataFrame(
                data=[
                    {
                        "PERSON_ID": 1,
                        "Player": "Player 1",
                        "HEIGHT": "6-5",
                        "WEIGHT": "250",
                    }
                ]
            ),
            pd.DataFrame(
                data=[
                    {
                        "PERSON_ID": 2,
                        "Player": "Player 2",
                        "HEIGHT": "6-3",
                        "WEIGHT": "180",
                    }
                ]
            ),
            pd.DataFrame(
                data=[
                    {
                        "PERSON_ID": 3,
                        "Player": "Player 3",
                        "HEIGHT": "7-1",
                        "WEIGHT": "270",
                    }
                ]
            ),
        ],
    )

    output_df = player_info_nba_api_source.concat_players_detail_info(
        filepath=data_dir.joinpath("players-info-1-00.parquet")
    )

    assert len(output_df) == 3
    assert set(output_df["Player"].to_list()) == {
        "Player 1",
        "Player 2",
        "Player 3",
    }


def test_concat_players_detail_info_column_not_found(
    data_dir: Path, player_info_nba_api_source: PlayerInfoNBAApiSource
) -> None:
    filepath = data_dir / "players-info-1-00.parquet"
    write_to_parquet(
        df=pd.DataFrame(
            data=[
                {
                    "PLAYER_ID": 1,
                    "PLAYER": "Player 1",
                    "HEIGHT": "6-5",
                    "WEIGHT": "250",
                }
            ]
        ),
        filepath=filepath,
    )

    with pytest.raises(ColumnNotFoundError) as exc_info:
        player_info_nba_api_source.concat_players_detail_info(
            filepath=filepath
        )

    assert (
        str(exc_info.value)
        == "'PERSON_ID' column not found, columns: ['PLAYER_ID', 'PLAYER', 'HEIGHT', 'WEIGHT']"
    )


def test_concat_players_detail_info_no_dataframes(
    mocker: MockerFixture,
    data_dir: Path,
    player_info_nba_api_source: PlayerInfoNBAApiSource,
) -> None:
    mocker.patch(
        "nbahl.sources.player_info_nba_api_source.get_column_ids",
        return_value=[1, 2, 3],
    )
    mocker.patch.object(
        player_info_nba_api_source,
        "get_player_info",
        side_effect=ConnectionError("Timeout"),
    )

    with pytest.raises(DataFrameEmptyError) as exc_info:
        player_info_nba_api_source.concat_players_detail_info(
            filepath=data_dir.joinpath("players-info-1-00.parquet")
        )

    assert str(exc_info.value) == "No DataFrames for any 'player_id'"


def test_ingest_all_players_info_success(
    mocker: MockerFixture,
    data_dir: Path,
    player_info_nba_api_source: PlayerInfoNBAApiSource,
) -> None:
    mocker.patch.object(
        player_info_nba_api_source,
        "get_all_players_info",
        return_value=pd.DataFrame(
            data=[
                {"PERSON_ID": 1, "Player": "Player 1"},
                {"PERSON_ID": 2, "Player": "Player 2"},
                {"PERSON_ID": 3, "Player": "Player 3"},
            ]
        ),
    )
    mock_db_writer = mocker.MagicMock(spec=DBWriter)
    mock_s3_writer = mocker.MagicMock(spec=S3Writer)
    mocker.patch("nbahl.sources.player_info_nba_api_source.reconcile")

    source_filepath = ingest_all_players_info(
        source=player_info_nba_api_source,
        season="2025-26",
        db_writer=mock_db_writer,
        s3_writer=mock_s3_writer,
    )

    ingestion_run = mock_db_writer.update.call_args.kwargs["ingestion_run"]
    key = mock_s3_writer.write.call_args.kwargs["key"]

    mock_s3_writer.write.assert_called_once()
    mock_db_writer.update.assert_called_once()
    assert ingestion_run.s3_key == "2025-26/players-info-1-00.parquet"
    assert ingestion_run.rows_in == 3
    assert ingestion_run.status == Status.SUCCESS
    assert ingestion_run.error_message is None
    assert key == "2025-26/players-info-1-00.parquet"
    assert source_filepath.as_posix().endswith(
        "2025-26/players-info-1-00.parquet"
    )


def test_ingest_players_detail_info(
    mocker: MockerFixture,
    data_dir: Path,
    player_info_nba_api_source: PlayerInfoNBAApiSource,
) -> None:
    mocker.patch.object(
        player_info_nba_api_source,
        "concat_players_detail_info",
        return_value=pd.DataFrame(
            data=[
                {
                    "PERSON_ID": 1,
                    "Player": "Player 1",
                    "HEIGHT": "6-5",
                    "WEIGHT": "250",
                },
                {
                    "PERSON_ID": 2,
                    "Player": "Player 2",
                    "HEIGHT": "6-3",
                    "WEIGHT": "180",
                },
                {
                    "PERSON_ID": 3,
                    "Player": "Player 3",
                    "HEIGHT": "7-1",
                    "WEIGHT": "270",
                },
            ]
        ),
    )

    mock_db_writer = mocker.MagicMock(spec=DBWriter)
    mock_s3_writer = mocker.MagicMock(spec=S3Writer)
    mocker.patch("nbahl.sources.player_info_nba_api_source.reconcile")
    mocker.patch(
        "nbahl.common.utils.get_current_date", return_value="2026-01-01"
    )

    ingest_players_detail_info(
        source=player_info_nba_api_source,
        source_filepath=data_dir.joinpath(
            "2025-26", "players-info-1-00.parquet"
        ),
        db_writer=mock_db_writer,
        s3_writer=mock_s3_writer,
    )

    ingestion_run = mock_db_writer.update.call_args.kwargs["ingestion_run"]
    key = mock_s3_writer.write.call_args.kwargs["key"]

    mock_s3_writer.write.assert_called_once()
    mock_db_writer.update.assert_called_once()
    assert (
        ingestion_run.s3_key
        == "player-bios/2026-01-01/players-info-1-00.parquet"
    )
    assert ingestion_run.rows_in == 3
    assert ingestion_run.status == Status.SUCCESS
    assert ingestion_run.error_message is None
    assert key == "player-bios/2026-01-01/players-info-1-00.parquet"
