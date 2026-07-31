from pathlib import Path

import pandas as pd
import pytest
from pytest_mock import MockerFixture
from requests.exceptions import ConnectionError

from nbahl.common.enums import LeagueID, Status
from nbahl.common.exceptions import ColumnNotFoundError, DataFrameEmptyError
from nbahl.common.utils import write_to_parquet
from nbahl.sources.team_roster_nba_api_source import (
    TeamRosterNBAApiSource,
    ingest_team_rosters_info,
)
from nbahl.writers.db_writer import DBWriter
from nbahl.writers.s3_writer import S3Writer


def test_get_team_roster_info_success(
    mocker: MockerFixture, team_roster_nba_api_source: TeamRosterNBAApiSource
) -> None:
    mock_class = mocker.patch(
        "nbahl.sources.team_roster_nba_api_source.CommonTeamRoster"
    )
    mock_class.return_value.get_data_frames.return_value = [
        pd.DataFrame(
            data=[
                {"PLAYER_ID": 1, "PLAYER": "Player 1", "TEAM_ID": "01"},
                {"PLAYER_ID": 2, "PLAYER": "Player 2", "TEAM_ID": "01"},
            ]
        ),
        pd.DataFrame(
            data=[
                {"COACH_ID": 1, "COACH": "Coach 1", "TEAM_ID": "01"},
                {"COACH_ID": 2, "COACH": "Coach 2", "TEAM_ID": "01"},
            ]
        ),
    ]

    info_dfs = team_roster_nba_api_source.get_team_roster_info(
        team_id="01", season="2025-26"
    )
    call_kwargs = mock_class.call_args.kwargs

    mock_class.assert_called_once()
    assert call_kwargs["team_id"] == "01"
    assert call_kwargs["season"] == "2025-26"
    assert set(info_dfs.keys()) == {"roster", "coaches"}


def test_get_team_roster_info_success_after_second_attempt(
    mocker: MockerFixture, team_roster_nba_api_source: TeamRosterNBAApiSource
) -> None:
    mock_class = mocker.patch(
        "nbahl.sources.team_roster_nba_api_source.CommonTeamRoster"
    )
    mocker.patch("tenacity.nap.time.sleep")
    mock_class.return_value.get_data_frames.side_effect = [
        ConnectionError("Timeout"),
        [
            pd.DataFrame(
                data=[
                    {"PLAYER_ID": 1, "PLAYER": "Player 1", "TEAM_ID": "01"},
                    {"PLAYER_ID": 2, "PLAYER": "Player 2", "TEAM_ID": "01"},
                ]
            ),
            pd.DataFrame(
                data=[
                    {"COACH_ID": 1, "COACH": "Coach 1", "TEAM_ID": "01"},
                    {"COACH_ID": 2, "COACH": "Coach 2", "TEAM_ID": "01"},
                ]
            ),
        ],
    ]

    info_dfs = team_roster_nba_api_source.get_team_roster_info(
        team_id="01", season="2025-26"
    )
    call_kwargs = mock_class.call_args.kwargs

    assert mock_class.call_count == 2
    assert call_kwargs["team_id"] == "01"
    assert call_kwargs["season"] == "2025-26"
    assert set(info_dfs.keys()) == {"roster", "coaches"}


