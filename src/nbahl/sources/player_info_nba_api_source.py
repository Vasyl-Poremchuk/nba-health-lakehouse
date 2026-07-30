import random
from functools import partial
from pathlib import Path

import pandas as pd
import structlog
from nba_api.stats.endpoints.commonallplayers import CommonAllPlayers
from nba_api.stats.endpoints.commonplayerinfo import CommonPlayerInfo

from nbahl.common.constants import (
    BaseConstants,
    PlayerInfoNBAApiSourceConstants,
)
from nbahl.common.enums import IsOnlyCurrentSeason, LeagueID
from nbahl.common.models import IngestionContext
from nbahl.common.retry import nba_api_retry
from nbahl.common.utils import (
    build_context_attributes,
    fetch_data_by_column_ids,
    get_column_ids,
)
from nbahl.config import Settings
from nbahl.pipelines import reconcile, run_ingestion
from nbahl.writers.db_writer import DBWriter
from nbahl.writers.s3_writer import S3Writer

log = structlog.get_logger()


class PlayerInfoNBAApiSource:
    """Fetches NBA player info from the NBA Stats API with retry logic.

    Provides two independent fetches: a bulk list of lightweight player bios
    (``get_all_players_info``), and a detailed per-player profile
    (``get_player_info``) that must be called once per player ID. Rotates
    browser-mimicking request headers on each attempt to reduce rate-limiting
    by stats.nba.com.

    Args:
        is_only_current_season: Whether ``get_all_players_info`` should
            return only current-season players.
        league_id: NBA API league identifier.
    """

    def __init__(
        self, is_only_current_season: IsOnlyCurrentSeason, league_id: LeagueID
    ) -> None:
        self.is_only_current_season = is_only_current_season
        self.league_id = league_id

    @nba_api_retry(logger=log)
    def get_all_players_info(self, season: str) -> pd.DataFrame:
        """Fetch the bulk list of all players for the given season.

        Retries up to 3 times with exponential backoff on failure.

        Args:
            season: NBA season string (e.g. ``"2025-26"``).

        Returns:
            DataFrame containing one lightweight bio row per player.

        Raises:
            Exception: Re-raised after the final retry attempt fails.
        """
        all_players_info_df = CommonAllPlayers(
            is_only_current_season=self.is_only_current_season,
            league_id=self.league_id,
            season=season,
            headers=random.choice(BaseConstants.HEADERS),
        ).get_data_frames()[0]

        log.info(
            "Fetched all players info",
            season=season,
            total_rows=len(all_players_info_df),
        )

        return all_players_info_df

    @nba_api_retry(logger=log)
    def get_player_info(self, player_id: str) -> pd.DataFrame:
        """Fetch detailed profile info for a single player.

        Retries up to 3 times with exponential backoff on failure.

        Args:
            player_id: NBA API player identifier.

        Returns:
            DataFrame containing the detailed profile row for the player.

        Raises:
            Exception: Re-raised after the final retry attempt fails.
        """
        player_info_df = CommonPlayerInfo(
            player_id=player_id,
            league_id_nullable=self.league_id,
            headers=random.choice(BaseConstants.HEADERS),
        ).get_data_frames()[0]

        log.info(
            "Fetched player info",
            player_id=int(player_id),
            total_rows=len(player_info_df),
        )

        return player_info_df

    def concat_players_detail_info(self, filepath: Path) -> pd.DataFrame:
        """Fetch detailed profile info for every player ID in a Parquet file.

        Reads unique ``PERSON_ID`` values from ``filepath`` (typically the
        output of ``get_all_players_info``), then fetches and concatenates
        ``get_player_info`` for each one.

        Args:
            filepath: Parquet file containing a ``PERSON_ID`` column.

        Returns:
            Concatenated DataFrame of detailed profile rows for all
            successfully fetched players.

        Raises:
            ColumnNotFoundError: If ``PERSON_ID`` is not present in the file.
            DataFrameEmptyError: If every player failed to fetch.
        """
        player_ids = get_column_ids(filepath=filepath, id_column="PERSON_ID")

        players_detail_info_df = fetch_data_by_column_ids(
            column_ids=player_ids,
            id_label="player_id",
            fetch_function=self.get_player_info,
        )

        return players_detail_info_df


