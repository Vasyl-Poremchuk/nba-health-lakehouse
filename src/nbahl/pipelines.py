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
    """Run a full ingestion cycle using a 2-phase commit against the metadata DB.

    Phase 1 inserts a ``PENDING`` record before any work begins, capturing
    ``started_at`` and ``s3_key``. Phase 2 updates that record to ``SUCCESS``
    (with ``ended_at`` and ``rows_in``) or ``FAILURE`` (with ``ended_at`` and
    ``error_message``) once the outcome is known. If Phase 1 itself fails the
    exception is re-raised immediately with no DB update attempted.

    Args:
        context: Runtime context carrying the source, paths, and identifiers.
        db_writer: Writer used to persist the ingestion run metadata.
        s3_writer: Writer used to upload the Parquet file to S3.

    Raises:
        Exception: Re-raised after the FAILURE record is written, or immediately
            if the initial PENDING record could not be inserted.
    """
    log.info(
        "Starting game log ingestion",
        source_name=context.source_name,
        season=context.season,
    )

    started_at = datetime.now(tz=UTC)
    pending_ingestion_run = IngestionRun(
        s3_key=context.s3_key, started_at=started_at, status=Status.PENDING
    )
    run_id: int | None = None

    try:
        run_id = db_writer.write(ingestion_run=pending_ingestion_run)

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
            s3_key=context.s3_key,
            started_at=started_at,
            ended_at=ended_at,
            rows_in=rows_in,
            status=Status.SUCCESS,
        )
        db_writer.update(run_id=run_id, ingestion_run=success_ingestion_run)

        log.info(
            "Game log ingestion succeeded",
            run_id=run_id,
            s3_key=context.s3_key,
            rows_in=rows_in,
        )
    except Exception as exc:
        ended_at = datetime.now(tz=UTC)

        failed_ingestion_run = IngestionRun(
            s3_key=context.s3_key,
            started_at=started_at,
            ended_at=ended_at,
            status=Status.FAILURE,
            error_message=str(exc),
        )

        if run_id is not None:
            db_writer.update(run_id=run_id, ingestion_run=failed_ingestion_run)

        log.error(
            "Game log ingestion failed",
            run_id=run_id,
            s3_key=context.s3_key,
            season=context.season,
            error=str(exc),
            exc_info=True,
        )
        raise


def reconcile(db_writer: DBWriter, s3_writer: S3Writer) -> None:
    """Resolve stale PENDING runs left behind by mid-flight pipeline crashes.

    Queries ingestion_runs for rows that have been PENDING longer than
    ``INTERVAL_MINS`` minutes, then checks S3 for each. Rows whose S3 object
    exists are marked ``SUCCESS``; rows with no S3 object are marked ``FAILURE``.
    Updates are applied in two batch calls to minimise round-trips.

    Args:
        db_writer: Writer used to query stale rows and update their status.
        s3_writer: Writer used to check whether each S3 object exists.
    """
    log.info("Starting reconcile")

    stale_rows = db_writer.get_stale_rows()
    run_ids: dict[str, list[int]] = {}

    for row in stale_rows:
        run_id = int(row["run_id"])
        s3_key = str(row["s3_key"])

        object_exists = s3_writer.object_exists(key=s3_key)

        if object_exists:
            run_ids.setdefault("success", []).append(run_id)
        else:
            run_ids.setdefault("failure", []).append(run_id)

    success_ids = run_ids.get("success", [])
    failure_ids = run_ids.get("failure", [])

    db_writer.update_status(run_ids=success_ids, status=Status.SUCCESS)
    db_writer.update_status(run_ids=failure_ids, status=Status.FAILURE)

    log.info(
        "Reconcile completed",
        stale_count=len(stale_rows),
        success_count=len(success_ids),
        failure_count=len(failure_ids),
    )
