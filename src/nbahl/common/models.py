from datetime import datetime
from pathlib import Path

from nba_api.stats.endpoints._base import Endpoint
from pydantic import BaseModel, ConfigDict

from nbahl.common.enums import Status
from nbahl.protocols import GameLogSource


class IngestionRun(BaseModel):
    """Metadata record for a single pipeline ingestion run.

    Attributes:
        s3_key: S3 object key of the uploaded Parquet file.
        started_at: UTC timestamp when the ingestion began.
        ended_at: UTC timestamp when the ingestion finished; ``None`` while PENDING.
        rows_in: Number of rows fetched; ``None`` while PENDING or on failure.
        status: Current outcome of the run.
        error_message: Exception message on failure; ``None`` otherwise.
    """

    s3_key: str
    started_at: datetime
    ended_at: datetime | None = None
    rows_in: int | None = None
    status: Status
    error_message: str | None = None


class IngestionContext(BaseModel):
    """Runtime context passed through the ingestion pipeline.

    Attributes:
        source_name: Logical identifier for the data source
            (e.g. ``"league-game-logs-00-t-regular-season"``).
        season: NBA season string (e.g. ``"2025-26"``).
        filepath: Local Parquet file path where ingested data is written.
        s3_key: S3 object key used when uploading the Parquet file.
        source: Data source instance that provides ``get_game_logs``.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    source_name: str
    season: str
    filepath: Path
    s3_key: str
    source: GameLogSource


class BoxScoreContext(BaseModel):
    """Runtime configuration for a single box score API endpoint variant.

    Attributes:
        box_score_class: The nba_api endpoint class to instantiate
            (e.g. ``BoxScoreTraditionalV3``).
        datasets: Ordered list of dataset names corresponding to the positional
            DataFrames returned by ``get_data_frames()``.
        includes_periods: Whether to forward ``start_period`` and ``end_period``
            to the endpoint. ``False`` for endpoints that do not accept period
            arguments (e.g. ``BoxScoreSummaryV3``).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    box_score_class: type[Endpoint]
    datasets: list[str]
    includes_periods: bool = True
