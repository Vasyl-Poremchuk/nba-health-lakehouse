from datetime import datetime

import pendulum
import structlog
from airflow.decorators import dag, task
from airflow.providers.amazon.aws.hooks.s3 import S3Hook

from nbahl.config import Settings

log = structlog.get_logger()
settings = Settings()


@dag(  # type: ignore[untyped-decorator]
    schedule=None,
    start_date=pendulum.datetime(2026, 6, 9, tz="UTC"),
    catchup=False,
    tags=["curr_date", "nbahl_env", "s3_objs"],
)
def smoke_test() -> None:
    """A smoke test DAG that verifies date logging, environment config, and S3 connectivity."""

    @task()  # type: ignore[untyped-decorator]
    def display_date() -> None:
        """A task that logs the current date."""
        log.info("DATE", date=datetime.now())

    @task()  # type: ignore[untyped-decorator]
    def display_nbahl_env() -> None:
        """A task that logs the value of the 'NBAHL_ENV' environment variable."""
        log.info("NBAHL_ENV", value=settings.nbahl_env)

    @task()  # type: ignore[untyped-decorator]
    def display_s3_files(bucket_name: str, prefix: str = "") -> None:
        """A task that logs a list of all objects in a bucket under a prefix.

        Args:
            bucket_name (str): The name of the bucket.
            prefix (str, optional): A key prefix. Defaults to "".
        """
        s3_hook = S3Hook(aws_conn_id=settings.aws_conn_id)
        obj_keys = s3_hook.list_keys(bucket_name=bucket_name, prefix=prefix)

        log.info(
            "Listing objects in bucket",
            bucket_name=bucket_name,
            prefix=prefix,
            keys=obj_keys,
        )

    display_date()
    display_nbahl_env()
    display_s3_files(bucket_name=f"nbahl-bronze-{settings.nbahl_env}")


smoke_test()
