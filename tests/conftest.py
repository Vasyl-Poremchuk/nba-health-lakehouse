from pathlib import Path

import pandas as pd
import pytest
from pytest_mock import MockerFixture

from nbahl.common.constants import BaseConstants, GameLogNBAApiSourceConstants
from nbahl.common.enums import (
    LeagueID,
    PlayerOrTeamAbbreviation,
    SeasonTypeAllStar,
)
from nbahl.sources.game_log_nba_api_source import GameLogNBAApiSource


@pytest.fixture(scope="function")
def data_dir(mocker: MockerFixture, tmp_path: Path) -> Path:
    """Patch ``BaseConstants.DATA_DIR`` to a temporary directory.

    Args:
        mocker: Pytest-mock fixture used to patch the class attribute.
        tmp_path: Pytest-provided temporary directory unique to the test.

    Returns:
        The temporary directory now used as the local data root.
    """
    return mocker.patch.object(BaseConstants, "DATA_DIR", tmp_path)


@pytest.fixture(scope="function")
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


@pytest.fixture(scope="function")
def league_game_log_constants() -> GameLogNBAApiSourceConstants:
    """Build a ``GameLogNBAApiSourceConstants`` instance.

    Returns:
        A plain ``GameLogNBAApiSourceConstants`` instance.
    """
    return GameLogNBAApiSourceConstants()


@pytest.fixture(scope="function")
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
