from datetime import UTC, datetime

import structlog

from nbahl.common.enums import Status
from nbahl.common.exceptions import DataFrameEmptyError
from nbahl.common.models import IngestionContext, IngestionRun
from nbahl.common.utils import write_to_parquet
from nbahl.writers.db_writer import DBWriter
from nbahl.writers.s3_writer import S3Writer

log = structlog.get_logger()


def run_ingestion(
    context: IngestionContext, db_writer: DBWriter, s3_writer: S3Writer
) -> None:
    """Run a full ingestion cycle: fetch, write locally, upload to S3, record metadata.

    On success writes the Parquet file, uploads it to S3, and inserts a
    ``SUCCESS`` run record into the metadata database. On any failure inserts
    a ``FAILURE`` record and re-raises the exception.

    Args:
        context: Runtime context carrying the source, paths, and identifiers.
        db_writer: Writer used to persist the ingestion run metadata.
        s3_writer: Writer used to upload the Parquet file to S3.

    Raises:
        Exception: Re-raised after the failure metadata record is written.
    """
    log.info(
        "Starting game log ingestion",
        source_name=context.source_name,
        season=context.season,
    )

    started_at = datetime.now(tz=UTC)

    try:
        df = context.source.get_game_logs(season=context.season)
        rows_in = len(df)

        if df.empty:
            raise DataFrameEmptyError("DataFrame is empty")

        write_to_parquet(df=df, filepath=context.filepath)
        log.debug(
            "Wrote Parquet file",
            filepath=str(context.filepath),
            rows=rows_in,
        )

        s3_writer.write(filepath=context.filepath, key=context.s3_key)
        log.debug("Uploaded file to S3", key=context.s3_key)

        ended_at = datetime.now(tz=UTC)

        success_ingestion_run = IngestionRun(
            source=context.source_name,
            started_at=started_at,
            ended_at=ended_at,
            rows_in=rows_in,
            status=Status.SUCCESS,
            error_message=None,
        )
        db_writer.write(ingestion_run=success_ingestion_run)

        log.info(
            "Game log ingestion succeeded",
            source_name=context.source_name,
            season=context.season,
            rows_in=rows_in,
        )
    except Exception as exc:
        ended_at = datetime.now(tz=UTC)

        failed_ingestion_run = IngestionRun(
            source=context.source_name,
            started_at=started_at,
            ended_at=ended_at,
            rows_in=None,
            status=Status.FAILURE,
            error_message=str(exc),
        )
        db_writer.write(ingestion_run=failed_ingestion_run)

        log.error(
            "Game log ingestion failed",
            source_name=context.source_name,
            season=context.season,
            error=str(exc),
            exc_info=True,
        )
        raise
