"""Settings read from the environment, validated in one place.

main.py calls get_settings() at import, so the app refuses to start with a
missing or invalid setting and lists every problem at once, instead of
failing later (e.g. on the first login when SECRET_KEY is missing).

Scripts and Alembic only need the database, so database.py uses
database_url() and they don't need SECRET_KEY or the other app settings.
"""
import os
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator


class ConfigError(RuntimeError):
    """A required setting is missing or invalid."""


class Settings(BaseModel):
    DATABASE_URL: str
    # signs login tokens; generate one with: openssl rand -hex 32
    SECRET_KEY: str = Field(min_length=32)
    JWT_ALGORITHM: Literal["HS256", "HS384", "HS512"] = "HS256"
    JWT_EXPIRE_MINUTES: int = Field(default=720, gt=0)
    # comma-separated in the environment
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    @field_validator("DATABASE_URL")
    @classmethod
    def _postgres_url(cls, value: str) -> str:
        if not value.startswith("postgresql"):
            raise ValueError("must be a postgresql:// URL")
        return value

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value):
        if isinstance(value, str):
            value = [origin.strip() for origin in value.split(",") if origin.strip()]
        for origin in value:
            if not origin.startswith(("http://", "https://")):
                raise ValueError(f"{origin!r} must start with http:// or https://")
        return value

    @field_validator("OLLAMA_BASE_URL")
    @classmethod
    def _http_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("must start with http:// or https://")
        return value


def _from_environment(names) -> dict[str, str]:
    # an empty value (e.g. "SECRET_KEY=" copied from the example file) counts as unset
    return {name: os.environ[name] for name in names if os.environ.get(name, "").strip()}


def load_settings() -> Settings:
    try:
        return Settings(**_from_environment(Settings.model_fields))
    except ValidationError as exc:
        # messages only, never the values: SECRET_KEY must not end up in logs
        problems = "\n".join(
            f"  {'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        raise ConfigError(f"Invalid configuration:\n{problems}") from None


@lru_cache
def get_settings() -> Settings:
    return load_settings()


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise ConfigError("Invalid configuration:\n  DATABASE_URL: Field required")
    return url
