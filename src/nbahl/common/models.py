from datetime import datetime

from pydantic import BaseModel

from nbahl.common.enums import Status


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
