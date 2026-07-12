from typing import Protocol, runtime_checkable

import pandas as pd


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
