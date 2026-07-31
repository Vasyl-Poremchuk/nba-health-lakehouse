import time
from collections.abc import Callable
from datetime import UTC, datetime
from enum import IntEnum, StrEnum
from pathlib import Path

import pandas as pd
import structlog

from nbahl.common.constants import BaseConstants
from nbahl.common.enums import Status
from nbahl.common.exceptions import (
    ColumnNotFoundError,
    DataFrameEmptyError,
    GameIDsBySourceEmptyError,
    NoSuffixesError,
)
from nbahl.common.models import (
    FailureCommitContext,
    IngestionRun,
    SuccessCommitContext,
)
from nbahl.writers.db_writer import DBWriter
from nbahl.writers.s3_writer import S3Writer

log = structlog.get_logger()


def get_filepath(
    data_dir: Path,
    *,
    source_name: str,
    season: str | None = None,
    source_dir: str | None = None,
) -> Path:
    """Return the local Parquet path for a season- or date-scoped dataset.

    Args:
        data_dir: Root data directory under which season or source
            subdirectories live.
        source_name: Logical source name used as the filename stem
            (e.g. ``"league-game-logs-00-t-regular-season"``).
        season: NBA season string (e.g. ``"2025-26"``); used for
            season-scoped sources.
        source_dir: Top-level directory grouping a non-season-scoped
            source's dated outputs (e.g. ``"player_bios"``); used together
            with today's date instead of ``season``.

    Returns:
        ``data_dir / season / source_name.parquet`` when ``season`` is given
        and ``source_dir`` is not; otherwise
        ``data_dir / source_dir / <today> / source_name.parquet``.

    Raises:
        ValueError: If neither ``season`` nor ``source_dir`` is provided.
    """
    filename = f"{source_name}.parquet"

    if season and source_dir is None:
        return data_dir.joinpath(season, filename)

    if source_dir is not None:
        return data_dir.joinpath(source_dir, get_current_date(), filename)

    raise ValueError("Either season or source_dir must be provided")


