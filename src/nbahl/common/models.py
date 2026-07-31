from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pandas as pd
from nba_api.stats.endpoints.boxscoreadvancedv3 import BoxScoreAdvancedV3
from nba_api.stats.endpoints.boxscoresummaryv3 import BoxScoreSummaryV3
from nba_api.stats.endpoints.boxscoretraditionalv3 import BoxScoreTraditionalV3
from pydantic import BaseModel, ConfigDict

from nbahl.common.enums import Status


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


class ArbitraryTypesModel(BaseModel):
    """Base model for contexts that carry non-Pydantic types (e.g. DataFrames,
    Callables that aren't plain functions).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)


class SourceRunContext(BaseModel):
    """Identifying fields shared by ``IngestionContext`` and ``CommitContext``.

    Attributes:
        source_name: Logical identifier for the data source
            (e.g. ``"league-game-logs-00-t-regular-season"``).
        s3_key: S3 object key the dataset is (or would be) uploaded to.
        season: NBA season string (e.g. ``"2025-26"``); ``None`` for sources
            that aren't season-scoped.
    """

    source_name: str
    s3_key: str
    season: str | None = None


class IngestionContext(SourceRunContext, ArbitraryTypesModel):
    """Runtime context passed through the ingestion pipeline.

    Attributes:
        filepath: Local Parquet file path where ingested data is written.
        fetch_function: Zero-arg callable that fetches and returns the data
            to ingest, e.g. ``partial(source.get_game_logs, season=season)``.
    """

    filepath: Path
    fetch_function: Callable[[], pd.DataFrame]


class CommitContext(SourceRunContext):
    """Shared identifying fields for a single dataset's commit outcome.

    Attributes:
        run_id: Primary key of the ``ingestion_runs`` row this commit updates.
        started_at: UTC timestamp when the ingestion run began.
    """

    run_id: int
    started_at: datetime


class SuccessCommitContext(CommitContext, ArbitraryTypesModel):
    """Commit context for a dataset that fetched successfully.

    Attributes:
        dataset_df: Fetched DataFrame to write and upload.
        filepath: Local Parquet file path to write ``dataset_df`` to.
    """

    dataset_df: pd.DataFrame
    filepath: Path


class FailureCommitContext(CommitContext):
    """Commit context for a dataset whose fetch or write/upload failed.

    Attributes:
        error_message: String representation of the exception that caused
            the failure.
    """

    error_message: str


class IngestionContextPerDataset(ArbitraryTypesModel):
    """Runtime context for an ingestion that fetches multiple datasets at once.

    One shared ``fetch_function`` call returns all datasets, which are then
    written and recorded individually - see ``run_ingestion_per_dataset``.

    Attributes:
        source_names: Logical identifier for each dataset, positionally
            aligned with ``filepaths``, ``s3_keys``, and ``datasets``.
        season: NBA season string (e.g. ``"2025-26"``); ``None`` for sources
            that aren't season-scoped.
        filepaths: Local Parquet file path for each dataset.
        s3_keys: S3 object key for each dataset.
        datasets: Dataset names used as keys into the dict returned by
            ``fetch_function``.
        fetch_function: Zero-arg callable that fetches and returns a mapping
            of dataset name to DataFrame for all datasets at once.
    """

    source_names: list[str]
    season: str | None = None
    filepaths: list[Path]
    s3_keys: list[str]
    datasets: list[str]
    fetch_function: Callable[[], dict[str, pd.DataFrame]]


class BoxScoreContext(ArbitraryTypesModel):
    """Runtime configuration for a single box score API endpoint variant.

    Attributes:
        box_score_class: The nba_api endpoint class to instantiate -
            one of ``BoxScoreTraditionalV3``, ``BoxScoreAdvancedV3``, or
            ``BoxScoreSummaryV3``.
        datasets: Ordered list of dataset names corresponding to the positional
            DataFrames returned by ``get_data_frames()``.
        includes_periods: Whether to forward ``start_period`` and ``end_period``
            to the endpoint. ``False`` for endpoints that do not accept period
            arguments (e.g. ``BoxScoreSummaryV3``).
    """

    box_score_class: (
        type[BoxScoreTraditionalV3]
        | type[BoxScoreAdvancedV3]
        | type[BoxScoreSummaryV3]
    )
    datasets: list[str]
    includes_periods: bool = True