def ingest_all_players_info(
    source: PlayerInfoNBAApiSource,
    season: str,
    db_writer: DBWriter,
    s3_writer: S3Writer,
) -> Path:
    """Build ingestion context for the bulk player list and run the pipeline.

    Args:
        source: Configured ``PlayerInfoNBAApiSource`` instance.
        season: NBA season string (e.g. ``"2025-26"``).
        db_writer: Writer used to persist the ingestion run metadata.
        s3_writer: Writer used to upload the Parquet file to S3.

    Returns:
        Local Parquet filepath the bulk player list was written to; feed this
        into ``ingest_players_detail_info`` as ``source_filepath``.
    """
    context_attributes = build_context_attributes(
        season=season,
        source_name_prefix=PlayerInfoNBAApiSourceConstants.SOURCE_NAME_PREFIX,
        suffixes=[source.is_only_current_season, source.league_id],
    )

    context = IngestionContext(
        season=season,
        fetch_function=partial(source.get_all_players_info, season=season),
        **context_attributes,
    )

    try:
        run_ingestion(
            context=context, db_writer=db_writer, s3_writer=s3_writer
        )
    finally:
        reconcile(db_writer=db_writer, s3_writer=s3_writer)

    return context.filepath


def ingest_players_detail_info(
    source: PlayerInfoNBAApiSource,
    source_filepath: Path,
    db_writer: DBWriter,
    s3_writer: S3Writer,
) -> None:
    """Build ingestion context for detailed per-player profiles and run the pipeline.

    Reads player IDs from ``source_filepath`` (the output of
    ``ingest_all_players_info``) and fetches a detailed profile for each.

    Args:
        source: Configured ``PlayerInfoNBAApiSource`` instance.
        source_filepath: Parquet file supplying the ``PERSON_ID`` values to
            fetch detail for, typically returned by ``ingest_all_players_info``.
        db_writer: Writer used to persist the ingestion run metadata.
        s3_writer: Writer used to upload the Parquet file to S3.
    """
    context_attributes = build_context_attributes(
        source_name_prefix=PlayerInfoNBAApiSourceConstants.SOURCE_NAME_PREFIX,
        suffixes=[source.is_only_current_season, source.league_id],
        source_dir=PlayerInfoNBAApiSourceConstants.SOURCE_DIR,
        num_trailing_parts=3,
    )

    context = IngestionContext(
        fetch_function=partial(
            source.concat_players_detail_info, filepath=source_filepath
        ),
        **context_attributes,
    )

    try:
        run_ingestion(
            context=context, db_writer=db_writer, s3_writer=s3_writer
        )
    finally:
        reconcile(db_writer=db_writer, s3_writer=s3_writer)


if __name__ == "__main__":
    season = "2025-26"
    settings = Settings()
    db_writer = DBWriter(settings=settings)
    db_writer.create_table()
    source = PlayerInfoNBAApiSource(
        is_only_current_season=IsOnlyCurrentSeason.CURRENT_SEASON_ONLY,
        league_id=LeagueID.NBA,
    )
    s3_writer = S3Writer(
        bucket=f"nbahl-bronze-{settings.nbahl_env}",
        profile_name=settings.profile_name.get_secret_value(),
    )

    all_players_info_filepath = ingest_all_players_info(
        season=season,
        source=source,
        db_writer=db_writer,
        s3_writer=s3_writer,
    )
    ingest_players_detail_info(
        source=source,
        source_filepath=all_players_info_filepath,
        db_writer=db_writer,
        s3_writer=s3_writer,
    )
