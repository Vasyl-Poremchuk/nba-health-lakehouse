from pathlib import Path

import pandas as pd
import pytest
from pytest_mock import MockerFixture

from nbahl.common.constants import (
    BaseConstants,
    GameLogNBAApiSourceConstants,
    PlayByPlayNBAApiSourceConstants,
)
from nbahl.common.enums import (
    IsOnlyCurrentSeason,
    LeagueID,
    Period,
    PlayerOrTeamAbbreviation,
    SeasonTypeAllStar,
)
from nbahl.sources.box_score_nba_api_source import BoxScoreNBAApiSource
from nbahl.sources.game_log_nba_api_source import GameLogNBAApiSource
from nbahl.sources.play_by_play_nba_api_source import PlayByPlayNBAApiSource
from nbahl.sources.player_info_nba_api_source import PlayerInfoNBAApiSource
from nbahl.sources.team_roster_nba_api_source import TeamRosterNBAApiSource


@pytest.fixture
def data_dir(mocker: MockerFixture, tmp_path: Path) -> Path:
    """Patch ``BaseConstants.DATA_DIR`` to a temporary directory.

    Args:
        mocker: Pytest-mock fixture used to patch the class attribute.
        tmp_path: Pytest-provided temporary directory unique to the test.

    Returns:
        The temporary directory now used as the local data root.
    """
    return mocker.patch.object(BaseConstants, "DATA_DIR", tmp_path)


@pytest.fixture
def league_game_logs_00_t_regular_season_df() -> pd.DataFrame:
    """Build a sample NBA team-level regular season game log DataFrame.

    Returns:
        Two-row DataFrame of team game log rows in the shape returned by
        the NBA Stats API ``LeagueGameLog`` endpoint.
    """
    data = [
        {
            "SEASON_ID": "22025",
            "TEAM_ID": 1610612745,
            "TEAM_ABBREVIATION": "HOU",
            "TEAM_NAME": "Houston Rockets",
            "GAME_ID": "0022500001",
            "GAME_DATE": "2025-10-21",
            "MATCHUP": "HOU @ OKC",
            "WL": "L",
            "MIN": 290,
            "FGM": 43,
            "FGA": 97,
            "FG_PCT": 0.443,
            "FG3M": 11,
            "FG3A": 39,
            "FG3_PCT": 0.282,
            "FTM": 27,
            "FTA": 31,
            "FT_PCT": 0.871,
            "OREB": 16,
            "DREB": 36,
            "REB": 52,
            "AST": 23,
            "STL": 6,
            "BLK": 5,
            "TOV": 25,
            "PF": 26,
            "PTS": 124,
            "PLUS_MINUS": -1,
            "VIDEO_AVAILABLE": 1,
        },
        {
            "SEASON_ID": "22025",
            "TEAM_ID": 1610612747,
            "TEAM_ABBREVIATION": "LAL",
            "TEAM_NAME": "Los Angeles Lakers",
            "GAME_ID": "0022500002",
            "GAME_DATE": "2025-10-21",
            "MATCHUP": "LAL vs. GSW",
            "WL": "L",
            "MIN": 240,
            "FGM": 42,
            "FGA": 77,
            "FG_PCT": 0.545,
            "FG3M": 8,
            "FG3A": 32,
            "FG3_PCT": 0.25,
            "FTM": 17,
            "FTA": 28,
            "FT_PCT": 0.607,
            "OREB": 7,
            "DREB": 32,
            "REB": 39,
            "AST": 23,
            "STL": 7,
            "BLK": 2,
            "TOV": 20,
            "PF": 21,
            "PTS": 109,
            "PLUS_MINUS": -10,
            "VIDEO_AVAILABLE": 1,
        },
    ]

    return pd.DataFrame(data=data)


