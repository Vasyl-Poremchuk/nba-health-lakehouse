from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pytest_mock import MockerFixture
from requests.exceptions import ConnectionError

from nbahl.common.enums import Period, Status
from nbahl.common.exceptions import (
    ColumnNotFoundError,
    GameIDsBySourceEmptyError,
)
from nbahl.sources.play_by_play_nba_api_source import (
    PlayByPlayNBAApiSource,
    ingest_play_by_play_game_logs,
)
from nbahl.writers.db_writer import DBWriter
from nbahl.writers.s3_writer import S3Writer


@pytest.mark.parametrize(
    "season, extension, filenames, expected_game_id_source_filenames",
    [
        (
            "2025-26",
            "parquet",
            [
                "league-game-logs-00-t-regular-season.parquet",
                "league-game-logs-00-t-pre-season.parquet",
                "league-game-logs-00-t-playoffs.parquet",
                "league-game-logs-00-t-all-star.parquet",
            ],
            [
                "league-game-logs-00-t-regular-season.parquet",
                "league-game-logs-00-t-pre-season.parquet",
                "league-game-logs-00-t-playoffs.parquet",
                "league-game-logs-00-t-all-star.parquet",
            ],
        ),
        (
            "2025-26",
            "csv",
            [
                "league-game-logs-00-t-regular-season.csv",
                "league-game-logs-00-t-pre-season.csv",
                "league-game-logs-00-t-playoffs.csv",
                "league-game-logs-00-t-all-star.csv",
            ],
            [
                "league-game-logs-00-t-regular-season.csv",
                "league-game-logs-00-t-pre-season.csv",
                "league-game-logs-00-t-playoffs.csv",
                "league-game-logs-00-t-all-star.csv",
            ],
        ),
        (
            "2025-26",
            "parquet",
            [
                "league-game-logs-00-t-regular-season.parquet",
                "league-game-logs-00-t-pre-season.parquet",
                "league-game-logs-00-t-playoffs.csv",
                "league-game-logs-00-t-all-star.csv",
            ],
            [
                "league-game-logs-00-t-regular-season.parquet",
                "league-game-logs-00-t-pre-season.parquet",
            ],
        ),
        (
            "2025-26",
            "csv",
            [
                "league-game-logs-00-t-regular-season.parquet",
                "league-game-logs-00-t-pre-season.parquet",
                "league-game-logs-00-t-playoffs.parquet",
                "league-game-logs-00-t-all-star.parquet",
            ],
            [],
        ),
        (
            "2025-26",
            "parquet",
            [
                "league-game-logs-00-t-regular-season.parquet",
                "00-t-pre-season.parquet",
                "league-game-logs-00-t-playoffs.csv",
                "league-game-logs-00-t-all-star.csv",
            ],
            ["league-game-logs-00-t-regular-season.parquet"],
        ),
        (
            "2025-26",
            "csv",
            [
                "league-game-logs-00-t-regular-season.parquet",
                "league-game-logs-00-t-pre-season.parquet",
                "00-t-playoffs.csv",
                "00-t-all-star.csv",
            ],
            [],
        ),
        ("2025-26", "parquet", [], []),
    ],
)
def test_get_game_id_source_filepaths(
    play_by_play_nba_api_source: PlayByPlayNBAApiSource,
    data_dir: Path,
    season: str,
    extension: str,
    filenames: list[str],
    expected_game_id_source_filenames: list[str],
) -> None:
    df = pd.DataFrame()
    season_dir = data_dir / season
    season_dir.mkdir(parents=True, exist_ok=True)

    for filename in filenames:
        filepath = season_dir / filename

        if filename.endswith(".parquet"):
            df.to_parquet(filepath, engine="pyarrow")
        elif filename.endswith(".csv"):
            df.to_csv(filepath)

    game_id_source_filepaths = (
        play_by_play_nba_api_source._get_game_id_source_filepaths(
            season=season, extension=extension
        )
    )
    game_id_source_filenames = [
        game_id_source_filepath.name
        for game_id_source_filepath in game_id_source_filepaths
    ]

    assert set(game_id_source_filenames) == set(
        expected_game_id_source_filenames
    )


def test_get_game_ids_success(
    play_by_play_nba_api_source: PlayByPlayNBAApiSource,
    data_dir: Path,
    league_game_logs_00_t_regular_season_df: pd.DataFrame,
) -> None:
    season_dir = data_dir / "2025-26"
    season_dir.mkdir(parents=True, exist_ok=True)
    filepath = season_dir / "league-game-logs-00-t-regular-season.parquet"
    league_game_logs_00_t_regular_season_df.to_parquet(
        filepath, engine="pyarrow", index=False
    )

    game_ids = play_by_play_nba_api_source._get_game_ids(
        season="2025-26",
        game_id_source_name="league-game-logs-00-t-regular-season",
        game_id_column="GAME_ID",
    )

    assert set(game_ids) == {"0022500001", "0022500002"}


