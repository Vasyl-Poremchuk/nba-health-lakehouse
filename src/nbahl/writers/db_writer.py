import psycopg

from nbahl.common.models import IngestionRun
from nbahl.config import Settings


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

        Intended for one-time setup, not for regular pipeline runs.
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS ingestion_runs (
                    run_id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                    source VARCHAR(100),
                    started_at TIMESTAMPTZ,
                    ended_at TIMESTAMPTZ,
                    rows_in INTEGER,
                    status VARCHAR(10),
                    error_message TEXT
                );
                """
            )

    def write(self, ingestion_run: IngestionRun) -> None:
        """Insert one ingestion run record into ingestion_runs.

        Args:
            ingestion_run: Run metadata to persist.
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                t"""
                INSERT INTO ingestion_runs (source, started_at, ended_at, rows_in, status, error_message)
                VALUES (
                    {ingestion_run.source},
                    {ingestion_run.started_at},
                    {ingestion_run.ended_at},
                    {ingestion_run.rows_in},
                    {ingestion_run.status},
                    {ingestion_run.error_message}
                );
                """
            )
