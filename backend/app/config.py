from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILES = (
    str(PROJECT_ROOT / ".env"),
    str(PROJECT_ROOT / "backend" / ".env"),
)


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./copilot_investor.db"
    test_database_url: str = "sqlite+aiosqlite:///./test.db"
    redis_url: str = "redis://localhost:6379"
    enable_scheduler: bool = True
    # Run a first monitoring pass the moment a thesis becomes monitorable, so a
    # freshly-onboarded user sees real signal in their first session instead of an
    # empty "all calm" dashboard. Prod safety valve if it strains API budgets.
    enable_first_pulse: bool = True
    # Shared secret that gates the global relevance-metrics endpoint
    # (GET /api/monitoring/relevance). Empty disables the endpoint entirely.
    metrics_token: str = ""

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    encryption_key: str = "change-me-32-byte-key-in-prod!!"  # Must be 32 bytes

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    openai_api_key: str = ""
    gemini_api_key: str = ""
    resend_api_key: str = ""
    sentry_dsn: str = ""
    trading212_base_url: str = "https://live.trading212.com/api/v0"
    alpha_vantage_api_key: str = ""
    market_data_provider: str = "yfinance"
    edgar_user_agent: str = "penKeep contact@penkeep.io"
    frontend_url: str = "http://localhost:3000"

    # LLM optimizations / reliability
    llm_response_cache_ttl_seconds: int = 15 * 60
    openai_prompt_cache_key: str = "thesis_decompose_v3"
    openai_prompt_cache_retention: str = "24h"  # "in_memory" | "24h"

    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