def test_get_game_ids_no_game_id_column(
    play_by_play_nba_api_source: PlayByPlayNBAApiSource,
    data_dir: Path,
    league_game_logs_00_t_regular_season_df: pd.DataFrame,
) -> None:
    season_dir = data_dir / "2025-26"
    season_dir.mkdir(parents=True, exist_ok=True)
    filepath = season_dir / "league-game-logs-00-t-regular-season.parquet"
    league_game_logs_00_t_regular_season_df = (
        league_game_logs_00_t_regular_season_df.drop(columns=["GAME_ID"])
    )
    league_game_logs_00_t_regular_season_df.to_parquet(
        filepath, engine="pyarrow", index=False
    )

    with pytest.raises(
        ColumnNotFoundError, match="'GAME_ID' column not found"
    ) as exc_info:
        play_by_play_nba_api_source._get_game_ids(
            season="2025-26",
            game_id_source_name="league-game-logs-00-t-regular-season",
            game_id_column="GAME_ID",
        )

    assert str(exc_info.value) == (
        "'GAME_ID' column not found, columns: "
        "['SEASON_ID', 'TEAM_ID', 'TEAM_ABBREVIATION', 'TEAM_NAME', "
        "'GAME_DATE', 'MATCHUP', 'WL', 'MIN', 'FGM', 'FGA', 'FG_PCT', "
        "'FG3M', 'FG3A', 'FG3_PCT', 'FTM', 'FTA', 'FT_PCT', 'OREB', "
        "'DREB', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'PF', 'PTS', "
        "'PLUS_MINUS', 'VIDEO_AVAILABLE']"
    )


def test_collect_game_ids_by_source(
    play_by_play_nba_api_source: PlayByPlayNBAApiSource,
    data_dir: Path,
    league_game_logs_00_t_regular_season_df: pd.DataFrame,
) -> None:
    season_dir = data_dir / "2025-26"
    season_dir.mkdir(parents=True, exist_ok=True)
    filepath = season_dir / "league-game-logs-00-t-regular-season.parquet"
    league_game_logs_00_t_regular_season_df.to_parquet(
        filepath, engine="pyarrow", index=False
    )

    game_ids_by_source = (
        play_by_play_nba_api_source.collect_game_ids_by_source(
            season="2025-26",
            game_id_source_filepaths=[filepath],
            extension="parquet",
        )
    )

    assert "league-game-logs-00-t-regular-season" in game_ids_by_source
    assert set(game_ids_by_source["league-game-logs-00-t-regular-season"]) == {
        "0022500001",
        "0022500002",
    }


def test_collect_game_ids_by_source_no_source_filepaths(
    play_by_play_nba_api_source: PlayByPlayNBAApiSource,
) -> None:
    game_ids_by_source = (
        play_by_play_nba_api_source.collect_game_ids_by_source(
            season="2025-26", game_id_source_filepaths=[], extension="parquet"
        )
    )

    assert game_ids_by_source == {}


def test_add_game_id_source_name(
    play_by_play_nba_api_source: PlayByPlayNBAApiSource,
    play_by_play_logs_0_0_df: pd.DataFrame,
) -> None:
    df = play_by_play_nba_api_source._add_game_id_source_name(
        df=play_by_play_logs_0_0_df,
        game_id_source_name="league-game-logs-00-t-regular-season",
    )

    assert "source_name" in df.columns
    assert len(df["source_name"].unique()) == 1
    assert df["source_name"].iloc[0] == "league-game-logs-00-t-regular-season"


def test_get_game_logs_success(
    mocker: MockerFixture,
    play_by_play_nba_api_source: PlayByPlayNBAApiSource,
    play_by_play_logs_0_0_df: pd.DataFrame,
) -> None:
    mocker.patch.object(
        play_by_play_nba_api_source,
        "collect_game_ids_by_source",
        return_value={
            "league-game-logs-00-t-regular-season": np.array(["0022500001"])
        },
    )
    mock_class = mocker.patch(
        "nbahl.sources.play_by_play_nba_api_source.PlayByPlayV3"
    )
    mocker.patch("nbahl.sources.play_by_play_nba_api_source.time.sleep")
    mock_class.return_value.get_data_frames.return_value = [
        play_by_play_logs_0_0_df
    ]

    output_df = play_by_play_nba_api_source.get_game_logs(season="2025-26")
    mock_class.assert_called_once()
    call_kwargs = mock_class.call_args.kwargs

    assert call_kwargs["game_id"] == "0022500001"
    assert call_kwargs["start_period"] == Period.ALL
    assert call_kwargs["end_period"] == Period.ALL
    assert (
        output_df["source_name"].iloc[0]
        == "league-game-logs-00-t-regular-season"
    )
    assert output_df.equals(play_by_play_logs_0_0_df)


