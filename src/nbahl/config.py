from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded and validated from environment variables."""

    postgres_pipeline_meta_user: SecretStr
    postgres_pipeline_meta_password: SecretStr
    postgres_pipeline_meta_db: SecretStr

    nbahl_env: str
    profile_name: SecretStr
    aws_conn_id: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
