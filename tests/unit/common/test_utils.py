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
from nbahl.common.exceptions import ColumnNotFoundError, NoSuffixesError
from nbahl.common.utils import (
    add_game_id_source_name,
    build_source_name,
    collect_game_ids_by_source,
    get_filepath,
    get_game_id_source_filepaths,
    get_game_ids,
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
    ) as exc_info:
        build_source_name(
            source_name_prefix=GameLogNBAApiSourceConstants.SOURCE_NAME_PREFIX,
            suffixes=[],
        )

    assert (
        str(exc_info.value)
        == "No suffixes are specified for 'league-game-logs'"
    )


@pytest.mark.parametrize(
    "season, game_id_source_name_prefix, extension, filenames, expected_game_id_source_filenames",
    [
        (
            "2025-26",
            "league-game-logs",
            "parquet",
            [
                "league-game-logs-00-t-regular-season.parquet",
                "league-game-logs-00-t-pre-season.parquet",
                "league-game-logs-00-t-playoffs.parquet",
                "league-game-logs-00-t-all-star.parquet",
            ],
            [
                "league-game-logs-00-t-regular-season.parquet",
                "league-game-logs-00-t-pre-season.parquet",
                "league-game-logs-00-t-playoffs.parquet",
                "league-game-logs-00-t-all-star.parquet",
            ],
        ),
        (
            "2025-26",
            "league-game-logs",
            "csv",
            [
                "league-game-logs-00-t-regular-season.csv",
                "league-game-logs-00-t-pre-season.csv",
                "league-game-logs-00-t-playoffs.csv",
                "league-game-logs-00-t-all-star.csv",
            ],
            [
                "league-game-logs-00-t-regular-season.csv",
                "league-game-logs-00-t-pre-season.csv",
                "league-game-logs-00-t-playoffs.csv",
                "league-game-logs-00-t-all-star.csv",
            ],
        ),
        (
            "2025-26",
            "league-game-logs",
            "parquet",
            [
                "league-game-logs-00-t-regular-season.parquet",
                "league-game-logs-00-t-pre-season.parquet",
                "league-game-logs-00-t-playoffs.csv",
                "league-game-logs-00-t-all-star.csv",
            ],
            [
                "league-game-logs-00-t-regular-season.parquet",
                "league-game-logs-00-t-pre-season.parquet",
            ],
        ),
        (
            "2025-26",
            "league-game-logs",
            "csv",
            [
                "league-game-logs-00-t-regular-season.parquet",
                "league-game-logs-00-t-pre-season.parquet",
                "league-game-logs-00-t-playoffs.parquet",
                "league-game-logs-00-t-all-star.parquet",
            ],
            [],
        ),
        (
            "2025-26",
            "league-game-logs",
            "parquet",
            [
                "league-game-logs-00-t-regular-season.parquet",
                "00-t-pre-season.parquet",
                "league-game-logs-00-t-playoffs.csv",
                "league-game-logs-00-t-all-star.csv",
            ],
            ["league-game-logs-00-t-regular-season.parquet"],
        ),
        (
            "2025-26",
            "league-game-logs",
            "csv",
            [
                "league-game-logs-00-t-regular-season.parquet",
                "league-game-logs-00-t-pre-season.parquet",
                "00-t-playoffs.csv",
                "00-t-all-star.csv",
            ],
            [],
        ),
        ("2025-26", "league-game-logs", "parquet", [], []),
    ],
)
def test_get_game_id_source_filepaths(
    data_dir: Path,
    season: str,
    game_id_source_name_prefix: str,
    extension: str,
    filenames: list[str],
    expected_game_id_source_filenames: list[str],
) -> None:
    df = pd.DataFrame()
    season_dir = data_dir / season
    season_dir.mkdir(parents=True, exist_ok=True)

    for filename in filenames:
        filepath = season_dir / filename

        if filename.endswith(".parquet"):
            df.to_parquet(filepath, engine="pyarrow")
        elif filename.endswith(".csv"):
            df.to_csv(filepath)

    game_id_source_filepaths = get_game_id_source_filepaths(
        season=season,
        game_id_source_name_prefix=game_id_source_name_prefix,
        extension=extension,
    )
    game_id_source_filenames = [
        game_id_source_filepath.name
        for game_id_source_filepath in game_id_source_filepaths
    ]

    assert set(game_id_source_filenames) == set(
        expected_game_id_source_filenames
    )


