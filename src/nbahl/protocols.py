from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

import pandas as pd

if TYPE_CHECKING:
    from nbahl.common.models import BoxScoreContext


@runtime_checkable
class GameLogSource(Protocol):
    """Protocol for data sources that provide NBA game logs."""

    def get_game_logs(self, season: str) -> pd.DataFrame:
        """Fetch game logs for the given season.

        Args:
            season: NBA season string (e.g. ``"2025-26"``).

        Returns:
            DataFrame containing all game log rows for the season.
        """


@runtime_checkable
class BoxScoreSource(Protocol):
    """Protocol for data sources that provide NBA box score game logs."""

    def get_box_score_game_logs(
        self,
        game_ids_by_source: dict[str, list[str]],
        box_score_context: BoxScoreContext,
    ) -> dict[str, pd.DataFrame]:
        """Fetch box score game logs for the given games and box score variant.

        Args:
            game_ids_by_source: Mapping of source name to game IDs to fetch,
                typically from ``get_game_ids_by_source``; the season is
                implicit in which games this mapping was built from.
            box_score_context: Configuration specifying the endpoint, datasets,
                and period settings.

        Returns:
            Mapping of dataset name to a DataFrame of box score rows for the
            given games.
        """


@runtime_checkable
class PlayerInfoSource(Protocol):
    """Protocol for data sources that provide NBA player info."""

    def get_all_players_info(self, season: str) -> pd.DataFrame:
        """Fetch the bulk list of all players for the given season.

        Args:
            season: NBA season string (e.g. ``"2025-26"``).

        Returns:
            DataFrame containing one lightweight bio row per player.
        """

    def get_player_info(self, player_id: str) -> pd.DataFrame:
        """Fetch detailed profile info for a single player.

        Args:
            player_id: NBA API player identifier.

        Returns:
            DataFrame containing the detailed profile row for the player.
        """


@runtime_checkable
class TeamRosterSource(Protocol):
    """Protocol for data sources that provide NBA team roster info."""

    def get_team_roster_info(
        self, team_id: str, season: str
    ) -> dict[str, pd.DataFrame]:
        """Fetch roster and coaching staff info for a single team.

        Args:
            team_id: NBA API team identifier.
            season: NBA season string (e.g. ``"2025-26"``).

        Returns:
            Mapping of dataset name (``"roster"``, ``"coaches"``) to the
            corresponding DataFrame for the team.
        """
