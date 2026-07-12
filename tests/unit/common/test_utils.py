from enum import StrEnum
from pathlib import Path

import pandas as pd
import pytest

from nbahl.common.constants import (
    BaseConstants,
    GameLogNBAApiSourceConstants,
    PlayByPlayNBAApiSourceConstants,
)
from nbahl.common.enums import (
    LeagueID,
    Period,
    PlayerOrTeamAbbreviation,
    SeasonTypeAllStar,
)
from nbahl.common.exceptions import NoSuffixesError
from nbahl.common.utils import (
    build_source_name,
    get_filepath,
    get_s3_key,
    read_from_parquet,
    write_to_parquet,
)


def test_get_filepath(data_dir: Path) -> None:
    filepath = get_filepath(
        data_dir,
        season="2025-26",
        source_name="league-game-logs-00-t-regular-season",
    )

    assert filepath.as_posix().endswith(
        "2025-26/league-game-logs-00-t-regular-season.parquet"
    )


def test_write_to_read_from_parquet(
    data_dir: Path,
    league_game_logs_00_t_regular_season_df: pd.DataFrame,
) -> None:
    filepath = data_dir / "league-game-logs-00-t-regular-season.parquet"
    write_to_parquet(
        league_game_logs_00_t_regular_season_df, filepath=filepath
    )

    output_df = read_from_parquet(filepath)

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


@pytest.mark.parametrize(
    "source_name_prefix, suffixes, expected_source_name",
    [
        (
            GameLogNBAApiSourceConstants.SOURCE_NAME_PREFIX,
            [
                LeagueID.NBA,
                PlayerOrTeamAbbreviation.TEAM,
                SeasonTypeAllStar.REGULAR_SEASON,
            ],
            "league-game-logs-00-t-regular-season",
        ),
        (
            PlayByPlayNBAApiSourceConstants.SOURCE_NAME_PREFIX,
            [Period.ALL, Period.ALL],
            "play-by-play-logs-0-0",
        ),
    ],
)
def test_build_source_name(
    source_name_prefix: str, suffixes: list[StrEnum], expected_source_name: str
) -> None:
    source_name = build_source_name(
        source_name_prefix=source_name_prefix, suffixes=suffixes
    )

    assert source_name == expected_source_name


def test_build_source_name_no_suffixes() -> None:
    with pytest.raises(
        NoSuffixesError, match="No suffixes are specified"
    ) as exp_info:
        build_source_name(
            source_name_prefix=GameLogNBAApiSourceConstants.SOURCE_NAME_PREFIX,
            suffixes=[],
        )

    assert (
        str(exp_info.value)
        == "No suffixes are specified for 'league-game-logs'"
    )
