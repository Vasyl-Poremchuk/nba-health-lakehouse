import random
from functools import partial
from pathlib import Path

import pandas as pd
import structlog
from nba_api.stats.endpoints.commonteamroster import CommonTeamRoster

from nbahl.common.constants import (
    BaseConstants,
    PlayerInfoNBAApiSourceConstants,
    TeamRosterNBAApiSourceConstants,
)
from nbahl.common.enums import IsOnlyCurrentSeason, LeagueID
from nbahl.common.models import IngestionContextPerDataset
from nbahl.common.retry import nba_api_retry
from nbahl.common.utils import (
    build_context_attributes,
    fetch_data_by_column_ids_per_dataset,
    get_column_ids,
    zip_datasets,
)
from nbahl.config import Settings
from nbahl.pipelines import reconcile, run_ingestion_per_dataset
from nbahl.writers.db_writer import DBWriter
from nbahl.writers.s3_writer import S3Writer

log = structlog.get_logger()


class TeamRosterNBAApiSource:
    """Fetches NBA team roster and coaching staff info from the NBA Stats API
    with retry logic.

    Args:
        league_id: NBA API league identifier.
    """

    def __init__(self, league_id: LeagueID) -> None:
        self.league_id = league_id

    @nba_api_retry(logger=log)
    def get_team_roster_info(
        self, team_id: str, season: str
    ) -> dict[str, pd.DataFrame]:
        """Fetch roster and coaching staff info for a single team.

        Retries up to 3 times with exponential backoff on failure.

        Args:
            team_id: NBA API team identifier.
            season: NBA season string (e.g. ``"2025-26"``).

        Returns:
            Mapping of dataset name (``"roster"``, ``"coaches"``) to the
            corresponding DataFrame for the team.

        Raises:
            Exception: Re-raised after the final retry attempt fails.
        """
        dfs = CommonTeamRoster(
            team_id=team_id,
            season=season,
            league_id_nullable=self.league_id,
            headers=random.choice(BaseConstants.HEADERS),
        ).get_data_frames()

        team_roster_info_dfs = zip_datasets(
            datasets=TeamRosterNBAApiSourceConstants.TEAM_ROSTER_SOURCES,
            dfs=dfs,
        )

        return team_roster_info_dfs

    def concat_team_rosters_info(
        self, season: str, filepath: Path
    ) -> dict[str, pd.DataFrame]:
        """Fetch roster and coaching staff info for every team ID in a Parquet file.

        Reads unique ``TEAM_ID`` values from ``filepath``, then fetches and
        concatenates ``get_team_roster_info`` per dataset for each team.

        Args:
            season: NBA season string (e.g. ``"2025-26"``).
            filepath: Parquet file containing a ``TEAM_ID`` column.

        Returns:
            Mapping of dataset name to the concatenated DataFrame of all
            successfully fetched teams' rows for that dataset.

        Raises:
            ColumnNotFoundError: If ``TEAM_ID`` is not present in the file.
            DataFrameEmptyError: If every team failed to fetch.
        """
        team_ids = get_column_ids(filepath=filepath, id_column="TEAM_ID")

        team_rosters_info = fetch_data_by_column_ids_per_dataset(
            column_ids=team_ids,
            id_label="team_id",
            fetch_function=partial(self.get_team_roster_info, season=season),
        )

        return team_rosters_info


def ingest_team_rosters_info(
    season: str,
    league_id: LeagueID,
    source_filepath: Path,
    db_writer: DBWriter,
    s3_writer: S3Writer,
) -> None:
    """Build ingestion context for team rosters and coaching staff, and run the pipeline.

    Reads team IDs from ``source_filepath`` (typically the output of
    ``ingest_all_players_info``, since ``CommonAllPlayers`` rows carry a
    ``TEAM_ID``) and fetches roster + coaching staff info for each team.

    Args:
        season: NBA season string (e.g. ``"2025-26"``).
        league_id: NBA API league identifier.
        source_filepath: Parquet file supplying the ``TEAM_ID`` values to
            fetch rosters for.
        db_writer: Writer used to persist the ingestion run metadata.
        s3_writer: Writer used to upload the Parquet files to S3.
    """
    source = TeamRosterNBAApiSource(league_id=league_id)
    partial_context: dict[str, list[str | Path]] = {}

    for dataset in TeamRosterNBAApiSourceConstants.TEAM_ROSTER_SOURCES:
        context_attributes = build_context_attributes(
            source_name_prefix=TeamRosterNBAApiSourceConstants.SOURCE_NAME_PREFIX,
            suffixes=[league_id, dataset],
            source_dir=TeamRosterNBAApiSourceConstants.SOURCE_DIR,
            num_trailing_parts=3,
        )

        for attribute, value in context_attributes.items():
            partial_context.setdefault(f"{attribute}s", []).append(value)

    context = IngestionContextPerDataset(
        season=season,
        datasets=TeamRosterNBAApiSourceConstants.TEAM_ROSTER_SOURCES,
        fetch_function=partial(
            source.concat_team_rosters_info,
            filepath=source_filepath,
            season=season,
        ),
        **partial_context,
    )

    try:
        run_ingestion_per_dataset(
            context=context, db_writer=db_writer, s3_writer=s3_writer
        )
    finally:
        reconcile(db_writer=db_writer, s3_writer=s3_writer)


if __name__ == "__main__":
    season = "2025-26"
    settings = Settings()
    db_writer = DBWriter(settings=settings)
    db_writer.create_table()
    source_context_attributes = build_context_attributes(
        source_name_prefix=PlayerInfoNBAApiSourceConstants.SOURCE_NAME_PREFIX,
        suffixes=[IsOnlyCurrentSeason.CURRENT_SEASON_ONLY, LeagueID.NBA],
        source_dir=PlayerInfoNBAApiSourceConstants.SOURCE_DIR,
        num_trailing_parts=3,
    )
    ingest_team_rosters_info(
        season=season,
        league_id=LeagueID.NBA,
        source_filepath=Path(source_context_attributes["filepath"]),
        db_writer=db_writer,
        s3_writer=S3Writer(
            bucket=f"nbahl-bronze-{settings.nbahl_env}",
            profile_name=settings.profile_name.get_secret_value(),
        ),
    )
