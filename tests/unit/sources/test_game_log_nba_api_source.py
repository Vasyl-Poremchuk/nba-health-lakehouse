import pandas as pd
import pytest
from pytest_mock import MockerFixture
from requests.exceptions import ConnectionError

from nbahl.common.enums import (
    LeagueID,
    PlayerOrTeamAbbreviation,
    SeasonTypeAllStar,
    Status,
)
from nbahl.sources.game_log_nba_api_source import (
    GameLogNBAApiSource,
    ingest_league_game_logs,
)
from nbahl.writers.db_writer import DBWriter
from nbahl.writers.s3_writer import S3Writer


def test_get_game_logs_success(
    mocker: MockerFixture,
    game_log_nba_api_source: GameLogNBAApiSource,
    league_game_logs_00_t_regular_season_df: pd.DataFrame,
) -> None:
    mock_class = mocker.patch(
        "nbahl.sources.game_log_nba_api_source.LeagueGameLog"
    )
    mock_class.return_value.get_data_frames.return_value = [
        league_game_logs_00_t_regular_season_df
    ]

    output_df = game_log_nba_api_source.get_game_logs(season="2025-26")
    mock_class.assert_called_once()
    call_kwargs = mock_class.call_args.kwargs

    assert call_kwargs["season"] == "2025-26"
    assert call_kwargs["league_id"] == LeagueID.NBA
    assert (
        call_kwargs["player_or_team_abbreviation"]
        == PlayerOrTeamAbbreviation.TEAM
    )
    assert (
        call_kwargs["season_type_all_star"] == SeasonTypeAllStar.REGULAR_SEASON
    )
    assert output_df.equals(league_game_logs_00_t_regular_season_df)


def test_get_game_logs_success_after_second_attempt(
    mocker: MockerFixture,
    game_log_nba_api_source: GameLogNBAApiSource,
    league_game_logs_00_t_regular_season_df: pd.DataFrame,
) -> None:
    mock_class = mocker.patch(
        "nbahl.sources.game_log_nba_api_source.LeagueGameLog"
    )
    mocker.patch("tenacity.nap.time.sleep")
    mock_class.return_value.get_data_frames.side_effect = [
        ConnectionError("Timeout"),
        [league_game_logs_00_t_regular_season_df],
    ]

    output_df = game_log_nba_api_source.get_game_logs(season="2025-26")

    assert mock_class.call_count == 2
    assert output_df.equals(league_game_logs_00_t_regular_season_df)


def test_get_game_logs_success_after_third_attempt(
    mocker: MockerFixture,
    game_log_nba_api_source: GameLogNBAApiSource,
    league_game_logs_00_t_regular_season_df: pd.DataFrame,
) -> None:
    mock_class = mocker.patch(
        "nbahl.sources.game_log_nba_api_source.LeagueGameLog"
    )
    mocker.patch("tenacity.nap.time.sleep")
    mock_class.return_value.get_data_frames.side_effect = [
        ConnectionError("Timeout"),
        ConnectionError("Timeout"),
        [league_game_logs_00_t_regular_season_df],
    ]

    output_df = game_log_nba_api_source.get_game_logs(season="2025-26")

    assert mock_class.call_count == 3
    assert output_df.equals(league_game_logs_00_t_regular_season_df)


def test_get_game_logs_failure_after_all_attempts(
    mocker: MockerFixture,
    game_log_nba_api_source: GameLogNBAApiSource,
) -> None:
    mock_class = mocker.patch(
        "nbahl.sources.game_log_nba_api_source.LeagueGameLog"
    )
    mocker.patch("tenacity.nap.time.sleep")
    mock_class.return_value.get_data_frames.side_effect = [
        ConnectionError("Timeout"),
        ConnectionError("Timeout"),
        ConnectionError("Timeout"),
    ]

    with pytest.raises(ConnectionError) as exp_info:
        game_log_nba_api_source.get_game_logs(season="2025-26")

    assert mock_class.call_count == 3
    assert str(exp_info.value) == "Timeout"


def test_ingest_league_game_logs_success(
    mocker: MockerFixture,
    league_game_logs_00_t_regular_season_df: pd.DataFrame,
) -> None:
    mocker.patch.object(
        GameLogNBAApiSource,
        "get_game_logs",
        return_value=league_game_logs_00_t_regular_season_df,
    )

    mock_db_writer = mocker.MagicMock(spec=DBWriter)
    mock_s3_writer = mocker.MagicMock(spec=S3Writer)

    ingest_league_game_logs(
        season="2025-26",
        league_id=LeagueID.NBA,
        player_or_team_abbreviation=PlayerOrTeamAbbreviation.TEAM,
        season_type=SeasonTypeAllStar.REGULAR_SEASON,
        db_writer=mock_db_writer,
        s3_writer=mock_s3_writer,
    )

    mock_s3_writer.write.assert_called_once()
    mock_db_writer.write.assert_called_once()
    ingestion_run = mock_db_writer.write.call_args.kwargs["ingestion_run"]
    key = mock_s3_writer.write.call_args.kwargs["key"]

    assert ingestion_run.source == "league-game-logs-00-t-regular-season"
    assert ingestion_run.status == Status.SUCCESS
    assert ingestion_run.rows_in == len(
        league_game_logs_00_t_regular_season_df
    )
    assert ingestion_run.error_message is None
    assert key == "2025-26/league-game-logs-00-t-regular-season.parquet"