def write_to_parquet(df: pd.DataFrame, *, filepath: Path) -> None:
    """Write a DataFrame to Parquet using zstd compression, creating parent dirs.

    Args:
        df: DataFrame to persist.
        filepath: Destination path; parent directories are created if they
            do not exist.
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(filepath, engine="pyarrow", compression="zstd", index=False)


def get_s3_key(filepath: Path, *, num_trailing_parts: int = 2) -> str:
    """Return the S3 object key from the last ``num_trailing_parts`` path components.

    Args:
        filepath: Local file path from which the key is derived.
        num_trailing_parts: Number of trailing path components to join
            (default ``2``, giving ``"<season>/<filename>.parquet"``).

    Returns:
        Forward-slash-joined string of the last ``num_trailing_parts`` path
        parts.
    """
    return "/".join(filepath.parts[-num_trailing_parts:])


def build_source_name(
    source_name_prefix: str, suffixes: list[StrEnum | str | IntEnum]
) -> str:
    """Build a kebab-case logical source name from a prefix and enum suffixes.

    Args:
        source_name_prefix: Leading segment of the name
            (e.g. ``"league-game-logs"``).
        suffixes: Ordered list of enum values appended after the prefix; spaces
            are replaced with hyphens and the result is lowercased.

    Returns:
        Hyphen-joined source name string
        (e.g. ``"league-game-logs-00-t-regular-season"``).

    Raises:
        NoSuffixesError: If ``suffixes`` is empty.
    """
    if not suffixes:
        raise NoSuffixesError(
            f"No suffixes are specified for {source_name_prefix!r}"
        )

    suffix = "-".join(str(_) for _ in suffixes).lower().replace(" ", "-")
    source_name = f"{source_name_prefix}-{suffix}"

    return source_name


def read_from_parquet(filepath: Path) -> pd.DataFrame:
    """Read a Parquet file into a DataFrame using the PyArrow engine.

    Args:
        filepath: Path to the Parquet file to read.

    Returns:
        DataFrame containing the contents of the Parquet file.
    """
    return pd.read_parquet(filepath, engine="pyarrow")


def get_game_id_source_filepaths(
    season: str, game_id_source_name_prefix: str
) -> list[Path]:
    """Glob for game ID source files matching the configured prefix.

    Args:
        season: NBA season string (e.g. ``"2025-26"``); determines the
            subdirectory searched under ``DATA_DIR``.
        game_id_source_name_prefix: Filename prefix used to filter results
            (e.g. ``"league-game-logs"``).

    Returns:
        List of matching file paths; empty when no files are found.
    """
    game_id_source_filepaths = list(
        BaseConstants.DATA_DIR.joinpath(season).glob(
            f"{game_id_source_name_prefix}*.parquet"
        )
    )

    if not game_id_source_filepaths:
        log.warning(
            "No game ID source files found",
            season=season,
            prefix=game_id_source_name_prefix,
        )

    return game_id_source_filepaths


def get_column_ids(filepath: Path, *, id_column: str) -> list[str]:
    """Return unique values from a column of a Parquet file.

    Args:
        filepath: Path to the Parquet file to read.
        id_column: Column name whose unique values should be returned
            (e.g. ``"PERSON_ID"``, ``"TEAM_ID"``).

    Returns:
        List of unique values from ``id_column``.

    Raises:
        ColumnNotFoundError: If ``id_column`` is not present in the file.
    """
    df = read_from_parquet(filepath=filepath)
    columns = list(df.columns)

    if id_column not in columns:
        raise ColumnNotFoundError(
            f"{id_column!r} column not found, columns: {columns}"
        )

    column_ids = list(df[id_column].unique())

    return column_ids


def collect_game_ids_by_source(
    season: str,
    game_id_source_filepaths: list[Path],
    *,
    game_id_column: str = "GAME_ID",
) -> dict[str, list[str]]:
    """Build a mapping from each source name to its unique game IDs.

    Args:
        season: NBA season string (e.g. ``"2025-26"``).
        game_id_source_filepaths: Parquet files whose game IDs should be
            collected, typically from ``get_game_id_source_filepaths``.
        game_id_column: Column name containing game IDs
            (default ``"GAME_ID"``).

    Returns:
        Dictionary mapping logical source name to a list of unique game IDs.
    """
    game_ids_by_source = {}

    for game_id_source_filepath in game_id_source_filepaths:
        game_id_source_name = game_id_source_filepath.name.replace(
            ".parquet", ""
        )
        filepath = get_filepath(
            data_dir=BaseConstants.DATA_DIR,
            source_name=game_id_source_name,
            season=season,
        )
        game_ids = get_column_ids(filepath=filepath, id_column=game_id_column)

        game_ids_by_source[game_id_source_name] = game_ids

    total_game_ids = sum(calculate_item_lengths(items=game_ids_by_source))
    log.info(
        "Resolved game IDs by source",
        total_sources=len(game_ids_by_source),
        total_game_ids=total_game_ids,
    )

    return game_ids_by_source


def add_game_id_source_name(
    df: pd.DataFrame, game_id_source_name: str
) -> pd.DataFrame:
    """Annotate a DataFrame with the originating source name.

    Args:
        df: DataFrame to annotate.
        game_id_source_name: Logical source name written to the
            ``source_name`` column.

    Returns:
        The same DataFrame with a ``source_name`` column added.
    """
    df["source_name"] = game_id_source_name

    return df


def zip_datasets(
    datasets: list[str], dfs: list[pd.DataFrame]
) -> dict[str, pd.DataFrame]:
    """Zip dataset names with their positionally matching DataFrames.

    Args:
        datasets: Ordered list of dataset names from the endpoint configuration.
        dfs: DataFrames returned by ``get_data_frames()``, in the same
            positional order as ``datasets``.

    Returns:
        Mapping of dataset name to the corresponding DataFrame.

    Raises:
        ValueError: If ``datasets`` and ``dfs`` have different lengths.
    """
    dataset_map = dict(zip(datasets, dfs, strict=True))

    return dataset_map


def calculate_item_lengths(
    items: dict[str, list[str] | list[pd.DataFrame]],
) -> list[int]:
    """Return the length of each value in a dict.

    Args:
        items: Mapping whose values support ``len()``.

    Returns:
        List of lengths in dict-iteration order.
    """
    item_lengths = [len(item) for item in items.values()]

    return item_lengths


def get_game_ids_by_source(
    season: str,
    game_id_source_name_prefix: str,
    *,
    game_id_column: str = "GAME_ID",
) -> dict[str, list[str]]:
    """Collect game IDs from previously ingested source files.

    Globs for Parquet files matching ``game_id_source_name_prefix`` under the
    season directory, reads unique game IDs from each file, and returns them
    grouped by source name.

    Args:
        season: NBA season string (e.g. ``"2025-26"``).
        game_id_source_name_prefix: Filename prefix used to glob for the
            Parquet files that supply game IDs.
        game_id_column: Column name containing game IDs
            (default ``"GAME_ID"``).

    Returns:
        Mapping of source name to a list of unique game IDs.

    Raises:
        GameIDsBySourceEmptyError: If no game IDs are found across all
            matching source files.
    """
    game_id_source_filepaths = get_game_id_source_filepaths(
        season=season, game_id_source_name_prefix=game_id_source_name_prefix
    )
    game_ids_by_source = collect_game_ids_by_source(
        season=season,
        game_id_source_filepaths=game_id_source_filepaths,
        game_id_column=game_id_column,
    )

    if not any(calculate_item_lengths(items=game_ids_by_source)):
        raise GameIDsBySourceEmptyError("There are no game IDs for the source")

    return game_ids_by_source


def build_context_attributes(
    source_name_prefix: str,
    suffixes: list[StrEnum | str | IntEnum],
    *,
    season: str | None = None,
    source_dir: str | None = None,
    num_trailing_parts: int = 2,
) -> dict[str, str | Path]:
    """Build the source name, local filepath, and S3 key for an ingestion context.

    Args:
        source_name_prefix: Leading segment of the source name
            (e.g. ``"play-by-play-logs"``).
        suffixes: Ordered list of enum values appended after the prefix.
        season: NBA season string (e.g. ``"2025-26"``); forwarded to
            ``get_filepath`` for season-scoped sources.
        source_dir: Top-level directory grouping a non-season-scoped
            source's dated outputs; forwarded to ``get_filepath``.
        num_trailing_parts: Number of trailing path components to join into
            the S3 key; forwarded to ``get_s3_key``.

    Returns:
        Dict with keys ``source_name``, ``filepath``, and ``s3_key``. Still
        missing ``season`` and ``fetch_function``, so it must be combined
        with those before unpacking into ``IngestionContext``.
    """
    source_name = build_source_name(
        source_name_prefix=source_name_prefix, suffixes=suffixes
    )
    filepath = get_filepath(
        data_dir=BaseConstants.DATA_DIR,
        source_name=source_name,
        season=season,
        source_dir=source_dir,
    )
    s3_key = get_s3_key(
        filepath=filepath, num_trailing_parts=num_trailing_parts
    )

    context_attributes: dict[str, str | Path] = {
        "source_name": source_name,
        "filepath": filepath,
        "s3_key": s3_key,
    }

    return context_attributes


def get_current_datetime() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(tz=UTC)


def get_current_date() -> str:
    """Return today's UTC date as an ISO-8601 string (e.g. ``"2025-10-21"``)."""
    return get_current_datetime().date().isoformat()


