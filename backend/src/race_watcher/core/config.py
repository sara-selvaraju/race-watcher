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
    # Shared secret for /admin endpoints (sent as X-Admin-Token). Unset = admin open, for local dev only.
    admin_token: str | None = Field(default=None, alias="ADMIN_TOKEN")
    # Last race day shown (inclusive), for a carnival spanning several days. Unset = one day.
    race_date_end: date | None = Field(default=None, alias="RACE_DATE_END")
    tz: str = Field(default="Australia/Melbourne", alias="TZ")

    # How often the worker fetches live odds while a race day is on. Each fetch is one
    # web-search LLM call per meeting, so this is the main cost dial.
    poll_interval_seconds: int = Field(default=900, alias="POLL_INTERVAL_SECONDS")
    # Fixed times (HH:MM in TZ, comma-separated) on each race day when every race still to run is
    # priced, whatever its start time. 09:15 catches the market after the big morning money.
    odds_check_times: str = Field(default="09:15", alias="ODDS_CHECK_TIMES")
    movement_threshold_pct: float = Field(default=10.0, alias="MOVEMENT_THRESHOLD_PCT")
    race_window_open_min_before: int = Field(default=120, alias="RACE_WINDOW_OPEN_MIN_BEFORE")
    race_window_close_min_after: int = Field(default=15, alias="RACE_WINDOW_CLOSE_MIN_AFTER")

    race_card_source: Literal["seed", "provider"] = Field(default="seed", alias="RACE_CARD_SOURCE")
    odds_source: Literal["betfair", "mock", "claude", "openrouter"] = Field(
        default="openrouter", alias="ODDS_SOURCE"
    )
    claude_research_model: str = Field(default="claude-sonnet-4-6", alias="CLAUDE_RESEARCH_MODEL")

    openrouter_api_key: str | None = Field(default=None, alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(default="anthropic/claude-sonnet-4.5", alias="OPENROUTER_MODEL")
    # Heavier model for /admin/refresh-tips and /admin/expand-field — Perplexity Sonar is
    # purpose-built for structured web research and finds complete fields more reliably.
    openrouter_research_model: str = Field(
        default="perplexity/sonar-pro", alias="OPENROUTER_RESEARCH_MODEL"
    )
    openrouter_web_search: bool = Field(default=True, alias="OPENROUTER_WEB_SEARCH")
    openrouter_site_url: str | None = Field(default=None, alias="OPENROUTER_SITE_URL")
    openrouter_app_name: str | None = Field(default="race-watcher", alias="OPENROUTER_APP_NAME")
    prediction_engine: Literal["heuristic"] = Field(default="heuristic", alias="PREDICTION_ENGINE")
    seed_file_path: Path = Field(default=Path("seed/flemington.json"), alias="SEED_FILE_PATH")
    # Which meetings/races to watch, and their card. See core/watchlist.py. If the file doesn't
    # exist, RACE_DATE..RACE_DATE_END and SEED_FILE_PATH are used instead.
    watch_file_path: Path = Field(default=Path("watch.json"), alias="WATCH_FILE_PATH")

    betfair_app_key: str | None = Field(default=None, alias="BETFAIR_APP_KEY")
    betfair_username: str | None = Field(default=None, alias="BETFAIR_USERNAME")
    betfair_password: str | None = Field(default=None, alias="BETFAIR_PASSWORD")
    betfair_cert_path: str | None = Field(default=None, alias="BETFAIR_CERT_PATH")
    betfair_cert_key_path: str | None = Field(default=None, alias="BETFAIR_CERT_KEY_PATH")

    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")

    @property
    def race_days(self) -> tuple[date, date]:
        """First and last race day shown (inclusive)."""
        return self.race_date, self.race_date_end or self.race_date

    @property
    def database_url_sync(self) -> str:
        # Alembic + SQLAlchemy sync engine use the same URL; psycopg driver is sync-capable.
        # Railway / Heroku-style hands us plain `postgresql://`; coerce so SQLAlchemy picks psycopg3.
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return url

    @field_validator("seed_file_path", "watch_file_path", mode="before")
    @classmethod
    def _resolve_seed_path(cls, v: str | Path) -> Path:
        p = Path(v)
        if not p.is_absolute():
            # resolve relative to the backend/ directory (cwd when running uv)
            return (Path.cwd() / p).resolve()
        return p


settings = Settings()
