from typing import Protocol

import pandas as pd


class LeagueGameLogSource(Protocol):
    """Protocol for data sources that provide NBA league game logs."""

    def get_game_logs(self, season: str) -> pd.DataFrame:
        """Fetch game logs for the given season.

        Args:
            season: NBA season string (e.g. ``"2025-26"``).

        Returns:
            DataFrame containing all game log rows for the season.
        """
