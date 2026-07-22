import logging
import random
import time
from datetime import UTC, datetime

import pandas as pd
import structlog
from nba_api.stats.endpoints.boxscoresummaryv3 import BoxScoreSummaryV3
from tenacity import (
    before_sleep_log,
    retry,
    stop_after_attempt,
    wait_exponential,
)

from nbahl.common.constants import (
    BaseConstants,
    BoxScoreNBAApiSourceConstants,
    PlayByPlayNBAApiSourceConstants,
)
from nbahl.common.enums import Period, Status
from nbahl.common.exceptions import (
    DataFrameEmptyError,
    GameIDsBySourceEmptyError,
)
from nbahl.common.models import BoxScoreContext, IngestionRun
from nbahl.common.utils import (
    add_game_id_source_name,
    build_source_name,
    collect_game_ids_by_source,
    get_filepath,
    get_game_id_source_filepaths,
    get_s3_key,
    write_to_parquet,
    zip_datasets,
)
from nbahl.config import Settings
from nbahl.pipelines import reconcile
from nbahl.writers.db_writer import DBWriter
from nbahl.writers.s3_writer import S3Writer

log = structlog.get_logger()


class BoxScoreNBAApiSource:
    """Fetches NBA box score logs from the NBA Stats API with retry logic.

    Discovers game IDs from previously ingested play-by-play Parquet files,
    then fetches box score data for each game across multiple endpoints. Rotates
    browser-mimicking request headers on each attempt to reduce rate-limiting
    by stats.nba.com.

    Args:
        start_period: First period to include in period-sensitive box score
            responses.
        end_period: Last period to include in period-sensitive box score
            responses.
        game_id_source_name_prefix: Filename prefix used to glob for the
            Parquet files that supply game IDs (e.g. ``"play-by-play-logs"``).
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
    def get_box_score_logs(
        self,
        game_id: str,
        game_id_source_name: str,
        box_score_context: BoxScoreContext,
    ) -> dict[str, pd.DataFrame]:
        """Fetch box score data for a single game from the NBA Stats API.

        Decorated with ``@retry``: retries up to 3 times with exponential
        backoff (3-10 s) and rotates request headers on each attempt to
        reduce rate-limiting. The original exception is re-raised after the
        final attempt. Period arguments are forwarded only when
        ``box_score_context.includes_periods`` is ``True``.

        Args:
            game_id: NBA game identifier (e.g. ``"0022401234"``).
            game_id_source_name: Logical source name written to the
                ``source_name`` column of each returned DataFrame.
            box_score_context: Configuration object that specifies the nba_api
                endpoint class, dataset names, and whether to forward period
                arguments.

        Returns:
            Mapping of dataset name to the annotated DataFrame for that dataset.

        Raises:
            Exception: Re-raised after all retry attempts are exhausted.
        """
        arguments = {
            "game_id": game_id,
            "headers": random.choice(BaseConstants.HEADERS),
        }

        if box_score_context.includes_periods:
            arguments.update(
                {
                    "start_period": self.start_period,
                    "end_period": self.end_period,
                }
            )

        dfs = box_score_context.box_score_class(**arguments).get_data_frames()
        dfs = [
            add_game_id_source_name(
                df=df,
                game_id_source_name=game_id_source_name,
            )
            for df in dfs
        ]

        box_score_logs = zip_datasets(
            datasets=box_score_context.datasets, dfs=dfs
        )

        return box_score_logs

    def get_box_score_game_logs(
        self, season: str, box_score_context: BoxScoreContext
    ) -> dict[str, pd.DataFrame]:
        """Fetch box score logs for all games in the given season.

        Discovers game IDs from previously ingested play-by-play source files,
        then fetches box score data for each game sequentially with a short
        sleep between requests. Each game is retried up to 3 times with
        exponential backoff. Games that exhaust all retries are skipped and
        logged as warnings; if the total number of skipped games reaches
        ``MAX_TOTAL_GAME_FAILURE_NUMBER``, the run is aborted immediately.

        Args:
            season: NBA season string (e.g. ``"2025-26"``).
            box_score_context: Configuration object specifying the API endpoint,
                dataset names, and period settings for this box score variant.

        Returns:
            Mapping of dataset name to a concatenated DataFrame of all
            successfully fetched game rows, annotated with a ``source_name``
            column. May be partial if some games were skipped due to persistent
            fetch errors.

        Raises:
            GameIDsBySourceEmptyError: If no game IDs are found across all
                source files.
            DataFrameEmptyError: If every game failed to fetch.
            Exception: Re-raised when the total number of game failures reaches
                ``MAX_TOTAL_GAME_FAILURE_NUMBER``.
        """
        game_id_source_filepaths = get_game_id_source_filepaths(
            season=season,
            game_id_source_name_prefix=self.game_id_source_name_prefix,
        )
        game_ids_by_source = collect_game_ids_by_source(
            season=season,
            game_id_source_filepaths=game_id_source_filepaths,
            game_id_column="gameId",
        )

        if not any(len(game_ids) for game_ids in game_ids_by_source.values()):
            raise GameIDsBySourceEmptyError(
                "There are no game IDs for the source"
            )

        box_score_logs_by_dataset: dict[str, list[pd.DataFrame]] = {}
        failed_game_ids: list[str] = []
        total_game_failures = 0

        for game_id_source_name, game_ids in game_ids_by_source.items():
            for game_id in game_ids:
                log.info(
                    "Fetching box score game logs",
                    source_name=game_id_source_name,
                    game_id=game_id,
                )

                try:
                    logs = self.get_box_score_logs(
                        game_id=game_id,
                        game_id_source_name=game_id_source_name,
                        box_score_context=box_score_context,
                    )

                    for dataset, df in logs.items():
                        box_score_logs_by_dataset.setdefault(
                            dataset, []
                        ).append(df)

                    time.sleep(BaseConstants.SLEEP_SECONDS)
                except Exception as exc:
                    log.warning(
                        "Fetching box score game logs failed",
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

        if not box_score_logs_by_dataset or not any(
            len(dfs) for dfs in box_score_logs_by_dataset.values()
        ):
            raise DataFrameEmptyError("No DataFrames for any game_id")

        box_score_game_logs = {
            dataset: pd.concat(objs=dfs)
            for dataset, dfs in box_score_logs_by_dataset.items()
        }

        log.info(
            "Fetched all box score game logs",
            season=season,
            total_rows=sum(len(dfs) for dfs in box_score_game_logs.values()),
        )

        return box_score_game_logs


def ingest_box_score_game_logs(
    season: str,
    start_period: Period,
    end_period: Period,
    db_writer: DBWriter,
    s3_writer: S3Writer,
) -> None:
    """Ingest box score game logs for all configured box score sources.

    Iterates over all entries in ``BoxScoreNBAApiSourceConstants.BOX_SCORE_SOURCES``,
    fetches game logs for each (endpoint, dataset) combination, writes the result
    as a Parquet file locally, uploads it to S3, and records the ingestion run
    metadata in the database. Always calls ``reconcile`` in a ``finally`` block
    to resolve any stale PENDING rows left by crashes.

    Args:
        season: NBA season string (e.g. ``"2025-26"``).
        start_period: First period forwarded to period-sensitive API endpoints.
        end_period: Last period forwarded to period-sensitive API endpoints.
        db_writer: Writer used to persist ingestion run metadata.
        s3_writer: Writer used to upload Parquet files to S3.
    """
    source = BoxScoreNBAApiSource(
        start_period=start_period,
        end_period=end_period,
        game_id_source_name_prefix=PlayByPlayNBAApiSourceConstants.SOURCE_NAME_PREFIX,
    )

    try:
        for (
            (box_score_class, box_score_source),
            datasets,
        ) in BoxScoreNBAApiSourceConstants.BOX_SCORE_SOURCES.items():
            includes_periods = box_score_class != BoxScoreSummaryV3

            box_score_context = BoxScoreContext(
                box_score_class=box_score_class,
                datasets=datasets,
                includes_periods=includes_periods,
            )

            source_names = [
                build_source_name(
                    source_name_prefix=BoxScoreNBAApiSourceConstants.SOURCE_NAME_PREFIX,
                    suffixes=[
                        start_period,
                        end_period,
                        box_score_source,
                        dataset.replace("_", "-"),
                    ],
                )
                for dataset in datasets
            ]
            filepaths = [
                get_filepath(
                    data_dir=BaseConstants.DATA_DIR,
                    season=season,
                    source_name=source_name,
                )
                for source_name in source_names
            ]
            s3_keys = [get_s3_key(filepath=filepath) for filepath in filepaths]
            started_at = datetime.now(tz=UTC)
            pending_ingestion_runs = [
                IngestionRun(
                    s3_key=s3_key, started_at=started_at, status=Status.PENDING
                )
                for s3_key in s3_keys
            ]
            run_ids: list[int] = []

            log.info(
                "Starting box score game log ingestion",
                box_score_source=box_score_source,
                season=season,
            )

            for pending_ingestion_run in pending_ingestion_runs:
                run_id = db_writer.write(ingestion_run=pending_ingestion_run)

                run_ids.append(run_id)

            box_score_game_logs = source.get_box_score_game_logs(
                season=season, box_score_context=box_score_context
            )

            for dataset, source_name, filepath, s3_key, run_id in zip(
                datasets,
                source_names,
                filepaths,
                s3_keys,
                run_ids,
                strict=True,
            ):
                try:
                    log.info(
                        "Starting box score game log ingestion",
                        source_name=source_name,
                        season=season,
                    )

                    df = box_score_game_logs[dataset]
                    rows_in = len(df)

                    if df.empty:
                        raise DataFrameEmptyError("DataFrame is empty")

                    write_to_parquet(df=df, filepath=filepath)
                    log.debug(
                        "Wrote Parquet file",
                        source_name=source_name,
                        filepath=str(filepath),
                        rows=rows_in,
                    )

                    s3_writer.write(filepath=filepath, key=s3_key)
                    log.debug(
                        "Uploaded file to S3",
                        source_name=source_name,
                        key=s3_key,
                    )

                    ended_at = datetime.now(tz=UTC)

                    success_ingestion_run = IngestionRun(
                        s3_key=s3_key,
                        started_at=started_at,
                        ended_at=ended_at,
                        rows_in=rows_in,
                        status=Status.SUCCESS,
                    )
                    db_writer.update(
                        run_id=run_id, ingestion_run=success_ingestion_run
                    )

                    log.info(
                        "Box score game log ingestion succeeded",
                        run_id=run_id,
                        source_name=source_name,
                        s3_key=s3_key,
                        rows_in=rows_in,
                    )
                except Exception as exc:
                    ended_at = datetime.now(tz=UTC)

                    failed_ingestion_run = IngestionRun(
                        s3_key=s3_key,
                        started_at=started_at,
                        ended_at=ended_at,
                        status=Status.FAILURE,
                        error_message=str(exc),
                    )

                    db_writer.update(
                        run_id=run_id, ingestion_run=failed_ingestion_run
                    )

                    log.error(
                        "Box score game log ingestion failed",
                        run_id=run_id,
                        source_name=source_name,
                        s3_key=s3_key,
                        season=season,
                        error=str(exc),
                        exc_info=True,
                    )
                    raise
    finally:
        reconcile(db_writer=db_writer, s3_writer=s3_writer)


if __name__ == "__main__":
    settings = Settings()
    db_writer = DBWriter(settings=settings)
    db_writer.create_table()
    ingest_box_score_game_logs(
        season="2025-26",
        start_period=Period.ALL,
        end_period=Period.ALL,
        db_writer=db_writer,
        s3_writer=S3Writer(
            bucket=f"nbahl-bronze-{settings.nbahl_env}",
            profile_name=settings.profile_name.get_secret_value(),
        ),
    )
