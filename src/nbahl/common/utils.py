from enum import StrEnum
from pathlib import Path

import pandas as pd

from nbahl.common.exceptions import NoSuffixesError


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