def test_get_game_ids_success(
    data_dir: Path,
    league_game_logs_00_t_regular_season_df: pd.DataFrame,
) -> None:
    season_dir = data_dir / "2025-26"
    season_dir.mkdir(parents=True, exist_ok=True)
    filepath = season_dir / "league-game-logs-00-t-regular-season.parquet"
    league_game_logs_00_t_regular_season_df.to_parquet(
        filepath, engine="pyarrow", index=False
    )

    game_ids = get_game_ids(
        season="2025-26",
        game_id_source_name="league-game-logs-00-t-regular-season",
        game_id_column="GAME_ID",
    )

    assert set(game_ids) == {"0022500001", "0022500002"}


def test_get_game_ids_no_game_id_column(
    data_dir: Path,
    league_game_logs_00_t_regular_season_df: pd.DataFrame,
) -> None:
    season_dir = data_dir / "2025-26"
    season_dir.mkdir(parents=True, exist_ok=True)
    filepath = season_dir / "league-game-logs-00-t-regular-season.parquet"
    league_game_logs_00_t_regular_season_df = (
        league_game_logs_00_t_regular_season_df.drop(columns=["GAME_ID"])
    )
    league_game_logs_00_t_regular_season_df.to_parquet(
        filepath, engine="pyarrow", index=False
    )

    with pytest.raises(
        ColumnNotFoundError, match="'GAME_ID' column not found"
    ) as exc_info:
        get_game_ids(
            season="2025-26",
            game_id_source_name="league-game-logs-00-t-regular-season",
            game_id_column="GAME_ID",
        )

    assert str(exc_info.value) == (
        "'GAME_ID' column not found, columns: "
        "['SEASON_ID', 'TEAM_ID', 'TEAM_ABBREVIATION', 'TEAM_NAME', "
        "'GAME_DATE', 'MATCHUP', 'WL', 'MIN', 'FGM', 'FGA', 'FG_PCT', "
        "'FG3M', 'FG3A', 'FG3_PCT', 'FTM', 'FTA', 'FT_PCT', 'OREB', "
        "'DREB', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'PF', 'PTS', "
        "'PLUS_MINUS', 'VIDEO_AVAILABLE']"
    )


def test_collect_game_ids_by_source(
    data_dir: Path,
    league_game_logs_00_t_regular_season_df: pd.DataFrame,
) -> None:
    season_dir = data_dir / "2025-26"
    season_dir.mkdir(parents=True, exist_ok=True)
    filepath = season_dir / "league-game-logs-00-t-regular-season.parquet"
    league_game_logs_00_t_regular_season_df.to_parquet(
        filepath, engine="pyarrow", index=False
    )

    game_ids_by_source = collect_game_ids_by_source(
        season="2025-26",
        game_id_source_filepaths=[filepath],
        extension="parquet",
    )

    assert "league-game-logs-00-t-regular-season" in game_ids_by_source
    assert set(game_ids_by_source["league-game-logs-00-t-regular-season"]) == {
        "0022500001",
        "0022500002",
    }


def test_collect_game_ids_by_source_no_source_filepaths() -> None:
    game_ids_by_source = collect_game_ids_by_source(
        season="2025-26", game_id_source_filepaths=[], extension="parquet"
    )

    assert game_ids_by_source == {}


def test_add_game_id_source_name(
    play_by_play_logs_0_0_df: pd.DataFrame,
) -> None:
    df = add_game_id_source_name(
        df=play_by_play_logs_0_0_df,
        game_id_source_name="league-game-logs-00-t-regular-season",
    )

    assert "source_name" in df.columns
    assert len(df["source_name"].unique()) == 1
    assert df["source_name"].iloc[0] == "league-game-logs-00-t-regular-season"
