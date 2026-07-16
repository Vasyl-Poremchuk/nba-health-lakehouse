import logging
import random
import time
from pathlib import Path

import pandas as pd
import structlog
from nba_api.stats.endpoints import PlayByPlayV3
from tenacity import (
    before_log,
    retry,
    retry_if_not_exception_type,
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
    ColumnNotFoundError,
    GameIDsBySourceEmptyError,
)
from nbahl.common.models import IngestionContext
from nbahl.common.utils import (
    build_source_name,
    get_filepath,
    get_s3_key,
    read_from_parquet,
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

    def _get_game_id_source_filepaths(
        self, season: str, extension: str = "parquet"
    ) -> list[Path]:
        """Glob for game ID source files matching the configured prefix.

        Args:
            season: NBA season string (e.g. ``"2025-26"``); determines the
                subdirectory searched under ``DATA_DIR``.
            extension: File extension to match (default ``"parquet"``).

        Returns:
            List of matching file paths; empty when no files are found.
        """
        game_id_source_filepaths = list(
            BaseConstants.DATA_DIR.joinpath(season).glob(
                f"{self.game_id_source_name_prefix}*.{extension}"
            )
        )

        if not game_id_source_filepaths:
            log.warning(
                "No game ID source files found",
                season=season,
                prefix=self.game_id_source_name_prefix,
            )

        return game_id_source_filepaths

    @staticmethod
    def _get_game_ids(
        season: str, game_id_source_name: str, game_id_column: str = "GAME_ID"
    ) -> list[str]:
        """Return unique game IDs from a game log Parquet file.

        Args:
            season: NBA season string (e.g. ``"2025-26"``).
            game_id_source_name: Logical source name used to locate the Parquet
                file (e.g. ``"league-game-logs-00-t-regular-season"``).
            game_id_column: Column name containing game IDs
                (default ``"GAME_ID"``).

        Returns:
            Array of unique game ID values from the specified column.

        Raises:
            ColumnNotFoundError: If ``game_id_column`` is not present in the
                Parquet file.
        """
        filepath = get_filepath(
            data_dir=BaseConstants.DATA_DIR,
            season=season,
            source_name=game_id_source_name,
        )
        df = read_from_parquet(filepath=filepath)
        columns = list(df.columns)

        if game_id_column not in columns:
            raise ColumnNotFoundError(
                f"{game_id_column!r} column not found, columns: {columns}"
            )

        game_ids = list(df[game_id_column].unique())

        return game_ids

    def collect_game_ids_by_source(
        self,
        season: str,
        game_id_source_filepaths: list[Path],
        extension: str = "parquet",
    ) -> dict[str, list[str]]:
        """Build a mapping from each source name to its unique game IDs.

        Args:
            season: NBA season string (e.g. ``"2025-26"``).
            game_id_source_filepaths: Parquet files whose game IDs should be
                collected, typically from ``_get_game_id_source_filepaths``.
            extension: File extension stripped from each filename to derive the
                source name (default ``"parquet"``).

        Returns:
            Dictionary mapping logical source name to an array of unique game IDs.
        """
        game_ids_by_source = {}

        for game_id_source_filepath in game_id_source_filepaths:
            game_id_source_name = game_id_source_filepath.name.replace(
                f".{extension}", ""
            )
            game_ids = self._get_game_ids(
                season=season, game_id_source_name=game_id_source_name
            )

            game_ids_by_source[game_id_source_name] = game_ids

        total_game_ids = sum(len(ids) for ids in game_ids_by_source.values())
        log.info(
            "Resolved game IDs by source",
            total_sources=len(game_ids_by_source),
            total_game_ids=total_game_ids,
        )

        return game_ids_by_source

    @staticmethod
    def _add_game_id_source_name(
        df: pd.DataFrame, game_id_source_name: str
    ) -> pd.DataFrame:
        """Annotate a play-by-play DataFrame with the originating source name.

        Args:
            df: Play-by-play DataFrame to annotate.
            game_id_source_name: Logical source name written to the
                ``source_name`` column.

        Returns:
            The same DataFrame with a ``source_name`` column added.
        """
        df["source_name"] = game_id_source_name

        return df

    @retry(
        stop=stop_after_attempt(max_attempt_number=3),
        before=before_log(logger=log, log_level=logging.INFO),
        wait=wait_exponential(multiplier=1, min=3, max=10),
        retry=retry_if_not_exception_type((GameIDsBySourceEmptyError,)),
        reraise=True,
    )
    def get_game_logs(self, season: str) -> pd.DataFrame:
        """Fetch play-by-play logs for all games in the given season.

        Discovers game IDs from previously ingested league game log files,
        then fetches play-by-play data for each game sequentially with a
        short sleep between requests. Retries up to 3 times with exponential
        backoff on failure.

        Args:
            season: NBA season string (e.g. ``"2025-26"``).

        Returns:
            Concatenated DataFrame of play-by-play rows for all games,
            annotated with a ``source_name`` column.

        Raises:
            Exception: Re-raised after the final retry attempt fails.
        """
        game_id_source_filepaths = self._get_game_id_source_filepaths(
            season=season
        )
        game_ids_by_source = self.collect_game_ids_by_source(
            season=season, game_id_source_filepaths=game_id_source_filepaths
        )

        if not any(len(game_ids) for game_ids in game_ids_by_source.values()):
            raise GameIDsBySourceEmptyError(
                "There are no game IDs for the source"
            )

        game_logs_dfs = []

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
                df = PlayByPlayV3(
                    game_id=game_id,
                    start_period=self.start_period,
                    end_period=self.end_period,
                    headers=random.choice(BaseConstants.HEADERS),
                ).get_data_frames()[0]

                df = self._add_game_id_source_name(
                    df=df, game_id_source_name=game_id_source_name
                )
                game_logs_dfs.append(df)
                time.sleep(BaseConstants.SLEEP_SECONDS)

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
    source_name = build_source_name(
        source_name_prefix=PlayByPlayNBAApiSourceConstants.SOURCE_NAME_PREFIX,
        suffixes=[start_period, end_period],
    )
    filepath = get_filepath(
        data_dir=BaseConstants.DATA_DIR,
        season=season,
        source_name=source_name,
    )
    s3_key = get_s3_key(filepath=filepath)
    source = PlayByPlayNBAApiSource(
        start_period=start_period,
        end_period=end_period,
        game_id_source_name_prefix=GameLogNBAApiSourceConstants.SOURCE_NAME_PREFIX,
    )

    context = IngestionContext(
        source_name=source_name,
        season=season,
        filepath=filepath,
        s3_key=s3_key,
        source=source,
    )

    run_ingestion(context=context, db_writer=db_writer, s3_writer=s3_writer)
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
