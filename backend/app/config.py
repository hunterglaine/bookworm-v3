from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, PostgresDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Long enough to sign HS256 tokens (RFC 7518 requires >= 32 bytes) and obvious
# enough that seeing it in a log is a red flag.
DEFAULT_SECRET_KEY = "insecure-development-only-secret-key-change-me"


class Settings(BaseSettings):
    """Application config, read from environment or the repo-root .env file."""

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    secret_key: str = DEFAULT_SECRET_KEY
    cors_origins: str = "http://localhost:5173"

    postgres_user: str = "bookworm"
    postgres_password: str = "bookworm"
    postgres_db: str = "bookworm"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # Book data provider. Rate limited to 60 req/min, so responses get cached.
    hardcover_api_url: str = "https://api.hardcover.app/v1/graphql"
    hardcover_token: str = Field(default="")

    # Auth. The access token is short-lived because nothing can revoke it; the
    # refresh token is long-lived because the database can.
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30

    @property
    def cookie_secure(self) -> bool:
        """Secure cookies require HTTPS, which dev over localhost is not."""
        return self.environment != "development"

    @model_validator(mode="after")
    def _require_a_real_secret_in_production(self) -> Self:
        """Refuse to start rather than sign tokens with a published constant.

        Anyone holding this key can mint a valid session for any account, so a
        missing SECRET_KEY has to be a crash, not a warning nobody reads.
        """
        if self.environment == "production" and self.secret_key == DEFAULT_SECRET_KEY:
            raise ValueError("SECRET_KEY must be set when ENVIRONMENT=production")
        return self

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