def test_get_team_roster_info_success_after_third_attempt(
    mocker: MockerFixture, team_roster_nba_api_source: TeamRosterNBAApiSource
) -> None:
    mock_class = mocker.patch(
        "nbahl.sources.team_roster_nba_api_source.CommonTeamRoster"
    )
    mocker.patch("tenacity.nap.time.sleep")
    mock_class.return_value.get_data_frames.side_effect = [
        ConnectionError("Timeout"),
        ConnectionError("Timeout"),
        [
            pd.DataFrame(
                data=[
                    {"PLAYER_ID": 1, "PLAYER": "Player 1", "TEAM_ID": "01"},
                    {"PLAYER_ID": 2, "PLAYER": "Player 2", "TEAM_ID": "01"},
                ]
            ),
            pd.DataFrame(
                data=[
                    {"COACH_ID": 1, "COACH": "Coach 1", "TEAM_ID": "01"},
                    {"COACH_ID": 2, "COACH": "Coach 2", "TEAM_ID": "01"},
                ]
            ),
        ],
    ]

    info_dfs = team_roster_nba_api_source.get_team_roster_info(
        team_id="01", season="2025-26"
    )
    call_kwargs = mock_class.call_args.kwargs

    assert mock_class.call_count == 3
    assert call_kwargs["team_id"] == "01"
    assert call_kwargs["season"] == "2025-26"
    assert set(info_dfs.keys()) == {"roster", "coaches"}


def test_get_team_roster_info_failure_after_all_attempts(
    mocker: MockerFixture, team_roster_nba_api_source: TeamRosterNBAApiSource
) -> None:
    mock_class = mocker.patch(
        "nbahl.sources.team_roster_nba_api_source.CommonTeamRoster"
    )
    mocker.patch("tenacity.nap.time.sleep")
    mock_class.return_value.get_data_frames.side_effect = ConnectionError(
        "Timeout"
    )

    with pytest.raises(ConnectionError) as exc_info:
        team_roster_nba_api_source.get_team_roster_info(
            team_id="01", season="2025-26"
        )

    assert mock_class.call_count == 3
    assert str(exc_info.value) == "Timeout"


def test_concat_team_rosters_info_success(
    mocker: MockerFixture,
    data_dir: Path,
    team_roster_nba_api_source: TeamRosterNBAApiSource,
) -> None:
    mocker.patch(
        "nbahl.sources.team_roster_nba_api_source.get_column_ids",
        return_value=["01", "02"],
    )
    mocker.patch("nbahl.common.utils.time.sleep")
    mocker.patch.object(
        team_roster_nba_api_source,
        "get_team_roster_info",
        side_effect=[
            {
                "roster": pd.DataFrame(
                    data=[
                        {
                            "PLAYER_ID": 1,
                            "PLAYER": "Player 1",
                            "TEAM_ID": "01",
                        },
                        {
                            "PLAYER_ID": 2,
                            "PLAYER": "Player 2",
                            "TEAM_ID": "01",
                        },
                    ]
                ),
                "coaches": pd.DataFrame(
                    data=[
                        {"COACH_ID": 1, "COACH": "Coach 1", "TEAM_ID": "01"},
                    ]
                ),
            },
            {
                "roster": pd.DataFrame(
                    data=[
                        {
                            "PLAYER_ID": 3,
                            "PLAYER": "Player 3",
                            "TEAM_ID": "02",
                        },
                    ]
                ),
                "coaches": pd.DataFrame(
                    data=[
                        {"COACH_ID": 2, "COACH": "Coach 2", "TEAM_ID": "02"},
                    ]
                ),
            },
        ],
    )

    output_info_dfs = team_roster_nba_api_source.concat_team_rosters_info(
        season="2025-26",
        filepath=data_dir.joinpath("players-info-1-00.parquet"),
    )

    assert set(output_info_dfs.keys()) == {"roster", "coaches"}
    assert len(output_info_dfs["roster"]) == 3
    assert len(output_info_dfs["coaches"]) == 2
    assert set(output_info_dfs["roster"]["PLAYER"]) == {
        "Player 1",
        "Player 2",
        "Player 3",
    }
    assert set(output_info_dfs["roster"]["TEAM_ID"]) == {"01", "02"}
    assert set(output_info_dfs["coaches"]["COACH"]) == {"Coach 1", "Coach 2"}
    assert set(output_info_dfs["coaches"]["TEAM_ID"]) == {"01", "02"}


