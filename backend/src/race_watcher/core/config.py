from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+psycopg://race:race@localhost:5432/race_watcher",
        alias="DATABASE_URL",
    )

    race_date: date = Field(default=date(2026, 6, 20), alias="RACE_DATE")
    tz: str = Field(default="Australia/Melbourne", alias="TZ")

    poll_interval_seconds: int = Field(default=300, alias="POLL_INTERVAL_SECONDS")
    movement_threshold_pct: float = Field(default=10.0, alias="MOVEMENT_THRESHOLD_PCT")
    race_window_open_min_before: int = Field(default=120, alias="RACE_WINDOW_OPEN_MIN_BEFORE")
    race_window_close_min_after: int = Field(default=15, alias="RACE_WINDOW_CLOSE_MIN_AFTER")

    race_card_source: Literal["seed", "provider"] = Field(default="seed", alias="RACE_CARD_SOURCE")
    odds_source: Literal["betfair", "mock"] = Field(default="mock", alias="ODDS_SOURCE")
    prediction_engine: Literal["heuristic"] = Field(default="heuristic", alias="PREDICTION_ENGINE")
    seed_file_path: Path = Field(default=Path("seed/flemington.json"), alias="SEED_FILE_PATH")

    betfair_app_key: str | None = Field(default=None, alias="BETFAIR_APP_KEY")
    betfair_username: str | None = Field(default=None, alias="BETFAIR_USERNAME")
    betfair_password: str | None = Field(default=None, alias="BETFAIR_PASSWORD")
    betfair_cert_path: str | None = Field(default=None, alias="BETFAIR_CERT_PATH")
    betfair_cert_key_path: str | None = Field(default=None, alias="BETFAIR_CERT_KEY_PATH")

    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")

    @property
    def database_url_sync(self) -> str:
        # Alembic + SQLAlchemy sync engine use the same URL; psycopg driver is sync-capable.
        return self.database_url

    @field_validator("seed_file_path", mode="before")
    @classmethod
    def _resolve_seed_path(cls, v: str | Path) -> Path:
        p = Path(v)
        if not p.is_absolute():
            # resolve relative to the backend/ directory (cwd when running uv)
            return (Path.cwd() / p).resolve()
        return p


settings = Settings()
