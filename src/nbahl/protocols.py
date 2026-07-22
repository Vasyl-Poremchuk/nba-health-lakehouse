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
        season: str,
        game_ids_by_source: dict[str, list[str]],
        box_score_context: BoxScoreContext,
    ) -> dict[str, pd.DataFrame]:
        """Fetch box score game logs for the given season and box score variant.

        Args:
            season: NBA season string (e.g. ``"2025-26"``).
            game_ids_by_source: Mapping of source name to game IDs to fetch,
                typically from ``get_game_ids_by_source``.
            box_score_context: Configuration specifying the endpoint, datasets,
                and period settings.

        Returns:
            Mapping of dataset name to a DataFrame of box score rows for the
            season.
        """
