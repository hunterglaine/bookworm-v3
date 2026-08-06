from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application config, read from environment or the repo-root .env file."""

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    secret_key: str = "change-me-in-real-environments"
    cors_origins: str = "http://localhost:5173"

    postgres_user: str = "bookworm"
    postgres_password: str = "bookworm"
    postgres_db: str = "bookworm"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # Book data provider. Rate limited to 60 req/min, so responses get cached.
    hardcover_api_url: str = "https://api.hardcover.app/v1/graphql"
    hardcover_token: str = Field(default="")

    @property
    def database_url(self) -> str:
        return str(
            PostgresDsn.build(
                scheme="postgresql+psycopg",
                username=self.postgres_user,
                password=self.postgres_password,
                host=self.postgres_host,
                port=self.postgres_port,
                path=self.postgres_db,
            )
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