def test_get_game_logs_success_after_second_attempt(
    mocker: MockerFixture,
    play_by_play_nba_api_source: PlayByPlayNBAApiSource,
    play_by_play_logs_0_0_df: pd.DataFrame,
) -> None:
    mocker.patch.object(
        play_by_play_nba_api_source,
        "collect_game_ids_by_source",
        return_value={
            "league-game-logs-00-t-regular-season": np.array(["0022500001"])
        },
    )
    mock_class = mocker.patch(
        "nbahl.sources.play_by_play_nba_api_source.PlayByPlayV3"
    )
    mocker.patch("tenacity.nap.time.sleep")
    mocker.patch("nbahl.sources.play_by_play_nba_api_source.time.sleep")
    mock_class.return_value.get_data_frames.side_effect = [
        ConnectionError("Timeout"),
        [play_by_play_logs_0_0_df],
    ]

    output_df = play_by_play_nba_api_source.get_game_logs(season="2025-26")

    assert mock_class.call_count == 2
    assert (
        output_df["source_name"].iloc[0]
        == "league-game-logs-00-t-regular-season"
    )
    assert output_df.equals(play_by_play_logs_0_0_df)


def test_get_game_logs_success_after_third_attempt(
    mocker: MockerFixture,
    play_by_play_nba_api_source: PlayByPlayNBAApiSource,
    play_by_play_logs_0_0_df: pd.DataFrame,
) -> None:
    mocker.patch.object(
        play_by_play_nba_api_source,
        "collect_game_ids_by_source",
        return_value={
            "league-game-logs-00-t-regular-season": np.array(["0022500001"])
        },
    )
    mock_class = mocker.patch(
        "nbahl.sources.play_by_play_nba_api_source.PlayByPlayV3"
    )
    mocker.patch("tenacity.nap.time.sleep")
    mocker.patch("nbahl.sources.play_by_play_nba_api_source.time.sleep")
    mock_class.return_value.get_data_frames.side_effect = [
        ConnectionError("Timeout"),
        ConnectionError("Timeout"),
        [play_by_play_logs_0_0_df],
    ]

    output_df = play_by_play_nba_api_source.get_game_logs(season="2025-26")

    assert mock_class.call_count == 3
    assert (
        output_df["source_name"].iloc[0]
        == "league-game-logs-00-t-regular-season"
    )
    assert output_df.equals(play_by_play_logs_0_0_df)


def test_get_game_logs_failure_after_all_attempts(
    mocker: MockerFixture, play_by_play_nba_api_source: PlayByPlayNBAApiSource
) -> None:
    mocker.patch.object(
        play_by_play_nba_api_source,
        "collect_game_ids_by_source",
        return_value={
            "league-game-logs-00-t-regular-season": np.array(["0022500001"])
        },
    )
    mock_class = mocker.patch(
        "nbahl.sources.play_by_play_nba_api_source.PlayByPlayV3"
    )
    mock_class.return_value.get_data_frames.side_effect = [
        ConnectionError("Timeout"),
        ConnectionError("Timeout"),
        ConnectionError("Timeout"),
    ]
    mocker.patch("tenacity.nap.time.sleep")
    mocker.patch("nbahl.sources.play_by_play_nba_api_source.time.sleep")

    with pytest.raises(ConnectionError) as exc_info:
        play_by_play_nba_api_source.get_game_logs(season="2025-26")

    assert mock_class.call_count == 3
    assert str(exc_info.value) == "Timeout"


@pytest.mark.parametrize(
    "return_value", [{}, {"league-game-logs-00-t-regular-season": []}]
)
def test_get_game_logs_failure_for_no_game_ids_by_source(
    mocker: MockerFixture,
    play_by_play_nba_api_source: PlayByPlayNBAApiSource,
    return_value: dict[str, list[str]],
) -> None:
    mock_collect_game_ids_by_source = mocker.patch.object(
        play_by_play_nba_api_source,
        "collect_game_ids_by_source",
        return_value=return_value,
    )
    mocker.patch("tenacity.nap.time.sleep")

    with pytest.raises(GameIDsBySourceEmptyError) as exc_info:
        play_by_play_nba_api_source.get_game_logs(season="2025-26")

    assert mock_collect_game_ids_by_source.call_count == 1
    assert str(exc_info.value) == "There are no game IDs for the source"


def test_ingest_play_by_play_game_logs_success(
    mocker: MockerFixture, play_by_play_logs_0_0_df: pd.DataFrame
) -> None:
    mocker.patch.object(
        PlayByPlayNBAApiSource,
        "get_game_logs",
        return_value=play_by_play_logs_0_0_df,
    )

    mock_db_writer = mocker.MagicMock(spec=DBWriter)
    mock_s3_writer = mocker.MagicMock(spec=S3Writer)

    ingest_play_by_play_game_logs(
        season="2025-26",
        start_period=Period.ALL,
        end_period=Period.ALL,
        db_writer=mock_db_writer,
        s3_writer=mock_s3_writer,
    )

    mock_s3_writer.write.assert_called_once()
    mock_db_writer.write.assert_called_once()
    ingestion_run = mock_db_writer.write.call_args.kwargs["ingestion_run"]
    key = mock_s3_writer.write.call_args.kwargs["key"]

    assert ingestion_run.source == "play-by-play-logs-0-0"
    assert ingestion_run.rows_in == 1
    assert ingestion_run.status == Status.SUCCESS
    assert ingestion_run.error_message is None
    assert key == "2025-26/play-by-play-logs-0-0.parquet"
