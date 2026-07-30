from datetime import timedelta

import psycopg
import structlog
from psycopg.rows import dict_row

from nbahl.common.constants import BaseConstants
from nbahl.common.enums import Status
from nbahl.common.models import IngestionRun
from nbahl.config import Settings

log = structlog.get_logger()


class DBWriter:
    """Writes ingestion run metadata to the PostgreSQL pipeline metadata database.

    Args:
        settings: Application settings providing PostgreSQL connection parameters.
    """

    def __init__(self, settings: Settings) -> None:
        self._user = settings.postgres_pipeline_meta_user.get_secret_value()
        self._password = (
            settings.postgres_pipeline_meta_password.get_secret_value()
        )
        self._dbname = settings.postgres_pipeline_meta_db.get_secret_value()
        self._host = settings.postgres_pipeline_meta_host
        self._port = settings.postgres_pipeline_meta_port

    def _connect(self) -> psycopg.Connection:
        """Open and return a psycopg connection to the pipeline metadata database.

        Returns:
            Open psycopg connection to the pipeline metadata database.
        """
        return psycopg.connect(
            host=self._host,
            port=self._port,
            dbname=self._dbname,
            user=self._user,
            password=self._password,
        )

    def create_table(self) -> None:
        """Create the ingestion_runs metadata table if it does not already exist.

        Uses ``CREATE TABLE IF NOT EXISTS``, so it's idempotent and safe to
        call on every pipeline run, not just for one-time setup.
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS ingestion_runs (
                    run_id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                    s3_key VARCHAR(100) NOT NULL,
                    started_at TIMESTAMPTZ NOT NULL,
                    ended_at TIMESTAMPTZ,
                    rows_in INTEGER,
                    status VARCHAR(10) NOT NULL,
                    error_message TEXT
                );
                """
            )
        log.info("Ensured ingestion_runs table exists")

    def write(self, ingestion_run: IngestionRun) -> int:
        """Insert one ingestion run record into ingestion_runs.

        Args:
            ingestion_run: Run metadata to persist.

        Returns:
            Auto-generated ``run_id`` of the newly inserted row.

        Raises:
            RuntimeError: If the INSERT statement returns no row.
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                t"""
                INSERT INTO ingestion_runs (s3_key, started_at, ended_at, rows_in, status, error_message)
                VALUES (
                    {ingestion_run.s3_key},
                    {ingestion_run.started_at},
                    {ingestion_run.ended_at},
                    {ingestion_run.rows_in},
                    {ingestion_run.status},
                    {ingestion_run.error_message}
                )
                RETURNING run_id;
                """
            )

            row = cur.fetchone()

            if row is None:
                raise RuntimeError(
                    "INSERT INTO ingestion_runs returned no run_id"
                )

            run_id = int(row[0])

        log.info(
            "Wrote ingestion run record",
            run_id=run_id,
            s3_key=ingestion_run.s3_key,
            status=ingestion_run.status,
        )

        return run_id

    def update(self, run_id: int, ingestion_run: IngestionRun) -> None:
        """Update outcome fields for an existing ingestion run record.

        Overwrites ``ended_at``, ``rows_in``, ``status``, and ``error_message``
        for the row identified by ``run_id``.

        Args:
            run_id: Primary key of the row to update.
            ingestion_run: Run metadata supplying the new field values.
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                t"""
                UPDATE ingestion_runs
                SET
                    ended_at = {ingestion_run.ended_at},
                    rows_in = {ingestion_run.rows_in},
                    status = {ingestion_run.status},
                    error_message = {ingestion_run.error_message}
                WHERE run_id = {run_id};
                """
            )

        log.debug(
            "Updated ingestion run record",
            run_id=run_id,
            status=ingestion_run.status,
        )

    def update_status(self, run_ids: list[int], status: Status) -> None:
        """Batch-update the status of multiple ingestion run records.

        No-op when ``run_ids`` is empty.

        Args:
            run_ids: Primary keys of the rows to update.
            status: Status value to set on all matching rows.
        """
        if not run_ids:
            return

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                t"""
                UPDATE ingestion_runs
                SET
                    status = {status}
                WHERE
                    run_id = ANY({run_ids});
                """
            )

        log.info(
            "Batch-updated ingestion run status",
            count=len(run_ids),
            status=status,
        )

    def get_stale_rows(self) -> list[dict[str, int | str]]:
        """Return PENDING rows that have been running longer than ``INTERVAL_MINUTES`` minutes.

        Returns:
            List of dicts with keys ``run_id`` and ``s3_key`` for each stale row.
        """
        interval_value = timedelta(minutes=BaseConstants.INTERVAL_MINUTES)

        with self._connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                t"""
                SELECT
                    run_id,
                    s3_key
                FROM
                    ingestion_runs
                WHERE
                    status = {Status.PENDING}
                    AND started_at < NOW() - {interval_value};
                """
            )

            stale_rows = cur.fetchall()

        return stale_rows
