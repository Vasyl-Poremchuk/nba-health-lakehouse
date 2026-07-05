from pathlib import Path

import pandas as pd
import pytest

from nbahl.common.constants import BaseConstants
from nbahl.common.utils import get_filepath, get_s3_key, write_to_parquet


def test_get_filepath(data_dir: Path) -> None:
    filepath = get_filepath(
        data_dir,
        season="2025-26",
        source_name="league-game-logs-00-t-regular-season",
    )

    assert filepath.as_posix().endswith(
        "2025-26/league-game-logs-00-t-regular-season.parquet"
    )


def test_write_to_parquet(
    data_dir: Path,
    league_game_logs_00_t_regular_season_df: pd.DataFrame,
) -> None:
    filepath = data_dir / "league-game-logs-00-t-regular-season.parquet"
    write_to_parquet(
        league_game_logs_00_t_regular_season_df, filepath=filepath
    )

    output_df = pd.read_parquet(filepath)

    assert output_df.equals(league_game_logs_00_t_regular_season_df)


@pytest.mark.parametrize(
    "filepath, idx, expected_s3_key",
    [
        (
            BaseConstants.DATA_DIR.joinpath(
                "2025-26", "league-game-logs-00-t-regular-season.parquet"
            ),
            2,
            "2025-26/league-game-logs-00-t-regular-season.parquet",
        ),
        (
            BaseConstants.DATA_DIR.joinpath(
                "2025-26", "league-game-logs-00-t-regular-season.parquet"
            ),
            1,
            "league-game-logs-00-t-regular-season.parquet",
        ),
    ],
)
def test_get_s3_key(filepath: Path, idx: int, expected_s3_key: str) -> None:
    s3_key = get_s3_key(filepath=filepath, idx=idx)

    assert s3_key == expected_s3_key