@pytest.fixture
def game_log_nba_api_source() -> GameLogNBAApiSource:
    """Build a ``GameLogNBAApiSource`` configured for NBA team regular season logs.

    Returns:
        A ``GameLogNBAApiSource`` instance parameterized for
        ``LeagueID.NBA``, ``PlayerOrTeamAbbreviation.TEAM``, and
        ``SeasonTypeAllStar.REGULAR_SEASON``.
    """
    return GameLogNBAApiSource(
        league_id=LeagueID.NBA,
        player_or_team_abbreviation=PlayerOrTeamAbbreviation.TEAM,
        season_type_all_star=SeasonTypeAllStar.REGULAR_SEASON,
    )


@pytest.fixture
def source_df(request: pytest.FixtureRequest) -> pd.DataFrame:
    """Resolve a named DataFrame fixture by string for indirect parametrization.

    Args:
        request: Pytest fixture request object; ``request.param`` must be the
            name of another fixture that returns a ``pd.DataFrame``.

    Returns:
        The DataFrame produced by the named fixture.
    """
    return request.getfixturevalue(request.param)


@pytest.fixture
def play_by_play_logs_0_0_df() -> pd.DataFrame:
    """Build a sample play-by-play log DataFrame for a single game.

    Returns:
        One-row DataFrame containing a period-start action in the shape
        returned by the NBA Stats API ``PlayByPlayV3`` endpoint.
    """
    data = [
        {
            "gameId": "0022500001",
            "actionNumber": 2,
            "clock": "PT12M00.00S",
            "period": 1,
            "teamId": 0,
            "teamTricode": "",
            "personId": 0,
            "playerName": "",
            "playerNameI": "",
            "xLegacy": 0,
            "yLegacy": 0,
            "shotDistance": 0,
            "shotResult": "",
            "isFieldGoal": 0,
            "scoreHome": "0",
            "scoreAway": "0",
            "pointsTotal": 0,
            "location": "",
            "description": "Start of 1st Period (10:18 PM EST)",
            "actionType": "period",
            "subType": "start",
            "videoAvailable": 1,
            "shotValue": 0,
            "actionId": 1,
        }
    ]

    return pd.DataFrame(data=data)


@pytest.fixture
def play_by_play_nba_api_source() -> PlayByPlayNBAApiSource:
    """Build a ``PlayByPlayNBAApiSource`` configured for all periods.

    Returns:
        A ``PlayByPlayNBAApiSource`` instance parameterized with
        ``Period.ALL`` for both ``start_period`` and ``end_period``, and
        ``GameLogNBAApiSourceConstants.SOURCE_NAME_PREFIX`` as the game ID
        source name prefix.
    """
    return PlayByPlayNBAApiSource(
        start_period=Period.ALL,
        end_period=Period.ALL,
        game_id_source_name_prefix=GameLogNBAApiSourceConstants.SOURCE_NAME_PREFIX,
    )


@pytest.fixture
def box_score_nba_api_source() -> BoxScoreNBAApiSource:
    """Build a ``BoxScoreNBAApiSource`` configured for all periods.

    Returns:
        A ``BoxScoreNBAApiSource`` instance parameterized with
        ``Period.ALL`` for both ``start_period`` and ``end_period``, and
        ``PlayByPlayNBAApiSourceConstants.SOURCE_NAME_PREFIX`` as the game ID
        source name prefix.
    """
    return BoxScoreNBAApiSource(
        start_period=Period.ALL,
        end_period=Period.ALL,
        game_id_source_name_prefix=PlayByPlayNBAApiSourceConstants.SOURCE_NAME_PREFIX,
    )


@pytest.fixture
def player_info_nba_api_source() -> PlayerInfoNBAApiSource:
    return PlayerInfoNBAApiSource(
        is_only_current_season=IsOnlyCurrentSeason.CURRENT_SEASON_ONLY,
        league_id=LeagueID.NBA,
    )


@pytest.fixture
def team_roster_nba_api_source() -> TeamRosterNBAApiSource:
    return TeamRosterNBAApiSource(league_id=LeagueID.NBA)
