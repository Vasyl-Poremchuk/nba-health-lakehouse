import logging
import random
from datetime import UTC, datetime

import pandas as pd
import structlog
from nba_api.stats.endpoints import LeagueGameLog
from tenacity import before_log, retry, stop_after_attempt, wait_exponential

from nbahl.common.constants import (
    BaseConstants,
    GameLogNBAApiSourceConstants,
)
from nbahl.common.enums import (
    LeagueID,
    PlayerOrTeamAbbreviation,
    SeasonTypeAllStar,
    Status,
)
from nbahl.common.exceptions import DataFrameEmptyError
from nbahl.common.models import IngestionRun
from nbahl.common.utils import get_filepath, get_s3_key, write_to_parquet
from nbahl.config import Settings
from nbahl.writers.db_writer import DBWriter
from nbahl.writers.s3_writer import S3Writer

log = structlog.get_logger()


class GameLogNBAApiSource:
    """Fetches NBA league game logs from the NBA Stats API with retry logic.

    Rotates browser-mimicking request headers on each attempt to reduce the
    chance of rate-limiting by stats.nba.com.

    Args:
        league_id: NBA API league identifier.
        player_or_team_abbreviation: Whether to fetch player-level or team-level rows.
        season_type_all_star: Season segment to query.
    """

    def __init__(
        self,
        league_id: LeagueID,
        player_or_team_abbreviation: PlayerOrTeamAbbreviation,
        season_type_all_star: SeasonTypeAllStar,
    ) -> None:
        self.league_id = league_id
        self.player_or_team_abbreviation = player_or_team_abbreviation
        self.season_type_all_star = season_type_all_star

    @retry(
        stop=stop_after_attempt(max_attempt_number=3),
        before=before_log(logger=log, log_level=logging.INFO),
        wait=wait_exponential(multiplier=1, min=3, max=10),
        reraise=True,
    )
    def get_game_logs(self, season: str) -> pd.DataFrame:
        """Return game logs for the given season from the NBA Stats API.

        Retries up to 3 times with exponential backoff on failure.

        Args:
            season: NBA season string (e.g. ``"2025-26"``).

        Returns:
            DataFrame containing all game log rows for the season.

        Raises:
            Exception: Re-raised after the final retry attempt fails.
        """
        game_logs_dfs = LeagueGameLog(
            league_id=self.league_id,
            player_or_team_abbreviation=self.player_or_team_abbreviation,
            season=season,
            season_type_all_star=self.season_type_all_star,
            headers=random.choice(BaseConstants.HEADERS),
        ).get_data_frames()
        game_logs_df = pd.concat(objs=game_logs_dfs)

        return game_logs_df


def ingest_league_game_logs(
    season: str,
    league_id: LeagueID,
    player_or_team_abbreviation: PlayerOrTeamAbbreviation,
    season_type: SeasonTypeAllStar,
    db_writer: DBWriter,
    s3_writer: S3Writer,
) -> None:
    """Run the full league game log ingestion pipeline for a single season.

    Fetches game logs from the NBA Stats API, writes them to a local Parquet
    file, uploads the file to S3, and records the run outcome in the pipeline
    metadata database. Re-raises any exception after persisting the failure
    record so the caller (or scheduler) sees a non-zero exit.

    Args:
        season: NBA season string (e.g. ``"2025-26"``).
        league_id: NBA API league identifier.
        player_or_team_abbreviation: Whether rows represent players or teams.
        season_type: Season segment to ingest.
        db_writer: Writer used to persist the ingestion run record.
        s3_writer: Writer used to upload the Parquet file to S3.

    Raises:
        Exception: Re-raised after writing the failed ingestion run record.
    """
    source_name = GameLogNBAApiSourceConstants.get_source_name(
        league_id=league_id,
        player_or_team_abbreviation=player_or_team_abbreviation,
        season_type=season_type,
    )
    filepath = get_filepath(
        data_dir=BaseConstants.DATA_DIR,
        season=season,
        source_name=source_name,
    )
    s3_key = get_s3_key(filepath=filepath)
    source = GameLogNBAApiSource(
        league_id=league_id,
        player_or_team_abbreviation=player_or_team_abbreviation,
        season_type_all_star=season_type,
    )

    log.info(
        "Starting league game log ingestion",
        season=season,
        league_id=league_id,
        player_or_team_abbreviation=player_or_team_abbreviation,
        season_type=season_type,
    )

    started_at = datetime.now(tz=UTC)

    try:
        df = source.get_game_logs(season=season)

        if df.empty:
            raise DataFrameEmptyError("DataFrame is empty")

        write_to_parquet(df=df, filepath=filepath)
        s3_writer.write(filepath=filepath, key=s3_key)
        ended_at = datetime.now(tz=UTC)

        success_ingestion_run = IngestionRun(
            source=source_name,
            started_at=started_at,
            ended_at=ended_at,
            rows_in=len(df),
            status=Status.SUCCESS,
            error_message=None,
        )
        db_writer.write(ingestion_run=success_ingestion_run)

        log.info(
            "League game log ingestion succeeded",
            season=season,
            rows=len(df),
        )
    except Exception as exc:
        ended_at = datetime.now(tz=UTC)

        failed_ingestion_run = IngestionRun(
            source=source_name,
            started_at=started_at,
            ended_at=ended_at,
            rows_in=None,
            status=Status.FAILURE,
            error_message=str(exc),
        )
        db_writer.write(ingestion_run=failed_ingestion_run)

        log.error(
            "League game log ingestion failed",
            season=season,
            error=str(exc),
        )
        raise


if __name__ == "__main__":
    settings = Settings()
    db_writer = DBWriter(settings=settings)
    db_writer.create_table()
    ingest_league_game_logs(
        season="2025-26",
        league_id=LeagueID.NBA,
        player_or_team_abbreviation=PlayerOrTeamAbbreviation.TEAM,
        season_type=SeasonTypeAllStar.REGULAR_SEASON,
        db_writer=db_writer,
        s3_writer=S3Writer(
            bucket=f"nbahl-bronze-{settings.nbahl_env}",
            profile_name=settings.profile_name.get_secret_value(),
        ),
    )
