from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from nbahl.common.enums import Status
from nbahl.protocols import GameLogSource


class IngestionRun(BaseModel):
    """Metadata record for a single pipeline ingestion run.

    Attributes:
        source: Logical name of the data source
            (e.g. ``"league-game-logs-00-t-regular-season"``).
        started_at: UTC timestamp when the ingestion began.
        ended_at: UTC timestamp when the ingestion finished.
        rows_in: Number of rows successfully ingested; ``None`` on failure.
        status: Outcome of the run.
        error_message: Exception message captured on failure; ``None`` on success.
    """

    source: str
    started_at: datetime
    ended_at: datetime
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