def test_concat_team_rosters_info_column_not_found(
    data_dir: Path, team_roster_nba_api_source: TeamRosterNBAApiSource
):
    filepath = data_dir / "players-info-1-00.parquet"
    write_to_parquet(
        df=pd.DataFrame(data=[{"PLAYER_ID": 1, "PLAYER": "Player 1"}]),
        filepath=filepath,
    )

    with pytest.raises(ColumnNotFoundError) as exc_info:
        team_roster_nba_api_source.concat_team_rosters_info(
            season="2025-26", filepath=filepath
        )

    assert (
        str(exc_info.value)
        == "'TEAM_ID' column not found, columns: ['PLAYER_ID', 'PLAYER']"
    )


def test_concat_team_rosters_info_no_dataframes(
    mocker: MockerFixture,
    data_dir: Path,
    team_roster_nba_api_source: TeamRosterNBAApiSource,
) -> None:
    mocker.patch(
        "nbahl.sources.team_roster_nba_api_source.get_column_ids",
        return_value=["01"],
    )
    mocker.patch.object(
        team_roster_nba_api_source,
        "get_team_roster_info",
        side_effect=ConnectionError("Timeout"),
    )

    with pytest.raises(DataFrameEmptyError) as exc_info:
        team_roster_nba_api_source.concat_team_rosters_info(
            season="2025-26",
            filepath=data_dir.joinpath("players-info-1-00.parquet"),
        )

    assert str(exc_info.value) == "No DataFrames for any 'team_id'"


def test_ingest_team_rosters_info_success(
    mocker: MockerFixture, data_dir: Path
) -> None:
    mocker.patch.object(
        TeamRosterNBAApiSource,
        "concat_team_rosters_info",
        return_value={
            "roster": pd.DataFrame(
                data=[
                    {"PLAYER_ID": 1, "PLAYER": "Player 1", "TEAM_ID": "01"},
                    {"PLAYER_ID": 2, "PLAYER": "Player 2", "TEAM_ID": "01"},
                ]
            ),
            "coaches": pd.DataFrame(
                data=[
                    {"COACH_ID": 1, "COACH": "Coach 1", "TEAM_ID": "01"},
                    {"COACH_ID": 2, "COACH": "Coach 2", "TEAM_ID": "01"},
                ]
            ),
        },
    )
    mock_db_writer = mocker.MagicMock(spec=DBWriter)
    mock_s3_writer = mocker.MagicMock(spec=S3Writer)
    mocker.patch("nbahl.sources.team_roster_nba_api_source.reconcile")
    mocker.patch(
        "nbahl.common.utils.get_current_date", return_value="2026-01-01"
    )

    ingest_team_rosters_info(
        season="2025-26",
        league_id=LeagueID.NBA,
        source_filepath=data_dir.joinpath("players-info-1-00.parquet"),
        db_writer=mock_db_writer,
        s3_writer=mock_s3_writer,
    )

    ingestion_runs_by_key = {
        call.kwargs["ingestion_run"].s3_key: call.kwargs["ingestion_run"]
        for call in mock_db_writer.update.call_args_list
    }
    write_keys = {
        call.kwargs["key"] for call in mock_s3_writer.write.call_args_list
    }
    expected_keys = {
        "rosters/2026-01-01/team-00-roster.parquet",
        "rosters/2026-01-01/team-00-coaches.parquet",
    }

    assert mock_s3_writer.write.call_count == 2
    assert mock_db_writer.update.call_count == 2
    assert set(ingestion_runs_by_key) == expected_keys
    assert write_keys == expected_keys
    assert (
        ingestion_runs_by_key[
            "rosters/2026-01-01/team-00-roster.parquet"
        ].rows_in
        == 2
    )
    assert (
        ingestion_runs_by_key[
            "rosters/2026-01-01/team-00-coaches.parquet"
        ].rows_in
        == 2
    )
    assert all(
        run.status == Status.SUCCESS and run.error_message is None
        for run in ingestion_runs_by_key.values()
    )
