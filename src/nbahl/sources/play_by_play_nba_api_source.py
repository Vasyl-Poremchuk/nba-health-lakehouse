import logging
import random
import time

import pandas as pd
import structlog
from nba_api.stats.endpoints import PlayByPlayV3
from tenacity import (
    before_sleep_log,
    retry,
    stop_after_attempt,
    wait_exponential,
)

from nbahl.common.constants import (
    BaseConstants,
    GameLogNBAApiSourceConstants,
    PlayByPlayNBAApiSourceConstants,
)
from nbahl.common.enums import Period
from nbahl.common.exceptions import (
    DataFrameEmptyError,
)
from nbahl.common.models import IngestionContext
from nbahl.common.utils import (
    add_game_id_source_name,
    build_context_attributes,
    get_game_ids_by_source,
)
from nbahl.config import Settings
from nbahl.pipelines import reconcile, run_ingestion
from nbahl.writers.db_writer import DBWriter
from nbahl.writers.s3_writer import S3Writer

log = structlog.get_logger()


class PlayByPlayNBAApiSource:
    """Fetches NBA play-by-play logs from the NBA Stats API with retry logic.

    Discovers game IDs from previously ingested league game log Parquet files,
    then fetches play-by-play data for each game. Rotates browser-mimicking
    request headers on each attempt to reduce rate-limiting by stats.nba.com.

    Args:
        start_period: First period to include in the play-by-play response.
        end_period: Last period to include in the play-by-play response.
        game_id_source_name_prefix: Filename prefix used to glob for the
            Parquet files that supply game IDs (e.g. ``"league-game-logs"``).
    """

    def __init__(
        self,
        start_period: Period,
        end_period: Period,
        game_id_source_name_prefix: str,
    ) -> None:
        self.start_period = start_period
        self.end_period = end_period
        self.game_id_source_name_prefix = game_id_source_name_prefix

    @retry(
        stop=stop_after_attempt(max_attempt_number=3),
        before_sleep=before_sleep_log(logger=log, log_level=logging.WARNING),
        wait=wait_exponential(multiplier=1, min=3, max=10),
        reraise=True,
    )
    def get_play_by_play_logs(
        self, game_id: str, game_id_source_name: str
    ) -> pd.DataFrame:
        """Fetch play-by-play data for a single game from the NBA Stats API.

        Decorated with ``@retry``: retries up to 3 times with exponential
        backoff (3-10 s) and rotates request headers on each attempt to
        reduce rate-limiting. The original exception is re-raised after the
        final attempt.

        Args:
            game_id: NBA game identifier (e.g. ``"0022401234"``).
            game_id_source_name: Logical source name written to the
                ``source_name`` column of the returned DataFrame.

        Returns:
            DataFrame of play-by-play rows for the game, annotated with a
            ``source_name`` column.

        Raises:
            Exception: Re-raised after all retry attempts are exhausted.
        """
        df = PlayByPlayV3(
            game_id=game_id,
            start_period=self.start_period,
            end_period=self.end_period,
            headers=random.choice(BaseConstants.HEADERS),
        ).get_data_frames()[0]

        df = add_game_id_source_name(
            df=df, game_id_source_name=game_id_source_name
        )

        return df

    def get_game_logs(self, season: str) -> pd.DataFrame:
        """Fetch play-by-play logs for all games in the given season.

        Discovers game IDs from previously ingested league game log files,
        then fetches play-by-play data for each game sequentially with a
        short sleep between requests. Each game is retried up to 3 times with
        exponential backoff. Games that exhaust all retries are skipped and
        logged as warnings; if the total number of skipped games reaches
        ``MAX_TOTAL_GAME_FAILURE_NUMBER``, the run is aborted immediately.

        Args:
            season: NBA season string (e.g. ``"2025-26"``).

        Returns:
            Concatenated DataFrame of play-by-play rows for all successfully
            fetched games, annotated with a ``source_name`` column. May be
            partial if some games were skipped due to persistent fetch errors.

        Raises:
            GameIDsBySourceEmptyError: If no game IDs are found across all
                source files.
            DataFrameEmptyError: If every game failed to fetch.
            Exception: Re-raised when the total number of game failures reaches
                ``MAX_TOTAL_GAME_FAILURE_NUMBER``.
        """
        game_ids_by_source = get_game_ids_by_source(
            season=season,
            game_id_source_name_prefix=self.game_id_source_name_prefix,
        )

        game_logs_dfs = []
        failed_game_ids: list[str] = []
        total_game_failures = 0

        for (
            game_id_source_name,
            game_ids,
        ) in game_ids_by_source.items():
            for game_id in game_ids:
                log.info(
                    "Fetching play-by-play game logs",
                    source_name=game_id_source_name,
                    game_id=game_id,
                )

                try:
                    df = self.get_play_by_play_logs(
                        game_id=game_id,
                        game_id_source_name=game_id_source_name,
                    )

                    game_logs_dfs.append(df)
                    time.sleep(BaseConstants.SLEEP_SECONDS)
                except Exception as exc:
                    log.warning(
                        "Fetching play-by-play game logs failed",
                        game_id=game_id,
                        game_id_source_name=game_id_source_name,
                        error=str(exc),
                    )

                    if (
                        total_game_failures
                        >= BaseConstants.MAX_TOTAL_GAME_FAILURE_NUMBER
                    ):
                        raise

                    failed_game_ids.append(game_id)
                    total_game_failures += 1

        if failed_game_ids:
            log.warning(
                "Some game IDs failed to fetch and were skipped",
                total_failed=len(failed_game_ids),
                failed_game_ids=failed_game_ids,
            )

        if not game_logs_dfs:
            raise DataFrameEmptyError("No DataFrames for any game_id")

        game_logs_df = pd.concat(objs=game_logs_dfs)

        log.info(
            "Fetched all play-by-play game logs",
            season=season,
            total_rows=len(game_logs_df),
        )

        return game_logs_df


def ingest_play_by_play_game_logs(
    season: str,
    start_period: Period,
    end_period: Period,
    db_writer: DBWriter,
    s3_writer: S3Writer,
) -> None:
    """Build ingestion context for play-by-play logs and run the pipeline.

    Args:
        season: NBA season string (e.g. ``"2025-26"``).
        start_period: First period to include in the play-by-play response.
        end_period: Last period to include in the play-by-play response.
        db_writer: Writer used to persist the ingestion run metadata.
        s3_writer: Writer used to upload the Parquet file to S3.
    """
    context_arguments = build_context_attributes(
        season=season,
        source_name_prefix=PlayByPlayNBAApiSourceConstants.SOURCE_NAME_PREFIX,
        suffixes=[start_period, end_period],
    )
    source = PlayByPlayNBAApiSource(
        start_period=start_period,
        end_period=end_period,
        game_id_source_name_prefix=GameLogNBAApiSourceConstants.SOURCE_NAME_PREFIX,
    )

    context = IngestionContext(
        season=season, source=source, **context_arguments
    )

    try:
        run_ingestion(
            context=context, db_writer=db_writer, s3_writer=s3_writer
        )
    finally:
        reconcile(db_writer=db_writer, s3_writer=s3_writer)


if __name__ == "__main__":
    settings = Settings()
    db_writer = DBWriter(settings=settings)
    db_writer.create_table()
    ingest_play_by_play_game_logs(
        season="2025-26",
        start_period=Period.ALL,
        end_period=Period.ALL,
        db_writer=db_writer,
        s3_writer=S3Writer(
            bucket=f"nbahl-bronze-{settings.nbahl_env}",
            profile_name=settings.profile_name.get_secret_value(),
        ),
    )
