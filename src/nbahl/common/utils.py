from enum import StrEnum
from pathlib import Path

import pandas as pd
import structlog

from nbahl.common.constants import BaseConstants
from nbahl.common.exceptions import ColumnNotFoundError, NoSuffixesError

log = structlog.get_logger()


def get_filepath(data_dir: Path, *, season: str, source_name: str) -> Path:
    """Return the local Parquet path for a given season and dataset name.

    Args:
        data_dir: Root data directory under which season subdirectories live.
        season: NBA season string (e.g. ``"2025-26"``).
        source_name: Logical source name used as the filename stem
            (e.g. ``"league-game-logs-00-t-regular-season"``).

    Returns:
        Absolute path to the Parquet file:
        ``data_dir / season / source_name.parquet``.
    """
    return data_dir.joinpath(season, f"{source_name}.parquet")


def write_to_parquet(df: pd.DataFrame, *, filepath: Path) -> None:
    """Write a DataFrame to Parquet using zstd compression, creating parent dirs.

    Args:
        df: DataFrame to persist.
        filepath: Destination path; parent directories are created if they
            do not exist.
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(filepath, engine="pyarrow", compression="zstd", index=False)


def get_s3_key(filepath: Path, *, idx: int = 2) -> str:
    """Return the S3 object key from the last ``idx`` path components.

    Args:
        filepath: Local file path from which the key is derived.
        idx: Number of trailing path components to join (default ``2``,
            giving ``"<season>/<filename>.parquet"``).

    Returns:
        Forward-slash-joined string of the last ``idx`` path parts.
    """
    return "/".join(filepath.parts[-idx:])


def build_source_name(source_name_prefix: str, suffixes: list[StrEnum]) -> str:
    """Build a kebab-case logical source name from a prefix and enum suffixes.

    Args:
        source_name_prefix: Leading segment of the name
            (e.g. ``"league-game-logs"``).
        suffixes: Ordered list of enum values appended after the prefix; spaces
            are replaced with hyphens and the result is lowercased.

    Returns:
        Hyphen-joined source name string
        (e.g. ``"league-game-logs-00-t-regular-season"``).
    """
    if not suffixes:
        raise NoSuffixesError(
            f"No suffixes are specified for {source_name_prefix!r}"
        )

    source_name = (
        f"{source_name_prefix}-{"-".join(suffixes).lower().replace(" ", "-")}"
    )

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
    season: str, game_id_source_name_prefix: str, extension: str = "parquet"
) -> list[Path]:
    """Glob for game ID source files matching the configured prefix.

    Args:
        season: NBA season string (e.g. ``"2025-26"``); determines the
            subdirectory searched under ``DATA_DIR``.
        game_id_source_name_prefix: Filename prefix used to filter results
            (e.g. ``"league-game-logs"``).
        extension: File extension to match (default ``"parquet"``).

    Returns:
        List of matching file paths; empty when no files are found.
    """
    game_id_source_filepaths = list(
        BaseConstants.DATA_DIR.joinpath(season).glob(
            f"{game_id_source_name_prefix}*.{extension}"
        )
    )

    if not game_id_source_filepaths:
        log.warning(
            "No game ID source files found",
            season=season,
            prefix=game_id_source_name_prefix,
        )

    return game_id_source_filepaths


def get_game_ids(
    season: str, game_id_source_name: str, game_id_column: str = "GAME_ID"
) -> list[str]:
    """Return unique game IDs from a game log Parquet file.

    Args:
        season: NBA season string (e.g. ``"2025-26"``).
        game_id_source_name: Logical source name used to locate the Parquet
            file (e.g. ``"league-game-logs-00-t-regular-season"``).
        game_id_column: Column name containing game IDs
            (default ``"GAME_ID"``).

    Returns:
        Array of unique game ID values from the specified column.

    Raises:
        ColumnNotFoundError: If ``game_id_column`` is not present in the
            Parquet file.
    """
    filepath = get_filepath(
        data_dir=BaseConstants.DATA_DIR,
        season=season,
        source_name=game_id_source_name,
    )
    df = read_from_parquet(filepath=filepath)
    columns = list(df.columns)

    if game_id_column not in columns:
        raise ColumnNotFoundError(
            f"{game_id_column!r} column not found, columns: {columns}"
        )

    game_ids = list(df[game_id_column].unique())

    return game_ids


def collect_game_ids_by_source(
    season: str,
    game_id_source_filepaths: list[Path],
    extension: str = "parquet",
) -> dict[str, list[str]]:
    """Build a mapping from each source name to its unique game IDs.

    Args:
        season: NBA season string (e.g. ``"2025-26"``).
        game_id_source_filepaths: Parquet files whose game IDs should be
            collected, typically from ``get_game_id_source_filepaths``.
        extension: File extension stripped from each filename to derive the
            source name (default ``"parquet"``).

    Returns:
        Dictionary mapping logical source name to an array of unique game IDs.
    """
    game_ids_by_source = {}

    for game_id_source_filepath in game_id_source_filepaths:
        game_id_source_name = game_id_source_filepath.name.replace(
            f".{extension}", ""
        )
        game_ids = get_game_ids(
            season=season, game_id_source_name=game_id_source_name
        )

        game_ids_by_source[game_id_source_name] = game_ids

    total_game_ids = sum(len(ids) for ids in game_ids_by_source.values())
    log.info(
        "Resolved game IDs by source",
        total_sources=len(game_ids_by_source),
        total_game_ids=total_game_ids,
    )

    return game_ids_by_source


def add_game_id_source_name(
    df: pd.DataFrame, game_id_source_name: str
) -> pd.DataFrame:
    """Annotate a play-by-play DataFrame with the originating source name.

    Args:
        df: Play-by-play DataFrame to annotate.
        game_id_source_name: Logical source name written to the
            ``source_name`` column.

    Returns:
        The same DataFrame with a ``source_name`` column added.
    """
    df["source_name"] = game_id_source_name

    return df
