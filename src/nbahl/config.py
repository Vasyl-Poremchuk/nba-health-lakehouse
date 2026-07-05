from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded and validated from environment variables.

    Attributes:
        postgres_pipeline_meta_user: PostgreSQL username for the pipeline
            metadata database.
        postgres_pipeline_meta_password: PostgreSQL password for the pipeline
            metadata database.
        postgres_pipeline_meta_db: PostgreSQL database name for the pipeline
            metadata database.
        postgres_pipeline_meta_host: PostgreSQL host (default ``"localhost"``).
        postgres_pipeline_meta_port: PostgreSQL port (default ``5433``).
        nbahl_env: Deployment environment tag (e.g. ``"dev"``, ``"prod"``).
        profile_name: AWS named profile used for boto3 sessions.
        aws_conn_id: Airflow AWS connection identifier.
    """

    postgres_pipeline_meta_user: SecretStr
    postgres_pipeline_meta_password: SecretStr
    postgres_pipeline_meta_db: SecretStr
    postgres_pipeline_meta_host: str = "localhost"
    postgres_pipeline_meta_port: int = 5433

    nbahl_env: str
    profile_name: SecretStr
    aws_conn_id: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