def fetch_data_by_column_ids_per_dataset(
    column_ids: list[str],
    id_label: str,
    fetch_function: Callable[[str], dict[str, pd.DataFrame]],
) -> dict[str, pd.DataFrame]:
    """Fetch and concatenate multiple datasets per ID, tolerating partial failures.

    Calls ``fetch_function(column_id)`` for each ID in turn, sleeping
    ``BaseConstants.SLEEP_SECONDS`` after each successful fetch. IDs that fail
    are skipped and logged, up to ``BaseConstants.MAX_TOTAL_FAILURE_NUMBER``
    total failures; the next failure past that limit is re-raised.
    ``fetch_function`` returns a mapping of dataset name to DataFrame for each
    ID; results are concatenated per dataset.

    Args:
        column_ids: IDs to fetch data for (e.g. team IDs).
        id_label: Label used in log messages and the empty-result error
            (e.g. ``"team_id"``).
        fetch_function: Callable that takes a single ID and returns a mapping
            of dataset name to DataFrame.

    Returns:
        Mapping of dataset name to the concatenated DataFrame of all
        successfully fetched rows for that dataset.

    Raises:
        DataFrameEmptyError: If every ID failed to fetch.
        Exception: Re-raised once the total failure count reaches
            ``BaseConstants.MAX_TOTAL_FAILURE_NUMBER``.
    """
    dfs_by_dataset: dict[str, list[pd.DataFrame]] = {}
    failed_ids: list[str] = []
    total_failures = 0

    for column_id in column_ids:
        log.info("Fetching data", id_label=id_label, id=str(column_id))

        try:
            mapped_dfs = fetch_function(column_id)

            for dataset, df in mapped_dfs.items():
                dfs_by_dataset.setdefault(dataset, []).append(df)

            time.sleep(BaseConstants.SLEEP_SECONDS)
        except Exception as exc:
            log.warning(
                "Fetching data failed",
                id_label=id_label,
                id=str(column_id),
                error=str(exc),
            )

            if total_failures >= BaseConstants.MAX_TOTAL_FAILURE_NUMBER:
                raise

            failed_ids.append(str(column_id))
            total_failures += 1

    if failed_ids:
        log.warning(
            "Some IDs failed to fetch and were skipped",
            id_label=id_label,
            total_failed=len(failed_ids),
            failed_ids=failed_ids,
        )

    if not dfs_by_dataset or not all(_ for _ in dfs_by_dataset.values()):
        raise DataFrameEmptyError(f"No DataFrames for any {id_label!r}")

    fetched_data = {
        dataset: pd.concat(objs=dataset_dfs)
        for dataset, dataset_dfs in dfs_by_dataset.items()
    }

    log.info(
        "Fetched all data",
        total_rows=sum(calculate_item_lengths(items=fetched_data)),
    )

    return fetched_data


