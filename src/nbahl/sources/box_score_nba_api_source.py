import random
from functools import partial
from pathlib import Path

import pandas as pd
import structlog
from nba_api.stats.endpoints.boxscoresummaryv3 import BoxScoreSummaryV3

from nbahl.common.constants import (
    BaseConstants,
    BoxScoreNBAApiSourceConstants,
    PlayByPlayNBAApiSourceConstants,
)
from nbahl.common.enums import Period
from nbahl.common.models import BoxScoreContext, IngestionContextPerDataset
from nbahl.common.retry import nba_api_retry
from nbahl.common.utils import (
    add_game_id_source_name,
    build_context_attributes,
    fetch_data_by_column_ids_per_dataset,
    get_game_ids_by_source,
    zip_datasets,
)
from nbahl.config import Settings
from nbahl.pipelines import reconcile, run_ingestion_per_dataset
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

    @nba_api_retry(logger=log)
    def get_box_score_logs(
        self,
        game_id: str,
        game_id_source_name: str,
        box_score_context: BoxScoreContext,
    ) -> dict[str, pd.DataFrame]:
        """Fetch box score data for a single game from the NBA Stats API.

        Decorated with ``@nba_api_retry``: retries up to 3 times with
        exponential backoff (3-10 s) and rotates request headers on each
        attempt to reduce rate-limiting. The original exception is re-raised
        after the final attempt. Period arguments are forwarded only when
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
        self,
        game_ids_by_source: dict[str, list[str]],
        box_score_context: BoxScoreContext,
    ) -> dict[str, pd.DataFrame]:
        """Fetch box score logs for all games in the given season.

        Fetches box score data for each game sequentially with a short sleep
        between requests. Each game is retried up to 3 times with exponential
        backoff. Games that exhaust all retries are skipped and logged as
        warnings; if the total number of skipped games reaches
        ``BaseConstants.MAX_TOTAL_FAILURE_NUMBER`` (enforced by the underlying
        ``fetch_data_by_column_ids_per_dataset`` call), the run is aborted
        immediately.

        Args:
            game_ids_by_source: Mapping of source name to game IDs to fetch,
                typically from ``get_game_ids_by_source``.
            box_score_context: Configuration object specifying the API endpoint,
                dataset names, and period settings for this box score variant.

        Returns:
            Mapping of dataset name to a concatenated DataFrame of all
            successfully fetched game rows, annotated with a ``source_name``
            column. May be partial if some games were skipped due to persistent
            fetch errors.

        Raises:
            DataFrameEmptyError: If every game failed to fetch.
            Exception: Re-raised when the total number of game failures reaches
                ``BaseConstants.MAX_TOTAL_FAILURE_NUMBER``.
        """
        dfs_by_dataset: dict[str, list[pd.DataFrame]] = {}

        for game_id_source_name, game_ids in game_ids_by_source.items():
            box_score_logs_for_source = fetch_data_by_column_ids_per_dataset(
                column_ids=game_ids,
                id_label="game_id",
                fetch_function=partial(
                    self.get_box_score_logs,
                    game_id_source_name=game_id_source_name,
                    box_score_context=box_score_context,
                ),
            )

            for dataset, df in box_score_logs_for_source.items():
                dfs_by_dataset.setdefault(dataset, []).append(df)

        box_score_logs_by_dataset = {
            dataset: pd.concat(objs=dfs)
            for dataset, dfs in dfs_by_dataset.items()
        }

        return box_score_logs_by_dataset


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
    game_ids_by_source = get_game_ids_by_source(
        season=season,
        game_id_source_name_prefix=source.game_id_source_name_prefix,
        game_id_column="gameId",
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
            partial_context: dict[str, list[str | Path]] = {}

            for dataset in datasets:
                context_attributes = build_context_attributes(
                    source_name_prefix=BoxScoreNBAApiSourceConstants.SOURCE_NAME_PREFIX,
                    suffixes=[
                        start_period,
                        end_period,
                        box_score_source,
                        dataset.replace("_", "-"),
                    ],
                    season=season,
                )

                for attribute, value in context_attributes.items():
                    partial_context.setdefault(f"{attribute}s", []).append(
                        value
                    )

            context = IngestionContextPerDataset(
                season=season,
                datasets=datasets,
                fetch_function=partial(
                    source.get_box_score_game_logs,
                    game_ids_by_source=game_ids_by_source,
                    box_score_context=box_score_context,
                ),
                **partial_context,
            )

            run_ingestion_per_dataset(
                context=context, db_writer=db_writer, s3_writer=s3_writer
            )
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
