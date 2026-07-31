import structlog

from nbahl.common.enums import Status
from nbahl.common.models import (
    CommitContext,
    FailureCommitContext,
    IngestionContext,
    IngestionContextPerDataset,
    IngestionRun,
    SuccessCommitContext,
)
from nbahl.common.utils import (
    commit_failure,
    commit_success,
    get_current_datetime,
)
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
        "Starting ingestion",
        source_name=context.source_name,
        season=context.season,
    )

    started_at = get_current_datetime()
    pending_ingestion_run = IngestionRun(
        s3_key=context.s3_key, started_at=started_at, status=Status.PENDING
    )

    run_id = db_writer.write(ingestion_run=pending_ingestion_run)
    commit_context = CommitContext(
        run_id=run_id,
        source_name=context.source_name,
        s3_key=context.s3_key,
        started_at=started_at,
        season=context.season,
    )

    try:
        dataset_df = context.fetch_function()

        commit_success(
            context=SuccessCommitContext(
                **commit_context.model_dump(),
                dataset_df=dataset_df,
                filepath=context.filepath,
            ),
            db_writer=db_writer,
            s3_writer=s3_writer,
        )
    except Exception as exc:
        commit_failure(
            context=FailureCommitContext(
                **commit_context.model_dump(), error_message=str(exc)
            ),
            db_writer=db_writer,
        )
        raise


def run_ingestion_per_dataset(
    context: IngestionContextPerDataset,
    db_writer: DBWriter,
    s3_writer: S3Writer,
) -> None:
    """Run an ingestion cycle for multiple datasets fetched by one shared call.

    A 2-phase commit, extended to N datasets. Phase 1 inserts one ``PENDING``
    record per dataset before any work begins. ``context.fetch_function()``
    is then called once, returning all datasets at once; if it raises, every
    pending record is marked ``FAILURE`` and the exception is re-raised
    immediately. Otherwise each dataset is written and uploaded independently:
    a dataset's own failure (e.g. an empty DataFrame or an S3 error) marks
    only that dataset's record ``FAILURE`` and re-raises immediately, which
    also aborts the loop over the remaining datasets - any dataset not yet
    reached stays ``PENDING`` (not ``FAILURE``) until a later ``reconcile``
    call resolves it, rather than being attempted.

    Args:
        context: Runtime context carrying the shared fetch function, and
            per-dataset paths and identifiers.
        db_writer: Writer used to persist the ingestion run metadata.
        s3_writer: Writer used to upload the Parquet files to S3.

    Raises:
        Exception: Re-raised after the relevant FAILURE record(s) are
            written - either for every dataset (shared fetch failure) or for
            the one dataset that failed (per-dataset failure).
    """
    started_at = get_current_datetime()
    pending_ingestion_runs = [
        IngestionRun(
            s3_key=s3_key, started_at=started_at, status=Status.PENDING
        )
        for s3_key in context.s3_keys
    ]
    run_ids: list[int] = []

    log.info("Starting ingestion")

    for pending_ingestion_run in pending_ingestion_runs:
        run_id = db_writer.write(ingestion_run=pending_ingestion_run)

        run_ids.append(run_id)

    try:
        dataset_dfs = context.fetch_function()
    except Exception as exc:
        for run_id, source_name, s3_key in zip(
            run_ids, context.source_names, context.s3_keys, strict=True
        ):
            commit_failure(
                context=FailureCommitContext(
                    run_id=run_id,
                    source_name=source_name,
                    s3_key=s3_key,
                    started_at=started_at,
                    season=context.season,
                    error_message=str(exc),
                ),
                db_writer=db_writer,
            )

        raise

    for dataset, source_name, filepath, s3_key, run_id in zip(
        context.datasets,
        context.source_names,
        context.filepaths,
        context.s3_keys,
        run_ids,
        strict=True,
    ):
        commit_context = CommitContext(
            run_id=run_id,
            source_name=source_name,
            s3_key=s3_key,
            started_at=started_at,
            season=context.season,
        )

        try:
            log.info(
                "Starting ingestion",
                source_name=source_name,
                season=context.season,
            )

            dataset_df = dataset_dfs[dataset]
            commit_success(
                context=SuccessCommitContext(
                    **commit_context.model_dump(),
                    dataset_df=dataset_df,
                    filepath=filepath,
                ),
                db_writer=db_writer,
                s3_writer=s3_writer,
            )
        except Exception as exc:
            commit_failure(
                context=FailureCommitContext(
                    **commit_context.model_dump(), error_message=str(exc)
                ),
                db_writer=db_writer,
            )
            raise


def reconcile(db_writer: DBWriter, s3_writer: S3Writer) -> None:
    """Resolve stale PENDING runs left behind by mid-flight pipeline crashes.

    Queries ingestion_runs for rows that have been PENDING longer than
    ``INTERVAL_MINUTES`` minutes, then checks S3 for each. Rows whose S3 object
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