def fetch_data_by_column_ids(
    column_ids: list[str],
    id_label: str,
    fetch_function: Callable[[str], pd.DataFrame],
) -> pd.DataFrame:
    """Fetch and concatenate one DataFrame per ID, tolerating partial failures.

    Thin wrapper around ``fetch_data_by_column_ids_per_dataset`` that treats
    the single DataFrame returned by ``fetch_function`` as the only dataset
    in a single-key mapping, then unwraps it.

    Args:
        column_ids: IDs to fetch data for (e.g. player IDs).
        id_label: Label used in log messages and the empty-result error
            (e.g. ``"player_id"``).
        fetch_function: Callable that takes a single ID and returns a
            DataFrame.

    Returns:
        Concatenated DataFrame of all successfully fetched rows.

    Raises:
        DataFrameEmptyError: If every ID failed to fetch.
        Exception: Re-raised once the total failure count reaches
            ``BaseConstants.MAX_TOTAL_FAILURE_NUMBER``.
    """
    sentinel_dataset = "_single_dataset_"
    fetched_data = fetch_data_by_column_ids_per_dataset(
        column_ids=column_ids,
        id_label=id_label,
        fetch_function=lambda column_id: {
            sentinel_dataset: fetch_function(column_id)
        },
    )

    return fetched_data[sentinel_dataset]


def commit_success(
    context: SuccessCommitContext, db_writer: DBWriter, s3_writer: S3Writer
) -> None:
    """Write, upload, and record a dataset that was fetched successfully.

    Phase 2 (success branch) of the 2-phase commit: writes
    ``context.dataset_df`` to Parquet, uploads it to S3, then marks the
    existing ``PENDING`` DB record ``SUCCESS`` with ``rows_in``.

    Args:
        context: Fetched DataFrame plus the identifiers needed to write,
            upload, and update the DB record.
        db_writer: Writer used to update the ingestion run metadata.
        s3_writer: Writer used to upload the Parquet file to S3.

    Raises:
        DataFrameEmptyError: If ``context.dataset_df`` is empty.
    """
    rows_in = len(context.dataset_df)

    if context.dataset_df.empty:
        raise DataFrameEmptyError("DataFrame is empty")

    write_to_parquet(df=context.dataset_df, filepath=context.filepath)
    log.debug(
        "Wrote Parquet file",
        filepath=context.filepath.as_posix(),
        rows=rows_in,
    )

    s3_writer.write(filepath=context.filepath, key=context.s3_key)
    log.debug("Uploaded file to S3", key=context.s3_key)

    db_writer.update(
        run_id=context.run_id,
        ingestion_run=IngestionRun(
            s3_key=context.s3_key,
            started_at=context.started_at,
            ended_at=get_current_datetime(),
            rows_in=rows_in,
            status=Status.SUCCESS,
        ),
    )

    log.info(
        "Ingestion succeeded",
        run_id=context.run_id,
        s3_key=context.s3_key,
        rows_in=rows_in,
    )


def commit_failure(context: FailureCommitContext, db_writer: DBWriter) -> None:
    """Record a dataset whose fetch, write, or upload failed.

    Phase 2 (failure branch) of the 2-phase commit: marks the existing
    ``PENDING`` DB record ``FAILURE`` with ``context.error_message`` as the
    error message.

    Args:
        context: Identifiers for the failed run plus the exception message.
        db_writer: Writer used to update the ingestion run metadata.
    """
    db_writer.update(
        run_id=context.run_id,
        ingestion_run=IngestionRun(
            s3_key=context.s3_key,
            started_at=context.started_at,
            ended_at=get_current_datetime(),
            status=Status.FAILURE,
            error_message=context.error_message,
        ),
    )

    log.error(
        "Ingestion failed",
        run_id=context.run_id,
        s3_key=context.s3_key,
        error=context.error_message,
        exc_info=True,
    )
