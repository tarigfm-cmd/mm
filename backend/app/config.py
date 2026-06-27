from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── Application ───────────────────────────────────────────────────────────
    app_name: str = "Pharmacy Clinical AI"
    app_version: str = "1.0.0"
    debug: bool = False
    secret_key: str = Field(default="change-me-in-production-min-50-chars-000000000000")
    log_level: str = "INFO"

    # ── AI Provider ───────────────────────────────────────────────────────────
    anthropic_api_key: str = Field(default="")
    ai_model: str = "claude-sonnet-4-6"
    ai_max_tokens: int = 4096
    ai_temperature: float = 0.7

    # ── Database ──────────────────────────────────────────────────────────────
    db_user: str = "postgres"
    db_password: str = "postgres"
    db_host: str = "db"
    db_port: int = 5432
    db_name: str = "clinical_ai"

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def database_url_sync(self) -> str:
        """Synchronous URL used by Alembic migrations."""
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://redis:6379/0"

    # ── CORS ──────────────────────────────────────────────────────────────────
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # ── File Upload ───────────────────────────────────────────────────────────
    upload_dir: str = "./uploads"
    max_upload_size: int = 52_428_800  # 50 MB
    allowed_extensions: List[str] = ["pdf", "png", "jpg", "jpeg", "txt", "docx"]

    @field_validator("allowed_extensions", mode="before")
    @classmethod
    def parse_extensions(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str):
            return [ext.strip().lower() for ext in v.split(",")]
        return v

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    rate_limit_per_minute: int = 60
    rate_limit_upload_per_minute: int = 10
    rate_limit_ai_per_minute: int = 20

    # ── Monitoring ────────────────────────────────────────────────────────────
    sentry_dsn: str = ""

    # ── Server ────────────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000


@lru_cache
def get_settings() -> Settings:
    return Settings()
