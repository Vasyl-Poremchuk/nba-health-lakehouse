import logging
import random

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
)
from nbahl.common.models import IngestionContext
from nbahl.common.utils import (
    build_source_name,
    get_filepath,
    get_s3_key,
)
from nbahl.config import Settings
from nbahl.pipelines import run_ingestion
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
        game_logs_df = LeagueGameLog(
            league_id=self.league_id,
            player_or_team_abbreviation=self.player_or_team_abbreviation,
            season=season,
            season_type_all_star=self.season_type_all_star,
            headers=random.choice(BaseConstants.HEADERS),
        ).get_data_frames()[0]

        log.info(
            "Fetched league game logs",
            season=season,
            total_rows=len(game_logs_df),
        )

        return game_logs_df


def ingest_league_game_logs(
    season: str,
    league_id: LeagueID,
    player_or_team_abbreviation: PlayerOrTeamAbbreviation,
    season_type: SeasonTypeAllStar,
    db_writer: DBWriter,
    s3_writer: S3Writer,
) -> None:
    """Build ingestion context for league game logs and run the pipeline.

    Args:
        season: NBA season string (e.g. ``"2025-26"``).
        league_id: NBA API league identifier.
        player_or_team_abbreviation: Whether to fetch player-level or
            team-level rows.
        season_type: Season segment to query.
        db_writer: Writer used to persist the ingestion run metadata.
        s3_writer: Writer used to upload the Parquet file to S3.
    """
    source_name = build_source_name(
        source_name_prefix=GameLogNBAApiSourceConstants.SOURCE_NAME_PREFIX,
        suffixes=[league_id, player_or_team_abbreviation, season_type],
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

    context = IngestionContext(
        source_name=source_name,
        season=season,
        filepath=filepath,
        s3_key=s3_key,
        source=source,
    )

    run_ingestion(context=context, db_writer=db_writer, s3_writer=s3_writer)


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
